"""New synthetic input contracts only; no real DB, model, cash or download."""
from datetime import date, timedelta
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import h5py
import numpy as np
import pandas as pd

SOURCE = Path(__file__).with_name('stage067_settlement_source_projection.py')
spec = importlib.util.spec_from_file_location('stage067_under_test', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def native(day='2020-01-21', epoch='SHFE.AG.202003', **changes):
    row = dict(contract_epoch_id=epoch, trade_date=day, open=100., high=102., low=98.,
               close=101., volume=10., quality_status='accepted', source_id='old_tq:SHFE.ag2003',
               source_family='old_tq', source_symbol='ag2003', source_locator='{"row":2}',
               source_path='fixture.csv', source_sha256='', source_bytes=0, volume_factor=1.,
               N=4., history_run=21)
    row.update(changes)
    return row


def candidate(row=None, **changes):
    row = row or native()
    value = dict(source_epoch=row['contract_epoch_id'], trade_date=row['trade_date'],
                 open=row['open'], high=row['high'], low=row['low'], close=row['close'],
                 volume=10., settlement=100., prev_settlement=99., field_present=True,
                 observation_state='row_found', source_id='fixture', source_family='rqalpha',
                 locator='{"key":"AG2003","row":20}', close_text='101', settlement_text='100',
                 print_state='float64_not_original_print_precision')
    value.update(changes)
    return value


def meta(epoch='SHFE.AG.202003', **changes):
    value = dict(contract_epoch_id=epoch, maturity_date='2020-03-16', de_listed_date='2020-03-16',
                 order_book_id='AG2003', exchange='SHFE', underlying_symbol='AG')
    value.update(changes)
    return value


class ProjectionContracts(unittest.TestCase):
    def test_exact_source_predecessor_and_query_epoch_survive(self):
        dates = ['2020-01-20', '2020-01-21', '2020-01-23']
        mother = pd.DataFrame([
            dict(sequence_index=0, event_id='a', product_id='SHFE.AG', family_id='SHFE.AG', u_date=dates[0], reference_epoch='SHFE.AG.202003'),
            dict(sequence_index=1, event_id='b', product_id='SHFE.AG', family_id='SHFE.AG', u_date=dates[1], reference_epoch='SHFE.AG.202004'),
            dict(sequence_index=2, event_id='c', product_id='DCE.L_F', family_id='DCE.L', u_date=dates[2], reference_epoch=''),
        ])
        prepared = m.prepare_mother(mother, dates, expected_rows=3)
        self.assertEqual(prepared.v_date.tolist(), ['', dates[0], dates[1]])
        self.assertEqual(prepared.reference_epoch.tolist(), mother.reference_epoch.tolist())
        self.assertEqual(len(prepared), 3)
        self.assertEqual(prepared.family_id.iloc[2], 'DCE.L')

    def test_labels_never_control_mother_or_coverage(self):
        frame = pd.DataFrame([dict(sequence_index=i, event_id=f'e{i}', product_id='DCE.L_F', family_id='DCE.L',
                                  u_date=f'2020-01-0{i+1}', reference_epoch='', label_state=x, net_R_stress=999)
                              for i, x in enumerate(['open', 'closed_complete_bar_model', 'unknown'])])
        prepared = m.prepare_mother(frame, frame.u_date.tolist(), expected_rows=3)
        self.assertNotIn('label_state', prepared)
        self.assertNotIn('net_R_stress', prepared)
        self.assertEqual(prepared.event_id.tolist(), ['e0', 'e1', 'e2'])
        rows = prepared.assign(projection_state=['missing_native_v'] * 3, value_observed=0,
                               ohlc_relation='not_compared', source_route='none', rule_state='unknown')
        coverage = m.coverage_table(rows)
        self.assertEqual(int(coverage.mother_rows.sum()), 3)
        self.assertEqual(int(coverage.value_observed.sum()), 0)

    def test_valid_equal_close_settlement_is_zero_gap(self):
        row = native()
        result = m.resolve_observation(row, candidate(row, settlement=101.), None, meta())
        self.assertEqual(result['projection_state'], 'observed_historical_reconstruction')
        self.assertEqual(result['close_minus_settlement_v'], 0.)
        self.assertEqual(result['value_observed'], 1)
        self.assertEqual(result['strict_pit_accepted'], 0)
        self.assertEqual(result['available_at'], '')

    def test_fallback_only_for_absent_column(self):
        row = native()
        absent = candidate(row, field_present=False, settlement=None)
        result = m.resolve_observation(row, absent, candidate(row, source_id='rqalpha'), meta())
        self.assertEqual(result['source_route'], 'rq_fallback_after_absent_original_column')
        self.assertEqual(result['value_observed'], 1)
        for bad in [0., float('nan'), None]:
            with self.subTest(bad=bad):
                result = m.resolve_observation(row, candidate(row, settlement=bad), candidate(row, settlement=100.), meta())
                self.assertEqual(result['projection_state'], 'settlement_nonfinite_or_nonpositive')
                self.assertNotEqual(result['value_observed'], 1)
                self.assertEqual(result['source_route'], 'accepted_source_locator')

    def test_original_conflict_and_missing_locator_are_absorbing(self):
        row = native()
        good = candidate(row)
        for bad in [candidate(row, close=101.001, field_present=False),
                    candidate(row, observation_state='locator_row_missing', field_present=False)]:
            result = m.resolve_observation(row, bad, good, meta())
            self.assertEqual(result['value_observed'], 0)
            self.assertNotEqual(result['source_route'], 'rq_fallback_after_absent_original_column')
            if bad['observation_state'] == 'row_found':
                self.assertEqual(result['S_v'], 100.)

    def test_full_epoch_and_exact_date_not_short_symbol(self):
        row = native()
        for bad in [candidate(row, source_epoch='SHFE.AG.203003'), candidate(row, trade_date='2020-01-20')]:
            result = m.resolve_observation(row, bad, candidate(row), meta())
            self.assertEqual(result['projection_state'], 'source_identity_or_date_conflict')
            self.assertEqual(result['value_observed'], 0)

    def test_no_trade_nonfinite_and_range_conflicts_keep_unknown(self):
        row = native()
        expected = [(candidate(row, volume=0.), 'source_no_trade'),
                    (candidate(row, close=float('nan')), 'source_ohlc_conflict'),
                    (candidate(row, settlement=102.1), 'settlement_outside_native_range')]
        for source, state in expected:
            with self.subTest(state=state):
                self.assertEqual(m.resolve_observation(row, source, None, meta())['projection_state'], state)

    def test_final_date_and_unknown_rule_keep_values_without_feature_qualification(self):
        row = native()
        final = m.resolve_observation(row, candidate(row), None, meta(maturity_date=row['trade_date']))
        self.assertEqual(final['projection_state'], 'final_delivery_or_definition_unknown')
        self.assertEqual(final['S_v'], 100.)
        unknown = native(epoch='X.A.202003')
        value = m.resolve_observation(unknown, candidate(unknown), None, meta(epoch=unknown['contract_epoch_id']))
        self.assertEqual(value['projection_state'], 'rule_family_unknown')
        self.assertEqual(value['value_observed'], 0)

    def test_projected_observation_is_never_a_training_mask(self):
        row = native(N=float('nan'), history_run=3)
        result = m.resolve_observation(row, candidate(row), None, meta())
        self.assertEqual(result['value_observed'], 1)
        self.assertEqual(result['N_state'], 'N_v_not_ready20')
        self.assertEqual(result['feature_available'], 0)
        self.assertEqual(result['feature_state'], 'N_v_not_ready20')
        row = native(epoch='DCE.M.202003')
        result = m.resolve_observation(row, candidate(row), None, meta(epoch=row['contract_epoch_id']))
        self.assertEqual(result['rule_primary_bound'], 0)
        self.assertEqual(result['feature_available'], 0)
        self.assertEqual(result['feature_state'], 'primary_rule_evidence_not_bound')

    def test_cffex_day_and_delivery_rules_are_distinct(self):
        equity = m.rule_annotation('CFFEX.IF.202612', '2026-09-30', {})
        bond = m.rule_annotation('CFFEX.T.202612', '2026-09-30', {})
        self.assertEqual(equity['benchmark_family'], 'cffex_index_last_hour_daily')
        self.assertEqual(bond['benchmark_family'], 'cffex_bond_last_hour_daily')
        self.assertEqual(equity['expected_print_decimals'], '1')
        self.assertEqual(bond['expected_print_decimals'], '3')
        self.assertNotEqual(equity['final_delivery_definition'], bond['final_delivery_definition'])

    def test_native_atr_is_v_only_and_gaps_reset(self):
        dates = [(date(2020, 1, 1) + timedelta(days=i)).isoformat() for i in range(23)]
        records = [native(day=d, open=100., high=102., low=98., close=100., N=None) for d in dates]
        records[-1].update(open=1000., high=1100., low=900., close=1000.)
        wanted = {('SHFE.AG.202003', dates[20])}
        projected, receipt = m.build_native_projection(records, dates, wanted)
        self.assertEqual(projected[next(iter(wanted))]['N'], 4.)
        self.assertEqual(receipt['native_contract_days'], 23)
        records.pop(10)
        projected, _ = m.build_native_projection(records, dates, wanted)
        self.assertTrue(np.isnan(projected[next(iter(wanted))]['N']))

    def test_metadata_mapping_retains_f_and_century(self):
        entries = [dict(order_book_id='L2601F', exchange='DCE', underlying_symbol='L_F', maturity_date='2025-12-31', de_listed_date='2025-12-31'),
                   dict(order_book_id='CF1505', exchange='CZCE', underlying_symbol='CF', maturity_date='2015-05-15', de_listed_date='2015-05-15')]
        values = m.metadata_index(entries)
        self.assertEqual(values['DCE.L_F.202601']['order_book_id'], 'L2601F')
        self.assertIn('CZCE.CF.201505', values)

    def test_project_all_rows_missing_native_and_no_reference(self):
        dates = ['2020-01-20', '2020-01-21', '2020-01-22']
        frame = pd.DataFrame([dict(sequence_index=i, event_id=f'e{i}', product_id='SHFE.AG', family_id='SHFE.AG',
                                  u_date=d, reference_epoch='SHFE.AG.202003' if i < 2 else '') for i, d in enumerate(dates)])
        prepared = m.prepare_mother(frame, dates, expected_rows=3)
        values = m.project_mother(prepared, {}, {}, {}, {})
        self.assertEqual(len(values), 3)
        self.assertEqual(values.projection_state.tolist(), ['no_previous_source_day', 'missing_native_v', 'no_reference_epoch'])
        self.assertEqual(values.sequence_index.tolist(), [0, 1, 2])


class SourceReaderContracts(unittest.TestCase):
    def test_csv_exact_locator_and_print_text_and_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'official.csv.gz'
            with gzip.open(path, 'wt', newline='') as stream:
                stream.write('exchange,product,contract_yyyymm,date,open,high,low,close,volume,settle,pre_settle,source_member,source_row\n')
                stream.write('SHFE,ag,202003,2020-01-21,100,102,98,101.00,10,100.00,99,old.xls,8\n')
            row = native(source_family='official', source_id='official:fixture', source_path=str(path),
                         source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         source_locator='{"row":2,"source_member":"old.xls","raw_row":"8"}')
            reader = m.SourceReader({}, None, None)
            sources = reader.read_originals({(row['contract_epoch_id'], row['trade_date']): row})
            result = next(iter(sources.values()))
            self.assertEqual(result['settlement_text'], '100.00')
            self.assertEqual(result['source_epoch'], 'SHFE.AG.202003')
            row['source_locator'] = '{"row":3}'
            missing = next(iter(reader.read_originals({(row['contract_epoch_id'], row['trade_date']): row}).values()))
            self.assertEqual(missing['observation_state'], 'locator_row_missing')

    def test_tq_absent_column_still_validates_original_row_date(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'tq.csv'
            path.write_text('trade_date,open,high,low,close,volume\n2020-01-20,100,102,98,101,10\n')
            row = native(source_path=str(path), source_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            reader = m.SourceReader({}, None, None)
            value = next(iter(reader.read_originals({(row['contract_epoch_id'], row['trade_date']): row}).values()))
            self.assertFalse(value['field_present'])
            self.assertEqual(value['trade_date'], '2020-01-20')
            self.assertEqual(m.resolve_observation(row, value, candidate(row), meta())['value_observed'], 0)

    def test_h5_fallback_exact_date_and_duplicate_date_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'futures.h5'
            dtype = [('datetime', 'i8')] + [(k, 'f8') for k in ['open', 'high', 'low', 'close', 'volume', 'settlement', 'prev_settlement']]
            data = np.array([(20200120000000, 100., 102., 98., 101., 10., 100., 99.),
                             (20200121000000, 100., 102., 98., 101., 10., 100., 99.),
                             (20200121000000, 100., 102., 98., 101., 10., 100., 99.)], dtype=dtype)
            with h5py.File(path, 'w') as store:
                store.create_dataset('AG2003', data=data)
            reader = m.SourceReader({'SHFE.AG.202003': meta()}, path, m.stat_binding(path))
            row = native()
            values = reader.read_fallbacks({(row['contract_epoch_id'], row['trade_date']): row})
            self.assertEqual(next(iter(values.values()))['observation_state'], 'duplicate_source_epoch_day')
            row['trade_date'] = '2020-01-22'
            values = reader.read_fallbacks({(row['contract_epoch_id'], row['trade_date']): row})
            self.assertEqual(next(iter(values.values()))['observation_state'], 'source_date_missing')

    def test_actual_cli_hash_guard_precedes_input_or_sql_reads(self):
        with patch.object(m, 'run_actual', side_effect=AssertionError('actual must not run')):
            with self.assertRaisesRegex(ValueError, 'authorization'):
                m.main(['--protocol', '/absent', '--protocol-sha256', 'bad', '--output', '/absent',
                        '--authorize-source-sha256', 'wrong'])

    def test_fractional_csv_locator_never_truncates_to_real_row(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'tq.csv'
            path.write_text('trade_date,open,high,low,close,volume\n2020-01-21,100,102,98,101,10\n')
            row = native(source_path=str(path), source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         source_locator='{"row":2.5}')
            value = next(iter(m.SourceReader({}, None, None).read_originals({(row['contract_epoch_id'], row['trade_date']): row}).values()))
            self.assertEqual(value['observation_state'], 'accepted_locator_unparseable')

    def test_native_loader_has_one_ro_select_without_schema_probe(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'not_a_database.fixture'
            path.write_bytes(b'no sqlite engine is used in this test')
            binding = dict(m.stat_binding(path), sha256='inherited_not_rehashed')
            row = native(day='2020-01-21')
            values = tuple(row.get(k) for k in m.NATIVE_COLUMNS)
            calls = []

            class FakeDatabase:
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def execute(self, sql, params):
                    calls.append((sql, params))
                    return iter([values])

            with patch.object(m.sqlite3, 'connect', return_value=FakeDatabase()) as connect:
                result, receipt = m.read_native_once(binding, ['2020-01-21'], {(row['contract_epoch_id'], row['trade_date'])},
                                                     '2020-01-21', '2020-01-21')
            self.assertEqual(len(calls), 1)
            self.assertTrue(calls[0][0].lstrip().startswith('SELECT'))
            self.assertIn('mode=ro&immutable=1', connect.call_args.args[0])
            self.assertEqual(receipt['native_source_queries'], 1)
            self.assertEqual(len(result), 1)

    def test_h5_original_hash_binding_disagreement_is_not_a_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'futures.h5'
            with h5py.File(path, 'w') as store:
                store.create_dataset('AG2003', data=np.zeros(1, dtype=[('datetime', 'i8')]))
            binding = dict(m.stat_binding(path), sha256='frozen_rq_sha')
            reader = m.SourceReader({'SHFE.AG.202003': meta()}, path, binding)
            row = native(source_family='rqalpha', source_path=str(path), source_id='rqalpha',
                         source_sha256='different_accepted_rq_sha', source_locator='{"key":"AG2003","row":0}')
            result = reader.read_originals({(row['contract_epoch_id'], row['trade_date']): row})
            self.assertEqual(next(iter(result.values()))['observation_state'], 'accepted_h5_content_identity_conflict')

    def test_direct_actual_entry_requires_authorization_before_output_or_sql(self):
        with patch.object(m.sqlite3, 'connect', side_effect=AssertionError('no SQL before authorization')):
            with tempfile.TemporaryDirectory() as folder:
                output = Path(folder) / 'must_not_exist'
                with self.assertRaisesRegex(ValueError, 'authorization'):
                    m.run_actual(b'{}', output)
                self.assertFalse(output.exists())

    def test_h5_malformed_original_locator_stays_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'futures.h5'
            with h5py.File(path, 'w') as store:
                store.create_dataset('AG2003', data=np.zeros(1, dtype=[('datetime', 'i8')]))
            binding = dict(m.stat_binding(path), sha256='same')
            row = native(source_family='rqalpha', source_path=str(path), source_id='rqalpha', source_sha256='same',
                         source_bytes=binding['bytes'], source_locator='{"key":"AG2003","row":"bad"}')
            reader = m.SourceReader({'SHFE.AG.202003': meta()}, path, binding)
            value = next(iter(reader.read_originals({(row['contract_epoch_id'], row['trade_date']): row}).values()))
            self.assertEqual(value['observation_state'], 'accepted_locator_unparseable')


if __name__ == '__main__':
    unittest.main()
