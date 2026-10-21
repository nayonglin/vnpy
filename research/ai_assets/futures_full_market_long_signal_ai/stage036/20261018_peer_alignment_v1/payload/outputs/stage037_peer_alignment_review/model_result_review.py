"""Independent arithmetic review of frozen Stage035 assets; never fit or import author code."""
import argparse
from datetime import datetime
import hashlib
import io
import json
import math
import os
from pathlib import Path
import time

for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ[key] = '1'
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

ROOT = Path('/Users/mac/Desktop/fian')
LINE = ROOT/'research/lines/futures_full_market_long_signal_ai'
OUT = LINE/'outputs/stage037_peer_alignment_review'
OWN = ['r1_atr','r5_atr','r20_atr','body_atr','range_atr','close_location','gap_atr',
       'compression5_20','log_volume_ratio20','breakout20_atr','atr_pct']
ARMS = ['COMMON', 'ALIGNED', 'SHUFFLED']
CTX_COLUMNS=['market_lag_median_r1','market_lag_breadth','market_lag_iqr_r1','market_lag_missing','peer_count','rho_abs_sum','relation_missing','q_aligned','q_shuffled']
SCOPES = {'main': None, 'holdout_0': 0, 'holdout_1': 1}
PERIODS = {'all_2015': '2015-01-01', 'primary_2020': '2020-01-01'}
CI_COLS = [f'{arm}_{side}' for arm in ARMS for side in ('lower','upper')]
CI_COLS += [f'{name}_{side}' for name in ('ALIGNED_minus_COMMON','ALIGNED_minus_SHUFFLED','participation') for side in ('lower','upper')]
CI_COLS += ['stress_'+name for name in CI_COLS.copy()]
MAX_ERRORS = {}


def hash_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def bound(item):
    raw = Path(item['path']).read_bytes()
    assert hash_bytes(raw) == item['sha256'], item['path']
    assert len(raw) == item['bytes'], item['path']
    return raw


def compare_numbers(actual, expected, label, atol=2e-10, rtol=2e-10):
    a = np.asarray(actual, dtype=float); b = np.asarray(expected, dtype=float)
    assert a.shape == b.shape, (label, a.shape, b.shape)
    finite = np.isfinite(a) & np.isfinite(b)
    assert np.array_equal(np.isnan(a), np.isnan(b)), label
    delta = np.abs(a[finite]-b[finite])
    MAX_ERRORS[label] = max(MAX_ERRORS.get(label, 0.), float(delta.max()) if delta.size else 0.)
    assert np.all(delta <= atol+rtol*np.abs(b[finite])), (label, MAX_ERRORS[label])


def compare_tree(actual, expected, label):
    if isinstance(expected, np.ndarray):
        compare_numbers(actual, expected, label)
    elif isinstance(expected, dict):
        for key, value in expected.items():
            assert key in actual, (label, key)
            compare_tree(actual[key], value, label+'.'+key)
    elif isinstance(expected, list):
        assert len(actual) == len(expected), label
        for i, value in enumerate(expected):
            compare_tree(actual[i], value, label+str(i))
    elif expected is None:
        assert actual is None, label
    elif isinstance(expected, (int, float, np.number)) and not isinstance(expected, bool):
        compare_numbers(actual, expected, label)
    elif isinstance(expected, bool):
        assert actual == expected, label


def group(family):
    return int(hashlib.sha256(family.encode()).hexdigest(), 16) % 2


def weighted_scalers(s, context, weight):
    x=np.column_stack([s,context[:,:7]]);total=weight.sum()
    mean=(x*weight[:,None]).sum(axis=0)/total
    var=(((x-mean)**2)*weight[:,None]).sum(axis=0)/total
    values=context[:,7:9]
    qm=float((values*weight[:,None]).sum()/(2*total))
    qv=float((((values-qm)**2)*weight[:,None]).sum()/(2*total))
    return {'common18':{'mean':mean,'var':var,'scale':np.sqrt(np.where(var>0,var,1))},
            'q':{'mean':qm,'var':qv,'scale':np.sqrt(qv) if qv>0 else 1.}}



