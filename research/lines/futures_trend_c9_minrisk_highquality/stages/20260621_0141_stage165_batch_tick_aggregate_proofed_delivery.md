# Stage165 批量 tick 聚合 proofed delivery

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-21 01:41`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage152 批量 raw/normalized/proof 三件套交付，并重跑 Stage160/153 验收
- 是否重要突破：否；这是数据地基从 1 个 request 扩展到 6 个 request，不是策略收益/回撤突破，也不是正式候选
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk Backtest 文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html`
  - TqSdk API 文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html`
  - TqSdk DataDownloader 文档：`https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html`
  - TqSdk GitHub：`https://github.com/shinnytech/tqsdk-python`
- 我的判断：官方文档口径确认，若只订阅 K 线而没有 tick，回测生成的 quote 可能没有真实成交额且成交量为 0；订阅 tick 时 quote/tick 路径包含成交量、成交额和持仓量字段。因此 Stage165 继续沿 Stage163/164 的 tick 聚合路线，而不是回到 Stage162 的 K 线零成交量路径。DataDownloader 属于专业版历史下载能力，当前账号路径不可作为批量交付前提；tick replay 聚合可以作为候选数据源，但每个 request 必须生成 raw sha、proof、normalized parquet 并由 Stage153 验收。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage165_batch_tick_aggregate_proofed_delivery.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增 `STAGE165_MAX_REQUESTS`、`STAGE165_WRITE_INCOMING`、`STAGE165_OVERWRITE_EXISTING`、`STAGE165_MAX_SECONDS_TICK`、`STAGE165_TICK_DATA_LENGTH`、`STAGE165_MIN_NORMALIZED_ROWS` 等数据交付参数。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：本阶段批量交付 5 个缺失 request：`stage152_req_0014_fu2209_SHFE_20220706`、`stage152_req_0004_OI305_CZCE_20230310`、`stage152_req_0005_OI309_CZCE_20230628`、`stage152_req_0009_jm2401_DCE_20231103`、`stage152_req_0010_jm2405_DCE_20240329`。
- 账户规模：沿用当前研究线官方路径口径。
- 成本口径：沿用 Stage160/153 官方路径总滑点口径；本阶段不运行新回测。
- 样本过滤：固定选择策略为 `missing_stage153_ready_then_priority_score_desc_window_counts_desc_request_id_asc_not_pnl`，只看 Stage152 manifest 的缺失状态、priority score、窗口数量和 request_id，不看收益、回撤、胜负或品种表现。
- 策略/归因口径：复用 Stage164 的 `TqBacktest + get_tick_serial`，按 `last_price` 聚合 1m OHLC，按 tick 累计 `volume/amount` 的非负差分聚合分钟成交量/成交额；写入 Stage152 expected raw/normalized/proof 三件套后，重跑 Stage160 和 Stage153 验收。不创建策略规则、不运行 true engine、不触发 A/B、不改变 official config、不连接 CTP、不调用 order API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - Stage165：
    - `decision=stage165_batch_tick_aggregate_delivery_written_run_stage160_153_no_rule`
    - `next_best_action=rerun_stage160_then_stage153`
    - `ready_before_count=1`
    - `remaining_before_count=232`
    - `selected_request_count=5`
    - `credential_present=1`
    - `fetch_attempted_count=5`
    - `fetch_extracted_count=5`
    - `delivery_success_count=5`
    - `expected_files_written=15`
    - `raw_written_count=5`
    - `normalized_written_count=5`
    - `proof_written_count=5`
    - `raw_tick_row_count=72486`
    - `normalized_row_count=678`
    - `positive_volume_row_count=675`
    - `window_precheck_count=15`
    - `window_precheck_pass_count=15`
    - `window_precheck_fail_for_written_count=0`
  - 单 request 交付：
    - `fu2209.SHFE`：raw ticks `16155`、normalized `135`、positive volume `135`、window `3/3`
    - `OI305.CZCE`：raw ticks `16073`、normalized `135`、positive volume `135`、window `3/3`
    - `OI309.CZCE`：raw ticks `15966`、normalized `136`、positive volume `135`、window `3/3`
    - `jm2401.DCE`：raw ticks `12072`、normalized `136`、positive volume `135`、window `3/3`
    - `jm2405.DCE`：raw ticks `12220`、normalized `136`、positive volume `135`、window `3/3`
  - Stage160 复验：
    - `incoming_root_exists=1`
    - `present_expected_file_count=18/699`
    - `missing_expected_file_count=681`
    - `arrival_completion_pct=2.5751%`
    - `raw_file_present_count=6`
    - `normalized_file_present_count=6`
    - `proof_file_present_count=6`
    - `request_complete_triplet_count=6/233`
    - `request_partial_triplet_count=0`
    - `request_missing_triplet_count=227`
    - `unexpected_file_count=0`
    - `stage153_trigger_allowed=0`
  - Stage153 复验：
    - `request_ready_count=6/233`
    - `required_window_count=657`
    - `proof_json_valid_count=6`
    - `proof_raw_sha256_match_count=6`
    - `proof_identity_match_count=6`
    - `proof_no_trade_policy_declared_count=6`
    - `normalized_schema_pass_count=6`
    - `forbidden_provenance_marker_count=0`
    - `window_coverage_pass_count=18/657`
    - `right_tail_window_coverage_pass_count=18/54`
    - `bottom_loss_window_coverage_pass_count=0/54`
    - `maxdd_window_coverage_pass_count=3/72`
    - `low_resolution_window_coverage_pass_count=15/279`
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

