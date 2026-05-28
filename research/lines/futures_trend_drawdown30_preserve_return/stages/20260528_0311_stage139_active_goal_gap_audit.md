# Stage139 - 主动目标缺口审计

- 时间：2026-05-28 03:11 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 工作模式：`day`
- 阶段性质：只读目标缺口审计；不新增交易规则、不调参数、不新增资金。
- 是否重要突破：否。重要结论是目标缺口被重新量化：按晋级分数已有多个候选过线，但没有任何候选同时满足 3个月与6个月全部严格目标阈值。
- 是否触发 A/B：否。本阶段只审计既有固定候选。

## 外部调研与判断

- 调研方向：Deflated Sharpe / PSR、PBO、walk-forward validation、商品期货趋势/动量与 open interest。
- 参考资料：
  - Bailey、Lopez de Prado，《The Deflated Sharpe Ratio》：https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf
  - Bailey、Borwein、Lopez de Prado、Zhu，《The Probability of Backtest Overfitting》：https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
  - Clare、Seaton、Smith、Thomas，《Trend Following, Risk Parity and Momentum in Commodity Futures》：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2126813
- 调研结论：趋势、动量与 OI 方向有研究先验，但多候选回测后必须防止选择偏差；晋级不能只看最高分，还要看严格阈值、贡献集中、样本覆盖和后续鲁棒性降级。

## 版本变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage439_active_goal_gap_audit.py`
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage439_active_goal_gap_audit_summary_stage439_active_goal_gap_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage439_active_goal_gap_audit_target_metrics_stage439_active_goal_gap_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage439_active_goal_gap_audit_gap_stage439_active_goal_gap_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage439_active_goal_gap_audit_decision_stage439_active_goal_gap_audit_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage439_active_goal_gap_audit_report_stage439_active_goal_gap_audit_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage439_active_goal_gap_audit_chart_stage439_active_goal_gap_audit_v1.png`
- 修改正式策略：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。

## 核心结果

| 版本 | 当前状态 | 硬约束 | 晋级评分/改善数 | 严格目标全通过 | 总收益 | 最大回撤 | Sharpe | Ulcer | 3个月分 | 6个月分 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 | baseline | 1 | 0 | 0 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 100.0000 | 100.0000 |
| Stage103 | main_candidate | 1 | 1 | 0 | 5059.4984% | -28.9792% | 1.3681 | 14.3132 | 121.2041 | 134.4513 |
| Stage115 | high_score_paper | 1 | 1 | 0 | 5364.6659% | -23.5184% | 1.4810 | 12.0786 | 183.4601 | 210.3930 |
| OI best1 | paper_candidate | 1 | 1 | 0 | 5128.7927% | -26.8963% | 1.4092 | 13.5225 | 146.4538 | 155.0300 |
| OI top3 | hard_fail_fresh_start | 0 | 0 | 0 | 5150.0114% | -26.9944% | 1.4200 | 13.3869 | 155.0160 | 164.4191 |
| Value756 | paper_candidate_sample_gap | 1 | 1 | 0 | 5183.5439% | -28.9792% | 1.3808 | 14.1660 | 130.2395 | 143.3501 |
| Stage136 | paper_overfit_warning | 1 | 1 | 0 | 5122.8114% | -27.5906% | 1.3918 | 13.9133 | 141.2265 | 144.5203 |

## 严格目标缺口

- 严格目标全通过候选：无。
- 按晋级分数和改善数过线候选：Stage103、Stage115、OI best1、Value756、Stage136。
- OI top3 分数高、改善数高，但 `fresh_start_dd30_pass` 失败，因此硬淘汰。
- Stage115 最接近严格目标：3个月仍失败 `return_p05/return_median/positive_rate/below_5_rate/uw_p95`，6个月仅失败 `below_5_rate/uw_p95`；但 Stage116 已显示贡献日和保证金缺口，不可主晋级。
- Stage103 是当前最干净主候选，但严格目标仍失败：3个月失败 `return_p05/return_median/positive_rate/below_5_rate/dd20_rate/ulcer_p95/uw_p95`，6个月失败 `return_p05/positive_rate/below_5_rate/dd20_rate/ulcer_p95/uw_p95`。

## 决策

- 决策标签：`no_strict_full_target_candidate_keep_stage103_main`
- 当前主候选仍为 Stage103 `xsmom_vt10_q_momq_round_half_true_broker10_guard`。
- 当前完整目标尚未完成，不能调用完成。
- 不继续救 Stage115、Stage136、OI/value 的失败小参数。
- 下一步若继续主动研究，只能找全新低自由度风险源，或做 Stage103 工程化/影子盘/真实券商保证金验证。

## 过拟合反思

- 本阶段不是过拟合：只审计冻结候选与冻结目标阈值。
- 继续救已降级候选的单项失败指标会形成过拟合，尤其是按年份、贡献日、保证金小数或窗口去补洞。

## 继续价值反思

- 严格目标尚未完全完成，继续研究仍有价值。
- 下一阶段的价值不在旧路线救参，而在 Stage103 落地验证，或寻找全新、低自由度、保证金轻且样本更分散的风险源。

![Stage139 chart](/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage439_active_goal_gap_audit_chart_stage439_active_goal_gap_audit_v1.png)
