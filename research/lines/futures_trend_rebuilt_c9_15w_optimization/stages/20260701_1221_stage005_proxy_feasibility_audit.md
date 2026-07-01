# Stage005 冻结代理数据可行性审计

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01 12:21 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：数据可行性与代理蓝图，不改策略逻辑，不跑真实组合引擎
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 趋势跟随的右尾来自少数持续趋势，任何质量过滤或加风险都必须避免主账户核心右尾挤占。
- 多重检验和 Deflated Sharpe/PBO 框架要求先冻结数据与候选形状，再验证，不能边看回测边改标签。
- 本阶段采纳 Stage004 护栏：核心不挤占、鸡蛋独立、质量标签入场可见、加风险小额独立预算。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage005_proxy_feasibility_audit.py`
- 新增输出目录：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage005_proxy_feasibility_audit/`
- 修改策略脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增代理可行性审计口径。
- 修改参数：无
- 删除参数：无

## 数据要求审计结果

- `current_core_candidate_stream`：`PASS`。Stage167 entry candidates `9,751` 行，opened `3,043` 行，可作为当前重建核心候选流，不删除或替换原 C9 开仓。
- `current_rebuilt_closed_lots`：`FAIL`。当前 Stage167 输出目录未发现 trades/closed_lots/positions 文件，只有 entry_candidates 和 curves；无法用当前重建版逐笔 PnL 直接验证高质量标签。
- `current_entry_minute_quality_labels`：`FAIL`。Stage167 entry candidates 没有 entry_open/first_bar/ai4_6 aligned 标签。
- `old_quality_reference`：`REFERENCE_ONLY`。旧 Stage016 features `399` 行，`ai4_6_entry_or_first_aligned=24`，该标签 PnL `10,677,322.50`；只能作为特征蓝图，不能证明当前重建版达标。
- `current_ai_pool_membership`：`PASS`。Stage182 selected pool `477` 行，产品数 `19`，latest count `18`；可确认核心 C9 当前 AI 池，但不可直接重排。
- `jd_universe_eligible`：`PASS`。full-market universe 产品数 `57`，`jd.DCE` 存在。
- `jd_current_ai_scores`：`FAIL`。`jd_in_combined_pool=0`、`jd_in_latest_pool=0`；当前文件是 selected pool，不是完整 full-universe monthly score matrix，`jd` 没有当前 AI 分数历史。
- `period_gt_1y_validation_grid`：`PASS`。Stage002 annual rows `89`，可派生任意起点后周期大于一年年度/滚动约束，但当前只验证基准。
- `engine_hooks_for_non_displacing_add`：`PARTIAL`。策略代码存在 recovery_sleeve/post_entry_quality_add 字段和 entry_context，但当前 Stage167 均为 disabled/未触发；现有 hook 不等于 jd 独立 sleeve 或入场前质量加风险。

## 字段覆盖结论

- Stage167 entry candidates 已有：
  - `candidate_status`
  - `product_vt_symbol`
  - `direction`
  - `ai_product_pool_rank`
  - `ai_product_pool_score`
  - `ai_product_pool_allowed`
  - `oi_price_confirm_passed`
  - `oi_price_confirm_risk_restore_applied`
  - `portfolio_drawdown_pct`
- Stage167 entry candidates 缺失：
  - `broker10_margin_to_equity_pct`，逐日 curves 有但候选表没有。
  - `entry_open_relation_bucket`
  - `first_bar_relation_bucket`
  - `tag_ai4_6_entry_or_first_aligned`
  - `realized_pnl`
- 旧 Stage016 features 有质量标签和逐笔 PnL，但属于旧 C9 minrisk/highquality 线，只能迁移方法，不能直接作为当前重建版证据。

## 冻结代理蓝图

- `P0_core_preserve`：`READY`。保留当前 C9 核心，不删除、不重排、不降仓。
- `P1_hq_add_sleeve_proxy`：`DATA_BIND_REQUIRED`。只在当前 C9 已开仓且入场可见质量标签通过时，模拟小额独立加风险预算；需要当前 Stage167 opened entries + entry/first minute labels + closed-lot outcome。
- `P2_jd_independent_watch`：`CANDIDATE_GENERATION_REQUIRED`。把 `jd.DCE` 加入基础研究池，但不挤占核心 C9；需要 jd main contract mapping、独立候选生成、可选 full-universe AI score。
- `P3_shared_ai_rerank`：`FORBIDDEN_BY_STAGE004`。把 jd 或质量标签放入共享 AI topN 主池重排，禁止。
- `P4_topdown_risk_scaler`：`FORBIDDEN_BY_STAGE004`。按回撤、年度、窗口或波动统一调低/调高主账户风险，禁止。

## 输出文件

- report：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage005_proxy_feasibility_audit/rebuilt_c9_stage005_report_stage005_proxy_feasibility_audit_v1.md`
- requirements：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage005_proxy_feasibility_audit/rebuilt_c9_stage005_data_requirements_stage005_proxy_feasibility_audit_v1.csv`
- blueprint：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage005_proxy_feasibility_audit/rebuilt_c9_stage005_proxy_blueprint_stage005_proxy_feasibility_audit_v1.csv`
- fields：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage005_proxy_feasibility_audit/rebuilt_c9_stage005_field_presence_stage005_proxy_feasibility_audit_v1.csv`
- chart：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage005_proxy_feasibility_audit/rebuilt_c9_stage005_readiness_chart_stage005_proxy_feasibility_audit_v1.png`
- decision：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage005_proxy_feasibility_audit/rebuilt_c9_stage005_decision_stage005_proxy_feasibility_audit_v1.json`

## 结论

- Stage005 结论：现在不能直接写候选策略或跑 A/C，因为当前重建 Stage167 缺少逐笔 closed-lot 结果和当前口径的 entry/first-minute 质量标签。
- 旧 Stage016 质量标签有参考价值，但只能作为特征蓝图，不能作为当前重建版达标证据。
- 鸡蛋 `jd.DCE` 在 full-market universe 可用，但当前 Stage182 selected pool 和 latest pool 都没有 `jd`，且没有 full-universe monthly score matrix；所以不能做共享 AI rerank，也不能声称当前 AI 已能评价 `jd`。
- 下一步 Stage006 应先补当前重建版质量特征绑定器：Stage167 opened entries -> Stage861 minute labels -> closed-lot/outcome 或重跑保存 closed_lots。完成前不改交易逻辑。

## 过拟合反思

- 运行前判断：否。本阶段只审计数据可用性，不产生策略候选。
- 运行后判断：否。结论反而阻止了直接拿旧标签写当前候选，降低过拟合风险。

## 继续价值反思

- 运行前判断：是。目标要求高质量信号和加风险，必须先证明数据能支撑。
- 运行后判断：是。现在明确下一步不是扫参，而是补当前重建版质量特征绑定器。

## 合入建议

- 是否更新本线 `LINE.md`：是，补 Stage005 当前状态。
- 是否更新 `research/registry.md`：是，把本线最新阶段更新为 Stage005。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段未产生正式候选或重要突破。
