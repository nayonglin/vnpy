import hashlib,json
from pathlib import Path
from collections import defaultdict,Counter
from functools import lru_cache
from datetime import date
from decimal import Decimal
from math import sqrt
import numpy as np
import pandas as pd

root=Path('/Users/mac/Desktop/fian/weekly19-stop-reversal.local/research/lines')
line=root/'futures_weekly_two_close_momentum'
prior=line/'outputs/stage037_s19_fixed_one_150k_20261104'
jan=line/'outputs/stage033_s19_annual_starts_20261104'
out=line/'outputs/stage038_s19_fixed_one_150k_halfyear_20261104'
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
attempt=out.with_name('stage038_s19_fixed_one_150k_halfyear_attempt001_ratio_deficit')
parent_hashes,jan_hashes,output_hashes,attempt_hashes=manifest(prior),manifest(jan),manifest(out),manifest(attempt)
assert output_hashes.keys()==attempt_hashes.keys()
changed={k for k in output_hashes if output_hashes[k]!=attempt_hashes[k]}
assert changed=={'receipt.json','2022-07-01/summary.json'},changed
old_summary=j(attempt/'2022-07-01/summary.json')
patched_summary=j(out/'2022-07-01/summary.json')
assert old_summary['days_margin_above_equity']==388
assert patched_summary=={**old_summary,'days_margin_above_equity':463}
receipt=j(out/'receipt.json')
assert sha(prior/'SHA256SUMS')==receipt['parent_manifest_sha256']
assert sha(jan/'SHA256SUMS')==receipt['january_reference_manifest_sha256']
assert sha(line/'reviews/stage037_s19_fixed_one_150k_audit.json')==receipt['parent_audit_sha256']
assert sha(line/'stages/20261104_1751_stage038_s19_fixed_one_150k_halfyear_design.md')==receipt['design_sha256']
assert sha(line/'tools/stage038_s19_fixed_one_150k_halfyear.py')==receipt['entrypoint_sha256']
old=j(prior/'inputs.json')
assert old['initial']==start and old['cash_risk_fraction'] is None and len(old['products'])==19
assert old['inputs_sha256']==receipt['market_sha256']
assert receipt['capital']==start and receipt['cutoff']==target
pins={**old['inputs_sha256'],**old['source_sha256']}
assert all(sha(Path(name))==digest for name,digest in pins.items())
design_starts=[f'{year}-{month}-01' for year in range(2016,2027) for month in ('01','07')]
assert receipt['starts']==design_starts and receipt['completed_runs']==22 and receipt['unknown_runs']==0
assert {p.name for p in out.iterdir() if p.is_dir()}==set(design_starts)
metrics=pd.read_csv(out/'window_metrics.csv',keep_default_na=False).set_index('calendar_start',verify_integrity=True)
assert metrics.index.tolist()==design_starts
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
mapping=pd.read_csv(admitted/'mapping.csv',usecols=['date','continuous_symbol_vt','main_contract_vt'])
mains={(r.date,r.continuous_symbol_vt):r.main_contract_vt for r in mapping.itertuples(index=False)}
calendar=sorted(set(mapping.date))+[target]
assert calendar==sorted(set(calendar))
weekly=defaultdict(list)
all_calendar=sorted(set(calendar).union(pd.read_csv(admitted/'forward_calendar.csv').date))
for day in all_calendar:
    if day>='2014-01-01': weekly[date.fromisoformat(day).isocalendar()[:2]].append(day)
weeks=list(weekly.values())
week_by={day:i for i,w in enumerate(weeks) for day in w}
assert weeks[week_by[target]][-1]=='2026-11-06'
next_day={l:r for l,r in zip(calendar,calendar[1:])}
prior_day={r:l for l,r in zip(calendar,calendar[1:])}
@lru_cache(None)
def guard(epoch):
    m=epoch.split('.')[-1]
    b=f'{m[:4]}-{m[4:]}-01'
    return [d for d in all_calendar if d<b][-5]
@lru_cache(None)
def weekbar(epoch,index):
    if index<0: return None
    data=[market.get((d,epoch)) for d in weeks[index]]
    if None in data: return None
    return data[0].open,max(b.high for b in data),min(b.low for b in data),data[-1].close
