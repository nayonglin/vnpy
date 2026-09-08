from __future__ import annotations

from pathlib import Path

import pytest

from qmt_roll_strategy_material_manifest import (
    MaterialFile,
    MaterialManifestError,
    MaterialRole,
    StorageKind,
    build_material_manifest,
    load_and_validate_material_manifest,
    material_manifest_digest,
    serialize_material_manifest,
    sha256_file,
)


def _manifest(root: Path) -> dict[str, object]:
    target = root / "payload/ai/pool.csv"
    target.parent.mkdir(parents=True)
    target.write_text("rank,symbol\n1,fu.SHFE\n", encoding="utf-8")
    return build_material_manifest(
        release_id="m0001_20260819T153000+0800_d6080c914ae9",
        strategy_version="official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
        material_version="m0001",
        source_commit="d6080c914ae9884eaa984618f37f18022ef5e058",
        created_at_utc="2026-08-19T07:30:00Z",
        created_at_cst="2026-08-19T15:30:00+08:00",
        research_line="futures_official_strategy_material_governance",
        capital=150000.0,
        capital_label="15w",
        files=(
            MaterialFile(
                logical_path="ai/pool.csv",
                payload_path="payload/ai/pool.csv",
                role=MaterialRole.DECISION_ASSET,
                storage=StorageKind.GIT,
                size_bytes=target.stat().st_size,
                sha256=sha256_file(target),
                source_path="promotion_source:pool.csv",
            ),
        ),
        provenance={"eval_date": "2026-07-31"},
        qualification={"status": "candidate", "evidence_ids": []},
        parent_material_version="",
    )


def test_manifest_digest_is_stable_and_excludes_its_own_digest(tmp_path: Path) -> None:
    payload = _manifest(tmp_path)
    assert payload["manifest_sha256"] == material_manifest_digest(payload)
    assert serialize_material_manifest(payload) == serialize_material_manifest(dict(payload))


def test_validator_rejects_payload_byte_drift(tmp_path: Path) -> None:
    payload = _manifest(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(serialize_material_manifest(payload))
    (tmp_path / "payload/ai/pool.csv").write_text("rank,symbol\n1,rb.SHFE\n", encoding="utf-8")
    with pytest.raises(MaterialManifestError, match="material_file_sha256_mismatch"):
        load_and_validate_material_manifest(manifest_path, release_root=tmp_path)


def test_validator_rejects_unexpanded_lfs_pointer(tmp_path: Path) -> None:
    payload = _manifest(tmp_path)
    target = tmp_path / "payload/ai/pool.csv"
    pointer = b"version https://git-lfs.github.com/spec/v1\n" + b"oid sha256:" + b"a" * 64 + b"\nsize 1\n"
    target.write_bytes(pointer)
    row = payload["files"][0]
    row["size_bytes"] = len(pointer)
    row["sha256"] = sha256_file(target)
    rebuilt = build_material_manifest(
        release_id=str(payload["release_id"]),
        strategy_version=str(payload["strategy_version"]),
        material_version=str(payload["material_version"]),
        source_commit=str(payload["source_commit"]),
        created_at_utc=str(payload["created_at_utc"]),
        created_at_cst=str(payload["created_at_cst"]),
        research_line=str(payload["research_line"]),
        capital=float(payload["capital"]),
        capital_label=str(payload["capital_label"]),
        files=(row,),
        provenance=payload["provenance"],
        qualification=payload["qualification"],
        parent_material_version="",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(serialize_material_manifest(rebuilt))
    with pytest.raises(MaterialManifestError, match="git_lfs_pointer_not_expanded"):
        load_and_validate_material_manifest(manifest_path, release_root=tmp_path)
