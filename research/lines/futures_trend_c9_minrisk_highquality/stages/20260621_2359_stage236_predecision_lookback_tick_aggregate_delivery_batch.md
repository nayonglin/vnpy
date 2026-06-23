# Stage236 - predecision lookback tick aggregate delivery batch

- 时间：2026-06-21 23:59 CST
- 工作模式：day
- 研究线：futures_trend_c9_minrisk_highquality
- 本次性质：Stage177 predecision lookback 分钟数据地基补齐，第五十六批受控单请求交付
- 是否重要突破版本：否

## 开始前反思

- 是否可能过拟合：否。本阶段只按 Stage177 剩余 request 的固定优先级和交易所轮转补齐事前数据，不读取或筛选最终盈亏，不创建交易规则。
- 是否仍有价值继续做：是。当前线的第一性问题仍是分钟级特征必须先有点时化、可复验、无未来函数的数据地基；补齐覆盖比在未完成覆盖时直接做规则更有价值。

## 外部调研与判断

- TqSdk 官方对象文档说明 K 线和 tick 字段含 `datetime`、价格、成交量、持仓量等基础字段，适合作为只读行情源做决策前窗口聚合与 proof，但字段可得性不等于可直接交易化：https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.objs.html
- pandas rolling 文档确认 rolling/min_periods 等窗口计算语义应显式声明，后续 formal feature gate 需要固定窗口、min_periods 和 cutoff 口径：https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html
- vn.py `BarGenerator` 提供本地行情聚合惯例，说明分钟 bar 聚合应优先遵循成熟框架语义，而不是用 ad hoc 字符串或标签推断：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py
- 判断结论：继续沿当前研究线补齐 Stage177 predecision lookback 数据是合理的；本阶段不应引入 alpha、参数扫描、true engine、A/B 或正式候选，只交付数据和审计证据。

## 本次改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage236_predecision_lookback_tick_aggregate_delivery_batch.py`
- 新增参数：
  - `STAGE236_MAX_REQUESTS=1`
  - `STAGE236_MAX_SECONDS_TICK=180`
  - `STAGE236_TICK_DATA_LENGTH=10000`
  - `STAGE236_MIN_NORMALIZED_ROWS=61`
  - `STAGE236_MIN_POSITIVE_VOLUME_BARS=60`
  - `STAGE236_WRITE_INCOMING=1`
  - `STAGE236_OVERWRITE_EXISTING=0`
- 修改参数：无
- 删除参数：无
- 新增回测结果：无，本阶段没有运行 true engine 或策略回测
- 修改回测结果：无
- 删除回测结果：无
- 代码边界：不写 formal feature table，不创建策略规则，不运行 true engine，不触发 A/B，不改变 official config，不连接 CTP，不调用 order API

## Stage236 交付结果

- decision：`stage236_predecision_lookback_tick_aggregate_delivery_written_refresh_stage179_180_181_no_rule`
- selection_policy：`stage177_remaining_highest_priority_exchange_round_robin_stage236_no_pnl_no_rule`
- 选择 request：`stage177_req_0149_FG409_CZCE_20240522`
- 合约：`FG409.CZCE`
- 交易所：CZCE
- 决策日：2024-05-22
- 请求窗口：2024-05-08 09:00:00 至 2024-05-22 09:00:00
- tick_fetch_status：`timeout_after_180s`
- delivery_success_count：1/1
- expected_files_written：3/3
- raw_tick_row_count：198,008
- normalized_row_count：1,682
- positive_volume_row_count：1,669
- window_precheck_pass_count：1/1
- observed_predecision_closed_bar_count：1,682
- target_min_predecision_closed_bars：61
- min_positive_volume_bars_required：60
- 本批判断：虽然拉取以 180 秒超时结束，但已经取得远超最低门槛的决策前闭合分钟 bar，并通过 proof/hash/schema/cutoff 后续验证；不能把 timeout 或行数差异解读成交易质量标签。

## Stage179/180/181 刷新结果

- Stage179：
  - present_triplet_count：213/219
  - proof_hash_schema_identity_ready_count：213
  - filtered_request_ready_count：213
  - direct_file_request_ready_count：72
  - post_decision_bar_count：141
  - strategy_feature_usable：0
- Stage180：
  - filtered_source_written_count：213
  - cutoff_filtered_source_ready_count：213
  - filtered_source_row_count：589,843
  - filtered_positive_volume_row_count：589,325
  - post_decision_removed_count：141
  - lineage_pass_count：213
- Stage181：
  - feature_audit_row_written_count：213
  - feature_ready_cell_count：2,130/2,130
  - source_cutoff_guard_pass_count：213/213
  - lineage_pass_count：213/213
  - formal_feature_table_row_written_count：0
  - strategy_feature_usable：0

## 当前路径指标

本阶段没有改动策略路径，以下指标保持为当前线只读参照：

- 期末权益：39,176,437.60
- 总收益：26,017.625067%
- 最大回撤：-45.082656%
- Sharpe：1.633096
- 总滑点：2,730,130
- 总交易次数：787
- 胜率：36.090226%
- 最大 broker10 保证金/权益：111.736478%

## 视觉核验

- Stage236 official path delivery status：资金曲线、回撤和 broker10 路径未改变，底部只显示本批 selected/delivered/precheck/files 计数。
- Stage236 predecision window precheck：`stage177_req_0149_FG409_CZCE_20240522` 单行全绿，`observed_predecision_closed_bar_count=1682`、`positive_volume_bar_count=1669`、`coverage_precheck_pass=1`。
- Stage180 post-decision tail removed：仍显示 `141` 根决策后 bar 已被剔除，cutoff 口径未放松。
- Stage181 feature readiness matrix：`213 x 10` readiness 全绿。
- Stage181 feature value heatmap：存在横截面差异，但只作为审计材料，不进入 formal feature table 或策略规则。
- PNG 非空检查：Stage236/180/181 共 15 张 PNG 全部非空。

## 结论

- 点时化分钟特征地基从 `212/219` 推进到 `213/219`，剩余 `6` 个 entry decision。
- Stage236 新增 FG409 2024-05-22 的 raw/normalized/proof 三件套，并完成 Stage179/180/181 全链路刷新。
- 这仍是数据工程和审计阶段，不是策略效果突破；继续禁止分钟规则、true engine、A/B 或正式候选。

## 后续规划与 TODO

- Stage237 继续按当前研究线用受控单请求或短批补剩余 Stage177 delivery。
- 每批后继续刷新 Stage179/180/181，并检查 cutoff、lineage、readiness、PNG 非空和视觉一致性。
- 待 `219/219` 覆盖完成后，再设计 formal feature gate；在 gate 完成前不做收益驱动参数扫描。

## 结束反思

- 是否过拟合：否。全流程只扩展事前数据覆盖，未使用最终收益或回撤标签选择样本，也未把 heatmap 差异交易化。
- 是否仍有价值继续做：是。覆盖已经接近全量，剩余 6 个样本补齐后才有资格讨论可复验的 formal feature gate；当前继续推进的边际价值仍高。
