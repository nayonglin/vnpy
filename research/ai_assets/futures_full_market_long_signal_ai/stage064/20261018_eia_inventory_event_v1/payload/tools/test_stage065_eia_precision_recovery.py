"""New precision-recovery behavior, using real rejected EIA strings and finite cases."""
from pathlib import Path
import csv
import hashlib
import importlib.util
import io
import tempfile
import unittest

import pandas as pd

SOURCE = Path(__file__).with_name('stage065_eia_precision_recovery.py')
spec = importlib.util.spec_from_file_location('stage065_subject', SOURCE) if SOURCE.exists() else None
m = importlib.util.module_from_spec(spec) if spec else None
if m is not None:
    spec.loader.exec_module(m)
LINE = SOURCE.parents[1]
RAW = LINE / 'outputs/stage060_eia_report_import/excluded_raw_sources'
LABELS = ('Commercial (Excluding SPR)', 'Total Motor Gasoline', 'Distillate Fuel Oil')


def rep(rid='eia_wpsr_2020_03_04', ending='2020-02-28', release='2020-03-04'):
    return dict(report_id=rid, data_ending_expected=ending, release_date=release,
                issue_url='https://www.eia.gov/petroleum/supply/weekly/archive/2020/2020_03_04/wpsr.php',
                table1_url='https://www.eia.gov/petroleum/supply/weekly/archive/2020/2020_03_04/csv/table1.csv')


def table(current='100.000', prior='99.900', delta='0.101'):
    text = '"STUB_1","2/28/20","2/21/20","Difference","Percent Change"\n'
    for label in LABELS:
        text += f'"{label}","{current}","{prior}","{delta}","0"\n'
    return text.encode()


class PrecisionRecoveryBehavior(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(m, 'Stage065 precision recovery is not implemented')

    def test_real_three_decimal_case_preserves_published_difference(self):
        content = (RAW/'eia_wpsr_2020_03_04.csv').read_bytes()
        rows, audits = m.parse_rounded_table1(content, rep())
        self.assertEqual([x['current'] for x in rows], [444119.,252048.,134464.])
        # Commercial current-prior=784; the official weekly Difference is785.
        self.assertEqual([x['delta'] for x in rows], [785.,-4340.,-4008.])
        self.assertEqual([x['residual_native'] for x in audits], ['-0.001','0.001','0.000'])
        self.assertTrue(all(x['rounding_bound_native']=='0.0015' and x['rounding_compatible'] for x in audits))
        self.assertEqual([x['native_unit'] for x in rows], ['million_barrels']*3)

    def test_quantum_uses_each_printed_precision_and_gross_error_stays_unknown(self):
        coarse = table('100.0','99.9','0.0')
        rows, audit = m.parse_rounded_table1(coarse, rep())
        self.assertEqual(rows[0]['delta'], 0.)
        self.assertEqual(audit[0]['rounding_bound_native'], '0.15')
        fine = table('100.000','99.900','0.000')
        with self.assertRaises(ValueError):
            m.parse_rounded_table1(fine, rep())
        # Mixed decimal precision must use .0005+.0005+.005, not a fixed .0015.
        mixed = table('100.000','99.900','0.10')
        _, audit = m.parse_rounded_table1(mixed, rep())
        self.assertEqual(audit[0]['rounding_bound_native'], '0.006')

    def test_wrong_ending_and_lower_table_duplicate_cannot_be_recovered(self):
        content = table() + b'"STUB_1","STUB_2","2/28/20","2/21/20","Difference"\n"Distillate Fuel Oil","flow","999","1","2"\n'
        rows, _ = m.parse_rounded_table1(content, rep())
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[-1]['current'],100000.)
        with self.assertRaises(ValueError):
            m.parse_rounded_table1(content, rep(ending='2020-03-06'))

    def test_only_original_arithmetic_rejections_restore_and_all_identities_survive(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'table1.csv'; path.write_bytes(table())
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            reports = [rep('eligible'),rep('date_mismatch'),rep('download_missing'),rep('out_of_bound')]
            original = [dict(report_id=r['report_id'],series_label=k,current=None,prior_inline=None,delta=None,value_status='unknown') for r in reports for k in LABELS]
            base = dict(status=200,source_status='unknown_parse_failed',parse_error='current-prior does not equal reported Difference: -0.001',raw_path=str(path),sha256=digest)
            bindings = [dict(base,report_id='eligible'),dict(base,report_id='date_mismatch',parse_error='data-ending differs from official calendar'),
                        dict(base,report_id='download_missing',source_status='unknown_download_failed',status=0),dict(base,report_id='out_of_bound')]
            bad = Path(td)/'bad.csv';bad.write_bytes(table(delta='0.500'))
            bindings[-1].update(raw_path=str(bad),sha256=hashlib.sha256(bad.read_bytes()).hexdigest())
            restored,audit = m.recover_normalized_stocks(reports,original,bindings)
            self.assertEqual(len(restored),12)
            self.assertEqual(sum(x['value_status']=='known_precision_recovered' for x in restored),3)
            self.assertTrue(all(x['current'] is None for x in original))
            self.assertEqual({x['report_id'] for x in restored},{x['report_id'] for x in original})
            rejected_cells=[x for x in audit if x['scope']=='cell' and x['report_id']=='out_of_bound']
            self.assertEqual(len(rejected_cells),3)
            self.assertTrue(all(not x['rounding_compatible'] for x in rejected_cells))
            self.assertEqual([(x['report_id'],x['recovery_status']) for x in audit if x['scope']=='report'],
                             [('eligible','recovered'),('date_mismatch','not_eligible_original_reason'),('download_missing','not_eligible_original_reason'),('out_of_bound','retained_unknown_outside_precision_contract')])

    def test_raw_hash_drift_fails_before_recovery(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'changed.csv';p.write_bytes(table())
            rec=dict(report_id='drift',status=200,source_status='unknown_parse_failed',parse_error='current-prior does not equal reported Difference: -0.001',raw_path=str(p),sha256='0'*64)
            with self.assertRaises(ValueError):
                m.recover_normalized_stocks([rep('drift')],[],[rec])


if __name__ == '__main__':
    unittest.main(verbosity=2)
