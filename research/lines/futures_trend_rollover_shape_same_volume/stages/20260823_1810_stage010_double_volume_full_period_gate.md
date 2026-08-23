# Stage010 30日方向与成交量翻倍联合加风险全周期闸门

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：A/B 最小全周期真引擎验证；结果前冻结
- 记录时间：2026-08-23 18:10 CST
- 工作区/分支：`.worktrees/rollover-shape-same-volume` / `codex/rollover-shape-same-volume`
- 阶段性质：Stage008 失败后具有明确选择性的单点量能阈值验证
- 是否重要突破：否
- 是否触发A/B：是

## 外部调研与判断

- CME 说明成交量可辅助判断市场参与度、流动性和换月迁移，但成交量本身不能识别买卖方向：<https://www.cmegroup.com/education/courses/introduction-to-futures/what-is-volume>
- Lee 与 Swaminathan 说明价格动量与历史成交量存在交互，但没有为本实验的 `2.0` 比例提供直接理论依据：<https://papers.ssrn.com/sol3/papers.cfm?abstract_id=92589>
- 我的判断：`2.0` 是 Stage008 结果之后提出的后验阈值，过拟合风险中高；但现有诊断预检仅覆盖 `47/371=12.6685%` 的价格同向意图，明显不同于 D 的近普遍增强和 F 的 `57.6819%`，因此值得做一次冻结后的最小全周期证伪。

## 冻结实验臂

- A：当前正式 C9/15万原样，不启用换月续仓或方向风险增强。
- C：A + 换月连续历史形态续仓，`backwards_ratio_continuous + shrink_to_allowed`。
- F：C + 30日价格方向同向，并且 `recent_10d_volume > 1.0 * prior_10d_volume` 时风险金额乘 `1.2`。
- H：C + 30日价格方向同向，并且 `recent_10d_volume > 2.0 * prior_10d_volume` 时风险金额乘 `1.2`。
- `recent_10d` 固定为含信号日的 `T-9..T`；`prior_10d` 固定为 `T-19..T-10`；必须严格大于，恰好两倍不触发。
- 覆盖普通开仓、反手、换月重开、regular add、donchian add、post-quality add；放大后仍须经过全部既有硬风控，手数向下取整。

## 新增与修改

- 新增参数：`directional_30d_volume_ratio_threshold=1.0`；默认 `1.0`，且只有启用方向风险增强和量能确认时生效，因此不改变正式策略和既有 A/C/D/F 行为。
- 新增运行器：`tools/stage010_directional_double_volume_full_period_acfh.py`。
- 新增测试：`tests/test_rollover_shape_stage010_runner.py`；扩展 `tests/test_rollover_shape_same_volume.py`。
- 删除参数/脚本/结果：无。
- 正式配置、正式物料、master、production、CTP 和订单接口：禁止修改；订单/撤单 API 必须为 `0/0`。

## 数据与运行顺序

- 数据区间：`2018-01-01 -> 2026-05-29`。
- 账户规模：`150,000`。
- 成本、保证金、品种、信号、换月和硬风控口径：完全继承 Stage008。
- 先运行 A/C/F/H 共4次全周期真引擎；只有 H 同时通过 A_vs_H 与 C_vs_H 的全部门，才允许新建多周期阶段。
- 若全周期失败，立即停止；不运行多周期，不扫描 `1.5/1.8/2.2/2.5/3.0`、窗口、倍率、品种、方向、年份或起点。

## 预声明合同门

- 所有 H 诊断的 `directional_30d_volume_ratio_threshold` 必须精确为 `2.0`。
- `applied=1` 当且仅当30日价格方向同向且 `recent > 2.0 * prior`；对应风险金额精确为基础风险 `×1.2`，其他为 `×1.0`。
- 必须存在真实触发，并且 H 增强数不得超过价格同向诊断的 `30%`，避免退化成普遍加风险。

## 预声明全周期晋级门

H 必须分别相对 A 和 C 同时满足：

- 总收益不低于对照。
- 最大回撤恶化不超过 `1pp`。
- Sharpe 不低于对照 `0.01` 以上。
- 总滑点不超过对照的 `105%`。
- 账户生存通过。
- broker10 峰值和超100%天数均不劣于对照。

任意一项失败，决策固定为 `stop_double_volume_boost_after_full_period`；全部通过才允许 `run_double_volume_multicycle`。

## 过拟合反思

- 运行前判断：是，中高风险。
- 原因：`2.0` 是看到 F 失败后提出的阈值；本阶段只允许这一个冻结点和一套结果前门槛，失败即停止。

## 继续价值反思

- 运行前判断：有，但仅限最小全周期验证。
- 原因：12.6685% 的预检覆盖显示它有实际选择性；是否带来独立收益而不恶化风险，必须由未见结果的全周期闸门决定。
