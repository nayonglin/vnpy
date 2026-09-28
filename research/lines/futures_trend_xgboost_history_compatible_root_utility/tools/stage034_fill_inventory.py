from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import re
import sys
import traceback
from collections import Counter, defaultdict
from decimal import Decimal
from itertools import groupby
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = 'stage034_fill_inventory'
OUTPUT = ROOT / 'artifacts' / STAGE
SOURCE = ROOT / 'artifacts/stage033_holding_observer'
CONTRACT = ROOT / 'stages/20260906_0835_stage034_fill_inventory_contract.md'
FREEZE = ROOT / 'stages/stage034_input_freeze.json'
TOLERANCE = Decimal('0.0000001')
SUMMARY_SHA = 'd4567a19da9364e4f855006ce0c86467c60d88a0ce398ec7506a81e359345069'


def load(name):
    spec = importlib.util.spec_from_file_location('inventory_' + name, ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = value
    spec.loader.exec_module(value)
    return value


def number(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError('inventory_nonfinite')
    return result


class Inventory:
    def __init__(self):
        self.quantity = Decimal(0)
        self.average = Decimal(0)
        self.realized = Decimal(0)
        self.cashflow = Decimal(0)
        self.source_ids = []

    def apply(self, trade):
        direction = {'long': 1, 'short': -1, '\u591a': 1, '\u7a7a': -1}.get(trade['direction'])
        offset = {'open': 'open', 'close': 'close', '\u5f00': 'open', '\u5e73': 'close'}.get(trade['offset'])
        price, volume = number(trade['price']), number(trade['volume'])
        if direction is None or offset is None or price <= 0 or volume <= 0 or volume != volume.to_integral_value():
            raise ValueError('inventory_fill_invalid')
        signed = volume * direction
        if number(trade['signed_volume']) != signed:
            raise ValueError('inventory_signed_volume_invalid')
        if offset == 'open':
            if self.quantity * signed < 0:
                raise ValueError('inventory_opposite_open')
            self.average = (abs(self.quantity) * self.average + volume * price) / (abs(self.quantity) + volume)
        else:
            if self.quantity * signed >= 0 or volume > abs(self.quantity):
                raise ValueError('inventory_overclose_or_wrong_direction')
            sign = 1 if self.quantity > 0 else -1
            self.realized += sign * volume * (price - self.average)
        self.quantity += signed
        self.cashflow -= signed * price
        self.source_ids.append(trade['trade_id'])
        if not self.quantity:
            self.average = Decimal(0)
            self.source_ids = []


def ordered_trades(trades):
    values = []
    for row in trades:
        match = re.fullmatch(r'BACKTESTING\.([1-9][0-9]*)', row['trade_id'])
        if not match or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', row['date']) or row['datetime'][:10] != row['date']:
            raise ValueError('inventory_trade_identity_invalid')
        values.append((int(match[1]), row))
    values.sort(key=lambda value: value[0])
    if [value[0] for value in values] != list(range(1, len(values) + 1)):
        raise ValueError('inventory_trade_sequence_incomplete')
    rows = [value[1] for value in values]
    if [row['date'] for row in rows] != sorted(row['date'] for row in rows):
        raise ValueError('inventory_trade_date_regression')
    return rows


def reconcile(trades, position_rows, sizes):
    trades = ordered_trades(trades)
    by_date = defaultdict(list)
    for trade in trades:
        by_date[trade['date']].append(trade)
    book, previous_gross = {}, defaultdict(Decimal)
    records, daily, maximum, row_count = [], {}, Decimal(0), 0
    last_key = None
    for day, group in groupby(position_rows, key=lambda row: row['date']):
        before = {symbol: item.quantity for symbol, item in book.items()}
        today = by_date.pop(day, [])
        required = {symbol for symbol, quantity in before.items() if quantity} | {row['vt_symbol'] for row in today}
        for trade in today:
            book.setdefault(trade['vt_symbol'], Inventory()).apply(trade)
        seen, day_net = set(), Decimal(0)
        for row in group:
            symbol = row['vt_symbol']
            key = (day, symbol)
            if last_key is not None and key <= last_key:
                raise ValueError('inventory_position_identity_invalid')
            last_key = key
            row_count += 1
            seen.add(symbol)
            if symbol not in sizes or number(sizes[symbol]) <= 0:
                raise ValueError('inventory_contract_unit_missing')
            unit = number(sizes[symbol])
            item = book.get(symbol, Inventory())
            start, end = number(row['start_pos']), number(row['end_pos'])
            if start != before.get(symbol, 0) or end != item.quantity:
                raise ValueError(f'inventory_position_mismatch:{day}:{symbol}')
            close = number(row['close_price'])
            if (start or end or symbol in required) and close <= 0:
                raise ValueError('inventory_mark_price_invalid')
            gross = (item.cashflow + item.quantity * close) * unit
            inventory_gross = (item.realized + item.quantity * (close - item.average)) * unit
            cost = number(row['commission']) + number(row['slippage'])
            if cost < 0:
                raise ValueError('inventory_negative_cost')
            net = gross - previous_gross[symbol] - cost
            previous_gross[symbol] = gross
            error = max(abs(net - number(row['net_pnl'])), abs(gross - inventory_gross))
            maximum = max(maximum, error)
            if error > TOLERANCE:
                raise ValueError(f'inventory_pnl_mismatch:{day}:{symbol}:{error}')
            day_net += net
            if item.quantity:
                records.append({'date': day, 'vt_symbol': symbol, 'quantity': str(item.quantity),
                    'average_entry_price': str(item.average), 'source_trade_ids': list(item.source_ids),
                    'realized_price_quantity': str(item.realized), 'unrealized_price_quantity': str(item.quantity * (close - item.average)),
                    'last_processed_trade_id': today[-1]['trade_id'] if today else None})
        if required - seen:
            raise ValueError('inventory_position_coverage_missing')
        daily[day] = day_net
    if by_date:
        raise ValueError('inventory_trade_day_not_in_ledger')
    return records, daily, {'trade_count': len(trades), 'position_rows': row_count,
        'nonzero_contract_days': len(records), 'max_pnl_error': float(maximum)}


def cost_state(row, inventory):
    quantities = {symbol: float(number(item['quantity'])) for symbol, item in inventory.items() if number(item['quantity'])}
    if quantities != row['actual_positions']:
        raise ValueError('inventory_snapshot_position_mismatch')
    if row['state_status'] not in {'stable_holding', 'layer_not_synchronized'}:
        return row['state_status']
    if len(inventory) != 1 or any(number(item['average_entry_price']) <= 0 or not item['source_trade_ids'] for item in inventory.values()):
        raise ValueError('inventory_current_cost_missing')
    if any(number(layer['entry_price']) <= 0 for layer in row['layers']):
        return 'invalid_strategy_layer_price'
    return 'inventory_reconciled_holding'


def collect_inputs():
    observer = load('stage033_holding_observer')
    files = observer.collect_inputs()
    files.update(inventory_runner=Path(__file__).resolve(), inventory_contract=CONTRACT,
        inventory_tests=ROOT / 'tests/test_stage034_fill_inventory.py',
        holding_observer_input_manifest=SOURCE / 'input_manifest.json', holding_observer_freeze=observer.FREEZE,
        holding_observer_summary=SOURCE / 'summary.json', holding_population_runner=ROOT / 'tools/stage033b_holding_population.py',
        holding_population_summary=ROOT / 'artifacts/stage033b_holding_population/summary.json')
    for name in ('receipt.json', 'observer_receipt.json', 'archive_receipt.json', 'holding_states.json.gz'):
        files['holding_source_' + name] = SOURCE / 'workers/A' / name
    for name in ('daily','positions','trades','entry_candidates','entry_risk','root_features','stop_retry_events'):
        files['holding_frame_' + name] = SOURCE / 'workers/A' / (name + '.csv.gz')
    return dict(sorted(files.items()))


def configured():
    _, runner = load('stage033_holding_observer').configured(input_count=len(collect_inputs()))
    runner.STAGE = STAGE
    runner.collect_input_files = collect_inputs
    return runner


def load_sources(manifest):
    import pandas as pd
    observer = load('stage033_holding_observer')
    _, original = observer.configured()
    source_manifest = json.loads((SOURCE / 'input_manifest.json').read_text())
    original.validate_current_input_manifest(source_manifest)
    original.validate_frozen_input_contract(observer.FREEZE, source_manifest)
    if hashlib.sha256((SOURCE / 'summary.json').read_bytes()).hexdigest() != SUMMARY_SHA:
        raise ValueError('inventory_observer_summary_changed')
    summary = json.loads((SOURCE / 'summary.json').read_text())
    root = SOURCE / 'workers/A'
    receipt = json.loads((root / 'observer_receipt.json').read_text())
    worker = json.loads((root / 'receipt.json').read_text())
    if (original._file_identity(root / 'holding_states.json.gz') != receipt['trace_identity']
            or original._file_identity(root / 'observer_receipt.json') != summary['observer_receipt_identity']
            or hashlib.sha256((root / 'receipt.json').read_bytes()).hexdigest() != summary['worker_receipt_sha256']):
        raise ValueError('inventory_observer_identity_changed')
    raw = gzip.decompress((root / 'holding_states.json.gz').read_bytes())
    if hashlib.sha256(raw).hexdigest() != receipt['raw_sha256']:
        raise ValueError('inventory_raw_observer_changed')
    rows = json.loads(raw)
    collector = load('stage005_label_collection')
    for name, item in json.loads((root / 'archive_receipt.json').read_text()).items():
        collector.verify_archive(root / (name + '.csv.gz'), item)
    daily = pd.read_csv(root / 'daily.csv.gz', float_precision='round_trip')
    columns = ['date','vt_symbol','start_pos','end_pos','close_price','commission','slippage','net_pnl']
    positions = pd.read_csv(root / 'positions.csv.gz', usecols=columns, dtype=str, keep_default_na=False)
    if observer.qualify_trace(rows, daily, positions.assign(end_pos=pd.to_numeric(positions.end_pos))) != summary['qualification']:
        raise ValueError('inventory_observer_qualification_changed')
    trades = pd.read_csv(root / 'trades.csv.gz', dtype=str, keep_default_na=False)
    batch = load('stage004_label_batch')
    resolver_path = Path(manifest['files']['production_portfolio/contract_metadata.py']['path'])
    resolver = batch.load('inventory_unit_resolver', resolver_path)
    mapping = worker['contract_products']
    symbols = sorted(mapping)
    resolved = resolver.build_resolved_metadata(symbols, {s: 0 for s in symbols}, {s: 0 for s in symbols},
        {s: 0 for s in symbols}, mapping, Path(manifest['files']['contract_metadata']['path']))
    if any(value <= 0 for value in resolved['sizes'].values()) or set(resolved['metadata_sources'].values()) != {'tqsdk'}:
        raise ValueError('inventory_original_units_unresolved')
    return rows, daily, positions.sort_values(['date','vt_symbol']), trades, mapping, resolved['sizes']


def run():
    import pandas as pd
    if OUTPUT.exists():
        raise RuntimeError('inventory_campaign_already_exists')
    runner = configured()
    manifest = runner.build_input_manifest()
    runner.validate_frozen_input_contract(FREEZE, manifest)
    batch = load('stage004_label_batch')
    batch.verify_baseline_inputs(manifest)
    OUTPUT.mkdir(mode=0o700)
    batch.write_json(OUTPUT / 'input_manifest.json', manifest)
    try:
        rows, daily, positions, trades, mapping, sizes = load_sources(manifest)
        inventory, net_by_date, quality = reconcile(trades.to_dict('records'), positions.to_dict('records'), sizes)
        errors = [abs(number(row.net_pnl) - net_by_date[row.date]) for row in daily.itertuples()]
        if max(errors) > TOLERANCE or any(value for day, value in net_by_date.items() if day < daily.date.iloc[0]):
            raise ValueError('inventory_account_reconciliation_failed')
        quality['max_account_daily_error'] = float(max(errors))
        by_key = defaultdict(dict)
        for item in inventory:
            by_key[(item['date'], mapping[item['vt_symbol']])][item['vt_symbol']] = item
        state_rows, compatible_rows = [], []
        for row in rows:
            costs = by_key[(row['date'], row['product_vt_symbol'])]
            status = cost_state(row, costs)
            state_rows.append({'date': row['date'], 'product_vt_symbol': row['product_vt_symbol'],
                'source_state_status': row['state_status'], 'inventory_state_status': status,
                'contract_costs': costs})
            # The old grouping helper uses this name only to count eligible days.
            compatible_rows.append({**row, 'state_status': 'stable_holding' if status == 'inventory_reconciled_holding' else row['state_status']})
        population = load('stage033b_holding_population')
        events = pd.read_csv(ROOT / 'artifacts/stage003_cancelled_lifecycle/event_lifecycles.csv', dtype=str, keep_default_na=False)
        linked, roots = population.group_roots(compatible_rows, events)
        cutoffs = [str(month.date()) for month in pd.date_range(daily.date.iloc[0][:7]+'-01',daily.date.iloc[-1],freq='MS')]
        months = population.monthly_population(roots, cutoffs)
        headroom = batch.load('inventory_headroom', batch.V4 / 'tools/stage007_objective_headroom_audit.py')
        geometry = headroom.objective_headroom(daily, roots[roots.stable_observation_days.gt(0)], population.MIN_ROOTS)
        roots = roots.rename(columns={'stable_observation_days':'inventory_eligible_days',
            'first_stable_date':'first_inventory_eligible_date','last_stable_date':'last_inventory_eligible_date'})
        runner.validate_current_input_manifest(manifest)
        outputs = {}
        for name, value in [('inventory',inventory), ('holding_cost_states',state_rows)]:
            path = OUTPUT / (name + '.json.gz')
            raw = json.dumps(value, separators=(',',':'), allow_nan=False).encode()
            runner._write_bytes_exclusive(path, gzip.compress(raw, mtime=0))
            outputs[name] = {'compressed':runner._file_identity(path), 'raw_sha256':hashlib.sha256(raw).hexdigest()}
        for name, value in [('root_population',roots), ('monthly_population',months)]:
            path = OUTPUT / (name + '.csv')
            runner._write_bytes_exclusive(path, value.to_csv(index=False).encode())
            outputs[name] = runner._file_identity(path)
        summary = {'stage':STAGE, 'status':'inventory_reconciled_not_execution_or_model', 'quality':quality,
            'state_counts':dict(Counter(row['inventory_state_status'] for row in state_rows)),
            'roots_with_inventory_observations':int(roots.inventory_eligible_days.gt(0).sum()),
            'mature_roots_with_inventory_observations':int((roots.status.eq('mature') & roots.inventory_eligible_days.gt(0)).sum()),
            **geometry, 'source_file_contract_sha256':manifest['file_contract_sha256'], 'outputs':outputs,
            'new_strategy_replay_count':0,'new_utility_label_count':0,'model_fit_predict_count':0,'reviewer_started':False}
        batch.write_json(OUTPUT / 'summary.json', summary)
        print(json.dumps({key:value for key,value in summary.items() if key!='outputs'}), flush=True)
    except BaseException as exc:
        batch.write_json(OUTPUT / 'failure.json', {'status':'failed','error':str(exc),'traceback':traceback.format_exc()})
        raise


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze',action='store_true')
    mode.add_argument('--run',action='store_true')
    args = parser.parse_args()
    if args.freeze:
        runner = configured()
        manifest = runner.build_input_manifest()
        runner.validate_input_manifest_payload(manifest)
        load('stage004_label_batch').verify_baseline_inputs(manifest)
        payload = {key:manifest[key] for key in ('schema_version','stage','line_id','input_file_count',
            'input_logical_key_sha256','file_contract_sha256','runtime_contract_sha256')}
        payload['execution_authorized'] = True
        load('stage004_label_batch').write_json(FREEZE,payload)
        print(json.dumps(payload),flush=True)
    else:
        run()


if __name__ == '__main__':
    main()
