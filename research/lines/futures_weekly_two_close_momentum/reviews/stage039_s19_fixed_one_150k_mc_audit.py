from pathlib import Path
import csv, hashlib, json
from statistics import NormalDist
from decimal import Decimal
from collections import Counter
import numpy as np
import pandas as pd

line=Path('/Users/mac/Desktop/fian/weekly19-stop-reversal.local/research/lines/futures_weekly_two_close_momentum')
base=line/'outputs/stage033_s19_annual_starts_20261104'
prior=line/'outputs/stage034_s19_monte_carlo_v1'
historical=line/'outputs/stage037_s19_fixed_one_150k_20261104'
semiannual=line/'outputs/stage038_s19_fixed_one_150k_halfyear_20261104'
out=line/'outputs/stage039_s19_fixed_one_150k_mc_v1'
seed=20261104034
horizons=(252,756,1260)
blocks=(63,21)
prefix_days=63
n=20000
start=15000000
years=range(2015,2027)
levels=(1,5,25,50,75,95,99)
def sha(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def j(path): return json.loads(path.read_text())
def manifest(folder):
    listed={}
    for row in (folder/'SHA256SUMS').read_text().splitlines():
        digest,name=row.split(maxsplit=1)
        assert name not in listed and sha(folder/name)==digest,(folder,name)
        listed[name]=digest
    assert set(listed)=={str(f.relative_to(folder)) for f in folder.rglob('*') if f.is_file() and f.name!='SHA256SUMS'}
    return listed
pins=manifest(base)
prior_pins=manifest(prior)
historical_pins=manifest(historical)
semiannual_pins=manifest(semiannual)
verified=manifest(out)
receipt=j(out/'receipt.json')
prior_receipt=j(prior/'receipt.json')
assert sha(base/'SHA256SUMS')==prior_receipt['parent_sha256']
assert sha(prior/'SHA256SUMS')==receipt['parent_mc_manifest_sha256']
assert sha(historical/'SHA256SUMS')==receipt['parent_150k_manifest_sha256']
assert sha(semiannual/'SHA256SUMS')==receipt['semiannual_manifest_sha256']
assert sha(line/'stages/20261104_1759_stage039_s19_fixed_one_150k_mc_design.md')==receipt['design_sha256']
assert sha(line/'tools/stage039_s19_fixed_one_150k_mc.py')==receipt['entrypoint_sha256']
assert sha(line/'tools/stage034_s19_monte_carlo.py')==receipt['sampling_source_sha256']==prior_receipt['source_sha256']
assert sha(prior/'sampling_plan.npz')==receipt['paired_sampling_plan_sha256']
assert (prior_receipt['seed'],prior_receipt['prefix_days'],prior_receipt['initial_cents'],receipt['initial_capital'],receipt['paths_per_group'],receipt['completed_paths'],receipt['unknown_paths'])==(seed,prefix_days,2*start,start//100,n,4*n,0)
assert receipt['horizons']==list(horizons) and receipt['block_days']==list(blocks) and prior_receipt['prefix_years']==list(years)

def cents(v):
    x=Decimal(v)*100
    y=int(x.to_integral_value())
    assert abs(x-y)<Decimal('.0001')
    return y

def parse_ledger(file,capital):
    records=list(csv.DictReader(file.open()))
    dates=[r['date'] for r in records]
    assert dates==sorted(set(dates)) and dates[-1]==receipt['cutoff'] and len(dates)>=63
    assert (cents(records[0]['cash']),int(records[0]['positions']),cents(records[0]['margin']))==(capital,0,0)
    sequence=[]
    prev=capital
    for row in records:
        equity,net,margin=(cents(row[k]) for k in ('equity','net_pnl','margin'))
        assert margin>=0 and equity-prev==net and equity==cents(row['cash'])+cents(row['position_value'])
        sequence.append((net,margin))
        prev=equity
    return dates,np.array(sequence,dtype='int64')
old_prefixes=[]
for year in years:
    path=base/str(year)/'daily.csv'
    assert sha(path)==pins[f'{year}/daily.csv']==prior_receipt['source_daily_sha256'][str(year)]
    dates,seq=parse_ledger(path,2*start)
    assert dates[0].startswith(str(year))
    old_prefixes.append(seq[:prefix_days])
    if year==2015:
        full_dates,full_seq=dates,seq
dates150,seq150=parse_ledger(historical/'daily.csv',start)
assert full_dates==dates150 and np.array_equal(full_seq,seq150)
library=seq150[prefix_days:]
mature_range=(dates150[prefix_days],dates150[-1])
assert len(library)==prior_receipt['mature_days']==2812
old_labels=list(years)
new_labels=[f'{year}-{month}-01' for year in range(2016,2027) for month in ('01','07')]
assert new_labels==j(semiannual/'receipt.json')['starts'] and set(new_labels)==set(receipt['semiannual_daily_sha256'])
new_prefixes=[]
for s in new_labels:
    file=semiannual/s/'daily.csv'
    assert sha(file)==semiannual_pins[f'{s}/daily.csv']==receipt['semiannual_daily_sha256'][s]
    dates,seq=parse_ledger(file,start)
    assert dates==[d for d in dates150 if d>=s]
    new_prefixes.append(seq[:prefix_days])
    if s[5:7]=='01':
        assert np.array_equal(seq[:prefix_days],old_prefixes[int(s[:4])-2015])
old_pre,new_pre=np.array(old_prefixes),np.array(new_prefixes)
assert old_pre.shape==(12,63,2) and new_pre.shape==(22,63,2)
assert np.array_equal(old_pre[1:],new_pre[::2])
with np.load(prior/'sampling_plan.npz',allow_pickle=False) as f:
    assert set(f.files)=={'prefix_index','block_21_start','block_63_start'}
    plan={k:f[k] for k in f.files}
new_plan=np.load(out/'semiannual_prefix_indices.npy',allow_pickle=False)
def redraw_prefix(k):
    gen=np.random.Generator(np.random.PCG64(seed))
    return gen.integers(k,size=n,dtype='int32')
assert np.array_equal(plan['prefix_index'],redraw_prefix(12))
assert np.array_equal(new_plan,redraw_prefix(22))
assert np.bincount(plan['prefix_index']).min()>0 and np.bincount(new_plan).min()>0
series={
    'paired_january':(old_pre,old_labels,plan['prefix_index']),
    'semiannual':(new_pre,new_labels,new_plan),
}

def indexed_q(v,p):
    arr=np.sort(np.array(v),axis=0)
    k=(len(arr)-1)*p/100
    lo=int(k); hi=int(np.ceil(k))
    return arr[lo]+(k-lo)*(arr[hi]-arr[lo])

def wilson(k,m):
    z=NormalDist().inv_cdf(.975)
    center=(k+z*z/2)/(m+z*z)
    half=z*np.sqrt(k*(m-k)/m+z*z/4)/(m+z*z)
    return (max(0,center-half),min(1,center+half))

def eq_num(actual,expected,atol=1e-7):
    np.testing.assert_allclose(np.asarray(actual,dtype=float),np.asarray(expected,dtype=float),rtol=0,atol=atol)

frequencies=pd.read_csv(out/'event_frequencies.csv')
quantiles=pd.read_csv(out/'quantiles.csv')
fan_ref=pd.read_csv(out/'equity_fan.csv')
assert len(frequencies)==72 and len(quantiles)==60 and len(fan_ref)==244
checks=[]
path_groups={}
for cohort,(pre,labels,prefix_draw) in series.items():
    for block in blocks:
        complete,rem=divmod(horizons[-1]-prefix_days,block)
        draws=complete+bool(rem)
        highest=len(library)-block
        rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,block])))
        ids=plan[f'block_{block}_start']
        assert ids.shape==(n,draws) and ids.dtype==np.int32
        assert np.array_equal(ids,rng.integers(highest+1,size=(n,draws),dtype='int32'))
        assert ids.min()==0 and ids.max()==highest
        tape=pd.read_csv(out/f'{cohort}_paths_b{block}.csv')
        assert len(tape)==3*n and set(tape.block_days)=={block} and set(tape.horizon_days)==set(horizons)
        by_h={h:tape[tape.horizon_days==h].set_index('path_id',verify_integrity=True) for h in horizons}
        path_groups[cohort,block]=by_h
        assert all(list(frame.index)==list(range(1,n+1)) and frame.notna().all().all() for frame in by_h.values())
        sampled_days=np.arange(horizons[-1]-prefix_days)
        block_number=sampled_days//block
        day_in_block=sampled_days%block
        fan_times=np.arange(0,horizons[-1]+1,21)
        fan_points=np.full((n,len(fan_times)),start,dtype=np.int64)
        first_path=None
        for first in range(0,n,383):
            last=min(first+383,n)
            rows=np.arange(first,last)
            mature_index=ids[rows[:,None],block_number]+day_in_block
            path_indices=prefix_draw[rows]
            young=pre[path_indices]
            older=library[mature_index]
            increments=np.column_stack([young[:,:,0],older[:,:,0]])
            margin=np.column_stack([young[:,:,1],older[:,:,1]])
            cumulative=np.add.accumulate(increments,axis=1)
            equity=start+cumulative
            peak=np.maximum.accumulate(np.column_stack([np.full(len(rows),start),equity]),axis=1)[:,1:]
            dd_numerator=peak-equity
            dd_fraction=dd_numerator/peak
            needed=margin-cumulative
            breaches=needed>start
            fan_points[rows,1:]=equity[:,fan_times[1:]-1]
            for h in horizons:
                seg=np.s_[:,:h]
                observed=by_h[h].iloc[first:last]
                assert np.array_equal(observed.prefix_start,np.array(labels)[path_indices])
                needed_cap=np.maximum(0,np.max(needed[seg],axis=1))
                worst_shortfall=np.maximum(0,needed_cap-start)
                failure_count=breaches[seg].sum(axis=1)
                first_failure=np.argmax(np.column_stack([breaches[seg],np.full(len(rows),True)]),axis=1)+1
                first_failure[first_failure==h+1]=0
                expected=dict(
                    terminal_equity=equity[:,h-1]/100,
                    max_drawdown_pct=100*np.max(dd_fraction[seg],axis=1),
                    initial_capital_required=needed_cap/100,
                    max_margin_shortfall=worst_shortfall/100,
                    first_breach_day=first_failure,
                    margin_breach_days=failure_count,
                    terminal_loss=(equity[:,h-1]<start),
                    margin_breach=(failure_count>0),
                    equity_nonpositive=np.min(equity[seg],axis=1)<=0,
                )
                for threshold in (30,40,50):
                    expected[f'dd{threshold}']=np.any((100*dd_numerator[seg])>=threshold*peak[seg],axis=1)
                for key,value in expected.items():
                    if value.dtype==bool or key in ('first_breach_day','margin_breach_days'):
                        assert np.array_equal(observed[key].to_numpy(),value),(block,h,key,first)
                    else:
                        eq_num(observed[key],value)
        fan=fan_ref[(fan_ref.block_days==block)&(fan_ref.cohort==cohort)]
        assert fan.trading_days.to_list()==fan_times.tolist()
        for pct in levels:
            eq_num(fan[f'p{pct:02}'],indexed_q(fan_points,pct)/100)
        for h,frame in by_h.items():
            f=frequencies[(frequencies.block_days==block)&(frequencies.horizon_days==h)&(frequencies.cohort==cohort)].set_index('event',verify_integrity=True)
            assert set(f.index)=={'terminal_loss','margin_breach','equity_nonpositive','dd30','dd40','dd50'}
            events={}
            for label,r in f.iterrows():
                k=int(frame[label].sum())
                assert (k,n,n,0)==(r['count'],r['valid'],r['attempted'],r['unknown'])
                expected=(k/n,*wilson(k,n))
                eq_num([r.frequency,r.wilson_lo,r.wilson_hi],expected,atol=1e-12)
                events[label]={'count':k,'rate':expected[0],'wilson95':expected[1:]}
            q=quantiles[(quantiles.block_days==block)&(quantiles.horizon_days==h)&(quantiles.cohort==cohort)].set_index('measure',verify_integrity=True)
            values=dict(terminal_equity=frame.terminal_equity,max_drawdown_pct=frame.max_drawdown_pct,initial_capital_required=frame.initial_capital_required,max_margin_shortfall_given_breach=frame.loc[frame.margin_breach,'max_margin_shortfall'],first_breach_day_given_breach=frame.loc[frame.margin_breach,'first_breach_day'])
            assert set(q.index)==set(values)
            qrec={}
            for measure,sample in values.items():
                assert q.at[measure,'n']==len(sample)
                qs={f'p{pc:02}':float(indexed_q(sample,pc)) for pc in levels}
                eq_num(q.loc[measure,list(qs)],list(qs.values()))
                qrec[measure]=qs
            coverage={}
            for pct in (95,99):
                sample=values['initial_capital_required']
                cutoff=qrec['initial_capital_required'][f'p{pct:02}']
                covered=int((sample<=cutoff+1e-8).sum())
                assert covered>=round(n*pct/100),(block,h,pct,covered)
                rounded_yuan=int(np.ceil(cutoff-1e-8))
                conservative=int((sample<=rounded_yuan).sum())
                assert conservative>=covered
                coverage[f'p{pct:02}']={'required_cny':cutoff,'covered':covered,'coverage':covered/n,'upward_round_whole_yuan':rounded_yuan,'rounded_yuan_covered':conservative}
            checks.append(dict(cohort=cohort,block=block,horizon=h,events=events,quantiles=qrec,coverage=coverage))
            print(cohort,block,h,{k:v['count'] for k,v in events.items()},coverage,flush=True)
