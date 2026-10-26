"""Read-only, parameterized Stage029 comparison of two completed same-window ledgers.

This module imports no strategy, engine, downloader, or prior arm validator. It
recomputes conserved accounting and writes new report artifacts only. Success of
this derivation is not independent review, execution qualification, or promotion.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

CAPITAL = 150000.
POOL = {'AP.CZCE', 'CF.CZCE', 'FG.CZCE', 'MA.CZCE', 'OI.CZCE', 'SA.CZCE',
        'SH.CZCE', 'SM.CZCE', 'au.SHFE', 'cu.SHFE', 'fu.SHFE', 'hc.SHFE',
        'jm.DCE', 'lc.GFEX', 'lh.DCE', 'rb.SHFE', 'ru.SHFE', 'si.GFEX', 'sp.SHFE'}
FLAGS = ['enable_stage847_half_r_stop_retry', 'enable_stage827_intraday_c2_stop',
         'enable_ai_product_pool_filter', 'enable_selection_pairwise_v2',
         'enable_selection_pairwise_v2_catastrophic_veto',
         'enable_selection_pairwise_v2_catastrophic_hard_filter',
         'enable_selection_pairwise_v2_volume_tilt']
EXECUTION_MODEL = 'declared_daily_bar_open_next_bar_v1'
SEGMENT_COLUMNS = ['vt_symbol', 'direction', 'entry_trade_id', 'exit_trade_id',
    'entry_execution_datetime', 'exit_execution_datetime', 'entry_trading_date',
    'exit_trading_date', 'volume', 'entry_price', 'exit_price', 'contract_size',
    'entry_slippage', 'exit_slippage', 'entry_commission', 'exit_commission', 'gross_pnl', 'net_pnl']
ROUND_COLUMNS = ['vt_symbol', 'direction', 'entry_trade_id', 'exit_trade_id',
    'entry_execution_datetime', 'exit_execution_datetime', 'entry_trading_date',
    'exit_trading_date', 'opened_volume', 'fill_count', 'net_pnl']
OPEN_COLUMNS = ['vt_symbol', 'direction', 'entry_trade_id', 'entry_execution_datetime',
    'entry_trading_date', 'opened_volume', 'fill_count', 'end_pos', 'terminal_mark',
    'partial_closed_net_pnl', 'remaining_open_net_mtm', 'net_mtm']


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1048576), b''):
            digest.update(chunk)
    return digest.hexdigest()


def require_close(actual, expected, name, tolerance=1e-6):
    if not math.isfinite(float(actual)) or not math.isfinite(float(expected)) or abs(float(actual)-float(expected)) > tolerance:
        raise ValueError(f'{name}:{actual!r}!={expected!r}')


def verify_sources(sources):
    for path, digest in sources.items():
        if sha(path) != digest:
            raise ValueError('immutable_source_changed:'+str(path))


def snapshot_dir(path):
    return {str(p.resolve()): sha(p) for p in sorted(Path(path).rglob('*')) if p.is_file()}


def product(symbol):
    match = re.fullmatch(r'([A-Za-z]+)[0-9]{3,4}\.([A-Z]+)', str(symbol))
    value = None if match is None else match.group(1)+'.'+match.group(2)
    if value not in POOL:
        raise ValueError('contract_outside_frozen19:'+str(symbol))
    return value


def trading_day(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is not None or stamp != stamp.normalize():
        raise ValueError('exact_trading_date_required:'+str(value))
    return stamp.strftime('%Y-%m-%d')


def utc(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp):
        raise ValueError('execution_datetime_required')
    return stamp.tz_localize('Asia/Shanghai').tz_convert('UTC') if stamp.tzinfo is None else stamp.tz_convert('UTC')


def direction(value):
    text = str(value).lower()
    if text in {'多', 'long'}:
        return 1
    if text in {'空', 'short'}:
        return -1
    raise ValueError('unsupported_direction:'+text)


def offset(value):
    text = str(value).lower().replace(' ', '')
    if text in {'开', 'open'}:
        return 'open'
    if text in {'平', '平今', '平昨', 'close', 'closetoday', 'closeyesterday'}:
        return 'close'
    raise ValueError('unsupported_offset:'+text)


def ordered_fills(trades, clock):
    """Bind every fill to the clock's explicit exchange trading date, never its night date."""
    required = {'trade_id', 'vt_symbol', 'direction', 'offset', 'price', 'volume', 'trading_date'}
    if not required.issubset(trades.columns) or not (required|{'execution_datetime'}).issubset(clock.columns):
        raise ValueError('fill_and_clock_trading_date_columns_required')
    result, clock = trades.copy(), clock.copy()
    for frame in [result, clock]:
        frame['trade_id'] = frame.trade_id.astype(str)
        frame['trading_date'] = frame.trading_date.map(trading_day)
        if frame.trade_id.duplicated().any():
            raise ValueError('duplicate_trade_id')
    if set(result.trade_id) != set(clock.trade_id):
        raise ValueError('execution_clock_trade_ids_mismatch')
    check = clock.set_index('trade_id')
    for row in result.itertuples():
        target = check.loc[row.trade_id]
        for key in ['vt_symbol', 'direction', 'offset', 'trading_date']:
            if str(getattr(row, key)) != str(target[key]):
                raise ValueError('execution_clock_mismatch:'+key)
        if hasattr(row, 'date') and trading_day(row.date) != row.trading_date:
            raise ValueError('fill_date_not_trading_date')
        for key in ['price', 'volume']:
            require_close(getattr(row, key), target[key], 'execution_clock_'+key, 1e-8)
    result = result.drop(columns=['execution_datetime', '_clock_order'], errors='ignore')
    clock['_clock_order'] = np.arange(len(clock))
    result = result.merge(clock[['trade_id', 'execution_datetime', '_clock_order']], on='trade_id', validate='one_to_one')
    result['_execution_utc'] = result.execution_datetime.map(utc)
    result = result.sort_values(['_execution_utc', '_clock_order'], kind='stable').reset_index(drop=True)
    if len(result) and result.trading_date.tolist() != sorted(result.trading_date.tolist()):
        raise ValueError('execution_clock_trading_date_order_reversal')
    return result


