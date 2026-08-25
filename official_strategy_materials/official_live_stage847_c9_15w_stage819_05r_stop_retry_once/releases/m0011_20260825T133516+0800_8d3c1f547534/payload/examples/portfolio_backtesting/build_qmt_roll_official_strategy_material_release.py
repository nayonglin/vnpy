from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
from typing import Iterable, Iterator, Mapping

from qmt_roll_strategy_material_discovery import (
    DiscoveryResult,
    MaterialDeclaration,
    assert_discovery_publishable,
    discover_materials,
)
from qmt_roll_strategy_material_manifest import (
    MaterialFile,
    MaterialManifestError,
    MaterialRole,
    StorageKind,
    build_material_manifest,
    canonical_json_bytes,
    load_and_validate_material_manifest,
    serialize_material_manifest,
    sha256_file,
)
from qmt_roll_official_baseline_identity import (
    OFFICIAL_CONFIG_LOGICAL_PATH,
    OfficialBaselineIdentityError,
    assert_official_checkout_matches_active_material,
    ruleset_version_from_config,
)
from qmt_roll_official_strategy_material_resolver import (
    ActiveMaterialError,
    unique_inventory_row,
)


LFS_SIZE_THRESHOLD_BYTES = 10 * 1024 * 1024
MODEL_LFS_SUFFIXES = {".parquet", ".pkl", ".pickle", ".joblib", ".pt", ".pth", ".onnx"}
MATERIAL_ROOT_NAME = "official_strategy_materials"


class MaterialReleaseError(RuntimeError):
    """Raised when an official strategy-material release cannot proceed safely."""


@dataclass(frozen=True)
class GitLfsStatus:
    filters_ready: bool
    remote_ready: bool


@dataclass(frozen=True)
class ReleaseRequest:
    repo_root: Path
    official_version: str
    capital: float
    capital_label: str
    research_line: str
    source_commit: str
    created_at_utc: str
    created_at_cst: str
    discovery: DiscoveryResult
    provenance: Mapping[str, object]
    qualification: Mapping[str, object]
    parent_material_version: str = ""


@dataclass(frozen=True)
class PreparedRelease:
    release_id: str
    material_version: str
    release_dir: Path
    manifest_path: Path
    staged_paths: tuple[str, ...]


@dataclass(frozen=True)
class MasterPublication:
    release_id: str
    remote: str
    branch: str
    previous_remote_commit: str
    published_commit: str
    changed_paths: tuple[str, ...]
    status: str


@dataclass(frozen=True)
class OfficialPromotionPublication:
    release_id: str
    previous_remote_commit: str
    promoted_commit: str
    changed_paths: tuple[str, ...]
    source_commit: str
    ruleset_version: str
    status: str


def _git(repo_root: Path, *args: str, check: bool = True) -> str:
    forbidden = {"push", "reset", "stash"}
    if args and args[0] in forbidden:
        raise MaterialReleaseError(f"forbidden_git_operation:{args[0]}")
    if len(args) >= 2 and args[0] == "checkout" and args[1] == "--":
        raise MaterialReleaseError("forbidden_git_operation:checkout_restore")
    process = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if check and process.returncode != 0:
        message = process.stderr.strip() or process.stdout.strip() or "unknown"
        raise MaterialReleaseError(f"git_command_failed:{args[0] if args else 'git'}:{message}")
    return process.stdout


