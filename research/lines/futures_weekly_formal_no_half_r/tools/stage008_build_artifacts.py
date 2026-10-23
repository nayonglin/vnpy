"""Read completed E/G ledgers and derive new Stage008 artifacts only.

No engine, market data download, financial replay or price repair is imported.
Unreviewed G stays conditional diagnostic.  A rejected execution audit rejects
its entire path; modeled counts never become qualified executable counts.
"""
from __future__ import annotations
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import re
import tempfile
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

CAPITAL = 150000.
START = '2020-01-01'
END = '2026-10-22'
FLAGS = ['enable_stage847_half_r_stop_retry', 'enable_stage827_intraday_c2_stop', 'enable_ai_product_pool_filter']
SEGMENT_COLUMNS = ['vt_symbol', 'direction', 'entry_trade_id', 'exit_trade_id',
    'entry_execution_datetime', 'exit_execution_datetime', 'volume', 'entry_price', 'exit_price',
    'contract_size', 'entry_slippage', 'exit_slippage', 'entry_commission', 'exit_commission', 'gross_pnl', 'net_pnl']


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1048576), b''):
            digest.update(chunk)
    return digest.hexdigest()


def require_close(actual, expected, name, tolerance=1e-6):
    if not math.isfinite(float(actual)) or abs(float(actual)-float(expected)) > tolerance:
        raise ValueError(f'{name}:{actual!r}!={expected!r}')


def native_product(vt_symbol, products):
    match = re.fullmatch(r'([A-Za-z]+)[0-9]{3,4}(F?)\.([A-Z]+)', str(vt_symbol))
    if match is None:
        raise ValueError('native_contract_parse_failed:'+str(vt_symbol))
    product = match.group(1)+('_F' if match.group(2) else '')+'.'+match.group(3)
    if product not in products:
        raise ValueError('native_contract_outside_frozen19:'+str(vt_symbol))
    return product


def _utc(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp):
        raise ValueError('missing_actual_execution_datetime')
    return stamp.tz_localize('Asia/Shanghai').tz_convert('UTC') if stamp.tzinfo is None else stamp.tz_convert('UTC')


def ordered_fills(trades, clock=None):
    result = trades.copy()
    if result.empty:
        if clock is not None and not clock.empty:
            raise ValueError('execution_clock_trade_ids_mismatch')
        for name in ['trade_id','vt_symbol','direction','offset','price','volume','execution_datetime','datetime','trading_date','date']:
            if name not in result:
                result[name] = pd.Series(dtype=float if name in ['price','volume'] else str)
        return result
    result['trade_id'] = result.trade_id.astype(str)
    if result.trade_id.duplicated().any():
        raise ValueError('duplicate_trade_id')
    if clock is not None:
        clock = clock.copy()
        clock['trade_id'] = clock.trade_id.astype(str)
        if clock.trade_id.duplicated().any() or set(clock.trade_id) != set(result.trade_id):
            raise ValueError('execution_clock_trade_ids_mismatch')
        check = clock.set_index('trade_id')
        for row in result.itertuples():
            actual = check.loc[row.trade_id]
            for name in ['vt_symbol', 'direction', 'offset']:
                if name in check and str(getattr(row, name)) != str(actual[name]):
                    raise ValueError('execution_clock_identity_mismatch:'+name)
            for name in ['price', 'volume']:
                if name in check:
                    require_close(getattr(row, name), actual[name], 'execution_clock_'+name, 1e-8)
        clock['_clock_order'] = np.arange(len(clock))
        result = result.merge(clock[['trade_id', 'execution_datetime', '_clock_order']], on='trade_id', validate='one_to_one')
    else:
        if 'execution_datetime' not in result:
            if 'datetime' not in result:
                raise ValueError('actual_execution_clock_required')
            result['execution_datetime'] = result['datetime']
        result['_clock_order'] = np.arange(len(result))
    result['_execution_utc'] = result.execution_datetime.map(_utc)
    return result.sort_values(['_execution_utc', '_clock_order'], kind='stable').reset_index(drop=True)


