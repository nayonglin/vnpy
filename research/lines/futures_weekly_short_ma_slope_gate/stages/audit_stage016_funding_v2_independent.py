"""Independent funding V2 lifecycle tests, all synthetic/no external API."""
from pathlib import Path
from datetime import datetime,timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import copy, hashlib, importlib.util, json, runpy, subprocess, sys, tempfile, types, unittest
ROOT=Path(__file__).resolve().parents[4]
D=runpy.run_path(str(Path(__file__).with_name('audit_stage016_funding_independent.py')))
f=D['f'];Store=D['FundingStore'];account=D['account'];cash=D['cash'];recommend=D['recommend'];pending=D['pending'];paid=D['paid'];closure=D['closure'];T=D['T'];A=D['A'];R=D['R'];S=D['S']
def legacy():
    src=subprocess.check_output(['git','show','09e7e07e8:examples/portfolio_backtesting/qmt_roll_weekly19_funding.py'],cwd=ROOT,text=True)
    m=types.ModuleType('independent_actual_v1_checkpoint');exec(compile(src,'<actual-git-v1-checkpoint>','exec'),m.__dict__);return m
class V2(unittest.TestCase):
    def test_01_actual_v1_partial_upgrade_preserves_all_old_money_identity(self):
        v=legacy();old=v.recommend_topup(v.initial_state(A,R,'2026-10-30'),account(),'2026-10-30',['FAKE-NATIVE-1'],S,T)['state'];rid=next(iter(old['requests']))
        old=v.confirm_topup(old,rid,cash(rid,'10000'),account('130000','10000',at=T+timedelta(seconds=2)),T+timedelta(seconds=2));before=copy.deepcopy(old)
        upgraded=f.upgrade_funding_state(old);self.assertEqual(old,before);self.assertEqual(upgraded['revision'],old['revision']+1)
        for k in old:
            if k not in ('schema','revision'):self.assertEqual(upgraded[k],old[k],k)
        self.assertEqual(f.upgrade_funding_state(upgraded),upgraded)
        with self.assertRaisesRegex(f.FundingError,'upgrade_required'):f.assert_open_funding_ready(old,account('150000','10000',at=T+timedelta(seconds=2)),T+timedelta(seconds=2))
    def test_02_explicit_single_CAS_migration_and_reject_mutated_upgrade(self):
        v=legacy();old=v.initial_state(A,R,'2026-10-30')
        with tempfile.TemporaryDirectory(dir='/private/tmp') as t:
            st=Store(Path(t)/'s.json');st.create(old);up=f.upgrade_funding_state(old);bad=copy.deepcopy(up);bad['cashflow_checkpoint']=recommend(ids=[])['state']['cashflow_checkpoint']
            with self.assertRaisesRegex(f.FundingError,'explicit_v2_migration'):st.commit(0,bad)
            st.commit(0,up);self.assertEqual(st.load(),up)
            with self.assertRaisesRegex(f.FundingError,'revision_conflict'):st.commit(0,up)
    def test_03_v1_identical_WAL_recovery_before_migration(self):
        old=legacy().initial_state(A,R,'2026-10-30')
        with tempfile.TemporaryDirectory(dir='/private/tmp') as t:
            path=Path(t)/'s.json';st=Store(path);st.create(old);j=path.with_name('s.json.journal');j.write_bytes(st._record(old));j.chmod(0o600)
            self.assertEqual(st.load(),old);self.assertFalse(j.exists());up=f.upgrade_funding_state(old);st.commit(0,up);self.assertEqual(st.load(),up)
    def test_04_recovery_does_not_make_old_offer_a_debt(self):
        s,rid=pending();b=account('150000');f.assert_open_funding_ready(s,b,T)
        v=recommend(s,b);self.assertEqual(v['recommendation']['amount_fen'],0);self.assertEqual(v['state']['reserve_remaining_fen'],15000000)
        self.assertEqual(v['state']['requests'][rid]['confirmed_fen'],0)
        with self.assertRaises(f.FundingError):f.assert_open_funding_ready(s,account('149999.99'),T)
    def test_05_partial_at_floor_retains_unpaid_outside(self):
        s,rid=pending();s=paid(s,rid,'10000','10000');at=T+timedelta(seconds=3);b=account('150000','10000',at=at)
        f.assert_open_funding_ready(s,b,at);v=recommend(s,b,now=at)
        self.assertEqual(v['recommendation']['amount_fen'],0);self.assertEqual(v['recommendation']['historical_request_remaining_fen'],2000000)
        self.assertEqual(v['state']['reserve_remaining_fen'],14000000)
    def test_06_recovery_cannot_hide_new_deposit_or_withdrawal(self):
        s,rid=pending()
        for b in [account('200000','0.01'),account('200000',withdraw='0.01')]:
            with self.assertRaises(f.FundingError):f.assert_open_funding_ready(s,b,T)
            with self.assertRaises(f.FundingError):f.retire_topup_request(s,rid,b,T,reason='equity_recovered')
    def test_07_new_gap_is_non_actionable_and_old_cap_immutable(self):
        s,rid=pending();v=recommend(s,account('100000'));rec=v['recommendation']
        self.assertEqual((rec['status'],rec['amount_fen'],rec['actionable'],rec['request_id']),('request_refresh_required',5000000,False,None))
        self.assertEqual(v['state']['requests'][rid]['amount_fen'],3000000)
        retired=f.retire_topup_request(v['state'],rid,account('100000'),T,reason='superseded_current_gap')
        new=recommend(retired,account('100000'));nr=new['recommendation']['request_id']
        self.assertNotEqual(nr,rid);self.assertEqual(new['state']['admitted_entries'],s['admitted_entries']);self.assertEqual(next(iter(new['state']['request_attempts'].values())),[rid,nr])
    def test_08_late_old_cash_and_known_receipt_replay_are_distinct(self):
        s,rid=pending();s=paid(s,rid,'10000','10000');at=T+timedelta(seconds=3);b=account('150000','10000',at=at)
        retired=f.retire_topup_request(s,rid,b,at,reason='equity_recovered')
        self.assertEqual(f.confirm_topup(retired,rid,cash(rid,'10000'),b,at),retired)
        with self.assertRaisesRegex(f.FundingError,'retired_request'):
            f.confirm_topup(retired,rid,cash(rid,'20000','LATE',at=at+timedelta(seconds=1)),account('170000','30000',at=at+timedelta(seconds=2)),at+timedelta(seconds=2))
    def test_09_confirmed_admission_not_reused_across_generations_or_sources(self):
        s,rid=pending();s=paid(s,rid);at=T+timedelta(seconds=3)
        for i in range(3):
            b=account('130000','30000',at=at,generation_uuid='FAKE-NEW-'+str(i));v=f.recommend_topup(s,b,'2026-10-30',['FAKE-NATIVE-1'],str(i)*64,at)
            self.assertEqual(v['recommendation']['status'],'duplicate_admission');self.assertEqual(len(v['state']['requests']),1);self.assertEqual(v['state']['reserve_remaining_fen'],12000000)
    def test_10_recovery_retirement_consumes_candidate_and_no_R_refund(self):
        s,rid=pending();s=f.retire_topup_request(s,rid,account('150000'),T,reason='equity_recovered')
        v=recommend(s,account('130000'));self.assertEqual(v['recommendation']['status'],'duplicate_admission');self.assertEqual(v['state']['reserve_remaining_fen'],15000000)
        f.assert_open_funding_ready(s,account('130000'),T)
    def test_11_expiry_chain_can_retire_without_extending_old_deadline(self):
        s,rid=pending();s=paid(s,rid,'10000','10000');original=s['requests'][rid]['expires_at'];at=T+timedelta(minutes=1);day='2026-10-30';dep='10000'
        for nxt in ['2026-11-02','2026-11-03','2026-11-04','2026-11-05','2026-11-06']:
            closing=account('142000',dep,at=at,day=day);following=datetime.fromisoformat(nxt+'T16:10:00+08:00')
            s=f.reconcile_trading_day(s,closing,account('142000',at=following,day=nxt),following,continuity_receipt=closure(closing,nextday=nxt,at=at+timedelta(seconds=1)))
            at=following+timedelta(minutes=1);day=nxt;dep='0'
        self.assertEqual(s['requests'][rid]['expires_at'],original)
        s=f.retire_topup_request(s,rid,account('142000',at=at,day=day),at,reason='expired_superseded')
        self.assertEqual(s['reserve_remaining_fen'],14000000);self.assertEqual(s['requests'][rid]['status'],'retired_partial')
        v=f.recommend_topup(s,account('142000',at=at,day=day),'2026-11-06',['FAKE-NEW-WEEK'],S,at)
        self.assertEqual(v['recommendation']['amount_fen'],800000)
    def test_12_missing_cross_day_evidence_never_allows_retirement(self):
        s,rid=pending();at=T+timedelta(days=3)
        with self.assertRaises(f.FundingError):f.retire_topup_request(s,rid,account('200000',at=at,day='2026-11-02'),at,reason='equity_recovered')
    def test_13_append_only_retirement_attempt_and_schema_persistence(self):
        s,rid=pending();s=f.retire_topup_request(s,rid,account('100000'),T,reason='superseded_current_gap');v=recommend(s,account('100000'))['state']
        with tempfile.TemporaryDirectory(dir='/private/tmp') as t:
            st=Store(Path(t)/'s.json');st.create(f.initial_state(A,R,'2026-10-30'));first=recommend()['state'];st.commit(0,first);st.commit(1,s);st.commit(2,v)
            bad=copy.deepcopy(v);bad['revision']+=1;next(iter(bad['request_attempts'].values())).pop()
            with self.assertRaises(f.FundingError):st.commit(v['revision'],bad)
            self.assertEqual(st.load(),v)
    def test_14_schema_downgrade_rejected_even_if_empty_v1_valid(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as t:
            st=Store(Path(t)/'s.json');st.create(f.initial_state(A,R,'2026-10-30'));old=legacy().initial_state(A,R,'2026-10-30');old['revision']=1
            with self.assertRaises(f.FundingError):st.commit(0,old)
    def test_15_first_lock_creation_with_two_handles_is_safe(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as t:
            path=Path(t)/'s.json';st=Store(path);st.create(f.initial_state(A,R,'2026-10-30'))
            path.with_name('s.json.lock').unlink()  # fixture only; no live lock exists
            barrier=Barrier(2)
            def load(_):barrier.wait();return Store(path).load()
            with ThreadPoolExecutor(2) as pool:values=list(pool.map(load,[1,2]))
            self.assertEqual(values,[f.initial_state(A,R,'2026-10-30')]*2)

if __name__=='__main__':
    suite=unittest.TestSuite()
    for cls in [D['IndependentFunding'],D['IndependentStore'],V2]:suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
    result=unittest.TextTestRunner(verbosity=2).run(suite);raise SystemExit(not result.wasSuccessful())
