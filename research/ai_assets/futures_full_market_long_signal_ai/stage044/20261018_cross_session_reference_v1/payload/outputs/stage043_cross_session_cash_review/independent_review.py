"""One independent saved-output cash review; no strategy/SQL/model invocation."""
import argparse
from datetime import datetime
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import time
import numpy as np
import pandas as pd
from cash_review_core import replay_fill_cash,fill_days_to_daily,verify_saved_quantities,position_totals,summary_metrics

ROOT=Path('/Users/mac/Desktop/fian');LINE=ROOT/'research/lines/futures_full_market_long_signal_ai'
OUT=LINE/'outputs/stage043_cross_session_cash_review'
PROTOCOL_SHA='58fe0f80de248f1d3095ac9ef859c0cb9bd84e369809a466f2b554dd38195466'
SOURCE_SHA='ca40a4cf7b761b34f70d973a943723601d0ecf5fc355da3559d5bcbeff36661d'
SCENARIOS={'base':dict(fee_min=2.,fee_bps=.0001,slip_bps=.0001,slip_ticks=1,margin_floor=.20),
           'stress':dict(fee_min=6.,fee_bps=.0003,slip_bps=.0003,slip_ticks=3,margin_floor=.40)}
ERRORS={}


def sha(raw):return hashlib.sha256(raw).hexdigest()
def bound(item):
    raw=Path(item['path']).read_bytes();assert sha(raw)==item['sha256'],item['path']
    if 'bytes' in item:assert len(raw)==item['bytes'],item['path']
    return raw
def csv(path):return pd.read_csv(path,dtype=str,keep_default_na=False)
def number(series):return np.asarray([float(v) if str(v)!='' else np.nan for v in series],dtype=float)
def numeric(frame,columns):
    for c in columns:
        if c in frame:frame[c]=number(frame[c])
    return frame
def compare(actual,expected,key,atol=5e-6,rtol=2e-11):
    a=np.asarray(actual,dtype=float);b=np.asarray(expected,dtype=float);assert a.shape==b.shape,(key,a.shape,b.shape)
    assert np.array_equal(np.isnan(a),np.isnan(b)),key
    finite=np.isfinite(a)&np.isfinite(b);error=np.abs(a[finite]-b[finite])
    ERRORS[key]=max(ERRORS.get(key,0.),float(error.max()) if len(error) else 0.)
    assert np.all(error<=atol+rtol*np.abs(b[finite])),(key,ERRORS[key])
def positive(x):return x is not None and np.isfinite(x) and x>0
def econ_rate(e,s):return max(float(e.get('vendor_margin_rate') or 0.),SCENARIOS[s]['margin_floor'])
def fee(price,e,s):return max(SCENARIOS[s]['fee_min'],abs(price)*float(e['contract_multiplier'])*SCENARIOS[s]['fee_bps'])
def floorlot(q,lot):return math.floor(max(0.,q)/lot)*int(lot)
def quote(reference,side,e,s):
    rule=SCENARIOS[s];p=Decimal(str(reference));tick=e.get('tick_size')
    tick=float(tick) if positive(tick) else None
    delta=abs(p)*Decimal(str(rule['slip_bps']))
    if tick:delta=max(delta,Decimal(str(tick))*rule['slip_ticks'])
    price=p+delta if side=='BUY' else p-delta
    if tick:
        unit=Decimal(str(tick));rounding=ROUND_CEILING if side=='BUY' else ROUND_FLOOR
        price=(price/unit).to_integral_value(rounding=rounding)*unit
    value=float(price);assert value>0
    return value,fee(value,e,s),abs(value-reference)*float(e['contract_multiplier'])
def estimate(reference,N,e,s):
    buy=quote(reference,'BUY',e,s);sell=quote(reference,'SELL',e,s);mult=float(e['contract_multiplier'])
    r=2*N*mult+2*fee(reference,e,s)+buy[2]+sell[2]
    return r,1.10*reference*mult*econ_rate(e,s),2*fee(reference,e,s),buy


