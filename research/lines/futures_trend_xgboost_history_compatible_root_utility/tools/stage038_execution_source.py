from __future__ import annotations

import argparse
import ast
from collections import Counter
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sqlite3
import traceback
from types import SimpleNamespace

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STAGE = 'stage038_execution_source'
OUTPUT = ROOT / 'artifacts' / STAGE
CONTRACT = ROOT / 'stages/20260906_1003_stage038_execution_source_contract.md'
FREEZE = ROOT / 'stages/stage038_input_freeze.json'
PARENT = ROOT / 'artifacts/stage037_calendar_window'
OBSERVER = ROOT / 'artifacts/stage033_holding_observer/workers/A'
PRODUCTION = Path('/Users/bytedance/Desktop/person/vnpy_production_live/examples/portfolio_backtesting')
RAW_ROOTS = [PRODUCTION / 'downloaded_futures' / name for name in (
    'tqsdk_stage506_next_real_forward_risk_signal_frontier',
    'tqsdk_stage452_true_path_fallback_1455', 'tqsdk_stage448_minute_session_rebuild_batch')]
SEED = PRODUCTION / 'backtest_outputs/qmt_roll_stage449_minute_session_rebuild_full_ledger_proxy_detail_stage449_minute_session_rebuild_full_v1.csv'
SOURCES = {
    's452': PRODUCTION / 'analyze_qmt_roll_stage452_iterative_1455_proxy_backfill.py',
    's501': PRODUCTION / 'analyze_qmt_roll_stage501_asymmetric_entry_exit_execution.py',
    's502': PRODUCTION / 'analyze_qmt_roll_stage502_confirmed_daily_next_real_open_replay.py',
    's827': PRODUCTION / 'analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac.py',
    'strategy': PRODUCTION / 'qmt_roll_portfolio_strategy.py',
    'template': ROOT.parents[2] / '.py311/lib/python3.11/site-packages/vnpy_portfoliostrategy/template.py',
}


def function_node(source, name, owner=None):
    body = ast.parse(source).body
    if owner:
        owners = [node for node in body if isinstance(node, ast.ClassDef) and node.name == owner]
        if len(owners) != 1:
            raise ValueError('source_class_inventory')
        body = owners[0].body
    matches = [node for node in body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) != 1 or matches[0].decorator_list:
        raise ValueError('source_function_inventory')
    return matches[0]


def extract_function(source, name, namespace, owner=None):
    node = function_node(source, name, owner)
    module = ast.parse('from __future__ import annotations')
    module.body.append(node)
    exec(compile(ast.fix_missing_locations(module), '<frozen-price-function>', 'exec'), namespace)
    return namespace[name]


def make_legacy(raw_roots=None, seed_path=None):
    roots = RAW_ROOTS if raw_roots is None else raw_roots
    raw_namespace = {'pd': pd, 'Path': Path, 'RAW_ROOTS': roots}
    source = SOURCES['s452'].read_text()
    extract_function(source, '_raw_path', raw_namespace)
    original_load = extract_function(source, '_load_raw_bars', raw_namespace)
    cache = {}

    def cached(symbol):
        if symbol not in cache:
            cache[symbol] = original_load(symbol)
        return cache[symbol]

    source = SOURCES['s501'].read_text()
    assignments = [node for node in ast.parse(source).body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == 'NIGHT_SESSION_PRODUCTS' for target in node.targets)]
    if len(assignments) != 1:
        raise ValueError('source_night_inventory')
    namespace = {'pd': pd, 'np': np, 'math': math,
                 'NIGHT_SESSION_PRODUCTS': ast.literal_eval(assignments[0].value),
                 's452': SimpleNamespace(_load_raw_bars=cached),
                 's451': SimpleNamespace(STAGE149_DETAIL_PATH=seed_path or SEED)}
    for name in ('_safe_float', '_naive_date', '_product_from_contract', '_has_night_session',
                 '_window_price', '_next_real_open_proxy_from_raw', '_seed_proxy_maps'):
        extract_function(source, name, namespace)
    close_map, open_map = namespace['_seed_proxy_maps']()
    engine_namespace = {'s501': SimpleNamespace(**namespace), 'math': math}
    source = SOURCES['s502'].read_text()
    extract_function(source, '_safe_float', engine_namespace)
    resolver = extract_function(source, '_resolve_trade_price', engine_namespace, 'ConfirmedDailyNextRealOpenEngine')

    def resolve(order, fill_date, daily_open):
        engine = SimpleNamespace(open_proxy_map=open_map, datetime=fill_date)
        return resolver(engine, order, SimpleNamespace(open_price=daily_open))

    return SimpleNamespace(resolve=resolve, raw_cache=cache, open_map=open_map, close_map=close_map)


