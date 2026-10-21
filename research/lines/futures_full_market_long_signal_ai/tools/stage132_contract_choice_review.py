"""Independent fixed128 contract-choice actual audit.

No strategy replay, fitting or network. Actual mode needs all three exact final
manifests and terminals; one read-only native SELECT maximum. Definitions import
without touching data. Saved-fill accounting uses pinned independent102 helpers.
"""
from __future__ import annotations
import argparse,ast,bisect,gzip,hashlib,io,json,math,os,sqlite3,time,traceback
from collections import defaultdict,Counter,deque
from datetime import date,datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd

LINE=Path(__file__).resolve().parents[1]
PROTOCOL_SHA='bbd24a6e352fe0fbc77f710eeee18918cc1b4670749339e4f3ae67632095efe0'
ARMS=('A','B');SCOPES=('main','holdout_0','holdout_1');CUTOFFS=('2020-01-01','2023-01-01')
WINDOWS=('primary_2020','cold_2023');COSTS=('base','stress')
HELPERS={'stage102_cash_adapter.py':'702ad195d988eec4d847289ad9961525a35e65d4146de796073b1ca3c0df9044','stage102_cash_core.py':'4310bdd81375e17406b1773658c582ccb570a25d09b8fa53d15461c76cbb3eaa','stage102_cash_diagnostics.py':'0075f91ba110ea902ee374a917f20433ace66afde9bde755088f2573d09d11cc'}
NUMERIC=['sequence_index','action_sequence_index','mother_sequence_index','u_index','D_index','label_history_ready20','u_action_eligible','entry_capacity_qty','gross_capacity_qty','N_u','low20_u','u_close','history_run','lifecycle_index','entry_index','exit_index','unknown_index','last_path_index','holding_source_days','entry_reference','exit_reference','SL0','entry_boundary','exit_boundary','terminal_mark','R0_points','cash_risk_unit','multiplier','round_lot','tick_size','filled','trade_label_known','policy_diagnostic_pnl','net_R_stress','net_R_base','net_pnl_stress_per_lot','net_pnl_base_per_lot']
ERRORS={}

def finite(v):
    try:return not isinstance(v,(bool,np.bool_))and math.isfinite(float(v))
    except(TypeError,ValueError):return False

def positive(v):return finite(v)and float(v)>0

def compare(a,b,label,atol=2e-7,rtol=2e-10):
    x=np.asarray(a,dtype=float);y=np.asarray(b,dtype=float)
    assert x.shape==y.shape,(label,'shape',x.shape,y.shape)
    assert np.array_equal(np.isnan(x),np.isnan(y)),(label,'nan')
    assert np.array_equal(np.isfinite(x),np.isfinite(y)),(label,'finite')
    z=np.isfinite(x)&np.isfinite(y);err=np.abs(x[z]-y[z]);maximum=float(err.max())if err.size else 0.
    ERRORS[label]=max(ERRORS.get(label,0.),maximum)
    assert np.all(err<=atol+rtol*np.abs(y[z])),(label,maximum)

def capacity(volume,lot):
    if not finite(volume)or float(volume)<=0 or not positive(lot)or float(lot)!=int(lot):return None,None
    L=int(lot);gross=L*math.floor(.01*float(volume)/L);entry=L*math.floor(gross/(2*L))
    return gross,entry

def request(previous,anchor,current,next_index,lifecycle):
    if previous:return previous
    if next_index>=lifecycle:return 'held_lifecycle'
    if not current:return 'anchor_canonical_missing'
    if current!=anchor:return 'anchor_canonical_changed'
    return None

def union_intervals(intervals):
    result=[]
    for a,b in sorted(intervals):
        assert isinstance(a,(int,np.integer))and isinstance(b,(int,np.integer))and b>=a>=0
        if result and a<=result[-1][1]+1:result[-1][1]=max(result[-1][1],b)
        else:result.append([int(a),int(b)])
    return result

def union_weights(train):
    """Only the supplied own-mature fold; one family-u union, not one per month."""
    assert len(train)>0
    f=train.reset_index(drop=True);groups=[];index=np.empty(len(f),int)
    for gid,((family,u),ids)in enumerate(f.groupby(['family_id','u_date'],sort=True).indices.items()):
        ids=np.asarray(ids,int);a=pd.to_numeric(f.iloc[ids].entry_index).to_numpy(float);b=pd.to_numeric(f.iloc[ids].exit_index).to_numpy(float)
        assert np.isfinite(a).all()and np.isfinite(b).all()and np.equal(a,np.floor(a)).all()and np.equal(b,np.floor(b)).all()
        union=union_intervals(zip(a.astype(int),b.astype(int)));length=sum(y-x+1 for x,y in union);assert length>0
        index[ids]=gid;groups.append(dict(group_id=gid,family_id=family,u_date=u,union_intervals=union,union_length=length,member_count=len(ids)))
    for family in f.family_id.unique():
        own=[g for g in groups if g['family_id']==family];end=max(b for g in own for a,b in g['union_intervals']);delta=np.zeros(end+2,int)
        for g in own:
            for a,b in g['union_intervals']:delta[a]+=1;delta[b+1]-=1
        count=np.cumsum(delta[:-1]);inverse=np.divide(1.,count,out=np.zeros(len(count)),where=count>0);prefix=np.r_[0.,np.cumsum(inverse)]
        for g in own:g['uniqueness']=sum(prefix[b+1]-prefix[a]for a,b in g['union_intervals'])/g['union_length']
    U=np.asarray([groups[g]['uniqueness']for g in index]);n=np.asarray([groups[g]['member_count']for g in index]);base=U/n
    totals=pd.Series(base).groupby(f.u_date.to_numpy()).transform('sum').to_numpy();p=base/totals;w=p/p.mean()
    return dict(group_id=index,group_member_count=n,union_length=np.asarray([groups[g]['union_length']for g in index]),group_uniqueness=U,b_a=base,day_weight_total=totals,p_a=p,sample_weight=w,groups=groups)

def choose(rows,arm):
    """Returns family-u -> action_id, exact product month then normal-before-F."""
    assert arm in ARMS
    proposals=[]
    for(product,u),g in rows.groupby(['product_id','u_date'],sort=True):
        legal=g.loc[pd.to_numeric(g.u_action_eligible).eq(1)&np.isfinite(pd.to_numeric(g.score))&pd.to_numeric(g.score).gt(0)]
        if arm=='A':legal=legal.loc[legal.actual_epoch.eq(legal.anchor_epoch)]
        if legal.empty:continue
        picked=legal.sort_values(['score','actual_epoch','action_id'],ascending=[False,True,True],kind='mergesort').iloc[0]
        proposals.append((str(picked.family_id),str(u),str(product).endswith('_F'),str(product),str(picked.actual_epoch),str(picked.action_id)))
    selected={}
    for family,u,isF,product,epoch,action in sorted(proposals):selected.setdefault((family,u),action)
    return selected

def legal_bar(row):
    if row is None or len(row)<6 or row[5]!='accepted':return False
    if not all(positive(x)for x in row[:5]):return False
    O,H,L,C,V=row[:5];return L<=min(O,C)and H>=max(O,C)

def audit_capacity_rows(fills,bars,calendar,economics):
    previous={d:calendar[i-1]if i else ''for i,d in enumerate(calendar)};consumed=defaultdict(int);result=[]
    for i,r in enumerate(fills.to_dict('records')):
        account=r.get('account_id','');epoch=r['epoch'];day=r['date'];prior=previous[day];raw=bars.get((epoch,prior));cap,_=capacity(raw[4],economics[epoch]['round_lot'])if legal_bar(raw)else(None,None)
        key=(account,epoch,day);before=consumed[key];consumed[key]+=int(float(r['qty']));unknown=cap is None or consumed[key]>cap
        result.append(dict(fill_sequence_index=i,account_id=account,epoch=epoch,date=day,previous_date=prior,reference_volume=float(raw[4])if legal_bar(raw)else None,gross_cap=cap,prior_gross_qty=before,qty=int(float(r['qty'])),cumulative_gross_qty=consumed[key],execution_capacity_unknown=bool(unknown)))
    return result

def outcome(action,labels,end):
    if not action:return 0.,False
    r=labels[action]
    if r['participation_state']=='known_nonparticipation':return 0.,False
    if r['label_state']=='closed_complete_bar_model'and r.get('label_known_date','')and r['label_known_date']<=end and finite(r.get('net_R_stress')):return float(r['net_R_stress']),False
    return None,True

def choice_increment(a,b,labels,end):
    av,au=outcome(a,labels,end);bv,bu=outcome(b,labels,end)
    if a==b:return 0.,False,bool(au or bu)
    if au or bu:return None,True,False
    return bv-av,False,False

def group_hash(family):return int.from_bytes(hashlib.sha256(family.encode()).digest(),'big')%2

def binding(path):
    p=Path(path).resolve();raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def bound(b):
    raw=Path(b['path']).read_bytes();assert len(raw)==b.get('bytes',b.get('size',len(raw)))and hashlib.sha256(raw).hexdigest()==b['sha256'],('binding',b['path']);return raw

def table(b):return pd.read_csv(io.BytesIO(bound(b)),compression='gzip'if b['path'].endswith('.gz')else None,dtype=str,keep_default_na=False)

def artifact(manifest,role):
    values=manifest['artifacts'];values=list(values.values())if isinstance(values,dict)else values
    exact=[b for b in values if b.get('role')==role]
    if not exact and isinstance(manifest['artifacts'],dict)and role in manifest['artifacts']:exact=[manifest['artifacts'][role]]
    if not exact and isinstance(manifest.get(role),dict):exact=[manifest[role]]
    assert len(exact)==1,('artifact role',role);return exact[0]

def numeric(frame,columns):
    for key in columns:
        if key in frame:frame[key]=pd.to_numeric(frame[key].replace('',np.nan),errors='raise')
    return frame

def safe(v):
    if isinstance(v,dict):return{str(k):safe(x)for k,x in v.items()}
    if isinstance(v,(list,tuple)):return[safe(x)for x in v]
    if isinstance(v,np.ndarray):return safe(v.tolist())
    if isinstance(v,np.generic):return v.item()
    return v

