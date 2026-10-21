"""Frozen639 original-account structural support only; no new orders or PnL."""
import argparse
from collections import Counter,defaultdict
import csv
from datetime import datetime,timezone
import gzip
import importlib.util
import io as streams
import json
import math
from pathlib import Path
import time
import traceback

LINE=Path(__file__).resolve().parents[1]
PROTOCOL_SHA='455e3f33f548875bfe144e64225054f0a124b48ea0eb2f159290fa1091f07542'
s=importlib.util.spec_from_file_location('accepted627_IO_only',LINE/'tools/stage627_full_admission_diagnostic.py')
io=importlib.util.module_from_spec(s);s.loader.exec_module(io)
TOL=1e-10


def num(row,key):
    try:v=float(row[key])
    except (KeyError,TypeError,ValueError):return None
    return v if math.isfinite(v) else None


def integer(row,key):
    v=num(row,key);return int(v) if v is not None and v.is_integer() else None


def boolean(row,key):
    v=row.get(key)
    return True if v in (True,1,'True','1') else False if v in (False,0,'False','0') else None


def close(a,b):return abs(a-b)<=TOL*max(1.,abs(a),abs(b))


def signal_checks(s,calendar):
    if s is None:return dict(signal_present=False)
    u=integer(s,'u_index');D=integer(s,'D_index');K=integer(s,'voluntary_boundary_index');source=integer(s,'source_lifecycle_index')
    eff=integer(s,'effective_lifecycle_index');life=integer(s,'lifecycle_index');N=num(s,'N_u');cap=integer(s,'entry_capacity_qty')
    ready=integer(s,'label_history_ready20');history=integer(s,'history_run');score=num(s,'score');C=num(s,'u_close')
    index_ok=u is not None and D is not None and 0<=u<len(calendar) and D==u+1 and calendar[u]==s.get('u_date')
    if K is None:
        meta=source is not None and eff==source and life==eff and s.get('K_state')=='after_calendar_pending' and s.get('effective_boundary_origin')=='source_lifecycle'
    else:
        origin='voluntary_calendar' if source is not None and K<source else 'same_source_and_voluntary' if K==source else 'source_lifecycle'
        meta=source is not None and eff==min(K,source) and life==eff and 0<=K<len(calendar) and s.get('K_date')==calendar[K] and s.get('effective_boundary_origin')==origin
    Ddate=calendar[D] if D is not None and 0<=D<len(calendar) else None
    gate=(D<K if D is not None else None) if K is not None else (Ddate<s['K_target_date'] if Ddate and s.get('K_target_date') else None)
    return dict(signal_present=True,signal_u_clock=index_ok,signal_cutoff=s.get('cutoff')==io.fixed.cutoff_for(s.get('u_date','')),
        signal_positive_ready=score is not None and score>0 and N is not None and N>0 and C is not None and C>0 and num(s,'low20_u') is not None
            and cap is not None and cap>=1 and ready==1 and history is not None and history>=20 and integer(s,'potential')==1,
        signal_lifecycle_metadata=meta,signal_D_before_K=gate,
        signal_D_before_source=D<source if D is not None and source is not None else None)


