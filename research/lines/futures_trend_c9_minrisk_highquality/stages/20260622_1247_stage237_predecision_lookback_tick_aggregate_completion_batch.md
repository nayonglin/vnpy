# Stage237 - predecision lookback tick aggregate completion batch

- 时间：2026-06-22 12:47 CST
- 工作模式：day
- 研究线：futures_trend_c9_minrisk_highquality
- 本次性质：Stage177 predecision lookback 分钟数据地基最终补齐
- 是否重要突破版本：否，属于数据覆盖完成，不是策略效果突破

## 开始前反思

- 是否可能过拟合：否。本阶段只处理 Stage179 明确列出的剩余 6 个未覆盖 request，不按最终盈亏、回撤、品种表现或 heatmap 形态筛样本。
- 是否仍有价值继续做：是。Stage181 进入 formal feature gate 前必须先完成 `219/219` 点时化覆盖，否则后续任何规则审计都会带有样本覆盖偏差。

## 外部调研与判断

- TqSdk 官方对象文档列出 tick/K 线对象的 `datetime`、价格、成交量、持仓量等字段，说明它适合作为只读行情源，但字段存在不等于可以跳过 proof/cutoff 审计：https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.objs.html
- pandas rolling 文档强调窗口语义和边界参数，后续 formal feature gate 必须固定窗口、min_periods 和 cutoff，不能用样本表现临时调参：https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html
- vn.py `BarGenerator` 是成熟的分钟聚合参考，当前线继续采用确定性聚合和 lineage 审计，而不是用后验标签拼接分钟特征：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py
- 判断结论：补完剩余 6 个 request 是合理的最后一段数据工程；补完后不应继续“覆盖工程”，下一步应转向 formal feature gate 设计。

## 本次改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage237_predecision_lookback_tick_aggregate_completion_batch.py`
- 新增参数：
  - `STAGE237_MAX_REQUESTS=6`
  - `STAGE237_MAX_SECONDS_TICK=240`
  - `STAGE237_TICK_DATA_LENGTH=10000`
  - `STAGE237_MIN_NORMALIZED_ROWS=61`
  - `STAGE237_MIN_POSITIVE_VOLUME_BARS=60`
  - `STAGE237_WRITE_INCOMING=1`
  - `STAGE237_OVERWRITE_EXISTING=0`
- 修改参数：无
- 删除参数：无
- 新增回测结果：无，本阶段没有运行 true engine 或策略回测
- 修改回测结果：无
- 删除回测结果：无
- 代码边界：不写 formal feature table，不创建策略规则，不运行 true engine，不触发 A/B，不改变 official config，不连接 CTP，不调用 order API

## Stage237 补齐结果

- decision：`stage237_predecision_lookback_tick_aggregate_completion_written_refresh_stage179_180_181_no_rule`
- selection_policy：`stage177_remaining_all_completion_stage237_no_pnl_no_rule`
- selected_request_count：6
- delivery_success_count：6/6
- expected_files_written：18/18
- raw_tick_row_count：1,677,770
- normalized_row_count：21,012
- positive_volume_row_count：20,965
- window_precheck_pass_count：6/6
- min_observed_predecision_closed_bar_count：2,090
- max_observed_predecision_closed_bar_count：4,670
- target_min_predecision_closed_bars：61
- min_positive_volume_bars_required：60

| request_id | vt_symbol | tick_fetch_status | normalized | positive_volume | observed_predecision_closed_bars |
|---|---:|---:|---:|---:|---:|
| `stage177_req_0165_SA605_CZCE_20260316` | `SA605.CZCE` | `timeout_after_240s` | 2,615 | 2,587 | 2,615 |
| `stage177_req_0187_au2012_SHFE_20200723` | `au2012.SHFE` | `timeout_after_240s` | 3,786 | 3,786 | 3,786 |
| `stage177_req_0189_cu2012_SHFE_20201117` | `cu2012.SHFE` | `extracted` | 4,661 | 4,660 | 4,660 |
| `stage177_req_0190_cu2203_SHFE_20220211` | `cu2203.SHFE` | `extracted` | 2,091 | 2,091 | 2,090 |
| `stage177_req_0188_au2206_SHFE_20220215` | `au2206.SHFE` | `extracted` | 3,188 | 3,188 | 3,187 |
| `stage177_req_0191_cu2310_SHFE_20230831` | `cu2310.SHFE` | `extracted` | 4,671 | 4,653 | 4,670 |

说明：前两笔虽然以 240 秒超时结束，但均已取得远超 `61` 根最低门槛的决策前闭合分钟，并通过 proof/hash/schema/cutoff 后续验证；不能把 timeout 或行数差异解读成交易质量标签。

## Stage179/180/181 刷新结果

- Stage179：
  - request_count：219
  - present_triplet_count：219/219
  - proof_hash_schema_identity_ready_count：219
  - filtered_request_ready_count：219
  - direct_file_request_ready_count：74
  - post_decision_bar_count：145
  - missing_count：0
  - strategy_feature_usable：0
- Stage180：
  - filtered_source_written_count：219
  - cutoff_filtered_source_ready_count：219
  - filtered_source_row_count：610,851
  - filtered_positive_volume_row_count：610,286
  - post_decision_removed_count：145
  - lineage_pass_count：219
- Stage181：
  - feature_audit_row_written_count：219
  - feature_ready_cell_count：2,190/2,190
  - source_cutoff_guard_pass_count：219/219
  - lineage_pass_count：219/219
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

- Stage237 official path delivery status：资金曲线、回撤和 broker10 路径未改变，底部显示本批 selected/delivered/precheck/files 计数。
- Stage237 predecision window precheck：6 个 request 全绿，`coverage_precheck_pass=1`。
- Stage180 post-decision tail removed：刷新后显示 `145` 根决策后 bar 已被剔除。
- Stage181 feature readiness matrix：`219 x 10` readiness 全绿。
- Stage181 feature value heatmap：存在横截面差异，但只作为审计材料，不进入 formal feature table 或策略规则。
- PNG 非空检查：Stage237/180/181 共 15 张 PNG 全部非空。
- 已知展示口径问题：Stage237 gate 表中 `selected_request_count` 的 required 被基础脚本写成 `0`，原因是 summary 在写入三件套后才计算 remaining；不影响 Stage237 summary、delivery audit 与 Stage179/180/181 的 `219/219` 结论。

## 结论

- Stage177 predecision lookback 点时化分钟数据覆盖已从 `213/219` 补齐到 `219/219`，剩余缺口为 `0`。
- Stage181 只读 feature audit 已达到 `2,190/2,190` ready，但 formal feature table 仍为 `0`，策略规则仍为 `0`。
- 这不是策略效果突破；它完成的是“后续特征审计不再带覆盖缺口”的数据地基。

## 后续规划与 TODO

- 停止继续做覆盖扩展，下一步进入 Stage238：formal feature gate 设计。
- Stage238 应先定义从 audit 到 formal feature table 的准入规则：固定 cutoff、固定窗口、固定缺失处理、固定跨品种尺度归一，不看收益标签调参。
- 在 formal feature gate 通过前，继续禁止分钟规则、true engine、A/B 或正式候选。

## 结束反思

- 是否过拟合：否。补齐对象是预先存在的最后 6 个缺口，且没有任何收益驱动筛选或参数扫描。
- 是否仍有价值继续做：覆盖工程本身已经完成，继续补覆盖没有价值；下一步有价值的是把 `219/219` audit 数据转成可复验、无未来函数的 formal feature gate。
