"""Read-only independent audits of the 201 preregistered Stage256 accounts.

Only independent_reviews/ is written. No strategy, engine, training or download
is run. --account may be repeated; omitted IDs remain explicitly pending.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
IDS = ['AI_MONTHLY', 'AI_INITIAL_FIXED'] + [f'RANDOM_{i:03d}' for i in range(1, 200)]
REQUIRED = ['metrics.json', 'run_provenance.json', 'actual_strategy_settings.json',
            'stage256_account_provenance.json',
            'effective_parameters.json', 'daily.csv', 'trades.csv', 'positions.csv',
            'internal_equity_daily.csv', 'entry_candidates.csv', 'entry_risk.csv',
            'execution_clock.csv', 'execution_proxy_usage.csv',
            'execution_anchor_requests.csv', 'minute_scan_requests.csv']
TOL = 1e-6


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def safe(value):
    if isinstance(value, dict): return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [safe(v) for v in value]
    if isinstance(value, np.generic): value = value.item()
    if isinstance(value, (pd.Timestamp, datetime)): return value.isoformat()
    if isinstance(value, float) and not np.isfinite(value): return None
    return value


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(safe(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def csv(path):
    try: return pd.read_csv(path)
    except pd.errors.EmptyDataError: return pd.DataFrame()


def normalized(frame):
    frame = frame.copy()
    for col, mapping in [('direction', {'多': 'long', '空': 'short', 'Long': 'long', 'Short': 'short', 'long': 'long', 'short': 'short'}),
                         ('offset', {'开': 'open', 'Open': 'open', 'open': 'open', '平': 'close', '平今': 'close', '平昨': 'close', 'Close': 'close', 'Close Today': 'close', 'Close Yesterday': 'close', 'close': 'close'})]:
        if col in frame:
            if not frame[col].isin(mapping).all(): raise ValueError(f'unknown_{col}_enum')
            frame[col] = frame[col].map(mapping)
    return frame


def residual(values):
    values = pd.Series(values, dtype=float)
    if values.empty: return 0.0
    if not np.isfinite(values).all(): return float('inf')
    return float(values.abs().max())


def audit_ledger(trades, daily, positions, parameters, capital):
    """Independent cash + full marked holdings, plus flat-to-flat cycles."""
    errors = []; t = normalized(trades); d = daily.set_index('date').sort_index()
    if not d.index.is_unique or not positions.set_index(['date', 'vt_symbol']).index.is_unique:
        raise ValueError('duplicate_daily_or_position_key')
    if t.empty:
        t = pd.DataFrame(columns=['trade_id', 'order_id', 'vt_symbol', 'direction', 'offset', 'volume', 'price', 'date', 'datetime'])
    if not t.trade_id.is_unique: errors.append('duplicate_trade_id')
    t['trading_date'] = t.get('trading_date', t.date)
    for col in ['volume', 'price']: t[col] = pd.to_numeric(t[col], errors='raise')
    t['signed'] = t.volume * np.where(t.direction.eq('long'), 1., -1.)
    t['size'] = t.vt_symbol.map(parameters['contract_sizes'])
    t['commission_calc'] = t.volume * t['size'] * t.price * t.vt_symbol.map(parameters['rates'])
    t['slippage_calc'] = t.volume * t['size'] * t.vt_symbol.map(parameters['slippages'])
    t['cost'] = t.commission_calc + t.slippage_calc
    t['cashflow'] = -t.signed * t.price * t['size'] - t.cost
    if not np.isfinite(t[['signed', 'size', 'cost', 'cashflow']].to_numpy(dtype=float)).all(): errors.append('invalid_trade_metadata')
    if (t.volume.le(0) | t.price.le(0)).any(): errors.append('nonpositive_fill')
    pp = positions.set_index(['date', 'vt_symbol']).sort_index().copy()
    changes = t.groupby(['trading_date', 'vt_symbol']).signed.sum()
    if set(changes.index) - set(pp.index): errors.append('fill_missing_position_key')
    pp['derived_change'] = changes.reindex(pp.index, fill_value=0.)
    pp['derived_end'] = pp.groupby(level=1).derived_change.cumsum()
    size = pp.index.get_level_values(1).map(parameters['contract_sizes']).to_numpy()
    marked = (pp.derived_end * pp.close_price * size).groupby(level=0).sum()
    cash = t.groupby('trading_date').cashflow.sum().reindex(marked.index, fill_value=0.).cumsum()
    reconstructed = capital + cash + marked
    if set(d.index) - set(reconstructed.index): errors.append('daily_missing_position_date')
    eq_res = residual(d.account_equity - reconstructed.reindex(d.index))
    if eq_res > TOL: errors.append('cash_mtm_mismatch')
    change_res = residual(pp.derived_change - pp.pos_change)
    pos_res = residual(pp.derived_end - pp.end_pos)
    if max(change_res, pos_res) > TOL: errors.append('position_ledger_mismatch')
    expected_pnl = reconstructed.reindex(d.index).diff(); expected_pnl.iloc[0] = reconstructed.reindex(d.index).iloc[0] - capital
    if residual(expected_pnl - d.net_pnl) > TOL: errors.append('daily_pnl_mismatch')
    counts = t.groupby('trading_date').size().reindex(d.index, fill_value=0)
    if not counts.equals(d.trade_count.astype('int64')): errors.append('daily_trade_count_mismatch')
    for col in ['commission', 'slippage']:
        byday = t.groupby('trading_date')[col + '_calc'].sum().reindex(d.index, fill_value=0.)
        if residual(byday - d[col]) > TOL: errors.append(f'{col}_mismatch')
    if set(t.trading_date) - set(d.index): errors.append('fill_outside_account_calendar')
    order = t.assign(_id=t.trade_id.str.extract(r'(\d+)$', expand=False).astype(float)).sort_values('_id')
    if not pd.to_datetime(order.datetime, utc=True).is_monotonic_increasing: errors.append('nonchronological_trade_ids')
    holdings = {}; active = {}; cycles = []
    for x in order.itertuples():
        old = holdings.get(x.vt_symbol, 0.)
        if x.offset == 'close' and (old * x.signed >= 0 or abs(old) + TOL < x.volume): errors.append('close_without_position')
        if x.offset == 'open' and old * x.signed < 0: errors.append('opposite_open_without_close')
        item = active.setdefault(x.vt_symbol, {'cash': 0., 'cost': 0., 'trade_ids': [], 'entry_date': x.trading_date})
        item['cash'] += x.cashflow; item['cost'] += x.cost; item['trade_ids'].append(x.trade_id)
        holdings[x.vt_symbol] = old + x.signed
        if abs(holdings[x.vt_symbol]) < TOL:
            cycles.append({'vt_symbol': x.vt_symbol, 'entry_date': item['entry_date'], 'exit_date': x.trading_date,
                           'net_pnl': item['cash'], 'cost': item['cost'], 'trade_ids': item['trade_ids']})
            del active[x.vt_symbol]
    last = pp.reset_index().sort_values('date').groupby('vt_symbol').tail(1).set_index('vt_symbol')
    open_net = 0.; open_positions = {}
    for symbol, item in active.items():
        q = holdings[symbol]; open_positions[symbol] = q
        open_net += item['cash'] + q * float(last.loc[symbol, 'close_price']) * parameters['contract_sizes'][symbol]
    wins = [x['net_pnl'] for x in cycles if x['net_pnl'] > TOL]
    losses = [x['net_pnl'] for x in cycles if x['net_pnl'] < -TOL]
    closed_net = sum(x['net_pnl'] for x in cycles)
    if abs(closed_net + open_net - (d.account_equity.iloc[-1] - capital)) > TOL: errors.append('cycle_and_open_net_mismatch')
    return dict(errors=sorted(set(errors)), fill_count=len(t), end_equity=float(d.account_equity.iloc[-1]),
                total_return_pct=float((d.account_equity.iloc[-1] / capital - 1) * 100),
                max_dd_pct=float((d.account_equity / d.account_equity.cummax() - 1).min() * 100),
                cash_mtm_max_residual=eq_res, position_change_max_residual=change_res, position_end_max_residual=pos_res,
                cost_total=float(t.cost.sum()), slippage=float(t.slippage_calc.sum()), commission=float(t.commission_calc.sum()),
                closed_cycles=len(cycles), cycle_wins=len(wins), cycle_losses=len(losses), cycle_flats=len(cycles)-len(wins)-len(losses),
                cycle_win_rate_pct=100 * len(wins) / len(cycles) if cycles else None,
                profit_factor=sum(wins) / -sum(losses) if losses else None,
                profit_factor_infinite=bool(wins and not losses), closed_cycle_net_pnl=closed_net,
                end_open_episode_net_mtm=open_net, end_positions=open_positions, cycles=cycles,
                daily_first=str(d.index.min()), daily_last=str(d.index.max()), daily_rows=len(d))


def audit_membership(candidates, pool):
    dates = sorted(pool.eval_date.astype(str).unique()); bydate = {dt: g.set_index('product_vt_symbol') for dt, g in pool.groupby('eval_date')}
    mismatches = []
    for i, x in candidates.iterrows():
        prior = [dt for dt in dates if dt < str(x['date'])]
        if not prior:
            mismatches.append({'row': int(i), 'reason': 'no_prior_snapshot'}); continue
        dt = prior[-1]; subset = bydate[dt]; allowed = x.product_vt_symbol in subset.index
        rank = float(subset.loc[x.product_vt_symbol, 'score_rank']) if allowed else 0.
        score = float(subset.loc[x.product_vt_symbol, 'score']) if allowed else 0.
        ok = (int(x.ai_product_pool_allowed) == int(allowed) and str(x.ai_product_pool_signal_date) == dt
              and float(x.ai_product_pool_rank) == rank and abs(float(x.ai_product_pool_score) - score) < 1e-10
              and int(x.get('ai_product_pool_use_next_trade_date_for_entry', 0)) == 0)
        if not ok: mismatches.append({'row': int(i), 'date': str(x['date']), 'product': x.product_vt_symbol, 'expected_eval': dt, 'expected_allowed': allowed})
    return {'rows': len(candidates), 'mismatches': mismatches}


def audit_registered_pools(manifest):
    """Regenerate all draws without importing the experiment's pool generator."""
    errors=[]; checked=0; source=csv(manifest['source_pool'])
    days=manifest['expected_eval_dates']; universe=sorted(manifest['non_fu_universe'])
    if set(manifest['accounts'])!=set(IDS): errors.append('account_registry_not_exact_201')
    if len(universe)!=18 or len(set(universe))!=18 or 'fu.SHFE' in universe: errors.append('wrong_non_fu_universe')
    if len(days)!=22 or days!=sorted(set(days)): errors.append('wrong_eval_dates')
    if sha(manifest['source_pool'])!=manifest['source_pool_sha256']: errors.append('source_pool_hash_changed')
    initial=set(source.loc[source.eval_date.eq(days[0]),'product_vt_symbol'])
    history=source[source.eval_date.lt(days[0])].drop(columns='strategy').reset_index(drop=True)
    for ident in IDS:
        if ident not in manifest['accounts']: continue
        spec=manifest['accounts'][ident]; p=csv(spec['pool_file'])
        if sha(spec['pool_file'])!=spec['pool_sha256']: errors.append(f'{ident}:pool_hash')
        if set(p.strategy)!={spec.get('policy_id',spec.get('strategy'))}: errors.append(f'{ident}:policy')
        relevant=p[p.eval_date.ge(days[0])]
        if set(relevant.eval_date)!=set(days): errors.append(f'{ident}:eval_dates')
        if not p[p.eval_date.lt(days[0])].drop(columns='strategy').reset_index(drop=True).equals(history): errors.append(f'{ident}:warmup_history_changed')
        if ident=='AI_MONTHLY' and Path(spec['pool_file']).read_bytes()!=Path(manifest['source_pool']).read_bytes(): errors.append('AI_MONTHLY:not_exact_official_copy')
        rng=None
        if ident.startswith('RANDOM_'):
            path_id=int(ident.rsplit('_',1)[1])
            if spec.get('path_id')!=path_id: errors.append(f'{ident}:path_id')
            rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([manifest['master_seed'],path_id])))
        for day in days:
            g=p[p.eval_date.eq(day)]; members=set(g.product_vt_symbol)
            valid=(len(g)==11 and len(members)==11 and 'fu.SHFE' in members and members-{'fu.SHFE'}<=set(universe)
                   and sorted(g.score_rank)==list(range(1,12)) and set(g.top_n)=={11}
                   and g.loc[g.product_vt_symbol.eq('fu.SHFE'),'score_rank'].tolist()==[11])
            if not valid: errors.append(f'{ident}:{day}:not_ten_plus_fu')
            expected=set(rng.choice(universe,10,replace=False).tolist())|{'fu.SHFE'} if rng else initial if ident=='AI_INITIAL_FIXED' else set(source.loc[source.eval_date.eq(day),'product_vt_symbol'])
            if members!=expected: errors.append(f'{ident}:{day}:membership_not_preregistered')
            checked+=1
    return {'status':'FAIL' if errors else 'PASS','errors':errors,'accounts':len(manifest['accounts']),
            'monthly_snapshots_checked':checked,'random_paths_regenerated':199,
            'random_algorithm':'PCG64(SeedSequence([master_seed,path_id])); sequential choice(sorted18,10,replace=False)',
            'numpy_version':np.__version__,'initial_fixed_members':sorted(initial),
            'seed_selection':'exact path IDs 1..199 retained; every draw matches preregistered stream'}


