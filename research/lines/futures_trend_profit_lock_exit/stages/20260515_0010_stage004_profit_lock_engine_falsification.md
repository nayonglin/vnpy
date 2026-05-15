# 2026-05-15 00:10 Stage004 盈利锁定候选组合引擎反证

## 基本信息

- 当前模式：`night`
- 所属研究线：`futures_trend_profit_lock_exit`
- 策略基准：Stage78-1 `official_stage78_1_defensive_50w_no_sizing_cap`
- 资金口径：50万
- 是否重要突破：阶段性重要；发现 D 候选通过 engine gate。

## 新增/修改

- 新增脚本：`examples/portfolio_backtesting/run_qmt_roll_stage274_profit_lock_engine_falsification.py`
- 修改正式参数：无。
- 删除参数：无。

## 实验设计

- A：Stage78-1 当前正式锁盈层。
- C：Stage273 事件级 robust-best `scale_current_1.65`。
- D：两段式候选 `low retain 30% / high retain 90%`，即 `30%->27% / 20%->18% / 10%->9% / 5%->1.5% / 3%->0.9% / 2%->0.6%`。
- 窗口：`full_2020_2026`、`since_2022`、`since_2025`、`since_2026`、`stage269_aug_nov_2025`、`stage131_q2022_4_proxy_252d`。

## 新增结果

A 全周期：

- 期末权益：`26,353,935`
- 总收益：`5170.79%`
- 最大回撤：`-40.17%`
- Sharpe：`1.1374`
- 总滑点：`2,057,380`
- 总交易次数：`883`
- 胜率：`43.36%`

C 全周期：

- 期末权益：`31,736,530`
- 总收益：`6247.31%`
- 最大回撤：`-46.03%`
- Sharpe：`1.2662`
- 总滑点：`2,151,340`
- 总交易次数：`879`
- 胜率：`43.78%`
- 结论：收益提升但回撤恶化 `-5.86pp`，拒绝，不晋级。

D 全周期：

- 期末权益：`29,979,315`
- 总收益：`5895.86%`
- 最大回撤：`-39.69%`
- Sharpe：`1.2031`
- 总滑点：`2,165,660`
- 总交易次数：`881`
- 胜率：`43.90%`
- 相对 A：期末权益 `+3,625,380`，回撤改善 `+0.48pp`，Sharpe `+0.0656`。
- 结论：D 通过 engine gate，进入 Stage275。

## 过拟合反思

- 运行前判断：存在过拟合风险。
- 原因：Stage273 的事件级候选来自历史交易路径。
- 运行后判断：C 被反证，D 仍可能过拟合但值得继续。
- 原因：D 不是事件级最高收益点，而是更低自由度、更保守的两段式结构，并通过多个引擎窗口。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：D 在组合引擎里改善收益且没有放大最大回撤，需要继续做起始年份、季度冷启动和滑点压力。

## 输出文件

- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage274_profit_lock_engine_falsification_report_stage274_profit_lock_engine_falsification_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage274_profit_lock_engine_falsification_summary_stage274_profit_lock_engine_falsification_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage274_profit_lock_engine_falsification_comparison_stage274_profit_lock_engine_falsification_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage274_profit_lock_engine_falsification_decision_stage274_profit_lock_engine_falsification_v1.json`
