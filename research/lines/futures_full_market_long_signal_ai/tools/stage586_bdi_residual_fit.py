"""Frozen585 BDI projection and <=12 residual solves; only root runs actual."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time
import traceback
import numpy as np
import pandas as pd
import stage586_bdi_core as core
import stage567_pmi_residual_fit as prior

old=prior.old
TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
PROTOCOL_SHA='c7c7313a8ccac4a292e31ba87c2818f12acf47b9322c4ef289fcc9f8a6a2261a'
FILES=['stage586_bdi_core.py','stage586_bdi_residual_fit.py','test_stage586_bdi_residual.py',
       'stage567_pmi_residual_fit.py','stage538_sector_residual_fit.py','stage156_voluntary_choices.py',
       'stage130_contract_choice_fit.py','stage071_settlement_narrow_fit.py']
def source_bundle():return [old.binding(TOOLS/n) for n in FILES]
def raw_json(bound):
    data=Path(bound['path']).read_bytes()
    if len(data)!=bound['bytes'] or hashlib.sha256(data).hexdigest()!=bound['sha256']:raise ValueError('raw binding differs')
    return json.loads(data.decode('utf-8'))

def monthly_diagnostics(report,daily,macro):
    alias=macro.rename(columns={'reference_month':'report_month'})
    report,day,monthly,annual,context=prior.monthly_diagnostics(report,daily,alias)
    day=day.rename(columns={'report_month':'reference_month'})
    context=context.rename(columns={'report_month':'reference_month'})
    day['u_calendar_month']=day.u_date.str[:7]
    monthly['u_calendar_month']=monthly.u_month
    monthly['reference_month']=monthly.u_month.map(lambda m:core.shift_month(m,-1))
    context['u_calendar_month']=context.reference_month.map(lambda m:core.shift_month(m,1))
    means=report['calendar_month_groups'];checks={}
    for scope in ('main','holdout_0','holdout_1'):
        for contrast in ('C_minus_A','C_minus_B'):
            x=means.get(scope,{}).get(contrast,{}).get('equal_calendar_month_mean_increment_R')
            checks[scope+'_'+contrast]=bool(x is not None and np.isfinite(x) and x>0)
    for era in report['main_era_means']:
        if era['contrast']=='C_minus_B':
            x=era['equal_calendar_month_mean_increment_R'];checks[era['era']+'_C_minus_B']=bool(x is not None and np.isfinite(x) and x>0)
    passed=len(checks)==8 and all(checks.values())
    report.update(schema='stage586_bdi_actual_chosen_action_diagnostic_v1',nominal_cash_prerequisite=passed,
        fixed585_gate=checks,all_population_identified=False,full_policy_cash_qualified=False,
        reference_month='previous complete calendar month of u; separate from diagnostic u_month',
        time_slices='original u_date year, never reference_month year',
        q_missing_policy='full u retained, exact A fallback; same-action increment0; different-action unknown remains NaN')
    return report,day,monthly,annual,context

def zero_family_report(linked,parents):
    f=linked.sort_values('selected',ascending=False,kind='stable').drop_duplicates(['scope','arm','family_id','u_index']).copy()
    f['year']=f.u_date.str[:4]
    grouped=f.groupby(['scope','arm','family_id','year']).agg(family_u=('u_index','size'),selected=('selected','sum'),
        known_value_family_u=('diagnostic_value_R','count'),mean_known_value_R=('diagnostic_value_R','mean')).reset_index()
    grids=[];fg={x:old.base130.family_group(x) for x in parents.family_id.unique()}
    for scope in ('main','holdout_0','holdout_1'):
        pp=parents if scope=='main' else parents.loc[parents.family_id.map(fg).eq(int(scope[-1]))]
        index=pd.MultiIndex.from_product([[scope],['A','B','C'],sorted(pp.family_id.unique()),sorted(parents.u_date.str[:4].unique())],names=['scope','arm','family_id','year'])
        grids.append(index.to_frame(index=False))
    result=pd.concat(grids,ignore_index=True).merge(grouped,how='left',on=['scope','arm','family_id','year'],validate='one_to_one')
    for c in ['family_u','selected','known_value_family_u']:result[c]=result[c].fillna(0).astype(int)
    result['unknown_value_family_u']=result.family_u-result.known_value_family_u
    return result

def run(args):
    pb=old.binding(args.protocol)
    if pb['sha256']!=PROTOCOL_SHA:raise ValueError('frozen585 differs')
    protocol=old.small_json(pb)
    if protocol['schema']!='stage585_frozen_bdi_monthly_residual_v1':raise ValueError('wrong585 schema')
    sources=source_bundle();out=Path(args.output).resolve()
    if out.exists() or LINE/'outputs/stage586_bdi_residual_fit' not in out.parents:raise ValueError('fresh586 output required')
    out.mkdir(parents=True)
    if args.check_source:
        ready=dict(schema='stage586_source_ready_v1',source_ready=True,actual_started=False,protocol=pb,source_bundle=sources,
            fixtures='8 targeted synthetic boundaries RED8 then GREEN8; no real data fit/pretrial',
            diagnostics='equal u_calendar_month; reference_month retained separately; eras/annual use u_date year',
            fit=0,cash=0,SQL=0,market_downloads=0)
        old.write_json(out/'source_ready.json',ready);print(json.dumps(ready));return
    if not args.actual or not args.source_ready:raise ValueError('root actual requires exact source-ready')
    ready=json.loads(Path(args.source_ready).read_text())
    if ready['protocol']!=pb or ready['source_bundle']!=sources or not ready['source_ready']:raise ValueError('source-ready differs')
    start=time.monotonic();attempted=completed=0;artifacts={};reads=dict(raw=0,train=0,forward=0,mothers=0,A_choices=0)
    def event(kind,record,arm):
        nonlocal attempted,completed
        if kind=='attempt':attempted+=1
        else:completed+=1
        with (out/'fit_events.jsonl').open('a') as f:
            f.write(json.dumps(dict(event=kind,scope=record['scope'],cutoff=record['cutoff'],arm=arm,attempted=attempted,completed=completed))+'\n');f.flush()
    def save(name,value):artifacts[name]=old.write_json(out/(name+'.json'),value)
    def table(name,frame):artifacts[name]=old.write_frame(out/(name+'.csv.gz'),frame)
    def finish(status,extra):
        terminal=dict(status=status,exit_code=0,attempted=attempted,completed=completed,base_refits=0,cash=0,SQL=0,downloads=0,
            elapsed_seconds=time.monotonic()-start,automatic_retry=False,goal_complete=False,**extra)
        save('actual_terminal',terminal)
        old.write_json(out/'manifest.json',dict(schema='stage586_bdi_residual_fit_v1',status=status,protocol=pb,source_bundle=sources,
            inputs=protocol['inputs'],training_folds=protocol['training_folds'],actual_fit_calls_attempted=attempted,
            actual_fit_calls_completed=completed,base_refits=0,cash_replays=0,native_source_queries=0,downloads=0,
            goal_complete=False,production_qualified=False,increased_betting_qualified=False,**artifacts))
        print(json.dumps(terminal),flush=True);return terminal
    save('actual_started',dict(status='started',started_utc=datetime.now(timezone.utc).isoformat(),protocol=pb,source_bundle=sources,
        source_ready=old.binding(args.source_ready),root_unique_actual=True,max_new_fits=12,cash_budget=0))
    try:
        inp=protocol['inputs'];accepted=old.small_json(inp['accepted538_manifest']);fold_records=old.small_json(inp['fold_records'])
        if accepted['schema']!='stage538_sector_residual_fit_v1' or accepted['status']!='completed':raise ValueError('accepted538 not completed')
        for role in ('calendar','forward_base_compact','mothers_forward','choices_main','choices_holdout'):
            if inp[role]!=accepted[role]:raise ValueError('accepted compact differs '+role)
        for fold in protocol['training_folds']:
            accepted_fold=next(r for r in fold_records if (r['scope'],r['cutoff'])==(fold['scope'],fold['cutoff']))
            if fold['train_compact']!=accepted_fold['train_compact'] or fold['original_training_check']!=accepted_fold['training_check']:raise ValueError('accepted fold differs')
        # Bind small evidence once; their existing price audit is not rerun.
        for role in ('source_audit','source_anchor_check','design_decision'):old.small_json(inp[role])
        receipt=old.small_json(inp['raw_receipt']);data=raw_json(inp['raw_bdi']);reads['raw']+=1
        if receipt['status']!=200 or receipt['sha256']!=inp['raw_bdi']['sha256']:raise ValueError('raw receipt differs')
        rows=data['result']['data']['data']
        if len(rows)!=protocol['source_contract']['raw_rows'] or any(r.get('symbol')!='BDI' for r in rows):raise ValueError('raw BDI scope differs')
        calendar=old.small_json(inp['calendar'])
        if len(calendar)!=5587 or calendar!=sorted(set(calendar)):raise ValueError('whole source calendar differs')
        months,macro,quality=core.project_source(rows,protocol['source_contract'],calendar,protocol['scope']['end']);del rows,data
        table('source_months',months);table('calendar_u_bdi',macro);save('source_quality',quality)
        save('projection_summary',dict(calendar_rows=len(macro),known_u=int(macro.macro_available.sum()),reference_months=len(months),
            known_reference_months=int(months.q_state.eq('known').sum()),endpoint_states=months.endpoint_state.value_counts().to_dict(),
            q_states=months.q_state.value_counts().to_dict(),historical_first_release_certified=False,conditional_reconstructed_clock=True))
        records=[]
        for fold in protocol['training_folds']:
            train=old.read_table_once(fold['train_compact'],prior.TRAIN,['sequence_index','u_index','u_action_eligible','net_R_stress','sample_weight','Ahat']);reads['train']+=1
            if len(train)!=fold['original_training_check']['training_rows']:raise ValueError('cached training row count differs')
            if fold['scope']!='main' and train.family_id.map({f:old.base130.family_group(f) for f in train.family_id.unique()}).eq(int(fold['scope'][-1])).any():raise ValueError('held-family leakage')
            stats,training_months=core.training_statistics(train,macro,fold['cutoff']);stats.update(scope=fold['scope'],cutoff=fold['cutoff'],train_compact=fold['train_compact'])
            folder=out/'folds'/fold['scope']/fold['cutoff'];folder.mkdir(parents=True)
            stats['training_source_months']=old.write_frame(folder/'training_source_months.csv.gz',training_months)
            records.append(stats);del train,training_months
            print(json.dumps(dict(phase='preflight',scope=stats['scope'],cutoff=stats['cutoff'],M=stats['M'],support=stats['support_pass'])),flush=True)
        supported=len(records)==6 and all(r['support_pass'] for r in records)
        save('support_preflight',dict(all_six_supported=supported,minimum_M=60,folds=records))
        if not supported:
            save('source_read_receipt',dict(reads,COMMON=0,actions=0,native=0,old_offsets_consumed=False))
            return finish('stopped_insufficient_support',dict(nominal_cash_prerequisite=False,CI=0))
        heads=core.fit_models(records,event);deltas={};offsets=[]
        for key,head in heads.items():
            scope,cutoff,arm=key
            artifacts['head_'+scope+'_'+cutoff+'_'+arm]=old.write_json(out/'folds'/scope/cutoff/(arm+'_head.json'),head)
            deltas[key]=core.predict_delta(macro,head)
        for fold in protocol['training_folds']:
            scope,cutoff=fold['scope'],fold['cutoff'];mask=macro.u_date.ge(cutoff)&(macro.u_date.lt('2023-01-01') if cutoff=='2020-01-01' else macro.u_date.le(protocol['scope']['end']))
            offset=macro.loc[mask].copy();offset['scope']=scope;offset['cutoff']=cutoff;idx=offset.u_index.to_numpy(int)
            for arm in ('B','C'):offset[arm+'_offset']=deltas[(scope,cutoff,arm)][idx]
            offsets.append(offset)
        table('daily_offsets',pd.concat(offsets,ignore_index=True))
        # One forward read; label columns remain untouched until ALL selection finishes.
        forward=prior.clean_forward(old.read_table_once(inp['forward_base_compact'],prior.FORWARD,['sequence_index','mother_sequence_index','u_index','u_action_eligible','score']));reads['forward']+=1
        if len(forward)!=1933480 or forward.duplicated(['scope','action_id']).any() or not np.isfinite(forward.score).all():raise ValueError('complete forward children differ')
        for f in fold_records:
            if int((forward.scope.eq(f['scope'])&forward.cutoff.eq(f['cutoff'])).sum())!=f['prediction_children']:raise ValueError('own-fold forward population differs')
        parents=old.read_table_once(inp['mothers_forward'],old.select156.IDENTITY,['sequence_index','u_index']);reads['mothers']+=1
        if len(parents)!=161014 or parents.event_id.duplicated().any():raise ValueError('complete mothers differ')
        A=[]
        for role in ('choices_main','choices_holdout'):
            f=old.read_table_once(inp[role],prior.CHOICE,['sequence_index','u_index','proposed_score','chosen_action_sequence_index','score','selected']);reads['A_choices']+=1
            A.append(f.loc[f.arm.eq('A')].copy());del f
        choices=[pd.concat(A,ignore_index=True)];selection=[];score_checks=[];fg={f:old.base130.family_group(f) for f in parents.family_id.unique()}
        for scope in protocol['scope']['scopes']:
            children=forward.loc[forward.scope.eq(scope)].copy();u=children.u_index.to_numpy(int)
            if (u<0).any() or (u>=len(calendar)).any() or not np.array_equal(children.u_date.to_numpy(),macro.u_date.to_numpy()[u]):raise ValueError('forward source-u differs')
            if scope!='main' and not children.family_id.map(fg).eq(int(scope[-1])).all():raise ValueError('held score families differ')
            pp=parents if scope=='main' else parents.loc[parents.family_id.map(fg).eq(int(scope[-1]))];parent_rows=pp.to_dict('records');available=macro.macro_available.to_numpy()[u]==1
            for arm in ('B','C'):
                delta=np.zeros(len(children))
                for cutoff in protocol['scope']['cutoffs']:
                    mask=children.cutoff.eq(cutoff).to_numpy();delta[mask]=deltas[(scope,cutoff,arm)][u[mask]]
                cf=children[old.select156.SCORE_FIELDS].copy();cf['score']=core.apply_delta(children.score.to_numpy(float),delta,available)
                columns=cf.columns.tolist();score_rows=(dict(zip(columns,values)) for values in cf.itertuples(index=False,name=None))
                result=old.select_scope(parent_rows,score_rows,calendar,protocol['scope']['end'],scope,arm);chosen=pd.DataFrame(result['choices']);choices.append(chosen)
                selection.append(dict(scope=scope,arm=arm,summary=result['summary']));score_checks.append(dict(scope=scope,arm=arm,full_rows=len(children),original_nonpositive=int(children.score.le(0).sum()),new_nonpositive=int(cf.score.le(0).sum()),missing_q=int((~available).sum()),bitwise_A_fallback=True))
                print(json.dumps(dict(phase='selection',scope=scope,arm=arm,parents=len(chosen),selected=int(chosen.selected.sum()))),flush=True)
                del cf,result,chosen
            del children
        choices=pd.concat(choices,ignore_index=True)
        for part in (choices.loc[choices.scope.eq('main')],choices.loc[choices.scope.ne('main')]):
            if len(part)!=161014*3 or part.duplicated(['arm','event_id']).any():raise ValueError('full three-arm parents differ')
            for arm in old.ARMS:
                if set(part.loc[part.arm.eq(arm),'event_id'])!=set(parents.event_id):raise ValueError('mother identities shrank')
        for scope,part in choices.groupby('scope',sort=True):
            aa=part.loc[part.arm.eq('A')].set_index('event_id');missing=~macro.macro_available.to_numpy(bool)[aa.u_index.to_numpy(int)]
            for arm in ('B','C'):
                cc=part.loc[part.arm.eq(arm)].set_index('event_id').reindex(aa.index)
                if not aa.loc[missing,'chosen_action_id'].eq(cc.loc[missing,'chosen_action_id']).all() or not aa.loc[missing,'selected'].eq(cc.loc[missing,'selected']).all():raise ValueError('missing q changed A choice')
        # Forward outcomes are first consumed here, after fits and complete selection.
        actions=forward[['action_id',*prior.LABELS]].drop_duplicates('action_id').copy();actions['net_R_stress']=pd.to_numeric(actions.net_R_stress,errors='coerce')
        main_ids=set(forward.loc[forward.scope.eq('main'),'action_id']);held_ids=set(forward.loc[forward.scope.ne('main'),'action_id'])
        if main_ids!=held_ids or len(actions)!=len(main_ids) or len(forward)!=2*len(main_ids):raise ValueError('complete main/held action labels differ')
        report,daily,annual_u,linked=old.diagnostics(choices,actions,protocol['scope']['end'])
        report,day,monthly,annual,context=monthly_diagnostics(report,daily,macro)
        for name,frame in [('choices_main',choices.loc[choices.scope.eq('main')]),('choices_holdout',choices.loc[choices.scope.ne('main')]),('held_daily',day),('calendar_monthly',monthly),('calendar_annual',annual),('held_annual_u_equal',annual_u),('source_reference_month_context',context),('family_year_including_zero',zero_family_report(linked,parents))]:table(name,frame)
        fields=['event_id','family_id','u_index','u_date','scope','arm','chosen_action_id','selected','diagnostic_value_R',*prior.LABELS]
        table('diagnostic_linked',linked[fields]);save('selection_records',selection);save('held_diagnostic',report)
        passed=report['nominal_cash_prerequisite']
        save('continuation_gate',dict(status='nominal_known_support_only' if passed else 'unsupported',nominal_cash_prerequisite=passed,
            checks=report['fixed585_gate'],unconditional_full_policy_supported=False,independent587_review_required=True,cash_authorized=False,goal_complete=False))
        save('descriptive_CI',dict(status='not_run_failed_fixed_gate' if not passed else 'not_authorized_this_protocol',new_resampling=0))
        save('source_read_receipt',dict(reads,COMMON=0,actions=0,train_common_unique=0,native=0,old_sector_PMI_offsets_consumed=False,forward_labels_consumed_after_full_selection=True))
        save('summary',dict(status='completed',actual_fit_calls_attempted=attempted,actual_fit_calls_completed=completed,base_refits=0,cash=0,
            registered_products=98,registered_families=95,full_forward_mothers=161014,full_forward_children=len(forward),nominal_cash_prerequisite=passed,
            macro_known_u=int(macro.macro_available.sum()),reference_month='previous complete calendar month',diagnostic_month='original u_calendar_month',
            source_read_counts=reads,goal_complete=False))
        if attempted!=12 or completed!=12 or sources!=source_bundle():raise ValueError('exact twelve solves/source freeze differs')
        return finish('completed',dict(nominal_cash_prerequisite=passed,CI=0))
    except BaseException as e:
        save('actual_terminal',dict(status='failed',exit_code=1,attempted=attempted,completed=completed,base_refits=0,cash=0,SQL=0,downloads=0,
            source_read_counts=reads,automatic_retry=False,elapsed_seconds=time.monotonic()-start,error_type=type(e).__name__,error=str(e),traceback=traceback.format_exc()))
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','output'):p.add_argument('--'+name,required=True)
    p.add_argument('--source-ready');p.add_argument('--check-source',action='store_true');p.add_argument('--actual',action='store_true')
    a=p.parse_args();run(a)
