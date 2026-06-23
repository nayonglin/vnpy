# Stage199 predecision lookback tick aggregate delivery batch

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 10:32 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage177 predecision lookback 数据地基小批量扩容；刷新 Stage179/180/181 审计链路。
- 是否重要突破：否。本阶段只把已交付样本从 `72` 扩到 `76`，不是策略收益/回撤突破。
- 是否触发A/B：否。没有策略候选、没有 true engine、没有正式配置变更。

## 外部调研与判断

- 参考资料：
  - TqSdk `TqBacktest` 官方文档：https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html
  - TqSdk `TqApi/get_tick_serial` 官方文档：https://doc.shinnytech.com/tqsdk/1.5.0/reference/tqsdk.api.html
  - pandas `DataFrame.rolling` 官方文档：https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html
  - vn.py `BarGenerator` 源码：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py
- 我的判断：
  - TqSdk 回测/tick serial 继续只作为历史 tick 抽取入口；`timeout` 不自动失败，也绝不能自动视为完整，必须由窗口 precheck 和 proof/hash/schema 共同裁决。
  - pandas rolling 的端点纪律继续要求 `bar_end_ts <= decision_ts`；Stage180 剔除决策后 bar 之前，任何分钟特征都不能被交易化。
  - vn.py BarGenerator 的 tick 聚合经验继续提醒我们同时审计价格、成交量、成交额、持仓变化；单看 close 或收益会把数据质量问题误当信号。
  - Stage199 仍是覆盖义务扩容，`low_resolution`、`timeout`、`positive_volume` 等状态只能作为数据审计字段，不能作为降低回撤规则。

## 本次版本改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage199_predecision_lookback_tick_aggregate_delivery_batch.py`
- 新增阶段记录：`research/lines/futures_trend_c9_minrisk_highquality/stages/20260621_1032_stage199_predecision_lookback_tick_aggregate_delivery_batch.md`
- 修改当前线状态：`research/lines/futures_trend_c9_minrisk_highquality/LINE.md`
- 新增参数：
  - `STAGE199_MAX_REQUESTS=4`
  - `STAGE199_TICK_DATA_LENGTH=10000`
  - `STAGE199_MAX_SECONDS_TICK=240`
  - `STAGE199_MIN_POSITIVE_VOLUME_BARS_REQUIRED=60`
  - `target_min_predecision_closed_bars=61`
- 修改参数：无。沿用 Stage178/179/180/181 的 point-in-time、hash/schema、cutoff 和审计特征链路。
- 删除参数：无。
- 新增回测结果：无。本阶段没有运行 true engine，没有生成收益候选。
- 修改回测结果：无。
- 删除回测结果：无。

## Stage199 交付结果

- 决策：`stage199_predecision_lookback_tick_aggregate_delivery_written_refresh_stage179_180_181_no_rule`
- 选择策略：`stage177_remaining_highest_priority_exchange_round_robin_stage199_no_pnl_no_rule`
- 本批选择 `4` 个 request，全部为 `low_resolution` 覆盖义务：
  - `stage177_req_0073_MA101_CZCE_20201214`：`timeout_after_240s`，raw `372,292`，normalized `3,288`，positive `3,288`，observed closed bars `3,288`
  - `stage177_req_0098_jm2205_DCE_20220330`：`extracted`，raw `233,288`，normalized `3,461`，positive `3,461`，observed closed bars `3,460`
  - `stage177_req_0126_sp2012_SHFE_20200817`：`extracted`，raw `179,942`，normalized `3,461`，positive `3,385`，observed closed bars `3,460`
  - `stage177_req_0080_OI105_CZCE_20201222`：`extracted`，raw `333,467`，normalized `3,461`，positive `3,461`，observed closed bars `3,460`
- 本批合计：
  - `delivery_success_count=4/4`
  - `expected_files_written=12/12`
  - `raw_tick_row_count=1,118,989`
  - `normalized_row_count=13,671`
  - `positive_volume_row_count=13,595`
  - `window_precheck_pass_count=4/4`
  - `min_observed_predecision_closed_bar_count=3,288`
  - `max_observed_predecision_closed_bar_count=3,460`
  - `right_tail=0`，`bottom_loss=0`，`maxDD=0`，`low_resolution=4`

