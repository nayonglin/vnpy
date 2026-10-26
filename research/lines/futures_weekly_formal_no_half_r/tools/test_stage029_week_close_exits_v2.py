"""Stage029 v2 admission tests; preserve frozen v1 and failed R001."""
from datetime import datetime
from types import SimpleNamespace
from copy import deepcopy
import unittest
import json
import pandas as pd
from vnpy.trader.constant import Offset, Direction
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy, ProductState
from test_stage029_week_close_exits import Harness, bar, SYMBOL as FIXTURE_SYMBOL, OTHER as FIXTURE_OTHER
import test_stage029_week_close_exits as v1_fixture
SYMBOL="rb1510.SHFE"
OTHER="rb1505.SHFE"
from stage029_week_close_exits import week_close_exit_strategy_class as v1_factory
try:
    from stage029_week_close_exits_v2 import week_close_exit_strategy_class, audit_week_close_exits
except ImportError:
    week_close_exit_strategy_class=v1_factory
    audit_week_close_exits=None

class SizingHarness(Harness):
    def __init__(self):
        super().__init__()
        self.ams={SYMBOL:self.ams.pop(FIXTURE_SYMBOL),OTHER:self.ams.pop(FIXTURE_OTHER)}
        self.vt_symbols=list(self.ams)
        self.trade_event_diagnostics=[]
        self.parent_sizing_calls=0
        self.parent_result={'selected_volume':3,'stop_price':80.,'nested':{'all_parent_guards':'unchanged'},
            'risk_amount':123.4,'margin_per_contract':100.,'sentinel':object()}
        self.pending_margin_reservation=0.; self.pending_cluster_margin_reservation={}
        self.pending_active_products=set(); self.target_data=self.targets
        self.estimated_equity=self.base_capital=150000.; self.margin_in_use=0.
        self.portfolio_drawdown_pct=0.; self.loss_streak=0; self.profit_recovery_streak=0
        self.portfolio_equity_high_water=150000.
        self.portfolio_overheat_cooldown_reason=''
        self.portfolio_overheat_cooldown_prior_drawdown_pct=0.
        self.portfolio_overheat_cooldown_prior_ret20=float('nan')
        self.portfolio_overheat_cooldown_prior_ret60=float('nan')
        self.portfolio_volatility_budget_scale=1.
        self.portfolio_volatility_budget_realized_annual_vol=0.
        self.current_env_gate_snapshot={}
        self.cluster_margin_usage={}; self.cluster_unrealized_pnl={}
        self.product_direction_outcome_history={}
        self._recovery_sleeve_last_open_timestamp=None
        self.source_symbol_by_contract={SYMBOL:'rb.SHFE',OTHER:'rb.SHFE'}
        self.rollover_shape_same_volume_diagnostics=[]
        self.entry_candidate_snapshots=[]
    def _calculate_entry_sizing(self, vt_symbol,direction,bar,history,signal_data,
            risk_mode_override=None,entry_context='flat_entry',apply_env_gate=True,
            active_positions_before=None,correlation_snapshot=None):
        self.parent_sizing_calls+=1
        self._entry_stop_price(direction,bar,history,True)
        return self.parent_result
    def get_target(self,symbol): return self.targets.get(symbol,0)
    def get_pricetick(self,symbol): return 1.
    def _reserved_margin_in_use(self): return self.margin_in_use+self.pending_margin_reservation
    def _risk_cluster_for_symbol(self,symbol): return ''
    def _rollover_released_risk_snapshot(self,**kwargs): return {}
    def _apply_rollover_released_risk_snapshot(self,snapshot): pass
    def _rollover_reopen_drawdown_guard_fields(self):
        return {'rollover_reopen_drawdown_guard_enabled':0,'rollover_reopen_drawdown_guard_passed':1}

