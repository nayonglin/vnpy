"""Read-only all-market daily research source; never a financial replay or production loader.

A main contract for t is selected solely from real bars at the immediately
preceding source-calendar session. Missing observations never carry forward.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
LINE = ROOT / 'research/lines/futures_trend_full_market_noai_one_lot'
SOURCE_ROOT = Path('/Users/mac/Desktop/fian')
SOURCE_LINE = SOURCE_ROOT / 'research/lines/futures_trend_rollover_shape_same_volume/outputs'
DEFAULT_INPUTS = LINE / 'outputs/inputs'
START = '2014-01-01'
TRADE_START = '2015-01-01'
END = '2026-10-16'
EXPECTED_CLEAN_SHA256 = 'a63f92ce7e1d51080ba92f7214fc493f1e6a69aa0079d6ecef7190eea9b58711'


def identity(path):
    path = Path(path).resolve()
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=h.hexdigest())


def product_symbol(exchange, product):
    value = product if exchange in {'CZCE', 'CFFEX'} else product.lower()
    if product.endswith('_F'):
        value = product[:-2].lower() + '_F'
    return f'{value}.{exchange}'


def research_symbol(exchange, product, yyyymm):
    p, ex = product_symbol(str(exchange), str(product)).split('.')
    return f'{p}{yyyymm}.{ex}'


def build_causal_mapping(market, contracts, calendar, products):
    frame = market.copy()
    frame['date'] = pd.to_datetime(frame.date).dt.strftime('%Y-%m-%d')
    if frame.duplicated(['contract_epoch_id', 'date']).any():
        raise ValueError('duplicate_market_date')
    days = pd.DatetimeIndex(calendar).normalize()
    if days.duplicated().any() or not days.is_monotonic_increasing:
        raise ValueError('invalid_source_calendar')
    if not frame.date.isin(days.strftime('%Y-%m-%d')).all():
        raise ValueError('market_date_outside_calendar')
    next_day = dict(zip(days[:-1].strftime('%Y-%m-%d'), days[1:].strftime('%Y-%m-%d')))
    frame['observation_date'] = frame.date
    frame['date'] = frame.date.map(next_day)
    frame = frame.loc[frame.date.notna()].copy()
    frame['contract_yyyymm'] = frame.contract_yyyymm.astype(str)
    frame = frame.loc[frame.contract_yyyymm.ge(frame.date.str.replace('-', '').str[:6])]
    maturity = contracts.set_index('contract_epoch_id').maturity_date.to_dict() if 'maturity_date' in contracts else {}
    frame['maturity_date'] = frame.contract_epoch_id.map(maturity).fillna('')
    frame = frame.loc[frame.maturity_date.eq('') | frame.date.le(frame.maturity_date)]
    # No t market information, survival, or full-history best-contract filter.
    frame = frame.sort_values(['date','exchange','product','close_oi','volume','contract_epoch_id'],
                              ascending=[True,True,True,False,False,True])
    selected = frame.drop_duplicates(['date','exchange','product']).set_index(['date','exchange','product'])
    grid = pd.MultiIndex.from_tuples([(d,ex,p) for d in days.strftime('%Y-%m-%d') for ex,p in sorted(products)],
                                     names=['date','exchange','product'])
    result = selected.reindex(grid)[['contract_epoch_id','contract_yyyymm','observation_date','close_oi','volume']].reset_index()
    result[['contract_epoch_id','contract_yyyymm','observation_date']] = result[['contract_epoch_id','contract_yyyymm','observation_date']].fillna('')
    result['continuous_symbol_vt'] = [product_symbol(ex,p) for ex,p in zip(result.exchange,result['product'])]
    result['main_contract_vt'] = [research_symbol(ex,p,m) if m else '' for ex,p,m in zip(result.exchange,result['product'],result.contract_yyyymm)]
    result['mapping_status'] = np.where(result.contract_epoch_id.ne(''),'observed_previous_session','missing_previous_session_eligible_contract')
    return result


def _positive(value):
    try:
        value = float(value)
    except (TypeError,ValueError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def _meta_epoch(row):
    match = re.fullmatch(r'[A-Z]+(\d{4})F?', str(row.get('order_book_id','')))
    if not match:
        return None
    yy_mm = match.group(1)
    return f"{row['exchange']}.{row['underlying_symbol']}.20{yy_mm}"


def resolve_metadata(contracts, instrument_rows, info_rows):
    instruments = {}
    for row in instrument_rows:
        key = _meta_epoch(row)
        if key:
            if key in instruments and instruments[key] != row:
                raise ValueError(f'duplicate_instrument_metadata:{key}')
            instruments[key] = row
    exact_info = {str(x['order_book_id']): x for x in info_rows if x.get('order_book_id')}
    product_info = {str(x['underlying_symbol']): x for x in info_rows if x.get('underlying_symbol')}
    rows = []
    for contract in contracts.itertuples(index=False):
        epoch = str(contract.contract_epoch_id)
        meta = instruments.get(epoch)
        if not meta or _positive(meta.get('contract_multiplier')) is None:
            raise ValueError(f'metadata_missing_exact_contract_multiplier:{epoch}')
        order_book_id = str(meta['order_book_id'])
        info = exact_info.get(order_book_id) or product_info.get(str(contract.product)) or {}
        info_source = 'rq_exact_contract' if order_book_id in exact_info else 'rq_product_fallback'
        tick = _positive(info.get('tick_size'))
        if tick is None:
            raise ValueError(f'tick_missing:{epoch}')
        exact_fee_margin = _positive(info.get('margin_rate')) if order_book_id in exact_info else None
        instrument_margin = _positive(meta.get('margin_rate'))
        margin = exact_fee_margin or instrument_margin or _positive(info.get('margin_rate'))
        margin_source = 'rq_exact_contract' if exact_fee_margin else ('rq_exact_instrument' if instrument_margin else 'rq_product_fallback')
        if margin is None:
            raise ValueError(f'margin_missing:{epoch}')
        fee_keys = ['open_commission_ratio','close_commission_ratio','close_commission_today_ratio']
        fee_type = info.get('commission_type')
        if fee_type not in {'by_money','by_volume'} or any(k not in info for k in fee_keys):
            raise ValueError(f'commission_missing:{epoch}')
        fees = [float(info[k]) for k in fee_keys]
        if any(not math.isfinite(v) or v < 0 for v in fees):
            raise ValueError(f'commission_invalid:{epoch}')
        native = str(meta.get('trading_code') or '')
        if not native:
            p = str(contract.product).replace('_F','')
            p = p if contract.exchange in {'CZCE','CFFEX'} else p.lower()
            native = p + str(contract.contract_yyyymm)[2:] + ('F' if str(contract.product).endswith('_F') else '')
        vt = research_symbol(str(contract.exchange),str(contract.product),str(contract.contract_yyyymm))
        size = float(meta['contract_multiplier'])
        # Existing formal jm uses two ticks; all other existing formal products use one.
        slippage = max(tick, 1.0) if contract.exchange == 'DCE' and contract.product == 'JM' else tick
        row = dict(contract_epoch_id=epoch,vt_symbol=vt,research_symbol=vt,
                   product_vt_symbol=product_symbol(str(contract.exchange),str(contract.product)),
                   native_symbol=f'{native}.{contract.exchange}',exchange=contract.exchange,product=contract.product,
                   contract_yyyymm=str(contract.contract_yyyymm),size=size,pricetick=tick,margin_ratio=margin,slippage=slippage,
                   rate=fees[0] if fee_type=='by_money' else 0.0,
                   rate_open=fees[0] if fee_type=='by_money' else 0.0,
                   rate_close=fees[1] if fee_type=='by_money' else 0.0,
                   rate_close_today=fees[2] if fee_type=='by_money' else 0.0,
                   fee_per_lot_open=fees[0] if fee_type=='by_volume' else 0.0,
                   fee_per_lot_close=fees[1] if fee_type=='by_volume' else 0.0,
                   fee_per_lot_close_today=fees[2] if fee_type=='by_volume' else 0.0,
                   commission_type=fee_type,fee_method=fee_type,fee_open=fees[0],fee_close=fees[1],fee_close_today=fees[2],volume_multiple=size,commission_status=f'observed_{fee_type}',
                   multiplier_source='rq_exact_contract',tick_fee_source=info_source,
                   margin_source=margin_source,
                   metadata_time_basis='vendor_snapshot_not_historical_daily_PIT',
                   slippage_source='fixed_one_tick_except_formal_JM_min_1_price_unit',
                   listed_date=meta.get('listed_date',''),maturity_date=meta.get('maturity_date',''))
        rows.append(row)
    result = pd.DataFrame(rows).sort_values('vt_symbol').reset_index(drop=True)
    if result.vt_symbol.duplicated().any():
        raise ValueError('duplicate_research_symbol')
    return result


def build_source(output_dir=DEFAULT_INPUTS):
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise ValueError('source_output_exists_refusing_overwrite')
    rq = SOURCE_LINE / 'stage265_deep_daily/rqalpha'
    inputs = dict(clean=SOURCE_LINE/'stage266_clean_daily/clean_daily.sqlite',
                  instruments=rq/'futures_metadata.json',future_info=rq/'future_info.json',calendar=rq/'trading_dates.npy')
    fingerprints = {key: identity(path) for key,path in inputs.items()}
    if fingerprints['clean']['sha256'] != EXPECTED_CLEAN_SHA256:
        raise ValueError('clean_store_changed')
    with closing(sqlite3.connect(inputs['clean'].resolve().as_uri()+'?mode=ro',uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        market = pd.read_sql_query('SELECT contract_epoch_id,exchange,product,contract_yyyymm,trade_date AS date,open,high,low,close,volume,close_oi,open_oi,source_id FROM daily_bars WHERE trade_date>=? AND trade_date<=? ORDER BY contract_epoch_id,trade_date',db,params=[START,END])
        contracts = pd.read_sql_query('SELECT * FROM contracts',db)
    products = sorted(set(map(tuple, market.loc[market.date.ge(TRADE_START),['exchange','product']].to_numpy())))
    if len(products) != 93:
        raise ValueError(f'expected_93_historical_products:{len(products)}')
    market = market.loc[[tuple(x) in products for x in market[['exchange','product']].to_numpy()]].copy()
    calendar = pd.to_datetime(np.load(inputs['calendar'],allow_pickle=False).astype(str),format='%Y%m%d')
    calendar = calendar[(calendar >= START) & (calendar <= END)]
    if str(calendar[-1].date()) != END:
        raise ValueError('calendar_incomplete')
    mapping = build_causal_mapping(market,contracts,calendar,products)
    used_epochs = set(mapping.loc[mapping.contract_epoch_id.ne(''),'contract_epoch_id'])
    chosen_contracts = contracts.loc[contracts.contract_epoch_id.isin(used_epochs)].copy()
    if len(chosen_contracts) != len(used_epochs):
        raise ValueError('missing_contract_identity')
    metadata = resolve_metadata(chosen_contracts,json.loads(inputs['instruments'].read_text()),json.loads(inputs['future_info'].read_text()))
    market = market.loc[market.contract_epoch_id.isin(used_epochs)].copy()
    market['vt_symbol'] = market.contract_epoch_id.map(metadata.set_index('contract_epoch_id').vt_symbol)
    real_keys = pd.MultiIndex.from_frame(market[['date','contract_epoch_id']])
    mapping['real_bar_on_effective_day'] = pd.MultiIndex.from_frame(mapping[['date','contract_epoch_id']]).isin(real_keys)
    mapping['main_contract_native_vt'] = mapping.contract_epoch_id.map(metadata.set_index('contract_epoch_id').native_symbol).fillna('')
    universe = pd.DataFrame(products,columns=['exchange','product'])
    universe['product_vt_symbol'] = [product_symbol(ex,p) for ex,p in products]
    universe['eligible'] = 1
    universe['eligibility_basis'] = 'all_historical_products_with_accepted_clean_observations_since_2015_not_survivor_list'
    manifest = dict(status='all_market_daily_research_inputs_only',financial_replays=0,model_fits=0,
                    start=START,trade_start=TRADE_START,end=END,source_inputs=fingerprints,
                    historical_products=len(products),exchanges=sorted(universe.exchange.unique()),
                    mapping_policy='previous_calendar_session_close_oi_desc_volume_desc_epoch_asc_next_session_effective',
                    candidate_filter='delivery_yyyymm_ge_effective_yyyymm_and_known_maturity_ge_effective_day',
                    contract_epochs=len(used_epochs),market_rows=len(market),source_calendar_days=len(calendar),
                    mapping_grid_rows=len(mapping),mapped_product_days=int(mapping.contract_epoch_id.ne('').sum()),
                    missing_mapping_product_days=int(mapping.contract_epoch_id.eq('').sum()),
                    selected_contract_missing_real_bar_days=int((mapping.contract_epoch_id.ne('') & ~mapping.real_bar_on_effective_day).sum()),
                    tick_fee_sources=metadata.tick_fee_source.value_counts().to_dict(),
                    commission_type_counts=metadata.commission_type.value_counts().to_dict(),
                    boundaries=['Daily source only; cannot reproduce C9 intraday half-R stop/progress ordering or retry.',
                                'Known contract lifecycle is a vendor snapshot; no historical publication-time/PIT certification.',
                                'Fees/margins/ticks are contract or product vendor snapshots, not historical daily broker terms.',
                                'By-volume fees require explicit engine per-lot accounting; rate=0 is not fee-free.',
                                'Different open/close/close-today rates require explicit engine handling.',
                                'Universe includes 93 historical codes including ME/TC and separate monthly-average F families.',
                                'Only epochs ever selected by causal policy are materialized, with their complete available warmup/held history.',
                                'Missing bars remain missing; cached valuation cannot authorize signals or fills.',
                                'Slippage fixed one tick, except existing formal JM minimum one price unit; not a TCA estimate.'])
    for key,path in inputs.items():
        if identity(path)['sha256'] != fingerprints[key]['sha256']:
            raise ValueError(f'input_changed:{key}')
    output.mkdir(parents=True,exist_ok=True)
    for name,frame in [('mapping',mapping),('contract_metadata',metadata),('product_universe',universe),('market_daily',market)]:
        frame.to_csv(output/f'{name}.csv',index=False)
    manifest['output_files'] = {p.name:identity(p) for p in sorted(output.glob('*.csv'))}
    manifest['code'] = identity(__file__)
    (output/'source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return manifest


def load_source(input_dir=DEFAULT_INPUTS):
    folder = Path(input_dir)
    manifest = json.loads((folder/'source_manifest.json').read_text())
    for name,spec in manifest['output_files'].items():
        if identity(folder/name)['sha256'] != spec['sha256']:
            raise ValueError(f'source_output_changed:{name}')
    market = pd.read_csv(folder/'market_daily.csv',dtype={'contract_yyyymm':str})
    mapping = pd.read_csv(folder/'mapping.csv',keep_default_na=False,dtype={'contract_yyyymm':str})
    metadata = pd.read_csv(folder/'contract_metadata.csv',keep_default_na=False,dtype={'contract_yyyymm':str})
    return market,mapping,metadata,manifest


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--build',action='store_true')
    parser.add_argument('--output',type=Path,default=DEFAULT_INPUTS)
    args=parser.parse_args()
    if not args.build:
        parser.error('--build required; never starts a financial backtest')
    print(json.dumps(build_source(args.output),ensure_ascii=False,indent=2))
