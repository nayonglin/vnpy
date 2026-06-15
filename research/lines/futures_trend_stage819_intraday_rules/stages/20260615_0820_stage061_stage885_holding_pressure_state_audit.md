# Stage061 Stage885 持仓压力状态只读审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 08:20 CST`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage884 后续全路径持仓压力状态只读审计；不新增交易规则、不改官方正式版、不改官方候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否。属于风险标签边界确认，不是可推广策略突破。
- 是否触发正式 A/B：否。Stage885 只读，不进入正式候选、不写根目录 `back_log.md`。
- 决策：`stage885_pressure_state_real_but_not_trade_rule_mixed_outcomes`

## 外部调研与判断

- vn.py/VeighNa 官方项目定位支持组合策略回测与实盘框架；本阶段继续用组合路径审计，而不是单笔收益代理。
- CME margin / open-interest 资料提示，敞口、流动性和保证金要在组合层判断，不能只看单笔交易。
- 趋势跟随 pyramiding 资料强调 portfolio heat 和仓位集中度是硬约束；“盈利后加仓”本身并不能证明组合风险可生存。
- Backtrader 成交语义资料继续支持本线纪律：后续收益/回撤只能用于只读归因，不能作为实时规则条件。
- 我的判断：Stage884 已证明 C17 是持仓保证金分子扩张；Stage885 先检查是否存在低自由度、实时可观测的 holding pressure state。结果显示它是真风险标签，但不是直接退出/减仓规则。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage885_stage884_holding_pressure_state_audit.py`
- 新增输出前缀：`qmt_roll_stage885_stage884_holding_pressure_state_audit_*`
- 新增交易规则：无。
- 新增参数：无交易参数；新增只读状态定义：
  - `ACCOUNT_HEAT_WATCH_PCT = 80.0`
  - `ACCOUNT_HEAT_DANGER_PCT = 100.0`
  - `TOP1_PRODUCT_DIRECTION_WATCH_PCT = 35.0`
  - `TOP3_PRODUCT_DIRECTION_SHARE_WATCH = 0.70`
  - `holding_pressure_state = account_heat_watch and top1_product_direction_watch and top3_cluster_watch`
- 修改参数：无官方配置修改；C4/C9/C17 均保持原始输出。
- 删除参数：无。
- 输入修正：C4/C9 closed lots 读取 Stage863，C17 closed lots 读取 Stage883，避免把 Stage883 仅含 C17 明细误当作 C9/C4 无持仓。

## 回测与审计参数

- 数据区间：沿用 Stage883 / Stage863 全周期 `2018-01-01 -> 2026-05-29`。
- 上游候选：`official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1`
- 账户规模：`300000`
- 分钟数据：Stage861 full minute bars，加载 `1,479,592` 根、`216` 个合约。
- 输入：
  - curve：Stage883 C4/C9/C17 curve
  - C4/C9 closed lots：Stage863 closed lots
  - C17 closed lots：Stage883 closed lots
- 后续 `next5/next20 return` 与 `future20_min_return` 只用于只读归因，不参与状态定义。
- 不扫描 broker 阈值、top1 阈值、top3 share、品种、方向、年份或分钟窗口。

## 源结果复述

### C17 结果

- 期末权益：`51,683,814.65`
- 总收益：`17,127.9382%`
- 最大回撤：`-41.1625%`
- Sharpe：`1.6223`
- 总滑点：`3,921,000`
- 总交易次数：`1,051`
- 胜率：`53.4863%`
- max broker10 margin/equity：`127.4316%`
- p95 broker10 margin/equity：`63.7936%`

## 新增审计结果

### 压力状态分桶

- C4 pressure state：`21` 天，覆盖 `3` 年；median broker10 `91.7641%`，max broker10 `111.4255%`；median next20 return `12.6588%`，negative next20 share `33.3333%`，worst future20 min return `-26.5666%`。
- C9 pressure state：`22` 天，覆盖 `3` 年；median broker10 `91.8452%`，max broker10 `114.3987%`；median next20 return `10.8325%`，negative next20 share `31.8182%`，worst future20 min return `-18.9546%`。
- C17 pressure state：`25` 天，覆盖 `5` 年；median broker10 `91.1489%`，max broker10 `127.4316%`；median next20 return `16.9511%`，negative next20 share `8.0000%`，worst future20 min return `-17.3744%`。
- C17-only pressure days：`9` 天。

### C17-only 重点日期

- `2020-10-23`：C17 broker10 `83.3732%`，C9 `0.0000%`，C17 next20 return `55.9349%`，future20 min return `8.8130%`。
- `2020-10-15`：C17 `127.4316%`，C9 `78.3721%`，C17 next20 return `69.3620%`，future20 min return `14.2370%`。
- `2019-12-23`：C17 `88.7827%`，C9 `47.3272%`，C17 next20 return `10.2174%`，future20 min return `-1.8583%`。
- `2020-10-16`：C17 `113.0928%`，C9 `76.4447%`，C17 next20 return `49.6384%`，future20 min return `10.6054%`。
- `2023-11-10`：C17 `91.0666%`，C9 `88.4489%`，C17 next20 return `-3.3567%`，future20 min return `-4.9271%`。
- 判断：9 个 C17-only pressure 日期中，多数后续为正；只有少数负样本，不能把 pressure state 直接改成退出或减仓规则。

### 产品方向压力

- C17 top product-direction pressure 包括 `CF.CZCE short`、`rb.SHFE long`、`lh.DCE short`、`cu.SHFE long`、`jm.DCE long` 等，分散在多个年份和方向。
- 这说明压力状态确实是组合层集中度标签，不是单一品种黑名单证据。

## 视觉复核

- summary chart 非空：C17 broker10 和 top1 product-direction 压力在少数时期明显上穿 `80%` account heat，但散点图颜色显示这些压力点并不集中在后续亏损区域。
- bucket 图非空：C9 pressure 和 C17 pressure 的 median next20 return 均为正；C17 pressure 的 negative next20 share 只有 `8%`。
- atlas page001 非空：展示 `AP.CZCE short`、`OI.CZCE long` 等压力日期的分钟K路径；这些样本更多是持仓中压力，而非可直接用分钟K判断“应该退出”的单根信号。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage885_stage884_holding_pressure_state_audit_report_stage885_stage884_holding_pressure_state_audit_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage885_stage884_holding_pressure_state_audit_decision_stage885_stage884_holding_pressure_state_audit_v1.json`
- daily state：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage885_stage884_holding_pressure_state_audit_daily_state_stage885_stage884_holding_pressure_state_audit_v1.csv`
- product-direction daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage885_stage884_holding_pressure_state_audit_product_direction_daily_stage885_stage884_holding_pressure_state_audit_v1.csv`
- pressure bucket：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage885_stage884_holding_pressure_state_audit_pressure_bucket_stage885_stage884_holding_pressure_state_audit_v1.csv`
- C17/C9 delta：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage885_stage884_holding_pressure_state_audit_c17_c9_delta_stage885_stage884_holding_pressure_state_audit_v1.csv`
- summary chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage885_stage884_holding_pressure_state_audit_summary_chart_stage885_stage884_holding_pressure_state_audit_v1.png`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage885_stage884_holding_pressure_state_audit_atlas_page001_stage885_stage884_holding_pressure_state_audit_v1.png` 至 `page004`

