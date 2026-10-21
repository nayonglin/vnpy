"""Frozen-source daily decision adapter; no fill, accounting, roll or age inference.

Single base layer / integer quantity is a research restriction. Excluding active
portfolio heat and forced-margin decisions changes the source target. Returned
state is proposed only; pending requests need an external execution/commit
contract. Source signal-date age must be supplied by that contract, not guessed
from actual fill time here.
"""
from __future__ import annotations
import ast
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
METHODS = ('_update_dynamic_stops','_update_layer_stop','_profit_lock_price','_profit_lock_thresholds','_apply_atr_mid_stop','_process_prev2day_stop','_should_relax_prev2day_stop_for_locked_trend','_should_relax_prev2day_stop_for_post_quality','_process_layer_stops','_process_rsi_partial_exit','_stop_triggered','_stop_execution_price','_apply_add_position_profit_lock')
SETTINGS = dict(trailing_stop_enabled=True,trailing_stop_pct=0.,profit_lock_tiers='',atr_2x_mid_stop_enabled=True,enable_prev2day_stop=True,enable_rsi_partial_exit=True,rsi_partial_exit_threshold=95.,rsi_partial_exit_ratio=.5,enable_profit_giveback_stop=False,enable_profit_lock_trend_relaxed_prev2day_stop=False,enable_post_entry_quality_prev2day_relax=False,post_entry_quality_add_triggers_add_profit_lock=False)
EXPECTED_RELEASE='m0008_20261008T204054+0800_2a7420a9f955'
EXPECTED_SOURCE_SHA='982977374be58ece5c5ee351a0bf60d0d1e8e213b7c480cc47d46c84ab90b45c'

@lru_cache(maxsize=1)
def _host_class_and_binding():
    pointer=json.loads((ROOT/'official_strategy_materials/CURRENT.json').read_text())
    if pointer['release_id'] != EXPECTED_RELEASE: raise ValueError('source_release_changed_requires_review')
    release=ROOT/'official_strategy_materials'/pointer['strategy_version']/'releases'/EXPECTED_RELEASE
    logical='examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py'; source=release/'payload'/logical
    data=source.read_bytes(); sha=hashlib.sha256(data).hexdigest()
    manifest=json.loads((release/'manifest.json').read_text()); manifest_sha=next(x['sha256'] for x in manifest['files'] if x['logical_path']==logical)
    if sha != EXPECTED_SOURCE_SHA or sha != manifest_sha:raise ValueError('frozen_source_sha_mismatch')
    tree=ast.parse(data.decode()); original=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='QmtRollPortfolioStrategy'); funcs={n.name:n for n in original.body if isinstance(n,ast.FunctionDef)}
    hashes={k:hashlib.sha256(ast.dump(funcs[k],include_attributes=False).encode()).hexdigest() for k in METHODS}
    body=[deepcopy(funcs[k]) for k in METHODS]
    cls=ast.ClassDef(name='FrozenDailyRules',bases=[],keywords=[],body=body,decorator_list=[])
    module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),cls],type_ignores=[])
    ns=dict(pd=pd,math=math);exec(compile(ast.fix_missing_locations(module),str(source),'exec'),ns)
    binding=dict(release_id=EXPECTED_RELEASE,source_logical_path=logical,source_sha256=sha,method_ast_sha256=hashes,method_lines={k:[funcs[k].lineno,funcs[k].end_lineno] for k in METHODS},settings=deepcopy(SETTINGS),excluded_active_portfolio_rules=['risk_cluster_heat_deleverage','forced_margin_deleverage'],scope='research_single_base_integer_qty_daily_decision_only')
    return ns['FrozenDailyRules'],binding

def source_binding():return deepcopy(_host_class_and_binding()[1])

def _finite(value,name,positive=False):
    if isinstance(value,bool):raise ValueError('invalid_'+name)
    try:v=float(value)
    except (TypeError,ValueError):raise ValueError('invalid_'+name) from None
    if not math.isfinite(v) or (positive and v<=0):raise ValueError('invalid_'+name)
    return v

def _integer(value,name,minimum=0):
    if isinstance(value,bool) or not isinstance(value,int) or value<minimum:raise ValueError('invalid_'+name)
    return value

def _ohlc(row,name):
    if not isinstance(row,dict):raise ValueError('invalid_'+name)
    try:r={k:_finite(row[k],name+'_'+k,True) for k in ('open','high','low','close')}
    except KeyError:raise ValueError('missing_'+name+'_ohlc') from None
    if r['low']>min(r['open'],r['close']) or r['high']<max(r['open'],r['close']) or r['low']>r['high']:raise ValueError('invalid_'+name+'_geometry')
    return r

@dataclass
class _State:
    direction:str
    layers:list
    bars_since_entry:int
    prev2day_stop_price:float|None
    rsi_partial_exit_done:bool
    contract_vt_symbol:str
    product_vt_symbol:str
    def active_volume(self):return self.layers[0].volume
    def base_volume(self):return self.layers[0].volume


