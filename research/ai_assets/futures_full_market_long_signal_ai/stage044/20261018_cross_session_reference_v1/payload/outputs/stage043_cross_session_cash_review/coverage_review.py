"""Finite coverage/action closure supplement; no source SQL or strategy replay."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import time
import pandas as pd

LINE=Path('/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai')
OUT=LINE/'outputs/stage043_cross_session_cash_review'
EXPERIMENT=LINE/'outputs/stage042_cross_session_experiment/experiment'

def main():
    began=time.monotonic();started=datetime.now().astimezone().isoformat(timespec='seconds')
    signals=pd.read_csv(EXPERIMENT/'signals_all.csv.gz',usecols=['reference_epoch','status','economics_status','policy_ready55','potential'])
    observed=signals.status.eq('observed_long_research_opportunity');exact=signals.economics_status.eq('exact_epoch_metadata_snapshot')
    assert observed.sum()==212852 and observed.equals(exact)
    projection=json.loads((LINE/'outputs/stage041_minimum_cash_economics_sources/economic_projection.json').read_text())
    unresolved={epoch for epoch,value in projection['instruments'].items() if value['economics_status']!='exact_epoch_metadata_snapshot'}
    assert len(unresolved)==18 and not signals.loc[observed,'reference_epoch'].isin(unresolved).any()
    assert not (signals.potential.eq(1)&~exact).any()
    closure=[]
    for directory in sorted((EXPERIMENT/'cash').iterdir()):
        b=pd.read_csv(directory/'budgets.csv.gz',dtype=str,keep_default_na=False)
        f=pd.read_csv(directory/'fills.csv.gz',dtype=str,keep_default_na=False)
        if 'budget_kind' not in b:b['budget_kind']=''
        if 'budget_id' not in f:f['budget_id']=pd.Series(dtype=str)
        new=b.loc[b.budget_kind.eq('new_entry')].copy()
        new['D_qty']=pd.to_numeric(new['D_qty'])
        positive=new.loc[new.D_qty.gt(0)].set_index('budget_id')
        buys=f.loc[f.side.eq('BUY')].set_index('budget_id')
        assert set(positive.index)==set(buys.index) and not buys.index.duplicated().any()
        for budget,row in positive.iterrows():assert row.D_qty==float(buys.loc[budget,'qty'])
        closure.append({'account_id':directory.name,'new_allocations':len(new),'positive_D_actions':len(positive),'BUY_fills':len(buys)})
    r={'schema':'stage043_finite_economic_action_coverage_v1','independent_review':True,'status':'coverage_closed',
       'observed_rows':int(observed.sum()),'exact_economic_observed_rows':int((observed&exact).sum()),
       'ready55_rows':int(signals.policy_ready55.sum()),'potential_rows':int(signals.potential.sum()),
       'potential_economics_unresolved':int((signals.potential.eq(1)&~exact).sum()),'unresolved_native_epochs':18,
       'unresolved_epoch_current_reference_rows':int(signals.reference_epoch.isin(unresolved).sum()),'D_buy_action_closure':closure,
       'sql_queries':0,'strategy_replays':0,'model_fit_calls':0,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
       'started_at':started,'finished_at':datetime.now().astimezone().isoformat(timespec='seconds'),'elapsed_seconds':time.monotonic()-began,
       'limitations':['Metadata exact epoch identity is not proof of historical broker economics; static snapshot/fallback assumptions remain.',
                      '55 breakout is a reference policy only; future AI universe remains the full product-day mother table.']}
    (OUT/'coverage_receipt.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':r['status'],'observed':r['observed_rows'],'potential':r['potential_rows'],'unresolved_reference_rows':r['unresolved_epoch_current_reference_rows'],'elapsed_seconds':r['elapsed_seconds']}))

if __name__=='__main__':main()
