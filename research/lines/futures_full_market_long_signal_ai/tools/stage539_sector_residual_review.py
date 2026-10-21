"""Independent compact-cache review for completed Stage538. Never fits a candidate or reads old large inputs."""
from __future__ import annotations

import argparse
from bisect import bisect_left
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

PROTOCOL_SHA = 'acd8fcbf9e738e266067179a6b1fe240e09775ade737d1616b73abf4a46cf592'
CONTRASTS = {'C_minus_A': ('C', 'A'), 'C_minus_B': ('C', 'B'), 'B_minus_A': ('B', 'A')}
ARMS = ('A', 'B', 'C')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def family_hash(value):
    return int.from_bytes(hashlib.sha256(str(value).encode()).digest(), 'big') % 2


def small(binding):
    data = Path(binding['path']).read_bytes()
    require(len(data) == binding['bytes'] and hashlib.sha256(data).hexdigest() == binding['sha256'],
            'small binding mismatch: '+binding['path'])
    return json.loads(data)


class CompressedRead:
    def __init__(self, binding):
        self.binding = binding
        self.stream = Path(binding['path']).open('rb')
        self.digest = hashlib.sha256()
        self.size = 0

    def read(self, amount=-1):
        value = self.stream.read(amount)
        self.digest.update(value)
        self.size += len(value)
        return value


def table(binding):
    stream = CompressedRead(binding)
    try:
        with gzip.GzipFile(fileobj=stream, mode='rb') as gz:
            result = pd.read_csv(gz, dtype=str, keep_default_na=False, float_precision='round_trip')
        require(stream.size == binding['bytes'] and stream.digest.hexdigest() == binding['sha256'],
                'new compact binding mismatch: '+binding['path'])
        return result
    finally:
        stream.stream.close()


def numeric(frame, names):
    for name in names:
        frame[name] = pd.to_numeric(frame[name], errors='coerce')
    return frame


def close(a, b, name, atol=1e-10, rtol=1e-10):
    aa, bb = np.asarray(a, float), np.asarray(b, float)
    require(aa.shape == bb.shape and np.allclose(aa, bb, atol=atol, rtol=rtol, equal_nan=True), name)
    valid = np.isfinite(aa) & np.isfinite(bb)
    return float(np.max(np.abs(aa[valid]-bb[valid]))) if valid.any() else 0.


def independent_weights(frame):
    """Rebuild family-u union and inverse family concurrency, without author helpers."""
    n = len(frame)
    membership = np.empty(n, np.int64)
    records = []
    for gid, ((family, day), indices) in enumerate(frame.groupby(['family_id', 'u_date'], sort=True).indices.items()):
        indices = np.asarray(indices, int)
        pairs = sorted(zip(frame.entry_index.to_numpy()[indices], frame.exit_index.to_numpy()[indices]))
        merged = []
        for left, right in pairs:
            require(np.isfinite(left) and np.isfinite(right) and int(left) == left and int(right) == right
                    and 0 <= left <= right, 'invalid compact mature interval')
            left, right = int(left), int(right)
            if merged and left <= merged[-1][1]+1:
                merged[-1][1] = max(right, merged[-1][1])
            else:
                merged.append([left, right])
        membership[indices] = gid
        records.append(dict(family=family, day=day, count=len(indices), intervals=merged,
                            length=sum(right-left+1 for left, right in merged)))
    families = {}
    for gid, item in enumerate(records):
        families.setdefault(item['family'], []).append(gid)
    uniqueness = np.empty(len(records), float)
    for group_ids in families.values():
        length = max(right for gid in group_ids for _, right in records[gid]['intervals'])+1
        changes = np.zeros(length+1, np.int64)
        for gid in group_ids:
            for left, right in records[gid]['intervals']:
                changes[left] += 1
                changes[right+1] -= 1
        counts = np.cumsum(changes[:-1])
        inv = np.divide(1., counts, out=np.zeros(length), where=counts > 0)
        prefix = np.r_[0., np.cumsum(inv)]
        for gid in group_ids:
            item = records[gid]
            uniqueness[gid] = sum(prefix[right+1]-prefix[left] for left, right in item['intervals'])/item['length']
    group_counts = np.array([r['count'] for r in records])
    lengths = np.array([r['length'] for r in records])
    base = uniqueness[membership]/group_counts[membership]
    day_codes, _ = pd.factorize(frame.u_date, sort=False)
    totals = np.bincount(day_codes, weights=base)[day_codes]
    divided = base/totals
    w = divided/divided.mean()
    return dict(group_id=membership, group_member_count=group_counts[membership],
                group_union_length=lengths[membership], group_uniqueness=uniqueness[membership],
                base_weight=base, day_weight_total=totals, sample_weight=w,
                normalized_weight=w/w.sum()), len(records)