def review_signals(experiment,protocol,calendar,economics):
    signals=csv(experiment/'signals_all.csv.gz')
    parent=pd.read_csv(io.BytesIO(bound(protocol['panel'])),compression='gzip',dtype=str,keep_default_na=False)
    assert len(signals)==399252 and signals.event_id.tolist()==parent.event_id.tolist()
    for c in ['product_id','exchange','product','u_date','reference_epoch','status','planned_execution_date','direction']:
        assert signals[c].tolist()==parent[c].tolist(),c
    numeric(signals,['u_index','D_index','policy_ready55','breakout','potential','N_u','low20_u','high55_before','history_run','u_close','lifecycle_index'])
    assert signals.product_id.nunique()==98 and signals.exchange.nunique()==6
    assert signals.family_id.eq(signals.product_id.str.removesuffix('_F')).all()
    lookup={d:i for i,d in enumerate(calendar)}
    assert np.array_equal(signals.u_index.to_numpy(),signals.u_date.map(lookup).to_numpy())
    assert np.array_equal(signals.D_index.to_numpy(),signals.u_index.to_numpy()+1)
    ready=signals.policy_ready55.eq(1)
    assert np.isfinite(signals.loc[ready,['N_u','u_close','low20_u','high55_before']]).all().all()
    assert (signals.loc[ready,'N_u']>0).all() and (signals.loc[ready,'history_run']>=56).all()
    breakout=ready&signals.u_close.gt(signals.high55_before)
    assert np.array_equal(signals.breakout.to_numpy(),breakout.astype(int).to_numpy())
    assert np.array_equal(signals.potential.to_numpy(),signals.breakout.to_numpy())
    for r in signals.loc[signals.reference_epoch.ne(''),['reference_epoch','lifecycle_index']].drop_duplicates().itertuples(index=False):
        e=economics[r.reference_epoch];nominal=r.reference_epoch.rsplit('.',1)[-1]
        choices=[nominal[:4]+'-'+nominal[4:]+'-01']
        for field in ['known_lifecycle_exit_boundary','nominal_month_first_date','maturity_date','de_listed_date']:
            value=e.get(field)
            if isinstance(value,str) and len(value)>=10 and value[:10]>='1900-01-01':choices.append(value[:10])
        assert int(r.lifecycle_index)==int(np.searchsorted(calendar,min(choices)))
    return signals.set_index('event_id',drop=False)


def review_budgets(budgets,daily,signals,economics,scenario,calendar,start):
    if budgets.empty:return {'rows':0,'new_allocations':0,'existing_reductions':0}
    assert not budgets.budget_id.duplicated().any()
    fields=['u_equity','existing_risk','existing_buffered_margin','unit_risk_u','unit_margin_u','unit_fee_reserve_u',
            'target_qty_unscaled','joint_scale','target_qty_prefloor','qty_cap','round_lot','allocated_risk',
            'allocated_buffered_margin','allocated_fee','D_qty','D_unit_risk','D_unit_margin_plus_fee','existing_qty','target_existing_qty']
    numeric(budgets,fields)
    for name in ['budget_kind','D_state','budget_state']:
        if name not in budgets:budgets[name]=''
    date_index={d:i for i,d in enumerate(calendar)};day=daily.set_index('date');new_count=0;reduce_count=0
    for u,group in budgets.groupby('u_date',sort=False):
        assert group.execution_date.eq(calendar[date_index[u]+1]).all()
        if u in day.index:
            eq=float(day.loc[u,'equity']);risk=float(day.loc[u,'initial_risk']);margin=float(day.loc[u,'buffered_margin'])
        else:
            assert date_index[u]==start-1;eq=1_000_000.;risk=0.;margin=0.
        compare(group.u_equity.to_numpy(),np.full(len(group),eq),'u_equity')
        compare(group.existing_risk.to_numpy(),np.full(len(group),risk),'u_existing_risk')
        compare(group.existing_buffered_margin.to_numpy(),np.full(len(group),margin),'u_existing_margin')
        new=group.loc[group.budget_kind.eq('new_entry')]
        expected=[]
        for row in new.to_dict('records'):
            signal=signals.loc[row['event_id']];assert signal.potential==1
            assert row['reference_epoch']==signal.reference_epoch and row['u_date']==signal.u_date
            e=economics[row['reference_epoch']];assert e['economics_status']=='exact_epoch_metadata_snapshot'
            r,m,f,buy=estimate(float(signal.u_close),float(signal.N_u),e,scenario)
            real=max(0.,.0025*eq/r) if eq>0 else 0.
            expected.append((row,r,m,f,real,e))
            compare([row['unit_risk_u'],row['unit_margin_u'],row['unit_fee_reserve_u'],row['target_qty_unscaled']],
                    [r,m,f,real],'u_unit_allocations')
        totalrisk=sum(r*real for _,r,m,f,real,e in expected);totalmargin=sum(m*real for _,r,m,f,real,e in expected)
        scale=min(1.,max(0.,.02*eq-risk)/totalrisk if totalrisk else 1.,max(0.,.25*eq-margin)/totalmargin if totalmargin else 1.) if eq>0 else 0.
        for row,r,m,f,real,e in expected:
            target=real*scale;lot=int(e['round_lot']);new_count+=1
            compare([row['joint_scale'],row['target_qty_prefloor'],row['allocated_risk'],row['allocated_buffered_margin'],row['allocated_fee']],
                    [scale,target,target*r,target*m,target*f],'prefloor_allocations')
            assert row['qty_cap']==floorlot(row['target_qty_prefloor'],lot)
            assert row['D_qty']<=row['qty_cap'] and row['D_qty']>=0
        reductions=group.loc[group.budget_kind.eq('existing_position_reduction')]
        if len(reductions):
            factor=min(1.,.02*eq/risk if risk else 1.,.25*eq/margin if margin else 1.) if eq>0 else 0.
            for row in reductions.to_dict('records'):
                e=economics[row['reference_epoch']];target=floorlot(row['existing_qty']*factor,int(e['round_lot']))
                compare(row['joint_scale'],factor,'reduction_scale')
                assert row['target_existing_qty']==target and row['qty_cap']==row['existing_qty']-target
                reduce_count+=1
    return {'rows':len(budgets),'new_allocations':new_count,'existing_reductions':reduce_count}