def execution_boundaries():
    def calls(key, name, owner):
        node = function_node(SOURCES[key].read_text(), name, owner)
        return [ast.unparse(call.func) for call in sorted(
            (value for value in ast.walk(node) if isinstance(value, ast.Call)),
            key=lambda value: (value.lineno, value.col_offset))]

    daily = calls('s502', 'new_bars', 'ConfirmedDailyNextRealOpenEngine')
    strategy = calls('strategy', 'on_bars', 'QmtRollPortfolioStrategy')
    rebalance = calls('template', 'rebalance_portfolio', 'StrategyTemplate')
    fill = calls('s827', '_fill_order', 'Stage827IntradayC2Engine')
    cross = function_node(SOURCES['s502'].read_text(), 'cross_delayed_orders', 'ConfirmedDailyNextRealOpenEngine')
    inline = 'self._fill_synthetic_intraday_close' in fill and any(isinstance(node, ast.For) for node in ast.walk(cross))
    if not inline:
        raise ValueError('source_inline_fill_contract_changed')
    return {'delayed_fill_before_strategy': daily.index('self.cross_delayed_orders') < daily.index('self.strategy.on_bars'),
            'ordinary_rebalance_before_forced_margin': strategy.index('self.rebalance_portfolio') < strategy.index('self._process_forced_margin_deleverage'),
            'rebalance_cancels_all_first': rebalance[0] == 'self.cancel_all',
            'open_fill_calls_intraday_before_next_order': inline,
            'globally_chronological_minute_engine': False}


def order_inventory(rows):
    result = {}
    for row in rows:
        for order in row['active_orders']:
            key = order['order_id']
            if key in result and result[key] != order:
                raise ValueError('conflicting_observed_order:' + key)
            result[key] = order
    return result


def trade_origin(order_id, orders):
    if order_id in orders:
        return 'observed_order'
    if '.stage847_c9.' in order_id or order_id.endswith('.stage827_c2'):
        return 'synthetic_intraday'
    return 'missing_observed_order'


def audit_trade(trade, orders, legacy, daily):
    key = trade['order_id']
    origin = trade_origin(key, orders)
    result = {name: trade[name] for name in ('trade_id', 'order_id', 'date', 'vt_symbol', 'direction', 'offset', 'volume', 'price')}
    result['status'] = origin
    if origin != 'observed_order':
        return result
    order = orders[key]
    direction = {'Direction.LONG': '\u591a', 'Direction.SHORT': '\u7a7a'}.get(order['direction'])
    offset = {'Offset.OPEN': '\u5f00', 'Offset.CLOSE': '\u5e73'}.get(order['offset'])
    if (order['vt_symbol'] != trade['vt_symbol'] or direction != trade['direction']
            or offset != trade['offset'] or float(order['volume']) != float(trade['volume'])):
        result['status'] = 'order_identity_mismatch'
        return result
    opening = daily.get((trade['vt_symbol'], trade['date']))
    if opening is None:
        result['status'] = 'daily_bar_missing'
        return result
    price, source, proxy = legacy.resolve(SimpleNamespace(**order), pd.Timestamp(trade['date']), opening)
    signal_date = pd.Timestamp(order['datetime']).tz_localize(None).normalize()
    result.update(signal_date=str(signal_date.date()), resolved_price=price, price_source=source,
                  first_time=str(proxy.get('proxy_first_time', '')), daily_open=opening,
                  price_error=price - float(trade['price']))
    result['status'] = ('matched' if signal_date < pd.Timestamp(trade['date'])
                        and math.isfinite(price) and abs(result['price_error']) <= 1e-7 else 'price_or_time_mismatch')
    return result


