# Stage006 真实标签结束日修正报告

- 决策：`stage006_pit_corrected_confirmed_pass_development_only`
- 修正OOS月份：`49`
- 旧92日切分违规：`18`条 / `1`折
- 新PIT切分违规：`0`条 / `0`折
- 这些月份已被前序阶段自适应使用，因此只能称为开发时间外样本。

| 臂 | 双目标Rank IC均值 | 中位数 | Top10月均未来净利润 | 净利润10%分位 | Top10月均未来最大回撤 | 回撤10%分位 | 换入率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A_logistic | 0.056148 | 0.100155 | 43422.24 | -131975.00 | -169941.22 | -271486.00 | 23.3333% |
| B_ranker | 0.100250 | 0.055886 | 54949.49 | -110776.00 | -158636.33 | -216542.00 | 25.6250% |
| C_fusion | 0.096263 | 0.073996 | 51477.14 | -119838.00 | -163012.35 | -236105.00 | 25.6250% |
| C3_confirmed | 0.116418 | 0.134619 | 44613.57 | -114562.00 | -154402.14 | -236089.00 | 21.8750% |

## C3原11项门槛

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

## 边界

- 本阶段没有运行策略真引擎，代理收益和聚合路径回撤不是账户权益结论。
- 即使资格通过，也必须补充未触碰样本或新增前向shadow，才能讨论部署。
- 失败后不得修改模型参数、融合权重、确认月数、TopN或门槛救援。
