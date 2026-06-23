# Stage041 timestamp-ready replay 一致性审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 01:43 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：成交点时子集 replay convention 审计 / 只读账本工程
- 是否重要突破：否。它发现关键 convention 风险，但不产生候选规则。
- 是否触发A/B：否。本阶段没有新策略版本接入正式候选，也不修改正式配置。

## 外部调研与判断

- 参考资料：
  - Backtrader order execution 文档：https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/
  - Backtrader order 文档：https://www.backtrader.com/docu/order/
  - QuantConnect Understanding Time 文档：https://www.quantconnect.com/docs/v1/key-concepts/understanding-time
  - QuantConnect time slices 文档：https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/time-modeling/timeslices
  - QuantConnect fill model 文档：https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/trade-fills/key-concepts
  - NautilusTrader backtesting 文档：https://nautilustrader.io/docs/latest/concepts/backtesting/
- 我的判断：Backtrader、QuantConnect 与 NautilusTrader 的共同原则是，成交价、成交时间、bar timestamp convention 和 fill model 必须同时前向一致。Stage040 只能证明 raw proxy 能解释成交价；Stage041 进一步证明 raw timestamp 与官方 intraday diagnostics 的交易日口径还没有完全统一，不能把 raw timestamp anchor 直接用于分钟进出场规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage041_timestamp_ready_replay_consistency_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数。新增审计 variant：
  - `official_date_first_stage861_open_subset`
  - `official_date_official_open_anchor_subset`
  - `raw_timestamp_calendar_day_anchor`
  - `raw_timestamp_stitched_to_official_date_anchor`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage040 / Stage039 / Stage010 官方 C9/15w 输入，`2018-01-01` 至本地官方数据末端。
- 账户规模：`150000`
- 成本口径：官方 C9/15w 原始成本口径；本阶段不重跑候选策略。
- 样本过滤：Stage040 `timestamp_ready=1` 的 initial orders，共 `219` 笔。
- 策略/归因口径：当前官方正式 C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`；只审计 raw proxy timestamp 与 Stage861 minute / official intraday diagnostics 的 replay convention。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：closed-lot 胜率 `36.0902%`
- 其他关键指标：
  - timestamp-ready initial orders：`219`
  - raw timestamp 在 official date 内：`64`
  - raw timestamp 在 candidate date 但不在 official date 内：`140`
  - Stage861 找不到 raw timestamp：`15`
  - official-date official-open anchor 子集 event match：`98.1735%`，mismatch `4`
  - official-date first Stage861 open 子集 event match：`68.9498%`，mismatch `68`
  - raw timestamp calendar-day anchor ready：`204`，event match `73.0392%`，mismatch `55`
  - raw timestamp stitched-to-official-date anchor ready：`204`，event match `87.2549%`，mismatch `26`
  - first Stage861 same-exit 期末权益：`35,118,687.60`
  - first Stage861 same-exit 最大回撤：`-48.1910%`
  - raw stitched same-exit 期末权益：`39,176,437.60`
  - raw stitched same-exit 最大回撤：`-45.0827%`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage041_timestamp_ready_replay_consistency_audit/qmt_roll_stage041_c9_minrisk_timestamp_ready_replay_consistency_audit_report_stage041_timestamp_ready_replay_consistency_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage041_timestamp_ready_replay_consistency_audit/qmt_roll_stage041_c9_minrisk_timestamp_ready_replay_consistency_audit_summary_stage041_timestamp_ready_replay_consistency_audit_v1.csv`
