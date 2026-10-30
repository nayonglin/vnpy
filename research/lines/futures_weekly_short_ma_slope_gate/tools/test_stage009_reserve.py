"""Behavioral reserve tests: cash conservation, causal eligibility and no probe effects."""
from datetime import datetime
from types import SimpleNamespace
import math
import unittest
from stage005_short_bottom20 import range_strategy_class
try:
 from stage009_reserve import reserve_strategy_class
except ImportError:
 def reserve_strategy_class(base,*a,**k):return base

class History:
 def __init__(self,blocked=False):self.blocked=blocked;self.calls=[]
 def snapshot(self,symbol,day,price):
  self.calls.append((symbol,day,price));return dict(would_block=self.blocked,contract_epoch_id='physical-1',range_low=80.,range_high=120.,history_end=day,range_status='valid')

class Parent:
 """Small marked-to-market account with real cash effects; no mocked call counters."""
 long_entry_enabled=True;short_entry_enabled=True;risk_ratio_of_total_assets=.02
 def __init__(self):
  self.base_capital=150000.;self.capital_base=150000.;self.settled_balance=150000.;self.estimated_equity=150000.;self.mark_pnl=0.;self.trade_costs_total=0.;self.total_margin_in_use=0.;self.pending_margin_reservation=0.;self.loss_streak=3;self.portfolio_equity_high_water=180000.;self.portfolio_drawdown_pct=1-150000/180000.;self.return_history=[.01,-.02];self.weekly_valid=True;self.weekly_stop=90.;self.stop_error=None;self.current_risk_per_trade=0.;self.risk_multiplier=.7;self.cluster_margin_usage={'rb':10000.};self.cluster_unrealized_pnl={'rb':-5000.};self.risk_cluster_heat_pressure_snapshot={};self.risk_cluster_heat_gate_weight=.5;self.portfolio_margin_deleverage_ratio=0.;self.strategy_engine=SimpleNamespace(bars={'rb':object()},datetime=datetime(2015,1,5))
 def _estimate_equity(self,bars):return self.settled_balance+self.mark_pnl
 def _is_native_openable_candidate(self,signal,direction,selected_volume):return selected_volume>0 and ((direction=='long' and self.long_entry_enabled) or (direction=='short' and self.short_entry_enabled and signal=='short_case1a'))
 def _weekly_initial_stop_qualification(self,symbol,direction,bar):
  if self.stop_error:raise self.stop_error
  return self.weekly_stop,self.weekly_valid,dict(week_end='2015-01-02')
 def _sizing_equity_snapshot(self):return dict(sizing_equity=max(0.,self.estimated_equity or self.base_capital),effective_sizing_equity_cap=max(0.,self.estimated_equity or self.base_capital),sentinel='parent')
 def _sizing_equity(self):return self._sizing_equity_snapshot()['sizing_equity']
 def _limited_available_balance(self,entry_context='flat_entry'):return max(0.,self._sizing_equity()*.9-self.total_margin_in_use-self.pending_margin_reservation)
 def _risk_amount_from_ratio(self,ratio,balance,risk_multiplier_override=None):return max(1000.,ratio*balance)*self.risk_multiplier
 def _refresh_portfolio_drawdown_state(self):
  self.portfolio_equity_high_water=max(self.portfolio_equity_high_water,self.estimated_equity,self.base_capital);self.portfolio_drawdown_pct=max(0.,(self.portfolio_equity_high_water-self.estimated_equity)/self.portfolio_equity_high_water)
 def _refresh_portfolio_margin_deleverage_state(self):self.portfolio_margin_deleverage_ratio=self.total_margin_in_use/max(1e-9,self.estimated_equity)
 def _refresh_risk_cluster_heat_pressure_snapshot(self):self.risk_cluster_heat_pressure_snapshot={'rb':5000./max(1.,self._sizing_equity())+self.portfolio_drawdown_pct}
 def _current_min_risk_cluster_heat_gate_weight(self):return 1.-self.risk_cluster_heat_pressure_snapshot.get('rb',0.)
 def _calculate_entry_sizing(self,vt_symbol,direction,bar,history,signal_data,**kwargs):
  available=self._limited_available_balance();risk=self._risk_amount_from_ratio(.02,available);volume=max(0,int(min(available//1000,risk//100))) if self.weekly_valid else 0
  return dict(selected_volume=volume,limited_balance=available,risk_amount=risk,stop_price=self.weekly_stop,parent_equity_seen=self.estimated_equity,parent_heat_seen=self.risk_cluster_heat_pressure_snapshot.get('rb'),nested={'parent':'unchanged'})
 def on_bars(self,bars):self.estimated_equity=self._estimate_equity(bars);return 'parent-day'
 def update_trade(self,trade):self.settled_balance+=trade.pnl;self.trade_costs_total+=trade.cost;self.estimated_equity=self._estimate_equity(self.strategy_engine.bars);return 'parent-fill'

def bar(day='2015-01-05',symbol='rb1510.SHFE'):
 return SimpleNamespace(datetime=datetime.fromisoformat(day),vt_symbol=symbol,close_price=100.)
def make(blocked=False,range_enabled=False,enabled=True):
 h=History(blocked);return reserve_strategy_class(Parent,h,range_enabled,'2015-01-01',enabled=enabled)(),h
def size(s,day='2015-01-05',symbol='rb1510.SHFE',direction='long',signal='long_case1a',context='flat_entry'):
 b=bar(day,symbol);return s._calculate_entry_sizing(symbol,direction,b,None,{'signal':signal},entry_context=context)

class ReserveTests(unittest.TestCase):
 def test_unrealized_loss_funded_before_parent_budget_and_raw_bridge(self):
  s,_=make();s.mark_pnl=-20000.;r=size(s)
  self.assertEqual(r['parent_equity_seen'],150000.);self.assertEqual(s.settled_balance,170000.);self.assertEqual(s.reserve_balance,130000.);self.assertEqual(s.reserve_cumulative_transfer,20000.)
  e=s.reserve_transfer_events[0];self.assertEqual((e['trading_equity_before'],e['trading_equity_after'],e['raw_account_equity'],e['total_account_equity']),(130000.,150000.,130000.,280000.));self.assertTrue(e['weekly_stop_valid']);self.assertEqual(e['phase'],'before_parent_sizing');self.assertEqual(s.base_capital,150000.)
 def test_profit_uses_all_equity_and_never_replenishes_reserve(self):
  s,_=make();s.mark_pnl=100000.;r=size(s)
  self.assertEqual(r['parent_equity_seen'],250000.);self.assertEqual(s.reserve_balance,150000.);self.assertEqual(len(s.reserve_transfer_events),0)
  s.mark_pnl=-10000.;size(s,'2015-01-06');self.assertEqual(s.reserve_balance,140000.)
  s.mark_pnl=100000.;size(s,'2015-01-07');self.assertEqual(s.reserve_balance,140000.)
  s.mark_pnl=-20000.;size(s,'2015-01-08');self.assertEqual(s.reserve_balance,130000.)
 def test_partial_and_exhausted_reserve_are_exact(self):
  s,_=make();s.mark_pnl=-140000.;size(s);self.assertEqual(s.reserve_balance,10000.)
  s.mark_pnl=-220000.;r=size(s,'2015-01-06');self.assertEqual(s.reserve_balance,0.);self.assertEqual(r['parent_equity_seen'],80000.);self.assertEqual(s.reserve_cumulative_transfer,150000.)
  s.mark_pnl=-230000.;size(s,'2015-01-07');self.assertEqual(s.reserve_balance,0.);self.assertEqual(len(s.reserve_transfer_events),2)
 def test_zero_and_negative_exhausted_equity_never_fall_back_to_base(self):
  for loss in [-300000.,-300001.]:
   s,_=make();s.mark_pnl=loss;r=size(s)
   self.assertEqual(s.reserve_balance,0.);self.assertEqual(r['selected_volume'],0);self.assertEqual(s._sizing_equity(),0.);self.assertEqual(r['limited_balance'],0.)
 def test_probe_roll_exit_add_and_warmup_do_not_transfer_or_poison_real_key(self):
  for context in ['env_probe','rollover_reopen','regular_add','donchian_add','exit']:
   s,_=make();s.mark_pnl=-10000.;size(s,context=context);self.assertEqual(s.reserve_balance,150000.);size(s);self.assertEqual(s.reserve_balance,140000.)
  s,_=make();s.mark_pnl=-10000.;size(s,'2014-12-31');self.assertEqual(s.reserve_balance,150000.)
 def test_direction_signal_permission_and_invalid_stop_do_not_transfer(self):
  for signal,direction in [('none','long'),('short_case2','short'),('short_case1a','long'),('long_case1a','short')]:
   s,_=make();s.mark_pnl=-10000.;size(s,signal=signal,direction=direction);self.assertEqual(s.reserve_balance,150000.)
  for flag in ['long_entry_enabled','weekly_valid']:
   s,_=make();setattr(s,flag,False);s.mark_pnl=-10000.;size(s);self.assertEqual(s.reserve_balance,150000.)
 def test_bad_weekly_source_raises_before_any_cash_mutation(self):
  s,_=make();s.mark_pnl=-10000.;s.stop_error=ValueError('missing-completed-week')
  with self.assertRaisesRegex(ValueError,'missing-completed-week'):size(s)
  self.assertEqual(s.settled_balance,150000.);self.assertEqual(s.reserve_balance,150000.)
 def test_disabled_case3_signal_cannot_consume_reserve(self):
  s,_=make();s.mark_pnl=-10000.;size(s,signal='long_case3')
  self.assertEqual(s.reserve_balance,150000.)
  self.assertEqual(s.reserve_transfer_events,[])
 def test_C_bottom20_rejected_without_transfer_but_A_is_not_rejected(self):
  for enabled,expected in [(True,150000.),(False,140000.)]:
   s,h=make(blocked=True,range_enabled=enabled);s.mark_pnl=-10000.;size(s,direction='short',signal='short_case1a');self.assertEqual(s.reserve_balance,expected)
   if enabled:self.assertTrue(s.reserve_signal_checks[-1]['range_would_block'])
 def test_real_range_wrapper_chain_blocks_C_before_cash_and_preserves_parent_result(self):
  for candidate,blocked,expected_cash,expected_volume in [(True,True,150000.,0),(True,False,140000.,None),(False,True,140000.,None)]:
   h=History(blocked);base=range_strategy_class(Parent,h,enabled=candidate);s=reserve_strategy_class(base,h,candidate,'2015-01-01')();s.mark_pnl=-10000.;r=size(s,direction='short',signal='short_case1a')
   self.assertEqual(s.reserve_balance,expected_cash);self.assertEqual(sum(c.__name__=='ShortBottom20RangeStrategy' for c in type(s).__mro__),1)
   self.assertEqual(len(s.short_price_range_decisions),1)
   if expected_volume is None:self.assertGreater(r['selected_volume'],0);self.assertEqual(r['nested'],{'parent':'unchanged'})
   else:self.assertEqual(r['selected_volume'],expected_volume)
 def test_same_candidate_repeat_cannot_drain_again_even_if_mark_changes(self):
  s,_=make();s.mark_pnl=-10000.;size(s);s.mark_pnl=-20000.;size(s);self.assertEqual(s.reserve_cumulative_transfer,10000.);self.assertTrue(s.reserve_signal_checks[-1]['duplicate'])
 def test_same_day_multiple_symbols_use_one_shared_account_without_double_funding(self):
  s,_=make();s.mark_pnl=-20000.;size(s);size(s,symbol='cu1505.SHFE');self.assertEqual(s.reserve_cumulative_transfer,20000.);self.assertEqual(len(s.reserve_transfer_events),1)
  s.settled_balance-=100.;size(s,symbol='au1506.SHFE');self.assertEqual(s.reserve_cumulative_transfer,20100.);self.assertEqual(s.reserve_balance,129900.)
 def test_reverse_can_fund_and_disabled_mode_has_no_money_effect(self):
  s,_=make();s.mark_pnl=-10000.;size(s,context='reverse_entry');self.assertEqual(s.reserve_balance,140000.)
  s,_=make(enabled=False);s.mark_pnl=-10000.;r=size(s);self.assertEqual(s.reserve_balance,150000.);self.assertEqual(r['parent_equity_seen'],140000.)
 def test_funding_refreshes_pressure_only_preserves_risk_memory_and_reservations(self):
  s,_=make();s.mark_pnl=-30000.;s.pending_margin_reservation=7000.;s.total_margin_in_use=10000.;s.portfolio_equity_high_water=200000.;before=(s.loss_streak,s.portfolio_equity_high_water,list(s.return_history),s.risk_multiplier,s.pending_margin_reservation)
  r=size(s);self.assertEqual(before,(s.loss_streak,s.portfolio_equity_high_water,s.return_history,s.risk_multiplier,s.pending_margin_reservation));self.assertAlmostEqual(s.portfolio_drawdown_pct,.25);self.assertAlmostEqual(s.portfolio_margin_deleverage_ratio,10000/150000);self.assertAlmostEqual(r['parent_heat_seen'],5000/150000+.25);self.assertGreater(s.current_risk_per_trade,0.)
 def test_snapshots_phase_and_fill_cost_conservation_with_no_warmup_rows(self):
  s,_=make();self.assertEqual(s.on_bars({'x':bar('2014-12-31')}),'parent-day');self.assertEqual(len(s.reserve_daily_snapshots),0)
  s.mark_pnl=-20000.;size(s);s.on_bars({'x':bar()});trade=SimpleNamespace(pnl=-105.,cost=5.,trading_date='2015-01-05');self.assertEqual(s.update_trade(trade),'parent-fill');rows=s.reserve_daily_snapshots
  self.assertEqual([r['phase'] for r in rows],['after_on_bars_settlement','after_update_trade']);self.assertLess(rows[0]['sequence'],rows[1]['sequence']);self.assertEqual(rows[-1]['raw_account_equity'],129895.);self.assertEqual(rows[-1]['total_account_equity'],279895.);self.assertEqual(rows[-1]['trade_costs_total'],5.)
 def test_nonfinite_equity_rejected_without_mutation(self):
  for value in [math.nan,math.inf,-math.inf]:
   s,_=make();s.mark_pnl=value
   with self.assertRaises(ValueError):size(s)
   self.assertEqual(s.reserve_balance,150000.)
 def test_callback_snapshot_failure_sets_strict_engine_failure_not_silent_partial(self):
  for phase in ['bar','fill']:
   s,_=make();s.mark_pnl=math.nan
   with self.assertRaises(ValueError):
    if phase=='bar':s.on_bars({'x':bar()})
    else:s.update_trade(SimpleNamespace(pnl=0.,cost=0.,trading_date='2015-01-05'))
   self.assertIn('reserve_nonfinite_trading_equity',getattr(s.strategy_engine,'intraday_execution_failure',''))
if __name__=='__main__':unittest.main()
