"""Frozen605, report-unit Corn residual falsification. No import-time data I/O.

Original52 is fixed; only2 seasonal means and2 scalar heads may be fitted. Root
alone runs --actual after source review. Large inherited inputs are not rehashed.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,math,re,time
from collections import Counter,defaultdict
from datetime import date,datetime,time as dtime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent;LINE=TOOLS.parent
PROTOCOL=LINE/'outputs/stage605_wasde_report_residual_protocol/protocol.json'
PROTOCOL_SHA='5cc338a105bb8229456bd64a9c6a250b34ab3875fcdc52636f39419c9c29783d'
END='2026-10-16';CUTOFFS=('2020-01-01','2023-01-01')
PRIMARY=('2020/21','2021/22','2023/24','2024/25','2025/26')
COMMON_COLS=['sequence_index','action_id','mother_sequence_index','mother_event_id','product_id','family_id','u_date','u_index','reference_epoch','u_action_eligible','label_state','participation_state','net_R_stress','label_known_date']
COUNTS=('original_child_rows','ineligible_child_rows','nonparticipation_child_rows','unknown_child_rows','known_child_rows','before_availability_rows','target_child_rows')


def number(v):
    try:return float(v)
    except (TypeError,ValueError):return math.nan

def finite(v):return math.isfinite(number(v))
def available(day):
    return datetime.combine(date.fromisoformat(day)+timedelta(days=2),dtime(),ZoneInfo('America/New_York')).astimezone(timezone.utc).isoformat()

def training_MY_allowed(my,cutoff):
    return bool(re.fullmatch(r'\d{4}/\d{2}',my or '') and int(my[:4])+1<int(cutoff[:4]))

def source_for_u(day,sources):
    s=sources.get(day[:7])
    if s is None:return dict(active=False,reason='no_source_month')
    if not s['eligible']:return dict(s,active=False,reason=s.get('reason','source_unknown'))
    close=datetime.combine(date.fromisoformat(day),dtime(15),ZoneInfo('Asia/Shanghai')).astimezone(timezone.utc)
    ok=close>=datetime.fromisoformat(available(s['release_date']))
    return dict(s,active=ok,reason='known_pair_available' if ok else 'before_availability')

def build_sources(grid):
    sources={};ncontent=0;nconditional=0
    for raw in grid:
        month=raw['release_month'];known=raw['content_pair_state']=='two_current_Proj_cells_same_MY'
        ncontent+=int(known);c=raw.get('cell_evidence_current');p=raw.get('cell_evidence_previous')
        eligible=known and not raw.get('visible_V2',False)
        my=raw.get('selected_latest_common_MY') or (raw.get('new_Proj_MY_first_seen') or [''])[0]
        s=dict(release_month=month,release_date=None,report_id='unknown-'+month,MY=my or '',x=None,
            eligible=eligible,reason='source_'+raw['content_pair_state'],source_pair_state=raw['content_pair_state'])
        if known:
            assert c['ProjEstFlag']==p['ProjEstFlag']=='Proj.' and c['MarketYear']==p['MarketYear']==my
            assert c['Unit']==p['Unit']=='Million Bushels' and c['ReportTitle']==p['ReportTitle']=='U.S. Feed Grain and Corn Supply and Use'
            assert c['Commodity']==p['Commodity']=='Corn' and c['Region']==p['Region']=='United States'
            assert c['Attribute']==p['Attribute']=='Production'
            def day(text):
                for fmt in ('%Y-%m-%d','%m/%d/%Y'):
                    try:return datetime.strptime(text,fmt).date().isoformat()
                    except ValueError:pass
                raise ValueError('explicit release date required')
            cd,pd_=day(c['ReleaseDate']),day(p['ReleaseDate'])
            first=date.fromisoformat(month+'-01');prev=(first-timedelta(days=1)).strftime('%Y-%m')
            assert cd[:7]==month and pd_[:7]==prev
            for cell,d in ((c,cd),(p,pd_)):
                assert (int(cell['ForecastYear']),int(cell['ForecastMonth']))==(int(d[:4]),int(d[5:7]))
            P,Q=float(c['Value']),float(p['Value'])
            assert math.isfinite(P) and math.isfinite(Q) and P>0 and Q>0
            s.update(release_date=cd,report_id=c['WasdeNumber']+'|'+cd+'|'+my,x=(P-Q)/Q,
                current_value=c['Value'],previous_value=p['Value'],current_cell=c,previous_cell=p,
                availability=available(cd),reason='known_conditional_pair' if eligible else 'V2_correction_known_at_unknown')
        if eligible:nconditional+=1
        if month in sources:raise ValueError('duplicate source month')
        sources[month]=s
    assert len(sources)==199 and ncontent==162 and nconditional==160
    return sources


def aggregate_reports(rows,sources,cutoff,train,end,calendar=None):
    def in_window(day):return day<cutoff if train else cutoff<=day<('2023-01-01' if cutoff=='2020-01-01' else '9999') and day<=end
    reports={}
    for month,s in sources.items():
        if not in_window(month+'-01'):continue
        reports[month]=dict(release_month=month,report_id=s['report_id'],release_date=s.get('release_date'),MY=s['MY'],x=s.get('x'),
            eligible=s['eligible'],source_reason=s['reason'],cutoff=cutoff,train=train,target=None,known_u=0,observed_u=0,
            **{c:0 for c in COUNTS},old_sample_weight_sum=0.,old_sample_weight_finite_rows=0)
    us={};seen=set()
    for r in rows:
        day=r['u_date']
        if not in_window(day):continue
        if not train and r.get('cutoff',cutoff)!=cutoff:raise ValueError('forward deployment cutoff mismatch')
        if r['product_id']!='DCE.C' or r['family_id']!='DCE.C' or not r['reference_epoch'].startswith('DCE.C.'):
            raise ValueError('Corn identity mismatch')
        if r['action_id'] in seen:raise ValueError('duplicate Corn child')
        seen.add(r['action_id'])
        if calendar is not None and calendar[int(r['u_index'])]!=day:raise ValueError('u calendar identity')
        month=day[:7];s=source_for_u(day,sources)
        if day not in us:us[day]=dict(u_date=day,release_month=month,report_id=s.get('report_id','unknown-'+month),cutoff=cutoff,train=train,
            active_source=s['active'],source_reason=s['reason'],**{c:0 for c in COUNTS},residual_sum=0.,target=None)
        u=us[day];u['original_child_rows']+=1
        if not s['active']:u['before_availability_rows']+=int(s['reason']=='before_availability')
        y=number(r['net_R_stress']);ahat=number(r.get('Ahat',r.get('score')));known=r['label_known_date']
        matured=bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}',known) and (known<cutoff if train else known<=end))
        if number(r['u_action_eligible'])!=1:state='ineligible_child_rows'
        elif r['participation_state']=='known_nonparticipation':state='nonparticipation_child_rows'
        elif r['label_state']!='closed_complete_bar_model' or not math.isfinite(y) or not math.isfinite(ahat) or not matured:state='unknown_child_rows'
        else:state='known_child_rows'
        u[state]+=1
        allowed=s['active'] and (not train or training_MY_allowed(s.get('MY',''),cutoff))
        if allowed and state=='known_child_rows':u['target_child_rows']+=1;u['residual_sum']+=y-ahat
        rr=reports.get(month)
        if rr is not None and finite(r.get('sample_weight')):
            rr['old_sample_weight_sum']+=float(r['sample_weight']);rr['old_sample_weight_finite_rows']+=1
    for u in us.values():
        if u['target_child_rows']:u['target']=u['residual_sum']/u['target_child_rows']
        r=reports.get(u['release_month'])
        if r is None:continue
        r['observed_u']+=1
        for c in COUNTS:r[c]+=u[c]
        if u['target'] is not None:r.setdefault('_targets',[]).append(u['target'])
    for r in reports.values():
        targets=r.pop('_targets',[]);r['known_u']=len(targets)
        if not r['eligible']:r['report_state']='source_unknown'
        elif train and not training_MY_allowed(r['MY'],cutoff):r['report_state']='head_MY_boundary_excluded'
        elif not targets:r['report_state']='no_known_mature_target'
        else:r['target']=float(np.mean(targets));r['report_state']='known_mature_subset'
        r['target_scope']='known eligible mature children, equal child within u then equal u; unknown never0'
    return list(reports.values()),list(us.values())


def fit_heads(reports,on_operation=None):
    train=[r for r in reports if finite(r.get('target')) and finite(r.get('x')) and r.get('eligible',True)]
    M=len(train);B=dict(status='unsupported',reports=M,month_means={});C=dict(status='unsupported',reports=M,MY_count=len({r['MY'] for r in train}),gamma=None,sigma=None,month_centers={},lambda_=1.)
    if not M:return dict(B=B,C=C)
    if on_operation:on_operation('B_month_means')
    groups=defaultdict(list)
    for r in train:groups[r['release_month'][5:7]].append(r)
    B.update(status='supported',month_means={m:float(np.mean([r['target'] for r in rs])) for m,rs in groups.items()})
    centers={m:float(np.mean([r['x'] for r in rs])) for m,rs in groups.items()};C['month_centers']=centers
    q=np.array([r['x']-centers[r['release_month'][5:7]] for r in train]);var=float(np.mean(q*q));C['within_month_variance']=var
    if M<2 or C['MY_count']<2 or not math.isfinite(var) or var<=0:return dict(B=B,C=C)
    sigma=math.sqrt(var);z=q/sigma;e=np.array([r['target']-B['month_means'][r['release_month'][5:7]] for r in train])
    if on_operation:on_operation('C_scalar_solve')
    numerator=float(np.mean(z*e));denominator=float(np.mean(z*z)+1.);gamma=numerator/denominator
    C.update(status='supported',sigma=sigma,gamma=gamma,numerator=numerator,denominator=denominator,
        normalized_weight_sum=1.,sum_weighted_z=float(np.mean(z)),normal_equation_abs_residual=abs(gamma*denominator-numerator))
    return dict(B=B,C=C)


def score_reports(reports,heads):
    B,C=heads['B'],heads['C'];out=[]
    for raw in reports:
        r=dict(raw);m=r['release_month'][5:7];seen=m in B['month_means'];sourceok=r.get('eligible',True) and finite(r.get('x'))
        modelok=B['status']=='supported' and C['status']=='supported'
        usable=seen and sourceok and modelok
        b=B['month_means'][m] if seen and sourceok else 0.
        z=(r['x']-C['month_centers'][m])/C['sigma'] if usable else None
        c=b+C['gamma']*z if usable else 0. if not seen or not sourceok else None
        r.update(pred_A=0.,pred_B=b,pred_C=c,z=z,delta_prediction=c-b if c is not None else None,
            scored=bool(usable and finite(r.get('target'))),score_state='known_conditional' if usable else 'unseen_month_shared_A' if not seen else 'source_shared_A' if not sourceok else 'C_unsupported')
        for arm,p in [('A',0.),('B',b),('C',c)]:r['loss_'+arm]=(r['target']-p)**2 if r['scored'] else None
        out.append(r)
    return out


def cycle_metadata(my,end):
    y=int(my[:4]);start=f'{y}-05-01';finish=f'{y+1}-04-30';marketing_end=f'{y+1}-08-31'
    deployment='2020-01-01' if start>='2020-01-01' and finish<'2023-01-01' else '2023-01-01' if start>='2023-01-01' and finish<=end else None
    return dict(forecast_publication_cycle_start=start,forecast_publication_cycle_end=finish,
        actual_marketing_year_end=marketing_end,one_deployment_window=deployment,forecast_cycle_wholly_in_one_window=deployment is not None,
        actual_marketing_year_finished=marketing_end<=end,primary=my in PRIMARY)


def evaluate(scored,heads,invariants,end):
    known=[r for r in scored if r['scored']];eras={};groups={}
    def stats(rs):
        d=dict(scored_reports=len(rs),nonzero_C_minus_B=sum(r['delta_prediction']!=0 for r in rs))
        for arm in ('A','B','C'):d['MSE_'+arm]=float(np.mean([r['loss_'+arm] for r in rs])) if rs else None
        d['Delta_BC']=d['MSE_B']-d['MSE_C'] if rs else None;return d
    for cut in CUTOFFS:eras[cut]=stats([r for r in known if r['cutoff']==cut])
    for my in sorted(set(PRIMARY)|{r['MY'] for r in scored if r.get('MY')}):groups[my]=dict(stats([r for r in known if r['MY']==my]),**cycle_metadata(my,end))
    primary=[groups[y]['Delta_BC'] for y in PRIMARY];all5=all(v is not None for v in primary)
    pooled=float(np.mean(primary)) if all5 else None
    gate=dict(identity_clock_maturity_fallback_invariants=bool(invariants),both_C_supported=all(heads[c]['C']['status']=='supported' for c in CUTOFFS),
        each_era_C_over_B=all(v['Delta_BC'] is not None and v['Delta_BC']>0 for v in eras.values()),
        each_era_C_not_worse_A=all(v['MSE_C'] is not None and v['MSE_C']<=v['MSE_A'] for v in eras.values()),
        all5_primary_supported_nonnegative=all5 and all(v>=0 for v in primary),equal_MY_mean_positive=pooled is not None and pooled>0,
        each_era_nonzero_delta=all(v['nonzero_C_minus_B']>0 for v in eras.values()))
    gate['passed']=all(gate.values())
    ci=dict(status='unsupported_missing_primary_MY',replicates=2000,seed=20261021,interval=None,descriptive_only=True,gate=False)
    if all5:
        values=np.asarray(primary);rng=np.random.default_rng(20261021);draws=values[rng.integers(0,len(values),(2000,len(values)))].mean(axis=1)
        ci.update(status='descriptive_few_dependent_MY',mean=pooled,interval=np.quantile(draws,[.025,.975],method='linear').tolist())
    return dict(eras=eras,MY_groups=groups,primary_MY_equal_mean_Delta_BC=pooled,gate=gate,descriptive_MY_bootstrap=ci,
        training_report_equal=True,report_targets_known_mature_subset=True,alpha_qualified=False,cash_qualified=False)


def binding(path):
    p=Path(path).resolve();raw=p.read_bytes()
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def read_small(b):
    if b['bytes']>2_000_000:raise ValueError('not a small input')
    raw=Path(b['path']).read_bytes()
    if len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:raise ValueError('small binding changed '+b['path'])
    return json.loads(raw)

def inherited_stat(b):
    p=Path(b['path']);s=p.stat()
    if s.st_size!=b['bytes'] or not p.is_file():raise ValueError('inherited size differs '+str(p))
    return dict(path=str(p),bytes=s.st_size,inode=s.st_ino,device=s.st_dev,mtime_ns=s.st_mtime_ns,
        inherited_sha256=b['sha256'],rehashed=False)

def write_json(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def ready_inputs(protocol):
    src=protocol['source'];small={k:src[k] for k in ('pair_grid','summary','root604','review603','interface607','design606','accepted538_review539','calendar')}
    for f in src['train_compact']:
        for k in ('original_model','original_scaler'):small[k+'_'+f['cutoff']]=f[k]
    return small

def check_ready(path,expected_sha):
    b=binding(path)
    if b['sha256']!=expected_sha:raise ValueError('source-ready binding mismatch')
    ready=read_small(b);pb=binding(PROTOCOL)
    if pb['sha256']!=PROTOCOL_SHA or ready['protocol']!=pb:raise ValueError('frozen605 mismatch')
    protocol=read_small(pb)
    for key in ('source','fixture','fixture_receipt'):
        if binding(ready[key]['path'])!=ready[key]:raise ValueError('source/test/receipt changed')
    receipt=read_small(ready['fixture_receipt'])
    if receipt.get('exit_code')!=0 or receipt['source']!=ready['source'] or receipt['fixture']!=ready['fixture']:
        raise ValueError('fixture receipt not for this source')
    if ready['small_inputs']!=ready_inputs(protocol):raise ValueError('source-ready inputs differ')
    return ready,b,protocol,pb


def read_corn_once(b,train):
    columns=COMMON_COLS+(['Ahat','sample_weight'] if train else ['score','scope','cutoff'])
    parts=[];allrows=0
    for part in pd.read_csv(b['path'],usecols=columns,dtype=str,keep_default_na=False,chunksize=100000):
        allrows+=len(part);mask=part.product_id.eq('DCE.C')
        if not train:mask &=part.scope.eq('main')
        if mask.any():parts.append(part.loc[mask].copy())
    frame=pd.concat(parts,ignore_index=True) if parts else pd.DataFrame(columns=columns)
    if frame.action_id.duplicated().any():raise ValueError('duplicate cached Corn child')
    return frame,allrows


def source_coverage(sources,scored):
    result={}
    for my in sorted({r['MY'] for r in scored if r.get('MY')}):
        y=int(my[:4]);months=[f'{yy}-{m:02d}' for yy in (y,y+1) for m in range(1,13) if f'{y}-05'<=f'{yy}-{m:02d}'<=f'{y+1}-04']
        known=[m for m in months if sources.get(m,{}).get('eligible') and sources[m]['MY']==my]
        rows=[r for r in scored if r['MY']==my]
        result[my]=dict(**cycle_metadata(my,END),forecast_cycle_months=months,expected_feature_months=months[1:],May_first_new_Proj_not_a_pair=months[0],
            conditional_source_months=known,source_pair_months=len(known),missing_or_not_pair_months=[m for m in months if m not in known],
            known_target_reports=sum(finite(r.get('target')) for r in rows),scored_reports=sum(r['scored'] for r in rows),
            unknown_child_rows=sum(r['unknown_child_rows'] for r in rows),target_child_rows=sum(r['target_child_rows'] for r in rows),
            source_complete_not_claimed=True)
    return result


def run_actual(args):
    ready,rb,protocol,pb=check_ready(args.source_ready,args.source_ready_sha256)
    output=Path(args.output).resolve();root=LINE/'outputs/stage607_wasde_report_residual'
    if output.exists() or output.parent!=root or output.name!='actual_run1':raise ValueError('fresh unique607 actual_run1 required')
    output.mkdir();began=time.monotonic();artifacts={};status='failed';error=None
    counts=dict(B_fits=0,C_scalar_solves=0,actual_fitted_objects=0,train_compact_reads=0,forward_compact_reads=0,
        new_cash=0,full_policy_reselection=0,base52_refits=0,COMMON_reads=0,native_reads=0,SQL=0,downloads=0,old_large_hashes=0)
    def save(name,value):
        write_json(output/name,value);artifacts[name]=binding(output/name)
    def save_csv(name,frame):
        pd.DataFrame(frame).to_csv(output/name,index=False,compression={'method':'gzip','mtime':0})
        artifacts[name]=binding(output/name)
    save('started.json',dict(schema='stage607_started_v1',protocol=pb,source_ready=rb,started_at=datetime.now(timezone.utc).isoformat(),automatic_retry=False))
    try:
        small={k:read_small(b) for k,b in ready['small_inputs'].items()};calendar=small['calendar']
        if len(calendar)!=5587:raise ValueError('original calendar length')
        sources=build_sources(small['pair_grid']);save('source_months.json',sources)
        large={f['cutoff']:f['binding'] for f in protocol['source']['train_compact']};large['forward']=protocol['source']['forward_compact']
        before={k:inherited_stat(b) for k,b in large.items()};train_frames={};raw_counts={};caches={}
        for fold in protocol['source']['train_compact']:
            cutoff=fold['cutoff'];model=small['original_model_'+cutoff];scaler=small['original_scaler_'+cutoff]
            if (model['scope']!='main' or model['cutoff']!=cutoff or len(model['coef'])!=52
                    or len(scaler['common']['columns'])!=26 or model['feature_names']!=scaler['feature_names']):
                raise ValueError('immutable original52 metadata')
            frame,n=read_corn_once(fold['binding'],True);counts['train_compact_reads']+=1
            if n!=fold['expected_all_rows']:raise ValueError('original train rows differ')
            # Original cache is a mature train table; never silently make a corrupt
            # original training input look like additional legitimate missing data.
            good=(frame.u_date.lt(cutoff)&frame.label_known_date.ne('')&frame.label_known_date.lt(cutoff)
                &frame.label_state.eq('closed_complete_bar_model')&frame.u_action_eligible.eq('1')
                &np.isfinite(pd.to_numeric(frame.net_R_stress,errors='coerce'))&np.isfinite(pd.to_numeric(frame.Ahat,errors='coerce')))
            if not good.all():raise ValueError('accepted Corn train maturity or score differs')
            train_frames[cutoff]=frame;raw_counts[cutoff]=dict(all_rows=n,Corn_rows=len(frame))
            name='corn_train_'+cutoff+'.csv.gz';save_csv(name,frame);caches[cutoff]=artifacts[name]
        forward,n=read_corn_once(large['forward'],False);counts['forward_compact_reads']+=1
        if len(forward)!=protocol['source']['expected_main_Corn_forward_rows']:raise ValueError('full main Corn forward children differ')
        raw_counts['forward']=dict(all_rows=n,main_Corn_rows=len(forward));save_csv('corn_forward.csv.gz',forward);caches['forward']=artifacts['corn_forward.csv.gz']
        for cutoff in CUTOFFS:
            own=forward.loc[forward.cutoff.eq(cutoff)]
            stop='2023-01-01' if cutoff==CUTOFFS[0] else '9999'
            if not own.u_date.ge(cutoff).all() or not own.u_date.lt(stop).all():raise ValueError('old deployment window identity')
        # All3 inherited streams are captured and validated before any new object.
        heads={};scored=[];train_tables={};u_tables={}
        def operation(kind):
            counts['B_fits' if kind=='B_month_means' else 'C_scalar_solves']+=1;counts['actual_fitted_objects']+=1
            if counts['actual_fitted_objects']>4 or counts['B_fits']>2 or counts['C_scalar_solves']>2:raise ValueError('frozen605 fit budget')
            with (output/'fit_operations.jsonl').open('a') as f:f.write(json.dumps(dict(kind=kind,**counts))+'\n')
        for cutoff in CUTOFFS:
            tr,tu=aggregate_reports(train_frames[cutoff].to_dict('records'),sources,cutoff,True,END,calendar)
            ev,eu=aggregate_reports(forward.loc[forward.cutoff.eq(cutoff)].to_dict('records'),sources,cutoff,False,END,calendar)
            h=fit_heads(tr,operation);heads[cutoff]=h;train_tables[cutoff]=tr;u_tables[cutoff]=dict(train=tu,evaluation=eu)
            rows=score_reports(ev,h);scored.extend(rows)
            save('heads_'+cutoff+'.json',h);save('train_reports_'+cutoff+'.json',tr)
            save_csv('train_u_audit_'+cutoff+'.csv.gz',tu);save_csv('evaluation_u_audit_'+cutoff+'.csv.gz',eu)
            print(json.dumps(dict(phase='report_heads_complete',cutoff=cutoff,train_known_reports=sum(finite(r['target']) for r in tr),C_status=h['C']['status'],counts=counts)),flush=True)
        after={k:inherited_stat(b) for k,b in large.items()}
        if before!=after:raise ValueError('old input changed during actual')
        # The source, clock, identity, label maturity and shared fallback checks are
        # structural and above; validate primary calendar rules without new data.
        invariant=all(cycle_metadata(my,END)['forecast_cycle_wholly_in_one_window'] and cycle_metadata(my,END)['actual_marketing_year_finished'] for my in PRIMARY)
        for r in scored:
            if r['score_state'] in ('unseen_month_shared_A','source_shared_A') and (r['pred_B']!=0. or r['pred_C']!=0.):invariant=False
        result=evaluate(scored,heads,invariant,END);coverage=source_coverage(sources,scored)
        for my,v in result['MY_groups'].items():
            if my in coverage:v['source_coverage']=coverage[my]
        save('report_predictions.json',scored);save('source_target_coverage.json',coverage)
        save('evaluation.json',result);save('continuation_gate.json',result['gate']);save('descriptive_MY_bootstrap.json',result['descriptive_MY_bootstrap'])
        save('input_stat_receipt.json',dict(before=before,after=after,old_large_hashes=0))
        summary=dict(schema='stage607_report_residual_summary_v1',counts=counts,raw_target_cache_counts=raw_counts,
            training_support={c:dict(report_rows=len(train_tables[c]),known_target_reports=sum(finite(r['target']) for r in train_tables[c]),MY=sorted({r['MY'] for r in train_tables[c] if finite(r['target'])})) for c in CUTOFFS},
            evaluation_report_states={c:dict(Counter(r['report_state'] for r in scored if r['cutoff']==c)) for c in CUTOFFS},
            eras=result['eras'],primary_MY_equal_mean_Delta_BC=result['primary_MY_equal_mean_Delta_BC'],continuation_gate=result['gate'],
            source_conditional_pairs=160,source_first_print_certified=False,full98_95_objective_unchanged=True,
            financial_metrics='N/A',production_qualified=False,goal_complete=False)
        save('summary.json',summary)
        # Binding small code again does not reopen any inherited financial input.
        for key in ('source','fixture','fixture_receipt'):
            if binding(ready[key]['path'])!=ready[key]:raise ValueError('source changed during actual')
        status='completed'
    except BaseException as exc:
        error=dict(type=type(exc).__name__,message=str(exc));raise
    finally:
        save('terminal.json',dict(schema='stage607_terminal_v1',status=status,exit_code=0 if status=='completed' else 1,
            elapsed_seconds=time.monotonic()-began,counts=counts,error=error,automatic_retry=False))
    manifest=dict(schema='stage607_WASDE_report_residual_v1',status=status,protocol=pb,source_ready=rb,inputs=protocol['source'],
        Corn_target_caches=caches,artifacts=artifacts,counts=counts,goal_complete=False,production_qualified=False,full_policy_reselection=0,new_cash=0)
    write_json(output/'manifest.json',manifest)
    return dict(status=status,output=str(output),counts=counts,gate=result['gate'])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source-ready',required=True);parser.add_argument('--source-ready-sha256',required=True)
    parser.add_argument('--output');parser.add_argument('--actual',action='store_true');parser.add_argument('--check-source',action='store_true');args=parser.parse_args(argv)
    if args.actual:
        if not args.output:parser.error('--actual requires --output')
        print(json.dumps(run_actual(args),ensure_ascii=False),flush=True)
    elif args.check_source:
        ready,_,_,_=check_ready(args.source_ready,args.source_ready_sha256)
        print(json.dumps(dict(status='source_ready_verified',data_reads=0,new_fit=0,new_cash=0,source=ready['source'])))
    else:parser.error('explicit --actual or --check-source required')
if __name__=='__main__':main()
