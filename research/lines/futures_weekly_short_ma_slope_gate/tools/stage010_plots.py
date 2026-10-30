"""Pure five-figure display of the already-completed Stage009 trading accounts.

External funds enter balance NAV only after transfer to the trading account.
This renderer does not run a financial engine, read sources, publish files, or
interpret cashflow-inclusive balance statistics as strategy performance.
"""
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
EXPECTED_DAILY_POINTS = 141996
# Frozen window boundaries/counts from the completed Stage009 source; these
# constrain display scope, rather than relying on a self-consistent summary.
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
VARIANTS = ('A_R', 'A_idle', 'C_R', 'C_idle')
FIGURE_NAMES = ('01_account_nav_drawdown_2015.png',
                '02_january_account_nav.png', '03_june_account_nav.png',
                '04_account_cashflow_deltas.png',
                '05_trading_pnl_and_deposit_overview.png')
COLORS = {'A_R': '#2168ad', 'A_idle': '#7f8a96',
          'C_R': '#b5224a', 'C_idle': '#cb941b'}
LABELS = {'A_R': 'A + external deposits', 'A_idle': 'A original',
          'C_R': 'C + external deposits', 'C_idle': 'C original'}
SHORT_LABELS = {'A_R': 'A + deposits', 'A_idle': 'A original',
                'C_R': 'C + deposits', 'C_idle': 'C original'}
FOOTER = ('External reserve excluded; deposits INCLUDED in balance NAV;\n'
          'account growth/DD/Sharpe include cashflow and are not flow-adjusted strategy performance.')
SUMMARY_FIELDS = {
    'start', 'variant', 'arm', 'funding_mode', 'actual_start', 'actual_end',
    'trading_days', 'observation_only', 'initial_trading_capital',
    'account_end_equity', 'account_growth_pct', 'balance_max_dd_pct',
    'balance_sharpe', 'balance_returns_defined', 'real_trading_net_pnl',
    'total_transferred', 'off_account_reserve_end', 'total_slippage',
    'total_commission', 'modeled_fill_count', 'transfer_event_days',
    'nonpositive_trading_equity_days'}
PAIR_FIELDS = {
    'start', 'arm', 'cohort', 'observation_only', 'delta_account_growth_pp',
    'delta_balance_max_dd_pp', 'delta_balance_sharpe',
    'delta_real_trading_net_pnl', 'delta_account_end_equity', 'external_deposits'}
DAILY_FIELDS = {
    'start', 'variant', 'date', 'raw_account_equity', 'net_pnl',
    'trading_account_equity', 'reserve_balance', 'cumulative_transfer',
    'transfer_amount', 'account_nav', 'balance_drawdown_pct',
    'total_account_equity', 'slippage', 'commission', 'trade_count'}


def _require(condition, label):
    if not condition:
        raise ValueError('stage010_plots:' + label)


def _near(left, right):
    return np.allclose(left, right, rtol=1e-10, atol=1e-6, equal_nan=False)


def _boolean(value):
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if value == 'True':
        return True
    if value == 'False':
        return False
    raise ValueError('stage010_plots:explicit_boolean_required')


def _dates(values):
    result = pd.to_datetime(values, errors='raise')
    _require(not result.isna().any(), 'missing_date')
    _require((result == result.dt.normalize()).all(), 'daily_dates_no_intraday_time')
    return result.dt.strftime('%Y-%m-%d')


def balance_sharpe(equity):
    """Cashflow-inclusive balance statistic, with explicit denominator validity."""
    equity = np.asarray(equity, dtype=float)
    previous = np.r_[INITIAL_TRADING_CAPITAL, equity[:-1]]
    defined = bool(len(equity) and np.isfinite(equity).all() and
                   np.isfinite(previous).all() and (previous > 0).all())
    if not defined:
        return 0., False
    returns = (equity - previous) / previous
    if not np.isfinite(returns).all():
        return 0., False
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.
    value = float(returns.mean() / std * np.sqrt(252)) if std > 0 else 0.
    return value, True


