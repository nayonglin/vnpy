# Stage033 tick/真实成交量分钟源可行性审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：day
- 记录时间：2026-06-20 00:00
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读数据工程可行性审计；不新增交易规则，不改正式配置，不连接 CTP，不调用订单 API。
- 是否重要突破：否。结论重要但属于覆盖边界确认，不是候选突破。
- 是否触发A/B：否。`candidate_ready=0`，`ab_triggered=0`。

## 外部调研与判断

- 参考资料：
  - TqSdk `DataDownloader` 文档：https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html
  - TqSdk 介绍：https://doc.shinnytech.com/tqsdk/latest/intro.html
  - TqSdk GitHub：https://github.com/shinnytech/tqsdk-python
  - vn.py README：https://github.com/vnpy/vnpy/blob/master/README_ENG.md
- 我的判断：
  - TqSdk `DataDownloader` 技术上支持历史 tick CSV，`dur_sec=0` 为 tick 数据，但它是专业版/授权功能，本阶段不应在无凭据和无质检流程下直接下载并使用。
  - vn.py 的 `data_recorder` 说明框架可以实时记录 Tick/K 线到数据库，但这只能证明后续数据工程路径存在，不能证明当前仓库已有 Stage030 历史事件 tick 覆盖。
  - 当前 stop/retry 当根 OHLCV 规则的瓶颈不是参数，而是历史 tick/真实成交量分钟源缺失；继续在 Stage861 零 range/零 volume 或少量 smoke tick 上挖规则会制造伪信号。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage033_tick_source_feasibility_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `TICK_MATCH_TOLERANCE_SECONDS=60`
  - `DOWNLOAD_WINDOW_SECONDS_BEFORE=60`
  - `DOWNLOAD_WINDOW_SECONDS_AFTER=120`
  - TqSdk download plan 固定 `dur_sec=0`
  - `ACCOUNT_CAPITAL=150000`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用当前正式 C9/15w official closed lots 与 Stage030 stop/retry event 特征，事件覆盖 `2018-2026`。
- 账户规模：`150,000`。
- 成本口径：沿用官方 C9/15w 基准曲线与 Stage005/Stage030 成本口径；本阶段不新增交易、不重算滑点。
- 样本过滤：
  - Stage030 stop/retry event keys：`125`
  - event lots：`180`
  - event moments：`375`，包括 `first_stop/reentry/retry_failed`
  - 本地 tick 候选：`examples/portfolio_backtesting/backtest_outputs/*tick*.csv`
- 策略/归因口径：
  - 只识别本地 tick-like CSV schema，包括 `last_price/bid_price_1/ask_price_1/volume_delta` 与 `datetime`。
  - 检查 same symbol、same day、事件附近 `60s`、事件后 `60s` bar 重建，以及 `last_volume/volume_delta` 成交量线索。
  - 生成 TqSdk tick 下载计划，但不认证、不下载。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：closed-lot 胜率 `36.0902%`
