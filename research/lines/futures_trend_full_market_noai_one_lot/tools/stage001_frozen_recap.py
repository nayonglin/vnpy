"""Read one hash-closed research bundle and invoke only Stage038 display functions.

No strategy modules, TqSdk, downloads, database writes, or official source edits.
Canonical function AST nodes are compiled verbatim, never copied into this adapter.
"""
from __future__ import annotations

import argparse
import ast
from collections import deque
from datetime import datetime
import hashlib
import html
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
from plotly.offline import get_plotlyjs

REPO = Path(__file__).resolve().parents[4]
CANONICAL = REPO / 'research/lines/futures_trend_winner_trade_forensics/tools/stage038_c9_15w_big_winner_multiscale_html.py'
FUNCTIONS = ('_json_safe', '_closed_lots_from_trade_ledger', '_trade_episodes', '_selected_tail_episodes', '_all_trade_episodes', '_date_index', '_window_dates', '_context_daily', '_weekly_from_daily', '_monthly_from_daily', '_trading_day_bars_from_daily', '_monthly_window', '_add_moving_averages', '_period_coordinates', '_records', '_html')
CONSTANTS = ('DAILY_PRE', 'DAILY_POST', 'INTRADAY_PRE', 'INTRADAY_POST', 'MONTHLY_PRE', 'MONTHLY_POST', 'MA_PERIODS', 'WEEKLY_MA_WARMUP_WEEKS', 'MONTHLY_MA_WARMUP_MONTHS', 'TRADING_DAY_MA_WARMUP_DAYS')
REQUIRED = ('trades.csv', 'daily.csv', 'summary.json', 'contract_metadata.csv', 'mapping.csv', 'market_daily.csv')


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load_display_functions(products: dict[str, str]) -> SimpleNamespace:
    """Load a closed pure-display subset; fail if canonical names are missing."""
    tree = ast.parse(CANONICAL.read_text(encoding='utf-8'), filename=str(CANONICAL))
    nodes = []
    found = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS:
            nodes.append(node)
            found.add(node.name)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in CONSTANTS:
            nodes.append(node)
            found.add(node.targets[0].id)
    if found != set(FUNCTIONS + CONSTANTS):
        raise ValueError(f'Canonical display contract changed: missing {set(FUNCTIONS + CONSTANTS) - found}')
    namespace = dict(globals())
    namespace.update({'s719': SimpleNamespace(_infer_product=lambda symbol: products[symbol]),
                      '_daily_from_existing_minute_files': lambda *args: pd.DataFrame(),
                      'OFFICIAL_LIVE_ALIAS': '研究版', 'OFFICIAL_LIVE_VERSION': 'research'})
    subset = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)] + nodes, type_ignores=[])
    exec(compile(ast.fix_missing_locations(subset), str(CANONICAL), 'exec'), namespace)
    return SimpleNamespace(**namespace)


def read_bundle(source: Path) -> tuple[dict, dict[str, pd.DataFrame], dict]:
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    for key in ('run_id', 'source_commit', 'parameters', 'start', 'end', 'hashes'):
        if key not in manifest:
            raise ValueError(f'Missing frozen identity field: {key}')
    for name in REQUIRED:
        expected = manifest['hashes'].get(name)
        if not expected or not (source / name).is_file() or sha256(source / name) != expected:
            raise ValueError(f'Frozen evidence hash mismatch or missing: {name}')
    frames = {name: pd.read_csv(source / name) for name in REQUIRED if name.endswith('.csv')}
    trades = frames['trades.csv']
    if trades.empty or trades['trade_id'].astype(str).duplicated().any():
        raise ValueError('Frozen ledger must have nonempty unique trade ids')
    for key, required in {'trades.csv': {'trade_id','datetime','date','vt_symbol','direction','offset','volume','price'}, 'daily.csv': {'date'}, 'contract_metadata.csv': {'vt_symbol','size'}, 'mapping.csv': {'date','product','exchange','main_contract_vt'}, 'market_daily.csv': {'date','vt_symbol','open','high','low','close','volume'}}.items():
        if not required.issubset(frames[key].columns):
            raise ValueError(f'Missing frozen columns: {key}: {required - set(frames[key].columns)}')
    for key in ('trades.csv', 'daily.csv', 'mapping.csv', 'market_daily.csv'):
        frames[key]['date'] = pd.to_datetime(frames[key]['date'], errors='raise').dt.normalize()
    if frames['daily.csv'].empty:
        raise ValueError('Frozen equity/daily evidence is empty')
    if not trades['date'].between(pd.Timestamp(manifest['start']), pd.Timestamp(manifest['end'])).all():
        raise ValueError('Frozen trade interval differs from manifest')
    summary = json.loads((source / 'summary.json').read_text(encoding='utf-8'))
    if 'total_trade_count' in summary and float(summary['total_trade_count']) != len(trades):
        raise ValueError('Frozen metrics trade count differs from ledger')
    return manifest, frames, summary


