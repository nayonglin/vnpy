# Stage166 覆盖缺口均衡 tick 聚合 proofed delivery

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-21 01:54`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage152 覆盖缺口导向的批量 raw/normalized/proof 三件套交付，并重跑 Stage160/153 验收
- 是否重要突破：否；这是 bottom-loss/maxDD 数据覆盖补齐进展，不是策略收益/回撤突破，也不是正式候选
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk Backtest 文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html`
  - TqSdk tick 序列使用文档：`https://tqsdk-python.readthedocs.io/en/latest/usage/mddatas.html`
  - TqSdk DataDownloader 文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.tools.download.html`
  - TqSdk GitHub：`https://github.com/shinnytech/tqsdk-python`
- 我的判断：TqSdk 文档继续支持 Stage163-165 的结论：K 线路径可能生成零成交量 quote，tick 序列才是本线当前能得到真实成交量/成交额的候选源；DataDownloader 可下载 tick 或任意 K 线周期，但属于专业版历史下载能力，不能作为本机当前批量交付前提。Stage166 的本质不是换 alpha，而是按 Stage152/153 的数据合同补齐被明显欠覆盖的 bottom-loss/maxDD 窗口，避免后续只在右尾数据上做视觉判断。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage166_gap_balanced_tick_aggregate_proofed_delivery.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增 `STAGE166_MAX_REQUESTS`、`STAGE166_WRITE_INCOMING`、`STAGE166_OVERWRITE_EXISTING`、`STAGE166_MAX_SECONDS_TICK`、`STAGE166_TICK_DATA_LENGTH`、`STAGE166_MIN_NORMALIZED_ROWS` 等数据交付参数。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：本阶段批量交付 8 个缺失 request：`stage152_req_0023_jm2301_DCE_20221130`、`stage152_req_0017_AP505_CZCE_20250224`、`stage152_req_0018_AP505_CZCE_20250317`、`stage152_req_0027_fu2209_SHFE_20220418`、`stage152_req_0030_ru2601_SHFE_20251203`、`stage152_req_0031_ru2605_SHFE_20260127`、`stage152_req_0019_OI205_CZCE_20220105`、`stage152_req_0020_SH605_CZCE_20260303`。
- 账户规模：沿用当前研究线官方路径口径。
- 成本口径：沿用 Stage160/153 官方路径总滑点口径；本阶段不运行新回测。
- 样本过滤：固定选择策略为 `missing_stage153_ready_then_manifest_coverage_gap_bottom_loss_maxdd_right_tail_request_id_not_trade_rule`。这里使用 bottom-loss/maxDD 只是 Stage152 manifest 的覆盖义务，不是交易筛选，也不允许后续把这些标签直接变成规则。
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
  - Stage166：
    - `decision=stage166_gap_balanced_tick_aggregate_delivery_written_run_stage160_153_no_rule`
    - `next_best_action=rerun_stage160_then_stage153`
    - `ready_before_count=6`
    - `remaining_before_count=227`
    - `selected_request_count=8`
    - `selected_bottom_loss_window_count=24`
    - `selected_maxdd_window_count=3`
    - `selected_right_tail_window_count=0`
    - `selected_low_resolution_window_count=15`
    - `selected_target_bottom_loss_plus_maxdd_window_count=27`
    - `credential_present=1`
    - `fetch_attempted_count=8`
    - `fetch_extracted_count=8`
    - `delivery_success_count=8`
    - `delivered_bottom_loss_plus_maxdd_window_count=27`
    - `expected_files_written=24`
    - `raw_written_count=8`
    - `normalized_written_count=8`
    - `proof_written_count=8`
    - `raw_tick_row_count=110113`
    - `normalized_row_count=1105`
    - `positive_volume_row_count=1101`
    - `window_precheck_count=24`
    - `window_precheck_pass_count=24`
    - `window_precheck_fail_for_written_count=0`
  - 单 request 交付：
    - `jm2301.DCE`：raw ticks `7580`、normalized `135`、positive volume `135`、window `3/3`
    - `AP505.CZCE` 2025-02-24：raw ticks `10792`、normalized `136`、positive volume `136`、window `3/3`
    - `AP505.CZCE` 2025-03-17：raw ticks `13043`、normalized `136`、positive volume `136`、window `3/3`
    - `fu2209.SHFE` 2022-04-18：raw ticks `16159`、normalized `135`、positive volume `135`、window `3/3`
    - `ru2601.SHFE`：raw ticks `14030`、normalized `136`、positive volume `135`、window `3/3`
    - `ru2605.SHFE`：raw ticks `15978`、normalized `136`、positive volume `135`、window `3/3`
    - `OI205.CZCE`：raw ticks `15340`、normalized `135`、positive volume `135`、window `3/3`
    - `SH605.CZCE`：raw ticks `17191`、normalized `156`、positive volume `154`、window `3/3`
  - Stage160 复验：
    - `incoming_root_exists=1`
    - `present_expected_file_count=42/699`
    - `missing_expected_file_count=657`
    - `arrival_completion_pct=6.0086%`
    - `raw_file_present_count=14`
    - `normalized_file_present_count=14`
    - `proof_file_present_count=14`
    - `request_complete_triplet_count=14/233`
    - `request_partial_triplet_count=0`
    - `request_missing_triplet_count=219`
    - `unexpected_file_count=0`
    - `stage153_trigger_allowed=0`
  - Stage153 复验：
    - `request_ready_count=14/233`
    - `required_window_count=657`
    - `proof_json_valid_count=14`
    - `proof_raw_sha256_match_count=14`
    - `proof_identity_match_count=14`
    - `proof_no_trade_policy_declared_count=14`
    - `normalized_schema_pass_count=14`
    - `forbidden_provenance_marker_count=0`
    - `window_coverage_pass_count=42/657`
    - `right_tail_window_coverage_pass_count=18/54`
    - `bottom_loss_window_coverage_pass_count=24/54`
    - `maxdd_window_coverage_pass_count=6/72`
    - `low_resolution_window_coverage_pass_count=30/279`
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

