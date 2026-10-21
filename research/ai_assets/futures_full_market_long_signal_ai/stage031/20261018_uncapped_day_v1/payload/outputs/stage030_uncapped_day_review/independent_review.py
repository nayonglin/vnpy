"""Independent fixed uncapped DAY review; no author calculation imports, SQL or fits."""
import argparse
from datetime import datetime
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import time

import numpy as np
import pandas as pd

ROOT = Path('/Users/mac/Desktop/fian')
LINE = ROOT/'research/lines/futures_full_market_long_signal_ai'
OUT = LINE/'outputs/stage030_uncapped_day_review'
PROTOCOL = LINE/'outputs/stage028_uncapped_day_protocol/protocol.json'
PROTOCOL_SHA = '5c2ed793c64f74d503e7a474a93e4885905087b087e7925756c8395eb35100f2'
MAX_ERRORS = {}
FIELDS = ['A_gross_lower','A_gross_upper','B_gross_lower','B_gross_upper','A_lower','A_upper','B_lower','B_upper',
          'paired_lower','paired_upper','stress_A_lower','stress_A_upper','stress_B_lower','stress_B_upper',
          'stress_paired_lower','stress_paired_upper','tail_gain','giveback','double_penalty_lower','double_penalty_upper','new_realized_tail']
CI_FIELDS = ['A_lower','A_upper','B_lower','B_upper','paired_lower','paired_upper','stress_A_lower','stress_A_upper',
             'stress_B_lower','stress_B_upper','stress_paired_lower','stress_paired_upper','tail_gain','giveback',
             'double_penalty_lower','double_penalty_upper','new_realized_tail']


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def bound(item):
    raw = Path(item['path']).read_bytes()
    assert digest(raw) == item['sha256'], item['path']
    if 'bytes' in item:
        assert len(raw) == item['bytes'], item['path']
    return raw


def csv_bound(item):
    raw = bound(item)
    return pd.read_csv(io.BytesIO(raw), compression='gzip' if item['path'].endswith('.gz') else None,
                       dtype=str, keep_default_na=False)


def compare(a, b, key, atol=1e-9, rtol=1e-12):
    a = np.asarray(a,dtype=float); b = np.asarray(b,dtype=float)
    assert a.shape == b.shape, (key,a.shape,b.shape)
    assert np.array_equal(np.isnan(a),np.isnan(b)), key
    good = np.isfinite(a)&np.isfinite(b); error = np.abs(a[good]-b[good])
    MAX_ERRORS[key] = max(MAX_ERRORS.get(key,0.),float(error.max()) if error.size else 0.)
    assert np.all(error <= atol+rtol*np.abs(b[good])), (key,MAX_ERRORS[key])


def family_group(family):
    return int(hashlib.sha256(family.encode()).hexdigest(),16)%2


def numbers(series):
    return np.array([float(value) if str(value)!='' else np.nan for value in series],dtype=float)


def compare_tree(actual,expected,key):
    if isinstance(expected,dict):
        assert set(expected)<=set(actual),key
        for k,v in expected.items():compare_tree(actual[k],v,key+'.'+k)
    elif expected is None:
        assert actual is None,key
    elif isinstance(expected,(int,float,np.number)) and not isinstance(expected,bool):
        compare(actual,expected,key)


