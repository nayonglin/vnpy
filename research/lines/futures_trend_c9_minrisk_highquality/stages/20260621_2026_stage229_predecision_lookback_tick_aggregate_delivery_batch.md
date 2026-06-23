# Stage229 predecision lookback tick aggregate delivery batch

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 20:26 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage177 predecision lookback 数据地基小批量扩容；刷新 Stage179/180/181 审计链路。
- 是否重要突破：否。本阶段只把已交付样本从 `192` 扩到 `196`，不是策略收益/回撤突破。
- 是否触发A/B：否。没有策略候选、没有 true engine、没有正式配置变更。

## 外部调研与判断

- 参考资料：
  - TqSdk `tqsdk.objs` 官方文档：https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.objs.html
  - pandas `DataFrame.rolling` 官方文档：https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html
  - vn.py `BarGenerator` 源码：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py
- 我的判断：
  - TqSdk/tick 与 Kline 字段继续只作为历史数据入口和审计字段；`extracted`、拉取耗时、正量差异和覆盖高低只能描述数据工程边界，不能被解释为市场质量或交易信号。
  - pandas rolling 与 cutoff 的核心纪律仍是 `bar_end_ts <= decision_ts`；Stage181 的全部审计特征必须来自 Stage180 cutoff-filtered source。
  - vn.py BarGenerator 的经验继续提醒：分钟地基不能只看 close 或收益，要同时审计 OHLCV、成交额和持仓变化，否则容易把数据缺口误读成策略结构。
  - Stage229 仍是覆盖义务扩容；本批 ordinary 覆盖只说明样本地基扩大，不允许直接交易化。

## 本次版本改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage229_predecision_lookback_tick_aggregate_delivery_batch.py`
- 新增阶段记录：`research/lines/futures_trend_c9_minrisk_highquality/stages/20260621_2026_stage229_predecision_lookback_tick_aggregate_delivery_batch.md`
- 修改当前线状态：`research/lines/futures_trend_c9_minrisk_highquality/LINE.md`
- 新增参数：
  - `STAGE229_MAX_REQUESTS=4`
  - `STAGE229_TICK_DATA_LENGTH=10000`
  - `STAGE229_MAX_SECONDS_TICK=240`
  - `STAGE229_MIN_POSITIVE_VOLUME_BARS=60`
  - `target_min_predecision_closed_bars=61`
- 修改参数：无。沿用 Stage178/179/180/181 的 point-in-time、hash/schema、cutoff 和审计特征链路。
- 删除参数：无。
- 新增回测结果：无。本阶段没有运行 true engine，没有生成收益候选。
- 修改回测结果：无。
- 删除回测结果：无。

## Stage229 交付结果

- 决策：`stage229_predecision_lookback_tick_aggregate_delivery_written_refresh_stage179_180_181_no_rule`
- 选择策略：`stage177_remaining_highest_priority_exchange_round_robin_stage229_no_pnl_no_rule`
- 本批选择 `4` 个 request，全部为 `ordinary` 覆盖义务：
  - `stage177_req_0169_SM209_CZCE_20220419`：`extracted`，raw `155,914`，normalized `2,036`，positive `2,036`，observed closed bars `2,035`
  - `stage177_req_0212_sp2009_SHFE_20200407`：`extracted`，raw `106,839`，normalized `2,035`，positive `2,029`，observed closed bars `2,034`
  - `stage177_req_0134_AP210_CZCE_20220428`：`extracted`，raw `251,847`，normalized `2,261`，positive `2,261`，observed closed bars `2,260`
  - `stage177_req_0213_sp2009_SHFE_20200415`：`extracted`，raw `138,955`，normalized `2,035`，positive `2,035`，observed closed bars `2,034`
- 本批合计：
  - `delivery_success_count=4/4`
  - `expected_files_written=12/12`
  - `raw_tick_row_count=653,555`
  - `normalized_row_count=8,367`
  - `positive_volume_row_count=8,361`
  - `window_precheck_pass_count=4/4`
  - `min_observed_predecision_closed_bar_count=2,034`
  - `max_observed_predecision_closed_bar_count=2,260`
  - `right_tail=0`，`bottom_loss=0`，`maxDD=0`，`low_resolution=0`
- 重要边界：本批 `sp2009` 2020-04-07 有 `6` 根非正量分钟差异，但正量分钟仍有 `2,028` 根，远超 `60` 根门槛并通过后续 proof/hash/schema/cutoff 验证；这只能作为数据审计现象，不是交易过滤条件。

## Stage179/180/181 刷新结果

