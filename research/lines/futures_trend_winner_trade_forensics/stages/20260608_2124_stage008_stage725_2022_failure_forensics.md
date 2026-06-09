# Stage008 - Stage725 2022-2023失败归因

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：`day`
- 记录时间：`2026-06-08 21:24 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage725 失败窗口逐笔法证；只读归因，不作为正式候选。
- 是否重要突破：否，关键边界修正。
- 是否触发A/B：否。本阶段不是可接正式版的新策略，只是解释 Stage725 为什么在 2022-2023 失败。

## 外部调研与判断

- 参考资料：
  - Meta-labeling 概念：`https://en.wikipedia.org/wiki/Meta-Labeling`
  - regime filter 概念参考：`https://www.darwintiq.com/articles/what-is-a-regime-filter`
  - 趋势跟随回测参考仓库：`https://github.com/trustdan/trend-following-backtesting-strategies`
- 我的判断：外部资料支持“先固定主策略，再用上下文/状态过滤机会”的研究纪律，但不能直接复制成我们组合里的豁免规则。Stage725 的失败必须先做实现与路径归因，避免把实现结构偏差误判成特征失败。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage726_stage725_2022_failure_forensics.py`
- 修改脚本：无正式配置修改。
- 删除脚本：无。
- 新增参数：
  - `ANALYSIS_START=2022-01-01`
  - `ANALYSIS_END=2023-12-31`
  - 对照 A：`stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
  - 候选 C：`stage526_200k_force95_to80_drawdown_gated_directional_edge60_exemption_stage725`
- 修改参数：无正式参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2022-01-01` 至 `2023-12-31`
- 账户规模：`200,000`
- 成本口径：复用 Stage725 官方回测成本。
- 样本过滤：只取 Stage725 硬失败窗口 `phase_2022_2023`，不按品种、方向或单一盈利窗口筛选。
- 策略/归因口径：重跑 A/C 并导出 `closed_lots`、`entry_risk`、`entry_candidates`、`recovery_lots`、`product_signal_summary`。

## 结果

### Stage725窗口指标

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A 正式 recovery sleeve | 200,595 | 0.2975% | -28.0550% | 0.1053 | 4,150 | 78 | 49.1620% |
| C Stage725 | 135,540 | -32.2300% | -32.2300% | -2.0381 | 1,400 | 34 | 22.7273% |

### 逐笔法证

| 版本 | closed lots | realized PnL | avg R | closed lot胜率 | recovery lots | recovery PnL | risk_floor lots | risk_floor PnL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A 正式 recovery sleeve | 39 | 4,745 | -0.1380 | 30.7692% | 8 | -5,680 | 0 | 0 |
| C Stage725 | 17 | -63,060 | -1.1437 | 5.8824% | 0 | 0 | 7 | -1,160 |

- `candidate_recovery_lot_count=0`
- `base_recovery_lot_count=8`
- `closed_lot_delta_vs_base=-22`
- `official_sleeve_removed=True`
- `selector_training_viable=False`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage726_stage725_2022_failure_forensics_report_stage726_stage725_2022_failure_forensics_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage726_stage725_2022_failure_forensics_summary_stage726_stage725_2022_failure_forensics_v1.csv`
- entry_risk：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage726_stage725_2022_failure_forensics_entry_risk_stage726_stage725_2022_failure_forensics_v1.csv`
- entry_candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage726_stage725_2022_failure_forensics_entry_candidates_stage726_stage725_2022_failure_forensics_v1.csv`
- closed_lots：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage726_stage725_2022_failure_forensics_closed_lots_stage726_stage725_2022_failure_forensics_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage726_stage725_2022_failure_forensics_decision_stage726_stage725_2022_failure_forensics_v1.json`

## 结论

- 本阶段结论：`stage725_failure_forensics_official_sleeve_removed`。
- Stage725 在 2022-2023 的失败不能简单归因为 `directional_edge60 + DD<=5%` 放大的高质量机会亏损。
- 更关键的问题是：C 为了恢复正常风险 sizing，关闭了当前正式版的一手 `recovery_sleeve`，导致正式版在 2022-2023 仍能参与的恢复仓结构被移除。
- 因此，Stage725 不能作为“高质量机会豁免失败/成功”的干净证据；它混入了“官方 sleeve 被移除”的结构差异。

## 过拟合反思

- 运行前判断：否。它是失败归因，不是新参数拟合。
- 运行后判断：否，但如果继续用 2022-2023 结果倒推新规则，会变成过拟合。
- 原因：本阶段只解释已有失败，不按结果调品种、年份、阈值或方向。

## 继续价值反思

- 运行前判断：有价值。否则会把 Stage725 的结构问题误判成特征问题。
- 运行后判断：有价值，但下一步只能验证一个更干净的问题：保留官方 sleeve，只允许官方 recovery setup 在预声明高质量条件下绕过一手限制。
- 原因：只有先保持正式 sleeve 不变，才能判断正常风险豁免本身是否有独立价值。

## 后续规划

- 不再基于 Stage725 直接推广 `directional_edge60 + DD<=5%`。
- 下一步做 Stage727：保留官方 `recovery_sleeve`，只在官方 `long_case1a/short_case1a` recovery setup 满足 `directional_edge60 + DD<=5%` 时允许正常风险 sizing。
