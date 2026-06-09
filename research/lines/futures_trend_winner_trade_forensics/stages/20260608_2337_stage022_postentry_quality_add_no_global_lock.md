# Stage022 - 入场后确认仓解耦全局锁盈复验

- 时间：2026-06-08 23:37 CST
- 研究线：`futures_trend_winner_trade_forensics`
- 是否重要突破版本：否，属于机制归因后的二次反证。
- 决策：`postentry_quality_add_no_global_lock_still_not_promoted`

## 调研与判断

- 外部/GitHub 调研结论：趋势跟随加仓需要把“加仓风险管理”和“原主仓趋势退出”区分开，不能因为早期确认仓就过早切断主仓右尾。
- 本次判断：Stage738 的失败有明确工程机制原因，因此只做一个结构性修正：确认仓不再触发原有成熟加仓的全局锁盈。没有调特征阈值、倍数、窗口、品种或年份。

## 版本改动

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage739_postentry_quality_add_no_global_lock.py`
- 修改策略：`examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 新增参数：
  - `post_entry_quality_add_triggers_add_profit_lock=False`
- 修改参数：
  - Stage738 脚本显式固定 `post_entry_quality_add_triggers_add_profit_lock=True`，保证 Stage738 结果可复现。
  - Stage739 候选固定 `post_entry_quality_add_triggers_add_profit_lock=False`。
- 删除参数：无。

## A/C 定义

- A：当前正式 Stage372/20万 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
- C1：A + `post1_body60_ratio_ge50` 确认仓，手数 `floor(base_volume * 0.5)`，不触发全局加仓锁盈
- C2：A + `post1_avg_directional_close_strength_ge60` 确认仓，手数 `floor(base_volume * 0.5)`，不触发全局加仓锁盈

## 回测结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 确认仓信号 | 不足一手 | 实际确认仓 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A 正式 | 8,728,285 | 4264.1425% | -38.6713% | 1.6279 | 506,220 | 633 | 52.2586% | 0 | 0 | 0 |
| C1 body60 no-lock | 3,497,200 | 1648.6000% | -37.6890% | 1.3795 | 266,830 | 698 | 52.1622% | 75 | 6 | 51 |
| C2 dirclose no-lock | 3,818,270 | 1809.1350% | -40.8531% | 1.3430 | 330,120 | 739 | 52.0963% | 130 | 14 | 82 |

## 多起点要点

- 解耦后相对 Stage738 明显改善：C1 期末权益从 `1,880,045` 提升到 `3,497,200`；C2 从 `721,720` 提升到 `3,818,270`。
- 但二者仍远低于正式 A：C1 全周期收益保留 `38.6619%`，C2 `42.4267%`。
- C1 `since_2022` 收益保留 `28.5626%`，C2 `since_2022` 仅 `25.8171%`。
- C2 全周期回撤 `-40.8531%`，比正式版恶化 `-2.1818pp`；`phase_2024_2025` 回撤恶化 `-9.8156pp`。

## 归因

- Stage738 的确有“确认仓触发全局锁盈”的交互问题，Stage739 解耦后收益恢复一部分。
- 但剩余差距仍很大，说明 overlay 的错误不只在全局锁盈：真实确认仓改变了仓位路径、后续止损/强制减仓/复利基数和下一次 sizing，不能用单笔残余 PnL 线性叠加。
- 方向性收盘强 C2 触发更多，真实成交 `82` 次，但并没有带来更稳定收益，说明该特征更像“趋势已快速展开后的可解释标签”，不是可直接交易化加仓规则。

## 过拟合反思

- 运行前：否。只做一处机制解耦，不调整阈值和倍数。
- 运行后：如果继续通过“只给某些年份/品种/方向触发、放宽/收紧 post1 阈值、改 0.5x 到其他小数”救结果，将明显过拟合。

## 继续价值

- 本真实加仓路线当前不值得继续接正式版。
- 仍有只读法证价值：入场后早期顺畅 K 线可作为“交易复盘标签/forward watch”，但不能作为所有交易放大风险或确认仓规则。
- 下一步不建议继续真实加仓；若沿本目标继续，只能转向非交易型标签、退出/持有质量解释，或等待 OOS forward 样本。

## 输出

- 合并图：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage739_stage738_combined_postentry_quality_add_full_equity.png`
- 图：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage739_postentry_quality_add_no_global_lock_chart_stage739_postentry_quality_add_no_global_lock_v1.png`
- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage739_postentry_quality_add_no_global_lock_report_stage739_postentry_quality_add_no_global_lock_v1.md`
- 决策：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage739_postentry_quality_add_no_global_lock_decision_stage739_postentry_quality_add_no_global_lock_v1.json`
