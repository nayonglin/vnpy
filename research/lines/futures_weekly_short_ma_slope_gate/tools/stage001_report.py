"""Read-only Stage032 A/C report; accepted ledgers only, never a strategy replay.

The inherited Stage029 *pure accounting functions* are reused. Its frozen-2015
loader and its old RSI-on baseline contract are deliberately not called.
"""
from __future__ import annotations
import argparse
import sys
from collections import defaultdict
from datetime import datetime
import json
import math
import os
from pathlib import Path
import tempfile
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
BASETOOLS=Path(__file__).resolve().parents[2]/'futures_weekly_formal_no_half_r/tools'
sys.path.insert(0,str(BASETOOLS))
from stage029_build_artifacts import (
    CAPITAL, POOL, FLAGS, EXECUTION_MODEL, sha, snapshot_dir, verify_sources,
    require_close, trading_day, utc, direction, offset, product, metadata,
    ordered_fills, inventory_accounting, pnl_stats, curve_metrics,
    validate_completion, position_aggregates, annual_rows, product_rows,
    validate_output_paths,
)

ADDON_CONFIG = dict(up_days=2, volume=1, max_adds_per_parent=2,
    max_active_per_product=1, stop_rule='fixed_prior2_low_daily_close_next_open')
IDENTITY_KEYS = {'daily_sqlite_sha256', 'mapping_sha256',
    'physical_epoch_daily_sha256', 'receipt_sha256'}


def audit_positions(path, daily, fills, effective):
    """Reprice every financially active position row from real fills and marks.

    A fabricated terminal mark cannot be hidden behind a conserved grand total.
    The input table includes warmup rows; those may not carry financial state.
    """
    dates = set(daily.date.dt.strftime('%Y-%m-%d'))
    use = ['date','vt_symbol','start_pos','end_pos','pre_close','close_price',
           'net_pnl','slippage','commission','trade_count']
    active, seen, observed = [], set(), set()
    with pd.read_csv(path, usecols=use, chunksize=100000) as chunks:
        for frame in chunks:
            frame['date'] = frame.date.map(trading_day)
            numeric = use[2:]
            outside = ~frame.date.isin(dates)
            financial = frame[['start_pos','end_pos','net_pnl','slippage','commission','trade_count']].fillna(0).abs().sum(axis=1).ne(0)
            if bool((outside & financial).any()):
                raise ValueError('position_financial_state_outside_requested_calendar')
            frame = frame.loc[~outside].copy()
            if not np.isfinite(frame[numeric].to_numpy(float)).all():
                raise ValueError('nonfinite_position_ledger')
            keys = list(zip(frame.date, frame.vt_symbol))
            if len(set(keys)) != len(keys) or seen.intersection(keys):
                raise ValueError('duplicate_position_date_contract')
            seen.update(keys);observed.update(frame.date)
            active.append(frame.loc[financial.loc[frame.index]])
    if observed != dates:
        raise ValueError('incomplete_position_calendar')
    frame = pd.concat(active, ignore_index=True).set_index(['date','vt_symbol'])
    groups = {(d,s):g for (d,s),g in fills.groupby(['trading_date','vt_symbol'], sort=False)}
    if not set(groups).issubset(set(frame.index)):
        raise ValueError('fill_missing_position_row')
    positions, prior_marks = defaultdict(float), {}
    daily_rows = defaultdict(list)
    for key, row in frame.sort_index().iterrows():
        day, symbol = key
        size, slip, rate = metadata(effective, symbol)
        require_close(row.start_pos, positions[symbol], 'position_inventory_start:'+str(key))
        mark = float(row.close_price)
        if mark <= 0 or (row.start_pos and row.pre_close <= 0):
            raise ValueError('real_position_mark_required:'+str(key))
        if row.start_pos:
            require_close(row.pre_close, prior_marks.get(symbol, math.nan), 'position_previous_close:'+str(key))
        g = groups.get(key, fills.iloc[:0])
        signed = sum(direction(r.direction)*float(r.volume) for r in g.itertuples())
        fees = sum(float(r.volume)*float(r.price)*size*rate for r in g.itertuples())
        slips = float(g.volume.sum())*size*slip
        pnl = float(row.start_pos)*(mark-float(row.pre_close))*size + sum(
            direction(r.direction)*(mark-float(r.price))*size*float(r.volume) for r in g.itertuples())-fees-slips
        require_close(row.end_pos, positions[symbol]+signed, 'position_inventory_end:'+str(key))
        for name, expected in [('net_pnl',pnl),('slippage',slips),('commission',fees),('trade_count',len(g))]:
            require_close(row[name], expected, 'position_mtm_'+name+':'+str(key))
        positions[symbol] = float(row.end_pos);prior_marks[symbol] = mark
        daily_rows[day].append((symbol, float(row.end_pos)))
    # A missing carry row could otherwise leave the cached inventory unchanged.
    active_symbols = set()
    for day in sorted(dates):
        present = {s:p for s,p in daily_rows[day]}
        if not active_symbols.issubset(present):
            raise ValueError('missing_held_position_day:'+day)
        active_symbols = {s for s,p in present.items() if abs(p)>1e-9}
    contributions=frame.reset_index()
    contributions['year']=contributions.date.str[:4].astype(int)
    contributions['product']=contributions.vt_symbol.map(product)
    by_year_product=contributions.groupby(['year','product'],sort=True).net_pnl.sum().reset_index().to_dict('records')
    return dict(active_position_rows=len(frame), audited_daily_dates=len(dates), annual_product_contributions=by_year_product,
                method='Fill-derived inventory and per-contract cash/MTM/cost repricing on every financial position row.')


