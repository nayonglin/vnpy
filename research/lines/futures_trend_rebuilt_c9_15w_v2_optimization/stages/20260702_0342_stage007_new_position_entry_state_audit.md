# Stage007 新增/交易仓入场状态审计

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02 03:44 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因；不改策略、不改实盘配置、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否；本阶段只产生真实引擎 A/B 候选假设，尚未产生策略候选

## 外部调研与判断

- 参考资料：
  - pysystemtrade / Rob Carver 系统化交易框架：趋势期货策略要拆分 forecast、position sizing、组合风险和成本。
  - Machine Learning for Trading：时间序列/机器学习交易研究必须避免 look-ahead contamination。
  - Trend-following/managed-futures 资料：whipsaw 和 drawdown 是趋势策略结构性成本，不能用单个历史伤口做黑名单。
- 我的判断：
  - Stage006 已证明残余主要来自窗口后新增/交易仓的 base holding path；Stage007 应看入场前可见状态，而不是继续扫 Stage074 ramp、AI topN、具体品种方向或事后 MAE/MFE。
  - 产品方向归因只作解释；真正可能进入下一步的只能是 PIT 入场前条件。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage007_new_position_entry_state_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage007_new_position_entry_state_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `min_population_count=50`
  - `min_source_count=3`
  - `min_loss_share_pct=5.0`
  - `min_lift=1.25`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage006 residual windows 和 Stage019 closed lots 可用区间。
- 账户规模：沿用 Stage013/Stage019 C9 15w rebuilt closed lots。
- 成本口径：本阶段不重新计算成本，只使用 Stage006 holding loss 权重和 Stage019 入场批次特征。
- 样本过滤：
  - Stage006 `window_position_detail` 中 `source_bucket=opened_or_traded_after_window_start`。
  - 仅保留 `stage074_scaled_holding_pnl < 0` 且 direction 为 `long/short` 的 window/product/direction 行。
  - Stage019 closed lots 按同 source、同 product、同 direction、`entry_date > window_start_date` 且 `entry_date <= window_end_date` 匹配。
- 策略/归因口径：
  - 一个 Stage006 window/product/direction 的 holding loss 按匹配 lots 等权分摊。
  - 背景样本为同 source 的 first residual window start 到 last residual window end 之间全部 closed lots。
  - product/direction 和事后 MAE/MFE/R multiple 不允许作为交易候选条件。

## 结果

- 期末权益：不适用，本阶段不是回测
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - window loss rows：`13,981`
  - window 数：`929`
  - source 数：`10`
  - entry exposure rows：`32,419`
  - unique exposed lots：`470`
  - background lots：`598`
  - matched holding loss：`489,388,288.0757`
  - unmatched holding loss：`0.0`
  - matched holding loss share：`100.0%`
  - stable candidate conditions：`rsi_exhaustion_zone`、`ai_rank_5_to_8`、`selected_volume_gt1`、`risk_multiplier_ge2`
  - 只读产品方向归因前三：`SM.CZCE short` loss share `25.4627%`、`fu.SHFE long` `23.3301%`、`sp.SHFE long` `22.0173%`

## 输出文件

- report：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage007_new_position_entry_state_audit/rebuilt_c9_v2_stage007_new_position_entry_state_audit_report_stage007_new_position_entry_state_audit_v1.md`
- decision：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage007_new_position_entry_state_audit/rebuilt_c9_v2_stage007_new_position_entry_state_audit_decision_stage007_new_position_entry_state_audit_v1.json`
- entry exposures：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage007_new_position_entry_state_audit/rebuilt_c9_v2_stage007_new_position_entry_state_audit_entry_exposures_stage007_new_position_entry_state_audit_v1.csv.gz`
- background lots：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage007_new_position_entry_state_audit/rebuilt_c9_v2_stage007_new_position_entry_state_audit_background_lots_stage007_new_position_entry_state_audit_v1.csv.gz`
- condition summary：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage007_new_position_entry_state_audit/rebuilt_c9_v2_stage007_new_position_entry_state_audit_condition_summary_stage007_new_position_entry_state_audit_v1.csv`
- numeric feature summary：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage007_new_position_entry_state_audit/rebuilt_c9_v2_stage007_new_position_entry_state_audit_numeric_feature_summary_stage007_new_position_entry_state_audit_v1.csv`
- product direction summary：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage007_new_position_entry_state_audit/rebuilt_c9_v2_stage007_new_position_entry_state_audit_product_direction_summary_stage007_new_position_entry_state_audit_v1.csv`
- chart：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage007_new_position_entry_state_audit/rebuilt_c9_v2_stage007_new_position_entry_state_audit_condition_lift_chart_stage007_new_position_entry_state_audit_v1.png`

## 结论

- 本阶段结论：`stage007_has_pit_entry_state_candidates_need_true_engine_ab`。
- 是否进入下一步：是，但只能进入冻结真实引擎 A/B，不得直接改正式版。
- 下一步：
  - 不做 `SM/fu/sp` 产品方向黑名单。
  - 不做简单 topN 或日期窗口规则。
  - 优先验证 PIT 条件组合：`rsi_exhaustion_zone`、`ai_rank_5_to_8`、`selected_volume_gt1`、`risk_multiplier_ge2`，并保持 AI 月池、止损重试、保证金、整数手和成本逻辑不变。

## 过拟合反思

- 运行前判断：有过拟合风险。
- 运行后判断：仍有过拟合风险，但比直接挖品种/日期低。
- 原因：标签来自已知 residual loss windows；本阶段通过跨 source、样本数、loss share、lift 门槛和 PIT 字段约束降低风险，但不能证明收益提升，必须真实引擎多起点验证。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：Stage007 给出了 4 个非品种黑名单的入场前候选条件，并确认 Stage006->Stage019 映射覆盖 `100%`，下一步可以做低自由度 A/B，而不是继续盲扫。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage007 结论和下一步。
- 是否更新 `research/registry.md`：是，把二期线最新阶段推进到 Stage007。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段不是正式候选、重要突破或跨线合入。
