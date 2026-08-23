# Stage011 成交量翻倍 H 多周期诊断闸门

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：用户在 Stage010 全周期失败后明确要求的诊断性多周期
- 记录时间：2026-08-23 18:28 CST
- 工作区/分支：`.worktrees/rollover-shape-same-volume` / `codex/rollover-shape-same-volume`
- 阶段性质：补充跨周期稳健性诊断，不是重新开放晋级
- 是否重要突破：否
- 是否触发A/B：是

## 外部调研与判断

- CME 支持把成交量作为市场参与度与流动性的辅助信息，但不能由成交量单独推断交易方向：<https://www.cmegroup.com/education/courses/introduction-to-futures/what-is-volume>
- Lee 与 Swaminathan 支持价格动量与成交量存在交互，但没有为 `2.0` 阈值提供理论最优性：<https://papers.ssrn.com/sol3/papers.cfm?abstract_id=92589>
- 我的判断：Stage010 已经因 A/C 对照的回撤和成本失败，Stage011 只能回答风险代价是否跨周期稳定，不能用部分滚动窗口胜出覆盖完整周期失败。

## 运行身份与复用合同

- 固定窗口：Stage005 固化的 `43` 个窗口，包括完整周期、1/2/3年每年1月和6月独立冷启动；每个周期的临近完整终端窗口只观察不投票。
- A/C/F：复用 Stage008 已提交的 `43×3=129` 次独立真引擎运行，来源提交 `ce9e9c5d7`。
- 复用前必须验证 A/C/F 完整周期 summary 和各 `2,037` 行资金曲线与 Stage010 同臂逐值完全一致；任何漂移立即失败。
- H：新运行 `43` 次独立真引擎，每个窗口重建引擎、资金、持仓和账户状态。
- 最终逻辑矩阵：`43×4=172` 个臂窗；必须生成 `258` 行两两 comparison、`54` 行周期/起点 aggregate 和完整资金曲线。
- 必须在报告中明确：这是 `129` 个冻结基线运行 + `43` 个新增 H 运行，禁止表述为本阶段新跑172次。

## 冻结实验臂

- A：当前正式 C9/15万。
- C：A + `backwards_ratio_continuous + shrink_to_allowed` 换月连续历史续仓。
- F：C + 30日方向同向且 `recent_10d_volume > 1.0 * prior_10d_volume` 时风险 `×1.2`。
- H：C + 30日方向同向且 `recent_10d_volume > 2.0 * prior_10d_volume` 时风险 `×1.2`。
- H 时间窗：`recent=T-9..T`（含信号日），`prior=T-19..T-10`；必须严格大于。

## 多周期报告格式

- 固定输出五图且顺序不变：完整周期、1年滚动、2年滚动、3年滚动、周期汇总。
- 1/2/3年图按年份排序，同年1月在前、6月在后；`*` 只表示临近完整终端观察窗口。
- 每个周期分别输出 `combined/January/June`。
- 必须列出最差收益、最深回撤、最差 Sharpe、最高成本比和最低生存权益窗口。

## 决策纪律

- 继续沿用 Stage010 的完整周期门；Stage010 的 A_vs_H/C_vs_H 失败不会因用户要求补跑而被删除。
- H 必须同时通过 A_vs_H 和 C_vs_H 的全部完整周期门，以及1/2/3年各 `combined/January/June` 共18个 H 周期门，才允许 `double_volume_multicycle_evidence_supports_reopening_review`。
- 任一失败，决策固定为 `confirm_double_volume_not_promotable_after_multicycle`。
- 周期门：收益胜率至少50%、收益差中位非负、DD非劣2pp比例至少80%、DD50失败数不增加、Sharpe非劣0.05比例至少80%、聚合滑点不超过105%、全部生存、broker100失败数不增加。
- 失败后不扫描成交量比例、窗口、风险倍率、品种、方向、年份或起点。

## 新增与边界

- 新增运行器：`tools/stage011_double_volume_multicycle_acfh.py`。
- 新增测试：`tests/test_rollover_shape_stage011_runner.py`。
- 新增/修改/删除策略参数：均无；复用 Stage010 已冻结 H。
- 正式配置、正式物料、master、production、CTP 和订单接口禁止修改；订单/撤单 API 必须为 `0/0`。

## 过拟合反思

- 运行前判断：是，高风险。
- 原因：H 已在全周期失败，补跑多周期属于结果后追加诊断；固定窗口、固定门和不调参只能防止进一步恶化，不能消除后验选择。

## 继续价值反思

- 运行前判断：有限有价值。
- 原因：可以确认 H 的收益、回撤和成本效应是否依赖单一长周期，并形成用户要求的固定五图；没有继续调参或晋级价值，除非全部原门意外通过。