- Stage166 report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage166_gap_balanced_tick_aggregate_proofed_delivery/qmt_roll_stage166_c9_minrisk_gap_balanced_tick_aggregate_proofed_delivery_report_stage166_gap_balanced_tick_aggregate_proofed_delivery_v1.md`
- Stage166 summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage166_gap_balanced_tick_aggregate_proofed_delivery/qmt_roll_stage166_c9_minrisk_gap_balanced_tick_aggregate_proofed_delivery_summary_stage166_gap_balanced_tick_aggregate_proofed_delivery_v1.csv`
- Stage166 selected requests：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage166_gap_balanced_tick_aggregate_proofed_delivery/qmt_roll_stage166_c9_minrisk_gap_balanced_tick_aggregate_proofed_delivery_selected_requests_stage166_gap_balanced_tick_aggregate_proofed_delivery_v1.csv`
- Stage166 request run status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage166_gap_balanced_tick_aggregate_proofed_delivery/qmt_roll_stage166_c9_minrisk_gap_balanced_tick_aggregate_proofed_delivery_request_run_status_stage166_gap_balanced_tick_aggregate_proofed_delivery_v1.csv`
- Stage166 delivery audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage166_gap_balanced_tick_aggregate_proofed_delivery/qmt_roll_stage166_c9_minrisk_gap_balanced_tick_aggregate_proofed_delivery_delivery_audit_stage166_gap_balanced_tick_aggregate_proofed_delivery_v1.csv`
- Stage166 window precheck：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage166_gap_balanced_tick_aggregate_proofed_delivery/qmt_roll_stage166_c9_minrisk_gap_balanced_tick_aggregate_proofed_delivery_window_precheck_stage166_gap_balanced_tick_aggregate_proofed_delivery_v1.csv`
- Stage160 summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage160_authoritative_minute_arrival_monitor/qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_summary_stage160_authoritative_minute_arrival_monitor_v1.csv`
- Stage153 summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage153_authoritative_minute_ohlcv_intake_validator/qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator_summary_stage153_authoritative_minute_ohlcv_intake_validator_v1.csv`
- incoming：本阶段写入 8 个 request 的 raw/normalized/proof 三件套；叠加 Stage164/165 后当前 `incoming/stage152_authoritative_minute_ohlcv` 共 14 个 complete triplets、42 个文件。
- orders：无；本阶段禁止报单和 true engine。
- daily：无新增回测 daily；使用官方路径资金曲线图跟踪。
- quality：
  - Stage166 5 张 PNG 均非空；
  - Stage160 5 张 PNG 均非空；
  - Stage153 5 张 PNG 均非空。

