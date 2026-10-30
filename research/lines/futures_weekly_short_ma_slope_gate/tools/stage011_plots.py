"""Pure Stage011 renderer: prior and uniform OI base risks, both with top-ups.

The caller admits source hashes and exchange-calendar truth and saves figures.
This module only checks the complete frozen reporting projection and renders it;
it never reads files, downloads data, or runs the financial engine.
"""
import math
import numpy as np
import pandas as pd
from matplotlib import dates as mdates
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

STARTS = tuple(f'{year}-{month:02d}-01' for year in range(2015, 2027)
               for month in (1, 6) if (year, month) <= (2026, 1))
CUTOFF = '2026-10-29'
INITIAL_TRADING_CAPITAL = 150000.
EXTERNAL_FUNDING_LIMIT = 150000.
TOTAL_BUDGET = 300000.
EXPECTED_DAILY_POINTS = 141996
_COUNTS = (2871, 2773, 2627, 2527, 2383, 2286, 2139, 2040, 1896,
           1797, 1652, 1555, 1409, 1312, 1166, 1070, 924, 826, 682,
           584, 440, 343, 197)
_ACTUAL_STARTS = ('2015-01-05', '2015-06-01', '2016-01-04', '2016-06-01',
                  '2017-01-03', '2017-06-01', '2018-01-02', '2018-06-01',
                  '2019-01-02', '2019-06-03', '2020-01-02', '2020-06-01',
                  '2021-01-04', '2021-06-01', '2022-01-04', '2022-06-01',
                  '2023-01-03', '2023-06-01', '2024-01-02', '2024-06-03',
                  '2025-01-02', '2025-06-03', '2026-01-05')
WINDOW_SCOPE = dict(zip(STARTS, zip(_ACTUAL_STARTS, _COUNTS)))
VARIANTS = ('A_old', 'A_new', 'C_old', 'C_new')
FIGURE_NAMES = ('01_account_nav_drawdown_2015.png',
                '02_january_account_nav.png', '03_june_account_nav.png',
                '04_real_pnl_wealth_deltas.png',
                '05_risk_funding_and_pnl_overview.png')
COLORS = {'A_old': '#7f8a96', 'A_new': '#2168ad',
          'C_old': '#cb941b', 'C_new': '#b5224a'}
LABELS = {'A_old': 'A prior OI base risks + deposits',
          'A_new': 'A uniform 1.8% base + deposits',
          'C_old': 'C prior OI base risks + deposits',
          'C_new': 'C uniform 1.8% base + deposits'}
SHORT_LABELS = {'A_old': 'A prior', 'A_new': 'A uniform',
                'C_old': 'C prior', 'C_new': 'C uniform'}
FOOTER = ('Account NAV = E / 150k: external reserve excluded; deposits INCLUDED; E growth/DD/Sharpe include cashflows.\n'
          'Economic comparison: W = E + R = 300k + real trading PnL; W / 300k excludes internal transfers from returns.\n'
          'Only OI base risks 6% / 6% / 2.5% -> 1.8%; OI x2, enhanced x1.5 and low-volume x0.5 retained.')
STRATEGY_SCOPE = ('A: original 19, no added price gate | C: short bottom 20% veto only | '
                  'add-on / long-price / MA-slope gates OFF')
SUMMARY_FIELDS = {
    'start', 'variant', 'arm', 'version', 'funding_mode', 'actual_start', 'actual_end',
    'trading_days', 'observation_only', 'initial_trading_capital',
    'account_end_equity', 'account_growth_pct', 'balance_max_dd_pct',
    'balance_sharpe', 'balance_returns_defined', 'real_trading_net_pnl',
    'total_transferred', 'off_account_reserve_end', 'total_slippage',
    'total_commission', 'modeled_fill_count', 'transfer_event_days',
    'transfer_event_count', 'nonpositive_trading_equity_days',
    'wealth_end_equity', 'wealth_return_pct', 'wealth_max_dd_pct', 'wealth_sharpe',
    'wealth_returns_defined', 'nonpositive_total_equity_days',
    'reserve_exhausted', 'exhaustion_date', 'trading_margin_peak_pct',
    'trading_margin_over100_days'}
