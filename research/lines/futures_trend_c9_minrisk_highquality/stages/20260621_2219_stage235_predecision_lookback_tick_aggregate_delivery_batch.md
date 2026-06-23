# Stage235 predecision lookback tick aggregate delivery batch

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 22:19 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage177 predecision lookback 数据地基受控单请求扩容；刷新 Stage179/180/181 审计链路。
- 是否重要突破：否。本阶段只把已验证样本从 `210` 扩到 `212`，不是策略收益/回撤突破。
- 是否触发A/B：否。没有策略候选、没有 true engine、没有正式配置变更。

## 外部调研与判断

- 参考资料：
  - TqSdk `tqsdk.objs` 官方文档：https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.objs.html
  - pandas `DataFrame.rolling` 官方文档：https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html
  - vn.py `BarGenerator` 源码：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py
- 我的判断：
  - TqSdk tick/kline 字段继续只作为历史数据入口和审计字段；`timeout_after_180s` 只能描述数据接口边界，不能被解释为市场质量或交易信号。
  - pandas rolling 与 cutoff 的核心纪律仍是 `bar_end_ts <= decision_ts`；Stage181 的全部审计特征必须来自 Stage180 cutoff-filtered source。
  - vn.py BarGenerator 的经验继续提醒：分钟地基不能只看 close 或最终收益，要同时审计 OHLCV、成交额和持仓变化，否则容易把数据缺口误读成策略结构。
  - Stage235 仍是覆盖义务扩容；本批 ordinary 覆盖只说明样本地基扩大，不允许直接交易化。

## 本次版本改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage235_predecision_lookback_tick_aggregate_delivery_batch.py`
- 新增阶段记录：`research/lines/futures_trend_c9_minrisk_highquality/stages/20260621_2219_stage235_predecision_lookback_tick_aggregate_delivery_batch.md`
- 修改当前线状态：`research/lines/futures_trend_c9_minrisk_highquality/LINE.md`
- 新增参数：
  - 默认 `STAGE235_MAX_REQUESTS=1`
  - 默认 `STAGE235_MAX_SECONDS_TICK=180`
  - `STAGE235_TICK_DATA_LENGTH=10000`
  - `STAGE235_MIN_POSITIVE_VOLUME_BARS=60`
  - `target_min_predecision_closed_bars=61`
- 修改参数：无。沿用 Stage178/179/180/181 的 point-in-time、hash/schema、cutoff 和审计特征链路。
- 删除参数：无。
- 新增回测结果：无。本阶段没有运行 true engine，没有生成收益候选。
- 修改回测结果：无。
- 删除回测结果：无。
- 运行状态备注：验证过程中曾短暂观察到同名 Stage235 artifacts 的 `SA309 target_exists` 状态；记录关闭前当前持久化 artifacts 已变为 `CF405` clean delivery，且 Stage179/180/181 已全部重跑到 `212/219`。本记录以当前持久化文件为权威。

## Stage235 交付结果

- Stage235 持久化决策：`stage235_predecision_lookback_tick_aggregate_delivery_written_refresh_stage179_180_181_no_rule`
- 选择策略：`stage177_remaining_highest_priority_exchange_round_robin_stage235_no_pnl_no_rule`
- 本批当前持久化选择 `1` 个 request，属于 `ordinary` 覆盖义务：
  - `stage177_req_0144_CF405_CZCE_20240119`：`timeout_after_180s`，raw `203,937`，normalized `2,111`，positive `2,094`，observed closed bars `2,111`
- 本批合计：
  - `delivery_success_count=1/1`
  - `expected_files_written=3/3`
  - `raw_tick_row_count=203,937`
  - `normalized_row_count=2,111`
  - `positive_volume_row_count=2,094`
  - `window_precheck_pass_count=1/1`
  - `min_observed_predecision_closed_bar_count=2,111`
  - `max_observed_predecision_closed_bar_count=2,111`
  - `right_tail=0`，`bottom_loss=0`，`maxDD=0`，`low_resolution=0`
- 重要边界：
  - `CF405` 的 tick 拉取状态为 `timeout_after_180s`，但已抽取到 `2,111` 根决策前闭合 bar，远超 `60/61` 门槛，并通过后续 proof/hash/schema/cutoff 验证；这只能作为数据接口状态，不是交易过滤条件，也不代表完整 14 天全量保证。
  - 本阶段没有写 formal feature table、没有策略规则、没有 true engine、没有 A/B、没有正式配置变更、没有 CTP、没有 order API。