def head(s, context, arm, scalers):
    raw=np.column_stack([s,context[:,:7]])
    common=(raw-np.asarray(scalers['common18']['mean']))/np.asarray(scalers['common18']['scale'])
    q=np.zeros(len(s)) if arm=='COMMON' else context[:,7 if arm=='ALIGNED' else 8]
    q=(q-scalers['q']['mean'])/scalers['q']['scale']
    return np.column_stack([common,q])



def daily_values(pred, calendar):
    known = pred.loc[pred.label_identified.eq(1)].copy()
    lo = known.proxy_lower.to_numpy(); hi = known.proxy_upper.to_numpy()
    data = {'u_date': known.u_date.to_numpy(), 'identified_rows': np.ones(len(known))}
    masks = {arm: known['pred_'+arm].gt(0).to_numpy(dtype=float) for arm in ARMS}
    for arm, mask in masks.items():
        for prefix, cost in [('', 0.), ('stress_', .8)]:
            data[prefix+arm+'_lower'] = mask*(lo-cost)
            data[prefix+arm+'_upper'] = mask*(hi-cost)
        data[arm+'_selection_rate'] = mask
        data[arm+'_mse_proxy_lower'] = (known['pred_'+arm].to_numpy()-lo)**2
    p = known.assign(mask=masks['ALIGNED']).groupby('u_date')['mask'].transform('mean').to_numpy()
    for name, a in [('ALIGNED_minus_COMMON', masks['ALIGNED']-masks['COMMON']),
                    ('ALIGNED_minus_SHUFFLED', masks['ALIGNED']-masks['SHUFFLED']),
                    ('participation', masks['ALIGNED']-p)]:
        for prefix, cost in [('', 0.), ('stress_', .8)]:
            ends = np.stack([a*(lo-cost), a*(hi-cost)])
            data[prefix+name+'_lower'] = ends.min(axis=0)
            data[prefix+name+'_upper'] = ends.max(axis=0)
    events = pd.DataFrame(data)
    result = events.groupby('u_date').mean()
    result['identified_rows'] = events.groupby('u_date').size()
    return result.reindex(pd.Index(calendar, name='u_date'))


def num_mean(values):
    values = np.asarray(values, dtype=float); values = values[np.isfinite(values)]
    return float(values.mean()) if len(values) else None


def cohort_and_rare(pred):
    known = pred.label_identified.eq(1); unknown = ~known
    count = {'feature_ready_predictions': len(pred), 'identified_rows': int(known.sum()),
             'unknown_rows': int(unknown.sum()), 'unknown_label_states': pred.loc[unknown,'label_state'].value_counts().to_dict(),
             'unknown_rate': num_mean(unknown)}
    rare = {}
    for arm in ARMS:
        mask = pred['pred_'+arm].gt(0); selected = known & mask; missing = unknown & mask
        selected_frame = pred.loc[selected]; n = len(selected_frame)
        count[arm] = {'all_ready_selection_rate': num_mean(mask), 'identified_selection_rate': num_mean(mask[known]),
                      'unknown_selection_rate': num_mean(mask[unknown]), 'selected_identified_rows': n,
                      'selected_identified_dates': int(selected_frame.u_date.nunique()),
                      'selected_identified_families': int(selected_frame.family_id.nunique()),
                      'selected_unknown_rows': int(missing.sum()), 'selected_unknown_dates': int(pred.loc[missing,'u_date'].nunique()),
                      'selected_unknown_families': int(pred.loc[missing,'family_id'].nunique())}
        certain = int(selected_frame.label_state.eq('profit_only').sum())
        ambiguous = int(selected_frame.label_state.eq('double_touch_interval').sum())
        rare[arm] = {'selected_identified_rows': n, 'dates': int(selected_frame.u_date.nunique()),
                     'families': int(selected_frame.family_id.nunique()), 'certain_profit_only_rows': certain,
                     'double_touch_rows': ambiguous, 'target_touch_fraction_lower': certain/n if n else None,
                     'target_touch_fraction_upper': (certain+ambiguous)/n if n else None,
                     'mean_interval_width': num_mean(selected_frame.proxy_upper-selected_frame.proxy_lower),
                     'excluded_certain_profit_only_rows': int((known & ~mask & pred.label_state.eq('profit_only')).sum())}
    count['context_coverage']={'relation_missing_rate':num_mean(pred.relation_missing),'market_lag_missing_rate':num_mean(pred.market_lag_missing),
                               'mean_peer_count':num_mean(pred.peer_count),'mean_rho_abs_sum':num_mean(pred.rho_abs_sum)}
    return count, rare


