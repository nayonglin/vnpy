# Stage113 微观结构必需窗口覆盖验收

## 基本信息

- 时间：2026-06-20 17:13
- 工作模式：day
- 研究线：`futures_trend_c9_minrisk_highquality`
- 阶段性质：只读 required-window manifest 与覆盖校验器；不写真引擎、不新增交易规则、不触发 A/B、不改正式配置、不连接 CTP、不调用订单 API。
- 决策：`stage113_required_window_manifest_built_no_authorized_data_no_rule`
- 重要突破版本：否。它是 Stage112 的硬化版本，把覆盖从 manifest 自报总数推进到逐事件窗口验收。

## 开始前反思

- 是否在过拟合：否。本阶段不使用盈亏结果设计交易条件，只把 Stage108/Stage045 已有 timestamp-ready 订单转成未来授权数据必须覆盖的固定窗口。
- 是否还有价值继续：是。Stage112 仍依赖数据包 manifest 填写覆盖数量，Stage113 把覆盖要求拆成逐候选、逐事件窗口，能防止未来数据包只靠自报覆盖率进入规则预检。

## 外部调研与判断

- CME MDP 3.0 / MBOFD 资料显示，完整盘口重建依赖 Market by Order Full Depth 的增量事件、时间戳与 book management 处理，不能用日级或 L1 快照替代。
- Nasdaq TotalView-ITCH 规格强调用一系列订单消息追踪客户订单，含 day-unique order reference、timestamp、sequence/message continuity。判断：订单簿数据必须有事件连续性证据，不能只保存派生结果。
- Databento GLBX.MDP3 文档显示 MDP 3.0 有 nanosecond `ts_event` 与 `ts_recv` 等字段，并说明 MDP 3.0 提供 full granularity order event 与聚合深度数据。判断：Stage113 的窗口验收必须要求 `ts_event` 覆盖和 sequence gap 证明。
- 数据完整性通用原则要求覆盖目标问题的完整范围，否则缺口会引入偏差。判断：本线必须覆盖 right-tail、bottom-loss、maxDD context，而不是只覆盖容易拿到的普通样本。

调研结论：未来授权数据包不能只说“覆盖 95%”；必须证明每个 C9 关键候选窗口的 `vt_symbol + ts_event` span 覆盖，并提供 sequence gap 为 0 或等价 capture continuity proof。

参考链接：

- https://databento.com/docs/venues-and-datasets/glbx-mdp3
- https://www.cmegroup.com/market-data/distributor/market-data-platform.html
- https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/NQTVITCHSpecification.pdf
- https://montecarlo.ai/blog-what-is-data-completeness/

## 本阶段改动