## 视觉分析

- Stage166 官方路径图显示资金曲线、回撤和 broker10 未改变，说明本阶段没有引入策略收益变化。
- Stage166 selected gap priority 图显示本批几乎全是 bottom-loss 覆盖义务，并带少量 maxDD/low-resolution 重叠；这是对 Stage165 右尾偏覆盖的纠偏。
- Stage166 delivery matrix 显示 8 个 request 的 raw、normalized、proof 全部写入，没有 partial triplet。
- Stage166 window precheck matrix 显示 24 个窗口全部通过，且各窗口有正成交量；其中 `SH605.CZCE` 的 `session_guard_to_event_or_240m` 窗口延伸到 `13:33`，仍通过实际 bar 覆盖与正量检查。
- Stage153 window heatmap 最新状态显示 right-tail 已覆盖 `18/54`，bottom-loss 覆盖从 `0/54` 提升到 `24/54`，maxDD 覆盖从 `3/72` 提升到 `6/72`；这比只补右尾更适合后续做视觉对比，避免“只看赢家形态”的偏差。

## 结论

- 本阶段结论：Stage166 成功把当前线权威分钟数据覆盖从 `6` 个 request / `18` 个窗口推进到 `14` 个 request / `42` 个窗口，并显著补上 bottom-loss 覆盖。所有 14 个 ready request 均通过 proof JSON、raw sha、身份、no-trade policy、normalized schema 和 forbidden marker 检查。
- 是否进入下一步：是，但下一步仍是数据覆盖扩展，不是策略。
- 下一步：继续沿 Stage152 manifest 批量补齐尚未覆盖的 bottom-loss、maxDD 与剩余 right-tail 窗口；每批写入后必须重跑 Stage160/153。只有 Stage153 全包窗口覆盖、Stage156/157/158 lineage 与 feature table 闸门通过后，才允许进入只读 feature atlas 或分钟信号候选。

## 过拟合反思

- 运行前判断：否。Stage166 只按 Stage153 覆盖缺口补数据，没有调交易阈值、没有运行 true engine，也没有使用 bottom-loss/maxDD 去构造交易规则。
- 运行后判断：否，但这里有一个需要持续警惕的边界：bottom-loss/maxDD 是结果标签，作为数据覆盖义务是必要的，作为交易条件则会直接过拟合。
- 原因：本阶段成功标准来自 proof、raw sha、schema、forbidden marker 和窗口覆盖；选择 bottom-loss/maxDD 只是为了让未来视觉 atlas 能同时看到赢家、亏损和回撤段的分钟形态，防止只在右尾样本上形成错觉。后续不得把 “bottom-loss request 是否存在/缺失” 或该标签直接接入策略。

## 继续价值反思

- 运行前判断：有。Stage165 后 right-tail 已有覆盖，但 bottom-loss 仍为 `0/54`，继续只看右尾会让视觉分析偏向幸存者样本。
- 运行后判断：有。Stage166 把 bottom-loss 覆盖推进到 `24/54`，使后续高质量信号视觉判断更接近“赢家和亏损同图谱比较”的必要条件。
- 原因：目标要求用分钟级 K 线识别高质量信号并控制风险；在数据覆盖不均衡时提前建规则更容易过拟合。继续补全多类窗口，是比立即造规则更稳健的推进方式。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage166 摘要。
- 是否更新 `research/registry.md`：否，未新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否，非正式候选、非策略突破、非路线废弃；等核心窗口批量覆盖并打通 Stage156/157/158 后再考虑。
