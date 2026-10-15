"""Read-only Stage246 frozen-source adapter to the pinned Stage038 renderer.

No strategy imports, replay, downloads, or broker connections. The chart functions
are loaded by AST, as in the existing stock recap adapter; their implementation
is not copied. Outputs remain in this research line per AGENTS.md.
"""
from __future__ import annotations

import argparse
import ast
from dataclasses import asdict
from datetime import datetime
import hashlib
import html
import json
import math
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parents[4]
LINE = ROOT / 'research/lines/futures_trend_rollover_shape_same_volume'
SOURCE_ROOT = Path('/Users/mac/.codex/worktrees/formal-2020-replay/fian')
RUN_REL = Path('research/lines/futures_trend_rollover_shape_same_volume/outputs/stage246_2020_20261014/replay_round3')
CANONICAL = ROOT / 'research/lines/futures_trend_winner_trade_forensics/tools/stage038_c9_15w_big_winner_multiscale_html.py'
RENDERER_SHA = '613672a4cc91493ba17dc055542e4b4172349de210ff932530caf04ce36bb93a'
FUNCTIONS = {'_json_safe', '_date_index', '_window_dates', '_context_daily',
             '_weekly_from_daily', '_monthly_from_daily', '_trading_day_bars_from_daily',
             '_monthly_window', '_add_moving_averages', '_period_coordinates', '_records', '_html'}
REQUIRED = ['metrics.json', 'daily.csv', 'trades.csv', 'effective_parameters.json',
            'run_provenance.json', 'input_manifest.json', 'validation_report.json',
            'trade_outcomes_summary.json', 'trade_outcomes_complete_cycles.csv',
            'trade_outcomes_fifo_matches.csv', 'annual_attribution.csv']


def sha(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def close(a: float, b: float, label: str) -> None:
    if not math.isfinite(float(a)) or not math.isfinite(float(b)) or not math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-6):
        raise ValueError(f'{label}: {a} != {b}')


def require_evidence(run: Path) -> None:
    missing = [name for name in REQUIRED if not (run / name).is_file()]
    if missing:
        raise ValueError(f'Incomplete frozen bundle: {missing}')


def require_closed(outcomes: dict) -> None:
    if outcomes.get('unclosed_cycle_count') != 0 or outcomes.get('unclosed_abs_contracts') != 0:
        raise ValueError('Residual open positions: complete-cycle adapter requires a closed ledger')


def validate_output(output: Path, allowed: Path = LINE / 'outputs') -> Path:
    output = output.resolve()
    if output.parent != allowed.resolve():
        raise ValueError('Output must be a new direct child of this research line')
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    return output


def load_renderer(extra: dict) -> dict:
    if sha(CANONICAL) != RENDERER_SHA:
        raise ValueError('Canonical renderer changed: review before updating pin')
    nodes = [node for node in ast.parse(CANONICAL.read_text()).body
             if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS]
    if {node.name for node in nodes} != FUNCTIONS:
        raise ValueError('Incomplete canonical renderer')
    namespace = dict(pd=pd, np=np, math=math, json=json, html=html, Any=Any,
                     datetime=datetime, get_plotlyjs=get_plotlyjs, MA_PERIODS=(5,10,20,40),
                     MONTHLY_PRE=10, MONTHLY_POST=10, DAILY_PRE=300, DAILY_POST=50,
                     INTRADAY_PRE=5, INTRADAY_POST=5, WEEKLY_MA_WARMUP_WEEKS=45,
                     MONTHLY_MA_WARMUP_MONTHS=45, TRADING_DAY_MA_WARMUP_DAYS=1230,
                     OFFICIAL_LIVE_ALIAS='Stage037 C9/15万正式物料历史回测',
                     OFFICIAL_LIVE_VERSION='ai_top10_plus_fu_official_live_v1')
    namespace.update(extra)
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), *nodes], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(CANONICAL), 'exec'), namespace)
    return namespace