def decide_daily_exit(*,state,history,bar,rsi_value,ma_long_prev_value):
    """Consume exactly AM41 and externally aligned age/RSI/previous MA20.

    A request has a close *signal reference*, never an execution/fill price.
    Integer holdings are never changed by this adapter. A partial requested flag
    is provisional until the external driver resolves fill/unknown/rejection.
    """
    if not isinstance(state,dict):raise ValueError('invalid_state')
    s=deepcopy(state)
    required=('direction','qty','entry_price','stop_price','max_profit_pct','highest_price','lowest_price','prev2day_stop_price','rsi_partial_exit_done','bars_since_entry','contract','target_contract','pending_roll')
    if any(k not in s for k in required):raise ValueError('missing_state_fields')
    if s['direction'] not in ('long','short'):raise ValueError('invalid_direction')
    _integer(s['qty'],'qty',1);_integer(s['bars_since_entry'],'bars_since_entry')
    for k in ('pending_roll','rsi_partial_exit_done'):
        if type(s[k]) is not bool:raise ValueError('invalid_'+k)
    for k in ('contract','target_contract'):
        if not isinstance(s[k],str) or not s[k]:raise ValueError('invalid_'+k)
    for k in ('entry_price','stop_price','highest_price','lowest_price'):s[k]=_finite(s[k],k,True)
    s['max_profit_pct']=_finite(s['max_profit_pct'],'max_profit_pct')
    if s['max_profit_pct']<0 or s['highest_price']<s['lowest_price']:raise ValueError('invalid_layer_path_state')
    if s['prev2day_stop_price'] is not None:s['prev2day_stop_price']=_finite(s['prev2day_stop_price'],'prev2day_stop_price',True)
    if not isinstance(history,list) or len(history)!=41:raise ValueError('requires_exact_AM41_history')
    h=[_ohlc(row,'history') for row in history];b=_ohlc(bar,'bar')
    if h[-1]!=b:raise ValueError('current_history_bar_mismatch')
    rsi=_finite(rsi_value,'rsi_value');ma=_finite(ma_long_prev_value,'ma_long_prev_value',True)
    if not 0<=rsi<=100:raise ValueError('invalid_rsi_value')
    result=dict(status='known_decision',request=None,proposed_state=deepcopy(s),proposed_state_is_executed=False,age_semantics='external_source_signal_date_age_not_actual_fill_age; not certified here',execution_certified=False)
    if s['pending_roll'] or s['target_contract']!=s['contract']:
        result['status']='unsupported_roll_contract';return result
    cls,_=_host_class_and_binding();host=cls()
    for key,value in SETTINGS.items():setattr(host,key,deepcopy(value))
    layer=SimpleNamespace(kind='base',direction=s['direction'],volume=s['qty'],entry_price=s['entry_price'],stop_price=s['stop_price'],highest_price=s['highest_price'],lowest_price=s['lowest_price'],max_profit_pct=s['max_profit_pct'],profit_giveback_stop_active=False)
    st=_State(s['direction'],[layer],s['bars_since_entry'],s['prev2day_stop_price'],s['rsi_partial_exit_done'],s['contract'],'research_unbound_product')
    bb=SimpleNamespace(**{key+'_price':value for key,value in b.items()})
    capture={}
    def queue(reason,reduce_qty,reference):
        if capture.get('request') is not None:raise RuntimeError('multiple_requests_not_supported')
        capture['request']=dict(action='reduce',reason=reason,reduce_qty=int(reduce_qty),target_qty=s['qty']-int(reduce_qty),contract=s['contract'],direction=s['direction'],signal_reference_price=float(reference),execution_timing='next_valid_session_open_required',fill_status='unresolved_external_execution_required')
    def close_all(_state,exit_price,**kw):queue(kw['exit_reason'],s['qty'],exit_price)
    def record(**kw):capture['partial_reason']=kw['reason']
    def reduce(_state,target_volume,exit_price):queue(capture['partial_reason'],s['qty']-target_volume,exit_price)
    host._close_all_layers_and_set_flat_target=close_all;host._record_trade_event=record;host._reduce_position_to_target=reduce
    frame=pd.DataFrame(h)
    host._update_dynamic_stops(st,bb,frame)
    reason=host._process_prev2day_stop(st,bb,frame)
    if not reason:reason=host._process_layer_stops(st,bb)
    if not reason:reason=host._process_rsi_partial_exit(st,bb,rsi)
    if not reason and host._stop_triggered(s['direction'],bb,ma):
        reason=s['direction']+'_ma_stop';queue(reason,s['qty'],host._stop_execution_price(s['direction'],bb,ma))
    proposed=deepcopy(s)
    for k in ('stop_price','highest_price','lowest_price','max_profit_pct'):proposed[k]=float(getattr(layer,k))
    proposed['prev2day_stop_price']=st.prev2day_stop_price;proposed['rsi_partial_exit_done']=st.rsi_partial_exit_done
    result.update(request=capture.get('request'),proposed_state=proposed)
    return result


