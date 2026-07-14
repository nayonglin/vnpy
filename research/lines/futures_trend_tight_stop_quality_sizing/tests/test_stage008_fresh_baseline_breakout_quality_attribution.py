from __future__ import annotations

from pathlib import Path
import sys
import tempfile

import numpy as np
import pandas as pd
import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage008_fresh_baseline_breakout_quality_attribution as s008


def _bars(count: int = 90) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=count)
    close = np.linspace(100.0, 145.0, count)
    return pd.DataFrame(
        {
            "date": dates,
            "open": close - 0.4,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1000.0,
        }
    )


def test_prior20_channel_excludes_current_signal_bar() -> None:
    bars = _bars()
    bars.loc[bars.index[-1], "high"] = 10_000.0
    panel = s008.indicator_panel(bars)

    row = panel.iloc[-1]
    expected = bars.iloc[-21:-1]["high"].max()
    assert row["prior20_high"] == pytest.approx(expected)
    assert row["prior20_high"] != pytest.approx(10_000.0)


def test_feature_snapshot_uses_last_completed_bar_and_direction() -> None:
    bars = _bars()
    panel = s008.indicator_panel(bars)
    entry_date = bars["date"].iloc[-1] + pd.offsets.BDay(1)

    long_row = s008.features_before_entry(panel, entry_date, "long")
    short_row = s008.features_before_entry(panel, entry_date, "short")

    assert pd.Timestamp(long_row["feature_date"]).normalize() == bars["date"].iloc[-1]
    assert pd.Timestamp(long_row["feature_date"]).normalize() < pd.Timestamp(entry_date).normalize()
    assert long_row["directional_efficiency20"] > 0
    assert short_row["directional_efficiency20"] < 0
    assert long_row["breakout_margin20_atr"] > 0
    assert short_row["breakout_margin20_atr"] < 0


def test_discovery_summary_cannot_consume_validation_or_holdout_pnl() -> None:
    frame = pd.DataFrame(
        {
            "sample_segment": ["discovery"] * 8 + ["validation", "holdout"],
            "entry_date": pd.to_datetime(
                [f"2022-01-{day:02d}" for day in range(3, 11)] + ["2023-01-03", "2025-01-03"]
            ),
            "product": ["A", "B", "C", "D", "E", "F", "G", "H", "X", "Y"],
            "direction": ["long", "short"] * 5,
            "realized_pnl": [10.0, -2.0, 8.0, -1.0, 6.0, -3.0, 5.0, -4.0, 1e9, -1e9],
            "r_multiple": [1.0, -0.2, 0.8, -0.1, 0.6, -0.3, 0.5, -0.4, 1e8, -1e8],
            "stop_atr14": np.arange(1.0, 11.0),
            "breakout_margin20_atr": np.arange(-2.0, 8.0),
            "directional_efficiency20": np.linspace(-0.8, 0.8, 10),
            "atr14_to_prior60_median": np.linspace(0.5, 1.5, 10),
        }
    )

    summary = s008.discovery_feature_bin_summary(frame)
    assert summary["candidate_count"].max() <= 2
    assert summary["total_pnl"].abs().max() < 100.0
    assert set(summary["sample_segment"]) == {"discovery"}


def test_partition_event_outputs_never_exports_future_outcomes() -> None:
    frame = pd.DataFrame(
        {
            "open_trade_id": ["D1", "V1", "H1"],
            "sample_segment": ["discovery", "validation", "holdout"],
            "stop_atr14": [0.5, 0.6, 0.7],
            "breakout_margin20_atr": [1.0, 2.0, 3.0],
            "realized_pnl": [10.0, 1e9, -1e9],
            "r_multiple": [1.0, 1e8, -1e8],
            "initial_pnl": [10.0, 1e9, -1e9],
        }
    )

    discovery, future_seal = s008.partition_event_outputs(frame)

    assert discovery["open_trade_id"].tolist() == ["D1"]
    assert set(discovery["sample_segment"]) == {"discovery"}
    assert future_seal["row_count"] == 2
    assert future_seal["outcome_columns_removed"] is True
    assert set(future_seal["segments"]) == {"validation", "holdout"}
    assert "rows" not in future_seal

    mutated = frame.copy()
    mutated.loc[mutated["sample_segment"] != "discovery", ["realized_pnl", "r_multiple", "initial_pnl"]] *= -999.0
    _, changed_seal = s008.partition_event_outputs(mutated)
    assert changed_seal["feature_only_sha256"] == future_seal["feature_only_sha256"]


def test_prepare_output_directory_removes_legacy_future_outcome_file() -> None:
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory)
        legacy = output / "entry_events_private.csv.gz"
        legacy.write_bytes(b"future outcomes")

        s008.prepare_output_directory(output, legacy_paths=[legacy])

        assert output.is_dir()
        assert not legacy.exists()


