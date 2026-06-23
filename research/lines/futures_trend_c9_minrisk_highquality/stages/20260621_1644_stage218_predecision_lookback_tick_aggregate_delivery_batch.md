# Stage218 predecision lookback tick aggregate delivery batch

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 16:44 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage177 predecision lookback 数据地基小批量扩容；刷新 Stage179/180/181 审计链路。
- 是否重要突破：否。本阶段只把已交付样本从 `148` 扩到 `152`，不是策略收益/回撤突破。
- 是否触发A/B：否。没有策略候选、没有 true engine、没有正式配置变更。

## 外部调研与判断

- 参考资料：
  - TqSdk `TqBacktest` 官方文档：https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html
  - pandas `DataFrame.rolling` 官方文档：https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html
  - vn.py `BarGenerator` 源码：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py
- 我的判断：
  - TqSdk/tick 数据继续只作为历史数据入口；`extracted`、拉取耗时和交易所差异只能描述数据工程边界，不能被解释为市场质量或交易信号。
  - pandas rolling 与 cutoff 的核心纪律仍是 `bar_end_ts <= decision_ts`；Stage181 的全部审计特征必须来自 Stage180 cutoff-filtered source。
  - vn.py BarGenerator 的经验继续提醒：分钟地基不能只看 close 或收益，要同时审计 OHLCV、成交额和持仓变化，否则容易把数据缺口误读成策略结构。
  - Stage218 仍是覆盖义务扩容；本批 ordinary 覆盖只说明样本地基扩大，不允许直接交易化。

## 本次版本改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage218_predecision_lookback_tick_aggregate_delivery_batch.py`
- 新增阶段记录：`research/lines/futures_trend_c9_minrisk_highquality/stages/20260621_1644_stage218_predecision_lookback_tick_aggregate_delivery_batch.md`
- 修改当前线状态：`research/lines/futures_trend_c9_minrisk_highquality/LINE.md`
- 新增参数：
  - `STAGE218_MAX_REQUESTS=4`
  - `STAGE218_TICK_DATA_LENGTH=10000`
  - `STAGE218_MAX_SECONDS_TICK=240`
  - `STAGE218_MIN_POSITIVE_VOLUME_BARS=60`
  - `target_min_predecision_closed_bars=61`
- 修改参数：无。沿用 Stage178/179/180/181 的 point-in-time、hash/schema、cutoff 和审计特征链路。
- 删除参数：无。
- 新增回测结果：无。本阶段没有运行 true engine，没有生成收益候选。
- 修改回测结果：无。
- 删除回测结果：无。

## Stage218 交付结果

- 决策：`stage218_predecision_lookback_tick_aggregate_delivery_written_refresh_stage179_180_181_no_rule`
- 选择策略：`stage177_remaining_highest_priority_exchange_round_robin_stage218_no_pnl_no_rule`
- 本批选择 `4` 个 request，全部为 `ordinary` 覆盖义务：
  - `stage177_req_0146_FG109_CZCE_20210625`：`extracted`，raw `344,305`，normalized `2,995`，positive `2,995`，observed closed bars `2,994`
  - `stage177_req_0178_lh2401_DCE_20231024`：`extracted`，raw `145,810`，normalized `2,261`，positive `2,261`，observed closed bars `2,260`
  - `stage177_req_0197_hc2010_SHFE_20200622`：`extracted`，raw `349,288`，normalized `3,461`，positive `3,461`，observed closed bars `3,460`
  - `stage177_req_0141_CF109_CZCE_20210705`：`extracted`，raw `313,481`，normalized `3,461`，positive `3,461`，observed closed bars `3,460`
- 本批合计：
  - `delivery_success_count=4/4`
  - `expected_files_written=12/12`
  - `raw_tick_row_count=1,152,884`
  - `normalized_row_count=12,178`
  - `positive_volume_row_count=12,178`
  - `window_precheck_pass_count=4/4`
  - `min_observed_predecision_closed_bar_count=2,260`
  - `max_observed_predecision_closed_bar_count=3,460`
  - `right_tail=0`，`bottom_loss=0`，`maxDD=0`，`low_resolution=0`
- 重要边界：本批 `4` 个 request 均为 `extracted`，且均已抽取到远超 `61` 根决策前闭合 bar 并通过后续 proof/hash/schema/cutoff 验证；这只说明本批数据交付顺畅，不构成交易质量标签。

