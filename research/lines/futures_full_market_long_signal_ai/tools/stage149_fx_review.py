"""One independent incremental FX audit. No author imports, SQL, fits or replay.

Accepted130 identities/weights/common scalers and accepted132 mathematical ledger
helpers are inputs already independently accepted. Old control models/books are
identity references plus the new zero-column bridge, never requalified globally.
Actual mode requires root's exact source/input authorization and a fresh folder.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left
from collections import defaultdict
from contextlib import contextmanager
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import time
import traceback
import zipfile

import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
PROTOCOL_SHA = 'be0431bff87dc90d91a9f1b16940c9a6d8112a66d4309879abef46466ce4f270'
REVIEW132_SHA = '7d8b5fd1c1a2d80d2df32632c8b097e9ca15eced9e65de745af40f1e32a3a181'
HELPERS = {'stage132_contract_choice_review.py': REVIEW132_SHA,
 'stage102_cash_adapter.py':'702ad195d988eec4d847289ad9961525a35e65d4146de796073b1ca3c0df9044',
 'stage102_cash_core.py':'4310bdd81375e17406b1773658c582ccb570a25d09b8fa53d15461c76cbb3eaa',
 'stage102_cash_diagnostics.py':'0075f91ba110ea902ee374a917f20433ace66afde9bde755088f2573d09d11cc'}
SCOPES = ('main','holdout_0','holdout_1')
CUTOFFS = ('2020-01-01','2023-01-01')
WINDOWS = ('primary_2020','cold_2023')
COSTS = ('base','stress')
LEDGERS = ('daily','fills','positions','reservations','rejections','closed','open','capacity_audit','entry_execution_unknown')
IDENTITY = ['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
NUMERIC = ['sequence_index','action_sequence_index','mother_sequence_index','u_index','u_action_eligible',
 'entry_capacity_qty','N_u','low20_u','u_close','history_run','lifecycle_index','net_R_stress',
 'selected','chosen_action_sequence_index','score','proposed_score','sample_weight']
VERIFIED = set()
ERRORS = {}


def binding(path):
    p = Path(path).resolve(); digest = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20), b''): digest.update(chunk)
    return dict(path=str(p), bytes=p.stat().st_size, sha256=digest.hexdigest())


def verify(item):
    key = tuple(item[k] for k in ('path','bytes','sha256'))
    if key not in VERIFIED:
        same_binding(binding(item['path']), item); VERIFIED.add(key)
    return Path(item['path'])


def bound(item): return verify(item).read_bytes()


def same_binding(a,b):
    assert all(a.get(k)==b.get(k) for k in ('path','bytes','sha256')), ('exact identity', a, b)


def read_json(item): return json.loads(bound(item))


def table(item, usecols=None):
    return pd.read_csv(verify(item), usecols=usecols, dtype=str, keep_default_na=False, float_precision='round_trip')


def numeric(frame, columns=NUMERIC):
    for c in columns:
        if c in frame: frame[c] = pd.to_numeric(frame[c].replace('',np.nan), errors='raise')
    return frame


def finite(v):
    try: return not isinstance(v,(bool,np.bool_)) and math.isfinite(float(v))
    except (TypeError,ValueError): return False


def flag(v):
    assert str(v).lower() in ('true','false','0','1'), ('boolean', v)
    return str(v).lower() in ('true','1')


def compare(a,b,label,atol=2e-7,rtol=2e-10):
    a,b = np.asarray(a,float),np.asarray(b,float)
    assert a.shape==b.shape and np.array_equal(np.isnan(a),np.isnan(b)), (label,'shape/null')
    assert np.isfinite(a).all()==np.isfinite(b).all() and np.array_equal(np.isfinite(a),np.isfinite(b)), (label,'finite')
    ok=np.isfinite(a)&np.isfinite(b); e=np.abs(a[ok]-b[ok]); maximum=float(e.max()) if e.size else 0.
    ERRORS[label]=max(ERRORS.get(label,0.),maximum)
    assert np.all(e<=atol+rtol*np.abs(b[ok])), (label,maximum)


def fields(actual, expected, label):
    for key,value in expected.items():
        assert key in actual, (label,'missing field',key)
        got=actual[key]
        if isinstance(value,(bool,np.bool_)): assert flag(got)==value,(label,key,got,value)
        elif value is None: assert got is None or got=='' or (isinstance(got,float) and math.isnan(got)),(label,key,got)
        elif isinstance(value,(int,float,np.number)): compare(float(got) if got!='' else np.nan,value,label+'.'+key,atol=1e-8,rtol=2e-9)
        elif isinstance(value,(dict,list)): nested(got,value,label+'.'+key)
        else: assert got==value,(label,key,got,value)


def nested(actual, expected, label):
    if isinstance(expected,dict):
        assert set(actual)==set(expected),(label,'keys',set(actual)^set(expected))
        fields(actual,expected,label)
    elif isinstance(expected,list):
        assert len(actual)==len(expected),(label,'length')
        for a,b in zip(actual,expected): nested(a,b,label)
    elif isinstance(expected,(float,int,np.number)) and not isinstance(expected,(bool,np.bool_)):
        compare(actual,expected,label,atol=1e-8,rtol=2e-9)
    else: assert actual==expected,(label,actual,expected)


def safe(v):
    if isinstance(v,dict): return {str(k):safe(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [safe(x) for x in v]
    if isinstance(v,np.ndarray): return safe(v.tolist())
    if isinstance(v,np.generic): return v.item()
    return v


def write(path,value):
    with Path(path).open('x') as f:
        json.dump(safe(value),f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')


def progress(out,name,value):
    write(out/(name+'.json'),value);print(json.dumps(dict(phase=name,status='completed')),flush=True)


def artifact(manifest, role):
    if isinstance(manifest.get(role),dict) and 'path' in manifest[role]: return manifest[role]
    values=manifest.get('artifacts',[])
    if isinstance(values,dict):
        if role in values:return values[role]
        values=list(values.values())
    found=[b for b in values if b.get('role')==role or b.get('logical_name')==role]
    assert len(found)==1,('one artifact',role)
    return found[0]


def bundle(): return sorted([binding(TOOLS/n) for n in ('stage149_fx_review.py','test_stage149_fx_review.py',*HELPERS)],key=lambda b:b['path'])


def archive_rows(raw):
    """Parse each real source row before looking at missing legs; no skip/fill."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert archive.namelist()==['eurofxref-hist.csv'] and archive.testzip() is None
        source=archive.read('eurofxref-hist.csv').decode('utf-8-sig')
    result=[]
    for original in csv.DictReader(io.StringIO(source)):
        row={str(k).strip():str(v).strip() for k,v in original.items() if k is not None}
        day=datetime.strptime(row['Date'],'%Y-%m-%d').date().isoformat()
        legs={k:float(row[k]) if finite(row.get(k)) else None for k in ('USD','CNY')}
        assert all(v is None or v>0 for v in legs.values()),('invalid source leg',day)
        result.append(dict(date=day,USD_per_EUR=legs['USD'],CNY_per_EUR=legs['CNY'],S=legs['CNY']/legs['USD'] if all(v is not None for v in legs.values()) else None))
    result.sort(key=lambda r:r['date']); assert len(result)==len({r['date'] for r in result})
    return result


