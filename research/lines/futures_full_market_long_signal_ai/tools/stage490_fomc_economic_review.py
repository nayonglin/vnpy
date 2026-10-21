"""Bounded independent audit of the completed 488/489/491 experiment.

No estimator fit or strategy/cash kernel is called. One source-key SQL, one
original COMMON member read, one original score stream and one native cache.
Original129 Y, original mother streams and original CSV/H5 are never opened.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sqlite3
import sys
import time
import traceback

import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
PROTO_SHA = 'cf55afebcbf3a51139fc18a2b86522cb8c96f477c56f1798b505801375998aac'
ARMS = ('B_PRE_LIQUIDITY', 'C_PRE_LIQUIDITY_FOMC')
SCOPES = ('main', 'holdout_0', 'holdout_1')
CUTOFFS = ('2020-01-01', '2023-01-01')
END = '2026-10-16'
ERRORS = {}
READS = Counter()


def module(name):
    spec = importlib.util.spec_from_file_location('review490_' + name[:-3], TOOLS / name)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def safe(v):
    if isinstance(v, dict):
        return {str(k): safe(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [safe(x) for x in v]
    if isinstance(v, np.ndarray):
        return safe(v.tolist())
    if isinstance(v, (np.integer, np.bool_)):
        return v.item()
    if isinstance(v, (float, np.floating)):
        return float(v) if math.isfinite(v) else None
    return v


def write(path, value):
    Path(path).write_text(json.dumps(safe(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def bind(path):
    p = Path(path).resolve()
    raw = p.read_bytes()
    return dict(path=str(p), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def eq(a, b, label, atol=2e-7, rtol=2e-10):
    a, b = np.asarray(a, float), np.asarray(b, float)
    assert a.shape == b.shape, (label, 'shape', a.shape, b.shape)
    assert np.array_equal(np.isnan(a), np.isnan(b)), (label, 'NaN')
    assert np.array_equal(np.isfinite(a), np.isfinite(b)), (label, 'finite')
    valid = np.isfinite(a)
    err = np.abs(a[valid] - b[valid])
    ERRORS[label] = max(ERRORS.get(label, 0.), float(err.max()) if err.size else 0.)
    assert np.all(err <= atol + rtol * np.abs(b[valid])), (label, ERRORS[label])


def nums(frame, columns):
    for c in columns:
        if c in frame:
            frame[c] = pd.to_numeric(frame[c].replace('', np.nan), errors='raise')
    return frame


def truth(values):
    s = pd.Series(values).astype(str).str.lower()
    assert s.isin(['true', 'false', '1', '0']).all()
    return s.isin(['true', '1']).to_numpy()


def family_hash(v):
    return int(hashlib.sha256(str(v).encode()).hexdigest(), 16) % 2


class Reader:
    def __init__(self):
        self.raw, self.checked, self.bindings = {}, set(), {}

    def register(self, v):
        if isinstance(v, dict):
            if {'path', 'bytes', 'sha256'} <= set(v):
                path = str(Path(v['path']).resolve())
                if path in self.bindings:
                    assert all(self.bindings[path][k] == v[k] for k in ('bytes', 'sha256'))
                self.bindings[path] = v
            else:
                for x in v.values():
                    self.register(x)
        elif isinstance(v, list):
            for x in v:
                self.register(x)

    def read(self, b, retain=True):
        path = str(Path(b['path']).resolve())
        if path not in self.raw:
            raw = Path(path).read_bytes()
            assert len(raw) == b['bytes'] and hashlib.sha256(raw).hexdigest() == b['sha256'], path
            self.checked.add(path)
            if retain:
                self.raw[path] = raw
            return raw
        return self.raw[path]

    def doc(self, b):
        return json.loads(self.read(b))

    def table(self, b, usecols=None):
        return pd.read_csv(io.BytesIO(self.read(b)), compression='gzip' if b['path'].endswith('.gz') else None,
                           usecols=usecols, dtype=str, keep_default_na=False, float_precision='round_trip')

    def path_table(self, p):
        path = str(Path(p).resolve())
        return self.table(self.bindings[path])

    def finish(self):
        for path, b in self.bindings.items():
            if path not in self.checked:
                # Only new artifacts and small bound code/metadata get registered.
                self.read(b, retain=False)


def identities(a, b, columns, label):
    assert len(a) == len(b), label
    for c in columns:
        assert a[c].astype(str).tolist() == b[c].astype(str).tolist(), (label, c)


def stat(path):
    p = Path(path)
    s = p.stat()
    return (s.st_size, s.st_ino, s.st_mtime_ns)


def positive(x):
    try:
        return math.isfinite(float(x)) and float(x) > 0
    except (ValueError, TypeError):
        return False


def float_tokens(values):
    """Round-trip stored binary64 decimal text, without pandas' decimal parser."""
    return pd.Series(values, index=values.index).map(lambda x: float(x) if str(x) != '' else np.nan)


def boundary(epoch, calendar):
    y, m = int(epoch[-6:-2]), int(epoch[-2:])
    y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    target = f'{y:04d}-{m:02d}-01'
    if target < calendar[0]:
        return None, target, 'before_calendar_blocked'
    k = int(np.searchsorted(calendar, target))
    return (k, target, 'in_calendar') if k < len(calendar) else (None, target, 'after_calendar_pending')


def domain(epoch, u, calendar, boundaries):
    if epoch not in boundaries:
        boundaries[epoch] = boundary(epoch, calendar)
    k, target, state = boundaries[epoch]
    return False if state == 'before_calendar_blocked' or u + 1 >= len(calendar) else (
        u + 1 < k if k is not None else calendar[u + 1] < target)


