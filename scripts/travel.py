#!/usr/bin/env python3
"""Sofa Travel: standard-library prompt core with optional image decoders."""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import io
import json
import os
import random
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.1.1"
STYLES = {
    "candid": ("朋友随手拍", "普通手机后置摄像头拍摄的旅行抓拍感，构图略有留白，肤质自然，清晰但不过度锐化，不使用影楼打光或过度虚化。"),
    "film": ("像一帧电影", "克制的旅行电影剧照感，自然光，柔和反差与细腻颗粒，色彩统一但不浓艳，保留环境细节，不添加电影标题或字幕。"),
    "playful": ("假期有点好笑", "真实手机照片里的轻松幽默，笑点来自动作和生活细节，不夸张身体比例，不把人变成卡通，不添加表情包文字。"),
}
MODES = {"portrait": "本人出镜", "faceless": "不露脸旅行", "duo": "双人同行", "pet": "宠物独自出镜", "pet_pair": "我和宠物同框"}
PLATFORMS = {"universal": "通用", "doubao": "豆包", "jimeng": "即梦", "native": "Agent 生图", "heige": "heige-image"}
REPAIRS = {
    "identity": ("不像本人", "以原始人物参考照片为身份依据，修正当前照片中人物的脸型、五官相对位置、眼镜、发型与年龄感。不要变成相似的陌生人。保留当前照片的场景、构图、动作、衣服与光线，仅修正人物身份。不要通过增强磨皮来处理相似度。"),
    "blend": ("像贴上去的", "保留人物身份、衣服、动作和背景布局，只修正人物与场景的融合：统一光源方向与色温，匹配镜头透视、人物尺度、边缘清晰度和景深，补全脚底或座椅接触阴影。不要更换人物或目的地。"),
    "natural": ("太像广告", "保留同一人物、地点和动作，把当前照片调整为普通朋友用手机拍下的旅行记录。减少磨皮、夸张轮廓光和背景虚化，恢复自然肤质、环境细节和轻微生活感。不要添加脏污或无意义噪点。"),
    "hands": ("手或动作奇怪", "保持人物身份、服装、场景和光线，修正不自然的手部与肢体关系。必要时把动作简化为自然垂手或轻扶包带，保持手指数目与关节合理，不重画整张脸，不更换背景。"),
    "place": ("地点不对", "保持人物身份和镜头构图，依据所提供的真实地点参考图修正背景建筑或地貌。不要把不同城市地标混在同一场景，不猜测参考图中看不到的结构。若没有地点参考，先索取或寻找可核对的参考，再修正。"),
}


def destinations():
    return json.loads((ROOT / "data/destinations.json").read_text(encoding="utf-8"))["destinations"]


def resolve_destination(value, seed=None):
    items = destinations()
    if value in ("surprise", "随机", "随便"):
        return random.Random(seed).choice(items)
    for item in items:
        if value.casefold() == item["id"] or value in item["aliases"]:
            return item
    raise ValueError("暂未收录这个目的地。运行 list 查看内置目的地；自定义地点请让 Agent 按 references/director.md 编排。")


def platform_help(platform, mode):
    reference = {"portrait": "上传一张清晰、无遮挡的本人照片。", "duo": "按顺序上传两位同行者各自授权的清晰照片，第一张是人物甲，第二张是人物乙。", "pet": "上传一张宠物照片作为外观参考。", "pet_pair": "上传一张你与宠物的清晰合照；支持多参考图时也可第一张放本人、第二张放宠物，明确两张图的用途。", "faceless": "无需上传人脸照片。"}[mode]
    if platform == "doubao":
        return reference + "打开豆包官方应用的图片生成或图片编辑功能，粘贴一张照片对应的完整提示词。入口名称和额度以当前应用为准；不要只发聊天文案。每张分别生成。"
    if platform == "jimeng":
        return reference + "在即梦官方图片生成功能中添加参考图（如需要），粘贴完整中文提示词；在界面选择三比四或最接近的竖幅比例。每张分别生成。额度以当前账号为准。"
    if platform in ("native", "heige"):
        return reference + "先检查当前工具是否支持参考图编辑。支持时用原始参考图生成第一张，再继续同组镜头；不支持时保留提示词交付，不冒充已生成。每次生成保留原始身份参考，不只依赖上一张成片。"
    return reference + "在支持中文提示词的官方生图工具中使用。人物或宠物模式还需要参考图能力；每张复制完整提示词，三比四比例优先。工具费用与额度按平台实际规则。"


