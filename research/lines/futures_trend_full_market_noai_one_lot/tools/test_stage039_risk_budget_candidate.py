"""Actual native sizing with synthetic state; no data loader or financial replay."""
from dataclasses import FrozenInstanceError, asdict
from datetime import datetime
import importlib
import math
from pathlib import Path
from types import SimpleNamespace
import unittest

import pandas as pd

HERE = Path(__file__).resolve().parent
ENTRY = HERE / 'stage039_risk_budget_candidate.py'
VT = 'rb202005.SHFE'


class RiskBudgetCandidateTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(ENTRY.exists(), 'native-risk-budget candidate is not implemented')
        from vnpy.trader.setting import SETTINGS
        SETTINGS['log.file'] = False
        self.module = importlib.import_module('stage039_risk_budget_candidate')

    def fixture(self, **overrides):
        from vnpy_portfoliostrategy.template import StrategyTemplate
        cls = self.module.FullMarketNativeRiskBudgetOneLot
        strategy = object.__new__(cls)
        settings = self.module.candidate_overrides(Path('/tmp/not_read_universe.csv'), product_count=93)
        # Exact-boundary synthetic budget: all real native gates remain in use.
        settings.update(min_risk_per_trade=20.0, max_risk_per_trade=20.0)
        settings.update(overrides)
        engine = SimpleNamespace(get_size=lambda strategy, symbol:10,
                                 get_pricetick=lambda strategy, symbol:1,
                                 bars={})
        StrategyTemplate.__init__(strategy, engine, 'risk_budget_fixture', [VT], settings)
        strategy.source_symbol_by_contract = {VT:'rb.SHFE'}
        strategy.product_symbols = ['rb.SHFE']
        strategy.states = {}
        for field,value in {
            'base_capital':1000000.0,'estimated_equity':1000000.0,'portfolio_equity_high_water':1000000.0,
            'portfolio_drawdown_pct':0.0,'total_margin_in_use':0.0,'pending_margin_reservation':0.0,
            'loss_streak':0,'profit_recovery_streak':0,'portfolio_volatility_budget_scale':1.0,
            'portfolio_volatility_budget_realized_annual_vol':0.0,'portfolio_overheat_cooldown_scale':1.0,
            'portfolio_overheat_cooldown_reason':'','portfolio_overheat_cooldown_prior_drawdown_pct':0.0,
            'portfolio_overheat_cooldown_prior_ret20':0.0,'portfolio_overheat_cooldown_prior_ret60':0.0,
            '_recovery_sleeve_last_open_timestamp':None,'recovery_sleeve_open_count':0,
            'stage830_margin_cap_reduce_count':0,'stage830_margin_cap_block_count':0,
        }.items(): setattr(strategy,field,value)
        for field in ('pending_cluster_margin_reservation','cluster_margin_usage','cluster_unrealized_pnl',
                      'current_env_gate_snapshot','risk_cluster_heat_pressure_snapshot',
                      'risk_cluster_same_direction_multi_snapshot','product_direction_outcome_history','pending_entry_diagnostics'):
            setattr(strategy,field,{})
        strategy.pending_active_products = set()
        for field in ('trade_event_diagnostics','entry_risk_diagnostics','long_signal_atr_shock_diagnostics',
                      'long_signal_range_atr_diagnostics','stage830_margin_cap_events'):
            setattr(strategy,field,[])
        from vnpy.trader.object import BarData
        from vnpy.trader.constant import Exchange
        bar = BarData(symbol='rb202005', exchange=Exchange.SHFE, datetime=datetime(2020,1,3),
                      open_price=100,high_price=102,low_price=98,close_price=100,volume=100,gateway_name='FIXTURE')
        history = pd.DataFrame({'date':pd.bdate_range('2019-09-01',periods=80),
                                'open':100.0,'high':102.0,'low':98.0,'close':100.0,
                                'volume':100.0,'open_interest':100.0})
        return strategy,bar,history

    def sizing(self, strategy, bar, history, direction='long', **kwargs):
        return strategy._calculate_entry_sizing(VT,direction,bar,history,
            {'signal':direction+'_case2','risk_mode':'regular'},**kwargs)

    def test_pure_guard_requires_finite_positive_risk_and_budget(self):
        for risk,budget,want in [(20,20,True),(19.9,20,True),(20.000000001,20,False),
                                 (0,20,False),(-1,20,False),(20,0,False),(20,-1,False),
                                 (math.inf,20,False),(20,math.inf,False),(math.nan,20,False),
                                 (20,math.nan,False),(None,20,False),(20,None,False),
                                 ('bad',20,False),(True,20,False)]:
            with self.subTest(risk=risk,budget=budget):
                self.assertEqual(self.module.one_lot_budget_allows(risk,budget),want)

    def test_overrides_restore_native_budget_without_changing_policy_thresholds(self):
        from stage003_candidate import candidate_overrides
        old = candidate_overrides(Path('/tmp/not_read_universe.csv'))
        new = self.module.candidate_overrides(Path('/tmp/not_read_universe.csv'),product_count=93)
        self.assertEqual(new['fixed_size'],0)
        self.assertEqual(new['min_position_size'],1)
        self.assertEqual(new['max_position_size'],1)
        self.assertEqual(new['max_concurrent_positions'],93)
        for key,value in old.items():
            if key not in ('fixed_size','max_concurrent_positions'): self.assertEqual(new[key],value,key)

    def test_real_native_budget_equality_passes_and_oversized_lot_skips(self):
        for budget,want in [(20.0,1),(19.99,0)]:
            strategy,bar,history = self.fixture(min_risk_per_trade=budget,max_risk_per_trade=budget)
            result = self.sizing(strategy,bar,history)
            self.assertEqual(result['sizing_method'],'risk_budget')
            self.assertEqual(result['stop_price'],98.0)
            self.assertEqual(result['risk_per_contract'],20.0)
            self.assertEqual(result['risk_amount'],budget)
            self.assertEqual(result['selected_volume'],want)
            self.assertEqual(result['stage039_budget_gate_passed'],int(want>0))

    def test_real_tighter_long_stop_and_short_stop_are_preserved(self):
        strategy,bar,history = self.fixture()
        bar.low_price = 99
        long = self.sizing(strategy,bar,history,'long')
        short = self.sizing(strategy,bar,history,'short')
        self.assertEqual((long['stop_price'],long['risk_per_contract']),(99.0,10.0))
        self.assertEqual((short['stop_price'],short['risk_per_contract']),(102.0,20.0))

    def test_native_env_single_trade_and_cluster_gates_are_not_revived(self):
        for setting,extra in [({'enable_weighted_env_gate':True},{'current_env_gate_snapshot':{'env_gate_weight':0.0}}),
                              ({'max_single_trade_capital_usage_ratio':0.0},{}),
                              ({'enable_risk_cluster_margin_cap':True,'risk_cluster_map':'rb.SHFE=ferrous','risk_cluster_margin_cap_ratio':0.0}, {})]:
            strategy,bar,history = self.fixture(**setting)
            for key,value in extra.items(): setattr(strategy,key,value)
            result = self.sizing(strategy,bar,history)
            self.assertEqual(result['selected_volume'],0)
            self.assertEqual(result['stage039_native_selected_volume'],0)

    def test_native_streak_multiplier_is_retained(self):
        strategy,bar,history = self.fixture(streak_risk_multipliers='1,1,1,0.1',enable_oi_price_confirm_risk_restore=False)
        strategy.loss_streak = 3
        result = self.sizing(strategy,bar,history)
        self.assertEqual(result['risk_multiplier'],0.1)
        self.assertEqual(result['risk_amount'],2.0)
        self.assertEqual(result['selected_volume'],0)

    def test_real_formal_parameter_budget_fields_are_unchanged(self):
        from stage003_candidate import FullMarketNoAIOneLot
        formal = self.module.candidate_overrides(Path('/tmp/not_read_universe.csv'))
        strategy,bar,history = self.fixture(
            min_risk_per_trade=formal.get('min_risk_per_trade',FullMarketNoAIOneLot.min_risk_per_trade),
            max_risk_per_trade=formal.get('max_risk_per_trade',FullMarketNoAIOneLot.max_risk_per_trade))
        signal = {'signal':'long_case2','risk_mode':'regular'}
        native = FullMarketNoAIOneLot._calculate_entry_sizing(strategy,VT,'long',bar,history,signal)
        guarded = strategy._calculate_entry_sizing(VT,'long',bar,history,signal)
        for key,value in native.items():
            if key == 'selected_volume': continue
            if isinstance(value,float) and math.isnan(value):
                self.assertTrue(math.isnan(guarded[key]),key)
            else:
                self.assertEqual(guarded[key],value,key)
        self.assertLessEqual(guarded['selected_volume'],native['selected_volume'])
        self.assertLessEqual(guarded['selected_volume'],1)
        self.assertEqual(guarded['risk_amount'],strategy._risk_amount_from_ratio(
            guarded['risk_ratio'],guarded['limited_balance'],risk_multiplier_override=guarded['risk_multiplier'])
            *guarded['portfolio_overheat_cooldown_scale']*guarded['directional_30d_risk_boost_multiplier'])

    def test_explicit_guard_defeats_an_inherited_minimum_one_floor(self):
        # Model precisely the future/native minimum-one hazard named in the contract.
        # All normal-policy tests above use the actual native class and methods.
        class FloorNative:
            def _calculate_entry_sizing(self,*args,**kwargs):
                return {'selected_volume':1,'risk_amount':19.0,'risk_per_contract':20.0}
        class FloorCandidate(self.module.NativeRiskBudgetSizingMixin,FloorNative):
            fixed_size=0
            max_position_size=1
        candidate = FloorCandidate()
        result = candidate._calculate_entry_sizing(VT,'long',None,None,{})
        self.assertEqual(result['stage039_native_selected_volume'],1)
        self.assertEqual(result['selected_volume'],0)
        self.assertEqual(result['stage039_budget_gate_passed'],0)

    def test_overbudget_snapshot_cannot_create_a_pending_layer(self):
        from qmt_roll_portfolio_strategy import ProductState
        strategy,bar,history = self.fixture()
        result = self.sizing(strategy,bar,history)
        result['risk_amount'] = 19.0
        state = ProductState(product_vt_symbol='rb.SHFE')
        strategy._open_position(state,VT,'long',1,bar,'long_case2',history,
            {'signal':'long_case2','risk_mode':'regular'},sizing_snapshot=result)
        self.assertEqual(state.layers,[])
        self.assertEqual(strategy.entry_risk_diagnostics,[])

    def test_zero_passed_volume_cannot_reach_native_max_one_floor(self):
        from qmt_roll_portfolio_strategy import ProductState
        strategy,bar,history = self.fixture()
        result = self.sizing(strategy,bar,history)
        state = ProductState(product_vt_symbol='rb.SHFE')
        strategy._open_position(state,VT,'long',0,bar,'long_case2',history,
            {'signal':'long_case2','risk_mode':'regular'},sizing_snapshot=result)
        self.assertEqual(state.layers,[])
        self.assertEqual(strategy.entry_risk_diagnostics,[])

    def test_pending_layer_has_frozen_unique_original_signal_snapshot(self):
        from qmt_roll_portfolio_strategy import ProductState
        strategy,bar,history = self.fixture()
        result = self.sizing(strategy,bar,history)
        state = ProductState(product_vt_symbol='rb.SHFE')
        strategy._open_position(state,VT,'long',1,bar,'long_case2',history,
            {'signal':'long_case2','risk_mode':'regular'},sizing_snapshot=result)
        self.assertEqual(len(state.layers),1)
        layer = state.layers[0]
        frozen = layer.stage039_signal_risk_budget
        self.assertEqual(frozen.target_risk_amount,20.0)
        self.assertEqual(frozen.stop_price,98.0)
        self.assertEqual(frozen.risk_per_contract,20.0)
        self.assertEqual(frozen.signal_datetime,bar.datetime.isoformat())
        self.assertEqual(frozen.entry_context,'flat_entry')
        self.assertEqual(asdict(frozen)['min_risk_per_trade'],20.0)
        result['risk_amount'] = 999999
        strategy.loss_streak = 9
        self.assertEqual(frozen.target_risk_amount,20.0)
        with self.assertRaises(FrozenInstanceError): frozen.target_risk_amount = 999999
        other = ProductState(product_vt_symbol='rb.SHFE')
        strategy.loss_streak = 0
        result2 = self.sizing(strategy,bar,history)
        strategy._open_position(other,VT,'long',1,bar,'long_case2',history,
            {'signal':'long_case2','risk_mode':'regular'},sizing_snapshot=result2)
        self.assertNotEqual(frozen.snapshot_id,other.layers[0].stage039_signal_risk_budget.snapshot_id)


if __name__=='__main__': unittest.main()
