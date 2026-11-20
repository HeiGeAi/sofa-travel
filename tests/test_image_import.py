"""Offline complete-decoding and failure-preservation tests for image import."""
import base64
import builtins
import hashlib
import io
import json
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import travel


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))


def raw_png(rows=b'\0\0\0\0', width=1, height=1, interlace=0):
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, interlace))
            + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def encoded(fmt='PNG', mode='RGB', color='green', **kwargs):
    buffer = io.BytesIO()
    Image.new(mode, (2, 2), color).save(buffer, format=fmt, **kwargs)
    return buffer.getvalue()


class ImageImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / 'trip'
        travel.save_pack(travel.make_pack('paris'), self.folder)
        self.input = self.root / 'input.png'
        # A real previous image and history make preservation assertions useful.
        self.input.write_bytes(encoded(color='blue'))
        travel.attach(self.folder, '01', self.input)
        self.prior = encoded()
        with Image.open(io.BytesIO(self.prior)) as image:
            image.load()
        self.input.write_bytes(self.prior)
        self.previous = travel.attach(self.folder, '01', self.input)
        self.before = self.snapshot()

    def snapshot(self):
        return {p.relative_to(self.folder).as_posix(): p.read_bytes()
                for p in self.folder.rglob('*') if p.is_file()}

    def assert_preserved(self):
        self.assertEqual(self.snapshot(), self.before)
        self.assertEqual(self.previous.read_bytes(), self.prior)
        self.assertEqual(list(self.folder.glob('.attach-*')), [])

    def test_header_only_and_corrupt_png_cannot_change_outputs_history_or_receipt(self):
        header_only = b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR' + struct.pack('>II', 1, 1) + b'\0' * 10 + b'IEND'
        invalid = [header_only, raw_png(b'\x05\0\0\0'), self.prior[:-12],
                   self.prior[:33] + chunk(b'IEND', b''), raw_png(b'\0\0'), self.prior[:-1] + b'\xff']
        for data in invalid:
            with self.subTest(data=data):
                self.input.write_bytes(data)
                with self.assertRaises(ValueError):
                    travel.attach(self.folder, '01', self.input)
                self.assert_preserved()

    def test_complete_jpeg_and_png_variants_remain_supported(self):
        for mode in ('1', 'L', 'LA', 'P', 'RGB', 'RGBA', 'I;16'):
            with self.subTest(png_mode=mode):
                self.assertEqual(travel.validate_image_bytes(encoded(mode=mode, color=0)), ('image/png', 2, 2))
        self.assertEqual(travel.validate_image_bytes(raw_png(interlace=1)), ('image/png', 1, 1))
        for mode, progressive in (('RGB', False), ('RGB', True), ('L', False), ('CMYK', False)):
            with self.subTest(jpeg_mode=mode, progressive=progressive):
                self.assertEqual(travel.validate_image_bytes(encoded('JPEG', mode, color=0, progressive=progressive)), ('image/jpeg', 2, 2))
        self.input.write_bytes(encoded('JPEG'))
        dest = travel.attach(self.folder, '01', self.input)
        self.assertEqual(dest.suffix, '.jpg')
        self.assertTrue(self.previous.is_file())

    def test_truncated_and_header_only_jpeg_are_rejected(self):
        valid = encoded('JPEG')
        fake = b'\xff\xd8\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x03' + b'\0' * 9 + b'\xff\xd9'
        for data in (valid[:-2], valid[:len(valid)//2] + b'\xff\xd9', fake):
            with self.subTest(data=data):
                self.input.write_bytes(data)
                with self.assertRaises(ValueError):
                    travel.attach(self.folder, '01', self.input)
                self.assert_preserved()

    def test_missing_jpeg_entropy_with_end_marker_is_rejected(self):
        image = Image.new('RGB', (32, 32))
        image.putdata([((i * 7) % 256, (i * 29) % 256, (i * 71) % 256) for i in range(1024)])
        for progressive in (False, True):
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', progressive=progressive)
            valid = buffer.getvalue()
            self.assertEqual(travel.validate_image_bytes(valid), ('image/jpeg', 32, 32))
            sos = valid.index(b'\xff\xda')
            start = sos + 2 + int.from_bytes(valid[sos + 2:sos + 4], 'big')
            invalid = [valid[:start] + b'\xff\xd9']
            # Removing complete optional progressive scans can produce a valid
            # lower-refinement image. These cuts instead interrupt scan data.
            cuts = (10, 30, 100) if progressive else (10, 30, 100, 200)
            invalid += [valid[:-missing] + b'\xff\xd9' for missing in cuts]
            for data in invalid:
                with self.subTest(progressive=progressive, length=len(data)):
                    self.input.write_bytes(data)
                    with self.assertRaises(ValueError):
                        travel.attach(self.folder, '01', self.input)
                    self.assert_preserved()

    def test_unavailable_strict_jpeg_decoder_leaves_png_and_prompt_core_working(self):
        original_import = builtins.__import__
        def without_simplejpeg(name, *args, **kwargs):
            if name == 'simplejpeg' or name.startswith('simplejpeg.'):
                raise ImportError('strict JPEG decoder unavailable')
            return original_import(name, *args, **kwargs)
        jpeg = encoded('JPEG')
        with patch('builtins.__import__', side_effect=without_simplejpeg):
            self.assertEqual(travel.validate_image_bytes(self.prior), ('image/png', 2, 2))
            travel.save_pack(travel.make_pack('kyoto'), self.root / 'no-jpeg-deps')
            self.input.write_bytes(jpeg)
            with self.assertRaisesRegex(ValueError, 'requirements-jpeg.txt'):
                travel.attach(self.folder, '01', self.input)
        self.assert_preserved()

    def test_other_formats_and_animation_fail_closed(self):
        frames = io.BytesIO()
        Image.new('RGB', (2, 2), 'red').save(frames, format='PNG', save_all=True,
            append_images=[Image.new('RGB', (2, 2), 'blue')], duration=100, loop=0)
        for data in (encoded('GIF'), encoded('WEBP'), frames.getvalue()):
            with self.subTest(format=data[:12]):
                self.input.write_bytes(data)
                with self.assertRaises(ValueError):
                    travel.attach(self.folder, '01', self.input)
                self.assert_preserved()

    def test_pixel_and_file_limits_precede_full_decode(self):
        self.input.write_bytes(raw_png(width=32_000_001))
        with patch.object(ImageFile.ImageFile, 'load', side_effect=AssertionError('must not decode')):
            with self.assertRaisesRegex(ValueError, '尺寸过大'):
                travel.attach(self.folder, '01', self.input)
        self.assert_preserved()
        self.input.write_bytes(self.prior + b'x' * 128)
        with patch.object(travel, 'MAX_IMAGE_BYTES', 100), patch.object(travel, '_image_decoder') as decoder:
            with self.assertRaisesRegex(ValueError, '最大'):
                travel.attach(self.folder, '01', self.input)
            decoder.assert_not_called()
        self.assert_preserved()

    def test_unavailable_decoder_preserves_images_and_dependency_free_planning(self):
        original_import = builtins.__import__
        def without_pillow(name, *args, **kwargs):
            if name == 'PIL' or name.startswith('PIL.'):
                raise ImportError('decoder unavailable')
            return original_import(name, *args, **kwargs)
        with patch('builtins.__import__', side_effect=without_pillow):
            travel.save_pack(travel.make_pack('kyoto'), self.root / 'no-deps')
            with self.assertRaisesRegex(ValueError, 'requirements-image.txt'):
                travel.attach(self.folder, '01', self.input)
        self.assert_preserved()
        result = subprocess.run([sys.executable, '-S', str(ROOT / 'scripts/travel.py'), 'plan',
            '--destination', '京都', '--output', str(self.root / 'no-site-packages')], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_permissive_decoder_setting_is_rejected_not_changed(self):
        with patch.object(ImageFile, 'LOAD_TRUNCATED_IMAGES', True):
            with self.assertRaisesRegex(ValueError, 'LOAD_TRUNCATED_IMAGES'):
                travel.attach(self.folder, '01', self.input)
            self.assertTrue(ImageFile.LOAD_TRUNCATED_IMAGES)
        self.assert_preserved()

    def test_full_pixel_decoder_error_preserves_every_output(self):
        with patch.object(ImageFile.ImageFile, 'load', side_effect=OSError('bad pixels')):
            with self.assertRaisesRegex(ValueError, '完整解码'):
                travel.attach(self.folder, '01', self.input)
        self.assert_preserved()

    def test_same_validated_snapshot_is_hashed_stored_and_embedded(self):
        original = encoded(color='red')
        replacement = encoded(color='yellow')
        self.input.write_bytes(original)
        validate = travel.validate_image_bytes
        def change_source_after_validation(data):
            result = validate(data)
            self.input.write_bytes(replacement)
            return result
        with patch.object(travel, 'validate_image_bytes', side_effect=change_source_after_validation):
            dest = travel.attach(self.folder, '01', self.input)
        self.assertEqual(dest.read_bytes(), original)
        pack = json.loads((self.folder / 'trip.json').read_text(encoding='utf-8'))
        self.assertEqual(pack['shots'][0]['receipt']['sha256'], hashlib.sha256(original).hexdigest())
        self.assertIn(base64.b64encode(original).decode(), (self.folder / '相册.html').read_text(encoding='utf-8'))
        self.assertEqual(self.previous.read_bytes(), self.prior)

    def test_staging_write_failure_preserves_all_files(self):
        self.input.write_bytes(encoded(color='red'))
        with patch.object(travel.os, 'fsync', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                travel.attach(self.folder, '01', self.input)
        self.assert_preserved()

    def test_each_publication_failure_rolls_back_images_album_and_receipts(self):
        replace = travel.os.replace
        self.input.write_bytes(encoded(color='red'))
        for fail_at in range(1, 5):
            calls = 0
            def fail_once(source, target):
                nonlocal calls
                calls += 1
                if calls == fail_at:
                    raise OSError('replace failed')
                return replace(source, target)
            with self.subTest(fail_at=fail_at), patch.object(travel.os, 'replace', side_effect=fail_once):
                with self.assertRaisesRegex(OSError, 'replace failed'):
                    travel.attach(self.folder, '01', self.input)
            self.assert_preserved()

    def test_failure_on_first_import_does_not_leave_images_directory(self):
        empty = self.root / 'empty-trip'
        travel.save_pack(travel.make_pack('paris'), empty)
        with patch.object(travel.os, 'replace', side_effect=OSError('replace failed')):
            with self.assertRaises(OSError):
                travel.attach(empty, '01', self.input)
        self.assertFalse((empty / 'images').exists())
        pack = json.loads((empty / 'trip.json').read_text(encoding='utf-8'))
        self.assertEqual(pack['status'], 'prompts_only')


if __name__ == '__main__':
    unittest.main()
