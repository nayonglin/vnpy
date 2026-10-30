"""Pure C-only display of reserve100k versus reserve150k saved ledgers.

No engine, files, HTTP or output writes. The caller admits source/proof hashes,
exchange-calendar truth and event-level counts, then saves the returned figures.
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
EXPECTED_DAILY_POINTS = 70998
_COUNTS = (2871, 2773, 2627, 2527, 2383, 2286, 2139, 2040, 1896,
           1797, 1652, 1555, 1409, 1312, 1166, 1070, 924, 826, 682, 584, 440, 343, 197)
_ACTUAL_STARTS = ('2015-01-05', '2015-06-01', '2016-01-04', '2016-06-01',
                  '2017-01-03', '2017-06-01', '2018-01-02', '2018-06-01',
                  '2019-01-02', '2019-06-03', '2020-01-02', '2020-06-01',
                  '2021-01-04', '2021-06-01', '2022-01-04', '2022-06-01',
                  '2023-01-03', '2023-06-01', '2024-01-02', '2024-06-03',
                  '2025-01-02', '2025-06-03', '2026-01-05')
WINDOW_SCOPE = dict(zip(STARTS, zip(_ACTUAL_STARTS, _COUNTS)))
FRESH_STARTS = frozenset(('2017-01-01', '2017-06-01', '2018-01-01', '2018-06-01'))
VARIANTS = ('C_R150', 'C_R100')
RESERVES = {'C_R150': 150000., 'C_R100': 100000.}
COLORS = {'C_R150': '#7f8a96', 'C_R100': '#2168ad'}
LABELS = {'C_R150': 'C R150: 150k external reserve', 'C_R100': 'C R100: 100k external reserve'}
FIGURE_NAMES = ('01_c_account_nav_drawdown_2015.png', '02_january_c_account_nav.png',
                '03_june_c_account_nav.png', '04_real_pnl_account_dd_deposit_deltas.png',
                '05_reserve_use_and_survival_overview.png')
FOOTER = ('NAV = trading E / 150k: untransferred external R excluded; deposits INCLUDED; E growth/DD/Sharpe include cashflows.\n'
          'C only, short bottom 20% veto retained; original risks: ordinary 1.8%, OI surge 6% / 6%, OI decline 2.5%; no new alpha rule.\n'
          'R100 vs R150 total commitments differ (250k vs 300k). W = E + R is a conservation check, not a common-budget comparison.\n'
          'R100: 4 fresh engine windows + 19 proven nonbinding reuse; R150: 23 frozen baselines. 2026 Jan <1y: observation only.')
SUMMARY_FIELDS = {
    'start', 'variant', 'arm', 'version', 'funding_mode', 'method', 'reserve_initial',
    'initial_trading_capital', 'actual_start', 'actual_end', 'trading_days', 'observation_only',
    'account_end_equity', 'account_growth_pct', 'balance_max_dd_pct', 'balance_sharpe',
    'balance_returns_defined', 'real_trading_net_pnl', 'total_transferred', 'off_account_reserve_end',
    'total_slippage', 'total_commission', 'modeled_fill_count', 'transfer_event_days',
    'transfer_event_count', 'reserve_exhausted', 'exhaustion_date', 'nonpositive_trading_equity_days',
    'trading_margin_peak_pct', 'trading_margin_over100_days'}
PAIR_FIELDS = {
    'start', 'arm', 'cohort', 'observation_only', 'method100', 'delta_account_end_equity',
    'delta_real_trading_net_pnl', 'delta_account_growth_pp', 'delta_balance_max_dd_pp',
    'delta_balance_sharpe', 'delta_deposits', 'real_pnl_comparison', 'dd_comparison', 'sharpe_comparison'}
DAILY_FIELDS = {
    'start', 'variant', 'date', 'raw_account_equity', 'net_pnl', 'trading_account_equity',
    'reserve_balance', 'cumulative_transfer', 'transfer_amount', 'total_account_equity',
    'slippage', 'commission', 'trade_count', 'total_margin_exact', 'account_nav', 'balance_drawdown_pct'}
PAIR_METRICS = {
    'delta_account_end_equity': 'account_end_equity', 'delta_real_trading_net_pnl': 'real_trading_net_pnl',
    'delta_account_growth_pp': 'account_growth_pct', 'delta_balance_max_dd_pp': 'balance_max_dd_pct',
    'delta_balance_sharpe': 'balance_sharpe', 'delta_deposits': 'total_transferred'}


def _require(condition, label):
    if not condition:
        raise ValueError('stage013_plots:' + label)


def _near(left, right):
    return np.allclose(left, right, rtol=1e-10, atol=1e-6, equal_nan=False)


def _boolean(value):
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if value == 'True':
        return True
    if value == 'False':
        return False
    raise ValueError('stage013_plots:explicit_boolean_required')


def _dates(values):
    dates = pd.to_datetime(values, errors='raise')
    _require(not dates.isna().any() and (dates == dates.dt.normalize()).all(), 'valid_daily_dates')
    return dates.dt.strftime('%Y-%m-%d')


def balance_sharpe(equity):
    """Cashflow-inclusive account statistic, undefined after nonpositive prior E."""
    equity = np.asarray(equity, dtype=float)
    previous = np.r_[INITIAL_TRADING_CAPITAL, equity[:-1]]
    if not (len(equity) and np.isfinite(equity).all() and
            np.isfinite(previous).all() and (previous > 0).all()):
        return 0., False
    returns = (equity - previous) / previous
    if not np.isfinite(returns).all():
        return 0., False
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.
    return (float(returns.mean() / std * np.sqrt(252)) if std > 0 else 0.), True


def _method100(start):
    return 'fresh_engine' if start in FRESH_STARTS else 'proven_nonbinding_reuse'


def validate_inputs(summary, paired, daily):
    """Reject incomplete scope, mixed identities and broken cash/metric bridges.

    Frozen counts/endpoints and within-window date agreement are enforced. A
    proven reuse must also preserve every supplied daily trading/cost/margin
    path, while external reserve and total wealth differ by exactly 50k.
    """
    for name, frame, fields in (('summary', summary, SUMMARY_FIELDS), ('paired', paired, PAIR_FIELDS),
                                ('daily', daily, DAILY_FIELDS)):
        _require(isinstance(frame, pd.DataFrame) and fields.issubset(frame.columns), 'missing_' + name + '_columns')
    s, p, d = summary.copy(), paired.copy(), daily.copy()
    expected = {(start, variant) for start in STARTS for variant in VARIANTS}
    keys = list(zip(s.start, s.variant))
    _require(len(keys) == 46 and len(set(keys)) == 46 and set(keys) == expected, 'exact46_summary')
    _require(len(p) == 23 and not p.start.duplicated().any() and set(p.start) == set(STARTS), 'exact23_pairs')
    _require(len(d) == EXPECTED_DAILY_POINTS and set(zip(d.start, d.variant)) == expected, 'complete70998_daily')
    sb = {'observation_only', 'balance_returns_defined', 'reserve_exhausted'}
    for field in sb:
        s[field] = s[field].map(_boolean)
    p['observation_only'] = p.observation_only.map(_boolean)
    s['actual_start'], s['actual_end'], d['date'] = _dates(s.actual_start), _dates(s.actual_end), _dates(d.date)
    _require(not d.duplicated(['start', 'variant', 'date']).any(), 'unique_daily_dates')
    ss = {'start', 'variant', 'arm', 'version', 'funding_mode', 'method', 'actual_start', 'actual_end', 'exhaustion_date'}
    for frame, fields in ((s, SUMMARY_FIELDS - ss - sb),
                          (p, PAIR_FIELDS - {'start', 'arm', 'cohort', 'observation_only', 'method100'}),
                          (d, DAILY_FIELDS - {'start', 'variant', 'date'})):
        for field in fields:
            frame[field] = pd.to_numeric(frame[field], errors='raise')
            values = frame[field].to_numpy(float)
            valid = (np.isfinite(values) | np.isnan(values)) if field == 'trading_margin_peak_pct' else np.isfinite(values)
            _require(valid.all(), 'finite_' + field)
    if 'reserve_initial' in d:
        d['reserve_initial'] = pd.to_numeric(d.reserve_initial, errors='raise')
    for frame, fields in ((s, ('trading_days', 'modeled_fill_count', 'transfer_event_days', 'transfer_event_count',
                               'nonpositive_trading_equity_days', 'trading_margin_over100_days')), (d, ('trade_count',))):
        for field in fields:
            _require((frame[field] >= 0).all() and (frame[field] == np.floor(frame[field])).all(), 'nonnegative_integer_' + field)
    for frame, fields in ((s, ('total_slippage', 'total_commission')),
                          (d, ('slippage', 'commission', 'transfer_amount', 'total_margin_exact'))):
        for field in fields:
            _require((frame[field] >= 0).all(), 'nonnegative_' + field)
    si, pi = s.set_index(['start', 'variant']), p.set_index('start')
    curves, calendars = {}, {}
    for (start, variant), group in d.groupby(['start', 'variant'], sort=False):
        meta = si.loc[(start, variant)]
        g = group.sort_values('date').reset_index(drop=True)
        small, reserve_initial = variant == 'C_R100', RESERVES[variant]
        actual, count = WINDOW_SCOPE[start]
        _require(meta.arm == 'C' and meta.funding_mode == 'external_topup' and
                 meta.version == ('reserve100k' if small else 'reserve150k') and
                 meta.method == (_method100(start) if small else 'frozen_baseline'), 'C_original_risk_reserve_method_identity')
        _require(_near(meta.reserve_initial, reserve_initial) and _near(meta.initial_trading_capital, INITIAL_TRADING_CAPITAL),
                 'reserve_and_trading_initial_capital')
        if 'reserve_initial' in g:
            _require(_near(g.reserve_initial, reserve_initial), 'daily_reserve_initial')
        _require(bool(meta.observation_only) == (start == '2026-01-01'), 'summary_observation_scope')
        _require(meta.actual_start == actual and meta.actual_end == CUTOFF and int(meta.trading_days) == count,
                 'frozen_summary_window')
        _require(len(g) == count and g.date.iloc[0] == actual and g.date.iloc[-1] == CUTOFF, 'complete_daily_endpoints_count')
        dates = tuple(g.date)
        if start in calendars:
            _require(calendars[start] == dates, 'same_start_two_variant_calendar')
        else:
            calendars[start] = dates
        equity, raw = g.trading_account_equity.to_numpy(float), g.raw_account_equity.to_numpy(float)
        pnl, transfer, reserve = g.net_pnl.to_numpy(float), g.cumulative_transfer.to_numpy(float), g.reserve_balance.to_numpy(float)
        _require(_near(raw, INITIAL_TRADING_CAPITAL + pnl.cumsum()), 'raw_PnL_bridge')
        _require(_near(transfer, g.transfer_amount.cumsum()), 'daily_transfer_bridge')
        _require(_near(equity, raw + transfer), 'deposits_INCLUDED_in_E')
        _require(_near(reserve + transfer, reserve_initial) and (reserve >= -1e-6).all() and
                 (reserve <= reserve_initial + 1e-6).all(), 'reserve_cap_conservation')
        _require(_near(g.total_account_equity, equity + reserve) and
                 _near(g.total_account_equity, INITIAL_TRADING_CAPITAL + reserve_initial + pnl.cumsum()),
                 'W_conservation_distinct_initial_budgets')
        _require(_near(equity[0], INITIAL_TRADING_CAPITAL) and _near(pnl[0], 0.) and _near(transfer[0], 0.), 'fresh_E150k_NAV1_start')
        dd = (equity / np.maximum.accumulate(np.r_[INITIAL_TRADING_CAPITAL, equity])[1:] - 1) * 100
        _require(_near(g.account_nav, equity / INITIAL_TRADING_CAPITAL), 'E_NAV150k_external_R_excluded')
        _require(_near(g.balance_drawdown_pct, dd), 'balance_drawdown_from_initial_highwater')
        sharpe, defined = balance_sharpe(equity)
        _require(bool(meta.balance_returns_defined) == defined, 'balance_returns_defined')
        exhausted = np.flatnonzero(reserve <= 1e-6)
        _require(bool(meta.reserve_exhausted) == bool(len(exhausted)), 'reserve_exhausted_flag')
        date = '' if pd.isna(meta.exhaustion_date) else str(meta.exhaustion_date)
        _require(date == (g.date.iloc[int(exhausted[0])] if len(exhausted) else ''), 'reserve_exhaustion_date')
        margin = np.divide(g.total_margin_exact.to_numpy(float) * 165, equity,
                           out=np.full_like(equity, np.nan), where=equity > 0)
        if np.isfinite(margin).any():
            _require(_near(meta.trading_margin_peak_pct, np.nanmax(margin)), 'summary_metric_trading_margin_peak_pct')
        else:
            _require(pd.isna(meta.trading_margin_peak_pct), 'undefined_margin_peak')
        calculated = dict(account_end_equity=equity[-1], account_growth_pct=(equity[-1] / INITIAL_TRADING_CAPITAL - 1) * 100,
                          balance_max_dd_pct=float(dd.min()), balance_sharpe=sharpe,
                          real_trading_net_pnl=float(pnl.sum()), total_transferred=transfer[-1], off_account_reserve_end=reserve[-1],
                          total_slippage=float(g.slippage.sum()), total_commission=float(g.commission.sum()),
                          modeled_fill_count=int(g.trade_count.sum()), transfer_event_days=int(g.transfer_amount.gt(0).sum()),
                          nonpositive_trading_equity_days=int((equity <= 0).sum()), trading_margin_over100_days=int((margin > 100).sum()))
        for field, value in calculated.items():
            _require(_near(float(meta[field]), value), 'summary_metric_' + field)
        _require(int(meta.transfer_event_count) >= calculated['transfer_event_days'] and
                 ((int(meta.transfer_event_count) == 0) == (calculated['transfer_event_days'] == 0)), 'event_count_daily_bound')
        g['plot_date'] = pd.to_datetime(g.date)
        curves[(start, variant)] = g
    for start, pair in pi.iterrows():
        old, new = si.loc[(start, 'C_R150')], si.loc[(start, 'C_R100')]
        _require(pair.arm == 'C' and pair.method100 == new.method and
                 bool(pair.observation_only) == (start == '2026-01-01') and
                 pair.cohort == ('January' if start[5:7] == '01' else 'June'), 'paired_method_cohort_scope')
        for target, field in PAIR_METRICS.items():
            _require(_near(float(pair[target]), float(new[field]) - float(old[field])), 'paired_metric_' + target)
        for target, field in (('real_pnl_comparison', 'real_trading_net_pnl'),
                              ('dd_comparison', 'balance_max_dd_pct'), ('sharpe_comparison', 'balance_sharpe')):
            comparison = 0 if math.isclose(float(new[field]), float(old[field]), rel_tol=1e-10, abs_tol=1e-6) else (1 if new[field] > old[field] else -1)
            _require(pair[target] == comparison, 'paired_comparison_' + target)
        if new.method == 'proven_nonbinding_reuse':
            old_curve, new_curve = curves[(start, 'C_R150')], curves[(start, 'C_R100')]
            _require(old_curve.cumulative_transfer.max() <= 100000. + 1e-6, 'proven_reuse_must_be_nonbinding')
            for field in ('raw_account_equity', 'net_pnl', 'trading_account_equity', 'cumulative_transfer',
                          'transfer_amount', 'slippage', 'commission', 'trade_count', 'total_margin_exact'):
                _require(_near(old_curve[field], new_curve[field]), 'proven_reuse_daily_' + field)
            _require(_near(old_curve.reserve_balance - new_curve.reserve_balance, 50000.) and
                     _near(old_curve.total_account_equity - new_curve.total_account_equity, 50000.), 'proven_reuse_only_external_R_differs')
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
    status = 'INDEPENDENT REVIEWED WITH LIMITATIONS' if reviewed else 'INDEPENDENT REVIEW PENDING'
    fig.suptitle(f'STAGE013 {number}/5 | {status} | NO_PROMOTION\n' + description,
                 fontsize=11, fontweight='bold', y=.985)


def _footer(fig, extra):
    fig.text(.025, .012, FOOTER + '\n' + extra, fontsize=7.1, color='#505c6e', va='bottom')


def _curve(ax, frame, variant, field='account_nav', markers=False):
    small = variant == 'C_R100'
    ax.plot(frame.plot_date, frame[field], color=COLORS[variant], lw=1.6 if small else 2.4,
            ls='-' if small else '--', label=LABELS[variant], alpha=.92 if small else .8)
    if markers:
        events = frame.loc[frame.transfer_amount.gt(0)]
        ax.scatter(events.plot_date, events[field], s=20, marker='|', color=COLORS[variant], zorder=4, label='_nolegend_')


def _date_ticks(ax, start):
    span = (pd.Timestamp(CUTOFF) - pd.Timestamp(start)).days
    if span > 365:
        ax.xaxis.set_major_locator(mdates.YearLocator(base=4 if span > 365 * 6 else 2 if span > 365 * 3 else 1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    else:
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b%y'))


def _grid(si, curves, cohort, reviewed):
    starts = [s for s in STARTS if (s[5:7] == '01') == (cohort == 'January')]
    fig = _figure((15.6, 11.8))
    axes = fig.subplots(4, 3)
    for i, start in enumerate(starts):
        ax = axes.flat[i]
        meta = si.loc[(start, 'C_R100')]
        for variant in VARIANTS:
            _curve(ax, curves[(start, variant)], variant)
        ax.axhline(1., color='#bec5ce', lw=.6, ls=':')
        suffix = ' | <1y OBS' if start == '2026-01-01' else ''
        ax.set_title(start + suffix, fontsize=9, fontweight='bold')
        method = 'proven reuse: E curves overlap' if meta.method == 'proven_nonbinding_reuse' else 'fresh R100 engine'
        ax.text(.02, .97, f'{meta.actual_start} | {int(meta.trading_days)} days | {method}',
                transform=ax.transAxes, fontsize=6.5, va='top', color='#505c6e')
        if i % 3 == 0:
            ax.set_ylabel('C account NAV / 150k', fontsize=8)
        _date_ticks(ax, start)
        _decorate(ax)
        ax.tick_params(labelsize=7)
    for i in range(len(starts), 12):
        axes.flat[i].set_visible(False)
    _title(fig, 2 if cohort == 'January' else 3,
           f'{cohort}: all independent starts through {CUTOFF} | E starts at 150k / NAV 1\n'
           'C original OI risk tiers retained | 100k versus 150k external reserve', reviewed)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=2, frameon=False, fontsize=8, loc='upper center', bbox_to_anchor=(.5, .912))
    _footer(fig, 'All requested starts retained. Overlapping histories are not independent OOS samples; no formal promotion test.')
    fig.tight_layout(rect=[.012, .10, .995, .887])
    return fig


def _heatmaps(pi, reviewed):
    fig = _figure((15., 10.8))
    axes = fig.subplots(1, 3)
    labels = [s + (' * OBS' if s == '2026-01-01' else '') for s in STARTS]
    for ax, field, title in zip(axes,
        ('delta_real_trading_net_pnl', 'delta_balance_max_dd_pp', 'delta_deposits'),
        ('Real trading net PnL delta (CNY)', 'Account E max DD delta (pp)', 'Deposits consumed delta (CNY)')):
        values = np.array([pi.loc[start, field] for start in STARTS], float)
        bound = max(float(np.abs(values).max()), .001)
        im = ax.imshow(values.reshape(-1, 1), aspect='auto', cmap='RdBu', vmin=-bound, vmax=bound)
        ax.set_title(title, fontsize=10)
        ax.set_xticks([])
        ax.set_yticks(np.arange(len(STARTS)), labels, fontsize=8)
        for i, value in enumerate(values):
            rgba = im.cmap(im.norm(value))
            luminance = .2126 * rgba[0] + .7152 * rgba[1] + .0722 * rgba[2]
            ax.text(0, i, f'{value:+.2f}' if field.endswith('_pp') else f'{value:+,.0f}',
                    ha='center', va='center', fontsize=8, color='white' if luminance < .5 else '#17202a')
        fig.colorbar(im, ax=ax, fraction=.045, pad=.025)
    _title(fig, 4, 'Every window: R100 minus R150 | actual trading PnL, account drawdown and funding consumed\n'
           'Positive DD delta = shallower E drawdown; negative deposits delta = less funding; no common-budget W test', reviewed)
    _footer(fig, 'Zero deltas in proven nonbinding windows are expected. Deposit savings are not trading alpha; * denotes observation only.')
    fig.tight_layout(rect=[.005, .115, .995, .89])
    return fig


def _table(ax, rows, columns, title, widths):
    ax.axis('off')
    table = ax.table(cellText=rows, colLabels=columns, loc='center', cellLoc='center', colWidths=widths)
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1., 1.8)
    ax.set_title(title, fontsize=10, fontweight='bold')


def _overview(si, pi, reviewed):
    fig = _figure((16., 13.))
    axes = fig.subplots(3, 2)
    ax, width = axes[0, 0], .32
    for i, variant in enumerate(VARIANTS):
        q = si.xs(variant, level='variant')
        q = q.loc[~q.observation_only]
        counts = [int(q.real_trading_net_pnl.lt(0).sum()), int(q.nonpositive_trading_equity_days.gt(0).sum()),
                  int(q.trading_margin_over100_days.gt(0).sum())]
        bars = ax.bar(np.arange(3) + (i - .5) * width, counts, width, color=COLORS[variant], label=variant)
        for bar, count in zip(bars, counts):
            ax.text(bar.get_x() + bar.get_width() / 2, count + .15, str(count), ha='center', fontsize=8)
    ax.set_xticks(np.arange(3), ['Real PnL < 0', 'Any E <= 0', 'Margin x1.65/E >100%'])
    ax.set_ylim(0, 24)
    ax.set_ylabel('Mature windows (22 per variant)')
    ax.set_title('Trading loss, account survival and margin pressure', fontsize=10, fontweight='bold')
    ax.legend(frameon=False, fontsize=8)
    _decorate(ax)
    ax = axes[0, 1]
    for i, variant in enumerate(VARIANTS):
        counts = [sum(bool(si.loc[(s, variant), 'reserve_exhausted']) for s in STARTS
                      if s != '2026-01-01' and s[5:7] == month) for month in ('01', '06')]
        bars = ax.bar(np.arange(2) + (i - .5) * width, counts, width, color=COLORS[variant], label=variant)
        for bar, count in zip(bars, counts):
            ax.text(bar.get_x() + bar.get_width() / 2, count + .12, str(count), ha='center', fontsize=8)
    ax.set_xticks(np.arange(2), ['January (11)', 'June (11)'])
    ax.set_ylim(0, 12.8)
    ax.set_ylabel('Windows with external reserve exhausted')
    ax.set_title('Exhaustion: 100k cap versus 150k cap', fontsize=10, fontweight='bold')
    ax.legend(frameon=False, fontsize=8)
    _decorate(ax)
    ax = axes[1, 0]
    for i, variant in enumerate(VARIANTS):
        for j, month in enumerate(('01', '06')):
            starts = [s for s in STARTS if s != '2026-01-01' and s[5:7] == month]
            values = [si.loc[(s, variant), 'total_transferred'] / 1000 for s in starts]
            x = i * 2 + j
            ax.scatter(x + np.linspace(-.14, .14, len(values)), values, color=COLORS[variant], s=22,
                       marker='o' if month == '01' else '^')
            ax.plot([x - .23, x + .23], [np.mean(values)] * 2, color=COLORS[variant], lw=2)
        ax.axhline(RESERVES[variant] / 1000, color=COLORS[variant], ls=':', lw=1)
    ax.set_xticks(np.arange(4), ['R150 Jan', 'R150 Jun', 'R100 Jan', 'R100 Jun'])
    ax.set_ylim(-5, 165)
    ax.set_ylabel('Deposits consumed (CNY thousands)')
    ax.set_title('Every mature window retained; bar = mean, dotted = cap', fontsize=10, fontweight='bold')
    _decorate(ax)
    rows = []
    for variant in VARIANTS:
        m = si.loc[('2015-01-01', variant)]
        rows.append([variant, f'{m.real_trading_net_pnl:,.0f}', f'{m.total_transferred:,.0f}',
                     f'{m.account_end_equity:,.0f}', f'{m.off_account_reserve_end:,.0f}'])
    _table(axes[1, 1], rows, ['Variant', 'Real PnL', 'Deposits', 'End E', 'End R'],
           '2015 bridge: E = 150k + PnL + deposits; E curves overlap', [.17, .23, .19, .23, .18])
    rows = []
    for variant in VARIANTS:
        m = si.loc[('2026-01-01', variant)]
        rows.append([variant, f'{m.real_trading_net_pnl / 1000:+.1f}', f'{m.account_end_equity / 150000:.3f}',
                     f'{m.balance_max_dd_pct:.2f}%', f'{m.balance_sharpe:.3f}' if m.balance_returns_defined else 'N/A',
                     f'{m.total_transferred / 1000:.1f}'])
    _table(axes[2, 0], rows, ['Variant', 'Real PnL k', 'End NAV', 'E DD', 'E Sharpe', 'Deposit k'],
           '2026 Jan: <1 year OBSERVATION ONLY', [.17, .19, .16, .16, .16, .16])
    ax = axes[2, 1]
    ax.axis('off')
    mature = pi.loc[~pi.observation_only]
    lines = ['23 starts: 22 mature + 2026 Jan observation.',
             'R100: 4 fresh engines + 19 proven nonbinding reuse.',
             'R150: 23 frozen original C baselines; no uniform-risk variant.',
             f'Real PnL higher / tied / lower (mature): {int(mature.real_pnl_comparison.eq(1).sum())} / '
             f'{int(mature.real_pnl_comparison.eq(0).sum())} / {int(mature.real_pnl_comparison.eq(-1).sum())}.',
             '', 'E drawdown and Sharpe include internal deposits.',
             'Undefined E Sharpe is N/A; E<=0 makes margin ratio undefined.',
             'R100 and R150 commit different total capital (250k / 300k).',
             'Unused R never enters trading risk or margin capacity.',
             'Zero commissions / static margin / overlapping-history limits remain.',
             'No common-budget W gates or formal promotion. NO_PROMOTION.']
    ax.text(.015, .9, '\n'.join(lines), fontsize=8.2, va='top', linespacing=1.65)
    ax.set_title('Method transparency and interpretation', fontsize=10, fontweight='bold')
    _title(fig, 5, 'C original risk tiers: reserve consumption, real trading outcomes and survival\n'
           'Trading principal fixed at 150k; external reserve only changes from 150k to 100k', reviewed)
    _footer(fig, 'Static exchange margin x1.65 is not historical broker capacity or liquidation proof; research only, no rescue tuning.')
    fig.tight_layout(rect=[.01, .10, .995, .925], h_pad=3.1)
    return fig


def render_five(summary: pd.DataFrame, paired: pd.DataFrame, daily: pd.DataFrame,
                reviewed=False) -> dict[str, Figure]:
    """Return five unsaved figures; reviewed changes only the status title."""
    _require(type(reviewed) is bool, 'explicit_reviewed_boolean')
    si, pi, curves = validate_inputs(summary, paired, daily)
    figures, created = {}, []
    try:
        fig = _figure((14.4, 9.2))
        created.append(fig)
        nav_ax, dd_ax = fig.subplots(2, 1, sharex=True, gridspec_kw={'height_ratios': [2, 1]})
        for variant in VARIANTS:
            frame = curves[('2015-01-01', variant)]
            _curve(nav_ax, frame, variant, markers=True)
            _curve(dd_ax, frame, variant, 'balance_drawdown_pct')
        nav_ax.axhline(1., color='#bec5ce', lw=.7, ls=':')
        dd_ax.axhline(0., color='#bec5ce', lw=.7, ls=':')
        nav_ax.text(.025, .94, 'E curves overlap: proven nonbinding reuse; 2015 deposits 43,960 < 100,000.',
                    transform=nav_ax.transAxes, fontsize=8.5, va='top', color='#34495e')
        nav_ax.set_ylabel('C account NAV = trading E / 150,000')
        dd_ax.set_ylabel('Account E drawdown (%)')
        dd_ax.set_xlabel('Exchange trading date')
        nav_ax.legend(frameon=False, fontsize=8.5, ncol=2, loc='upper left', bbox_to_anchor=(0., 1.12))
        for ax in (nav_ax, dd_ax):
            _decorate(ax)
        _title(fig, 1, f'2015-01-01 / actual 2015-01-05 through {CUTOFF} | E starts 150k / NAV 1\n'
               'Original C OI risk tiers + short bottom 20% veto | external reserve R100 versus R150', reviewed)
        _footer(fig, 'Blue R100 overlays grey dashed R150 when account paths are equal; vertical marks show deposit days in both versions.')
        fig.tight_layout(rect=[.01, .14, .995, .90])
        figures[FIGURE_NAMES[0]] = fig
        for cohort, name in (('January', FIGURE_NAMES[1]), ('June', FIGURE_NAMES[2])):
            fig = _grid(si, curves, cohort, reviewed)
            created.append(fig)
            figures[name] = fig
        fig = _heatmaps(pi, reviewed)
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