def subject_text(mode, wardrobe):
    if mode == "pet_pair":
        return "以参考照片中的人物与宠物为同一个人和同一只动物；若有两张参考图，第一张用于人物身份，第二张用于宠物身份。分别保留人物的五官、发型、肤色、年龄感、体型和宠物的物种、毛色花纹、耳形与体型，不交换或融合特征。人物穿着" + wardrobe + "。宠物保持自然动物姿态，不穿人类衣服，人与宠物均远离水边和危险边缘。"
    if mode == "faceless":
        return "画面以旅行者第一视角或不露脸背影呈现，不出现可辨识的正脸，不需要构造用户的五官。背影人物穿着" + wardrobe + "。"
    if mode == "duo":
        return "参考图第一张的人物为甲，第二张为乙。两人均为授权同行者，分别保留各自脸型、五官比例、肤色、发型、年龄感和体型，禁止融合成一张脸或交换身份。两人关系保持中性，不默认情侣，不强行拥抱。两人服装保持各自参考照片中的穿搭，不交换衣服。"
    if mode == "pet":
        return "以参考照片中的宠物为同一只动物，保留物种、毛色花纹、耳朵形状、体型与眼睛特征，不改变品种，不拟人化，不强行穿人类衣服。画面不额外生成人类主人。"
    return "以我上传的原始参考照片为同一个人，保留脸型、五官比例、肤色、发型、眼镜等可见特征、年龄感和体型，不替换成网红脸，不改变性别呈现。人物统一穿着" + wardrobe + "。"


def make_pack(destination="surprise", mode="portrait", style="candid", platform="universal", count=3, seed=None, wardrobe="", note="", occasion="假期"):
    if mode not in MODES or style not in STYLES or platform not in PLATFORMS:
        raise ValueError("未知的人物模式、拍摄风格或平台。请查看命令帮助。")
    if count not in (3, 6, 9):
        raise ValueError("一组支持三张、六张或九张。")
    if len(note) > 500 or len(wardrobe) > 200 or len(occasion) > 30:
        raise ValueError("备注最多五百字，穿搭最多两百字，假期名称最多三十字。")
    d = resolve_destination(destination, seed)
    wardrobe = wardrobe.strip() or d["wardrobe"]
    appearance = subject_text(mode, wardrobe)
    walk = {"portrait": "人物自然走过，回头看向同行朋友的镜头", "faceless": "只出现旅行者背影，面部完全不可见", "duo": "甲在左侧略靠前，乙在右侧略靠后，并肩慢走，脸部彼此不遮挡", "pet": "宠物在安全平地上自然站立，四肢符合动物解剖结构", "pet_pair": "人物在安全平地蹲在宠物旁，轻扶松弛的牵引绳，两者都看向路边，不做复杂抱举动作"}[mode]
    pose = {"portrait": "人物占画面约三分之一，自然侧身看向镜头，双手轻松垂下", "faceless": "从旅行者背后拍摄，背影占画面约四分之一，不出现正脸", "duo": "两位人物站在画面左右两侧，彼此不遮挡，以朋友旅行合影的松弛姿态呈现", "pet": "宠物在画面前景的安全地面自然坐着，环境尺度真实，不放在危险边缘", "pet_pair": "人物自然坐在公共长椅上，宠物在旁边的安全平地，人物握着松弛的牵引绳，不把宠物放在肩头"}[mode]
    if style == "playful":
        pose += "，风轻轻吹乱头发或毛发，像刚拍照就被风打断的可爱瞬间"
    specs = [
        ("到了", "landmark", pose, "中景或环境人像，地标留在远处，人物与景物尺度自然", "柔和日间自然光", True),
        ("走走", "street", walk, "平视街头抓拍，环境占一半以上画面，避免路人抢占主体", "柔和日间自然光", True),
        ("歇一会儿", "food", "只拍桌上的食物与餐具，不出现人脸和手部，不出现商标，不宣称特定店铺", "坐在桌边的第一视角近景，不拼贴地标", "窗边柔和日光", False),
        ("看见", "landscape", "无人风景，主体是水面、山体或建筑的自然关系", "开阔的环境画面，层次清楚，地平线自然", "同一季节的午后自然光", False),
        ("绕个弯", "detour", walk, "中远景，人物占画面约五分之一，以环境讲述旅途", "接近傍晚的自然光", True),
        ("不想回去", "evening", pose, "环境人像，保留背景与前景的空间关系", "场景所描述的傍晚光线，人物曝光与环境协调", True),
        ("路过的细节", "street", "只拍路面、窗框或墙面与光影的细节，不出现人物、招牌文字和标志", "局部特写，保留天然材质，不制造与地点无关的道具", "斜射自然光", False),
        ("再停一分钟", "landmark", walk, "偏侧面机位，宽松取景，自然行走抓拍", "柔和日间自然光", True),
        ("最后一眼", "evening", "无人远景，留出大片天空，让画面安静下来", "远景收尾，不额外添加地标或烟花", "场景所描述的傍晚光线", False),
    ]
    selected = specs[:count]
    shots = []
    for i, (title, key, action, camera, light, has_subject) in enumerate(selected, 1):
        identity = appearance if has_subject else "这一张是同一趟旅行中的无人物插页，不出现旅行者，不需要人物参考照片。"
        prompt = "\n\n".join([
            f"请生成一张{d['name']}虚拟旅行相册中的独立照片。这是{occasion}的创意照片，不是实地拍摄记录。只生成这一张，不做九宫格或拼贴。",
            identity,
            f"场景：{d[key]}。季节与天气设定：{d['season']}。画面内容：{action}。",
            f"拍摄：{camera}。光线：{light}。{STYLES[style][1]}",
            "保持合理的建筑结构、人物透视、重力与接触阴影；不要重复地标，不把不同城市景物拼在一起，避免不自然的手部与肢体。不额外添加标题、签名或装饰文字。三比四竖幅构图，若工具不支持则使用最接近的竖幅。",
            *( ["本次额外创作要求：" + note.strip()] if note.strip() else [] ),
        ])
        shots.append({"id": f"{i:02d}", "title": title, "scene": d[key], "needs_reference": has_subject and mode != "faceless", "prompt": prompt, "status": "prompt_ready", "image": None})
    signature = json.dumps([d["id"], mode, style, platform, count, wardrobe, note, occasion], ensure_ascii=False)
    return {"schema_version": 1, "version": VERSION, "id": d["id"] + "-" + hashlib.sha256(signature.encode()).hexdigest()[:8], "destination": d, "settings": {"mode": mode, "style": style, "platform": platform, "count": count, "wardrobe": wardrobe, "note": note, "occasion": occasion}, "title": d["title"], "status": "prompts_only", "guide": platform_help(platform, mode), "caption": f"{d['caption']}\n实际行程：卧室、客厅、冰箱。\n本相册由 AI 创作，人在家里，想象在{d['name']}。", "shots": shots, "repairs": {k: {"title": v[0], "prompt": v[1]} for k, v in REPAIRS.items()}}