def review_source(r, p, source, out):
    f = r.table(source['artifacts']['exact_pre_fields'])
    req = r.table(p['source_fields']['inputs']['requests'])
    assert len(f) == len(req) == 54089 and not f.raw_request_id.duplicated().any()
    identities(f, req, req.columns, 'all raw request identities')
    ncols = ['pre_volume', 'native_volume', 'volume_factor', 'pre_open_native', 'pre_high_native',
             'pre_low_native', 'pre_close_native', 'pre_settlement_candidate', 'pre_settlement_source_verified',
             'pre_open_candidate', 'pre_high_candidate', 'pre_low_candidate', 'pre_close_candidate',
             'candidate_source_volume', 'cash_multiplier', 'numeric_notional', 'log_turnover_source_verified',
             'raw_candidate_notional', 'original_volume']
    nums(f, ncols)
    cfg = p['source_fields']['inputs']
    economics = r.doc(cfg['economics'])['instruments']
    dbp = Path(cfg['database']['path']).resolve()
    before = stat(dbp)
    assert not Path(str(dbp) + '-wal').exists() and not Path(str(dbp) + '-shm').exists()
    payload = json.dumps([[i, x.reference_epoch, x.pre_date] for i, x in enumerate(req.itertuples())])
    sql = """WITH q AS (
      SELECT json_extract(value,'$[0]') i,json_extract(value,'$[1]') e,json_extract(value,'$[2]') t
      FROM json_each(?))
      SELECT q.i,d.contract_epoch_id,d.trade_date,d.open,d.high,d.low,d.close,
      d.volume,d.native_volume,d.volume_factor,d.quality_status,d.source_id,d.source_locator,
      s.family,s.path,s.sha256,s.bytes FROM q
      LEFT JOIN daily_bars d ON d.contract_epoch_id=q.e AND d.trade_date=q.t
      LEFT JOIN sources s ON s.source_id=d.source_id ORDER BY q.i"""
    READS['pre_exact_SQL'] += 1
    with sqlite3.connect(dbp.as_uri() + '?mode=ro&immutable=1', uri=True) as db:
        native = list(db.execute(sql, (payload,)))
    assert stat(dbp) == before and len(native) == 54089
    found = 0
    assert [x[0] for x in native] == list(range(len(req)))
    for (i, epoch, day, O, H, L, C, V, rawV, factor, quality, sid, locator, family, path, sha, size), row in zip(native, f.to_dict('records')):
        if epoch is None:
            assert str(row['native_found']) == '0' and not truth([row['source_numerically_verified']])[0]
            assert not np.isfinite(row['log_turnover_source_verified'])
            continue
        found += 1
        assert epoch == row['reference_epoch'] and day == row['pre_date'] and str(row['native_found']) == '1'
        eq([row['pre_volume'], row['native_volume'], row['volume_factor']], [V, rawV, factor], 'pre native quantity', 0., 0.)
        eq([row['pre_open_native'], row['pre_high_native'], row['pre_low_native'], row['pre_close_native']], [O, H, L, C], 'pre native OHLC', 0., 0.)
        for k, v in [('accepted_source_id', sid), ('accepted_source_locator', locator), ('accepted_source_family', family),
                     ('accepted_source_path', path), ('accepted_source_sha256', sha)]:
            assert str(row[k]) == str(v), ('source provenance', k)
        e = economics.get(epoch, {})
        em = e.get('contract_multiplier')
        if em is None:
            assert not np.isfinite(row['cash_multiplier'])
        else:
            eq(row['cash_multiplier'], em, 'all exact epoch multipliers', 0., 0.)
        if row['source_route'] == 'rq_fallback_after_absent_original_column':
            assert str(row['original_field_present']).lower() == 'false'
            assert row['original_observation_state'] == 'row_found'
            assert row['original_source_epoch'] == epoch and row['original_source_date'] == day
            assert row['original_ohlc_relation'] != 'conflict' and positive(row['original_volume'])
        source_ok = (row['candidate_source_epoch'] == epoch and row['candidate_source_date'] == day and
                     row['ohlc_relation'] != 'conflict' and positive(row['pre_settlement_candidate']) and
                     L - 1e-8 <= row['pre_settlement_candidate'] <= H + 1e-8)
        quantity_ok = (V is not None and rawV is not None and factor in (.5, 1.) and V >= 0 and rawV >= 0
                       and abs(rawV * factor - V) <= 1e-6)
        native_ok = quality == 'accepted' and all(positive(x) for x in [O, H, L, C]) and L <= min(O, C) <= max(O, C) <= H
        candidate_ohlc = np.asarray([row['pre_open_candidate'], row['pre_high_candidate'],
                                     row['pre_low_candidate'], row['pre_close_candidate']], float)
        candidate_ok = np.isfinite(candidate_ohlc).all() and np.all(np.abs(candidate_ohlc - [O, H, L, C]) <= 1e-8)
        original_present = str(row['original_field_present']).lower() == 'true'
        row_ok = (row['original_observation_state'] == 'row_found' and
                  (original_present or row['source_route'] == 'rq_fallback_after_absent_original_column'))
        source_volume_ok = np.isfinite(row['candidate_source_volume']) and row['candidate_source_volume'] >= 0
        em_ok = (e.get('economics_status') == 'exact_epoch_metadata_snapshot' and positive(em) and
                 e.get('exchange') == epoch.split('.')[0] and e.get('underlying_symbol') == epoch.split('.')[1])
        expected_verified = bool(native_ok and source_ok and candidate_ok and quantity_ok and em_ok and row_ok and source_volume_ok)
        assert truth([row['source_numerically_verified']])[0] == expected_verified, ('numeric verification mask', i)
        if expected_verified:
            assert quality == 'accepted' and all(positive(x) for x in [O, H, L, C])
            assert L <= min(O, C) <= max(O, C) <= H and source_ok and quantity_ok
            assert e.get('economics_status') == 'exact_epoch_metadata_snapshot' and positive(em)
            assert e.get('exchange') == epoch.split('.')[0] and e.get('underlying_symbol') == epoch.split('.')[1]
            eq([row['pre_open_candidate'], row['pre_high_candidate'], row['pre_low_candidate'], row['pre_close_candidate']],
               [O, H, L, C], 'all verified candidate OHLC', 1e-8, 0.)
            eq(row['pre_settlement_source_verified'], row['pre_settlement_candidate'], 'source settlement retained', 0., 0.)
            n = V * em * row['pre_settlement_source_verified']
            eq(row['numeric_notional'], n, 'all verified notionals', 1e-6, 1e-12)
            eq(row['log_turnover_source_verified'], math.log(n) if n > 0 else np.nan, 'all verified log notionals', 1e-12, 1e-12)
        else:
            assert not np.isfinite(row['log_turnover_source_verified'])
    assert all(f[c].eq('0').all() for c in ['strict_pit_accepted', 'training_accepted', 'alpha_supported'])
    receipt = r.doc(source['artifacts']['source_read_receipt'])
    assert receipt['completed'] is True and receipt['request_rows'] == 54089 and receipt['native_found'] == found
    assert receipt['native_missing'] == 54089 - found and receipt['native_source_queries'] == 1
    observed = int(truth(f.source_numerically_verified).sum())
    assert receipt['source_numerically_verified'] == observed
    report = dict(request_rows=54089, native_found=found, native_missing=54089 - found,
                  numerically_verified=observed, source_state_counts=dict(Counter(f.source_numeric_state)),
                  source_parser_qualification_inherited=True, original_CSV_H5_revalidation=False,
                  historical_first_seen_PIT=False, source_SQL=1)
    write(out / 'source_phase.json', report)
    return f, economics, report