## Stage179/180/181 刷新结果

- Stage179：
  - `present_triplet_count=152`
  - `proof_hash_schema_identity_ready_count=152`
  - `filtered_request_ready_count=152`
  - `direct_file_request_ready_count=48`
  - `post_decision_bar_count=104`
  - `strategy_feature_usable=0`
- Stage180：
  - `filtered_source_written_count=152`
  - `cutoff_filtered_source_ready_count=152`
  - `filtered_source_row_count=431,646`
  - `filtered_positive_volume_row_count=431,266`
  - `post_decision_removed_count=104`
  - `lineage_pass_count=152`
- Stage181：
  - `feature_audit_row_written_count=152`
  - `feature_ready_cell_count=1520/1520`
  - `source_cutoff_guard_pass_count=152/152`
  - `lineage_pass_count=152/152`
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

- Stage218 precheck 图：4 个 request 全绿，全部超过 `61` 根决策前闭合 bar 要求。
- Stage180 tail removal 图：累计 `104` 根决策后 bar 被剔除，避免未来函数。
- Stage181 readiness 图：`152 x 10` 个审计单元全绿。
- Stage181 value heatmap：非空且有横截面差异；这些差异继续只作为审计信息，不得直接交易化。
- 关键 PNG 非空校验：Stage218/179/180/181 共 `20` 张 PNG 全部非空。
- 当前 Stage181 特征横截面：
  - `bar_return_1m`：min `-0.0147459165`，max `0.0193679918`，mean `0.0003447529`
  - `range_ratio_1m`：min `0.0000000000`，max `0.0075741637`，mean `0.0008190207`
  - `directional_efficiency_30m`：min `0.0000000000`，max `0.7183098592`，mean `0.1713058178`
  - `realized_volatility_30m`：min `0.0001564239`，max `0.0041081855`，mean `0.0009176274`
  - `true_range_median_30m`：min `0.0600000000`，max `70.0000000000`，mean `7.7246052632`
  - `volume_participation_30m`：min `0.8666666667`，max `1.0000000000`，mean `0.9958333333`
  - `volume_zscore_60m`：min `-0.5900707269`，max `0.5063034363`，mean `0.0221395854`
  - `open_interest_delta_60m`：min `-71,441`，max `47,119`，mean `-3,305.2039473684`
  - `turnover_vwap_gap_30m`：min `-0.0138560842`，max `0.0165267200`，mean `0.0001166203`
  - `closed_bar_count_coverage`：min `904`，max `4,758`，mean `2,839.7763157895`

## 结论

- Stage218 把点时化分钟特征地基从 `148` 个样本推进到 `152` 个样本，当前覆盖为 `152/219`，剩余 `67` 个 entry decision。
- 现在仍距离完整覆盖很远；样本覆盖显著扩大前，继续禁止分钟规则、true engine、A/B 或正式候选。
- 本阶段只证明数据交付、proof/hash/schema、cutoff 和审计特征链路可继续稳定扩展；没有证明任何降低回撤规则。
- 本批 `4` 个 request 全部 `extracted` 并通过审计；顺畅交付不是交易质量标签。

## 开始与结束反思

- 开始前是否过拟合：否。Stage218 只按 Stage177 剩余覆盖义务和交易所轮转补数据，没有按收益、回撤或 PnL 标签选样。
- 开始前是否值得继续：是。当前目标需要分钟级高质量信号，但在样本地基只有 `148/219` 时写规则会过浅。
- 结束后是否过拟合：否。本阶段没有新增交易规则、没有 true engine、没有正式配置变更；ordinary 覆盖、extracted 状态和审计特征继续被限制为数据审计字段。
- 结束后是否值得继续：是。`152/219` 仍不足以支撑普世规则判断，下一步 Stage219 应继续同口径扩展 Stage177 delivery，并复跑 Stage179/180/181。

## 后续规划与 TODO

- Stage219 继续小批量扩展 Stage177 predecision lookback delivery，维持交易所轮转和 priority 纪律。
- 每批继续生成并检查资金曲线、precheck、tail removal、readiness、value heatmap。
- 在覆盖显著扩大前，不做规则搜索、不做阈值扫描、不跑 true engine、不触发 A/B。