def validate_inputs(summary, paired, daily):
    """Validate complete scope and every displayed metric before figure creation.

    Source hashes and the interior exchange calendar are admitted by the caller.
    Here, frozen per-window counts/endpoints, cross-variant calendars, balances,
    costs, transfers and all displayed statistics must reconcile independently.
    """
    for name, frame, fields in (('summary', summary, SUMMARY_FIELDS),
                                ('paired', paired, PAIR_FIELDS),
                                ('daily', daily, DAILY_FIELDS)):
        _require(isinstance(frame, pd.DataFrame) and fields.issubset(frame.columns),
                 'missing_' + name + '_columns')
    s, p, d = summary.copy(), paired.copy(), daily.copy()
    forbidden = {'vote_eligible', 'equity_gate', 'dd_gate', 'sharpe_gate', 'three_gate_pass'}
    _require(not forbidden.intersection(p.columns), 'no_strategy_promotion_gates')
    expected = {(start, variant) for start in STARTS for variant in VARIANTS}
    keys = list(zip(s.start, s.variant))
    _require(len(keys) == 92 and len(set(keys)) == 92 and set(keys) == expected,
             'exact92_summary')
    pair_keys = list(zip(p.start, p.arm))
    _require(len(pair_keys) == 46 and len(set(pair_keys)) == 46 and
             set(pair_keys) == {(start, arm) for start in STARTS for arm in ('A', 'C')},
             'exact46_pairs')
    _require(len(d) == EXPECTED_DAILY_POINTS, 'complete141996_daily_points')
    _require(set(zip(d.start, d.variant)) == expected, 'exact92_daily_groups')
    s['observation_only'] = s.observation_only.map(_boolean)
    s['balance_returns_defined'] = s.balance_returns_defined.map(_boolean)
    p['observation_only'] = p.observation_only.map(_boolean)
    s['actual_start'] = _dates(s.actual_start)
    s['actual_end'] = _dates(s.actual_end)
    d['date'] = _dates(d.date)
    _require(not d.duplicated(['start', 'variant', 'date']).any(), 'unique_daily_dates')
    string_summary = {'start', 'variant', 'arm', 'funding_mode', 'actual_start',
                      'actual_end', 'observation_only', 'balance_returns_defined'}
    numeric_summary = SUMMARY_FIELDS - string_summary
    numeric_pair = PAIR_FIELDS - {'start', 'arm', 'cohort', 'observation_only'}
    numeric_daily = DAILY_FIELDS - {'start', 'variant', 'date'}
    for frame, fields in ((s, numeric_summary), (p, numeric_pair), (d, numeric_daily)):
        for field in fields:
            frame[field] = pd.to_numeric(frame[field], errors='raise')
            _require(np.isfinite(frame[field].to_numpy(float)).all(), 'finite_' + field)
    for frame, fields in ((s, ('trading_days', 'modeled_fill_count', 'transfer_event_days',
                               'nonpositive_trading_equity_days')), (d, ('trade_count',))):
        for field in fields:
            _require((frame[field] >= 0).all() and
                     (frame[field] == np.floor(frame[field])).all(),
                     'nonnegative_integer_' + field)
    for frame, fields in ((s, ('total_slippage', 'total_commission')),
                          (d, ('slippage', 'commission', 'transfer_amount'))):
        for field in fields:
            _require((frame[field] >= 0).all(), 'nonnegative_' + field)
    si, pi = s.set_index(['start', 'variant']), p.set_index(['start', 'arm'])
    curves, calendar = {}, {}
    for key, group in d.groupby(['start', 'variant'], sort=False):
        start, variant = key
        meta = si.loc[key]
        g = group.sort_values('date').reset_index(drop=True)
        funded = variant.endswith('_R')
        observation = start == '2026-01-01'
        actual, expected_count = WINDOW_SCOPE[start]
        _require(meta.arm == variant[0] and
                 meta.funding_mode == ('external_topup' if funded else 'original'),
                 'variant_arm_funding_identity')
        _require(bool(meta.observation_only) == observation, 'summary_observation_scope')
        _require(meta.actual_start == actual and meta.actual_end == CUTOFF and
                 int(meta.trading_days) == expected_count, 'frozen_summary_window')
        _require(len(g) == expected_count and g.date.iloc[0] == actual and
                 g.date.iloc[-1] == CUTOFF, 'complete_daily_endpoints_count')
        dates = tuple(g.date)
        if start in calendar:
            _require(calendar[start] == dates, 'same_start_four_variant_calendar')
        else:
            calendar[start] = dates
        equity = g.trading_account_equity.to_numpy(float)
        raw = g.raw_account_equity.to_numpy(float)
        transfer = g.cumulative_transfer.to_numpy(float)
        reserve = g.reserve_balance.to_numpy(float)
        pnl = g.net_pnl.to_numpy(float)
        _require(_near(meta.initial_trading_capital, INITIAL_TRADING_CAPITAL),
                 'initial_trading_capital150k')
        _require(_near(raw, INITIAL_TRADING_CAPITAL + np.cumsum(pnl)), 'raw_PnL_bridge')
        _require(_near(transfer, g.transfer_amount.cumsum().to_numpy(float)),
                 'daily_transfer_cumulative_bridge')
        _require(_near(equity, raw + transfer), 'deposits_INCLUDED_in_account_equity')
        _require(_near(reserve + transfer, EXTERNAL_FUNDING_LIMIT) and
                 (reserve >= -1e-6).all() and (reserve <= EXTERNAL_FUNDING_LIMIT + 1e-6).all(),
                 'external_funding_conservation_and_limit')
        # Total wealth exists solely as a conservation witness, never a curve.
        _require(_near(g.total_account_equity.to_numpy(float), equity + reserve),
                 'total_wealth_conservation_only')
        if not funded:
            _require(_near(transfer, 0.) and _near(g.transfer_amount, 0.) and
                     _near(reserve, EXTERNAL_FUNDING_LIMIT), 'original_no_external_deposit')
        _require(_near(equity[0], INITIAL_TRADING_CAPITAL) and _near(pnl[0], 0.) and
                 _near(transfer[0], 0.), 'fresh150k_account_start')
        drawdown = (equity / np.maximum.accumulate(np.r_[INITIAL_TRADING_CAPITAL, equity])[1:] - 1) * 100
        _require(_near(g.account_nav.to_numpy(float), equity / INITIAL_TRADING_CAPITAL),
                 'account_NAV150k_external_reserve_excluded')
        _require(_near(g.balance_drawdown_pct.to_numpy(float), drawdown),
                 'account_initial_highwater_drawdown')
        sharpe, defined = balance_sharpe(equity)
        _require(bool(meta.balance_returns_defined) == defined, 'balance_returns_defined')
        calculated = dict(
            account_end_equity=equity[-1],
            account_growth_pct=(equity[-1] / INITIAL_TRADING_CAPITAL - 1) * 100,
            balance_max_dd_pct=float(drawdown.min()), balance_sharpe=sharpe,
            real_trading_net_pnl=float(pnl.sum()), total_transferred=transfer[-1],
            off_account_reserve_end=reserve[-1], total_slippage=float(g.slippage.sum()),
            total_commission=float(g.commission.sum()), modeled_fill_count=int(g.trade_count.sum()),
            transfer_event_days=int(g.transfer_amount.gt(0).sum()),
            nonpositive_trading_equity_days=int((equity <= 0).sum()))
        for field, value in calculated.items():
            _require(_near(float(meta[field]), value), 'summary_daily_metric_' + field)
        g['plot_date'] = pd.to_datetime(g.date)
        curves[key] = g
    for (start, arm), pair in pi.iterrows():
        _require(bool(pair.observation_only) == (start == '2026-01-01') and
                 pair.cohort == ('January' if start[5:7] == '01' else 'June'),
                 'paired_observation_cohort_scope')
        original, funded = si.loc[(start, arm + '_idle')], si.loc[(start, arm + '_R')]
        deltas = dict(
            delta_account_growth_pp=funded.account_growth_pct - original.account_growth_pct,
            delta_balance_max_dd_pp=funded.balance_max_dd_pct - original.balance_max_dd_pct,
            delta_balance_sharpe=funded.balance_sharpe - original.balance_sharpe,
            delta_real_trading_net_pnl=funded.real_trading_net_pnl - original.real_trading_net_pnl,
            delta_account_end_equity=funded.account_end_equity - original.account_end_equity,
            external_deposits=funded.total_transferred)
        for field, value in deltas.items():
            _require(_near(float(pair[field]), float(value)), 'paired_metric_' + field)
    _require(int(s.observation_only.sum()) == 4 and int(p.observation_only.sum()) == 2,
             'one_observation_start_four_variants_two_pairs')
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
    fig.suptitle(f'STAGE010 {number}/5 | {state} | NO_PROMOTION\n' + description,
                 fontsize=11, fontweight='bold', y=.984)