def near(a,b,atol=1e-7): np.testing.assert_allclose(np.asarray(a,dtype=float),np.asarray(b,dtype=float),rtol=0,atol=atol)
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
def audit(d0,expected_summary):
    folder=out/d0
    config=j(folder/'inputs.json')
    assert config=={**old,'start':d0}
    expected_days=[d for d in calendar if d>=d0]
    daily=pd.read_csv(folder/'daily.csv')
    assert daily.date.to_list()==expected_days
    assert daily.loc[0,['equity','cash','positions','margin','cumulative_slippage']].to_list()==[start,start,0,0,0]
    if d0[5:7]=='01':
        ref=jan/d0[:4]
        names=('annual','cycles','entry_filter','fills','four_up_blocks','gaps','signals','terminal','week_body_filter')
        for name in names:
            ext='.json' if name=='terminal' else '.csv'
            assert (folder/(name+ext)).read_bytes()==(ref/(name+ext)).read_bytes()
        pd0=pd.read_csv(ref/'daily.csv')
        cols=['date','position_value','positions','margin','cumulative_slippage','cumulative_commission','net_pnl']
        pd.testing.assert_frame_equal(pd0[cols],daily[cols])
        near(pd0.equity-daily.equity,150000)
        near(pd0.cash-daily.cash,150000)
    tape=pd.read_csv(folder/'fills.csv',keep_default_na=False)
    gaps=pd.read_csv(folder/'gaps.csv')
    cycles=pd.read_csv(folder/'cycles.csv',keep_default_na=False)
    terminal=j(folder/'terminal.json')
    signals=pd.read_csv(folder/'signals.csv')
    assert signals.date.min()>=expected_days[0] and tape.signal_day.min()>=expected_days[0] and tape.date.min()>expected_days[0]
    assert not signals.date.eq(target).any()
    sig_index={}
    for sig in signals.itertuples(index=False):
        i=week_by[sig.date]
        assert sig.date==weeks[i][-1]
        current,prev=weekbar(sig.epoch,i),weekbar(sig.epoch,i-1)
        assert (current[3],prev[3])==(sig.close,sig.prior_close)
        key=sig.date,sig.product,sig.action
        assert key not in sig_index
        sig_index[key]=sig
        if sig.action.startswith('open_'):
            direction=1 if sig.action=='open_long' else -1
            older=weekbar(sig.epoch,i-2)
            assert older[3]==sig.older_close
            assert direction*current[3]>direction*prev[3]>direction*older[3]
            assert all(direction*(bar[3]-bar[0])>0 for bar in (current,prev))
            assert sig.stop==current[2 if direction==1 else 1] and sig.contract==mains[sig.date,sig.product]
            hist=[weekbar(sig.epoch,i-k) for k in range(21)]
            if all(hist): assert not all(direction*(current[3]-hist[k][3])<0 for k in (5,10,20))
            if direction==1 and all(hist[:5]):
                assert not all(a[3]>b[3] for a,b in zip(hist[:5],hist[1:5]))
        elif sig.action=='close_long':
            assert current[3]<=prev[2]==sig.stop
        else:
            assert sig.action=='close_short' and current[3]>=prev[1]==sig.stop
    by_date={d:list(f.itertuples(index=False)) for d,f in tape.groupby('date',sort=False)}
    open_observed=pd.read_csv(folder/'opening_funding.csv',keep_default_na=False)
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
                    sig=sig_index[f.signal_day,f.product,'open_long' if f.side==1 else 'open_short']
                    assert (sig.epoch,sig.stop)==(f.epoch,float(f.stop)) and day==next_day[f.signal_day]
                    assert day<guard(f.epoch) and b.high>b.low
                    assert f.cycle not in entries
                    entries[f.cycle]=f
                    if previous and previous.product==f.product:
                        assert previous.reason=='weekly_stop' and previous.signal_day==f.signal_day and previous.side==f.side
                        turns['reversals']+=1
                else:
                    assert previous and previous.product==f.product and previous.cycle==f.cycle and previous.side==-f.side and previous.reason=='roll_close'
                    assert f.signal_day==prior_day[day] and mains[f.signal_day,f.product]==f.contract
                    assert day<guard(f.epoch) and b.high>b.low
                    assert float(f.stop)==weekbar(f.epoch,week_by[day]-1)[2 if f.side==1 else 1]
                    turns['rolls']+=1
                positions[f.product]=[f.epoch,contract,f.side,f.cycle,p]
            else:
                holding=positions.pop(f.product)
                assert (f.epoch,contract,-f.side,f.cycle)==tuple(holding[:4])
                assert f.reason in ('weekly_stop','delivery_guard_exit','roll_close')
                if f.reason=='delivery_guard_exit': assert day>=guard(f.epoch)==f.signal_day
                if f.reason=='roll_close': assert day<guard(f.epoch)
                if f.reason=='weekly_stop':
                    sig=sig_index[f.signal_day,f.product,'close_long' if f.side==-1 else 'close_short']
                    assert (sig.epoch,sig.stop)==(f.epoch,float(f.stop)) and day>=next_day[f.signal_day]
                if f.reason!='roll_close':
                    assert f.cycle not in exits
                    exits[f.cycle]=f
            checkpoint(day,i,f.product,f.reason)
            previous=f
        assert all(day[:7].replace("-","")<=v[0].split(".")[-1] for v in positions.values())
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
    near(pd.Series(pnl).groupby(daily.date.str[:4]).sum(),pd.read_csv(folder/'annual.csv').net_pnl)
    closed=cycles[cycles.exit_day!='']
    wins=closed[closed.net_pnl>0].net_pnl
    losses=-closed[closed.net_pnl<0].net_pnl
    end_equity=calc.equity.iat[-1]
    expected=dict(days=len(daily),initial=start,equity=end_equity,net_pnl=end_equity-start,return_pct=100*(end_equity/start-1),max_dd_pct=100*drawdown.min(),sharpe=ret.mean()/ret.std(ddof=1)*sqrt(252),fills=len(tape),one_price_exits=int(tape.one_price.sum()),rolls=turns['rolls'],closed_cycles=len(closed),wins=len(wins),losses=len(losses),win_rate_pct=100*len(wins)/len(closed),payoff=wins.mean()/losses.mean(),profit_factor=wins.sum()/losses.sum(),slippage=slippage/100,commission=commission/100,net_pnl_double_slippage_same_path=end_equity-start-slippage/100,peak_margin=calc.margin.max(),peak_margin_ratio_pct=100*(calc.margin/calc.equity).max(),days_margin_above_equity=int((calc.margin>calc.equity).sum()),open_positions=len(positions),pending_signals=0,long_pnl=cycles.loc[cycles.direction==1,'net_pnl'].sum(),short_pnl=cycles.loc[cycles.direction==-1,'net_pnl'].sum(),terminal_open_net_pnl=cycles.loc[cycles.exit_day=='','net_pnl'].sum())
    summary=j(folder/'summary.json')
    assert set(summary)==set(expected)|{'start','end','gaps'}
    assert (summary['start'],summary['end'])==(expected_days[0],target)
    assert summary['gaps']==dict(Counter(gaps.reason))
    correct_deficit=expected.pop('days_margin_above_equity')
    published_deficit=summary['days_margin_above_equity']
    legacy_deficit=int((calc.margin/calc.equity>1).sum())
    assert published_deficit==correct_deficit,(d0,correct_deficit,published_deficit,legacy_deficit)
    near(list(expected.values()),[summary[k] for k in expected])
    near([end_equity-start],[cycles.net_pnl.sum()])


    free=calc.equity-calc.margin
    closing_def=set(daily.loc[free.lt(-1e-7),'date'])
    opening_def=set(open_calc.loc[open_calc.free_equity.lt(-1e-7),'date'])
    nonpos=set(daily.loc[calc.equity.le(0),'date']) | set(open_calc.loc[open_calc.equity.le(0),'date'])
    any_def=closing_def|opening_def
    min_free=min(float(free.min()),float(open_calc.free_equity.min()))
    max_pos_close=int(calc.positions.max())
    max_pos_open=int(open_calc.positions.max())
    wm={k:summary[k] for k in ('start','end','days','initial','equity','net_pnl','return_pct','max_dd_pct','sharpe','closed_cycles','fills','slippage')}
    wm.update(minimum_close_equity=float(calc.equity.min()),max_close_margin_pct=float(100*(calc.margin/calc.equity.where(calc.equity>0)).max()),close_deficit_days=len(closing_def),opening_deficit_days=len(opening_def),deficit_days=len(any_def),first_deficit=min(any_def,default=''),max_shortfall=max(0,-min_free),min_free_equity=min_free,nonpositive_equity_days=len(nonpos),opening_snapshots=len(open_calc),max_opening_positions=max_pos_open,max_close_positions=max_pos_close)
    assert set(wm)==set(expected_summary.index)
    for k,v in wm.items():
        if isinstance(v,str): assert expected_summary[k]==v,(d0,k,v,expected_summary[k])
        else: near(expected_summary[k],v)
    def plain(d): return {k:v.item() if isinstance(v,np.generic) else v for k,v in d.items()}
    min_open=plain(open_calc.loc[open_calc.free_equity.idxmin()].to_dict())
    min_close=dict(date=daily.loc[free.idxmin(),'date'],reason='close',equity=float(calc.equity.loc[free.idxmin()]),margin=float(calc.margin.loc[free.idxmin()]),free_equity=float(free.min()))
    return dict(calendar_start=d0,**wm,raw_engine_close_deficit_days=published_deficit,raw_engine_close_deficit_discrepancy=correct_deficit-published_deficit,first_nonpositive=min(nonpos,default=''),last_nonpositive=max(nonpos,default=''),min_equity_any=float(min(calc.equity.min(),open_calc.equity.min())),worst_free_snapshot=min((min_open,min_close),key=lambda x:x['free_equity']),signals=len(signals),reversals=turns['reversals'],rolls=turns['rolls'],total_cycles=len(cycles),late_day_pnl=float(pnl[-1]))

