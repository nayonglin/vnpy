"""Frozen536 residual-sector experiment. Root alone launches actual once; no base fit/SQL."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import time
import traceback
import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
PROTOCOL_SHA = 'acd8fcbf9e738e266067179a6b1fe240e09775ade737d1616b73abf4a46cf592'
CONTRASTS = {'C_minus_A': ('C', 'A'), 'C_minus_B': ('C', 'B'), 'B_minus_A': ('B', 'A')}
ARMS = ('A', 'B', 'C')


def module(name, filename):
    s = importlib.util.spec_from_file_location(name, TOOLS/filename)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


base130 = module('sector538_base130', 'stage130_contract_choice_fit.py')
select156 = module('sector538_select156', 'stage156_voluntary_choices.py')


def fit_offset(families, residual, original_weight, mapping, sectors):
    """Exact536 Z, including unknown positive mass; never conditionally renormalize p."""
    w = np.asarray(original_weight, float); r = np.asarray(residual, float)
    if len(w) != len(families) or len(r) != len(w) or not len(w):
        raise ValueError('nonempty aligned offset training required')
    if not np.isfinite(w).all() or (w <= 0).any() or not np.isfinite(r).all():
        raise ValueError('finite residual and positive training weight required')
    w = w/w.sum(); lookup = {g: j for j, g in enumerate(sectors)}
    idx = np.array([lookup.get(mapping.get(str(f)), -1) for f in families], int)
    mapped = idx >= 0; p = np.bincount(idx[mapped], weights=w[mapped], minlength=len(sectors))
    z = np.zeros((len(w), len(sectors)), float)
    z[mapped] = -p
    z[np.flatnonzero(mapped), idx[mapped]] += 1.
    G = z.T @ (w[:, None]*z); b = z.T @ (w*r)
    gamma = np.linalg.solve(G+np.eye(len(sectors)), b)
    delta = gamma-p@gamma
    delta[p == 0] = 0.  # Prediction cold groups are exact fallback, even if p'gamma != 0.
    df = float(np.trace(np.linalg.solve(G+np.eye(len(sectors)), G)))
    if not -1e-12 <= df <= np.trace(G)+1e-12 or np.trace(G) > 1+1e-12:
        raise ValueError('fixed effective df bound failed')
    actual_delta = np.zeros(len(w)); actual_delta[mapped] = delta[idx[mapped]]
    return dict(sectors=list(sectors), p=p.tolist(), G=G.tolist(), b=b.tolist(),
                gamma=gamma.tolist(), delta=delta.tolist(), effective_df=df,
                trace_G=float(np.trace(G)), ridge_lambda=1., normalized_weight_sum=float(w.sum()),
                mapped_training_weight=float(w[mapped].sum()), sumwZ=(w@z).tolist(),
                sumwdelta=float(w@actual_delta), unknown_training_rows=int((~mapped).sum()),
                new_global_intercept=False, zscore=False)


def offsets(families, head, mapping):
    table = {g: d if p > 0 else 0. for g, p, d in zip(head['sectors'], head['p'], head['delta'])}
    return np.array([table.get(mapping.get(str(f)), 0.) for f in families], float)


def select_scope(mothers, scores, calendar, end, scope, arm):
    def alias():
        for row in scores:
            if row['scope'] != scope:
                raise ValueError('own scope score required')
            yield dict(row, scope='main')
    result = select156.select_full_pool(mothers, alias(), calendar, end, audit_sink=lambda _: None)
    for row in result['choices']:
        row['scope'] = scope; row['arm'] = arm
    return result


def diagnostics(choices, actions, end):
    fields = ['action_id', 'label_state', 'participation_state', 'net_R_stress', 'label_known_date']
    linked = choices.merge(actions[fields], left_on='chosen_action_id', right_on='action_id', how='left', validate='many_to_one')
    selected = linked.selected.eq(1)
    closed = linked.label_state.eq('closed_complete_bar_model') & np.isfinite(linked.net_R_stress) & linked.label_known_date.fillna('').ne('') & linked.label_known_date.fillna('').le(end)
    zero = ~selected | linked.participation_state.eq('known_nonparticipation')
    linked['diagnostic_value_R'] = np.where(zero, 0., np.where(closed, linked.net_R_stress, np.nan))
    groups = {}; daily = []; annual = []
    for scope, part in linked.groupby('scope', sort=True):
        family = part.sort_values('selected', ascending=False, kind='stable').drop_duplicates(['arm', 'family_id', 'u_index'])
        arms = {a: family.loc[family.arm.eq(a)].set_index(['family_id', 'u_index']).sort_index() for a in ARMS}
        groups[scope] = {}
        for contrast, (hi, lo) in CONTRASTS.items():
            aa = arms[lo]; cc = arms[hi].reindex(aa.index)
            if len(aa) != len(cc) or cc.u_date.isna().any() or not aa.u_date.eq(cc.u_date).all():
                raise ValueError('full family-u population differs')
            same = aa.chosen_action_id.eq(cc.chosen_action_id)
            known = np.isfinite(aa.diagnostic_value_R) & np.isfinite(cc.diagnostic_value_R)
            values = np.where(same, 0., np.where(known, cc.diagnostic_value_R-aa.diagnostic_value_R, np.nan))
            unknown = ~same & ~known
            f = pd.DataFrame(dict(u_date=aa.u_date.to_numpy(), delta_R=values,
                                  known=np.isfinite(values), unknown=unknown.to_numpy()))
            days = f.groupby('u_date', sort=True).agg(delta_R=('delta_R', 'mean'), known_family_u=('known', 'sum'), unknown_family_u=('unknown', 'sum')).reset_index()
            days['scope'] = scope; days['contrast'] = contrast; daily.append(days)
            mean = float(days.delta_R.mean()) if days.delta_R.notna().any() else None
            record = dict(known_u_equal_mean_increment_R=mean, full_family_u=len(aa),
                          known_increment_family_u=int(np.isfinite(values).sum()),
                          known_source_days=int(days.delta_R.notna().sum()),
                          unknown_differential_selected_events=int(unknown.sum()),
                          common_unresolved_same_action=int((same & aa.chosen_action_id.ne('') & ~known).sum()),
                          unconditional_full_policy_supported=False,
                          selected_by_arm={a: int(part.loc[part.arm.eq(a), 'selected'].sum()) for a in ARMS})
            groups[scope][contrast] = record
            for year, yy in days.groupby(days.u_date.str[:4], sort=True):
                annual.append(dict(scope=scope, contrast=contrast, year=year,
                                   mean_delta_R=float(yy.delta_R.mean()) if yy.delta_R.notna().any() else np.nan,
                                   source_days=len(yy), known_source_days=int(yy.delta_R.notna().sum()),
                                   unknown_family_u=int(yy.unknown_family_u.sum())))
    report = dict(schema='stage538_actual_chosen_action_diagnostic_v1', groups=groups,
                  qualification='nominal observed-support triage, not full unknown policy or cash',
                  full_policy_cash_qualified=False)
    report['nominal_cash_prerequisite'] = nominal_cash_gate(report)
    return report, pd.concat(daily, ignore_index=True), pd.DataFrame(annual), linked


def nominal_cash_gate(report):
    for contrast in ('C_minus_A', 'C_minus_B'):
        values = [report['groups'].get(s, {}).get(contrast, {}).get('known_u_equal_mean_increment_R') for s in ('holdout_0', 'holdout_1')]
        if any(v is None or not np.isfinite(v) or v < 0 for v in values) or not any(v > 0 for v in values):
            return False
    return True


def binding(path):
    p = Path(path).resolve(); h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''): h.update(b)
    return dict(path=str(p), bytes=p.stat().st_size, sha256=h.hexdigest())


def simple(b): return {k: b[k] for k in ('path', 'bytes', 'sha256')}


def small_json(b):
    data = Path(b['path']).read_bytes()
    if len(data) != b['bytes'] or hashlib.sha256(data).hexdigest() != b['sha256']:
        raise ValueError('small binding differs '+b['path'])
    return json.loads(data)


def write_json(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False); f.write('\n')
    return binding(path)


def write_frame(path, frame):
    frame.to_csv(path, index=False, mode='x', compression={'method':'gzip', 'mtime':0}, float_format='%.17g')
    return binding(path)


def source_bundle():
    return [binding(TOOLS/n) for n in ('stage538_sector_residual_fit.py', 'test_stage538_sector_residual_fit.py',
                                     'stage130_contract_choice_fit.py', 'stage071_settlement_narrow_fit.py', 'stage156_voluntary_choices.py')]


class HashedInput:
    """Hash compressed bytes during the sole content read, never a second large-file pass."""
    def __init__(self, expected):
        self.expected = expected; self.f = Path(expected['path']).open('rb'); self.h = hashlib.sha256(); self.n = 0
    def read(self, n=-1):
        data = self.f.read(n); self.h.update(data); self.n += len(data); return data
    def close(self): self.f.close()
    def finish(self):
        if self.n != self.expected['bytes'] or self.h.hexdigest() != self.expected['sha256']:
            raise ValueError('single-read compressed input binding differs '+self.expected['path'])


def read_table_once(b, columns, numeric):
    reader = HashedInput(b)
    try:
        with gzip.GzipFile(fileobj=reader, mode='rb') as stream:
            frame = pd.read_csv(stream, usecols=columns, dtype=str, keep_default_na=False, float_precision='round_trip')
        reader.finish()
    finally: reader.close()
    for c in numeric: frame[c] = pd.to_numeric(frame[c], errors='coerce')
    return frame


def read_npz_once(b):
    data = Path(b['path']).read_bytes()
    if len(data) != b['bytes'] or hashlib.sha256(data).hexdigest() != b['sha256']:
        raise ValueError('npz input binding differs')
    with np.load(io.BytesIO(data), allow_pickle=False) as z: return {k: z[k] for k in z.files}


def check_training(train, groups, raw, weight, portable, scaler, record):
    actual = dict(training_rows=len(train), training_dates=int(train.u_date.nunique()),
                  training_families=int(train.family_id.nunique()), training_groups=len(groups),
                  max_u_date=str(train.u_date.max()), max_label_known_date=str(train.label_known_date.max()))
    if any(actual[k] != record[k] for k in actual): raise ValueError('old training cohort statistics differ')
    if not np.isfinite(weight).all() or (weight <= 0).any() or not np.isclose(weight.mean(), 1., atol=1e-12):
        raise ValueError('old union/day weights invalid')
    stats = [base130.legacy.finite_stats(raw[:, j], weight) for j in range(26)]
    for k in ('mean', 'var', 'scale', 'finite_count'):
        if not np.allclose([s[k] for s in stats], scaler['common'][k], rtol=1e-9, atol=1e-10):
            raise ValueError('original training scaler statistics differ '+k)
    if portable['feature_names'] != base130.FEATURE_NAMES or portable['parameters'] != base130.PARAMETERS:
        raise ValueError('frozen portable52 specification differs')
    X = base130.design(raw, scaler); coef = np.array(portable['coef']); y = train.net_R_stress.to_numpy(float)
    ahat = X@coef+portable['intercept']; z = np.column_stack([X, np.ones(len(X))])
    with base130.legacy.threadpool_limits(limits=1):
        lhs = z.T@(weight[:, None]*z); rhs = z.T@(weight*y)
    lhs[np.arange(52), np.arange(52)] += 1.
    expected = read_npz_once(record['normal_equations_reference'])
    beta = np.r_[coef, portable['intercept']]
    for name, value in [('lhs', lhs), ('rhs', rhs), ('coefficient_with_intercept', beta), ('weight_sum', np.array(weight.sum()))]:
        if not np.allclose(value, expected[name], rtol=1e-9, atol=1e-7):
            raise ValueError('original52 sufficient equations differ '+name)
    actual['normal_equation_max_abs_lhs_difference'] = float(np.max(np.abs(lhs-expected['lhs'])))
    actual['normal_equation_max_abs_rhs_difference'] = float(np.max(np.abs(rhs-expected['rhs'])))
    actual['base_refits'] = 0
    return ahat, actual


def support(frame, mapping, sectors):
    labels = frame.family_id.map(mapping).fillna('UNKNOWN')
    return [dict(sector=g, rows=int(labels.eq(g).sum()),
                 families=int(frame.loc[labels.eq(g), 'family_id'].nunique()),
                 dates=int(frame.loc[labels.eq(g), 'u_date'].nunique())) for g in [*sectors, 'UNKNOWN']]


def authorize(args):
    output = Path(args.output).resolve()
    if output.exists() or LINE/'outputs/stage538_sector_residual_fit' not in output.parents:
        raise ValueError('fresh stage538 output directory required')
    pb = binding(args.protocol)
    if args.protocol_sha256 != PROTOCOL_SHA or pb['sha256'] != PROTOCOL_SHA:
        raise ValueError('frozen536 protocol differs')
    protocol = small_json(pb); inv = small_json(protocol['input_inventory'])
    ab = binding(args.authorization); auth = small_json(ab)
    required = dict(schema='stage538_exact_root_authorization_v1', authorized_by='root',
                    protocol_sha256=PROTOCOL_SHA, input_inventory_sha256=protocol['input_inventory']['sha256'],
                    exact_source_authorized=True, output=str(output), maximum_new_offset_fit=12, base_refits=0)
    if any(auth.get(k) != v for k, v in required.items()) or auth.get('source_bundle') != source_bundle():
        raise ValueError('exact root538 authorization differs')
    return output, protocol, inv, pb, auth, ab


def run_actual(output, protocol, inventory, pb, auth, ab):
    output.mkdir(parents=True, exist_ok=False); started = time.monotonic(); sources = source_bundle()
    attempted = completed = 0; inputs = inventory['input_bindings']; artifacts = {}; heads = {}
    write_json(output/'actual_started.json', dict(status='started', mode='actual', protocol=pb,
               authorization=ab, source_bundle=sources, started_at=datetime.now(timezone.utc).isoformat(), automatic_retry=False))
    def event(filename, value):
        with (output/filename).open('a') as f: f.write(json.dumps(value, ensure_ascii=False)+'\n'); f.flush()
    try:
        for old in inventory['accepted_source_bundle']:
            if binding(old['path']) != simple(old): raise ValueError('accepted source changed '+old['path'])
        sc = inventory['schemas']
        a = read_table_once(inputs['actions'], sc['actions']['usecols'], sc['actions']['numeric_columns'])
        m = read_table_once(inputs['mothers'], sc['mothers']['usecols'], ['sequence_index', 'u_index'])
        common = read_npz_once(inputs['common'])
        raw = common['common']
        if len(a) != sc['actions']['rows'] or len(m) != sc['mothers']['rows'] or raw.shape != tuple(sc['common']['common_shape']) or common['columns'].tolist() != base130.COMMON:
            raise ValueError('full accepted129 input shape differs')
        if not np.array_equal(a.sequence_index.to_numpy(), np.arange(len(a))) or not np.array_equal(m.sequence_index.to_numpy(), np.arange(len(m))) or a.action_id.duplicated().any() or m.event_id.duplicated().any():
            raise ValueError('full accepted129 order/identity differs')
        if not a.action_sequence_index.eq(a.sequence_index).all() or not a.actual_epoch.eq(a.reference_epoch).all() or not a.event_id.eq(a.action_id).all():
            raise ValueError('action aliases differ')
        parent = m.iloc[a.mother_sequence_index.to_numpy(int)].reset_index(drop=True)
        for key, pk in [('product_id','product_id'),('family_id','family_id'),('u_date','u_date'),('u_index','u_index'),('mother_event_id','event_id'),('anchor_epoch','reference_epoch')]:
            if not np.array_equal(a[key].to_numpy(), parent[pk].to_numpy()): raise ValueError('action mother identity differs '+key)
        del parent
        if m.product_id.nunique() != 98 or m.family_id.nunique() != 95: raise ValueError('98/95 mother catalog differs')
        forward_m = m.loc[m.u_date.ge('2020-01-01')].copy()
        if len(forward_m) != 161014: raise ValueError('complete forward parent population differs')
        artifacts['mothers_forward'] = write_frame(output/'mothers_forward.csv.gz', forward_m)
        train_union = set(); fold_records = []
        mappings = {'B':protocol['taxonomy']['placebo_family_mapping'], 'C':protocol['taxonomy']['true_family_mapping']}
        sectors = protocol['taxonomy']['sector_order']
        for old in inventory['folds']:
            scope, cutoff = old['scope'], old['cutoff']; stop = '2023-01-01' if cutoff == '2020-01-01' else None
            train, pred, parents = base130.fold_slices(a, m, cutoff, stop, scope)
            if len(pred) != old['prediction_children'] or len(parents) != old['prediction_mothers']: raise ValueError('old forward fold population differs')
            ti = train.sequence_index.to_numpy(int); train_union.update(ti.tolist())
            wf, group = base130.training_weights(train); weights = wf.sample_weight.to_numpy(float)
            portable = small_json(old['portable_model']); scaler = small_json(old['scaler'])
            with base130.legacy.threadpool_limits(limits=1):
                ahat, check = check_training(train, group, raw[ti], weights, portable, scaler, old)
            folder = output/'folds'/scope/cutoff; folder.mkdir(parents=True)
            compact = pd.concat([train.reset_index(drop=True), wf.reset_index(drop=True)], axis=1)
            compact['normalized_weight'] = weights/weights.sum(); compact['Ahat'] = ahat
            train_b = write_frame(folder/'train_compact.csv.gz', compact)
            for arm in ('B','C'):
                attempted += 1; event('fit_attempts.jsonl', dict(attempt=attempted,scope=scope,cutoff=cutoff,arm=arm))
                h = fit_offset(train.family_id.to_numpy(), train.net_R_stress.to_numpy(float)-ahat, weights, mappings[arm], sectors)
                completed += 1
                h.update(scope=scope,cutoff=cutoff,arm=arm,training_check=check,train_compact=train_b,
                         portable_model=simple(old['portable_model']),scaler=simple(old['scaler']),
                         normal_equations_reference=simple(old['normal_equations_reference']),
                         train_support=support(train,mappings[arm],sectors),forward_support=support(pred,mappings[arm],sectors))
                heads[(scope,cutoff,arm)] = h; artifacts[f'head_{scope}_{cutoff}_{arm}'] = write_json(folder/(arm+'_head.json'),h)
                event('fit_completed.jsonl',dict(completed=completed,scope=scope,cutoff=cutoff,arm=arm,effective_df=h['effective_df']))
            fold_records.append(dict(scope=scope,cutoff=cutoff,train_compact=train_b,training_check=check,
                                     prediction_children=len(pred),prediction_mothers=len(parents)))
            print(json.dumps(dict(phase='offset_fold_complete',scope=scope,cutoff=cutoff,attempted=attempted,completed=completed)),flush=True)
            del train,pred,parents,compact,wf,group,ahat
        unique = np.array(sorted(train_union),np.int64); np.savez_compressed(output/'train_common_unique.npz',sequence_index=unique,raw26=raw[unique],columns=np.array(base130.COMMON))
        artifacts['train_common_unique'] = binding(output/'train_common_unique.npz'); del raw,common,train_union
        cal_np = read_npz_or_npy_calendar(inputs['calendar']); calendar = cal_np
        write_json(output/'calendar.json',calendar)
        artifacts['calendar'] = binding(output/'calendar.json')
        base_scores = {s:np.full(len(a),np.nan) for s in base130.SCOPES}
        score_counts = Counter(); negative = Counter(); reader = HashedInput(inputs['accepted_full_scores'])
        out_score = output/'forward_base_compact.csv.gz'; first = True
        with gzip.GzipFile(filename=str(out_score),mode='xb',mtime=0) as sink:
            try:
                with gzip.GzipFile(fileobj=reader,mode='rb') as source:
                    for chunk in pd.read_csv(source,usecols=sc['accepted_full_scores']['usecols'],dtype=str,keep_default_na=False,chunksize=100000,float_precision='round_trip'):
                        seq = pd.to_numeric(chunk.sequence_index,errors='raise').to_numpy(int)
                        if (seq < 0).any() or (seq >= len(a)).any(): raise ValueError('forward sequence outside actions')
                        action = a.iloc[seq]
                        for k in select156.SCORE_FIELDS:
                            if k in ('score','scope','cutoff'): continue
                            actual = pd.to_numeric(chunk[k],errors='raise').to_numpy() if k in ('sequence_index','mother_sequence_index','u_index','u_action_eligible') else chunk[k].to_numpy()
                            if not np.array_equal(actual,action[k].to_numpy()): raise ValueError('forward action identity differs '+k)
                        scores = pd.to_numeric(chunk.score,errors='raise').to_numpy(float)
                        if not np.isfinite(scores).all(): raise ValueError('nonfinite accepted base score')
                        corrections = {arm:np.zeros(len(chunk)) for arm in ('B','C')}
                        for (scope,cutoff), idx0 in chunk.groupby(['scope','cutoff'],sort=False).indices.items():
                            idx = np.asarray(idx0,int); ids = seq[idx]
                            if scope not in base_scores or len(set(ids)) != len(ids) or np.isfinite(base_scores[scope][ids]).any(): raise ValueError('duplicate/wrong forward scope')
                            if not (action.iloc[idx].u_date.ge(cutoff).all() and (cutoff!='2020-01-01' or action.iloc[idx].u_date.lt('2023-01-01').all())): raise ValueError('forward deployment cutoff differs')
                            if scope!='main' and not action.iloc[idx].family_id.map(base130.family_group).eq(int(scope[-1])).all(): raise ValueError('held own-family score differs')
                            base_scores[scope][ids] = scores[idx]; score_counts[(scope,cutoff)] += len(idx)
                            negative[scope] += int((scores[idx] <= 0).sum())
                            for arm in ('B','C'): corrections[arm][idx] = offsets(action.iloc[idx].family_id.to_numpy(),heads[(scope,cutoff,arm)],mappings[arm])
                        for k in ('label_state','participation_state','net_R_stress','label_known_date'): chunk[k] = action[k].to_numpy()
                        chunk['B_offset'] = corrections['B']; chunk['C_offset'] = corrections['C']
                        chunk.to_csv(sink,index=False,header=first,float_format='%.17g'); first=False
                reader.finish()
            finally: reader.close()
        artifacts['forward_base_compact'] = binding(out_score)
        for old in inventory['folds']:
            if score_counts[(old['scope'],old['cutoff'])] != old['prediction_children']: raise ValueError('full forward scope/fold shrunk')
        forward = a.u_date.ge('2020-01-01').to_numpy()
        if not np.array_equal(np.isfinite(base_scores['main']),forward) or not np.array_equal(np.isfinite(base_scores['holdout_0'])|np.isfinite(base_scores['holdout_1']),forward): raise ValueError('full child coverage shrunk')
        all_choices=[]; selection_records=[]
        for scope in base130.SCOPES:
            parents = forward_m if scope=='main' else forward_m.loc[forward_m.family_id.map(base130.family_group).eq(int(scope[-1]))]
            parent_rows = parents.to_dict('records'); ids = np.flatnonzero(np.isfinite(base_scores[scope])); children = a.iloc[ids]
            for arm in ARMS:
                score = base_scores[scope][ids].copy()
                if arm!='A':
                    for cutoff in base130.CUTOFFS:
                        mask=(children.u_date.lt('2023-01-01') if cutoff=='2020-01-01' else children.u_date.ge('2023-01-01')).to_numpy()
                        score[mask] += offsets(children.loc[mask,'family_id'].to_numpy(),heads[(scope,cutoff,arm)],mappings[arm])
                cf = children[[k for k in select156.SCORE_FIELDS if k not in ('scope','cutoff','score')]].copy()
                cf['score']=score; cf['scope']=scope; cf['cutoff']=np.where(children.u_date.lt('2023-01-01'),'2020-01-01','2023-01-01')
                def score_rows():
                    columns=cf.columns.tolist()
                    for values in cf.itertuples(index=False,name=None): yield dict(zip(columns,values))
                result=select_scope(parent_rows,score_rows(),calendar,base130.END,scope,arm)
                frame=pd.DataFrame(result['choices']); all_choices.append(frame)
                selection_records.append(dict(scope=scope,arm=arm,summary=result['summary']))
                print(json.dumps(dict(phase='selection_complete',scope=scope,arm=arm,parents=len(frame),selected=int(frame.selected.sum()))),flush=True)
        choices=pd.concat(all_choices,ignore_index=True)
        for kind,part in [('main',choices.loc[choices.scope.eq('main')]),('held_union',choices.loc[choices.scope.ne('main')])]:
            if len(part)!=161014*3 or part.duplicated(['arm','event_id']).any(): raise ValueError('complete three-arm parents differ '+kind)
            for arm in ARMS:
                if set(part.loc[part.arm.eq(arm),'event_id']) != set(forward_m.event_id): raise ValueError('complete parent identities shrunk')
        report,daily,annual,linked=diagnostics(choices,a,base130.END)
        artifacts['choices_main']=write_frame(output/'choices_main.csv.gz',choices.loc[choices.scope.eq('main')])
        artifacts['choices_holdout']=write_frame(output/'choices_holdout.csv.gz',choices.loc[choices.scope.ne('main')])
        artifacts['diagnostic_linked']=write_frame(output/'diagnostic_linked.csv.gz',linked)
        artifacts['held_daily']=write_frame(output/'held_daily.csv.gz',daily)
        artifacts['held_annual']=write_frame(output/'held_annual.csv.gz',annual)
        artifacts['held_diagnostic']=write_json(output/'held_diagnostic.json',report)
        artifacts['fold_records']=write_json(output/'fold_records.json',fold_records)
        artifacts['selection_records']=write_json(output/'selection_records.json',selection_records)
        summary=dict(status='completed',new_offset_fit_attempted=attempted,new_offset_fit_completed=completed,base_refits=0,
                     SQL=0,cash_replays=0,downloads=0,old_training_table_reads=0,
                     large_input_content_reads={'actions':1,'common':1,'mothers':1,'old_fullscores':1},
                     mother_rows=len(m),forward_parent_rows=161014,full_forward_score_rows=sum(score_counts.values()),
                     old_nonpositive_score_rows=dict(negative),nominal_cash_prerequisite=report['nominal_cash_prerequisite'],
                     goal_complete=False,production_qualified=False,month_relative_information_added=False)
        if attempted!=12 or completed!=12: raise ValueError('exactly twelve offset fits required')
        if sources!=source_bundle(): raise ValueError('source changed during actual')
        artifacts['summary']=write_json(output/'summary.json',summary)
        terminal=dict(status='completed',mode='actual',exit_code=0,attempted=attempted,completed=completed,base_refits=0,cash=0,SQL=0,downloads=0,automatic_retry=False,elapsed_seconds=time.monotonic()-started)
        artifacts['terminal']=write_json(output/'actual_terminal.json',terminal)
        manifest=dict(schema='stage538_sector_residual_fit_v1',status='completed',mode='actual',protocol=pb,
                      input_inventory=protocol['input_inventory'],input_bindings={k:simple(v) for k,v in inputs.items()},
                      authorization=ab,source_bundle=sources,actual_fit_calls_attempted=attempted,actual_fit_calls_completed=completed,
                      base_refits=0,cash_replays=0,native_source_queries=0,downloads=0,nominal_cash_prerequisite=report['nominal_cash_prerequisite'],
                      goal_complete=False,production_qualified=False,**artifacts)
        write_json(output/'manifest.json',manifest); return manifest
    except BaseException as error:
        if not (output/'actual_terminal.json').exists():
            write_json(output/'actual_terminal.json',dict(status='failed',mode='actual',exit_code=1,attempted=attempted,completed=completed,
                       base_refits=0,cash=0,SQL=0,downloads=0,automatic_retry=False,error_type=type(error).__name__,error=str(error),
                       traceback=traceback.format_exc(),elapsed_seconds=time.monotonic()-started))
        raise


def read_npz_or_npy_calendar(b):
    data=Path(b['path']).read_bytes()
    if len(data)!=b['bytes'] or hashlib.sha256(data).hexdigest()!=b['sha256']: raise ValueError('calendar differs')
    a=np.load(io.BytesIO(data),allow_pickle=False)
    days=([str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in a]
          if a.dtype.kind in 'iu' else a.astype('datetime64[D]').astype(str).tolist())
    if len(days)!=5587 or days!=sorted(set(days)): raise ValueError('accepted source calendar differs')
    return days


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('protocol','protocol-sha256','authorization','output'): p.add_argument('--'+key,required=True)
    args=p.parse_args(argv); output,protocol,inventory,pb,auth,ab=authorize(args)
    result=run_actual(output,protocol,inventory,pb,auth,ab)
    print(json.dumps(dict(status=result['status'],new_offset_fits=result['actual_fit_calls_completed'],output=str(output))),flush=True)


if __name__=='__main__': main()