def metadata(effective, symbol):
    try:
        size, slip, rate = [float(effective[key][symbol]) for key in ['sizes', 'slippages', 'rates']]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('missing_effective_contract_metadata:'+symbol) from exc
    if not all(math.isfinite(x) for x in [size, slip, rate]) or size <= 0 or slip < 0 or rate < 0:
        raise ValueError('invalid_effective_contract_metadata:'+symbol)
    return size, slip, rate


def pnl_stats(frame):
    values = frame.net_pnl.astype(float)
    if not np.isfinite(values).all():
        raise ValueError('nonfinite_closed_pnl')
    wins, losses = values[values > 1e-8], values[values < -1e-8]
    aw, al = (float(wins.mean()) if len(wins) else None), (float(-losses.mean()) if len(losses) else None)
    return dict(count=len(values), wins=len(wins), losses=len(losses), flat=len(values)-len(wins)-len(losses),
        win_rate_pct=100.*len(wins)/len(values) if len(values) else None,
        average_win=aw, average_loss_abs=al, payoff_ratio=aw/al if aw is not None and al else None,
        total_winning_pnl=float(wins.sum()), total_losing_pnl_abs=float(-losses.sum()),
        profit_factor=float(wins.sum()/-losses.sum()) if len(losses) else None,
        profit_factor_status='DEFINED' if len(losses) else 'UNDEFINED_NO_LOSSES', closed_net_pnl=float(values.sum()))


