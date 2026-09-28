# PIT打分日固定实际合约标签线

- line_id：`futures_trend_xgboost_pit_query_date_fixed_contract_labels`
- 创建时间：2026-09-05 01:42 CST
- 上游：已失败闭线的`futures_trend_xgboost_pit_roll_label_tradeability`只提供问题证据；冻结候选窗口来自已验证的`futures_trend_xgboost_pit_expiry_safe_roll_mapping`。
- 研究问题：能否在query date只用当时可见合约链、到期日和历史流动性，选定一个覆盖完整20日标签窗的真实合约，并在不换月的前提下形成全量可交易标签路径。
- 当前状态：Stage001唯一全量资格执行已失败闭线；候选宽度、因果选择和到期门通过，但固定合约未来价格质量与入场/退出容量门失败，不生成标签值、不训练XGBoost。
- 隔离边界：只写本线与registry；不修改任何上游研究线、正式逻辑回归、CTP、订单或生产文件。

## 当前阶段

- Stage000：`stages/20260905_0142_stage000_query_date_fixed_contract_preregistration.md`。
- Stage001计划：`plans/20260905_stage001_query_date_fixed_contract_qualification.md`。
- Stage001结果：`stages/20260905_0156_stage001_query_date_fixed_contract_fail_close.md`。
- 冻结结果：成功选约`54,305/56,272`路径、每qid候选最小/中位/最大`48/51/58`；未来合格`50,690`、失败`3,615`；产物`11/11`、输入`6/6`、错误`0`。

## 过拟合反思

- 当前判断：否。
- 原因：规则由20日标签持有期、既有90%历史覆盖门、最小1手1%容量门和合约到期约束直接推出；不按上一线失败产品名单删除样本。
- 边界：禁止看到结果后修改18/20、100/100、30个候选、排序、持有期、产品或年份。

## 继续价值反思

- 当前判断：本线无，XGBoost总目标仍有。
- 原因：失败集中在退出端和持有后半段，说明固定20日持有无法穿越流动性迁移；后续仅值得另立严格滞后一日的动态换约资格线，不能在本线改远月或调阈值。
