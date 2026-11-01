"""Offline execution safety tests; no broker or production qualification."""
import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'examples/portfolio_backtesting'))
import qmt_roll_official_execution_profile as profiles
import qmt_roll_weekly19_funding as funding
try:
    import qmt_roll_weekly19_execution as execution
except ModuleNotFoundError:
    execution = None

NOW = datetime(2026, 10, 30, 21, tzinfo=timezone(timedelta(hours=8)))
ACCOUNT = hashlib.sha256(b'9999\0test-account').hexdigest()
RELEASE = 'weekly19-test-release'
DAY = '2026-11-02'

def envelope(raw):
    text = json.dumps(raw, sort_keys=True, separators=(',', ':'))
    return dict(raw_payload=text, raw_sha256=hashlib.sha256(text.encode()).hexdigest())

def account(**overrides):
    raw = dict(schema='weekly19.ctp-account.v1', source_kind='ctp_account_callback',
               account_key=ACCOUNT, material_release_id=RELEASE, observed_at=NOW.isoformat(),
               trading_day=DAY, generation_uuid='q1', query_reqid=1, query_complete=True,
               CurrencyID='CNY', BrokerID='9999', AccountID='test-account',
               Balance='150000.00', Deposit='0.00', Withdraw='0.00', Available='10000.00')
    raw.update(overrides)
    return envelope(raw)

def query(kind, rows, **overrides):
    raw = dict(schema='weekly19.ctp-' + kind + '.v1',
               source_kind='ctp_' + ('position' if kind == 'positions' else 'order') + '_query',
               account_key=ACCOUNT, material_release_id=RELEASE, trading_day=DAY,
               observed_at=NOW.isoformat(), generation_uuid='q1', query_reqid=2, query_complete=True)
    raw[kind] = rows
    raw.update(overrides)
    return envelope(raw)

def trade(trade_id, volume=1):
    return envelope(dict(schema='weekly19.ctp-trade.v1', source_kind='ctp_trade_callback',
        account_key=ACCOUNT, material_release_id=RELEASE, intent_id='old-close', trade_id=trade_id,
        vt_symbol='rb2610.SHFE', offset='close', volume=volume,
        trade_datetime=(NOW - timedelta(seconds=1)).isoformat()))

