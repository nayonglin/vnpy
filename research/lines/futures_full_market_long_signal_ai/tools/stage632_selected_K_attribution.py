"""Frozen630 fixed52+K accounting only; no selection/fit/cash/path replay/CI.

Historical END remains2026-10-16. This does not await today's close or
change the separate u20 -> D21 forward calculation.
"""
import argparse
from collections import Counter, defaultdict
import importlib.util
import json
import math
from pathlib import Path
import time
import traceback
from datetime import datetime, timezone

LINE=Path(__file__).resolve().parents[1]
PROTOCOL_SHA='ded4457758a82ab79ea7297b031a95973a3ab691e735738ee2a9f16b3b1945e4'
spec=importlib.util.spec_from_file_location('accepted627_IO_only',LINE/'tools/stage627_full_admission_diagnostic.py')
io=importlib.util.module_from_spec(spec);spec.loader.exec_module(io)
SCOPES=io.SCOPES;END='2026-10-16';TOL=1e-8
E_FIELDS=io.SCORE+io.PURE+['m','known','Y','outcome_reason']
ID=io.SCORE[:10]
K_STATE=['branch','primary_domain','calendar_allowed','K_target_date','K_index','K_date','K_state',
    'K_stress_known','K_stress_net_R','K_stress_known_date','K_stress_known_phase','K_stress_state',
    'K_stress_exit_index','K_stress_exit_date','K_stress_exit_reason','policy_reward_known','policy_reward',
    'policy_known_date','policy_known_phase','label_known_date','label_known_phase']
ACTION_COST=['N_u','R0_points','cash_risk_unit','multiplier','tick_size','entry_reference','exit_reference',
    'SL0','entry_boundary','exit_boundary','gross_points_reference','gross_R_reference','stress_entry_fill',
    'stress_exit_fill','stress_entry_fee_per_lot','stress_exit_fee_per_lot','stress_total_fee_per_lot',
    'stress_entry_slippage_per_lot','stress_exit_slippage_per_lot','stress_total_slippage_per_lot',
    'net_pnl_stress_per_lot','net_R_stress','entry_index','entry_date','exit_index','exit_date','exit_reason',
    'label_state','label_known_date','label_known_phase']
QUOTE_COST=['N_u','R0_points','cash_risk_unit','multiplier','tick_size','entry_reference','stress_entry_fill',
    'stress_entry_fee_per_lot','stress_entry_slippage_per_lot','native_day','native_open','native_valid',
    'K_stress_sell_fill','K_stress_sell_fee_per_lot','K_stress_sell_slippage_per_lot','K_stress_net_pnl_per_lot',
    'net_R_stress','label_state','label_known_date','label_known_phase','entry_index','entry_date','K_stress_tickized']
ACTION_FIELDS=list(dict.fromkeys(ID+ACTION_COST));QUOTE_FIELDS=list(dict.fromkeys(ID+K_STATE+QUOTE_COST))
VALUE_FIELDS=['A_I','G_J','Fee_J','Slip_J','known_net_unattributed','S_I','old_error_H','K_change_H',
    'remaining_error_I_minus_H','current_target_error','J_exposure','H_exposure','selected_known_exposure',
    'cancel_exposure','identified_gap_overshoot_contribution']
COUNT_FIELDS=['n','nI','selected','selected_known','selected_unknown','cancel','J_complete','J_incomplete','H_complete',
    'H_incomplete','nI0','component_check_failures','entry_day_gap_count','held_day_gap_count','quote_gap_unknown_count']


def flag(value):
    if value in (True,1,'True','1'):return True
    if value in (False,0,'False','0'):return False
    raise ValueError('explicit binary flag required')


def number(row,key):
    try:value=float(row[key])
    except (KeyError,ValueError,TypeError):return None
    return value if math.isfinite(value) else None


def close(a,b):return abs(a-b)<=TOL*max(1.,abs(b))


