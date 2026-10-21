"""One small float/date group; no raw archive, API or old suite reads."""
from datetime import datetime
import importlib.util
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo


class ExactDailyFloatTiny(unittest.TestCase):
    def test_only_exact_whole_second_float_and_confirmed_midnight_recovers(self):
        # Catches broad float->int casts, loss of the literal witness, padding
        # treated as dates, non-whole ns admission, or a calendar-free label.
        path=Path(__file__).with_name('stage342_offline_date_adapter.py')
        self.assertTrue(path.exists(),'offline exact-float date adapter is not implemented')
        spec=importlib.util.spec_from_file_location('stage342_tiny',path)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        ns=int(datetime(2026,10,19,tzinfo=ZoneInfo('Asia/Shanghai')).timestamp())*10**9
        def row(value,literal=None,kind='float64'):
            return dict(row_index=0,raw_ns=None,raw_datetime_type=kind,
                raw_datetime_literal=repr(value) if literal is None else literal,
                timestamp_state='raw_timestamp_unknown',values=dict(datetime=value,
                    open=100.,high=101.,low=99.,close=100.,volume=1000.,open_oi=10.,close_oi=11.))
        calendar={'2026-10-19':True,'2026-10-20':True}
        source=row(float(ns));original=repr(source)
        recovered=m.recover_timestamp(source,source_dtype='float64',calendar=calendar)
        self.assertEqual(recovered['recovered_ns'],ns)
        self.assertEqual(recovered['trade_date'],'2026-10-19')
        self.assertEqual(recovered['timestamp_recovery_state'],'recovered_exact_whole_second_float_ns')
        self.assertEqual(repr(source),original)
        rejected=[row(0.),row(-1.),row(float('inf')),row(float('nan')),row(1.5),
                  row(float(ns+256)),row(float(ns),literal=str(ns+1)),row(float(ns),kind='float32')]
        for bad in rejected:
            with self.subTest(value=bad['raw_datetime_literal'],kind=bad['raw_datetime_type']):
                result=m.recover_timestamp(bad,source_dtype=bad['raw_datetime_type'],calendar=calendar)
                self.assertIsNone(result['trade_date'])
                self.assertIsNone(result['recovered_ns'])
        for cal in ({},{'2026-10-19':False}):
            self.assertIsNone(m.recover_timestamp(source,source_dtype='float64',calendar=cal)['trade_date'])
        noon=row(float(ns+12*3600*10**9))
        self.assertIsNone(m.recover_timestamp(noon,source_dtype='float64',calendar=calendar)['trade_date'])
        integer=row(ns,kind='int64');integer.update(raw_ns=ns,timestamp_state='strict_integer_ns')
        kept=m.recover_timestamp(integer,source_dtype='int64',calendar=calendar)
        self.assertEqual(kept['timestamp_recovery_state'],'original_strict_integer_ns')
        self.assertEqual(kept['recovered_ns'],ns)
        decoded=m.decode_row(source,symbol='SHFE.cu2611',source_dtype='float64',calendar=calendar,
            identity_map={'SHFE.cu2611':'SHFE.CU.202611'},received_at='2026-10-19T19:37:00+00:00',
            raw_sha256='tiny_raw_binding',end_inclusive='2026-10-20')
        self.assertEqual(decoded['contract_epoch_id'],'SHFE.CU.202611')
        self.assertEqual(decoded['native_values']['volume'],1000.)
        self.assertEqual(decoded['received_at'],'2026-10-19T19:37:00+00:00')
        self.assertIsNone(decoded['source_completed_at'])
        self.assertEqual(decoded['units_status'],'provider_raw_units_unverified')
        self.assertFalse(decoded['model_input_eligible'])
        self.assertEqual(decoded['window_state'],'in_window')


if __name__=='__main__':unittest.main()