def verify_source(root: Path, run: Path) -> tuple:
    require_evidence(run)
    metrics, outcomes, provenance, inputs = [read(run / name) for name in
        ['metrics.json', 'trade_outcomes_summary.json', 'run_provenance.json', 'input_manifest.json']]
    require_closed(outcomes)
    if outcomes['status'] != 'passed' or read(run / 'validation_report.json')['status'] != 'passed':
        raise ValueError('Source validation did not pass')
    if sha(run / 'input_manifest.json') != provenance['input_manifest_sha256']:
        raise ValueError('Input manifest hash mismatch')
    if not provenance['all_data_and_model_inputs_unchanged_during_run']:
        raise ValueError('Source inputs changed during replay')
    mapping_rel = Path('examples/portfolio_backtesting/backtest_outputs/tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv')
    for relative in [Path('.vntrader/database.db'), mapping_rel, Path('official_strategy_materials/CURRENT.json')]:
        if sha(root / relative) != inputs[str(relative)]:
            raise ValueError(f'Frozen market/identity hash mismatch: {relative}')
    for filename, key in [('trades.csv','trades'), ('effective_parameters.json','effective_parameters')]:
        if sha(run / filename) != outcomes['source_sha256'][key]:
            raise ValueError(f'Frozen ledger hash mismatch: {filename}')
    sys.path.insert(0, str(ROOT / 'examples/portfolio_backtesting'))
    from qmt_roll_official_baseline_identity import assert_official_checkout_matches_active_material
    identity = asdict(assert_official_checkout_matches_active_material(root))
    if identity != asdict(assert_official_checkout_matches_active_material(ROOT)):
        raise ValueError('Local official material identity differs from replay checkout')
    daily = pd.read_csv(run / 'daily.csv', parse_dates=['date'])
    trades = pd.read_csv(run / 'trades.csv').set_index('trade_id', verify_integrity=True)
    cycles = pd.read_csv(run / 'trade_outcomes_complete_cycles.csv')
    matches = pd.read_csv(run / 'trade_outcomes_fifo_matches.csv')
    if not daily.date.is_monotonic_increasing or daily.date.duplicated().any():
        raise ValueError('Daily chronology invalid')
    if not daily.date.between(metrics['start'], metrics['end']).all():
        raise ValueError('Daily dates outside source interval')
    close(float(np.max(np.abs(daily.account_equity - (metrics['account_capital'] + daily.net_pnl.cumsum())))), 0., 'equity identity')
    close(float(np.max(np.abs(daily.net_pnl - (daily.holding_pnl + daily.trading_pnl - daily.commission - daily.slippage)))), 0., 'daily pnl identity')
    close(daily.account_equity.iloc[-1], metrics['end_equity'], 'ending equity')
    close((daily.account_equity.iloc[-1] / metrics['account_capital'] - 1) * 100, metrics['total_return_pct'], 'return')
    close(((daily.account_equity / daily.account_equity.cummax()) - 1).min() * 100, metrics['max_dd_pct'], 'drawdown')
    close(daily.slippage.sum(), metrics['total_slippage'], 'slippage')
    close(len(trades), metrics['total_trade_count'], 'fills')
    close(len(cycles), outcomes['complete_cycle_count'], 'cycles')
    close((cycles.net_pnl > 1e-7).mean()*100, outcomes['complete_cycle_win_rate_pct'], 'win rate')
    close(cycles.net_pnl.sum(), daily.net_pnl.sum(), 'closed pnl')
    if not cycles.open_trade_count.eq(1).all():
        raise ValueError('Multiple entry fills per cycle need an explicit adapter')
    return metrics, outcomes, identity, daily, trades, cycles, matches, mapping_rel


