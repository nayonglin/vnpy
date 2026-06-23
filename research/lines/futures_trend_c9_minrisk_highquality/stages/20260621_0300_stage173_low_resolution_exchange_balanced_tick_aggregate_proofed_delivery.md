# Stage173 low-resolution 第二批交易所均衡 tick 聚合 proofed delivery

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 03:00 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：权威分钟 OHLCV 数据补齐与验收；不是策略版本
- 是否重要突破：否。它继续推进低分辨率覆盖，但还没有进入特征或策略阶段。
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Man Group 趋势回撤与 whipsaw 讨论：`https://www.man.com/insights/is-this-time-different`
  - Alpha Architect 趋势跟踪 whipsaw 讨论：`https://alphaarchitect.com/trend-following-the-epitome-of-no-pain-no-gain/`
  - TqSdk GitHub：`https://github.com/shinnytech/tqsdk-python`
  - TqSdk 行情文档：`https://tqsdk-python.readthedocs.io/en/latest/usage/mddatas.html`
  - W3C PROV-DM：`https://www.w3.org/TR/prov-dm/`
- 我的判断：趋势系统会反复遭遇 whipsaw，但不能用历史 whipsaw/回撤标签直接构造过滤器；当前最有价值的动作仍是把分钟数据覆盖、真实成交量和 provenance 做扎实。Stage173 延续 Stage172 的交易所轮转，是为了防止 low-resolution 覆盖只偏向某个交易所，而不是引入交易所筛选规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage173_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `STAGE173_MAX_REQUESTS`，默认 `24`
  - `STAGE173_WRITE_INCOMING`，默认 `1`
  - `STAGE173_OVERWRITE_EXISTING`，默认 `0`
  - `STAGE173_MAX_SECONDS_TICK`，默认 `90`
  - `STAGE173_TICK_DATA_LENGTH`，默认 `120000`
  - `STAGE173_MIN_NORMALIZED_ROWS`，默认 `10`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage152 manifest 中剩余 low-resolution 覆盖缺口；本批 `2020-01-09` 至 `2026-01-14`，覆盖 CZCE/DCE/SHFE。
