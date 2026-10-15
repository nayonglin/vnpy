"""Summarize one continuous frozen replay, without rerunning or changing strategy."""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    import numpy as np
    import pandas as pd
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    folder = args.result.resolve()
    metrics = json.loads((folder / 'metrics.json').read_text())
    daily = pd.read_csv(folder / 'daily.csv').sort_values('date')
    daily['date'] = pd.to_datetime(daily.date)
    capital = float(metrics['account_capital'])
    previous = capital
    annual = []
    for year, group in daily.groupby(daily.date.dt.year):
        equity = group.account_equity.astype(float)
        peak = np.maximum.accumulate(np.r_[previous, equity.to_numpy()])[1:]
        dd = (equity.to_numpy() / peak - 1) * 100
        annual.append({
            'year': int(year), 'first_date': group.date.min().date().isoformat(),
            'last_date': group.date.max().date().isoformat(), 'begin_equity': previous,
            'end_equity': float(equity.iloc[-1]), 'net_profit': float(equity.iloc[-1] - previous),
            'return_pct': float((equity.iloc[-1]/previous - 1)*100),
            'within_year_max_dd_pct': float(dd.min()), 'trade_fills': int(group.trade_count.sum()),
            'slippage': float(group.total_slippage.sum()), 'commission': float(group.commission.sum()),
            'nonzero_daily_win_rate_pct': float(group.loc[group.total_net_pnl.abs()>1e-12, 'total_net_pnl'].gt(0).mean()*100),
        })
        previous = float(equity.iloc[-1])
    pd.DataFrame(annual).to_csv(folder / 'annual_attribution.csv', index=False, encoding='utf-8-sig')
    equity = daily.account_equity.to_numpy(dtype=float)
    assert np.allclose(equity, capital + daily.total_net_pnl.cumsum(), rtol=0, atol=1e-6)
    trades = pd.read_csv(folder / 'trades.csv')
    assert len(trades) == int(daily.trade_count.sum())
    positions = pd.read_csv(folder / 'positions.csv')
    positions['date'] = pd.to_datetime(positions.date)
    last = positions[positions.date.eq(daily.date.max()) & positions.end_pos.ne(0)].copy()
    last.to_csv(folder / 'ending_open_positions.csv', index=False, encoding='utf-8-sig')
    audit = {
        'equity_equals_initial_plus_cumulative_net_pnl': True,
        'trade_rows_equal_daily_fills': True,
        'daily_rows': len(daily), 'first_date': daily.date.min().date().isoformat(),
        'last_date': daily.date.max().date().isoformat(), 'initial_capital': capital,
        'commission_total': float(daily.commission.sum()), 'slippage_total': float(daily.total_slippage.sum()),
        'opening_fills': int(trades.offset.isin(['Open', '开']).sum()),
        'closing_fills': int((~trades.offset.isin(['Open', '开'])).sum()),
        'ending_open_contracts': len(last),
        'win_rate_definition': 'Positive P&L days / nonzero P&L days; not trade win rate.',
        'annual_definition': 'Attribution of this single continuous equity path; no year-by-year capital or strategy reset.',
    }
    (folder / 'summary_checks.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2))
    dates = daily.date
    drawdown = (equity / np.maximum.accumulate(np.r_[capital, equity])[1:] - 1)*100
    with plt.rc_context({'font.family':'sans-serif','font.size':10,'axes.spines.top':False,'axes.spines.right':False}):
        fig, axes = plt.subplots(2, 1, figsize=(11, 6.8), sharex=True, gridspec_kw={'height_ratios':[2.2,1]})
        fig.suptitle('C9 / Stage847 official replay | Initial capital CNY 150,000', x=0.09, ha='left', fontsize=15, fontweight='bold')
        axes[0].plot(dates, equity, color='#146454', linewidth=1.6)
        axes[0].set_ylabel('Equity (CNY)')
        axes[0].yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v/1e6:g}m'))
        axes[0].grid(axis='y', color='#e5e7eb', linewidth=.7)
        axes[1].fill_between(dates, drawdown, 0, color='#b96638', alpha=.24)
        axes[1].plot(dates, drawdown, color='#a65128', linewidth=.8)
        axes[1].set_ylabel('Drawdown (%)')
        axes[1].grid(axis='y', color='#e5e7eb', linewidth=.7)
        fig.text(.09, .015, '2020-01-01 to 2026-10-14 | Frozen rules | Official slippage; commissions = 0\nHistorical replay only. Inherited intraday timing limitations are documented in the stage report.', fontsize=9, color='#555555')
        fig.tight_layout(rect=(0, .075, 1, .95))
        fig.savefig(folder / 'equity_drawdown.png', dpi=180)
        fig.savefig(folder / 'equity_drawdown.svg')
        plt.close(fig)
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == '__main__':
    main()
