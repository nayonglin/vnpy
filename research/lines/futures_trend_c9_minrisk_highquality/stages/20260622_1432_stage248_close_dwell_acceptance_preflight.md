# Stage248 close-dwell acceptance 只读预检

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-22 14:32`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读预检、分钟收盘停留结构、非触价排序机制复核
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Shi/Lian《Trend Following Strategies: A Practical Guide》：趋势跟随长期有效性来自合适时间尺度与风险纪律，短期回撤不可被简单规避。<https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5140633>
  - Nevmyvaka/Kearns/Papandreou/Sycara《Electronic Trading in Order-Driven Markets: Efficient Execution》：执行效果依赖微观结构和历史订单簿 what-if，不能只靠粗粒度价格条替代成交机制。<https://www.cis.upenn.edu/~mkearns/papers/optexec.pdf>
  - OFR/CFTC《Effects of Limit Order Book Information Level on Market Stability Metrics》：高保真订单流与盘口信息能提供价格稳定性信号，分钟 OHLC 不足以刻画同一分钟内的真实先后。<https://www.financialresearch.gov/working-papers/files/OFRwp2014-09_PaddrikHayesSchererBeling_EffectsLimitOrderBookInformationLevelMarketStabilityMetrics.pdf>
  - GitHub `PyTrendFollow`：公开趋势跟随框架强调多合约、回测、数据源和执行接入，支持把分钟层定位为执行/风控层而非替代上游趋势 alpha。<https://github.com/chrism2671/PyTrendFollow>
- 我的判断：
  - Stage247 已关闭 formal feature 单变量路线，继续挖单特征阈值会过拟合。
  - Stage102 已证明分钟 OHLC 同根触价顺序不足，所以本阶段只用分钟收盘相对入场价的停留结构，避开 high/low 先后排序。
  - close-dwell 是更接近“价格是否被市场接受”的执行层概念，但没有盘口/订单流时仍只能做只读预检，不能直接交易化。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage248_close_dwell_acceptance_preflight.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `DWELL_WINDOW_BARS=30`
  - `MIN_DWELL_BARS=6`
  - `MAJORITY_RATIO=2/3`
  - 固定状态：`positive_acceptance_dwell`、`underwater_acceptance_dwell`、`two_sided_chop_dwell`、`mixed_or_neutral_dwell`、`short_runway_le5_no_dwell`、`first_bar_event_no_closed_dwell`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage045/Stage100 的 `219` 个 timestamp-ready replay order。
- 账户规模：沿用官方 C9/15w 曲线，初始权益 `150,000`。
- 成本口径：沿用官方曲线；本阶段没有新增交易、滑点或手续费。
- 样本过滤：
  - 只使用官方 replay open 到 C9 first event 或日终之前的分钟序列。
  - close-dwell 分类只看分钟收盘相对入场价的方向性 R，不用同根 high/low 先后。
  - 少于 6 根可观察分钟或首根即 C9 event 的订单单独归类，不强行补证据。
- 策略/归因口径：
  - 本阶段不创建交易规则，不运行 true engine，不触发 A/B。
  - 只用官方 order realized PnL 做状态贡献和视觉反例归因。

## 结果

- 期末权益：`39,176,437.60`，官方路径未变
- 总收益：`26017.6251%`，官方路径未变
- 最大回撤：`-45.0827%`，官方路径未变
- Sharpe：`1.6331`，官方路径未变
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - `decision=stage248_close_dwell_acceptance_mixed_tail_conflict_no_rule`
  - `timestamp_ready_order_count=219`
  - `dwell_state_count=6`
  - `adequate_dwell_order_count=105`
  - `positive_acceptance_order_count=44`
  - `positive_acceptance_pnl_sum=18,474,002.50`
  - `positive_acceptance_right_tail_count=7`
  - `positive_acceptance_bottom_loss_count=0`
  - `underwater_acceptance_order_count=39`
  - `underwater_acceptance_pnl_sum=-189,233.40`
  - `underwater_acceptance_right_tail_count=2`
  - `underwater_acceptance_bottom_loss_count=5`
  - `right_tail_visual_count=18`
  - `bottom_loss_visual_count=18`
  - `maxdd_context_order_count=24`
  - `pnl_mixed_state_count=6`
  - `tail_conflict_state_count=3`
  - `promotion_gate_count=6`
  - `promotion_gate_pass_count=2`
  - `strategy_rule_created=0`
  - `true_engine_run=0`
  - `ab_triggered=0`
  - `official_config_changed=0`
  - `ctp_connected=0`
  - `order_api_called=0`

## 图像分析

- 官方资金/回撤叠加图：
  - 状态点分布在高权益台阶、2022-2023 回撤段和近端样本，不是单一年份或单一行情。
  - `positive_acceptance_dwell` 出现在重要右尾区间，但 `first_bar_event_no_closed_dwell`、`short_runway_le5_no_dwell`、`underwater_acceptance_dwell` 也出现在权益台阶附近。
- 状态贡献曲线：
  - `positive_acceptance_dwell` 是最强正贡献桶，2025 后贡献快速上升，说明 close-dwell 有解释价值。
  - `first_bar_event_no_closed_dwell` 和 `short_runway_le5_no_dwell` 也是大正贡献桶，分别贡献约 `10,324,498` 和 `5,120,311`，这会阻断“先等 dwell 证据再恢复风险”的规则。
  - `underwater_acceptance_dwell` 总体接近微负，但内部同时包含右尾和底部亏损，不是稳定坏信号。
- dwell/event matrix：
  - 正贡献主要绑定 C9 `progress`，`positive_acceptance + progress` 贡献约 `19,953,245`。
  - 但 `first_bar + progress` 贡献约 `12,355,060`，`short_runway + progress` 贡献约 `6,340,934`，`underwater + progress` 也有约 `3,670,130`。
  - 这说明 close-dwell 更像 C9 progress 之后的路径分层，不是独立可提前决策的 alpha。
- atlas：
  - `jm2401.DCE`、`OI305.CZCE` 是首根事件右尾，几乎不给 close-dwell 观察时间。
  - `OI309.CZCE` 是短跑道右尾，不能被 30-bar dwell 捕捉。
  - `jm2509.DCE`、`au2510.SHFE` 是漂亮的 positive-dwell 右尾，说明该标签有复盘价值。
  - `SH405.CZCE` 被归为 `underwater_acceptance_dwell` 但最终是 right-tail 大赢家，直接反证“水下停留就是坏信号”。
  - `cu2307.SHFE`、`lh2411.DCE`、`ru2409.SHFE` 展示底部亏损确实常有 underwater/chop 形态，但坏样本也分散在 short-runway 和 mixed 状态。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage248_close_dwell_acceptance_preflight/qmt_roll_stage248_c9_minrisk_close_dwell_acceptance_preflight_report_stage248_close_dwell_acceptance_preflight_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage248_close_dwell_acceptance_preflight/qmt_roll_stage248_c9_minrisk_close_dwell_acceptance_preflight_summary_stage248_close_dwell_acceptance_preflight_v1.csv`
