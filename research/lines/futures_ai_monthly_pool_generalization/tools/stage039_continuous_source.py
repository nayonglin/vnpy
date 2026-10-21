"""Continuous isolated monthly research source, not a formal strategy/label.

Consumes externally identified daily fresh signals and declared reference
anchors. Fixed-risk books reset only for new ordinary fresh entries; roll keeps
its episode denominator. Unknown trajectories are sticky across future entries.
"""
from copy import deepcopy
from datetime import date
import math
from stage024_fixed_r_accounting import FixedRiskLedger
from stage034_episode_driver import (_validated_record,_pending_fills,_c2,_daily_decision,_snapshot,_unknown)


def _iso(value):
    if not isinstance(value,str):raise ValueError('invalid_ISO_day')
    try:parsed=date.fromisoformat(value)
    except ValueError:raise ValueError('invalid_ISO_day') from None
    if parsed.isoformat()!=value:raise ValueError('invalid_ISO_day')
    return value


def _positive(value):
    if isinstance(value,bool):raise ValueError('boolean_numeric_input')
    try:number=float(value)
    except (TypeError,ValueError):raise ValueError('invalid_numeric_input') from None
    if not math.isfinite(number) or number<=0:raise ValueError('nonpositive_or_nonfinite_input')
    return number


def _finish_episode(branch,day):
    if branch['status']!='known' or branch['state'] is not None or branch['pending'] is not None:return
    book=branch['book']
    if book is not None and book.risk_currency is not None and not book.remaining:
        branch['completed'].append(dict(episode_id=branch['episode_id'],direction=branch['direction'],
                                       signal_day=branch['episode_signal_day'],finished_day=day,book=book))
        branch['book']=None;branch['episode_id']=None;branch['episode_signal_day']=None;branch['delay']=None


def _fresh(case,branch,day,index):
    if branch['status']!='known':return
    session=case['sessions'].get(day)
    if session is None:_unknown(branch,'continuous_source_session_missing');return
    # Missing signals matter even while a position is held: the source identity
    # requires explicit observation, not a default absence of opportunities.
    if 'fresh_signal' not in session:_unknown(branch,'daily_fresh_signal_observation_missing');return
    signal=session['fresh_signal']
    if signal is None:return
    if not isinstance(signal,dict):raise ValueError('invalid_fresh_signal')
    required=('direction','contract','qty','stop_price','signal_high','signal_low')
    if any(k not in signal for k in required):raise ValueError('missing_fresh_signal_fields')
    if signal['direction'] not in ('long','short'):raise ValueError('invalid_fresh_direction')
    if not isinstance(signal['contract'],str) or not signal['contract'] or signal['contract']!=session.get('target_contract'):
        raise ValueError('fresh_contract_target_mismatch')
    if type(signal['qty']) is not int or signal['qty']<1:raise ValueError('invalid_fresh_integer_qty')
    for key in ('stop_price','signal_high','signal_low'):_positive(signal[key])
    if signal['signal_high']<signal['signal_low']:raise ValueError('invalid_signal_extremes')
    if branch['state'] is not None or branch['pending'] is not None:return
    record=_validated_record(case,day,index,signal['contract'])
    if record is None:_unknown(branch,'fresh_signal_daily_history_missing');return
    for key,barkey in [('signal_high','high'),('signal_low','low')]:
        if not math.isclose(float(signal[key]),float(record['bar'][barkey]),rel_tol=0,abs_tol=1e-9):raise ValueError('fresh_signal_bar_extremes_mismatch')
    branch['direction']=signal['direction'];branch['book']=FixedRiskLedger(signal['direction'],signal['stop_price'])
    branch['episode_id']=branch['next_episode_id'];branch['next_episode_id']+=1
    branch['entry_signal_day']=day;branch['episode_signal_day']=day
    branch['pending']=dict(kind='open',contract=signal['contract'],qty=signal['qty'],stop_price=signal['stop_price'],
                           signal_high=signal['signal_high'],signal_low=signal['signal_low'],signal_day=day)
    branch['delay']=None


def _totals(case,branch,day):
    if branch['status']!='known':return None,None
    snapshots=[e['book'].mark({}) for e in branch['completed']]
    if branch['book'] is not None and branch['book'].risk_currency is not None:
        snapshots.append(_snapshot(case,branch,day))
    def total(key):
        values=[s[key] for s in snapshots]
        return None if any(v is None for v in values) else sum(values)
    return total('gross_r'),total('net_r')


def _episodes(case,branch,day):
    rows=[]
    for e in branch['completed']:
        rows.append(dict(episode_id=e['episode_id'],direction=e['direction'],signal_day=e['signal_day'],
                         finished_day=e['finished_day'],snapshot=e['book'].mark({}),tape=deepcopy(e['book'].tape)))
    if branch['book'] is not None:
        rows.append(dict(episode_id=branch['episode_id'],direction=branch['direction'],signal_day=branch['episode_signal_day'],
                         finished_day=None,snapshot=_snapshot(case,branch,day),tape=deepcopy(branch['book'].tape)))
    return rows


