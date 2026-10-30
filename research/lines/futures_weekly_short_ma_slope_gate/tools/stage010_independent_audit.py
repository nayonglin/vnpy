"""Independent scalar audit of Stage010 saved ledgers; imports no projection/engine.

Only selected Stage009 sources are read. No financial replay, service, download,
production access or mutation of implementation/data is performed.
"""
from pathlib import Path
import hashlib
import json
import math
import statistics
import base64
import re
from html.parser import HTMLParser
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

LINE = Path(__file__).resolve().parents[1]
OUT = LINE / 'artifacts/stage010_off_account_nav'
OLD = LINE / 'artifacts/stage009_multistart'
INITIAL = 150000.0
LOCK = 'b4712560c72548106fb9e4273895e1bfc80c56a6813cdfe3d71b4190b5d5a424'
STARTS = [f'{y}-{m:02d}-01' for y in range(2015, 2027) for m in [1, 6]
          if y < 2026 or m == 1]
VARIANTS = ['A_idle', 'A_R', 'C_idle', 'C_R']
KEY = ['start', 'variant']
DAILY_KEY = KEY + ['date']


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images, self.options, self.rows, self.assets = [], [], [], []
        self.current_row = self.cell = None
        self.in_cell = False
        self.in_script = False
        self.scripts = []
        self.current_script = ''

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag == 'img':
            self.images.append(attr['src'])
        if tag == 'option':
            self.options.append(attr['value'])
        if tag in ['script', 'link', 'iframe', 'source', 'video', 'audio', 'object']:
            self.assets.extend(v for k, v in attrs if k in ['src', 'href', 'data'])
        if tag == 'script':
            self.in_script = True
            self.current_script = ''
        if tag == 'tr' and 'data-start' in attr:
            self.current_row = [attr['data-start'], []]
        if tag == 'td':
            self.in_cell = True
            self.cell = ''

    def handle_data(self, data):
        if self.in_cell:
            self.cell += data
        if self.in_script:
            self.current_script += data

    def handle_endtag(self, tag):
        if tag == 'td':
            assert self.current_row is not None
            self.current_row[1].append(self.cell)
            self.in_cell = False
        if tag == 'tr' and self.current_row is not None:
            self.rows.append(self.current_row)
            self.current_row = None
        if tag == 'script':
            self.scripts.append(self.current_script)
            self.in_script = False


def audit_display(directory):
    directory = Path(directory)
    receipt = json.loads((directory / 'delivery_receipt.json').read_text())
    lock = json.loads((OUT / 'data_manifest.json').read_text())['files_sha256']
    assert receipt['data_files_sha256'] == lock
    for category in ['figure_files_sha256', 'report_files_sha256']:
        for path, expected in receipt[category].items():
            assert Path(path).parent == directory
            assert digest(path) == expected, 'display file SHA ' + path
    assert len(receipt['figure_files_sha256']) == 5
    assert len(receipt['report_files_sha256']) == 2
    report = directory / 'Stage010_15万起点_场外补资净值报告.html'
    page = report.read_text()
    parser = ReportParser()
    parser.feed(page)
    assert not parser.assets and not re.search(r'url\s*\(', page), 'external runtime assets'
    assert len(parser.images) == 5
    for image, source in zip(parser.images, receipt['figure_files_sha256']):
        assert image.startswith('data:image/png;base64,')
        decoded = base64.b64decode(image.split(',', 1)[1], validate=True)
        assert hashlib.sha256(decoded).hexdigest() == digest(source), 'embedded PNG'
    assert parser.options == ['all'] + STARTS
    assert len(parser.rows) == 92
    summary = load('summary.csv')
    order = {variant: i for i, variant in enumerate(VARIANTS)}
    summary = summary.assign(_order=summary.variant.map(order)).sort_values(['start', '_order'])
    labels = {'A_idle': 'A原版', 'A_R': 'A＋场外补资', 'C_idle': 'C原版', 'C_R': 'C＋场外补资'}
    for (start, cells), row in zip(parser.rows, summary.itertuples()):
        assert start == row.start
        expected = [row.start + ('（观察）' if row.observation_only else ''), labels[row.variant],
            f'{row.account_end_equity:,.0f}', f'{row.account_growth_pct:+.2f}%',
            f'{row.balance_max_dd_pct:.2f}%', f'{row.balance_sharpe:.3f}',
            f'{row.real_trading_net_pnl:+,.0f}', f'{row.total_transferred:,.0f}',
            f'{row.off_account_reserve_end:,.0f}', f'{row.total_slippage:,.0f}',
            str(int(row.modeled_fill_count)), f'{row.round_win_rate_pct:.2f}%',
            f'{row.round_average_win:,.2f}', f'{row.round_average_loss_abs:,.2f}',
            f'{row.round_payoff_ratio:.3f}', f'{row.round_profit_factor:.3f}']
        assert cells == expected, 'HTML row values ' + str((start, row.variant))
    assert len(parser.scripts) == 1
    assert 'document.getElementById("startFilter").addEventListener("change"' in parser.scripts[0]
    assert 'r.hidden=this.value!=="all"&&r.dataset.start!==this.value' in parser.scripts[0]
    assert page.count('id="fig') == 5 and 'NO_PROMOTION' in page
    assert '账户增长、回撤、账户Sharpe均含入金影响' in page
    assert '净值＝交易账户权益÷150,000' in page
    return {'status': 'STATIC_OFFLINE_HTML_CHECKS_PASS',
            'figure_files_sha256': receipt['figure_files_sha256'],
            'report_files_sha256': receipt['report_files_sha256'],
            'receipt_sha256': digest(directory / 'delivery_receipt.json'),
            'checks': ['5 embedded PNG bytes match standalone figure SHA',
                       '92 rows x16 formatted source values and23 starts match summary',
                       'No external scripts/styles/iframes/runtime URL assets',
                       'One local filtering script binds actual start values',
                       'All display receipt SHA matches source data lock'],
            'browser_interaction_verified': False,
            'browser_interaction_limitation': 'Parent reports CUA URL safety rejects file://; no HTTP workaround attempted.'}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def same(left, right, label, allow_missing=False):
    a, b = np.asarray(left), np.asarray(right)
    if a.shape != b.shape:
        raise AssertionError(f'{label}: different shapes {a.shape} {b.shape}')
    if np.issubdtype(a.dtype, np.number) and np.issubdtype(b.dtype, np.number):
        if not np.allclose(a, b, rtol=1e-12, atol=1e-7, equal_nan=allow_missing):
            raise AssertionError(label)
    elif not ((a == b) | (pd.isna(a) & pd.isna(b) & allow_missing)).all():
        raise AssertionError(label)


