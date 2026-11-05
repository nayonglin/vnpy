from pathlib import Path
import hashlib,json
from collections import defaultdict,Counter
from functools import lru_cache
from datetime import date
from math import sqrt
import numpy as np
import pandas as pd

root=Path('/Users/mac/Desktop/fian/weekly19-stop-reversal.local/research/lines')
p=root/'futures_weekly_two_close_momentum'
base=p/'outputs/stage025_delivery_guard/S19_guard_2015_20261103_attempt001'
new=p/'outputs/stage033_s19_annual_starts_20261104'
fallback=p/'outputs/stage033_s19_annual_starts_20261103'
tail=p/'outputs/stage033_s19_data/attempt002'
frozen=root/'futures_weekly19_stop_reversal/outputs'
data_root=frozen/'stage002_data/data_approved'
old='2026-11-03'
end='2026-11-04'
def j(path): return json.loads(path.read_text())
def sha(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def verify_manifest(folder,expected=None):
    present=set()
    if expected: assert sha(folder/'SHA256SUMS')==expected
    for row in (folder/'SHA256SUMS').read_text().splitlines():
        digest,name=row.split(maxsplit=1)
        assert sha(folder/name)==digest,(folder,name)
        present.add(name)
    assert {str(x.relative_to(folder)) for x in folder.rglob('*') if x.is_file() and x.name!='SHA256SUMS'}==present
    return len(present)
receipt=j(new/'receipt.json')
hash_counts={x.name:verify_manifest(x,receipt['baseline_manifest_sha256'] if x==base else None) for x in (base,new,fallback)}
assert receipt['cutoff']==end and receipt['years']==list(range(2015,2027))
assert receipt['design_sha256']==sha(p/'stages/20261104_1651_stage033_s19_annual_starts_design.md')
assert receipt['entrypoint_sha256']==sha(p/'tools/stage033_s19_annual_starts.py')
pins={}
def verify_pins(data):
    for path,digest in data.items():
        if path not in pins: pins[path]=sha(Path(path))
        assert pins[path]==digest,(path,digest)
verify_pins(receipt['source_hashes'])
for path in base.iterdir():
    if path.is_file() and path.name not in ('SHA256SUMS','inputs.json'):
        assert path.read_bytes()==(new/'reproduction_20261103'/path.name).read_bytes()
source=j(base/'inputs.json')
source.pop('source_sha256')
source.pop('inputs_sha256')
mapping=pd.read_csv(data_root/'mapping.csv',usecols=['date','continuous_symbol_vt','main_contract_vt'])
mains={(x.date,x.continuous_symbol_vt):x.main_contract_vt for x in mapping.itertuples(index=False)}
all_days=sorted(set(mapping.date).union(pd.read_csv(data_root/'forward_calendar.csv').date))
old_days=sorted(set(mapping.date))
days=old_days+[end]
pos={k:i for i,k in enumerate(days)}
assert days==sorted(set(days))
weekly=defaultdict(list)
for day in all_days:
    if day<'2014-01-01': continue
    weekly[date.fromisoformat(day).isocalendar()[:2]].append(day)
weeks=list(weekly.values())
week_pos={day:i for i,w in enumerate(weeks) for day in w}
assert week_pos[end]==week_pos[old] and weeks[week_pos[end]][-1]=='2026-11-06'
months=defaultdict(list)
for day in all_days: months[day[:7]].append(day)
def guard(delivery):
    m=f'{delivery[:4]}-{delivery[4:]}'
    prior_days=[d for d in all_days if d[:7]<m]
    return prior_days[-5]
epochs=pd.read_csv(data_root/'physical_epochs.csv',dtype=str)
epoch_by_vt=dict(zip(epochs[epochs.contract_yyyymm.ge('202611')].vt_symbol,epochs[epochs.contract_yyyymm.ge('202611')].contract_epoch_id))
prices=pd.read_csv(data_root/'physical_epoch_daily.csv',usecols=['date','vt_symbol','contract_epoch_id','open','high','low','close'])
raw=pd.read_csv(tail/'provider/raw_daily.csv')
raw=raw[(raw.date==end)&(raw.volume>0)].copy()
raw['contract_epoch_id']=raw.vt_symbol.map(epoch_by_vt)
prices=pd.concat([prices,raw[prices.columns]],ignore_index=True)
data={(r.date,r.contract_epoch_id):r for r in prices.itertuples(index=False)}
assert len(data)==len(prices)
spec=j(frozen/'stage003_D_20261103_attempt01/contract_settings.json')
@lru_cache(None)
def wb(epoch,index):
    if index<0: return None
    bars=[data.get((day,epoch)) for day in weeks[index]]
    if None in bars: return None
    return (bars[0].open,max(b.high for b in bars),min(b.low for b in bars),bars[-1].close)
window=pd.read_csv(new/'window_metrics.csv',index_col='start_year')
fallback_window=pd.read_csv(fallback/'window_metrics.csv',index_col='start_year')
assert list(window.index)==list(range(2015,2027))
results=[]
for year,row in window.iterrows():
    f=new/str(year)
    prior=fallback/str(year)
    conf=j(f/'inputs.json')
    verify_pins(conf.pop('inputs_sha256'))
    verify_pins(conf.pop('source_sha256'))
    assert conf=={**source,'start':f'{year}-01-01','end':end}
    d=pd.read_csv(f/'daily.csv')
    tape=pd.read_csv(f/'fills.csv',keep_default_na=False)
    sig=pd.read_csv(f/'signals.csv')
    cycle=pd.read_csv(f/'cycles.csv',keep_default_na=False)
    gaps=pd.read_csv(f/'gaps.csv')
    term=j(f/'terminal.json')
    initial=300000
    expected_days=[day for day in days if day>=f'{year}-01-01']
    assert d.date.to_list()==expected_days
    assert d.loc[0,['cash','equity','margin','positions','cumulative_slippage','cumulative_commission']].tolist()==[initial,initial,0,0,0,0]
    assert tape.date.min()>d.date.min() and sig.date.min()>=d.date.min()
    assert not tape.date.eq(end).any() and not sig.date.eq(end).any() and not gaps.date.eq(end).any()
    assert not term['pending'] and not term['pending_reversals']
    for name in ('fills','signals','gaps','entry_filter','four_up_blocks','week_body_filter'):
        assert (f/(name+'.csv')).read_bytes()==(prior/(name+'.csv')).read_bytes(),(year,name)
    pd.testing.assert_frame_equal(d.iloc[:-1],pd.read_csv(prior/'daily.csv'))
    for name in ('cycles',):
        r=cycle[cycle.exit_day!=''].reset_index(drop=True)
        o=pd.read_csv(prior/(name+'.csv'),keep_default_na=False)
        pd.testing.assert_frame_equal(r,o[o.exit_day!=''].reset_index(drop=True))
    prior_term=j(prior/'terminal.json')
    assert set(term['positions'])==set(prior_term['positions'])
    for product in term['positions']:
        p1,p2=(dict(x['positions'][product]) for x in (term,prior_term))
        p1.pop('mark'); p2.pop('mark')
        assert p1==p2
    sig_index={}
    for s in sig.itertuples(index=False):
        i=week_pos[s.date]
        assert s.date==weeks[i][-1] and s.date<end
        current,previous=wb(s.epoch,i),wb(s.epoch,i-1)
        assert (current[3],previous[3])==(s.close,s.prior_close)
        if s.action.startswith('open_'):
            older=wb(s.epoch,i-2)
            assert older[3]==s.older_close
            sign=1 if s.action=='open_long' else -1
            assert sign*current[3]>sign*previous[3]>sign*older[3]
            assert all(sign*(w[3]-w[0])>0 for w in (current,previous))
            assert s.contract==mains[s.date,s.product] and s.stop==current[2 if sign>0 else 1]
            earlier=[wb(s.epoch,i-k) for k in range(21)]
            if all(earlier):
                assert not all(sign*(current[3]-earlier[k][3])<0 for k in (5,10,20))
            if sign==1 and all(earlier[:5]):
                assert not all(l[3]>r[3] for l,r in zip(earlier[:5],earlier[1:5]))
        elif s.action=='close_long':
            assert current[3]<=previous[2] and s.stop==previous[2]
        else:
            assert s.action=='close_short' and current[3]>=previous[1] and s.stop==previous[1]
        sig_index[s.date,s.product,s.action]=s
    by_date=dict(list(tape.groupby('date',sort=False)))
    cash=initial; slip=commission=0
    positions={}
    per_cycle=defaultdict(float)
    cycles_open={}
    cycles_close={}
    rows=[]
    for day in d.date:
        roll_close={}
        for x in (by_date[day].itertuples(index=False) if day in by_date else ()):
            market=data[day,x.epoch]
            assert x.volume==1 and x.contract==market.vt_symbol and x.price==market.open
            assert x.one_price==(market.high==market.low)
            assert x.size==spec['sizes'][x.contract]
            assert x.slippage==spec['slippages'][x.contract]*x.size and x.commission==spec['rates'][x.contract]*x.size*x.price
            flow=-x.side*x.price*x.size-x.slippage-x.commission
            cash+=flow; slip+=x.slippage; commission+=x.commission; per_cycle[x.cycle]+=flow
            if x.reason=='entry':
                s=sig_index[x.signal_day,x.product,'open_long' if x.side>0 else 'open_short']
                assert (s.epoch,s.stop)==(x.epoch,float(x.stop)) and pos[day]==pos[x.signal_day]+1
                assert day<guard(x.epoch.split('.')[-1]) and market.high>market.low
                assert x.product not in positions and x.cycle not in cycles_open
                cycles_open[x.cycle]=x
                positions[x.product]=[x.epoch,x.contract,x.side,x.size,x.price,x.cycle]
            elif x.reason=='roll_open':
                y=roll_close.pop(x.product)
                assert (x.cycle,x.side)==(y.cycle,-y.side) and x.product not in positions
                assert x.signal_day==days[pos[day]-1] and x.contract==mains[x.signal_day,x.product]
                assert day<guard(x.epoch.split('.')[-1]) and market.high>market.low
                assert x.stop!='' and float(x.stop)==wb(x.epoch,week_pos[day]-1)[2 if x.side==1 else 1]
                positions[x.product]=[x.epoch,x.contract,x.side,x.size,x.price,x.cycle]
            else:
                y=positions.pop(x.product)
                assert (x.epoch,x.contract,-x.side,x.size,x.cycle)==(*y[:4],y[-1])
                if x.reason=='roll_close':
                    assert day<guard(x.epoch.split('.')[-1])
                    roll_close[x.product]=x
                elif x.reason=='weekly_stop':
                    s=sig_index[x.signal_day,x.product,'close_long' if x.side<0 else 'close_short']
                    assert (s.epoch,s.stop)==(x.epoch,float(x.stop)) and pos[day]>=pos[x.signal_day]+1
                    cycles_close[x.cycle]=x
                else:
                    assert x.reason=='delivery_guard_exit' and day>=guard(x.epoch.split('.')[-1])==x.signal_day
                    cycles_close[x.cycle]=x
        assert not roll_close
        mark=margin=0
        for product,v in positions.items():
            epoch,symbol,side,size,last,cy=v
            market=data.get((day,epoch))
            v[4]=close=market.close if market is not None else last
            assert day[:7].replace('-','')<=epoch.split('.')[-1]
            mark+=side*size*close
            margin+=size*close*spec['margin_ratios'][symbol]
        rows.append((cash+mark,cash,mark,margin,len(positions),slip,commission))
    np.testing.assert_allclose(rows,d[['equity','cash','position_value','margin','positions','cumulative_slippage','cumulative_commission']],atol=1e-7,rtol=0)
    terms={v[-1]:v[2]*v[3]*v[4] for v in positions.values()}
    assert set(terms)==set(cycle[cycle.exit_day==''].cycle)
    assert len(terms)==len(term['positions'])
    for product,v in positions.items():
        t=term['positions'][product]
        assert (v[0],v[1],v[2],v[4],v[5])==(t['epoch'],t['symbol'],t['side'],t['mark'],t['cycle'])
    for cy in cycle.itertuples(index=False):
        first,last=cycles_open[cy.cycle],cycles_close.get(cy.cycle)
        assert (cy.product,cy.direction,cy.entry_day,cy.exit_day)==(first.product,first.side,first.date,last.date if last else '')
        np.testing.assert_allclose([cy.cash_flow,cy.terminal_mark,cy.net_pnl],[per_cycle[cy.cycle],terms.get(cy.cycle,0),per_cycle[cy.cycle]+terms.get(cy.cycle,0)],atol=1e-7,rtol=0)
    values=np.array(rows)
    eq=values[:,0]
    margins=values[:,3]
    assert abs(cycle.net_pnl.sum()+initial-eq[-1])<1e-7
    assert abs((d.equity.iat[-1]-d.equity.iat[-2])-(d.position_value.iat[-1]-d.position_value.iat[-2]))<1e-7
    rets=eq/np.r_[initial,eq[:-1]]-1
    pnl_day=np.diff(np.r_[initial,eq])
    dd=eq/np.maximum.accumulate(np.r_[initial,eq])[1:]-1
    np.testing.assert_allclose(pnl_day,d.net_pnl,atol=1e-7,rtol=0)
    np.testing.assert_allclose(dd,d.drawdown,atol=1e-12,rtol=0)
    np.testing.assert_allclose(margins/eq,d.margin_ratio,atol=1e-12,rtol=0)
    ann=pd.DataFrame(dict(year=d.date.str[:4],net_pnl=pnl_day)).groupby('year').net_pnl.sum()
    np.testing.assert_allclose(ann,pd.read_csv(f/'annual.csv').net_pnl,atol=1e-7,rtol=0)
    closed=cycle[cycle.exit_day!='']
    pnl=eq[-1]-initial
    calc=dict(start=d.date.iat[0],end=d.date.iat[-1],days=len(d),initial=initial,equity=eq[-1],net_pnl=pnl,return_pct=100*pnl/initial,max_dd_pct=100*dd.min(),sharpe=rets.mean()/rets.std(ddof=1)*sqrt(252),closed_cycles=len(closed),wins=int((closed.net_pnl>0).sum()),losses=int((closed.net_pnl<0).sum()),win_rate_pct=100*(closed.net_pnl>0).sum()/len(closed),fills=len(tape),slippage=slip,commission=commission,peak_margin=margins.max(),peak_margin_ratio_pct=100*(margins/eq).max(),days_margin_above_equity=int((margins>eq).sum()),open_positions=len(positions),terminal_open_net_pnl=cycle[cycle.exit_day==''].net_pnl.sum(),net_pnl_double_slippage_same_path=pnl-slip,cagr_pct=100*((eq[-1]/initial)**(252/len(d))-1),peak_positions=int(values[:,4].max()),min_free_equity=(eq-margins).min())
    summary=j(f/'summary.json')
    assert summary['gaps']==dict(Counter(gaps.reason))
    for name,val in calc.items():
        for expected in (row[name],summary.get(name,row[name])):
            assert val==expected if isinstance(val,str) else abs(val-expected)<1e-7,(year,name,val,expected)
    assert abs(float(fallback_window.at[year,'equity'])-eq[-2])<1e-7
    rec={'year':year,'signals':len(sig),'delta_tail':eq[-1]-eq[-2],'first_entry':tape.date.min(),'open_cycles':len(cycle),**calc}
    results.append({k:(v.item() if isinstance(v,np.generic) else v) for k,v in rec.items()})
    print(year,calc['days'],calc['equity'],calc['days_margin_above_equity'],calc['min_free_equity'],len(sig),rec['delta_tail'],flush=True)
audit=dict(verdict='PASS_WITH_LIMITATIONS',manifests=hash_counts,pins=len(pins),final_manifest_sha=sha(new/'SHA256SUMS'),days=sum(r['days'] for r in results),fills=sum(r['fills'] for r in results),signals=sum(r['signals'] for r in results),results=results)
Path('/private/tmp/fian_stage033_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
print({k:v for k,v in audit.items() if k!='results'},flush=True)
