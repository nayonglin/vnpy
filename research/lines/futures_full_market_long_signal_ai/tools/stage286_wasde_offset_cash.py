"""Standalone frozen284 candidate cash adapter. Import has no data/kernel I/O.

Root-only research identity authorization; no fit, old selector or old CLI.
All newly selected IDs are admitted, never restricted to the old4365 signals.
"""
from __future__ import annotations
import argparse
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
PROTOCOL_SHA='b604940cf2d43fa504883796a8532a734101a7d2291d7fee225296c384e39193'
CANDIDATE='WASDE_PUBLICATION_MONTH_OFFSET'
REFS=LINE/'stages/20261020_0110_stage279_frozen_common52_offset_interface_refs.json'
WINDOWS=('primary_2020','cold_2023')
COSTS=('base','stress')
BOUNDS={'primary_2020':('2020-01-01','2026-10-16'),'cold_2023':('2023-01-01','2026-10-16')}
MOTHER_FIELDS=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
ACTION_FIELDS=['action_id','event_id','action_sequence_index','mother_sequence_index','mother_event_id',
    'product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible',
    'entry_capacity_qty','N_u','low20_u','u_close']


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


def source_bundle():return [binding(TOOLS/n) for n in ('stage286_wasde_offset_cash.py','test_stage286_wasde_offset_cash.py')]


def prepare_choices(mothers,choices,expected_parents=161014):
    forward=mothers.loc[mothers.u_date.ge('2020-01-01')]
    if len(forward)!=expected_parents or len(choices)!=expected_parents or choices.event_id.duplicated().any():
        raise ValueError('complete ordered forward parent choices required')
    for col in MOTHER_FIELDS:
        a,b=forward[col].reset_index(drop=True),choices[col].reset_index(drop=True)
        equal=(a.astype(float).tolist()==b.astype(float).tolist()) if col in ('sequence_index','u_index') else a.astype(str).tolist()==b.astype(str).tolist()
        if not equal:raise ValueError('original complete parent identity differs '+col)
    if set(choices.scope)!={'main'} or set(choices.policy)!={'NARROW'}:
        raise ValueError('main fixed NARROW choices required')
    if not set(choices.arm).issubset({'VOLUNTARY_RESELECT',CANDIDATE}):raise ValueError('candidate/internal arm differs')
    picked=choices.copy();selected=picked.selected.astype(float)
    if not selected.isin([0,1]).all():raise ValueError('binary selected required')
    picked['selected']=selected.astype(int)
    ids=set(picked.loc[picked.selected.eq(1),'chosen_action_id'])
    if not ids or '' in ids or len(ids)!=int(picked.selected.sum()):raise ValueError('unique nonempty new selected action IDs required')
    picked['arm']='VOLUNTARY_RESELECT' # helper schema alias only; never overwrite external identity
    return picked,ids


def collect_selected_actions(chunks,ids):
    frames=[];rows=0
    for chunk in chunks:
        rows+=len(chunk)
        if not set(ACTION_FIELDS).issubset(chunk.columns):raise ValueError('all16 causal action fields required')
        part=chunk.loc[chunk.action_id.isin(ids),ACTION_FIELDS].copy()
        if len(part):frames.append(part)
    result=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame(columns=ACTION_FIELDS)
    if result.action_id.duplicated().any() or set(result.action_id)!=set(ids):raise ValueError('each new selected action required exactly once')
    result.attrs['source_rows_seen']=rows
    return result


def nominal_gate(points):
    keyed={(p['window'],p['cost']):p for p in points}
    if len(points)!=4 or set(keyed)!={(w,c) for w in WINDOWS for c in COSTS}:raise ValueError('four paired fixed comparisons required')
    finite_positive=lambda x:x is not None and math.isfinite(float(x)) and float(x)>0
    predicates={w:dict(equity_strictly_higher=finite_positive(keyed[(w,'stress')].get('ending_equity_difference')),
        drawdown_strictly_shallower=finite_positive(keyed[(w,'stress')].get('drawdown_percentage_point_difference'))) for w in WINDOWS}
    passed=all(v for p in predicates.values() for v in p.values())
    return dict(nominal_economic_pass=passed,predicates=predicates,base_is_descriptive_only=True,
        production_qualified=False,goal_complete=False,alpha_proved=False,held_supported=False,
        interpretation='four fixed stress comparisons only; CI, missing archive coverage and single corn limit inference')


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
    records=[];status='failed';error=None;meta=dict(metadata or {})
    write_json(out/'actual_started.json',dict(stage=286,started_at=began,**meta))
    def progress(account=None):write_json(out/'cash_progress.json',dict(cash_accounts_started=started,cash_accounts_completed=completed,current_account=account,max_new_candidate_cash=4,new_fit=0,old_control_replays=0))
    progress()
    try:
        if before:before(out)
        for spec in account_specs():
            if started>=4:raise ValueError('fixed four cash budget exhausted')
            started+=1;progress(spec['account_id']);book=run_account(spec)
            completed+=1;progress(spec['account_id']);records.append(export_account(spec,book))
        if (started,completed)!=(4,4):raise ValueError('exact four new candidates required')
        if finalize:finalize(out,records)
        status='completed';return records
    except BaseException as exc:error=type(exc).__name__+': '+str(exc);raise
    finally:
        terminal=dict(status=status,error=error,started_at=began,finished_at=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=time.monotonic()-clock,cash_accounts_started=started,cash_accounts_completed=completed,
            max_new_candidate_cash=4,new_fit=0,old_control_replays=0,SQL=0,auto_retry=False,goal_complete=False,production_qualified=False)
        write_json(out/'actual_terminal.json',terminal)
        artifacts=[binding(f) for f in sorted(out.rglob('*')) if f.is_file() and f.name!='manifest.json']
        write_json(out/'manifest.json',dict(schema='stage286_wasde_offset_cash_manifest_v1',status=status,candidate=CANDIDATE,
            accounts=records,terminal=binding(out/'actual_terminal.json'),artifacts=artifacts,**meta,
            new_fit=0,new_cash_accounts=completed,cash_accounts_started=started,old_control_replays=0,goal_complete=False,production_qualified=False))


