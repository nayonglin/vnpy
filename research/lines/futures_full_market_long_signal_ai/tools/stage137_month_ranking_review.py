"""Increment-only Stage134 month attribution audit; never SQL, fit or replay.

Accepted129 labels,130 models and131 B4 accounts are identity-bound references.
Only new135 choices/label contrasts and136 saved books are examined. Imports
and finite fixtures touch none of those data. Actual CLI requires exact hashes.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import time
import traceback

import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
PROTOCOL_SHA = '25ad088a36d4aa3a022e7da7e818902e62b1c7c922b85aae3c31ad960c780e62'
REVIEW132_SHA = '7d8b5fd1c1a2d80d2df32632c8b097e9ca15eced9e65de745af40f1e32a3a181'
CONTROLS = ('MAX_VOLUME_POS',) + tuple(f'RANDOM_POS_{i:02d}' for i in range(20))
SCOPES = ('main', 'holdout_0', 'holdout_1')
WINDOWS = ('primary_2020', 'cold_2023')
COSTS = ('base', 'stress')
KEY_VERSION = 'stage134_positive_month_rank_v1'
LEDGERS = ('daily', 'fills', 'positions', 'reservations', 'rejections', 'closed', 'open', 'capacity_audit', 'entry_execution_unknown')
HELPER_NAMES = ('stage132_contract_choice_review.py', 'stage102_cash_adapter.py', 'stage102_cash_core.py', 'stage102_cash_diagnostics.py')


def binding(path):
    p = Path(path).resolve()
    raw = p.read_bytes()
    return dict(path=str(p), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def bound(item):
    raw = Path(item['path']).read_bytes()
    assert len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256'], ('binding', item['path'])
    return raw


def table(item, usecols=None):
    return pd.read_csv(io.BytesIO(bound(item)), compression='gzip' if item['path'].endswith('.gz') else None,
                       dtype=str, keep_default_na=False, usecols=usecols)


def same_binding(a, b):
    assert all(a[k] == b[k] for k in ('path', 'bytes', 'sha256')), ('identity', a.get('path'), b.get('path'))


def bundle():
    return [binding(TOOLS / name) for name in ('stage137_month_ranking_review.py', 'test_stage137_month_ranking_review.py') + HELPER_NAMES]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def write(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        f.write('\n')


def finite(value):
    try:
        return not isinstance(value, (bool, np.bool_)) and np.isfinite(float(value))
    except (ValueError, TypeError):
        return False


def random_key(seed, row):
    return digest(dict(version=KEY_VERSION, seed=int(seed), product_id=str(row['product_id']),
                       u_date=str(row['u_date']), actual_epoch=str(row['actual_epoch'])))


def select_control(rows, control):
    """Independent135 selection from source E; never accepts an outcome filter."""
    assert control in CONTROLS
    legal = rows.loc[pd.to_numeric(rows.u_action_eligible).eq(1) &
                     pd.to_numeric(rows.score).map(finite) & pd.to_numeric(rows.score).gt(0)].copy()
    assert len(legal) > 0
    if control == 'MAX_VOLUME_POS':
        legal['rule_key'] = pd.to_numeric(legal.u_volume)
        assert np.isfinite(legal.rule_key).all()
        chosen = legal.sort_values(['rule_key', 'actual_epoch', 'action_id'], ascending=[False, True, True], kind='mergesort').iloc[0]
        return str(chosen.action_id), float(chosen.rule_key)
    seed = int(control[-2:])
    legal['rule_key'] = [random_key(seed, row) for row in legal.to_dict('records')]
    chosen = legal.sort_values(['rule_key', 'actual_epoch', 'action_id'], kind='mergesort').iloc[0]
    return str(chosen.action_id), str(chosen.rule_key)


def own_outcome(row, end):
    if row.get('participation_state') == 'known_nonparticipation':
        return 0., False
    known_date = row.get('label_known_date', '')
    if row.get('label_state') == 'closed_complete_bar_model' and known_date and known_date <= end and finite(row.get('net_R_stress')):
        return float(row['net_R_stress']), False
    return None, True


def linear_contrast(left, right, labels, end):
    """Exact rational coefficients cancel shared unknown before identification."""
    known = 0.
    positive = negative = Fraction(0)
    common = 0
    for action in set(left) | set(right):
        a, b = Fraction(left.get(action, 0)), Fraction(right.get(action, 0))
        coefficient = a - b
        value, unknown = own_outcome(labels[action], end)
        common += int(unknown and min(a, b) > 0)
        if unknown:
            if coefficient > 0:
                positive += coefficient
            else:
                negative -= coefficient
        else:
            known += float(coefficient) * value
    unidentified = bool(positive or negative)
    return dict(value=None if unidentified else known, unknown=unidentified,
                known_contribution=known, positive_unknown_mass=float(positive),
                negative_unknown_mass=float(negative), common_unknown_actions=common)


def equal_u_summary(rows):
    assert not rows.empty
    unknown = rows.unknown.astype(bool)
    means = pd.to_numeric(rows.value).groupby(rows.u_date).mean()
    return dict(family_u_rows=len(rows), source_u_count=len(means), unknown_family_u=int(unknown.sum()),
                mean=None if unknown.any() else float(means.mean()))


def materialize_parents(parents, overrides):
    """Delta affects selected action proposals, retaining all full-base rows."""
    assert parents.event_id.is_unique and overrides.event_id.is_unique
    chosen = parents.loc[pd.to_numeric(parents.selected).eq(1), 'event_id']
    assert set(chosen) == set(overrides.event_id), 'delta must cover every selected parent exactly'
    result = parents.copy()
    overrides = overrides.copy()
    for target, source in [('proposed_action_id','chosen_action_id'), ('proposed_epoch','chosen_epoch'), ('proposed_score','score')]:
        if source in overrides:
            overrides[target] = overrides[source]
    allowed = ['chosen_action_id', 'chosen_action_sequence_index', 'chosen_epoch', 'score',
               'proposed_action_id', 'proposed_epoch', 'proposed_score']
    for name in allowed:
        if name not in overrides:
            continue
        if name not in result:
            result[name] = pd.Series(np.nan, index=result.index, dtype=object)
        mapping = overrides.set_index('event_id')[name]
        mask = pd.to_numeric(result.selected).eq(1)
        result.loc[mask, name] = result.loc[mask, 'event_id'].map(mapping)
    assert len(result) == len(parents) and result.event_id.tolist() == parents.event_id.tolist()
    return result


def paired_comparison(ai, references, indices, financial_unknown):
    assert len(references) in (1, 20)
    point = dict(financial_unknown=bool(financial_unknown))
    if ai is None or any(x is None for x in references):
        point.update(status='survival_failure_no_log_repair', mean_daily_log_difference=None,
                     cumulative_log_difference=None, ci95_low=None, ci95_high=None)
        return point, np.full(len(indices), np.nan)
    assert all(np.asarray(x).shape == np.asarray(ai).shape for x in references)
    delta = np.asarray(ai) - np.mean(references, axis=0)
    values = delta[indices].mean(axis=1)
    low, high = np.quantile(values, [.025, .975])
    point.update(status='valid', mean_daily_log_difference=float(delta.mean()), cumulative_log_difference=float(delta.sum()),
                 ci95_low=float(low), ci95_high=float(high))
    return point, values


@contextmanager
def cash_context(review, cash, positions):
    previous = (review.CASH_HELPER, review.ACTIVE_POSITIONS, cash.review_budgets)
    review.CASH_HELPER, review.ACTIVE_POSITIONS = cash, positions
    cash.review_budgets = review.review_capped_budgets
    try:
        yield
    finally:
        review.CASH_HELPER, review.ACTIVE_POSITIONS, cash.review_budgets = previous


def accepted_helpers():
    assert binding(TOOLS / 'stage132_contract_choice_review.py')['sha256'] == REVIEW132_SHA
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    import stage132_contract_choice_review as r
    cash, diag = r.independent_helpers()
    return r, cash, diag


def assert_fields(actual, expected, diag, label):
    """Numerics/null/booleans use meaning; only expected science fields matter."""
    for name, value in expected.items():
        assert name in actual, (label, 'missing', name)
        if isinstance(value, (bool, np.bool_)) and isinstance(actual[name], str):
            assert actual[name].lower() in ('true', 'false', '0', '1')
            got = actual[name].lower() in ('true', '1')
        elif value is None and actual[name] == '':
            got = None
        elif isinstance(value, (int, float, np.number)) and not isinstance(value, (bool, np.bool_)) and isinstance(actual[name], str):
            got = float(actual[name]) if actual[name] != '' else None
        else:
            got = actual[name]
        diag.compare(got, value, label + '.' + name)


def read_manifest(path, sha, schema):
    b = binding(path)
    assert b['sha256'] == sha, ('CLI exact manifest SHA', path)
    value = json.loads(bound(b))
    assert value['schema'] == schema
    return value, b


def artifact(manifest, role):
    if role in manifest and isinstance(manifest[role], dict) and 'path' in manifest[role]:
        return manifest[role]
    values = manifest.get('artifacts', {})
    if isinstance(values, dict):
        assert role in values, ('artifact absent', role)
        return values[role]
    found = [b for b in values if b.get('role') == role]
    assert len(found) == 1, ('artifact ambiguous', role)
    return found[0]


def checkpoint(out, name, identity, calculate):
    target = out / (name + '.json')
    if target.exists():
        saved = json.loads(target.read_text())
        assert saved['identity'] == identity, ('checkpoint identity changed', name)
        assert saved['completed'] is True
        return saved['result']
    result = calculate()
    write(target, dict(identity=identity, completed=True, result=result))
    print(json.dumps(dict(phase=name, completed=True)), flush=True)
    return result


def closure(args):
    protocol, pb = read_manifest(args.protocol, args.protocol_sha256, 'stage134_month_ranking_attribution_protocol_v1')
    assert pb['sha256'] == PROTOCOL_SHA and pb['bytes'] == 20790
    attribution, ab = read_manifest(args.attribution_manifest, args.attribution_manifest_sha256, 'stage135_month_ranking_attribution_v1')
    cash_manifest, cb = read_manifest(args.cash_manifest, args.cash_manifest_sha256, 'stage136_month_ranking_cash_v1')
    sources = bundle()
    assert digest(sources) == args.source_bundle_sha256, 'exact137 source bundle required'
    assert args.cache_manifest_sha256 == protocol['inputs']['native_cache_manifest']['sha256']
    same_binding(binding(args.cache_manifest), protocol['inputs']['native_cache_manifest'])
    for b in protocol['source_bindings']:
        bound(b)
    for manifest in (attribution, cash_manifest):
        same_binding(manifest['protocol'], pb)
        for role, expected in protocol['inputs'].items():
            same_binding(manifest['input_bindings'][role], expected)
        for b in manifest['source_bundle']:
            bound(b)
        terminal = json.loads(bound(manifest['terminal']))
        assert terminal['status'] == 'completed', ('new terminal not completed', manifest['schema'])
        if 'exit_code' in terminal:
            assert terminal['exit_code'] == 0
    same_binding(cash_manifest['input_bindings']['attribution_manifest'], ab)
    same_binding(cash_manifest['input_bindings']['overrides'], artifact(attribution, 'overrides'))
    accepted = json.loads(bound(protocol['inputs']['accepted_review']))
    terminal = json.loads(bound(protocol['inputs']['accepted_review_terminal']))
    assert terminal['status'] == 'completed'
    # The exact accepted review hash is the trust root; never call old entrypoints.
    identity = dict(protocol=pb, attribution=ab, cash=cb, sources=sources,
                    native_cache_manifest=protocol['inputs']['native_cache_manifest'], native_cache=protocol['inputs']['native_cache'])
    if args.root_authorization:
        auth = json.loads(Path(args.root_authorization).read_text())
        assert auth['schema'] == 'stage134_exact_root_authorization_v1'
        for name, actual in (('protocol', pb), ('attribution_manifest', ab), ('cash_manifest', cb)):
            if name in auth:
                same_binding(auth[name], actual)
    return protocol, attribution, cash_manifest, identity


def source_tables(protocol, r):
    """Read accepted source projections, without requalifying labels or models."""
    fields = ['action_id', 'actual_epoch', 'action_sequence_index', 'mother_sequence_index', 'mother_event_id',
              'product_id', 'family_id', 'u_date', 'u_index', 'reference_epoch', 'anchor_epoch', 'u_action_eligible',
              'u_volume', 'entry_capacity_qty', 'gross_capacity_qty', 'N_u', 'low20_u', 'u_close', 'history_run',
              'lifecycle_index', 'label_state', 'participation_state', 'net_R_stress', 'label_known_date']
    actions = table(protocol['inputs']['actions'], fields).set_index('action_id', drop=False)
    r.numeric(actions, ['action_sequence_index', 'mother_sequence_index', 'u_index', 'u_action_eligible', 'u_volume',
                        'entry_capacity_qty', 'gross_capacity_qty', 'N_u', 'low20_u', 'u_close', 'history_run',
                        'lifecycle_index', 'net_R_stress'])
    mothers = table(protocol['inputs']['mothers'])
    r.numeric(mothers, ['sequence_index', 'u_index'])
    parents = pd.concat([table(protocol['inputs'][role]) for role in ('choices_main', 'choices_holdout')], ignore_index=True)
    parents = parents.loc[parents.arm.eq('B')].copy()
    r.numeric(parents, ['sequence_index', 'u_index', 'selected', 'chosen_action_sequence_index', 'score', 'proposed_score'])
    scores = table(protocol['inputs']['child_scores'])
    r.numeric(scores, ['sequence_index', 'mother_sequence_index', 'u_index', 'u_action_eligible', 'score'])
    # All original forward states remain in the base. No source label predicate.
    assert len(mothers) == 399252 and mothers.event_id.is_unique
    assert len(parents.loc[parents.scope.eq('main')]) == 161014
    assert len(parents.loc[parents.scope.ne('main')]) == 161014
    assert not parents.duplicated(['scope', 'event_id']).any()
    return actions, mothers, parents, scores


def bridge_check(module, store, r):
    """Compare136's thin API to the accepted NativeBars for every cached row."""
    adapter = module.CachedMarket(store)
    checked = 0
    for epoch, series in store.series.items():
        bars = []
        indicators = []
        for k in series['days']:
            bars.append(adapter.bar(epoch, int(k)))
            indicators.append(adapter.indicator(epoch, int(k)))
        valid = series['valid']
        assert all((bar is not None) == bool(v) for bar, v in zip(bars, valid)), ('bridge valid', epoch)
        raw = np.asarray([[b[c] for c in ('open', 'high', 'low', 'close', 'volume')] for b in bars if b is not None], float)
        if valid.any():
            r.compare(raw, series['values'][valid], 'bridge_OHLCV', atol=0, rtol=0)
        for name, native in (('N', 'N'), ('low20', 'low20'), ('run_length', 'run')):
            expected = np.where(valid, series[native], 0 if name == 'run_length' else np.nan)
            r.compare([d[name] for d in indicators], expected, 'bridge_' + name, atol=0, rtol=0)
        checked += len(series['days'])
    assert adapter.bar('__missing__', 0) is None
    return dict(cached_native_rows_checked=checked, epochs_checked=len(store.series), SQL=0, indicators_recomputed=False)