def design_and_base(raw26, portable, scaler):
    means, scales = np.array(scaler['common']['mean']), np.array(scaler['common']['scale'])
    finite = np.isfinite(raw26)
    z = np.concatenate((np.where(finite, (raw26-means)/scales, 0.), (~finite).astype(float)), axis=1)
    require(z.shape[1] == 52 and np.isfinite(z).all(), 'independent52 design invalid')
    coefficients = np.array(portable['coef'], float)
    return z, np.dot(z, coefficients)+float(portable['intercept'])


def independent_head(family, residual, weights, mapping, sectors):
    wn = np.asarray(weights, float)/np.sum(weights)
    lookup = {sector: i for i, sector in enumerate(sectors)}
    ids = np.array([lookup.get(mapping.get(str(f)), -1) for f in family])
    mask = ids >= 0
    p = np.zeros(len(sectors))
    for j in range(len(sectors)):
        p[j] = wn[ids == j].sum()
    design = np.zeros((len(family), len(sectors)))
    design[mask] = np.eye(len(sectors))[ids[mask]]-p
    gram = (design.T*wn) @ design
    rhs = design.T @ (wn*np.asarray(residual))
    gamma = np.linalg.solve(np.eye(len(sectors))+gram, rhs)
    delta = (np.eye(len(sectors))-p) @ gamma
    delta[p == 0] = 0.
    eigenvalues = np.linalg.eigvalsh(gram)
    df = float(np.sum(eigenvalues/(1.+eigenvalues)))
    train_delta = np.zeros(len(family))
    train_delta[mask] = delta[ids[mask]]
    q = wn[mask].sum()
    require(eigenvalues.min() >= -1e-12 and df <= np.trace(gram)+1e-12
            and np.trace(gram) <= 1+1e-12, 'independent low-df bound violated')
    return dict(p=p, G=gram, b=rhs, gamma=gamma, delta=delta, effective_df=df,
                trace_G=float(np.trace(gram)), mapped_training_weight=float(q),
                normalized_weight_sum=float(wn.sum()), sumwZ=wn@design,
                sumwdelta=float(wn@train_delta), unknown_training_rows=int((~mask).sum()))


def true_offsets(families, head, mapping, sectors):
    values = {sector: head['delta'][i] if head['p'][i] > 0 else 0.
              for i, sector in enumerate(sectors)}
    return np.array([values.get(mapping.get(str(f)), 0.) for f in families])


def independent_choices(mothers, children, calendar, scope, arm):
    f = children.copy()
    f['candidate_score'] = f.score.to_numpy() + (f[arm+'_offset'].to_numpy() if arm != 'A' else 0.)
    next_dates = np.array(calendar, object)
    boundaries = {}
    for epoch in f.reference_epoch.unique():
        year, month = int(epoch[-6:-2]), int(epoch[-2:])
        year, month = (year-1, 12) if month == 1 else (year, month-1)
        target = f'{year:04d}-{month:02d}-01'
        boundaries[epoch] = -1 if target < calendar[0] else bisect_left(calendar, target)
    k = f.reference_epoch.map(boundaries).to_numpy()
    d = f.u_index.to_numpy(int)+1
    eligible = f.u_action_eligible.eq(1).to_numpy() & (f.candidate_score.to_numpy() > 0)
    calendar_gate = (d < len(calendar)) & (k >= 0) & (d < k)
    # k==len(calendar) also expresses accepted future-K D<target, because every observed D precedes target.
    def best(mask):
        return f.loc[mask].sort_values(['mother_sequence_index', 'candidate_score', 'reference_epoch', 'action_id'],
                                      ascending=[True, False, True, True], kind='stable').drop_duplicates('mother_sequence_index')
    def winners(frame):
        frame = frame.copy()
        frame['is_F'] = frame.product_id.str.endswith('_F').astype(int)
        return frame.sort_values(['u_index', 'family_id', 'is_F', 'product_id', 'reference_epoch', 'action_id'],
                                 kind='stable').drop_duplicates(['family_id', 'u_index'])
    old, proposed = best(eligible), best(eligible & calendar_gate)
    old_win, new_win = winners(old), winners(proposed)
    result = mothers.copy().set_index('sequence_index', drop=False)
    def mapped(frame, column, default=''):
        return result.sequence_index.map(frame.set_index('mother_sequence_index')[column]).fillna(default)
    result['proposed_action_id'] = mapped(proposed, 'action_id')
    result['proposed_epoch'] = mapped(proposed, 'reference_epoch')
    result['proposed_score'] = mapped(proposed, 'candidate_score', np.nan)
    result['chosen_action_id'] = mapped(new_win, 'action_id')
    result['chosen_action_sequence_index'] = mapped(new_win, 'sequence_index', -1).astype(int)
    result['chosen_epoch'] = mapped(new_win, 'reference_epoch')
    result['score'] = mapped(new_win, 'candidate_score', np.nan)
    result['old_chosen_action_id'] = mapped(old_win, 'action_id')
    result['old_chosen_epoch'] = mapped(old_win, 'reference_epoch')
    result['selected'] = result.chosen_action_id.ne('').astype(int)
    observed = set(f.mother_sequence_index)
    old_observed = set(old.mother_sequence_index)
    result['selection_state'] = np.select([result.selected.eq(1), result.proposed_action_id.ne(''),
                                          ~result.sequence_index.isin(observed), result.sequence_index.isin(old_observed)],
                                         ['selected', 'family_priority_suppressed', 'no_observed_children',
                                          'no_calendar_eligible_positive_action'], default='no_original_eligible_positive_action')
    result['arm'], result['scope'] = arm, scope
    return result.reset_index(drop=True)


