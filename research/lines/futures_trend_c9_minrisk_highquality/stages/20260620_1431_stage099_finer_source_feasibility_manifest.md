# Stage099 更细信息源可行性 manifest

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 14:31 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读信息源 manifest；不是真引擎、不生成交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - 郑商所持仓排名：`https://www.czce.com.cn/cn/jysj/ccpm/H077003004index_1.htm`
  - SHFE 成交持仓公布标准：`https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/dailyranking/decl/`
  - CFTC COT explanatory notes：`https://www.cftc.gov/MarketReports/CommitmentsofTraders/ExplanatoryNotes/index.htm`
  - CFTC COT reports：`https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm`
  - AKShare 期货数据文档：`https://akshare.akfamily.xyz/data/futures/futures.html`
  - GitHub `hftbacktest`：`https://github.com/nkaz001/hftbacktest`
  - GitHub `nautilus_trader`：`https://github.com/nautechsystems/nautilus_trader`
- 我的判断：更细信息源的本质不是“再找一个阈值”，而是取得当时可见、能解释风险承接的更高分辨率状态。官方/交易所公开持仓排名和 COT 类资料说明，持仓解释力来自类别、席位、合约月份、报告门槛和发布时间；GitHub 盘口回放项目也说明 orderflow/队列必须有完整 tick/depth、延迟和排队语义。当前产品总计级仓单/会员排名不能替代这些细粒度数据，直接规则化会走向过拟合。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage099_finer_source_feasibility_manifest.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数/字段：
  - `route_id`：`member_category_seat_structure`、`contract_month_oi_migration`、`inventory_basis_term_structure`、`authorized_quote_depth_orderflow`、`same_source_executable_minute_bars`、`stage045_timestamp_ready_replay_new_candidate`
  - `point_in_time_fields_required`
  - `entry_time_visibility`
  - `expected_granularity_gain`
  - `minute_k_alignment`
  - `coverage_expectation`
  - `permission_cost_risk`
  - `implementation_risk`
  - `overfit_risk`
  - `right_tail_gate`
  - `direct_rule_allowed=0`
  - `true_engine_allowed=0`
  - `ab_allowed=0`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用基准路径作为背景曲线；Stage098 gate 作为上游阻断证据。
- 账户规模：沿用基准路径，仅作背景路径。
- 成本口径：沿用基准统计，总滑点 `2,730,130`。
- 样本过滤：无新增收益样本过滤。
- 策略/归因口径：只读 manifest，`manifest_only=1`、`strategy_feature_usable=0`、`true_engine_run=0`。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`53.2560%`
- 其他关键指标：
  - `decision=stage099_finer_source_manifest_built_no_rule`
  - `prior_stage_decision=stage098_product_total_granularity_insufficient_no_rule`
  - `route_count=6`
  - `data_engineering_route_count=4`
  - `procurement_required_route_count=1`
  - `immediate_research_route_count=1`
  - `direct_rule_allowed_count=0`
  - `true_engine_allowed_count=0`
  - `ab_allowed_count=0`
  - `promotion_gate_count=4`
  - `promotion_gate_pass_count=0`
  - `recommended_next_route=stage045_timestamp_ready_replay_new_candidate`
  - `recommended_next_action=next Stage100 should be read-only preflight for a new non-closed minute candidate`
  - `official_config_changed=0`、`strategy_rule_created=0`、`true_engine_run=0`、`ab_triggered=0`、`order_api_called=0`、`ctp_connected=0`

## 视觉观察

