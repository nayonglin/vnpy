# Stage220 predecision lookback tick aggregate delivery batch

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 17:23 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage177 predecision lookback 数据地基小批量扩容；刷新 Stage179/180/181 审计链路。
- 是否重要突破：否。本阶段只把已交付样本从 `156` 扩到 `160`，不是策略收益/回撤突破。
- 是否触发A/B：否。没有策略候选、没有 true engine、没有正式配置变更。

## 外部调研与判断

- 参考资料：
  - TqSdk `TqBacktest` 官方文档：https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html
  - pandas `DataFrame.rolling` 官方文档：https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html
  - vn.py `BarGenerator` 源码：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py
- 我的判断：
  - TqSdk/tick 数据继续只作为历史数据入口；`extracted`、`timeout_after_240s`、拉取耗时和交易所差异只能描述数据工程边界，不能被解释为市场质量或交易信号。
  - pandas rolling 与 cutoff 的核心纪律仍是 `bar_end_ts <= decision_ts`；Stage181 的全部审计特征必须来自 Stage180 cutoff-filtered source。
  - vn.py BarGenerator 的经验继续提醒：分钟地基不能只看 close 或收益，要同时审计 OHLCV、成交额和持仓变化，否则容易把数据缺口误读成策略结构。
  - Stage220 仍是覆盖义务扩容；本批 ordinary 覆盖只说明样本地基扩大，不允许直接交易化。

## 本次版本改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage220_predecision_lookback_tick_aggregate_delivery_batch.py`
- 新增阶段记录：`research/lines/futures_trend_c9_minrisk_highquality/stages/20260621_1723_stage220_predecision_lookback_tick_aggregate_delivery_batch.md`
- 修改当前线状态：`research/lines/futures_trend_c9_minrisk_highquality/LINE.md`
- 新增参数：
  - `STAGE220_MAX_REQUESTS=4`
  - `STAGE220_TICK_DATA_LENGTH=10000`
  - `STAGE220_MAX_SECONDS_TICK=240`
  - `STAGE220_MIN_POSITIVE_VOLUME_BARS=60`
  - `target_min_predecision_closed_bars=61`
- 修改参数：无。沿用 Stage178/179/180/181 的 point-in-time、hash/schema、cutoff 和审计特征链路。
- 删除参数：无。
- 新增回测结果：无。本阶段没有运行 true engine，没有生成收益候选。
- 修改回测结果：无。
- 删除回测结果：无。

## Stage220 交付结果

- 决策：`stage220_predecision_lookback_tick_aggregate_delivery_written_refresh_stage179_180_181_no_rule`
- 选择策略：`stage177_remaining_highest_priority_exchange_round_robin_stage220_no_pnl_no_rule`
- 本批选择 `4` 个 request，全部为 `ordinary` 覆盖义务：
  - `stage177_req_0154_MA201_CZCE_20210906`：`timeout_after_240s`，raw `378,405`，normalized `3,227`，positive `3,227`，observed closed bars `3,227`
  - `stage177_req_0180_lh2409_DCE_20240408`：`extracted`，raw `96,366`，normalized `1,809`，positive `1,809`，observed closed bars `1,808`
  - `stage177_req_0198_hc2010_SHFE_20200803`：`extracted`，raw `312,609`，normalized `3,461`，positive `3,461`，observed closed bars `3,460`
  - `stage177_req_0162_SA201_CZCE_20210908`：`timeout_after_240s`，raw `373,188`，normalized `3,246`，positive `3,246`，observed closed bars `3,246`
- 本批合计：
  - `delivery_success_count=4/4`
  - `expected_files_written=12/12`
  - `raw_tick_row_count=1,160,568`
  - `normalized_row_count=11,743`
  - `positive_volume_row_count=11,743`
  - `window_precheck_pass_count=4/4`
  - `min_observed_predecision_closed_bar_count=1,808`
  - `max_observed_predecision_closed_bar_count=3,460`
  - `right_tail=0`，`bottom_loss=0`，`maxDD=0`，`low_resolution=0`
- 重要边界：`MA201` 2021-09-06 与 `SA201` 2021-09-08 为 `timeout_after_240s`，但均已抽取到远超 `61` 根决策前闭合 bar 并通过后续 proof/hash/schema/cutoff 验证；这不能被解读为完整 14 天全量保证，也不是交易质量标签。

