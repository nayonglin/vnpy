"""Independent read-only reconstruction of the fixed stock run; no engine imports."""
from collections import defaultdict
from pathlib import Path
import hashlib
import json
import math
import sys
import tarfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
PKG = ROOT / 'examples/stock_backtesting/qmt357_commit4ac255e'
BASE = ROOT / 'examples/stock_backtesting/qmt357'
OUT = PKG / 'outputs/fixed_2020_20260928_commit4ac255e_repaired_v1'
SNAP = PKG / 'data/snapshots/history_201910_20260928_repaired_v1'
REPAIR = PKG / 'data/repairs/stage010_repaired_v1'
OLD_SOURCE = BASE / 'data/downloads/history_20191001_20260928/source_panel.parquet'
ERR = defaultdict(float)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def eq(actual, expected, tag, atol=1e-6):
    error = abs(float(actual) - float(expected))
    ERR[tag] = max(ERR[tag], error)
    assert error <= atol, (tag, actual, expected, error)


def readj(path):
    return json.loads(path.read_text())


manifest = readj(OUT / 'manifest.json')
identity = readj(OUT / 'run_identity.json')
snapshot = readj(SNAP / 'manifest.json')
spec = readj(REPAIR / 'repair_specification.json')
build = readj(REPAIR / 'build_result.json')
summary = readj(OUT / 'summary.json')
cfg = manifest['settings']
assert manifest['status'] == 'COMPLETE' and manifest['complete_period_result']
assert identity['status'] == 'RUNNING' and not identity['complete_period_result']
for key in identity:
    if key not in ('status', 'complete_period_result'):
        assert identity[key] == manifest[key], key
assert sha(OUT / 'run_identity.json') == manifest['run_identity_sha256']
assert sha(OUT / 'code_snapshot.tar.gz') == manifest['code_archive_sha256']
assert sha(SNAP / 'panel.parquet') == snapshot['panel_sha256'] == manifest['snapshot']['panel_sha256']
assert sha(REPAIR / 'source_panel.parquet') == snapshot['source_sha256'] == build['source_sha256']
assert sha(REPAIR / 'repair_specification.json') == snapshot['source_metadata']['repair_specification_sha256']
assert sha(OLD_SOURCE) == spec['source_sha256'] == snapshot['source_metadata']['source_parent_sha256']
assert len(spec['operations']) == build['operations'] == 19
assert sha(Path('/tmp/qmt-commit-4ac255e.WqwflV/震荡股高卖低买策略.py')) == manifest['source_provenance']['source_sha256']
for name, value in manifest['code_sha256'].items():
    assert sha(PKG / name) == value, name
for name, value in manifest['baseline_code_sha256'].items():
    assert sha(BASE / name) == value, name
with tarfile.open(OUT / 'code_snapshot.tar.gz', 'r:gz') as archive:
    archived = {m.name: hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                for m in archive.getmembers() if m.isfile()}
    for name, value in manifest['code_sha256'].items():
        assert archived['qmt357_commit4ac255e/'+name] == value, name
    for name, value in manifest['baseline_code_sha256'].items():
        assert archived['qmt357/'+name] == value, name

old = pd.read_parquet(OLD_SOURCE)
source = pd.read_parquet(REPAIR / 'source_panel.parquet')
panel = pd.read_parquet(SNAP / 'panel.parquet')
for frame in (old, source, panel):
    frame['date'] = pd.to_datetime(frame.date)
    assert not frame.duplicated(['date', 'vt_symbol']).any()
keys = ['date', 'vt_symbol']
old = old.sort_values(keys).reset_index(drop=True)
source = source.sort_values(keys).reset_index(drop=True)
panel = panel.sort_values(keys).reset_index(drop=True)
assert len(old) == len(source) == len(panel) == build['rows'] == 692961
pd.testing.assert_frame_equal(source, panel, check_dtype=False)
for field in ('date', 'vt_symbol', 'open', 'high', 'low', 'close', 'volume',
              'limit_up', 'limit_down', 'is_st', 'is_member'):
    pd.testing.assert_series_equal(old[field], source[field], check_dtype=False)
