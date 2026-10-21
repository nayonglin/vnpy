"""Frozen Stage453 source-X visibility/support. No Y, prices, scores, fit or API.

Import is inert. Only the explicit actual CLI reads the bound source, one mother
identity table and six original training identity/weight tables, once each.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, time as daytime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import time
import traceback
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

LINE = Path(__file__).resolve().parents[1]
PROTOCOL = LINE/'outputs/stage453_Con4_fixed_protocol/protocol.json'
PROTOCOL_SHA = 'c82dfb499558b0ecc32e8f9654b3361f68741a74400c67507b1d01a69ca9e053'
CLARIFICATIONS = LINE/'outputs/stage453_Con4_fixed_protocol/clock_implementation_clarifications.json'
CLARIFICATIONS_SHA = '9ce259c878659832da5d9b7e6936a5d724eafe1aba7449944d9092006945a5ff'
OUTPUT = LINE/'outputs/stage454_Con4_visible_support/actual_run1'
NY, SHANGHAI = ZoneInfo('America/New_York'), ZoneInfo('Asia/Shanghai')
MOTHER_COLS = ['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
TRAIN_COLS = ['sequence_index','mother_sequence_index','product_id','family_id','u_date','u_index','sample_weight']
MAPPING = {'002602':'DCE.C','007601':'DCE.Y','026603':'DCE.M','033661':'CZCE.CF',
           '080732':'CZCE.SR','084691':'SHFE.AG','085692':'SHFE.CU','088691':'SHFE.AU'}


def midnight(day):
    return datetime.combine(date.fromisoformat(str(day)), daytime.min, NY)


def calendar_add(instant, days):
    return midnight((instant.astimezone(NY).date()+timedelta(days=days)).isoformat())


def family_group(value):
    return int(hashlib.sha256(str(value).encode()).hexdigest(),16)%2


def compile_clock(rows, clock):
    """Keep every source row, then apply monotonic-asof state events per code."""
    episodes=[]; events=defaultdict(list)
    masks=[x['source_mask'] for x in clock['mask_decisions_10']]
    ids={x['mask_id'] for x in masks}
    interruptions=[]
    for key,start,end in [
        ('M2013_shutdown_clock_unknown','2013-10-04','2013-11-09'),
        ('M2018_19_backlog_actual_clock_gap','2018-12-28','2019-03-30'),
        ('M2023_ION_override','2023-02-03','2023-03-22'),
        ('M2025_intended_not_confirmed','2025-10-03',None)]:
        if key in ids:
            interruptions.append((midnight(start),midnight(end) if end else None,key))
            for code in MAPPING: events[code].append((midnight(start).timestamp(),1,'',-1,'clock_quarantine:'+key))
    if 'M2023_ION_override' in ids:
        for code in MAPPING: events[code].append((midnight('2023-03-17').timestamp(),1,'',-1,'ION2023_mar17_nonpublication'))
    pub=clock['publication_event_decisions_54']
    guards=clock['unaligned_event_guard_rule']['guards']
    seen=set()
    for i,raw in enumerate(rows):
        asof,code=raw['asof'],raw['market_code']; d=date.fromisoformat(asof)
        if code not in MAPPING or raw['channel']!=MAPPING[code] or (asof,code) in seen:
            raise ValueError('source_identity_mapping_or_duplicate')
        seen.add((asof,code))
        aligned=[e for e in pub if e.get('proposed_native_asof_for_design')==asof]
        confirmed=[e for e in aligned if e.get('proposed_research_available_at') and e['source_fields'].get('confirmed_release_date')]
        scheduled=next((e['source_fields']['original_scheduled_release_date'] for e in aligned
                        if e['source_fields'].get('original_scheduled_release_date')),None)
        if scheduled is None and d.weekday()==1: scheduled=(d+timedelta(days=3)).isoformat()
        reasons=[]; details=[]; status='assumed_normal_week'
        for m in masks:
            basis=m['basis']; hit=False
            if m['mask_id']=='M2023_ION_override': continue
            if m['mask_id']=='M2025_intended_not_confirmed': hit=asof>=m['start']
            elif basis=='position_asof_and_CFTC_code': hit=m['start']<=asof<=m['end_inclusive'] and code in m['target_codes']
            elif basis=='position_asof': hit=m['start']<=asof<=m['end_inclusive']
            elif basis=='original_scheduled_release_date': hit=scheduled is not None and m['start']<=scheduled<=m['end_inclusive']
            if hit:
                reasons.append('revision_quarantine' if basis=='position_asof_and_CFTC_code' else 'clock_quarantine')
                details.append(m['mask_id'])
        for name,g in guards.items():
            if g['position_asof_start_inclusive']<=asof<g['position_asof_end_exclusive']:
                reasons.append('unaligned_event');details.append(name)
        for e in aligned:
            if e['decision']=='quarantine_explicit_asof_plan_only': reasons.append('unconfirmed_plan');details.append(e['event_id'])
        q=raw.get('Con4Net_All')
        if q is None or not np.isfinite(q) or not -1<=q<=1:
            reasons.append('raw_numeric_unknown');details.extend(raw.get('unknown_reasons',[]))
        original_due=calendar_add(midnight(scheduled),1) if scheduled else None
        available=None; release_date=None; release_at=None; alignment='usual_Tuesday_Friday_assumption'; event_id=None
        if confirmed:
            if len(confirmed)!=1: raise ValueError('ambiguous_confirmed_release')
            e=confirmed[0]; available=datetime.fromisoformat(e['proposed_research_available_at']).astimezone(NY)
            release_date=e['source_fields']['confirmed_release_date']; release_at=e['source_fields'].get('confirmed_release_at')
            alignment=e['position_asof_alignment_status'];event_id=e['event_id'];status='explicit_date_boundary_assumption'
        # Two explicitly adopted publication anchors; do not generalize a revision's
        # date into vintage qualification for every unchanged market.
        elif asof=='2019-03-26' and code=='085692':
            available=midnight('2019-03-30');release_date='2019-03-29';alignment='explicit_source_asof';event_id='reporting2019_march_unrevised_copper_anchor';status='explicit_date_boundary_assumption'
        elif asof=='2011-10-11' and code=='002602':
            available=midnight('2011-10-15');release_date='2011-10-14';alignment='explicit_source_asof';event_id='OI2011_corn_adjusted_at_release';status='explicit_date_boundary_assumption'
        else:
            ion=next((m for m in masks if m['mask_id']=='M2023_ION_override'),None)
            if ion and scheduled and ion['start']<=scheduled<=ion['end_inclusive']:
                reasons.append('clock_quarantine');details.append('ION_ordinary_slot_suppressed')
            if d.weekday()!=1:
                reasons.append('unknown_unaligned');details.append('non_Tuesday_without_confirmed_release')
            elif scheduled:
                available=midnight((d+timedelta(days=11)).isoformat())
                if asof>'2013-11-08': status='normal_after_expected_resumption_assumption'
                if any(start.timestamp()<=available.timestamp() and (end is None or available.timestamp()<end.timestamp()) for start,end,_ in interruptions):
                    reasons.append('ordinary_grant_crosses_interruption')
        reasons=list(dict.fromkeys(reasons)); details=list(dict.fromkeys(details))
        suppressed_ion='ION_ordinary_slot_suppressed' in details
        if reasons:
            available=None
            status='unknown_unaligned' if any(x in reasons for x in ('unknown_unaligned','unaligned_event')) else 'unknown_planned' if 'unconfirmed_plan' in reasons else 'unknown_quarantined'
            # Ordinary deferred rows never enter this branch; ION slots are
            # suppressed and handled by explicit interruption/nonpublication reset.
            genuine_unknown=any(r!='ordinary_grant_crosses_interruption' for r in reasons)
            if original_due is not None and not suppressed_ion and genuine_unknown:
                events[code].append((original_due.timestamp(),1,asof,i,';'.join(reasons)))
        expiry=calendar_add(available,7) if available else None
        episode={**raw,'source_episode_index':i,'source_asof':asof,'source_CFTC_code':code,
            'clock_status':status,'source_confirmed_release_date':release_date,'source_confirmed_release_at':release_at,
            'position_asof_alignment_status':alignment,'original_scheduled_release_date':scheduled,
            'original_candidate_availability_at':original_due.isoformat() if original_due else None,
            'research_available_at':available.isoformat() if available else None,
            'research_expiry_at':expiry.isoformat() if expiry else None,
            'available_utc_epoch':available.timestamp() if available else None,
            'expiry_utc_epoch':expiry.timestamp() if expiry else None,
            'release_episode_id':('release:'+available.isoformat()+':'+asof) if available else None,
            'availability_group_id':('NY00:'+available.isoformat()) if available else None,
            'adopted_event_id':event_id,'row_quarantine_reasons':reasons,'row_quarantine_details':details,
            'strict_firstseen_or_vintage_verified':False,'ordinary_holiday_calendar_complete':False,
            'resumption_actual_confirmed':False}
        episodes.append(episode)
        if available:
            events[code].append((available.timestamp(),3 if release_date else 2,asof,i,''))
            events[code].append((expiry.timestamp(),0,asof,i,'expired'))
    streams={}
    for code,ev in events.items():
        current=-1;floor='';states=[]
        for instant,kind,asof,i,reason in sorted(ev):
            if kind==0:
                if current!=i: continue
                current=-1; state_reason='expired'
            elif kind==1:
                if asof and asof<floor: continue
                floor=max(floor,asof);current=-1;state_reason=reason
            else:
                if asof<=floor:
                    episodes[i]['row_quarantine_reasons'].append('older_than_consumed_source_asof')
                    episodes[i]['row_quarantine_details'].append('late_grant_rejected')
                    episodes[i]['research_available_at']=None;episodes[i]['research_expiry_at']=None
                    episodes[i]['available_utc_epoch']=None;episodes[i]['expiry_utc_epoch']=None
                    episodes[i]['availability_group_id']=None;episodes[i]['release_episode_id']=None
                    continue
                floor=asof;current=i;state_reason=''
            if states and states[-1]['source_episode_index']>=0:
                old=episodes[states[-1]['source_episode_index']]
                if instant<old['expiry_utc_epoch']:
                    old['expiry_utc_epoch']=instant;old['research_expiry_at']=datetime.fromtimestamp(instant,NY).isoformat()
            state=dict(utc_epoch=instant,source_episode_index=current,unknown_reason=state_reason,consumed_source_asof_floor=floor)
            if states and states[-1]['utc_epoch']==instant:states[-1]=state
            else:states.append(state)
        streams[code]=states
    return episodes,streams


def project_mothers(mothers, episodes, streams):
    """Exact product/date cutoff at 15:00 Shanghai; unknown never backfills."""
    out=mothers.copy(); n=len(out)
    idx=np.full(n,-1,dtype=np.int64);reasons=np.full(n,'structurally_unmapped',dtype=object)
    cutoff={d:datetime.combine(date.fromisoformat(d),daytime(15),SHANGHAI).timestamp() for d in out.u_date.unique()}
    times=out.u_date.map(cutoff).to_numpy(float)
    for code,product in MAPPING.items():
        ii=np.flatnonzero(out.product_id.to_numpy()==product)
        state=streams.get(code,[])
        if not len(ii):continue
        reasons[ii]='not_yet_available_or_deferred_by_policy'
        if not state:continue
        loc=np.searchsorted(np.array([s['utc_epoch'] for s in state]),times[ii],side='right')-1
        good=loc>=0
        si=np.array([s['source_episode_index'] for s in state],dtype=np.int64)
        rr=np.array([s['unknown_reason'] for s in state],dtype=object)
        idx[ii[good]]=si[loc[good]];reasons[ii[good]]=rr[loc[good]]
    q=np.full(n,np.nan,dtype=np.float64);finite=idx>=0
    q[finite]=np.array([episodes[j]['Con4Net_All'] for j in idx[finite]],dtype=np.float64)
    out['q_raw']=q;out['source_episode_index']=idx;out['unknown_reason']=reasons
    for col in ['source_asof','source_CFTC_code','clock_status','availability_group_id','release_episode_id','research_available_at','research_expiry_at']:
        vals=np.full(n,'',dtype=object)
        vals[finite]=[episodes[j][col] or '' for j in idx[finite]]
        out[col]=vals
    out.loc[~finite & out.unknown_reason.eq('structurally_unmapped'),'clock_status']='structurally_unmapped'
    out.loc[~finite & ~out.unknown_reason.eq('structurally_unmapped'),'clock_status']='unknown'
    return out


def q_statistics(q, weights):
    q=np.asarray(q,float);weights=np.asarray(weights,float)
    if q.shape!=weights.shape or not np.isfinite(weights).all() or (weights<=0).any():raise ValueError('invalid_original_weights')
    finite=np.isfinite(q);mean=var=None
    if finite.any():
        mean=float(np.average(q[finite],weights=weights[finite]));var=float(np.average((q[finite]-mean)**2,weights=weights[finite]))
    ready=bool(mean is not None and var is not None and np.isfinite(mean) and np.isfinite(var) and var>0 and (np.abs(q[finite])<=1).all())
    return dict(ready=ready,training_rows=len(q),finite_count=int(finite.sum()),missing_count=int((~finite).sum()),
        finite_weight_sum=float(weights[finite].sum()),missing_weight_sum=float(weights[~finite].sum()),
        mean=mean,var=var,scale=float(np.sqrt(var)) if ready else None,
        raw_finite_min=float(q[finite].min()) if finite.any() else None,raw_finite_max=float(q[finite].max()) if finite.any() else None)


def support_summary(frame, weights):
    weights=np.asarray(weights,float);q=frame.q_raw.to_numpy(float);finite=np.isfinite(q)
    f=frame.loc[finite].copy();f['original_weight']=weights[finite]
    def concentration(column):
        totals=f.groupby(column,sort=True).original_weight.sum();total=float(totals.sum())
        shares=totals.to_numpy(float)/total if total else np.array([])
        return dict(groups=len(totals),weight_sum=total,max_share=float(shares.max()) if len(shares) else None,
            hhi=float(shares@shares) if len(shares) else None,effective_groups=float(1/(shares@shares)) if len(shares) else None,
            weights=[dict(group=str(k),original_weight=float(v),share=float(v/total)) for k,v in totals.items()])
    return dict(rows=len(frame),finite_rows=len(f),unknown_reason_counts={str(k):int(v) for k,v in frame.loc[~finite].unknown_reason.value_counts().items()},
        q_statistics=q_statistics(q,weights),availability_groups=int(f.availability_group_id.nunique()),
        release_episodes=int(f.release_episode_id.nunique()),source_asofs=int(f.source_asof.nunique()),
        episode_channels=int(f[['release_episode_id','source_CFTC_code']].drop_duplicates().shape[0]),
        mapped_families=int(f.family_id.nunique()),mapped_family_ids=sorted(f.family_id.unique()),
        source_years=sorted(f.source_asof.str[:4].unique()),
        clock_status_counts={str(k):int(v) for k,v in f.clock_status.value_counts().items()},
        availability_weight_concentration=concentration('availability_group_id'),
        episode_weight_concentration=concentration('release_episode_id'),
        annual=[dict(year=str(y),mother_or_child_rows=len(g),finite_rows=int(np.isfinite(g.q_raw).sum()),
            availability_groups=int(g.loc[np.isfinite(g.q_raw),'availability_group_id'].nunique()),
            mapped_family_ids=sorted(g.loc[np.isfinite(g.q_raw),'family_id'].unique()))
            for y,g in frame.groupby(frame.u_date.str[:4],sort=True)])


def validate_training_identity(train, mothers, fold):
    if len(train)!=fold['training_rows']:raise ValueError('original_training_row_count')
    if train.sequence_index.duplicated().any() or not train.sequence_index.is_monotonic_increasing:raise ValueError('original_training_order')
    ii=train.mother_sequence_index.to_numpy(np.int64)
    if (ii<0).any() or (ii>=len(mothers)).any():raise ValueError('parent_identity_index')
    for c in ['product_id','family_id','u_date','u_index']:
        if not np.array_equal(train[c].to_numpy(),mothers[c].to_numpy()[ii]):raise ValueError('parent_identity_'+c)
    if not train.u_date.lt(fold['cutoff']).all():raise ValueError('training_cutoff')
    if fold['scope']!='main' and train.family_id.map(family_group).eq(int(fold['scope'][-1])).any():raise ValueError('held_training_family_leak')
    for key,value in [('training_dates',train.u_date.nunique()),('training_families',train.family_id.nunique()),
                      ('training_groups',len(train[['family_id','u_date']].drop_duplicates())),('max_u_date',train.u_date.max())]:
        if key in fold and value!=fold[key]:raise ValueError('original_training_identity_'+key)
    w=train.sample_weight.to_numpy(float)
    if not np.isfinite(w).all() or (w<=0).any():raise ValueError('invalid_original_weights')


def stat_bound(binding):
    p=Path(binding['path']);s=p.stat()
    if not p.is_file() or s.st_size!=binding['bytes']:raise ValueError('inherited_binding_size_changed '+str(p))
    return dict(path=str(p),bytes=s.st_size,device=s.st_dev,inode=s.st_ino,mtime_ns=s.st_mtime_ns,
                inherited_sha256=binding['sha256'],rehashed=False)


def binding(path):
    p=Path(path);b=p.read_bytes()
    return dict(path=str(p.resolve()),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())


def write_json(path,obj):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')


def read_identity(spec,columns,numeric,counters):
    counters[spec['path']]+=1
    frame=pd.read_csv(spec['path'],usecols=columns,dtype=str,keep_default_na=False,float_precision='round_trip')
    for c in numeric:frame[c]=frame[c].astype(np.int64 if c!='sample_weight' else float)
    return frame


def run_actual(protocol,output,code_sha):
    """One reserved run; partial errors remain in manifest and never auto-retry."""
    started=time.monotonic();output.mkdir(parents=True,exist_ok=False)
    design=protocol['experiment_design452'];refs=design['identity_reuse'];folds=refs['original130_folds']
    inputs=dict(mothers=refs['inputs']['mothers'],numeric448=protocol['input_bindings']['numeric448'],
                clock_implementation_clarifications=dict(path=str(CLARIFICATIONS),bytes=1801,sha256=CLARIFICATIONS_SHA),
                training_identity_weights=[f['training_identity_weights'] for f in folds])
    specs=[inputs['numeric448'],inputs['mothers']]+inputs['training_identity_weights']+[f['scaler'] for f in folds]
    counters=Counter();before=[];after=[];records=[];artifacts={};error=None
    try:
        before=[stat_bound(s) for s in specs]
        source=inputs['numeric448'];counters[source['path']]+=1;raw=Path(source['path']).read_bytes()
        if len(raw)!=source['bytes'] or hashlib.sha256(raw).hexdigest()!=source['sha256']:raise ValueError('numeric448_binding_changed')
        rows=[json.loads(line) for line in raw.splitlines() if line.strip()];del raw
        if len(rows)!=6680 or len({r['asof'] for r in rows})!=835:raise ValueError('original_source_row_count')
        expected={(r['asof'],code) for r in rows for code in MAPPING}
        if {(r['asof'],r['market_code']) for r in rows}!=expected:raise ValueError('source_full_date_code_grid')
        episodes,streams=compile_clock(rows,protocol['clock_contract451']);del rows
        mothers=read_identity(inputs['mothers'],MOTHER_COLS,['sequence_index','u_index'],counters)
        if len(mothers)!=399252 or not np.array_equal(mothers.sequence_index,np.arange(len(mothers))) or mothers.event_id.duplicated().any() or mothers.duplicated(['product_id','u_date']).any():raise ValueError('original_full_mother_identity')
        if mothers.product_id.nunique()!=98 or mothers.family_id.nunique()!=95 or int(mothers.u_date.ge('2020-01-01').sum())!=161014:raise ValueError('original_full_market_universe')
        visible=project_mothers(mothers,episodes,streams)
        path=output/'visible_mother_con4.npz'
        with path.open('xb') as f:np.savez_compressed(f,q_raw=visible.q_raw.to_numpy(np.float64),sequence_index=mothers.sequence_index.to_numpy(np.int64),source_episode_index=visible.source_episode_index.to_numpy(np.int64))
        artifacts['visible_mother_con4']=binding(path)
        path=output/'source_episodes.jsonl'
        with path.open('x',encoding='utf-8') as f:
            for e in episodes:f.write(json.dumps(e,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n')
        artifacts['source_episodes']=binding(path)
        path=output/'visible_mother_audit.csv.gz';visible.to_csv(path,index=False,float_format='%.17g',compression=dict(method='gzip',mtime=0));artifacts['visible_mother_audit']=binding(path)
        write_json(output/'clock_state_streams.json',streams);artifacts['clock_state_streams']=binding(output/'clock_state_streams.json')
        for fold in folds:
            train=read_identity(fold['training_identity_weights'],TRAIN_COLS,['sequence_index','mother_sequence_index','u_index','sample_weight'],counters)
            validate_training_identity(train,mothers,fold)
            ti=train.mother_sequence_index.to_numpy(np.int64);train_visible=visible.iloc[ti].reset_index(drop=True)
            train_stats=support_summary(train_visible,train.sample_weight.to_numpy(float))
            cutoff=fold['cutoff'];next_cutoff='2023-01-01' if cutoff=='2020-01-01' else None
            mask=mothers.u_date.ge(cutoff)&(mothers.u_date.lt(next_cutoff) if next_cutoff else True)
            if fold['scope']!='main':mask &= mothers.family_id.map(family_group).eq(int(fold['scope'][-1]))
            pred=visible.loc[mask].copy()
            if len(pred)!=fold['prediction_mothers']:raise ValueError('original_prediction_mother_count '+fold['scope']+'/'+cutoff)
            pred_stats=support_summary(pred,np.ones(len(pred)))
            passed=bool(train_stats['q_statistics']['ready'] and train_stats['availability_groups']>=2 and pred_stats['availability_groups']>=2
                and train_stats['mapped_families']>=2 and pred_stats['mapped_families']>=2
                and len(train_stats['source_years'])>=2 and len(pred_stats['source_years'])>=2)
            records.append(dict(scope=fold['scope'],cutoff=cutoff,passed=passed,q_statistics=train_stats['q_statistics'],
                training_identity_weights=fold['training_identity_weights'],scaler=fold['scaler'],
                training_identity_verified=True,training_row_order_preserved=True,weights_recomputed=False,
                prediction_mothers=len(pred),training_support=train_stats,prediction_support=pred_stats))
            print(json.dumps(dict(phase='source_support',scope=fold['scope'],cutoff=cutoff,passed=passed)),flush=True)
        after=[stat_bound(s) for s in specs]
        if before!=after:raise ValueError('input_stat_changed_during_single_pass')
        global_support=support_summary(visible,np.ones(len(visible)))
        write_json(output/'mother_support.json',global_support);artifacts['mother_support']=binding(output/'mother_support.json')
    except Exception:
        error=traceback.format_exc()
        after=[]
        for s in specs:
            try:after.append(stat_bound(s))
            except Exception as exc:after.append(dict(path=s['path'],stat_error=str(exc)))
    manifest=dict(schema='stage454_con4_visible_source_manifest_v1',status='failed' if error else 'completed',
        protocol_sha256=PROTOCOL_SHA,clock_implementation_clarifications_sha256=CLARIFICATIONS_SHA,
        code_sha256=code_sha,created_at=datetime.now(timezone.utc).isoformat(),
        inputs=inputs,artifacts=artifacts,sixfold_source_support=records,
        all_support_passed=not error and len(records)==6 and all(r['passed'] for r in records),
        source_input_pass_counts=dict(counters),input_stats_before=before,input_stats_after=after,
        physical_counts=dict(source_numeric_passes=counters[inputs['numeric448']['path']],mother_identity_passes=counters[inputs['mothers']['path']],
            training_identity_passes=sum(counters[s['path']] for s in inputs['training_identity_weights']),Y=0,prices=0,scores=0,common26=0,raw_ZIP=0,fit=0,cash=0,SQL=0,API=0),
        actual_parameters=dict(ordinary_lag_calendar_days_from_native_Tuesday=11,TTL_NY_calendar_days=7,
            observation_cutoff='15:00 Asia/Shanghai',ordinary_holiday_calendar_complete=False,strict_firstseen_or_vintage_verified=False,
            active_interruptions=[['2013-10-04','2013-11-09'],['2018-12-28','2019-03-30'],['2023-02-03','2023-03-22'],['2025-10-03',None]],
            column='Con4Net_All',unknown_raw='NaN',weights='original130 sample_weight, finite-q weighted population variance'),
        exceptions=[] if not error else [error],elapsed_seconds=time.monotonic()-started,
        new_training_or_cash_authorized=False,formal_C9_change=False,strict_PIT_qualified=False)
    write_json(output/'manifest.json',manifest)
    print(json.dumps(dict(status=manifest['status'],all_support_passed=manifest['all_support_passed'],elapsed_seconds=manifest['elapsed_seconds'])),flush=True)
    if error:raise RuntimeError(error)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actual',action='store_true');parser.add_argument('--expected-code-sha256')
    args=parser.parse_args()
    if not args.actual:parser.error('explicit --actual required; imports and fixtures perform no actual reads')
    code_sha=binding(__file__)['sha256']
    if args.expected_code_sha256!=code_sha:raise ValueError('exact_code_sha_required')
    body=PROTOCOL.read_bytes()
    if hashlib.sha256(body).hexdigest()!=PROTOCOL_SHA:raise ValueError('frozen453_protocol_changed')
    clarify=CLARIFICATIONS.read_bytes()
    if hashlib.sha256(clarify).hexdigest()!=CLARIFICATIONS_SHA:raise ValueError('frozen453_clarifications_changed')
    run_actual(json.loads(body),OUTPUT,code_sha)


if __name__=='__main__':main()
