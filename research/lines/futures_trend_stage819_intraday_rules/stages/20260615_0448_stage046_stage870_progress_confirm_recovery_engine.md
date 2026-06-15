# Stage046 Stage870 progress-confirm recovery 真实引擎

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-15 04:48 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：研究线内冻结 A/C 真实组合引擎验证；只比较 Stage830 C4、Stage847 C9、Stage870 C13；不改 Stage372 官方正式版，不改 Stage819 官方候选配置，不连接 CTP，不调用下单。
- 是否重要突破：否
- 是否触发A/B：否，`formal_ab_triggered=false`，C13 不满足正式候选或 A/B 前置条件。

## 外部调研与判断

- 参考资料：
  - vn.py GitHub：https://github.com/vnpy/vnpy
  - Backtrader order execution docs：https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/
  - Backtrader stop/bracket examples：https://www.backtrader.com/blog/posts/2018-02-01-stop-trading/stop-trading/
- 我的判断：
  - Stage868/869 已经说明 reclaim、close-confirm、retry_failed 这些 stop/retry 标签本身不够。要继续，只能让价格先证明趋势恢复，而不是仅仅回到原入场附近。
  - 本阶段把“趋势恢复证明”冻结为唯一形状：首次 `0.5R` 失败先退出；之后同日只有触及原入场方向的 `+0.5R progress` 才允许重开；重开后若回到原入场价立刻止损。
  - 这不是 AI，不用未来标签，也不扫窗口/R/品种/方向/年份；但如果它不能同时改善收益、回撤、Sharpe 与 broker10，就说明这一结构仍不是可用策略。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage870_stage847_progress_confirm_recovery_engine.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `enable_stage870_progress_confirm_recovery`
- 修改参数：
  - C9 的重入语义从“重回原入场价即重开，止损仍在原 0.5R stop”改为“触及原入场方向 `+0.5R progress` 才重开，重开后止损在原入场价”。
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage847/C9 全周期 `START` 到 `END`。
- 账户规模：沿用 Stage819/Stage830/Stage847 的组合回测口径。
- 成本口径：沿用既有组合回测成本和滑点口径。
- 样本过滤：无年份、品种、方向过滤；不扫描阈值、R、时间窗、品种、方向。
- 策略/归因口径：
  - A：`stage830_stage819_c2_broker10_100_cap`，即 C4。
  - B：`stage847_stage819_c4_05r_stop_retry_once`，即 C9。
  - C：`stage870_stage819_c9_progress_confirm_recovery`，即 C13。
  - C13 规则：首次 `0.5R` adverse stop 不变；若之后触及原入场方向 `+0.5R progress`，在 progress price 合成重开一次；重开后若回到原入场价，立即合成平仓；同一根分钟K保守判定止损优先。

## 结果

| arm | 期末权益 | 相对C4 | 相对C9 | 总收益 | 最大回撤 | 相对C9回撤 | Sharpe | 相对C9 Sharpe | 总滑点 | 总交易次数 | 胜率 | max broker10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C4 `stage830_stage819_c2_broker10_100_cap` | 46,015,805.0 | 0.0 | -4,621,339.6 | 15,238.6017% | -47.1915% | -4.5602pp | 1.5996 | -0.0316 | 3,023,410 | 678 | 53.0630% | 111.4255% |
| C9 `stage847_stage819_c4_05r_stop_retry_once` | 50,637,144.6 | +4,621,339.6 | 0.0 | 16,779.0482% | -42.6313% | 0.0000pp | 1.6312 | 0.0000 | 3,607,030 | 786 | 53.5299% | 114.3987% |
| C13 `stage870_stage819_c9_progress_confirm_recovery` | 46,668,137.3 | +652,332.3 | -3,969,007.3 | 15,456.0458% | -38.7460% | +3.8853pp | 1.5783 | -0.0529 | 3,344,700 | 753 | 53.4070% | 120.7738% |

- 期末权益：C13 `46,668,137.3`，比 C9 少 `3,969,007.3`。
- 总收益：C13 `15,456.0458%`，低于 C9 `16,779.0482%`。
- 最大回撤：C13 `-38.7460%`，比 C9 改善 `+3.8853pp`，这是本阶段唯一强项。
- Sharpe：C13 `1.5783`，低于 C9 `1.6312`，也低于 C4 `1.5996`。
- 总滑点：C13 `3,344,700`，低于 C9 但高于 C4。
- 总交易次数：C13 `753`，低于 C9 `786`，高于 C4 `678`。
- 风险路径：C13 max broker10 `120.7738%`，高于 C9 `114.3987%` 和 C4 `111.4255%`，不满足生存线要求。

### 事件结果

| profile | final_state | events | volume | reentered | retry_failed | median reentry minus entry |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| C9 | `flat_no_reentry` | 70 | 14,095 | 0 | 0 | N/A |
| C9 | `flat_retry_failed` | 25 | 4,795 | 25 | 25 | N/A |
| C9 | `open_after_reentry` | 26 | 5,292 | 26 | 0 | N/A |
| C13 | `flat_no_progress_reentry` | 96 | 17,343 | 0 | 0 | N/A |
| C13 | `flat_progress_reentry_failed` | 16 | 2,994 | 16 | 16 | 7.25 |
| C13 | `open_after_progress_reentry` | 13 | 3,551 | 13 | 0 | 8.00 |

- C13 将 C9 的 `51` 次重入压缩为 `29` 次 progress-confirm 重入，但并没有把剩余重入变成足够高质量的右尾。
- C13 `flat_no_progress_reentry` 增至 `96` 次，说明更严格恢复确认大幅减少了重试；但收益损失过大。
- C13 仍有 `16` 次 progress 重开后回到原入场价止损，atlas 显示“更强确认”后仍存在假突破和快速回撤。