changes = pd.read_parquet(REPAIR / 'field_changes.parquet')
assert len(changes) == build['changed_fields'] == 9417
assert changes.field.value_counts().to_dict() == build['changes_by_field']
indexed_old, indexed_new = old.set_index(keys), source.set_index(keys)
for field in ('adj_factor', 'cash_dividend', 'split_ratio'):
    unequal = ~np.isclose(indexed_old[field], indexed_new[field], rtol=0, atol=1e-12)
    expected = set(indexed_old.index[unequal].tolist())
    actual = set(changes.loc[changes.field == field, keys].itertuples(index=False, name=None))
    actual = {(pd.Timestamp(day), sym) for day, sym in actual}
    assert expected == actual, (field, len(expected), len(actual))
gaps = pd.read_parquet(REPAIR / 'remaining_factor_gaps.parquet')
assert len(gaps) == build['remaining_factor_gaps'] == 15

calendar = pd.DatetimeIndex(panel.loc[panel.vt_symbol == '000300.SSE', 'date'])
active = calendar[(calendar >= manifest['start']) & (calendar <= manifest['end'])]
daily = pd.read_csv(OUT / 'daily_equity.csv', parse_dates=['date']).set_index('date')
trades = pd.read_csv(OUT / 'trades.csv', parse_dates=['date', 'signal_date'])
orders = pd.read_csv(OUT / 'orders.csv', parse_dates=['signal_date'])
signals = pd.read_csv(OUT / 'signals.csv', parse_dates=['date']).set_index(['date', 'vt_symbol'])
gates = pd.read_csv(OUT / 'gates.csv', parse_dates=['date']).set_index('date')
reported_trips = pd.read_csv(OUT / 'round_trips.csv', parse_dates=['entry_date', 'exit_date'])
coverage = pd.read_csv(OUT / 'position_coverage.csv', parse_dates=['date']).set_index(['date', 'vt_symbol'])
trails = pd.read_csv(OUT / 'trailing_stops.csv', parse_dates=['date'])
assert daily.index.equals(active) and len(active) == 1634
assert not trails.duplicated(['date', 'vt_symbol']).any()
trails_by_day = {day: part for day, part in trails.groupby('date', sort=False)}
trades_by_day = {day: part for day, part in trades.groupby('date', sort=False)}
gap_keys = {(pd.Timestamp(row.date), row.vt_symbol) for row in gaps.itertuples(index=False)}
unsupported = {(pd.Timestamp(row['date']), row['vt_symbol']) for row in snapshot['source_metadata']['unsupported_corporate_actions']}
cash = cfg['capital']
holdings = {}
last_price = {}
ledger, trips, held_actions, gap_exposure, unsupported_exposure = [], [], [], [], []
held_keys = set()
min_cash, max_count, max_buy_ratio, max_delay = cash, 0, 0., 0
special_lowerings = 0
trail_checks = 0
before = {}
for day_date, bars in panel.groupby('date', sort=True):
    rows = bars.set_index('vt_symbol')
    if day_date < active[0]:
        last_price.update(zip(bars.vt_symbol, bars.close))
        continue
    if day_date > active[-1]:
        break
    before[day_date] = {sym: h['shares'] for sym, h in holdings.items()}
    previous_equity = ledger[-1]['equity'] if ledger else cfg['capital']
    for sym, h in holdings.items():
        if sym not in rows.index:
            continue
        row = rows.loc[sym]
        dividend, split = float(row.cash_dividend), float(row.split_ratio)
        if dividend or split != 1:
            prior = h['shares']
            credit = prior * dividend
            shares = prior * split
            eq(shares, round(shares), 'action_integer_shares')
            h['shares'] = int(round(shares))
            h['dividends'] += credit
            cash += credit
            h['buy'] = (h['buy'] - dividend) / split
            h['peak'] = (h['peak'] - dividend) / split
            h['stop'] = (h['stop'] - dividend) / split
            h['take'] = (h['take'] - dividend) / split
            last_price[sym] = (last_price[sym] - dividend) / split
            held_actions.append(dict(date=str(day_date.date()), vt_symbol=sym, old_shares=prior,
                                     new_shares=h['shares'], credit=credit))
    for day, sym in gap_keys:
        if day == day_date and sym in holdings:
            gap_exposure.append(dict(date=str(day.date()), vt_symbol=sym, shares=holdings[sym]['shares']))
    for day, sym in unsupported:
        if day == day_date and sym in holdings:
            unsupported_exposure.append(dict(date=str(day.date()), vt_symbol=sym, shares=holdings[sym]['shares']))
    buy_spend = fee_sum = slip_sum = turnover = trade_count = 0.
    seen_buy = False
    for trade in trades_by_day.get(day_date, pd.DataFrame()).itertuples(index=False):
        sym = trade.vt_symbol
        assert sym in rows.index
        row = rows.loc[sym]
        is_buy = trade.direction == 'buy'
        assert is_buy or not seen_buy
        seen_buy |= is_buy
        assert trade.signal_date < day_date and row.volume > 0
        delay = calendar.get_loc(day_date) - calendar.get_loc(trade.signal_date)
        max_delay = max(max_delay, delay)
        if is_buy:
            assert delay == 1 and not row.is_st and row.is_member
            assert not sym.startswith(('300', '688')) and row.open < row.limit_up - 1e-8
        else:
            assert row.open > row.limit_down + 1e-8
            for pending in calendar[(calendar > trade.signal_date) & (calendar < day_date)]:
                p = panel[(panel.date == pending) & (panel.vt_symbol == sym)]
                assert p.empty or p.iloc[0].volume <= 0 or p.iloc[0].open <= p.iloc[0].limit_down + 1e-8
        fill = float(row.open) + (cfg['slippage_per_share'] if is_buy else -cfg['slippage_per_share'])
        assert 0 < fill <= row.limit_up and fill >= row.limit_down
        notional = trade.shares * fill
        fee = max(cfg['minimum_commission'], notional * cfg['commission_rate'])
        if not is_buy:
            fee += notional * cfg['stamp_duty_rate']
        eq(fill, trade.price, 'trade_price')
        eq(notional, trade.turnover, 'trade_turnover')
        eq(fee, trade.commission, 'trade_fee')
        eq(trade.shares * cfg['slippage_per_share'], trade.slippage, 'trade_slippage')
        order = orders[(orders.vt_symbol == sym) & (orders.signal_date == trade.signal_date)
                       & (orders.direction == ('Long' if is_buy else 'Short'))]
        assert len(order) == 1 and order.iloc[0].filled_shares == trade.shares
        assert order.iloc[0].requested_shares >= trade.shares
        if is_buy:
            assert sym not in holdings and len(holdings) < cfg['max_positions']
            assert trade.shares > 0 and trade.shares % 100 == 0
            assert gates.loc[trade.signal_date, 'allowed']
            signal = signals.loc[(trade.signal_date, sym)]
            assert notional + fee <= signal.budget + 1e-6
            assert notional + fee <= cash * (1 - cfg['cash_buffer']) + 1e-6
            cash -= notional + fee
            buy_spend += notional + fee
            holdings[sym] = dict(shares=trade.shares, entry_date=day_date, entry_cost=notional+fee,
                                 dividends=0., buy=fill, peak=fill, stop=fill*(1-cfg['stop_loss_pct']),
                                 take=fill*(1+cfg['stop_profit_pct']))
        else:
            h = holdings.pop(sym)
            assert day_date > h['entry_date'] and trade.shares == h['shares']
            cash += notional - fee
            trips.append(dict(vt_symbol=sym, entry_date=h['entry_date'], exit_date=day_date,
                              entry_cost=h['entry_cost'], proceeds=notional-fee, dividends=h['dividends'],
                              net_pnl=notional-fee+h['dividends']-h['entry_cost']))
        eq(cash, trade.cash_after, 'cash_after_trade')
        assert cash >= -1e-6
        min_cash = min(min_cash, cash)
        max_count = max(max_count, len(holdings))
        fee_sum += fee
        slip_sum += trade.shares * cfg['slippage_per_share']
        turnover += notional
        trade_count += 1
    assert buy_spend <= cfg['day_position_size'] * previous_equity + 1e-6
    max_buy_ratio = max(max_buy_ratio, buy_spend / previous_equity)
    last_price.update(zip(bars.vt_symbol, bars.close))
    day_trails = trails_by_day.get(day_date, pd.DataFrame())
    for trail in day_trails.itertuples(index=False):
        h = holdings[trail.vt_symbol]
        row = rows.loc[trail.vt_symbol]
        observed = float(row.close)
        eq(observed, trail.observed_close, 'trail_observed_close')
        eq(h['buy'], trail.buy_price, 'trail_buy_price')
        eq(h['stop'], trail.old_stop, 'trail_old_stop')
        peak = max(h['peak'], observed)
        eq(peak, trail.peak, 'trail_peak_close')
        h['peak'] = peak
        next_stop = h['stop']
        if observed > h['buy']:
            gain = (peak-h['buy'])/h['buy']
            tier = .15 if gain >= .40 else .10 if gain >= .30 else .06 if gain >= .20 else .03 if gain >= .10 else 0.
            next_stop = max(next_stop, h['buy']*(1+tier))
        eq(next_stop, trail.new_stop, 'trail_new_stop')
        h['stop'] = next_stop
        trail_checks += 1
        # The source takes a stop snapshot for today's exit check before this
        # protection; a later check can therefore see a lower stored stop.
        profit = (observed-h['buy'])/h['buy']
        protected = next_stop
        if observed >= row.limit_up*.995 and profit >= cfg['stop_profit_pct']*.8:
            protected = max(h['buy']*1.01, observed*.97)
        if observed <= row.limit_down*1.005 and profit > 0:
            protected = h['buy']
        if protected < next_stop - 1e-9:
            special_lowerings += 1
        h['stop'] = protected
    value = 0.
    for sym, h in holdings.items():
        assert sym in rows.index and rows.loc[sym].volume > 0
        value += h['shares'] * last_price[sym]
        item = coverage.loc[(day_date, sym)]
        eq(item.shares, h['shares'], 'coverage_shares')
        eq(item.mark_price, last_price[sym], 'coverage_mark')
        eq(item.market_value, h['shares']*last_price[sym], 'coverage_value')
        assert item.has_bar and not item.is_suspended and item.stale_sessions == 0
        held_keys.add((day_date, sym))
    values = dict(cash=cash, market_value=value, equity=cash+value,
                  balance=cash+value, net_pnl=cash+value-previous_equity,
                  position_count=len(holdings), stale_market_value=0.,
                  trade_count=trade_count, commission=fee_sum, slippage=slip_sum, turnover=turnover)
    for field, value in values.items():
        eq(value, daily.loc[day_date, field], 'daily_'+field)
    ledger.append(dict(date=day_date, **values))

