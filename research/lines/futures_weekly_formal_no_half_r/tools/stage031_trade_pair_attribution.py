"""Read-only fill-derived B/W native-round accounting and static attribution.
No engine/strategy import, financial replay, fitting, downloads or source mutation.
"""
from __future__ import annotations
import ast
from collections import defaultdict, deque, Counter
from datetime import datetime
from decimal import Decimal, getcontext
import hashlib, json, math, re
from numbers import Number
from pathlib import Path
from zoneinfo import ZoneInfo
import sys
import pandas as pd
import numpy as np

getcontext().prec = 40
D = lambda x: Decimal(str(x))
LINE = Path(__file__).resolve().parents[1]
OUT = LINE/'outputs/stage031_trade_pair_attribution'
ROOT = LINE.parents[2]
ARM = {'B':LINE/'outputs/R_attempt003', 'W':LINE/'outputs/stage030_weekly_attempt001'}
SOURCES = {}


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def source(p):
    p=Path(p).resolve();SOURCES[str(p)]=sha(p);return p


def read(p,**kw):
    return pd.read_csv(source(p),**kw)


def load(p):return json.loads(source(p).read_text())
def js(v):return json.dumps(v,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def clean(v):
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    if isinstance(v,np.generic):v=v.item()
    if isinstance(v,float) and not math.isfinite(v):return None
    if isinstance(v,Decimal):return float(v)
    return v


def close(a,b,label,tol=1e-6):
    assert abs(float(a)-float(b))<=tol,(label,a,b)


def epoch_lookup(weekly):
    grouped={s:g.sort_values('week_end') for s,g in weekly.groupby('vt_symbol')}
    def lookup(s,day):
        g=grouped[s];q=g[g.week_end.le(day)]
        assert len(q),(s,day,'no prior observed week')
        return str(q.iloc[-1].contract_epoch_id)
    return lookup


def drawdown(daily):
    x=daily.account_equity.to_numpy(float);peak=np.maximum.accumulate(np.r_[150000.,x])[1:];dd=x/peak-1
    ti=int(np.argmin(dd));pk=peak[ti];pis=np.flatnonzero(x[:ti+1]==pk)
    pi=int(pis[-1]) if len(pis) else None
    return dict(peak_date=str(daily.iloc[pi].date) if pi is not None else 'INITIAL_CAPITAL',trough_date=str(daily.iloc[ti].date),peak_equity=float(pk),trough_equity=float(x[ti]),drawdown_pct=float(dd[ti]*100))


def rebuild(arm,path):
    trades=read(path/'trades.csv');clock=read(path/'execution_clock.csv')
    assert trades.trade_id.is_unique and clock.trade_id.is_unique
    assert set(trades.trade_id)==set(clock.trade_id)
    check=clock.set_index('trade_id')
    for r in trades.itertuples():
        c=check.loc[r.trade_id]
        for k in ['vt_symbol','trading_date','direction','offset']:assert str(getattr(r,k))==str(c[k]),(arm,r.trade_id,k)
        for k in ['price','volume']:close(getattr(r,k),c[k],arm+':clock:'+k)
    clock['_clock_order']=np.arange(len(clock))
    fills=trades.merge(clock[['trade_id','execution_datetime','_clock_order']],on='trade_id',validate='one_to_one')
    fills['_utc']=pd.to_datetime(fills.execution_datetime,utc=True)
    fills=fills.sort_values(['_utc','_clock_order'],kind='stable').reset_index(drop=True)
    assert fills.trading_date.tolist()==sorted(fills.trading_date.tolist())
    effective=load(path/'effective_parameters.json');weekly=read(path/'weekly_bars.csv')
    epoch=epoch_lookup(weekly);daily=read(path/'daily.csv');last=str(daily.iloc[-1].date)
    marks={};terminal_positions={}
    # Large CSV is scanned with narrow columns/chunks; no full read.
    for ch in pd.read_csv(source(path/'positions.csv'),usecols=['date','vt_symbol','end_pos','close_price'],chunksize=100000):
        q=ch[ch.date.eq(last)&ch.end_pos.ne(0)]
        for r in q.itertuples():marks[r.vt_symbol]=D(r.close_price);terminal_positions[r.vt_symbol]=D(r.end_pos)
    active={};rounds=[];segments=[];fillrows=[];fill_to_round={};nextn=0
    for line,r in enumerate(fills.to_dict('records'),start=2):
        sym=str(r['vt_symbol']);p=D(r['price']);q=D(r['volume']);sgn=1 if r['direction']=='多' else -1
        assert q>0 and p>0 and r['direction'] in ['多','空']
        size=D(effective['sizes'][sym]);slip=D(effective['slippages'][sym])*size;fee=p*size*D(effective['rates'][sym]);cost=(slip+fee)*q
        isopen=r['offset']=='开'
        if isopen and sym not in active:
            nextn+=1;active[sym]=dict(round_id=f'{arm}{nextn:03d}',arm=arm,vt_symbol=sym,physical_epoch=epoch(sym,r['trading_date']),direction='long' if sgn>0 else 'short',sign=sgn,entry_trading_date=r['trading_date'],entry_execution_datetime=r['execution_datetime'],entry_trade_id=r['trade_id'],opened_volume=D(0),pos=D(0),cash=D(0),realized_net_pnl=D(0),realized_gross_pnl=D(0),entry_cost=D(0),exit_cost=D(0),entry_weight=D(0),entryfills=[],exitfills=[],queue=deque(),fill_count=0,contract_size=size)
        assert sym in active,(arm,'unmatched',r['trade_id'])
        a=active[sym];rid=a['round_id'];fill_to_round[r['trade_id']]=rid
        assert a['physical_epoch']==epoch(sym,r['trading_date']),(arm,sym,'cross epoch in round')
        a['fill_count']+=1;a['cash']-=D(sgn)*p*size*q+cost
        er=dict(trade_id=r['trade_id'],order_id=r['order_id'],trading_date=r['trading_date'],execution_datetime=r['execution_datetime'],price=float(p),volume=float(q),reason=None if pd.isna(r['exit_reason']) else r['exit_reason'],source_row=int(r['_clock_order'])+2)
        fillrows.append(dict(arm=arm,round_id=rid,source_trades_row=int(r['_clock_order'])+2,**{k:clean(v) for k,v in r.items() if k not in ['_utc','_clock_order']}))
        if isopen:
            assert sgn==a['sign'];a['opened_volume']+=q;a['pos']+=q;a['entry_weight']+=p*q;a['entry_cost']+=cost;a['entryfills'].append(er)
            a['queue'].append(dict(price=p,quantity=q,slip_unit=slip,fee_unit=fee,trade_id=r['trade_id'],date=r['trading_date']))
        else:
            assert sgn==-a['sign'];a['pos']-=q;assert a['pos']>=0
            a['exit_cost']+=cost;a['exitfills'].append(er);remaining=q
            while remaining:
                e=a['queue'][0];matched=min(remaining,e['quantity']);gross=D(a['sign'])*(p-e['price'])*size*matched
                net=gross-(e['slip_unit']+e['fee_unit']+slip+fee)*matched
                a['realized_net_pnl']+=net;a['realized_gross_pnl']+=gross
                segments.append(dict(arm=arm,round_id=rid,vt_symbol=sym,entry_trade_id=e['trade_id'],exit_trade_id=r['trade_id'],entry_date=e['date'],exit_date=r['trading_date'],volume=float(matched),entry_price=float(e['price']),exit_price=float(p),gross_pnl=float(gross),net_pnl=float(net)))
                e['quantity']-=matched;remaining-=matched
                if not e['quantity']:a['queue'].popleft()
            if not a['pos']:
                close(a['cash'],a['realized_net_pnl'],'round cash')
                a.update(status='closed',exit_trading_date=r['trading_date'],exit_execution_datetime=r['execution_datetime'],terminal_mark=None,remaining_qty=D(0),remaining_net_mtm=D(0),net_pnl=a['cash'])
                rounds.append(a);del active[sym]
    for sym,a in active.items():
        assert sym in marks
        m=marks[sym];pos=D(a['sign'])*a['pos'];close(pos,terminal_positions[sym],'terminal position')
        remaining=sum((D(a['sign'])*(m-e['price'])*a['contract_size']-e['slip_unit']-e['fee_unit'])*e['quantity'] for e in a['queue'])
        net=a['cash']+pos*m*a['contract_size'];close(a['realized_net_pnl']+remaining,net,'open round cash')
        a.update(status='terminal_open',exit_trading_date=last,exit_execution_datetime=None,terminal_mark=float(m),remaining_qty=a['pos'],remaining_net_mtm=remaining,net_pnl=net);rounds.append(a)
    rows=[]
    for a in rounds:
        assert a['opened_volume']>0
        a['weighted_entry_price']=a['entry_weight']/a['opened_volume']
        a['price_pnl_per_initial_lot']=(a['realized_gross_pnl']+sum(D(a['sign'])*(D(a['terminal_mark'])-e['price'])*a['contract_size']*e['quantity'] for e in a['queue']))/a['opened_volume']
        a['net_pnl_per_initial_lot']=a['net_pnl']/a['opened_volume']
        # Entry signature excludes quantity, but requires identical normalized opening price/date weights.
        sig=defaultdict(Decimal)
        for e in a['entryfills']:sig[(e['trading_date'],e['execution_datetime'],str(e['price']))]+=D(e['volume'])/a['opened_volume']
        a['entry_signature']=js([[*k,str(v)] for k,v in sorted(sig.items())])
        a['entry_schedule_json']=js(a.pop('entryfills'));a['exit_schedule_json']=js(a.pop('exitfills'))
        a['dd_window_overlap']=a['entry_trading_date']<=DD_W['trough_date'] and a['exit_trading_date']>DD_W['peak_date']
        for k in ['queue','cash','pos','entry_weight','sign']:a.pop(k,None)
        rows.append(clean(a))
    rf=pd.DataFrame(rows).sort_values('round_id');close(rf.net_pnl.sum(),daily.net_pnl.sum(),arm+':total ledger')
    return dict(rounds=rf,fills=pd.DataFrame(fillrows),segments=pd.DataFrame(segments),daily=daily,effective=effective,weekly=weekly,fill_to_round=fill_to_round,epoch=epoch)


def pair_rounds(b,w):
    keys=['vt_symbol','physical_epoch','direction','entry_trading_date']
    assert not b.duplicated(keys).any() and not w.duplicated(keys).any()
    m=w.merge(b,on=keys,how='outer',suffixes=('_w','_b'),indicator='presence',validate='one_to_one')
    out=[]
    for _,r in m.iterrows():
        both=r['presence']=='both';e=bool(both and r['entry_signature_w']==r['entry_signature_b'])
        x=r.to_dict();x['pair_status']='matched_same_entry' if e else ('entry_inconsistent' if both else ('W_only' if r['presence']=='left_only' else 'B_only'))
        x['entry_consistent']=e;x['net_pnl_delta_w_minus_b']=(r.net_pnl_w if pd.notna(r.net_pnl_w) else 0)-(r.net_pnl_b if pd.notna(r.net_pnl_b) else 0)
        x['quantity_scale_component']=None;x['unit_exit_price_component']=None;x['unit_exit_cost_component']=None;x['unit_total_component']=None
        if e:
            qw,qb=D(r.opened_volume_w),D(r.opened_volume_b);nb,pb,pw=D(r.net_pnl_b)/qb,D(r.price_pnl_per_initial_lot_b),D(r.price_pnl_per_initial_lot_w)
            scale=(qw-qb)*nb;unit=qw*(D(r.net_pnl_w)/qw-nb);price=qw*(pw-pb)
            x.update(quantity_scale_component=float(scale),unit_exit_price_component=float(price),unit_exit_cost_component=float(unit-price),unit_total_component=float(unit))
            close(scale+unit,x['net_pnl_delta_w_minus_b'],'static pair identity')
        x['pair_id']=f'P{len(out)+1:03d}';out.append(clean(x))
    return pd.DataFrame(out)


def snapshot_compare(name,keys,b,w):
    frames={}
    for arm,path in ARM.items():
        d=read(path/(name+'.csv')).copy();d['source_row']=np.arange(len(d))+2
        for k in keys:d[k]=d[k].fillna('').astype(str)
        d['_occurrence']=d.groupby(keys,dropna=False).cumcount()
        if name=='entry_risk':
            actual_ids=set((b if arm=='B' else w)['fills'].order_id)
            f=(b if arm=='B' else w)['fills'];order_to_round=dict(zip(f.order_id,f.round_id))
            d['order_has_actual_fill']=d.signal_order_id.isin(actual_ids);d['actual_round_id']=d.signal_order_id.map(order_to_round)
        frames[arm]=d
    k=keys+['_occurrence'];m=frames['W'].merge(frames['B'],on=k,how='outer',suffixes=('_w','_b'),indicator='presence',validate='one_to_one')
    ignore={'profile','result_scope','candidate_index','entry_index','diagnostic_index','source_row','signal_order_id','actual_round_id'}
    common=[c for c in frames['W'].columns if c in frames['B'].columns and c not in k and c not in ignore]
    changes=Counter();diffs=[]
    for _,r in m.iterrows():
        changed=[]
        if r['presence']=='both':
            for c in common:
                a,z=r[c+'_w'],r[c+'_b']
                equal=(pd.isna(a) and pd.isna(z)) or (pd.notna(a) and pd.notna(z) and ((isinstance(a,Number) and isinstance(z,Number) and math.isclose(float(a),float(z),rel_tol=1e-12,abs_tol=1e-8)) or (not isinstance(a,Number) and not isinstance(z,Number) and str(a)==str(z))))
                if not equal:changed.append(c);changes[c]+=1
        diffs.append(js(changed))
    m['changed_fields_json']=diffs
    write(name.replace('entry_candidates','matched_entry_candidates').replace('entry_risk','matched_entry_risk').replace('rollover_shape_same_volume','matched_rollovers')+'.csv',m)
    return m,dict(row_counts={arm:len(d) for arm,d in frames.items()},presence_counts=m.presence.value_counts().to_dict(),changed_field_counts=dict(changes))


def write(name,data):
    if isinstance(data,pd.DataFrame):data.to_csv(OUT/name,index=False)
    else:(OUT/name).write_text(json.dumps(clean(data),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def triggers_table(w,pairs):
    tr=read(ARM['W']/'profit_half_triggers.csv');ep=read(ARM['W']/'profit_half_episodes.csv')
    anchors=read(ARM['W']/'execution_anchor_requests.csv');events=read(ARM['W']/'trade_events.csv')
    created=ep[ep.action.eq('created')].copy();assert created.episode_id.is_unique
    output=[];rr=w['rounds'];ff=w['fills'];cal=list(w['daily'].date);wby=rr.set_index('round_id');pp=pairs.set_index('round_id_w');seen=[]
    for idx,t in tr.iterrows():
        e=created[created.episode_id.eq(t.episode_id)];assert len(e)==1;e=e.iloc[0]
        q=rr[(rr.vt_symbol==t.vt_symbol)&(rr.direction==t.direction)&(rr.entry_trading_date>e.entry_signal_date)&(rr.entry_trading_date<=t.signal_date)&(rr.exit_trading_date>=t.signal_date)]
        # Entry signal date may itself equal same-day execution trading date for daytime contracts.
        if len(q)!=1:q=rr[(rr.vt_symbol==t.vt_symbol)&(rr.direction==t.direction)&(rr.entry_trading_date>=e.entry_signal_date)&(rr.entry_trading_date<=t.signal_date)&(rr.exit_trading_date>=t.signal_date)]
        assert len(q)==1,(t.episode_id,t.vt_symbol,t.signal_date,q.round_id.tolist());r=q.iloc[0];rid=r.round_id;seen.append(rid)
        an=anchors[(anchors.vt_symbol==t.vt_symbol)&(anchors.signal_date==t.signal_date)&anchors.offset.eq('平')]
        assert len(an)==1,(rid,'anchor ambiguity',len(an));an=an.iloc[0]
        f=ff[(ff.round_id==rid)&ff.order_id.eq(an.order_id)]
        assert len(f)==1,(rid,t.reason,len(f));f=f.iloc[0];nextday=cal[cal.index(t.signal_date)+1]
        assert f.trading_date==nextday and an.trading_date==nextday
        event=events[(events.vt_symbol==t.vt_symbol)&events.date.eq(t.signal_date)&events.reason.eq(t.reason)]
        assert len(event)==1;close(event.iloc[0].volume,t.close_volume,'half event volume')
        forced=events[(events.vt_symbol==t.vt_symbol)&events.date.eq(t.signal_date)&events.reason.eq('forced_margin_deleverage')&events.offset.eq('Close')]
        forced_qty=float(forced.volume.sum())
        if f.volume!=t.close_volume:
            forced=events[(events.vt_symbol==t.vt_symbol)&events.date.eq(t.signal_date)&events.reason.eq('forced_margin_deleverage')]
            forced_qty=float(forced.volume.sum())
        close(f.volume,float(t.close_volume)+forced_qty,'net half plus same-day forced quantity')
        close(f.price,an.daily_open,'anchor daily open')
        week=w['weekly'][(w['weekly'].vt_symbol==t.vt_symbol)&(w['weekly'].contract_epoch_id==r.physical_epoch)&(w['weekly'].week_end==t.week_end)];assert len(week)==1;week=week.iloc[0]
        close(week.close,t.close,'signal close');close(t.cost,r.weighted_entry_price,'trigger actual cost')
        pct=(D(t.close)-D(t.cost))/D(t.cost) if t.direction=='long' else (D(t.cost)-D(t.close))/D(t.cost)
        assert pct>D('0.05') and t.fresh and t.entry_price_synced and t.close_volume==math.floor(t.pre_volume/2) and t.remaining_volume>=1
        pair=pp.loc[rid];x={**clean(t.to_dict()),'trigger_source_row':idx+2,'round_id_w':rid,'actual_entry_trade_id':r.entry_trade_id,'actual_entry_trading_date':r.entry_trading_date,'actual_entry_execution_datetime':r.entry_execution_datetime,'actual_entry_cost':r.weighted_entry_price,'physical_epoch':r.physical_epoch,'source_week_end':str(week.week_end),'source_week_days':week.source_days,'strict_profit_gt5_verified':True,'strict_price_profit_pct_decimal':str(pct),'next_trading_date':nextday,'half_fill_trade_id':f.trade_id,'half_execution_datetime':f.execution_datetime,'half_execution_trading_date':f.trading_date,'half_execution_price':f.price,'half_execution_qty':t.close_volume,'net_order_execution_qty':f.volume,'same_order_forced_margin_qty':forced_qty,'actual_fill_reason_label':f.exit_reason,'w_remaining_after_net_order':t.remaining_volume-forced_qty,'w_initial_qty':r.opened_volume,'w_remaining_immediately_after_half':t.remaining_volume,'w_final_status':r.status,'w_final_exit_or_mark_date':r.exit_trading_date,'w_final_mark':r.terminal_mark,'w_exit_schedule_json':r.exit_schedule_json,'w_net_pnl':r.net_pnl,'w_net_pnl_per_initial_lot':r.net_pnl_per_initial_lot,'w_price_pnl_per_initial_lot':r.price_pnl_per_initial_lot,'dd_window_overlap':r.dd_window_overlap}
        for c in ['pair_id','pair_status','round_id_b','entry_execution_datetime_b','weighted_entry_price_b','opened_volume_b','exit_schedule_json_b','status_b','terminal_mark_b','net_pnl_b','net_pnl_per_initial_lot_b','price_pnl_per_initial_lot_b','net_pnl_delta_w_minus_b','quantity_scale_component','unit_exit_price_component','unit_exit_cost_component','unit_total_component']:x[c]=clean(pair[c])
        output.append(x)
    assert len(output)==74 and len(set(seen))==74
    return pd.DataFrame(output),ep


def snapshot_attribution(b,w,pairs):
    days=[DD_W['peak_date'],DD_W['trough_date']];snap=[]
    for arm,z in [('B',b),('W',w)]:
        marks={day:{} for day in days}
        for ch in pd.read_csv(source(ARM[arm]/'positions.csv'),usecols=['date','vt_symbol','end_pos','close_price'],chunksize=100000):
            q=ch[ch.date.isin(days)&ch.end_pos.ne(0)]
            for r in q.itertuples():marks[r.date][r.vt_symbol]=D(r.close_price)
        fs=z['fills']
        for day in days:
            totals=D(0)
            for rr in z['rounds'].itertuples():
                fills=fs[fs.round_id.eq(rr.round_id)&fs.trading_date.le(day)]
                if fills.empty:continue
                cash=D(0);pos=D(0);incost=D(0)
                for f in fills.itertuples():
                    sign=D(1 if f.direction=='多' else -1);qty=D(f.volume);price=D(f.price);size=D(rr.contract_size)
                    cost=(D(z['effective']['slippages'][rr.vt_symbol])*size+price*size*D(z['effective']['rates'][rr.vt_symbol]))*qty
                    cash-=sign*price*size*qty+cost;pos+=sign*qty;incost+=cost
                mark=marks[day].get(rr.vt_symbol) if pos else None
                assert pos==0 or mark is not None,(arm,day,rr.round_id,'missing exact-native mark')
                net=cash+(pos*mark*D(rr.contract_size) if pos else 0);totals+=net
                snap.append(dict(arm=arm,round_id=rr.round_id,date=day,vt_symbol=rr.vt_symbol,direction=rr.direction,physical_epoch=rr.physical_epoch,entry_trading_date=rr.entry_trading_date,final_exit_or_mark_date=rr.exit_trading_date,initial_qty=rr.opened_volume,net_position=float(pos),mark_price=float(mark) if mark else None,incurred_cost=float(incost),net_pnl_to_date=float(net),gross_price_pnl_to_date=float(net+incost)))
            curve=z['daily'][z['daily'].date.eq(day)].iloc[0];close(totals,float(curve.account_equity)-150000.,arm+':snapshot net')
    st=pd.DataFrame(snap);write('round_snapshots_peak_trough.csv',st)
    pk=st[st.date.eq(days[0])].set_index('round_id');tr=st[st.date.eq(days[1])].set_index('round_id')
    rows=[]
    for _,r in pairs.iterrows():
        x={k:clean(r[k]) for k in ['pair_id','pair_status','round_id_w','round_id_b','vt_symbol','physical_epoch','direction','entry_trading_date','opened_volume_w','opened_volume_b','weighted_entry_price_w','weighted_entry_price_b','exit_trading_date_w','exit_trading_date_b','dd_window_overlap_w','dd_window_overlap_b']}
        for arm in ['w','b']:
            rid=r['round_id_'+arm]
            for label,lookup in [('peak',pk),('trough',tr)]:
                for fld in ['net_pnl_to_date','gross_price_pnl_to_date','net_position','incurred_cost']:
                    x[f'{label}_{fld}_{arm}']=float(lookup.loc[rid,fld]) if rid in lookup.index else 0.
            x['dd_net_pnl_'+arm]=x['trough_net_pnl_to_date_'+arm]-x['peak_net_pnl_to_date_'+arm]
            x['dd_gross_pnl_'+arm]=x['trough_gross_price_pnl_to_date_'+arm]-x['peak_gross_price_pnl_to_date_'+arm]
        for label in ['prefix','dd_window']:
            a='peak_net_pnl_to_date' if label=='prefix' else 'dd_net_pnl';g='peak_gross_price_pnl_to_date' if label=='prefix' else 'dd_gross_pnl'
            x[label+'_net_delta_w_minus_b']=x[a+'_w']-x[a+'_b']
            x[label+'_scale_component']=None;x[label+'_unit_total_component']=None;x[label+'_unit_price_component']=None;x[label+'_unit_cost_component']=None
            if r.entry_consistent:
                qw,qb=D(r.opened_volume_w),D(r.opened_volume_b);pb=D(x[a+'_b'])/qb
                scale=(qw-qb)*pb;unit=qw*(D(x[a+'_w'])/qw-pb);price=qw*(D(x[g+'_w'])/qw-D(x[g+'_b'])/qb)
                x[label+'_scale_component']=float(scale);x[label+'_unit_total_component']=float(unit);x[label+'_unit_price_component']=float(price);x[label+'_unit_cost_component']=float(unit-price)
                close(scale+unit,x[label+'_net_delta_w_minus_b'],label+':pair conservation')
        rows.append(x)
    p=pd.DataFrame(rows);write('prefix_pair_attribution.csv',p)
    overlap=p.dd_window_overlap_w.eq(True)|p.dd_window_overlap_b.eq(True)
    write('drawdown_round_attribution.csv',p[overlap])
    close(p.prefix_net_delta_w_minus_b.sum(),-65220.,'W peak total difference')
    close(p.dd_window_net_delta_w_minus_b.sum(),19215.,'W less absolute DD interval loss')
    info={}
    for label in ['prefix','dd_window']:
        ss={k:float(p[label+'_'+k].sum()) for k in ['net_delta_w_minus_b','scale_component','unit_total_component','unit_price_component','unit_cost_component']}
        ss['unmatched_net_delta_w_minus_b']=float(p.loc[p.pair_status.ne('matched_same_entry'),label+'_net_delta_w_minus_b'].sum())
        close(ss['scale_component']+ss['unit_total_component']+ss['unmatched_net_delta_w_minus_b'],ss['net_delta_w_minus_b'],label+':all conservation')
        info[label]=ss
    # Bind actual opening order to its original risk snapshot. Plans without fills cannot appear here.
    sizing=[]
    fields=['entry_index','date','entry_context','signal','risk_mode','sizing_method','estimated_equity','sizing_equity','limited_balance','allowed_capital','total_margin_in_use_before','risk_ratio','risk_multiplier','target_risk_amount','risk_per_contract','contracts_by_risk','contracts_by_margin','contracts_by_single_trade_cap','risk_cluster_cap_amount','risk_cluster_reserved_margin_before','risk_cluster_max_volume','risk_cluster_selected_volume_before','risk_cluster_selected_volume','selected_volume','actual_filled_volume','loss_streak','profit_recovery_streak','effective_streak_risk_multipliers','oi_price_confirm_risk_restore_applied','oi_price_confirm_risk_restore_effective_multiplier','directional_30d_risk_boost_applied','directional_30d_low_volume_discount_applied','same_direction_correlation_active_count','same_direction_correlation_gate_weight','signal_order_id']
    for arm,z in [('B',b),('W',w)]:
        risk=read(ARM[arm]/'entry_risk.csv');risk['source_entry_risk_row']=np.arange(len(risk))+2
        for r in z['rounds'].itertuples():
            fill=z['fills'][z['fills'].trade_id.eq(r.entry_trade_id)].iloc[0]
            q=risk[risk.signal_order_id.eq(fill.order_id)];assert len(q)==1,(arm,r.round_id,'entry risk join',len(q));q=q.iloc[0]
            x={k:getattr(r,k) for k in ['arm','round_id','vt_symbol','direction','physical_epoch','entry_trading_date','entry_execution_datetime','opened_volume','weighted_entry_price','net_pnl','dd_window_overlap']}
            for k in fields+['source_entry_risk_row']:x[k]=clean(q[k])
            x['actual_initial_qty_to_equity']=r.opened_volume/q.estimated_equity
            x['actual_initial_risk_to_equity']=r.opened_volume*q.risk_per_contract/q.estimated_equity
            x['source_order_id']=fill.order_id;sizing.append(x)
    sf=pd.DataFrame(sizing);write('actual_round_sizing.csv',sf)
    # Exact matched-round entry snapshots, including every difference and earliest divergence.
    ww=sf[sf.arm.eq('W')].drop(columns='arm');bb=sf[sf.arm.eq('B')].drop(columns='arm')
    sm=pairs[['pair_id','round_id_w','round_id_b','pair_status']].merge(ww,left_on='round_id_w',right_on='round_id',how='left').drop(columns='round_id').merge(bb,left_on='round_id_b',right_on='round_id',how='left',suffixes=('_w','_b')).drop(columns='round_id')
    write('actual_round_sizing_pairs.csv',sm)
    info['dd_round_count']=int(overlap.sum());info['actual_round_sizing_count']=len(sf)
    return info


if __name__=='__main__':
    if OUT.exists() and '--refresh-unfrozen' not in sys.argv:raise FileExistsError(OUT)
    OUT.mkdir(parents=True,exist_ok='--refresh-unfrozen' in sys.argv)
    DD_W=drawdown(read(ARM['W']/'daily.csv'))
    b=rebuild('B',ARM['B']);w=rebuild('W',ARM['W']);pairs=pair_rounds(b['rounds'],w['rounds'])
    assert len(b['rounds'])==359 and len(w['rounds'])==353
    assert b['rounds'].status.value_counts().to_dict()=={'closed':355,'terminal_open':4}
    assert w['rounds'].status.value_counts().to_dict()=={'closed':349,'terminal_open':4}
    assert pairs.pair_status.value_counts().get('matched_same_entry',0)==339
    close(pairs.net_pnl_delta_w_minus_b.sum(),-1476430.,'entire W-B bridge')
    write('rounds_all.csv',pd.concat([b['rounds'],w['rounds']],ignore_index=True));write('round_pairs.csv',pairs)
    write('fills_all.csv',pd.concat([b['fills'],w['fills']],ignore_index=True));write('fifo_segments_all.csv',pd.concat([b['segments'],w['segments']],ignore_index=True))
    triggers,ep=triggers_table(w,pairs);write('profit_half_triggers_all.csv',triggers)
    write('reason_label_mismatches.csv',triggers[triggers.actual_fill_reason_label.ne(triggers.reason)])
    cand,cs=snapshot_compare('entry_candidates',['date','product_vt_symbol','contract_vt_symbol','direction','entry_context','signal'],b,w)
    risk,rs=snapshot_compare('entry_risk',['date','product_vt_symbol','contract_vt_symbol','direction','entry_context','signal','layer_kind'],b,w)
    roll,ros=snapshot_compare('rollover_shape_same_volume',['date','product_vt_symbol','old_contract_vt_symbol','target_contract_vt_symbol','direction'],b,w)
    # All trade events retained, and matched on semantic identity for guard evidence.
    events=[]
    for arm,path in ARM.items():
        d=read(path/'trade_events.csv');d['source_row']=np.arange(len(d))+2;d['arm']=arm;events.append(d)
    ev=pd.concat(events,ignore_index=True);write('trade_events_all.csv',ev)
    for arm,path in ARM.items():
        load(path/'actual_strategy_settings.json');load(path/'profit_half_acceptance.json') if arm=='W' else None
        load(path/'historical_epoch_transitions.json');load(path/'input_manifest.json')
    code=source(ROOT/'examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py');cap=source(ROOT/'examples/portfolio_backtesting/analyze_qmt_roll_stage830_stage827_c2_broker10_margin_cap.py');source(__file__)
    eq={}
    for arm,z in [('B',b),('W',w)]:eq[arm]=dict(round_count=len(z['rounds']),closed_count=int(z['rounds'].status.eq('closed').sum()),open_count=int(z['rounds'].status.eq('terminal_open').sum()),net_pnl=float(z['rounds'].net_pnl.sum()),entry_cost=float(z['rounds'].entry_cost.sum()),exit_cost=float(z['rounds'].exit_cost.sum()),dd=drawdown(z['daily']))
    matched=pairs[pairs.entry_consistent];unw=pairs[pairs.pair_status.eq('W_only')];unb=pairs[pairs.pair_status.eq('B_only')]
    sums={k:float(matched[k].sum()) for k in ['net_pnl_delta_w_minus_b','quantity_scale_component','unit_exit_price_component','unit_exit_cost_component','unit_total_component']}
    sums.update(W_only_net_pnl=float(unw.net_pnl_w.sum()),B_only_net_pnl=float(unb.net_pnl_b.sum()),unmatched_delta=float(unw.net_pnl_w.sum()-unb.net_pnl_b.sum()),total_delta=float(pairs.net_pnl_delta_w_minus_b.sum()))
    close(sums['quantity_scale_component']+sums['unit_total_component']+sums['unmatched_delta'],sums['total_delta'],'final attribution bridge')
    # Episode CREATED is a target plan; map created to real fill rounds using entry signal + direction + contract.
    plans=ep[ep.action.eq('created')].copy();real=[]
    for _,p in plans.iterrows():
        nextday=w['daily'].date[w['daily'].date.gt(p.entry_signal_date)]
        td=nextday.iloc[0] if len(nextday) else None
        m=w['rounds'][(w['rounds'].vt_symbol==p.vt_symbol)&(w['rounds'].direction==p.direction)&(w['rounds'].entry_trading_date==td)]
        real.append(m.round_id.iloc[0] if len(m)==1 else None)
    plans['actual_round_id']=real;write('episode_created_plans.csv',plans)
    eventcounts=ev.groupby(['arm','reason']).size().unstack(0,fill_value=0).reset_index();write('event_reason_counts.csv',eventcounts)
    prefix_dd_bridge=snapshot_attribution(b,w,pairs)
    summary=dict(prefix_dd_bridge=prefix_dd_bridge,schema='stage031_native_round_static_attribution_v1',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),status='DERIVED_PENDING_INDEPENDENT_REVIEW',financial_replays=0,strategy_imports=0,downloads=0,production_qualified=False,promotion='NO_PROMOTION',arms=eq,pair_counts=pairs.pair_status.value_counts().to_dict(),static_bridge=sums,profit_half=dict(trigger_count=len(triggers),strict_gt5_passed=len(triggers),next_trading_day_fill_passed=len(triggers),unit_total_sum=float(triggers.unit_total_component.sum()),quantity_scale_sum=float(triggers.quantity_scale_component.sum()),unit_price_sum=float(triggers.unit_exit_price_component.sum()),unit_cost_sum=float(triggers.unit_exit_cost_component.sum()),unmatched_count=int(triggers.pair_status.ne('matched_same_entry').sum())),episode_created_plan_count=len(plans),episode_created_actual_round_match_count=int(plans.actual_round_id.notna().sum()),episode_created_plan_not_a_fill=True,entry_candidates=cs,entry_risk=rs,rollover=ros,dd_window=DD_W,accounting_basis=dict(native_round='Only original actual OPEN fills start a flat-to-flat native-contract round; includes partial exits and terminal-open MTM; no cross-rollover joining.',pair_key=['native_contract','physical_epoch_from_frozen_weekly_bars','direction','actual_entry_trading_date'],strict_same_entry='Matched price/date/execution datetime weights for all opening fills, normalized by opened volume.',formula='PNL_W-PNL_B=(qW-qB)*(PNL_B/qB)+qW*((PNL_W/qW)-(PNL_B/qB))',q='Sum of actual opening quantities within the native round; first-open quantities equal sum if no add fills; entry signature enforces same normalized opening schedule.',price_component='qW*(gross_price_PNL_W/qW-gross_price_PNL_B/qB)',cost_component='unit_total_component minus unit_exit_price_component; incurred entry and exit slippage/commission only; terminal remaining inventory has no synthetic exit fee.',cost_allocation='FIFO entry costs proportional to each closed matched quantity; remaining entry costs stay in terminal MTM.',causality='Static realized-path accounting identity only. No same-size rerun/counterfactual; quantities and unmatched trades can reflect feedback, and no total component is labelled sold-too-early.',terminal='Mark at frozen 2026-10-26 real-native close from positions.csv; retain prior partial realized PNL.'),source_files_sha256=SOURCES,assertions=dict(fill_clock_identity=True,all_original_fills_once=True,real_open_round_counts=True,fifo_and_native_cash_conservation=True,terminal_positions_and_daily_net_conservation=True,physical_epoch_no_crossing=True,pair_one_to_one=True,all_74_trigger_cost_threshold_week_nextday_qty_verified=True,static_bridge_exact_tolerance_1e_6=True))
    write('summary.json',summary)
    for p,d in SOURCES.items():assert sha(p)==d,('source mutated',p)
    schema={p.name:list(pd.read_csv(p,nrows=0).columns) for p in sorted(OUT.glob('*.csv'))}
    write('table_schema.json',schema)
    outputs={str(p.resolve()):sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='source_and_output_manifest.json'}
    write('source_and_output_manifest.json',dict(schema='stage031_trade_attribution_manifest_v1',source_files_sha256=SOURCES,output_files_sha256=outputs,self_hash_excluded=True))
    print(json.dumps(clean(dict(arms=eq,pair_counts=summary['pair_counts'],static_bridge=sums,profit_half=summary['profit_half'],episode_created=summary['episode_created_plan_count'],episode_actual=summary['episode_created_actual_round_match_count'],entry_candidates=cs,entry_risk=rs,rollover=ros)),ensure_ascii=False,indent=2))
