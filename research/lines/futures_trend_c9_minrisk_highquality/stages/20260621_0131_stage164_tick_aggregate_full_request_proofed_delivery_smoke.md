# Stage164 tick 聚合完整 request proofed delivery smoke

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-21 01:31`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage152 单请求 raw/normalized/proof 三件套交付与 Stage160/153 验收
- 是否重要突破：否；这是数据工程单请求突破，不是策略收益/回撤突破，也不是正式候选
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk Backtest 文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html`
  - TqSdk API 文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html`
  - TqSdk DataDownloader 文档：`https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html`
  - TqSdk GitHub：`https://github.com/shinnytech/tqsdk-python`
- 我的判断：Stage163 已证明 TqSdk tick 回放可以聚合出真实分钟成交量；Stage164 的本质不是 alpha，而是把这个候选数据源推进到 Stage152/153 能验收的 raw/normalized/proof 三件套。Stage153 只接受 proof 身份、raw sha、schema、no-trade policy、forbidden marker 和 window coverage 都通过的数据，因此写入 `incoming/` 后必须立即跑 Stage160/153，不能把“脚本写了文件”当作有效数据。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage164_tick_aggregate_full_request_proofed_delivery_smoke.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增 `STAGE164_REQUEST_ID`、`STAGE164_WRITE_INCOMING`、`STAGE164_OVERWRITE_EXISTING`、`STAGE164_MAX_SECONDS_TICK`、`STAGE164_TICK_DATA_LENGTH`、`STAGE164_MIN_NORMALIZED_ROWS` 等数据交付参数。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：单请求 `stage152_req_0011_jm2509_DCE_20250709`，Stage152 request 窗口 `2025-07-09 08:30:00` 至 `2025-07-09 14:03:00`；tick 查询 `2025-07-09 08:15:00` 至 `2025-07-09 14:04:00`。
- 账户规模：沿用当前研究线官方路径口径。
- 成本口径：沿用 Stage160/161/162/163 官方路径总滑点口径；本阶段不运行新回测。
- 样本过滤：沿用 Stage162/163 同一 request，不按收益、回撤、品种、方向、年份挑样本。
- 策略/归因口径：`TqBacktest + get_tick_serial` 拉取 tick，按 `last_price` 聚合 1m OHLC，按 tick 累计 `volume/amount` 的非负差分聚合分钟成交量/成交额；写入 Stage152 expected raw/normalized/proof 三件套后，重跑 Stage160 和 Stage153 验收。不创建策略规则、不运行 true engine、不触发 A/B、不改变 official config、不连接 CTP、不调用 order API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - Stage164：
    - `decision=stage164_one_request_tick_aggregate_delivery_written_run_stage160_153_no_rule`
    - `next_best_action=rerun_stage160_then_stage153`
    - `request_id=stage152_req_0011_jm2509_DCE_20250709`
    - `tick_fetch_status=extracted`
    - `raw_tick_row_count=19339`
    - `normalized_row_count=170`
    - `positive_volume_row_count=169`
    - `positive_turnover_row_count=169`
    - `window_precheck_count=3`
    - `window_precheck_pass_count=3`
    - `expected_files_written=3`
    - `raw_written=1`
    - `normalized_written=1`
    - `proof_written=1`
    - `side_effect_count=1`
  - Stage160 复验：
    - `incoming_root_exists=1`
    - `present_expected_file_count=3/699`
    - `request_complete_triplet_count=1/233`
    - `request_missing_triplet_count=232`
    - `stage153_trigger_allowed=0`
    - `unexpected_file_count=0`
  - Stage153 复验：
    - `request_ready_count=1/233`
    - `raw_file_present_count=1`
    - `proof_file_present_count=1`
    - `normalized_file_present_count=1`
    - `proof_json_valid_count=1`
    - `proof_raw_sha256_match_count=1`
    - `proof_identity_match_count=1`
    - `proof_no_trade_policy_declared_count=1`
    - `normalized_schema_pass_count=1`
    - `forbidden_provenance_marker_count=0`
    - `window_coverage_pass_count=3/657`
    - `right_tail_window_coverage_pass_count=3/54`
    - `bottom_loss_window_coverage_pass_count=0/54`
    - `maxdd_window_coverage_pass_count=0/72`
    - `stage154_feature_build_allowed=0`
  - 安全/策略闸门：
    - `current_package_promotion_allowed=0`
    - `true_engine_allowed=0`
    - `strategy_feature_usable=0`
    - `objective_completion_proven=0`
    - `official_config_changed=0`
    - `strategy_rule_created=0`
    - `true_engine_run=0`
    - `order_api_called=0`
    - `ctp_connected=0`

## 输出文件