def review_models(r, p, fit, fields, calendar, out):
    art = fit['artifacts']
    f = r.table(art['event_features_labels'])
    child = r.table(p['input_bindings']['event_metadata']['all_event_child_requests.csv.gz'])
    assert len(f) == len(child) == 54089
    identities(f, child, child.columns, 'all event child identities')
    numeric = ['sequence_index', 'action_sequence_index', 'mother_sequence_index', 'u_index', 'D_index',
               'u_action_eligible', 'net_R_stress', 'event_center', 'L_centered']
    nums(f, numeric)
    for name in ['L', 'FF4', 'SP500']:
        f[name] = float_tokens(f[name])
    raw = pd.read_csv(io.BytesIO(r.read(p['input_bindings']['fomc_raw'])), dtype=str, keep_default_na=False)
    assert len(raw) == 385
    for name in ['FF4', 'SP500']:
        expected = float_tokens(raw[name]).to_numpy(float)[pd.to_numeric(f.fomc_ordinal).to_numpy(int)]
        eq(f[name], expected, 'raw event ' + name, 0., 0.)
    source = fields.set_index('raw_request_id').reindex(f.raw_request_id)
    eq(f.L, source.log_turnover_source_verified, 'exact pre field join L', 0., 0.)
    boundaries = {}
    dom = np.array([int(x.u_action_eligible) == 1 and domain(x.reference_epoch, int(x.u_index), calendar, boundaries) for x in f.itertuples()])
    mask = truth(source.source_numerically_verified) & np.isfinite(f.L) & np.isfinite(f[['FF4', 'SP500']]).all(axis=1)
    assert np.array_equal(truth(f.pre_domain), dom)
    centered = np.full(len(f), np.nan)
    centers = np.full(len(f), np.nan)
    for _, ix in f.groupby('fomc_event_id', sort=False).indices.items():
        ix = np.asarray(ix, int); eligible = ix[mask[ix] & dom[ix]]
        if not len(eligible):
            mask[ix] = False
            continue
        by_family = f.iloc[eligible].groupby('family_id', sort=False).L.mean()
        center = float(by_family.mean())
        centered[ix] = f.L.to_numpy(float)[ix] - center
        centers[ix] = center
    mask &= dom & np.isfinite(centered)
    eq(f.event_center, centers, 'all event centers', 1e-11, 1e-12)
    eq(f.L_centered, centered, 'all centered pre exposure', 1e-11, 1e-12)
    assert np.array_equal(truth(f.feature_mask), mask)
    with np.load(io.BytesIO(r.read(art['event_common26'])), allow_pickle=False) as z:
        projected = z['common']; projected_sequence = z['sequence_index']; columns = z['columns'].tolist()
    old_common = p['input_bindings']['original_common']; before = stat(old_common['path'])
    READS['original_COMMON'] += 1
    with np.load(old_common['path'], allow_pickle=False) as z:
        whole = z['common']
        assert whole.shape == (1552456, 26) and z['columns'].tolist() == columns
        expected_common = whole[f.sequence_index.to_numpy(int)].astype(float)
        del whole
    assert stat(old_common['path']) == before
    eq(projected_sequence, f.sequence_index, 'projected common identities', 0., 0.)
    eq(projected, expected_common, 'all event COMMON scalars', 0., 0.)
    records = r.doc(art['fit_records'])
    assert len(records) == 12
    base_models = {(x['scope'], x['cutoff']): x for x in p['input_bindings']['original_models']}
    heads, folds = {}, []
    for scope in SCOPES:
        for cutoff in CUTOFFS:
            mature = (f.u_date.ge('2010-01-01') & f.u_date.lt(cutoff) &
                      f.label_state.eq('closed_complete_bar_model') & f.label_known_date.ne('') &
                      f.label_known_date.lt(cutoff) & f.u_action_eligible.eq(1) & mask &
                      np.isfinite(f.net_R_stress))
            if scope != 'main':
                mature &= f.family_id.map(family_hash).ne(int(scope[-1]))
            train = f.loc[mature].copy()
            assert len(train)
            ef = train.groupby('fomc_event_id').family_id.transform('nunique').to_numpy(float)
            ec = train.groupby(['fomc_event_id', 'family_id']).family_id.transform('size').to_numpy(float)
            weights = 1 / (ef * ec); weights /= weights.mean()
            original = base_models[scope, cutoff]
            model, scaler = r.doc(original['portable_model']), r.doc(original['scaler'])
            X = projected[train.index.to_numpy(int)]
            finite = np.isfinite(X)
            Z = np.column_stack([np.where(finite, (X - np.asarray(scaler['common']['mean'])) /
                                         np.asarray(scaler['common']['scale']), 0.), (~finite).astype(float)])
            baseline = Z @ np.asarray(model['coef']) + model['intercept']
            residual = train.net_R_stress.to_numpy(float) - baseline
            values = train[['L_centered', 'FF4', 'SP500']].to_numpy(float)
            mean = np.average(values, axis=0, weights=weights)
            var = np.average((values - mean) ** 2, axis=0, weights=weights)
            scale = np.sqrt(var); scale[scale == 0] = 1
            zz = (values - mean) / scale
            for arm in ARMS:
                record = next(x for x in records if (x['scope'], x['cutoff'], x['arm']) == (scope, cutoff, arm))
                saved_train = r.table(record['training_rows'])
                identities(saved_train, train, ['action_id'], 'mature train order')
                for name, expected in [('sample_weight', weights), ('frozen_base_score', baseline), ('head_target_residual', residual)]:
                    eq(pd.to_numeric(saved_train[name]), expected, 'all train ' + name, 1e-9, 1e-10)
                h = r.doc(record['head'])
                for name, expected in [('mean', mean), ('variance', var), ('scale', scale)]:
                    eq(h['scaler'][name], expected, 'all head scaler ' + name, 1e-10, 1e-10)
                assert h['scaler']['constant'] == (var == 0).tolist()
                design = np.column_stack([np.ones(len(zz)), zz[:, 0]])
                if arm == ARMS[1]:
                    design = np.column_stack([design, zz[:, 1], zz[:, 2], zz[:, 0] * zz[:, 1], zz[:, 0] * zz[:, 2]])
                lhs = design.T @ (weights[:, None] * design)
                penalty = np.eye(design.shape[1]); penalty[0, 0] = 0; lhs += penalty
                rhs = design.T @ (weights * residual); coef = np.asarray(h['coef'])
                eq(h['lhs'], lhs, '12 independent normal lhs', 1e-7, 1e-9)
                eq(h['rhs'], rhs, '12 independent normal rhs', 1e-7, 1e-9)
                eq(lhs @ coef, rhs, '12 unique normal solutions', 1e-7, 1e-9)
                assert h['alpha'] == 1 and h['constant_penalized'] is False and h['interaction_rescaled'] is False
                assert h['event_count'] == train.fomc_event_id.nunique() and h['family_count'] == train.family_id.nunique()
                assert h['max_training_u_date'] == train.u_date.max() and h['max_label_known_date'] == train.label_known_date.max()
                heads[scope, cutoff, arm] = h
                folds.append(dict(scope=scope, cutoff=cutoff, arm=arm, rows=len(train), events=train.fomc_event_id.nunique(),
                                  families=train.family_id.nunique(), max_known_date=train.label_known_date.max()))
    write(out / 'model_phase.json', dict(heads_checked=12, projected_COMMON_scalars=int(projected.size), folds=folds,
          refits=0, original129_Y_revalidation=False, in_sample_baseline_residual=True, conditional_reconstruction=True))
    f['feature_mask'] = mask
    return f, heads, boundaries


