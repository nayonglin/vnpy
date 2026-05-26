# Stage034 C3 波动预算真实引擎验证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 01:38 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：真实引擎验证 / 反证
- 是否重要突破：否，但属于重要反证
- 是否触发A/B：是；因 Stage033 出现可能接入正式版本的候选，已按 `version-ab-experiment` 做隔离验证

## 外部调研与判断

- 参考资料：
  - Moskowitz, Ooi, Pedersen, `Time Series Momentum`：趋势组合常用跨资产波动率和组合风险预算，但必须落到可交易仓位。
  - Moreira and Muir, `Volatility-Managed Portfolios`：波动率管理有理论依据，但日收益层缩放不能直接等价为真实成交规则。
- 我的判断：
  - 波动预算不是拍脑袋补丁，有经济含义；但第78-1的收益来自少数趋势加速段，若在高波动段机械减掉已有仓位，可能同时砍掉利润腿。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/run_qmt_roll_stage334_c3_volatility_budget_engine_validation.py`
- 修改脚本：`examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 删除脚本：无
- 新增参数：
  - `enable_portfolio_volatility_budget`
  - `portfolio_volatility_budget_lookback`
  - `portfolio_volatility_budget_target_annual_vol`
  - `portfolio_volatility_budget_min_scale`
  - `portfolio_volatility_budget_entry_contexts`
  - `enable_portfolio_volatility_budget_deleverage`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-01 至 2026-04-30
- 账户规模：500,000
- 成本口径：沿用 C3 / Stage78-1 真实引擎口径，含滑点，佣金为 0
- 样本过滤：不新增品种过滤；仅验证 Stage033 预声明的三个粗档位
- 策略/归因口径：`C3_supply_headwind` 底座 + 组合层波动预算，作用于开仓、加仓、换月重开和已有持仓缩放

## 结果

### A：C3 原始

- 期末权益：30,925,650
- 总收益：6,085.1300%
- 最大回撤：-31.0767%
- Sharpe：1.3663
- 总滑点：1,556,750
- 总交易次数：757
- 胜率：45.3826%

### C：20日波动预算70%

- 期末权益：7,125,655
- 总收益：1,325.1310%
- 收益保留：21.7765%
- 最大回撤：-38.3072%
- Sharpe：0.9413
- 总滑点：737,680
- 总交易次数：854
- 胜率：51.9833%
- 已有持仓缩放次数：103
- 平均 scale：0.9769
- 最低 scale：0.5969

### C：60日波动预算60%

- 期末权益：4,981,835
- 总收益：896.3670%
- 收益保留：14.7304%
- 最大回撤：-38.3679%
- Sharpe：0.8305
- 总滑点：561,700
- 总交易次数：819
- 胜率：51.9912%
- 已有持仓缩放次数：86
- 平均 scale：0.9801
- 最低 scale：0.7252

### C：60日波动预算70%

- 期末权益：7,591,400
- 总收益：1,418.2800%
- 收益保留：23.3073%
- 最大回撤：-42.4966%
- Sharpe：0.9201
- 总滑点：558,170
- 总交易次数：796
- 胜率：49.4172%
- 已有持仓缩放次数：64
- 平均 scale：0.9849
- 最低 scale：0.7359

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage334_c3_volatility_budget_engine_validation_report_stage334_c3_volatility_budget_engine_validation_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage334_c3_volatility_budget_engine_validation_summary_stage334_c3_volatility_budget_engine_validation_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage334_c3_volatility_budget_engine_validation_comparison_stage334_c3_volatility_budget_engine_validation_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage334_c3_volatility_budget_engine_validation_daily_stage334_c3_volatility_budget_engine_validation_v1.csv`
- scale_history：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage334_c3_volatility_budget_engine_validation_scale_history_stage334_c3_volatility_budget_engine_validation_v1.csv`
- trade_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage334_c3_volatility_budget_engine_validation_trade_events_stage334_c3_volatility_budget_engine_validation_v1.csv`

## 结论

- 本阶段结论：真实引擎全样本失败。三个 Stage033 日收益层候选全部没有同时满足“最大回撤30以内”和“C3收益保留80%以上”，并且最大回撤反而恶化到 `-38.3072%` 到 `-42.4966%`。
- 关键原因：日收益层缩放假设可以每天连续调整组合净值；真实引擎里已有仓位缩放是实际平仓。scale 恢复后不会自动恢复原始仓位，因此在趋势加速段减掉利润腿，同时没有有效消除后续深回撤。
- 是否进入下一步：进入机制消融诊断，但不继续围绕 `55日/0.67` 这类小数调参。
- 下一步：只做低自由度机制消融，区分“新开仓缩放失败”与“已有仓位平掉后无法恢复”两个来源；若仍失败，停止当前波动预算形状。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：继续扫参数会过拟合。
- 原因：本阶段只验证 Stage033 预声明的三个粗档位，没有用结果反向挑小数；但真实引擎已经把形状反证，继续调 lookback/target 小数是在救历史。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：机制消融仍有价值，但候选本身暂不可继续推广。
- 原因：失败不是单纯数字差一点，而是暴露调整机制和日收益层假设不一致。需要确认是否应彻底停止波动预算，还是仅停止“已有仓位强平式缩放”。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，作为 Stage033 强线索被真实引擎反证的重要记录。