def inventory_accounting(fills, effective, terminal_marks):
    """Derive FIFO matches and exact-contract flat-to-flat rounds from zero initial inventory."""
    inventory, active = defaultdict(deque), {}
    segments, rounds, open_rows = [], [], []
    total_slip = total_fee = 0.
    for row in fills.to_dict('records'):
        symbol, price, qty = str(row['vt_symbol']), float(row['price']), float(row['volume'])
        if not (math.isfinite(price) and price > 0 and math.isfinite(qty) and qty > 0):
            raise ValueError('invalid_fill:'+str(row['trade_id']))
        size, slip, rate = metadata(effective, symbol)
        sign, kind = direction(row['direction']), offset(row['offset'])
        su, fu = size*slip, size*price*rate
        total_slip += su*qty; total_fee += fu*qty
        queue = inventory[symbol]
        if kind == 'open':
            if queue and queue[0]['sign'] != sign:
                raise ValueError('opposing_open_without_close:'+symbol)
            if not queue:
                active[symbol] = dict(vt_symbol=symbol, direction='long' if sign > 0 else 'short',
                    entry_trade_id=str(row['trade_id']), entry_execution_datetime=str(row['execution_datetime']),
                    entry_trading_date=row['trading_date'], opened_volume=0., fill_count=0, cash=0., realized=0.)
            queue.append(dict(sign=sign, quantity=qty, price=price, trade_id=str(row['trade_id']),
                execution_datetime=str(row['execution_datetime']), trading_date=row['trading_date'], slip_unit=su, fee_unit=fu))
            active[symbol]['opened_volume'] += qty
        elif symbol not in active:
            raise ValueError('unmatched_close:'+str(row['trade_id']))
        episode = active[symbol]
        episode['fill_count'] += 1
        episode['cash'] -= sign*price*size*qty+(su+fu)*qty
        if kind == 'open':
            continue
        remaining = qty
        while remaining > 1e-9:
            if not queue or queue[0]['sign'] != -sign:
                raise ValueError('unmatched_close:'+str(row['trade_id']))
            entry = queue[0]; matched = min(remaining, entry['quantity'])
            gross = entry['sign']*(price-entry['price'])*size*matched
            es, xs, ef, xf = entry['slip_unit']*matched, su*matched, entry['fee_unit']*matched, fu*matched
            net = gross-es-xs-ef-xf
            segments.append(dict(vt_symbol=symbol, direction='long' if entry['sign'] > 0 else 'short',
                entry_trade_id=entry['trade_id'], exit_trade_id=str(row['trade_id']),
                entry_execution_datetime=entry['execution_datetime'], exit_execution_datetime=str(row['execution_datetime']),
                entry_trading_date=entry['trading_date'], exit_trading_date=row['trading_date'], volume=matched,
                entry_price=entry['price'], exit_price=price, contract_size=size,
                entry_slippage=es, exit_slippage=xs, entry_commission=ef, exit_commission=xf, gross_pnl=gross, net_pnl=net))
            episode['realized'] += net; entry['quantity'] -= matched; remaining -= matched
            if entry['quantity'] <= 1e-9:
                queue.popleft()
        if not queue:
            require_close(episode['cash'], episode['realized'], 'complete_contract_round_conservation')
            rounds.append({k:episode[k] for k in ROUND_COLUMNS if k in episode} | dict(
                exit_trade_id=str(row['trade_id']), exit_execution_datetime=str(row['execution_datetime']),
                exit_trading_date=row['trading_date'], net_pnl=episode['cash']))
            del active[symbol]
    net_positions, remaining_total = {}, 0.
    for symbol, episode in active.items():
        queue = inventory[symbol]
        mark = float(terminal_marks.get(symbol, math.nan))
        if not math.isfinite(mark) or mark <= 0:
            raise ValueError('real_terminal_mark_required:'+symbol)
        size, _, _ = metadata(effective, symbol)
        pos = sum(entry['sign']*entry['quantity'] for entry in queue)
        remaining = sum((entry['sign']*(mark-entry['price'])*size-entry['slip_unit']-entry['fee_unit'])*entry['quantity'] for entry in queue)
        net = episode['cash']+pos*mark*size
        require_close(episode['realized']+remaining, net, 'open_contract_round_conservation')
        open_rows.append({k:episode[k] for k in OPEN_COLUMNS if k in episode} | dict(end_pos=pos,
            terminal_mark=mark, partial_closed_net_pnl=episode['realized'], remaining_open_net_mtm=remaining, net_mtm=net))
        net_positions[symbol] = float(pos); remaining_total += remaining
    sf, rf, of = pd.DataFrame(segments, columns=SEGMENT_COLUMNS), pd.DataFrame(rounds, columns=ROUND_COLUMNS), pd.DataFrame(open_rows, columns=OPEN_COLUMNS)
    closed = pnl_stats(sf); complete = pnl_stats(rf)
    ledger_net = complete['closed_net_pnl']+float(of.net_mtm.sum())
    require_close(closed['closed_net_pnl']+remaining_total, ledger_net, 'FIFO_complete_round_open_conservation')
    return sf, rf, of, dict(closed_fifo=closed, complete_contract_rounds=complete,
        open_round_count=len(of), open_round_partial_closed_net_pnl=float(of.partial_closed_net_pnl.sum()),
        open_round_net_mtm=float(of.net_mtm.sum()), open_remaining_net_mtm=remaining_total,
        open_net_positions=net_positions, ledger_net_pnl=ledger_net, total_slippage=total_slip, total_commission=total_fee,
        fifo_basis='Matched FIFO segments; both entry and exit costs; open remaining inventory excluded.',
        round_basis='Exact real contract, from flat to flat; partial closes within a still-open round excluded from complete rounds.',
        open_basis='Open round net MTM includes its partial realized PnL and remaining inventory MTM, including incurred costs; no synthetic terminal close.')


def curve_metrics(daily, capital=CAPITAL):
    equity = daily.account_equity.astype(float)
    if equity.empty or not np.isfinite(equity).all():
        raise ValueError('empty_or_nonfinite_equity')
    previous = equity.shift(1).fillna(float(capital))
    returns = equity/previous-1. if bool((equity > 0).all()) and capital > 0 else None
    peak = np.maximum.accumulate(np.r_[float(capital), equity.to_numpy()])[1:]
    std = float(returns.std(ddof=1)) if returns is not None else 0.
    return dict(initial_capital=float(capital), end_equity=float(equity.iloc[-1]),
        net_pnl=float(daily.net_pnl.sum()), total_return_pct=float((equity.iloc[-1]/capital-1)*100) if capital else None,
        max_dd_pct=float(((equity.to_numpy()/peak)-1).min()*100),
        sharpe=float(returns.mean()/std*np.sqrt(252)) if std > 0 else None,
        sharpe_basis='Daily simple equity returns including first day vs starting equity; sample stdev ddof=1; annualization sqrt(252); zero risk-free rate.',
        nonpositive_equity_days=int((equity <= 0).sum()), total_slippage=float(daily.slippage.sum()),
        total_commission=float(daily.commission.sum()), modeled_fill_count=int(daily.trade_count.sum()),
        actual_start=daily.date.iloc[0].strftime('%Y-%m-%d'), actual_end=daily.date.iloc[-1].strftime('%Y-%m-%d'), trading_days=len(daily))


def validate_completion(terminal, postflight, acceptances):
    if terminal.get('status') not in {'completed', 'completed_pending_independent_review'} or terminal.get('error'):
        raise ValueError('completed_nonrejected_terminal_required')
    if postflight.get('inputs_unchanged') is not True or postflight.get('mismatches'):
        raise ValueError('postflight_inputs_changed')
    required = {'bar_open_acceptance.json', 'ai_selection_acceptance.json', 'macd_acceptance.json',
                'short_case2_acceptance.json', 'no_position_cap_acceptance.json', 'historical_safety_acceptance.json'}
    if not required.issubset(acceptances):
        raise ValueError('required_acceptance_missing:'+','.join(sorted(required-set(acceptances))))
    for name, proof in acceptances.items():
        if proof.get('accepted') is not True or str(proof.get('verdict', '')).startswith(('REJECT', 'FAIL')):
            raise ValueError('acceptance_not_accepted:'+name)
    if acceptances['bar_open_acceptance.json'].get('verdict') != 'PASS_DECLARED_BAR_OPEN_MODEL':
        raise ValueError('bar_open_acceptance_verdict_required')