def read_optional_rows(path):
    try:
        return pd.read_csv(path, keep_default_na=False)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def sleeve_accounting(path, fills, effective, terminal_marks, enabled, terminal_day=None, trading_dates=None):
    allocation_path = path/'daily_addon_allocations.csv'
    allocations = read_optional_rows(allocation_path)
    required = {'trade_id','vt_symbol','trading_date','direction','offset','price','volume','sleeve','round_id','addon_id','entry_price','stop_price'}
    if allocations.empty and (not enabled or fills.empty):
        allocations = fills.copy();allocations['sleeve']='base';allocations['round_id']='';allocations['addon_id']='';allocations['entry_price']=allocations.price;allocations['stop_price']=0.
    elif not required.issubset(allocations.columns):
        raise ValueError('allocation_schema_required')
    allocations['trade_id'] = allocations.trade_id.astype(str)
    allocations['round_id'] = allocations.round_id.astype(str)
    allocations['addon_id'] = allocations.addon_id.astype(str)
    if set(allocations.trade_id) != set(fills.trade_id):
        raise ValueError('allocation_fill_coverage_mismatch')
    originals = fills.set_index('trade_id')
    cooked = []
    for trade_id, group in allocations.groupby('trade_id', sort=False):
        row = originals.loc[trade_id]
        for item in group.to_dict('records'):
            if str(item['vt_symbol']) != str(row.vt_symbol) or direction(item['direction'])!=direction(row.direction) or offset(item['offset'])!=offset(row.offset):
                raise ValueError('allocation_fill_mismatch:contract_direction_offset')
            if trading_day(item['trading_date']) != row.trading_date:
                raise ValueError('allocation_trading_date_mismatch')
            require_close(item['price'],row.price,'allocation_price')
            qty = float(item['volume'])
            if not math.isfinite(qty) or qty<=0 or qty!=int(qty):
                raise ValueError('allocation_positive_integer_volume_required')
            if item['sleeve'] not in {'base','daily_addon'} or (not enabled and item['sleeve']!='base'):
                raise ValueError('allocation_sleeve_invalid')
            if item['sleeve']=='daily_addon' and not str(item['addon_id']):
                raise ValueError('allocation_addon_id_required')
            cooked.append({**row.to_dict(),**item,'execution_datetime':row.execution_datetime,'_execution_utc':row._execution_utc,'_clock_order':row._clock_order})
        require_close(group.volume.astype(float).sum(),row.volume,'allocation_volume_conservation')
    alloc = pd.DataFrame(cooked, columns=list(dict.fromkeys([*fills.columns,*allocations.columns])))
    if not alloc.empty:
        alloc = alloc.sort_values(['_execution_utc','_clock_order'],kind='stable')
    tables = {'segments':[], 'rounds':[], 'opened':[]}
    summaries = {}
    addon_entries = []
    for sleeve in ['base','daily_addon']:
        selected = alloc.loc[alloc.sleeve.eq(sleeve)].copy()
        selected['owner_id'] = selected.vt_symbol if sleeve=='base' else selected.addon_id
        combined = {'segments':[], 'rounds':[], 'opened':[]};stats=[]
        for owner_id, owner in selected.groupby('owner_id',sort=False):
            if sleeve=='daily_addon':
                opens = owner.loc[owner.offset.map(offset).eq('open')]
                if len(opens)!=1 or float(opens.volume.sum())!=1 or len(set(owner.vt_symbol))!=1 or len(set(owner.round_id))!=1:
                    raise ValueError('allocation_addon_single_entry_contract_round_required')
                for key in ['entry_price','stop_price']:
                    values=owner[key].astype(float)
                    if not np.isfinite(values).all() or values.le(0).any() or len(set(values))!=1:
                        raise ValueError('allocation_addon_fixed_'+key+'_required')
                require_close(opens.entry_price.iloc[0],opens.price.iloc[0],'allocation_addon_entry_price')
                addon_entries.append(dict(addon_id=str(owner_id),round_id=str(opens.round_id.iloc[0]),entry_trading_date=opens.trading_date.iloc[0],entry_trade_id=str(opens.trade_id.iloc[0])))
            sf,rf,of,account = inventory_accounting(owner,effective,terminal_marks)
            if sleeve=='daily_addon':
                last=owner.iloc[-1];closed=not len(of);exit_day=last.trading_date if closed else terminal_day
                entry=addon_entries[-1]
                entry.update(vt_symbol=str(opens.vt_symbol.iloc[0]),product=product(opens.vt_symbol.iloc[0]),status='closed' if closed else 'open',
                    exit_trading_date=last.trading_date if closed else None,exit_reason=str(last.get('reason','')) if closed else None,
                    net_pnl=account['ledger_net_pnl'],closed_net_pnl=account['closed_fifo']['closed_net_pnl'],open_net_mtm=account['open_round_net_mtm'],
                    total_slippage=account['total_slippage'],total_commission=account['total_commission'],
                    holding_calendar_days=(pd.Timestamp(exit_day)-pd.Timestamp(entry['entry_trading_date'])).days if exit_day else None,
                    holding_trading_days=sum(entry['entry_trading_date']<=d<=exit_day for d in trading_dates) if trading_dates is not None and exit_day else None)
            for key,table in [('segments',sf),('rounds',rf),('opened',of)]:
                tagged = table.assign(sleeve=sleeve,owner_id=str(owner_id))
                if not tagged.empty:
                    combined[key].append(tagged);tables[key].append(tagged)
            stats.append(account)
        empty_sf,empty_rf,empty_of,_=inventory_accounting(fills.iloc[:0],effective,terminal_marks)
        frames={k:pd.concat(v,ignore_index=True) if v else e.assign(sleeve=pd.Series(dtype=str),owner_id=pd.Series(dtype=str)) for (k,v),e in zip(combined.items(),[empty_sf,empty_rf,empty_of])}
        summaries[sleeve]=dict(closed_fifo=pnl_stats(frames['segments']),complete_contract_rounds=pnl_stats(frames['rounds']),
            open_round_count=len(frames['opened']),open_round_net_mtm=float(frames['opened'].net_mtm.sum()),
            open_remaining_net_mtm=float(frames['opened'].remaining_open_net_mtm.sum()),
            ledger_net_pnl=sum(s['ledger_net_pnl'] for s in stats),total_slippage=sum(s['total_slippage'] for s in stats),
            total_commission=sum(s['total_commission'] for s in stats),fill_allocation_count=len(selected),
            native_fill_count=int(selected.trade_id.nunique()),opened_volume=float(selected.loc[selected.offset.map(offset).eq('open'),'volume'].sum()))
    rounds_path=path/'daily_addon_rounds.csv'
    declared_rounds=read_optional_rows(rounds_path)
    counts=pd.DataFrame(addon_entries,columns=['addon_id','round_id','entry_trading_date','entry_trade_id','vt_symbol','product','status','exit_trading_date','exit_reason','net_pnl','closed_net_pnl','open_net_mtm','total_slippage','total_commission','holding_calendar_days','holding_trading_days'])
    if len(counts):
        if not {'round_id','actual_add_count'}.issubset(declared_rounds.columns) or declared_rounds.round_id.duplicated().any():
            raise ValueError('addon_round_count_schema_required')
        expected=counts.groupby('round_id').size().to_dict();declared=declared_rounds.assign(round_id=declared_rounds.round_id.astype(str)).set_index('round_id').actual_add_count.to_dict()
        if not set(expected).issubset(declared) or any(int(v)>2 or float(declared[k])!=v for k,v in expected.items()) or any(float(v)!=expected.get(k,0) for k,v in declared.items()):
            raise ValueError('addon_round_actual_add_count_mismatch')
        counts['add_number']=counts.groupby('round_id',sort=False).cumcount()+1
    else:
        counts['add_number']=pd.Series(dtype=int)
        if 'actual_add_count' in declared_rounds and declared_rounds.actual_add_count.astype(float).ne(0).any():
            raise ValueError('addon_round_actual_add_count_mismatch')
    empty_sf,empty_rf,empty_of,_=inventory_accounting(fills.iloc[:0],effective,terminal_marks)
    result={k:pd.concat(v,ignore_index=True) if v else e.assign(sleeve=pd.Series(dtype=str),owner_id=pd.Series(dtype=str)) for (k,v),e in zip(tables.items(),[empty_sf,empty_rf,empty_of])}
    analysis=dict(actual_add_count=len(counts),closed_add_count=int(counts.status.eq('closed').sum()),open_add_count=int(counts.status.eq('open').sum()),by_add_number={})
    for number,group in counts.groupby('add_number',sort=True):
        closed=group.loc[group.status.eq('closed')]
        analysis['by_add_number'][str(number)]=dict(count=len(group),closed_count=len(closed),open_count=len(group)-len(closed),
            net_pnl=float(group.net_pnl.sum()),open_net_mtm=float(group.open_net_mtm.sum()),closed_trade_statistics=pnl_stats(closed),
            total_slippage=float(group.total_slippage.sum()),total_commission=float(group.total_commission.sum()))
    events=read_optional_rows(path/'daily_addon_events.csv')
    decisions=read_optional_rows(path/'daily_addon_decisions.csv')
    guard=read_optional_rows(path/'daily_addon_guard_failures.csv')
    if not guard.empty:raise ValueError('daily_addon_guard_failures_present')
    analysis['event_action_counts']={str(k):int(v) for k,v in events.action.value_counts().items()} if 'action' in events else {}
    analysis['exit_reason_counts']={str(k):int(v) for k,v in counts.loc[counts.status.eq('closed')].exit_reason.value_counts().items()}
    analysis['decision_rows']=len(decisions)
    analysis['decision_reason_counts']={str(k):int(v) for k,v in decisions.reason.value_counts().items()} if 'reason' in decisions else {}
    analysis['decision_accepted_count']=int(decisions.accepted.astype(str).str.lower().eq('true').sum()) if 'accepted' in decisions else 0
    analysis['decision_rejected_count']=len(decisions)-analysis['decision_accepted_count']
    result.update(summaries=summaries,entries=counts,allocations=alloc,analysis=analysis)
    return result


