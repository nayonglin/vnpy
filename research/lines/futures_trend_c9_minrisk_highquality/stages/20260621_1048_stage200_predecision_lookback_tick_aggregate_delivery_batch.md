# Stage200 predecision lookback tick aggregate delivery batch

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 10:48 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage177 predecision lookback 数据地基小批量扩容；刷新 Stage179/180/181 审计链路。
- 是否重要突破：否。本阶段只把已交付样本从 `76` 扩到 `80`，不是策略收益/回撤突破。
- 是否触发A/B：否。没有策略候选、没有 true engine、没有正式配置变更。

## 外部调研与判断

- 参考资料：
  - TqSdk `TqBacktest` 官方文档：https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html
  - TqSdk `TqApi/get_tick_serial` 官方文档：https://doc.shinnytech.com/tqsdk/1.5.0/reference/tqsdk.api.html
  - pandas `DataFrame.rolling` 官方文档：https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html
  - vn.py `BarGenerator` 源码：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py
- 我的判断：
  - TqSdk tick/回测推进入口可继续用于历史分钟地基扩容，但完整性必须由本地 proof/hash/schema/window precheck 证明。
  - pandas rolling 的窗口端点纪律继续要求 `bar_end_ts <= decision_ts`；Stage180 剔除决策后 bar 之前，任何分钟特征都不能用于策略规则。
  - vn.py BarGenerator 的经验继续要求成交量、成交额、持仓变化与价格一起审计，避免只看 close 造成伪信号。
  - Stage200 仍是覆盖义务扩容，`low_resolution`、正量 bar 数、closed bar 覆盖量均只能作为数据质量字段，不能作为交易筛选条件。

## 本次版本改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage200_predecision_lookback_tick_aggregate_delivery_batch.py`
- 新增阶段记录：`research/lines/futures_trend_c9_minrisk_highquality/stages/20260621_1048_stage200_predecision_lookback_tick_aggregate_delivery_batch.md`
- 修改当前线状态：`research/lines/futures_trend_c9_minrisk_highquality/LINE.md`
- 新增参数：
  - `STAGE200_MAX_REQUESTS=4`
  - `STAGE200_TICK_DATA_LENGTH=10000`
  - `STAGE200_MAX_SECONDS_TICK=240`
  - `STAGE200_MIN_POSITIVE_VOLUME_BARS_REQUIRED=60`
  - `target_min_predecision_closed_bars=61`
- 修改参数：无。沿用 Stage178/179/180/181 的 point-in-time、hash/schema、cutoff 和审计特征链路。
- 删除参数：无。
- 新增回测结果：无。本阶段没有运行 true engine，没有生成收益候选。
- 修改回测结果：无。
- 删除回测结果：无。

## Stage200 交付结果

- 决策：`stage200_predecision_lookback_tick_aggregate_delivery_written_refresh_stage179_180_181_no_rule`
- 选择策略：`stage177_remaining_highest_priority_exchange_round_robin_stage200_no_pnl_no_rule`
- 本批选择 `4` 个 request，全部为 `low_resolution` 覆盖义务：
  - `stage177_req_0064_CF105_CZCE_20210210`：`extracted`，raw `295,729`，normalized `3,461`，positive `3,461`，observed closed bars `3,460`
  - `stage177_req_0099_jm2209_DCE_20220525`：`extracted`，raw `271,239`，normalized `3,461`，positive `3,461`，observed closed bars `3,460`
  - `stage177_req_0121_ru2101_SHFE_20201015`：`extracted`，raw `147,930`，normalized `1,386`，positive `1,386`，observed closed bars `1,385`
  - `stage177_req_0084_SA105_CZCE_20210222`：`extracted`，raw `154,013`，normalized `1,611`，positive `1,611`，observed closed bars `1,610`
- 本批合计：
  - `delivery_success_count=4/4`
  - `expected_files_written=12/12`
  - `raw_tick_row_count=868,911`
  - `normalized_row_count=9,919`
  - `positive_volume_row_count=9,919`
  - `window_precheck_pass_count=4/4`
  - `min_observed_predecision_closed_bar_count=1,385`
  - `max_observed_predecision_closed_bar_count=3,460`
  - `right_tail=0`，`bottom_loss=0`，`maxDD=0`，`low_resolution=4`

## Stage179/180/181 刷新结果

