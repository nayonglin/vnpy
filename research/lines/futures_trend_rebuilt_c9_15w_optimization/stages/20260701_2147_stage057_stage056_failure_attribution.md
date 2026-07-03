# Stage057 - Stage056 失败归因

> 废弃说明：本记录为修复 cap event 到 baseline lot 日期匹配前的中间产物，`matched baseline lot = 0` 是已知错误。有效结论以 `research/lines/futures_trend_rebuilt_c9_15w_optimization/stages/20260701_2149_stage057_stage056_failure_attribution.md` 为准。

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01T21:47:16 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读失败归因，不改官方实盘配置。
- 是否重要突破：`否`
- 是否触发A/B：`否`

## 外部调研与判断

- 参考资料：AlphaSimplex risk variation in trend-following、pysystemtrade/Rob Carver forecast scaling、time-series momentum 与 trend-following position sizing 资料。
- 我的判断：Stage056 失败不是因为 Top8 数字要微调，而是“一刀切 cap”把风险预算从连续问题简化成硬门槛，容易压掉右尾。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage057_stage056_failure_attribution.py`
- 新增测试：`tests/test_rebuilt_c9_stage057_stage056_failure_attribution.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：无交易参数。
- 修改参数：无。
- 删除参数：无。

## 归因参数

- 输入：Stage056 curves/trades/entry_risk/entry_candidates/budget_cap_events。
- 口径：A=Stage013，C=Stage056；严格窗口仍使用 `>365` 自然日。
- lot 归因：把 Stage056 cap event 按 `requested_start + entry_date + contract + product + direction` 匹配 Stage013 baseline closed lot，并按减少手数比例估算被 cap 掉的 realized PnL proxy。
- 不连接 CTP、不调用订单 API。

## 结果

- Stage056 新增负窗口 `120914`，修复负窗口 `18842`。
- 新增负窗口中分母效应 `116352`，绝对权益更差 `4562`。
- cap 事件 `852`，匹配 baseline lot `0`，减少手数 `5016`。
- 被 cap 掉的 baseline PnL proxy 合计 `0.00`，少赚 `0.00`，少亏 `0.00`。
- 右尾错杀 source `0`，减亏有帮助 source `0`。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage057_stage056_failure_attribution/rebuilt_c9_stage057_stage056_failure_attribution_report_stage057_stage056_failure_attribution_v1.md`
- source_attribution：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage057_stage056_failure_attribution/rebuilt_c9_stage057_stage056_failure_attribution_source_attribution_stage057_stage056_failure_attribution_v1.csv`
- product_attribution：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage057_stage056_failure_attribution/rebuilt_c9_stage057_stage056_failure_attribution_product_direction_attribution_stage057_stage056_failure_attribution_v1.csv`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage057_stage056_failure_attribution/rebuilt_c9_stage057_stage056_failure_attribution_chart_stage057_stage056_failure_attribution_v1.png`

## 结论

- 本阶段结论：`stage057_stage056_failed_due_to_coarse_hard_cap_right_tail_wrong_cut`。
- 下一步：不要扫 `TopN/手数/品种`；若继续，应寻找连续预算或状态条件，先做只读归因/稳定性，再决定是否真引擎。

## 过拟合反思

- 运行前判断：否。Stage057 只解释 Stage056 已失败结果，不新增交易规则。
- 运行后判断：否。本阶段没有调参；结论反而要求停止 TopN/手数/品种救参。

## 继续价值反思

- 运行前判断：有。Stage056 已反证，但仍要知道失败形状，避免重复走硬 cap。
- 运行后判断：有条件。继续价值在连续预算/状态归因，不在 full-market TopN 硬门槛。