def markdown(pack):
    attached = sum(bool(s.get("image")) for s in pack["shots"])
    status = f"已导入 {attached}/{len(pack['shots'])} 张实际图片，图片质量仍需目视检查。" if attached else "中文提示词已就绪，尚未生成照片。"
    lines = [f"# 沙发旅行社｜{pack['title']}", "", "人没出门，相册先环游世界。", "", f"目的地：{pack['destination']['name']}。模式：{MODES[pack['settings']['mode']]}。风格：{STYLES[pack['settings']['style']][0]}。", "", "当前交付：" + status + "软件与提示词免费，生图费用或免费额度取决于所用工具。", "", "## 怎么拍", "", pack["guide"], "", "先生成第一张，检查人物相似度和光线，再继续。人物镜头始终带上原始参考图；风景和餐桌镜头无需人脸图。若使用成片辅助构图，明确原始图只管身份、成片只管穿搭与风格。", ""]
    for shot in pack["shots"]:
        lines += [f"## {shot['id']}｜{shot['title']}", "", "参考图：" + ("需要。使用原始人物或宠物参考图。" if shot["needs_reference"] else "不需要。"), "", "```text", shot["prompt"], "```", ""]
        if shot.get("image"):
            lines += [f"![{shot['title']}，AI 旅行创作]({shot['image']})", ""]
    lines += ["## 发相册时可以这样写", "", pack["caption"], "", "## 出图不满意", "", "修改已有成片时，保留原图并另存新版本。身份修复同时提供原始身份图和待修成片，明确两张图各自用途。", ""]
    for repair in pack["repairs"].values():
        lines += [f"### {repair['title']}", "", repair["prompt"], ""]
    return "\n".join(lines)


