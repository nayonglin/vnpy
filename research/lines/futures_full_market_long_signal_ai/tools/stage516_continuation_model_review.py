"""Independent fixed-continuation math, initially synthetic/static only.

This module does not import the author model code and performs no I/O on import.
The actual compact-review adapter is added only after its schema is frozen.
"""
import numpy as np


def review_features(raw, t_day, source_target_day, k_target_day):
    a = np.asarray(raw, dtype=float)
    x = np.full((len(a), 6), np.nan)
    r = a[:, 6]
    valid = np.isfinite(r) & (r > 0)
    numerators = (a[:, 0]-a[:, 1], a[:, 0]-a[:, 2],
                  a[:, 3]-a[:, 4], a[:, 5])
    for j, numerator in enumerate(numerators):
        ok = valid & np.isfinite(numerator)
        x[ok, j] = numerator[ok]/r[ok]
    x[:, 4] = a[:, 7]
    t = np.asarray(t_day, dtype=float)
    s = np.asarray(source_target_day, dtype=float)
    k = np.asarray(k_target_day, dtype=float)
    ok = np.isfinite(t) & np.isfinite(s) & np.isfinite(k)
    x[ok, 5] = np.minimum(s[ok], k[ok])-t[ok]
    x[~np.isfinite(x)] = np.nan
    return x


def review_targets(quoted, fixed_risk, observed):
    q = np.asarray(quoted, dtype=float)
    r = np.asarray(fixed_risk, dtype=float)
    observed = np.asarray(observed, dtype=bool)
    out = np.full((len(q), 2), np.nan)
    for j, cols in enumerate(((1, 2, 3, 4), (5, 6, 7, 8))):
        bf, bc, vf, vc = (q[:, z] for z in cols)
        ok = (observed[:, 2*j] & observed[:, 2*j+1] &
              np.isfinite(q[:, 0]) & (q[:, 0] > 0) &
              np.isfinite(r) & (r > 0) &
              np.isfinite(q[:, cols]).all(axis=1))
        out[ok, j] = ((bf[ok]-vf[ok])*q[ok, 0]-bc[ok]+vc[ok])/(r[ok]*q[ok, 0])
    return out


def review_mask(a, cutoff, excluded_hash=None):
    m = np.asarray(a['entry_supported'], bool) & np.isfinite(a['y_stress'])
    for key in ('u_day', 't_day', 'k_day', 'baseline_day', 'voluntary_day'):
        day = np.asarray(a[key])
        m &= np.isfinite(day) & (day >= 0) & (day < cutoff)
    if excluded_hash is not None:
        m &= np.asarray(a['family_hash']) != int(excluded_hash)
    return m


def review_weights(day, family):
    day = np.asarray(day)
    family = np.asarray(family)
    if len(day) == 0:
        raise ValueError('empty training fold')
    pairs, inv, count = np.unique(np.column_stack((day, family)), axis=0,
                                  return_inverse=True, return_counts=True)
    dates, date_inv, families_per_date = np.unique(pairs[:, 0], return_inverse=True,
                                                  return_counts=True)
    return 1./(len(dates)*families_per_date[date_inv[inv]]*count[inv])


def review_scaler(x, w):
    x = np.asarray(x, float)
    w = np.asarray(w, float)
    mu = np.zeros(x.shape[1])
    sd = np.ones(x.shape[1])
    for j in range(x.shape[1]):
        finite = np.isfinite(x[:, j])
        mass = w[finite].sum()
        if mass > 0:
            mu[j] = np.dot(w[finite], x[finite, j])/mass
            variance = np.dot(w[finite], (x[finite, j]-mu[j])**2)/mass
            if variance > 0:
                sd[j] = np.sqrt(variance)
    return mu, sd


def review_design(x, mu, sd):
    x = np.asarray(x, float)
    observed = np.isfinite(x)
    numeric = (np.where(observed, x, mu)-mu)/sd
    return np.column_stack((np.ones(len(x)), numeric, (~observed).astype(float)))


def review_solve(design, y, w):
    d = np.asarray(design, float)
    gram = d.T@(w[:, None]*d)
    rhs = d.T@(w*y)
    penalty = np.eye(d.shape[1])
    penalty[0, 0] = 0.
    lhs = gram+penalty
    coef = np.linalg.solve(lhs, rhs)
    effective_df = np.trace(np.linalg.solve(lhs, gram))
    return coef, gram, rhs, effective_df