def attribute_action(e,k,old,quote,end):
    """Accounting on an already fixed m1 action; incomplete fields stay residual."""
    known=flag(e['known']);Y=float(e['Y']) if known else None;score=float(e['score']);branch=k['branch']
    old_value=number(old,'net_R_stress') if old else None
    H=bool(known and old and old.get('label_state')=='closed_complete_bar_model' and old_value is not None
        and old.get('label_known_date') and old['label_known_date']<=end and old.get('label_known_phase'))
    result=dict(known=known,YK=Y,score_value=score,branch=branch,J=False,G=None,Fee=None,Slip=None,
        component_state='K_unknown',component_check_failures=0,accounting_residual=None,max_scaled_component_residual=0.,
        H=H,oldY=old_value if H else None,old_error_H=old_value-score if H else None,
        K_change_H=Y-old_value if H else None,remaining_error_I_minus_H=Y-score if known and not H else None,
        exit_reason=k.get('K_stress_exit_reason','') or k.get('cancel_reason','') or 'unresolved',
        gap_state='K_unknown',gap_overshoot_R=None)
    if not known:return result
    if branch=='known_nonparticipation':
        if not (k.get('primary_domain')=='1' and k.get('policy_reward_known')=='1' and number(k,'policy_reward')==0
            and k.get('policy_known_date') and k['policy_known_date']<=end and k.get('policy_known_phase') and Y==0):
            raise ValueError('known cancellation not certified primary policy0')
        result.update(J=True,G=0.,Fee=0.,Slip=0.,component_state='known_cancel_no_execution',gap_state='cancel_no_execution',accounting_residual=0.)
        return result
    source=old if branch=='copy_before_K' else quote if branch=='quote_K' else None
    if source is None:result['component_state']='same_path_cost_source_missing';return result
    F=number(source,'entry_reference');X=number(source,'exit_reference' if branch=='copy_before_K' else 'native_open')
    N=number(source,'N_u');R0=number(source,'R0_points');M=number(source,'multiplier');d=number(source,'cash_risk_unit')
    buy=number(source,'stress_entry_fill');bf=number(source,'stress_entry_fee_per_lot');bs=number(source,'stress_entry_slippage_per_lot')
    sell_prefix='stress_exit_' if branch=='copy_before_K' else 'K_stress_sell_'
    sell=number(source,sell_prefix+'fill');sf=number(source,sell_prefix+'fee_per_lot');ss=number(source,sell_prefix+'slippage_per_lot')
    if branch=='copy_before_K' and source.get('exit_reason')=='gap_stop':
        B=number(source,'exit_boundary');entry=number(source,'entry_index');exit_=number(source,'exit_index')
        if all(v is not None for v in (B,X,R0,entry,exit_)) and R0>0 and exit_>=entry:
            result['gap_state']='entry_day_gap_stop' if exit_==entry else 'held_day_gap_stop'
            result['gap_overshoot_R']=max(B-X,0.)/R0
        else:result['gap_state']='copy_gap_fields_unknown'
    elif branch=='quote_K':result['gap_state']='quote_K_boundary_unknown'
    else:result['gap_state']='not_gap_stop'
    required=[F,X,N,R0,M,d,buy,bf,bs,sell,sf,ss]
    if any(v is None for v in required):result['component_state']='missing_same_path_component_fields';return result
    if min(F,X,N,R0,M,d,buy,sell)<=0 or min(bf,bs,sf,ss)<0:
        result.update(component_state='invalid_same_path_component_values',component_check_failures=1);return result
    checks=[]
    def check(name,a,b):checks.append((name,a,b,abs(a-b)/max(1.,abs(b))))
    check('R0=.25N',R0,.25*N);check('risk=R0M',d,R0*M)
    check('entry_slip',bs,M*(buy-F));check('exit_slip',ss,M*(X-sell))
    tick=number(source,'tick_size')
    if tick is not None and tick>0:
        check('entry_tick',buy,round(buy/tick)*tick);check('exit_tick',sell,round(sell/tick)*tick)
    G=M*(X-F)/d;Fee=(bf+sf)/d;Slip=M*((buy-F)+(X-sell))/d;net=G-Fee-Slip
    check('same_K_netR',net,Y);check('filled_price_net',M*(sell-buy)-bf-sf,Y*d)
    netpnl=number(source,'net_pnl_stress_per_lot' if branch=='copy_before_K' else 'K_stress_net_pnl_per_lot')
    if netpnl is None:result['component_state']='missing_saved_same_K_netpnl';return result
    check('saved_netpnl',netpnl,Y*d)
    if branch=='copy_before_K':
        for key,expected in [('stress_total_fee_per_lot',bf+sf),('stress_total_slippage_per_lot',bs+ss),
                              ('gross_points_reference',X-F),('gross_R_reference',(X-F)/R0)]:
            saved=number(source,key)
            if saved is None:result['component_state']='missing_saved_copy_check_fields';return result
            check(key,saved,expected)
        if result['gap_overshoot_R'] is not None:
            B=number(source,'exit_boundary');check('gap_gross_identity',G,(B-F)/R0-(B-X)/R0)
    failures=[name for name,a,b,scaled in checks if not close(a,b)]
    result.update(accounting_residual=net-Y,max_scaled_component_residual=max(v[3] for v in checks),component_check_failures=len(failures))
    if failures:result['component_state']='measurement_residual:'+','.join(failures);return result
    result.update(J=True,G=G,Fee=Fee,Slip=Slip,component_state='known_same_path_components')
    return result