- 账户规模：沿用官方 C9 路径统计，不改变资金口径。
- 成本口径：沿用官方 C9 路径统计，`total_slippage=2730130.0`。
- 样本过滤：仅选择 Stage153 尚未 ready 且 `low_resolution_window_count > 0` 的 request，并按交易所轮转；这是 manifest 覆盖义务，不是交易筛选条件。
- 策略/归因口径：不创建交易规则、不运行 true engine、不触发 A/B、不改变 official config、不连接 CTP、不调用 order API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130.0`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - Stage173：`decision=stage173_low_resolution_exchange_balanced_tick_aggregate_delivery_written_run_stage160_153_no_rule`
  - `ready_before_count=87`
  - `remaining_before_count=146`
  - `selected_request_count=24`
  - `selected_low_resolution_window_count=72`
  - `selected_right_tail_window_count=0`
  - `selected_bottom_loss_window_count=0`
  - `selected_maxdd_window_count=0`
  - `fetch_attempted_count=24`
  - `fetch_extracted_count=24`
  - `delivery_success_count=24`
  - `delivered_low_resolution_window_count=72`
  - `expected_files_written=72`
  - `raw_written_count=24`
  - `normalized_written_count=24`
  - `proof_written_count=24`
  - `raw_tick_row_count=346406`
  - `normalized_row_count=3251`
  - `positive_volume_row_count=3240`
  - `window_precheck_count=72`
  - `window_precheck_pass_count=72`
  - `window_precheck_fail_for_written_count=0`
  - 交易所分布：CZCE `11` 个 request / `33` 窗口，DCE `2` 个 request / `6` 窗口，SHFE `11` 个 request / `33` 窗口。
  - Stage160 复验：`present_expected_file_count=333/699`，`request_complete_triplet_count=111/233`，`request_partial_triplet_count=0`，`unexpected_file_count=0`
  - Stage153 复验：`request_ready_count=111/233`，`window_coverage_pass_count=318/657`，`right_tail_window_coverage_pass_count=54/54`，`bottom_loss_window_coverage_pass_count=54/54`，`maxdd_window_coverage_pass_count=72/72`，`low_resolution_window_coverage_pass_count=213/279`
  - Stage153 质量：`proof_json_valid_count=111`，`proof_raw_sha256_match_count=111`，`proof_identity_match_count=111`，`proof_no_trade_policy_declared_count=111`，`normalized_schema_pass_count=111`，`forbidden_provenance_marker_count=0`
  - Stage153 仍然：`stage154_feature_build_allowed=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage173_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery/qmt_roll_stage173_c9_minrisk_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_report_stage173_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage173_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery/qmt_roll_stage173_c9_minrisk_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_summary_stage173_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_v1.csv`
- selected requests：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage173_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery/qmt_roll_stage173_c9_minrisk_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_selected_requests_stage173_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_v1.csv`
- request run status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage173_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery/qmt_roll_stage173_c9_minrisk_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_request_run_status_stage173_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_v1.csv`
- delivery audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage173_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery/qmt_roll_stage173_c9_minrisk_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_delivery_audit_stage173_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_v1.csv`
- window precheck：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage173_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery/qmt_roll_stage173_c9_minrisk_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_window_precheck_stage173_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_v1.csv`
- quality：Stage160/Stage153 已重跑并覆盖更新同名 summary/audit/visual 输出。

## 视觉检查

- Stage173 5 张 PNG 均非空：
  - delivery matrix：`std_sum=298.349062`
  - gate status：`std_sum=281.666337`
  - official path：`std_sum=106.953724`
  - selected low-resolution exchange-balanced priority：`std_sum=189.471872`
  - window precheck：`std_sum=307.316002`
- Stage160 5 张 PNG 均非空。
- Stage153 5 张 PNG 均非空。
- 视觉判断：
  - 官方资金曲线、回撤和 broker10 曲线未改变，说明本阶段没有引入策略收益变化。
  - selected priority 图显示本批集中补 CZCE/SHFE，并完成剩余 DCE low-resolution 覆盖。
  - delivery matrix 显示 24 个 request 的 raw、normalized、proof 全部写入，没有 partial triplet。
  - window precheck matrix 显示 72 个 low-resolution 窗口全部正量通过。

## 结论

- 本阶段结论：Stage173 成功交付第二批交易所均衡 low-resolution 样本，low-resolution 覆盖从 `141/279` 提升到 `213/279`。当前线权威分钟数据地基推进到 `111` 个 request / `318` 个窗口。
- 是否进入下一步：进入下一步数据覆盖，不进入策略规则。
- 下一步：继续补剩余 low-resolution 窗口，当前还剩 `66` 个；全包仍是 `318/657`，Stage153 全包通过前继续禁止 Stage154 feature builder、分钟规则、true engine、A/B 或正式候选。

## 过拟合反思

- 运行前判断：否。Stage173 沿用交易所轮转的数据覆盖原则，不使用收益、亏损、回撤结果构造规则。
- 运行后判断：否。结果只是 low-resolution 覆盖推进，没有任何收益指标优化动作，也没有改变官方路径。
- 原因：交易所和品种只用于覆盖均衡，不能被解释成“哪个交易所更适合交易”的策略结论。

## 继续价值反思

- 运行前判断：有。low-resolution 仍缺 `138` 个窗口，如果不补齐，分钟 atlas 可能把数据缺失误看成信号质量。
- 运行后判断：有。缺口降到 `66` 个窗口，已接近补完，下一批可考虑一次性完成 low-resolution。
- 原因：目标要求基于分钟级 K 线做视觉分析，数据覆盖和成交量 proof 是任何非过拟合判断的前提。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage173 摘要。
- 是否更新 `research/registry.md`：否，非正式候选、非路线合并、非重大突破。
- 是否追加根目录 `memory.md/back_log.md`：否，非正式候选、非重大突破。
