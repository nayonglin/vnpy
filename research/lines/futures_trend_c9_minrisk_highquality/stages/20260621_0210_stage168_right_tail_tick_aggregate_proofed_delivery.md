# Stage168 right-tail 覆盖优先 tick 聚合 proofed delivery

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-21 02:10`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage152 right-tail 覆盖缺口导向的批量 raw/normalized/proof 三件套交付，并重跑 Stage160/153 验收
- 是否重要突破：否；这是右尾数据覆盖补齐进展，不是策略收益/回撤突破，也不是正式候选
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk Backtest 文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html`
  - TqSdk tick 序列使用文档：`https://tqsdk-python.readthedocs.io/en/latest/usage/mddatas.html`
  - W3C PROV-DM：`https://www.w3.org/TR/prov-dm/`
  - TqSdk GitHub：`https://github.com/shinnytech/tqsdk-python`
- 我的判断：TqSdk 文档继续证明 tick 路径比 K 线路径更适合当前线真实成交量分钟数据交付；W3C PROV 的核心思想也支持把 raw tick、聚合活动、proof/hash/schema 和 normalized bar 串成可追溯链。Stage168 补 right-tail 的目的，是让未来分钟级视觉 atlas 既能看到回撤/亏损段，也能看到 C9 复利底座的大赢家段，避免为了降回撤而系统性砍掉右尾。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage168_right_tail_tick_aggregate_proofed_delivery.py`
- 修改脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage166_gap_balanced_tick_aggregate_proofed_delivery.py`，新增通用 `delivered_right_tail_window_count`、`delivered_bottom_loss_window_count`、`delivered_maxdd_window_count`、`delivered_low_resolution_window_count` 摘要字段；不改变数据聚合、proof 或写入逻辑。
- 删除脚本：无
- 新增参数：无策略参数；新增 `STAGE168_MAX_REQUESTS`、`STAGE168_WRITE_INCOMING`、`STAGE168_OVERWRITE_EXISTING`、`STAGE168_MAX_SECONDS_TICK`、`STAGE168_TICK_DATA_LENGTH`、`STAGE168_MIN_NORMALIZED_ROWS` 等数据交付参数。
- 修改参数：无交易参数。
- 删除参数：无

## 回测/归因参数

