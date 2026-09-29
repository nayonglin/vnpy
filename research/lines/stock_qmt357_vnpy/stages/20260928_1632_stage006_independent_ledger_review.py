"""Read-only independent audit of frozen 2020-2026 outputs, no engine imports."""
from pathlib import Path
import hashlib
import json
import math
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
PKG = ROOT / 'examples/stock_backtesting/qmt357'
OUT = PKG / 'outputs/fixed_2020_20260924_v2data'
SNAP = PKG / 'data/history_201910_20260924'
DATA = PKG / 'data/downloads/history_20191001_20260924'


def readj(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(a, b, tag, atol=1e-6):
    error = abs(float(a) - float(b))
    errors[tag] = max(errors.get(tag, 0), error)
    assert error <= atol, (tag, a, b, error)


errors = {}
manifest = readj(OUT / 'manifest.json')
summary = readj(OUT / 'summary.json')
snapshot = readj(SNAP / 'manifest.json')
download = readj(DATA / 'download_manifest.json')
freeze = readj(DATA / 'source_build_freeze.json')
code_ok = {name: sha(PKG / name) == val for name, val in manifest['code_sha256'].items()}
assert all(code_ok.values()), code_ok
assert all(freeze['code_sha256'][name] == download['code_sha256'][name] == manifest['code_sha256'][name]
           for name in freeze['code_sha256'])
assert sha(SNAP / 'panel.parquet') == snapshot['panel_sha256']
assert sha(DATA / 'source_panel.parquet') == snapshot['source_sha256'] == download['output_sha256']
assert sha(Path('/Users/bytedance/Desktop/person/qmt_stock/357.py')) == manifest['source_provenance']['source_sha256']
assert snapshot == manifest['snapshot']
assert download['state'] == 'complete' and download['complete_stocks'] == download['attempted_stocks'] == 420
assert download['failed_stocks'] == 0 and download['current_failures'] == []
assert readj(DATA / 'download_errors.json') == []
assert Path(manifest['vnpy_settings']).resolve() == PKG / 'runtime/.vntrader'
assert not manifest['database_opened']
assert not (PKG / 'runtime').is_symlink() and not (PKG / 'runtime/.vntrader').is_symlink()

panel = pd.read_parquet(SNAP / 'panel.parquet')
panel['date'] = pd.to_datetime(panel.date)
assert not panel.duplicated(['date', 'vt_symbol']).any()
source = pd.read_parquet(DATA / 'source_panel.parquet')
source['date'] = pd.to_datetime(source.date)
pd.testing.assert_frame_equal(panel.sort_values(['date', 'vt_symbol']).reset_index(drop=True),
                              source[panel.columns].sort_values(['date', 'vt_symbol']).reset_index(drop=True),
                              check_dtype=False)
calendar = pd.DatetimeIndex(panel.loc[panel.vt_symbol == '000300.SSE', 'date'].sort_values())
active = calendar[(calendar >= manifest['start']) & (calendar <= manifest['end'])]
assert len(active) == 1633 and len(calendar[calendar < manifest['start']]) == 61
daily = pd.read_csv(OUT / 'daily_equity.csv', parse_dates=['date']).set_index('date')
trades = pd.read_csv(OUT / 'trades.csv', parse_dates=['date', 'signal_date'])
orders = pd.read_csv(OUT / 'orders.csv', parse_dates=['signal_date'])
signals = pd.read_csv(OUT / 'signals.csv', parse_dates=['date']).set_index(['date', 'vt_symbol'])
gates = pd.read_csv(OUT / 'gates.csv', parse_dates=['date']).set_index('date')
roundtrips = pd.read_csv(OUT / 'round_trips.csv', parse_dates=['entry_date', 'exit_date'])
reported_coverage = pd.read_csv(OUT / 'position_coverage.csv', parse_dates=['date']).set_index(['date', 'vt_symbol'])
assert daily.index.equals(active)

cfg = manifest['settings']
cash = float(cfg['capital'])
holdings, last_prices = {}, {}
ledger, trips, actions, before_positions, after_positions = [], [], [], {}, {}
coverage_keys = []
max_budget_ratio, min_cash, max_count = 0, cash, 0
trade_dict = {dt: part for dt, part in trades.groupby('date', sort=False)}
max_next_session_delay = 0
order_fill_checks = 0
for dt, day in panel.groupby('date', sort=True):
    if dt < active[0]:
        last_prices.update(zip(day.vt_symbol, day.close))
        continue
    if dt > active[-1]:
        break
    rows = day.set_index('vt_symbol')
    before_positions[dt] = {sym: h['shares'] for sym, h in holdings.items()}
    previous_equity = ledger[-1]['equity'] if ledger else cfg['capital']
    for sym, h in holdings.items():
        if sym not in rows.index:
            continue
        row = rows.loc[sym]
        if row.cash_dividend or row.split_ratio != 1:
            credit = h['shares'] * row.cash_dividend
            old = h['shares']
            h['shares'] *= row.split_ratio
            close(h['shares'], round(h['shares']), 'integer_action_shares')
            h['shares'] = round(h['shares'])
            h['dividends'] += credit
            cash += credit
            last_prices[sym] = (last_prices[sym] - row.cash_dividend) / row.split_ratio
            actions.append(dict(date=str(dt.date()), vt_symbol=sym, old_shares=old,
                                new_shares=h['shares'], dividend=credit))
    buy_spend = fees = slippage = turnover = count = 0
    seen_buy = False
    for trade in trade_dict.get(dt, pd.DataFrame()).itertuples(index=False):
        sym = trade.vt_symbol
        row = rows.loc[sym]
        buy = trade.direction == 'buy'
        assert buy or not seen_buy, 'sells must execute before buys'
        seen_buy |= buy
        assert trade.signal_date < dt and row.volume > 0
        delay = calendar.get_loc(dt) - calendar.get_loc(trade.signal_date)
        max_next_session_delay = max(max_next_session_delay, delay)
        assert delay >= 1
        if buy:
            assert delay == 1, 'buys are one-shot next-session intents'
            assert not row.is_st and row.is_member and not sym.startswith(('300', '688'))
            assert row.open < row.limit_up - 1e-8
        else:
            assert row.open > row.limit_down + 1e-8
            # An older sell intent is allowed only if every intervening open
            # could not execute under the disclosed model.
            for pending_day in calendar[(calendar > trade.signal_date) & (calendar < dt)]:
                pending_rows = panel[(panel.date == pending_day) & (panel.vt_symbol == sym)]
                assert (pending_rows.empty or pending_rows.iloc[0].volume <= 0
                        or pending_rows.iloc[0].open <= pending_rows.iloc[0].limit_down + 1e-8)
        price = row.open + (cfg['slippage_per_share'] if buy else -cfg['slippage_per_share'])
        assert row.limit_down <= price <= row.limit_up and price > 0
        notional = trade.shares * price
        fee = max(cfg['minimum_commission'], notional * cfg['commission_rate'])
        if not buy:
            fee += notional * cfg['stamp_duty_rate']
        close(price, trade.price, 'fill_price')
        close(notional, trade.turnover, 'turnover')
        close(fee, trade.commission, 'trade_commission')
        close(trade.shares * cfg['slippage_per_share'], trade.slippage, 'trade_slippage')
        order = orders[(orders.vt_symbol == sym) & (orders.signal_date == trade.signal_date)
                       & (orders.direction == ('Long' if buy else 'Short'))]
        assert len(order) == 1 and order.iloc[0].filled_shares == trade.shares
        assert order.iloc[0].requested_shares >= trade.shares
        order_fill_checks += 1
        if buy:
            assert sym not in holdings and len(holdings) < cfg['max_positions']
            assert trade.shares > 0 and trade.shares % 100 == 0
            assert gates.loc[trade.signal_date, 'allowed']
            signal = signals.loc[(trade.signal_date, sym)]
            assert notional + fee <= signal.budget + 1e-6
            assert notional + fee <= cash * (1-cfg['cash_buffer']) + 1e-6
            cash -= notional + fee
            buy_spend += notional + fee
            holdings[sym] = dict(shares=trade.shares, entry_date=dt, entry_cost=notional+fee, dividends=0.)
        else:
            h = holdings.pop(sym)
            assert dt > h['entry_date'] and trade.shares == h['shares']
            cash += notional - fee
            trips.append(dict(vt_symbol=sym, entry_date=h['entry_date'], exit_date=dt,
                              entry_cost=h['entry_cost'], proceeds=notional-fee, dividends=h['dividends'],
                              net_pnl=notional-fee+h['dividends']-h['entry_cost']))
        close(cash, trade.cash_after, 'cash_after_trade')
        assert cash >= -1e-6
        min_cash, max_count = min(min_cash, cash), max(max_count, len(holdings))
        fees += fee
        slippage += trade.shares * cfg['slippage_per_share']
        turnover += notional
        count += 1
    assert buy_spend <= cfg['day_position_size'] * previous_equity + 1e-6
    max_budget_ratio = max(max_budget_ratio, buy_spend/previous_equity)
    last_prices.update(zip(day.vt_symbol, day.close))
    value = sum(h['shares']*last_prices[sym] for sym,h in holdings.items())
    for sym,h in holdings.items():
        assert sym in rows.index and rows.loc[sym].volume > 0, ('held missing/suspended', dt, sym)
        item = reported_coverage.loc[(dt,sym)]
        close(item.shares, h['shares'], 'coverage_shares')
        close(item.mark_price, last_prices[sym], 'coverage_mark')
        close(item.market_value, h['shares']*last_prices[sym], 'coverage_market_value')
        assert item.has_bar and not item.is_suspended and item.stale_sessions == 0 and item.stale_calendar_days == 0
        coverage_keys.append((dt,sym))
    after_positions[dt] = {sym: h['shares'] for sym,h in holdings.items()}
    computed = dict(date=dt, cash=cash, market_value=value, equity=cash+value, position_count=len(holdings),
                    trade_count=count, commission=fees, slippage=slippage, turnover=turnover)
    for key,val in computed.items():
        if key != 'date':
            close(val, daily.loc[dt,key], 'daily_'+key)
    ledger.append(computed)

assert len(coverage_keys) == len(reported_coverage) == 2032
assert len(trips) == len(roundtrips) == 213
computed_trips = pd.DataFrame(trips)
for i,item in computed_trips.iterrows():
    actual = roundtrips.iloc[i]
    for key in ('vt_symbol','entry_date','exit_date'):
        assert item[key] == actual[key]
    for key in ('entry_cost','proceeds','dividends','net_pnl'):
        close(item[key], actual[key], 'roundtrip_'+key)

reconstructed = pd.DataFrame(ledger).set_index('date')
equities = np.r_[cfg['capital'], reconstructed.equity.to_numpy()]
returns = equities[1:]/equities[:-1]-1
dd = equities[1:]/np.maximum.accumulate(equities)[1:]-1
recomputed_summary = dict(end_equity=equities[-1], total_return_pct=(equities[-1]/equities[0]-1)*100,
    max_drawdown_pct=dd.min()*100, sharpe=returns.mean()/returns.std(ddof=0)*math.sqrt(cfg['annual_days']),
    total_slippage=reconstructed.slippage.sum(), total_commission=reconstructed.commission.sum(),
    total_trade_count=int(reconstructed.trade_count.sum()), closed_round_trips=len(trips),
    win_rate_pct=(computed_trips.net_pnl>0).mean()*100, open_positions=len(holdings), trading_days=len(ledger))
for key,val in recomputed_summary.items():
    close(val,summary[key], 'summary_'+key)
close(computed_trips.net_pnl.sum(), equities[-1]-cfg['capital'], 'total_realized_pnl_vs_equity')
close(np.max(abs(returns-daily['return'])),0,'daily_returns')
close(np.max(abs(dd*100-daily.drawdown_pct)),0,'daily_drawdown')
annual = pd.read_csv(OUT / 'annual_summary.csv').set_index('year')
opening = cfg['capital']
for year,part in reconstructed.groupby(reconstructed.index.year):
    eq = np.r_[opening, part.equity.to_numpy()]
    r = eq[1:]/eq[:-1]-1
    subset = computed_trips[computed_trips.exit_date.dt.year == year]
    vals = dict(start_equity=opening,end_equity=eq[-1],return_pct=(eq[-1]/opening-1)*100,
        max_drawdown_pct=(eq[1:]/np.maximum.accumulate(eq)[1:]-1).min()*100,
        sharpe=r.mean()/r.std(ddof=0)*math.sqrt(cfg['annual_days']), total_trade_count=part.trade_count.sum(),
        total_commission=part.commission.sum(), total_slippage=part.slippage.sum(),
        closed_round_trips=len(subset), win_rate_pct=(subset.net_pnl>0).mean()*100,
        open_positions=part.position_count.iloc[-1], trading_days=len(part))
    for key,val in vals.items():
        close(val,annual.loc[year,key],'annual_'+key)
    opening = eq[-1]
for key in ('total_trade_count','total_commission','total_slippage','closed_round_trips','trading_days'):
    close(annual[key].sum(),summary[key],'annual_sum_'+key)
close(np.prod(1+annual.return_pct/100)-1, summary['total_return_pct']/100,'annual_compound_return')

stock = panel[panel.vt_symbol != '000300.SSE'].sort_values(['vt_symbol','date']).copy()
previous_factor = stock.groupby('vt_symbol').adj_factor.shift()
gap = stock[previous_factor.notna() & ~np.isclose(stock.adj_factor,previous_factor,rtol=1e-10,atol=0)
            & (stock.cash_dividend==0) & (stock.split_ratio==1)]
assert len(gap) == 24
gap_exposure = []
for item in gap.itertuples(index=False):
    gap_exposure.append(dict(date=str(item.date.date()), vt_symbol=item.vt_symbol,
        beginning_shares=before_positions.get(item.date,{}).get(item.vt_symbol,0),
        ending_shares=after_positions.get(item.date,{}).get(item.vt_symbol,0)))
assert all(x['beginning_shares']==0 and x['ending_shares']==0 for x in gap_exposure)
missing = pd.read_parquet(DATA / 'missing_member_bars.parquet')
missing['date'] = pd.to_datetime(missing.date)
assert len(missing) == 37
missing_exposure = []
observed_pairs = set(panel.set_index(['date','vt_symbol']).index)
for item in missing.itertuples(index=False):
    assert (item.date,item.vt_symbol) not in observed_pairs
    missing_exposure.append(dict(date=str(item.date.date()),vt_symbol=item.vt_symbol,
        beginning_shares=before_positions.get(item.date,{}).get(item.vt_symbol,0),
        ending_shares=after_positions.get(item.date,{}).get(item.vt_symbol,0)))
assert all(x['beginning_shares']==0 and x['ending_shares']==0 for x in missing_exposure)
# Independently reconstruct monthly universe flags and missing member rows.
components = pd.read_parquet(DATA / 'historical_components.parquet')
components['snapshot_date'] = pd.to_datetime(components.snapshot_date)
components['updateDate'] = pd.to_datetime(components.updateDate)
assert (components.updateDate <= components.snapshot_date).all()
assert (components.groupby('snapshot_date').code.nunique() == 300).all()
snapshot_dates = sorted(components.snapshot_date.unique())
assert len(snapshot_dates) == 85
members_by_snapshot = {dt: {code[3:]+('.SSE' if code[:2]=='sh' else '.SZSE')
    for code in group.code if not code[3:].startswith(('300','688'))}
    for dt,group in components.groupby('snapshot_date')}
expected_pairs = set()
for dt in calendar:
    latest = max(s for s in snapshot_dates if s < dt)
    expected_pairs.update((dt,sym) for sym in members_by_snapshot[latest])
assert len(expected_pairs) == 440341
independent_missing = expected_pairs-observed_pairs
assert independent_missing == set(missing.set_index(['date','vt_symbol']).index)
actual_member_pairs = set(stock.loc[stock.is_member,['date','vt_symbol']].itertuples(index=False,name=None))
assert actual_member_pairs == expected_pairs & observed_pairs
halt_audit = []
for sym,halt_start in [('600837.SSE','2025-02-06'),('601989.SSE','2025-08-13')]:
    halt_start = pd.Timestamp(halt_start)
    relevant = stock[(stock.vt_symbol==sym) & (stock.date>=halt_start)]
    assert (relevant.volume==0).all()
    relevant_dates = active[active >= halt_start]
    exposed = [(str(dt.date()),before_positions[dt].get(sym,0),after_positions[dt].get(sym,0))
               for dt in relevant_dates if before_positions[dt].get(sym,0) or after_positions[dt].get(sym,0)]
    assert not exposed
    sym_trips = computed_trips[computed_trips.vt_symbol==sym]
    halt_audit.append(dict(vt_symbol=sym,first_halted_day=str(halt_start.date()),
        zero_volume_bars=len(relevant),ending_bar=str(relevant.date.max().date()),
        last_position_exit=str(sym_trips.exit_date.max().date()) if len(sym_trips) else None,
        held_from_halt_onward=exposed))
limit_violations = stock[(stock.high > stock.limit_up+1e-8) | (stock.low < stock.limit_down-1e-8)]
assert len(limit_violations)==41 and limit_violations.is_member.sum()==0
assert int((stock.volume==0).sum())==1686
index_prices=panel[panel.vt_symbol=='000300.SSE'].set_index('date').close
for dt in active:
    hist=index_prices.loc[:dt]
    gate=bool(hist.iloc[-1]>=hist.iloc[-2] and hist.iloc[-5:].mean()>hist.iloc[-10:].mean()>hist.iloc[-20:].mean())
    assert gate==gates.loc[dt,'allowed'],('market gate',dt)
influenced = []
for item in gap.itertuples(index=False):
    history = stock[stock.vt_symbol == item.vt_symbol].date.tolist()
    where = history.index(item.date)
    potential_dates = set(history[where:where+59])
    matched = trades[(trades.vt_symbol == item.vt_symbol) & (trades.direction=='buy') & trades.signal_date.isin(potential_dates)]
    influenced.extend(dict(gap_date=str(item.date.date()),vt_symbol=item.vt_symbol,
        signal_date=str(t.signal_date.date()),buy_date=str(t.date.date())) for t in matched.itertuples(index=False))

result = dict(status='PASS_ENGINEERING_LEDGER_NOT_ALPHA_VALIDATION', code_hashes_checked=len(code_ok),
    snapshot_and_source_hashes_match=True, downloader_freeze_matches=True, raw_union_complete=420,
    max_errors=errors, summary=recomputed_summary, minimum_cash=min_cash, max_positions=max_count,
    max_daily_buy_budget_pct=max_budget_ratio*100, order_fill_checks=order_fill_checks,
    max_execution_delay_sessions=max_next_session_delay, held_stock_days=len(coverage_keys),
    held_action_events=actions, realized_winners=int((computed_trips.net_pnl>0).sum()),
    gap_exposure=gap_exposure, missing_exposure=missing_exposure,
    historical_member_pairs=len(expected_pairs),independent_missing_member_pairs=len(independent_missing),
    merger_halt_exposure=halt_audit,derived_limit_violations=len(limit_violations),
    buy_signals_with_gap_in_60bar_window=influenced,
    no_vnpy_imported=not any(x.startswith('vnpy') for x in sys.modules),
    no_futures_strategy_imported=not any(x.startswith(('qmt_roll','qmt_range','run_qmt_roll','examples.futures')) for x in sys.modules))
serialized=json.dumps(result,ensure_ascii=False,indent=2,default=lambda x: x.item() if hasattr(x,'item') else str(x))
Path(__file__).with_suffix('.json').write_text(serialized,encoding='utf-8')
print(serialized)
