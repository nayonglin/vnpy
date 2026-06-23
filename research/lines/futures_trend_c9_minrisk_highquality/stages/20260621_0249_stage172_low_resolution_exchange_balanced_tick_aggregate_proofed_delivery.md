# Stage172 low-resolution 交易所均衡 tick 聚合 proofed delivery

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 02:49 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：权威分钟 OHLCV 数据补齐与验收；不是策略版本
- 是否重要突破：否。它推进低分辨率覆盖，但还没有进入特征或策略阶段。
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Man Group 趋势回撤与 whipsaw 讨论：`https://www.man.com/insights/is-this-time-different`
  - A Century of Evidence on Trend-Following Investing：`https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2993026_code277060.pdf?abstractid=2993026`
  - TqSdk 行情文档：`https://tqsdk-python.readthedocs.io/en/latest/usage/mddatas.html`
  - TqBacktest 文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html`
  - W3C PROV-DM：`https://www.w3.org/TR/prov-dm/`
- 我的判断：趋势系统的回撤常来自 whipsaw 和状态切换，但长期收益又依赖跨周期右尾。现在 right-tail、bottom-loss、maxDD 已满覆盖，下一步补 low-resolution 不能只按 request_id 线性推进，否则会过度集中在 CZCE。Stage172 采用交易所轮转均衡，是为了让后续视觉 atlas 更早看到 CZCE/DCE/GFEX/SHFE 的共同数据质量，不是构造交易筛选条件。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage172_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `STAGE172_MAX_REQUESTS`，默认 `24`
  - `STAGE172_WRITE_INCOMING`，默认 `1`
  - `STAGE172_OVERWRITE_EXISTING`，默认 `0`
  - `STAGE172_MAX_SECONDS_TICK`，默认 `90`
  - `STAGE172_TICK_DATA_LENGTH`，默认 `120000`
  - `STAGE172_MIN_NORMALIZED_ROWS`，默认 `10`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage152 manifest 中剩余 low-resolution 覆盖缺口；本批 `2020-01-10` 至 `2025-07-30`，覆盖 CZCE/DCE/GFEX/SHFE。
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
  - Stage172：`decision=stage172_low_resolution_exchange_balanced_tick_aggregate_delivery_written_run_stage160_153_no_rule`
  - `ready_before_count=63`
  - `remaining_before_count=170`
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
  - `raw_tick_row_count=285467`
  - `normalized_row_count=3253`
  - `positive_volume_row_count=3242`
  - `window_precheck_count=72`
  - `window_precheck_pass_count=72`
  - `window_precheck_fail_for_written_count=0`
  - 交易所分布：CZCE `8/24` 窗口、DCE `7/21` 窗口、GFEX `1/3` 窗口、SHFE `8/24` 窗口。
  - Stage160 复验：`present_expected_file_count=261/699`，`request_complete_triplet_count=87/233`，`request_partial_triplet_count=0`，`unexpected_file_count=0`
  - Stage153 复验：`request_ready_count=87/233`，`window_coverage_pass_count=246/657`，`right_tail_window_coverage_pass_count=54/54`，`bottom_loss_window_coverage_pass_count=54/54`，`maxdd_window_coverage_pass_count=72/72`，`low_resolution_window_coverage_pass_count=141/279`
  - Stage153 质量：`proof_json_valid_count=87`，`proof_raw_sha256_match_count=87`，`proof_identity_match_count=87`，`proof_no_trade_policy_declared_count=87`，`normalized_schema_pass_count=87`，`forbidden_provenance_marker_count=0`
  - Stage153 仍然：`stage154_feature_build_allowed=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage172_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery/qmt_roll_stage172_c9_minrisk_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_report_stage172_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage172_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery/qmt_roll_stage172_c9_minrisk_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_summary_stage172_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_v1.csv`
- selected requests：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage172_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery/qmt_roll_stage172_c9_minrisk_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_selected_requests_stage172_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_v1.csv`
- request run status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage172_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery/qmt_roll_stage172_c9_minrisk_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_request_run_status_stage172_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_v1.csv`
- delivery audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage172_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery/qmt_roll_stage172_c9_minrisk_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_delivery_audit_stage172_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_v1.csv`
- window precheck：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage172_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery/qmt_roll_stage172_c9_minrisk_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_window_precheck_stage172_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_v1.csv`
- quality：Stage160/Stage153 已重跑并覆盖更新同名 summary/audit/visual 输出。

## 视觉检查

- Stage172 5 张 PNG 均非空：
  - delivery matrix：`std_sum=298.394863`
  - gate status：`std_sum=281.664184`
  - official path：`std_sum=106.957497`
  - selected low-resolution exchange-balanced priority：`std_sum=189.512620`
  - window precheck：`std_sum=307.254994`
- Stage160 5 张 PNG 均非空。
- Stage153 5 张 PNG 均非空。
- 视觉判断：
  - 官方资金曲线、回撤和 broker10 曲线未改变，说明本阶段没有引入策略收益变化。
  - selected priority 图显示本批覆盖 CZCE/DCE/GFEX/SHFE，而不是被 CZCE 单一交易所主导。
  - delivery matrix 显示 24 个 request 的 raw、normalized、proof 全部写入，没有 partial triplet。
  - window precheck matrix 显示 72 个 low-resolution 窗口全部正量通过；GFEX `si2310` 也通过。

## 结论

- 本阶段结论：Stage172 成功交付一批交易所均衡的 low-resolution 样本，low-resolution 覆盖从 `69/279` 提升到 `141/279`。当前线权威分钟数据地基推进到 `87` 个 request / `246` 个窗口。
- 是否进入下一步：进入下一步数据覆盖，不进入策略规则。
- 下一步：继续补剩余 low-resolution 窗口，当前还剩 `138` 个；全包仍是 `246/657`，Stage153 全包通过前继续禁止 Stage154 feature builder、分钟规则、true engine、A/B 或正式候选。

## 过拟合反思

- 运行前判断：否。Stage172 的交易所轮转是数据覆盖均衡原则，不使用收益、亏损、回撤结果构造规则。
- 运行后判断：否。结果只是 low-resolution 覆盖推进，没有任何收益指标优化动作，也没有改变官方路径。
- 原因：低分辨率标签是数据质量缺口，不是交易状态。若把交易所、年份或品种覆盖差异当成开平仓规则，会明显过拟合。

## 继续价值反思

- 运行前判断：有。关键尾部已满覆盖，但 low-resolution 仍缺 `210` 个窗口，直接做分钟 atlas 会被数据质量缺口扭曲。
- 运行后判断：有。均衡补数后低分辨率缺口降到 `138` 个窗口，后续 atlas 更接近跨交易所共同口径。
- 原因：目标要求基于分钟级 K 线识别高质量信号，前提是分钟数据覆盖、成交量和 provenance 足够稳；否则视觉判断会把数据缺口误看成策略结构。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage172 摘要。
- 是否更新 `research/registry.md`：否，非正式候选、非路线合并、非重大突破。
- 是否追加根目录 `memory.md/back_log.md`：否，非正式候选、非重大突破。
