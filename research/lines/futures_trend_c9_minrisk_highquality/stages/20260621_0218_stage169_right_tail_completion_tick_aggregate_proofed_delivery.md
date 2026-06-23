# Stage169 right-tail 补完 tick 聚合 proofed delivery

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-21 02:18`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage152 剩余 right-tail 覆盖补完的 raw/normalized/proof 三件套交付，并重跑 Stage160/153 验收
- 是否重要突破：否；这是 right-tail 数据覆盖补完，不是策略收益/回撤突破，也不是正式候选
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk 合约与历史数据文档：`https://tqsdk-python.readthedocs.io/en/latest/usage/mddatas.html`
  - TqSdk Backtest 文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html`
  - W3C PROV-DM：`https://www.w3.org/TR/prov-dm/`
  - TqSdk GitHub：`https://github.com/shinnytech/tqsdk-python`
- 我的判断：TqSdk 文档列出支持 GFEX，并统一采用 `交易所代码.合约代码` 格式；Stage169 实测 `si2509.GFEX` 可通过 tick 聚合写入并被 Stage153 接受。right-tail 补完的价值不是寻找“只做赢家”的规则，而是为未来任何降回撤候选建立右尾保护参照，防止视觉上只优化亏损段、实盘中砍掉复利来源。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage169_right_tail_completion_tick_aggregate_proofed_delivery.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增 `STAGE169_MAX_REQUESTS`、`STAGE169_WRITE_INCOMING`、`STAGE169_OVERWRITE_EXISTING`、`STAGE169_MAX_SECONDS_TICK`、`STAGE169_TICK_DATA_LENGTH`、`STAGE169_MIN_NORMALIZED_ROWS` 等数据交付参数。
- 修改参数：无交易参数。
- 删除参数：无

## 回测/归因参数

- 数据区间：本阶段批量交付 6 个缺失 request：`stage152_req_0012_lh2505_DCE_20250307`、`stage152_req_0013_si2509_GFEX_20250710`、`stage152_req_0033_au2412_SHFE_20241017`、`stage152_req_0034_au2510_SHFE_20250902`、`stage152_req_0126_au2412_SHFE_20241016`、`stage152_req_0127_au2510_SHFE_20250901`。
- 账户规模：沿用当前研究线官方路径口径。
- 成本口径：沿用 Stage160/153 官方路径总滑点口径；本阶段不运行新回测。
- 样本过滤：固定选择策略为 `missing_stage153_ready_then_complete_remaining_right_tail_first_request_id_not_trade_rule`。这里使用 right-tail 只是 Stage152 manifest 的覆盖义务，不是交易筛选，也不允许后续把右尾标签直接变成规则。
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
  - Stage169：
    - `decision=stage169_right_tail_completion_tick_aggregate_delivery_written_run_stage160_153_no_rule`
    - `next_best_action=rerun_stage160_then_stage153`
    - `ready_before_count=30`
    - `remaining_before_count=203`
    - `selected_request_count=6`
    - `selected_right_tail_window_count=12`
    - `credential_present=1`
    - `fetch_attempted_count=6`
    - `fetch_extracted_count=6`
    - `delivery_success_count=6`
    - `delivered_right_tail_window_count=12`
    - `expected_files_written=18`
    - `raw_written_count=6`
    - `normalized_written_count=6`
    - `proof_written_count=6`
    - `raw_tick_row_count=129067`
    - `normalized_row_count=1258`
    - `positive_volume_row_count=1256`
    - `window_precheck_count=12`
    - `window_precheck_pass_count=12`
    - `window_precheck_fail_for_written_count=0`
  - 单 request 交付：
    - `lh2505.DCE`：raw ticks `8643`、normalized `136`、positive volume `135`、window `3/3`
    - `si2509.GFEX`：raw ticks `16146`、normalized `136`、positive volume `135`、window `3/3`
    - `au2412.SHFE` 2024-10-17：raw ticks `53603`、normalized `491`、positive volume `491`、window `2/2`
    - `au2510.SHFE` 2025-09-02：raw ticks `19823`、normalized `193`、positive volume `193`、window `2/2`
    - `au2412.SHFE` 2024-10-16：raw ticks `15712`、normalized `151`、positive volume `151`、window `1/1`
    - `au2510.SHFE` 2025-09-01：raw ticks `15140`、normalized `151`、positive volume `151`、window `1/1`
  - Stage160 复验：
    - `incoming_root_exists=1`
    - `present_expected_file_count=108/699`
    - `missing_expected_file_count=591`
    - `arrival_completion_pct=15.4506%`
    - `raw_file_present_count=36`
    - `normalized_file_present_count=36`
    - `proof_file_present_count=36`
    - `request_complete_triplet_count=36/233`
    - `request_partial_triplet_count=0`
    - `request_missing_triplet_count=197`
    - `unexpected_file_count=0`
    - `stage153_trigger_allowed=0`
  - Stage153 复验：
    - `request_ready_count=36/233`
    - `required_window_count=657`
    - `proof_json_valid_count=36`
    - `proof_raw_sha256_match_count=36`
    - `proof_identity_match_count=36`
    - `proof_no_trade_policy_declared_count=36`
    - `normalized_schema_pass_count=36`
    - `forbidden_provenance_marker_count=0`
    - `window_coverage_pass_count=102/657`
    - `right_tail_window_coverage_pass_count=54/54`
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