def context_mapping_groups(mapping: pd.DataFrame) -> dict[tuple[str, str], pd.DataFrame]:
    # Partition only input rows; canonical _context_daily retains all filtering,
    # sorting, bar windows, warmup and chart behavior unchanged.
    return {key: frame for key, frame in mapping.groupby(
        [mapping['product'].astype(str).str.lower(), mapping['exchange']], sort=False
    )}


def render_bundle(source: Path, output: Path, *, context_builder=None, context_provenance=None) -> dict:
    source, output = Path(source).resolve(), Path(output).resolve()
    if output == source or output in source.parents or source in output.parents:
        raise ValueError('Output must be isolated from frozen source')
    if output.exists():
        raise FileExistsError(f'Recap output already exists: {output}')
    adapter_code_hash = sha256(Path(__file__))
    identity, frames, metrics = read_bundle(source)
    metadata = frames['contract_metadata.csv'].copy()
    if metadata['vt_symbol'].duplicated().any() or (pd.to_numeric(metadata['size'], errors='raise') <= 0).any():
        raise ValueError('Contract metadata must have unique symbols and positive size')
    products = {str(row.vt_symbol): str(getattr(row, 'product', ''.join(c for c in str(row.vt_symbol).split('.')[0] if c.isalpha()))) for row in metadata.itertuples()}
    renderer = load_display_functions(products)
    closed = renderer._closed_lots_from_trade_ledger(frames['trades.csv'], sizes=metadata.set_index('vt_symbol')['size'].to_dict(), allow_residual_open=True, source_prefix=identity['run_id'])
    residual = closed.attrs.get('residual_open_positions', [])
    if not closed.empty:
        opened = frames['trades.csv'][frames['trades.csv']['offset'].astype(str).str.lower().isin(['open', '开'])].copy()
        open_volumes = opened.set_index(opened['trade_id'].astype(str))['volume'].astype(float)
        if 'signal' in opened.columns:
            # Carry only the hash-bound entry's recorded case; do not infer labels.
            source_signals = opened.set_index(opened['trade_id'].astype(str))['signal']
            blank = closed['signal'].isna() | closed['signal'].astype(str).str.strip().eq('')
            closed.loc[blank, 'signal'] = closed.loc[blank, 'open_trade_id'].astype(str).map(source_signals).fillna('')
        closed_volumes = closed.groupby('open_trade_id')['volume'].sum()
        complete_ids = {str(key) for key, value in closed_volumes.items() if math.isclose(float(value), float(open_volumes.loc[str(key)]), rel_tol=0, abs_tol=1e-10)}
        incomplete_closed_lots = closed[~closed['open_trade_id'].astype(str).isin(complete_ids)].to_dict('records')
        closed = closed[closed['open_trade_id'].astype(str).isin(complete_ids)].copy()
    else:
        incomplete_closed_lots = []
    if closed.empty:
        raise ValueError('Frozen bundle has no completed episodes to render')
    episodes = renderer._all_trade_episodes(closed)
    # All completed episodes request local 15m evidence; missing local input is disclosed.
    episodes['draw_intraday'] = 1
    market = frames['market_daily.csv']
    if market.duplicated(['vt_symbol', 'date']).any():
        raise ValueError('Duplicate contract daily bars')
    bar_cache = {str(key): group.drop(columns=['vt_symbol']).copy().sort_values('date').reset_index(drop=True) for key, group in market.groupby('vt_symbol', sort=False)}
    def contract_daily(symbol):
        if symbol not in bar_cache:
            raise RuntimeError(f'Missing local frozen daily bars for {symbol}')
        return bar_cache[symbol]
    renderer._context_daily.__globals__['_contract_daily'] = contract_daily
    daily_by_episode, dates_by_episode = {}, {}
    mapping = frames['mapping.csv']
    if context_builder is None:
        mapping_groups = context_mapping_groups(mapping)
        for i, row in enumerate(episodes.itertuples(index=False), 1):
            product_value = str(row.product)
            product, exchange = product_value.split('.', 1) if '.' in product_value else (product_value, str(row.vt_symbol).split('.', 1)[1])
            product_mapping = mapping_groups.get((product.lower(), exchange), mapping.iloc[:0])
            daily, dates = renderer._context_daily(row, product_mapping, bar_cache, allow_daily_download=False, allow_noncritical_daily_gaps=True, data_end=pd.Timestamp(identity['end']))
            daily_by_episode[str(row.open_trade_id)] = daily
            dates_by_episode[str(row.open_trade_id)] = dates
            if i % 100 == 0:
                print(f'Canonical daily context {i}/{len(episodes)}', flush=True)
    else:
        daily_by_episode, dates_by_episode = context_builder(episodes, mapping, bar_cache, pd.Timestamp(identity['end']))
    minute = pd.DataFrame(columns=['vt_symbol','bar_datetime','trading_day','open','high','low','close','volume'])
    if 'bars_15m.csv' in identity['hashes']:
        path = source / 'bars_15m.csv'
        if not path.is_file() or sha256(path) != identity['hashes']['bars_15m.csv']:
            raise ValueError('Frozen evidence hash mismatch: bars_15m.csv')
        minute = pd.read_csv(path)
        minute['bar_datetime'] = pd.to_datetime(minute['bar_datetime'])
        minute['trading_day'] = pd.to_datetime(minute['trading_day']).dt.normalize()
    records, chart_manifest = renderer._records(episodes, daily_by_episode, dates_by_episode, minute)
    # Requesting a minute window is not evidence that any minute bars exist.
    available_ids = {r['meta']['open_trade_id'] for r in records if len(r['intraday']['x']) > 0}
    for r in records:
        r['meta']['draw_intraday'] = int(r['meta']['open_trade_id'] in available_ids)
    chart_manifest['draw_intraday'] = chart_manifest.open_trade_id.isin(available_ids).astype(int)
    episodes['draw_intraday'] = episodes.open_trade_id.isin(available_ids).astype(int)
    residual_note = f'期末有{len(residual)}项残余未平仓，不计入完整交易图；明细见residual_open_positions.json。'
    mode = str(metrics.get('mode', identity.get('mode', '')))
    is_daily_proxy = mode == 'daily-proxy'
    mode_label = '日线近似（daily-proxy）' if is_daily_proxy else (f'回测模式：{mode}' if mode else '')
    boundaries = metrics.get('boundaries', [])
    boundary_items = boundaries if isinstance(boundaries, list) else [boundaries]
    # Keep plain text here: canonical _html escapes source_warning/source_label/title.
    boundary_note = '冻结边界：' + '；'.join(item if isinstance(item, str) else json.dumps(item, ensure_ascii=False) for item in boundary_items) + '。' if boundary_items else ''
    statistics = []
    for field, label, fmt in (
        ('end_balance', '期末权益', ',.2f'), ('total_return', '总收益', '.4f'),
        ('max_ddpercent', '最大回撤', '.4f'), ('sharpe_ratio', 'Sharpe', '.4f'),
        ('win_rate_pct', '净胜率', '.4f'), ('total_commission', '手续费', ',.2f'),
        ('total_slippage', '滑点', ',.2f'), ('payoff_ratio', '净盈亏比', '.4f'),
        ('profit_factor', '盈利因子', '.4f'),
    ):
        if metrics.get(field) is not None:
            suffix = '%' if field in ('total_return', 'max_ddpercent', 'win_rate_pct') else ''
            statistics.append(label + format(float(metrics[field]), fmt) + suffix)
    count_parts = []
    if metrics.get('total_trade_count') is not None:
        count_parts.append(f"{int(metrics['total_trade_count'])}成交")
    if metrics.get('completed_episodes') is not None:
        count_parts.append(f"{int(metrics['completed_episodes'])}完整交易")
    if count_parts:
        statistics.append('/'.join(count_parts))
    statistics_note = (('冻结账面统计（不可认证业绩）' if metrics.get('performance_certifiable') is False else '冻结回测统计') + '：' + '、'.join(statistics) + '。') if statistics else ''
    position_policy_note = '无品种数上限，每品种1手。' if metrics.get('position_count_limit_removed') is True else ''
    summary = {
        'line_id':'futures_trend_full_market_noai_one_lot', 'stage':'Stage001', 'source_profile':'full_market_noai_one_lot_frozen',
        'run_id':identity['run_id'], 'source_commit':identity['source_commit'], 'source_manifest_sha256':sha256(source / 'manifest.json'),
        'source_provenance':identity, 'backtest_metrics':metrics, 'episode_scope':'all',
        'chart_episodes':len(episodes), 'closed_lots':len(closed),
        'chart_profit_episodes':int(episodes['result_type'].eq('profit').sum()), 'chart_loss_episodes':int(episodes['result_type'].eq('loss').sum()), 'chart_flat_episodes':int(episodes['result_type'].eq('flat').sum()),
        'residual_open_positions':residual, 'partial_closes_of_residual_entries':incomplete_closed_lots, 'bars_15m':len(minute), 'intraday_missing_days':int(chart_manifest['intraday_missing_days'].sum()),
        'missing_context_days':sum(len(record['meta']['missing_context_dates']) for record in records),
        'page_title':('【执行与残仓受限】' if metrics.get('performance_certifiable') is False else '') + ('【日线近似】' if is_daily_proxy else '') + ('【无品种数上限，每品种1手】' if position_policy_note else '') + '正式物料研究版：全市场无AI / 多空全部case / 100万每品种1手逐笔复盘',
        'source_label':('日线近似；' if is_daily_proxy else '') + '基于master Stage037/m0008正式物料的独立研究回测', 'source_version':identity['run_id'],
        'rank_basis':'realized_pnl', 'coverage_note':'全部完整开平仓均可选择30日K、10日K、月K、周K和日K；15分钟仅展示本次冻结包已有数据，缺失不补造。',
        'source_warning':(mode_label + '。' if mode_label else '') + position_policy_note + boundary_note + statistics_note + residual_note + '前后图窗受上市历史与数据截止限制，缺少的远期历史和MA预热不合成；主力代理与背景缺口见逐笔指标和manifest。图中每笔PnL为合约价差毛收益，账户手续费和滑点以冻结回测指标为准；R不可获得时显示N/A。',
        'footer_scope':f'共{len(episodes)}笔完整开平仓episode；',
        'adapter_code_sha256':adapter_code_hash,
        'context_generation':context_provenance or {'mode':'serial', 'workers':1},
        'canonical_renderer':str(CANONICAL), 'canonical_renderer_sha256':sha256(CANONICAL), 'canonical_functions':list(FUNCTIONS),
        'strategy_rerun_performed':False, 'market_download_performed':False, 'production_access_performed':False,
        'data_end':identity['end'], 'source_directory':str(source),
    }
    # Build everything before output creation, then write a distinct new version.
    page = renderer._html(records, summary)
    if sha256(Path(__file__)) != adapter_code_hash:
        raise ValueError('Adapter source changed during rendering')
    if context_provenance and sha256(Path(context_provenance['entry'])) != context_provenance['entry_sha256']:
        raise ValueError('Context entry source changed during rendering')
    output.mkdir(parents=True)
    (output / 'index.html').write_text(page, encoding='utf-8')
    (output / 'records.json').write_text(json.dumps(renderer._json_safe(records), ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    chart_manifest.to_csv(output / 'chart_manifest.csv', index=False)
    closed.to_csv(output / 'closed_lots.csv', index=False)
    episodes.to_csv(output / 'all_trade_episodes.csv', index=False)
    frames['daily.csv'].to_csv(output / 'strategy_daily.csv', index=False)
    (output / 'residual_open_positions.json').write_text(json.dumps(residual, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    summary['artifact_sha256'] = {path.name:sha256(path) for path in output.iterdir()}
    (output / 'summary.json').write_text(json.dumps(renderer._json_safe(summary), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    summary = render_bundle(args.source, args.output)
    print(json.dumps({key:summary[key] for key in ('run_id','chart_episodes','chart_profit_episodes','chart_loss_episodes','bars_15m','intraday_missing_days')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