def _direction(value):
    value = str(value).lower()
    if value in {'多', 'long'}:
        return 1
    if value in {'空', 'short'}:
        return -1
    raise ValueError('unsupported_trade_direction:'+value)


def _offset(value):
    value = str(value).lower().replace(' ', '')
    if value in {'开', 'open'}:
        return 'open'
    if value in {'平', '平今', '平昨', 'close', 'closetoday', 'closeyesterday'}:
        return 'close'
    raise ValueError('unsupported_trade_offset:'+value)


def _metadata(effective, symbol):
    try:
        size, slip, rate = (float(effective[key][symbol]) for key in ['sizes', 'slippages', 'rates'])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('effective_metadata_missing_or_invalid:'+symbol) from exc
    if not all(math.isfinite(x) for x in [size, slip, rate]) or size <= 0 or slip < 0 or rate < 0:
        raise ValueError('effective_metadata_out_of_range:'+symbol)
    return size, slip, rate


def fifo_segments(trades, effective, clock=None, terminal_marks=None):
    fills = ordered_fills(trades, clock)
    inventory = defaultdict(deque)
    segments = []
    total_slippage = total_commission = cash = 0.
    for row in fills.to_dict('records'):
        symbol = str(row['vt_symbol'])
        price, quantity = float(row['price']), float(row['volume'])
        if not (math.isfinite(price) and price > 0 and math.isfinite(quantity) and quantity > 0):
            raise ValueError('invalid_fill_price_or_quantity:'+str(row['trade_id']))
        size, slip, rate = _metadata(effective, symbol)
        sign, offset = _direction(row['direction']), _offset(row['offset'])
        slip_unit, fee_unit = size*slip, size*price*rate
        total_slippage += slip_unit*quantity
        total_commission += fee_unit*quantity
        cash -= sign*price*size*quantity+(slip_unit+fee_unit)*quantity
        queue = inventory[symbol]
        if offset == 'open':
            if queue and queue[0]['sign'] != sign:
                raise ValueError('opposing_open_without_close:'+symbol)
            queue.append(dict(sign=sign, quantity=quantity, price=price,
                trade_id=str(row['trade_id']), execution_datetime=str(row['execution_datetime']),
                slip_unit=slip_unit, fee_unit=fee_unit))
            continue
        remaining = quantity
        while remaining > 1e-9:
            if not queue or queue[0]['sign'] != -sign:
                raise ValueError('unmatched_close:'+str(row['trade_id']))
            entry = queue[0]
            matched = min(remaining, entry['quantity'])
            gross = entry['sign']*(price-entry['price'])*size*matched
            entry_slip, exit_slip = entry['slip_unit']*matched, slip_unit*matched
            entry_fee, exit_fee = entry['fee_unit']*matched, fee_unit*matched
            segments.append(dict(vt_symbol=symbol, direction='long' if entry['sign'] > 0 else 'short',
                entry_trade_id=entry['trade_id'], exit_trade_id=str(row['trade_id']),
                entry_execution_datetime=entry['execution_datetime'], exit_execution_datetime=str(row['execution_datetime']),
                volume=matched, entry_price=entry['price'], exit_price=price, contract_size=size,
                entry_slippage=entry_slip, exit_slippage=exit_slip,
                entry_commission=entry_fee, exit_commission=exit_fee,
                gross_pnl=gross, net_pnl=gross-entry_slip-exit_slip-entry_fee-exit_fee))
            entry['quantity'] -= matched
            remaining -= matched
            if entry['quantity'] <= 1e-9:
                queue.popleft()
    frame = pd.DataFrame(segments, columns=SEGMENT_COLUMNS)
    wins, losses = frame.loc[frame.net_pnl > 1e-8], frame.loc[frame.net_pnl < -1e-8]
    average_win = float(wins.net_pnl.mean()) if len(wins) else None
    average_loss = float(-losses.net_pnl.mean()) if len(losses) else None
    net_positions = {symbol:float(sum(entry['sign']*entry['quantity'] for entry in queue))
        for symbol, queue in inventory.items() if queue}
    open_quantity = float(sum(entry['quantity'] for queue in inventory.values() for entry in queue))
    open_gross = open_cost = terminal_value = 0.
    if open_quantity and terminal_marks is None:
        open_net = ledger_net = None
    else:
        for symbol, queue in inventory.items():
            if not queue:
                continue
            if symbol not in terminal_marks or not math.isfinite(float(terminal_marks[symbol])) or float(terminal_marks[symbol]) <= 0:
                raise ValueError('terminal_real_mark_required:'+symbol)
            mark = float(terminal_marks[symbol]);size, _, _ = _metadata(effective, symbol)
            for entry in queue:
                open_gross += entry['sign']*(mark-entry['price'])*size*entry['quantity']
                open_cost += (entry['slip_unit']+entry['fee_unit'])*entry['quantity']
                terminal_value += entry['sign']*mark*size*entry['quantity']
        open_net = open_gross-open_cost
        ledger_net = cash+terminal_value
        require_close(frame.net_pnl.sum()+open_net, ledger_net, 'FIFO_cash_mark_conservation')
    stats = dict(closed_segments=len(frame), winning_segments=len(wins), losing_segments=len(losses),
        breakeven_segments=int(len(frame)-len(wins)-len(losses)),
        closed_quantity=float(frame.volume.sum()), closed_net_pnl=float(frame.net_pnl.sum()),
        win_rate_pct=float(len(wins)/len(frame)*100) if len(frame) else None,
        quantity_weighted_win_rate_pct=float(wins.volume.sum()/frame.volume.sum()*100) if len(frame) else None,
        average_winning_segment=average_win, average_losing_segment_abs=average_loss,
        payoff_ratio=average_win/average_loss if average_win is not None and average_loss else None,
        profit_factor=float(wins.net_pnl.sum()/-losses.net_pnl.sum()) if len(losses) else None,
        open_quantity=open_quantity, open_net_positions=net_positions,
        open_unrealized_net=open_net, ledger_net_pnl=ledger_net,
        total_slippage=total_slippage, total_commission=total_commission,
        win_rate_basis='closed FIFO matched segments after both entry and exit slippage/commission; open inventory excluded; segments are not independent strategy rounds')
    return frame, stats


