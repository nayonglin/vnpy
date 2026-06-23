# Stage163 TqSdk tick 聚合分钟量能数据源诊断

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-21 01:23`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage162 零成交量后的数据源修复诊断
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk Backtest 文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html`
  - TqSdk API 文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html`
  - TqSdk DataDownloader 文档：`https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html`
  - TqSdk GitHub：`https://github.com/shinnytech/tqsdk-python`
- 我的判断：Stage162 的零成交量不是“合约没有成交”的证据，而是 `TqBacktest + get_kline_serial` 路径在 K 线/quote 语义下会出现 volume 为 0 的接口限制。官方文档说明 K 线字段本身包含成交量，但 `DataDownloader` 属于专业版历史下载能力；本地 Stage079 也证明 `TqBacktest + get_tick_serial` 能拿到历史 tick。因此本阶段应把 K 线路径作为负例、DataDownloader 作为权限诊断、tick 回放聚合作为下一步 proofed delivery 候选源。仍然不能把 tick 聚合直接当 alpha，必须经过 full-request raw/normalized/proof、Stage153 proof/schema/hash/window coverage。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage163_tqsdk_tick_to_minute_volume_source_diagnostic.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增 `STAGE163_REQUEST_ID`、`STAGE163_TICK_PROBE_MINUTES`、`STAGE163_MAX_SECONDS_TICK`、`STAGE163_RUN_DOWNLOADER`、`STAGE163_MAX_SECONDS_DOWNLOADER`、`STAGE163_TICK_DATA_LENGTH` 等数据诊断参数。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：单请求 `stage152_req_0011_jm2509_DCE_20250709`，Stage152 request 窗口 `2025-07-09 08:30:00` 至 `2025-07-09 14:03:00`；本阶段 tick probe 查询 `2025-07-09 08:15:00` 至 `2025-07-09 10:00:00`。
- 账户规模：沿用当前研究线官方路径口径。
- 成本口径：沿用 Stage160/161/162 官方路径总滑点口径；本阶段不运行新回测。
- 样本过滤：沿用 Stage162 同一 request，不按收益、回撤、品种、方向、年份挑样本。
- 策略/归因口径：三方法数据源诊断：Stage162 `get_kline_serial(60)` 作为负例，`TqBacktest + get_tick_serial` 聚合 1m OHLCV 作为候选修复路径，`DataDownloader(dur_sec=60)` 作为权限/直接 1m 下载诊断；不写 `incoming/`，不创建策略规则、不运行 true engine、不触发 A/B、不改变 official config、不连接 CTP、不调用 order API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - `decision=stage163_tick_aggregate_has_real_volume_prepare_full_request_proofed_delivery_no_rule`
  - `next_best_action=stage164_tick_aggregate_full_request_proofed_delivery_smoke`
  - `tqsdk_import_ok=1`
  - `tqsdk_version=3.9.4`
  - `credential_present=1`
  - `stage162_kline_loaded=1`
  - `stage162_kline_positive_volume_row_count=0`
  - `tick_fetch_status=extracted`
  - `tick_row_count=7057`
  - `tick_minute_row_count=61`
  - `tick_positive_volume_minute_count=60`
  - `tick_positive_turnover_minute_count=60`
  - `datadownloader_import_ok=1`
  - `datadownloader_status=failed`
  - `datadownloader_positive_volume_row_count=0`
  - `incoming_files_written=0`
  - `current_package_promotion_allowed=0`
  - `true_engine_allowed=0`
  - `strategy_feature_usable=0`
  - `objective_completion_proven=0`
  - `side_effect_count=0`
  - `visual_output_count=5`
  - `max_broker10_margin_to_equity_pct=111.7365%`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage163_tqsdk_tick_to_minute_volume_source_diagnostic/qmt_roll_stage163_c9_minrisk_tqsdk_tick_to_minute_volume_source_diagnostic_report_stage163_tqsdk_tick_to_minute_volume_source_diagnostic_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage163_tqsdk_tick_to_minute_volume_source_diagnostic/qmt_roll_stage163_c9_minrisk_tqsdk_tick_to_minute_volume_source_diagnostic_summary_stage163_tqsdk_tick_to_minute_volume_source_diagnostic_v1.csv`
- method audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage163_tqsdk_tick_to_minute_volume_source_diagnostic/qmt_roll_stage163_c9_minrisk_tqsdk_tick_to_minute_volume_source_diagnostic_method_audit_stage163_tqsdk_tick_to_minute_volume_source_diagnostic_v1.csv`
- tick fetch status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage163_tqsdk_tick_to_minute_volume_source_diagnostic/qmt_roll_stage163_c9_minrisk_tqsdk_tick_to_minute_volume_source_diagnostic_tick_fetch_status_stage163_tqsdk_tick_to_minute_volume_source_diagnostic_v1.csv`
- tick raw sample：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage163_tqsdk_tick_to_minute_volume_source_diagnostic/qmt_roll_stage163_c9_minrisk_tqsdk_tick_to_minute_volume_source_diagnostic_tick_raw_sample_stage163_tqsdk_tick_to_minute_volume_source_diagnostic_v1.csv`
- tick minute agg sample：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage163_tqsdk_tick_to_minute_volume_source_diagnostic/qmt_roll_stage163_c9_minrisk_tqsdk_tick_to_minute_volume_source_diagnostic_tick_minute_agg_sample_stage163_tqsdk_tick_to_minute_volume_source_diagnostic_v1.csv`
- DataDownloader status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage163_tqsdk_tick_to_minute_volume_source_diagnostic/qmt_roll_stage163_c9_minrisk_tqsdk_tick_to_minute_volume_source_diagnostic_datadownloader_status_stage163_tqsdk_tick_to_minute_volume_source_diagnostic_v1.csv`
- gate status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage163_tqsdk_tick_to_minute_volume_source_diagnostic/qmt_roll_stage163_c9_minrisk_tqsdk_tick_to_minute_volume_source_diagnostic_gate_status_stage163_tqsdk_tick_to_minute_volume_source_diagnostic_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage163_tqsdk_tick_to_minute_volume_source_diagnostic/qmt_roll_stage163_c9_minrisk_tqsdk_tick_to_minute_volume_source_diagnostic_decision_stage163_tqsdk_tick_to_minute_volume_source_diagnostic_v1.json`
- orders：无；本阶段禁止报单和 true engine。
- daily：无新增回测 daily；使用官方路径资金曲线图跟踪。
- quality：5 张 PNG 视觉产物均非空：
  - `qmt_roll_stage163_c9_minrisk_tqsdk_tick_to_minute_volume_source_diagnostic_official_path_source_repair_status_stage163_tqsdk_tick_to_minute_volume_source_diagnostic_v1.png`
  - `qmt_roll_stage163_c9_minrisk_tqsdk_tick_to_minute_volume_source_diagnostic_method_volume_comparison_stage163_tqsdk_tick_to_minute_volume_source_diagnostic_v1.png`
  - `qmt_roll_stage163_c9_minrisk_tqsdk_tick_to_minute_volume_source_diagnostic_tick_agg_minute_ohlcv_stage163_tqsdk_tick_to_minute_volume_source_diagnostic_v1.png`
  - `qmt_roll_stage163_c9_minrisk_tqsdk_tick_to_minute_volume_source_diagnostic_datadownloader_probe_stage163_tqsdk_tick_to_minute_volume_source_diagnostic_v1.png`
  - `qmt_roll_stage163_c9_minrisk_tqsdk_tick_to_minute_volume_source_diagnostic_gate_status_matrix_stage163_tqsdk_tick_to_minute_volume_source_diagnostic_v1.png`

## 视觉分析

- 官方路径图显示资金曲线、回撤曲线、broker10 曲线未改变；Stage163 只是数据源修复诊断，目标仍未完成。
- method comparison 显示 Stage162 K 线路径有 `169` 行但正成交量 `0`；tick 聚合路径有 `61` 根分钟，其中 `60` 根有正成交量；DataDownloader 路径无输出。
- tick agg OHLCV 图显示 09:00 后每分钟成交量明显非零，例如 09:00 分钟量 `8629`，说明“分钟量能无法取得”这个判断过强；真正问题是 K 线路径不合适，以及 tick 聚合尚未 full-request proofed。
- DataDownloader 图和 status 显示当前账号不支持历史数据下载功能：`您的账户不支持下载历史数据功能，需要购买后才能使用`，因此不能优先使用直接 1m 下载器。
- gate matrix 显示安全闸门通过：`incoming_files_written=0`、`strategy_rule_created=0`、`true_engine_run=0`、`order_api_called=0`；数据源修复闸门中 tick 正量通过，DataDownloader 正量失败。

## 结论

- 本阶段结论：Stage162 的 TqSdk K 线路径不是合格源，但 TqSdk tick 回放聚合 1m 有真实成交量和成交额，值得推进到 Stage164 的 full-request proofed delivery smoke。DataDownloader 因账号权限失败，当前不能作为直接 1m 源。
- 是否进入下一步：是，但下一步仍是数据交付，不是策略。
- 下一步：Stage164 应对同一个 request 跑完整 `08:30-14:03` tick 回放聚合，只有 raw/normalized/proof 三件套完整、hash/schema/proof 合规、正成交量覆盖通过时，才允许写入 expected `incoming/stage152_authoritative_minute_ohlcv/...`；写入后立即跑 Stage160/153 验收。未通过前不得进入 feature builder、true engine、A/B 或正式候选。

## 过拟合反思

- 运行前判断：否。Stage163 是接口/数据源诊断，不按收益、回撤、品种、方向或年份选择样本，不产生交易规则。
- 运行后判断：否，但下一步存在 transform 过拟合风险，必须压住。
- 原因：tick 聚合的正成交量只证明可构造分钟 OHLCV，不证明该 OHLCV 与策略执行语义完全同源；如果为了通过 Stage153 调整 tick 聚合口径、分钟边界或成交量差分规则，就会把数据 transform 过拟合成“可用证据”。

## 继续价值反思

- 运行前判断：有。Stage162 后如果只停在“volume=0”，会错过 tick 回放这条已被 Stage079 证明可行的通路。
- 运行后判断：有。Stage163 把阻塞从“没有真实分钟量能”推进到“需要 full-request tick 聚合 proofed delivery”。
- 原因：当前目标必须有分钟级进出场的可行动 K 线/量能数据；Stage163 证明有一个候选数据通道，但仍需 Stage164/Stage153 证明 lineage、schema、hash、窗口覆盖和 no-proxy/no-fixture。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage163 摘要。
- 是否更新 `research/registry.md`：否，未新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破、非正式候选、非路线废弃。