def project(rows, dates):
    releases=[r['date'] for r in rows];zone=timezone(timedelta(hours=8));result=[]
    for day in sorted(set(dates)):
        u=datetime.strptime(day,'%Y-%m-%d').replace(tzinfo=zone);n=bisect_left(releases,day)-1
        row=dict(u_date=day,q=np.nan,fx_missing=1,projection_state='missing_adjacent_source',assigned_time='',decision_time=u.replace(hour=15).isoformat())
        for label,index in [('n',n),('d',n-1),('w',n-2)]:
            source=rows[index] if index>=0 else None
            row.update({label+'_date':source['date'] if source else '',label+'_source_row_index':index if source else -1,
                label+'_age_days':(u.date()-datetime.strptime(source['date'],'%Y-%m-%d').date()).days if source else -1,
                label+'_USD_per_EUR':source['USD_per_EUR'] if source else None,label+'_CNY_per_EUR':source['CNY_per_EUR'] if source else None})
        row.update(change_date=row['d_date'],finalization_date=row['n_date'])
        if n>=0:
            assigned=datetime.strptime(releases[n],'%Y-%m-%d').replace(tzinfo=zone)+timedelta(days=1,hours=8)
            row['assigned_time']=assigned.isoformat();assert assigned<=u.replace(hour=15),'assigned after decision'
        if n>=2:
            if all(rows[i]['S'] is not None for i in (n,n-1,n-2)):
                row.update(q=math.log(rows[n-1]['S']/rows[n-2]['S']),fx_missing=0,projection_state='observed_conservative_archive_reconstruction')
            else:row['projection_state']='missing_adjacent_currency_leg'
        result.append(row)
    return pd.DataFrame(result)


def q_stats(q,w):
    q,w=np.asarray(q,float),np.asarray(w,float);ok=np.isfinite(q)
    assert q.shape==w.shape and np.isfinite(w).all() and (w>0).all() and ok.any()
    mean=float(np.sum(q[ok]*w[ok])/np.sum(w[ok]));var=float(np.sum(w[ok]*(q[ok]-mean)**2)/np.sum(w[ok]))
    assert finite(mean) and finite(var) and var>0,'positive finite q variation required'
    return dict(mean=mean,var=var,scale=math.sqrt(var),finite_count=int(ok.sum()))


def design54(common,q,scaler,stats):
    raw=np.asarray(common,float);q=np.asarray(q,float);m=np.asarray(scaler['common']['mean'],float);s=np.asarray(scaler['common']['scale'],float)
    assert raw.shape==(len(q),26) and m.shape==s.shape==(26,) and np.isfinite(m).all() and np.isfinite(s).all() and (s>0).all()
    ok=np.isfinite(raw);qok=np.isfinite(q)
    return np.column_stack([np.where(ok,(raw-m)/s,0.),(~ok).astype(float),(~qok).astype(float),np.where(qok,(q-stats['mean'])/stats['scale'],0.)])


def normal_equations(X,y,w):
    Z=np.column_stack([X,np.ones(len(X))]);w=np.asarray(w,float);y=np.asarray(y,float)
    lhs=Z.T@(w[:,None]*Z);lhs[np.arange(X.shape[1]),np.arange(X.shape[1])]+=1.
    return lhs,Z.T@(w*y)


def family_group(value): return int.from_bytes(hashlib.sha256(str(value).encode()).digest(),'big')%2


def choose(rows):
    """Full eligible domain, highest exact-product score then original priority."""
    legal=rows.loc[rows.u_action_eligible.eq(1)&rows.score.map(finite)&rows.score.gt(0)]
    ordered=legal.sort_values(['mother_sequence_index','score','actual_epoch','action_id'],ascending=[True,False,True,True],kind='stable').drop_duplicates('mother_sequence_index')
    proposals={int(r.mother_sequence_index):r for r in ordered.itertuples(index=False)}
    keys=sorted((str(r.family_id),str(r.u_date),str(r.product_id).endswith('_F'),str(r.product_id),str(r.actual_epoch),str(r.action_id)) for r in ordered.itertuples(index=False))
    winners={}
    for family,u,isF,product,epoch,action in keys:winners.setdefault((family,u),action)
    return winners,proposals


def outcome(action,labels,end):
    if not action:return 0.,False
    row=labels[action]
    if row.get('participation_state')=='known_nonparticipation':return 0.,False
    if row.get('label_state')=='closed_complete_bar_model' and row.get('label_known_date','') and row['label_known_date']<=end and finite(row.get('net_R_stress')):return float(row['net_R_stress']),False
    return None,True


def increment(control,fx,labels,end):
    a,au=outcome(control,labels,end);b,bu=outcome(fx,labels,end)
    if control==fx:return 0.,False,bool(au or bu)
    if au or bu:return None,True,False
    return b-a,False,False


def held_result(fx,control,actions,end):
    labels=actions.set_index('action_id')[['label_state','participation_state','net_R_stress','label_known_date']].to_dict('index');groups={};days=[];family_rows=[]
    for scope,part in fx.groupby('scope',sort=True):
        base=control.loc[control.scope.eq(scope)&control.arm.eq('CONTROL_REUSED')]
        def compact(f):return f.sort_values('selected',ascending=False,kind='stable').drop_duplicates(['family_id','u_index']).set_index(['family_id','u_index']).sort_index()
        left,right=compact(base),compact(part)
        assert left.index.tolist()==right.index.tolist() and left.u_date.tolist()==right.u_date.tolist(),'complete held family-u'
        records=[];common=0
        for key,l,r in zip(left.index,left.itertuples(),right.itertuples()):
            v,u,c=increment(l.chosen_action_id,r.chosen_action_id,labels,end);common+=c
            av,au=outcome(l.chosen_action_id,labels,end);bv,bu=outcome(r.chosen_action_id,labels,end)
            row=dict(scope=scope,family_id=key[0],u_index=int(key[1]),u_date=r.u_date,control_chosen_action_id=l.chosen_action_id,fx_chosen_action_id=r.chosen_action_id,control_value_R=av,fx_value_R=bv,same_action=l.chosen_action_id==r.chosen_action_id,delta_R=v,known=v is not None,unknown=u,common_unresolved_same_action=c)
            records.append(row);family_rows.append(row)
        f=pd.DataFrame(records);d=f.groupby('u_date',sort=True).agg(delta_R=('delta_R','mean'),known_family_u=('known','sum'),unknown_family_u=('unknown','sum')).reset_index();d['scope']=scope;days.append(d)
        mean=float(d.delta_R.mean()) if d.delta_R.notna().any() else None;unknown=int(f.unknown.sum())
        groups[scope]=dict(nominal_pass=mean is not None and mean>=0,status='unsupported' if mean is not None and mean<0 else 'unknown' if mean is None or unknown else 'supported',known_u_equal_mean_increment_R=mean,unknown_differential_selected_events=unknown,common_unresolved_same_action=int(common),full_family_u=len(f),known_increment_family_u=int(f.known.sum()),known_source_days=int(d.delta_R.notna().sum()),selected_by_arm={'CONTROL_REUSED':int(base.selected.sum()),'FX':int(part.selected.sum())},annual=[dict(year=y,mean_delta_R=float(v.delta_R.mean()) if v.delta_R.notna().any() else None,source_days=len(v),unknown_family_u=int(v.unknown_family_u.sum())) for y,v in d.groupby(d.u_date.str[:4])],unknown_R_bounds=None)
    return groups,pd.concat(days,ignore_index=True),pd.DataFrame(family_rows)


def paired(fx,control,indices):
    if fx is None or control is None:return dict(status='survival_failure_no_log_repair',ci95_low=None,ci95_high=None),np.full(len(indices),np.nan)
    delta=np.asarray(fx,float)-np.asarray(control,float);indices=np.asarray(indices)
    assert delta.ndim==1 and indices.dtype.kind in 'iu' and indices.ndim==2 and indices.shape[1]==len(delta) and indices.min()>=0 and indices.max()<len(delta)
    values=delta[indices].mean(axis=1);low,high=np.quantile(values,[.025,.975])
    return dict(status='valid',mean_daily_log_difference=float(delta.mean()),cumulative_log_difference=float(delta.sum()),ci95_low=float(low),ci95_high=float(high)),values