def review_predictions(x, day, heads):
    from datetime import date
    out = np.full(len(x), np.nan)
    bounds = [date.fromisoformat(s).toordinal() for s in ('2020-01-01', '2023-01-01')]
    for j, name in enumerate(('2020-01-01', '2023-01-01')):
        keep = np.asarray(day) >= bounds[j]
        if j == 0:
            keep &= np.asarray(day) < bounds[1]
        ids = np.flatnonzero(keep)
        m = heads[name]
        for chunk in range(0, len(ids), 100000):
            part = ids[chunk:chunk+100000]
            out[part] = review_design(x[part], m['mean'], m['scale'])@m['coef']
    return out


def review_first_requests(sequence, prediction):
    ids = np.flatnonzero(np.isfinite(prediction) & (prediction < 0))
    if len(ids) == 0:
        return {}
    seq, first = np.unique(np.asarray(sequence)[ids], return_index=True)
    return {int(s): int(ids[j]) for s, j in zip(seq, first)}


def _binding(path):
    import hashlib
    from pathlib import Path
    p = Path(path).resolve()
    raw = p.read_bytes()
    return dict(path=str(p), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def _clean(obj):
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _clean(obj.tolist())
    if isinstance(obj, (np.integer, np.bool_)):
        return obj.item()
    if isinstance(obj, (float, np.floating)):
        return float(obj) if np.isfinite(obj) else None
    return obj


def _write_json(path, obj):
    import json
    with path.open('x') as stream:
        json.dump(_clean(obj), stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def _equal_numbers(actual, expected, name, atol=1e-10, rtol=1e-10):
    a = np.asarray(actual, float)
    b = np.asarray(expected, float)
    if a.shape != b.shape or not np.array_equal(np.isnan(a), np.isnan(b)):
        raise AssertionError(name+' shape/missing pattern differs')
    np.testing.assert_allclose(a, b, atol=atol, rtol=rtol, equal_nan=True, err_msg=name)
    finite = np.isfinite(a) & np.isfinite(b)
    return float(np.max(np.abs(a[finite]-b[finite]))) if finite.any() else 0.


def actual_review(protocol_path, author_manifest_path, authorization_path, output_path):
    """One new-compact review; never imports515 or reads511/native/old choices."""
    import csv
    from datetime import date, datetime, timezone
    import gzip
    import hashlib
    import io
    import json
    from pathlib import Path
    import time

    start = time.monotonic()
    out = Path(output_path).resolve()
    code = Path(__file__).resolve()
    source_bundle = [_binding(code), _binding(code.with_name('test_stage516_continuation_model_review.py'))]
    pb, mb = _binding(protocol_path), _binding(author_manifest_path)
    auth = json.loads(Path(authorization_path).read_text())
    if (auth.get('actual_stage') != 516 or auth.get('protocol_sha256') != pb['sha256'] or
            auth.get('author_manifest_sha256') != mb['sha256'] or
            auth.get('source_bundle') != source_bundle or auth.get('output_path') != str(out)):
        raise ValueError('root exact516 one-run authorization differs')
    out.mkdir(parents=True, exist_ok=False)
    _write_json(out/'started.json', dict(status='started', protocol_binding=pb,
        author_manifest_binding=mb, source_bundle=source_bundle,
        timestamp=datetime.now(timezone.utc).isoformat(), automatic_retry=False))
    reads = {}

    def read_bound(b, role):
        p = Path(b['path'])
        before = p.stat()
        raw = p.read_bytes()
        after = p.stat()
        if (len(raw) != b['bytes'] or hashlib.sha256(raw).hexdigest() != b['sha256'] or
                (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns)):
            raise ValueError('bound source changed '+role)
        if role in reads:
            raise ValueError('duplicate physical read '+role)
        reads[role] = dict(binding=b, physical_reads=1, bytes_read=len(raw))
        return raw

    def read_json(b, role):
        return json.loads(read_bound(b, role))

    def load_npz(b, role):
        raw = read_bound(b, role)
        with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
            return {name: archive[name] for name in archive.files}

    try:
        p = read_json(pb, 'protocol')
        manifest = read_json(mb, 'author_manifest')
        if (manifest.get('status') != 'completed' or manifest.get('fits_completed') != 6 or
                manifest.get('protocol_binding') != pb):
            raise AssertionError('author manifest is not a completed six-head514 run')
        artifacts = manifest['artifacts']
        meta = read_json(artifacts['compact_meta'], 'compact_meta')
        portable = read_json(artifacts['portable_models'], 'portable_models')
        summary = read_json(artifacts['summary'], 'author_summary')
        handoff = read_json(artifacts['handoff'], 'author_handoff')
        if (handoff.get('protocol_binding') != pb or handoff.get('protocol_sha256') != pb['sha256'] or
                handoff.get('portable_models_binding') != artifacts['portable_models'] or
                handoff.get('held_diagnostic_binding') != artifacts['summary']):
            raise AssertionError('portable/handoff closure differs')
        if meta['compact_binding'] != artifacts['compact_state_arrays']:
            raise AssertionError('compact meta/manifest binding differs')
        a = load_npz(artifacts['compact_state_arrays'], 'new_compact')
        n = p['scope']['riskset_states']
        if meta['rows'] != n or any(len(v) != n for v in a.values()):
            raise AssertionError('new compact rows differ')
        if any(list(a[k].shape) != shape for k, shape in meta['array_shapes'].items()):
            raise AssertionError('compact array shape differs')
        if np.any(np.diff(a['sequence']) < 0):
            raise AssertionError('compact action order differs')
        same = np.diff(a['sequence']) == 0
        if (np.diff(a['t_index'])[same] <= 0).any() or (a['u_day'] >= a['t_day']).any():
            raise AssertionError('causal state order differs')
        missing_day = meta['missing_day']
        decoded = {}
        for field in ('t_day', 'source_target_day', 'k_target_day'):
            decoded[field] = a[field].astype(float)
            decoded[field][a[field] == missing_day] = np.nan
        x = review_features(a['raw_state'], decoded['t_day'],
                            decoded['source_target_day'], decoded['k_target_day'])
        maximum_errors = {'features': _equal_numbers(a['X'], x, 'all riskset causal features')}
        known_code = meta['quote_vocab']['observed_research_quote']
        entry = np.all(a['quote_codes'][:, :2] == known_code, axis=1)
        if not np.array_equal(entry, a['entry_supported']):
            raise AssertionError('stress entry-support codes differ')
        observed = a['quote_codes'][:, 2:] == known_code
        targets = review_targets(a['quotes'], a['raw_state'][:, 6], observed)
        maximum_errors['stress_target'] = _equal_numbers(a['y_stress'], targets[:, 0], 'stress SELL target')
        maximum_errors['base_target'] = _equal_numbers(a['y_base'], targets[:, 1], 'base SELL target')
        # Entry/terminal quote components remain label-only. Known quote
        # events must have an observed event phase; no phase is ever an X.
        phases = {int(v): k for k, v in meta['phase_vocab'].items()}
        for j, field in enumerate(('baseline_day', 'voluntary_day')):
            known_event = np.isfinite(a['y_stress'])
            if (a[field][known_event] == missing_day).any():
                raise AssertionError('finite label lacks availability '+field)
            legal_phase = ('open', 'intraday') if j == 0 else ('open',)
            if any(phases[int(z)] not in legal_phase for z in np.unique(a['phase_codes'][known_event, j])):
                raise AssertionError('finite label event phase differs '+field)
        models = portable['models']
        cutoffs = ('2020-01-01', '2023-01-01')
        scopes = ('main', 'holdout_0', 'holdout_1')
        reconstructed = {s: {} for s in scopes}
        model_reviews = {}
        for cutoff in cutoffs:
            day = date.fromisoformat(cutoff).toordinal()
            for scope in scopes:
                key = scope+'|'+cutoff
                held = None if scope == 'main' else int(scope[-1])
                keep = review_mask(a, day, held)
                ids = np.flatnonzero(keep)
                if len(ids) == 0:
                    raise AssertionError('empty fixed training head '+key)
                w = review_weights(a['t_day'][ids], a['family_code'][ids])
                mu, sd = review_scaler(x[ids], w)
                design = review_design(x[ids], mu, sd)
                coef, gram, rhs, effective_df = review_solve(design, targets[ids, 0], w)
                model = models[key]
                errors = dict(mean=_equal_numbers(model['mean'], mu, key+' mean'),
                    scale=_equal_numbers(model['scale'], sd, key+' scale'),
                    coef=_equal_numbers(model['coef'], coef, key+' coef'),
                    gram=_equal_numbers(model['weighted_gram'], gram, key+' gram'),
                    rhs=_equal_numbers(model['normal_rhs'], rhs, key+' rhs'),
                    df=_equal_numbers(model['effective_df'], effective_df, key+' df'))
                lhs = gram+np.diag(np.r_[0., np.ones(12)])
                errors['lhs'] = _equal_numbers(model['normal_lhs'], lhs, key+' lhs')
                errors['weighted_target_mean'] = _equal_numbers(model['weighted_target_mean'], w@targets[ids, 0], key+' meanY')
                if model['training_rows'] != len(ids) or model['alpha'] != 1. or model['intercept_penalized'] is not False:
                    raise AssertionError('fixed model design differs '+key)
                _equal_numbers(model['weight_sum'], w.sum(), key+' weight sum', atol=1e-12, rtol=0)
                if held is not None and (a['family_hash'][ids] == held).any():
                    raise AssertionError('held family entered training '+key)
                reconstructed[scope][cutoff] = dict(mean=mu, scale=sd, coef=coef)
                model_reviews[key] = dict(rows=len(ids), dates=len(np.unique(a['t_day'][ids])),
                    families=len(np.unique(a['family_code'][ids])), weight_sum=float(w.sum()),
                    effective_df=float(effective_df), numerical_errors=errors,
                    max_u_ordinal=int(a['u_day'][ids].max()), max_t_ordinal=int(a['t_day'][ids].max()),
                    max_K_ordinal=int(a['k_day'][ids].max()),
                    max_baseline_available_ordinal=int(a['baseline_day'][ids].max()),
                    max_requested_available_ordinal=int(a['voluntary_day'][ids].max()),
                    held_family_excluded=True)
                _write_json(out/(scope+'_'+cutoff[:4]+'_checked.json'), model_reviews[key])
                print(json.dumps(dict(phase='model_reconstructed', head=key, rows=len(ids))), flush=True)
        # Identity is one compact action map, not a second old-source scan.
        identity_raw = read_bound(artifacts['action_identity'], 'new_action_identity')
        identity = {}
        with gzip.GzipFile(fileobj=io.BytesIO(identity_raw)) as stream:
            for row in csv.DictReader(io.TextIOWrapper(stream)):
                seq = int(row['sequence_index'])
                family = row['family_id']
                if int(hashlib.sha256(family.encode()).hexdigest(), 16) % 2 != int(row['family_hash_group']):
                    raise AssertionError('compact action held-hash differs')
                if seq in identity:
                    raise AssertionError('duplicate compact action identity')
                identity[seq] = row
        unique_seq, first_idx = np.unique(a['sequence'], return_index=True)
        if set(identity) != set(map(int, unique_seq)):
            raise AssertionError('compact action identity domain differs')
        family_by_code = {int(v): k for k, v in meta['family_codes'].items()}
        for seq, first in zip(unique_seq, first_idx):
            row = identity[int(seq)]
            if (family_by_code[int(a['family_code'][first])] != row['family_id'] or
                    int(a['family_hash'][first]) != int(row['family_hash_group']) or
                    int(a['u_day'][first]) != date.fromisoformat(row['u_date']).toordinal()):
                raise AssertionError('compact identity/row mapping differs')
        selected_review = {}
        anchors = read_json(artifacts['selected_action_anchors'], 'new_selected_action_anchors')
        for scope in scopes:
            prediction = review_predictions(x, a['t_day'], reconstructed[scope])
            scored = load_npz(artifacts['scores_'+scope], 'new_scores_'+scope)
            maximum_errors['scores_'+scope] = _equal_numbers(scored['prediction'], prediction, scope+' scores')
            for field, truth in (('row_indices', np.arange(n)), ('current_t_day', a['t_day']),
                                 ('action_sequence', a['sequence'])):
                if not np.array_equal(scored[field], truth):
                    raise AssertionError('saved score alignment differs '+scope+' '+field)
            held = np.ones(n, bool) if scope == 'main' else a['family_hash'] == int(scope[-1])
            if not np.array_equal(scored['held_family_prediction'], held):
                raise AssertionError('held prediction flag differs '+scope)
            selected_review[scope] = review_selected_units(scope, prediction, a, targets, identity,
                anchors, artifacts, summary, read_bound)
            print(json.dumps(dict(phase='selected_unit_checked', scope=scope,
                                  counts=selected_review[scope])), flush=True)
        author_reads = read_json(artifacts['source_read_receipt_final'], 'author_source_receipt')
        allowed_roles = {'calendar', 'action_path_summary', 'unit_states',
            'baseline_terminal_observations', 'voluntary_exit_observations',
            'choices_main_A', 'choices_holdout_0_A', 'choices_holdout_1_A'}
        if set(author_reads) != allowed_roles or any(
                v['physical_reads'] != 1 or v['binding'] != p['inputs'][k]
                for k, v in author_reads.items()):
            raise AssertionError('author declared single-source read scope differs')
        result = dict(schema='stage516_fixed_continuation_model_review_v1', status='completed',
            completed=True, material_disagreements=0, material_issues=[],
            protocol_binding=pb, author_manifest_binding=mb,
            portable_models_binding=artifacts['portable_models'], source_bundle=source_bundle,
            review_scope='new compact causal X/paired SELL/clock/6model/3score/3selected-unit diagnostics; old full source not recertified',
            source_read_receipt=reads, maximum_numerical_errors=maximum_errors,
            counts=dict(riskset_rows=n, compact_actions=len(identity), models=6, score_scopes=3),
            model_reviews=model_reviews, selected_unit_reviews=selected_review,
            inherited_provenance='511/512 unit/native/economics mappings and full98/95 domain; original Achoice selection source accepted separately',
            limitations=['known label selection may be informative', 'overlapping states not independent N',
                         'held and history already disclosed', 'unit outcomes not account wealth or reinvestment value',
                         'finite bar-model/PIT/source qualifications inherited'],
            cash=0, new_fit=0, coefficient_reconstructions=6, old511_table_reads=0,
            old_native_reads=0, original129_reads=0, SQL=0, market_API=0,
            overfit_risk=True, increased_betting_qualified=False, goal_complete=False,
            elapsed_seconds=time.monotonic()-start)
        _write_json(out/'review_receipt.json', result)
        _write_json(out/'terminal.json', dict(status='completed', exit_code=0,
            material_disagreements=0, elapsed_seconds=time.monotonic()-start))
        print(json.dumps(_clean(result)), flush=True)
    except Exception as exc:
        _write_json(out/'failure.json', dict(status='failed_no_auto_retry', error_type=type(exc).__name__,
            error=str(exc), source_read_receipt=reads, elapsed_seconds=time.monotonic()-start))
        raise


def review_selected_units(scope, prediction, a, targets, identity, anchors, artifacts, summary, read_bound):
    import csv
    from datetime import date
    import gzip
    import hashlib
    import io
    from collections import defaultdict
    raw = read_bound(artifacts['selected_unit_policy_'+scope], 'new_selected_units_'+scope)
    rows = list(csv.DictReader(io.StringIO(gzip.decompress(raw).decode())))
    requests = review_first_requests(a['sequence'], prediction)
    if len(rows) != len({int(row['action_sequence']) for row in rows}):
        raise AssertionError('duplicate selected action '+scope)
    known_cancel = {'u_ineligible', 'D_not_before_K', 'lifecycle_entry_rejected',
                    'stale_breakout_cancel_at_open', 'invalid_initial_risk_cancel'}
    deltas = {'stress': [], 'base': []}
    requested = []
    def number(value):
        return float(value) if value not in ('', None) else float('nan')
    def boolean(value):
        if value not in ('True', 'False'):
            raise AssertionError('nonboolean saved unit flag')
        return value == 'True'
    for row in rows:
        seq = int(row['action_sequence'])
        anchor = anchors[str(seq)]
        if (row['scope'] != scope or anchor['action_id'] != row['action_id'] or
                row['baseline_participation_state'] != anchor['participation_state'] or
                row['baseline_terminal_state'] != anchor['terminal_state'] or
                row['baseline_available_at'] != anchor['available_at']):
            raise AssertionError('selected terminal anchor differs '+scope)
        if scope != 'main' and int(hashlib.sha256(row['family_id'].encode()).hexdigest(), 16) % 2 != int(scope[-1]):
            raise AssertionError('selected held family is not held '+scope)
        if seq in identity and any(row[field] != identity[seq][field]
                for field in ('action_id', 'family_id', 'product_id', 'u_date')):
            raise AssertionError('selected/compact action identity differs '+scope)
        j = requests.get(seq)
        request = j is not None
        requested.append(request)
        if row['request_state'] != ('first_negative_request' if request else 'hold_original_unit_policy'):
            raise AssertionError('first-negative policy differs '+scope)
        if boolean(row['observed_asof_same_path_zero']) != (not request):
            raise AssertionError('asof identical path flag differs '+scope)
        if request:
            if int(row['request_t_index']) != int(a['t_index'][j]) or row['request_t_date'] != date.fromordinal(int(a['t_day'][j])).isoformat():
                raise AssertionError('first request timing differs '+scope)
            _equal_numbers(number(row['prediction']), prediction[j], scope+' selected prediction')
        elif row['request_t_index'] or row['request_t_date'] or row['prediction']:
            raise AssertionError('held unit has a synthetic request '+scope)
        for col, cost in enumerate(('stress', 'base')):
            if request:
                expected = -targets[j, col]
            else:
                closed = (anchor['participation_state'] == 'entered' and
                          anchor['terminal_state'] == 'closed_complete_bar_model' and
                          anchor[cost+'_terminal_SELL_quote_state'] == 'observed_research_quote' and
                          bool(anchor['available_at']) and anchor['available_at'] <= '2026-10-16')
                expected = 0. if closed or anchor['participation_state'] in known_cancel else np.nan
            value = number(row[cost+'_known_delta_R'])
            _equal_numbers(value, expected, scope+' '+cost+' unit delta')
            state = 'known_terminal_increment' if np.isfinite(expected) else 'terminal_increment_unknown'
            if row[cost+'_delta_state'] != state:
                raise AssertionError('known/unknown terminal state differs '+scope)
            deltas[cost].append(expected)
        if boolean(row['hold_terminal_delta_exact_zero']) != (not request and np.isfinite(deltas['stress'][-1])):
            raise AssertionError('hold terminal exact zero flag differs '+scope)
    reported = {r['scope']: r for r in summary['selected_unit_policies']}[scope]
    report = dict(scope=scope, selected_A_entries=len(rows), requested_exits=sum(requested),
                  held_all_else=len(rows)-sum(requested), unit_not_cash=True)
    if any(reported[key] != report[key] for key in ('selected_A_entries', 'requested_exits', 'held_all_else')):
        raise AssertionError('selected policy counts differ '+scope)
    for cost in ('stress', 'base'):
        delta = np.asarray(deltas[cost])
        change = np.asarray(requested, bool)
        finite = np.isfinite(delta)
        by_u = defaultdict(list)
        for row, value in zip(rows, delta):
            if np.isfinite(value):
                by_u[row['u_date']].append(float(value))
        known_changed = int((change & finite).sum())
        unknown_changed = int((change & ~finite).sum())
        changed_mean = float(delta[change & finite].mean()) if known_changed else np.nan
        u_mean = float(np.mean([np.mean(v) for v in by_u.values()])) if by_u else np.nan
        if (reported[cost+'_known_changed_units'] != known_changed or
                reported[cost+'_unknown_changed_units'] != unknown_changed or
                reported[cost+'_unknown_differential_selected_events'] != int((~finite).sum())):
            raise AssertionError('known/unknown selected counts differ '+scope+' '+cost)
        _equal_numbers(reported[cost+'_known_changed_mean_delta_R'], changed_mean,
                       scope+' '+cost+' changed mean')
        _equal_numbers(reported[cost+'_known_u_equal_mean_increment_R'], u_mean,
                       scope+' '+cost+' known date mean')
        report.update({cost+'_known_changed_units': known_changed,
                       cost+'_unknown_changed_units': unknown_changed,
                       cost+'_unknown_differential_selected_events': int((~finite).sum()),
                       cost+'_known_changed_mean_delta_R': changed_mean,
                       cost+'_known_u_equal_mean_increment_R': u_mean})
    return report


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--protocol', required=True)
    p.add_argument('--author-manifest', required=True)
    p.add_argument('--authorization', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    actual_review(args.protocol, args.author_manifest, args.authorization, args.output)


if __name__ == '__main__':
    main()
