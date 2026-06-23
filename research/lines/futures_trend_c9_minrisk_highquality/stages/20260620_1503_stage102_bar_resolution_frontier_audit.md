# Stage102 分钟OHLC执行分辨率边界诊断

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 15:03 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读执行分辨率边界诊断；不是真引擎、不生成交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Backtrader order creation/execution 文档：`https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/`
  - hftbacktest docs：`https://hftbacktest.readthedocs.io/en/py-v2.2.0/`
  - hftbacktest order book imbalance 示例：`https://hftbacktest.readthedocs.io/en/latest/tutorials/Market%20Making%20with%20Alpha%20-%20Order%20Book%20Imbalance.html`
  - Databento L2/MBO queue position 说明：`https://medium.databento.com/getting-queue-position-with-l2-and-order-book-data-from-databento-d3f8039b2515`
- 我的判断：分钟K适合做中低频路径审计，但如果候选动作贴近 C9 stop/progress、依赖当前分钟收盘后立即成交，或需要判断同一分钟内先后顺序，就已经越过 OHLC 能稳定支持的边界。外部资料共同指向一个约束：执行敏感规则需要 tick、盘口、队列、延迟和订单流，否则回测很容易高估可行动性。Stage102 因此不再救 Stage100/101 的 absorption/reclaim，而是审计“继续用分钟OHLC找下一条近触价规则是否有基础”。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage102_bar_resolution_frontier_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增诊断字段：
  - `resolution_bucket`
  - `event_bar_idx`
  - `completed_bars_before_event`
  - `minutes_from_open_to_event`
  - `event_bar_high_r`
  - `event_bar_low_r`
  - `same_bar_stop_progress_ambiguous`
  - `first_bar_event`
  - `close_signal_next_bar_collision`
  - `low_resolution_zone`
- 新增诊断 bucket：
  - `first_bar_event_no_closed_bar`
  - `one_bar_event_close_action_collision`
  - `two_to_five_bar_short_runway`
  - `gt_five_bar_runway`
  - `no_c9_stop_or_progress_before_day_end`
- 新增参数：无；`+0.5R/-0.5R` 仅沿用 C9 stop/progress 事件语义，不作为新策略阈值。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：复用 Stage100 preflight rows，共 `219` 笔 Stage045 timestamp-ready orders。
- 账户规模：沿用基准路径，仅作背景路径。
- 成本口径：沿用基准统计，总滑点 `2,730,130`。
- 样本过滤：无新增收益过滤；bucket 只用于执行分辨率和视觉 atlas 选择。
- 策略/归因口径：只读 OHLC actionability audit，`ohlc_actionability_allowed=0`、`true_engine_allowed=0`、`strategy_feature_usable=0`。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：closed-lot win rate `36.0902%`
- 其他关键指标：
  - `decision=stage102_bar_resolution_frontier_blocks_ohlc_rule_no_rule`
  - `timestamp_ready_order_count=219`
  - `resolution_bucket_count=5`
  - `low_resolution_order_count=93`
  - `low_resolution_pnl_sum=14,680,399.40`
  - `low_resolution_right_tail_count=7`
  - `low_resolution_bottom_loss_count=5`
  - `low_resolution_maxdd_context_count=12`
  - `same_bar_stop_progress_ambiguous_order_count=0`
  - `first_bar_event_order_count=68`
  - `close_signal_next_bar_collision_order_count=25`
  - `two_to_five_bar_short_runway_order_count=21`
  - `gt_five_bar_runway_order_count=87`
  - `tail_conflict_bucket_count=4`
  - `pnl_sign_conflict_bucket_count=5`
  - `promotion_gate_count=7`
  - `promotion_gate_pass_count=1`
  - `official_config_changed=0`、`strategy_rule_created=0`、`true_engine_run=0`、`ab_triggered=0`、`order_api_called=0`、`ctp_connected=0`

## 视觉观察