def fixture():
    broker = account()
    cash = funding.initial_state(ACCOUNT, RELEASE, '2026-10-30')
    cash = funding.recommend_topup(cash, broker, '2026-10-30', [], 'f' * 64, NOW)['state']
    snapshot = dict(account=broker, positions=query('positions', []), orders=query('orders', []))
    intent = dict(intent_id='w19-1', signal_order_id='W19.1', signal_datetime='2026-10-30T00:00:00',
                  signal_identity=dict(intent_id='w19-1', signal_order_id='W19.1',
                                       signal_datetime='2026-10-30T00:00:00', trading_date=DAY),
                  execution_profile='weekly19-15w-r150k',
                  official_live_version='official_live_weekly19_base15w_reserve15w_stage014',
                  capital=150000, capital_label='15w',
                  ruleset_version='stage014_week_close_19_short_bottom20_original_risk_external_reserve_v1',
                  material_release_id=RELEASE, account_fingerprint=ACCOUNT,
                  trading_date=DAY, target_date='2026-10-30', completed_target_date='2026-10-30', physical_epoch_id='rb2701.SHFE:2026',
                  vt_symbol='rb2701.SHFE', direction='long', offset='open',
                  planned_volume=1, limit_price=4000, source='weekly19_pending_order',
                  intent_kind='native_entry', data_receipt_sha256='f' * 64,
                  protection_timing='fresh_completed_week_close', completed_week_end='2026-10-30',
                  requires_funding_revision=cash['revision'])
    context = dict(material_release_id=RELEASE, account_fingerprint=ACCOUNT, trading_date=DAY,
                   cold_start_date='2026-10-30', target_cutoff_date='2026-10-30', data_receipt_sha256='f' * 64,
                   confirmed_cash_state=cash, broker_snapshot=snapshot,
                   quote=dict(vt_symbol='rb2701.SHFE', observed_at=NOW.isoformat(), bid=3999,
                              ask=4000, session_id='night-20261102', trading_date=DAY),
                   metadata=dict(vt_symbol='rb2701.SHFE', physical_epoch_id='rb2701.SHFE:2026',
                                 pricetick=1, size=10, broker_margin_rate='0.165',
                                 max_volume=100, min_volume=1),
                   session=dict(is_open=True, trading_date=DAY, session_id='night-20261102',
                                starts_at=NOW.isoformat(), ends_at=(NOW + timedelta(hours=2)).isoformat()),
                   completed_close_intents=[], execution_ledger_rows=[])
    context['durable_state_sha256'] = 'e' * 64
    context['open_risk_proof'] = dict(schema='weekly19.open-risk-proof.v1', intent_id=intent['intent_id'],
        selected_volume=1, approved_volume_cap=1, current_equity=150000, current_available=10000,
        execution_reference=4000, stop_price=3900, source_history_sha256='a' * 64,
        source_data_receipt_sha256='f' * 64, durable_state_sha256='e' * 64,
        account_raw_sha256=broker['raw_sha256'], quote_sha256=hashlib.sha256(json.dumps(context['quote'],
            ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        quote_session_id=context['quote']['session_id'], confirmed_funding_revision=cash['revision'], blocked_reason='')
    return intent, context

class Weekly19ExecutionTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(execution, 'weekly19 execution boundary is absent')

    def test_profile_is_registered_without_changing_historical_default(self):
        weekly = profiles.resolve_execution_profile('weekly19-15w-r150k')
        self.assertEqual(weekly.capital, 150000)
        self.assertEqual(weekly.allowed_intent_sources, ('weekly19_pending_order', 'weekly19_risk_reduce'))
        self.assertFalse(weekly.intraday_stop_retry_enabled)
        self.assertEqual(weekly.decision_mode, 'weekly19')
        self.assertIs(profiles.resolve_execution_profile(), profiles.C9_15W_PROFILE)

    def test_admitted_open_is_capped_by_real_available_without_mutation(self):
        intent, context = fixture()
        before = copy.deepcopy((intent, context))
        ready = execution.evaluate_intent(intent, context, now=NOW)
        self.assertTrue(ready['allowed'], ready)
        self.assertEqual(ready['volume'], 1)
        self.assertEqual((intent, context), before)
        intent['planned_volume'] = 2
        context['open_risk_proof'].update(selected_volume=2, approved_volume_cap=2)
        denied = execution.evaluate_intent(intent, context, now=NOW)
        self.assertFalse(denied['allowed'])
        self.assertIn('weekly19_real_available_insufficient', denied['blockers'])

    def test_old_sources_release_and_receipt_are_rejected(self):
        for field, value in [('source', 'stage901_pending_order'),
                             ('material_release_id', 'old-release'),
                             ('data_receipt_sha256', 'b' * 64),
                             ('ruleset_version', 'stage037')]:
            with self.subTest(field=field):
                intent, context = fixture()
                intent[field] = value
                self.assertFalse(execution.evaluate_intent(intent, context, now=NOW)['allowed'])

    def test_open_needs_fresh_account_positions_orders_quote_and_session(self):
        for field in ('positions', 'orders'):
            intent, context = fixture()
            context['broker_snapshot'][field] = query(field, [], query_complete=False)
            self.assertFalse(execution.evaluate_intent(intent, context, now=NOW)['allowed'])
        for area in ('positions', 'orders'):
            intent, context = fixture()
            context['broker_snapshot'][area] = query(area, [], observed_at=(NOW - timedelta(minutes=6)).isoformat())
            self.assertFalse(execution.evaluate_intent(intent, context, now=NOW)['allowed'])
        intent, context = fixture()
        context['session']['is_open'] = False
        self.assertFalse(execution.evaluate_intent(intent, context, now=NOW)['allowed'])

    def test_close_not_blocked_by_missing_cash_but_requires_actual_position(self):
        intent, context = fixture()
        intent.update(offset='close', direction='short', source='weekly19_risk_reduce', intent_kind='risk_close')
        context['confirmed_cash_state'] = None
        context['broker_snapshot']['account'] = None
        context['broker_snapshot']['positions'] = query('positions', [dict(vt_symbol=intent['vt_symbol'], direction='long', volume=1)])
        ready = execution.evaluate_intent(intent, context, now=NOW)
        self.assertTrue(ready['allowed'], ready)
        context['broker_snapshot']['positions'] = query('positions', [])
        self.assertIn('weekly19_close_exceeds_actual_position', execution.evaluate_intent(intent, context, now=NOW)['blockers'])

    def test_pending_topup_never_grants_available_or_open(self):
        intent, context = fixture()
        broker = account(Balance='120000.00')
        cash = funding.recommend_topup(context['confirmed_cash_state'], broker, '2026-10-30', ['x'], 'f' * 64, NOW)['state']
        context['confirmed_cash_state'] = cash
        context['broker_snapshot']['account'] = broker
        intent['requires_funding_revision'] = cash['revision']
        result = execution.evaluate_intent(intent, context, now=NOW)
        self.assertFalse(result['allowed'])
        self.assertTrue(any('funding_pending' in x for x in result['blockers']), result)

    def test_rollover_reopen_requires_real_full_close_and_fresh_flat(self):
        intent, context = fixture()
        intent.update(intent_kind='rollover_reopen', depends_on_close_intent_id='old-close',
                      rollover_from_vt_symbol='rb2610.SHFE')
        self.assertFalse(execution.evaluate_intent(intent, context, now=NOW)['allowed'])
        context['completed_close_intents'] = [dict(intent_id='old-close', material_release_id=RELEASE,
                    account_fingerprint=ACCOUNT, offset='close', vt_symbol='rb2610.SHFE',
                    requested_volume=2, filled_volume=1, trade_ids=['real-1'], broker_fills=[trade('real-1')])]
        self.assertFalse(execution.evaluate_intent(intent, context, now=NOW)['allowed'])
        context['completed_close_intents'][0]['filled_volume'] = 2
        context['completed_close_intents'][0]['trade_ids'].append('real-2')
        context['completed_close_intents'][0]['broker_fills'].append(trade('real-2'))
        self.assertTrue(execution.evaluate_intent(intent, context, now=NOW)['allowed'])
        context['broker_snapshot']['positions'] = query('positions', [dict(vt_symbol='rb2610.SHFE', direction='long', volume=1)])
        self.assertFalse(execution.evaluate_intent(intent, context, now=NOW)['allowed'])

    def test_c9_protection_metadata_and_pre_activation_signal_rejected(self):
        intent, context = fixture()
        intent['protection_timing'] = 'intraday_tick'
        self.assertFalse(execution.evaluate_intent(intent, context, now=NOW)['allowed'])
        intent, context = fixture()
        context['cold_start_date'] = '2026-10-31'
        self.assertFalse(execution.evaluate_intent(intent, context, now=NOW)['allowed'])

if __name__ == '__main__':
    unittest.main()

class Weekly19ConsumerRouteTest(unittest.TestCase):
    def test_stage905_weekly_does_not_read_legacy_inputs(self):
        from unittest.mock import patch
        import run_qmt_roll_stage905_official_live_executor_dry_run as consumer
        from types import SimpleNamespace
        intent, context = fixture()
        decision = dict(schema='weekly19.runtime-decision.v1', material_release_id=RELEASE,
                        account_fingerprint=ACCOUNT, trading_date='2026-10-30', intents=[intent])
        with patch.object(consumer, '_read_csv_maybe', side_effect=AssertionError('legacy artifact read')):
            result = consumer.run_executor_dry_run('2026-10-30',
                       execution_profile=profiles.resolve_execution_profile('weekly19-15w-r150k'),
                       weekly19_decision=decision, weekly19_context=context,
                       clock=SimpleNamespace(epoch_ns=lambda: int(NOW.timestamp()*1000000000), monotonic_ns=lambda: 1, clock_domain_id=lambda: 'fixture'), write_compat_outputs=False)
        self.assertEqual(result.summary['execution_profile'], 'weekly19-15w-r150k')
        self.assertEqual(result.summary['ready_count'], 1)
        self.assertEqual(result.summary['send_order_api_called_count'], 0)

    def test_stage945_weekly_uses_dedicated_cli_without_c9_flags(self):
        import run_qmt_roll_stage945_official_live_production_session_launcher as consumer
        command = consumer.build_stage930_command(spec=consumer.SESSION_SPECS['night'], target_date='2026-10-30',
                     execution_profile=profiles.resolve_execution_profile('weekly19-15w-r150k'))
        self.assertIn('run_qmt_roll_weekly19_live.py', ' '.join(command))
        self.assertIn('--context-file', command)
        self.assertNotIn('--detector-mode', command)
        self.assertNotIn('--ai-pool-preflight-mode', command)
        self.assertEqual(command[command.index('--session')+1], 'night')
        self.assertEqual(command[command.index('--duration-seconds')+1], str(consumer.SESSION_SPECS['night'].duration_seconds))
        self.assertIn('--require-current-session-name', command)

    def test_stage947_keeps_seven_jobs_and_routes_weekly_without_ai(self):
        import run_qmt_roll_stage947_official_live_production_support_launcher as consumer
        for job in ('postclose-precompute', 'postclose-report', 'monthly-ai-pool', 'health'):
            command = consumer.build_support_command(consumer.SUPPORT_JOB_SPECS[job],
                         execution_profile=profiles.resolve_execution_profile('weekly19-15w-r150k'))
            self.assertIn('run_qmt_roll_weekly19_live.py', ' '.join(command))
            self.assertNotIn('run_qmt_roll_stage935', ' '.join(command))
        self.assertEqual(len(consumer.SUPPORT_JOB_SPECS), 5)

class Weekly19SubmitBoundaryTest(unittest.TestCase):
    def test_current_risk_cap_cannot_silently_shrink_a_signed_100_lot_delivery_at_send(self):
        import run_qmt_roll_stage931_official_live_ctp_submit_adapter as consumer
        from copy import deepcopy
        intent, context = fixture()
        intent['planned_volume'] = 100
        context['broker_snapshot']['account'] = account(Balance='1000000.00', Available='1000000.00')
        context['open_risk_proof'].update(selected_volume=50, approved_volume_cap=100,
            current_equity=1000000, current_available=1000000,
            account_raw_sha256=context['broker_snapshot']['account']['raw_sha256'])
        admitted=execution.evaluate_intent(intent,context,now=NOW)
        self.assertTrue(admitted['allowed'],admitted)
        self.assertEqual(admitted['volume'],50)
        original=deepcopy(intent)
        self.assertIn('weekly19_signed_delivery_volume_changed',
            consumer.weekly19_pre_submit_blockers(intent,lambda row:context,now=NOW))
        self.assertEqual(intent,original)
        context['open_risk_proof']['selected_volume']=100
        self.assertEqual(consumer.weekly19_pre_submit_blockers(intent,lambda row:context,now=NOW),[])

    def test_physical_split_cannot_hide_parent_risk_cut_and_real_fills_release_only_remaining_cap(self):
        from types import SimpleNamespace
        import run_qmt_roll_stage931_official_live_ctp_submit_adapter as consumer
        intent, context = fixture()
        intent.update(intent_id='delivery', planned_intent_id='w19-1', planned_volume=25)
        parent=dict(intent, planned_volume=100)
        context['broker_snapshot']['account']=account(Balance='1000000.00',Available='1000000.00')
        context['metadata']['max_volume']=1000
        context['open_risk_proof'].update(selected_volume=50,approved_volume_cap=225,current_equity=1000000,current_available=1000000,
            account_raw_sha256=context['broker_snapshot']['account']['raw_sha256'])
        context['actual_fill_lifecycle']=dict(schema='weekly19.actual-fill-lifecycle.v1',planned_intent_id='w19-1',delivery_intent_id='delivery',
            signal_order_id=intent['signal_order_id'],business_approved_volume=225,business_filled_volume=0,business_remaining_volume=225,
            delivery_approved_volume=100,delivery_filled_volume=0,delivery_remaining_volume=100,delivery_trade_ids=[],durable_state_sha256=context['durable_state_sha256'])
        transport=dict(weekly19_immutable_parent_intent=parent,weekly19_current_physical_child=dict(volume=25))
        self.assertTrue(execution.evaluate_intent(intent,context,now=NOW)['allowed'])
        self.assertIn('weekly19_signed_delivery_volume_changed',consumer.weekly19_pre_submit_blockers(intent,lambda row,**kw:context,now=NOW,transport_context=transport))
        # Only real, durably admitted fills lower the remaining signed cap.
        parent['planned_volume']=225;intent['planned_volume']=125;transport['weekly19_current_physical_child']['volume']=125
        context['open_risk_proof']['selected_volume']=125
        context['actual_fill_lifecycle'].update(delivery_approved_volume=225,business_filled_volume=100,business_remaining_volume=125,
            delivery_filled_volume=100,delivery_remaining_volume=125,delivery_trade_ids=['conditional-real-fill-identity'])
        self.assertEqual(consumer.weekly19_pre_submit_blockers(intent,lambda row,**kw:context,now=NOW,transport_context=transport),[])
        context['actual_fill_lifecycle']['delivery_filled_volume']=0
        self.assertTrue(consumer.weekly19_pre_submit_blockers(intent,lambda row,**kw:context,now=NOW,transport_context=transport))

    def test_final_gate_samples_real_clock_after_slow_fresh_source_provider(self):
        import run_qmt_roll_stage931_official_live_ctp_submit_adapter as consumer
        intent,context=fixture();later=NOW+timedelta(seconds=4)
        for kind in ('account','positions','orders'):
            raw=json.loads(context['broker_snapshot'][kind]['raw_payload']);raw['observed_at']=later.isoformat()
            context['broker_snapshot'][kind]=envelope(raw)
        context['quote']['observed_at']=later.isoformat()
        context['open_risk_proof'].update(account_raw_sha256=context['broker_snapshot']['account']['raw_sha256'],quote_sha256=funding._hash(context['quote']))
        self.assertEqual(consumer.weekly19_pre_submit_blockers(intent,lambda row:context,now=NOW,now_provider=lambda:later),[])

    def test_weekly_metadata_uses_weekly_contract_instead_of_stage372(self):
        import run_qmt_roll_stage931_official_live_ctp_submit_adapter as consumer
        intent, _ = fixture()
        intent['position_epoch_id'] = 'weekly-own-position-epoch'
        self.assertEqual(consumer._execution_profile_intent_blockers(profiles.resolve_execution_profile('weekly19-15w-r150k'), intent), [])

    def test_fresh_provider_is_rechecked_instead_of_trusting_dryrun_gate(self):
        import run_qmt_roll_stage931_official_live_ctp_submit_adapter as consumer
        intent, context = fixture()
        intent['weekly19_gate'] = dict(allowed=True)
        self.assertEqual(consumer.weekly19_pre_submit_blockers(intent, lambda _: context, now=NOW), [])
        context['broker_snapshot']['account'] = account(Available='0')
        self.assertIn('weekly19_risk_fresh_source_mismatch', consumer.weekly19_pre_submit_blockers(intent, lambda _: context, now=NOW))
        self.assertTrue(consumer.weekly19_pre_submit_blockers(intent, None, now=NOW))

    def test_only_hashed_real_trade_details_can_release_rollover_dependency(self):
        intent, context = fixture()
        intent.update(intent_kind='rollover_reopen', depends_on_close_intent_id='old-close', rollover_from_vt_symbol='rb2610.SHFE')
        context['completed_close_intents'] = [dict(intent_id='old-close', material_release_id=RELEASE,
            account_fingerprint=ACCOUNT, offset='close', vt_symbol='rb2610.SHFE', requested_volume=1,
            filled_volume=1, trade_ids=['invented'])]
        self.assertFalse(execution.evaluate_intent(intent, context, now=NOW)['allowed'])

class Weekly19ReliabilityReuseTest(unittest.TestCase):
    def test_weekly_order_payload_enters_existing_stage931_artifact_guard(self):
        import run_qmt_roll_stage905_official_live_executor_dry_run as producer
        import run_qmt_roll_stage931_official_live_ctp_submit_adapter as consumer
        from types import SimpleNamespace
        intent, context = fixture()
        decision = dict(schema='weekly19.runtime-decision.v1', material_release_id=RELEASE,
            account_fingerprint=ACCOUNT, trading_date='2026-10-30', intents=[intent])
        result = producer.run_executor_dry_run('2026-10-30',
            execution_profile=profiles.resolve_execution_profile('weekly19-15w-r150k'),
            weekly19_decision=decision, weekly19_context=context,
            clock=SimpleNamespace(epoch_ns=lambda: int(NOW.timestamp()*1000000000)), write_compat_outputs=False)
        self.assertEqual(consumer._stage905_ready_intent_artifact_blockers(result.intents), [])
        tampered = result.intents.copy(deep=True)
        tampered.loc[0, 'material_release_id'] = 'old'
        self.assertTrue(consumer._stage905_ready_intent_artifact_blockers(tampered))

    def test_durable_generic_ledger_preserves_weekly_signal_and_release_identity(self):
        import run_qmt_roll_stage931_official_live_ctp_submit_adapter as consumer
        intent, _ = fixture()
        metadata = consumer._intent_ledger_metadata(intent)
        self.assertEqual(metadata.get('material_release_id'), RELEASE)
        self.assertEqual(metadata.get('signal_identity'), intent['signal_identity'])
        self.assertEqual(metadata.get('physical_epoch_id'), intent['physical_epoch_id'])

    def test_production_qualification_suite_cannot_omit_weekly_boundary(self):
        import build_qmt_roll_stage179_release_manifest as builder
        self.assertIn('tests/test_weekly19_execution.py', builder.PRODUCTION_REQUIRED_TEST_SUITES)
        self.assertIn('examples/portfolio_backtesting/qmt_roll_weekly19_execution.py', builder.DEFAULT_CRITICAL_FILES)

class Weekly19WarmCapabilityTest(unittest.TestCase):
    def test_weekly_warm_executor_cannot_start_without_fresh_and_fill_consumers(self):
        import run_qmt_roll_stage931_official_live_ctp_submit_adapter as consumer
        args = consumer.parse_args(['--command', 'serve', '--execution-profile', 'weekly19-15w-r150k', '--stage179-warm-executor'])
        from unittest.mock import patch
        with patch.object(consumer, '_serve_stage179_no_submit_prewarm', side_effect=AssertionError('legacy prewarm forbidden')):
            with self.assertRaisesRegex(Exception, 'weekly19_qualified_execution_providers_required'):
                consumer.run_serve(args)

    def test_weekly_event_consumer_failure_never_counts_as_durable_fill(self):
        import run_qmt_roll_stage931_official_live_ctp_submit_adapter as consumer
        intent, _ = fixture()
        self.assertTrue(consumer.weekly19_broker_event_blockers('trade', {}, intent, None))
        self.assertTrue(consumer.weekly19_broker_event_blockers('trade', {}, intent, lambda *args: {'status': 'applied'}))
        self.assertEqual(consumer.weekly19_broker_event_blockers('trade', {}, intent,
            lambda *args: {'status': 'applied', 'state_sha256': 'd' * 64}), [])

class Weekly19GovernanceRouteTest(unittest.TestCase):
    def test_configured_authority_resolves_weekly_identity_and_rejects_unknown(self):
        from unittest.mock import patch
        import qmt_roll_official_live_lightweight_context as context
        with patch.object(context, 'OFFICIAL_LIVE_VERSION', 'official_live_weekly19_base15w_reserve15w_stage014'):
            self.assertEqual(profiles.resolve_configured_execution_profile().profile_key, 'weekly19-15w-r150k')
        with patch.object(context, 'OFFICIAL_LIVE_VERSION', 'unrecognized'):
            with self.assertRaises(ValueError):
                profiles.resolve_configured_execution_profile()

    def test_stage930_weekly_initialization_never_starts_old_services(self):
        from unittest.mock import patch
        import run_qmt_roll_stage930_official_live_c9_session_daemon as consumer
        args = consumer._build_parser().parse_args(['--execution-profile', 'weekly19-15w-r150k'])
        with patch.object(consumer, '_initialize_tick_stream_supervisor', side_effect=AssertionError('old tick start')):
            result = consumer._initialize_runtime_services(args, {}, target_date='2026-10-30')
        self.assertEqual(result[1]['enabled'], 0)
        self.assertEqual(result[2]['preflight_status'], 'weekly19_ai_disabled')

    def test_stage927_weekly_arming_requires_actual_qualification_and_data_receipt(self):
        import run_qmt_roll_stage927_official_live_real_submit_arming_gate as consumer
        intent, context = fixture()
        self.assertTrue(consumer.weekly19_arming_blockers(intent, context, now=NOW))

class Weekly19CurrentRiskProofTest(unittest.TestCase):
    def test_every_open_needs_original_rule_current_equity_risk_proof(self):
        intent, context = fixture()
        context.pop('open_risk_proof', None)
        self.assertFalse(execution.evaluate_intent(intent, context, now=NOW)['allowed'])

class Weekly19OwnedLeaseTest(unittest.TestCase):
    def test_own_zero_native_reservation_can_progress_but_sent_evidence_cannot(self):
        intent, context = fixture()
        row = dict(intent_id=intent['intent_id'], material_release_id=RELEASE, account_fingerprint=ACCOUNT,
                   intent_payload_sha256='a' * 64, spool_lease_token='lease-1', event_type='reserved')
        context['execution_ledger_rows'] = [row]
        self.assertFalse(execution.evaluate_intent(intent, context, now=NOW)['allowed'])
        context['current_delivery_lease'] = dict(intent_id=intent['intent_id'], payload_sha256='a' * 64, lease_token='lease-1')
        self.assertTrue(execution.evaluate_intent(intent, context, now=NOW)['allowed'])
        row['event_type'] = 'send_order_called'
        self.assertFalse(execution.evaluate_intent(intent, context, now=NOW)['allowed'])