def evaluate_u(p,entry,candidate,daily,buy,reservation,reductions,calendar,canonical):
    """Tri-state conjunction, only u information. D fills are not an argument."""
    checks={};u=calendar.index(p['date']) if p.get('date') in calendar else None
    D=u+1 if u is not None else None;Ddate=calendar[D] if D is not None and D<len(calendar) else None
    qty=integer(p,'qty');lot=integer(reservation or {},'round_lot')
    identity=None
    if entry is not None and buy is not None and reservation is not None:
        match=(p.get('root_id')==p.get('account_id','')+'_'+p.get('event_id','') and entry.get('event_id')==p.get('event_id')
            and all(entry.get(k)==p.get(t) for k,t in [('reference_epoch','epoch'),('family_id','family_id'),('product_id','product_id')]))
        match=match and all(buy.get(k)==p.get(k) for k in ('root_id','event_id','family_id','product_id','epoch'))
        entryD=integer(entry,'D_index');entryday=calendar[entryD] if entryD is not None and 0<=entryD<len(calendar) else None
        match=match and buy.get('side')=='BUY' and buy.get('date')==entryday and reservation.get('execution_date')==entryday
        match=match and reservation.get('u_date')==entry.get('u_date') and reservation.get('event_id')==entry.get('event_id')
        match=match and reservation.get('budget_id')==buy.get('budget_id') and reservation.get('budget_kind')=='new_entry'
        bq=integer(buy,'qty');rq=integer(reservation,'D_qty')
        match=match and qty is not None and qty>0 and bq is not None and bq>=qty and rq==bq and lot is not None and lot>0 and qty%lot==0 and bq%lot==0
        match=match and num(buy,'fill_price') is not None and num(buy,'fill_price')>0 and p.get('_u_qty_reconciled') is True
        identity=True if match else None
    checks['old_entry_identity']=identity
    if entry is None:
        checks.update(old_signal_metadata=None,old_pureK=None,old_K_equals_nextD=None)
    else:
        old=signal_checks(entry,calendar);checks['old_signal_metadata']=all(v is True for v in old.values())
        K=integer(entry,'voluntary_boundary_index');source=integer(entry,'source_lifecycle_index')
        checks['old_pureK']=(entry.get('effective_boundary_origin')=='voluntary_calendar' and K is not None and source is not None and K<source)
        checks['old_K_equals_nextD']=D==K if D is not None and K is not None else None
    mark=p.get('mark_state');stale=integer(p,'stale_days')
    checks['u_nonstale_nondeferred']=mark=='native_close' and stale==0 if mark and stale is not None else None
    checks['u_lifecycle_force']=p.get('force_next')=='lifecycle_exit' if p.get('force_next') is not None else None
    target=p.get('reduce_to_next');no_reduction=True if target in ('',None) else False if num(p,'reduce_to_next') is not None else None
    for r in reductions:
        if r.get('budget_kind')!='existing_position_reduction':continue
        if r.get('root_id')==p.get('root_id') or r.get('event_id')==p.get('event_id'):no_reduction=False
        elif not r.get('root_id') and not r.get('event_id') and no_reduction is True:no_reduction=None
    checks['u_no_reduction']=no_reduction
    E=num(daily or {},'equity');risk=num(daily or {},'initial_risk');margin=num(daily or {},'buffered_margin');insolvent=boolean(daily or {},'ever_insolvent')
    checks['u_account_alive']=not insolvent and E>0 if insolvent is not None and E is not None else None
    checks['u_account_risk_cap']=risk<=.02*E+TOL*max(1,abs(.02*E)) if risk is not None and E is not None else None
    checks['u_account_margin_cap']=margin<=.25*E+TOL*max(1,abs(.25*E)) if margin is not None and E is not None else None
    if candidate is None:
        checks['original_same_u_intent']=False;checks['different_epoch']=None;checks['new_signal_eligible']=None
    else:
        checks['original_same_u_intent']=candidate.get('u_date')==p.get('date') and candidate.get('family_id')==p.get('family_id')
        checks['different_epoch']=candidate.get('reference_epoch')!=p.get('epoch')
        checks['new_signal_eligible']=all(v is True for v in signal_checks(candidate,calendar).values())
    base=list(checks.values());provisional=all(v is True for v in base)
    canonical_state=canonical.get('reference_state') if canonical is not None else 'not_requested'
    canonical_ref=canonical.get('reference_epoch','') if canonical is not None else ''
    checks['canonical_same']=canonical_ref==entry.get('anchor_epoch') if canonical_state=='found' and entry is not None else None
    false=[k for k,v in checks.items() if v is False];unknown=[k for k,v in checks.items() if v is None]
    state='known_false' if false else 'provisional_needs_canonical' if provisional and canonical is None else 'unknown' if unknown else 'supported'
    return dict(u_plan_state=state,u_plan_reason=';'.join(false if false else unknown),checks_json=json.dumps(checks,separators=(',',':')),
        provisional=provisional,canonical_state=canonical_state,canonical_reference=canonical_ref,old_lot=lot,
        u_index=u,D_index=D,D_date=Ddate,new_event_id=candidate.get('event_id','') if candidate else '',
        new_epoch=candidate.get('reference_epoch','') if candidate else '',entry_anchor=entry.get('anchor_epoch','') if entry else '',
        replacement_qty='unknown',newroot_reservation='unknown',new_two_leg_execution='unknown',financial_metrics='N/A')


