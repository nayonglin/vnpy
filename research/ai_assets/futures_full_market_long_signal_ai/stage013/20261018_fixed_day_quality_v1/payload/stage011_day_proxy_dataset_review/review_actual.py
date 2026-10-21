"""Independent frozen009 table/interval/context and finite original-SQL review."""
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime
from itertools import zip_longest
import ast,csv,gzip,hashlib,io,json,math,sqlite3,struct,time

LINE=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
EXPORT=LINE/'outputs/stage009_day_proxy_dataset/export'
START=datetime.now().astimezone().isoformat();BEGAN=time.monotonic();bindings={}
def read(path,expect=None):
    p=Path(path);raw=p.read_bytes();h=hashlib.sha256(raw).hexdigest()
    if expect:
        assert h==expect['sha256'],('SHA',str(p))
        if 'bytes'in expect:assert len(raw)==expect['bytes']
    bindings[str(p)]=dict(sha256=h,bytes=len(raw));return raw
def load(path,h=None):return json.loads(read(path,dict(sha256=h)if h else None))
def rows(raw):return csv.DictReader(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(raw)),encoding='utf-8',newline=''))
def f(value):
    x=float(value);assert math.isfinite(x);return x
def close(a,b):assert math.isclose(float(a),float(b),rel_tol=1e-11,abs_tol=1e-11),(a,b)
def state(path):
    p=Path(path);s=p.stat();return dict(path=str(p),bytes=s.st_size,mtime_ns=s.st_mtime_ns,inode=s.st_ino,
        wal_present=Path(str(p)+'-wal').exists(),shm_present=Path(str(p)+'-shm').exists())
def scalar_label(bar,D,end,atr,ready):
    if not D:return 'execution_day_unknown',None,None,0
    if D>end:return 'right_censored',None,None,0
    if not ready:return 'history_unready',None,None,0
    if bar is None:return 'missing_D',None,None,0
    o,h,l,c=(float(bar[k])for k in ('open','high','low','close'))
    if not all(math.isfinite(x)and x>0 for x in (o,h,l,c))or not l<=min(o,c)<=max(o,c)<=h:return 'invalid_D_prices',None,None,0
    R=atr/4;sl=o-R;pt=o+4*R
    if sl<=0:return 'nonpositive_stop',None,None,0
    s,p=l<=sl,h>=pt
    if s and p:return 'double_touch_interval',-1.,4.,1
    if s:return 'stop_only',-1.,-1.,0
    if p:return 'profit_only',4.,4.,0
    value=(c-o)/R;return 'day_close',value,value,0
def own_math(bars):
    tr=[max(b['high']-b['low'],abs(b['high']-a['close']),abs(b['low']-a['close']))for a,b in zip(bars,bars[1:])]
    atr=math.fsum(tr)/len(tr);u=bars[-1];c=u['close']
    if not math.isfinite(atr)or atr<=0:return None,atr
    values=[(c-bars[-2]['close'])/atr,(c-bars[-6]['close'])/math.sqrt(5)/atr,(c-bars[0]['close'])/math.sqrt(20)/atr,
        (c-u['open'])/atr,(u['high']-u['low'])/atr,(c-u['low'])/(u['high']-u['low'])if u['high']!=u['low']else .5,
        (u['open']-bars[-2]['close'])/atr,math.fsum(tr[-5:])/5/atr,
        math.log(u['volume']/(math.fsum(x['volume']for x in bars[:-1])/20)),
        (c-max(x['high']for x in bars[:-1]))/atr,atr/c]
    return values,atr