def load_ledger(path,role):
    path=Path(path).resolve();frozen=snapshot_dir(path)
    def read(name):
        file=path/name
        if str(file) not in frozen:raise FileNotFoundError(file)
        return json.loads(file.read_text()) if name.endswith('.json') else pd.read_csv(file,low_memory=False)
    terminal,postflight=read('terminal.json'),read('postflight.json')
    proofs={p.name:read(p.name) for p in sorted(path.glob('*_acceptance.json'))}
    validate_completion(terminal,postflight,proofs)
    if not {'week_close_exit_acceptance.json','daily_addon_acceptance.json'}.issubset(proofs):raise ValueError('required_stage032_acceptance_missing')
    pre,settings,effective,source_metrics=[read(n) for n in ['preflight.json','actual_strategy_settings.json','effective_parameters.json','metrics.json']]
    if len(settings)!=1:raise ValueError('single_strategy_settings_required')
    actual=settings[0]['actual'];enabled=False;addon=read('actual_daily_addon_configuration.json')
    gate=read('short_ma_slope_acceptance.json')
    if gate.get('enabled') is not (role=='candidate') or pre.get('short_ma_slope_gate_enabled') is not (role=='candidate'):raise ValueError('slope_arm_flag_mismatch')
    if any(actual.get(k) is not False for k in FLAGS) or actual.get('enable_rsi_partial_exit') is not False:raise ValueError('disabled_AI_halfR_C2_RSI_flags_mismatch')
    if tuple(actual.get(k) for k in ['ma_short','ma_mid','ma_long'])!=(5,10,20) or actual.get('research_exact_array_manager_size')!=41:raise ValueError('weekly_MA_or_capacity_mismatch')
    if set(pre.get('universe_products',[]))!=POOL or pre.get('ready_need')!=21 or pre.get('storage_capacity')!=41:raise ValueError('frozen19_or_weekly_readiness_mismatch')
    if pre.get('execution_model')!=EXECUTION_MODEL or pre.get('minute_quote_confirmed') is not False:raise ValueError('declared_daily_open_model_required')
    if pre.get('daily_addon_enabled') is not enabled or addon.get('enabled') is not enabled or any(addon.get(k)!=v for k,v in ADDON_CONFIG.items()):raise ValueError('addon_configuration_contract_failed')
    if pre.get('arm')!=('C' if role=='candidate' else 'A'):raise ValueError('arm_role_mismatch')
    identity=pre.get('data_identity',{})
    if not IDENTITY_KEYS.issubset(identity) or any(not isinstance(v,str) or len(v)!=64 or any(c not in '0123456789abcdef' for c in v) for v in identity.values()):raise ValueError('data_identity_required')
    for value in [actual.get('capital_base'),settings[0].get('engine_capital'),effective['spec']['capital']['account_capital'],effective['spec']['capital']['c3_capital']]:require_close(value,CAPITAL,'capital_contract')
    if actual.get('max_concurrent_positions')!=19 or proofs['no_position_cap_acceptance.json'].get('MA40_decision_enabled') is not False:raise ValueError('max19_and_MA40_off_required')
    for key in ['stage830_broker_margin_multiplier','forced_margin_deleverage_broker_multiplier']:require_close(actual.get(key),1.65,'actual_margin_multiplier:'+key)
    weekly=proofs['week_close_exit_acceptance.json'];short=proofs['short_case2_acceptance.json']
    if weekly.get('rsi_exit_enabled') is not False or weekly.get('short_case2_enabled') is not False or weekly.get('reconciliation_rebuilt_layer_count')!=0 or weekly.get('weekly_stop_guard_failure_count')!=0:raise ValueError('week_close_exit_guard_failure')
    if short.get('short_case2_gate_allowed') is not False or short.get('short_case2_opened')!=0:raise ValueError('short_case2_opened')
    quality,reads=read('data_quality.json'),read('data_read_counts.json')
    if any(quality.get(k) for k in ['held_or_traded_daily_gaps','held_or_traded_zero_volume','captured_bar_failures']):raise ValueError('data_quality_failure')
    if any(reads.get(k)!=0 for k in ['minute_reads','proxy_reads','ai_selection_model_load_attempts']):raise ValueError('unexpected_minute_proxy_AI_read')
    daily=read('daily.csv');daily['date']=pd.to_datetime(daily.date.map(trading_day))
    hist=proofs['historical_safety_acceptance.json'];start,end=str(pre['start']),str(pre['end'])
    if start!='2020-01-01' or end<start or daily.empty or daily.date.duplicated().any() or not daily.date.is_monotonic_increasing or daily.date.iloc[0]!=pd.Timestamp('2020-01-02') or daily.date.iloc[-1]!=pd.Timestamp(end):raise ValueError('full_requested_2020_calendar_required')
    if hist.get('requested_start')!=start or hist.get('requested_end')!=end or hist.get('account_days')!=len(daily) or hist.get('actual_calendar_matches') is not True or hist.get('readiness_calendar_matches') is not True or hist.get('epoch_failure_count')!=0 or hist.get('strict_next_trading_day_open') is not True:raise ValueError('historical_safety_calendar_contract_failed')
    numeric=['account_equity','net_pnl','slippage','commission','trade_count','total_margin_exact','broker10_total_margin_exact']
    if not np.isfinite(daily[numeric].to_numpy(float)).all():raise ValueError('nonfinite_daily_ledger')
    if daily[['slippage','commission','trade_count','total_margin_exact']].lt(0).any().any() or not daily.trade_count.eq(daily.trade_count.astype(int)).all():raise ValueError('negative_cost_margin_or_invalid_fill_count')
    require_close(np.max(np.abs(CAPITAL+daily.net_pnl.cumsum()-daily.account_equity)),0.,'daily_equity_conservation')
    require_close(daily.commission.sum(),0.,'zero_commission_required')
    require_close(np.max(np.abs(daily.broker10_total_margin_exact-daily.total_margin_exact*1.1)),0.,'legacy_broker10_is_1p1')
    fills=ordered_fills(read('trades.csv'),read('execution_clock.csv'))
    if not set(fills.trading_date).issubset(set(daily.date.dt.strftime('%Y-%m-%d'))):raise ValueError('fill_trade_day_outside_daily_calendar')
    if not fills.volume.astype(float).eq(fills.volume.astype(float).round()).all():raise ValueError('integer_futures_volume_required')
    fills['product']=fills.vt_symbol.map(product)
    slice_dates=sorted(set(daily.groupby(daily.date.dt.year).date.max().dt.strftime('%Y-%m-%d')))
    position_audit=audit_positions(path/'positions.csv',daily,fills,effective)
    pos=position_aggregates(path/'positions.csv',daily,fills,slice_dates)
    if pos['max_daily_products']>19 or proofs['no_position_cap_acceptance.json'].get('max_daily_product_positions')!=pos['max_daily_products']:raise ValueError('observed_product_position_count_mismatch')
    sf,rf,of,accounting=inventory_accounting(fills,effective,pos['marks'][end]);curve=curve_metrics(daily)
    for symbol in set(accounting['open_net_positions'])|set(pos['positions'][end]):require_close(accounting['open_net_positions'].get(symbol,0.),pos['positions'][end].get(symbol,0.),'terminal_inventory:'+symbol)
    for a,b,name in [(accounting['ledger_net_pnl'],curve['net_pnl'],'cash_mark_vs_daily'),(accounting['total_slippage'],curve['total_slippage'],'slippage'),(accounting['total_commission'],curve['total_commission'],'commission')]:require_close(a,b,name+'_conservation')
    for key in ['end_equity','total_return_pct','max_dd_pct','sharpe']:
        if curve[key] is None:
            if source_metrics.get(key) is not None:raise ValueError('source_metrics:'+key)
        else:require_close(curve[key],source_metrics[key],'source_metrics:'+key)
    for count in [daily.trade_count.sum(),source_metrics['total_trade_count'],proofs['bar_open_acceptance.json']['trade_count']]:require_close(count,len(fills),'fill_count_conservation')
    binding=read('actual_database_binding.json');db=Path(binding['expected']).resolve()
    if not any(Path(item[2]).resolve()==db for item in binding['database_list'] if len(item)>2 and item[2]):raise ValueError('actual_database_binding_mismatch')
    manifest=read('input_manifest.json')
    if not isinstance(manifest,dict) or not manifest:raise ValueError('nonempty_input_manifest_required')
    sources=dict(frozen)
    for key,digest in manifest.items():
        p=str(Path(key).resolve())
        if p in sources and sources[p]!=digest:raise ValueError('input_manifest_conflicting_digest:'+p)
        sources[p]=digest
    if str(db) not in sources or sources[str(db)]!=identity['daily_sqlite_sha256'] or not set(identity.values()).issubset(set(manifest.values())):raise ValueError('data_identity_not_bound_to_input_manifest')
    verify_sources(sources)
    sleeves=sleeve_accounting(path,fills,effective,pos['marks'][end],enabled,terminal_day=end,trading_dates=daily.date.dt.strftime('%Y-%m-%d').tolist())
    for field in ['ledger_net_pnl','total_slippage','total_commission']:require_close(sum(s[field] for s in sleeves['summaries'].values()),accounting[field],'sleeve_'+field+'_conservation')
    raw=daily.total_margin_exact/daily.account_equity.where(daily.account_equity.gt(0))*100;actual_margin=raw*1.65
    risk=dict(actual_broker_margin_multiplier=1.65,legacy_broker10_multiplier=1.1,
        actual_margin_basis='Configured static exchange margin times 1.65; not historical actual broker margin.',
        legacy_margin_basis='Legacy broker10 column = static exchange margin times 1.1; never labelled actual.',
        raw_margin_to_equity_average_pct=float(raw.mean()) if raw.notna().any() else None,raw_margin_to_equity_max_pct=float(raw.max()) if raw.notna().any() else None,
        actual_margin_to_equity_average_pct=float(actual_margin.mean()) if actual_margin.notna().any() else None,actual_margin_to_equity_max_pct=float(actual_margin.max()) if actual_margin.notna().any() else None,
        actual_margin_over100_days=int(actual_margin.gt(100).sum()),nonpositive_equity_risk_ratio_undefined_days=int(daily.account_equity.le(0).sum()),
        max_daily_close_products=pos['max_daily_products'],daily_close_over4_days=pos['daily_over4_days'])
    return dict(path=str(path),role=role,daily=daily,fills=fills,segments=sf,rounds=rf,opened=of,accounting=accounting,metrics=curve,risk=risk,positions=pos,position_audit=position_audit,
        effective=effective,settings=settings,addon=addon,preflight=pre,acceptances=proofs,sources=sources,attempt_snapshot=frozen,database_sha256=sources[str(db)],sleeve_details=sleeves)


