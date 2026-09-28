# PIT换月感知产品标签线

- line_id：`futures_trend_xgboost_pit_roll_aware_product_labels`
- 创建时间：2026-09-05 00:25 CST
- 研究对象：为保留线上逻辑回归、后续独立接入XGBoost建立可执行的产品级20日标签路径；主力换月时逐日使用同一合约计算收益，不把合约价差跳点当收益。
- 上游：关闭的日级Ranker V2只提供技术失败事实；数据输入只读复用V1无标签面板和PIT全市场source rebuild final。
- 当前状态：Stage001唯一入口因source manifest逻辑名/path格式与V1 filename-key verifier不兼容，在数据解析前预检失败并闭线；没有打开close、收益、标签或模型效果。
- 隔离边界：只写本线与`research/registry.md`；V1/V2 final、正式版本、生产、CTP和订单只读或禁止。

## 核心判断

- V2失败不是`sc2403`历史源缺失：该合约行情到2024-02-29，旧固定合约标签却要求到2024-03-08；PIT主力映射已在2024-02-08切到`sc2404`。
- 正式策略持有的是产品风险并会换月，固定合约跨完整20日并非稳定可执行目标。
- 新合同按前一已知交易日映射决定下一段持仓合约，每段只比较同一合约两个交易日价格；换月日在旧合约收盘退出、新合约收盘进入，后续标签阶段再单独定义成本。

## 当前阶段

- Stage000：`stages/20260905_0025_stage000_roll_aware_label_plan_preregistration.md`。
- Stage001计划：`plans/20260905_stage001_roll_aware_label_plan_qualification.md`。
- Stage001结果：`stages/20260905_0042_stage001_manifest_preflight_fail_close.md`；授权nonce已消费、final不存在，不重跑本线。

## 过拟合反思

- 当前判断：否，但研究序列适应风险存在。
- 原因：唯一入口停在manifest预检，没有解析研究表或观察效果；旧Ranker V2和本线均永久关闭。
- 边界：不得依据未来收益选择换月日、备用合约或标签窗口；任何规则都必须在close值访问前冻结。

## 继续价值反思

- 当前判断：本线无继续价值；仅允许另立V2修正manifest verifier。
- 原因：原资格问题尚未执行，但本线授权已消费；V2只能做接口兼容修复，不能改变数据或研究门槛。
