"""Two final MROs differ only by an explicit weekly filter, with strict .0025 risk."""
import importlib
import ast
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import pandas as pd
from vnpy.trader.constant import Offset

try:runner=importlib.import_module('stage093_run_quarter_pair')
except ModuleNotFoundError as exc:
    if exc.name!='stage093_run_quarter_pair':raise
    runner=importlib.import_module('stage086_run_fractional_risk')


class PairPolicyTests(unittest.TestCase):
    def test_explicit_both_modes_share_quarter_risk_but_only_enabled_has_weekly_mro(self):
        self.assertTrue(hasattr(runner,'select_classes'),'common paired runner is missing')
        for mode in ('enabled','disabled'):
            strategy,engine=runner.select_classes(mode,'daily-proxy')
            names={cls.__name__ for cls in strategy.__mro__}|{cls.__name__ for cls in engine.__mro__}
            self.assertEqual('WeeklyLongEntryMixin' in names,mode=='enabled')
            self.assertEqual('WeeklyLongExecutionMixin' in names,mode=='enabled')
            self.assertIn('PendingOpenLifecycleMixin',names)
            self.assertIn('ForcedMarginIntentMixin',names)
            self.assertIn('PendingCloseQuantityMixin',names)
            self.assertIn('stage090_quarter_risk',{cls.__module__ for cls in strategy.__mro__})
            self.assertNotIn('stage068_fractional_risk',{cls.__module__ for cls in strategy.__mro__})
            self.assertNotIn('stage075_fractional_weekly',{cls.__module__ for cls in strategy.__mro__})
            self.assertEqual(strategy.stage068_risk_fraction,.0025)

    def test_parent_parameters_change_only_strict_fraction_and_pair_settings_are_identical(self):
        parent=json.loads((runner.LINE/'outputs'/runner.PARENT_EXECUTION_RUN_ID/'manifest.json').read_text())
        contracts=pd.read_csv(runner.LINE/'outputs/run_20261019_contract_weekly_long_v1/contract_metadata.csv')
        settings=runner.supply_settings(runner.build_settings(runner._metadata(contracts),runner.LINE/'outputs/inputs/product_universe.csv'),'disabled-research')
        settings.update(enable_stage827_intraday_c2_stop=False,enable_stage847_half_r_stop_retry=False)
        self.assertEqual({k:(parent['parameters'].get(k),v) for k,v in settings.items() if parent['parameters'].get(k)!=v},
                         {'stage068_risk_fraction':(.005,.0025)})
        self.assertEqual(set(settings),set(parent['parameters']))
        self.assertEqual(runner.FRACTIONAL_RISK_POLICY['risk_fraction'],.0025)
        self.assertEqual(runner.FRACTIONAL_RISK_POLICY['signal_budget'],'signal_equity * 0.0025')

    def test_disabled_features_and_checks_never_access_any_provider_or_engine_attribute(self):
        class Poison:
            def __getattribute__(self,name):raise AssertionError('disabled touched '+name)
        features,export=runner.weekly_feature_artifact(Poison(),False)
        checks=runner.weekly_check_summary(Poison(),Poison(),False)
        self.assertEqual(list(features.columns),runner.WEEKLY_FEATURE_COLUMNS)
        self.assertTrue(features.empty)
        self.assertEqual(export,dict(scope='disabled_no_weekly_queries',queried_contracts=[],rows=0))
        self.assertEqual(checks['weekly_execution_checks'],0)
        self.assertIsNone(checks['actual_long_weekly_violations'])
        self.assertEqual(checks['weekly_filter_validation'],'not_applicable')
        engine=SimpleNamespace()
        with patch.object(runner,'WeeklyContractTrend',side_effect=AssertionError('provider constructed')):
            runner.configure_weekly_provider(engine,False,Poison(),Poison(),Poison())
        self.assertFalse(engine.weekly_filter_enabled)
        self.assertFalse(hasattr(engine,'weekly_contract'))
        for bad in (None,'disabled',0):
            with self.assertRaises(ValueError):runner.configure_weekly_provider(engine,bad,None,None,None)

    def test_clone_whitelist_preserves_all_existing_financial_algorithms(self):
        directory=Path(__file__).parent
        expected=(directory/'stage068_fractional_risk.py').read_text().replace('0.5%','0.25%').replace('0.005','0.0025').replace('RISK_FRACTION = .005','RISK_FRACTION = .0025').replace('fixed_half_percent','fixed_quarter_percent')
        self.assertEqual((directory/'stage090_quarter_risk.py').read_text(),expected)
        expected=(directory/'stage075_fractional_weekly.py').read_text().replace('from stage068_fractional_risk import','from stage090_quarter_risk import')
        self.assertEqual((directory/'stage091_quarter_weekly.py').read_text(),expected)
        expected=(directory/'stage085_pending_open_lifecycle.py').read_text().replace('from stage068_fractional_risk import','from stage090_quarter_risk import').replace('from stage075_fractional_weekly import','from stage091_quarter_weekly import')
        expected=expected.replace('class PendingOpenLifecycleMixin:\n',"class PendingOpenLifecycleMixin:\n    def _stage092_weekly_enabled(self):\n        enabled=getattr(self.strategy_engine,'weekly_filter_enabled',None)\n        if type(enabled) is not bool:raise ValueError('stage092_requires_explicit_boolean_weekly_mode')\n        return enabled\n\n")
        expected=expected.replace("if direction=='long':","if self._stage092_weekly_enabled() and direction=='long':")
        self.assertEqual((directory/'stage092_quarter_pending_open.py').read_text(),expected)
        parent=ast.parse((directory/'stage086_run_fractional_risk.py').read_text())
        paired=ast.parse((directory/'stage093_run_quarter_pair.py').read_text())
        old_fee=next(node for node in parent.body if isinstance(node,ast.ClassDef) and node.name=='FeeStrategy')
        new_fee=next(node for node in paired.body if isinstance(node,ast.ClassDef) and node.name=='AccountingStrategyMixin')
        self.assertEqual([ast.dump(x) for x in old_fee.body],[ast.dump(x) for x in new_fee.body])
        for tree in (parent,paired):
            methods={node.name:node for cls in tree.body if isinstance(cls,ast.ClassDef) and cls.name=='CleanExecution' for node in cls.body if isinstance(node,ast.FunctionDef)}
            if tree is parent:original=methods
            else:
                for name,node in original.items():
                    if name!='__init__':self.assertEqual(ast.dump(node),ast.dump(methods[name]))


