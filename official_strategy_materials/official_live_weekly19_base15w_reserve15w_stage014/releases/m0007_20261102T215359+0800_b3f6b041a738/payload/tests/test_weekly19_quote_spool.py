"""Real journal/spool IO with literal offline MD fixture; never production proof."""
from datetime import timedelta
from pathlib import Path
import json
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'examples/portfolio_backtesting'))
from test_weekly19_execution import fixture, NOW, RELEASE, ACCOUNT
from qmt_roll_official_live_tick_stream import TickStreamPipeline
from qmt_roll_official_live_tick_types import DurableTickCursor
from qmt_roll_official_live_trace import LatencyTrace
import qmt_roll_official_live_intent_spool as spool
try:
    import qmt_roll_weekly19_quote_spool as weekly
except ModuleNotFoundError:
    weekly = None

class QuoteClock:
    epoch = int(NOW.timestamp() * 1000000000)
    mono = 10000000000
    def epoch_ns(self): return self.epoch
    def monotonic_ns(self): return self.mono
    def clock_domain_id(self): return 'weekly19-test-boot'

class Weekly19QuoteSpoolTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(weekly, 'weekly19 quote/spool assembly missing')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'md.ndjson'
        self.clock = QuoteClock()
        pipeline = TickStreamPipeline(feed_session_id='weekly19-md', journal_segment_path=self.path,
                    clock=self.clock, max_buffer_ticks=10, writer_batch_size=1)
        pipeline.start()
        self.pipeline = pipeline
        self.addCleanup(lambda: pipeline.shutdown(timeout_seconds=2))
        tick = SimpleNamespace(vt_symbol='rb2701.SHFE', symbol='rb2701', exchange='SHFE', datetime=NOW,
                  last_price=4000.0, bid_price_1=3999.0, ask_price_1=4000.0, bid_volume_1=10, ask_volume_1=10)
        pipeline.capture_ingress(tick)
        self.assertTrue(pipeline.wait_until_durable(1, timeout_seconds=2))
        snapshot = pipeline.durable_snapshot()
        self.cursor = DurableTickCursor(snapshot.feed_session_id, snapshot.durable_ingress_sequence,
                                      snapshot.durable_journal_byte_offset, snapshot.journal_schema)
        self.intent, self.context = fixture()
        import run_qmt_roll_stage905_official_live_executor_dry_run as producer
        from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE
        decision = dict(schema='weekly19.runtime-decision.v1', material_release_id=RELEASE,
            account_fingerprint=ACCOUNT, trading_date='2026-10-30', intents=[self.intent])
        result = producer.run_executor_dry_run('2026-10-30', execution_profile=WEEKLY19_15W_R150K_PROFILE,
            weekly19_decision=decision, weekly19_context=self.context, clock=self.clock, write_compat_outputs=False)
        self.ready = result.intents.iloc[0].to_dict()
        self.state = dict(material_release_id=RELEASE, account_fingerprint=ACCOUNT,
              position_epoch_id='weekly19-epoch-1', state_generation='weekly19-epoch-1:7', revision=7,
              root_position_id='weekly19-root-1', position_cycle_id='weekly19-cycle-1',
              durable_state_sha256='e' * 64)

    def prepare(self):
        return weekly.prepare_weekly19_quote_intent(self.ready, journal_segment_path=self.path,
               durable_through=self.cursor, execution_state=self.state, clock=self.clock)

    def test_public_quote_cache_reads_only_new_frames_and_returns_detached_values(self):
        weekly._QUOTE_CACHE.clear()
        calls=[];original=weekly.TickStreamJournalReader.read_after
        def observed(reader,previous,**kwargs):
            calls.append(previous);return original(reader,previous,**kwargs)
        session=dict(trading_date='2026-11-02',session_id='fixture-night')
        def quote(cursor):
            return weekly.read_weekly19_quote_snapshot(self.path,durable_through=cursor,
                symbol='rb2701.SHFE',clock=self.clock,trading_date='2026-11-02',session=session)
        with patch.object(weekly.TickStreamJournalReader,'read_after',observed):
            first=quote(self.cursor);self.assertEqual(first['ask'],4000.0)
            initial_calls=len(calls);first['ask']=1
            self.assertEqual(quote(self.cursor)['ask'],4000.0);self.assertEqual(len(calls),initial_calls)
            tick=SimpleNamespace(vt_symbol='rb2701.SHFE',symbol='rb2701',exchange='SHFE',datetime=NOW,
                last_price=4001.0,bid_price_1=4000.0,ask_price_1=4001.0,bid_volume_1=10,ask_volume_1=10)
            self.pipeline.capture_ingress(tick);self.assertTrue(self.pipeline.wait_until_durable(2,timeout_seconds=2))
            snap=self.pipeline.durable_snapshot();new=DurableTickCursor(snap.feed_session_id,snap.durable_ingress_sequence,snap.durable_journal_byte_offset,snap.journal_schema)
            self.assertEqual(quote(new)['ask'],4001.0);self.assertEqual(calls[initial_calls],self.cursor)
    def test_cached_quote_still_rehashes_committed_prefix_and_rejects_rewrite(self):
        weekly._latest_quote(self.path,self.cursor,'rb2701.SHFE')
        payload=self.path.read_bytes();position=payload.index(b'4000.0')
        with self.path.open('r+b')as stream:stream.seek(position);stream.write(b'4001.0')
        with self.assertRaisesRegex(ValueError,'journal_changed'):
            weekly._latest_quote(self.path,self.cursor,'rb2701.SHFE')
    def test_public_quote_rejects_future_clock_even_with_valid_cached_row(self):
        self.clock.epoch-=1
        with self.assertRaisesRegex(ValueError,'future'):
            weekly.read_weekly19_quote_snapshot(self.path,durable_through=self.cursor,symbol='rb2701.SHFE',clock=self.clock,
                trading_date='2026-11-02',session=dict(trading_date='2026-11-02',session_id='fixture-night'))

    def test_weekly_signal_and_new_quote_trace_remain_distinct_and_spoolable(self):
        item = self.prepare()
        trace = LatencyTrace.from_json(item['trace_json'])
        self.assertEqual(item['signal_identity'], self.intent['signal_identity'])
        self.assertNotEqual(item['intent_id'], self.intent['intent_id'])
        self.assertIn('weekly19_quote_admitted', trace.stamps)
        self.assertNotIn('stage904_detected', trace.stamps)
        import run_qmt_roll_stage931_official_live_ctp_submit_adapter as consumer
        import pandas as pd
        self.assertEqual(consumer._stage905_ready_intent_artifact_blockers(pd.DataFrame([item])), [])
        connection = spool.open_spool(Path(self.temp.name) / 'spool.sqlite3')
        self.addCleanup(connection.close)
        result = weekly.commit_weekly19_quote_batch(connection, consumer_id='weekly19',
                 expected_cursor=None, next_cursor=self.cursor, intents=[item], clock=self.clock)
        self.assertEqual(result.inserted_count, 1)
        snapshot = spool.snapshot_authorizable_intents(connection, now_epoch_ns=self.clock.epoch_ns(),
                       now_monotonic_ns=self.clock.monotonic_ns(), clock_domain_id=self.clock.clock_domain_id(), execution_profile='weekly19-15w-r150k')
        self.assertIsNotNone(snapshot.candidate)
        self.assertEqual(snapshot.candidate.source, 'weekly19_pending_order')
        observations = spool.read_trace_observations(connection, intent_id=item['intent_id'])
        self.assertIn('weekly19_quote_admitted', observations)
        self.assertNotIn('stage904_detected', observations)

    def test_old_quote_wrong_boot_or_uncommitted_cursor_cannot_make_ready(self):
        self.clock.epoch += 26000000000
        self.clock.mono += 26000000000
        with self.assertRaisesRegex(ValueError, 'quote.*expired|quote.*stale'):
            self.prepare()
        self.clock.epoch -= 26000000000
        self.clock.mono -= 26000000000
        self.cursor = DurableTickCursor('weekly19-md', 1, self.cursor.journal_byte_offset-1)
        with self.assertRaises(ValueError):
            self.prepare()

    def test_caller_quote_flags_or_c9_source_cannot_replace_durable_journal(self):
        self.ready['source'] = 'stage901_pending_order'
        with self.assertRaises(ValueError):
            self.prepare()
        self.ready['source'] = 'weekly19_pending_order'
        self.path.write_text('{"verified":true,"qualified":true}\n')
        with self.assertRaises(ValueError):
            self.prepare()

    def test_replay_is_idempotent_and_old_profile_cursor_is_rejected(self):
        item = self.prepare()
        connection = spool.open_spool(Path(self.temp.name) / 'replay.sqlite3')
        self.addCleanup(connection.close)
        first = weekly.commit_weekly19_quote_batch(connection, expected_cursor=None, next_cursor=self.cursor,
                    intents=[item], clock=self.clock)
        replay = weekly.commit_weekly19_quote_batch(connection, expected_cursor=None, next_cursor=self.cursor,
                    intents=[item], clock=self.clock)
        self.assertEqual(first.inserted_count, 1)
        self.assertTrue(replay.idempotent_replay)
        connection.execute("UPDATE detector_cursors SET consumer_id='stage941'")
        with self.assertRaises(spool.SpoolValidationError):
            spool.snapshot_authorizable_intents(connection, now_epoch_ns=self.clock.epoch_ns(),
                now_monotonic_ns=self.clock.monotonic_ns(), clock_domain_id=self.clock.clock_domain_id(),
                execution_profile='weekly19-15w-r150k')

    def test_same_durable_quote_can_admit_another_real_business_intent_without_clock_renewal(self):
        item = self.prepare()
        connection = spool.open_spool(Path(self.temp.name) / 'same-cursor.sqlite3')
        self.addCleanup(connection.close)
        weekly.commit_weekly19_quote_batch(connection, expected_cursor=None, next_cursor=self.cursor,
            intents=[item], clock=self.clock)
        self.ready['intent_id'] = 'another-planned-intent'
        self.ready['signal_identity'] = dict(self.ready['signal_identity'], intent_id='another-planned-intent')
        another = self.prepare()
        result = weekly.commit_weekly19_quote_batch(connection, expected_cursor=self.cursor, next_cursor=self.cursor,
            intents=[another], clock=self.clock)
        self.assertEqual(result.inserted_count, 1)
        self.assertEqual(LatencyTrace.from_json(another['trace_json']).stamps['gateway_ingress'],
                         LatencyTrace.from_json(item['trace_json']).stamps['gateway_ingress'])
        self.assertEqual(another['deadline_epoch_ns'], item['deadline_epoch_ns'])
        self.clock.epoch += 26_000_000_000
        self.clock.mono += 26_000_000_000
        with self.assertRaises(ValueError): self.prepare()

    def test_delivery_identity_is_accepted_by_weekly_gate_with_original_signal(self):
        from qmt_roll_weekly19_execution import evaluate_intent
        item = self.prepare()
        result = evaluate_intent(item, self.context, now=NOW)
        self.assertTrue(result['allowed'], result)

    def test_warm_lease_keeps_weekly_business_direction_and_independent_request_enums(self):
        import run_qmt_roll_stage931_official_live_ctp_submit_adapter as execution
        from qmt_roll_weekly19_execution import evaluate_intent
        item = self.prepare()
        row, request = execution._stage179_spool_lease_row(SimpleNamespace(intent=SimpleNamespace(
            payload=item, intent_id=item['intent_id'])))
        self.assertEqual(row['direction'], item['direction'])
        self.assertEqual(row['offset'], item['offset'])
        self.assertEqual(request['direction'], execution.Direction.LONG.value)
        self.assertTrue(evaluate_intent(row, self.context, now=NOW)['allowed'])

    def test_two_quote_deliveries_cannot_open_the_same_native_signal_twice(self):
        first_item = self.prepare()
        connection = spool.open_spool(Path(self.temp.name) / 'duplicate.sqlite3')
        self.addCleanup(connection.close)
        weekly.commit_weekly19_quote_batch(connection, expected_cursor=None, next_cursor=self.cursor,
                                          intents=[first_item], clock=self.clock)
        previous = self.cursor
        self.clock.epoch += 1000000000
        self.clock.mono += 1000000000
        tick = SimpleNamespace(vt_symbol='rb2701.SHFE', symbol='rb2701', exchange='SHFE', datetime=NOW+timedelta(seconds=1),
                  last_price=4000.0, bid_price_1=3999.0, ask_price_1=4000.0, bid_volume_1=10, ask_volume_1=10)
        self.pipeline.capture_ingress(tick)
        self.assertTrue(self.pipeline.wait_until_durable(2, timeout_seconds=2))
        snapshot = self.pipeline.durable_snapshot()
        self.cursor = DurableTickCursor(snapshot.feed_session_id, snapshot.durable_ingress_sequence,
                                      snapshot.durable_journal_byte_offset, snapshot.journal_schema)
        second = self.prepare()
        self.assertNotEqual(first_item['intent_id'], second['intent_id'])
        with self.assertRaisesRegex(spool.SpoolConflictError, 'weekly19.*already'):
            weekly.commit_weekly19_quote_batch(connection, expected_cursor=previous, next_cursor=self.cursor,
                                              intents=[second], clock=self.clock)

    def test_spool_readback_rechecks_original_durable_quote_bytes(self):
        item = self.prepare()
        connection = spool.open_spool(Path(self.temp.name) / 'tamper.sqlite3')
        self.addCleanup(connection.close)
        weekly.commit_weekly19_quote_batch(connection, expected_cursor=None, next_cursor=self.cursor,
                                          intents=[item], clock=self.clock)
        raw = self.path.read_bytes()
        self.path.write_bytes(raw.replace(b'4000.0', b'3990.0', 1))
        with self.assertRaises(spool.SpoolValidationError):
            spool.snapshot_authorizable_intents(connection, now_epoch_ns=self.clock.epoch_ns(),
                now_monotonic_ns=self.clock.monotonic_ns(), clock_domain_id=self.clock.clock_domain_id(),
                execution_profile='weekly19-15w-r150k')