def review_account(directory,scenario,window,protocol,signals,economics,calendar):
    dates=[d for d in calendar if window['start']<=d<=window['end']]
    daily=csv(directory/'daily.csv.gz')
    numeric(daily,[c for c in daily if c not in ['account_id','window_id','scenario','date','ever_insolvent']])
    assert daily.date.tolist()==dates and not daily.date.duplicated().any()
    fills=csv(directory/'fills.csv.gz').rename(columns={'root_id':'root','fill_price':'fill','entry_fill':'entryfill','risk_per_lot':'risk_perlot'})
    numeric(fills,['qty','reference_price','fill','entryfill','multiplier','fee','slippage','realized_gross','margin_rate','risk_perlot'])
    positions=csv(directory/'position_days.csv.gz').rename(columns={'root_id':'root','entry_fill':'entryfill','risk_per_lot':'risk_perlot'})
    numeric(positions,['qty','entryfill','entry_reference','mark','multiplier','margin_rate','risk_perlot','SL0','boundary_next','unrealized','notional','stale_days'])
    if 'mark_state' not in positions:positions['mark_state']=pd.Series(dtype=str)
    budgets=csv(directory/'budgets.csv.gz');summary=json.loads((directory/'summary.json').read_text())
    fill_daily,roots,remaining=replay_fill_cash(fills);expected_cash=fill_days_to_daily(fill_daily,dates)
    quantity_checks=verify_saved_quantities(fills,positions,dates,roots)
    for observed,expected in [('cash','cash'),('cumulative_realized_gross','cum_realized_gross'),('cumulative_fees','cum_fees'),('cumulative_slippage','cum_slippage')]:
        compare(daily[observed],expected_cash[expected],'daily_'+observed)
    valuation=position_totals(positions,dates)
    for observed,expected in [('unrealized','unrealized'),('margin','margin'),('buffered_margin','buffered_reserve'),('initial_risk','initial_risk')]:
        compare(daily[observed],valuation[expected],'daily_'+observed)
    equity=expected_cash.cash.to_numpy()+valuation.unrealized.to_numpy()
    compare(daily.equity,equity,'daily_equity')
    compare(daily.stale_zero_equity,equity+valuation.stale_zero_adjustment.to_numpy(),'daily_stale_zero')
    if positions.empty:
        notionals=np.zeros(len(dates));stale=np.zeros(len(dates));counts=np.zeros(len(dates));stalecount=np.zeros(len(dates))
    else:
        notionals=(positions.qty*positions.multiplier*positions.mark).groupby(positions.date).sum().reindex(dates).fillna(0.).to_numpy()
        stale=(positions.qty*positions.multiplier*positions.mark*positions.mark_state.eq('stale')).groupby(positions.date).sum().reindex(dates).fillna(0.).to_numpy()
        counts=positions.groupby('date').size().reindex(dates).fillna(0.).to_numpy()
        stalecount=positions.loc[positions.mark_state.eq('stale')].groupby('date').size().reindex(dates).fillna(0.).to_numpy()
    compare(daily.open_notional,notionals,'daily_notional');compare(daily.stale_notional,stale,'daily_stale_notional')
    compare(daily.unresolved_zero_equity,equity-notionals,'daily_all_open_zero')
    compare(daily.open_positions,counts,'daily_open_count');compare(daily.stale_positions,stalecount,'daily_stale_count')
    assert np.array_equal(daily.ever_insolvent.eq('True').to_numpy(),np.maximum.accumulate(equity<=0))
    checked_budget=review_budgets(budgets,daily,signals,economics,scenario,calendar,calendar.index(dates[0]))
    lookup=budgets.set_index('budget_id') if len(budgets) else pd.DataFrame()
    if len(positions):
        assert not positions.duplicated(['date','family_id']).any()
        compare(positions.unrealized,positions.qty*positions.multiplier*(positions.mark-positions.entryfill),'position_unrealized')
        compare(positions.notional,positions.qty*positions.multiplier*positions.mark,'position_notional')
        for epoch,rows in positions.groupby('epoch',sort=False):
            e=economics[epoch];compare(rows.multiplier,np.full(len(rows),e['contract_multiplier']),'position_multiplier')
            compare(rows.margin_rate,np.full(len(rows),econ_rate(e,scenario)),'position_margin_rate')
    for row in fills.to_dict('records'):
        e=economics[row['epoch']];assert e['economics_status']=='exact_epoch_metadata_snapshot'
        assert row['multiplier']==e['contract_multiplier'] and row['qty']%int(e['round_lot'])==0
        price,unitfee,unitslip=quote(row['reference_price'],row['side'],e,scenario)
        compare([row['fill'],row['fee'],row['slippage']],[price,row['qty']*unitfee,row['qty']*unitslip],'all_fill_prices_fees_slippage')
        signal=signals.loc[row['event_id']];assert row['epoch']==signal.reference_epoch
        assert row['family_id']==signal.family_id and row['product_id']==signal.product_id
        assert row['date']>=signal.planned_execution_date
        if row['side']=='BUY':
            assert row['date']==signal.planned_execution_date and row['budget_id'] in lookup.index
            b=lookup.loc[row['budget_id']];assert b['budget_kind']=='new_entry' and b['u_date']==signal.u_date
            r,m,f,buy=estimate(row['reference_price'],signal.N_u,e,scenario)
            cashunit=buy[0]*e['contract_multiplier']*econ_rate(e,scenario)+buy[1]
            cap=min(float(b['qty_cap']),floorlot(float(b['allocated_risk'])/r,int(e['round_lot'])),
                    floorlot((float(b['allocated_buffered_margin'])+float(b['allocated_fee']))/cashunit,int(e['round_lot'])))
            assert row['qty']==cap and float(b['D_qty'])==cap
            compare(row['risk_perlot'],r,'entry_risk_perlot')
            assert b['D_state'] in ['entered','entered_reduced_own_allocation']
    # Pending reserves are the frozen prefloor allocations of positive-cap intents only.
    if len(budgets) and 'budget_kind' in budgets:
        new=budgets.loc[budgets.budget_kind.eq('new_entry')&budgets.qty_cap.gt(0)]
    else:new=pd.DataFrame(columns=['u_date','allocated_risk','allocated_buffered_margin','allocated_fee'])
    for field,allocation in [('new_order_risk_reserve','allocated_risk'),('new_order_margin_reserve','allocated_buffered_margin'),('new_order_fee_reserve','allocated_fee')]:
        sums=new.groupby('u_date')[allocation].sum().reindex(dates).fillna(0.) if len(new) else np.zeros(len(dates))
        compare(daily[field],sums,'daily_'+field)
    compare(daily.new_order_reserve,daily.new_order_margin_reserve+daily.new_order_fee_reserve,'daily_new_reserve')
    compare(daily.total_reserve,daily.buffered_margin+daily.new_order_reserve,'daily_total_reserve')
    closed=csv(directory/'closed_episodes.csv.gz');opens=csv(directory/'open_episodes.csv.gz')
    assert set(closed.root_id)=={k for k,v in roots.items() if v['closed']}
    assert set(opens.root_id)==set(remaining)
    for row in closed.to_dict('records'):
        r=roots[row['root_id']];compare(float(row['net_pnl']),r['net'],'closed_root_net')
        assert row['exit_date']==r['exit_date'] and row['entry_date']==r['entry_date']
    for row in opens.to_dict('records'):
        assert float(row['qty'])==remaining[row['root_id']]['qty']
        assert row['state'] in ['stale_open_unresolved','open_right_censored']
    insolvent=bool(np.any(equity<=0));computed=summary_metrics(equity,roots,insolvent=insolvent)
    mapping={'ending_equity':'ending_equity','closed_trades':'closed_trades','open_positions':'open_roots','closed_net_win_rate':'win_rate','sharpe':'sharpe'}
    for actual,expected in mapping.items():
        if computed[expected] is None:assert summary[actual] is None
        else:compare(summary[actual],computed[expected],'summary_'+actual)
    compare(summary['total_return_pct'],computed['total_return']*100,'summary_return')
    compare(summary['max_drawdown_pct'],computed['max_drawdown']*100,'summary_drawdown')
    compare(summary['total_fees'],expected_cash.cum_fees.iloc[-1],'summary_fee')
    compare(summary['total_slippage'],expected_cash.cum_slippage.iloc[-1],'summary_slippage')
    compare(summary['unrealized'],valuation.unrealized.iloc[-1],'summary_unrealized')
    compare(summary['cumulative_realized_gross'],expected_cash.cum_realized_gross.iloc[-1],'summary_realized')
    compare(summary['stale_zero_equity'],equity[-1]-stale[-1],'summary_stale_zero')
    compare(summary['all_open_long_zero_scenario_equity'],equity[-1]-notionals[-1],'summary_open_zero')
    assert summary['ever_insolvent']==insolvent and summary['source_dates']==len(dates)
    assert summary['source_start']==dates[0] and summary['source_end']==dates[-1]
    assert summary['initial_capital']==1_000_000. and summary['partial']==window.get('partial',False)
    return {'account_id':directory.name,'fills_checked':len(fills),'daily_rows_checked':len(daily),
            'position_rows_checked':quantity_checks,'budgets_checked':checked_budget,'closed_roots_checked':len(closed),
            'open_roots_checked':len(opens),'metrics':computed,'summary':summary}


