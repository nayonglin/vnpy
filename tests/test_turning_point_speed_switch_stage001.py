from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_turning_point_speed_switch" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def module():
    return importlib.import_module("stage001_turning_state_attribution")


def close_panel(*, periods: int = 50, descending: bool = False) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    dates = pd.bdate_range("2020-01-01", periods=periods)
    values = np.arange(100.0, 100.0 + periods)
    if descending:
        values = values[::-1]
    frame = pd.DataFrame(
        {
            "date": dates,
            "contract_vt_symbol": "rb2005.SHFE",
            "close": values,
            "return_valid": [0] + [1] * (periods - 1),
            "source": "synthetic",
        }
    )
    return frame, dates


class Stage001TurningStateAttributionTest(unittest.TestCase):
    def test_contract_to_product_preserves_exchange(self) -> None:
        m = module()
        self.assertEqual(m.contract_to_product("rb2005.SHFE"), "rb.SHFE")
        self.assertEqual(m.contract_to_product("AP010.CZCE"), "AP.CZCE")
        self.assertEqual(m.contract_to_product("IF2606.CFFEX"), "IF.CFFEX")
        with self.assertRaisesRegex(ValueError, "contract"):
            m.contract_to_product("bad-symbol")

    def test_t1_state_uses_exact_previous_40_days_and_ignores_action_day(self) -> None:
        m = module()
        panel, dates = close_panel()
        action_date = dates[45]
        shocked = pd.concat(
            [
                panel,
                pd.DataFrame(
                    [
                        {
                            "date": action_date,
                            "contract_vt_symbol": "rb2005.SHFE",
                            "close": 1.0,
                            "return_valid": 1,
                            "source": "future_shock",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        ).drop_duplicates(["date", "contract_vt_symbol"], keep="last")
        state = m.compute_t1_ma_state(
            shocked,
            contract="rb2005.SHFE",
            action_date=action_date,
            market_dates=dates,
            position_direction=1,
        )
        self.assertEqual(state["available"], 1)
        self.assertEqual(state["asof_date"], dates[44])
        self.assertLess(state["asof_date"], action_date)
        self.assertEqual(state["slow_aligned"], 1)
        self.assertEqual(state["fast_relation"], "concordant")

    def test_t1_state_handles_short_and_rejects_short_or_gapped_history(self) -> None:
        m = module()
        panel, dates = close_panel(descending=True)
        state = m.compute_t1_ma_state(
            panel,
            contract="rb2005.SHFE",
            action_date=dates[45],
            market_dates=dates,
            position_direction=-1,
        )
        self.assertEqual(state["slow_aligned"], 1)
        self.assertEqual(state["fast_relation"], "concordant")

        short_panel = panel.iloc[:39].copy()
        short_dates = dates[:40]
        unavailable = m.compute_t1_ma_state(
            short_panel,
            contract="rb2005.SHFE",
            action_date=short_dates[-1],
            market_dates=short_dates,
            position_direction=-1,
        )
        self.assertEqual(unavailable["available"], 0)
        self.assertEqual(unavailable["reason"], "insufficient_history")

        gapped = panel[panel["date"].ne(dates[30])].copy()
        unavailable = m.compute_t1_ma_state(
            gapped,
            contract="rb2005.SHFE",
            action_date=dates[45],
            market_dates=dates,
            position_direction=-1,
        )
        self.assertEqual(unavailable["available"], 0)
        self.assertEqual(unavailable["reason"], "nonconsecutive_history")

    def test_primary_event_is_once_per_episode_and_not_first_contract_state(self) -> None:
        m = module()
        dates = pd.bdate_range("2022-01-03", periods=7)
        rows = pd.DataFrame(
            {
                "action_date": dates,
                "episode_id": "rb.SHFE:long:1",
                "actual_contract": ["rb2205.SHFE"] * 5 + ["rb2210.SHFE"] * 2,
                "feature_available": 1,
                "slow_aligned": 1,
                "fast_relation": [
                    "concordant",
                    "opposite",
                    "opposite",
                    "neutral",
                    "opposite",
                    "opposite",
                    "opposite",
                ],
            }
        )
        result = m.mark_primary_events(rows, market_dates=dates)
        self.assertEqual(result.loc[result["is_primary_event"].eq(1), "action_date"].tolist(), [dates[1]])
        self.assertEqual(result.loc[5, "contract_first_state"], 1)

        starts_opposite = rows.iloc[:3].copy()
        starts_opposite["fast_relation"] = ["opposite", "neutral", "opposite"]
        result = m.mark_primary_events(starts_opposite, market_dates=dates)
        self.assertEqual(int(result["is_primary_event"].sum()), 0)

    def test_event_requires_consecutive_observed_state(self) -> None:
        m = module()
        dates = pd.bdate_range("2022-01-03", periods=4)
        rows = pd.DataFrame(
            {
                "action_date": [dates[0], dates[2]],
                "episode_id": "x:long:1",
                "actual_contract": "x2205.DCE",
                "feature_available": 1,
                "slow_aligned": 1,
                "fast_relation": ["concordant", "opposite"],
            }
        )
        result = m.mark_primary_events(rows, market_dates=dates)
        self.assertEqual(int(result["is_primary_event"].sum()), 0)

    def test_half_release_is_conservative_integer_action(self) -> None:
        m = module()
        self.assertEqual(m.half_release(1), (1, 0))
        self.assertEqual(m.half_release(2), (1, 1))
        self.assertEqual(m.half_release(3), (2, 1))
        self.assertEqual(m.half_release(10), (5, 5))
        with self.assertRaises(ValueError):
            m.half_release(-1)

    def test_pigeonhole_bootstrap_is_deterministic_and_detects_adverse_difference(self) -> None:
        m = module()
        rows = []
        for product_index in range(8):
            for block in range(8):
                rows.append(
                    {
                        "product": f"p{product_index}.X",
                        "date_block20": block,
                        "group": "opposite",
                        "outcome": -0.8 - product_index * 0.01,
                    }
                )
                rows.append(
                    {
                        "product": f"p{product_index}.X",
                        "date_block20": block,
                        "group": "concordant",
                        "outcome": 0.2 + product_index * 0.01,
                    }
                )
        frame = pd.DataFrame(rows)
        first = m.pigeonhole_bootstrap_mean_difference(frame, iterations=500, seed=20260712)
        second = m.pigeonhole_bootstrap_mean_difference(frame, iterations=500, seed=20260712)
        self.assertEqual(first, second)
        self.assertLess(first["point_difference"], -0.9)
        self.assertLess(first["ci95_upper"], 0.0)
        with self.assertRaisesRegex(ValueError, "products"):
            m.pigeonhole_bootstrap_mean_difference(frame[frame["product"].eq("p0.X")])

    def test_mechanical_decision_fails_closed(self) -> None:
        m = module()
        gates = pd.DataFrame(
            [
                {"gate": "coverage", "passed": 1, "detail": "ok"},
                {"gate": "statistics", "passed": 0, "detail": "ci crosses zero"},
            ]
        )
        self.assertFalse(m.mechanical_canary_decision(gates))
        self.assertTrue(m.mechanical_canary_decision(gates.assign(passed=1)))
        with self.assertRaisesRegex(ValueError, "gate"):
            m.mechanical_canary_decision(pd.DataFrame())

    def test_empty_outcome_frame_keeps_fail_closed_schema(self) -> None:
        m = module()
        result = m.attach_outcomes(
            pd.DataFrame(columns=["action_date"]),
            positions=pd.DataFrame(),
            trades=pd.DataFrame(),
            product_days=pd.DataFrame(),
            panel=pd.DataFrame(),
            market_dates=pd.DatetimeIndex([]),
            include_economics=True,
        )
        for column in (
            "outcome_1d_available",
            "outcome_5d_available",
            "outcome_20d_available",
            "economic_available",
            "released_volume",
        ):
            self.assertIn(column, result.columns)
        self.assertTrue(result.empty)

    def test_analysis_frames_are_hard_truncated_to_frozen_end(self) -> None:
        m = module()
        frames = {
            name: pd.DataFrame({"date": ["2026-06-29", "2026-06-30"], "value": [1, 2]})
            for name in ("daily", "trades", "positions", "candidates", "panel")
        }
        result = m.truncate_analysis_frames(frames, pd.Timestamp("2026-06-29"))
        for frame in result.values():
            self.assertEqual(frame["date"].max(), pd.Timestamp("2026-06-29"))
            self.assertEqual(len(frame), 1)

    def test_cross_day_position_conservation_rejects_missing_or_wrong_carry(self) -> None:
        m = module()
        dates = pd.bdate_range("2022-01-03", periods=3)
        valid = pd.DataFrame(
            {
                "date": [dates[0], dates[1], dates[2]],
                "vt_symbol": "a2205.X",
                "start_pos": [0, 1, 1],
                "end_pos": [1, 1, 0],
            }
        )
        audit = m.validate_cross_day_position_conservation(valid, market_dates=dates)
        self.assertEqual(audit["cross_day_checked_rows"], 2)
        wrong = valid.copy()
        wrong.loc[1, "start_pos"] = 2
        with self.assertRaisesRegex(RuntimeError, "cross-day"):
            m.validate_cross_day_position_conservation(wrong, market_dates=dates)
        missing = pd.concat(
            [
                valid.iloc[[0, 2]],
                pd.DataFrame(
                    {
                        "date": [dates[1]],
                        "vt_symbol": ["dummy2205.X"],
                        "start_pos": [0],
                        "end_pos": [0],
                    }
                ),
            ],
            ignore_index=True,
        )
        with self.assertRaisesRegex(RuntimeError, "cross-day"):
            m.validate_cross_day_position_conservation(missing, market_dates=dates)

    def test_exit_price_is_volume_weighted(self) -> None:
        m = module()
        date = pd.Timestamp("2022-01-04")
        trades = pd.DataFrame(
            {
                "date": [date, date],
                "vt_symbol": ["a2205.X", "a2205.X"],
                "offset": ["Close", "Close"],
                "direction_sign": [-1, -1],
                "price": [100.0, 110.0],
                "volume": [1, 3],
                "trade_id": ["1", "2"],
                "datetime": ["2022-01-04 09:01:00+08:00", "2022-01-04 09:02:00+08:00"],
            }
        )
        price = m._exit_trade_price(
            trades,
            date=date,
            contract="a2205.X",
            position_direction=1,
        )
        self.assertAlmostEqual(price, 107.5)

    def test_empty_concentration_and_summary_fail_closed(self) -> None:
        m = module()
        self.assertIsNone(m.positive_top_n_share(pd.Series(dtype=float), n=5))
        self.assertIsNone(m.positive_top_n_share(pd.Series([-1.0, 0.0]), n=5))
        self.assertAlmostEqual(m.positive_top_n_share(pd.Series([4.0, 3.0, 2.0, 1.0]), n=2), 0.7)
        summary = m.build_event_summary(pd.DataFrame())
        self.assertTrue(summary.empty)
        self.assertIn("dimension", summary.columns)
        self.assertIn("mean_5d_r", summary.columns)


if __name__ == "__main__":
    unittest.main()
