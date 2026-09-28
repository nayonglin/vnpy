# Stage001 XGBoost融合预测资格报告

- 决策：`stage001_prediction_qualification_fail_stop_no_backtest`
- OOS月份：`49`
- 训练面板：`1368`行 / `76`个月 / `108`项特征
- 标签隔离：`92`自然日
- 本阶段不是策略回测，不产生期末权益、收益率、最大回撤或Sharpe结论。

## A/B/C结果

| 臂 | 月均Rank IC | Rank IC中位数 | Top10月均未来净利润合计 | Top10未来净利润10%分位 | Top10上半区命中率 | Top10换入率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A_logistic | -0.014834 | -0.021672 | 40787.76 | -131975.00 | 50.6122% | 23.7500% |
| B_xgboost | 0.019570 | 0.021762 | 41049.49 | -120906.00 | 52.8571% | 21.4583% |
| C_fusion | 0.006375 | -0.018520 | 33457.86 | -136702.00 | 52.0408% | 22.7083% |

## 预声明门槛

- `PASS` `identity_and_determinism`
- `PASS` `oos_months_ge_45`
- `PASS` `mean_rank_ic_strictly_better`
- `PASS` `median_rank_ic_noninferior`
- `FAIL` `top10_mean_future_pnl_strictly_better`
- `FAIL` `top10_p10_future_pnl_noninferior`
- `PASS` `top10_top_half_rate_noninferior`
- `PASS` `top10_turnover_le_105pct`
- `PASS` `yearly_rank_ic_wins_ge_3`
- `FAIL` `worst_year_rank_ic_delta_ge_minus_003`

## 解释边界

- 未来净利润来自现有单品种策略标签，只是组合收益代理，不含真实Top10组合的资金、保证金、相关性和执行路径。
- 尾部10%分位只是回撤代理，不能替代真引擎最大回撤。
- 只有全部资格门通过，才允许进入Stage002 A/C策略回测。
