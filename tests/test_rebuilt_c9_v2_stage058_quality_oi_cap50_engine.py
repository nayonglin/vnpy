from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage058_quality_oi_cap50_add_risk_engine as s058


class Stage058QualityOiCap50EngineTest(unittest.TestCase):
    def _lookup(self) -> dict[str, pd.DataFrame]:
        snapshots = pd.DataFrame(
            [
                {
                    "feature_date": "2020-01-01",
                    "asof_date": "2020-01-02",
                    "product_key": "rb.shfe",
                    "product_vt_symbol": "rb.SHFE",
                    "contract_vt_symbol": "rb2005.SHFE",
                    "contract_open_interest": 1000,
                    "product_total_oi": 2500,
                    "contract_oi_share": 0.40,
                    "oi_rank": 2,
                    "contract_count": 3,
                    "top1_contract_vt": "rb2010.SHFE",
                    "top1_oi_share": 0.45,
                    "top2_contract_vt": "rb2005.SHFE",
                    "top2_oi_share": 0.40,
                    "top2_cumulative_oi_share": 0.85,
                    "main_contract_vt": "rb2005.SHFE",
                    "mapping_main_oi_share": 0.40,
                    "contract_is_mapping_main": True,
                    "contract_is_top1_oi": False,
                    "contract_is_top2_oi": True,
                },
                {
                    "feature_date": "2020-01-02",
                    "asof_date": "2020-01-03",
                    "product_key": "rb.shfe",
                    "product_vt_symbol": "rb.SHFE",
                    "contract_vt_symbol": "rb2005.SHFE",
                    "contract_open_interest": 1600,
                    "product_total_oi": 2500,
                    "contract_oi_share": 0.64,
                    "oi_rank": 1,
                    "contract_count": 3,
                    "top1_contract_vt": "rb2005.SHFE",
                    "top1_oi_share": 0.64,
                    "top2_contract_vt": "rb2010.SHFE",
                    "top2_oi_share": 0.20,
                    "top2_cumulative_oi_share": 0.84,
                    "main_contract_vt": "rb2005.SHFE",
                    "mapping_main_oi_share": 0.64,
                    "contract_is_mapping_main": True,
                    "contract_is_top1_oi": True,
                    "contract_is_top2_oi": True,
                },
            ]
        )
        return s058._stage058_build_oi_lookup(snapshots)

    def test_oi_lookup_uses_latest_prior_asof_without_future_peek(self) -> None:
        lookup = self._lookup()

        before = s058._stage058_contract_oi_fields(
            contract_vt_symbol="rb2005.SHFE",
            entry_date=pd.Timestamp("2020-01-02 10:00:00+08:00"),
            oi_lookup=lookup,
        )
        after = s058._stage058_contract_oi_fields(
            contract_vt_symbol="rb2005.SHFE",
            entry_date=pd.Timestamp("2020-01-03"),
            oi_lookup=lookup,
        )

        self.assertEqual(before["stage058_contract_oi_asof_date"], "2020-01-02")
        self.assertAlmostEqual(float(before["stage058_contract_oi_share"]), 0.40)
        self.assertEqual(before["stage058_contract_oi_share_hit"], 0)
        self.assertEqual(after["stage058_contract_oi_asof_date"], "2020-01-03")
        self.assertAlmostEqual(float(after["stage058_contract_oi_share"]), 0.64)
        self.assertEqual(after["stage058_contract_oi_share_hit"], 1)

    def test_oi_lookup_rejects_stale_features(self) -> None:
        fields = s058._stage058_contract_oi_fields(
            contract_vt_symbol="rb2005.SHFE",
            entry_date=pd.Timestamp("2020-01-20"),
            oi_lookup=self._lookup(),
            max_feature_age_days=5,
        )

        self.assertEqual(fields["stage058_contract_oi_matched"], 0)
        self.assertEqual(fields["stage058_contract_oi_lookup_reason"], "asof_too_old")

    def test_quality_and_oi_hits_cap_at_50pct_floor_integer(self) -> None:
        selected, fields = s058._stage058_apply_quality_oi_cap50_add_risk(
            sizing={"selected_volume": 8, "ai_product_pool_rank": 3},
            direction="long",
            entry_context="flat_entry",
            target_contract="rb2005.SHFE",
            entry_date=pd.Timestamp("2020-01-03"),
            oi_lookup=self._lookup(),
            enabled=True,
        )

        self.assertEqual(selected, 12)
        self.assertEqual(fields["stage058_quality_oi_add_risk_applied"], 1)
        self.assertAlmostEqual(float(fields["stage058_quality_oi_raw_add_fraction"]), 0.50)
        self.assertAlmostEqual(float(fields["stage058_quality_oi_capped_add_fraction"]), 0.50)
        self.assertEqual(fields["stage058_quality_oi_quality_hit"], 1)
        self.assertEqual(fields["stage058_quality_oi_oi_hit"], 1)

    def test_single_leg_hits_add_25pct_floor_integer(self) -> None:
        quality_only, quality_fields = s058._stage058_apply_quality_oi_cap50_add_risk(
            sizing={"selected_volume": 8, "ai_product_pool_rank": 3},
            direction="long",
            entry_context="flat_entry",
            target_contract="rb2005.SHFE",
            entry_date=pd.Timestamp("2020-01-02"),
            oi_lookup=self._lookup(),
            enabled=True,
        )
        oi_only, oi_fields = s058._stage058_apply_quality_oi_cap50_add_risk(
            sizing={"selected_volume": 8, "ai_product_pool_rank": 9},
            direction="long",
            entry_context="flat_entry",
            target_contract="rb2005.SHFE",
            entry_date=pd.Timestamp("2020-01-03"),
            oi_lookup=self._lookup(),
            enabled=True,
        )

        self.assertEqual(quality_only, 10)
        self.assertEqual(quality_fields["stage058_quality_oi_quality_hit"], 1)
        self.assertEqual(quality_fields["stage058_quality_oi_oi_hit"], 0)
        self.assertEqual(oi_only, 10)
        self.assertEqual(oi_fields["stage058_quality_oi_quality_hit"], 0)
        self.assertEqual(oi_fields["stage058_quality_oi_oi_hit"], 1)

    def test_preserves_no_hit_small_integer_and_non_flat_cases(self) -> None:
        cases = [
            ({"selected_volume": 8, "ai_product_pool_rank": 9}, "rb2005.SHFE", "2020-01-02", "flat_entry", "quality_and_oi_not_hit"),
            ({"selected_volume": 3, "ai_product_pool_rank": 3}, "rb2005.SHFE", "2020-01-02", "flat_entry", "floor_combo_no_integer_increment"),
            ({"selected_volume": 8, "ai_product_pool_rank": 3}, "rb2005.SHFE", "2020-01-03", "regular_add", "non_flat_entry_context"),
        ]

        for sizing, contract, entry_date, entry_context, reason in cases:
            with self.subTest(reason=reason):
                selected, fields = s058._stage058_apply_quality_oi_cap50_add_risk(
                    sizing=sizing,
                    direction="long",
                    entry_context=entry_context,
                    target_contract=contract,
                    entry_date=pd.Timestamp(entry_date),
                    oi_lookup=self._lookup(),
                    enabled=True,
                )

                self.assertEqual(selected, int(sizing["selected_volume"]))
                self.assertEqual(fields["stage058_quality_oi_add_risk_applied"], 0)
                self.assertEqual(fields["stage058_quality_oi_add_risk_reason"], reason)


if __name__ == "__main__":
    unittest.main()
