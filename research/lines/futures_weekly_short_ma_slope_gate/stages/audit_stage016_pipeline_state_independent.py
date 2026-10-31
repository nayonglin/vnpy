"""Synthetic structural pipeline-store audit; no runtime engine construction."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
import copy,hashlib,json,os,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'))
import qmt_roll_weekly19_funding as f
from qmt_roll_weekly19_pipeline_state import PipelineStateStore,PipelineStateError
from qmt_roll_weekly19_runtime import _encode,_state_digest
A=hashlib.sha256(b'INDEPENDENT-PIPELINE-FAKE').hexdigest();R='INDEPENDENT-PIPELINE-NOT-QUALIFIED';DAY='2026-10-30';S='a'*64

def cash():return f.initial_state(A,R,DAY)
def empty():return dict(schema='weekly19.pipeline-state.v1',revision=0,account_key=A,material_release_id=R,funding=cash(),runtime=None,decision=None,decision_state=None)
def runtime(funds=None,rev=0,decision=None):
    funds=cash()if funds is None else funds
    decoded=dict(revision=rev,position_identities={},confirmed_cash_state=copy.deepcopy(funds),current_receipt_hash=S,days={})
    if decision is not None:decoded['days'][DAY]={'request_hash':'b'*64,'decision':copy.deepcopy(decision)}
    body=dict(schema='weekly19.runtime-state.v1',revision=rev,account_key=A,material_release_id=R,position_identities={},production_qualified=False,runtime=_encode(decoded),strategy=_encode({}),engine=_encode({}),settings_sha256='c'*64,input_sha256='d'*64,input_cursor=DAY,input_prefix_sha256='e'*64)
    return dict(body,state_sha256=_state_digest(body))
def bound():
    b=empty();d=dict(schema='weekly19.runtime-decision.v1',trading_date=DAY,account_fingerprint=A,material_release_id=R,confirmed_cash_state=cash(),data_receipt_sha256=S,before_state_sha256='0'*64,after_state_sha256=None,production_qualified=False,intents=[],funding_admitted_ids=[])
    origin=runtime(decision=d);d['after_state_sha256']=origin['state_sha256'];origin=runtime(decision=d)
    assert origin['state_sha256']==d['after_state_sha256']
    b.update(runtime=copy.deepcopy(origin),decision_state=origin,decision=d);return b

class Pipeline(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(dir='/private/tmp');self.addCleanup(self.t.cleanup);self.path=Path(self.t.name)/'pipeline.json';self.st=PipelineStateStore(self.path,A,R);self.st.initialize(empty())
    def reject(self,value):
        before=self.path.read_bytes()
        with self.assertRaises((PipelineStateError,f.FundingError,ValueError,TypeError,KeyError)):self.st.transact(lambda _:value)
        self.assertEqual(self.path.read_bytes(),before)
    def test_01_coherent_runtime_cash_origin_positive(self):
        b=bound();saved=self.st.transact(lambda _:b);self.assertEqual(saved['revision'],1);self.assertEqual(saved['decision']['after_state_sha256'],saved['decision_state']['state_sha256']);self.assertEqual(self.st.read(),saved)
    def test_02_foreign_decision_identity_rejected_before_write(self):
        for key,value in [('material_release_id','FOREIGN'),('account_fingerprint','f'*64)]:
            b=bound();b['decision'][key]=value;self.reject(b)
    def test_03_bad_runtime_digest_cannot_be_persisted(self):
        b=bound();b['runtime']['state_sha256']='0'*64;self.reject(b)
    def test_04_rehashed_runtime_with_different_cash_is_rejected(self):
        other=cash();other['revision']=1;b=bound();b['runtime']=runtime(funds=other);self.reject(b)
    def test_05_future_origin_revision_is_not_a_historical_decision(self):
        b=bound();d=b['decision'];origin=runtime(rev=2,decision=d);d['after_state_sha256']=origin['state_sha256'];b['decision_state']=runtime(rev=2,decision=d);self.reject(b)
    def test_06_historical_origin_survives_current_runtime_revision(self):
        b=bound();old_hash=b['decision_state']['state_sha256'];b['runtime']=runtime(rev=1,decision=b['decision'])
        self.assertNotEqual(b['runtime']['state_sha256'],old_hash);saved=self.st.transact(lambda _:b);self.assertEqual(saved['decision']['after_state_sha256'],old_hash)
    def test_07_decision_receipt_or_afterhash_mismatch_rejected(self):
        for key,value in [('data_receipt_sha256','f'*64),('after_state_sha256','f'*64)]:
            b=bound();b['decision'][key]=value;self.reject(b)
    def test_08_decision_without_origin_or_orphan_origin_rejected(self):
        b=bound();b['decision_state']=None;self.reject(b)
        b=bound();b['decision']=None;self.reject(b)
    def test_09_transform_raises_has_no_partial_commit(self):
        before=self.path.read_bytes()
        def bad(b):b['funding']['reserve_remaining_fen']=0;raise RuntimeError('INJECTED')
        with self.assertRaises(RuntimeError):self.st.transact(bad)
        self.assertEqual(self.path.read_bytes(),before)
    def test_10_stale_caller_revision_cannot_overwrite_current(self):
        self.st.transact(lambda b:dict(b,diagnostics={'n':1}));stale=empty();self.reject(stale)
    def test_11_concurrent_diagnostics_transform_never_loses_revision(self):
        def worker(_):return self.st.transact(lambda b:dict(b,diagnostics={'n':b.get('diagnostics',{}).get('n',0)+1}))
        with ThreadPoolExecutor(4)as p:list(p.map(worker,range(12)))
        value=self.st.read();self.assertEqual((value['revision'],value['diagnostics']['n']),(12,12))
    def test_12_first_lock_creation_concurrency(self):
        self.path.with_name('pipeline.json.lock').unlink();barrier=Barrier(2)
        def read(_):barrier.wait();return PipelineStateStore(self.path,A,R).read()
        with ThreadPoolExecutor(2)as p:rows=list(p.map(read,[1,2]))
        self.assertEqual(rows,[empty(),empty()])
    def test_13_before_replace_fault_leaves_old_complete_snapshot(self):
        before=self.path.read_bytes()
        with patch('qmt_roll_weekly19_pipeline_state.os.replace',side_effect=OSError('BEFORE_REPLACE')):
            with self.assertRaises(OSError):self.st.transact(lambda b:dict(b,diagnostics={'n':1}))
        self.assertEqual(self.path.read_bytes(),before)
    def test_14_after_replace_directory_fsync_fault_requires_reload_not_false_rollback(self):
        real=os.fsync
        def fail(fd):
            import stat
            if stat.S_ISDIR(os.fstat(fd).st_mode):raise OSError('AFTER_REPLACE')
            return real(fd)
        with patch('qmt_roll_weekly19_pipeline_state.os.fsync',side_effect=fail):
            with self.assertRaises(OSError):self.st.transact(lambda b:dict(b,diagnostics={'n':1}))
        loaded=self.st.read();self.assertEqual((loaded['revision'],loaded['diagnostics']['n']),(1,1))
        # No transport side effect occurred. Commit outcome on I/O error can be
        # ambiguous; caller must reload and reconcile before any publication.
    def test_15_private_mode_and_owning_snapshot(self):
        self.assertEqual(self.path.stat().st_mode&0o777,0o600);self.path.chmod(0o640)
        with self.assertRaises(PipelineStateError):self.st.read()
    def test_16_funding_cold_start_identity_cannot_be_rewritten(self):
        b=empty();b['funding']['cold_start_date']='2026-10-29';b['funding']['revision']=1;self.reject(b)
    def test_17_changed_funding_needs_a_strictly_increasing_revision(self):
        b=empty();b['funding']['cashflow_checkpoint']={'trading_day':DAY,'observed_at':'2026-10-30T16:00:00+08:00','raw_sha256':'f'*64,'deposit_fen':0,'withdraw_fen':0};self.reject(b)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Pipeline));raise SystemExit(not result.wasSuccessful())
