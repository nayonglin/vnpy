# Stage003 干净候选账户边际标签计划审计

- 决策：`stage003_account_label_plan_pass_smoke_blocked_on_runtime_preflight`。
- 切分：开发35月/266行，封存账户标签12月/108行。
- 任务：主任务266，A/A哨兵4，合计270。
- 资格路径结构门已审计；未读取标签、未训练、未回测。
- smoke仍受运行时前置阻断：['old_frozen_runtime_missing', 'isolated_research_snapshot_not_frozen']。
