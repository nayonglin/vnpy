from __future__ import annotations

from pathlib import Path
import sys
import unittest

import pandas as pd


TOOLS_DIR = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_optimization"
    / "tools"
)
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


from stage070_super_quality_sibling_panel import (  # noqa: E402
    CANDIDATE_VARIANTS,
    _build_panel_lot_deltas_from_frames,
    _build_panel_curves,
    _candidate_masks,
)


class RebuiltC9Stage070SuperQualitySiblingPanelTest(unittest.TestCase):
    def test_candidate_masks_are_frozen_stage068_new_composites(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "open_trade_id": "A",
                    "full_market_ai_top8": True,
                    "account_injured": True,
                    "ai_rank_1_6": False,
                    "active_positions_ge3": False,
                },
                {
                    "open_trade_id": "B",
                    "full_market_ai_top8": True,
                    "account_injured": False,
                    "ai_rank_1_6": True,
                    "active_positions_ge3": True,
                },
                {
                    "open_trade_id": "C",
                    "full_market_ai_top8": True,
                    "account_injured": False,
                    "ai_rank_1_6": False,
                    "active_positions_ge3": False,
                },
            ]
        )

        masks = _candidate_masks(frame)

        self.assertEqual(set(masks), set(CANDIDATE_VARIANTS))
        self.assertEqual(frame.loc[masks["full_market_ai_top8_and_account_injured"], "open_trade_id"].tolist(), ["A"])
        self.assertEqual(frame.loc[masks["full_market_ai_top8_and_ai_rank_1_6"], "open_trade_id"].tolist(), ["B"])
        self.assertEqual(frame.loc[masks["full_market_ai_top8_and_active_positions_lt3"], "open_trade_id"].tolist(), ["A", "C"])

    def test_panel_lot_deltas_can_select_same_lot_for_multiple_frozen_variants(self) -> None:
        closed = pd.DataFrame(
            [
                {
                    "requested_start_month": "2020-01",
                    "lot_id": "lot1",
                    "open_trade_id": "A",
                    "entry_date": "2020-01-02",
                    "exit_date": "2020-01-10",
                    "product": "rb.SHFE",
                    "vt_symbol": "rb2005.SHFE",
                    "direction": "long",
                    "realized_pnl": 1000.0,
                }
            ]
        )
        matrix = pd.DataFrame(
            [
                {
                    "requested_start_month": "2020-01",
                    "open_trade_id": "A",
                    "full_market_ai_top8": True,
                    "account_injured": True,
                    "ai_rank_1_6": True,
                    "active_positions_ge3": False,
                }
            ]
        )

        deltas, audit = _build_panel_lot_deltas_from_frames(closed, matrix)

        self.assertEqual(set(deltas["candidate_variant"]), set(CANDIDATE_VARIANTS))
        self.assertTrue((deltas["stage070_proxy_delta_pnl"] == 250.0).all())
        self.assertEqual(audit["variant_count"], len(CANDIDATE_VARIANTS))

    def test_panel_curves_apply_each_variant_delta_independently(self) -> None:
        curves = pd.DataFrame(
            [
                {"requested_start_month": "2020-01", "date": "2020-01-10", "account_equity": 150000.0},
                {"requested_start_month": "2020-01", "date": "2020-01-11", "account_equity": 151000.0},
            ]
        )
        deltas = pd.DataFrame(
            [
                {
                    "candidate_variant": "full_market_ai_top8_and_ai_rank_1_6",
                    "requested_start_month": "2020-01",
                    "exit_date": pd.Timestamp("2020-01-11"),
                    "stage070_proxy_delta_pnl": 250.0,
                },
                {
                    "candidate_variant": "full_market_ai_top8_and_active_positions_lt3",
                    "requested_start_month": "2020-01",
                    "exit_date": pd.Timestamp("2020-01-11"),
                    "stage070_proxy_delta_pnl": -100.0,
                },
            ]
        )

        panel, unmatched = _build_panel_curves(curves, deltas)

        self.assertEqual(unmatched, 0)
        by_variant = panel[panel["date"].eq(pd.Timestamp("2020-01-11"))].set_index("variant")
        self.assertAlmostEqual(float(by_variant.loc["stage013_engine", "equity"]), 151000.0)
        self.assertAlmostEqual(float(by_variant.loc["full_market_ai_top8_and_ai_rank_1_6", "equity"]), 151250.0)
        self.assertAlmostEqual(float(by_variant.loc["full_market_ai_top8_and_active_positions_lt3", "equity"]), 150900.0)


if __name__ == "__main__":
    unittest.main()
