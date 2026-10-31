"""Independent source/provenance and Friday reporting adversarial tests.
All captures/ledgers/transports are synthetic. No CTP/bank/SMTP connects occur.
"""
from pathlib import Path
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
import copy,hashlib,json,os,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'tests')]
import qmt_roll_weekly19_broker_evidence as p
import qmt_roll_weekly19_funding as funding
from test_weekly19_broker_evidence import BrokerEvidenceTest,ACCOUNT,RELEASE,PROFILE,NOW
from test_weekly19_friday_report import inputs,account as report_account,NOW as FRIDAY
from qmt_roll_weekly19_friday_report import build_friday_report,FridayMailOutbox,ReportError,report_digest

def env(raw):
    t=json.dumps(raw,sort_keys=True,separators=(',',':'));return dict(raw_payload=t,raw_sha256=hashlib.sha256(t.encode()).hexdigest())
class Provider(unittest.TestCase):
    def setUp(self):
        self.x=BrokerEvidenceTest();self.x.setUp();self.addCleanup(self.x.doCleanups)
    def policy(self):
        kw=self.x._load_kwargs();kw['trusted_source_hashes']={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in p.CAPTURE_SOURCE_FILES};return kw
    def test_01_direct_funding_dependency_hash_wrong_rejected(self):
        self.x.publish();kw=self.policy();kw['trusted_source_hashes']['examples/portfolio_backtesting/qmt_roll_weekly19_funding.py']='0'*64
        with self.assertRaises(p.BrokerEvidenceError):p.load_broker_snapshot(self.x.summary_path,self.x.manifest_path,**kw)
    def test_02_direct_account_context_dependency_missing_rejected(self):
        self.x.publish();kw=self.policy();kw['trusted_source_hashes'].pop('examples/portfolio_backtesting/qmt_roll_official_live_broker_account_snapshot.py',None)
        with self.assertRaises(p.BrokerEvidenceError):p.load_broker_snapshot(self.x.summary_path,self.x.manifest_path,**kw)
    def test_03_minimum_five_semantic_source_closure(self):
        self.assertTrue(set(['examples/portfolio_backtesting/qmt_roll_weekly19_funding.py','examples/portfolio_backtesting/qmt_roll_official_live_broker_account_snapshot.py']).issubset(p.CAPTURE_SOURCE_FILES))
    def ledger(self,**kw):
        row=dict(account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE,broker_order_id='CTP.11_22_33',intent_id='independent-intent',signal_order_id='W19.independent',signal_identity=dict(intent_id='independent-intent',signal_order_id='W19.independent'),vt_symbol='rb2701.SHFE',direction='long',offset='open',completed_volume=999999);row.update(kw);return [row]
    def test_04_unknown_native_fill_enums_never_emit_null_fields(self):
        for key,other in [('Direction',dict(direction=None)),('OffsetFlag',dict(offset=None))]:
            self.x.publish(orders=[self.x.order],trades=[dict(self.x.trade,**{key:'9'})])
            with self.subTest(key=key),self.assertRaises(p.BrokerEvidenceError):
                p.load_broker_fills(self.x.summary_path,self.x.manifest_path,self.ledger(**other),**self.policy())
    def test_05_actual_fill_quantity_not_caller_ledger_or_fake_order_mapping(self):
        self.x.publish(orders=[self.x.order],trades=[self.x.trade]);v=p.load_broker_fills(self.x.summary_path,self.x.manifest_path,self.ledger(),**self.policy());raw=json.loads(v[0]['raw_payload'])
        self.assertEqual(raw['volume'],1);self.assertEqual(raw['source_callback'],'onRspQryTrade');self.assertFalse(raw['production_qualified'])
        with self.assertRaises(p.BrokerEvidenceError):p.load_broker_fills(self.x.summary_path,self.x.manifest_path,self.ledger()+self.ledger(),**self.policy())
    def test_06_default_production_authority_and_final_statement_stay_blocked(self):
        self.x.publish();kw=self.policy();kw.pop('require_production_qualification')
        with self.assertRaisesRegex(p.BrokerEvidenceError,'qualification_missing'):p.load_broker_snapshot(self.x.summary_path,self.x.manifest_path,**kw)
        with self.assertRaisesRegex(p.BrokerEvidenceError,'final_cashflow_statement_parser'):p.load_cashflow_day_close(env({'verified':True,'cashflows_complete':True}))
    def test_07_native_bank_query_freshness_not_only_outer_publish_time(self):
        col,state,rid,_,_=self.x.transfer_fixture();raw=json.loads(col.export_capture(now=NOW+timedelta(seconds=3))['raw_payload'])
        raw['request_sent_at']=(NOW-timedelta(days=30)).isoformat()
        for cb in raw['callbacks']:cb['received_at']=(NOW-timedelta(days=30)+timedelta(seconds=2)).isoformat()
        with self.assertRaises(p.BrokerEvidenceError):p.load_bank_cashflow_receipt(env(raw),state=state,request_id=rid,bank_serial='BANK-REF-1',now=NOW+timedelta(seconds=3),require_production_qualification=False)
    def test_08_bank_record_cannot_occur_after_query_callback(self):
        col,state,rid,_,_=self.x.transfer_fixture();raw=json.loads(col.export_capture(now=NOW+timedelta(seconds=3))['raw_payload']);raw['rows'][0]['TradeTime']='21:00:03'
        with self.assertRaises(p.BrokerEvidenceError):p.load_bank_cashflow_receipt(env(raw),state=state,request_id=rid,bank_serial='BANK-REF-1',now=NOW+timedelta(seconds=3),require_production_qualification=False)
    def test_09_transfer_callback_context_restores_on_exception_without_connect(self):
        col,_,_,_,_=self.x.transfer_fixture()
        class Fake:
            def onRspQryTransferSerial(self,*a):return 'ORIGINAL'
        obj=Fake();original=Fake.onRspQryTransferSerial
        with self.assertRaises(RuntimeError):
            with p.instrument_transfer_serial_callback(obj,col,connection_generation=lambda:'connection-1',clock=lambda:NOW):raise RuntimeError('INJECTED')
        self.assertIs(Fake.onRspQryTransferSerial,original)
    def test_10_raw_capture_mode_and_hardlink_reject_even_hash_unchanged(self):
        _,manifest=self.x.publish();path=Path(manifest['weekly19_capture']['path']);path.chmod(0o640)
        with self.assertRaises(p.BrokerEvidenceError):p.load_broker_snapshot(self.x.summary_path,self.x.manifest_path,**self.policy())
        path.chmod(0o600);os.link(path,self.x.root/'SECOND-LINK')
        with self.assertRaises(p.BrokerEvidenceError):p.load_broker_snapshot(self.x.summary_path,self.x.manifest_path,**self.policy())

    def test_11_SHFE_close_flags_keep_native_proof_and_business_close(self):
        for flag,kind in [('1','close'),('3','closetoday'),('4','closeyesterday')]:
            order=dict(self.x.order,Direction='1',CombOffsetFlag=flag);trade=dict(self.x.trade,Direction='1',OffsetFlag=flag)
            self.x.publish(orders=[order],trades=[trade]);row=json.loads(p.load_broker_fills(self.x.summary_path,self.x.manifest_path,self.ledger(direction='short',offset='close'),**self.policy())[0]['raw_payload'])
            self.assertEqual((row['offset'],row['business_offset'],row['broker_offset'],row['native_offset_flag']),('close','close',kind,flag))
            with self.assertRaises(p.BrokerEvidenceError):p.load_broker_fills(self.x.summary_path,self.x.manifest_path,self.ledger(direction='short',offset='close',broker_offset='open'),**self.policy())

