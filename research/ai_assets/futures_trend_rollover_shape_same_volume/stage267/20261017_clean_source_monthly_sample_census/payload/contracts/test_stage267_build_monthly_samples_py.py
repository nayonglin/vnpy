"""Boundary acceptance for sample counting; no source replay or model fit."""
from functools import lru_cache
from pathlib import Path
import csv
import json
import tempfile
import unittest

import numpy as np
import pandas as pd

try:
    import stage267_build_monthly_samples as builder
except ModuleNotFoundError:
    builder = None


@lru_cache(maxsize=1)
def fixture():
    dates = pd.bdate_range("2019-01-01", periods=260)
    products = builder.FIXED_PRODUCTS
    grid = pd.MultiIndex.from_product([dates, products], names=["date", "product_vt_symbol"]).to_frame(index=False)
    original = builder.load_original()
    sums = ["net_pnl", "slippage", "turnover", "trade_count", "abs_pos_change", "active_contract_count", "candidate_count", "opened_count", "selected_volume_sum", "selected_volume_ungated_sum", "corr_gate_enabled_count", "volume_tilt_applied_count"]
    means = ["avg_corr_gate_weight", "avg_same_direction_active_count", "avg_same_direction_max_corr", "avg_pairwise_score", "best_pairwise_rank", "avg_volume_tilt_multiplier", "avg_volume_tilt_score_gap", "avg_volume_tilt_top_gap", "avg_active_positions_before", "breakout_rate", "bullish_alignment_rate", "bearish_alignment_rate", "avg_rsi", "avg_loss_streak"]
    for col in sums + means:
        grid[col] = 1.0
    grid["net_pnl"] = grid.product_vt_symbol.map({p: float(i+1) for i, p in enumerate(products)})
    featured = original.add_rolling_features(grid)
    coverage = grid[["date", "product_vt_symbol"]].assign(observed=True, mapped=True)
    calendar = pd.bdate_range("2019-01-01", "2020-03-31")
    return featured, coverage, calendar, dates[-1]


