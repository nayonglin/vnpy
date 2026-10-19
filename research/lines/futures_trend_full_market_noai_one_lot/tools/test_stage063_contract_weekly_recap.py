"""Exact contract weekly plot: no cross-contract OHLC, missing-week compression or collateral changes."""
import copy,importlib.util,json,unittest
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).parent

def load(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class ContractWeeklyRecapTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue((HERE/'stage063_contract_weekly_recap.py').exists(),'exact contract weekly recap missing');self.mod=load('stage063_contract_weekly_recap')
        self.calendar=pd.DataFrame({'date':pd.bdate_range('2024-01-01',periods=45*5)})
        self.market=pd.concat([pd.DataFrame(dict(date=self.calendar.date,vt_symbol=vt,open=values,high=values+2,low=values-2,close=values+1,volume=10.,execution_only=False,quote_class='accepted_clean',allow_new_open=np.nan)) for vt,values in [('a202412.DCE',np.repeat(np.arange(1.,46.),5)+100),('a202503.DCE',np.repeat(np.arange(45.,0.,-1),5)+100)]],ignore_index=True)
        self.contracts=pd.DataFrame([dict(vt_symbol=vt,product_vt_symbol='a.DCE',listed_date='2024-01-01') for vt in self.market.vt_symbol.unique()])

    def tables(self):return self.mod.build_weekly_tables(self.market,self.contracts,self.calendar,set(self.market.vt_symbol))

    def test_opposite_contracts_use_their_own_full_history_and_exact_ohlcv(self):
        t=self.tables();a=t['a202412.DCE'];b=t['a202503.DCE']
        self.assertEqual(a.iloc[39].close,141.);self.assertEqual(b.iloc[39].close,107.)
        self.assertEqual(a.iloc[39].ma40,121.5);self.assertEqual(b.iloc[39].ma40,126.5)
        self.assertEqual((a.iloc[39].open,a.iloc[39].high,a.iloc[39].low,a.iloc[39].volume),(140.,142.,138.,50.))

    def test_bad_eow_remains_blank_and_does_not_compress_ma_window(self):
        bad=pd.Timestamp('2024-02-02');self.market.loc[self.market.vt_symbol.eq('a202412.DCE')&self.market.date.eq(bad),'execution_only']=True
        t=self.tables()['a202412.DCE'];self.assertTrue(pd.isna(t.iloc[4].close));self.assertTrue(pd.isna(t.iloc[4].open));self.assertTrue(pd.isna(t.iloc[39].ma40));self.assertTrue(pd.notna(t.iloc[44].ma40));self.assertEqual(len(t),45)

    def test_prelisting_and_missing_weeks_cannot_borrow_main_prices(self):
        self.contracts.loc[1,'listed_date']='2024-10-01';t=self.tables();labels=[str(p) for p in self.calendar.date.dt.to_period('W-FRI').unique()]
        old={'meta':{'vt_symbol':'a202503.DCE','entry_x':123,'signal':'short_case2'},'weekly':{'label':labels,'x':list(range(45)),'width':[.9]*45,'close':[99999]*45},'daily':{'close':[99999]},'monthly':{'close':[88888]},'intraday':{},'day30':{},'day10':{}}
        before=copy.deepcopy(old);self.mod.replace_weekly_records([old],t)
        self.assertIsNone(old['weekly']['close'][0]);self.assertIsNone(old['weekly']['ma40'][-1]);self.assertEqual(old['daily'],before['daily']);self.assertEqual(old['weekly']['x'],before['weekly']['x']);self.assertEqual(old['weekly']['width'],before['weekly']['width'])
        self.assertEqual(self.mod.non_weekly_payload_hash([old]),self.mod.non_weekly_payload_hash([before]))

    def test_allow_open_nan_keeps_clean_but_explicit_false_invalidates_eow(self):
        self.assertTrue(pd.notna(self.tables()['a202412.DCE'].iloc[39].close))
        self.market['allow_new_open']=self.market.allow_new_open.astype(object);self.market.loc[self.market.vt_symbol.eq('a202412.DCE')&self.market.date.eq('2024-10-04'),'allow_new_open']=False
        self.assertTrue(pd.isna(self.tables()['a202412.DCE'].iloc[39].close))

    def test_full_weekly_validation_rejects_any_changed_value(self):
        tables=self.tables();labels=tables['a202412.DCE'].week.tolist()
        records=[{'meta':{'vt_symbol':'a202412.DCE'},'weekly':{'label':labels,'x':list(range(45)),'width':[.9]*45}}]
        self.mod.replace_weekly_records(records,tables)
        report=self.mod.validate_weekly_records(records,tables)
        self.assertEqual(report['weekly_slots'],45);self.assertEqual(report['ohlcv_values_checked'],225);self.assertEqual(report['ma_values_checked'],180)
        records[0]['weekly']['high'][39]+=1
        with self.assertRaisesRegex(ValueError,'weekly_value'):self.mod.validate_weekly_records(records,tables)

    def test_full_frozen_enrichment_preserves_other_arrays_hash_and_inputs(self):
        fixture=load('test_stage001_frozen_recap').FrozenRecapTest('runTest');fixture.setUp();self.addCleanup(fixture.doCleanups)
        source=fixture.source;root=fixture.root;market=pd.read_csv(source/'market_daily.csv');market['execution_only']=False;market['quote_class']='accepted_clean';market.to_csv(source/'market_daily.csv',index=False)
        metadata=pd.read_csv(source/'contract_metadata.csv');metadata['product_vt_symbol']='rb.SHFE';metadata['listed_date']='2010-01-01';metadata.to_csv(source/'contract_metadata.csv',index=False)
        pd.DataFrame({'date':pd.bdate_range('2010-01-01','2021-01-31')}).to_csv(source/'trading_calendar.csv',index=False)
        (source/'closed_episodes.csv').write_text('episode_id,net_pnl\n1,100\n');(source/'residual_open_positions.json').write_text('[]')
        gate=self.mod.WeeklyContractTrend(market,metadata,pd.read_csv(source/'trading_calendar.csv'));gate.lookup('rb1901.SHFE','2020-12-31');gate.weekly.to_csv(source/'weekly_contract_features.csv',index=False)
        metrics=json.loads((source/'summary.json').read_text());metrics.update(long_weekly_filter=True,weekly_policy=dict(self.mod.WEEKLY_POLICY));(source/'summary.json').write_text(json.dumps(metrics));fixture.freeze()
        identity=json.loads((source/'manifest.json').read_text());identity.update(long_weekly_filter=True,weekly_policy=dict(self.mod.WEEKLY_POLICY));(source/'manifest.json').write_text(json.dumps(identity))
        parent=root/'parent';fixture.module.render_bundle(source,parent);before=json.loads((parent/'records.json').read_text());sourcehash=self.mod.sha256(source/'manifest.json');parenthash=self.mod.sha256(parent/'summary.json')
        out=root/'exact';r=self.mod.enrich(source,parent,out);after=json.loads((out/'records.json').read_text())
        self.assertEqual(self.mod.non_weekly_payload_hash(before),self.mod.non_weekly_payload_hash(after));self.assertEqual(self.mod.sha256(source/'manifest.json'),sourcehash);self.assertEqual(self.mod.sha256(parent/'summary.json'),parenthash)
        self.assertIn('stage058_weekly_contract.py',r['weekly_contract_enrichment']['dependency_sha256']);self.assertIn('stage062_contract_weekly_overview.py',r['weekly_contract_enrichment']['dependency_sha256']);self.assertEqual(r['weekly_contract_enrichment']['records'],1);self.assertTrue('交易合约自身' in r['source_warning'])
        for name in ('closed_lots.csv','all_trade_episodes.csv'):self.assertEqual((out/name).read_bytes(),(parent/name).read_bytes())
        with self.assertRaises(FileExistsError):self.mod.enrich(source,parent,out)
        (source/'trading_calendar.csv').write_text('tampered')
        with self.assertRaisesRegex(ValueError,'hash'):self.mod.enrich(source,parent,root/'tampered')

if __name__=='__main__':unittest.main()