## 结论

- Holding pressure state 是真实风险标签：它能定位 C17 broker10 与产品方向集中暴露的高压段。
- Holding pressure state 不是交易规则：C4/C9/C17 的 pressure state 后续 20 日中位收益均为正，C17 pressure 的负收益占比仅 `8%`。直接“高压就退出/减仓”会砍掉右尾。
- 不进入引擎、不触发 A/B、不做阈值救参。后续如果继续，只能把 pressure state 当复盘定位标签，进一步寻找“高压下失败前的分钟级结构破坏”，而不是对所有高压一刀切。

## 过拟合反思

- 运行前判断：否。本阶段不是按峰值日期/品种写规则，而是用预声明的账户 heat、top1 产品方向、top3 集中度做只读分桶。
- 运行后判断：否，但若继续扫描 `75/85/90` broker 阈值、`30/40/50` top1 阈值、top3 share 或按品种过滤，就会过拟合。当前证据已经说明压力标签本身不能直接交易化。

## 继续价值反思

- 运行前判断：有价值。Stage884 只证明 C17 是分子扩张，还需要判断这种分子扩张能否抽象成实时风控状态。
- 运行后判断：Stage885 作为归因有价值；作为直接规则没有继续价值。继续方向只能是更细的只读复盘：在 pressure state 内寻找真正的分钟级失败结构，例如高压下不再创新高/低、反向放量、OI 逆向且回撤无法恢复等，但必须先只读，不得扫阈值。
