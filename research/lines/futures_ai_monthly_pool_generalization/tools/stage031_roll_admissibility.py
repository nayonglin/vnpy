"""Local roll shape/delay helper; no identification, account sizing or fills.

Exact 41 positive OHLCV and strict dates are a declared research restriction.
Global calendar continuity, contract/data identity and historical economics must
be qualified externally. The helper never certifies a formal complete rollover.
"""
from __future__ import annotations
import ast
from copy import deepcopy
from datetime import date
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
from stage012_c2_reference_frontier import frozen_initial_stop_host

ROOT=Path(__file__).resolve().parents[4]
EXPECTED_RELEASE='m0008_20261008T204054+0800_2a7420a9f955'
EXPECTED_SOURCE_SHA='982977374be58ece5c5ee351a0bf60d0d1e8e213b7c480cc47d46c84ab90b45c'
METHODS=('_rollover_shape_continuation_snapshot','_calculate_macd')

@lru_cache(maxsize=1)
def _host_and_binding():
    pointer=json.loads((ROOT/'official_strategy_materials/CURRENT.json').read_text())
    if pointer['release_id']!=EXPECTED_RELEASE:raise ValueError('source_release_changed_requires_review')
    release=ROOT/'official_strategy_materials'/pointer['strategy_version']/'releases'/EXPECTED_RELEASE
    manifest=json.loads((release/'manifest.json').read_text())
    def verified(logical):
        data=(release/'payload'/logical).read_bytes();sha=hashlib.sha256(data).hexdigest()
        expected=next(r['sha256'] for r in manifest['files'] if r['logical_path']==logical)
        if sha!=expected:raise ValueError('frozen_source_sha_mismatch')
        return data,sha
    logical='examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py';data,sha=verified(logical)
    if sha!=EXPECTED_SOURCE_SHA:raise ValueError('frozen_roll_source_changed')
    original=next(n for n in ast.parse(data.decode()).body if isinstance(n,ast.ClassDef) and n.name=='QmtRollPortfolioStrategy')
    functions={n.name:n for n in original.body if isinstance(n,ast.FunctionDef)}
    attributes={n.target.id:ast.literal_eval(n.value) for n in original.body if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.target.id in ('ma_short','ma_mid','ma_long','ma_extra_long','long_entry_enabled','short_entry_enabled')}
    buildlogical='examples/portfolio_backtesting/run_qmt_roll_backtest.py';builddata,buildsha=verified(buildlogical)
    short_values=[]
    for node in ast.walk(ast.parse(builddata.decode())):
        if isinstance(node,ast.Dict):
            for key,value in zip(node.keys,node.values):
                if isinstance(key,ast.Constant) and key.value=='short_entry_enabled':short_values.append(ast.literal_eval(value))
    if short_values!=[True]:raise ValueError('short_entry_setting_changed_requires_review')
    attributes['short_entry_enabled']=short_values[0]
    if attributes!={'ma_short':5,'ma_mid':10,'ma_long':20,'ma_extra_long':40,'long_entry_enabled':True,'short_entry_enabled':True}:raise ValueError('shape_settings_changed_requires_review')
    configlogical='examples/portfolio_backtesting/qmt_roll_official_stage037_ruleset_config.py';configdata,configsha=verified(configlogical)
    delay=[]
    for node in ast.walk(ast.parse(configdata.decode())):
        if isinstance(node,ast.Dict):
            for key,value in zip(node.keys,node.values):
                if isinstance(key,ast.Constant) and key.value=='rollover_delay_trading_days':delay.append(ast.literal_eval(value))
    if len(delay)!=1 or type(delay[0]) is not int or delay[0]<=0:raise ValueError('invalid_bound_delay_configuration')
    cls=ast.ClassDef(name='FrozenRollShape',bases=[],keywords=[],body=[deepcopy(functions[k]) for k in METHODS],decorator_list=[])
    module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),cls],type_ignores=[])
    ns=dict(np=np,pd=pd);exec(compile(ast.fix_missing_locations(module),'frozen_roll_shape','exec'),ns)
    binding=dict(release_id=EXPECTED_RELEASE,source_logical_path=logical,source_sha256=sha,method_ast_sha256={k:hashlib.sha256(ast.dump(functions[k],include_attributes=False).encode()).hexdigest() for k in METHODS},settings=attributes,settings_override_logical_path=buildlogical,settings_override_sha256=buildsha,required_delay_days=delay[0],delay_configuration_logical_path=configlogical,delay_configuration_sha256=configsha,scope='local_shape_only_no_account_sizing_no_fills')
    return ns['FrozenRollShape'],binding

