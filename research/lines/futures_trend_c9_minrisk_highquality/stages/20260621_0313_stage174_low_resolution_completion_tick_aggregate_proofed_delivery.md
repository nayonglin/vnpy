# Stage174 low-resolution 剩余补完 tick 聚合 proofed delivery

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 03:13 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：权威分钟 OHLCV 数据补齐与验收；不是策略版本
- 是否重要突破：否。low-resolution 覆盖已补完，但普通窗口仍缺，不能进入特征或策略阶段。
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Man Group 趋势回撤与 whipsaw 讨论：`https://www.man.com/insights/is-this-time-different`
  - Alpha Architect 趋势跟踪 whipsaw 讨论：`https://alphaarchitect.com/trend-following-the-epitome-of-no-pain-no-gain/`
  - TqSdk GitHub：`https://github.com/shinnytech/tqsdk-python`
  - TqSdk 行情文档：`https://tqsdk-python.readthedocs.io/en/latest/usage/mddatas.html`
  - W3C PROV-DM：`https://www.w3.org/TR/prov-dm/`
- 我的判断：趋势系统的回撤和 whipsaw 是常态，不能把历史回撤、低分辨率或最终盈亏标签直接写成交易过滤器。Stage174 的价值在于补齐分钟数据 coverage 与 provenance，使后续如果提出分钟级候选，能先排除数据盲区和成交量缺失造成的错觉；TqSdk 只作为授权历史 tick/行情获取通道，proof 文件保留来源、hash 和无交易策略声明。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage174_low_resolution_completion_tick_aggregate_proofed_delivery.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `STAGE174_MAX_REQUESTS`，默认 `64`
  - `STAGE174_WRITE_INCOMING`，默认 `1`
  - `STAGE174_OVERWRITE_EXISTING`，默认 `0`
  - `STAGE174_MAX_SECONDS_TICK`，默认 `90`
  - `STAGE174_TICK_DATA_LENGTH`，默认 `120000`
  - `STAGE174_MIN_NORMALIZED_ROWS`，默认 `10`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage152 manifest 中剩余 low-resolution 覆盖缺口；本批 `2020-07-20` 至 `2026-02-13`，覆盖 CZCE/SHFE。
- 账户规模：沿用官方 C9 路径统计，不改变资金口径。
- 成本口径：沿用官方 C9 路径统计，`total_slippage=2730130.0`。
- 样本过滤：仅选择 Stage153 尚未 ready 且 `low_resolution_window_count > 0` 的剩余 request；这是 manifest 覆盖义务，不是交易筛选条件。
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
  - Stage174：`decision=stage174_low_resolution_completion_tick_aggregate_delivery_written_run_stage160_153_no_rule`
  - `ready_before_count=111`
  - `remaining_before_count=122`
  - `selected_request_count=25`
  - `selected_low_resolution_window_count=66`
  - `selected_right_tail_window_count=0`
  - `selected_bottom_loss_window_count=0`
  - `selected_maxdd_window_count=0`
  - `fetch_attempted_count=25`
  - `fetch_extracted_count=25`
  - `delivery_success_count=25`
  - `delivered_low_resolution_window_count=66`
  - `expected_files_written=75`
  - `raw_written_count=25`
  - `normalized_written_count=25`
  - `proof_written_count=25`
  - `raw_tick_row_count=326784`
  - `normalized_row_count=3336`
  - `positive_volume_row_count=3322`
  - `window_precheck_count=66`
  - `window_precheck_pass_count=66`
  - `window_precheck_fail_for_written_count=0`
  - 交易所分布：CZCE `15` 个 request / `45` 窗口，SHFE `10` 个 request / `21` 窗口。
  - Stage160 复验：`present_expected_file_count=408/699`，`request_complete_triplet_count=136/233`，`request_partial_triplet_count=0`，`unexpected_file_count=0`
  - Stage153 复验：`request_ready_count=136/233`，`window_coverage_pass_count=384/657`，`right_tail_window_coverage_pass_count=54/54`，`bottom_loss_window_coverage_pass_count=54/54`，`maxdd_window_coverage_pass_count=72/72`，`low_resolution_window_coverage_pass_count=279/279`
  - Stage153 质量：`proof_json_valid_count=136`，`proof_raw_sha256_match_count=136`，`proof_identity_match_count=136`，`proof_no_trade_policy_declared_count=136`，`normalized_schema_pass_count=136`，`forbidden_provenance_marker_count=0`
  - Stage153 仍然：`stage154_feature_build_allowed=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage174_low_resolution_completion_tick_aggregate_proofed_delivery/qmt_roll_stage174_c9_minrisk_low_resolution_completion_tick_aggregate_proofed_delivery_report_stage174_low_resolution_completion_tick_aggregate_proofed_delivery_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage174_low_resolution_completion_tick_aggregate_proofed_delivery/qmt_roll_stage174_c9_minrisk_low_resolution_completion_tick_aggregate_proofed_delivery_summary_stage174_low_resolution_completion_tick_aggregate_proofed_delivery_v1.csv`
