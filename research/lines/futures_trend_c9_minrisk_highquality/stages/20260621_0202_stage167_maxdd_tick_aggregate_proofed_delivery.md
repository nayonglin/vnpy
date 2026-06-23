# Stage167 maxDD 覆盖优先 tick 聚合 proofed delivery

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-21 02:02`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage152 maxDD 覆盖缺口导向的批量 raw/normalized/proof 三件套交付，并重跑 Stage160/153 验收
- 是否重要突破：否；这是 maxDD 数据覆盖补齐进展，不是策略收益/回撤突破，也不是正式候选
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk Backtest 文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html`
  - TqSdk tick 序列使用文档：`https://tqsdk-python.readthedocs.io/en/latest/usage/mddatas.html`
  - 数据来源/数据血缘说明：`https://www.ibm.com/think/topics/data-provenance`
  - TqSdk GitHub：`https://github.com/shinnytech/tqsdk-python`
- 我的判断：TqSdk 官方文档明确说明，未订阅 tick、只订阅 K 线时，quote 的 `amount` 可能为 `nan` 且 `volume` 始终为 0；tick 序列则提供成交量序列。这继续支持 Stage167 沿用 tick 聚合源。数据血缘角度上，当前最重要的不是提前寻找规则，而是让每一行分钟数据可追溯到 raw tick、proof、schema 与 hash；因此 Stage167 继续补 Stage153 覆盖缺口，优先把 maxDD 窗口从薄覆盖推进到可视觉比较的状态。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage167_maxdd_tick_aggregate_proofed_delivery.py`
- 修改脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage166_gap_balanced_tick_aggregate_proofed_delivery.py`，仅把 report title、chart title、decision 字符串参数化，便于 Stage167 复用同一交付逻辑；不改变 Stage166 选择策略、数据聚合、proof 或写入逻辑。
- 删除脚本：无
- 新增参数：无策略参数；新增 `STAGE167_MAX_REQUESTS`、`STAGE167_WRITE_INCOMING`、`STAGE167_OVERWRITE_EXISTING`、`STAGE167_MAX_SECONDS_TICK`、`STAGE167_TICK_DATA_LENGTH`、`STAGE167_MIN_NORMALIZED_ROWS` 等数据交付参数。
- 修改参数：无交易参数。
- 删除参数：无

## 回测/归因参数