def load(name):
    spec = importlib.util.spec_from_file_location('source038_' + name, ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def collect_inputs():
    files = {key: Path(item['path']) for key, item in json.loads((PARENT / 'input_manifest.json').read_text())['files'].items()}
    files.update(execution_source_runner=Path(__file__).resolve(), execution_source_tests=ROOT / 'tests/test_stage038_execution_source.py',
                 execution_source_contract=CONTRACT, execution_seed_csv=SEED,
                 execution_parent_manifest=PARENT / 'input_manifest.json', execution_parent_summary=PARENT / 'summary.json',
                 execution_parent_windows=PARENT / 'windows.csv', execution_observer=OBSERVER / 'holding_states.json.gz',
                 execution_observer_receipt=OBSERVER / 'observer_receipt.json', execution_A_trades=OBSERVER / 'trades.csv.gz',
                 execution_A_receipt=OBSERVER / 'receipt.json', execution_A_archives=OBSERVER / 'archive_receipt.json',
                 execution_original_manifest=OBSERVER.parent.parent / 'input_manifest.json')
    for index, root in enumerate(RAW_ROOTS):
        if not root.is_dir():
            raise ValueError('execution_raw_root_missing')
        for path in sorted(root.rglob('*')):
            if path.is_file():
                files[f'execution_raw/{index}/{path.relative_to(root)}'] = path
    return dict(sorted(files.items()))


def configured():
    parent = load('stage037_calendar_window')
    runner = parent.configured()
    manifest = json.loads((PARENT / 'input_manifest.json').read_text())
    runner.validate_frozen_input_contract(parent.FREEZE, manifest)
    runner.validate_current_input_manifest(manifest)
    summary = json.loads((PARENT / 'summary.json').read_text())
    for item in summary['outputs'].values():
        if runner._file_identity(Path(item['path'])) != item:
            raise ValueError('execution_parent_output_changed')
    runner.STAGE = STAGE
    runner.collect_input_files = collect_inputs
    runner.EXPECTED_INPUT_FILE_COUNT = len(collect_inputs())
    return runner


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)


