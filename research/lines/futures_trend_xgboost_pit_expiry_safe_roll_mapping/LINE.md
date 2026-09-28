# PIT到期安全换月映射资格线

- line_id：`futures_trend_xgboost_pit_expiry_safe_roll_mapping`
- 创建时间：2026-09-05 00:57 CST
- 上游：已失败关闭的`futures_trend_xgboost_pit_roll_aware_product_labels_v2`。
- 研究问题：能否仅用映射日可见流动性和事前已知`expire_date`，为下一return date选择仍可交易的合约，从结构上消除到期边界，而不读取未来映射、未来bar存在或close值来选约。
- 当前状态：Stage001唯一执行通过并封存；56,272条路径和1,125,440个leg全部完整，6个leg/2个到期事件完成fallback，但`RS607`选择日成交量为0，标签值生成暂缓。
- 隔离边界：只写本线与registry；V1/V2标签线、日级Ranker、正式逻辑回归、CTP、订单和生产文件均不改。

## 当前阶段

- Stage000：`stages/20260905_0057_stage000_expiry_safe_roll_mapping_preregistration.md`。
- Stage001计划：`plans/20260905_stage001_expiry_safe_roll_mapping_qualification.md`。
- Stage001授权：`stages/20260905_stage001_execution_authorization.json`，nonce已消费。
- Stage001结果：`stages/20260905_0114_stage001_expiry_safe_roll_mapping_pass.md`。
- 冻结产物：`artifacts/stage001_expiry_safe_roll_mapping/`，verify-only为8个artifact、7个输入、0错误。

## 过拟合反思

- 当前判断：否。
- 原因：规则由合约最后交易日与可执行性约束推出，不接触收益、标签、模型效果；两个已知失败事件只作为canary，不作为删样本或特例分支。
- 边界：不得用return date的bar存在、未来vendor主力或未来收益来选择替代合约。

## 继续价值反思

- 当前判断：本线目标已完成；直接生成标签暂无充分资格，另立成交安全线有价值。
- 原因：`wr2401`成交65/持仓73具备基本活动，`RS607`成交0/持仓6仅满足到期与bar存在，不足以证明可执行；不得把技术完整率当成标签可信度。