class MinuteStore:
    def __init__(self, path):
        # Loaded only once per audit batch, never once per account.
        frame = pd.read_csv(path, usecols=['vt_symbol','bar_datetime','open','high','low','close'])
        frame['stamp'] = pd.to_datetime(frame.pop('bar_datetime'))
        self.groups = {symbol: g.set_index('stamp').drop(columns='vt_symbol').sort_index() for symbol, g in frame.groupby('vt_symbol', sort=False)}
        self.stamp_sets = {symbol:set(g.index) for symbol,g in self.groups.items()}

    def rows(self, symbol):
        return self.groups.get(symbol, pd.DataFrame(columns=['open','high','low','close'], index=pd.DatetimeIndex([])))


def audit_execution(frames, parameters, store):
    sys.path.insert(0, str(ROOT / 'examples/portfolio_backtesting'))
    from qmt_roll_intraday_execution import local_timestamp, session_minutes, effective_pricetick
    t = normalized(frames['trades.csv']); u = normalized(frames['execution_proxy_usage.csv']); clock = normalized(frames['execution_clock.csv'])
    scans = frames['minute_scan_requests.csv']; anchors = frames['execution_anchor_requests.csv']; positions = frames['positions.csv']
    errors = []; cal = pd.to_datetime(positions.date.unique()); grids = {}
    def grid(symbol, day):
        key=(symbol,day)
        if key not in grids: grids[key]=session_minutes(symbol,day,cal)
        return grids[key]
    tids = set(t.get('trade_id', []))
    if tids != set(u.get('trade_id', [])) or tids != set(clock.get('trade_id', [])): errors.append('trade_usage_clock_id_difference')
    if any(not f.trade_id.is_unique for f in (t,u,clock) if 'trade_id' in f): errors.append('duplicate_execution_id')
    missing_fills=[]; synthetic=0; outbar=[]; off_tick=[]; session_bad=[]; joined_bad=[]
    if len(t):
        ui=u.set_index('trade_id'); ci=clock.set_index('trade_id')
        for x in t.itertuples():
            if x.trade_id not in ui.index or x.trade_id not in ci.index: continue
            usage=ui.loc[x.trade_id]; ck=ci.loc[x.trade_id]; stamp=local_timestamp(usage.execution_datetime); day=str(usage.trading_date)
            if any(getattr(x,col)!=ck[col] for col in ['vt_symbol','direction','offset','price','volume']): joined_bad.append(x.trade_id)
            if x.price!=usage.trade_price or x.volume!=usage.order_volume or x.vt_symbol!=usage.vt_symbol or str(x.date)!=day or str(ck.trading_date)!=day or local_timestamp(x.datetime)!=stamp or local_timestamp(ck.execution_datetime)!=stamp: joined_bad.append(x.trade_id)
            if stamp not in grid(x.vt_symbol,day): session_bad.append(x.trade_id)
            is_synth=str(usage.price_source).startswith('stage'); synthetic+=is_synth
            if not is_synth and stamp!=grid(x.vt_symbol,day)[0]: errors.append('ordinary_not_at_session_start')
            if not is_synth and (str(usage.signal_date)>=day or local_timestamp(usage.signal_datetime)>=stamp): errors.append('signal_not_before_execution')
            tick=effective_pricetick(x.vt_symbol,day,parameters['priceticks'][x.vt_symbol])
            if abs(x.price/tick-round(x.price/tick))>1e-7: off_tick.append(x.trade_id)
            rows=store.rows(x.vt_symbol)
            if stamp not in rows.index:
                missing_fills.append({'trade_id':x.trade_id,'symbol':x.vt_symbol,'stamp':str(stamp),'synthetic':is_synth,'source':str(usage.price_source),'volume':x.volume,'price':x.price})
                if is_synth: errors.append('synthetic_without_minute')
            else:
                bar=rows.loc[stamp]
                if isinstance(bar,pd.DataFrame): errors.append('duplicate_fill_minute'); continue
                vals=bar[['open','high','low','close']].to_numpy(float)
                if not np.isfinite(vals).all() or min(vals)<=0 or bar.low>min(bar.open,bar.close) or bar.high<max(bar.open,bar.close): errors.append('invalid_fill_ohlc')
                if not bar.low-TOL<=x.price<=bar.high+TOL: outbar.append(x.trade_id)
                if not is_synth and abs(x.price-bar.open)>TOL: errors.append('ordinary_price_not_minute_open')
    if joined_bad: errors.append('trade_usage_clock_mismatch')
    if session_bad: errors.append('fill_outside_session')
    if outbar: errors.append('fill_outside_minute_range')
    if off_tick: errors.append('off_historical_tick')
    missing_scans=[]; unique_missing=set(); scan_bad=[]
    unique=scans.drop_duplicates(['vt_symbol','trading_date','execution_datetime']) if len(scans) else scans
    for x in unique.itertuples():
        stamps=grid(x.vt_symbol,x.trading_date); stamps=stamps[stamps>=local_timestamp(x.requested_start)]
        missing=set(stamps)-store.stamp_sets.get(x.vt_symbol,set())
        if len(missing)!=int(x.missing_bar_count) or len(stamps)!=int(x.expected_bar_count) or len(stamps)-len(missing)!=int(x.actual_bar_count) or (str(x.coverage_status)=='complete')!=(not missing): scan_bad.append({'symbol':x.vt_symbol,'date':x.trading_date,'expected_missing':len(missing),'reported':int(x.missing_bar_count)})
        if missing: missing_scans.append({'symbol':x.vt_symbol,'date':x.trading_date,'missing':len(missing)})
        unique_missing.update((x.vt_symbol,str(dt)) for dt in missing)
    if scan_bad: errors.append('scan_coverage_count_mismatch')
    anchor_gaps=[]
    if len(anchors):
        ordinary = t[t.trade_id.isin(u.loc[~u.price_source.astype(str).str.startswith('stage'),'trade_id'])]
        if set(ordinary.order_id) != set(anchors.order_id): errors.append('ordinary_anchor_id_difference')
        for x in anchors.itertuples():
            expected=grid(x.vt_symbol,x.trading_date)[0]
            if local_timestamp(x.expected_start)!=expected: errors.append('anchor_session_start_mismatch')
            present=expected in store.rows(x.vt_symbol).index
            if (str(x.coverage_status)=='complete')!=present: errors.append('anchor_coverage_mismatch')
            if present and local_timestamp(x.actual_time)!=expected: errors.append('anchor_time_mismatch')
            if not present: anchor_gaps.append({'symbol':x.vt_symbol,'date':x.trading_date,'expected_start':str(expected),'price':x.price,'offset':x.offset,'order_id':x.order_id})
    if len(t) and any(str(x).startswith('stage847') for x in u.price_source): errors.append('half_r_execution_present')
    # C2 stop closes use .intraday.1; only the .2 branch is a retry entry.
    if len(t) and t.order_id.astype(str).str.contains(r'\.intraday\.2(?:\.|$)',regex=True).any(): errors.append('retry_order_present')
    return dict(errors=sorted(set(errors)), synthetic_fills=synthetic, missing_fill_minutes=missing_fills,
                out_of_bar_ids=outbar, off_tick_ids=off_tick, session_mismatch_ids=session_bad,
                raw_scan_requests=len(scans), unique_scan_requests=len(unique), incomplete_scans=len(missing_scans),
                missing_scan_minutes=len(unique_missing), incomplete_scan_details=missing_scans, scan_count_mismatches=scan_bad,
                anchors=len(anchors), incomplete_anchors=len(anchor_gaps), anchor_gaps=anchor_gaps,
                source_counts=u.price_source.value_counts().to_dict() if len(u) else {})