def score_increment(frame, head):
    z = (frame[['L_centered', 'FF4', 'SP500']].to_numpy(float) - np.asarray(head['scaler']['mean'])) / np.asarray(head['scaler']['scale'])
    x = np.column_stack([np.ones(len(z)), z[:, 0]])
    if head['arm'] == ARMS[1]:
        x = np.column_stack([x, z[:, 1], z[:, 2], z[:, 0] * z[:, 1], z[:, 0] * z[:, 2]])
    return x @ np.asarray(head['coef'])


def review_forward(r, p, fit, f, heads, calendar, boundaries, out):
    art = fit['artifacts']
    mothers = r.table(art['forward_mothers_projection'])
    old = p['input_bindings']['forward_full_mothers_from156_choices']
    READS['original156_identity_projection'] += 1
    old_before = stat(old['path'])
    old_m = pd.read_csv(old['path'], usecols=list(mothers) + ['chosen_action_id', 'score', 'selected'],
                        dtype=str, keep_default_na=False, float_precision='round_trip')
    assert stat(old['path']) == old_before
    identities(mothers, old_m, list(mothers), 'all161014 forward mother identities')
    assert len(mothers) == 161014 and mothers.product_id.nunique() == 98 and mothers.family_id.nunique() == 95
    causal = r.table(art['causal_actions_projection'])
    assert len(causal) == 966740 and causal.action_id.is_unique
    causal_idx = causal.set_index('action_id', drop=False)
    overlays = r.table(art['event_score_overlays'])
    for c in ['score', 'score_A', 'score_' + ARMS[0], 'score_' + ARMS[1]]:
        overlays[c] = float_tokens(overlays[c])
    overlay_idx = overlays.set_index(['scope', 'cutoff', 'action_id'], verify_integrity=True)
    feature = f.set_index('action_id', verify_integrity=True)
    best, observed, positive_mothers = {}, {}, {}
    counts, states = Counter(), Counter()
    seen = {s: set() for s in SCOPES}
    for scope in SCOPES:
        for arm in ('A',) + ARMS:
            best[scope, arm], observed[scope, arm], positive_mothers[scope, arm] = {}, set(), set()
    score_source = p['input_bindings']['original130_scores']; before = stat(score_source['path'])
    READS['original130_scores'] += 1
    overlay_checked = 0
    for chunk in pd.read_csv(score_source['path'], compression='gzip', dtype=str, keep_default_na=False,
                             chunksize=100000, float_precision='round_trip'):
        base = float_tokens(chunk.score).to_numpy(float)
        for (scope, cutoff), ids0 in chunk.groupby(['scope', 'cutoff'], sort=False).groups.items():
            ids = np.asarray(list(ids0), int) - chunk.index[0]
            sub = chunk.iloc[ids].copy(); count = len(sub)
            assert scope in SCOPES and cutoff in CUTOFFS and np.isfinite(base[ids]).all()
            assert sub.action_id.is_unique and not seen[scope].intersection(sub.action_id)
            seen[scope].update(sub.action_id); counts[scope, cutoff] += count
            if scope == 'main':
                target = causal_idx.reindex(sub.action_id)
                identities(sub.reset_index(drop=True), target.reset_index(drop=True),
                           ['action_id', 'mother_sequence_index', 'mother_event_id', 'product_id', 'family_id', 'u_date',
                            'u_index', 'reference_epoch', 'anchor_epoch', 'u_action_eligible'], 'all forward causal/score identities')
            event_pos = np.flatnonzero(sub.action_id.isin(feature.index).to_numpy())
            actual_event = feature.reindex(sub.action_id.iloc[event_pos]).copy()
            valid = actual_event.feature_mask.to_numpy(bool)
            candidates = {'A': base[ids].copy()}
            for arm in ARMS:
                values = base[ids].copy()
                if valid.any():
                    values[event_pos[valid]] += score_increment(actual_event.iloc[np.flatnonzero(valid)], heads[scope, cutoff, arm])
                candidates[arm] = values
                states[scope, arm, 'applied'] += int(valid.sum())
                states[scope, arm, 'field_missing_fallback_A'] += int(len(event_pos) - valid.sum())
                states[scope, arm, 'non_event_fallback_A'] += count - len(event_pos)
            if len(event_pos):
                keys = pd.MultiIndex.from_arrays([[scope] * len(event_pos), [cutoff] * len(event_pos), sub.action_id.iloc[event_pos]])
                saved = overlay_idx.reindex(keys)
                assert saved.index.equals(keys) and saved.score_A.notna().all()
                eq(saved.score_A, base[ids][event_pos], 'all event baseline saved scores', 0., 0.)
                for arm in ARMS:
                    eq(saved['score_' + arm], candidates[arm][event_pos], 'all event predictions ' + arm, 1e-9, 1e-10)
                    assert saved['head_state_' + arm].tolist() == np.where(valid, 'applied', 'field_missing_fallback_A').tolist()
                overlay_checked += len(event_pos)
            # Stream all original rows once; ranking and family priority are independent code.
            for j, row in enumerate(sub.to_dict('records')):
                parent, u = int(row['mother_sequence_index']), int(row['u_index'])
                assert calendar[u] == row['u_date'] and row['reference_epoch'].rsplit('.', 1)[0] == row['product_id']
                if scope != 'main':
                    assert family_hash(row['family_id']) == int(scope[-1])
                eligible = int(row['u_action_eligible']) == 1
                gate = domain(row['reference_epoch'], u, calendar, boundaries)
                for arm, values in candidates.items():
                    key = scope, arm; value = float(values[j]); observed[key].add(parent)
                    if eligible and value > 0:
                        positive_mothers[key].add(parent)
                        rank = (-value, row['reference_epoch'], row['action_id'])
                        if gate and (parent not in best[key] or rank < best[key][parent][0]):
                            best[key][parent] = (rank, row, value)
    assert stat(score_source['path']) == before
    assert sum(counts.values()) == 1933480 and sum(n for (s, _), n in counts.items() if s == 'main') == 966740
    assert overlay_checked == len(overlays)
    choices = {}
    for scope in SCOPES:
        parents = mothers if scope == 'main' else mothers.loc[mothers.family_id.map(family_hash).eq(int(scope[-1]))]
        for arm in ('A',) + ARMS:
            key = scope, arm
            proposals = best[key]
            winners = {}
            order = sorted(proposals.items(), key=lambda kv: (int(kv[1][1]['u_index']), kv[1][1]['family_id'],
                        kv[1][1]['product_id'].endswith('_F'), kv[1][1]['product_id'], kv[1][1]['reference_epoch'], kv[1][1]['action_id']))
            for parent, (_, row, value) in order:
                winners.setdefault((row['family_id'], int(row['u_index'])), (parent, row, value))
            winning = {v[0]: v for v in winners.values()}
            saved = r.table(art['choices_' + scope + '_' + arm])
            identities(saved, parents, list(mothers), 'all prospective mother identities')
            expected_ids, scores, statuses = [], [], []
            for row in parents.itertuples(index=False):
                seq = int(row.sequence_index); win = winning.get(seq)
                expected_ids.append(win[1]['action_id'] if win else '')
                scores.append(win[2] if win else np.nan)
                statuses.append('selected' if win else 'family_priority_suppressed' if seq in proposals else
                                'no_observed_children' if seq not in observed[key] else
                                'no_calendar_eligible_positive_action' if seq in positive_mothers[key] else 'no_original_eligible_positive_action')
            assert saved.chosen_action_id.tolist() == expected_ids and saved.selection_state.tolist() == statuses
            eq(pd.to_numeric(saved.score.replace('', np.nan)), scores, 'all choice scores', 1e-9, 1e-10)
            assert truth(saved.selected).tolist() == [bool(x) for x in expected_ids]
            assert saved.scope.eq(scope).all() and saved.candidate.eq(arm).all() and saved.policy.eq('NARROW').all()
            if scope == 'main' and arm == 'A':
                assert saved.chosen_action_id.tolist() == old_m.chosen_action_id.tolist()
                assert saved.selected.tolist() == old_m.selected.tolist()
                eq(pd.to_numeric(saved.score.replace('', np.nan)), pd.to_numeric(old_m.score.replace('', np.nan)),
                   'full A original156 chosen scores', 0., 0.)
            choices[key] = saved
    write(out / 'forward_phase.json', dict(original_score_rows=sum(counts.values()), event_overlays=overlay_checked,
          forward_mothers=161014, full_products=98, full_families=95, full_causal_action_rows=len(causal),
          all_scope_arm_choices_checked=9, exact_passthrough_by_static_rule_and_full_selection_reconciliation=True,
          inherited_score_stream_reads=1))
    return mothers, causal, choices, states