def load(name, output=OUT):
    return pd.read_csv(output / name, float_precision='round_trip')


def scalar_metrics(group):
    """One-pass independent accounting, no calls to Stage010 implementation."""
    pnl = deposit = 0.0
    prior = highwater = INITIAL
    worst = 0.0
    returns, checks = [], []
    defined = True
    for row in group.itertuples():
        pnl += float(row.net_pnl)
        deposit += float(row.transfer_amount)
        equity = INITIAL + pnl + deposit
        highwater = max(highwater, equity)
        drawdown = 100.0 * (equity / highwater - 1.0)
        worst = min(worst, drawdown)
        if prior > 0 and math.isfinite(prior) and math.isfinite(equity):
            change = (equity - prior) / prior
            defined &= math.isfinite(change)
            returns.append(change)
        else:
            defined = False
        checks.append((INITIAL + pnl, equity, deposit, INITIAL - deposit,
                       equity / INITIAL, drawdown))
        prior = equity
    if defined and len(returns) > 1:
        std = statistics.stdev(returns)
        sharpe = statistics.mean(returns) / std * math.sqrt(252) if std > 0 else 0.0
    else:
        sharpe = 0.0
    return dict(account_end_equity=equity, account_growth_pct=(equity / INITIAL - 1) * 100,
                balance_max_dd_pct=worst, balance_sharpe=sharpe,
                balance_returns_defined=defined, real_trading_net_pnl=pnl,
                total_transferred=deposit, off_account_reserve_end=INITIAL - deposit,
                total_slippage=math.fsum(group.slippage),
                total_commission=math.fsum(group.commission),
                modeled_fill_count=sum(group.trade_count),
                transfer_event_days=sum(group.transfer_amount > 0),
                nonpositive_trading_equity_days=sum(group.trading_account_equity <= 0),
                initial_trading_capital=INITIAL, trading_days=len(group)), checks


