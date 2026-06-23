# Stage148 目标缺口与下一路线审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 23:15 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：研究路线审计 / 目标缺口与下一步路线选择
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Moskowitz/Ooi/Pedersen《Time Series Momentum》：https://elmwealth.com/wp-content/uploads/2017/06/timeseriesmomentum.pdf
  - Hurst/Ooi/Pedersen《A Century of Evidence on Trend-Following Investing》：https://fairmodel.econ.yale.edu/ec439/hurst.pdf
  - PyTrendFollow：https://github.com/chrism2671/PyTrendFollow
  - Broadfoot/Leveau《A Guide to Trend Following Strategies》：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4438260
- 我的判断：长期趋势跟随的第一性证据支持“简单、跨资产、跨周期、预声明”的趋势风险暴露，而不是在单条历史回撤或分钟残差里挖标签。当前线已反证 no-follow、opening-range、Tq top-book transform、maxDD label、账户层 vol/fixed capital、far-from-touch 等路线；如果继续救这些路线，本质上是在扩大过拟合风险。下一步只能走两条：等待真实 W0/授权 orderflow 数据，或在 Stage045 已校准 replay 子集上提出一个全新、预声明、非已关闭路线的只读假设。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage148_objective_gap_route_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage045/Stage147 固定 C9 minrisk 路径；本阶段不新增策略回测。
- 账户规模：沿用本线 C9 minrisk 研究口径。
- 成本口径：沿用输入账本，`total_slippage=2,730,130`
- 样本过滤：无新增过滤；只读读取 Stage045/080/082/083/084/099/108/109/141/147 结果。
- 策略/归因口径：目标缺口审计，不创建交易规则，不运行 true engine，不触发 A/B，不改变 official config，不连接 CTP，不调用 order API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - decision：`stage148_objective_gap_audit_ready_goal_not_complete_no_rule`
  - next_best_action：`new_predeclared_replay_hypothesis_or_wait_real_w0`
  - objective_gap_audit_ready：`1`
  - objective_completion_proven：`0`
  - objective_requirement_count：`10`
  - objective_missing_requirement_count：`6`
  - objective_proven_requirement_count：`4`
  - route_count：`7`
  - rule_candidate_allowed_route_count：`0`
  - real_candidate_package_supplied：`0`
  - current_package_promotion_allowed：`0`
  - side_effect_count：`0`
  - 目标缺口：缺少真实降回撤候选、80% 收益保留候选、真实 OOS/LOYO/monthly-start/right-tail 证据、可行动分钟 K 同源/授权数据、高质量最小风险信号。
  - 当前唯一可做的无新增数据研究：`calibrated_timestamp_ready_replay` 上的新预声明假设审计；不得从 residual 或已关闭路线救参。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage148_objective_gap_route_audit/qmt_roll_stage148_c9_minrisk_objective_gap_route_audit_report_stage148_objective_gap_route_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage148_objective_gap_route_audit/qmt_roll_stage148_c9_minrisk_objective_gap_route_audit_summary_stage148_objective_gap_route_audit_v1.csv`
- orders：无
- daily：无新增 daily 账本
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage148_objective_gap_route_audit/qmt_roll_stage148_c9_minrisk_objective_gap_route_audit_objective_requirement_gap_stage148_objective_gap_route_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage148_objective_gap_route_audit/qmt_roll_stage148_c9_minrisk_objective_gap_route_audit_route_scorecard_stage148_objective_gap_route_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage148_objective_gap_route_audit/qmt_roll_stage148_c9_minrisk_objective_gap_route_audit_next_action_queue_stage148_objective_gap_route_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage148_objective_gap_route_audit/qmt_roll_stage148_c9_minrisk_objective_gap_route_audit_gate_status_stage148_objective_gap_route_audit_v1.csv`
  - 5 张视觉图：official path gap status、objective gap matrix、route scorecard matrix、next action priority、gate status matrix。

## 结论

- 本阶段结论：目标尚未完成，且不能声称接近完成。当前 10 个目标要求中只有 4 个具备证据，6 个缺口仍在；7 条路线里 `rule_candidate_allowed=0`。真实 W0/授权 orderflow 未到，真实候选包未到。没有新数据时，唯一还可继续的研究动作是基于 Stage045 已校准 replay 子集写一个新的预声明假设，只做只读 preflight，且必须明显不同于 no-follow、opening-range、Tq-transform、maxDD-label、account-vol/fixed-capital、far-from-touch 等已关闭路线。
- 是否进入下一步：是。
- 下一步：优先等待真实 W0/授权 orderflow，并按 Stage125 -> Stage133 -> Stage112/113 进入数据验收；若继续无新增数据研究，则下一阶段只能写一个“非残差、非已关闭路线”的 Stage149 预声明假设规范，不进入 true engine，不触发 A/B，不改正式配置。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有收益优化、阈值扫描、品种/年份切片或交易规则；它明确指出哪些要求缺证据、哪些路线已关闭，作用是降低过拟合漂移。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：当前线如果不做目标缺口审计，很容易继续在历史失败路线周边救参。Stage148 把下一步压缩到真实数据验收或全新预声明假设，能保护“无过拟合、可穿越周期”的目标。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