def independent_diagnostics(choices, labels, end='2026-10-16'):
    labels = labels.set_index('action_id')
    source = choices.copy()
    selected = source.chosen_action_id.ne('')
    values = source.chosen_action_id.map(labels.net_R_stress).to_numpy(float)
    state = source.chosen_action_id.map(labels.label_state).fillna('')
    known_date = source.chosen_action_id.map(labels.label_known_date).fillna('')
    participation = source.chosen_action_id.map(labels.participation_state).fillna('')
    known = state.eq('closed_complete_bar_model') & known_date.ne('') & known_date.le(end) & np.isfinite(values)
    value = np.where(~selected | participation.eq('known_nonparticipation'), 0., np.where(known, values, np.nan))
    source['value_R'] = value
    source = source.sort_values('selected', ascending=False, kind='stable').drop_duplicates(['scope', 'arm', 'family_id', 'u_index'])
    reports, days_list, years_list = {}, [], []
    for scope, s in source.groupby('scope', sort=True):
        reports[scope] = {}
        arrays = {arm: s.loc[s.arm.eq(arm)].set_index(['family_id', 'u_index']).sort_index() for arm in ARMS}
        for contrast, (high, low) in CONTRASTS.items():
            a, c = arrays[low], arrays[high]
            require(a.index.equals(c.index) and a.u_date.equals(c.u_date), 'independent family-u domain mismatch')
            same = a.chosen_action_id.eq(c.chosen_action_id).to_numpy()
            finite = np.isfinite(a.value_R.to_numpy()) & np.isfinite(c.value_R.to_numpy())
            delta = c.value_R.to_numpy()-a.value_R.to_numpy()
            delta[same] = 0.
            delta[~same & ~finite] = np.nan
            unknown = ~same & ~finite
            daily = pd.DataFrame(dict(u_date=a.u_date.to_numpy(), delta_R=delta,
                                      known_family_u=np.isfinite(delta), unknown_family_u=unknown))
            daily = daily.groupby('u_date', sort=True).agg(delta_R=('delta_R', 'mean'),
                known_family_u=('known_family_u', 'sum'), unknown_family_u=('unknown_family_u', 'sum')).reset_index()
            daily['scope'], daily['contrast'] = scope, contrast
            days_list.append(daily)
            reports[scope][contrast] = dict(known_u_equal_mean_increment_R=float(daily.delta_R.mean()) if daily.delta_R.notna().any() else None,
                full_family_u=len(a), known_increment_family_u=int(np.isfinite(delta).sum()),
                known_source_days=int(daily.delta_R.notna().sum()),
                unknown_differential_selected_events=int(unknown.sum()),
                common_unresolved_same_action=int(np.sum(same & a.chosen_action_id.ne('').to_numpy() & ~finite)))
            for year, part in daily.groupby(daily.u_date.str[:4], sort=True):
                years_list.append(dict(scope=scope, contrast=contrast, year=year,
                    mean_delta_R=float(part.delta_R.mean()) if part.delta_R.notna().any() else np.nan,
                    source_days=len(part), known_source_days=int(part.delta_R.notna().sum()),
                    unknown_family_u=int(part.unknown_family_u.sum())))
    gate = True
    for contrast in ('C_minus_A', 'C_minus_B'):
        means = [reports[s][contrast]['known_u_equal_mean_increment_R'] for s in ('holdout_0', 'holdout_1')]
        gate &= all(v is not None and np.isfinite(v) and v >= 0 for v in means) and any(v > 0 for v in means if v is not None)
    return reports, pd.concat(days_list, ignore_index=True), pd.DataFrame(years_list), bool(gate)