class PairRealExecutionTests(unittest.TestCase):
    def fixture(self,mode='enabled',direction='long',price=None):
        import test_stage070_fractional_integration as legacy
        import stage090_quarter_risk as risk
        from stage091_quarter_weekly import WeeklyEntryAuthorization
        e,s,vt,b,o,layer=legacy.FractionalRunnerIntegration().fixture(price=price or (110 if direction=='long' else 90),direction=direction)
        strategy,engine=runner.select_classes(mode,'daily-proxy')
        s.__class__=strategy;e.__class__=engine
        e.weekly_filter_enabled=mode=='enabled';s.stage068_risk_fraction=.0025
        layer.stage068_signal_risk_budget=risk.FractionalSignalRiskReceipt(**dict(asdict(layer.stage068_signal_risk_budget),risk_fraction=.0025,target_risk_amount=2500.))
        if direction=='long':
            if mode=='enabled':layer.stage059_weekly_authorization=WeeklyEntryAuthorization(**asdict(layer.stage059_weekly_authorization))
            else:del layer.stage059_weekly_authorization
        e.prepare_opening_risk(e.datetime)
        return e,s,vt,b,o,layer

    def test_disabled_real_long_opens_with_poison_weekly_while_enabled_rejects_bad_week(self):
        import test_stage059_contract_weekly_candidate as weekly
        e,s,vt,b,o,layer=self.fixture('disabled')
        e.weekly_contract=weekly.Provider(False,True)
        e.cross_delayed_orders()
        self.assertEqual(s.get_pos(vt),3)
        self.assertEqual(next(iter(e.trades.values())).stage068_budget,2500.)
        self.assertEqual(e.weekly_execution_audit,[])
        e,s,vt,b,o,layer=self.fixture('enabled')
        e.weekly_contract=weekly.Provider(False)
        e.cross_delayed_orders();self.assertFalse(e.trades)
        self.assertFalse(e.weekly_execution_audit[-1]['weekly_allowed'])

    def test_both_short_paths_do_not_query_weekly_and_keep_quarter_budget(self):
        for mode in ('enabled','disabled'):
            e,s,vt,b,o,layer=self.fixture(mode,'short')
            e.cross_delayed_orders()
            self.assertEqual(s.get_pos(vt),-3)
            self.assertEqual(next(iter(e.trades.values())).stage068_signal_snapshot['risk_fraction'],.0025)
            self.assertEqual(e.weekly_execution_audit,[])

    def test_both_real_gap_and_old_receipt_type_fail_closed(self):
        from stage068_fractional_risk import FractionalSignalRiskReceipt as Old
        for mode in ('enabled','disabled'):
            for case in ('gap','legacy_type','wrong_fraction'):
                e,s,vt,b,o,layer=self.fixture(mode,price=200 if case=='gap' else 110)
                if case=='legacy_type':layer.stage068_signal_risk_budget=Old(**asdict(layer.stage068_signal_risk_budget))
                if case=='wrong_fraction':
                    from dataclasses import replace
                    layer.stage068_signal_risk_budget=replace(layer.stage068_signal_risk_budget,risk_fraction=.005,target_risk_amount=5000.)
                e.cross_delayed_orders();self.assertFalse(e.trades);self.assertEqual(s.get_target(vt),0)

    def test_common_clean_execution_stale_intent_gate_stays_in_both_modes(self):
        for mode in ('enabled','disabled'):
            e,s,vt,b,o,layer=self.fixture(mode)
            s.states['IC.CFFEX'].layers=[]
            runner.CleanExecution._fill_order(e,o,b)
            self.assertFalse(e.trades)
            self.assertEqual(e.blocked_open_orders[-1]['reason'],'stale_open_intent')

    def test_all_long_native_entry_contexts_have_only_the_explicit_weekly_difference(self):
        import stage091_quarter_weekly as weekly_module
        import test_stage059_contract_weekly_candidate as weekly
        from test_stage090_quarter_risk import QuarterRiskTests
        for context in ('flat_entry','reverse_entry','rollover_reopen'):
            helper,s,b,h=QuarterRiskTests().native()
            native=helper.sizing(s,b,h,entry_context=context)
            self.assertGreaterEqual(native['selected_volume'],0)
            if context!='reverse_entry':self.assertGreater(native['selected_volume'],0)
            s.__class__=type('WeeklyQuarterNative',(weekly_module.WeeklyLongEntryMixin,s.__class__),{})
            s.strategy_engine.weekly_contract=weekly.Provider(False)
            gated=helper.sizing(s,b,h,entry_context=context)
            self.assertEqual(gated['selected_volume'],0)
            self.assertEqual(gated['weekly_long_gate_passed'],0)
            self.assertEqual(gated['risk_amount'],native['risk_amount'])
        helper,s,b,h=QuarterRiskTests().native()
        s.__class__=type('PoisonQuarterNative',(weekly_module.WeeklyLongEntryMixin,s.__class__),{})
        s.strategy_engine.weekly_contract=weekly.Provider(False,True)
        self.assertGreater(helper.sizing(s,b,h,direction='short')['selected_volume'],0)
        self.assertGreater(helper.sizing(s,b,h,entry_context='env_probe')['selected_volume'],0)