def held_contrast(active, control, labels):
    labels = labels.set_index('action_id', verify_integrity=True)
    def values(frame):
        x = frame.assign(_selected=pd.to_numeric(frame.selected)).sort_values('_selected', ascending=False, kind='stable')
        x = x.drop_duplicates(['family_id', 'u_index']).set_index(['family_id', 'u_index']).sort_index()
        result = []
        for aid in x.chosen_action_id:
            if not aid:
                result.append(0.)
            elif aid not in labels.index:
                result.append(np.nan)
            else:
                q = labels.loc[aid]
                result.append(0. if q.participation_state == 'known_nonparticipation' else float(q.net_R_stress)
                              if q.label_state == 'closed_complete_bar_model' and q.label_known_date and
                              q.label_known_date <= END and np.isfinite(q.net_R_stress) else np.nan)
        return x, np.asarray(result)
    a, av = values(active); b, bv = values(control)
    assert a.index.equals(b.index) and a.u_date.equals(b.u_date)
    same = a.chosen_action_id.eq(b.chosen_action_id).to_numpy()
    known = np.isfinite(av) & np.isfinite(bv)
    delta = np.where(same, 0., np.where(known, av - bv, np.nan))
    daily = pd.DataFrame(dict(u_date=a.u_date.to_numpy(), delta_R=delta)).groupby('u_date').delta_R.mean()
    return dict(known_u_equal_mean_increment_R=float(daily.mean()) if daily.notna().any() else None,
                unknown_differential_selected_events=int((~same & ~known).sum()),
                full_family_u=len(a), known_increment_family_u=int(np.isfinite(delta).sum()))


