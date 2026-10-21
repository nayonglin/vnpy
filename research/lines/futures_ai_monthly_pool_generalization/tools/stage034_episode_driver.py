"""Bounded reference entry-episode driver, NOT full monthly source/live strategy.

External source calendar/asof targets/anchors/economics are declared inputs,
not certified by this module. No fresh entries after episode exit. Portfolio
rules excluded. Roll reference supports close-first only. All branches retained.
"""
from copy import deepcopy
from datetime import date
import math

import pandas as pd

from stage018_finite_path_ledger import execution
from stage012_c2_reference_frontier import classify_daily
from stage024_fixed_r_accounting import FixedRiskLedger, Fill, Economics
from stage026_daily_exit_adapter import decide_daily_exit
from stage031_roll_admissibility import advance_delay, evaluate_roll


def _unknown(branch,reason):
    branch['status']='trajectory_unknown';branch['unknown_reasons'].append(reason)
    return branch


def _record(case,day,contract):
    return case['sessions'].get(day,{}).get('contracts',{}).get(contract)


def _validated_record(case,day,index,contract):
    r=_record(case,day,contract)
    if r is None:return None
    expected=case['calendar'][index-40:index+1] if index>=40 else []
    if len(expected)!=41 or r.get('history_dates')!=expected:
        raise ValueError('history_calendar_not_exact_past_AM41')
    if len(r.get('history',[]))!=41:raise ValueError('requires_AM41')
    if r['history'][-1]!=r['bar']:raise ValueError('current_bar_history_mismatch')
    for bar in r['history']:
        o,h,l,c=(float(bar[k]) for k in ('open','high','low','close'))
        if not all(math.isfinite(v) and v>0 for v in (o,h,l,c)) or l>min(o,c) or h<max(o,c):
            raise ValueError('invalid_daily_OHLC')
    return r


def _anchor(record):
    anchor=None if record is None else record.get('anchor')
    if not anchor or not anchor.get('evidence_id'):return None
    if isinstance(anchor['price'],bool):raise ValueError('invalid_anchor_numeric_price')
    p=float(anchor['price'])
    if not math.isfinite(p) or p<=0 or not math.isclose(p,float(record['bar']['open']),abs_tol=1e-9,rel_tol=0):
        raise ValueError('anchor_daily_open_mismatch')
    stamp=pd.Timestamp(anchor['execution_datetime'])
    if pd.isna(stamp):raise ValueError('invalid_anchor_timestamp')
    return p


def _fill(branch,kind,day,contract,qty,record,roll=False):
    price=_anchor(record)
    if price is None:return False
    branch['book'].apply(Fill(kind,contract,day,price,qty,Economics(**record['economics']),
                              record.get('extra_slippage_price'),roll))
    return True


def _enter_state(branch,plan,price):
    branch['state']=dict(direction=branch['direction'],qty=plan['qty'],entry_price=price,
                         stop_price=plan['stop_price'],highest_price=plan['signal_high'],lowest_price=plan['signal_low'],
                         max_profit_pct=0.,prev2day_stop_price=None,rsi_partial_exit_done=False,
                         bars_since_entry=0,contract=plan['contract'],target_contract=plan['contract'],pending_roll=False)
    branch['entry_signal_day']=plan['signal_day'];branch['delay']=None