class MonthlyContractTests(unittest.TestCase):
    def run_build(self, *, featured=None, coverage=None, calendar=None, source_end=None):
        self.assertIsNotNone(builder, "Stage267 strict monthly sample builder must exist")
        self.assertTrue(callable(getattr(builder, "construct_samples", None)), "strict contract must exist")
        f, c, cal, end = fixture()
        return builder.construct_samples(f if featured is None else featured, c if coverage is None else coverage,
                                         cal if calendar is None else calendar, source_end=end if source_end is None else source_end)

    def test_original_108_columns_are_frozen_unchanged(self):
        result = self.run_build()
        self.assertEqual(len(result["feature_columns"]), 108)
        self.assertEqual(result["feature_columns"], builder.frozen_features())
        self.assertFalse(any(c.startswith("future_") for c in result["feature_columns"]))

    def test_full_120_days_and_next_60_source_dates(self):
        result = self.run_build()
        row = result["qualified_samples"].iloc[0]
        self.assertEqual(row.feature_observed_days, 120)
        self.assertEqual(row.label_observed_days, 60)
        self.assertLess(row.feature_start, row.eval_date)
        self.assertGreater(row.label_start, row.eval_date)
        self.assertEqual(row.label_end, fixture()[2][fixture()[2].get_loc(row.eval_date)+60])

    def test_evaluation_is_authoritative_calendar_month_end_not_partial_last_date(self):
        result = self.run_build(source_end=pd.Timestamp("2019-10-16"))
        self.assertNotIn(pd.Timestamp("2019-10-16"), set(result["all_samples"].eval_date))
        self.assertLessEqual(result["all_samples"].eval_date.max(), pd.Timestamp("2019-09-30"))

    def test_59_future_rows_never_pass_original_partial_label(self):
        result = self.run_build()
        row = result["all_samples"].loc[result["all_samples"].label_calendar_days.between(30,59)].iloc[0]
        self.assertFalse(row.label_complete)
        self.assertFalse(row.eligible)
        self.assertTrue(pd.isna(row.future_net_pnl_60d))
        self.assertTrue(np.isfinite(row.legacy_partial_future_net_pnl_60d))

    def test_missing_history_observation_is_not_zero_pnl_coverage(self):
        self.run_build()
        f,c,cal,end = fixture()
        evaluation = pd.Timestamp("2019-07-31")
        product = builder.FIXED_PRODUCTS[0]
        c = c.copy(); c.loc[c.date.eq(evaluation) & c.product_vt_symbol.eq(product), "observed"] = False
        result = self.run_build(coverage=c)
        row = result["all_samples"].loc[lambda x: x.eval_date.eq(evaluation) & x.product_vt_symbol.eq(product)].iloc[0]
        self.assertFalse(row.feature_coverage_ok)
        self.assertFalse(row.eligible)

    def test_missing_future_mapping_invalidates_label_without_filling(self):
        self.run_build()
        _,c,cal,_ = fixture(); c=c.copy()
        evaluation=pd.Timestamp("2019-07-31");product=builder.FIXED_PRODUCTS[0]
        c.loc[c.date.eq(cal[cal.get_loc(evaluation)+1]) & c.product_vt_symbol.eq(product), "mapped"] = False
        result=self.run_build(coverage=c)
        row=result["all_samples"].loc[lambda x:x.eval_date.eq(evaluation)&x.product_vt_symbol.eq(product)].iloc[0]
        self.assertFalse(row.label_coverage_ok)
        self.assertTrue(pd.isna(row.future_net_pnl_60d))

    def test_cross_section_is_recounted_after_product_eligibility(self):
        self.run_build();_,c,_,_=fixture();c=c.copy()
        c.loc[c.product_vt_symbol.isin(builder.FIXED_PRODUCTS[:11]),"mapped"]=False
        result=self.run_build(coverage=c)
        self.assertTrue(result["qualified_samples"].empty)
        self.assertEqual(result["all_samples"].loc[lambda x:x.history_ok & x.label_complete,"eligible_cross_section_count"].max(),7)

    def test_zero_future_months_counted_but_not_informative(self):
        self.run_build();f,c,cal,end=fixture();f=f.copy();f["net_pnl"]=0.0
        result=self.run_build(featured=f)
        self.assertGreater(len(result["qualified_samples"]),0)
        self.assertTrue(result["informative_samples"].empty)
        self.assertTrue(result["qualified_samples"].all_future_pnl_zero.all())
        self.assertTrue(result["qualified_samples"].target_future_top_half_60d.isna().all())

    def test_constant_nonzero_future_has_no_ordering(self):
        self.run_build();f,_,_,_=fixture();f=f.copy();f["net_pnl"]=1.0
        result=self.run_build(featured=f)
        self.assertFalse(result["qualified_samples"].all_future_pnl_zero.any())
        self.assertTrue(result["informative_samples"].empty)
        self.assertTrue(result["qualified_samples"].constant_future_pnl.all())

    def test_label_sum_excludes_eval_and_61st_future_day(self):
        self.run_build();f,c,cal,end=fixture();f=f.copy();evaluation=pd.Timestamp("2019-07-31");product=builder.FIXED_PRODUCTS[0]
        f.loc[f.product_vt_symbol.eq(product),"net_pnl"]=0.0
        for shift,value in ((0,10000),(1,1),(60,60),(61,100000)):
            f.loc[f.product_vt_symbol.eq(product)&f.date.eq(cal[cal.get_loc(evaluation)+shift]),"net_pnl"]=value
        result=self.run_build(featured=f)
        row=result["qualified_samples"].loc[lambda x:x.eval_date.eq(evaluation)&x.product_vt_symbol.eq(product)].iloc[0]
        self.assertEqual(row.future_net_pnl_60d,61.0)

    def test_no_open_oi_field_is_required(self):
        result=self.run_build()
        self.assertGreater(len(result["informative_samples"]),0)
        self.assertNotIn("open_oi",fixture()[0])

    def test_duplicate_coverage_rejected(self):
        self.run_build();_,c,_,_=fixture()
        with self.assertRaisesRegex(ValueError,"duplicate"):
            self.run_build(coverage=pd.concat([c,c.iloc[:1]],ignore_index=True))

    def test_string_false_is_not_truthy(self):
        self.assertIsNotNone(builder,"Stage267 builder must exist")
        self.assertEqual(builder.explicit_booleans(pd.Series(["False","True","0","1"])).tolist(),[False,True,False,True])
        with self.assertRaises(ValueError):builder.explicit_booleans(pd.Series(["yes"]))

    def test_calendar_duplicate_or_unsorted_rejected(self):
        self.run_build();_,_,cal,_=fixture()
        for bad in (cal.append(cal[-1:]),cal[::-1]):
            with self.assertRaisesRegex(ValueError,"calendar"):
                self.run_build(calendar=bad)

    def test_fixed_pool_cannot_silently_expand(self):
        self.run_build();f,c,cal,end=fixture();f=f.copy();f.loc[f.product_vt_symbol.eq(builder.FIXED_PRODUCTS[0]),"product_vt_symbol"]="a.DCE"
        with self.assertRaisesRegex(ValueError,"18|pool|product"):
            self.run_build(featured=f)

    def test_comparison_is_exact_product_month_key_difference(self):
        result=self.run_build();current=result["informative_samples"]
        baseline=current.iloc[:-1][["eval_date","product_vt_symbol"]]
        delta=builder.compare_baseline(current,baseline)
        self.assertEqual(delta["new_rows"],1)
        self.assertEqual(delta["lost_rows"],0)

    def test_future_changes_cannot_change_eval_108_features(self):
        result=self.run_build();f,c,cal,end=fixture();evaluation=pd.Timestamp("2019-07-31")
        changed=f.copy();changed.loc[changed.date>evaluation,"net_pnl"]+=999999
        changed=builder.load_original().add_rolling_features(changed)
        rebuilt=self.run_build(featured=changed)
        a=result["all_samples"].loc[lambda x:x.eval_date.eq(evaluation),result["feature_columns"]].reset_index(drop=True)
        b=rebuilt["all_samples"].loc[lambda x:x.eval_date.eq(evaluation),result["feature_columns"]].reset_index(drop=True)
        pd.testing.assert_frame_equal(a,b)

    def write_file_fixture(self,folder):
        dates=pd.bdate_range("2019-01-01",periods=260)
        rows=[]
        for day in dates:
            for i,product in enumerate(builder.FIXED_PRODUCTS):
                prod,ex=product.split(".")
                rows.append(dict(date=str(day.date()),vt_symbol=f"{prod}2001.{ex}",start_pos=0,end_pos=0,pos_change=0,
                                 trade_count=0,turnover=0,commission=0,slippage=0,holding_pnl=0,trading_pnl=i+1,total_pnl=i+1,net_pnl=i+1))
        pd.DataFrame(rows).to_csv(folder/"positions.csv",index=False)
        pd.DataFrame(columns=["date","product_vt_symbol","candidate_status"]).to_csv(folder/"entries.csv",index=False)
        coverage=pd.MultiIndex.from_product([dates,builder.FIXED_PRODUCTS],names=["date","product_vt_symbol"]).to_frame(index=False).assign(observed=True,mapped=True)
        coverage.to_csv(folder/"coverage.csv",index=False)
        pd.DataFrame({"date":pd.bdate_range("2019-01-01","2020-03-31")}).to_csv(folder/"calendar.csv",index=False)
        pd.DataFrame(columns=["eval_date","product_vt_symbol"]).to_csv(folder/"baseline.csv",index=False)
        return ["--positions",str(folder/"positions.csv"),"--entries",str(folder/"entries.csv"),"--coverage",str(folder/"coverage.csv"),
                "--calendar",str(folder/"calendar.csv"),"--baseline-samples",str(folder/"baseline.csv"),"--output-dir",str(folder/"out")]

    def test_file_entry_accepts_true_no_candidate_source_without_synthetic_events(self):
        self.assertIsNotNone(builder,"Stage267 builder must exist")
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);argv=self.write_file_fixture(folder)
            self.assertEqual(builder.main(argv),0)
            summary=json.loads((folder/"out/sample_summary.json").read_text())
            self.assertEqual(summary["model_fits"],0)
            self.assertEqual(summary["feature_count"],108)
            self.assertGreater(summary["informative"]["rows"],0)
            self.assertIn("same_source_history_split",summary)
            self.assertEqual(summary["same_source_history_split"]["informative"]["eval_pre2020"]["rows"],summary["informative"]["rows"])
            self.assertEqual(summary["same_source_history_split"]["informative"]["eval_2020_plus"]["rows"],0)
            all_rows=pd.read_csv(folder/"out/all_sample_contract.csv")
            self.assertTrue(all_rows.candidate_count_sum_120d.eq(0).all())
            self.assertTrue(all_rows.opened_count_sum_120d.eq(0).all())

    def test_file_source_does_not_default_missing_economic_column_to_zero(self):
        self.assertIsNotNone(builder,"Stage267 builder must exist")
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);argv=self.write_file_fixture(folder)
            frame=pd.read_csv(folder/"positions.csv").drop(columns="turnover");frame.to_csv(folder/"positions.csv",index=False)
            with self.assertRaisesRegex(ValueError,"turnover|required|schema"):
                builder.main(argv)

    def test_file_duplicate_contract_pnl_is_not_double_counted(self):
        self.assertIsNotNone(builder,"Stage267 builder must exist")
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);argv=self.write_file_fixture(folder)
            frame=pd.read_csv(folder/"positions.csv");pd.concat([frame,frame.iloc[:1]]).to_csv(folder/"positions.csv",index=False)
            with self.assertRaisesRegex(ValueError,"duplicate"):
                builder.main(argv)


if __name__=="__main__":unittest.main()
