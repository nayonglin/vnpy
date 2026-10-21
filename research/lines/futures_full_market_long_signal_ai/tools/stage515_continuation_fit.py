"""One fixed continuation-policy improvement. Import is research-I/O free.

The CLI needs an exact root514 protocol and explicit root authorization. It
joins the four accepted511 derived tables once, retains a compact audit source,
fits six tiny linear heads, and evaluates selected *unit* paths, never cash.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timezone
from functools import lru_cache
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import time
import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
CUTOFFS = ('2020-01-01', '2023-01-01')
SCOPES = ('main', 'holdout_0', 'holdout_1')
KNOWN_QUOTE = 'observed_research_quote'
MISSING_DAY = np.iinfo(np.int32).max
RAW_STATE_FIELDS = ('mark', 'SL0', 'boundary_next', 'close', 'previous_close',
                    'N_t', 'R0', 'age_source_days')
FEATURES = ('distance_SL0_R0', 'distance_boundary_R0', 'close_change_R0',
            'current_N_R0', 'age_source_days', 'remaining_calendar_days')
QUOTE_COLUMNS = ('multiplier', 'stress_terminal_fill', 'stress_terminal_fee',
    'stress_voluntary_fill', 'stress_voluntary_fee', 'base_terminal_fill',
    'base_terminal_fee', 'base_voluntary_fill', 'base_voluntary_fee')


def number(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return float('nan')


@lru_cache(maxsize=18000)
def day_number(value):
    if not value:
        return MISSING_DAY
    try:
        return date.fromisoformat(str(value)[:10]).toordinal()
    except (TypeError, ValueError):
        return MISSING_DAY


def raw_features(state):
    """Only current state and true, announced date targets; no final outcomes."""
    mark, sl, boundary, close, previous, n, risk, age = (
        number(state.get(key)) for key in RAW_STATE_FIELDS)
    x = np.full(6, np.nan)
    if math.isfinite(risk) and risk > 0:
        x[:4] = ((mark-sl)/risk, (mark-boundary)/risk,
                 (close-previous)/risk, n/risk)
    x[4] = age
    source = day_number(state.get('source_lifecycle_target_date'))
    k = day_number(state.get('K_target_date'))
    t = day_number(state.get('t_date'))
    # Both actual target dates are required; calendar-length sentinel is not one.
    if max(source, k, t) != MISSING_DAY:
        x[5] = min(source, k)-t
    x[~np.isfinite(x)] = np.nan
    return x


def paired_target(baseline, voluntary, risk, cost):
    """Future net SELL difference / fixed original risk; BUY is already sunk."""
    if baseline.get(cost+'_terminal_SELL_quote_state') != KNOWN_QUOTE or \
            voluntary.get(cost+'_SELL_quote_state') != KNOWN_QUOTE:
        return float('nan')
    mult = number(baseline.get('contract_multiplier'))
    vals = [number(baseline.get(cost+'_terminal_SELL_'+key)) for key in
            ('fill_price', 'fee_per_lot')]
    vals += [number(voluntary.get(cost+'_SELL_'+key)) for key in
             ('fill_price', 'fee_per_lot')]
    risk = number(risk)
    if not all(math.isfinite(x) for x in [mult, risk]+vals) or min(mult, risk) <= 0:
        return float('nan')
    bf, fee_b, vf, fee_v = vals
    return (mult*(bf-vf)-fee_b+fee_v)/(risk*mult)


def date_family_weights(days, families):
    """Each date one mass, each family within date one mass, then all paths."""
    days, families = np.asarray(days), np.asarray(families)
    if len(days) == 0 or len(days) != len(families):
        raise ValueError('nonempty aligned weighting domain required')
    pairs = np.rec.fromarrays((days, families), names='day,family')
    unique, inverse, counts = np.unique(pairs, return_inverse=True, return_counts=True)
    _, date_inverse, families_per_day = np.unique(unique.day,
        return_inverse=True, return_counts=True)
    w = 1./(counts[inverse]*families_per_day[date_inverse[inverse]])
    return w/w.sum()


def training_mask(data, cutoff_day, scope):
    mask = ((data['u_day'] < cutoff_day) & (data['k_day'] < cutoff_day) &
            (data['t_day'] < cutoff_day) & (data['baseline_day'] < cutoff_day) &
            (data['voluntary_day'] < cutoff_day) & data['entry_supported'].astype(bool) &
            np.isfinite(data['y_stress']))
    if scope != 'main':
        mask &= data['family_hash'] != int(scope[-1])
    return mask


def fit_scaler(raw, weights):
    raw = np.asarray(raw, float); weights = np.asarray(weights, float)
    means, scales, observed_weight = [], [], []
    for j in range(6):
        valid = np.isfinite(raw[:, j]); total = weights[valid].sum()
        mean = float(np.sum(weights[valid]*raw[valid, j])/total) if total else 0.
        var = float(np.sum(weights[valid]*(raw[valid, j]-mean)**2)/total) if total else 0.
        means.append(mean); scales.append(math.sqrt(var) if var > 0 else 1.)
        observed_weight.append(float(total))
    return dict(mean=means, scale=scales, observed_weight=observed_weight,
                missing_imputation='train_weighted_mean', missing_flags_scaled=False)


def design_matrix(raw, scaler):
    raw = np.asarray(raw, float)
    if raw.ndim == 1:
        raw = raw[None, :]
    missing = ~np.isfinite(raw)
    z = (raw-np.asarray(scaler['mean']))/np.asarray(scaler['scale'])
    z[missing] = 0.
    return np.column_stack((np.ones(len(raw)), z, missing.astype(float)))


def fit_head(raw, y, weights, scaler=None):
    weights, y = np.asarray(weights, float), np.asarray(y, float)
    if len(y) == 0 or not np.isfinite(y).all() or not np.isfinite(weights).all() or \
            (weights <= 0).any() or not np.isclose(weights.sum(), 1., rtol=0, atol=1e-12):
        raise ValueError('finite training target / positive sum-one weights required')
    scaler = fit_scaler(raw, weights) if scaler is None else scaler
    design = design_matrix(raw, scaler)
    gram = design.T@(weights[:, None]*design)
    penalty = np.eye(13); penalty[0, 0] = 0.
    lhs = gram+penalty; rhs = design.T@(weights*y)
    coef = np.linalg.solve(lhs, rhs)
    residual = float(np.max(np.abs(lhs@coef-rhs)))
    if not np.isfinite(coef).all() or residual > 1e-8:
        raise ValueError('normal equation or finite coefficient failure')
    prediction = design@coef
    return dict(**scaler, coef=coef.tolist(), alpha=1., weight_sum=float(weights.sum()),
        intercept_penalized=False, training_rows=len(y), normal_lhs=lhs.tolist(),
        normal_rhs=rhs.tolist(), weighted_gram=gram.tolist(),
        normal_equation_max_abs_residual=residual,
        effective_df=float(np.trace(np.linalg.solve(lhs, gram))),
        weighted_target_mean=float(weights@y), weighted_prediction_mean=float(weights@prediction),
        weighted_mse=float(weights@((prediction-y)**2)))


def cutoff_for(t_date):
    return None if t_date < CUTOFFS[0] else CUTOFFS[0] if t_date < CUTOFFS[1] else CUTOFFS[1]


def predict_state(models, t_date, state, scope='main'):
    cutoff = cutoff_for(t_date)
    if cutoff is None:
        return dict(prediction=None, cutoff=None, status='before_first_cutoff_hold')
    model = models.get(scope+'|'+cutoff)
    if model is None:
        return dict(prediction=None, cutoff=cutoff, status='missing_head_hold')
    prediction = float(design_matrix(raw_features(state), model)[0]@np.asarray(model['coef']))
    return dict(prediction=prediction if math.isfinite(prediction) else None, cutoff=cutoff,
                status='predicted' if math.isfinite(prediction) else 'nonfinite_prediction_hold')


def first_negative(values):
    for j, value in enumerate(values):
        if math.isfinite(number(value)) and float(value) < 0:
            return j
    return None


def unchanged_terminal_delta(anchor, cost):
    """No request through END is not proof of identical *future* terminal value."""
    known_cancel = {'u_ineligible', 'D_not_before_K', 'lifecycle_entry_rejected',
                    'stale_breakout_cancel_at_open', 'invalid_initial_risk_cancel'}
    if anchor.get('participation_state') in known_cancel:
        return 0.
    if anchor.get('participation_state') == 'entered' and \
            anchor.get('terminal_state') == 'closed_complete_bar_model' and \
            anchor.get(cost+'_terminal_SELL_quote_state') == KNOWN_QUOTE and \
            day_number(anchor.get('available_at')) <= day_number('2026-10-16'):
        return 0.
    return float('nan')


def safe(obj):
    if isinstance(obj, dict): return {str(k): safe(v) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)): return [safe(v) for v in obj]
    if isinstance(obj, np.ndarray): return safe(obj.tolist())
    if isinstance(obj, (np.integer, np.bool_)): return obj.item()
    if isinstance(obj, (float, np.floating)): return float(obj) if math.isfinite(obj) else None
    return obj


def binding(path):
    path = Path(path).resolve(); h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=h.hexdigest())


def write_json(path, obj):
    with Path(path).open('x') as f:
        json.dump(safe(obj), f, ensure_ascii=False, indent=2, allow_nan=False); f.write('\n')
    return binding(path)


def read_bound(bound, receipt, role):
    p = Path(bound['path']); before = p.stat(); raw = p.read_bytes(); after = p.stat()
    if len(raw) != bound['bytes'] or hashlib.sha256(raw).hexdigest() != bound['sha256']:
        raise ValueError('input identity changed: '+role)
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('input changed during unique read: '+role)
    receipt[role] = dict(binding=bound, physical_reads=1, bytes_read=len(raw))
    return raw


def csv_rows(bound, fields, receipt, role):
    raw = read_bound(bound, receipt, role)
    for frame in pd.read_csv(io.BytesIO(raw), compression='gzip', usecols=fields,
                             dtype=str, keep_default_na=False, chunksize=20000):
        for values in frame[fields].itertuples(index=False, name=None):
            yield dict(zip(fields, values))


class Cursor:
    def __init__(self, rows):
        self.rows = iter(rows); self.current = next(self.rows, None)
    def take(self, sequence):
        result = []
        while self.current is not None and int(self.current['sequence_index']) == sequence:
            result.append(self.current); self.current = next(self.rows, None)
        if self.current is not None and int(self.current['sequence_index']) < sequence:
            raise ValueError('derived join ordering broken')
        return result


SUMMARY_FIELDS = ['sequence_index', 'action_id', 'product_id', 'family_id', 'reference_epoch',
    'u_date', 'family_hash_group', 'u_action_eligible', 'participation_state', 'terminal_state',
    'K_date', 'K_target_date', 'source_lifecycle_target_date', 'entry_date', 'riskset_count',
    'state_count', 'stale_count']
STATE_FIELDS = ['sequence_index', 'action_id', 'family_id', 'family_hash_group',
    't_index', 't_date', 'riskset', *RAW_STATE_FIELDS, 'source_lifecycle_target_date', 'K_target_date']
BASE_FIELDS = ['sequence_index', 'action_id', 'contract_multiplier', 'available_at', 'available_phase',
    'stress_entry_BUY_quote_state', 'stress_entry_SELL_estimate_quote_state'] + [
        f'{cost}_terminal_SELL_{key}' for cost in ('base', 'stress')
        for key in ('quote_state', 'fill_price', 'fee_per_lot')]
VOL_FIELDS = ['sequence_index', 'action_id', 't_index', 't_date', 'available_at', 'available_phase'] + [
    f'{cost}_SELL_{key}' for cost in ('base', 'stress')
    for key in ('quote_state', 'fill_price', 'fee_per_lot')]


def extract_compact(inputs, out, receipt, expected, calendar=None, selected_sequences=None):
    cursors = {name: Cursor(csv_rows(inputs[name], fields, receipt, name)) for name, fields in (
        ('unit_states', STATE_FIELDS), ('baseline_terminal_observations', BASE_FIELDS),
        ('voluntary_exit_observations', VOL_FIELDS))}
    total = expected['decision_riskset_states']
    ints = ('sequence', 't_index', 't_day', 'u_day', 'k_day', 'source_target_day',
            'k_target_day', 'baseline_day', 'voluntary_day', 'family_code', 'family_hash')
    data = {key: np.empty(total, dtype=np.int32) for key in ints}
    data.update(X=np.empty((total, 6)), raw_state=np.empty((total, 8)),
        quotes=np.empty((total, 9)), quote_codes=np.empty((total, 6), dtype=np.int16),
        phase_codes=np.empty((total, 2), dtype=np.int16),
        entry_supported=np.empty(total, dtype=bool), y_stress=np.empty(total), y_base=np.empty(total))
    quote_vocab, phase_vocab, families = {}, {}, {}
    def encode(vocab, key):
        if key not in vocab: vocab[key] = len(vocab)
        return vocab[key]
    cohort = defaultdict(Counter); n = state_count = summary_count = baseline_count = 0
    identity_map = {}
    selected_anchors = {}; selected_sequences = selected_sequences or set()
    identity_path = out/'action_identity.csv.gz'
    with gzip.open(identity_path, 'xt', newline='') as identity_file:
        identity_writer = csv.DictWriter(identity_file, fieldnames=SUMMARY_FIELDS)
        identity_writer.writeheader()
        for a in csv_rows(inputs['action_path_summary'], SUMMARY_FIELDS, receipt, 'action_path_summary'):
            seq = int(a['sequence_index'])
            if seq != summary_count: raise ValueError('full action sequence differs')
            summary_count += 1
            g = int(a['family_hash_group']); fam = a['family_id']
            if int(hashlib.sha256(fam.encode()).hexdigest(), 16) % 2 != g:
                raise ValueError('family hash identity differs')
            ud, kd = day_number(a['u_date']), day_number(a['K_date'])
            for cutoff in CUTOFFS:
                if ud < day_number(cutoff) and kd < day_number(cutoff):
                    for scope in SCOPES:
                        if scope != 'main' and g == int(scope[-1]): continue
                        c = cohort[cutoff+'|'+scope]; c['all_cohort_actions'] += 1
                        c['u_eligible_actions'] += int(a['u_action_eligible'])
                        c['participation:'+a['participation_state']] += 1
                        c['terminal:'+a['terminal_state']] += 1
                        c['held_close_states_alltime'] += int(a['state_count'])
                        c['riskset_states_alltime'] += int(a['riskset_count'])
            terminals = cursors['baseline_terminal_observations'].take(seq)
            states = cursors['unit_states'].take(seq)
            voluntary = cursors['voluntary_exit_observations'].take(seq)
            state_count += len(states); baseline_count += len(terminals)
            if len(terminals) > 1: raise ValueError('duplicate baseline terminal')
            b = terminals[0] if terminals else {}
            if seq in selected_sequences:
                selected_anchors[seq] = dict(sequence=seq,action_id=a['action_id'],
                    participation_state=a['participation_state'],terminal_state=a['terminal_state'],
                    available_at=b.get('available_at',''),available_phase=b.get('available_phase',''),
                    **{cost+'_terminal_SELL_quote_state': b.get(cost+'_terminal_SELL_quote_state','')
                       for cost in ('base','stress')})
            if states and not b: raise ValueError('held states lack unit baseline record')
            if int(a['riskset_count']) != len(voluntary) or int(a['state_count']) != len(states):
                raise ValueError('per-action source conservation differs')
            if voluntary:
                identity_writer.writerow(a)
                identity_map[seq] = a['action_id']
            v_cursor = iter(voluntary)
            for state in states:
                if int(state['riskset']) != 1: continue
                v = next(v_cursor, None)
                if v is None or v['action_id'] != a['action_id'] or state['action_id'] != a['action_id'] or \
                        int(v['t_index']) != int(state['t_index']) or state['family_id'] != fam:
                    raise ValueError('state/voluntary exact identity join differs')
                if n >= total: raise ValueError('riskset exceeds accepted count')
                if calendar is not None and (not 0 <= int(state['t_index']) < len(calendar) or
                        calendar[int(state['t_index'])] != state['t_date']):
                    raise ValueError('state calendar clock identity differs')
                if fam not in families: families[fam] = len(families)
                fixed = dict(sequence=seq, t_index=int(state['t_index']), t_day=day_number(state['t_date']),
                    u_day=ud, k_day=kd, source_target_day=day_number(state['source_lifecycle_target_date']),
                    k_target_day=day_number(state['K_target_date']), baseline_day=day_number(b.get('available_at')),
                    voluntary_day=day_number(v['available_at']), family_code=families[fam], family_hash=g)
                for key, value in fixed.items(): data[key][n] = value
                data['X'][n] = raw_features(state)
                data['raw_state'][n] = [number(state.get(k)) for k in RAW_STATE_FIELDS]
                data['entry_supported'][n] = (b.get('stress_entry_BUY_quote_state') == KNOWN_QUOTE and
                    b.get('stress_entry_SELL_estimate_quote_state') == KNOWN_QUOTE)
                data['quote_codes'][n] = [encode(quote_vocab, value) for value in (
                    b.get('stress_entry_BUY_quote_state', ''), b.get('stress_entry_SELL_estimate_quote_state', ''),
                    b.get('stress_terminal_SELL_quote_state', ''), v.get('stress_SELL_quote_state', ''),
                    b.get('base_terminal_SELL_quote_state', ''), v.get('base_SELL_quote_state', ''))]
                data['phase_codes'][n] = [encode(phase_vocab, value) for value in
                    (b.get('available_phase', ''), v.get('available_phase', ''))]
                values = [number(b.get('contract_multiplier'))]
                for cost in ('stress', 'base'):
                    values.extend(number(b.get(cost+'_terminal_SELL_'+k)) for k in ('fill_price', 'fee_per_lot'))
                    values.extend(number(v.get(cost+'_SELL_'+k)) for k in ('fill_price', 'fee_per_lot'))
                data['quotes'][n] = values
                for cost in ('stress', 'base'):
                    data['y_'+cost][n] = paired_target(b, v, state['R0'], cost)
                for cutoff in CUTOFFS:
                    if ud < day_number(cutoff) and kd < day_number(cutoff) and fixed['t_day'] < day_number(cutoff):
                        for scope in SCOPES:
                            if scope != 'main' and g == int(scope[-1]): continue
                            c = cohort[cutoff+'|'+scope]; c['riskset_before_cutoff'] += 1
                            if not data['entry_supported'][n]: c['entry_quote_unknown'] += 1
                            for cost in ('stress', 'base'):
                                known = math.isfinite(data['y_'+cost][n]) and \
                                    fixed['baseline_day'] < day_number(cutoff) and fixed['voluntary_day'] < day_number(cutoff)
                                c[cost+':paired_known_before_cutoff' if known else cost+':paired_unknown_or_notyet'] += 1
                n += 1
            if summary_count % 100000 == 0:
                p = dict(action_rows=summary_count, riskset_rows=n, fits=0, cash=0)
                write_json(out/f'join_progress_{summary_count:07d}.json', p)
                print(json.dumps(p), flush=True)
    if summary_count != expected['actions'] or n != total or state_count != expected['held_close_states'] or \
            baseline_count != expected['entered_paths'] or any(c.current is not None for c in cursors.values()):
        raise ValueError('complete derived-table join conservation differs')
    compact_path = out/'compact_state_arrays.npz'
    np.savez_compressed(compact_path, **data)
    meta = dict(rows=n, total_actions=summary_count, held_states=state_count, baseline_rows=baseline_count,
        feature_names=FEATURES, raw_state_columns=RAW_STATE_FIELDS, quote_columns=QUOTE_COLUMNS,
        quote_code_columns=['entry_BUY', 'entry_SELL_estimate', 'stress_terminal_SELL',
            'stress_voluntary_SELL', 'base_terminal_SELL', 'base_voluntary_SELL'],
        phase_code_columns=['baseline', 'voluntary'], quote_vocab=quote_vocab,
        phase_vocab=phase_vocab, family_codes=families, missing_day=MISSING_DAY,
        day_encoding='datetime.date.toordinal; missing sentinel int32max, never an expiry date',
        row_order='source action sequence ascending then source t_index ascending; riskset rows only',
        weighted_variance_ddof=0, missing_column_mean=0, zero_or_missing_column_scale=1,
        array_shapes={key:list(value.shape) for key,value in data.items()},
        cohort_counts=cohort, identity_binding=binding(identity_path), compact_binding=binding(compact_path),
        universe_provenance='511/512 accepted full 98 products/95 families/six exchanges; natural child 97/94',
        row_independence=False, target_missingness_assumption='unknown; no MAR/IPCW claim')
    return data, meta, identity_map, selected_anchors


def save_npz(path, **arrays):
    np.savez_compressed(path, **arrays)
    return binding(path)


def actual(protocol_path, authorization_path, output):
    start = time.monotonic(); out = Path(output).resolve(); out.mkdir(parents=True, exist_ok=False)
    protocol_binding = binding(protocol_path)
    protocol = json.loads(Path(protocol_path).read_text())
    auth = json.loads(Path(authorization_path).read_text())
    source_bundle = [binding(Path(__file__)), binding(TOOLS/'test_stage515_continuation_fit.py')]
    if auth.get('protocol_sha256') != protocol_binding['sha256'] or auth.get('output_path') != str(out) or \
            auth.get('source_bundle') != source_bundle or auth.get('actual_stage') != 515:
        raise ValueError('root exact one-run authorization differs')
    write_json(out/'started.json', dict(status='started', timestamp=datetime.now(timezone.utc).isoformat(),
        protocol_binding=protocol_binding, source_bundle=source_bundle, automatic_retry=False))
    receipt = {}; artifacts = {}; fit_count = 0
    try:
        inputs=protocol['inputs']; domain=protocol['scope']
        expected=dict(actions=domain['actions'],decision_riskset_states=domain['riskset_states'],
            held_close_states=domain['unit_states'],entered_paths=689607)
        # 689607 is the accepted511 baseline-observation row count, not an
        # outcome-derived training selection. All actions remain in cohort counts.
        calendar_raw=read_bound(inputs['calendar'],receipt,'calendar')
        calendar_array=np.load(io.BytesIO(calendar_raw),allow_pickle=False)
        if calendar_array.dtype.kind in 'iu':
            calendar=[str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in calendar_array]
        else:
            calendar=calendar_array.astype('datetime64[D]').astype(str).tolist()
        if len(calendar)!=5587 or calendar!=sorted(set(calendar)):
            raise ValueError('original calendar domain differs')
        choices_by_scope={}; selected_sequences=set()
        for scope in SCOPES:
            frame=pd.read_csv(io.BytesIO(read_bound(inputs['choices_'+scope+'_A'],receipt,'choices_'+scope+'_A')),
                compression='gzip',dtype=str,keep_default_na=False)
            if set(frame['arm'])!={'VOLUNTARY_RESELECT'}:
                raise ValueError('A157 OWN voluntary-reselect identity differs')
            choices_by_scope[scope]=frame
            selected_sequences.update(int(x) for x in frame.loc[frame.selected.eq('1'),'chosen_action_sequence_index'])
        data, meta, identity_map, selected_anchors = extract_compact(inputs, out, receipt, expected,
            calendar, selected_sequences)
        if set(selected_anchors)!=selected_sequences:
            raise ValueError('selected A action absent from full source action domain')
        artifacts['selected_action_anchors']=write_json(out/'selected_action_anchors.json',selected_anchors)
        artifacts['compact_meta'] = write_json(out/'compact_meta.json', meta)
        artifacts['source_read_receipt'] = write_json(out/'source_read_receipt.json', receipt)
        artifacts['compact_state_arrays'] = meta['compact_binding']; artifacts['action_identity'] = meta['identity_binding']
        write_json(out/'joined_checkpoint.json', dict(status='complete_before_any_fit',
            compact_binding=meta['compact_binding'], fit=0, cash=0))
        models = {}; records = []
        for cutoff in CUTOFFS:
            for scope in SCOPES:
                key = scope+'|'+cutoff; mask = training_mask(data, day_number(cutoff), scope)
                indices = np.flatnonzero(mask)
                if len(indices) == 0: raise ValueError('empty predeclared training fold '+key)
                w = date_family_weights(data['t_day'][indices], data['family_code'][indices])
                scaler = fit_scaler(data['X'][indices], w)
                prefix = scope+'_'+cutoff[:4]
                train_binding = save_npz(out/(prefix+'_training_before_fit.npz'), row_indices=indices,
                    sequence=data['sequence'][indices], t_index=data['t_index'][indices], X=data['X'][indices],
                    y=data['y_stress'][indices], weights=w)
                calibration_binding = write_json(out/(prefix+'_calibration_before_fit.json'),
                    dict(cutoff=cutoff, scope=scope, scaler=scaler, training_binding=train_binding,
                         train_dates=len(np.unique(data['t_day'][indices])),
                         train_families=len(np.unique(data['family_code'][indices])),
                         no_dedup='all candidate states split family-day mass; not independent observations'))
                model = fit_head(data['X'][indices], data['y_stress'][indices], w, scaler)
                fit_count += 1; model.update(cutoff=cutoff, scope=scope, features=FEATURES,
                    training_binding=train_binding, calibration_binding=calibration_binding,
                    known_target_scope='stress entry-supported / mature-K / paired SELL strictly before cutoff')
                models[key] = model
                artifacts[prefix+'_model'] = write_json(out/(prefix+'_model.json'), model)
                records.append(dict(scope=scope, cutoff=cutoff, rows=len(indices),
                    dates=len(np.unique(data['t_day'][indices])), families=len(np.unique(data['family_code'][indices])),
                    effective_df=model['effective_df'], weighted_target_mean=model['weighted_target_mean']))
                print(json.dumps(dict(phase='head_completed', key=key, fits=fit_count, rows=len(indices))), flush=True)
        artifacts['portable_models'] = write_json(out/'portable_models.json', dict(schema='stage515_portable_models_v1',
            models=models, feature_function='stage515_continuation_fit.raw_features',
            deployment='head by current t_date, not entry u_date; missing X mean-imputed with flags',
            prediction_API='predict_state(models,t_date,state,scope=main)', fallback='hold on missing/nonfinite prediction',
            entry_policy_unchanged=True, stop_and_K_unchanged=True))
        scope_scores = {}; policy_summaries = []
        for scope in SCOPES:
            pred = np.full(len(data['X']), np.nan)
            for cutoff in CUTOFFS:
                mask = data['t_day'] >= day_number(cutoff)
                if cutoff == CUTOFFS[0]: mask &= data['t_day'] < day_number(CUTOFFS[1])
                # Predict in bounded chunks without re-reading any source table.
                indices = np.flatnonzero(mask)
                for j in range(0, len(indices), 100000):
                    ids = indices[j:j+100000]
                    pred[ids] = design_matrix(data['X'][ids], models[scope+'|'+cutoff])@np.asarray(models[scope+'|'+cutoff]['coef'])
            scope_scores[scope] = pred
            artifacts['scores_'+scope] = save_npz(out/('riskset_scores_'+scope+'.npz'),
                row_indices=np.arange(len(pred), dtype=np.int32), prediction=pred,
                current_t_day=data['t_day'], action_sequence=data['sequence'],
                held_family_prediction=(np.ones(len(pred), dtype=bool) if scope == 'main' else
                                        data['family_hash'] == int(scope[-1])))
            choices=choices_by_scope[scope]
            selected = choices.loc[choices.selected.eq('1')]
            selected_map = {int(row.chosen_action_sequence_index): row.chosen_action_id
                            for row in selected.itertuples()}
            starts = np.r_[0, np.flatnonzero(np.diff(data['sequence']))+1, len(pred)]
            first = {}
            for lo, hi in zip(starts[:-1], starts[1:]):
                seq = int(data['sequence'][lo])
                if seq not in selected_map: continue
                if identity_map[seq] != selected_map[seq]:
                    raise ValueError('selected A action identity differs from full unit state')
                if np.any(np.diff(data['t_index'][lo:hi]) <= 0): raise ValueError('path state order differs')
                rel = first_negative(pred[lo:hi])
                if rel is not None: first[seq] = int(lo+rel)
            rows = []
            for row in selected.itertuples():
                seq = int(row.chosen_action_sequence_index); index = first.get(seq)
                anchor=selected_anchors[seq]
                if anchor['action_id']!=row.chosen_action_id:
                    raise ValueError('selected terminal anchor identity differs')
                base_delta=unchanged_terminal_delta(anchor,'base') if index is None else -data['y_base'][index]
                stress_delta=unchanged_terminal_delta(anchor,'stress') if index is None else -data['y_stress'][index]
                result = dict(scope=scope, action_sequence=seq, action_id=row.chosen_action_id,
                    product_id=row.product_id, family_id=row.family_id, u_date=row.u_date,
                    request_state='hold_original_unit_policy' if index is None else 'first_negative_request',
                    request_t_index=None if index is None else int(data['t_index'][index]),
                    request_t_date=None if index is None else date.fromordinal(int(data['t_day'][index])).isoformat(),
                    prediction=None if index is None else float(pred[index]),
                    base_known_delta_R=base_delta, stress_known_delta_R=stress_delta,
                    baseline_participation_state=anchor['participation_state'],
                    baseline_terminal_state=anchor['terminal_state'],
                    baseline_available_at=anchor['available_at'],
                    base_delta_state='known_terminal_increment' if math.isfinite(base_delta) else 'terminal_increment_unknown',
                    stress_delta_state='known_terminal_increment' if math.isfinite(stress_delta) else 'terminal_increment_unknown',
                    observed_asof_same_path_zero=index is None,
                    hold_terminal_delta_exact_zero=index is None and math.isfinite(stress_delta))
                rows.append(result)
            frame = pd.DataFrame(rows)
            policy_path = out/('selected_unit_policy_'+scope+'.csv.gz')
            frame.to_csv(policy_path, index=False, compression='gzip', float_format='%.17g')
            artifacts['selected_unit_policy_'+scope] = binding(policy_path)
            change = frame.request_state.eq('first_negative_request')
            report = dict(scope=scope, selected_A_entries=len(frame), requested_exits=int(change.sum()),
                          held_all_else=int((~change).sum()), unit_not_cash=True)
            for cost in ('base', 'stress'):
                delta = pd.to_numeric(frame.loc[change, cost+'_known_delta_R'], errors='coerce')
                report[cost+'_known_changed_units'] = int(delta.notna().sum())
                report[cost+'_unknown_changed_units'] = int(delta.isna().sum())
                report[cost+'_known_changed_mean_delta_R'] = float(delta.mean()) if delta.notna().any() else None
                all_delta=pd.to_numeric(frame[cost+'_known_delta_R'],errors='coerce')
                per_u=frame.assign(_delta=all_delta).groupby('u_date',sort=True)._delta.mean()
                report[cost+'_known_u_equal_mean_increment_R']=float(per_u.mean()) if per_u.notna().any() else None
                report[cost+'_unknown_differential_selected_events']=int(all_delta.isna().sum())
                report[cost+'_conditional_known_mean_not_robust_claim']=True
            policy_summaries.append(report)
        artifacts['source_read_receipt_final'] = write_json(out/'source_read_receipt_final.json', receipt)
        summary = dict(schema='stage515_continuation_fit_summary_v1', status='completed',
            fits=fit_count, cash=0, SQL=0, native_reads=0, original129_reads=0,
            full_riskset_rows=len(data['X']), cohort_counts=meta['cohort_counts'],
            training_records=records, selected_unit_policies=policy_summaries,
            whole_policy_domain='inherited accepted511/512 98 historical products /95 families /six exchanges',
            limitations=['candidate unit paths overlap; not independent N', 'known target missingness may be informative',
                'selected unit delta is not capital return or paired account wealth',
                'features encode incomplete state; one-step baseline improvement need not improve repeated policy',
                'daily bar-model stop not a guaranteed maximum gap loss; no increased risk or formal deployment'],
            elapsed_seconds=time.monotonic()-start)
        artifacts['summary'] = write_json(out/'summary.json', summary)
        artifacts['handoff'] = write_json(out/'handoff.json',dict(schema='stage515_continuation_cash_handoff_v1',
            protocol_binding=protocol_binding,protocol_sha256=protocol_binding['sha256'],
            portable_models_binding=artifacts['portable_models'],held_diagnostic_binding=artifacts['summary'],
            feature_source=binding(__file__),candidate='C_CONTINUATION_FIXED_RIDGE',
            entry_choices_main=inputs['choices_main_A'],entry_arm='VOLUNTARY_RESELECT',
            completed_fits=fit_count,old_entry_retrained=0,account_replay_by_stage517=True,
            selected_unit_outcomes_are_not_cash=True))
        write_json(out/'manifest.json', dict(schema='stage515_continuation_fit_manifest_v1', status='completed',
            protocol_binding=protocol_binding, source_bundle=source_bundle, artifacts=artifacts,
            fits_completed=fit_count, cash=0, automatic_retry=False))
        write_json(out/'terminal.json', dict(status='completed', exit_code=0, fit=fit_count, cash=0,
            elapsed_seconds=time.monotonic()-start))
        print(json.dumps(safe(summary)), flush=True)
    except Exception as exc:
        write_json(out/'failure.json', dict(status='failed_no_auto_retry', error_type=type(exc).__name__,
            error=str(exc), fits_completed=fit_count, cash=0, elapsed_seconds=time.monotonic()-start,
            source_receipt=receipt, artifacts_completed=artifacts))
        raise


def main():
    p = argparse.ArgumentParser(); p.add_argument('--protocol', required=True)
    p.add_argument('--authorization', required=True); p.add_argument('--output', required=True)
    args = p.parse_args(); actual(args.protocol, args.authorization, args.output)


if __name__ == '__main__':
    main()