class Report(unittest.TestCase):
    def guarded(self,i):
        try:return build_friday_report(**i,preview=False)
        except ReportError:return {'actionable':False,'rejected':True}
    def test_11_stale_30k_request_at_current50k_gap_is_not_actionable(self):
        i=inputs();i['broker_account']=report_account('100000.00');r=self.guarded(i);self.assertFalse(r['actionable'])
    def test_12_missing_actionable_cannot_default_true(self):
        i=inputs();i['recommendation'].pop('actionable',None);self.assertFalse(self.guarded(i)['actionable'])
    def test_13_wrong_request_id_or_source_cannot_be_actionable(self):
        for kw in [dict(request_id='f'*64),dict(amount_fen=2999999)]:
            i=inputs();i['recommendation'].update(kw);self.assertFalse(self.guarded(i)['actionable'])
    def test_14_positive_advice_without_current_native_admission_is_not_actionable(self):
        i=inputs();i['decision']['funding_admitted_ids']=[];i['decision']['intents']=[];self.assertFalse(self.guarded(i)['actionable'])
    def test_15_old_pending_is_shown_when_this_batch_has_no_advice(self):
        i=inputs();i['recommendation']={'status':'no_admitted_entry','amount_fen':0,'actionable':False};i['decision']['funding_admitted_ids']=[];i['decision']['intents']=[]
        r=build_friday_report(**i);self.assertEqual(r['historical_pending_fen'],3000000);self.assertFalse(r['funding_ready']);self.assertIn('历史',r['body'])
    def test_16_E_recovered_means_no_old_debt_and_no_virtual_new_cash(self):
        i=inputs();i['broker_account']=report_account('151000.00');r=build_friday_report(**i,preview=False)
        self.assertEqual(r['current_recommendation_fen'],0);self.assertFalse(r['actionable']);self.assertEqual(r['reserve_remaining_fen'],15000000);self.assertIn('不必补足旧建议',r['body'])
    def test_17_last_week_source_and_bad_raw_cash_are_blocked(self):
        i=inputs();i['now']=FRIDAY+timedelta(days=7);i['broker_account']=report_account(at=i['now']);r=self.guarded(i);self.assertFalse(r['actionable'])
        i=inputs();i['broker_account']['raw_sha256']='0'*64;r=self.guarded(i);self.assertFalse(r['actionable'])
    def test_18_foreign_currency_never_calculates_actionable_CNY_amount(self):
        i=inputs();raw=json.loads(i['broker_account']['raw_payload']);raw['CurrencyID']='USD';i['broker_account']=env(raw);self.assertFalse(self.guarded(i)['actionable'])

    def test_23_valid_current_bound_advice_is_not_permanently_blocked(self):
        r=build_friday_report(**inputs(),preview=False)
        self.assertTrue(r['actionable']);self.assertEqual(r['current_recommendation_fen'],3000000)
        self.assertFalse(r['funding_ready']);self.assertFalse(r['production_qualified'])
        self.assertEqual(r['equity_fen'],12000000)