class WeekCloseAdmissionV2Tests(unittest.TestCase):
    def strategy(self,base=SizingHarness): return week_close_exit_strategy_class(base,{})()
    def accept(self,s,day='2015-03-13',close=2493.,high=2516.,low=2449.,symbol=SYMBOL):
        return v1_fixture.WeekCloseExitTests.accept(self,s,day,close,high,low,symbol)
    def request(self,s,close=2520.,day='2015-03-16',symbol=SYMBOL):
        b=bar(day,close,close+5.,close-5.,symbol); s.current_bar_date=pd.Timestamp(day)
        return b
    def sizing(self,s,b,direction='short',context='rollover_reopen'):
        return s._calculate_entry_sizing(b.vt_symbol,direction,b,s._build_history_df(s.ams[b.vt_symbol]),
            {'signal':'short_case1a' if direction=='short' else 'long_case2'},entry_context=context)
    def reject(self):
        s=self.strategy(); self.accept(s); b=self.request(s)
        try: result=self.sizing(s,b)
        except ValueError as exc: self.fail('v2 must reject only this candidate with zero size, got '+str(exc))
        return s,result
    def evidence(self,context='rollover_reopen',signal_date='2015-03-16'):
        return {'entry_candidates':pd.DataFrame(columns=['date','contract_vt_symbol','direction','entry_context','candidate_status','selected_volume']),
            'rollover_shape_same_volume':pd.DataFrame([dict(date=signal_date,target_contract_vt_symbol=SYMBOL,
                direction='short',final_volume=0,selected_volume_before_exact_gate=0,status='skipped')]) if context=='rollover_reopen' else pd.DataFrame(),
            'trades':pd.DataFrame(columns=['order_id','vt_symbol','direction','offset','volume']),
            'execution_anchor_requests':pd.DataFrame(columns=['order_id','signal_date','vt_symbol','offset'])}
    def test_actual_rb_midweek_wrong_side_is_zero_without_parent_budget_or_mutation(self):
        s,result=self.reject()
        self.assertEqual(result['selected_volume'],0); self.assertEqual(result['stop_price'],2516.)
        self.assertEqual(result['plan_reference_close'],2520.)
        self.assertEqual(result['budget_evaluation'],'not_evaluated')
        self.assertEqual(s.parent_sizing_calls,0)
        self.assertEqual(s.initial_stop_audit,[]); self.assertEqual(s.weekly_stop_guard_failures,[])
        row=s.invalid_weekly_stop_rejections[-1]
        self.assertEqual((row['signal_date'],row['week_end'],row['direction'],row['entry_context']),
            ('2015-03-16','2015-03-13','short','rollover_reopen'))
        self.assertEqual(s.targets,{}); self.assertEqual(s.pending_margin_reservation,0.)
        self.assertEqual(s.pending_active_products,set())
    def test_long_mirror_and_equal_stop_boundary_reject_both_sides(self):
        for direction,plan in [('long',70.),('long',80.),('short',2516.)]:
            with self.subTest(direction=direction,plan=plan):
                s=self.strategy()
                self.accept(s,close=100.,high=130.,low=80.) if direction=='long' else self.accept(s)
                result=self.sizing(s,self.request(s,close=plan),direction)
                self.assertEqual(result['selected_volume'],0)
                self.assertEqual(s.parent_sizing_calls,0)
    def test_valid_path_returns_entire_parent_dictionary_object_unchanged(self):
        s=self.strategy(); self.accept(s)
        result=self.sizing(s,self.request(s,close=2515.))
        self.assertIs(result,s.parent_result); self.assertEqual(s.parent_sizing_calls,1)
        self.assertEqual(s.invalid_weekly_stop_rejections,[])
        self.assertEqual(s.initial_stop_audit[-1]['stop_price'],2516.)
    def test_stage804_long_tighter_stop_is_preserved_by_qualification(self):
        from analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine import QmtRollPortfolioStrategyStage847C9StopRetry as Formal
        class FormalHarness(Formal,SizingHarness):
            __init__=SizingHarness.__init__
            _calculate_entry_sizing=SizingHarness._calculate_entry_sizing
            get_target=SizingHarness.get_target
            get_size=SizingHarness.get_size
            get_pricetick=SizingHarness.get_pricetick
            _margin_ratio_for_symbol=SizingHarness._margin_ratio_for_symbol
            _reserved_margin_in_use=SizingHarness._reserved_margin_in_use
        s=self.strategy(FormalHarness); self.accept(s,close=100.,high=130.,low=80.)
        result=self.sizing(s,self.request(s,close=85.),'long')
        self.assertEqual(result['stop_price'],90.)
        self.assertEqual(result['selected_volume'],0)
    def test_valid_stage804_diagnostics_match_v1_exactly_and_restore_same_object(self):
        from analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine import QmtRollPortfolioStrategyStage847C9StopRetry as Formal
        class FormalHarness(Formal,SizingHarness):
            __init__=SizingHarness.__init__
            _calculate_entry_sizing=SizingHarness._calculate_entry_sizing
        old=v1_factory(FormalHarness,{})(); new=self.strategy(FormalHarness)
        for s in [old,new]:
            self.accept(s,close=100.,high=130.,low=80.)
            self.sizing(s,self.request(s,close=105.),'long')
        self.assertEqual(len(old.trade_event_diagnostics),1)
        self.assertEqual(new.trade_event_diagnostics,old.trade_event_diagnostics)
        original=new.trade_event_diagnostics
        self.sizing(new,self.request(new,close=105.),'long')
        self.assertIs(new.trade_event_diagnostics,original)
        self.assertEqual(len(new.trade_event_diagnostics),2)

    def test_missing_week_wrong_day_epoch_and_nan_remain_hard_failures(self):
        for fault in ['missing','date','epoch','nan','future']:
            with self.subTest(fault=fault):
                s=self.strategy()
                if fault!='missing': self.accept(s)
                b=self.request(s)
                if fault=='date': s.current_bar_date=pd.Timestamp('2015-03-17')
                if fault=='epoch': s.ams[SYMBOL].inner=type(s.ams[SYMBOL].inner)(41)
                if fault=='nan': s.ams[SYMBOL].completed[-1]['close']=float('nan')
                if fault=='future': s.ams[SYMBOL].completed[-1]['week_end']='2015-03-20'
                with self.assertRaises(ValueError): self.sizing(s,b)
                self.assertEqual(s.invalid_weekly_stop_rejections,[])
    def test_unknown_direction_and_invalid_plan_prices_are_hard_failures(self):
        for direction,plan in [('other',2520.),('long',float('nan')),('short',0.)]:
            with self.subTest(direction=direction,plan=plan):
                s=self.strategy(); self.accept(s)
                with self.assertRaises(ValueError): self.sizing(s,self.request(s,close=plan),direction)
                self.assertEqual(s.invalid_weekly_stop_rejections,[])
    def test_nonfinite_or_nonpositive_formal_stop_is_not_zero_admission(self):
        for stop in [0.,-1.,float('nan'),float('inf')]:
            with self.subTest(stop=stop):
                class BadStop(SizingHarness):
                    def _entry_stop_price(self,*args): return stop
                s=self.strategy(BadStop); self.accept(s)
                with self.assertRaisesRegex(ValueError,'invalid_weekly_initial_stop'):
                    self.sizing(s,self.request(s))
                self.assertEqual(s.invalid_weekly_stop_rejections,[])
    def test_valid_parent_failure_is_rethrown_without_zero_conversion(self):
        marker=RuntimeError('parent_budget_fault')
        class Fault(SizingHarness):
            def _calculate_entry_sizing(self,*args,**kwargs): raise marker
        s=self.strategy(Fault); self.accept(s)
        with self.assertRaises(RuntimeError) as got: self.sizing(s,self.request(s,close=2515.))
        self.assertIs(got.exception,marker); self.assertEqual(s.invalid_weekly_stop_rejections,[])
    def test_original_v1_open_and_stop_hard_gates_are_preserved(self):
        s,result=self.reject(); b=self.request(s)
        with self.assertRaisesRegex(ValueError,'initial_stop_wrong_direction'):
            s._open_position(ProductState('rb.SHFE'),SYMBOL,'short',1,b,'rollover_reopen',
                s._build_history_df(s.ams[SYMBOL]),{},sizing_snapshot=result)
    def test_rollover_closes_old_contract_and_does_not_target_or_reserve_new(self):
        s=self.strategy(); s.enable_rollover_shape_same_volume_reopen=True
        s.rollover_reopen_enabled=True; s.rollover_shape_volume_policy='shrink_to_allowed'
        for i,day in enumerate(pd.date_range('2014-10-24',periods=21,freq='W-FRI')):
            close=2693.-i*10.
            self.accept(s,day.strftime('%Y-%m-%d'),close,close+23.,close-44.)
        self.accept(s,'2015-03-13',2493.,2516.,2449.)
        b=self.request(s); old=bar('2015-03-16',2500.,2510.,2490.,OTHER)
        st=v1_fixture.WeekCloseExitTests.state(self,'short',entry='20150102',symbol=OTHER)
        s.strategy_engine.bars={SYMBOL:b,OTHER:old}
        s._handle_rollover(st,SYMBOL,s.strategy_engine.bars)
        self.assertEqual(st.layers,[]); self.assertEqual(s.targets,{OTHER:0})
        self.assertEqual(s.pending_margin_reservation,0.)
        self.assertEqual(s.events[-1]['reason'],'rollover_close')
        self.assertEqual(s.rollover_shape_same_volume_diagnostics[-1]['final_volume'],0)
        self.assertEqual(s.rollover_shape_same_volume_diagnostics[-1]['status'],'skipped')
    def test_invalid_candidate_does_not_gate_other_contract_daily_margin(self):
        s,result=self.reject(); b=self.request(s,symbol=OTHER,close=90.)
        st=v1_fixture.WeekCloseExitTests.state(self,symbol=OTHER)
        s.enable_portfolio_margin_deleverage=True
        s.portfolio_margin_deleverage_pressure=2.; s.portfolio_margin_deleverage_min_pressure=1.
        s.portfolio_margin_deleverage_layer_kinds='base'
        self.assertEqual(s._process_portfolio_margin_deleverage(st,b),'long_portfolio_margin_deleverage')
        self.assertEqual(st.layers,[]); self.assertEqual(s.targets,{OTHER:0})
    def test_callback_failure_is_registered_and_original_exception_rethrown(self):
        marker=ValueError('source_contract_fault')
        class Fault(SizingHarness):
            def on_bars(self,bars): raise marker
        s=self.strategy(Fault)
        with self.assertRaises(ValueError) as got: s.on_bars({SYMBOL:bar('2015-03-16')})
        self.assertIs(got.exception,marker)
        self.assertIn('source_contract_fault',s.strategy_engine.intraday_execution_failure)
    def test_callback_success_result_is_unchanged(self):
        class Success(SizingHarness):
            def on_bars(self,bars): return 'unchanged'
        s=self.strategy(Success)
        self.assertEqual(s.on_bars({}),'unchanged')
        self.assertFalse(hasattr(s.strategy_engine,'intraday_execution_failure'))
    def test_invalid_snapshot_is_consumable_by_real_candidate_logger(self):
        s,result=self.reject(); b=self.request(s)
        s._record_entry_candidate_snapshot(product_vt_symbol='rb.SHFE',contract_vt_symbol=SYMBOL,
            direction='short',bar=b,signal='short_case1a',entry_context='flat_entry',
            candidate_status='skipped',skip_reason='sizing_zero_volume',signal_data={},
            sizing_snapshot=result,active_positions_before=0)
        row=s.entry_candidate_snapshots[-1]
        self.assertEqual(row['stop_price'],2516.)
        self.assertEqual(row['selected_volume'],0)
        self.assertEqual(row['risk_per_contract'],0.)
        self.assertEqual(row['is_opened'],0)
        self.assertEqual(row['incremental_margin_budget_gate_passed'],0)
        self.assertEqual(row['rollover_reopen_drawdown_guard_passed'],0)
    def test_valid_real_parent_sizing_full_result_matches_v1(self):
        class RealSizing(SizingHarness):
            _calculate_entry_sizing=QmtRollPortfolioStrategy._calculate_entry_sizing
        old=v1_factory(RealSizing,{})(); new=self.strategy(RealSizing)
        results=[]
        for s in [old,new]:
            self.accept(s)
            results.append(self.sizing(s,self.request(s,close=2515.)))
        self.assertGreater(len(results[0]),40)
        self.assertEqual(json.dumps(results[0],sort_keys=True,default=str),
                         json.dumps(results[1],sort_keys=True,default=str))
    def test_audit_rejects_ownership_mutation_or_invalid_receipt(self):
        self.assertTrue(callable(audit_week_close_exits),'v2 audit missing')
        for field in ['ownership_after','stop_price']:
            with self.subTest(field=field):
                s,_=self.reject()
                if field=='ownership_after':
                    s.invalid_weekly_stop_rejections[0][field]['pending_margin_reservation']=100.
                else: s.invalid_weekly_stop_rejections[0][field]=0.
                with self.assertRaises(ValueError): audit_week_close_exits(s,self.evidence())
    def test_audit_does_not_blacklist_another_context_same_signal_day(self):
        self.assertTrue(callable(audit_week_close_exits),'v2 audit missing')
        s,_=self.reject(); frames=self.evidence()
        frames['entry_candidates']=pd.DataFrame([dict(date='2015-03-16',contract_vt_symbol=SYMBOL,
            direction='short',entry_context='flat_entry',candidate_status='opened',selected_volume=1)])
        frames['trades']=pd.DataFrame([dict(order_id='T1',vt_symbol=SYMBOL,direction='空',offset='开',volume=1)])
        frames['execution_anchor_requests']=pd.DataFrame([dict(order_id='T1',signal_date='2015-03-16',
            vt_symbol=SYMBOL,offset='开')])
        self.assertTrue(audit_week_close_exits(s,frames)['accepted'])

    def test_audit_requires_corresponding_rejection_evidence(self):
        self.assertTrue(callable(audit_week_close_exits),'v2 audit missing')
        s,_=self.reject()
        with self.assertRaisesRegex(ValueError,'rejection_evidence_missing'):
            audit_week_close_exits(s,{})
        self.assertTrue(audit_week_close_exits(s,self.evidence())['accepted'])
    def test_audit_rejects_opened_candidate_or_targeted_rollover(self):
        self.assertTrue(callable(audit_week_close_exits),'v2 audit missing')
        s,_=self.reject(); frames=self.evidence()
        frames['rollover_shape_same_volume'].loc[0,['final_volume','status']]=[1,'targeted']
        with self.assertRaisesRegex(ValueError,'rejected_candidate_opened'):
            audit_week_close_exits(s,frames)
    def test_audit_joins_order_signal_date_not_execution_day_or_contract_blacklist(self):
        self.assertTrue(callable(audit_week_close_exits),'v2 audit missing')
        for signal_day,rejected in [('2015-03-16',True),('2015-03-20',False)]:
            with self.subTest(signal_day=signal_day):
                s,_=self.reject(); frames=self.evidence()
                frames['trades']=pd.DataFrame([dict(order_id='T1',vt_symbol=SYMBOL,direction=Direction.SHORT,
                    offset=Offset.OPEN,volume=1,date='2015-03-17')])
                frames['execution_anchor_requests']=pd.DataFrame([dict(order_id='T1',signal_date=signal_day,
                    vt_symbol=SYMBOL,offset='开')])
                if rejected:
                    with self.assertRaisesRegex(ValueError,'rejected_candidate_open_fill'):
                        audit_week_close_exits(s,frames)
                else: self.assertTrue(audit_week_close_exits(s,frames)['accepted'])
    def test_audit_missing_order_anchor_cannot_claim_no_rejected_fills(self):
        self.assertTrue(callable(audit_week_close_exits),'v2 audit missing')
        s,_=self.reject(); frames=self.evidence()
        frames['trades']=pd.DataFrame([dict(order_id='T1',vt_symbol=SYMBOL,direction='空',offset='开',volume=1)])
        with self.assertRaisesRegex(ValueError,'rejection_execution_anchor_missing'):
            audit_week_close_exits(s,frames)

if __name__=='__main__': unittest.main()