def load_runtime(cash_refs):
    for b in cash_refs['source_bundle']:
        if not same(binding(b['path']),b):raise ValueError('accepted small cash source changed '+b['path'])
    spec=importlib.util.spec_from_file_location('stage286_accepted157',TOOLS/'stage157_voluntary_cash.py')
    v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);return v


def authorize(args):
    out=Path(args.output).resolve()
    if out.exists():raise FileExistsError('fresh output required; previous attempt retained')
    if LINE/'outputs/stage286_wasde_offset_cash' not in out.parents:raise ValueError('Stage286 output root required')
    pb=binding(args.protocol)
    if args.protocol_sha256!=PROTOCOL_SHA or pb['sha256']!=PROTOCOL_SHA:raise ValueError('exact284 protocol required')
    p=read_json(pb)
    if p.get('schema')!='stage284_wasde_frozen_common52_publication_month_offset_protocol_v1' or p.get('candidate')!=CANDIDATE:raise ValueError('284 identity differs')
    ab=binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:raise ValueError('root authorization hash differs')
    auth=read_json(ab);bundle=source_bundle()
    expected=dict(schema='stage286_exact_root_authorization_v1',authorized_by='root',protocol_sha256=PROTOCOL_SHA,
        output=str(out),max_new_candidate_cash=4,max_new_fit=0)
    if any(auth.get(k)!=v for k,v in expected.items()):raise ValueError('single exact root research authorization required')
    if sorted(auth.get('source_bundle',[]),key=lambda b:b['path'])!=sorted(bundle,key=lambda b:b['path']):raise ValueError('authorized source/fixture differs')
    clar=read_json(auth['technical_clarifications'])
    if clar.get('protocol_sha256')!=PROTOCOL_SHA:raise ValueError('284 technical clarification binding differs')
    if auth['interface_refs']['path']!=str(REFS):raise ValueError('exact279 inherited interface refs required')
    return out,p,pb,auth,ab,bundle