## Stage179/180/181 刷新结果

- Stage179：
  - `present_triplet_count=76`
  - `proof_hash_schema_identity_ready_count=76`
  - `filtered_request_ready_count=76`
  - `direct_file_request_ready_count=22`
  - `post_decision_bar_count=54`
  - `strategy_feature_usable=0`
- Stage180：
  - `filtered_source_written_count=76`
  - `cutoff_filtered_source_ready_count=76`
  - `filtered_source_row_count=222,161`
  - `filtered_positive_volume_row_count=221,969`
  - `post_decision_removed_count=54`
  - `lineage_pass_count=76`
- Stage181：
  - `feature_audit_row_written_count=76`
  - `feature_ready_cell_count=760/760`
  - `source_cutoff_guard_pass_count=76/76`
  - `lineage_pass_count=76/76`
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

- Stage199 precheck 图：4 个 request 全绿，全部超过 `61` 根决策前闭合 bar 要求。
- Stage180 tail removal 图：累计 `54` 根决策后 bar 被剔除，避免未来函数。
- Stage181 readiness 图：`76 x 10` 个审计单元全绿。
- Stage181 value heatmap：非空；`directional_efficiency_30m` 下界扩到 `0.0`，说明本批增加了更低效率横截面，但仍只作为审计特征，不构成交易条件。
- 关键 PNG 非空校验：Stage199/179/180/181 共 `20` 张 PNG 全部非空。
- 当前 Stage181 特征横截面：
  - `bar_return_1m`：min `-0.0145967935`，max `0.0135135135`，mean `0.0004715282`
  - `range_ratio_1m`：min `0.0000000000`，max `0.0075741637`，mean `0.0008165107`
  - `directional_efficiency_30m`：min `0.0000000000`，max `0.4634146341`，mean `0.1741120860`
  - `realized_volatility_30m`：min `0.0001564239`，max `0.0027795734`，mean `0.0008946845`
  - `true_range_median_30m`：min `0.1600000000`，max `40.0000000000`，mean `7.0505263158`
  - `volume_participation_30m`：min `0.8666666667`，max `1.0000000000`，mean `0.9969298246`
  - `volume_zscore_60m`：min `-0.5900707269`，max `0.5063034363`，mean `0.0573745887`
  - `open_interest_delta_60m`：min `-64,294`，max `47,119`，mean `-3,280.7368421053`
  - `turnover_vwap_gap_30m`：min `-0.0115857746`，max `0.0122075013`，mean `0.0003322245`
  - `closed_bar_count_coverage`：min `1,130`，max `4,670`，mean `2,923.1710526316`

## 结论

- Stage199 把点时化分钟特征地基从 `72` 个样本推进到 `76` 个样本。
- 现在仍距离 Stage177 的 `219` 个 entry decision 很远；样本覆盖显著扩大前，继续禁止分钟规则、true engine、A/B 或正式候选。
- 本阶段只证明数据交付、proof/hash/schema、cutoff 和审计特征链路可继续稳定扩展；没有证明任何降低回撤规则。

## 开始与结束反思

- 开始前是否过拟合：否。Stage199 只按剩余覆盖义务和交易所轮转补数据，没有按收益、回撤或 PnL 标签选样。
- 开始前是否值得继续：是。当前目标需要分钟级高质量信号，但在样本地基只有 `72/219` 时写规则会过浅。
- 结束后是否过拟合：否。本阶段没有新增交易规则、没有 true engine、没有正式配置变更；`timeout` 与 `low_resolution` 均被限制为数据审计字段。
- 结束后是否值得继续：是。`76/219` 仍不足以支撑普世规则判断，下一步 Stage200 应继续同口径扩展 Stage177 delivery，并复跑 Stage179/180/181。

## 后续规划与 TODO

- Stage200 继续小批量扩展 Stage177 predecision lookback delivery，维持交易所轮转和 priority 纪律。
- 每批继续生成并检查资金曲线、precheck、tail removal、readiness、value heatmap。
- 在覆盖显著扩大前，不做规则搜索、不做阈值扫描、不跑 true engine、不触发 A/B。