def load_and_derive():
    protocol_raw = PROTOCOL.read_bytes(); assert digest(protocol_raw) == PROTOCOL_SHA
    protocol = json.loads(protocol_raw); bound(protocol['frozen_spec'])
    parent = json.loads(bound(protocol['data_manifest']))
    frame = csv_bound(parent['feature_label_csv']); audit = csv_bound(parent['audit_paths'])
    assert len(frame) == 399252 and not frame.event_id.duplicated().any()
    assert len(audit) == 212852 and not audit.event_id.duplicated().any()
    assert set(audit.event_id) == set(frame.loc[frame.reference_epoch.ne(''),'event_id'])
    assert frame.status.eq('observed_long_research_opportunity').equals(frame.reference_epoch.ne(''))
    audit = audit.set_index('event_id')
    observed = frame.loc[frame.reference_epoch.ne('')].set_index('event_id')
    for key in ['u_date','reference_epoch','planned_execution_date','history_state','label_state']:
        assert observed[key].equals(audit.loc[observed.index,key]), key
    for key in ['feature_ready','label_identified','path_ambiguous','gross_lower','gross_upper','proxy_lower','proxy_upper']:
        frame[key] = numbers(frame[key])
    assert int(frame.feature_ready.sum()) == 194709 and int(frame.label_identified.sum()) == 194168
    known = frame.label_identified.eq(1)
    assert int((frame.feature_ready.eq(1)&~known).sum()) == 541
    frame['family_group'] = frame.family_id.map(family_group)
    frame['ind_A_gross_lower'] = frame.gross_lower
    frame['ind_A_gross_upper'] = frame.gross_upper
    frame['ind_B_gross'] = np.nan
    frame['ind_pair_lower'] = np.nan; frame['ind_pair_upper'] = np.nan
    frame['ind_tail_gain'] = np.nan; frame['ind_giveback'] = np.nan
    frame['ind_ambig_lower'] = np.nan; frame['ind_ambig_upper'] = np.nan
    audit_known = audit.loc[frame.loc[known,'event_id']]
    entry = numbers(audit_known.ideal_entry_F); risk = numbers(audit_known.risk_distance)
    close_r = (numbers(audit_known.D_close)-entry)/risk
    frame['D_close_R'] = np.nan; frame.loc[known,'D_close_R'] = close_r
    frame['raw_stop_touch_diagnostic'] = np.nan
    frame['raw_profit_touch_diagnostic'] = np.nan
    frame.loc[known,'raw_stop_touch_diagnostic'] = (numbers(audit_known.D_low)<=numbers(audit_known.ideal_stop)).astype(int)
    frame.loc[known,'raw_profit_touch_diagnostic'] = (numbers(audit_known.D_high)>=numbers(audit_known.ideal_profit)).astype(int)
    frame.loc[known,['ind_tail_gain','ind_giveback','ind_ambig_lower','ind_ambig_upper']] = 0.
    for state in ['stop_only','day_close','profit_only','double_touch_interval']:
        mask = known & frame.label_state.eq(state)
        if state in ['stop_only','double_touch_interval']:
            frame.loc[mask,'ind_B_gross'] = -1.
        elif state == 'day_close':
            compare(frame.loc[mask,'gross_lower'],frame.loc[mask,'gross_upper'],'day_close_single')
            frame.loc[mask,'ind_B_gross'] = frame.loc[mask,'gross_lower']
        else:
            rows = audit.loc[frame.loc[mask,'event_id']]
            close = numbers(rows['D_close'])
            entry = numbers(rows['ideal_entry_F'])
            risk = numbers(rows['risk_distance'])
            assert np.all(np.isfinite(close)) and np.all(np.isfinite(entry)) and np.all(risk>0)
            value = (close-entry)/risk
            frame.loc[mask,'ind_B_gross'] = value
            frame.loc[mask,'ind_tail_gain'] = np.maximum(value-4,0.)
            frame.loc[mask,'ind_giveback'] = np.minimum(value-4,0.)
        if state == 'double_touch_interval':
            frame.loc[mask,'ind_ambig_lower'] = -5.
    frame.loc[known,'ind_pair_lower'] = frame.loc[known,['ind_tail_gain','ind_giveback','ind_ambig_lower']].sum(axis=1)
    frame.loc[known,'ind_pair_upper'] = frame.loc[known,['ind_tail_gain','ind_giveback','ind_ambig_upper']].sum(axis=1)
    frame['ind_B_net'] = frame.ind_B_gross-.2
    frame['ind_B_stress'] = frame.ind_B_gross-1.
    frame['ind_A_stress_lower'] = frame.gross_lower-1.
    frame['ind_A_stress_upper'] = frame.gross_upper-1.
    frame['ind_B_gt4'] = known & frame.ind_B_gross.gt(4.)
    assert np.isfinite(frame.loc[known,['ind_B_gross','ind_pair_lower','ind_pair_upper']]).all().all()
    assert frame.loc[~known,['ind_B_gross','ind_pair_lower','ind_pair_upper']].isna().all().all()
    translations = {'A_gross_lower':'gross_lower','A_gross_upper':'gross_upper',
        'B_gross_lower':'ind_B_gross','B_gross_upper':'ind_B_gross','A_lower':'proxy_lower','A_upper':'proxy_upper',
        'B_lower':'ind_B_net','B_upper':'ind_B_net','paired_lower':'ind_pair_lower','paired_upper':'ind_pair_upper',
        'stress_A_lower':'ind_A_stress_lower','stress_A_upper':'ind_A_stress_upper',
        'stress_B_lower':'ind_B_stress','stress_B_upper':'ind_B_stress','stress_paired_lower':'ind_pair_lower','stress_paired_upper':'ind_pair_upper',
        'tail_gain':'ind_tail_gain','giveback':'ind_giveback','double_penalty_lower':'ind_ambig_lower','double_penalty_upper':'ind_ambig_upper'}
    for output,independent in translations.items():frame[output] = frame[independent]
    frame['new_realized_tail'] = np.nan;frame.loc[known,'new_realized_tail'] = frame.loc[known,'ind_B_gt4'].astype(int)
    frame['A_width'] = frame.proxy_upper-frame.proxy_lower;frame['B_width'] = frame.ind_B_gross-frame.ind_B_gross
    frame['paired_width'] = frame.ind_pair_upper-frame.ind_pair_lower
    frame['evaluation_state'] = np.where(frame.feature_ready.eq(0),'not_feature_ready',frame.label_state)
    frame.loc[known,'evaluation_state'] = 'identified'
    return protocol,parent,frame


