from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import causal_formal_features as features


def _daily_frame(*, periods: int = 190, products: tuple[str, ...] = ("a.DCE", "b.DCE")) -> pd.DataFrame:
    dates = pd.bdate_range("2023-01-02", periods=periods)
    rows: list[dict[str, object]] = []
    for product_index, product in enumerate(products, start=1):
        for date_index, date in enumerate(dates, start=1):
            scale = float(product_index * date_index)
            rows.append(
                {
                    "date": date,
                    "product_vt_symbol": product,
                    "net_pnl": scale,
                    "slippage": scale * 0.01,
                    "turnover": scale * 100.0,
                    "trade_count": float(date_index % 4),
                    "abs_pos_change": float(date_index % 3),
                    "active_contract_count": 1.0,
                    "candidate_count": float(date_index % 5),
                    "opened_count": float(date_index % 2),
                    "selected_volume_sum": scale * 0.2,
                    "selected_volume_ungated_sum": scale * 0.25,
                    "corr_gate_enabled_count": float(date_index % 2),
                    "volume_tilt_applied_count": float(date_index % 3 == 0),
                    "avg_corr_gate_weight": 0.8,
                    "avg_same_direction_active_count": 2.0,
                    "avg_same_direction_max_corr": 0.4,
                    "avg_pairwise_score": scale * 0.001,
                    "best_pairwise_rank": float((date_index % 10) + 1),
                    "avg_volume_tilt_multiplier": 1.0,
                    "avg_volume_tilt_score_gap": 0.1,
                    "avg_volume_tilt_top_gap": 0.2,
                    "avg_active_positions_before": 2.0,
                    "breakout_rate": 0.3,
                    "bullish_alignment_rate": 0.4,
                    "bearish_alignment_rate": 0.2,
                    "avg_rsi": 50.0,
                    "avg_loss_streak": 1.0,
                }
            )
    return pd.DataFrame(rows)


def test_causal_features_ignore_future_outlier() -> None:
    daily = _daily_frame()
    cutoff = pd.Timestamp("2023-06-30")
    baseline = features.build_causal_rolling_features(daily)

    changed_daily = daily.copy()
    changed_daily.loc[changed_daily["date"] > cutoff, "net_pnl"] = 1_000_000_000.0
    changed = features.build_causal_rolling_features(changed_daily)

    columns = ["date", "product_vt_symbol", *features.formal_feature_columns()]
    assert_frame_equal(
        baseline.loc[baseline["date"] <= cutoff, columns].reset_index(drop=True),
        changed.loc[changed["date"] <= cutoff, columns].reset_index(drop=True),
        check_exact=True,
    )


def test_monthly_panel_has_exact_formal_features_and_no_forbidden_columns() -> None:
    featured = features.build_causal_rolling_features(_daily_frame())
    panel, feature_columns = features.build_label_free_monthly_samples(featured)

    assert len(feature_columns) == 108
    assert feature_columns == features.formal_feature_columns()
    assert np.isfinite(panel[feature_columns].to_numpy(dtype="float64")).all()
    assert not any(
        column.startswith(features.FORBIDDEN_COLUMN_PREFIXES)
        for column in panel.columns
    )
    assert panel.groupby("eval_date")["product_vt_symbol"].nunique().eq(2).all()


def test_rolling_sum_uses_only_trailing_window() -> None:
    daily = _daily_frame(periods=25, products=("a.DCE",))
    featured = features.build_causal_rolling_features(daily)

    last = featured.sort_values("date").iloc[-1]
    expected = daily.sort_values("date")["net_pnl"].tail(20).sum()
    assert last["net_pnl_sum_20d"] == pytest.approx(expected)


def test_label_end_is_the_nth_future_trading_date() -> None:
    dates = pd.bdate_range("2024-01-02", periods=10)
    calendar = features.build_label_end_calendar(
        dates,
        [dates[0], dates[5], dates[8]],
        horizon=3,
    )

    assert calendar.loc[0, "label_end"] == dates[3]
    assert calendar.loc[1, "label_end"] == dates[8]
    assert pd.isna(calendar.loc[2, "label_end"])


def test_pit_fold_excludes_prior_month_whose_label_ends_after_test() -> None:
    calendar = pd.DataFrame(
        {
            "eval_date": pd.to_datetime(
                ["2024-01-31", "2024-02-29", "2024-03-31", "2024-04-30", "2024-05-31"]
            ),
            "label_end": pd.to_datetime(
                ["2024-02-15", "2024-06-15", "2024-04-15", "2024-07-15", "2024-08-15"]
            ),
        }
    )

    folds = features.build_pit_fold_plan(calendar, minimum_train_months=2)

    may = folds.loc[folds["test_eval_date"].eq(pd.Timestamp("2024-05-31"))].iloc[0]
    assert may["train_eval_dates"] == "2024-01-31,2024-03-31"
    assert may["train_months"] == 2
    assert may["train_label_end_max"] == pd.Timestamp("2024-04-15")
    assert may["pit_violation_rows"] == 0


def test_pit_fold_rejects_inconsistent_duplicate_label_end() -> None:
    calendar = pd.DataFrame(
        {
            "eval_date": pd.to_datetime(["2024-01-31", "2024-01-31"]),
            "label_end": pd.to_datetime(["2024-04-01", "2024-04-02"]),
        }
    )

    with pytest.raises(ValueError, match="inconsistent_label_end"):
        features.build_pit_fold_plan(calendar, minimum_train_months=1)
