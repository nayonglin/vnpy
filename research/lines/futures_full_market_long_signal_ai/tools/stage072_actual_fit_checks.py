"""Independent saved-label/Ridge arithmetic. No model fitting or author imports."""
import io,json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from stage072_actual_cash_adapter import bound,compare,numeric,quote

ID=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']

def table(binding,usecols=None):
    return pd.read_csv(io.BytesIO(bound(binding)),compression='gzip' if binding['path'].endswith('.gz') else None,
                       dtype=str,keep_default_na=False,usecols=usecols)

def label_checks(frames,calendar,economics):
    a,b=frames['WIDE'],frames['NARROW'];lookup={d:i for i,d in enumerate(calendar)}
    for c in ID:assert a[c].tolist()==b[c].tolist(),('label identity',c)
    result={}
    for policy,f in frames.items():
        k=2. if policy=='WIDE' else .25
        assert len(f)==399252 and f.event_id.nunique()==len(f)
        assert f.family_id.eq(f.product_id.str.removesuffix('_F')).all()
        numeric(f,['sequence_index','u_index','D_index','N_u','low20_u','u_close','history_run','lifecycle_index',
                   'entry_index','exit_index','filled','label_history_ready20','R0_points','SL0','entry_reference','exit_reference',
                   'entry_boundary','cash_risk_unit','multiplier','policy_diagnostic_pnl'])
        assert np.array_equal(f.sequence_index,np.arange(len(f)))
        assert np.array_equal(f.u_index,f.u_date.map(lookup)) and np.array_equal(f.D_index,f.u_index+1)
        ready=f.history_run.ge(20)&np.isfinite(f.N_u)&f.N_u.gt(0)&np.isfinite(f.low20_u)&f.low20_u.gt(0)
        assert ready.equals(f.label_history_ready20.eq(1))
        compare(f.loc[ready,'R0_points'],k*f.loc[ready,'N_u'],'label_R0_'+policy)
        closed=f.label_state.eq('closed_complete_bar_model');nonpart=f.label_state.eq('known_nonparticipation')
        assert f.loc[closed,'filled'].eq(1).all()
        assert (f.loc[closed,'label_known_date']==f.loc[closed,'exit_date']).all()
        assert f.loc[~closed,'label_known_date'].eq('').all()
        assert (f.loc[closed,'label_known_date']>f.loc[closed,'u_date']).all()
        assert f.loc[closed,'entry_index'].eq(f.loc[closed,'D_index']).all()
        assert f.loc[closed,'exit_index'].ge(f.loc[closed,'entry_index']).all()
        assert f.loc[closed,'entry_date'].tolist()==[calendar[int(x)] for x in f.loc[closed,'entry_index']]
        assert f.loc[closed,'exit_date'].tolist()==[calendar[int(x)] for x in f.loc[closed,'exit_index']]
        assert f.loc[nonpart,'policy_diagnostic_pnl'].eq(0).all() and f.loc[~nonpart,'policy_diagnostic_pnl'].isna().all()
        present=np.isfinite(f.entry_reference)
        compare(f.loc[present,'SL0'],f.loc[present,'entry_reference']-k*f.loc[present,'N_u'],'label_SL0_'+policy)
        entered=f.filled.eq(1)
        compare(f.loc[entered,'entry_boundary'],np.maximum(f.loc[entered,'SL0'],f.loc[entered,'low20_u']),'label_entry_boundary_'+policy)
        compare(f.loc[closed,'cash_risk_unit'],k*f.loc[closed,'N_u']*f.loc[closed,'multiplier'],'label_risk_'+policy)
        for cost in ['base','stress']:
            cols=[f'net_R_{cost}',f'net_pnl_{cost}_per_lot']+[f'{cost}_{s}' for s in
                 ['entry_fill','exit_fill','entry_fee_per_lot','exit_fee_per_lot','total_fee_per_lot','entry_slippage_per_lot','exit_slippage_per_lot','total_slippage_per_lot']]
            numeric(f,cols)
            assert f.loc[~closed,[f'net_R_{cost}',f'net_pnl_{cost}_per_lot']].isna().all().all()
            z=f.loc[closed]
            net=z.multiplier*(z[f'{cost}_exit_fill']-z[f'{cost}_entry_fill'])-z[f'{cost}_entry_fee_per_lot']-z[f'{cost}_exit_fee_per_lot']
            compare(z[f'net_pnl_{cost}_per_lot'],net,'label_net_CNY_'+policy+cost)
            compare(z[f'net_R_{cost}'],net/(k*z.N_u*z.multiplier),'label_net_R_'+policy+cost)
            if policy=='NARROW':
                numeric(f,[f'net_R_common2N_{cost}'])
                compare(f.loc[closed,f'net_R_common2N_{cost}'],net/(2*z.N_u*z.multiplier),'label_common2N_'+cost)
            # Decimal tick rounding is independently reconstructed, not inferred from saved slippage.
            for side,mask,refcol,prefix in [('BUY',entered,'entry_reference','entry'),('SELL',closed,'exit_reference','exit')]:
                ix=f.index[mask];rows=f.loc[ix,['reference_epoch',refcol]]
                cache={};values=[]
                for epoch,refprice in rows.itertuples(index=False,name=None):
                    key=(epoch,float(refprice));value=cache.get(key)
                    if value is None:value=quote(float(refprice),side,economics[epoch],cost);cache[key]=value
                    values.append(value)
                expected=np.asarray(values)
                for j,suffix in enumerate(['fill','fee_per_lot','slippage_per_lot']):
                    compare(f.loc[ix,f'{cost}_{prefix}_{suffix}'],expected[:,j],'all_label_quotes_'+policy+cost+side+suffix)
        result[policy]={'rows':len(f),'closed':int(closed.sum()),'states':f.label_state.value_counts().to_dict()}
    for c in ['N_u','low20_u','u_close','history_run','lifecycle_index','label_history_ready20']:
        compare(a[c],b[c],'same_causal_u_'+c)
    return result

