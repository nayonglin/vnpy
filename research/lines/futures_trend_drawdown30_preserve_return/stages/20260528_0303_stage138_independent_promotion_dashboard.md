# Stage138 - 独立晋级判断看板

- 时间：2026-05-28 03:03 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 工作模式：`day`
- 阶段性质：只读晋级裁决；不新增策略、不改参数、不扫窗口、不新增资金。
- 是否重要突破：是。突破不是新收益，而是把 Stage137 后的候选层级重新裁清：Stage103 晋级为当前主执行相对候选，Stage115/Stage136 只保留 paper。
- 是否触发 A/B：否。本阶段没有产生新策略版本，只整合既有固定候选证据。

## 外部调研与判断

- 调研方向：PBO / Deflated Sharpe / PSR、walk-forward、rolling holding、block bootstrap、贡献日剔除。
- 参考资料：
  - Bailey、Borwein、Lopez de Prado、Zhu，《The Probability of Backtest Overfitting》：https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
  - Bailey、Lopez de Prado，《The Deflated Sharpe Ratio》：https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf
  - `pypbo` Python 实现参考：https://github.com/esvhd/pypbo
- 调研结论：多次候选选择后不能只看全样本收益、Sharpe 或单张权益曲线；必须检查任意启动、样本分段、贡献集中、成本和保证金可执行性。
- 本次专业判断：如果不按硬目标机械排序，仍然应该让 Stage103 晋级为主执行相对候选；Stage115 是高分 paper，Stage136 是体验 paper，但两者都不够干净。

## 版本变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage438_independent_promotion_dashboard.py`
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage438_independent_promotion_dashboard_summary_stage438_independent_promotion_dashboard_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage438_independent_promotion_dashboard_rolling_holding_stage438_independent_promotion_dashboard_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage438_independent_promotion_dashboard_pairwise_rolling_stage438_independent_promotion_dashboard_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage438_independent_promotion_dashboard_top_edge_day_ablation_stage438_independent_promotion_dashboard_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage438_independent_promotion_dashboard_leave_one_year_ablation_stage438_independent_promotion_dashboard_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage438_independent_promotion_dashboard_decision_stage438_independent_promotion_dashboard_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage438_independent_promotion_dashboard_report_stage438_independent_promotion_dashboard_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage438_independent_promotion_dashboard_chart_stage438_independent_promotion_dashboard_v1.png`
- 修改正式策略：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。

## 核心结果

| 版本 | 晋级判断 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 3个月分 | 6个月分 | 总滑点 | 总交易次数 | 非零日胜率 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 | baseline_keep | 31,040,650 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 100.0000 | 100.0000 | 1,556,750 | 757 | 48.3478% |
| Stage103 | promote_main_execution_relative_candidate | 31,730,915 | 5059.4984% | -28.9792% | 1.3681 | 14.3132 | 121.2041 | 134.4513 | 1,569,265 | 1,217 | 50.3432% |
| Stage115 | high_score_paper_only | 33,607,695 | 5364.6659% | -23.5184% | 1.4810 | 12.0786 | 183.4601 | 210.3930 | 1,594,705 | 1,719 | 53.8102% |
| Stage136 | paper_only_overfit_warning | 32,120,290 | 5122.8114% | -27.5906% | 1.3918 | 13.9133 | 141.2265 | 144.5203 | 1,576,215 | 1,469 | 50.7671% |

## 任意启动与贡献集中

- Stage103 相对 Stage079 的 `90/180/252/504` 日收益胜率为 `43.0437%/44.2985%/43.6134%/32.0974%`，不是多数窗口收益都更高；但它的最大回撤、Ulcer、成本和保证金证据最干净，因此仍是主执行相对候选。
- Stage115 相对 Stage103 的 `90/180/252/504` 日收益胜率为 `46.0153%/41.3890%/38.4653%/33.5916%`；剔除最大 `1` 个相对贡献日后，相对 Stage103 收益差变为 `-13.4058pp`，且绝对 broker10 仍需额外现金约 `7,137.64`。
- Stage136 相对 Stage103 的 `90/180/252/504` 日收益胜率为 `34.3539%/28.2966%/27.3919%/34.4217%`；剔除最大 `1` 个相对贡献日后，相对 Stage103 收益差 `-55.0864pp`；留一年度最差相对 Stage079 收益差 `-262.4845pp`。

## 决策

- 主执行相对候选：Stage103 `xsmom_vt10_q_momq_round_half_true_broker10_guard`。
- 高分 paper：Stage115 `stage103_plus_cffex_index_best1_tsmom60_guard`，不主晋级。
- paper/体验观察：Stage136 `stage103_plus_low_skew252_best1_vt10_mom63_round_half_guard`，不主晋级。
- Stage079 继续作为当前 baseline。
- 不继续救 Stage115 股指 TSMOM 小参数，不继续救 Stage136 偏度 self-validation 小参数，也不继续做连续失败信号路线。

## 过拟合反思

- 本阶段不是过拟合：没有新增交易规则、没有调参数，只对既有固定路径做统一裁决。
- 如果后续为了让 Stage115 或 Stage136 主晋级而继续改保证金小数、贡献日、年份、偏度窗口、动量窗口或日期过滤，就会转为过拟合。

## 继续价值反思

- 继续做 Stage103 工程化复跑、paper/影子盘和真实券商保证金对账有价值。
- 继续主动研究也有价值，但只能寻找全新、低自由度、样本更分散、保证金更轻的新风险源。
- 继续沿连续失败信号、股指 TSMOM 救参、偏度 self-validation 救参主动优化，价值低。

![Stage138 chart](/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage438_independent_promotion_dashboard_chart_stage438_independent_promotion_dashboard_v1.png)