m=load(EXPORT/'manifest.json','ea26675e8322bee8a3c71d4ba0c731055a52a161359c1ac456de628029a5071e')
terminal=load(EXPORT/'actual_terminal.json','8c253db4603cb4027e58344feba601994b7289eacae018718065e51e1ba0ac69')
assert terminal['exit_code']==0 and terminal['actual_build_invocations']==1 and terminal['counts']==m['counts']
assert terminal['manifest_sha256']==bindings[str(EXPORT/'manifest.json')]['sha256']
assert m['dataset']==m['feature_label_csv']==terminal['dataset']
source=LINE/'tools/stage009_day_proxy_dataset.py';test=LINE/'tools/test_stage009_day_proxy_dataset.py'
read(source,dict(sha256='f7e9eaa56bee511e670a0f09175e58321ab358a501b3e0d63a5d6e2b3ddb89c4'))
read(test,dict(sha256='1ee59dd763fb1d54b2bb65b35f36b5690b5d6e8511c0393610f4092f7d79ac51'))
assert m['source_code']['sha256']==terminal['source_sha256']==bindings[str(source)]['sha256']
small={path:read(path,item)for path,item in m['source_bindings'].items()}
protocol=json.loads(small[m['protocol']['path']]);assert m['protocol']['sha256']=='2e5da3da4440223e3ac978256d563b80d5bd4264cec56d4085ed6062d7bad0a4'
observation=json.loads(small[m['opportunity_review']['path']]);assert observation['independent_review']is True
src=json.loads(small[protocol['inputs']['source_bindings']['path']]);db_path=Path(src['database']['path']);before=state(db_path)
for k,v in before.items():assert v==m['database_before'][k]==m['database_after'][k]
assert not before['wal_present']and not before['shm_present']
assert m['database_full_hash_recomputed']is False and m['real_economic_labels_ready']is False and m['financial_ready']is False
assert m['qualified_for_fixed_proxy_experiment']is False and m['publication_pit_certified']is False
data_raw=read(m['dataset']['path'],m['dataset']);audit_raw=read(m['audit_paths']['path'],m['audit_paths'])
panel_path=str(Path(m['opportunity_manifest']['path']).parent/'product_day_opportunities.csv.gz');panel_raw=small[panel_path]
cal_raw=small[src['calendar']['path']];assert cal_raw[:8]==b'\x93NUMPY\x01\x00'
h=struct.unpack('<H',cal_raw[8:10])[0];header=ast.literal_eval(cal_raw[10:10+h].decode('latin1'));assert header['descr']=='<i8'
cal=[f'{x//10000:04d}-{x//100%100:02d}-{x%100:02d}'for(x,)in struct.iter_unpack('<q',cal_raw[10+h:])]
assert cal==sorted(set(cal));target=[x for x in cal if protocol['scope'][0]<=x<=protocol['scope'][1]]
assert target==m['source_calendar_scope_dates']and len(target)==4074
idx={d:i for i,d in enumerate(cal)};prev=dict(zip(cal[1:],cal));succ=dict(zip(cal,cal[1:]))
own=protocol['own_features'];market=protocol['market_features'];identities=['event_id','product_id','product','exchange','u_date','reference_epoch','planned_execution_date','status','direction']
assert own==m['own_features']and market==m['market_features']
counts=Counter();hist=Counter();labels=Counter();years=defaultdict(Counter);per_product=Counter();event_ids=set();ready_points=defaultdict(lambda:defaultdict(list))
audit_expected={};samples={};last_ready={};ready_dates=set();ready_families=set();ready_unknown_sources=0
for p,r in zip_longest(rows(panel_raw),rows(data_raw)):
    assert p is not None and r is not None
    assert all(p[k]==r[k]for k in identities)
    event=r['event_id'];u=r['u_date'];pid=r['product_id'];D=r['planned_execution_date'];family=r['exchange']+'.'+r['product'].removesuffix('_F')
    assert event not in event_ids and r['family_id']==family and D==succ.get(u,'')and u in target
    event_ids.add(event);per_product[pid]+=1;counts['rows']+=1;hist[r['history_state']]+=1;labels[r['label_state']]+=1;year=years[u[:4]];year['rows']+=1
    ready=int(r['feature_ready']);identified=int(r['label_identified']);amb=int(r['path_ambiguous'])
    assert ready in (0,1)and identified in (0,1)and amb in (0,1)
    assert identified<=ready and amb<=identified
    if r['status']=='observed_long_research_opportunity':counts['observed_rows']+=1;audit_expected[event]=(r['history_state'],r['label_state'],r['atr20'],ready,identified,amb,*[r[k]for k in ('gross_lower','gross_upper','proxy_lower','proxy_upper')])
    else:assert not ready and not identified and r['history_state']=='no_reference_observation'
    if ready:
        assert r['history_state']=='ready'and f(r['atr20'])>0
        for k in own:f(r[k])
        ready_points[u][family].append(f(r['r1_atr']));ready_dates.add(u);ready_families.add(family)
        counts['feature_ready']+=1;year['feature_ready']+=1
        if not identified:counts['ready_unknown_label']+=1;ready_unknown_sources+=1
        samples.setdefault('first_'+r['exchange'],r);last_ready[r['exchange']]=r
        if r['product'].endswith('_F'):samples.setdefault(r['product_id'],r)
    else:assert all(r[k]==''for k in own)
    for k in market:f(r[k])
    assert int(r['market_lag_missing'])in (0,1)
    if ready:counts['ready_context_missing']+=int(r['market_lag_missing'])
    if identified:
        assert r['label_known_date']==D and u<D<=protocol['scope'][1]
        lo,hi,pl,pu=(f(r[k])for k in ('gross_lower','gross_upper','proxy_lower','proxy_upper'))
        assert -1.-1e-11<=lo<=hi<=4.+1e-11;close(pl,lo-.2);close(pu,hi-.2)
        if amb:assert r['label_state']=='double_touch_interval'and lo==-1 and hi==4
        else:close(lo,hi)
        counts['label_identified']+=1;counts['ambiguous_identified']+=amb;year['label_identified']+=1;year['ambiguous']+=amb
    else:assert r['label_known_date']==''and all(r[k]==''for k in ('gross_lower','gross_upper','proxy_lower','proxy_upper'))
    for name,match in (('gap',r['history_state']=='source_calendar_gap_rewarm'),('insufficient',r['history_state']=='insufficient_same_epoch_history'),
            ('missing_D',r['label_state']=='missing_D'),('double_touch',r['label_state']=='double_touch_interval'),('profit_only',r['label_state']=='profit_only')):
        if match:samples.setdefault(name,r)
