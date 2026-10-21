"""Independent bounded Stage034 context review; no SQL or author imports."""
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd

ROOT=Path('/Users/mac/Desktop/fian');LINE=ROOT/'research/lines/futures_full_market_long_signal_ai'
OUT=LINE/'outputs/stage037_peer_alignment_review'
MANIFEST=LINE/'outputs/stage034_peer_alignment_dataset/export/manifest.json'
EXPECTED='2a3abe55eabf0fba5bb5d749fb4343d1bf341e3d217b93619554ab11bf98d990'
SCOPES=['main','holdout_0','holdout_1']
MARKET=['market_lag_median_r1','market_lag_breadth','market_lag_iqr_r1','market_lag_missing']

def sha(raw):return hashlib.sha256(raw).hexdigest()
def bound(item):
    raw=Path(item['path']).read_bytes();assert sha(raw)==item['sha256'];assert len(raw)==item['bytes'];return raw
def group(f):return int(sha(f.encode()),16)%2

def reference(panel,calendar,u,own,held):
    k=calendar.index(u);shock=panel.iloc[k-1] if k else panel.iloc[0]*np.nan
    peers=[p for p in panel if p!=own and (held is None or group(p)!=held) and np.isfinite(shock[p])]
    market=shock[peers].to_numpy()
    if len(market):
        quant=np.quantile(market,[.25,.5,.75],method='linear')
        out=[quant[1],np.mean(market>0),quant[2]-quant[0],0.,0.,0.,1.,0.,0.]
    else:out=[0.,0.,0.,1.,0.,0.,1.,0.,0.]
    if k<21:return np.array(out)
    history=panel.iloc[k-21:k-1];x=history[own].to_numpy()
    if not np.isfinite(x).all() or np.sum((x-x.mean())**2)==0:return np.array(out)
    names=[];rho=[]
    for p in sorted(peers):
        y=history[p].to_numpy()
        if not np.isfinite(y).all() or np.sum((y-y.mean())**2)==0:continue
        r=float(np.corrcoef(x,y)[0,1]);assert abs(r)<=1+1e-12
        names.append(p);rho.append(np.clip(r,-1.,1.))
    out[4]=len(names);z=sum(abs(r) for r in rho);out[5]=z
    if z:
        ordered=sorted(names,key=lambda p:(sha(('stage032-peer-alignment-null-v1|'+u+'|'+own+'|'+p).encode()),p))
        out[6]=0.;out[7]=sum(r*shock[p] for r,p in zip(rho,names))/z
        out[8]=sum(r*shock[p] for r,p in zip(rho,ordered))/z
    return np.array(out)