- 数据区间：本阶段批量交付 8 个缺失 request：`stage152_req_0037_MA209_CZCE_20220613`、`stage152_req_0040_SA209_CZCE_20220707`、`stage152_req_0042_jm2301_DCE_20220829`、`stage152_req_0043_lh2301_DCE_20221110`、`stage152_req_0046_fu2209_SHFE_20220622`、`stage152_req_0047_fu2305_SHFE_20230131`、`stage152_req_0048_fu2305_SHFE_20230214`、`stage152_req_0050_hc2305_SHFE_20230221`。
- 账户规模：沿用当前研究线官方路径口径。
- 成本口径：沿用 Stage160/153 官方路径总滑点口径；本阶段不运行新回测。
- 样本过滤：固定选择策略为 `missing_stage153_ready_then_manifest_coverage_gap_maxdd_right_tail_bottom_loss_request_id_not_trade_rule`。这里使用 maxDD/right-tail/bottom-loss 只是 Stage152 manifest 的覆盖义务，不是交易筛选，也不允许后续把这些标签直接变成规则。
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
  - Stage167：
    - `decision=stage167_maxdd_tick_aggregate_delivery_written_run_stage160_153_no_rule`
    - `next_best_action=rerun_stage160_then_stage153`
    - `ready_before_count=14`
    - `remaining_before_count=219`
    - `selected_request_count=8`
    - `selected_bottom_loss_window_count=0`
    - `selected_maxdd_window_count=24`
    - `selected_right_tail_window_count=0`
    - `selected_low_resolution_window_count=24`
    - `credential_present=1`
    - `fetch_attempted_count=8`
    - `fetch_extracted_count=8`
    - `delivery_success_count=8`
    - `expected_files_written=24`
    - `raw_written_count=8`
    - `normalized_written_count=8`
    - `proof_written_count=8`
    - `raw_tick_row_count=112321`
    - `normalized_row_count=1081`
    - `positive_volume_row_count=1080`
    - `window_precheck_count=24`
    - `window_precheck_pass_count=24`
    - `window_precheck_fail_for_written_count=0`
  - 单 request 交付：
    - `MA209.CZCE`：raw ticks `16163`、normalized `135`、positive volume `135`、window `3/3`
    - `SA209.CZCE`：raw ticks `15951`、normalized `135`、positive volume `135`、window `3/3`
    - `jm2301.DCE`：raw ticks `10931`、normalized `135`、positive volume `135`、window `3/3`
    - `lh2301.DCE`：raw ticks `6618`、normalized `136`、positive volume `135`、window `3/3`
    - `fu2209.SHFE` 2022-06-22：raw ticks `16097`、normalized `135`、positive volume `135`、window `3/3`
    - `fu2305.SHFE` 2023-01-31：raw ticks `15929`、normalized `135`、positive volume `135`、window `3/3`
    - `fu2305.SHFE` 2023-02-14：raw ticks `16082`、normalized `135`、positive volume `135`、window `3/3`
    - `hc2305.SHFE`：raw ticks `14550`、normalized `135`、positive volume `135`、window `3/3`
  - Stage160 复验：
    - `incoming_root_exists=1`
    - `present_expected_file_count=66/699`
    - `missing_expected_file_count=633`
    - `arrival_completion_pct=9.4421%`
    - `raw_file_present_count=22`
    - `normalized_file_present_count=22`
    - `proof_file_present_count=22`
    - `request_complete_triplet_count=22/233`
    - `request_partial_triplet_count=0`
    - `request_missing_triplet_count=211`
    - `unexpected_file_count=0`
    - `stage153_trigger_allowed=0`
  - Stage153 复验：
    - `request_ready_count=22/233`
    - `required_window_count=657`
    - `proof_json_valid_count=22`
    - `proof_raw_sha256_match_count=22`
    - `proof_identity_match_count=22`
    - `proof_no_trade_policy_declared_count=22`
    - `normalized_schema_pass_count=22`
    - `forbidden_provenance_marker_count=0`
    - `window_coverage_pass_count=66/657`
    - `right_tail_window_coverage_pass_count=18/54`
    - `bottom_loss_window_coverage_pass_count=24/54`
    - `maxdd_window_coverage_pass_count=30/72`
    - `low_resolution_window_coverage_pass_count=54/279`
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

- Stage167 report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage167_maxdd_tick_aggregate_proofed_delivery/qmt_roll_stage167_c9_minrisk_maxdd_tick_aggregate_proofed_delivery_report_stage167_maxdd_tick_aggregate_proofed_delivery_v1.md`
- Stage167 summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage167_maxdd_tick_aggregate_proofed_delivery/qmt_roll_stage167_c9_minrisk_maxdd_tick_aggregate_proofed_delivery_summary_stage167_maxdd_tick_aggregate_proofed_delivery_v1.csv`
- Stage167 selected requests：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage167_maxdd_tick_aggregate_proofed_delivery/qmt_roll_stage167_c9_minrisk_maxdd_tick_aggregate_proofed_delivery_selected_requests_stage167_maxdd_tick_aggregate_proofed_delivery_v1.csv`
- Stage167 request run status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage167_maxdd_tick_aggregate_proofed_delivery/qmt_roll_stage167_c9_minrisk_maxdd_tick_aggregate_proofed_delivery_request_run_status_stage167_maxdd_tick_aggregate_proofed_delivery_v1.csv`
- Stage167 delivery audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage167_maxdd_tick_aggregate_proofed_delivery/qmt_roll_stage167_c9_minrisk_maxdd_tick_aggregate_proofed_delivery_delivery_audit_stage167_maxdd_tick_aggregate_proofed_delivery_v1.csv`
- Stage167 window precheck：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage167_maxdd_tick_aggregate_proofed_delivery/qmt_roll_stage167_c9_minrisk_maxdd_tick_aggregate_proofed_delivery_window_precheck_stage167_maxdd_tick_aggregate_proofed_delivery_v1.csv`
- Stage160 summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage160_authoritative_minute_arrival_monitor/qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_summary_stage160_authoritative_minute_arrival_monitor_v1.csv`
- Stage153 summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage153_authoritative_minute_ohlcv_intake_validator/qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator_summary_stage153_authoritative_minute_ohlcv_intake_validator_v1.csv`
- incoming：本阶段写入 8 个 request 的 raw/normalized/proof 三件套；叠加 Stage164/165/166 后当前 `incoming/stage152_authoritative_minute_ohlcv` 共 22 个 complete triplets、66 个文件。
- orders：无；本阶段禁止报单和 true engine。
- daily：无新增回测 daily；使用官方路径资金曲线图跟踪。
- quality：
  - Stage167 5 张 PNG 均非空；
  - Stage160 5 张 PNG 均非空；
  - Stage153 5 张 PNG 均非空。

