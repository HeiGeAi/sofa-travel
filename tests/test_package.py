"""Verify the actual public ZIP is portable, complete and allowlisted."""
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import package


class PackageTests(unittest.TestCase):
    def test_release_roundtrip_and_document_links(self):
        with tempfile.TemporaryDirectory() as directory:
            staging = Path(directory) / "source"
            for name in package.FILES:
                target = staging / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            (staging / "output").mkdir()
            (staging / "output/private.jpg").write_text("DO_NOT_PUBLISH")
            with patch.object(package, "ROOT", staging):
                archive = package.package()
                digest = hashlib.sha256(archive.read_bytes()).hexdigest()
                self.assertEqual(digest, hashlib.sha256(package.package().read_bytes()).hexdigest())
            with zipfile.ZipFile(archive) as z:
                self.assertIn("SKILL.md", z.namelist())
                self.assertNotIn("output/private.jpg", z.namelist())
                self.assertTrue(all(not n.startswith("/") and ".." not in Path(n).parts for n in z.namelist()))
                extracted = Path(directory) / "extracted"
                z.extractall(extracted)
            for document in extracted.rglob("*.md"):
                # Check explicit local Markdown links, not code examples.
                for target in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
                    if "://" not in target and not target.startswith("#"):
                        self.assertTrue((document.parent / target.split("#")[0]).exists(), f"{document.name}: {target}")
            result = subprocess.run([sys.executable, "scripts/travel.py", "plan", "--destination", "京都", "--mode", "faceless", "--platform", "jimeng", "--output", "output/fresh-trip"], cwd=extracted, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((extracted / "output/fresh-trip/相册.html").is_file())
            site = (extracted / "site/index.html").read_text(encoding="utf-8")
            self.assertNotIn("__TRAVEL_DATA__", site)
            self.assertNotRegex(site, r'<(?:img|script)[^>]+src="https?://')


if __name__ == "__main__":
    unittest.main()