PAIR_FIELDS = {
    'start', 'arm', 'cohort', 'observation_only', 'delta_account_growth_pp',
    'delta_balance_max_dd_pp', 'delta_balance_sharpe',
    'delta_real_trading_net_pnl', 'delta_account_end_equity', 'delta_deposits',
    'delta_wealth_return_pp', 'delta_wealth_max_dd_pp', 'delta_wealth_sharpe',
    'real_pnl_gate', 'wealth_dd_gate', 'wealth_sharpe_gate', 'three_gate_pass'}
DAILY_FIELDS = {
    'start', 'variant', 'date', 'raw_account_equity', 'net_pnl',
    'trading_account_equity', 'reserve_balance', 'cumulative_transfer',
    'transfer_amount', 'account_nav', 'balance_drawdown_pct',
    'total_account_equity', 'wealth_nav', 'wealth_drawdown_pct',
    'slippage', 'commission', 'trade_count', 'total_margin_exact'}
PAIR_METRICS = {
    'delta_account_growth_pp': 'account_growth_pct',
    'delta_balance_max_dd_pp': 'balance_max_dd_pct',
    'delta_balance_sharpe': 'balance_sharpe',
    'delta_real_trading_net_pnl': 'real_trading_net_pnl',
    'delta_account_end_equity': 'account_end_equity',
    'delta_deposits': 'total_transferred',
    'delta_wealth_return_pp': 'wealth_return_pct',
    'delta_wealth_max_dd_pp': 'wealth_max_dd_pct',
    'delta_wealth_sharpe': 'wealth_sharpe'}


def _require(condition, label):
    if not condition:
        raise ValueError('stage011_plots:' + label)


def _near(left, right):
    return np.allclose(left, right, rtol=1e-10, atol=1e-6, equal_nan=False)


def _boolean(value):
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if value == 'True':
        return True
    if value == 'False':
        return False
    raise ValueError('stage011_plots:explicit_boolean_required')


def _dates(values):
    dates = pd.to_datetime(values, errors='raise')
    _require(not dates.isna().any(), 'missing_date')
    _require((dates == dates.dt.normalize()).all(), 'daily_dates_no_intraday_time')
    return dates.dt.strftime('%Y-%m-%d')


def _return_sharpe(equity, initial, positive_previous):
    equity = np.asarray(equity, dtype=float)
    previous = np.r_[initial, equity[:-1]]
    valid_previous = previous > 0 if positive_previous else previous != 0
    if not (len(equity) and np.isfinite(equity).all() and
            np.isfinite(previous).all() and valid_previous.all()):
        return 0., False
    returns = (equity - previous) / previous
    if not np.isfinite(returns).all():
        return 0., False
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.
    return (float(returns.mean() / std * np.sqrt(252)) if std > 0 else 0.), True


def balance_sharpe(equity):
    """E statistic is undefined if any prior trading balance is nonpositive."""
    return _return_sharpe(equity, INITIAL_TRADING_CAPITAL, True)


def wealth_sharpe(equity):
    """Retain frozen Stage009 W convention; zero prior W makes returns undefined."""
    return _return_sharpe(equity, TOTAL_BUDGET, False)