def fixed_gate(points,held,stale,positive_wealth,execution_unknown):
    primary=points[('primary_2020','stress')];others=[p for k,p in points.items() if k!=('primary_2020','stress')]
    own=all(finite(p['active_total_return_pct']) and p['active_total_return_pct']>0 for p in points.values())
    returns=primary['return_percentage_point_difference']>0 and all(p['return_percentage_point_difference']>=0 for p in others)
    dd_known=all(finite(p['drawdown_percentage_point_difference']) for p in points.values())
    dd=all((p['drawdown_percentage_point_difference']>0 if p is primary else p['drawdown_percentage_point_difference']>=0) for p in points.values() if finite(p['drawdown_percentage_point_difference']))
    ci=finite(primary.get('ci95_low')) and primary['ci95_low']>0
    h=[held['groups'][s] for s in ('holdout_0','holdout_1')];hn=all(v['nominal_pass'] is True and (not 'known_u_equal_mean_increment_R' in v or finite(v['known_u_equal_mean_increment_R']) and v['known_u_equal_mean_increment_R']>=0) for v in h);hu=any(v['unknown_differential_selected_events']>0 or v['status']=='unknown' for v in h)
    cash_nominal=bool(own and returns and dd_known and dd and ci and positive_wealth)
    if all(p.get('identification')=='all_empty_unidentified' for p in points.values()):status='all_empty_unidentified'
    elif not(own and returns and dd and ci and hn and positive_wealth):status='unsupported'
    elif not dd_known:status='unknown_empty_reference_DD'
    elif stale:status='unknown_historical_stale'
    elif execution_unknown:status='unknown_execution_capacity_or_entry'
    elif hu:status='unknown_differential_held_outcome'
    else:status='supported_limited_reconstruction_model_only'
    return dict(status=status,cash_nominal_pass=cash_nominal,held_known_nominal_pass=bool(hn),FX_own_returns_positive_in_all_four=bool(own),primary_strict_return_and_DD_improvement=bool(returns and dd),actual_wealth_positive=bool(positive_wealth),nominal_pass=bool(cash_nominal and hn and not hu and not stale and not execution_unknown),financial_unknown=bool(stale or not dd_known or execution_unknown),held_signal_unknown=bool(hu),signal_label_uncertainty_is_not_cash_exposure=True,strict_first_release_PIT_established=False,goal_complete=False,production_qualified=False,increased_betting_qualified=False,independent_actual_review_required=True,no_automatic_promotion=True,execution_unknown=bool(execution_unknown),any_historical_stale=bool(stale))


def compare_frame(saved,expected,keys,label,numbers=(),booleans=()):
    saved,expected=saved.copy(),expected.copy()
    for key in keys:saved[key]=saved[key].astype(str);expected[key]=expected[key].astype(str)
    assert not saved.duplicated(keys).any() and not expected.duplicated(keys).any(),(label,'duplicate')
    a=saved.set_index(keys).sort_index();b=expected.set_index(keys).sort_index()
    assert a.index.tolist()==b.index.tolist(),(label,'complete domain')
    for key in b:
        assert key in a,(label,'missing',key)
        if key in numbers:
            compare(pd.to_numeric(a[key].replace('',np.nan)),pd.to_numeric(b[key]),label+'.'+key,atol=1e-10)
        elif key in booleans:
            assert a[key].map(flag).tolist()==b[key].map(bool).tolist(),(label,'bool',key)
        else: assert a[key].astype(str).tolist()==b[key].astype(str).tolist(),(label,'identity',key)


def review_projection(protocol,manifest,mothers,out):
    rows=archive_rows(bound(protocol['source']['archive']))
    assert len(rows)==7116 and rows[0]['date']=='1999-01-04' and rows[-1]['date']=='2026-10-16'
    expected=project(rows,mothers.u_date)
    actual=table(manifest['projection']); assert len(actual)==399252 and not actual.event_id.duplicated().any()
    for key in IDENTITY:
        if key in ('sequence_index','u_index'): compare(pd.to_numeric(actual[key]),mothers[key],'projection mother '+key,atol=0,rtol=0)
        else: assert actual[key].tolist()==mothers[key].tolist(),('projection full mother identity',key)
    per_date=actual.drop_duplicates('u_date').drop(columns=[k for k in IDENTITY if k!='u_date'])
    assert len(per_date)==len(expected)
    numbercols=['q','fx_missing']+[x+'_'+y for x in ('n','d','w') for y in ('source_row_index','age_days','USD_per_EUR','CNY_per_EUR')]
    compare_frame(per_date,expected,['u_date'],'ZIP independent projection',numbercols)
    for col in expected:
        if col=='u_date':continue
        mapped=expected.set_index('u_date')[col].reindex(actual.u_date)
        if col in numbercols: compare(pd.to_numeric(actual[col].replace('',np.nan)),pd.to_numeric(mapped),'all399252 projection '+col,atol=1e-12)
        else: assert actual[col].tolist()==mapped.tolist(),('all399252 projection',col)
    source_dates=table(manifest['source_dates'])
    compare_frame(source_dates,expected,['u_date'],'source dates',numbercols)
    summary=read_json(manifest['summary']);observed=expected.fx_missing.eq(0)
    fields(summary,dict(status='completed',mother_rows=399252,domestic_dates=len(expected),observed_mothers=int(actual.fx_missing.eq('0').sum()),missing_mothers=int(actual.fx_missing.eq('1').sum()),distinct_release_cohorts=expected.loc[observed,'n_date'].nunique(),repeated_domestic_asof_states=int(expected.loc[observed,'n_date'].duplicated().sum()),strict_pit_accepted=False,production_qualified=False,goal_complete=False),'projection summary')
    report=dict(rawZIP_rows=len(rows),full_mother_projection_rows=len(actual),source_dates=len(expected),all_n_d_w_same_batch_ratios_and_q_checked=True,all_08_assignment_u15_clocks_and_ages_checked=True,missing_or_future_rows_not_skipped=True,distinct_release_cohorts=int(expected.loc[observed,'n_date'].nunique()),repeated_domestic_asof_states=int(expected.loc[observed,'n_date'].duplicated().sum()),strict_first_release_PIT_established=False)
    progress(out,'projection_from_rawZIP',report)
    return expected.set_index('u_date').q,report


def review_control_choices(protocol,manifests):
    controls=[];full=[]
    for role,old_role in [('choices_main','accepted_choices_main'),('choices_holdout','accepted_choices_holdout')]:
        old=numeric(table(protocol['input_roles'][old_role]));old=old.loc[old.arm.eq('B')].copy();old['arm']='CONTROL_REUSED'
        new=numeric(table(artifact(manifests['fit'],role)));control=new.loc[new.arm.eq('CONTROL_REUSED')]
        assert set(new.arm)=={'CONTROL_REUSED','FX'} and len(new)==322028
        numeric_cols=[c for c in NUMERIC if c in old]
        compare_frame(control,old,['scope','event_id'],'accepted CONTROL zero-column reference '+role,numeric_cols)
        controls.append(control);full.append(new)
    return pd.concat(controls,ignore_index=True),pd.concat(full,ignore_index=True)


