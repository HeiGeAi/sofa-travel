# 跨 Agent 使用

共用同一个 SKILL.md 和中文内容，不依赖某个厂商的工具名、模型 ID 或命令宏。先读 START.md，再按需读引用文件。

| 场景 | 最短路径 | 边界 |
| :--- | :--- | :--- |
| WorkBuddy 本地任务 | 提供仓库文件夹并让它读 START.md；或导入本地 Skill ZIP | 不能仅凭安装成功宣称生图可用 |
| Codex | 打开仓库，读取 SKILL.md；可复制到自己的技能目录 | 原生生图是否可用取决于当前工具 |
| Claude Code | 在仓库中读 SKILL.md；需要常驻时按其技能目录约定安装 | 不假设能直接调用 Codex 的工具 |
| 只有网页读取能力的 Agent | 读取 GitHub 的 START.md、SKILL.md 与所需参考文件 | 无文件写入时直接交付聊天文本 |
| 不能联网的 Agent | 用户提供解压后的文件夹或相关文档 | 首次使用不强制安装依赖 |
| 豆包、即梦 | 复制生成的中文提示词，在官方功能中上传参考图 | 这是手动生图路径，不是假设它们能安装本技能 |

## WorkBuddy

腾讯官方文档把 Skills 描述为可导入本地技能包的能力，并支持在授权范围内读取和写入本地文件。本项目提供两条入口：

一、文件夹入口。打开一个 WorkBuddy 本地任务，把解压后的项目文件夹交给它，输入：

```text
请读取这个文件夹里的 START.md 和 SKILL.md。用「沙发旅行社」带我去京都，三张，不露脸，给我可以复制到即梦的中文提示词。如果有文件工具，再给我做一本本地旅行手帐。
```

二、技能导入。使用 WorkBuddy 当前界面的「添加技能」或本地技能包导入功能，选择 `sofa-travel-1.1.1.zip`。ZIP 中 SKILL.md 位于根目录，无需再解压并套一层目录。导入后用自然语言说「沙发旅行社，带我去大理」。实际入口名称随版本变化，以当前界面为准。

没有 Python 时，Agent 直接读 JSON 数据与导演手册，输出完整中文内容。需要文件相册但宿主无命令能力时，可打开打包内的 site/index.html 选择与下载旅行包。它不会上传照片，也不需要后台服务。

官方依据（2026-09-28 查阅）：

* [WorkBuddy 产品说明](https://cloud.tencent.com/product/workbuddy)
* [WorkBuddy 技能说明](https://free-plat-test.qcloudcdn.com/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)
* [WorkBuddy 本地工作台](https://www.workbuddy.ai/docs/zh/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Task-Bar)

文档兼容、ZIP 结构验证、独立 Agent 行为测试和 WorkBuddy 应用实测是不同证据。各项状态见 VERIFICATION.md，不用「兼容」替代「已实测」。

## 图片导入的可选依赖

提示词、目的地列表与网页构建仍只需 Python 3.10+ 标准库。导入 PNG/JPEG 或检查参考图需要 `python3 -m pip install -r requirements-image.txt`（Pillow 12.3.0）；JPEG 另需 `python3 -m pip install -r requirements-jpeg.txt`，安装 simplejpeg 1.9.0 与 NumPy（Python 3.10 固定 2.2.6，Python 3.11+ 固定 2.3.5），增加数十 MB 安装体积；安装失败或离线未安装时可继续提示词流程，不能把只验文件头的图片标记为导入成功。依赖文件也包含在发布 ZIP 中。

[官方 simplejpeg 1.9.0](https://pypi.org/project/simplejpeg/1.9.0/) 提供常用 CPython 3.10–3.14 的 Linux glibc x64/arm64、Windows x64、macOS x64/arm64 wheel，采用 MIT 许可并有 PyPI Trusted Publishing 来源记录。其他平台可能需要自行编译；本项目不自动编译或安装系统工具，无法安装时请继续提示词流程或在图像工具中另存 PNG。严格解码拒绝解码器报告的错误与警告，不保证识别所有能正常解码的像素改动，也不判定照片语义。