def audit_account(account_id, directory, spec, manifest, store):
    frames={n:csv(directory/n) for n in REQUIRED if n.endswith('.csv')}
    metrics=read(directory/'metrics.json'); provenance=read(directory/'run_provenance.json'); parameters=read(directory/'effective_parameters.json')
    actual_rows=read(directory/'actual_strategy_settings.json')
    if len(actual_rows)!=1: raise ValueError('actual_strategy_instance_count')
    actual=actual_rows[0]; reference=read(manifest['reference_settings_path'])[0]; errors=[]
    policy=spec.get('policy_id',spec.get('strategy')); pool_path=Path(spec['pool_file']).resolve(); pool=csv(pool_path)
    if sha(pool_path)!=spec['pool_sha256']: errors.append('pool_hash_mismatch')
    if set(pool.strategy)!={policy}: errors.append('pool_policy_id_mismatch')
    start=manifest['start']; end=manifest['end']; capital=float(manifest['capital'])
    parameter_delta={}
    for scope in ['setting','actual']:
        expected=dict(reference[scope]); expected.update(trade_start_date=start,ai_product_pool_eligibility_path=str(pool_path),ai_product_pool_strategy=policy)
        delta={k:[expected.get(k),actual[scope].get(k)] for k in set(expected)|set(actual[scope]) if expected.get(k)!=actual[scope].get(k)}
        parameter_delta[scope]=delta
        if delta: errors.append(f'{scope}_unexpected_parameter_delta')
    for key,value in {'enable_stage847_half_r_stop_retry':False,'enable_stage827_intraday_c2_stop':True,'enable_ai_product_pool_filter':True,'enable_selection_pairwise_v2':True}.items():
        if actual['actual'].get(key) is not value: errors.append(f'wrong_flag:{key}')
    if actual.get('engine_capital')!=capital or actual.get('non_strategy_fields')!=reference.get('non_strategy_fields') or any(v!=capital for v in actual.get('non_strategy_fields',{}).values()): errors.append('capital_mismatch')
    if actual.get('supply_demand_signal_rows')!=reference.get('supply_demand_signal_rows'): errors.append('external_signal_rows_changed')
    pref=read(manifest['parameters_reference_path'])
    for key in ['contract_sizes','priceticks','rates','slippages']:
        if parameters.get(key)!=pref.get(key): errors.append(f'contract_metadata_changed:{key}')
    relevant=pool[pool.eval_date.ge(manifest['expected_eval_dates'][0])]
    if set(relevant.eval_date)!=set(manifest['expected_eval_dates']): errors.append('pool_eval_dates_mismatch')
    pool_bad=[]; universe=set(manifest['non_fu_universe'])
    for day,g in relevant.groupby('eval_date'):
        members=set(g.product_vt_symbol)
        if len(g)!=11 or len(members)!=11 or 'fu.SHFE' not in members or not members-{'fu.SHFE'}<=universe or sorted(g.score_rank)!=list(range(1,12)) or set(g.top_n)!={11}: pool_bad.append(str(day))
    if pool_bad: errors.append('pool_not_ten_plus_fu')
    candidates=frames['entry_candidates.csv']; membership=audit_membership(candidates,pool)
    if membership['mismatches']: errors.append('candidate_membership_mismatch')
    ledger=audit_ledger(frames['trades.csv'],frames['daily.csv'],frames['positions.csv'],parameters,capital); errors+=ledger['errors']
    execution=audit_execution(frames,parameters,store); errors+=execution['errors']
    for key,expected in [('end_equity',ledger['end_equity']),('total_return_pct',ledger['total_return_pct']),('max_dd_pct',ledger['max_dd_pct']),('total_slippage',ledger['slippage']),('total_trade_count',ledger['fill_count'])]:
        if abs(float(metrics[key])-expected)>TOL: errors.append(f'metrics_mismatch:{key}')
    if metrics['start']!=start or metrics['end']!=end or ledger['daily_first']<start or ledger['daily_last']!=end: errors.append('account_window_mismatch')
    t=frames['trades.csv']
    if len(t) and (t.date.lt(start)|t.date.gt(end)).any(): errors.append('fill_outside_window')
    warm=frames['positions.csv']; warm=warm[warm.date.lt(start)]
    if len(warm) and (warm[['end_pos','pos_change']].abs()>TOL).any().any(): errors.append('nonflat_warmup')
    di=frames['daily.csv'].merge(frames['internal_equity_daily.csv'],on='date',how='left',validate='one_to_one')
    internal_res=residual(di.account_equity-di.estimated_equity)
    settled_res=residual(di.account_equity-di.settled_balance)
    if max(internal_res,settled_res)>TOL: errors.append('internal_equity_mismatch')
    if provenance.get('vendor_swallowed_bar_exception_guard') is not True or provenance.get('captured_bar_failure_count')!=0: errors.append('exception_guard_failed')
    if provenance.get('all_data_and_model_inputs_unchanged_during_run') is not True: errors.append('inputs_changed_or_unverified')
    if provenance.get('minute_input_sha256')!=manifest['minute_cache_sha256']: errors.append('minute_identity_mismatch')
    pref_provenance=read(Path(manifest['parameters_reference_path']).parent/'run_provenance.json')
    if provenance.get('correctness_code_sha256')!=pref_provenance['correctness_code_sha256']: errors.append('accepted_correctness_code_identity_changed')
    for key in ['input_manifest_sha256','shared_signal_input_dir','supply_demand_history']:
        if provenance.get(key)!=pref_provenance.get(key): errors.append(f'shared_input_identity_changed:{key}')
    sidecar=read(directory/'stage256_account_provenance.json')
    if sidecar.get('account_id')!=account_id or sidecar.get('policy_id')!=policy or sidecar.get('pool_file')!=str(pool_path): errors.append('stage256_account_identity_mismatch')
    if sidecar.get('start')!=start or sidecar.get('end')!=end or sidecar.get('capital')!=capital or sidecar.get('half_r_enabled') is not False or sidecar.get('ai_pool_enabled') is not True: errors.append('stage256_account_declaration_mismatch')
    before=sidecar.get('input_sha256_before',{}); after=sidecar.get('input_sha256_after',{})
    if not before or before!=after: errors.append('stage256_inputs_changed')
    identities={'pool':spec['pool_sha256'],'minute':manifest['minute_cache_sha256'],
                'reference_settings':sha(manifest['reference_settings_path']),'parameters_reference':sha(manifest['parameters_reference_path']),
                'source_pool':manifest['source_pool_sha256'], 'registry':sha(directory.parent.parent/'experiment_manifest.json')}
    if any(before.get(k)!=v for k,v in identities.items()): errors.append('stage256_input_identity_mismatch')
    for name,digest in provenance.get('correctness_code_sha256',{}).items():
        if sha(ROOT/name)!=digest: errors.append(f'runtime_code_changed:{name}')
    risk=frames['entry_risk.csv']; usage=normalized(frames['execution_proxy_usage.csv'])
    rf=risk[risk.get('actual_filled_volume',pd.Series(index=risk.index,dtype=float)).fillna(0).gt(0)].copy()
    ordinary=usage[usage.offset.eq('open') & ~usage.price_source.astype(str).str.startswith('stage')] if len(usage) else usage
    qty_res=price_res=risk_res=0.
    if len(ordinary):
        rr=rf.groupby('signal_order_id').actual_filled_volume.sum(); oo=ordinary.groupby('signal_order_id').order_volume.sum()
        if set(rr.index)!=set(oo.index): errors.append('risk_order_binding_mismatch')
        qty_res=residual(rr-oo); rp=(rf.actual_filled_volume*rf.filled_entry_price).groupby(rf.signal_order_id).sum()/rr; op=(ordinary.order_volume*ordinary.trade_price).groupby(ordinary.signal_order_id).sum()/oo; price_res=residual(rp-op)
        if max(qty_res,price_res)>TOL: errors.append('risk_fill_price_or_quantity_mismatch')
        size=rf.contract_vt_symbol.map(parameters['contract_sizes']); tick=rf.contract_vt_symbol.map(parameters['priceticks'])
        per_contract=np.maximum((rf.filled_entry_price-rf.stop_price).abs()*size,np.maximum(tick*size,1.))
        risk_res=residual(per_contract*rf.actual_filled_volume-rf.actual_risk_amount)
        if risk_res>TOL: errors.append('risk_amount_not_filled_quantity')
    elif len(rf): errors.append('risk_filled_without_open')
    for name in ['stop_retry_events.csv']:
        if (directory/name).exists() and len(csv(directory/name)): errors.append('half_r_events_present')
    gaps=execution['incomplete_scans']+execution['incomplete_anchors']
    if gaps and not provenance.get('diagnostic_incomplete_minutes'): errors.append('strict_run_has_execution_gaps')
    return dict(account_id=account_id,status='FAIL' if errors else ('PASS_DIAGNOSTIC_GAPS' if gaps else 'PASS_COVERAGE_COMPLETE'),
                accounting_passed=not errors,strict_performance_accepted=not errors and not gaps and not provenance.get('diagnostic_incomplete_minutes'),
                errors=sorted(set(errors)),ledger=ledger,execution=execution,membership=membership,settings_delta=parameter_delta,
                pool={'policy_id':policy,'eval_dates':len(relevant.eval_date.unique()),'invalid_dates':pool_bad,'sha256':sha(pool_path)},
                internal_equity_max_residual=internal_res,settled_balance_max_residual=settled_res,
                risk_fill_qty_max_residual=qty_res,risk_fill_price_max_residual=price_res,
                risk_amount_max_residual=risk_res,
                warmup={'rows':len(warm),'first':warm.date.min() if len(warm) else None,'last':warm.date.max() if len(warm) else None},
                diagnostic_incomplete_minutes=provenance.get('diagnostic_incomplete_minutes'),source_metrics_sharpe=metrics.get('sharpe'))


