"""Independent, synthetic funding/store adversarial tests; no real providers.

All fake raw payloads are deliberately fabricated. Their acceptance must never
be reported as broker origin, a real deposit, production qualification or orders.
"""
from pathlib import Path
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
import copy, hashlib, io, json, os, stat, subprocess, sys, tempfile, unittest
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'examples/portfolio_backtesting'))
import qmt_roll_weekly19_funding as f
from qmt_roll_weekly19_funding_store import FundingStore
T = datetime(2026,10,30,16,10,tzinfo=timezone(timedelta(hours=8)))
A = hashlib.sha256(b'INDEPENDENT-FAKE-BROKER\0INDEPENDENT-FAKE-ACCOUNT').hexdigest()
R = 'INDEPENDENT-FAKE-RELEASE'
S = hashlib.sha256(b'NOT-A-REAL-SIGNAL').hexdigest()
def envelope(d):
    raw=json.dumps(d,sort_keys=True,separators=(',',':'))
    return dict(raw_payload=raw,raw_sha256=hashlib.sha256(raw.encode()).hexdigest())
def account(balance='120000', deposit='0', withdraw='0', at=T, day='2026-10-30', **kw):
    d=dict(schema='weekly19.ctp-account.v1',source_kind='ctp_account_callback',
      account_key=A,material_release_id=R,observed_at=at.isoformat(),trading_day=day,
      generation_uuid='SYNTHETIC-NOT-PROVIDER',query_reqid=31,query_complete=True,
      CurrencyID='CNY',BrokerID='INDEPENDENT-FAKE-BROKER',AccountID='INDEPENDENT-FAKE-ACCOUNT',
      Balance=balance,Deposit=deposit,Withdraw=withdraw)
    d.update(kw);return envelope(d)
def cash(rid, amount='30000', receipt_id='FAKE-BANK-1', at=T+timedelta(seconds=1), day='2026-10-30', **kw):
    d=dict(schema='weekly19.bank-cashflow.v1',source_kind='broker_cashflow_receipt',
      account_key=A,material_release_id=R,request_id=rid,trading_day=day,
      occurred_at=at.isoformat(),receipt_id=receipt_id,Amount=amount,Direction='deposit',Status='completed')
    d.update(kw);return envelope(d)
def closure(closing,nextday='2026-11-02',at=T+timedelta(minutes=2),**kw):
    b=json.loads(closing['raw_payload']);d=dict(schema='weekly19.cashflow-day-close.v1',
      source_kind='broker_cashflow_day_close',account_key=A,material_release_id=R,
      trading_day=b['trading_day'],next_trading_day=nextday,closed_at=at.isoformat(),
      closing_account_sha256=closing['raw_sha256'],Deposit=b['Deposit'],Withdraw=b['Withdraw'],
      cashflows_complete=True,statement_id='FAKE-CLOSE-1');d.update(kw);return envelope(d)
def initial():return f.initial_state(A,R,'2026-10-30')
def recommend(state=None, evidence=None, ids=None, now=T):
    return f.recommend_topup(initial() if state is None else state,
      account() if evidence is None else evidence,'2026-10-30',
      ['FAKE-NATIVE-1'] if ids is None else ids,S,now)
def pending(balance='120000'):
    v=recommend(evidence=account(balance));return v['state'],v['recommendation']['request_id']
def paid(state,rid,amount='30000',deposit='30000',receipt_id='FAKE-BANK-1',now=T+timedelta(seconds=2)):
    return f.confirm_topup(state,rid,cash(rid,amount,receipt_id,at=now-timedelta(seconds=1)),
      account('150000',deposit,at=now),now)