def _footer(fig, extra):
    fig.text(.03, .012, FOOTER + '\n' + extra, fontsize=7.5,
             color='#505c6e', va='bottom')


def _curve(ax, frame, variant, field='account_nav', markers=False):
    funded = variant.endswith('_R')
    ax.plot(frame.plot_date, frame[field], color=COLORS[variant],
            lw=1.5 if funded else 1.15, ls='-' if funded else '--',
            label=LABELS[variant])
    if markers and funded:
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
    fig = _figure((15.2, 11.5))
    axes = fig.subplots(4, 3)
    for i, start in enumerate(starts):
        ax = axes.flat[i]
        meta = si.loc[(start, 'A_R')]
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
           f'{cohort} independent starts to {CUTOFF} | every account starts at CNY 150,000 / NAV 1\n'
           'A: original 19, no price filter | C: short bottom 20% veto | add-on / long-price / MA-slope gates OFF', reviewed)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=4, frameon=False, fontsize=8,
               loc='upper center', bbox_to_anchor=(.5, .912))
    _footer(fig, '2026 Jan is observation only. Windows overlap and have different lengths; no promotion votes or OOS independence claim.')
    fig.tight_layout(rect=[.012, .07, .995, .887])
    return fig


def _heatmaps(pi, si, reviewed):
    fig = _figure((15.2, 11.8))
    axes = fig.subplots(2, 3)
    metrics = [('delta_account_growth_pp', 'Account growth delta (pp)'),
               ('delta_balance_max_dd_pp', 'Balance max DD delta (pp)'),
               ('delta_balance_sharpe', 'Balance Sharpe delta')]
    labels = [start + (' * OBS' if start == '2026-01-01' else '') for start in STARTS]
    for j, (field, title) in enumerate(metrics):
        all_values = pi[field].to_numpy(float)
        bound = max(float(np.abs(all_values).max()), .001)
        for i, arm in enumerate(('A', 'C')):
            ax = axes[i, j]
            values = np.array([pi.loc[(start, arm), field] for start in STARTS], float)
            im = ax.imshow(values.reshape(-1, 1), aspect='auto', cmap='RdBu_r',
                           vmin=-bound, vmax=bound)
            ax.set_title(f'{arm} + deposits minus {arm} original\n{title}', fontsize=9.5)
            ax.set_xticks([])
            ax.set_yticks(np.arange(len(STARTS)), labels, fontsize=7)
            for k, value in enumerate(values):
                valid = field != 'delta_balance_sharpe' or (
                    bool(si.loc[(STARTS[k], arm + '_R'), 'balance_returns_defined']) and
                    bool(si.loc[(STARTS[k], arm + '_idle'), 'balance_returns_defined']))
                rgba = im.cmap(im.norm(value))
                lum = .2126 * rgba[0] + .7152 * rgba[1] + .0722 * rgba[2]
                text = (f'{value:+.3f}' if field == 'delta_balance_sharpe' else f'{value:+.2f}') if valid else 'N/A'
                ax.text(0, k, text, ha='center', va='center', fontsize=7,
                        color='white' if lum < .5 else '#17202a')
            fig.colorbar(im, ax=ax, fraction=.045, pad=.025)
    _title(fig, 4, 'Cashflow-inclusive account deltas across all 23 starts\n'
           'Positive DD delta = shallower balance drawdown; color shows sign, not an alpha or promotion verdict', reviewed)
    _footer(fig, '* 2026 Jan is observation only. Each metric shares an A/C scale. Undefined balance Sharpe is labeled N/A.')
    fig.tight_layout(rect=[.005, .07, .995, .905])
    return fig