- 其他关键指标：
  - stop/retry event net PnL：`-5,667,538.40`
  - 本地 `*tick*.csv` 文件：`55`
  - tick-like 文件：`22`
  - tick-like rows：`131`
  - tick-like symbols：`4`
  - Stage030 event moments：`375`
  - 本地 tick 可重建 bar 且有成交量线索：`0`
  - reentry moment slots：`125`
  - 真实重入时间可用：`54`
  - reentry 本地 tick 可重建 bar 且有成交量线索：`0`
  - TqSdk import：`1`
  - DataDownloader import：`1`
  - tick download plan rows：`205`
  - download_attempted：`0`
  - 决策：`stage033_tick_source_no_candidate_local_history_missing_download_plan_only`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage033_tick_source_feasibility_audit/qmt_roll_stage033_c9_minrisk_tick_source_feasibility_audit_report_stage033_tick_source_feasibility_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage033_tick_source_feasibility_audit/qmt_roll_stage033_c9_minrisk_tick_source_feasibility_audit_summary_stage033_tick_source_feasibility_audit_v1.csv`
- source summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage033_tick_source_feasibility_audit/qmt_roll_stage033_c9_minrisk_tick_source_feasibility_audit_source_summary_stage033_tick_source_feasibility_audit_v1.csv`
- tick catalog：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage033_tick_source_feasibility_audit/qmt_roll_stage033_c9_minrisk_tick_source_feasibility_audit_local_tick_file_catalog_stage033_tick_source_feasibility_audit_v1.csv`
- normalized ticks：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage033_tick_source_feasibility_audit/qmt_roll_stage033_c9_minrisk_tick_source_feasibility_audit_normalized_local_tick_rows_stage033_tick_source_feasibility_audit_v1.csv`
- event coverage：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage033_tick_source_feasibility_audit/qmt_roll_stage033_c9_minrisk_tick_source_feasibility_audit_event_tick_coverage_stage033_tick_source_feasibility_audit_v1.csv`
- download plan：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage033_tick_source_feasibility_audit/qmt_roll_stage033_c9_minrisk_tick_source_feasibility_audit_tqsdk_tick_download_plan_stage033_tick_source_feasibility_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage033_tick_source_feasibility_audit/qmt_roll_stage033_c9_minrisk_tick_source_feasibility_audit_decision_stage033_tick_source_feasibility_audit_v1.json`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage033_tick_source_feasibility_audit/qmt_roll_stage033_c9_minrisk_tick_source_feasibility_audit_path_tick_readiness_chart_stage033_tick_source_feasibility_audit_v1.png`
- catalog heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage033_tick_source_feasibility_audit/qmt_roll_stage033_c9_minrisk_tick_source_feasibility_audit_tick_catalog_year_heatmap_stage033_tick_source_feasibility_audit_v1.png`
- event heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage033_tick_source_feasibility_audit/qmt_roll_stage033_c9_minrisk_tick_source_feasibility_audit_event_tick_coverage_heatmap_stage033_tick_source_feasibility_audit_v1.png`
- tick sample chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage033_tick_source_feasibility_audit/qmt_roll_stage033_c9_minrisk_tick_source_feasibility_audit_local_tick_sample_chart_stage033_tick_source_feasibility_audit_v1.png`

## 视觉分析

- path chart：官方权益右尾仍在，但 stop/retry 事件累计贡献长期为负；本地 tick-ready 组没有出现，事件贡献只能落在 `no_local_tick_symbol/no_reentry_state/no_local_tick_event_day` 等不可用覆盖桶。
- catalog heatmap：本地 tick-like 行几乎全部集中在 `2026` 的 SimNow/live/smoke 文件，另有 `2025` 年 5 行 synthetic TCA 样本；这不是 `2018-2026` 历史事件 tick 库。
- event heatmap：`local_tick_bar_and_volume_ready` 为 `0`；`first_stop` 124 个为 `no_local_tick_symbol`，`reentry` 54 个真实重入时点也全部为 `no_local_tick_symbol`。
- tick sample chart：本地 live tick 样本能画出 last/bid/ask，说明 schema 本身可用；但下方 Stage030 事件年分布跨 `2018-2026`，当前样本无法覆盖历史回测事件。

## 结论

- 本阶段结论：当前工作区没有可用于 Stage030 stop/retry 历史事件重建的本地 tick/真实成交量分钟源。TqSdk 路径技术上可行，但必须先做授权下载和质量审计；不能用现有本地 tick smoke 文件或 Stage861 零 range 分钟源继续设计当根 body/range/volume 规则。
- 是否进入下一步：不进入候选、不进入 A/B、不接正式。
- 下一步：
  - 若继续 stop/retry，当且仅当先按 download plan 下载历史 tick/真实成交量分钟源，再复跑 Stage032/033 exact-bar 质量审计。
  - 若暂不下载，应停止 stop/retry 当根 OHLCV 分支，转向入场前可见、覆盖完整、非最终盈亏标签的外生风险源，或只做 forward watch。

## 过拟合反思

- 运行前判断：继续在当前 Stage861 零 range/零 volume 分钟源上挖重入当根 K 形态会过拟合，甚至是伪信号。
- 运行后判断：否，本阶段本身不过拟合。
- 原因：没有新增交易规则，没有根据盈亏调阈值，只审计数据覆盖与可重建性；结果是 `0` 个本地 tick-ready 事件时点，反而约束了继续过拟合的空间。

## 继续价值反思

- 运行前判断：有价值，但价值在数据源可行性，不在继续调 stop/retry 小规则。
- 运行后判断：有条件地有价值。
- 原因：TqSdk/vn.py 路径证明历史 tick/实时记录技术上存在，但当前工作区没有覆盖；只有拿到历史 tick 并通过质量审计后，stop/retry OHLCV 分支才值得继续。没有数据前，继续这个方向就是低质量消耗。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage033 结论和下一步边界。
- 是否更新 `research/registry.md`：否，本阶段非路线合入/废弃/正式候选。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段没有正式候选、重要突破或跨线合并。