def policy_weights(rows, ai, volume, canonical):
    E = rows.loc[pd.to_numeric(rows.u_action_eligible).eq(1)]
    S = E.loc[pd.to_numeric(E.score).map(finite) & pd.to_numeric(E.score).gt(0)]
    return dict(AI={ai:Fraction(1)} if ai else {},
                UNIFORM_S={a:Fraction(1, len(S)) for a in S.action_id} if len(S) else {},
                UNIFORM_E={a:Fraction(1, len(E)) for a in E.action_id} if len(E) else {},
                MAX_VOLUME_POS={volume:Fraction(1)} if volume else {},
                K={canonical:Fraction(1)} if canonical else {})


CONTRASTS = {'AI_minus_UNIFORM_S':('AI', 'UNIFORM_S'), 'UNIFORM_S_minus_UNIFORM_E':('UNIFORM_S', 'UNIFORM_E'),
             'AI_minus_MAX_VOLUME_POS':('AI', 'MAX_VOLUME_POS'), 'UNIFORM_E_minus_K':('UNIFORM_E', 'K'), 'AI_minus_K':('AI', 'K')}


def expected_diagnostic(base, pools, labels, end):
    """One original family-u, with no intent zero when source B did not admit."""
    selected = base.loc[pd.to_numeric(base.selected).eq(1)]
    assert len(selected) <= 1
    first = selected.iloc[0] if len(selected) else base.iloc[0]
    result = {name:first[name] for name in ('scope', 'cutoff', 'u_date', 'u_index', 'family_id')}
    result.update(admitted=bool(len(selected)), winning_product_id='', mother_event_id='', chosen_ai_action_id='',
                  chosen_volume_action_id='', canonical_action_id='', positive_month_count=0, eligible_month_count=0)
    if len(selected):
        p = selected.iloc[0]
        rows = pools[p.event_id]
        E = rows.loc[rows.u_action_eligible.eq(1)]
        S = E.loc[E.score.map(finite) & E.score.gt(0)]
        ai, volume = str(p.chosen_action_id), select_control(rows, 'MAX_VOLUME_POS')[0]
        canonical_rows = S.loc[S.actual_epoch.eq(p.anchor_epoch)]
        assert len(canonical_rows) <= 1
        canonical = '' if canonical_rows.empty else str(canonical_rows.iloc[0].action_id)
        result.update(winning_product_id=p.product_id, mother_event_id=p.event_id, chosen_ai_action_id=ai,
                      chosen_volume_action_id=volume, canonical_action_id=canonical,
                      positive_month_count=len(S), eligible_month_count=len(E))
        weights = policy_weights(rows, ai, volume, canonical)
    else:
        weights = {key:{} for key in ('AI', 'UNIFORM_S', 'UNIFORM_E', 'MAX_VOLUME_POS', 'K')}
    support = weights['UNIFORM_S']
    result['common_unresolved_count'] = sum(own_outcome(labels[a], end)[1] for a in support)
    for prefix, left, right in [(k,v,{}) for k,v in weights.items()] + [(k,weights[a],weights[b]) for k,(a,b) in CONTRASTS.items()]:
        contrast = linear_contrast(left, right, labels, end)
        result.update({prefix+'_value':contrast['value'], prefix+'_known':not contrast['unknown'],
                       prefix+'_unknown_positive_mass':contrast['positive_unknown_mass'],
                       prefix+'_unknown_negative_mass':contrast['negative_unknown_mass']})
    return result


