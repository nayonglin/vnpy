# Stage198 predecision lookback tick aggregate delivery batch

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 10:11 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage177 predecision lookback 数据地基小批量扩容；刷新 Stage179/180/181 审计链路。
- 是否重要突破：否。本阶段只把已交付样本从 `68` 扩到 `72`，不是策略收益/回撤突破。
- 是否触发A/B：否。没有策略候选、没有 true engine、没有正式配置变更。

## 外部调研与判断

- 参考资料：
  - TqSdk `TqBacktest` 官方文档：https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html
  - TqSdk `TqApi/get_tick_serial` 官方文档：https://doc.shinnytech.com/tqsdk/1.5.0/reference/tqsdk.api.html
  - pandas `DataFrame.rolling` 官方文档：https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html
  - vn.py `BarGenerator` 源码：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py
- 我的判断：
  - TqSdk tick serial 可以继续作为历史 tick 抽取入口，但完整性必须由落盘文件、proof、hash、schema 和窗口 precheck 共同证明，不能只相信一次 14 天请求。
  - pandas rolling 的窗口端点纪律要求继续执行 `bar_end_ts <= decision_ts`，所有决策后分钟 bar 必须先被 Stage180 剔除再进入审计特征。
  - vn.py BarGenerator 的 tick 聚合经验说明价格、成交量、成交额、持仓增量必须一起审计；本阶段保持 Stage178/164 的非负成交量增量聚合口径。
  - Stage198 的 `low_resolution` 只是覆盖义务，不是交易筛选标签；用它写规则会把数据缺口伪装成 alpha，属于过拟合。

## 本次版本改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage198_predecision_lookback_tick_aggregate_delivery_batch.py`
- 新增阶段记录：`research/lines/futures_trend_c9_minrisk_highquality/stages/20260621_1011_stage198_predecision_lookback_tick_aggregate_delivery_batch.md`
- 修改当前线状态：`research/lines/futures_trend_c9_minrisk_highquality/LINE.md`
- 新增参数：
  - `STAGE198_MAX_REQUESTS=4`
  - `STAGE198_TICK_DATA_LENGTH=10000`
  - `STAGE198_MAX_SECONDS_TICK=240`
  - `STAGE198_MIN_POSITIVE_VOLUME_BARS_REQUIRED=60`
  - `target_min_predecision_closed_bars=61`
- 修改参数：无。沿用 Stage178/179/180/181 的 point-in-time、hash/schema、cutoff 和审计特征链路。
- 删除参数：无。
- 新增回测结果：无。本阶段没有运行 true engine，没有生成收益候选。
- 修改回测结果：无。
- 删除回测结果：无。

## Stage198 交付结果

- 决策：`stage198_predecision_lookback_tick_aggregate_delivery_written_refresh_stage179_180_181_no_rule`
- 选择策略：`stage177_remaining_highest_priority_exchange_round_robin_stage198_no_pnl_no_rule`
- 本批选择 `4` 个 request，全部为 `low_resolution` 覆盖义务：
  - `stage177_req_0083_SA009_CZCE_20200720`：raw `190,559`，normalized `3,461`，positive `3,461`，observed closed bars `3,460`
  - `stage177_req_0097_jm2205_DCE_20220214`：raw `125,850`，normalized `1,732`，positive `1,732`，observed closed bars `1,731`
  - `stage177_req_0119_rb2010_SHFE_20200512`：raw `245,691`，normalized `2,063`，positive `2,063`，observed closed bars `2,062`
  - `stage177_req_0063_CF101_CZCE_20200929`：raw `270,574`，normalized `3,461`，positive `3,461`，observed closed bars `3,460`
- 本批合计：
  - `delivery_success_count=4/4`
  - `expected_files_written=12/12`
  - `raw_tick_row_count=832,674`
  - `normalized_row_count=10,717`
  - `positive_volume_row_count=10,717`
  - `window_precheck_pass_count=4/4`
  - `min_observed_predecision_closed_bar_count=1,731`
  - `max_observed_predecision_closed_bar_count=3,460`
  - `right_tail=0`，`bottom_loss=0`，`maxDD=0`，`low_resolution=4`