def daily_accounting(E,selected):
    nI=sum(flag(r['known']) for r in E);known=[r for r in selected if r['known']]
    norm=lambda values:sum(values)/nI if nI else 0.
    J=[r for r in known if r['J']];H=[r for r in known if r['H']]
    out=dict(n=len(E),nI=nI,selected=len(selected),selected_known=len(known),selected_unknown=len(selected)-len(known),
        cancel=sum(r['component_state']=='known_cancel_no_execution' for r in known),J_complete=len(J),
        J_incomplete=len(known)-len(J),H_complete=len(H),H_incomplete=len(known)-len(H),nI0=int(nI==0),
        component_check_failures=sum(r['component_check_failures'] for r in selected),
        A_I=norm(r['YK'] for r in known),G_J=norm(r['G'] for r in J),Fee_J=norm(r['Fee'] for r in J),
        Slip_J=norm(r['Slip'] for r in J),known_net_unattributed=norm(r['YK'] for r in known if not r['J']),
        S_I=norm(r['score_value'] for r in known),old_error_H=norm(r['old_error_H'] for r in H),
        K_change_H=norm(r['K_change_H'] for r in H),remaining_error_I_minus_H=norm(r['remaining_error_I_minus_H'] for r in known if not r['H']),
        J_exposure=len(J)/nI if nI else 0.,H_exposure=len(H)/nI if nI else 0.,
        selected_known_exposure=len(known)/nI if nI else 0.,cancel_exposure=sum(r['component_state']=='known_cancel_no_execution' for r in known)/nI if nI else 0.,
        entry_day_gap_count=sum(r['gap_state']=='entry_day_gap_stop' for r in selected),
        held_day_gap_count=sum(r['gap_state']=='held_day_gap_stop' for r in selected),
        quote_gap_unknown_count=sum(r['gap_state']=='quote_K_boundary_unknown' for r in selected),
        identified_gap_overshoot_contribution=norm(r['gap_overshoot_R'] for r in known if r['gap_overshoot_R'] is not None))
    out['current_target_error']=out['A_I']-out['S_I']
    out['accounting_identity_residual']=out['A_I']-(out['G_J']-out['Fee_J']-out['Slip_J']+out['known_net_unattributed'])
    out['bridge_identity_residual']=out['A_I']-(out['S_I']+out['old_error_H']+out['K_change_H']+out['remaining_error_I_minus_H'])
    return out