- orders：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage248_close_dwell_acceptance_preflight/qmt_roll_stage248_c9_minrisk_close_dwell_acceptance_preflight_dwell_rows_stage248_close_dwell_acceptance_preflight_v1.csv`
- daily：沿用官方曲线，本阶段未生成新 daily
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage248_close_dwell_acceptance_preflight/qmt_roll_stage248_c9_minrisk_close_dwell_acceptance_preflight_decision_stage248_close_dwell_acceptance_preflight_v1.json`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage248_close_dwell_acceptance_preflight/qmt_roll_stage248_c9_minrisk_close_dwell_acceptance_preflight_state_summary_stage248_close_dwell_acceptance_preflight_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage248_close_dwell_acceptance_preflight/qmt_roll_stage248_c9_minrisk_close_dwell_acceptance_preflight_state_event_summary_stage248_close_dwell_acceptance_preflight_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage248_close_dwell_acceptance_preflight/qmt_roll_stage248_c9_minrisk_close_dwell_acceptance_preflight_promotion_gate_stage248_close_dwell_acceptance_preflight_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage248_close_dwell_acceptance_preflight/qmt_roll_stage248_c9_minrisk_close_dwell_acceptance_preflight_atlas_manifest_stage248_close_dwell_acceptance_preflight_v1.csv`

## 结论

- 本阶段结论：
  - close-dwell acceptance 比单变量 formal feature 更接近执行层本质，有复盘和 forward-watch 价值。
  - 但它没有通过交易化闸门：右尾有 `11/18` 不在 `positive_acceptance_dwell`，底部亏损有 `12/18` 不在 underwater/chop，`6/6` 状态都存在正负 PnL 混合，`3` 个状态同时含 right-tail 与 bottom-loss。
  - 因此本阶段不进入 true engine、不触发 A/B、不创建策略规则。
- 是否进入下一步：进入，但不继续调 close-dwell 窗口或比例。
- 下一步：
  - close-dwell 只保留为 forward-watch 标签。
  - 若继续“最小风险搏最大收益”，下一步应找能处理首根/短跑道右尾的新机制：真实执行回放/盘口订单流、C9 progress 事件前的可行动数据、或账户级风险预算，而不是延后等 30-bar 证据。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：当前阶段否；若继续调 `30` 根、`6` 根、`2/3` 比例则会过拟合。
- 原因：
  - 本阶段是从 Stage247 关闭单变量路线后，换机制层级做只读预检。
  - 分类只用预声明 close-dwell 状态，不根据结果调整窗口、比例、年份、品种、方向或交易所。
  - 结论主动阻断交易化，没有把贡献最漂亮的 `positive_acceptance_dwell` 救成规则。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有研究价值，但没有直接交易化价值。
- 原因：
  - 有价值：明确 close-dwell 是一个解释/观察标签，并且比单变量更符合“价格接受”的第一性直觉。
  - 无直接交易化价值：它无法保护首根/短跑道右尾，也无法独立隔离底部亏损。
  - 继续方向必须转向更高信息层级或账户层，而不是继续在 close-dwell 内部扫参。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage248 摘要。
- 是否更新 `research/registry.md`：否，本阶段不是重要突破或正式候选。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、路线废弃正式合入、正式候选或跨线合并。
