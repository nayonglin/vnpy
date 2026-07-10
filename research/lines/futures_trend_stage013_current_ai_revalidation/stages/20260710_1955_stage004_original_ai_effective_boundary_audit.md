# Stage004 原始 AI 生效边界法证审计

- line_id：`futures_trend_stage013_current_ai_revalidation`
- 当前模式：`day`
- 记录时间：`2026-07-10 20:09:02 CST`
- 阶段性质：只读输入法证，不是回测，不改策略、AI 文件、实盘或 CTP
- 新增/修改/删除参数：无

## 结果

- 原始 walk-forward 训练/测试/步长：`720/180/180` 天。
- 原始预测共 `900` 行、`50` 个 eval_date，首个日期 `2022-01-28`。
- 当前 AI 文件 `504` 行/`55` 个 eval_date；2019-12 为 18 品种静态边界，2022-01 至 2026-06 的 54 个月月度快照连续无缺口。
- 当前 `ai_probability` 的 50 个日期与原始 walk-forward predictions 日期集合完全一致；2026-03 至 05 为恢复快照，2026-06 为 live inference。
- Stage062 在 2021-04 至 12 回算的 9 个月早于原首个 OOS 日期，是新 live inference 规则提前生效的反事实，不是原冻结政策下丢失的月池。

## 最终结论

- 决策：`current_ai_calendar_complete_under_original_oos_policy_stage003_is_counterfactual`。
- Stage002 的 current-AI 月历在原冻结 OOS 政策下是完整的；Stage003 应定性为 early-activation sensitivity，不能用来否定 Stage002。
- 独立 agent review：边界法证通过，`P0=0/P1=0/P2=1`、置信度 `98%`；残余 P2 是 2026-03 至 05 只恢复 membership，原概率值未字节级恢复。

## 反思

- 过拟合：否。本阶段只核对代码常量、预测日期和文件覆盖。
- 继续价值：有。已撤销 Stage002 的“9个月缺失阻塞”，下一步进入成本/执行稳健性；Stage003 不继续。
