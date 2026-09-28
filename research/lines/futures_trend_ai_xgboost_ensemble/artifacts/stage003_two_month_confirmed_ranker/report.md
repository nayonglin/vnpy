# Stage003 两月确认XGBoost月池资格报告

- 决策：`stage003_two_month_confirmed_pass_allow_true_engine`
- OOS月份：`49`
- 平均确认品种数：`7.2245`

| 指标 | A逻辑回归 | C3两月确认 |
| --- | ---: | ---: |
| 双目标Rank IC均值 | 0.057940 | 0.122840 |
| 双目标Rank IC中位数 | 0.147191 | 0.177647 |
| Top10月均未来净利润 | 40787.76 | 55690.10 |
| Top10净利润10%分位 | -131975.00 | -112914.00 |
| Top10月均未来最大回撤 | -169782.04 | -155874.18 |
| Top10回撤10%分位 | -271486.00 | -236089.00 |
| Top10换入率 | 23.7500% | 21.8750% |

## 预声明门槛

- `PASS` `identity_path_and_determinism`
- `PASS` `oos_months_ge_45`
- `PASS` `mean_dual_rank_ic_strictly_better`
- `PASS` `median_dual_rank_ic_noninferior`
- `PASS` `top10_mean_future_pnl_strictly_better`
- `PASS` `top10_p10_future_pnl_noninferior`
- `PASS` `top10_mean_future_drawdown_strictly_better`
- `PASS` `top10_p10_future_drawdown_noninferior`
- `PASS` `top10_turnover_le_105pct`
- `PASS` `yearly_dual_rank_ic_wins_ge_3`
- `PASS` `worst_year_dual_rank_ic_delta_ge_minus_003`

- 资格通过才允许进入真引擎；失败不得修改确认月数或填充规则。
- 本阶段没有运行策略回测，不产生实际权益、最大回撤或Sharpe。
