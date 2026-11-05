import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
from tempfile import TemporaryDirectory
import unittest

from restore_s21_backup import restore


def fixture(folder, member="repo/research/example.txt"):
    content = b"frozen S21 evidence\n"
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        info = tarfile.TarInfo(member)
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
    packed = gzip.compress(buffer.getvalue(), mtime=0)
    parts = []
    for i, block in enumerate((packed[:31], packed[31:])):
        name = f"snapshot.tar.gz.part{i:03d}"
        (folder / name).write_bytes(block)
        parts.append(dict(path=name, size=len(block), sha256=hashlib.sha256(block).hexdigest()))
    manifest = dict(schema=1, archive_sha256=hashlib.sha256(packed).hexdigest(), parts=parts,
                    files=[dict(member=member, original_path="/old/machine/example.txt", size=len(content),
                                sha256=hashlib.sha256(content).hexdigest())])
    (folder / "manifest.json").write_text(json.dumps(manifest))
    return content


class BackupRestoreTest(unittest.TestCase):
    def test_split_archive_restores_verified_bytes_and_path_map(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp) / "snapshot"; folder.mkdir()
            content = fixture(folder)
            target = Path(temp) / "restored"
            report = restore(folder, target)
            self.assertEqual((target / "repo/research/example.txt").read_bytes(), content)
            self.assertEqual(report["verified_files"], 1)
            mapped = json.loads((target / "recovery-path-map.json").read_text())["/old/machine/example.txt"]
            self.assertTrue(Path(mapped).samefile(target / "repo/research/example.txt"))
            with self.assertRaises(FileExistsError):
                restore(folder, target)

    def test_corrupt_part_is_rejected_before_extraction(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp) / "snapshot"; folder.mkdir(); fixture(folder)
            (folder / "snapshot.tar.gz.part000").write_bytes(b"corrupt")
            target = Path(temp) / "restored"
            with self.assertRaises(ValueError):
                restore(folder, target)
            self.assertFalse(target.exists())

    def test_path_traversal_is_rejected(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp) / "snapshot"; folder.mkdir(); fixture(folder, "../outside.txt")
            with self.assertRaises(ValueError):
                restore(folder, Path(temp) / "restored")
            self.assertFalse((Path(temp) / "outside.txt").exists())


if __name__ == "__main__":
    unittest.main()
