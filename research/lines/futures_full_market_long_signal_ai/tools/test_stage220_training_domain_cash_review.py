"""Only new checkpoint/schema and fixed217 gate wiring; no research I/O."""
import importlib.util
from pathlib import Path
import unittest

s=importlib.util.spec_from_file_location('cashreview220',Path(__file__).with_name('stage220_training_domain_cash_review.py'))
r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

class CashPhaseWiring(unittest.TestCase):
    def test_exact_completed_new_model_checkpoint_only(self):
        b={'path':'new218','bytes':123,'sha256':'synthetic'}
        phase=dict(schema='stage220_domain_model_review_v1',status='completed',core_blockers=0,new_prediction_model_rows=1933480,cash_eligible=True,manifest=b)
        cash=dict(schema='stage219_training_domain_loss_cash_v1',status='completed',input_bindings=dict(fit_manifest=b))
        r.verify_phase_contract(phase,cash)
        for d in (dict(schema='stage207_local_curve_information_review_v1'),dict(cash_eligible=False),dict(core_blockers=1),dict(new_prediction_model_rows=1933479)):
            with self.assertRaises(AssertionError):r.verify_phase_contract(dict(phase,**d),cash)

    def test_strict217_gate_can_accept_support_and_reject_held_unknown(self):
        points={(w,c):dict(active_total_return_pct=1.,return_percentage_point_difference=.1,drawdown_percentage_point_difference=.1,ci95_low=.001) for w in r.WINDOWS for c in r.COSTS}
        held={g:dict(known_u_equal_mean_increment_R=.01,unknown_differential_selected_events=0,nominal_pass=True) for g in ('holdout_0','holdout_1')}
        self.assertTrue(r.gate(points,held,False,False,True)['nominal_pass'])
        held['holdout_0']['unknown_differential_selected_events']=16
        self.assertFalse(r.gate(points,held,False,False,True)['nominal_pass'])
        self.assertTrue(r.gate(points,held,False,False,True)['held_signal_unknown'])

if __name__=='__main__':unittest.main()