def _overview(si, reviewed):
    fig = _figure((15.2, 10.8))
    axes = fig.subplots(2, 2)
    ax = axes[0, 0]
    width = .18
    x = np.arange(2)
    for i, variant in enumerate(VARIANTS):
        counts = []
        for month in ('01', '06'):
            starts = [start for start in STARTS if start != '2026-01-01' and start[5:7] == month]
            counts.append(sum(si.loc[(start, variant), 'real_trading_net_pnl'] < 0 for start in starts))
        bars = ax.bar(x + (i - 1.5) * width, counts, width,
                      color=COLORS[variant], label=SHORT_LABELS[variant])
        for bar, count in zip(bars, counts):
            ax.text(bar.get_x() + bar.get_width() / 2, count + .13, str(count),
                    ha='center', fontsize=8)
    ax.set_xticks(x, ['January (11 windows)', 'June (11 windows)'])
    ax.set_ylim(0, 12.8)
    ax.set_ylabel('Windows with real trading net PnL < 0')
    ax.set_title('Actual trading losses: external deposits are excluded', fontsize=10)
    ax.legend(frameon=False, fontsize=7.5, ncol=2)
    _decorate(ax)
    ax = axes[0, 1]
    groups = [(arm, cohort) for arm in ('A', 'C') for cohort in ('January', 'June')]
    consumption = []
    for arm, cohort in groups:
        starts = [start for start in STARTS if start != '2026-01-01' and
                  (start[5:7] == '01') == (cohort == 'January')]
        consumption.append([si.loc[(start, arm + '_R'), 'total_transferred'] / 1000 for start in starts])
    boxes = ax.boxplot(consumption, positions=np.arange(1, 5), patch_artist=True,
                       widths=.5, showfliers=False)
    for i, (patch, values) in enumerate(zip(boxes['boxes'], consumption)):
        color = COLORS[groups[i][0] + '_R']
        patch.set_facecolor(color)
        patch.set_alpha(.22)
        ax.scatter(np.full(len(values), i + 1) + np.linspace(-.12, .12, len(values)),
                   values, s=17, color=color, zorder=3)
    ax.set_xticks(np.arange(1, 5), [f'{arm} {cohort}\n11 windows' for arm, cohort in groups])
    ax.set_ylim(-5, 160)
    ax.set_ylabel('External deposits (CNY thousands)')
    ax.set_title('Funding consumed: each completed window retained', fontsize=10)
    _decorate(ax)
    ax = axes[1, 0]
    ax.axis('off')
    rows = []
    for variant in VARIANTS:
        meta = si.loc[('2015-01-01', variant)]
        rows.append([SHORT_LABELS[variant], '150,000', f'{meta.real_trading_net_pnl:,.0f}',
                     f'{meta.total_transferred:,.0f}', f'{meta.account_end_equity:,.0f}'])
    table = ax.table(cellText=rows, colLabels=['Variant', 'Initial', '+ Real PnL', '+ Deposits', '= Balance'],
                     loc='center', cellLoc='center', colWidths=[.23, .16, .22, .17, .22])
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1., 1.7)
    ax.set_title('2015 account balance bridge (CNY): 150k + PnL + deposits',
                 fontsize=10, fontweight='bold')
    ax.text(.01, .12, 'Only real trading PnL is generated by trading.\n'
            'Deposits raise account balance; untransferred funds remain outside.',
            transform=ax.transAxes, fontsize=8, color='#505c6e', va='top')
    ax = axes[1, 1]
    ax.axis('off')
    rows = []
    for variant in VARIANTS:
        meta = si.loc[('2026-01-01', variant)]
        sharpe = f'{meta.balance_sharpe:.3f}' if meta.balance_returns_defined else 'N/A'
        rows.append([SHORT_LABELS[variant], f'{meta.account_growth_pct:+.2f}%',
                     f'{meta.balance_max_dd_pct:.2f}%', sharpe,
                     f'{meta.real_trading_net_pnl / 1000:+.1f}', f'{meta.total_transferred / 1000:.1f}'])
    table = ax.table(cellText=rows, colLabels=['Variant', 'Acct growth', 'Bal DD', 'Bal Sharpe', 'PnL k', 'Deposit k'],
                     loc='center', cellLoc='center', colWidths=[.23, .18, .15, .16, .14, .14])
    table.auto_set_font_size(False)
    table.set_fontsize(7.5)
    table.scale(1., 1.7)
    ax.set_title('2026-01-01: <1 year OBSERVATION ONLY', fontsize=10, fontweight='bold')
    ax.text(.01, .12, 'No promotion votes. January 11 + June 11 completed windows per arm.\n'
            'Balance growth, DD and Sharpe include external cash inflows.',
            transform=ax.transAxes, fontsize=8, color='#505c6e', va='top')
    _title(fig, 5, 'Trading outcomes, external funding use and account balance reconciliation\n'
           '92 variant-windows | all starts use CNY 150,000 trading principal', reviewed)
    _footer(fig, 'Completed source replay reused; this is a display correction. Inherited data/execution/cost limits remain; NO_PROMOTION.')
    fig.tight_layout(rect=[.01, .075, .995, .91])
    return fig