def validate_inputs(summary, paired, daily):
    """Check exact scope, cash bridges and displayed metrics before allocating figures.

    Counts/endpoints and within-window four-variant date agreement are checked.
    The caller must additionally admit the interior exchange calendar and hashes.
    Daily aggregation can bound event counts, but cannot prove event-level counts.
    """
    for name, frame, fields in (('summary', summary, SUMMARY_FIELDS),
                                ('paired', paired, PAIR_FIELDS),
                                ('daily', daily, DAILY_FIELDS)):
        _require(isinstance(frame, pd.DataFrame) and fields.issubset(frame.columns),
                 'missing_' + name + '_columns')
    s, p, d = summary.copy(), paired.copy(), daily.copy()
    expected = {(start, variant) for start in STARTS for variant in VARIANTS}
    keys = list(zip(s.start, s.variant))
    _require(len(keys) == 92 and len(set(keys)) == 92 and set(keys) == expected,
             'exact92_summary')
    keys = list(zip(p.start, p.arm))
    _require(len(keys) == 46 and len(set(keys)) == 46 and
             set(keys) == {(start, arm) for start in STARTS for arm in ('A', 'C')},
             'exact46_pairs')
    _require(len(d) == EXPECTED_DAILY_POINTS, 'complete141996_daily_points')
    _require(set(zip(d.start, d.variant)) == expected, 'exact92_daily_groups')
    summary_bools = {'observation_only', 'balance_returns_defined',
                     'wealth_returns_defined', 'reserve_exhausted'}
    pair_bools = {'observation_only', 'real_pnl_gate', 'wealth_dd_gate',
                  'wealth_sharpe_gate', 'three_gate_pass'}
    for frame, fields in ((s, summary_bools), (p, pair_bools)):
        for field in fields:
            frame[field] = frame[field].map(_boolean)
    s['actual_start'], s['actual_end'] = _dates(s.actual_start), _dates(s.actual_end)
    d['date'] = _dates(d.date)
    _require(not d.duplicated(['start', 'variant', 'date']).any(), 'unique_daily_dates')
    summary_strings = {'start', 'variant', 'arm', 'version', 'funding_mode',
                       'actual_start', 'actual_end', 'exhaustion_date'}
    numeric_summary = SUMMARY_FIELDS - summary_strings - summary_bools
    numeric_pair = PAIR_FIELDS - {'start', 'arm', 'cohort'} - pair_bools
    for frame, fields in ((s, numeric_summary), (p, numeric_pair),
                          (d, DAILY_FIELDS - {'start', 'variant', 'date'})):
        for field in fields:
            frame[field] = pd.to_numeric(frame[field], errors='raise')
            values = frame[field].to_numpy(float)
            if field == 'trading_margin_peak_pct':
                _require((np.isfinite(values) | np.isnan(values)).all(), 'finite_or_undefined_margin')
            else:
                _require(np.isfinite(values).all(), 'finite_' + field)
    for frame, fields in ((s, ('trading_days', 'modeled_fill_count', 'transfer_event_days',
                               'transfer_event_count', 'nonpositive_trading_equity_days',
                               'nonpositive_total_equity_days', 'trading_margin_over100_days')),
                          (d, ('trade_count',))):
        for field in fields:
            _require((frame[field] >= 0).all() and
                     (frame[field] == np.floor(frame[field])).all(),
                     'nonnegative_integer_' + field)
    for frame, fields in ((s, ('total_slippage', 'total_commission')),
                          (d, ('slippage', 'commission', 'transfer_amount', 'total_margin_exact'))):
        for field in fields:
            _require((frame[field] >= 0).all(), 'nonnegative_' + field)
    si, pi = s.set_index(['start', 'variant']), p.set_index(['start', 'arm'])
    curves, calendars = {}, {}
    for key, group in d.groupby(['start', 'variant'], sort=False):
        start, variant = key
        meta = si.loc[key]
        g = group.sort_values('date').reset_index(drop=True)
        new = variant.endswith('_new')
        actual, count = WINDOW_SCOPE[start]
        _require(meta.arm == variant[0] and meta.funding_mode == 'external_topup' and
                 meta.version == ('uniform_risk' if new else 'prior_risk'),
                 'variant_arm_version_both_topup_identity')
        _require(bool(meta.observation_only) == (start == '2026-01-01'), 'summary_observation_scope')
        _require(meta.actual_start == actual and meta.actual_end == CUTOFF and
                 int(meta.trading_days) == count, 'frozen_summary_window')
        _require(len(g) == count and g.date.iloc[0] == actual and
                 g.date.iloc[-1] == CUTOFF, 'complete_daily_endpoints_count')
        dates = tuple(g.date)
        if start in calendars:
            _require(calendars[start] == dates, 'same_start_four_variant_calendar')
        else:
            calendars[start] = dates
        equity = g.trading_account_equity.to_numpy(float)
        raw, pnl = g.raw_account_equity.to_numpy(float), g.net_pnl.to_numpy(float)
        reserve, transfer = g.reserve_balance.to_numpy(float), g.cumulative_transfer.to_numpy(float)
        wealth = g.total_account_equity.to_numpy(float)
        _require(_near(meta.initial_trading_capital, INITIAL_TRADING_CAPITAL), 'initial_trading_capital150k')
        _require(_near(raw, INITIAL_TRADING_CAPITAL + pnl.cumsum()), 'raw_PnL_bridge')
        _require(_near(transfer, g.transfer_amount.cumsum()), 'daily_transfer_cumulative_bridge')
        _require(_near(equity, raw + transfer), 'deposits_INCLUDED_in_account_equity')
        _require(_near(reserve + transfer, EXTERNAL_FUNDING_LIMIT) and
                 (reserve >= -1e-6).all() and (reserve <= EXTERNAL_FUNDING_LIMIT + 1e-6).all(),
                 'external_funding_conservation_and_limit')
        _require(_near(wealth, equity + reserve) and _near(wealth, TOTAL_BUDGET + pnl.cumsum()),
                 'wealth_equals_300k_plus_real_PnL')
        _require(_near(equity[0], INITIAL_TRADING_CAPITAL) and _near(pnl[0], 0.) and
                 _near(transfer[0], 0.), 'fresh150k_account_start')
        dd = (equity / np.maximum.accumulate(np.r_[INITIAL_TRADING_CAPITAL, equity])[1:] - 1) * 100
        wdd = (wealth / np.maximum.accumulate(np.r_[TOTAL_BUDGET, wealth])[1:] - 1) * 100
        for field, values in (('account_nav', equity / INITIAL_TRADING_CAPITAL),
                              ('balance_drawdown_pct', dd),
                              ('wealth_nav', wealth / TOTAL_BUDGET), ('wealth_drawdown_pct', wdd)):
            _require(_near(g[field].to_numpy(float), values), 'daily_metric_' + field)
        bsharpe, bdefined = balance_sharpe(equity)
        wsharpe, wdefined = wealth_sharpe(wealth)
        _require(bool(meta.balance_returns_defined) == bdefined and
                 bool(meta.wealth_returns_defined) == wdefined, 'return_denominator_defined_flags')
        exhaustion = np.flatnonzero(reserve <= 1e-6)
        exhausted = bool(len(exhaustion))
        _require(bool(meta.reserve_exhausted) == exhausted, 'reserve_exhaustion_flag')
        actual_exhaustion = '' if pd.isna(meta.exhaustion_date) else str(meta.exhaustion_date)
        _require(actual_exhaustion == (g.date.iloc[int(exhaustion[0])] if exhausted else ''),
                 'reserve_exhaustion_date')
        amounts = g.total_margin_exact.to_numpy(float) * 1.65
        margin = np.divide(amounts * 100, equity, out=np.full_like(equity, np.nan), where=equity > 0)
        if np.isfinite(margin).any():
            _require(_near(meta.trading_margin_peak_pct, np.nanmax(margin)), 'summary_daily_metric_trading_margin_peak_pct')
        else:
            _require(pd.isna(meta.trading_margin_peak_pct), 'undefined_margin_peak')
        calculated = dict(
            account_end_equity=equity[-1], account_growth_pct=(equity[-1] / INITIAL_TRADING_CAPITAL - 1) * 100,
            balance_max_dd_pct=float(dd.min()), balance_sharpe=bsharpe,
            wealth_end_equity=wealth[-1], wealth_return_pct=(wealth[-1] / TOTAL_BUDGET - 1) * 100,
            wealth_max_dd_pct=float(wdd.min()), wealth_sharpe=wsharpe,
            real_trading_net_pnl=float(pnl.sum()), total_transferred=transfer[-1],
            off_account_reserve_end=reserve[-1], total_slippage=float(g.slippage.sum()),
            total_commission=float(g.commission.sum()), modeled_fill_count=int(g.trade_count.sum()),
            transfer_event_days=int(g.transfer_amount.gt(0).sum()),
            nonpositive_trading_equity_days=int((equity <= 0).sum()),
            nonpositive_total_equity_days=int((wealth <= 0).sum()),
            trading_margin_over100_days=int((margin > 100).sum()))
        for field, value in calculated.items():
            _require(_near(float(meta[field]), value), 'summary_daily_metric_' + field)
        _require(int(meta.transfer_event_count) >= calculated['transfer_event_days'] and
                 ((int(meta.transfer_event_count) == 0) == (calculated['transfer_event_days'] == 0)),
                 'event_count_bounded_by_daily_aggregation')
        g['plot_date'] = pd.to_datetime(g.date)
        curves[key] = g
    for (start, arm), pair in pi.iterrows():
        _require(bool(pair.observation_only) == (start == '2026-01-01') and
                 pair.cohort == ('January' if start[5:7] == '01' else 'June'),
                 'paired_observation_cohort_scope')
        old, new = si.loc[(start, arm + '_old')], si.loc[(start, arm + '_new')]
        for target, field in PAIR_METRICS.items():
            _require(_near(float(pair[target]), float(new[field]) - float(old[field])), 'paired_metric_' + target)
        comparisons = {field: 0 if math.isclose(float(new[field]), float(old[field]),
                                                rel_tol=1e-10, abs_tol=1e-6)
                       else (1 if new[field] > old[field] else -1)
                       for field in ('real_trading_net_pnl', 'wealth_max_dd_pct', 'wealth_sharpe')}
        gates = dict(real_pnl_gate=comparisons['real_trading_net_pnl'] > 0,
                     wealth_dd_gate=comparisons['wealth_max_dd_pct'] >= 0,
                     wealth_sharpe_gate=comparisons['wealth_sharpe'] >= 0)
        gates['three_gate_pass'] = all(gates.values())
        for field, value in gates.items():
            _require(bool(pair[field]) == bool(value), 'paired_research_gate_' + field)
    return si, pi, curves


