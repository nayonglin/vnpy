from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pandas as pd
import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools/stage001_legacy_scorer_pit_audit.py"
)
SPEC = importlib.util.spec_from_file_location(
    "stage001_legacy_scorer_pit_audit", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
stage001 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = stage001
SPEC.loader.exec_module(stage001)


def test_load_current_products_uses_python_ast(tmp_path: Path) -> None:
    source = tmp_path / "qmt_universe.py"
    source.write_text(
        "PRODUCT_SPECS = [\n"
        "    ProductSpec('rb', Exchange.SHFE, 10, 1.0, 1.0, 0.1),\n"
        "    ProductSpec('MA', Exchange.CZCE, 10, 1.0, 1.0, 0.1),\n"
        "]\n",
        encoding="utf-8",
    )

    assert stage001.load_current_products_ast(source) == {"rb.SHFE", "MA.CZCE"}


def test_mapping_bar_coverage_only_counts_eligible_nonempty_rows() -> None:
    mapping = pd.DataFrame(
        {
            "date": pd.to_datetime(["2021-01-07", "2021-01-08", "2021-01-11"]),
            "continuous_symbol_vt": ["lh.DCE"] * 3,
            "main_contract_vt": ["", "lh2109.DCE", "lh2109.DCE"],
        }
    )
    valid_bar_keys = {("2021-01-08", "lh2109.DCE")}
    effective = {"lh.DCE": pd.Timestamp("2021-01-08")}

    result = stage001.audit_mapping_bar_coverage(
        mapping,
        valid_bar_keys=valid_bar_keys,
        effective_listing_dates=effective,
        analysis_dates=pd.DatetimeIndex(pd.to_datetime(["2021-01-07", "2021-01-08", "2021-01-11"])),
    )

    assert result["eligible_mapping_rows"] == 2
    assert result["eligible_nonempty_mapping_rows"] == 2
    assert result["same_day_valid_ohlc_rows"] == 1
    assert result["same_day_valid_ohlc_coverage"] == pytest.approx(0.5)


def test_decision_allows_only_conditional_pit_when_history_source_is_missing() -> None:
    summary = {
        "input_identity_stable": True,
        "legacy_future_pnl_reproduction_pass": True,
        "legacy_fold_count": 9,
        "legacy_overlap_fold_count": 9,
        "legacy_partial_horizon_rows": 18,
        "legacy_unlisted_sample_rows": 100,
        "effective_listing_dates_complete": True,
        "minimum_eligible_cross_section": 14,
        "historical_asof_universe_reconstructable": False,
        "mapping_same_day_bar_coverage": 1.0,
    }

    decision = stage001.build_decision(summary)

    assert decision == stage001.CONDITIONAL_PASS_DECISION


def test_decision_fails_when_label_reproduction_drifts() -> None:
    summary = {
        "input_identity_stable": True,
        "legacy_future_pnl_reproduction_pass": False,
        "legacy_fold_count": 9,
        "legacy_overlap_fold_count": 9,
        "legacy_partial_horizon_rows": 18,
        "legacy_unlisted_sample_rows": 100,
        "effective_listing_dates_complete": True,
        "minimum_eligible_cross_section": 14,
        "historical_asof_universe_reconstructable": False,
        "mapping_same_day_bar_coverage": 1.0,
    }

    assert stage001.build_decision(summary) == stage001.FAIL_DECISION


def test_publish_refuses_to_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "artifact"
    output.mkdir()

    with pytest.raises(stage001.Stage001Error, match="output_already_exists"):
        stage001.publish_artifacts(
            output,
            label_audit=pd.DataFrame(),
            fold_audit=pd.DataFrame(),
            listing_audit=pd.DataFrame(),
            universe_audit={},
            summary={},
        )