def test_distribution_thresholds_ignore_outcome_columns() -> None:
    frame = pd.DataFrame(
        {
            "sample_segment": ["discovery"] * 4 + ["validation"],
            "stop_atr14": [0.5, 1.0, 1.5, 2.0, 999.0],
            "breakout_margin20_atr": [-1.0, 0.0, 1.0, 2.0, 999.0],
            "directional_efficiency20": [-0.5, 0.0, 0.5, 1.0, 999.0],
            "atr14_to_prior60_median": [0.8, 0.9, 1.0, 1.1, 999.0],
            "realized_pnl": [1e9, -1e9, 1e9, -1e9, 1e12],
        }
    )
    thresholds = s008.discovery_distribution_thresholds(frame)

    assert thresholds["stop_atr14_q50"] == pytest.approx(1.25)
    assert thresholds["breakout_margin20_atr_q75"] == pytest.approx(1.25)
    assert thresholds["directional_efficiency20_q50"] == pytest.approx(0.25)
    assert thresholds["atr14_to_prior60_median_q50"] == pytest.approx(0.95)


def test_new_feature_table_rejects_ai_fields() -> None:
    with pytest.raises(ValueError, match="AI-derived"):
        s008.assert_no_new_ai_features(pd.DataFrame({"ai_rank": [1], "stop_atr14": [0.5]}))


def test_terminal_open_inventory_reconciles_fifo_long_and_short() -> None:
    trades = pd.DataFrame(
        [
            {"datetime": "2024-01-02 09:01", "vt_symbol": "A.X", "trade_id": "1", "offset": "Open", "direction": "Long", "price": 100.0, "volume": 2.0},
            {"datetime": "2024-01-03 09:01", "vt_symbol": "A.X", "trade_id": "2", "offset": "Close", "direction": "Short", "price": 110.0, "volume": 1.0},
            {"datetime": "2024-01-02 09:02", "vt_symbol": "B.X", "trade_id": "3", "offset": "Open", "direction": "Short", "price": 200.0, "volume": 3.0},
            {"datetime": "2024-01-03 09:02", "vt_symbol": "B.X", "trade_id": "4", "offset": "Close", "direction": "Long", "price": 190.0, "volume": 1.0},
        ]
    )
    positions = pd.DataFrame(
        [
            {"date": "2024-01-03", "vt_symbol": "A.X", "end_pos": 1.0, "close_price": 105.0},
            {"date": "2024-01-03", "vt_symbol": "B.X", "end_pos": -2.0, "close_price": 180.0},
        ]
    )

    lots, audit = s008.terminal_open_inventory(trades, positions, {"sizes": {"A.X": 10, "B.X": 5}})

    assert len(lots) == 2
    assert audit["position_reconciliation_pass"] is True
    assert audit["terminal_unrealized_pnl"] == pytest.approx(250.0)


def test_terminal_open_inventory_rejects_position_mismatch() -> None:
    trades = pd.DataFrame(
        [{"datetime": "2024-01-02", "vt_symbol": "A.X", "trade_id": "1", "offset": "Open", "direction": "Long", "price": 100.0, "volume": 1.0}]
    )
    positions = pd.DataFrame(
        [{"date": "2024-01-03", "vt_symbol": "A.X", "end_pos": 2.0, "close_price": 105.0}]
    )

    with pytest.raises(RuntimeError, match="terminal position mismatch"):
        s008.terminal_open_inventory(trades, positions, {"sizes": {"A.X": 10}})


def test_same_timestamp_trade_ids_use_natural_engine_sequence() -> None:
    trades = pd.DataFrame(
        [
            {"datetime": "2024-01-02 09:01", "vt_symbol": "A.X", "trade_id": "BACKTESTING.10", "offset": "Close", "direction": "Short", "price": 99.0, "volume": 1.0},
            {"datetime": "2024-01-02 09:01", "vt_symbol": "A.X", "trade_id": "BACKTESTING.9", "offset": "Open", "direction": "Long", "price": 100.0, "volume": 1.0},
        ]
    )
    positions = pd.DataFrame(
        [{"date": "2024-01-02", "vt_symbol": "A.X", "end_pos": 0.0, "close_price": 99.0}]
    )

    canonical = s008.canonical_attribution_trades(trades)
    lots, audit = s008.terminal_open_inventory(trades, positions, {"sizes": {"A.X": 10}})

    assert canonical["trade_id_source"].tolist() == ["BACKTESTING.9", "BACKTESTING.10"]
    assert lots.empty
    assert audit["terminal_unrealized_pnl"] == pytest.approx(0.0)


