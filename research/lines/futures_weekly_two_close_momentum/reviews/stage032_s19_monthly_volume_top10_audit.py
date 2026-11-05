from pathlib import Path
from collections import Counter
import hashlib,json,re
import h5py
import numpy as np
import pandas as pd
root=Path('/Users/mac/Desktop/fian/weekly19-stop-reversal.local/research/lines')
p=root/'futures_weekly_two_close_momentum'
base=p/'outputs/stage031_s19_weekly_shape_replay_v1'
new=p/'outputs/stage032_s19_monthly_volume_top10_v1'
arms=('control','expansion','expansion_break3')
def hash(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def verify_manifest(folder):
    files=set()
    for line in (folder/'SHA256SUMS').read_text().splitlines():
        expected, name=line.split(maxsplit=1)
        assert hash(folder/name)==expected,(folder,name)
        files.add(name)
    actual={str(f.relative_to(folder)) for f in folder.rglob('*') if f.is_file()}-{'SHA256SUMS'}
    if actual!=files: print('Manifest extra',folder.name,sorted(actual-files),flush=True)
    assert not files-actual
    if folder==new: assert actual==files
    return len(files)
receipt=json.loads((new/'receipt.json').read_text())
assert hash(base/'SHA256SUMS')==receipt['baseline_manifest_sha256']
assert hash(p/'tools/stage032_s19_monthly_volume_top10.py')==receipt['entrypoint_sha256']
assert hash(p/'stages/20261104_1604_stage032_s19_monthly_volume_top10_design.md')==receipt['design_sha256']
assert hash(Path(receipt['raw_path']))==receipt['raw_sha256']
result={'manifests':{f.name:verify_manifest(f) for f in (base,new)},'entries':{},'finance':{}}
print('SHA',result['manifests'],flush=True)

data_root=root/'futures_weekly19_stop_reversal/outputs/stage002_data/data_approved'
m=pd.read_csv(data_root/'mapping.csv',keep_default_na=False,usecols=['date','continuous_symbol_vt','main_contract_vt']).rename(columns={'continuous_symbol_vt':'product','main_contract_vt':'mapped_contract'})
products=receipt['products']
assert sorted(m['product'].unique())==products
cal=pd.Index(m.date.unique()).sort_values().to_series(index=None)
cal.index=range(len(cal))
cal_by_month=cal.groupby(cal.str[:7]).agg(['first','last'])
m=m[(m.date.str[:7]>='2014-12')&(m.date.str[:7]<'2026-11')].sort_values(['product','date'])
assert not (m.mapped_contract.ne('').groupby(m['product']).cummax() & m.mapped_contract.eq('')).any()
m=m[m.mapped_contract.ne('')]
d=pd.read_csv(new/'rank_volume_daily.csv')
j=m.merge(d,on=['date','product','mapped_contract'],how='outer',validate='1:1',indicator=True)
assert j._merge.eq('both').all()
q=pd.read_csv(data_root/'physical_epoch_daily.csv',usecols=['date','vt_symbol','volume']).rename(columns={'vt_symbol':'mapped_contract','volume':'admitted_volume'})
j=j.merge(q,on=['date','mapped_contract'],how='left',validate='m:1')
exists=j.admitted_volume.notna()
assert j.loc[exists,'status'].eq('admitted').all()
assert (j.loc[exists,'source_contract']==j.loc[exists,'mapped_contract']).all()
assert (j.loc[exists,'volume']==j.loc[exists,'admitted_volume']).all()
raw_book={}
missing=[]
with h5py.File(receipt['raw_path'],'r') as raw:
    def obs(key):
        if key not in raw_book:
            raw_book[key]={}
            if key in raw:
                raw_book[key]={str(int(n))[:8]:int(v) for n,v in raw[key].fields(['datetime','volume'])[:]}
        return raw_book[key]
    for r in j.loc[~exists].itertuples(index=False):
        stamp=r.date.replace('-','')
        ticker=r.mapped_contract.split('.')[0].upper()
        if r.mapped_contract.endswith('.CZCE'):
            prefix=ticker[:-3]
            key_year=min(range(int(r.date[:4])-5,int(r.date[:4])+5),key=lambda y:(str(y)[-1]!=ticker[-3],abs(y-int(r.date[:4]))))
            ticker=prefix+str(key_year)[-2:]+ticker[-2:]
        if r.mapped_contract=='MA501.CZCE':
            assert '2014-12-01'<=r.date<='2014-12-08'
            key='ME1501'
            raw_v=obs(key)[stamp]
            assert raw_v>0 and raw_v%2==0
            v=raw_v//2; status='legacy_double_sided'
        elif obs(ticker).get(stamp)==0:
            key=ticker; v=0; status='raw_confirmed_zero'
        else:
            key=ticker
            assert stamp not in obs(key),(r,obs(key).get(stamp))
            if ticker=='FU1805' and '2018-05-02'<=r.date<='2018-05-10':
                v=None; status='expired_mapping_bounded'
            else:
                assert ticker=='FU1905' and '2018-06-28'<=r.date<'2018-07-16'
                v=0; status='exchange_market_closed'; missing.append(stamp)
        assert r.source_contract==key and (pd.isna(r.volume) if v is None else r.volume==v) and r.status==status,(r,key,v,status)
    fu_keys=[key for key in raw if re.fullmatch(r'FU[0-9]{4}',key)]
    may_upper=sum(v for key in fu_keys for d,v in obs(key).items() if d.startswith('201805'))
    assert sum(obs(k).get(d,0) for k in fu_keys for d in missing)==0
assert j.status.value_counts().to_dict()==receipt['source_status_counts']
assert len(j.loc[~exists])==597 and may_upper==receipt['fu_2018_05_raw_all_contract_upper_bound']==4
rank=pd.read_csv(new/'monthly_rankings.csv')
roster={}
for mon,period in rank.groupby('effective_month'):
    previous=(pd.Period(mon,'M')-1).strftime('%Y-%m')
    assert period.source_month.eq(previous).all()
    assert period.source_first_day.eq(cal_by_month.loc[previous,'first']).all()
    assert period.source_last_day.eq(cal_by_month.loc[previous,'last']).all()
    assert period.effective_day.eq(cal_by_month.loc[mon,'first']).all()
    assert cal_by_month.loc[previous,'last']<cal_by_month.loc[mon,'first']
    monthly=j[j.date.str[:7].eq(previous)]
    stats=monthly.groupby('product').volume.agg(['sum','count','size']).reindex(products,fill_value=0)
    stats=stats.sort_values('sum',ascending=False,kind='stable')
    stats=stats[stats['sum']>0]
    expected={k:i for i,k in enumerate(stats.index,start=1)}
    cutoff=stats['sum'].iat[9]
    assert period.cutoff_volume.eq(cutoff).all()
    selected=set()
    for x in period.itertuples(index=False):
        s=monthly[monthly['product'].eq(x.product)].volume
        assert (s.sum(),s.count(),s.isna().sum())==(x.known_volume,x.covered_days,x.unresolved_days)
        i=expected.get(x.product)
        assert pd.isna(x.rank) if i is None else x.rank==i
        assert bool(x.selected)==bool(i and i<=10)
        if x.selected: selected.add(x.product)
    assert len(selected)==10
    roster[mon]=selected
assert len(roster)==143 and len(rank)==143*19
assert rank.loc[(rank.effective_month=='2018-06')&(rank['product']=='fu.SHFE'),'cutoff_volume'].iat[0]==2032485>may_upper
result['ranking']={'daily_rows':len(j),'rank_rows':len(rank),'months':len(roster),'selected_per_month':10,'status':j.status.value_counts().to_dict(),'fu_may_upper':may_upper,'fu_cutoff':2032485}
print('Rank',result['ranking'],flush=True)

all_paths={}
unique_pins={}
for arm in arms:
    for group in ('full_pool','monthly_top10'):
        folder=new/group/arm
        all_paths[f'{group}/{arm}']=folder
        old=json.loads((base/arm/'inputs.json').read_text())
        config=json.loads((folder/'inputs.json').read_text())
        for key in ['inputs_sha256','source_sha256']:
            for name,digest in config[key].items():
                if name not in unique_pins: unique_pins[name]=hash(Path(name))
                assert unique_pins[name]==digest,(name,digest)
        stage032_source=config.pop('source_sha256')
        stage031_source=old.pop('source_sha256')
        expected_changes={str(p/'tools/run_weekly_portfolio.py')}
        if group=='monthly_top10':
            entrypoint=str(p/'tools/stage032_s19_monthly_volume_top10.py')
            assert stage032_source.pop(entrypoint)==receipt['entrypoint_sha256']
        assert stage032_source.keys()==stage031_source.keys()
        assert {key for key in stage032_source if stage032_source[key]!=stage031_source[key]}==expected_changes
        for key in expected_changes:
            historical=base/'analysis/frozen_source'/Path(key).name
            assert hash(historical)==stage031_source[key]
        if group=='full_pool':
            assert {f.name for f in folder.iterdir()}=={f.name for f in (base/arm).iterdir()}
            assert all(f.read_bytes()==(base/arm/f.name).read_bytes() for f in folder.iterdir() if f.name!='inputs.json')
            assert config==old
            continue
        frozen_roster={month:set(picks) for month,picks in config.pop('monthly_entry_products').items()}
        assert frozen_roster==roster and config==old
        f=pd.read_csv(folder/'fills.csv',keep_default_na=False)
        b=pd.read_csv(folder/'monthly_entry_blocks.csv')
        signals=pd.read_csv(folder/'signals.csv')
        sg={(x.date,x.product,x.action) for x in signals.itertuples(index=False)}
        tape={}
        for x in f.itertuples(index=False): tape.setdefault((x.date,x.product),[]).append(x)
        counts=Counter()
        examples={}
        for x in f.itertuples(index=False):
            if x.reason=='entry':
                assert x.product in roster[x.date[:7]]
                assert (x.signal_day,x.product,'open_long' if x.side==1 else 'open_short') in sg
                if any(y.reason=='weekly_stop' and y.signal_day==x.signal_day for y in tape[x.date,x.product]):
                    assert tape[x.date,x.product].index(x)>0
                    counts['executed_reverse']+=1
                if x.signal_day[:7]!=x.date[:7]:
                    counts['executed_cross_month']+=1
                    if x.product not in roster[x.signal_day[:7]]:
                        counts['executed_only_new_month']+=1
                        examples.setdefault('only_new_month',(x.signal_day,x.date,x.product))
            elif x.product not in roster[x.date[:7]]:
                counts['out_of_pool_'+x.reason]+=1
                examples.setdefault('out_of_pool_'+x.reason,(x.date,x.product))
        for x in b.itertuples(index=False):
            assert x.product not in roster[x.date[:7]]
            assert (x.signal_day,x.product,x.action) in sg
            same_day=tape.get((x.date,x.product),[])
            assert not any(y.reason=='entry' for y in same_day)
            assert (x.kind=='reversal')==any(y.reason=='weekly_stop' and y.signal_day==x.signal_day for y in same_day)
            counts['blocked_'+x.kind]+=1
            if x.signal_day[:7]!=x.date[:7] and x.product in roster[x.signal_day[:7]]:
                counts['blocked_only_new_month']+=1
                examples.setdefault('blocked_only_new_month',(x.signal_day,x.date,x.product))
        result['entries'][arm]={'counts':dict(counts),'examples':examples}
        print('Entry',arm,dict(counts),examples,flush=True)
result['input_pins']=len(unique_pins)
print('Input pins',len(unique_pins),flush=True)
# Reconstruct financial ledgers using the historical contracts and the trade tape only.
frozen=root/'futures_weekly19_stop_reversal/outputs'
data=pd.read_csv(frozen/'stage002_data/data_approved/physical_epoch_daily.csv',usecols=['date','vt_symbol','contract_epoch_id','open','high','low','close'])
data_by_key={(r.date,r.contract_epoch_id):r for r in data.itertuples(index=False)}
specs=json.loads((frozen/'stage003_D_20261103_attempt01/contract_settings.json').read_text())
for arm,folder in all_paths.items():
    summary=json.loads((folder/'summary.json').read_text())
    d=pd.read_csv(folder/'daily.csv')
    fills=pd.read_csv(folder/'fills.csv')
    c=pd.read_csv(folder/'cycles.csv',keep_default_na=False)
    cycles_cash={k:0 for k in c.cycle}
    by_date=dict(list(fills.groupby('date',sort=False)))
    positions={}
    ledger=[]
    cash=300000
    slip=commission=0
    for day in d.date:
        for fill in (by_date[day].itertuples(index=False) if day in by_date else ()):
            market=data_by_key[(day,fill.epoch)]
            assert (fill.contract,fill.price,fill.one_price)==(market.vt_symbol,market.open,market.low==market.high)
            assert fill.size==specs['sizes'][fill.contract]
            assert fill.slippage==specs['slippages'][fill.contract]*fill.size*fill.volume
            assert fill.commission==specs['rates'][fill.contract]*fill.size*fill.volume*fill.price
            flow=-fill.side*fill.price*fill.volume*fill.size-fill.slippage-fill.commission
            cash+=flow
            cycles_cash[fill.cycle]+=flow
            slip+=fill.slippage
            commission+=fill.commission
            if fill.reason in ('entry','roll_open'):
                assert fill.product not in positions
                positions[fill.product]=(fill.epoch,fill.contract,fill.side,fill.volume,fill.size,fill.price,fill.cycle)
            else:
                prior=positions.pop(fill.product)
                assert (fill.epoch,fill.contract,-fill.side,fill.volume,fill.size,fill.cycle)==(*prior[:5],prior[-1]),(fill,prior)
        mark=margin=0
        for product,(epoch,symbol,side,volume,size,last,cycle) in positions.items():
            bar=data_by_key.get((day,epoch))
            close=last if bar is None else bar.close
            mark+=side*close*volume*size
            margin+=close*size*volume*specs['margin_ratios'][symbol]
            positions[product]=(epoch,symbol,side,volume,size,close,cycle)
        ledger.append((cash+mark,cash,mark,margin,len(positions),slip,commission))
    names=['equity','cash','position_value','margin','positions','cumulative_slippage','cumulative_commission']
    np.testing.assert_allclose(ledger,d[names],atol=1e-7,rtol=0)
    terminal_marks={value[-1]:value[2]*value[3]*value[4]*value[5] for value in positions.values()}
    for r in c.itertuples(index=False):
        np.testing.assert_allclose([cycles_cash[r.cycle],terminal_marks.get(r.cycle,0),cycles_cash[r.cycle]+terminal_marks.get(r.cycle,0)],[r.cash_flow,r.terminal_mark,r.net_pnl],atol=1e-7,rtol=0)
    ending=d.equity.iat[-1]; closed=c[c.exit_day.ne('')]
    daily_pnl=d.equity.diff().fillna(d.equity-300000)
    drawdown=(d.equity/d.equity.cummax().clip(lower=300000)-1)
    returns=d.equity.pct_change().fillna(d.equity/300000-1)
    a=pd.read_csv(folder/'annual.csv')
    np.testing.assert_allclose(daily_pnl.groupby(d.date.str[:4]).sum(),a.net_pnl,atol=1e-7,rtol=0)
    computed=dict(equity=ending,net_pnl=ending-300000,max_dd_pct=100*drawdown.min(),sharpe=returns.mean()/returns.std()*np.sqrt(252),closed_cycles=len(closed),wins=int(closed.net_pnl.gt(0).sum()),losses=int(closed.net_pnl.lt(0).sum()),fills=len(fills),open_positions=len(positions),peak_margin_ratio_pct=(d.margin/d.equity).max()*100)
    np.testing.assert_allclose(list(computed.values()),[summary[k] for k in computed],atol=1e-7,rtol=0)
    result['finance'][arm]={'days':len(d),'cycles':len(c),**{k:float(v) if isinstance(v,np.floating) else int(v) if isinstance(v,np.integer) else v for k,v in computed.items()}}
    print('Financial',arm,len(d),len(c),computed,flush=True)
result['verdict']='PASS_WITH_LIMITATIONS'
Path('/private/tmp/fian_stage032_audit.json').write_text(json.dumps(result,indent=2)+'\n')
