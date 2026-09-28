#!/usr/bin/env python3
"""Build the offline field guide from the canonical prompt compiler."""
import base64
import json
from pathlib import Path
from travel import ROOT, STYLES, MODES, PLATFORMS, REPAIRS, destinations, make_pack, platform_help


def build():
    packs = {}
    for d in destinations():
        for mode in MODES:
            for style in STYLES:
                pack = make_pack(d["id"], mode, style, count=9)
                packs[f"{d['id']}:{mode}:{style}"] = {k: pack[k] for k in ("title", "destination", "caption", "shots")}
    data = {"destinations": destinations(), "packs": packs, "modes": MODES, "styles": {k: v[0] for k, v in STYLES.items()}, "platforms": PLATFORMS, "guides": {f"{p}:{m}": platform_help(p, m) for p in PLATFORMS for m in MODES}, "repairs": {k: {"title": v[0], "prompt": v[1]} for k, v in REPAIRS.items()}}
    template = (ROOT / "site/template.html").read_text(encoding="utf-8")
    template = template.replace("__TRAVEL_DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c"))
    for name, filename in {"REFERENCE": "reference.jpg", "PARIS": "paris-01.jpg", "STREET": "paris-02.jpg", "FOOD": "paris-03.jpg"}.items():
        path = ROOT / "assets" / filename
        if not path.is_file():
            raise SystemExit(f"Missing real demonstration image: {path.name}. Build stops; no stock fallback.")
        template = template.replace(f"__{name}_IMAGE__", "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode())
    if "__TRAVEL_" in template or "_IMAGE__" in template:
        raise SystemExit("Unresolved template token")
    target = ROOT / "site/index.html"
    target.write_text(template, encoding="utf-8")
    print(f"Built {target.name}: {target.stat().st_size:,} bytes, {len(packs)} prompt variants, self-contained images.")


if __name__ == "__main__":
    build()