- official path chart：低分辨率事件点分布在权益台阶、2022-2023 回撤段和近端样本上，不是某一年或某个窗口独有问题。
- bucket contribution chart：`first_bar_event_no_closed_bar` 与 `gt_five_bar_runway` 都是正贡献大桶；尤其首根事件桶本身承载右尾，不能把“太快触发”直接解释成坏信号。
- bucket summary chart：`first_bar_event_no_closed_bar` `68` 笔、`one_bar_event_close_action_collision` `25` 笔；二者合计 `93` 笔低分辨率区，里面同时有 `7` 个 right-tail visual 和 `5` 个 bottom-loss visual。
- gate chart：`same_bar_stop_progress_ordering` 通过，因为本次没有同根双触发；其余 6 个 gate 阻断，核心是无闭合K线可行动、下一根成交碰撞、右尾保护和 OHLC 不分离。
- atlas：`OI305/jm2401/fu2509` 显示首根就 progress 的右尾；`OI309` 显示第二根 progress 的大右尾，若依据第一根 close 后再动作，成交会天然与 C9 事件同根碰撞；`AP505/ru2605` 显示同类低分辨率区也有底部亏损，说明 OHLC 不能稳定区分好坏。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage102_bar_resolution_frontier_audit/qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_report_stage102_bar_resolution_frontier_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage102_bar_resolution_frontier_audit/qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_summary_stage102_bar_resolution_frontier_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage102_bar_resolution_frontier_audit/qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_decision_stage102_bar_resolution_frontier_audit_v1.json`
- resolution rows：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage102_bar_resolution_frontier_audit/qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_resolution_rows_stage102_bar_resolution_frontier_audit_v1.csv`
- bucket summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage102_bar_resolution_frontier_audit/qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_bucket_summary_stage102_bar_resolution_frontier_audit_v1.csv`
- event timing summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage102_bar_resolution_frontier_audit/qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_event_timing_summary_stage102_bar_resolution_frontier_audit_v1.csv`
- promotion gate：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage102_bar_resolution_frontier_audit/qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_promotion_gate_stage102_bar_resolution_frontier_audit_v1.csv`
- atlas manifest：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage102_bar_resolution_frontier_audit/qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_atlas_manifest_stage102_bar_resolution_frontier_audit_v1.csv`
- charts：
  - `qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_official_path_chart_stage102_bar_resolution_frontier_audit_v1.png`
  - `qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_bucket_contribution_chart_stage102_bar_resolution_frontier_audit_v1.png`
  - `qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_bucket_summary_chart_stage102_bar_resolution_frontier_audit_v1.png`
  - `qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_promotion_gate_chart_stage102_bar_resolution_frontier_audit_v1.png`
  - `atlas_page001` 至 `atlas_page006`

## 结论

- 本阶段结论：分钟 OHLC 继续承载近触价执行敏感候选的基础不足；Stage102 不进入 true engine，不触发 A/B。
- 原因：
  - `68` 笔 C9 stop/progress 在首根扫描K发生，没有可用的已闭合分钟K让规则先判断再执行。
  - `25` 笔会发生 close signal -> next bar execution 与 C9 事件同根碰撞。
  - 低分辨率区净 PnL 为正且包含 `7` 个右尾样本；任何“早期降低风险/退出”的 OHLC 规则都会先伤右尾，再谈不上收益保留 `80%+`。
  - 同一低分辨率区也含 `5` 个 bottom-loss，说明 OHLC 本身不能把大亏和右尾分开。
- 下一步：不要再从 Stage100/101/102 的 OHLC 近触价 bucket 中救窗口或阈值。若继续分钟级目标，应优先推进 Stage099 的授权盘口/队列/成交流数据工程路线；若暂不做数据工程，只能提出远离触价、非 close 后立即成交、不会切断首根/第二根右尾的新第一性候选。

## 过拟合反思

- 运行前判断：否。Stage102 预先固定为执行分辨率诊断，不按收益好坏挑窗口。
- 运行后判断：否。结果没有把 `first_bar`、`one_bar` 或 `gt_five` 任何桶交易化，也没有利用 `same_bar_stop_progress=0` 强行 promotion。
- 原因：bucket 由事件可行动性定义，不由最终盈亏、品种、方向、年份或月份定义；结论是阻断 OHLC 近触价路线，而不是提出收益优化规则。

## 继续价值反思

- 运行前判断：有价值。Stage101 关闭 absorption/reclaim 后，需要判断继续在分钟K内挖近触价候选是否还值得。
- 运行后判断：OHLC 近触价路线继续价值低；研究线继续有价值，但应切到更细数据或换成不依赖当前分钟内顺序的候选。
- 原因：低分辨率区覆盖 `93/219` 笔，而且同时承载右尾与底部亏损；继续用同一颗粒度调参很可能过拟合且损伤右尾。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage102 摘要和下一步边界。
- 是否更新 `research/registry.md`：否，不是正式候选、重要突破或路线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，不是正式候选、重要突破或跨线合并。