def finite_mean(values):
    values = np.asarray(values,dtype=float);values = values[np.isfinite(values)]
    return float(values.mean()) if len(values) else None


def daily_values(frame,calendar):
    known = frame.loc[frame.label_identified.eq(1)]
    cols = [*FIELDS,'A_width','B_width','paired_width']
    values = known.groupby('u_date')[cols].mean()
    values['identified_rows'] = known.groupby('u_date').size()
    return values.reindex(pd.Index(calendar,name='u_date'))


def cohort(frame):
    ready = frame.feature_ready.eq(1);known = frame.label_identified.eq(1)
    tail = known&frame.ind_B_gt4
    return {'outer_rows':len(frame),'observed_rows':int(frame.reference_epoch.ne('').sum()),
            'feature_ready_rows':int(ready.sum()),'identified_rows':int(known.sum()),'unready_rows':int((~ready).sum()),
            'ready_unknown_rows':int((ready&~known).sum()),'label_states':frame.label_state.value_counts().to_dict(),
            'ready_unknown_states':frame.loc[ready&~known,'label_state'].value_counts().to_dict(),
            'new_realized_tail_rows':int(tail.sum()),'new_realized_tail_dates':int(frame.loc[tail,'u_date'].nunique()),
            'new_realized_tail_families':int(frame.loc[tail,'family_id'].nunique()),
            'original_double_touch_rows':int((known&frame.label_state.eq('double_touch_interval')).sum()),
            'profit_only_giveback_rows':int((known&frame.ind_giveback.lt(0)).sum())}


def bootstrap(daily):
    array = daily[CI_FIELDS].to_numpy(); n = len(array);block = min(60,n)
    rng = np.random.default_rng(20261018); h = hashlib.sha256();samples = []
    for unused in range(2000):
        starts = rng.integers(0,n-block+1,size=math.ceil(n/block))
        indices = np.concatenate([np.arange(start,start+block) for start in starts])[:n]
        h.update(indices.astype('<i8').tobytes());selected = array[indices]
        denominator = np.isfinite(selected).sum(axis=0)
        samples.append(np.divide(np.nan_to_num(selected,nan=0.).sum(axis=0),denominator,
                                 out=np.full(len(CI_FIELDS),np.nan),where=denominator>0))
    samples = np.asarray(samples);metrics = {}
    for j,key in enumerate(CI_FIELDS):
        finite = samples[:,j][np.isfinite(samples[:,j])]
        ci = np.quantile(finite,[.025,.975]) if len(finite) else [None,None]
        metrics[key] = {'mean':finite_mean(array[:,j]),'ci95_lower':ci[0],'ci95_upper':ci[1],
                        'finite_source_days':int(np.isfinite(array[:,j]).sum()),'finite_bootstrap_replicates':len(finite)}
    return {'block_length_source_days':60,'effective_block_length':block,'repetitions':2000,'seed':20261018,
            'source_grid_days':n,'common_indices_sha256':h.hexdigest(),'metrics':metrics}