- Stage179：
  - `present_triplet_count=196`
  - `proof_hash_schema_identity_ready_count=196`
  - `filtered_request_ready_count=196`
  - `direct_file_request_ready_count=61`
  - `post_decision_bar_count=135`
  - `strategy_feature_usable=0`
- Stage180：
  - `filtered_source_written_count=196`
  - `cutoff_filtered_source_ready_count=196`
  - `filtered_source_row_count=546,084`
  - `filtered_positive_volume_row_count=545,695`
  - `post_decision_removed_count=135`
  - `lineage_pass_count=196`
- Stage181：
  - `feature_audit_row_written_count=196`
  - `feature_ready_cell_count=1960/1960`
  - `source_cutoff_guard_pass_count=196/196`
  - `lineage_pass_count=196/196`
  - `formal_feature_table_row_written_count=0`
  - `strategy_feature_usable=0`

## 资金曲线与正式路径指标

本阶段按用户要求不再重复确认谁是正式版；资金曲线指标保持当前研究线既有口径，只用于确认数据地基扩容没有误触策略执行：

- 期末权益：`39,176,437.60`
- 总收益：`26,017.63%`
- 最大回撤：`-45.08%`
- Sharpe：`1.633`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.09%`
- Broker10 最大保证金/权益：`111.74%`

## 视觉与特征审计

- Stage229 official path 图：权益、回撤、broker10 保证金路径未因本阶段改变；底部只显示本批交付状态。
- Stage229 precheck 图：4 个 request 全绿，最低 `2,034` 根决策前闭合 bar，远超 `61` 根要求。
- Stage180 tail removal 图：累计 `135` 根决策后 bar 被剔除，避免未来函数。
- Stage181 readiness 图：`196 x 10` 个审计单元全绿。
- Stage181 value heatmap：非空且有横截面差异；新增样本未破坏 readiness，继续只作为审计现象，不得直接交易化。
- 关键 PNG 非空校验：Stage229/179/180/181 共 `20` 张 PNG 全部非空。
- 当前 Stage181 特征横截面：
  - `bar_return_1m`：min `-0.0148148148`，max `0.0624843789`，mean `0.0009858400`
  - `range_ratio_1m`：min `0.0000000000`，max `0.0075741637`，mean `0.0007399070`
  - `directional_efficiency_30m`：min `0.0000000000`，max `1.0000000000`，mean `0.1843682931`
  - `realized_volatility_30m`：min `0.0001564239`，max `0.0111252506`，mean `0.0010175393`
  - `true_range_median_30m`：min `0.0000000000`，max `70.0000000000`，mean `7.6362244898`
  - `volume_participation_30m`：min `0.8666666667`，max `1.0000000000`，mean `0.9967687075`
  - `volume_zscore_60m`：min `-0.6385072074`，max `0.6711468978`，mean `0.0231124125`
  - `open_interest_delta_60m`：min `-71,441`，max `47,119`，mean `-3,115.4081632653`
  - `turnover_vwap_gap_30m`：min `-0.0145152731`，max `0.0597902774`，mean `0.0006159963`
  - `closed_bar_count_coverage`：min `904`，max `4,758`，mean `2,786.1428571429`

## 结论

- Stage229 把点时化分钟特征地基从 `192` 个样本推进到 `196` 个样本，当前覆盖为 `196/219`，剩余 `23` 个 entry decision。
- 现在仍距离完整覆盖有差距；样本覆盖显著扩大前，继续禁止分钟规则、true engine、A/B 或正式候选。
- 本阶段只证明数据交付、proof/hash/schema、cutoff 和审计特征链路可继续稳定扩展；没有证明任何降低回撤规则。

## 开始与结束反思

- 开始前是否过拟合：否。Stage229 只按 Stage177 剩余覆盖义务和交易所轮转补数据，没有按收益、回撤或 PnL 标签选样。
- 开始前是否值得继续：是。当前目标需要分钟级高质量信号，但在样本地基只有 `192/219` 时写规则仍然过浅。
- 结束后是否过拟合：否。本阶段没有新增交易规则、没有 true engine、没有正式配置变更；ordinary 覆盖和审计特征继续被限制为数据审计字段。
- 结束后是否值得继续：是。`196/219` 仍不足以支撑普世规则判断，下一步 Stage230 应继续同口径扩展 Stage177 delivery，并复跑 Stage179/180/181。

## 后续规划与 TODO

- Stage230 继续小批量扩展 Stage177 predecision lookback delivery，维持交易所轮转和 priority 纪律。
- 每批继续生成并检查资金曲线、precheck、tail removal、readiness、value heatmap。
- 在覆盖显著扩大前，不做规则搜索、不做阈值扫描、不跑 true engine、不触发 A/B。