- official context chart：上方资金/回撤曲线仅作为背景；下方工程 readiness 排序显示 `stage045_timestamp_ready_replay_new_candidate` 是唯一可立即推进的研究路线，且仍是 `rule_allowed=0`。
- feasibility heatmap：`authorized_quote_depth_orderflow` 的信息价值和分钟对齐最高，但 `coverage_expectation=unknown`、权限和实现摩擦都高；不应让当前研究卡在采购前置条件上。
- priority quadrant：`stage045_timestamp_ready_replay_new_candidate` 位于低摩擦高信息价值区域；`same_source_executable_minute_bars` 和 `authorized_quote_depth_orderflow` 信息价值也高，但前者需要生产同源数据恢复，后者需要授权 tick/depth。
- promotion gate chart：四个 gate 全部 blocked，没有任何 route 可以进入交易规则、true engine、A/B 或执行链路。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage099_finer_source_feasibility_manifest/qmt_roll_stage099_c9_minrisk_finer_source_feasibility_manifest_report_stage099_finer_source_feasibility_manifest_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage099_finer_source_feasibility_manifest/qmt_roll_stage099_c9_minrisk_finer_source_feasibility_manifest_summary_stage099_finer_source_feasibility_manifest_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage099_finer_source_feasibility_manifest/qmt_roll_stage099_c9_minrisk_finer_source_feasibility_manifest_decision_stage099_finer_source_feasibility_manifest_v1.json`
- manifest：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage099_finer_source_feasibility_manifest/qmt_roll_stage099_c9_minrisk_finer_source_feasibility_manifest_manifest_stage099_finer_source_feasibility_manifest_v1.csv`
- priority matrix：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage099_finer_source_feasibility_manifest/qmt_roll_stage099_c9_minrisk_finer_source_feasibility_manifest_priority_matrix_stage099_finer_source_feasibility_manifest_v1.csv`
- promotion gate：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage099_finer_source_feasibility_manifest/qmt_roll_stage099_c9_minrisk_finer_source_feasibility_manifest_promotion_gate_stage099_finer_source_feasibility_manifest_v1.csv`
- charts：
  - `qmt_roll_stage099_c9_minrisk_finer_source_feasibility_manifest_official_context_chart_stage099_finer_source_feasibility_manifest_v1.png`
  - `qmt_roll_stage099_c9_minrisk_finer_source_feasibility_manifest_feasibility_heatmap_stage099_finer_source_feasibility_manifest_v1.png`
  - `qmt_roll_stage099_c9_minrisk_finer_source_feasibility_manifest_priority_quadrant_stage099_finer_source_feasibility_manifest_v1.png`
  - `qmt_roll_stage099_c9_minrisk_finer_source_feasibility_manifest_promotion_gate_chart_stage099_finer_source_feasibility_manifest_v1.png`

## 结论

- 本阶段结论：更细信息源路线只形成数据工程地图，不形成交易规则。会员类别/席位结构、合约月份 OI 迁移、库存/基差/期限结构、授权盘口/队列/成交流、生产同源分钟数据都必须先过 raw 覆盖、发布时间、schema、右尾保护和视觉 gate。
- 是否进入下一步：有价值继续，但不应继续围绕当前产品总计级外生表救参。
- 下一步：默认进入 Stage100，在 Stage045 已校准的 `timestamp_ready=1` replay 子集上做一个不同构、第一性、只读的分钟候选预检；fallback/no-proxy 样本保持原路径，不得当成筛选条件。若未来拿到授权细粒度数据，再按本 manifest 建立覆盖和点时化审计。

## 过拟合反思

- 运行前判断：否。Stage099 是信息源边界设计，不优化收益、不扫阈值。
- 运行后判断：否。所有 route 均显式 `direct_rule_allowed=0`、`true_engine_allowed=0`，工程优先级分数只用于数据路线排序，不是策略评分。
- 原因：如果把 `contract_month_oi_migration`、`member_category_seat_structure` 或 `authorized_quote_depth_orderflow` 的高分直接当成交易规则，就是把数据可行性误用成策略证据；本阶段没有这么做。

## 继续价值反思

- 运行前判断：有价值。Stage098 已关闭产品总计级直接规则化，Stage099 可以防止下一步在错误数据粒度上继续消耗。
- 运行后判断：有价值，但价值不在当前外生聚合表；价值在把数据工程路线和立即可推进的 Stage100 replay 新候选分开。
- 原因：授权盘口/队列信息从第一性上更接近“高质量信号用最小风险搏最大收益”的执行问题，但短期获取摩擦高；当前能立即推进的是已校准 replay 子集的新候选预检。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage099 摘要和 Stage100 边界。
- 是否更新 `research/registry.md`：否，不是正式候选、重要突破或路线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，不是正式候选、重要突破或跨线合并。