- Stage169 report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage169_right_tail_completion_tick_aggregate_proofed_delivery/qmt_roll_stage169_c9_minrisk_right_tail_completion_tick_aggregate_proofed_delivery_report_stage169_right_tail_completion_tick_aggregate_proofed_delivery_v1.md`
- Stage169 summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage169_right_tail_completion_tick_aggregate_proofed_delivery/qmt_roll_stage169_c9_minrisk_right_tail_completion_tick_aggregate_proofed_delivery_summary_stage169_right_tail_completion_tick_aggregate_proofed_delivery_v1.csv`
- Stage169 selected requests：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage169_right_tail_completion_tick_aggregate_proofed_delivery/qmt_roll_stage169_c9_minrisk_right_tail_completion_tick_aggregate_proofed_delivery_selected_requests_stage169_right_tail_completion_tick_aggregate_proofed_delivery_v1.csv`
- Stage169 request run status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage169_right_tail_completion_tick_aggregate_proofed_delivery/qmt_roll_stage169_c9_minrisk_right_tail_completion_tick_aggregate_proofed_delivery_request_run_status_stage169_right_tail_completion_tick_aggregate_proofed_delivery_v1.csv`
- Stage169 delivery audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage169_right_tail_completion_tick_aggregate_proofed_delivery/qmt_roll_stage169_c9_minrisk_right_tail_completion_tick_aggregate_proofed_delivery_delivery_audit_stage169_right_tail_completion_tick_aggregate_proofed_delivery_v1.csv`
- Stage169 window precheck：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage169_right_tail_completion_tick_aggregate_proofed_delivery/qmt_roll_stage169_c9_minrisk_right_tail_completion_tick_aggregate_proofed_delivery_window_precheck_stage169_right_tail_completion_tick_aggregate_proofed_delivery_v1.csv`
- Stage160 summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage160_authoritative_minute_arrival_monitor/qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_summary_stage160_authoritative_minute_arrival_monitor_v1.csv`
- Stage153 summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage153_authoritative_minute_ohlcv_intake_validator/qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator_summary_stage153_authoritative_minute_ohlcv_intake_validator_v1.csv`
- incoming：本阶段写入 6 个 request 的 raw/normalized/proof 三件套；叠加 Stage164-168 后当前 `incoming/stage152_authoritative_minute_ohlcv` 共 36 个 complete triplets、108 个文件。
- orders：无；本阶段禁止报单和 true engine。
- daily：无新增回测 daily；使用官方路径资金曲线图跟踪。
- quality：
  - Stage169 5 张 PNG 均非空；
  - Stage160 5 张 PNG 均非空；
  - Stage153 5 张 PNG 均非空。

## 视觉分析

- Stage169 官方路径图显示资金曲线、回撤和 broker10 未改变，说明本阶段没有引入策略收益变化。
- Stage169 selected right-tail completion 图显示本批只针对剩余 right-tail 覆盖，其中包含 DCE、GFEX 与 SHFE 黄金夜盘跨日窗口。
- Stage169 delivery matrix 显示 6 个 request 的 raw、normalized、proof 全部写入，没有 partial triplet。
- Stage169 window precheck matrix 显示 12 个 right-tail 窗口全部通过；黄金夜盘跨日窗口有明显更长的 session guard，实际 bar 与正量覆盖均通过。
- Stage153 window heatmap 最新状态显示 right-tail 已从 `42/54` 补到 `54/54`；maxDD 保持 `30/72`，bottom-loss 保持 `24/54`。

## 结论

- 本阶段结论：Stage169 成功把 right-tail 覆盖补满到 `54/54`，当前线权威分钟数据覆盖推进到 `36` 个 request / `102` 个窗口。所有 36 个 ready request 均通过 proof JSON、raw sha、身份、no-trade policy、normalized schema 和 forbidden marker 检查。
- 是否进入下一步：是，但下一步仍是数据覆盖扩展，不是策略。
- 下一步：继续沿 Stage152 manifest 批量补齐 bottom-loss 与 maxDD 窗口；每批写入后必须重跑 Stage160/153。只有 Stage153 全包窗口覆盖、Stage156/157/158 lineage 与 feature table 闸门通过后，才允许进入只读 feature atlas 或分钟信号候选。

## 过拟合反思

- 运行前判断：否。Stage169 只按 Stage153 剩余 right-tail 覆盖缺口补数据，没有调交易阈值、没有运行 true engine，也没有使用右尾标签构造交易规则。
- 运行后判断：否，但必须强调：right-tail 已满覆盖只证明未来可以保护右尾，不证明已经找到高质量信号。
- 原因：本阶段成功标准来自 proof、raw sha、schema、forbidden marker 和窗口覆盖；补完 right-tail 是为了让未来降回撤候选必须面对右尾保护约束，不能为了漂亮回撤牺牲 C9 的主要收益来源。

## 继续价值反思

- 运行前判断：有。Stage168 后 right-tail 仍缺 `12` 个窗口，尤其包含 GFEX 和黄金夜盘跨日样本；这些可能是未来规则最容易误伤的右尾反例。
- 运行后判断：有。Stage169 补满 right-tail，让后续视觉 atlas 至少在右尾保护维度具备完整样本。
- 原因：目标要求收益保留 80% 以上；右尾完整覆盖是收益保留约束的基础设施。下一步应把 bottom-loss 和 maxDD 也补到相近覆盖水平，再进入 feature lineage 和视觉 atlas。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage169 摘要。
- 是否更新 `research/registry.md`：否，未新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否，非正式候选、非策略突破、非路线废弃；等核心窗口批量覆盖并打通 Stage156/157/158 后再考虑。
