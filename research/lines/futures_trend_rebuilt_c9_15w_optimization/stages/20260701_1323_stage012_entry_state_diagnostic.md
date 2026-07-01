# Stage012 新增/交易仓位入场前账户状态诊断

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01 13:23 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读诊断；不改策略、不扫参数、不连接 CTP、不调用下单。
- 是否重要突破：否。它不是候选策略，只是把 Stage011 左尾新增/交易仓位拆到交易前可见状态。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：
  - Sandberg/Ohman, `Position sizing in trend following trading strategies`：趋势策略的 position sizing 可用目标波动、最大回撤等账户风险口径，但必须服务于稳健性。
  - Hood/Raughtigan, `Volatility Targeting Is Trendy`：波动目标在趋势类资产上可能有效，但商品等资产不一定普适，不能无脑套用。
  - AQR, `Demystifying Managed Futures`：趋势跟随价值来自跨市场、跨期限与风险管理，而非单窗口拟合。
  - Graham Capital, `Trend-Following Primer`：持仓大小本质上应随风险/波动调整。
- 我的判断：账户状态、保证金压力、持仓集中度、AI rank 与质量标签可以作为下一步候选的输入；但 Stage012 不能直接把 `2022-07 -> 2023-07` 坏窗口里的某个状态桶变成规则，否则就是窗口拟合。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage012_entry_state_diagnostic.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `FOCUS_SOURCE_BUCKET=opened_or_traded_after_focus_start`
  - `BASELINE_START=2020-01-01`
  - 焦点窗口继承 Stage011：`2022-07-15 -> 2023-07-17`
  - source 继承 Stage011：`10` 个冷启动账户
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 账户规模：C9/15w live profile，沿用 Stage167/Stage006 口径。
- 数据输入：
  - Stage006 curves：当前重建版同口径全曲线。
  - Stage007 quality features：分钟源修复后的逐笔质量标签。
  - Stage011 positions/window detail：焦点窗口日级持仓 PnL 归因。
- 归因维度：
  - 日级新增/交易仓位：上一交易日 drawdown、broker10 margin/equity、活跃品种数、品种方向。
  - 入场逐笔：上一交易日状态、active positions、AI rank、quality bucket、same-direction count/correlation、risk multiplier、loss streak。
- 基准对照：`2020-01-01` 以后、同 `10` 个 source、非焦点入场记录，作为 `baseline_2020plus_entries`。

## 结果

- 期末权益：不适用，本阶段不是完整候选回测。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：本阶段不汇总完整账户滑点；焦点日级新增/交易仓位维度内可见滑点合计来自明细文件。
- 总交易次数：焦点日级新增/交易仓位维度内可见交易次数合计来自明细文件。
- 胜率：焦点入场逐笔胜率 `23.8908%`，基准 `2020+` 入场逐笔胜率 `47.5890%`。
- 其他关键指标：
  - daily detail rows：`1,070`。
  - entry detail rows：`2,692`。
  - 焦点窗口新增/交易仓位日级净 PnL：`-11,911,535`。
  - 焦点窗口入场 lot：`293`，完整 realized PnL：`-10,990,495`。
  - 焦点入场每 lot realized PnL：`-37,510.22`；基准 `2020+` 每 lot：`33,952.97`；差值：`-71,463.20`。
  - 日级最差状态桶：`prev_active_products_bucket=products_1`，`net_pnl=-9,712,225`，`row_count=588`，`source_count=10`。
  - 入场逐笔最差状态桶：`active_positions_bucket=active_0`，`lot_count=213`，`realized_pnl=-8,303,185`，胜率 `21.1268%`。
  - AI rank：焦点 `rank_4_6` 为 `88` 笔，`realized_pnl=-6,684,760`，胜率 `10.2273%`；同桶基准 `realized_pnl=26,746,833.4`，每 lot `47,847.64`。
  - 质量标签：焦点 `ai4_6_not_aligned` 为 `49` 笔，`realized_pnl=-4,531,740`，胜率 `0%`；但基准同桶仍为正 `2,340,433.4`，不能直接一刀切。
  - 质量标签：焦点 `ai4_6_entry_or_first_aligned` 为 `39` 笔，`realized_pnl=-2,153,020`；基准同桶为 `24,406,400`，每 lot `113,518.14`。说明高质量标签在坏窗口也会承压，后续加风险必须叠加账户状态，不应单独放大。

