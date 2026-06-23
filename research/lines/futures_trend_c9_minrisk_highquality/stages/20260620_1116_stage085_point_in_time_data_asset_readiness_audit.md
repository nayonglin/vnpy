# Stage085 点时化数据资产 readiness 审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 11:16 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读数据源闸门审计；不是真实组合引擎，不新增交易规则。
- 是否重要突破：否。它是路线边界收束，不是候选突破。
- 是否触发A/B：否。没有可接入正式版或 A/B 的策略版本。

## 外部调研与判断

- 参考资料：
  - HftBacktest order-book imbalance 示例和文档：`https://github.com/nkaz001/hftbacktest/blob/master/examples/Market%20Making%20with%20Alpha%20-%20Order%20Book%20Imbalance.ipynb`、`https://hftbacktest.readthedocs.io/en/latest/tutorials/Market%20Making%20with%20Alpha%20-%20Order%20Book%20Imbalance.html`
  - CME open interest 说明：`https://www.cmegroup.com/education/courses/introduction-to-futures/open-interest`
  - Commodity carry / basis / inventory 研究：`https://macrosynergy.com/research/commodity-carry-as-a-trading-signal-part-1/`、`https://www.nber.org/system/files/working_papers/w13249/w13249.pdf`
- 我的判断：
  - 盘口/订单簿不平衡、OFI、spread/depth/queue 是有第一性先验的短周期信息，但必须有同源或授权的 BBO/depth/trade feed，且要能还原成交与队列语义；当前 Tq dur0 tick 被 Stage080 降级为 TCA，不应规则化。
  - 会员持仓、仓单、库存、基差、COT 这类外生源有商品基本面先验，但必须点时化、覆盖足够、口径权威，并且先证明不会切断 C9 右尾；当前本地缓存不满足。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage085_point_in_time_data_asset_readiness_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无交易参数；新增数据 route gate 字段：`point_in_time`、`preentry_or_event_time_visible`、`same_source_or_authorized`、`full_coverage`、`not_outcome_label`、`prior_not_closed`、`right_tail_protected`。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage010 官方 C9/15w 日曲线与本线 Stage027/028/060/065/066/068/076/080/084 输出；本阶段不重跑策略回测。