def review_choices(saved,parents,pred,scores,scope,cutoff):
    assert saved.event_id.tolist()==parents.event_id.tolist() and len(saved)==len(parents)
    assert saved.scope.eq(scope).all() and saved.cutoff.eq(cutoff).all() and saved.policy.eq('NARROW').all() and saved.arm.eq('FX').all()
    for key in IDENTITY:assert saved[key].tolist()==parents[key].tolist(),('full FX parent identity',scope,cutoff,key)
    assert saved.anchor_epoch.tolist()==parents.reference_epoch.tolist()
    source=pred.copy();source['score']=scores;winners,proposals=choose(source);lookup=source.set_index('action_id');observed=set(pred.mother_sequence_index)
    for row in saved.itertuples(index=False):
        action=winners.get((row.family_id,row.u_date),'')
        if action and int(lookup.loc[action,'mother_sequence_index'])!=int(row.sequence_index):action=''
        assert row.chosen_action_id==action and int(row.selected)==bool(action),('new FX winner',row.event_id)
        if action:
            child=lookup.loc[action];assert row.chosen_epoch==child.actual_epoch and int(row.chosen_action_sequence_index)==int(child.action_sequence_index)
            compare(row.score,child.score,'new chosen score',atol=1e-10)
        else:assert row.chosen_epoch=='' and int(row.chosen_action_sequence_index)==-1 and not finite(row.score)
        proposal=proposals.get(int(row.sequence_index))
        if proposal is not None:
            assert row.proposed_action_id==proposal.action_id and row.proposed_epoch==proposal.actual_epoch
            compare(row.proposed_score,proposal.score,'new proposed score',atol=1e-10)
            state='selected' if action else 'family_priority_suppressed'
        else:
            assert row.proposed_action_id==row.proposed_epoch=='' and not finite(row.proposed_score)
            state='no_observed_children' if int(row.sequence_index) not in observed else 'no_eligible_positive_action'
        assert row.selection_state==state,('FX selection state',row.event_id,row.selection_state,state)


def review_models(protocol,manifest,actions,mothers,common,q,out):
    old_records=read_json(protocol['input_roles']['accepted_fit_records']);records=read_json(manifest['fit_records'])
    expected_keys={(s,c) for s in SCOPES for c in CUTOFFS}
    old={(r['scope'],r['cutoff']):r for r in old_records};new={(r['scope'],r['cutoff']):r for r in records}
    assert len(old_records)==len(records)==6 and set(old)==set(new)==expected_keys
    control,choices=review_control_choices(protocol,{'fit':manifest})
    fx=choices.loc[choices.arm.eq('FX')].copy();scores=numeric(table(manifest['child_scores']))
    assert set(scores.arm)=={'FX'}
    forward=actions.loc[actions.u_date.ge(CUTOFFS[0])]
    for frame in (scores.loc[scores.scope.eq('main')],scores.loc[scores.scope.ne('main')]):assert frame.action_id.is_unique and set(frame.action_id)==set(forward.action_id),'all forward actions retained'
    for frame in (fx.loc[fx.scope.eq('main')],fx.loc[fx.scope.ne('main')]):assert frame.event_id.is_unique and set(frame.event_id)==set(mothers.loc[mothers.u_date.ge(CUTOFFS[0]),'event_id']),'all forward mothers retained'
    assert np.isfinite(q[forward.sequence_index.to_numpy(int)]).all(),'zero bridge complete forward'
    prepared=[]
    # Validate all six zero-column/q conditions before checking any new model.
    for scope in SCOPES:
        for cutoff,stop in zip(CUTOFFS,('2023-01-01',None)):
            key=(scope,cutoff);prior,record=old[key],new[key]
            for role,oldrole in [('training_identity_weights','training_identity_weights'),('weight_groups','weight_groups'),('accepted_common_scaler','scaler'),('accepted_portable_model','portable_model')]:same_binding(record[role],prior[oldrole])
            nested(record['accepted_fit_record'],prior,'exact accepted fold record')
            trainmask=actions.u_action_eligible.eq(1)&actions.label_state.eq('closed_complete_bar_model')&actions.u_date.lt(cutoff)&actions.label_known_date.ne('')&actions.label_known_date.lt(cutoff)&np.isfinite(actions.net_R_stress)
            predmask=actions.u_date.ge(cutoff)&(actions.u_date.lt(stop) if stop else True);parentmask=mothers.u_date.ge(cutoff)&(mothers.u_date.lt(stop) if stop else True)
            if scope!='main':
                g=int(scope[-1]);trainmask &= actions.family_id.map(family_group).ne(g);predmask &= actions.family_id.map(family_group).eq(g);parentmask &= mothers.family_id.map(family_group).eq(g)
            train,pred,parent=actions.loc[trainmask],actions.loc[predmask],mothers.loc[parentmask];ti=train.sequence_index.to_numpy(int);pi=pred.sequence_index.to_numpy(int)
            verify(prior['model']);verify(prior['portable_model']);verify(prior['weight_groups'])
            accepted=numeric(table(prior['training_identity_weights'],['sequence_index','action_id','net_R_stress','label_known_date','u_date','family_id','u_action_eligible','label_state','sample_weight']))
            for col in ('sequence_index','action_id','label_known_date','u_date','family_id','u_action_eligible','label_state'):assert accepted[col].tolist()==train[col].tolist(),('accepted mature identity',key,col)
            compare(accepted.net_R_stress,train.net_R_stress,'accepted target source',atol=1e-11)
            weights=accepted.sample_weight.to_numpy(float);assert len(weights)==len(train) and np.isfinite(weights).all() and (weights>0).all()
            assert np.isfinite(q[ti]).all(),'zero bridge all mature train'
            stats=q_stats(q[ti],weights);scaler=read_json(record['scaler']);prior_scaler=read_json(prior['scaler'])
            nested(scaler['common'],prior_scaler['common'],'accepted common scaler exact');same_binding(scaler['accepted_common_scaler'],prior['scaler'])
            fields(scaler,dict(scope=scope,cutoff=cutoff),'new scaler identity');nested(scaler['scalar'],stats,'own train-only q stats')
            assert scaler['feature_names']==prior_scaler['feature_names']+['fx_missing','fx_q_std']
            fields(record,dict(training_rows=len(train),prediction_children=len(pred),prediction_mothers=len(parent),dimension=54,new_training_identity_copy=False),'new fold record')
            prepared.append((scope,cutoff,record,prior,train,pred,parent,ti,pi,weights,scaler,stats))
    bridge=read_json(manifest['bridge_preflight'])
    fields(bridge,dict(status='passed',control_bridge_verified=True,all_six_preflight_before_first_fit=True,common26_binding_reused=True,accepted_training_identity_target_weights_reused=True,control_added_columns_identically_zero=True,complete_forward_actions=len(forward),complete_forward_fx_missing=0,control_new_fits=0,control_new_cash_replays=0),'global control bridge')
    assert len(bridge['folds'])==6
    reports=[]
    from threadpoolctl import threadpool_limits
    import joblib
    for scope,cutoff,record,prior,train,pred,parent,ti,pi,w,scaler,stats in prepared:
        br=[f for f in bridge['folds'] if (f['scope'],f['cutoff'])==(scope,cutoff)];assert len(br)==1
        fields(br[0],dict(training_rows=len(train),training_fx_missing=0,prediction_children=len(pred),prediction_mothers=len(parent)),'bridge fold');nested(br[0]['q_scaler'],stats,'bridge q')
        for a,b in [('training_identity_weights','training_identity_weights'),('common_scaler','scaler'),('portable_model','portable_model')]:same_binding(br[0][a],prior[b])
        model=read_json(record['portable_model']);fields(model,dict(schema='stage147_portable_fx_ridge_v1',scope=scope,cutoff=cutoff,parameters=dict(alpha=1.,fit_intercept=True,solver='cholesky'),feature_names=scaler['feature_names']),'portable model')
        coef=np.asarray(model['coef'],float);beta=np.r_[coef,model['intercept']];assert coef.shape==(54,) and np.isfinite(beta).all()
        X=design54(common[ti],q[ti],scaler,stats)
        assert not X[:,52].any(),'zero bridge new missing column'
        with threadpool_limits(limits=1):lhs,rhs=normal_equations(X,train.net_R_stress.to_numpy(float),w)
        compare(lhs@beta,rhs,'new six Ridge optimality',atol=1e-7,rtol=1e-8)
        with np.load(verify(record['normal_equations']),allow_pickle=False) as ne:
            compare(ne['lhs'],lhs,'new six normal lhs',atol=2e-6);compare(ne['rhs'],rhs,'new six normal rhs',atol=2e-6)
            compare(ne['coefficient_with_intercept'],beta,'new serialized normal beta',atol=1e-12);compare(ne['weight_sum'],w.sum(),'new weight_sum',atol=1e-9)
        compare(record['normal_equation_max_abs_residual'],np.max(np.abs(lhs@beta-rhs)),'normal residual metadata',atol=2e-6)
        estimator=joblib.load(verify(record['model']));compare(estimator.coef_,coef,'new joblib coefficients',atol=1e-12);compare(estimator.intercept_,model['intercept'],'new joblib intercept',atol=1e-12)
        assert estimator.alpha==1. and estimator.fit_intercept is True and estimator.solver=='cholesky'
        del X,lhs,rhs
        with threadpool_limits(limits=1):predicted=design54(common[pi],q[pi],scaler,stats)@coef+model['intercept']
        saved=scores.loc[scores.scope.eq(scope)&scores.cutoff.eq(cutoff)]
        assert saved.action_id.tolist()==pred.action_id.tolist(),'new all-child score order'
        for col in ('sequence_index','mother_sequence_index','mother_event_id','product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible'):assert saved[col].tolist()==pred[col].tolist(),('new score identity',col)
        compare(saved.score,predicted,'all new FX child scores',atol=1e-10)
        selected=fx.loc[fx.scope.eq(scope)&fx.cutoff.eq(cutoff)];review_choices(selected,parent,pred,predicted,scope,cutoff)
        reports.append(dict(scope=scope,cutoff=cutoff,training_rows=len(train),forward_children=len(pred),forward_mothers=len(parent),q_stats=stats,common_scaler_refit=False,weights_reconstructed=False,model_refit=False))
        progress(out,'model_'+scope+'_'+cutoff,reports[-1])
    root=Path(manifest['terminal']['path']).parent
    for name,count in [('fit_attempts.jsonl','attempt'),('fit_completed.jsonl','completed')]:
        events=[json.loads(l) for l in (root/name).read_text().splitlines() if l]
        assert [(e['scope'],e['cutoff']) for e in events]==[(s,c) for s in SCOPES for c in CUTOFFS] and [e[count] for e in events]==list(range(1,7))
    groups,held_daily,family=held_result(fx,control,actions,'2026-10-16')
    held=read_json(manifest['held_diagnostic']);nested(held['groups'],groups,'all held summary groups')
    fields(held,dict(schema='stage147_fx_held_v1',contrast='FX_minus_CONTROL_REUSED',full_policy_cash_qualified=False),'held boundary')
    compare_frame(table(manifest['held_daily']),held_daily,['scope','u_date'],'held complete daily',['delta_R','known_family_u','unknown_family_u'])
    compare_frame(table(manifest['held_family_u']),family,['scope','family_id','u_index'],'held complete family-u',['delta_R','control_value_R','fx_value_R'],['same_action','known','unknown','common_unresolved_same_action'])
    return fx.loc[fx.scope.eq('main')],held,dict(new_models_checked=6,new_child_scores_checked=len(scores),new_parent_choices_checked=len(fx),control_parent_rows_reference_checked=len(control),full_held_family_u_checked=len(family),folds=reports,old_models_reaudited=False,old_union_weights_reconstructed=False,old_refits=0)


