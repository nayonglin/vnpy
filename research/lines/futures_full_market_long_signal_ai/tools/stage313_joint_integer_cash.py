"""Standalone frozen311 joint integer cash adapter. Import has no data/kernel I/O.

Root-only research identity authorization; no fit, old selector or old CLI.
Accepted157 signals are inherited exactly; no actions, choices or scores are rebuilt.
"""
from __future__ import annotations
import argparse
from collections import Counter
import gzip
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import time
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
PROTOCOL_SHA='f97b23b7732a9ff97272cd793e4ed6c42dc60df6377543d0ab8bcfee527e1259'
CANDIDATE='JOINT_INTEGER_SCORE_BUDGET'
ENGINE_NAME='stage312_joint_integer_allocator.py'
REFS=LINE/'stages/20261020_0110_stage279_frozen_common52_offset_interface_refs.json'
WINDOWS=('primary_2020','cold_2023')
COSTS=('base','stress')
BOUNDS={'primary_2020':('2020-01-01','2026-10-16'),'cold_2023':('2023-01-01','2026-10-16')}
MOTHER_FIELDS=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
INT_SIGNAL_FIELDS=['action_sequence_index','u_index','D_index','label_history_ready20','history_run',
    'lifecycle_index','entry_capacity_qty','u_gross_capacity_qty','potential','source_lifecycle_index','effective_lifecycle_index']
FLOAT_SIGNAL_FIELDS=['N_u','low20_u','u_close','score','voluntary_boundary_index']
TEXT_SIGNAL_FIELDS=['event_id','mother_event_id','product_id','family_id','u_date','reference_epoch','anchor_epoch',
    'arm','policy','cutoff','control_id','effective_boundary_origin','K_state','K_target_date','K_date']


def binding(path):
    p=Path(path).resolve();h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())


def same(a,b):return all(a.get(k)==b.get(k) for k in ('path','bytes','sha256'))


def read_bytes(b):
    raw=Path(b['path']).read_bytes()
    if len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:raise ValueError('bound new/small input differs '+b['path'])
    return raw


def read_json(b):return json.loads(read_bytes(b))


def stat_bound(b):
    if Path(b['path']).stat().st_size!=b['bytes']:raise ValueError('inherited frozen file size changed '+b['path'])


def write_json(path,value):
    with Path(path).open('w') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')


def source_bundle():
    return [binding(TOOLS/n) for n in (ENGINE_NAME,'test_'+ENGINE_NAME,'stage313_joint_integer_cash.py','test_stage313_joint_integer_cash.py')]


def parse_signal_tokens(frame,expected=4365):
    required=INT_SIGNAL_FIELDS+FLOAT_SIGNAL_FIELDS+TEXT_SIGNAL_FIELDS
    if len(frame)!=expected or not set(required).issubset(frame.columns):raise ValueError('complete persisted157 signals required')
    result=frame.copy()
    for name in INT_SIGNAL_FIELDS:
        value=result[name].astype(float)
        if not np.isfinite(value).all() or not np.equal(value,np.floor(value)).all():raise ValueError('integer saved signal field '+name)
        result[name]=value.astype(np.int64)
    for name in FLOAT_SIGNAL_FIELDS:result[name]=result[name].replace('',np.nan).astype(float)
    k=result.voluntary_boundary_index.to_numpy();known=np.isfinite(k)
    if np.isinf(k).any() or not np.equal(k[known],np.floor(k[known])).all():raise ValueError('nullable integer K boundary required')
    if (result.event_id.duplicated().any() or result.duplicated(['family_id','u_date']).any()
            or set(result.arm)!={'VOLUNTARY_RESELECT'} or set(result.control_id)!={'VOLUNTARY_RESELECT'}
            or set(result.policy)!={'NARROW'} or not result.cutoff.isin(['2020-01-01','2023-01-01']).all()
            or not result.label_history_ready20.eq(1).all() or not result.potential.eq(1).all()
            or not result.D_index.eq(result.u_index+1).all()):raise ValueError('unchanged saved signal identity/policy required')
    for name in ('N_u','u_close','score'):
        if not np.isfinite(result[name]).all() or not result[name].gt(0).all():raise ValueError('positive saved signal '+name)
    if not np.isfinite(result.low20_u).all():raise ValueError('finite saved low20 required')
    return result


