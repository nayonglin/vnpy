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
sizing=line/'outputs/stage035_s19_half_pct_20261104'
out=line/'outputs/stage036_s19_paired_mc_v1'
seed=20261104034
horizons=(252,756,1260)
blocks=(63,21)
prefix_days=63
n=20000
start=30000000
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
sizing_pins=manifest(sizing)
verified=manifest(out)
receipt=j(out/'receipt.json')
prior_receipt=j(prior/'receipt.json')
assert sha(base/'SHA256SUMS')==prior_receipt['parent_sha256']
assert sha(prior/'SHA256SUMS')==receipt['parent_mc_manifest_sha256']
assert sha(sizing/'SHA256SUMS')==receipt['parent_sizing_manifest_sha256']
assert sha(line/'stages/20261104_1724_stage036_s19_paired_mc_design.md')==receipt['design_sha256']
assert sha(line/'tools/stage036_s19_paired_mc.py')==receipt['entrypoint_sha256']
assert sha(line/'tools/stage034_s19_monte_carlo.py')==receipt['sampling_source_sha256']==prior_receipt['source_sha256']
assert sha(prior/'sampling_plan.npz')==receipt['paired_sampling_plan_sha256']
assert (prior_receipt['seed'],prior_receipt['prefix_days'],prior_receipt['initial_cents'],receipt['paths_per_block'],receipt['attempted_pairs'],receipt['unknown_pairs'])==(seed,prefix_days,start,n,2*n,0)
assert receipt['horizons']==list(horizons) and receipt['block_days']==list(blocks) and prior_receipt['prefix_years']==list(years)

def cents(v):
    x=Decimal(v)*100
    y=int(x.to_integral_value())
    assert abs(x-y)<Decimal('.0001')
    return y

series={}
for arm in ('fixed_one','cash_risk_0_5pct'):
    prefixes=[]
    for year in years:
        fixed_path=base/str(year)/'daily.csv'
        control_dates=[r['date'] for r in csv.DictReader(fixed_path.open())]
        if arm=='fixed_one':
            file=fixed_path
            assert sha(file)==pins[f'{year}/daily.csv']==prior_receipt['source_daily_sha256'][str(year)]
        else:
            file=(sizing/arm/'daily.csv') if year==2015 else (out/'cold_starts'/str(year)/'daily.csv')
            assert sha(file)==receipt['dynamic_daily_sha256'][str(year)]
        records=list(csv.DictReader(file.open()))
        dates=[r['date'] for r in records]
        assert dates==control_dates[:len(records)] and dates==sorted(set(dates))
        if arm=='cash_risk_0_5pct' and year!=2015: assert len(dates)==63
        else: assert dates[-1]==receipt['cutoff']
        assert (cents(records[0]['cash']),int(records[0]['positions']),cents(records[0]['margin']))==(start,0,0)
        sequence=[]
        prev=start
        for row in records:
            equity,net,margin=(cents(row[k]) for k in ('equity','net_pnl','margin'))
            assert margin>=0 and equity-prev==net and equity==cents(row['cash'])+cents(row['position_value'])
            sequence.append((net,margin))
            prev=equity
        prefixes.append(sequence[:prefix_days])
        if year==2015:
            mature=sequence[prefix_days:]
            mature_range=(dates[prefix_days],dates[-1])
    assert len(mature)==prior_receipt['mature_days']==2812
    pre=np.array(prefixes,dtype=np.int64)
    library=np.array(mature,dtype=np.int64)
    assert pre.shape==(12,63,2)
    series[arm]=(pre,library)

with np.load(prior/'sampling_plan.npz',allow_pickle=False) as f:
    assert set(f.files)=={'prefix_index','block_21_start','block_63_start'}
    plan={k:f[k] for k in f.files}
