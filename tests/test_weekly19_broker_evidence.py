"""Offline capture fixtures. None is a production/broker-origin qualification."""
import copy
from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

os.environ.setdefault('QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR', '1')
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'examples/portfolio_backtesting'
sys.path.insert(0, str(SOURCE))
import run_ctp_stage174_readonly_probe as stage174
import qmt_roll_weekly19_funding as funding
try:
    import qmt_roll_weekly19_broker_evidence as provider
except ModuleNotFoundError:
    provider = None

NOW = datetime.fromisoformat('2026-10-30T21:00:00+08:00')
DAY = '20261102'
RELEASE = 'weekly19-test-release'
PROFILE = 'weekly19-15w-r150k'
ACCOUNT = hashlib.sha256(b'9999\0test-account').hexdigest()
GENERATION = '11111111-2222-4333-8444-555555555555'


class BrokerEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(provider, 'weekly19 broker evidence provider is absent')
        self.temp = tempfile.TemporaryDirectory(prefix='weekly19-provider-', dir='/private/tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.summary_path = self.root/'summary.json'
        self.manifest_path = self.root/'manifest.json'
        self.account = dict(BrokerID='9999', AccountID='test-account', CurrencyID='CNY', TradingDay=DAY,
            Balance=120000.0, Available=90000.0, Deposit=0.0, Withdraw=0.0, CurrMargin=30000.0,
            FrozenMargin=0.0, FrozenCash=0.0, FrozenCommission=0.0, PositionProfit=10000.0, PreBalance=110000.0)
        self.position = dict(BrokerID='9999', InvestorID='test-account', TradingDay=DAY,
            InstrumentID='rb2701', ExchangeID='SHFE', PosiDirection='2', Position=2, TodayPosition=1,
            YdPosition=1, PositionProfit=1000.0, UseMargin=30000.0, LongFrozen=0, ShortFrozen=0)
        self.order = dict(BrokerID='9999', InvestorID='test-account', TradingDay=DAY,
            InstrumentID='rb2701', ExchangeID='SHFE', Direction='0', CombOffsetFlag='0', LimitPrice=4000,
            VolumeTotalOriginal=2, VolumeTraded=1, OrderStatus='1', FrontID=11, SessionID=22,
            OrderRef='33', OrderSysID='SYS-1', InsertDate='20261030', InsertTime='21:00:00')
        self.trade = dict(BrokerID='9999', InvestorID='test-account', TradingDay=DAY,
            InstrumentID='rb2701', ExchangeID='SHFE', Direction='0', OffsetFlag='0', Price=4000,
            Volume=1, TradeID='TR-1', OrderSysID='SYS-1', TradeDate='20261030', TradeTime='21:00:00')

    def publish(self, accounts=None, positions=None, orders=None, trades=None, mutate=None, enabled=True):
        raw = dict(account=[self.account] if accounts is None else accounts,
                   positions=[self.position] if positions is None else positions,
                   orders=[] if orders is None else orders, trades=[] if trades is None else trades)
        module = SimpleNamespace(EXCHANGE_CTP2VT={'SHFE':'SHFE'},
            DIRECTION_CTP2VT={'0':'long', '1':'short', '2':'long', '3':'short'},
            OFFSET_CTP2VT={'0':'open','1':'close','3':'closetoday','4':'closeyesterday'},
            STATUS_CTP2VT={'0':'all_traded','1':'part_traded','3':'not_traded','5':'cancelled'})
        normalized_orders, normalized_trades, join = stage174._normalize_query_bundle_rows(
            raw['orders'], raw['trades'], generation_uuid=GENERATION, ctp_gateway_module=module)
        normalized_positions, position_status = stage174._normalize_queried_positions(
            raw['positions'], generation_uuid=GENERATION, broker_trading_day=DAY, ctp_gateway_module=module)
        queries = {}
        callbacks = {}
        for index, name in enumerate(('orders','trades','positions','account','contracts')):
            count = len(raw[name]) if name != 'contracts' else 1
            sent = NOW - timedelta(seconds=20-2*index)
            done = sent + timedelta(seconds=1)
            queries[name] = dict(reqid=101+index, request_sent=True, request_return_code=0,
                request_sent_at=sent.isoformat(), completed_at=done.isoformat(), callback_count=max(count,1),
                data_callback_count=count, last_seen=True, error_rows=0, complete=True,
                connection_generation='connection-1')
            callbacks[name] = [dict(query_generation_uuid=GENERATION, connection_generation='connection-1',
                reqid=101+index, expected_reqid=101+index, reqid_matched=1, last=i==max(count,1)-1,
                has_data=count>0, error_id=0, received_at=done.isoformat()) for i in range(max(count,1))]
        queries['positions'].update(position_status)
        generations = {name:'connection-1' for name in stage174.FULL_READINESS_SNAPSHOT_COMPONENTS}
        summary = dict(generated_at=NOW.isoformat(), query_generation_uuid=GENERATION,
            broker_trading_day=DAY, status='readonly_snapshots_received', connect_requested=True,
            real_order_enabled=False, invocation_id='fixture-invocation', source_commit='a'*40,
            connection_lifecycle=dict(current_connection_generation='connection-1', readiness_generation='connection-1',
                snapshot_connection_generations=generations, query_connection_generations={name:'connection-1' for name in queries}),
            order_api_evidence_window=dict(closed=1, closed_epoch_ns=1),
            broker_query_bundle=dict(schema_version=2, generation_uuid=GENERATION, generated_at=NOW.isoformat(),
                broker_trading_day=DAY, queries=queries, complete=True, trade_order_join_complete=True,
                trade_identity_complete=True, snapshot_connection_generation='connection-1',
                snapshot_connection_generations=generations, full_snapshot_current_generation=True,
                account=dict(account_fingerprint=ACCOUNT, login_account_match=True, response_account_match=True,
                             trading_account_response_match=True)))
        for key in ('send_order_api_called_count','cancel_order_api_called_count','native_mutation_api_called_count',
                    'send_order_api_attempted_count','cancel_order_api_attempted_count','native_mutation_api_attempted_count',
                    'order_api_called_count','order_api_attempted_count'):
            summary[key] = 0
        summary['rows'] = dict(accounts=[dict(balance=999999999)], positions=normalized_positions,
            orders=normalized_orders, trades=normalized_trades, contracts=[], logs=[],
            raw_queried_accounts=raw['account'], raw_queried_positions=raw['positions'],
            raw_queried_orders=raw['orders'], raw_queried_trades=raw['trades'],
            account_query_callbacks=callbacks['account'], position_query_callbacks=callbacks['positions'],
            order_query_callbacks=callbacks['orders'], trade_query_callbacks=callbacks['trades'])
        if mutate: mutate(summary)
        paths = dict(SUMMARY_PATH=self.summary_path, QUERY_BUNDLE_MANIFEST_PATH=self.manifest_path)
        for name in ('ACCOUNT','POSITION','ORDER','TRADE','CONTRACT','LOG','POSITION_QUERY_CALLBACK',
                     'ORDER_QUERY_CALLBACK','TRADE_QUERY_CALLBACK'):
            paths[name+'_PATH'] = self.root/(name.lower()+'.csv')
        argv = ['stage174', '--invocation-id', 'fixture-invocation']
        if enabled:
            argv += ['--weekly19-material-release-id', RELEASE, '--weekly19-execution-profile', PROFILE,
                     '--weekly19-private-capture-dir', str(self.root)]
        with ExitStack() as stack:
            for name, path in paths.items(): stack.enter_context(mock.patch.object(stage174,name,path))
            stack.enter_context(mock.patch.object(stage174,'_run_probe',return_value=summary))
            stack.enter_context(mock.patch.object(stage174,'_source_commit',return_value='a'*40))
            stack.enter_context(mock.patch.object(sys,'argv',argv))
            stack.enter_context(redirect_stdout(io.StringIO()))
            stage174.main()
        return json.loads(self.summary_path.read_text()), json.loads(self.manifest_path.read_text())

    def load(self, **changes):
        args = dict(expected_account_key=ACCOUNT, material_release_id=RELEASE, execution_profile=PROFILE,
                    now=NOW, trusted_source_hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in [SOURCE/'run_ctp_stage174_readonly_probe.py', SOURCE/'qmt_roll_weekly19_broker_evidence.py',
                                     SOURCE/'qmt_roll_official_live_late_retry_fill.py']},
                    require_production_qualification=False)
        args.update(changes)
        return provider.load_broker_snapshot(self.summary_path, self.manifest_path, **args)

    def mutate_capture(self, edit):
        summary = json.loads(self.summary_path.read_text())
        manifest = json.loads(self.manifest_path.read_text())
        ref = manifest['weekly19_capture']
        path = Path(ref['path'])
        payload = json.loads(path.read_text())
        edit(payload)
        data = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
        path.write_bytes(data)
        ref['sha256'] = hashlib.sha256(data).hexdigest()
        summary['broker_query_bundle']['weekly19_capture'] = ref
        self.summary_path.write_text(json.dumps(summary))
        self.manifest_path.write_text(json.dumps(manifest))

    def test_generation_bound_capture_preserves_native_cash_fields_privately(self):
        summary, manifest = self.publish()
        self.assertEqual(summary['broker_query_bundle']['weekly19_capture'], manifest['weekly19_capture'])
        path = Path(manifest['weekly19_capture']['path'])
        self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
        capture = json.loads(path.read_text())
        self.assertEqual(capture['raw_queried_accounts'][0]['Deposit'],0.0)
        self.assertEqual(capture['raw_queried_accounts'][0]['TradingDay'],DAY)
        self.assertFalse(capture['production_qualified'])
        self.assertNotIn('test-account', json.dumps(summary))

    def test_load_converts_same_source_funds_positions_orders_to_public_envelopes(self):
        self.publish(orders=[self.order])
        snapshot = self.load()
        cash = funding.initial_state(ACCOUNT, RELEASE, '2026-10-30')
        read = provider.read_account_snapshot(snapshot['account'], expected_account_key=ACCOUNT, material_release_id=RELEASE, now=NOW)
        self.assertEqual((read['balance_fen'],read['available_fen']),(12000000,9000000))
        self.assertEqual(json.loads(snapshot['positions']['raw_payload'])['positions'],
                         [dict(vt_symbol='rb2701.SHFE', direction='long', volume=2)])
        orders = json.loads(snapshot['orders']['raw_payload'])['orders']
        self.assertEqual(orders[0]['broker_order_id'],'CTP.11_22_33')
        self.assertEqual((orders[0]['volume'],orders[0]['traded']),(2,1))
        self.assertFalse(snapshot['production_qualified'])

    def test_production_default_cannot_be_enabled_by_fixture_qualification_claim(self):
        self.publish()
        self.mutate_capture(lambda c:c.update(production_qualified=True,verified=True))
        with self.assertRaises(provider.BrokerEvidenceError): self.load()
        self.publish()
        with self.assertRaisesRegex(provider.BrokerEvidenceError,'production_capture_qualification_missing'):
            self.load(require_production_qualification=True)

    def test_legacy_snapshot_without_raw_capture_cannot_confirm_cash(self):
        self.publish(enabled=False)
        with self.assertRaisesRegex(provider.BrokerEvidenceError,'capture'):
            self.load()

    def test_missing_or_multiple_accounts_and_foreign_currency_fail_closed(self):
        for accounts in ([],[self.account,self.account],[dict(self.account,CurrencyID='USD')],
                         [dict(self.account,AccountID='other')]):
            with self.subTest(accounts=accounts):
                self.publish(accounts=accounts)
                with self.assertRaises(provider.BrokerEvidenceError): self.load()

    def test_missing_cash_fields_and_subcent_or_nonfinite_native_money_rejected(self):
        for field in ('Deposit','Withdraw','TradingDay','Available'):
            raw = dict(self.account); del raw[field]
            with self.subTest(field=field):
                self.publish(accounts=[raw])
                with self.assertRaises(provider.BrokerEvidenceError): self.load()
        for value in (True, 'NaN', 120000.001, 'Infinity'):
            with self.subTest(value=value):
                self.publish(accounts=[dict(self.account,Deposit=value)])
                with self.assertRaises(provider.BrokerEvidenceError): self.load()

    def test_raw_account_callback_requires_matched_reqid_connection_and_error_free_last(self):
        for key,value in (('reqid',999),('connection_generation','stale'),('last',False),('error_id',1)):
            self.publish()
            self.mutate_capture(lambda c:c['callbacks']['account'][0].update({key:value}))
            with self.subTest(key=key), self.assertRaises(provider.BrokerEvidenceError): self.load()

    def test_profile_release_account_source_hash_and_invocation_binding_are_mandatory(self):
        self.publish()
        for changes in (dict(material_release_id='other'),dict(execution_profile='c9-15w'),
                        dict(expected_account_key='b'*64),dict(trusted_source_hashes={})):
            with self.subTest(changes=changes), self.assertRaises(provider.BrokerEvidenceError): self.load(**changes)
        for key,value in (('invocation_id','other'),('source_commit','b'*40)):
            self.publish()
            self.mutate_capture(lambda c:c['runner_provenance'].update({key:value}))
            with self.subTest(key=key), self.assertRaises(provider.BrokerEvidenceError): self.load()

    def test_stale_future_and_naive_snapshot_fail_closed(self):
        self.publish()
        for now in (NOW+timedelta(seconds=301),NOW-timedelta(seconds=1),NOW.replace(tzinfo=None)):
            with self.subTest(now=now), self.assertRaises(provider.BrokerEvidenceError): self.load(now=now)

    def test_order_mutation_attempt_or_unclosed_firewall_window_blocks_capture(self):
        for change in (dict(send_order_api_called_count=1),dict(native_mutation_api_attempted_count=1),
                       dict(order_api_evidence_window=dict(closed=0))):
            self.publish(mutate=lambda s:s.update(change))
            with self.subTest(change=change), self.assertRaises(provider.BrokerEvidenceError): self.load()

    def test_artifact_tamper_and_symlink_are_rejected(self):
        _,manifest = self.publish()
        path = Path(manifest['weekly19_capture']['path'])
        path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(provider.BrokerEvidenceError): self.load()
        self.publish()
        path = Path(json.loads(self.manifest_path.read_text())['weekly19_capture']['path'])
        actual = self.root/'actual'
        path.rename(actual); path.symlink_to(actual)
        with self.assertRaises(provider.BrokerEvidenceError): self.load()

    def test_position_split_rows_aggregate_without_double_counting_yd_position(self):
        one = dict(self.position,Position=1,TodayPosition=1,YdPosition=0)
        two = dict(self.position,Position=2,TodayPosition=0,YdPosition=2)
        self.publish(positions=[one,two])
        rows = json.loads(self.load()['positions']['raw_payload'])['positions']
        self.assertEqual(rows,[dict(vt_symbol='rb2701.SHFE',direction='long',volume=3)])

    def test_fill_uses_native_stable_trade_id_and_unique_ledger_intent_not_caller_quantity(self):
        self.publish(orders=[self.order],trades=[self.trade])
        ledger = [dict(account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE,
            broker_order_id='CTP.11_22_33',intent_id='intent-1',signal_order_id='W19.1',
            signal_identity=dict(intent_id='intent-1',signal_order_id='W19.1'),vt_symbol='rb2701.SHFE',
            direction='long',offset='open',completed_volume=999999)]
        fills = provider.load_broker_fills(self.summary_path,self.manifest_path,ledger,
            **self._load_kwargs())
        raw = json.loads(fills[0]['raw_payload'])
        self.assertEqual(raw['volume'],1)
        self.assertEqual(raw['intent_id'],'intent-1')
        self.assertEqual(raw['trade_id'],'ctp:9999:test-account:SHFE:20261030:SYS-1:TR-1')
        self.assertEqual(raw['source_callback'],'onRspQryTrade')
        self.assertEqual(raw['trade_datetime'],raw['execution_datetime'])
        self.assertEqual(raw['trading_day'],'2026-11-02')
        self.assertFalse(raw['production_qualified'])
        with self.assertRaises(provider.BrokerEvidenceError):
            provider.load_broker_fills(self.summary_path,self.manifest_path,ledger+ledger,**self._load_kwargs())

    def _load_kwargs(self):
        return dict(expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE,now=NOW,
            trusted_source_hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
                for path in [SOURCE/'run_ctp_stage174_readonly_probe.py', SOURCE/'qmt_roll_weekly19_broker_evidence.py',
                             SOURCE/'qmt_roll_official_live_late_retry_fill.py']},require_production_qualification=False)

    def test_unknown_trade_or_unmatched_ledger_identity_never_becomes_an_actual_fill(self):
        self.publish(orders=[self.order],trades=[self.trade])
        for ledger in ([],[dict(broker_order_id='CTP.11_22_33',intent_id='fake')]):
            with self.subTest(ledger=ledger),self.assertRaises(provider.BrokerEvidenceError):
                provider.load_broker_fills(self.summary_path,self.manifest_path,ledger,**self._load_kwargs())

    def test_account_report_reader_exposes_source_funds_margin_and_unknown_pnl_explicitly(self):
        self.publish()
        raw = self.load()['account']
        result = provider.read_account_snapshot(raw,expected_account_key=ACCOUNT,material_release_id=RELEASE,now=NOW)
        self.assertEqual((result['equity_fen'],result['available_fen'],result['unrealized_pnl_fen'],result['margin_fen']),
                         (12000000,9000000,1000000,3000000))
        self.assertEqual((result['currency'],result['trading_day']),('CNY','2026-11-02'))
        self.assertFalse(result['production_qualified'])
        account = dict(self.account); del account['PositionProfit']
        self.publish(accounts=[account])
        result = provider.read_account_snapshot(self.load()['account'],expected_account_key=ACCOUNT,material_release_id=RELEASE,now=NOW)
        self.assertIsNone(result['unrealized_pnl_fen'])

    def test_account_report_reader_rejects_query_error_or_unfinished_query(self):
        self.publish()
        original = self.load()['account']
        for key,value in (('query_error_rows',1),('query_last_seen',False)):
            raw = json.loads(original['raw_payload']); raw[key]=value
            payload=json.dumps(raw,sort_keys=True,separators=(',',':'))
            envelope=dict(raw_payload=payload,raw_sha256=hashlib.sha256(payload.encode()).hexdigest())
            with self.subTest(key=key),self.assertRaises(provider.BrokerEvidenceError):
                provider.read_account_snapshot(envelope,expected_account_key=ACCOUNT,material_release_id=RELEASE,now=NOW)

    def transfer_fixture(self):
        self.publish()
        snapshot=self.load()
        cash=funding.initial_state(ACCOUNT,RELEASE,'2026-10-30')
        recommendation=funding.recommend_topup(cash,snapshot['account'],'2026-10-30',['native-1'],'f'*64,NOW)
        state=recommendation['state']; rid=recommendation['recommendation']['request_id']
        class FakeNative:
            def reqQryTransferSerial(self,payload,reqid):
                self.request=(payload,reqid)
                return 0
        native=FakeNative()
        collector=provider.TransferSerialCollector(snapshot['account'],connection_generation='connection-1')
        collector.begin(native,query_reqid=201,now=NOW,current_connection_generation='connection-1')
        serial=dict(BrokerID='9999',AccountID='test-account',InvestorID='test-account',CurrencyID='CNY',
            TradingDay=DAY,TradeDate='20261030',TradeTime='21:00:01',TradeCode='202001',BankID='001',
            PlateSerial=901,BankSerial='BANK-REF-1',FutureSerial=902,TradeAmount=30000.0,CustFee=0.0,
            BrokerFee=0.0,AvailabilityFlag='1',ErrorID=0)
        collector.on_callback(serial,dict(ErrorID=0),201,True,connection_generation='connection-1',
                              observed_at=NOW+timedelta(seconds=2))
        return collector,state,rid,serial,native

    def test_readonly_transfer_serial_collector_uses_only_native_query_and_keeps_source_unqualified(self):
        collector,state,rid,serial,native=self.transfer_fixture()
        self.assertEqual(native.request,(dict(BrokerID='9999',AccountID='test-account',BankID='',CurrencyID='CNY'),201))
        evidence=collector.export_capture(now=NOW+timedelta(seconds=3))
        raw=json.loads(evidence['raw_payload'])
        self.assertTrue(raw['query_complete'])
        self.assertFalse(raw['production_qualified'])
        parsed=provider.load_bank_cashflow_receipt(evidence,state=state,request_id=rid,bank_serial='BANK-REF-1',
            now=NOW+timedelta(seconds=3),require_production_qualification=False)
        receipt=json.loads(parsed['raw_payload'])
        self.assertEqual((receipt['Amount'],receipt['request_id']),('30000.00',rid))
        self.assertEqual(receipt['source_callback'],'onRspQryTransferSerial')
        self.assertFalse(receipt['production_qualified'])
        with self.assertRaisesRegex(provider.BrokerEvidenceError,'accepted_cashflow_source_missing'):
            provider.load_bank_cashflow_receipt(evidence,state=state,request_id=rid,bank_serial='BANK-REF-1',
                                               now=NOW+timedelta(seconds=3))

    def test_serial_wrong_reqid_connection_errors_repeal_and_withdraw_cannot_confirm(self):
        collector,state,rid,serial,native=self.transfer_fixture()
        for change in (dict(AvailabilityFlag='2'),dict(TradeCode='202002'),dict(ErrorID=1),dict(CustFee=1.0)):
            evidence=json.loads(collector.export_capture(now=NOW+timedelta(seconds=3))['raw_payload'])
            evidence['rows'][0].update(change)
            payload=json.dumps(evidence,sort_keys=True,separators=(',',':'))
            envelope=dict(raw_payload=payload,raw_sha256=hashlib.sha256(payload.encode()).hexdigest())
            with self.subTest(change=change),self.assertRaises(provider.BrokerEvidenceError):
                provider.load_bank_cashflow_receipt(envelope,state=state,request_id=rid,bank_serial='BANK-REF-1',
                    now=NOW+timedelta(seconds=3),require_production_qualification=False)
        collector.on_callback(serial,dict(ErrorID=0),201,True,connection_generation='old',observed_at=NOW+timedelta(seconds=4))
        with self.assertRaises(provider.BrokerEvidenceError): collector.export_capture(now=NOW+timedelta(seconds=4))

    def test_native_trade_order_mapping_does_not_trust_rehashed_normalized_order_id(self):
        self.publish(orders=[self.order],trades=[self.trade])
        self.mutate_capture(lambda c:c['raw_queried_orders'][0].update(OrderRef='other'))
        ledger=[dict(account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE,
            broker_order_id='CTP.11_22_33',intent_id='intent-1',signal_order_id='W19.1',
            signal_identity=dict(intent_id='intent-1',signal_order_id='W19.1'),vt_symbol='rb2701.SHFE',direction='long',offset='open')]
        with self.assertRaises(provider.BrokerEvidenceError):
            provider.load_broker_fills(self.summary_path,self.manifest_path,ledger,**self._load_kwargs())

    def test_public_account_time_is_native_callback_completion_not_later_publish_time(self):
        summary,_=self.publish()
        account=json.loads(self.load()['account']['raw_payload'])
        self.assertEqual(account['observed_at'],summary['broker_query_bundle']['queries']['account']['completed_at'])

    def test_native_trade_from_other_nominal_day_cannot_be_relabelled_current(self):
        self.publish(orders=[self.order],trades=[dict(self.trade,TradingDay='20261030')])
        ledger=[dict(account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE,
            broker_order_id='CTP.11_22_33',intent_id='intent-1',signal_order_id='W19.1',
            signal_identity=dict(intent_id='intent-1',signal_order_id='W19.1'),vt_symbol='rb2701.SHFE',direction='long',offset='open')]
        with self.assertRaises(provider.BrokerEvidenceError):
            provider.load_broker_fills(self.summary_path,self.manifest_path,ledger,**self._load_kwargs())

    def test_transfer_callback_context_restores_original_method_and_persists_private_raw_bytes(self):
        self.publish()
        snapshot=self.load()
        class FakeNative:
            def reqQryTransferSerial(self,payload,reqid):
                self.onRspQryTransferSerial({},dict(ErrorID=0),reqid,True)
                return 0
            def onRspQryTransferSerial(self,data,error,reqid,last):
                self.old_callback_seen=True
        native=FakeNative(); original=FakeNative.onRspQryTransferSerial
        collector=provider.TransferSerialCollector(snapshot['account'],connection_generation='connection-1')
        with provider.instrument_transfer_serial_callback(native,collector,
            connection_generation=lambda:'connection-1',clock=lambda:NOW+timedelta(seconds=1)):
            collector.begin(native,query_reqid=201,now=NOW,current_connection_generation='connection-1')
        self.assertIs(FakeNative.onRspQryTransferSerial,original)
        self.assertFalse(hasattr(native,'old_callback_seen'))
        reference=provider.persist_transfer_serial_capture(self.root/'serial.json',collector,now=NOW+timedelta(seconds=2))
        self.assertEqual(stat.S_IMODE((self.root/'serial.json').stat().st_mode),0o600)
        self.assertEqual(hashlib.sha256((self.root/'serial.json').read_bytes()).hexdigest(),reference['sha256'])
        self.assertFalse(reference['production_qualified'])

    def test_bank_and_day_close_are_explicitly_unavailable_without_accepted_parser(self):
        for method in (provider.load_bank_cashflow_receipt,provider.load_cashflow_day_close):
            with self.assertRaisesRegex(provider.BrokerEvidenceError,'accepted_cashflow_source_missing'):
                method(dict(verified=True,source_kind='bank',cashflows_complete=True))


if __name__=='__main__': unittest.main()
