from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/pit_scorer_audit.py"
SPEC = importlib.util.spec_from_file_location("pit_scorer_audit", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


def _daily(product: str, periods: int, start: str = "2020-01-02") -> pd.DataFrame:
    dates = pd.bdate_range(start, periods=periods)
    return pd.DataFrame(
        {
            "date": dates,
            "product_vt_symbol": product,
            "net_pnl": np.arange(periods, dtype="float64"),
        }
    )


def test_recover_label_boundaries_reproduces_full_60_day_sum() -> None:
    daily = _daily("rb.SHFE", 70)
    expected = float(daily.loc[1:60, "net_pnl"].sum())
    samples = pd.DataFrame(
        {
            "eval_date": [daily.loc[0, "date"]],
            "product_vt_symbol": ["rb.SHFE"],
            "future_net_pnl_60d": [expected],
        }
    )

    result = audit.recover_label_boundaries(daily, samples, horizon=60)

    assert result.loc[0, "future_observation_count"] == 60
    assert result.loc[0, "future_label_start_date"] == daily.loc[1, "date"]
    assert result.loc[0, "future_label_end_date"] == daily.loc[60, "date"]
    assert bool(result.loc[0, "full_horizon_label"])
    assert result.loc[0, "recomputed_future_net_pnl"] == pytest.approx(expected)
    assert result.loc[0, "legacy_future_net_pnl_abs_diff"] == pytest.approx(0.0)


def test_recover_label_boundaries_marks_partial_tail_label() -> None:
    daily = _daily("rb.SHFE", 36)
    expected = float(daily.loc[1:, "net_pnl"].sum())
    samples = pd.DataFrame(
        {
            "eval_date": [daily.loc[0, "date"]],
            "product_vt_symbol": ["rb.SHFE"],
            "future_net_pnl_60d": [expected],
        }
    )

    result = audit.recover_label_boundaries(daily, samples, horizon=60)

    assert result.loc[0, "future_observation_count"] == 35
    assert result.loc[0, "future_label_end_date"] == daily.loc[35, "date"]
    assert not bool(result.loc[0, "full_horizon_label"])


def test_fold_overlap_treats_label_end_equal_test_start_as_leakage() -> None:
    samples = pd.DataFrame(
        {
            "eval_date": pd.to_datetime(["2020-01-31", "2020-02-28", "2020-03-31"]),
            "product_vt_symbol": ["rb.SHFE"] * 3,
            "future_label_end_date": pd.to_datetime(["2020-03-01", "2020-04-01", "2020-05-01"]),
            "target_future_top_half_60d": [0, 1, 0],
        }
    )
    windows = pd.DataFrame(
        {
            "window_id": ["wf_01"],
            "train_start": ["2020-01-01"],
            "train_end": ["2020-03-01"],
            "test_start": ["2020-03-01"],
            "test_end": ["2020-06-01"],
        }
    )

    result = audit.audit_fold_label_overlap(samples, windows)

    assert result.loc[0, "train_rows"] == 2
    assert result.loc[0, "overlap_rows"] == 2
    assert result.loc[0, "strict_clean_train_rows"] == 0
    assert result.loc[0, "overlap_months"] == 2


def test_effective_listing_date_uses_later_official_or_valid_bar_date() -> None:
    official = {"lh.DCE": pd.Timestamp("2021-01-08"), "rb.SHFE": pd.Timestamp("2009-03-27")}
    first_valid = {"lh.DCE": pd.Timestamp("2021-01-07"), "rb.SHFE": pd.Timestamp("2020-01-02")}

    result = audit.build_effective_listing_dates(
        ["lh.DCE", "rb.SHFE"], official, first_valid
    )

    assert result["lh.DCE"] == pd.Timestamp("2021-01-08")
    assert result["rb.SHFE"] == pd.Timestamp("2020-01-02")


def test_listing_filter_runs_before_cross_sectional_target() -> None:
    samples = pd.DataFrame(
        {
            "eval_date": pd.to_datetime(["2020-01-31"] * 4),
            "product_vt_symbol": ["a.DCE", "b.DCE", "c.DCE", "d.DCE"],
            "future_net_pnl_60d": [40.0, 30.0, 20.0, 10.0],
            "target_future_top_half_60d": [1, 1, 0, 0],
        }
    )
    effective = {
        "a.DCE": pd.Timestamp("2020-02-01"),
        "b.DCE": pd.Timestamp("2019-01-01"),
        "c.DCE": pd.Timestamp("2019-01-01"),
        "d.DCE": pd.Timestamp("2019-01-01"),
    }

    eligible, audit_rows = audit.apply_listing_filter_before_target(samples, effective)

    assert eligible["product_vt_symbol"].tolist() == ["b.DCE", "c.DCE", "d.DCE"]
    assert eligible["pit_target_future_top_half_60d"].tolist() == [1, 1, 0]
    assert audit_rows.loc[0, "ineligible_sample_rows"] == 1
    assert audit_rows.loc[0, "eligible_cross_section_count"] == 3


def test_first_valid_ohlc_ignores_zero_and_synthetic_contracts() -> None:
    bars = pd.DataFrame(
        {
            "datetime": pd.to_datetime(
                ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-06"]
            ),
            "symbol": ["rb2005", "rb2005", "rb8888", "rb2005"],
            "exchange": ["SHFE"] * 4,
            "open_price": [0.0, 3500.0, 3600.0, 3510.0],
            "high_price": [3500.0, 3520.0, 3610.0, 3530.0],
            "low_price": [3400.0, 3490.0, 3590.0, 3500.0],
            "close_price": [3450.0, 3510.0, 3605.0, 3520.0],
        }
    )

    result = audit.derive_first_valid_ohlc_dates(bars, ["rb.SHFE"])

    assert result == {"rb.SHFE": pd.Timestamp("2020-01-02")}


def test_universe_provenance_does_not_claim_historical_asof_without_source() -> None:
    result = audit.classify_universe_provenance(
        sample_products={"rb.SHFE", "lh.DCE"},
        current_products={"rb.SHFE", "lh.DCE"},
        observed_position_products={"rb.SHFE", "lh.DCE"},
        mapping_products={"rb.SHFE", "lh.DCE", "a.DCE"},
        historical_approval_source=None,
    )

    assert result["classification"] == "fixed_current_design_universe_only"
    assert not result["historical_asof_universe_reconstructable"]
    assert result["mapping_has_broader_products"]