def plot(ledgers,path):
    os.environ.setdefault('MPLCONFIGDIR','/private/tmp/weekly-research-mpl')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    fig,(top,bottom)=plt.subplots(2,1,figsize=(13,8),sharex=True,gridspec_kw={'height_ratios':[2,1]})
    for role,color,label in [('baseline','#2467a6','A: weekly base / no addon'),('candidate','#c36f19','C: weekly base + short MA5/10 slope gate')]:
        d=ledgers[role]['daily'];top.plot(d.date,d.account_equity,lw=1.4,color=color,label=label)
        peak=np.maximum.accumulate(np.r_[CAPITAL,d.account_equity.to_numpy()])[1:]
        bottom.plot(d.date,(d.account_equity/peak-1)*100,lw=1.1,color=color)
    top.axhline(CAPITAL,color='#888',lw=.7,ls='--');top.legend(frameon=False,fontsize=9)
    top.set_ylabel('Modeled equity (CNY)');top.yaxis.set_major_formatter(FuncFormatter(lambda x,_:f'{x:,.0f}'))
    bottom.set_ylabel('Drawdown (%)');bottom.set_xlabel('Exchange trading date')
    for ax in [top,bottom]:ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
    m=ledgers['baseline']['metrics'];fig.suptitle('STAGE001 SHORT MA SLOPE / OFFLINE RESEARCH / NO PROMOTION / INDEPENDENT REVIEW PENDING\n'+f"{m['actual_start']} to {m['actual_end']}; original19; CNY150,000 each; MA5/10/20\nDaily next-open model; zero commission; static exchange margin x1.65",fontsize=11,fontweight='bold')
    fig.tight_layout(rect=[0,0,1,.9]);fig.savefig(path,dpi=170);plt.close(fig)