import test_stage085_pending_open_lifecycle as lifecycle
class EnabledPendingLifecycle(lifecycle.PendingOpenLifecycleTests):
    weekly_mode='enabled'
    def fixture(self,direction='short',volume=2):
        import stage090_quarter_risk as risk
        from stage091_quarter_weekly import WeeklyEntryAuthorization
        e,s,vt,b,o,layer,state=lifecycle.PendingOpenLifecycleTests().fixture(direction,volume)
        strategy,engine=runner.select_classes(self.weekly_mode,'daily-proxy')
        s.__class__=strategy;e.__class__=engine;e.weekly_filter_enabled=self.weekly_mode=='enabled'
        s.stage068_risk_fraction=.0025
        layer.stage068_signal_risk_budget=risk.FractionalSignalRiskReceipt(**dict(asdict(layer.stage068_signal_risk_budget),risk_fraction=.0025,target_risk_amount=2500.))
        if direction=='long':
            if self.weekly_mode=='enabled':layer.stage059_weekly_authorization=WeeklyEntryAuthorization(**asdict(layer.stage059_weekly_authorization))
            else:del layer.stage059_weekly_authorization
        return e,s,vt,b,o,layer,state

class DisabledPendingLifecycle(EnabledPendingLifecycle):
    weekly_mode='disabled'
    def test_budget_stop_and_weekly_opening_gates_still_reject_original_intent(self):
        for case in ('equity','stop'):
            e,s,vt,b,o,layer,state=self.defer(direction='long')
            s._reconcile_state_with_position(state,0,b)
            if case=='equity':s.settled_balance=1000.
            self.later_fill(e,s,vt,b,price=99. if case=='stop' else None)
            self.assertFalse(e.trades);self.assertEqual(s.get_target(vt),0)


import test_stage078_forced_margin_planning as forced
class EnabledForcedMargin(lifecycle.Final086ForcedMarginTests):
    strategy_base,engine_base=runner.select_classes('enabled','daily-proxy')
    def intent(self,*args,**kwargs):
        import stage090_quarter_risk as risk
        from stage091_quarter_weekly import WeeklyEntryAuthorization
        e,s,vt,b,state,layer=super().intent(*args,**kwargs)
        s.stage068_risk_fraction=.0025
        layer.stage068_signal_risk_budget=risk.FractionalSignalRiskReceipt(**dict(asdict(layer.stage068_signal_risk_budget),risk_fraction=.0025,target_risk_amount=2500.))
        if layer.direction=='long' and self.engine_base.weekly_filter_enabled:
            layer.stage059_weekly_authorization=WeeklyEntryAuthorization(**asdict(layer.stage059_weekly_authorization))
        return e,s,vt,b,state,layer

class DisabledForcedMargin(EnabledForcedMargin):
    strategy_base,engine_base=runner.select_classes('disabled','daily-proxy')


import test_stage074_pending_close_quantity as closes
class EnabledPendingClose(closes.PendingCloseQuantityTests):
    strategy_base,engine_base=runner.select_classes('enabled','daily-proxy')
class DisabledPendingClose(closes.PendingCloseQuantityTests):
    strategy_base,engine_base=runner.select_classes('disabled','daily-proxy')


if __name__=='__main__':unittest.main()
