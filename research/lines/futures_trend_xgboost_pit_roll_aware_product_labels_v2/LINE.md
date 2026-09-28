# PIT换月感知产品标签V2线

- line_id：`futures_trend_xgboost_pit_roll_aware_product_labels_v2`
- 创建时间：2026-09-05 00:43 CST
- 上游：关闭的`futures_trend_xgboost_pit_roll_aware_product_labels`，其唯一入口只在source manifest预检失败，未解析研究表。
- 唯一合同差异：source rebuild manifest按逻辑key下entry的`path/size/sha256`验证，不再错误地把逻辑key当文件名。
- 完全不变：57,528基础行、56,272候选行、1,046 qid、20段、T-1映射、bar存在、`sc` canary、零价格/标签/模型/回测/生产副作用门。
- 当前状态：Stage001唯一执行已失败闭线；manifest适配通过，但2个独立到期边界造成6条`return_bar_missing`，不得重跑或删除失败样本。
- 隔离边界：只写本线与registry；V1原线、日级Ranker V1/V2、正式版本、CTP和订单均只读或禁止。

## 当前阶段

- Stage000：`stages/20260905_0043_stage000_v2_source_manifest_verifier_preregistration.md`。
- Stage001计划：`plans/20260905_stage001_v2_roll_aware_label_plan.md`。
- Stage001授权：`stages/20260905_stage001_v2_execution_authorization.json`，nonce已消费。
- Stage001结果：`stages/20260905_0052_stage001_v2_roll_aware_label_plan_fail_close.md`。
- 冻结产物：`artifacts/stage001_v2_roll_aware_label_plan/`，`--verify-only`为9个artifact、7个输入、0错误。

## 过拟合反思

- 当前判断：否。
- 原因：修正只处理两种manifest序列化契约，没有打开价格、标签或效果，也不改变任何研究样本和规则。
- 边界：V2不得把技术修复扩展成数据删选、fallback、缩窗或模型调整。

## 结果

- 56,272条路径、1,125,440段、29,361次换月中，56,266条完整，6条失败。
- 失败归并为2个到期事件：`wr2310.SHFE`到期日2023-10-16、`RS511.CZCE`到期日2025-11-14；对应下一交易日均无bar。
- `sc` canary、输入身份、分区、manifest与零副作用门通过；完整路径、PIT映射与bar存在门失败。
- 决策：`stage001_v2_roll_aware_label_plan_fail_close_no_labels`；close、收益、标签、模型、回测、CTP、订单和生产写入均为0。

## 继续价值反思

- 当前判断：本线无，结构性到期资格研究另立线才有。
- 原因：本线唯一命题已被6条失败直接证伪；`expire_date`可完整解释两个独立事件，继续方向应是事前生命周期门，而不是放宽本线合同。
