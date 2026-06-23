# Stage036 分钟成交时间戳可恢复性审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 00:40 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读数据工程/可恢复性审计，不新增交易规则
- 是否重要突破：否，属于关键数据前提澄清
- 是否触发A/B：否，未形成候选，不接正式版本

## 外部调研与判断

- 参考资料：
  - vn.py GitHub issue `#1918` 展示 BAR 模式 `cross_limit_order` 用当前 bar 的 low/high 判断成交、bar open 作为 best price：https://github.com/vnpy/vnpy/issues/1918
  - vn.py `utility.py` 的 `update_bar_daily_window` 会把完成的日线 bar datetime 归零到 `hour=0, minute=0, second=0`：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py
  - NautilusTrader 文档指出 bar-only 回测下 next-open/执行时序需要更细粒度数据或明确事件驱动，否则会有 look-ahead/时序问题：https://nautilustrader.io/docs/latest/concepts/backtesting/
  - NautilusTrader `#4063` 讨论用 bar decomposition 把 OHLC 拆成合成事件，说明 bar 级数据本身不能自然给出 intra-bar 真实事件顺序：https://github.com/nautechsystems/nautilus_trader/issues/4063
- 我的判断：
  - 当前 C9/15w 官方产物中的 `00:00:00` 更符合日线 bar 聚合/日线引擎 timestamp，而不是实际分钟成交时间。
  - 后续若继续分钟级开仓/恢复/减仓规则，必须先建立真实分钟执行回放账本；否则容易把日线占位、session 首根、clock bucket 当作“默会经验”，本质是数据结构过拟合。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage036_minute_execution_timestamp_recoverability_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage010 官方 C9/15w `2018-01-02` 至 `2026-06-15`
- 账户规模：`150,000`
- 成本口径：沿用 Stage010 官方口径，成本倍率 `1.0`
- 样本过滤：官方 closed lots 全量 `399` 笔；官方 trades / trade_events / intraday_events / entry_candidates 全量审计
- 策略/归因口径：
  - 只分类各产物时间字段为 `exact_intraday`、`daily_midnight_placeholder`、`date_only_placeholder`、`missing`
  - closed lot 通过 `open_trade_id` 回连 official open trade，判断是否能恢复真实开仓分钟
  - post-open 的 `hit_time/first_stop_time/reentry_time/retry_failed_time` 只作为路径事件覆盖，不代替初始开仓成交时间

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：closed-lot 胜率 `36.0902%`
- 其他关键指标：
  - official closed lots：`399`
  - open exact ready lots：`0`
  - open daily placeholder lots：`399`
  - open missing/unjoined lots：`0`
  - official open trade rows：`387`，`datetime/time` 均为 midnight placeholder
  - closed lots join open trades：`399`，`open_trade_datetime/open_trade_time` 均为 midnight placeholder
  - post-open exact event rows：`hit_time=14`、`first_stop_time=125`、`reentry_time=54`、`retry_failed_time=26`
  - artifact 总审计行数：`4862`；exact intraday rows `219` 只来自 post-open event 字段；daily midnight placeholder rows `3429`；date-only placeholder rows `877`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage036_minute_execution_timestamp_recoverability_audit/qmt_roll_stage036_c9_minrisk_minute_execution_timestamp_recoverability_audit_report_stage036_minute_execution_timestamp_recoverability_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage036_minute_execution_timestamp_recoverability_audit/qmt_roll_stage036_c9_minrisk_minute_execution_timestamp_recoverability_audit_summary_stage036_minute_execution_timestamp_recoverability_audit_v1.csv`
- orders：无
- daily：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage036_minute_execution_timestamp_recoverability_audit/qmt_roll_stage036_c9_minrisk_minute_execution_timestamp_recoverability_audit_contribution_curve_stage036_minute_execution_timestamp_recoverability_audit_v1.csv`
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage036_minute_execution_timestamp_recoverability_audit/qmt_roll_stage036_c9_minrisk_minute_execution_timestamp_recoverability_audit_artifact_timestamp_audit_stage036_minute_execution_timestamp_recoverability_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage036_minute_execution_timestamp_recoverability_audit/qmt_roll_stage036_c9_minrisk_minute_execution_timestamp_recoverability_audit_lot_timestamp_features_stage036_minute_execution_timestamp_recoverability_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage036_minute_execution_timestamp_recoverability_audit/qmt_roll_stage036_c9_minrisk_minute_execution_timestamp_recoverability_audit_intraday_event_coverage_stage036_minute_execution_timestamp_recoverability_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage036_minute_execution_timestamp_recoverability_audit/qmt_roll_stage036_c9_minrisk_minute_execution_timestamp_recoverability_audit_source_code_evidence_stage036_minute_execution_timestamp_recoverability_audit_v1.csv`
  - 资金/视觉图：
    - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage036_minute_execution_timestamp_recoverability_audit/qmt_roll_stage036_c9_minrisk_minute_execution_timestamp_recoverability_audit_open_timestamp_path_chart_stage036_minute_execution_timestamp_recoverability_audit_v1.png`
    - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage036_minute_execution_timestamp_recoverability_audit/qmt_roll_stage036_c9_minrisk_minute_execution_timestamp_recoverability_audit_artifact_timestamp_heatmap_stage036_minute_execution_timestamp_recoverability_audit_v1.png`
    - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage036_minute_execution_timestamp_recoverability_audit/qmt_roll_stage036_c9_minrisk_minute_execution_timestamp_recoverability_audit_intraday_event_timeline_stage036_minute_execution_timestamp_recoverability_audit_v1.png`

## 结论

- 本阶段结论：`stage036_minute_execution_timestamp_not_recoverable_from_current_artifacts`
- 是否进入下一步：是，但下一步必须先做真实分钟执行回放或转入场前外生源；不能继续用 daily placeholder 推导分钟规则。
- 下一步：
  - 构建 deterministic execution timestamp replay：把日线信号、下一可交易分钟、夜盘跨日、合约 session、C9 stop/retry post-open 事件统一到同一事件账本。
  - 如果暂不做执行回放，则只允许和真正入场前可见、覆盖完整的外生源做只读交叉，不再挖 `09:00/session/clock/open placeholder`。

## 过拟合反思

- 运行前判断：否，本阶段不是优化参数，而是在识别数据字段是否可用于分钟级规则。
- 运行后判断：否，脚本没有新增交易规则，也没有按历史盈亏筛选样本；它把所有时间字段按可恢复性硬分类。
- 原因：结论是“不能使用当前字段做分钟开仓规则”，这会减少过拟合空间；如果忽略该结论继续挖 session/clock，则才是过拟合。

## 继续价值反思

- 运行前判断：有价值，因为 Stage035 已证明 session/clock 图谱受 open time 占位限制，必须先确认能否恢复真实分钟成交时间。
- 运行后判断：有价值，但路线必须切换到数据工程或外生源；继续在当前 official trade ledger 上做分钟开仓形态没有价值。
- 原因：`399/399` 个 closed lot 只能回连到 daily placeholder，真实开仓分钟 `0` 个可得；post-open event 时间虽有价值，但只能服务 stop/retry 路径复盘，不能替代初始成交时间。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage036 约束。
- 是否更新 `research/registry.md`：否，本阶段不是正式候选、重要突破或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是本线数据边界审计，不是正式候选或合入摘要。