def position_aggregates(path, daily, fills, slice_dates):
    use = ['date', 'vt_symbol', 'end_pos', 'close_price', 'net_pnl', 'slippage', 'commission', 'trade_count']
    daily_parts, products, counts = [], defaultdict(float), defaultdict(int)
    marks = {day:{} for day in slice_dates}; positions = {day:{} for day in slice_dates}
    for chunk in pd.read_csv(path, usecols=use, chunksize=100000):
        chunk['date'] = chunk.date.map(trading_day)
        chunk = chunk.loc[chunk.date.between(daily.date.iloc[0].strftime('%Y-%m-%d'), daily.date.iloc[-1].strftime('%Y-%m-%d'))].copy()
        if chunk.empty:
            continue
        chunk['product'] = chunk.vt_symbol.map(product)
        if not np.isfinite(chunk[['end_pos', 'close_price', 'net_pnl', 'slippage', 'commission', 'trade_count']].to_numpy(float)).all():
            raise ValueError('nonfinite_position_ledger')
        daily_parts.append(chunk.groupby('date')[['net_pnl', 'slippage', 'commission', 'trade_count']].sum())
        for key, value in chunk.groupby('product').net_pnl.sum().items():
            products[key] += float(value)
        # One position per product is checked using distinct contracts across chunks below.
        for row in chunk.loc[chunk.end_pos.ne(0)].itertuples():
            counts[(row.date, row.product)] += 1
        for day in slice_dates:
            last = chunk.loc[chunk.date.eq(day)]
            for row in last.itertuples():
                if row.vt_symbol in positions[day]:
                    raise ValueError('duplicate_terminal_position:'+row.vt_symbol)
                positions[day][row.vt_symbol] = float(row.end_pos)
                marks[day][row.vt_symbol] = float(row.close_price)
    if not daily_parts:
        raise ValueError('empty_position_ledger')
    sums = pd.concat(daily_parts).groupby(level=0).sum().reindex(daily.date.dt.strftime('%Y-%m-%d'), fill_value=0)
    for key in ['net_pnl', 'slippage', 'commission', 'trade_count']:
        require_close(np.max(np.abs(sums[key].to_numpy()-daily[key].to_numpy())), 0., 'daily_position_conservation:'+key)
    if any(value > 1 for value in counts.values()):
        raise ValueError('multiple_held_contracts_same_product_day')
    by_day = defaultdict(int)
    for day, _ in counts:
        by_day[day] += 1
    return dict(product_pnl=dict(products), marks=marks, positions=positions,
                max_daily_products=max(by_day.values(), default=0), daily_over4_days=sum(n > 4 for n in by_day.values()))


