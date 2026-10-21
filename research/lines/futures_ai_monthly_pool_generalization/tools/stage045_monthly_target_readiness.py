"""Full-asof-universe conditional rank identification, not a model/backtest.

Stage042 net-R is a new research target. Its static economics and assumed daily
opens remain conditional; engineering floors never certify financial validity.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from stage002_cohort_contract import build_cohort_bounds

LINE=Path(__file__).resolve().parents[1]
INPUT=LINE/'outputs/stage042_coldstart_coverage/monthly_coldstart_coverage.csv'
FLOORS=dict(min_train_months=60,min_robust_rows=612,min_each_class=100,
            min_each_class_months=24,min_train_products=12)


def _bool(series,name):
    value=series.astype(str).str.strip().str.lower()
    if not value.isin(['true','false','1','0']).all():raise ValueError('explicit boolean required: '+name)
    return value.isin(['true','1'])


def build_targets(coverage):
    frame=coverage.copy()
    for name in ['asof_eligible','maturity_clock_reached','all_paths_value_known']:
        frame[name]=_bool(frame[name],name)
    if not frame.row_role.isin(['candidate','fixed','monthly_average_F']).all():raise ValueError('unknown row role')
    frame['history_ok']=frame.asof_eligible & frame.row_role.eq('candidate')
    frame['feature_coverage_ok']=frame.history_ok
    frame['tradable_asof']=frame.history_ok
    frame['label_complete']=frame.maturity_clock_reached
    # A finite collection of known paths with different values is not a point.
    value=pd.to_numeric(frame.cumulative_net_r,errors='raise')
    if (frame.all_paths_value_known & value.notna() & ~np.isfinite(value)).any():raise ValueError('nonfinite conditional value')
    frame['label_coverage_ok']=frame.all_paths_value_known & value.notna()
    frame['label_end']=frame.target_day
    frame['future_net_pnl_60d']=value
    result=build_cohort_bounds(frame)
    result['robust_target']=pd.Series([None]*len(result),dtype=object)
    result.loc[result.target_state.eq('identified_top_half'),'robust_target']=1
    result.loc[result.target_state.eq('identified_bottom_half'),'robust_target']=0
    result['target_identity']='monthly_flat_coldstart_future60_close_sum_episode_unitR_static_economics_daily_open_conditional'
    result['formal_training_qualified']=False
    return result


def training_gate(targets,cutoff=None):
    rows=targets[targets.point_target_identified].copy()
    if cutoff is not None:
        end=pd.to_datetime(rows.label_end,errors='raise')
        rows=rows[(rows.eval_date < pd.Timestamp(cutoff)) & (end < pd.Timestamp(cutoff))]
    classes=rows.robust_target.astype(int)
    zero=rows[classes.eq(0)];one=rows[classes.eq(1)]
    counts=dict(robust_rows=len(rows),months=rows.eval_date.nunique(),products=rows.product_vt_symbol.nunique(),
                class0_rows=len(zero),class1_rows=len(one),class0_months=zero.eval_date.nunique(),class1_months=one.eval_date.nunique())
    failures=[]
    if counts['robust_rows']<FLOORS['min_robust_rows']:failures.append('robust_rows_below_612')
    if counts['months']<FLOORS['min_train_months']:failures.append('months_below_60')
    if counts['products']<FLOORS['min_train_products']:failures.append('products_below_12')
    for c in [0,1]:
        if counts[f'class{c}_rows']<FLOORS['min_each_class']:failures.append(f'class{c}_rows_below_100')
        if counts[f'class{c}_months']<FLOORS['min_each_class_months']:failures.append(f'class{c}_months_below_24')
    return dict(**{k:int(v) for k,v in counts.items()},cutoff=cutoff,engineering_floor_pass=not failures,
                failures=failures,formal_qualification=False,fit_permission=False)


def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(input_path=INPUT,output_path=None):
    output_path=Path(output_path or LINE/'outputs/stage045_monthly_target_readiness')
    if output_path.exists():raise ValueError('immutable_output_exists')
    coverage=pd.read_csv(input_path)
    targets=build_targets(coverage)
    cohort=[]
    for date,g in targets.groupby('eval_date',sort=True):
        members=g[g.asof_member];known=members[members.label_observable]
        cohort.append(dict(eval_date=str(date.date()),N=len(members),K=len(known),unknown=len(members)-len(known),
                           mature_members=int(members.maturity_clock_reached.sum()),
                           robust_top=int(members.target_state.eq('identified_top_half').sum()),
                           robust_bottom=int(members.target_state.eq('identified_bottom_half').sum()),
                           ambiguous=int(members.target_state.eq('ambiguous').sum()),
                           known_zero=int(known.future_net_pnl_60d.eq(0).sum()),constant=int(members.constant_observed_target.sum()),
                           minimum_known_for_possible_point_label=len(members)//2+1 if len(members) else 0))
    cohorts=pd.DataFrame(cohort)
    robust=targets[targets.point_target_identified]
    counts=[]
    for grouping,series in [('year',targets.eval_date.dt.year),('exchange',targets.exchange),('product',targets.product_vt_symbol)]:
        for key,g in targets.groupby(series,sort=True):
            counts.append(dict(grouping=grouping,key=str(key),rows=len(g),asof_members=int(g.asof_member.sum()),
                               mature_members=int((g.asof_member & g.maturity_clock_reached).sum()),known=int(g.label_observable.sum()),
                               top=int(g.target_state.eq('identified_top_half').sum()),bottom=int(g.target_state.eq('identified_bottom_half').sum())))
    gate=training_gate(targets)
    annual=[training_gate(targets,f'{year}-01-01') for year in range(2018,2027)]
    summary=dict(issued_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),rows=len(targets),
                 asof_members=int(targets.asof_member.sum()),known_point_values=int(targets.label_observable.sum()),
                 robust_rows=len(robust),target_state_counts=targets.target_state.value_counts().to_dict(),
                 robust_months=int(robust.eval_date.nunique()),robust_products=int(robust.product_vt_symbol.nunique()),
                 overall_engineering_gate=gate,annual_pretest_training_gates=annual,
                 model_fits=0,orders=0,formal_AC_run=False,production_modified=False,
                 interpretation='identification under declared research source assumptions; not historical PIT truth, predictive evidence or financial return',
                 fit_decision='DIAGNOSTIC_FLOOR_ONLY_REQUIRES_SOURCE_REVIEW_FEATURE_JOIN_AND_FIXED_PROTOCOL' if gate['engineering_floor_pass'] else 'DO_NOT_FIT_INSUFFICIENT_IDENTIFIABLE_LABELS')
    output_path.mkdir(parents=True)
    targets.to_csv(output_path/'monthly_target_identification.csv',index=False)
    cohorts.to_csv(output_path/'monthly_cohorts.csv',index=False)
    pd.DataFrame(counts).to_csv(output_path/'stratified_coverage.csv',index=False)
    (output_path/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    bindings=dict(inputs={str(input_path):_sha(input_path)},code={str(Path(__file__)):_sha(__file__),str(LINE/'tools/stage002_cohort_contract.py'):_sha(LINE/'tools/stage002_cohort_contract.py')},
                  outputs={p.name:_sha(p) for p in output_path.glob('*') if p.is_file()},floors=FLOORS)
    (output_path/'bindings.json').write_text(json.dumps(bindings,ensure_ascii=False,indent=2)+'\n')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,default=INPUT);parser.add_argument('--output',type=Path)
    args=parser.parse_args();print(json.dumps(run(args.input,args.output),ensure_ascii=False,indent=2))
