# Stage019 C3叠加统一风险预算缩放验证

- 研究线：`futures_trend_drawdown30_preserve_return`
- 时间：2026-05-25 20:32 CST
- 基准版本：`official_stage78_1_defensive_50w_no_sizing_cap`
- 阶段性质：A/C 风险预算边界验证。
- 是否重要突破：否。属于重要反证。

## 开始前反思

- 是否过拟合：否。只测试预设的账户级风险预算缩放 `0.95/0.90`，不是连续搜索小数。
- 是否有价值继续：是。C3 卡在 `-31.0767%`，理论上小幅统一降风险可能把它压进30以内，同时保留大部分收益。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/run_qmt_roll_stage319_supply_headwind_risk_scale_validation.py`
- 修改正式78-1参数：无。
- 新增正式参数：无。
- 删除参数：无。

## 结果

全样本：

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 结论 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| C_pressure040 | 25,429,055 | 4985.811% | -31.0767% | 1.2650 | 2,047,490 | 862 | 45.0346% | 对照 |
| C3_supply_headwind | 30,925,650 | 6085.130% | -31.0767% | 1.3663 | 1,556,750 | 757 | 45.3826% | C3对照 |
| C3_supply_headwind_risk095 | 25,808,970 | 5061.794% | -31.5110% | 1.3120 | 1,339,950 | 762 | 45.0262% | 不通过 |
| C3_supply_headwind_risk090 | 13,119,635 | 2523.927% | -37.6010% | 1.1332 | 766,260 | 745 | 43.4316% | 不通过 |

多周期补充：

- `risk095` 在 `since_2023` 最大回撤 `-25.3319%`，但全样本恶化；`since_2024` 最大回撤 `-30.2962%`，未过30。
- `risk090` 在 `since_2024` 最大回撤 `-27.2694%`，但全样本最大回撤恶化到 `-37.6010%`，收益也大幅下降。

## 结论

- 统一降低风险预算不是答案。
- 手数取整、仓位触发路径和复利高水位改变后，风险缩放并不会线性降低最大回撤。
- 不继续扫 `0.92/0.93/0.94` 这类小数，否则过拟合风险很高。

## 结束后反思

- 是否过拟合：否。本阶段接受了反直觉负结果，没有继续救参数。
- 是否有价值继续：是，但方向应改为最差回撤归因，找结构来源。

## 输出文件

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage319_supply_headwind_risk_scale_validation_report_stage319_supply_headwind_risk_scale_validation_v1.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage319_supply_headwind_risk_scale_validation_summary_stage319_supply_headwind_risk_scale_validation_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage319_supply_headwind_risk_scale_validation_comparison_stage319_supply_headwind_risk_scale_validation_v1.csv`