## Stage179/180/181 刷新结果

- Stage179：
  - `present_triplet_count=212`
  - `proof_hash_schema_identity_ready_count=212`
  - `filtered_request_ready_count=212`
  - `direct_file_request_ready_count=71`
  - `post_decision_bar_count=141`
  - `strategy_feature_usable=0`
- Stage180：
  - `filtered_source_written_count=212`
  - `cutoff_filtered_source_ready_count=212`
  - `filtered_source_row_count=588,161`
  - `filtered_positive_volume_row_count=587,656`
  - `post_decision_removed_count=141`
  - `lineage_pass_count=212`
- Stage181：
  - `feature_audit_row_written_count=212`
  - `feature_ready_cell_count=2120/2120`
  - `source_cutoff_guard_pass_count=212/212`
  - `lineage_pass_count=212/212`
  - `formal_feature_table_row_written_count=0`
  - `strategy_feature_usable=0`

## 资金曲线与正式路径指标

本阶段按用户要求不再重复确认正式版归属；资金曲线指标保持当前研究线既有口径，只用于确认数据地基扩容没有误触策略执行：

- 期末权益：`39,176,437.60`
- 总收益：`26,017.63%`
- 最大回撤：`-45.08%`
- Sharpe：`1.633`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.09%`
- Broker10 最大保证金/权益：`111.74%`

## 视觉与特征审计

- Stage235 official path 图：权益、回撤、broker10 保证金路径未因本阶段改变；底部显示 selected `1`、delivered `1`、precheck pass `1`、files `3`。
- Stage235 precheck 图：单行全绿，`2,111` 根决策前闭合 bar，远超 `61` 根要求。
- Stage180 tail removal 图：累计 `141` 根决策后 bar 被剔除，避免未来函数。
- Stage181 readiness 图：`212 x 10` 个审计单元全绿。
- Stage181 value heatmap：非空且有横截面差异；新增样本未破坏 readiness，继续只作为审计现象，不得直接交易化。
- 关键 PNG 非空校验：Stage235/180/181 共 `15` 张 PNG 全部非空。

## 结论

- Stage235 当前持久化 artifacts 为 CF405 clean delivery，并把点时化分钟特征地基从 `210` 个样本推进到 `212` 个样本，当前覆盖为 `212/219`，剩余 `7` 个 entry decision。
- 现在仍距离完整覆盖有差距；样本全覆盖和 formal feature gate 设计完成前，继续禁止分钟规则、true engine、A/B 或正式候选。
- 本阶段只证明 CF405 triplet 能通过 proof/hash/schema、cutoff 和审计特征链路；没有证明任何降低回撤规则。

## 开始与结束反思

- 开始前是否过拟合：否。Stage235 只按 Stage177 剩余覆盖义务和交易所轮转补数据，没有按收益、回撤或 PnL 标签选样。
- 开始前是否值得继续：是。当前目标需要分钟级高质量信号，但在样本地基只有 `210/219` 时写规则仍然过浅。
- 结束后是否过拟合：否。本阶段没有新增交易规则、没有 true engine、没有正式配置变更；ordinary 覆盖和审计特征继续被限制为数据审计字段。
- 结束后是否值得继续：是。`212/219` 仍不足以支撑普世规则判断，下一步 Stage236 应继续同口径扩展 Stage177 delivery，并复跑 Stage179/180/181。

## 后续规划与 TODO

- Stage236 继续受控小批量扩展 Stage177 predecision lookback delivery，维持交易所轮转和 priority 纪律。
- 如果后续 request 出现 `target_exists`，优先记录为既有 triplet 复验，不覆盖文件；只有明确需要修复半成品时才清理并重跑。
- 每批继续生成并检查资金曲线、precheck、tail removal、readiness、value heatmap。
- 在样本全覆盖和 formal feature gate 设计完成前，不做规则搜索、不做阈值扫描、不跑 true engine、不触发 A/B。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage235 摘要。
- 是否更新 `research/registry.md`：否。本阶段不是重要突破、路线废弃、正式候选或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是重要突破或正式候选。
