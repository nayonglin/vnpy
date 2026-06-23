# Stage175 ordinary 剩余补完 tick 聚合 proofed delivery

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 03:51 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：权威分钟 OHLCV 数据补齐与验收；不是策略版本
- 是否重要突破：否。Stage152 全包数据覆盖已完成，但这只是数据地基，不是策略候选。
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk GitHub：`https://github.com/shinnytech/tqsdk-python`
  - TqSdk 行情文档：`https://tqsdk-python.readthedocs.io/en/latest/usage/mddatas.html`
  - Apache Arrow/Parquet metadata：`https://arrow.apache.org/docs/python/generated/pyarrow.parquet.RowGroupMetaData.html`
  - pandas rolling window：`https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html`
  - vn.py BarData/TickData：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py`
- 我的判断：TqSdk tick 聚合可以作为当前线 proofed delivery 的补数通道，但只能作为数据来源和 provenance 链路，不是 alpha。普通窗口补齐后仍不能直接写规则，必须继续过 Stage156/157/158 与 point-in-time 防泄漏审计。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage175_ordinary_completion_tick_aggregate_proofed_delivery.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `STAGE175_MAX_REQUESTS`，默认 `128`
  - `STAGE175_WRITE_INCOMING`，默认 `1`
  - `STAGE175_OVERWRITE_EXISTING`，默认 `0`
  - `STAGE175_MAX_SECONDS_TICK`，默认 `90`
  - `STAGE175_TICK_DATA_LENGTH`，默认 `120000`
  - `STAGE175_MIN_NORMALIZED_ROWS`，默认 `10`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage152 manifest 中剩余 ordinary 覆盖缺口；本批 `2020-01-14` 至 `2026-03-16`，覆盖 CZCE/DCE/GFEX/SHFE。
- 账户规模：沿用官方 C9 路径统计，不改变资金口径。
- 成本口径：沿用官方 C9 路径统计，`total_slippage=2730130.0`。
- 样本过滤：仅选择 Stage153 尚未 ready 且不属于 right-tail/bottom-loss/maxDD/low-resolution 的剩余 ordinary request；这是 manifest 覆盖义务，不是交易筛选条件。
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
  - Stage175：`decision=stage175_ordinary_completion_tick_aggregate_delivery_written_run_stage160_153_no_rule`
  - `ready_before_count=136`
  - `remaining_before_count=97`
  - `selected_request_count=97`
  - `selected_right_tail_window_count=0`
  - `selected_bottom_loss_window_count=0`
  - `selected_maxdd_window_count=0`
  - `selected_low_resolution_window_count=0`
  - `fetch_attempted_count=97`
  - `fetch_extracted_count=97`
  - `delivery_success_count=97`
  - `expected_files_written=291`
  - `raw_tick_row_count=1653968`
  - `normalized_row_count=16868`
  - `positive_volume_row_count=16802`
  - `window_precheck_count=273`
  - `window_precheck_pass_count=273`
  - Stage160 复验：`present_expected_file_count=699/699`，`request_complete_triplet_count=233/233`，`request_partial_triplet_count=0`，`unexpected_file_count=0`，`stage153_trigger_allowed=1`
  - Stage153 复验：`request_ready_count=233/233`，`window_coverage_pass_count=657/657`，`right_tail_window_coverage_pass_count=54/54`，`bottom_loss_window_coverage_pass_count=54/54`，`maxdd_window_coverage_pass_count=72/72`，`low_resolution_window_coverage_pass_count=279/279`
  - Stage153 质量：`proof_json_valid_count=233`，`proof_raw_sha256_match_count=233`，`proof_identity_match_count=233`，`proof_no_trade_policy_declared_count=233`，`normalized_schema_pass_count=233`，`forbidden_provenance_marker_count=0`
  - Stage156 复跑：`feature_ready_window_count=657/657`，`positioning_feature_ready_window_count=657/657`，`leakage_guard_pass_count=9/9`
  - Stage157 复跑：`build_plan_ready_feature_count=10/10`，`unit_selftest_pass_count=4/4`，`feature_table_row_written_count=0`
  - Stage158 复跑：`lineage_selftest_pass_count=5/5`，`lineage_pass_window_count=0/657`，因为 Stage157 仍是空跑。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage175_ordinary_completion_tick_aggregate_proofed_delivery/qmt_roll_stage175_c9_minrisk_ordinary_completion_tick_aggregate_proofed_delivery_report_stage175_ordinary_completion_tick_aggregate_proofed_delivery_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage175_ordinary_completion_tick_aggregate_proofed_delivery/qmt_roll_stage175_c9_minrisk_ordinary_completion_tick_aggregate_proofed_delivery_summary_stage175_ordinary_completion_tick_aggregate_proofed_delivery_v1.csv`
