# Stage208 predecision lookback tick aggregate delivery batch

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 13:19 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage177 predecision lookback 数据地基小批量扩容；刷新 Stage179/180/181 审计链路。
- 是否重要突破：否。本阶段只把已交付样本从 `108` 扩到 `112`，不是策略收益/回撤突破。
- 是否触发A/B：否。没有策略候选、没有 true engine、没有正式配置变更。

## 外部调研与判断

- 参考资料：
  - TqSdk `TqBacktest` 官方文档：https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html
  - pandas `DataFrame.rolling` 官方文档：https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html
  - vn.py `BarGenerator` 源码：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py
- 我的判断：
  - TqSdk/tick 数据继续只作为历史数据入口；timeout、拉取耗时和低分辨率标签只能描述数据工程边界，不能被解释为市场质量或交易信号。
  - pandas rolling 与 cutoff 的核心纪律仍是 `bar_end_ts <= decision_ts`；Stage181 的全部审计特征必须来自 Stage180 cutoff-filtered source。
  - vn.py BarGenerator 的经验继续提醒：分钟地基不能只看 close 或收益，要同时审计 OHLCV、成交额和持仓变化，否则容易把数据缺口误读成策略结构。
  - Stage208 仍是覆盖义务扩容；本批 `low_resolution`、closed bar 覆盖和 positive volume 覆盖只允许作为质检字段，不允许交易化。

## 本次版本改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage208_predecision_lookback_tick_aggregate_delivery_batch.py`
- 新增阶段记录：`research/lines/futures_trend_c9_minrisk_highquality/stages/20260621_1319_stage208_predecision_lookback_tick_aggregate_delivery_batch.md`
- 修改当前线状态：`research/lines/futures_trend_c9_minrisk_highquality/LINE.md`
- 新增参数：
  - `STAGE208_MAX_REQUESTS=4`
  - `STAGE208_TICK_DATA_LENGTH=10000`
  - `STAGE208_MAX_SECONDS_TICK=240`
  - `STAGE208_MIN_POSITIVE_VOLUME_BARS_REQUIRED=60`
  - `target_min_predecision_closed_bars=61`
- 修改参数：无。沿用 Stage178/179/180/181 的 point-in-time、hash/schema、cutoff 和审计特征链路。
- 删除参数：无。
- 新增回测结果：无。本阶段没有运行 true engine，没有生成收益候选。
- 修改回测结果：无。
- 删除回测结果：无。

## Stage208 交付结果

- 决策：`stage208_predecision_lookback_tick_aggregate_delivery_written_refresh_stage179_180_181_no_rule`
- 选择策略：`stage177_remaining_highest_priority_exchange_round_robin_stage208_no_pnl_no_rule`
- 本批选择 `4` 个 request，全部为 `low_resolution` 覆盖义务：
  - `stage177_req_0091_SM409_CZCE_20240523`：`extracted`，raw `268,669`，normalized `2,261`，positive `2,261`，observed closed bars `2,260`
  - `stage177_req_0103_au2006_SHFE_20200206`：`extracted`，raw `80,903`，normalized `905`，positive `905`，observed closed bars `904`
  - `stage177_req_0085_SA501_CZCE_20241104`：`timeout_after_240s`，raw `370,965`，normalized `3,133`，positive `3,102`，observed closed bars `3,133`
  - `stage177_req_0110_fu2405_SHFE_20240222`：`extracted`，raw `143,114`，normalized `1,268`，positive `1,268`，observed closed bars `1,267`
- 本批合计：
  - `delivery_success_count=4/4`
  - `expected_files_written=12/12`
  - `raw_tick_row_count=863,651`
  - `normalized_row_count=7,567`
  - `positive_volume_row_count=7,536`
  - `window_precheck_pass_count=4/4`
  - `min_observed_predecision_closed_bar_count=904`
  - `max_observed_predecision_closed_bar_count=3,133`
  - `right_tail=0`，`bottom_loss=0`，`maxDD=0`，`low_resolution=4`
- 重要边界：`SA501` 为 `timeout_after_240s`，但已抽取到远超 `61` 根决策前闭合 bar 并通过后续 proof/hash/schema/cutoff 验证；这不能被解读为完整 14 天全量保证。

## Stage179/180/181 刷新结果

- Stage179：
  - `present_triplet_count=112`
  - `proof_hash_schema_identity_ready_count=112`
  - `filtered_request_ready_count=112`
  - `direct_file_request_ready_count=34`
  - `post_decision_bar_count=78`
  - `strategy_feature_usable=0`
