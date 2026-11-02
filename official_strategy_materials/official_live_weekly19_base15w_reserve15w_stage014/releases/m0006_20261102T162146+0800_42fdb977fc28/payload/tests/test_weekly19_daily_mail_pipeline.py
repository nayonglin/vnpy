"""Offline daily-mail integration: fixture sender, never SMTP/CTP/orders."""
import copy
from datetime import datetime
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'examples/portfolio_backtesting'), str(ROOT / 'tests')]
import qmt_roll_weekly19_live_pipeline as pipeline
import qmt_roll_weekly19_runtime as runtime
from test_weekly19_live_pipeline import FixtureBackend, report_broker
from test_weekly19_runtime import ACCOUNT, RELEASE, NOW
import test_weekly19_runtime as runtime_tests


class DailyBackend(FixtureBackend):
    def __init__(self):
        super().__init__()
        self.messages = []
        self.balance = '150000.00'
        day = '2026-11-02'
        prior = '2026-10-30'
        self.bars[day] = copy.deepcopy(self.bars[prior])
        for bar in self.bars[day].values():
            bar.datetime = pd.Timestamp(day).to_pydatetime()
        self.metadata['daily_mapping'][day] = copy.deepcopy(self.metadata['daily_mapping'][prior])
        extra = self.epochs.loc[self.epochs.date.eq(prior)].copy()
        extra['date'] = day
        self.epochs = pd.concat([self.epochs, extra], ignore_index=True)

    def load_inputs(self, target_date, now):
        result = super().load_inputs(target_date, now)
        result['broker_snapshot'] = report_broker(balance=self.balance, available='0.00', now=now, day=target_date)
        return result

    def require_production(self):
        # This injected fixture still has no real backend, credentials or sockets.
        pass

    def validate_initial_account(self, snapshot, now):
        assert json.loads(snapshot['positions']['raw_payload'])['positions'] == []

    def send_mail(self, report):
        self.sends += 1
        self.messages.append(copy.deepcopy(report))
        return getattr(self, 'daily_response', {'email_status':'sent'}) if report['schema']=='weekly19.daily-risk-report.v1' else {'email_status':'sent'}


class DailyMailIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/private/tmp')
        parent = Path(self.tmp.name).resolve()
        parent.chmod(0o700)
        self.backend = DailyBackend()
        self.context = dict(backend=self.backend, state_path=parent / 'state.json', mail_outbox=parent,
                            account_key=ACCOUNT, material_release_id=RELEASE, cold_start_date='2026-10-30',
                            target_date='2026-10-30', now=NOW, preview=True)

    def tearDown(self):
        self.tmp.cleanup()

    def monday(self, *, preview=True):
        self.context['preview'] = preview
        pipeline.run_weekly19_support_job('postclose-precompute', context=self.context)
        self.context.update(target_date='2026-11-02', now=datetime.fromisoformat('2026-11-02T16:55:00+08:00'))
        pipeline.run_weekly19_support_job('postclose-precompute', context=self.context)

    def test_monday_preview_emits_no_signal_mail_without_sender_or_replay(self):
        self.monday()
        before = pipeline.pipeline_store(self.context).read()
        result = pipeline.run_weekly19_support_job('postclose-report', context=self.context)
        self.assertIsNotNone(result['mail'])
        self.assertEqual(result['daily_mail']['schema'], 'weekly19.daily-risk-report.v1')
        self.assertEqual(result['daily_mail']['target_date'], '2026-11-02')
        self.assertIn('无', result['daily_mail']['body'])
        self.assertEqual(self.backend.sends, 0)
        self.assertEqual(self.backend.publishes, 0)
        self.assertEqual(before, pipeline.pipeline_store(self.context).read())

    def test_monday_repeated_report_sends_once_and_separate_from_friday(self):
        self.monday(preview=False)
        # Friday precompute retains its independent weekly/funding mail.
        self.assertEqual(self.backend.sends, 1)
        a = pipeline.run_weekly19_support_job('postclose-report', context=self.context)
        b = pipeline.run_weekly19_support_job('postclose-report', context=self.context)
        self.assertEqual(self.backend.sends, 2)
        self.assertEqual(a['daily_mail']['delivery']['status'], 'sent')
        self.assertEqual(b['daily_mail']['delivery']['status'], 'already_sent')

    def test_unprocessed_day_is_blocked_instead_of_false_no_risk(self):
        result = pipeline.run_weekly19_support_job('postclose-report', context=self.context)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(self.backend.sends, 0)

    def test_unknown_delivery_is_explicit_error_and_does_not_resend(self):
        self.monday(preview=False)
        self.backend.daily_response = {'email_status':'delivery_unknown'}
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, 'daily_mail_delivery'):
                pipeline.run_weekly19_support_job('postclose-report', context=self.context)
        self.assertEqual(self.backend.sends, 2, 'one Friday and one ambiguous daily attempt only')

    def test_daily_report_refreshes_readonly_evidence_before_reading_status(self):
        self.monday(preview=False)
        fixed = self.context['now']
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls.fromisoformat(fixed.isoformat())
        self.context['now'] = Clock.fromisoformat(fixed.isoformat())
        calls = []
        self.backend.refresh_readonly = lambda at: calls.append(at)
        with patch.object(pipeline, 'datetime', Clock):
            pipeline.run_weekly19_support_job('postclose-report', context=self.context)
        self.assertEqual(len(calls), 1, 'report must not reuse an expired earlier account/query capture')


