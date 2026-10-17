"""Small source-level correction and scoped-loader contracts; no real build."""
from types import SimpleNamespace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd

try:import stage016_source859_qualification as module
except ImportError:module=None


class SourceQualificationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(module,'Stage016 not implemented')
        self.times=pd.date_range('2022-04-06 09:00',periods=3,freq='min')
        rows=[dict(vt_symbol='AP210.CZCE',bar_datetime=t,open=10.,high=11.,low=9.,close=10.,volume=1.,open_oi=100.,close_oi=101.)for t in self.times]
        self.reference=pd.DataFrame(rows)
        self.existing=self.reference.iloc[:2].copy()
        self.existing['minute_source']=['stage859_tqsdk_backtest','verified_other']
        self.existing.loc[0,'high']=10.
        self.allowed={(r.vt_symbol,r.bar_datetime)for r in self.reference.itertuples()}

    def prepare(self,reference=None,existing=None):
        return module.prepare_delta(self.existing if existing is None else existing,
            self.reference if reference is None else reference,self.allowed,'completed_test','sha_test')

    def test_only_actual_859_differences_corrected_and_missing_keys_appended(self):
        corrections,added=self.prepare()
        self.assertEqual(len(corrections),1);self.assertEqual(len(added),1)
        self.assertEqual(corrections.iloc[0]['old_high'],10.)
        merged=module.apply_delta(self.existing,corrections,added,self.allowed)
        self.assertEqual(len(merged),3);self.assertEqual(merged.loc[0,'high'],11.)
        self.assertEqual(merged.loc[1,'minute_source'],'verified_other')
        self.assertTrue(merged.bar_date.eq(merged.bar_datetime.dt.normalize()).all())

    def test_non859_or_open_openoi_changes_refuse_entire_delta(self):
        for index,field in [(1,'high'),(0,'open'),(0,'open_oi')]:
            with self.subTest(index=index,field=field):
                reference=self.reference.copy();reference.loc[index,field]+=1
                with self.assertRaises(ValueError):self.prepare(reference=reference)

    def test_old_values_and_source_are_runtime_preconditions(self):
        corrections,added=self.prepare()
        for field,value in [('close',9.5),('minute_source','other_source')]:
            changed=self.existing.copy();changed.loc[0,field]=value
            with self.assertRaisesRegex(ValueError,'old_value_or_source_changed'):
                module.apply_delta(changed,corrections,added,self.allowed)

    def test_replacements_are_included_in_A0_disjointness(self):
        corrections,added=self.prepare()
        used={('AP210.CZCE',self.times[0])}
        result=module.changed_key_intersection(corrections,added,used)
        self.assertEqual(result['intersection_count'],1)
        self.assertEqual(result['changed_keys'],2)

    def test_loader_requires_qualification_and_restores_loader_and_caches_on_error(self):
        corrections,added=self.prepare()
        original=lambda symbols:self.existing.copy()
        engine=SimpleNamespace(_load_stage861_full_minute_bars=original,
            _FULL_MINUTE_BY_SYMBOL_CACHE='cache',_FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS={'old'},_LAST_MINUTE_AUDIT='audit')
        qualified=module.QualifiedDelta(corrections,added,self.allowed,review_accepted=True,all_four_sessions_qualified=True)
        with self.assertRaisesRegex(RuntimeError,'probe_failure'):
            with module.temporary_qualified_minute_delta(engine,qualified):
                merged=engine._load_stage861_full_minute_bars(['AP210.CZCE'])
                self.assertEqual(len(merged),3)
                raise RuntimeError('probe_failure')
        self.assertIs(engine._load_stage861_full_minute_bars,original)
        self.assertEqual(engine._FULL_MINUTE_BY_SYMBOL_CACHE,'cache')
        self.assertEqual(engine._FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS,{'old'})
        self.assertEqual(engine._LAST_MINUTE_AUDIT,'audit')
        unqualified=module.QualifiedDelta(corrections,added,self.allowed,review_accepted=False,all_four_sessions_qualified=False)
        with self.assertRaisesRegex(ValueError,'full_session_qualification_missing'):
            with module.temporary_qualified_minute_delta(engine,unqualified):pass

    def test_stage018_actual_qualification_contract(self):
        with tempfile.TemporaryDirectory()as temporary:
            source=Path(temporary)/'stage018';folder=source/'network_attempt1';folder.mkdir(parents=True)
            receipt=Path(temporary)/'review_receipt.json'
            grid=pd.date_range('2022-04-06 09:00',periods=225,freq='min')
            raw=pd.DataFrame([dict(vt_symbol='AP210.CZCE',bar_datetime=stamp,
                **{field:1. for field in module.old.VALUES})for stamp in grid])
            raw.to_csv(folder/'raw_completed_minutes.csv',index=False)
            pd.DataFrame([dict(vt_symbol='AP210.CZCE',bar_datetime=stamp,successor_time=stamp+pd.Timedelta(minutes=1),
                method='observed_later_serial_kline',completed=True)for stamp in grid]).to_csv(folder/'completion_evidence.csv',index=False)
            module.old.write_json(folder/'quality.json',dict(sessions=[dict(vt_symbol='AP210.CZCE',
                execution_trade_date='2022-04-06',accepted=True,completion_evidence_complete=True)]))
            module.old.write_json(folder/'parent_receipt.json',dict(exit_code=0,all_inputs_unchanged=True))
            module.old.write_json(folder/'worker_receipt.json',dict(provider_attempts=1))
            review=dict(p0_findings=0,p1_findings=0,qualified_precise_sessions=39,
                qualified_research_data=True,required_AP210_accepted=True,
                source_fingerprints={str(path):module.old.sha256(path)for path in folder.iterdir()})
            with patch.object(module,'S018',source),patch.object(module,'R018',receipt):
                for missing_flag in ['required_AP210_accepted','qualified_research_data']:
                    module.old.write_json(receipt,{**review,missing_flag:False})
                    with self.assertRaisesRegex(ValueError,'AP210_independent_full_session_qualification_missing'):
                        module.reviewed_ap_reference(module.old.sha256(receipt),grid,{})
                module.old.write_json(receipt,review)
                accepted,digest=module.reviewed_ap_reference(module.old.sha256(receipt),grid,{})
                self.assertEqual(len(accepted),225)
                self.assertEqual(digest,review['source_fingerprints'][str(folder/'raw_completed_minutes.csv')])


if __name__=='__main__':unittest.main()
