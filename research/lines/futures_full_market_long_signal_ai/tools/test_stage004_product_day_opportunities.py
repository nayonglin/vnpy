"""Finite source-date and read-only SQLite tests; no strategy/runtime imports."""
import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import struct
import tempfile
import unittest

MODULE_PATH=Path(__file__).with_name('stage004_product_day_opportunities.py')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixture(path,contracts,rows):
    with sqlite3.connect(path) as db:
        db.executescript('''CREATE TABLE contracts(contract_epoch_id TEXT,exchange TEXT,product TEXT,
            contract_yyyymm TEXT,listed_date TEXT,delisted_date TEXT,maturity_date TEXT,metadata_status TEXT);
            CREATE TABLE daily_bars(contract_epoch_id TEXT,exchange TEXT,product TEXT,source_symbol TEXT,
            contract_yyyymm TEXT,trade_date TEXT,open REAL,high REAL,low REAL,close REAL,
            volume REAL,close_oi REAL,open_oi REAL,open_interest REAL,source_id TEXT,
            source_locator TEXT,volume_factor REAL,oi_factor REAL,native_volume REAL,native_close_oi REAL,
            native_open_oi REAL,open_oi_status TEXT,quality_status TEXT,legacy108_row_usable INTEGER,
            train_eligible INTEGER,priority INTEGER);''')
        for epoch in contracts:
            ex,prod,month=epoch.split('.')
            db.execute('INSERT INTO contracts VALUES(?,?,?,?,?,?,?,?)',(epoch,ex,prod,month,'','','','fixture_metadata'))
        for epoch,day,fields in rows:
            ex,prod,month=epoch.split('.')
            r=dict(contract_epoch_id=epoch,exchange=ex,product=prod,source_symbol=prod+month[-3:],
                contract_yyyymm=month,trade_date=day,open=10.,high=12.,low=9.,close=11.,volume=10.,
                close_oi=20.,open_oi=None,open_interest=20.,source_id='fixture_actual_source',source_locator='fixture:row',
                volume_factor=1.,oi_factor=1.,native_volume=10.,native_close_oi=20.,native_open_oi=None,
                open_oi_status='not_available',quality_status='accepted',legacy108_row_usable=0,train_eligible=0,priority=100)
            r.update(fields)
            db.execute('INSERT INTO daily_bars VALUES('+','.join('?' for _ in r)+')',tuple(r.values()))