def test_annual_return_uses_previous_year_end_equity() -> None:
    daily = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-12-31", "2021-01-04", "2021-12-31"]),
            "account_equity": [100.0, 120.0, 150.0],
            "net_pnl": [0.0, 20.0, 30.0],
            "trade_count": [0, 1, 1],
            "slippage": [0.0, 0.0, 0.0],
        }
    )

    annual = s008._annual_path(daily, capital=100.0).set_index("year")

    assert annual.loc[2021, "start_equity"] == pytest.approx(100.0)
    assert annual.loc[2021, "year_return_pct_on_start_equity"] == pytest.approx(50.0)


def test_drawdown_episode_counts_only_underwater_days() -> None:
    daily = pd.DataFrame(
        {
            "date": pd.bdate_range("2024-01-02", periods=4),
            "account_equity": [100.0, 90.0, 80.0, 100.0],
        }
    )
    events = pd.DataFrame(columns=["entry_date", "realized_pnl", "r_multiple"])

    episodes = s008._drawdown_episodes(daily, events)

    assert len(episodes) == 1
    assert int(episodes.iloc[0]["underwater_trading_days"]) == 2
    assert pd.Timestamp(episodes.iloc[0]["recovery_date"]) == daily["date"].iloc[-1]


def test_full_ai_pool_membership_audit_checks_values_and_blocked_absence() -> None:
    candidates = pd.DataFrame(
        [
            {
                "candidate_index": 1,
                "date": "2024-02-05",
                "product_vt_symbol": "rb.SHFE",
                "skip_reason": "",
                "ai_product_pool_enabled": 1,
                "ai_product_pool_allowed": 1,
                "ai_product_pool_strategy": "top",
                "ai_product_pool_signal_date": "2024-01-31",
                "ai_product_pool_score": 0.8,
                "ai_product_pool_rank": 1,
                "ai_product_pool_top_n": 1,
            },
            {
                "candidate_index": 2,
                "date": "2024-02-05",
                "product_vt_symbol": "au.SHFE",
                "skip_reason": "ai_product_pool_blocked",
                "ai_product_pool_enabled": 1,
                "ai_product_pool_allowed": 0,
                "ai_product_pool_strategy": "top",
                "ai_product_pool_signal_date": "2024-01-31",
                "ai_product_pool_score": 0.0,
                "ai_product_pool_rank": 0,
                "ai_product_pool_top_n": 0,
            },
        ]
    )
    pool = pd.DataFrame(
        [{"strategy": "top", "eval_date": "2024-01-31", "product_vt_symbol": "rb.SHFE", "score": 0.8, "score_rank": 1, "top_n": 1}]
    )

    audit = s008.full_ai_pool_membership_audit(candidates, pool)
    assert audit["allowed_value_mismatch_count"] == 0
    assert audit["blocked_member_mismatch_count"] == 0

    bad = candidates.copy()
    bad.loc[0, "ai_product_pool_score"] = 0.7
    with pytest.raises(RuntimeError, match="full AI pool membership audit failed"):
        s008.full_ai_pool_membership_audit(bad, pool)


def test_core_feature_coverage_gate_matches_predeclaration() -> None:
    assert s008.MIN_CORE_COVERAGE == pytest.approx(0.95)


def test_volume_mismatch_requires_exact_causal_forced_margin_deleverage_event() -> None:
    lineage = pd.DataFrame(
        [
            {
                "open_trade_id": "T1",
                "vt_symbol": "SM101.CZCE",
                "direction": "long",
                "source_datetime": "2020-11-25 00:00:00+08:00",
                "volume": 4.0,
                "source_selected_volume": 23.0,
                "attempt_kind": "flat_entry",
            }
        ]
    )
    events = pd.DataFrame(
        [
            {
                "date": "2020-11-25",
                "vt_symbol": "SM101.CZCE",
                "position_direction": "long",
                "reason": "forced_margin_deleverage",
                "volume": 19.0,
            }
        ]
    )

    audit = s008.audit_source_volume_mismatches(lineage, events)
    assert audit["mismatch_count"] == 1
    assert audit["unexplained_mismatch_count"] == 0
    assert audit["exact_causal_event_count"] == 1

    for column, value in [
        ("date", "2020-11-24"),
        ("vt_symbol", "rb2101.SHFE"),
        ("position_direction", "short"),
        ("volume", 18.0),
        ("reason", "long_base_stop"),
    ]:
        bad = events.copy()
        bad.loc[0, column] = value
        with pytest.raises(RuntimeError, match="unexplained source volume mismatch"):
            s008.audit_source_volume_mismatches(lineage, bad)
