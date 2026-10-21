"""只读拆解 Stage190 冻结线性分数；不训练、不重选政策、不读取收益/价格。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import time
import numpy as np
import pandas as pd

LINE = Path(__file__).resolve().parents[1]
FIT = LINE / 'outputs/stage190_registration_fit/actual_run1'
OUT = LINE / 'outputs/stage195_missingness_attribution/actual_run1'
KEY = ['scope', 'cutoff', 'arm']
PKEY = KEY + ['mother_sequence_index', 'product_id', 'u_date']
GKEY = KEY + ['year', 'M', 'eligible']
EPS = 1e-12  # 仅披露近数值边界，绝不替代原严格 >0 门


def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')


def small_binding(p):
    body = p.read_bytes()
    return {'path': str(p), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def stat(p):
    s = p.stat()
    return dict(size=s.st_size, mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns, inode=s.st_ino)


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def main():
    started = time.monotonic()
    OUT.mkdir(parents=True, exist_ok=False)
    dump('started.json', dict(started=now(), actual_fit=0, actual_cash=0, SQL=0,
                            source=small_binding(Path(__file__).resolve())))
    manifest = json.loads((FIT/'manifest.json').read_text())
    assert small_binding(FIT/'manifest.json')['sha256'] == 'ff4a616087af55e31aa9500683e08fdda29dda7aa8a1392a75d158064f1dffff'
    inherited = {r: manifest[r] for r in ['child_scores', 'choices_main', 'choices_holdout']}
    before = {r: stat(Path(b['path'])) for r, b in inherited.items()}
    assert all(before[r]['size'] == b['bytes'] for r, b in inherited.items())
    model_rows, model_bindings = [], []
    for path in sorted(FIT.glob('folds/*/*/*/portable_model.json')):
        body = path.read_bytes()
        binding = dict(path=str(path), bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        assert binding == manifest['artifacts'][str(path.relative_to(FIT))]
        m = json.loads(body)
        assert len(m['coef']) == 54 and m['feature_names'][52:] == ['registration_missing', 'registration_standardized']
        assert m['feature_names'][21] == 'q_missing' and m['feature_names'][47] == 'q_missing_missing'
        if m['arm'] == 'CONTROL54':
            assert m['coef'][53] == 0
        model_rows.append({k: m[k] for k in KEY} | dict(b_m=m['coef'][52], b_q=m['coef'][53], intercept=m['intercept']))
        model_bindings.append(binding)
    models = pd.DataFrame(model_rows)
    assert len(models) == 12 and not models.duplicated(KEY).any()
    groups, partial_parents = [], []
    total = 0
    cols = PKEY + ['sequence_index', 'u_action_eligible', 'score', 'registration_q_raw',
                   'registration_q_missing', 'registration_q_design']
    for c in pd.read_csv(inherited['child_scores']['path'], usecols=cols, chunksize=200000):
        c = c.merge(models, on=KEY, how='left', validate='many_to_one')
        assert not c.b_m.isna().any()
        c['M'] = c.registration_q_missing.astype(int)
        c['eligible'] = c.u_action_eligible.astype(int)
        assert c.M.isin([0, 1]).all() and c.eligible.isin([0, 1]).all()
        assert (c.M.to_numpy() == (~np.isfinite(c.registration_q_raw.to_numpy())).astype(int)).all()
        assert np.isfinite(c[['score', 'registration_q_design']].to_numpy()).all()
        assert (c.loc[c.M.eq(1), 'registration_q_design'] == 0).all()
        assert (c.loc[c.arm.eq('CONTROL54'), 'registration_q_design'] == 0).all()
        c['year'] = c.u_date.str[:4].astype(int)
        c['direct_M'] = c.b_m*c.M
        c['direct_Q'] = c.b_q*c.registration_q_design
        c['without_direct_M'] = c.score-c.direct_M
        c['COMMON52_intercept_remainder'] = c.without_direct_M-c.direct_Q
        c['positive'] = c.score.gt(0).astype(int)
        c['without_M_positive'] = c.without_direct_M.gt(0).astype(int)
        c['positive_to_nonpositive'] = (c.score.gt(0) & c.without_direct_M.le(0)).astype(int)
        c['nonpositive_to_positive'] = (c.score.le(0) & c.without_direct_M.gt(0)).astype(int)
        c['original_exact_zero'] = c.score.eq(0).astype(int)
        c['without_M_exact_zero'] = c.without_direct_M.eq(0).astype(int)
        c['original_near_zero'] = c.score.abs().le(EPS).astype(int)
        c['without_M_near_zero'] = c.without_direct_M.abs().le(EPS).astype(int)
        c['abs_direct_M'] = c.direct_M.abs()
        c['abs_direct_Q'] = c.direct_Q.abs()
        c['eligible_positive'] = c.eligible*c.positive
        c['eligible_without_M_positive'] = c.eligible*c.without_M_positive
        spec = {'actions': ('score', 'size')}
        for col in ['score', 'direct_M', 'direct_Q', 'abs_direct_M', 'abs_direct_Q', 'without_direct_M',
                    'COMMON52_intercept_remainder', 'positive', 'without_M_positive', 'positive_to_nonpositive',
                    'nonpositive_to_positive', 'original_exact_zero', 'without_M_exact_zero',
                    'original_near_zero', 'without_M_near_zero']:
            spec[col+'_sum'] = (col, 'sum')
        groups.append(c.groupby(GKEY, sort=False).agg(**spec).reset_index())
        partial_parents.append(c.groupby(PKEY, sort=False).agg(
            M_min=('M', 'min'), M_max=('M', 'max'), Z_min=('registration_q_design', 'min'),
            Z_max=('registration_q_design', 'max'), actions=('score', 'size'), eligible_actions=('eligible', 'sum'),
            eligible_positive=('eligible_positive', 'sum'),
            eligible_without_M_positive=('eligible_without_M_positive', 'sum')).reset_index())
        total += len(c)
    assert total == 3866960
    action = pd.concat(groups).groupby(GKEY, as_index=False, sort=True).sum()
    parent = pd.concat(partial_parents).groupby(PKEY, as_index=False, sort=False).agg(
        M_min=('M_min', 'min'), M_max=('M_max', 'max'), Z_min=('Z_min', 'min'), Z_max=('Z_max', 'max'),
        actions=('actions', 'sum'), eligible_actions=('eligible_actions', 'sum'),
        eligible_positive=('eligible_positive', 'sum'), eligible_without_M_positive=('eligible_without_M_positive', 'sum'))
    max_M_range = int((parent.M_max-parent.M_min).max())
    max_Z_range = float((parent.Z_max-parent.Z_min).max())
    assert max_M_range == 0 and max_Z_range == 0
    assert not parent.duplicated(KEY+['product_id', 'u_date']).any()
    parent['M'] = parent.M_min
    parent['year'] = parent.u_date.str[:4].astype(int)
    parent['with_eligible_actions'] = parent.eligible_actions.gt(0).astype(int)
    parent['parent_gate_positive'] = parent.eligible_positive.gt(0).astype(int)
    parent['parent_gate_without_M_positive'] = parent.eligible_without_M_positive.gt(0).astype(int)
    parent['parent_gate_positive_to_nonpositive'] = (parent.parent_gate_positive.eq(1) & parent.parent_gate_without_M_positive.eq(0)).astype(int)
    parent['parent_gate_nonpositive_to_positive'] = (parent.parent_gate_positive.eq(0) & parent.parent_gate_without_M_positive.eq(1)).astype(int)
    pspec = {'scored_mothers': ('M', 'size')}
    for col in ['actions', 'eligible_actions', 'with_eligible_actions', 'parent_gate_positive',
                'parent_gate_without_M_positive', 'parent_gate_positive_to_nonpositive', 'parent_gate_nonpositive_to_positive']:
        pspec[col] = (col, 'sum')
    parent_groups = parent.groupby(KEY+['year', 'M'], as_index=False, sort=True).agg(**pspec)
    choices = []
    lookup = parent[KEY+['mother_sequence_index', 'M', 'eligible_actions']].rename(columns={'mother_sequence_index': 'sequence_index'})
    for role in ['choices_main', 'choices_holdout']:
        c = pd.read_csv(inherited[role]['path'], usecols=KEY+['sequence_index', 'u_date', 'selected'])
        assert c.selected.isin([0, 1]).all()
        c = c.merge(lookup, on=KEY+['sequence_index'], how='left', validate='one_to_one')
        assert not (c.selected.eq(1) & c.M.isna()).any()
        c['M'] = c.M.fillna(-1).astype(int)  # -1: 无任何 scored child，绝非登记值缺失
        c['year'] = c.u_date.str[:4].astype(int)
        c['has_eligible_child'] = c.eligible_actions.fillna(0).gt(0).astype(int)
        assert not (c.selected.eq(1) & c.has_eligible_child.eq(0)).any()
        choices.append(c.groupby(KEY+['year', 'M'], as_index=False).agg(
            original_all_mothers=('selected', 'size'), original_selected=('selected', 'sum'),
            original_mothers_with_eligible_child=('has_eligible_child', 'sum')))
    choice_groups = pd.concat(choices).sort_values(KEY+['year', 'M'])
    assert int(choice_groups.original_all_mothers.sum()) == 644056
    assert int(action.actions.sum()) == total and int(parent_groups.actions.sum()) == total
    after = {r: stat(Path(b['path'])) for r, b in inherited.items()}
    assert before == after
    action.to_csv(OUT/'action_groups.csv', index=False, float_format='%.17g')
    parent_groups.to_csv(OUT/'parent_groups.csv', index=False, float_format='%.17g')
    choice_groups.to_csv(OUT/'choice_groups.csv', index=False)
    models.to_csv(OUT/'model_coefficients.csv', index=False, float_format='%.17g')
    cell = action.groupby(KEY, as_index=False).sum(numeric_only=True).drop(columns=['year', 'M', 'eligible'])
    cell.to_csv(OUT/'cell_totals.csv', index=False, float_format='%.17g')
    dump('summary.json', dict(schema='stage195_frozen_score_direct_term_attribution_v1', completed=now(),
        elapsed_seconds=time.monotonic()-started, action_rows=total, model_cells=12,
        scored_mother_model_rows=len(parent), original_choice_mother_model_rows=644056,
        max_within_parent_M_range=max_M_range, max_within_parent_Z_range=max_Z_range,
        actual_fit=0, actual_cash=0, SQL=0, new_selection_policy=0, prices_or_labels_read=0,
        near_boundary_diagnostic=EPS, decision_threshold='strict original >0; no tolerance replacement',
        input_big_bindings=inherited, input_big_binding_evidence='inherited Stage190, fully accepted Stage192/193; byte/stat guard only, no repeated SHA pass',
        before_after_stats=before, input_models=model_bindings,
        outputs={name: small_binding(OUT/name) for name in ['action_groups.csv', 'parent_groups.csv', 'choice_groups.csv', 'model_coefficients.csv', 'cell_totals.csv']},
        limitations=['Frozen algebra, not retrained ablation, no profit causality or counterfactual cash.',
                    'Direct terms depend on coding baseline; no contribution/score importance ratio.',
                    'Eligible action and mother gates are before common K, family priority and account/capacity rules.',
                    'Within-parent ranking invariance does not establish family/account policy invariance.',
                    'COMMON52 remainder can retain missingness proxies; strictPIT=false remains.',
                    'Arms/scopes/children repeat market objects; rows are not independent experiences.']))
    dump('terminal.json', dict(status='completed', completed=now(), actual_fit=0, actual_cash=0, SQL=0))
    print(json.dumps(dict(status='completed', action_rows=total, mother_model_rows=len(parent), elapsed=time.monotonic()-started)))


if __name__ == '__main__':
    main()
