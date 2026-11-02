"""Explicit private generations with a fixture-only fetch backend. No network."""
from pathlib import Path
import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd
from tests.test_weekly19_data import DataTests
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'))
try:
    import qmt_roll_weekly19_data_update as update
except ModuleNotFoundError as exc:
    if exc.name!='qmt_roll_weekly19_data_update':raise
    update=None

class FixtureBackend:
    def __init__(self,case):self.case=case;self.calls=[]
    def fetch_mapping(self,products,start,target):
        self.calls.append(('mapping',tuple(products),start,target))
        frame=pd.read_csv(self.case.root/'mapping.csv',dtype=str)
        frame=frame.loc[frame.date=='2026-10-30'].copy();frame['date']=target
        frame.attrs['forward_calendar']=dict(source='explicit-fixture-not-TQ',trading_dates=[target,'2026-11-03','2026-11-09'])
        return frame
    def fetch_contracts(self,symbols,*,new_symbols,target_date):
        self.calls.append(('daily',tuple(symbols),tuple(new_symbols)))
        answer={}
        for symbol in symbols:
            digits=''.join(c for c in symbol.split('.')[0] if c.isdigit())
            month=digits[-2:];year=2026 if digits in ('612','2612') else 2027
            quote=dict(instrument_id=symbol.split('.')[1]+'.'+symbol.split('.')[0],ins_class='FUTURE',
                delivery_year=year,delivery_month=int(month),expire_datetime=1800000000.,price_tick=1.,volume_multiple=10.)
            records=[dict(id=0,datetime=int(pd.Timestamp('2026-10-30',tz='Asia/Shanghai').tz_convert('UTC').timestamp()*1e9),
                duration=86400,open=100.,high=102.,low=99.,close=101.,volume=1000.,close_oi=2100.,open_oi=999.,turnover=100000.),
                dict(id=1,datetime=int(pd.Timestamp(target_date,tz='Asia/Shanghai').tz_convert('UTC').timestamp()*1e9),
                duration=86400,open=102.,high=104.,low=101.,close=103.,volume=1200.,close_oi=2200.,open_oi=999.,turnover=120000.)]
            answer[symbol]=dict(quote=quote,daily=pd.DataFrame(records))
        return answer