- 数据区间：本阶段批量交付 8 个缺失 request：`stage152_req_0015_fu2503_SHFE_20241217`、`stage152_req_0016_fu2509_SHFE_20250807`、`stage152_req_0001_AP201_CZCE_20211012`、`stage152_req_0002_AP505_CZCE_20250328`、`stage152_req_0003_FG109_CZCE_20210414`、`stage152_req_0006_SH405_CZCE_20240326`、`stage152_req_0007_SM201_CZCE_20210901`、`stage152_req_0008_SM205_CZCE_20220303`。
- 账户规模：沿用当前研究线官方路径口径。
- 成本口径：沿用 Stage160/153 官方路径总滑点口径；本阶段不运行新回测。
- 样本过滤：固定选择策略为 `missing_stage153_ready_then_manifest_coverage_gap_right_tail_bottom_loss_maxdd_request_id_not_trade_rule`。这里使用 right-tail 只是 Stage152 manifest 的覆盖义务，不是交易筛选，也不允许后续把右尾标签直接变成规则。
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
  - Stage168：
    - `decision=stage168_right_tail_tick_aggregate_delivery_written_run_stage160_153_no_rule`
    - `next_best_action=rerun_stage160_then_stage153`
    - `ready_before_count=22`
    - `remaining_before_count=211`
    - `selected_request_count=8`
    - `selected_right_tail_window_count=24`
    - `selected_bottom_loss_window_count=0`
    - `selected_maxdd_window_count=0`
    - `selected_low_resolution_window_count=6`
    - `credential_present=1`
    - `fetch_attempted_count=8`
    - `fetch_extracted_count=8`
    - `delivery_success_count=8`
    - `delivered_right_tail_window_count=24`
    - `delivered_low_resolution_window_count=6`
    - `expected_files_written=24`
    - `raw_written_count=8`
    - `normalized_written_count=8`
    - `proof_written_count=8`
    - `raw_tick_row_count=110146`
    - `normalized_row_count=1158`
    - `positive_volume_row_count=1156`
    - `window_precheck_count=24`
    - `window_precheck_pass_count=24`
    - `window_precheck_fail_for_written_count=0`
  - 单 request 交付：
    - `fu2503.SHFE`：raw ticks `16201`、normalized `136`、positive volume `135`、window `3/3`
    - `fu2509.SHFE`：raw ticks `14668`、normalized `136`、positive volume `135`、window `3/3`
    - `AP201.CZCE`：raw ticks `12465`、normalized `136`、positive volume `136`、window `3/3`
    - `AP505.CZCE`：raw ticks `13669`、normalized `136`、positive volume `136`、window `3/3`
    - `FG109.CZCE`：raw ticks `15408`、normalized `135`、positive volume `135`、window `3/3`
    - `SH405.CZCE`：raw ticks `10867`、normalized `207`、positive volume `207`、window `3/3`
    - `SM201.CZCE`：raw ticks `15909`、normalized `136`、positive volume `136`、window `3/3`
    - `SM205.CZCE`：raw ticks `10959`、normalized `136`、positive volume `136`、window `3/3`
  - Stage160 复验：
    - `incoming_root_exists=1`
    - `present_expected_file_count=90/699`
    - `missing_expected_file_count=609`
    - `arrival_completion_pct=12.8755%`
    - `raw_file_present_count=30`
    - `normalized_file_present_count=30`
    - `proof_file_present_count=30`
    - `request_complete_triplet_count=30/233`
    - `request_partial_triplet_count=0`
    - `request_missing_triplet_count=203`
    - `unexpected_file_count=0`
    - `stage153_trigger_allowed=0`
  - Stage153 复验：
    - `request_ready_count=30/233`
    - `required_window_count=657`
    - `proof_json_valid_count=30`
    - `proof_raw_sha256_match_count=30`
    - `proof_identity_match_count=30`
    - `proof_no_trade_policy_declared_count=30`
    - `normalized_schema_pass_count=30`
    - `forbidden_provenance_marker_count=0`
    - `window_coverage_pass_count=90/657`
    - `right_tail_window_coverage_pass_count=42/54`
    - `bottom_loss_window_coverage_pass_count=24/54`
    - `maxdd_window_coverage_pass_count=30/72`
    - `low_resolution_window_coverage_pass_count=60/279`
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

- Stage168 report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage168_right_tail_tick_aggregate_proofed_delivery/qmt_roll_stage168_c9_minrisk_right_tail_tick_aggregate_proofed_delivery_report_stage168_right_tail_tick_aggregate_proofed_delivery_v1.md`
- Stage168 summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage168_right_tail_tick_aggregate_proofed_delivery/qmt_roll_stage168_c9_minrisk_right_tail_tick_aggregate_proofed_delivery_summary_stage168_right_tail_tick_aggregate_proofed_delivery_v1.csv`
- Stage168 selected requests：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage168_right_tail_tick_aggregate_proofed_delivery/qmt_roll_stage168_c9_minrisk_right_tail_tick_aggregate_proofed_delivery_selected_requests_stage168_right_tail_tick_aggregate_proofed_delivery_v1.csv`
- Stage168 request run status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage168_right_tail_tick_aggregate_proofed_delivery/qmt_roll_stage168_c9_minrisk_right_tail_tick_aggregate_proofed_delivery_request_run_status_stage168_right_tail_tick_aggregate_proofed_delivery_v1.csv`
- Stage168 delivery audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage168_right_tail_tick_aggregate_proofed_delivery/qmt_roll_stage168_c9_minrisk_right_tail_tick_aggregate_proofed_delivery_delivery_audit_stage168_right_tail_tick_aggregate_proofed_delivery_v1.csv`
- Stage168 window precheck：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage168_right_tail_tick_aggregate_proofed_delivery/qmt_roll_stage168_c9_minrisk_right_tail_tick_aggregate_proofed_delivery_window_precheck_stage168_right_tail_tick_aggregate_proofed_delivery_v1.csv`
- Stage160 summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage160_authoritative_minute_arrival_monitor/qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_summary_stage160_authoritative_minute_arrival_monitor_v1.csv`
- Stage153 summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage153_authoritative_minute_ohlcv_intake_validator/qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator_summary_stage153_authoritative_minute_ohlcv_intake_validator_v1.csv`
- incoming：本阶段写入 8 个 request 的 raw/normalized/proof 三件套；叠加 Stage164-167 后当前 `incoming/stage152_authoritative_minute_ohlcv` 共 30 个 complete triplets、90 个文件。
- orders：无；本阶段禁止报单和 true engine。
- daily：无新增回测 daily；使用官方路径资金曲线图跟踪。
- quality：
  - Stage168 5 张 PNG 均非空；
  - Stage160 5 张 PNG 均非空；
  - Stage153 5 张 PNG 均非空。