- Stage179：
  - `present_triplet_count=80`
  - `proof_hash_schema_identity_ready_count=80`
  - `filtered_request_ready_count=80`
  - `direct_file_request_ready_count=22`
  - `post_decision_bar_count=58`
  - `strategy_feature_usable=0`
- Stage180：
  - `filtered_source_written_count=80`
  - `cutoff_filtered_source_ready_count=80`
  - `filtered_source_row_count=232,076`
  - `filtered_positive_volume_row_count=231,884`
  - `post_decision_removed_count=58`
  - `lineage_pass_count=80`
- Stage181：
  - `feature_audit_row_written_count=80`
  - `feature_ready_cell_count=800/800`
  - `source_cutoff_guard_pass_count=80/80`
  - `lineage_pass_count=80/80`
  - `formal_feature_table_row_written_count=0`
  - `strategy_feature_usable=0`

## 资金曲线与正式路径指标

本阶段没有修改正式路径，资金曲线指标保持不变，只用于确认数据地基扩容没有误触策略执行：

- 期末权益：`39,176,437.60`
- 总收益：`26,017.63%`
- 最大回撤：`-45.08%`
- Sharpe：`1.633`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.09%`
- Broker10 最大保证金/权益：`111.74%`

## 视觉与特征审计

- Stage200 precheck 图：4 个 request 全绿，全部超过 `61` 根决策前闭合 bar 要求。
- Stage180 tail removal 图：累计 `58` 根决策后 bar 被剔除，避免未来函数。
- Stage181 readiness 图：`80 x 10` 个审计单元全绿。
- Stage181 value heatmap：非空；`closed_bar_count_coverage` 均值回落到 `2,900.95`，说明本批增加了较短但仍足够的入场前覆盖窗口。
- 关键 PNG 非空校验：Stage200/179/180/181 共 `20` 张 PNG 全部非空。
- 当前 Stage181 特征横截面：
  - `bar_return_1m`：min `-0.0145967935`，max `0.0135135135`，mean `0.0004284178`
  - `range_ratio_1m`：min `0.0000000000`，max `0.0075741637`，mean `0.0008323976`
  - `directional_efficiency_30m`：min `0.0000000000`，max `0.4634146341`，mean `0.1754966516`
  - `realized_volatility_30m`：min `0.0001564239`，max `0.0027795734`，mean `0.0008957685`
  - `true_range_median_30m`：min `0.1600000000`，max `40.0000000000`，mean `7.0855000000`
  - `volume_participation_30m`：min `0.8666666667`，max `1.0000000000`，mean `0.9970833333`
  - `volume_zscore_60m`：min `-0.5900707269`，max `0.5063034363`，mean `0.0532186510`
  - `open_interest_delta_60m`：min `-64,294`，max `47,119`，mean `-3,217.45`
  - `turnover_vwap_gap_30m`：min `-0.0115857746`，max `0.0122075013`，mean `0.0003679861`
  - `closed_bar_count_coverage`：min `1,130`，max `4,670`，mean `2,900.95`

## 结论

- Stage200 把点时化分钟特征地基从 `76` 个样本推进到 `80` 个样本。
- 现在仍距离 Stage177 的 `219` 个 entry decision 很远；样本覆盖显著扩大前，继续禁止分钟规则、true engine、A/B 或正式候选。
- 本阶段只证明数据交付、proof/hash/schema、cutoff 和审计特征链路可继续稳定扩展；没有证明任何降低回撤规则。

## 开始与结束反思

- 开始前是否过拟合：否。Stage200 只按剩余覆盖义务和交易所轮转补数据，没有按收益、回撤或 PnL 标签选样。
- 开始前是否值得继续：是。当前目标需要分钟级高质量信号，但在样本地基只有 `76/219` 时写规则会过浅。
- 结束后是否过拟合：否。本阶段没有新增交易规则、没有 true engine、没有正式配置变更；低分辨率覆盖继续被限制为数据审计字段。
- 结束后是否值得继续：是。`80/219` 仍不足以支撑普世规则判断，下一步 Stage201 应继续同口径扩展 Stage177 delivery，并复跑 Stage179/180/181。

## 后续规划与 TODO

- Stage201 继续小批量扩展 Stage177 predecision lookback delivery，维持交易所轮转和 priority 纪律。
- 每批继续生成并检查资金曲线、precheck、tail removal、readiness、value heatmap。
- 在覆盖显著扩大前，不做规则搜索、不做阈值扫描、不跑 true engine、不触发 A/B。
