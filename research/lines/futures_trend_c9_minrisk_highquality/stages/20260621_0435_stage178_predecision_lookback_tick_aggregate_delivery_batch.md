# Stage178 predecision lookback tick 聚合交付第一批

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 04:35 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage177 前置 lookback 数据交付第一批
- 是否重要突破：否，属于数据地基推进
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：TqSdk `get_tick_serial` / 历史行情文档、pandas rolling/window 文档、vn.py `BarGenerator`/tick-to-bar 语义。
- 我的判断：14 天前置窗口不能假设一次 tick 回放天然完整，必须小批量交付并用 `bar_end_ts <= decision_ts` 独立预检；priority class 只作为 Stage177 coverage obligation，不是交易过滤器。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage178_predecision_lookback_tick_aggregate_delivery_batch.py`
- 新增参数：`STAGE178_MAX_REQUESTS=4`、`STAGE178_MAX_SECONDS_TICK=240`、`STAGE178_TICK_DATA_LENGTH=10000`、`MIN_NORMALIZED_ROWS=61`、`MIN_POSITIVE_VOLUME_BARS=60`
- 修改/删除参数：无

## 回测/归因参数

- 数据区间：Stage177 最高优先级中 CZCE/DCE/GFEX/SHFE 各 1 个 `14` 自然日 lookback 请求
- 账户规模/成本口径：沿用当前线资金曲线，仅作视觉上下文
- 样本过滤：最高 priority_score `5`，交易所轮转；不按收益、年份、品种、方向、回撤结果筛选
- 策略/归因口径：只写 raw/normalized/proof 三件套；不写 feature table、不创建策略规则、不运行 true engine

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - `decision=stage178_predecision_lookback_tick_aggregate_delivery_written_wait_stage179_no_rule`
  - `selected_request_count=4`
  - `delivery_success_count=4`
  - `expected_files_written=12`
  - `raw_tick_row_count=1298286`
  - `normalized_row_count=11885`
  - `positive_volume_row_count=11885`
  - `window_precheck_pass_count=4/4`
  - `min_observed_predecision_closed_bar_count=2260`
  - `max_observed_predecision_closed_bar_count=3470`
  - `feature_table_row_written_count=0`
  - `strategy_rule_created=0`
  - `true_engine_run=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage178_predecision_lookback_tick_aggregate_delivery_batch/qmt_roll_stage178_c9_minrisk_predecision_lookback_tick_aggregate_delivery_batch_report_stage178_predecision_lookback_tick_aggregate_delivery_batch_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage178_predecision_lookback_tick_aggregate_delivery_batch/qmt_roll_stage178_c9_minrisk_predecision_lookback_tick_aggregate_delivery_batch_summary_stage178_predecision_lookback_tick_aggregate_delivery_batch_v1.csv`
- quality：selected/request status/delivery/window/gate CSV 与 5 张 PNG

## 结论

- 本阶段结论：第一批 `4` 个 Stage177 lookback 请求成功写入，且自检中每个请求在决策前闭合 bar 数远超 `61`。
- 是否进入下一步：是
- 下一步：必须跑 Stage179 独立验收，不能直接进入 feature table。

## 过拟合反思

- 运行前判断：否。只做统一数据交付，不从收益结果调规则。
- 运行后判断：否。第一批按交易所轮转和 Stage177 coverage obligation 选取，没有使用最终盈亏标签。
- 原因：数据合同推进不改变交易信号，不扫阈值。

## 继续价值反思

- 运行前判断：是。Stage177 已证明入场前数据不足。
- 运行后判断：是。第一批证明 14 天 tick 回放可交付，但成本高，必须由 Stage179 独立验收。
- 原因：没有点时化前置数据，无法进入高质量分钟信号研究。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
