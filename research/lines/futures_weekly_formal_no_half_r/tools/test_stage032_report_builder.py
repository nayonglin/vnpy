"""Real cash/MTM fixtures for Stage032's fail-closed report, no strategy replay."""
from pathlib import Path
import importlib.util
import json
import tempfile
import unittest
import pandas as pd

PATH = Path(__file__).with_name('stage032_build_artifacts.py')

class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('stage032_report', PATH)
        cls.m = importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.m)

    def ledger(self, path, enabled, db):
        path.mkdir()
        def write(name, value): (path/name).write_text(json.dumps(value))
        actual = dict({k:False for k in self.m.FLAGS},ma_short=5,ma_mid=10,ma_long=20,research_exact_array_manager_size=41,
            capital_base=150000.,max_concurrent_positions=19,stage830_broker_margin_multiplier=1.65,
            forced_margin_deleverage_broker_multiplier=1.65,enable_rsi_partial_exit=False)
        write('terminal.json',{'status':'completed_pending_independent_review','error':None})
        write('postflight.json',{'inputs_unchanged':True,'mismatches':[]})
        write('actual_strategy_settings.json',[{'actual':actual,'setting':actual,'engine_capital':150000.,'strategy_class':'HistoricalSafetyStrategy'}])
        effective = {'spec':{'capital':{'account_capital':150000.,'c3_capital':150000.}},'sizes':{'au2006.SHFE':10},'slippages':{'au2006.SHFE':1},'rates':{'au2006.SHFE':0}}
        write('effective_parameters.json',effective)
        config = dict(enabled=enabled,up_days=2,volume=1,max_adds_per_parent=2,max_active_per_product=1,stop_rule='fixed_prior2_low_daily_close_next_open')
        write('actual_daily_addon_configuration.json',config)
        write('preflight.json',dict(arm='C' if enabled else 'A',start='2020-01-01',end='2020-01-07',universe_products=sorted(self.m.POOL),ready_need=21,storage_capacity=41,execution_model=self.m.EXECUTION_MODEL,minute_quote_confirmed=False,daily_addon_enabled=enabled,data_identity={key:self.m.sha(db) for key in ['daily_sqlite_sha256','mapping_sha256','physical_epoch_daily_sha256','receipt_sha256']}))
        proofs = {'bar_open_acceptance.json':{'accepted':True,'verdict':'PASS_DECLARED_BAR_OPEN_MODEL','trade_count':4},
            'ai_selection_acceptance.json':{'accepted':True},'macd_acceptance.json':{'accepted':True},
            'short_case2_acceptance.json':{'accepted':True,'short_case2_gate_allowed':False,'short_case2_opened':0},
            'no_position_cap_acceptance.json':{'accepted':True,'MA40_decision_enabled':False,'max_daily_product_positions':1},
            'historical_safety_acceptance.json':{'accepted':True,'requested_start':'2020-01-01','requested_end':'2020-01-07','actual_calendar_matches':True,'readiness_calendar_matches':True,'epoch_failure_count':0,'strict_next_trading_day_open':True,'account_days':4},
            'week_close_exit_acceptance.json':{'accepted':True,'rsi_exit_enabled':False,'short_case2_enabled':False,'reconciliation_rebuilt_layer_count':0,'weekly_stop_guard_failure_count':0},
            'daily_addon_acceptance.json':{'accepted':True}}
        for name,value in proofs.items(): write(name,value)
        write('data_quality.json',dict(held_or_traded_daily_gaps=[],held_or_traded_zero_volume=[],captured_bar_failures=[]))
        write('data_read_counts.json',dict(minute_reads=0,proxy_reads=0,ai_selection_model_load_attempts=0))
        write('actual_database_binding.json',{'expected':str(db),'database_list':[[0,'main',str(db)]]})
        write('input_manifest.json',{str(db):self.m.sha(db)})
        dates=['2020-01-02','2020-01-03','2020-01-06','2020-01-07'];pnls=[-20.,190.,-210.,190.]
        daily=pd.DataFrame(dict(date=dates,account_equity=150000+pd.Series(pnls).cumsum(),net_pnl=pnls,slippage=[20.,10.,10.,10.],commission=[0.]*4,trade_count=[1]*4,total_margin_exact=[100.,110.,0.,120.],broker10_total_margin_exact=[110.,121.,0.,132.]))
        daily.to_csv(path/'daily.csv',index=False)
        metrics=self.m.curve_metrics(daily.assign(date=pd.to_datetime(dates)));write('metrics.json',{**metrics,'total_trade_count':4})
        trades=pd.DataFrame(dict(trade_id=['1','2','3','4'],vt_symbol=['au2006.SHFE']*4,direction=['多','空','空','多'],offset=['开','平','平','开'],price=[100.,110.,90.,100.],volume=[2.,1.,1.,1.],trading_date=dates,datetime=[d+' 09:00:00' for d in dates]))
        trades.to_csv(path/'trades.csv',index=False);trades.rename(columns={'datetime':'execution_datetime'}).to_csv(path/'execution_clock.csv',index=False)
        positions=daily[['date','net_pnl','slippage','commission','trade_count']].copy();positions['vt_symbol']='au2006.SHFE';positions['start_pos']=[0.,2.,1.,0.];positions['end_pos']=[2.,1.,0.,1.];positions['close_price']=[100.,110.,90.,120.];positions['pre_close']=[0.,100.,110.,90.];positions.to_csv(path/'positions.csv',index=False)
        # The addon is opened by trade4 and marked at120, never synthetically closed.
        alloc=trades.rename(columns={'datetime':'execution_datetime'}).copy();alloc['sleeve']=['base']*3+['daily_addon' if enabled else 'base'];alloc['addon_id']=['']*3+['add1' if enabled else ''];alloc['round_id']='round1';alloc['reason']='test';alloc['entry_price']=alloc.price;alloc['stop_price']=80.
        alloc.to_csv(path/'daily_addon_allocations.csv',index=False)
        pd.DataFrame([dict(round_id='round1',product_vt_symbol='au.SHFE',actual_add_count=int(enabled),status='open')]).to_csv(path/'daily_addon_rounds.csv',index=False)
        for name in ['events','decisions','snapshots','guard_failures']:
            pd.DataFrame(columns=['kind']).to_csv(path/f'daily_addon_{name}.csv',index=False)

    def pair(self,root):
        db=root/'daily.sqlite';db.write_bytes(b'immutable fixture data');a=root/'A';c=root/'C';self.ledger(a,False,db);self.ledger(c,True,db);return a,c

    def alter(self,path,name,fn):
        p=path/name;v=json.loads(p.read_text());fn(v);p.write_text(json.dumps(v))

    def test_report_real_fifo_round_open_and_sleeve_cost_conservation(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);a,c=self.pair(p);before={**self.m.snapshot_dir(a),**self.m.snapshot_dir(c)}
            got=self.m.build_artifacts(a,c,p/'report',p/'report'/'equity_drawdown.png')
            self.assertEqual(got['financial_replays'],0)
            s=json.loads((p/'report/comparison.json').read_text());candidate=s['arms']['candidate']
            self.assertEqual(candidate['accounting']['ledger_net_pnl'],150.)
            self.assertEqual(candidate['accounting']['closed_fifo']['closed_net_pnl'],-40.)
            self.assertEqual(candidate['accounting']['complete_contract_rounds']['count'],1)
            self.assertEqual(candidate['accounting']['open_round_net_mtm'],190.)
            self.assertEqual(candidate['sleeves']['daily_addon']['ledger_net_pnl'],190.)
            self.assertEqual(candidate['sleeves']['base']['ledger_net_pnl'],-40.)
            self.assertEqual(s['promotion_decision'],'NO_PROMOTION')
            self.assertEqual(candidate['addon_analysis']['actual_add_count'],1)
            self.assertEqual(candidate['addon_analysis']['by_add_number']['1']['open_net_mtm'],190.)
            entries=pd.read_csv(p/'report/addon_entries.csv')
            self.assertEqual(entries.net_pnl.tolist(),[190.])
            self.assertEqual(entries.status.tolist(),['open'])
            self.assertEqual(len(pd.read_csv(p/'report/annual_products.csv')),2)
            self.assertAlmostEqual(candidate['risk']['actual_margin_to_equity_max_pct'],120/150150*165)
            self.assertEqual(before,{**self.m.snapshot_dir(a),**self.m.snapshot_dir(c)})
            self.assertTrue((p/'report/equity_drawdown.png').stat().st_size>1000)
            self.m.verify_sources(json.loads((p/'report/delivery_manifest.json').read_text())['files_sha256'])
            self.assertEqual(len(pd.read_csv(p/'report/products.csv')),38)
            with self.assertRaises(FileExistsError): self.m.build_artifacts(a,c,p/'report',p/'report/equity_drawdown.png')

    def test_rejects_unfinished_missing_acceptance_and_false_reported_metrics(self):
        for name,change,error in [('terminal.json',lambda v:v.update(status='running'),'completed'),('metrics.json',lambda v:v.update(end_equity=150151),'source_metrics'),('daily_addon_acceptance.json',lambda v:v.update(accepted=False),'acceptance')]:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as folder:
                p=Path(folder);a,c=self.pair(p);self.alter(c,name,change)
                with self.assertRaisesRegex(ValueError,error):self.m.build_artifacts(a,c,p/'report',p/'plot.png')
                self.assertFalse((p/'report').exists())

    def test_rejects_data_identity_and_config_difference(self):
        for name,change,error in [('preflight.json',lambda v:v['data_identity'].update(mapping_sha256='a'*64),'data_identity'),('actual_strategy_settings.json',lambda v:v[0]['actual'].update(ma_short=6),'MA'),('effective_parameters.json',lambda v:v['spec']['capital'].update(risk_multiplier=.123),'effective'),('actual_daily_addon_configuration.json',lambda v:v.update(up_days=3),'addon_configuration')]:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as folder:
                p=Path(folder);a,c=self.pair(p);self.alter(c,name,change)
                with self.assertRaisesRegex(ValueError,error):self.m.build_artifacts(a,c,p/'report',p/'plot.png')

    def test_missing_calendar_day_nonfinite_positions_and_wrong_terminal_mark_rejected(self):
        for mode,error in [('missing','calendar'),('nan','nonfinite'),('mark','position_mtm')]:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as folder:
                p=Path(folder);a,c=self.pair(p)
                if mode=='missing':
                    d=pd.read_csv(c/'daily.csv').drop(index=1);d.to_csv(c/'daily.csv',index=False)
                else:
                    pos=pd.read_csv(c/'positions.csv');pos.loc[3,'close_price']=float('nan') if mode=='nan' else 121.;pos.to_csv(c/'positions.csv',index=False)
                with self.assertRaisesRegex(ValueError,error):self.m.build_artifacts(a,c,p/'report',p/'plot.png')

    def test_allocation_cannot_invent_fill_price_volume_or_omit_fills(self):
        for mode in ['price','volume','missing']:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as folder:
                p=Path(folder);a,c=self.pair(p);d=pd.read_csv(c/'daily_addon_allocations.csv')
                if mode=='missing':d=d.drop(index=2)
                else:d.loc[3,mode]+=1
                d.to_csv(c/'daily_addon_allocations.csv',index=False)
                with self.assertRaisesRegex(ValueError,'allocation'):self.m.build_artifacts(a,c,p/'report',p/'plot.png')

    def test_daily_position_pnl_forgery_rejected_even_when_daily_total_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);a,c=self.pair(p);pos=pd.read_csv(c/'positions.csv');pos.loc[0,'start_pos']=1.;pos.to_csv(c/'positions.csv',index=False)
            with self.assertRaisesRegex(ValueError,'position_inventory'):self.m.build_artifacts(a,c,p/'report',p/'plot.png')

    def test_sleeve_exit_does_not_close_base_fifo_lot(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);a,c=self.pair(p)
            effective=json.loads((c/'effective_parameters.json').read_text())
            trades=pd.DataFrame(dict(trade_id=['1','2','3'],vt_symbol=['au2006.SHFE']*3,direction=['多','多','空'],offset=['开','开','平'],price=[100.,110.,120.],volume=[1.,1.,1.],trading_date=['2020-01-02','2020-01-03','2020-01-06'],execution_datetime=['2020-01-02 09:00','2020-01-03 09:00','2020-01-06 09:00']))
            fills=self.m.ordered_fills(trades,trades)
            allocations=trades.copy();allocations['sleeve']=['base','daily_addon','daily_addon'];allocations['addon_id']=['','one','one'];allocations['round_id']='parent';allocations['entry_price']=[100.,110.,110.];allocations['stop_price']=[0.,95.,95.]
            allocations.to_csv(c/'daily_addon_allocations.csv',index=False)
            pd.DataFrame([dict(round_id='parent',actual_add_count=1)]).to_csv(c/'daily_addon_rounds.csv',index=False)
            sf,rf,of,total=self.m.inventory_accounting(fills,effective,{'au2006.SHFE':125.})
            own=self.m.sleeve_accounting(c,fills,effective,{'au2006.SHFE':125.},True)
            self.assertEqual(total['closed_fifo']['closed_net_pnl'],180.)
            self.assertEqual(own['summaries']['daily_addon']['closed_fifo']['closed_net_pnl'],80.)
            self.assertEqual(own['summaries']['base']['open_remaining_net_mtm'],240.)
            self.assertEqual(sum(v['ledger_net_pnl'] for v in own['summaries'].values()),total['ledger_net_pnl'])
            allocations.loc[2,'stop_price']=96.;allocations.to_csv(c/'daily_addon_allocations.csv',index=False)
            with self.assertRaisesRegex(ValueError,'fixed_stop_price'):
                self.m.sleeve_accounting(c,fills,effective,{'au2006.SHFE':125.},True)

    def test_empty_trading_and_empty_allocation_is_valid(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            for name in ['allocations','rounds','events','decisions','guard_failures']:
                pd.DataFrame().to_csv(path/f'daily_addon_{name}.csv',index=False)
            empty=pd.DataFrame(columns=['trade_id','vt_symbol','trading_date','direction','offset','price','volume','execution_datetime','_execution_utc','_clock_order'])
            result=self.m.sleeve_accounting(path,empty,dict(sizes={},slippages={},rates={}),{},True)
            self.assertEqual(result['summaries']['daily_addon']['ledger_net_pnl'],0.)

    def test_output_overlap_rejected_before_reading_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);a,c=self.pair(p)
            with self.assertRaisesRegex(ValueError,'inside_input'):
                self.m.build_artifacts(a,c,a/'report',p/'plot.png')

    def test_adapter_english_enums_and_integer_round_ids_are_semantically_equal(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);a,c=self.pair(p)
            allocation=pd.read_csv(c/'daily_addon_allocations.csv',keep_default_na=False)
            allocation['direction']=allocation.direction.map({'多':'long','空':'short'})
            allocation['offset']=allocation.offset.map({'开':'open','平':'close'})
            allocation['round_id']=1
            allocation.to_csv(c/'daily_addon_allocations.csv',index=False)
            pd.DataFrame([dict(round_id=1,actual_add_count=1)]).to_csv(c/'daily_addon_rounds.csv',index=False)
            result=self.m.load_ledger(c,'candidate')
            self.assertEqual(result['sleeve_details']['summaries']['daily_addon']['ledger_net_pnl'],190.)

if __name__=='__main__':unittest.main()
