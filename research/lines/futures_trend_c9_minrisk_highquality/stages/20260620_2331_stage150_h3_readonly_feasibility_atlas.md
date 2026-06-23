# Stage150 H3 只读可行性与视觉 atlas

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 23:31 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：H3 预声明假设的只读可行性审计 / 视觉 atlas / 规则入口阻断
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Research Affiliates《Walking the Tightrope: Trend Following's Tricky Tradeoffs》：https://www.researchaffiliates.com/insights/publications/articles/1077-trend-followings-tricky-tradeoffs-sharpe-ratio-vs-skew
  - Man Group《Creating Portfolio Convexity: Trend Versus Options》：https://www.man.com/insights/creating-portfolio-convexity
  - Man AHL《Trend Following and Drawdowns: Is This Time Different?》：https://www.man.com/documents/download/968d3-bd4b9-d4724-f6ab8/Man_AHL_Analysis_Trend_Following_and_Drawdowns%3A_Is_This_Time_Different%3F_English_%28United_States%29_17-06-2025.pdf
  - GitHub walk-forward-analysis topic：https://github.com/topics/walk-forward-analysis
  - GitHub `TonyMa1/walk-forward-backtester`：https://github.com/TonyMa1/walk-forward-backtester
- 我的判断：趋势跟随的长期价值高度依赖右尾凸性和正偏收益，降低回撤的 overlay 如果没有同源执行证据，最容易把右尾当噪声砍掉。公开 walk-forward/backtest 框架能提供验证纪律，但不能替代本线需要的授权同源分钟 K、盘口或 broker execution replay。因此 Stage150 只能证明 H3 当前是否具备规则化条件，不能从 Stage102 的 post-entry 标签里直接挖规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage150_h3_readonly_feasibility_atlas.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage045/Stage102/Stage149 固定 C9 minrisk 路径与账本；本阶段不新增策略回测。
- 账户规模：沿用本线 C9 minrisk 研究口径。
- 成本口径：沿用输入账本，`total_slippage=2,730,130`
- 样本过滤：不新增交易过滤；只读读取 Stage102 context rows `219` 笔、Stage149 H3 spec 与 evidence。
- 策略/归因口径：H3 feasibility audit；Stage102 event family、runway bucket、tail context 只作视觉上下文，不允许作为交易条件。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - decision：`stage150_h3_readonly_feasibility_blocks_rule_no_candidate`
  - next_best_action：`wait_real_w0_or_find_new_point_in_time_external_source`
  - h3_feasibility_audit_ready：`1`
  - h3_rule_feasible_now：`0`
  - same_source_or_authorized_data_ready：`0`
  - stage102_context_order_count：`219`
  - right_tail_order_count：`18`
  - bottom_loss_order_count：`18`
  - maxdd_context_order_count：`24`
  - low_resolution_order_count：`93`
  - tail_conflict_cell_count：`4`
  - blocked_feature_route_count：`5`
  - rule_feasible_route_count：`0`
  - feasibility_evidence_count：`11`
  - rule_entry_evidence_pass_count：`3`
  - atlas_row_count：`24`
  - atlas_page_count：`4`
  - current_package_promotion_allowed：`0`
  - true_engine_allowed：`0`
  - strategy_feature_usable：`0`
  - side_effect_count：`0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage150_h3_readonly_feasibility_atlas/qmt_roll_stage150_c9_minrisk_h3_readonly_feasibility_atlas_report_stage150_h3_readonly_feasibility_atlas_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage150_h3_readonly_feasibility_atlas/qmt_roll_stage150_c9_minrisk_h3_readonly_feasibility_atlas_summary_stage150_h3_readonly_feasibility_atlas_v1.csv`
- orders：无
- daily：无新增 daily 账本
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage150_h3_readonly_feasibility_atlas/qmt_roll_stage150_c9_minrisk_h3_readonly_feasibility_atlas_feasibility_evidence_stage150_h3_readonly_feasibility_atlas_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage150_h3_readonly_feasibility_atlas/qmt_roll_stage150_c9_minrisk_h3_readonly_feasibility_atlas_blocked_feature_routes_stage150_h3_readonly_feasibility_atlas_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage150_h3_readonly_feasibility_atlas/qmt_roll_stage150_c9_minrisk_h3_readonly_feasibility_atlas_tail_conflict_matrix_stage150_h3_readonly_feasibility_atlas_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage150_h3_readonly_feasibility_atlas/qmt_roll_stage150_c9_minrisk_h3_readonly_feasibility_atlas_r_path_summary_atlas_manifest_stage150_h3_readonly_feasibility_atlas_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage150_h3_readonly_feasibility_atlas/qmt_roll_stage150_c9_minrisk_h3_readonly_feasibility_atlas_gate_status_stage150_h3_readonly_feasibility_atlas_v1.csv`
  - 5 张主视觉图：official path H3 status、feasibility evidence matrix、tail conflict heatmap、leadtime runway distribution、gate status matrix。
  - 4 页 R-path summary atlas：page001-page004。

## 结论

- 本阶段结论：H3 在当前本地数据下不能规则化。五条可能路线全部被阻断：`event_family_direct_rule` 属于 post-entry/replay 后标签；`runway_bucket_rule` 与 Stage102/far-from-touch 已关闭形状冲突；`tail_separation_by_existing_ohlc` 在现有 OHLC 上无法无过拟合地区分右尾和底部亏损；`authorized_orderflow_continuation` 缺真实 W0/授权数据；`broker_execution_replay_maturity` 缺同源执行回放。Stage150 生成了资金曲线和 24 笔 R-path 视觉 atlas，但这只能说明为什么当前不能进规则，不能说明有候选。
- 是否进入下一步：是，但必须换到“真实数据到货验收”或“新的点时化外生信息源定义”，不能继续在 Stage102 event family/runway bucket 上救参。
- 下一步：优先等待真实 W0/授权 orderflow 并执行 Stage125 -> Stage133 -> Stage112/113；若继续无新增数据研究，Stage151 只能做新 point-in-time 外生源路线筛选，不能再把 H3 internal replay 包装成规则。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有调阈值、没有按年份/品种/方向切片优化、没有 true engine、没有交易规则；所有可疑路线都被显式阻断，特别是 post-entry event family 和 runway bucket。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但 H3 internal replay 的继续价值已经很低。
- 原因：Stage150 给出强边界：现有内部 replay 标签不足以形成无过拟合规则。继续价值转移到真实 W0/授权 orderflow，或寻找新的入场前可见、点时化、非最终盈亏标签的外生源。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