- Stage180：
  - `filtered_source_written_count=112`
  - `cutoff_filtered_source_ready_count=112`
  - `filtered_source_row_count=313,192`
  - `filtered_positive_volume_row_count=312,965`
  - `post_decision_removed_count=78`
  - `lineage_pass_count=112`
- Stage181：
  - `feature_audit_row_written_count=112`
  - `feature_ready_cell_count=1120/1120`
  - `source_cutoff_guard_pass_count=112/112`
  - `lineage_pass_count=112/112`
  - `formal_feature_table_row_written_count=0`
  - `strategy_feature_usable=0`

## 资金曲线与正式路径指标

本阶段没有重新确认或修改正式路径；资金曲线指标保持不变，只用于确认数据地基扩容没有误触策略执行：

- 期末权益：`39,176,437.60`
- 总收益：`26,017.63%`
- 最大回撤：`-45.08%`
- Sharpe：`1.633`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.09%`
- Broker10 最大保证金/权益：`111.74%`

## 视觉与特征审计

- Stage208 precheck 图：4 个 request 全绿，全部超过 `61` 根决策前闭合 bar 要求。
- Stage180 tail removal 图：累计 `78` 根决策后 bar 被剔除，避免未来函数。
- Stage181 readiness 图：`112 x 10` 个审计单元全绿。
- Stage181 value heatmap：非空；`directional_efficiency_30m` 上界扩到 `0.7183098592`，说明横截面覆盖继续变化，但不能构成交易条件。
- 关键 PNG 非空校验：Stage208/179/180/181 共 `20` 张 PNG 全部非空。
- 当前 Stage181 特征横截面：
  - `bar_return_1m`：min `-0.0147459165`，max `0.0135135135`，mean `0.0003096730`
  - `range_ratio_1m`：min `0.0000000000`，max `0.0075741637`，mean `0.0008618894`
  - `directional_efficiency_30m`：min `0.0000000000`，max `0.7183098592`，mean `0.1760994559`
  - `realized_volatility_30m`：min `0.0001564239`，max `0.0041081855`，mean `0.0009756026`
  - `true_range_median_30m`：min `0.0600000000`，max `60.0000000000`，mean `7.8607142857`
  - `volume_participation_30m`：min `0.8666666667`，max `1.0000000000`，mean `0.9979166667`
  - `volume_zscore_60m`：min `-0.5900707269`，max `0.5063034363`，mean `0.0367444028`
  - `open_interest_delta_60m`：min `-65,502`，max `47,119`，mean `-3,256.4553571429`
  - `turnover_vwap_gap_30m`：min `-0.0138560842`，max `0.0122075013`，mean `0.0000178379`
  - `closed_bar_count_coverage`：min `904`，max `4,670`，mean `2,796.3571428571`

## 结论

- Stage208 把点时化分钟特征地基从 `108` 个样本推进到 `112` 个样本。
- 现在仍距离 Stage177 的 `219` 个 entry decision 很远；样本覆盖显著扩大前，继续禁止分钟规则、true engine、A/B 或正式候选。
- 本阶段只证明数据交付、proof/hash/schema、cutoff 和审计特征链路可继续稳定扩展；没有证明任何降低回撤规则。
- 本批 `4` 个 request 全部交付并通过审计，其中 `1` 个触达 timeout 边界；timeout 只描述数据抓取边界，不是交易质量标签。

## 开始与结束反思

- 开始前是否过拟合：否。Stage208 只按 Stage177 剩余覆盖义务和交易所轮转补数据，没有按收益、回撤或 PnL 标签选样。
- 开始前是否值得继续：是。当前目标需要分钟级高质量信号，但在样本地基只有 `108/219` 时写规则会过浅。
- 结束后是否过拟合：否。本阶段没有新增交易规则、没有 true engine、没有正式配置变更；低分辨率、timeout 和审计特征继续被限制为数据审计字段。
- 结束后是否值得继续：是。`112/219` 仍不足以支撑普世规则判断，下一步 Stage209 应继续同口径扩展 Stage177 delivery，并复跑 Stage179/180/181。

## 后续规划与 TODO

- Stage209 继续小批量扩展 Stage177 predecision lookback delivery，维持交易所轮转和 priority 纪律。
- 每批继续生成并检查资金曲线、precheck、tail removal、readiness、value heatmap。
- 在覆盖显著扩大前，不做规则搜索、不做阈值扫描、不跑 true engine、不触发 A/B。
