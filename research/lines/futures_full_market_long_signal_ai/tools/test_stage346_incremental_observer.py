"""One loader-only tiny; no actual artifacts or earlier test groups."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

TOOLS=Path(__file__).resolve().parent

class OverlayTiny(unittest.TestCase):
    def test_factor1_overlay_keeps_raw_lineage_and_excludes_unknown_zero_and_other_days(self):
        # Breaks on treating raw success as accepted, zero filling OI,
        # losing receipt/hash lineage, date20 leakage or duplicate overwrite.
        path=TOOLS/'stage346_incremental_observer.py'
        self.assertTrue(path.exists(),'new one-pass root loader missing')
        spec=importlib.util.spec_from_file_location('fixture346',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        receipt=dict(entry_hash='actual321-entry',recorded_at='2026-10-19T19:40:00+00:00')
        raw=dict(path='/synthetic/P.json',bytes=1,sha256='raw-sha')
        index={'DCE.p2701':dict(symbol='DCE.p2701',raw=raw,receipt=receipt)}
        native=dict(open=100.,high=103.,low=99.,close=102.,volume=500.,open_oi=None,close_oi=None)
        row=dict(schema='stage342_date_normalized_row_v1',symbol='DCE.p2701',raw_sha256='raw-sha',
            raw_row_index=7,contract_epoch_id='DCE.P.202701',trade_date='2026-10-19',
            identity_state='known_explicit',date_mapping_state='operational_midnight_label',
            date_mapping_rule='tq_daily_midnight_label_calendar_v1',timestamp_recovery_state='recovered_exact_whole_second_float_ns',
            recovered_ns=1792339200000000000,native_values=native,native_missing_fields=['open_oi','close_oi'],
            received_at=receipt['recorded_at'],fresh_ready=True,source_completed_at=None,
            units_status='provider_raw_units_unverified',canonical_quality_status='unknown',model_input_eligible=False)
        rows=[(row,'line1'),(dict(row,raw_row_index=8,contract_epoch_id=None,identity_state='unknown'),'line2'),
              (dict(row,raw_row_index=9,native_values=dict(native,volume=0.)),'line3'),
              (dict(row,trade_date='2026-10-20'),'line4'),(dict(row,trade_date=None),'line5')]
        before=deepcopy(rows)
        args=dict(date_rows_binding=dict(path='/synthetic/date_rows.gz',sha256='343-sha'),
                  acceptance_binding=dict(path='/synthetic/337.json',sha256='337-sha'))
        overlay,rejected,counts=module.prepare_overlay(rows,index,**args)
        self.assertEqual(rows,before);self.assertEqual(len(overlay),1)
        self.assertEqual(overlay[0]['canonical_values'],{k:native[k] for k in ('open','high','low','close','volume','close_oi')})
        self.assertIsNone(overlay[0]['canonical_values']['close_oi'])
        self.assertEqual(overlay[0]['native_missing_fields'],['open_oi','close_oi'])
        self.assertEqual(overlay[0]['source_receipt']['receiver321_receipt'],receipt)
        self.assertEqual(overlay[0]['source_receipt']['date343_line_sha256'],'line1')
        self.assertEqual(overlay[0]['unit_overlay'],dict(volume_factor=1,oi_factor=1,scope='accepted337_same_batch_u19_only'))
        self.assertTrue(overlay[0]['model_input_eligible']);self.assertEqual(overlay[0]['canonical_quality_status'],'accepted')
        self.assertEqual(counts['input_rows'],5);self.assertEqual(counts['u19_rows'],3)
        self.assertEqual(counts['accepted_rows'],1);self.assertEqual(counts['identity_unknown_geometry_rows'],1)
        self.assertEqual(counts['invalid_or_zero_volume_rows'],1);self.assertEqual(counts['u20_excluded'],1)
        self.assertEqual(len(rejected),2)
        with self.assertRaises(ValueError):module.prepare_overlay([(row,'a'),(row,'b')],index,**args)
        with self.assertRaises(ValueError):module.prepare_overlay([(dict(row,raw_sha256='changed'),'a')],index,**args)

if __name__=='__main__':unittest.main()