def diagnostic_aggregates(frame):
    records = []
    for scope, source in frame.groupby('scope', sort=True):
        for population, mask in [('full', np.ones(len(source), bool)), ('admitted', source.admitted), ('multiple', source.positive_month_count.gt(1))]:
            part = source.loc[mask]
            for period, part0 in [('all', part)] + [(y, g) for y,g in part.groupby(part.u_date.str[:4], sort=True)]:
                for contrast in ('AI', 'UNIFORM_S', 'UNIFORM_E', 'MAX_VOLUME_POS', 'K') + tuple(CONTRASTS):
                    known = part0[contrast+'_known'].astype(bool)
                    day_means = pd.to_numeric(part0[contrast+'_value']).groupby(part0.u_date).mean()
                    mean = float(day_means.mean()) if day_means.notna().any() else None
                    records.append(dict(scope=scope, population=population, period=period, contrast=contrast,
                                        family_u_rows=len(part0), u_days=part0.u_date.nunique(), known_increment_rows=int(known.sum()),
                                        unknown_increment_rows=int((~known).sum()), mean_equal_u_known_only=mean,
                                        all_identified_mean_equal_u=mean if len(part0) and known.all() else None,
                                        unknown_positive_mass=float(part0[contrast+'_unknown_positive_mass'].sum()),
                                        unknown_negative_mass=float(part0[contrast+'_unknown_negative_mass'].sum())))
    return records


