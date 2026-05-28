# Stage126 多候选晋级口径审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-28 01:08 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读晋级审计；汇总 Stage403-425 的已冻结候选、目标闸门和后续降级证据。
- 是否重要突破：是。重要性不是新增更强版本，而是明确当前只能晋级 Stage103，避免把高短持有分但鲁棒性不足的版本误升为主候选。
- 是否触发A/B：否。本阶段不新增策略版本，不改变 A/C 默认口径，只做候选层级整理。

## 外部调研与判断

- 参考资料：
  - NBER Working Paper 21329 `Backtesting Strategies Based on Multiple Signals`：多信号/多候选策略选择会显著放大样本内过拟合和多重检验偏差。
  - GitHub `esvhd/pypbo`：提供 PBO、PSR、MinTRL、Deflated Sharpe Ratio 等回测过拟合诊断框架，说明多候选筛选后不能只看最高 Sharpe 或最高分。
- 我的判断：
  - 当前已经从 Stage079 以后连续尝试了多个低自由度风险源和 overlay；如果只按 3个月/6个月短持有分排序，`activation_linear_6m_33`、股指 TSMOM、OI确认、value proxy 等都会显得有吸引力。
  - 但“任何时候启动、启动多久体验都不能明显劣化”的目标，本质上更接近稳健性/选择偏差控制问题，不是单表打分问题。
  - 因此本阶段采用更严格晋级口径：先过 Stage079 原始硬闸门，再看是否能超过当前 Stage103 incumbent，最后检查是否已被后续鲁棒性审计降级。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage426_active_objective_promotion_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - 审计范围：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage4*_gate_*.csv`
  - 主基准：`stage079`
  - 当前 incumbent：`xsmom_vt10_q_momq_round_half_true_broker10_guard`
  - 后续降级映射：Stage115 股指 best1、Stage122 value756、Stage125 OI best1。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用各 Stage403-425 固定输出的公共全周期与多起点审计口径，主样本为 `2020-2026`。
- 账户规模：Stage079 口径为 `50万C3下单 + 11.5万外部现金`，总账户 `61.5万`；Stage103 及后续候选均不增加账户总资金。
- 成本口径：沿用各候选 gate 文件中的 `1x/2x/3x/5x` 成本压力与 `1.10x` broker 保证金审计结果。
- 样本过滤：不新增过滤；只读取已冻结 gate / summary / score 输出。
- 策略/归因口径：只读候选晋级审计，不修改交易规则、品种池、入场/出场逻辑、保证金或下单路径。

## 结果

- Stage079 基准：
  - 期末权益：`31,040,650`
  - 总收益：`4947.2602%`
  - 最大回撤：`-29.7007%`
  - Sharpe：`1.3188`
  - Ulcer：`15.0874`
  - 总滑点：`1,556,750`
  - 总交易次数：`757`
  - 胜率：日度胜率 `36.2924%`，非零日胜率约 `48.3478%`
- 当前主执行相对候选 Stage103 `xsmom_vt10_q_momq_round_half_true_broker10_guard`：
  - 期末权益：`31,730,915`
  - 总收益：`5059.4984%`
  - 最大回撤：`-28.9792%`
  - Sharpe：`1.3681`
  - Ulcer：`14.3132`
  - 总滑点：`1,569,265`
  - 总交易次数：`1,217`
  - 胜率：日度胜率约 `43.0809%`，非零日胜率约 `50.3432%`
  - 3个月/6个月短持有分：`121.2041 / 134.4513`
  - 90/180日用户8项改善：`6/8 / 6/8`
- Stage079 原始目标通过候选数量：`6`
- 干净主候选：
  - `xsmom_vt10_q_momq_round_half_true_broker10_guard`
- 仅保留 paper / 非 incumbent 升级候选：
  - `stage103_plus_oi_confirm63_best1_weekly_guard`
  - `xsmom_vt10_q_momq_round_half_true`
  - `xsmom_vt10_q_momq_short_only_round_half_broker10_guard`
- 已被后续鲁棒性审计降级的候选：
  - `stage103_plus_cffex_index_best1_tsmom60_guard`
  - `stage103_plus_value_proxy756_monthly_guard`
- 分层统计：
  - `failed_active_objective_gate`：`58` 个，最高短持有分 `213.231`
  - `paper_only_not_incumbent_upgrade`：`3` 个，最高短持有分 `151.171`
  - `downgraded_by_later_robustness`：`2` 个，最高短持有分 `198.273`
  - `current_main_execution_relative_candidate`：`1` 个，短持有分 `128.490`
  - `baseline`：`1` 个
- 关键反直觉点：
  - 最高短持有分不是可晋级版本，而是 `activation_linear_6m_33`，短持有分 `213.231`，但它损害 3个月/6个月中位收益和低增长率，因此已在 Stage120 停止。
  - Stage115 股指 best1 全周期指标非常强，`5364.6659%/-23.5184%/Sharpe1.4810/Ulcer12.0786`，但 Stage116 显示相对 Stage103 任意启动收益胜率弱，剔除最大 `1` 个相对贡献日后总收益低于 Stage103，因此不能继续晋级。
  - Stage125 OI best1 通过 Stage079 原始目标，`5128.7927%/-26.8963%/Sharpe1.4092/Ulcer13.5225`，但相对 Stage103 的 `90/180/252/504` 日收益胜率仅 `45.3849%/36.1333%/32.2972%/30.4372%`，且 `5x` 成本略劣于 Stage103，因此只保留 paper 线索。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage426_active_objective_promotion_audit_report_stage426_active_objective_promotion_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage426_active_objective_promotion_audit_candidate_table_stage426_active_objective_promotion_audit_v1.csv`
