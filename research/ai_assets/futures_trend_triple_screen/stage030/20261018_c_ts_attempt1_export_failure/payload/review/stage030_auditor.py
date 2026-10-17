"""Independent C_TS cash, inventory and ordered-entry evidence audit.

No engine, market database, model or network is imported. --self-test uses only
small synthetic ledgers. Actual review requires explicit completed exit evidence;
this tool never watches for a run to finish and never restarts financial work.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from stage001_compare import evaluate_metrics

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE.parents[2]
SOURCE = LINE / 'outputs/stage028_ordered_account/C_TS'
OUT = LINE / 'outputs/stage030_independent_account_review'
A0 = LINE / 'outputs/stage001_first_screen/A0_attempt2'
A0_REVIEW = LINE / 'outputs/stage001_independent_review/review_receipt.json'
A0_REVIEW_SHA = '5317fa98054c7469e0dc983fdb5678c05678bd382f616f1ec4b5bb59c4d4356d'
RETRY = 'stage847_intraday_reentry_at_original_entry'
CONDITIONAL = 'stage028_conditional_initial_stop_entry'
SCOPE = 'offline_ordered_initial_entry_C_TS_vs_reused_A0_attempt2'
NAMES = ['summary.json','daily.csv','trades.csv','positions.csv',
    'execution_proxy_usage.csv','execution_clock.csv','internal_equity_daily.csv',
    'entry_candidates.csv','effective_parameters.json','actual_strategy_settings.json',
    'run_provenance.json','metrics.json','minute_scan_requests.csv',
    'rollover_shape_same_volume.csv','ordered_gate_audit.csv','ordered_fill_audit.csv',
    'ordered_execution_audit.csv','ordered_audits.json','qualified_wait_audit.json',
    'input_manifest.json','preflight_used.json','runner_used.py',
    'stage028_ordered_engine.py','stage028_ordered_strategy.py',
    'protocol_used.md','holding_contract_used.md','data_stack_manifest.json']


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576), b''): h.update(block)
    return h.hexdigest()


def read(path): return json.loads(Path(path).read_text())
def csv(path): return pd.read_csv(path).fillna('')
def stamp(value):
    result=pd.Timestamp(value)
    return result.tz_convert('Asia/Shanghai').tz_localize(None) if result.tzinfo is not None else result


def close(actual, expected, name, atol=1e-6):
    a=np.asarray(actual,dtype=float); b=np.asarray(expected,dtype=float)
    assert np.isfinite(a).all() and np.isfinite(b).all(), ('nonfinite',name)
    residual=float(np.max(np.abs(a-b))) if a.size else 0.0
    assert residual < atol, (name,residual)
    return residual


def write(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def normalize(value):
    if isinstance(value,dict):
        return {key:('<empty_supply_demand>' if key=='supply_demand_signal_path' else normalize(item))
                for key,item in value.items()}
    if isinstance(value,list): return [normalize(item)for item in value]
    return value


def reconstruct_metrics(d,t,capital):
    equity=d.account_equity.to_numpy(dtype=float)
    changes=np.zeros(len(equity)); changes[1:]=equity[1:]/equity[:-1]-1
    std=changes.std(ddof=1)
    ratio=d.broker10_total_margin_exact.to_numpy(dtype=float)/equity*100
    return dict(end_equity=float(equity[-1]),total_return_pct=float((equity[-1]/capital-1)*100),
        max_dd_pct=float((equity/np.maximum.accumulate(equity)-1).min()*100),
        sharpe=float(changes.mean()/std*math.sqrt(252))if std>0 else 0.,
        min_equity=float(equity.min()),total_slippage=float(t.independent_slippage.sum()),
        total_commission=float(t.independent_commission.sum()),total_trade_count=len(t),
        max_broker10_margin_to_equity_pct=float(ratio.max()),
        days_over_100pct=int((ratio>100+1e-9).sum()),days_over_90pct=int((ratio>90+1e-9).sum()),
        days_equity_below_zero=int((equity<=0).sum()))


def reconstruct_episodes(t,candidates,conditional,rollover):
    """Actual OPEN order link is authoritative for conditional mother identity."""
    active={}; root_by_order={}; closed=[]; links=[]; roll_links=[]; mother_links=[]
    actual_conditional=conditional.set_index('order_id',verify_integrity=True).to_dict('index') if len(conditional)else{}
    opened=candidates.loc[candidates.candidate_status.eq('opened')]
    pending=candidates.loc[candidates.candidate_status.eq('conditional_pending')]
    for row in t.to_dict('records'):
        symbol=row['vt_symbol']; opening=row['offset']=='开'; order=row['order_id']
        if symbol not in active:
            assert opening,(symbol,row['trade_id'],'close_without_position')
            retry=row['price_source']==RETRY
            if retry:
                parent=order.split('.intraday.')[0]
                assert '.intraday.' in order and parent!=order and parent in root_by_order
                original=t.loc[t.order_id.eq(parent)&t.offset.eq('开')]
                assert len(original)==1 and original.iloc[0].vt_symbol==symbol and original.iloc[0].date==row['date']
                assert stamp(original.iloc[0].execution_datetime)<stamp(row['execution_datetime'])
                root,context=root_by_order[parent]
                links.append(dict(root=root,retry_fill=row['trade_id'],parent_order=parent))
            else:
                root=row['trade_id'];direction='long'if row['signed_volume']>0 else'short'
                pool=pending if order in actual_conditional else opened
                matches=pool.loc[pool.date.eq(row['signal_date'])&pool.contract_vt_symbol.eq(symbol)&pool.direction.eq(direction)]
                if order in actual_conditional:
                    evidence=actual_conditional[order]
                    assert row['price_source']==CONDITIONAL
                    assert evidence['contract']==symbol and evidence['signal_day']==row['signal_date']
                    assert evidence['execution_day']==row['date']
                    close(row['volume'],evidence['volume'],'conditional mother quantity')
                    close(row['price'],evidence['fill_price'],'conditional mother price')
                    assert len(matches)==1,('conditional_candidate_not_unique',order,len(matches))
                else: assert row['price_source']!=CONDITIONAL,('conditional_without_actual_link',order)
                if len(matches)==1:
                    context=str(matches.iloc[0].entry_context)
                    mother_links.append(dict(root=root,order_id=order,candidate_index=int(matches.iloc[0].candidate_index),
                                             kind='conditional'if order in actual_conditional else'ordinary'))
                else:
                    assert len(matches)==0,('mother_candidate_not_unique',order,len(matches))
                    continuation=rollover.loc[rollover.date.eq(row['signal_date'])&rollover.target_contract_vt_symbol.eq(symbol)&
                        rollover.direction.eq(direction)&rollover.status.eq('targeted')&pd.to_numeric(rollover.final_volume).ge(row['volume'])]
                    assert len(continuation)==1,(symbol,row['trade_id'],'unproven_rollover_open')
                    r=continuation.iloc[0]; source_contract=r.old_contract_vt_symbol
                    source_closes=t.loc[t.vt_symbol.eq(source_contract)&t.date.eq(row['date'])&t.offset.ne('开')&
                        t.signal_date.eq(row['signal_date'])]
                    assert len(source_closes)>0,('roll_without_actual_old_contract_close',order)
                    assert pd.to_numeric(source_closes.volume).sum()+1e-9>=row['volume']
                    assert max(stamp(x)for x in source_closes.execution_datetime)<=stamp(row['execution_datetime'])
                    context='rollover_reopen'
                    roll_links.append(dict(fill=row['trade_id'],signal_date=row['signal_date'],source_contract=source_contract,
                        target_contract=symbol,diagnostic_index=int(r.diagnostic_index),volume=row['volume'],
                        source_close_trade_ids=';'.join(source_closes.trade_id)))
            root_by_order[order]=(root,context)
            active[symbol]=dict(root=root,entry_context=context,first_fill=row['trade_id'],entry_date=row['date'],
                symbol=symbol,quantity=0.,net_cash=0.,costs=0.,retry=retry)
        cycle=active[symbol]
        assert (cycle['quantity']==0 or cycle['quantity']*row['signed_volume']>0) if opening else (
            cycle['quantity']*row['signed_volume']<0 and abs(cycle['quantity'])+1e-9>=row['volume'])
        cycle['quantity']+=row['signed_volume'];cycle['net_cash']+=row['independent_cash']
        cycle['costs']+=row['independent_slippage']+row['independent_commission']
        if abs(cycle['quantity'])<1e-9:
            cycle.update(last_fill=row['trade_id'],exit_date=row['date']);closed.append(cycle);del active[symbol]
    cycles=pd.DataFrame(closed)
    live_roots={x['root']for x in active.values()}
    episodes=cycles.loc[~cycles.root.isin(live_roots)].groupby('root',as_index=False).agg(
        net_pnl=('net_cash','sum'),costs=('costs','sum'),cycles=('root','size'),entry_context=('entry_context','first'))
    return cycles,episodes,active,links,roll_links,mother_links


def audit_inventory(source,d,t,parameters,settings):
    """One chunked positions pass, independent sparse fill-to-inventory lookup."""
    days=d.date.tolist();idx={day:i for i,day in enumerate(days)};n=len(days)
    marks=np.zeros(n);pnl=np.zeros(n);margin=np.zeros(n);active_count=np.zeros(n)
    size_map=parameters['contract_sizes']; margin_map={}
    for item in settings['margin_ratio_overrides'].split(','):
        if item.strip(): key,value=item.split('=');margin_map[key]=float(value)
    inventory={}
    for symbol,group in t.groupby('vt_symbol',sort=False):
        delta=group.groupby('date').signed_volume.sum()
        indices=np.array([idx[x]for x in delta.index]);order=np.argsort(indices)
        inventory[symbol]=(indices[order],delta.to_numpy(dtype=float)[order].cumsum())
    seen_nonzero=set();last_marks={};max_start=max_end=0.;rows=0;products=defaultdict(set)
    for p in pd.read_csv(source/'positions.csv',usecols=['date','vt_symbol','start_pos','end_pos','close_price','net_pnl'],chunksize=250000):
        assert p.date.isin(idx).all();assert not p.duplicated(['date','vt_symbol']).any()
        for symbol,g in p.groupby('vt_symbol',sort=False):
            di=g.date.map(idx).to_numpy(dtype=int);sz=float(size_map[symbol])
            assert np.isfinite(g[['start_pos','end_pos','close_price','net_pnl']].to_numpy(dtype=float)).all()
            changes,quantities=inventory.get(symbol,(np.array([],dtype=int),np.array([],dtype=float)))
            def qty(indices):
                at=np.searchsorted(changes,indices,side='right')-1
                return np.where(at>=0,quantities[np.maximum(at,0)],0.) if len(changes)else np.zeros(len(indices))
            max_start=max(max_start,close(g.start_pos,qty(di-1),'start inventory'))
            max_end=max(max_end,close(g.end_pos,qty(di),'end inventory'))
            np.add.at(marks,di,g.end_pos.to_numpy(dtype=float)*g.close_price.to_numpy(dtype=float)*sz)
            np.add.at(pnl,di,g.net_pnl.to_numpy(dtype=float))
            mr=margin_map.get(symbol,float(settings.get('default_margin_ratio',.1)))
            np.add.at(margin,di,abs(g.end_pos.to_numpy(dtype=float))*np.maximum(g.close_price.to_numpy(dtype=float),0)*sz*mr)
            live=g.end_pos.ne(0);np.add.at(active_count,di,live.to_numpy(dtype=int))
            for day in g.loc[live,'date']: seen_nonzero.add((day,symbol));products[day].add(''.join(c for c in symbol.split('.')[0]if c.isalpha())+'.'+symbol.rsplit('.',1)[1])
            end=g.loc[g.date.eq(days[-1])]
            if len(end): assert len(end)==1;last_marks[symbol]=float(end.close_price.iloc[0])
        rows+=len(p)
    for symbol,(di,q)in inventory.items():
        for i in range(n):
            at=np.searchsorted(di,i,side='right')-1
            if at>=0 and q[at]!=0:assert(days[i],symbol)in seen_nonzero,('missing_nonzero_position',days[i],symbol)
    broker=margin*float(settings['stage830_broker_margin_multiplier'])
    residuals=dict(inventory_start=max_start,inventory_end=max_end,
        position_net_pnl=close(pnl,d.net_pnl,'position net pnl'),
        position_margin=close(margin,d.c3_margin_exact,'position exchange margin'),
        broker_margin=close(broker,d.broker10_total_margin_exact,'broker margin'),
        active_contracts=close(active_count,d.c3_active_contracts,'active contracts'),
        active_products=close([len(products[x])for x in days],d.c3_active_products,'active products'))
    return marks,last_marks,residuals,rows


def ordered_evidence(source,t,candidates,parameters,minutes,d):
    fill=csv(source/'ordered_fill_audit.csv');events=csv(source/'ordered_execution_audit.csv');gate=csv(source/'ordered_gate_audit.csv')
    audits=read(source/'ordered_audits.json')
    assert len(fill)==len(audits['fill']) and len(events)==len(audits['execution']) and len(gate)==len(audits['decision'])
    assert fill.intent_id.is_unique and fill.order_id.is_unique and events.intent_id.is_unique
    assert events.status.isin(['filled','expired_untriggered','expired_past_day']).all()
    # A one-day intent cannot remain past-due after all actual account dates.
    assert not events.status.eq('expired_past_day').any()
    assert set(events.loc[events.status.eq('filled'),'intent_id'])==set(fill.intent_id)
    dates=d.date.tolist();next_day=dict(zip(dates,dates[1:]))
    pending=gate.loc[gate.candidate_status.eq('conditional_pending')]
    assert pending.intent_id.is_unique
    assert set(events.intent_id).issubset(set(pending.intent_id))
    for row in events.to_dict('records'):
        assert row['execution_day']==next_day[row['signal_day']]
        assert row['setup_day']<row['signal_day'] and row['weekly_asof'][:10]<row['signal_day']
        p=pending.loc[pending.intent_id.eq(row['intent_id'])];assert len(p)==1
        close(row['quantity'],p.native_volume.iloc[0],'native frozen quantity')
        plan=candidates.loc[candidates.date.eq(row['signal_day'])&candidates.product_vt_symbol.eq(row['product'])&
            candidates.contract_vt_symbol.eq(row['contract'])&candidates.candidate_status.eq('conditional_pending')]
        assert len(plan)==1;plan=plan.iloc[0]
        close(row['quantity'],plan.selected_volume,'candidate frozen quantity')
        close(row['forecast_risk_amount'],plan.risk_per_contract*row['quantity'],'forecast risk')
        close(row['forecast_margin_amount'],plan.margin_per_contract*row['quantity'],'forecast margin')
        req=minutes.loc[minutes.vt_symbol.eq(row['contract'])&minutes.trading_date.eq(row['execution_day'])]
        assert len(req.loc[req.requested_start.eq(req.session_start)])>=1,('unqualified_full_conditional_session',row['intent_id'])
        if row['status']!='filled':
            assert row['intent_id']not in set(fill.intent_id)
            assert row['order_id']=='' and row['fill_price']=='',('untriggered_phantom_order',row)
            continue
        f=fill.loc[fill.intent_id.eq(row['intent_id'])].iloc[0]
        actual=t.loc[t.order_id.eq(f.order_id)&t.offset.eq('开')]
        assert len(actual)==1;actual=actual.iloc[0]
        assert actual.price_source==CONDITIONAL
        assert actual.date==row['execution_day'] and actual.signal_date==row['signal_day']
        assert stamp(actual.execution_datetime)==stamp(row['execution_datetime'])==stamp(f.execution_datetime)
        close(actual.volume,row['quantity'],'actual native q');close(actual.price,row['fill_price'],'actual fill price')
        close(f.stop_price,plan.stop_price,'frozen S')
        size=float(parameters['contract_sizes'][row['contract']]);tick=float(parameters['priceticks'][row['contract']])
        risk=max(abs(actual.price-plan.stop_price)*size,max(tick*size,1.))*actual.volume
        margin=actual.price*size*plan.margin_ratio*actual.volume
        close(row['actual_risk_amount'],risk,'actual risk');close(row['actual_margin_amount'],margin,'actual margin')
        close(f.actual_risk_amount,risk,'fill risk');close(f.actual_margin_amount,margin,'fill margin')
        assert len(req.loc[req.requested_start.map(stamp).eq(stamp(f.execution_datetime))])>=1
    unknown=gate.loc[gate.baseline_fallback.map(lambda x:str(x).lower()in('true','1'))&gate.native_status.eq('opened')]
    known_ordinary=t.loc[t.offset.eq('开')&t.price_source.ne(CONDITIONAL)&t.price_source.ne(RETRY)]
    # Ordinary openings also include proven rolls and existing-layer adds; only
    # native flat_entry ordinary candidates require unknown fallback evidence.
    for row in known_ordinary.to_dict('records'):
        plan=candidates.loc[candidates.date.eq(row['signal_date'])&candidates.contract_vt_symbol.eq(row['vt_symbol'])&
            candidates.candidate_status.eq('opened')&candidates.entry_context.eq('flat_entry')]
        if len(plan):
            assert len(plan)==1
            match=unknown.loc[unknown.date.eq(row['signal_date'])&unknown.contract.eq(row['vt_symbol'])]
            assert len(match)==1,('ordinary_flat_not_unknown_fallback',row['trade_id'])
    filled=events.loc[events.status.eq('filled')].copy()
    stats=dict(conditional_intents=len(events),conditional_fills=len(fill),
        untriggered_intents=int(events.status.eq('expired_untriggered').sum()),
        observed_native_selected=int(gate.native_status.eq('opened').sum()),
        unknown_fallback_selected=len(unknown),end_pending=len(audits['pending']),
        full_session_required_for_untriggered=True,untriggered_actual_orders=0,
        actual_quantity_recomputed_at_fill=False,
        actual_risk_above_forecast_count=int((pd.to_numeric(filled.actual_risk_amount)>pd.to_numeric(filled.forecast_risk_amount)+1e-6).sum()),
        actual_margin_above_forecast_count=int((pd.to_numeric(filled.actual_margin_amount)>pd.to_numeric(filled.forecast_margin_amount)+1e-6).sum()))
    for field in('risk','margin'):
        a=pd.to_numeric(filled['actual_'+field+'_amount']);f=pd.to_numeric(filled['forecast_'+field+'_amount'])
        stats['max_actual_to_forecast_'+field+'_ratio']=float((a/f).max())if len(filled)else None
        stats['max_actual_minus_forecast_'+field+'_amount']=float((a-f).max())if len(filled)else None
    return fill,stats


def audit_provenance(source,exit_path,hashes):
    evidence=read(exit_path);assert evidence.get('exit_code')==0 and evidence.get('terminal_observed')is True
    assert evidence.get('source')==str(source) and evidence.get('summary_sha256')==hashes['summary.json']
    prov=read(source/'run_provenance.json');summary=read(source/'summary.json');pre=read(source/'preflight_used.json')
    assert not(source/'run_failure.json').exists()
    for x in(prov,summary):
        assert x['arm']=='C_TS'and x['status']=='completed_pending_independent_review'
        assert x['result_scope']==SCOPE and x['production_qualified']is False and x['financial_replays']==1
    for key in('all_consumed_inputs_unchanged_during_run','strict_minutes','actual_settings_equal_accepted_A',
                'parameters_equal_accepted_A','actual_daily_dates_equal_accepted_A0','original_u_close_quantity_and_stop_frozen'):
        assert prov[key]is True,key
    for key in('fill_time_broker_budget_rechecked','actual_gap_risk_bounded_by_u_gate'):assert prov[key]is False,key
    assert prov['captured_bar_failure_count']==0 and prov['broker_connections']==0 and prov['order_api_count']==0 and prov['cancel_api_count']==0
    assert summary['strict_minutes']['missing_bar_count']==0 and summary['strict_minutes']['captured_bar_failures']==0
    manifest=read(source/'input_manifest.json');assert manifest==prov['input_fingerprints']==summary['input_fingerprints']
    checks={}
    # Revalidate implementation/contract snapshots and compact receipts. Do not
    # rehash the accepted multi-million-minute cache or all 1,950 raw sources.
    snapshots={'runner_used.py':'source_adapter_sha256','protocol_used.md':'protocol_sha256','holding_contract_used.md':'holding_contract_sha256','data_stack_manifest.json':'data_stack_sha256'}
    for name,key in snapshots.items():assert hashes[name]==prov[key];checks[name]=hashes[name]
    for name,value in prov['source_modules_sha256'].items():assert hashes[name]==value;checks[name]=value
    for name,key in(('stage028_ordered_strategy.py','stage028_ordered_strategy.py'),('stage028_ordered_engine.py','stage028_ordered_engine.py'),('runner_used.py','stage028_run_ordered.py')):
        assert digest(LINE/'tools'/key)==hashes[name]
    for path,value in prov['correctness_code_sha256'].items():assert digest(ROOT/path)==value;checks[path]=value
    stack=read(source/'data_stack_manifest.json')
    assert stack['full_excludes_remaining_source859']is True and stack['anchor859_only_stage010_canonical_first_key']is True
    for path_key,sha_key in(('gate_review_path','gate_review_sha256'),):
        path=Path(stack[path_key]);assert digest(path)==stack[sha_key];checks[str(path)]=stack[sha_key]
    wait=read(source/'qualified_wait_audit.json')
    assert wait['initial_qualification']['scope']=='inherited_accepted_baseline_plus_usage_limited859_not_global_price_recertification'
    assert wait['initial_qualification']['anchor_only_rights']>=wait['initial_qualification']['appended_anchor_keys']
    for row in wait['gate']:
        if row['event']=='data_qualified_appended':
            assert row['old_keys_changed']==0
            path=Path(row['receipt_path']);assert digest(path)==row['receipt_sha256'];checks[str(path)]=row['receipt_sha256']
    baseline=prov['reused_A0'];assert digest(A0_REVIEW)==A0_REVIEW_SHA==baseline['review_sha256']
    review=read(A0_REVIEW);assert 'A0_attempt2'in review['financial_accounts_reviewed']
    assert review['remaining_implementation_p0']==review['remaining_implementation_p1']==0
    for name,value in baseline['artifact_sha256'].items():assert digest(A0/name)==value;checks[str(A0/name)]=value
    assert normalize(read(source/'effective_parameters.json'))==normalize(read(A0/'effective_parameters.json'))
    actual=read(source/'actual_strategy_settings.json');reference=read(A0/'actual_strategy_settings.json')
    assert len(actual)==1 and actual[0]['supply_demand_signal_rows']==0
    assert normalize(actual[0]['actual'])==normalize(reference[0]['actual'])
    assert pre['parameters_equal_accepted_A']is True and pre['requested_settings_equal_accepted_A']is True
    return prov,actual[0]['actual'],checks


def run(exit_path):
    source=SOURCE.resolve();assert source==SOURCE.resolve()
    assert Path(exit_path).is_file(),'explicit root terminal exit evidence required'
    hashes={name:digest(source/name)for name in NAMES}
    prov,settings,checked=audit_provenance(source,exit_path,hashes)
    d=csv(source/'daily.csv');assert d.date.is_unique and d.date.tolist()==sorted(d.date.tolist())
    a_dates=pd.read_csv(A0/'daily.csv',usecols=['date']).date.tolist()
    assert d.date.tolist()==a_dates and d.date.iloc[0]=='2020-01-02' and d.date.iloc[-1]=='2026-10-14'
    t=csv(source/'trades.csv');u=csv(source/'execution_proxy_usage.csv');c=csv(source/'execution_clock.csv')
    assert all(x.trade_id.is_unique for x in(t,u,c))and set(t.trade_id)==set(u.trade_id)==set(c.trade_id)
    assert t.date.eq(t.trading_date).all()
    joined=t.merge(c,on='trade_id',suffixes=('','_clock'),validate='one_to_one')
    for key in('trading_date','vt_symbol','direction','offset'):assert joined[key].eq(joined[key+'_clock']).all(),key
    for key in('price','volume'):close(joined[key],joined[key+'_clock'],'clock '+key)
    t=t.merge(u[['trade_id','signal_date','price_source','execution_datetime','signal_order_id']],on='trade_id',validate='one_to_one')
    t['fill_number']=t.trade_id.str.rsplit('.',n=1).str[-1].astype(int)
    t=t.sort_values('fill_number').reset_index(drop=True)
    assert t.fill_number.tolist()==list(range(1,len(t)+1))
    times=[stamp(x)for x in t.execution_datetime];assert times==sorted(times),'actual shared queue timestamps not ordered'
    assert all(stamp(x).date().isoformat()<=y for x,y in zip(t.execution_datetime,t.date))
    assert (pd.to_numeric(t.volume)>0).all()and np.equal(t.volume,np.round(t.volume)).all()
    close(t.signed_volume,t.volume*t.direction.map({'多':1,'空':-1}),'signed direction')
    parameters=read(source/'effective_parameters.json');sizes=t.vt_symbol.map(parameters['contract_sizes']).astype(float)
    t['independent_slippage']=t.volume*sizes*t.vt_symbol.map(parameters['slippages']).astype(float)
    t['independent_commission']=t.volume*sizes*t.price*t.vt_symbol.map(parameters['rates']).astype(float)
    t['independent_cash']=-t.signed_volume*sizes*t.price-t.independent_slippage-t.independent_commission
    capital=float(d.account_capital.iloc[0]);assert capital==150000 and d.account_capital.eq(capital).all()
    marks,last_marks,residuals,position_rows=audit_inventory(source,d,t,parameters,settings)
    fillcash=t.groupby('date').independent_cash.sum().reindex(d.date,fill_value=0).cumsum().to_numpy()
    independent_equity=capital+fillcash+marks
    residuals['cashflow_equity']=close(independent_equity,d.account_equity,'cashflow equity')
    residuals['daily_pnl_equity']=close(capital+d.net_pnl.cumsum(),d.account_equity,'pnl cumulative equity')
    internal=d.merge(csv(source/'internal_equity_daily.csv'),on='date',validate='one_to_one');assert len(internal)==len(d)
    residuals['internal_equity']=close(internal.account_equity,internal.estimated_equity,'internal equity')
    for field in('slippage','commission'):
        reconstructed=t.groupby('date')['independent_'+field].sum().reindex(d.date,fill_value=0)
        residuals[field]=close(reconstructed,d[field],'daily '+field)
    close(t.groupby('date').size().reindex(d.date,fill_value=0),d.trade_count,'daily fill count')
    metrics=reconstruct_metrics(d,t,capital);reported=read(source/'metrics.json')
    for key,value in metrics.items():
        if key!='total_commission':close(value,reported[key],'reported metric '+key,atol=1e-7)
    candidates=csv(source/'entry_candidates.csv');rollover=csv(source/'rollover_shape_same_volume.csv');minutes=csv(source/'minute_scan_requests.csv')
    assert minutes.missing_bar_count.eq(0).all()and minutes.coverage_status.eq('complete').all()
    close(minutes.expected_bar_count,minutes.actual_bar_count,'complete minute counts')
    assert minutes.requested_start.map(stamp).eq(minutes.actual_first_time.map(stamp)).all()
    fill,ordered=ordered_evidence(source,t,candidates,parameters,minutes,d)
    cycles,episodes,active,retries,rolls,mothers=reconstruct_episodes(t,candidates,fill,rollover)
    open_mtm=sum(v['net_cash']+v['quantity']*last_marks[sym]*parameters['contract_sizes'][sym]for sym,v in active.items())
    residuals['cycles_and_open_mtm']=close(cycles.net_cash.sum()+open_mtm,d.net_pnl.sum(),'cycles plus open mtm')
    a_metrics=read(A0/'metrics.json');decision=evaluate_metrics(a_metrics,metrics)
    result=dict(reviewed_at=datetime.now().astimezone().isoformat(timespec='seconds'),reviewer='ordered_financial_auditor',
        source=str(source),arm='C_TS',status='independent_exported_cash_inventory_ordered_checks_passed',
        scope='one_completed_offline_C_TS_account_exported_economics_and_order_identity; accepted_A0_reused',
        source_hashes=hashes,completion_evidence_sha256=digest(exit_path),checked_compact_inputs=checked,
        source_input_count=len(prov['input_fingerprints']),reconstructed_metrics=metrics,residuals=residuals,
        actual_daily_dates=len(d),positions_rows_streamed_once=position_rows,ordered_execution=ordered,
        closed_contract_cycles=len(cycles),complete_mother_order_episodes=len(episodes),
        mother_order_episode_wins=int(episodes.net_pnl.gt(1e-6).sum()),
        mother_order_episode_win_rate_pct=float(episodes.net_pnl.gt(1e-6).mean()*100),
        confirmed_retry_parent_links=len(retries),confirmed_rollover_reopen_links=len(rolls),end_open_contracts=len(active),
        end_open_net_mtm=float(open_mtm),episode_definition='actual opening order plus same-day retry; roll remains distinct episode with actual old-close lineage; still-open mother excluded',
        seven_gates=decision,minute_scan_rows=len(minutes),
        evidence_limits=['broker margin reconstructed at daily close; full-minute point-in-time portfolio margin peak not established',
            'accepted source859 limited-use receipts inherited; no global minute/raw-source requalification',
            'holding suffix and first-bar-open behavior require frozen source and focused causal tests; exported requests attest actual suffix reads',
            'single historical path with prior research selection; no new strict OOS, multistart or 2x-cost qualification'],
        p0_findings=0,p1_findings=0,p2_findings=0,financial_engine_runs_by_reviewer=0,model_training_runs=0,
        promotion_allowed=False,production_qualified=False)
    OUT.mkdir(parents=True,exist_ok=True)
    for name,frame in [('independent_cycles.csv',cycles),('independent_mother_order_episodes.csv',episodes),
        ('independent_retry_links.csv',pd.DataFrame(retries)),('independent_rollover_open_links.csv',pd.DataFrame(rolls)),
        ('independent_mother_candidate_links.csv',pd.DataFrame(mothers))]:frame.to_csv(OUT/name,index=False)
    pd.DataFrame({'date':d.date,'independent_equity':independent_equity,'daily_reported_equity':d.account_equity}).to_csv(OUT/'independent_equity.csv',index=False)
    assert all(digest(source/name)==value for name,value in hashes.items()),'source changed during audit'
    result['review_script_sha256']=digest(__file__)
    write(OUT/'account_checks.json',result)
    return result


def self_test():
    """Necessary regression: conditional_pending, exact parent retry and live exclusion."""
    rows=[('T.1','O.1','开',2,100.,'2020-01-02T09:30',CONDITIONAL),
          ('T.2','O.1.intraday.1','平',-2,95.,'2020-01-02T09:31','stage847_intraday_05r_initial_stop'),
          ('T.3','O.1.intraday.2','开',2,100.,'2020-01-02T09:32',RETRY),
          ('T.4','O.1.intraday.3','平',-2,105.,'2020-01-02T09:33','exit')]
    def ledger(rows):
        return pd.DataFrame([dict(trade_id=tid,order_id=oid,offset=off,signed_volume=q,volume=abs(q),price=price,
            execution_datetime=tm,price_source=src,vt_symbol='x.SHFE',date='2020-01-02',signal_date='2020-01-01',
            independent_cash=-q*price-1,independent_slippage=1.,independent_commission=0.)for tid,oid,off,q,price,tm,src in rows])
    candidates=pd.DataFrame([dict(candidate_index=1,date='2020-01-01',contract_vt_symbol='x.SHFE',direction='long',candidate_status='conditional_pending',entry_context='flat_entry')])
    fill=pd.DataFrame([dict(order_id='O.1',contract='x.SHFE',signal_day='2020-01-01',execution_day='2020-01-02',volume=2,fill_price=100)])
    cycles,episodes,active,links,_,mothers=reconstruct_episodes(ledger(rows),candidates,fill,pd.DataFrame())
    assert len(cycles)==2 and len(episodes)==1 and len(links)==1 and len(mothers)==1 and not active
    close(episodes.net_pnl.iloc[0],-4.,'fixture retry costs')
    _,episodes,active,_,_,_=reconstruct_episodes(ledger(rows[:-1]),candidates,fill,pd.DataFrame())
    assert len(episodes)==0 and len(active)==1,'live retry root must exclude original closed cycle'
    broken=fill.copy();broken.loc[0,'order_id']='O.other'
    try:reconstruct_episodes(ledger(rows),candidates,broken,pd.DataFrame())
    except AssertionError:pass
    else:raise AssertionError('fixture accepted conditional without exact actual order link')
    return dict(status='finite_nonfinancial_fixtures_passed',fixtures=3,financial_engine_runs=0,source_C_TS_accessed=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__);actions=parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--self-test',action='store_true');actions.add_argument('--completion-evidence',type=Path)
    args=parser.parse_args()
    result=self_test()if args.self_test else run(args.completion_evidence)
    print(json.dumps(result if args.self_test else {k:result[k]for k in('status','reconstructed_metrics','seven_gates')},ensure_ascii=False))


if __name__=='__main__':main()