def _figure(size):
    fig = Figure(figsize=size, facecolor='white')
    FigureCanvasAgg(fig)
    return fig


def _decorate(ax):
    ax.grid(alpha=.16)
    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(labelsize=8)


def _title(fig, number, description, reviewed):
    state = 'INDEPENDENT REVIEWED WITH LIMITATIONS' if reviewed else 'INDEPENDENT REVIEW PENDING'
    fig.suptitle(f'STAGE011 {number}/5 | {state} | NO_PROMOTION\n' + description,
                 fontsize=11, fontweight='bold', y=.985)


def _footer(fig, extra):
    fig.text(.025, .012, FOOTER + '\n' + extra, fontsize=7.2,
             color='#505c6e', va='bottom')


def _curve(ax, frame, variant, field='account_nav', markers=False):
    new = variant.endswith('_new')
    ax.plot(frame.plot_date, frame[field], color=COLORS[variant],
            lw=1.5 if new else 1.2, ls='-' if new else '--', label=LABELS[variant])
    if markers:
        events = frame.loc[frame.transfer_amount.gt(0)]
        ax.scatter(events.plot_date, events[field], s=20, marker='|',
                   color=COLORS[variant], zorder=4, label='_nolegend_')


def _date_ticks(ax, start):
    span = (pd.Timestamp(CUTOFF) - pd.Timestamp(start)).days
    if span > 365:
        ax.xaxis.set_major_locator(mdates.YearLocator(base=4 if span > 365 * 6 else
                                                      (2 if span > 365 * 3 else 1)))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    else:
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b%y'))