- tier summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage426_active_objective_promotion_audit_tier_summary_stage426_active_objective_promotion_audit_v1.csv`
- top candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage426_active_objective_promotion_audit_top_candidates_stage426_active_objective_promotion_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage426_active_objective_promotion_audit_decision_stage426_active_objective_promotion_audit_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage426_active_objective_promotion_audit_chart_stage426_active_objective_promotion_audit_v1.png`
- orders：不适用。
- daily：不适用。
- quality：不适用。

## 结论

- 本阶段结论：当前仍保留 Stage103 `xsmom_vt10_q_momq_round_half_true_broker10_guard` 为唯一干净主执行相对候选。
- 是否进入下一步：进入，但不是继续救已降级路线。
- 下一步：
  - 固定 Stage103 做工程化复跑、paper/影子盘、真实券商保证金接入。
  - 若继续追求理想 3个月/6个月体验，只能测试全新低自由度、低相关、样本更充分、保证金更轻的风险源；不得继续扫股指、OI、value、商品动量、分批启动等已降级路线的小参数。

## 过拟合反思

- 运行前判断：不是过拟合。原因是本阶段只审计已冻结候选，不新增规则或参数。
- 运行后判断：不是过拟合；它反而降低过拟合风险。
- 原因：
  - 多候选回测天然存在选择偏差，最高短持有分并不等于未来更稳。
  - 本阶段把“目标通过”“相对 incumbent 升级”“后续审计是否降级”拆开，避免用单一漂亮指标替代稳健性判断。
  - 若继续为了让 Stage115、value756、OI best1 通过单个失败项而调日期、窗口、阈值、品种或保证金小数，就会转为过拟合。

## 继续价值反思

- 运行前判断：有价值。原因是 Stage103 之后候选很多，必须统一晋级口径，否则会在多个好看但不稳的版本中反复摇摆。
- 运行后判断：继续做有价值，但方向要收束。
- 原因：
  - Stage103 已经是清晰可执行的下一阶段主候选，值得进入工程化和 paper/影子盘。
  - 已降级路线继续主动优化价值低；继续挖新风险源仍有价值，但必须从“能穿越周期”的结构先验出发，而不是从历史坏窗口补丁出发。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage126 执行约束和阶段记录。
- 是否更新 `research/registry.md`：是，更新当前研究线状态与最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：是。该阶段是重要候选晋级口径结论，应进入总账。