- selected requests：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage175_ordinary_completion_tick_aggregate_proofed_delivery/qmt_roll_stage175_c9_minrisk_ordinary_completion_tick_aggregate_proofed_delivery_selected_requests_stage175_ordinary_completion_tick_aggregate_proofed_delivery_v1.csv`
- request run status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage175_ordinary_completion_tick_aggregate_proofed_delivery/qmt_roll_stage175_c9_minrisk_ordinary_completion_tick_aggregate_proofed_delivery_request_run_status_stage175_ordinary_completion_tick_aggregate_proofed_delivery_v1.csv`
- delivery audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage175_ordinary_completion_tick_aggregate_proofed_delivery/qmt_roll_stage175_c9_minrisk_ordinary_completion_tick_aggregate_proofed_delivery_delivery_audit_stage175_ordinary_completion_tick_aggregate_proofed_delivery_v1.csv`
- window precheck：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage175_ordinary_completion_tick_aggregate_proofed_delivery/qmt_roll_stage175_c9_minrisk_ordinary_completion_tick_aggregate_proofed_delivery_window_precheck_stage175_ordinary_completion_tick_aggregate_proofed_delivery_v1.csv`
- quality：Stage160/Stage153/Stage156/Stage157/Stage158 已重跑并覆盖更新同名 summary/audit/visual 输出。

## 视觉检查

- Stage175 5 张 PNG 均非空，像素跨度均为 `765`。
- Stage160、Stage153、Stage156、Stage157、Stage158 共 25 张 PNG 均非空。
- 视觉判断：
  - Stage175 delivery matrix 显示 97 个 request 的 raw/normalized/proof 全部写入，无 partial。
  - Stage153 window coverage heatmap 已显示 right-tail、bottom-loss、maxDD、low-resolution、ordinary 全部通过。
  - Stage156 feature readiness 图显示合同层 feature readiness 全部通过，但 Stage157/158 仍是空跑和 lineage 自测，未写真 feature table。

## 结论

- 本阶段结论：Stage175 成功补完剩余 ordinary 样本，Stage152/153 数据包从 `136/233` request、`384/657` window 推进到 `233/233` request、`657/657` window；所有 proof/schema/hash/window gate 均通过。
- 是否进入下一步：进入下一步 point-in-time materialization 审计，不进入策略规则。
- 下一步：必须检查 Stage156 特征在真实 decision timestamp 之前是否有足够 pre-decision closed bars；如果不足，先扩展 predecision lookback manifest 或预声明更短 lookback 的极简特征，不能直接把 post-entry/event window 写成入场规则。

## 过拟合反思

- 运行前判断：否。Stage175 只补 Stage153 未 ready 的 ordinary coverage，不使用收益、亏损、回撤结果构造规则。
- 运行后判断：否。结果只是数据覆盖完成，官方资金曲线和策略路径未改变，也没有按品种、年份、交易所或盈亏做参数选择。
- 原因：ordinary 是 manifest 覆盖剩余项，不是交易标签。

## 继续价值反思

- 运行前判断：有。ordinary 缺口不补齐，任何分钟级视觉分析都会被全包 coverage 缺失污染。
- 运行后判断：有。数据包已经完整，研究线可以从“补数据”推进到“point-in-time 特征可材料化性审计”，但策略目标仍未完成。
- 原因：目标要求无过拟合的分钟级进出场规则；数据完整只是必要条件，不是充分条件。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage175 摘要。
- 是否更新 `research/registry.md`：否，非正式候选、非路线合并、非重大突破。
- 是否追加根目录 `memory.md/back_log.md`：否，非正式候选、非重大突破。
