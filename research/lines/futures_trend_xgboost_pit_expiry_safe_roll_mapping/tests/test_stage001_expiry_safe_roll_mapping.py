from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage001_expiry_safe_roll_mapping as stage001


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    path = bundle / "artifact_manifest.json"
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def _write_path_manifest(bundle: Path, artifacts: dict[str, Path]) -> Path:
    payload = {
        "artifacts": {
            name: {
                "path": str(path.resolve()),
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for name, path in artifacts.items()
        }
    }
    path = bundle / "artifact_manifest.json"
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def test_default_input_sha256_freezes_all_seven_inputs() -> None:
    assert set(stage001.DEFAULT_EXPECTED_SHA256) == set(
        stage001.DEFAULT_INPUT_PATHS
    )
    observed = {
        name: _sha256(path)
        for name, path in stage001.DEFAULT_INPUT_PATHS.items()
    }
    assert observed == stage001.DEFAULT_EXPECTED_SHA256


def test_stage001_repairs_expiry_boundary_and_publishes_bundle(
    tmp_path: Path,
) -> None:
    v2_dir = tmp_path / "v2"
    source_dir = tmp_path / "source"
    line_dir = tmp_path / "line"
    v2_dir.mkdir()
    source_dir.mkdir()
    line_dir.mkdir()

    paths = v2_dir / "roll_aware_label_plan.csv"
    paths.write_text(
        "query_date,product_vt_symbol,main_contract_vt,entry_date,label_end,"
        "source_partition,leg_count,roll_count,failure_count,path_valid\n"
        "2025-01-02,p.EX,P2501.EX,2025-01-03,2025-01-07,"
        "fixed_exit_bar_missing,2,1,1,False\n"
        "2025-01-02,q.EX,Q2505.EX,2025-01-03,2025-01-07,"
        "fixed_label_accepted,2,0,0,True\n",
        encoding="utf-8",
    )
    legs = v2_dir / "roll_aware_legs.csv"
    legs.write_text(
        "query_date,product_vt_symbol,source_partition,leg_index,previous_date,"
        "return_date,mapping_date,selected_contract_vt,previous_bar_present,"
        "return_bar_present,roll_event,leg_valid,failure_reason\n"
        "2025-01-02,p.EX,fixed_exit_bar_missing,1,2025-01-03,2025-01-06,"
        "2025-01-02,P2501.EX,True,False,False,False,return_bar_missing\n"
        "2025-01-02,p.EX,fixed_exit_bar_missing,2,2025-01-06,2025-01-07,"
        "2025-01-06,P2505.EX,True,True,True,True,\n"
        "2025-01-02,q.EX,fixed_label_accepted,1,2025-01-03,2025-01-06,"
        "2025-01-02,Q2505.EX,True,True,False,True,\n"
        "2025-01-02,q.EX,fixed_label_accepted,2,2025-01-06,2025-01-07,"
        "2025-01-06,Q2505.EX,True,True,False,True,\n",
        encoding="utf-8",
    )
    v2_summary = v2_dir / "summary.json"
    v2_summary.write_text(
        json.dumps(
            {
                "decision": "stage001_v2_roll_aware_label_plan_fail_close_no_labels",
                "path_rows": 2,
                "leg_rows": 4,
                "invalid_path_rows": 1,
                "failure_counts": {"return_bar_missing": 1},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    v2_manifest = _write_filename_manifest(
        v2_dir, [paths.name, legs.name, v2_summary.name]
    )

    catalog = source_dir / "catalog.csv"
    catalog.write_text(
        "vt_symbol,product_vt_symbol,expire_date\n"
        "P2501.EX,p.EX,2025-01-03\n"
        "P2505.EX,p.EX,2025-05-16\n"
        "Q2505.EX,q.EX,2025-05-16\n",
        encoding="utf-8",
    )
    bars = source_dir / "bars.csv"
    bars.write_text(
        "datetime,symbol,exchange,interval,close_price,volume,open_interest\n"
        "2025-01-02,P2501,EX,d,not-read,100,200\n"
        "2025-01-02,P2505,EX,d,not-read,80,150\n"
        "2025-01-02,Q2505,EX,d,not-read,50,100\n"
        "2025-01-03,P2501,EX,d,not-read,90,180\n"
        "2025-01-03,P2505,EX,d,not-read,85,160\n"
        "2025-01-03,Q2505,EX,d,not-read,55,110\n"
        "2025-01-06,P2505,EX,d,not-read,95,170\n"
        "2025-01-06,Q2505,EX,d,not-read,60,120\n"
        "2025-01-07,P2505,EX,d,not-read,100,180\n"
        "2025-01-07,Q2505,EX,d,not-read,65,130\n",
        encoding="utf-8",
    )
    source_manifest = _write_path_manifest(
        source_dir, {"catalog": catalog, "normalised_bars": bars}
    )

    input_paths = {
        "v2_manifest": v2_manifest,
        "v2_paths": paths,
        "v2_legs": legs,
        "v2_summary": v2_summary,
        "source_manifest": source_manifest,
        "source_catalog": catalog,
        "source_bars": bars,
    }
    expected_sha256 = {name: _sha256(path) for name, path in input_paths.items()}
    expected = stage001.ExpectedCounts(
        path_rows=2,
        path_qids=1,
        leg_rows=4,
        holding_period=2,
        v2_invalid_path_rows=1,
        v2_invalid_leg_rows=1,
    )
    canaries = stage001.CanarySet(
        expiry=(
            stage001.ExpiryCanary(
                query_date="2025-01-02",
                product_vt_symbol="p.EX",
                leg_index=1,
                original_contract_vt="P2501.EX",
            ),
        ),
        stable=stage001.StablePathCanary(
            query_date="2025-01-02",
            product_vt_symbol="q.EX",
            first_contract_vt="Q2505.EX",
            label_end="2025-01-07",
            minimum_roll_count=0,
        ),
    )
    output_dir = line_dir / "artifacts" / "stage001"

    summary = stage001.run_stage001(
        line_dir=line_dir,
        output_dir=output_dir,
        v2_bundle_dir=v2_dir,
        source_bundle_dir=source_dir,
        input_paths=input_paths,
        expected_sha256=expected_sha256,
        expected=expected,
        canaries=canaries,
    )

    assert summary["all_gates_passed"] is True
    assert summary["decision"] == stage001.PASS_DECISION
    assert summary["expiry_fallback_leg_count"] == 1
    assert summary["invalid_leg_rows"] == 0
    assert summary["close_value_reads"] == 0
    verification = stage001.verify_final_bundle(output_dir)
    assert verification["verified"] is True
    assert verification["input_count"] == 7