assert len(held_keys) == len(coverage)
assert len(trades) == 452 and len(trips) == len(reported_trips) == 226
assert len(trails) == trail_checks
assert not gap_exposure and not unsupported_exposure
assert not holdings and max_count <= 3
reconstructed = pd.DataFrame(ledger).set_index('date')
for trip, reported in zip(trips, reported_trips.itertuples(index=False), strict=True):
    assert (trip['vt_symbol'], trip['entry_date'], trip['exit_date']) == (
        reported.vt_symbol, reported.entry_date, reported.exit_date)
    for field in ('entry_cost', 'proceeds', 'dividends', 'net_pnl'):
        eq(trip[field], getattr(reported, field), 'trip_'+field)
trips_frame = pd.DataFrame(trips)
equity = np.r_[cfg['capital'], reconstructed.equity.to_numpy()]
returns = equity[1:]/equity[:-1]-1
drawdowns = equity[1:]/np.maximum.accumulate(equity)[1:]-1
metrics = dict(end_equity=equity[-1], total_return_pct=(equity[-1]/equity[0]-1)*100,
               max_drawdown_pct=drawdowns.min()*100,
               sharpe=returns.mean()/returns.std(ddof=0)*math.sqrt(cfg['annual_days']),
               total_slippage=reconstructed.slippage.sum(), total_commission=reconstructed.commission.sum(),
               total_trade_count=int(reconstructed.trade_count.sum()), closed_round_trips=len(trips),
               win_rate_pct=(trips_frame.net_pnl>0).mean()*100, open_positions=len(holdings),
               trading_days=len(reconstructed))
