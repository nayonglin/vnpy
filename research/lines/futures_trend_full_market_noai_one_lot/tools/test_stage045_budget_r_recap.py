"""Risk enrichment must retain plots and use actual accepted initial risk, not budget."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

import pandas as pd

HERE=Path(__file__).resolve().parent
ENTRY=HERE/'stage045_budget_r_recap.py'


class BudgetRRecapTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(ENTRY.exists(),'actual-risk R recap enricher is not implemented')
        spec=importlib.util.spec_from_file_location('budget_R_fixture',HERE/'test_stage044_validate_budget_artifacts.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        self.fixture=mod.BudgetArtifactsTest(methodName='runTest');self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.source=self.fixture.source;self.root=self.fixture.root
        self.parent=self.fixture.recap;self.output=self.root/'risk_enriched'
        import stage045_budget_r_recap
        self.module=stage045_budget_r_recap

    def test_actual_initial_risk_is_denominator_and_all_other_data_is_preserved(self):
        trades=pd.read_csv(self.source/'trades.csv');audit=pd.read_csv(self.source/'open_budget_audit.csv')
        for index,row in trades[trades.offset.eq('open')].iterrows():
            snap=json.loads(row.stage041_signal_snapshot);snap.update(target_risk_amount=100.,min_risk_per_trade=100.,max_risk_per_trade=100.)
            encoded=json.dumps(snap,sort_keys=True)
            trades.loc[index,'stage041_open_budget']=100.;trades.loc[index,'stage041_signal_snapshot']=encoded
            audit.loc[audit.trade_id.eq(row.trade_id),'opening_budget']=100.
            audit.loc[audit.trade_id.eq(row.trade_id),'signal_snapshot']=encoded
        trades['commission']=6.;trades['slippage']=4.
        trades.to_csv(self.source/'trades.csv',index=False);audit.to_csv(self.source/'open_budget_audit.csv',index=False)
        closed=pd.read_csv(self.source/'closed_episodes.csv');closed['cost']=20.;closed['net_pnl']=80.
        closed.to_csv(self.source/'closed_episodes.csv',index=False)
        self.fixture.rebuild();self.parent=self.fixture.recap
        before=json.loads((self.parent/'records.json').read_text())
        result=self.module.enrich(self.source,self.parent,self.output)
        after=json.loads((self.output/'records.json').read_text())
        self.assertEqual(after[0]['meta']['risk_amount'],20.)
        self.assertEqual(after[0]['meta']['r_multiple'],5.)
        self.assertEqual(self.module.non_r_payload_hash(before),self.module.non_r_payload_hash(after))
        masked_before=copy.deepcopy(before);masked_after=copy.deepcopy(after)
        for records in (masked_before,masked_after):
            for record in records:
                for key in ('risk_amount','r_multiple'):record['meta'].pop(key,None)
        self.assertEqual(masked_before,masked_after)
        for name in ('closed_lots.csv','all_trade_episodes.csv','chart_manifest.csv'):
            frame=pd.read_csv(self.output/name)
            self.assertEqual(frame.iloc[0]['risk_amount'],20.)
            self.assertEqual(frame.iloc[0]['r_multiple'],5.)
        self.assertNotIn('R不可获得时显示N/A',result['source_warning'])
        self.assertIn('实际接受的初始止损风险',result['source_warning'])
        self.assertIn('毛盈亏',result['source_warning'])
        self.assertIn('不重选',result['source_warning'])
        parent_summary=json.loads((self.parent/'summary.json').read_text())
        self.assertEqual(result['backtest_metrics'],parent_summary['backtest_metrics'])
        self.assertEqual(result['risk_enrichment']['non_r_payload_sha256_before'],result['risk_enrichment']['non_r_payload_sha256_after'])
        self.assertEqual(result['artifact_sha256']['records.json'],self.fixture.fixture.module.sha256(self.output/'records.json'))

    def test_exact_seventeen_digit_csv_budget_matches_json_authorization(self):
        target=32146.359636085206
        trades=pd.read_csv(self.source/'trades.csv',float_precision='round_trip')
        audit=pd.read_csv(self.source/'open_budget_audit.csv',float_precision='round_trip')
        for index,row in trades[trades.offset.eq('open')].iterrows():
            snapshot=json.loads(row.stage041_signal_snapshot)
            snapshot.update(target_risk_amount=target,min_risk_per_trade=target,max_risk_per_trade=target)
            encoded=json.dumps(snapshot,sort_keys=True)
            trades.loc[index,'stage041_open_budget']=target;trades.loc[index,'stage041_signal_snapshot']=encoded
            audit.loc[audit.trade_id.eq(row.trade_id),'opening_budget']=target
            audit.loc[audit.trade_id.eq(row.trade_id),'signal_snapshot']=encoded
        trades.to_csv(self.source/'trades.csv',index=False);audit.to_csv(self.source/'open_budget_audit.csv',index=False)
        self.fixture.rebuild();self.parent=self.fixture.recap
        result=self.module.enrich(self.source,self.parent,self.output)
        self.assertEqual(result['risk_enrichment']['enriched_complete_episodes'],1)
        self.assertEqual(json.loads((self.output/'records.json').read_text())[0]['meta']['r_multiple'],5.)

    def test_missing_actual_risk_is_rejected_instead_of_falling_back_to_budget(self):
        trades=pd.read_csv(self.source/'trades.csv');trades.loc[trades.trade_id.eq('o1'),'stage041_entry_risk']=None
        trades.to_csv(self.source/'trades.csv',index=False);self.fixture.rebuild();self.parent=self.fixture.recap
        with self.assertRaisesRegex(ValueError,'actual.*risk'):
            self.module.enrich(self.source,self.parent,self.output)
        self.assertFalse(self.output.exists())

    def test_tampered_parent_chart_cache_is_rejected(self):
        (self.parent/'records.json').write_text('[]')
        with self.assertRaisesRegex(ValueError,'parent.*hash'):
            self.module.enrich(self.source,self.parent,self.output)
        self.assertFalse(self.output.exists())

    def test_tampered_source_receipt_is_rejected(self):
        with (self.source/'trades.csv').open('a') as handle:handle.write('\n')
        with self.assertRaisesRegex(ValueError,'source.*hash'):
            self.module.enrich(self.source,self.parent,self.output)
        self.assertFalse(self.output.exists())

    def test_existing_or_nested_output_cannot_be_overwritten(self):
        with self.assertRaises(ValueError):self.module.enrich(self.source,self.parent,self.parent/'nested')
        self.output.mkdir();(self.output/'keep').write_text('keep')
        with self.assertRaises(FileExistsError):self.module.enrich(self.source,self.parent,self.output)
        self.assertEqual((self.output/'keep').read_text(),'keep')


if __name__=='__main__':unittest.main()