def accepted_helpers():
    for name,sha in HELPERS.items():assert binding(TOOLS/name)['sha256']==sha,('accepted independent helper changed',name)
    if str(TOOLS) not in sys.path:sys.path.insert(0,str(TOOLS))
    spec=importlib.util.spec_from_file_location('review149_accepted132_math',TOOLS/'stage132_contract_choice_review.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    cash,diag=module.independent_helpers()
    return module,cash,diag


@contextmanager
def cash_context(review,cash,positions):
    old=(review.CASH_HELPER,review.ACTIVE_POSITIONS,cash.review_budgets)
    review.CASH_HELPER,review.ACTIVE_POSITIONS,cash.review_budgets=cash,positions,review.review_capped_budgets
    try:yield
    finally:review.CASH_HELPER,review.ACTIVE_POSITIONS,cash.review_budgets=old


def cached_store(protocol,execution,r):
    # Only saved accepted arrays; no SQL, DB stat/hash, indicators or labels rerun.
    bridge,calendar=r.calendar_from_protocol(execution);meta=read_json(protocol['input_roles']['native_cache_manifest'])
    same_binding(meta['file'],protocol['input_roles']['native_cache'])
    assert meta['schema']=='stage132_native_store_recovery_cache_v1' and meta['native_rows']==1552456 and meta['native_epochs']==9520
    store=r.NativeBars(calendar)
    with np.load(verify(meta['file']),allow_pickle=False) as z:
        epochs=z['epochs'].tolist();offsets=z['offsets'];arrays={k:z[k] for k in ('days','values','accepted','valid','N','low20','run')}
        assert len(epochs)==9520 and offsets[0]==0 and offsets[-1]==1552456
        for i,e in enumerate(epochs):store.series[e]={k:v[int(offsets[i]):int(offsets[i+1])] for k,v in arrays.items()}
    economics=read_json(bridge['economic_projection'])['instruments'];assert set(economics)==set(store.series)
    return store,economics


def review_signals(manifest,choices,actions,store,economics,r):
    saved=numeric(table(manifest['signals']),NUMERIC+['D_index','label_history_ready20','potential','u_gross_capacity_qty'])
    selected=choices.loc[choices.selected.eq(1)]
    assert saved.event_id.is_unique and saved.event_id.tolist()==selected.chosen_action_id.tolist(),'every new selected FX signal'
    assert not saved.duplicated(['family_id','u_date']).any()
    lookup=actions.set_index('action_id');got=saved.set_index('event_id',drop=False)
    for c in selected.itertuples(index=False):
        action=lookup.loc[c.chosen_action_id];epoch=action.actual_epoch;k=store.index[action.u_date];j=store.locate(epoch,k)
        assert j is not None and store.series[epoch]['valid'][j] and action.u_action_eligible==1
        native=store.series[epoch];gross,entry=r.capacity(native['values'][j,4],economics[epoch]['round_lot'])
        assert native['run'][j]>=20 and entry>=economics[epoch]['round_lot'] and c.score>0
        expected=dict(mother_event_id=c.event_id,action_sequence_index=int(action.action_sequence_index),product_id=action.product_id,family_id=action.family_id,u_date=action.u_date,u_index=k,D_index=k+1,reference_epoch=epoch,anchor_epoch=action.anchor_epoch,label_history_ready20=1,N_u=float(native['N'][j]),low20_u=float(native['low20'][j]),u_close=float(native['values'][j,3]),history_run=int(native['run'][j]),lifecycle_index=r.lifecycle(epoch,economics[epoch],store.calendar),entry_capacity_qty=int(entry),u_gross_capacity_qty=int(gross),potential=1,score=float(c.score),arm='FX',control_id='FX',policy='NARROW',cutoff=c.cutoff)
        fields(got.loc[c.chosen_action_id].to_dict(),expected,'independent new FX signal')
    got['planned_execution_date']=[store.calendar[int(k)+1] if int(k)+1<len(store.calendar) else '' for k in got.u_index]
    return got


def extra_book_checks(folder,account,summary,group_table,tails,cash):
    roots=[]
    closed=cash.csv(folder/'closed.csv.gz');opened=cash.csv(folder/'open.csv.gz');fills=cash.csv(folder/'fills.csv.gz')
    cash.numeric(closed,['net_pnl']);cash.numeric(opened,['realized_gross','entry_fees','exit_fees','unrealized']);cash.numeric(fills,['fee','slippage'])
    for frame,isclosed in ((closed,True),(opened,False)):
        for row in frame.to_dict('records'):
            value=float(row['net_pnl']) if isclosed else math.fsum([float(row['realized_gross']),-float(row['entry_fees']),-float(row['exit_fees']),float(row['unrealized'])])
            roots.append(dict(root_id=row['root_id'],sector='financial' if row['product_id'].startswith('CFFEX.') else 'commodity',variant='F' if row['product_id'].endswith('_F') else 'ordinary',closed=isclosed,value=value))
    expected=[]
    for dimension,key,names in [('market_sector','sector',('financial','commodity')),('product_variant','variant',('ordinary','F'))]:
        for name in names:
            part=[r for r in roots if r[key]==name];cl=[r for r in part if r['closed']];op=[r for r in part if not r['closed']];ids={r['root_id'] for r in part};f=fills.loc[fills.root_id.isin(ids)]
            record=dict(dimension=dimension,group=name,episodes=len(part),closed_episodes=len(cl),open_episodes=len(op),closed_net_pnl=math.fsum(r['value'] for r in cl),open_marked_net_pnl=math.fsum(r['value'] for r in op),net_equity_contribution=math.fsum(r['value'] for r in part),fees=float(f.fee.sum()),slippage_attribution=float(f.slippage.sum()),slippage_already_in_fill_price=True)
            row=group_table.loc[group_table.account.eq(account)&group_table.dimension.eq(dimension)&group_table.group.eq(name)];assert len(row)==1;fields(row.iloc[0].to_dict(),record,'sector variant including zero');expected.append(record)
        compare(math.fsum(r['net_equity_contribution'] for r in expected if r['dimension']==dimension),summary['ending_equity']-1000000.,'sector variant cash bridge',atol=1e-5)
    columns=[c for c in ('root_id','event_id','product_id','family_id','epoch','entry_date','exit_date','net_pnl') if c in closed]
    for key,part in [('largest_wins',closed.loc[closed.net_pnl.gt(0)].nlargest(5,'net_pnl')),('largest_losses',closed.loc[closed.net_pnl.lt(0)].nsmallest(5,'net_pnl'))]:
        expected_tail=part[columns].to_dict('records');nested(tails[key],expected_tail,'all new '+key)
    return dict(sector_variant_rows=len(expected),largest_wins=len(tails['largest_wins']),largest_losses=len(tails['largest_losses']))


def review_books(protocol,manifest,signals,mothers,store,economics,execution,out,r,cash,diag):
    expected_keys={(w,c) for w in WINDOWS for c in COSTS};books={(a['window'],a['cost']):a for a in manifest['accounts']}
    assert len(books)==len(manifest['accounts'])==4 and set(books)==expected_keys
    reports=read_json(manifest['diagnostics']);family_year=diag._read(verify(manifest['family_year_including_zero']).parent,'family_year_including_zero')
    annual=table(manifest['annual_slices']);summary_table=table(manifest['account_summaries']);capacity=table(manifest['capacity_summary']);groups=table(manifest['sector_variant_attribution']);tails=read_json(manifest['largest_wins_losses'])
    families=sorted(mothers.family_id.unique());summaries={};daily={};logs={};reviewed=[];family_totals=[]
    for key in [(w,c) for w in WINDOWS for c in COSTS]:
        window,cost=key;a=books[key];name=f'NARROW_FX_{window}_{cost}';folder=Path(a['directory'])
        assert a['account_id']==name and a['arm']=='FX' and folder==Path(manifest['terminal']['path']).parent/name
        assert set(a['ledgers'])==set(LEDGERS)
        for role,b in a['ledgers'].items():assert Path(b['path'])==folder/(role+'.csv.gz');verify(b)
        summary=read_json(a['summary']);assert Path(a['summary']['path'])==folder/'summary.json'
        bounds=execution['cash']['windows'][window];schedule=dict(id=window,start=bounds[0],end=bounds[1])
        with cash_context(r,cash,cash.csv(folder/'positions.csv.gz')):
            checked=cash.review_account(folder,cost,schedule,execution,signals,economics,store.calendar,.25)
            native=r.account_native_and_capacity(folder,signals,mothers,store,economics,summary,cost)
        saved_fy=family_year.loc[family_year.arm.eq('FX')&family_year.window.eq(window)&family_year.cost.eq(cost)]
        d,log,numbers,fy=diag._account(folder,summary,reports[name],saved_fy,families);diag._daily_summary(d,summary,1000000.)
        saved_annual=annual.loc[annual.account.eq(name)].sort_values('year');assert len(saved_annual)==len(reports[name]['annual_slices'])
        for actual,expected in zip(saved_annual.to_dict('records'),reports[name]['annual_slices']):fields(actual,expected,'all new annual slices')
        row=summary_table.loc[summary_table.account.eq(name)];assert len(row)==1
        fields(row.iloc[0].to_dict(),{k:v for k,v in summary.items() if not isinstance(v,(dict,list))},'all new summary table')
        cap=capacity.loc[capacity.account.eq(name)];assert len(cap)==1
        fields(cap.iloc[0].to_dict(),{k:summary[k] for k in ('execution_unknown','unknown_capacity_fills','capacity_unknown_roots','entry_execution_unknown')},'new capacity summary')
        fills=cash.csv(folder/'fills.csv.gz');roots=pd.concat([cash.csv(folder/'closed.csv.gz'),cash.csv(folder/'open.csv.gz')],ignore_index=True).set_index('root_id');gap=[]
        for f in fills.loc[fills.side.eq('SELL')&fills.reason.eq('gap_stop')].to_dict('records'):
            root=roots.loc[f['root_id']];loss=(float(root.entry_reference)-float(f['reference_price']))/(.25*signals.loc[f['event_id'],'N_u'])
            gap.append(dict(event_id=f['event_id'],date=f['date'],gross_loss_R=loss,qty=int(float(f['qty'])),realized_gross=float(f['realized_gross']),exit_fee=float(f['fee'])))
        nested(reports[name]['gap_stop_fills'],gap,'all new gap stop fills');assert reports[name]['gap_stop_exceeds_1R']==sum(g['gross_loss_R']>1 for g in gap)
        assert summary['any_historical_stale']==bool(numbers['stale_days']>0)
        extras=extra_book_checks(folder,name,summary,groups,tails[name],cash)
        report=dict(account_id=name,ledger=checked,native=native,diagnostics=numbers,extra_reports=extras)
        progress(out,'book_'+name,report);reviewed.append(report)
        summaries[key]=summary;daily[key]=d;logs[key]=log;family_totals.append(fy.assign(arm='FX',window=window,cost=cost))
    assert set(reports)==set(tails)=={a['account_id'] for a in reviewed} and len(summary_table)==len(capacity)==4 and len(groups)==16
    keys=['arm','window','cost','family_id'];measures=['net_equity_contribution','fee','slippage','fill_count','filled_qty']
    expected=pd.concat(family_totals).groupby(keys)[measures].sum().sort_index();actual=table(manifest['family_total_including_zero']).set_index(keys).sort_index();assert actual.index.tolist()==expected.index.tolist()
    for c in measures:compare(actual[c],expected[c],'all new family totals '+c)
    return summaries,daily,logs,reviewed


def review_comparisons(protocol,manifest,summaries,daily,logs,books,held,diag):
    old=read_json(protocol['input_roles']['accepted_cash_manifest']);old_reports=read_json(artifact(old,'diagnostics.json'))
    assert set(manifest['baseline_books'])=={w+'_'+c for w in WINDOWS for c in COSTS}
    comparisons=table(manifest['comparisons']);distributions=table(manifest['bootstrap_distributions'])
    assert len(comparisons)==4 and not comparisons.duplicated(['window','cost']).any() and comparisons.contrast.eq('FX_minus_CONTROL_REUSED').all() and len(distributions)==2000
    assert set(distributions)=={w+'_'+c+'_FX_minus_CONTROL_REUSED' for w in WINDOWS for c in COSTS}
    points={};control_summaries={};control_logs={};stale=False
    for window in WINDOWS:
        indices=np.load(verify(protocol['bootstrap_indices'][window]),allow_pickle=False)
        for cost in COSTS:
            key=(window,cost);name=f'NARROW_B_{window}_{cost}';reference=manifest['baseline_books'][window+'_'+cost]
            fields(reference,dict(window=window,cost=cost,arm='CONTROL_REUSED',source_account_id=name,source_arm='B',diagnostic_key=name,source_only=True,replayed=False),'old CONTROL identity only')
            for role,logical in [('summary',name+'/summary.json'),('daily',name+'/daily.csv.gz'),('diagnostics','diagnostics.json')]:same_binding(reference[role],artifact(old,logical))
            control=read_json(reference['summary']);cd=pd.read_csv(verify(reference['daily']),dtype={'date':str},float_precision='round_trip')
            assert cd.date.tolist()==daily[key].date.tolist(),'identical paired new/old source dates'
            assert indices.shape==(2000,len(cd)) and indices.dtype.kind in 'iu' and indices.min()>=0 and indices.max()<len(cd)
            cl=diag._log(cd,1000000.);point,dist=paired(logs[key],cl,indices);active=summaries[key]
            point.update(active_total_return_pct=active['total_return_pct'],reference_total_return_pct=control['total_return_pct'],return_percentage_point_difference=active['total_return_pct']-control['total_return_pct'],drawdown_percentage_point_difference=None if control['fills']==0 else active['max_drawdown_pct']-control['max_drawdown_pct'],dd_comparison_state='NA_empty_reference' if control['fills']==0 else 'active_reference',identification='all_empty_unidentified' if active['fills']==control['fills']==0 else 'observed_cash_comparison')
            row=comparisons.loc[comparisons.window.eq(window)&comparisons.cost.eq(cost)];assert len(row)==1
            fields(row.iloc[0].to_dict(),point,'all four paired points')
            fields(row.iloc[0].to_dict(),dict(bootstrap_repetitions=2000,block_length=252,indices_regenerated=False,epsilon_log_repair=False),'paired CI assumptions')
            compare(pd.to_numeric(distributions[window+'_'+cost+'_FX_minus_CONTROL_REUSED'].replace('',np.nan)),dist,'all four original070 bootstrap distributions',atol=1e-12)
            points[key]=point;control_summaries[key]=control;control_logs[key]=cl
            stale |= old_reports[name]['stale_days']>0
    stale |= any(b['diagnostics']['stale_days']>0 for b in books)
    unknown=any(v['execution_unknown'] for v in list(summaries.values())+list(control_summaries.values()))
    positive=all(log is not None for log in list(logs.values())+list(control_logs.values()))
    gate=fixed_gate(points,held,bool(stale),positive,bool(unknown));nested(read_json(manifest['continuation_gate']),gate,'all145 nominal/unknown gates')
    identification=read_json(manifest['signal_identification'])
    fields(identification,dict(full_mother_rows=399252,full_main_parent_rows_per_arm=161014,old_B_selection_used_as_admission_gate=False,future_label_state_used_as_admission_gate=False,local_B_schema_alias_only=True,old_global_ARMS_changed=False),'full population identity')
    nested(identification['held_groups'],held['groups'],'full held group disclosure')
    disclosure=read_json(manifest['budget_and_tick_disclosure'])
    fields(disclosure,dict(policy='NARROW',bootstrap_indices_regenerated=False,fees_already_in_cash=True,slippage_in_fill_price_already=True,slippage_deducted_again=False,no_gap_loss_cap=True,no_actual_orderbook_execution_proof=True,strict_first_release_PIT_established=False,source_archive_is_final_reconstruction=True,goal_complete=False,production_qualified=False,increased_betting_qualified=False),'cash science disclosure')
    nested(disclosure['budget'],protocol['execution']['budget'],'unchanged budget');nested(disclosure['capacity'],protocol['execution']['capacity'],'unchanged capacity');nested(disclosure['anchor'],protocol['execution']['anchor_and_execution'],'unchanged anchor');nested(disclosure['bootstrap_indices'],protocol['bootstrap_indices'],'exact original070 indices disclosure')
    receipt=read_json(manifest['source_read_receipt']);fields(receipt,dict(native_source_queries=0,actual_model_fit_calls=0,new_labels=0,old_baseline_replays=0,full_forward_parent_rows_per_arm=161014,full_mother_rows=399252),'cache-only source receipt')
    return dict(comparisons_checked=4,bootstrap_repetitions=2000,block_length=252,indices_regenerated=False,paired_daily_log_conditional_not_unseen_OOS=True,gate=gate,points=[dict(window=w,cost=c,**p) for (w,c),p in points.items()],old_control_book_reaudits=0,old_control_replays=0,execution_unknown_in_either_arm_retained=bool(unknown))


def authorize(args):
    output=Path(args.output).resolve()
    assert not output.exists() and LINE/'outputs/stage149_fx_review' in output.parents,'fresh149 output required'
    pb=binding(args.protocol);assert args.protocol_sha256==pb['sha256']==PROTOCOL_SHA,'exact final145 protocol'
    protocol=read_json(pb);assert protocol['schema']=='stage145_fx_information_protocol_v1' and protocol['line_id']==LINE.name
    ab=binding(args.authorization);assert ab['sha256']==args.authorization_sha256,'exact authorization hash'
    auth=read_json(ab)
    fields(auth,dict(schema='stage145_exact_root_authorization_v1',authorized_by='root',stage='review',exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(output)),'root exact149 authorization')
    assert auth['source_bundle']==bundle(),'authorized149 source/helpers bundle'
    assert set(auth['input_bindings'])=={'projection_manifest','fit_manifest','cash_manifest'},'exact three new phase manifests'
    return output,protocol,pb,auth,ab


def input_closure(protocol,auth):
    manifests={};bindings={};expected={'projection':(146,'stage146_fx_projection_v1'),'fit':(147,'stage147_fx_fit_v1'),'cash':(148,'stage148_fx_cash_v1')}
    for role,(stage,schema) in expected.items():
        b=auth['input_bindings'][role+'_manifest'];m=read_json(b)
        fields(m,dict(schema=schema,status='completed',mode='actual',protocol_sha256=PROTOCOL_SHA),'completed'+role)
        same_binding(m['protocol'],binding(LINE/'outputs/stage145_fx_information_protocol/protocol.json'))
        term=read_json(m['terminal']);fields(term,dict(status='completed',exit_code=0,native_source_queries=0),'new terminal '+role)
        for source in m['source_bundle']:verify(source)
        if role=='projection':fields(term,dict(actual_fit_calls_completed=0,cash_replays=0,downloads=0),'projection budget')
        elif role=='fit':fields(term,dict(actual_fit_calls_attempted=6,actual_fit_calls_completed=6,control_fit_calls=0,cash_replays=0,new_cash_accounts=0,downloads=0),'fit budget')
        else:fields(term,dict(cash_accounts_started=4,new_cash_accounts=4,actual_model_fit_calls=0,new_labels=0,downloads=0,whole_database_hashes=0,old_baseline_replays=0,old_control_cash_replays=0),'cash budget')
        manifests[role]=m;bindings[role]=dict(manifest=b,terminal=m['terminal'],source_bundle=m['source_bundle'])
    p,f,c=manifests['projection'],manifests['fit'],manifests['cash']
    for role,b in p['input_bindings'].items():same_binding(b,protocol['source'][role] if role in ('values','content_receipt') else protocol['input_roles'][role])
    same_binding(f['input_bindings']['projection_manifest'],auth['input_bindings']['projection_manifest']);same_binding(f['input_bindings']['projection'],p['projection'])
    for role,b in f['input_bindings'].items():
        if role not in ('projection_manifest','projection'):same_binding(b,protocol['input_roles'][role])
    same_binding(c['input_bindings']['fit_manifest'],auth['input_bindings']['fit_manifest'])
    for role in ('choices_main','held_diagnostic','bridge_preflight'):same_binding(c['input_bindings'][role],f[role])
    for role,b in c['input_bindings'].items():
        if role in protocol['input_roles']:same_binding(b,protocol['input_roles'][role])
    accepted_fit=read_json(protocol['input_roles']['accepted_fit_manifest']);accepted_cash=read_json(protocol['input_roles']['accepted_cash_manifest']);accepted_review=read_json(protocol['input_roles']['accepted_review_receipt'])
    fields(accepted_review,dict(completed=True,research_arithmetic_accepted=True,C=0,I=0),'accepted132 receipt reference')
    for role,oldrole in [('accepted_fit_records','fit_records'),('accepted_child_scores','child_scores'),('accepted_choices_main','choices_main'),('accepted_choices_holdout','choices_holdout')]:same_binding(protocol['input_roles'][role],accepted_fit[oldrole])
    for role in ('actions','mothers','common','dataset_manifest','dataset_terminal'):same_binding(accepted_fit['input_bindings'][role],protocol['input_roles'][role])
    same_binding(accepted_cash['protocol'],protocol['input_roles']['execution_protocol'])
    execution=read_json(protocol['input_roles']['execution_protocol'])
    same_binding(c['input_bindings']['market_protocol'],execution['inputs']['market_protocol'])
    for role in ('actions','mothers','dataset_manifest'):same_binding(accepted_cash['input_bindings'][role],protocol['input_roles'][role])
    same_binding(f['reused_child_scores'],protocol['input_roles']['accepted_child_scores'])
    verify(protocol['input_roles']['accepted_child_scores'])
    return manifests,bindings


def review(args):
    out,protocol,pb,auth,ab=authorize(args);out.mkdir(parents=True,exist_ok=False);started=time.monotonic();sources=bundle();status='failed';error=None
    write(out/'actual_started.json',dict(status='started',schema='stage149_incremental_review_start_v1',protocol=pb,authorization=ab,source_bundle=sources,input_bindings=auth['input_bindings'],new_SQL=0,new_fits=0,new_cash=0,fixture=False))
    snapshot=out/'checker_snapshot';snapshot.mkdir()
    for source in sources:(snapshot/Path(source['path']).name).write_bytes(bound(source))
    try:
        manifests,closure=input_closure(protocol,auth);progress(out,'input_closure',closure)
        roles=protocol['input_roles'];mothers=numeric(table(roles['mothers'],IDENTITY));assert len(mothers)==399252 and mothers.event_id.is_unique and np.array_equal(mothers.sequence_index,np.arange(399252))
        assert mothers.product_id.nunique()==98 and mothers.family_id.nunique()==95 and set(mothers.product_id.str.split('.').str[0])==set(protocol['population']['exchanges'])
        by_date,projection_report=review_projection(protocol,manifests['projection'],mothers,out)
        columns=['sequence_index','action_sequence_index','action_id','event_id','actual_epoch','reference_epoch','mother_sequence_index','mother_event_id','anchor_epoch','product_id','family_id','u_date','u_index','u_action_eligible','entry_capacity_qty','N_u','low20_u','u_close','history_run','lifecycle_index','label_state','label_known_date','participation_state','net_R_stress']
        actions=numeric(table(roles['actions'],columns));assert len(actions)==1552456 and actions.action_id.is_unique and np.array_equal(actions.sequence_index,np.arange(len(actions)))
        mi=actions.mother_sequence_index.to_numpy(int);assert np.array_equal(actions.mother_event_id,mothers.event_id.to_numpy()[mi]) and actions.event_id.eq(actions.action_id).all() and actions.actual_epoch.eq(actions.reference_epoch).all()
        for col in ('product_id','family_id','u_date','u_index'):assert np.array_equal(actions[col],mothers[col].to_numpy()[mi]),('accepted source projection identity',col)
        with np.load(verify(roles['common']),allow_pickle=False) as z:common=z['common'].copy();common_columns=z['columns'].tolist()
        execution=read_json(roles['execution_protocol']);assert common.shape==(1552456,26) and common_columns==execution['features']['common_columns']
        q=by_date.reindex(actions.u_date).to_numpy(float)
        choices,held,model_report=review_models(protocol,manifests['fit'],actions,mothers,common,q,out);progress(out,'models_and_full_held',model_report)
        del common,q
        r,cash,diag=accepted_helpers();store,economics=cached_store(protocol,execution,r)
        signals=review_signals(manifests['cash'],choices,actions,store,economics,r)
        fields(read_json(manifests['cash']['signal_identification']),dict(selected_FX_actions=len(signals)),'new selected FX actions')
        summaries,daily,logs,books=review_books(protocol,manifests['cash'],signals,mothers,store,economics,execution,out,r,cash,diag)
        comparisons=review_comparisons(protocol,manifests['cash'],summaries,daily,logs,books,held,diag);progress(out,'paired_CI_and_gates',comparisons)
        assert sources==bundle(),'review source changed during actual'
        receipt=dict(schema='stage149_fx_incremental_independent_review_v1',completed=True,C=0,I=0,M=0,research_arithmetic_accepted=True,fixed_package_supported=comparisons['gate']['status']=='supported_limited_reconstruction_model_only',input_closure=closure,projection_review=projection_report,model_review=model_report,cash_accounts=books,comparisons=comparisons,new_SQL=0,new_fits=0,new_cash=0,new_labels=0,new_downloads=0,whole_DB_hashes=0,old_control_fits=0,old_control_cash_replays=0,old_models_or_ledger_full_reaudits=0,full_new_results_independent_review_completions=1,numeric_max_errors=dict(ERRORS),accepted_helper_numeric_errors=dict(cash.ERRORS),checker_sources=sources,strict_first_release_PIT_established=False,orderbook_execution_established=False,narrow_stop_is_universal_loss_bound=False,goal_complete=False,production_qualified=False,increased_betting_qualified=False,limitations=['Final ECB archive is not first-release vintage; assigned availability remains a historical assumption.','One global scalar does not identify month-specific FX or causal innovation; repeated as-of states are not independent releases.','Same historical search, overlapping starts and held families do not create unseen macro OOS; CI is conditional on fixed reconstructed paths.','Daily ideal native-bar execution, gap/stale/capacity and entry unknown limits survive nominal profit.','Old CONTROL remains an unsupported historical reference, never a newly promoted winner.'])
        write(out/'review_receipt.json',receipt);status='completed'
        return receipt
    except BaseException as exc:
        error=f'{type(exc).__name__}: {exc}';write(out/'failure_trace.json',dict(error=error,traceback=traceback.format_exc()));raise
    finally:
        write(out/'actual_terminal.json',dict(status=status,exit_code=0 if status=='completed' else 1,error=error,elapsed_seconds=time.monotonic()-started,new_SQL=0,new_fits=0,new_cash=0,new_labels=0,new_downloads=0,whole_DB_hashes=0,old_control_replays=0,full_new_results_independent_review_completions=int(status=='completed'),automatic_retry=False,fixture=False))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','protocol-sha256','authorization','authorization-sha256','output'):p.add_argument('--'+name,required=True)
    receipt=review(p.parse_args(argv));print(json.dumps(dict(completed=receipt['completed'],C=receipt['C'],I=receipt['I'],new_SQL=0,new_fits=0,new_cash=0)),flush=True)


if __name__=='__main__':main()