- Stage165 report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage165_batch_tick_aggregate_proofed_delivery/qmt_roll_stage165_c9_minrisk_batch_tick_aggregate_proofed_delivery_report_stage165_batch_tick_aggregate_proofed_delivery_v1.md`
- Stage165 summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage165_batch_tick_aggregate_proofed_delivery/qmt_roll_stage165_c9_minrisk_batch_tick_aggregate_proofed_delivery_summary_stage165_batch_tick_aggregate_proofed_delivery_v1.csv`
- Stage165 selected requests：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage165_batch_tick_aggregate_proofed_delivery/qmt_roll_stage165_c9_minrisk_batch_tick_aggregate_proofed_delivery_selected_requests_stage165_batch_tick_aggregate_proofed_delivery_v1.csv`
- Stage165 request run status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage165_batch_tick_aggregate_proofed_delivery/qmt_roll_stage165_c9_minrisk_batch_tick_aggregate_proofed_delivery_request_run_status_stage165_batch_tick_aggregate_proofed_delivery_v1.csv`
- Stage165 delivery audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage165_batch_tick_aggregate_proofed_delivery/qmt_roll_stage165_c9_minrisk_batch_tick_aggregate_proofed_delivery_delivery_audit_stage165_batch_tick_aggregate_proofed_delivery_v1.csv`
- Stage165 window precheck：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage165_batch_tick_aggregate_proofed_delivery/qmt_roll_stage165_c9_minrisk_batch_tick_aggregate_proofed_delivery_window_precheck_stage165_batch_tick_aggregate_proofed_delivery_v1.csv`
- Stage160 summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage160_authoritative_minute_arrival_monitor/qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_summary_stage160_authoritative_minute_arrival_monitor_v1.csv`
- Stage153 summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage153_authoritative_minute_ohlcv_intake_validator/qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator_summary_stage153_authoritative_minute_ohlcv_intake_validator_v1.csv`
- incoming：本阶段写入 5 个 request 的 raw/normalized/proof 三件套；叠加 Stage164 后当前 `incoming/stage152_authoritative_minute_ohlcv` 共 6 个 complete triplets。
- orders：无；本阶段禁止报单和 true engine。
- daily：无新增回测 daily；使用官方路径资金曲线图跟踪。
- quality：
  - Stage165 5 张 PNG 均非空；
  - Stage160 5 张 PNG 均非空；
  - Stage153 5 张 PNG 均非空。

## 视觉分析

- Stage165 官方路径图显示资金曲线、回撤和 broker10 没有被改动；这说明本阶段只是数据交付，不是收益候选。
- Stage165 delivery matrix 显示本批 5 个 request 的 raw、normalized、proof 全部写入，且没有 partial triplet。
- Stage165 selected priority 图显示选择依据集中在 priority score 和窗口覆盖数量，不包含 PnL、最大回撤、年份胜负或产品收益筛选。
- Stage165 window precheck matrix 显示 15 个窗口全部通过，分钟成交量为真实正量，不再是 Stage162 的全 0 K 线路径。
- Stage160/153 图显示到货从 Stage164 的 `3/699` 提升到 `18/699`，验收从 `1/233` 提升到 `6/233`；但全包仍大幅未完成，feature builder 和策略研究闸门继续关闭。

## 结论

- 本阶段结论：Stage165 成功把 tick 聚合 proofed delivery 从单 request 扩展为 6 个 request、18 个窗口；所有 6 个 ready request 均通过 proof JSON、raw sha、身份、no-trade policy、normalized schema 和 forbidden marker 检查。但 Stage153 全包仍只完成 `18/657` 窗口，距离可构建分钟特征和可交易策略还很远。
- 是否进入下一步：是，但下一步仍是数据交付扩展，不是策略。
- 下一步：继续沿 Stage152 manifest 批量扩展 tick 聚合 proofed delivery，优先补 bottom-loss、maxDD 和 right-tail 核心窗口；每批写入后必须重跑 Stage160/153。只有 Stage153 全包窗口覆盖、Stage156/157/158 lineage 与 feature table 闸门通过后，才允许进入只读 feature atlas 或分钟信号候选。

## 过拟合反思

- 运行前判断：否。Stage165 不按历史收益、回撤、胜负或品种表现挑样本，只补 Stage153 尚未 ready 的高优先级 request。
- 运行后判断：否，但后续需要继续防止数据转换过拟合。
- 原因：本阶段没有产生交易规则，也没有运行 true engine；成功标准来自 proof、raw sha、schema、forbidden marker 和窗口覆盖。固定 tick 差分聚合是数据规范，不是策略阈值；后续不能为了让某些窗口通过而调整 session 边界、成交量差分、no-trade policy 或 request 顺序。

## 继续价值反思

- 运行前判断：有。Stage164 只证明 1 个 request 可被验收，无法支撑分钟级普世信号研究。
- 运行后判断：有。Stage165 证明同一 tick 聚合交付流程能跨 SHFE、CZCE、DCE 和不同年份稳定生成正量分钟包，并被 Stage153 接受。
- 原因：目标要求基于分钟级 K 线进出场且不能过拟合；当前最关键缺口仍是权威、点时化、可回溯的分钟 OHLCV。继续补齐数据覆盖，比在 6 个 ready request 上提早造规则更有价值。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage165 摘要。
- 是否更新 `research/registry.md`：否，未新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否，非正式候选、非策略突破、非路线废弃；等核心窗口批量覆盖并打通 Stage156/157/158 后再考虑。