samples.update({'last_'+ex:r for ex,r in last_ready.items()})
assert counts['rows']==399252 and len(per_product)==98 and set(per_product.values())=={4074}
for k in ('rows','observed_rows','feature_ready','label_identified','ready_unknown_label','ambiguous_identified','ready_context_missing'):assert counts[k]==m['counts'][k]
assert dict(hist)==m['counts']['history_states']and dict(labels)==m['counts']['label_states']
assert len(ready_dates)==m['counts']['ready_dates']and len(ready_families)==m['counts']['ready_families']
for y in m['year_counts']:
    assert all(years[str(y['year'])][k]==y[k]for k in ('rows','feature_ready','label_identified','ambiguous'))

# Audit scalar labels over all observed rows; these diagnostic prices are not new source truth.
audit_seen=set()
for a in rows(audit_raw):
    event=a['event_id'];assert event in audit_expected and event not in audit_seen;audit_seen.add(event)
    history,state_value,atr,ready,identified,amb,*values=audit_expected[event]
    assert a['history_state']==history and a['label_state']==state_value
    if atr:close(a['atr20'],atr)
    else:assert a['atr20']==''
    if not ready:continue
    D=a['planned_execution_date'];b=None
    if a['ideal_entry_F']:
        b=dict(open=f(a['ideal_entry_F']),high=f(a['D_high']),low=f(a['D_low']),close=f(a['D_close']))
        close(a['risk_distance'],f(atr)/4);close(a['ideal_stop'],b['open']-f(atr)/4);close(a['ideal_profit'],b['open']+f(atr))
    expected=scalar_label(b,D,protocol['scope'][1],f(atr),True)
    assert expected[0]==state_value and expected[3]==amb
    if identified:
        for actual,value in zip(values,(expected[1],expected[2],expected[1]-.2,expected[2]-.2)):close(actual,value)
assert audit_seen==set(audit_expected)

# Recompute all +4 fields independently from lagged all-ready family values (unknown-D included).
family_means={d:{fam:math.fsum(xs)/len(xs)for fam,xs in groups.items()}for d,groups in ready_points.items()}
def quantile(xs,q):
    position=(len(xs)-1)*q;lo=math.floor(position);hi=math.ceil(position)
    return xs[lo]*(hi-position)+xs[hi]*(position-lo)if lo!=hi else xs[lo]
