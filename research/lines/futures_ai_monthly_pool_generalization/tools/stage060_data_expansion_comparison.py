"""Paired old/new predictions under one expanded identification set and full N."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from stage047_learnability import pair_bounds

KEYS=['eval_date','product_vt_symbol']


def compare_predictions(old,new,targets):
    old=old.copy();new=new.copy();targets=targets.copy()
    for frame in [old,new,targets]:
        frame['eval_date']=pd.to_datetime(frame.eval_date,errors='raise')
        if frame.duplicated(KEYS).any():raise ValueError('duplicate_product_date')
    combined=old[KEYS+['expanded_probability']].merge(new[KEYS+['expanded_probability']],on=KEYS,
                how='outer',suffixes=('_old','_new'),validate='one_to_one',indicator=True)
    if not combined._merge.eq('both').all():raise ValueError('prediction_universes_differ')
    combined=combined.drop(columns='_merge')
    expected=targets[targets.eval_date.isin(combined.eval_date)]
    if 'asof_member' in expected:expected=expected[expected.asof_member]
    if set(map(tuple,expected[KEYS].to_numpy()))!=set(map(tuple,combined[KEYS].to_numpy())):
        raise ValueError('full_asof_universe_not_preserved')
    combined=combined.merge(expected[KEYS+['robust_target','maturity_clock_reached']],on=KEYS,validate='one_to_one')
    rows=[]
    for day,g in combined.groupby('eval_date',sort=True):
        y=pd.to_numeric(g.robust_target,errors='raise').to_numpy(float)
        record=dict(eval_date=str(day.date()),year=day.year,N=len(g),known=int(np.isfinite(y).sum()),
                    mature=bool(g.maturity_clock_reached.all()))
        for metric in ['brier','logloss','error']:
            lo,hi=pair_bounds(y,g.expanded_probability_new.to_numpy(float),g.expanded_probability_old.to_numpy(float),metric)
            record[metric+'_improvement_lower']=float(lo.mean());record[metric+'_improvement_upper']=float(hi.mean())
            record[metric+'_known_only_improvement']=None if not np.isfinite(y).any() else float(lo[np.isfinite(y)].mean())
        rows.append(record)
    return combined,pd.DataFrame(rows)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(old_path,new_path,target_path,output):
    if output.exists():raise ValueError('immutable_output_exists')
    for path in [old_path,new_path]:
        manifest=json.loads((path.parent/'local_reproducibility_manifest.json').read_text())
        declared=[r for r in manifest['assets'] if Path(r['path']).resolve()==path.resolve()]
        if len(declared)!=1 or sha(path)!=declared[0]['sha256']:raise ValueError('prediction_run_manifest_drift')
    data,monthly=compare_predictions(pd.read_csv(old_path),pd.read_csv(new_path),pd.read_csv(target_path))
    annual=[]
    for year,g in monthly.groupby('year',sort=True):
        mature=g[g.mature];row=dict(year=int(year),months=len(g),mature_months=len(mature),N=int(g.N.sum()),known=int(g.known.sum()))
        for col in g:
            if col.endswith(('_lower','_upper','_improvement')):
                row[col]=None if mature.empty or not mature[col].notna().any() else float(mature[col].mean())
        annual.append(row)
    output.mkdir(parents=True);data.to_csv(output/'paired_all_asof_predictions.csv',index=False)
    monthly.to_csv(output/'monthly_paired_loss_bounds.csv',index=False)
    pd.DataFrame(annual).to_csv(output/'annual_paired_loss_bounds.csv',index=False)
    summary=dict(issued_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),rows=len(data),months=len(monthly),
                 common_new_identification_set=True,unknown_labels_retained=True,improvement='old_prediction_loss_minus_new_prediction_loss',
                 robust_brier_improvement_years=[r['year'] for r in annual if r['brier_improvement_lower'] is not None and r['brier_improvement_lower']>0],
                 formal_AC_run=False,usable_for_trading=False,
                 interpretation='historical source evidence expansion diagnostic; no calibrated probability or financial performance claim')
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    assets=[dict(path=str(output/name),sha256=sha(output/name),reproducibility_required=True,
                 asset_class=kind,usable_for_trading=False) for name,kind in [
                    ('paired_all_asof_predictions.csv','decision_asset'),('monthly_paired_loss_bounds.csv','qualification_evidence'),
                    ('annual_paired_loss_bounds.csv','qualification_evidence'),('summary.json','qualification_evidence')]]
    manifest=dict(inputs={str(p):sha(p) for p in [old_path,new_path,target_path]},code={str(Path(__file__)):sha(__file__)},assets=assets,
                  production_or_official_release=False,git_staged=False)
    (output/'local_comparison_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ['old_path','new_path','target_path','output']:parser.add_argument('--'+name.replace('_','-'),type=Path,required=True)
    print(json.dumps(run(**vars(parser.parse_args())),ensure_ascii=False,indent=2))