## Stage179/180/181 刷新结果

- Stage179：
  - `present_triplet_count=72`
  - `proof_hash_schema_identity_ready_count=72`
  - `filtered_request_ready_count=72`
  - `direct_file_request_ready_count=21`
  - `post_decision_bar_count=51`
  - `strategy_feature_usable=0`
- Stage180：
  - `filtered_source_written_count=72`
  - `cutoff_filtered_source_ready_count=72`
  - `filtered_source_row_count=208,493`
  - `filtered_positive_volume_row_count=208,377`
  - `post_decision_removed_count=51`
  - `lineage_pass_count=72`
- Stage181：
  - `feature_audit_row_written_count=72`
  - `feature_ready_cell_count=720/720`
  - `source_cutoff_guard_pass_count=72/72`
  - `lineage_pass_count=72/72`
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

- Stage198 precheck 图：4 个 request 全绿，全部超过 `61` 根决策前闭合 bar 要求。
- Stage180 tail removal 图：累计 `51` 根决策后 bar 被剔除，避免未来函数。
- Stage181 readiness 图：`72 x 10` 个审计单元全绿。
- Stage181 value heatmap：非空；`range_ratio_1m` 上界扩到 `0.007574`，但这只说明低分辨率覆盖继续扩展，不构成可交易条件。
- 关键 PNG 非空校验：Stage198/179/180/181 共 `20` 张 PNG 全部非空。
- 当前 Stage181 特征横截面：
  - `bar_return_1m`：min `-0.0145967935`，max `0.0135135135`，mean `0.0005179275`
  - `range_ratio_1m`：min `0.0000000000`，max `0.0075741637`，mean `0.0007969917`
  - `directional_efficiency_30m`：min `0.0204081633`，max `0.4634146341`，mean `0.1779431795`
  - `realized_volatility_30m`：min `0.0001564239`，max `0.0027795734`，mean `0.0008931106`
  - `true_range_median_30m`：min `0.1600000000`，max `40.0000000000`，mean `7.2095833333`
  - `volume_participation_30m`：min `0.8666666667`，max `1.0000000000`，mean `0.9967592593`
  - `volume_zscore_60m`：min `-0.5900707269`，max `0.5063034363`，mean `0.0526985802`
  - `open_interest_delta_60m`：min `-64,294`，max `47,119`，mean `-3,822.9166666667`
  - `turnover_vwap_gap_30m`：min `-0.0115857746`，max `0.0122075013`，mean `0.0003446478`
  - `closed_bar_count_coverage`：min `1,130`，max `4,670`，mean `2,895.7361111111`

## 结论

- Stage198 把点时化分钟特征地基从 `68` 个样本推进到 `72` 个样本。
- 现在仍距离 Stage177 的 `219` 个 entry decision 很远；样本覆盖显著扩大前，继续禁止分钟规则、true engine、A/B 或正式候选。
- 本阶段只证明数据交付、proof/hash/schema、cutoff 和审计特征链路可继续稳定扩展；没有证明任何降低回撤规则。

## 开始与结束反思

- 开始前是否过拟合：否。Stage198 没有读取 PnL 标签做筛选，也没有调收益参数，只按剩余覆盖义务和交易所轮转补数据。
- 开始前是否值得继续：是。当前目标要求基于分钟级 K 线识别高质量信号，但在样本地基只有 `68/219` 时直接写规则会很浅。
- 结束后是否过拟合：否。本阶段没有新增交易规则、没有 true engine、没有正式配置变更，`low_resolution` 被明确禁止交易化。
- 结束后是否值得继续：是。`72/219` 仍不足以支撑普世规则判断，下一步 Stage199 应继续同口径扩展 Stage177 delivery，并复跑 Stage179/180/181。

## 后续规划与 TODO

- Stage199 继续小批量扩展 Stage177 predecision lookback delivery，优先维持交易所轮转和 priority 纪律。
- 每批继续生成并检查资金曲线、precheck、tail removal、readiness、value heatmap。
- 在覆盖显著扩大前，不做规则搜索、不做阈值扫描、不跑 true engine、不触发 A/B。
