"""Single fixed Stage268 attribution; reuse market cache and accepted ledger.

No backtesting engine, downloads, model fitting or trading APIs are invoked.
Sparse coverage is a failed evidence prerequisite, never grounds for retuning.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

from stage269_statistics import build_outcomes, effect_summary, effect_with_bootstrap, group_stats, ols_incremental
from stage269_episode_attribution import build_episode_table, episode_group_stats, episode_effect_with_bootstrap

LINE = Path(__file__).resolve().parents[1]
OUT = LINE/'outputs/stage269_market_efficiency_validation'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_calendar(values):
    # RQ calendar stores integer YYYYMMDD, not Unix nanoseconds.
    return pd.DatetimeIndex(pd.to_datetime(np.asarray(values).astype(str),format='%Y%m%d')).normalize()


def clean_json(value):
    if isinstance(value, dict):
        return {str(k):clean_json(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):
        return [clean_json(v) for v in value]
    if isinstance(value,(np.integer,)):
        return int(value)
    if isinstance(value,(float,np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value,(np.bool_,)):
        return bool(value)
    if isinstance(value,(pd.Timestamp,datetime)):
        return value.isoformat()
    return value


def write_json(path, value):
    path.write_text(json.dumps(clean_json(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def mask_period(frame, start=None, end=None, exclude_year=None):
    """Keep calendar intact; blank groups when the full label crosses a split."""
    result=frame.copy()
    dates=pd.to_datetime(result['date'])
    ends=pd.to_datetime(result['label_end'])
    if exclude_year is not None:
        lo=pd.Timestamp(int(exclude_year),1,1)
        hi=pd.Timestamp(int(exclude_year),12,31)
        keep=ends.notna() & ~((dates<=hi)&(ends>=lo))
    else:
        keep=dates.between(pd.Timestamp(start),pd.Timestamp(end)) & ends.between(pd.Timestamp(start),pd.Timestamp(end))
    result.loc[~keep,'regime']=np.nan
    return result


def sensitivity_table(frame):
    """Same main gate/classified anchors, no auxiliary raw-history rescue."""
    rows=[]
    for metric in ['market_er20','market_er120','commodity_er60','sector_equal_er60','outside_pool_er60','own_pool_er60']:
        if metric not in frame:
            continue
        valid=frame['gate_pass'].eq(True)&frame['regime'].isin(['low','mid','high'])&frame[metric].notna()&frame['future20_return'].notna()
        f=frame.loc[valid]
        rows.append(dict(metric=metric,n=len(f),pearson_future20=f[metric].corr(f['future20_return']) if len(f)>1 else np.nan,
                         spearman_future20=f[metric].corr(f['future20_return'],method='spearman') if len(f)>1 else np.nan,
                         scope='descriptive same main certified/classified anchors; no independent auxiliary regrouping'))
    return rows


def main():
    dest=OUT/'analysis'
    dest.mkdir(parents=True,exist_ok=True)
    base=LINE/'outputs/stage251_half_r_ab/A_final3'
    frozen=json.loads((LINE/'outputs/stage268_market_efficiency_design/design_inputs.json').read_text())
    daily=pd.read_csv(base/'daily.csv',parse_dates=['date'])
    expected=next(x['sha256'] for x in frozen['source_files'] if x['logical_name']=='daily.csv')
    if sha(base/'daily.csv')!=expected:
        raise ValueError('frozen daily source drift')
    market_path=OUT/'market/market_daily.csv'
    market=pd.read_csv(market_path,parse_dates=['date'])
    market_summary=json.loads((OUT/'market/market_summary.json').read_text())
    if sha(market_path)!=market_summary['output_sha256']['market_daily.csv']:
        raise ValueError('market cache drift')
    calendar=parse_calendar(np.load(LINE/'outputs/stage265_deep_daily/rqalpha/trading_dates.npy'))
    calendar=calendar[(calendar>=daily.date.min())&(calendar<=daily.date.max())]
    frame=build_outcomes(daily,calendar,150000).merge(market,on='date',how='left',validate='one_to_one')
    if len(frame)!=1641 or not frame.source_present.all():
        raise ValueError('unexpected baseline/calendar coverage')
    frame.to_csv(dest/'joined_daily.csv',index=False)
    primary=effect_with_bootstrap(frame,60,2000,42)
    block120=effect_with_bootstrap(frame,120,2000,42)
    primary['evidence_status']='INSUFFICIENT_CROSS_CYCLE_MARKET_COVERAGE'
    primary['inference_limitation']='Overlapping sparse historical anchors concentrated in 2025-2026; conditional block intervals, not independent observations or fresh OOS.'
    write_json(dest/'primary_block60.json',primary)
    write_json(dest/'sensitivity_block120.json',block120)
    group_rows=[]
    for outcome in ['future20_return','future20_cash','normalized_future20_return','future20_return_extra_slippage']:
        group=group_stats(frame,outcome)
        group['outcome']=outcome
        group['profit_probability_scope']='original future20 net return, same label'
        group_rows.extend(group.to_dict('records'))
    pd.DataFrame(group_rows).to_csv(dest/'group_summary.csv',index=False)
    yearly=[]
    for year in range(2020,2027):
        result=effect_summary(mask_period(frame,f'{year}-01-01',f'{year}-12-31'))
        yearly.append(dict(year=year,**{k:v for k,v in result.items() if k!='groups'}))
    pd.DataFrame(yearly).to_csv(dest/'annual_effects.csv',index=False)
    periods=[]
    for label,start,end in [('2020-2022','2020-01-01','2022-12-31'),('2023-2024','2023-01-01','2024-12-31'),('2025+','2025-01-01','2026-12-31')]:
        result=effect_summary(mask_period(frame,start,end))
        periods.append(dict(period=label,**{k:v for k,v in result.items() if k!='groups'}))
    pd.DataFrame(periods).to_csv(dest/'period_effects.csv',index=False)
    leave=[]
    for year in range(2020,2027):
        result=effect_summary(mask_period(frame,exclude_year=year))
        leave.append(dict(excluded_year=year,**{k:v for k,v in result.items() if k!='groups'}))
    pd.DataFrame(leave).to_csv(dest/'leave_year_out.csv',index=False)
    contemporaneous=[]
    for x in ['market_er60','commodity_er60','sector_equal_er60','outside_pool_er60']:
        m=frame.loc[frame.gate_pass.eq(True)&frame[x].notna()&frame.past60_return.notna()]
        contemporaneous.append(dict(metric=x,n=len(m),pearson=m[x].corr(m.past60_return),spearman=m[x].corr(m.past60_return,method='spearman'),scope='same trailing60 window; explanatory only'))
    pd.DataFrame(contemporaneous).to_csv(dest/'contemporaneous.csv',index=False)
    pd.DataFrame(sensitivity_table(frame)).to_csv(dest/'market_sensitivities.csv',index=False)
    model_controls=[[],['market_vol60'],['market_vol60','market_corr60','direction_breadth60','own_pool_er60'],
        ['market_vol60','market_corr60','direction_breadth60','own_pool_er60','past60_vol','broker10_margin_to_equity_pct','c3_active_products']]
    models=[dict(model=i,**ols_incremental(frame,controls=controls,year_fe=True)) for i,controls in enumerate(model_controls)]
    write_json(dest/'regression_summary.json',models)
    episodes=build_episode_table(base,market,calendar)
    episodes.to_csv(dest/'episodes.csv',index=False)
    episode_groups=episode_group_stats(episodes)
    episode_groups.to_csv(dest/'episode_groups.csv',index=False)
    episode_effect=episode_effect_with_bootstrap(episodes,calendar,block=60,repeats=2000,seed=42)
    write_json(dest/'episode_block60.json',episode_effect)
    coverage=[]
    for year,f in frame.groupby(frame.date.dt.year):
        coverage.append(dict(year=int(year),calendar_days=len(f),gate_days=int(f.gate_pass.eq(True).sum()),
            classified_days=int(f.regime.isin(['low','mid','high']).sum()),mature_classified_days=int((f.regime.isin(['low','mid','high'])&f.label_mature).sum())))
    summary=dict(stage='stage269',recorded_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        line_id=LINE.name,verdict='INSUFFICIENT_CROSS_CYCLE_MARKET_COVERAGE',
        financial_replays=0,AI_training=0,downloads=0,market_feature_computation_runs=1,
        formal_parameters='C9/150000; AI10 nonfu+fixed fu; half-R stop on; retry once',
        baseline_scope='Stage251 A_final3 accepted correctness overlay, formal parameters; not production qualification',
        source_calendar_days=len(frame),market_gate_days=int(frame.gate_pass.eq(True).sum()),
        classified_days=int(frame.regime.isin(['low','mid','high']).sum()),
        mature_classified_days=primary['n_labeled'],nonoverlap20_qualified_anchors=primary['nonoverlap20_n'],
        coverage_by_year=coverage,primary_return_difference=primary['return_difference'],primary_return_ci=primary['return_ci'],
        primary_probability_difference=primary['profit_probability_difference'],primary_probability_ci=primary['profit_probability_ci'],
        episode_rows=len(episodes),episode_closed=int(episodes.is_closed.sum()),episode_open=int(episodes.is_open.sum()),
        episode_classified=int(episodes.regime.isin(['low','mid','high']).sum()),episode_risk_unmatched=int(episodes.risk_unmatched.sum()),
        market_daily_sha256=sha(market_path),daily_sha256=expected,driver_sha256=sha(__file__),
        main_gate_unchanged=True,selection_warning='All source periods previously seen; sparse conditional association cannot establish general rule or causality',
        next_step='Stop this hypothesis stage; a future liquid-universe study needs independent predeclaration, no result-driven gate relaxation')
    write_json(dest/'analysis_summary.json',summary)
    write_json(dest/'analysis_file_hashes.json',{p.name:sha(p) for p in sorted(dest.iterdir()) if p.is_file() and p.name!='analysis_file_hashes.json'})
    print(json.dumps(clean_json(summary),ensure_ascii=False))


if __name__=='__main__':
    main()
