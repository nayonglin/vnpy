"""One read-only FI/state build; potential intents are not funded trades."""
from __future__ import annotations

import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
import csv
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[4]
LINE = ROOT / 'research/lines/futures_trend_triple_screen'
PROJECT = ROOT / 'examples/portfolio_backtesting'
PRIOR = LINE / 'outputs/stage005_potential_signal_demand'
A0 = LINE / 'outputs/stage001_first_screen/A0_attempt2'
OUTPUT = LINE / 'outputs/stage027_ordered_features'
SPEC = LINE / 'stages/20261018_0214_stage027_ordered_state_design.md'
START, END = '2020-01-01', '2026-10-14'
NATIVE_FIELDS = ('signal_date', 'product_vt_symbol', 'vt_symbol', 'signal',
                 'execution_trade_date')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                    allow_nan=False) + '\n')


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fields):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_native_identities(rows):
    result = {}
    for source in rows:
        row = {key: str(source[key]) for key in NATIVE_FIELDS}
        date.fromisoformat(row['signal_date'])
        if row['execution_trade_date']:
            if row['execution_trade_date'] <= row['signal_date']:
                raise ValueError('native_execution_not_after_signal')
            date.fromisoformat(row['execution_trade_date'])
        if not row['signal'].startswith(('long', 'short')):
            raise ValueError('native_direction_missing')
        key = (row['signal_date'], row['product_vt_symbol'], row['vt_symbol'])
        if key in result:
            raise ValueError('duplicate_native_identity')
        result[key] = row
    return result


class Eligibility:
    """Exact original strict-prior snapshot lookup; no inferred fu exception."""
    def __init__(self, rows, strategy):
        self.snapshots = defaultdict(set)
        for row in rows:
            if row['strategy'] != strategy:
                continue
            day = date.fromisoformat(row['eval_date']).isoformat()
            product = row['product_vt_symbol']
            if product in self.snapshots[day]:
                raise ValueError('duplicate_eligibility_product')
            self.snapshots[day].add(product)
        self.dates = sorted(self.snapshots)
        if not self.dates:
            raise ValueError('eligibility_empty')

    def allowed(self, product, effective_day):
        index = bisect_left(self.dates, effective_day) - 1
        return index < 0 or product in self.snapshots[self.dates[index]]


def local_day(text):
    value = datetime.fromisoformat(text)
    if value.tzinfo is not None:
        value = value.astimezone(ZoneInfo('Asia/Shanghai'))
    return value.date().isoformat()