def weights(train):
    # A training-only occupancy array per family; no test/censored event participates.
    start=train.entry_index.to_numpy(int);end=train.exit_index.to_numpy(int);family=train.family_id.to_numpy()
    u=np.empty(len(train))
    for name in np.unique(family):
        p=np.flatnonzero(family==name);d=np.zeros(int(end[p].max())+2)
        np.add.at(d,start[p],1);np.add.at(d,end[p]+1,-1)
        c=np.cumsum(d);inv=np.zeros_like(c);np.divide(1,c,out=inv,where=c>0)
        cs=np.r_[0,np.cumsum(inv)]
        u[p]=(cs[end[p]+1]-cs[start[p]])/(end[p]-start[p]+1)
    mass=pd.Series(u).groupby(train.u_date.to_numpy()).transform('sum').to_numpy()
    day=u/mass;return u,day,day/day.mean()

def stats(x,w):
    m=np.isfinite(x)
    if not m.any():return 0.,0.,1.
    mean=np.sum(x[m]*w[m])/w[m].sum();var=np.sum(w[m]*(x[m]-mean)**2)/w[m].sum()
    return mean,var,np.sqrt(var) if var>0 else 1.

def check_fits(fit,frames,source_mask_binding,out):
    inputs=fit['input_bindings'];root=Path(fit['predictions']['path']).parent
    raw=np.load(io.BytesIO(bound(inputs['common_npz'])),allow_pickle=False);common=raw['common'];columns=raw['columns'].tolist()
    assert common.shape==(399252,26)
    own_mask=table(source_mask_binding,usecols=['event_id','research_mask_069'])
    observation=pd.read_csv(root/'research_observation_projection.csv.gz',dtype=str,keep_default_na=False)
    assert own_mask.event_id.tolist()==observation.event_id.tolist()==frames['WIDE'].event_id.tolist()
    mask=pd.to_numeric(own_mask.research_mask_069).eq(1).to_numpy()
    assert np.array_equal(pd.to_numeric(observation.research_observed).to_numpy(),mask.astype(int))
    numeric(observation,['q_settlement','q_proxy','external_missing'])
    # Root permits this one four-column projection solely to audit the new071 transformation.
    source=table(inputs['settlement_projection'],usecols=['event_id','C_v','S_v','N_v'])
    assert source.event_id.tolist()==observation.event_id.tolist();numeric(source,['C_v','S_v','N_v'])
    with np.errstate(divide='ignore',invalid='ignore'):q=((source.C_v-source.S_v)/source.N_v).where(mask,np.nan).to_numpy()
    proxy=table(inputs['ohlc_proxy'],usecols=['event_id','H_v','L_v','C_v','N_v','ohlc_proxy_raw','v_date','v_index','reference_epoch'])
    assert proxy.event_id.tolist()==observation.event_id.tolist();numeric(proxy,['H_v','L_v','C_v','N_v','ohlc_proxy_raw'])
    with np.errstate(divide='ignore',invalid='ignore'):p=((proxy.C_v-(proxy.H_v+proxy.L_v+proxy.C_v)/3)/proxy.N_v).where(mask,np.nan).to_numpy()
    compare(observation.q_settlement,q,'071_raw_settlement_scalar',atol=1e-12)
    compare(observation.q_proxy,p,'071_raw_proxy_scalar',atol=1e-12)
    compare(proxy.loc[mask,'ohlc_proxy_raw'],p[mask],'070_raw_proxy_formula',atol=1e-12)
    assert np.array_equal(observation.external_missing.to_numpy(),(~mask).astype(int))
    records=[json.loads(line) for line in (root/'fits.jsonl').read_text().splitlines()]
    assert len(records)==12
    predictions=table(fit['predictions']);numeric(predictions,['sequence_index','u_index','score','selected','history_ready20'])
    assert len(predictions)==966084 and not predictions.duplicated(['policy','arm','event_id']).any()
    result=[]
    for policy in ['WIDE','NARROW']:
        f=frames[policy]
        for cutoff,stop in [('2020-01-01','2023-01-01'),('2023-01-01',None)]:
            mature=f.label_state.eq('closed_complete_bar_model')&f.u_date.lt(cutoff)&f.label_known_date.ne('')&f.label_known_date.lt(cutoff)
            train=f.loc[mature].sort_values(['u_date','event_id']);test=f.loc[f.u_date.ge(cutoff)&(f.u_date.lt(stop) if stop else True)].sort_values(['u_date','event_id'])
            ui,uw,w=weights(train);ti=train.sequence_index.to_numpy(int);pi=test.sequence_index.to_numpy(int)
            cell=root/'cells'/policy/cutoff;scaler=json.loads((cell/'scaler.json').read_text())
            saved=pd.read_csv(cell/'training_identity_weights.csv.gz',dtype=str,keep_default_na=False)
            assert saved.event_id.tolist()==train.event_id.tolist()
            for key,val in [('uniqueness',ui),('u_normalized_weight',uw),('sample_weight',w)]:compare(pd.to_numeric(saved[key]),val,'training_'+policy+cutoff+key,atol=1e-10)
            means=[];variances=[];scales=[]
            for j in range(26):
                m,v,s=stats(common[ti,j],w);means.append(m);variances.append(v);scales.append(s)
            qm,qv,qs=stats(np.r_[q[ti],p[ti]],np.r_[w/2,w/2])
            for key,val in [('mean',means),('var',variances),('scale',scales)]:compare(scaler['common'][key],val,'scaler_common_'+key,atol=1e-10)
            compare([scaler['scalar'][c] for c in ['mean','var','scale']],[qm,qv,qs],'scaler_scalar',atol=1e-10)
            assert scaler['common']['columns']==columns
            def base(ix):
                x=common[ix];miss=~np.isfinite(x)
                return np.column_stack([(np.where(miss,means,x)-means)/scales,miss.astype(float),(~mask[ix]).astype(float)])
            z=np.load(cell/'normalized_inputs.npz',allow_pickle=False)
            compare(z['train_base'],base(ti),'normalized_training_base',atol=1e-10)
            compare(z['prediction_base'],base(pi),'normalized_prediction_base',atol=1e-10)
            compare(z['sample_weight'],w,'normalized_sample_weight',atol=1e-10)
            compare(z['y'],train.net_R_stress,'normalized_own_y',atol=1e-12)
            assert np.array_equal(z['train_sequence_index'],ti) and np.array_equal(z['prediction_sequence_index'],pi)
            for name,values in [('settlement',q),('proxy',p)]:
                for prefix,ix in [('train',ti),('prediction',pi)]:
                    expect=(np.where(np.isfinite(values[ix]),values[ix],qm)-qm)/qs
                    compare(z[prefix+'_'+name],expect,'normalized_scalar_'+name,atol=1e-10)
            for arm in ['COMMON','SETTLEMENT','OHLC_PROXY']:
                model=json.loads((cell/arm/'portable_model.json').read_text());coef=np.asarray(model['coef']);intercept=float(model['intercept'])
                assert len(coef)==54 and model['parameters']=={'alpha':1.,'fit_intercept':True,'solver':'cholesky'}
                tail='settlement' if arm=='SETTLEMENT' else 'proxy'
                x=np.column_stack([z['train_base'],np.zeros(len(ti)) if arm=='COMMON' else z['train_'+tail]])
                xt=np.column_stack([z['prediction_base'],np.zeros(len(pi)) if arm=='COMMON' else z['prediction_'+tail]])
                if arm=='COMMON':assert (x[:,-1]==0).all() and (xt[:,-1]==0).all()
                aug=np.column_stack([x,np.ones(len(x))]);lhs=aug.T@(w[:,None]*aug);lhs[np.arange(54),np.arange(54)]+=1;rhs=aug.T@(w*z['y']);beta=np.r_[coef,intercept]
                ne=np.load(cell/arm/'normal_equations.npz',allow_pickle=False)
                compare(ne['lhs'],lhs,'normal_equation_lhs',atol=2e-7,rtol=2e-11);compare(ne['rhs'],rhs,'normal_equation_rhs',atol=2e-7,rtol=2e-11)
                compare(ne['coefficient_with_intercept'],beta,'portable_coefficients',atol=1e-12)
                residual=float(np.max(abs(lhs@beta-rhs)));assert np.allclose(lhs@beta,rhs,atol=1e-7,rtol=1e-8)
                actual=predictions.loc[predictions.policy.eq(policy)&predictions.arm.eq(arm)&predictions.cutoff.eq(cutoff)]
                assert actual.event_id.tolist()==test.event_id.tolist()
                score=xt@coef+intercept;compare(actual.score,score,'all_portable_predictions',atol=1e-10)
                assert np.array_equal(actual.history_ready20.to_numpy(),test.label_history_ready20.to_numpy())
                assert np.array_equal(actual.selected.to_numpy(),(test.label_history_ready20.eq(1).to_numpy()&(actual.score.to_numpy()>0)).astype(int))
                result.append(dict(policy=policy,cutoff=cutoff,arm=arm,train=len(train),predict=len(test),normal_equation_max_residual=residual))
    assert predictions.groupby(['policy','arm']).size().eq(161014).all()
    return predictions,{'models':result,'predictions_checked':len(predictions),'accepted_mask_rows':int(mask.sum()),'source_four_column_reads':1}
