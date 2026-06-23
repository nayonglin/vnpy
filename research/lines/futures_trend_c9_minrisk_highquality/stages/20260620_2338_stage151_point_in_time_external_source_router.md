# Stage151 点时化外生源路线筛选

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 23:38 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：外生源路线筛选 / 数据合同前置 / 非规则候选
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Databento Futures Market Data：https://databento.com/futures
  - CME DataMine：https://www.cmegroup.com/datamine.html
  - FirstRate Data historical intraday data：https://firstratedata.com/
  - Macrosynergy commodity carry：https://macrosynergy.com/research/commodity-carry-as-a-trading-signal-part-1/
  - CME CVOL/skew research：https://www.cmegroup.com/insights/economic-research/2023/is-cvol-skew-a-leading-indicator-of-price-trends-in-commodities-bonds-and-currency-markets.html
- 我的判断：真正贴合本线目标的外生源必须同时满足“入场前或入场当刻可见、点时化、分钟级执行相关、独立于最终盈亏、跨品种可覆盖”。公开资料显示历史分钟K、tick、MBO/MBP、PCAP 可以通过授权方式取得；期权 IV/skew、carry、仓单/会员等有经济含义，但不是直接的分钟级执行证据。结合 Stage150，下一步不应继续在 internal replay 标签上救参，而应优先补权威 `1m OHLCV + real volume/OI` 数据合同。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage151_point_in_time_external_source_router.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage045/Stage150 官方路径与既有汇总；本阶段不新增策略回测。
- 账户规模：沿用本线 C9 minrisk 研究口径。
- 成本口径：沿用输入账本，`total_slippage=2,730,130`
- 样本过滤：不新增交易过滤；只读读取 Stage099/107/114/115/150 summary。
- 策略/归因口径：数据路线筛选，不创建规则，不运行 true engine，不触发 A/B，不连接 CTP，不调用订单 API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - decision：`stage151_external_source_router_selects_minute_ohlcv_manifest_no_rule`
  - next_best_action：`stage152_authoritative_minute_ohlcv_manifest`
  - source_route_screen_ready：`1`
  - source_route_count：`8`
  - data_engineering_route_count：`7`
  - closed_route_collision_count：`3`
  - rule_feasible_route_count：`0`
  - current_data_ready_route_count：`1`，但唯一 ready 的是已阻断的 internal replay labels，不能作为规则源。
  - selected_next_route：`authoritative_minute_ohlcv_volume`
  - selected_next_route_priority_rank：`1`
  - selected_next_route_rule_feasible_now：`0`
  - selected_next_route_requires_manifest：`1`
  - stage152_manifest_requirement_count：`18`
  - stage152_manifest_hard_gate_count：`16`
  - stage150_h3_rule_feasible_now：`0`
  - stage150_tail_conflict_cell_count：`4`
  - current_package_promotion_allowed：`0`
  - true_engine_allowed：`0`
  - strategy_feature_usable：`0`
  - side_effect_count：`0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage151_point_in_time_external_source_router/qmt_roll_stage151_c9_minrisk_point_in_time_external_source_router_report_stage151_point_in_time_external_source_router_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage151_point_in_time_external_source_router/qmt_roll_stage151_c9_minrisk_point_in_time_external_source_router_summary_stage151_point_in_time_external_source_router_v1.csv`
- orders：无
- daily：无新增 daily 账本
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage151_point_in_time_external_source_router/qmt_roll_stage151_c9_minrisk_point_in_time_external_source_router_source_route_scorecard_stage151_point_in_time_external_source_router_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage151_point_in_time_external_source_router/qmt_roll_stage151_c9_minrisk_point_in_time_external_source_router_manifest_requirements_stage151_point_in_time_external_source_router_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage151_point_in_time_external_source_router/qmt_roll_stage151_c9_minrisk_point_in_time_external_source_router_next_action_queue_stage151_point_in_time_external_source_router_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage151_point_in_time_external_source_router/qmt_roll_stage151_c9_minrisk_point_in_time_external_source_router_gate_status_stage151_point_in_time_external_source_router_v1.csv`
  - 5 张视觉图：official path source status、route score matrix、source priority bars、manifest requirement matrix、gate status matrix。

## 结论

- 本阶段结论：Stage151 没有找到任何可直接规则化的路线，`rule_feasible_route_count=0`。但路线筛选明确了下一步最高价值数据工程方向：`authoritative_minute_ohlcv_volume`。它比期权 IV/skew、carry、仓单/会员、宏观新闻更贴合“基于分钟级别 K 线进出场”的目标，也避开 Stage102/150 internal replay 的 post-entry 标签和 closed-route 冲突。Stage152 应只写权威分钟 OHLCV/volume/OI manifest 与 required-window coverage contract，不做规则、不做阈值。
- 是否进入下一步：是。
- 下一步：Stage152 构建 `authoritative_minute_ohlcv_volume` 的固定 manifest 和覆盖门槛，字段至少包括 raw_file、sha256、schema_hash、vendor_license、query_params、vt_symbol、bar_start/end_ts、OHLC、real volume、turnover/OI、session calendar、sequence gap、right-tail/bottom-loss/maxDD window coverage。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有收益优化、阈值扫描、品种/年份/方向切片、true engine 或交易规则；它把路线限制到数据合同，避免把 internal replay 或粗外生源包装成交易条件。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：Stage150 后继续做 H3 internal replay 已经价值很低；Stage151 把下一步转为权威分钟K数据合同，仍然贴近原目标的“分钟级别 K 线进出场”，同时保持无过拟合。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
