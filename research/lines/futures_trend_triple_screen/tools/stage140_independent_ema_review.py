"""EMA identity/evidence adapter over pinned030/033/095 accounting algorithms."""
from __future__ import annotations
import ast
from collections import defaultdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import tempfile

import stage140_ema_checkpoint as checkpoint
from stage140_ema_checkpoint import BoundAsset

TOOLS=Path(__file__).resolve().parent
CONDITIONAL='stage127_ema_limit_initial_primary'


def _algorithms():
    # 095's source loader pins every extracted original source; no old audit/main.
    import stage095_independent_off_account_review as inherited
    import numpy as np
    import pandas as pd
    base=inherited.module('stage030_independent_ordered_account_review.py')
    base.CONDITIONAL=CONDITIONAL
    a33=inherited.module('stage033_independent_checkpoint_account_review.py')
    original=TOOLS/'stage095_independent_off_account_review.py'
    expected='be688b02314b7c9d5a23d21f3cf0575e9d66a6e1f7a8a5b8c80ebcd627426b6f'
    if checkpoint.asset(original).sha256!=expected:raise ValueError('ema_original_accounting_source_changed')
    tree=ast.parse(original.read_bytes());audit=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='audit')
    body=next(n for n in audit.body if isinstance(n,ast.Try)).body
    # Exact original statements from params/sizes through independent metrics.
    first=next(i for i,n in enumerate(body)if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='params'for t in n.targets))
    last=next(i for i,n in enumerate(body)if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='candidates'for t in n.targets))
    arithmetic=compile(ast.Module(body=body[first:last],type_ignores=[]),str(original),'exec')
    return inherited,base,a33,np,pd,arithmetic


def _ema_number(value,name,*,minimum=None,positive=False):
    if isinstance(value,bool)or not isinstance(value,(int,float))or not math.isfinite(value):
        raise ValueError('ema_invalid_number:'+name)
    if (positive and value<=0)or(minimum is not None and value<minimum):raise ValueError('ema_number_bound:'+name)
    return float(value)


def _ema_integer(value,name,minimum=0):
    if type(value)is not int or value<minimum:raise ValueError('ema_invalid_integer:'+name)
    return value


def _ema_text(value,name):
    if not isinstance(value,str)or not value:raise ValueError('ema_missing_identity:'+name)
    return value


def _ema_day(value,name):
    _ema_text(value,name)
    if len(value)!=10 or datetime.strptime(value,'%Y-%m-%d').date().isoformat()!=value:
        raise ValueError('ema_invalid_day:'+name)
    return value


def _ema_equal(actual,expected,name,base):
    if expected is None:
        if actual is not None:raise ValueError('ema_expected_NA:'+name)
    elif isinstance(expected,bool):
        if actual is not expected:raise ValueError('ema_boolean_mismatch:'+name)
    elif isinstance(expected,(int,float)):
        base.close(_ema_number(actual,name),expected,'EMA '+name)
    elif type(actual)is not type(expected)or actual!=expected:raise ValueError('ema_binding_mismatch:'+name)


