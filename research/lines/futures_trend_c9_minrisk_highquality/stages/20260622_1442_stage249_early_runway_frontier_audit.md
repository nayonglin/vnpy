# Stage249 early-runway frontier 边界审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-22 14:42`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读边界审计、早期跑道右尾保护、延迟确认阻断证明
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Research Affiliates《Walking the Tightrope: Trend Following's Tricky Tradeoffs》：趋势跟随的正偏收益和 Sharpe 存在权衡，右尾保护来自少数大赢家，不能轻易用更平滑的路径换掉。<https://www.researchaffiliates.com/content/dam/ra/publications/pdf/1077-trend-followings-tricky-tradeoffs-sharpe-ratio-vs-skew.pdf>
  - Zarattini/Pagani/Wilcox《Does Trend-Following Still Work on Stocks?》：大样本趋势交易中，少数交易驱动累计利润，交易成本和换手会显著影响净效果。<https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5084316>
  - Man AHL《The Need for Speed in Trend-Following Strategies》：更快的趋势系统有风险管理价值，但速度、换手、偏度和 Sharpe 之间存在结构性取舍。<https://www.man.com/insights/need-for-speed-trend-following>
  - GitHub `quantiacs/strategy-futures-trend-following`：公开期货趋势策略模板强调多资产、时间序列、信号定义和图形化结果，支持把执行速度和信号结构分开审计。<https://github.com/quantiacs/strategy-futures-trend-following>
- 我的判断：
  - Stage248 已证明 close-dwell 有解释价值但不能成为规则；真正问题在于很多右尾在首根或 5 根内完成 C9 progress。
  - 如果早期跑道承载大量右尾，那么“先小仓等确认再恢复”的执行层形状天然会漏掉右尾，不是改窗口能解决。
  - 本阶段只量化边界，不创建规则，不把任何前置特征组合成早期右尾选择器。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage249_early_runway_frontier_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `EARLY_STATES={"first_bar_event_no_closed_dwell","short_runway_le5_no_dwell"}`
  - 固定 early frontier：首根事件或 `1-5` 根内事件，且没有足够 close-dwell 观察空间。
  - 固定前置特征审计：Stage239 的 7 个 formal candidate feature 的 `q4q5_top_quality` 与 `q5_top_quality`。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage248 的 `219` 个 timestamp-ready replay order。
- 账户规模：沿用官方 C9/15w 曲线，初始权益 `150,000`。
- 成本口径：沿用官方曲线；本阶段没有新增交易、滑点或手续费。
- 样本过滤：
  - `early_no_dwell` = `first_bar_event_no_closed_dwell` 或 `short_runway_le5_no_dwell`。
  - `adequate_dwell` = 其余有足够 close-dwell 观察空间的订单。
  - 前置特征只读取 Stage239 已点时化的 formal feature quintile，不新增阈值。
- 策略/归因口径：
  - 本阶段不创建交易规则，不运行 true engine，不触发 A/B。
  - 只用官方 order realized PnL、right-tail visual、bottom-loss visual 和 maxDD context 做边界归因。

## 结果

- 期末权益：`39,176,437.60`，官方路径未变
- 总收益：`26017.6251%`，官方路径未变
- 最大回撤：`-45.0827%`，官方路径未变
- Sharpe：`1.6331`，官方路径未变
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - `decision=stage249_early_runway_frontier_blocks_delayed_confirmation_no_rule`
  - `timestamp_ready_order_count=219`
  - `early_runway_order_count=114`
  - `early_runway_pnl_sum=15,444,809.40`
  - `early_runway_pnl_share=0.476829`
  - `early_runway_right_tail_count=9`
  - `early_runway_right_tail_share=0.5000`
  - `early_runway_bottom_loss_count=9`
  - `early_runway_bottom_loss_share=0.5000`
  - `early_progress_order_count=74`
  - `early_stop_order_count=40`
  - `best_predecision_feature_early_right_tail_capture_count=5`
  - `clean_predecision_feature_signal_count=0`
  - `promotion_gate_count=5`
  - `promotion_gate_pass_count=1`
  - `strategy_rule_created=0`
  - `true_engine_run=0`
  - `ab_triggered=0`
  - `official_config_changed=0`
  - `ctp_connected=0`
  - `order_api_called=0`

## 图像分析

- 官方资金/回撤叠加图：
  - `early_no_dwell` 点横跨完整权益曲线，覆盖高台阶、2022-2023 回撤段和近端样本。
  - 这不是单一年份、单一产品或单一交易所异常，不适合用补丁处理。
- frontier contribution chart：
  - `early_no_dwell` 累计贡献约 `1544万`，占 Stage248 订单 PnL 的 `47.68%`。
  - 该曲线在 2023 前后显著拉升，并非无关噪声桶。
