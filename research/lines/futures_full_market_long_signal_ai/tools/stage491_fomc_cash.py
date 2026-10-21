"""Stage491: two frozen FOMC residual policies, eight cache-only cash books.

No actual data, native cache, legacy module or cash is read/run on import. A is
accepted157's own four books, never its old131B control. Only new489 derived
causal projections enter unchanged157/131 execution; original129 is not read.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import pickle
import time
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
TEST=TOOLS/'test_stage491_fomc_cash.py'
PROTOCOL_SHA='cf55afebcbf3a51139fc18a2b86522cb8c96f477c56f1798b505801375998aac'
ARMS=('B_PRE_LIQUIDITY','C_PRE_LIQUIDITY_FOMC')
CONTRASTS=('B_minus_A','C_minus_A','C_minus_B')
WINDOWS=('primary_2020','cold_2023')
COSTS=('base','stress')
BOUNDS={'primary_2020':('2020-01-01','2026-10-16'),'cold_2023':('2023-01-01','2026-10-16')}
MOTHER_FIELDS=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
ACTION_FIELDS=['action_id','event_id','action_sequence_index','mother_sequence_index','mother_event_id',
    'product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible',
    'entry_capacity_qty','N_u','low20_u','u_close']


def binding(path):
    p=Path(path).resolve();raw=p.read_bytes()
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def same(a,b):return all(a.get(k)==b.get(k) for k in ('path','bytes','sha256'))


def read_bytes(b):
    raw=Path(b['path']).read_bytes()
    if len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:
        raise ValueError('bound input differs '+b['path'])
    return raw


def read_json(b):return json.loads(read_bytes(b))


def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.tmp')
    with tmp.open('w') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    tmp.replace(path)


def read_table(b):
    return pd.read_csv(io.BytesIO(read_bytes(b)),compression='gzip' if b['path'].endswith('.gz') else None,
        dtype=str,keep_default_na=False,float_precision='round_trip')


def numeric(frame,columns):
    for col in columns:
        if col in frame:frame[col]=pd.to_numeric(frame[col].replace('',np.nan),errors='raise')
    return frame


def source_bundle():return [binding(Path(__file__)),binding(TEST)]


def prepare_choices(mothers,choices,arm,expected_parents=161014):
    if arm not in ARMS:raise ValueError('frozen B/C arm required')
    if len(mothers)!=expected_parents or len(choices)!=expected_parents or choices.event_id.duplicated().any():
        raise ValueError('complete ordered forward choices required')
    if list(mothers.columns)!=MOTHER_FIELDS:raise ValueError('exact seven mother identity columns required')
    for col in MOTHER_FIELDS:
        a,b=mothers[col].reset_index(drop=True),choices[col].reset_index(drop=True)
        equal=(pd.to_numeric(a).tolist()==pd.to_numeric(b).tolist()) if col in ('sequence_index','u_index') else a.astype(str).tolist()==b.astype(str).tolist()
        if not equal:raise ValueError('forward mother identity differs '+col)
    if set(choices.scope)!={'main'} or set(choices.policy)!={'NARROW'} or set(choices.arm)!={'VOLUNTARY_RESELECT'}:
        raise ValueError('main fixed NARROW/VOLUNTARY_RESELECT helper schema required')
    if 'candidate' not in choices or set(choices.candidate)!={arm}:raise ValueError('external candidate identity differs')
    expected=np.where(choices.u_date.lt('2023-01-01'),'2020-01-01','2023-01-01')
    if choices.cutoff.tolist()!=expected.tolist():raise ValueError('original deployment cutoff differs')
    picked=choices.copy();numeric(picked,['sequence_index','u_index','selected','chosen_action_sequence_index','score'])
    if not picked.selected.isin([0,1]).all():raise ValueError('binary selection required')
    picked['selected']=picked.selected.astype(int)
    ids=set(picked.loc[picked.selected.eq(1),'chosen_action_id'])
    if '' in ids or len(ids)!=int(picked.selected.sum()):raise ValueError('unique selected child identities required')
    if not np.isfinite(picked.loc[picked.selected.eq(1),'score']).all():raise ValueError('finite selected scores required')
    return picked,ids


def collect_action_union(actions,ids,expected_rows=966740):
    if list(actions.columns)!=ACTION_FIELDS:raise ValueError('exact16 causal fields required; no future Y')
    if len(actions)!=expected_rows or actions.action_id.duplicated().any():raise ValueError('complete unique forward causal actions required')
    part=actions.loc[actions.action_id.isin(ids)].copy()
    if len(part)!=len(ids) or set(part.action_id)!=set(ids):raise ValueError('each selected union action required exactly once')
    receipt=dict(source_rows=len(actions),derived_action_reads=1,selected_union_actions=len(part),
        ineligible_rows_retained_in_source=int(pd.to_numeric(actions.u_action_eligible).eq(0).sum()),
        source_fields=ACTION_FIELDS,original129_reads=0,future_outcome_columns_read=0)
    numeric(part,['action_sequence_index','mother_sequence_index','u_index','u_action_eligible','entry_capacity_qty','N_u','low20_u','u_close'])
    return part,receipt


def fixed_gate(points,held,*,wealth_positive,any_stale=False,execution_unknown=False):
    keyed={(x['window'],x['cost']):x for x in points}
    if len(points)!=4 or set(keyed)!={(w,c) for w in WINDOWS for c in COSTS}:raise ValueError('four fixed contrasts required')
    finite=lambda x:x is not None and math.isfinite(float(x));checks={}
    for key,p in keyed.items():
        strict=key==('primary_2020','stress');ret=p.get('return_percentage_point_difference');dd=p.get('drawdown_percentage_point_difference')
        checks['_'.join(key)]=dict(positive_return=finite(p.get('active_total_return_pct')) and p['active_total_return_pct']>0,
            return_improvement=finite(ret) and (ret>0 if strict else ret>=0),
            drawdown_improvement=finite(dd) and (dd>0 if strict else dd>=0))
    ci=finite(keyed[('primary_2020','stress')].get('ci95_low')) and keyed[('primary_2020','stress')]['ci95_low']>0
    nominal=bool(all(all(x.values()) for x in checks.values()) and ci and wealth_positive)
    groups=held.get('groups',{})
    if set(groups)!={'holdout_0','holdout_1'}:raise ValueError('both held groups required')
    held_known={g:finite(x.get('known_u_equal_mean_increment_R')) and x['known_u_equal_mean_increment_R']>=0 for g,x in groups.items()}
    unknowns={g:x.get('unknown_differential_selected_events') for g,x in groups.items()}
    if any(isinstance(n,bool) or not isinstance(n,(int,np.integer)) or n<0 for n in unknowns.values()):raise ValueError('nonnegative explicit held unknown counts required')
    held_unknown=any(n>0 for n in unknowns.values());financial_unknown=bool(any_stale or execution_unknown)
    all_nominal=bool(nominal and all(held_known.values()))
    status=('unsupported' if not all_nominal else 'unknown_historical_stale' if any_stale else
        'unknown_execution_capacity_or_entry' if execution_unknown else 'unknown_differential_held_outcome' if held_unknown else 'nominal_policy_pass_unqualified')
    return dict(status=status,cash_nominal_pass=nominal,held_known_nominal_pass=all(held_known.values()),
        nominal_pass=bool(all_nominal and not financial_unknown and not held_unknown),predicates=checks,
        primary_daily_log_CI_lower_positive=bool(ci),actual_wealth_positive=bool(wealth_positive),
        held_known_mean_nonnegative=held_known,held_unknown_differential_selected_events=unknowns,
        held_signal_unknown=held_unknown,financial_unknown=financial_unknown,any_historical_stale=bool(any_stale),execution_unknown=bool(execution_unknown))


def dual_gate(points,held,*,wealth_positive,any_stale=False,execution_unknown=False):
    if set(points)!=set(CONTRASTS) or set(held)!=set(CONTRASTS):raise ValueError('all three paired contrast disclosures required')
    gates={k:fixed_gate(points[k],held[k],wealth_positive=wealth_positive,any_stale=any_stale,execution_unknown=execution_unknown) for k in CONTRASTS}
    required=('C_minus_B','C_minus_A');passed=all(gates[k]['nominal_pass'] for k in required)
    return dict(schema='stage491_fomc_dual_gate_v1',status='nominal_policy_pass_unqualified' if passed else 'unsupported_or_unknown',
        nominal_pass=passed,required_contrasts=list(required),B_minus_A_disclosure_only=True,contrasts=gates,
        alpha_proved=False,causal_identification=False,historical_first_seen_PIT_proved=False,
        new_thresholds_or_seed=False,bootstrap_indices_regenerated=False,full_market_mechanism_proved=False,
        increased_betting_qualified=False,production_qualified=False,goal_complete=False,independent_actual_review_required=True)


def account_specs():
    return [dict(arm=a,candidate=a,window=w,cost=c,account_id=f'NARROW_{a}_{w}_{c}') for a in ARMS for w in WINDOWS for c in COSTS]


def run_eight(output,run_account,export_account,*,before=None,finalize=None,metadata=None):
    """Fresh once-only actual; completed raw book checkpoint precedes reporting.

    Any failure preserves counts/checkpoints. It never retries kernels or replaces
    a failed output; a report-only recovery would require a separate root scope.
    """
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    began=datetime.now(timezone.utc).isoformat();clock=time.monotonic();started=completed=0
    books=[];records=[];status='failed';error=None;meta=dict(metadata or {})
    write_json(out/'actual_started.json',dict(stage=491,started_at=began,metadata=meta))
    def progress(phase,account=None):write_json(out/'cash_progress.json',dict(phase=phase,current_account=account,cash_accounts_started=started,
        cash_accounts_completed=completed,max_new_candidate_cash=8,new_fit=0,old_control_replays=0))
    progress('preparing')
    try:
        if before:before(out)
        for spec in account_specs():
            if started>=8:raise ValueError('eight cash budget exhausted')
            started+=1;progress('kernel_running',spec['account_id']);book=run_account(spec)
            path=out/'checkpoints'/(spec['account_id']+'.pickle.gz');path.parent.mkdir(parents=True,exist_ok=True)
            tmp=path.with_name(path.name+'.tmp');tmp.write_bytes(gzip.compress(pickle.dumps(book,protocol=5),mtime=0));tmp.replace(path)
            completed+=1;books.append(dict(spec=spec,book=binding(path)))
            write_json(out/'book_checkpoints.json',dict(schema='stage491_completed_raw_books_v1',cash_accounts_started=started,
                cash_accounts_completed=completed,books=books,metadata=meta));progress('book_checkpoint_complete',spec['account_id']);del book
        if (started,completed)!=(8,8):raise ValueError('exact eight complete books required')
        for item in books:
            spec=item['spec'];progress('reporting',spec['account_id']);book=pickle.loads(gzip.decompress(read_bytes(item['book'])))
            records.append(export_account(spec,book));write_json(out/'report_checkpoints.json',dict(accounts=records,raw_books_replayed=False));del book
        if finalize:finalize(out,records)
        status='completed';progress('completed');return records
    except BaseException as exc:error=type(exc).__name__+': '+str(exc);raise
    finally:
        terminal=dict(status=status,error=error,exit_code=0 if status=='completed' else 1,started_at=began,
            finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,
            cash_accounts_started=started,cash_accounts_completed=completed,new_cash_accounts=completed,new_fit=0,
            max_new_candidate_cash=8,native_SQL=0,old_control_replays=0,auto_retry=False,goal_complete=False,production_qualified=False)
        write_json(out/'actual_terminal.json',terminal)
        artifacts={str(f.relative_to(out)):binding(f) for f in sorted(out.rglob('*')) if f.is_file() and f.name!='manifest.json' and not f.name.endswith('.tmp')}
        write_json(out/'manifest.json',dict(schema='stage491_fomc_cash_manifest_v1',status=status,metadata=meta,
            arms=list(ARMS),accounts=records,terminal=binding(out/'actual_terminal.json'),artifacts=artifacts,
            new_fit=0,new_cash_accounts=completed,cash_accounts_started=started,old_control_replays=0,native_SQL=0,goal_complete=False))


def decode_calendar(cal):
    return ([f'{int(v):08d}'[:4]+'-'+f'{int(v):08d}'[4:6]+'-'+f'{int(v):08d}'[6:] for v in cal]
            if cal.dtype.kind in 'iu' else cal.astype('datetime64[D]').astype(str).tolist())


def control_ledger_binding(control,role):
    item=control['ledgers_relative_to_directory'][role]
    return dict(path=str(Path(control['directory'])/item['file']),bytes=item['bytes'],sha256=item['sha256'])


def pair_years(candidate,control):
    a={str(r['year']):r for r in candidate};b={str(r['year']):r for r in control}
    if set(a)!=set(b):raise ValueError('paired annual calendar coverage differs')
    rows=[]
    for year in sorted(a):
        x,y=a[year],b[year];diff=lambda k:None if x.get(k) is None or y.get(k) is None else x[k]-y[k]
        rows.append(dict(year=year,partial=year=='2026',candidate_return_pct=x['return_pct'],control_return_pct=y['return_pct'],
            candidate_growth_amount=x['cash_growth'],control_growth_amount=y['cash_growth'],
            candidate_max_drawdown_pct=x['max_drawdown_pct'],control_max_drawdown_pct=y['max_drawdown_pct'],
            return_percentage_point_difference=diff('return_pct'),growth_amount_difference=diff('cash_growth'),
            drawdown_percentage_point_difference=diff('max_drawdown_pct')))
    return rows


def same_book_through_2025(daily,initial=1000000.):
    part=daily.loc[daily.date.astype(str).le('2025-12-31')].copy()
    if not len(part):raise ValueError('same book has no observations through2025')
    equity=pd.to_numeric(part.equity,errors='raise').to_numpy(dtype=float)
    if not np.isfinite(equity).all():raise ValueError('finite actual equity required')
    peak=np.maximum.accumulate(np.r_[float(initial),equity])[1:]
    dd=equity/peak-1. if (peak>0).all() else np.full(len(equity),np.nan)
    return dict(ending_date=str(part.date.iloc[-1]),source_days=len(part),ending_equity=float(equity[-1]),
        cash_growth=float(equity[-1]-initial),total_return_pct=float((equity[-1]/initial-1.)*100),
        max_drawdown_pct=float(dd.min()*100) if np.isfinite(dd).all() else None,
        new_account=False,capital_reset=False,year_end_liquidation=False,disclosure_only=True)


def load_runtime(protocol,old):
    b=protocol['input_bindings']['original157_source']
    if not same(binding(b['path']),b):raise ValueError('accepted157 source changed')
    spec=importlib.util.spec_from_file_location('stage491_accepted157',TOOLS/'stage157_voluntary_cash.py')
    v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
    if sorted(v.source_bundle(),key=lambda b:b['path'])!=sorted(old['source_bundle'],key=lambda b:b['path']):raise ValueError('accepted157 execution dependencies changed')
    r=v.reuse
    if (r.ref.INITIAL,r.ref.SINGLE_RISK,r.ref.TOTAL_RISK,r.ref.MARGIN_CAP,r.ref.MARGIN_BUFFER)!=(1000000,.0025,.02,.25,1.1):raise ValueError('accepted execution risk constants changed')
    return v


def validate(args):
    out=Path(args.output).resolve()
    if LINE/'outputs/stage491_fomc_cash' not in out.parents:raise ValueError('Stage491 fresh output root required')
    if out.exists():raise FileExistsError('fresh output required; old attempts retained')
    pb=binding(args.protocol)
    if pb['sha256']!=args.protocol_sha256 or pb['sha256']!=PROTOCOL_SHA:raise ValueError('frozen487 SHA differs')
    p=read_json(pb)
    if p.get('schema')!='stage487_fomc_residual_protocol_v1' or p.get('line_id')!=LINE.name:raise ValueError('487 experiment identity differs')
    hb=binding(args.handoff)
    if hb['sha256']!=args.handoff_sha256:raise ValueError('489 handoff SHA differs')
    h=read_json(hb)
    if h.get('schema')!='stage489_fomc_residual_cash_handoff_v1' or h.get('protocol_sha256')!=pb['sha256'] or not same(h['protocol_binding'],pb):raise ValueError('489 handoff protocol closure differs')
    ab=binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:raise ValueError('exact491 root authorization SHA differs')
    a=read_json(ab);expected=dict(schema='stage491_exact_root_authorization_v1',authorized_by='root',stage='cash',
        protocol_sha256=pb['sha256'],output=str(out),max_new_cash=8,max_new_fit=0,actual_run_limit=1)
    if any(a.get(k)!=v for k,v in expected.items()) or not same(a['handoff_binding'],hb):raise ValueError('exact root once-only cash authorization required')
    if sorted(a.get('source_bundle',[]),key=lambda b:b['path'])!=sorted(source_bundle(),key=lambda b:b['path']):raise ValueError('authorized491 source/test bytes differ')
    c=p['cash_contract_inherited_exact']
    constants=tuple(c[k] for k in ('initial_capital','single_family_risk','total_risk','buffered_margin_cap','margin_buffer','initial_stop_N','participation_rate'))
    if constants!=(1000000,.0025,.02,.25,1.1,.25,.01) or c['new_accounts_max']!=8 or c['new_SQL_or_native_downloads']!=0:raise ValueError('frozen eight-account execution constants differ')
    if c['windows']!={k:list(v) for k,v in BOUNDS.items()}:raise ValueError('fixed 2020/2023 windows differ')
    if (c['CI']['block_length'],c['CI']['repetitions'],c['CI']['reuse_exact_indices_no_regeneration'])!=(252,2000,True):raise ValueError('exact070 indices required')
    return out,p,pb,h,hb,a,ab


def execute(args):
    out,p,pb,h,hb,auth,ab=validate(args);bundle=source_bundle();state={}
    old=read_json(p['control']['cash_manifest']);c=p['cash_contract_inherited_exact'];deps=c['market_dependencies_inherited']
    metadata=dict(protocol=pb,handoff=hb,authorization=ab,fit_manifest=h['fit_manifest_binding'],source_bundle=bundle,fixture=False)
    def prepare(folder):
        model=read_json(h['fit_manifest_binding'])
        if model.get('status')!='completed' or model.get('protocol_sha256')!=pb['sha256']:raise ValueError('completed frozen489 model required')
        # Every handoff artifact must be explicitly recorded by the completed fit manifest.
        manifest_bindings=[]
        def collect(x):
            if isinstance(x,dict):
                if set(('path','bytes','sha256')).issubset(x):manifest_bindings.append(x)
                else:
                    for z in x.values():collect(z)
            elif isinstance(x,list):
                for z in x:collect(z)
        collect(model.get('artifacts',{}))
        hb_to_check=[h[k] for k in ('causal_actions_projection_binding','forward_mothers_projection_binding','boundaries_binding','calendar_binding','held_gate_binding')]
        if set(h['arms'])!=set(ARMS):raise ValueError('both frozen model arms required')
        for a in ARMS:hb_to_check.extend(h['arms'][a][k] for k in ('choices_main_binding','held_diagnostic_binding'))
        if any(not any(same(b,x) for x in manifest_bindings) for b in hb_to_check):raise ValueError('489 handoff artifact not bound by model manifest')
        v=load_runtime(p,old);r=v.reuse
        mothers=read_table(h['forward_mothers_projection_binding'])
        if list(mothers.columns)!=MOTHER_FIELDS or len(mothers)!=161014 or mothers.event_id.duplicated().any() or mothers.product_id.nunique()!=98 or mothers.family_id.nunique()!=95:raise ValueError('complete161014 98product95family forward mother projection required')
        numeric(mothers,['sequence_index','u_index'])
        choices={};ids={}
        for a in ARMS:choices[a],ids[a]=prepare_choices(mothers,read_table(h['arms'][a]['choices_main_binding']),a)
        actions,action_receipt=collect_action_union(read_table(h['causal_actions_projection_binding']),set.union(*ids.values()))
        boundsdoc=read_json(h['boundaries_binding'])
        if boundsdoc.get('schema')!='stage156_voluntary_K_only_v1' or boundsdoc.get('account_deadline_certified') is not False:raise ValueError('unchanged unqualified voluntary calendar K required')
        # New child epochs must be in the full-calendar boundary document, never old157's selection gate.
        if not set(actions.reference_epoch).issubset(boundsdoc['epochs']):raise ValueError('new selected epoch missing full-domain K')
        calendar=decode_calendar(np.load(io.BytesIO(read_bytes(h['calendar_binding'])),allow_pickle=False))
        if h['calendar_binding']['bytes']!=deps['calendar']['bytes'] or h['calendar_binding']['sha256']!=deps['calendar']['sha256']:raise ValueError('original source calendar differs')
        store,receipt,cache_meta=r.cache_source.restore_native_cache(deps['native_cache_manifest'])
        if receipt['native_source_queries']!=0 or r.ref.NATIVE_QUERIES!=0 or not same(receipt['cache_file'],deps['native_cache']):raise ValueError('one accepted cache load, zero native SQL required')
        market,dates=r.CachedMarket(store),store.calendar
        if dates!=calendar:raise ValueError('cache/handoff calendar mismatch')
        economics=json.loads(read_bytes(deps['economic_projection']))['instruments']
        if set(economics)!=set(store.series):raise ValueError('exact cache/economics epochs required')
        signals={};prepared={}
        for a in ARMS:
            sig=v.make_voluntary_signals(actions,mothers,choices[a],boundsdoc['epochs'],market,dates,economics)
            if len(sig)!=len(ids[a]):raise ValueError('selected signal admission changed')
            sig['arm']=a;sig['control_id']=a;signals[a]=sig;prepared[a]=v.author.organize(sig,mothers,dates)
            r.ref.write_table(folder/('signals_'+a+'.csv.gz'),sig,[])
            trace=['event_id','mother_event_id','reference_epoch','anchor_epoch','u_date','u_index','D_index',
                'source_lifecycle_index','voluntary_boundary_index','effective_lifecycle_index','effective_boundary_origin','K_target_date','K_date','K_state']
            r.ref.write_table(folder/('boundary_lineage_'+a+'.csv.gz'),sig[trace],[])
        bounds={}
        for w in WINDOWS:
            start,end=(int(np.searchsorted(dates,x)) for x in BOUNDS[w])
            if end>=len(dates) or dates[end]!=BOUNDS[w][1]:raise ValueError('fixed source window endpoint absent')
            bounds[w]=(start,end)
        controls=c['control_accounts_reused'];keyed={(x['window'],x['cost']):x for x in controls}
        if len(controls)!=4 or set(keyed)!={(w,k) for w in WINDOWS for k in COSTS}:raise ValueError('all four A157 own books required')
        for (w,k),x in keyed.items():
            expected='NARROW_VOLUNTARY_RESELECT_'+w+'_'+k
            if x['account_id']!=expected or Path(x['directory']).name!=expected or 'stage157_voluntary_cash' not in x['directory']:raise ValueError('A is accepted157 OWN book, not131B')
        held=read_json(h['held_gate_binding'])
        if set(held.get('contrasts',{}))!=set(CONTRASTS):raise ValueError('three held contrast diagnostics required')
        state.update(v=v,r=r,mothers=mothers,signals=signals,prepared=prepared,market=market,dates=dates,economics=economics,
            bounds=bounds,receipt=receipt,cache_meta=cache_meta,controls=keyed,families=sorted(mothers.family_id.unique()),held=held['contrasts'],
            summaries={},reports={},daily={},family_tables=[],sectors=[],tails={})
        write_json(folder/'source_read_receipt.json',dict(receipt,**action_receipt,derived_mother_reads=1,
            complete_forward_mother_rows=len(mothers),selected_by_arm={a:len(ids[a]) for a in ARMS},
            cache_restores=1,original129_mother_reads=0,original_COMMON_reads=0,model_fits=0,selectors_called=0,
            old_A_replays=0,labels_read=0,old_global_ARMS_changed=False))
        write_json(folder/'control_references.json',controls)
    def run(spec):
        start,end=state['bounds'][spec['window']];a=spec['arm']
        return state['v'].kernel.run_cash_account(state['signals'][a],state['market'],state['dates'],state['economics'],
            spec['cost'],spec['account_id'],start,end,prepared=state['prepared'][a])
    def export(spec,book):
        r=state['r'];folder=out/spec['account_id'];ledgers=r.write_ledgers(folder,book)
        summary,report,fy=r.helpers.cash_report(book,state['families'],r.ref.INITIAL)
        tick_lots=0.;unknown_tick_fills=0
        for f in book['fills']:
            tick=state['economics'][f['epoch']].get('tick_size')
            if r.ref.positive(tick):tick_lots+=abs(f['fill_price']-f['reference_price'])/float(tick)*f['qty']
            else:unknown_tick_fills+=1
        summary.update(spec,role='candidate',source_helper_arm='VOLUNTARY_RESELECT',any_historical_stale=report['stale_days']>0,
            execution_unknown=book['execution_unknown'],unknown_capacity_fills=sum(x['capacity_state']=='execution_capacity_unknown' for x in book['capacity_audit']),
            capacity_unknown_roots=len(book['capacity_unknown_roots']),entry_execution_unknown=len(book['entry_execution_unknown']),
            slippage_tick_lots_known=tick_lots,unknown_tick_fills=unknown_tick_fills,slippage_already_in_fill_price=True,
            transaction_count_definition='closed_trades=closed roots; fills=all BUY/SELL fills; total_filled_qty=quantity')
        key=(spec['arm'],spec['window'],spec['cost']);state['summaries'][key]=summary;state['reports'][spec['account_id']]=report
        state['daily'][key]=pd.DataFrame(book['daily']);state['family_tables'].append(r.report_helpers.add_family_costs(fy,book).assign(**spec))
        groups,tails=r.extra_reports(book);state['tails'][spec['account_id']]=tails
        state['sectors'].extend(dict(account_id=spec['account_id'],arm=spec['arm'],window=spec['window'],cost=spec['cost'],**x) for x in groups)
        for name,value in [('summary',summary),('diagnostics',report),('largest_wins_losses',tails)]:write_json(folder/(name+'.json'),r.kernel.original.safe(value))
        r.ref.write_table(folder/'sector_variant_year_including_zero.csv.gz',state['v'].sector_year_attribution(book),[])
        return dict(spec,directory=str(folder),summary=binding(folder/'summary.json'),ledgers=ledgers)
    def finalize(folder,records):
        r=state['r']
        if not same(old['diagnostics'],p['input_bindings']['A157_diagnostics']):raise ValueError('own157 diagnostic binding differs')
        control_reports=read_json(p['input_bindings']['A157_diagnostics']);indices={};control_metrics=[]
        for w,b in c['CI']['indices'].items():indices[w]=np.load(io.BytesIO(read_bytes(b)),allow_pickle=False)
        for (w,k),x in state['controls'].items():
            key=('A',w,k);state['summaries'][key]=dict(read_json(x['summary']),arm='A',window=w,cost=k,account_id=x['account_id'],role='control_reused',replayed=False)
            state['daily'][key]=pd.read_csv(io.BytesIO(read_bytes(control_ledger_binding(x,'daily'))),compression='gzip',float_precision='round_trip')
            state['reports'][x['account_id']]=control_reports[x['account_id']]
            control_metrics.append(state['summaries'][key])
        points={k:[] for k in CONTRASTS};annual=[];paired_year=[];distributions={}
        pair_arms={'B_minus_A':(ARMS[0],'A'),'C_minus_A':(ARMS[1],'A'),'C_minus_B':(ARMS[1],ARMS[0])}
        for contrast,(active,baseline) in pair_arms.items():
            for w in WINDOWS:
                for k in COSTS:
                    sk,bk=(active,w,k),(baseline,w,k);a,b=state['summaries'][sk],state['summaries'][bk]
                    start,end=state['bounds'][w]
                    if indices[w].shape!=(2000,end-start+1):raise ValueError('original bootstrap source width differs')
                    stats,dist=r.paired_statistics(state['daily'][sk],state['daily'][bk],indices[w])
                    point=dict(contrast=contrast,window=w,cost=k,active_account_id=a['account_id'],reference_account_id=b['account_id'],
                        active_total_return_pct=a['total_return_pct'],reference_total_return_pct=b['total_return_pct'],
                        ending_equity_difference=a['ending_equity']-b['ending_equity'],
                        sharpe_difference=None if a.get('sharpe') is None or b.get('sharpe') is None else a['sharpe']-b['sharpe'],
                        **r.helpers.compare_points(a,b),**stats)
                    points[contrast].append(point);distributions[contrast+'_'+w+'_'+k]=dist
                    ar=state['reports'][a['account_id']]['annual_slices'];br=state['reports'][b['account_id']]['annual_slices']
                    paired_year.extend(dict(contrast=contrast,window=w,cost=k,**x) for x in pair_years(ar,br))
        for key,summary in state['summaries'].items():
            for x in state['reports'][summary['account_id']]['annual_slices']:
                annual.append(dict(account_id=summary['account_id'],arm=key[0],window=key[1],cost=key[2],**x))
        stale=any(x['stale_days']>0 for x in state['reports'].values())
        unknown=any(s['execution_unknown'] for s in state['summaries'].values())
        wealth=all(r._log_path(x)[0] is not None for x in state['daily'].values())
        gate=dual_gate(points,state['held'],wealth_positive=wealth,any_stale=stale,execution_unknown=unknown)
        gate.update(own_A_control_books=4,new_B_C_cash_books=8,full_products=98,full_families=95,
            evidence='historically adaptive conditional research; 2020/2023 holdouts are not blind',
            stop_loss_cannot_cap_gap_loss=True,capacity_and_historical_rules_remain_unknown=True)
        old_fy=read_table(p['input_bindings']['A157_family_year'])
        old_fy=old_fy.loc[old_fy.arm.eq('VOLUNTARY_RESELECT')].copy();old_fy['arm']='A';old_fy['candidate']='A'
        if set(old_fy.family_id)!=set(state['families']):raise ValueError('A157 full95 family attribution required')
        numeric(old_fy,['net_equity_contribution','fee','slippage','fill_count','filled_qty'])
        family_year=pd.concat(state['family_tables']+[old_fy],ignore_index=True)
        for (arm,w,k),summary in state['summaries'].items():
            f=family_year.loc[family_year.arm.eq(arm)&family_year.window.eq(w)&family_year.cost.eq(k)]
            if not np.isclose(f.net_equity_contribution.sum(),summary['ending_equity']-r.ref.INITIAL,rtol=1e-12,atol=1e-6):raise ValueError('family attribution cash identity differs')
        through2025=[dict(account_id=state['summaries'][key]['account_id'],arm=key[0],window=key[1],cost=key[2],
            **same_book_through_2025(frame,r.ref.INITIAL)) for key,frame in state['daily'].items()]
        for name,value in [('account_summaries',list(state['summaries'].values())),('comparisons',[x for v in points.values() for x in v]),
            ('annual_slices',annual),('paired_annual',paired_year),('bootstrap_distributions',pd.DataFrame(distributions)),
            ('family_year_including_zero',family_year),
            ('family_total_including_zero',family_year.groupby(['arm','window','cost','family_id'])[['net_equity_contribution','fee','slippage','fill_count','filled_qty']].sum().reset_index()),
            ('same_book_through_2025',through2025),('sector_variant_attribution',state['sectors'])]:
            r.ref.write_table(folder/(name+'.csv.gz'),value,[])
        for name,value in [('decision',gate),('diagnostics',state['reports']),('largest_wins_losses',state['tails'])]:write_json(folder/(name+'.json'),r.kernel.original.safe(value))
        if source_bundle()!=bundle or r.ref.NATIVE_QUERIES!=0:raise ValueError('491 source drift or zero-SQL budget failure')
        if r.cache_source.database_state(state['cache_meta']['database']['path'])!=state['receipt']['database_after']:raise ValueError('native database stat drift')
    return run_eight(out,run,export,before=prepare,finalize=finalize,metadata=metadata)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','protocol-sha256','handoff','handoff-sha256','authorization','authorization-sha256','output'):parser.add_argument('--'+name,required=True)
    execute(parser.parse_args())

if __name__=='__main__':main()