def _grid(si, curves, cohort, reviewed):
    starts = [start for start in STARTS if (start[5:7] == '01') == (cohort == 'January')]
    fig = _figure((15.6, 11.8))
    axes = fig.subplots(4, 3)
    for i, start in enumerate(starts):
        ax = axes.flat[i]
        meta = si.loc[(start, 'A_new')]
        for variant in VARIANTS:
            _curve(ax, curves[(start, variant)], variant)
        ax.axhline(1., color='#bec5ce', lw=.6, ls=':')
        suffix = ' | <1y OBS' if start == '2026-01-01' else ''
        ax.set_title(f'{start}{suffix}', fontsize=9, fontweight='bold')
        ax.text(.02, .97, f'actual {meta.actual_start} | {int(meta.trading_days)} trading days',
                transform=ax.transAxes, fontsize=6.8, va='top', color='#505c6e')
        if i % 3 == 0:
            ax.set_ylabel('Account NAV / 150k', fontsize=8)
        _date_ticks(ax, start)
        _decorate(ax)
        ax.tick_params(labelsize=7)
    for i in range(len(starts), 12):
        axes.flat[i].set_visible(False)
    _title(fig, 2 if cohort == 'January' else 3,
           f'{cohort}: all independent starts to {CUTOFF} | initial account CNY 150,000 / NAV 1\n' +
           STRATEGY_SCOPE, reviewed)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=4, frameon=False, fontsize=7.5,
               loc='upper center', bbox_to_anchor=(.5, .912))
    _footer(fig, '2026 Jan is observation only. Overlapping windows are not independent OOS samples; all requested starts retained.')
    fig.tight_layout(rect=[.012, .085, .995, .887])
    return fig