def main():
    began=time.monotonic();started=datetime.now().astimezone().isoformat(timespec='seconds')
    raw=MANIFEST.read_bytes();assert sha(raw)==EXPECTED;m=json.loads(raw)
    frame=pd.read_csv(io.BytesIO(bound(m['parent_feature_labels'])),compression='gzip',
                      usecols=['event_id','family_id','product_id','u_date','feature_ready','label_identified','r1_atr',*MARKET],
                      keep_default_na=False)
    frame.r1_atr=pd.to_numeric(frame.r1_atr,errors='coerce');ready=frame.loc[frame.feature_ready.eq(1)].reset_index(drop=True)
    ids=pd.read_csv(io.BytesIO(bound(m['event_ids_csv'])),compression='gzip')
    assert len(ready)==194709 and int(ready.label_identified.eq(0).sum())==541
    assert ids.event_id.tolist()==ready.event_id.tolist() and ids.sequence_index.tolist()==list(range(len(ready)))
    states=pd.read_csv(io.BytesIO(bound(m['context_states'])),compression='gzip')
    assert states.event_id.tolist()==ready.event_id.tolist()
    with np.load(io.BytesIO(bound(m['context_npz'])),allow_pickle=False) as saved:
        assert saved.files==SCOPES;contexts={scope:saved[scope] for scope in SCOPES}
    for scope,x in contexts.items():
        assert x.shape==(194709,9) and x.dtype.str=='<f8' and np.isfinite(x).all()
        assert np.isin(x[:,3],[0,1]).all() and np.isin(x[:,6],[0,1]).all()
        assert np.all(x[:,4]>=0) and np.all(x[:,4]==np.floor(x[:,4]))
        assert np.all(x[:,5]>=0) and np.all(x[:,5]<=x[:,4]+1e-12)
        missing=x[:,6]==1;assert np.all(x[missing,5]==0) and np.all(x[missing,7:]==0)
        assert np.all(x[~missing,4]>0) and np.all(x[~missing,5]>0)
        assert np.array_equal(states[scope+'_state'].eq('relation_ready').to_numpy(),~missing)
    main_error=float(np.abs(contexts['main'][:,:4]-ready[MARKET].to_numpy(float)).max())
    assert np.allclose(contexts['main'][:,:4],ready[MARKET].to_numpy(float),atol=1e-12,rtol=1e-12)
    dates=np.load(io.BytesIO(bound(m['source_calendar'])),allow_pickle=False)
    calendar=[f'{str(int(v))[:4]}-{str(int(v))[4:6]}-{str(int(v))[6:]}' for v in dates]
    assert len(calendar)==5587 and len(m['source_calendar_scope_dates'])==4074
    means=ready.groupby(['u_date','family_id']).r1_atr.mean()
    panel=means.unstack('family_id').reindex(calendar)
    # Pre-outcome deterministic strata: first/middle/last ready day in each year;
    # first/middle/last lexical query family and first F/unknown-ready row if present.
    selected=[]
    for year in range(2010,2027):
        days=sorted(ready.loc[ready.u_date.str.startswith(str(year)),'u_date'].unique())
        for u in sorted(set([days[0],days[len(days)//2],days[-1]])):
            rows=ready.loc[ready.u_date.eq(u)];families=sorted(rows.family_id.unique())
            picks=set([families[0],families[len(families)//2],families[-1]])
            for mask in [rows.product_id.str.endswith('_F'),rows.label_identified.eq(0)]:
                if mask.any():picks.add(rows.loc[mask].family_id.iloc[0])
            for family in sorted(picks):selected.append(int(rows.loc[rows.family_id.eq(family)].index[0]))
    samples=[];max_error=0.
    for index in selected:
        row=ready.loc[index]
        for scope,held in [('main',None),('holdout_0',0),('holdout_1',1)]:
            expected=reference(panel,calendar,row.u_date,row.family_id,held);actual=contexts[scope][index]
            error=float(np.max(np.abs(expected-actual)));max_error=max(max_error,error)
            assert np.allclose(expected,actual,atol=1e-11,rtol=1e-11),(row.event_id,scope,error)
            samples.append({'event_id':row.event_id,'u_date':row.u_date,'family_id':row.family_id,
                            'scope':scope,'peer_count':int(expected[4]),'max_abs_error':error})
    # Same family/day includes F expressions: contexts must be exactly equal.
    duplicate_groups=ready.groupby(['u_date','family_id']).indices
    duplicate_pairs=0
    for indices in duplicate_groups.values():
        if len(indices)>1:
            for x in contexts.values():assert np.array_equal(x[indices],np.repeat(x[indices[:1]],len(indices),axis=0))
            duplicate_pairs+=len(indices)-1
    terminal=json.loads(bound(m['actual_terminal']));assert terminal['exit_code']==0
    r={'schema':'stage037_bounded_context_review_v1','independent_review':True,'status':'accepted_context_contract_with_bounded_numeric_reconstruction',
       'source_manifest':{'path':str(MANIFEST),'sha256':EXPECTED,'bytes':len(raw)},'all_ready_rows':len(ready),'ready_unknown_rows':541,
       'full_scope_matrices':3,'full_main_market4_scalar_checks':778836,'main_market4_max_abs_error':main_error,
       'bounded_query_rows':len(selected),'bounded_scope_cells':len(samples),'bounded_cells_max_abs_error':max_error,'bounded_cells':samples,
       'F_duplicate_context_pairs_checked':duplicate_pairs,'source_code_read':m['source_code'],'six_behavior_tests_read':m['tests'],
       'critical':0,'important':0,'minor':0,'full_q_independent_recomputed':False,
       'fit_calls':0,'sql_queries':0,'financial_backtests':0,'downloads':0,'author_calculation_imports':0,
       'actual035_result_review_started':False,'financial_ready':False,'production_qualified':False,
       'limitations':['Bounded q/held/null reconstruction plus code/behavior boundary review; not all-q independent recomputation.',
                      'q may reconstruct own u-1 shock omitted by COMMON S11; no proof beyond complete own history or causal propagation.']}
    (OUT/'context_review.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    t={'schema':'stage037_context_actual_terminal_v1','exit_code':0,'started_at':started,
       'finished_at':datetime.now().astimezone().isoformat(timespec='seconds'),'elapsed_seconds':time.monotonic()-began,
       'source_sha256':sha(Path(__file__).read_bytes()),'fit_calls':0,'sql_queries':0,'financial_backtests':0}
    (OUT/'context_actual_terminal.json').write_text(json.dumps(t,indent=2)+'\n')
    print(json.dumps({'status':r['status'],'ready_rows':len(ready),'bounded_cells':len(samples),
                      'max_error':max_error,'elapsed_seconds':t['elapsed_seconds']}))

if __name__=='__main__':main()