## 视觉分析

- Stage168 官方路径图显示资金曲线、回撤和 broker10 未改变，说明本阶段没有引入策略收益变化。
- Stage168 selected right-tail priority 图显示本批 8 个 request 全部是 right-tail 覆盖义务，前两个 `fu` request 同时带 low-resolution 覆盖。
- Stage168 delivery matrix 显示 8 个 request 的 raw、normalized、proof 全部写入，没有 partial triplet。
- Stage168 window precheck matrix 显示 24 个 right-tail 窗口全部通过，且各窗口有正成交量和无重复 bar；`SH405.CZCE` 的 event buffer 与 session guard 延伸到日内较晚时间，但仍由实际 bar 覆盖。
- Stage153 window heatmap 最新状态显示 right-tail 覆盖从 `18/54` 提升到 `42/54`；maxDD 保持 `30/72`，bottom-loss 保持 `24/54`。这让后续视觉 atlas 更能同时保护右尾和观察回撤/亏损段。

## 结论

- 本阶段结论：Stage168 成功把当前线权威分钟数据覆盖从 `22` 个 request / `66` 个窗口推进到 `30` 个 request / `90` 个窗口，并把 right-tail 覆盖推进到 `42/54`。所有 30 个 ready request 均通过 proof JSON、raw sha、身份、no-trade policy、normalized schema 和 forbidden marker 检查。
- 是否进入下一步：是，但下一步仍是数据覆盖扩展，不是策略。
- 下一步：继续沿 Stage152 manifest 批量补齐剩余 right-tail、bottom-loss 与 maxDD 窗口；每批写入后必须重跑 Stage160/153。只有 Stage153 全包窗口覆盖、Stage156/157/158 lineage 与 feature table 闸门通过后，才允许进入只读 feature atlas 或分钟信号候选。

## 过拟合反思

- 运行前判断：否。Stage168 只按 Stage153 right-tail 覆盖缺口补数据，没有调交易阈值、没有运行 true engine，也没有使用右尾标签构造交易规则。
- 运行后判断：否，但风险边界必须继续写清：right-tail 是结果标签，作为覆盖义务可用于保护未来规则不砍大赢家，作为交易条件则会直接过拟合。
- 原因：本阶段成功标准来自 proof、raw sha、schema、forbidden marker 和窗口覆盖；选择 right-tail 是为了让未来高质量信号视觉分析不只看亏损/回撤段，从而避免“为了降低回撤牺牲复利底座”的错误。

## 继续价值反思

- 运行前判断：有。Stage167 后 maxDD 已显著补强，但 right-tail 仍只有 `18/54`，不利于判断未来规则是否系统性砍掉大赢家。
- 运行后判断：有。Stage168 把 right-tail 覆盖推进到 `42/54`，使后续视觉对照更接近“赢家、亏损、回撤同图谱比较”的必要条件。
- 原因：目标要求收益保留 80% 以上；没有右尾分钟数据，任何降回撤规则都可能在视觉上看似稳健、实际砍掉主要复利来源。继续补齐 right-tail/bottom-loss/maxDD 同源分钟数据，比提前造规则更符合不过拟合原则。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage168 摘要。
- 是否更新 `research/registry.md`：否，未新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否，非正式候选、非策略突破、非路线废弃；等核心窗口批量覆盖并打通 Stage156/157/158 后再考虑。
