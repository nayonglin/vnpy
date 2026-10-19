import importlib.util,unittest
from pathlib import Path
HERE=Path(__file__).parent

def load():
 p=HERE/'stage094_quarter_risk_recap.py';assert p.exists(),'quarter-risk adapter missing';s=importlib.util.spec_from_file_location('quarter094',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def fixture(m,enabled):
 import copy
 a=dict(**m.old.FRACTIONAL_FLAGS,fractional_risk_policy=copy.deepcopy(m.FRACTIONAL_POLICY),parent_execution_run_id=m.PARENT_RUN,parent_execution_manifest_sha256=m.PARENT_SHA,parent_execution_commit=m.PARENT_COMMIT,frozen_data_manifest_sha256=m.DATA_SHA,long_weekly_filter=enabled,weekly_policy=copy.deepcopy(m.WEEKLY_POLICY) if enabled else None,weekly_feature_export_scope='queried_contracts_complete_local_weeks' if enabled else 'disabled_no_weekly_queries')
 a['parameters']=dict(stage068_risk_fraction=.0025,max_position_size=2147483647,min_position_size=1,fixed_size=0,max_concurrent_positions=93);a['weekly_feature_export']=dict(scope='disabled_no_weekly_queries',queried_contracts=[],rows=0) if not enabled else {}
 b=copy.deepcopy(a)
 if not enabled:b.update({k:0 for k in m.OFF_COUNTERS});b['actual_long_weekly_violations']=None
 return a,b

class QuarterRiskTest(unittest.TestCase):
 def test_quarter_budget_exact_and_reused_allocation(self):
  m=load();self.assertEqual(m.budget(1000000),2500);self.assertEqual(m.budget(32146.359636085206),float(__import__('decimal').Decimal('32146.359636085206')*__import__('decimal').Decimal('.0025')))
  import stage071_fractional_recap as old
  self.assertIs(m.attribute_closed_lots,old.attribute_closed_lots);self.assertIs(m.complete_entry_episodes,old.complete_entry_episodes)
  self.assertTrue(m.reuse_proof()['only_declared_constants_changed'])
 def test_full_frozen_both_modes_R_cost_arrays_and_display_weekly_without_provider(self):
  import json
  for enabled in (True,False):
   arm=frozen_arm(self,enabled);r=json.loads((arm['fractional']/'records.json').read_text())[0]['meta'];self.assertEqual(r['volume'],3);self.assertEqual(r['risk_amount'],300);self.assertEqual(r['cost'],18);self.assertEqual(r['net_pnl'],482)
   w=json.loads((arm['weekly']/'summary.json').read_text());self.assertEqual(w['quarter_weekly_display']['financial_provider_queries'],0);self.assertEqual(w['quarter_weekly_display']['weekly_filter'],enabled);self.assertEqual(w['quarter_weekly_display']['non_weekly_payload_sha256_before'],w['quarter_weekly_display']['non_weekly_payload_sha256_after']);self.assertTrue('0.25%' in w['page_title'])
   if not enabled:self.assertTrue('关闭' in w['page_title']);self.assertTrue('不构成策略周过滤证据' in w['source_warning'])
 def test_policy_modes_and_parent_binding_not_old_half_percent(self):
  m=load()
  for mode in (True,False):
   a,b=fixture(m,mode);m.validate_policy(a,b)
   a['fractional_risk_policy']['risk_fraction']=.005
   with self.assertRaisesRegex(ValueError,'quarter_policy'):m.validate_policy(a,b)
  a,b=fixture(m,False);b['actual_long_weekly_violations']=0
  with self.assertRaisesRegex(ValueError,'disabled_weekly'):m.validate_policy(a,b)
  a,b=fixture(m,True);a['parent_execution_manifest_sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'parent_execution'):m.validate_policy(a,b)



def frozen_arm(test,enabled):
 import importlib.util,json,shutil,pandas as pd,numpy as np
 import stage094_quarter_risk_recap as m
 import stage095_quarter_weekly_display as week
 from stage001_frozen_recap import render_bundle
 s=importlib.util.spec_from_file_location('toy071quarter',HERE/'test_stage071_fractional_recap.py');fm=importlib.util.module_from_spec(s);s.loader.exec_module(fm);f=fm.FractionalRecapTest('runTest');f.setUp();test.addCleanup(f.doCleanups);source,unused,root=f.source_fixture();data=root/'data_anchor';shutil.copytree(source,data);data_hash=m.old.sha256(data/'manifest.json')
 a,b=fixture(m,enabled);identity=json.loads((source/'manifest.json').read_text());metrics=json.loads((source/'summary.json').read_text());identity.update(a);metrics.update(b);identity.update(run_id=source.name,mode='daily-proxy',baseline_run_manifest_sha256=data_hash);identity.pop('code_snapshot_hashes',None)
 dates=pd.bdate_range('2015-01-05',periods=2862);identity['start']=str(dates[0].date());identity['end']=str(dates[-1].date());net=np.zeros(len(dates));net[0]=-100;net[1]=517;equity=1000000+np.cumsum(net);peak=np.maximum.accumulate(np.maximum(equity,1000000));dd=(equity/peak-1)*100
 daily=pd.DataFrame(dict(date=dates.strftime('%Y-%m-%d'),net_pnl=net,equity=equity,balance=equity,highlevel=peak,drawdown=equity-peak,ddpercent=dd,commission=[22.]+[0.]*(len(dates)-1),slippage=[11.]+[0.]*(len(dates)-1)));daily.to_csv(source/'daily.csv',index=False)
 metrics.update(mode='daily-proxy',performance_certifiable=True,analysis_start=daily.date.iloc[0],analysis_end=daily.date.iloc[-1],initial_capital=1000000,total_days=len(daily),end_balance=float(equity[-1]),total_return=float((equity[-1]/1000000-1)*100),max_drawdown=float((equity-peak).min()),max_ddpercent=float(dd.min()),total_commission=22.,total_slippage=11.,residual_open_positions=1,completed_contracts=3,actual_long_weekly_violations=0 if enabled else None)
 trades=pd.read_csv(source/'trades.csv',float_precision='round_trip')
 for i,r in trades[trades.offset.eq('open')].iterrows():
  d=json.loads(r.stage068_signal_snapshot);d.update(risk_fraction=.0025,target_risk_amount=2500);trades.loc[i,'stage068_signal_snapshot']=json.dumps(d);trades.loc[i,'stage068_open_budget']=2500
 trades['stage059_weekly_signal_snapshot']=json.dumps(dict(allowed=True)) if enabled else 'null';trades['stage059_weekly_open_snapshot']=json.dumps(dict(allowed=True)) if enabled else 'null';trades.to_csv(source/'trades.csv',index=False)
 audit=pd.read_csv(source/'open_budget_audit.csv',float_precision='round_trip');audit['opening_budget']=2500;audit['max_affordable_volume']=25;audit['signal_snapshot']=audit.trade_id.map(trades.set_index('trade_id').stage068_signal_snapshot);audit.to_csv(source/'open_budget_audit.csv',index=False)
 market=pd.read_csv(source/'market_daily.csv');market['execution_only']=False;market['quote_class']='accepted_clean';market['allow_new_open']=float('nan');market.to_csv(source/'market_daily.csv',index=False);calendar=pd.DataFrame({'date':pd.bdate_range('2010-01-01','2027-12-31')});calendar.to_csv(source/'trading_calendar.csv',index=False);meta=pd.read_csv(source/'contract_metadata.csv');meta['listed_date']='2010-01-01';meta.to_csv(source/'contract_metadata.csv',index=False)
 table=week.build_display_tables(market,meta,calendar,{'rb1901.SHFE'})['rb1901.SHFE'];ends=pd.Series(calendar.date).groupby(calendar.date.dt.to_period('W-FRI').astype(str)).max();features=table[['week','close','ma5','ma10','ma20','ma40']].copy();features['week_last_session']=features.week.map(ends);features['contract_vt_symbol']='rb1901.SHFE'
 if not enabled:features=features.iloc[:0]
 features.to_csv(source/'weekly_contract_features.csv',index=False)
 for name in ('weekly_signal_audit.csv','weekly_execution_audit.csv'):pd.DataFrame([dict(trade_id='o1',weekly_allowed=True)] if enabled else []).to_csv(source/name,index=False)
 if enabled:identity['weekly_feature_export']=dict(scope='queried_contracts_complete_local_weeks',queried_contracts=['rb1901.SHFE'],rows=len(features))
 identity['weekly_feature_export_scope']='queried_contracts_complete_local_weeks' if enabled else 'disabled_no_weekly_queries';metrics['weekly_feature_export_scope']=identity['weekly_feature_export_scope']
 (source/'lifecycle_deadlines.csv').write_text('vt_symbol,deadline\nrb1901.SHFE,2019-01-01\n');snap=source/'code_snapshot';snap.mkdir(exist_ok=True)
 for name in ('stage090_quarter_risk.py','stage091_quarter_weekly.py','stage092_quarter_pending_open.py','stage093_run_quarter_pair.py'):(snap/name).write_text('# frozen toy fixture\n')
 identity['code_snapshot_hashes']={p.name:m.old.sha256(p) for p in snap.iterdir()};(source/'summary.json').write_text(json.dumps(metrics));identity['hashes']={p.name:m.old.sha256(p) for p in source.iterdir() if p.is_file() and p.name!='manifest.json'};(source/'manifest.json').write_text(json.dumps(identity));raw=root/'raw_quarter';render_bundle(source,raw);risk=root/'risk_quarter';m.enrich(source,raw,risk);weekly=root/'weekly_quarter';week.enrich(source,risk,weekly)
 return dict(source=source,raw=raw,fractional=risk,weekly=weekly,root=root,data=data,data_hash=data_hash)

if __name__=='__main__':unittest.main()