def load_ledger(path, role):
    path = Path(path).resolve()
    frozen = snapshot_dir(path)
    def read(name):
        p = path/name
        if str(p) not in frozen:
            raise FileNotFoundError(p)
        return json.loads(p.read_text()) if name.endswith('.json') else pd.read_csv(p, low_memory=False)
    terminal, postflight = read('terminal.json'), read('postflight.json')
    proofs = {p.name:read(p.name) for p in sorted(path.glob('*_acceptance.json'))}
    validate_completion(terminal, postflight, proofs)
    if role == 'candidate' and ('week_close_exit_acceptance.json' not in proofs or proofs['week_close_exit_acceptance.json'].get('accepted') is not True):
        raise ValueError('candidate_week_close_exit_acceptance_required')
    pre, settings, effective, source_metrics = [read(n) for n in ['preflight.json', 'actual_strategy_settings.json', 'effective_parameters.json', 'metrics.json']]
    if len(settings) != 1:
        raise ValueError('single_strategy_settings_required')
    actual = settings[0]['actual']
    if any(actual.get(k) is not False for k in FLAGS):
        raise ValueError('disabled_AI_halfR_C2_flags_mismatch')
    if tuple(actual.get(k) for k in ['ma_short', 'ma_mid', 'ma_long']) != (5, 10, 20) or actual.get('research_exact_array_manager_size') != 41:
        raise ValueError('weekly_MA_or_capacity_mismatch')
    if set(pre.get('universe_products', [])) != POOL or pre.get('ready_need') != 21 or pre.get('storage_capacity') != 41:
        raise ValueError('frozen19_or_weekly_readiness_mismatch')
    if pre.get('execution_model') != EXECUTION_MODEL or pre.get('minute_quote_confirmed') is not False:
        raise ValueError('declared_daily_open_model_required')
    for value in [actual.get('capital_base'), settings[0].get('engine_capital'), effective['spec']['capital']['account_capital'], effective['spec']['capital']['c3_capital']]:
        require_close(value, CAPITAL, 'capital_contract')
    if actual.get('max_concurrent_positions') != 19 or proofs['no_position_cap_acceptance.json'].get('MA40_decision_enabled') is not False:
        raise ValueError('max19_and_MA40_off_required')
    for key in ['stage830_broker_margin_multiplier', 'forced_margin_deleverage_broker_multiplier']:
        require_close(actual.get(key), 1.65, 'actual_margin_multiplier:'+key)
    if role == 'baseline':
        if actual.get('enable_rsi_partial_exit') is not True or proofs['short_case2_acceptance.json'].get('short_case2_gate_allowed') is not True:
            raise ValueError('baseline_RSI_and_short_case2_enabled_required')
    if role == 'candidate':
        weekly = proofs['week_close_exit_acceptance.json']
        if weekly.get('rsi_exit_enabled') is not False or weekly.get('short_case2_enabled') is not False or weekly.get('reconciliation_rebuilt_layer_count') != 0 or weekly.get('weekly_stop_guard_failure_count') != 0:
            raise ValueError('candidate_week_close_exit_guard_failure')
        short = proofs['short_case2_acceptance.json']
        if actual.get('enable_rsi_partial_exit') is not False or short.get('short_case2_gate_allowed') is not False or short.get('short_case2_opened') != 0:
            raise ValueError('candidate_no_RSI_no_short_case2_required')
        candidates = read('entry_candidates.csv')
        if ((candidates.signal.eq('short_case2')) & candidates.candidate_status.eq('opened')).any():
            raise ValueError('candidate_short_case2_open_plan_observed')
    quality, reads = read('data_quality.json'), read('data_read_counts.json')
    if any(quality.get(k) for k in ['held_or_traded_daily_gaps', 'held_or_traded_zero_volume', 'captured_bar_failures']):
        raise ValueError('data_quality_failure')
    if any(reads.get(k) != 0 for k in ['minute_reads', 'proxy_reads', 'ai_selection_model_load_attempts']):
        raise ValueError('unexpected_minute_proxy_AI_read')
    hist = proofs['historical_safety_acceptance.json']
    if hist.get('actual_calendar_matches') is not True or hist.get('readiness_calendar_matches') is not True or hist.get('epoch_failure_count') != 0 or hist.get('strict_next_trading_day_open') is not True:
        raise ValueError('historical_safety_contract_failed')
    daily = read('daily.csv')
    daily['date'] = pd.to_datetime(daily.date.map(trading_day))
    if daily.empty or daily.date.duplicated().any() or not daily.date.is_monotonic_increasing:
        raise ValueError('nonempty_unique_chronological_daily_required')
    start, end = str(pre['start']), str(pre['end'])
    if start != '2015-01-01' or daily.date.iloc[0] != pd.Timestamp('2015-01-05') or daily.date.iloc[-1] != pd.Timestamp(end):
        raise ValueError('full_requested_2015_window_required')
    if hist.get('requested_start') != start or hist.get('requested_end') != end:
        raise ValueError('history_requested_window_mismatch')
    numeric = ['account_equity', 'net_pnl', 'slippage', 'commission', 'trade_count', 'total_margin_exact', 'broker10_total_margin_exact']
    if not np.isfinite(daily[numeric].to_numpy(float)).all():
        raise ValueError('nonfinite_daily_ledger')
    require_close(np.max(np.abs(CAPITAL+daily.net_pnl.cumsum()-daily.account_equity)), 0., 'daily_equity_conservation')
    require_close(daily.commission.sum(), 0., 'zero_commission_required')
    require_close(np.max(np.abs(daily.broker10_total_margin_exact-daily.total_margin_exact*1.1)), 0., 'legacy_broker10_is_1p1')
    fills = ordered_fills(read('trades.csv'), read('execution_clock.csv'))
    if not set(fills.trading_date).issubset(set(daily.date.dt.strftime('%Y-%m-%d'))):
        raise ValueError('fill_trade_day_outside_daily_calendar')
    fills['product'] = fills.vt_symbol.map(product)
    slice_dates = sorted({end, *[daily.loc[daily.date.le(f'{y}-12-31'), 'date'].iloc[-1].strftime('%Y-%m-%d') for y in [2019, 2020]]})
    pos = position_aggregates(path/'positions.csv', daily, fills, slice_dates)
    if pos['max_daily_products'] > 19 or proofs['no_position_cap_acceptance.json'].get('max_daily_product_positions') != pos['max_daily_products']:
        raise ValueError('observed_product_position_count_mismatch')
    sf, rf, of, accounting = inventory_accounting(fills, effective, pos['marks'][end])
    for symbol in set(accounting['open_net_positions'])|set(pos['positions'][end]):
        require_close(accounting['open_net_positions'].get(symbol, 0.), pos['positions'][end].get(symbol, 0.), 'terminal_inventory:'+symbol)
    curve = curve_metrics(daily)
    require_close(accounting['ledger_net_pnl'], curve['net_pnl'], 'cash_mark_vs_daily_conservation')
    require_close(accounting['total_slippage'], curve['total_slippage'], 'slippage_conservation')
    require_close(accounting['total_commission'], curve['total_commission'], 'commission_conservation')
    for key in ['end_equity', 'total_return_pct', 'max_dd_pct']:
        require_close(curve[key], source_metrics[key], 'source_metrics:'+key)
    if curve['sharpe'] is None:
        if source_metrics.get('sharpe') is not None:
            raise ValueError('source_sharpe_should_be_undefined')
    else:
        require_close(curve['sharpe'], source_metrics['sharpe'], 'source_metrics:sharpe')
    for count in [daily.trade_count.sum(), source_metrics['total_trade_count'], proofs['bar_open_acceptance.json']['trade_count']]:
        require_close(count, len(fills), 'fill_count_conservation')
    # The explicit database binding gives a directly comparable data identity.
    binding = read('actual_database_binding.json')
    db = Path(binding['expected']).resolve()
    if not any(Path(item[2]).resolve() == db for item in binding['database_list'] if len(item) > 2 and item[2]):
        raise ValueError('actual_database_binding_mismatch')
    manifest = read('input_manifest.json')
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError('nonempty_input_manifest_required')
    sources = dict(frozen)
    for key, digest in manifest.items():
        p = str(Path(key).resolve())
        if p in sources and sources[p] != digest:
            raise ValueError('input_manifest_conflicting_digest:'+p)
        sources[p] = digest
    sources.setdefault(str(db), sha(db))
    verify_sources(sources)
    raw = daily.total_margin_exact/daily.account_equity*100.
    margin = raw*1.65
    risk = dict(actual_broker_margin_multiplier=1.65, legacy_broker10_multiplier=1.1,
        raw_margin_to_equity_average_pct=float(raw.mean()), raw_margin_to_equity_max_pct=float(raw.max()),
        actual_margin_to_equity_average_pct=float(margin.mean()), actual_margin_to_equity_max_pct=float(margin.max()),
        actual_margin_over100_days=int(margin.gt(100).sum()), max_daily_close_products=pos['max_daily_products'], daily_close_over4_days=pos['daily_over4_days'])
    return dict(path=str(path), role=role, daily=daily, fills=fills, segments=sf, rounds=rf, opened=of,
        accounting=accounting, metrics=curve, risk=risk, positions=pos, effective=effective, settings=settings,
        preflight=pre, acceptances=proofs, sources=sources, attempt_snapshot=frozen, database_sha256=sources[str(db)])


