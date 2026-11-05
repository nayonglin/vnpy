from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from stage005_trade_recap import (
    LINE, STAGE005, STAGE007_2022, STAGE013_2022, STAGE018_2022,
    WINDOW_PROFILES,
    episode_inputs, load, partition_cycles, reversal_links, write,
)


class Stage005RecapTest(unittest.TestCase):
    def test_overlap_keeps_carry_in_and_carry_out_and_discloses_residual(self):
        profile = WINDOW_PROFILES["q-2020-drawdown"]
        cycles = pd.DataFrame({
            "cycle": [1, 2, 3, 4, 5, 6],
            "entry_day": ["2019-12-01", "2019-12-23", "2020-01-02", "2020-06-05", "2020-06-08", "2020-01-03"],
            "exit_day": ["2019-12-31", "2020-01-02", "2020-02-03", "2020-06-08", "2020-06-12", ""],
        })
        closed, residual = partition_cycles(cycles, profile)
        self.assertEqual(closed.cycle.to_list(), [2, 3, 4])
        self.assertEqual(residual.cycle.to_list(), [6])

    def test_s_window_verifies_frozen_manifest_and_only_accepts_s(self):
        profile = WINDOW_PROFILES["s-2022-drawdown"]
        with self.assertRaisesRegex(ValueError, "frozen hash mismatch"):
            load(LINE / "outputs" / STAGE018_2022.run, profile)
        inputs, _, cycles, _, _, _, _ = load(LINE / "outputs" / profile.run, profile)
        self.assertTrue(inputs["block_four_up"])
        closed, residual = partition_cycles(cycles, profile)
        self.assertEqual(len(closed), 78)
        self.assertTrue(residual.empty)

    def test_missing_frozen_receipt_stops_generation(self):
        with TemporaryDirectory() as tmp:
            dest = Path(tmp) / "new_recap"
            with self.assertRaisesRegex(FileNotFoundError, "independent_audit"):
                write(Path(tmp), dest)
            self.assertFalse(dest.exists())

    def test_mismatched_receipt_is_rejected(self):
        with TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "independent_audit.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "frozen hash mismatch"):
                load(run)

    def test_cross_year_exit_retained_and_residual_disclosed(self):
        cycles = pd.DataFrame({
            "cycle": [1, 2, 3, 4],
            "entry_day": ["2014-12-31", "2020-12-28", "2020-12-31", "2021-01-04"],
            "exit_day": ["2015-01-05", "2021-01-08", "", "2021-01-15"],
        })
        closed, residual = partition_cycles(cycles)
        self.assertEqual(closed.cycle.to_list(), [2])
        self.assertEqual(residual.cycle.to_list(), [3])

    def test_existing_output_is_preserved(self):
        with TemporaryDirectory() as tmp:
            dest = Path(tmp)
            index = dest / "index.html"
            index.write_text("previous recap")
            with self.assertRaises(FileExistsError):
                write(dest / "missing-run", dest)
            self.assertEqual(index.read_text(), "previous recap")

    def test_fixed_one_profile_rejects_another_audited_run(self):
        with self.assertRaisesRegex(ValueError, "frozen hash mismatch"):
            load(LINE / "outputs" / STAGE005.run, STAGE007_2022)

    def test_fixed_one_frozen_cycles_need_no_sizing_ledger(self):
        _, _, cycles, fills, sizing, _, _ = load(LINE / "outputs" / STAGE007_2022.run, STAGE007_2022)
        closed, residual = partition_cycles(cycles, STAGE007_2022)
        episodes, _, entry_sizing = episode_inputs(closed, fills, sizing)
        self.assertIsNone(entry_sizing)
        self.assertTrue(residual.empty)
        self.assertEqual(len(episodes), 117)
        self.assertEqual(episodes.exit_date.gt(STAGE007_2022.end).sum(), 10)
        self.assertTrue(episodes.volume.eq(1).all())
        self.assertAlmostEqual(episodes.realized_pnl.sum(), -41495)

    def test_fresh_add_profile_reconciles_odd_number_of_fills(self):
        profile = STAGE013_2022
        _, _, cycles, fills, sizing, _, _ = load(LINE / "outputs" / profile.run, profile)
        closed, residual = partition_cycles(cycles, profile)
        episodes, legs, _ = episode_inputs(closed, fills, sizing)
        self.assertTrue(residual.empty)
        self.assertEqual(len(episodes), 117)
        self.assertEqual(sum(len(legs[cycle]) for cycle in closed.cycle), 325)
        self.assertEqual(episodes.realized_pnl.sum(), -91340)
        self.assertEqual(len(legs[581]), 11)
        self.assertEqual(legs[581][-1].volume, 2)
        broken = fills.copy()
        broken.loc[broken.cycle.eq(581) & broken.reason.eq("weekly_stop"), "volume"] = 1
        with self.assertRaisesRegex(ValueError, "segment does not flatten"):
            episode_inputs(closed, broken, sizing)

    def test_q_pairs_distinct_reversal_cycles(self):
        profile = STAGE018_2022
        _, _, cycles, fills, sizing, _, _ = load(LINE / "outputs" / profile.run, profile)
        closed, residual = partition_cycles(cycles, profile)
        self.assertEqual(len(closed), 124)
        self.assertTrue(residual.empty)
        self.assertIsNone(sizing)
        links = reversal_links(fills)
        entries = fills.loc[fills.cycle.isin(closed.cycle) & fills.reason.eq("entry")]
        self.assertEqual(entries.fill_id.isin(links).sum(), 29)
        new = entries.loc[entries.cycle.eq(754)].iloc[0]
        old = links[new.fill_id]
        self.assertEqual((old.cycle, old.date, old.price), (739, "2022-10-31", 10939))
        self.assertEqual(links[old.fill_id].cycle, 754)

    def test_s44_2022_binds_both_pools_and_keeps_delivery_exits(self):
        from stage005_trade_recap import STAGE025_S44_2022

        profile = STAGE025_S44_2022
        with self.assertRaisesRegex(ValueError, "frozen hash mismatch"):
            load(LINE / "outputs" / profile.run.replace("S44_", "S19_"), profile)
        inputs, metrics, cycles, fills, sizing, market, mapping = load(LINE / "outputs" / profile.run, profile)
        closed, residual = partition_cycles(cycles, profile)
        episodes, _, _ = episode_inputs(closed, fills, sizing)
        self.assertEqual(len(inputs["products"]), 44)
        self.assertEqual(set(mapping.continuous_symbol_vt), set(inputs["products"]))
        self.assertEqual(metrics["equity"], 1466160)
        self.assertEqual(len(episodes), 321)
        self.assertTrue(residual.empty)
        self.assertEqual(episodes.direction.value_counts().to_dict(), {"long": 169, "short": 152})
        self.assertEqual(int(episodes.exit_date.gt(profile.end).sum()), 20)
        self.assertEqual(int(episodes.exit_reason.eq("到期保护平仓").sum()), 48)
        self.assertEqual(episodes.realized_pnl.sum(), -42365)
        self.assertTrue(set(fills.loc[fills.cycle.isin(closed.cycle), "epoch"]) <= set(market.contract_epoch_id))