def review_attribution(protocol, manifest, actions, parents, scores, r, diag):
    for role in ('choices_main', 'choices_holdout'):
        same_binding(manifest['full_base_references'][role], protocol['inputs'][role])
    overrides = table(artifact(manifest, 'overrides'))
    assert set(overrides.control_id) == set(CONTROLS)
    assert not overrides.duplicated(['control_id', 'scope', 'mother_event_id']).any()
    assert not set(overrides) & {'label_state', 'net_R_stress', 'entry_index', 'exit_index', 'label_known_date'}
    selected = parents.loc[parents.selected.eq(1)]
    assert len(overrides) == len(selected) * 21
    got = overrides.set_index(['control_id', 'scope', 'mother_event_id'])
    r.numeric(overrides, ['mother_sequence_index', 'u_index', 'chosen_action_sequence_index', 'score', 'u_volume'])
    got = overrides.set_index(['control_id', 'scope', 'mother_event_id'])
    labels = actions[['label_state', 'participation_state', 'net_R_stress', 'label_known_date']].to_dict('index')
    # Source projection only; no model loading, prediction or label rebuilding.
    extras = actions.reindex(scores.action_id)
    source = scores.reset_index(drop=True).copy()
    for name in ('actual_epoch', 'u_volume'):
        source[name] = extras[name].to_numpy()
    assert source.actual_epoch.notna().all()
    all_expected = []
    pre_family = []
    for scope in SCOPES:
        scope_base = parents.loc[parents.scope.eq(scope)]
        scope_scores = source.loc[source.scope.eq(scope)]
        elig = scope_scores.u_action_eligible.eq(1) & scope_scores.score.map(finite)
        pre = scope_scores.assign(E=elig.astype(int), S=(elig & scope_scores.score.gt(0)).astype(int)).groupby('mother_event_id')[['E','S']].sum()
        pre_family.append(dict(scope=scope, parent_rows=len(pre), E_nonempty_S_empty=int((pre.E.gt(0)&pre.S.eq(0)).sum()), E_nonempty=int(pre.E.gt(0).sum())))
        own_selected = scope_base.loc[scope_base.selected.eq(1)]
        wanted = set(own_selected.event_id)
        pools = {key:g for key,g in scope_scores.loc[scope_scores.mother_event_id.isin(wanted)].groupby('mother_event_id', sort=False)}
        for p in own_selected.itertuples(index=False):
            pool = pools[p.event_id]
            assert pool.product_id.eq(p.product_id).all() and pool.u_date.eq(p.u_date).all()
            assert pool.family_id.eq(p.family_id).all() and pool.anchor_epoch.eq(p.anchor_epoch).all()
            assert pool.cutoff.eq(p.cutoff).all()
            for control in CONTROLS:
                action_id, key = select_control(pool, control)
                saved = got.loc[(control, scope, p.event_id)].to_dict()
                action = actions.loc[action_id]
                expected = dict(cutoff=p.cutoff, mother_sequence_index=p.sequence_index, product_id=p.product_id,
                                family_id=p.family_id, u_date=p.u_date, u_index=p.u_index, chosen_action_id=action_id,
                                chosen_action_sequence_index=action.action_sequence_index, chosen_epoch=action.actual_epoch,
                                anchor_epoch=p.anchor_epoch, score=float(pool.loc[pool.action_id.eq(action_id), 'score'].iloc[0]),
                                u_volume=float(action.u_volume), rule_key='max_original_u_volume' if control == 'MAX_VOLUME_POS' else key)
                assert_fields(saved, expected, diag, 'override')
        # Compact full-base reconstruction: no original state/identity can vanish.
        for control in CONTROLS:
            ov = overrides.loc[overrides.control_id.eq(control)&overrides.scope.eq(scope)].rename(columns={'mother_event_id':'event_id'})
            full = materialize_parents(scope_base, ov)
            assert full.loc[full.selected.eq(0), scope_base.columns].equals(scope_base.loc[scope_base.selected.eq(0)])
            for name in ('sequence_index', 'event_id', 'product_id', 'family_id', 'u_date', 'u_index', 'reference_epoch', 'anchor_epoch', 'selected', 'selection_state'):
                assert full[name].tolist() == scope_base[name].tolist()
        for _, base in scope_base.groupby(['family_id', 'u_date'], sort=True):
            all_expected.append(expected_diagnostic(base, pools, labels, protocol['scope']['end']))
    expected = pd.DataFrame(all_expected)
    saved = table(artifact(manifest, 'diagnostic_family_u'))
    keys = ['scope', 'family_id', 'u_date']
    assert not saved.duplicated(keys).any()
    saved = saved.set_index(keys).sort_index()
    expected = expected.set_index(keys).sort_index()
    assert saved.index.tolist() == expected.index.tolist(), 'complete family-u domain'
    bools = [c for c in expected if c.endswith('_known')] + ['admitted']
    numbers = [c for c in expected if c not in ('cutoff','winning_product_id','mother_event_id','chosen_ai_action_id','chosen_volume_action_id','canonical_action_id') + tuple(bools)]
    for name in bools:
        assert saved[name].astype(str).str.lower().isin(['true','false','0','1']).all()
        assert saved[name].astype(str).str.lower().isin(['true','1']).tolist() == expected[name].astype(bool).tolist(), ('diagnostic bool', name)
    for name in numbers:
        r.compare(pd.to_numeric(saved[name].replace('', np.nan)), pd.to_numeric(expected[name]), 'diagnostic_' + name, atol=1e-10)
    for name in set(expected)-set(bools)-set(numbers):
        assert saved[name].tolist() == expected[name].tolist(), ('diagnostic identity', name)
    summary = json.loads(bound(artifact(manifest, 'diagnostic_summary')))
    pre_actual = {v['scope']:v for v in summary['pre_family']}
    for row in pre_family:
        assert_fields(pre_actual[row['scope']], row, diag, 'pre_family')
    aggregates = diagnostic_aggregates(expected.reset_index())
    index = lambda row:tuple(row[n] for n in ('scope','population','period','contrast'))
    saved_aggregates = {index(row):row for row in summary['aggregates']}
    assert len(saved_aggregates) == len(summary['aggregates']) == len(aggregates)
    for row in aggregates:
        assert_fields(saved_aggregates[index(row)], row, diag, 'diagnostic aggregate')
    assert_fields(summary, dict(new_SQL=0, new_fits=0, new_cash=0, new_labels=0), diag, 'attribution no replay')
    return dict(overrides_checked=len(overrides), selected_parent_rows=len(selected), full_parent_rows=len(parents),
                family_u_diagnostics_checked=len(expected), aggregate_rows_checked=len(aggregates),
                exact_rational_unknown_cancellation=True, source_labels_or_models_reaudited=False)