for field, value in metrics.items():
    eq(value, summary[field], 'summary_'+field)
eq(trips_frame.net_pnl.sum(), equity[-1]-cfg['capital'], 'realized_vs_equity')
eq(np.max(abs(returns-daily['return'])), 0., 'daily_return')
eq(np.max(abs(drawdowns*100-daily.drawdown_pct)), 0., 'daily_drawdown')
annual = pd.read_csv(OUT/'annual_summary.csv').set_index('year')
opening = cfg['capital']
for year, part in reconstructed.groupby(reconstructed.index.year):
    annual_equity = np.r_[opening, part.equity.to_numpy()]
    annual_returns = annual_equity[1:]/annual_equity[:-1]-1
    subset = trips_frame[trips_frame.exit_date.dt.year == year]
    vals = dict(start_equity=opening, end_equity=annual_equity[-1],
        return_pct=(annual_equity[-1]/opening-1)*100,
        max_drawdown_pct=(annual_equity[1:]/np.maximum.accumulate(annual_equity)[1:]-1).min()*100,
        sharpe=annual_returns.mean()/annual_returns.std(ddof=0)*math.sqrt(cfg['annual_days']),
        total_trade_count=part.trade_count.sum(), total_commission=part.commission.sum(),
        total_slippage=part.slippage.sum(), closed_round_trips=len(subset),
        win_rate_pct=(subset.net_pnl>0).mean()*100,
        open_positions=part.position_count.iloc[-1], trading_days=len(part))
    for field, value in vals.items():
        eq(value, annual.loc[year, field], 'annual_'+field)
    opening = annual_equity[-1]
