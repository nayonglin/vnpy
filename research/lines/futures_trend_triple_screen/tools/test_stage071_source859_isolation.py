"""Three bounded Stage071 contract tests; no replay, model, provider or orders.

Receipt wrappers below are TEST FIXTURES for new gate-generated identities.
They are never independent market-data signatures or engine response pointers.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
OUT = LINE / 'outputs/stage075_source859_isolation_implementation'
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(TOOLS))
import stage022_run_c0_qualified_wait as runtime

original_output = runtime.OUTPUT
try:
    runtime.OUTPUT = OUT
    runtime.configure_runtime(Path(tempfile.mkdtemp(prefix='shared_', dir=OUT)))
finally:
    runtime.OUTPUT = original_output

import numpy as np
import pandas as pd
import stage002_local_minute_overlay as old
import stage021_blocking_data_gate as gate
import stage061_accepted_wait_delta as accepted

PHASE = os.environ.get('STAGE075_PHASE', 'manual')
RUN = Path(tempfile.mkdtemp(prefix=PHASE + '_', dir=OUT))
SOURCE = TOOLS / 'stage071_source859_isolation.py'
if SOURCE.exists():
    import stage071_source859_isolation as isolation
else:
    # Behavioral RED represents the unmodified preload policy, not an import error.
    @contextmanager
    def legacy_context(s901, completed_value_keys, audit):
        yield
    isolation = SimpleNamespace(
        isolate_unqualified_source859=lambda frame, keys: (frame.copy(), {'removed_source859_rows': 0}),
        temporary_source859_isolation=legacy_context,
    )

SOURCE859 = 'stage859_tqsdk_backtest'
PINS = {
    LINE / 'stages/20261018_0609_stage071_source859_preload_isolation_contract.md':
        'e31f66d17fb61bf940731556fdc5f5815a3df42f915f1bccbf27718b0b58a493',
    TOOLS / 'stage021_blocking_data_gate.py':
        '150dd70a264f360046f6d633829a4dff9a81c371c34bad6288e41a081bbb498b',
    LINE / 'outputs/stage066_fu2209_conflict_diagnostic/evidence.json':
        '2a92f959bef508d0b893579aa763490e2c2dcfdc4ed0c4c56c09bbf67d42597b',
    LINE / 'outputs/stage014_conflict_consumption_diagnostic/A0_actual_read_source_distribution.json':
        '7f06df100b2c9b132991d8cbd956f52d5bf373266b40a9dfc4d6d0f494be79f0',
}
DIGEST = '6873f0a1930106a91bb35355efbf2e9843ddcd9f05aa3ebf1ebf105806ab3730'
REQUEST = LINE / f'outputs/stage036_b_ts_account/B_TS/data_wait/request_{DIGEST}/request.json'
RECEIPT = LINE / f'outputs/stage052_generic_daily_source_resolver/request_{DIGEST}/delivery_receipt.json'
DATA = RECEIPT.with_name('delivery_minutes.csv')
PINS.update({
    REQUEST: 'b991fd05fb55f2e39309d2261a2ef0f753e72f4a7fd7a27c189176972fb558e4',
    RECEIPT: '274190b95b9c1ff18cdee2743730ddec0a89b6ad4f035e108f69f269701327bf',
    DATA: '7e41b88df89143f1205f83e53280c9b84f23ff15ce06309aac698e7b70ddec22',
})


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def frame_for(symbol, stamps, sources):
    return pd.DataFrame([
        dict(vt_symbol=symbol, bar_datetime=stamp, open=100., high=102., low=99.,
             close=101., volume=4., open_oi=10., close_oi=11., minute_source=source,
             extra=f'preserve_{i}')
        for i, (stamp, source) in enumerate(zip(stamps, sources))
    ])


class TestSource859Isolation(unittest.TestCase):
    def test_only_unproven859_removed_anchor_rights_not_promoted(self):
        calendar = pd.DatetimeIndex(['2022-05-30', '2022-05-31'])
        symbol = 'fu2209.SHFE'
        stamps = old.session_grid(symbol, '2022-05-31', calendar)[:6]
        frame = frame_for(symbol, stamps, [SOURCE859, SOURCE859, SOURCE859,
            'stage016_completed_correction', 'stage249_completed_trading_day_fragment',
            'stage061_accepted_wait_delta'])
        other = 'rb2210.SHFE'
        other_first = old.session_grid(other, '2022-05-31', calendar)[0]
        frame = pd.concat([frame, frame_for(other, [other_first], [SOURCE859])], ignore_index=True)
        snapshot = frame.copy(deep=True)
        completed = {(symbol, stamps[0]), (symbol, stamps[1]), (symbol, stamps[5])}
        result, audit = isolation.isolate_unqualified_source859(frame, completed)
        self.assertEqual(len(result), 5)
        self.assertEqual(audit['removed_source859_rows'], 2)
        self.assertEqual(audit['retained_source859_rows'], 2)
        self.assertEqual(audit['retained_non859_rows'], 3)
        pd.testing.assert_frame_equal(frame, snapshot)
        pd.testing.assert_frame_equal(result, snapshot.drop(index=[2, 6]))
        demand = pd.DataFrame([
            dict(vt_symbol=s, execution_trade_date='2022-05-31', requirement_kind='anchor')
            for s in (symbol, other)
        ])
        full, anchor, inherited = runtime.inherited_qualification_predicates(
            {symbol: result}, {(symbol, stamps[1])}, demand, calendar)
        new_anchor = frozenset({(symbol, stamps[5])})
        delta = accepted.FrozenDelta(result.loc[result.bar_datetime.eq(stamps[5])],
            frozenset(), new_anchor, {}, {'fixture_only': True})
        full, anchor = accepted.compose_qualification(full, anchor, new_anchor, delta)
        for stamp in (stamps[0], stamps[5]):
            self.assertTrue(anchor(symbol, stamp))
            self.assertFalse(full(symbol, stamp))
        self.assertTrue(full(symbol, stamps[1]))
        self.assertFalse(anchor(other, other_first))  # old demand alone is no completion proof
        for bad in (frame.drop(columns='close_oi'),
                    pd.concat([frame, frame.iloc[:1]], ignore_index=True),
                    frame.assign(bar_datetime=pd.NaT)):
            with self.subTest(invalid='columns_key_or_duplicate'):
                with self.assertRaises((ValueError, TypeError)):
                    isolation.isolate_unqualified_source859(bad, completed)
        with self.assertRaises((ValueError, TypeError)):
            isolation.isolate_unqualified_source859(frame, {('', stamps[0])})
        aware = frame.copy()
        aware['bar_datetime'] = aware.bar_datetime.dt.tz_localize('Asia/Shanghai').dt.tz_convert('UTC')
        normalized, _ = isolation.isolate_unqualified_source859(aware, completed)
        pd.testing.assert_frame_equal(normalized, result)
        write(RUN / 'tiny_contract.json', dict(filter=audit, inherited=inherited,
            retained_completed_anchor_full=False, new061_anchor_full=False,
            demand_only_unproven_anchor_removed=True, input_unchanged=True))

    def test_real_fu_projection_true021_replacement_and_retained_conflict(self):
        for path, expected in PINS.items():
            self.assertEqual(sha(path), expected, str(path))
        request = json.loads(REQUEST.read_text())
        receipt = json.loads(RECEIPT.read_text())
        complete, full, anchor, _ = gate._read_delivery(request, gate.QualifiedDelivery(RECEIPT, sha(RECEIPT)))
        self.assertEqual((len(complete), len(full), len(anchor)), (345, 345, 0))
        evidence = json.loads((LINE / 'outputs/stage066_fu2209_conflict_diagnostic/evidence.json').read_text())
        existing_stamps = pd.to_datetime(request['requirements'][0]['existing_source_timestamps'])
        projection = complete.loc[complete.bar_datetime.isin(existing_stamps)].copy()
        self.assertEqual(len(projection), 226)
        projection['minute_source'] = 'stage249_completed_trading_day_fragment'
        projection = projection.set_index('bar_datetime', drop=False)
        changed_stamps = set()
        for item in evidence['differences']:
            stamp = pd.Timestamp(item['bar_datetime'])
            self.assertEqual(float(projection.loc[stamp, item['field']]), float(item['new']))
            projection.loc[stamp, item['field']] = item['old']
            projection.loc[stamp, 'minute_source'] = item['old_source']
            changed_stamps.add(stamp)
        projection = projection.reset_index(drop=True)
        self.assertEqual(len(changed_stamps), 225)
        self.assertEqual(int(projection.minute_source.eq(SOURCE859).sum()), 225)
        proof = set()  # no new completion proof for old859; retained249 is not deleted
        isolated, filter_audit = isolation.isolate_unqualified_source859(projection, proof)
        projection.to_csv(RUN / 'fu226_evidence_reconstruction.csv', index=False)
        cases = []

        class Engine:
            def _stage827_order_context(self, order, bar):
                return None

        def exercise(name, physical, should_pass):
            case_dir = RUN / name
            case_dir.mkdir()
            order = SimpleNamespace(vt_orderid='FIXTURE.OPEN.1', vt_symbol='fu2209.SHFE',
                offset=SimpleNamespace(name='OPEN'))
            bar = object()
            engine = Engine()
            engine.datetime = pd.Timestamp('2022-05-31')
            engine.active_limit_orders = {order.vt_orderid: order}
            engine.bars = {order.vt_symbol: bar}
            original_mapping = {order.vt_symbol: physical.copy(deep=True)}
            engine.strategy = SimpleNamespace(stage827_minute_by_symbol=original_mapping,
                available_trade_dates=pd.DatetimeIndex(['2022-05-30', '2022-05-31']))
            common = {(order.vt_symbol, stamp) for stamp in physical.loc[
                physical.minute_source.eq('stage249_completed_trading_day_fragment'), 'bar_datetime']}
            audit = []
            generated = []

            def resolver(actual_request):
                generated.append(deepcopy(actual_request))
                write(case_dir / 'actual_gate_generated_request.json', actual_request)
                wrapper = deepcopy(receipt)
                wrapper.update(request_sha256=actual_request['request_sha256'], fixture_only=True,
                    reviewer='TEST_FIXTURE_ONLY_REBIND_OF_PINNED_STAGE052',
                    origin_request_path=str(REQUEST), origin_request_sha256=sha(REQUEST),
                    origin_receipt_path=str(RECEIPT), origin_receipt_sha256=sha(RECEIPT),
                    fixture_scope='unit mechanism only; no new independent market-data qualification',
                    response_written=False)
                wrapped = case_dir / 'fixture_only_receipt_wrapper.json'
                write(wrapped, wrapper)
                return gate.QualifiedDelivery(wrapped, sha(wrapped))

            with gate.qualified_wait_scope(Engine, resolver, audit, qualified_existing_keys=common) as real_gate:
                if should_pass:
                    real_gate.ensure(engine, order, bar)
                    loaded = engine.strategy.stage827_minute_by_symbol[order.vt_symbol]
                    self.assertEqual(len(loaded), 345)
                    self.assertEqual(len(real_gate.dynamic_full), 345)
                    self.assertFalse(real_gate.requirements(engine, order, bar)[0])
                    pd.testing.assert_frame_equal(
                        loaded.sort_values('bar_datetime')[gate.FIELDS].reset_index(drop=True),
                        complete.sort_values('bar_datetime').reset_index(drop=True))
                    appended = [row for row in audit if row['event'] == 'data_qualified_appended']
                    self.assertEqual(appended[0]['appended_keys'], 344)
                    self.assertEqual(appended[0]['old_keys_changed'], 0)
                else:
                    with self.assertRaisesRegex(ValueError, 'qualified_delivery_old_value_conflict'):
                        real_gate.ensure(engine, order, bar)
                    pd.testing.assert_frame_equal(engine.strategy.stage827_minute_by_symbol[order.vt_symbol], physical)
                    self.assertFalse(real_gate.dynamic_full)
                    self.assertFalse(any(row['event'] == 'data_qualified_appended' for row in audit))
            self.assertIs(engine.strategy.stage827_minute_by_symbol, original_mapping)
            self.assertEqual(len(generated), 1)
            self.assertEqual(generated[0]['request_sha256'], gate.request_sha256(generated[0]))
            self.assertNotEqual(generated[0]['request_sha256'], request['request_sha256'])
            result = dict(case=name, actual_generated_request_sha256=generated[0]['request_sha256'],
                physical_existing=len(physical), expected_pass=should_pass, audit=audit,
                fixture_only=True, root_terminal_signed=False, response_written=False)
            write(case_dir / 'evidence.json', result)
            cases.append(result)

        exercise('old_policy_conflict', projection, False)
        self.assertEqual(len(isolated), 1)
        exercise('new_policy_append344', isolated, True)
        conflict = isolated.copy(deep=True)
        conflict.loc[conflict.index[0], 'high'] += 1
        exercise('retained249_conflict', conflict, False)
        for path, expected in PINS.items():
            self.assertEqual(sha(path), expected, str(path))
        write(RUN / 'fu_true021_contract.json', dict(
            reconstruction='pinned Stage066 differences + pinned completed345 CSV + original request existing226',
            dead_engine_RAM_read=False, base_full_csv_reread=False, original_request_parser_keys=len(complete),
            filter=filter_audit, cases=cases, source_fingerprints={str(p): h for p, h in PINS.items()},
            A0_source_distribution_only_reused=True, financial_replays=0, model_fits=0, orders=0))

    def test_context_normal_and_exception_restore_exact_cache_objects(self):
        frame = frame_for('fu2209.SHFE', pd.date_range('2022-05-31 09:00', periods=2, freq='min'),
            [SOURCE859, 'stage249_completed_trading_day_fragment'])
        original_frame = frame.copy(deep=True)
        cache = {'sentinel': object()}
        symbols = {'ORIGINAL'}
        original_audit = {'sentinel': ['unchanged']}
        s901 = SimpleNamespace(_FULL_MINUTE_BY_SYMBOL_CACHE=cache,
            _FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS=symbols, _LAST_MINUTE_AUDIT=original_audit)
        def loader(requested):
            return frame
        s901._load_stage861_full_minute_bars = loader
        audit = []
        with isolation.temporary_source859_isolation(s901, set(), audit):
            self.assertIsNone(s901._FULL_MINUTE_BY_SYMBOL_CACHE)
            self.assertEqual(s901._FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS, set())
            self.assertIsNot(s901._LAST_MINUTE_AUDIT, original_audit)
            filtered = s901._load_stage861_full_minute_bars({'fu2209.SHFE'})
            self.assertEqual(len(filtered), 1)
            s901._FULL_MINUTE_BY_SYMBOL_CACHE = {'fu2209.SHFE': filtered}
            s901._FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS = {'fu2209.SHFE'}
            s901._LAST_MINUTE_AUDIT['inside'] = True
        for name, expected in [('_FULL_MINUTE_BY_SYMBOL_CACHE', cache),
                ('_FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS', symbols), ('_LAST_MINUTE_AUDIT', original_audit),
                ('_load_stage861_full_minute_bars', loader)]:
            self.assertIs(getattr(s901, name), expected)
        self.assertEqual(original_audit, {'sentinel': ['unchanged']})
        self.assertEqual(len(audit), 1)
        successful_audit = deepcopy(audit)
        with self.assertRaisesRegex(RuntimeError, 'body_failed'):
            with isolation.temporary_source859_isolation(s901, set(), audit):
                s901._load_stage861_full_minute_bars({'fu2209.SHFE'})
                raise RuntimeError('body_failed')
        self.assertEqual(audit, successful_audit)

        def failing_loader(requested):
            s901._FULL_MINUTE_BY_SYMBOL_CACHE = {'pollution': True}
            s901._FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS = {'pollution'}
            s901._LAST_MINUTE_AUDIT = {'pollution': True}
            raise RuntimeError('loader_failed')
        s901._load_stage861_full_minute_bars = failing_loader
        with isolation.temporary_source859_isolation(s901, set(), audit):
            before = tuple(getattr(s901, name) for name in (
                '_FULL_MINUTE_BY_SYMBOL_CACHE', '_FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS', '_LAST_MINUTE_AUDIT'))
            with self.assertRaisesRegex(RuntimeError, 'loader_failed'):
                s901._load_stage861_full_minute_bars({'fu2209.SHFE'})
            for name, expected in zip(('_FULL_MINUTE_BY_SYMBOL_CACHE',
                    '_FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS', '_LAST_MINUTE_AUDIT'), before):
                self.assertIs(getattr(s901, name), expected)
        self.assertIs(s901._load_stage861_full_minute_bars, failing_loader)
        self.assertIs(s901._FULL_MINUTE_BY_SYMBOL_CACHE, cache)
        self.assertIs(s901._FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS, symbols)
        self.assertIs(s901._LAST_MINUTE_AUDIT, original_audit)
        self.assertEqual(audit, successful_audit)
        pd.testing.assert_frame_equal(frame, original_frame)
        write(RUN / 'context_contract.json', dict(normal_and_exception_object_identity_restored=True,
            body_failure_audit_rolled_back=True, loader_failure_cache_and_audit_rolled_back=True,
            successful_filter_audit=successful_audit))


if __name__ == '__main__':
    print('STAGE075_EVIDENCE_DIR=' + str(RUN), flush=True)
    unittest.main(verbosity=2)
