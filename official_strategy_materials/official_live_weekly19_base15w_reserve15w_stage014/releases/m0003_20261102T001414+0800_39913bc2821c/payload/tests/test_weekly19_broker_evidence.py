"""Offline capture fixtures. None is a production/broker-origin qualification."""
import copy
from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timedelta
import hashlib
import hmac
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
                        for path in [ROOT/name for name in provider.CAPTURE_SOURCE_FILES]},
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
                for path in [ROOT/name for name in provider.CAPTURE_SOURCE_FILES]},require_production_qualification=False)

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

    def test_v6_capture_and_loader_pin_all_six_direct_semantic_sources(self):
        _,manifest=self.publish()
        capture=json.loads(Path(manifest['weekly19_capture']['path']).read_text())
        expected={'examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py',
                  'examples/portfolio_backtesting/qmt_roll_weekly19_broker_evidence.py',
                  'examples/portfolio_backtesting/qmt_roll_official_live_late_retry_fill.py',
                  'examples/portfolio_backtesting/qmt_roll_weekly19_funding.py',
                  'examples/portfolio_backtesting/qmt_roll_official_live_broker_account_snapshot.py',
                  'examples/portfolio_backtesting/qmt_roll_official_live_execution_ledger.py'}
        self.assertEqual(set(capture['runner_provenance']['source_hashes']),expected)
        self.assertEqual(set(provider.CAPTURE_SOURCE_FILES),expected)
        for name in expected:
            self.assertEqual(capture['runner_provenance']['source_hashes'][name],
                             hashlib.sha256((ROOT/name).read_bytes()).hexdigest())

    def test_v2_missing_or_wrong_funding_and_account_context_pins_fail_closed(self):
        self.publish()
        names=['examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py',
               'examples/portfolio_backtesting/qmt_roll_weekly19_broker_evidence.py',
               'examples/portfolio_backtesting/qmt_roll_official_live_late_retry_fill.py',
               'examples/portfolio_backtesting/qmt_roll_weekly19_funding.py',
               'examples/portfolio_backtesting/qmt_roll_official_live_broker_account_snapshot.py',
               'examples/portfolio_backtesting/qmt_roll_official_live_execution_ledger.py']
        complete={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
        for dependency in names[-3:]:
            missing=dict(complete); del missing[dependency]
            wrong=dict(complete); wrong[dependency]='0'*64
            for pins in (missing,wrong):
                with self.subTest(dependency=dependency,pins=pins),self.assertRaises(provider.BrokerEvidenceError):
                    self.load(trusted_source_hashes=pins)

    def test_v2_declared_extra_pin_must_match_and_unsafe_source_paths_are_rejected(self):
        self.publish()
        pins=self._load_kwargs()['trusted_source_hashes']
        extra='examples/portfolio_backtesting/qmt_roll_weekly19_funding_store.py'
        self.assertFalse(self.load(trusted_source_hashes=dict(pins,**{extra:hashlib.sha256((ROOT/extra).read_bytes()).hexdigest()}))['production_qualified'])
        for name,digest in ((extra,'0'*64),('../outside.py','0'*64),('/private/tmp/outside.py','0'*64),
            ('examples/portfolio_backtesting/ctp_live.local.env','0'*64),('.git/config','0'*64),
            ('examples//portfolio_backtesting/qmt_roll_weekly19_funding.py','0'*64)):
            with self.subTest(name=name),self.assertRaises(provider.BrokerEvidenceError):
                self.load(trusted_source_hashes=dict(pins,**{name:digest}))

    def test_v2_changed_or_symlink_direct_dependency_is_rejected_without_mutating_locked_sources(self):
        names=['examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py',
               'examples/portfolio_backtesting/qmt_roll_weekly19_broker_evidence.py',
               'examples/portfolio_backtesting/qmt_roll_official_live_late_retry_fill.py',
               'examples/portfolio_backtesting/qmt_roll_weekly19_funding.py',
               'examples/portfolio_backtesting/qmt_roll_official_live_broker_account_snapshot.py',
               'examples/portfolio_backtesting/qmt_roll_official_live_execution_ledger.py']
        source_copy=self.root/'source-copy'
        for name in names:
            target=source_copy/name; target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((ROOT/name).read_bytes())
        dependency=names[-2]; target=source_copy/dependency
        pins={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
        with mock.patch.object(provider,'ROOT',source_copy):
            self.publish()
            target.write_bytes(target.read_bytes()+b'\n# simulated immutable-source drift\n')
            with self.assertRaises(provider.BrokerEvidenceError): self.load(trusted_source_hashes=pins)
            target.unlink(); target.symlink_to(ROOT/dependency)
            with self.assertRaises(provider.BrokerEvidenceError): self.load(trusted_source_hashes=pins)

    def test_v2_unknown_native_trade_enum_rejects_even_matching_none_ledger(self):
        for field,ledger_field in (('Direction','direction'),('OffsetFlag','offset')):
            native=dict(self.trade); native[field]='9'
            self.publish(orders=[self.order],trades=[native])
            ledger=dict(account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE,
                broker_order_id='CTP.11_22_33',intent_id='intent-1',signal_order_id='W19.1',
                signal_identity=dict(intent_id='intent-1',signal_order_id='W19.1'),vt_symbol='rb2701.SHFE',direction='long',offset='open')
            ledger[ledger_field]=None
            with self.subTest(field=field),self.assertRaises(provider.BrokerEvidenceError):
                provider.load_broker_fills(self.summary_path,self.manifest_path,[ledger],**self._load_kwargs())

    def test_v2_shfe_close_today_yesterday_and_generic_close_keep_broker_offset_proof(self):
        for flag,broker_offset in (('1','close'),('3','closetoday'),('4','closeyesterday')):
            self.publish(orders=[dict(self.order,Direction='1',CombOffsetFlag=flag)],
                         trades=[dict(self.trade,Direction='1',OffsetFlag=flag)])
            ledger=dict(account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE,
                broker_order_id='CTP.11_22_33',intent_id='intent-1',signal_order_id='W19.1',
                signal_identity=dict(intent_id='intent-1',signal_order_id='W19.1'),vt_symbol='rb2701.SHFE',direction='short',offset='close')
            for explicit in (False,True):
                row=dict(ledger)
                if explicit: row['broker_offset']=broker_offset
                fills=provider.load_broker_fills(self.summary_path,self.manifest_path,[row],**self._load_kwargs())
                native=json.loads(fills[0]['raw_payload'])
                with self.subTest(flag=flag,explicit=explicit):
                    self.assertEqual(native['offset'],'close')
                    self.assertEqual(native['business_offset'],'close')
                    self.assertEqual(native['broker_offset'],broker_offset)
                    self.assertEqual(native['native_offset_flag'],flag)
                    self.assertEqual(native['volume'],1)
            public_order=json.loads(self.load()['orders']['raw_payload'])['orders'][0]
            self.assertEqual((public_order['offset'],public_order['broker_offset']),('close',broker_offset))

    def test_v2_raw_order_offset_and_optional_ledger_broker_offset_must_match_native_trade(self):
        ledger=dict(account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE,
            broker_order_id='CTP.11_22_33',intent_id='intent-1',signal_order_id='W19.1',
            signal_identity=dict(intent_id='intent-1',signal_order_id='W19.1'),vt_symbol='rb2701.SHFE',direction='short',offset='close')
        cases=[('1','3',{}),('3','4',{}),('3','3',dict(broker_offset='closeyesterday')),
               ('0','0',{}),('3','3',dict(broker_offset='open'))]
        for orderflag,tradeflag,changes in cases:
            self.publish(orders=[dict(self.order,Direction='1',CombOffsetFlag=orderflag)],
                         trades=[dict(self.trade,Direction='1',OffsetFlag=tradeflag)])
            with self.subTest(orderflag=orderflag,tradeflag=tradeflag,changes=changes),self.assertRaises(provider.BrokerEvidenceError):
                provider.load_broker_fills(self.summary_path,self.manifest_path,[dict(ledger,**changes)],**self._load_kwargs())

    def test_v2_bank_parser_rechecks_native_query_freshness_and_occurrence_before_callback(self):
        collector,state,rid,serial,native=self.transfer_fixture()
        raw=json.loads(collector.export_capture(now=NOW+timedelta(seconds=3))['raw_payload'])
        stale=copy.deepcopy(raw)
        stale['request_sent_at']=(NOW-timedelta(days=30)).isoformat()
        for callback in stale['callbacks']: callback['received_at']=(NOW-timedelta(days=30)+timedelta(seconds=1)).isoformat()
        late_occurrence=copy.deepcopy(raw)
        late_occurrence['rows'][0]['TradeTime']='21:00:03'
        for changed in (stale,late_occurrence):
            payload=json.dumps(changed,sort_keys=True,separators=(',',':'))
            envelope=dict(raw_payload=payload,raw_sha256=hashlib.sha256(payload.encode()).hexdigest())
            with self.subTest(changed=changed),self.assertRaises(provider.BrokerEvidenceError):
                provider.load_bank_cashflow_receipt(envelope,state=state,request_id=rid,bank_serial='BANK-REF-1',
                    now=NOW+timedelta(seconds=4),require_production_qualification=False)

    def order_ledger(self,**changes):
        identity=dict(intent_id='intent-1',signal_order_id='W19.1',signal_datetime='2026-10-30T00:00:00',trading_date='2026-11-02')
        row=dict(account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE,
            broker_order_id='CTP.11_22_33',intent_id='intent-1',signal_order_id='W19.1',signal_identity=identity,
            vt_symbol='rb2701.SHFE',direction='long',offset='open',planned_volume=2)
        row.update(changes)
        return row

    def test_v3_query_order_terminal_bridge_uses_native_cumulative_quantity_and_original_intent(self):
        self.publish(orders=[dict(self.order,OrderStatus='5')],trades=[self.trade])
        ledger=self.order_ledger(completed_volume=999)
        updates=provider.load_broker_order_updates(self.summary_path,self.manifest_path,[ledger],**self._load_kwargs())
        raw=json.loads(updates[0]['raw_payload'])
        self.assertEqual((raw['status'],raw['volume'],raw['traded']),('cancelled',2,1))
        self.assertEqual(raw['signal_identity'],ledger['signal_identity'])
        self.assertEqual(raw['source_callback'],'onRspQryOrder')
        self.assertEqual(raw['order_sys_id'],'SYS-1')
        self.assertFalse(raw['production_qualified'])

    def test_v3_query_order_partial_filled_rejected_and_unknown_status_are_decidable(self):
        for changes,status,traded in ((dict(OrderStatus='3',VolumeTraded=0),'working',0),
            (dict(OrderStatus='1'),'partially_filled',1),(dict(OrderStatus='0',VolumeTraded=2),'filled',2),
            (dict(OrderStatus='a',OrderSubmitStatus='4',VolumeTraded=0),'rejected',0)):
            self.publish(orders=[dict(self.order,**changes)])
            raw=json.loads(provider.load_broker_order_updates(self.summary_path,self.manifest_path,
                [self.order_ledger()],**self._load_kwargs())[0]['raw_payload'])
            self.assertEqual((raw['status'],raw['traded']),(status,traded))
        self.publish(orders=[dict(self.order,OrderStatus='9')])
        with self.assertRaises(provider.BrokerEvidenceError):
            provider.load_broker_order_updates(self.summary_path,self.manifest_path,[self.order_ledger()],**self._load_kwargs())

    def test_v3_query_order_symbol_volume_ambiguous_ledger_and_shfe_offset_mismatch_rejected(self):
        self.publish(orders=[self.order])
        for ledger in ([self.order_ledger(vt_symbol='rb2705.SHFE')],[self.order_ledger(planned_volume=3)],
                       [self.order_ledger(),self.order_ledger()]):
            with self.subTest(ledger=ledger),self.assertRaises(provider.BrokerEvidenceError):
                provider.load_broker_order_updates(self.summary_path,self.manifest_path,ledger,**self._load_kwargs())
        self.publish(orders=[dict(self.order,CombOffsetFlag='3',Direction='1')])
        for offset,broker_offset in (('close','closetoday'),('close','closeyesterday'),('open','closetoday')):
            ledger=self.order_ledger(direction='short',offset=offset,broker_offset=broker_offset)
            if (offset,broker_offset)==('close','closetoday'):
                raw=json.loads(provider.load_broker_order_updates(self.summary_path,self.manifest_path,[ledger],**self._load_kwargs())[0]['raw_payload'])
                self.assertEqual((raw['offset'],raw['broker_offset']),('close','closetoday'))
            else:
                with self.assertRaises(provider.BrokerEvidenceError):
                    provider.load_broker_order_updates(self.summary_path,self.manifest_path,[ledger],**self._load_kwargs())

    def test_v3_order_semantic_id_is_stable_across_restart_query_generation(self):
        self.publish(orders=[self.order])
        first=provider.load_broker_order_updates(self.summary_path,self.manifest_path,[self.order_ledger()],**self._load_kwargs())[0]
        def new_generation(summary):
            changed=json.loads(json.dumps(summary).replace(GENERATION,'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'))
            summary.clear();summary.update(changed)
        self.publish(orders=[self.order],mutate=new_generation)
        second=provider.load_broker_order_updates(self.summary_path,self.manifest_path,[self.order_ledger()],**self._load_kwargs())[0]
        one=json.loads(first['raw_payload']);two=json.loads(second['raw_payload'])
        self.assertEqual(one['event_id'],two['event_id'])
        self.assertEqual(one['event_semantic_sha256'],two['event_semantic_sha256'])
        self.assertNotEqual(first['raw_sha256'],second['raw_sha256'])
        semantic={key:one[key] for key in ('account_key','material_release_id','intent_id','signal_order_id','signal_identity',
            'broker_order_id','vt_symbol','direction','offset','broker_offset','volume','traded','status')}
        payload=json.dumps(semantic,sort_keys=True,separators=(',',':'),ensure_ascii=False)
        self.assertEqual(one['event_semantic_sha256'],hashlib.sha256(payload.encode()).hexdigest())

    def native_capture(self,orders=None,trades=None,ledger=None,callback_generation='connection-1'):
        self.publish()
        account=self.load()['account'];ledger=[self.order_ledger()] if ledger is None else ledger
        collector=provider.NativeBrokerCallbackCollector(account,connection_generation='connection-1',
            service_generation='service-1',execution_ledger_rows=ledger)
        for order in ([self.order] if orders is None else orders):
            collector.record('onRtnOrder',order,connection_generation=callback_generation,observed_at=NOW+timedelta(seconds=1))
        for trade in ([self.trade] if trades is None else trades):
            collector.record('onRtnTrade',trade,connection_generation=callback_generation,observed_at=NOW+timedelta(seconds=2))
        reference=provider.persist_native_broker_capture(self.root/('native-'+os.urandom(4).hex()+'.json'),collector,
            now=NOW+timedelta(seconds=3))
        return reference,ledger,collector

    def test_v3_true_native_push_builder_preserves_callback_shape_and_fills_before_orders(self):
        reference,ledger,collector=self.native_capture()
        result=provider.load_native_broker_events(reference,ledger,**dict(self._load_kwargs(),now=NOW+timedelta(seconds=4)))
        self.assertFalse(result['production_qualified'])
        self.assertEqual(result['apply_order'],['fills','orders'])
        fill=json.loads(result['fills'][0]['raw_payload']);order=json.loads(result['orders'][0]['raw_payload'])
        self.assertEqual(fill['source_callback'],'onRtnTrade')
        self.assertEqual(order['source_callback'],'onRtnOrder')
        self.assertEqual((order['status'],fill['volume'],order['traded']),('partially_filled',1,1))
        self.assertEqual(order['connection_generation'],'connection-1')
        self.assertEqual(order['service_generation'],'service-1')
        self.assertEqual(stat.S_IMODE(Path(reference['path']).stat().st_mode),0o600)
        with self.assertRaisesRegex(provider.BrokerEvidenceError,'production_capture_qualification_missing'):
            provider.load_native_broker_events(reference,ledger,**dict(self._load_kwargs(),now=NOW+timedelta(seconds=4),require_production_qualification=True))

    def test_v3_native_collector_rejects_vnpy_object_and_normalized_rows_as_raw_ctp(self):
        self.publish();account=self.load()['account']
        collector=provider.NativeBrokerCallbackCollector(account,connection_generation='connection-1',
            service_generation='service-1',execution_ledger_rows=[self.order_ledger()])
        for payload in (SimpleNamespace(orderid='11_22_33'),dict(vt_orderid='CTP.11_22_33',volume=2,status='cancelled')):
            with self.subTest(payload=payload),self.assertRaises(provider.BrokerEvidenceError):
                collector.record('onRtnOrder',payload,connection_generation='connection-1',observed_at=NOW)
        with self.assertRaises(provider.BrokerEvidenceError):
            collector.record('onRtnOrder',self.order,connection_generation='old',observed_at=NOW)

    def test_v3_native_push_wrong_symbol_missing_order_proof_and_reused_binding_rejected(self):
        for orders,trades,ledger in (([dict(self.order,InstrumentID='rb2705')],[self.trade],[self.order_ledger()]),
            ([],[self.trade],[self.order_ledger()]),([self.order],[self.trade],[self.order_ledger(),self.order_ledger()])):
            reference,_,_=self.native_capture(orders=orders,trades=trades,ledger=ledger)
            with self.subTest(orders=orders),self.assertRaises(provider.BrokerEvidenceError):
                provider.load_native_broker_events(reference,ledger,**dict(self._load_kwargs(),now=NOW+timedelta(seconds=4)))

    def test_v3_native_push_partial_cancel_duplicate_and_restart_stable_semantics(self):
        reference,ledger,_=self.native_capture(orders=[self.order,dict(self.order,OrderStatus='5'),dict(self.order,OrderStatus='5')])
        result=provider.load_native_broker_events(reference,ledger,**dict(self._load_kwargs(),now=NOW+timedelta(seconds=4)))
        self.assertEqual(len(result['orders']),2)
        again=provider.load_native_broker_events(reference,ledger,**dict(self._load_kwargs(),now=NOW+timedelta(seconds=4)))
        self.assertEqual(result,again)
        self.assertEqual([json.loads(e['raw_payload'])['status'] for e in result['orders']],['partially_filled','cancelled'])
        reference2,_,_=self.native_capture(orders=[dict(self.order,OrderStatus='5')])
        resumed=provider.load_native_broker_events(reference2,ledger,**dict(self._load_kwargs(),now=NOW+timedelta(seconds=4)))
        self.assertEqual(json.loads(result['orders'][-1]['raw_payload'])['event_id'],json.loads(resumed['orders'][0]['raw_payload'])['event_id'])

    def test_v3_native_callback_instrumentation_records_before_vnpy_normalization_and_restores(self):
        self.publish();account=self.load()['account'];seen=[]
        class FakeNative:
            def onRtnOrder(self,data): seen.append(('normalized-order',len(collector.events)))
            def onRtnTrade(self,data): seen.append(('normalized-trade',len(collector.events)))
        native=FakeNative();original=FakeNative.onRtnOrder
        collector=provider.NativeBrokerCallbackCollector(account,connection_generation='connection-1',
            service_generation='service-1',execution_ledger_rows=[self.order_ledger()])
        with provider.instrument_native_broker_callbacks(native,collector,connection_generation=lambda:'connection-1',clock=lambda:NOW):
            native.onRtnOrder(self.order);native.onRtnTrade(self.trade)
        self.assertIs(FakeNative.onRtnOrder,original)
        self.assertEqual(seen,[('normalized-order',1),('normalized-trade',2)])
        self.assertEqual(collector.events[0]['native'],self.order)
        self.assertEqual(collector.events[1]['native'],self.trade)

    def test_v3_spool_delivery_intent_and_original_business_id_remain_distinct(self):
        self.publish(orders=[self.order],trades=[self.trade])
        ledger=self.order_ledger(intent_id='W19EXEC-delivery-1',planned_intent_id='intent-1')
        order=json.loads(provider.load_broker_order_updates(self.summary_path,self.manifest_path,[ledger],**self._load_kwargs())[0]['raw_payload'])
        fill=json.loads(provider.load_broker_fills(self.summary_path,self.manifest_path,[ledger],**self._load_kwargs())[0]['raw_payload'])
        for row in (order,fill):
            self.assertEqual(row['intent_id'],'intent-1')
            self.assertEqual(row['delivery_intent_id'],'W19EXEC-delivery-1')
            self.assertEqual(row['signal_identity']['intent_id'],'intent-1')
        wrong=dict(ledger,planned_intent_id='different-plan')
        with self.assertRaises(provider.BrokerEvidenceError):
            provider.load_broker_order_updates(self.summary_path,self.manifest_path,[wrong],**self._load_kwargs())
        reference,_,_=self.native_capture(ledger=[ledger])
        native=provider.load_native_broker_events(reference,[ledger],**dict(self._load_kwargs(),now=NOW+timedelta(seconds=4)))
        for item in native['fills']+native['orders']:
            raw=json.loads(item['raw_payload'])
            self.assertEqual((raw['intent_id'],raw['delivery_intent_id']),('intent-1','W19EXEC-delivery-1'))

    def test_v4_generic_ledger_fold_collapses_semantic_events_and_preserves_delivery_identity(self):
        base=self.order_ledger(intent_id='W19EXEC-delivery-1',planned_intent_id='intent-1')
        base['account_fingerprint']=base.pop('account_key');base['vt_orderid']=base.pop('broker_order_id')
        base['order_request_volume']=2.0;base.pop('planned_volume')
        base['front_id']=11;base['session_id']=22;base['order_ref']='33'
        rows=[dict(base,event_type=kind,volume=qty,broker_callback_key=str(qty))
              for kind,qty in [('native_order_identity_persisted_before_insert',2),('send_order_returned',2),('filled_or_part_filled',1)]]
        rows.append(dict(base,event_type='reserved',vt_orderid=''))
        bindings=provider.derive_order_intent_bindings(rows,expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE)
        self.assertEqual(len(bindings),1)
        self.assertEqual((bindings[0]['intent_id'],bindings[0]['planned_intent_id'],bindings[0]['order_request_volume']),('W19EXEC-delivery-1','intent-1',2))
        self.publish(orders=[self.order],trades=[self.trade])
        raw=json.loads(provider.load_broker_order_updates(self.summary_path,self.manifest_path,bindings,**self._load_kwargs())[0]['raw_payload'])
        self.assertEqual((raw['intent_id'],raw['delivery_intent_id']),('intent-1','W19EXEC-delivery-1'))
        self.assertEqual(len(provider.load_broker_fills(self.summary_path,self.manifest_path,bindings,**self._load_kwargs())),1)

    def test_v4_generic_ledger_fold_conflicts_are_not_event_deduplication(self):
        base=self.order_ledger()
        for delta in (dict(intent_id='different'),dict(planned_intent_id='different'),dict(vt_symbol='rb2705.SHFE'),
                      dict(direction='short'),dict(offset='close'),dict(planned_volume=3),dict(front_id=99),
                      dict(account_fingerprint='a'*64),dict(signal_identity_json='{}')):
            with self.subTest(delta=delta),self.assertRaises(provider.BrokerEvidenceError):
                provider.derive_order_intent_bindings([base,dict(base,**delta)],expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE)

    def test_v4_shfe_child_cap_preserves_parent_plan_and_ignores_normalized_callback_enums(self):
        base=self.order_ledger(direction='多',offset='平今',planned_direction='long',planned_offset='close',
            planned_volume=2,broker_order_volume=1,order_request_volume=1.0,broker_offset='closetoday',native_offset_flag='3')
        bindings=provider.derive_order_intent_bindings([base,dict(base,event_type='fill',volume=1)],
            expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE)
        self.assertEqual((bindings[0]['planned_volume'],bindings[0]['broker_order_volume']),(2,1))
        self.assertEqual((bindings[0]['direction'],bindings[0]['offset']),('long','close'))
        order=dict(self.order,CombOffsetFlag='3',VolumeTotalOriginal=1,VolumeTraded=1,OrderStatus='0')
        self.publish(orders=[order],trades=[dict(self.trade,OffsetFlag='3')])
        event=json.loads(provider.load_broker_order_updates(self.summary_path,self.manifest_path,bindings,**self._load_kwargs())[0]['raw_payload'])
        self.assertEqual((event['volume'],event['offset'],event['broker_offset']),(1,'close','closetoday'))

    def test_v4_generic_fold_has_no_trade_volume_cap_and_strict_signal_json(self):
        base=self.order_ledger();base.pop('planned_volume');base['volume']=1
        base['signal_identity_json']=json.dumps(base.pop('signal_identity'))
        result=provider.derive_order_intent_bindings([base,dict(base,volume=2)],expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE)
        self.assertNotIn('planned_volume',result[0])
        bad=dict(base,signal_identity_json='{"intent_id":"intent-1","intent_id":"other"}')
        with self.assertRaises(provider.BrokerEvidenceError):
            provider.derive_order_intent_bindings([bad],expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE)

    def batch_ledger(self,both_native=True):
        import qmt_roll_official_live_execution_ledger as ledger
        fingerprint='f'*64
        base=self.order_ledger(intent_id='W19EXEC-delivery',planned_intent_id='intent-1',offset='close')
        base.update(source='weekly19_close',account_fingerprint=base.pop('account_key'),planned_direction='long',planned_offset='close',
            service_generation='service-1',connection_generation='connection-1',spool_lease_owner='service-1',spool_lease_token='lease-1',
            intent_payload_sha256='b'*64,parent_intent_fingerprint=fingerprint,intent_fingerprint=fingerprint,
            trading_date='2026-11-02',target_date='2026-11-02')
        base.pop('broker_order_id')
        children=[dict(child_order_id=fingerprint+':'+str(index+1)+'/2',child_order_index=index,volume=1,broker_offset=offset,
            vt_symbol='rb2701.SHFE',direction='long',trading_date='2026-11-02') for index,offset in enumerate(('closetoday','closeyesterday'))]
        manifest=dict(schema='weekly19.physical-batch-manifest.v1',intent_id=base['intent_id'],planned_intent_id='intent-1',
            signal_identity=base['signal_identity'],intent_payload_sha256=base['intent_payload_sha256'],parent_intent_fingerprint=fingerprint,
            spool_lease_token='lease-1',service_generation='service-1',connection_generation='connection-1',approved_parent_volume=2,
            expected_children=children,expected_children_sha256=funding._hash(children))
        events=[dict(base,weekly19_batch_manifest=manifest,approved_parent_volume=2,expected_children=children,
            expected_children_sha256=funding._hash(children),api_slot_batch_id='',child_order_id=c['child_order_id'],
            child_order_index=c['child_order_index'],child_order_count=2,child_order_volume=1.,child_order_offset='平今' if index==0 else '平昨')
            for index,c in enumerate(children)]
        batchid=funding._hash(dict(target_date='2026-11-02',slot_type='send_order',usage_before=0,base_events=events))[:24]
        quota=ledger._with_record_checksum(dict(events[0],event_type='api_slot_reserved',api_slot_type='send_order',api_slot_reserved=1,
            api_slot_reserved_count=2,api_slot_batch_count=2,api_slot_batch_id=batchid,api_slot_batch_children=events))
        rows=[quota]
        for index,event in enumerate(events[:2 if both_native else 1]):
            native=dict(event,event_type='native_order_identity_persisted_before_insert',api_slot_batch_id=batchid,front_id=11,
                session_id=22,order_ref=str(33+index),vt_orderid='CTP.11_22_'+str(33+index),broker_order_volume=1,
                broker_offset=children[index]['broker_offset'],native_offset_flag=str(3+index),req_order_insert_reqid=501+index,native_api_called=0)
            rows.append(ledger._with_record_checksum(native))
        return rows

    def test_v6_quota_complete_children_reconstruct_before_any_second_native_order(self):
        rows=self.batch_ledger(both_native=False)
        bindings=provider.derive_order_intent_bindings(rows,expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE)
        self.assertEqual(len(bindings),1)
        raw=bindings[0]
        self.assertEqual((raw['execution_batch_id'],raw['api_slot_batch_id']),(rows[0]['api_slot_batch_id'],rows[0]['api_slot_batch_id']))
        self.assertEqual((raw['api_slot_batch_count'],raw['approved_parent_volume'],len(raw['expected_children'])),(2,2,2))
        self.assertEqual(raw['child_order_id'],rows[1]['child_order_id'])
        self.assertNotIn('broker_order_id',raw['expected_children'][1])
        self.assertEqual(raw['execution_batch_proof']['quota_record_checksum'],rows[0]['record_checksum'])
        self.assertEqual(raw['execution_batch_proof']['native_identity_record_checksum'],rows[1]['record_checksum'])

    def test_v6_callback_list_or_missing_partial_quota_never_creates_parent_proof(self):
        rows=self.batch_ledger();native=rows[1]
        for changed in ([native],rows[1:], [dict(native,event_type='filled_or_part_filled')]):
            with self.subTest(kind=[r['event_type'] for r in changed]),self.assertRaises(provider.BrokerEvidenceError):
                provider.derive_order_intent_bindings(changed,expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE)
        bad=copy.deepcopy(rows);bad[0]['api_slot_batch_children'].pop()
        bad[0]['record_checksum']=funding._hash({k:v for k,v in bad[0].items() if k!='record_checksum'})
        with self.assertRaises(provider.BrokerEvidenceError):
            provider.derive_order_intent_bindings(bad,expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE)

    def test_v6_quota_native_checksum_order_identity_manifest_and_children_are_strict(self):
        changes=[(0,'record_checksum','0'*64),(1,'record_checksum',None),(1,'api_slot_batch_id','0'*24),
            (1,'child_order_id','unknown-child'),(1,'broker_order_volume',2),(1,'broker_offset','closeyesterday'),
            (1,'planned_intent_id','wrong'),(1,'connection_generation','wrong'),(1,'native_api_called',1),
            (1,'source','wrong'),(1,'ruleset_version','wrong'),(1,'reservation_record_checksum','f'*64)]
        for index,key,value in changes:
            rows=self.batch_ledger();rows[index][key]=value
            if key!='record_checksum':rows[index]['record_checksum']=funding._hash({k:v for k,v in rows[index].items() if k!='record_checksum'})
            with self.subTest(key=key),self.assertRaises(provider.BrokerEvidenceError):
                provider.derive_order_intent_bindings(rows,expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE)
        rows=self.batch_ledger()
        for bad in ([rows[1],rows[0],rows[2]],[rows[0],rows[0],*rows[1:]],[*rows,dict(event_type='ledger_checksum_error')]):
            with self.subTest(order=[r['event_type'] for r in bad]),self.assertRaises(provider.BrokerEvidenceError):
                provider.derive_order_intent_bindings(bad,expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE)

    def test_v6_query_and_native_envelopes_preserve_full_parent_proof_and_child_native_volume(self):
        rows=self.batch_ledger();bindings=provider.derive_order_intent_bindings(rows,expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE)
        order=dict(self.order,CombOffsetFlag='3',VolumeTotalOriginal=1,VolumeTraded=1,OrderStatus='0')
        trade=dict(self.trade,OffsetFlag='3')
        self.publish(orders=[order],trades=[trade])
        query=provider.load_broker_order_updates(self.summary_path,self.manifest_path,bindings,**self._load_kwargs())
        fills=provider.load_broker_fills(self.summary_path,self.manifest_path,bindings,**self._load_kwargs())
        reference,_,_=self.native_capture(orders=[order],trades=[trade],ledger=bindings)
        native=provider.load_native_broker_events(reference,bindings,**dict(self._load_kwargs(),now=NOW+timedelta(seconds=4)))
        for event in query+fills+native['orders']+native['fills']:
            raw=json.loads(event['raw_payload'])
            self.assertEqual((raw['api_slot_batch_count'],raw['approved_parent_volume'],raw['volume']),(2,2,1))
            self.assertEqual(raw['expected_children_sha256'],funding._hash(raw['expected_children']))
            self.assertEqual(raw['execution_batch_proof']['quota_record_checksum'],rows[0]['record_checksum'])
            if raw['schema']=='weekly19.ctp-order.v1':
                keys=('account_key','material_release_id','intent_id','signal_order_id','signal_identity','broker_order_id','vt_symbol','direction','offset','broker_offset','volume','traded','status')
                self.assertEqual(raw['event_semantic_sha256'],funding._hash({key:raw[key] for key in keys}))

    def test_v6_wrong_callback_child_and_callback_before_native_identity_are_rejected(self):
        import qmt_roll_official_live_execution_ledger as ledger
        rows=self.batch_ledger();callback=dict(rows[1],event_type='filled_or_part_filled',child_order_id=rows[2]['child_order_id'],child_order_index=1,
            broker_offset='closeyesterday',native_offset_flag='4')
        callback=ledger._with_record_checksum(callback)
        for bad in ([*rows,callback],[rows[0],dict(rows[1],event_type='send_order_returned'),*rows[1:]]):
            with self.subTest(events=[r['event_type'] for r in bad]),self.assertRaises(provider.BrokerEvidenceError):
                provider.derive_order_intent_bindings(bad,expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE)

    def test_v6_reader_rejects_symlink_corruption_duplicate_json_key_and_incomplete_tail(self):
        path=self.root/'quota.jsonl';rows=self.batch_ledger()
        valid=''.join(json.dumps(row)+'\n' for row in rows)
        for payload in (valid+'{"x":1,"x":2}\n',valid.rstrip('\n'),valid.replace(rows[0]['record_checksum'],'0'*64),valid+'bad-json\n'):
            path.write_text(payload);path.chmod(0o600)
            with self.subTest(payload=payload[-40:]),self.assertRaises(provider.BrokerEvidenceError):
                provider.load_execution_order_intent_bindings(path,expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE)
        path.unlink();target=self.root/'target.jsonl';target.write_text(valid);target.chmod(0o600);path.symlink_to(target)
        with self.assertRaises(provider.BrokerEvidenceError):
            provider.load_execution_order_intent_bindings(path,expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE)

    def test_v6_actual_931_quota_and_callback_builders_match_provider_private_reader(self):
        import run_qmt_roll_stage931_official_live_ctp_submit_adapter as execution
        from qmt_roll_official_live_execution_ledger import append_execution_ledger_event,read_execution_ledger,reserve_execution_ledger_intent
        path=self.root/'actual-quota.jsonl'
        paths=execution.ExecutorServicePaths.for_spool(spool_path=self.root/'unused-spool.sqlite3',ledger_path=path)
        session=execution._build_stage179_warm_ctp_session(SimpleNamespace(target_date='2026-10-30',execution_profile=PROFILE,connect_wait_seconds=3),
            SimpleNamespace(output_root=self.root),paths,weekly19_context_provider=lambda *a,**kw:None,
            weekly19_event_consumer=lambda *a:None,weekly19_native_capture_factory=lambda **kw:None)
        state=next(cell.cell_contents for cell in session._reserve_api_slot.__closure__ if isinstance(cell.cell_contents,dict) and 'intent_contexts'in cell.cell_contents)
        state['connection_generation']='connection-1'
        row=self.order_ledger(intent_id='W19EXEC-delivery',planned_intent_id='intent-1',offset='close',order_request_volume=2)
        row.pop('broker_order_id');row['account_fingerprint']=row.pop('account_key')
        row.update(source='weekly19_close',trading_date='2026-11-02')
        requests=[execution.OrderRequest(symbol='rb2701',exchange=execution.Exchange.SHFE,direction=execution.Direction.LONG,
            type=execution.OrderType.LIMIT,volume=1,price=4000,offset=offset) for offset in (execution.Offset.CLOSETODAY,execution.Offset.CLOSEYESTERDAY)]
        context=dict(row=row,requests=requests,request=requests[0],fingerprint='f'*64,intent_id='W19EXEC-delivery',target_date='2026-10-30',
            intent_payload_sha256='a'*64,intent_kind='close',service_generation='service-1',connection_generation='connection-1',
            spool_lease_owner='service-1',spool_lease_token='lease-1')
        reservation=reserve_execution_ledger_intent(target_date='2026-10-30',row=row,
            order_request=dict(symbol='rb2701',exchange='SHFE',direction='long',offset='close',volume=2,price=4000),
            close_retry_after_cancel_seconds=30,base_event=dict(row,intent_kind='close',intent_payload_sha256='a'*64,
                spool_lease_owner='service-1',spool_lease_token='lease-1'),path=path)
        self.assertTrue(reservation['reserved'])
        context.update(fingerprint=reservation['intent_fingerprint'],close_submit_attempt_no=reservation['close_submit_attempt_no'],
            close_attempt_lease_token=reservation['close_attempt_lease_token'],reservation_record_checksum=reservation['latest_ledger_event']['record_checksum'])
        state['intent_contexts']['W19EXEC-delivery']=context
        lease=SimpleNamespace(lease_token='lease-1',intent=SimpleNamespace(target_date='2026-10-30',intent_id='W19EXEC-delivery',
            payload_sha256='a'*64,intent_kind='close',vt_symbol='rb2701.SHFE',lease_owner='service-1'))
        batch=session._reserve_api_slot(lease);quota=read_execution_ledger(path)[-1]
        self.assertTrue(batch,quota.get('api_slot_blocker'))
        self.assertEqual(batch,quota['api_slot_batch_id'])
        native=dict(quota['api_slot_batch_children'][0],event_type='native_order_identity_persisted_before_insert',api_slot_batch_id=batch,
            broker_order_volume=1,broker_offset='closetoday',native_offset_flag='3',front_id='11',session_id='22',order_ref='33',
            vt_orderid='CTP.11_22_33',req_order_insert_reqid=501,native_api_called=0)
        append_execution_ledger_event(native,path)
        context.update(child_order_id=native['child_order_id'],child_order_index=0,child_order_count=2)
        callback=execution._stage179_warm_callback_base(context,dict(direction='多',offset='平今',broker_offset='closetoday',native_offset_flag='3'))
        append_execution_ledger_event(dict(callback,event_type='filled_or_part_filled',vt_orderid='CTP.11_22_33',volume=1),path)
        path.chmod(0o600)
        bindings=provider.load_execution_order_intent_bindings(path,expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE)
        self.assertEqual(len(bindings),1)
        self.assertEqual((bindings[0]['planned_volume'],bindings[0]['order_request_volume'],bindings[0]['broker_order_volume']),(2,2,1))
        self.assertEqual(bindings[0]['expected_children_sha256'],quota['expected_children_sha256'])
        self.assertEqual(bindings[0]['api_slot_batch_count'],2)

    def test_v6_private_ledger_reader_grants_typed_origin_only_after_complete_proof(self):
        rows=self.batch_ledger();path=self.root/'execution.jsonl'
        path.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows));path.chmod(0o600)
        bindings=provider.load_execution_order_intent_bindings(path,expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE)
        provider._require_verified_execution_bindings(bindings,True)
        with self.assertRaises(provider.BrokerEvidenceError): provider._require_verified_execution_bindings(list(bindings),True)
        with self.assertRaises(provider.BrokerEvidenceError): bindings.append(dict())
        bindings[0]['approved_parent_volume']=999
        with self.assertRaises(provider.BrokerEvidenceError): provider._require_verified_execution_bindings(bindings,True)
        path.chmod(0o644)
        with self.assertRaises(provider.BrokerEvidenceError):
            provider.load_execution_order_intent_bindings(path,expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE)

    def test_authority_self_declared_qualified_registry_is_not_a_trusted_source(self):
        fake=self.root/'fake-registry.json'
        fake.write_text(json.dumps(dict(schema='weekly19.capture-authority-registry.v1',qualified=True,status='qualified')))
        fake.chmod(0o600)
        reference=dict(path=str(fake),sha256=hashlib.sha256(fake.read_bytes()).hexdigest())
        with self.assertRaises(provider.BrokerEvidenceError):
            provider.load_capture_authority_registry(reference,expected_account_key=ACCOUNT,material_release_id=RELEASE,
                execution_profile=PROFILE,trusted_source_hashes=self._load_kwargs()['trusted_source_hashes'],now=NOW)

    def test_authority_invalid_real_qualification_cannot_create_private_key_or_registry(self):
        evidence=self.root/'qualification.json'
        critical=[dict(path=name,sha256=hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),size_bytes=len((ROOT/name).read_bytes()))
                  for name in provider.CAPTURE_AUTHORITY_SOURCE_FILES]
        evidence.write_text(json.dumps(dict(critical_files=critical)));evidence.chmod(0o600)
        registry=self.root/'authority.json'
        with self.assertRaisesRegex(provider.BrokerEvidenceError,'authority_real_qualification_rejected'):
            provider.create_capture_authority_registry(registry,qualification_path=evidence,
                qualification_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),
                expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE,
                source_commit='a'*40,official_version='official_live_weekly19_base15w_reserve15w_stage014',
                critical_files=list(provider.CAPTURE_AUTHORITY_SOURCE_FILES),manifest_created_at_utc=NOW.isoformat(),now=NOW)
        self.assertFalse(registry.exists())
        self.assertFalse(Path(str(registry)+'.key').exists())

    def test_authority_registry_requires_real_production_manifest_activation_before_key_creation(self):
        qualification=dict(path=str(self.root/'qualification.json'),sha256='a'*64)
        with mock.patch.object(provider,'_validate_authority_qualification',return_value=dict(evidence_sha256='b'*64)):
            for release,activation in ((None,None),(dict(qualified=True),dict(qualified=True))):
                registry=self.root/'never-created-authority.json'
                with self.subTest(release=release),self.assertRaises(provider.BrokerEvidenceError):
                    provider.create_capture_authority_registry(registry,qualification_path=qualification['path'],qualification_sha256=qualification['sha256'],
                        expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=PROFILE,source_commit='a'*40,
                        official_version='official_live_weekly19_base15w_reserve15w_stage014',critical_files=list(provider.CAPTURE_AUTHORITY_SOURCE_FILES),
                        manifest_created_at_utc=NOW.isoformat(),now=NOW,
                        production_release_manifest=release,production_activation_receipt=activation)
                self.assertFalse(registry.exists());self.assertFalse(Path(str(registry)+'.key').exists())

    def test_authority_runner_cannot_use_material_commit_as_production_head(self):
        authority=SimpleNamespace(registry=dict(qualified_source_commit='a'*40,production_source_commit='a'*40,
            material_source_commit='b'*40,qualification_identity=dict(source_commit='a'*40)))
        capture=dict(runner_provenance=dict(source_commit='a'*40))
        provider._assert_runner_production_source(capture,authority)
        with self.assertRaises(provider.BrokerEvidenceError):
            provider._assert_runner_production_source(dict(runner_provenance=dict(source_commit='b'*40)),authority)
        authority.registry['qualified_source_commit']='c'*40
        with self.assertRaises(provider.BrokerEvidenceError): provider._assert_runner_production_source(capture,authority)

    def test_authority_mac_binds_nonce_context_and_payload_but_is_not_production_proof(self):
        key=b'offline-unit-fixture-key-32-bytes!'
        body=dict(schema='weekly19.capture-authority-receipt.v1',capture_kind='stage174_query',
            registry_sha256='a'*64,raw_capture_sha256='b'*64,account_key=ACCOUNT,material_release_id=RELEASE,
            execution_profile=PROFILE,nonce='1'*32,generation_uuid=GENERATION)
        payload=json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
        receipt=dict(body,hmac_sha256=hmac.new(key,payload,hashlib.sha256).hexdigest())
        self.assertIsNone(provider._verify_capture_receipt_mac(receipt,key,body))
        wrong=dict(receipt,nonce='2'*32)
        with self.assertRaises(provider.BrokerEvidenceError): provider._verify_capture_receipt_mac(wrong,key,body)
        wrong=dict(receipt,raw_capture_sha256='c'*64)
        with self.assertRaises(provider.BrokerEvidenceError): provider._verify_capture_receipt_mac(wrong,key,body)

    def test_bank_and_day_close_are_explicitly_unavailable_without_accepted_parser(self):
        for method in (provider.load_bank_cashflow_receipt,provider.load_cashflow_day_close):
            with self.assertRaisesRegex(provider.BrokerEvidenceError,'accepted_cashflow_source_missing'):
                method(dict(verified=True,source_kind='bank',cashflows_complete=True))


if __name__=='__main__': unittest.main()
