# Stage352 Stage526 20万资本参与率边界

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 14:24 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：部署资金层 A/C；不改 Stage526 alpha，不连接 CTP，不调用下单。
- 是否重要突破：是。20万小资金口径首次找到非 all-in 的硬闸门通过候选。
- 是否触发A/B：是。按 `skills/version-ab-experiment/SKILL.md`，部署层只做 A vs C。

## 外部调研与判断

- 参考资料：vn.py PortfolioStrategy 官方文档；vn.py RiskManager 官方文档。
- 我的判断：PortfolioStrategy 可以承载多合约组合，但 RiskManager 主要是委托前风控；20万账户的问题不是单个下单瞬间能否开仓，而是盈利复投后的 sizing 放大和次日权益路径风险。因此本阶段不继续扫保证金百分比，而测试粗粒度资本参与率。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage652_stage526_200k_capital_participation_frontier.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `sizing_equity_cap=200000`
  - `enable_dynamic_sizing_equity_soft_cap=True`
  - `dynamic_sizing_equity_soft_cap_base=200000`
  - `dynamic_sizing_equity_soft_cap_max=500000`
  - `dynamic_sizing_equity_soft_cap_participation=0.25/0.50`
  - `dynamic_sizing_equity_soft_cap_margin_start_ratio=10.0`
  - `dynamic_sizing_equity_soft_cap_margin_full_ratio=11.0`
  - `dynamic_sizing_equity_soft_cap_drawdown_start_ratio=10.0`
  - `dynamic_sizing_equity_soft_cap_drawdown_full_ratio=11.0`
- 修改参数：防守复验使用 `risk_multiplier=0.50`、`max_concurrent_positions=2`。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage526/Stage650 真实整数手日线重放区间。
- 账户规模：`200,000`。
- 成本口径：`1x/2x/3x` 滑点压力。
- 样本过滤：无日期、品种或坏窗口过滤。
- 策略/归因口径：
  - A：`stage526_200k_allin_r080_pc25_maxpos4`
  - C1：`stage526_200k_no_reinvest_cap200k_r080_pc25_maxpos4`
  - C2：`stage526_200k_profit25_cap500k_r080_pc25_maxpos4`
  - C3：`stage526_200k_profit50_cap500k_r080_pc25_maxpos4`
  - C4：`stage526_200k_defensive_r050_pc25_maxpos2`

## 结果

- 最优硬闸门候选：`stage526_200k_profit50_cap500k_r080_pc25_maxpos4`
- 期末权益：`1,466,985`
- 总收益：`633.4925%`
- 年化收益率：`37.0357%`
- 最大回撤：`-19.1790%`
- Sharpe：`1.4901`
- 总滑点：`66,270`
- 总交易次数：`538`
- 胜率：`50.7322%`
- 其他关键指标：
  - broker10 最大保证金/权益：`58.6659%`
  - 超100%保证金天数：`0`
  - 2x成本最大回撤：`-19.9556%`
  - 3x成本最大回撤：`-20.7678%`
  - 3x成本期末权益：`1,334,445`
  - 3x成本总收益：`567.2225%`

## 全部候选摘要

| 候选 | 期末权益 | 总收益 | 年化 | 最大回撤 | Sharpe | broker10峰值 | 3x成本回撤 | hard_pass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all-in原版 | `11,554,320` | `5677.1600%` | `89.9139%` | `-38.0459%` | `1.6639` | `120.0983%` | `-43.2876%` | `0` |
| 不复投cap20万 | `674,285` | `237.1425%` | `21.1871%` | `-17.9757%` | `1.2343` | `56.4791%` | `-20.0745%` | `1` |
| 利润25%参与cap50万 | `1,444,185` | `622.0925%` | `36.6967%` | `-19.7580%` | `1.5524` | `56.4791%` | `-22.2066%` | `1` |
| 利润50%参与cap50万 | `1,466,985` | `633.4925%` | `37.0357%` | `-19.1790%` | `1.4901` | `58.6659%` | `-20.7678%` | `1` |
| 防守r050/maxpos2 | `1,434,940` | `617.4700%` | `36.5580%` | `-24.2399%` | `1.2639` | `65.6421%` | `-26.6574%` | `1` |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage652_stage526_200k_capital_participation_frontier_report_stage652_stage526_200k_capital_participation_frontier_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage652_stage526_200k_capital_participation_frontier_summary_stage652_stage526_200k_capital_participation_frontier_v1.csv`
- orders：无订单输出；本阶段不连接交易接口。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage652_stage526_200k_capital_participation_frontier_daily_stage652_stage526_200k_capital_participation_frontier_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage652_stage526_200k_capital_participation_frontier_decision_stage652_stage526_200k_capital_participation_frontier_v1.json`

## 结论

- 本阶段结论：决策 `stage526_200k_capital_participation_hard_pass`。20万原版 all-in 仍不可实盘，但资本参与率能消除保证金穿线；最强粗档是 `利润50%参与 + sizing最高50万 + r080/pc25/maxpos4`。
- 是否进入下一步：是。
- 下一步：把 `profit50_cap500k` 当作 20万小资金执行候选做完整冷启动、分年/分季度、成本边界、控制组漂移、Stage526 live TCA 和真实券商保证金验收；在未补 TCA 前仍不能直接称为实盘批准。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但需要防止继续围绕 `25/50` 做小数优化。
- 原因：本阶段只测试粗粒度资金参与结构，不按历史日期、品种或坏窗口修补；结果显示 25%和50%两个粗档均通过，说明机制不是单点偶然。但继续扫 `30/40/60/70%` 或 `40/60万cap` 会开始滑向过拟合。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：用户真实资金约20万，本阶段给出了比防守降风险更接近 Stage526 原信号的可执行资金层候选；但后续价值在验收和执行证据，不在继续调资金参与小数。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，避免并行冲突；合入时统一整理。
- 是否更新 `research/registry.md`：暂不更新。
- 是否追加根目录 `memory.md/back_log.md`：是，追加重要摘要。