def validate_signal_identity(signals,mothers,dates):
    parents=mothers.set_index('event_id',verify_integrity=True)
    for row in signals.to_dict('records'):
        if row['mother_event_id'] not in parents.index:raise ValueError('saved signal mother absent')
        parent=parents.loc[row['mother_event_id']]
        if any(str(row[k])!=str(parent[k]) for k in ('product_id','family_id','u_date')) or row['u_index']!=int(parent.u_index):
            raise ValueError('saved signal original mother differs')
        u=row['u_index'];D=row['D_index'];source=row['source_lifecycle_index'];effective=row['effective_lifecycle_index'];k=row['voluntary_boundary_index']
        if (not 0<=u<D<len(dates) or dates[u]!=row['u_date'] or row['anchor_epoch']!=parent.reference_epoch
                or row['lifecycle_index']!=effective):raise ValueError('saved signal calendar/anchor differs')
        if np.isfinite(k):
            if not D<k<len(dates) or dates[int(k)]!=row['K_date'] or effective!=min(source,int(k)):
                raise ValueError('saved signal fixed K differs')
        elif row['K_state']!='after_calendar_pending' or row['K_date'] or effective!=source:
            raise ValueError('saved pending K was repaired or truncated')


def safe(value):
    if isinstance(value,dict):return {str(k):safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,np.ndarray)):return [safe(v) for v in value]
    if isinstance(value,np.generic):return safe(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    return value


def write_audit(path,rows):
    with gzip.open(path,'wt',encoding='utf-8',compresslevel=1) as stream:
        for row in rows:stream.write(json.dumps(safe(row),ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
    return binding(path)


def nominal_gate(points):
    keyed={(p['window'],p['cost']):p for p in points}
    if len(points)!=4 or set(keyed)!={(w,c) for w in WINDOWS for c in COSTS}:raise ValueError('four paired fixed comparisons required')
    finite_positive=lambda x:x is not None and math.isfinite(float(x)) and float(x)>0
    predicates={w:dict(equity_strictly_higher=finite_positive(keyed[(w,'stress')].get('ending_equity_difference')),
        drawdown_strictly_shallower=finite_positive(keyed[(w,'stress')].get('drawdown_percentage_point_difference'))) for w in WINDOWS}
    passed=all(v for p in predicates.values() for v in p.values())
    return dict(nominal_economic_pass=passed,predicates=predicates,base_is_descriptive_only=True,
        production_qualified=False,goal_complete=False,alpha_proved=False,
        interpretation='both stress windows equity/DD strictly improve; score proxy, dependence, numerical and historical adaptive research limits remain')


def pair_years(candidate,control):
    a={r['year']:r for r in candidate};b={r['year']:r for r in control}
    if set(a)!=set(b):raise ValueError('paired yearly source coverage differs')
    rows=[]
    for year in sorted(a):
        x,y=a[year],b[year]
        diff=lambda k:None if x.get(k) is None or y.get(k) is None else x[k]-y[k]
        rows.append(dict(year=year,partial=year=='2026',candidate_return_pct=x['return_pct'],control_return_pct=y['return_pct'],
            candidate_growth_amount=x['cash_growth'],control_growth_amount=y['cash_growth'],
            candidate_max_drawdown_pct=x['max_drawdown_pct'],control_max_drawdown_pct=y['max_drawdown_pct'],
            return_percentage_point_difference=diff('return_pct'),growth_amount_difference=diff('cash_growth'),
            drawdown_percentage_point_difference=diff('max_drawdown_pct')))
    return rows


def account_specs():return [dict(candidate=CANDIDATE,window=w,cost=c,account_id=f'NARROW_{CANDIDATE}_{w}_{c}') for w in WINDOWS for c in COSTS]


def run_four(output,run_account,export_account,*,before=None,finalize=None,metadata=None):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    began=datetime.now(timezone.utc).isoformat();clock=time.monotonic();started=completed=0
    records=[];status='failed';error=None;current=None;meta=dict(metadata or {})
    write_json(out/'actual_started.json',dict(stage=313,started_at=began,**meta))
    def progress(account=None):write_json(out/'cash_progress.json',dict(cash_accounts_started=started,cash_accounts_completed=completed,current_account=account,max_new_candidate_cash=4,new_fit=0,old_control_replays=0))
    progress()
    try:
        if before:before(out)
        for spec in account_specs():
            if started>=4:raise ValueError('fixed four cash budget exhausted')
            started+=1;current=spec;progress(spec['account_id']);book=run_account(spec)
            completed+=1;progress(spec['account_id']);records.append(export_account(spec,book))
        if (started,completed)!=(4,4):raise ValueError('exact four new candidates required')
        if finalize:finalize(out,records)
        status='completed';return records
    except BaseException as exc:
        error=type(exc).__name__+': '+str(exc)
        if hasattr(exc,'allocation_audit'):
            folder=out/(current['account_id'] if current else 'prepare_failure');folder.mkdir(parents=True,exist_ok=True)
            audit=write_audit(folder/'failed_allocation_audit.jsonl.gz',exc.allocation_audit)
            write_json(folder/'failed_allocation_receipt.json',dict(status='failed',account=current,audit=audit,
                batches=len(exc.allocation_audit),retry=False,fallback=False))
        raise
    finally:
        terminal=dict(status=status,error=error,started_at=began,finished_at=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=time.monotonic()-clock,cash_accounts_started=started,cash_accounts_completed=completed,
            max_new_candidate_cash=4,new_fit=0,old_control_replays=0,SQL=0,auto_retry=False,goal_complete=False,production_qualified=False)
        write_json(out/'actual_terminal.json',terminal)
        artifacts=[binding(f) for f in sorted(out.rglob('*')) if f.is_file() and f.name!='manifest.json']
        write_json(out/'manifest.json',dict(schema='stage313_joint_integer_cash_manifest_v1',status=status,candidate=CANDIDATE,
            accounts=records,terminal=binding(out/'actual_terminal.json'),artifacts=artifacts,**meta,
            new_fit=0,new_cash_accounts=completed,cash_accounts_started=started,old_control_replays=0,goal_complete=False,production_qualified=False))


def load_runtime(original_bundle):
    for b in original_bundle:
        if not same(binding(b['path']),b):raise ValueError('accepted small cash source changed '+b['path'])
    def load(name,identity):
        spec=importlib.util.spec_from_file_location(identity,TOOLS/name)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    return load('stage157_voluntary_cash.py','stage313_accepted157'),load(ENGINE_NAME,'stage313_new312')


def authorize(args):
    out=Path(args.output).resolve()
    if out.exists():raise FileExistsError('fresh output required; previous attempt retained')
    if LINE/'outputs/stage313_joint_integer_cash' not in out.parents:raise ValueError('Stage313 output root required')
    pb=binding(args.protocol)
    if args.protocol_sha256!=PROTOCOL_SHA or pb['sha256']!=PROTOCOL_SHA:raise ValueError('exact311 protocol required')
    p=read_json(pb)
    if p.get('schema')!='stage311_joint_integer_budget_protocol_v1' or p.get('candidate')!=CANDIDATE:raise ValueError('311 identity differs')
    ab=binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:raise ValueError('root authorization hash differs')
    auth=read_json(ab);bundle=source_bundle()
    expected=dict(schema='stage313_exact_root_authorization_v1',authorized_by='root',exact_source_authorized=True,
        candidate=CANDIDATE,protocol_sha256=PROTOCOL_SHA,output=str(out),max_new_candidate_cash=4,max_new_fit=0)
    if any(auth.get(k)!=v for k,v in expected.items()):raise ValueError('single exact root research authorization required')
    if sorted(auth.get('source_bundle',[]),key=lambda b:b['path'])!=sorted(bundle,key=lambda b:b['path']):raise ValueError('authorized312/313 source/tests differ')
    if not same(auth.get('interface_refs',{}),p['interface_refs']) or auth['interface_refs']['path']!=str(REFS):
        raise ValueError('exact279 inherited interface refs required')
    return out,p,pb,auth,ab,bundle


def execute(args):
    out,p,pb,auth,ab,bundle=authorize(args);state={}
    metadata=dict(protocol=pb,protocol_sha256=PROTOCOL_SHA,authorization=ab,source_bundle=bundle,
        inputs=dict(signals=p['signals'],mothers=p['mothers'],market_dependencies=p['market_dependencies']),
        research_identity_gate_only=True,fixture=False)

    def prepare(folder):
        refs=read_json(auth['interface_refs']);cash=refs['cash']
        if (cash['source_bundle']!=p['original_source_bundle'] or cash['control_accounts']!=p['control_accounts']
                or cash['market_dependencies']!=p['market_dependencies']):raise ValueError('311 inherited cash references differ')
        v,engine=load_runtime(p['original_source_bundle']);r=v.reuse
        stat_bound(p['mothers'])
        mothers=pd.read_csv(p['mothers']['path'],usecols=MOTHER_FIELDS,dtype=str,keep_default_na=False)
        for col in ('sequence_index','u_index'):mothers[col]=mothers[col].astype(np.int64)
        if (len(mothers)!=399252 or mothers.event_id.duplicated().any() or mothers.product_id.nunique()!=98
                or mothers.family_id.nunique()!=95 or not np.array_equal(mothers.sequence_index,np.arange(399252))):
            raise ValueError('full399252 canonical mother domain required')
        signals=parse_signal_tokens(pd.read_csv(io.BytesIO(read_bytes(p['signals'])),compression='gzip',dtype=str,keep_default_na=False))
        store,receipt,cache_meta=r.cache_source.restore_native_cache(p['market_dependencies']['native_cache_manifest'])
        if receipt['native_source_queries']!=0 or r.ref.NATIVE_QUERIES!=0:raise ValueError('zero SQL required')
        if not same(cache_meta['file'],p['market_dependencies']['native_cache']):raise ValueError('311 inherited native cache differs')
        market,dates=r.CachedMarket(store),store.calendar
        validate_signal_identity(signals,mothers,dates)
        econ_binding=p['market_dependencies']['economic_projection'];stat_bound(econ_binding)
        economics=json.loads(Path(econ_binding['path']).read_text())['instruments']
        if set(economics)!=set(store.series):raise ValueError('frozen cache/economics epochs differ')
        bounds={}
        for w in WINDOWS:
            start,end=(int(np.searchsorted(dates,d)) for d in BOUNDS[w])
            if end>=len(dates) or dates[end]!=BOUNDS[w][1]:raise ValueError('fixed window/source calendar differs')
            bounds[w]=(start,end)
        state.update(v=v,r=r,engine=engine,cash=cash,signals=signals,mothers=mothers,dates=dates,market=market,economics=economics,
            prepared=v.author.organize(signals,mothers,dates),bounds=bounds,receipt=receipt,cache_meta=cache_meta,
            families=sorted(mothers.family_id.unique()),summaries={},reports={},daily={},family_tables=[],allocation={})
        write_json(folder/'source_read_receipt.json',dict(receipt,candidate=CANDIDATE,signal_binding=p['signals'],
            signal_rows=len(signals),signal_streams=1,signal_parser='dtype=str then direct float/int; optional K empty remains NaN',
            full_mother_rows=399252,mother_streams=1,mother_fields=MOTHER_FIELDS,economic_reads=1,native_cache_reads=1,
            original_canonical_from_full_mothers=True,new_fit=0,models_scores_labels_read=0,selectors_called=0,
            raw_action_reads=0,signals_recomputed=0,separate_old_large_prehashes=0,base_and_stress_share_frozen_stress_score=True))
        write_json(folder/'control_references.json',p['control_accounts'])

    def run(spec):
        a,b=state['bounds'][spec['window']]
        return state['engine'].run_cash_account(state['signals'],state['market'],state['dates'],state['economics'],
            spec['cost'],spec['account_id'],a,b,prepared=state['prepared'],policy='NARROW',base_kernel=state['v'].kernel)

    def export(spec,book):
        r=state['r'];name=spec['account_id'];folder=out/name
        ledgers=r.write_ledgers(folder,book);summary,report,fy=r.helpers.cash_report(book,state['families'],r.ref.INITIAL)
        audit=write_audit(folder/'allocation_audit.jsonl.gz',book['allocation_audit'])
        allocation=dict(book['allocation_diagnostics'],audit_rows=len(book['allocation_audit']),
            mode_counts=dict(Counter(row['mode'] for row in book['allocation_audit'])))
        write_json(folder/'allocation_diagnostics.json',safe(allocation));state['allocation'][name]=allocation
        ledgers['allocation_audit']=audit;ledgers['allocation_diagnostics']=binding(folder/'allocation_diagnostics.json')
        tick_lots=0.;unknown_tick_fills=0
        for f in book['fills']:
            tick=state['economics'][f['epoch']].get('tick_size')
            if r.ref.positive(tick):tick_lots+=abs(f['fill_price']-f['reference_price'])/float(tick)*f['qty']
            else:unknown_tick_fills+=1
        summary.update(spec,arm=CANDIDATE,source_helper_arm='VOLUNTARY_RESELECT',role='candidate',allocation_diagnostics=allocation,
            any_historical_stale=report['stale_days']>0,execution_unknown=book['execution_unknown'],
            capacity_unknown_fills=sum(x['capacity_state']=='execution_capacity_unknown' for x in book['capacity_audit']),
            capacity_unknown_roots=len(book['capacity_unknown_roots']),entry_execution_unknown=len(book['entry_execution_unknown']),
            slippage_tick_lots_known=tick_lots,unknown_tick_fills=unknown_tick_fills,slippage_already_in_fill_price=True,
            transaction_count_definition='closed_trades=closed roots; fills=all BUY/SELL fills; total_filled_qty=quantity')
        key=(spec['window'],spec['cost']);state['summaries'][key]=summary;state['reports'][name]=report;state['daily'][key]=pd.DataFrame(book['daily'])
        state['family_tables'].append(r.report_helpers.add_family_costs(fy,book).assign(**spec,arm=CANDIDATE))
        groups,tails=r.extra_reports(book)
        for file,value in [('summary',summary),('diagnostics',report),('largest_wins_losses',tails)]:write_json(folder/(file+'.json'),r.kernel.original.safe(value))
        r.ref.write_table(folder/'sector_variant_attribution.csv.gz',groups,[])
        return dict(spec,directory=str(folder),summary=binding(folder/'summary.json'),ledgers=ledgers)

    def finalize(folder,records):
        r=state['r'];cash=state['cash'];old=read_json(read_json(cash['existing_interface_refs'])['small_identity_bindings']['157'])
        control_reports=read_json(old['diagnostics']);points=[];annual=[];paired_year=[];distributions={};metrics=list(state['summaries'].values());indices={}
        for w,b in cash['market_dependencies']['bootstrap_indices_optional_if_paired_CI_retained'].items():
            stat_bound(b);indices[w]=np.load(b['path'],allow_pickle=False)
        controls={(c['window'],c['cost']):c for c in cash['control_accounts']}
        for spec in account_specs():
            key=(spec['window'],spec['cost']);control=controls[key];baseline=read_json(control['summary']);active=state['summaries'][key]
            cd=pd.read_csv(io.BytesIO(read_bytes(control['daily'])),compression='gzip',float_precision='round_trip')
            stats,dist=r.paired_statistics(state['daily'][key],cd,indices[key[0]])
            points.append(dict(spec,control_account_id=control['account_id'],ending_equity_difference=active['ending_equity']-baseline['ending_equity'],
                **r.helpers.compare_points(active,baseline),**stats))
            distributions[key[0]+'_'+key[1]]=dist
            metrics.append(dict(baseline,account_id=control['account_id'],window=key[0],cost=key[1],role='control_reused',replayed=False))
            ar=state['reports'][spec['account_id']]['annual_slices'];br=control_reports[control['account_id']]['annual_slices']
            paired_year.extend(dict(window=key[0],cost=key[1],**a) for a in pair_years(ar,br))
            for name,role,rows in ((spec['account_id'],'candidate',ar),(control['account_id'],'control_reused',br)):
                annual.extend(dict(account_id=name,role=role,window=key[0],cost=key[1],**a) for a in rows)
        for name,value in [('account_summaries',metrics),('comparisons',points),('annual_slices',annual),('paired_annual',paired_year),
                ('bootstrap_distributions',pd.DataFrame(distributions)),('family_year_including_zero',pd.concat(state['family_tables'],ignore_index=True))]:
            r.ref.write_table(folder/(name+'.csv.gz'),value,[])
        gate=nominal_gate(points)
        gate.update(any_candidate_historical_stale=any(s['any_historical_stale'] for s in state['summaries'].values()),
            any_candidate_execution_unknown=any(s['execution_unknown'] for s in state['summaries'].values()),
            CI_is_paired_daily_log_growth_diagnostic=True,overlapping_action_and_source_days_not_independent=True,
            bootstrap_indices_regenerated=False,mapped_product_scope='all original98 products',score_proxy_is_calibrated_cash_expectation=False,historical_first_seen_PIT_proved=False)
        write_json(folder/'decision.json',gate)
        write_json(folder/'allocation_summary.json',dict(accounts=state['allocation'],
            audit_complete_including_empty_and_untriggered=True,same_state_old_reservations_diagnostic_only=True,
            original_control_replays=0,score_source='same original net_R_stress score in both cost scenarios'))
        if source_bundle()!=bundle or r.ref.NATIVE_QUERIES!=0:raise ValueError('source drift or SQL budget violation')
        if r.cache_source.database_state(state['cache_meta']['database']['path'])!=state['receipt']['database_after']:raise ValueError('native database stat drift')

    return run_four(out,run,export,before=prepare,finalize=finalize,metadata=metadata)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','protocol-sha256','authorization','authorization-sha256','output'):parser.add_argument('--'+name,required=True)
    execute(parser.parse_args())


if __name__=='__main__':main()
