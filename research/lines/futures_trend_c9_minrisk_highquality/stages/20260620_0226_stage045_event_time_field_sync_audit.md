# Stage045 Event Time Field Sync Audit

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 02:26 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：replay 时间与字段同步审计 / 不生成交易规则
- 是否重要突破：否，属于分钟 replay 基础设施验收，不是收益突破
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Backtrader order 文档：`https://www.backtrader.com/docu/order/`
  - Backtrader order creation/execution 文档：`https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/`
  - NautilusTrader backtesting 文档：`https://nautilustrader.io/docs/latest/concepts/backtesting/`
  - vn.py `BarGenerator` 源码：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py`
  - SHFE trading hours：`https://www.shfe.com.cn/eng/reports/CalendarHolidays/TradingHours/`
- 我的判断：
  - 分钟 replay 要先证明 event family、event time、price 和 bar index 与官方引擎同步；否则任何分钟形态都可能只是执行账本偏差。
  - Stage044 已解决 C2 stop 价格语义，Stage045 的职责不是找收益，而是验证“类型对了以后，时间和字段也确实对了”。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage045_event_time_field_sync_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；固定审计变体 `stage827_directional_c2_stop_start0_stop_first`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage043/Stage044 timestamp-ready 子集和 Stage010 官方 intraday events
- 账户规模：`150000`
- 成本口径：沿用官方曲线，`total_slippage=2,730,130`
- 样本过滤：Stage044 official semantics variant，共 `219` 笔 timestamp-ready initial orders
- 策略/归因口径：
  - 官方正式版：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
  - 审计口径：用 Stage010 official intraday events 作为时间/价格/事件字段权威源；用 Stage044 official semantics replay 作为对照。
  - 不改变开仓、平仓、手数、资金路径；same-exit 曲线只用于证明语义审计没有改变策略收益。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - timestamp-ready orders：`219`
  - event family match：`219/219 = 100.0000%`
  - source event expected/found：`89/89`
  - no-event source clean：`130/130`
  - required time fields exact：`136/136 = 100.0000%`
  - required price fields exact：`419/419 = 100.0000%`
  - required C9 bar-index fields exact：`125/125 = 100.0000%`
  - full event sync exact：`219/219 = 100.0000%`
  - event family 分布：
    - `no_intraday_event/open_no_intraday_event`：`130`
    - `c9_flat_no_reentry`：`47`
    - `c9_flat_retry_failed`：`16`
    - `c9_open_after_reentry`：`15`
    - `c2_stop`：`11`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage045_event_time_field_sync_audit/qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_report_stage045_event_time_field_sync_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage045_event_time_field_sync_audit/qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_summary_stage045_event_time_field_sync_audit_v1.csv`
- orders：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage045_event_time_field_sync_audit/qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_event_sync_ledger_stage045_event_time_field_sync_audit_v1.csv`
- daily：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage045_event_time_field_sync_audit/qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_path_chart_stage045_event_time_field_sync_audit_v1.png`
- quality：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage045_event_time_field_sync_audit/qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_field_sync_chart_stage045_event_time_field_sync_audit_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage045_event_time_field_sync_audit/qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_timeline_atlas_stage045_event_time_field_sync_audit_v1.png`

## 结论

- 本阶段结论：
  - Stage044 official semantics variant 已与 Stage010 官方 intraday events 在 event family、必要时间字段、价格字段和 C9 bar index 上全部精确同步。
  - 这说明 timestamp-ready 子集可以作为后续分钟规则真实回放的底座；但只覆盖 `219` 笔 timestamp-ready initial orders，`105` 笔 fallback/no-proxy 初始订单仍不能被硬补为可执行分钟账本。
  - 本阶段没有发现可交易信号，不进入候选策略、不触发 A/B。
- 是否进入下一步：进入下一阶段候选设计前置；不进入正式候选。
- 下一步：
  - 可以在已校准的 timestamp-ready 子集上重新提出一个普世、预声明、非残差样本驱动的分钟执行候选。
  - 候选必须显式处理 `timestamp_ready` 覆盖边界：缺 raw proxy 的 `105` 笔保持官方路径或另做数据工程，不能用最终收益补 timestamp。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有调参、没有筛品种/方向/年份、没有按收益结果选择样本。
  - 对齐依据来自官方 Stage010 intraday events 和 Stage827/Stage847 执行语义；结果是账本同步，不是历史绩效优化。
  - 视觉输出只验证资金路径未改变、事件 marker 重合，不构成交易信号。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有。
- 原因：
  - event replay 从 Stage038 的原型不稳定推进到 timestamp-ready 子集 `100%` 字段同步，已经具备做下一条分钟候选的基础。
  - 继续价值不在继续修 residual，而在用这个底座测试真正第一性原则的候选：高质量信号时用最小额外风险承接，不能再从 mismatch 样本反推规则。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage045 结论与下一步。
- 是否更新 `research/registry.md`：否，本阶段不是重要突破、正式候选、路线废弃或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是线内 replay 基础设施验收，不是重要合入摘要。