def annual_rows(ledger):
    rows, starting = [], CAPITAL
    for year, group in ledger['daily'].groupby(ledger['daily'].date.dt.year, sort=True):
        metrics = curve_metrics(group, starting)
        require_close(metrics['end_equity']-starting, metrics['net_pnl'], 'annual_conservation')
        closed = ledger['segments'].loc[ledger['segments'].exit_trading_date.between(f'{year}-01-01', f'{year}-12-31')]
        rounds = ledger['rounds'].loc[ledger['rounds'].exit_trading_date.between(f'{year}-01-01', f'{year}-12-31')]
        rows.append(dict(role=ledger['role'], year=int(year), period_kind='terminal_year_to_actual_asof' if year == ledger['daily'].date.iloc[-1].year else 'calendar_year',
            **metrics, **{'fifo_'+k:v for k,v in pnl_stats(closed).items()}, **{'round_'+k:v for k,v in pnl_stats(rounds).items()}))
        starting = metrics['end_equity']
    return rows


def product_rows(ledger):
    rows = []
    for p in sorted(POOL):
        fills = ledger['fills'].loc[ledger['fills']['product'].eq(p)]
        closed = ledger['segments'].loc[ledger['segments'].vt_symbol.map(product).eq(p)]
        rounds = ledger['rounds'].loc[ledger['rounds'].vt_symbol.map(product).eq(p)]
        opened = ledger['opened'].loc[ledger['opened'].vt_symbol.map(product).eq(p)]
        row = dict(role=ledger['role'], product=p, modeled_fill_count=len(fills), modeled_fill_volume=float(fills.volume.sum()),
            daily_mtm_net_pnl=ledger['positions']['product_pnl'].get(p, 0.), open_round_net_mtm=float(opened.net_mtm.sum()),
            open_remaining_net_mtm=float(opened.remaining_open_net_mtm.sum()),
            **{'fifo_'+k:v for k,v in pnl_stats(closed).items()}, **{'round_'+k:v for k,v in pnl_stats(rounds).items()})
        require_close(row['daily_mtm_net_pnl'], row['fifo_closed_net_pnl']+row['open_remaining_net_mtm'], 'product_FIFO_conservation:'+p)
        require_close(row['daily_mtm_net_pnl'], row['round_closed_net_pnl']+row['open_round_net_mtm'], 'product_round_conservation:'+p)
        rows.append(row)
    return rows


def slice_rows(ledger):
    rows = []
    for year in [2019, 2020]:
        daily = ledger['daily'].loc[ledger['daily'].date.le(f'{year}-12-31')]
        day = daily.date.iloc[-1].strftime('%Y-%m-%d')
        fills = ledger['fills'].loc[ledger['fills'].trading_date.le(day)]
        _, _, _, accounting = inventory_accounting(fills, ledger['effective'], ledger['positions']['marks'][day])
        metrics = curve_metrics(daily)
        require_close(metrics['net_pnl'], accounting['ledger_net_pnl'], 'slice_conservation:'+str(year))
        rows.append(dict(role=ledger['role'], slice=f'2015-{year}', **metrics,
            **{'fifo_'+k:v for k,v in accounting['closed_fifo'].items()},
            **{'round_'+k:v for k,v in accounting['complete_contract_rounds'].items()},
            open_remaining_net_mtm=accounting['open_remaining_net_mtm'], open_round_net_mtm=accounting['open_round_net_mtm']))
    return rows


