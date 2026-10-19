"""A new strict quarter-percent policy, never a compatibility half-percent alias."""
from dataclasses import replace
import importlib
from pathlib import Path
import unittest

try:m=importlib.import_module('stage090_quarter_risk')
except ModuleNotFoundError as exc:
    if exc.name!='stage090_quarter_risk':raise
    m=importlib.import_module('stage068_fractional_risk')


class QuarterRiskTests(unittest.TestCase):
    def receipt(self,**changes):
        values=dict(snapshot_id='quarter-original',contract_vt_symbol='rb202005.SHFE',product_vt_symbol='rb.SHFE',
            direction='long',signal='long_case2',signal_datetime='2020-01-03T00:00:00',entry_context='flat_entry',
            signal_equity=1000000.,risk_fraction=.0025,target_risk_amount=2500.,risk_per_contract=100.,
            stop_price=100.,authorized_volume=25)
        values.update(changes)
        return m.FractionalSignalRiskReceipt(**values)

    def native(self,**settings):
        import test_stage068_fractional_risk as old
        helper=old.FractionalRiskTests();helper.m=m
        settings.setdefault('stage068_risk_fraction',.0025)
        return helper.fixture(**settings)

    def real(self,price=110.,direction='long'):
        import test_stage068_fractional_risk as old
        helper=old.RealFractionalFillTests();helper.m=m;helper.receipt=self.receipt
        return helper.fixture(price=price,quantity=25,direction=direction)

    def test_exact_quarter_formula_floor_and_policy_identity(self):
        self.assertEqual(m.RISK_FRACTION,.0025)
        self.assertEqual(m.fractional_budget(1000000.),2500.)
        self.assertEqual(m.fractional_budget(1200000.),3000.)
        self.assertEqual(m.FractionalSignalRiskReceipt.__module__,'stage090_quarter_risk')
        for budget,risk,want in [(2500,100,25),(2500,100.000000001,24),(2500,2501,0),(2500,2500,1)]:
            self.assertEqual(m.whole_contracts(budget,risk),want)
        for equity in [None,True,0,-1,float('nan'),float('inf')]:self.assertEqual(m.fractional_budget(equity),0.)

    def test_native_order_of_quantity_gates_starts_from_new_budget(self):
        helper,s,b,h=self.native(min_risk_per_trade=999999.,max_risk_per_trade=999999.,enable_weighted_env_gate=True)
        s.current_env_gate_snapshot={'env_gate_weight':.5}
        sizing=helper.sizing(s,b,h)
        self.assertEqual(sizing['risk_amount'],2500.)
        self.assertEqual(sizing['contracts_by_risk'],125)
        self.assertEqual(sizing['selected_volume'],62)
        self.assertGreater(helper.sizing(s,b,h,entry_context='env_probe')['selected_volume'],1)

    def test_half_percent_configuration_is_rejected_not_accepted_as_compatibility(self):
        helper,s,b,h=self.native()
        s.stage068_risk_fraction=.005
        with self.assertRaises(ValueError):helper.sizing(s,b,h)

    def test_opening_budget_is_min_original_and_current_equity_with_whole_rejection(self):
        args=dict(direction='long',open_price=110.,stop_price=100.,size=10.,tick=.1,volume=25,
            receipt=self.receipt(),opening_equity=1000000.)
        result=m.assess_fractional_open(**args)
        self.assertTrue(result['allowed']);self.assertEqual(result['total_risk'],2500.)
        self.assertEqual(result['opening_budget'],2500.)
        self.assertEqual(m.assess_fractional_open(**dict(args,opening_equity=2000000.))['opening_budget'],2500.)
        for changes in [dict(open_price=110.01),dict(opening_equity=999999.),dict(volume=24),dict(stop_price=99.)]:
            self.assertFalse(m.assess_fractional_open(**dict(args,**changes))['allowed'])

    def test_real_long_and_short_twenty_five_lots_use_quarter_receipt(self):
        for direction,price in [('long',110.),('short',90.)]:
            e,s,vt,b,o,layer=self.real(price,direction)
            e.cross_delayed_orders()
            self.assertEqual(s.get_pos(vt),25 if direction=='long' else -25)
            trade=next(iter(e.trades.values()))
            self.assertEqual(trade.stage068_entry_risk,2500.)
            self.assertEqual(trade.stage068_budget,2500.)
            self.assertEqual(trade.stage068_signal_snapshot['risk_fraction'],.0025)

    def test_real_legacy_receipt_type_cannot_authorize_quarter_open(self):
        from dataclasses import asdict
        from stage068_fractional_risk import FractionalSignalRiskReceipt as Legacy
        e,s,vt,b,o,layer=self.real()
        layer.stage068_signal_risk_budget=Legacy(**asdict(layer.stage068_signal_risk_budget))
        e.cross_delayed_orders()
        self.assertFalse(e.trades);self.assertEqual(s.get_target(vt),0)


if __name__=='__main__':unittest.main()