- 新增工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage113_microstructure_required_window_coverage.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage113_microstructure_required_window_coverage/`
- 生成固定窗口清单：
  - `entry_quality_window`：所有 `219` 个 timestamp-ready 候选，`09:00` 前 `5` 分钟到后 `35` 分钟。
  - `event_touch_window`：Stage045 精确时间字段周围 `±120s`，包括 `first_stop_time`、`reentry_time`、`retry_failed_time`、`c2_hit_time`。
  - `session_no_event_guard`：`no_intraday_event` 样本从 `08:55` 到 `15:05`，防止缺数据伪装成无事件。
- 新增未来覆盖规则：
  - `manifest_span_covers_window_and_sequence_gap_zero`
  - 必须匹配 `vt_symbol`
  - 必须有 `ts_event` 或等价交易所事件时间
  - 必须有 sequence gap 为 `0` 或等价 capture continuity proof

## 参数与结果变更

- 新增参数：
  - `ENTRY_PRE_MINUTES=5`
  - `ENTRY_POST_MINUTES=35`
  - `EVENT_PRE_SECONDS=120`
  - `EVENT_POST_SECONDS=120`
  - `SESSION_GUARD_END_TIME=15:05:00`
  - `MAX_ROWS_PER_FILE=2,000,000`
- 修改参数：无。
- 删除参数：无。
- 新增回测结果：无真实回测；只复用当前路径资金曲线做窗口覆盖视觉图。
- 修改回测结果：无。
- 删除回测结果：无。

当前路径指标保持不变：

| 指标 | 数值 |
| --- | ---: |
| 期末权益 | 39,176,437.60 |
| 总收益 | 26017.6251% |
| 最大回撤 | -45.0827% |
| Sharpe | 1.6331 |
| 总滑点 | 2,730,130 |
| 总交易次数 | 787 |
| 胜率 | 36.0902% |
| broker10 峰值 | 111.7365% |

## 关键验收结果

| 项目 | 结果 |
| --- | ---: |
| required_candidate_count | 219 |
| required_window_count | 485 |
| entry_quality_window_count | 219 |
| event_touch_window_count | 136 |
| session_no_event_guard_window_count | 130 |
| visual_priority_window_count | 127 |
| right_tail_window_count | 36 |
| bottom_loss_window_count | 37 |
| maxdd_context_window_count | 58 |
| indexed_authorized_data_file_count | 0 |
| covered_window_count | 0 |
| covered_candidate_count | 0 |
| coverage_gate_pass_count | 0 / 7 |
| true_engine_allowed | 0 |
| strategy_feature_usable | 0 |

窗口类型覆盖：

| window_type | required | covered | coverage |
| --- | ---: | ---: | ---: |
| entry_quality_window | 219 | 0 | 0.0% |
| event_touch_window | 136 | 0 | 0.0% |
| session_no_event_guard | 130 | 0 | 0.0% |

## 视觉产物

- official path window coverage：`qmt_roll_stage113_c9_minrisk_microstructure_required_window_coverage_official_path_window_coverage_stage113_microstructure_required_window_coverage_v1.png`
- window count chart：`qmt_roll_stage113_c9_minrisk_microstructure_required_window_coverage_window_count_chart_stage113_microstructure_required_window_coverage_v1.png`
- coverage gate chart：`qmt_roll_stage113_c9_minrisk_microstructure_required_window_coverage_coverage_gate_chart_stage113_microstructure_required_window_coverage_v1.png`
- event hour chart：`qmt_roll_stage113_c9_minrisk_microstructure_required_window_coverage_event_hour_chart_stage113_microstructure_required_window_coverage_v1.png`

视觉观察：

- official path window coverage 图显示所有候选覆盖点都是红色，且覆盖权益台阶、2022 主回撤、broker10 尖峰和近端高位震荡，不是单一区间问题。
- window count chart 显示 `485` 个必需窗口全未覆盖，未来不能只拿少量 right-tail 或 bottom-loss 样本做微观规则。
- coverage gate chart 显示 `authorized_file_index_present`、`all_required_windows_covered`、`right_tail/bottom_loss/maxDD` 全部 blocked。
- event hour chart 显示事件窗口主要集中在 `09` 点，但也有 `21/22` 点夜盘事件；这说明日级覆盖或单一日盘窗口不够，必须用事件时间逐窗验收。

## 结论

Stage113 已把 Stage112 的覆盖目标细化为 `485` 个必需窗口。当前没有授权 intake 文件，因此所有 coverage gate 仍为 `0`。这不是策略候选，但它提高了未来数据接入的真实性：任何授权 MBO/L3 或 MBP-10/L2 数据包必须逐窗口覆盖后，才允许进入 Stage111/112 之后的只读规则预检。

本阶段继续证明：没有新授权数据前，不能把本地 Tq、Stage608/932、Stage449/861 或旧 OHLC 代理包装成微观结构规则。

## 后续规划和 TODO

1. 未来数据包放入 Stage112 固定 intake root 后，先跑 Stage112，再跑 Stage113。
2. Stage113 必须看到 `indexed_authorized_data_file_count > 0`、`covered_window_count=485`、right-tail/bottom-loss/maxDD 窗口全覆盖，且 sequence gap proof 为 0，才允许讨论下一阶段只读规则预检。
3. 若数据供应方无法提供 sequence gap 或 capture continuity proof，只能作为 TCA/forward-watch，不进入规则研究。

## 结束反思

- 是否在过拟合：否。本阶段只固定窗口和覆盖证明，未按历史收益切条件，也没有调参救路线。
- 是否还有价值继续：有，但继续价值仍在数据接入与验收。没有授权数据包时，继续做内部分钟 OHLC 候选会回到 Stage109 已关闭的过拟合路径。