verified=[]
for d0,expected_summary in metrics.iterrows():
    res=audit(d0,expected_summary)
    print(d0,res['equity'],res['deficit_days'],res['nonpositive_equity_days'],res['worst_free_snapshot'],flush=True)
    verified.append({k:v.item() if isinstance(v,np.generic) else v for k,v in res.items()})
totals={key:sum(r[key] for r in verified) for key in ('days','fills','signals','opening_snapshots','closed_cycles','total_cycles')}
stats=dict(attempted=22,valid=len(verified),unknown=0,deficit_runs=sum(r['deficit_days']>0 for r in verified),close_deficit_runs=sum(r['close_deficit_days']>0 for r in verified),opening_deficit_runs=sum(r['opening_deficit_days']>0 for r in verified),nonpositive_runs=sum(r['nonpositive_equity_days']>0 for r in verified),profitable_runs=sum(r['net_pnl']>0 for r in verified),no_deficit_starts=[r['calendar_start'] for r in verified if r['deficit_days']==0],minimum_equity=min(r['min_equity_any'] for r in verified),max_shortfall=max(r['max_shortfall'] for r in verified))
discrepancies={r['calendar_start']:r['raw_engine_close_deficit_discrepancy'] for r in verified if r['raw_engine_close_deficit_discrepancy']}
report=dict(verdict='PASS_WITH_DISCLOSED_LEGACY_SUMMARY_DEFECT' if discrepancies else 'PASS_WITH_LIMITATIONS',legacy_summary_deficit_discrepancies=discrepancies,output_manifest_sha=sha(out/'SHA256SUMS'),output_manifest_entries=len(output_hashes),retained_attempt_manifest_entries=len(attempt_hashes),retained_attempt_changed_files=sorted(changed),parent_manifest_entries=len(parent_hashes),january_manifest_entries=len(jan_hashes),pins=len(pins),totals=totals,aggregate=stats,runs=verified)
Path('/private/tmp/fian_stage038_audit.json').write_text(json.dumps(report,indent=2)+'\n')
print({k:v for k,v in report.items() if k!='runs'},flush=True)