def curve_metrics(daily, capital=CAPITAL):
    equity = daily.account_equity.astype(float)
    if equity.empty or not np.isfinite(equity.to_numpy()).all():
        raise ValueError('empty_or_nonfinite_equity')
    positive = bool((equity > 0).all())
    previous = equity.shift(1).fillna(float(capital))
    returns = equity/previous-1. if positive else None
    peak = np.maximum.accumulate(np.r_[float(capital), equity.to_numpy()])[1:]
    std = float(returns.std(ddof=1)) if positive else 0.
    return dict(end_equity=float(equity.iloc[-1]), total_return_pct=float((equity.iloc[-1]/capital-1)*100),
        max_dd_pct=float(((equity.to_numpy()/peak)-1).min()*100),
        sharpe=float(returns.mean()/std*np.sqrt(252)) if std > 0 else None,
        nonpositive_equity_days=int((equity <= 0).sum()),
        total_slippage=float(daily.slippage.sum()), total_commission=float(daily.commission.sum()),
        modeled_fill_count=int(daily.trade_count.sum()), initial_capital=float(capital),
        actual_start=daily.date.iloc[0].strftime('%Y-%m-%d'), actual_end=daily.date.iloc[-1].strftime('%Y-%m-%d'),
        trading_days=len(daily))


