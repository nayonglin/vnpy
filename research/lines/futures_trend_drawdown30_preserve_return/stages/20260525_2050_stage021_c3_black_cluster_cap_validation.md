# Stage021 C3叠加黑色建材簇上限验证

- 研究线：`futures_trend_drawdown30_preserve_return`
- 时间：2026-05-25 20:50 CST
- 基准版本：`official_stage78_1_defensive_50w_no_sizing_cap`
- 阶段性质：A/C 真实引擎验证。
- 是否重要突破：否。属于重要反证，避免把2021归因过拟合成永久限制。

## 开始前反思

- 是否过拟合：有风险，但可控。原因是黑色建材来自 Stage020 最差回撤归因；控制方式是只按宽产业簇测试 `35%/25%` 两个既有上限，不做单品种黑名单、不调入场阈值，并要求多窗口不过度伤收益。
- 是否有价值继续：是。若宽产业簇上限能过线，说明剩余回撤确实来自相关暴露；若不能，也能排除一条直觉上容易过拟合的路。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/run_qmt_roll_stage321_c3_black_cluster_cap_validation.py`
- 修改正式78-1参数：无。
- 新增正式参数：无。
- 删除参数：无。

## 结果

全样本：

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 结论 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| C_pressure040 | 25,429,055 | 4985.811% | -31.0767% | 1.2650 | 2,047,490 | 862 | 45.0346% | 对照 |
| C3_supply_headwind | 30,925,650 | 6085.130% | -31.0767% | 1.3663 | 1,556,750 | 757 | 45.3826% | C3对照 |
| C3_black_cluster_cap35 | 31,438,720 | 6187.744% | -33.7132% | 1.4220 | 1,687,040 | 777 | 45.5243% | 不通过 |
| C3_black_cluster_cap25 | 31,564,445 | 6212.889% | -31.3252% | 1.4472 | 1,748,440 | 768 | 46.2532% | 不通过 |

多周期关键结果：

- `since_2023`：cap35 总收益 `378.777%`，cap25 总收益 `315.757%`，均明显低于 C3 的 `694.350%`
- `since_2024`：cap35 总收益 `179.596%`，cap25 总收益 `113.072%`，均明显低于 C3 的 `204.202%`
- `phase_2024_2025`：cap35 总收益 `158.004%`，cap25 总收益 `140.436%`，均明显低于 C3 的 `244.120%`
- `ytd_2026`：与 C3 一致，未改善。

## 结论

- 黑色建材簇静态上限不能完成目标。
- 全样本收益虽然更高，但最大回撤仍未进30%，且 `since_2023/since_2024` 收益明显受损。
- 这说明不能把 2021 归因直接写成永久黑色建材限制；否则就是过拟合。

## 结束后反思

- 是否过拟合：本阶段验证本身不是过拟合；如果继续调 `30%/28%/32%` 去救结果，会过拟合。
- 是否有价值继续：有价值，但下一步应转向“条件触发的相关暴露冷却/拥挤状态”，即只有在簇内同步持仓、簇内近期亏损和账户回撤同时异常时限制新增风险，而不是永久压某个簇。

## 输出文件

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage321_c3_black_cluster_cap_validation_report_stage321_c3_black_cluster_cap_validation_v1.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage321_c3_black_cluster_cap_validation_summary_stage321_c3_black_cluster_cap_validation_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage321_c3_black_cluster_cap_validation_comparison_stage321_c3_black_cluster_cap_validation_v1.csv`