def build_artifacts(baseline_dir,candidate_dir,out_dir,figure):
    baseline_dir,candidate_dir=Path(baseline_dir).resolve(),Path(candidate_dir).resolve();out_dir,figure=Path(out_dir).resolve(),Path(figure).resolve()
    if baseline_dir==candidate_dir:raise ValueError('distinct_baseline_candidate_required')
    validate_output_paths(out_dir,figure,[baseline_dir,candidate_dir])
    ledgers={role:load_ledger(path,role) for role,path in [('baseline',baseline_dir),('candidate',candidate_dir)]}
    a,c=ledgers['baseline'],ledgers['candidate']
    if not a['daily'].date.equals(c['daily'].date) or any(a['preflight'][k]!=c['preflight'][k] for k in ['start','end']):raise ValueError('same_requested_and_actual_window_calendar_required')
    if a['preflight']['data_identity']!=c['preflight']['data_identity'] or a['database_sha256']!=c['database_sha256']:raise ValueError('same_data_identity_required')
    if a['settings']!=c['settings']:raise ValueError('same_actual_and_declared_strategy_settings_required')
    if a['effective']!=c['effective']:raise ValueError('same_effective_parameters_required')
    if {k:v for k,v in a['addon'].items() if k!='enabled'}!={k:v for k,v in c['addon'].items() if k!='enabled'}:raise ValueError('same_addon_configuration_except_enabled_required')
    sources={str(Path(__file__).resolve()):sha(__file__),str((BASETOOLS/'stage029_build_artifacts.py').resolve()):sha(BASETOOLS/'stage029_build_artifacts.py')}
    for ledger in ledgers.values():
        for key,digest in ledger['sources'].items():
            if key in sources and sources[key]!=digest:raise ValueError('comparison_conflicting_source_hash:'+key)
            sources[key]=digest
    arms={role:dict(attempt_path=l['path'],actual_strategy_class=l['settings'][0]['strategy_class'],metrics=l['metrics'],accounting=l['accounting'],risk=l['risk'],position_audit=l['position_audit'],sleeves=l['sleeve_details']['summaries'],addon_analysis=l['sleeve_details']['analysis'],database_sha256=l['database_sha256'],acceptance_files=sorted(l['acceptances']),terminal_open_positions=l['opened'].to_dict('records')) for role,l in ledgers.items()}
    gates={k:bool(c['metrics'][k]>=a['metrics'][k]) if a['metrics'][k] is not None and c['metrics'][k] is not None else None for k in ['end_equity','max_dd_pct','sharpe']}
    summary=dict(schema='stage001_same_source_short_ma_slope_comparison_v1',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),status='DERIVED_PENDING_INDEPENDENT_REVIEW',independent_review_verdict=None,production_qualified=False,promotion_decision='NO_PROMOTION',financial_replays=0,arms=arms,
        comparison={k:c['metrics'][k]-a['metrics'][k] if c['metrics'][k] is not None and a['metrics'][k] is not None else None for k in ['end_equity','total_return_pct','max_dd_pct','sharpe']},
        fixed_candidate_continue_gates=gates,fixed_candidate_result='PASS_FIXED_WINDOW_ONLY' if all(v is True for v in gates.values()) else 'MIXED_OR_FAIL_NO_RESCUE_TUNING',
        direct_daily_addon_net_pnl=0.0,base_capital_path_difference=c['sleeve_details']['summaries']['base']['ledger_net_pnl']-a['sleeve_details']['summaries']['base']['ledger_net_pnl'],
        contract=dict(requested_start=a['preflight']['start'],requested_end=a['preflight']['end'],actual_asof=a['metrics']['actual_end'],capital=CAPITAL,pool=sorted(POOL),execution_model=EXECUTION_MODEL,data_identity=a['preflight']['data_identity'],baseline_addon_configuration=a['addon'],candidate_addon_configuration=c['addon'],actual_margin_multiplier=1.65,legacy_broker10_multiplier=1.1),
        limitations=['Repeated historical development sample; no new PIT/OOS evidence and no parameter rescue scanning.',
            'Static original19 universe, zero commission, fixed slippage, and daily next-open model lack quote/depth/queue/capacity qualification.',
            'Historical main-contract mapping and source daily/epoch reconstruction limitations remain; accepted data is not a claim all vendor data is correct.',
            'Margin uses configured static exchange margin times1.65, not historical actual broker margin; legacy broker10 uses1.1.',
            'Native flat-to-flat rounds are exact-contract inventory rounds, not weekly logical parent rounds; roll contracts remain separate.',
            'Sleeve attribution follows recorded real-fill owner allocations. Ordinary total-inventory FIFO can close a different lot; its win rate is a separate statistic.',
            'Terminal open inventory is marked at real terminal closes with incurred costs; it is never synthetically closed or counted as a closed win.',
            'Derivation and accounting gates do not replace independent strategy/data/result review or production qualification.'],source_files_sha256=sources)
    require_close(summary['comparison']['end_equity'],summary['direct_daily_addon_net_pnl']+summary['base_capital_path_difference'],'direct_and_capital_path_difference')
    out_dir.parent.mkdir(parents=True,exist_ok=True)
    if not figure.is_relative_to(out_dir):figure.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.stage032_report_',dir=out_dir.parent) as temporary:
        temp=Path(temporary);tables=temp/'tables';tables.mkdir();pic=temp/'equity_drawdown.png'
        pd.DataFrame([row for l in ledgers.values() for row in annual_rows(l)]).to_csv(tables/'annual.csv',index=False)
        pd.DataFrame([row for l in ledgers.values() for row in product_rows(l)]).to_csv(tables/'products.csv',index=False)
        pd.DataFrame([dict(role=role,**row) for role,l in ledgers.items() for row in l['position_audit']['annual_product_contributions']]).to_csv(tables/'annual_products.csv',index=False)
        pd.DataFrame([dict(role=role,**l['metrics'],**{'fifo_'+k:v for k,v in l['accounting']['closed_fifo'].items()},**{'round_'+k:v for k,v in l['accounting']['complete_contract_rounds'].items()},**l['risk'],open_remaining_net_mtm=l['accounting']['open_remaining_net_mtm'],open_round_net_mtm=l['accounting']['open_round_net_mtm']) for role,l in ledgers.items()]).to_csv(tables/'summary.csv',index=False)
        for name,key in [('closed_fifo_segments.csv','segments'),('complete_contract_rounds.csv','rounds'),('terminal_open_rounds.csv','opened')]:
            pd.concat([l[key].assign(role=role) for role,l in ledgers.items()],ignore_index=True).to_csv(tables/name,index=False)
            pd.concat([l['sleeve_details'][key].assign(role=role) for role,l in ledgers.items()],ignore_index=True).to_csv(tables/('owner_'+name),index=False)
        pd.DataFrame([dict(role=role,sleeve=sleeve,**{k:v for k,v in s.items() if not isinstance(v,dict)},**{'fifo_'+k:v for k,v in s['closed_fifo'].items()},**{'round_'+k:v for k,v in s['complete_contract_rounds'].items()}) for role,l in ledgers.items() for sleeve,s in l['sleeve_details']['summaries'].items()]).to_csv(tables/'sleeve_summary.csv',index=False)
        entry_frames=[l['sleeve_details']['entries'].assign(role=role) for role,l in ledgers.items()]
        pd.concat([f for f in entry_frames if not f.empty] or entry_frames[:1],ignore_index=True).to_csv(tables/'addon_entries.csv',index=False)
        for role,l in ledgers.items():l['daily'][['date','account_equity','net_pnl','slippage','commission','trade_count']].to_csv(tables/(role+'_daily.csv'),index=False)
        plot(ledgers,pic)
        summary['short_ma_slope_gate']={role:ledger['acceptances']['short_ma_slope_acceptance.json'] for role,ledger in ledgers.items()}
        summary['output_files_sha256']={str(out_dir/p.name):sha(p) for p in sorted(tables.glob('*.csv'))};summary['output_files_sha256'][str(figure)]=sha(pic)
        (tables/'comparison.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        manifest=dict(schema='stage032_report_delivery_manifest_v1',comparison_sha256=sha(tables/'comparison.json'),files_sha256={**summary['output_files_sha256'],str(out_dir/'comparison.json'):sha(tables/'comparison.json')},self_hash_excluded=True,independent_review_verdict=None)
        (tables/'delivery_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        verify_sources(sources)
        for l in ledgers.values():
            if snapshot_dir(l['path'])!=l['attempt_snapshot']:raise ValueError('attempt_file_set_or_bytes_changed:'+l['path'])
        validate_output_paths(out_dir,figure,[baseline_dir,candidate_dir])
        if figure.is_relative_to(out_dir):
            (tables/figure.relative_to(out_dir)).parent.mkdir(parents=True,exist_ok=True);os.link(pic,tables/figure.relative_to(out_dir));os.rename(tables,out_dir)
        else:
            os.link(pic,figure)
            try:os.rename(tables,out_dir)
            except Exception:figure.unlink();raise
    return dict(status='DERIVED_PENDING_INDEPENDENT_REVIEW',outputs=[str(out_dir),str(figure)],financial_replays=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True);parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--figure',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(build_artifacts(args.baseline,args.candidate,args.out,args.figure),ensure_ascii=False))

if __name__=='__main__':main()