def run_continuous_source(case):
    """Run every source close; preserve predeclared evaluation rows and paths.

    Daily anchors, economics and fresh signals are external research assumptions.
    This API provides neither actual anchor nor original 108-feature qualification.
    """
    case=deepcopy(case);calendar=case['calendar']
    if not isinstance(calendar,list) or not calendar or calendar!=sorted(set(calendar)):raise ValueError('source_calendar_not_strict')
    for day in calendar:_iso(day)
    start=_iso(case['start_day']);observed=_iso(case['observed_through'])
    if start not in calendar or observed<start:raise ValueError('invalid_source_start_or_observation')
    if not isinstance(case['sessions'],dict):raise ValueError('invalid_source_sessions')
    if any(day not in calendar or _iso(day)>observed for day in case['sessions']):raise ValueError('session_outside_calendar_or_after_observation')
    evaluation=case.get('monthly_eval_days',[])
    if not isinstance(evaluation,list) or evaluation!=sorted(set(evaluation)) or any(_iso(day) not in calendar or day<start for day in evaluation):
        raise ValueError('invalid_monthly_evaluation_calendar')
    branches=[dict(status='known',direction=None,unknown_reasons=[],state=None,book=None,pending=None,
                   completed=[],episode_id=None,next_episode_id=0,delay=None,entry_signal_day=None,episode_signal_day=None,trace=[],choices=[],
                   last_gross_r=0.,last_net_r=0.)]
    processed=[(index,day) for index,day in enumerate(calendar) if start<=day<=observed]
    for index,day in processed:
        expanded=[]
        for branch in branches:
            branch['day_c2']=None
            if branch['status']=='known':
                if day not in case['sessions']:_unknown(branch,'continuous_source_session_missing');new=None
                elif branch['book'] is not None:
                    try:new=_pending_fills(case,branch,day,index)
                    except ValueError as exc:
                        if str(exc)=='wrong_side_initial_risk':_unknown(branch,'initial_entry_signed_risk_invalid');new=None
                        else:raise
                else:new=None
                paths=_c2(branch,new,day) if new is not None and branch['status']=='known' else [branch]
            else:paths=[branch]
            for out in paths:
                _daily_decision(case,out,day,index)
                _finish_episode(out,day)
                _fresh(case,out,day,index)
                gross,net=_totals(case,out,day)
                gross_delta=None if gross is None or out['last_gross_r'] is None else gross-out['last_gross_r']
                net_delta=None if net is None or out['last_net_r'] is None else net-out['last_net_r']
                out['last_gross_r'],out['last_net_r']=gross,net
                out['trace'].append(dict(day=day,status=out['status'],unknown_reasons=deepcopy(out['unknown_reasons']),
                                         pending=deepcopy(out['pending']),state=deepcopy(out['state']),c2_event=out['day_c2'],
                                         actual_qty=(out['book'].remaining if out['book'] is not None else 0) if out['status']=='known' else None,
                                         episode_count=len(out['completed'])+(out['book'] is not None),
                                         cumulative_gross_r=gross,cumulative_net_r=net,delta_gross_r=gross_delta,delta_net_r=net_delta))
                expanded.append(out)
        if len(expanded)>256:raise ValueError('scenario_budget_exceeded_no_truncation')
        branches=expanded
    finalday=processed[-1][1]
    paths=[]
    for path_id,b in enumerate(branches):
        byday={r['day']:r for r in b['trace']};monthly=[]
        for day in evaluation:
            row=byday.get(day)
            monthly.append(dict(eval_day=day,observed=row is not None,status='not_yet_observed' if row is None else row['status'],
                                cumulative_gross_r=None if row is None else row['cumulative_gross_r'],
                                cumulative_net_r=None if row is None else row['cumulative_net_r'],training_eligible=False))
        paths.append(dict(path_id=path_id,status=b['status'],unknown_reasons=b['unknown_reasons'],choices=b['choices'],trace=b['trace'],
                          pending=b['pending'],episodes=_episodes(case,b,finalday),monthly_evaluations=monthly,
                          cumulative_gross_r=b['last_gross_r'],cumulative_net_r=b['last_net_r'],training_eligible=False))
    return dict(paths=paths,start_day=start,observed_through=observed,monthly_eval_days=evaluation,
                source_scope='single_product_continuous_external_fresh_reference_anchors_fixed_initial_R_each_fresh_episode',
                complete_formal_source=False,training_eligible=False,net_60d_training_labels=False,
                evidence_validity='external_declared_inputs_not_certified_here',max_paths=256,
                excluded=['shared_cash','account_sizing','portfolio_slots_heat_and_risk_rules','original_AI_eligibility_loop'],
                initial_R_policy='new ordinary fresh entry new book; rollover continues current book')