def run_synthetic_probe(output_parent=None):
    """Write a new, bounded synthetic decision artifact. No market data is read."""
    from datetime import datetime
    parent=Path(output_parent) if output_parent else Path(__file__).resolve().parents[1]/'outputs/stage026_daily_exit_adapter'
    parent.mkdir(parents=True,exist_ok=True)
    folder=parent/datetime.now().astimezone().strftime('run_%Y%m%d_%H%M%S_%f')
    folder.mkdir(exist_ok=False)
    def make(name,direction='long',qty=4):
        history=[dict(open=100.,high=101.,low=99.,close=100.) for _ in range(41)]
        return dict(case_id=name,state=dict(direction=direction,qty=qty,entry_price=100.,stop_price=90. if direction=='long' else 110.,max_profit_pct=0.,highest_price=100.,lowest_price=100.,prev2day_stop_price=None,rsi_partial_exit_done=False,bars_since_entry=1,contract='synthetic.X',target_contract='synthetic.X',pending_roll=False),history=history,bar=dict(history[-1]),rsi_value=50.,ma_long_prev_value=95. if direction=='long' else 105.)
    rows=[]
    x=make('low_touch_only');x['bar']['low']=80.;x['history'][-1]=dict(x['bar']);rows.append(x)
    x=make('close_stop');x['bar']=dict(open=100.,high=101.,low=88.,close=89.);x['history'][-1]=dict(x['bar']);rows.append(x)
    x=make('profit_lock_close_stop');x['state']['max_profit_pct']=.03;x['bar']=dict(open=100.,high=101.,low=99.,close=100.5);x['history'][-1]=dict(x['bar']);rows.append(x)
    x=make('prev2day_priority');x['state']['bars_since_entry']=2;x['state']['stop_price']=100.5;x['history'][-3]['low']=100.;x['history'][-2]['low']=100.;rows.append(x)
    x=make('rsi_before_ma');x['rsi_value']=96.;x['ma_long_prev_value']=101.;rows.append(x)
    x=make('one_lot_rsi_noop_ma',qty=1);x['rsi_value']=96.;x['ma_long_prev_value']=101.;rows.append(x)
    x=make('short_rsi_before_ma',direction='short',qty=3);x['rsi_value']=4.;x['ma_long_prev_value']=99.;rows.append(x)
    x=make('atr_mid_same_close_stop');x['history']=[dict(open=100.,high=100.5,low=99.5,close=100.) for _ in range(41)];x['bar']=dict(open=100.,high=115.,low=99.,close=105.);x['history'][-1]=dict(x['bar']);rows.append(x)
    x=make('target_changed_unsupported');x['state']['target_contract']='other.X';rows.append(x)
    x=make('pending_roll_unsupported');x['state']['pending_roll']=True;rows.append(x)
    outputs=[]
    for row in rows:
        payload={k:deepcopy(v) for k,v in row.items() if k!='case_id'};before=deepcopy(payload)
        result=decide_daily_exit(**payload)
        if payload != before:raise RuntimeError('probe_input_mutated')
        outputs.append(dict(case_id=row['case_id'],result=result))
    def write(name,obj):
        path=folder/name;path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n');return hashlib.sha256(path.read_bytes()).hexdigest()
    hashes={name:write(name,obj) for name,obj in [('inputs.json',rows),('outputs.json',outputs),('bindings.json',source_binding())]}
    source=Path(__file__).resolve();test=source.with_name('test_stage026_daily_exit_adapter.py')
    summary=dict(generated_at=datetime.now().astimezone().isoformat(),probe_kind='synthetic_pure_daily_decisions',fixture_count=len(rows),known_decision_count=sum(x['result']['status']=='known_decision' for x in outputs),unsupported_roll_count=sum(x['result']['status']=='unsupported_roll_contract' for x in outputs),queued_request_count=sum(x['result']['request'] is not None for x in outputs),actual_fill_count=0,financial_replay_count=0,net_60d_label_count=0,fit_count=0,production_mutation_count=0,input_mutation_count=0,artifact_sha256=hashes,code_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),test_sha256=hashlib.sha256(test.read_bytes()).hexdigest(),age_qualification=False,c2_qualification=False,notes=['integer quantity diagnostic only','proposed RSI flag is not committed fill state','roll unsupported; pending ordinary execution handled externally','active portfolio heat/forced exits excluded research delta'])
    write('summary.json',summary)
    return str(folder),summary

if __name__=='__main__':
    path,summary=run_synthetic_probe()
    print(json.dumps(dict(output_dir=path,summary=summary),ensure_ascii=False,indent=2))