def main():
    parser = argparse.ArgumentParser();parser.add_argument('--manifest',required=True)
    parser.add_argument('--manifest-sha256',required=True);args = parser.parse_args()
    began = time.monotonic();started = datetime.now().astimezone().isoformat(timespec='seconds')
    path = Path(args.manifest);raw = path.read_bytes();assert digest(raw) == args.manifest_sha256
    manifest = json.loads(raw);experiment = path.parent
    assert manifest['status'] == 'completed' and manifest['actual_model_fit_calls'] == 0
    assert manifest['financial_runs'] == 0 and not manifest['financial_ready'] and not manifest['production_qualified']
    assert manifest['source']['sha256'] == 'ee388ea4439b240054b8b5eb6dfa9907c6e982104ce8e6418cbe5057849d0fe2'
    bound(manifest['source']);bound(manifest['tests'])
    for item in manifest['artifacts']:bound(item)
    terminal = json.loads((experiment/'actual_terminal.json').read_text())
    assert terminal['status'] == 'completed' and terminal['exit_code'] == 0
    assert terminal['actual_model_fit_calls'] == 0 and terminal['financial_runs'] == 0 and terminal['sql_queries'] == 0
    protocol,parent,frame = load_and_derive();calendar = parent['source_calendar_scope_dates']
    actual = pd.read_csv(experiment/'event_intervals.csv.gz',dtype=str,keep_default_na=False)
    assert len(actual) == len(frame) and actual.event_id.tolist() == frame.event_id.tolist()
    for key in ['product_id','product','exchange','u_date','reference_epoch','planned_execution_date','status','direction',
                'family_id','history_state','label_state','label_known_date','evaluation_state']:
        assert actual[key].tolist() == frame[key].tolist(),key
    event_cols = [*FIELDS,'A_width','B_width','paired_width','D_close_R','raw_stop_touch_diagnostic',
                  'raw_profit_touch_diagnostic','feature_ready','label_identified','path_ambiguous','family_group']
    for key in event_cols:compare(numbers(actual[key]),frame[key],'events_'+key)
    assert np.array_equal(numbers(actual.loc[frame.label_identified.eq(1),'new_realized_tail']),
                          frame.loc[frame.label_identified.eq(1),'ind_B_gt4'].to_numpy())
    metrics = json.loads((experiment/'metrics.json').read_text())
    scopes = {'main':frame,'family_0':frame.loc[frame.family_group.eq(0)],'family_1':frame.loc[frame.family_group.eq(1)]}
    scopes['family_combined'] = pd.concat([scopes['family_0'],scopes['family_1']],ignore_index=True)
    assert len(scopes['family_combined']) == len(frame) and not scopes['family_combined'].event_id.duplicated().any()
    independent = {};reports = 0;daily_outputs = 0
    for scope,f in scopes.items():
        independent[scope] = {'annual':{}}
        selectors = [(str(y),f.u_date.str.startswith(str(y)),[d for d in calendar if d.startswith(str(y))]) for y in range(2010,2027)]
        selectors += [(name,f.u_date.ge(start),[d for d in calendar if d>=start])
                      for name,start in [('all_2010','2010-01-01'),('primary_2020','2020-01-01')]]
        for name,mask,dates in selectors:
            selected = f.loc[mask];d = daily_values(selected,dates);reports += 1
            report = {'cohort':cohort(selected),'date_equal_means':{c:finite_mean(d[c]) for c in d},
                      'source_grid_days':len(dates),'no_identified_days':int(d.identified_rows.isna().sum())}
            if name in ['all_2010','primary_2020']:
                saved = pd.read_csv(experiment/f'daily_{scope}_{name}.csv',index_col=0)
                assert saved.index.tolist() == dates
                compare(saved[d.columns].to_numpy(),d.to_numpy(),'all_daily_outputs');daily_outputs += 1
                if scope == 'main':
                    report['bootstrap'] = bootstrap(d)
                    assert metrics['scopes'][scope][name]['bootstrap']['common_indices_sha256'] == report['bootstrap']['common_indices_sha256']
                independent[scope][name] = report
                compare_tree(metrics['scopes'][scope][name],report,'metrics.'+scope+'.'+name)
            else:
                independent[scope]['annual'][name] = report
                compare_tree(metrics['scopes'][scope]['annual'][name],report,'annual.'+scope+'.'+name)
    primary = independent['main']['primary_2020'];all_period = independent['main']['all_2010']
    positive = lambda x:x is not None and np.isfinite(x) and x>0
    ci = primary['bootstrap']['metrics'];means = primary['date_equal_means'];tail = primary['cohort']
    gates = {'primary_B_lower_ci_positive':positive(ci['B_lower']['ci95_lower']),
             'primary_paired_lower_ci_positive':positive(ci['paired_lower']['ci95_lower']),
             'primary_same_mask_cost_1R_B_positive':positive(means['stress_B_lower']),
             'all_2010_B_lower_positive':positive(all_period['date_equal_means']['B_lower']),
             'all_2010_paired_lower_positive':positive(all_period['date_equal_means']['paired_lower']),
             'family_0_primary_paired_lower_positive':positive(independent['family_0']['primary_2020']['date_equal_means']['paired_lower']),
             'family_1_primary_paired_lower_positive':positive(independent['family_1']['primary_2020']['date_equal_means']['paired_lower']),
             'four_complete_years_paired_lower_positive':sum(positive(independent['main']['annual'][str(y)]['date_equal_means']['paired_lower']) for y in range(2020,2026))>=4,
             'partial_2026_B_lower_positive':positive(independent['main']['annual']['2026']['date_equal_means']['B_lower']),
             'primary_realized_tail_dates_ge60':tail['new_realized_tail_dates']>=60,
             'primary_realized_tail_families_ge8':tail['new_realized_tail_families']>=8}
    gates = {key:bool(value) for key,value in gates.items()}
    assert len(gates) == 11 and metrics['gates'] == gates
    assert metrics['uncapped_policy_screen_pass'] == all(gates.values())
    assert all(value is None for value in metrics['financial_metrics'].values())
    receipt = {'schema':'stage030_uncapped_day_independent_review_v1','independent_review':True,
               'status':'accepted_calculations_policy_screen_pass' if all(gates.values()) else 'accepted_calculations_rejected_policy_screen',
               'source_manifest':{'path':str(path),'sha256':args.manifest_sha256,'bytes':len(raw)},
               'source_code_read':manifest['source'],'full_event_rows_checked':len(frame),
               'identified_rows_checked':int(frame.label_identified.sum()),'ready_unknown_rows_preserved':541,
               'observed_audit_rows_checked':212852,'scope_period_reports_checked':reports,'daily_outputs_checked':daily_outputs,
               'primary_2020_date_equal_means':means,'primary_2020_cohort':tail,
               'gates':gates,'uncapped_policy_screen_pass':all(gates.values()),
               'max_abs_numeric_error':max(MAX_ERRORS.values()),'max_abs_daily_error':MAX_ERRORS['all_daily_outputs'],
               'max_abs_event_error':max(v for key,v in MAX_ERRORS.items() if key.startswith('events_')),
               'critical':0,'important':0,'minor':0,'qualified_for_fixed_proxy_policy_calculations':True,
               'real_economic_labels_ready':False,'financial_ready':False,'production_qualified':False,
               'fit_calls':0,'sql_queries':0,'financial_backtests':0,'downloads':0,'author_calculation_imports':0,
               'limitations':['Single-valued B is identified only under the inherited ideal continuous policy, not qualified real execution or cash labels.',
                              'Paired partial-identification bounds and fixed-policy source-day bootstrap uncertainty are separate.',
                              'Family partitions test heterogeneity only; no trained holdout, AI or model information claim.',
                              'Input status repair changed two strings only; first failed attempt produced no policy results.']}
    (OUT/'review_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    end = {'schema':'stage030_actual_terminal_v1','exit_code':0,'started_at':started,
           'finished_at':datetime.now().astimezone().isoformat(timespec='seconds'),'elapsed_seconds':time.monotonic()-began,
           'source_sha256':digest(Path(__file__).read_bytes()),'fit_calls':0,'sql_queries':0,'financial_backtests':0}
    (OUT/'actual_terminal.json').write_text(json.dumps(end,indent=2)+'\n')
    print(json.dumps({'status':receipt['status'],'full_event_rows':len(frame),'reports':reports,'gates_true':sum(gates.values()),
                      'gates_false':11-sum(gates.values()),'max_event_error':receipt['max_abs_event_error'],
                      'max_daily_error':receipt['max_abs_daily_error'],'elapsed_seconds':end['elapsed_seconds']}))


if __name__ == '__main__':
    main()