def _ema_budgets(payload,base):
    """Independently evaluate the fixed127 scalar bounds; never rerun sizing."""
    ema=payload['ema'];params=payload['parameters'];settings=payload['actual'][0]['actual']
    prefix='ema_limit_final_budget_';decisions={};intents={}
    for row in ema['decision']:
        if row['mechanism_id']!=checkpoint.MECHANISM_ID:raise ValueError('ema_decision_mechanism')
        key=(_ema_day(row['date'],'decision.date'),_ema_text(row['product'],'decision.product'),row['contract'])
        if key in decisions:raise ValueError('ema_duplicate_decision')
        decisions[key]=row
        if row['decision']not in ('intent','waiting','blocked'):raise ValueError('ema_unknown_decision')
        intent=row['intent_id']
        if intent is not None:
            _ema_text(intent,'decision.intent_id');_ema_text(row['setup_id'],'decision.setup_id')
            if row['decision']!='intent'or row['signal']not in ('long_triple_screen','short_triple_screen')or intent in intents:
                raise ValueError('ema_decision_intent_not_unique')
            intents[intent]=row
        elif row['decision']=='intent':raise ValueError('ema_decision_intent_missing')
    budgets={};gross={};clusters={};last_rank={}
    margin_map={}
    for item in settings.get('margin_ratio_overrides','').split(','):
        if item.strip():key,value=item.split('=');margin_map[key]=float(value)
    for row in ema['budget']:
        if row['mechanism_id']!=checkpoint.MECHANISM_ID:raise ValueError('ema_budget_mechanism')
        day=_ema_day(row['signal_day'],'budget.signal_day');product=_ema_text(row['product_vt_symbol'],'budget.product')
        contract=_ema_text(row['contract_vt_symbol'],'budget.contract');key=(day,product,contract)
        if key in budgets or key not in decisions:raise ValueError('ema_budget_decision_not_unique')
        decision=decisions[key]
        if decision['intent_id']is None or decision['decision']!='intent':raise ValueError('ema_budget_without_intent')
        direction=1 if row['direction']=='long'else(-1 if row['direction']=='short'else None)
        if direction is None or decision['signal']!=('long_triple_screen'if direction==1 else'short_triple_screen'):
            raise ValueError('ema_budget_direction')
        values={k[len(prefix):]:v for k,v in row.items()if k.startswith(prefix)}
        for name,value in values.items():_ema_equal(decision[prefix+name],value,'decision_budget.'+name,base)
        def number(name,positive=False):return _ema_number(values[name],'budget.'+name,minimum=0,positive=positive)
        def integer(name,minimum=0):return _ema_integer(values[name],'budget.'+name,minimum)
        a=integer('volume_before',1);q=integer('volume_after');minimum=integer('min_position_size',1);maximum=integer('max_position_size',1)
        if minimum>maximum:raise ValueError('ema_budget_position_bounds')
        rank=values['original_rank']
        if rank is not None:_ema_integer(rank,'budget.original_rank')
        ordered_rank=rank or math.inf
        if ordered_rank<last_rank.get(day,-math.inf):raise ValueError('ema_budget_rank_order')
        last_rank[day]=ordered_rank
        _ema_equal(decision['selection_pairwise_rank'],rank,'decision.rank',base)
        T=number('trigger',True);S=number('stop_price',True);size=number('contract_size',True);tick=number('pricetick',True)
        ratio=number('margin_ratio',True);rho=number('risk_per_contract',True);margin=number('margin_per_contract',True)
        R=number('risk_amount');L=number('limited_balance');K=number('single_trade_capital_limit');E=number('equity_u',True);B=number('reserved_margin_before')
        if direction*(T-S)<=0:raise ValueError('ema_budget_stop_side')
        for name,expected in (('risk_per_contract',max(direction*(T-S)*size,max(tick*size,1.))),('margin_per_contract',T*size*ratio),
                ('contract_size',params['contract_sizes'][contract]),('pricetick',params['priceticks'][contract]),
                ('margin_ratio',margin_map.get(contract,float(settings.get('default_margin_ratio',.1))))):
            _ema_equal(values[name],expected,'budget.'+name,base)
        for name,expected in (('ema_limit_signal_day',day),('ema_limit_trigger_price',T),('ema_limit_contract_size',size),
                ('ema_limit_pricetick',tick),('ema_limit_budget_equity_u',E),('ema_limit_min_position_size',minimum),('ema_limit_max_position_size',maximum)):
            _ema_equal(decision[name],expected,'decision.'+name,base)
        for field,value in (('min_position_size',minimum),('max_position_size',maximum)):
            if field in settings:_ema_equal(value,settings[field],'settings.'+field,base)
        old=gross.get(day,0.);cluster=values['cluster_name']
        if not isinstance(cluster,str):raise ValueError('ema_budget_cluster_type')
        cluster_old=clusters.get((day,cluster),0.)
        _ema_equal(number('gross_margin_before'),old,'budget.gross_prefix',base)
        _ema_equal(number('gross_cluster_margin_before'),cluster_old,'budget.cluster_prefix',base)
        counts=dict(contracts_by_risk=int(R//rho),contracts_by_margin=int(max(0.,L-old)//margin),contracts_by_single=int(K//margin))
        bounds=[a,counts['contracts_by_risk'],counts['contracts_by_margin'],counts['contracts_by_single'],maximum]
        broker=integer('broker_enabled');cluster_on=integer('cluster_enabled')
        if broker not in (0,1)or cluster_on not in (0,1):raise ValueError('ema_budget_gate_enabled')
        if broker:
            cap=number('broker_cap_ratio',True);multiplier=number('broker_margin_multiplier',True)
            counts['contracts_by_broker']=int(max(0.,E*cap/multiplier-B-old)//margin);bounds.append(counts['contracts_by_broker'])
            for field,value in (('stage830_projected_broker10_margin_to_equity_cap',cap),('stage830_broker_margin_multiplier',multiplier)):
                if field in settings:_ema_equal(value,settings[field],'settings.'+field,base)
        else:
            counts['contracts_by_broker']=None
            for name in ('broker_cap_ratio','broker_margin_multiplier'):_ema_equal(values[name],None,'budget.'+name,base)
        if cluster_on:
            if not cluster:raise ValueError('ema_budget_cluster_missing')
            cap=number('cluster_cap_amount');reserved=number('cluster_reserved_margin_before')
            counts['contracts_by_cluster']=int(max(0.,cap-reserved-cluster_old)//margin);bounds.append(counts['contracts_by_cluster'])
        else:
            counts['contracts_by_cluster']=None
            for name in ('cluster_cap_amount','cluster_reserved_margin_before'):_ema_equal(values[name],None,'budget.'+name,base)
        for name,expected in counts.items():
            if expected is not None:integer(name)
            _ema_equal(values[name],expected,'budget.'+name,base)
        expected_q=max(0,min(bounds));expected_q=0 if 0<expected_q<minimum else expected_q
        if q!=expected_q or _ema_integer(decision['volume'],'decision.volume')!=q:raise ValueError('ema_budget_frozen_q_mismatch')
        reason='ema_limit_final_budget_zero'if q==0 else('ema_limit_final_budget_reduce'if q<a else'within_ema_limit_final_budget')
        if values['reason']!=reason or decision['candidate_status']!=('opened'if q else'filtered'):
            raise ValueError('ema_budget_admission_reason')
        _ema_equal(values['predicted_risk_T'],q*rho,'budget.predicted_risk_T',base)
        _ema_equal(values['predicted_margin_T'],q*margin,'budget.predicted_margin_T',base)
        budgets[key]=dict(row=row,decision=decision,values=values,direction=direction,q=q,T=T,S=S,size=size,tick=tick,rho=rho,margin=margin,ratio=ratio)
        # The accepted rule consumes admitted a, even for q=0 or expired orders.
        gross[day]=old+a*margin;clusters[(day,cluster)]=cluster_old+a*margin
    for key,row in decisions.items():
        if row.get('candidate_status')=='opened'and row.get('volume',0)>0 and key not in budgets:
            raise ValueError('ema_admitted_decision_without_budget')
    return budgets,intents


def ema_evidence(payload,t,usage,base,pd):
    ema=payload['ema'];run_id=_ema_text(payload['run_context']['run_id'],'run_id')
    for name in ('decision','budget','execution','fill','pending'):
        if not isinstance(ema[name],list)or any(not isinstance(x,dict)for x in ema[name]):raise ValueError('ema_audit_row_type:'+name)
    budgets,intents=_ema_budgets(payload,base)
    truth={x['trade_id']:x for x in payload['actual_trade_identities']}
    if any(x.get('research_mechanism')not in (None,checkpoint.MECHANISM_ID)for x in truth.values()):raise ValueError('ema_unknown_mechanism')
    execution=ema['execution'];filled=[x for x in execution if x['status']=='filled']
    if any(x['status']not in ('filled','expired_unfilled','expired_past_day')for x in execution):raise ValueError('ema_unfinished_or_unknown_execution')
    terminal={};audit_by_order={};audit_by_intent={};used_mothers=set();consumed_setups=set();conditional=[];gaps=0
    account_days=set(payload['combined'].date.astype(str).str[:10])
    for row in ema['fill']:
        order=_ema_text(row['order_id'],'fill.order_id');intent=_ema_text(row['intent_id'],'fill.intent_id')
        if order in audit_by_order or intent in audit_by_intent:raise ValueError('ema_duplicate_fill_receipt')
        audit_by_order[order]=row;audit_by_intent[intent]=row
    for row in execution:
        intent=_ema_text(row['intent_id'],'execution.intent_id')
        if intent in terminal or intent not in intents:raise ValueError('ema_duplicate_or_unknown_intent_consumption')
        terminal[intent]=row;decision=intents[intent]
        key=(row['signal_day'],row['product'],row['contract'])
        if key not in budgets or budgets[key]['decision']is not decision:raise ValueError('ema_execution_budget_link')
        b=budgets[key];v=b['values'];q=b['q'];direction=b['direction']
        if q<=0 or _ema_integer(row['quantity'],'execution.quantity',1)!=q:raise ValueError('ema_execution_frozen_q_mismatch')
        if row['mechanism_id']!=checkpoint.MECHANISM_ID or row['policy']!='primary':raise ValueError('ema_execution_mechanism')
        if row['setup_id']!=decision['setup_id']:raise ValueError('ema_execution_setup_link')
        _ema_text(row['epoch_id'],'execution.epoch_id');setup_day=_ema_day(row['setup_day'],'execution.setup_day')
        signal_day=_ema_day(row['signal_day'],'execution.signal_day');day=_ema_day(row['execution_day'],'execution.execution_day')
        if not setup_day<=signal_day<day or day not in account_days:raise ValueError('ema_execution_DAY_order')
        if type(row['direction'])is not int or row['direction']!=direction:raise ValueError('ema_execution_direction')
        rank=_ema_integer(row['rank'],'execution.rank',1)
        if v['original_rank']and rank!=v['original_rank']:raise ValueError('ema_execution_rank')
        tick=_ema_number(row['execution_tick'],'execution.tick',positive=True);limit=_ema_number(row['limit_price'],'execution.limit',positive=True)
        _ema_equal(limit,b['T'],'execution.frozen_L',base)
        if abs(limit/tick-round(limit/tick))>1e-8:raise ValueError('ema_frozen_L_tick')
        forecast_risk=q*b['rho'];forecast_margin=q*b['margin']
        _ema_equal(row['forecast_risk_amount'],forecast_risk,'execution.forecast_risk',base)
        _ema_equal(row['forecast_margin_amount'],forecast_margin,'execution.forecast_margin',base)
        if row['resource_reservation_released']is not False:raise ValueError('ema_reservation_refill')
        if row['status']!='filled':
            for field in ('fill_price','actual_risk_amount','actual_margin_amount'):_ema_equal(row[field],None,'unfilled.'+field,base)
            if intent in audit_by_intent or row.get('order_id')is not None:raise ValueError('ema_unfilled_consumed')
            continue
        if row['setup_id']in consumed_setups:raise ValueError('ema_setup_consumed_more_than_once')
        consumed_setups.add(row['setup_id'])
        order=_ema_text(row['order_id'],'execution.order_id')
        if order not in audit_by_order or audit_by_order[order]['intent_id']!=intent:raise ValueError('ema_actual_fill_link_missing')
        fill=audit_by_order[order]
        for field,expected in (('mechanism_id',checkpoint.MECHANISM_ID),('setup_id',decision['setup_id']),('product',row['product']),
                ('contract',row['contract']),('signal_day',signal_day),('execution_day',day)):
            _ema_equal(fill[field],expected,'fill.'+field,base)
        if _ema_integer(fill['volume'],'fill.volume',1)!=q:raise ValueError('ema_fill_frozen_q_mismatch')
        actual=t.loc[t.order_id.astype(str).eq(order)&t.offset.eq('开')]
        if len(actual)!=1:raise ValueError('ema_actual_open_not_unique')
        actual=actual.iloc[0];identity=truth[actual.trade_id]
        expected=f'{checkpoint.MECHANISM_ID}/{run_id}/{intent}/{order}'
        if expected in used_mothers:raise ValueError('ema_duplicate_mother_consumption')
        used_mothers.add(expected)
        for data in (identity,fill,row):
            if data.get('economic_mother_id')!=expected:raise ValueError('ema_actual_mother_identity')
        if identity.get('research_mechanism')!=checkpoint.MECHANISM_ID or row['run_id']!=run_id or row['native_order_id']!=order:
            raise ValueError('ema_actual_run_order_identity')
        if actual.vt_symbol!=row['contract']or actual.date!=day or actual.signal_date!=signal_day or actual.direction!=('多'if direction==1 else'空'):
            raise ValueError('ema_execution_clock_binding')
        if actual.price_source!=CONDITIONAL or base.stamp(actual.execution_datetime)!=base.stamp(row['execution_datetime']):
            raise ValueError('ema_actual_execution_source_clock')
        price=_ema_number(row['fill_price'],'execution.fill_price',positive=True)
        for actual_value,expected_value,name in ((actual.price,price,'native.price'),(actual.volume,q,'native.quantity'),
                (row['stop_price'],b['S'],'execution.frozen_S'),(row['price'],price,'execution.price'),(row['trigger'],limit,'execution.trigger')):
            _ema_equal(actual_value,expected_value,name,base)
        if row['order_type']!='limit'or row['trading_date']!=day:raise ValueError('ema_execution_DAY_type')
        if abs(price/tick-round(price/tick))>1e-8 or direction*(price-limit)>1e-9:raise ValueError('ema_execution_limit_or_tick')
        minute=row['entry_minute'];stamp=base.stamp(minute['bar_datetime'])
        if stamp!=base.stamp(row['execution_datetime'])or not signal_day<=stamp.date().isoformat()<=day:
            raise ValueError('ema_fill_outside_DAY')
        for field in ('open','high','low','close'):_ema_number(minute[field],'minute.'+field,positive=True)
        volume=_ema_number(minute['volume'],'minute.volume',minimum=0)
        if minute['low']>min(minute['open'],minute['close'])or minute['high']<max(minute['open'],minute['close']):raise ValueError('ema_minute_ohlc')
        extreme=minute['low']if direction==1 else minute['high']
        if direction*(extreme-limit)>-tick+1e-9 or math.floor(volume)<q:raise ValueError('ema_execution_penetration_volume')
        if not minute['low']<=price<=minute['high']:raise ValueError('ema_fill_unreachable')
        signed=direction*(price-b['S']);gap=signed<=0
        risk=None if gap else max(signed*b['size'],max(b['tick']*b['size'],1.))
        actual_risk=None if gap else risk*q;actual_margin=price*b['size']*b['ratio']*q
        expected_fields=dict(signed_risk_price=signed,stop_side_valid=not gap,invalid_stop_side_gap=gap,
            actual_risk_price=None if gap else signed,actual_risk_per_contract=risk,actual_risk_amount=actual_risk,
            actual_margin_amount=actual_margin,actual_minus_forecast_risk_amount=None if gap else actual_risk-forecast_risk,
            actual_minus_forecast_margin_amount=actual_margin-forecast_margin,
            actual_to_forecast_risk_ratio=None if gap else actual_risk/forecast_risk,
            actual_to_forecast_margin_ratio=actual_margin/forecast_margin)
        for field,value in expected_fields.items():_ema_equal(row[field],value,'execution.'+field,base)
        for field,value in (('signed_risk_price',signed),('actual_risk_amount',actual_risk),('actual_margin_amount',actual_margin),
                ('forecast_risk_amount',forecast_risk),('forecast_margin_amount',forecast_margin)):
            _ema_equal(fill[field],value,'fill.'+field,base)
        group=t.loc[t.trade_id.map(lambda x:truth[x].get('economic_mother_id')).eq(expected)]
        if gap:
            gaps+=1
            if group.price_source.eq('stage847_intraday_reentry_at_original_entry').any()or len(group)!=2:
                raise ValueError('ema_invalid_gap_retry_or_missing_protection')
            close=group.loc[group.offset.ne('开')]
            if len(close)!=1 or close.iloc[0].price_source!='invalid_stop_side_gap':raise ValueError('ema_gap_protection_missing')
            _ema_equal(close.iloc[0].volume,q,'gap.protection_quantity',base)
            # Both real TradeData rows remain in the inherited commission/slippage arithmetic.
        conditional.append(dict(order_id=order,contract=row['contract'],signal_day=signal_day,execution_day=day,
            volume=q,fill_price=float(actual.price),intent_id=intent))
    if set(audit_by_intent)!={x['intent_id']for x in filled}:raise ValueError('ema_orphan_fill_receipt')
    if set(t.loc[t.price_source.eq(CONDITIONAL),'order_id'].astype(str))!=set(audit_by_order):raise ValueError('ema_native_initial_fill_not_consumed')
    pending={}
    last_day=max(payload['combined'].date.astype(str).str[:10])
    for row in ema['pending']:
        intent=_ema_text(row['intent_id'],'pending.intent_id')
        if intent in pending or intent in terminal or intent not in intents:raise ValueError('ema_duplicate_pending_consumption')
        decision=intents[intent];key=(row['signal_day'],row['product'],row['contract'])
        if key not in budgets or budgets[key]['decision']is not decision:raise ValueError('ema_pending_budget_link')
        b=budgets[key];plan=row['frozen_plan']
        if row['mechanism_id']!=checkpoint.MECHANISM_ID or row['setup_id']!=decision['setup_id']or row['order_type']!='limit':
            raise ValueError('ema_pending_identity')
        if not _ema_day(row['signal_day'],'pending.signal_day')<_ema_day(row['execution_day'],'pending.execution_day')or row['execution_day']<=last_day:
            raise ValueError('ema_pending_within_completed_DAY')
        if _ema_integer(plan['volume'],'pending.quantity',1)!=b['q']:raise ValueError('ema_pending_frozen_q')
        _ema_equal(row['limit_price'],b['T'],'pending.frozen_L',base)
        _ema_equal(plan['sizing']['stop_price'],b['S'],'pending.frozen_S',base)
        pending[intent]=row
    admitted={b['decision']['intent_id']for b in budgets.values()if b['q']>0}
    if admitted!=set(terminal)|set(pending):raise ValueError('ema_admitted_intent_missing_terminal')
    for identity in truth.values():
        if identity.get('research_mechanism')==checkpoint.MECHANISM_ID and identity.get('economic_mother_id')not in used_mothers:
            raise ValueError('ema_orphan_native_mother')
    return pd.DataFrame(conditional),dict(initial_fills=len(filled),invalid_gap_mothers=gaps,
        unfilled=sum(x['status']!='filled'for x in execution),budget_rows=len(ema['budget']),
        decision_budget_intent_links=len(budgets),all_fixed_q_bounds_recomputed=True,risk_margin_deltas_ratios_recomputed=True,
        actual_prices_from_execution_audit_after_native_identity_check=True)


def _audit_payload(payload,export,summary):
    """Finite-fixture seam and real review share unchanged original arithmetic."""
    inherited,base,a33,np,pd,arithmetic=_algorithms()
    from stage022_run_c0_qualified_wait import canonical_trade_enums,attach_trading_dates
    from stage031_run_ordered_checkpoint import build_execution_clock
    clock,usage=build_execution_clock(payload['capture'],payload['actual_trade_identities'])
    a33.identity_audit(payload['capture']['usage'],payload['actual_trade_identities'],clock,usage)
    trades=canonical_trade_enums(payload['frames']['trades'])
    truth=pd.DataFrame(payload['actual_trade_identities']).set_index('trade_id',verify_integrity=True)
    for field in ('research_mechanism','economic_mother_id'):trades[field]=trades.trade_id.map(truth[field])
    trades=attach_trading_dates(trades,clock)
    tables={**payload['frames'],'trades':trades,'daily':payload['combined'],'execution_clock':clock,'execution_proxy_usage':usage,
        'actual_trade_identities':pd.DataFrame(payload['actual_trade_identities']),
        'internal_equity_daily':pd.DataFrame(payload['capture'].get('equity',[]))}
    tables.update({'ema_'+k+'_audit':pd.DataFrame(v)for k,v in payload['ema'].items()})
    for name,frame in tables.items():
        if checkpoint.asset(export/(name+'.csv')).sha256!=a33.serialized_csv_sha(frame):raise ValueError('ema_raw_export_table_mismatch:'+name)
    if any(x.get('event')=='data_gate_failed'for x in payload.get('wait_audit',[])):raise ValueError('ema_completed_account_has_failed_gate')
    for row in payload.get('wait_audit',[]):
        if row.get('event')=='data_qualified_appended'and(type(row.get('old_keys_changed'))is not int or row['old_keys_changed']!=0):
            raise ValueError('ema_completed_account_old_keys_changed')
    from stage106_independent_off_account_review import signal_day
    t=trades.copy();u=usage.copy();u['signal_date']=u.signal_date.map(lambda v:signal_day(v,pd))
    selected=u[['trade_id','signal_date','price_source','execution_datetime','signal_order_id']].copy()
    t=t.drop(columns=[x for x in selected.columns if x!='trade_id'and x in t.columns]).merge(selected,on='trade_id',validate='one_to_one')
    for field in ('date','trading_date'):t[field]=t[field].astype(str).str[:10]
    t['fill_number']=t.trade_id.str.rsplit('.',n=1).str[-1].astype(int);t=t.sort_values('fill_number').reset_index(drop=True)
    if t.fill_number.tolist()!=list(range(1,len(t)+1)):raise ValueError('ema_actual_fill_serial')
    d=payload['combined'].copy();d['date']=pd.to_datetime(d.date).dt.strftime('%Y-%m-%d')
    settings=payload['actual'][0]['actual'];params=payload['parameters']
    base.close(t.signed_volume,t.volume*t.direction.map({'多':1,'空':-1}),'actual signed direction')
    env=dict(payload=payload,export=export,summary=summary,t=t,d=d,settings=settings,params=params,
        base=base,a33=a33,np=np,pd=pd)
    exec(arithmetic,env)
    conditional,evidence=ema_evidence(payload,t,usage,base,pd)
    candidates=payload['frames']['entry_candidates'].copy();rollover=payload['frames']['rollover_shape_same_volume'].copy()
    for frame in (candidates,rollover):
        if 'date'in frame:frame['date']=frame.date.astype(str).str[:10]
    cycles,episodes,active,retries,rolls,mothers=base.reconstruct_episodes(t,candidates,conditional,rollover)
    open_mtm=sum(v['net_cash']+v['quantity']*env['last_marks'][symbol]*params['contract_sizes'][symbol]for symbol,v in active.items())
    env['residuals']['cycles_and_open_mtm']=base.close(cycles.net_cash.sum()+open_mtm,d.net_pnl.sum(),'cycles plus open mtm')
    # Retry may cross L; its authoritative parent and economic mother must agree.
    for link in retries:
        retry=t.loc[t.trade_id.eq(link['retry_fill'])].iloc[0]
        parent=t.loc[t.order_id.eq(link['parent_order'])&t.offset.eq('开')].iloc[0]
        if truth.loc[retry.trade_id,'economic_mother_id']!=truth.loc[parent.trade_id,'economic_mother_id']:raise ValueError('ema_retry_mother_changed')
    return dict(reconstructed_metrics=env['metrics'],residuals=env['residuals'],EMA=evidence,
        closed_cycles=len(cycles),mother_episodes=len(episodes),retry_links=len(retries),roll_links=len(rolls),
        original_accounting_algorithms_changed=False,financial_replays=0,model_loads=0,
        limitations=['Commission schedule inherited, including known zero rates.','Margin is daily closing margin, not minute portfolio peak.',
            'V>=q is a source-level lot inference and all-or-none research approximation; queue allocation is unproven.'])


def audit_ema(*,completion:BoundAsset,output:Path)->dict:
    evidence=json.loads(checkpoint.read_asset(completion))
    if (evidence.get('schema')!='stage140_ema_actual_completion_v1'or evidence.get('issued_by')!='root'
        or evidence.get('account_id')!=checkpoint.ACCOUNT_ID or evidence.get('fixture_only')is not False
        or evidence.get('actual_terminal_observed')is not True or type(evidence.get('exit_code'))is not int or evidence['exit_code']!=0
        or not evidence.get('tool_session_id')or not evidence.get('tool_terminal_chunk_id')):raise ValueError('ema_actual_root_completion_required')
    context=BoundAsset(Path(evidence['run_context_path']),evidence['run_context_sha256'],evidence['run_context_bytes'])
    run=checkpoint.run_from_context(context)
    if run.run_id!=evidence['run_id']:raise ValueError('ema_completion_run_mismatch')
    actual_tools={str(p):checkpoint.asset(p)for name in ('data_runtime','data_scope')for p in (run.output/name).rglob('*.json')}
    declared=evidence.get('data_tool_bindings')
    if not isinstance(declared,dict)or set(declared)!=set(actual_tools):raise ValueError('ema_actual_data_tool_closure_required')
    for path,bound in actual_tools.items():
        if declared[path]!=dict(sha256=bound.sha256,bytes=bound.bytes):raise ValueError('ema_actual_data_tool_changed')
    import stage022_run_c0_qualified_wait as runtime
    with tempfile.TemporaryDirectory(prefix='ema-review-')as tmp:
        previous=runtime.OUTPUT
        try:runtime.OUTPUT=Path(tmp);runtime.configure_runtime(Path(tmp)/'shared')
        finally:runtime.OUTPUT=previous
        payload,binding=checkpoint.load_sealed(run)
        success=json.loads((run.output/'export_success.json').read_bytes())
        summary_asset=BoundAsset(Path(success['summary_path']),success['summary_sha256'],success['summary_bytes'])
        summary=json.loads(checkpoint.read_asset(summary_asset));export=summary_asset.path.parent
        if (evidence.get('raw_sha256')!=binding['manifest']['raw_sha256']or evidence.get('seal_sha256')!=binding['seal_sha256']
            or evidence.get('summary_sha256')!=summary_asset.sha256):raise ValueError('ema_completion_raw_export_binding')
        result=_audit_payload(payload,export,summary)
        result.update(schema='stage140_ema_independent_account_review_v1',independent_review=True,
            account_id=checkpoint.ACCOUNT_ID,run_id=run.run_id,status='accepted_original_cash_inventory_costs_and_ema_evidence',
            completion_path=str(completion.path),completion_sha256=completion.sha256,
            raw_sha256=binding['manifest']['raw_sha256'],reviewer_source_sha256=checkpoint.asset(__file__).sha256,
            actual_data_tool_bindings=declared,
            production_qualified=False)
        checkpoint.write_json(Path(output)/'review_receipt.json',result)
        return result
