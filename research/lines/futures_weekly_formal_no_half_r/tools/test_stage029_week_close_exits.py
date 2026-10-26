"""Hand-calculated Stage029 adapter behavior; no market replay or download."""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest
import pandas as pd
from vnpy.trader.constant import Exchange, Interval, Offset
from vnpy.trader.object import BarData
from vnpy.trader.utility import ArrayManager
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy, PositionLayer, ProductState
from stage018_short_case2 import short_case2_weekly_strategy_class
try:
    from stage029_week_close_exits import week_close_exit_strategy_class, audit_week_close_exits
except ImportError:
    week_close_exit_strategy_class = short_case2_weekly_strategy_class
    audit_week_close_exits = None

SYMBOL = 'rb2701.SHFE'
OTHER = 'rb2705.SHFE'

def bar(day, close=100., high=110., low=90., symbol=SYMBOL, volume=10.):
    return BarData(symbol=symbol.split('.')[0], exchange=Exchange.SHFE,
        datetime=datetime.fromisoformat(day), interval=Interval.DAILY, gateway_name='TEST',
        open_price=close, high_price=high, low_price=low, close_price=close,
        volume=volume, turnover=1000., open_interest=100.)

class Harness(QmtRollPortfolioStrategy):
    """Real risk/stop/layer methods; replace IO and unrelated account statistics."""
    def __init__(self):
        self.ams={s:ArrayManager(41) for s in [SYMBOL, OTHER]}
        self.vt_symbols=list(self.ams); self.daily_mapping={}; self.states={}
        self.current_bar_date=pd.Timestamp('2026-01-02')
        self.filter_allows=True; self.enable_rsi_filter=False
        self.long_entry_enabled=True; self.short_entry_enabled=True
        self.stop_loss_pct=.1; self.enable_prev2day_stop=True
        self.trailing_stop_enabled=False; self.trailing_stop_pct=0.
        self.enable_profit_giveback_stop=False; self.atr_2x_mid_stop_enabled=False
        self.enable_rsi_partial_exit=True
        self.targets={}; self.execution_price_overrides={}; self.events=[]
        self.realized_pnl=0.; self.strategy_engine=SimpleNamespace(bars={})
        self.portfolio_margin_deleverage_count=0
    def on_bars(self, bars):
        for symbol, b in bars.items(): self.ams[symbol].update_bar(b)
        if bars: self.current_bar_date=pd.Timestamp(next(iter(bars.values())).datetime)
    def _passes_entry_filters(self, signal, history): return self.filter_allows
    def _margin_ratio_for_symbol(self, symbol): return .1
    def _record_entry_risk_diagnostic(self, **kwargs): pass
    def _record_trade_event(self, **kwargs): self.events.append(kwargs)
    def _queue_pending_close_lot(self, *args): pass
    def _record_product_direction_outcome(self, *args): pass
    def _update_streak_risk_state(self, *args, **kwargs): pass
    def get_size(self, symbol): return 10
    def set_target(self, symbol, target): self.targets[symbol]=target