def write(path,value):
    with Path(path).open('x')as f:json.dump(safe(value),f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')

def progress(out,name,value):write(out/(name+'.json'),value);print(json.dumps(dict(phase=name,completed=True)),flush=True)

class NativeBars:
    """One SQL read into compact per-epoch arrays; no large database hash."""
    def __init__(self,calendar):self.calendar=calendar;self.index={d:i for i,d in enumerate(calendar)};self.series={}
    def get(self,key,default=None):
        epoch,day=key;s=self.series.get(epoch);k=self.index.get(day)
        if s is None or k is None:return default
        j=int(np.searchsorted(s['days'],k))
        if j>=len(s['days'])or s['days'][j]!=k:return default
        return tuple(s['values'][j])+('accepted'if s['accepted'][j]else'invalid',)
    def locate(self,epoch,k):
        s=self.series.get(epoch)
        if s is None:return None
        j=int(np.searchsorted(s['days'],k));return j if j<len(s['days'])and s['days'][j]==k else None

def database_state(path):
    p=Path(path);s=p.stat();return dict(path=str(p.resolve()),bytes=s.st_size,inode=s.st_ino,mtime_ns=s.st_mtime_ns,wal_present=Path(str(p)+'-wal').exists(),shm_present=Path(str(p)+'-shm').exists())

def indicator_arrays(days,values,valid):
    n=len(days);N=np.full(n,np.nan);low20=np.full(n,np.nan);run=np.zeros(n,int);r=0;last=None;previous=None;level=math.nan;seed=0.;lows=deque()
    for j,k in enumerate(days):
        if not valid[j]:r=0;last=None;previous=None;level=math.nan;seed=0.;lows.clear();continue
        if last is None or k!=last+1:r=0;previous=None;level=math.nan;seed=0.;lows.clear()
        O,H,L,C,V=values[j];tr=H-L if previous is None else max(H-L,abs(H-previous),abs(L-previous));r+=1
        if r<=20:
            seed+=tr
            if r==20:level=seed/20.
        else:level=(19*level+tr)/20.
        while lows and lows[0][0]<k-19:lows.popleft()
        while lows and lows[-1][1]>=L:lows.pop()
        lows.append((int(k),float(L)));N[j]=level;run[j]=r
        if r>=20:low20[j]=lows[0][1]
        last=int(k);previous=float(C)
    return N,low20,run

def read_native_once(b,calendar,out):
    before=database_state(b['path'])
    for k,v in before.items():assert b[k]==v,('native snapshot',k)
    write(out/'native_query_started.json',dict(native_source_queries_started=1,database=before))
    store=NativeBars(calendar);count=0;epoch='';days=[];values=[];accepted=[]
    def finish():
        if not days:return
        d=np.asarray(days,np.int32);x=np.asarray(values,float);a=np.asarray(accepted,bool);valid=a&np.isfinite(x).all(axis=1)&(x>0).all(axis=1)&(x[:,2]<=np.minimum(x[:,0],x[:,3]))&(x[:,1]>=np.maximum(x[:,0],x[:,3]))
        N,L,r=indicator_arrays(d,x,valid);store.series[epoch]=dict(days=d,values=x,accepted=a,valid=valid,N=N,low20=L,run=r)
    with sqlite3.connect('file:'+b['path']+'?mode=ro&immutable=1',uri=True)as db:
        cursor=db.execute('SELECT contract_epoch_id,trade_date,open,high,low,close,volume,quality_status FROM daily_bars WHERE trade_date>=? AND trade_date<=? ORDER BY contract_epoch_id,trade_date',('2010-01-01',calendar[-1]))
        for e,day,O,H,L,C,V,status in cursor:
            if e!=epoch:finish();epoch=e;days=[];values=[];accepted=[]
            k=store.index[day];assert not days or k>days[-1]
            days.append(k);values.append((O,H,L,C,V));accepted.append(status=='accepted');count+=1
        finish()
    after=database_state(b['path']);assert before==after and count==1552456 and len(store.series)==9520
    return store,dict(native_source_queries=1,native_contract_days=count,native_epochs=len(store.series),database_before=before,database_after=after,database_rehashed=False,inherited_database_sha256=b['sha256'])

def own_features(s,j):
    if j<20 or int(s['days'][j])-int(s['days'][j-20])!=20 or not s['valid'][j-20:j+1].all():return np.full(11,np.nan)
    x=s['values'][j-20:j+1];tr=np.maximum.reduce([x[1:,1]-x[1:,2],np.abs(x[1:,1]-x[:-1,3]),np.abs(x[1:,2]-x[:-1,3])]);atr=math.fsum(tr)/20
    if not positive(atr):return np.full(11,np.nan)
    u=x[-1];p=x[-2]
    a=np.array([(u[3]-p[3])/atr,(u[3]-x[-6,3])/(math.sqrt(5)*atr),(u[3]-x[0,3])/(math.sqrt(20)*atr),(u[3]-u[0])/atr,(u[1]-u[2])/atr,(u[3]-u[2])/(u[1]-u[2])if u[1]>u[2]else.5,(u[0]-p[3])/atr,(math.fsum(tr[-5:])/5)/atr,math.log(u[4]/(math.fsum(x[:-1,4])/20)),(u[3]-max(x[:-1,1]))/atr,atr/u[3]])
    return a if np.isfinite(a).all()else np.full(11,np.nan)

def pair_pools(store,needed):
    pools=defaultdict(list);ordinals=np.asarray(store.calendar,dtype='datetime64[D]').astype(np.int64)
    for epoch,s in store.series.items():
        product,month=epoch.rsplit('.',1);nominal=int(np.datetime64(month[:4]+'-'+month[4:]+'-01','D').astype(np.int64));d=s['days'];x=s['values'];valid=s['valid']
        paired=np.flatnonzero(valid[1:]&valid[:-1]&(np.diff(d)==1))+1
        for j in paired:
            k=int(d[j])
            if(product,k)not in needed or nominal<=ordinals[k]:continue
            pools[(product,k)].append((epoch,month,(nominal-ordinals[k])/365.,math.log(x[j,3]/x[j-1,3]),x[j,3],x[j-1,3]))
    for key in pools:pools[key].sort(key=lambda p:(p[1],p[0]))
    return pools

def maturity_features(pool,epoch,N,C):
    peers=[p for p in pool if p[0]!=epoch];tau=np.asarray([p[2]for p in peers]);r=np.asarray([p[3]for p in peers]);normal=N/C if positive(N)and positive(C)else math.nan
    qmissing=not positive(normal)or len({p[1]for p in peers})<3
    if not qmissing:qmissing=not positive(float(np.sum((tau-tau.mean())**2)))
    following=next((p for p in pool[1:]if p[1]!=pool[0][1]),None)if pool else None
    front=pool[0]if pool else None;bu=bp=span=math.nan
    if following is not None:bu=math.log(following[4]/front[4]);bp=math.log(following[5]/front[5]);span=following[2]-front[2]
    return np.asarray([normal,len(peers),float(tau.max()-tau.min())if len(peers)else math.nan,float(r.mean())if len(peers)else math.nan,float(r.std(ddof=0))if len(peers)else math.nan,float(r.min())if len(peers)else math.nan,float(r.max())if len(peers)else math.nan,bu,bp,span,int(qmissing),int(following is None),int(not math.isfinite(normal))])

def qualified(e):return e.get('economics_status')=='exact_epoch_metadata_snapshot'and positive(e.get('contract_multiplier'))and positive(e.get('round_lot'))and float(e['round_lot']).is_integer()

def lifecycle(epoch,e,calendar):
    month=epoch.rsplit('.',1)[1];boundaries=[month[:4]+'-'+month[4:]+'-01']
    for key in ('known_lifecycle_exit_boundary','nominal_month_first_date','maturity_date','de_listed_date'):
        v=e.get(key)
        if isinstance(v,str)and len(v)>=10 and v[:10]>='1900-01-01':boundaries.append(v[:10])
    return bisect.bisect_left(calendar,min(boundaries))

def audit_label_path(row,store,e,refs,end,cash):
    """Independent one-action price-path check, not an account or alternate policy."""
    epoch=row.reference_epoch;s=store.series[epoch];u=int(row.u_index);D=u+1;j=store.locate(epoch,u);N=s['N'][j];L20=s['low20'][j];C=s['values'][j,3];ready=s['valid'][j]and s['run'][j]>=20 and positive(N)and positive(L20)
    if not ready:return 'not_history_ready',{}
    if not qualified(e):return 'input_or_economics_unresolved',{}
    exp=lifecycle(epoch,e,store.calendar)
    try:
        for cost in COSTS:cash.estimate(C,N,e,cost,.25)
    except(AssertionError,ValueError):return 'input_or_economics_unresolved',{}
    if not row.anchor_epoch or not legal_bar(store.get((row.anchor_epoch,store.calendar[u]))):return 'input_or_economics_unresolved',{}
    if D<len(store.calendar)and (D>=exp or (e.get('listed_date')and store.calendar[D]<e['listed_date'])):return 'known_nonparticipation',{}
    if D>end:return 'intent_right_censored',{}
    q=store.locate(epoch,D)
    if q is None or not s['valid'][q]:return 'entry_execution_unknown',{}
    F=s['values'][q,0];SL=F-.25*N
    if F<=L20 or SL<=0:return 'known_nonparticipation',{}
    try:buys={c:cash.quote(F,'BUY',e,c)for c in COSTS}
    except(AssertionError,ValueError):return 'input_or_economics_unresolved',{}
    B=max(SL,L20);force=None;answer=dict(entry_index=D,entry_reference=F,SL0=SL,entry_boundary=B)
    for k in range(D,end+1):
        p=store.locate(epoch,k)
        if p is None or not s['valid'][p]:return 'path_or_execution_unknown',answer
        O,H,L,close,V=s['values'][p];exit_ref=O if force or O<=B else B if L<=B else None
        if exit_ref is not None:
            try:sells={c:cash.quote(exit_ref,'SELL',e,c)for c in COSTS}
            except(AssertionError,ValueError):return 'input_or_economics_unresolved',answer
            answer.update(exit_index=k,exit_reference=exit_ref,exit_boundary=B,holding_source_days=k-D+1)
            for cost in COSTS:
                net=float(e['contract_multiplier'])*(sells[cost][0]-buys[cost][0])-buys[cost][1]-sells[cost][1];answer['net_pnl_'+cost+'_per_lot']=net;answer['net_R_'+cost]=net/(.25*N*float(e['contract_multiplier']))
            return 'closed_complete_bar_model',answer
        B=max(SL,float(s['low20'][p]));force=request(force,row.anchor_epoch,refs.get((row.product_id,k),''),k+1,exp)
    return 'open_right_censored',answer

def calendar_from_protocol(protocol):
    bridge=json.loads(bound(protocol['inputs']['market_protocol']));a=np.load(io.BytesIO(bound(bridge['calendar'])),allow_pickle=False)
    days=[str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8]for v in a]if a.dtype.kind in'iu'else a.astype('datetime64[D]').astype(str).tolist()
    assert len(days)==5587 and days==sorted(set(days));return bridge,days

