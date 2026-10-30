import importlib.util,json,tempfile,unittest
from pathlib import Path
from copy import deepcopy
import pandas as pd

class ReserveRunnerTests(unittest.TestCase):
 def subject(self):
  self.assertIsNotNone(importlib.util.find_spec('stage009_contract'),'Stage009 independent contract not implemented')
  import stage009_contract as m
  return m
 def test_independent_scope_and_capital_are_fixed(self):
  m=self.subject();self.assertEqual(len(m.STARTS),23);self.assertEqual(m.CUTOFF,'2026-10-29');self.assertEqual((m.ENGINE_CAPITAL,m.RESERVE_CAPITAL,m.TOTAL_CAPITAL),(150000.,150000.,300000.));self.assertNotIn('2026-06-01',m.STARTS)
 def fixture(self):
  raw=pd.DataFrame(dict(date=['2015-01-05','2015-01-06','2015-01-07'],account_equity=[150000.,130000.,135000.],net_pnl=[0.,-20000.,5000.],slippage=[0.,20.,10.],commission=[0.,0.,0.],trade_count=[0,2,1]))
  events=[dict(date='2015-01-06',event_id='1',transfer_amount=20000.,cumulative_transfer=20000.,reserve_after=130000.,reserve_before=150000.,trading_equity_before=130000.,trading_equity_after=150000.,raw_account_equity=130000.,total_account_equity=280000.,entry_context='flat_entry',phase='before_parent_sizing',signal='long_case1a',direction='long',weekly_stop_valid=True,range_would_block=False)]
  return raw,events
 def test_internal_transfer_does_not_create_total_profit(self):
  m=self.subject();raw,events=self.fixture();d=m.reserve_daily_bridge(raw,events,'2015-01-01');self.assertEqual(d.trading_account_equity.tolist(),[150000.,150000.,155000.]);self.assertEqual(d.reserve_balance.tolist(),[150000.,130000.,130000.]);self.assertEqual(d.total_account_equity.tolist(),[300000.,280000.,285000.]);self.assertEqual(d.net_pnl.sum(),-15000.);self.assertEqual(raw.account_equity.tolist(),[150000.,130000.,135000.])
 def test_transfer_before_account_duplicate_negative_or_overdraw_rejected(self):
  m=self.subject();raw,events=self.fixture()
  for bad in [[dict(events[0],date='2014-12-31')],events+events,[dict(events[0],transfer_amount=-1.)],[dict(events[0],transfer_amount=150001.,cumulative_transfer=150001.,reserve_after=-1.)]]:
   with self.subTest(bad=bad),self.assertRaises(ValueError):m.reserve_daily_bridge(raw,bad,'2015-01-01')
 def test_idle_controls_same300k_capital_without_replay(self):
  m=self.subject();raw,_=self.fixture();d=m.reserve_daily_bridge(raw,[],'2015-01-01');self.assertEqual(d.cumulative_transfer.tolist(),[0.,0.,0.]);self.assertEqual(d.reserve_balance.tolist(),[150000.]*3);self.assertEqual(d.total_account_equity.iloc[-1],285000.)
 def test_checkpoint_key_binds_amounts_scope_and_source(self):
  m=self.subject();f=dict(source_head='a'*40,cutoff=m.CUTOFF,engine_initial_capital=150000.,reserve_initial_capital=150000.,total_initial_capital=300000.);base=m.checkpoint_key(f,'f'*64,'A','2015-01-01')
  for changed in [dict(f,reserve_initial_capital=0),dict(f,source_head='b'*40)]:self.assertNotEqual(base,m.checkpoint_key(changed,'f'*64,'A','2015-01-01'))
  self.assertNotEqual(base,m.checkpoint_key(f,'f'*64,'C','2015-01-01'))
 def fake_run(self,root):
  import math,numpy as np
  m=self.subject();raw,events=self.fixture();raw.loc[2,'date']=m.CUTOFF;events[0]['candidate_key']='2015-01-06|x|long|long_case1a|flat_entry';bridge=m.reserve_daily_bridge(raw,events,'2015-01-01');path=root/'run';path.mkdir();mapping=root/'mapping.csv';raw[['date']].to_csv(mapping,index=False);source=root/'source.txt';source.write_text('fixed input')
  flags={k:False for k in ['enable_portfolio_volatility_budget','enable_portfolio_volatility_budget_deleverage','enable_portfolio_overheat_cooldown','enable_portfolio_overheat_cooldown_deleverage','enable_portfolio_drawdown_gate','enable_portfolio_drawdown_deleverage','enable_risk_cluster_heat_gate']};flags.update(enable_risk_cluster_heat_deleverage=True,enable_risk_cluster_margin_cap=True)
  freeze=dict(source_head='a'*40,cutoff=m.CUTOFF,data_identity={'data':'b'*64},engine_initial_capital=150000.,reserve_initial_capital=150000.,total_initial_capital=300000.)
  def write(name,obj):(path/name).write_text(json.dumps(obj))
  write('preflight.json',dict(arm='A',start='2015-01-01',end=m.CUTOFF,head='a'*40,frozen_source_head='a'*40,freeze_sha256='f'*64,data_identity=freeze['data_identity'],short_ma_slope_gate_enabled=False,long_ma_slope_gate_enabled=False,long_price_range_gate_enabled=False,short_price_range_gate_enabled=False,reserve_topup_enabled=True,engine_initial_capital=150000.,reserve_initial_capital=150000.,total_initial_capital=300000.,actual_reserve_risk_flags=flags))
  write('terminal.json',dict(status='completed_pending_independent_review',error=None,started_at='2026-10-30T14:00:00+08:00',completed_at='2026-10-30T14:01:00+08:00',order_api_count=0));write('postflight.json',dict(inputs_unchanged=True));write('input_manifest.json',{str(source):m.sha(source)})
  for name in ['short_ma_slope_acceptance.json','long_ma_slope_acceptance.json','long_price_range_acceptance.json','short_price_range_acceptance.json']:write(name,dict(accepted=True,enabled=False,applied_block_count=0,decision_count=0))
  write('actual_strategy_settings.json',[dict(actual=dict(trade_start_date='2015-01-01',capital_base=150000.,enable_add_position=False,mapping_csv_path=str(mapping)))])
  raw.to_csv(path/'daily.csv',index=False);bridge.to_csv(path/'reserve_daily.csv',index=False)
  def metrics(equity,capital):
   ret=equity.pct_change().replace([np.inf,-np.inf],np.nan).fillna(0.);return dict(end_equity=float(equity.iloc[-1]),total_return_pct=(float(equity.iloc[-1])/capital-1)*100,total_slippage=30.,total_trade_count=3,max_dd_pct=float(((equity/equity.cummax()-1)*100).min()),sharpe=float(ret.mean()/ret.std(ddof=1)*math.sqrt(252)),account_capital=capital,initial_capital=capital,equity_basis='total_account_equity' if capital==300000 else 'raw_engine_account_equity_excluding_internal_transfers')
  write('metrics.json',metrics(raw.account_equity,150000.));write('reserve_total_metrics.json',metrics(bridge.total_account_equity,300000.));checks=[dict(events[0],eligible=True,duplicate=False,selected_volume_after_parent=0,enabled=True)];snaps=[]
  for i,row in enumerate(bridge.to_dict('records')):snaps.append(dict(date=row['date'],phase='after_on_bars_settlement',sequence=i+1,**{k:row[k] for k in ['raw_account_equity','cumulative_transfer','trading_account_equity','reserve_balance','total_account_equity']},transfer_event_count=0 if i==0 else 1,trade_costs_total=0.))
  phases=[dict(date='2015-01-06',post_sizing_fill=False,fill_count=2),dict(date=m.CUTOFF,post_sizing_fill=False,fill_count=1)]
  for name,obj in [('reserve_events.json',events),('reserve_checks.json',checks),('reserve_snapshots.json',snaps),('reserve_fill_phases.json',phases)]:write(name,obj)
  write('reserve_acceptance.json',dict(accepted=True,enabled=True,event_count=1,check_count=1,snapshot_count=3,engine_initial_capital=150000.,strategy_capital_base=150000.,reserve_initial_capital=150000.,total_initial_capital=300000.,actual_risk_flags=flags,snapshot_proof=m.validate_reserve_snapshots(bridge,snaps,'2015-01-01'),phase_proof=m.validate_event_daily_anchors(bridge,events,phases),checks_proof=m.validate_reserve_checks(checks,events,'A','2015-01-01')))
  return path,freeze
 def test_checkpoint_reconstructs_both_buckets_and_preserves_loss(self):
  m=self.subject()
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);run,f=self.fake_run(root);cp=root/'cp.json';r=m.make_checkpoint(run,cp,f,'f'*64,'A','2015-01-01');self.assertEqual(r['metrics']['end_equity'],285000.);self.assertEqual(r['raw_metrics']['end_equity'],135000.);self.assertLess(r['metrics']['total_return_pct'],0);self.assertEqual(m.read_checkpoint(cp,f,'f'*64,'A','2015-01-01')['cumulative_transfer'],20000.)
   (run/'reserve_daily.csv').write_text((run/'reserve_daily.csv').read_text()+'\n')
   with self.assertRaises(ValueError):m.read_checkpoint(cp,f,'f'*64,'A','2015-01-01')
 def test_run_rejects_fake_accepted_certificate_wrong_capital_or_phase(self):
  m=self.subject()
  with tempfile.TemporaryDirectory() as td:
   run,f=self.fake_run(Path(td));p=run/'reserve_acceptance.json';original=json.loads(p.read_text())
   for key,value in [('engine_initial_capital',300000.),('event_count',0),('snapshot_proof',{'accepted':True})]:
    bad=deepcopy(original);bad[key]=value;p.write_text(json.dumps(bad))
    with self.subTest(key=key),self.assertRaises(ValueError):m.validate_run(run,f,'A','2015-01-01')
   p.write_text(json.dumps(original));phase=run/'reserve_fill_phases.json';rows=json.loads(phase.read_text());rows[0]['post_sizing_fill']=True;phase.write_text(json.dumps(rows))
   with self.assertRaises(ValueError):m.validate_run(run,f,'A','2015-01-01')
 def test_coordinator_only_canary_first_and_failed_job_never_redispatched(self):
  import stage009_coordinator as c
  self.assertTrue(hasattr(c,'select_pending'),'strict dispatch selector missing');reg={'jobs':{s+'|'+a:dict(status='pending') for s in c.STARTS for a in ['A','C']}}
  self.assertEqual(c.select_pending(reg,'canary'),['2015-01-01|A','2015-01-01|C']);self.assertEqual(len(c.select_pending(reg,'resume')),46)
  reg['jobs']['2015-01-01|A']['status']='failed'
  with self.assertRaises(ValueError):c.select_pending(reg,'resume')
 def test_freeze_requires_fixed46_amounts_and_all_financial_sources(self):
  m=self.subject()
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);registry=root/'idle_registry.json';old=root/'old_freeze.json';registry.write_text('{}');old.write_text('{}')
   required=m.required_financial_sources();f=dict(source_head='a'*40,cutoff=m.CUTOFF,starts=list(m.STARTS),data_identity={k:'b'*64 for k in m.IDENTITY_KEYS},source_files_sha256={str(p):m.sha(p) for p in required},engine_initial_capital=150000.,reserve_initial_capital=150000.,total_initial_capital=300000.,planned_arm_windows=46,planned_financial_replays=46,idle_control_registry=str(registry),idle_control_registry_sha256=m.sha(registry),idle_control_freeze=str(old),idle_control_freeze_sha256=m.sha(old));p=root/'freeze.json';p.write_text(json.dumps(f));self.assertEqual(m.validate_freeze(p)[0],f)
   for key,value in [('engine_initial_capital',300000),('planned_financial_replays',42),('source_files_sha256',{}),('starts',list(m.STARTS)[:-1])]:
    bad=deepcopy(f);bad[key]=value;p.write_text(json.dumps(bad))
    with self.subTest(key=key),self.assertRaises(ValueError):m.validate_freeze(p)
 def test_bridge_rejects_self_consistent_event_using_fake_real_equity(self):
  m=self.subject();raw,events=self.fixture();fake=dict(events[0],raw_account_equity=140000.,trading_equity_before=140000.,trading_equity_after=150000.,transfer_amount=10000.,reserve_after=140000.,cumulative_transfer=10000.,total_account_equity=290000.)
  with self.assertRaisesRegex(ValueError,'event_raw'):m.reserve_daily_bridge(raw,[fake],'2015-01-01')
 def test_event_is_anchored_to_raw_daily_only_without_post_sizing_fill(self):
  m=self.subject();self.assertTrue(hasattr(m,'validate_event_daily_anchors'),'event phase anchor missing');raw,events=self.fixture();d=m.reserve_daily_bridge(raw,events,'2015-01-01');phases=[dict(date='2015-01-06',post_sizing_fill=False,fill_count=2),dict(date='2015-01-07',post_sizing_fill=False,fill_count=1)]
  self.assertTrue(m.validate_event_daily_anchors(d,events,phases)['accepted'])
  bad=deepcopy(events);bad[0]['raw_account_equity']+=100
  with self.assertRaises(ValueError):m.validate_event_daily_anchors(d,bad,phases)
  with self.assertRaises(ValueError):m.validate_event_daily_anchors(d,events,[dict(phases[0],post_sizing_fill=True)])
 def test_reserve_checks_require_eligible_unique_positive_events(self):
  m=self.subject();self.assertTrue(hasattr(m,'validate_reserve_checks'),'candidate event matching missing');_,events=self.fixture();events[0]['candidate_key']='candidate';checks=[dict(events[0],eligible=True,duplicate=False,selected_volume_after_parent=0,enabled=True)]
  self.assertTrue(m.validate_reserve_checks(checks,events,'A','2015-01-01')['accepted'])
  for key,value in [('entry_context','env_probe'),('duplicate',True),('eligible',False),('weekly_stop_valid',False)]:
   bad=deepcopy(checks);bad[0][key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):m.validate_reserve_checks(bad,events,'A','2015-01-01')
 def test_snapshot_last_sequence_matches_actual_raw_daily(self):
  m=self.subject();self.assertTrue(hasattr(m,'validate_reserve_snapshots'),'independent snapshot reconciliation missing');raw,events=self.fixture();d=m.reserve_daily_bridge(raw,events,'2015-01-01');snaps=[]
  for i,row in enumerate(d.to_dict('records')):snaps.append(dict(date=row['date'],phase='after_on_bars_settlement',sequence=i+1,**{k:row[k] for k in ['raw_account_equity','cumulative_transfer','trading_account_equity','reserve_balance','total_account_equity']},transfer_event_count=0 if i==0 else 1,trade_costs_total=0.))
  self.assertTrue(m.validate_reserve_snapshots(d,snaps,'2015-01-01')['accepted'])
  bad=deepcopy(snaps);bad[-1]['trading_account_equity']+=1
  with self.assertRaises(ValueError):m.validate_reserve_snapshots(d,bad,'2015-01-01')
 def test_total_metrics_use300k_curve_not_raw150k(self):
  m=self.subject();self.assertTrue(hasattr(m,'total_metric_frame'),'total capital curve adapter missing');raw,events=self.fixture();d=m.reserve_daily_bridge(raw,events,'2015-01-01');frame=m.total_metric_frame(raw,d);self.assertEqual(frame.account_equity.tolist(),[300000.,280000.,285000.]);self.assertEqual(raw.account_equity.tolist(),[150000.,130000.,135000.]);self.assertEqual(frame.net_pnl.tolist(),raw.net_pnl.tolist())
 def test_runner_preserves_engine_capital_and_rejects_hidden300k(self):
  self.assertIsNotNone(importlib.util.find_spec('run_stage009'),'Stage009 independent runner missing')
  import run_stage009 as r
  reference=json.loads((r.FROZEN/'R_attempt003/actual_strategy_settings.json').read_text())[0]['actual'];current=deepcopy(reference);mapping=r.LINE/'outputs/new_mapping.csv';current['mapping_csv_path']=str(mapping);current['trade_start_date']='2018-06-01'
  for k,v in list(current.items()):
   if isinstance(v,str):current[k]=v.replace('/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/',str(r.ROOT)+'/')
  self.assertEqual(r.normalize_settings(current,reference,mapping,{},'2018-06-01'),reference)
  current['capital_base']=300000
  with self.assertRaises(ValueError):r.normalize_settings(current,reference,mapping,{},'2018-06-01')
 def test_coordinator_runs46_new_and_canary2015jan(self):
  self.assertIsNotNone(importlib.util.find_spec('stage009_coordinator'),'Stage009 independent coordinator missing')
  import stage009_coordinator as c
  self.assertEqual(c.CANARY,'2015-01-01');self.assertEqual(c.BASE.name,'stage009_multistart');self.assertEqual(c.output_path('2020-06-01','C').name,'stage009_C_20200601_attempt001')
 def test_reserve_daily_bridge_checks_raw_pnl_identity(self):
  m=self.subject();raw,events=self.fixture();raw.loc[2,'account_equity']+=1
  with self.assertRaisesRegex(ValueError,'raw_equity'):m.reserve_daily_bridge(raw,events,'2015-01-01')

if __name__=='__main__':unittest.main()
