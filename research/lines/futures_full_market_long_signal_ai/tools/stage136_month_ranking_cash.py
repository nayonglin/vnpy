"""Frozen Stage134: 84 new positive-pool controls using exact132 cached arrays.

Imports and synthetic fixtures perform no native query, fit, label construction,
download or actual account run. Actual execution requires exact root source and
input bindings plus a fresh output; old AI books are references, never replayed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
PROTOCOL_SHA = '25ad088a36d4aa3a022e7da7e818902e62b1c7c922b85aae3c31ad960c780e62'
POLICIES = ('MAX_VOLUME_POS',) + tuple(f'RANDOM_POS_{i:02d}' for i in range(20))
RANDOM_POLICIES = POLICIES[1:]
WINDOWS = ('primary_2020', 'cold_2023')
COSTS = ('base', 'stress')
FIXED_ROLES = ('market_protocol', 'dataset_manifest', 'actions', 'mothers', 'fit_manifest',
    'child_scores', 'choices_main', 'choices_holdout', 'baseline_cash_manifest', 'accepted_review',
    'accepted_review_terminal', 'native_cache_manifest', 'native_cache')
INPUT_ROLES = FIXED_ROLES + ('attribution_manifest', 'overrides')
ACTION_FIELDS = ['action_id', 'event_id', 'action_sequence_index', 'mother_sequence_index',
    'mother_event_id', 'product_id', 'family_id', 'u_date', 'u_index', 'reference_epoch',
    'anchor_epoch', 'u_action_eligible', 'entry_capacity_qty', 'N_u', 'low20_u', 'u_close']
OVERRIDE_FIELDS = ['control_id', 'scope', 'cutoff', 'mother_sequence_index', 'mother_event_id',
    'product_id', 'family_id', 'u_date', 'u_index', 'chosen_action_id', 'chosen_action_sequence_index',
    'chosen_epoch', 'anchor_epoch', 'score', 'u_volume', 'rule_key']
IDENTITY = ['sequence_index', 'event_id', 'product_id', 'family_id', 'u_date', 'u_index', 'reference_epoch']


def load(name, identity):
    spec = importlib.util.spec_from_file_location(identity, TOOLS/name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


author = load('stage131_contract_choice_cash.py', 'cash136_accepted131')
cache_source = load('stage132_contract_choice_review.py', 'cash136_accepted132_cache')
kernel, ref = author.kernel, author.ref
helpers, report_helpers = author.helpers, author.report_helpers
diagnostics = helpers.diagnostics


def source_bundle():
    paths = {b['path'] for b in author.source_bundle()}
    paths.update(str(TOOLS/n) for n in ('stage136_month_ranking_cash.py',
        'test_stage136_month_ranking_cash.py', 'stage132_contract_choice_review.py',
        'stage102_cash_adapter.py', 'stage102_cash_core.py', 'stage102_cash_diagnostics.py'))
    return sorted((ref.file_binding(p) for p in paths), key=lambda b: b['path'])


def verify_file(item):
    """Verify a needed compressed artifact once without retaining all raw bytes."""
    p = Path(item['path'])
    if p.stat().st_size != item['bytes']:
        raise ValueError('bound file size changed '+str(p))
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    if h.hexdigest() != item['sha256']:
        raise ValueError('bound file hash changed '+str(p))


def read_json(item):
    return json.loads(ref.read_bound(item))


def numeric(frame, columns):
    for column in columns:
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors='raise')
    return frame


class CachedMarket:
    """Thin accepted131 interface over already-computed accepted132 arrays."""
    def __init__(self, store):
        self.store, self.dates = store, store.calendar
        self.series = store.series

    def bar(self, epoch, k):
        j = self.store.locate(epoch, k)
        if j is None or not self.series[epoch]['valid'][j]:
            return None
        O, H, L, C, V = self.series[epoch]['values'][j]
        return dict(open=float(O), high=float(H), low=float(L), close=float(C), volume=float(V))

    def indicator(self, epoch, k):
        j = self.store.locate(epoch, k)
        if j is None or not self.series[epoch]['valid'][j]:
            return dict(N=math.nan, run_length=0, low20=math.nan, high55_before=math.nan)
        s = self.series[epoch]
        return dict(N=float(s['N'][j]), run_length=int(s['run'][j]),
            low20=float(s['low20'][j]), high55_before=math.nan)


def make_control_signals(overrides, mothers, actions, market, dates, economics):
    """Selected-only interface; the complete parent population stays in 135/base."""
    if (overrides.empty or set(overrides.scope) != {'main'}
            or overrides.control_id.nunique() != 1 or overrides.mother_event_id.duplicated().any()):
        raise ValueError('one nonempty unique main control required')
    control = str(overrides.control_id.iloc[0])
    if control not in POLICIES:
        raise ValueError('unknown fixed cash control')
    part = overrides.reset_index(drop=True)
    parent_index = mothers.set_index('event_id', drop=False, verify_integrity=True)
    try:
        parents = parent_index.loc[part.mother_event_id].reset_index(drop=True).copy()
    except KeyError as exc:
        raise ValueError('selected control parent missing') from exc
    for left, right in (('mother_sequence_index', 'sequence_index'), ('product_id', 'product_id'),
                       ('family_id', 'family_id'), ('u_date', 'u_date'), ('u_index', 'u_index'),
                       ('anchor_epoch', 'reference_epoch')):
        if part[left].tolist() != parents[right].tolist():
            raise ValueError('control changed parent '+left)
    for column in ('chosen_action_id', 'chosen_action_sequence_index', 'chosen_epoch',
                   'anchor_epoch', 'score', 'scope', 'cutoff'):
        parents[column] = part[column].to_numpy()
    parents['selected'], parents['arm'], parents['policy'] = 1, 'B', 'NARROW'
    ids = set(part.chosen_action_id)
    children = actions.loc[actions.action_id.isin(ids)].copy()
    result = author.make_signals(children, parents[IDENTITY], parents, 'B', market, dates, economics)
    result['control_id'], result['arm'] = control, control
    if len(result) != len(part):
        raise ValueError('selected overrides lost cash signals')
    return result


def _log_path(frame):
    result = frame.copy()
    if 'ever_insolvent' in result:
        def boolean(value):
            if isinstance(value, (bool, np.bool_)):
                return bool(value)
            if str(value).lower() in ('true', '1'):
                return True
            if str(value).lower() in ('false', '0'):
                return False
            raise ValueError('unknown saved insolvency boolean')
        result['ever_insolvent'] = result.ever_insolvent.map(boolean)
    return diagnostics.daily_log_growth(result, ref.INITIAL)


def paired_log_contrast(ai, controls, indices):
    """AI dailylog minus the arithmetic mean of every required control dailylog."""
    if not controls:
        raise ValueError('empty reference ensemble')
    dates = ai.date.tolist()
    if any(frame.date.tolist() != dates for frame in controls.values()):
        raise ValueError('paired source calendar differs')
    index = np.asarray(indices)
    if (index.ndim != 2 or index.shape != (2000, len(dates)) or index.dtype.kind not in 'iu'
            or index.min() < 0 or index.max() >= len(dates)):
        raise ValueError('original 2000 source-block index matrix required')
    al, ast = _log_path(ai)
    paths, bad, states = [], [], {}
    for name, frame in controls.items():
        log, state = _log_path(frame)
        states[name] = state
        if log is None:
            bad.append(name)
        else:
            paths.append(log)
    common = dict(control_count=len(controls), AI_log_status=ast, control_log_status=states,
        invalid_control_ids=bad, no_seed_dropped=True, epsilon_log_repair=False,
        bootstrap_repetitions=2000, block_length=252, indices_regenerated=False)
    if al is None or bad:
        return dict(common, status='survival_failure_no_log_repair', mean_daily_log_difference=None,
            cumulative_log_difference=None, ci95_low=None, ci95_high=None), np.full(2000, np.nan)
    difference = al-np.mean(np.vstack(paths), axis=0)
    distribution = difference[index].mean(axis=1)
    low, high = np.quantile(distribution, [.025, .975])
    return dict(common, status='valid', mean_daily_log_difference=float(difference.mean()),
        cumulative_log_difference=float(difference.sum()), ci95_low=float(low), ci95_high=float(high)), distribution


LEDGER_KEYS = dict(fills='fills', reservations='budgets', daily='daily', positions='position_days',
    closed='closed_episodes', open='open_episodes', capacity_audit='capacity_audit',
    entry_execution_unknown='entry_execution_unknown')


def write_ledgers(folder, book):
    folder.mkdir(parents=True, exist_ok=True)
    result = {}
    for role, key in LEDGER_KEYS.items():
        empty = author.EMPTY_COLUMNS.get(key, ['account_id', 'scenario', 'date', 'equity', 'ever_insolvent'])
        path = folder/(role+'.csv.gz')
        ref.write_table(path, book[key], empty)
        result[role] = ref.file_binding(path)
    path = folder/'rejections.csv.gz'
    ref.write_table(path, [r for r in book['budgets'] if r.get('D_qty', 0) == 0], helpers.EMPTY_COLUMNS['budgets'])
    result['rejections'] = ref.file_binding(path)
    return result


def authorize(args):
    output = Path(args.output).resolve()
    if output.exists():
        raise FileExistsError('fresh output required; retain failures '+str(output))
    allowed = LINE/'outputs/stage136_month_ranking_cash'
    if allowed not in output.parents:
        raise ValueError('fresh Stage136 output directory required')
    pb = ref.file_binding(args.protocol)
    if args.protocol_sha256 != PROTOCOL_SHA or pb['sha256'] != PROTOCOL_SHA:
        raise ValueError('frozen134 protocol SHA required')
    protocol = read_json(pb)
    if (protocol.get('schema') != 'stage134_month_ranking_attribution_protocol_v1'
            or protocol.get('stage') != 134 or protocol.get('line_id') != LINE.name):
        raise ValueError('134 protocol identity differs')
    ab = ref.file_binding(args.authorization)
    if ab['sha256'] != args.authorization_sha256:
        raise ValueError('authorization SHA differs')
    auth = read_json(ab)
    expected = dict(schema='stage134_exact_root_authorization_v1', authorized_by='root', stage='cash',
        exact_source_authorized=True, protocol_sha256=PROTOCOL_SHA, output=str(output))
    if any(auth.get(k) != v for k, v in expected.items()):
        raise ValueError('exact root cash authorization required')
    if sorted(auth.get('source_bundle', []), key=lambda b: b['path']) != source_bundle():
        raise ValueError('authorized source/tests bundle differs')
    inputs = auth.get('input_bindings', {})
    if set(inputs) != set(INPUT_ROLES):
        raise ValueError('exact13 protocol inputs plus attribution_manifest/overrides required')
    for role in FIXED_ROLES:
        author.same_binding(inputs[role], protocol['inputs'][role], role)
    for item in protocol['source_bindings']:
        author.same_binding(ref.file_binding(item['path']), item, 'accepted pure source')
    risk = protocol['fixed']['risk']
    actual = (ref.INITIAL, ref.SINGLE_RISK, ref.TOTAL_RISK, ref.MARGIN_CAP, ref.MARGIN_BUFFER)
    expected_risk = tuple(risk[k] for k in ('initial_equity', 'single_family_risk', 'total_risk',
        'buffered_margin_cap', 'margin_buffer'))
    if actual != expected_risk or risk['initial_stop_N'] != .25:
        raise ValueError('frozen cash risk constants differ')
    if (tuple(protocol['cash']['policies']) != POLICIES or protocol['cash']['new_accounts_max'] != 84
            or protocol['cash']['native_SQL'] != 0 or protocol['cash']['old_AI_books_replayed'] != 0):
        raise ValueError('fixed21 controls/84new accounts/zero SQL and old replay required')
    return protocol, pb, auth, ab


def validate_upstream(protocol, inputs):
    dataset, fit, baseline = (read_json(inputs[r]) for r in ('dataset_manifest', 'fit_manifest', 'baseline_cash_manifest'))
    for manifest, schema in ((dataset, 'stage129_contract_choice_dataset_v1'),
                             (fit, 'stage130_contract_choice_fit_v1'),
                             (baseline, 'stage131_contract_choice_cash_v1')):
        if manifest.get('schema') != schema or manifest.get('status') != 'completed' or manifest.get('mode') != 'actual':
            raise ValueError('completed actual129/130/131 evidence required')
    for role in ('actions', 'mothers'):
        author.same_binding(dataset[role], inputs[role], 'dataset '+role)
    for role in ('child_scores', 'choices_main', 'choices_holdout'):
        author.same_binding(fit[role], inputs[role], 'fit '+role)
    accepted, terminal = read_json(inputs['accepted_review']), read_json(inputs['accepted_review_terminal'])
    if accepted.get('completed') is not True or (accepted.get('C'), accepted.get('I')) != (0, 0):
        raise ValueError('accepted132 review required')
    if terminal.get('status') != 'completed' or terminal.get('exit_code') != 0:
        raise ValueError('accepted132 terminal required')
    attribution = read_json(inputs['attribution_manifest'])
    if (attribution.get('schema') != 'stage135_month_ranking_attribution_v1'
            or attribution.get('status') != 'completed' or attribution.get('mode') != 'actual'
            or attribution.get('protocol', {}).get('sha256') != PROTOCOL_SHA):
        raise ValueError('completed actual135 under frozen134 required')
    author.same_binding(attribution['overrides'], inputs['overrides'], '135 overrides')
    for role in FIXED_ROLES:
        author.same_binding(attribution['input_bindings'][role], inputs[role], '135 source '+role)
    at = read_json(attribution['terminal'])
    if at.get('status') != 'completed' or at.get('exit_code') != 0:
        raise ValueError('completed135 terminal required')
    cache = read_json(inputs['native_cache_manifest'])
    author.same_binding(cache['file'], inputs['native_cache'], '132 cached arrays')
    if cache.get('schema') != 'stage132_native_store_recovery_cache_v1':
        raise ValueError('exact132 recovery cache required')
    return attribution, baseline


def read_selected_actions(item, ids):
    verify_file(item)
    frames = []
    for chunk in pd.read_csv(item['path'], compression='gzip', usecols=ACTION_FIELDS,
            dtype=str, keep_default_na=False, chunksize=100000, float_precision='round_trip'):
        selected = chunk.loc[chunk.action_id.isin(ids)].copy()
        if len(selected):
            frames.append(selected)
    if not frames:
        raise ValueError('no selected source actions')
    result = pd.concat(frames, ignore_index=True)
    numeric(result, ['action_sequence_index', 'mother_sequence_index', 'u_index', 'u_action_eligible',
        'entry_capacity_qty', 'N_u', 'low20_u', 'u_close'])
    if result.action_id.duplicated().any() or set(result.action_id) != set(ids):
        raise ValueError('every selected action must be an exact unique source child')
    return result


def load_selected_inputs(inputs):
    verify_file(inputs['mothers'])
    mothers = pd.read_csv(inputs['mothers']['path'], dtype=str, keep_default_na=False, usecols=IDENTITY)
    numeric(mothers, ['sequence_index', 'u_index'])
    if len(mothers) != 399252 or mothers.event_id.duplicated().any():
        raise ValueError('complete source mothers required for canonical reference schedule')
    verify_file(inputs['choices_main'])
    base = pd.read_csv(inputs['choices_main']['path'], dtype=str, keep_default_na=False,
        usecols=IDENTITY+['selected', 'arm', 'scope', 'cutoff'])
    numeric(base, ['sequence_index', 'u_index', 'selected'])
    base = base.loc[base.arm.eq('B') & base.selected.eq(1)].copy()
    verify_file(inputs['overrides'])
    overrides = pd.read_csv(inputs['overrides']['path'], dtype=str, keep_default_na=False,
        usecols=OVERRIDE_FIELDS, float_precision='round_trip')
    overrides = overrides.loc[overrides.scope.eq('main')].copy()
    numeric(overrides, ['mother_sequence_index', 'u_index', 'chosen_action_sequence_index', 'score', 'u_volume'])
    if set(overrides.control_id) != set(POLICIES) or overrides.duplicated(['control_id', 'mother_event_id']).any():
        raise ValueError('one main override for every source B selected parent/control required')
    original = base.set_index('event_id', verify_integrity=True)
    for control in POLICIES:
        part = overrides.loc[overrides.control_id.eq(control)].set_index('mother_event_id')
        if set(part.index) != set(original.index):
            raise ValueError('changed B prospective selected parent set '+control)
        aligned = original.reindex(part.index)
        for left, right in (('mother_sequence_index', 'sequence_index'), ('product_id', 'product_id'),
                ('family_id', 'family_id'), ('u_date', 'u_date'), ('u_index', 'u_index'),
                ('scope', 'scope'), ('cutoff', 'cutoff'), ('anchor_epoch', 'reference_epoch')):
            if part[left].tolist() != aligned[right].tolist():
                raise ValueError('control changed source B winning parent '+control+'/'+left)
        if not np.isfinite(part.score).all() or not part.score.gt(0).all():
            raise ValueError('negative/nonfinite cash score forbidden')
    actions = read_selected_actions(inputs['actions'], set(overrides.chosen_action_id))
    return mothers, overrides, actions, len(base)


def artifact(manifest, logical_name):
    found = [b for b in manifest['artifacts'] if b.get('logical_name') == logical_name]
    if len(found) != 1:
        raise ValueError('exact baseline artifact not found '+logical_name)
    return {k: found[0][k] for k in ('path', 'bytes', 'sha256')}


def baseline_references(manifest):
    result, summaries, daily = {}, {}, {}
    diag_binding = artifact(manifest, 'diagnostics.json')
    for window in WINDOWS:
        for cost in COSTS:
            name = f'NARROW_B_{window}_{cost}'
            sb = artifact(manifest, name+'/summary.json')
            db = artifact(manifest, name+'/daily.csv.gz')
            summary = read_json(sb)
            frame = pd.read_csv(io.BytesIO(ref.read_bound(db)), compression='gzip')
            key = (window, cost)
            summaries[key], daily[key] = summary, frame
            result[window+'_'+cost] = dict(window=window, cost=cost, account_id=name, summary=sb, daily=db,
                diagnostics=diag_binding, diagnostic_key=name,
                source_only=True, replayed=False)
    return result, summaries, daily


def compare_accounts(summaries, daily, ai_summaries, ai_daily, indices):
    points, distributions, ranks = [], {}, []
    for window in WINDOWS:
        for cost in COSTS:
            ai = ai_daily[(window, cost)]
            for contrast, controls in (('AI_minus_MAX_VOLUME_POS', ('MAX_VOLUME_POS',)),
                    ('AI_minus_RANDOM_POS_mean20', RANDOM_POLICIES)):
                references = {name: daily[(name, window, cost)] for name in controls}
                stats, dist = paired_log_contrast(ai, references, indices[window])
                unknown = bool(ai_summaries[(window, cost)]['execution_unknown']
                    or ai_summaries[(window, cost)]['stale_positions']
                    or ai.stale_positions.gt(0).any()
                    or any(summaries[(name, window, cost)]['execution_unknown']
                        or summaries[(name, window, cost)]['any_historical_stale'] for name in controls))
                point = dict(window=window, cost=cost, contrast=contrast, **stats,
                    AI_total_return_pct=ai_summaries[(window, cost)]['total_return_pct'],
                    AI_max_drawdown_pct=ai_summaries[(window, cost)]['max_drawdown_pct'],
                    AI_sharpe=ai_summaries[(window, cost)]['sharpe'], financial_unknown=unknown,
                    conditional_positive_pool_only=True, no_promotion=True)
                if len(controls) == 1:
                    reference = summaries[(controls[0], window, cost)]
                    point.update(reference_total_return_pct=reference['total_return_pct'],
                        reference_max_drawdown_pct=reference['max_drawdown_pct'],
                        return_percentage_point_difference=point['AI_total_return_pct']-reference['total_return_pct'],
                        drawdown_percentage_point_difference=point['AI_max_drawdown_pct']-reference['max_drawdown_pct'])
                points.append(point)
                distributions[window+'_'+cost+'_'+contrast] = dist
            values = [summaries[(name, window, cost)]['total_return_pct'] for name in RANDOM_POLICIES]
            ai_return = ai_summaries[(window, cost)]['total_return_pct']
            finite = all(ref.finite(v) for v in values+[ai_return])
            ranks.append(dict(window=window, cost=cost, controls=list(RANDOM_POLICIES), seed_count=20,
                status='descriptive_only' if finite else 'unknown_return_rank',
                random_returns_below_AI=None if not finite else sum(v < ai_return for v in values),
                random_returns_equal_AI=None if not finite else sum(v == ai_return for v in values),
                AI_percentile_fraction=None if not finite else sum(v < ai_return for v in values)/20.,
                not_p_value=True, no_best_seed_selection=True, unseen_OOS=False))
    return points, distributions, ranks


def execute(args):
    protocol, pb, auth, ab = authorize(args)
    inputs = auth['input_bindings']
    attribution, baseline_manifest = validate_upstream(protocol, inputs)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    started_at, clock = datetime.now(timezone.utc).isoformat(), time.monotonic()
    before = source_bundle()
    started, completed, status, error = 0, 0, 'failed', None
    accounts, signal_bindings, reports, summaries, daily, family_tables, capacities = [], {}, {}, {}, {}, [], []
    ref.write_json(out/'actual_started.json', dict(stage='cash', status='started', started_at=started_at,
        protocol=pb, authorization=ab, source_bundle=before, fixture=False))
    try:
        mothers, overrides, actions, selected_count = load_selected_inputs(inputs)
        store, native_receipt, _ = cache_source.restore_native_cache(inputs['native_cache_manifest'])
        if native_receipt['native_source_queries'] != 0:
            raise ValueError('no native SQL authorized')
        market, dates = CachedMarket(store), store.calendar
        market_protocol = read_json(inputs['market_protocol'])
        economics = read_json(market_protocol['economic_projection'])['instruments']
        families = sorted(mothers.family_id.unique())
        if len(families) != 95 or set(economics) != set(store.series):
            raise ValueError('fixed95 families and exact cached economics required')
        indices = {w: np.load(io.BytesIO(ref.read_bound(protocol['bootstrap_indices'][w])), allow_pickle=False) for w in WINDOWS}
        baseline_books, ai_summaries, ai_daily = baseline_references(baseline_manifest)
        ref.write_json(out/'source_read_receipt.json', dict(native_receipt,
            actual_model_fit_calls=0, new_labels=0, old_AI_books_replayed=0,
            selected_source_children=len(actions), source_B_selected_parents=selected_count))
        # Full mother reference schedule is identical for all controls; build once.
        empty = pd.DataFrame(columns=['u_index'])
        _, references = author.organize(empty, mothers, dates)
        for control in POLICIES:
            part = overrides.loc[overrides.control_id.eq(control)].copy()
            sig = make_control_signals(part, mothers.loc[mothers.event_id.isin(part.mother_event_id)],
                actions.loc[actions.action_id.isin(part.chosen_action_id)], market, dates, economics)
            path = out/f'signals_{control}.csv.gz'
            ref.write_table(path, sig, [])
            signal_bindings[control] = ref.file_binding(path)
            potential = {int(k): g.to_dict('records') for k, g in sig.groupby('u_index', sort=True)}
            prepared = (potential, references)
            for window in WINDOWS:
                bounds = protocol['cash']['windows'][window]
                start, end = (int(np.searchsorted(dates, value)) for value in bounds)
                if end >= len(dates) or dates[end] != bounds[1] or indices[window].shape != (2000, end-start+1):
                    raise ValueError('fixed source calendar/window/index width differs')
                for cost in COSTS:
                    name = f'NARROW_{control}_{window}_{cost}'
                    if started >= 84:
                        raise ValueError('new cash budget exhausted')
                    started += 1
                    book = kernel.run_cash_account(sig, market, dates, economics, cost, name, start, end, prepared=prepared)
                    completed += 1
                    folder = out/name
                    ledger_bindings = write_ledgers(folder, book)
                    summary, report, fy = helpers.cash_report(book, families, ref.INITIAL)
                    capacity = dict(account=name, control_id=control, arm=control, window=window, cost=cost,
                        execution_unknown=book['execution_unknown'],
                        unknown_capacity_fills=sum(r['capacity_state'] == 'execution_capacity_unknown' for r in book['capacity_audit']),
                        capacity_unknown_roots=len(book['capacity_unknown_roots']),
                        entry_execution_unknown=len(book['entry_execution_unknown']))
                    summary.update(capacity, any_historical_stale=report['stale_days'] > 0)
                    report.update(capacity)
                    summaries[(control, window, cost)] = summary
                    daily[(control, window, cost)] = pd.DataFrame(book['daily'])[['date', 'equity', 'ever_insolvent']]
                    reports[name] = report
                    capacities.append(capacity)
                    fy = report_helpers.add_family_costs(fy, book)
                    family_tables.append(fy.assign(control_id=control, arm=control, window=window, cost=cost))
                    ref.write_json(folder/'summary.json', kernel.original.safe(summary))
                    accounts.append(dict(control_id=control, window=window, cost=cost, account_id=name,
                        directory=str(folder), summary=ref.file_binding(folder/'summary.json'), ledgers=ledger_bindings))
                    print(json.dumps(dict(phase='account_complete', account=name, completed=completed,
                        elapsed_seconds=time.monotonic()-clock)), flush=True)
        if started != 84 or completed != 84 or ref.NATIVE_QUERIES != 0:
            raise ValueError('exact84 new accounts/zero SQL required')
        points, distributions, ranks = compare_accounts(summaries, daily, ai_summaries, ai_daily, indices)
        ref.write_table(out/'comparisons.csv.gz', points, [])
        ref.write_table(out/'bootstrap_distributions.csv.gz', pd.DataFrame(distributions), [])
        ref.write_json(out/'descriptive_seed_ranks.json', kernel.original.safe(ranks))
        fy = pd.concat(family_tables, ignore_index=True)
        ref.write_table(out/'family_year_including_zero.csv.gz', fy, [])
        ref.write_table(out/'family_total_including_zero.csv.gz', fy.groupby(['control_id', 'arm', 'window', 'cost', 'family_id'])[
            ['net_equity_contribution', 'fee', 'slippage', 'fill_count', 'filled_qty']].sum().reset_index(), [])
        ref.write_table(out/'annual_slices.csv.gz', [dict(account=name, **row) for name, report in reports.items() for row in report['annual_slices']], [])
        rows = [dict(value, control_id=key[0], arm=key[0], window=key[1], cost=key[2]) for key, value in summaries.items()]
        ref.write_table(out/'account_summaries.csv.gz', rows, [])
        ref.write_table(out/'seed_distribution.csv.gz', [r for r in rows if r['control_id'] in RANDOM_POLICIES], [])
        ref.write_table(out/'capacity_summary.csv.gz', capacities, [])
        ref.write_json(out/'diagnostics.json', kernel.original.safe(reports))
        ref.write_json(out/'baseline_references.json', kernel.original.safe(baseline_books))
        ref.write_json(out/'signal_identification.json', dict(source_selected_parent_set_unchanged=True,
            full_mother_rows=399252, main_parent_rows=161014, source_B_selected_parents=selected_count,
            full_parent_representation='exact135 delta plus source130 B full parent bindings',
            base_choices_main=inputs['choices_main'], base_choices_holdout=inputs['choices_holdout'],
            overrides=inputs['overrides'], attribution_manifest=inputs['attribution_manifest'],
            future_label_states_not_used_for_cash_eligibility=True, selected_actions={p: selected_count for p in POLICIES}))
        ref.write_json(out/'research_interpretation.json', dict(original133_verdict='unsupported',
            original133_verdict_unchanged=True, conditional_positive_pool_ranking_only=True,
            primary='primary_2020 stress AI dailylog minus fixed20 random dailylog arithmetic mean',
            all20_seeds_retained=True, seed_rank_descriptive_not_p_value=True, no_best_seed_promotion=True,
            no_true_unseen_OOS=True, strict_orderbook_execution_established=False,
            goal_complete=False, production_qualified=False, increased_betting_qualified=False))
        if source_bundle() != before:
            raise ValueError('authorized source changed during136 actual')
        if cache_source.database_state(read_json(inputs['native_cache_manifest'])['database']['path']) != native_receipt['database_after']:
            raise ValueError('cached native database stat changed during136 actual')
        status = 'completed'
    except BaseException as exc:
        error = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        ref.write_json(out/'actual_terminal.json', dict(status=status, stage='cash', started_at=started_at,
            finished_at=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic()-clock,
            exit_code=0 if status == 'completed' else 1, error=error, cash_accounts_started=started,
            new_cash_accounts=completed, native_source_queries=ref.NATIVE_QUERIES,
            actual_model_fit_calls=0, new_labels=0, downloads=0, whole_database_hashes=0,
            old_AI_books_replayed=0, old_baseline_replays=0, fixture=False, python=sys.executable))
    artifacts = [dict(ref.file_binding(p), logical_name=str(p.relative_to(out)), role='decision_asset',
        feature_schema='stage136_month_ranking_cash_v1', raw_ohlc=False, reproducibility_required=True)
        for p in sorted(out.rglob('*')) if p.is_file()]
    manifest = dict(schema='stage136_month_ranking_cash_v1', status=status, mode='actual',
        protocol=pb, authorization=ab, source_bundle=before, input_bindings=inputs,
        terminal=ref.file_binding(out/'actual_terminal.json'), artifacts=artifacts, accounts=accounts,
        signals=signal_bindings, baseline_books=baseline_books, bootstrap_indices=protocol['bootstrap_indices'],
        new_cash_accounts=completed, native_source_queries=ref.NATIVE_QUERIES, actual_model_fit_calls=0,
        new_labels=0, old_AI_books_replayed=0, old_baseline_replays=0,
        goal_complete=False, production_qualified=False, increased_betting_qualified=False)
    for name in ('comparisons', 'bootstrap_distributions', 'account_summaries', 'seed_distribution',
                 'family_year_including_zero', 'family_total_including_zero', 'annual_slices',
                 'capacity_summary', 'diagnostics', 'descriptive_seed_ranks', 'source_read_receipt',
                 'signal_identification', 'research_interpretation'):
        suffix = '.json' if name in ('diagnostics', 'descriptive_seed_ranks', 'source_read_receipt',
            'signal_identification', 'research_interpretation') else '.csv.gz'
        manifest[name] = ref.file_binding(out/(name+suffix))
    ref.write_json(out/'manifest.json', manifest)
    return dict(status=status, output=str(out), native_source_queries=ref.NATIVE_QUERIES, new_cash_accounts=completed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('protocol', 'protocol-sha256', 'authorization', 'authorization-sha256', 'output'):
        parser.add_argument('--'+name, required=True)
    print(json.dumps(execute(parser.parse_args()), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