def review_dataset(manifest,protocol,out,cash):
    mb=artifact(manifest,'mothers');ab=artifact(manifest,'actions');xb=artifact(manifest,'common')
    mothers=table(mb);numeric(mothers,['sequence_index','u_index'])
    assert len(mothers)==399252 and mothers.event_id.is_unique and np.array_equal(mothers.sequence_index,np.arange(len(mothers)))
    assert mothers.product_id.nunique()==98 and mothers.family_id.nunique()==95 and mothers.product_id.str.split('.').str[0].nunique()==6
    assert not mothers.duplicated(['product_id','u_date']).any()and mothers.u_date.nunique()==4074
    original=pd.read_csv(io.BytesIO(bound(protocol['inputs']['narrow_labels'])),compression='gzip',usecols=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch'],dtype=str,keep_default_na=False)
    numeric(original,['sequence_index','u_index'])
    for c in original:assert mothers[c].tolist()==original[c].tolist(),('mother retained',c)
    del original
    bridge,calendar=calendar_from_protocol(protocol);economics=json.loads(bound(bridge['economic_projection']))['instruments'];store,native=read_native_once(bridge['database'],calendar,out)
    assert np.array_equal(mothers.u_index,mothers.u_date.map(store.index))
    # Read only the fields actually independently checked; author-only QA fields remain bound.
    keep=list(dict.fromkeys(NUMERIC+['action_id','event_id','actual_epoch','reference_epoch','mother_event_id','anchor_epoch','product_id','family_id','u_date','label_state','label_known_date','participation_state','economics_status','capacity_state','observation_state','u_ineligibility_reason','cancel_reason','unknown_reason']))
    raw=bound(ab);header=pd.read_csv(io.BytesIO(raw),compression='gzip',nrows=0).columns
    actions=pd.read_csv(io.BytesIO(raw),compression='gzip',usecols=[c for c in keep if c in header],dtype=str,keep_default_na=False,float_precision='round_trip');del raw;numeric(actions,NUMERIC)
    assert len(actions)>0 and actions.action_id.is_unique and not actions.duplicated(['mother_sequence_index','actual_epoch']).any()
    assert np.array_equal(actions.sequence_index,np.arange(len(actions)))and actions.sequence_index.eq(actions.action_sequence_index).all()
    assert actions.event_id.eq(actions.action_id).all()and actions.reference_epoch.eq(actions.actual_epoch).all()
    p=actions.mother_sequence_index.to_numpy(int);assert(p>=0).all()and(p<len(mothers)).all()
    for c in ('product_id','family_id','u_date','u_index'):assert actions[c].tolist()==mothers[c].to_numpy()[p].tolist(),('child parent',c)
    assert actions.mother_event_id.tolist()==mothers.event_id.to_numpy()[p].tolist()and actions.anchor_epoch.tolist()==mothers.reference_epoch.to_numpy()[p].tolist()
    assert actions.actual_epoch.str.rsplit('.',n=1).str[0].eq(actions.product_id).all()and actions.family_id.eq(actions.product_id.str.removesuffix('_F')).all()
    assert actions.D_index.eq(actions.u_index+1).all()and actions.u_action_eligible.isin([0,1]).all()
    with np.load(io.BytesIO(bound(xb)),allow_pickle=False)as z:common=z['common'].copy();columns=z['columns'].tolist()
    assert common.shape==(len(actions),26)and columns==protocol['features']['common_columns']and common.dtype==np.float64
    mother_lookup={(r.product_id,int(r.u_index)):int(r.sequence_index)for r in mothers.itertuples(index=False)};expected=[]
    for epoch,s in store.series.items():
        product=epoch.rsplit('.',1)[0]
        for j,k in enumerate(s['days']):
            parent=mother_lookup.get((product,int(k)))
            if parent is not None:expected.append((parent,epoch))
    expected.sort();assert list(zip(actions.mother_sequence_index,actions.actual_epoch))==expected,'full native child action population'
    del expected
    needed=set(zip(actions.product_id,actions.u_index.astype(int)));pools=pair_pools(store,needed);refs={(r.product_id,int(r.u_index)):r.reference_epoch for r in mothers.itertuples(index=False)}
    ready_count=0;eligible_count=0;closed_count=0;states=Counter();path_count=0;economic_unknown=0;chunks=0;end=store.index[protocol['scope']['end']]
    for start in range(0,len(actions),20000):
        part=actions.iloc[start:start+20000];X=np.full((len(part),26),np.nan);expected_N=np.full(len(part),np.nan);expected_L=np.full(len(part),np.nan);expected_C=np.full(len(part),np.nan);expected_run=np.zeros(len(part));expected_ready=np.zeros(len(part));expected_eligible=np.zeros(len(part));expected_entrycap=np.full(len(part),np.nan);expected_gross=np.full(len(part),np.nan);path_values=defaultdict(list)
        for z,row in enumerate(part.itertuples(index=False)):
            epoch=row.actual_epoch;u=int(row.u_index);version='stage129_contract_choice_action_v1';payload=json.dumps(dict(version=version,mother_event_id=row.mother_event_id,actual_epoch=epoch),ensure_ascii=False,sort_keys=True,separators=(',',':'));assert row.action_id==version+'_'+hashlib.sha256(payload.encode()).hexdigest();s=store.series[epoch];j=store.locate(epoch,u);assert j is not None
            N=float(s['N'][j]);L=float(s['low20'][j]);C=float(s['values'][j,3]);run=int(s['run'][j]);valid=bool(s['valid'][j]);e=economics.get(epoch,{})
            expected_N[z]=N if valid else np.nan;expected_L[z]=L if valid else np.nan;expected_C[z]=C if valid else np.nan;expected_run[z]=run
            ready=valid and run>=20 and positive(N)and positive(L);expected_ready[z]=int(ready);ready_count+=ready
            gc,ec=capacity(s['values'][j,4],e.get('round_lot'));expected_gross[z]=gc if gc is not None else np.nan;expected_entrycap[z]=ec if ec is not None else np.nan
            exp=lifecycle(epoch,e,calendar);legal=ready and qualified(e)and legal_bar(store.get((row.anchor_epoch,calendar[u])))and ec is not None and ec>=e['round_lot']and (u+1>=len(calendar) or u+1<exp) and(u+1>=len(calendar)or not e.get('listed_date')or calendar[u+1]>=e['listed_date'])
            if legal:
                try:
                    for cost in COSTS:cash.estimate(C,N,e,cost,.25)
                except(AssertionError,ValueError):legal=False
            expected_eligible[z]=int(legal);eligible_count+=legal;economic_unknown+=not qualified(e)
            X[z,:11]=own_features(s,j);X[z,11:24]=maturity_features(pools.get((row.product_id,u),[]),epoch,N,C)
            if ready and qualified(e):
                try:
                    _,_,f,buy=cash.estimate(C,N,e,'stress',.25);sell=cash.quote(C,'SELL',e,'stress');X[z,24]=(f+buy[2]+sell[2])/(2*N*e['contract_multiplier'])
                except(AssertionError,ValueError):pass
            if ready:X[z,25]=(C-L)/(2*N)
            # Every child's state and all ready/economic paths are checked, not only winners.
            state,path=audit_label_path(row,store,e,refs,end,cash);assert row.label_state==state,('all-child policy state',int(row.sequence_index),row.label_state,state)
            states[state]+=1;path_count+=bool(path);closed_count+=state=='closed_complete_bar_model'
            for key,value in path.items():
                if key in part.columns:path_values[key].append((z,value))
            if state=='closed_complete_bar_model':
                assert row.label_known_date==calendar[int(path['exit_index'])] and row.filled==1 and row.trade_label_known==1
            elif finite(row.net_R_stress)or finite(row.net_R_base):raise AssertionError('nonclosed target not null')
            else:assert row.trade_label_known==0
            if state=='known_nonparticipation':assert row.policy_diagnostic_pnl==0
            else:assert not finite(row.policy_diagnostic_pnl)
        for key,values in path_values.items():
            index=np.asarray([i for i,v in values],int);wanted=np.asarray([v for i,v in values]);compare(part[key].to_numpy()[index],wanted,'label_'+key,atol=2e-7)
        compare(part.N_u,expected_N,'all_native_N',atol=1e-12);compare(part.low20_u,expected_L,'all_native_low20',atol=1e-12);compare(part.u_close,expected_C,'all_native_u_close',atol=0,rtol=0);compare(part.history_run,expected_run,'all_native_rewarm',atol=0,rtol=0)
        compare(part.label_history_ready20,expected_ready,'all_u_history_ready',atol=0,rtol=0);compare(part.u_action_eligible,expected_eligible,'all_u_eligible',atol=0,rtol=0);compare(part.entry_capacity_qty,expected_entrycap,'all_u_half_capacity',atol=0,rtol=0)
        if 'gross_capacity_qty' in part:compare(part['gross_capacity_qty'],expected_gross,'all_u_gross_capacity',atol=0,rtol=0)
        compare(common[start:start+len(part)],X,'all_common26_native',atol=2e-10,rtol=2e-10);chunks+=1
        if chunks%5==0:print(json.dumps(dict(phase='independent_all_child_paths_features',completed_rows=start+len(part),total_rows=len(actions))),flush=True)
    report=dict(mother_rows_checked=len(mothers),products=98,families=95,exchanges=6,child_rows_checked=len(actions),child_population_complete=True,common_values_checked=int(common.size),all_own_feature_and_peer_pool_rows_checked=True,all_label_states_checked=len(actions),independent_policy_paths_checked=path_count,independent_closed_paths_checked=closed_count,policy_states=dict(states),history_ready=ready_count,u_eligible=eligible_count,economic_unknown=economic_unknown,native=native,strict_first_publication_PIT_established=False,static_economics_snapshot_limitation=True)
    return actions,mothers,common,columns,store,economics,report

def weighted_stats(values,w):
    x=np.asarray(values,float);ok=np.isfinite(x)
    if not ok.any():return dict(mean=0.,var=0.,scale=1.,finite_count=0)
    mean=float(np.average(x[ok],weights=w[ok]));var=float(np.average((x[ok]-mean)**2,weights=w[ok]));return dict(mean=mean,var=var,scale=math.sqrt(var)if var>0 else 1.,finite_count=int(ok.sum()))

def head52(raw,scaler):
    x=np.asarray(raw,float);m=np.asarray(scaler['common']['mean']);s=np.asarray(scaler['common']['scale']);ok=np.isfinite(x)
    assert np.isfinite(m).all()and np.isfinite(s).all()and(s>0).all();return np.column_stack([np.where(ok,(x-m)/s,0.),(~ok).astype(float)])

def check_choice_rows(saved,parents,pred,scores,scope,cutoff):
    assert len(saved)==2*len(parents)and not saved.duplicated(['event_id','arm']).any();a=pred.copy();a['score']=scores
    selected_maps={arm:choose(a,arm)for arm in ARMS};lookup=a.set_index('action_id');parent_index=parents.set_index('event_id')
    proposals={};observed=set(pred.mother_sequence_index)
    for arm in ARMS:
        legal=a.loc[a.u_action_eligible.eq(1)&a.score.gt(0)]
        if arm=='A':legal=legal.loc[legal.actual_epoch.eq(legal.anchor_epoch)]
        own=legal.sort_values(['mother_sequence_index','score','actual_epoch','action_id'],ascending=[True,False,True,True],kind='stable').drop_duplicates('mother_sequence_index')
        proposals[arm]=own.set_index('mother_sequence_index')
        s=saved.loc[saved.arm.eq(arm)];assert s.event_id.tolist()==parents.event_id.tolist()and s.scope.eq(scope).all()and s.cutoff.eq(cutoff).all()and s.policy.eq('NARROW').all()
        for c in('sequence_index','product_id','family_id','u_date','u_index','reference_epoch'):assert s[c].tolist()==parents[c].tolist(),('full parent choice identity',arm,c)
        assert s.anchor_epoch.tolist()==parents.reference_epoch.tolist()
        for r in s.itertuples(index=False):
            action=selected_maps[arm].get((r.family_id,r.u_date),'')
            # A family-u winner is attached to its own product mother only.
            # Other ordinary/F mothers retain their independent selected0 state.
            if action and int(lookup.loc[action,'mother_sequence_index'])!=int(r.sequence_index):action=''
            assert r.chosen_action_id==action and int(r.selected)==bool(action),('prospective winner',r.event_id,arm)
            if action:
                child=lookup.loc[action];assert r.chosen_epoch==child.actual_epoch and int(r.chosen_action_sequence_index)==int(child.sequence_index);compare(r.score,child.score,'all_parent_chosen_score',atol=1e-11)
            else:assert r.chosen_epoch==''and int(r.chosen_action_sequence_index)==-1 and not finite(r.score)
            if int(r.sequence_index)in proposals[arm].index:
                proposed=proposals[arm].loc[int(r.sequence_index)];assert r.proposed_action_id==proposed.action_id and r.proposed_epoch==proposed.actual_epoch;compare(r.proposed_score,proposed.score,'all_proposed_score',atol=1e-11)
                expected_state='selected'if action else'family_priority_suppressed'
            else:
                assert r.proposed_action_id==''and r.proposed_epoch==''and not finite(r.proposed_score)
                expected_state='no_observed_children'if int(r.sequence_index)not in observed else 'no_eligible_positive_action'
            assert r.selection_state==expected_state
    return len(saved)

def independent_held(choices,actions,end):
    labels=actions[['action_id','label_state','participation_state','net_R_stress','label_known_date']].set_index('action_id').to_dict('index');groups={};daily=[]
    for scope,part in choices.groupby('scope',sort=True):
        family=part.sort_values('selected',ascending=False,kind='stable').drop_duplicates(['arm','family_id','u_index']);arms={arm:family.loc[family.arm.eq(arm)].set_index(['family_id','u_index']).sort_index()for arm in ARMS};a=arms['A'];b=arms['B'].reindex(a.index);assert len(a)==len(b)and a.u_date.eq(b.u_date).all()
        values=[];common=0;unknown=0
        for left,right,day in zip(a.chosen_action_id,b.chosen_action_id,a.u_date):
            v,u,c=choice_increment(left,right,labels,end);values.append(dict(u_date=day,delta_R=v,known=v is not None,unknown=u));common+=c;unknown+=u
        f=pd.DataFrame(values);d=f.groupby('u_date',sort=True).agg(delta_R=('delta_R','mean'),known_family_u=('known','sum'),unknown_family_u=('unknown','sum')).reset_index();d['scope']=scope;daily.append(d);mean=float(d.delta_R.mean())if d.delta_R.notna().any()else None
        groups[scope]=dict(nominal_pass=mean is not None and mean>=0,status='unsupported'if mean is not None and mean<0 else'unknown'if mean is None or unknown else'supported',known_u_equal_mean_increment_R=mean,unknown_differential_selected_events=int(unknown),common_unresolved_same_action=int(common),full_family_u=len(a),known_increment_family_u=int(f.known.sum()),known_source_days=int(d.delta_R.notna().sum()),selected_by_arm={arm:int(part.loc[part.arm.eq(arm),'selected'].sum())for arm in ARMS},annual=[dict(year=y,mean_delta_R=float(v.delta_R.mean())if v.delta_R.notna().any()else None,source_days=len(v),unknown_family_u=int(v.unknown_family_u.sum()))for y,v in d.groupby(d.u_date.str[:4])],unknown_R_bounds=None)
    return dict(schema='stage130_prospective_choice_held_v1',groups=groups,contrast='B_minus_A',meaning='actual pre-outcome chosen action; same action incremental zero with unresolved disclosure; distinct unknown never zero; family-u then equal-u; not cash',full_policy_cash_qualified=False),pd.concat(daily,ignore_index=True)

def nested(actual,expected,label):
    if isinstance(expected,dict):
        assert set(actual)==set(expected),(label,'keys',set(actual)^set(expected))
        for k,v in expected.items():nested(actual[k],v,label+'.'+str(k))
    elif isinstance(expected,list):
        assert len(actual)==len(expected),(label,'length')
        for i,(a,b)in enumerate(zip(actual,expected)):nested(a,b,label+str(i))
    elif isinstance(expected,(float,int,np.number))and not isinstance(expected,bool):compare(actual,expected,label,atol=1e-8,rtol=2e-9)
    else:assert actual==expected,(label,actual,expected)

def review_models(manifest,actions,mothers,common,columns,out):
    root=Path(manifest['terminal']['path']).parent;records=json.loads(bound(manifest['fit_records']));assert len(records)==6
    scores=table(artifact(manifest,'child_scores'));numeric(scores,['sequence_index','mother_sequence_index','u_index','u_action_eligible','score'])
    main=table(artifact(manifest,'choices_main'));held=table(artifact(manifest,'choices_holdout'))
    for f in(main,held):numeric(f,['sequence_index','u_index','selected','chosen_action_sequence_index','score','proposed_score'])
    choices=pd.concat([main,held],ignore_index=True);forward=actions.loc[actions.u_date.ge('2020-01-01')]
    for q in(scores.loc[scores.scope.eq('main')],scores.loc[scores.scope.ne('main')]):assert q.action_id.is_unique and set(q.action_id)==set(forward.action_id)
    for q in(main,held):
        assert len(q)==322028 and not q.duplicated(['event_id','arm']).any()
        for arm in ARMS:assert set(q.loc[q.arm.eq(arm),'event_id'])==set(mothers.loc[mothers.u_date.ge('2020-01-01'),'event_id'])
    cells=[]
    for scope in SCOPES:
        for cutoff,stop in zip(CUTOFFS,('2023-01-01',None)):
            mask=actions.u_action_eligible.eq(1)&actions.label_state.eq('closed_complete_bar_model')&actions.u_date.lt(cutoff)&actions.label_known_date.ne('')&actions.label_known_date.lt(cutoff)&np.isfinite(actions.net_R_stress)
            pmask=actions.u_date.ge(cutoff)&(actions.u_date.lt(stop)if stop else True);mmask=mothers.u_date.ge(cutoff)&(mothers.u_date.lt(stop)if stop else True)
            if scope!='main':
                g=int(scope[-1]);mask&=actions.family_id.map(group_hash).ne(g);pmask&=actions.family_id.map(group_hash).eq(g);mmask&=mothers.family_id.map(group_hash).eq(g)
            train=actions.loc[mask];pred=actions.loc[pmask];parent=mothers.loc[mmask];ti=train.sequence_index.to_numpy(int);pi=pred.sequence_index.to_numpy(int);assert len(train)and len(pred)
            w=union_weights(train);weights=w['sample_weight'];cell=root/'folds'/scope/cutoff
            saved=pd.read_csv(cell/'training_identity_weights.csv.gz',dtype=str,keep_default_na=False,float_precision='round_trip');numeric(saved,NUMERIC+['group_id','group_member_count','group_union_length','group_uniqueness','base_weight','day_weight_total','sample_weight'])
            assert saved.action_id.tolist()==train.action_id.tolist()and saved.label_known_date.tolist()==train.label_known_date.tolist()
            for c in('u_action_eligible','u_index','entry_index','exit_index','net_R_stress'):compare(saved[c],train[c],'all_training_'+c,atol=1e-11)
            for c,k in [('group_id','group_id'),('group_member_count','group_member_count'),('group_union_length','union_length'),('group_uniqueness','group_uniqueness'),('base_weight','b_a'),('day_weight_total','day_weight_total'),('sample_weight','sample_weight')]:compare(saved[c],w[k],'all_union_weight_'+c,atol=1e-10)
            gs=pd.read_csv(cell/'weight_groups.csv.gz',dtype=str,keep_default_na=False);assert len(gs)==len(w['groups'])
            for r,g in zip(gs.to_dict('records'),w['groups']):
                assert int(r['group_id'])==g['group_id']and r['family_id']==g['family_id']and r['u_date']==g['u_date']and json.loads(r['union_intervals'])==g['union_intervals'];assert int(r['member_count'])==g['member_count']and int(r['union_length'])==g['union_length'];compare(r['uniqueness'],g['uniqueness'],'all_group_uniqueness',atol=1e-10)
            scaler=json.loads((cell/'scaler.json').read_text());assert scaler['feature_names']==columns+[c+'_missing'for c in columns]and scaler['common']['columns']==columns and scaler['scope']==scope and scaler['cutoff']==cutoff
            stats=[weighted_stats(common[ti,j],weights)for j in range(26)]
            for key in('mean','var','scale','finite_count'):compare(scaler['common'][key],[s[key]for s in stats],'all_fold_scaler_'+key,atol=1e-10)
            model=json.loads((cell/'portable_model.json').read_text());assert model['schema']=='stage130_shared_portable_ridge_v1'and model['scope']==scope and model['cutoff']==cutoff and model['parameters']==dict(alpha=1.,fit_intercept=True,solver='cholesky')and model['feature_names']==scaler['feature_names']
            coef=np.asarray(model['coef'],float);beta=np.r_[coef,float(model['intercept'])];assert len(coef)==52
            X=head52(common[ti],scaler);Z=np.column_stack([X,np.ones(len(X))]);lhs=Z.T@(weights[:,None]*Z);lhs[np.arange(52),np.arange(52)]+=1.;rhs=Z.T@(weights*train.net_R_stress.to_numpy(float));assert np.allclose(lhs@beta,rhs,atol=1e-7,rtol=1e-8)
            with np.load(cell/'normal_equations.npz',allow_pickle=False)as ne:compare(ne['lhs'],lhs,'all_normal_lhs',atol=2e-6);compare(ne['rhs'],rhs,'all_normal_rhs',atol=2e-6);compare(ne['coefficient_with_intercept'],beta,'all_portable_beta',atol=1e-12);compare(ne['weight_sum'],weights.sum(),'all_weight_sum',atol=1e-9)
            del X,Z
            import joblib
            estimator=joblib.load(cell/'model.joblib');compare(estimator.coef_,coef,'six_serialized_coefficients',atol=1e-12);compare(estimator.intercept_,model['intercept'],'six_serialized_intercept',atol=1e-12);assert estimator.alpha==1. and estimator.fit_intercept is True and estimator.solver=='cholesky'
            expected_scores=head52(common[pi],scaler)@coef+model['intercept'];actual=scores.loc[scores.scope.eq(scope)&scores.cutoff.eq(cutoff)];assert actual.action_id.tolist()==pred.action_id.tolist()
            compare(actual.score,expected_scores,'all_shared_child_forward_scores',atol=1e-10)
            for c in('sequence_index','mother_sequence_index','mother_event_id','product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible'):assert actual[c].tolist()==pred[c].tolist(),('all score identity',c)
            choice=choices.loc[choices.scope.eq(scope)&choices.cutoff.eq(cutoff)];check_choice_rows(choice,parent,pred,expected_scores,scope,cutoff)
            rec=next(r for r in records if(r['scope'],r['cutoff'])==(scope,cutoff))
            for k,v in dict(training_rows=len(train),training_dates=train.u_date.nunique(),training_families=train.family_id.nunique(),training_groups=len(gs),prediction_children=len(pred),prediction_mothers=len(parent),max_u_date=train.u_date.max(),max_label_known_date=train.label_known_date.max(),dimension=52).items():assert rec[k]==v,(scope,cutoff,k)
            cells.append(dict(scope=scope,cutoff=cutoff,training_rows=len(train),prediction_children=len(pred),prediction_mothers=len(parent),normal_equation_max_abs_residual=float(np.max(np.abs(lhs@beta-rhs))),groups=len(gs)))
            progress(out,'model_'+scope+'_'+cutoff,cells[-1])
    for filename,count in [('fit_attempts.jsonl','attempt'),('fit_completed.jsonl','completed')]:
        events=[json.loads(l)for l in(root/filename).read_text().splitlines()if l];assert[(r['scope'],r['cutoff'])for r in events]==[(s,c)for s in SCOPES for c in CUTOFFS]and[r[count]for r in events]==list(range(1,7))
    assert manifest['actual_fit_calls_attempted']==manifest['actual_fit_calls_completed']==6 and len(scores)==manifest['prediction_children']
    calculated,daily=independent_held(choices,actions,'2026-10-16');nested(json.loads(bound(artifact(manifest,'held_diagnostic'))),calculated,'held_actual_choice_family_u')
    saved_daily=table(artifact(manifest,'held_daily'));assert saved_daily[['u_date','scope']].values.tolist()==daily[['u_date','scope']].values.tolist()
    for c in('delta_R','known_family_u','unknown_family_u'):compare(pd.to_numeric(saved_daily[c].replace('',np.nan)),daily[c],'all_held_daily_'+c,atol=1e-10)
    return main,calculated,dict(models_checked=6,shared_child_scores_checked=len(scores),prospective_parent_choices_checked=len(choices),folds=cells,refits=0,all_unknown_prediction_rows_retained=True)

ACTIVE_POSITIONS=None
CASH_HELPER=None
REUSED_LEDGERS={}

def review_capped_budgets(budgets,daily,signals,economics,scenario,calendar,start,k):
    """Independent u fractional reserve then cap, including every selected rejection."""
    c=CASH_HELPER;fields=['u_equity','existing_risk','existing_buffered_margin','unit_risk_u','unit_margin_u','unit_fee_reserve_u','target_qty_unscaled','joint_scale','target_qty_prefloor','qty_cap','original_qty_cap','round_lot','allocated_risk','allocated_buffered_margin','allocated_fee','D_qty','D_unit_risk','D_unit_margin_plus_fee','existing_qty','target_existing_qty']
    c.numeric(budgets,fields)
    if budgets.empty:
        assert not(signals.u_index.ge(start-1)&signals.u_date.lt(daily.date.iloc[-1])).any();return dict(rows=0,new_allocations=0,existing_reductions=0,selected_event_records=0)
    assert budgets.budget_id.is_unique
    for field in('budget_kind','budget_state','D_state'):
        if field not in budgets:budgets[field]=''
    ordinary=budgets.loc[~budgets.budget_kind.eq('existing_position_reduction')];expected=set(signals.loc[signals.u_index.ge(start-1)&signals.u_date.lt(daily.date.iloc[-1]),'event_id']);assert ordinary.event_id.is_unique and set(ordinary.event_id)==expected,'all prospective choices retained as intents/rejections'
    lookup={d:i for i,d in enumerate(calendar)};day=daily.set_index('date');new_count=reduce_count=0
    for u,group in budgets.groupby('u_date',sort=False):
        assert group.execution_date.eq(calendar[lookup[u]+1]).all()
        if u in day.index:eq=float(day.loc[u,'equity']);risk=float(day.loc[u,'initial_risk']);margin=float(day.loc[u,'buffered_margin']);insolvent=str(day.loc[u,'ever_insolvent']).lower()in('true','1')
        else:assert lookup[u]==start-1;eq=1000000.;risk=margin=0.;insolvent=False
        for field,v in [('u_equity',eq),('existing_risk',risk),('existing_buffered_margin',margin)]:compare(group[field],np.full(len(group),v),'all_budget_'+field)
        occupied=set(ACTIVE_POSITIONS.loc[ACTIVE_POSITIONS.date.eq(u),'family_id'])if ACTIVE_POSITIONS is not None else set();over=risk>.02*eq or margin>.25*eq
        expected_new=set()
        for r in group.loc[~group.budget_kind.eq('existing_position_reduction')].to_dict('records'):
            sig=signals.loc[r['event_id']];reason='family_occupied'if sig.family_id in occupied else'insolvent_permanent_pause'if insolvent else'existing_risk_margin_over_cap'if over else None
            if reason:assert r['budget_kind']!='new_entry'and r['budget_state']==reason and r['D_state']==reason,('rejection reason',r['event_id'],reason)
            else:expected_new.add(r['event_id'])
        new=group.loc[group.budget_kind.eq('new_entry')];assert set(new.event_id)==expected_new
        proposals=[]
        for r in new.to_dict('records'):
            sig=signals.loc[r['event_id']];e=economics[r['reference_epoch']];assert r['reference_epoch']==sig.reference_epoch and r['anchor_epoch']==sig.anchor_epoch
            R,M,F,buy=c.estimate(float(sig.u_close),float(sig.N_u),e,scenario,.25);real=max(0.,.0025*eq/R)if eq>0 else 0.;proposals.append((r,sig,e,R,M,F,real))
            compare([r['unit_risk_u'],r['unit_margin_u'],r['unit_fee_reserve_u'],r['target_qty_unscaled']],[R,M,F,real],'u_unit_estimates')
        totalrisk=sum(R*q for r,sig,e,R,M,F,q in proposals);totalmargin=sum(M*q for r,sig,e,R,M,F,q in proposals)
        scale=min(1.,max(0.,.02*eq-risk)/totalrisk if totalrisk else 1.,max(0.,.25*eq-margin)/totalmargin if totalmargin else 1.)if eq>0 else 0.
        for r,sig,e,R,M,F,real in proposals:
            target=real*scale;lot=int(e['round_lot']);original=c.floorlot(target,lot);cap=min(original,int(sig.entry_capacity_qty));assert r['original_qty_cap']==original and r['qty_cap']==cap and r['D_qty']<=cap and r['D_qty']>=0
            compare([r['joint_scale'],r['target_qty_prefloor'],r['allocated_risk'],r['allocated_buffered_margin'],r['allocated_fee']],[scale,target,target*R,target*M,target*F],'all_joint_allocations_before_cap');new_count+=1
        reductions=group.loc[group.budget_kind.eq('existing_position_reduction')];factor=min(1.,.02*eq/risk if risk else 1.,.25*eq/margin if margin else 1.)if eq>0 else 0.
        expected_roots=set(ACTIVE_POSITIONS.loc[ACTIVE_POSITIONS.date.eq(u),'root_id'])if(insolvent or over)and ACTIVE_POSITIONS is not None else set();assert (set(reductions.root_id) if 'root_id' in reductions else set())==expected_roots
        for r in reductions.to_dict('records'):
            e=economics[r['reference_epoch']];target=c.floorlot(r['existing_qty']*factor,int(e['round_lot']));compare(r['joint_scale'],factor,'all_reduce_scale');assert r['target_existing_qty']==target and r['qty_cap']==r['existing_qty']-target;reduce_count+=1
    return dict(rows=len(budgets),new_allocations=new_count,existing_reductions=reduce_count,selected_event_records=len(expected))

def map_request(reason):return {'held_lifecycle':'lifecycle_exit','anchor_canonical_missing':'observation_exit_requested','anchor_canonical_changed':'liquidity_reference_changed'}.get(reason,reason)

def rejection_equivalence(budgets,rejections):
    """Critical IDs/numeric/state semantics; collect only display-only differences."""
    expected=budgets.loc[pd.to_numeric(budgets.D_qty).eq(0)].set_index('budget_id').sort_index()
    actual=rejections.set_index('budget_id').sort_index();assert expected.index.tolist()==actual.index.tolist(),'rejection identities altered or omitted'
    numeric_fields=set(NUMERIC)|{'u_equity','existing_risk','existing_buffered_margin','unit_risk_u','unit_margin_u','unit_fee_reserve_u','target_qty_unscaled','joint_scale','target_qty_prefloor','qty_cap','original_qty_cap','allocated_risk','allocated_buffered_margin','allocated_fee','D_qty','D_unit_risk','D_unit_margin_plus_fee','existing_qty','target_existing_qty','capacity_entry_qty_u','u_gross_capacity_qty','score'}
    states={'event_id','root_id','mother_event_id','product_id','family_id','reference_epoch','anchor_epoch','u_date','execution_date','account_id','scenario','budget_kind','budget_state','D_state'}
    warnings=[]
    for col in sorted(set(expected)|set(actual)):
        if col not in expected or col not in actual:
            present=expected[col] if col in expected else actual[col]
            if present.map(lambda v:v is None or pd.isna(v) or v=='').all():continue
            assert col not in numeric_fields|states,('critical rejection column absent',col)
            warnings.append(dict(kind='display_column_difference',column=col));continue
        a=expected[col];b=actual[col]
        if col in numeric_fields:
            av=pd.to_numeric(a.replace('',np.nan),errors='raise');bv=pd.to_numeric(b.replace('',np.nan),errors='raise');compare(av,bv,'rejections_numeric_'+col,atol=1e-10,rtol=1e-10)
        else:
            normalize=lambda x:'' if x is None or pd.isna(x) else str(x).lower() if isinstance(x,(bool,np.bool_)) or str(x).lower() in('true','false') else str(x)
            aa=a.map(normalize);bb=b.map(normalize);different=aa.ne(bb)
            if different.any():
                assert col not in states,('critical rejection state differs',col,int(different.sum()))
                warnings.append(dict(kind='display_value_difference',column=col,rows=int(different.sum())))
    return warnings

def account_native_and_capacity(directory,signals,mothers,store,economics,summary,cost):
    c=CASH_HELPER;fills=c.csv(directory/'fills.csv.gz');positions=c.csv(directory/'positions.csv.gz');roots=pd.concat([c.csv(directory/'closed.csv.gz'),c.csv(directory/'open.csv.gz')],ignore_index=True).set_index('root_id');refs={(r.product_id,int(r.u_index)):r.reference_epoch for r in mothers.itertuples(index=False)};lookup=store.index
    c.numeric(fills,['reference_price','qty']);c.numeric(positions,['mark','SL0','boundary_next','stale_days']);pos=positions.set_index(['root_id','date'])
    for r in roots.to_dict('index').values():
        sig=signals.loc[r['event_id']];assert r['anchor_epoch']==sig.anchor_epoch and r['epoch']==sig.reference_epoch;compare(float(r['SL0']),float(r['entry_reference'])-.25*sig.N_u,'all_root_initial_stop',atol=1e-11)
    for r in positions.itertuples(index=False):
        root=roots.loc[r.root_id];sig=signals.loc[r.event_id];k=lookup[r.date];bar=store.get((r.epoch,r.date));valid=legal_bar(bar)
        if r.mark_state=='stale':assert not valid and r.force_next=='research_deferred_liquidation'
        else:
            assert valid;compare(r.mark,bar[3],'all_native_position_close',atol=0,rtol=0);s=store.series[r.epoch];j=store.locate(r.epoch,k);compare(r.boundary_next,max(float(root.SL0),float(s['low20'][j])),'all_held_own_boundary',atol=1e-10)
            prior_day=store.calendar[k-1] if k else ''
            previous=pos.loc[(r.root_id,prior_day)] if (r.root_id,prior_day) in pos.index else None
            old_boundary=float(previous.boundary_next) if previous is not None else max(float(root.SL0),float(sig.low20_u))
            assert previous is None or not previous.force_next,('mandatory forced exit omitted',r.root_id,r.date)
            assert bar[0]>old_boundary and bar[2]>old_boundary,('mandatory stop omitted',r.root_id,r.date)
            expected=map_request(request(None,sig.anchor_epoch,refs.get((r.product_id,k),''),k+1,int(float(root.expiry))));assert (r.force_next or None)==expected,('all_anchor_close_request',r.root_id,r.date,r.force_next,expected)
    for r in fills.to_dict('records'):
        bar=store.get((r['epoch'],r['date']));assert legal_bar(bar);k=lookup[r['date']];root=roots.loc[r['root_id']];sig=signals.loc[r['event_id']];reference=float(r['reference_price']);prior_date=store.calendar[k-1]if k else''
        if r['side']=='BUY':
            assert r['date']==sig.planned_execution_date;compare(reference,bar[0],'native_buy_open',atol=0,rtol=0);assert 2*float(r['qty'])<=capacity(store.get((r['epoch'],sig.u_date))[4],economics[r['epoch']]['round_lot'])[0]
            continue
        prior=pos.loc[(r['root_id'],prior_date)]if(r['root_id'],prior_date)in pos.index else None;force=(str(prior.force_next)or None)if prior is not None else None
        boundary=float(prior.boundary_next)if prior is not None else max(float(root.SL0),float(sig.low20_u))
        if r['reason']=='risk_margin_joint_reduction':assert not force;compare(reference,bar[0],'native_reduce_open',atol=0,rtol=0)
        elif force:assert r['reason']==force;compare(reference,bar[0],'native_persistent_forced_open',atol=0,rtol=0)
        elif bar[0]<=boundary:assert r['reason']=='gap_stop';compare(reference,bar[0],'native_gap_open',atol=0,rtol=0)
        else:assert r['reason']=='stop_boundary'and bar[2]<=boundary;compare(reference,boundary,'native_boundary_exit',atol=1e-10)
    expected=audit_capacity_rows(fills,store,store.calendar,economics);saved=c.csv(directory/'capacity_audit.csv.gz');assert len(saved)==len(expected)
    unknown_roots=set()
    for r,e in zip(saved.to_dict('records'),expected):
        f=fills.iloc[e['fill_sequence_index']];assert r['root_id']==f.root_id and r['account_id']==f.account_id and int(r['fill_sequence'])==e['fill_sequence_index']and r['epoch']==e['epoch']and r['fill_date']==e['date']and r['capacity_reference_date']==e['previous_date']and r['side']==f.side and r['reason']==f.reason
        for a,b in [('capacity_reference_volume','reference_volume'),('capacity_cap_qty','gross_cap'),('prior_same_epoch_day_gross_qty','prior_gross_qty'),('fill_qty','qty'),('cumulative_same_epoch_day_gross_qty','cumulative_gross_qty')]:compare(float(r[a])if r[a]!=''else np.nan,e[b]if e[b]is not None else np.nan,'all_gross_capacity_'+a,atol=0,rtol=0)
        assert(r['capacity_state']=='execution_capacity_unknown')==e['execution_capacity_unknown']
        if e['execution_capacity_unknown']:unknown_roots.add(r['root_id'])
    budgets=c.csv(directory/'reservations.csv.gz');c.numeric(budgets,['qty_cap','D_qty','allocated_risk','allocated_buffered_margin','allocated_fee','existing_qty','target_existing_qty'])
    for b in budgets.loc[budgets.budget_kind.eq('new_entry')].to_dict('records'):
        sig=signals.loc[b['event_id']];bar=store.get((sig.reference_epoch,b['execution_date']));qty=0;state=b['budget_state']
        if b['qty_cap']>0:
            if not legal_bar(bar):state='entry_execution_unknown'
            elif bar[0]<=sig.low20_u:state='stale_breakout_cancel_at_open'
            elif bar[0]-.25*sig.N_u<=0:state='invalid_initial_risk_cancel'
            else:
                e=economics[sig.reference_epoch];R,M,F,buy=c.estimate(bar[0],sig.N_u,e,cost,.25);unit=buy[0]*e['contract_multiplier']*c.econ_rate(e,cost)+buy[1];L=int(e['round_lot']);qty=min(b['qty_cap'],c.floorlot(b['allocated_risk']/R,L),c.floorlot((b['allocated_buffered_margin']+b['allocated_fee'])/unit,L));state='own_open_allocation_insufficient' if qty==0 else 'entered' if qty==b['qty_cap'] else 'entered_reduced_own_allocation'
        assert b['D_qty']==qty and b['D_state']==state,('all D entry decisions',b['budget_id'],b['D_state'],state)
        entered=fills.loc[fills.side.eq('BUY')&fills.budget_id.eq(b['budget_id'])];assert len(entered)==int(qty>0)
        if qty:assert float(entered.iloc[0].qty)==qty
    for b in budgets.loc[budgets.budget_kind.eq('existing_position_reduction')].to_dict('records'):
        bar=store.get((b['reference_epoch'],b['execution_date']));k=lookup[b['execution_date']];prior=pos.loc[(b['root_id'],store.calendar[k-1])];desired=b['existing_qty']-b['target_existing_qty']
        if not legal_bar(bar):assert b['D_state']=='missing_quote_deferred_exit' and b['D_qty']==0
        elif prior.force_next:assert b['D_state']=='forced_full_exit_priority' and b['D_qty']==b['existing_qty']
        elif desired>0:
            assert b['D_state']=='executed_reduction' and b['D_qty']==desired;reduced=fills.loc[fills.side.eq('SELL')&fills.budget_id.eq(b['budget_id'])&fills.reason.eq('risk_margin_joint_reduction')];assert len(reduced)==1 and float(reduced.iloc[0].qty)==desired
        else:assert b['D_state']=='scheduled_reduction' and b['D_qty']==0
    unknown_entry=c.csv(directory/'entry_execution_unknown.csv.gz');missing=budgets.loc[budgets.D_state.eq('entry_execution_unknown')];assert set(missing.budget_id)==set(unknown_entry.budget_id)
    for r in unknown_entry.to_dict('records'):
        sig=signals.loc[r['event_id']];assert not legal_bar(store.get((sig.reference_epoch,r['date'])))and r['date']==sig.planned_execution_date and not fills.budget_id.eq(r['budget_id']).any()
    for root_id,r in roots.to_dict('index').items():assert(str(r['execution_capacity_unknown']).lower()in('true','1'))==(root_id in unknown_roots)
    execution=bool(unknown_roots or len(unknown_entry));assert summary['execution_unknown']==execution and summary['capacity_unknown_roots']==len(unknown_roots)and summary['entry_execution_unknown']==len(unknown_entry)and summary['unknown_capacity_fills']==sum(x['execution_capacity_unknown']for x in expected)
    rejects=c.csv(directory/'rejections.csv.gz');presentation_warnings=rejection_equivalence(budgets,rejects)
    return dict(native_fill_references_checked=len(fills),native_position_marks_boundaries_requests_checked=len(positions),capacity_fills_checked=len(expected),capacity_unknown_roots=len(unknown_roots),entry_execution_unknown=len(unknown_entry),execution_unknown=execution,all_rejections_preserved=len(rejects),presentation_warnings=presentation_warnings,additional_SQL=0,strategy_replay=False)

def fixed_gate(points,held,stale,positive_wealth,execution_unknown):
    values=list(points.values());p=points[('primary_2020','stress')];returns=p['return_percentage_point_difference']>0 and all(v['return_percentage_point_difference']>=0 for k,v in points.items()if k!=('primary_2020','stress'));dds=[v['drawdown_percentage_point_difference']for v in values];known=all(x is not None and finite(x)for x in dds);dd=all(x>=0 for x in dds if x is not None and finite(x));ci=p['ci95_low']is not None and finite(p['ci95_low'])and p['ci95_low']>0;own=all(finite(v['active_total_return_pct'])and v['active_total_return_pct']>0 for v in values);h={k:held['groups'][k]for k in('holdout_0','holdout_1')};hn=all(v['nominal_pass']is True for v in h.values());hu=any(v['unknown_differential_selected_events']>0 or v['status']=='unknown'for v in h.values());nominal=bool(returns and known and dd and ci and own and positive_wealth)
    if all(v['identification']=='all_empty_unidentified'for v in values):status='all_empty_unidentified'
    elif not(returns and dd and ci and hn and own and positive_wealth):status='unsupported'
    elif not known:status='unknown_empty_reference_DD'
    elif stale:status='unknown_historical_stale'
    elif hu:status='unknown_differential_held_outcome'
    else:status='supported_research_model_only'
    if execution_unknown and status=='supported_research_model_only':status='unknown_execution_capacity_or_entry'
    return dict(status=status,cash_nominal_pass=nominal,held_known_nominal_pass=bool(hn),B_own_returns_positive_in_all_four=bool(own),actual_wealth_positive=bool(positive_wealth),nominal_pass=bool(nominal and hn and not execution_unknown),financial_unknown=bool(stale or not known or execution_unknown),signal_unknown_main=False,held_signal_unknown=bool(hu),signal_label_uncertainty_is_not_cash_exposure=True,goal_complete=False,production_qualified=False,increased_betting_qualified=False,independent_actual_review_required=True,no_automatic_promotion=True,execution_unknown=bool(execution_unknown),any_historical_stale=bool(stale))

def review_cash(manifest,protocol,actions,mothers,choices,held,store,economics,out,cash,diag):
    global ACTIVE_POSITIONS
    directory=Path(manifest['terminal']['path']).parent;cash.review_budgets=review_capped_budgets;families=sorted(mothers.family_id.unique());saved_diag=json.loads((directory/'diagnostics.json').read_text());fy=diag._read(directory,'family_year_including_zero');annual=diag._read(directory,'annual_slices');summary_table=diag._read(directory,'account_summaries');capacity_table=cash.csv(directory/'capacity_summary.csv.gz');all_accounts=[];summaries={};daily={};logs={};count={};family_expected=[];selected_counts={}
    for arm in ARMS:
        selected=choices.loc[choices.arm.eq(arm)&choices.selected.eq(1)];selected_counts[arm]=len(selected);sig=actions.set_index('action_id',drop=False).loc[selected.chosen_action_id].copy();sig['potential']=1;sig['planned_execution_date']=[store.calendar[int(k)+1]if int(k)+1<len(store.calendar)else''for k in sig.u_index];sig=sig.set_index('event_id',drop=False)
        assert sig.index.is_unique and not sig.duplicated(['family_id','u_date']).any()
        for window in WINDOWS:
            bounds=protocol['cash']['windows'][window];schedule=dict(id=window,start=bounds[0],end=bounds[1])
            for cost in COSTS:
                key=(arm,window,cost);name='NARROW_'+arm+'_'+window+'_'+cost;folder=directory/name;ACTIVE_POSITIONS=cash.csv(folder/'positions.csv.gz')
                if name in REUSED_LEDGERS:
                    prior_ledger=REUSED_LEDGERS[name];account=json.loads(bound(prior_ledger));assert account['account_id']==name
                    progress(out,'ledger_reused_'+name,dict(evidence=prior_ledger,accepted_ledger=account))
                else:
                    account=cash.review_account(folder,cost,schedule,protocol,sig,economics,store.calendar,.25);progress(out,'ledger_'+name,account)
                summary=account['summary'];summaries[key]=summary
                extra=account_native_and_capacity(folder,sig,mothers,store,economics,summary,cost);account['native_anchor_capacity']=extra;progress(out,'native_policy_capacity_'+name,extra)
                saved_fy=fy.loc[fy.arm.eq(arm)&fy.window.eq(window)&fy.cost.eq(cost)];d,l,n,expected_fy=diag._account(folder,summary,saved_diag[name],saved_fy,families);diag._daily_summary(d,summary,1000000.)
                daily[key]=d;logs[key]=l;count[name]=n;family_expected.append(expected_fy.assign(arm=arm,window=window,cost=cost));account['diagnostics']=n
                row=summary_table.loc[summary_table.arm.eq(arm)&summary_table.window.eq(window)&summary_table.cost.eq(cost)];assert len(row)==1
                for field,value in summary.items():
                    if not isinstance(value,(dict,list)):diag._fields(row.iloc[0].to_dict(),{field:value},'account_summary_table')
                rows=annual.loc[annual.account.eq(name)].sort_values('year');assert len(rows)==len(saved_diag[name]['annual_slices'])
                for r,e in zip(rows.to_dict('records'),saved_diag[name]['annual_slices']):diag._fields(r,e,'all_annual_slices')
                caprow=capacity_table.loc[capacity_table.account.eq(name)];assert len(caprow)==1
                for field in('execution_unknown','unknown_capacity_fills','capacity_unknown_roots','entry_execution_unknown'):
                    value=summary[field];actual=caprow.iloc[0][field];assert(str(actual).lower()in('true','1'))==value if isinstance(value,bool)else int(actual)==value
                # Independent gap and loss-R diagnostics use own action N, never 2N.
                fills=cash.csv(folder/'fills.csv.gz');roots=pd.concat([cash.csv(folder/'closed.csv.gz'),cash.csv(folder/'open.csv.gz')],ignore_index=True).set_index('root_id');gaps=[]
                for r in fills.loc[fills.side.eq('SELL')&fills.reason.eq('gap_stop')].to_dict('records'):
                    root=roots.loc[r['root_id']];loss=(float(root.entry_reference)-float(r['reference_price']))/(.25*sig.loc[r['event_id'],'N_u']);gaps.append(dict(event_id=r['event_id'],date=r['date'],gross_loss_R=loss,qty=int(float(r['qty'])),realized_gross=float(r['realized_gross']),exit_fee=float(r['fee'])))
                nested(saved_diag[name]['gap_stop_fills'],gaps,'all_gap_stop_fills');assert saved_diag[name]['gap_stop_exceeds_1R']==sum(g['gross_loss_R']>1 for g in gaps)
                all_accounts.append(account);progress(out,'cash_'+name,account)
    assert len(all_accounts)==8 and set(saved_diag)=={a['account_id']for a in all_accounts}
    total=diag._read(directory,'family_total_including_zero');cols=['arm','window','cost','family_id'];measures=['net_equity_contribution','fee','slippage','fill_count','filled_qty'];expected=pd.concat(family_expected).groupby(cols)[measures].sum().sort_index();actual=total.set_index(cols).sort_index();assert actual.index.tolist()==expected.index.tolist()
    for c in measures:compare(actual[c],expected[c],'all95_family_total_'+c)
    comparisons=diag._read(directory,'comparisons');distributions=diag._read(directory,'bootstrap_distributions');assert len(comparisons)==4 and not comparisons.duplicated(['window','cost']).any()and set(comparisons.contrast)=={'B_minus_A'}and len(distributions)==2000;assert set(distributions)=={w+'_'+c+'_B_minus_A'for w in WINDOWS for c in COSTS}
    points={}
    for window in WINDOWS:
        dates=daily[('A',window,'base')].date.tolist();assert all(d.date.tolist()==dates for k,d in daily.items()if k[1]==window);index=np.load(io.BytesIO(bound(protocol['bootstrap_indices'][window])),allow_pickle=False);assert index.shape==(2000,len(dates))and index.dtype.kind in'iu'and index.min()>=0 and index.max()<len(dates)
        for cost in COSTS:
            a,b=('B',window,cost),('A',window,cost);active,reference=summaries[a],summaries[b];point=dict(active_total_return_pct=active['total_return_pct'],reference_total_return_pct=reference['total_return_pct'],return_percentage_point_difference=active['total_return_pct']-reference['total_return_pct'],drawdown_percentage_point_difference=None if reference['fills']==0 else active['max_drawdown_pct']-reference['max_drawdown_pct'],dd_comparison_state='NA_empty_reference'if reference['fills']==0 else'active_reference',identification='all_empty_unidentified'if active['fills']==reference['fills']==0 else'observed_cash_comparison')
            if logs[a]is None or logs[b]is None:values=np.full(2000,np.nan);point.update(status='survival_failure_no_log_repair',ci95_low=None,ci95_high=None)
            else:
                delta=logs[a]-logs[b];values=delta[index].mean(axis=1);lo,hi=np.quantile(values,[.025,.975]);point.update(status='valid',mean_daily_log_difference=float(delta.mean()),cumulative_log_difference=float(delta.sum()),ci95_low=float(lo),ci95_high=float(hi))
            row=comparisons.loc[comparisons.window.eq(window)&comparisons.cost.eq(cost)];assert len(row)==1;diag._fields(row.iloc[0].to_dict(),point,'all4_comparison');compare(distributions[window+'_'+cost+'_B_minus_A'],values,'all2000_paired_bootstrap',atol=1e-12);points[(window,cost)]=point
    stale=any(v['stale_days']>0 for v in count.values());execution=any(a['native_anchor_capacity']['execution_unknown']for a in all_accounts);gate=fixed_gate(points,held,stale,all(l is not None for l in logs.values()),execution);nested(json.loads((directory/'continuation_gate.json').read_text()),gate,'fixed_gate_with_capacity_unknown')
    identification=json.loads((directory/'signal_identification.json').read_text());assert identification['main_parent_rows_per_arm']==161014 and identification['full_mother_rows']==399252 and identification['selected_actions']==selected_counts and identification['future_label_states_not_used_for_cash_eligibility']is True;nested(identification['held_groups'],held['groups'],'held_groups_disclosed')
    disclosure=json.loads((directory/'budget_and_tick_disclosure.json').read_text());assert disclosure['bootstrap_indices']==protocol['bootstrap_indices']and disclosure['bootstrap_indices_regenerated']is False and disclosure['no_gap_loss_cap']is True and disclosure['no_actual_orderbook_execution_proof']is True and disclosure['A_curve_equals_old070_required']is False
    assert disclosure['reservation_records']==sum(a['budgets_checked']['rows']for a in all_accounts)
    return all_accounts,dict(accounts_checked=8,common_date_contrasts_checked=4,bootstrap_repetitions=2000,block_length=252,indices_regenerated=False,gate=gate,presentation_warnings=[dict(account=a['account_id'],**w) for a in all_accounts for w in a['native_anchor_capacity']['presentation_warnings']],annual_family_concentration_gap_unknown_checked=True,orderbook_execution_established=False,partial_2026_explicit=True)

def same_binding(a,b):return all(a.get(k)==b.get(k)for k in('path','bytes','sha256'))

def closure(args,out):
    schemas={'dataset':'stage129_contract_choice_dataset_v1','fit':'stage130_contract_choice_fit_v1','cash':'stage131_contract_choice_cash_v1'};manifests={};bindings={}
    for role in('dataset','fit','cash'):
        b=binding(getattr(args,role+'_manifest'));assert b['sha256']==getattr(args,role+'_sha256'),(role,'exact root manifest');m=json.loads(bound(b));assert m['schema']==schemas[role]and m['mode']=='actual'and m['status']=='completed'and m['protocol']['sha256']==PROTOCOL_SHA
        assert m['terminal']['sha256']==getattr(args,role+'_terminal_sha256');terminal=json.loads(bound(m['terminal']));assert terminal['status']=='completed'and terminal['exit_code']==0
        counts={'dataset':dict(native_source_queries=1,new_cash_accounts=0,actual_fit_calls_completed=0,downloads=0,whole_database_hashes=0),'fit':dict(native_source_queries=0,actual_fit_calls_attempted=6,actual_fit_calls_completed=6,cash_replays=0,downloads=0),'cash':dict(native_source_queries=1,cash_accounts_started=8,new_cash_accounts=8,actual_model_fit_calls=0,downloads=0,new_labels=0,whole_database_hashes=0,old_baseline_replays=0)}[role]
        for k,v in counts.items():assert terminal[k]==v,(role,'terminal count',k)
        auth=json.loads(bound(m['authorization']));expected=dict(schema='stage128_exact_root_authorization_v1',stage=role,authorized_by='root',exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(Path(b['path']).parent))
        for k,v in expected.items():assert auth[k]==v,(role,'auth',k)
        assert sorted(auth['source_bundle'],key=lambda x:x['path'])==sorted(m['source_bundle'],key=lambda x:x['path'])
        if role!='dataset':assert auth['input_bindings']==m['input_bindings']
        for s in m['source_bundle']:bound(s)
        values=m['artifacts'];values=list(values.values())if isinstance(values,dict)else values;paths=set()
        for a in values:
            assert a['path']not in paths and str(Path(a['path']).resolve()).startswith(str(Path(b['path']).parent)+'/');paths.add(a['path']);bound(a)
        manifests[role]=m;bindings[role]=dict(manifest=b,terminal=m['terminal'],authorization=m['authorization'],source_bundle=m['source_bundle'],artifact_count=len(paths))
    protocol=json.loads(bound(manifests['dataset']['protocol']));assert protocol['stage']==128 and protocol['line_id']==LINE.name and protocol['scope']==dict(all_states_retained=True,catalog_products=98,end='2026-10-16',exchanges=6,families=95,mother_dates=4074,mother_rows=399252,start='2010-01-04')
    for role in('fit','cash'):assert manifests[role]['protocol']==manifests['dataset']['protocol']
    d,f,c=manifests['dataset'],manifests['fit'],manifests['cash'];assert same_binding(f['input_bindings']['dataset_manifest'],bindings['dataset']['manifest'])and same_binding(f['input_bindings']['dataset_terminal'],d['terminal'])and f['cash_eligible']is True
    for role in('actions','common','mothers'):assert same_binding(f['input_bindings'][role],artifact(d,role))
    assert same_binding(c['input_bindings']['dataset_manifest'],bindings['dataset']['manifest'])and same_binding(c['input_bindings']['fit_manifest'],bindings['fit']['manifest'])
    for role in('actions','mothers'):assert same_binding(c['input_bindings'][role],artifact(d,role))
    for role in('choices_main','held_diagnostic'):assert same_binding(c['input_bindings'][role],artifact(f,role))
    assert c['bootstrap_indices']==protocol['bootstrap_indices']and c['new_cash_accounts']==8 and c['native_source_queries']==1 and c['actual_model_fit_calls']==0
    for b in protocol['source_bindings']:bound(b)
    write(out/'input_closure.json',bindings);return manifests,bindings,protocol

def independent_helpers():
    for name,sha in HELPERS.items():assert binding(LINE/'tools'/name)['sha256']==sha,('independent helper changed',name)
    import stage102_cash_adapter as cash
    import stage102_cash_diagnostics as diag
    return cash,diag

def resume_verified_source(args,manifests,bindings,protocol,out):
    """Reuse the exact completed source phase; do not repeat features/label paths.

    The first process's compact native arrays were in RAM and died at its checker
    identity assertion. One additional native SELECT rebuilds them for unfinished
    cash reference checks. Both SQLs remain explicitly counted in receipts.
    """
    prior=Path(args.resume_source_review).resolve()
    report_b=binding(prior/'all_child_native_features_labels_states.json')
    terminal_b=binding(prior/'actual_terminal.json')
    assert report_b['sha256']==args.resume_source_report_sha256 and terminal_b['sha256']==args.resume_terminal_sha256
    report=json.loads(bound(report_b));terminal=json.loads(bound(terminal_b));started=json.loads((prior/'actual_started.json').read_text());prior_closure=json.loads((prior/'input_closure.json').read_text())
    assert terminal['status']=='failed' and terminal['exit_code']==1 and terminal['new_SQL']==1 and terminal['full_review_completions']==0
    assert "('prospective winner'," in terminal['error'] and not (prior/'review_receipt.json').exists()
    for role in('dataset','fit','cash'):
        assert same_binding(prior_closure[role]['manifest'],bindings[role]['manifest']) and same_binding(prior_closure[role]['terminal'],bindings[role]['terminal'])
        for suffix in('manifest','sha256','terminal_sha256'):assert started['exact_root_inputs'][role+'_'+suffix]==getattr(args,role+'_'+suffix)
    old_source=next(b for b in started['checker_sources']if Path(b['path']).name=='stage132_contract_choice_review.py')
    assert old_source['sha256']==args.resume_checker_sha256
    snapshot=prior/'checker_snapshot'/'stage132_contract_choice_review.py';old_text=snapshot.read_text();assert hashlib.sha256(old_text.encode()).hexdigest()==old_source['sha256']
    old_nodes={n.name:ast.dump(n,include_attributes=False)for n in ast.parse(old_text).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))};new_nodes={n.name:ast.dump(n,include_attributes=False)for n in ast.parse(Path(__file__).read_text()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    phase_functions=['finite','positive','compare','capacity','request','legal_bar','NativeBars','database_state','indicator_arrays','read_native_once','own_features','pair_pools','maturity_features','qualified','lifecycle','audit_label_path','calendar_from_protocol','review_dataset']
    for name in phase_functions:assert old_nodes[name]==new_nodes[name],('reused source verifier changed',name)
    assert report['child_rows_checked']==report['all_label_states_checked']==manifests['dataset']['action_rows']==1552456 and report['mother_rows_checked']==399252 and report['common_values_checked']==1552456*26 and report['child_population_complete']is True and report['all_own_feature_and_peer_pool_rows_checked']is True
    assert report['native']['native_source_queries']==1 and sum(report['policy_states'].values())==1552456
    dataset=manifests['dataset'];mothers=table(artifact(dataset,'mothers'));numeric(mothers,['sequence_index','u_index'])
    keep=list(dict.fromkeys(NUMERIC+['action_id','event_id','actual_epoch','reference_epoch','mother_event_id','anchor_epoch','product_id','family_id','u_date','label_state','label_known_date','participation_state','economics_status','capacity_state','observation_state','u_ineligibility_reason','cancel_reason','unknown_reason']))
    raw=bound(artifact(dataset,'actions'));header=pd.read_csv(io.BytesIO(raw),compression='gzip',nrows=0).columns
    actions=pd.read_csv(io.BytesIO(raw),compression='gzip',usecols=[c for c in keep if c in header],dtype=str,keep_default_na=False,float_precision='round_trip');del raw;numeric(actions,NUMERIC)
    with np.load(io.BytesIO(bound(artifact(dataset,'common'))),allow_pickle=False)as z:common=z['common'].copy();columns=z['columns'].tolist()
    assert len(actions)==1552456 and common.shape==(1552456,26)and columns==protocol['features']['common_columns']
    bridge,calendar=calendar_from_protocol(protocol);economics=json.loads(bound(bridge['economic_projection']))['instruments'];store,reconstructed=read_native_once(bridge['database'],calendar,out)
    assert reconstructed['database_before']==report['native']['database_before'] and reconstructed['database_after']==report['native']['database_after']
    continuation=dict(schema='stage132_checker_identity_fix_continuation_v1',prior_failed_review=str(prior),prior_terminal=terminal_b,accepted_source_phase=report_b,prior_checker_source=old_source,source_phase_functions_AST_unchanged=phase_functions,exact_phase_input_bindings=bindings,new_source_feature_label_passes=0,native_reconstruction_for_unfinished_cash=reconstructed,prior_review_SQL=1,this_continuation_SQL=1,cumulative_review_SQL=2,cumulative_dataset_cash_review_SQL=4,original_budget_was_total3=True,budget_exception='root explicitly permits one extra read because prior compact native state was not persisted after checker assertion; no strategy or financial rerun',new_research_fit=0,new_research_cash=0,old_failed_terminal_preserved=True,goal_complete=False)
    write(out/'continuation_receipt.json',continuation)
    reused=dict(report,source_phase_reused_from=report_b,original_failed_review_terminal=terminal_b,source_feature_label_passes_this_process=0,native_reconstruction_this_process=reconstructed,cumulative_review_SQL=2)
    return actions,mothers,common,columns,store,economics,reused

def persist_native_cache(store,out,database):
    """Simple local recovery cache, avoiding another SQL for report-only issues."""
    epochs=sorted(store.series);lengths=[len(store.series[e]['days'])for e in epochs];offsets=np.r_[0,np.cumsum(lengths)];payload=dict(epochs=np.asarray(epochs,dtype='U40'),offsets=offsets)
    for key in('days','values','accepted','valid','N','low20','run'):payload[key]=np.concatenate([store.series[e][key]for e in epochs],axis=0)
    target=out/'native_store_cache.npz'
    with target.open('xb')as f:np.savez(f,**payload)
    cache=dict(schema='stage132_native_store_recovery_cache_v1',file=binding(target),database=database,native_epochs=len(epochs),native_rows=int(offsets[-1]),purpose='local recovery only; no research or second native read',native_SQL_for_cache=0)
    write(out/'native_store_cache.json',cache);return cache

def restore_native_cache(cache_binding):
    meta=json.loads(bound(cache_binding));assert meta['schema']=='stage132_native_store_recovery_cache_v1'and meta['native_rows']==1552456 and meta['native_epochs']==9520
    before=database_state(meta['database']['path'])
    for k,v in before.items():assert meta['database'][k]==v,('cached native snapshot',k)
    # Calendar itself is the accepted original5587 exact source calendar.
    protocol=json.loads((LINE/'outputs/stage128_contract_choice_protocol/protocol.json').read_text());_,calendar=calendar_from_protocol(protocol);store=NativeBars(calendar)
    with np.load(io.BytesIO(bound(meta['file'])),allow_pickle=False)as z:
        epochs=z['epochs'].tolist();offsets=z['offsets'];flat={k:z[k]for k in('days','values','accepted','valid','N','low20','run')}
        assert len(epochs)==9520 and offsets[0]==0 and offsets[-1]==1552456
        for i,e in enumerate(epochs):store.series[e]={k:a[int(offsets[i]):int(offsets[i+1])]for k,a in flat.items()}
    after=database_state(meta['database']['path']);assert before==after
    return store,dict(native_source_queries=0,native_contract_days=1552456,native_epochs=9520,database_before=before,database_after=after,database_rehashed=False,cache=cache_binding,cache_file=meta['file'],restored_from_exact_cache=True),meta

def resume_cash_only(args,manifests,bindings,protocol,out):
    global REUSED_LEDGERS
    eb=binding(args.cash_only_evidence);assert eb['sha256']==args.cash_only_evidence_sha256
    evidence=json.loads(bound(eb));assert evidence['schema']=='stage132_cash_only_resume_evidence_v1'
    model_report=json.loads(bound(evidence['models_passed']));held=json.loads(bound(evidence['held_verified']));source_report=json.loads(bound(evidence['source_passed']));old_terminal=json.loads(bound(evidence['prior_failed_terminal']));old_closure=json.loads(bound(evidence['prior_input_closure']));old_source_resume=json.loads(bound(evidence['prior_continuation_receipt']));old_failure=json.loads(bound(evidence['prior_failure']))
    assert old_terminal['status']=='failed'and old_terminal['exit_code']==1 and old_terminal['cumulative_review_SQL']==2 and old_terminal['full_review_completions']==0 and 'zero.equals(saved_reject)'in old_failure['traceback']
    assert model_report['models_checked']==6 and model_report['refits']==0 and model_report['all_unknown_prediction_rows_retained']is True and len(model_report['folds'])==6
    assert source_report['child_rows_checked']==source_report['all_label_states_checked']==1552456 and source_report['common_values_checked']==40363856 and source_report['source_feature_label_passes_this_process']==0
    assert old_source_resume['cumulative_review_SQL']==2 and old_source_resume['new_source_feature_label_passes']==0
    original_report=json.loads(bound(old_source_resume['accepted_source_phase']));assert original_report['child_rows_checked']==1552456 and original_report['all_label_states_checked']==1552456
    for role in('dataset','fit','cash'):assert same_binding(old_closure[role]['manifest'],bindings[role]['manifest'])and same_binding(old_closure[role]['terminal'],bindings[role]['terminal'])
    old_text=bound(evidence['prior_checker_snapshot']).decode();old_nodes={n.name:ast.dump(n,include_attributes=False)for n in ast.parse(old_text).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))};new_nodes={n.name:ast.dump(n,include_attributes=False)for n in ast.parse(Path(__file__).read_text()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    names=['finite','positive','compare','capacity','request','legal_bar','NativeBars','database_state','indicator_arrays','read_native_once','own_features','pair_pools','maturity_features','qualified','lifecycle','audit_label_path','calendar_from_protocol','review_dataset','group_hash','union_intervals','union_weights','weighted_stats','head52','choose','check_choice_rows','choice_increment','outcome','independent_held','nested','review_models']
    for name in names:assert old_nodes[name]==new_nodes[name],('accepted source/model verifier changed',name)
    dataset=manifests['dataset'];mothers=table(artifact(dataset,'mothers'));numeric(mothers,['sequence_index','u_index']);keep=list(dict.fromkeys(NUMERIC+['action_id','event_id','actual_epoch','reference_epoch','mother_event_id','anchor_epoch','product_id','family_id','u_date','label_state','label_known_date','participation_state']))
    raw=bound(artifact(dataset,'actions'));header=pd.read_csv(io.BytesIO(raw),compression='gzip',nrows=0).columns;actions=pd.read_csv(io.BytesIO(raw),compression='gzip',usecols=[c for c in keep if c in header],dtype=str,keep_default_na=False,float_precision='round_trip');del raw;numeric(actions,NUMERIC)
    choices=table(artifact(manifests['fit'],'choices_main'));numeric(choices,['sequence_index','u_index','selected','chosen_action_sequence_index','score','proposed_score']);assert len(mothers)==399252 and len(actions)==1552456 and len(choices)==322028
    bridge,calendar=calendar_from_protocol(protocol);economics=json.loads(bound(bridge['economic_projection']))['instruments']
    args._prior_review_SQL=int(evidence.get('prior_review_SQL',2));args._prior_review_startups=int(evidence.get('prior_review_startups',2))
    if evidence.get('native_cache'):
        assert args._prior_review_SQL==3
        store,native,cache=restore_native_cache(evidence['native_cache'])
        cache_terminal=json.loads(bound(evidence['cache_failed_terminal']));assert cache_terminal['status']=='failed'and cache_terminal['cumulative_review_SQL']==3
        cache_closure=json.loads(bound(evidence['cache_input_closure']))
        for role in('dataset','fit','cash'):assert same_binding(cache_closure[role]['manifest'],bindings[role]['manifest'])and same_binding(cache_closure[role]['terminal'],bindings[role]['terminal'])
        ledger_checker=bound(evidence['cache_checker_snapshot']).decode();old_budget=next(n for n in ast.parse(ledger_checker).body if isinstance(n,ast.FunctionDef)and n.name=='review_capped_budgets');current_budget=next(n for n in ast.parse(Path(__file__).read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='review_capped_budgets');assert ast.dump(old_budget,include_attributes=False)==ast.dump(current_budget,include_attributes=False)
        REUSED_LEDGERS=evidence.get('passed_ledgers',{})
        for b in REUSED_LEDGERS.values():bound(b)
    else:
        store,native=read_native_once(bridge['database'],calendar,out);cache=persist_native_cache(store,out,bridge['database']);REUSED_LEDGERS={}
    assert native['database_before']==source_report['native']['database_before']and native['database_after']==source_report['native']['database_after']
    total_SQL=args._prior_review_SQL+native['native_source_queries']
    continuation=dict(schema='stage132_cash_only_continuation_receipt_v1',exact_evidence=eb,accepted_source_phase=evidence['source_passed'],accepted_model_phase=evidence['models_passed'],accepted_held=evidence['held_verified'],prior_failed_terminal=evidence['prior_failed_terminal'],original_failed_terminal=old_source_resume['prior_terminal'],unchanged_source_model_verifier_AST=names,exact_inputs=bindings,source_feature_label_reruns=0,model_check_reruns=0,new_research_fits=0,new_research_cash=0,native_recovery=native,native_cache=cache,prior_review_SQL=args._prior_review_SQL,this_continuation_SQL=native['native_source_queries'],cumulative_review_SQL=total_SQL,cumulative_dataset_cash_review_SQL=2+total_SQL,budget_exception='prior extra native reads retained in count; cached continuation performs zero new SQL' if evidence.get('native_cache') else 'root permits one extra native read after two checker-only failures; prior in-memory store was unavailable, this read is cached locally',per_account_checkpoints=True,prior_failures_preserved=True,goal_complete=False)
    write(out/'continuation_receipt.json',continuation)
    source=dict(source_report,source_phase_reused_from=evidence['source_passed'],source_feature_label_passes_this_process=0,native_reconstruction_this_process=native,cumulative_review_SQL=total_SQL)
    models=dict(model_report,model_phase_reused_from=evidence['models_passed'],model_check_passes_this_process=0)
    return actions,mothers,choices,held,store,economics,source,models

def review(args):
    global CASH_HELPER
    for key in('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[key]='1'
    from threadpoolctl import threadpool_limits
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=False);started=datetime.now(timezone.utc).isoformat();clock=time.monotonic();status='failed';error=None
    sources=[binding(Path(__file__)),binding(Path(__file__).with_name('test_stage132_contract_choice_review.py'))]+[binding(LINE/'tools'/n)for n in HELPERS]
    write(output/'actual_started.json',dict(schema='stage132_contract_choice_review_started_v1',started_at=started,process_id=os.getpid(),review_startups=1,exact_root_inputs=vars(args),checker_sources=sources,whole_DB_hashes=0,new_SQL_max=1,research_fits=0,research_cash_runs=0))
    snapshots=output/'checker_snapshot';snapshots.mkdir()
    for b in sources:(snapshots/Path(b['path']).name).write_bytes(Path(b['path']).read_bytes())
    try:
        cash,diag=independent_helpers();CASH_HELPER=cash
        manifests,bindings,protocol=closure(args,output);progress(output,'final_exact_input_closure',bindings)
        with threadpool_limits(limits=1):
            if args.cash_only_evidence:
                assert args.cash_only_evidence_sha256 and not args.resume_source_review
                actions,mothers,choices,held,store,economics,dataset,models=resume_cash_only(args,manifests,bindings,protocol,output)
                progress(output,'source_models_accepted_cash_only',dict(source=dataset,models=models))
            else:
                if args.resume_source_review:
                    assert args.resume_source_report_sha256 and args.resume_terminal_sha256 and args.resume_checker_sha256
                    actions,mothers,common,columns,store,economics,dataset=resume_verified_source(args,manifests,bindings,protocol,output)
                    progress(output,'source_phase_reused_no_feature_label_loop',dataset)
                else:
                    actions,mothers,common,columns,store,economics,dataset=review_dataset(manifests['dataset'],protocol,output,cash);progress(output,'all_child_native_features_labels_states',dataset)
                choices,held,models=review_models(manifests['fit'],actions,mothers,common,columns,output);progress(output,'all6_shared_models_scores_choices_held',models)
                del common
            write(output/'independently_verified_held.json',held)
            accounts,diagnostics=review_cash(manifests['cash'],protocol,actions,mothers,choices,held,store,economics,output,cash,diag);progress(output,'all8_cash_ledgers_anchor_capacity_diagnostics',diagnostics)
        assert sources==[binding(b['path'])for b in sources]
        final=dict(schema='stage132_contract_choice_independent_review_v1',completed=True,C=0,I=0,M=len(diagnostics.get('presentation_warnings',[])),review_startups=1,full_review_completions=1,cumulative_review_startups=getattr(args,'_prior_review_startups',2)+1 if args.cash_only_evidence else 2 if args.resume_source_review else 1,checker_sources=sources,input_closure=bindings,dataset_review=dataset,model_review=models,cash_accounts=accounts,diagnostics=diagnostics,held_diagnostic=held,numeric_max_errors=dict(ERRORS,**{'cash_'+k:v for k,v in cash.ERRORS.items()}),execution=dict(new_SQL=int((output/'native_query_started.json').exists()),prior_review_SQL=getattr(args,'_prior_review_SQL',2) if args.cash_only_evidence else 1 if args.resume_source_review else 0,cumulative_review_SQL=getattr(args,'_prior_review_SQL',2)+int((output/'native_query_started.json').exists()) if args.cash_only_evidence else 2 if args.resume_source_review else 1,cumulative_dataset_cash_review_SQL=2+getattr(args,'_prior_review_SQL',2)+int((output/'native_query_started.json').exists()) if args.cash_only_evidence else 4 if args.resume_source_review else 3,source_feature_label_passes_this_process=0 if args.cash_only_evidence or args.resume_source_review else 1,model_check_passes_this_process=0 if args.cash_only_evidence else 1,new_fits=0,new_cash_runs=0,whole_native_strategy_replay=0,old_models=0,old_suites=0,whole_database_hashes=0,network_requests=0),scope_name_alias={'holdout0':'holdout_0','holdout1':'holdout_1'},scope_alias_is_scientific_change=False,research_arithmetic_accepted=True,fixed_package_supported=diagnostics['gate']['status']=='supported_research_model_only',limitations=['重复使用历史数据后的择题风险，非真正未见OOS','日线无法证明开盘成交、极窄损顺序或1%盘口容量','经济快照不是逐日券商真实费用/保证金','自身closed成熟训练存在条件样本选择，未知不补零','共同canonical anchor只检验初开月选择，不含自由续持或自由普通F替换','2000日期块抽样不是2000独立市场周期','开放/历史缺价/容量未知不能用理想PnL消除'],strict_first_publication_PIT_established=False,orderbook_execution_established=False,narrow_stop_is_universal_loss_bound=False,goal_complete=False,production_qualified=False,increased_betting_qualified=False)
        write(output/'review_receipt.json',final);status='completed'
    except BaseException as exc:
        error=f'{type(exc).__name__}: {exc}';write(output/'failure.json',dict(error=error,traceback=traceback.format_exc()));raise
    finally:
        write(output/'actual_terminal.json',dict(status=status,started_at=started,finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,error=error,exit_code=0 if status=='completed'else 1,review_startups=1,cumulative_review_startups=getattr(args,'_prior_review_startups',2)+1 if args.cash_only_evidence else 2 if args.resume_source_review else 1,full_review_completions=int(status=='completed'),prior_review_SQL=getattr(args,'_prior_review_SQL',2) if args.cash_only_evidence else 1 if args.resume_source_review else 0,cumulative_review_SQL=(getattr(args,'_prior_review_SQL',2) if args.cash_only_evidence else 1 if args.resume_source_review else 0)+int((output/'native_query_started.json').exists()),new_SQL=int((output/'native_query_started.json').exists()),research_fits=0,research_cash_runs=0,automatic_retry=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for role in('dataset','fit','cash'):
        for key in('manifest','sha256','terminal-sha256'):parser.add_argument('--'+role+'-'+key,required=True)
    parser.add_argument('--cash-only-evidence')
    parser.add_argument('--cash-only-evidence-sha256')
    parser.add_argument('--resume-source-review')
    parser.add_argument('--resume-source-report-sha256')
    parser.add_argument('--resume-terminal-sha256')
    parser.add_argument('--resume-checker-sha256')
    parser.add_argument('--output',required=True)
    review(parser.parse_args())