def summarize(days):
    n=len(days)
    return dict(source_dates=n,**{key:sum(r[key] for r in days)/n if n else 0. for key in VALUE_FIELDS},
        counts={key:sum(r[key] for r in days) for key in COUNT_FIELDS},
        max_accounting_identity_residual=max((abs(r['accounting_identity_residual']) for r in days),default=0.),
        max_bridge_identity_residual=max((abs(r['bridge_identity_residual']) for r in days),default=0.),
        interpretation='Same fixed I/nI and full source-calendar equal-u; no causal zero-cost wealth or new CI.',
        gap='Identified copy-gap part only; quote_K prior boundary unknown, not filled0.')


def same_identity(a,b):
    if any(a[k]!=b[k] for k in ID):raise ValueError('original selected action identity differs')


def source_clock(e,k,old,q,end):
    if k['primary_domain']!='1' or k['calendar_allowed']!='1':raise ValueError('original m1 pureK domain differs')
    expected=io.label_outcome(k,end)
    if flag(e['known'])!=expected['known'] or (expected['known'] and not close(float(e['Y']),expected['Y'])):
        raise ValueError('original627 K classification/value differs')
    if k['branch']=='copy_before_K' and expected['known']:
        pairs={'K_stress_exit_index':'exit_index','K_stress_exit_date':'exit_date','K_stress_exit_reason':'exit_reason',
               'K_stress_known_date':'label_known_date','K_stress_known_phase':'label_known_phase'}
        if any(k[dst]!=old[src] for dst,src in pairs.items()) or k['entry_date']!=old['entry_date']:
            raise ValueError('copy_before_K source entry/exit/clock mismatch')
    if k['branch']=='quote_K' and q is not None:
        if any(q[key]!=k[key] for key in K_STATE):raise ValueError('K quote source clock/state differs')
        if q['native_valid']!='1' or io.integer(q['native_day'])!=io.integer(k['K_index']):
            raise ValueError('K quote native point does not match fixed K')
        if q['entry_date']!=old['entry_date'] or q['entry_index']!=old['entry_index']:
            raise ValueError('K quote original entry clock differs')
        for key in ('N_u','R0_points','cash_risk_unit','multiplier','entry_reference','stress_entry_fill',
                    'stress_entry_fee_per_lot','stress_entry_slippage_per_lot'):
            a,b=number(q,key),number(old,key)
            if a is not None and b is not None and not close(a,b):raise ValueError('K quote original entry cost differs '+key)


def write_table(out,name,fields,rows,artifacts):
    with io.csv_sink(out/name,fields,artifacts) as sink:sink.writerows(rows)