class IndependentFunding(unittest.TestCase):
    def test_01_self_consistent_fabricated_evidence_is_not_origin_or_qualification(self):
        s,rid=pending();s=paid(s,rid)
        self.assertEqual(s['confirmed_topup_fen'],3000000)
        self.assertFalse(s['production_qualified'])
        self.assertIsNone(f.assert_open_funding_ready(s,account('150000','30000',at=T+timedelta(seconds=2)),T+timedelta(seconds=2)))
        # This is a documented conditional boundary, NOT a real funding proof.
        self.assertNotIn('trading_equity_fen',s)
    def test_02_raw_payload_tamper_and_duplicate_json_key_reject(self):
        b=account();b['raw_payload']=b['raw_payload'].replace('120000','140000')
        with self.assertRaises(f.FundingError):recommend(evidence=b)
        b=account();b['raw_payload']=b['raw_payload'][:-1]+',"Balance":"140000"}'
        b['raw_sha256']=hashlib.sha256(b['raw_payload'].encode()).hexdigest()
        with self.assertRaises(f.FundingError):recommend(evidence=b)
    def test_03_evidence_boundaries_300_seconds_and_one_second_future(self):
        recommend(evidence=account(at=T-timedelta(seconds=300)))
        for at in [T-timedelta(seconds=300,microseconds=1),T+timedelta(microseconds=1)]:
            with self.assertRaises(f.FundingError):recommend(evidence=account(at=at))
    def test_04_all_wrong_account_release_sources_reject_without_mutation(self):
        s,rid=pending();before=copy.deepcopy(s)
        for kw in [dict(account_key='f'*64),dict(material_release_id='WRONG'),dict(source_kind='not-provider')]:
            with self.assertRaises(f.FundingError):
                f.confirm_topup(s,rid,cash(rid,**kw),account(deposit='30000',at=T+timedelta(seconds=2)),T+timedelta(seconds=2))
            self.assertEqual(s,before)
    def test_05_fractional_partial_then_exact_remainder_no_double_credit(self):
        s,rid=pending();one=paid(s,rid,'0.01','0.01')
        self.assertEqual(one['reserve_remaining_fen'],14999999)
        two=paid(one,rid,'29999.99','30000','FAKE-BANK-2',T+timedelta(seconds=4))
        self.assertEqual(two['reserve_remaining_fen'],12000000)
        replay=f.confirm_topup(two,rid,cash(rid,'0.01','FAKE-BANK-1'),
          account('150000','30000',at=T+timedelta(seconds=5)),T+timedelta(seconds=5))
        self.assertEqual(replay,two)
    def test_06_unknown_extra_cash_rejects_and_error_leaves_state_unchanged(self):
        s,rid=pending();before=copy.deepcopy(s)
        for b in [account(deposit='30000.01',at=T+timedelta(seconds=2)),
                  account(deposit='30000',withdraw='0.01',at=T+timedelta(seconds=2))]:
            with self.assertRaises(f.FundingError):f.confirm_topup(s,rid,cash(rid),b,T+timedelta(seconds=2))
            self.assertEqual(s,before)
    def test_07_expiry_exact_and_late_do_not_debit(self):
        s,rid=pending();before=copy.deepcopy(s)
        for at in [T+timedelta(days=7),T+timedelta(days=8)]:
            with self.assertRaisesRegex(f.FundingError,'request_expired'):
                f.confirm_topup(s,rid,cash(rid,at=at),account(deposit='30000',at=at),at)
            self.assertEqual(s,before)
    def test_08_late_receipt_or_account_cannot_reorder_after_snapshot(self):
        s,rid=pending();future=cash(rid,at=T+timedelta(seconds=3))
        with self.assertRaisesRegex(f.FundingError,'receipt_after_broker_snapshot'):
            f.confirm_topup(s,rid,future,account(deposit='30000',at=T+timedelta(seconds=2)),T+timedelta(seconds=4))
    def test_09_full_friday_night_monday_partial_chain_preserves_inputs(self):
        s,rid=pending();s=paid(s,rid,'10000','10000');before=copy.deepcopy(s)
        close=account(deposit='10000',at=T+timedelta(minutes=1));night=T.replace(hour=21,minute=0)
        opening=account(at=night,day='2026-11-02')
        rolled=f.reconcile_trading_day(s,close,opening,night,continuity_receipt=closure(close))
        self.assertEqual(s,before);self.assertEqual(rolled['confirmed_topup_fen'],1000000)
        with self.assertRaisesRegex(f.FundingError,'funding_pending'):f.assert_open_funding_ready(rolled,opening,night)
        at=night+timedelta(seconds=2)
        end=f.confirm_topup(rolled,rid,cash(rid,'20000','FAKE-BANK-2',at=night+timedelta(seconds=1),day='2026-11-02'),
          account('150000','20000',at=at,day='2026-11-02'),at)
        self.assertEqual(end['confirmed_topup_fen'],3000000);self.assertEqual(end['reserve_remaining_fen'],12000000)
        f.assert_open_funding_ready(end,account('150000','20000',at=at,day='2026-11-02'),at)
    def test_10_missing_or_wrong_cross_day_proof_is_fail_closed(self):
        s,rid=pending();close=account(at=T+timedelta(minutes=1));night=T.replace(hour=21,minute=0)
        for proof in [None,closure(close,account_key='f'*64),closure(close,material_release_id='WRONG'),
                      closure(close,closing_account_sha256='f'*64),closure(close,cashflows_complete=False)]:
            with self.assertRaises(f.FundingError):
                f.reconcile_trading_day(s,close,account(at=night,day='2026-11-02'),night,continuity_receipt=proof)
    def test_11_zero_start_unknown_night_cash_is_not_silently_accepted(self):
        s,rid=pending();close=account(at=T+timedelta(minutes=1));night=T.replace(hour=21,minute=0)
        with self.assertRaisesRegex(f.FundingError,'unreconciled_cashflow_at_day_roll'):
            f.reconcile_trading_day(s,close,account(deposit='30000',at=night,day='2026-11-02'),night,continuity_receipt=closure(close))
    def test_12_exhausted_reserve_and_zero_or_negative_E_have_no_base_fallback(self):
        s,rid=pending('0');s=paid(s,rid,'150000','150000')
        at=T+timedelta(seconds=3)
        for e in ['0','-0.01','-100000']:
            with self.assertRaisesRegex(f.FundingError,'nonpositive_equity'):
                f.assert_open_funding_ready(s,account(e,'150000',at=at),at)
        f.assert_open_funding_ready(s,account('0.01','150000',at=at),at)
    def test_13_pending_without_new_candidate_is_still_blocked(self):
        s,rid=pending();v=recommend(s,ids=[])
        self.assertEqual(v['recommendation']['status'],'no_admitted_entry')
        self.assertEqual(v['recommendation']['amount_fen'],0)
        self.assertEqual(v['state']['requests'][rid]['status'],'pending')
        with self.assertRaisesRegex(f.FundingError,'funding_pending'):
            f.assert_open_funding_ready(v['state'],account(),T)
        # Mail adapter MUST display outstanding pending request; this status
        # alone does not mean all requested cash has arrived or no funding due.
    def test_14_simulated_money_never_changes_account_evidence_or_input(self):
        s=initial();b=account();inputs=copy.deepcopy((s,b));v=recommend(s,b)
        self.assertEqual((s,b),inputs);s=v['state'];rid=v['recommendation']['request_id']
        c=cash(rid);b=account('150000','30000',at=T+timedelta(seconds=2));inputs=copy.deepcopy((s,c,b))
        new=f.confirm_topup(s,rid,c,b,T+timedelta(seconds=2))
        self.assertEqual((s,c,b),inputs);self.assertFalse(new['production_qualified'])