### K线视觉复核

- path chart 已复核：C13 回撤曲线更浅，但权益曲线长期低于 C9，broker10 峰值更高。
- atlas page001 已复核：`rb1805.SHFE short 2018-01-16`、`rb1805.SHFE long 2018-01-30`、`MA809.CZCE long 2018-06-14` 均能看到首次 stop、reclaim、progress reentry 与 recovery fail；这说明规则按预期触发，但 progress 确认仍不能稳定过滤假恢复。
- 人眼结论：`+0.5R progress` 确认太晚，牺牲了 C9 的复利右尾；但它又不够强，不能阻止后续 broker10 压力恶化。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage870_stage847_progress_confirm_recovery_engine_report_stage870_stage847_progress_confirm_recovery_engine_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage870_stage847_progress_confirm_recovery_engine_summary_stage870_stage847_progress_confirm_recovery_engine_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage870_stage847_progress_confirm_recovery_engine_comparison_stage870_stage847_progress_confirm_recovery_engine_v1.csv`
- curve：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage870_stage847_progress_confirm_recovery_engine_curve_stage870_stage847_progress_confirm_recovery_engine_v1.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage870_stage847_progress_confirm_recovery_engine_trades_stage870_stage847_progress_confirm_recovery_engine_v1.csv`
- entry_risk：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage870_stage847_progress_confirm_recovery_engine_entry_risk_stage870_stage847_progress_confirm_recovery_engine_v1.csv`
- entry_candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage870_stage847_progress_confirm_recovery_engine_entry_candidates_stage870_stage847_progress_confirm_recovery_engine_v1.csv`
- trade_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage870_stage847_progress_confirm_recovery_engine_trade_events_stage870_stage847_progress_confirm_recovery_engine_v1.csv`
- intraday_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage870_stage847_progress_confirm_recovery_engine_intraday_events_stage870_stage847_progress_confirm_recovery_engine_v1.csv`
- stop_retry_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage870_stage847_progress_confirm_recovery_engine_stop_retry_events_stage870_stage847_progress_confirm_recovery_engine_v1.csv`
- closed_lots：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage870_stage847_progress_confirm_recovery_engine_closed_lots_stage870_stage847_progress_confirm_recovery_engine_v1.csv`
- event_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage870_stage847_progress_confirm_recovery_engine_event_summary_stage870_stage847_progress_confirm_recovery_engine_v1.csv`
- path_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage870_stage847_progress_confirm_recovery_engine_path_chart_stage870_stage847_progress_confirm_recovery_engine_v1.png`
- atlas_manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage870_stage847_progress_confirm_recovery_engine_atlas_manifest_stage870_stage847_progress_confirm_recovery_engine_v1.csv`
- atlas_pages：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage870_stage847_progress_confirm_recovery_engine_atlas_page001_stage870_stage847_progress_confirm_recovery_engine_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage870_stage847_progress_confirm_recovery_engine_atlas_page002_stage870_stage847_progress_confirm_recovery_engine_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage870_stage847_progress_confirm_recovery_engine_atlas_page003_stage870_stage847_progress_confirm_recovery_engine_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage870_stage847_progress_confirm_recovery_engine_atlas_page004_stage870_stage847_progress_confirm_recovery_engine_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage870_stage847_progress_confirm_recovery_engine_decision_stage870_stage847_progress_confirm_recovery_engine_v1.json`

## 结论

- 本阶段结论：`stage870_progress_confirm_recovery_not_promoted`。
- 是否进入下一步：该 progress-confirm recovery 分支不进入下一步，不进入正式候选，不触发正式 A/B。
- 下一步：
  - 不继续扫 progress R 倍数、recovery stop 位置、确认分钟数、品种、方向或年份。
  - 不再沿 C9 的 stop/retry 重入质量做小变体；Stage868、Stage869、Stage870 已连续反证 reclaim、close-confirm、retry_failed cooldown 与 progress-confirm recovery。
  - 如果继续本线，应转向持仓后组合风险治理，尤其解释为什么 C13 回撤更浅但 broker10 峰值更差；或者寻找完全独立于 stop/retry 标签的新分钟级趋势恢复信号。

## 过拟合反思

- 运行前判断：否。规则是固定的趋势恢复证明，不做参数扫描。
- 运行后判断：本阶段实现本身不是过拟合；但继续调 `+0.5R`、止损位置、确认窗口、品种或年份就是过拟合。
- 原因：失败不是因为 progress 阈值没调好，而是“更严格入场”同时砍掉 C9 的收益和 Sharpe，并把 broker10 峰值推高。继续微调只会在收益、回撤和保证金压力之间来回搬风险。

## 继续价值反思

- 运行前判断：有继续价值。它是 Stage869 后一个真正独立于 reclaim 标签的实时趋势恢复结构。
- 运行后判断：progress-confirm recovery 分支没有继续价值；研究线整体仍有价值，但应换方向。
- 原因：C13 虽把最大回撤从 C9 `-42.6313%` 改善到 `-38.7460%`，但期末权益少 `3,969,007.3`、Sharpe 低 `0.0529`、max broker10 恶化 `+6.3750pp`。这不是可穿越周期的增强。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage046 否决结论，并停止 progress-confirm recovery 分支。
- 是否更新 `research/registry.md`：否，本线归属未变更。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、不是路线合并、不是正式候选、也没有触发正式 A/B。