class ProductDayOpportunitiesTest(unittest.TestCase):
    def module(self):
        self.assertTrue(MODULE_PATH.is_file(),'new Stage004 opportunity selector is not implemented')
        spec=importlib.util.spec_from_file_location('stage004_under_test',MODULE_PATH)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def scan(self,module,path,calendar,start,end):
        rows=[];rejected=[]
        info=module.scan_database(path,calendar,start_date=start,end_date=end,emit=rows.append,emit_rejected=rejected.append)
        return rows,info,rejected

    def test_complete_roster_keeps_F_no_data_and_legacy_false(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'tiny.sqlite'
            epochs=['SHFE.CU.201505','DCE.L_F.201505','CZCE.WT.201505','INE.SC.201505','CFFEX.IF.201505','GFEX.SI.202301']
            fixture(path,epochs,[(epochs[0],'2015-01-05',{}),(epochs[1],'2015-01-05',{})])
            rows,info,rejected=self.scan(m,path,['2015-01-05','2015-01-06','2015-01-07'],'2015-01-05','2015-01-06')
            self.assertEqual(len(rows),12);self.assertEqual(len(info['product_roster']),6);self.assertFalse(rejected)
            self.assertEqual({r['exchange'] for r in rows},{'SHFE','DCE','CZCE','INE','CFFEX','GFEX'})
            f=next(r for r in rows if r['product_id']=='DCE.L_F' and r['u_date']=='2015-01-05')
            self.assertEqual(f['status'],'observed_long_research_opportunity');self.assertEqual(f['train_eligible'],0)
            self.assertEqual(f['legacy108_row_usable'],0);self.assertIsNone(f['open_oi'])
            self.assertEqual({r['direction'] for r in rows},{'long'})
            empty=next(r for r in rows if r['product_id']=='CZCE.WT')
            self.assertEqual(empty['status'],'no_accepted_observation');self.assertIsNone(empty['close'])
            self.assertEqual(empty['reference_epoch'],'');self.assertEqual(f['planned_execution_date'],'2015-01-06')
            self.assertEqual(len({(r['product_id'],r['u_date']) for r in rows}),12)

    def test_ranking_real_epochs_and_invalid_rows_are_explicit(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'ranking.sqlite'; a='SHFE.CU.202005';b='SHFE.CU.202006';c='SHFE.CU.202007'
            rows=[(a,'2020-01-02',dict(volume=20,close_oi=1)),(b,'2020-01-02',dict(volume=10,close_oi=9999)),
                (a,'2020-01-03',dict(volume=20,close_oi=None)),(b,'2020-01-03',dict(volume=20,close_oi=0)),
                (a,'2020-01-06',dict(volume=20,close_oi=100)),(b,'2020-01-06',dict(volume=20,close_oi=100)),
                (c,'2020-01-02',dict(volume=0)),(c,'2020-01-03',dict(high=5)),
                (c,'2020-01-06',dict(quality_status='quarantined',volume=999999))]
            fixture(p,[a,b,c],rows)
            out,info,rejected=self.scan(m,p,['2020-01-02','2020-01-03','2020-01-06'],'2020-01-02','2020-01-06')
            self.assertEqual([r['reference_epoch'] for r in out],[a,b,a]);self.assertEqual(len(rejected),3)
            self.assertEqual([r['candidate_count'] for r in out],[2,2,2]);self.assertEqual(info['counts']['rejected_rows'],3)
            epoch_db=Path(folder)/'epochs.sqlite'
            fixture(epoch_db,['CZCE.SM.201501','CZCE.SM.202501'],[
                ('CZCE.SM.201501','2015-01-05',dict(source_symbol='SM501')),
                ('CZCE.SM.202501','2025-01-06',dict(source_symbol='SM501'))])
            separated,_,_=self.scan(m,epoch_db,['2015-01-05','2025-01-06'],'2015-01-05','2025-01-06')
            self.assertEqual([r['reference_epoch'] for r in separated],['CZCE.SM.201501','CZCE.SM.202501'])
            with sqlite3.connect(p) as db:db.execute('INSERT INTO daily_bars SELECT * FROM daily_bars LIMIT 1')
            with self.assertRaisesRegex(ValueError,'duplicate'):
                self.scan(m,p,['2020-01-02','2020-01-03','2020-01-06'],'2020-01-02','2020-01-06')
            bad=Path(folder)/'identity.sqlite';fixture(bad,[a],[(a,'2020-01-02',dict(product='AL'))])
            with self.assertRaisesRegex(ValueError,'identity'):
                self.scan(m,bad,['2020-01-02'],'2020-01-02','2020-01-02')

    def test_prefix_invariance_future_high_volume_and_delete_D(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'prefix.sqlite';a='SHFE.CU.202005';b='SHFE.CU.202006'
            fixture(p,[a,b],[(a,'2020-01-02',{})])
            calendar=['2020-01-02','2020-01-03','2020-01-06']
            before,_,_=self.scan(m,p,calendar,'2020-01-02','2020-01-02')
            with sqlite3.connect(p) as db:
                db.execute("INSERT INTO daily_bars SELECT contract_epoch_id,exchange,product,source_symbol,contract_yyyymm,'2020-01-03',open,high,low,close,volume,close_oi,open_oi,open_interest,source_id,source_locator,volume_factor,oi_factor,native_volume,native_close_oi,native_open_oi,open_oi_status,quality_status,legacy108_row_usable,train_eligible,priority FROM daily_bars")
                db.execute("UPDATE daily_bars SET contract_epoch_id=?,contract_yyyymm='202006',volume=1e12,close=12 WHERE trade_date='2020-01-03'",(b,))
            full,_,_=self.scan(m,p,calendar,'2020-01-02','2020-01-06')
            self.assertEqual(full[0],before[0]);self.assertEqual(full[1]['reference_epoch'],b)
            with sqlite3.connect(p) as db:db.execute("DELETE FROM daily_bars WHERE trade_date='2020-01-03'")
            deleted,_,_=self.scan(m,p,calendar,'2020-01-02','2020-01-02')
            self.assertEqual(deleted,before)
            terminal,_,_=self.scan(m,p,['2020-01-02'],'2020-01-02','2020-01-02')
            self.assertEqual(terminal[0]['execution_day_status'],'execution_day_unknown')
            self.assertEqual(terminal[0]['reference_epoch'],before[0]['reference_epoch'])
            self.assertEqual(terminal[0]['event_id'],before[0]['event_id'])

    def test_real_readonly_sqlite_bound_calendar_export_and_sidecar_guard(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);p=root/'tiny.sqlite';fixture(p,['DCE.L_F.202005'],[('DCE.L_F.202005','2020-01-02',{})])
            before=sha(p)
            with m.open_readonly(p) as db:
                self.assertEqual(db.execute('PRAGMA query_only').fetchone()[0],1)
                with self.assertRaises(sqlite3.OperationalError):db.execute('CREATE TABLE forbidden(x)')
            absent=root/'absent.sqlite'
            with self.assertRaises(FileNotFoundError):
                with m.open_readonly(absent):pass
            self.assertFalse(absent.exists())
            header=repr(dict(descr='<i8',fortran_order=False,shape=(3,)))
            pad=(-((10+len(header)+1)%16))%16;payload=(header+' '*pad+'\n').encode('latin1')
            cal=root/'calendar.npy';cal.write_bytes(b'\x93NUMPY\x01\x00'+struct.pack('<H',len(payload))+payload+struct.pack('<qqq',20200102,20200103,20200106))
            self.assertEqual(m.load_calendar(cal.read_bytes()),['2020-01-02','2020-01-03','2020-01-06'])
            stat=p.stat();bindings=dict(schema='stage004_source_bindings_v1',database=dict(path=str(p),bytes=stat.st_size,mtime_ns=stat.st_mtime_ns,sha256=before,wal_present=False,shm_present=False),calendar=dict(path=str(cal),sha256=sha(cal),bytes=cal.stat().st_size),small_bindings=[])
            binding_path=root/'bindings.json';binding_path.write_text(json.dumps(bindings))
            result=m.export_panel(binding_path,sha(binding_path),root/'export')
            self.assertFalse(result['financial_ready']);self.assertFalse(result['label_ready']);self.assertFalse(result['model_ready'])
            self.assertFalse(result['publication_pit_certified']);self.assertEqual(result['counts']['panel_rows'],3)
            with gzip.open(root/'export/product_day_opportunities.csv.gz','rt',newline='') as stream:rows=list(csv.DictReader(stream))
            self.assertEqual(len(rows),3);self.assertEqual(rows[1]['close'],'');self.assertEqual(rows[0]['direction'],'long')
            self.assertNotIn('feature_known_at',rows[0]);self.assertEqual(sha(p),before)
            with self.assertRaises(FileExistsError):m.export_panel(binding_path,sha(binding_path),root/'export')
            Path(str(p)+'-wal').write_bytes(b'x')
            with self.assertRaisesRegex(ValueError,'sidecar|state'):
                m.export_panel(binding_path,sha(binding_path),root/'blocked')
            self.assertFalse((root/'blocked').exists())


if __name__=='__main__':unittest.main()