class UpdateTests(DataTests):
    # The inherited reader contract is deliberately rerun on the base fixture.
    def setUp(self):
        super().setUp();self.assertIsNotNone(update,'dedicated weekly19 updater is absent')
        frame=pd.read_csv(self.root/'physical_epoch_daily.csv')
        epochs=[]
        for symbol in self.symbols:
            code,exchange=symbol.split('.');prefix=''.join(c for c in code if c.isalpha());digits=code[len(prefix):]
            month='202612' if digits in ('612','2612') else '202701'
            eid=exchange+'.'+prefix.upper()+'.'+month
            frame.loc[frame.vt_symbol==symbol,'contract_epoch_id']=eid
            epochs.append(dict(vt_symbol=symbol,contract_epoch_id=eid,contract_yyyymm=month,
                listed_date='2026-01-01',delisted_date='2027-12-31',lifecycle_status='explicit-fixture'))
        frame.to_csv(self.root/'physical_epoch_daily.csv',index=False)
        pd.DataFrame(epochs).to_csv(self.root/'physical_epochs.csv',index=False)
        self.generations=self.root.parent/(self.root.name+'-generations')
        self.addCleanup(lambda:__import__('shutil').rmtree(self.generations,ignore_errors=True))
        self.backend=FixtureBackend(self)
    def run_update(self,**kw):
        hashes=self.hashes();hashes['physical_epochs.csv']=update.reader._sha(self.root/'physical_epochs.csv')
        args=dict(material_release_id='weekly19-update-fixture',target_date='2026-11-02',held_contracts=['rb2701.SHFE'],
            expected_hashes=hashes,backend=self.backend,now=pd.Timestamp('2026-11-02T15:30:00+08:00').to_pydatetime())
        args.update(kw)
        with patch.object(update.reader,'_now',return_value=args['now']):
            return update.update_weekly19_assets(self.root,self.generations,**args)
    def test_immutable_generation_keeps_old_rows_and_close_oi_and_explicit_held_contract(self):
        before=self.hashes();out=self.run_update()
        self.assertEqual(before,self.hashes());self.assertFalse(out['production_qualified'])
        self.assertEqual(set(self.backend.calls[0][1]),set(self.products))
        self.assertIn('rb2701.SHFE',self.backend.calls[1][1])
        generation=Path(out['asset_root']);self.assertTrue(generation.is_dir())
        self.assertNotEqual(generation,self.root)
        with sqlite3.connect(generation/'daily.sqlite') as db:
            self.assertEqual(db.execute("select open_interest from dbbardata where symbol='rb2701' and substr(datetime,1,10)='2026-11-02'").fetchone()[0],2200.)
            self.assertEqual(db.execute("select open_interest from dbbardata where symbol='rb2701' and substr(datetime,1,10)='2026-10-30'").fetchone()[0],2000.)
        latest=json.loads((self.generations/'latest.json').read_text())
        self.assertEqual(latest['asset_root'],str(generation));self.assertTrue((generation/'forward_calendar.csv').is_file())
        self.assertTrue(out['conditional_read']);self.assertEqual(out['market_order_calls'],0)
    def test_missing_held_target_bar_aborts_without_publishing_latest(self):
        original=self.backend.fetch_contracts
        def missing(*a,**kw):
            out=original(*a,**kw);out['rb2701.SHFE']['daily']=out['rb2701.SHFE']['daily'].iloc[:1];return out
        self.backend.fetch_contracts=missing
        with self.assertRaisesRegex(update.DataUpdateError,'required_completed_daily_missing:rb2701.SHFE'):
            self.run_update()
        self.assertFalse((self.generations/'latest.json').exists())
    def test_unknown_contract_requires_explicit_delivery_month_and_full_available_history(self):
        mapping=self.backend.fetch_mapping;fetch=self.backend.fetch_contracts
        def new_mapping(*a):
            out=mapping(*a);out.loc[out.continuous_symbol_vt=='rb.SHFE','main_contract_vt']='rb2705.SHFE';return out
        self.backend.fetch_mapping=new_mapping
        def incomplete(*a,**kw):
            out=fetch(*a,**kw);out['rb2705.SHFE']['daily']['id']=[50,51];return out
        self.backend.fetch_contracts=incomplete
        with self.assertRaisesRegex(update.DataUpdateError,'new_contract_available_history_start_missing'):
            self.run_update()
    def test_missing_close_oi_never_falls_back_to_open_oi(self):
        fetch=self.backend.fetch_contracts
        def absent(*a,**kw):
            out=fetch(*a,**kw);out['rb2612.SHFE']['daily']=out['rb2612.SHFE']['daily'].drop(columns='close_oi');return out
        self.backend.fetch_contracts=absent
        with self.assertRaisesRegex(update.DataUpdateError,'daily_close_oi_required'):
            self.run_update()
    def test_forming_target_is_rejected_before_backend_is_called(self):
        with self.assertRaisesRegex(update.DataUpdateError,'target_trading_day_not_completed'):
            self.run_update(now=pd.Timestamp('2026-11-02T14:59:00+08:00').to_pydatetime())
        self.assertEqual(self.backend.calls,[])
    def test_registry_hash_and_explicit_private_destination_are_required(self):
        hashes=self.hashes()
        with self.assertRaisesRegex(update.DataUpdateError,'approved_explicit_epoch_month_required'):
            self.run_update(expected_hashes=hashes)
        with self.assertRaisesRegex(update.DataUpdateError,'generation_destination_must_be_separate'):
            update.update_weekly19_assets(self.root,self.root,material_release_id='fixture',target_date='2026-11-02',
                held_contracts=[],expected_hashes=hashes,backend=self.backend,now=pd.Timestamp('2026-11-02T15:30:00+08:00').to_pydatetime())

    def test_unobserved_non_strategy_turnover_uses_declared_transport_sentinel_only(self):
        fetch=self.backend.fetch_contracts
        def absent(*a,**kw):
            out=fetch(*a,**kw)
            for payload in out.values():payload['daily']=payload['daily'].drop(columns='turnover')
            return out
        self.backend.fetch_contracts=absent
        out=self.run_update();receipt=json.loads((Path(out['asset_root'])/'receipt.json').read_text())
        self.assertTrue(receipt['turnover_unknown_not_observed'])
        self.assertFalse(receipt['turnover_dependent_strategies_qualified'])
        with sqlite3.connect(Path(out['asset_root'])/'daily.sqlite') as db:
            self.assertEqual(db.execute("select turnover from dbbardata where symbol='rb2612' and substr(datetime,1,10)='2026-11-02'").fetchone()[0],0.)

    def test_legacy_seed_has_observed_bounds_only_and_no_legal_listing_fabrication(self):
        frame=pd.read_csv(self.root/'physical_epoch_daily.csv');frame['contract_yyyymm']=frame.contract_epoch_id.str.split('.').str[-1]
        frame.to_csv(self.root/'physical_epoch_daily.csv',index=False)
        seed=update.build_legacy_epoch_seed_from_approved(self.root/'physical_epoch_daily.csv',trusted_sha256=self.hashes()['physical_epoch_daily.csv'])
        self.assertTrue(seed.listed_unknown.all());self.assertTrue(seed.delisted_unknown.all())
        self.assertEqual(set(seed.listed_date),{''});self.assertEqual(set(seed.observed_available_min),{'2026-10-29'})
        out=self.run_update(expected_hashes=self.hashes());self.assertFalse(out['production_qualified'])
    def test_new_contract_full_available_id0_history_keeps_legal_listing_unknown(self):
        mapping=self.backend.fetch_mapping
        def new_mapping(*a):
            out=mapping(*a);out.loc[out.continuous_symbol_vt=='rb.SHFE','main_contract_vt']='rb2705.SHFE';return out
        self.backend.fetch_mapping=new_mapping
        out=self.run_update();admission=out['new_contract_history_admissions'][0]
        self.assertTrue(admission['listed_unknown']);self.assertEqual(admission['listed_date'],'')
        self.assertEqual(admission['observed_available_min'],'2026-10-30')
        self.assertTrue(admission['available_history_ids_contiguous']);self.assertFalse(admission['legal_listing_history_complete'])
        self.assertFalse(out['production_qualified'])

    def test_new_contract_missing_completed_vendor_id_cannot_publish(self):
        mapping=self.backend.fetch_mapping;fetch=self.backend.fetch_contracts
        def new_mapping(*a):
            out=mapping(*a);out.loc[out.continuous_symbol_vt=='rb.SHFE','main_contract_vt']='rb2705.SHFE';return out
        def gap(*a,**kw):
            out=fetch(*a,**kw);out['rb2705.SHFE']['daily']['id']=[0,2];return out
        self.backend.fetch_mapping=new_mapping;self.backend.fetch_contracts=gap
        with self.assertRaisesRegex(update.DataUpdateError,'new_contract_available_history_id_gap'):
            self.run_update()
        self.assertFalse((self.generations/'latest.json').exists())

    def test_expired_offmain_unheld_contract_does_not_require_fabricated_next_bar(self):
        symbol='rb2705.SHFE'
        physical=pd.read_csv(self.root/'physical_epoch_daily.csv');extra=physical.loc[physical.vt_symbol=='rb2701.SHFE'].copy()
        extra['vt_symbol']=symbol;extra['contract_epoch_id']='SHFE.RB.202705'
        pd.concat([physical,extra],ignore_index=True).to_csv(self.root/'physical_epoch_daily.csv',index=False)
        meta=pd.read_csv(self.root/'metadata.csv');row=meta.loc[meta.vt_symbol=='rb2701.SHFE'].copy();row['vt_symbol']=symbol
        pd.concat([meta,row],ignore_index=True).to_csv(self.root/'metadata.csv',index=False)
        epochs=pd.read_csv(self.root/'physical_epochs.csv');row=epochs.loc[epochs.vt_symbol=='rb2701.SHFE'].copy()
        row['vt_symbol']=symbol;row['contract_epoch_id']='SHFE.RB.202705';row['contract_yyyymm']='202705'
        pd.concat([epochs,row],ignore_index=True).to_csv(self.root/'physical_epochs.csv',index=False)
        with sqlite3.connect(self.root/'daily.sqlite') as db:
            db.execute("insert into dbbardata(symbol,exchange,datetime,interval,volume,turnover,open_interest,open_price,high_price,low_price,close_price) select 'rb2705',exchange,datetime,interval,volume,turnover,open_interest,open_price,high_price,low_price,close_price from dbbardata where symbol='rb2701'")
        fetch=self.backend.fetch_contracts
        def expired(*a,**kw):
            out=fetch(*a,**kw);out[symbol]['daily']=out[symbol]['daily'].iloc[:1]
            out[symbol]['quote']['expire_datetime']=pd.Timestamp('2026-11-01',tz='Asia/Shanghai').timestamp();return out
        self.backend.fetch_contracts=expired
        out=self.run_update();receipt=json.loads((Path(out['asset_root'])/'receipt.json').read_text())
        self.assertEqual(receipt['expired_unheld_offmain_contracts'][0]['vt_symbol'],symbol)
        with sqlite3.connect(Path(out['asset_root'])/'daily.sqlite') as db:
            self.assertEqual(db.execute("select count(*) from dbbardata where symbol='rb2705' and substr(datetime,1,10)='2026-11-02'").fetchone()[0],0)

    def test_explicit_known_epoch_cannot_absorb_same_native_code_from_next_decade(self):
        fetch=self.backend.fetch_contracts
        def future_epoch(*a,**kw):
            out=fetch(*a,**kw);out['AP612.CZCE']['quote']['delivery_year']=2036
            out['AP612.CZCE']['quote']['expire_datetime']=pd.Timestamp('2036-12-31',tz='Asia/Shanghai').timestamp()
            return out
        self.backend.fetch_contracts=future_epoch;before=self.hashes()
        with self.assertRaisesRegex(update.DataUpdateError,'known_contract_quote_epoch_mismatch:AP612.CZCE'):
            self.run_update()
        self.assertEqual(before,self.hashes());self.assertFalse((self.generations/'latest.json').exists())
    def test_explicit_known_epoch_with_matching_raw_delivery_month_appends_actual_bar(self):
        out=self.run_update();frame=pd.read_csv(Path(out['asset_root'])/'physical_epoch_daily.csv')
        row=frame.loc[(frame.vt_symbol=='AP612.CZCE')&(frame.date=='2026-11-02')].iloc[0]
        self.assertEqual(row.contract_epoch_id,'CZCE.AP.202612')
        self.assertEqual(int(row.contract_yyyymm),202612)
