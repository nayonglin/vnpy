# Stage176 point-in-time 特征材料化闸门审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 03:52 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：point-in-time 特征材料化可行性审计；不是策略版本
- 是否重要突破：否。它阻断了直接写真 feature table 的错误路径，避免未来泄漏。
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - pandas rolling window：`https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html`
  - pandas windowing operations：`https://pandas.pydata.org/docs/user_guide/window.html`
  - W3C PROV-DM：`https://www.w3.org/TR/prov-dm/`
  - Apache Arrow/Parquet metadata：`https://arrow.apache.org/docs/python/generated/pyarrow.parquet.RowGroupMetaData.html`
  - vn.py BarData/TickData：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py`
- 我的判断：Stage153/156 的数据完整和合同 readiness 只是说明“数据可读且字段齐”，不等于“可在入场决策时点无泄漏地计算”。rolling 特征必须严格限制在 `decision_ts` 之前；event/session 窗口中满足 30m/60m 的样本不能反向当成入场前信息。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage176_point_in_time_feature_materialization_gate.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage153 已验收的 `233` 个 request / `657` 个窗口。
- 账户规模：沿用官方 C9 路径统计，不改变资金口径。
- 成本口径：沿用官方 C9 路径统计，`total_slippage=2730130.0`。
- 样本过滤：不按盈亏/年份/品种筛选；按窗口类型定义 point-in-time context：
  - `entry_pre30_post120`：`decision_ts = window_start_ts + 30m`，作为唯一 entry decision context。
  - `event_buffer_15m`：`decision_ts = window_start_ts + 15m`，只作 event diagnostic，不允许作为入场规则。
  - `session_guard_to_event_or_240m`：`decision_ts = window_start_ts`，只作 session path diagnostic，不允许作为入场规则。
- 策略/归因口径：不写 feature table、不创建交易规则、不运行 true engine、不触发 A/B、不改变 official config、不连接 CTP、不调用 order API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130.0`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - Stage176：`decision=stage176_point_in_time_feature_materialization_blocks_entry_features_extend_predecision_lookback_no_rule`
  - `stage153_request_ready_count=233/233`
  - `stage153_window_coverage_pass_count=657/657`
  - `stage156_feature_ready_window_count=657/657`
  - `stage156_positioning_feature_ready_window_count=657/657`
  - `window_count=657`
  - `decision_timestamp_defined_count=657`
  - `entry_window_count=219`
  - `entry_one_min_ready_count=30/219`
  - `entry_core_30m_ready_count=0/219`
  - `entry_full_60m_ready_count=0/219`
  - `entry_feature_row_allowed_count=0/219`
  - `feature_table_row_written_count=0`
  - `strategy_rule_created=0`
  - `true_engine_run=0`
  - `ab_triggered=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage176_point_in_time_feature_materialization_gate/qmt_roll_stage176_c9_minrisk_point_in_time_feature_materialization_gate_report_stage176_point_in_time_feature_materialization_gate_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage176_point_in_time_feature_materialization_gate/qmt_roll_stage176_c9_minrisk_point_in_time_feature_materialization_gate_summary_stage176_point_in_time_feature_materialization_gate_v1.csv`
- feature lookback requirement：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage176_point_in_time_feature_materialization_gate/qmt_roll_stage176_c9_minrisk_point_in_time_feature_materialization_gate_feature_lookback_requirement_stage176_point_in_time_feature_materialization_gate_v1.csv`
- window materialization audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage176_point_in_time_feature_materialization_gate/qmt_roll_stage176_c9_minrisk_point_in_time_feature_materialization_gate_window_decision_materialization_audit_stage176_point_in_time_feature_materialization_gate_v1.csv`
- context summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage176_point_in_time_feature_materialization_gate/qmt_roll_stage176_c9_minrisk_point_in_time_feature_materialization_gate_context_readiness_summary_stage176_point_in_time_feature_materialization_gate_v1.csv`

## 视觉检查

- Stage176 5 张 PNG 均非空，像素跨度均为 `765`。
- 视觉判断：
  - closed-bar distribution 图显示 `entry_decision` 的 pre-decision closed bars 基本贴近 0，远低于 30m/60m 特征最低线；`event_diagnostic` 虽有部分满足，但不可作为入场前信息。
  - feature readiness matrix 显示 entry decision：`window_count=219`，`one_min_ready=30`，`core_30m_ready=0`，`full_60m_ready=0`，`entry_feature_row_allowed=0`。
  - gate matrix 中 Stage153/156 数据门通过，但 entry 30m/60m 和 entry feature row allowed 均失败，这是正确阻断。

## 结论

- 本阶段结论：当前权威分钟数据包完整，但 Stage152 原始窗口不是为“入场前 30m/60m 特征”设计的；如果严格禁止未来泄漏，不能直接材料化 Stage156 的完整特征表，更不能进入策略规则。
- 是否进入下一步：进入下一步数据合同修正，不进入策略规则。
- 下一步：优先新增一个 predecision lookback 扩展 manifest，给每个 entry decision 至少补足 `>=61` 根入场前 closed 1m bar；或者预声明一套更短 lookback 的极简 feature contract，但这条路线必须先证明普世性并继续防止 right-tail/bottom-loss/年份/品种反推。

## 过拟合反思

- 运行前判断：否。Stage176 审计的是时间可见性和最小 lookback，不看收益结果、不调阈值。
- 运行后判断：否。它阻断了更容易过拟合的错误路径，即用 event/session 后验窗口去构造入场前信号。
- 原因：point-in-time 是第一性约束；任何违反它的漂亮指标都不能作为策略证据。

## 继续价值反思

- 运行前判断：有。Stage156 合同 ready 后，必须验证真实 decision_ts 前是否可材料化，否则会把后验数据误当特征。
- 运行后判断：有。发现了一个关键结构缺口：数据包完整但 predecision lookback 不够。下一步补 lookback 比直接扫规则更有价值。
- 原因：目标要求“高质量信号时用最小风险搏最大收益”，高质量信号必须在入场前可见；当前数据窗口还不足以支持这一点。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage176 摘要。
- 是否更新 `research/registry.md`：否，非正式候选、非路线合并、非重大突破。
- 是否追加根目录 `memory.md/back_log.md`：否，非正式候选、非重大突破。