## 视觉分析

- Stage167 官方路径图显示资金曲线、回撤和 broker10 未改变，说明本阶段没有引入策略收益变化。
- Stage167 selected maxDD priority 图显示本批 8 个 request 全部是 maxDD context，且均带 low-resolution 重叠覆盖；这是对 Stage166 后 maxDD 覆盖仍薄的补强。
- Stage167 delivery matrix 显示 8 个 request 的 raw、normalized、proof 全部写入，没有 partial triplet。
- Stage167 window precheck matrix 显示 24 个 maxDD context 窗口全部通过，且各窗口有正成交量和无重复 bar。
- Stage153 window heatmap 最新状态显示 maxDD 覆盖从 `6/72` 提升到 `30/72`，low-resolution 从 `30/279` 提升到 `54/279`；right-tail 与 bottom-loss 暂未变化，后续仍需补齐。

## 结论

- 本阶段结论：Stage167 成功把当前线权威分钟数据覆盖从 `14` 个 request / `42` 个窗口推进到 `22` 个 request / `66` 个窗口，并把 maxDD 覆盖推进到 `30/72`。所有 22 个 ready request 均通过 proof JSON、raw sha、身份、no-trade policy、normalized schema 和 forbidden marker 检查。
- 是否进入下一步：是，但下一步仍是数据覆盖扩展，不是策略。
- 下一步：继续沿 Stage152 manifest 批量补齐剩余 maxDD、bottom-loss 与 right-tail 窗口；每批写入后必须重跑 Stage160/153。只有 Stage153 全包窗口覆盖、Stage156/157/158 lineage 与 feature table 闸门通过后，才允许进入只读 feature atlas 或分钟信号候选。

## 过拟合反思

- 运行前判断：否。Stage167 只按 Stage153 maxDD 覆盖缺口补数据，没有调交易阈值、没有运行 true engine，也没有使用 maxDD 标签构造交易规则。
- 运行后判断：否，但风险边界必须继续写清：maxDD 是结果/路径标签，作为覆盖义务可用于未来视觉对照，作为交易条件则会直接过拟合。
- 原因：本阶段成功标准来自 proof、raw sha、schema、forbidden marker 和窗口覆盖；选择 maxDD 是为了让未来高质量信号视觉分析同时观察回撤段形态，而不是从回撤段反推出开平仓规则。

## 继续价值反思

- 运行前判断：有。Stage166 后 bottom-loss 已有一定覆盖，但 maxDD 仍只有 `6/72`，无法支撑对最大回撤期分钟结构的视觉审计。
- 运行后判断：有。Stage167 把 maxDD 覆盖推进到 `30/72`，使后续对“高质量信号是否避开回撤段噪音/拥挤/反复触发”的视觉比较更接近可用状态。
- 原因：目标是降低最大回撤且保留收益；如果没有 maxDD 段的真实分钟数据，任何降回撤规则都容易变成事后解释。继续补齐 maxDD/right-tail/bottom-loss 的同源分钟数据，比提前造规则更符合不过拟合原则。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage167 摘要。
- 是否更新 `research/registry.md`：否，未新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否，非正式候选、非策略突破、非路线废弃；等核心窗口批量覆盖并打通 Stage156/157/158 后再考虑。
