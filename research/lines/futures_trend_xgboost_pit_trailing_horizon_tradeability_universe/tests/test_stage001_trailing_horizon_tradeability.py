from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage001_trailing_horizon_tradeability as stage001


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


def _fixture(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path, dict[str, Path]]:
    upstream_dir = tmp_path / "upstream"
    source_dir = tmp_path / "source"
    dynamic_dir = tmp_path / "dynamic"
    line_dir = tmp_path / "line"
    for directory in (upstream_dir, source_dir, dynamic_dir, line_dir):
        directory.mkdir()

    paths = upstream_dir / "expiry_safe_paths.csv"
    paths.write_text(
        "query_date,product_vt_symbol,main_contract_vt,entry_date,label_end,"
        "source_partition,leg_count,roll_count,failure_count,path_valid,"
        "expiry_fallback_count\n"
        "2025-01-08,p.EX,P2501.EX,2025-01-09,2025-01-13,"
        "fixed_label_accepted,2,0,0,True,0\n"
        "2025-01-08,q.EX,Q2501.EX,2025-01-09,2025-01-13,"
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

    dynamic_summary = dynamic_dir / "summary.json"
    dynamic_summary.write_text(
        json.dumps(
            {
                "decision": stage001.PRIOR_DYNAMIC_FAIL_DECISION,
                "close_value_reads": 0,
                "model_fit_count": 0,
                "strategy_backtest_runs": 0,
                "implementation_identities": {
                    "core_sha256": stage001.PRIOR_DYNAMIC_CORE_SHA256
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    dynamic_manifest = _write_filename_manifest(
        dynamic_dir, [dynamic_summary.name]
    )

    dates = [
        "2024-12-30",
        "2024-12-31",
        "2025-01-02",
        "2025-01-03",
        "2025-01-06",
        "2025-01-08",
        "2025-01-09",
        "2025-01-10",
        "2025-01-13",
        "2025-01-14",
    ]
    bars = source_dir / "bars.csv"
    rows = [
        "datetime,symbol,exchange,interval,close_price,volume,open_interest"
    ]
    for index, date in enumerate(dates):
        rows.append(f"{date},P2505,EX,d,not-read,{500 + index},700")
        rows.append(f"{date},Q2505,EX,d,not-read,{600 + index},800")
    bars.write_text("\n".join(rows) + "\n", encoding="utf-8")
    catalog = source_dir / "catalog.csv"
    catalog.write_text(
        "vt_symbol,product_vt_symbol,expire_date\n"
        "P2505.EX,p.EX,2025-05-30\n"
        "Q2505.EX,q.EX,2025-05-30\n",
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
        "prior_dynamic_manifest": dynamic_manifest,
        "prior_dynamic_summary": dynamic_summary,
    }
    return line_dir, upstream_dir, source_dir, dynamic_dir, input_paths


def _expected(minimum_candidates: int = 2) -> stage001.ExpectedCounts:
    return stage001.ExpectedCounts(
        path_rows=2,
        path_qids=1,
        holding_period=2,
        trailing_lookback=2,
        minimum_candidates_per_qid=minimum_candidates,
    )


def _run(
    tmp_path: Path,
    *,
    output_name: str,
    expected: stage001.ExpectedCounts | None = None,
) -> tuple[dict[str, object], Path]:
    line_dir, upstream_dir, source_dir, dynamic_dir, input_paths = _fixture(
        tmp_path
    )
    expected_sha256 = {name: _sha256(path) for name, path in input_paths.items()}
    output_dir = line_dir / "artifacts" / output_name
    summary = stage001.run_stage001(
        line_dir=line_dir,
        output_dir=output_dir,
        upstream_bundle_dir=upstream_dir,
        source_bundle_dir=source_dir,
        prior_dynamic_bundle_dir=dynamic_dir,
        input_paths=input_paths,
        expected_sha256=expected_sha256,
        expected=expected or _expected(),
    )
    return summary, output_dir


def test_stage001_passes_without_reading_close_and_verifies_bundle(
    tmp_path: Path,
) -> None:
    summary, output_dir = _run(tmp_path, output_name="stage001_pass")

    assert summary["all_gates_passed"] is True
    assert summary["decision"] == stage001.PASS_DECISION
    assert summary["historical_eligible_path_rows"] == 2
    assert summary["selected_path_rows"] == 2
    assert summary["future_qualified_path_rows"] == 2
    assert summary["historical_future_observation_violation_rows"] == 0
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
    assert verification["artifact_count"] == 15
    assert verification["input_count"] == 8


def test_historical_failure_excludes_candidate_before_future_audit(
    tmp_path: Path,
) -> None:
    line_dir, upstream_dir, source_dir, dynamic_dir, input_paths = _fixture(
        tmp_path
    )
    bars = input_paths["source_bars"]
    bars.write_text(
        bars.read_text(encoding="utf-8").replace(
            "2025-01-03,Q2505,EX,d,not-read,603,800",
            "2025-01-03,Q2505,EX,d,not-read,0,800",
        ),
        encoding="utf-8",
    )
    _write_path_manifest(
        source_dir,
        {"bars": bars, "catalog": input_paths["source_catalog"]},
    )
    expected_sha256 = {name: _sha256(path) for name, path in input_paths.items()}
    output_dir = line_dir / "artifacts" / "stage001_history_filter"

    summary = stage001.run_stage001(
        line_dir=line_dir,
        output_dir=output_dir,
        upstream_bundle_dir=upstream_dir,
        source_bundle_dir=source_dir,
        prior_dynamic_bundle_dir=dynamic_dir,
        input_paths=input_paths,
        expected_sha256=expected_sha256,
        expected=_expected(minimum_candidates=1),
    )

    assert summary["all_gates_passed"] is True
    assert summary["historical_eligible_path_rows"] == 1
    assert summary["selected_path_rows"] == 1
    assert summary["future_qualified_path_rows"] == 1
    assert summary["historical_rejection_counts"]
    assert stage001.verify_final_bundle(output_dir)["verified"] is True


def test_future_failure_does_not_rewrite_selected_universe(
    tmp_path: Path,
) -> None:
    line_dir, upstream_dir, source_dir, dynamic_dir, input_paths = _fixture(
        tmp_path
    )
    bars = input_paths["source_bars"]
    bars.write_text(
        bars.read_text(encoding="utf-8").replace(
            "2025-01-13,P2505,EX,d,not-read,508,700",
            "2025-01-13,P2505,EX,d,not-read,0,700",
        ),
        encoding="utf-8",
    )
    _write_path_manifest(
        source_dir,
        {"bars": bars, "catalog": input_paths["source_catalog"]},
    )
    expected_sha256 = {name: _sha256(path) for name, path in input_paths.items()}
    output_dir = line_dir / "artifacts" / "stage001_future_fail"

    summary = stage001.run_stage001(
        line_dir=line_dir,
        output_dir=output_dir,
        upstream_bundle_dir=upstream_dir,
        source_bundle_dir=source_dir,
        prior_dynamic_bundle_dir=dynamic_dir,
        input_paths=input_paths,
        expected_sha256=expected_sha256,
        expected=_expected(),
    )

    assert summary["all_gates_passed"] is False
    assert summary["selected_path_rows"] == 2
    assert summary["future_qualified_path_rows"] == 1
    assert summary["gates"]["future_price_observation_quality_gate"] is False
    assert summary["gates"]["future_minimum_one_lot_capacity_gate"] is False
    assert stage001.verify_final_bundle(output_dir)["verified"] is True


def test_stage001_fails_when_causal_universe_is_too_narrow(
    tmp_path: Path,
) -> None:
    summary, output_dir = _run(
        tmp_path,
        output_name="stage001_narrow",
        expected=_expected(minimum_candidates=3),
    )

    assert summary["all_gates_passed"] is False
    assert summary["gates"]["candidate_breadth_gate"] is False
    assert summary["minimum_candidates_observed"] == 2
    assert stage001.verify_final_bundle(output_dir)["verified"] is True