def validate_output_paths(out_dir, figure, input_dirs):
    out_dir, figure = Path(out_dir).resolve(), Path(figure).resolve()
    for p in [out_dir, figure]:
        if p.exists():
            raise FileExistsError('refuse_to_overwrite:'+str(p))
    for src in map(lambda x:Path(x).resolve(), input_dirs):
        for p in [out_dir, figure]:
            if p.is_relative_to(src) or src.is_relative_to(p):
                raise ValueError('output_inside_input_or_ancestor:'+str(p))
    if figure == out_dir or out_dir.is_relative_to(figure):
        raise ValueError('invalid_output_figure_overlap')


def plot(ledgers, path):
    os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/weekly-research-mpl')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(13, 8), sharex=True, gridspec_kw={'height_ratios':[2,1]})
    for role, color, label in [('baseline', '#2467a6', 'Baseline: prior daily technical exits'), ('candidate', '#c36f19', 'Candidate: weekly-close exits; no short case2 / RSI exit')]:
        d = ledgers[role]['daily']
        top.plot(d.date, d.account_equity, lw=1.4, color=color, label=label)
        peak = np.maximum.accumulate(np.r_[CAPITAL, d.account_equity.to_numpy()])[1:]
        bottom.plot(d.date, (d.account_equity/peak-1)*100., lw=1.1, color=color)
    top.axhline(CAPITAL, color='#888', lw=.7, ls='--');top.legend(frameon=False, fontsize=9)
    top.set_ylabel('Modeled equity (CNY)');top.yaxis.set_major_formatter(FuncFormatter(lambda x,_:f'{x:,.0f}'))
    bottom.set_ylabel('Drawdown (%)');bottom.set_xlabel('Exchange trading date')
    for ax in [top, bottom]:
        ax.grid(alpha=.2);ax.spines[['top', 'right']].set_visible(False)
    dates = ledgers['baseline']['metrics']
    fig.suptitle('OFFLINE RESEARCH / NO PROMOTION / INDEPENDENT REVIEW PENDING\nOriginal19; weekly MA5/10/20; MA40 / MACD / all AI / half-R / C2 off; max19\n'+
        f"{dates['actual_start']} to {dates['actual_end']}; CNY150,000 each; daily-open model; zero commission; fixed slippage", fontsize=10.5, fontweight='bold')
    fig.tight_layout(rect=[0,0,1,.9]);fig.savefig(path, dpi=170);plt.close(fig)