def classify_g(audit, review=None, g_path=None):
    audit = audit or {}
    review_verdict = None
    if review is not None:
        if review.get('schema') != 'stage008_independent_review_v1' or g_path is None:
            raise ValueError('unsupported_or_unbound_final_review_schema')
        if Path(review.get('g_attempt_path', '')).resolve() != Path(g_path).resolve():
            raise ValueError('final_review_wrong_G_attempt')
        review_verdict = str(review.get('verdict', ''))
        if review_verdict != 'PASS_OFFLINE_RESEARCH' and not review_verdict.startswith('REJECT_'):
            raise ValueError('unsupported_final_review_verdict')
    verdict = str(audit.get('verdict', 'NOT_ESTABLISHED'))
    rejected = audit.get('accepted') is False or verdict.startswith('REJECT_') or (review_verdict or '').startswith('REJECT_')
    passed_minutes = audit.get('accepted') is True and verdict == 'PASS_POSITIVE_EXECUTION_MINUTES'
    accepted = bool(not rejected and passed_minutes and review_verdict == 'PASS_OFFLINE_RESEARCH')
    if rejected:
        classification = 'DIAGNOSTIC_ONLY_EXECUTION_REJECTED'
        if (review_verdict or '').startswith('REJECT_'):
            verdict = review_verdict
        elif not verdict.startswith('REJECT_'):
            verdict = 'REJECT_EXECUTION_AUDIT'
    elif accepted:
        classification = 'REVIEWED_OFFLINE_RESEARCH_NO_PROMOTION'
    else:
        classification = 'CONDITIONAL_DIAGNOSTIC_PENDING_INDEPENDENT_REVIEW'
    return dict(performance_classification=classification, execution_audit_status=verdict,
        valid_performance_accepted=accepted, production_qualified=False, promotion_decision='NO_PROMOTION',
        qualified_executable_trade_count=None, qualified_executable_product_count=None,
        qualified_counts_status='NOT_ESTABLISHED: offline model fills/products are not production or executable-capacity qualification')


def _stamp(row, status):
    return {**row, 'performance_classification':status['performance_classification'],
        'execution_audit_status':status['execution_audit_status'], 'production_qualified':False,
        'qualified_executable_counts_status':status['qualified_counts_status']}


def annual_rows(daily, arm, status, capital=CAPITAL):
    rows, starting = [], float(capital)
    daily = daily.sort_values('date')
    terminal_year = int(daily.date.iloc[-1].year)
    for year, group in daily.groupby(daily.date.dt.year, sort=True):
        ending, pnl = float(group.account_equity.iloc[-1]), float(group.net_pnl.sum())
        require_close(ending-starting, pnl, 'annual_equity_pnl_conservation')
        rows.append(_stamp(dict(arm=arm, year=int(year), period=f'{year} YTD' if int(year)==terminal_year else str(year),
            period_start=group.date.iloc[0].strftime('%Y-%m-%d'), period_end=group.date.iloc[-1].strftime('%Y-%m-%d'),
            starting_equity=starting, ending_equity=ending, net_pnl=pnl, return_pct=(ending/starting-1)*100 if starting else None,
            modeled_fill_count=int(group.trade_count.sum()), slippage=float(group.slippage.sum()), commission=float(group.commission.sum())),status))
        starting = ending
    return rows