class DailyRiskProjectionTests(unittest.TestCase):
    def fixture(self):
        helper = runtime_tests.CloseLifecycleTests()
        obj, bars, volume = helper.opened()
        plan = helper.plan_close(obj, bars)
        return helper, obj, plan, volume

    def test_intent_carries_same_day_raw_exit_reason(self):
        helper, obj, plan, volume = self.fixture()
        self.assertEqual(plan.get('exit_reason'), 'long_base_stop')

    def test_reason_rejects_old_open_side_wrong_position_and_conflicts(self):
        from vnpy.trader.constant import Direction
        helper, obj, plan, volume = self.fixture()
        event = dict(date='2026-10-30', vt_symbol=plan['vt_symbol'], position_direction='long',
                     offset='Close', reason='long_risk_cluster_heat_deleverage')
        saved = obj.strategy.trade_event_diagnostics
        try:
            for change in [dict(date='2026-10-29'), dict(offset='Open'), dict(position_direction='short'), dict(vt_symbol='ru2605.SHFE')]:
                obj.strategy.trade_event_diagnostics = [dict(event, **change)]
                self.assertEqual(obj.engine._mail_close_reason(obj.strategy, plan['vt_symbol'], '2026-10-30', Direction.SHORT), '')
            obj.strategy.trade_event_diagnostics = [event, dict(event, reason='forced_margin_deleverage')]
            self.assertEqual(obj.engine._mail_close_reason(obj.strategy, plan['vt_symbol'], '2026-10-30', Direction.SHORT), '')
        finally:
            obj.strategy.trade_event_diagnostics = saved

    def test_pending_is_not_a_fill_and_partial_close_uses_original_position_direction(self):
        helper, obj, plan, volume = self.fixture()
        bundle = dict(decision=dict(trading_date='2026-10-30'), runtime=obj.export_state())
        rows = pipeline._daily_risk_rows(bundle)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['position_direction'], 'long')
        self.assertEqual(rows[0]['filled_volume'], 0)
        self.assertEqual(rows[0]['planned_volume'], volume)
        helper.fill(obj, plan, 1, 100.0, 'mail-partial-close')
        bundle['runtime'] = obj.export_state()
        rows = pipeline._daily_risk_rows(bundle)
        self.assertEqual(rows[0]['filled_volume'], 1)
        self.assertEqual(rows[0]['fill_trading_dates'], ['2026-11-02'])
        self.assertEqual(rows[0]['reason_code'], 'long_base_stop')
        evidence = next(iter(obj.close_lifecycles.values()))['fill_evidence'][0]
        self.assertEqual(evidence['trade_id'], 'mail-partial-close')
        self.assertEqual(len(evidence['raw_sha256']), 64)
        state = obj.export_state()
        helper.fill(obj, plan, 1, 100.0, 'mail-partial-close')
        self.assertEqual(state, obj.export_state(), 'duplicate fill must not duplicate date evidence')

    def test_completed_old_signal_is_shown_on_actual_fill_trading_day_only(self):
        helper, obj, plan, volume = self.fixture()
        helper.fill(obj, plan, volume, 100.0, 'mail-full-close')
        bundle = dict(decision=dict(trading_date='2026-11-02'), runtime=obj.export_state())
        rows = pipeline._daily_risk_rows(bundle)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['status'], 'completed')
        bundle['decision']['trading_date'] = '2026-11-03'
        self.assertEqual(pipeline._daily_risk_rows(bundle), [])

    def test_retry_intents_count_one_original_lifecycle_and_keep_reason(self):
        helper, obj, plan, volume = self.fixture()
        helper.fill(obj, plan, 1, 100.0, 'mail-partial-retry')
        obj.apply_order_update(runtime_tests.envelope(dict(schema='weekly19.ctp-order.v1',
            source_kind='ctp_order_callback', account_key=ACCOUNT, material_release_id=RELEASE,
            signal_order_id=plan['signal_order_id'], event_id='mail-close-cancel',
            status='cancelled', traded=1, broker_order_id='broker-'+plan['intent_id'])))
        snapshot = runtime_tests.broker(positions=[dict(vt_symbol=plan['vt_symbol'], direction='long', volume=volume-1)],
                                        now=obj.clock(), day='2026-11-02')
        quote = dict(symbol=plan['vt_symbol'], observed_at=obj.clock().isoformat(), bid=99.0, ask=99.5,
                     session_id='fixture-night', trading_date='2026-11-02')
        retry = obj.reconcile_broker_snapshot(snapshot, obj.confirmed_cash_state, quote_snapshot=quote)['retry_intents'][0]
        self.assertEqual(retry['exit_reason'], plan['exit_reason'])
        rows = pipeline._daily_risk_rows(dict(decision=dict(trading_date='2026-11-02'), runtime=obj.export_state()))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['planned_volume'], volume)
        self.assertEqual(rows[0]['filled_volume'], 1)
        self.assertGreaterEqual(len(rows[0]['intent_ids']), 2)

    def test_fill_date_cannot_be_changed_without_accepted_fill_semantics(self):
        helper, obj, plan, volume = self.fixture()
        helper.fill(obj, plan, volume, 100.0, 'mail-tampered-date')
        saved = obj.export_state()
        data = runtime._decode(saved['runtime'])
        next(iter(data['close_lifecycles'].values()))['fill_evidence'][0]['trading_day'] = '2026-11-03'
        saved['runtime'] = runtime._encode(data)
        with self.assertRaisesRegex(ValueError, 'fill_evidence'):
            pipeline._daily_risk_rows(dict(decision=dict(trading_date='2026-11-03'), runtime=saved))

    def test_legacy_completed_without_fill_dates_stays_explicitly_unconfirmed(self):
        helper, obj, plan, volume = self.fixture()
        helper.fill(obj, plan, volume, 100.0, 'mail-legacy-date')
        saved = obj.export_state()
        data = runtime._decode(saved['runtime'])
        next(iter(data['close_lifecycles'].values())).pop('fill_evidence')
        saved['runtime'] = runtime._encode(data)
        rows = pipeline._daily_risk_rows(dict(decision=dict(trading_date='2026-11-03'), runtime=saved))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['fill_date_coverage'], 'legacy_or_partial')


class DailyBackendRoutingTests(unittest.TestCase):
    def test_daily_and_friday_use_separate_known_event_types(self):
        from qmt_roll_weekly19_local_backend import LocalEvidenceBackend
        backend = LocalEvidenceBackend.__new__(LocalEvidenceBackend)
        backend.config = {'material_release_id': RELEASE}
        backend.repo = ROOT
        backend.require_production = lambda: None
        report = dict(preview=False, material_release_id=RELEASE, subject='fixture', body='fixture',
                      blockers=[], report_sha256='a'*64)
        with patch('qmt_roll_official_live_email_notify.send_official_live_email_notification', return_value={'email_status':'sent'}) as transport:
            for schema, event in [('weekly19.daily-risk-report.v1', 'weekly19_daily_risk'),
                                  ('weekly19.friday-report.v1', 'weekly19_friday_signal_funding')]:
                backend.send_mail(dict(report, schema=schema))
                self.assertEqual(transport.call_args.kwargs['event_type'], event)
            with self.assertRaisesRegex(ValueError, 'mail_schema'):
                backend.send_mail(dict(report, schema='unknown'))
            self.assertEqual(transport.call_count, 2)


if __name__ == '__main__':
    unittest.main()