- Stage164 report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage164_tick_aggregate_full_request_proofed_delivery_smoke/qmt_roll_stage164_c9_minrisk_tick_aggregate_full_request_proofed_delivery_smoke_report_stage164_tick_aggregate_full_request_proofed_delivery_smoke_v1.md`
- Stage164 summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage164_tick_aggregate_full_request_proofed_delivery_smoke/qmt_roll_stage164_c9_minrisk_tick_aggregate_full_request_proofed_delivery_smoke_summary_stage164_tick_aggregate_full_request_proofed_delivery_smoke_v1.csv`
- Stage164 delivery audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage164_tick_aggregate_full_request_proofed_delivery_smoke/qmt_roll_stage164_c9_minrisk_tick_aggregate_full_request_proofed_delivery_smoke_delivery_audit_stage164_tick_aggregate_full_request_proofed_delivery_smoke_v1.csv`
- Stage164 window precheck：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage164_tick_aggregate_full_request_proofed_delivery_smoke/qmt_roll_stage164_c9_minrisk_tick_aggregate_full_request_proofed_delivery_smoke_window_precheck_stage164_tick_aggregate_full_request_proofed_delivery_smoke_v1.csv`
- Stage160 summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage160_authoritative_minute_arrival_monitor/qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_summary_stage160_authoritative_minute_arrival_monitor_v1.csv`
- Stage153 summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage153_authoritative_minute_ohlcv_intake_validator/qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator_summary_stage153_authoritative_minute_ohlcv_intake_validator_v1.csv`
- Stage153 request audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage153_authoritative_minute_ohlcv_intake_validator/qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator_request_file_audit_stage153_authoritative_minute_ohlcv_intake_validator_v1.csv`
- Stage153 window coverage：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage153_authoritative_minute_ohlcv_intake_validator/qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator_window_coverage_audit_stage153_authoritative_minute_ohlcv_intake_validator_v1.csv`
- incoming raw：`incoming/stage152_authoritative_minute_ohlcv/DCE/jm2509_DCE/20250709/stage152_req_0011_jm2509_DCE_20250709.raw.csv.zst`
- incoming normalized：`incoming/stage152_authoritative_minute_ohlcv/DCE/jm2509_DCE/20250709/stage152_req_0011_jm2509_DCE_20250709.normalized.parquet`
- incoming proof：`incoming/stage152_authoritative_minute_ohlcv/DCE/jm2509_DCE/20250709/stage152_req_0011_jm2509_DCE_20250709.proof.json`
- orders：无；本阶段禁止报单和 true engine。
- daily：无新增回测 daily；使用官方路径资金曲线图跟踪。
- quality：
  - Stage164 5 张 PNG 均非空；
  - Stage160 5 张 PNG 均非空；
  - Stage153 5 张 PNG 均非空。

## 视觉分析

- Stage164 官方路径图显示资金曲线/回撤/broker10 未改变；这是数据交付，不是收益候选。
- Stage164 OHLCV 图显示完整 request 内 1m tick 聚合价格和成交量连续可读，成交量不再是 Stage162 的全 0。
- Stage164 window precheck matrix 显示 3 个 right-tail 窗口全部通过：`entry_pre30_post120`、`event_buffer_15m`、`session_guard_to_event_or_240m`。
- Stage160 trigger gate 图显示到货从 `0/699` 推进到 `3/699`，但全包仍缺 `696` 个 expected files，不能自动触发下游。
- Stage153 window heatmap 显示只有这一个 request 的 3 个 right-tail windows 通过，其余 bottom-loss/maxDD/low-resolution 仍为空；这证明本阶段是“单点数据闸门突破”，不是策略或全包突破。

## 结论

- 本阶段结论：Stage164 成功把 Stage163 的 tick 聚合修复路径推进为一个 Stage152 request 的有效 raw/normalized/proof 三件套，并通过 Stage153 单请求 proof/schema/hash/window coverage。当前 `request_ready_count=1/233`、`window_coverage_pass_count=3/657`，全包仍不放行。
- 是否进入下一步：是，但下一步仍是数据交付扩展，不是策略。
- 下一步：按 Stage152 manifest 的优先级继续扩展 tick 聚合 proofed delivery，优先覆盖 right-tail、bottom-loss、maxDD 三类窗口；每批写入后必须重跑 Stage160/153。只有 Stage153 全包窗口覆盖、Stage156/157/158 lineage 与 feature table 闸门通过后，才允许进入只读 feature atlas 或分钟信号候选。

## 过拟合反思

- 运行前判断：否。Stage164 固定使用 Stage162/163 同一 request，只做完整数据交付，不按收益、回撤、品种、方向、年份筛选。
- 运行后判断：否，但后续扩展必须防止数据 transform 过拟合。
- 原因：本阶段没有产生交易规则，也没有运行 true engine；成功/失败标准来自 Stage153 的 proof、raw sha、schema、forbidden marker 和 window coverage。后续不能为了让更多 request 通过而调分钟边界、成交量差分或 no-trade policy。

## 继续价值反思

- 运行前判断：有。Stage163 已证明 tick 聚合有正量，但如果不写入并跑 Stage153，就无法证明它满足当前线权威分钟数据合同。
- 运行后判断：有。Stage164 把“可能可用的数据源”推进成了“单 request 可验收数据”，这是继续做分钟级高质量信号研究的必要前置。
- 原因：目标要求基于分钟级 K 线进出场且不能过拟合；当前最关键缺口是权威、点时化、可回溯的分钟 OHLCV。Stage164 正在补这个地基，但全包远未完成。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage164 摘要。
- 是否更新 `research/registry.md`：否，未新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否，非正式候选、非策略突破、非路线废弃；若后续批量覆盖核心窗口后再考虑追加。