def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--experiment',required=True,type=Path); ap.add_argument('--account',action='append'); ap.add_argument('--require-all',action='store_true'); ap.add_argument('--refresh',action='store_true')
    args=ap.parse_args(); exp=args.experiment.resolve(); manifest=read(exp/'experiment_manifest.json'); out=exp/'independent_reviews'; out.mkdir(exist_ok=True)
    selected=args.account or IDS
    if set(selected)-set(IDS): raise ValueError('unknown_account_id')
    script_hash=sha(__file__); manifest_hash=sha(exp/'experiment_manifest.json'); store=None; results={}; cache_hash=None
    pools=audit_registered_pools(manifest)
    pools.update(experiment_manifest_sha256=manifest_hash,audit_script_sha256=script_hash)
    write(out/'pool_registration_review.json',pools)
    for ident in selected:
        directory=exp/'accounts'/ident; review_path=out/'accounts'/f'{ident}.json'
        missing=[n for n in REQUIRED if not (directory/n).exists()]
        if ident not in manifest.get('accounts',{}) or missing:
            results[ident]={'account_id':ident,'status':'INCOMPLETE','missing_files':missing,'run_failure_present':(directory/'run_failure.json').exists()}; continue
        prov=read(directory/'run_provenance.json')
        if not prov.get('completed_at') or not read(directory/'stage256_account_provenance.json').get('completed_at'):
            results[ident]={'account_id':ident,'status':'INCOMPLETE','reason':'provenance_not_completed'}; continue
        source_hashes={n:sha(directory/n) for n in REQUIRED}
        for n in ['stop_retry_events.csv']:
            if (directory/n).exists(): source_hashes[n]=sha(directory/n)
        spec=manifest['accounts'][ident]; source_hashes['pool_file']=sha(spec['pool_file'])
        if review_path.exists() and not args.refresh:
            prior=read(review_path)
            if prior.get('source_hashes')==source_hashes and prior.get('audit_script_sha256')==script_hash and prior.get('experiment_manifest_sha256')==manifest_hash:
                results[ident]=prior; continue
        try:
            if cache_hash is None:
                cache_hash=sha(manifest['minute_csv'])
            if cache_hash!=manifest['minute_cache_sha256']: raise ValueError('frozen_minute_cache_hash_mismatch')
            if store is None: store=MinuteStore(manifest['minute_csv'])
            result=audit_account(ident,directory,spec,manifest,store)
            if any(sha(directory/n)!=digest for n,digest in source_hashes.items() if n!='pool_file'): result['errors'].append('source_changed_during_audit'); result['status']='FAIL'; result['accounting_passed']=False
        except Exception as exc:
            result={'account_id':ident,'status':'FAIL','accounting_passed':False,'errors':[f'{type(exc).__name__}: {exc}']}
        result.update(source_hashes=source_hashes,audit_script_sha256=script_hash,experiment_manifest_sha256=manifest_hash,reviewed_at=datetime.now(timezone.utc).isoformat())
        write(review_path,result); results[ident]=result
        print(json.dumps({'account':ident,'status':result['status'],'errors':result.get('errors',[])},ensure_ascii=False),flush=True)
    # Existing independent results are retained in the complete 201-ID view.
    for ident in IDS:
        if ident in results: continue
        path=out/'accounts'/f'{ident}.json'
        if path.exists():
            previous=read(path)
            results[ident]=previous if previous.get('audit_script_sha256')==script_hash and previous.get('experiment_manifest_sha256')==manifest_hash else {'account_id':ident,'status':'REVIEW_STALE'}
        else: results[ident]={'account_id':ident,'status':'NOT_REVIEWED'}
    statuses=Counter(x['status'] for x in results.values()); passed=sum(v for k,v in statuses.items() if k.startswith('PASS'))
    summary={'status':'FAIL' if statuses['FAIL'] or pools['errors'] else ('COMPLETE_DIAGNOSTIC' if passed==201 and statuses['PASS_DIAGNOSTIC_GAPS'] else 'COMPLETE_ACCOUNTING' if passed==201 else 'INCOMPLETE'),
             'expected_accounts':201,'audited_passed':passed,'status_counts':dict(statuses),'missing_or_unreviewed':[k for k,v in results.items() if not v['status'].startswith('PASS')],
             'any_path_has_gaps':bool(statuses['PASS_DIAGNOSTIC_GAPS']), 'strict_comparative_conclusion_allowed':not pools['errors'] and passed==201 and all(v.get('strict_performance_accepted') for v in results.values()),
             'pool_registration_review':pools,
             'audit_script_sha256':script_hash,'experiment_manifest_sha256':manifest_hash,'accounts':results}
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');write(out/f'batch_{stamp}.json',summary);write(out/'latest.json',summary)
    rows=[]
    for ident,x in results.items():
        l=x.get('ledger',{}); e=x.get('execution',{}); row={'account_id':ident,'status':x['status']}
        row.update({k:l.get(k) for k in ['end_equity','total_return_pct','max_dd_pct','slippage','commission','fill_count','closed_cycles','cycle_win_rate_pct','profit_factor','end_open_episode_net_mtm']});row.update({k:e.get(k) for k in ['incomplete_scans','missing_scan_minutes','incomplete_anchors']});rows.append(row)
    pd.DataFrame(rows).to_csv(out/'summary.csv',index=False)
    print(json.dumps({k:v for k,v in summary.items() if k!='accounts'},ensure_ascii=False))
    return 1 if statuses['FAIL'] or pools['errors'] else 2 if args.require_all and passed!=201 else 0


if __name__=='__main__': raise SystemExit(main())