def block_ci(daily):
    values = daily[CI_COLS].to_numpy(); n = len(values); block = min(60,n)
    rng = np.random.default_rng(20261018); digest = hashlib.sha256(); samples = []
    for unused in range(2000):
        starts = rng.integers(0, n-block+1, size=math.ceil(n/block))
        indices = np.concatenate([np.arange(start,start+block) for start in starts])[:n]
        digest.update(indices.astype('<i8').tobytes())
        selected = values[indices]; valid = np.isfinite(selected); denominator = valid.sum(axis=0)
        samples.append(np.divide(np.nan_to_num(selected,nan=0.).sum(axis=0), denominator,
                                 out=np.full(len(CI_COLS),np.nan), where=denominator>0))
    samples = np.asarray(samples)
    result = {}
    for j, name in enumerate(CI_COLS):
        finite = samples[:,j][np.isfinite(samples[:,j])]
        limits = np.quantile(finite,[.025,.975]) if len(finite) else [None,None]
        result[name] = {'mean': num_mean(values[:,j]), 'ci95_lower': limits[0], 'ci95_upper': limits[1],
                        'finite_source_days': int(np.isfinite(values[:,j]).sum()), 'finite_bootstrap_replicates': len(finite)}
    return {'block_length': 60, 'effective_block_length': block, 'repetitions': 2000,
            'seed': 20261018, 'source_grid_days': n, 'common_indices_sha256': digest.hexdigest(), 'metrics': result}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--manifest', required=True)
    parser.add_argument('--manifest-sha256', required=True); args = parser.parse_args()
    began = time.monotonic(); started = datetime.now().astimezone().isoformat(timespec='seconds')
    path = Path(args.manifest); raw = path.read_bytes(); assert hash_bytes(raw) == args.manifest_sha256
    manifest = json.loads(raw); experiment = path.parent
    assert manifest['source']['sha256'] == '7141bb6e026fece3baa88d1a98db1d5cbe2a6ed8268d5e5ed9d116b7d4204292'
    bound(manifest['source']); bound(manifest['tests'])
    assert manifest['status'] == 'completed' and manifest['actual_fit_calls'] == 108
    assert manifest['financial_runs'] == 0 and not manifest['financial_ready'] and not manifest['production_qualified']
    for item in manifest['artifacts']:
        bound(item)
    terminal = json.loads((experiment/'actual_terminal.json').read_text())
    assert terminal['status'] == 'completed' and terminal['exit_code'] == 0 and terminal['actual_ridge_fit_calls'] == 108
    assert terminal['actual_financial_runs'] == 0
    inputs = manifest['input_bindings']
    parent = json.loads(bound(inputs['data_manifest'])); context_manifest = json.loads(bound(inputs['context_manifest']))
    frame = pd.read_csv(io.BytesIO(bound(parent['feature_label_csv'])), compression='gzip', dtype=str, keep_default_na=False)
    for c in ['feature_ready','label_identified','path_ambiguous',*OWN,'gross_lower','gross_upper','proxy_lower','proxy_upper']:
        frame[c] = pd.to_numeric(frame[c].replace('',np.nan))
    ready = frame.loc[frame.feature_ready.eq(1)].copy()
    ready['sequence_index'] = np.arange(len(ready)); ready['family_group'] = ready.family_id.map(group)
    with np.load(io.BytesIO(bound(context_manifest['context_npz'])),allow_pickle=False) as saved:
        assert set(saved.files)==set(SCOPES)
        contexts={scope:saved[scope] for scope in SCOPES}
    calendar=parent['source_calendar_scope_dates']
    pred = {}; scalar_predictions = 0; cell_count = 0; normal_checks = []
    with threadpool_limits(limits=1):
        for scope, held in SCOPES.items():
            p = pd.read_csv(experiment/f'predictions_{scope}.csv.gz',dtype=str,keep_default_na=False)
            for c in ['test_year','label_identified','path_ambiguous','gross_lower','gross_upper','proxy_lower','proxy_upper',
                      *['pred_'+a for a in ARMS],*['mask_'+a for a in ARMS],*CTX_COLUMNS]:
                p[c] = pd.to_numeric(p[c].replace('',np.nan))
            assert not p.event_id.duplicated().any()
            expected_ids = []
            for year in range(2015,2027):
                cutoff = next(d for d in calendar if d.startswith(str(year)))
                train = ready.loc[ready.label_identified.eq(1) & ready.u_date.lt(cutoff)
                                   & ready.label_known_date.ne('') & ready.label_known_date.lt(cutoff)].copy()
                test = ready.loc[ready.u_date.str.startswith(str(year))].copy()
                if held is not None:
                    train = train.loc[train.family_group.ne(held)]; test = test.loc[test.family_group.eq(held)]
                train = train.sort_values(['u_date','event_id']); test = test.sort_values(['u_date','event_id'])
                expected_ids.extend(test.event_id.tolist()); weights = 1/train.groupby('u_date').u_date.transform('size').to_numpy()
                weights /= weights.mean(); s = train[OWN].to_numpy(); qt = contexts[scope][train.sequence_index.to_numpy()]
                scales = weighted_scalers(s, qt, weights)
                cell = experiment/'fits'/f'{year}_{scope}'
                with np.load(cell/'training_membership.npz',allow_pickle=False) as membership:
                    assert np.array_equal(membership['sequence_index'],train.sequence_index.to_numpy())
                    compare_numbers(membership['weights'],weights,'all_training_weights',atol=1e-14,rtol=1e-14)
                actual = p.loc[p.test_year.eq(year)].set_index('event_id').loc[test.event_id]
                for c in ['product_id','family_id','exchange','u_date','reference_epoch','planned_execution_date','status',
                          'history_state','label_state','label_known_date']:
                    assert actual[c].tolist() == test[c].tolist(), (scope,year,c)
                for c in ['label_identified','path_ambiguous','gross_lower','gross_upper','proxy_lower','proxy_upper']:
                    compare_numbers(actual[c],test[c],'saved_label_'+c)
                compare_numbers(actual[CTX_COLUMNS].to_numpy(),contexts[scope][test.sequence_index.to_numpy()],'all_saved_contexts')
                for arm in ARMS:
                    record = json.loads((cell/(arm+'.json')).read_text()); cell_count += 1
                    assert record['cutoff_exclusive'] == cutoff and record['heldout_group'] == held
                    assert record['training_rows'] == len(train) and record['training_dates'] == train.u_date.nunique()
                    assert record['training_families'] == sorted(train.family_id.unique())
                    assert record['training_ids_sha256'] == hash_bytes(('\n'.join(train.event_id)+'\n').encode())
                    assert record['training_weights_sha256'] == hash_bytes(weights.astype('<f8').tobytes())
                    compare_tree(record['scalers'],scales,'scalers')
                    assert record['max_u_date'] == train.u_date.max() and record['max_label_known_date'] == train.label_known_date.max()
                    assert record['alpha'] == 1 and record['head_dimension'] == 19
                    assert record['scope']==scope and record['context_scope']==scope
                    assert record['context_manifest']==inputs['context_manifest']
                    h = head(test[OWN].to_numpy(),contexts[scope][test.sequence_index.to_numpy()],arm,record['scalers'])
                    score = h@np.asarray(record['coef'])+record['intercept']; scalar_predictions += len(score)
                    compare_numbers(actual['pred_'+arm],score,'all_predictions')
                    assert np.array_equal(actual['mask_'+arm].to_numpy(),score>0)
                    if (year,scope) in [(2015,'main'),(2026,'holdout_0')]:
                        htrain = head(s,qt,arm,record['scalers'])
                        error = htrain@np.asarray(record['coef'])+record['intercept']-train.proxy_lower.to_numpy()
                        gradient = htrain.T@(weights*error)+np.asarray(record['coef'])
                        scale = max(1.,np.abs(htrain.T@(weights*train.proxy_lower.to_numpy())).max())
                        relative = float(np.abs(gradient).max()/scale)
                        intercept_residual = abs(float(np.dot(weights,error)/weights.sum()))
                        assert relative < 2e-8 and intercept_residual < 1e-10
                        normal_checks.append({'fit_id':record['fit_id'],'relative_normal_residual':relative,
                                              'weighted_intercept_residual':intercept_residual})
            assert p.event_id.tolist() == expected_ids
            pred[scope] = p
    assert cell_count == 108 and len(normal_checks) == 6
    pred['holdout_combined'] = pd.concat([pred['holdout_0'],pred['holdout_1']],ignore_index=True)
    assert not pred['holdout_combined'].event_id.duplicated().any()
    metrics = json.loads((experiment/'metrics.json').read_text()); independent = {}; daily_count = 0
    for scope,p in pred.items():
        independent[scope] = {'annual':{}}
        selectors = [(str(y),p.u_date.str.startswith(str(y)),[d for d in calendar if d.startswith(str(y))]) for y in range(2015,2027)]
        selectors += [(name,p.u_date.ge(start),[d for d in calendar if d>=start]) for name,start in PERIODS.items()]
        for name,mask,dates in selectors:
            selected = p.loc[mask]; d = daily_values(selected,dates); daily_count += 1
            cohort,rare = cohort_and_rare(selected)
            report = {'cohort':cohort,'date_equal_means':{c:num_mean(d[c]) for c in d},
                      'source_grid_days':len(dates),'no_identified_days':int(d.identified_rows.isna().sum()),'rare_quality':rare}
            if name in PERIODS:
                actual_daily = pd.read_csv(experiment/f'daily_{scope}_{name}.csv',index_col=0)
                assert actual_daily.index.tolist() == dates
                compare_numbers(actual_daily[d.columns].to_numpy(),d.to_numpy(),'all_daily_outputs')
                if scope == 'main':
                    ci = block_ci(d); report['bootstrap'] = ci
                    assert metrics['scopes'][scope][name]['bootstrap']['common_indices_sha256'] == ci['common_indices_sha256']
                independent[scope][name] = report
                compare_tree(metrics['scopes'][scope][name],report,'metrics.'+scope+'.'+name)
            else:
                independent[scope]['annual'][name] = report
                compare_tree(metrics['scopes'][scope]['annual'][name],report,'annual.'+scope+'.'+name)
    primary = independent['main']['primary_2020']; secondary = independent['main']['all_2015']
    ci = primary['bootstrap']['metrics']; means = primary['date_equal_means']
    positive = lambda x: x is not None and np.isfinite(x) and x>0
    gates = {'primary_ALIGNED_selected_identified_dates_ge60':primary['cohort']['ALIGNED']['selected_identified_dates']>=60,
             'primary_ALIGNED_selected_identified_families_ge8':primary['cohort']['ALIGNED']['selected_identified_families']>=8,
             'primary_ALIGNED_lower_ci_positive':positive(ci['ALIGNED_lower']['ci95_lower']),
             'primary_ALIGNED_minus_COMMON_lower_ci_positive':positive(ci['ALIGNED_minus_COMMON_lower']['ci95_lower']),
             'primary_ALIGNED_minus_SHUFFLED_lower_ci_positive':positive(ci['ALIGNED_minus_SHUFFLED_lower']['ci95_lower']),
             'primary_participation_lower_ci_positive':positive(ci['participation_lower']['ci95_lower']),
             'same_mask_cost_1R_primary_ALIGNED_lower_positive':positive(means['stress_ALIGNED_lower']),
             'four_complete_years_ALIGNED_minus_COMMON_lower_positive':sum(positive(independent['main']['annual'][str(y)]['date_equal_means']['ALIGNED_minus_COMMON_lower']) for y in range(2020,2026))>=4,
             'four_complete_years_ALIGNED_minus_SHUFFLED_lower_positive':sum(positive(independent['main']['annual'][str(y)]['date_equal_means']['ALIGNED_minus_SHUFFLED_lower']) for y in range(2020,2026))>=4,
             'partial_2026_ALIGNED_lower_positive':positive(independent['main']['annual']['2026']['date_equal_means']['ALIGNED_lower'])}
    for key in ['ALIGNED_lower','ALIGNED_minus_COMMON_lower','ALIGNED_minus_SHUFFLED_lower','participation_lower']:
        gates['all_2015_'+key+'_positive'] = positive(secondary['date_equal_means'][key])
    for g in (0,1):
        for key in ['ALIGNED_lower','ALIGNED_minus_COMMON_lower','ALIGNED_minus_SHUFFLED_lower']:
            gates[f'holdout_{g}_primary_{key}_positive'] = positive(independent[f'holdout_{g}']['primary_2020']['date_equal_means'][key])
    gates = {k:bool(v) for k,v in gates.items()}; assert len(gates) == 20 and metrics['gates'] == gates
    assert metrics['quality_information_screen_pass'] == all(gates.values())
    assert all(value is None for value in metrics['financial_metrics'].values())
    result = {'schema':'stage037_peer_alignment_independent_review_v1','independent_review':True,
              'status':'accepted_calculations_screen_pass' if all(gates.values()) else 'accepted_calculations_rejected_quality_screen',
              'manifest':{'path':str(path),'sha256':args.manifest_sha256,'bytes':len(raw)},
              'source_code_read':manifest['source'],'fit_records_checked':cell_count,'scalar_predictions_checked':scalar_predictions,
              'normal_equations_checked':normal_checks,'all_period_scope_reports_checked':daily_count,
              'gates':gates,'quality_information_screen_pass':all(gates.values()),
              'max_abs_prediction_error':MAX_ERRORS['all_predictions'],'max_abs_daily_output_error':MAX_ERRORS['all_daily_outputs'],
              'max_abs_numeric_error':max(MAX_ERRORS.values()),'critical':0,'important':0,'minor':0,
              'qualified_for_fixed_proxy_experiment':True,'real_economic_labels_ready':False,'financial_ready':False,'production_qualified':False,
              'fit_calls':0,'sql_queries':0,'author_calculation_imports':0,'financial_backtests':0,'downloads':0,
              'primary_2020_date_equal_means':means,
              'limitations':['Fixed peer projection conditional DAY proxy only; not cash returns or deployability; q can proxy own lag omitted from COMMON, not proof beyond full own history or causality.',
                             'Fixed-prediction block CI excludes model retraining and repeated researcher selection.',
                             'No SQL or full q rebuild; separate context review covers full schema/main summaries plus492 independently reconstructed cells and code/behavior causal boundaries.']}
    (OUT/'review_receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    end = {'schema':'stage037_model_result_actual_terminal_v1','exit_code':0,'started_at':started,
           'finished_at':datetime.now().astimezone().isoformat(timespec='seconds'),'elapsed_seconds':time.monotonic()-began,
           'source_sha256':hash_bytes(Path(__file__).read_bytes()),'fit_calls':0,'sql_queries':0,'financial_backtests':0}
    (OUT/'actual_terminal.json').write_text(json.dumps(end,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'fit_records':cell_count,'scalar_predictions':scalar_predictions,
                      'gates_true':sum(gates.values()),'gates_false':20-sum(gates.values()),
                      'max_prediction_error':result['max_abs_prediction_error'],'elapsed_seconds':end['elapsed_seconds']}))


if __name__ == '__main__':
    main()
