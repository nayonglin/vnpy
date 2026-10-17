"""Fixed full-period screening decision; no tuning, engine or significance test."""
from pathlib import Path
import json
import math
import pandas as pd


def evaluate_metrics(a,c):
    required=['total_return_pct','max_dd_pct','sharpe','max_broker10_margin_to_equity_pct',
              'days_over_100pct','min_equity','days_equity_below_zero','total_trade_count']
    if any(k not in m or not math.isfinite(float(m[k])) for m in [a,c] for k in required):
        raise ValueError('missing or nonfinite required economic metric')
    gates=dict(higher_net_return=c['total_return_pct']>a['total_return_pct'],
        lower_drawdown=c['max_dd_pct']>a['max_dd_pct'],
        sharpe_not_lower=c['sharpe']>=a['sharpe'],
        margin_peak_not_worse=c['max_broker10_margin_to_equity_pct']<=a['max_broker10_margin_to_equity_pct'],
        margin_over100_days_not_worse=c['days_over_100pct']<=a['days_over_100pct'],
        candidate_survives=c['min_equity']>0 and c['days_equity_below_zero']==0,
        nonempty_candidate=c['total_trade_count']>0)
    passed=all(gates.values())
    return dict(gates=gates,fullperiod_screen_pass=passed,
        return_delta_percentage_points=c['total_return_pct']-a['total_return_pct'],
        drawdown_improvement_percentage_points=c['max_dd_pct']-a['max_dd_pct'],
        next_action='independent_review_then_fixed_multicycle' if passed else 'stop_first_screen_shape_no_parameter_rescue',
        promotion_allowed=False,production_qualified=False,
        scope='descriptive full-period offline screen; robustness and unseen-data advantage not established')


def main():
    root=Path(__file__).resolve().parents[1]/'outputs/stage001_first_screen'
    paths=json.loads((root/'completed_arm_paths.json').read_text()) if (root/'completed_arm_paths.json').exists() else {'A0':'A0','C0':'C0'}
    a=json.loads((root/paths['A0']/'metrics.json').read_text())
    c=json.loads((root/paths['C0']/'metrics.json').read_text())
    decision=evaluate_metrics(a,c)
    daily=[pd.read_csv(root/paths[arm]/'daily.csv',usecols=['date']) for arm in ['A0','C0']]
    if daily[0].date.tolist()!=daily[1].date.tolist():
        raise ValueError('arm calendars differ')
    decision['calendar_rows']=len(daily[0])
    rows=[]
    for arm,m in [('A0',a),('C0',c)]:
        rows.append(dict(arm=arm,**m))
    pd.DataFrame(rows).to_csv(root/'comparison.csv',index=False)
    (root/'decision.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(decision,ensure_ascii=False))


if __name__=='__main__':main()