def actual(protocol_path,ready_path,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);began=time.monotonic();reads={};artifacts={}
    io.json_write(out/'started.json',dict(started_at=datetime.now(timezone.utc).isoformat(),automatic_retry=False,
        new_fit=0,new_cash=0,new_labels=0,new_CI=0,historical_END=END,current_day_close_dependency=False))
    try:
        pb=io.binding(protocol_path)
        if pb['sha256']!=PROTOCOL_SHA:raise ValueError('frozen630 changed')
        protocol=json.loads(Path(protocol_path).read_text());ready=json.loads(Path(ready_path).read_text())
        if ready['protocol']!=pb:raise ValueError('source-ready protocol differs')
        for b in ready['sources']+ready['helpers']:io.read_bound(b)
        tested=json.loads(io.read_bound(ready['fixture_receipt']['binding']))
        if tested['exit_code']!=0 or tested['source']!=ready['sources'][0] or tested['fixture']!=ready['sources'][1]:
            raise ValueError('tested source differs')
        family_doc=json.loads(io.read_bound(ready['family_coverage_addendum']))
        family_map=family_doc['families_by_scope']
        if [len(family_map[s]) for s in SCOPES]!=[95,38,57] or set(family_map['holdout_0'])&set(family_map['holdout_1']) or set(family_map['main'])!=set(family_map['holdout_0'])|set(family_map['holdout_1']):
            raise ValueError('complete fixed family inventory differs')
        io.json_write(out/'family_coverage_metadata.json',family_doc)
        cal_data=io.read_bound(protocol['calendar']);(out/'calendar.json').write_bytes(cal_data);calendar=json.loads(cal_data)['calendar']
        dates=[d for d in calendar if '2020-01-01'<=d<=END]
        if not dates or calendar!=sorted(set(calendar)):raise ValueError('original full calendar differs')
        io.read_bound(protocol['accepted629']);ref_data=io.read_bound(protocol['reference627_windows']);reference=json.loads(ref_data)
        (out/'reference627_windows.json').write_bytes(ref_data)
        source=protocol['bindings'];E=[];fixed_union={};seen=set();all_actions=set()
        with io.csv_sink(out/'E_slim_literals.csv.gz',E_FIELDS,artifacts) as sink:
            for row in io.csv_rows(source['E_linked'],E_FIELDS,reads,'E_linked'):
                key=(row['scope'],row['action_id'])
                if key in seen or row['scope'] not in SCOPES or row['family_id'] not in family_map[row['scope']]:raise ValueError('E duplicate/scope/family differs')
                seen.add(key);all_actions.add(row['action_id']);sink.writerow(row);E.append(row)
                if io.integer(row['m']) not in (0,1):raise ValueError('original admission flag differs')
                if flag(row['known']) and number(row,'Y') is None:raise ValueError('known original E nonfinite')
                if row['m']=='1':
                    if row['action_id'] in fixed_union:same_identity(fixed_union[row['action_id']],row)
                    fixed_union[row['action_id']]=row
        if len(E)!=216916 or len(all_actions)!=129851 or sum(r['scope']=='main' and r['m']=='1' for r in E)!=4365:
            raise ValueError('frozen full E/original main admission differs')
        io.progress(out,'selected_union_fixed_before_new_measurements',full_E=len(E),m1_union=len(fixed_union))
        K={};actions={};quotes={}
        with io.csv_sink(out/'selected_K_literals.csv.gz',io.K_FIELDS,artifacts) as sink:
            Kseen=set()
            for row in io.csv_rows(source['selected_K_literals'],io.K_FIELDS,reads,'selected_K_literals'):
                aid=row['action_id']
                if aid in Kseen:raise ValueError('K literal action duplicate')
                Kseen.add(aid)
                if aid in fixed_union:same_identity(fixed_union[aid],row);K[aid]=row;sink.writerow(row)
        if set(K)!=set(fixed_union):raise ValueError('m1 union K source incomplete')
        with io.csv_sink(out/'selected_actions_literals.csv.gz',ACTION_FIELDS,artifacts) as sink:
            n=0;ids=set()
            for row in io.csv_rows(source['actions'],ACTION_FIELDS,reads,'actions'):
                if io.integer(row['sequence_index'])!=n or row['action_id'] in ids:raise ValueError('original action sequence/domain differs')
                n+=1;ids.add(row['action_id']);aid=row['action_id']
                if aid in fixed_union:same_identity(fixed_union[aid],row);actions[aid]=row;sink.writerow(row)
                if n%250000==0:io.progress(out,'action_stream_progress',rows=n)
        if n!=1552456 or set(actions)!=set(fixed_union):raise ValueError('full action/m1 union source differs')
        del ids,Kseen,all_actions,seen
        with io.csv_sink(out/'selected_quote_literals.csv.gz',QUOTE_FIELDS,artifacts) as sink:
            ids=set()
            for row in io.csv_rows(source['K_quote_evidence'],QUOTE_FIELDS,reads,'K_quote_evidence'):
                aid=row['action_id']
                if aid in ids:raise ValueError('K evidence duplicate')
                ids.add(aid)
                if aid in fixed_union:same_identity(fixed_union[aid],row);quotes[aid]=row;sink.writerow(row)
        attributed=[];Egroups=defaultdict(list);Agroups=defaultdict(list)
        for row in E:
            Egroups[(row['scope'],row['u_date'])].append(row)
            if row['m']!='1':continue
            aid=row['action_id'];k=K[aid];old=actions[aid];q=quotes.get(aid)
            source_clock(row,k,old,q,END)
            a=dict(row,**attribute_action(row,k,old,q,END));attributed.append(a);Agroups[(row['scope'],row['u_date'])].append(a)
        io.progress(out,'accounting_measurement_complete',selected_scope_rows=len(attributed))
        attr_fields=E_FIELDS+[k for k in attributed[0] if k not in E_FIELDS]
        write_table(out,'action_accounting.csv.gz',attr_fields,attributed,artifacts)
        daily=[]
        for scope in SCOPES:
            for day in dates:daily.append(dict(scope=scope,u_date=day,**daily_accounting(Egroups[(scope,day)],Agroups[(scope,day)])))
        write_table(out,'daily.csv.gz',list(daily[0]),daily,artifacts)
        periods={**{('window',name):bounds for name,bounds in protocol['windows'].items()},
                 **{('era',name):bounds for name,bounds in protocol['eras'].items()},
                 **{('annual',str(y)):[str(y)+'-01-01',min(str(y)+'-12-31',END)] for y in range(2020,2027)}}
        reports={};type_rows=[];family_rows=[];daily_lookup={(d['scope'],d['u_date']):d for d in daily}
        for (kind,name),bounds in periods.items():
            reports[(kind,name)]={}
            for scope in SCOPES:
                ds=[d for d in daily if d['scope']==scope and bounds[0]<=d['u_date']<=bounds[1]]
                reports[(kind,name)][scope]=summarize(ds);n_days=len(ds)
                rs=[r for r in attributed if r['scope']==scope and bounds[0]<=r['u_date']<=bounds[1]]
                types=defaultdict(list)
                for row in rs:types[(row['branch'],row['exit_reason'],row['gap_state'])].append(row)
                for (branch,reason,gap),part in sorted(types.items()):
                    def weighted(key,predicate=lambda r:True):
                        return sum(r[key]/daily_lookup[(scope,r['u_date'])]['nI'] for r in part if r['known'] and predicate(r) and r[key] is not None)/n_days if n_days else 0.
                    type_rows.append(dict(period_kind=kind,period=name,scope=scope,branch=branch,exit_reason=reason,gap_state=gap,
                        source_dates=n_days,count=len(part),known=sum(r['known'] for r in part),unknown=sum(not r['known'] for r in part),
                        J_complete=sum(r['J'] for r in part),Y_contribution=weighted('YK'),G_J_contribution=weighted('G',lambda r:r['J']),
                        Fee_J_contribution=weighted('Fee',lambda r:r['J']),Slip_J_contribution=weighted('Slip',lambda r:r['J']),
                        identified_gap_overshoot_contribution=(weighted('gap_overshoot_R') if any(r['gap_overshoot_R'] is not None for r in part) else None)))
                if kind=='annual':
                    by_family=defaultdict(list)
                    for r in rs:by_family[r['family_id']].append(r)
                    for family in family_map[scope]:
                        part=by_family[family]
                        family_rows.append(dict(scope=scope,year=name,family_id=family,selected=len(part),
                            known=sum(r['known'] for r in part),unknown=sum(not r['known'] for r in part),
                            J_complete=sum(r['J'] for r in part),H_complete=sum(r['H'] for r in part),
                            A_I_contribution=sum(r['YK']/daily_lookup[(scope,r['u_date'])]['nI'] for r in part if r['known'])/n_days if n_days else 0.))
        windows={s+'/'+name:reports[('window',name)][s] for name in protocol['windows'] for s in SCOPES}
        eras={s+'/'+name:reports[('era',name)][s] for name in protocol['eras'] for s in SCOPES}
        annual={s+'/'+str(y):reports[('annual',str(y))][s] for y in range(2020,2027) for s in SCOPES}
        for key,value in windows.items():
            if not close(value['A_I'],reference[key]['A_I']['mean']):raise ValueError('original627 A_I not reproduced '+key)
        io.json_write(out/'windows.json',windows);io.json_write(out/'eras.json',eras);io.json_write(out/'annual.json',annual)
        write_table(out,'type_contributions.csv.gz',list(type_rows[0]),type_rows,artifacts)
        write_table(out,'family_year_including_zero.csv.gz',list(family_rows[0]),family_rows,artifacts)
        failures=sum(r['component_check_failures'] for r in attributed)
        identities=dict(original_main_admission_preserved=4365,full_E_rows=len(E),m1_union=len(fixed_union),
            m1_scope_rows=len(attributed),same629_A_I=True,family_counts={s:len(family_map[s]) for s in SCOPES},
            component_measurement_check_failures=failures,
            max_scaled_component_residual=max(r['max_scaled_component_residual'] for r in attributed),
            max_daily_accounting_residual=max(abs(d['accounting_identity_residual']) for d in daily),
            max_daily_bridge_residual=max(abs(d['bridge_identity_residual']) for d in daily),
            exact_components_for_all_known=all(r['J'] for r in attributed if r['known']) and failures==0,
            residual_contribution_retained=True,full_market_R_not_reidentified=True,tolerance=TOL)
        if any(not close(d['accounting_identity_residual'],0.) or not close(d['bridge_identity_residual'],0.) for d in daily):
            raise ValueError('same denominator accounting/target bridge identity failed')
        io.json_write(out/'identities.json',identities);io.json_write(out/'input_read_receipts.json',reads)
        summary=dict(status='completed',historical_END=END,current_day_close_dependency=False,new_fit=0,new_cash=0,
            new_labels=0,new_CI=0,new_financial_gate=0,SQL=0,native_reads=0,score_model_COMMON_reads=0,
            selected_scope_rows=len(attributed),selected_union=len(fixed_union),component_states=dict(Counter(r['component_state'] for r in attributed)),
            J_complete=sum(r['J'] for r in attributed),J_incomplete_known=sum(r['known'] and not r['J'] for r in attributed),
            H_complete=sum(r['H'] for r in attributed),H_incomplete_known=sum(r['known'] and not r['H'] for r in attributed),
            original_K_unknown=sum(not r['known'] for r in attributed),component_measurement_failures=failures,
            accounting_valid=failures==0,financial_metrics='N/A: unchanged fixed-policy accounting, no new cash result',
            cumulative_fit=551,cumulative_completed_cash=290,old_partial_cash=1,goal_complete=False,production_qualified=False,
            interpretation='Partial identification/J-H leftovers explicit; no causal zero-cost cash claim or post-result rescue.')
        io.json_write(out/'summary.json',summary)
        terminal=dict(status='completed',exit_code=0,elapsed_seconds=time.monotonic()-began,new_fit=0,new_cash=0,new_labels=0,
            ended_at=datetime.now(timezone.utc).isoformat(),automatic_retry=False)
        io.json_write(out/'terminal.json',terminal)
        for p in sorted(out.iterdir()):
            if p.is_file() and p.name not in artifacts:artifacts[p.name]=io.binding(p)
        io.json_write(out/'manifest.json',dict(schema='stage632_fixed_K_accounting_v1',status='completed',protocol=pb,
            source_ready=io.binding(ready_path),source_bundle=ready['sources'],helpers=ready['helpers'],
            family_coverage_addendum=ready['family_coverage_addendum'],inputs=source,input_read_receipts=reads,
            artifacts=artifacts,counters=protocol['counters_before'],new_fit=0,new_cash=0,new_labels=0,new_CI=0,
            new_financial_gate=0,historical_END=END,current_day_close_dependency=False,production_qualified=False))
        return terminal
    except BaseException as exc:
        terminal=dict(status='failed',exit_code=1,elapsed_seconds=time.monotonic()-began,error=repr(exc),
            traceback=traceback.format_exc(),automatic_retry=False,new_fit=0,new_cash=0,new_labels=0)
        io.json_write(out/'terminal.json',terminal);io.json_write(out/'input_read_receipts.json',reads);raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--protocol',required=True)
    parser.add_argument('--source-ready',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();print(json.dumps(actual(args.protocol,args.source_ready,args.output),ensure_ascii=False))