for field in ('total_trade_count','total_commission','total_slippage','closed_round_trips','trading_days'):
    eq(annual[field].sum(), summary[field], 'annual_sum_'+field)
eq(np.prod(1+annual.return_pct/100)-1, summary['total_return_pct']/100, 'annual_compound')

# Residuals are a caution inventory, not an inference of any cash/share event.
cases = pd.read_parquet(ROOT/'research/lines/stock_qmt357_vnpy/stages/20260928_2127_stage010_factor_pattern_audit_event_checks.parquet')
cases['date'] = pd.to_datetime(cases.date)
major = pd.read_parquet(ROOT/'research/lines/stock_qmt357_vnpy/stages/20260928_2127_stage010_factor_pattern_audit_major_reference_cases.parquet')
major_keys = {(pd.Timestamp(r.date),r.vt_symbol) for r in major.itertuples(index=False)}
minor = cases[cases.classification == 'explicit_cash_split_reference_incompatible']
minor = minor[[((pd.Timestamp(r.date),r.vt_symbol) not in major_keys) for r in minor.itertuples(index=False)]]
assert len(minor) == 176
minor_intersections = []
for row in minor.itertuples(index=False):
    pre_action = before.get(row.date,{}).get(row.vt_symbol,0)
    same_day_position = (row.date,row.vt_symbol) in held_keys
    if pre_action or same_day_position:
        day_buys = trades[(trades.date == row.date) & (trades.vt_symbol == row.vt_symbol)
                          & (trades.direction == 'buy')]
        minor_intersections.append(dict(date=str(row.date.date()), vt_symbol=row.vt_symbol,
            residual=float(row.cash_split_reference_residual),
            pre_action_holding_shares=pre_action, actual_dividend_entitlement=bool(pre_action),
            same_day_new_position_shares=int(day_buys.shares.sum()),
            end_of_day_position=bool(same_day_position)))
result = dict(status='PASS_ENGINEERING_LEDGER_WITH_DATA_LIMITS', summary=metrics,
    max_absolute_errors=dict(ERR), min_cash=min_cash, max_positions=max_count,
    max_daily_buy_budget_pct=max_buy_ratio*100, max_fill_delay_sessions=max_delay,
    held_stock_days=len(held_keys), held_actions=held_actions,
    trailing_rows_checked=trail_checks, special_limit_lowerings=special_lowerings,
    unmodeled_factor_direct_exposure=gap_exposure,
    unsupported_600515_direct_exposure=unsupported_exposure,
    minor_residual_inventory_rows=len(minor), minor_residual_held_intersections=minor_intersections,
    original_failure_000001=dict(shares_on_2020_12_31=before[pd.Timestamp('2020-12-31')]['000001.SZSE'],
        mark_2020_12_30=float(coverage.loc[(pd.Timestamp('2020-12-30'),'000001.SZSE'),'mark_price']),
        mark_2020_12_31=float(coverage.loc[(pd.Timestamp('2020-12-31'),'000001.SZSE'),'mark_price']),
        stop_2020_12_31=float(trails.loc[(trails.date == pd.Timestamp('2020-12-31'))
            & (trails.vt_symbol == '000001.SZSE'),'new_stop'].iloc[0])),
    no_engine_or_vnpy_imported=not any(x.startswith(('vnpy','examples.stock_backtesting')) for x in sys.modules))
Path(__file__).with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str))
print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
