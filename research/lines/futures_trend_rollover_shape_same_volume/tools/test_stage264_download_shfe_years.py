"""离线验证下载边界：无HTTP请求，不接触真实凭证。"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


SCRIPT = Path(__file__).with_name("stage264_download_shfe_years.py")


class ArchiveBoundaries(unittest.TestCase):
    def setUp(self):
        if not SCRIPT.is_file():
            self.fail("SHFE downloader boundary implementation is not available")
        spec = importlib.util.spec_from_file_location("stage264_download", SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make_zip(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr("sample.xls", bytes.fromhex("d0cf11e0a1b11ae1") + b"fixture")
        return buf.getvalue()

    def test_official_index_binding_rejects_a_changed_selection(self):
        index = self.root / "index.json"
        selection = self.root / "selection.json"
        index.write_text(json.dumps({"data": {"historicalData": [
            {"type": "1", "year": "2015", "url": "/reports/a.zip"}]}}))
        selection.write_text(json.dumps({"index_url": self.module.INDEX_URL,
            "index_sha256": hashlib.sha256(index.read_bytes()).hexdigest(), "selection": [
            {"type": "1", "year": "2015", "url": "https://example.org/not-official.zip"}]}))
        with self.assertRaises(ValueError):
            self.module.load_routes(index, selection)

    def test_archive_hash_mismatch_is_rejected(self):
        path = self.root / "2015.zip"
        path.write_bytes(self.make_zip())
        with self.assertRaises(ValueError):
            self.module.verify_archive(path, expected_sha="0" * 64)

    def test_gate_is_bound_to_the_actual_first_archive(self):
        path = self.root / "2015.zip"
        path.write_bytes(self.make_zip())
        state = {"first_sample_gate": {"gate": "pass", "archive_sha256": "0" * 64},
                 "years": [{"year": 2015, "status": "downloaded", "path": str(path)}]}
        with self.assertRaises(ValueError):
            self.module.require_first_sample_gate(state)

    def test_oversize_stream_never_creates_a_completed_archive(self):
        class Response:
            status_code = 200
            headers = {}
            def iter_content(self, chunk_size):
                yield b"x" * 9
        path = self.root / "2015.zip"
        with self.assertRaises(ValueError):
            self.module.write_response(Response(), path, max_bytes=8)
        self.assertFalse(path.exists())

    def test_existing_valid_archive_is_skipped_without_network(self):
        class ForbiddenNetwork:
            def get(self, *args, **kwargs):
                raise AssertionError("cached archive must not trigger HTTP")
        path = self.root / "2015.zip"
        body = self.make_zip()
        path.write_bytes(body)
        rec = {"year": 2015, "status": "downloaded", "path": str(path),
               "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
        result = self.module.download_one(rec, ForbiddenNetwork())
        self.assertEqual(result["action"], "verified_existing")
        self.assertEqual(path.read_bytes(), body)


if __name__ == "__main__":
    unittest.main()