def _pending_fills(case,branch,day,index):
    plan=branch['pending'];new_record=None
    if plan is None:return new_record
    contract=plan['contract'];r=_validated_record(case,day,index,contract)
    if plan['kind']=='open':
        if not _fill(branch,'open',day,contract,plan['qty'],r):
            _unknown(branch,'entry_anchor_or_bar_missing');return None
        _enter_state(branch,plan,_anchor(r));branch['pending']=None;new_record=r
    elif plan['kind']=='reduce':
        if not _fill(branch,'close',day,contract,plan['reduce_qty'],r):
            _unknown(branch,'pending_close_anchor_or_bar_missing');return None
        branch['state']['qty']=branch['book'].remaining
        if 'rsi_partial_exit' in plan['reason']:branch['state']['rsi_partial_exit_done']=True
        if not branch['book'].remaining:branch['state']=None
        branch['pending']=None
    elif plan['kind']=='roll':
        if not _fill(branch,'close',day,contract,branch['book'].remaining,r,True):
            _unknown(branch,'old_roll_close_anchor_missing');return None
        branch['state']=None
        if plan.get('unknown_reopen'):
            _unknown(branch,'roll_reopen_admissibility_unknown_after_old_close');return None
        new=plan.get('new')
        if new is None:branch['pending']=None;return None
        nr=_validated_record(case,day,index,new['contract'])
        if _anchor(nr) is None:
            _unknown(branch,'new_roll_anchor_missing_after_old_close');return None
        if pd.Timestamp(nr['anchor']['execution_datetime'])<pd.Timestamp(r['anchor']['execution_datetime']):
            _unknown(branch,'unsupported_new_roll_open_precedes_old_close');return None
        if not _fill(branch,'open',day,new['contract'],new['qty'],nr,True):
            _unknown(branch,'new_roll_open_unresolved');return None
        _enter_state(branch,new,_anchor(nr));branch['pending']=None;new_record=nr
    else:raise ValueError('invalid_pending_kind')
    return new_record


def _c2(branch,record,day):
    s=branch['state'];e=float(s['entry_price']);sign=1 if s['direction']=='long' else -1
    risk=sign*(e-float(s['stop_price']))
    if risk<=0:return [_unknown(branch,'new_entry_signed_risk_invalid')]
    if record.get('c2_guard_tick') is None:return [_unknown(branch,'configured_c2_guard_tick_missing')]
    if isinstance(record['c2_guard_tick'],bool):raise ValueError('invalid_configured_c2_guard_tick')
    guard=float(record['c2_guard_tick'])
    if not math.isfinite(guard) or guard<=0:raise ValueError('invalid_configured_c2_guard_tick')
    guard=max(guard,1e-9)
    if risk<guard:branch['day_c2']='guard_inactive';return [branch]
    paths=record.get('minute_paths')
    if paths is None:
        if record.get('daily_bar_complete') is not True:
            return [_unknown(branch,'entry_session_OHLC_completeness_unknown')]
        b=record['bar'];case=classify_daily(s['direction'],e,b['high'],b['low'],b['close'],risk)['daily_case']
        if case in ('neither','confirm_only'):
            branch['day_c2']='expired' if case=='neither' else 'confirmed';return [branch]
        return [_unknown(branch,'c2_order_or_fill_unknown_without_minute_path')]
    if not paths or not record.get('minute_evidence_id'):raise ValueError('minute_path_evidence_missing')
    outputs=[]
    for choice,path in enumerate(paths):
        if not path:raise ValueError('empty_minute_path')
        frame=pd.DataFrame(path)
        values=frame[['open','high','low','close']].astype(float)
        if not all(math.isfinite(x) and x>0 for x in values.to_numpy().flat):raise ValueError('minute_OHLC_invalid')
        if (values.low>values[['open','close']].min(axis=1)).any() or (values.high<values[['open','close']].max(axis=1)).any():
            raise ValueError('minute_OHLC_geometry')
        agg=[float(frame.open.iloc[0]),float(frame.high.max()),float(frame.low.min()),float(frame.close.iloc[-1])]
        if not all(math.isclose(a,float(record['bar'][k]),rel_tol=0,abs_tol=1e-8) for a,k in zip(agg,('open','high','low','close'))):
            raise ValueError('minute_daily_aggregate_mismatch')
        out=deepcopy(branch);out['choices'].append(dict(day=day,choice=choice,evidence_id=record['minute_evidence_id']))
        hit,note=execution.first_stop(frame,e-sign*risk,e+sign*risk,long=sign==1)
        if hit>=0:
            try:price,fill_note=execution.stop_fill(frame.iloc[hit],e-sign*risk,float(record['economics']['tick']),buy=sign==-1)
            except ValueError:
                outputs.append(_unknown(out,'c2_fill_unreachable'));continue
            out['book'].apply(Fill('close',s['contract'],day,price,s['qty'],Economics(**record['economics']),
                                    record.get('extra_slippage_price')))
            out['state']=None;out['day_c2']='stopped:'+note+':'+fill_note
        else:out['day_c2']='expired' if note=='no_trigger' else 'confirmed'
        outputs.append(out)
    return outputs