def _validate_remote_target(remote: str, branch: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", remote):
        raise MaterialReleaseError("publish_remote_invalid")
    if branch != "master":
        raise MaterialReleaseError("publish_branch_must_be_master")


def _remote_branch_head(repo_root: Path, remote: str, branch: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(repo_root), "ls-remote", "--heads", remote, branch],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        message = process.stderr.strip() or process.stdout.strip() or "unknown"
        raise MaterialReleaseError(f"remote_head_query_failed:{message}")
    rows = [line.split() for line in process.stdout.splitlines() if line.strip()]
    expected_ref = f"refs/heads/{branch}"
    exact = [row[0] for row in rows if len(row) == 2 and row[1] == expected_ref]
    if len(exact) != 1 or not re.fullmatch(r"[0-9a-f]{40}", exact[0]):
        raise MaterialReleaseError("remote_master_head_missing")
    return exact[0]


def _push_head_to_master(repo_root: Path, remote: str, branch: str) -> None:
    process = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "push",
            "--no-force",
            "--porcelain",
            remote,
            f"HEAD:refs/heads/{branch}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        message = process.stderr.strip() or process.stdout.strip() or "unknown"
        raise MaterialReleaseError(f"direct_master_push_failed:{message}")


def _push_commit_to_master(
    repo_root: Path,
    commit: str,
    remote: str,
    branch: str,
) -> None:
    process = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "push",
            "--no-force",
            "--porcelain",
            remote,
            f"{commit}:refs/heads/{branch}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        message = process.stderr.strip() or process.stdout.strip() or "unknown"
        raise MaterialReleaseError(f"complete_official_promotion_push_failed:{message}")


@contextmanager
def _detached_worktree(repo_root: Path, commit: str, *, prefix: str) -> Iterator[Path]:
    parent = Path(tempfile.mkdtemp(prefix=prefix))
    worktree = parent / "checkout"
    try:
        _git(repo_root, "worktree", "add", "--detach", str(worktree), commit)
        yield worktree
    finally:
        if worktree.exists():
            process = subprocess.run(
                ["git", "-C", str(repo_root), "worktree", "remove", "--force", str(worktree)],
                check=False,
                capture_output=True,
                text=True,
            )
            if process.returncode != 0:
                message = process.stderr.strip() or process.stdout.strip() or "unknown"
                raise MaterialReleaseError(f"temporary_worktree_cleanup_failed:{message}")
        try:
            parent.rmdir()
        except OSError as exc:
            raise MaterialReleaseError(f"temporary_worktree_parent_cleanup_failed:{parent}") from exc


def _write_bytes_atomically(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _repo_relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(repo_root.resolve(strict=True)).as_posix()
    except ValueError as exc:
        raise MaterialReleaseError(f"path_outside_repo:{path}") from exc


def _validate_logical_path(logical_path: str) -> None:
    path = PurePosixPath(logical_path)
    if not logical_path or path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise MaterialReleaseError(f"invalid_logical_path:{logical_path}")


def detect_git_lfs_status(repo_root: Path) -> GitLfsStatus:
    clean = _git(repo_root, "config", "--get", "filter.lfs.clean", check=False).strip()
    smudge = _git(repo_root, "config", "--get", "filter.lfs.smudge", check=False).strip()
    filters_ready = bool(clean and smudge)
    env_process = subprocess.run(
        ["git", "-C", str(repo_root), "lfs", "env"],
        check=False,
        capture_output=True,
        text=True,
    )
    output = f"{env_process.stdout}\n{env_process.stderr}"
    remote_ready = env_process.returncode == 0 and (
        "AccessUpload=basic" in output
        or "AccessUpload=none" not in output and "Endpoint=" in output and "Endpoint= (auth=none)" not in output
    )
    return GitLfsStatus(filters_ready=filters_ready, remote_ready=remote_ready)


def classify_storage(path: Path, *, lfs_status: GitLfsStatus) -> StorageKind:
    requires_lfs = path.stat().st_size > LFS_SIZE_THRESHOLD_BYTES or path.suffix.lower() in MODEL_LFS_SUFFIXES
    if not requires_lfs:
        return StorageKind.GIT
    if not lfs_status.filters_ready or not lfs_status.remote_ready:
        raise MaterialReleaseError("git_lfs_not_ready")
    return StorageKind.GIT_LFS


def lfs_attribute_lines(paths: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        f"/{path} filter=lfs diff=lfs merge=lfs -text"
        for path in sorted(set(paths))
    )


def assert_clean_source_tree(repo_root: Path, source_commit: str) -> None:
    head = _git(repo_root, "rev-parse", "HEAD").strip()
    if head != source_commit:
        raise MaterialReleaseError("source_commit_not_head")
    status = _git(repo_root, "status", "--porcelain", "--untracked-files=all")
    if status.strip():
        raise MaterialReleaseError("source_tree_not_clean")


@contextmanager
def publication_lock(repo_root: Path) -> Iterator[None]:
    lock_path = Path(_git(repo_root, "rev-parse", "--git-path", "strategy-material-publication.lock").strip())
    if not lock_path.is_absolute():
        lock_path = repo_root / lock_path
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _strategy_root(repo_root: Path, official_version: str) -> Path:
    if not official_version or "/" in official_version or official_version in {".", ".."}:
        raise MaterialReleaseError("official_version_invalid")
    return repo_root / MATERIAL_ROOT_NAME / official_version


def _load_index(strategy_root: Path) -> dict[str, object]:
    index_path = strategy_root / "index.json"
    if not index_path.exists():
        return {"schema_version": 1, "official_version": strategy_root.name, "releases": []}
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MaterialReleaseError("release_index_invalid") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1 or not isinstance(payload.get("releases"), list):
        raise MaterialReleaseError("release_index_invalid")
    return payload


def allocate_next_material_version(repo_root: Path, official_version: str) -> str:
    index = _load_index(_strategy_root(repo_root, official_version))
    versions: list[int] = []
    for release in index["releases"]:
        if not isinstance(release, dict):
            raise MaterialReleaseError("release_index_invalid")
        value = str(release.get("material_version", ""))
        if len(value) == 5 and value.startswith("m") and value[1:].isdigit():
            versions.append(int(value[1:]))
    return f"m{(max(versions, default=0) + 1):04d}"


def _release_id(material_version: str, created_at_cst: str, source_commit: str) -> str:
    parsed = datetime.fromisoformat(created_at_cst)
    timestamp = parsed.strftime("%Y%m%dT%H%M%S%z")
    return f"{material_version}_{timestamp}_{source_commit[:12]}"


def _normalized_git_file_mode(path: Path) -> int:
    """Preserve Git's executable bit while keeping material files non-writable."""

    return 0o755 if path.stat().st_mode & 0o111 else 0o644


def _parent_manifest(repo_root: Path, official_version: str) -> dict[str, object] | None:
    strategy_root = _strategy_root(repo_root, official_version)
    index = _load_index(strategy_root)
    releases = index["releases"]
    if not releases:
        return None
    latest = releases[-1]
    if not isinstance(latest, dict) or not latest.get("release_id"):
        raise MaterialReleaseError("release_index_invalid")
    path = strategy_root / "releases" / str(latest["release_id"]) / "manifest.json"
    return load_and_validate_material_manifest(path, release_root=path.parent)


def _copy_and_snapshot_all(
    *,
    repo_root: Path,
    declarations: Iterable[MaterialDeclaration],
    temporary: Path,
    lfs_status: GitLfsStatus,
) -> tuple[tuple[MaterialFile, ...], tuple[str, ...]]:
    files: list[MaterialFile] = []
    lfs_paths: list[str] = []
    for declaration in sorted(declarations, key=lambda item: item.logical_path):
        _validate_logical_path(declaration.logical_path)
        source = declaration.source_path if declaration.source_path.is_absolute() else repo_root / declaration.source_path
        if source.is_symlink() or not source.is_file():
            raise MaterialReleaseError(f"material_source_not_regular:{declaration.logical_path}")
        before_size = source.stat().st_size
        before_hash = sha256_file(source)
        storage = classify_storage(source, lfs_status=lfs_status)
        payload_relative = f"payload/{declaration.logical_path}"
        target = temporary / payload_relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(_normalized_git_file_mode(source))
        after_size = source.stat().st_size
        after_hash = sha256_file(source)
        if before_size != after_size or before_hash != after_hash or sha256_file(target) != before_hash:
            raise MaterialReleaseError(f"material_source_changed_during_copy:{declaration.logical_path}")
        if storage is StorageKind.GIT_LFS:
            final_relative = (
                Path(MATERIAL_ROOT_NAME)
                / temporary.parent.parent.name
                / "releases"
                / temporary.name
                / payload_relative
            ).as_posix()
            lfs_paths.append(final_relative)
        if declaration.source_kind == "repo":
            source_path = _repo_relative(repo_root, source)
        else:
            source_path = f"promotion_source:{source.name}"
        files.append(
            MaterialFile(
                logical_path=declaration.logical_path,
                payload_path=payload_relative,
                role=declaration.role,
                storage=storage,
                size_bytes=before_size,
                sha256=before_hash,
                source_path=source_path,
            )
        )
    return tuple(files), tuple(lfs_paths)


def _changes(parent: Mapping[str, object] | None, files: Iterable[MaterialFile]) -> dict[str, object]:
    current = {file.logical_path: file.sha256 for file in files}
    previous: dict[str, str] = {}
    if parent:
        previous = {
            str(row["logical_path"]): str(row["sha256"])
            for row in parent.get("files", [])
            if isinstance(row, dict)
        }
    added = sorted(set(current) - set(previous))
    deleted = sorted(set(previous) - set(current))
    changed = sorted(path for path in set(current) & set(previous) if current[path] != previous[path])
    return {
        "added": added,
        "changed": changed,
        "deleted": deleted,
        "added_count": len(added),
        "changed_count": len(changed),
        "deleted_count": len(deleted),
    }


def _write_release_metadata(
    *,
    temporary: Path,
    request: ReleaseRequest,
    material_version: str,
    release_id: str,
    files: tuple[MaterialFile, ...],
    parent: Mapping[str, object] | None,
) -> None:
    parent_version = request.parent_material_version
    if not parent_version and parent:
        parent_version = str(parent["material_version"])
    manifest = build_material_manifest(
        release_id=release_id,
        strategy_version=request.official_version,
        material_version=material_version,
        source_commit=request.source_commit,
        created_at_utc=request.created_at_utc,
        created_at_cst=request.created_at_cst,
        research_line=request.research_line,
        capital=request.capital,
        capital_label=request.capital_label,
        files=files,
        provenance=request.provenance,
        qualification=request.qualification,
        parent_material_version=parent_version,
        changes=_changes(parent, files),
    )
    (temporary / "manifest.json").write_bytes(serialize_material_manifest(manifest))
    with (temporary / "inventory.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("logical_path", "payload_path", "role", "storage", "size_bytes", "sha256", "source_path"),
            lineterminator="\n",
        )
        writer.writeheader()
        for row in manifest["files"]:
            writer.writerow(row)
    checksum_lines = [f"{row['sha256']}  {row['payload_path']}" for row in manifest["files"]]
    (temporary / "checksums.sha256").write_text("\n".join(checksum_lines) + ("\n" if checksum_lines else ""), encoding="utf-8")
    (temporary / "RELEASE.md").write_text(
        "\n".join(
            (
                f"# {release_id}",
                "",
                f"- 正式策略版本：`{request.official_version}`",
                f"- 物料版本：`{material_version}`",
                f"- 来源提交：`{request.source_commit}`",
                f"- 固化时间（CST）：`{request.created_at_cst}`",
                f"- 文件数：`{len(files)}`",
                "- 下单 API 调用：`0`",
                "",
                "本目录为不可变正式策略物料快照。发布提交与激活提交必须分离。",
                "",
            )
        ),
        encoding="utf-8",
    )


def verify_release_tree(release_dir: Path) -> dict[str, object]:
    for name in ("manifest.json", "inventory.csv", "checksums.sha256", "RELEASE.md"):
        path = release_dir / name
        if path.is_symlink() or not path.is_file():
            raise MaterialReleaseError(f"release_metadata_missing:{name}")
    try:
        manifest = load_and_validate_material_manifest(release_dir / "manifest.json", release_root=release_dir)
    except MaterialManifestError as exc:
        raise MaterialReleaseError(str(exc)) from exc
    inventory_rows = list(csv.DictReader((release_dir / "inventory.csv").read_text(encoding="utf-8").splitlines()))
    expected_rows = [
        {key: str(value) for key, value in row.items()}
        for row in manifest["files"]
    ]
    if inventory_rows != expected_rows:
        raise MaterialReleaseError("inventory_manifest_mismatch")
    checksum_expected = [f"{row['sha256']}  {row['payload_path']}" for row in manifest["files"]]
    checksum_actual = (release_dir / "checksums.sha256").read_text(encoding="utf-8").splitlines()
    if checksum_actual != checksum_expected:
        raise MaterialReleaseError("checksums_manifest_mismatch")
    return manifest


def _update_lfs_attributes(repo_root: Path, paths: Iterable[str]) -> bool:
    lines = lfs_attribute_lines(paths)
    if not lines:
        return False
    attributes = repo_root / ".gitattributes"
    existing = attributes.read_text(encoding="utf-8").splitlines() if attributes.exists() else []
    merged = sorted(set(existing) | set(lines))
    _write_bytes_atomically(attributes, ("\n".join(merged) + "\n").encode("utf-8"))
    return True


def _update_release_index_atomically(
    *,
    repo_root: Path,
    official_version: str,
    release_id: str,
    material_version: str,
    manifest: Mapping[str, object],
) -> Path:
    strategy_root = _strategy_root(repo_root, official_version)
    index = _load_index(strategy_root)
    releases = index["releases"]
    if any(isinstance(item, dict) and item.get("release_id") == release_id for item in releases):
        raise MaterialReleaseError("release_id_exists")
    releases.append(
        {
            "material_version": material_version,
            "release_id": release_id,
            "created_at_cst": manifest["created_at_cst"],
            "source_commit": manifest["source_commit"],
            "manifest_sha256": manifest["manifest_sha256"],
            "tree_fingerprint": manifest["tree_fingerprint"],
            "file_count": len(manifest["files"]),
        }
    )
    index_path = strategy_root / "index.json"
    _write_bytes_atomically(index_path, canonical_json_bytes(index) + b"\n")
    return index_path


def _stage_release_paths_only(repo_root: Path, paths: Iterable[Path]) -> tuple[str, ...]:
    relative = tuple(sorted({_repo_relative(repo_root, path) for path in paths}))
    _git(repo_root, "add", "--", *relative)
    staged = tuple(
        sorted(
            line.strip()
            for line in _git(repo_root, "diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines()
            if line.strip()
        )
    )
    allowed_files: set[str] = set()
    for item in relative:
        target = repo_root / item
        if target.is_dir():
            allowed_files.update(
                _repo_relative(repo_root, path)
                for path in target.rglob("*")
                if path.is_file()
            )
        else:
            allowed_files.add(item)
    if set(staged) != allowed_files:
        raise MaterialReleaseError("staged_path_outside_release_allowlist")
    return staged


def prepare_release(request: ReleaseRequest) -> PreparedRelease:
    repo_root = request.repo_root.resolve(strict=True)
    assert_clean_source_tree(repo_root, request.source_commit)
    assert_discovery_publishable(request.discovery)
    with publication_lock(repo_root):
        material_version = allocate_next_material_version(repo_root, request.official_version)
        release_id = _release_id(material_version, request.created_at_cst, request.source_commit)
        strategy_root = _strategy_root(repo_root, request.official_version)
        releases_root = strategy_root / "releases"
        releases_root.mkdir(parents=True, exist_ok=True)
        final = releases_root / release_id
        if final.exists():
            raise MaterialReleaseError("release_id_exists")
        temporary = Path(tempfile.mkdtemp(prefix=f".{release_id}.tmp-", dir=str(releases_root)))
        published = False
        attributes_changed = False
        try:
            parent = _parent_manifest(repo_root, request.official_version)
            files, lfs_paths = _copy_and_snapshot_all(
                repo_root=repo_root,
                declarations=request.discovery.declarations,
                temporary=temporary,
                lfs_status=detect_git_lfs_status(repo_root),
            )
            _write_release_metadata(
                temporary=temporary,
                request=request,
                material_version=material_version,
                release_id=release_id,
                files=files,
                parent=parent,
            )
            verify_release_tree(temporary)
            os.replace(temporary, final)
            published = True
            manifest = verify_release_tree(final)
            index_path = _update_release_index_atomically(
                repo_root=repo_root,
                official_version=request.official_version,
                release_id=release_id,
                material_version=material_version,
                manifest=manifest,
            )
            if lfs_paths:
                corrected = [
                    str(path).replace(f"/{temporary.name}/", f"/{release_id}/")
                    for path in lfs_paths
                ]
                attributes_changed = _update_lfs_attributes(repo_root, corrected)
            stage_paths = [final, index_path]
            if attributes_changed:
                stage_paths.append(repo_root / ".gitattributes")
            staged_paths = _stage_release_paths_only(repo_root, stage_paths)
            prepared = PreparedRelease(release_id, material_version, final, final / "manifest.json", staged_paths)
            _write_prepared_receipt(repo_root, prepared)
            return prepared
        except Exception:
            if not published and temporary.exists():
                shutil.rmtree(temporary)
            raise


def _prepared_receipt_path(repo_root: Path, release_id: str) -> Path:
    git_path = Path(_git(repo_root, "rev-parse", "--git-path", f"strategy-material-{release_id}.prepared.json").strip())
    return git_path if git_path.is_absolute() else repo_root / git_path


def _write_prepared_receipt(repo_root: Path, prepared: PreparedRelease) -> None:
    payload = {
        "release_id": prepared.release_id,
        "material_version": prepared.material_version,
        "release_dir": _repo_relative(repo_root, prepared.release_dir),
        "manifest_path": _repo_relative(repo_root, prepared.manifest_path),
        "staged_paths": list(prepared.staged_paths),
    }
    _write_bytes_atomically(_prepared_receipt_path(repo_root, prepared.release_id), canonical_json_bytes(payload) + b"\n")


def _load_prepared_receipt(repo_root: Path, release_id: str) -> PreparedRelease:
    path = _prepared_receipt_path(repo_root, release_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MaterialReleaseError("prepared_release_receipt_missing") from exc
    return PreparedRelease(
        release_id=str(payload["release_id"]),
        material_version=str(payload["material_version"]),
        release_dir=repo_root / str(payload["release_dir"]),
        manifest_path=repo_root / str(payload["manifest_path"]),
        staged_paths=tuple(str(item) for item in payload["staged_paths"]),
    )


def assert_exact_staged_paths(repo_root: Path, allowed: Iterable[str]) -> None:
    actual = {
        line.strip()
        for line in _git(repo_root, "diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines()
        if line.strip()
    }
    if actual != set(allowed):
        raise MaterialReleaseError("staged_path_outside_release_allowlist")


def commit_prepared_release(*, repo_root: Path, prepared: PreparedRelease, confirmation: str) -> str:
    required = f"I_UNDERSTAND_THIS_COMMITS_OFFICIAL_STRATEGY_MATERIALS:{prepared.release_id}"
    if confirmation != required:
        raise MaterialReleaseError("release_commit_confirmation_missing")
    verify_release_tree(prepared.release_dir)
    _verify_all_material_releases(repo_root / MATERIAL_ROOT_NAME)
    assert_exact_staged_paths(repo_root, prepared.staged_paths)
    _git(repo_root, "commit", "-m", f"release(materials): {prepared.release_id}")
    return _git(repo_root, "rev-parse", "HEAD").strip()


def assert_release_commit_contains_exact_release(repo_root: Path, release_id: str, release_commit: str) -> Path:
    _git(repo_root, "cat-file", "-e", f"{release_commit}^{{commit}}")
    matches = _git(
        repo_root,
        "ls-tree",
        "-r",
        "--name-only",
        release_commit,
        "--",
        MATERIAL_ROOT_NAME,
    ).splitlines()
    candidates = [line for line in matches if f"/releases/{release_id}/manifest.json" in line]
    if len(candidates) != 1:
        raise MaterialReleaseError("release_commit_missing_exact_release")
    return repo_root / candidates[0]


def assert_exact_release_commit(repo_root: Path, release_id: str, release_commit: str) -> Path:
    manifest_path = assert_release_commit_contains_exact_release(repo_root, release_id, release_commit)
    subject = _git(repo_root, "show", "-s", "--format=%s", release_commit).strip()
    if subject != f"release(materials): {release_id}":
        raise MaterialReleaseError("release_commit_subject_invalid")
    changed = {
        line.strip()
        for line in _git(
            repo_root,
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            release_commit,
        ).splitlines()
        if line.strip()
    }
    release_dir = PurePosixPath(manifest_path.relative_to(repo_root).as_posix()).parent
    strategy_root = release_dir.parent.parent
    allowed_exact = {str(strategy_root / "index.json"), ".gitattributes"}
    if not changed or any(
        path not in allowed_exact and not path.startswith(f"{release_dir.as_posix()}/")
        for path in changed
    ):
        raise MaterialReleaseError("release_commit_changed_paths_invalid")
    return manifest_path


def _assert_regular_tree(root: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise MaterialReleaseError("material_root_not_regular")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise MaterialReleaseError(f"material_publish_symlink_forbidden:{path.relative_to(root).as_posix()}")


def _assert_same_tree(left: Path, right: Path) -> None:
    left_files = {
        path.relative_to(left).as_posix(): sha256_file(path)
        for path in left.rglob("*")
        if path.is_file()
    }
    right_files = {
        path.relative_to(right).as_posix(): sha256_file(path)
        for path in right.rglob("*")
        if path.is_file()
    }
    if left_files != right_files:
        raise MaterialReleaseError("remote_material_release_immutable_conflict")


def _merge_release_index(source: Path, target: Path) -> None:
    source_payload = _load_index(source.parent)
    target_payload = _load_index(target.parent)
    if source_payload.get("official_version") != target_payload.get("official_version"):
        raise MaterialReleaseError("release_index_official_version_mismatch")
    merged: dict[str, dict[str, object]] = {}
    versions: dict[str, str] = {}
    for item in (*target_payload["releases"], *source_payload["releases"]):
        if not isinstance(item, dict) or not item.get("release_id"):
            raise MaterialReleaseError("release_index_invalid")
        release_id = str(item["release_id"])
        material_version = str(item.get("material_version", ""))
        if not re.fullmatch(r"m\d{4}", material_version):
            raise MaterialReleaseError("release_index_invalid")
        prior_release_id = versions.get(material_version)
        if prior_release_id is not None and prior_release_id != release_id:
            raise MaterialReleaseError("remote_material_version_conflict")
        versions[material_version] = release_id
        if release_id in merged and merged[release_id] != item:
            raise MaterialReleaseError("remote_release_index_conflict")
        merged[release_id] = dict(item)
    target_payload["releases"] = sorted(
        merged.values(),
        key=lambda item: (str(item.get("material_version", "")), str(item.get("release_id", ""))),
    )
    _write_bytes_atomically(target, canonical_json_bytes(target_payload) + b"\n")


def _merge_material_root(source_root: Path, target_root: Path) -> None:
    _assert_regular_tree(source_root)
    if not target_root.exists():
        target_root.mkdir(parents=True)
    else:
        _assert_regular_tree(target_root)
    for source_strategy in sorted(path for path in source_root.iterdir() if path.is_dir()):
        target_strategy = target_root / source_strategy.name
        target_strategy.mkdir(parents=True, exist_ok=True)
        source_releases = source_strategy / "releases"
        target_releases = target_strategy / "releases"
        target_releases.mkdir(parents=True, exist_ok=True)
        for source_release in sorted(path for path in source_releases.iterdir() if path.is_dir()):
            target_release = target_releases / source_release.name
            if target_release.exists():
                _assert_regular_tree(target_release)
                _assert_same_tree(source_release, target_release)
            else:
                shutil.copytree(source_release, target_release)
        source_index = source_strategy / "index.json"
        target_index = target_strategy / "index.json"
        if target_index.exists():
            _merge_release_index(source_index, target_index)
        else:
            shutil.copyfile(source_index, target_index)


def _verify_all_material_releases(material_root: Path) -> None:
    _assert_regular_tree(material_root)
    manifests = sorted(material_root.glob("*/releases/*/manifest.json"))
    if not manifests:
        raise MaterialReleaseError("material_publish_has_no_releases")
    for manifest in manifests:
        verify_release_tree(manifest.parent)
    for strategy_root in sorted(path for path in material_root.iterdir() if path.is_dir()):
        index = _load_index(strategy_root)
        if index.get("official_version") != strategy_root.name:
            raise MaterialReleaseError("release_index_official_version_mismatch")
        rows = index["releases"]
        indexed: dict[str, dict[str, object]] = {}
        versions: dict[str, str] = {}
        for row in rows:
            if not isinstance(row, dict) or not row.get("release_id"):
                raise MaterialReleaseError("release_index_invalid")
            release_id = str(row["release_id"])
            material_version = str(row.get("material_version", ""))
            if release_id in indexed:
                raise MaterialReleaseError("release_index_duplicate_release_id")
            if material_version in versions and versions[material_version] != release_id:
                raise MaterialReleaseError("remote_material_version_conflict")
            indexed[release_id] = row
            versions[material_version] = release_id
        actual_dirs = {
            path.name: path
            for path in (strategy_root / "releases").iterdir()
            if path.is_dir()
        }
        if set(indexed) != set(actual_dirs):
            raise MaterialReleaseError("release_index_directory_set_mismatch")
        for release_id, release_dir in actual_dirs.items():
            manifest = verify_release_tree(release_dir)
            expected = {
                "material_version": manifest["material_version"],
                "release_id": manifest["release_id"],
                "created_at_cst": manifest["created_at_cst"],
                "source_commit": manifest["source_commit"],
                "manifest_sha256": manifest["manifest_sha256"],
                "tree_fingerprint": manifest["tree_fingerprint"],
                "file_count": len(manifest["files"]),
            }
            if manifest["strategy_version"] != strategy_root.name or indexed[release_id] != expected:
                raise MaterialReleaseError("release_index_manifest_mismatch")


def _material_root_uses_lfs(material_root: Path) -> bool:
    for manifest_path in material_root.glob("*/releases/*/manifest.json"):
        manifest = verify_release_tree(manifest_path.parent)
        if any(str(row.get("storage")) == StorageKind.GIT_LFS.value for row in manifest["files"]):
            return True
    return False


def publish_materials_to_master(
    *,
    repo_root: Path,
    release_id: str,
    release_commit: str,
    confirmation: str,
    remote: str = "origin",
    branch: str = "master",
) -> MasterPublication:
    """Publish only the immutable material root directly to remote master."""

    required = f"I_APPROVE_DIRECT_OFFICIAL_MATERIAL_PUSH_TO_MASTER:{release_id}"
    if confirmation != required:
        raise MaterialReleaseError("direct_master_push_confirmation_missing")
    _validate_remote_target(remote, branch)
    assert_exact_release_commit(repo_root, release_id, release_commit)
    previous_remote_commit = _remote_branch_head(repo_root, remote, branch)
    _git(repo_root, "fetch", "--no-tags", remote, f"refs/heads/{branch}")
    fetched_commit = _git(repo_root, "rev-parse", "FETCH_HEAD").strip()
    if fetched_commit != previous_remote_commit:
        raise MaterialReleaseError("remote_master_changed_during_fetch")
    with _detached_worktree(repo_root, release_commit, prefix="official-material-source-") as source:
        source_root = source / MATERIAL_ROOT_NAME
        _verify_all_material_releases(source_root)
        uses_lfs = _material_root_uses_lfs(source_root)
        if uses_lfs:
            raise MaterialReleaseError("direct_master_lfs_remote_not_proven")
        release_candidates = list(source_root.glob(f"*/releases/{release_id}"))
        if len(release_candidates) != 1:
            raise MaterialReleaseError("release_id_not_unique")
        with _detached_worktree(repo_root, fetched_commit, prefix="official-material-master-") as target:
            target_root = target / MATERIAL_ROOT_NAME
            _merge_material_root(source_root, target_root)
            staged_roots = [MATERIAL_ROOT_NAME]
            _verify_all_material_releases(target_root)
            verify_release(repo_root=target, release_id=release_id)
            _git(target, "add", "--", *staged_roots)
            changed_paths = tuple(
                sorted(
                    line.strip()
                    for line in _git(target, "diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines()
                    if line.strip()
                )
            )
            if any(
                path != MATERIAL_ROOT_NAME
                and not path.startswith(f"{MATERIAL_ROOT_NAME}/")
                for path in changed_paths
            ):
                raise MaterialReleaseError("direct_master_publish_path_outside_material_root")
            if not changed_paths:
                confirmed_remote_commit = _remote_branch_head(target, remote, branch)
                if confirmed_remote_commit != previous_remote_commit:
                    raise MaterialReleaseError("remote_master_changed_before_noop_readback")
                return MasterPublication(
                    release_id=release_id,
                    remote=remote,
                    branch=branch,
                    previous_remote_commit=previous_remote_commit,
                    published_commit=previous_remote_commit,
                    changed_paths=(),
                    status="already_published",
                )
            _git(target, "commit", "--no-gpg-sign", "-m", f"publish(materials): {release_id}")
            published_commit = _git(target, "rev-parse", "HEAD").strip()
            if _git(target, "merge-base", previous_remote_commit, published_commit).strip() != previous_remote_commit:
                raise MaterialReleaseError("direct_master_publish_not_fast_forward")
            _push_head_to_master(target, remote, branch)
            confirmed_remote_commit = _remote_branch_head(target, remote, branch)
            if confirmed_remote_commit != published_commit:
                raise MaterialReleaseError("direct_master_push_readback_mismatch")
            return MasterPublication(
                release_id=release_id,
                remote=remote,
                branch=branch,
                previous_remote_commit=previous_remote_commit,
                published_commit=published_commit,
                changed_paths=changed_paths,
                status="published",
            )


def _validated_promotion_path(value: str, *, error: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or "." in path.parts
        or ".." in path.parts
        or path.as_posix() != value
    ):
        raise MaterialReleaseError(error)
    return path


def _copy_regular_file(source: Path, target: Path, *, error: str) -> None:
    if source.is_symlink() or not source.is_file():
        raise MaterialReleaseError(error)
    cursor = target.parent
    while not cursor.exists() and cursor != cursor.parent:
        cursor = cursor.parent
    if cursor.is_symlink() or not cursor.is_dir():
        raise MaterialReleaseError(error)
    before = sha256_file(source)
    data = source.read_bytes()
    if sha256_file(source) != before:
        raise MaterialReleaseError(f"{error}_source_changed")
    _write_bytes_atomically(target, data)
    expected_mode = _normalized_git_file_mode(source)
    target.chmod(expected_mode)
    if (
        sha256_file(target) != before
        or target.stat().st_mode & 0o777 != expected_mode
    ):
        raise MaterialReleaseError(f"{error}_copy_mismatch")


def _commit_promotion_tree(
    target: Path,
    *,
    previous_remote_commit: str,
    activation_commit: str,
    release_id: str,
) -> str:
    tree = _git(target, "write-tree").strip()
    command = [
        "git",
        "-C",
        str(target),
        "commit-tree",
        tree,
        "-p",
        previous_remote_commit,
    ]
    if activation_commit != previous_remote_commit:
        command.extend(("-p", activation_commit))
    process = subprocess.run(
        command,
        input=f"promote(official): {release_id}\n",
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        message = process.stderr.strip() or process.stdout.strip() or "unknown"
        raise MaterialReleaseError(f"complete_official_promotion_commit_failed:{message}")
    promoted_commit = process.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", promoted_commit):
        raise MaterialReleaseError("complete_official_promotion_commit_invalid")
    return promoted_commit


def promote_official_version_to_master(
    *,
    repo_root: Path,
    release_id: str,
    release_commit: str,
    activation_commit: str,
    qualification: Mapping[str, object],
    governance_paths: tuple[str, ...],
    confirmation: str,
    remote: str = "origin",
    branch: str = "master",
) -> OfficialPromotionPublication:
    """Promote one qualified release, active pointer, source, and governance to master."""

    required = f"I_APPROVE_COMPLETE_OFFICIAL_PROMOTION_TO_MASTER:{release_id}"
    if confirmation != required:
        raise MaterialReleaseError("complete_official_promotion_confirmation_missing")
    _validate_remote_target(remote, branch)
    assert_exact_release_commit(repo_root, release_id, release_commit)
    assert_qualification_passed(qualification, release_commit)
    _git(repo_root, "cat-file", "-e", f"{activation_commit}^{{commit}}")
    governance = tuple(
        _validated_promotion_path(
            item,
            error="promotion_governance_path_invalid",
        )
        for item in governance_paths
    )
    if len(set(governance)) != len(governance):
        raise MaterialReleaseError("promotion_governance_path_invalid")

    previous_remote_commit = _remote_branch_head(repo_root, remote, branch)
    _git(repo_root, "fetch", "--no-tags", remote, f"refs/heads/{branch}")
    fetched_commit = _git(repo_root, "rev-parse", "FETCH_HEAD").strip()
    if fetched_commit != previous_remote_commit:
        raise MaterialReleaseError("remote_master_changed_during_fetch")

    with _detached_worktree(
        repo_root,
        activation_commit,
        prefix="official-promotion-source-",
    ) as source:
        current_path = source / MATERIAL_ROOT_NAME / "CURRENT.json"
        try:
            current = json.loads(current_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MaterialReleaseError("promotion_activation_current_invalid") from exc
        if (
            not isinstance(current, dict)
            or current.get("release_id") != release_id
            or current.get("release_commit") != release_commit
        ):
            raise MaterialReleaseError("promotion_activation_release_mismatch")
        if current.get("qualification") != dict(qualification):
            raise MaterialReleaseError("promotion_activation_qualification_mismatch")
        try:
            source_identity = assert_official_checkout_matches_active_material(source)
        except OfficialBaselineIdentityError as exc:
            raise MaterialReleaseError(str(exc)) from exc

        source_root = source / MATERIAL_ROOT_NAME
        _verify_all_material_releases(source_root)
        if _material_root_uses_lfs(source_root):
            raise MaterialReleaseError("complete_official_promotion_lfs_remote_not_proven")
        manifest = verify_release(repo_root=source, release_id=release_id)
        top_level_rows = []
        allowed_prefixes = ("examples/portfolio_backtesting/", "tests/", "skills/")
        for row in manifest["files"]:
            logical_path = str(row["logical_path"])
            if logical_path.startswith(allowed_prefixes):
                _validated_promotion_path(
                    logical_path,
                    error="promotion_manifest_logical_path_invalid",
                )
                top_level_rows.append(row)

        with _detached_worktree(
            repo_root,
            fetched_commit,
            prefix="official-promotion-master-",
        ) as target:
            _merge_material_root(source_root, target / MATERIAL_ROOT_NAME)
            _copy_regular_file(
                current_path,
                target / MATERIAL_ROOT_NAME / "CURRENT.json",
                error="promotion_current_copy_invalid",
            )
            allowed_top_level: set[str] = set()
            release_dir = (
                source
                / MATERIAL_ROOT_NAME
                / source_identity.strategy_version
                / "releases"
                / release_id
            )
            for row in top_level_rows:
                logical_path = str(row["logical_path"])
                payload_path = release_dir / str(row["payload_path"])
                _copy_regular_file(
                    payload_path,
                    target / logical_path,
                    error="promotion_manifest_source_invalid",
                )
                allowed_top_level.add(logical_path)
            for relative in governance:
                logical_path = relative.as_posix()
                _copy_regular_file(
                    source / logical_path,
                    target / logical_path,
                    error="promotion_governance_source_invalid",
                )
                allowed_top_level.add(logical_path)

            try:
                target_identity = assert_official_checkout_matches_active_material(target)
            except OfficialBaselineIdentityError as exc:
                raise MaterialReleaseError(str(exc)) from exc
            if target_identity != source_identity:
                raise MaterialReleaseError("promotion_target_identity_mismatch")

            staged_roots = [MATERIAL_ROOT_NAME, *sorted(allowed_top_level)]
            _git(target, "add", "--", *staged_roots)
            changed_paths = tuple(
                sorted(
                    line.strip()
                    for line in _git(
                        target,
                        "diff",
                        "--cached",
                        "--name-only",
                        "--diff-filter=ACMR",
                    ).splitlines()
                    if line.strip()
                )
            )
            if any(
                path not in allowed_top_level
                and path != MATERIAL_ROOT_NAME
                and not path.startswith(f"{MATERIAL_ROOT_NAME}/")
                for path in changed_paths
            ):
                raise MaterialReleaseError("complete_official_promotion_path_outside_allowlist")
            if _remote_branch_head(target, remote, branch) != previous_remote_commit:
                raise MaterialReleaseError("remote_master_changed_before_promotion_push")
            promoted_commit = _commit_promotion_tree(
                target,
                previous_remote_commit=previous_remote_commit,
                activation_commit=activation_commit,
                release_id=release_id,
            )
            if (
                _git(target, "merge-base", previous_remote_commit, promoted_commit).strip()
                != previous_remote_commit
            ):
                raise MaterialReleaseError("complete_official_promotion_not_fast_forward")
            _push_commit_to_master(target, promoted_commit, remote, branch)
            if _remote_branch_head(target, remote, branch) != promoted_commit:
                raise MaterialReleaseError("complete_official_promotion_readback_mismatch")
            return OfficialPromotionPublication(
                release_id=release_id,
                previous_remote_commit=previous_remote_commit,
                promoted_commit=promoted_commit,
                changed_paths=changed_paths,
                source_commit=source_identity.source_commit,
                ruleset_version=source_identity.ruleset_version,
                status="promoted",
            )


def assert_qualification_passed(qualification: Mapping[str, object], release_commit: str) -> None:
    if qualification.get("status") not in {"passed", "qualified"}:
        raise MaterialReleaseError("qualification_not_passed")
    if qualification.get("release_commit") != release_commit:
        raise MaterialReleaseError("qualification_release_commit_mismatch")
    if int(qualification.get("order_api_called_count", -1)) != 0:
        raise MaterialReleaseError("qualification_order_api_count_nonzero")
    if int(qualification.get("cancel_order_api_called_count", -1)) != 0:
        raise MaterialReleaseError("qualification_order_api_count_nonzero")
    evidence_ids = qualification.get("evidence_ids")
    if not isinstance(evidence_ids, list) or not evidence_ids:
        raise MaterialReleaseError("qualification_evidence_missing")


def write_current_atomically(
    repo_root: Path,
    *,
    release_id: str,
    release_commit: str,
    qualification: Mapping[str, object],
    activation_mode: str = "active",
) -> Path:
    manifest_candidates = list(
        (repo_root / MATERIAL_ROOT_NAME).glob(f"*/releases/{release_id}/manifest.json")
    )
    if len(manifest_candidates) != 1:
        raise MaterialReleaseError("release_manifest_not_unique")
    manifest = verify_release_tree(manifest_candidates[0].parent)
    try:
        config_row = unique_inventory_row(manifest, OFFICIAL_CONFIG_LOGICAL_PATH)
        ruleset_version = ruleset_version_from_config(
            manifest_candidates[0].parent / str(config_row["payload_path"])
        )
    except (ActiveMaterialError, OfficialBaselineIdentityError) as exc:
        raise MaterialReleaseError(f"release_ruleset_identity_invalid:{exc}") from exc
    payload = {
        "schema_version": 1,
        "activation_mode": activation_mode,
        "strategy_version": manifest["strategy_version"],
        "release_id": release_id,
        "release_commit": release_commit,
        "material_version": manifest["material_version"],
        "ruleset_version": ruleset_version,
        "source_commit": manifest["source_commit"],
        "manifest_sha256": manifest["manifest_sha256"],
        "tree_fingerprint": manifest["tree_fingerprint"],
        "activated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "qualification": dict(qualification),
    }
    path = repo_root / MATERIAL_ROOT_NAME / "CURRENT.json"
    _write_bytes_atomically(path, canonical_json_bytes(payload) + b"\n")
    return path


def activate_release(
    *,
    repo_root: Path,
    release_id: str,
    release_commit: str,
    qualification: Mapping[str, object],
    confirmation: str,
) -> str:
    required = f"I_UNDERSTAND_THIS_ACTIVATES_OFFICIAL_STRATEGY_MATERIALS:{release_id}"
    if confirmation != required:
        raise MaterialReleaseError("release_activation_confirmation_missing")
    assert_clean_source_tree(repo_root, _git(repo_root, "rev-parse", "HEAD").strip())
    assert_release_commit_contains_exact_release(repo_root, release_id, release_commit)
    assert_qualification_passed(qualification, release_commit)
    current_path = write_current_atomically(
        repo_root,
        release_id=release_id,
        release_commit=release_commit,
        qualification=qualification,
    )
    relative = _repo_relative(repo_root, current_path)
    _git(repo_root, "add", "--", relative)
    assert_exact_staged_paths(repo_root, (relative,))
    _git(repo_root, "commit", "-m", f"activate(materials): {release_id}")
    return _git(repo_root, "rev-parse", "HEAD").strip()


def verify_release(*, repo_root: Path, release_id: str | None = None) -> dict[str, object]:
    if release_id is None:
        current = repo_root / MATERIAL_ROOT_NAME / "CURRENT.json"
        if not current.is_file():
            raise MaterialReleaseError("current_material_release_missing")
        payload = json.loads(current.read_text(encoding="utf-8"))
        release_id = str(payload["release_id"])
    candidates = list((repo_root / MATERIAL_ROOT_NAME).glob(f"*/releases/{release_id}"))
    if len(candidates) != 1:
        raise MaterialReleaseError("release_id_not_unique")
    return verify_release_tree(candidates[0])


def _cli_prepare(args: argparse.Namespace) -> PreparedRelease:
    from build_qmt_roll_stage179_release_manifest import DEFAULT_CRITICAL_FILES
    from qmt_roll_ai_artifact_registry import load_publication_request

    repo = Path(args.repo_root).resolve(strict=True)
    publication = load_publication_request(Path(args.publication_request))
    declarations = [
        MaterialDeclaration(
            source_path=Path(str(row["path"])),
            logical_path=f"ai/stage182/{row['logical_name']}",
            role=MaterialRole(str(row["role"])),
            reproducibility_required=True,
            source_kind="promotion_source",
        )
        for row in publication["ai_artifacts"]
        if bool(row["reproducibility_required"])
    ]
    discovery = discover_materials(
        repo_root=repo,
        entrypoints=(),
        declared_paths=tuple(Path(path) for path in DEFAULT_CRITICAL_FILES),
        config_assets=(),
        ai_artifacts=declarations,
    )
    now_utc = datetime.now(timezone.utc)
    now_cst = now_utc.astimezone().replace(microsecond=0)
    source_commit = _git(repo, "rev-parse", "HEAD").strip()
    stage179_manifest_path = Path(args.stage179_manifest).resolve(strict=True) if args.stage179_manifest else None
    provenance = {
        "generator": publication["generator"],
        "data_cutoff": publication["data_cutoff"],
        "eval_date": publication["eval_date"],
        "training_label_cutoff": publication["training_label_cutoff"],
        "publication_request_sha256": publication["request_sha256"],
        "stage179_manifest_path": str(stage179_manifest_path) if stage179_manifest_path else "not_provided",
        "stage179_manifest_sha256": sha256_file(stage179_manifest_path) if stage179_manifest_path else "not_provided",
    }
    request = ReleaseRequest(
        repo_root=repo,
        official_version=str(publication["official_version"]),
        capital=float(args.capital),
        capital_label=args.capital_label,
        research_line=args.research_line,
        source_commit=source_commit,
        created_at_utc=now_utc.isoformat().replace("+00:00", "Z"),
        created_at_cst=now_cst.isoformat(),
        discovery=discovery,
        provenance=provenance,
        qualification={"status": "candidate", "evidence_ids": []},
    )
    return prepare_release(request)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Freeze and verify official strategy materials")
    parser.add_argument(
        "action",
        choices=(
            "prepare",
            "commit",
            "verify",
            "publish-master",
            "promote-master",
            "activate",
        ),
    )
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--publication-request")
    parser.add_argument("--stage179-manifest")
    parser.add_argument("--release-id")
    parser.add_argument("--release-commit")
    parser.add_argument("--activation-commit")
    parser.add_argument("--qualification-json")
    parser.add_argument("--governance-path", action="append", default=[])
    parser.add_argument("--confirmation")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--target-branch", default="master")
    parser.add_argument("--capital", type=float, default=150000.0)
    parser.add_argument("--capital-label", default="15w")
    parser.add_argument("--research-line", default="futures_official_strategy_material_governance")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo = Path(args.repo_root).resolve(strict=True)
    if args.action == "prepare":
        if not args.publication_request:
            raise MaterialReleaseError("publication_request_required")
        prepared = _cli_prepare(args)
        print(canonical_json_bytes({
            "status": "prepared",
            "release_id": prepared.release_id,
            "material_version": prepared.material_version,
            "release_dir": str(prepared.release_dir),
            "manifest_path": str(prepared.manifest_path),
            "staged_paths": list(prepared.staged_paths),
            "commit_confirmation": f"I_UNDERSTAND_THIS_COMMITS_OFFICIAL_STRATEGY_MATERIALS:{prepared.release_id}",
        }).decode("utf-8"))
        return 0
    if args.action == "commit":
        if not args.release_id:
            raise MaterialReleaseError("release_id_required")
        commit = commit_prepared_release(
            repo_root=repo,
            prepared=_load_prepared_receipt(repo, args.release_id),
            confirmation=args.confirmation or "",
        )
        print(canonical_json_bytes({"status": "committed", "release_id": args.release_id, "release_commit": commit}).decode("utf-8"))
        return 0
    if args.action == "verify":
        manifest = verify_release(repo_root=repo, release_id=args.release_id)
        print(canonical_json_bytes({
            "status": "verified",
            "release_id": manifest["release_id"],
            "manifest_sha256": manifest["manifest_sha256"],
            "tree_fingerprint": manifest["tree_fingerprint"],
            "file_count": len(manifest["files"]),
        }).decode("utf-8"))
        return 0
    if args.action == "publish-master":
        if not args.release_id or not args.release_commit:
            raise MaterialReleaseError("master_publication_arguments_required")
        publication = publish_materials_to_master(
            repo_root=repo,
            release_id=args.release_id,
            release_commit=args.release_commit,
            confirmation=args.confirmation or "",
            remote=args.remote,
            branch=args.target_branch,
        )
        print(canonical_json_bytes({
            "status": publication.status,
            "release_id": publication.release_id,
            "remote": publication.remote,
            "branch": publication.branch,
            "previous_remote_commit": publication.previous_remote_commit,
            "published_commit": publication.published_commit,
            "changed_paths": list(publication.changed_paths),
        }).decode("utf-8"))
        return 0
    if args.action == "promote-master":
        if (
            not args.release_id
            or not args.release_commit
            or not args.activation_commit
            or not args.qualification_json
        ):
            raise MaterialReleaseError("complete_master_promotion_arguments_required")
        qualification = json.loads(
            Path(args.qualification_json).read_text(encoding="utf-8")
        )
        publication = promote_official_version_to_master(
            repo_root=repo,
            release_id=args.release_id,
            release_commit=args.release_commit,
            activation_commit=args.activation_commit,
            qualification=qualification,
            governance_paths=tuple(args.governance_path),
            confirmation=args.confirmation or "",
            remote=args.remote,
            branch=args.target_branch,
        )
        print(
            canonical_json_bytes(
                {
                    "status": publication.status,
                    "release_id": publication.release_id,
                    "previous_remote_commit": publication.previous_remote_commit,
                    "promoted_commit": publication.promoted_commit,
                    "changed_paths": list(publication.changed_paths),
                    "source_commit": publication.source_commit,
                    "ruleset_version": publication.ruleset_version,
                }
            ).decode("utf-8")
        )
        return 0
    if not args.release_id or not args.release_commit or not args.qualification_json:
        raise MaterialReleaseError("activation_arguments_required")
    qualification = json.loads(Path(args.qualification_json).read_text(encoding="utf-8"))
    activation_commit = activate_release(
        repo_root=repo,
        release_id=args.release_id,
        release_commit=args.release_commit,
        qualification=qualification,
        confirmation=args.confirmation or "",
    )
    print(canonical_json_bytes({"status": "activated", "activation_commit": activation_commit}).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
