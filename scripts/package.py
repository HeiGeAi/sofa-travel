#!/usr/bin/env python3
"""Reproducible allowlisted ZIP for local Skill import. SKILL.md at archive root."""
import hashlib
import json
import zipfile
from pathlib import Path
from travel import ROOT, VERSION

FILES = [".gitignore", "SKILL.md", "START.md", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "agents/openai.yaml", "data/destinations.json", "scripts/travel.py", "scripts/generate.py", "references/director.md", "references/providers.md", "references/repairs.md", "docs/COMPATIBILITY.md", "site/index.html"]
FILES += ["AGENTS.md", "CONTRIBUTING.md", "docs/VERIFICATION.md", "assets/PROVENANCE.md", "assets/reference.jpg", "assets/paris-01.jpg", "assets/paris-02.jpg", "assets/paris-03.jpg", "scripts/build_site.py", "scripts/package.py", "site/template.html", "tests/test_travel.py", "tests/test_package.py"]
FILES += ["examples/paris-weekend/" + name for name in ["旅行包.md", "相册.html", "trip.json", "prompts/01.txt", "prompts/02.txt", "prompts/03.txt", "images/01-322656312e25.jpg", "images/02-1daa36643ad0.jpg", "images/03-982082306b63.jpg"]]

FILES += ["assets/woman-reference.jpg", "assets/kyoto-01.jpg", "assets/kyoto-02.jpg", "assets/kyoto-03.jpg"]

FILES += ["examples/kyoto-rain/" + name for name in ['旅行包.md', '相册.html', 'trip.json', 'reference-prompt.txt', 'prompts/01.txt', 'prompts/02.txt', 'prompts/03.txt', 'images/01-ff7a1afe89c8.jpg', 'images/02-00f5fcde2a58.jpg', 'images/03-455c13ecc321.jpg']]

def package():
    for name in FILES:
        if not (ROOT / name).is_file():
            raise ValueError("Missing release file: " + name)
    out = ROOT / "dist"
    out.mkdir(exist_ok=True)
    archive = out / f"sofa-travel-{VERSION}.zip"
    manifest = []
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in FILES:
            blob = (ROOT / name).read_bytes()
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, blob)
            manifest.append({"path": name, "sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob)})
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (out / (archive.name + ".sha256")).write_text(digest + "  " + archive.name + "\n", encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps({"version": VERSION, "files": manifest}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Built {archive.name}: {archive.stat().st_size:,} bytes; {len(FILES)} allowlisted files; SHA-256 {digest}")
    return archive


if __name__ == "__main__":
    package()