- selected requests：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage174_low_resolution_completion_tick_aggregate_proofed_delivery/qmt_roll_stage174_c9_minrisk_low_resolution_completion_tick_aggregate_proofed_delivery_selected_requests_stage174_low_resolution_completion_tick_aggregate_proofed_delivery_v1.csv`
- request run status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage174_low_resolution_completion_tick_aggregate_proofed_delivery/qmt_roll_stage174_c9_minrisk_low_resolution_completion_tick_aggregate_proofed_delivery_request_run_status_stage174_low_resolution_completion_tick_aggregate_proofed_delivery_v1.csv`
- delivery audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage174_low_resolution_completion_tick_aggregate_proofed_delivery/qmt_roll_stage174_c9_minrisk_low_resolution_completion_tick_aggregate_proofed_delivery_delivery_audit_stage174_low_resolution_completion_tick_aggregate_proofed_delivery_v1.csv`
- window precheck：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage174_low_resolution_completion_tick_aggregate_proofed_delivery/qmt_roll_stage174_c9_minrisk_low_resolution_completion_tick_aggregate_proofed_delivery_window_precheck_stage174_low_resolution_completion_tick_aggregate_proofed_delivery_v1.csv`
- quality：Stage160/Stage153 已重跑并覆盖更新同名 summary/audit/visual 输出。

## 视觉检查

- Stage174 5 张 PNG 均非空，像素跨度均为 `765`：
  - delivery matrix：`1700x2337`
  - gate status：`2210x1190`
  - official path：`2550x1870`
  - selected low-resolution completion priority：`2210x2464`
  - window precheck：`2040x3141`
- Stage160 5 张 PNG 均非空。
- Stage153 5 张 PNG 均非空。
- 视觉判断：
  - Stage174 selected priority 图只有 low-resolution 蓝色栈，`3/2/1` 窗口长度清晰，没有 right-tail、bottom-loss、maxDD 混入。
  - Stage174 window precheck matrix 的 `coverage_precheck_pass` 一列全绿，66 个窗口全部通过，且 observed/positive volume 两列没有空白异常。
  - Stage153 window coverage heatmap 中 right-tail、bottom-loss、maxDD、low-resolution 四列全绿；ordinary 仍为红色 `0/91`，说明下一步仍是普通覆盖补齐，不允许提前进入 feature builder。

## 结论

- 本阶段结论：Stage174 成功一次性补完剩余 low-resolution 样本，low-resolution 覆盖从 `213/279` 提升到 `279/279`。当前线权威分钟数据地基推进到 `136` 个 request / `384` 个窗口，关键尾部和低分辨率覆盖均已满。
- 是否进入下一步：进入下一步数据覆盖，不进入策略规则。
- 下一步：补普通 coverage 缺口；全包仍是 `384/657`，还缺 `97` 个 request / `273` 个窗口。Stage153 全包通过前继续禁止 Stage154 feature builder、分钟规则、true engine、A/B 或正式候选。

## 过拟合反思

- 运行前判断：否。Stage174 只补 Stage152/153 明确缺失的 low-resolution coverage，不使用收益、亏损、回撤结果构造规则。
- 运行后判断：否。结果只是数据覆盖完成，官方资金曲线和策略路径未改变，也没有按品种、年份、交易所或盈亏做参数选择。
- 原因：low-resolution 是执行分辨率和数据质量问题，不是 alpha 标签；把它先补齐，是为了防止后续把数据盲区误判为高质量信号。

## 继续价值反思

- 运行前判断：有。low-resolution 还缺 `66` 个窗口，若不补齐，分钟级视觉分析会被数据缺口污染。
- 运行后判断：有。关键尾部与 low-resolution 已满覆盖，但普通窗口还缺 `273` 个，Stage154 仍被禁止。
- 原因：目标要求基于分钟 K 线进出场并用视觉分析判断信号质量；在全包 coverage 未完成前，任何策略结论都可能混入数据偏差。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage174 摘要。
- 是否更新 `research/registry.md`：否，非正式候选、非路线合并、非重大突破。
- 是否追加根目录 `memory.md/back_log.md`：否，非正式候选、非重大突破。