def execute(args):
    out,p,pb,auth,ab,bundle=authorize(args);state={}
    metadata=dict(protocol=pb,technical_clarifications=auth['technical_clarifications'],authorization=ab,
        fit_select_manifest=auth['fit_select_manifest'],source_bundle=bundle,research_identity_gate_only=True,fixture=False)

    def prepare(folder):
        m=read_json(auth['fit_select_manifest'])
        if (m.get('schema')!='stage285_wasde_offset_fit_select_manifest_v1' or m.get('status')!='completed'
                or m.get('protocol_sha256')!=PROTOCOL_SHA or m.get('candidate')!=CANDIDATE):raise ValueError('completed285 exact candidate required')
        refs=read_json(auth['interface_refs']);cash=refs['cash'];fixed=read_json(cash['existing_interface_refs'])['input_bindings_inherited_from_accepted157']
        for role in ('mothers','actions'):
            if not same(m['inputs'][role],fixed[role]):raise ValueError('285 frozen dataset binding differs '+role)
        v=load_runtime(cash);r=v.reuse
        stat_bound(m['inputs']['mothers'])
        mothers=pd.read_csv(m['inputs']['mothers']['path'],usecols=MOTHER_FIELDS,dtype=str,keep_default_na=False)
        for col in ('sequence_index','u_index'):mothers[col]=mothers[col].astype(int)
        if len(mothers)!=399252 or mothers.event_id.duplicated().any() or mothers.product_id.nunique()!=98 or mothers.family_id.nunique()!=95:raise ValueError('full399252 canonical mother domain required')
        choices=pd.read_csv(io.BytesIO(read_bytes(m['artifacts']['choices_main'])),compression='gzip',dtype=str,keep_default_na=False)
        picked,ids=prepare_choices(mothers,choices)
        for col in ('sequence_index','u_index','chosen_action_sequence_index'):picked[col]=picked[col].astype(int)
        picked['score']=picked.score.replace('',np.nan).astype(float)
        stat_bound(m['inputs']['actions'])
        chunks=pd.read_csv(m['inputs']['actions']['path'],compression='gzip',usecols=ACTION_FIELDS,dtype=str,
            keep_default_na=False,chunksize=100000,float_precision='round_trip')
        actions=collect_selected_actions(chunks,ids)
        source_rows=actions.attrs['source_rows_seen']
        if source_rows!=1552456:raise ValueError('complete once-only action stream row count differs')
        r.numeric(actions,['action_sequence_index','mother_sequence_index','u_index','u_action_eligible','entry_capacity_qty','N_u','low20_u','u_close'])
        boundaries=read_json(m['artifacts']['boundaries'])
        if boundaries.get('schema')!='stage156_voluntary_K_only_v1' or boundaries.get('account_deadline_certified') is not False:raise ValueError('unchanged noncertified voluntary K required')
        store,receipt,cache_meta=r.cache_source.restore_native_cache(cash['market_dependencies']['native_cache_manifest'])
        if receipt['native_source_queries']!=0 or r.ref.NATIVE_QUERIES!=0:raise ValueError('zero SQL required')
        market,dates=r.CachedMarket(store),store.calendar
        econ_binding=cash['market_dependencies']['economic_projection'];stat_bound(econ_binding)
        economics=json.loads(Path(econ_binding['path']).read_text())['instruments']
        if set(economics)!=set(store.series):raise ValueError('frozen cache/economics epochs differ')
        signals=v.make_voluntary_signals(actions,mothers,picked,boundaries['epochs'],market,dates,economics)
        if len(signals)!=len(ids):raise ValueError('new selected action admission differs')
        bounds={}
        for w in WINDOWS:
            start,end=(int(np.searchsorted(dates,d)) for d in BOUNDS[w])
            if end>=len(dates) or dates[end]!=BOUNDS[w][1]:raise ValueError('fixed window/source calendar differs')
            bounds[w]=(start,end)
        state.update(v=v,r=r,cash=cash,signals=signals,mothers=mothers,dates=dates,market=market,economics=economics,
            prepared=v.author.organize(signals,mothers,dates),bounds=bounds,receipt=receipt,cache_meta=cache_meta,
            families=sorted(mothers.family_id.unique()),summaries={},reports={},daily={},family_tables=[])
        r.ref.write_table(folder/'signals_candidate.csv.gz',signals,[])
        trace=['event_id','mother_event_id','reference_epoch','anchor_epoch','u_date','u_index','D_index',
            'source_lifecycle_index','voluntary_boundary_index','effective_lifecycle_index','effective_boundary_origin','K_target_date','K_date','K_state']
        r.ref.write_table(folder/'boundary_lineage.csv.gz',signals[trace],[])
        write_json(folder/'source_read_receipt.json',dict(receipt,candidate=CANDIDATE,new_selected_actions=len(ids),
            main_parent_rows=161014,full_mother_rows=399252,action_source_rows=source_rows,action_streams=1,action_fields=ACTION_FIELDS,
            old4365_admission_gate_used=False,choices_binding=m['artifacts']['choices_main'],actions_binding=m['inputs']['actions'],
            original_canonical_from_full_mothers=True,new_fit=0,models_scores_labels_read=0,selectors_called=0,separate_old_large_prehashes=0))
        write_json(folder/'control_references.json',cash['control_accounts'])

    def run(spec):
        a,b=state['bounds'][spec['window']]
        return state['v'].kernel.run_cash_account(state['signals'],state['market'],state['dates'],state['economics'],
            spec['cost'],spec['account_id'],a,b,prepared=state['prepared'])

    def export(spec,book):
        r=state['r'];name=spec['account_id'];folder=out/name
        ledgers=r.write_ledgers(folder,book);summary,report,fy=r.helpers.cash_report(book,state['families'],r.ref.INITIAL)
        tick_lots=0.;unknown_tick_fills=0
        for f in book['fills']:
            tick=state['economics'][f['epoch']].get('tick_size')
            if r.ref.positive(tick):tick_lots+=abs(f['fill_price']-f['reference_price'])/float(tick)*f['qty']
            else:unknown_tick_fills+=1
        summary.update(spec,arm=CANDIDATE,source_helper_arm='VOLUNTARY_RESELECT',role='candidate',
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
            CI_is_paired_daily_log_growth_diagnostic=True,independent_USDA_observations_not_daily_rows=True,
            bootstrap_indices_regenerated=False,single_mapped_product='DCE.C',archive_first_seen_PIT_proved=False)
        write_json(folder/'decision.json',gate)
        if source_bundle()!=bundle or r.ref.NATIVE_QUERIES!=0:raise ValueError('source drift or SQL budget violation')
        if r.cache_source.database_state(state['cache_meta']['database']['path'])!=state['receipt']['database_after']:raise ValueError('native database stat drift')

    return run_four(out,run,export,before=prepare,finalize=finalize,metadata=metadata)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','protocol-sha256','authorization','authorization-sha256','output'):parser.add_argument('--'+name,required=True)
    execute(parser.parse_args())


if __name__=='__main__':main()