def load_ledger(path, arm, products):
    path = Path(path).resolve()
    sources = {}
    def read(name):
        p = path/name;sources[str(p)] = sha(p)
        return json.loads(p.read_text()) if name.endswith('.json') else pd.read_csv(p,low_memory=False)
    terminal, metrics, effective = (read(name) for name in ['terminal.json','metrics.json','effective_parameters.json'])
    status = str(terminal.get('status',''))
    if terminal.get('error') or not (status.startswith('completed') or status.startswith('rejected_reject_execution_')):
        raise ValueError('complete_ledger_required:'+arm)
    settings, preflight = read('actual_strategy_settings.json'), read('preflight.json')
    expected_class = 'WeeklyIndicatorsStrategy' if arm=='E' else 'ThreeMaWeeklyIndicatorsStrategy'
    if len(settings)!=1 or settings[0]['strategy_class']!=expected_class or any(settings[0]['actual'].get(k) is not False for k in FLAGS):
        raise ValueError('actual_arm_class_or_disabled_flags_mismatch:'+arm)
    if int(settings[0]['actual']['research_exact_array_manager_size'])!=41:
        raise ValueError('history_storage_capacity_changed:'+arm)
    if len(products)!=19 or set(preflight['universe_products'])!=set(products):
        raise ValueError('frozen_original19_mismatch:'+arm)
    require_close(settings[0]['engine_capital'],CAPITAL,'engine_capital')
    for key in ['account_capital','c3_capital']:
        require_close(effective['spec']['capital'][key],CAPITAL,'effective_'+key)
    expected_scope = 'weekly_half_r_c2_ai_off_same_data_original19' if arm=='E' else 'weekly_three_ma_half_r_c2_ai_off_original19'
    if metrics.get('arm')!=arm or metrics.get('result_scope')!=expected_scope:
        raise ValueError('arm_result_scope_mismatch:'+arm)
    daily, trades, positions, clock = (read(name) for name in ['daily.csv','trades.csv','positions.csv','execution_clock.csv'])
    if trades.empty:trades = ordered_fills(trades, clock)
    daily['date'] = pd.to_datetime(daily.date).dt.normalize()
    if daily.date.duplicated().any() or not daily.date.between(START,END).all():
        raise ValueError('invalid_account_calendar:'+arm)
    daily = daily.sort_values('date').reset_index(drop=True)
    if daily.empty or daily.date.iloc[-1]!=pd.Timestamp(END):
        raise ValueError('full_requested_account_window_required:'+arm)
    for col in ['account_equity','net_pnl','slippage','commission','trade_count']:
        daily[col] = pd.to_numeric(daily[col],errors='raise')
        if not np.isfinite(daily[col].to_numpy(float)).all():
            raise ValueError('nonfinite_account_column:'+col)
    require_close(np.abs((CAPITAL+daily.net_pnl.cumsum())-daily.account_equity).max(),0.,'daily_account_conservation')
    positions['date'] = pd.to_datetime(positions.date).dt.normalize()
    positions = positions.loc[positions.date.between(START,END)].copy()
    trade_days = pd.to_datetime(trades['trading_date'] if 'trading_date' in trades else trades.date)
    if not trade_days.between(START,END).all():
        raise ValueError('trade_outside_account_window')
    for frame in [trades,positions]:
        frame['product_vt_symbol'] = frame.vt_symbol.map(lambda symbol:native_product(symbol,products))
    terminal_positions = positions.loc[positions.date.eq(daily.date.iloc[-1])]
    if terminal_positions.vt_symbol.duplicated().any():
        raise ValueError('duplicate_terminal_position')
    marks = dict(zip(terminal_positions.vt_symbol,terminal_positions.close_price))
    segments, fifo = fifo_segments(trades,effective,clock,marks)
    if len(segments):
        segments['product_vt_symbol'] = segments.vt_symbol.map(lambda symbol:native_product(symbol,products))
    else:
        segments['product_vt_symbol'] = pd.Series(dtype=str)
    actual_pos = terminal_positions.set_index('vt_symbol').end_pos.astype(float).to_dict()
    for symbol in set(actual_pos)|set(fifo['open_net_positions']):
        require_close(actual_pos.get(symbol,0.),fifo['open_net_positions'].get(symbol,0.),'FIFO_terminal_position:'+symbol)
    recomputed = curve_metrics(daily)
    require_close(recomputed['end_equity'],metrics['end_equity'],'source_end_equity')
    require_close(recomputed['total_return_pct'],metrics['total_return_pct'],'source_return')
    require_close(recomputed['max_dd_pct'],metrics['max_dd_pct'],'source_drawdown')
    if recomputed['sharpe'] is not None:
        require_close(recomputed['sharpe'],metrics['sharpe'],'source_sharpe')
    require_close(recomputed['modeled_fill_count'],len(trades),'source_fill_count')
    require_close(metrics['total_trade_count'],len(trades),'source_metrics_fill_count')
    require_close(fifo['total_slippage'],daily.slippage.sum(),'FIFO_slippage')
    require_close(fifo['total_commission'],daily.commission.sum(),'FIFO_commission')
    require_close(daily.commission.sum(),0.,'zero_commission_contract')
    require_close(fifo['ledger_net_pnl'],daily.account_equity.iloc[-1]-CAPITAL,'FIFO_full_ledger_conservation')
    require_close(positions.net_pnl.sum(),daily.net_pnl.sum(),'product_MTM_conservation')
    recomputed.update(pool_product_count=19,modeled_traded_product_count=int(trades.product_vt_symbol.nunique()),
        modeled_traded_products=sorted(trades.product_vt_symbol.unique()),modeled_fill_volume=float(trades.volume.sum()))
    optional = {}
    for name in ['postflight.json','data_quality.json','weekly_coverage.json','execution_volume_acceptance.json']:
        if (path/name).exists():optional[name] = read(name)
    if optional.get('postflight.json',{}).get('inputs_unchanged') is False:
        raise ValueError('input_mutation_rejected')
    quality = optional.get('data_quality.json',{})
    if any(quality.get(k) for k in ['held_or_traded_daily_gaps','held_or_traded_zero_volume','captured_bar_failures']):
        raise ValueError('daily_data_or_execution_failure_not_qualified_for_completed_report')
    return dict(path=str(path),arm=arm,daily=daily,trades=trades,positions=positions,effective=effective,
        source_metrics=metrics,metrics=recomputed,segments=segments,fifo_stats=fifo,
        sources=sources,optional=optional,terminal=terminal,
        identity_basis='actual class/settings, original19 preflight, full chronological execution clock and conserved ledger; inherited labels/deployable_pass excluded')


