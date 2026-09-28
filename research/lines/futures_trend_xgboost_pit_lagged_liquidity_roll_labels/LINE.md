# PIT滞后流动性动态换约标签线

- line_id：`futures_trend_xgboost_pit_lagged_liquidity_roll_labels`
- 创建时间：2026-09-05 02:03 CST
- 上游：冻结候选窗口来自已验证的`futures_trend_xgboost_pit_expiry_safe_roll_mapping`；已失败闭线的`futures_trend_xgboost_pit_query_date_fixed_contract_labels`只提供机制证据。
- 研究问题：能否只使用每个执行日前一全市场交易日可见的实际合约流动性，在20日标签窗内因果地动态换约，并形成全量可交易路径。
- 当前状态：Stage001唯一全量资格执行已失败闭线；严格滞后、候选宽度和单向到期规则通过，但后续映射、端点质量及换出容量门失败，不生成标签值、不训练XGBoost。
- 隔离边界：只写本线与registry；不修改任何上游研究线、正式逻辑回归、CTP、订单或生产文件。

## 当前阶段

- Stage000：`stages/20260905_0203_stage000_lagged_liquidity_roll_preregistration.md`。
- Stage001计划：`plans/20260905_stage001_lagged_liquidity_roll_qualification.md`。
- Stage001结果：`stages/20260905_0223_stage001_lagged_liquidity_roll_fail_close.md`。
- 冻结结果：leg1保留`54,876/56,272`条路径，最终合格`54,086`；`463`条路径映射缺失，完整路径另有`37`条价格失败、`314`条容量失败；产物`10/10`、输入`6/6`、错误`0`。

## 过拟合反思

- 当前判断：本次否；结果后救参风险高。
- 原因：唯一执行前已冻结上一交易日信息集、实际合约到期约束和既有最小1手容量门；不使用失败品种、年份或未来执行结果选择合约。
- 边界：禁止看到结果后修改100/100、30个候选、排序、20日持有期、产品、年份或单向到期规则。

## 继续价值反思

- 当前判断：本线无，XGBoost总目标仍有。
- 原因：动态机制虽比固定合约多形成`3,396`条合格路径，但未达到全量硬门；本线不得调参或重跑。若继续，只能另立query-date以前历史可成交性资格线，以统一事前规则剔除不能穿越完整标签窗的产品，仍不触碰收益。