## 输出文件

- report：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage012_entry_state_diagnostic/rebuilt_c9_stage012_entry_state_diagnostic_report_stage012_entry_state_diagnostic_v1.md`
- decision：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage012_entry_state_diagnostic/rebuilt_c9_stage012_entry_state_diagnostic_decision_stage012_entry_state_diagnostic_v1.json`
- chart：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage012_entry_state_diagnostic/rebuilt_c9_stage012_entry_state_diagnostic_chart_stage012_entry_state_diagnostic_v1.png`
- daily_state_detail：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage012_entry_state_diagnostic/rebuilt_c9_stage012_entry_state_diagnostic_daily_state_detail_stage012_entry_state_diagnostic_v1.csv`
- daily_state_summary：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage012_entry_state_diagnostic/rebuilt_c9_stage012_entry_state_diagnostic_daily_state_summary_stage012_entry_state_diagnostic_v1.csv`
- entry_state_detail：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage012_entry_state_diagnostic/rebuilt_c9_stage012_entry_state_diagnostic_entry_state_detail_stage012_entry_state_diagnostic_v1.csv`
- entry_dimension_summary：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage012_entry_state_diagnostic/rebuilt_c9_stage012_entry_state_diagnostic_entry_dimension_summary_stage012_entry_state_diagnostic_v1.csv`
- entry_combo_summary：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage012_entry_state_diagnostic/rebuilt_c9_stage012_entry_state_diagnostic_entry_combo_summary_stage012_entry_state_diagnostic_v1.csv`
- baseline_comparison：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage012_entry_state_diagnostic/rebuilt_c9_stage012_entry_state_diagnostic_baseline_comparison_stage012_entry_state_diagnostic_v1.csv`

## 结论

- 本阶段结论：坏窗口不是简单的“AI rank 差”或“某品种坏”，而是账户处在较深 drawdown/低有效风险承受状态时，正常风险的新入场也会整体失效；焦点窗口的高质量标签同样亏损，说明加风险必须叠加账户状态闸门。
- 是否进入下一步：是。
- 下一步：冻结一个不按品种、不按日期、不扫参的账户状态候选，例如“账户处于深回撤且有效空仓/低活跃状态时，新开仓不直接用正常风险，先进入小风险试探；只有出现可见确认后释放风险”。下一步必须写真引擎，而不是只读代理。

## 过拟合反思

- 运行前判断：否。只看交易前可见状态，并与 `2020+` 基准对照，不新增规则。
- 运行后判断：否。没有把任何状态桶变成阈值，也没有按 `SM.CZCE short`、`2022-07-18` 或单品种做黑名单。
- 原因：Stage012 只证明“左尾与账户状态相关”，不证明某个阈值可上线。

## 继续价值反思

- 运行前判断：是。Stage011 已确认新增/交易仓位占左尾亏损 `61.92%`，必须看入场前状态。
- 运行后判断：有。状态归因显示坏窗口中的正常风险入场整体失效，而基准中这些桶多数仍盈利；这提示下一步要做“风险释放纪律”，不是继续单独加强 AI 高质量信号。
- 原因：用户目标要求任意一年以上窗口正收益并保留右尾，单纯加风险会放大左尾；账户状态闸门是更符合第一性原理的方向。

## 合入建议

- 是否更新本线 `LINE.md`：是，最新阶段更新到 Stage012。
- 是否更新 `research/registry.md`：是，最新关键阶段更新到 Stage012。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段仍是独立研究线内部诊断，不是正式候选、重要合入或路线废弃。