def product_rows(ledger, products, status):
    trades, positions, segments = ledger['trades'],ledger['positions'],ledger['segments']
    rows = []
    for product in sorted(products):
        t = trades.loc[trades.product_vt_symbol.eq(product)]
        p = positions.loc[positions.product_vt_symbol.eq(product)]
        s = segments.loc[segments.product_vt_symbol.eq(product)]
        rows.append(_stamp(dict(arm=ledger['arm'],product_vt_symbol=product,
            modeled_fill_count=len(t),modeled_fill_volume=float(t.volume.sum()),
            net_pnl_daily_mtm=float(p.net_pnl.sum()),closed_fifo_segments=len(s),
            closed_fifo_net_pnl=float(s.net_pnl.sum()),
            zero_fill_interpretation='zero modeled fills is not evidence that no raw signal occurred',
            pnl_basis='daily MTM of coupled portfolio, includes terminal unrealized; not independent product marginal alpha'),status))
    require_close(sum(r['modeled_fill_count'] for r in rows),len(trades),'product_fill_conservation')
    require_close(sum(r['net_pnl_daily_mtm'] for r in rows),ledger['daily'].net_pnl.sum(),'product_net_conservation')
    return rows


def require_new_outputs(paths):
    for path in paths:
        if Path(path).exists():
            raise FileExistsError('refuse_to_overwrite_existing_artifact:'+str(path))


def plot_comparison(ledgers,statuses,path):
    os.environ.setdefault('MPLCONFIGDIR','/private/tmp/weekly-research-mpl')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    g_status=statuses['G'];rejected='REJECTED' in g_status['performance_classification']
    reviewed=g_status['valid_performance_accepted']
    title='G DIAGNOSTIC ONLY - EXECUTION REJECTED' if rejected else (
        'E / G OFFLINE RESEARCH - NO PROMOTION' if reviewed else 'G CONDITIONAL DIAGNOSTIC - INDEPENDENT REVIEW PENDING')
    fig,(top,bottom)=plt.subplots(2,1,figsize=(12.5,7.8),sharex=True,gridspec_kw={'height_ratios':[2.1,1]})
    for arm,color in [('E','#2864A5'),('G','#B3261E' if rejected else '#C16A08')]:
        d=ledgers[arm]['daily'];label='E: reviewed 4-MA baseline (19 products)' if arm=='E' else (
            'G: 3-MA DIAGNOSTIC ONLY / REJECTED' if rejected else 'G: 3-MA offline research' if reviewed else 'G: 3-MA CONDITIONAL DIAGNOSTIC / PENDING')
        style='--' if arm=='G' and not reviewed else '-'
        top.plot(d.date,d.account_equity,color=color,lw=1.5,ls=style,label=label)
        peak=np.maximum.accumulate(np.r_[CAPITAL,d.account_equity.to_numpy()])[1:]
        bottom.plot(d.date,(d.account_equity/peak-1)*100,color=color,lw=1.2,ls=style)
    top.axhline(CAPITAL,color='#777777',lw=.7,ls='--');top.set_ylabel('Modeled equity (CNY)')
    top.yaxis.set_major_formatter(FuncFormatter(lambda value,_:f'{value:,.0f}'));top.legend(frameon=False,fontsize=9)
    bottom.axhline(0,color='#777777',lw=.7);bottom.set_ylabel('Drawdown (%)');bottom.set_xlabel('Trading date')
    for axis in [top,bottom]:axis.grid(alpha=.2);axis.spines[['top','right']].set_visible(False)
    fig.suptitle(title+'\nOriginal 19; MA5/10/20 vs MA5/10/20/40; completed weeks; Half-R/C2/AI off\nCNY 150,000; 2020-01-01 to 2026-10-22; zero commission; no production qualification',
        fontsize=11,color='#A8201A' if rejected else '#383838',fontweight='bold')
    if not reviewed:
        top.text(.99,.02,'G METRICS AND COUNTS ARE CONDITIONAL MODEL DIAGNOSTICS',transform=top.transAxes,
            ha='right',va='bottom',fontsize=8,color='#A8201A',bbox=dict(facecolor='white',alpha=.88,edgecolor='#A8201A'))
    fig.tight_layout(rect=[0,0,1,.90]);fig.savefig(path,dpi=170);plt.close(fig)


