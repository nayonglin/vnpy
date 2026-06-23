# Stage032 分钟源质量与替代源审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：day
- 记录时间：2026-06-19 23:48
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读数据质量审计；不新增交易规则、不改正式配置、不连接 CTP、不调用订单 API。
- 是否重要突破：否。它是止损/重入分钟源可用性边界确认，不是候选收益突破。
- 是否触发A/B：否。`candidate_ready=0`，没有可接入正式版或 A/B 的策略版本。

## 外部调研与判断

- 参考资料：
  - TqSdk 官方文档 `get_kline_serial()`/K线说明：`https://doc.shinnytech.com/tqsdk/latest/usage/mddatas.html`，K线 DataFrame 应包含 `datetime/open/high/low/close/volume/open_oi/close_oi`，且分钟周期用秒数 `60` 表示。
  - TqSdk `TqApi` reference：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html`，`get_kline_data_series` 同样返回 OHLC、成交量、起止持仓等字段。
  - vn.py GitHub `BarGenerator`：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py`，分钟 bar 由 tick 更新生成，逻辑上应有 high/low/close 与 open_interest 语义。
  - VeighNa 社区历史 K 线数据讨论：`https://www.vnpy.com/forum/topic/31048-postgresql-du-xie-da-liang-shu-ju-huan-man-wen-ti-de-xiu-gai`，本地数据库乱序/写入可导致 K 线跳变，历史数据质量必须审计。
  - TqSdk GitHub issue #498：`https://github.com/shinnytech/tqsdk-python/issues/498`，历史 K 线曾有时段异常反馈，不能把历史分钟K视为天然可靠。
- 我的判断：
  - 外部资料支持“分钟K规则必须先做 exact bar 质量审计”的原则。
  - 当前本地 Stage861 和 TqSDK raw 源都能给出 close-to-close 路径，但多数 stop/retry 关键当根没有可用 `high-low` 区间和成交量；因此不能把当根 body、区间收盘位置或量能扩张写成策略规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage032_minute_source_quality_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `LOCAL_WINDOW_BARS=20`，仅用于判断 exact bar 附近 close-to-close 路径是否可见，不是交易阈值。
  - 本地替代源：Stage859 gap backfill、Stage448 session rebuild、Stage504 fallback、Stage446 proxy extract。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage005/030 官方 C9/15w 只读路径，`2018-01` 至 `2026-06-15`。
- 账户规模：`150,000`。
- 成本口径：官方曲线原始成本口径，未新增滑点或交易。
- 样本过滤：只审计 Stage030 stop/retry event keys；共 `125` 个 event keys、`180` 个 event lots。
- 策略/归因口径：对 `first_stop`、`reentry`、`retry_failed` 三类事件时点，逐源检查 exact bar、same-day coverage、range、body、volume、OI delta 和前后窗口 close path。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：closed-lot 胜率 `36.0902%`
- 其他关键指标：
  - stop/retry event keys：`125`，event lots：`180`，净 PnL `-5,667,538.40`。
  - reentry event keys：`54`，净 PnL `265,710.60`。
  - Stage861 reentry exact bar：`54/54`；range ready：`0/54`；volume ready：`0/54`；window close-path ready：`54/54`。
  - 本地替代源最好口径下 reentry range ready：`0`；volume ready：`0`；local better than Stage861：`0`。
  - Stage861 first_stop exact bar：`125/125`；range ready：`4/125`；volume ready：`4/125`。
  - `reentry_exact_zero_range_no_volume_path_ready`：`54` 个 event keys、`109` lots、净 PnL `265,710.60`。
  - `no_reentry_state`：`71` 个 event keys、`71` lots、净 PnL `-5,933,249.00`。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage032_minute_source_quality_audit/qmt_roll_stage032_c9_minrisk_minute_source_quality_audit_report_stage032_minute_source_quality_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage032_minute_source_quality_audit/qmt_roll_stage032_c9_minrisk_minute_source_quality_audit_summary_stage032_minute_source_quality_audit_v1.csv`
- event source quality：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage032_minute_source_quality_audit/qmt_roll_stage032_c9_minrisk_minute_source_quality_audit_event_source_quality_stage032_minute_source_quality_audit_v1.csv`
- event best source：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage032_minute_source_quality_audit/qmt_roll_stage032_c9_minrisk_minute_source_quality_audit_event_best_source_stage032_minute_source_quality_audit_v1.csv`
- contribution curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage032_minute_source_quality_audit/qmt_roll_stage032_c9_minrisk_minute_source_quality_audit_quality_contribution_curve_stage032_minute_source_quality_audit_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage032_minute_source_quality_audit/qmt_roll_stage032_c9_minrisk_minute_source_quality_audit_path_quality_contribution_chart_stage032_minute_source_quality_audit_v1.png`
- source heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage032_minute_source_quality_audit/qmt_roll_stage032_c9_minrisk_minute_source_quality_audit_source_quality_heatmap_stage032_minute_source_quality_audit_v1.png`
- moment heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage032_minute_source_quality_audit/qmt_roll_stage032_c9_minrisk_minute_source_quality_audit_moment_quality_heatmap_stage032_minute_source_quality_audit_v1.png`
- minute atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage032_minute_source_quality_audit/qmt_roll_stage032_c9_minrisk_minute_source_quality_audit_source_comparison_atlas_page001-003_stage032_minute_source_quality_audit_v1.png`

## 结论

- 本阶段结论：`stage032_minute_source_quality_no_candidate_data_engineering_required`。
- 是否进入下一步：进入数据工程或换路线，不进入 true engine / A/B。
- 下一步：
  - 若继续 stop/retry 分支，先补 tick 或真实成交量分钟源，再复跑 exact bar 质量审计。
  - 若暂不补数据，停止 stop/retry 小变体，回到入场前可见、覆盖完整、与最终盈亏标签无关的外生风险源。

## 过拟合反思

- 运行前判断：直接在 Stage031 成功/失败重入形态上继续挖规则会过拟合，因为可见结构混杂且当根数据退化。
- 运行后判断：本阶段本身不过拟合。
- 原因：没有选择交易参数、没有使用未来盈亏写阈值，只审计数据质量。若在没有真实 range/volume 的情况下继续写 body/volume 规则，才会转为过拟合。

## 继续价值反思

- 运行前判断：有价值。分钟级目标的前提是分钟数据真实可用，先验上必须确认。
- 运行后判断：有价值，但价值转向“数据工程/路线切换”。
- 原因：Stage861 覆盖强但 exact candle 质量不足；本地 raw 源没有修复 reentry 当根 OHLCV。继续用当前源做 stop/retry 当根确认会消耗研究预算且偏离第一性原则。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage032 摘要与下一步边界。
- 是否更新 `research/registry.md`：否。无正式候选、无路线合并、无重要突破。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是本线内部数据质量审计，不属于重要突破或正式候选。
