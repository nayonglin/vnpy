"""Independent audit tests: no implementation import from 071/072."""
import importlib.util,unittest,json,shutil
from unittest.mock import patch
from pathlib import Path
import pandas as pd
HERE=Path(__file__).parent

class IndependentDisplayTest(unittest.TestCase):
    def setUp(self):
        path=HERE/'stage081_validate_fractional_display.py';self.assertTrue(path.exists(),'independent display validator missing')
        spec=importlib.util.spec_from_file_location('display081',path);self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)

    def test_quantity_cost_and_total_R_independent_partial_matching(self):
        rows=[('o', 'long','open',3,100,6,3),('c1','short','close',1,110,2,1),('c2','short','close',2,120,4,2),('r','long','open',4,100,8,4),('c3','short','close',1,95,2,1)]
        trades=pd.DataFrame([dict(trade_id=i,vt_symbol='x',direction=d,offset=o,volume=v,price=p,commission=c,slippage=s,date='2020-01-01',stage068_entry_risk=v*100 if o=='open' else None) for i,d,o,v,p,c,s in rows])
        result=self.m.match_entries(trades,{'x':10})
        e=result['complete']['o'];self.assertEqual(e['volume'],3);self.assertEqual(e['gross_pnl'],500);self.assertEqual(e['cost'],18);self.assertEqual(e['net_pnl'],482);self.assertEqual(e['r_multiple'],500/300)
        self.assertEqual(len(result['complete']),1);self.assertEqual(result['partial'][0]['net_pnl'],-56);self.assertEqual(result['remaining_entry_cost'],9)
        trades.loc[4,'volume']=5
        with self.assertRaisesRegex(ValueError,'close_quantity'):self.m.match_entries(trades,{'x':10})

    def test_exact_weekly_no_contract_mix_no_gap_compression(self):
        calendar=pd.DataFrame({'date':pd.bdate_range('2020-01-06',periods=30)})
        market=pd.DataFrame([dict(vt_symbol=v,date=d,open=p,high=p+1,low=p-1,close=p,volume=1,execution_only=False,quote_class='accepted_clean') for v in ('x1','x2') for n,d in enumerate(calendar.date) for p in ([100+n if v=='x1' else 200-n]) if not(v=='x1' and n==14)])
        contracts=pd.DataFrame([dict(vt_symbol=v,listed_date='2020-01-06') for v in ('x1','x2')]);tables=self.m.independent_weekly(market,contracts,calendar,{'x1','x2'})
        a,b=tables['x1'],tables['x2'];self.assertGreater(a.close.iloc[-1],a.close.iloc[0]);self.assertLess(b.close.iloc[-1],b.close.iloc[0]);self.assertTrue(pd.isna(a.close.iloc[2]));self.assertTrue(pd.isna(a.ma5.iloc[-1]));self.assertTrue(pd.notna(b.ma5.iloc[-1]));self.assertEqual(len(a),6)

    def test_complete_frozen_fixture_audit_checks_receipts_records_and_JS(self):
        spec=importlib.util.spec_from_file_location('fixture071audit',HERE/'test_stage071_fractional_recap.py');fmod=importlib.util.module_from_spec(spec);spec.loader.exec_module(fmod)
        f=fmod.FractionalRecapTest('runTest');f.setUp();self.addCleanup(f.doCleanups);source,oldparent,root=f.source_fixture()
        metrics=json.loads((source/'summary.json').read_text());metrics['performance_certifiable']=True;(source/'summary.json').write_text(json.dumps(metrics))
        manifest=json.loads((source/'manifest.json').read_text());manifest['run_id']=source.name;manifest['hashes']={p.name:self.m.sha(p) for p in source.iterdir() if p.name!='manifest.json'};(source/'manifest.json').write_text(json.dumps(manifest))
        baseline=root/'baseline';shutil.copytree(source,baseline);digest=self.m.sha(baseline/'manifest.json');manifest['baseline_run_manifest_sha256']=digest;(source/'manifest.json').write_text(json.dumps(manifest))
        from stage001_frozen_recap import render_bundle
        raw=root/'raw081';render_bundle(source,raw)
        fractional=root/'fractional081'
        with patch.object(f.mod,'BASELINE_SHA',digest):f.mod.enrich(source,raw,fractional)
        with patch.object(self.m,'BASELINE_SHA',digest):r=self.m.validate(source,baseline,raw=raw,fractional=fractional)
        self.assertEqual(r['complete_entries'],1);self.assertEqual(r['complete_contracts'],3);self.assertEqual(r['partial_segments'],1);self.assertEqual(r['residual_contracts'],3);self.assertGreater(r['artifacts']['fractional']['javascript_blocks'],0)
        (fractional/'records.json').write_text('[]')
        with patch.object(self.m,'BASELINE_SHA',digest):
            with self.assertRaisesRegex(ValueError,'artifact_hash'):self.m.validate(source,baseline,fractional=fractional)

    def test_protected_payload_detects_geometry_changes_only(self):
        a=[{'meta':{'open_trade_id':'o','risk_amount':None},'weekly':{'x':[1]},'daily':{'x':[2]}}];b=[{'meta':{'open_trade_id':'o','risk_amount':100},'weekly':{'x':[1]},'daily':{'x':[2]}}]
        self.assertEqual(self.m.protected(a,'risk'),self.m.protected(b,'risk'));b[0]['daily']['x']=[9]
        self.assertNotEqual(self.m.protected(a,'risk'),self.m.protected(b,'risk'))

if __name__=='__main__':unittest.main()