def build():
    if OUTPUT.exists():
        raise FileExistsError('ordered_build_output_exists_no_repeat')
    inputs = {}

    def bind(path, expected=None):
        path = Path(path).resolve()
        found = digest(path)
        if expected is not None and found != expected:
            raise ValueError('bound_input_changed:' + str(path))
        inputs[str(path)] = found
        return path

    review_path = bind(LINE / 'outputs/stage005_independent_review/review_receipt.json')
    review = json.loads(review_path.read_text())
    if review['p0_findings'] or review['p1_findings']:
        raise ValueError('native_stream_not_accepted')
    prior_summary = json.loads(bind(PRIOR / 'summary.json',
                                   review['source_summary_sha256']).read_text())
    prior_inputs = json.loads(bind(PRIOR / 'input_manifest.json',
                                  review['source_input_manifest_sha256']).read_text())
    for name in ('potential_initial_events.csv', 'global_engine_calendar.csv'):
        bind(PRIOR / name, prior_summary['artifacts'][name])
    settings_path = bind(A0 / 'actual_strategy_settings.json',
                         prior_inputs[str(A0 / 'actual_strategy_settings.json')])
    parameters_path = bind(A0 / 'effective_parameters.json',
                           prior_inputs[str(A0 / 'effective_parameters.json')])
    settings = json.loads(settings_path.read_text())[0]['actual']
    parameters = json.loads(parameters_path.read_text())
    a0_manifest = json.loads(bind(A0 / 'input_manifest.json').read_text())
    for name in ('mapping_csv_path', 'product_universe_csv_path',
                 'ai_product_pool_eligibility_path'):
        p = Path(settings[name])
        expected = prior_inputs.get(str(p), a0_manifest.get(str(p), {}).get('sha256'))
        if not expected:
            raise ValueError('source_not_in_accepted_manifest:' + name)
        bind(p, expected)
    if settings.get('ai_product_pool_use_next_trade_date_for_entry', False):
        raise ValueError('unexpected_AI_effective_date_contract')
    database = bind(ROOT / '.vntrader/database.db',
                    prior_inputs[str(ROOT / '.vntrader/database.db')])
    if Path(str(database) + '-wal').exists() and Path(str(database) + '-wal').stat().st_size:
        raise ValueError('unexpected_database_wal')
    weekly_path = bind(LINE / 'outputs/stage001_weekly_features/weekly_daily.csv',
                       prior_inputs[str(LINE / 'outputs/stage001_weekly_features/weekly_daily.csv')])
    for p in (SPEC, Path(__file__), Path(__file__).with_name('test_stage027_build_ordered_features.py'),
              Path(__file__).with_name('stage027_ordered_state.py'),
              Path(__file__).with_name('test_stage027_ordered_state.py'),
              Path(__file__).with_name('stage001_run_first_screen.py'),
              Path(__file__).with_name('stage005_potential_signal_demand.py')):
        bind(p)
    for name in ('qmt_roll_portfolio_strategy.py', 'qmt_roll_intraday_execution.py',
                 'qmt_roll_official_ai_pool_policy.py'):
        p = PROJECT / name
        bind(p, a0_manifest[str(p)]['sha256'])

    OUTPUT.mkdir(parents=True, exist_ok=False)
    began = time.monotonic()
    write_json(OUTPUT / 'attempt_started.json', dict(started_at=datetime.now().astimezone().isoformat(),
               financial_replays=0, model_fits=0, network_calls=0))
    try:
        from stage027_ordered_state import force_index_rows, OrderedSetupMachine
        from stage001_run_first_screen import WeeklyLookup
        from stage005_potential_signal_demand import load_runtime
        load_runtime()  # frozen numerical imports only; never construct a strategy/account
        from qmt_roll_intraday_execution import effective_pricetick
        from qmt_roll_official_ai_pool_policy import official_ai_pool_snapshot_blockers

        universe = {r['product_vt_symbol'] for r in read_csv(settings['product_universe_csv_path'])
                    if int(float(r.get('eligible', '1'))) == 1}
        metadata = set(parameters['contract_sizes'])
        calendar = [r['date'] for r in read_csv(PRIOR / 'global_engine_calendar.csv')]
        if len(calendar) != len(set(calendar)) or calendar != sorted(calendar):
            raise ValueError('invalid_real_calendar')
        next_day = {day: calendar[i + 1] if i + 1 < len(calendar) else None
                    for i, day in enumerate(calendar)}
        mapping = defaultdict(dict)
        for row in read_csv(settings['mapping_csv_path']):
            product, target = row['continuous_symbol_vt'], row['main_contract_vt']
            if product in universe and target:
                key = row['date']
                if product in mapping[key] and mapping[key][product] != target:
                    raise ValueError('conflicting_main_mapping')
                mapping[key][product] = target

        eligible_rows = [r for r in read_csv(settings['ai_product_pool_eligibility_path'])
                         if r['strategy'] == settings['ai_product_pool_strategy']]
        by_eval = defaultdict(list)
        for row in eligible_rows:
            by_eval[row['eval_date']].append(row)
        for day, group in by_eval.items():
            blockers = official_ai_pool_snapshot_blockers(
                products=[r['product_vt_symbol'] for r in group],
                ranks=[r['score_rank'] for r in group], top_ns=[r['top_n'] for r in group],
                eval_date=day, score_types=[r['score_type'] for r in group])
            if blockers:
                raise ValueError('AI_snapshot_contract_invalid:' + str(blockers))
        pool = Eligibility(eligible_rows, settings['ai_product_pool_strategy'])
        native = load_native_identities(read_csv(PRIOR / 'potential_initial_events.csv'))
        if len(native) != prior_summary['raw_events']:
            raise ValueError('native_event_count_changed')
        weekly = WeeklyLookup.read(weekly_path)
        daily = []
        with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
            db.execute('PRAGMA query_only=ON')
            for row in db.execute("SELECT symbol||'.'||exchange, datetime, high_price, low_price, close_price, volume FROM dbbardata WHERE interval='d' AND datetime >= ? AND datetime <= ?",
                                  ('2019-06-01 00:00:00', END + ' 00:00:00')):
                symbol, stamp, high, low, close, volume = row
                if symbol in metadata:
                    daily.append(dict(date=local_day(stamp), vt_symbol=symbol,
                                      high=high, low=low, close=close, volume=volume))
        if sorted({r['date'] for r in daily}) != calendar:
            raise ValueError('source_real_calendar_not_identical_to_stage005')
        features = force_index_rows(daily, calendar)
        feature_fields = ['date', 'vt_symbol', 'raw_force', 'fi2', 'ready', 'reason', 'previous_date']
        write_csv(OUTPUT / 'fi2_daily.csv', features, feature_fields)
        fi = {(r['date'], r['vt_symbol']): r for r in features}
        bars = {(r['date'], r['vt_symbol']): r for r in daily}
        if len(fi) != len(features) or len(bars) != len(daily):
            raise ValueError('duplicate_daily_key')
        machines = {arm: OrderedSetupMachine(arm) for arm in ('B_TS', 'C_TS')}
        intents, fallbacks, reasons, matched = [], [], Counter(), set()
        for day in (d for d in calendar if START <= d <= END):
            for product in sorted(universe):
                target = mapping.get(day, {}).get(product, '')
                bar = bars.get((day, target))
                missing = 'missing_target_mapping' if not target else 'missing_real_target_bar'
                valid_extremes = bar and all(math.isfinite(float(bar[k])) and float(bar[k]) > 0
                                            for k in ('high', 'low')) and bar['high'] >= bar['low']
                if bar and not valid_extremes:
                    missing = 'invalid_daily_extremes'
                if not valid_extremes:
                    for arm, machine in machines.items():
                        machine.cancel(product, day, missing)
                        reasons[(arm, missing)] += 1
                    continue
                key = (day, product, target)
                event = native.get(key)
                if event:
                    matched.add(key)
                    if event['execution_trade_date'] != (next_day[day] or ''):
                        raise ValueError('native_next_trade_date_changed')
                code, exchange = product.rsplit('.', 1)
                w = weekly.get(day, f'{exchange}.{code}'.upper())
                f = fi[(day, target)]
                tick = effective_pricetick(target, next_day[day] or day,
                                          float(parameters['priceticks'][target]))
                for arm, machine in machines.items():
                    decision = machine.on_close(product=product, contract=target, day=day,
                        next_day=next_day[day], high=float(bar['high']), low=float(bar['low']),
                        tick=tick, weekly_ready=w['ready'], weekly_direction=w['direction'],
                        weekly_asof=w['weekly_asof'] or None, fi_ready=f['ready'], fi2=f['fi2'],
                        eligible=pool.allowed(product, day), position_open=False,
                        native_signal=event['signal'] if event else None)
                    reasons[(arm, decision['decision'])] += 1
                    if decision['intent']:
                        intents.append(decision['intent'])
                    if arm == 'C_TS' and event and decision['baseline_fallback']:
                        fallbacks.append(dict(**event, fallback_reason=decision['cancel_reason']))
        if matched != set(native):
            raise ValueError('not_all_accepted_native_identities_observed:' + str(len(set(native) - matched)))
        for r in intents:
            if r['arm'] == 'C_TS' and not (r['setup_day'] < r['signal_day'] < r['execution_day']):
                raise ValueError('C_ordering_violation')
        intent_fields = ['arm', 'intent_id', 'product', 'contract', 'epoch_id', 'setup_id',
                         'setup_day', 'signal_day', 'execution_day', 'direction', 'trigger',
                         'weekly_asof', 'native_signal']
        write_csv(OUTPUT / 'potential_intents.csv', intents, intent_fields)
        write_csv(OUTPUT / 'C_baseline_fallback_candidates.csv', fallbacks,
                  [*NATIVE_FIELDS, 'fallback_reason'])
        unchanged = all(digest(p) == s for p, s in inputs.items())
        if not unchanged:
            raise ValueError('consumed_inputs_changed')
        write_json(OUTPUT / 'input_manifest.json', inputs)
        result = dict(status='completed_pure_state_build_pending_independent_review',
            elapsed_seconds=time.monotonic() - began, source_daily_rows=len(daily),
            FI_ready_rows=sum(r['ready'] for r in features), real_calendar_rows=len(calendar),
            metadata_contracts=len(metadata), native_events=len(native), native_identities_matched=len(matched),
            intent_counts=dict(Counter(r['arm'] for r in intents)),
            C_baseline_fallback_candidates=len(fallbacks), decision_counts={f'{a}:{b}': n for (a, b), n in reasons.items()},
            state_start=START, feature_preload_start='2019-06-01', end=END,
            AI_effective_date_mode='signal_day_strict_prior_eval; unchanged_original_default',
            setup_consumption='not consumed: all-flat unfilled conservative potential upper bound',
            full_account_demand_or_fills=False, outcome_fields_used=0, financial_replays=0,
            model_fits=0, network_calls=0, orders=0, strategy_initializations=0,
            all_consumed_inputs_unchanged=unchanged, production_qualified=False,
            artifacts={p.name: digest(p) for p in OUTPUT.iterdir() if p.is_file()})
        write_json(OUTPUT / 'summary.json', result)
        print(json.dumps({k: result[k] for k in ('status', 'elapsed_seconds', 'source_daily_rows',
                         'native_identities_matched', 'intent_counts', 'C_baseline_fallback_candidates')}, ensure_ascii=False))
    except Exception as exc:
        write_json(OUTPUT / 'build_failure.json', dict(error=repr(exc), financial_replays=0,
                   model_fits=0, network_calls=0, accepted_financial_metrics=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true', required=True)
    parser.parse_args()
    build()