def reviewed_signals(manifest, attribution, actions, parents, store, economics, r, diag):
    assert set(manifest['signals']) == set(CONTROLS)
    overrides = table(artifact(attribution, 'overrides'))
    overrides = overrides.loc[overrides.scope.eq('main')]
    result = {}
    expected_parent = set(parents.loc[parents.scope.eq('main')&parents.selected.eq(1), 'event_id'])
    for control in CONTROLS:
        selected = overrides.loc[overrides.control_id.eq(control)]
        assert set(selected.mother_event_id) == expected_parent
        saved = table(manifest['signals'][control])
        assert saved.event_id.tolist() == selected.chosen_action_id.tolist()
        assert saved.event_id.is_unique and not saved.duplicated(['family_id', 'u_date']).any()
        r.numeric(saved, ['action_sequence_index','u_index','D_index','label_history_ready20','N_u','low20_u','u_close',
                          'history_run','lifecycle_index','entry_capacity_qty','u_gross_capacity_qty','potential','score'])
        saved = saved.set_index('event_id', drop=False)
        for ov in selected.itertuples(index=False):
            action = actions.loc[ov.chosen_action_id]
            epoch, day = str(action.actual_epoch), str(action.u_date)
            k = store.index[day]
            j = store.locate(epoch, k)
            assert j is not None and store.series[epoch]['valid'][j]
            native = store.series[epoch]
            gross, entry = r.capacity(native['values'][j,4], economics[epoch]['round_lot'])
            assert native['run'][j] >= 20 and entry >= economics[epoch]['round_lot']
            expected = dict(mother_event_id=ov.mother_event_id, action_sequence_index=int(action.action_sequence_index),
                            product_id=action.product_id, family_id=action.family_id, u_date=day, u_index=k, D_index=k+1,
                            reference_epoch=epoch, anchor_epoch=action.anchor_epoch, label_history_ready20=1,
                            N_u=float(native['N'][j]), low20_u=float(native['low20'][j]), u_close=float(native['values'][j,3]),
                            history_run=int(native['run'][j]), lifecycle_index=int(action.lifecycle_index),
                            entry_capacity_qty=int(entry), u_gross_capacity_qty=int(gross), potential=1,
                            score=float(ov.score), arm=control, policy='NARROW', cutoff=ov.cutoff, control_id=control)
            assert_fields(saved.loc[ov.chosen_action_id].to_dict(), expected, diag, 'control signal')
        saved['planned_execution_date'] = [store.calendar[int(k)+1] if int(k)+1<len(store.calendar) else '' for k in saved.u_index]
        result[control] = saved
    return result


