"""Minute coverage invariants; no financial engine, download or source mutation."""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import sqlite3
import unittest
import pandas as pd

try:import stage002_local_minute_overlay as module
except ImportError:module=None


class LocalOverlayTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(module,'local minute overlay is not implemented')
        self.expected=pd.date_range('2020-05-18 09:00',periods=3,freq='min')
        self.source=pd.DataFrame(dict(vt_symbol=['rb2010.SHFE']*3,bar_datetime=self.expected,
            open=[10.,11.,12.],high=[12.,13.,14.],low=[9.,10.,11.],close=[11.,12.,13.],
            volume=[2.,3.,4.],open_oi=[20.,21.,22.],close_oi=[21.,22.,23.]))
        self.daily=dict(open=10.,high=14.,low=9.,close=13.,volume=9.,open_oi=20.,close_oi=23.)
        self.base=self.source.iloc[0:0].copy()

    def test_only_new_keys_are_appended_and_original_base_is_preserved(self):
        base=self.source.iloc[:1].copy();before=base.copy(deep=True)
        new,audit=module.validate_session(self.source,self.expected,self.daily,base)
        self.assertEqual(audit['status'],'accepted')
        self.assertEqual(len(new),2)
        merged=module.merge_frames_preserving_base(base,new)
        self.assertEqual(len(merged),3)
        pd.testing.assert_frame_equal(base,before)
        self.assertEqual(merged.iloc[0]['close'],11.)

    def test_overlap_price_conflict_quarantines_whole_session(self):
        base=self.source.iloc[:1].copy();base.loc[0,'close']=10.5
        new,audit=module.validate_session(self.source,self.expected,self.daily,base)
        self.assertTrue(new.empty)
        self.assertEqual(audit['reason'],'base_overlap_conflict')

    def test_incomplete_duplicate_invalid_and_daily_mismatch_are_rejected(self):
        cases=[(self.source.iloc[:-1],self.daily,'incomplete_session'),
            (pd.concat([self.source,self.source.iloc[:1]]),self.daily,'duplicate_minute'),
            (self.source.assign(low=[15.,10.,11.]),self.daily,'invalid_minute_ohlcvoi'),
            (self.source,{**self.daily,'close':12.},'daily_aggregate_mismatch')]
        for source,daily,reason in cases:
            with self.subTest(reason=reason):
                new,audit=module.validate_session(source,self.expected,daily,self.base)
                self.assertTrue(new.empty);self.assertEqual(audit['reason'],reason)

    def test_unknown_daily_open_oi_is_not_fabricated_or_required(self):
        new,audit=module.validate_session(self.source,self.expected,{**self.daily,'open_oi':float('nan')},self.base)
        self.assertEqual(len(new),3)
        self.assertEqual(audit['daily_open_oi_check'],'unknown')

    def test_missing_csv_fallback_uses_exact_database_identity_and_date(self):
        with TemporaryDirectory()as folder:
            path=Path(folder)/'bars.db'
            with sqlite3.connect(path)as db:
                db.execute('CREATE TABLE dbbardata(symbol TEXT,exchange TEXT,interval TEXT,datetime TEXT,open_price REAL,high_price REAL,low_price REAL,close_price REAL,volume REAL,open_interest REAL)')
                db.executemany('INSERT INTO dbbardata VALUES(?,?,?,?,?,?,?,?,?,?)',[
                    ('AP005','CZCE','d','2020-05-18 00:00:00',10,14,9,13,9,23),
                    ('AP005','CZCE','d','2010-05-18 00:00:00',99,99,99,99,99,99),
                    ('AP005','SHFE','d','2020-05-18 00:00:00',88,88,88,88,88,88)])
            before=path.read_bytes()
            frame=module.read_database_daily(path,'AP005.CZCE')
            self.assertEqual(len(frame),1);self.assertEqual(float(frame.iloc[0]['close']),13.)
            self.assertTrue(pd.isna(frame.iloc[0]['open_oi']))
            self.assertEqual(path.read_bytes(),before)

    def test_friday_night_uses_monday_source_trading_date(self):
        calendar=pd.to_datetime(['2020-05-15','2020-05-18'])
        grid=module.session_grid('rb2010.SHFE','2020-05-18',calendar)
        self.assertEqual(len(grid),345)
        self.assertEqual(str(grid[0]),'2020-05-15 21:00:00')
        self.assertEqual(str(grid[-1]),'2020-05-18 14:59:00')

    def test_actual_a0_read_ranges_detect_even_one_added_key(self):
        anchors=pd.DataFrame([dict(vt_symbol='rb2010.SHFE',expected_start='2020-05-15T21:00:00')])
        scans=pd.DataFrame([dict(vt_symbol='rb2010.SHFE',trading_date='2020-05-18',requested_start='2020-05-18T09:00:00')])
        calendar=pd.to_datetime(['2020-05-15','2020-05-18'])
        receipt=module.prove_read_disjointness(self.source,anchors,scans,calendar)
        self.assertEqual(receipt['intersection_count'],3)
        self.assertFalse(receipt['path_equivalent'])
        other=self.source.assign(vt_symbol='cu2006.SHFE')
        self.assertEqual(module.prove_read_disjointness(other,anchors,scans,calendar)['intersection_count'],0)

    def test_merge_refuses_to_overwrite_even_identical_duplicate_key(self):
        with self.assertRaisesRegex(ValueError,'overlay_contains_base_key'):
            module.merge_frames_preserving_base(self.source,self.source.iloc[:1])

    def test_temporary_loader_merges_and_restores_caches_on_exception(self):
        original=lambda symbols:self.source.iloc[:1].copy()
        cache=object();symbols={'old'};audit={'old':True}
        s901=SimpleNamespace(_load_stage861_full_minute_bars=original,
            _FULL_MINUTE_BY_SYMBOL_CACHE=cache,_FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS=symbols,
            _LAST_MINUTE_AUDIT=audit)
        with self.assertRaises(RuntimeError):
            with module.temporary_minute_overlay(s901,self.source.iloc[1:]):
                self.assertEqual(len(s901._load_stage861_full_minute_bars({'rb2010.SHFE'})),3)
                self.assertIsNone(s901._FULL_MINUTE_BY_SYMBOL_CACHE)
                raise RuntimeError('leave scope')
        self.assertIs(s901._load_stage861_full_minute_bars,original)
        self.assertIs(s901._FULL_MINUTE_BY_SYMBOL_CACHE,cache)
        self.assertIs(s901._FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS,symbols)
        self.assertIs(s901._LAST_MINUTE_AUDIT,audit)


if __name__=='__main__':unittest.main()