pair_checks=[]
for block in blocks:
    parent_paths=pd.read_csv(prior/f'paths_b{block}.csv')
    for h in horizons:
        x=parent_paths[parent_paths.horizon_days==h].set_index('path_id',verify_integrity=True)
        y=path_groups['paired_january',block][h]
        assert x.index.equals(y.index) and x.prefix_year.equals(y.prefix_start)
        assert np.array_equal(x.terminal_equity-y.terminal_equity,np.full(n,150000))
        assert x.initial_capital_required.equals(y.initial_capital_required)
        assert x.terminal_loss.equals(y.terminal_loss)
        for label in ('margin_breach','equity_nonpositive','dd30','dd40','dd50'):
            assert not (x[label] & ~y[label]).any()
        assert (y.max_drawdown_pct>=x.max_drawdown_pct-1e-10).all()
        assert (y.max_margin_shortfall>=x.max_margin_shortfall).all()
        assert (y.margin_breach_days>=x.margin_breach_days).all()
        assert (y.loc[x.margin_breach,'first_breach_day']<=x.loc[x.margin_breach,'first_breach_day']).all()
        c=dict(block=block,horizon=h)
        c['added_paths_due_to_lower_capital']={key:int((~x[key]&y[key]).sum()) for key in ('margin_breach','equity_nonpositive','dd30','dd40','dd50')}
        pair_checks.append(c)
        print('paired_check',c,flush=True)
result=dict(verdict='PASS_WITH_LIMITATIONS',fixed_300k_ledger_manifest_entries=len(pins),stage034_manifest_entries=len(prior_pins),stage037_manifest_entries=len(historical_pins),stage038_manifest_entries=len(semiannual_pins),output_manifest_entries=len(verified),output_manifest_sha=sha(out/'SHA256SUMS'),seed=seed,source_mature_range=mature_range,source_mature_days=len(library),attempted_paths=4*n,unknown_paths=0,annual_semiannual_prefix_counts={label:int(v) for label,v in zip(new_labels,np.bincount(new_plan))},path_horizon_rows=4*n*len(horizons),capital_paired_horizon_rows=2*n*len(horizons),fan_rows=len(fan_ref),checks=checks,paired_checks=pair_checks)
Path('/private/tmp/fian_stage039_audit.json').write_text(json.dumps(result,indent=2)+'\n')
print({k:v for k,v in result.items() if k not in ('checks','paired_checks')},flush=True)