class WeekCloseExitTests(unittest.TestCase):
    def strategy(self): return week_close_exit_strategy_class(Harness, {})()
    def accept(self, s, day, close=100., high=110., low=90., symbol=SYMBOL):
        b=bar(day,close,high,low,symbol); am=s.ams[symbol]
        am.weeks[tuple(b.datetime.date().isocalendar()[:2])]=(day,)
        am.update_bar(b); s.current_bar_date=pd.Timestamp(day)
        return b
    def state(self, direction='long', entry='2026-01-02', stop=95., symbol=SYMBOL):
        return ProductState(product_vt_symbol='rb.SHFE', contract_vt_symbol=symbol,
            direction=direction, entry_date=entry, bars_since_entry=99,
            layers=[PositionLayer('base',direction,2,100.,stop,110.,90.,'fixture',entry)])
    def daily(self,s,day='2026-01-07',close=90.,high=111.,low=80.,symbol=SYMBOL):
        b=bar(day,close,high,low,symbol); s.current_bar_date=pd.Timestamp(day)
        return b
    def test_midweek_daily_cross_does_not_close_base_or_inline_ma(self):
        s=self.strategy(); self.accept(s,'2026-01-02'); st=self.state()
        b=self.daily(s)
        self.assertEqual(s._process_layer_stops(st,b),'')
        self.assertEqual(len(st.layers),1)
        self.assertFalse(s._stop_triggered('long',b,95.))
        self.assertEqual(s.events,[])
    def test_week_close_cross_closes_at_week_close(self):
        s=self.strategy(); b=self.accept(s,'2026-01-09',90.,130.,70.); st=self.state()
        self.assertEqual(s._process_layer_stops(st,b),'long_base_stop')
        self.assertEqual(st.layers,[]); self.assertEqual(s.targets[SYMBOL],0)
        self.assertEqual(s.events[-1]['price'],90.)
        self.assertEqual(s.realized_pnl,-200.)
    def test_week_low_cross_is_not_close_confirmation(self):
        s=self.strategy(); b=self.accept(s,'2026-01-09',100.,130.,70.); st=self.state()
        self.assertEqual(s._process_layer_stops(st,b),'')
        self.assertFalse(s._stop_triggered('long',b,95.))
        self.assertFalse(s._stop_triggered('short',b,105.))
    def test_initial_stop_uses_week_low_instead_of_last_day_low(self):
        s=self.strategy(); self.accept(s,'2026-01-02',100.,130.,80.)
        b=self.daily(s,close=105.,high=106.,low=104.)
        h=s._build_history_df(s.ams[SYMBOL])
        self.assertEqual(s._entry_stop_price('long',b,h,True),80.)
        row=s.initial_stop_audit[-1]
        self.assertEqual(row['weekly_close'],100.); self.assertEqual(row['plan_reference_close'],105.)
        self.assertTrue(row['direction_valid']); self.assertEqual(row['week_end'],'2026-01-02')
    def test_midweek_open_retains_daily_entry_and_weekly_initial_extrema(self):
        s=self.strategy(); self.accept(s,'2026-01-02',100.,130.,80.)
        b=self.daily(s,close=105.,high=106.,low=104.); h=s._build_history_df(s.ams[SYMBOL])
        st=ProductState('rb.SHFE')
        s._open_position(st,SYMBOL,'long',2,b,'long_rollover',h,{},sizing_snapshot={'stop_price':80.})
        self.assertEqual(st.layers[0].entry_price,105.)
        self.assertEqual((st.layers[0].highest_price,st.layers[0].lowest_price),(130.,80.))
        self.assertEqual(st.entry_date,'20260107')
    def test_wrong_direction_weekly_roll_stop_fails_without_repair(self):
        s=self.strategy(); self.accept(s,'2026-01-02',100.,130.,80.)
        b=self.daily(s,close=70.,high=75.,low=65.)
        with self.assertRaisesRegex(ValueError,'initial_stop_wrong_direction'):
            s._entry_stop_price('long',b,s._build_history_df(s.ams[SYMBOL]),True)
        self.assertEqual(s.initial_stop_audit[-1]['stop_price'],80.)
        self.assertFalse(s.initial_stop_audit[-1]['direction_valid'])
    def test_dynamic_extrema_and_profit_lock_update_on_week_only(self):
        s=self.strategy(); self.accept(s,'2026-01-02'); st=self.state(stop=70.)
        s.trailing_stop_enabled=True
        b=self.daily(s,close=140.,high=150.,low=120.)
        s._update_dynamic_stops(st,b,s._build_history_df(s.ams[SYMBOL]))
        self.assertEqual((st.layers[0].highest_price,st.layers[0].max_profit_pct,st.layers[0].stop_price),(110.,0.,70.))
        b=self.accept(s,'2026-01-09',120.,160.,75.)
        s._update_dynamic_stops(st,b,s._build_history_df(s.ams[SYMBOL]))
        self.assertEqual((st.layers[0].highest_price,st.layers[0].lowest_price),(160.,75.))
        self.assertAlmostEqual(st.layers[0].max_profit_pct,.2)
        self.assertAlmostEqual(st.layers[0].stop_price,115.)
    def test_atr_midpoint_uses_whole_week_extrema(self):
        s=self.strategy()
        for i,day in enumerate(pd.date_range('2025-09-26', periods=14, freq='W-FRI')):
            self.accept(s,day.strftime('%Y-%m-%d'),100.,101.,99.)
        b=self.accept(s,'2026-01-09',120.,130.,90.); st=self.state(stop=70.)
        s.atr_2x_mid_stop_enabled=True
        last_day=bar('2026-01-09',120.,121.,119.)
        s._update_dynamic_stops(st,last_day,s._build_history_df(s.ams[SYMBOL]))
        self.assertEqual(st.layers[0].stop_price,110.)
    def test_prev2_requires_two_accepted_post_entry_weeks_not_daily_age(self):
        s=self.strategy(); self.accept(s,'2025-12-26',100.,110.,95.)
        self.accept(s,'2026-01-02',100.,110.,95.); st=self.state(stop=70.)
        b=self.accept(s,'2026-01-09',90.,100.,80.)
        self.assertEqual(s._process_prev2day_stop(st,b,s._build_history_df(s.ams[SYMBOL])),'')
        self.assertIsNone(st.prev2day_stop_price)
        b=self.accept(s,'2026-01-23',70.,100.,65.)
        self.assertEqual(s._process_prev2day_stop(st,b,s._build_history_df(s.ams[SYMBOL])),'long_prev2day_stop')
        self.assertEqual(s.events[-1]['price'],70.)
        self.assertEqual(st.bars_since_entry,0)
    def test_prev2_week_age_accepts_real_compact_entry_date(self):
        s=self.strategy(); self.accept(s,'2026-01-02',100.,110.,95.)
        self.accept(s,'2026-01-09',100.,110.,90.)
        b=self.accept(s,'2026-01-16',70.,100.,60.)
        st=self.state(entry='20260102',stop=50.)
        self.assertEqual(s._process_prev2day_stop(st,b,s._build_history_df(s.ams[SYMBOL])),'long_prev2day_stop')

    def test_holiday_thursday_is_effective_week_end(self):
        days=['2026-02-09','2026-02-10','2026-02-11','2026-02-12']
        s=self.strategy(); am=s.ams[SYMBOL]
        am.weeks[tuple(datetime.fromisoformat(days[0]).date().isocalendar()[:2])]=tuple(days)
        for day in days:
            am.update_bar(bar(day,90. if day==days[-1] else 100.,110.,80.))
        b=self.daily(s,days[-1],close=90.)
        self.assertEqual(s._process_layer_stops(self.state(),b),'long_base_stop')
    def test_stale_fresh_flag_on_absent_contract_cannot_trigger(self):
        s=self.strategy(); self.accept(s,'2026-01-02',90.,110.,80.)
        self.assertTrue(s.ams[SYMBOL].fresh)
        b=self.daily(s,close=90.)
        self.assertFalse(s._stop_triggered('long',b,95.))
    def test_old_contract_uses_own_week_not_target_contract(self):
        s=self.strategy(); self.accept(s,'2026-01-09',100.,120.,80.,SYMBOL)
        self.accept(s,'2026-01-09',70.,90.,60.,OTHER)
        b=self.daily(s,'2026-01-09',100.,120.,80.)
        self.assertFalse(s._stop_triggered('long',b,95.))
        self.assertEqual(s._process_layer_stops(self.state(),b),'')
    def test_missing_week_and_reset_epoch_completed_fail_closed(self):
        s=self.strategy(); b=self.daily(s)
        with self.assertRaisesRegex(ValueError,'completed_week_missing'):
            s._entry_stop_price('long',b,pd.DataFrame(),True)
        self.accept(s,'2024-01-05'); am=s.ams[SYMBOL]
        am.weeks[(2026,2)]=('2026-01-05','2026-01-09')
        am.update_bar(bar('2026-01-05'))
        self.assertEqual(am.inner.count,0); self.assertTrue(am.completed)
        with self.assertRaisesRegex(ValueError,'completed_week_missing'):
            s._entry_stop_price('long',self.daily(s,'2026-01-07'),pd.DataFrame(),True)
    def test_completed_week_inner_mismatch_fails_closed(self):
        s=self.strategy(); self.accept(s,'2026-01-02'); s.ams[SYMBOL].inner.close_array[-1]=777.
        with self.assertRaisesRegex(ValueError,'completed_week_inner_mismatch'):
            s._entry_stop_price('long',self.daily(s),pd.DataFrame(),True)
    def test_short_case2_is_blocked_long_case2_remains_native_openable(self):
        s=self.strategy()
        self.assertFalse(s._is_native_openable_candidate('short_case2','short',1))
        self.assertTrue(s._is_native_openable_candidate('short_case1a','short',1))
        self.assertTrue(s._is_native_openable_candidate('long_case2','long',1))
        self.assertFalse(s.research_short_case2_enabled)
    def test_rsi_exit_off_despite_extreme_rsi_and_locked_contract(self):
        s=self.strategy(); st=self.state(); b=self.daily(s)
        self.assertFalse(s.enable_rsi_partial_exit)
        self.assertEqual(s._process_rsi_partial_exit(st,b,100.),'')
        self.assertEqual(len(st.layers),1); self.assertEqual(s.events,[])
        s.enable_rsi_partial_exit=True
        with self.assertRaisesRegex(ValueError,'locked_contract_changed'):
            s.on_bars({SYMBOL:b})
    def test_daily_margin_deleverage_is_not_weekly_gated(self):
        s=self.strategy(); self.accept(s,'2026-01-02'); st=self.state(); b=self.daily(s)
        s.enable_portfolio_margin_deleverage=True
        s.portfolio_margin_deleverage_pressure=2.; s.portfolio_margin_deleverage_min_pressure=1.
        s.portfolio_margin_deleverage_layer_kinds='base'
        self.assertEqual(s._process_portfolio_margin_deleverage(st,b),'long_portfolio_margin_deleverage')
        self.assertEqual(st.layers,[]); self.assertEqual(s.targets[SYMBOL],0)
        self.assertEqual(s.events[-1]['price'],90.)
    def test_reconcile_reconstruction_is_counted_and_rejected_by_acceptance(self):
        s=self.strategy(); st=ProductState('rb.SHFE'); s._reconcile_state_with_position(st,1,self.daily(s))
        self.assertEqual(len(st.layers),1)
        self.assertEqual(s.reconciliation_rebuilt_layer_count,1)
        with self.assertRaisesRegex(ValueError,'reconciliation_rebuilt_layer'):
            audit_week_close_exits(s)
    def test_short_week_close_and_initial_stop_remain_mirrored(self):
        s=self.strategy(); b=self.accept(s,'2026-01-09',110.,120.,80.)
        self.assertEqual(s._entry_stop_price('short',b,s._build_history_df(s.ams[SYMBOL]),True),120.)
        self.assertEqual(s._process_layer_stops(self.state(direction='short',stop=105.),b),'short_base_stop')
        self.assertEqual(s.events[-1]['price'],110.)
        self.assertEqual(s.realized_pnl,-200.)
    def test_supplied_daily_stop_cannot_bypass_weekly_initial_stop(self):
        s=self.strategy(); self.accept(s,'2026-01-02',100.,130.,80.)
        st=ProductState('rb.SHFE'); b=self.daily(s,close=105.,high=106.,low=104.)
        with self.assertRaisesRegex(ValueError,'initial_stop_snapshot_mismatch'):
            s._open_position(st,SYMBOL,'long',2,b,'long_rollover',s._build_history_df(s.ams[SYMBOL]),{},
                sizing_snapshot={'stop_price':94.5})
        self.assertEqual(st.layers,[])
    def test_stale_bar_date_cannot_authorize_old_fresh_week(self):
        s=self.strategy(); old=self.accept(s,'2026-01-02',90.,110.,80.)
        s.current_bar_date=pd.Timestamp('2026-01-07')
        with self.assertRaisesRegex(ValueError,'technical_bar_date_mismatch'):
            s._stop_triggered('long',old,95.)
    def test_frames_audit_rejects_rsi_exit_and_short2_open(self):
        self.assertTrue(callable(audit_week_close_exits),'Stage029 audit missing')
        for frame in [pd.DataFrame([{'reason':'long_rsi_partial_exit_half'}]),
                      pd.DataFrame([{'signal':'short_case2','candidate_status':'opened'}]),
                      pd.DataFrame([{'signal':'short_case2','offset':'开'}]),
                      pd.DataFrame([{'signal':'short_case2','offset':Offset.OPEN}])]:
            with self.subTest(columns=list(frame)):
                with self.assertRaisesRegex(ValueError,'forbidden_week_close_events'):
                    audit_week_close_exits(self.strategy(),{'events':frame})
    def test_accepted_new_epoch_does_not_reuse_old_completed_week_age(self):
        s=self.strategy()
        for day in ['2024-01-05','2024-01-12','2024-01-19']:
            self.accept(s,day,100.,110.,95.)
        b=self.accept(s,'2026-01-09',70.,100.,60.)
        self.assertEqual(s.ams[SYMBOL].inner.count,1)
        st=self.state(entry='20260102',stop=50.)
        self.assertEqual(s._process_prev2day_stop(st,b,s._build_history_df(s.ams[SYMBOL])),'')
        self.assertEqual(s.weekly_stop_audit[-1]['accepted_post_entry_weeks'],1)
    def test_all_declared_locks_are_enforced_before_daily_processing(self):
        for name,value in [('enable_add_position',True),('enable_donchian_add_position',True),
                           ('enable_post_entry_quality_add',True),('reverse_on_opposite_signal',True),
                           ('exit_on_alignment_break',True),('rollover_shape_history_mode','backwards_ratio_continuous')]:
            with self.subTest(name=name):
                s=self.strategy(); setattr(s,name,value)
                with self.assertRaisesRegex(ValueError,'locked_contract_changed'):
                    s.on_bars({SYMBOL:bar('2026-01-07')})

    def test_clean_acceptance_and_guard_failure_cannot_be_hidden(self):
        self.assertTrue(callable(audit_week_close_exits),'Stage029 audit missing')
        s=self.strategy(); self.assertTrue(audit_week_close_exits(s)['accepted'])
        s.weekly_stop_guard_failures.append({'reason':'fixture'})
        with self.assertRaisesRegex(ValueError,'weekly_stop_guard_failures'):
            audit_week_close_exits(s)

if __name__ == '__main__': unittest.main()