def _heatmaps(pi, si, reviewed):
    fig = _figure((15.6, 12.3))
    axes = fig.subplots(2, 3)
    metrics = [('delta_real_trading_net_pnl', 'Real trading net PnL delta (CNY)'),
               ('delta_wealth_max_dd_pp', 'W max DD delta (percentage points)'),
               ('delta_wealth_sharpe', 'W Sharpe delta')]
    labels = [start + (' * OBS' if start == '2026-01-01' else '') for start in STARTS]
    for j, (field, title) in enumerate(metrics):
        bound = max(float(np.abs(pi[field].to_numpy(float)).max()), .001)
        for i, arm in enumerate(('A', 'C')):
            ax = axes[i, j]
            values = np.array([pi.loc[(start, arm), field] for start in STARTS], float)
            im = ax.imshow(values.reshape(-1, 1), aspect='auto', cmap='RdBu',
                           vmin=-bound, vmax=bound)
            ax.set_title(f'{arm} uniform minus {arm} prior\n{title}', fontsize=9.5)
            ax.set_xticks([])
            ax.set_yticks(np.arange(len(STARTS)), labels, fontsize=7)
            for k, value in enumerate(values):
                valid = field != 'delta_wealth_sharpe' or (
                    bool(si.loc[(STARTS[k], arm + '_new'), 'wealth_returns_defined']) and
                    bool(si.loc[(STARTS[k], arm + '_old'), 'wealth_returns_defined']))
                rgba = im.cmap(im.norm(value))
                lum = .2126 * rgba[0] + .7152 * rgba[1] + .0722 * rgba[2]
                display = (f'{value:+,.0f}' if j == 0 else f'{value:+.3f}' if j == 2 else f'{value:+.2f}')
                ax.text(0, k, display if valid else 'N/A', ha='center', va='center', fontsize=7,
                        color='white' if lum < .5 else '#17202a')
            fig.colorbar(im, ax=ax, fraction=.045, pad=.025)
    _title(fig, 4, 'Economic comparison across every requested start: same total budget CNY 300,000\n'
           'Positive = more real PnL / shallower W drawdown / higher W Sharpe; deposits are excluded from PnL', reviewed)
    _footer(fig, '* 2026 Jan: observation only. A/C share each metric scale; undefined W Sharpe is N/A; three gates describe research only.')
    fig.tight_layout(rect=[.005, .085, .995, .91])
    return fig


def _mature_starts(month=None):
    return [start for start in STARTS if start != '2026-01-01' and
            (month is None or start[5:7] == month)]


