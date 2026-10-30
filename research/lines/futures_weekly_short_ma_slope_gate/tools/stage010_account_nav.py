"""Stage010: project frozen Stage009 ledgers to deposit-inclusive trading NAV.

This module imports no strategy, engine, market client or production runtime.
Source accounting is checked before the requested display-only projection.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import math
import numpy as np
import pandas as pd

LINE=Path(__file__).resolve().parents[1]
STARTS=tuple(f'{y}-{m:02d}-01' for y in range(2015,2027) for m in (1,6) if (y,m)<=(2026,1))
VARIANTS=('A_R','A_idle','C_R','C_idle')
CUTOFF='2026-10-29'
INITIAL=150000.
POINTS=141996
SOURCE_MANIFEST_SHA='b4712560c72548106fb9e4273895e1bfc80c56a6813cdfe3d71b4190b5d5a424'
DAILY_FIELDS=['start','variant','date','raw_account_equity','net_pnl','trading_account_equity',
    'reserve_balance','cumulative_transfer','transfer_amount','total_account_equity','slippage','commission','trade_count']


def require(value,label):
    if not value:raise ValueError('stage010_account_nav:'+label)


def near(a,b):return np.allclose(a,b,rtol=1e-10,atol=1e-6,equal_nan=False)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def source_admission():
    manifest=LINE/'stages/stage009_delivery_manifest.json'
    require(sha(manifest)==SOURCE_MANIFEST_SHA,'locked_source_manifest')
    locked=json.loads(manifest.read_text());require(locked['accepted'] is True,'source_not_accepted')
    require(locked['arm_windows']==46 and locked['derived_variant_windows']==92 and locked['total_daily_points']==POINTS,'source_scope')
    selected=[LINE/'artifacts/stage009_multistart'/name for name in ['all_daily.csv','summary.csv','reserve_events.csv']]
    selected += [LINE/'stages'/name for name in ['stage009_independent_final.json','stage009_freeze.json']]
    hashes={str(manifest):SOURCE_MANIFEST_SHA}
    for path in selected:
        expected=locked['files_sha256'][str(path)];require(sha(path)==expected,'locked_source:'+path.name);hashes[str(path)]=expected
    independent=json.loads(selected[-2].read_text())
    require(independent['status']=='PASS_WITH_LIMITATIONS' and not independent['failures'],'source_independent_status')
    return hashes


def project_curve(source,variant):
    require(variant in VARIANTS,'variant')
    require(set(DAILY_FIELDS)-{'start','variant'}<=set(source),'curve_columns')
    d=source.copy();d['date']=pd.to_datetime(d.date,errors='raise').dt.strftime('%Y-%m-%d')
    require(len(d)>0 and d.date.is_monotonic_increasing and not d.date.duplicated().any(),'ordered_unique_dates')
    for field in DAILY_FIELDS[3:]:
        d[field]=pd.to_numeric(d[field],errors='raise');require(np.isfinite(d[field]).all(),'finite_'+field)
    e=d.trading_account_equity.to_numpy(float);t=d.cumulative_transfer.to_numpy(float);r=d.reserve_balance.to_numpy(float)
    require(near(e,d.raw_account_equity.to_numpy(float)+t),'trading_bridge')
    require(near(d.raw_account_equity,INITIAL+d.net_pnl.cumsum()),'true_pnl_bridge')
    require(near(d.total_account_equity,e+r) and near(r+t,INITIAL),'source_bucket_conservation')
    require((r>=-1e-6).all() and (r<=INITIAL+1e-6).all() and (np.diff(t)>=-1e-6).all() and (t>=-1e-6).all() and (d.transfer_amount>=-1e-6).all(),'isolated_reserve')
    require(near(t,d.transfer_amount.cumsum()),'deposit_daily_bridge')
    if variant.endswith('_idle'):require(near(t,0) and near(r,INITIAL),'original_cannot_receive')
    require(near(e[0],INITIAL) and near(d.net_pnl.iloc[0],0) and near(t[0],0),'fresh_150k_start')
    d['account_nav']=e/INITIAL
    d['balance_drawdown_pct']=(e/np.maximum.accumulate(np.r_[INITIAL,e])[1:]-1)*100
    return d


def metrics(d):
    e=d.trading_account_equity.to_numpy(float);previous=np.r_[INITIAL,e[:-1]]
    defined=bool((previous>0).all())
    changes=np.divide(e-previous,previous,out=np.full_like(e,np.nan),where=previous>0)
    defined=defined and bool(np.isfinite(changes).all())
    std=float(changes.std(ddof=1)) if defined and len(e)>1 else 0.
    sharpe=float(changes.mean()/std*math.sqrt(252)) if defined and std>0 else 0.
    return dict(initial_trading_capital=INITIAL,account_end_equity=float(e[-1]),
        account_growth_pct=float((e[-1]/INITIAL-1)*100),balance_max_dd_pct=float(d.balance_drawdown_pct.min()),
        balance_sharpe=sharpe,balance_returns_defined=defined,real_trading_net_pnl=float(d.net_pnl.sum()),
        total_transferred=float(d.cumulative_transfer.iloc[-1]),off_account_reserve_end=float(d.reserve_balance.iloc[-1]),
        total_slippage=float(d.slippage.sum()),total_commission=float(d.commission.sum()),modeled_fill_count=int(d.trade_count.sum()),
        transfer_event_days=int(d.transfer_amount.gt(0).sum()),nonpositive_trading_equity_days=int((e<=0).sum()),
        actual_start=str(d.date.iloc[0]),actual_end=str(d.date.iloc[-1]),trading_days=len(d))


def project_all(source_summary,source_daily,events):
    expected={(s,v) for s in STARTS for v in VARIANTS}
    require(len(source_summary)==92 and not source_summary.duplicated(['start','variant']).any() and set(zip(source_summary.start,source_summary.variant))==expected,'92_source_summaries')
    require(len(source_daily)==POINTS and not source_daily.duplicated(['start','variant','date']).any() and set(zip(source_daily.start,source_daily.variant))==expected,'141996_source_daily_points')
    si=source_summary.set_index(['start','variant']);rows=[];curves=[];calendars={}
    for (start,variant),group in source_daily.groupby(['start','variant'],sort=True):
        d=project_curve(group.sort_values('date').reset_index(drop=True),variant);m=metrics(d);old=si.loc[(start,variant)]
        require(start<=m['actual_start'] and m['actual_end']==CUTOFF,'source_cutoff')
        calendar=tuple(d.date)
        if start in calendars:require(calendar==calendars[start],'four_variant_calendar')
        else:calendars[start]=calendar
        mapping={'account_end_equity':'trading_end_equity','real_trading_net_pnl':'net_pnl','total_transferred':'total_transferred',
            'off_account_reserve_end':'reserve_end_balance','total_slippage':'total_slippage','total_commission':'total_commission',
            'modeled_fill_count':'modeled_fill_count','trading_days':'trading_days','transfer_event_days':'transfer_event_days',
            'nonpositive_trading_equity_days':'nonpositive_trading_equity_days'}
        for new,previous in mapping.items():require(near(m[new],old[previous]),'unchanged_'+new)
        require(m['actual_start']==str(old.actual_start)[:10] and m['actual_end']==str(old.actual_end)[:10],'unchanged_dates')
        ev=events.loc[(events.start==start)&(events.variant==variant)]
        event_daily=ev.groupby('date').transfer_amount.sum().to_dict()
        require(near(d.transfer_amount,d.date.map(event_daily).fillna(0)),'unchanged_deposit_events')
        require(near(m['account_end_equity']-INITIAL,m['real_trading_net_pnl']+m['total_transferred']),'final_account_bridge')
        true_stats={k:old[k] for k in old.index if k.startswith('round_') or k=='open_round_net_mtm'}
        rows.append(dict(start=start,variant=variant,arm=variant[0],funding_mode='external_topup' if variant.endswith('_R') else 'original',
            observation_only=start=='2026-01-01',**m,**true_stats))
        curves.append(d[DAILY_FIELDS+['account_nav','balance_drawdown_pct']])
    summary=pd.DataFrame(rows);daily=pd.concat(curves,ignore_index=True);index=summary.set_index(['start','variant']);pairs=[]
    for start in STARTS:
        for arm in ['A','C']:
            a=index.loc[(start,arm+'_idle')];c=index.loc[(start,arm+'_R')]
            pairs.append(dict(start=start,arm=arm,cohort='January' if start[5:7]=='01' else 'June',observation_only=start=='2026-01-01',
                delta_account_growth_pp=c.account_growth_pct-a.account_growth_pct,delta_balance_max_dd_pp=c.balance_max_dd_pct-a.balance_max_dd_pct,
                delta_balance_sharpe=c.balance_sharpe-a.balance_sharpe,delta_real_trading_net_pnl=c.real_trading_net_pnl-a.real_trading_net_pnl,
                delta_account_end_equity=c.account_end_equity-a.account_end_equity,external_deposits=c.total_transferred))
    return summary,pd.DataFrame(pairs),daily


def build_data(output):
    output=Path(output);require(not output.exists(),'output_already_exists')
    source_hashes=source_admission();old=LINE/'artifacts/stage009_multistart'
    source_summary=pd.read_csv(old/'summary.csv',float_precision='round_trip')
    source_daily=pd.read_csv(old/'all_daily.csv',usecols=DAILY_FIELDS,float_precision='round_trip')
    events=pd.read_csv(old/'reserve_events.csv',float_precision='round_trip')
    summary,paired,daily=project_all(source_summary,source_daily,events)
    # Bind the exact sources read; do not accept a source changing mid-build.
    for path,expected in source_hashes.items():require(sha(path)==expected,'source_changed_during_projection')
    output.mkdir(parents=True)
    for name,frame in [('summary.csv',summary),('paired.csv',paired),('daily.csv',daily)]:frame.to_csv(output/name,index=False)
    metadata=dict(schema='stage010-off-account-nav-v1',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        status='INDEPENDENT_REVIEW_PENDING',line_id=LINE.name,financial_replays=0,market_downloads=0,production_accesses=0,
        strategy_parameters_changed=False,transaction_ledgers_changed=False,cutoff=CUTOFF,independent_starts=len(STARTS),
        variant_windows=len(summary),paired_windows=len(paired),daily_points=len(daily),initial_trading_capital=INITIAL,
        source_files_sha256=source_hashes,projection_source_sha256=sha(__file__),promotion_decision='NO_PROMOTION',
        nav_definition='trading_account_equity / 150000; excludes off-account reserve; includes transferred deposits',
        account_bridge='E = 150000 + cumulative true net trading PnL + cumulative external deposits',
        metric_warning='Account growth, balance drawdown and balance Sharpe include cashflow; not flow-adjusted strategy performance.',
        balance_sharpe_definition='simple daily account balance changes; initial previous balance150000; ddof1; sqrt252; undefined denominators -> 0 plus explicit false flag',
        source_research='https://www.backtrader.com/blog/posts/2017-06-19-fund-tracking/fund-tracking/')
    (output/'projection.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    return metadata


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=LINE/'artifacts/stage010_off_account_nav')
    print(json.dumps(build_data(p.parse_args().output),ensure_ascii=False,indent=2))