def _daily_decision(case,branch,day,index):
    if branch['status']!='known' or branch['state'] is None:return
    s=branch['state'];r=_validated_record(case,day,index,s['contract'])
    if r is None:_unknown(branch,'holding_daily_bar_missing');return
    target=case['sessions'][day].get('target_contract')
    if not target:_unknown(branch,'asof_target_contract_missing');return
    if target!=s['contract']:
        branch['delay']=advance_delay(branch['delay'],target,day)
        if branch['delay']['due']:
            nr=_validated_record(case,day,index,target)
            plan=dict(kind='roll',contract=s['contract'],new=None,unknown_reopen=nr is None)
            if nr is not None:
                admissible=evaluate_roll(s['direction'],nr['history'],nr['history_dates'],day,contract=target)
                if admissible['allowed']:
                    qty=case['sessions'][day].get('roll_qty')
                    if not isinstance(qty,int) or isinstance(qty,bool) or qty<1:
                        plan['unknown_reopen']=True
                    else:plan['new']=dict(contract=target,qty=qty,stop_price=admissible['signal_stop'],
                                           signal_high=nr['bar']['high'],signal_low=nr['bar']['low'],signal_day=day)
            branch['pending']=plan;return
    else:branch['delay']=None
    s['bars_since_entry']=index-case['calendar'].index(branch['entry_signal_day'])
    # Source delay waiting uses the held contract for normal daily exits.
    s['target_contract']=s['contract'];s['pending_roll']=False
    decision=decide_daily_exit(state=s,history=[{k:bar[k] for k in ('open','high','low','close')} for bar in r['history']],
                               bar={k:r['bar'][k] for k in ('open','high','low','close')},
                               rsi_value=r['rsi_value'],ma_long_prev_value=r['ma_long_prev_value'])
    branch['state']=decision['proposed_state']
    # RSI completion is an execution commit, not the proposed decision flag.
    branch['state']['rsi_partial_exit_done']=s['rsi_partial_exit_done']
    if decision['request'] is not None:branch['pending']=dict(kind='reduce',**decision['request'])


def _snapshot(case,branch,day):
    book=branch['book']
    if book.risk_currency is None:return None
    r=_record(case,day,book.contract) if book.remaining else None
    snapshot=book.mark({book.contract:r['bar']['close']} if r else {})
    if branch['status']!='known':
        snapshot['recorded_legs_only']=True
        snapshot['recorded_leg_realized_gross']=snapshot.pop('realized_gross')
        snapshot['recorded_remaining_qty']=snapshot.pop('remaining_qty')
        for key in ('unrealized_gross','gross','net','gross_r','net_r'):
            snapshot[key]=None
        snapshot['status']='trajectory_unknown_recorded_legs_only'
    return snapshot