def audit():
    data_lock = json.loads((OUT / 'data_manifest.json').read_text())['files_sha256']
    for path, expected in data_lock.items():
        assert digest(path) == expected, f'data lock: {path}'
    projection = json.loads((OUT / 'projection.json').read_text())
    manifest = LINE / 'stages/stage009_delivery_manifest.json'
    assert digest(manifest) == LOCK, 'source admission manifest'
    source_manifest = json.loads(manifest.read_text())
    assert source_manifest['accepted'] is True
    source_hashes = projection['source_files_sha256']
    selected = [manifest, OLD / 'all_daily.csv', OLD / 'summary.csv', OLD / 'reserve_events.csv',
                LINE / 'stages/stage009_independent_final.json', LINE / 'stages/stage009_freeze.json']
    assert set(source_hashes) == {str(path) for path in selected}
    for path in selected:
        expected = LOCK if path == manifest else source_manifest['files_sha256'][str(path)]
        assert source_hashes[str(path)] == expected and digest(path) == expected, str(path)
    old_review = json.loads((LINE / 'stages/stage009_independent_final.json').read_text())
    assert old_review['status'] == 'PASS_WITH_LIMITATIONS' and not old_review['failures']
    for key in ['financial_replays', 'market_downloads', 'production_accesses']:
        assert projection[key] == 0
    assert projection['strategy_parameters_changed'] is False
    assert projection['transaction_ledgers_changed'] is False
    assert projection['promotion_decision'] == 'NO_PROMOTION'
    assert projection['projection_source_sha256'] == digest(LINE / 'tools/stage010_account_nav.py')
    s, p, d = load('summary.csv'), load('paired.csv'), load('daily.csv')
    old_s = load('summary.csv', OLD)
    old_d = pd.read_csv(OLD / 'all_daily.csv', usecols=list(d.columns[:-2]), float_precision='round_trip')
    ev = load('reserve_events.csv', OLD)
    expected = {(start, variant) for start in STARTS for variant in VARIANTS}
    assert len(s) == 92 and len(p) == 46 and len(d) == 141996
    assert not s.duplicated(KEY).any() and set(zip(s.start, s.variant)) == expected
    assert not d.duplicated(DAILY_KEY).any() and set(zip(d.start, d.variant)) == expected
    assert not p.duplicated(['start', 'arm']).any()
    assert set(zip(p.start, p.arm)) == {(start, arm) for start in STARTS for arm in 'AC'}
    assert int(s.observation_only.sum()) == 4 and int(p.observation_only.sum()) == 2
    ds = d.sort_values(DAILY_KEY).reset_index(drop=True)
    os = old_d.sort_values(DAILY_KEY).reset_index(drop=True)
    for field in old_d.columns:
        same(ds[field], os[field], 'unchanged daily ' + field)
    si, oi = s.set_index(KEY), old_s.set_index(KEY)
    round_fields = [c for c in old_s.columns if c.startswith('round_') or c == 'open_round_net_mtm']
    for field in round_fields:
        same(si.sort_index()[field], oi.sort_index()[field], 'unchanged rounds ' + field, True)
    groups = {key: group.sort_values('date').reset_index(drop=True)
              for key, group in d.groupby(KEY)}
    event_map = ev.groupby(DAILY_KEY).transfer_amount.sum().to_dict()
    recomputed, calendars, endpoints = {}, {}, {}
    for key, group in groups.items():
        start, variant = key
        summary = si.loc[key]
        source = oi.loc[key]
        assert summary.arm == variant[0]
        assert summary.funding_mode == ('external_topup' if variant.endswith('_R') else 'original')
        assert bool(summary.observation_only) == (start == '2026-01-01')
        assert group.date.iloc[0] == source.actual_start == summary.actual_start
        assert group.date.iloc[-1] == source.actual_end == summary.actual_end == '2026-10-29'
        assert len(group) == source.trading_days == summary.trading_days
        calendar = tuple(group.date)
        if start in calendars:
            assert calendars[start] == calendar
        calendars[start] = calendar
        endpoints[start] = {'actual_start': calendar[0], 'cutoff': calendar[-1], 'trading_days': len(group)}
        assert group.trading_account_equity.iloc[0] == INITIAL
        assert group.account_nav.iloc[0] == 1 and group.net_pnl.iloc[0] == 0
        assert group.transfer_amount.iloc[0] == group.cumulative_transfer.iloc[0] == 0
        assert group.transfer_amount.ge(0).all() and group.reserve_balance.between(-1e-7, INITIAL + 1e-7).all()
        if variant.endswith('_idle'):
            assert group.cumulative_transfer.eq(0).all() and group.reserve_balance.eq(INITIAL).all()
        amounts = [event_map.get((start, variant, date), 0.0) for date in group.date]
        same(group.transfer_amount, amounts, 'event daily amounts ' + str(key))
        metrics, checks = scalar_metrics(group)
        recomputed[key] = metrics
        fields = ['raw_account_equity', 'trading_account_equity', 'cumulative_transfer',
                  'reserve_balance', 'account_nav', 'balance_drawdown_pct']
        for j, field in enumerate(fields):
            same(group[field], [row[j] for row in checks], 'scalar daily ' + field + str(key))
        same(group.total_account_equity, group.trading_account_equity + group.reserve_balance,
             'legacy wealth witness ' + str(key))
        for field, value in metrics.items():
            same(summary[field], value, 'scalar summary ' + field + str(key))
        for new, old in [('account_end_equity', 'trading_end_equity'), ('real_trading_net_pnl', 'net_pnl'),
                         ('total_transferred', 'total_transferred'), ('off_account_reserve_end', 'reserve_end_balance'),
                         ('total_slippage', 'total_slippage'), ('total_commission', 'total_commission'),
                         ('modeled_fill_count', 'modeled_fill_count')]:
            same(summary[new], source[old], 'source summary ' + new + str(key))
    assert set(event_map).issubset(set(zip(d.start, d.variant, d.date)))
    for row in p.itertuples():
        original, funded = recomputed[(row.start, row.arm + '_idle')], recomputed[(row.start, row.arm + '_R')]
        assert row.cohort == ('January' if row.start[5:7] == '01' else 'June')
        assert row.observation_only == (row.start == '2026-01-01')
        for pair_field, field in [('delta_account_growth_pp', 'account_growth_pct'),
                                  ('delta_balance_max_dd_pp', 'balance_max_dd_pct'),
                                  ('delta_balance_sharpe', 'balance_sharpe'),
                                  ('delta_real_trading_net_pnl', 'real_trading_net_pnl'),
                                  ('delta_account_end_equity', 'account_end_equity')]:
            same(getattr(row, pair_field), funded[field] - original[field], pair_field)
        same(row.external_deposits, funded['total_transferred'], 'paired deposits')
        same(row.delta_account_end_equity, row.delta_real_trading_net_pnl + row.external_deposits,
             'paired account-PnL-deposit bridge')
    c24 = si.loc[('2024-06-01', 'C_R')]
    same(c24.real_trading_net_pnl, -8560, 'C2024June actual loss')
    same(c24.total_transferred, 31660, 'C2024June deposits')
    same(c24.account_end_equity, 173100, 'C2024June balance')
    same(c24.account_growth_pct, 15.4, 'C2024June cashflow growth')
    c26 = si.loc[('2026-01-01', 'C_R')]
    c26_original = si.loc[('2026-01-01', 'C_idle')]
    same(c26.total_transferred, 720, 'C2026 deposit')
    same(c26.real_trading_net_pnl, c26_original.real_trading_net_pnl, 'C2026 unchanged actual PnL')
    same(c26.account_end_equity - c26_original.account_end_equity, 720, 'C2026 deposit-only balance difference')
    for path, expected_hash in data_lock.items():
        assert digest(path) == expected_hash, 'data changed during audit ' + path
    for path, expected_hash in source_hashes.items():
        assert digest(path) == expected_hash, 'source changed during audit ' + path
    return {'status': 'NUMERIC_CHECKS_PASS_VISUAL_REVIEW_PENDING',
            'audited_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
            'financial_replays': 0, 'market_downloads': 0, 'production_accesses': 0,
            'scope': {'starts': len(STARTS), 'variant_windows': len(s), 'pairs': len(p),
                      'daily_points': len(d), 'cutoff': '2026-10-29', 'endpoints': endpoints},
            'source_files_sha256': source_hashes, 'data_files_sha256': data_lock,
            'independent_checks': ['6 selected source SHA and accepted Stage009 identity',
              'every preserved daily source column and every round statistic including missing values',
              'all92 scalar running PnL/deposits/account equity/NAV/initial highwater DD',
              'all92 scalar simple change Sharpe using statistics.stdev ddof1 sqrt252',
              'all92 summary costs/fills/events/endpoints/calendars/observation flags',
              'all46 paired metrics and account-difference=Pnl-difference+deposits',
              'C2024June loss despite positive deposit-inclusive account growth',
              'C2026Jan 720 deposit changes only account balance, actual PnL identical'],
            'counterexamples': {'C_2024_June': {k: float(c24[k]) for k in ['real_trading_net_pnl', 'total_transferred', 'account_end_equity', 'account_growth_pct']},
                               'C_2026_January': {'deposit': float(c26.total_transferred),
                                                  'same_actual_PnL': float(c26.real_trading_net_pnl)}},
            'failures': []}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--display', type=Path)
    args = parser.parse_args()
    result = audit()
    if args.display:
        result['display'] = audit_display(args.display)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(encoded)
    print(json.dumps({key: result[key] for key in ['status', 'scope', 'counterexamples', 'failures']}, ensure_ascii=False, indent=2))
