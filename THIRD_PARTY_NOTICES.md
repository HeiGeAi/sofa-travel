# 来源与署名

沙发旅行社代码、中文提示词编排与目的地资料由 HeiGeAi 为本项目原创编写，没有复制 ai-travel-studio 或其它写真 SaaS 的代码。

视觉采用 [HeiGe-Design](https://github.com/HeiGeAi/HeiGe-Design) 的 doodle-note（涂鸦本）设定：纸张底色、墨蓝、单次荧光笔重点、页边手绘箭头与手帐结构。该设计项目采用 MIT 许可证。Copyright (c) HeiGeAi。项目根目录 LICENSE 保留 MIT 许可全文。

assets 中 reference、paris-01、paris-02、paris-03 为本项目通过原生图像生成工具制作的虚构成年人物与虚拟旅行样片。没有使用真实用户身份照片，没有复制第三方图库。用于公开展示，不承诺地标每个细节均为纪实。格式压缩不改变图像内容。

字体仅声明系统与可选字体栈，不打包或远程加载第三方字体。

调研时参考了以下项目的产品结构，不代表其为本项目依赖或背书：

* SamurAIGPT/ai-travel-studio：目的地选择与旅行照流程。
* bethel-mark/travel-xhs-content：旅行 Skill 的资料组织方式。
* PicoTrex/Awesome-Nano-Banana-images：参考图、提示词与效果图的并列展示。
* TencentARC/PhotoMaker：身份一致性问题的技术背景。

## Optional image-validation dependencies

These packages are installed separately from PyPI, not vendored in the release ZIP:

* [Pillow 12.3.0](https://pypi.org/project/Pillow/12.3.0/): MIT-CMU license; PNG and JPEG container/pixel decoding.
* [simplejpeg 1.9.0](https://pypi.org/project/simplejpeg/1.9.0/): MIT license, Joachim Folz; strict JPEG decoding through its bundled libjpeg-turbo. Upstream wheels carry their library notices.
* [NumPy](https://numpy.org/doc/stable/license.html): BSD-3-Clause; simplejpeg output buffers. Requirements pin 2.2.6 for Python 3.10 and 2.3.5 for Python 3.11+.
