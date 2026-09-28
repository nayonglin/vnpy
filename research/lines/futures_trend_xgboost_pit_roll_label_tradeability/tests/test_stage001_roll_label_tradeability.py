from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage001_roll_label_tradeability as stage001


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


def test_default_input_sha256_freezes_all_six_inputs() -> None:
    assert set(stage001.DEFAULT_EXPECTED_SHA256) == set(
        stage001.DEFAULT_INPUT_PATHS
    )
    observed = {
        name: _sha256(path)
        for name, path in stage001.DEFAULT_INPUT_PATHS.items()
    }
    assert observed == stage001.DEFAULT_EXPECTED_SHA256


def test_stage001_publishes_complete_tradeability_audit(tmp_path: Path) -> None:
    upstream_dir = tmp_path / "upstream"
    source_dir = tmp_path / "source"
    line_dir = tmp_path / "line"
    upstream_dir.mkdir()
    source_dir.mkdir()
    line_dir.mkdir()

    paths = upstream_dir / "expiry_safe_paths.csv"
    paths.write_text(
        "query_date,product_vt_symbol,main_contract_vt,entry_date,label_end,"
        "source_partition,leg_count,roll_count,failure_count,path_valid,"
        "expiry_fallback_count\n"
        "2025-01-02,p.EX,P2501.EX,2025-01-03,2025-01-07,"
        "fixed_exit_bar_missing,2,1,0,True,1\n"
        "2025-01-02,q.EX,Q2505.EX,2025-01-03,2025-01-07,"
        "fixed_label_accepted,2,0,0,True,0\n",
        encoding="utf-8",
    )
    legs = upstream_dir / "expiry_safe_legs.csv"
    legs.write_text(
        "query_date,product_vt_symbol,leg_index,previous_date,return_date,"
        "selected_contract_vt,expiry_fallback,roll_event,leg_valid\n"
        "2025-01-02,p.EX,1,2025-01-03,2025-01-06,P2501.EX,False,False,True\n"
        "2025-01-02,p.EX,2,2025-01-06,2025-01-07,P2505.EX,True,True,True\n"
        "2025-01-02,q.EX,1,2025-01-03,2025-01-06,Q2505.EX,False,False,True\n"
        "2025-01-02,q.EX,2,2025-01-06,2025-01-07,Q2505.EX,False,False,True\n",
        encoding="utf-8",
    )
    upstream_summary = upstream_dir / "summary.json"
    upstream_summary.write_text(
        json.dumps(
            {
                "decision": stage001.UPSTREAM_PASS_DECISION,
                "path_rows": 2,
                "leg_rows": 4,
                "invalid_path_rows": 0,
                "invalid_leg_rows": 0,
                "expiry_fallback_leg_count": 1,
                "roll_event_count": 1,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    upstream_manifest = _write_filename_manifest(
        upstream_dir, [paths.name, legs.name, upstream_summary.name]
    )

    bars = source_dir / "bars.csv"
    bars.write_text(
        "datetime,symbol,exchange,interval,close_price,volume,open_interest\n"
        "2025-01-03,P2501,EX,d,not-read,100,100\n"
        "2025-01-06,P2501,EX,d,not-read,120,130\n"
        "2025-01-06,P2505,EX,d,not-read,140,150\n"
        "2025-01-07,P2505,EX,d,not-read,160,170\n"
        "2025-01-03,Q2505,EX,d,not-read,180,190\n"
        "2025-01-06,Q2505,EX,d,not-read,200,210\n"
        "2025-01-07,Q2505,EX,d,not-read,220,230\n",
        encoding="utf-8",
    )
    source_manifest = _write_path_manifest(source_dir, {"bars": bars})
    input_paths = {
        "upstream_manifest": upstream_manifest,
        "upstream_paths": paths,
        "upstream_legs": legs,
        "upstream_summary": upstream_summary,
        "source_manifest": source_manifest,
        "source_bars": bars,
    }
    expected_sha256 = {name: _sha256(path) for name, path in input_paths.items()}
    expected = stage001.ExpectedCounts(
        path_rows=2,
        path_qids=1,
        leg_rows=4,
        holding_period=2,
        upstream_invalid_path_rows=0,
        upstream_invalid_leg_rows=0,
        upstream_fallback_leg_rows=1,
    )
    output_dir = line_dir / "artifacts" / "stage001"

    summary = stage001.run_stage001(
        line_dir=line_dir,
        output_dir=output_dir,
        upstream_bundle_dir=upstream_dir,
        source_bundle_dir=source_dir,
        input_paths=input_paths,
        expected_sha256=expected_sha256,
        expected=expected,
    )

    assert summary["all_gates_passed"] is True
    assert summary["decision"] == stage001.PASS_DECISION
    assert summary["execution_event_rows"] == 6
    assert summary["price_invalid_leg_rows"] == 0
    assert summary["capacity_invalid_event_rows"] == 0
    assert summary["close_value_reads"] == 0
    verification = stage001.verify_final_bundle(output_dir)
    assert verification["verified"] is True
    assert verification["input_count"] == 6
