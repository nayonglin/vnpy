# Stage018 供需强逆风过滤真实引擎验证

- 研究线：`futures_trend_drawdown30_preserve_return`
- 时间：2026-05-25 20:17 CST
- 基准版本：`official_stage78_1_defensive_50w_no_sizing_cap`
- 阶段性质：A/C 真实引擎验证。
- 是否重要突破：否，但形成新的收益效率线索。

## 开始前反思

- 是否过拟合：否。原因是只把 Stage017 观察到的强逆风固定成 `<= -0.35` 禁止新增开仓，未调权重、未调品种、未按窗口救结果。
- 是否有价值继续：是。原因是 `C_pressure040` 距离目标只差约 `1.08pp`，供需过滤若能减少差开仓，可能在不破坏趋势结构的前提下改善路径。

## 本次变更

- 修改脚本：`examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 新增脚本：`examples/portfolio_backtesting/run_qmt_roll_stage318_supply_demand_headwind_engine_validation.py`
- 新增默认关闭参数：
  - `enable_supply_demand_headwind_filter`
  - `supply_demand_signal_path`
  - `supply_demand_headwind_threshold`
  - `supply_demand_headwind_weight_floor`
  - `supply_demand_headwind_max_age_days`
- 修改正式78-1默认路径：无。新增参数默认关闭，不影响正式基准。
- 删除参数：无。

## A/C 口径

- A：`A_baseline_78_1`
- C1：`C_pressure040`
- C2：`C_supply_headwind`
- C3：`C_pressure040_supply_headwind`
- 规则：供需方向分 `<= -0.35` 时新增开仓手数降为0。
- 账户资金：`500,000`
- 成本口径：沿用第78-1滑点口径，总手续费为0。

## 全样本结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 结论 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| A_baseline_78_1 | 25,542,885 | 5008.577% | -40.0607% | 1.1295 | 1,968,150 | 880 | 43.2432% | 基准 |
| C_pressure040 | 25,429,055 | 4985.811% | -31.0767% | 1.2650 | 2,047,490 | 862 | 45.0346% | 当前最强内部风控 |
| C_supply_headwind | 25,942,485 | 5088.497% | -40.0607% | 1.1943 | 1,489,100 | 774 | 44.1026% | 单独不降回撤 |
| C_pressure040_supply_headwind | 30,925,650 | 6085.130% | -31.0767% | 1.3663 | 1,556,750 | 757 | 45.3826% | 收益效率改善但未过30 |

## 多周期关键结果

- `since_2023`：C3 总收益 `694.350%`、最大回撤 `-24.9751%`、Sharpe `1.3796`
- `since_2024`：C3 总收益 `204.202%`、最大回撤 `-29.5488%`、Sharpe `0.9879`
- `phase_2024_2025`：C3 总收益 `244.120%`、最大回撤 `-27.6113%`、Sharpe `1.3135`
- `ytd_2026`：C3 总收益 `-14.782%`、最大回撤 `-28.4063%`、Sharpe `-1.0842`

## 结论

- C3 不通过硬目标：全样本最大回撤仍为 `-31.0767%`。
- 但 C3 全样本收益、Sharpe、滑点、交易次数均明显改善，是一个有价值的研究线索。
- 不能直接合入78-1；下一步先归因为什么 C3 仍卡在 `-31.0767%`。

## 结束后反思

- 是否过拟合：否。供需阈值冻结后验证，负面/正面结果都接受。
- 是否有价值继续：是。C3 的收益效率改善很明显，但必须解决全样本最差回撤来源，且不能用小数阈值救。

## 输出文件

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage318_supply_demand_headwind_engine_validation_report_stage318_supply_demand_headwind_engine_validation_v1.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage318_supply_demand_headwind_engine_validation_summary_stage318_supply_demand_headwind_engine_validation_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage318_supply_demand_headwind_engine_validation_comparison_stage318_supply_demand_headwind_engine_validation_v1.csv`

