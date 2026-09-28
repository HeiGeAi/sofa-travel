"""Behavioral regression tests. No network or paid image requests."""
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import travel
import generate


def png(path, color=b"\x00\x70\x90"):
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"\0" + color)) + chunk(b"IEND", b""))
    return path


class TravelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def save(self, **kwargs):
        folder = self.root / "trip"
        travel.save_pack(travel.make_pack("大理", **kwargs), folder)
        return folder

    def test_modes_reference_roles_and_chinese_independent_prompts(self):
        for mode in travel.MODES:
            for destination in travel.destinations():
                pack = travel.make_pack(destination["id"], mode=mode, count=9)
                self.assertEqual([s["needs_reference"] for s in pack["shots"]], [mode != "faceless", mode != "faceless", False, False, mode != "faceless", mode != "faceless", False, mode != "faceless", False])
                for shot in pack["shots"]:
                    self.assertIn(destination["name"], shot["prompt"])
                    self.assertIn("独立照片", shot["prompt"])
                    self.assertNotIn("同上", shot["prompt"])
                    self.assertIsNone(shot["image"])
        pair = travel.make_pack("大理", mode="pet_pair")["shots"][0]["prompt"]
        self.assertIn("人物与宠物", pair)
        self.assertNotIn("不额外生成人类主人", pair)
        duo = travel.make_pack("大理", mode="duo")["shots"][0]["prompt"]
        self.assertIn("不默认情侣", duo)

    def test_invalid_options_and_repeatable_surprise(self):
        for kwargs in ({"mode": "oops"}, {"count": 4}, {"note": "长" * 501}):
            with self.assertRaises(ValueError):
                travel.make_pack(**kwargs)
        with self.assertRaises(ValueError):
            travel.resolve_destination("不存在")
        self.assertEqual(travel.make_pack(seed=42), travel.make_pack(seed=42))

    def test_cli_chinese_output_survives_non_utf8_pipe(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/travel.py"), "plan", "--destination", "京都", "--output", str(self.root / "京都")], env={**os.environ, "PYTHONIOENCODING": "ascii"}, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        self.assertEqual(json.loads(result.stdout.decode("utf-8"))["destination"], "京都")

    def test_real_import_status_history_and_portability(self):
        folder = self.save()
        first = png(self.root / "first.png")
        other = png(self.root / "other.png", b"\x20\x30\x40")
        target = travel.attach(folder, "01", first)
        pack = json.loads((folder / "trip.json").read_text(encoding="utf-8"))
        self.assertEqual(pack["status"], "partial_images")
        self.assertEqual(pack["shots"][0]["receipt"]["sha256"], hashlib.sha256(first.read_bytes()).hexdigest())
        self.assertEqual(pack["shots"][0]["receipt"]["visual_review"], "pending")
        self.assertIn("已导入 1/3", (folder / "旅行包.md").read_text(encoding="utf-8"))
        self.assertIn("data:image/png;base64,", (folder / "相册.html").read_text(encoding="utf-8"))
        travel.attach(folder, "01", other)
        pack = json.loads((folder / "trip.json").read_text(encoding="utf-8"))
        self.assertIn(target.relative_to(folder.resolve()).as_posix(), pack["shots"][0]["history"])
        self.assertTrue(target.is_file())
        for shot in ("02", "03"):
            travel.attach(folder, shot, first)
        self.assertEqual(json.loads((folder / "trip.json").read_text(encoding="utf-8"))["status"], "images_attached")

    def test_rejects_fake_images_without_claiming_success(self):
        folder = self.save()
        fake = self.root / "image.png"
        fake.write_text("<html>provider quota exceeded</html>")
        before = (folder / "trip.json").read_bytes()
        with self.assertRaises(ValueError):
            travel.attach(folder, "01", fake)
        self.assertEqual(before, (folder / "trip.json").read_bytes())
        valid = png(self.root / "real.png")
        fake.write_bytes(valid.read_bytes()[:-12])
        with self.assertRaises(ValueError):
            travel.image_info(fake)

    def test_no_overwrite_escaping_and_path_traversal(self):
        folder = self.save(note="</textarea><script>alert(1)</script>")
        with self.assertRaises(ValueError):
            travel.save_pack(travel.make_pack(), folder)
        album = (folder / "相册.html").read_text(encoding="utf-8")
        self.assertNotIn("<script>alert(1)</script>", album)
        self.assertIn("&lt;script&gt;", album)
        image = png(self.root / "outside.png")
        pack = json.loads((folder / "trip.json").read_text(encoding="utf-8"))
        pack["shots"][0]["image"] = "../outside.png"
        with self.assertRaises(ValueError):
            travel.render_album(pack, folder)

    def test_adapter_reference_counts_and_no_duplicate_jobs(self):
        folder = self.save(mode="pet_pair")
        skill = self.root / "provider"
        (skill / "scripts").mkdir(parents=True)
        for name in ("edit.py", "gen.py"):
            (skill / "scripts" / name).write_text("raise RuntimeError('must not execute during prepare')")
        ref = png(self.root / "ref.png")
        for refs in ([ref], [ref, ref]):
            jobs = generate.prepare(folder, skill, refs, "all")
            self.assertEqual(len(jobs), 3)
            self.assertEqual(jobs[-1]["needs_reference"], False)
            self.assertNotIn("--input", jobs[-1]["command"])
        with self.assertRaises(ValueError):
            generate.prepare(folder, skill, [])
        travel.attach(folder, "01", ref)
        self.assertEqual(generate.prepare(folder, skill, [], "first"), [])
        (folder / "generated").mkdir()
        png(folder / "generated/02.png")
        with self.assertRaises(ValueError):
            generate.prepare(folder, skill, [ref], "02")

    def test_adapter_failure_does_not_leak_logs_or_continue(self):
        folder = self.save(mode="faceless")
        skill = self.root / "provider"
        (skill / "scripts").mkdir(parents=True)
        (skill / "scripts/gen.py").write_text("import sys\nprint('SECRET_SENTINEL')\nsys.exit(7)\n")
        result = subprocess.run([sys.executable, str(ROOT / "scripts/generate.py"), "--trip", str(folder), "--skill-dir", str(skill), "--shots", "all", "--execute"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("SECRET_SENTINEL", result.stdout + result.stderr)
        self.assertNotIn("正在生成镜头 02", result.stdout)
        self.assertEqual(json.loads((folder / "trip.json").read_text(encoding="utf-8"))["status"], "prompts_only")


if __name__ == "__main__":
    unittest.main()