context_cache={};context_checked=0
for r in rows(data_raw):
    key=(r['u_date'],r['family_id'])
    if key not in context_cache:
        xs=sorted(v for fam,v in family_means.get(prev.get(key[0],''),{}).items()if fam!=key[1])
        context_cache[key]=[quantile(xs,.5),sum(v>0 for v in xs)/len(xs),quantile(xs,.75)-quantile(xs,.25),0]if xs else [0,0,0,1]
    for k,value in zip(market,context_cache[key]):close(r[k],value)
    context_checked+=1

# Exactly 20 shape-stratified original-SQL probes; no producer math or replay imported.
assert len(samples)==20,len(samples)
db=sqlite3.connect(db_path.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON')
SQL=[]
for tag,r in sorted(samples.items()):
    epoch=r['reference_epoch'];u=r['u_date'];D=r['planned_execution_date']
    history=[dict(x)for x in db.execute("SELECT * FROM daily_bars WHERE contract_epoch_id=? AND trade_date>=? AND trade_date<=? ORDER BY trade_date DESC LIMIT 21",(epoch,protocol['scope'][0],u))][::-1]
    assert history and history[-1]['trade_date']==u
    assert all(x['contract_epoch_id']==epoch for x in history)
    if len(history)<21:expected_history='insufficient_same_epoch_history';features=None;atr=None
    elif [x['trade_date']for x in history]!=cal[idx[u]-20:idx[u]+1]:expected_history='source_calendar_gap_rewarm';features=None;atr=None
    else:
        assert all(x['quality_status']=='accepted'and x['volume']>0 for x in history)
        features,atr=own_math(history);expected_history='ready'if features is not None else'zero_or_nonfinite_atr'
    assert expected_history==r['history_state']
    if features is not None:
        close(r['atr20'],atr)
        for k,value in zip(own,features):close(r[k],value)
    D_row=db.execute('SELECT * FROM daily_bars WHERE contract_epoch_id=? AND trade_date=?',(epoch,D)).fetchone()
    label=scalar_label(dict(D_row)if D_row else None,D,protocol['scope'][1],atr,features is not None)
    assert r['label_state']==label[0]
    if label[1]is not None:
        for k,value in zip(('gross_lower','gross_upper','proxy_lower','proxy_upper'),(label[1],label[2],label[1]-.2,label[2]-.2)):close(r[k],value)
    SQL.append(dict(tag=tag,event_id=r['event_id'],epoch=epoch,u=u,D=D,history_rows=len(history),D_found=D_row is not None,
        history_state=expected_history,label_state=label[0],source_rows=len(history)+int(D_row is not None)))
db.close();after=state(db_path);assert before==after
checks=dict(all_399252_identities_preserved=True,feature_ready_distinct_from_label_identified=True,unknown_labels_blank=True,
    all_11_ready_own_features_finite=True,all_4_context_features_independently_recomputed=True,
    lag_context_includes_unknown_D_ready_observations=True,family_mean_dedup_own_family_exclusion=True,
    all_identified_ideal_intervals_recomputed_from_diagnostic_prices=True,cost_budget_not_actual_fees=True,
    known_date_equals_D_close_date_not_midnight_PIT=True,SQL_20_same_epoch_21_calendar_bar_features_and_D_labels_match=True,
    protocol_and_source_closure_match=True,DB_readonly_stat_unchanged=True)
result=dict(schema='stage011_independent_day_proxy_checks_v1',started_at=START,finished_at=datetime.now().astimezone().isoformat(),
    elapsed_seconds=time.monotonic()-BEGAN,counts=dict(counts),history_states=dict(hist),label_states=dict(labels),checks=checks,
    context_rows_checked=context_checked,context_unknown_D_ready_inputs=ready_unknown_sources,
    audit_observed_rows_checked=len(audit_seen),SQL_probes=SQL,SQL_probe_count=len(SQL),SQL_source_rows=sum(x['source_rows']for x in SQL),
    input_output_bindings=bindings,DB_before=before,DB_after=after,DB_full_hash_recomputed=False,
    producer_imported=False,producer_dataset_rebuilds=0,model_fits=0,financial_runs=0,native_runs=0,network_calls=0)
p=OUT/'actual_review_checks.json';assert not p.exists();p.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:v for k,v in result.items()if k not in ('input_output_bindings','SQL_probes')},ensure_ascii=False))
