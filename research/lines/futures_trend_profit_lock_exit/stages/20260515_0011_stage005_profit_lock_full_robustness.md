# 2026-05-15 00:11 Stage005 盈利锁定 D 候选全稳健性验证

## 基本信息

- 当前模式：`night`
- 所属研究线：`futures_trend_profit_lock_exit`
- 策略基准：Stage78-1 `official_stage78_1_defensive_50w_no_sizing_cap`
- 资金口径：50万
- 是否重要突破：阶段性重要；D 通过全稳健性验证，但尚未通过逐笔集中度审查。

## 新增/修改

- 新增脚本：`examples/portfolio_backtesting/run_qmt_roll_stage275_profit_lock_full_robustness.py`
- 修改正式参数：无。
- 删除参数：无。

## 实验设计

- 只验证 D，不再搜索新参数。
- D：`30%->27% / 20%->18% / 10%->9% / 5%->1.5% / 3%->0.9% / 2%->0.6%`
- 检查维度：
  - 起始年份：2020 到 2026。
  - 季度冷启动：26 个季度起点。
  - 短窗口：63/126/252 交易日。
  - 滑点压力：1x/2x/3x/5x/10x。

## 新增结果

全周期 D：

- 期末权益：`29,979,315`
- 总收益：`5895.86%`
- 最大回撤：`-39.69%`
- Sharpe：`1.2031`
- 总滑点：`2,165,660`
- 总交易次数：`881`
- 胜率：`43.90%`

相对 A：

- 全周期期末权益：`+3,625,380`
- 全周期回撤：`+0.48pp`
- 起始年份胜出：`6/7`
- 起始年份回撤不恶化超过 2pp：`7/7`
- 2026 起点：期末权益 `-6,515`，但最大回撤改善 `+2.48pp`
- 季度冷启动 paired win rate：`75.64%`
- 季度冷启动 dd ok rate：`98.72%`
- 63/126/252 聚合均通过。
- 5x 滑点压力：D-A 期末权益 `+3,192,260`
- 10x 滑点压力：D-A 期末权益 `+2,650,860`

## 过拟合反思

- 运行前判断：仍有过拟合风险。
- 原因：D 是历史数据上筛出来的候选，必须看冷启动和成本压力。
- 运行后判断：Stage275 降低了过拟合疑虑，但没有完全解除。
- 原因：多周期与滑点都通过，但还没证明收益不是少数交易/品种贡献。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，必须进入逐笔归因。
- 原因：D 已经不像纯样本内噪声，但正式替换前要查贡献集中度。

## 输出文件

- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage275_profit_lock_full_robustness_report_stage275_profit_lock_full_robustness_v1.md`
- start_year_comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage275_profit_lock_full_robustness_start_year_comparison_stage275_profit_lock_full_robustness_v1.csv`
- horizon_aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage275_profit_lock_full_robustness_horizon_aggregate_stage275_profit_lock_full_robustness_v1.csv`
- slippage_comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage275_profit_lock_full_robustness_slippage_comparison_stage275_profit_lock_full_robustness_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage275_profit_lock_full_robustness_decision_stage275_profit_lock_full_robustness_v1.json`