def observe_D(p,Ddate,fills,Dpositions,available):
    """Observed old-leg fact, independent of u qualification and new quantities."""
    root=p.get('root_id');q=integer(p,'qty');own=[f for f in fills if f.get('root_id')==root]
    states=sorted({f.get('capacity_state','') for f in own})
    out=dict(D_observation_state='unknown',D_reason='D_not_observed',D_sell_qty=None,D_residual_qty=None,
        D_old_capacity_states_json=json.dumps(states,separators=(',',':')))
    if not available or not Ddate:return out
    if q is None or q<=0:out['D_reason']='old_qty_unidentified';return out
    if any(f.get('family_id')==p.get('family_id') and f.get('root_id')!=root for f in fills):
        out.update(D_observation_state='known_false',D_reason='extra_samefamily_fill');return out
    if any(any(f.get(k)!=p.get(k) for k in ('event_id','family_id','product_id','epoch')) for f in own):
        out['D_reason']='old_fill_identity_unknown';return out
    sells=[f for f in own if f.get('side')=='SELL'];values=[integer(f,'qty') for f in sells]
    if any(v is None or v<=0 for v in values):out['D_reason']='old_fill_qty_unknown';return out
    sold=sum(values);remaining=[integer(r,'qty') for r in Dpositions if r.get('root_id')==root]
    if any(v is None for v in remaining) or len(remaining)>1:out['D_reason']='residual_snapshot_unknown';return out
    residual=sum(remaining);out.update(D_sell_qty=sold,D_residual_qty=residual)
    if any(f.get('side')!='SELL' or f.get('reason')!='lifecycle_exit' for f in own):
        out.update(D_observation_state='known_false',D_reason='mixed_or_other_exit');return out
    if sold==q and residual==0:
        if any(num(f,'fill_price') is None or num(f,'fill_price')<=0 for f in sells):out['D_reason']='fill_price_unknown';return out
        out.update(D_observation_state='observed_full_lifecycle_close',D_reason='complete_original_modeled_old_leg');return out
    if sold<=q and sold+residual==q:
        out.update(D_observation_state='known_false',D_reason='partial_or_no_old_close');return out
    out['D_reason']='old_quantity_reconciliation_unknown';return out


def csv_rows(b,fields,optional,reads,role):
    with Path(b['path']).open('rb') as raw:
        hashed=io.HashStream(raw)
        with gzip.GzipFile(fileobj=hashed,mode='rb') as z,streams.TextIOWrapper(z,encoding='utf-8',newline='') as text:
            reader=csv.DictReader(text);header=reader.fieldnames
            if not header or not set(fields)<=set(header):raise ValueError('required source header missing '+role)
            missing=[k for k in optional if k not in header];n=0
            for row in reader:
                n+=1;yield {k:row[k] if k in header else '' for k in fields+optional}
        if hashed.n!=b['bytes'] or hashed.sha.hexdigest()!=b['sha256']:raise ValueError('combined source binding mismatch '+role)
        reads[role]=dict(b,rows=n,source_opens=1,hash_and_parse_same_stream=True,columns=fields+optional,missing_optional_columns=missing)


