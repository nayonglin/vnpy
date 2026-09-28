from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage001_v2_roll_aware_label_plan as stage001_v2


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_path_manifest(bundle: Path, artifacts: dict[str, Path]) -> None:
    payload = {
        "artifacts": {
            logical_name: {
                "path": str(path.resolve()),
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for logical_name, path in artifacts.items()
        },
        "source_files": [],
    }
    (bundle / "artifact_manifest.json").write_text(
        json.dumps(payload, sort_keys=True), encoding="utf-8"
    )


def _write_filename_manifest(bundle: Path, filenames: list[str]) -> Path:
    payload = {
        "artifacts": {
            name: {
                "size": (bundle / name).stat().st_size,
                "sha256": _sha256(bundle / name),
            }
            for name in sorted(filenames)
        },
        "input_identities": {},
    }
    manifest = bundle / "artifact_manifest.json"
    manifest.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return manifest


def test_verify_path_manifest_accepts_logical_keys_and_entry_paths(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "source"
    bundle.mkdir()
    mapping = bundle / "pit_main_contract_mapping.csv.gz"
    bars = bundle / "normalised_daily_bars.csv.gz"
    mapping.write_bytes(b"mapping")
    bars.write_bytes(b"bars")
    _write_path_manifest(bundle, {"mapping": mapping, "normalised_bars": bars})

    result = stage001_v2.verify_path_manifest_bundle(bundle)

    assert result == {
        "verified": True,
        "errors": [],
        "artifact_count": 2,
        "manifest_mode": "logical_key_with_path",
    }


def test_verify_path_manifest_rejects_path_escape_and_missing_file(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "source"
    bundle.mkdir()
    outside = tmp_path / "outside.csv"
    outside.write_bytes(b"outside")
    missing = bundle / "missing.csv"
    manifest = {
        "artifacts": {
            "outside": {
                "path": str(outside),
                "size": outside.stat().st_size,
                "sha256": _sha256(outside),
            },
            "missing": {
                "path": str(missing),
                "size": 1,
                "sha256": "0" * 64,
            },
        }
    }
    (bundle / "artifact_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    result = stage001_v2.verify_path_manifest_bundle(bundle)

    assert result["verified"] is False
    assert result["errors"] == [
        "artifact_missing:missing",
        "artifact_path_outside_bundle:outside",
    ]


def test_verify_path_manifest_rejects_size_and_sha_drift(tmp_path: Path) -> None:
    bundle = tmp_path / "source"
    bundle.mkdir()
    artifact = bundle / "mapping.csv"
    artifact.write_bytes(b"current")
    manifest = {
        "artifacts": {
            "mapping": {
                "path": str(artifact),
                "size": 1,
                "sha256": "0" * 64,
            }
        }
    }
    (bundle / "artifact_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    result = stage001_v2.verify_path_manifest_bundle(bundle)

    assert result["verified"] is False
    assert result["errors"] == [
        "artifact_size_mismatch:mapping",
        "artifact_sha256_mismatch:mapping",
    ]


def test_run_stage001_v2_publishes_with_path_manifest_source(tmp_path: Path) -> None:
    v1_dir = tmp_path / "v1"
    source_dir = tmp_path / "source"
    line_dir = tmp_path / "line"
    v1_dir.mkdir()
    source_dir.mkdir()
    line_dir.mkdir()

    model_features = v1_dir / "model_feature_panel.csv"
    model_features.write_text(
        "query_date,product_vt_symbol,main_contract_vt\n"
        "2024-01-01,p.EX,P01.EX\n"
        "2024-01-01,q.EX,Q01.EX\n"
        "2024-01-02,a.EX,A01.EX\n",
        encoding="utf-8",
    )
    accepted = v1_dir / "label_plan.csv"
    accepted.write_text(
        "query_date,product_vt_symbol,main_contract_vt,entry_date,label_end\n"
        "2024-01-01,q.EX,Q01.EX,2024-01-02,2024-01-04\n",
        encoding="utf-8",
    )
    rejected = v1_dir / "rejected_label_plan.csv"
    rejected.write_text(
        "query_date,product_vt_symbol,main_contract_vt,entry_date,label_end,rejection_reason\n"
        "2024-01-01,p.EX,P01.EX,2024-01-02,2024-01-04,exit_bar_missing\n"
        "2024-01-02,a.EX,A01.EX,2024-01-03,,exit_date_outside_cutoff\n",
        encoding="utf-8",
    )
    v1_manifest = _write_filename_manifest(
        v1_dir, [model_features.name, accepted.name, rejected.name]
    )

    mapping = source_dir / "mapping.csv"
    mapping.write_text(
        "date,continuous_symbol_vt,main_contract_vt,mapping_resolution\n"
        "2024-01-01,p.EX,P01.EX,resolved\n"
        "2024-01-02,p.EX,P02.EX,resolved\n"
        "2024-01-03,p.EX,P03.EX,resolved\n"
        "2024-01-04,p.EX,P03.EX,resolved\n"
        "2024-01-01,q.EX,Q01.EX,resolved\n"
        "2024-01-02,q.EX,Q01.EX,resolved\n"
        "2024-01-03,q.EX,Q01.EX,resolved\n"
        "2024-01-04,q.EX,Q01.EX,resolved\n",
        encoding="utf-8",
    )
    bars = source_dir / "bars.csv"
    bars.write_text(
        "datetime,symbol,exchange,interval,close_price\n"
        "2024-01-02,P01,EX,d,not-read\n"
        "2024-01-03,P01,EX,d,not-read\n"
        "2024-01-03,P03,EX,d,not-read\n"
        "2024-01-04,P03,EX,d,not-read\n"
        "2024-01-02,Q01,EX,d,not-read\n"
        "2024-01-03,Q01,EX,d,not-read\n"
        "2024-01-04,Q01,EX,d,not-read\n",
        encoding="utf-8",
    )
    _write_path_manifest(
        source_dir, {"mapping": mapping, "normalised_bars": bars}
    )
    source_manifest = source_dir / "artifact_manifest.json"

    input_paths = {
        "v1_manifest": v1_manifest,
        "model_features": model_features,
        "accepted_label_plan": accepted,
        "rejected_label_plan": rejected,
        "source_manifest": source_manifest,
        "source_mapping": mapping,
        "source_bars": bars,
    }
    expected_sha256 = {name: _sha256(path) for name, path in input_paths.items()}
    expected = stage001_v2.ExpectedCounts(
        base_rows=3,
        base_qids=2,
        fixed_label_accepted_rows=1,
        fixed_exit_bar_missing_rows=1,
        exit_date_outside_cutoff_rows=1,
        candidate_rows=2,
        candidate_qids=1,
        cutoff_rows=1,
        total_legs=4,
        holding_period=2,
    )
    canary = stage001_v2.Canary(
        query_date="2024-01-01",
        product_vt_symbol="p.EX",
        first_contract_vt="P01.EX",
        label_end="2024-01-04",
    )
    output_dir = line_dir / "artifacts" / "stage001_v2"

    summary = stage001_v2.run_stage001_v2(
        line_dir=line_dir,
        output_dir=output_dir,
        v1_bundle_dir=v1_dir,
        source_bundle_dir=source_dir,
        input_paths=input_paths,
        expected_sha256=expected_sha256,
        expected=expected,
        canary=canary,
    )

    assert summary["all_gates_passed"] is True
    assert summary["decision"] == stage001_v2.PASS_DECISION
    assert summary["source_verification"]["manifest_mode"] == (
        "logical_key_with_path"
    )
    verification = stage001_v2.verify_final_bundle(output_dir)
    assert verification["verified"] is True
    assert verification["input_count"] == 7
