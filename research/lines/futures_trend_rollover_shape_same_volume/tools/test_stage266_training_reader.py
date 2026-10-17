"""Boundary tests use isolated real SQLite files, never market/production stores."""
from datetime import date
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest

import pandas as pd
import stage266_training_reader as reader

COLUMNS=('contract_epoch_id','trade_date','open','high','low','close','volume','open_interest','close_oi','open_oi','open_oi_status','exchange','product','contract_yyyymm','source_symbol','source_id','quality_status','train_eligible','legacy108_usable')


class TrainingReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'clean.sqlite'
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE daily_bars ('+','.join(c+' '+('TEXT' if c in {'contract_epoch_id','trade_date','open_oi_status','exchange','product','contract_yyyymm','source_symbol','source_id','quality_status'} else 'REAL') for c in COLUMNS)+')')

    def put(self,day='2025-01-06',epoch='CZCE.SM.202501',**changes):
        exchange,product,month=epoch.split('.')
        row={'contract_epoch_id':epoch,'trade_date':day,'open':10.,'high':12.,'low':9.,'close':11.,'volume':100.,'open_interest':20.,'close_oi':20.,'open_oi':19.,'open_oi_status':'source_observed','exchange':exchange,'product':product,'contract_yyyymm':month,'source_symbol':'SM501','source_id':'fixture','quality_status':'accepted','train_eligible':1,'legacy108_usable':1}
        row.update(changes)
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT INTO daily_bars VALUES ('+','.join('?' for _ in COLUMNS)+')',[row[c] for c in COLUMNS])

    def load(self,**kwargs):
        args={'contract_epoch_id':'CZCE.SM.202501','candidate_date':'2025-01-10',**kwargs}
        return reader.load_contract_bars(self.path,**args)

    def fill_week(self,missing_open_first=False):
        for day in pd.bdate_range('2025-01-06','2025-01-10'):
            changes={}
            if missing_open_first and day.day==6:changes={'open_oi':None,'open_oi_status':'missing_not_imputed','train_eligible':0,'legacy108_usable':0}
            self.put(day.date().isoformat(),**changes)

    def test_explicit_delivery_month_separates_identical_czce_symbol(self):
        self.put('2015-01-06','CZCE.SM.201501',close=10.)
        self.put('2025-01-06','CZCE.SM.202501',close=11.)
        old=reader.load_contract_bars(self.path,exchange='CZCE',product='SM',contract_yyyymm='201501',candidate_date='2025-01-10')
        self.assertEqual(old['date'].dt.year.tolist(),[2015])
        self.assertEqual(self.load()['date'].dt.year.tolist(),[2025])

    def test_candidate_cutoff_is_applied_before_validation(self):
        self.put('2025-01-09')
        self.put('2025-01-13',open_oi=None,open_oi_status='missing_not_imputed')
        frame=self.load(candidate_date='2025-01-10',open_oi_policy='strict')
        self.assertEqual(frame['trade_date'].tolist(),['2025-01-09'])
        self.assertEqual(frame['open_oi'].tolist(),[19.])

    def test_candidate_date_and_explicit_identity_are_required(self):
        with self.assertRaises(TypeError):reader.load_contract_bars(self.path,contract_epoch_id='CZCE.SM.202501')
        with self.assertRaises(reader.TrainingDataError):reader.load_contract_bars(self.path,exchange='CZCE',product='SM',candidate_date='2025-01-10')
        with self.assertRaises(reader.TrainingDataError):self.load(contract_epoch_id='SM501.CZCE')

    def test_conflicting_selectors_fail_instead_of_guessing(self):
        with self.assertRaises(reader.TrainingDataError):self.load(product='SF',exchange='CZCE',contract_yyyymm='202501')

    def test_mark_mode_preserves_missing_open_oi_and_explicit_unusable_flag(self):
        self.put(open_oi=None,open_oi_status='missing_not_imputed',train_eligible=0,legacy108_usable=0)
        frame=self.load()
        self.assertTrue(pd.isna(frame.loc[0,'open_oi']))
        self.assertFalse(bool(frame.loc[0,'legacy108_usable']))
        self.assertFalse(frame.attrs['legacy108_window_qualified'])
        self.assertIn('open_oi',frame.loc[0,'reader_row_issues'])

    def test_strict_mode_rejects_missing_or_unverified_open_oi(self):
        self.put(open_oi=None,open_oi_status='missing_not_imputed',train_eligible=0,legacy108_usable=0)
        with self.assertRaises(reader.TrainingDataError):self.load(open_oi_policy='strict')

    def test_observed_zero_open_oi_is_a_real_value(self):
        self.put(open_oi=0.)
        self.assertEqual(self.load(open_oi_policy='strict').loc[0,'open_oi'],0.)

    def test_nonmissing_open_oi_without_observed_status_stays_unusable(self):
        self.put(open_oi_status='missing_not_imputed')
        self.assertFalse(bool(self.load().loc[0,'legacy108_usable']))
        with self.assertRaises(reader.TrainingDataError):self.load(open_oi_policy='strict')

    def test_start_date_can_select_complete_recent_window(self):
        self.fill_week(missing_open_first=True)
        frame=self.load(start_date='2025-01-08',open_oi_policy='strict')
        self.assertEqual(frame['trade_date'].tolist(),['2025-01-08','2025-01-09','2025-01-10'])

    def test_duplicate_dates_are_not_silently_kept_last(self):
        self.put();self.put(close=10.)
        with self.assertRaises(reader.TrainingDataError):self.load()

    def test_nonaccepted_zero_volume_and_invalid_geometry_are_marked(self):
        self.put('2025-01-06',quality_status='quarantined')
        self.put('2025-01-07',volume=0.)
        self.put('2025-01-08',close=20.)
        self.assertEqual(self.load()['legacy108_usable'].tolist(),[False,False,False])
        with self.assertRaises(reader.TrainingDataError):self.load(open_oi_policy='strict')

    def test_close_oi_alias_disagreement_is_a_contract_error(self):
        self.put(open_interest=21.)
        with self.assertRaises(reader.TrainingDataError):self.load()

    def test_reader_never_creates_missing_database_or_writes_existing(self):
        before=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.load()
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),before)
        absent=self.path.with_name('absent.sqlite')
        with self.assertRaises(FileNotFoundError):reader.load_contract_bars(absent,contract_epoch_id='CZCE.SM.202501',candidate_date='2025-01-10')
        self.assertFalse(absent.exists())

    def test_unsafe_table_name_is_rejected(self):
        with self.assertRaises(reader.TrainingDataError):self.load(table='daily_bars; DROP TABLE daily_bars')

    def test_monthly_average_family_never_merges_standard_futures(self):
        self.put(epoch='DCE.L_F.202602',source_symbol='L2602F')
        frame=reader.load_contract_bars(self.path,exchange='DCE',product='L_F',contract_yyyymm='202602',candidate_date='2025-01-10')
        self.assertEqual(frame['contract_epoch_id'].tolist(),['DCE.L_F.202602'])
        empty=reader.load_contract_bars(self.path,exchange='DCE',product='L',contract_yyyymm='202602',candidate_date='2025-01-10')
        self.assertTrue(empty.empty)

    def test_window_checks_expected_calendar_gaps_not_tail_observation_count(self):
        for day in ['2025-01-06','2025-01-07','2025-01-08','2025-01-10']:self.put(day)
        calendar=pd.bdate_range('2025-01-06','2025-01-10')
        report=reader.qualify_legacy108_window(self.load(),candidate_date='2025-01-10',expected_trade_dates=calendar,window_rows=3)
        self.assertFalse(report['eligible'])
        self.assertEqual(report['missing_dates'],['2025-01-09'])
        with self.assertRaises(reader.TrainingDataError):reader.require_legacy108_window(self.load(),candidate_date='2025-01-10',expected_trade_dates=calendar,window_rows=3)

    def test_recent_complete_window_does_not_fail_for_older_missing_open_oi(self):
        self.fill_week(missing_open_first=True)
        window=reader.require_legacy108_window(self.load(),candidate_date='2025-01-10',expected_trade_dates=pd.bdate_range('2025-01-06','2025-01-10'),window_rows=3)
        self.assertEqual(window['trade_date'].tolist(),['2025-01-08','2025-01-09','2025-01-10'])
        self.assertTrue(window.attrs['legacy108_window_qualified'])

    def test_window_truncates_future_rows_and_future_calendar(self):
        self.fill_week();self.put('2025-01-13')
        frame=self.load(candidate_date='2025-01-13')
        report=reader.qualify_legacy108_window(frame,candidate_date='2025-01-10',expected_trade_dates=pd.bdate_range('2025-01-06','2025-01-13'),window_rows=3)
        self.assertTrue(report['eligible'])
        self.assertEqual(report['future_rows_excluded'],1)
        self.assertEqual(report['window_end'],'2025-01-10')

    def test_holiday_candidate_and_insufficient_calendar_do_not_qualify(self):
        self.fill_week();cal=pd.bdate_range('2025-01-06','2025-01-10')
        self.assertFalse(reader.qualify_legacy108_window(self.load(),candidate_date='2025-01-12',expected_trade_dates=cal,window_rows=3)['eligible'])
        self.assertFalse(reader.qualify_legacy108_window(self.load(),candidate_date='2025-01-10',expected_trade_dates=cal[-2:],window_rows=3)['eligible'])

    def test_mapping_month_identity_uses_its_own_trade_date(self):
        def row(day):return {'date':day,'product':'SM','exchange':'CZCE','continuous_symbol_vt':'SM.CZCE','main_contract_tq':'CZCE.SM501','main_contract_vt':'SM501.CZCE'}
        self.assertEqual(reader.mapping_identity(row('2015-01-06'))['contract_epoch_id'],'CZCE.SM.201501')
        self.assertEqual(reader.mapping_identity(row('2025-01-06'))['contract_epoch_id'],'CZCE.SM.202501')

    def test_mapping_never_relabels_me_to_ma_or_ignores_wrong_month(self):
        bad={'date':'2015-01-06','product':'MA','exchange':'CZCE','main_contract_tq':'CZCE.ME505','main_contract_vt':'ME505.CZCE'}
        with self.assertRaises(reader.TrainingDataError):reader.mapping_identity(bad)

    def test_actual_clean_schema_row_flag_is_supported_explicitly(self):
        self.put()
        with sqlite3.connect(self.path) as db:
            db.execute('ALTER TABLE daily_bars RENAME COLUMN legacy108_usable TO legacy108_row_usable')
        self.assertTrue(bool(self.load(open_oi_policy='strict').loc[0,'legacy108_usable']))

    def test_unexpected_observation_inside_calendar_window_does_not_leak(self):
        self.fill_week()
        # Use a calendar which intentionally excludes one source date.
        frame=self.load()
        cal=pd.DatetimeIndex(['2025-01-06','2025-01-07','2025-01-08','2025-01-10'])
        report=reader.qualify_legacy108_window(frame,candidate_date='2025-01-10',expected_trade_dates=cal,window_rows=3)
        self.assertFalse(report['eligible'])
        self.assertEqual(report['unexpected_observation_dates'],['2025-01-09'])

    def test_invalid_calendar_and_timezone_do_not_normalize_silently(self):
        self.fill_week()
        with self.assertRaises(reader.TrainingDataError):self.load(candidate_date=pd.Timestamp('2025-01-10',tz='Asia/Shanghai'))
        with self.assertRaises(reader.TrainingDataError):reader.qualify_legacy108_window(self.load(),candidate_date='2025-01-10',expected_trade_dates=['2025-01-10','2025-01-10'])

    def test_availability_audit_counts_mapping_gaps_without_claiming_labels(self):
        self.fill_week(missing_open_first=True)
        def mapped(day, vt='SM501.CZCE'):
            return {'date':day,'product':'SM','exchange':'CZCE','main_contract_vt':vt,'main_contract_tq':'CZCE.SM501'}
        mapping=pd.DataFrame([mapped('2025-01-06'),mapped('2025-01-07'),mapped('2025-01-08'),mapped('2025-01-10'),mapped('2025-01-13','INVALID')])
        report,details=reader.audit_mapping_availability(self.path,mapping,candidate_date='2025-01-10',expected_trade_dates=pd.bdate_range('2025-01-06','2025-01-13'),window_rows=3,products={('CZCE','SM')})
        self.assertEqual(report['calendar_product_rows'],5)
        self.assertEqual(report['mapped_identity_rows'],4)
        self.assertEqual(report['missing_mapping_rows'],1)
        self.assertEqual(report['legacy108_feature_window_rows'],1)
        self.assertFalse(report['label_maturity_or_training_samples_certified'])
        last=details.loc[details.date.eq('2025-01-10')].iloc[0]
        self.assertTrue(last.legacy108_feature_window_ok)
        self.assertFalse(details.loc[details.date.eq('2025-01-09'),'mapped_identity'].iloc[0])

    def test_availability_audit_preserves_mapping_errors_and_rejects_duplicates(self):
        self.fill_week()
        bad={'date':'2025-01-10','product':'SM','exchange':'CZCE','main_contract_vt':'SM501.CZCE','main_contract_tq':'CZCE.SM505'}
        report,details=reader.audit_mapping_availability(self.path,pd.DataFrame([bad]),candidate_date='2025-01-10',expected_trade_dates=pd.bdate_range('2025-01-06','2025-01-10'),window_rows=3,products={('CZCE','SM')})
        self.assertEqual(report['unresolved_mapping_rows'],1)
        self.assertIn('disagree',details.iloc[-1].mapping_status)
        with self.assertRaises(reader.TrainingDataError):reader.audit_mapping_availability(self.path,pd.DataFrame([bad,bad]),candidate_date='2025-01-10',expected_trade_dates=pd.bdate_range('2025-01-06','2025-01-10'),products={('CZCE','SM')})

    def test_csv_only_deletion_delta_invalidates_exact_date_and_expected_window(self):
        self.fill_week()
        mapping=pd.DataFrame([{'date':day.date().isoformat(),'product':'SM','exchange':'CZCE','main_contract_vt':'SM501.CZCE','main_contract_tq':'CZCE.SM501'} for day in pd.bdate_range('2025-01-06','2025-01-10')])
        cal=pd.bdate_range('2025-01-06','2025-01-10')
        _,details=reader.audit_mapping_availability(self.path,mapping,candidate_date='2025-01-10',expected_trade_dates=cal,window_rows=3,products={('CZCE','SM')})
        # Delete Jan6: Jan8's expected window includes it; Jan9/10 no longer do.
        delta=pd.DataFrame([{'contract_epoch_id':'CZCE.SM.202501','trade_date':'2025-01-06'}, {'contract_epoch_id':'CZCE.SM.201501','trade_date':'2025-01-09'}])
        adjusted,report=reader.apply_deletions_to_availability(details,delta,candidate_date='2025-01-10',expected_trade_dates=cal,window_rows=3)
        self.assertEqual(adjusted.observed_clean_row.tolist(),[False,True,True,True,True])
        self.assertEqual(adjusted.legacy108_feature_window_ok.tolist(),[False,False,False,True,True])
        self.assertEqual(report['strict_windows_invalidated'],1)
        self.assertEqual(report['clean_rows_invalidated'],1)
        self.assertTrue(details.iloc[0].observed_clean_row)
        bad={'date':'2025-01-06','product':'SM','exchange':'CZCE','main_contract_tq':'CZCE.SM505','main_contract_vt':'SM501.CZCE'}
        with self.assertRaises(reader.TrainingDataError):reader.mapping_identity(bad)


if __name__=='__main__':unittest.main()