def review_books(protocol, manifest, signals, mothers, store, economics, out, identity, r, cash, diag):
    assert len(manifest['accounts']) == 84
    expected_keys = {(c,w,s) for c in CONTROLS for w in WINDOWS for s in COSTS}
    books = {(a['control_id'],a['window'],a['cost']):a for a in manifest['accounts']}
    assert set(books) == expected_keys and len(books) == len(manifest['accounts'])
    directory = Path(manifest['terminal']['path']).parent
    reports = json.loads(bound(artifact(manifest, 'diagnostics')))
    family_year = table(artifact(manifest, 'family_year_including_zero'))
    annual = table(artifact(manifest, 'annual_slices'))
    summary_table = table(artifact(manifest, 'account_summaries'))
    capacity = table(artifact(manifest, 'capacity_summary'))
    families = sorted(mothers.family_id.unique())
    summaries, daily, logs, accounts, warnings = {}, {}, {}, [], []
    family_totals = []
    for key in sorted(expected_keys):
        control, window, cost = key
        a = books[key]
        name = f'NARROW_{control}_{window}_{cost}'
        folder = Path(a['directory'])
        assert a['account_id'] == name and folder == directory/name
        assert set(a['ledgers']) == set(LEDGERS)
        for role, b in a['ledgers'].items():
            assert Path(b['path']) == folder/(role+'.csv.gz')
            bound(b)
        assert Path(a['summary']['path']) == folder/'summary.json'
        summary = json.loads(bound(a['summary']))
        sig = signals[control]
        low, high = protocol['cash']['windows'][window]
        schedule = dict(id=window, start=low, end=high)
        def calculate():
            positions = cash.csv(folder/'positions.csv.gz')
            with cash_context(r, cash, positions):
                checked = cash.review_account(folder, cost, schedule, protocol, sig, economics, store.calendar, .25)
                native = r.account_native_and_capacity(folder, sig, mothers, store, economics, summary, cost)
            saved_fy = family_year.loc[family_year.control_id.eq(control)&family_year.window.eq(window)&family_year.cost.eq(cost)]
            d, log, numbers, fy = diag._account(folder, summary, reports[name], saved_fy, families)
            diag._daily_summary(d, summary, 1000000.)
            expected_annual = reports[name]['annual_slices']
            saved_annual = annual.loc[annual.account.eq(name)].sort_values('year')
            assert len(saved_annual) == len(expected_annual)
            for actual, expected in zip(saved_annual.to_dict('records'), expected_annual):
                assert_fields(actual, expected, diag, 'annual')
            summary_row = summary_table.loc[summary_table.control_id.eq(control)&summary_table.window.eq(window)&summary_table.cost.eq(cost)]
            assert len(summary_row) == 1
            assert_fields(summary_row.iloc[0].to_dict(), {k:v for k,v in summary.items() if not isinstance(v,(dict,list))}, diag, 'summary table')
            caprow = capacity.loc[capacity.account.eq(name)]
            assert len(caprow) == 1
            assert_fields(caprow.iloc[0].to_dict(), {k:summary[k] for k in ('execution_unknown','unknown_capacity_fills','capacity_unknown_roots','entry_execution_unknown')}, diag, 'capacity summary')
            fills = cash.csv(folder/'fills.csv.gz')
            roots = pd.concat([cash.csv(folder/'closed.csv.gz'),cash.csv(folder/'open.csv.gz')],ignore_index=True).set_index('root_id')
            gaps = []
            for fill in fills.loc[fills.side.eq('SELL')&fills.reason.eq('gap_stop')].to_dict('records'):
                root = roots.loc[fill['root_id']]
                loss = (float(root.entry_reference)-float(fill['reference_price']))/(.25*sig.loc[fill['event_id'],'N_u'])
                gaps.append(dict(event_id=fill['event_id'], date=fill['date'], gross_loss_R=loss, qty=int(float(fill['qty'])),
                                 realized_gross=float(fill['realized_gross']), exit_fee=float(fill['fee'])))
            r.nested(reports[name]['gap_stop_fills'], gaps, 'gap_stop_fills')
            assert reports[name]['gap_stop_exceeds_1R'] == sum(g['gross_loss_R']>1 for g in gaps)
            assert summary['any_historical_stale'] == bool(numbers['stale_days']>0)
            return r.safe(dict(account_id=name, ledger=checked, native=native, diagnostics=numbers))
        account = checkpoint(out, 'book_'+name, dict(run=identity, book=a), calculate)
        accounts.append(account)
        warnings.extend(dict(account=name, **w) for w in account['native']['presentation_warnings'])
        summaries[key] = summary
        d = diag._read(folder, 'daily')
        daily[key], logs[key] = d, diag._log(d, 1000000.)
        sub = family_year.loc[family_year.control_id.eq(control)&family_year.window.eq(window)&family_year.cost.eq(cost)].copy()
        for measure in ('net_equity_contribution','fee','slippage','fill_count','filled_qty'):
            sub[measure] = pd.to_numeric(sub[measure])
        family_totals.append(sub)
    assert set(reports) == {a['account_id'] for a in accounts}
    assert len(summary_table) == len(capacity) == 84
    measures = ['net_equity_contribution','fee','slippage','fill_count','filled_qty']
    keys = ['control_id','arm','window','cost','family_id']
    expected = pd.concat(family_totals).groupby(keys)[measures].sum().sort_index()
    total = table(artifact(manifest, 'family_total_including_zero')).set_index(keys).sort_index()
    assert total.index.tolist() == expected.index.tolist()
    for name in measures:
        r.compare(pd.to_numeric(total[name]), expected[name], 'family total '+name)
    seeds = table(artifact(manifest, 'seed_distribution'))
    assert len(seeds) == 80 and set(seeds.control_id) == set(CONTROLS[1:])
    for row in seeds.to_dict('records'):
        summary = summaries[(row['control_id'],row['window'],row['cost'])]
        assert_fields(row, {k:v for k,v in summary.items() if not isinstance(v,(dict,list))}, diag, 'full seed distribution')
    return summaries, daily, logs, dict(accounts_checked=84, accounts=accounts, presentation_warnings=warnings,
        all_new_fills_budgets_anchor_gross_capacity_checked=True, old_AI_books_reaudited=False)