def render_five(summary: pd.DataFrame, paired: pd.DataFrame, daily: pd.DataFrame,
                reviewed=False) -> dict[str, Figure]:
    """Return five unsaved figures; caller owns output, source admission and review."""
    _require(type(reviewed) is bool, 'explicit_reviewed_boolean')
    si, pi, curves = validate_inputs(summary, paired, daily)
    figures = {}
    created = []
    try:
        fig = _figure((13.8, 8.5))
        created.append(fig)
        nav_ax, dd_ax = fig.subplots(2, 1, sharex=True,
                                     gridspec_kw={'height_ratios': [2, 1]})
        for variant in VARIANTS:
            frame = curves[('2015-01-01', variant)]
            _curve(nav_ax, frame, variant, markers=True)
            _curve(dd_ax, frame, variant, 'balance_drawdown_pct')
        nav_ax.axhline(1., color='#bec5ce', lw=.7, ls=':')
        dd_ax.axhline(0., color='#bec5ce', lw=.7, ls=':')
        nav_ax.set_ylabel('Account NAV = trading balance / 150,000')
        dd_ax.set_ylabel('Balance drawdown (%)')
        dd_ax.set_xlabel('Exchange trading date')
        nav_ax.legend(frameon=False, fontsize=8.5, ncol=2, loc='upper left')
        for ax in (nav_ax, dd_ax):
            _decorate(ax)
        _title(fig, 1, f'Full start 2015-01-01 / actual 2015-01-05 to {CUTOFF} | initial CNY 150,000 / NAV 1\n'
               'A: original 19, no price filter | C: short bottom 20% veto | add-on / long-price / MA-slope gates OFF', reviewed)
        _footer(fig, 'Short vertical marks on funded NAV curves show deposit days. Linear axes retain negative balances if present.')
        fig.tight_layout(rect=[.01, .09, .995, .91])
        figures[FIGURE_NAMES[0]] = fig
        for cohort, name in (('January', FIGURE_NAMES[1]), ('June', FIGURE_NAMES[2])):
            fig = _grid(si, curves, cohort, reviewed)
            created.append(fig)
            figures[name] = fig
        fig = _heatmaps(pi, si, reviewed)
        created.append(fig)
        figures[FIGURE_NAMES[3]] = fig
        fig = _overview(si, reviewed)
        created.append(fig)
        figures[FIGURE_NAMES[4]] = fig
        return figures
    except Exception:
        for fig in created:
            fig.clear()
        raise
