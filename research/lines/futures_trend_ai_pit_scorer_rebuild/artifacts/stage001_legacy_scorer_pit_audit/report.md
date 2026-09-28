# Stage001 旧正式评分器PIT审计

- 决策：`stage001_legacy_pit_audit_complete_allow_fixed_universe_conditional_rebuild`。
- 旧fold：`9`；标签越界fold：`9`，越界训练行：`504`。
- 非完整60日标签：`36`行；未上市样本：`133`行。
- 历史批准宇宙可重建：`False`；下一阶段证据仅限固定当前设计宇宙条件下的PIT基线。
- 本阶段训练0、回测0、sealed holdout读取0、CTP/订单调用0。