def episode_rows(cycles: pd.DataFrame, matches: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    rows, consumed = [], set()
    for index, cycle in enumerate(cycles.itertuples(index=False)):
        entry, final = trades.loc[cycle.first_trade_id], trades.loc[cycle.last_trade_id]
        lots = matches[matches.entry_trade_id.eq(cycle.first_trade_id)]
        if len(lots) != cycle.close_trade_count or lots.empty:
            raise ValueError('FIFO mapping differs from complete cycle')
        close(lots.net_pnl.sum(), cycle.net_pnl, 'episode pnl')
        close(lots.volume.sum(), cycle.opened_volume, 'episode volume')
        if cycle.first_trade_id in consumed:
            raise ValueError('Duplicate episode')
        consumed.add(cycle.first_trade_id)
        consumed.update(lots.exit_trade_id)
        weighted_exit = np.average(lots.exit_price, weights=lots.volume)
        change = (weighted_exit / entry.price - 1) * 100
        # Preserve display timestamps; known inherited natural-day/night-session
        # ambiguity is disclosed. No invented signal/risk-to-trade join.
        entry_date = pd.Timestamp(cycle.first_datetime).tz_localize(None).normalize()
        exit_date = pd.Timestamp(cycle.last_datetime).tz_localize(None).normalize()
        reasons = ' / '.join(dict.fromkeys(trades.loc[lots.exit_trade_id, 'exit_reason'].fillna('未标注').astype(str)))
        result = 'profit' if cycle.net_pnl > 1e-7 else 'loss' if cycle.net_pnl < -1e-7 else 'flat'
        rows.append(dict(open_trade_id=cycle.first_trade_id, close_trade_id=cycle.last_trade_id,
            lot_id=cycle.first_trade_id, lot_count=len(lots), vt_symbol=cycle.vt_symbol,
            product=re.sub(r'\d+', '', cycle.vt_symbol), direction=cycle.direction,
            entry_date=entry_date, exit_date=exit_date, entry_price=entry.price,
            exit_price=final.price, weighted_exit_price=weighted_exit, volume=cycle.opened_volume,
            price_change_pct=change, price_change_label=f'标的原价涨跌 {change:+.2f}%（非账户收益）',
            realized_pnl=cycle.net_pnl, r_multiple=float('nan'), result_type=result,
            result_rank=index+1, is_tail=0, draw_intraday=0,
            profit_r_threshold=float('nan'), loss_r_threshold=float('nan'),
            holding_calendar_days=(exit_date-entry_date).days, exit_reason=reasons,
            signal='未做逐成交信号绑定',
            selection_basis=f'{cycle.first_trade_id} → {cycle.last_trade_id}｜{int(cycle.opened_volume)}手｜开{entry.price:g} / 最终平{final.price:g}｜{reasons}'))
    if consumed != set(trades.index):
        raise ValueError('Unpaired source fills')
    return pd.DataFrame(rows)


def generate(root: Path, output: Path) -> None:
    output = validate_output(output)
    run = root / RUN_REL
    metrics, outcomes, identity, daily, trades, cycles, matches, mapping_rel = verify_source(root, run)
    source_hashes = {name: sha(run / name) for name in REQUIRED}
    episodes = episode_rows(cycles, matches, trades)
    mapping = pd.read_csv(root / mapping_rel, parse_dates=['date']).dropna(subset=['main_contract_vt'])
    mapping = mapping[mapping.date.le(metrics['end'])].copy()
    with sqlite3.connect(f'file:{root}/.vntrader/database.db?mode=ro', uri=True) as conn:
        bars = pd.read_sql_query("SELECT symbol || '.' || exchange AS vt_symbol, datetime AS date, open_price AS open, high_price AS high, low_price AS low, close_price AS close, volume FROM dbbardata WHERE interval='d' ORDER BY datetime", conn)
    bars['date'] = pd.to_datetime(bars.date).dt.normalize()
    bars = bars[bars.date.le(metrics['end'])]
    cache = {key: value.drop(columns='vt_symbol').reset_index(drop=True) for key, value in bars.groupby('vt_symbol', sort=False)}
    def contract_daily(symbol: str) -> pd.DataFrame:
        if symbol not in cache:
            raise RuntimeError(f'Missing exact contract {symbol}')
        return cache[symbol]
    renderer = load_renderer({'_contract_daily': contract_daily,
        '_daily_from_existing_minute_files': lambda *args: pd.DataFrame()})
    context, minute_dates = {}, {}
    print(f'Verified {len(episodes)} cycles / {len(trades)} fills; building canonical charts', flush=True)
    for i, row in enumerate(episodes.itertuples(index=False)):
        context[row.open_trade_id], minute_dates[row.open_trade_id] = renderer['_context_daily'](
            row, mapping, cache, allow_daily_download=False, allow_noncritical_daily_gaps=True,
            data_end=pd.Timestamp(metrics['end']))
        if (i+1) % 50 == 0:
            print(f'Context {i+1}/{len(episodes)}', flush=True)
    records, manifest = renderer['_records'](episodes, context, minute_dates,
        pd.DataFrame(columns=['vt_symbol','bar_datetime','trading_day','open','high','low','close','volume']))
    for record, row in zip(records, episodes.itertuples(index=False)):
        for key in ['entry_price', 'exit_price', 'realized_pnl', 'volume']:
            close(record['meta'][key], getattr(row, key), f'rendered {key}')
        for key in ['entry_source', 'exit_source']:
            if record['meta'][key] != row.vt_symbol:
                raise ValueError('Entry or final exit must use exact-contract bars')
    warning = ('正式物料历史回测，非实盘收益；生产运行身份未核验。2020年至2022-01-28沿用静态18池，之后才启用月度Top10非fu＋固定fu。手续费为0；最大回撤53.30%、保证金代理峰值149.53%，部署门未通过。'
               '历史模型含2020–2022训练段，继承自然日扫描/夜盘时序问题，非严格样本外或无前视证明。'
               '分钟缓存仅覆盖选定日期，未拼成完整15分钟图；R未做唯一风险快照绑定，显示N/A。')
    summary = dict(source_label='Stage037 / C9 15万 / Top10非fu＋固定fu',
        source_version=identity['material_release_id'], source_warning=warning,
        page_title='正式策略历史回测复盘 · 2020—2026-10-14', episode_scope='all',
        coverage_note=f'全量{len(episodes)}个完整持仓周期；按净利润、年份、品种筛选。30日K、10日K、月K、周K、日K可选；15分钟本次未提供。',
        footer_scope=f'{len(episodes)}个完整持仓周期，{len(trades)}笔成交；部分平仓聚合至最终平仓。',
        rank_basis='realized_pnl', source_bundle=str(run), identity=identity,
        source_checkout_commit=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'], text=True).strip(),
        frozen_metrics=metrics, frozen_trade_outcomes=outcomes, source_sha256=source_hashes,
        renderer_sha256=RENDERER_SHA, completed_cycle_count=len(episodes),
        profit_count=int((episodes.result_type=='profit').sum()), loss_count=int((episodes.result_type=='loss').sum()),
        flat_count=int((episodes.result_type=='flat').sum()), rerun=False, market_download=False,
        production_access=False, strategy_change=False, generated_at=datetime.now().astimezone().isoformat(),
        proxy_episode_count=int(manifest.context_fallback_days.gt(0).sum()),
        context_gap_episode_count=int(manifest.missing_context_dates.map(bool).sum()),
        notes=['图表MA仅供展示，跨合约背景未复权并用灰线标出，不是策略信号MA。',
               '成交日期沿用导出自然日；夜盘事件可能属于下一交易日，00:00不是可信盘中时间。12个最终平仓价落在同自然日日K高低之外，保留原账本，不代表在该日K范围内可成交。',
               '最终平仓标记用最后一笔价格；价格涨跌排序用全部平仓的成交量加权价格。'])
    page = renderer['_html'](records, summary)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[.68,.32], vertical_spacing=.08)
    fig.add_trace(go.Scatter(x=daily.date, y=daily.account_equity, name='权益（元）', line=dict(color='#2563eb')), row=1,col=1)
    fig.add_trace(go.Scatter(x=daily.date, y=(daily.account_equity/daily.account_equity.cummax()-1)*100,
        name='回撤（%）',fill='tozeroy',line=dict(color='#c2410c')), row=2,col=1)
    fig.update_layout(height=440,margin=dict(l=70,r=25,t=30,b=35),hovermode='x unified',template='plotly_white')
    annual = pd.read_csv(run/'annual_attribution.csv')
    overview = ('<section class="panel" style="padding:18px;margin-bottom:16px"><h2>冻结回测总览</h2>'
        f'<p>15万元 → <b>{metrics["end_equity"]:,.2f}元</b> · 总收益 {metrics["total_return_pct"]:,.2f}% · '
        f'最大回撤 {metrics["max_dd_pct"]:.2f}% · Sharpe {metrics["sharpe"]:.4f} · '
        f'净胜率 {outcomes["complete_cycle_win_rate_pct"]:.2f}%（{outcomes["complete_cycle_wins"]}/{len(episodes)}）</p>'
        f'<p>滑点 {metrics["total_slippage"]:,.0f}元；手续费0元。成交{len(trades)}笔，期末持仓0。数据截止：2026-10-14。盈利日占非零盈亏日 {metrics["nonzero_daily_win_rate_pct"]:.2f}%（不是交易胜率）。</p>'
        + fig.to_html(full_html=False, include_plotlyjs=False, div_id='equityOverview')
        + '<details><summary>数据身份、已知边界与年度原表</summary><p>'
        + html.escape('；'.join(summary['notes'])) + '</p><p>' + html.escape(str(identity))
        + '</p><p>MA历史不足不补造；上市前和截止后不足的窗口按可用历史截断。盈亏/持平计数：119/274/2。</p>'
        + annual.to_html(index=False, border=0) + '</details></section>')
    page = page.replace('<div class="toolbar">', overview+'<div class="toolbar">', 1)
    # Tail filters are not defined for this full-ledger source.
    page = page.replace('<option value="profit_tail">盈利尾部</option>', '').replace('<option value="loss_tail">亏损尾部</option>', '')
    for name, expected in source_hashes.items():
        if sha(run/name) != expected:
            raise ValueError(f'Source changed during render: {name}')
    output.mkdir(parents=True)
    episodes.to_csv(output/'episodes.csv',index=False)
    manifest.to_csv(output/'chart_manifest.csv',index=False)
    (output/'records.json').write_text(json.dumps(renderer['_json_safe'](records), ensure_ascii=False, separators=(',',':'), allow_nan=False))
    (output/'summary.json').write_text(json.dumps(renderer['_json_safe'](summary),ensure_ascii=False,indent=2,allow_nan=False))
    (output/'index.html').write_text(page)
    print(json.dumps({'html':str(output/'index.html'),'cycles':len(records),'bytes':len(page.encode()),
        'proxy_episodes':summary['proxy_episode_count'],'gap_episodes':summary['context_gap_episode_count']},ensure_ascii=False),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, default=SOURCE_ROOT)
    parser.add_argument('--output', type=Path, default=LINE/'outputs/stage248_formal_m0008_20200101_20261014_recap_v1')
    args = parser.parse_args()
    generate(args.source_root, args.output)
