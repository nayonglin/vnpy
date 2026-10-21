"""Stage069 frozen 12-Ridge fit. Zero SQL; exact root authorization precedes actual I/O.

The source projection remains values-only (training_accepted=feature_available=0).
A separately bound root receipt permits only this historical reconstruction mask.
No model/threshold search, old-feature rebuild, cash replay, or native data access.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import sys
import time

for _key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS',
             'VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[_key] = '1'

import joblib
import numpy as np
import pandas as pd
import scipy
import sklearn
from sklearn.linear_model import Ridge
from threadpoolctl import threadpool_limits

LINE = Path(__file__).resolve().parents[1]
STAGE_ROOT = LINE / 'outputs/stage071_settlement_narrow_fit'
PROTOCOL = LINE / 'outputs/stage069_settlement_narrow_joint_protocol/protocol.json'
PROTOCOL_SHA = '0418566cd9b624fb5a985448b3b0d4c94dbef56280feffd49bce09e1c5bf2dde'
COMMON_SHA = 'e3174cf1d2067611e6a2538d25aafee17772adcd1889a68408d727fdc4fc1fd3'
SOURCE_SCRIPT_SHA = 'dacbb8d58e42f98c003d83c5a673a9bc651d645f092e17bd02e1dcdecb49f048'
SOURCE_PROTOCOL_SHA = 'aa5dd80908bc21a06731761ac4539f2acfb86091061d2fa761592652dde9553a'
COMMON = ['r1_atr','r5_atr','r20_atr','body_atr','range_atr','close_location',
    'gap_atr','compression5_20','log_volume_ratio20','breakout20_atr','atr_pct',
    'normalizer','peer_count','tenor_span_years','return_mean','return_std',
    'return_min','return_max','front_next_basis_u','front_next_basis_prev',
    'front_next_tenor_span_years','q_missing','front_next_missing','normalizer_missing',
    'stress_u_cost_R','low20_distance_R']
FEATURE_NAMES = COMMON + [c+'_missing' for c in COMMON] + ['external_missing','scalar']
IDENTITY = ['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
LABEL_COLUMNS = IDENTITY + ['entry_index','exit_index','entry_date','exit_date',
    'label_known_date','label_state','net_R_stress','label_history_ready20']
SOURCE_COLUMNS = IDENTITY + ['v_index','v_date','projection_state','value_observed',
    'N_state','ohlc_relation','lifecycle_state','benchmark_family','rule_state',
    'rule_primary_bound','training_accepted','feature_available','strict_pit_accepted',
    'candidate_quote_epoch','candidate_quote_date','accepted_C_v','C_v','S_v','N_v']
PROXY_COLUMNS = IDENTITY + ['v_index','v_date','H_v','L_v','C_v','N_v',
    'ohlc_proxy_raw','proxy_state','N_state']
RULE_STATES = ('historical_family_reconstruction_not_full_vintage',
    'family_default_assumption_no_primary_rule_bound')
ARMS = ('COMMON','SETTLEMENT','OHLC_PROXY')
POLICIES = ('WIDE','NARROW')
CUTOFFS = ('2020-01-01','2023-01-01')
PARAMETERS = dict(alpha=1.,fit_intercept=True,solver='cholesky')
INPUT_ROLES = {'wide_labels','common_npz','common_identity','settlement_manifest',
    'settlement_projection','settlement_terminal','source_acceptance','narrow_labels',
    'ohlc_proxy','narrow_manifest'}


def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def file_binding(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    return dict(path=str(path),bytes=path.stat().st_size,sha256=digest.hexdigest())


def read_bound(binding):
    raw = Path(binding['path']).read_bytes()
    if len(raw) != binding['bytes'] or sha_bytes(raw) != binding['sha256']:
        raise ValueError('input binding mismatch: '+binding['path'])
    return raw


def same_binding(left, right):
    return all(left.get(k) == right.get(k) for k in ('path','bytes','sha256'))


def write_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())


def write_csv(path, frame):
    if Path(path).exists():
        raise FileExistsError(str(path))
    frame.to_csv(path,index=False,compression={'method':'gzip','mtime':0},float_format='%.17g')
    return file_binding(path)


def write_npz(path, **arrays):
    with Path(path).open('xb') as stream:
        np.savez_compressed(stream,**arrays)
    return file_binding(path)


def authorize(path, sha, output, source_bundle, required_roles=INPUT_ROLES):
    """Bind code, fixed science, all accepted input bytes, and an unused output."""
    if Path(output).exists():
        raise FileExistsError('fresh output required: '+str(output))
    binding = file_binding(path)
    if binding['sha256'] != sha:
        raise ValueError('authorization SHA mismatch')
    auth = json.loads(read_bound(binding))
    if (auth.get('schema') != 'stage069_exact_root_authorization_v1'
            or auth.get('authorized_by') != 'root' or auth.get('stage') != 'fit'
            or auth.get('exact_source_authorized') is not True):
        raise ValueError('exact root fit authorization required')
    if auth.get('protocol_sha256') != PROTOCOL_SHA:
        raise ValueError('authorization protocol mismatch')
    if auth.get('output') != str(Path(output).resolve()):
        raise ValueError('authorization output mismatch')
    supplied = auth.get('source_bundle',[])
    actual_by_path = {b['path']:b for b in source_bundle}
    if len(supplied) != len(actual_by_path) or {b.get('path') for b in supplied} != set(actual_by_path):
        raise ValueError('authorization source bundle differs')
    for b in supplied:
        if not same_binding(b,actual_by_path[b['path']]):
            raise ValueError('authorization exact source mismatch')
    inputs = auth.get('input_bindings',{})
    if set(inputs) != set(required_roles):
        raise ValueError('authorization input roles differ')
    for b in inputs.values():
        read_bound(b)
    return auth


def training_slice(frame, cutoff):
    use = (frame.u_date.lt(cutoff) & frame.label_known_date.ne('')
        & frame.label_known_date.lt(cutoff) & frame.label_state.eq('closed_complete_bar_model'))
    train = frame.loc[use].sort_values(['u_date','event_id']).copy()
    if train.empty or not np.isfinite(train.net_R_stress.to_numpy(float)).all():
        raise ValueError('empty/nonfinite own-policy mature training target')
    return train


def prediction_slice(frame, cutoff, next_cutoff=None):
    use = frame.u_date.ge(cutoff)
    if next_cutoff is not None:
        use &= frame.u_date.lt(next_cutoff)
    return frame.loc[use].sort_values(['u_date','event_id']).copy()


def training_weights(train):
    """Only own-policy mature rows; family inclusive concurrency then equal u mass."""
    if train.empty:
        raise ValueError('empty mature training')
    starts, ends = train.entry_index.to_numpy(float),train.exit_index.to_numpy(float)
    if (not np.isfinite(starts).all() or not np.isfinite(ends).all()
            or (starts < 0).any() or (ends < starts).any()
            or not np.equal(starts,np.floor(starts)).all()
            or not np.equal(ends,np.floor(ends)).all()):
        raise ValueError('invalid own-policy closed interval')
    starts,ends = starts.astype(np.int64),ends.astype(np.int64)
    family = train.family_id.to_numpy()
    uniqueness = np.empty(len(train),dtype=float)
    for name in pd.unique(family):
        pos = np.flatnonzero(family == name);a,b = starts[pos],ends[pos]
        delta = np.zeros(int(b.max())+2,dtype=np.int64)
        np.add.at(delta,a,1);np.add.at(delta,b+1,-1)
        concurrency = np.cumsum(delta)[:-1]
        inverse = np.divide(1.,concurrency,out=np.zeros_like(concurrency,dtype=float),where=concurrency>0)
        cumulative = np.r_[0.,np.cumsum(inverse)]
        uniqueness[pos] = (cumulative[b+1]-cumulative[a])/(b-a+1)
    totals = pd.Series(uniqueness).groupby(train.u_date.to_numpy()).transform('sum').to_numpy()
    date_weight = uniqueness/totals
    weights = date_weight/date_weight.mean()
    if not np.isfinite(weights).all() or (weights<=0).any():
        raise ValueError('invalid training weights')
    return pd.DataFrame(dict(uniqueness=uniqueness,u_normalized_weight=date_weight,
        sample_weight=weights),index=train.index)


def finite_stats(values, weights):
    x,w = np.asarray(values,float),np.asarray(weights,float)
    finite = np.isfinite(x)
    if not finite.any():
        return dict(mean=0.,var=0.,scale=1.,finite_count=0)
    mean = float(np.average(x[finite],weights=w[finite]))
    var = float(np.average((x[finite]-mean)**2,weights=w[finite]))
    return dict(mean=mean,var=var,scale=math.sqrt(var) if var>0 else 1.,finite_count=int(finite.sum()))


def fit_scalers(common, settlement, proxy, weights):
    x,q,p,w = np.asarray(common,float),np.asarray(settlement,float),np.asarray(proxy,float),np.asarray(weights,float)
    if x.shape != (len(w),26) or q.shape != w.shape or p.shape != w.shape or not len(w):
        raise ValueError('invalid scaler shapes')
    if not np.isfinite(w).all() or (w<=0).any():
        raise ValueError('invalid scaler weights')
    if not np.array_equal(np.isfinite(q),np.isfinite(p)):
        raise ValueError('information scalars must have shared missing mask')
    stats = [finite_stats(x[:,j],w) for j in range(26)]
    scalar = finite_stats(np.r_[q,p],np.r_[w*.5,w*.5])
    return dict(common=dict(columns=COMMON,**{k:[s[k] for s in stats] for k in ('mean','var','scale','finite_count')}),
        scalar=scalar,feature_names=FEATURE_NAMES,common_units='accepted_original_2N_for_both_policies',
        weighting='own_mature_training_only; finite_population; settlement/proxy each half weight',
        missing='common training mean imputation; scalar missing standardized zero; unscaled indicators')


def design_base(common, observed, scaler):
    x,observed = np.asarray(common,float),np.asarray(observed,bool)
    if x.shape != (len(observed),26):
        raise ValueError('invalid common/mask shape')
    missing = ~np.isfinite(x)
    mean,scale = np.asarray(scaler['common']['mean']),np.asarray(scaler['common']['scale'])
    z = (np.where(missing,mean,x)-mean)/scale
    base = np.column_stack([z,missing.astype(float),(~observed).astype(float)])
    if base.shape != (len(x),53) or not np.isfinite(base).all():
        raise ValueError('nonfinite common53 design')
    return base


def scalar_projection(values, scaler):
    q = np.asarray(values,float);s = scaler['scalar']
    return (np.where(np.isfinite(q),q,s['mean'])-s['mean'])/s['scale']


def design_matrix(base, values, arm, scaler):
    if arm not in ARMS:
        raise ValueError('unknown information arm')
    q = np.zeros(len(base)) if arm=='COMMON' else scalar_projection(values,scaler)
    result = np.column_stack([base,q])
    if result.shape != (len(base),54) or not np.isfinite(result).all():
        raise ValueError('nonfinite or non54 design')
    return result


def prediction_frame(frame, scores, policy, arm, cutoff):
    score = np.asarray(scores,float)
    if score.shape != (len(frame),) or not np.isfinite(score).all():
        raise ValueError('nonfinite/invalid prediction scores')
    result = frame[IDENTITY].copy()
    result['policy'],result['arm'],result['cutoff'] = policy,arm,cutoff
    result['history_ready20'] = frame.label_history_ready20.to_numpy(np.int8)
    result['selected'] = (result.history_ready20.eq(1).to_numpy() & (score>0)).astype(np.int8)
    result['score'] = score
    return result


def _identity(left, right, keys=IDENTITY):
    if not set(keys).issubset(left) or not set(keys).issubset(right):
        raise ValueError('mother identity columns missing')
    if len(left)!=len(right):
        raise ValueError('mother identity row count differs')
    for col in keys:
        if not np.array_equal(left[col].astype(str).to_numpy(),right[col].astype(str).to_numpy()):
            raise ValueError('mother identity differs: '+col)


def _numeric(frame, columns):
    for col in columns:
        frame[col] = pd.to_numeric(frame[col].replace('',np.nan),errors='raise')
    return frame


def observation_projection(mother, source, proxy):
    """Research mask, derived from exact same-v provenance; never uses labels/Y."""
    _identity(mother,source)
    _identity(mother,proxy)
    source,proxy = source.copy(),proxy.copy()
    _numeric(source,['v_index','value_observed','training_accepted','feature_available',
        'strict_pit_accepted','accepted_C_v','C_v','S_v','N_v'])
    _numeric(proxy,['v_index','H_v','L_v','C_v','N_v','ohlc_proxy_raw'])
    if not source[['training_accepted','feature_available','strict_pit_accepted']].eq(0).all().all():
        raise ValueError('source acceptance flags must remain zero')
    finite_positive = lambda f,cols: np.isfinite(f[cols].to_numpy(float)).all(axis=1) & (f[cols].to_numpy(float)>0).all(axis=1)
    use = (source.projection_state.eq('observed_historical_reconstruction') & source.value_observed.eq(1)
        & source.N_state.eq('N_v_ready20') & source.ohlc_relation.eq('equal_with_fixed_absolute_tolerance_1e-8')
        & source.lifecycle_state.eq('before_vendor_final_boundary') & source.benchmark_family.ne('unknown')
        & source.benchmark_family.ne('') & source.rule_state.isin(RULE_STATES)
        & source.candidate_quote_epoch.eq(mother.reference_epoch) & mother.reference_epoch.ne('')
        & source.candidate_quote_date.eq(source.v_date) & source.v_date.ne('') & source.v_date.lt(mother.u_date)
        & source.v_index.eq(mother.u_index.to_numpy(int)-1)
        & proxy.v_index.eq(source.v_index) & proxy.v_date.eq(source.v_date)
        & proxy.proxy_state.eq('valid_same_epoch_previous_source_day') & proxy.N_state.eq('N_v_ready20')
        & finite_positive(source,['accepted_C_v','C_v','S_v','N_v'])
        & finite_positive(proxy,['H_v','L_v','C_v','N_v'])
        & source.C_v.sub(source.accepted_C_v).abs().le(1e-8)
        & source.C_v.sub(proxy.C_v).abs().le(1e-8) & source.N_v.sub(proxy.N_v).abs().le(1e-8)
        & proxy.H_v.ge(proxy.L_v) & source.S_v.ge(proxy.L_v-1e-8) & source.S_v.le(proxy.H_v+1e-8)
        & proxy.C_v.ge(proxy.L_v-1e-8) & proxy.C_v.le(proxy.H_v+1e-8))
    with np.errstate(divide='ignore',invalid='ignore'):
        q = (source.C_v-source.S_v)/source.N_v
        p = (proxy.C_v-(proxy.H_v+proxy.L_v+proxy.C_v)/3)/proxy.N_v
    use &= np.isfinite(q) & np.isfinite(p) & np.isfinite(proxy.ohlc_proxy_raw)
    use &= np.isclose(p,proxy.ohlc_proxy_raw,rtol=1e-12,atol=1e-12,equal_nan=False)
    result = mother[IDENTITY].copy()
    result['research_observed'] = use.astype(np.int8)
    result['external_missing'] = (~use).astype(np.int8)
    result['q_settlement'],result['q_proxy'] = q.where(use,np.nan),p.where(use,np.nan)
    for col in ('projection_state','N_state','rule_state','benchmark_family','lifecycle_state','v_date','v_index'):
        result[col] = source[col].to_numpy()
    result['proxy_state'] = proxy.proxy_state.to_numpy()
    return result


def fit_cell(frame, common, observation, policy, cutoff, next_cutoff, directory, on_fit=None):
    """Three fits sharing one persisted training/prediction normalization projection."""
    directory = Path(directory);directory.mkdir(parents=True,exist_ok=False)
    train,test = training_slice(frame,cutoff),prediction_slice(frame,cutoff,next_cutoff)
    if test.empty:
        raise ValueError('empty forward block')
    ti,pi = train.sequence_index.to_numpy(int),test.sequence_index.to_numpy(int)
    q,p = observation.q_settlement.to_numpy(float),observation.q_proxy.to_numpy(float)
    observed = observation.research_observed.to_numpy(bool)
    weights = training_weights(train);w = weights.sample_weight.to_numpy(float)
    scaler = fit_scalers(common[ti],q[ti],p[ti],w)
    write_json(directory/'scaler.json',scaler)
    train_base = design_base(common[ti],observed[ti],scaler)
    test_base = design_base(common[pi],observed[pi],scaler)
    train_q,train_p = scalar_projection(q[ti],scaler),scalar_projection(p[ti],scaler)
    test_q,test_p = scalar_projection(q[pi],scaler),scalar_projection(p[pi],scaler)
    y = train.net_R_stress.to_numpy(float)
    normalized_binding = write_npz(directory/'normalized_inputs.npz',train_base=train_base,
        prediction_base=test_base,train_settlement=train_q,train_proxy=train_p,
        prediction_settlement=test_q,prediction_proxy=test_p,y=y,sample_weight=w,
        train_sequence_index=ti,prediction_sequence_index=pi)
    training = train[LABEL_COLUMNS].copy()
    for col in weights:
        training[col] = weights[col].to_numpy()
    training_binding = write_csv(directory/'training_identity_weights.csv.gz',training)
    prediction_binding = write_csv(directory/'prediction_identity.csv.gz',test[IDENTITY+['label_history_ready20']])
    identity_sha = sha_bytes(('\n'.join(train.event_id)+'\n').encode())
    results,records = [],[]
    for arm in ARMS:
        arm_dir = directory/arm;arm_dir.mkdir()
        x = np.column_stack([train_base,np.zeros(len(train)) if arm=='COMMON' else train_q if arm=='SETTLEMENT' else train_p])
        xt = np.column_stack([test_base,np.zeros(len(test)) if arm=='COMMON' else test_q if arm=='SETTLEMENT' else test_p])
        estimator = Ridge(**PARAMETERS)
        if on_fit is not None:
            on_fit(policy,cutoff,arm)
        with threadpool_limits(limits=1):
            estimator.fit(x,y,sample_weight=w)
        score = estimator.predict(xt)
        portable = dict(schema='stage071_portable_ridge_v1',policy=policy,arm=arm,cutoff=cutoff,
            parameters=PARAMETERS,feature_names=FEATURE_NAMES,coef=estimator.coef_.tolist(),intercept=float(estimator.intercept_))
        write_json(arm_dir/'portable_model.json',portable)
        with (arm_dir/'model.joblib').open('xb') as stream:
            joblib.dump(estimator,stream,compress=3)
        z = np.column_stack([x,np.ones(len(x))])
        lhs = z.T@(w[:,None]*z);lhs[np.arange(54),np.arange(54)] += 1.
        rhs = z.T@(w*y)
        beta = np.r_[estimator.coef_,estimator.intercept_]
        residual = float(np.max(np.abs(lhs@beta-rhs)))
        if not np.allclose(lhs@beta,rhs,rtol=1e-8,atol=1e-7):
            raise ValueError('normal equation residual exceeds tolerance')
        ne = write_npz(arm_dir/'normal_equations.npz',lhs=lhs,rhs=rhs,
            coefficient_with_intercept=beta,weight_sum=np.array(w.sum()))
        if not np.allclose(score,xt@np.asarray(portable['coef'])+portable['intercept'],rtol=1e-12,atol=1e-12):
            raise ValueError('portable scores differ')
        predictions = prediction_frame(test,score,policy,arm,cutoff)
        results.append(predictions)
        records.append(dict(policy=policy,arm=arm,cutoff=cutoff,training_rows=len(train),prediction_rows=len(test),
            training_dates=int(train.u_date.nunique()),training_identity_sha256=identity_sha,
            max_u_date=str(train.u_date.max()),max_label_known_date=str(train.label_known_date.max()),
            training_identity_weights=training_binding,prediction_identity=prediction_binding,
            normalized_inputs=normalized_binding,scaler=file_binding(directory/'scaler.json'),
            model=file_binding(arm_dir/'model.joblib'),portable_model=file_binding(arm_dir/'portable_model.json'),
            normal_equations=ne,normal_equation_max_abs_residual=residual,target='own_policy_net_R_stress',
            selected=int(predictions.selected.sum()),dimension=54,common_scalar_strict_zero=True))
    return pd.concat(results,ignore_index=True),records


def _csv(binding, columns):
    return pd.read_csv(io.BytesIO(read_bound(binding)),compression='gzip' if binding['path'].endswith('.gz') else None,
        usecols=columns,dtype=str,keep_default_na=False)


def validate_labels(frame, policy):
    if len(frame)!=399252 or frame.event_id.duplicated().any():
        raise ValueError('complete399252 mother differs: '+policy)
    _numeric(frame,['sequence_index','u_index','entry_index','exit_index','net_R_stress','label_history_ready20'])
    for col in ('sequence_index','u_index'):
        values = frame[col].to_numpy(float)
        if not np.isfinite(values).all() or not np.equal(values,np.floor(values)).all():
            raise ValueError('noninteger source identity')
        frame[col] = values.astype(np.int64)
    if not np.array_equal(frame.sequence_index,np.arange(399252)):
        raise ValueError('original mother sequence order differs')
    if (not frame.label_history_ready20.isin([0,1]).all()
            or not frame.family_id.eq(frame.product_id.str.removesuffix('_F')).all()
            or frame.duplicated(['product_id','u_date']).any()
            or frame.product_id.nunique()!=98 or frame.product_id.str.split('.').str[0].nunique()!=6
            or int(frame.u_date.ge(CUTOFFS[0]).sum())!=161014):
        raise ValueError('mother universe/ready/family changed')
    closed = frame.label_state.eq('closed_complete_bar_model')
    if (not np.isfinite(frame.loc[closed,'net_R_stress']).all()
            or frame.loc[~closed,'net_R_stress'].notna().any()
            or not frame.loc[closed,'label_known_date'].gt(frame.loc[closed,'u_date']).all()
            or not frame.loc[closed,'label_known_date'].eq(frame.loc[closed,'exit_date']).all()):
        raise ValueError('own-policy closed/null/maturity contract differs')
    if policy=='WIDE' and int(closed.sum())!=180507:
        raise ValueError('accepted049 wide closed count differs')
    frame['label_history_ready20'] = frame.label_history_ready20.astype(np.int8)
    return frame


def validate_source_acceptance(inputs, source, terminal):
    if source.get('script_sha256') != SOURCE_SCRIPT_SHA or source.get('model_fits')!=0 or source.get('cash_replays')!=0:
        raise ValueError('067 completed source manifest differs')
    artifact_map = {a['path']:a for a in source['artifacts']}
    for role in ('settlement_projection','settlement_terminal'):
        binding = inputs[role]
        if binding['path'] not in artifact_map or not same_binding(binding,artifact_map[binding['path']]):
            raise ValueError('067 artifact binding differs: '+role)
    protocol_artifacts = [a for a in source['artifacts'] if Path(a['path']).name=='protocol.json']
    if len(protocol_artifacts)!=1 or protocol_artifacts[0]['sha256']!=SOURCE_PROTOCOL_SHA:
        raise ValueError('067 source protocol differs')
    if (terminal.get('completed') is not True or terminal.get('native_source_queries')!=1
            or terminal.get('model_fits')!=0 or terminal.get('cash_replays')!=0):
        raise ValueError('067 source terminal not complete')
    receipt = json.loads(read_bound(inputs['source_acceptance']))
    if (receipt.get('schema')!='stage069_settlement_source_acceptance_v1'
            or receipt.get('status')!='accepted_for_fixed_research_reconstruction'
            or receipt.get('training_accepted_in_source_unchanged') is not True
            or receipt.get('protocol_sha256')!=PROTOCOL_SHA
            or receipt.get('rule_assumption')!='historical_reconstruction_one_source_day_lag_not_release_verified'
            or set(receipt.get('accepted_rule_states',[]))!=set(RULE_STATES)):
        raise ValueError('root historical source acceptance differs')
    for key,role in (('source_manifest','settlement_manifest'),('source_projection','settlement_projection'),('source_terminal','settlement_terminal')):
        if not same_binding(receipt.get(key,{}),inputs[role]):
            raise ValueError('source acceptance exact binding differs: '+key)
    return receipt


def load_inputs(inputs):
    source = json.loads(read_bound(inputs['settlement_manifest']))
    terminal = json.loads(read_bound(inputs['settlement_terminal']))
    acceptance = validate_source_acceptance(inputs,source,terminal)
    narrow_manifest = json.loads(read_bound(inputs['narrow_manifest']))
    if (narrow_manifest.get('schema')!='stage070_narrow_labels_v1'
            or narrow_manifest.get('status')!='completed' or narrow_manifest.get('mode')!='actual'
            or narrow_manifest.get('protocol',{}).get('sha256')!=PROTOCOL_SHA
            or narrow_manifest.get('native_source_queries')!=1
            or narrow_manifest.get('actual_model_fit_calls')!=0):
        raise ValueError('070 narrow labels not completed under frozen protocol')
    for role,manifest_key in (('narrow_labels','labels_narrow'),('ohlc_proxy','ohlc_proxy')):
        if not same_binding(inputs[role],narrow_manifest.get(manifest_key,{})):
            raise ValueError('070 narrow artifact binding differs')
    wide = validate_labels(_csv(inputs['wide_labels'],LABEL_COLUMNS),'WIDE')
    narrow = validate_labels(_csv(inputs['narrow_labels'],LABEL_COLUMNS),'NARROW')
    _identity(wide,narrow)
    if not wide.label_history_ready20.equals(narrow.label_history_ready20):
        raise ValueError('policy readiness identity differs')
    identity = json.loads(read_bound(inputs['common_identity']))
    if (identity.get('rows')!=399252 or identity.get('columns')!=COMMON
            or identity.get('event_ids_sha256')!=sha_bytes(('\n'.join(wide.event_id)+'\n').encode())
            or not same_binding(identity.get('common',{}),inputs['common_npz'])
            or inputs['common_npz']['sha256']!=COMMON_SHA or inputs['common_npz']['bytes']!=28214904):
        raise ValueError('accepted053 common original identity differs')
    with np.load(io.BytesIO(read_bound(inputs['common_npz'])),allow_pickle=False) as prepared:
        if prepared['columns'].tolist()!=COMMON or prepared['common'].shape!=(399252,26):
            raise ValueError('common26 original schema differs')
        common = prepared['common'].astype(np.float64)
    source_frame = _csv(inputs['settlement_projection'],SOURCE_COLUMNS)
    proxy = _csv(inputs['ohlc_proxy'],PROXY_COLUMNS)
    # Source/070 serialized integers are normalized before exact identity checking.
    _numeric(source_frame,['sequence_index','u_index','v_index'])
    _numeric(proxy,['sequence_index','u_index','v_index'])
    for frame in (source_frame,proxy):
        for col in ('sequence_index','u_index'):
            if not np.isfinite(frame[col]).all() or not np.equal(frame[col],np.floor(frame[col])).all():
                raise ValueError('noninteger source projection identity')
            frame[col]=frame[col].astype(np.int64)
    observation = observation_projection(wide,source_frame,proxy)
    expected_rows=acceptance.get('research_mask_rows',acceptance.get('accepted_rows'))
    if expected_rows is not None and int(observation.research_observed.sum())!=expected_rows:
        raise ValueError('source accepted mask row count differs')
    if ('research_mask_2020plus_rows' in acceptance
            and int(observation.loc[observation.u_date.ge(CUTOFFS[0]),'research_observed'].sum())!=acceptance['research_mask_2020plus_rows']):
        raise ValueError('source forward accepted mask row count differs')
    if ('research_mask_zero_scalar_rows' in acceptance
            and int(observation.q_settlement.eq(0).sum())!=acceptance['research_mask_zero_scalar_rows']):
        raise ValueError('source legitimate zero scalar count differs')
    if 'mask_sha256' in acceptance:
        masksha=sha_bytes(observation.research_observed.to_numpy(np.uint8).tobytes())
        if masksha!=acceptance['mask_sha256']:
            raise ValueError('source accepted mask SHA differs')
    return {'WIDE':wide,'NARROW':narrow},common,observation


def run_actual(output, auth, protocol, source_bundle):
    """Once only; caller has verified authorization. Failed directories are retained."""
    output = Path(output);output.mkdir(parents=True,exist_ok=False)
    started = time.monotonic()
    counts = dict(native_source_queries=0,model_fits_attempted=0,model_fits_completed=0,cash_replays=0,
        downloads=0,labels_built=0,whole_db_or_h5_hashes=0)
    write_json(output/'actual_started.json',dict(started_at=datetime.now(timezone.utc).isoformat(),**counts))
    write_json(output/'protocol.json',protocol)
    write_json(output/'input_bindings.json',auth['input_bindings'])
    def on_fit(policy,cutoff,arm):
        counts['model_fits_attempted']+=1
        with (output/'fit_attempts.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(policy=policy,cutoff=cutoff,arm=arm,attempt=counts['model_fits_attempted']))+'\n')
            stream.flush();os.fsync(stream.fileno())
    try:
        frames,common,observation=load_inputs(auth['input_bindings'])
        write_csv(output/'research_observation_projection.csv.gz',observation)
        coverage = observation.assign(exchange=observation.product_id.str.split('.').str[0],year=observation.u_date.str[:4])
        coverage = coverage.groupby(['exchange','year','rule_state'],dropna=False).agg(mother_rows=('event_id','size'),observed=('research_observed','sum')).reset_index()
        write_csv(output/'observation_coverage.csv.gz',coverage)
        all_predictions,records=[],[]
        for policy in POLICIES:
            for k,cutoff in enumerate(CUTOFFS):
                prediction,cell_records = fit_cell(frames[policy],common,observation,policy,cutoff,
                    CUTOFFS[k+1] if k+1<len(CUTOFFS) else None,output/'cells'/policy/cutoff,on_fit)
                counts['model_fits_completed']+=len(cell_records)
                all_predictions.append(prediction);records.extend(cell_records)
                with (output/'fits.jsonl').open('a') as stream:
                    for record in cell_records:stream.write(json.dumps(record,allow_nan=False,sort_keys=True)+'\n')
                    stream.flush();os.fsync(stream.fileno())
        predictions=pd.concat(all_predictions,ignore_index=True)
        if counts['model_fits_attempted']!=12 or counts['model_fits_completed']!=12 or len(predictions)!=966084:
            raise ValueError('fixed 12 fit / 966084 score budget differs')
        group=predictions.groupby(['policy','arm'])
        if not group.size().eq(161014).all() or len(group)!=6 or predictions.duplicated(['policy','arm','event_id']).any():
            raise ValueError('disjoint complete forward mother prediction identity failed')
        prediction_binding=write_csv(output/'predictions.csv.gz',predictions)
        summary=dict(schema='stage071_settlement_narrow_fit_summary_v1',completed=True,
            predictions=len(predictions),predictions_per_arm_policy=161014,
            fits=12,source_training_flags_modified=False,strict_pit_claim=False,
            target='own_policy_net_R_stress',source_observed_rows=int(observation.research_observed.sum()),
            policy_support={p:dict(mother_rows=len(f),label_states=f.label_state.value_counts().to_dict()) for p,f in frames.items()},
            prediction_activity=predictions.groupby(['policy','arm','cutoff']).agg(rows=('event_id','size'),selected=('selected','sum')).reset_index().to_dict('records'),
            runtime=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__,sklearn=sklearn.__version__,joblib=joblib.__version__))
        write_json(output/'summary.json',summary)
        write_json(output/'actual_terminal.json',dict(status='completed',completed=True,exit_code=0,new_cash_accounts=0,
            actual_fit_calls_completed=counts['model_fits_completed'],elapsed_seconds=time.monotonic()-started,**counts))
        artifacts={str(p.relative_to(output)):file_binding(p) for p in sorted(output.rglob('*')) if p.is_file()}
        manifest=dict(schema='stage071_settlement_narrow_fit_v1',status='completed',mode='actual',completed=True,
            protocol=file_binding(output/'protocol.json'),protocol_sha256=PROTOCOL_SHA,terminal=file_binding(output/'actual_terminal.json'),
            predictions=prediction_binding,source_bundle=source_bundle,input_bindings=auth['input_bindings'],artifacts=artifacts,
            actual_fit_calls_completed=12,model_fits=12,cash_replays=0,native_source_queries=0,prediction_rows=966084)
        write_json(output/'manifest.json',manifest)
        return manifest
    except BaseException as error:
        if not (output/'actual_terminal.json').exists():
            write_json(output/'actual_terminal.json',dict(status='failed',completed=False,exit_code=1,new_cash_accounts=0,
                actual_fit_calls_completed=counts['model_fits_completed'],error_type=type(error).__name__,
                error=str(error),elapsed_seconds=time.monotonic()-started,**counts))
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--protocol-sha256',required=True)
    parser.add_argument('--authorization',type=Path,required=True)
    parser.add_argument('--authorization-sha256',required=True)
    args=parser.parse_args(argv)
    if args.protocol_sha256!=PROTOCOL_SHA or file_binding(PROTOCOL)['sha256']!=PROTOCOL_SHA:
        raise ValueError('exact frozen069 protocol SHA required')
    output=args.output.resolve()
    if STAGE_ROOT.resolve() not in output.parents:
        raise ValueError('output must be inside stage071 research root')
    if sklearn.__version__!='1.6.1':
        raise ValueError('accepted sklearn1.6.1 runtime required')
    bundle=[file_binding(__file__),file_binding(Path(__file__).with_name('test_stage071_settlement_narrow_fit.py'))]
    auth=authorize(args.authorization,args.authorization_sha256,output,bundle)
    run_actual(output,auth,json.loads(PROTOCOL.read_text()),bundle)
    print(json.dumps(dict(completed=True,output=str(output),model_fits=12,native_source_queries=0,cash_replays=0)))


if __name__=='__main__':
    main()