class IndependentStore(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='stage016-independent-',dir='/private/tmp')
        self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'cash.json';self.store=FundingStore(self.path)
        self.store.create(initial());self.next=recommend()['state']
    def test_15_WAL_before_state_replace_recovers_exactly_once(self):
        actual=self.store._atomic
        def crash(directory,name,state):
            if name==self.store.name:raise RuntimeError('INJECTED_AFTER_WAL')
            return actual(directory,name,state)
        with patch.object(self.store,'_atomic',side_effect=crash):
            with self.assertRaisesRegex(RuntimeError,'AFTER_WAL'):self.store.commit(0,self.next)
        fresh=FundingStore(self.path);self.assertEqual(fresh.load(),self.next);self.assertEqual(fresh.load(),self.next)
    def test_16_crash_before_WAL_is_safe_and_no_update(self):
        with patch.object(self.store,'_atomic',side_effect=RuntimeError('INJECTED_BEFORE_WAL')):
            with self.assertRaises(RuntimeError):self.store.commit(0,self.next)
        self.assertEqual(self.store.load(),initial())
    def test_17_WAL_current_state_already_replaced_cleanup_recovery(self):
        real=os.unlink
        def crash(name,*args,**kwargs):
            if name==self.store.journal_name:raise OSError('INJECTED_BEFORE_JOURNAL_CLEANUP')
            return real(name,*args,**kwargs)
        with patch('qmt_roll_weekly19_funding_store.os.unlink',side_effect=crash):
            with self.assertRaises(f.FundingError):self.store.commit(0,self.next)
        self.assertEqual(FundingStore(self.path).load(),self.next)
        self.assertFalse(self.path.with_name(self.path.name+'.journal').exists())
    def test_18_two_independent_store_handles_CAS_has_only_one_winner(self):
        barrier=Barrier(2)
        def race(label):
            obj=FundingStore(self.path);state=recommend(ids=[label])['state'];barrier.wait()
            try:obj.commit(0,state);return 'committed'
            except f.FundingError as e:return str(e)
        with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(race,['A','B']))
        self.assertEqual(outcomes.count('committed'),1);self.assertEqual(outcomes.count('revision_conflict'),1)
        self.assertEqual(self.store.load()['revision'],1)
    def test_19_corrupt_or_cross_release_journal_never_replaces_state(self):
        bad=copy.deepcopy(self.next);bad['material_release_id']='WRONG'
        # Make a fully internally consistent foreign identity journal.
        bad=initial();bad['material_release_id']='WRONG';bad['revision']=1
        journal=self.path.with_name(self.path.name+'.journal');journal.write_bytes(self.store._record(bad));journal.chmod(0o600)
        before=self.path.read_bytes()
        with self.assertRaisesRegex(f.FundingError,'journal_revision_or_identity_invalid'):self.store.load()
        self.assertEqual(self.path.read_bytes(),before)
    def test_20_recomputed_checksum_cannot_resurrect_paid_reserve(self):
        self.store.commit(0,self.next);rid=next(iter(self.next['requests']));accepted=paid(self.next,rid)
        self.store.commit(1,accepted);revived=copy.deepcopy(self.next);revived['revision']=3
        with self.assertRaisesRegex(f.FundingError,'store_ledger_rollback_forbidden'):self.store.commit(2,revived)
        self.assertEqual(self.store.load()['reserve_remaining_fen'],12000000)
    def test_21_parent_lock_state_journal_private_permissions(self):
        self.assertEqual(stat.S_IMODE(Path(self.tmp.name).stat().st_mode),0o700)
        for path in [self.path,self.path.with_name(self.path.name+'.lock')]:
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
        self.path.chmod(0o640)
        with self.assertRaises(f.FundingError):self.store.load()
    def test_22_future_revision_journal_and_journal_symlink_reject(self):
        journal=self.path.with_name(self.path.name+'.journal');bad=copy.deepcopy(initial());bad['revision']=2
        journal.write_bytes(self.store._record(bad));journal.chmod(0o600)
        with self.assertRaises(f.FundingError):self.store.load()
        journal.unlink();journal.symlink_to(self.path)
        with self.assertRaises(f.FundingError):self.store.load()
    def test_23_successful_receipt_store_restart_replay_does_not_debit_twice(self):
        self.store.commit(0,self.next);rid=next(iter(self.next['requests']));accepted=paid(self.next,rid)
        self.store.commit(1,accepted);fresh=FundingStore(self.path);replay=paid(fresh.load(),rid)
        fresh.commit(2,replay);self.assertEqual(fresh.load(),accepted)
    def test_24_stale_CAS_and_checkpoint_rollback_do_not_write(self):
        self.store.commit(0,self.next);before=self.path.read_bytes()
        with self.assertRaises(f.FundingError):self.store.commit(0,self.next)
        bad=copy.deepcopy(self.next);bad['revision']=2;bad['cashflow_checkpoint']['observed_at']=(T-timedelta(seconds=1)).isoformat()
        with self.assertRaises(f.FundingError):self.store.commit(1,bad)
        self.assertEqual(self.path.read_bytes(),before)

    def test_25_two_process_CAS_has_one_winner(self):
        worker = "import runpy,sys; d=runpy.run_path(sys.argv[1]); st=d['FundingStore'](d['Path'](sys.argv[2])); old=st.load(); new=d['recommend'](state=old,ids=[sys.argv[3]])['state']; print('READY',flush=True); sys.stdin.readline()\ntry:\n st.commit(0,new); print('committed',flush=True)\nexcept d['f'].FundingError as exc:\n print(str(exc),flush=True)\n"
        children=[subprocess.Popen([sys.executable,'-B','-c',worker,__file__,str(self.path),label],
          stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for label in ['P1','P2']]
        for child in children:self.addCleanup(lambda p=child: p.kill() if p.poll() is None else None)
        for child in children:self.assertEqual(child.stdout.readline().strip(),'READY')
        for child in children:child.stdin.write('GO\n');child.stdin.flush()
        outputs=[]
        for child in children:
            tail,err=child.communicate(timeout=10);self.assertEqual(child.returncode,0,err);outputs.append(tail.strip())
        self.assertEqual(sorted(outputs),['committed','revision_conflict'])
        self.assertEqual(self.store.load()['revision'],1)

if __name__=='__main__':
    runner=unittest.TextTestRunner(verbosity=2)
    result=runner.run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    raise SystemExit(not result.wasSuccessful())
