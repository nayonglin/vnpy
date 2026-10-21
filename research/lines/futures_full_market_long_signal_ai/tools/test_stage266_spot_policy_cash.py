"""Only new wrapper contracts; no accepted financial kernel or data is imported."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import pandas as pd

SOURCE=Path(__file__).with_name('stage266_spot_policy_cash.py')


def implementation(case):
    case.assertTrue(SOURCE.exists(),'Stage266 implementation is missing')
    spec=importlib.util.spec_from_file_location('stage266_fixture_module',SOURCE)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class WrapperContracts(unittest.TestCase):
    def test_cancellation_is_only_a_private_complete_signal_mask(self):
        # A wrong unknown branch, reordering, mutated score/expiry, or mother/action
        # identity swap must fail. Literal expected IDs are hand-derived.
        m=implementation(self)
        rows=[]
        for j in range(3):
            rows.append(dict(event_id='action'+str(j),mother_event_id='parent'+str(j),
                product_id='DCE.C',family_id='corn',u_date='2020-01-02',u_index=5,
                reference_epoch='DCE.C.202003',anchor_epoch='DCE.C.202005',score=1.5+j,
                lifecycle_index=50,N_u=2.5,source_lifecycle_index=60))
        original=pd.DataFrame(rows);before=original.copy(deep=True)
        side=original[m.IDENTITY].copy();side.insert(0,'signal_row',range(3))
        side['available']=[1,0,1];side['keep_entry']=[0,1,1]
        side['action']=['cancel','retain','retain'];side['reason']=['nonpositive','missing','positive']
        result=m.apply_policy(original,side,expected_count=3)
        self.assertEqual(result.event_id.tolist(),['action1','action2'])
        pd.testing.assert_frame_equal(original,before)
        pd.testing.assert_frame_equal(result,original.iloc[[1,2]].reset_index(drop=True))
        bad=side.copy();bad.loc[1,['keep_entry','action']]=[0,'cancel']
        with self.assertRaises(ValueError):m.apply_policy(original,bad,expected_count=3)
        bad=side.copy();bad.loc[0,'event_id']='parent0'
        with self.assertRaises(ValueError):m.apply_policy(original,bad,expected_count=3)

    def test_research_gate_and_four_account_terminal_preserve_real_budget(self):
        # A fifth run, premature read/run, missing failed-start count, wrong
        # comparison identity, or silent overwrite must fail observable files.
        m=implementation(self)
        bundle=[dict(path='/fixture/new.py',bytes=1,sha256='x')]
        cov=dict(total_signals=4365,cancel_count=1,core_blockers=0)
        review=dict(schema='stage267_spot_policy_source_review_v1',completed=True,
            core_blockers=0,protocol_sha256=m.PROTOCOL_SHA,source_bindings=bundle)
        m.check_research_gates(cov,review,bundle)
        for key,value in [('cancel_count',0),('core_blockers',1)]:
            bad=dict(cov);bad[key]=value
            with self.assertRaises(ValueError):m.check_research_gates(bad,review,bundle)
        bad=dict(review);bad['source_bindings']=[]
        with self.assertRaises(ValueError):m.check_research_gates(cov,bad,bundle)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'good';calls=[]
            def run(spec):
                calls.append(spec['account_id'])
                progress=json.loads((out/'cash_progress.json').read_text())
                self.assertEqual(progress['cash_accounts_started'],len(calls))
                self.assertEqual(progress['cash_accounts_completed'],len(calls)-1)
                return {'fixture_book':spec['account_id']}
            def export(spec,book):return dict(account_id=spec['account_id'],ending_equity=110.)
            records=m.run_four(out,run,export)
            self.assertEqual([r['account_id'] for r in records],[
                'NARROW_SPOT264_primary_2020_base','NARROW_SPOT264_primary_2020_stress',
                'NARROW_SPOT264_cold_2023_base','NARROW_SPOT264_cold_2023_stress'])
            terminal=json.loads((out/'actual_terminal.json').read_text())
            self.assertEqual((terminal['cash_accounts_started'],terminal['cash_accounts_completed']),(4,4))
            self.assertEqual(terminal['status'],'completed')
            with self.assertRaises(FileExistsError):m.run_four(out,run,export)
            failed=Path(tmp)/'failed';attempts=[]
            def failure(spec):
                attempts.append(spec['account_id'])
                if len(attempts)==2:raise RuntimeError('synthetic stop')
                return {}
            with self.assertRaises(RuntimeError):m.run_four(failed,failure,export)
            terminal=json.loads((failed/'actual_terminal.json').read_text())
            self.assertEqual((terminal['cash_accounts_started'],terminal['cash_accounts_completed']),(2,1))
            self.assertEqual(terminal['status'],'failed')


if __name__=='__main__':unittest.main()
