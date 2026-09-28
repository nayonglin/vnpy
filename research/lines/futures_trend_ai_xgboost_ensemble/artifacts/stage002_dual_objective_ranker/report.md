# Stage002 收益/回撤双目标XGBRanker资格报告

- 决策：`stage002_dual_objective_ranker_fail_stop_no_backtest`
- 晋级臂：`无`
- OOS月份：`49`
- 路径净利润复算最大误差：`2.91e-11`
- 本阶段仍是预测资格赛，不是策略回测。

## A/B/C指标

| 臂 | 双目标Rank IC均值 | 中位数 | Top10月均未来净利润 | 净利润10%分位 | Top10月均未来最大回撤 | 回撤10%分位 | 换入率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A_logistic | 0.057798 | 0.147191 | 40787.76 | -131975.00 | -169782.04 | -271486.00 | 23.7500% |
| B_ranker | 0.094831 | 0.055886 | 56310.20 | -110776.00 | -158430.10 | -224084.00 | 27.0833% |
| C_fusion | 0.087715 | 0.032495 | 55028.06 | -119838.00 | -161254.08 | -236105.00 | 26.2500% |

## B_ranker相对A门槛

- `PASS` `identity_path_and_determinism`
- `PASS` `oos_months_ge_45`
- `PASS` `mean_dual_rank_ic_strictly_better`
- `FAIL` `median_dual_rank_ic_noninferior`
- `PASS` `top10_mean_future_pnl_strictly_better`
- `PASS` `top10_p10_future_pnl_noninferior`
- `PASS` `top10_mean_future_drawdown_strictly_better`
- `PASS` `top10_p10_future_drawdown_noninferior`
- `FAIL` `top10_turnover_le_105pct`
- `PASS` `yearly_dual_rank_ic_wins_ge_3`
- `FAIL` `worst_year_dual_rank_ic_delta_ge_minus_003`

## C_fusion相对A门槛

- `PASS` `identity_path_and_determinism`
- `PASS` `oos_months_ge_45`
- `PASS` `mean_dual_rank_ic_strictly_better`
- `FAIL` `median_dual_rank_ic_noninferior`
- `PASS` `top10_mean_future_pnl_strictly_better`
- `PASS` `top10_p10_future_pnl_noninferior`
- `PASS` `top10_mean_future_drawdown_strictly_better`
- `PASS` `top10_p10_future_drawdown_noninferior`
- `FAIL` `top10_turnover_le_105pct`
- `PASS` `yearly_dual_rank_ic_wins_ge_3`
- `PASS` `worst_year_dual_rank_ic_delta_ge_minus_003`

## 边界

- 聚合路径来自现有单品种策略每日净利润求和，是进入真引擎前的资格代理。
- 固定fu、保证金竞争、相关性门、整数手和实际交易成本只能由后续真引擎确认。
- 资格失败不得通过修改双目标权重、rank参数或TopN救援。
