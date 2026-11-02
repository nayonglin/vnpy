"""Same-connection frozen native epoch fixtures, never production proof."""
import copy
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import stat
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'examples/portfolio_backtesting'))
import qmt_roll_weekly19_broker_evidence as provider
import test_weekly19_broker_evidence as fixtures
try:
    import qmt_roll_weekly19_warm_evidence as warm
except ModuleNotFoundError:
    warm=None

ROOT=Path(__file__).resolve().parents[1]
NOW=fixtures.NOW


class WarmEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(warm,'same-connection native warm builder is absent')
        self.fixture=fixtures.BrokerEvidenceTest()
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        identity=dict(account_key=fixtures.ACCOUNT,material_release_id=fixtures.RELEASE,execution_profile=fixtures.PROFILE,
            service_generation='warm-service-1',connection_generation='warm-connection-1')
        data=dict(account=[self.fixture.account],positions=[self.fixture.position],
            orders=[dict(self.fixture.order,InsertTime='20:58:59')],
            trades=[dict(self.fixture.trade,TradeTime='20:59:00')])
        receipts={};rows=dict(_weekly19_capture_identity=identity,_native_order_api_call_counts=dict(reqOrderInsert=7))
        epoch_keys=dict(account='_final_account_funds_epoch',positions='_position_query_epoch',orders='_order_query_epoch',trades='_trade_query_epoch')
        for index,kind in enumerate(('account','positions','orders','trades')):
            sent=NOW-timedelta(seconds=30-index*4);done=sent+timedelta(seconds=1)
            reqid=301+index
            callbacks=[dict(data=copy.deepcopy(item),error=dict(ErrorID=0),reqid=reqid,last=i==len(data[kind])-1,
                received_at=done.isoformat(),connection_generation=identity['connection_generation']) for i,item in enumerate(data[kind])]
            receipt=dict(identity,schema='weekly19.warm-native-query-epoch.v1',kind=kind,query_reqid=reqid,
                request_sent_at=sent.isoformat(),completed_at=done.isoformat(),request_return_code=0,request_ret=0,
                last_seen=True,error_rows=0,native_callbacks=callbacks,late_callback_blockers=[])
            receipts[kind]=receipt
            rows[epoch_keys[kind]]=dict(complete_reqid=reqid,active_reqid=None,weekly19_native_receipt=copy.deepcopy(receipt))
        rows['_weekly19_native_receipts']=receipts
        class NoQuery:
            def reqQryOrder(self,*args): raise AssertionError('warm builder must not query')
            def reqQryTrade(self,*args): raise AssertionError('warm builder must not query')
            def reqQryTradingAccount(self,*args): raise AssertionError('warm builder must not query')
            def reqQryInvestorPosition(self,*args): raise AssertionError('warm builder must not query')
            def connect(self,*args): raise AssertionError('warm builder must not connect')
        self.context=dict(rows=rows,td_api=NoQuery(),connection_generation=identity['connection_generation'],
            service_generation=identity['service_generation'])
        self.policy=dict(expected_account_key=fixtures.ACCOUNT,material_release_id=fixtures.RELEASE,execution_profile=fixtures.PROFILE,
            now=NOW,trusted_source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                for name in (*provider.CAPTURE_SOURCE_FILES,'examples/portfolio_backtesting/qmt_roll_weekly19_warm_evidence.py')},
            require_production_qualification=False)

    def load(self,context=None,**changes):
        return warm.load_warm_broker_snapshot(self.context if context is None else context,**dict(self.policy,**changes))

    def test_valid_frozen_same_connection_epochs_produce_original_funds_and_orders_without_query(self):
        before=copy.deepcopy(self.context['rows'])
        result=self.load()
        account=json.loads(result['account']['raw_payload']);positions=json.loads(result['positions']['raw_payload'])
        orders=json.loads(result['orders']['raw_payload']);trades=json.loads(result['trades']['raw_payload'])
        self.assertEqual((account['Balance'],account['Deposit'],account['Withdraw']),('120000.00','0.00','0.00'))
        self.assertEqual(positions['positions'],[dict(vt_symbol='rb2701.SHFE',direction='long',volume=2)])
        self.assertEqual((orders['orders'][0]['volume'],orders['orders'][0]['traded']),(2,1))
        self.assertEqual(trades['trades'][0]['broker_trade_identity'],'ctp:9999:test-account:SHFE:20261030:SYS-1:TR-1')
        self.assertFalse(result['production_qualified']);self.assertFalse(result['source_qualified'])
        self.assertEqual(self.context['rows'],before)
        self.assertEqual(account['capture_kind'],'warm_epoch_snapshot')
        self.assertEqual(account['connection_generation'],'warm-connection-1')

    def test_warm_real_order_counters_are_not_mislabelled_readonly_api_zero(self):
        self.context['rows']['send_order_api_called_count']=9
        self.context['rows']['cancel_order_api_called_count']=3
        self.assertEqual(json.loads(self.load()['account']['raw_payload'])['Balance'],'120000.00')

    def test_missing_frozen_receipts_do_not_fall_back_to_normalized_or_pending_rows(self):
        del self.context['rows']['_weekly19_native_receipts']['orders']
        self.context['rows']['_order_query_epoch']['authoritative_orders']=[dict(vt_orderid='CTP.11_22_33')]
        self.context['rows']['_order_query_epoch']['pending_callbacks']=[]
        with self.assertRaisesRegex(warm.WarmEvidenceError,'frozen_native_receipt_missing'):
            self.load()

    def test_query_reqid_last_error_late_return_and_connection_mismatch_fail_closed(self):
        for key,value in (('query_reqid',0),('last_seen',False),('error_rows',1),('request_return_code',-1),
            ('connection_generation','old'),('late_callback_blockers',['late'])):
            context=copy.deepcopy(self.context)
            context['rows']['_weekly19_native_receipts']['orders'][key]=value
            with self.subTest(key=key),self.assertRaises(warm.WarmEvidenceError): self.load(context)
        for key,value in (('reqid',0),('last',False),('connection_generation','old'),('error',dict(ErrorID=1))):
            context=copy.deepcopy(self.context);context['rows']['_weekly19_native_receipts']['orders']['native_callbacks'][0][key]=value
            with self.subTest(key=key),self.assertRaises(warm.WarmEvidenceError): self.load(context)

    def test_stale_future_naive_and_cross_epoch_generation_are_rejected(self):
        for stamp in ((NOW-timedelta(minutes=10)).isoformat(),(NOW+timedelta(seconds=1)).isoformat(),NOW.replace(tzinfo=None).isoformat()):
            context=copy.deepcopy(self.context)
            context['rows']['_weekly19_native_receipts']['account']['completed_at']=stamp
            with self.subTest(stamp=stamp),self.assertRaises(warm.WarmEvidenceError): self.load(context)
        context=copy.deepcopy(self.context);context['connection_generation']='new'
        with self.assertRaises(warm.WarmEvidenceError): self.load(context)

    def test_raw_account_identity_cash_fields_and_native_object_shape_are_mandatory(self):
        for changes in (dict(AccountID='other'),dict(Deposit='NaN'),dict(CurrencyID='USD')):
            context=copy.deepcopy(self.context);context['rows']['_weekly19_native_receipts']['account']['native_callbacks'][0]['data'].update(changes)
            context['rows']['_final_account_funds_epoch']['weekly19_native_receipt']=copy.deepcopy(context['rows']['_weekly19_native_receipts']['account'])
            with self.subTest(changes=changes),self.assertRaises(warm.WarmEvidenceError): self.load(context)
        context=copy.deepcopy(self.context)
        context['rows']['_weekly19_native_receipts']['orders']['native_callbacks'][0]['data']=dict(vt_orderid='CTP.11_22_33',status='cancelled')
        context['rows']['_order_query_epoch']['weekly19_native_receipt']=copy.deepcopy(context['rows']['_weekly19_native_receipts']['orders'])
        with self.assertRaises(warm.WarmEvidenceError): self.load(context)

    def test_epoch_mirror_mismatch_and_missing_or_wrong_warm_source_pin_rejected(self):
        self.context['rows']['_order_query_epoch']['complete_reqid']=999
        with self.assertRaises(warm.WarmEvidenceError): self.load()
        self.setUp()
        for name in (provider.CAPTURE_SOURCE_FILES[-1],'examples/portfolio_backtesting/qmt_roll_weekly19_warm_evidence.py'):
            pins=dict(self.policy['trusted_source_hashes']);pins[name]='0'*64
            with self.subTest(name=name),self.assertRaises(warm.WarmEvidenceError): self.load(trusted_source_hashes=pins)

    def test_shfe_offsets_retained_and_trade_native_order_mismatch_rejected(self):
        context=copy.deepcopy(self.context)
        for kind,field in (('orders','CombOffsetFlag'),('trades','OffsetFlag')):
            context['rows']['_weekly19_native_receipts'][kind]['native_callbacks'][0]['data'][field]='3'
            context['rows']['_weekly19_native_receipts'][kind]['native_callbacks'][0]['data']['Direction']='1'
            context['rows'][dict(orders='_order_query_epoch',trades='_trade_query_epoch')[kind]]['weekly19_native_receipt']=copy.deepcopy(context['rows']['_weekly19_native_receipts'][kind])
        result=self.load(context)
        self.assertEqual(json.loads(result['orders']['raw_payload'])['orders'][0]['broker_offset'],'closetoday')
        self.assertEqual(json.loads(result['trades']['raw_payload'])['trades'][0]['offset'],'close')
        context['rows']['_weekly19_native_receipts']['trades']['native_callbacks'][0]['data']['OffsetFlag']='4'
        context['rows']['_trade_query_epoch']['weekly19_native_receipt']=copy.deepcopy(context['rows']['_weekly19_native_receipts']['trades'])
        with self.assertRaises(warm.WarmEvidenceError): self.load(context)

    def test_duplicate_or_inconsistent_native_order_is_not_a_complete_unique_snapshot(self):
        context=copy.deepcopy(self.context);receipt=context['rows']['_weekly19_native_receipts']['orders']
        receipt['native_callbacks'][0]['last']=False
        receipt['native_callbacks'].append(copy.deepcopy(receipt['native_callbacks'][0]));receipt['native_callbacks'][-1]['last']=True
        context['rows']['_order_query_epoch']['weekly19_native_receipt']=copy.deepcopy(receipt)
        context['rows']['_weekly19_native_receipts']['trades']['native_callbacks'][0]['data']={}
        context['rows']['_trade_query_epoch']['weekly19_native_receipt']=copy.deepcopy(context['rows']['_weekly19_native_receipts']['trades'])
        with self.assertRaisesRegex(warm.WarmEvidenceError,'native_order_identity_duplicate'): self.load(context)
        for changes in (dict(OrderStatus='0',VolumeTraded=1),dict(InsertTime='23:00:00'),dict(OrderRef='invalid')):
            context=copy.deepcopy(self.context);receipt=context['rows']['_weekly19_native_receipts']['orders']
            receipt['native_callbacks'][0]['data'].update(changes)
            context['rows']['_order_query_epoch']['weekly19_native_receipt']=copy.deepcopy(receipt)
            with self.subTest(changes=changes),self.assertRaises(warm.WarmEvidenceError): self.load(context)

    def test_private_warm_capture_is_not_qualified_by_caller_flag_or_native_looking_dict(self):
        path=self.fixture.root/'warm.json'
        reference=warm.persist_warm_native_query_capture(path,self.context,**self.policy)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),reference['sha256'])
        self.context['weekly19_warm_capture_reference']=reference
        self.context['qualified']=True
        with self.assertRaisesRegex(warm.WarmEvidenceError,'warm_capture_authority_missing'):
            self.load(require_production_qualification=True)
        with self.assertRaises(warm.WarmEvidenceError):
            self.load(require_production_qualification=True,capture_authority_capability=dict(qualified=True))

    def test_warm_query_recovery_events_bind_real_partial_fill_before_cumulative_order(self):
        ledger=[self.fixture.order_ledger(intent_id='W19EXEC-delivery',planned_intent_id='intent-1')]
        events=warm.load_warm_broker_events(self.context,ledger,**self.policy)
        self.assertEqual(events['apply_order'],['fills','orders'])
        fill=json.loads(events['fills'][0]['raw_payload']);order=json.loads(events['orders'][0]['raw_payload'])
        self.assertEqual((fill['volume'],order['traded'],order['status']),(1,1,'partially_filled'))
        self.assertEqual((fill['intent_id'],fill['delivery_intent_id']),('intent-1','W19EXEC-delivery'))
        self.assertEqual((fill['source_callback'],order['source_callback']),('onRspQryTrade','onRspQryOrder'))
        self.assertEqual(warm.load_warm_broker_events(self.context,ledger,**self.policy),events)
        with self.assertRaises(warm.WarmEvidenceError):
            warm.load_warm_broker_events(self.context,[dict(ledger[0],planned_intent_id='other')],**self.policy)
        with self.assertRaisesRegex(warm.WarmEvidenceError,'warm_capture_authority_missing'):
            warm.load_warm_broker_events(self.context,ledger,**dict(self.policy,require_production_qualification=True))

    def test_warm_recovery_event_semantics_stable_across_query_generation_and_shfe_child(self):
        ledger=[self.fixture.order_ledger(offset='close',planned_volume=2,broker_order_volume=1,broker_offset='closeyesterday')]
        context=copy.deepcopy(self.context)
        for kind,offsetkey in (('orders','CombOffsetFlag'),('trades','OffsetFlag')):
            receipt=context['rows']['_weekly19_native_receipts'][kind]
            receipt['native_callbacks'][0]['data'][offsetkey]='4'
            if kind=='orders':receipt['native_callbacks'][0]['data'].update(VolumeTotalOriginal=1,OrderStatus='0')
            context['rows'][warm.EPOCH_KEYS[kind]]['weekly19_native_receipt']=copy.deepcopy(receipt)
        first=warm.load_warm_broker_events(context,ledger,**self.policy)
        for kind,receipt in context['rows']['_weekly19_native_receipts'].items():
            receipt['query_reqid']+=100
            for callback in receipt['native_callbacks']:callback['reqid']+=100
            context['rows'][warm.EPOCH_KEYS[kind]].update(complete_reqid=receipt['query_reqid'],weekly19_native_receipt=copy.deepcopy(receipt))
        again=warm.load_warm_broker_events(context,ledger,**self.policy)
        self.assertEqual(json.loads(first['orders'][0]['raw_payload'])['event_id'],json.loads(again['orders'][0]['raw_payload'])['event_id'])
        self.assertEqual(json.loads(first['fills'][0]['raw_payload'])['trade_id'],json.loads(again['fills'][0]['raw_payload'])['trade_id'])
        self.assertNotEqual(first['fills'][0]['raw_sha256'],again['fills'][0]['raw_sha256'])
        self.assertEqual(json.loads(first['fills'][0]['raw_payload'])['broker_offset'],'closeyesterday')

    def test_v6_warm_query_events_preserve_quota_children_and_actual_child_only(self):
        rows=self.fixture.batch_ledger(both_native=False)
        path=self.fixture.root/'warm-quota.jsonl';path.write_text(''.join(json.dumps(r)+'\n' for r in rows));path.chmod(0o600)
        bindings=provider.load_execution_order_intent_bindings(path,expected_account_key=fixtures.ACCOUNT,
            material_release_id=fixtures.RELEASE,execution_profile=fixtures.PROFILE)
        context=copy.deepcopy(self.context)
        for kind,key in (('orders','CombOffsetFlag'),('trades','OffsetFlag')):
            receipt=context['rows']['_weekly19_native_receipts'][kind];receipt['native_callbacks'][0]['data'][key]='3'
            if kind=='orders':receipt['native_callbacks'][0]['data'].update(VolumeTotalOriginal=1,VolumeTraded=1,OrderStatus='0')
            context['rows'][warm.EPOCH_KEYS[kind]]['weekly19_native_receipt']=copy.deepcopy(receipt)
        events=warm.load_warm_broker_events(context,bindings,**self.policy)
        for envelope in events['fills']+events['orders']:
            raw=json.loads(envelope['raw_payload'])
            self.assertEqual((raw['volume'],raw['approved_parent_volume'],len(raw['expected_children'])),(1,2,2))
            self.assertEqual(raw['execution_batch_id'],rows[0]['api_slot_batch_id'])
            self.assertEqual(raw['execution_batch_proof']['native_identity_record_checksum'],rows[1]['record_checksum'])
            self.assertNotIn('broker_order_id',raw['expected_children'][1])

    def test_future_native_trade_time_is_not_relabelled_as_current_query_time(self):
        context=copy.deepcopy(self.context)
        context['rows']['_weekly19_native_receipts']['trades']['native_callbacks'][0]['data']['TradeTime']='23:00:00'
        context['rows']['_trade_query_epoch']['weekly19_native_receipt']=copy.deepcopy(context['rows']['_weekly19_native_receipts']['trades'])
        with self.assertRaisesRegex(warm.WarmEvidenceError,'native_trade_after_query_callback'):
            self.load(context)


if __name__=='__main__': unittest.main()