def source_binding():return deepcopy(_host_and_binding()[1])

def _day(value):
    if not isinstance(value,str):raise ValueError('invalid_iso_day')
    try:parsed=date.fromisoformat(value)
    except ValueError:raise ValueError('invalid_iso_day') from None
    if parsed.isoformat()!=value:raise ValueError('noncanonical_iso_day')
    return value

def _contract(value):
    if not isinstance(value,str) or not value or value.strip()!=value:raise ValueError('invalid_contract')
    return value

def advance_delay(previous:dict|None,target_contract:str,day:str)->dict:
    """Count ordered distinct processing dates, not calendar elapsed days.

    Does not certify the calendar, mapping, held position or due applicability.
    """
    target=_contract(target_contract);today=_day(day);required=source_binding()['required_delay_days']
    if previous is not None:
        if not isinstance(previous,dict) or any(k not in previous for k in ('target_contract','signal_day','last_counted_day','elapsed')):raise ValueError('invalid_delay_state')
        oldtarget=_contract(previous['target_contract']);signal=_day(previous['signal_day']);last=_day(previous['last_counted_day']);elapsed=previous['elapsed']
        if type(elapsed) is not int or elapsed<0 or signal>last or today<last or (signal==last and elapsed!=0):raise ValueError('invalid_or_backwards_delay_state')
    if previous is None or oldtarget!=target:
        signal,last,elapsed=today,today,0
    elif today!=last:
        elapsed+=1;last=today
    return dict(target_contract=target,signal_day=signal,last_counted_day=last,elapsed=elapsed,due=elapsed>=required,required_days=required)

def _number(value):
    if isinstance(value,bool):raise ValueError('invalid_numeric_input')
    try:result=float(value)
    except (TypeError,ValueError):raise ValueError('invalid_numeric_input') from None
    if not math.isfinite(result) or result<=0:raise ValueError('nonpositive_or_nonfinite_history_input')
    return result

def evaluate_roll(direction,history,dates,signal_day,contract=None)->dict:
    """Return local shape + signal stop; does not qualify complete roll entry.

    The caller must compare dates with its global source-processing calendar.
    A known local shape fail still permits a separate old-close decision.
    """
    if direction not in ('long','short'):raise ValueError('invalid_direction')
    if contract is not None:_contract(contract)
    day=_day(signal_day)
    if not isinstance(history,list) or len(history)!=41:raise ValueError('requires_exact_AM41_history')
    if not isinstance(dates,list) or len(dates)!=41:raise ValueError('requires_exact_41_dates')
    ds=[_day(d) for d in dates]
    if any(a>=b for a,b in zip(ds,ds[1:])) or ds[-1]!=day:raise ValueError('history_dates_not_strict_or_signal_mismatch')
    rows=[]
    for row in history:
        if not isinstance(row,dict) or any(k not in row for k in ('open','high','low','close','volume')):raise ValueError('missing_OHLCV_history_input')
        r={k:_number(row[k]) for k in ('open','high','low','close','volume')}
        if r['low']>min(r['open'],r['close']) or r['high']<max(r['open'],r['close']) or r['low']>r['high']:raise ValueError('invalid_history_geometry')
        rows.append(r)
    cls,binding=_host_and_binding();host=cls()
    for key,value in binding['settings'].items():setattr(host,key,value)
    frame=pd.DataFrame(rows);shape=host._rollover_shape_continuation_snapshot(direction,frame)
    stophost,stopbinding=frozen_initial_stop_host();bar=SimpleNamespace(**{k+'_price':rows[-1][k] for k in ('open','high','low','close')})
    signal_stop=float(stophost._entry_stop_price(direction,bar,frame,use_day_extreme=True))
    return dict(allowed=bool(shape['allowed']),signal_stop=signal_stop,shape=shape,source_binding={**deepcopy(binding),'initial_stop_sources':stopbinding},signal_day=day,contract=contract,formal_roll_qualified=False,calendar_continuity_certified=False,contract_identity_certified=False,economics_certified=False,scope='local_exact41_OHLCV_strict_dates_shape_and_signal_stop_only; external_calendar_and_identity_required')