def render_album(pack, folder, *, image_overrides=None):
    """Portable single-file album: local user images embedded, no outgoing requests."""
    e = html.escape
    cards = []
    for shot in pack["shots"]:
        picture = '<div class="empty">这一页，等你抵达。<small>提示词已准备好，照片尚未导入</small></div>'
        if shot.get("image"):
            path = (folder / shot["image"]).resolve()
            if not path.is_relative_to(folder.resolve()):
                raise ValueError("相册图片路径越出旅行包目录。")
            if image_overrides and shot["image"] in image_overrides:
                payload, (mime, _, _) = image_overrides[shot["image"]]
            else:
                payload, (mime, _, _) = read_image(path)
            picture = f'<img alt="{e(shot["title"])}，AI 旅行创作" src="data:{mime};base64,{base64.b64encode(payload).decode()}">'
        cards.append(f'<article>{picture}<div class="body"><span>{shot["id"]} / {e(shot["scene"])}</span><h2>{e(shot["title"])}</h2><details><summary>打开完整中文提示词</summary><textarea readonly aria-label="{e(shot["title"])}的中文提示词">{e(shot["prompt"])}</textarea><button onclick="copyText(this.previousElementSibling,this)">复制提示词</button></details></div></article>')
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>沙发旅行社 · ''' + e(pack["title"]) + '''</title><style>
*{box-sizing:border-box}body{margin:0;padding:32px 24px 64px;background:#faf7ee;color:#1e2a38;font:17px/1.7 "PingFang SC","Microsoft YaHei",sans-serif}main{max-width:1100px;margin:auto}header{padding:40px 0}h1{font-size:clamp(32px,5vw,60px);line-height:1.2;color:#1f3f73}h2{margin:8px 0}header p{max-width:700px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:32px}article{background:#fffdf6;border:1px solid #d5dbe6;border-radius:12px;overflow:hidden}img{width:100%;display:block;aspect-ratio:3/4;object-fit:contain;background:#f0eee6}.body{padding:24px}span,small{font-size:13px;color:#5f5a50}small{display:block}.empty{aspect-ratio:3/2;display:flex;flex-direction:column;align-items:center;justify-content:center;background:repeating-linear-gradient(0deg,transparent,transparent 23px,#d5dbe6 24px)}textarea{width:100%;height:300px;margin:16px 0;padding:16px;font:15px/1.7 inherit;border:1px solid #d5dbe6;resize:vertical}button{background:#1f3f73;color:#fbf8ef;border:0;border-radius:8px;padding:14px 20px;font:inherit;cursor:pointer}summary{cursor:pointer}footer{margin-top:48px;white-space:pre-line}button:focus-visible,summary:focus-visible{outline:3px solid #1f3f73;outline-offset:4px}@media(max-width:650px){.grid{grid-template-columns:1fr}body{padding:16px}header{padding:24px 0}}
</style><main><header><p>SOFA TRAVEL / AI 创作相册</p><h1>''' + e(pack["title"]) + '''</h1><p>''' + e(pack["guide"]) + '''</p><p>本地相册，不上传照片。照片来自 AI 创作或用户导入，不代表实际到访。</p></header><section class="grid">''' + "".join(cards) + '''</section><footer>''' + e(pack["caption"]) + '''</footer></main><script>
async function copyText(area,button){try{await navigator.clipboard.writeText(area.value);button.textContent='已复制，去生图吧'}catch(e){area.focus();area.select();button.textContent='已选中，请手动复制'}}
</script></html>'''


def save_pack(pack, folder):
    folder = Path(folder)
    if folder.exists() and any(folder.iterdir()):
        raise ValueError("输出目录不是空目录。请选择新目录，已有旅行不会被覆盖。")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "trip.json").write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (folder / "旅行包.md").write_text(markdown(pack), encoding="utf-8")
    (folder / "相册.html").write_text(render_album(pack, folder), encoding="utf-8")
    prompts = folder / "prompts"
    prompts.mkdir(exist_ok=True)
    for shot in pack["shots"]:
        (prompts / (shot["id"] + ".txt")).write_text(shot["prompt"] + "\n", encoding="utf-8")


MAX_IMAGE_BYTES = 32 * 1024 * 1024
MAX_IMAGE_PIXELS = 32_000_000
MAX_DECODED_BYTES = 128 * 1024 * 1024


def _image_decoder():
    # Prompt creation remains standard-library-only. Importing or checking an
    # actual image requires a real decoder, never a signature-only fallback.
    try:
        from PIL import Image, ImageFile
    except ImportError as exc:
        raise ValueError("导入图片需要 Pillow 解码器。请执行 python3 -m pip install -r requirements-image.txt；不安装也可继续生成中文提示词旅行包。") from exc
    if ImageFile.LOAD_TRUNCATED_IMAGES:
        raise ValueError("图片解码器必须关闭 LOAD_TRUNCATED_IMAGES。")
    return Image


def _decode_jpeg_strict(data, width, height):
    # Pillow/libjpeg can recover an incomplete entropy stream even with
    # LOAD_TRUNCATED_IMAGES=False. Reject those warnings via strict libjpeg-turbo.
    try:
        from simplejpeg import decode_jpeg_header, decode_jpeg
    except ImportError as exc:
        raise ValueError("JPEG 导入还需要严格解码器，请执行 python3 -m pip install -r requirements-jpeg.txt；PNG 导入只需 Pillow。") from exc
    try:
        h, w, colorspace, _ = decode_jpeg_header(data, strict=True)
        if (w, h) != (width, height):
            raise ValueError("JPEG 解码器返回的尺寸不一致。")
        # Dimensions already passed our pixel/byte caps before this allocation.
        pixels = decode_jpeg(data, colorspace="CMYK" if colorspace in {"CMYK", "YCCK"} else "RGB", strict=True)
        if pixels.shape[:2] != (height, width):
            raise ValueError("JPEG 像素尺寸不一致。")
    except ValueError as exc:
        raise ValueError("JPEG 像素数据不完整或解码器报告损坏，请重新导出后导入。") from exc


def validate_image_bytes(data):
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("图片不能为空，单张最大三十二兆字节。")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        if len(data) < 45 or data[-12:] != b"\x00\x00\x00\x00IEND\xaeB`\x82":
            raise ValueError("图片不是完整的 PNG。")
    elif not (data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9")):
        raise ValueError("请使用完整 PNG 或 JPEG 图片，其他格式请在图像工具中另存后导入。")
    Image = _image_decoder()
    try:
        with Image.open(io.BytesIO(data), formats=["PNG", "JPEG"]) as decoded:
            width, height = decoded.size
            if not width or not height or width * height > MAX_IMAGE_PIXELS or width * height * 4 > MAX_DECODED_BYTES:
                raise ValueError("图片尺寸过大，最多三千二百万像素、128 MiB 像素缓冲区。")
            if getattr(decoded, "n_frames", 1) != 1:
                raise ValueError("请将动画另存为单张 PNG 或 JPEG 后导入。")
            mime = "image/png" if decoded.format == "PNG" else "image/jpeg"
            decoded.verify()
        # verify() checks the container, but only load() decodes the pixels.
        # Reopen the same bounded immutable snapshot after verify().
        with Image.open(io.BytesIO(data), formats=["PNG", "JPEG"]) as decoded:
            decoded.load()
    except (OSError, SyntaxError, IndexError, Image.DecompressionBombError) as exc:
        raise ValueError("图片无法完整解码，请在图像工具中重新导出 PNG 或 JPEG。") from exc
    if mime == "image/jpeg":
        _decode_jpeg_strict(data, width, height)
    return mime, width, height


def read_image(path):
    # A bounded single read prevents growth/changes between validation, hashing,
    # copying and HTML embedding from creating a false success receipt.
    with Path(path).open("rb") as source:
        data = source.read(MAX_IMAGE_BYTES + 1)
    return data, validate_image_bytes(data)


def image_info(path):
    return read_image(path)[1]


def _publish_attachment(folder, updates):
    """Stage all files first; restore prior files after a publication failure.

    Each replacement is atomic, with trip.json published last. This is rollback
    for caught I/O failures, not a multi-file transaction across a process crash.
    """
    staging = Path(tempfile.mkdtemp(prefix=".attach-", dir=folder))
    staged = []
    published = []
    created_directories = []
    keep_backups = False
    try:
        for index, (target, data) in enumerate(updates):
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise ValueError("相册输出必须是普通文件，不能是符号链接。")
            new = staging / f"{index}.new"
            with new.open("wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            backup = None
            if target.exists():
                backup = staging / f"{index}.old"
                shutil.copyfile(target, backup)
            staged.append((target, new, backup))
        for target, new, backup in staged:
            if not target.parent.exists():
                target.parent.mkdir()
                created_directories.append(target.parent)
            os.replace(new, target)
            published.append((target, backup))
    except BaseException:
        try:
            for target, backup in reversed(published):
                if backup is None:
                    target.unlink()
                else:
                    os.replace(backup, target)
            for directory in reversed(created_directories):
                directory.rmdir()
        except OSError as exc:
            # Keep the recovery files if the filesystem also rejects rollback.
            keep_backups = True
            raise OSError(f"导入失败且无法完全恢复，原文件备份保留于 {staging}") from exc
        raise
    finally:
        if not keep_backups:
            shutil.rmtree(staging)


def attach(folder, shot_id, image, source="user_import"):
    folder = Path(folder).resolve()
    pack = json.loads((folder / "trip.json").read_text(encoding="utf-8"))
    shot = next((s for s in pack["shots"] if s["id"] == shot_id), None)
    if not shot:
        raise ValueError("不存在这个镜头编号。")
    if source not in ("user_import", "native_generation", "heige_image"):
        raise ValueError("未知图片来源。")
    payload, (mime, width, height) = read_image(image)
    digest = hashlib.sha256(payload).hexdigest()
    relative = "images/" + shot_id + "-" + digest[:12] + (".png" if mime == "image/png" else ".jpg")
    dest = folder / relative
    if dest.parent.is_symlink() or dest.is_symlink():
        raise ValueError("相册图片输出不能是符号链接。")
    if dest.exists() and read_image(dest)[0] != payload:
        raise ValueError("同名相册图片与本次内容不一致，原文件已保留。")
    previous = shot.get("image")
    if previous and previous != relative:
        shot.setdefault("history", []).append(previous)
    shot.update(image=relative, status="image_attached", receipt={"source": source, "sha256": digest, "width": width, "height": height, "imported_at": datetime.now(timezone.utc).isoformat(), "visual_review": "pending"})
    pack["status"] = "images_attached" if all(s.get("image") for s in pack["shots"]) else "partial_images"
    # Render and validate every image before changing any output or receipt.
    album = render_album(pack, folder, image_overrides={relative: (payload, (mime, width, height))})
    updates = [] if dest.exists() else [(dest, payload)]
    updates += [
        (folder / "相册.html", album.encode("utf-8")),
        (folder / "旅行包.md", markdown(pack).encode("utf-8")),
        (folder / "trip.json", (json.dumps(pack, ensure_ascii=False, indent=2) + "\n").encode("utf-8")),
    ]
    _publish_attachment(folder, updates)
    return dest


def configure_console():
    """Agent subprocess pipes on Windows may default to a non-Chinese code page."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main():
    configure_console()
    parser = argparse.ArgumentParser(description="沙发旅行社：免费中文旅行提示词与本地相册")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="查看目的地")
    plan = commands.add_parser("plan", help="生成中文旅行包，不调用网络或生图接口")
    plan.add_argument("--destination", default="surprise")
    plan.add_argument("--mode", choices=MODES, default="portrait")
    plan.add_argument("--style", choices=STYLES, default="candid")
    plan.add_argument("--platform", choices=PLATFORMS, default="universal")
    plan.add_argument("--count", type=int, choices=(3, 6, 9), default=3)
    plan.add_argument("--seed", type=int)
    plan.add_argument("--wardrobe", default="")
    plan.add_argument("--note", default="")
    plan.add_argument("--occasion", default="假期")
    plan.add_argument("--output", required=True)
    imp = commands.add_parser("attach", help="把真实图片导入相册，保留历史版本")
    imp.add_argument("--trip", required=True)
    imp.add_argument("--shot", required=True)
    imp.add_argument("--image", required=True)
    imp.add_argument("--source", choices=("user_import", "native_generation", "heige_image"), default="user_import")
    repair = commands.add_parser("repair", help="输出中文修图指令")
    repair.add_argument("issue", choices=REPAIRS)
    args = vars(parser.parse_args())
    command = args.pop("command")
    try:
        if command == "list":
            for d in destinations():
                print(f"{d['id']:12s} {d['name']} · {d['title']}")
        elif command == "plan":
            output = Path(args.pop("output")).resolve()
            pack = make_pack(**args)
            save_pack(pack, output)
            print(json.dumps({"status": "prompts_only", "destination": pack["destination"]["name"], "folder": str(output), "shots": len(pack["shots"])}, ensure_ascii=False))
        elif command == "attach":
            print(attach(args["trip"], args["shot"], args["image"], args["source"]))
        else:
            print(REPAIRS[args["issue"]][1])
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print("未完成：" + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