def verify_frame(expected, actual, keys, strings, numbers):
    a = expected.sort_values(keys).reset_index(drop=True)
    b = actual.sort_values(keys).reset_index(drop=True)
    require(len(a) == len(b), 'row count differs '+str(keys))
    for column in keys+strings:
        require(np.array_equal(a[column].astype(str), b[column].astype(str)), 'field differs '+column)
    errors = {}
    for column in numbers:
        errors[column] = close(pd.to_numeric(a[column], errors='coerce'), pd.to_numeric(b[column], errors='coerce'), 'numeric differs '+column)
    return errors


def review(manifest_path, output):
    started = time.monotonic()
    manifest_bytes = Path(manifest_path).read_bytes()
    manifest = json.loads(manifest_bytes)
    require(manifest['status'] == 'completed' and manifest['actual_fit_calls_completed'] == 12, '538 not completed; no post-fit claim')
    require(manifest['protocol']['sha256'] == PROTOCOL_SHA, 'wrong protocol')
    protocol = small(manifest['protocol'])
    inventory = small(manifest['input_inventory'])
    terminal = small(manifest['terminal'])
    require(terminal['status'] == 'completed' and terminal['exit_code'] == 0 and terminal['completed'] == 12
            and terminal['base_refits'] == terminal['cash'] == terminal['SQL'] == 0, 'actual terminal not accepted')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for source in manifest['source_bundle']:
        content = Path(source['path']).read_bytes()
        require(len(content) == source['bytes'] and hashlib.sha256(content).hexdigest() == source['sha256'], 'author source drift')
    union_b = manifest['train_common_unique']
    raw_bytes = Path(union_b['path']).read_bytes()
    require(len(raw_bytes) == union_b['bytes'] and hashlib.sha256(raw_bytes).hexdigest() == union_b['sha256'], 'unique train NPZ drift')
    with np.load(io.BytesIO(raw_bytes), allow_pickle=False) as archive:
        sequence = archive['sequence_index'].copy()
        raw26 = archive['raw26'].copy()
        columns = archive['columns'].tolist()
    require(np.array_equal(sequence, np.unique(sequence)) and raw26.shape == (len(sequence), 26), 'bad unique train design')
    del raw_bytes
    sectors = protocol['taxonomy']['sector_order']
    mappings = dict(B=protocol['taxonomy']['placebo_family_mapping'], C=protocol['taxonomy']['true_family_mapping'])
    fold_records = small(manifest['fold_records'])
    independent_heads, training_reports = {}, []
    for old in inventory['folds']:
        scope, cutoff = old['scope'], old['cutoff']
        record = next(r for r in fold_records if r['scope'] == scope and r['cutoff'] == cutoff)
        train = numeric(table(record['train_compact']), ['sequence_index', 'entry_index', 'exit_index', 'u_index',
            'u_action_eligible', 'net_R_stress', 'Ahat', 'normalized_weight', 'sample_weight'])
        require(len(train) == old['training_rows'] and train.u_date.nunique() == old['training_dates']
                and train.family_id.nunique() == old['training_families'], 'mature training counts differ')
        require(train.u_action_eligible.eq(1).all() and train.label_state.eq('closed_complete_bar_model').all()
                and train.u_date.lt(cutoff).all() and train.label_known_date.ne('').all()
                and train.label_known_date.lt(cutoff).all() and np.isfinite(train.net_R_stress).all(), 'maturity differs')
        if scope != 'main':
            require(train.family_id.map(family_hash).ne(int(scope[-1])).all(), 'held family enters training')
        weights, groups = independent_weights(train)
        require(groups == old['training_groups'], 'union group count differs')
        weight_error = {name: close(value, pd.to_numeric(train[name], errors='raise'), 'weight differs '+name)
                        for name, value in weights.items()}
        positions = np.searchsorted(sequence, train.sequence_index.to_numpy(int))
        require((positions < len(sequence)).all() and np.array_equal(sequence[positions], train.sequence_index), 'train raw mapping missing')
        portable, scaler = small(old['portable_model']), small(old['scaler'])
        require(columns == scaler['common']['columns'] and len(portable['coef']) == 52
                and portable['parameters'] == {'alpha': 1., 'fit_intercept': True, 'solver': 'cholesky'}, 'base52 drift')
        design, base = design_and_base(raw26[positions], portable, scaler)
        base_error = close(base, train.Ahat.to_numpy(), 'base training score differs', atol=1e-9)
        for arm in ('B', 'C'):
            head = independent_head(train.family_id, train.net_R_stress.to_numpy()-base,
                                    weights['sample_weight'], mappings[arm], sectors)
            saved = small(manifest[f'head_{scope}_{cutoff}_{arm}'])
            errors = {k: close(v, saved[k], 'head differs '+k) for k, v in head.items()}
            require(saved['ridge_lambda'] == 1 and saved['new_global_intercept'] is False
                    and saved['zscore'] is False, 'head spec drift')
            independent_heads[(scope, cutoff, arm)] = head
            training_reports.append(dict(scope=scope, cutoff=cutoff, arm=arm, rows=len(train), groups=groups,
                max_weight_error=max(weight_error.values()), max_base_error=base_error,
                max_head_error=max(errors.values()), q=head['mapped_training_weight'],
                sumwZ=head['sumwZ'].tolist(), sumwdelta=head['sumwdelta'], effective_df=head['effective_df'],
                warm_groups=[sectors[i] for i, p in enumerate(head['p']) if p > 0]))
        del train, design, base
        print(json.dumps(dict(review_phase='training', scope=scope, cutoff=cutoff)), flush=True)
    del raw26, sequence
    forward = numeric(table(manifest['forward_base_compact']), ['sequence_index', 'mother_sequence_index',
        'u_index', 'u_action_eligible', 'score', 'net_R_stress', 'B_offset', 'C_offset'])
    require(len(forward) == 1933480 and not forward.duplicated(['scope', 'sequence_index']).any()
            and np.isfinite(forward.score).all(), 'full forward domain differs')
    offset_errors = []
    for (scope, cutoff), positions in forward.groupby(['scope', 'cutoff'], sort=False).indices.items():
        subset = forward.iloc[positions]
        old = next(r for r in inventory['folds'] if r['scope'] == scope and r['cutoff'] == cutoff)
        require(len(subset) == old['prediction_children'] and subset.u_date.ge(cutoff).all()
                and (cutoff != '2020-01-01' or subset.u_date.lt('2023-01-01').all()), 'forward cutoff differs')
        if scope != 'main':
            require(subset.family_id.map(family_hash).eq(int(scope[-1])).all(), 'held forward identity differs')
        for arm in ('B', 'C'):
            expected = true_offsets(subset.family_id, independent_heads[(scope, cutoff, arm)], mappings[arm], sectors)
            offset_errors.append(close(expected, subset[arm+'_offset'], 'forward offset differs'))
    mothers = numeric(table(manifest['mothers_forward']), ['sequence_index', 'u_index'])
    require(len(mothers) == 161014 and mothers.event_id.is_unique, 'full mother domain differs')
    parent_lookup = mothers.set_index('sequence_index')
    for child_key, parent_key in [('mother_event_id', 'event_id'), ('product_id', 'product_id'),
                                  ('family_id', 'family_id'), ('u_date', 'u_date'),
                                  ('u_index', 'u_index'), ('anchor_epoch', 'reference_epoch')]:
        linked_identity = forward.mother_sequence_index.map(parent_lookup[parent_key])
        require(np.array_equal(linked_identity.to_numpy(), forward[child_key].to_numpy()),
                'compact child/parent identity differs '+child_key)
    main_identity = forward.loc[forward.scope.eq('main')].sort_values('sequence_index')
    held_identity = forward.loc[forward.scope.ne('main')].sort_values('sequence_index')
    require(len(main_identity) == len(held_identity) == 966740, 'main/held union coverage differs')
    for column in ['sequence_index', 'action_id', 'mother_sequence_index', 'family_id', 'product_id', 'u_date', 'cutoff']:
        require(np.array_equal(main_identity[column].to_numpy(), held_identity[column].to_numpy()),
                'main/held child coverage differs '+column)
    del main_identity, held_identity, parent_lookup
    calendar = small(manifest['calendar'])
    require(len(calendar) == 5587 and calendar == sorted(set(calendar)), 'calendar invalid')
    saved_choices = pd.concat([table(manifest['choices_main']), table(manifest['choices_holdout'])], ignore_index=True)
    numeric(saved_choices, ['sequence_index', 'u_index', 'selected'])
    reconstructed = []
    for scope in ('main', 'holdout_0', 'holdout_1'):
        sub = forward.loc[forward.scope.eq(scope)]
        parents = mothers if scope == 'main' else mothers.loc[mothers.family_id.map(family_hash).eq(int(scope[-1]))]
        for arm in ARMS:
            reconstructed.append(independent_choices(parents, sub, calendar, scope, arm))
        print(json.dumps(dict(review_phase='choices', scope=scope)), flush=True)
    choices = pd.concat(reconstructed, ignore_index=True)
    choice_errors = verify_frame(choices, saved_choices, ['scope', 'arm', 'event_id'],
        ['proposed_action_id', 'proposed_epoch', 'chosen_action_id', 'chosen_epoch', 'selection_state',
         'old_chosen_action_id', 'old_chosen_epoch'], ['proposed_score', 'score', 'chosen_action_sequence_index', 'selected'])
    # Main and held label copies must agree; each forward action has precisely both policy scopes.
    label_fields = ['action_id', 'label_state', 'participation_state', 'net_R_stress', 'label_known_date']
    labels = forward[label_fields].drop_duplicates()
    require(labels.action_id.is_unique and len(labels)*2 == len(forward), 'forward labels/coverage disagree')
    reports, days, years, gate = independent_diagnostics(choices, labels)
    saved_report = small(manifest['held_diagnostic'])
    diagnostic_errors = []
    for scope, contrasts in reports.items():
        for contrast, item in contrasts.items():
            expected = saved_report['groups'][scope][contrast]
            for key, value in item.items():
                if value is None:
                    require(expected[key] is None, 'all unknown mean differs')
                else:
                    diagnostic_errors.append(close(value, expected[key], 'diagnostic differs '+key))
    daily_errors = verify_frame(days, table(manifest['held_daily']), ['scope', 'contrast', 'u_date'], [],
                                ['delta_R', 'known_family_u', 'unknown_family_u'])
    annual_errors = verify_frame(years, table(manifest['held_annual']), ['scope', 'contrast', 'year'], [],
                                 ['mean_delta_R', 'source_days', 'known_source_days', 'unknown_family_u'])
    require(gate == saved_report['nominal_cash_prerequisite'] == manifest['nominal_cash_prerequisite'], 'cash triage gate differs')
    reviewer_source = Path(__file__).read_bytes()
    result = dict(schema='stage539_sector_residual_independent_review_v1', status='completed',
        reviewed_at=datetime.now(timezone.utc).isoformat(), C=0, I=0, M=0,
        review_source=dict(path=str(Path(__file__).resolve()), bytes=len(reviewer_source),
                           sha256=hashlib.sha256(reviewer_source).hexdigest()),
        completed_after_actual=True, author_manifest=dict(path=str(Path(manifest_path).resolve()), bytes=len(manifest_bytes),
        sha256=hashlib.sha256(manifest_bytes).hexdigest()), protocol_sha256=PROTOCOL_SHA,
        new_candidate_fits=0, cash_replays=0, SQL=0, downloads=0, old_large_table_reads=0,
        author_actual_fits=12, training=training_reports, forward_rows=len(forward), choice_rows=len(choices),
        max_forward_offset_error=max(offset_errors), choice_errors=choice_errors,
        max_diagnostic_error=max(diagnostic_errors), daily_errors=daily_errors, annual_errors=annual_errors,
        diagnostic_groups=reports, nominal_cash_prerequisite=gate, unconditional_full_policy_supported=False,
        economic_qualification=False, production_qualified=False, elapsed_seconds=time.monotonic()-started,
        confidence='Exact compact arithmetic/identity/maturity/weights and chosen-policy calculations accepted; repeated-history, one placebo, unknown outcomes and original execution assumptions remain.')
    path = output/'review.json'
    with path.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(status='completed', C=0, I=0, M=0, nominal_cash_prerequisite=gate,
                          output=str(path), elapsed_seconds=result['elapsed_seconds'])), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    review(args.manifest, args.output)


if __name__ == '__main__':
    main()
