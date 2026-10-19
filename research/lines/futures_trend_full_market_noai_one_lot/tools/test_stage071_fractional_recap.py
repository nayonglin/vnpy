"""Normalized multi-lot financial display contracts; actual receipt parser awaits 068/070."""
import importlib.util
import json
import tempfile
from pathlib import Path
import unittest
import pandas as pd
from stage001_frozen_recap import load_display_functions
HERE=Path(__file__).parent

class FractionalRecapTest(unittest.TestCase):
    def setUp(self):
        entry=HERE/'stage071_fractional_recap.py';self.assertTrue(entry.exists(),'fractional multi-lot display adapter missing')
        spec=importlib.util.spec_from_file_location('stage071_fixture',entry);self.mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.mod)
        self.renderer=load_display_functions({'x202612.DCE':'x.DCE'})
        self.trades=pd.DataFrame([
            ['o1','2024-01-02','long','open',3,100,6,3],
            ['c1','2024-01-03','short','close',1,110,2,1],
            ['c2','2024-01-04','short','close',2,120,4,2],
            ['o2','2024-01-05','long','open',4,100,8,4],
            ['c3','2024-01-08','short','close',1,95,2,1],
        ],columns=['trade_id','date','direction','offset','volume','price','commission','slippage'])
        self.trades['vt_symbol']='x202612.DCE';self.trades['datetime']=self.trades.date+' 09:00:00'
        self.closed=self.renderer._closed_lots_from_trade_ledger(self.trades,sizes={'x202612.DCE':10},allow_residual_open=True)
        self.receipts={'o1':dict(filled_volume=3,risk_per_lot=100.,initial_risk_total=300.),'o2':dict(filled_volume=4,risk_per_lot=100.,initial_risk_total=400.)}

    def test_three_lot_partial_exits_count_one_complete_episode_with_total_risk(self):
        closed=self.mod.attribute_closed_lots(self.trades,self.closed,self.receipts)
        complete,partial=self.mod.complete_entry_episodes(self.trades,closed)
        self.assertEqual(len(complete),1);row=complete.iloc[0]
        self.assertEqual(row.open_trade_id,'o1');self.assertEqual(row.volume,3);self.assertEqual(row.lot_count,2)
        self.assertEqual(row.realized_pnl,500);self.assertEqual(row.risk_amount,300);self.assertAlmostEqual(row.r_multiple,500/300)
        self.assertAlmostEqual(row.weighted_exit_price,350/3);self.assertEqual(row.cost,18);self.assertEqual(row.net_pnl,482)
        self.assertEqual(partial.open_trade_id.tolist(),['o2']);self.assertEqual(partial.iloc[0].volume,1);self.assertEqual(partial.iloc[0].cost,6)

    def test_entry_risk_and_both_fill_costs_are_allocated_once_by_matched_volume(self):
        closed=self.mod.attribute_closed_lots(self.trades,self.closed,self.receipts)
        self.assertEqual(closed.risk_amount.tolist(),[100,200,100]);self.assertEqual(closed.cost.tolist(),[6,12,6])
        self.assertEqual(closed.net_pnl.tolist(),[94,388,-56]);self.assertEqual(closed.cost.sum(),24)
        # Remaining 3 lots carry 9 entry-cost allocation; all 33 cash costs were already charged by the account.
        self.assertEqual((self.trades.commission+self.trades.slippage).sum(),closed.cost.sum()+9)

    def test_receipt_volume_and_total_risk_cannot_fall_back_to_one_lot(self):
        self.receipts['o1']['initial_risk_total']=100
        with self.assertRaisesRegex(ValueError,'risk'):self.mod.attribute_closed_lots(self.trades,self.closed,self.receipts)
        self.receipts['o1']['initial_risk_total']=300;self.receipts['o1']['filled_volume']=1
        with self.assertRaisesRegex(ValueError,'volume'):self.mod.attribute_closed_lots(self.trades,self.closed,self.receipts)


    def source_fixture(self):
        spec=importlib.util.spec_from_file_location('raw071fixture',HERE/'test_stage001_frozen_recap.py');fmod=importlib.util.module_from_spec(spec);spec.loader.exec_module(fmod)
        fixture=fmod.FrozenRecapTest('runTest');fixture.setUp();self.addCleanup(fixture.doCleanups);source=fixture.source
        trades=self.trades.copy();trades['date']=trades.date.str.replace('2024','2018');trades['datetime']=trades.date+' 09:00:00';trades['vt_symbol']='rb1901.SHFE';trades['signal']=trades.offset.map({'open':'long_case2','close':''})
        trades['stage068_entry_risk']=float('nan');trades['stage068_risk_per_contract']=float('nan');trades['stage068_open_budget']=float('nan');trades['stage068_signal_snapshot']='{}';audit=[]
        for i,r in trades[trades.offset.eq('open')].iterrows():
            receipt=dict(snapshot_id=r.trade_id,contract_vt_symbol=r.vt_symbol,product_vt_symbol='rb.SHFE',direction='long',signal='long_case2',signal_datetime=r.datetime,entry_context='flat_entry',signal_equity=1000000.,risk_fraction=.005,target_risk_amount=5000.,risk_per_contract=100.,stop_price=90.,authorized_volume=int(r.volume))
            encoded=json.dumps(receipt);trades.loc[i,'stage068_entry_risk']=100*r.volume;trades.loc[i,'stage068_risk_per_contract']=100;trades.loc[i,'stage068_open_budget']=5000;trades.loc[i,'stage068_signal_snapshot']=encoded
            audit.append(dict(trade_id=r.trade_id,filled=True,signal_snapshot=encoded,opening_equity=1000000.,opening_budget=5000.,risk_per_contract=100.,total_risk=100*r.volume,max_affordable_volume=50,volume=r.volume))
        trades.to_csv(source/'trades.csv',index=False);pd.DataFrame(audit).to_csv(source/'open_budget_audit.csv',index=False)
        metadata=pd.read_csv(source/'contract_metadata.csv');metadata['product']='rb';metadata['product_vt_symbol']='rb.SHFE';metadata['pricetick']=1;metadata.to_csv(source/'contract_metadata.csv',index=False)
        pd.DataFrame([dict(open_trade_id='o1',entry_trade_id='o1',close_trade_ids='["c1","c2"]',volume=3,gross_pnl=500,cost=18,net_pnl=482,exit_price=350/3)]).to_csv(source/'closed_episodes.csv',index=False)
        pd.DataFrame([dict(open_trade_id='o2',exit_trade_id='c3',volume=1,gross_pnl=-50,cost=6,net_pnl=-56)]).to_csv(source/'partial_closes_of_residual_entries.csv',index=False)
        (source/'residual_open_positions.json').write_text(json.dumps([dict(trade_id='o2',volume=3,original_open_volume=4,closed_volume=1,remaining_volume=3,commission=6,slippage=3)]))
        metrics=json.loads((source/'summary.json').read_text());metrics.update(total_trade_count=5,completed_episodes=1,**self.mod.FRACTIONAL_FLAGS,fractional_risk_policy=dict(self.mod.FRACTIONAL_POLICY),baseline_commit=self.mod.BASELINE_COMMIT)
        (source/'summary.json').write_text(json.dumps(metrics));fixture.freeze();identity=json.loads((source/'manifest.json').read_text());identity.update(**self.mod.FRACTIONAL_FLAGS,fractional_risk_policy=dict(self.mod.FRACTIONAL_POLICY),baseline_commit=self.mod.BASELINE_COMMIT,baseline_run_manifest_sha256=self.mod.BASELINE_SHA)
        identity['parameters']=dict(stage068_risk_fraction=.005,max_position_size=2147483647,min_position_size=1,fixed_size=0,max_concurrent_positions=93);(source/'manifest.json').write_text(json.dumps(identity))
        parent=fixture.root/'raw';fixture.module.render_bundle(source,parent);return source,parent,fixture.root

    def test_full_frozen_multi_lot_recap_preserves_plot_arrays_and_displays_net_cost_volume(self):
        source,parent,root=self.source_fixture();out=root/'fractional';before=json.loads((parent/'records.json').read_text())
        result=self.mod.enrich(source,parent,out);after=json.loads((out/'records.json').read_text());m=after[0]['meta']
        self.assertEqual(m['volume'],3);self.assertEqual(m['risk_amount'],300);self.assertAlmostEqual(m['r_multiple'],500/300);self.assertEqual(m['cost'],18);self.assertEqual(m['net_pnl'],482)
        self.assertEqual(self.mod.protected_hash(before),self.mod.protected_hash(after));self.assertEqual(result['fractional_recap_enrichment']['unallocated_remaining_entry_cash_cost'],9)
        page=(out/'index.html').read_text();self.assertTrue("['交易手数',m.volume]" in page);self.assertTrue("['毛/净盈亏'" in page);self.assertTrue('0.5%' in page);self.assertFalse('每品种1手' in result['page_title'])
        self.assertEqual(pd.read_csv(out/'closed_lots.csv').signal.tolist(),['long_case2','long_case2'])
        self.assertEqual(len(pd.read_csv(out/'partial_closes_of_residual_entries.csv')),1)
        self.assertEqual(result['backtest_metrics'],json.loads((source/'summary.json').read_text()))
        with self.assertRaises(FileExistsError):self.mod.enrich(source,parent,out)

    def test_round_trip_budget_receipt_and_wrong_fraction_rejected(self):
        source,parent,root=self.source_fixture();trades=pd.read_csv(source/'trades.csv',float_precision='round_trip');trades.loc[trades.offset.eq('open'),'stage068_open_budget']=5000.000000000001
        trades.to_csv(source/'trades.csv',index=False)
        with self.assertRaisesRegex(ValueError,'fractional_open_budget'):self.mod.normalize_receipts(source,trades)
        identity=json.loads((source/'manifest.json').read_text());metrics=json.loads((source/'summary.json').read_text());identity['fractional_risk_policy']['risk_fraction']=.0005
        with self.assertRaisesRegex(ValueError,'fractional_risk_policy'):self.mod.validate_policy(identity,metrics)

if __name__=='__main__':unittest.main()