def _count_panel(ax, si, field, title, ylabel, predicate):
    x, width = np.arange(2), .18
    for i, variant in enumerate(VARIANTS):
        counts = [sum(predicate(si.loc[(start, variant), field]) for start in _mature_starts(month))
                  for month in ('01', '06')]
        bars = ax.bar(x + (i - 1.5) * width, counts, width,
                      color=COLORS[variant], label=SHORT_LABELS[variant])
        for bar, count in zip(bars, counts):
            ax.text(bar.get_x() + bar.get_width() / 2, count + .13, str(count), ha='center', fontsize=8)
    ax.set_xticks(x, ['January (11 windows)', 'June (11 windows)'])
    ax.set_ylim(0, 12.8)
    ax.set_ylabel(ylabel, fontsize=8)
    ax.set_title(title, fontsize=10, fontweight='bold')
    ax.legend(frameon=False, fontsize=7.5, ncol=2)
    _decorate(ax)


def _table(ax, rows, labels, title, widths, fontsize=8):
    ax.axis('off')
    table = ax.table(cellText=rows, colLabels=labels, loc='center',
                     cellLoc='center', colWidths=widths)
    table.auto_set_font_size(False)
    table.set_fontsize(fontsize)
    table.scale(1., 1.7)
    ax.set_title(title, fontsize=10, fontweight='bold')


def _overview(si, pi, reviewed):
    fig = _figure((16., 13.2))
    axes = fig.subplots(3, 2)
    _count_panel(axes[0, 0], si, 'real_trading_net_pnl', 'Actual trading loss windows',
                 'Windows with real net PnL < 0', lambda value: value < 0)
    _count_panel(axes[0, 1], si, 'reserve_exhausted', 'External reserve exhausted',
                 'Windows consuming all CNY 150,000 reserve', bool)
    ax = axes[1, 0]
    for i, variant in enumerate(VARIANTS):
        for j, month in enumerate(('01', '06')):
            values = [si.loc[(start, variant), 'total_transferred'] / 1000 for start in _mature_starts(month)]
            x = i * 2 + j
            ax.scatter(x + np.linspace(-.15, .15, len(values)), values,
                       color=COLORS[variant], marker='o' if month == '01' else '^', s=18, alpha=.8)
            ax.plot([x - .22, x + .22], [np.median(values)] * 2, color=COLORS[variant], lw=2)
    ax.set_xticks(np.arange(8), [SHORT_LABELS[v] + '\n' + m for v in VARIANTS for m in ('Jan', 'Jun')])
    ax.set_ylim(-5, 160)
    ax.set_ylabel('Deposits consumed (CNY thousands)')
    ax.set_title('All 22 mature windows / variant; horizontal line = median', fontsize=10, fontweight='bold')
    _decorate(ax)
    rows = []
    for variant in VARIANTS:
        meta = si.loc[('2015-01-01', variant)]
        rows.append([SHORT_LABELS[variant], '150,000', f'{meta.real_trading_net_pnl:,.0f}',
                     f'{meta.total_transferred:,.0f}', f'{meta.account_end_equity:,.0f}'])
    _table(axes[1, 1], rows, ['Variant', 'Initial E', '+ Real PnL', '+ Deposits', '= End E'],
           '2015 account bridge (CNY): 150k + PnL + deposits', [.19, .16, .23, .18, .24], 7.5)
    rows = []
    for variant in VARIANTS:
        meta = si.loc[('2026-01-01', variant)]
        rows.append([SHORT_LABELS[variant], f'{meta.real_trading_net_pnl / 1000:+.1f}',
                     f'{meta.total_transferred / 1000:.1f}', f'{meta.wealth_return_pct:+.2f}%',
                     f'{meta.wealth_max_dd_pct:.2f}%',
                     f'{meta.wealth_sharpe:.3f}' if meta.wealth_returns_defined else 'N/A'])
    _table(axes[2, 0], rows, ['Variant', 'Real PnL k', 'Deposits k', 'W return', 'W DD', 'W Sharpe'],
           '2026 Jan: <1 year OBSERVATION ONLY', [.19, .17, .17, .16, .15, .16], 7.5)
    ax = axes[2, 1]
    ax.axis('off')
    lines = ['Mature research comparisons: 22 starts per arm (11 Jan + 11 Jun)']
    for arm in ('A', 'C'):
        pairs = pi.loc[(slice(None), arm), :]
        mature = pairs.loc[~pairs.observation_only]
        lines.append(f'{arm}: real PnL improves {int(mature.real_pnl_gate.sum())}/22; '
                     f'W DD no worse {int(mature.wealth_dd_gate.sum())}/22')
        lines.append(f'    W Sharpe no lower {int(mature.wealth_sharpe_gate.sum())}/22; '
                     f'all three {int(mature.three_gate_pass.sum())}/22')
    risk_windows = int(((si.trading_margin_over100_days > 0) |
                        (si.nonpositive_trading_equity_days > 0)).sum())
    undefined_w = int((~si.wealth_returns_defined).sum())
    lines += ['', f'Broker margin x1.65 / E: >100% or nonpositive E in {risk_windows}/92 windows.',
              f'Undefined W Sharpe in {undefined_w}/92; source convention allows negative prior W.',
              'E<=0 days have undefined margin ratio, recorded separately.',
              'Overlapping histories / zero commissions / static margin limits remain.',
              'Three gates are descriptive research comparisons. NO_PROMOTION.']
    ax.text(.015, .9, '\n'.join(lines), fontsize=8.1, va='top', linespacing=1.65)
    ax.set_title('Research gates and risk limitations', fontsize=10, fontweight='bold')
    _title(fig, 5, 'Prior versus uniform OI base risks: real trading outcomes, funding and account bridge\n'
           'Both versions use the same 150k trading + 150k external reserve rule; all 92 variant-windows retained', reviewed)
    _footer(fig, 'Funding is an internal transfer from the fixed reserve. More deposits do not demonstrate trading alpha; no formal promotion.')
    fig.tight_layout(rect=[.01, .085, .995, .925], h_pad=3.2)
    return fig


