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
sizing_parent=line/'outputs/stage035_s19_half_pct_20261104'
mc_parent=line/'outputs/stage034_s19_monte_carlo_v1'
out=line/'outputs/stage036_s19_paired_mc_v1'
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
hashes={folder.name:len(manifest(folder)) for folder in (parent,sizing_parent,mc_parent,out)}
receipt=j(out/'receipt.json')
assert sha(mc_parent/'SHA256SUMS')==receipt['parent_mc_manifest_sha256']
assert sha(sizing_parent/'SHA256SUMS')==receipt['parent_sizing_manifest_sha256']
assert sha(line/'stages/20261104_1724_stage036_s19_paired_mc_design.md')==receipt['design_sha256']
assert sha(line/'tools/stage036_s19_paired_mc.py')==receipt['entrypoint_sha256']
assert sha(line/'tools/stage034_s19_monte_carlo.py')==receipt['sampling_source_sha256']
assert sha(mc_parent/'sampling_plan.npz')==receipt['paired_sampling_plan_sha256']
pin_hash={}
def pins(entries):
    for path,digest in entries.items():
        if path not in pin_hash: pin_hash[path]=sha(Path(path))
        assert pin_hash[path]==digest,path
parent_conf=j(sizing_parent/'cash_risk_0_5pct/inputs.json')
pins(parent_conf.pop('source_sha256'))
pins(parent_conf['inputs_sha256'])
products=parent_conf['products']
assert len(products)==19 and parent_conf['cash_risk_fraction']==0.005
assert sha(sizing_parent/'cash_risk_0_5pct/daily.csv')==receipt['dynamic_daily_sha256']['2015']
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

def audit_start(year):
    arm=out/'cold_starts'/str(year)

    daily=pd.read_csv(arm/'daily.csv')
    opening=pd.read_csv(arm/'opening_marks.csv',keep_default_na=False)
    sizing=pd.read_csv(arm/'risk_sizing.csv')
    tape=pd.read_csv(arm/'fills.csv',keep_default_na=False)
    sig=pd.read_csv(arm/'signals.csv')
    cycle=pd.read_csv(arm/'cycles.csv',keep_default_na=False)
    gaps=pd.read_csv(arm/'gaps.csv')
    terminal=j(arm/'terminal.json')
    expected=pd.read_csv(parent/str(year)/'daily.csv',usecols=['date']).date.iloc[:63]
    assert daily.date.equals(expected)
    assert daily.date.to_list()==[d for d in days if d>=f'{year}-01-01'][:63]
    assert sha(arm/'daily.csv')==receipt['dynamic_daily_sha256'][str(year)]
    cutoff=daily.date.iat[-1]
    assert all(daily.date.iat[0]<=x<=cutoff for x in sig.date)
    assert all(daily.date.iat[0]<x<=cutoff for x in tape.date)
    assert not gaps.reason.eq('held_close_stale').any()
    conf=j(arm/'inputs.json')
    pins(conf.pop('source_sha256'))
    assert conf=={**parent_conf,'start':f'{year}-01-01','end':cutoff}
    assert daily.loc[0,['equity','cash','positions','margin','lots','cumulative_slippage']].to_list()==[300000,300000,0,0,0,0]
    for v in terminal['positions'].values():
        assert bars[cutoff,v['epoch']].close==v['mark']
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
        nonlocal cash,slip,commission
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
            if s.date==cutoff:
                action,signal_day,contract,epoch,stop=(terminal['pending_reversals'].get(s.product) or terminal['pending'][s.product])
                assert (action,signal_day,contract,epoch,float(stop))==(s.action,s.date,s.contract,s.epoch,s.stop)
                continue
            why=allowed_gaps[next_day[s.date],s.product,s.contract]
            if why=='entry_delivery_guard': assert next_day[s.date]>=guard(s.epoch)
            elif why=='entry_open_unavailable':
                b=bars.get((next_day[s.date],s.epoch))
                assert b is None or b.high==b.low
            missed[why]+=1
    assert sum(missed.values())==len(allowed_gaps)

    a=np.asarray(daily_seen,dtype=float)
    eq=a[:,0]
    margin=a[:,3]
    returns=eq/np.r_[300000,eq[:-1]]-1
    pnl_day=np.diff(np.r_[300000,eq])
    dd=eq/np.maximum.accumulate(np.r_[300000,eq])[1:]-1
    near(pnl_day,daily.net_pnl)
    near(dd,daily.drawdown)
    near(margin/eq,daily.margin_ratio)
    near(pd.Series(pnl_day).groupby(daily.date.str[:4]).sum(),pd.read_csv(arm/'annual.csv').net_pnl)
    closed=cycle[cycle.exit_day!='']
    summary=j(arm/'summary.json')
    near([summary['equity'],summary['fills'],summary['closed_cycles'],summary['peak_margin_ratio_pct'],summary['slippage'],summary['days_margin_above_equity'],summary['max_dd_pct'],summary['sharpe']],[eq[-1],len(tape),len(closed),100*(margin/eq).max(),slip,int((margin>eq).sum()),100*dd.min(),returns.mean()/returns.std(ddof=1)*sqrt(252)])
    return dict(year=year,start=daily.date.iat[0],end=cutoff,days=len(daily),equity=eq[-1],fills=len(tape),signals=len(sig),opening_marks=len(opening),sizing=len(sizing),closed_cycles=len(closed),rolls=dict(roll_count),risks=dict(risk_count),reverse=dict(reverse_count),margin_deficit_days=int((margin>eq).sum()),pending=len(terminal['pending']),pending_reversals=len(terminal['pending_reversals']))

results=[]
for year in range(2016,2027):
    r=audit_start(year)
    print(r,flush=True)
    results.append(r)
report=dict(verdict='PASS_WITH_LIMITATIONS',output_manifest_sha=sha(out/'SHA256SUMS'),hashes=hashes,pins=len(pin_hash),starts=len(results),totals={key:sum(r[key] for r in results) for key in ('days','fills','signals','opening_marks','sizing','closed_cycles','margin_deficit_days')},results=results)
Path('/private/tmp/fian_stage036_cold_audit.json').write_text(json.dumps(report,indent=2)+'\n')
print({k:v for k,v in report.items() if k!='results'},flush=True)
