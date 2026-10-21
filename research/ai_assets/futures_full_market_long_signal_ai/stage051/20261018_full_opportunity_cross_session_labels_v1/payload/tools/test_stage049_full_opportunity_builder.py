"""Bounded synthetic contracts; no native inputs, SQL, models or accounts."""
import importlib.util
import json
import math
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

import pandas as pd


SOURCE = Path(__file__).with_name("stage049_full_opportunity_builder.py")
spec = importlib.util.spec_from_file_location("stage049_builder_under_test", SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture(finish=42, missing=(), changes=None, references=None):
    changes, references = changes or {}, references or {}
    dates = [(date(2020, 1, 1) + timedelta(days=i)).isoformat() for i in range(finish)]
    epoch = "X.A.203001"
    records, panel = [], []
    for i, day in enumerate(dates):
        values = (100., 101., 99., 100.) if i < 20 else (102., 103., 101., 102.)
        O, H, L, C = changes.get(i, values)
        if i not in missing:
            records.append(dict(contract_epoch_id=epoch, trade_date=day, open=O, high=H,
                                low=L, close=C, volume=10., quality_status="accepted"))
        reference = references.get(i, epoch if i not in missing else "")
        panel.append(dict(event_id=f"e{i}", product_id="X.A", exchange="X", product="A",
                          u_date=day, reference_epoch=reference,
                          status="observed_long_research_opportunity" if reference else "no_accepted_observation",
                          planned_execution_date=dates[i + 1] if i + 1 < finish else "", direction="long"))
    economics = {epoch: dict(economics_status="exact_epoch_metadata_snapshot", contract_multiplier=10.,
                           round_lot=1., tick_size=None, vendor_margin_rate=.2,
                           listed_date="2019-01-01", maturity_date="2030-01-15",
                           de_listed_date="2030-01-15", known_lifecycle_exit_boundary="2030-01-01",
                           nominal_month_first_date="2030-01-01", future_info_scope="product_default_snapshot")}
    market = m.ref.Market.from_records(records, dates)
    return dates, records, pd.DataFrame(panel), economics, market


class FullOpportunityContracts(unittest.TestCase):
    def labels(self, f, **kwargs):
        dates, records, panel, economics, market = f
        frame = m.build_labels(panel, market, dates, economics, **kwargs)
        self.assertEqual(frame.event_id.tolist(), panel.event_id.tolist(), "mother identities/order must remain complete")
        return frame.set_index("event_id")

    def test_twenty_bars_ready_without_55_trigger_or_occupancy(self):
        frame = self.labels(fixture())
        self.assertEqual(frame.loc["e18", "label_history_ready20"], 0)
        self.assertEqual(frame.loc["e19", "label_history_ready20"], 1)
        self.assertEqual(frame.loc["e19", "N_u"], 2.)
        self.assertEqual(frame.loc["e19", "participation_state"], "filled")
        self.assertEqual(frame.loc["e20", "participation_state"], "filled")
        self.assertEqual(frame.loc["e19", "entry_index"], 20)
        self.assertEqual(frame.loc["e20", "entry_index"], 21)

    def test_gap_resets_twenty_bar_history_without_deleting_no_observation(self):
        frame = self.labels(fixture(missing=(18,)))
        self.assertEqual(frame.loc["e18", "label_history_ready20"], 0)
        self.assertEqual(frame.loc["e19", "label_history_ready20"], 0)
        self.assertEqual(frame.loc["e37", "label_history_ready20"], 0)
        self.assertEqual(frame.loc["e38", "label_history_ready20"], 1)
        self.assertEqual(frame.loc["e38", "history_run"], 20)

    def test_D_is_strict_source_successor_not_next_available_quote(self):
        f = fixture(missing=(20,))
        frame = self.labels(f)
        row = frame.loc["e19"]
        self.assertEqual(row.planned_execution_date, f[0][20])
        self.assertEqual(row.label_history_ready20, 1)
        self.assertEqual(row.label_state, "entry_execution_unknown")
        self.assertEqual(row.unknown_index, 20)
        self.assertTrue(pd.isna(row.net_R_stress))

    def test_stale_quote_cancels_preserving_null_trade_target_and_diagnostic_zero(self):
        f = fixture(changes={20: (99., 100., 98., 99.)})
        row = self.labels(f).loc["e19"]
        self.assertEqual(row.participation_state, "known_nonparticipation")
        self.assertEqual(row.cancel_reason, "stale_boundary_at_open")
        self.assertEqual(row.policy_diagnostic_pnl, 0.)
        self.assertEqual(row.filled, 0)
        self.assertEqual(row.participation_known_date, f[0][20])
        self.assertTrue(pd.isna(row.net_R_stress))
        self.assertTrue(pd.isna(row.label_known_date))

    def test_entry_same_bar_uses_u_boundary_and_complete_costs_per_lot(self):
        row = self.labels(fixture(changes={20: (102., 103., 98., 100.)})).loc["e19"]
        self.assertEqual(row.label_state, "closed_complete_bar_model")
        self.assertEqual(row.entry_index, 20)
        self.assertEqual(row.exit_index, 20)
        self.assertEqual(row.exit_reference, 99.)
        self.assertEqual(row.label_known_phase, "after_all_source_close")
        self.assertEqual(row.cash_risk_unit, 40.)
        self.assertAlmostEqual(row.net_pnl_base_per_lot, -34.201)
        self.assertAlmostEqual(row.net_pnl_stress_per_lot, -42.603)
        self.assertAlmostEqual(row.net_R_stress, -1.065075)
        self.assertAlmostEqual(row.base_total_fee_per_lot, 4.)
        self.assertAlmostEqual(row.base_total_slippage_per_lot, .201)
        self.assertAlmostEqual(row.base_u_fee_roundtrip_per_lot, 4.)
        self.assertAlmostEqual(row.base_u_slippage_roundtrip_per_lot, .2)
        self.assertAlmostEqual(row.stress_u_fee_roundtrip_per_lot, 12.)
        self.assertAlmostEqual(row.stress_u_slippage_roundtrip_per_lot, .6)

    def test_next_day_uses_prior_close_low_not_current_day_low(self):
        f = fixture(changes={0: (100., 101., 90., 100.), 21: (102., 103., 98.5, 100.)})
        row = self.labels(f).loc["e19"]
        self.assertEqual(row.label_state, "closed_complete_bar_model")
        self.assertAlmostEqual(row.N_u, 2.45)
        self.assertEqual(row.exit_index, 21)
        self.assertEqual(row.exit_reference, 99.)

    def test_gap_exit_loss_is_not_clamped_to_minus_one_R(self):
        row = self.labels(fixture(changes={21: (90., 91., 89., 90.)})).loc["e19"]
        self.assertEqual(row.exit_index, 21)
        self.assertEqual(row.exit_reason, "gap_stop")
        self.assertEqual(row.exit_reference, 90.)
        self.assertAlmostEqual(row.gross_R_reference, -3.)
        self.assertLess(row.net_R_stress, -3.)

    def test_changed_reference_exits_old_epoch_at_next_open(self):
        f = fixture(changes={21: (90., 91., 89., 90.)}, references={20: "X.A.203002"})
        row = self.labels(f).loc["e19"]
        self.assertEqual(row.reference_epoch, "X.A.203001")
        self.assertEqual(row.exit_reason, "liquidity_reference_changed")
        self.assertEqual(row.exit_index, 21)
        self.assertEqual(row.exit_reference, 90.)

    def test_known_earlier_lifecycle_exits_and_cancels_next_intent(self):
        f = fixture()
        f[3]["X.A.203001"]["maturity_date"] = f[0][21]
        frame = self.labels(f)
        self.assertEqual(frame.loc["e19", "exit_index"], 21)
        self.assertEqual(frame.loc["e19", "exit_reason"], "lifecycle_exit")
        self.assertEqual(frame.loc["e20", "label_history_ready20"], 1)
        self.assertEqual(frame.loc["e20", "participation_state"], "known_nonparticipation")
        self.assertEqual(frame.loc["e20", "cancel_reason"], "known_entry_ineligible_lifecycle")
        self.assertTrue(pd.isna(frame.loc["e20", "net_R_stress"]))

    def test_missing_held_bar_is_absorbing_unknown_even_after_later_stop(self):
        row = self.labels(fixture(missing=(21,), changes={22: (90., 91., 89., 90.)})).loc["e19"]
        self.assertEqual(row.filled, 1)
        self.assertEqual(row.label_state, "path_or_execution_unknown")
        self.assertEqual(row.unknown_index, 21)
        self.assertTrue(pd.isna(row.exit_index))
        self.assertTrue(pd.isna(row.label_known_date))
        self.assertTrue(pd.isna(row.net_R_base))
        self.assertTrue(pd.isna(row.policy_diagnostic_pnl))

    def test_terminal_open_and_last_intent_are_censored_not_artificially_closed(self):
        frame = self.labels(fixture(finish=21))
        self.assertEqual(frame.loc["e19", "label_state"], "open_right_censored")
        self.assertTrue(pd.isna(frame.loc["e19", "exit_reference"]))
        self.assertTrue(pd.isna(frame.loc["e19", "net_R_stress"]))
        self.assertEqual(frame.loc["e20", "label_state"], "intent_right_censored")
        self.assertEqual(frame.loc["e20", "label_history_ready20"], 1)
        # A report cutoff is not necessarily the end of the full known calendar.
        # If D exists there, an already-known expiry cancels without reading D.
        dates, records, panel, economics, market = fixture(finish=23)
        economics["X.A.203001"]["maturity_date"] = dates[21]
        short = (dates, records, panel.iloc[:21].copy(), economics, market)
        final = self.labels(short, scope_end=20).loc["e20"]
        self.assertEqual(final.participation_state, "known_nonparticipation")
        self.assertEqual(final.cancel_reason, "known_entry_ineligible_lifecycle")
        self.assertEqual(final.participation_known_date, dates[20])
        self.assertTrue(pd.isna(final.net_R_stress))

    def test_future_poison_cannot_change_earlier_completed_label(self):
        before = self.labels(fixture(changes={20: (102., 103., 98., 100.)})).loc["e19"]
        self.assertEqual(before.label_state, "closed_complete_bar_model")
        changes = {i: (10000., 10010., 9990., 10000.) for i in range(21, 42)}
        changes[20] = (102., 103., 98., 100.)
        after = self.labels(fixture(changes=changes)).loc["e19"]
        keys = ["N_u", "low20_u", "u_close", "label_history_ready20", "label_state", "entry_index",
                "exit_index", "exit_reference", "net_R_base", "net_R_stress", "label_known_date"]
        self.assertEqual(before[keys].to_dict(), after[keys].to_dict())

    def test_F_and_plain_keep_independent_economic_identity_without_family_occupancy(self):
        dates, records, panel, economics, _ = fixture(changes={20: (102., 103., 98., 100.)})
        extra = [dict(r, contract_epoch_id="X.A_F.203001") for r in records]
        panel_f = panel.assign(event_id=panel.event_id + "f", product_id="X.A_F", product="A_F", reference_epoch="X.A_F.203001")
        all_panel = pd.concat([panel, panel_f], ignore_index=True)
        economics["X.A_F.203001"] = dict(economics["X.A.203001"], contract_multiplier=5., round_lot=5.)
        market = m.ref.Market.from_records(records + extra, dates)
        frame = self.labels((dates, records + extra, all_panel, economics, market))
        self.assertEqual(frame.loc["e19", "family_id"], frame.loc["e19f", "family_id"])
        self.assertEqual(frame.loc["e19", "filled"], 1)
        self.assertEqual(frame.loc["e19f", "filled"], 1)
        self.assertEqual(frame.loc["e19f", "multiplier"], 5.)
        self.assertEqual(frame.loc["e19f", "round_lot"], 5.)
        self.assertAlmostEqual(frame.loc["e19f", "net_pnl_base_per_lot"], -19.1005)

    def test_history_ready_is_independent_of_unresolved_economics(self):
        f = fixture()
        f[3]["X.A.203001"] = dict(economics_status="unresolved_exact_epoch_metadata")
        row = self.labels(f).loc["e19"]
        self.assertEqual(row.label_history_ready20, 1)
        self.assertEqual(row.label_state, "input_or_economics_unresolved")
        self.assertTrue(pd.isna(row.net_R_stress))

    def test_output_refuses_overwrite_before_loading_any_native_input(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileExistsError):
                m.execute(SimpleNamespace(output=directory, protocol="must-not-open", protocol_sha256="unused"))


if __name__ == "__main__":
    unittest.main()
