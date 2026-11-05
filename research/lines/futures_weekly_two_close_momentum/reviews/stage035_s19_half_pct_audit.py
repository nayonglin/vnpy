from pathlib import Path
import hashlib,json
from collections import defaultdict,Counter
from functools import lru_cache
from datetime import date
from math import sqrt
from decimal import Decimal as D
import numpy as np
import pandas as pd

root=Path('/Users/mac/Desktop/fian/weekly19-stop-reversal.local/research/lines')
line=root/'futures_weekly_two_close_momentum'
parent=line/'outputs/stage033_s19_annual_starts_20261104'
out=line/'outputs/stage035_s19_half_pct_20261104'
tail=line/'outputs/stage033_s19_data/attempt002'
frozen=root/'futures_weekly19_stop_reversal/outputs'
data_root=frozen/'stage002_data/data_approved'
target='2026-11-04'
def j(path): return json.loads(path.read_text())
def sha(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def manifest(folder):
    result={}
    for row in (folder/'SHA256SUMS').read_text().splitlines():
        digest,name=row.split(maxsplit=1)
        assert name not in result and sha(folder/name)==digest,(folder,name)
        result[name]=digest
    assert set(result)=={str(x.relative_to(folder)) for x in folder.rglob('*') if x.is_file() and x.name!='SHA256SUMS'}
    return result
hashes={'stage033':len(manifest(parent)),'stage035':len(manifest(out))}
receipt=j(out/'receipt.json')
assert sha(parent/'SHA256SUMS')==receipt['parent_manifest_sha256']
assert sha(line/'reviews/stage033_s19_annual_starts_audit.json')==receipt['parent_audit_sha256']
assert sha(line/'stages/20261104_1718_stage035_s19_half_pct_design.md')==receipt['design_sha256']
assert sha(line/'tools/stage035_s19_half_pct.py')==receipt['entrypoint_sha256']
pin_hash={}
def pins(entries):
    for path,digest in entries.items():
        if path not in pin_hash: pin_hash[path]=sha(Path(path))
        assert pin_hash[path]==digest,path
pins(receipt['inputs_sha256'])
parent_conf=j(parent/'2015/inputs.json')
parent_conf.pop('source_sha256')
assert parent_conf['inputs_sha256']==receipt['inputs_sha256']
products=parent_conf['products']
assert len(products)==19
for name,fraction in [('fixed_one',None),('cash_risk_0_5pct',0.005)]:
    conf=j(out/name/'inputs.json')
    pins(conf.pop('source_sha256'))
    assert conf=={**parent_conf,'cash_risk_fraction':fraction}
fixed=out/'fixed_one'
assert {f.name for f in fixed.iterdir()}=={f.name for f in (parent/'2015').iterdir()}
for f in fixed.iterdir():
    if f.name!='inputs.json': assert f.read_bytes()==(parent/'2015'/f.name).read_bytes(),f.name
mapping=pd.read_csv(data_root/'mapping.csv',usecols=['date','continuous_symbol_vt','main_contract_vt'])
mains={(x.date,x.continuous_symbol_vt):x.main_contract_vt for x in mapping.itertuples(index=False)}
days=sorted(set(mapping.date))+[target]
assert days==sorted(set(days))
calendar=sorted(set(days).union(pd.read_csv(data_root/'forward_calendar.csv').date))
weekly=defaultdict(list)
for d in calendar:
    if d>='2014-01-01': weekly[date.fromisoformat(d).isocalendar()[:2]].append(d)
weeks=list(weekly.values())
week_of={d:i for i,w in enumerate(weeks) for d in w}
assert weeks[week_of[target]][-1]=='2026-11-06'
previous_day={d0:d1 for d1,d0 in zip(days,days[1:])}
next_day={d0:d1 for d0,d1 in zip(days,days[1:])}
@lru_cache(None)
def guard(epoch):
    m=epoch.split('.')[-1]
    boundary=f'{m[:4]}-{m[4:]}-01'
    return [d for d in calendar if d<boundary][-5]
epochs=pd.read_csv(data_root/'physical_epochs.csv',dtype=str)
young=epochs[epochs.contract_yyyymm.ge('202611')]
epoch_by_vt=dict(zip(young.vt_symbol,young.contract_epoch_id))
prices=pd.read_csv(data_root/'physical_epoch_daily.csv',usecols=['date','vt_symbol','contract_epoch_id','open','high','low','close'])
raw=pd.read_csv(tail/'provider/raw_daily.csv')
raw=raw[(raw.date==target)&(raw.volume>0)].copy()
raw['contract_epoch_id']=raw.vt_symbol.map(epoch_by_vt)
prices=pd.concat([prices,raw[prices.columns]],ignore_index=True)
bars={(x.date,x.contract_epoch_id):x for x in prices.itertuples(index=False)}
assert len(bars)==len(prices)
spec=j(frozen/'stage003_D_20261103_attempt01/contract_settings.json')
def by_spec(name,contract): return D(str(spec[name][contract]))
@lru_cache(None)
def weekbar(epoch,i):
    if i<0: return None
    data=[bars.get((d,epoch)) for d in weeks[i]]
    if None in data: return None
    return data[0].open,max(x.high for x in data),min(x.low for x in data),data[-1].close
def near(a,b):
    np.testing.assert_allclose(np.array(a,dtype=float),np.array(b,dtype=float),atol=1e-7,rtol=0)
arm=out/'cash_risk_0_5pct'
daily=pd.read_csv(arm/'daily.csv')
opening=pd.read_csv(arm/'opening_marks.csv',keep_default_na=False)
sizing=pd.read_csv(arm/'risk_sizing.csv')
tape=pd.read_csv(arm/'fills.csv',keep_default_na=False)
sig=pd.read_csv(arm/'signals.csv')
cycle=pd.read_csv(arm/'cycles.csv',keep_default_na=False)
gaps=pd.read_csv(arm/'gaps.csv')
terminal=j(arm/'terminal.json')
assert daily.date.to_list()==[d for d in days if d>='2015-01-01']
assert daily.loc[0,['equity','cash','positions','margin','lots','cumulative_slippage']].to_list()==[300000,300000,0,0,0,0]
assert not terminal['pending'] and not terminal['pending_reversals']
assert not any(df.date.eq(target).any() for df in (sizing,tape,sig,gaps))
for name in ('cash_risk_0_5pct','fixed_one'):
    t=j(out/name/'terminal.json')
    assert all((target,v['epoch']) in bars and bars[target,v['epoch']].close==v['mark'] for v in t['positions'].values())

sig_index={}
for s in sig.itertuples(index=False):
    i=week_of[s.date]
    assert s.date==weeks[i][-1]
    cw,pw=weekbar(s.epoch,i),weekbar(s.epoch,i-1)
    assert (cw[3],pw[3])==(s.close,s.prior_close)
    assert (s.date,s.product,s.action) not in sig_index
    sig_index[s.date,s.product,s.action]=s
    if s.action.startswith('open_'):
        sign=1 if s.action=='open_long' else -1
        tw=weekbar(s.epoch,i-2)
        assert tw[3]==s.older_close
        assert sign*cw[3]>sign*pw[3]>sign*tw[3] and all(sign*(w[3]-w[0])>0 for w in (cw,pw))
        assert s.contract==mains[s.date,s.product] and s.stop==cw[2 if sign==1 else 1]
        hist=[weekbar(s.epoch,i-k) for k in range(21)]
        if all(hist):
            assert not all(sign*(cw[3]-hist[k][3])<0 for k in (5,10,20))
        if sign==1 and all(hist[:5]):
            assert not all(l[3]>r[3] for l,r in zip(hist[:5],hist[1:5]))
    elif s.action=='close_long':
        assert cw[3]<=pw[2]==s.stop
    else:
        assert s.action=='close_short' and cw[3]>=pw[1]==s.stop

by_f={(d,p):list(df.itertuples(index=False)) for (d,p),df in tape.groupby(['date','product'],sort=False)}
by_s={(x.date,x.product):x for x in sizing.itertuples(index=False)}
assert len(by_s)==len(sizing)
open_signals=set()
roll_count=Counter()
risk_count=Counter()
reverse_count=Counter()
positions={}
open_seen={}
close_seen={}
cycle_cash=defaultdict(D)
cash=D(300000)
slip=commission=D(0)
daily_seen=[]
open_seen_tape=[]
max_initial_ratio=D(0)
def open_account(day):
    equity=cash
    margin=D(0)
    for epoch,contract,side,lots,last,cy in positions.values():
        market=bars.get((day,epoch))
        price=D(str(market.open)) if market is not None else last
        exposure=lots*price*by_spec('sizes',contract)
        equity+=side*exposure
        margin+=exposure*by_spec('margin_ratios',contract)
    return equity,margin,equity-margin,len(positions),sum(v[3] for v in positions.values())
def account_fill(f):
    global cash,slip,commission
    market=bars[f.date,f.epoch]
    sz=by_spec('sizes',f.contract)
    price=D(str(f.price))
    s=sz*by_spec('slippages',f.contract)*f.volume
    c=sz*by_spec('rates',f.contract)*price*f.volume
    assert (f.contract,f.price,f.one_price,f.size)==(market.vt_symbol,market.open,market.high==market.low,sz)
    assert D(str(f.slippage))==s and D(str(f.commission))==c
    flow=-f.side*sz*price*f.volume-s-c
    cash+=flow; cycle_cash[f.cycle]+=flow; slip+=s; commission+=c

for day in daily.date:
    open_seen_tape.append((day,'',*open_account(day)))
    for product in products:
        fills=by_f.get((day,product),[])
        order=by_s.get((day,product))
        if not fills and order is None: continue
        old_pos=None
        exit_fill=None
        if fills and fills[0].reason in ('weekly_stop','delivery_guard_exit','roll_close','roll_funding_exit'):
            exit_fill=fills[0]
            old_pos=positions.pop(product)
            ep,con,side,lots,last,cy=old_pos
            assert (exit_fill.epoch,exit_fill.contract,exit_fill.side,exit_fill.volume,exit_fill.cycle)==(ep,con,-side,lots,cy)
            account_fill(exit_fill)
            if exit_fill.reason=='weekly_stop':
                s=sig_index[exit_fill.signal_day,product,'close_long' if side==1 else 'close_short']
                assert (s.epoch,s.stop)==(ep,float(exit_fill.stop)) and exit_fill.date>=next_day[s.date]
                close_seen[cy]=exit_fill
            elif exit_fill.reason=='delivery_guard_exit':
                assert day>=guard(ep)==exit_fill.signal_day and order is None
                close_seen[cy]=exit_fill
            elif exit_fill.reason=='roll_funding_exit':
                close_seen[cy]=exit_fill
        if order is not None:
            assert product not in positions
            b=bars[day,order.epoch]
            assert b.open==order.price and b.vt_symbol==order.contract and b.high>b.low and day<guard(order.epoch)
            eq,mg,free,_,_=open_account(day)
            near([order.equity,order.margin,order.free_cash],[eq,mg,free])
            amount=max(free,D(0))
            size=by_spec('sizes',order.contract)
            quote=D(str(order.price))
            cost=size*(by_spec('slippages',order.contract)+quote*by_spec('rates',order.contract))
            lot_margin=size*quote*by_spec('margin_ratios',order.contract)
            affordable=int(amount//(lot_margin+cost))
            risk=None
            if order.kind=='entry':
                signal=sig_index[order.signal_day,product,'open_long' if order.side==1 else 'open_short']
                assert next_day[order.signal_day]==day
                assert (signal.stop,signal.epoch)==(order.stop,order.epoch)
                open_signals.add((signal.date,product,signal.action))
                budget=amount*D('.005')
                risk=order.side*size*(quote-D(str(order.stop)))
                requested=int(budget//risk) if risk>0 else 0
                near([order.risk_budget,order.risk_per_lot],[budget,risk])
                if exit_fill is not None:
                    assert exit_fill.reason=='weekly_stop' and exit_fill.signal_day==order.signal_day
                    assert exit_fill.side==order.side
                    reverse_count['considered']+=1
            else:
                assert order.kind=='roll' and exit_fill and exit_fill.reason in ('roll_close','roll_funding_exit')
                assert day<guard(old_pos[0]) and order.signal_day==previous_day[day]
                assert old_pos[1]!=order.contract==mains[order.signal_day,product]
                assert order.side==old_pos[2]
                assert pd.isna(order.risk_budget) and pd.isna(order.risk_per_lot)
                assert order.stop==weekbar(order.epoch,week_of[day]-1)[2 if order.side==1 else 1]
                requested=old_pos[3]
            executed=min(requested,affordable)
            if risk is not None and risk<=0: status='at_or_through_stop'
            elif risk is not None and requested==0: status='risk_below_one_lot'
            elif executed==0: status='margin_below_one_lot'
            elif executed<requested: status='margin_capped'
            else: status='filled'
            near([order.margin_per_lot,order.entry_cost_per_lot],[lot_margin,cost])
            assert (requested,affordable,executed,status)==(order.requested_lots,order.affordable_lots,order.executed_lots,order.status)
            (risk_count if order.kind=='entry' else roll_count)[status]+=1
            if executed:
                enter=fills[-1]
                assert enter is not exit_fill and len(fills)==1+int(exit_fill is not None)
                reason='entry' if order.kind=='entry' else 'roll_open'
                assert (enter.reason,enter.epoch,enter.contract,enter.side,enter.volume,enter.signal_day,float(enter.stop))==(reason,order.epoch,order.contract,order.side,executed,order.signal_day,order.stop)
                if reason=='entry':
                    assert enter.cycle not in open_seen
                    open_seen[enter.cycle]=enter
                    assert executed*risk<=budget
                    max_initial_ratio=max(max_initial_ratio,executed*risk/free)
                    if exit_fill: reverse_count['executed']+=1
                else:
                    assert enter.cycle==old_pos[-1] and exit_fill.reason=='roll_close'
                account_fill(enter)
                positions[product]=[enter.epoch,enter.contract,enter.side,enter.volume,quote,enter.cycle]
                eq2,mg2,free2,_,_=open_account(day)
                assert free2==free-executed*(lot_margin+cost) and free2>=0
            else:
                assert len(fills)==int(exit_fill is not None)
        else:
            assert len(fills)==1 and exit_fill is not None
        if fills: open_seen_tape.append((day,product,*open_account(day)))
    mark=D(0); margin=D(0)
    for product,v in positions.items():
        ep,sym,side,lots,last,cy=v
        b=bars.get((day,ep))
        v[4]=D(str(b.close)) if b is not None else last
        assert day[:7].replace('-','')<=ep.split('.')[-1]
        notional=v[4]*by_spec('sizes',sym)*lots
        mark+=side*notional; margin+=notional*by_spec('margin_ratios',sym)
    daily_seen.append((cash+mark,cash,mark,margin,len(positions),slip,commission,sum(v[3] for v in positions.values())))

assert set(by_f)=={(x[0],x[1]) for x in open_seen_tape if x[1]}
reconstructed=pd.DataFrame(open_seen_tape,columns=opening.columns)
assert reconstructed[['date','after_product']].equals(opening[['date','after_product']])
near(reconstructed.iloc[:,2:],opening.iloc[:,2:])
assert opening.free_cash.min()>0
near(daily_seen,daily[['equity','cash','position_value','margin','positions','cumulative_slippage','cumulative_commission','lots']])
terminal_marks={}
for product,(ep,sym,side,lots,last,cy) in positions.items():
    t=terminal['positions'][product]
    assert (t['epoch'],t['symbol'],t['side'],t['volume'],t['mark'],t['cycle'])==(ep,sym,side,lots,float(last),cy)
    terminal_marks[cy]=side*lots*last*by_spec('sizes',sym)
assert set(positions)==set(terminal['positions'])
assert set(terminal_marks)==set(cycle[cycle.exit_day==''].cycle)
for r in cycle.itertuples(index=False):
    first,exit_=open_seen[r.cycle],close_seen.get(r.cycle)
    assert (r.entry_day,r.exit_day,r.product,r.direction)==(first.date,exit_.date if exit_ else '',first.product,first.side)
    tm=terminal_marks.get(r.cycle,D(0))
    near([r.cash_flow,r.terminal_mark,r.net_pnl],[cycle_cash[r.cycle],tm,cycle_cash[r.cycle]+tm])
allowed_gaps={(x.date,x.product,x.contract):x.reason for x in gaps.itertuples(index=False) if x.reason in ('entry_delivery_guard','entry_open_unavailable')}
missed=Counter()
for key,s in sig_index.items():
    if s.action.startswith('open_') and key not in open_signals:
        why=allowed_gaps[next_day[s.date],s.product,s.contract]
        if why=='entry_delivery_guard': assert next_day[s.date]>=guard(s.epoch)
        elif why=='entry_open_unavailable':
            b=bars.get((next_day[s.date],s.epoch))
            assert b is None or b.high==b.low
        missed[why]+=1
assert sum(missed.values())==len(allowed_gaps)
a=np.asarray(daily_seen,dtype=float)
eq=a[:,0]
m=a[:,3]
returns=eq/np.r_[300000,eq[:-1]]-1
ret_day=np.diff(np.r_[300000,eq])
dd=eq/np.maximum.accumulate(np.r_[300000,eq])[1:]-1
near(ret_day,daily.net_pnl)
near(dd,daily.drawdown)
near(m/eq,daily.margin_ratio)
near(pd.Series(ret_day).groupby(daily.date.str[:4]).sum(),pd.read_csv(arm/'annual.csv').net_pnl)
closed=cycle[cycle.exit_day!='']
wins=closed[closed.net_pnl>0].net_pnl
losses=-closed[closed.net_pnl<0].net_pnl
summary=j(arm/'summary.json')
pnl=eq[-1]-300000
near([pnl],[cycle.net_pnl.sum()])
s=dict(days=len(daily),initial=300000,equity=eq[-1],net_pnl=pnl,return_pct=pnl/3000,max_dd_pct=100*dd.min(),sharpe=returns.mean()/returns.std(ddof=1)*sqrt(252),fills=len(tape),one_price_exits=int(tape.one_price.sum()),rolls=roll_count['filled']+roll_count['margin_capped'],closed_cycles=len(closed),wins=len(wins),losses=len(losses),win_rate_pct=100*len(wins)/len(closed),payoff=wins.mean()/losses.mean(),profit_factor=wins.sum()/losses.sum(),slippage=slip,commission=commission,net_pnl_double_slippage_same_path=pnl-float(slip),peak_margin=m.max(),peak_margin_ratio_pct=(m/eq).max()*100,days_margin_above_equity=int((m>eq).sum()),open_positions=len(positions),pending_signals=0,long_pnl=cycle[cycle.direction==1].net_pnl.sum(),short_pnl=cycle[cycle.direction==-1].net_pnl.sum(),terminal_open_net_pnl=cycle[cycle.exit_day==''].net_pnl.sum())
near(list(s.values()),[summary[k] for k in s])
assert summary['gaps']==dict(Counter(gaps.reason))
assert (summary['start'],summary['end'])==(daily.date.iat[0],target)==(receipt['cutoff'].replace(target,daily.date.iat[0]),receipt['cutoff'])
ctf=pd.read_csv(fixed/'daily.csv')
fs=j(fixed/'summary.json')
def jsonnum(x):
    if isinstance(x,D): return float(x)
    if isinstance(x,np.generic): return x.item()
    return x
def day_detail(frame,i,cols):
    return {k:jsonnum(frame.at[i,k]) for k in cols}
sized_max=sizing.iloc[sizing.executed_lots.idxmax()]
cap=sizing[sizing.status=='margin_capped'].to_dict('records')
report=dict(verdict='PASS_WITH_LIMITATIONS',output_manifest_sha=sha(out/'SHA256SUMS'),hashes=hashes,pins=len(pin_hash),opening_rows=len(opening),sizing_rows=len(sizing),sizing_outcomes=dict(risk_count),roll_outcomes=dict(roll_count),reversals=dict(reverse_count),pre_sizing_rejections=dict(missed),candidate_summary=summary,fixed_summary=fs,max_candidate_nominal_initial_risk_pct=float(max_initial_ratio*100),peak_candidate_trade_lots=int(sized_max.executed_lots),peak_candidate_daily_lots=int(daily.lots.max()),peak_candidate_daily_products=int(daily.positions.max()),peak_fixed_daily_products=int(ctf.positions.max()),min_opening_free=day_detail(opening,opening.free_cash.idxmin(),('date','after_product','free_cash','margin','equity')),min_candidate_daily_free=day_detail(daily,(daily.equity-daily.margin).idxmin(),('date','margin','equity')),peak_candidate_open_margin_ratio_pct=float((100*opening.margin/opening.equity).max()),margin_capped_orders=cap,terminal_day_delta={'fixed_one':float(ctf.net_pnl.iat[-1]),'cash_risk_0_5pct':float(daily.net_pnl.iat[-1])})
Path('/private/tmp/fian_stage035_audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
