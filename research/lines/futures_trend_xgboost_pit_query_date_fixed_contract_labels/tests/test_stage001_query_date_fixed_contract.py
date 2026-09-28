from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage001_query_date_fixed_contract as stage001


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


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, dict[str, Path]]:
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
        "fixed_label_accepted,2,0,0,True,0\n"
        "2025-01-02,q.EX,Q2501.EX,2025-01-03,2025-01-07,"
        "fixed_label_accepted,2,0,0,True,0\n",
        encoding="utf-8",
    )
    upstream_summary = upstream_dir / "summary.json"
    upstream_summary.write_text(
        json.dumps(
            {
                "decision": stage001.UPSTREAM_PASS_DECISION,
                "path_rows": 2,
                "path_qids": 1,
                "invalid_path_rows": 0,
                "invalid_leg_rows": 0,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    upstream_manifest = _write_filename_manifest(
        upstream_dir, [paths.name, upstream_summary.name]
    )

    bars = source_dir / "bars.csv"
    bars.write_text(
        "datetime,symbol,exchange,interval,close_price,volume,open_interest\n"
        "2025-01-01,P2505,EX,d,not-read,100,100\n"
        "2025-01-02,P2505,EX,d,not-read,110,120\n"
        "2025-01-03,P2505,EX,d,not-read,130,140\n"
        "2025-01-06,P2505,EX,d,not-read,150,160\n"
        "2025-01-07,P2505,EX,d,not-read,170,180\n"
        "2025-01-01,Q2505,EX,d,not-read,200,210\n"
        "2025-01-02,Q2505,EX,d,not-read,220,230\n"
        "2025-01-03,Q2505,EX,d,not-read,240,250\n"
        "2025-01-06,Q2505,EX,d,not-read,260,270\n"
        "2025-01-07,Q2505,EX,d,not-read,280,290\n",
        encoding="utf-8",
    )
    catalog = source_dir / "catalog.csv"
    catalog.write_text(
        "vt_symbol,product_vt_symbol,expire_date\n"
        "P2505.EX,p.EX,2025-01-31\n"
        "Q2505.EX,q.EX,2025-01-31\n",
        encoding="utf-8",
    )
    source_manifest = _write_path_manifest(
        source_dir, {"bars": bars, "catalog": catalog}
    )
    input_paths = {
        "upstream_manifest": upstream_manifest,
        "upstream_paths": paths,
        "upstream_summary": upstream_summary,
        "source_manifest": source_manifest,
        "source_catalog": catalog,
        "source_bars": bars,
    }
    return line_dir, upstream_dir, source_dir, input_paths


def test_stage001_publishes_fixed_contract_qualification_without_close_reads(
    tmp_path: Path,
) -> None:
    line_dir, upstream_dir, source_dir, input_paths = _fixture(tmp_path)
    expected_sha256 = {name: _sha256(path) for name, path in input_paths.items()}
    expected = stage001.ExpectedCounts(
        path_rows=2,
        path_qids=1,
        holding_period=2,
        history_window=2,
        required_capacity_days=2,
        minimum_candidates_per_qid=2,
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
    assert summary["selected_path_rows"] == 2
    assert summary["fixed_leg_rows"] == 4
    assert summary["execution_event_rows"] == 4
    assert summary["roll_event_rows"] == 0
    assert summary["minimum_candidates_observed"] == 2
    assert summary["close_value_reads"] == 0
    assert summary["opened_bar_columns"] == [
        "datetime",
        "symbol",
        "exchange",
        "interval",
        "volume",
        "open_interest",
    ]
    verification = stage001.verify_final_bundle(output_dir)
    assert verification["verified"] is True
    assert verification["artifact_count"] == 11
    assert verification["input_count"] == 6


def test_stage001_fails_when_query_group_has_fewer_than_frozen_candidates(
    tmp_path: Path,
) -> None:
    line_dir, upstream_dir, source_dir, input_paths = _fixture(tmp_path)
    expected_sha256 = {name: _sha256(path) for name, path in input_paths.items()}
    expected = stage001.ExpectedCounts(
        path_rows=2,
        path_qids=1,
        holding_period=2,
        history_window=2,
        required_capacity_days=2,
        minimum_candidates_per_qid=3,
    )
    output_dir = line_dir / "artifacts" / "stage001_too_narrow"

    summary = stage001.run_stage001(
        line_dir=line_dir,
        output_dir=output_dir,
        upstream_bundle_dir=upstream_dir,
        source_bundle_dir=source_dir,
        input_paths=input_paths,
        expected_sha256=expected_sha256,
        expected=expected,
    )

    assert summary["all_gates_passed"] is False
    assert summary["decision"] == stage001.FAIL_DECISION
    assert summary["gates"]["candidate_breadth_gate"] is False
    assert summary["minimum_candidates_observed"] == 2
    assert stage001.verify_final_bundle(output_dir)["verified"] is True


def test_stage001_fails_when_selected_exit_has_zero_volume(
    tmp_path: Path,
) -> None:
    line_dir, upstream_dir, source_dir, input_paths = _fixture(tmp_path)
    bars = input_paths["source_bars"]
    bars.write_text(
        bars.read_text(encoding="utf-8").replace(
            "2025-01-07,P2505,EX,d,not-read,170,180",
            "2025-01-07,P2505,EX,d,not-read,0,180",
        ),
        encoding="utf-8",
    )
    _write_path_manifest(
        source_dir,
        {"bars": bars, "catalog": input_paths["source_catalog"]},
    )
    expected_sha256 = {name: _sha256(path) for name, path in input_paths.items()}
    expected = stage001.ExpectedCounts(
        path_rows=2,
        path_qids=1,
        holding_period=2,
        history_window=2,
        required_capacity_days=2,
        minimum_candidates_per_qid=2,
    )
    output_dir = line_dir / "artifacts" / "stage001_zero_exit_volume"

    summary = stage001.run_stage001(
        line_dir=line_dir,
        output_dir=output_dir,
        upstream_bundle_dir=upstream_dir,
        source_bundle_dir=source_dir,
        input_paths=input_paths,
        expected_sha256=expected_sha256,
        expected=expected,
    )

    assert summary["all_gates_passed"] is False
    assert summary["decision"] == stage001.FAIL_DECISION
    assert summary["gates"]["price_observation_quality_gate"] is False
    assert summary["gates"]["minimum_one_lot_capacity_gate"] is False
    assert summary["price_invalid_path_rows"] == 1
    assert summary["capacity_invalid_path_rows"] == 1
    assert stage001.verify_final_bundle(output_dir)["verified"] is True
