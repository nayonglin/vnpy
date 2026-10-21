"""Finite synthetic acceptance for the new 054 adapter/statistics, no actual run."""
import importlib.util
import hashlib
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


PATH = Path(__file__).with_name("stage054_maturity_cash_compare.py")


def module():
    if not PATH.exists():
        return None
    spec = importlib.util.spec_from_file_location("stage054_tested", PATH)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class CashAdapterAndStatistics(unittest.TestCase):
    def setUp(self):
        self.m = module()
        self.assertIsNotNone(self.m, "054 score/cash adapter must exist")

    def test_action_retains_all_rows_and_does_not_read_future_outcomes(self):
        labels = pd.DataFrame(dict(event_id=list("abcd"), product_id=["X.A"]*4,
            family_id=["X.A"]*4, u_date=["2019-12-31", "2020-01-02", "2020-01-03", "2020-01-06"],
            u_index=[1, 2, 3, 4], reference_epoch=["old", "old", "new", ""],
            label_history_ready20=[1, 1, 1, 0], N_u=[1.]*4, low20_u=[90.]*4,
            u_close=[100.]*4, history_run=[20]*4, lifecycle_index=[30]*4,
            label_state=["closed_complete_bar_model", "entry_execution_unknown", "known_nonparticipation", "not_history_ready"],
            net_R_stress=[5., np.nan, np.nan, np.nan], filled=[1, 0, 0, 0]))
        predictions = pd.DataFrame(dict(event_id=list("bcd"), product_id=["X.A"]*3,
            family_id=["X.A"]*3, u_date=labels.u_date.iloc[1:].tolist(), u_index=[2,3,4],
            scope=["main"]*3, arm=["ALIGNED"]*3, cutoff=["2020-01-01"]*3,
            score=[1., 2., 100.], selected=[1,1,0], history_ready20=[1,1,0]))
        signals = self.m.make_signals(labels, predictions, "ALIGNED")
        self.assertEqual(signals.event_id.tolist(), list("abcd"))
        self.assertEqual(signals.potential.tolist(), [0,1,1,0])
        self.assertEqual(signals.reference_epoch.tolist(), ["old","old","new",""])
        changed = labels.assign(label_state="open_right_censored", filled=0, net_R_stress=-999.)
        pd.testing.assert_frame_equal(signals, self.m.make_signals(changed, predictions, "ALIGNED"))
        self.assertTrue(np.isnan(signals.loc[0, "score"]))

    def test_first_2023_open_uses_existing_2022_score_but_2020_has_no_2019_prediction(self):
        for year in (2020, 2023):
            dates = pd.date_range(f"{year-1}-11-25", f"{year}-01-03", freq="D").strftime("%Y-%m-%d").tolist()
            start = int(np.searchsorted(dates, f"{year}-01-01"))
            epoch = "X.A.203001"
            records = [dict(contract_epoch_id=epoch, trade_date=d, open=100., high=102., low=99., close=101., volume=10., quality_status="accepted") for d in dates]
            market = self.m.ref.Market.from_records(records, dates)
            economics = {epoch: dict(economics_status="exact_epoch_metadata_snapshot", contract_multiplier=1., round_lot=1., tick_size=None,
                vendor_margin_rate=.2, listed_date="2010-01-01", nominal_month_first_date="2030-01-01")}
            labels = pd.DataFrame([dict(event_id=f"e{i}", product_id="X.A", family_id="X.A", u_date=d, u_index=i,
                reference_epoch=epoch, label_history_ready20=int(i>=19), N_u=3., low20_u=99., u_close=101., history_run=i+1, lifecycle_index=1000) for i,d in enumerate(dates)])
            eligible = labels.loc[labels.u_date.ge("2020-01-01")]
            pred = eligible[["event_id","product_id","family_id","u_date","u_index"]].assign(scope="main", arm="ALIGNED", cutoff="2020-01-01", score=1., selected=eligible.label_history_ready20.to_numpy(), history_ready20=eligible.label_history_ready20.to_numpy())
            signals = self.m.make_signals(labels, pred, "ALIGNED")
            book = self.m.ref.run_cash_account(signals, market, dates, economics, "base", "fixture", start, start)
            buys = [r for r in book["fills"] if r["side"]=="BUY"]
            self.assertEqual(len(buys), int(year==2023))
            if buys:
                self.assertEqual(buys[0]["date"], f"{year}-01-01")
                self.assertEqual(book["budgets"][0]["u_date"], f"{year-1}-12-31")
                self.assertTrue(book["budgets"][0]["pre_window_reservation"])

    def test_log_first_day_shared_circular_blocks_and_bankruptcy_fail_closed(self):
        daily = pd.DataFrame(dict(date=["2020-01-02","2020-01-03","2020-01-06"], equity=[110.,121.,133.1], ever_insolvent=[False]*3))
        logs, status = self.m.daily_log_growth(daily, 100.)
        self.assertEqual(status, "valid")
        np.testing.assert_allclose(logs, np.log(1.1))
        indices = self.m.circular_indices(3, 4, 2, 7)
        self.assertEqual(indices.shape, (4,3))
        self.assertTrue(np.all((indices[:,1]-indices[:,0])%3==1))
        result, distribution = self.m.paired_log_statistics(dict(ALIGNED=daily, SHUFFLED=daily.assign(equity=[100.,100.,100.]), COMMON=daily.assign(equity=[100.,100.,100.])), 100., indices)
        np.testing.assert_allclose(distribution.ALIGNED_minus_SHUFFLED, distribution.ALIGNED_minus_COMMON)
        self.assertAlmostEqual(result["ALIGNED_minus_COMMON"]["mean_daily_log_difference"], np.log(1.1))
        broken = daily.assign(equity=[110.,-1.,120.])
        logs, status = self.m.daily_log_growth(broken, 100.)
        self.assertIsNone(logs)
        self.assertEqual(status, "survival_failure_no_log_repair")
        result, distribution = self.m.paired_log_statistics(dict(ALIGNED=broken, SHUFFLED=daily, COMMON=daily), 100., indices)
        self.assertIsNone(result["ALIGNED_minus_COMMON"]["ci95_low"])
        self.assertTrue(distribution.ALIGNED_minus_COMMON.isna().all())

    def test_held_condition_uses_identified_common_domain_cancel_zero_unknown_excluded(self):
        labels = pd.DataFrame(dict(event_id=list("abcde"), label_state=["closed_complete_bar_model","known_nonparticipation","entry_execution_unknown","open_right_censored","closed_complete_bar_model"],
            participation_state=["filled","known_nonparticipation","unknown","filled","filled"], net_R_stress=[2.,np.nan,np.nan,np.nan,-2.]))
        rows=[]
        for arm in ("COMMON","ALIGNED","SHUFFLED"):
            for i,event in enumerate("abcde"):
                selected = int(arm=="ALIGNED" and event in "abcd")
                rows.append(dict(event_id=event, product_id="X.A", family_id="X.A", u_date="2020-01-02" if i<4 else "2020-01-03", u_index=10+i,
                    scope="holdout_0", arm=arm, score=1. if selected else -1., selected=selected, history_ready20=1))
        report, daily, linkage = self.m.held_diagnostics(pd.DataFrame(rows), labels)
        group = report["groups"]["holdout_0"]
        self.assertEqual(group["identified_common_events"],3)
        self.assertAlmostEqual(group["ALIGNED_minus_SHUFFLED_daily_equal_mean_R"], .5)
        self.assertEqual(group["arms"]["ALIGNED"]["selected_unknown_or_open"],2)
        self.assertEqual(group["arms"]["ALIGNED"]["selected_known_nonparticipation"],1)
        self.assertEqual(len(linkage),15)
        self.assertFalse(linkage.loc[linkage.event_id.isin(list("cd")),"identified_domain"].any())
        self.assertEqual(group["status"],"unknown")

    def test_held_scope_preserves_two_groups_and_rejects_combined_or_wrong_family_group(self):
        self.assertTrue(callable(getattr(self.m,"validate_held_groups",None)),"held file must preserve the two original scopes")
        families=["X.A","X.B","X.C","X.D"]
        expected=["holdout_"+str(int(hashlib.sha256(v.encode()).hexdigest(),16)%2) for v in families]
        frame=pd.DataFrame(dict(family_id=families,scope=expected))
        preserved=self.m.validate_held_groups(frame)
        pd.testing.assert_frame_equal(preserved,frame)
        with self.assertRaises(ValueError):
            self.m.validate_held_groups(frame.assign(scope="holdout_combined"))
        with self.assertRaises(ValueError):
            self.m.validate_held_groups(frame.assign(scope=list(reversed(expected))))

    def test_family_year_attribution_reconciles_continuous_equity_and_entry_exit_fees(self):
        ledger=self.m.ref.CashLedger(1000.)
        root=dict(root_id="r",event_id="e",family_id="X.A",product_id="X.A",epoch="X.A.203001",entry_date="2020-12-31",multiplier=10.,risk_per_lot=20.,margin_rate=.2,round_lot=1)
        ledger.enter(root,1,100.,101.,2.,10.)
        ledger.mark("r",110.,False)
        daily=[dict(date="2020-12-31",ever_insolvent=False,**ledger.totals())]
        positions=[dict(date="2020-12-31",family_id="X.A",unrealized=90.)]
        ledger.exit("r",1,110.,109.,3.,10.,"2021-01-04","stop_boundary")
        daily.append(dict(date="2021-01-04",ever_insolvent=False,**ledger.totals()))
        report,family_year=self.m.cash_diagnostics(dict(daily=daily,fills=ledger.fills,position_days=positions),1000.)
        self.assertAlmostEqual(family_year.net_equity_contribution.sum(),75.)
        self.assertAlmostEqual(family_year.fee.sum(),5.)
        self.assertEqual(report["attribution_max_abs_error"],0.)
        self.assertEqual(report["annual_slices"][1]["starting_equity"],1088.)
        self.assertFalse(report["annual_slices"][1]["independent_cold_start"])


if __name__ == "__main__":
    unittest.main()
