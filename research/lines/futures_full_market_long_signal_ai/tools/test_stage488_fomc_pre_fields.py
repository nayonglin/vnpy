"""Four new pure boundary contracts; no actual inputs, SQL, market files or fits."""
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name('stage488_fomc_pre_fields.py')
spec = importlib.util.spec_from_file_location('stage488_under_test', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
resolver = m.load_resolver()


def inputs(**native_changes):
    request = dict(raw_request_id='request0', reference_epoch='SHFE.AG.202003', pre_date='2020-01-21',
                   pre_observed_any_epoch='1', requestable='1', child_link_count='1', event_count='1', product_aliases='["SHFE.AG"]')
    native = dict(contract_epoch_id=request['reference_epoch'], trade_date=request['pre_date'],
                  open=100., high=102., low=98., close=101., volume=10., native_volume=20., volume_factor=.5,
                  quality_status='accepted', source_id='old_tq:SHFE.ag2003', source_family='old_tq',
                  source_symbol='ag2003', source_locator='{"row":2}', source_path='fixture.csv',
                  source_sha256='fixture', source_bytes=0, N=math.nan, history_run=0)
    native.update(native_changes)
    primary = dict(source_epoch=native['contract_epoch_id'], trade_date=native['trade_date'],
                   open=100., high=102., low=98., close=101., volume=native['native_volume'],
                   settlement=100., prev_settlement=99., field_present=True, observation_state='row_found',
                   source_id=native['source_id'], source_family='old_tq', locator='{"row":2}',
                   close_text='101.00', settlement_text='100.00', print_state='source_csv_field_text_preserved')
    metadata = dict(economics_status='exact_epoch_metadata_snapshot', exchange='SHFE', underlying_symbol='AG',
                    order_book_id='AG2003', maturity_date='2020-03-16', de_listed_date='2020-03-16',
                    contract_multiplier=10., currency='CNY', currency_source='fixed_domestic_research_assumption',
                    historical_broker_specification_qualified=False)
    return request, native, primary, metadata


class ExactSourceBoundary(unittest.TestCase):
    def test_csv_budget_cannot_exceed_exact_request_count(self):
        budget = dict(starts_max=1, retries=0, requests_reads_max=1, economic_projection_reads_max=1,
                      native_selects_max=1, CSV_unique_physical_file_reads_max=2,
                      CSV_total_physical_bytes_max=1024**3, CSV_each_physical_path_reads_max=1,
                      H5_readonly_opens_max=2, whole_database_H5_rehashes=0, downloads=0,
                      old_full_mother_action_streams=0)
        protocol = dict(schema='stage487_fomc_residual_protocol_v1',
                        source_fields=dict(inputs={}, budget=budget, contract=dict(requests_rows=2)))
        # Only authorization is bypassed for this synthetic boundary. An already
        # existing output stops before mkdir or any real input read/SQL/reader.
        with tempfile.TemporaryDirectory() as folder, patch.object(m, 'verify_authorization', return_value=None):
            with self.assertRaisesRegex(ValueError, 'field output exists'):
                m.project_fields(protocol, folder, authorization={})
            budget['CSV_unique_physical_file_reads_max'] = 3
            with self.assertRaisesRegex(ValueError, 'source budget differs'):
                m.project_fields(protocol, folder, authorization={})

    def test_clean_single_sided_volume_is_not_halved_twice(self):
        request, native, primary, metadata = inputs()
        got = m.resolve_numeric_record(request, native, primary, None, metadata, resolver)
        self.assertEqual(got['pre_volume'], 10.)
        self.assertEqual(got['native_volume'], 20.)
        self.assertEqual(got['volume_factor'], .5)
        self.assertEqual(got['numeric_notional'], 10000.)

    def test_zero_volume_preserved_without_log_or_training_claim(self):
        request, native, primary, metadata = inputs(volume=0., native_volume=0.)
        got = m.resolve_numeric_record(request, native, primary, None, metadata, resolver)
        self.assertEqual(got['pre_volume'], 0.)
        self.assertEqual(got['numeric_notional'], 0.)
        self.assertTrue(got['source_numerically_verified'])
        self.assertIsNone(got['log_turnover_source_verified'])
        self.assertEqual(got['inherited067_value_observed'], 0)

    def test_only_absent_original_column_uses_fixed_fallback(self):
        request, native, primary, metadata = inputs()
        primary.update(field_present=False, settlement=None, settlement_text='')
        fallback = dict(primary, field_present=True, settlement=99.5, settlement_text='99.5', source_id='rqalpha', source_family='rqalpha')
        got = m.resolve_numeric_record(request, native, primary, fallback, metadata, resolver)
        self.assertEqual(got['source_route'], 'rq_fallback_after_absent_original_column')
        self.assertEqual(got['pre_settlement_source_verified'], 99.5)
        self.assertEqual(got['raw_request_id'], request['raw_request_id'])

    def test_bad_value_or_ohlc_never_rescues_from_other_source(self):
        request, native, primary, metadata = inputs()
        fallback = dict(primary, settlement=99.5, source_id='rqalpha', source_family='rqalpha')
        for changes in [dict(settlement=math.nan), dict(settlement=0.), dict(settlement=103.),
                        dict(field_present=False, close=101.001), dict(field_present=False, observation_state='locator_row_missing')]:
            with self.subTest(changes=changes):
                got = m.resolve_numeric_record(request, native, dict(primary, **changes), fallback, metadata, resolver)
                self.assertEqual(got['source_route'], 'accepted_source_locator')
                self.assertIsNone(got['pre_settlement_source_verified'])
                self.assertFalse(got['source_numerically_verified'])


if __name__ == '__main__':
    unittest.main()