## Stage179/180/181 刷新结果

- Stage179：
  - `present_triplet_count=160`
  - `proof_hash_schema_identity_ready_count=160`
  - `filtered_request_ready_count=160`
  - `direct_file_request_ready_count=50`
  - `post_decision_bar_count=110`
  - `strategy_feature_usable=0`
- Stage180：
  - `filtered_source_written_count=160`
  - `cutoff_filtered_source_ready_count=160`
  - `filtered_source_row_count=455,215`
  - `filtered_positive_volume_row_count=454,833`
  - `post_decision_removed_count=110`
  - `lineage_pass_count=160`
- Stage181：
  - `feature_audit_row_written_count=160`
  - `feature_ready_cell_count=1600/1600`
  - `source_cutoff_guard_pass_count=160/160`
  - `lineage_pass_count=160/160`
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

- Stage220 precheck 图：4 个 request 全绿，全部超过 `61` 根决策前闭合 bar 要求；本批最低 `lh2409` 也有 `1,808` 根。
- Stage180 tail removal 图：累计 `110` 根决策后 bar 被剔除，避免未来函数。
- Stage181 readiness 图：`160 x 10` 个审计单元全绿。
- Stage181 value heatmap：非空且有横截面差异；这些差异继续只作为审计信息，不得直接交易化。
- 关键 PNG 非空校验：Stage220/179/180/181 共 `20` 张 PNG 全部非空。
- 当前 Stage181 特征横截面：
  - `bar_return_1m`：min `-0.0147459165`，max `0.0193679918`，mean `0.0003191386`
  - `range_ratio_1m`：min `0.0000000000`，max `0.0075741637`，mean `0.0008185993`
  - `directional_efficiency_30m`：min `0.0000000000`，max `0.7183098592`，mean `0.1727620094`
  - `realized_volatility_30m`：min `0.0001564239`，max `0.0041081855`，mean `0.0009096360`
  - `true_range_median_30m`：min `0.0600000000`，max `70.0000000000`，mean `7.7258750000`
  - `volume_participation_30m`：min `0.8666666667`，max `1.0000000000`，mean `0.9960416667`
  - `volume_zscore_60m`：min `-0.5900707269`，max `0.6477878905`，mean `0.0274112117`
  - `open_interest_delta_60m`：min `-71,441`，max `47,119`，mean `-3,038.6875000000`
  - `turnover_vwap_gap_30m`：min `-0.0138560842`，max `0.0165267200`，mean `0.0001143817`
  - `closed_bar_count_coverage`：min `904`，max `4,758`，mean `2,845.0937500000`

## 结论

- Stage220 把点时化分钟特征地基从 `156` 个样本推进到 `160` 个样本，当前覆盖为 `160/219`，剩余 `59` 个 entry decision。
- 现在仍距离完整覆盖有差距；样本覆盖显著扩大前，继续禁止分钟规则、true engine、A/B 或正式候选。
- 本阶段只证明数据交付、proof/hash/schema、cutoff 和审计特征链路可继续稳定扩展；没有证明任何降低回撤规则。
- 本批 `2` 个 request 触达 timeout 边界但均通过审计；timeout 只描述数据抓取边界，不是交易质量标签。

## 开始与结束反思

- 开始前是否过拟合：否。Stage220 只按 Stage177 剩余覆盖义务和交易所轮转补数据，没有按收益、回撤或 PnL 标签选样。
- 开始前是否值得继续：是。当前目标需要分钟级高质量信号，但在样本地基只有 `156/219` 时写规则仍然过浅。
- 结束后是否过拟合：否。本阶段没有新增交易规则、没有 true engine、没有正式配置变更；ordinary 覆盖、timeout 状态和审计特征继续被限制为数据审计字段。
- 结束后是否值得继续：是。`160/219` 仍不足以支撑普世规则判断，下一步 Stage221 应继续同口径扩展 Stage177 delivery，并复跑 Stage179/180/181。

## 后续规划与 TODO

- Stage221 继续小批量扩展 Stage177 predecision lookback delivery，维持交易所轮转和 priority 纪律。
- 每批继续生成并检查资金曲线、precheck、tail removal、readiness、value heatmap。
- 在覆盖显著扩大前，不做规则搜索、不做阈值扫描、不跑 true engine、不触发 A/B。