def build_artifacts(baseline_dir, candidate_dir, out_dir, figure):
    baseline_dir, candidate_dir = Path(baseline_dir).resolve(), Path(candidate_dir).resolve()
    out_dir, figure = Path(out_dir).resolve(), Path(figure).resolve()
    if baseline_dir == candidate_dir:
        raise ValueError('distinct_baseline_candidate_required')
    validate_output_paths(out_dir, figure, [baseline_dir, candidate_dir])
    ledgers = {role:load_ledger(path, role) for role,path in [('baseline', baseline_dir), ('candidate', candidate_dir)]}
    left, right = ledgers['baseline'], ledgers['candidate']
    if not left['daily'].date.equals(right['daily'].date) or left['preflight']['start'] != right['preflight']['start'] or left['preflight']['end'] != right['preflight']['end']:
        raise ValueError('same_requested_and_actual_window_calendar_required')
    if left['database_sha256'] != right['database_sha256']:
        raise ValueError('same_database_snapshot_required')
    parameter_differences = {}
    for group in ['setting', 'actual']:
        a, b = left['settings'][0][group], right['settings'][0][group]
        parameter_differences[group] = {k:{'baseline':a.get(k), 'candidate':b.get(k)} for k in sorted(set(a)|set(b)) if a.get(k) != b.get(k)}
    # An explicit full diff is audit evidence. Candidate-only implementation markers
    # are allowed; undeclared changes to an existing setting are rejected.
    for group, diffs in parameter_differences.items():
        illegal = [k for k in diffs if k != 'enable_rsi_partial_exit' and k in left['settings'][0][group]]
        if illegal:
            raise ValueError('undeclared_existing_setting_changes:'+group+':'+','.join(illegal))
    for key in ['sizes', 'slippages', 'rates']:
        if left['effective'][key] != right['effective'][key]:
            raise ValueError('same_contract_sizes_and_costs_required:'+key)
    sources = {str(Path(__file__).resolve()):sha(__file__)}
    for ledger in ledgers.values():
        for key,digest in ledger['sources'].items():
            if key in sources and sources[key] != digest:
                raise ValueError('comparison_conflicting_source_hash:'+key)
            sources[key] = digest
    annual = [row for ledger in ledgers.values() for row in annual_rows(ledger)]
    products = [row for ledger in ledgers.values() for row in product_rows(ledger)]
    slices = [row for ledger in ledgers.values() for row in slice_rows(ledger)]
    arms = {role:dict(attempt_path=l['path'], actual_strategy_class=l['settings'][0]['strategy_class'],
        metrics=l['metrics'], accounting=l['accounting'], risk=l['risk'], database_sha256=l['database_sha256'],
        acceptance_files=sorted(l['acceptances']), terminal_open_positions=l['opened'].to_dict('records')) for role,l in ledgers.items()}
    summary = dict(schema='stage029_parameterized_derived_comparison_v1', generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        status='DERIVED_PENDING_INDEPENDENT_REVIEW', independent_review_verdict=None, production_qualified=False,
        promotion_decision='NO_PROMOTION', financial_replays=0, arms=arms, parameter_differences=parameter_differences,
        comparison={key:right['metrics'][key]-left['metrics'][key] for key in ['end_equity', 'total_return_pct', 'max_dd_pct']},
        contract=dict(requested_start=left['preflight']['start'], requested_end=left['preflight']['end'],
            actual_asof=left['metrics']['actual_end'], capital=CAPITAL, pool=sorted(POOL), execution_model=EXECUTION_MODEL,
            commission='zero', slippage='fixed source effective_parameters', actual_margin_multiplier=1.65, legacy_broker10_multiplier=1.1),
        limitations=['Repeated historical sample and combined three-item ablation; not independent marginal attribution, PIT, OOS, or promotion evidence.',
            'Static original19 universe, zero commission, fixed slippage and daily-open fills; spread/depth/queue/capacity qualification absent.',
            'Stage028 source disputes, accepted-observation week gaps and historical main mapping timestamp limitations remain.',
            'Full contract rounds do not merge different rollover contracts. Still-open rounds include partial realized PnL; terminal inventory is marked, never forcibly closed.',
            'Accepted replay gates and accounting derivation are not an independent result review.'], source_files_sha256=sources)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    if not figure.is_relative_to(out_dir):
        figure.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.stage029_report_', dir=out_dir.parent) as temporary:
        temp = Path(temporary);tables = temp/'tables';tables.mkdir();pic = temp/'equity_drawdown.png'
        pd.DataFrame(annual).to_csv(tables/'annual.csv', index=False)
        pd.DataFrame(products).to_csv(tables/'products.csv', index=False)
        pd.DataFrame(slices).to_csv(tables/'slices_2015_2019_2020.csv', index=False)
        pd.DataFrame([dict(role=role, **l['metrics'], **{'fifo_'+k:v for k,v in l['accounting']['closed_fifo'].items()},
            **{'round_'+k:v for k,v in l['accounting']['complete_contract_rounds'].items()}, **l['risk'],
            open_remaining_net_mtm=l['accounting']['open_remaining_net_mtm'], open_round_net_mtm=l['accounting']['open_round_net_mtm']) for role,l in ledgers.items()]).to_csv(tables/'summary.csv', index=False)
        for name, key in [('closed_fifo_segments.csv', 'segments'), ('complete_contract_rounds.csv', 'rounds'), ('terminal_open_rounds.csv', 'opened')]:
            frames = [l[key].assign(role=role) for role,l in ledgers.items()]
            pd.concat(frames, ignore_index=True).to_csv(tables/name, index=False)
        for role,l in ledgers.items():
            l['daily'][['date', 'account_equity', 'net_pnl', 'slippage', 'commission', 'trade_count']].to_csv(tables/(role+'_daily.csv'), index=False)
        plot(ledgers, pic)
        summary['output_files_sha256'] = {str(out_dir/p.name):sha(p) for p in sorted(tables.glob('*.csv'))}
        summary['output_files_sha256'][str(figure)] = sha(pic)
        (tables/'comparison.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
        manifest = dict(schema='stage029_report_delivery_manifest_v1', comparison_sha256=sha(tables/'comparison.json'),
            files_sha256={**summary['output_files_sha256'], str(out_dir/'comparison.json'):sha(tables/'comparison.json')},
            self_hash_excluded=True, independent_review_verdict=None)
        (tables/'delivery_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
        verify_sources(sources)
        for ledger in ledgers.values():
            if snapshot_dir(ledger['path']) != ledger['attempt_snapshot']:
                raise ValueError('attempt_file_set_or_bytes_changed:'+ledger['path'])
        validate_output_paths(out_dir, figure, [baseline_dir, candidate_dir])
        if figure.is_relative_to(out_dir):
            (tables/figure.relative_to(out_dir)).parent.mkdir(parents=True, exist_ok=True)
            os.link(pic, tables/figure.relative_to(out_dir))
            os.rename(tables, out_dir)
        else:
            os.link(pic, figure)
            try:
                os.rename(tables, out_dir)
            except Exception:
                figure.unlink()
                raise
    return dict(status='DERIVED_PENDING_INDEPENDENT_REVIEW', outputs=[str(out_dir), str(figure)], financial_replays=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-dir', type=Path, required=True)
    parser.add_argument('--candidate-dir', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path, required=True)
    parser.add_argument('--figure', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_artifacts(args.baseline_dir, args.candidate_dir, args.out_dir, args.figure), ensure_ascii=False))


if __name__ == '__main__':
    main()
