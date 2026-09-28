#!/usr/bin/env python3
"""Optional heige-image bridge. Dry-run by default; no credentials managed here."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from travel import attach, image_info, configure_console


def prepare(trip, skill_dir, references, selection="first", python=sys.executable):
    trip, skill_dir = Path(trip).resolve(), Path(skill_dir).resolve()
    pack = json.loads((trip / "trip.json").read_text(encoding="utf-8"))
    shots = pack["shots"] if selection == "all" else [s for s in pack["shots"] if s["id"] == selection.zfill(2)] if selection != "first" else pack["shots"][:1]
    if not shots:
        raise ValueError("未找到请求的镜头。")
    pending = [s for s in shots if not s.get("image")]
    refs = [Path(r).resolve() for r in references]
    if any(s["needs_reference"] for s in pending):
        needed = 2 if pack["settings"]["mode"] == "duo" else 1
        allowed = (1, 2) if pack["settings"]["mode"] == "pet_pair" else (needed,)
        if len(refs) not in allowed:
            hint = "一张人与宠物合照，或按人物、宠物顺序的两张参考图" if pack["settings"]["mode"] == "pet_pair" else f"恰好 {needed} 张原始参考图"
            raise ValueError(f"当前模式需要{hint}。无人镜头单独生成时无需参考。")
        for ref in refs:
            image_info(ref)
    commands = []
    for shot in pending:
        script = skill_dir / "scripts" / ("edit.py" if shot["needs_reference"] else "gen.py")
        if not script.is_file():
            raise ValueError(f"heige-image 缺少 {script.name}。保留中文提示词，请使用具备相应能力的版本或官方生图工具。")
        output = trip / "generated" / (shot["id"] + ".png")
        if output.exists():
            raise ValueError(f"镜头 {shot['id']} 已有尚未导入的生成文件。请先检查并导入，避免重复计费。")
        command = [python, str(script), "--prompt", shot["prompt"], "-ar", "3:4", "-o", str(output), "--retry", "0"]
        if shot["needs_reference"]:
            for ref in refs:
                command += ["--input", str(ref)]
        commands.append({"shot": shot["id"], "command": command, "output": output, "needs_reference": shot["needs_reference"]})
    return commands


def main():
    configure_console()
    parser = argparse.ArgumentParser(description="调用用户已有的 heige-image，默认仅检查计划")
    parser.add_argument("--trip", required=True)
    parser.add_argument("--skill-dir", required=True)
    parser.add_argument("--reference", action="append", default=[])
    parser.add_argument("--shots", default="first", help="first、all 或镜头编号")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    try:
        if args.timeout < 1 or args.timeout > 900:
            raise ValueError("超时范围为一至九百秒。")
        jobs = prepare(args.trip, args.skill_dir, args.reference, args.shots, args.python)
        print(json.dumps({"mode": "execute" if args.execute else "dry_run", "pending_shots": [j["shot"] for j in jobs], "uploads_references": any(j["needs_reference"] for j in jobs), "note": "实际执行使用 heige-image 已有配置，可能产生费用。此脚本不验证账号额度或接口可用性。"}, ensure_ascii=False), flush=True)
        if not args.execute:
            return 0
        for job in jobs:
            job["output"].parent.mkdir(exist_ok=True)
            print("正在生成镜头 " + job["shot"], flush=True)
            result = subprocess.run(job["command"], capture_output=True, text=True, timeout=args.timeout, encoding="utf-8", errors="replace")
            if result.returncode != 0:
                # Upstream logs may echo credentials. Do not print or persist them.
                raise ValueError(f"镜头 {job['shot']} 的 heige-image 进程退出码为 {result.returncode}。本次停止，没有改换模型或自动重试。请在 heige-image 中检查依赖、配置和额度；提示词和已完成照片仍在。")
            if not job["output"].is_file():
                raise ValueError("工具没有返回实际图片文件，不能标记生图成功。")
            target = attach(args.trip, job["shot"], job["output"], "heige_image")
            print("已导入实际图片，仍需目视检查：" + str(target), flush=True)
        return 0
    except subprocess.TimeoutExpired:
        print("生图等待超时，已停止本地等待。上游可能仍在执行或计费，请先检查上游记录，不要立即重试。", file=sys.stderr)
        return 3
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print("未完成：" + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