def run(runner, manifest):
    runner.validate_frozen_input_contract(FREEZE, manifest)
    OUTPUT.mkdir(mode=0o700)
    write_json(OUTPUT / 'input_manifest.json', manifest)
    try:
        receipt = json.loads((OBSERVER / 'observer_receipt.json').read_text())
        raw = gzip.decompress((OBSERVER / 'holding_states.json.gz').read_bytes())
        if hashlib.sha256(raw).hexdigest() != receipt['raw_sha256']:
            raise ValueError('execution_observer_raw_identity')
        provenance = receipt['runtime_provenance']
        for item in [provenance['strategy_on_bars'], *provenance['engine_methods'].values()]:
            if item and runner._file_identity(Path(item['source']))['sha256'] != item['source_sha256']:
                raise ValueError('execution_runtime_source_changed')
        rows = json.loads(raw)
        if len(rows) != receipt['row_count']:
            raise ValueError('execution_observer_count')
        orders = order_inventory(rows)
        legacy = make_legacy()
        trades = pd.read_csv(OBSERVER / 'trades.csv.gz')
        windows = pd.read_csv(PARENT / 'windows.csv')
        if len(trades) != 655 or len(windows) != 1002 or not windows.status.eq('source_proxy_qualified_not_execution').all():
            raise ValueError('execution_frozen_population_changed')
        daily = {}
        database = Path(manifest['files']['source_database']['path'])
        connection = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
        try:
            connection.execute('PRAGMA query_only=ON')
            for symbol in sorted(set(trades.vt_symbol) | set(windows.vt_symbol)):
                contract, exchange = symbol.split('.')
                values = connection.execute("SELECT substr(datetime,1,10),open_price FROM dbbardata WHERE symbol=? AND exchange=? AND interval='d' AND datetime >= '2020-01-02' AND datetime < '2026-08-29'", (contract, exchange))
                for day, opening in values:
                    key = (symbol, day)
                    if key in daily:
                        raise ValueError('execution_daily_duplicate')
                    daily[key] = float(opening)
        finally:
            connection.close()

        baseline = [audit_trade(trade, orders, legacy, daily) for trade in trades.to_dict('records')]
        comparisons = []
        for row in windows.to_dict('records'):
            opening = daily.get((row['vt_symbol'], row['next_calendar_day']))
            if opening is None:
                raise ValueError('execution_window_daily_missing')
            order = SimpleNamespace(vt_symbol=row['vt_symbol'], datetime=pd.Timestamp(row['date']), price=opening)
            price, source, proxy = legacy.resolve(order, pd.Timestamp(row['next_calendar_day']), opening)
            first = proxy.get('proxy_first_time', '')
            first = pd.Timestamp(first).isoformat() if first else ''
            comparisons.append({'date': row['date'], 'next_calendar_day': row['next_calendar_day'],
                'vt_symbol': row['vt_symbol'], 'legacy_price': price, 'legacy_source': source, 'legacy_first_time': first,
                'qualified_price': row['first_open'], 'qualified_first_time': row['first_time'],
                'price_error': price - row['first_open'], 'price_matches': abs(price - row['first_open']) <= 1e-7,
                'time_matches': first == row['first_time'],
                'legacy_uses_order_price_fallback': source == 'fallback_daily_next_open' and not opening})

        frames = {'baseline_prices': pd.DataFrame(baseline), 'window_prices': pd.DataFrame(comparisons)}
        for name, frame in frames.items():
            frame.to_csv(OUTPUT / (name + '.csv'), index=False)
        runner.validate_current_input_manifest(manifest)
        counts = Counter(row['status'] for row in baseline)
        compatible = not (set(counts) - {'matched', 'synthetic_intraday'}) and counts['matched'] > 0
        boundaries = execution_boundaries()
        original_files = json.loads((OBSERVER.parent.parent / 'input_manifest.json').read_text())['files']
        original_paths = {item['path'] for item in original_files.values()}
        missing_original = [item['path'] for key, item in manifest['files'].items()
                            if (key.startswith('execution_raw/') or key == 'execution_seed_csv')
                            and item['path'] not in original_paths]
        summary = {'stage': STAGE, 'status': 'current_legacy_prices_compatible_not_execution' if compatible else 'legacy_price_qualification_failed',
            'baseline_trade_count': len(baseline), 'baseline_status_counts': dict(counts),
            'baseline_price_source_counts': dict(Counter(row.get('price_source', 'synthetic_or_unresolved') for row in baseline)),
            'window_count': len(comparisons), 'window_legacy_source_counts': dict(Counter(row['legacy_source'] for row in comparisons)),
            'window_price_matches': sum(row['price_matches'] for row in comparisons),
            'window_time_matches': sum(row['time_matches'] for row in comparisons),
            'seed_open_map_count': len(legacy.open_map), 'seed_close_map_count': len(legacy.close_map),
            'raw_file_count': sum(key.startswith('execution_raw/') for key in manifest['files']),
            'raw_contracts_loaded': len(legacy.raw_cache), 'execution_boundaries': boundaries,
            'dependencies_absent_from_original_manifest': missing_original,
            'retroactive_input_identity_proven': False,
            'baseline_metrics_reference_only': json.loads((OBSERVER / 'receipt.json').read_text())['metrics'],
            'new_replay_count': 0, 'new_label_count': 0, 'new_model_count': 0, 'reviewer_count': 0,
            'production_write_count': 0, 'file_contract_sha256': manifest['file_contract_sha256'],
            'outputs': {name: runner._file_identity(OUTPUT / (name + '.csv')) for name in frames}}
        write_json(OUTPUT / 'summary.json', summary)
        print(json.dumps(summary, ensure_ascii=False), flush=True)
    except BaseException as exc:
        write_json(OUTPUT / 'failure.json', {'error': str(exc), 'traceback': traceback.format_exc()})
        raise


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--freeze', action='store_true')
    group.add_argument('--run', action='store_true')
    args = parser.parse_args()
    runner = configured()
    manifest = runner.build_input_manifest()
    runner.validate_input_manifest_payload(manifest)
    if args.freeze:
        payload = {key: manifest[key] for key in ('schema_version', 'stage', 'line_id', 'input_file_count',
            'input_logical_key_sha256', 'file_contract_sha256', 'runtime_contract_sha256')}
        payload['execution_authorized'] = True
        write_json(FREEZE, payload)
        print(json.dumps(payload), flush=True)
    else:
        run(runner, manifest)


if __name__ == '__main__':
    main()
