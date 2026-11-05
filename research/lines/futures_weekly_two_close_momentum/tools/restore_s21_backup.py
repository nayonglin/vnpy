"""Verify and restore a split, checksum-bound S21 research snapshot using stdlib only."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_relative(value):
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts or str(path) != value:
        raise ValueError(f"unsafe snapshot member: {value}")
    return Path(*path.parts)


def restore(snapshot, destination, repo=None):
    snapshot, destination = Path(snapshot).resolve(), Path(destination).resolve()
    if destination.exists():
        raise FileExistsError(f"destination must not exist: {destination}")
    manifest = json.loads((snapshot / "manifest.json").read_text())
    if manifest["schema"] != 1:
        raise ValueError("unsupported snapshot schema")
    expected = {}
    for row in manifest["files"]:
        safe_relative(row["member"])
        if row["member"] in expected:
            raise ValueError("duplicate snapshot member")
        expected[row["member"]] = row
    for part in manifest["parts"]:
        relative = safe_relative(part["path"])
        if len(relative.parts) != 1:
            raise ValueError("snapshot parts must be adjacent to the manifest")
        path = snapshot / relative
        if path.stat().st_size != part["size"] or digest(path) != part["sha256"]:
            raise ValueError(f"corrupt snapshot part: {part['path']}")
    if repo is not None:
        for row in manifest.get("code_files", []):
            path = Path(repo) / safe_relative(row["path"])
            if not path.is_file() or digest(path) != row["sha256"]:
                raise ValueError(f"checkout source differs from snapshot: {row['path']}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="s21-unpack-", dir=destination.parent) as temp:
        packed = Path(temp) / "snapshot.tar.gz"
        with packed.open("wb") as target:
            for part in manifest["parts"]:
                with (snapshot / part["path"]).open("rb") as source:
                    shutil.copyfileobj(source, target, length=1024 * 1024)
        if digest(packed) != manifest["archive_sha256"]:
            raise ValueError("combined snapshot checksum mismatch")
        destination.mkdir()
        seen = set()
        with tarfile.open(packed, "r|gz") as archive:
            for member in archive:
                if not member.isfile() or member.name not in expected or member.name in seen:
                    raise ValueError(f"unexpected archive member: {member.name}")
                row = expected[member.name]
                if member.size != row["size"]:
                    raise ValueError(f"size mismatch: {member.name}")
                target = destination / safe_relative(member.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                if digest(target) != row["sha256"]:
                    raise ValueError(f"restored file checksum mismatch: {member.name}")
                seen.add(member.name)
        if seen != set(expected):
            raise ValueError("snapshot is missing manifest members")
    paths = {row["original_path"]: str(destination / row["member"]) for row in expected.values()}
    (destination / "recovery-path-map.json").write_text(json.dumps(paths, ensure_ascii=False, indent=2) + "\n")
    report = dict(status="PASS", verified_files=len(seen),
                  verified_bytes=sum(row["size"] for row in expected.values()),
                  verified_code_files=len(manifest.get("code_files", [])) if repo is not None else 0,
                  archive_sha256=manifest["archive_sha256"])
    (destination / "restore-verification.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--repo", type=Path, help="also verify the normal Git source files")
    parser.add_argument("--verify-only", action="store_true", help="fully extract in temporary storage, then remove it")
    args = parser.parse_args()
    if args.verify_only:
        with tempfile.TemporaryDirectory(prefix="s21-restore-test-") as temp:
            report = restore(args.snapshot, Path(temp) / "restored", args.repo)
    elif args.destination is None:
        parser.error("provide --destination or --verify-only")
    else:
        report = restore(args.snapshot, args.destination, args.repo)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