def run_episode(case):
    """Return reference paths, known economic legs, fixed clock and maturity flags."""
    case=deepcopy(case)
    calendar=case['calendar']
    if not calendar or calendar!=sorted(calendar) or len(calendar)!=len(set(calendar)):
        raise ValueError('source_calendar_not_strict')
    for day in calendar:
        if date.fromisoformat(day).isoformat()!=day:raise ValueError('calendar_not_ISO')
    horizon=case['horizon'];mode=case['terminal_mode']
    if isinstance(horizon,bool) or not isinstance(horizon,int) or not 1<=horizon<=60:
        raise ValueError('invalid_horizon')
    if mode not in ('mtm','exit_next_open'):raise ValueError('invalid_terminal_mode')
    start=calendar.index(case['signal_day']);end=start+horizon
    observed=case['observed_through'];date.fromisoformat(observed)
    if observed<case['signal_day']:raise ValueError('observation_before_signal')
    if any(day>observed for day in case['sessions']):raise ValueError('session_after_observed_through')
    if any(day not in calendar for day in case['sessions']):raise ValueError('session_outside_source_calendar')
    initial=case['initial'];qty=initial['qty']
    if not isinstance(qty,int) or isinstance(qty,bool) or qty<1:raise ValueError('invalid_initial_integer_qty')
    branches=[dict(status='known',direction=initial['direction'],unknown_reasons=[],state=None,
                   book=FixedRiskLedger(initial['direction'],initial['stop_price']),delay=None,trace=[],choices=[],
                   entry_signal_day=case['signal_day'],pending=dict(kind='open',contract=initial['contract'],qty=qty,
                       stop_price=initial['stop_price'],signal_high=initial['signal_high'],signal_low=initial['signal_low'],signal_day=case['signal_day']))]
    finish=end+(mode=='exit_next_open')
    for index in range(start+1,min(finish,len(calendar)-1)+1):
        day=calendar[index]
        if day>observed:break
        expanded=[]
        for branch in branches:
            branch['day_c2']=None
            if branch['status']=='known':
                try:new=_pending_fills(case,branch,day,index)
                except ValueError as exc:
                    if str(exc)=='wrong_side_initial_risk':_unknown(branch,'initial_entry_signed_risk_invalid');new=None
                    else:raise
                paths=_c2(branch,new,day) if new is not None and branch['status']=='known' else [branch]
            else:paths=[branch]
            for out in paths:
                if index<=end:_daily_decision(case,out,day,index)
                if mode=='exit_next_open' and index==end and out['status']=='known':
                    if out['book'].remaining:
                        out['pending']=dict(kind='reduce',contract=out['book'].contract,
                                            reduce_qty=out['book'].remaining,reason='research_horizon_liquidation')
                    elif out['pending'] is not None:
                        _unknown(out,'horizon_pending_reopen_not_flat_terminal')
                snap=_snapshot(case,out,day)
                out['trace'].append(dict(day=day,status=out['status'],pending=deepcopy(out['pending']),
                                         actual_qty=out['book'].remaining if out['status']=='known' else None,c2_event=out['day_c2'],
                                         state=deepcopy(out['state']),snapshot=snap))
                expanded.append(out)
        if len(expanded)>256:raise ValueError('scenario_budget_exceeded_no_truncation')
        branches=expanded
    target=calendar[end] if end<len(calendar) else None
    exit_day=calendar[end+1] if end+1<len(calendar) else None
    maturity=target is not None and observed>=target
    if mode=='exit_next_open':maturity=maturity and exit_day is not None and observed>=exit_day
    rows=[]
    for path_id,b in enumerate(branches):
        snap=b['trace'][-1]['snapshot'] if b['trace'] else None
        identified=b['status']=='known' and snap is not None and snap['net_r'] is not None
        rows.append(dict(path_id=path_id,status=b['status'],unknown_reasons=b['unknown_reasons'],
                         trace=b['trace'],choices=b['choices'],snapshot=snap,pending=b['pending'],tape=b['book'].tape,
                         reference_net_r=snap['net_r'] if identified else None,
                         reference_value_mature=bool(maturity and identified),training_eligible=False))
    return dict(signal_day=case['signal_day'],horizon=horizon,terminal_mode=mode,target_day=target,
                exit_day_required=exit_day if mode=='exit_next_open' else None,
                maturity_clock_reached=bool(maturity),paths=rows,training_eligible=False,
                complete_monthly_source=False,source_scope='isolated_entry_episode_with_external_targets_and_reference_anchors',
                evidence_validity='declared_inputs_not_certified_here',max_paths=256)