def build_artifacts(line_dir, review_json=None):
    line=Path(line_dir).resolve();out=line/'outputs';art=line/'artifacts'
    table_dir=art/'stage008';plot_path=art/'stage008_equity_drawdown.png'
    require_new_outputs([table_dir,plot_path])
    old_artifacts={str(p):sha(p) for p in art.rglob('*') if p.is_file()} if art.exists() else {}
    pointer_path=out/'G_completed_attempt.json';pointer=json.loads(pointer_path.read_text())
    g_path=Path(pointer['path']).resolve()
    if g_path.parent!=out.resolve() or not re.fullmatch(r'G_attempt[0-9]{3}',g_path.name):
        raise ValueError('G_completed_pointer_outside_scope')
    e_path=out/'E_attempt009';preflight=e_path/'preflight.json'
    products=set(json.loads(preflight.read_text())['universe_products'])
    ledgers={arm:load_ledger(path,arm,products) for arm,path in [('E',e_path),('G',g_path)]}
    if not ledgers['E']['daily'].date.equals(ledgers['G']['daily'].date):
        raise ValueError('E_G_account_calendar_not_identical')
    review=None;sources={str(pointer_path):sha(pointer_path)}
    if review_json is not None:
        review_json=Path(review_json).resolve();review=json.loads(review_json.read_text());sources[str(review_json)]=sha(review_json)
    statuses={'E':dict(performance_classification='REVIEWED_OFFLINE_RESEARCH_BASELINE',execution_audit_status='PREVIOUSLY_REVIEWED_E009',
        valid_performance_accepted=True,production_qualified=False,promotion_decision='NO_PROMOTION',
        qualified_executable_trade_count=None,qualified_executable_product_count=None,
        qualified_counts_status='NOT_ESTABLISHED: reviewed offline research is not production or executable-capacity qualification'),
        'G':classify_g(ledgers['G']['optional'].get('execution_volume_acceptance.json'),review,g_path)}
    annual=pd.DataFrame([row for arm,ledger in ledgers.items() for row in annual_rows(ledger['daily'],arm,statuses[arm])])
    products_table=pd.DataFrame([row for arm,ledger in ledgers.items() for row in product_rows(ledger,products,statuses[arm])])
    segment_tables=[];arm_summaries={}
    for arm,ledger in ledgers.items():
        sources.update(ledger['sources']);segments=ledger['segments'].copy();segments.insert(0,'arm',arm)
        for key in ['performance_classification','execution_audit_status','qualified_counts_status']:
            segments[key]=statuses[arm][key]
        segment_tables.append(segments)
        arm_summaries[arm]=dict(path=ledger['path'],**statuses[arm],modeled_metrics=ledger['metrics'],
            closed_fifo=ledger['fifo_stats'],identity_basis=ledger['identity_basis'],
            weekly_coverage=ledger['optional'].get('weekly_coverage.json'),
            metrics_basis='conserved offline modeled ledger; diagnostic if rejected or review pending; zero commission')
    summary=dict(schema='stage008_three_ma_original19_artifacts_v1',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        contract=dict(start=START,end=END,capital=CAPITAL,products=sorted(products),pool_count=19,
            E_MA_periods=[5,10,20,40],G_MA_periods=[5,10,20],G_storage=41,G_cross_ready=21,G_rollover_shape_need=20,
            G_simple_trend_need=25,half_R=False,C2=False,AI=False),arms=arm_summaries,
        comparison=dict(modeled_ending_equity_G_minus_E=ledgers['G']['metrics']['end_equity']-ledgers['E']['metrics']['end_equity'],
            modeled_return_pct_G_minus_E=ledgers['G']['metrics']['total_return_pct']-ledgers['E']['metrics']['total_return_pct'],
            modeled_drawdown_pct_G_minus_E=ledgers['G']['metrics']['max_dd_pct']-ledgers['E']['metrics']['max_dd_pct'],
            interpretation='arithmetic comparison only; rejected/pending G does not establish valid executable superiority'),
        final_independent_review=None if review_json is None else dict(path=str(review_json),sha256=sha(review_json),verdict=review.get('verdict')),
        promotion_decision='NO_PROMOTION',production_qualified=False,financial_replays=0,
        limitations=['All unreviewed or execution-rejected G values and counts are conditional model diagnostics.',
            'Zero commission and fixed slippage; positive minute volume does not establish spread/depth/queue/capacity.',
            'Not a new PIT/OOS test; repeated historical-window use and original data limitations remain.',
            'Per-product MTM is a coupled-account decomposition, not independent marginal alpha.',
            'FIFO matched segments can split one entry; win rate is not win-day rate or independent strategy-round probability.',
            'Storage41/readiness21 are separate; 30-period risk warms at31; inherited rollover shape can act at20 observations.',
            'Inherited labels, notes and deployable_pass are not qualification or arm identity.'],
        source_files_sha256=sources)
    art.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.stage008_build_',dir=art) as temporary:
        temp=Path(temporary);annual.to_csv(temp/'annual.csv',index=False);products_table.to_csv(temp/'products.csv',index=False)
        pd.concat(segment_tables,ignore_index=True).to_csv(temp/'closed_fifo_segments.csv',index=False)
        plot_comparison(ledgers,statuses,temp/'stage008_equity_drawdown.png')
        summary['output_files_sha256']={name:sha(temp/name) for name in ['annual.csv','products.csv','closed_fifo_segments.csv','stage008_equity_drawdown.png']}
        (temp/'comparison.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        for path,digest in sources.items():
            if sha(path)!=digest:raise ValueError('source_changed_while_building:'+path)
        for path,digest in old_artifacts.items():
            if sha(path)!=digest:raise ValueError('previous_artifact_changed:'+path)
        require_new_outputs([table_dir,plot_path]);table_dir.mkdir()
        for name in ['annual.csv','products.csv','comparison.json','closed_fifo_segments.csv']:
            os.link(temp/name,table_dir/name)
        os.link(temp/'stage008_equity_drawdown.png',plot_path)
    return dict(status='DERIVED_ARTIFACTS_ONLY_NO_FINANCIAL_REPLAY',G_classification=statuses['G']['performance_classification'],
        outputs=[str(plot_path),*[str(table_dir/name) for name in ['annual.csv','products.csv','comparison.json','closed_fifo_segments.csv']]],
        previous_artifact_files_preserved=len(old_artifacts),financial_replays=0)


def main():
    default=next((parent/'research/lines/futures_weekly_formal_no_half_r' for parent in Path(__file__).resolve().parents
        if (parent/'official_strategy_materials/CURRENT.json').is_file()),None)
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--line-dir',type=Path,default=default)
    parser.add_argument('--review-json',type=Path);args=parser.parse_args()
    if args.line_dir is None:raise ValueError('--line-dir required outside repository')
    print(json.dumps(build_artifacts(args.line_dir,args.review_json),ensure_ascii=False))

if __name__=='__main__':main()
