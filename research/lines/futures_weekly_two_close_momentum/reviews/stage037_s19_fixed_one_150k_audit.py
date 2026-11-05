import hashlib,json
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal
from math import sqrt
import numpy as np
import pandas as pd

root=Path('/Users/mac/Desktop/fian/weekly19-stop-reversal.local/research/lines')
line=root/'futures_weekly_two_close_momentum'
prior=line/'outputs/stage035_s19_half_pct_20261104'
source=prior/'fixed_one'
out=line/'outputs/stage037_s19_fixed_one_150k_20261104'
tail=line/'outputs/stage033_s19_data/attempt002'
history=root/'futures_weekly19_stop_reversal/outputs'
admitted=history/'stage002_data/data_approved'
start=150000
target='2026-11-04'

def j(path): return json.loads(path.read_text())
def sha(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def manifest(folder):
    listed={}
    for line in (folder/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split(maxsplit=1)
        assert name not in listed and digest==sha(folder/name)
        listed[name]=digest
    assert set(listed)=={str(x.relative_to(folder)) for x in folder.rglob('*') if x.is_file() and x.name!='SHA256SUMS'}
    return listed
parent_hashes,output_hashes=manifest(prior),manifest(out)
receipt=j(out/'receipt.json')
assert sha(prior/'SHA256SUMS')==receipt['parent_manifest_sha256']
assert sha(line/'reviews/stage035_s19_half_pct_audit.json')==receipt['parent_audit_sha256']
assert sha(line/'stages/20261104_1743_stage037_s19_fixed_one_150k_design.md')==receipt['design_sha256']
assert sha(line/'tools/stage037_s19_fixed_one_150k.py')==receipt['entrypoint_sha256']
old,new=j(source/'inputs.json'),j(out/'inputs.json')
assert old['initial']==300000 and new['initial']==start and new=={**old,'initial':start}
assert new['cash_risk_fraction'] is None and len(new['products'])==19
assert new['inputs_sha256']==receipt['market_sha256']
pins={**new['inputs_sha256'],**new['source_sha256']}
assert all(sha(Path(name))==digest for name,digest in pins.items())
reproduced=['annual.csv','cycles.csv','entry_filter.csv','fills.csv','four_up_blocks.csv','gaps.csv','signals.csv','terminal.json','week_body_filter.csv']
assert all((out/name).read_bytes()==(source/name).read_bytes() for name in reproduced)
daily=pd.read_csv(out/'daily.csv')
parent_daily=pd.read_csv(source/'daily.csv')
prices=pd.read_csv(admitted/'physical_epoch_daily.csv',usecols=['date','vt_symbol','contract_epoch_id','open','high','low','close'])
epoch=pd.read_csv(admitted/'physical_epochs.csv',dtype=str,usecols=['vt_symbol','contract_epoch_id','contract_yyyymm'])
epoch=epoch[epoch.contract_yyyymm.ge('202611')].set_index('vt_symbol',verify_integrity=True).contract_epoch_id
raw=pd.read_csv(tail/'provider/raw_daily.csv')
new_bars=raw[raw.date.eq(target)&raw.volume.gt(0)].copy()
assert len(new_bars)==26
new_bars['contract_epoch_id']=new_bars.vt_symbol.map(epoch)
prices=pd.concat((prices,new_bars[prices.columns]),ignore_index=True)
market={(x.date,x.contract_epoch_id):x for x in prices.itertuples(index=False)}
assert len(market)==len(prices)
calendar=sorted(set(pd.read_csv(admitted/'mapping.csv',usecols=['date']).date))
expected_days=[d for d in calendar if d>='2015-01-01']+[target]
assert daily.date.to_list()==expected_days and len(expected_days)==2875
common=['date','position_value','positions','margin','cumulative_slippage','cumulative_commission','net_pnl']
pd.testing.assert_frame_equal(parent_daily[common],daily[common])
def near(a,b,atol=1e-7): np.testing.assert_allclose(np.asarray(a,dtype=float),np.asarray(b,dtype=float),rtol=0,atol=atol)
near(parent_daily.equity-daily.equity,start)
near(parent_daily.cash-daily.cash,start)
assert daily.loc[0,['equity','cash','positions','margin','cumulative_slippage']].to_list()==[start,start,0,0,0]

# Work in exact cents and build the opening tape independently from frozen bar data.
def cents(amount):
    scaled=Decimal(str(amount))*100
    exact=scaled.to_integral_value()
    assert abs(exact-scaled)<=Decimal('.0001')
    return int(exact)
spec=j(history/'stage003_D_20261103_attempt01/contract_settings.json')
size={k:int(v) for k,v in spec['sizes'].items()}
rate={k:Decimal(str(v)) for k,v in spec['rates'].items()}
margin_ratio={k:Decimal(str(v)) for k,v in spec['margin_ratios'].items()}
slip_cents={k:cents(size[k]*Decimal(str(v))) for k,v in spec['slippages'].items()}
prices_cents={k:(cents(v.open),cents(v.close)) for k,v in market.items()}
tape=pd.read_csv(out/'fills.csv',keep_default_na=False)
gaps=pd.read_csv(out/'gaps.csv')
cycles=pd.read_csv(out/'cycles.csv',keep_default_na=False)
terminal=j(out/'terminal.json')
by_date={d:list(f.itertuples(index=False)) for d,f in tape.groupby('date',sort=False)}
open_observed=pd.read_csv(out/'opening_funding.csv',keep_default_na=False)
positions={}
cycle_flow=defaultdict(int)
entries={}
exits={}
expected_open=[]
expected_daily=[]
cash=cents(start)
slippage=commission=0
missing_mark=Counter()
turns=Counter()

def mark(day,leg):
    value=margin=0
    for product,x in positions.items():
        ep,contract,side,cy,last=x
        price=prices_cents.get((day,ep),(last,last))[leg]
        notional=price*size[contract]
        value+=notional*side
        margin+=Decimal(notional)*margin_ratio[contract]
        if leg==1:
            if (day,ep) not in prices_cents: missing_mark[day,product]+=1
            x[4]=price
    return value,margin

def checkpoint(day,n,product='',why='before_fills'):
    value,margin=mark(day,0)
    equity=cash+value
    expected_open.append((day,n,product,why,equity/100,margin/100,(equity-margin)/100,len(positions)))

for day in expected_days:
    checkpoint(day,0)
    prior_product=None
    previous=None
    for i,f in enumerate(by_date.get(day,()),1):
        assert prior_product is None or f.product>=prior_product
        prior_product=f.product
        b=market[day,f.epoch]
        contract=f.contract
        assert (contract,f.price,f.volume,f.size,f.one_price)==(b.vt_symbol,b.open,1,size[contract],b.high==b.low)
        assert f.side in (-1,1)
        p=cents(f.price)
        notional=p*size[contract]
        s=slip_cents[contract]
        c=Decimal(notional)*rate[contract]
        assert (cents(f.slippage),cents(f.commission))==(s,c)
        flow=-f.side*notional-s-c
        cash+=flow; slippage+=s; commission+=c; cycle_flow[f.cycle]+=flow
        if f.reason in ('entry','roll_open'):
            assert f.product not in positions
            if f.reason=='entry':
                assert f.cycle not in entries
                entries[f.cycle]=f
                if previous and previous.product==f.product:
                    assert previous.reason=='weekly_stop' and previous.signal_day==f.signal_day and previous.side==f.side
                    turns['reversals']+=1
            else:
                assert previous and previous.product==f.product and previous.cycle==f.cycle and previous.side==-f.side and previous.reason=='roll_close'
                turns['rolls']+=1
            positions[f.product]=[f.epoch,contract,f.side,f.cycle,p]
        else:
            old=positions.pop(f.product)
            assert (f.epoch,contract,-f.side,f.cycle)==tuple(old[:4])
            assert f.reason in ('weekly_stop','delivery_guard_exit','roll_close')
            if f.reason!='roll_close':
                assert f.cycle not in exits
                exits[f.cycle]=f
        checkpoint(day,i,f.product,f.reason)
        previous=f
    value,margin=mark(day,1)
    expected_daily.append(((cash+value)/100,cash/100,value/100,margin/100,len(positions),slippage/100,commission/100))
open_calc=pd.DataFrame(expected_open,columns=open_observed.columns).astype({"equity":float,"margin":float,"free_equity":float})
assert open_calc.iloc[:,:4].equals(open_observed.iloc[:,:4])
near(open_calc.iloc[:,4:],open_observed.iloc[:,4:])
assert len(open_calc)==len(tape)+len(daily)
calc=pd.DataFrame(expected_daily,columns=['equity','cash','position_value','margin','positions','cumulative_slippage','cumulative_commission']).astype(float)
near(calc,daily[calc.columns])
assert set(positions)==set(terminal['positions'])
assert not terminal['pending'] and not terminal['pending_reversals']
assert set(missing_mark)==set(zip(gaps[gaps.reason=='held_close_stale'].date,gaps[gaps.reason=='held_close_stale']['product']))
terminal_value={}
for product,(ep,contract,side,cy,mark) in positions.items():
    t=terminal['positions'][product]
    assert (t['epoch'],t['symbol'],t['side'],t['cycle'],cents(t['mark']))==(ep,contract,side,cy,mark)
    assert mark==prices_cents[target,ep][1]
    terminal_value[cy]=side*mark*size[contract]
assert not tape.date.eq(target).any() and not gaps.date.eq(target).any()
assert set(cycles.cycle)==set(entries)
assert set(cycles[cycles.exit_day==''].cycle)==set(terminal_value)
for r in cycles.itertuples(index=False):
    first=entries[r.cycle]; last=exits.get(r.cycle)
    assert (r.product,r.direction,r.entry_day,r.exit_day)==(first.product,first.side,first.date,last.date if last else '')
    flow=cycle_flow[r.cycle]; val=terminal_value.get(r.cycle,0)
    assert (cents(r.cash_flow),cents(r.terminal_mark),cents(r.net_pnl))==(flow,val,flow+val)
ret=calc.equity/np.r_[start,calc.equity.iloc[:-1]]-1
drawdown=calc.equity/np.maximum.accumulate(np.r_[start,calc.equity])[1:]-1
pnl=np.diff(np.r_[start,calc.equity])
near(drawdown,daily.drawdown,1e-12)
near(calc.margin/calc.equity,daily.margin_ratio,1e-12)
near(pnl,daily.net_pnl)
near(pd.Series(pnl).groupby(daily.date.str[:4]).sum(),pd.read_csv(out/'annual.csv').net_pnl)
closed=cycles[cycles.exit_day!='']
wins=closed[closed.net_pnl>0].net_pnl
losses=-closed[closed.net_pnl<0].net_pnl
end_equity=calc.equity.iat[-1]
expected=dict(days=len(daily),initial=start,equity=end_equity,net_pnl=end_equity-start,return_pct=100*(end_equity/start-1),max_dd_pct=100*drawdown.min(),sharpe=ret.mean()/ret.std(ddof=1)*sqrt(252),fills=len(tape),one_price_exits=int(tape.one_price.sum()),rolls=turns['rolls'],closed_cycles=len(closed),wins=len(wins),losses=len(losses),win_rate_pct=100*len(wins)/len(closed),payoff=wins.mean()/losses.mean(),profit_factor=wins.sum()/losses.sum(),slippage=slippage/100,commission=commission/100,net_pnl_double_slippage_same_path=end_equity-start-slippage/100,peak_margin=calc.margin.max(),peak_margin_ratio_pct=100*(calc.margin/calc.equity).max(),days_margin_above_equity=int((calc.margin>calc.equity).sum()),open_positions=len(positions),pending_signals=0,long_pnl=cycles.loc[cycles.direction==1,'net_pnl'].sum(),short_pnl=cycles.loc[cycles.direction==-1,'net_pnl'].sum(),terminal_open_net_pnl=cycles.loc[cycles.exit_day=='','net_pnl'].sum())
summary=j(out/'summary.json')
assert set(summary)==set(expected)|{'start','end','gaps'}
assert (summary['start'],summary['end'])==(expected_days[0],target)
assert summary['gaps']==dict(Counter(gaps.reason))
near(list(expected.values()),[summary[k] for k in expected])
near([end_equity-start],[cycles.net_pnl.sum()])

free=calc.equity-calc.margin
funding=dict(max_positions=int(calc.positions.max()),close_margin_deficit_days=int((free<0).sum()),close_min_free_equity=free.min(),close_min_free_equity_date=daily.loc[free.idxmin(),'date'],opening_snapshots=len(open_calc),opening_margin_deficit_days=int(open_calc.loc[open_calc.free_equity<0,'date'].nunique()),opening_min_free_equity=open_calc.free_equity.min(),opening_min_free_equity_date=open_calc.loc[open_calc.free_equity.idxmin(),'date'],opening_peak_margin_ratio_pct=100*(open_calc.margin/open_calc.equity).max(),peak_drawdown_date=daily.loc[drawdown.idxmin(),'date'],minimum_equity=calc.equity.min(),minimum_equity_date=daily.loc[calc.equity.idxmin(),'date'])
actual=j(out/'funding_summary.json')
assert actual.keys()==funding.keys()
for k,v in funding.items():
    if isinstance(v,str): assert actual[k]==v
    else: near(actual[k],v)
def plain(d): return {k:v.item() if isinstance(v,np.generic) else v for k,v in d.items()}
report=dict(verdict='PASS_WITH_LIMITATIONS',output_manifest_sha=sha(out/'SHA256SUMS'),output_manifest_entries=len(output_hashes),parent_manifest_entries=len(parent_hashes),pins=len(pins),matched_trade_artifacts=reproduced,day_count=len(daily),opening_snapshots=len(open_calc),fill_count=len(tape),total_cycles_including_open=len(cycles),reversals=turns['reversals'],roll_events=turns['rolls'],final_net_pnl_day=daily.net_pnl.iat[-1],minimum_opening=plain(open_calc.loc[open_calc.free_equity.idxmin()].to_dict()),minimum_opening_cash_before_fills=float(open_calc.loc[open_calc.fill_sequence==0,'free_equity'].min()),peak_margin_opening=plain(open_calc.loc[(open_calc.margin/open_calc.equity).idxmax()].to_dict()),funding_summary=actual,financial_summary=summary)
Path('/private/tmp/fian_stage037_audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