class Outbox(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(dir='/private/tmp');self.addCleanup(self.t.cleanup);self.root=Path(self.t.name).resolve();self.out=FridayMailOutbox(self.root);self.report=build_friday_report(**inputs(),preview=False)
    def test_19_preview_never_calls_even_injected_transport(self):
        r=build_friday_report(**inputs());calls=[];self.assertEqual(self.out.deliver(r,lambda _:calls.append('called'))['status'],'preview_only');self.assertEqual(calls,[])
    def test_20_threaded_same_release_week_has_one_transport_attempt(self):
        barrier=Barrier(2);calls=[]
        def run(_):
            out=FridayMailOutbox(self.root);barrier.wait();return out.deliver(self.report,lambda r:(calls.append(1) or {'email_status':'sent'}))['status']
        with ThreadPoolExecutor(max_workers=2)as pool:results=list(pool.map(run,[1,2]))
        self.assertEqual(calls,[1]);self.assertEqual(sorted(results),['already_sent','sent'])
    def test_21_crash_after_transport_before_final_state_is_unknown_no_retry(self):
        real=self.out._write;calls=[]
        def fault(name,obj,fd):
            if obj['status']=='sent':raise OSError('INJECTED_AFTER_SEND')
            return real(name,obj,fd)
        with patch.object(self.out,'_write',side_effect=fault):
            with self.assertRaises(OSError):self.out.deliver(self.report,lambda _:(calls.append(1)or{'email_status':'sent'}))
        again=FridayMailOutbox(self.root).deliver(self.report,lambda _:(calls.append(2)or{'email_status':'sent'}))
        self.assertEqual(again['status'],'delivery_unknown');self.assertEqual(calls,[1])
    def test_22_tamper_body_and_private_outbox_mode_reject_before_transport(self):
        r=copy.deepcopy(self.report);r['body']+='TAMPER';calls=[]
        with self.assertRaises(ReportError):self.out.deliver(r,lambda _:calls.append(1))
        self.assertEqual(calls,[]);self.root.chmod(0o750)
        with self.assertRaises(ReportError):FridayMailOutbox(self.root)
if __name__=='__main__':
    choice=sys.argv[1] if len(sys.argv)>1 else 'all';classes=[Provider]if choice=='provider'else[Report,Outbox]if choice=='report'else[Provider,Report,Outbox]
    suite=unittest.TestSuite()
    for cls in classes:suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
    result=unittest.TextTestRunner(verbosity=2).run(suite);raise SystemExit(not result.wasSuccessful())
