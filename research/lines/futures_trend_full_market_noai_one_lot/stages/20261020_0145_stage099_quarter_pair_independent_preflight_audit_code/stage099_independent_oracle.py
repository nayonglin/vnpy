import sys,json,math
from copy import deepcopy
from datetime import datetime
from dataclasses import asdict
sys.path.insert(0,'/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot/tools')
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file']=False
from test_stage093_pair import EnabledPendingLifecycle,DisabledPendingLifecycle,PairRealExecutionTests
import stage090_quarter_risk as quarter
import stage068_fractional_risk as legacy
import stage093_run_quarter_pair as runner
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch
from qmt_roll_portfolio_strategy import ProductState,PositionLayer
checks=[]
def ck(name,condition):
 assert condition,name
 checks.append(name)
for mode in ('enabled','disabled'):
 Fixture=EnabledPendingLifecycle if mode=='enabled' else DisabledPendingLifecycle
 # Complete native daily missing-bar flow preserves authorization and funding.
 h=Fixture();e,s,vt,b,o,l,state=h.defer(missing=True);original=l.stage068_signal_risk_budget
 other=deepcopy(b);other.symbol='OTHER';other.vt_symbol='OTHER.CFFEX'
 s.on_bars({other.vt_symbol:other})
 ck('missing_margin270',s.total_margin_in_use==270 and s._reserved_margin_in_use()==270)
 ck('missing_cluster270',s.cluster_margin_usage=={'IC':270.})
 ck('missing_pnl0',not s.cluster_unrealized_pnl and s.get_pos(vt)==0)
 ck('cache_dispatch_no_AM',s.ams[vt].count==300 and not e.trades and (e.datetime,vt) not in e.history_data)
 ck('same_receipt',state.layers[0].stage068_signal_risk_budget is original)
 h.later_fill(e,s,vt,b);ck('later_actual3',s.get_pos(vt)==-3 and len(e.trades)==1)
 ck('later_original_snapshot',next(iter(e.trades.values())).stage068_signal_snapshot==asdict(original))
 # Actual margin is additive with an independent pending OPEN, regardless of how
 # much of actual A has already been committed to delayed CLOSE.
 for direction in ('long','short'):
  for committed in range(6):
   e,s,vt,b,o,l,state=h.defer();avt='IF202112.CFFEX';prod='IF.CFFEX';ab=deepcopy(b);ab.symbol='IF202112';ab.vt_symbol=avt;ab.open_price=ab.high_price=ab.low_price=ab.close_price=100.
   s.source_symbol_by_contract[avt]=prod;s.pos_data[avt]=5 if direction=='long' else -5;s.set_target(avt,(5-committed)*(1 if direction=='long' else -1));e.sizes[avt]=10;e.bars[avt]=ab
   real_layers=[] if committed==5 else [PositionLayer('base',direction,5-committed,95,90 if direction=='long' else 110,100,100,'filled','2021-12-01',entry_price_synced=True)]
   s.states[prod]=ProductState(product_vt_symbol=prod,contract_vt_symbol=avt,direction=direction,layers=real_layers)
   if committed:s.pending_close_lots[avt]=[dict(volume=committed,direction=direction,entry_price=95,provisional_exit_price=100)]
   s.risk_cluster_map='IC.CFFEX=shared;IF.CFFEX=shared';bars={vt:b,avt:ab}
   ck('fund770_'+direction+str(committed),s._estimate_margin_usage(bars)==770 and s._estimate_margin_usage_by_cluster(bars)=={'shared':770.})
   ck('true_pnl_'+direction+str(committed),s._estimate_unrealized_pnl_by_cluster(bars)=={'shared':250. if direction=='long' else -250.})
   s._stage078_intent_reservations={vt:dict(margin=270.,cluster='shared',cluster_margin=270.)};s.pending_margin_reservation=270.;s.pending_cluster_margin_reservation={'shared':270.}
   ck('not_double_'+direction+str(committed),s._reserved_margin_in_use()==770 and s._reserved_cluster_margin('shared')==770)
   s.pending_margin_reservation+=7;s.pending_cluster_margin_reservation['shared']+=7
   ck('extra_reserve_'+direction+str(committed),s._reserved_margin_in_use()==777 and s._reserved_cluster_margin('shared')==777)
   s._stage078_forced_planning_active=True
   ck('projection_'+direction+str(committed),s._estimate_margin_usage(bars)==(5-committed)*100+270)
   s._stage078_forced_planning_active=False
   ck('restored_actual_'+direction+str(committed),s._estimate_margin_usage(bars)==770)
 # Genuine deferred path mapping invalidates before real engine fill; normal first
 # T->T+1 intentionally retains old original signal contract semantics.
 for deferred in (False,True):
  e,s,vt,b,o,l,state=h.fixture(volume=100)
  if deferred:
   b.volume=2;e.cross_delayed_orders();s.on_bars({vt:b});dt=datetime(2021,12,13)
  else:dt=e.datetime
  s.daily_mapping[dt.date().isoformat()]={};real=deepcopy(b);real.datetime=dt;real.volume=100;e.history_data[(dt,vt)]=real
  e.new_bars(dt)
  ck('mapping_timing_'+str(deferred),(not e.trades and not s.get_pos(vt) and not s.pending_close_lots) if deferred else (len(e.trades)==1 and s.get_pos(vt)==-3))
 # Valid own fresh rollover is counted for funding even while the old real leg
 # remains entirely pending CLOSE; strict preservation still does not authorize it.
 e,s,vt,b,o,l,state=h.fixture();old='IC202109.CFFEX';ob=deepcopy(b);ob.symbol='IC202109';ob.vt_symbol=old;ob.open_price=ob.high_price=ob.low_price=ob.close_price=100.;e.sizes[old]=10;e.bars[old]=ob;s.source_symbol_by_contract[old]='IC.CFFEX';s.pos_data[old]=-5;s.pending_close_lots[old]=[dict(volume=5,direction='short',entry_price=95,provisional_exit_price=100)]
 s._stage085_fresh_layers={vt:(l,l.stage068_signal_risk_budget)}
 ck('fresh_rollover_funding770',s._estimate_margin_usage({vt:b,old:ob})==770 and s._reserved_margin_in_use()==770)
 ck('strict_preserve_still_false',not s._stage085_status(state)[0])

