"""Frozen Stage268 market environment, independent of strategy PnL.

Only exact-contract close/volume/close-OI observations are read. The daily
reference is chosen at the preceding source-calendar close. This is an
environment statistic, not a costless investable continuous price series.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right, insort
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3

import numpy as np
import pandas as pd

EXPECTED_DB_SHA256 = 'a63f92ce7e1d51080ba92f7214fc493f1e6a69aa0079d6ecef7190eea9b58711'
FORMAL19 = frozenset({'GFEX.LC','SHFE.AU','SHFE.CU','CZCE.MA','CZCE.OI','CZCE.AP',
    'CZCE.SM','CZCE.SA','SHFE.RB','DCE.JM','SHFE.HC','CZCE.CF','CZCE.FG','CZCE.SH',
    'GFEX.SI','SHFE.RU','DCE.LH','SHFE.SP','SHFE.FU'})
SECTOR_PRODUCTS = {
    '黑色': 'SHFE.RB SHFE.HC SHFE.WR SHFE.SS DCE.I DCE.J DCE.JM CZCE.SF CZCE.SM CZCE.TC CZCE.ZC',
    '有色/新能源': 'SHFE.AL SHFE.AO SHFE.CU SHFE.NI SHFE.PB SHFE.SN SHFE.ZN SHFE.AD INE.BC GFEX.SI GFEX.LC GFEX.PS',
    '贵金属': 'SHFE.AU SHFE.AG GFEX.PD GFEX.PT',
    '能源化工': 'SHFE.RU SHFE.BR SHFE.BU SHFE.FU INE.LU INE.NR INE.SC DCE.BZ DCE.EB DCE.EG DCE.L DCE.PG DCE.PP DCE.V CZCE.FG CZCE.MA CZCE.ME CZCE.PF CZCE.PL CZCE.PR CZCE.PX CZCE.SA CZCE.SH CZCE.TA CZCE.UR',
    '农林': 'DCE.A DCE.B DCE.BB DCE.C DCE.CS DCE.FB DCE.JD DCE.LG DCE.LH DCE.M DCE.P DCE.RR DCE.Y CZCE.AP CZCE.CF CZCE.CJ CZCE.CY CZCE.ER CZCE.JR CZCE.LR CZCE.OI CZCE.PK CZCE.PM CZCE.RI CZCE.RM CZCE.RO CZCE.RS CZCE.SR CZCE.WH CZCE.WS CZCE.WT SHFE.SP SHFE.OP',
    '股指': 'CFFEX.IC CFFEX.IF CFFEX.IH CFFEX.IM',
    '利率': 'CFFEX.T CFFEX.TF CFFEX.TL CFFEX.TS',
    '其他商品/运价': 'INE.EC',
}
PRODUCT_SECTORS = {pid: sector for sector, values in SECTOR_PRODUCTS.items() for pid in values.split()}
WINDOWS = (20, 60, 120)
PRIMARY_COLUMNS = ['date','market_er60','raw_market_er60','gate_pass','coverage_ratio',
    'active_products','valid_products','commodity_er60','sector_equal_er60',
    'outside_pool_er60','own_pool_er60','market_er20','market_er120','market_vol60',
    'direction_breadth60','market_corr60','er60_expanding_pct','regime']


def _calendar(values):
    result = pd.DatetimeIndex(pd.to_datetime(values)).normalize()
    if result.has_duplicates or not result.is_monotonic_increasing or result.hasnans:
        raise ValueError('calendar must be unique, increasing, finite source dates')
    return result


def load_calendar(path):
    raw = np.load(path, allow_pickle=False)
    if np.issubdtype(raw.dtype, np.integer):
        return _calendar(pd.to_datetime(raw.astype(str), format='%Y%m%d'))
    if np.issubdtype(raw.dtype, np.datetime64):
        return _calendar(raw)
    raise ValueError('calendar requires YYYYMMDD integers or datetime64')


def _rolling_efficiency(returns, window):
    count = returns.notna().astype(int).rolling(window, min_periods=window).sum()
    net = returns.rolling(window, min_periods=window).sum()
    path = returns.abs().rolling(window, min_periods=window).sum()
    complete = count.eq(window)
    zero = complete & path.eq(0)
    er = (net.abs() / path).where(complete).mask(zero, 0.0)
    # Floating addition can produce tiny >1 roundoff for monotone paths.
    return er.clip(0, 1), zero, net.where(complete)


def build_product_features(bars, calendar, *, start_date, end_date):
    """Return a complete source-date x ordinary historical product panel.

    Fields: date, product_id, reference_epoch, r, return_status, active,
    observed, traded, age_source_days, er20/60/120, zero_path20/60/120,
    vol60 (sample std * sqrt(252)), sum60. No future source rows are used.
    """
    cal = _calendar(calendar)
    end = pd.Timestamp(end_date).normalize()
    start = pd.Timestamp(start_date).normalize()
    cal = cal[cal <= end]
    if start > end or not len(cal):
        raise ValueError('empty date scope')
    required = {'trade_date','exchange','product','contract_epoch_id','close','volume','close_oi'}
    if not required <= set(bars):
        raise ValueError(f'missing bar fields: {sorted(required-set(bars))}')
    b = bars[list(required)].copy()
    b['trade_date'] = pd.to_datetime(b.trade_date).dt.normalize()
    b = b.loc[(b.trade_date <= end) & ~b['product'].str.endswith('_F')].copy()
    if b.duplicated(['contract_epoch_id','trade_date']).any():
        raise ValueError('duplicate exact-contract source dates')
    if not b.trade_date.isin(cal).all():
        raise ValueError('bar date is not in the explicit source calendar')
    b['product_id'] = b.exchange + '.' + b['product']
    identity_ok = b.contract_epoch_id.str.match(r'^[A-Z]+\.[A-Z]+\.\d{6}$')
    identity_ok &= b.contract_epoch_id.str.rsplit('.', n=1).str[0].eq(b.product_id)
    if not identity_ok.all():
        raise ValueError('noncanonical or conflicting product identity')
    result = []
    for pid, group in b.groupby('product_id', sort=True):
        observed_rows = group.loc[np.isfinite(group.close) & group.close.gt(0)]
        observed = pd.Series(cal.isin(observed_rows.trade_date), index=cal)
        traded_rows = observed_rows.loc[np.isfinite(observed_rows.volume) & observed_rows.volume.gt(0)]
        traded = pd.Series(cal.isin(traded_rows.trade_date), index=cal)
        age = np.arange(len(cal), dtype=float)
        if len(observed_rows):
            age -= cal.get_indexer([observed_rows.trade_date.min()])[0]
        else:
            age[:] = np.nan
        active = (age >= 61) & traded.astype(int).rolling(20, min_periods=1).sum().gt(0)
        candidates = traded_rows.loc[np.isfinite(traded_rows.close_oi) & traded_rows.close_oi.ge(0)]
        winners = (candidates.sort_values(['trade_date','close_oi','volume','contract_epoch_id'],
                       ascending=[True,False,False,True])
                    .drop_duplicates('trade_date').set_index('trade_date'))
        zero_oi_days = set(winners.index[winners.close_oi.eq(0)])
        positive = winners.loc[winners.close_oi.gt(0)]
        references = positive.contract_epoch_id.reindex(cal).shift(1).fillna('')
        previous_close = positive.close.reindex(cal).shift(1)
        exact_closes = observed_rows.set_index(['trade_date','contract_epoch_id']).close
        current = pd.Series(exact_closes.reindex(pd.MultiIndex.from_arrays([cal, references])).to_numpy(), index=cal)
        r = np.log(current / previous_close)
        status = pd.Series('ok',index=cal)
        status.loc[references.eq('')] = 'missing_previous_reference'
        previous_days = pd.Series(cal, index=cal).shift(1)
        status.loc[previous_days.isin(zero_oi_days)] = 'all_oi_zero'
        status.loc[references.ne('') & current.isna()] = 'missing_current_bar'
        frame = pd.DataFrame(dict(date=cal, product_id=pid, reference_epoch=references.to_numpy(),
            r=r.to_numpy(), return_status=status.to_numpy(), observed=observed.to_numpy(),
            traded=traded.to_numpy(), age_source_days=age, active=np.asarray(active)))
        for window in WINDOWS:
            er, zero, net = _rolling_efficiency(r, window)
            frame[f'er{window}'] = er.to_numpy()
            frame[f'zero_path{window}'] = zero.to_numpy()
            if window == 60:
                frame['sum60'] = net.to_numpy()
        frame['vol60'] = (r.rolling(60, min_periods=60).std(ddof=1) * np.sqrt(252)).to_numpy()
        result.append(frame.loc[frame.date.ge(start)])
    return pd.concat(result, ignore_index=True) if result else pd.DataFrame()


def expanding_percentile(values, min_history=252):
    """Prior-only empirical percentile; ties get half their prior mass."""
    history=[]
    pct=[]
    groups=[]
    for value in values:
        if np.isfinite(value) and len(history) >= min_history:
            rank=(bisect_left(history, value)+bisect_right(history, value))/(2*len(history))
            pct.append(rank)
            groups.append('low' if rank <= 1/3 else 'mid' if rank <= 2/3 else 'high')
        else:
            pct.append(np.nan)
            groups.append('')
        if np.isfinite(value):
            insort(history, float(value))
    return pd.Series(pct,index=values.index),pd.Series(groups,index=values.index)


def _gate(active, valid, sectors):
    active_n = len(active)
    valid_n = len(valid)
    ratio = valid_n / active_n if active_n else np.nan
    commodity_n = int((~valid.product_id.str.startswith('CFFEX.')).sum())
    active_counts = active.product_id.map(sectors).value_counts()
    valid_counts = valid.product_id.map(sectors).value_counts()
    valid_sectors = int(valid_counts.gt(0).sum())
    sector_cover = valid_counts.reindex(active_counts.index,fill_value=0) / active_counts
    reasons=[]
    if not active_n or ratio < 0.9:
        reasons.append('coverage_below_90pct')
    if commodity_n < 15:
        reasons.append('commodity_products_below_15')
    if valid_sectors < 5:
        reasons.append('valid_sectors_below_5')
    if (sector_cover < 0.8).any():
        reasons.append('sector_coverage_below_80pct')
    return dict(gate_pass=not reasons, coverage_ratio=ratio, active_products=active_n,
        valid_products=valid_n, valid_commodity_products=commodity_n,
        active_sectors=len(active_counts),valid_sectors=valid_sectors,
        minimum_sector_coverage=float(sector_cover.min()) if len(sector_cover) else np.nan,
        gate_reasons=';'.join(reasons))


def aggregate_market(product_features, sectors):
    """Market and sector tables. Auxiliary medians use the valid active set.

    Every auxiliary set has valid/active counts and coverage. ER20/120 apply
    the same frozen quality gates independently. Only M is gate-certified;
    raw_M and auxiliary valid-set diagnostics never imply complete coverage.
    """
    f=product_features.copy()
    if not f.product_id.isin(sectors).all():
        raise ValueError(f'unmapped product sectors: {sorted(set(f.product_id)-set(sectors))}')
    f['date']=pd.to_datetime(f.date)
    rows=[]
    sector_rows=[]
    return_panel=f.pivot(index='date',columns='product_id',values='r').sort_index()
    for day, all_day in f.groupby('date',sort=True):
        active=all_day.loc[all_day.active]
        valid=active.loc[np.isfinite(active.er60)]
        gate=_gate(active,valid,sectors)
        raw=float(valid.er60.median()) if len(valid) else np.nan
        row=dict(date=day,market_er60=raw if gate['gate_pass'] else np.nan,
            raw_market_er60=raw,**gate)
        for name,mask in [('commodity',~active.product_id.str.startswith('CFFEX.')),
                          ('outside_pool',~active.product_id.isin(FORMAL19)),
                          ('own_pool',active.product_id.isin(FORMAL19))]:
            subset=active.loc[mask]
            usable=subset.loc[np.isfinite(subset.er60)]
            row[f'{name}_er60']=float(usable.er60.median()) if len(usable) else np.nan
            row[f'{name}_active_products']=len(subset)
            row[f'{name}_valid_products']=len(usable)
            row[f'{name}_coverage_ratio']=len(usable)/len(subset) if len(subset) else np.nan
        sector_medians=[]
        for sector in dict.fromkeys(sectors.values()):
            subset=active.loc[active.product_id.map(sectors).eq(sector)]
            usable=subset.loc[np.isfinite(subset.er60)]
            median=float(usable.er60.median()) if len(usable) else np.nan
            if len(usable):
                sector_medians.append(median)
            sector_rows.append(dict(date=day,sector=sector,active_products=len(subset),
                valid_products=len(usable),coverage_ratio=len(usable)/len(subset) if len(subset) else np.nan,
                er60=median,active_product_ids='|'.join(subset.product_id),
                valid_product_ids='|'.join(usable.product_id)))
        row['sector_equal_er60']=float(np.mean(sector_medians)) if sector_medians else np.nan
        row['sector_equal_valid_sectors']=len(sector_medians)
        row['sector_equal_active_sectors']=gate['active_sectors']
        for window in (20,120):
            usable=active.loc[np.isfinite(active[f'er{window}'])]
            g=_gate(active,usable,sectors)
            raw_w=float(usable[f'er{window}'].median()) if len(usable) else np.nan
            row[f'market_er{window}']=raw_w if g['gate_pass'] else np.nan
            row[f'raw_market_er{window}']=raw_w
            for key,value in g.items():
                row[f'er{window}_{key}']=value
        row['market_vol60']=float(valid.vol60.median()) if len(valid) else np.nan
        row['direction_breadth60']=float(abs(np.sign(valid.sum60).mean())) if len(valid) else np.nan
        row['diagnostic_valid_products']=len(valid)
        row['diagnostic_coverage_ratio']=gate['coverage_ratio']
        row['zero_path60_products']=int(valid.zero_path60.sum())
        last60=return_panel.loc[:day].tail(60).reindex(columns=valid.product_id)
        corr=last60.corr(min_periods=60).to_numpy()
        pairs=corr[np.triu_indices(len(corr),k=1)]
        finite=pairs[np.isfinite(pairs)]
        row['market_corr60']=float(finite.mean()) if len(finite) else np.nan
        row['correlation_valid_pairs']=len(finite)
        row['correlation_possible_pairs']=len(valid)*(len(valid)-1)//2
        row['active_product_ids']='|'.join(active.product_id)
        row['valid_product_ids']='|'.join(valid.product_id)
        row['missing_product_ids']='|'.join(active.loc[~np.isfinite(active.er60)].product_id)
        row['ordinary_observed_products']=int(all_day.observed.sum()) if 'observed' in all_day else np.nan
        rows.append(row)
    daily=pd.DataFrame(rows)
    daily['er60_expanding_pct'],daily['regime']=expanding_percentile(daily.market_er60)
    daily=daily[PRIMARY_COLUMNS+[c for c in daily if c not in PRIMARY_COLUMNS]]
    return daily,pd.DataFrame(sector_rows)


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def _plain(value):
    if isinstance(value,(np.integer,)): return int(value)
    if isinstance(value,(np.floating,)): return float(value)
    if isinstance(value,(np.bool_,)): return bool(value)
    if isinstance(value,(pd.Timestamp,)): return value.strftime('%Y-%m-%d')
    raise TypeError(type(value).__name__)



def write_cached_coverage_diagnostics(output_dir):
    """Summarize already computed market caches; never reads bars or PnL."""
    out=Path(output_dir)
    f=pd.read_csv(out/'product_features.csv.gz',parse_dates=['date'])
    sectors=pd.read_csv(out/'sector_daily.csv',parse_dates=['date'])
    daily=pd.read_csv(out/'market_daily.csv',parse_dates=['date'])
    rows=[]
    year_rows=[]
    for pid,g in f.groupby('product_id',sort=True):
        a=g.loc[g.active]
        v=a.loc[a.er60.notna()]
        observed=g.loc[g.observed,'date']
        traded=g.loc[g.traded,'date']
        rows.append(dict(product_id=pid,sector=PRODUCT_SECTORS[pid],
            in_formal19=pid in FORMAL19,first_observed=observed.min(),last_observed=observed.max(),
            first_traded=traded.min(),last_traded=traded.max(),active_days=len(a),
            valid_er60_days=len(v),valid_er60_coverage=len(v)/len(a) if len(a) else np.nan,
            valid_er20_days=int(a.er20.notna().sum()),valid_er120_days=int(a.er120.notna().sum()),
            missing_return_days=int(a.r.isna().sum()),
            missing_current_bar_days=int(a.return_status.eq('missing_current_bar').sum()),
            all_oi_zero_days=int(a.return_status.eq('all_oi_zero').sum()),
            missing_previous_reference_days=int(a.return_status.eq('missing_previous_reference').sum()),
            zero_path60_days=int(v.zero_path60.sum())))
        for year,yg in a.groupby(a.date.dt.year):
            year_rows.append(dict(year=year,product_id=pid,sector=PRODUCT_SECTORS[pid],
                active_days=len(yg),valid_er60_days=int(yg.er60.notna().sum()),
                er60_coverage=float(yg.er60.notna().mean()),
                missing_return_days=int(yg.r.isna().sum()),
                missing_current_bar_days=int(yg.return_status.eq('missing_current_bar').sum()),
                all_oi_zero_days=int(yg.return_status.eq('all_oi_zero').sum()),
                missing_previous_reference_days=int(yg.return_status.eq('missing_previous_reference').sum())))
    product=pd.DataFrame(rows)
    by_year_product=pd.DataFrame(year_rows)
    product.to_csv(out/'coverage_by_product.csv',index=False,date_format='%Y-%m-%d',float_format='%.17g')
    by_year_product.to_csv(out/'coverage_by_year_product.csv',index=False,float_format='%.17g')
    year_sector=[]
    for (year,sector),g in sectors.groupby([sectors.date.dt.year,'sector'],sort=True):
        total=int(g.active_products.sum())
        valid=int(g.valid_products.sum())
        year_sector.append(dict(year=year,sector=sector,active_product_days=total,
            valid_product_days=valid,coverage_ratio=valid/total if total else np.nan,
            active_days=int(g.active_products.gt(0).sum()),
            sector_gate_fail_days=int((g.active_products.gt(0)&g.coverage_ratio.lt(.8)).sum())))
    pd.DataFrame(year_sector).to_csv(out/'coverage_by_year_sector.csv',index=False,float_format='%.17g')
    # Exact reference keys make observed gap causes inspectable without redoing cleaning QA.
    gaps=f.loc[f.active & f.r.isna(),['date','product_id','reference_epoch','return_status']]
    gaps.to_csv(out/'missing_return_days.csv.gz',index=False,compression='gzip',date_format='%Y-%m-%d')
    summary=json.loads((out/'market_summary.json').read_text())
    primary=daily.loc[daily.date.ge('2020-01-02')]
    summary['primary_calendar_days']=len(primary)
    summary['primary_gate_pass_days']=int(primary.gate_pass.sum())
    summary['primary_classified_days']=int(primary.regime.notna().sum())
    summary['first_classified_date']=primary.loc[primary.regime.notna(),'date'].min().strftime('%Y-%m-%d')
    summary['primary_regime_counts']=primary.regime.value_counts().to_dict()
    summary['primary_coverage_failure_verdict']='insufficient_predeclared_cross_year_coverage_no_gate_relaxation'
    summary['coverage_limitation']='Only 142 classified dates, all in 2025-2026; 2020-2024 have no prior-252-history qualified classifications. Frozen full-period multi-year inference cannot be supported by this coverage.'
    summary['coverage_diagnostics_from_cache_only']=True
    summary['source_code_sha256']=sha256(Path(__file__))
    for name in ['coverage_precheck.json','coverage_precheck.csv','coverage_by_product.csv',
                 'coverage_by_year_product.csv','coverage_by_year_sector.csv','missing_return_days.csv.gz']:
        summary['output_sha256'][name]=sha256(out/name)
    (out/'market_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',required=True)
    parser.add_argument('--calendar',required=True)
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--start-date',default='2010-01-04')
    parser.add_argument('--end-date',default='2026-10-14')
    args=parser.parse_args(argv)
    out=Path(args.output_dir).resolve()
    out.mkdir(parents=True,exist_ok=True)
    names=['product_sectors.json','product_features.csv.gz','market_daily.csv','sector_daily.csv','market_summary.json']
    if any((out/name).exists() for name in names):
        raise FileExistsError('frozen market outputs already exist; no silent rerun or overwrite')
    mapping=dict(recorded_at=datetime.now().astimezone().isoformat(),
        declared_before_feature_computation=True,strategy_pnl_accessed=False,
        definition='Fixed industrial taxonomy; historical codes remain separate votes. SS is black; rubber/glass/soda are chemical; forest/paper products are agricultural/forest; GFEX PT/PD are precious.',
        sectors=list(SECTOR_PRODUCTS),product_sectors=PRODUCT_SECTORS,
        formal19=sorted(FORMAL19),excluded_product_families=['DCE.L_F','DCE.PP_F','DCE.V_F'])
    (out/'product_sectors.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n')
    db=Path(args.db).resolve()
    calendar=Path(args.calendar).resolve()
    source_sha=sha256(db)
    if source_sha != EXPECTED_DB_SHA256:
        raise ValueError(f'clean DB identity changed: {source_sha}')
    source_stat=db.stat()
    cal=load_calendar(calendar)
    with sqlite3.connect(f'file:{db}?mode=ro',uri=True) as conn:
        bars=pd.read_sql_query('SELECT trade_date,exchange,product,contract_epoch_id,close,volume,close_oi FROM daily_bars WHERE trade_date <= ? AND quality_status = ?',conn,params=[args.end_date,'accepted'])
    universe=set(bars.loc[~bars['product'].str.endswith('_F'),'exchange']+'.'+bars.loc[~bars['product'].str.endswith('_F'),'product'])
    if universe != set(PRODUCT_SECTORS) or len(universe)!=94:
        raise ValueError(f'frozen ordinary taxonomy mismatch missing={set(universe)-set(PRODUCT_SECTORS)} extra={set(PRODUCT_SECTORS)-set(universe)}')
    print(json.dumps(dict(phase='input_ready',rows=len(bars),ordinary_products=len(universe),source_sha256=source_sha)),flush=True)
    features=build_product_features(bars,cal,start_date=args.start_date,end_date=args.end_date)
    features.to_csv(out/'product_features.csv.gz',index=False,compression='gzip',float_format='%.17g',date_format='%Y-%m-%d')
    del bars
    print(json.dumps(dict(phase='product_features_ready',rows=len(features))),flush=True)
    preflight=[]
    for day, group in features.groupby('date',sort=True):
        active=group.loc[group.active]
        valid=active.loc[np.isfinite(active.er60)]
        preflight.append(dict(date=day,**_gate(active,valid,PRODUCT_SECTORS)))
    preflight=pd.DataFrame(preflight)
    preflight.to_csv(out/'coverage_precheck.csv',index=False,date_format='%Y-%m-%d')
    early=dict(phase='coverage_precheck',calendar_days=len(preflight),
        gate_pass_days=int(preflight.gate_pass.sum()),
        primary_days=int(preflight.date.ge('2020-01-02').sum()),
        primary_gate_pass_days=int(preflight.loc[preflight.date.ge('2020-01-02'),'gate_pass'].sum()),
        per_year={str(y):dict(days=len(g),pass_days=int(g.gate_pass.sum()),
            coverage_median=float(g.coverage_ratio.median()),
            reasons=g.loc[~g.gate_pass,'gate_reasons'].value_counts().to_dict())
            for y,g in preflight.groupby(preflight.date.dt.year)})
    (out/'coverage_precheck.json').write_text(json.dumps(early,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(early,ensure_ascii=False),flush=True)
    daily,sectors=aggregate_market(features,PRODUCT_SECTORS)
    daily.to_csv(out/'market_daily.csv',index=False,float_format='%.17g',date_format='%Y-%m-%d')
    sectors.to_csv(out/'sector_daily.csv',index=False,float_format='%.17g',date_format='%Y-%m-%d')
    end_sha=sha256(db)
    if end_sha!=source_sha or db.stat().st_size!=source_stat.st_size or db.stat().st_mtime_ns!=source_stat.st_mtime_ns:
        raise ValueError('source database changed during computation')
    counts={}
    for year,g in daily.groupby(daily.date.dt.year):
        counts[str(year)]=dict(source_days=len(g),gate_pass_days=int(g.gate_pass.sum()),
            classified_days=int(g.regime.ne('').sum()),coverage_min=float(g.coverage_ratio.min()),
            coverage_median=float(g.coverage_ratio.median()),coverage_max=float(g.coverage_ratio.max()),
            active_median=float(g.active_products.median()),valid_median=float(g.valid_products.median()),
            regimes=g.loc[g.regime.ne(''),'regime'].value_counts().to_dict())
    summary=dict(stage='stage269_market_features',recorded_at=datetime.now().astimezone().isoformat(),
        strategy_pnl_accessed=False,financial_replays=0,downloads=0,AI_training=0,market_feature_computation_runs=1,
        protocol='Stage268 frozen 2026-10-17 21:34',source_db=str(db),source_db_sha256=source_sha,
        source_bytes_unchanged=True,calendar=str(calendar),calendar_sha256=sha256(calendar),
        start_date=args.start_date,end_date=args.end_date,ordinary_products=len(universe),
        product_ids=sorted(universe),excluded_families=mapping['excluded_product_families'],
        formal19=sorted(FORMAL19),calendar_days=len(daily),gate_pass_days=int(daily.gate_pass.sum()),
        classified_days=int(daily.regime.ne('').sum()),
        first_gate_pass=daily.loc[daily.gate_pass,'date'].min(),last_gate_pass=daily.loc[daily.gate_pass,'date'].max(),
        per_year=counts,gate_reason_counts=daily.loc[~daily.gate_pass,'gate_reasons'].value_counts().to_dict(),
        coverage_qualified_for_requested_primary_sample=bool(daily.loc[daily.date.ge('2020-01-02'),'gate_pass'].all()),
        quality_gate='ER60 complete 60 adjacent source-day returns; active age>=61 and true trade in last20; coverage>=90%, commodity>=15, valid sectors>=5, every active sector>=80%',
        auxiliary_scope='ER60 auxiliaries use valid mature-active products; explicit subset counts/coverage. Vol60 ddof1 annualization sqrt252; breadth=abs(mean(sign(sum60r))); corr=mean finite upper-triangle pairs in complete 60r valid set, zero-variance pairs excluded and counted.',
        sensitivity_gate='ER20 and ER120 use the identical active denominator and quality gates independently; no percentile regrouping for auxiliary measures',
        percentile='prior-only valid M history; 252 prior observations; (n_less+0.5*n_equal)/n_history; <=1/3 low, <=2/3 mid, >2/3 high',
        historical_identity_limitation='Exchange historical codes retained separately, no mechanical economic deduplication or price splicing.',
        research_judgement='Descriptive market environment validation only; no parameters chosen by strategy results and no trading-rule claim.',
        output_sha256={name:sha256(out/name) for name in names[:-1]})
    (out/'market_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=_plain,allow_nan=False)+'\n')
    write_cached_coverage_diagnostics(out)
    print(json.dumps({k:summary[k] for k in ['calendar_days','gate_pass_days','classified_days','per_year']},ensure_ascii=False,default=_plain),flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
