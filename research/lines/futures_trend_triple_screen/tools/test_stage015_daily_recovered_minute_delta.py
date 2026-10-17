"""Recovered daily references may qualify only explicitly approved delta keys."""
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

try:
    import stage015_daily_recovered_minute_delta as module
except ImportError:
    module=None
import pandas as pd


class DailyMinuteDeltaTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(module,"Stage015 delta is not implemented")
        self.grid=pd.date_range("2020-05-18 09:00",periods=3,freq="min")
        self.rows=pd.DataFrame(dict(vt_symbol=["rb2010.SHFE"]*3,bar_datetime=self.grid,
            open=[10.,11.,12.],high=[12.,13.,14.],low=[9.,10.,11.],close=[11.,12.,13.],
            volume=[2.,3.,4.],open_oi=[20.,21.,22.],close_oi=[21.,22.,23.]))
        self.daily=dict(vt_symbol="rb2010.SHFE",trade_date="2020-05-18",open=10.,high=14.,low=9.,
            close=13.,volume=9.,open_oi=20.,close_oi=23.,source_bar_id=10,source_datetime_ns=100,
            successor_id=11,successor_datetime_ns=200)
        self.audit=pd.DataFrame([dict(vt_symbol="rb2010.SHFE",trade_date="2020-05-18",accepted=True,
            reason="completed_and_six_fields_matched",mismatch_fields="",database_closeOI="N/A_not_independently_available",
            source_bar_id=10,source_datetime_ns=100,successor_id=11,successor_datetime_ns=200)])
        self.review=dict(qualified_research_daily=True,p0_findings=0,p1_findings=0)

    def test_only_independently_qualified_target_rows_become_references(self):
        raw=pd.DataFrame([self.daily,{**self.daily,"trade_date":"2020-05-19"}])
        references=module.approved_references(raw,self.audit,self.review)
        self.assertEqual(set(references),{("rb2010.SHFE","2020-05-18")})
        rejected=self.audit.assign(accepted=False)
        self.assertEqual(module.approved_references(raw,rejected,self.review),{})
        with self.assertRaisesRegex(ValueError,"daily_independent_review_not_accepted"):
            module.approved_references(raw,self.audit,{**self.review,"qualified_research_daily":False})

    def test_missing_reference_leaves_session_unqualified(self):
        added,audit=module.qualify_delta_session("rb2010.SHFE","2020-05-18",{},
            {"local":self.rows},self.grid,self.rows.iloc[:0],"full_session")
        self.assertTrue(added.empty)
        self.assertEqual(audit["reason"],"independently_qualified_daily_target_missing")

    def test_recovered_reference_stitches_existing_minutes_without_overwriting(self):
        references={("rb2010.SHFE","2020-05-18"):self.daily}
        existing=self.rows.iloc[:1].copy()
        added,audit=module.qualify_delta_session("rb2010.SHFE","2020-05-18",references,
            {"local":self.rows.iloc[1:]},self.grid,existing,"anchor")
        self.assertEqual(list(added.close),[12.,13.])
        self.assertEqual(audit["status"],"accepted")
        changed=self.rows.copy();changed.loc[0,"close"]=10.5
        added,audit=module.qualify_delta_session("rb2010.SHFE","2020-05-18",references,
            {"local":changed},self.grid,existing,"full_session")
        self.assertTrue(added.empty)
        self.assertEqual(audit["reason"],"base_overlap_conflict")
        self.assertEqual(float(existing.iloc[0].close),11.)

    def test_existing_reader_keeps_only_exact_requested_keys_and_binds_bytes(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/"existing.csv"
            outside=self.rows.assign(vt_symbol="cu2010.SHFE")
            pd.concat([self.rows,outside]).to_csv(path,index=False)
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            relevant,manifest=module.stream_relevant_existing({path:digest},{"rb2010.SHFE":self.grid[:1]},chunksize=2)
            self.assertEqual(len(relevant),1)
            self.assertEqual(float(relevant.iloc[0].close),11.)
            self.assertEqual(manifest[0]["scanned_rows"],6)
            self.assertEqual(manifest[0]["retained_rows"],1)
            with self.assertRaisesRegex(ValueError,"existing_source_sha_changed"):
                module.stream_relevant_existing({path:"0"*64},{"rb2010.SHFE":self.grid[:1]},chunksize=2)


if __name__=="__main__":unittest.main()