- 账户规模：`150,000`。
- 成本口径：沿用官方曲线成本与滑点汇总。
- 样本过滤：不按盈亏、年份、品种、方向筛选；路线固定为授权盘口/quote/depth、Tq reentry tick、Tq initial-entry tick、Stage449/raw、会员持仓、仓单/库存/基差、CFTC COT、Stage496、账户层。
- 策略/归因口径：只读 route gate。任一路线必须同时通过点时化、入场前/事件时可见、同源或授权、覆盖完整、非最终盈亏标签、既有路线未关闭、右尾保护，才允许进入下一阶段候选审计。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6339`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：沿用 Stage010 官方口径 `53.2560%`
- 其他关键指标：
  - route_count：`9`
  - rule_candidate_allowed_route_count：`0`
  - asset_family_count：`5`
  - asset_file_count：`254`
  - top_route_by_readiness：`R4_stage449_raw_generation_open_quote`
  - top_readiness_score_pct：`71.4286%`
  - authorized_orderbook_local_asset_count：`0`
  - member_rank_cache_file_count：`1`
  - basis_warehouse_cache_file_count：`4`
  - cftc_cache_file_count：`7`
  - strategy_rule_created：`0`
  - true_engine_run：`0`
  - order_api_called：`0`
  - ctp_connected：`0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage085_point_in_time_data_asset_readiness_audit/qmt_roll_stage085_c9_minrisk_point_in_time_data_asset_readiness_audit_report_stage085_point_in_time_data_asset_readiness_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage085_point_in_time_data_asset_readiness_audit/qmt_roll_stage085_c9_minrisk_point_in_time_data_asset_readiness_audit_summary_stage085_point_in_time_data_asset_readiness_audit_v1.csv`
- route_scorecard：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage085_point_in_time_data_asset_readiness_audit/qmt_roll_stage085_c9_minrisk_point_in_time_data_asset_readiness_audit_route_scorecard_stage085_point_in_time_data_asset_readiness_audit_v1.csv`
- asset_catalog：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage085_point_in_time_data_asset_readiness_audit/qmt_roll_stage085_c9_minrisk_point_in_time_data_asset_readiness_audit_asset_catalog_stage085_point_in_time_data_asset_readiness_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage085_point_in_time_data_asset_readiness_audit/qmt_roll_stage085_c9_minrisk_point_in_time_data_asset_readiness_audit_decision_stage085_point_in_time_data_asset_readiness_audit_v1.json`
- official path/data gate chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage085_point_in_time_data_asset_readiness_audit/qmt_roll_stage085_c9_minrisk_point_in_time_data_asset_readiness_audit_official_path_data_gate_chart_stage085_point_in_time_data_asset_readiness_audit_v1.png`
- route gate heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage085_point_in_time_data_asset_readiness_audit/qmt_roll_stage085_c9_minrisk_point_in_time_data_asset_readiness_audit_route_gate_heatmap_stage085_point_in_time_data_asset_readiness_audit_v1.png`
- asset catalog chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage085_point_in_time_data_asset_readiness_audit/qmt_roll_stage085_c9_minrisk_point_in_time_data_asset_readiness_audit_asset_catalog_chart_stage085_point_in_time_data_asset_readiness_audit_v1.png`
- next action chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage085_point_in_time_data_asset_readiness_audit/qmt_roll_stage085_c9_minrisk_point_in_time_data_asset_readiness_audit_next_action_chart_stage085_point_in_time_data_asset_readiness_audit_v1.png`

## 视觉结论

- official path/data gate chart：官方 C9/15w 权益右尾仍强，但 2022 附近深回撤与 broker10 尖峰未被任何已就绪 route 解释或覆盖；图上 `route_allowed=0/9` 是本阶段核心视觉结论。
- route gate heatmap：所有路线最后一列 `rule_candidate_allowed` 全为 `0`。多数路线卡在 `full_coverage`、`same_source_or_authorized`、`prior_not_closed`、`right_tail_protected`，说明本地有数据不等于可交易规则。
- asset catalog chart：文件数主要集中在 `tqsdk_stage449_459_861_minute` 和 `tqsdk_tick_or_gap_backfill`，但这两类已经被 Stage080/Stage084 边界约束为 TCA/账本资产；会员持仓、仓单/基差和 CFTC 文件数量较少且覆盖/映射不足。
- next action chart：最高 readiness 的 Stage449/raw 和 CFTC 仍是红色 blocked，前者缺真实 quote/depth/raw 字段，后者缺国内合约映射和频率滞后规范。

## 结论

- 本阶段结论：`stage085_no_rule_ready_data_source_get_authorized_or_official_point_in_time_data`
- 是否进入下一步：进入数据工程下一步，不进入 true engine、不进入 A/B、不产生策略候选。
- 下一步：
  - 第一优先：取得授权 vendor/raw exchange tick/quote/depth，或找到 Stage449/raw 生成端真实 open/quote/depth 字段；拿到后按固定 spec 做全量覆盖和右尾保护审计。
  - 第二优先：补官方/授权会员持仓 `2020-2022` 和 DCE/CZCE/SHFE/GFEX 历史缺口，统一品种/合约口径后再绑定 C9。
  - 第三优先：用官方细粒度仓单/库存/基差替换或验证当前第三方缓存，再做固定 spec 只读审计。
  - 在新增数据前，不从 closed-lot、maxDD episode、账户曲线、Tq exact/mismatch、Stage449 zero-volume source class 继续反推规则。

## 过拟合反思

- 运行前判断：否。只做数据资产 readiness 审计，不生成交易规则；它的作用是防止继续从历史曲线救参。
- 运行后判断：否。输出为 `0/9` route allowed，没有利用历史盈亏挑选规则。
- 原因：本阶段使用的是硬 gate，不是收益最大化。真正会过拟合的是绕过这些 gate，继续扫 fixed weight、盘口字段、member TopN、basis 阈值、CFTC 映射、年份/品种/方向或 maxDD episode 标签。

## 继续价值反思

- 运行前判断：有。Stage084 后旧账户层关闭，必须判断本地是否已有可用新增信息源。
- 运行后判断：有，但价值集中在数据工程，不在策略参数研究。
- 原因：Stage085 证明本地现有资产没有 rule-ready route；继续做策略阈值没有价值。真正有价值的是拿到授权盘口/quote/depth、Stage449/raw 真实字段、官方会员持仓或官方仓单/库存/基差覆盖后，再按固定 spec 复验。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage085 结论和下一步边界。
- 是否更新 `research/registry.md`：否。本阶段不是正式候选、不是重要突破，也不是跨线合入。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段为本线边界记录，不是正式候选或重要合入摘要。
