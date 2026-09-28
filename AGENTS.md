# Sofa Travel development

This repository is an agent-native Chinese virtual travel experience, not a real travel booking service. Read SKILL.md when playing; read this file when developing.

Core: Python 3.10+ standard library only. The generated site must also work from file:// without a build, network, or external fonts. Destination data lives in data/destinations.json. Python is the canonical prompt compiler; the site consumes its precompiled variants, never a divergent second compiler.

All user-facing image prompts and repair instructions are Chinese. Preserve user choices. A prompt package is not a generated photo. No stock-photo fallback, silent model switch, undisclosed reference upload, or invented success receipt. Generated demo images feature a synthetic adult; personal photos belong in ignored output directories and never in a release ZIP.

Run python3 -m unittest discover -s tests -v, python3 scripts/build_site.py, and python3 scripts/package.py before release. Visually test desktop and mobile, file://, copy/download, keyboard, and reduced motion. Record the exact scope of live provider and host testing in docs/VERIFICATION.md. Do not claim untested platforms are verified.

No deployment, payment system, automatic scheduled publishing, or mandatory external service. Preserve upstream notices for any reused assets. Never embed secrets or workstation paths in distributable files.