def review_comparisons(protocol, manifest, summaries, daily, logs, r, diag):
    baseline_manifest = json.loads(bound(protocol['inputs']['baseline_cash_manifest']))
    baseline_artifacts = {v['logical_name']:v for v in baseline_manifest['artifacts']}
    assert set(manifest['baseline_books']) == {w+'_'+c for w in WINDOWS for c in COSTS}
    comparisons = table(artifact(manifest, 'comparisons'))
    distributions = table(artifact(manifest, 'bootstrap_distributions'))
    assert len(comparisons) == 8 and not comparisons.duplicated(['window','cost','contrast']).any()
    assert len(distributions) == 2000
    ranks = json.loads(bound(artifact(manifest, 'descriptive_seed_ranks')))
    assert len(ranks) == 4
    points = []
    for window in WINDOWS:
        indices = np.load(io.BytesIO(bound(protocol['bootstrap_indices'][window])), allow_pickle=False)
        for cost in COSTS:
            baseline = manifest['baseline_books'][window+'_'+cost]
            name = f'NARROW_B_{window}_{cost}'
            assert baseline['account_id'] == name and baseline['source_only'] is True and baseline['replayed'] is False
            assert baseline['window'] == window and baseline['cost'] == cost
            for role, logical in [('summary',name+'/summary.json'), ('daily',name+'/daily.csv.gz'), ('diagnostics','diagnostics.json')]:
                same_binding(baseline[role], baseline_artifacts[logical])
            ai_summary = json.loads(bound(baseline['summary']))
            ai_daily = pd.read_csv(io.BytesIO(bound(baseline['daily'])), compression='gzip', dtype={'date':str})
            # Original B4 is reference-only; no old fill, budget or native review.
            ai = diag._log(ai_daily, 1000000.)
            assert indices.shape == (2000, len(ai_daily)) and indices.dtype.kind in 'iu'
            assert indices.min() >= 0 and indices.max() < len(ai_daily)
            for contrast, controls in [('AI_minus_MAX_VOLUME_POS',CONTROLS[:1]), ('AI_minus_RANDOM_POS_mean20',CONTROLS[1:])]:
                assert all(daily[(c,window,cost)].date.tolist() == ai_daily.date.tolist() for c in controls)
                unknown = bool(ai_summary['execution_unknown'] or ai_summary['stale_positions'] or ai_daily.stale_positions.gt(0).any()
                               or any(summaries[(c,window,cost)]['execution_unknown'] or summaries[(c,window,cost)]['any_historical_stale'] for c in controls))
                point, values = paired_comparison(ai, [logs[(c,window,cost)] for c in controls], indices, unknown)
                point.update(AI_total_return_pct=ai_summary['total_return_pct'], AI_max_drawdown_pct=ai_summary['max_drawdown_pct'],
                             AI_sharpe=ai_summary['sharpe'], conditional_positive_pool_only=True, no_promotion=True)
                if len(controls) == 1:
                    control = summaries[(controls[0],window,cost)]
                    point.update(reference_total_return_pct=control['total_return_pct'], reference_max_drawdown_pct=control['max_drawdown_pct'],
                                 return_percentage_point_difference=ai_summary['total_return_pct']-control['total_return_pct'],
                                 drawdown_percentage_point_difference=ai_summary['max_drawdown_pct']-control['max_drawdown_pct'])
                row = comparisons.loc[comparisons.window.eq(window)&comparisons.cost.eq(cost)&comparisons.contrast.eq(contrast)]
                assert len(row) == 1
                assert_fields(row.iloc[0].to_dict(), point, diag, 'comparison')
                assert_fields(row.iloc[0].to_dict(), dict(control_count=len(controls), no_seed_dropped=True, epsilon_log_repair=False,
                    bootstrap_repetitions=2000, block_length=252, indices_regenerated=False), diag, 'comparison assumptions')
                r.compare(pd.to_numeric(distributions[window+'_'+cost+'_'+contrast].replace('',np.nan)), values, 'paired distributions', atol=1e-12)
                points.append(dict(window=window, cost=cost, contrast=contrast, **point))
            seed_returns = [summaries[(c,window,cost)]['total_return_pct'] for c in CONTROLS[1:]]
            ai_return = ai_summary['total_return_pct']
            identified = all(finite(v) for v in seed_returns+[ai_return])
            rank = [v for v in ranks if v['window']==window and v['cost']==cost]
            assert len(rank) == 1 and rank[0]['controls'] == list(CONTROLS[1:])
            assert_fields(rank[0], dict(seed_count=20, status='descriptive_only' if identified else 'unknown_return_rank',
                random_returns_below_AI=sum(v<ai_return for v in seed_returns) if identified else None,
                random_returns_equal_AI=sum(v==ai_return for v in seed_returns) if identified else None,
                AI_percentile_fraction=sum(v<ai_return for v in seed_returns)/20. if identified else None,
                not_p_value=True, no_best_seed_selection=True, unseen_OOS=False), diag, 'descriptive rank')
    assert set(distributions) == {p['window']+'_'+p['cost']+'_'+p['contrast'] for p in points}
    interpretation = json.loads(bound(artifact(manifest, 'research_interpretation')))
    assert_fields(interpretation, dict(original133_verdict='unsupported', original133_verdict_unchanged=True,
        conditional_positive_pool_ranking_only=True, all20_seeds_retained=True, seed_rank_descriptive_not_p_value=True,
        no_best_seed_promotion=True, no_true_unseen_OOS=True, strict_orderbook_execution_established=False,
        goal_complete=False, production_qualified=False, increased_betting_qualified=False), diag, 'research interpretation')
    return dict(comparisons_checked=8, bootstrap_repetitions=2000, block_length=252, points=points,
        fixed20_conditional_path_CI_only=True, rank_is_pvalue=False, old_AI_replays=0, no_strategy_or_leverage_qualification=True)


