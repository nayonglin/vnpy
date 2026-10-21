"""Continuation guards only; no actual results, SQL, fit or cash replay."""
import importlib.util
from pathlib import Path
import unittest


class ContinuationGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=Path(__file__).with_name('stage149_fx_review_continue.py')
        if not path.exists():raise AssertionError('independent continuation entrypoint missing')
        spec=importlib.util.spec_from_file_location('fx149_continue_fixture',path)
        cls.r=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.r)

    def test_only_alias_change_allowed_and_changed_math_rejected(self):
        old="def held_result():\n    base=control.loc[control.scope.eq(scope)&control.arm.eq('B')]\n    return 3\n"
        new=old.replace("control.arm.eq('B')", "control.arm.eq('CONTROL_REUSED')")
        self.assertTrue(self.r.alias_only_change(old,new))
        with self.assertRaises(AssertionError):self.r.alias_only_change(old,new.replace('return 3','return 4'))

    def test_failed_terminal_must_match_held_stage_with_zero_extra_work(self):
        terminal=dict(status='failed',exit_code=1,error='AssertionError: complete held family-u',new_SQL=0,new_fits=0,new_cash=0,new_labels=0,new_downloads=0,whole_DB_hashes=0,old_control_replays=0,full_new_results_independent_review_completions=0)
        trace=dict(error=terminal['error'],traceback='review_models\nheld_result\nAssertionError: complete held family-u')
        self.assertTrue(self.r.failed_held_stage(terminal,trace))
        with self.assertRaises(AssertionError):self.r.failed_held_stage(dict(terminal,new_fits=1),trace)

    def test_requires_all_six_unique_completed_model_evidence(self):
        reports=[dict(scope=s,cutoff=c,training_rows=3,forward_children=5,forward_mothers=2,q_stats=dict(mean=0.,var=1.,scale=1.,finite_count=3),common_scaler_refit=False,model_refit=False,weights_reconstructed=False) for s in self.r.base.SCOPES for c in self.r.base.CUTOFFS]
        self.assertEqual(self.r.model_evidence(reports)['models_checked'],6)
        with self.assertRaises(AssertionError):self.r.model_evidence(reports[:-1])


if __name__=='__main__':unittest.main()