def restore_native(r, p, calendar, old_review):
    deps = p['cash_contract_inherited_exact']['market_dependencies_inherited']
    meta = r.doc(deps['native_cache_manifest'])
    assert meta['native_rows'] == 1552456 and meta['native_epochs'] == 9520
    store = old_review.NativeBars(calendar)
    READS['native_cache'] += 1
    with np.load(io.BytesIO(r.read(deps['native_cache'])), allow_pickle=False) as z:
        epochs, offsets = z['epochs'].tolist(), z['offsets']
        flat = {k: z[k] for k in ['days', 'values', 'accepted', 'valid', 'N', 'low20', 'run']}
        assert len(epochs) == 9520 and offsets[-1] == 1552456
        for i, epoch in enumerate(epochs):
            store.series[epoch] = {k: x[int(offsets[i]):int(offsets[i + 1])] for k, x in flat.items()}
    return store


def review_cash(r, p, fit, cash_manifest, mothers, causal, choices, features, calendar, economics, out):
    old = module('stage132_contract_choice_review.py')
    sys.path.insert(0, str(TOOLS))
    cash, diag = old.independent_helpers()
    old.CASH_HELPER = cash
    cash.review_budgets = old.review_capped_budgets
    store = restore_native(r, p, calendar, old)
    root = Path(cash_manifest['terminal']['path']).parent
    families = sorted(mothers.family_id.unique())
    all_family = r.path_table(root / 'family_year_including_zero.csv.gz')
    nums(all_family, ['net_equity_contribution', 'fee', 'slippage', 'fill_count', 'filled_qty'])
    diagnostics = r.doc(r.bindings[str((root / 'diagnostics.json').resolve())])
    held_saved = r.doc(fit['artifacts']['held_gate'])['contrasts']
    held = {}
    pair_arms = {'B_minus_A': (ARMS[0], 'A'), 'C_minus_A': (ARMS[1], 'A'), 'C_minus_B': (ARMS[1], ARMS[0])}
    for name, (a, b) in pair_arms.items():
        held[name] = {}
        for scope in SCOPES[1:]:
            result = held_contrast(choices[scope, a], choices[scope, b], features)
            saved = held_saved[name]['groups'][scope]
            for key, value in result.items():
                if value is None:
                    assert saved[key] is None
                elif isinstance(value, float):
                    eq(saved[key], value, 'held ' + name + ' ' + key, 1e-12, 1e-10)
                else:
                    assert saved[key] == value
            held[name][scope] = result
    selected_actions = causal.set_index('action_id', verify_integrity=True)
    nums(selected_actions, ['action_sequence_index', 'mother_sequence_index', 'u_index', 'u_action_eligible',
                           'entry_capacity_qty', 'N_u', 'low20_u', 'u_close'])
    all_summaries, all_daily, all_logs, reports, counts = {}, {}, {}, {}, []
    for arm in ARMS:
        picked = choices['main', arm].loc[pd.to_numeric(choices['main', arm].selected).eq(1)]
        signal = selected_actions.loc[picked.chosen_action_id].copy()
        signal['potential'] = 1
        signal['planned_execution_date'] = [calendar[int(x) + 1] for x in signal.u_index]
        signal = signal.set_index('event_id', drop=False)
        for x in signal.itertuples():
            s = store.series[x.reference_epoch]; j = store.locate(x.reference_epoch, int(x.u_index))
            assert j is not None and bool(s['valid'][j]) and int(s['run'][j]) >= 20
            eq([x.N_u, x.low20_u, x.u_close], [s['N'][j], s['low20'][j], s['values'][j, 3]], 'all selected native causal values', 1e-10, 1e-10)
            assert x.u_action_eligible == 1
        for window, bounds in p['cash']['windows'].items():
            for cost in p['cash']['costs']:
                name = f'NARROW_{arm}_{window}_{cost}'
                folder = root / name
                old.ACTIVE_POSITIONS = cash.csv(folder / 'positions.csv.gz')
                account = cash.review_account(folder, cost, dict(id=window, start=bounds[0], end=bounds[1]), {}, signal, economics, calendar, .25)
                extra = old.account_native_and_capacity(folder, signal, mothers, store, economics, account['summary'], cost)
                summary = account['summary']
                fy = all_family.loc[all_family.arm.eq(arm) & all_family.window.eq(window) & all_family.cost.eq(cost)]
                daily, log, diagnostic_count, _ = diag._account(folder, summary, diagnostics[name], fy, families)
                diag._daily_summary(daily, summary, 1000000.)
                key = arm, window, cost
                all_summaries[key], all_daily[key], all_logs[key], reports[name] = summary, daily, log, diagnostics[name]
                counts.append(dict(account_id=name, fills=account['fills_checked'], daily=account['daily_rows_checked'],
                                   positions=account['position_rows_checked'], budgets=account['budgets_checked']['rows'],
                                   closed=account['closed_roots_checked'], native_capacity=extra, diagnostics=diagnostic_count))
                write(out / (name + '_audit.json'), counts[-1])
    # A's four own accounts are reused; independently reconcile saved daily metrics,
    # never invoke a strategy kernel or review different131 control books.
    for control in p['cash_contract_inherited_exact']['control_accounts_reused']:
        name = control['account_id']; key = 'A', control['window'], control['cost']
        assert name == 'NARROW_VOLUNTARY_RESELECT_' + control['window'] + '_' + control['cost']
        summary = r.doc(control['summary'])
        item = control['ledgers_relative_to_directory']['daily']
        b = dict(path=str(Path(control['directory']) / item['file']), bytes=item['bytes'], sha256=item['sha256'])
        daily = pd.read_csv(io.BytesIO(r.read(b)), compression='gzip', dtype={'date': str}, float_precision='round_trip')
        diag._daily_summary(daily, summary, 1000000.)
        all_summaries[key], all_daily[key], all_logs[key] = summary, daily, diag._log(daily, 1000000.)
    control_reports = r.doc(p['input_bindings']['A157_diagnostics'])
    for control in p['cash_contract_inherited_exact']['control_accounts_reused']:
        reports[control['account_id']] = control_reports[control['account_id']]
    comparisons = r.path_table(root / 'comparisons.csv.gz')
    distributions = r.path_table(root / 'bootstrap_distributions.csv.gz')
    decision = r.doc(r.bindings[str((root / 'decision.json').resolve())])
    assert len(comparisons) == 12 and len(distributions) == 2000
    supported = {}
    for contrast, (a, b) in pair_arms.items():
        scenario_pass = []
        for window, ib in p['statistics']['bootstrap_indices'].items():
            index = np.load(io.BytesIO(r.read(ib)), allow_pickle=False)
            for cost in p['cash']['costs']:
                ka, kb = (a, window, cost), (b, window, cost)
                da, db = all_daily[ka], all_daily[kb]
                assert da.date.tolist() == db.date.tolist() and index.shape == (2000, len(da))
                sa, sb = all_summaries[ka], all_summaries[kb]
                saved = comparisons.loc[comparisons.contrast.eq(contrast) & comparisons.window.eq(window) & comparisons.cost.eq(cost)]
                assert len(saved) == 1
                q = saved.iloc[0]
                for field, expected in [('active_total_return_pct', sa['total_return_pct']),
                                        ('reference_total_return_pct', sb['total_return_pct']),
                                        ('return_percentage_point_difference', sa['total_return_pct'] - sb['total_return_pct']),
                                        ('ending_equity_difference', sa['ending_equity'] - sb['ending_equity'])]:
                    eq(float(q[field]), expected, 'all paired metrics ' + field)
                dd = None if sb['fills'] == 0 else sa['max_drawdown_pct'] - sb['max_drawdown_pct']
                eq(float(q.drawdown_percentage_point_difference) if q.drawdown_percentage_point_difference else np.nan,
                   dd if dd is not None else np.nan, 'all paired DD')
                la, lb = all_logs[ka], all_logs[kb]
                lo = hi = None
                if la is None or lb is None:
                    expected_dist = np.full(2000, np.nan)
                else:
                    delta = la - lb; expected_dist = delta[index].mean(axis=1)
                    lo, hi = np.quantile(expected_dist, [.025, .975])
                    eq([float(q.ci95_low), float(q.ci95_high), float(q.mean_daily_log_difference), float(q.cumulative_log_difference)],
                       [lo, hi, delta.mean(), delta.sum()], 'all paired CI and growth', 1e-12, 1e-10)
                eq(pd.to_numeric(distributions[contrast + '_' + window + '_' + cost].replace('', np.nan)),
                   expected_dist, 'all 2000 bootstrap draws', 1e-12, 1e-10)
                strict = (window, cost) == ('primary_2020', 'stress')
                improve = sa['total_return_pct'] - sb['total_return_pct']
                scenario_pass.append(sa['total_return_pct'] > 0 and (improve > 0 if strict else improve >= 0) and
                                     dd is not None and (dd > 0 if strict else dd >= 0) and
                                     (not strict or lo is not None and lo > 0))
        held_pass = all(x['known_u_equal_mean_increment_R'] is not None and x['known_u_equal_mean_increment_R'] >= 0
                        and x['unknown_differential_selected_events'] == 0 for x in held[contrast].values())
        any_stale = any(x['stale_days'] > 0 for x in reports.values())
        any_unknown = any(x.get('execution_unknown', False) for x in all_summaries.values())
        wealth = all(x is not None for x in all_logs.values())
        supported[contrast] = bool(all(scenario_pass) and held_pass and not any_stale and not any_unknown and wealth)
        assert decision['contrasts'][contrast]['nominal_pass'] == supported[contrast]
    assert decision['nominal_pass'] == (supported['C_minus_B'] and supported['C_minus_A'])
    for flag in ['alpha_proved', 'causal_identification', 'historical_first_seen_PIT_proved',
                 'increased_betting_qualified', 'production_qualified', 'goal_complete']:
        assert decision[flag] is False
    # All same-book2025 rows are descriptive truncations, with no added account.
    through = r.path_table(root / 'same_book_through_2025.csv.gz')
    assert len(through) == 12
    for q in through.to_dict('records'):
        key = q['arm'], q['window'], q['cost']; d = all_daily[key].loc[all_daily[key].date.le('2025-12-31')]
        path = np.r_[1000000., d.equity.to_numpy(float)]
        eq([float(q['ending_equity']), float(q['total_return_pct']), float(q['max_drawdown_pct'])],
           [path[-1], (path[-1] / 1000000. - 1) * 100, (path / np.maximum.accumulate(path) - 1).min() * 100], 'all samebook through2025')
        assert str(q['new_account']).lower() == str(q['capital_reset']).lower() == 'false'
    report = dict(accounts_checked=8, reused_A_accounts=4, fills_checked=sum(x['fills'] for x in counts),
                  daily_rows_checked=sum(x['daily'] for x in counts), account_checks=counts,
                  contrasts_checked=12, bootstrap_draws_per_contrast=2000, strategy_replays=0,
                  estimator_fits=0, conditional_nominal_pass=decision['nominal_pass'], decision=decision)
    write(out / 'cash_phase.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for role in ['protocol', 'source-manifest', 'fit-manifest', 'cash-manifest']:
        parser.add_argument('--' + role, required=True)
        parser.add_argument('--' + role + '-sha256', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--resume-source-phase')
    parser.add_argument('--resume-source-phase-sha256')
    parser.add_argument('--prior-terminal')
    parser.add_argument('--prior-terminal-sha256')
    args = parser.parse_args()
    out = Path(args.output).resolve()
    assert LINE / 'outputs/stage490_fomc_economic_independent_review' in out.parents
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic(); status = 'failed'; error = None
    r = Reader()
    write(out / 'started.json', dict(started_at=datetime.now(timezone.utc).isoformat(), arguments=vars(args),
          one_bounded_review=True, researcher_fits_cash=0, original129_Y_CSV_H5_mother_reads=0))
    try:
        manifests = {}
        for role in ['protocol', 'source_manifest', 'fit_manifest', 'cash_manifest']:
            b = bind(getattr(args, role))
            assert b['sha256'] == getattr(args, role + '_sha256'), role
            if role == 'protocol':
                assert b['sha256'] == PROTO_SHA
            manifests[role] = r.doc(b)
        p, source, fit, cm = (manifests[x] for x in ['protocol', 'source_manifest', 'fit_manifest', 'cash_manifest'])
        assert source['schema'] == 'stage488_pre_fields_manifest_v1'
        assert fit['status'] == cm['status'] == 'completed'
        assert fit['new_fits_attempted'] == fit['new_fits_completed'] == 12 and cm['new_cash_accounts'] == 8
        for m in [source, fit]:
            assert m['protocol_sha256'] == PROTO_SHA
        assert cm['metadata']['protocol']['sha256'] == PROTO_SHA
        for m in [source, fit, cm]:
            r.register(m['artifacts'])
            r.register(m.get('source_bundle', []))
        assert r.doc(source['artifacts']['terminal'])['completed'] is True
        assert r.doc(fit['terminal'])['status'] == r.doc(cm['terminal'])['status'] == 'completed'
        calendar_array = np.load(io.BytesIO(r.read(p['input_bindings']['calendar'])), allow_pickle=False)
        calendar = [f'{int(x):08d}'[:4] + '-' + f'{int(x):08d}'[4:6] + '-' + f'{int(x):08d}'[6:] for x in calendar_array]
        assert len(calendar) == 5587 and calendar == sorted(set(calendar))
        inherited = None
        if args.resume_source_phase:
            phase_binding = bind(args.resume_source_phase)
            prior_binding = bind(args.prior_terminal)
            assert phase_binding['sha256'] == args.resume_source_phase_sha256 == 'c57aa3b166ff16dec8de183d973afa174fae36a569cb7c1dc470cd91bcaa7028'
            assert prior_binding['sha256'] == args.prior_terminal_sha256 == 'dd88a0646ef33a202d12f76818f0bcbc14086fa668dc1dcb037fa7f227539b92'
            source_report = r.doc(phase_binding)
            prior = r.doc(prior_binding)
            assert prior['status'] == 'failed' and prior['actual_input_budget'] == {'pre_exact_SQL': 1}
            assert prior['error']['message'] == "('raw event FF4', 1.0061396160665481e-16)"
            assert source_report['request_rows'] == 54089 and source_report['source_SQL'] == 1
            inherited = dict(source_phase=phase_binding, prior_terminal=prior_binding,
                             source_SQL_in_current_process=0, source_values_not_reaudited=True,
                             new_source_field_and_event_artifact_rereads_explicit=True)
            write(out / 'source_phase_inherited.json', inherited)
            READS['pre_exact_SQL'] = 1  # Cumulative, already spent in the prior accepted source phase.
            fields = r.table(source['artifacts']['exact_pre_fields'])
            nums(fields, ['log_turnover_source_verified'])
            economics = r.doc(p['source_fields']['inputs']['economics'])['instruments']
        else:
            fields, economics, source_report = review_source(r, p, source, out)
        features, heads, boundaries = review_models(r, p, fit, fields, calendar, out)
        mothers, causal, choices, states = review_forward(r, p, fit, features, heads, calendar, boundaries, out)
        cash_report = review_cash(r, p, fit, cm, mothers, causal, choices, features, calendar, economics, out)
        r.finish()
        assert READS == Counter(pre_exact_SQL=1, original_COMMON=1, original130_scores=1,
                                original156_identity_projection=1, native_cache=1)
        receipt = dict(schema='stage490_fomc_economic_actual_review_v1', completed=True, P0=0, P1=0, P2=0,
                       actual_input_budget=dict(READS), sources=source_report, cash=cash_report,
                       max_abs_errors=ERRORS, reviewer_estimator_fits=0, reviewer_strategy_cash_replays=0,
                       original129_Y_original_CSV_H5_original_mother_rescans=0,
                       inherited_source_parser_original_Y_qualification=True,
                       inherited_completed_source_phase=inherited,
                       independent_original_raw_values_recertified=False,
                       historical_first_seen_PIT_qualified=False, alpha_proved=False, goal_complete=False)
        write(out / 'review_receipt.json', receipt)
        status = 'completed'
        print(json.dumps(dict(status=status, P0=0, P1=0, P2=0, output=str(out)), ensure_ascii=False), flush=True)
    except BaseException as exc:
        error = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
        write(out / 'failure.json', error)
        raise
    finally:
        write(out / 'terminal.json', dict(status=status, elapsed_seconds=time.monotonic() - start, error=error,
              actual_input_budget=dict(READS), no_automatic_retry=True, reviewer_fits_cash_replays=0))


if __name__ == '__main__':
    main()