def review(args):
    out = Path(args.output).resolve()
    allowed = LINE/'outputs/stage137_month_ranking_review'
    assert allowed in out.parents, '137 output directory required'
    out.mkdir(parents=True, exist_ok=args.resume)
    assert args.resume or not list(out.iterdir()), 'fresh output or explicit checkpoint resume required'
    started = time.monotonic()
    terminal = out/('actual_terminal_resume_'+str(time.time_ns())+'.json' if args.resume else 'actual_terminal.json')
    status, error = 'failed', None
    try:
        protocol, attribution, cash_manifest, identity = closure(args)
        run_identity = digest(identity)
        if not (out/'exact_inputs.json').exists():
            write(out/'exact_inputs.json', identity)
        else:
            assert json.loads((out/'exact_inputs.json').read_text()) == identity
        r, cash, diag = accepted_helpers()
        sources_before = bundle()
        actions, mothers, parents, scores = source_tables(protocol, r)
        source_result = checkpoint(out, 'attribution', run_identity,
            lambda:review_attribution(protocol, attribution, actions, parents, scores, r, diag))
        del scores
        store, native, cache = r.restore_native_cache(protocol['inputs']['native_cache_manifest'])
        same_binding(cache['file'], protocol['inputs']['native_cache'])
        assert native['native_source_queries'] == 0
        market = json.loads(bound(protocol['inputs']['market_protocol']))
        economics = json.loads(bound(market['economic_projection']))['instruments']
        # Author module is imported only for the new bridge API, never its cash run.
        spec = importlib.util.spec_from_file_location('review137_bridge136', TOOLS/'stage136_month_ranking_cash.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        bridge = checkpoint(out, 'cached_bridge', run_identity, lambda:bridge_check(module, store, r))
        signals = reviewed_signals(cash_manifest, attribution, actions, parents, store, economics, r, diag)
        summaries, daily, logs, books = review_books(protocol, cash_manifest, signals, mothers, store, economics, out, run_identity, r, cash, diag)
        comparisons = checkpoint(out, 'comparisons', run_identity,
            lambda:review_comparisons(protocol, cash_manifest, summaries, daily, logs, r, diag))
        assert_fields(cash_manifest, dict(new_cash_accounts=84, native_source_queries=0, actual_model_fit_calls=0,
            new_labels=0, old_AI_books_replayed=0, old_baseline_replays=0, goal_complete=False,
            production_qualified=False, increased_betting_qualified=False), diag, 'cash execution budget')
        assert r.database_state(cache['database']['path']) == native['database_after']
        assert bundle() == sources_before
        receipt = dict(schema='stage137_incremental_month_ranking_review_v1', status='completed', exact_inputs=identity,
            scope='new choices/diagnostics/84 cash books/comparisons only; accepted old source qualification retained',
            attribution=source_result, cached_bridge=bridge, books=books, comparisons=comparisons,
            counts=dict(Critical=0, Important=0, Minor=0), presentation_warnings=books['presentation_warnings'],
            native_source_queries=0, actual_fit_calls=0, new_cash_replays=0, old_AI_reaudits=0,
            elapsed_seconds=time.monotonic()-started, scientific_acceptance_is_strategy_qualification=False,
            production_qualified=False, increased_betting_qualified=False, original133_verdict='unsupported')
        target = out/('review_receipt_resume_'+str(time.time_ns())+'.json' if args.resume else 'review_receipt.json')
        write(target, r.safe(receipt))
        status = 'completed'
        print(json.dumps(dict(status=status, receipt=binding(target))), flush=True)
        return receipt
    except BaseException:
        error = traceback.format_exc()
        raise
    finally:
        write(terminal, dict(status=status, exit_code=0 if status=='completed' else 1, error=error,
            elapsed_seconds=time.monotonic()-started, native_source_queries=0, actual_fit_calls=0,
            new_cash_replays=0, downloads=0, whole_database_hashes=0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','protocol-sha256','attribution-manifest','attribution-manifest-sha256',
                 'cash-manifest','cash-manifest-sha256','cache-manifest','cache-manifest-sha256','source-bundle-sha256','output'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--root-authorization')
    parser.add_argument('--resume', action='store_true', help='exact137 checkpoints only; preserve all previous failure terminals')
    review(parser.parse_args())


if __name__ == '__main__':
    main()
