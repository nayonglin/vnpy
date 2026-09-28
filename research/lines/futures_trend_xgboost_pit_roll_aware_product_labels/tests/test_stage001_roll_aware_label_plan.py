from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage001_roll_aware_label_plan as stage001


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_bundle(directory: Path, filenames: list[str]) -> Path:
    artifacts = {
        name: {"sha256": _sha256(directory / name), "size": (directory / name).stat().st_size}
        for name in sorted(filenames)
    }
    manifest = directory / "artifact_manifest.json"
    manifest.write_text(
        json.dumps({"artifacts": artifacts, "input_identities": {}}, sort_keys=True),
        encoding="utf-8",
    )
    return manifest


def test_load_bar_presence_ignores_every_price_and_liquidity_value(tmp_path: Path) -> None:
    path = tmp_path / "bars.csv"
    path.write_text(
        "datetime,symbol,exchange,interval,close_price,volume,open_interest\n"
        "2024-01-02,P01,EX,d,not-a-price,not-volume,not-oi\n"
        "2024-01-02,P01,EX,1h,also-invalid,also-invalid,also-invalid\n",
        encoding="utf-8",
    )

    result = stage001.load_bar_presence(path)

    assert result.columns.tolist() == ["date", "contract_vt_symbol"]
    assert result.to_dict("records") == [
        {
            "date": pd.Timestamp("2024-01-02"),
            "contract_vt_symbol": "P01.EX",
        }
    ]


def _passing_inputs() -> tuple[
    dict[str, int], pd.DataFrame, pd.DataFrame, pd.DataFrame
]:
    partition = {
        "base_rows": 3,
        "base_qids": 2,
        "fixed_label_accepted_rows": 1,
        "fixed_exit_bar_missing_rows": 1,
        "exit_date_outside_cutoff_rows": 1,
        "candidate_rows": 2,
        "cutoff_rows": 1,
    }
    paths = pd.DataFrame(
        {
            "query_date": ["2024-01-01", "2024-01-01"],
            "product_vt_symbol": ["p.EX", "q.EX"],
            "main_contract_vt": ["P01.EX", "Q01.EX"],
            "entry_date": ["2024-01-02", "2024-01-02"],
            "label_end": ["2024-01-04", "2024-01-04"],
            "source_partition": [
                "fixed_exit_bar_missing",
                "fixed_label_accepted",
            ],
            "leg_count": [2, 2],
            "roll_count": [1, 0],
            "failure_count": [0, 0],
            "path_valid": [True, True],
        }
    )
    legs = pd.DataFrame(
        {
            "query_date": ["2024-01-01"] * 4,
            "product_vt_symbol": ["p.EX", "p.EX", "q.EX", "q.EX"],
            "leg_index": [1, 2, 1, 2],
            "previous_date": [
                "2024-01-02",
                "2024-01-03",
                "2024-01-02",
                "2024-01-03",
            ],
            "return_date": [
                "2024-01-03",
                "2024-01-04",
                "2024-01-03",
                "2024-01-04",
            ],
            "mapping_date": [
                "2024-01-01",
                "2024-01-03",
                "2024-01-01",
                "2024-01-03",
            ],
            "selected_contract_vt": ["P01.EX", "P02.EX", "Q01.EX", "Q01.EX"],
            "previous_bar_present": [True] * 4,
            "return_bar_present": [True] * 4,
            "roll_event": [False, True, False, False],
            "leg_valid": [True] * 4,
            "failure_reason": [""] * 4,
        }
    )
    failures = legs.iloc[:0].copy()
    return partition, paths, legs, failures


def test_assess_stage001_requires_all_frozen_identity_only_gates() -> None:
    partition, paths, legs, failures = _passing_inputs()
    expected = stage001.ExpectedCounts(
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
    canary = stage001.Canary(
        query_date="2024-01-01",
        product_vt_symbol="p.EX",
        first_contract_vt="P01.EX",
        label_end="2024-01-04",
    )

    result = stage001.assess_stage001(
        partition,
        paths,
        legs,
        failures,
        v1_verified=True,
        source_verified=True,
        input_identity_stable=True,
        expected=expected,
        canary=canary,
    )

    assert result["all_gates_passed"] is True
    assert result["decision"] == stage001.PASS_DECISION
    assert all(result["gates"].values())
    assert result["close_value_reads"] == 0
    assert result["future_return_calculations"] == 0
    assert result["model_fit_count"] == 0
    assert result["strategy_backtest_runs"] == 0


def test_assess_stage001_fails_when_canary_does_not_roll_or_path_fails() -> None:
    partition, paths, legs, failures = _passing_inputs()
    expected = stage001.ExpectedCounts(
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
    canary = stage001.Canary(
        query_date="2024-01-01",
        product_vt_symbol="p.EX",
        first_contract_vt="P01.EX",
        label_end="2024-01-04",
    )
    paths.loc[paths["product_vt_symbol"].eq("p.EX"), "roll_count"] = 0
    legs.loc[legs.index[1], ["leg_valid", "failure_reason"]] = [
        False,
        "return_bar_missing",
    ]
    failures = legs.loc[~legs["leg_valid"]].copy()

    result = stage001.assess_stage001(
        partition,
        paths,
        legs,
        failures,
        v1_verified=True,
        source_verified=True,
        input_identity_stable=True,
        expected=expected,
        canary=canary,
    )

    assert result["all_gates_passed"] is False
    assert result["decision"] == stage001.FAIL_DECISION
    assert result["gates"]["complete_path_gate"] is False
    assert result["gates"]["canary_gate"] is False


def test_run_stage001_publishes_a_manifest_backed_identity_only_bundle(
    tmp_path: Path,
) -> None:
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
    v1_manifest = _write_bundle(
        v1_dir,
        [model_features.name, accepted.name, rejected.name],
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
    source_manifest = _write_bundle(source_dir, [mapping.name, bars.name])

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
    expected = stage001.ExpectedCounts(
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
    canary = stage001.Canary(
        query_date="2024-01-01",
        product_vt_symbol="p.EX",
        first_contract_vt="P01.EX",
        label_end="2024-01-04",
    )
    output_dir = line_dir / "artifacts" / "stage001"

    summary = stage001.run_stage001(
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
    assert output_dir.is_dir()
    verification = stage001.verify_final_bundle(output_dir)
    assert verification["verified"] is True
    assert verification["input_count"] == 7
    published_summary = json.loads(
        (output_dir / "summary.json").read_text(encoding="utf-8")
    )
    assert published_summary["close_value_reads"] == 0
    assert published_summary["decision"] == stage001.PASS_DECISION