def counts(rows):
    material=sum(r['u_plan_state']=='unknown' or (r['u_plan_state']=='supported' and r['D_observation_state']=='unknown') for r in rows)
    return dict(position_snapshots=len(rows),distinct_roots=len({r['root_id'] for r in rows}),
        u_supported=sum(r['u_plan_state']=='supported' for r in rows),u_known_false=sum(r['u_plan_state']=='known_false' for r in rows),
        u_unknown=sum(r['u_plan_state']=='unknown' for r in rows),provisional=sum(r['provisional'] for r in rows),
        D_full_close=sum(r['D_observation_state']=='observed_full_lifecycle_close' for r in rows),
        joint_supported=sum(r['u_plan_state']=='supported' and r['D_observation_state']=='observed_full_lifecycle_close' for r in rows),
        material_unknown=material,underlying_action_union=len({r['event_id'] for r in rows}),
        joint_action_pair_union=len({(r['event_id'],r['date'],r['new_event_id']) for r in rows if r['u_plan_state']=='supported' and r['D_observation_state']=='observed_full_lifecycle_close'}))


def actual(protocol_path,ready_path,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);began=time.monotonic();reads={};artifacts={}
    io.json_write(out/'started.json',dict(started_at=datetime.now(timezone.utc).isoformat(),automatic_retry=False,new_fit=0,new_cash=0,new_labels=0,new_CI=0))
    try:
        pb=io.binding(protocol_path)
        if pb['sha256']!=PROTOCOL_SHA:raise ValueError('frozen639 changed')
        protocol=json.loads(Path(protocol_path).read_text());ready=json.loads(Path(ready_path).read_text())
        if ready['protocol']!=pb:raise ValueError('source-ready protocol differs')
        for b in ready['sources']+ready['helpers']:io.read_bound(b)
        tested=json.loads(io.read_bound(ready['fixture_receipt']['binding']))
        if tested['exit_code']!=0 or tested['source']!=ready['sources'][0] or tested['fixture']!=ready['sources'][1]:raise ValueError('tested637 source differs')
        inputs=protocol['inputs'];fields=protocol['required_fields'];account_ids=protocol['account_ids'];END=protocol['historical_END']
        cal=io.read_bound(inputs['calendar']);(out/'calendar.json').write_bytes(cal);calendar=json.loads(cal)['calendar'];lookup={d:i for i,d in enumerate(calendar)}
        fam=io.read_bound(inputs['family_inventory']);(out/'family_inventory.json').write_bytes(fam);families=json.loads(fam)['families_by_scope']['main']
        if len(families)!=95 or calendar!=sorted(set(calendar)):raise ValueError('original calendar/family inventory differs')
        signals=list(csv_rows(inputs['signals'],fields['signals'],[],reads,'signals'))
        if len(signals)!=4365 or len({s['event_id'] for s in signals})!=4365 or len({(s['family_id'],s['u_date']) for s in signals})!=4365:raise ValueError('original4365 m1 identity differs')
        for signal in signals:
            if signal['event_id']==signal['mother_event_id'] or not all(v is True for v in signal_checks(signal,calendar).values()):raise ValueError('original signal identity/eligibility differs')
        with io.csv_sink(out/'signal_slim.csv.gz',fields['signals'],artifacts) as sink:sink.writerows(signals)
        by_event={s['event_id']:s for s in signals};by_family_u={(s['family_id'],s['u_date']):s for s in signals};books={a:{} for a in account_ids}
        for role in ('positions','fills','reservations','daily'):
            required=fields[role] if role!='reservations' else fields['reservations_required'];optional=fields['reservations_optional_header'] if role=='reservations' else []
            with io.csv_sink(out/(role+'_slim.csv.gz'),required+optional,artifacts) as sink:
                for account in account_ids:
                    rows=list(csv_rows(inputs[account+'/'+role+'.csv.gz'],required,optional,reads,account+'/'+role))
                    if any(r['account_id']!=account or r['scenario']!=account.rsplit('_',1)[-1] for r in rows):raise ValueError('original account source identity differs')
                    sink.writerows(rows);books[account][role]=rows
        io.progress(out,'all_original_small_books_read',position_rows=sum(len(b['positions']) for b in books.values()))
        contexts=[];requested=set()
        for account,book in books.items():
            daily={r['date']:r for r in book['daily']};window='cold_2023' if '_cold_2023_' in account else 'primary_2020';bounds=protocol['account_windows'][window]
            if len(daily)!=len(book['daily']) or sorted(daily)!=[d for d in calendar if bounds[0]<=d<=bounds[1]]:raise ValueError('complete account date grid differs')
            fill_root=defaultdict(list);fill_day=defaultdict(list);pos_day=defaultdict(list);reservations=defaultdict(list);budget=defaultdict(list)
            for f in book['fills']:fill_root[f['root_id']].append(f);fill_day[f['date']].append(f)
            for r in book['reservations']:reservations[r['u_date']].append(r);budget[r['budget_id']].append(r)
            for p in book['positions']:pos_day[p['date']].append(p)
            for original in book['positions']:
                p=dict(original);rootfills=fill_root[p['root_id']];buys=[f for f in rootfills if f['side']=='BUY'];buy=buys[0] if len(buys)==1 else None
                rr=budget.get(buy['budget_id'],[]) if buy else [];entry_res=rr[0] if len(rr)==1 else None
                past=[f for f in rootfills if f['date']<=p['date']];qs=[integer(f,'qty') for f in past]
                net=sum(q if f['side']=='BUY' else -q for f,q in zip(past,qs)) if all(q is not None and f['side'] in ('BUY','SELL') for f,q in zip(past,qs)) else None
                p['_u_qty_reconciled']=net==integer(p,'qty') if net is not None else None
                entry=by_event.get(p['event_id']);candidate=by_family_u.get((p['family_id'],p['date']))
                args=(p,entry,candidate,daily.get(p['date']),buy,entry_res,reservations[p['date']],calendar)
                plan=evaluate_u(*args,None);D=plan['D_date'];observed=observe_D(p,D,fill_day[D],pos_day[D],D in daily)
                contexts.append((original,args,observed))
                if plan['provisional']:requested.add((p['product_id'],p['date'],str(plan['u_index'])))
        refs={};mother_opened=bool(requested)
        if requested:
            matched=defaultdict(list)
            for row in csv_rows(inputs['mother_identity'],fields['mother_identity'],[],reads,'mother_identity'):
                key=(row['product_id'],row['u_date'],row['u_index'])
                if key in requested:matched[key].append(row['reference_epoch'])
            for product,day,u in sorted(requested):
                values=matched[(product,day,u)];state='found' if len(values)==1 and values[0] else 'ambiguous' if len(values)>1 else 'missing'
                refs[(product,day,u)]=dict(product_id=product,u_date=day,u_index=u,match_count=len(values),reference_values_json=json.dumps(values),
                    reference_state=state,reference_epoch=values[0] if state=='found' else '')
            with io.csv_sink(out/'requested_canonical_refs.csv.gz',['product_id','u_date','u_index','match_count','reference_values_json','reference_state','reference_epoch'],artifacts) as sink:sink.writerows(refs.values())
        support=[]
        for original,args,observed in contexts:
            p=args[0];key=(p['product_id'],p['date'],str(lookup.get(p['date'])));canon=refs.get(key)
            plan=evaluate_u(*args,canon)
            if plan['u_plan_state']=='provisional_needs_canonical':raise ValueError('provisional source reference was not resolved')
            support.append(dict(original,**plan,**observed,u_qty_reconciled=p['_u_qty_reconciled']))
        output_fields=fields['positions']+[k for k in support[0] if k not in fields['positions']]
        with io.csv_sink(out/'support.csv.gz',output_fields,artifacts) as sink:sink.writerows(support)
        per_account={a:counts([r for r in support if r['account_id']==a]) for a in account_ids};total=counts(support)
        decision='inconclusive' if total['material_unknown'] else 'design_only' if total['joint_supported'] else 'structural_NO_GO'
        annual=[];family_year=[];month=[];months=sorted({d[:7] for d in calendar if '2020-01-01'<=d<=END})
        for account in account_ids:
            rows=[r for r in support if r['account_id']==account]
            for year in range(2020,2027):
                ys=[r for r in rows if r['date'][:4]==str(year)];annual.append(dict(account_id=account,year=year,**counts(ys)))
                grouped=defaultdict(list)
                for r in ys:grouped[r['family_id']].append(r)
                for family in families:family_year.append(dict(account_id=account,year=year,family_id=family,**counts(grouped[family])))
            for mo in months:month.append(dict(account_id=account,month=mo,**counts([r for r in rows if r['date'][:7]==mo])))
        for name,rows in [('annual_counts',annual),('family_year_counts',family_year),('month_counts',month)]:
            with io.csv_sink(out/(name+'.csv.gz'),list(rows[0]),artifacts) as sink:sink.writerows(rows)
        summary=dict(status='completed',decision=decision,all_accounts=per_account,total=total,
            u_structural_nonzero=total['u_supported']>0,joint_structure_nonzero=total['joint_supported']>0,
            mother_opened=mother_opened,mother_skip_reason=None if mother_opened else 'zero_precanonical_provisional_intersections_no_canonical_pass_claim',requested_canonical_keys=len(requested),
            u_known_false_reasons=dict(Counter(reason for r in support if r['u_plan_state']=='known_false' for reason in r['u_plan_reason'].split(';') if reason)),
            u_unknown_reasons=dict(Counter(reason for r in support if r['u_plan_state']=='unknown' for reason in r['u_plan_reason'].split(';') if reason)),
            D_observation_reasons=dict(Counter(r['D_reason'] for r in support)),
            original_signal_count=len(signals),all_original_position_rows_retained=len(support),full_family_inventory=95,
            historical_END=END,current_day_close_dependency=False,replacement_qty='unknown',newroot_reservation='unknown',
            two_leg_executable_qualification='unknown',financial_metrics='N/A',new_fit=0,new_cash=0,new_labels=0,new_CI=0,new_financial_gate=0,
            material_unknown_definition='Only structural u/D identity/canonical facts; alwaysunknown new budgets/qty excluded.',
            old_capacity='Original fills capacity_state retained; unknown includes missing or exceeded fixed cap, not a newlot guarantee.',
            goal_complete=False,production_qualified=False,counters=protocol['counters'])
        io.json_write(out/'summary.json',summary);io.json_write(out/'input_read_receipts.json',reads)
        terminal=dict(status='completed',exit_code=0,elapsed_seconds=time.monotonic()-began,automatic_retry=False,new_fit=0,new_cash=0,new_labels=0)
        io.json_write(out/'terminal.json',terminal)
        for p in sorted(out.iterdir()):
            if p.is_file() and p.name not in artifacts:artifacts[p.name]=io.binding(p)
        io.json_write(out/'manifest.json',dict(schema='stage637_original_K_structural_support_v1',status='completed',protocol=pb,
            source_ready=io.binding(ready_path),source_bundle=ready['sources'],helpers=ready['helpers'],inputs=inputs,input_read_receipts=reads,
            mother_opened=mother_opened,mother_keys=len(requested),artifacts=artifacts,decision=decision,new_fit=0,new_cash=0,new_labels=0,
            new_CI=0,new_financial_gate=0,replacement_qty='unknown',financial_metrics='N/A',counters=protocol['counters']))
        return dict(terminal=terminal,decision=decision,u_supported=total['u_supported'],joint_supported=total['joint_supported'],material_unknown=total['material_unknown'],mother_opened=mother_opened)
    except BaseException as exc:
        io.json_write(out/'terminal.json',dict(status='failed',exit_code=1,elapsed_seconds=time.monotonic()-began,
            automatic_retry=False,new_fit=0,new_cash=0,error=repr(exc),traceback=traceback.format_exc()))
        io.json_write(out/'input_read_receipts.json',reads);raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--protocol',required=True);p.add_argument('--source-ready',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(actual(a.protocol,a.source_ready,a.output),ensure_ascii=False))
