"""Independent saved-ledger arithmetic for the one frozen264 cash batch.

No old CLI, strategy kernel, source quote, label or model is imported or run.
Root must confirm the actual266 process exited before calling this reviewer.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import hashlib
import io
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd

LINE=Path(__file__).resolve().parents[1]
PROTOCOL_SHA='d18b82b34719425439a7190325fa692c912c93aa42db7d0d46493f2544013d42'
INITIAL=1_000_000.
WINDOWS=('primary_2020','cold_2023')
COSTS=('base','stress')
ROLES=('daily','fills','closed','open','positions','reservations','rejections','capacity_audit','entry_execution_unknown')


def safe(x):
    if isinstance(x,dict):return {str(k):safe(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [safe(v) for v in x]
    if isinstance(x,(np.integer,np.bool_)):return x.item()
    if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
    return x


def flag(x):
    assert str(x).lower() in ('true','false','1','0'),('invalid flag',x)
    return str(x).lower() in ('true','1')


def num(x):return float(x) if x is not None and str(x)!='' else math.nan


def close(a,b,label):
    x,y=np.asarray(a,float),np.asarray(b,float)
    assert x.shape==y.shape and np.array_equal(np.isnan(x),np.isnan(y)),(label,'shape/null')
    assert np.allclose(x,y,atol=1e-5,rtol=2e-10,equal_nan=True),(label,float(np.nanmax(np.abs(x-y))))


def numeric(f,columns):
    f=f.copy()
    for k in columns:
        if k in f:f[k]=pd.to_numeric(f[k].replace('',np.nan),errors='raise')
    return f


def metrics(daily):
    path=np.r_[INITIAL,daily.equity.to_numpy(float)]
    insolvent=any(flag(v) for v in daily.ever_insolvent)
    ret=path[1:]/path[:-1]-1 if (path>0).all() and not insolvent else None
    std=None if ret is None or len(ret)<2 else ret.std(ddof=1)
    return dict(initial_capital=INITIAL,ending_equity=path[-1],total_return_pct=(path[-1]/INITIAL-1)*100,
        max_drawdown_pct=np.min(path/np.maximum.accumulate(path)-1)*100,
        sharpe=float(ret.mean()/std*np.sqrt(252)) if std is not None and std>0 else None,
        ever_insolvent=insolvent)


def annual(daily):
    rows=[];previous=INITIAL
    for year,part in daily.groupby(daily.date.str[:4],sort=True):
        path=np.r_[previous,part.equity.to_numpy(float)]
        rows.append(dict(year=year,partial=year=='2026',source_days=len(part),starting_equity=previous,
            ending_equity=path[-1],cash_growth=path[-1]-previous,return_pct=(path[-1]/previous-1)*100 if previous>0 else None,
            max_drawdown_pct=np.min(path/np.maximum.accumulate(path)-1)*100,
            continuous_account_slice=True,independent_cold_start=False))
        previous=path[-1]
    return rows


def quote(reference,side,e,cost):
    fee_min,bps,ticks=(2.,.0001,1) if cost=='base' else (6.,.0003,3)
    p=Decimal(str(float(reference)));tick=e.get('tick_size')
    tick=float(tick) if tick is not None and float(tick)>0 else None
    delta=abs(p)*Decimal(str(bps))
    if tick:delta=max(delta,Decimal(str(tick))*ticks)
    value=p+delta if side=='BUY' else p-delta
    if tick:
        t=Decimal(str(tick));value=(value/t).to_integral_value(rounding=ROUND_CEILING if side=='BUY' else ROUND_FLOOR)*t
    value=float(value);mult=float(e['contract_multiplier'])
    assert value>0
    return value,max(fee_min,abs(value)*mult*bps),abs(value-float(reference))*mult


def units(reference,N,e,cost):
    fee_min,bps=(2.,.0001) if cost=='base' else (6.,.0003)
    mult=float(e['contract_multiplier']);fee=max(fee_min,abs(float(reference))*mult*bps)
    buy,sell=quote(reference,'BUY',e,cost),quote(reference,'SELL',e,cost)
    rate=max(float(e.get('vendor_margin_rate') or 0.),.2 if cost=='base' else .4)
    return .25*float(N)*mult+2*fee+buy[2]+sell[2],1.1*float(reference)*mult*rate,2*fee,rate


def floorlot(x,lot):return math.floor(max(0.,float(x))/int(lot))*int(lot)


class Review:
    def __init__(self):self.cache={};self.bindings={};self.reads=Counter();self.accounts={};self.issues=[]

    def raw(self,path,expected=None):
        path=str(Path(path).resolve())
        if path not in self.cache:
            b=Path(path).read_bytes();self.cache[path]=b;self.reads[path]+=1
            self.bindings[path]=dict(path=path,bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
        if expected:
            assert all(self.bindings[path][k]==expected[k] for k in ('path','bytes','sha256')),('binding',path)
        return self.cache[path]

    def js(self,path,expected=None):return json.loads(self.raw(path,expected))

    def table(self,path,expected=None):
        return pd.read_csv(io.BytesIO(self.raw(path,expected)),compression='gzip' if str(path).endswith('.gz') else None,
            dtype=str,keep_default_na=False,float_precision='round_trip')

    def compare_fields(self,observed,expected,label):
        for k,v in expected.items():
            assert k in observed,(label,'missing',k)
            if v is None:assert observed[k] is None or observed[k]=='',(label,k,'null')
            elif isinstance(v,(bool,np.bool_)):assert flag(observed[k])==v,(label,k)
            elif isinstance(v,(float,int,np.number)):close(num(observed[k]),v,label+'.'+k)
            else:assert observed[k]==v,(label,k,observed[k],v)

    def prepare(self,actual,manifest_sha,confirmed_exit_code):
        assert confirmed_exit_code==0,'root actual-process terminal confirmation required'
        self.actual=Path(actual).resolve()
        terminal=self.js(self.actual/'actual_terminal.json')
        assert terminal['status']=='completed' and terminal['cash_accounts_started']==terminal['cash_accounts_completed']==4
        assert terminal['max_new_candidate_cash']==4 and terminal['new_fit']==terminal['old_control_replays']==terminal['SQL']==0
        self.manifest=self.js(self.actual/'manifest.json')
        assert self.bindings[str(self.actual/'manifest.json')]['sha256']==manifest_sha
        m=self.manifest
        assert m['status']=='completed' and m['new_cash_accounts']==m['cash_accounts_started']==4
        assert m['max_new_candidate_cash']==4 and m['new_fit']==m['old_control_replays']==0 and not m['fixture']
        self.p=self.js(m['protocol']['path'],m['protocol']);assert m['protocol']['sha256']==PROTOCOL_SHA
        auth=self.js(m['authorization']['path'],m['authorization'])
        assert auth['authorized_by']=='root' and auth['protocol_sha256']==PROTOCOL_SHA and auth['output']==str(self.actual)
        assert auth['max_new_candidate_cash']==4 and auth['max_new_fit']==0 and auth['source_bundle']==m['source_bundle']
        for b in m['source_bundle']:self.raw(b['path'],b)
        source_review=self.js(m['source_review_receipt']['path'],m['source_review_receipt'])
        assert source_review['completed'] is True and source_review['core_blockers']==0 and source_review['protocol_sha256']==PROTOCOL_SHA
        assert all(b in source_review['source_bindings'] for b in m['source_bundle'])
        self.artifacts={b['path']:b for b in m['artifacts']}
        self.refs=self.js(self.p['cash_interface_refs']['path'],self.p['cash_interface_refs'])
        calendar_ref=self.refs['market_dependencies']['calendar']
        market_ref=self.refs['small_identity_bindings']['market_protocol']
        scope=self.js(market_ref['path'],market_ref)['scope']
        full_dates=[str(int(x)) for x in np.load(io.BytesIO(self.raw(calendar_ref['path'],calendar_ref)),allow_pickle=False)]
        full_dates=[x[:4]+'-'+x[4:6]+'-'+x[6:] for x in full_dates]
        # Signal u_index/D_index use the full source calendar, not the dataset
        # scope's 2010+ date subset. Cash windows are sliced below by date.
        self.calendar=full_dates
        assert len(self.calendar)==scope['full_source_calendar_dates']==5587
        cm=self.js(m['coverage_manifest']['path'],m['coverage_manifest'])
        assert cm['status']=='completed' and cm['protocol_sha256']==PROTOCOL_SHA
        coverage=self.js(cm['artifacts']['coverage_summary']['path'],cm['artifacts']['coverage_summary'])
        assert coverage['total_signals']==4365 and coverage['cancel_count']==1108 and coverage['core_blockers']==0
        original=self.table(self.p['complete_signals']['path'],self.p['complete_signals'])
        side=self.table(cm['artifacts']['signal_map']['path'],cm['artifacts']['signal_map'])
        filtered=self.table(self.actual/'signals_SPOT264.csv.gz',self.artifacts[str(self.actual/'signals_SPOT264.csv.gz')])
        assert len(original)==len(side)==4365 and side.signal_row.astype(int).tolist()==list(range(4365))
        assert original.event_id.is_unique and side.event_id.is_unique
        for field in ('event_id','mother_event_id','product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch'):
            assert original[field].tolist()==side[field].tolist(),('signal sidecar identity',field)
        keep=side.keep_entry.astype(int);available=side.available.astype(int)
        assert keep.isin([0,1]).all() and available.isin([0,1]).all()
        assert keep.sum()==3257 and (1-keep).sum()==1108 and available.sum()==2782 and (1-available).sum()==1583
        assert keep.loc[available.eq(0)].eq(1).all() and side.action.tolist()==['retain' if k else 'cancel' for k in keep]
        expected=original.loc[keep.eq(1)].reset_index(drop=True)
        assert list(expected)==list(filtered) and expected.shape==filtered.shape
        for col in expected:
            if expected[col].tolist()==filtered[col].tolist():continue
            a,b=pd.to_numeric(expected[col].replace('',np.nan),errors='raise'),pd.to_numeric(filtered[col].replace('',np.nan),errors='raise')
            close(a,b,'unchanged retained signal '+col)
        self.signals=filtered.set_index('event_id',drop=False)
        for row in filtered.to_dict('records'):
            assert self.calendar[int(row['u_index'])]==row['u_date'] and int(row['D_index'])==int(row['u_index'])+1
        self.source_receipt=self.js(self.actual/'source_read_receipt.json',self.artifacts[str(self.actual/'source_read_receipt.json')])
        sr=self.source_receipt
        assert sr['original_signals']==4365 and sr['retained_signals']==3257 and sr['cancelled_signals']==1108 and sr['full_mother_rows']==399252
        assert sr['original_signal_binding']==self.p['complete_signals'] and sr['original_mother_binding']==self.p['complete_mothers']
        assert sr['new_fit']==sr['new_labels']==sr['old_control_replays']==sr['selectors_called']==sr['actions_scores_models_read']==0
        assert sr['native_source_queries']==0 and sr['large_mother_hash_recomputed'] is False
        self.economics=self.js(self.refs['market_dependencies']['economic_projection']['path'],self.refs['market_dependencies']['economic_projection'])['instruments']
        self.identity=dict(original_signals=4365,retained=3257,cancelled=1108,available=2782,unavailable_inherited=1583,
            retained_all_columns_unchanged=True,fullcanonical_domain_inherited_rows=399252,full_mother_reread=False)

    def account(self,spec):
        aid=spec['account_id'];directory=Path(spec['directory']);cost=spec['cost'];window=spec['window']
        t={role:self.table(directory/(role+'.csv.gz'),spec['ledgers'][role]) for role in ROLES}
        summary=self.js(spec['summary']['path'],spec['summary'])
        diagnostics=self.js(directory/'diagnostics.json',self.artifacts[str(directory/'diagnostics.json')])
        daily=numeric(t['daily'],[k for k in t['daily'] if k not in ('account_id','scenario','date','ever_insolvent','window_id','arm')])
        assert len(daily)>0 and daily.date.is_unique and daily.date.is_monotonic_increasing
        assert daily.date.iloc[-1]==self.p['windows'][window][1] and daily.date.iloc[0]>=self.p['windows'][window][0]
        assert daily.date.tolist()==[d for d in self.calendar if self.p['windows'][window][0]<=d<=self.p['windows'][window][1]]
        fills=numeric(t['fills'],['qty','reference_price','fill_price','entry_fill','multiplier','fee','slippage','realized_gross','margin_rate','risk_per_lot'])
        positions=numeric(t['positions'],['qty','entry_fill','entry_reference','mark','multiplier','margin_rate','risk_per_lot','SL0','boundary_next','unrealized','notional','stale_days'])
        roots={};quantity={};flow=[];tick_lots=0.;unknown_ticks=0
        assert fills.date.is_monotonic_increasing
        for r in fills.to_dict('records'):
            rid=r['root_id'];sig=self.signals.loc[r['event_id']];e=self.economics[r['epoch']]
            assert r['account_id']==aid and r['scenario']==cost and r['epoch']==sig.reference_epoch
            assert r['family_id']==sig.family_id and r['product_id']==sig.product_id and r['qty']>0
            assert r['qty']%int(e['round_lot'])==0 and r['multiplier']==float(e['contract_multiplier'])
            q,fee,slip=quote(r['reference_price'],r['side'],e,cost)
            close([r['fill_price'],r['fee'],r['slippage']],[q,fee*r['qty'],slip*r['qty']],aid+' fill economic arithmetic')
            if r['side']=='BUY':
                assert rid not in roots and r['date']==self.calendar[int(sig.D_index)]
                roots[rid]=dict(event_id=r['event_id'],entry_fill=r['fill_price'],entry_reference=r['reference_price'],entry_date=r['date'],multiplier=r['multiplier'],gross=0.,fee=0.,closed=False)
                quantity[rid]=r['qty'];gross=0.
                close(r['risk_per_lot'],units(r['reference_price'],sig.N_u,e,cost)[0],aid+' entry risk')
            else:
                assert r['side']=='SELL' and rid in quantity and r['qty']<=quantity[rid]
                gross=r['qty']*r['multiplier']*(r['fill_price']-roots[rid]['entry_fill']);quantity[rid]-=r['qty']
                if quantity[rid]==0:roots[rid].update(closed=True,exit_date=r['date']);del quantity[rid]
            roots[rid]['gross']+=gross;roots[rid]['fee']+=r['fee'];close(r['realized_gross'],gross,aid+' fill gross')
            flow.append(dict(date=r['date'],gross=gross,fee=r['fee'],slippage=r['slippage']))
            tick=e.get('tick_size')
            if tick is not None and float(tick)>0:tick_lots+=abs(r['fill_price']-r['reference_price'])/float(tick)*r['qty']
            else:unknown_ticks+=1
        dates=pd.Index(daily.date)
        acc=pd.DataFrame(flow,columns=['date','gross','fee','slippage']).groupby('date')[['gross','fee','slippage']].sum().reindex(dates,fill_value=0.).cumsum()
        for col,want in [('cumulative_realized_gross',acc.gross),('cumulative_fees',acc.fee),('cumulative_slippage',acc.slippage),('cash',INITIAL+acc.gross-acc.fee)]:close(daily[col],want,aid+' '+col)
        for r in positions.to_dict('records'):
            rt=roots[r['root_id']];sig=self.signals.loc[r['event_id']]
            assert r['event_id']==rt['event_id'] and r['epoch']==sig.reference_epoch
            close([r['entry_fill'],r['multiplier'],r['SL0']],[rt['entry_fill'],rt['multiplier'],rt['entry_reference']-.25*float(sig.N_u)],aid+' position anchor/stop')
        assert not positions.duplicated(['date','root_id']).any() and not positions.duplicated(['date','family_id']).any()
        qbook={};fg={d:x for d,x in fills.groupby('date',sort=False)};pg={d:x for d,x in positions.groupby('date',sort=False)}
        for day in dates:
            for r in fg.get(day,fills.iloc[:0]).to_dict('records'):
                rid=r['root_id'];qbook[rid]=qbook.get(rid,0.)+(r['qty'] if r['side']=='BUY' else -r['qty'])
                assert qbook[rid]>=0
                if not qbook[rid]:del qbook[rid]
            assert qbook==dict(zip(pg.get(day,positions.iloc[:0]).root_id,pg.get(day,positions.iloc[:0]).qty)),(aid,'remaining quantity',day)
        if len(positions):
            close(positions.unrealized,positions.qty*positions.multiplier*(positions.mark-positions.entry_fill),aid+' position unrealized')
            close(positions.notional,positions.qty*positions.multiplier*positions.mark,aid+' position notional')
        vals=pd.DataFrame(index=positions.index)
        vals['unrealized']=positions.qty*positions.multiplier*(positions.mark-positions.entry_fill)
        vals['margin']=positions.notional*positions.margin_rate;vals['buffered_margin']=1.1*vals.margin
        vals['initial_risk']=positions.qty*positions.risk_per_lot;vals['open_notional']=positions.notional
        vals['stale_notional']=positions.notional*positions.mark_state.eq('stale');vals['open_positions']=1
        vals['stale_positions']=positions.mark_state.eq('stale').astype(int);vals['date']=positions.date
        totals=vals.groupby('date').sum().reindex(dates,fill_value=0.)
        for col in totals:close(daily[col],totals[col],aid+' daily position '+col)
        close(daily.equity,daily.cash.to_numpy()+totals.unrealized.to_numpy(),aid+' equity')
        close(daily.stale_zero_equity,daily.equity.to_numpy()-totals.stale_notional.to_numpy(),aid+' stale zero')
        close(daily.unresolved_zero_equity,daily.equity.to_numpy()-totals.open_notional.to_numpy(),aid+' all open zero')
        assert np.array_equal(np.array([flag(x) for x in daily.ever_insolvent]),np.maximum.accumulate(daily.equity.to_numpy()<=0))
        closed=numeric(t['closed'],['net_pnl']);opened=numeric(t['open'],['qty'])
        assert closed.root_id.is_unique and opened.root_id.is_unique
        assert set(closed.root_id)=={k for k,v in roots.items() if v['closed']} and set(opened.root_id)==set(quantity)
        for row in pd.concat([closed,opened],ignore_index=True).to_dict('records'):
            sig=self.signals.loc[row['event_id']]
            assert row['anchor_epoch']==sig.anchor_epoch and row['mother_event_id']==sig.mother_event_id and row['epoch']==sig.reference_epoch
            assert int(float(row['expiry']))==int(float(sig.lifecycle_index))
        for r in closed.to_dict('records'):
            rt=roots[r['root_id']];close(r['net_pnl'],rt['gross']-rt['fee'],aid+' closed net')
            assert r['entry_date']==rt['entry_date'] and r['exit_date']==rt['exit_date']
        for r in opened.to_dict('records'):close(r['qty'],quantity[r['root_id']],aid+' open quantity')
        result=metrics(daily)
        result.update(fills=len(fills),closed_trades=len(closed),closed_net_win_rate=float((closed.net_pnl>0).mean()) if len(closed) else None,
            total_fees=acc.fee.iloc[-1],total_slippage=acc.slippage.iloc[-1],total_filled_qty=fills.qty.sum(),
            cumulative_realized_gross=acc.gross.iloc[-1],unrealized=totals.unrealized.iloc[-1],open_positions=len(opened),
            max_open_notional=totals.open_notional.max(),max_buffered_margin=totals.buffered_margin.max(),
            max_frozen_initial_risk=totals.initial_risk.max(),turnover_notional=(fills.qty*fills.multiplier*fills.fill_price).sum(),
            slippage_tick_lots_known=tick_lots,unknown_tick_fills=unknown_ticks)
        self.compare_fields(summary,result,aid+' summary')
        self.budgets(t,daily,positions,fills,aid,cost)
        slices=annual(daily);assert len(slices)==len(diagnostics['annual_slices'])
        for a,b in zip(diagnostics['annual_slices'],slices):self.compare_fields(a,b,aid+' annual')
        cap=t['capacity_audit'];assert len(cap)==len(fills)
        unknown_roots=set();consumed=Counter()
        for i,(a,f) in enumerate(zip(cap.to_dict('records'),fills.to_dict('records'))):
            key=(f['epoch'],f['date']);before=consumed[key];consumed[key]+=int(f['qty'])
            self.compare_fields(a,dict(fill_sequence=i,root_id=f['root_id'],epoch=f['epoch'],fill_date=f['date'],side=f['side'],reason=f['reason'],
                prior_same_epoch_day_gross_qty=before,fill_qty=f['qty'],cumulative_same_epoch_day_gross_qty=consumed[key]),aid+' capacity ledger')
            volume=num(a['capacity_reference_volume']);lot=int(self.economics[f['epoch']]['round_lot'])
            grosscap=None if not math.isfinite(volume) or volume<=0 else floorlot(volume*.01,lot)
            if grosscap is not None:close(num(a['capacity_cap_qty']),grosscap,aid+' reported volume cap')
            unknown=grosscap is None or consumed[key]>grosscap
            assert (a['capacity_state']=='execution_capacity_unknown')==unknown
            if unknown:unknown_roots.add(f['root_id'])
        execution_unknown=bool(unknown_roots or len(t['entry_execution_unknown']))
        self.compare_fields(summary,dict(capacity_unknown_fills=sum(cap.capacity_state.eq('execution_capacity_unknown')),
            capacity_unknown_roots=len(unknown_roots),entry_execution_unknown=len(t['entry_execution_unknown']),
            execution_unknown=execution_unknown,any_historical_stale=bool((daily.stale_positions>0).any())),aid+' unknown disclosure')
        result.update(account_id=aid,window=window,cost=cost,annual=slices,execution_unknown=execution_unknown,
            any_historical_stale=bool((daily.stale_positions>0).any()))
        self.accounts[(window,cost)]=result
        return daily,result

    def budgets(self,t,daily,positions,fills,aid,cost):
        b=numeric(t['reservations'],['D_qty','qty_cap','original_qty_cap','allocated_risk','allocated_buffered_margin','allocated_fee',
            'target_qty_unscaled','target_qty_prefloor','joint_scale','unit_risk_u','unit_margin_u','unit_fee_reserve_u',
            'u_equity','existing_risk','existing_buffered_margin','existing_qty','target_existing_qty'])
        assert b.budget_id.is_unique
        ordinary=b.loc[~b.budget_kind.eq('existing_position_reduction')]
        D_dates=self.signals.D_index.map(lambda k:self.calendar[int(k)])
        expected=self.signals.loc[D_dates.ge(daily.date.iloc[0])&self.signals.u_date.lt(daily.date.iloc[-1])]
        assert ordinary.event_id.is_unique and set(ordinary.event_id)==set(expected.event_id),(aid,'all retained intents')
        rejected=t['rejections'].set_index('budget_id');zero=b.loc[b.D_qty.eq(0)].set_index('budget_id')
        assert set(rejected.index)==set(zero.index)
        for k in ('event_id','u_date','reference_epoch','anchor_epoch','execution_date','budget_kind','budget_state','D_state'):
            assert rejected.loc[zero.index,k].tolist()==zero[k].tolist(),(aid,'rejection state',k)
        day=daily.set_index('date')
        for u,g in b.groupby('u_date',sort=False):
            eq=float(day.loc[u,'equity']) if u in day.index else INITIAL
            risk=float(day.loc[u,'initial_risk']) if u in day.index else 0.
            margin=float(day.loc[u,'buffered_margin']) if u in day.index else 0.
            close(g.u_equity,np.full(len(g),eq),aid+' budget equity')
            close(g.existing_risk,np.full(len(g),risk),aid+' budget occupied risk')
            close(g.existing_buffered_margin,np.full(len(g),margin),aid+' budget occupied margin')
            new=g.loc[g.budget_kind.eq('new_entry')];proposals=[]
            for r in new.to_dict('records'):
                sig=self.signals.loc[r['event_id']];e=self.economics[r['reference_epoch']]
                R,M,F,_=units(sig.u_close,sig.N_u,e,cost);target=max(0.,.0025*eq/R) if eq>0 else 0.
                close([r['unit_risk_u'],r['unit_margin_u'],r['unit_fee_reserve_u'],r['target_qty_unscaled']],[R,M,F,target],aid+' u unit reservations')
                proposals.append((r,sig,e,R,M,F,target))
            tr=sum(R*q for r,s,e,R,M,F,q in proposals);tm=sum(M*q for r,s,e,R,M,F,q in proposals)
            scale=min(1.,max(0.,.02*eq-risk)/tr if tr else 1.,max(0.,.25*eq-margin)/tm if tm else 1.) if eq>0 else 0.
            for r,s,e,R,M,F,q in proposals:
                target=q*scale;lot=int(e['round_lot']);cap=min(floorlot(target,lot),int(float(s.entry_capacity_qty)))
                close([r['joint_scale'],r['target_qty_prefloor'],r['allocated_risk'],r['allocated_buffered_margin'],r['allocated_fee']],[scale,target,target*R,target*M,target*F],aid+' joint prefloor reservations')
                assert r['original_qty_cap']==floorlot(target,lot) and r['qty_cap']==cap and 0<=r['D_qty']<=cap
                buys=fills.loc[fills.side.eq('BUY')&fills.budget_id.eq(r['budget_id'])]
                assert len(buys)==int(r['D_qty']>0)
                if len(buys):
                    f=buys.iloc[0];RR,MM,FF,rate=units(f.reference_price,s.N_u,e,cost)
                    unit=float(f.fill_price)*float(e['contract_multiplier'])*rate+float(f.fee)/float(f.qty)
                    want=min(cap,floorlot(r['allocated_risk']/RR,lot),floorlot((r['allocated_buffered_margin']+r['allocated_fee'])/unit,lot))
                    close([f.qty,r['D_qty']],[want,want],aid+' D filled reservation')
            factor=min(1.,.02*eq/risk if risk else 1.,.25*eq/margin if margin else 1.) if eq>0 else 0.
            for r in g.loc[g.budget_kind.eq('existing_position_reduction')].to_dict('records'):
                lot=int(self.economics[r['reference_epoch']]['round_lot']);target=floorlot(r['existing_qty']*factor,lot)
                close([r['joint_scale'],r['target_existing_qty'],r['qty_cap']],[factor,target,r['existing_qty']-target],aid+' reduction reservations')
        pending=b.loc[b.budget_kind.eq('new_entry')&b.qty_cap.gt(0)]
        for col,allocation in [('new_order_risk_reserve','allocated_risk'),('new_order_margin_reserve','allocated_buffered_margin'),('new_order_fee_reserve','allocated_fee')]:
            close(daily[col],pending.groupby('u_date')[allocation].sum().reindex(daily.date,fill_value=0.),aid+' daily '+col)
        close(daily.new_order_reserve,daily.new_order_margin_reserve+daily.new_order_fee_reserve,aid+' pending margin+fee')
        close(daily.total_reserve,daily.buffered_margin+daily.new_order_reserve,aid+' total reserve')
        missing=b.loc[b.D_state.eq('entry_execution_unknown')]
        assert set(missing.budget_id)==set(t['entry_execution_unknown'].budget_id)

    def finish(self):
        comparisons=[];all_annual=[]
        for spec,control in zip(self.manifest['accounts'],self.p['control_accounts']):
            assert (spec['window'],spec['cost'])==(control['window'],control['cost'])
            cd,active=self.account(spec)
            old=self.js(control['summary']['path'],control['summary'])
            ref=control['ledgers_relative_to_directory']['daily'];path=Path(control['directory'])/ref['file']
            bd=numeric(self.table(path,dict(path=str(path),bytes=ref['bytes'],sha256=ref['sha256'])),['equity','cumulative_fees','cumulative_slippage'])
            assert bd.date.tolist()==cd.date.tolist()
            baseline=metrics(bd);self.compare_fields(old,baseline,control['account_id']+' saved curve')
            close([old['total_fees'],old['total_slippage']],[bd.cumulative_fees.iloc[-1],bd.cumulative_slippage.iloc[-1]],'baseline cost totals')
            point=dict(account_id=spec['account_id'],window=spec['window'],cost=spec['cost'],control_account_id=control['account_id'],
                ending_equity_difference=active['ending_equity']-baseline['ending_equity'],
                return_percentage_point_difference=active['total_return_pct']-baseline['total_return_pct'],
                drawdown_percentage_point_difference=active['max_drawdown_pct']-baseline['max_drawdown_pct'])
            comparisons.append(point)
            all_annual.extend(dict(account_id=spec['account_id'],role='candidate',window=spec['window'],cost=spec['cost'],**r) for r in active['annual'])
            all_annual.extend(dict(account_id=control['account_id'],role='control_reused',window=spec['window'],cost=spec['cost'],**r) for r in annual(bd))
        points=self.table(self.actual/'comparisons.csv.gz',self.artifacts[str(self.actual/'comparisons.csv.gz')])
        for expected in comparisons:
            actual=points.loc[points.account_id.eq(expected['account_id'])];assert len(actual)==1
            self.compare_fields(actual.iloc[0].to_dict(),expected,'fixed comparisons')
        saved=self.table(self.actual/'annual_slices.csv.gz',self.artifacts[str(self.actual/'annual_slices.csv.gz')])
        assert len(saved)==len(all_annual)
        for expected in all_annual:
            row=saved.loc[saved.account_id.eq(expected['account_id'])&saved.year.eq(expected['year'])];assert len(row)==1
            self.compare_fields(row.iloc[0].to_dict(),expected,'all annual output')
        decision=self.js(self.actual/'decision.json',self.artifacts[str(self.actual/'decision.json')])
        stress=[p for p in comparisons if p['cost']=='stress'];effect=all(p['ending_equity_difference']>0 for p in stress)
        both=effect and all(p['drawdown_percentage_point_difference']>0 for p in stress)
        self.compare_fields(decision,dict(primary_falsification_pass=effect,both_stress_return_and_drawdown_improved=both,
            execution_unknown=any(a['execution_unknown'] for a in self.accounts.values()),
            any_historical_stale=any(a['any_historical_stale'] for a in self.accounts.values()),new_CI=0,new_fit=0,
            old_control_replays=0,goal_complete=False,production_qualified=False,increased_betting_qualified=False),'decision')
        return dict(accounts=list(self.accounts.values()),comparisons=comparisons,primary_falsification_pass=effect,
            both_stress_return_and_drawdown_improved=both)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--actual',required=True);p.add_argument('--manifest-sha256',required=True)
    p.add_argument('--root-confirmed-process-exit-code',type=int,required=True);p.add_argument('--output',required=True)
    a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=False);r=Review()
    receipt=dict(schema='stage268_fixed_spot_cash_independent_review_v1',status='failed',core_blockers=1)
    try:
        r.prepare(a.actual,a.manifest_sha256,a.root_confirmed_process_exit_code);result=r.finish()
        receipt.update(status='completed',core_blockers=0,identity=r.identity,results=result)
    except BaseException as exc:
        receipt['failure']=dict(type=type(exc).__name__,message=str(exc));raise
    finally:
        receipt.update(completed_at=datetime.now(timezone.utc).isoformat(),input_bindings=list(r.bindings.values()),
            file_read_counts=dict(r.reads),new_fit=0,new_cash=0,SQL=0,network=0,native_price_reads=0,raw_body_reads=0,
            labels_read=0,old_controls_replayed=0,goal_complete=False,production_qualified=False,
            limitations=['saved-ledger arithmetic; source marks/capacity volumes not independently certified against native prices',
                'fullcanonical original identity inherited from accepted263/267 chain; no old mothers/actions/scores read',
                'historical economics snapshot and vendor quote-vintage unknown retained; not PIT or execution truth',
                'windows overlap; adaptive historical research; no independent replication or future-alpha claim'])
        with (out/'receipt.json').open('x') as f:json.dump(safe(receipt),f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')


if __name__=='__main__':main()