# Own arithmetic boundary and cross-generation strict receipts.
for equity in (1_000_000.,999_999.,1_200_000.):
 ck('budget_'+str(equity),quarter.fractional_budget(equity)==equity/400.)
for budget,per,want in ((2500.,100.,25),(2500.,100.000000001,24),(2500.,2500.,1),(2500.,2500.01,0)):
 ck('floor_'+str(per),quarter.whole_contracts(budget,per)==want)
class Poison:
 def __getattribute__(self,name):raise AssertionError('weekly touched '+name)
for mode in ('enabled','disabled'):
 strategy,engine=runner.select_classes(mode,'daily-proxy')
 ck('own_mro_'+mode,'stage090_quarter_risk' in [c.__module__ for c in strategy.__mro__] and all(c.__module__ not in ('stage068_fractional_risk','stage075_fractional_weekly','stage085_pending_open_lifecycle') for c in strategy.__mro__+engine.__mro__))
 for direction in ('long','short'):
  for case in ('exact','gap','old_type','fake_new_half'):
   e,s,vt,b,o,l=PairRealExecutionTests().fixture(mode,direction)
   if mode=='disabled' or direction=='short':e.weekly_contract=Poison()
   if case=='gap':b.open_price=200 if direction=='long' else 1
   if case=='old_type':l.stage068_signal_risk_budget=legacy.FractionalSignalRiskReceipt(**asdict(l.stage068_signal_risk_budget))
   if case=='fake_new_half':l.stage068_signal_risk_budget=replace(l.stage068_signal_risk_budget,risk_fraction=.005,target_risk_amount=5000.)
   e.cross_delayed_orders()
   ck('real_'+mode+direction+case,bool(e.trades)==(case=='exact'))
   if case=='exact':ck('real_budget_'+mode+direction,next(iter(e.trades.values())).stage068_budget==2500.)
   else:ck('rejection_flat_'+mode+direction+case,s.get_pos(vt)==0 and s.get_target(vt)==0)
 e,s,vt,b,o,l=PairRealExecutionTests().fixture(mode,'short')
 snap=asdict(l.stage068_signal_risk_budget)
 ck('quarter_dict_rejected_by_legacy_'+mode,not legacy.assess_fractional_open(direction='short',open_price=90.,stop_price=l.stop_price,size=10.,tick=.1,volume=3,receipt=snap,opening_equity=1_000_000.)['allowed'])
# Disabled must not even inspect an engine/provider attribute during export.
feature,scope=runner.weekly_feature_artifact(Poison(),False);summary=runner.weekly_check_summary(Poison(),Poison(),False)
ck('disabled_empty_export',feature.empty and scope['queried_contracts']==[] and scope['scope']=='disabled_no_weekly_queries')
ck('disabled_NA_not_zero_violations',summary['weekly_execution_checks']==0 and summary['actual_long_weekly_violations'] is None)
with patch.object(runner,'WeeklyContractTrend',side_effect=AssertionError('constructor touched')):
 engine=SimpleNamespace();runner.configure_weekly_provider(engine,False,Poison(),Poison(),Poison())
ck('disabled_no_provider_constructed',engine.weekly_filter_enabled is False and not hasattr(engine,'weekly_contract'))

print(json.dumps({'checks_passed':len(checks),'financial_replays':0,'checks':checks}));open('/private/tmp/stage099_independent_oracle.json','w').write(json.dumps({'checks_passed':len(checks),'financial_replays':0,'checks':checks},indent=2))
