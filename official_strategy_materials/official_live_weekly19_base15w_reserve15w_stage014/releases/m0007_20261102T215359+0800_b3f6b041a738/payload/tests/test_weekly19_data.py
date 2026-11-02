"""Explicit private snapshot fixtures; no market download or financial replay."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo
import sys

import pandas as pd
from vnpy.trader.constant import Interval

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'))
try:
    import qmt_roll_weekly19_data as reader
except ModuleNotFoundError as exc:
    if exc.name!='qmt_roll_weekly19_data':raise
    reader=None
from tests.test_weekly19_runtime import fixture

FILES=('daily.sqlite','mapping.csv','physical_epoch_daily.csv','metadata.csv','receipt.json')


class DataTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(reader,'weekly19 readonly data adapter is absent')
        self.temp=tempfile.TemporaryDirectory(dir='/private/tmp');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        _,_,_,meta=fixture();self.products=meta['product_symbols'];self.symbols=meta['vt_symbols']+['rb2701.SHFE']
        mappings=[];physical=[];metadata=[]
        for product in self.products:
            metadata.append(dict(vt_symbol=product,source_symbol_vt=product,symbol_kind='product_cont',
                                 price_tick=1.,volume_multiple=10.,margin_ratio=.1))
        with sqlite3.connect(self.root/'daily.sqlite') as db:
            db.execute('create table dbbardata(id integer primary key,symbol text,exchange text,datetime text,interval text,volume real,turnover real,open_interest real,open_price real,high_price real,low_price real,close_price real)')
            for day in ('2026-10-29','2026-10-30'):
                for product in self.products:
                    symbol=next(s for s,p in meta['source_symbol_by_contract'].items() if p==product)
                    mappings.append(dict(date=day,continuous_symbol_vt=product,main_contract_vt=symbol))
                for symbol in self.symbols:
                    code,exchange=symbol.split('.')
                    physical.append(dict(vt_symbol=symbol,date=day,contract_epoch_id=symbol+'-physical',
                        open=100.,high=102.,low=99.,close=101.,volume=1000.,close_oi=2000.))
                    db.execute('insert into dbbardata(symbol,exchange,datetime,interval,volume,turnover,open_interest,open_price,high_price,low_price,close_price) values(?,?,?,?,?,?,?,?,?,?,?)',
                        (code,exchange,day+' 00:00:00','d',1000.,100000.,2000.,100.,102.,99.,101.))
            # A positive raw DB row was never admitted into physical history.
            db.execute("insert into dbbardata(symbol,exchange,datetime,interval,volume,turnover,open_interest,open_price,high_price,low_price,close_price) values('rb9999','SHFE','2026-10-30 00:00:00','d',1000,1000,2000,100,102,99,101)")
        for symbol in self.symbols:
            product=meta['source_symbol_by_contract'].get(symbol,'rb.SHFE')
            metadata.append(dict(vt_symbol=symbol,source_symbol_vt=product,symbol_kind='contract',
                                 price_tick=1.,volume_multiple=10.,margin_ratio=.1))
        pd.DataFrame(mappings).to_csv(self.root/'mapping.csv',index=False)
        pd.DataFrame(physical).to_csv(self.root/'physical_epoch_daily.csv',index=False)
        pd.DataFrame(metadata).to_csv(self.root/'metadata.csv',index=False)
        self.receipt=dict(schema='research-approved-fixture.v1',data_ready=True,date_start='2026-10-29',date_end='2026-10-30',
            units='single_sided_volume_close_oi',products=self.products,historical_main_reconstruction_complete=False,
            readiness_limitations=['fixture is not production qualification'],completed_at='2026-10-30T15:11:00+08:00')
        self.save_receipt()
        self.calendar=['2026-10-29','2026-10-30','2026-11-02','2026-11-03']

    def save_receipt(self):
        (self.root/'receipt.json').write_text(json.dumps(self.receipt))

    def hashes(self):
        return {name:hashlib.sha256((self.root/name).read_bytes()).hexdigest() for name in FILES}

    def load(self,**changes):
        kwargs=dict(material_release_id='weekly19-data-fixture',target_date='2026-10-30',forward_calendar=self.calendar,expected_hashes=self.hashes());kwargs.update(changes)
        return reader.load_weekly19_inputs(self.root,**kwargs)

    def test_explicit_sqlite_physical_parity_and_off_main_warmup_are_readonly_and_unqualified(self):
        before=self.hashes();out=self.load()
        self.assertEqual(before,self.hashes())
        self.assertEqual(set(out['metadata']['product_symbols']),set(self.products))
        self.assertIn('rb2701.SHFE',out['metadata']['vt_symbols'])
        self.assertNotIn('rb9999.SHFE',out['metadata']['vt_symbols'])
        self.assertEqual(len(out['bars_by_day']['2026-10-30']),20)
        self.assertEqual(out['receipt']['sqlite_physical_parity']['checked_rows'],40)
        self.assertTrue(out['receipt']['complete'])
        self.assertTrue(out['receipt']['conditional_read'])
        self.assertFalse(out['receipt']['production_qualified'])
        self.assertFalse(out['receipt']['historical_main_reconstruction_complete'])
        bar=out['bars_by_day']['2026-10-30']['rb2612.SHFE']
        self.assertEqual(bar.interval,Interval.DAILY)
        self.assertEqual(bar.open_interest,2000.)
        self.assertEqual(out['source_hashes_before'],out['source_hashes_after'])

    def test_hash_mismatch_is_rejected_before_dto(self):
        hashes=self.hashes();hashes['metadata.csv']='f'*64
        with self.assertRaisesRegex(reader.DataInputError,'source_hash_mismatch:metadata.csv'):
            self.load(expected_hashes=hashes)

    def test_actual_sqlite_price_disagreement_cannot_be_hidden_by_research_ready_flag(self):
        with sqlite3.connect(self.root/'daily.sqlite') as db:
            db.execute("update dbbardata set close_price=100 where symbol='rb2612' and substr(datetime,1,10)='2026-10-30'")
        with self.assertRaisesRegex(reader.DataInputError,'sqlite_physical_value_mismatch'):
            self.load()

    def test_missing_sqlite_bar_is_not_filled_from_csv_or_zero(self):
        with sqlite3.connect(self.root/'daily.sqlite') as db:
            db.execute("delete from dbbardata where symbol='rb2612' and substr(datetime,1,10)='2026-10-30'")
        with self.assertRaisesRegex(reader.DataInputError,'approved_sqlite_bar_missing'):
            self.load()

    def test_duplicate_daily_row_is_not_selected_arbitrarily(self):
        with sqlite3.connect(self.root/'daily.sqlite') as db:
            db.execute("insert into dbbardata(symbol,exchange,datetime,interval,volume,turnover,open_interest,open_price,high_price,low_price,close_price) values('rb2612','SHFE','2026-10-30 12:00:00','d',1000,100000,2000,100,102,99,101)")
        with self.assertRaisesRegex(reader.DataInputError,'duplicate_sqlite_daily_key'):
            self.load()

    def test_target_main_missing_physical_admission_is_blocked(self):
        frame=pd.read_csv(self.root/'physical_epoch_daily.csv')
        frame=frame.loc[~((frame.vt_symbol=='rb2612.SHFE')&(frame.date=='2026-10-30'))]
        frame.to_csv(self.root/'physical_epoch_daily.csv',index=False)
        with self.assertRaisesRegex(reader.DataInputError,'target_main_admitted_bar_missing'):
            self.load()

    def test_forward_calendar_must_reach_next_iso_week(self):
        with self.assertRaisesRegex(reader.DataInputError,'next_iso_week_calendar_required'):
            self.load(forward_calendar=self.calendar[:2])

    def test_today_forming_bar_is_rejected_even_if_receipt_says_ready(self):
        with patch.object(reader,'_now',return_value=datetime(2026,10,30,14,59,tzinfo=ZoneInfo('Asia/Shanghai'))):
            with self.assertRaisesRegex(reader.DataInputError,'target_trading_day_not_completed'):
                self.load()

    def test_old_research_qualification_flag_never_becomes_production(self):
        self.receipt['production_qualified']=True;self.save_receipt()
        self.assertFalse(self.load()['receipt']['production_qualified'])

    def test_source_units_cannot_be_inferred_or_silently_changed(self):
        self.receipt['units']='double_sided_volume';self.save_receipt()
        with self.assertRaisesRegex(reader.DataInputError,'single_sided_close_oi_units_required'):
            self.load()

    def test_forward_calendar_file_is_hash_checked_again_after_sqlite_read(self):
        path=self.root/'calendar.csv';pd.DataFrame({'date':self.calendar}).to_csv(path,index=False)
        hashes=self.hashes();hashes['forward_calendar']=reader._sha(path);original=reader._read_sqlite
        def changed(*args):
            out=original(*args);pd.DataFrame({'date':self.calendar[:-1]}).to_csv(path,index=False);return out
        with patch.object(reader,'_read_sqlite',side_effect=changed):
            with self.assertRaisesRegex(reader.DataInputError,'forward_calendar_changed_during_read'):
                self.load(forward_calendar=path,expected_hashes=hashes)