- replay ledger：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage041_timestamp_ready_replay_consistency_audit/qmt_roll_stage041_c9_minrisk_timestamp_ready_replay_consistency_audit_replay_ledger_stage041_timestamp_ready_replay_consistency_audit_v1.csv`
- timestamp alignment：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage041_timestamp_ready_replay_consistency_audit/qmt_roll_stage041_c9_minrisk_timestamp_ready_replay_consistency_audit_timestamp_alignment_stage041_timestamp_ready_replay_consistency_audit_v1.csv`
- variant summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage041_timestamp_ready_replay_consistency_audit/qmt_roll_stage041_c9_minrisk_timestamp_ready_replay_consistency_audit_variant_summary_stage041_timestamp_ready_replay_consistency_audit_v1.csv`
- event confusion：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage041_timestamp_ready_replay_consistency_audit/qmt_roll_stage041_c9_minrisk_timestamp_ready_replay_consistency_audit_event_confusion_stage041_timestamp_ready_replay_consistency_audit_v1.csv`
- daily：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage041_timestamp_ready_replay_consistency_audit/qmt_roll_stage041_c9_minrisk_timestamp_ready_replay_consistency_audit_same_exit_sensitivity_curve_stage041_timestamp_ready_replay_consistency_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage041_timestamp_ready_replay_consistency_audit/qmt_roll_stage041_c9_minrisk_timestamp_ready_replay_consistency_audit_decision_stage041_timestamp_ready_replay_consistency_audit_v1.json`
- 资金曲线：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage041_timestamp_ready_replay_consistency_audit/qmt_roll_stage041_c9_minrisk_timestamp_ready_replay_consistency_audit_same_exit_path_chart_stage041_timestamp_ready_replay_consistency_audit_v1.png`
- timestamp alignment 图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage041_timestamp_ready_replay_consistency_audit/qmt_roll_stage041_c9_minrisk_timestamp_ready_replay_consistency_audit_timestamp_alignment_chart_stage041_timestamp_ready_replay_consistency_audit_v1.png`
- event match 图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage041_timestamp_ready_replay_consistency_audit/qmt_roll_stage041_c9_minrisk_timestamp_ready_replay_consistency_audit_event_match_chart_stage041_timestamp_ready_replay_consistency_audit_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage041_timestamp_ready_replay_consistency_audit/qmt_roll_stage041_c9_minrisk_timestamp_ready_replay_consistency_audit_timestamp_replay_atlas_page001_stage041_timestamp_ready_replay_consistency_audit_v1.png` 至 `page003`

## 结论

- 本阶段结论：`stage041_timestamp_ready_replay_convention_not_yet_trade_rule`。Stage040 的 `219` 笔 timestamp-ready 只说明成交价可以由 raw proxy 解释；当 raw timestamp 真正作为扫描起点时，事件匹配从 official-date anchor 的 `98.1735%` 降到 stitched replay 的 `87.2549%`，说明交易日/session convention 仍未统一。
- 是否进入下一步：是，但仍然是账本工程，不是策略候选。
- 下一步：建立 trading-day stitched minute ledger，把 candidate date 夜盘、official date 日盘、Stage861 `bar_date/bar_datetime` 与 official intraday diagnostics 的事件时间统一到同一 session 口径。未完成前，不测试新的分钟开仓、恢复、降仓或退出规则。

## 视觉观察

- alignment chart 显示 day proxy 的 `64` 笔全部落在 official date `09:00` 窗口；night proxy 中 `140` 笔落在 candidate date `21:00`，不是 official date，另有 `15` 笔 raw timestamp 在 Stage861 中找不到精确 bar。
- event match chart 显示 official-date official-open anchor 子集达到 `98.2%`，raw stitched 只有 `87.3%`；差异来自扫描起点和交易日口径，不是成交价。
- same-exit path chart 中 raw stitched 曲线与官方重合，是因为 raw price 等于 official open price；它不能证明事件时间轴可交易化。
- atlas 显示多个夜盘样本中，raw timestamp 在前一晚 `21:00`，official-date first bar 在次日 `09:00`，官方事件线与 raw stitched replay 事件线顺序不一致。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有新增交易规则或参数，也没有按年份、品种、方向、时段筛选交易；只是揭示 timestamp convention 的账本约束。若把 day/night alignment class 当成信号好坏标签或只保留 `64` 个 official-date timestamp 样本做候选，就会转为过拟合和样本选择偏差。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有。
- 原因：Stage041 证明当前 replay 的主要问题已从“成交价不可解释”推进到“交易日/session convention 未统一”。继续做 stitched ledger 有价值，因为它是后续分钟级进出场候选是否可信的前置条件；但在这个前置条件通过前，继续写策略规则没有价值。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage041 摘要和下一步边界。
- 是否更新 `research/registry.md`：否。本阶段不是正式候选、重要突破或路线迁移。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是本线内部账本审计，不改变正式版或跨线结论。
