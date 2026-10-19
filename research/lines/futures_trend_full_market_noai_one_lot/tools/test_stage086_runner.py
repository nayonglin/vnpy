import json
import unittest
import pandas as pd
import stage079_run_fractional_risk as old
import stage086_run_fractional_risk as new


class Runner086Tests(unittest.TestCase):
    def test_economic_parameters_and_frozen_policy_are_identical_to_079(self):
        contracts=pd.read_csv(new.LINE/'outputs/run_20261019_contract_weekly_long_v1/contract_metadata.csv')
        path=new.LINE/'outputs/inputs/product_universe.csv'
        before=old.supply_settings(old.build_settings(old._metadata(contracts),path),'disabled-research')
        after=new.supply_settings(new.build_settings(new._metadata(contracts),path),'disabled-research')
        self.assertEqual(before,after)
        self.assertEqual(old.FRACTIONAL_RISK_POLICY,new.FRACTIONAL_RISK_POLICY)
        self.assertEqual(old.BASELINE_MANIFEST_SHA256,new.BASELINE_MANIFEST_SHA256)

    def test_new_modules_precede_frozen_guards_in_both_actual_mros(self):
        names=[cls.__name__ for cls in new.FeeStrategy.__mro__]
        self.assertLess(names.index('PendingOpenLifecycleMixin'),names.index('ForcedMarginIntentMixin'))
        engine=[cls.__name__ for cls in new.FullMarketDailyEngine.__mro__]
        self.assertLess(engine.index('PendingOpenLifecycleEngineMixin'),engine.index('WeeklyLongExecutionMixin'))
        self.assertEqual(new.sha(new.LINE/'outputs'/new.PRIOR_REJECTED_RUN/'manifest.json'),new.PRIOR_REJECTED_MANIFEST_SHA256)
        self.assertEqual(new.sha(new.LINE/'outputs'/new.PRIOR_REJECTED_RUN/'protocol.json'),new.PRIOR_REJECTED_PROTOCOL_SHA256)

    def test_export_only_quote_asof_discloses_forward_fill_without_mutating_source(self):
        rows=[dict(date='2021-08-11',vt_symbol='JR202109.CZCE',quote_datetime='2021-08-11',order_quote=2552.)]
        market=pd.DataFrame([dict(date='2021-08-10',vt_symbol='JR202109.CZCE')])
        annotated=new.annotate_quote_provenance(rows,market)
        self.assertEqual(annotated[0]['causal_quote_asof'],'2021-08-10')
        self.assertTrue(annotated[0]['valuation_proxy'])
        self.assertEqual(annotated[0]['order_quote'],2552.)
        self.assertNotIn('causal_quote_asof',rows[0])


if __name__=='__main__':unittest.main()
