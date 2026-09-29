"""Calendar-year slices of one continuous account, never yearly restarts."""
from __future__ import annotations

import math

import pandas as pd


def annual_statistics(daily: pd.DataFrame, round_trips: list[dict], *,
                      capital: float, annual_days: int = 252) -> list[dict]:
    dates = pd.DatetimeIndex(daily.index)
    if not dates.is_monotonic_increasing or dates.has_duplicates or dates.hasnans:
        raise ValueError('Annual statistics require sorted unique dates')
    if capital <= 0 or not math.isfinite(capital) or annual_days < 1:
        raise ValueError('Invalid annual statistics capital/days')
    if daily.empty:
        return []
    if not daily.equity.map(math.isfinite).all() or (daily.equity <= 0).any():
        raise ValueError('Annual statistics require positive finite equity')
    # Rebuild returns from equity, including the opening capital and year boundary.
    returns = daily.equity / daily.equity.shift(1, fill_value=capital) - 1
    opening = float(capital)
    rows = []
    for year in sorted(set(dates.year)):
        mask = dates.year == year
        part = daily.loc[mask]
        year_returns = returns.loc[mask]
        std = year_returns.std(ddof=0)
        closed = [trade for trade in round_trips if pd.Timestamp(trade['exit_date']).year == year]
        ending = float(part.equity.iloc[-1])
        rows.append(dict(year=int(year), start_date=str(dates[mask][0].date()),
            end_date=str(dates[mask][-1].date()), start_equity=opening, end_equity=ending,
            return_pct=(ending / opening - 1) * 100,
            max_drawdown_pct=float(((part.equity / part.equity.cummax().clip(lower=opening) - 1) * 100).min()),
            sharpe=float(year_returns.mean() / std * math.sqrt(annual_days)) if std > 0 else 0.,
            total_trade_count=int(part.trade_count.sum()), total_commission=float(part.commission.sum()),
            total_slippage=float(part.slippage.sum()), closed_round_trips=len(closed),
            win_rate_pct=100 * sum(t['net_pnl'] > 0 for t in closed) / len(closed) if closed else None,
            open_positions=int(part.position_count.iloc[-1]), trading_days=len(part)))
        opening = ending
    return rows
