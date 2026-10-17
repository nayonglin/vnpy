"""Research-only clean data views; no primary database writes or production hooks."""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

import pandas as pd

from stage266_training_reader import mapping_identity


def research_symbol(product_vt: str, yyyymm: str) -> str:
    product, exchange = product_vt.split('.')
    if len(str(yyyymm)) != 6 or not str(yyyymm).isdigit() or not 1 <= int(str(yyyymm)[-2:]) <= 12:
        raise ValueError('invalid_delivery_month')
    return f'{product}{yyyymm}.{exchange}'


def ready_dates(observed, calendar, window):
    observed = pd.DatetimeIndex(observed)
    calendar = pd.DatetimeIndex(calendar)
    present = pd.Series(calendar.isin(observed), index=calendar)
    return present.astype(int).rolling(window, min_periods=window).sum().eq(window)


def rename_metadata(original, info):
    keys = ['rates','slippages','sizes','priceticks','margin_ratios','metadata_sources']
    result = {key:{r.research_symbol: original[key][r.native_symbol] for r in info.itertuples()} for key in keys}
    result.update(vt_symbols=sorted(info.research_symbol.tolist()),
                  product_symbols=sorted(info.product_vt_symbol.unique().tolist()),
                  source_symbol_by_contract=dict(zip(info.research_symbol, info.product_vt_symbol)))
    return result


class CleanSource:
    def __init__(self, db_path, mapping_path, products, *, start, end, calendar):
        self.start, self.end = pd.Timestamp(start), pd.Timestamp(end)
        self.calendar = pd.DatetimeIndex(calendar)
        self.calendar = self.calendar[(self.calendar >= self.start) & (self.calendar <= self.end)]
        self.products = list(products)
        mapping = pd.read_csv(mapping_path).fillna('')
        mapping['date'] = pd.to_datetime(mapping.date).dt.normalize()
        mapping = mapping.loc[mapping.continuous_symbol_vt.isin(products) &
                              mapping.date.between(self.start,self.end)].copy()
        if mapping.duplicated(['date','continuous_symbol_vt']).any():
            raise ValueError('duplicate_mapping')
        mapping['native_symbol'] = mapping.main_contract_vt
        mapping['contract_epoch_id'] = ''
        info = {}
        for index, row in mapping.loc[mapping.main_contract_vt.ne('')].iterrows():
            identity = mapping_identity({**row.to_dict(),'date':row.date.date()})
            epoch = identity['contract_epoch_id']
            vt = research_symbol(row.continuous_symbol_vt,identity['contract_yyyymm'])
            mapping.at[index,'contract_epoch_id'] = epoch
            mapping.at[index,'main_contract_vt'] = vt
            record = dict(contract_epoch_id=epoch,research_symbol=vt,native_symbol=row.native_symbol,
                          product_vt_symbol=row.continuous_symbol_vt)
            if epoch in info and info[epoch] != record:
                raise ValueError('inconsistent_epoch_mapping')
            info[epoch] = record
        self.info = pd.DataFrame(info.values()).sort_values('research_symbol').reset_index(drop=True)
        if self.info.research_symbol.duplicated().any():
            raise ValueError('nonunique_research_identity')
        self.mapping = mapping
        path = Path(db_path).resolve()
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
            db.execute('PRAGMA query_only=ON')
            raw = pd.read_sql_query('SELECT contract_epoch_id,trade_date,open,high,low,close,volume,close_oi,open_oi,source_id FROM daily_bars WHERE trade_date>=? AND trade_date<=? ORDER BY contract_epoch_id,trade_date', db,
                                    params=[str(self.start.date()),str(self.end.date())])
        raw = raw.loc[raw.contract_epoch_id.isin(info)].copy()
        raw['date'] = pd.to_datetime(raw.trade_date)
        if raw.duplicated(['contract_epoch_id','date']).any():
            raise ValueError('duplicate_clean_contract_date')
        if not raw.date.isin(self.calendar).all():
            raise ValueError('bar_outside_source_calendar')
        self.frames = {}
        for epoch, frame in raw.groupby('contract_epoch_id',sort=False):
            vt = info[epoch]['research_symbol']
            self.frames[vt] = frame.reset_index(drop=True)
        self.raw_row_count = len(raw)
        self.missing_held = set()

    def pairwise_bars(self, symbol, asof):
        frame = self.frames.get(symbol)
        if frame is None:
            raise ValueError(f'missing_exact_epoch:{symbol}')
        bounded = frame.loc[frame.date <= pd.Timestamp(asof).normalize()].copy()
        if bounded.empty:
            raise ValueError(f'missing_exact_epoch_asof:{symbol}:{asof}')
        if bounded.date.max() != pd.Timestamp(asof).normalize():
            raise ValueError(f'stale_exact_epoch_asof:{symbol}:{asof}')
        return bounded.reset_index(drop=True)

    def coverage(self, *, warmup_window=120):
        grid = pd.MultiIndex.from_product([self.calendar,self.products],names=['date','product_vt_symbol'])
        frame = self.mapping.rename(columns={'continuous_symbol_vt':'product_vt_symbol'}).set_index(['date','product_vt_symbol'])
        result = frame.reindex(grid)[['main_contract_vt','contract_epoch_id']].fillna('').reset_index()
        result['mapped'] = result.main_contract_vt.ne('')
        result['real_main_bar'] = False
        result['warmup_complete'] = False
        for symbol, group in result.loc[result.mapped].groupby('main_contract_vt'):
            observed = self.frames[symbol].date if symbol in self.frames else []
            result.loc[group.index,'real_main_bar'] = group.date.isin(observed).to_numpy()
            complete = ready_dates(observed,self.calendar,warmup_window)
            result.loc[group.index,'warmup_complete'] = complete.reindex(group.date).to_numpy()
        result['held_bar_missing'] = [(d.strftime('%Y-%m-%d'),p) in self.missing_held for d,p in zip(result.date,result.product_vt_symbol)]
        result['observed'] = result.real_main_bar & result.warmup_complete & ~result.held_bar_missing
        return result

    def fill_engine(self, engine, BarData, Exchange, Interval):
        from zoneinfo import ZoneInfo
        engine.history_data.clear()
        engine.dts.clear()
        for vt_symbol in engine.vt_symbols:
            frame = self.frames.get(vt_symbol)
            if frame is None:
                continue
            symbol, ex = vt_symbol.split('.')
            for row in frame.itertuples():
                dt = row.date.to_pydatetime().replace(tzinfo=ZoneInfo('Asia/Shanghai'))
                bar = BarData(symbol=symbol,exchange=Exchange(ex),datetime=dt,interval=Interval.DAILY,
                              open_price=float(row.open),high_price=float(row.high),low_price=float(row.low),
                              close_price=float(row.close),volume=float(row.volume),open_interest=float(row.close_oi),
                              gateway_name='STAGE267_CLEAN_READ_ONLY')
                engine.history_data[(dt,vt_symbol)] = bar
                engine.dts.add(dt)
        if len(engine.dts) != len(self.calendar):
            raise ValueError('incomplete_source_calendar')
