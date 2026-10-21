"""Two new adapter contracts; synthetic callbacks, no kernel/data/cash run."""
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import pandas as pd

P=Path(__file__).with_name('stage313_joint_integer_cash.py')
S=importlib.util.spec_from_file_location('tiny313',P)
M=importlib.util.module_from_spec(S);S.loader.exec_module(M)


class Adapter(unittest.TestCase):
    # A default CSV float parser or dropping pending K would alter accepted signals.
    def test_saved_tokens_preserve_float_bits_pending_K_and_parent_anchor(self):
        rows=[];parents=[]
        for i in range(2):
            day=('2019-12-30','2019-12-31')[i]
            row=dict(event_id='action'+str(i),mother_event_id='parent'+str(i),action_sequence_index=str(i),
                product_id='DCE.C',family_id='DCE.C',u_date=day,u_index=str(i),D_index=str(i+1),
                reference_epoch='DCE.C.202005',anchor_epoch='DCE.C.202009',label_history_ready20='1',
                N_u='0.10000000000000002',low20_u='0.8',u_close='1.1',history_run='21',lifecycle_index='3',
                entry_capacity_qty='10',u_gross_capacity_qty='20',potential='1',score='0.12345678901234568',
                arm='VOLUNTARY_RESELECT',policy='NARROW',cutoff='2020-01-01',control_id='VOLUNTARY_RESELECT',
                source_lifecycle_index='3',voluntary_boundary_index='' if i==0 else '3.0',
                effective_lifecycle_index='3',effective_boundary_origin='source_lifecycle' if i==0 else 'same_source_and_voluntary',
                K_state='after_calendar_pending' if i==0 else 'reached',K_target_date='2021-01-01' if i==0 else '2020-01-03',
                K_date='' if i==0 else '2020-01-03')
            rows.append(row);parents.append(dict(sequence_index=i,event_id='parent'+str(i),product_id='DCE.C',family_id='DCE.C',
                u_date=day,u_index=i,reference_epoch='DCE.C.202009'))
        raw=pd.DataFrame(rows)
        try:signals=M.parse_signal_tokens(raw,expected=2)
        except Exception as exc:self.fail('saved token contract not implemented: '+str(exc))
        self.assertEqual(signals.N_u.iloc[0].hex(),float('0.10000000000000002').hex())
        self.assertEqual(signals.score.iloc[0].hex(),float('0.12345678901234568').hex())
        self.assertTrue(np.isnan(signals.voluntary_boundary_index.iloc[0]))
        self.assertEqual(signals.voluntary_boundary_index.iloc[1],3.)
        self.assertEqual(signals.event_id.tolist(),['action0','action1'])
        self.assertEqual(set(signals.arm),{'VOLUNTARY_RESELECT'})
        self.assertIsInstance(raw.N_u.iloc[0],str)
        dates=['2019-12-30','2019-12-31','2020-01-02','2020-01-03']
        M.validate_signal_identity(signals,pd.DataFrame(parents),dates)
        broken=signals.copy();broken.loc[0,'anchor_epoch']='DCE.C.202001'
        with self.assertRaises(ValueError):M.validate_signal_identity(broken,pd.DataFrame(parents),dates)

    # A failed allocator must persist its audit and stop, never count it completed.
    def test_second_callback_failure_preserves_audit_and_stops_without_retry(self):
        calls=[]
        class FailedAllocation(RuntimeError):pass
        def run(spec):
            calls.append(spec['account_id'])
            if len(calls)==2:
                exc=FailedAllocation('simulated allocation stop')
                exc.allocation_audit=[dict(batch_index=0,mode='joint_integer',problem=dict(A=[1000000001]),old_rows=[],actual_rows=[])]
                raise exc
            return {}
        with tempfile.TemporaryDirectory(prefix='stage313_callback_') as temporary:
            out=Path(temporary)/'fresh'
            with self.assertRaisesRegex(RuntimeError,'simulated allocation stop'):
                M.run_four(out,run,lambda spec,book:dict(account_id=spec['account_id']))
            terminal=json.loads((out/'actual_terminal.json').read_text())
            manifest=json.loads((out/'manifest.json').read_text())
            self.assertEqual(len(calls),2);self.assertEqual(terminal['cash_accounts_started'],2)
            self.assertEqual(terminal['cash_accounts_completed'],1);self.assertEqual(terminal['status'],'failed')
            self.assertEqual(manifest['status'],'failed');self.assertFalse(terminal['auto_retry'])
            files=list(out.rglob('failed_allocation_audit.jsonl.gz'));self.assertEqual(len(files),1)
            with gzip.open(files[0],'rt') as stream:audit=[json.loads(x) for x in stream]
            self.assertEqual(audit[0]['problem']['A'],[1000000001])


if __name__=='__main__':unittest.main()