prefix_seed=np.random.Generator(np.random.PCG64(seed))
prefix_draw=prefix_seed.integers(len(years),size=n,dtype='int32')
assert np.array_equal(plan['prefix_index'],prefix_draw)
assert np.bincount(prefix_draw).min()>0

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
for arm,(pre,library) in series.items():
    for block in blocks:
        complete,rem=divmod(horizons[-1]-prefix_days,block)
        draws=complete+bool(rem)
        highest=len(mature)-block
        rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,block])))
        ids=plan[f'block_{block}_start']
        assert ids.shape==(n,draws) and ids.dtype==np.int32
        assert np.array_equal(ids,rng.integers(highest+1,size=(n,draws),dtype='int32'))
        assert ids.min()==0 and ids.max()==highest
        tape=pd.read_csv(prior/f'paths_b{block}.csv' if arm=='fixed_one' else out/f'cash_paths_b{block}.csv')
        assert len(tape)==3*n and set(tape.block_days)=={block} and set(tape.horizon_days)==set(horizons)
        by_h={h:tape[tape.horizon_days==h].set_index('path_id',verify_integrity=True) for h in horizons}
        path_groups[arm,block]=by_h
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
                assert np.array_equal(observed.prefix_year,np.array(list(years))[path_indices])
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
        fan=fan_ref[(fan_ref.block_days==block)&(fan_ref.arm==arm)]
        assert fan.trading_days.to_list()==fan_times.tolist()
        for pct in levels:
            eq_num(fan[f'p{pct:02}'],indexed_q(fan_points,pct)/100)
        for h,frame in by_h.items():
            f=frequencies[(frequencies.block_days==block)&(frequencies.horizon_days==h)&(frequencies.arm==arm)].set_index('event',verify_integrity=True)
            assert set(f.index)=={'terminal_loss','margin_breach','equity_nonpositive','dd30','dd40','dd50'}
            events={}
            for label,r in f.iterrows():
                k=int(frame[label].sum())
                assert (k,n,n,0)==(r['count'],r['valid'],r['attempted'],r['unknown'])
                expected=(k/n,*wilson(k,n))
                eq_num([r.frequency,r.wilson_lo,r.wilson_hi],expected,atol=1e-12)
                events[label]={'count':k,'rate':expected[0],'wilson95':expected[1:]}
            q=quantiles[(quantiles.block_days==block)&(quantiles.horizon_days==h)&(quantiles.arm==arm)].set_index('measure',verify_integrity=True)
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
            checks.append(dict(arm=arm,block=block,horizon=h,events=events,quantiles=qrec,coverage=coverage))
            print(arm,block,h,{k:v['count'] for k,v in events.items()},coverage,flush=True)
paired=pd.read_csv(out/'paired_frequencies.csv')
assert len(paired)==72
pair_checks=[]
for block in blocks:
    for h in horizons:
        x=path_groups['fixed_one',block][h]
        y=path_groups['cash_risk_0_5pct',block][h]
        assert x.prefix_year.equals(y.prefix_year)
        ef=x.terminal_equity>y.terminal_equity
        ec=y.terminal_equity>x.terminal_equity
        df=x.max_drawdown_pct<y.max_drawdown_pct-1e-10
        dc=y.max_drawdown_pct<x.max_drawdown_pct-1e-10
        assert not (ef & ec).any() and not (df & dc).any()
        mf=x.margin_breach
        mc=y.margin_breach
        flags={
            'fixed_higher_equity':ef,'cash_higher_equity':ec,'equity_tie':~(ef|ec),
            'fixed_lower_drawdown':df,'cash_lower_drawdown':dc,'drawdown_tie':~(df|dc),
            'fixed_higher_equity_and_lower_drawdown':ef&df,'cash_higher_equity_and_lower_drawdown':ec&dc,
            'fixed_only_margin_breach':mf&~mc,'cash_only_margin_breach':mc&~mf,
            'both_margin_breach':mf&mc,'neither_margin_breach':~mf&~mc,
        }
        found=paired[(paired.block_days==block)&(paired.horizon_days==h)].set_index('measure',verify_integrity=True)
        assert set(found.index)==set(flags)
        result={}
        for name,value in flags.items():
            k=int(value.sum())
            observed=found.loc[name]
            assert (observed['count'],observed.pairs)==(k,n)
            expected=(k/n,*wilson(k,n))
            eq_num([observed.frequency,observed.wilson_lo,observed.wilson_hi],expected,atol=1e-12)
            result[name]={'count':k,'rate':expected[0],'wilson95':expected[1:]}
        pair_checks.append(dict(block=block,horizon=h,measures=result))
        print('paired',block,h,{k:v['count'] for k,v in result.items()},flush=True)
result=dict(verdict='PASS_WITH_LIMITATIONS',fixed_ledger_manifest_entries=len(pins),stage034_manifest_entries=len(prior_pins),stage035_manifest_entries=len(sizing_pins),output_manifest_entries=len(verified),output_manifest_sha=sha(out/'SHA256SUMS'),seed=seed,source_mature_range=mature_range,source_mature_days=len(mature),attempted_pairs=2*n,unknown_pairs=0,path_pair_horizon_rows=2*n*len(horizons),both_arm_path_horizon_rows=4*n*len(horizons),fan_rows=len(fan_ref),checks=checks,paired_checks=pair_checks)
Path('/private/tmp/fian_stage036_mc_audit.json').write_text(json.dumps(result,indent=2)+'\n')
print({k:v for k,v in result.items() if k not in ('checks','paired_checks')},flush=True)