- event timing bucket chart：
  - `first_bar_event + progress` 贡献约 `12,355,060`，包含 `6` 个 right-tail、`1` 个 bottom-loss。
  - `bar1_to_5_event + progress` 贡献约 `6,340,934`，包含 `3` 个 right-tail、`6` 个 bottom-loss。
  - 早期桶同时承载收益和亏损，说明“快”是必要但不充分条件。
- predecision feature capture heatmap：
  - 现有前置单特征没有干净隔离早期右尾。
  - 最好的 `low_range_ratio_1m q4q5` 只捕获 `5/9` 个早期 right-tail，同时带 `10` 个 bottom-loss 和 `16` 个 risk_bad。
  - `aligned_bar_return_1m q5` 只捕获 `2/9` 个早期 right-tail。
  - `directional_efficiency_30m q5` 捕获 `0/9` 个早期 right-tail。
- atlas：
  - `jm2405.DCE`、`jm2401.DCE`、`OI305.CZCE` 是首根 progress 右尾，几乎没有可观察空间。
  - `OI309.CZCE` 是 `1-5` 根内 progress 大右尾。
  - `jm2301.DCE`、`ru2605.SHFE`、`AP505.CZCE` 同样处于早期 progress/first-bar 边界，但最终是 bottom-loss。
  - 早期 progress 本身不能区分好坏，必须依赖入场前更高信息量或账户层预算，而不能靠入场后等待。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage249_early_runway_frontier_audit/qmt_roll_stage249_c9_minrisk_early_runway_frontier_audit_report_stage249_early_runway_frontier_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage249_early_runway_frontier_audit/qmt_roll_stage249_c9_minrisk_early_runway_frontier_audit_summary_stage249_early_runway_frontier_audit_v1.csv`
- orders：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage249_early_runway_frontier_audit/qmt_roll_stage249_c9_minrisk_early_runway_frontier_audit_frontier_rows_stage249_early_runway_frontier_audit_v1.csv`
- daily：沿用官方曲线，本阶段未生成新 daily
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage249_early_runway_frontier_audit/qmt_roll_stage249_c9_minrisk_early_runway_frontier_audit_decision_stage249_early_runway_frontier_audit_v1.json`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage249_early_runway_frontier_audit/qmt_roll_stage249_c9_minrisk_early_runway_frontier_audit_frontier_summary_stage249_early_runway_frontier_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage249_early_runway_frontier_audit/qmt_roll_stage249_c9_minrisk_early_runway_frontier_audit_event_bucket_summary_stage249_early_runway_frontier_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage249_early_runway_frontier_audit/qmt_roll_stage249_c9_minrisk_early_runway_frontier_audit_predecision_feature_signal_summary_stage249_early_runway_frontier_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage249_early_runway_frontier_audit/qmt_roll_stage249_c9_minrisk_early_runway_frontier_audit_promotion_gate_stage249_early_runway_frontier_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage249_early_runway_frontier_audit/qmt_roll_stage249_c9_minrisk_early_runway_frontier_audit_atlas_manifest_stage249_early_runway_frontier_audit_v1.csv`

## 结论

- 本阶段结论：
  - `early_no_dwell` 是延迟确认路线的硬边界：它承载 `47.68%` 的 Stage248 订单 PnL 和 `50%` 的 right-tail visual。
  - 同一早期边界也承载 `50%` 的 bottom-loss visual，不能简单做“早期 progress 就好”。
  - Stage239 的现有前置单特征无法提前干净识别这些早期右尾，最佳也只捕获 `5/9`，且带大量坏样本。
  - 因此“先小仓观察，等入场后分钟确认再恢复”的主路线应停止交易化推进。
- 是否进入下一步：进入，但换路线。
- 下一步：
  - 不再调首根/5根/30根或 dwell 比例。
  - 若继续追求“最小风险搏最大收益”，应转向：
    - 入场前更高信息量：盘口/订单流、真实执行回放、可行动的 C9 progress 前数据。
    - 或账户层风险预算：承认早期边界不可区分，用组合/权益层而不是单笔分钟确认去降回撤。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有新交易规则，没有扫窗口，也没有按结果调阈值。
  - 结论是阻断延迟确认，而不是把某个早期桶救成规则。
  - 前置特征审计只用 Stage239 已冻结的 7 个 formal candidate feature，不新增组合或小格。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但方向必须改变。
- 原因：
  - 有价值：明确了为什么 Stage248/Stage013/Stage002 这类延迟恢复形状会漏右尾。
  - 无继续调参价值：早期边界同时包含右尾和亏损，现有前置特征无法区分。
  - 下一步应转入账户层或更高信息层，而不是继续入场后确认。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage249 摘要。
- 是否更新 `research/registry.md`：否，本阶段不是重要突破或正式候选。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、路线废弃正式合入、正式候选或跨线合并。
