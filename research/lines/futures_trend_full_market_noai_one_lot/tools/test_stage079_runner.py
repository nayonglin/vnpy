import importlib,json,unittest
from pathlib import Path
from types import SimpleNamespace

path=Path(__file__).with_name('stage079_run_fractional_risk.py')
module=importlib.import_module('stage079_run_fractional_risk' if path.exists() else 'stage070_run_fractional_risk')

class RepairedRunnerTests(unittest.TestCase):
    def test_forced_planning_precedes_actual_quantity_guard_in_final_mro(self):
        names=[c.__name__ for c in module.FeeStrategy.__mro__]
        self.assertIn('ForcedMarginIntentMixin',names)
        self.assertLess(names.index('ForcedMarginIntentMixin'),names.index('PendingCloseQuantityMixin'))
    def test_failure_snapshot_distinguishes_actual_target_layers_and_pending(self):
        self.assertTrue(hasattr(module,'runtime_failure_snapshot'),'failure state must be captured outside _fill_order too')
        state=SimpleNamespace(contract_vt_symbol='x.DCE',direction='long',layers=[SimpleNamespace(volume=3,entry_price_synced=True,
            direction='long',entry_price=100,stop_price=90,signal='long_case2',entry_date='2020-01-01',kind='base')])
        s=SimpleNamespace(pos_data={'x.DCE':5},target_data={'x.DCE':3},states={'x.DCE':state},pending_close_lots={'x.DCE':[dict(volume=2,direction='long')]},
            pending_active_products=set(),pending_entry_diagnostics={},forced_margin_deleverage_events=[],entry_risk_diagnostics=[],estimated_equity=1000,settled_balance=1000,
            total_margin_in_use=500,pending_margin_reservation=0,pending_cluster_margin_reservation={})
        e=SimpleNamespace(strategy=s,datetime='2020-01-02',active_limit_orders={},opening_equity=1000,open_execution_costs=0)
        snap=module.runtime_failure_snapshot(e)
        self.assertEqual(snap['actual_positions'],{'x.DCE':5});self.assertEqual(snap['targets'],{'x.DCE':3})
        self.assertEqual(snap['states']['x.DCE']['layers'][0]['volume'],3)
        self.assertEqual(snap['pending_close_lots']['x.DCE'][0]['volume'],2)
        self.assertEqual(snap['marked_equity'],1000)
        json.dumps(module.safe(snap))

if __name__=='__main__':unittest.main()