def render_five(summary: pd.DataFrame, paired: pd.DataFrame, daily: pd.DataFrame,
                reviewed=False) -> dict[str, Figure]:
    """Return five unsaved figures; reviewed changes only the status title."""
    _require(type(reviewed) is bool, 'explicit_reviewed_boolean')
    si, pi, curves = validate_inputs(summary, paired, daily)
    figures, created = {}, []
    try:
        fig = _figure((14.4, 9.))
        created.append(fig)
        nav_ax, dd_ax = fig.subplots(2, 1, sharex=True, gridspec_kw={'height_ratios': [2, 1]})
        for variant in VARIANTS:
            frame = curves[('2015-01-01', variant)]
            _curve(nav_ax, frame, variant, markers=True)
            _curve(dd_ax, frame, variant, 'balance_drawdown_pct')
        nav_ax.axhline(1., color='#bec5ce', lw=.7, ls=':')
        dd_ax.axhline(0., color='#bec5ce', lw=.7, ls=':')
        nav_ax.set_ylabel('Account NAV = trading balance E / 150,000')
        dd_ax.set_ylabel('Account E drawdown (%)')
        dd_ax.set_xlabel('Exchange trading date')
        nav_ax.legend(frameon=False, fontsize=8.5, ncol=2, loc='upper left')
        for ax in (nav_ax, dd_ax):
            _decorate(ax)
        _title(fig, 1, f'Full start 2015-01-01 / actual 2015-01-05 to {CUTOFF} | initial E 150k / NAV 1\n' +
               STRATEGY_SCOPE, reviewed)
        _footer(fig, 'Vertical NAV marks show deposit days in both versions. Linear axes retain negative balances if present.')
        fig.tight_layout(rect=[.01, .11, .995, .91])
        figures[FIGURE_NAMES[0]] = fig
        for cohort, name in (('January', FIGURE_NAMES[1]), ('June', FIGURE_NAMES[2])):
            fig = _grid(si, curves, cohort, reviewed)
            created.append(fig)
            figures[name] = fig
        fig = _heatmaps(pi, si, reviewed)
        created.append(fig)
        figures[FIGURE_NAMES[3]] = fig
        fig = _overview(si, pi, reviewed)
        created.append(fig)
        figures[FIGURE_NAMES[4]] = fig
        return figures
    except Exception:
        for fig in created:
            fig.clear()
        raise