def review_native_audit(manifest,signals,experiment,calendar):
    audit=json.loads(gzip.decompress(bound(manifest['excluded_raw_audit'])))
    assert audit['raw_ohlc'] is True and audit['sql_queries']==0
    checked=[]
    price=pd.read_csv(experiment/'price_reference/episodes.csv.gz',dtype=str,keep_default_na=False)
    for case in audit['cases']:
        signal=signals.loc[case['event_id']];history=[r for r in case['entry_history'] if r['date']<=case['u_date']]
        assert history and all(not r.get('native_missing') and r.get('valid_positive_volume') for r in history)
        N=np.nan;trs=[];last=None
        for r in history:
            tr=r['high']-r['low'] if last is None else max(r['high']-r['low'],abs(r['high']-last),abs(r['low']-last))
            trs.append(tr)
            if len(trs)==20:N=sum(trs)/20
            elif len(trs)>20:N=(19*N+tr)/20
            last=r['close']
        assert len(history)>=56
        compare([N,max(r['high'] for r in history[-56:-1]),min(r['low'] for r in history[-20:]),history[-1]['close']],
                [signal.N_u,signal.high55_before,signal.low20_u,signal.u_close],'native_signal_N_channel',atol=1e-9,rtol=1e-12)
        neighborhood=case.get('event_neighborhood',[])
        exits=price.loc[price.event_id.eq(case['event_id'])&price.state.eq('closed_known_ideal')]
        if len(exits) and neighborhood and case['kind'].startswith('price_'):
            p=exits.iloc[0];bar=next((r for r in neighborhood if r['date']==p.exit_date),None)
            assert bar is not None and not bar.get('native_missing')
            compare(float(p['entry_reference']),next(r['open'] for r in case['entry_history'] if r['date']==p.entry_date),'native_entry_open')
            if p.exit_reason in ['liquidity_reference_changed','lifecycle_exit','observation_exit_requested','gap_stop']:
                compare(float(p.exit_reference),bar['open'],'native_old_epoch_exit_open')
            compare(float(p.gross_points),float(p.exit_reference)-float(p.entry_reference),'native_price_points')
            compare(float(p.gross_R),float(p.gross_points)/float(p.R0),'native_price_R')
        checked.append({'kind':case['kind'],'event_id':case['event_id'],'entry_history_rows':len(history),
                        'event_neighborhood_rows':len(neighborhood)})
    known=price.state.eq('closed_known_ideal')
    assert price.loc[known,'label_known_date'].equals(price.loc[known,'exit_date'])
    assert price.loc[~known,'label_known_date'].eq('').all()
    for col in ['exit_date','exit_reference','gross_points','gross_R']:
        if col in price:assert price.loc[~known,col].eq('').all()
    return {'cases_checked':checked,'price_episode_rows':len(price),'price_known_closed':int(known.sum()),
            'price_unknown':int(price.state.eq('path_or_execution_unknown').sum()),'raw_audit_copied_into_review':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',required=True);parser.add_argument('--manifest-sha256',required=True)
    args=parser.parse_args();began=time.monotonic();started=datetime.now().astimezone().isoformat(timespec='seconds')
    path=Path(args.manifest);raw=path.read_bytes();assert sha(raw)==args.manifest_sha256
    m=json.loads(raw);assert m['status']=='completed' and m['completed_research_cash_accounts']==18
    assert m['source']['sha256']==SOURCE_SHA and m['protocol']['sha256']==PROTOCOL_SHA
    bound(m['source']);bound(m['tests'])
    for item in m['artifacts']:bound(item)
    experiment=path.parent;terminal=json.loads((experiment/'actual_terminal.json').read_text())
    assert terminal['status']=='completed' and terminal['exit_code']==0
    assert terminal['completed_research_cash_accounts']==18 and terminal['actual_model_fit_calls']==0
    assert terminal['native_source_queries']==1 and terminal['network_calls']==0
    p=json.loads(bound(m['protocol']));economics=json.loads(bound(p['economic_projection']))['instruments']
    cal=np.load(io.BytesIO(bound(p['calendar'])),allow_pickle=False)
    calendar=[f'{str(int(v))[:4]}-{str(int(v))[4:6]}-{str(int(v))[6:8]}' for v in cal]
    signals=review_signals(experiment,p,calendar,economics)
    summaries=json.loads((experiment/'cash_summary.json').read_text());actual={r['account_id']:r for r in summaries['accounts']}
    assert len(actual)==18;results=[]
    for scenario in p['scope']['cash_scenarios']:
        for window in p['scope']['cash_windows']:
            account=scenario+'__'+window['id'];result=review_account(experiment/'cash'/account,scenario,window,p,signals,economics,calendar)
            assert result['summary']==actual[account];results.append(result)
            print(json.dumps({'checked_account':account,'fills':result['fills_checked'],'daily':result['daily_rows_checked']}),flush=True)
    native=review_native_audit(m,signals,experiment,calendar)
    receipt={'schema':'stage043_cross_session_cash_independent_review_v1','independent_review':True,
             'status':'accepted_saved_research_cash_arithmetic_not_strategy_profitability','source_manifest':{'path':str(path),'sha256':args.manifest_sha256,'bytes':len(raw)},
             'source_code_read':m['source'],'accounts_checked':18,'fills_checked':sum(r['fills_checked'] for r in results),
             'daily_rows_checked':sum(r['daily_rows_checked'] for r in results),'position_rows_checked':sum(r['position_rows_checked'] for r in results),
             'account_results':results,'native_bounded_review':native,'max_abs_comparison_error':max(ERRORS.values()),
             'critical':0,'important':0,'minor':0,'author_strategy_calls':0,'sql_queries':0,'model_fit_calls':0,'strategy_replays':0,'downloads':0,
             'research_cash_arithmetic_qualified':True,'broker_historical_truth_qualified':False,'production_qualified':False,'goal_complete':False,
             'limitations':['Fixed historical close-mark accrual scenarios, not broker daily variation-settlement balances or exact historical fees/margin.','Limited native event evidence plus source/behavior review, not a second full OHLC strategy simulation.','No AI, narrow-stop or leverage advantage established by arithmetic acceptance.']}
    (OUT/'review_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    end={'schema':'stage043_actual_terminal_v1','exit_code':0,'started_at':started,'finished_at':datetime.now().astimezone().isoformat(timespec='seconds'),
         'elapsed_seconds':time.monotonic()-began,'source_sha256':sha(Path(__file__).read_bytes()),
         'core_sha256':sha((OUT/'cash_review_core.py').read_bytes()),'sql_queries':0,'strategy_replays':0,'model_fit_calls':0}
    (OUT/'actual_terminal.json').write_text(json.dumps(end,indent=2)+'\n')
    print(json.dumps({'status':receipt['status'],'accounts':18,'fills':receipt['fills_checked'],'daily':receipt['daily_rows_checked'],
                      'max_error':receipt['max_abs_comparison_error'],'elapsed_seconds':end['elapsed_seconds']}))


if __name__=='__main__':main()
