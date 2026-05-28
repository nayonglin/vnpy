# Stage113 现金管理收益前沿审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-27 22:07 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：边界审计；固定 Stage103，不新增交易信号，只评估 11.5 万现金槽位现实收益上限。
- 是否重要突破：否
- 是否触发A/B：否，属于既有候选的现金管理边界审计。

## 外部调研与判断

- 参考资料：
  - Caixin Global：2026-05-12 报道国内最大货币基金 7日年化收益跌破 0.9%。
  - CEIC Yu'e Bao Fund Yield：余额宝货币基金 7日年化长期数据。
  - GitHub `walk-forward-analysis` topic、`fxstr/walk-forward`、`TonyMa1/walk-forward-backtester`：滚动/任意启动验证是比单条全周期曲线更可靠的策略体验审计方式。
- 我的判断：2026年5月现实现金管理收益大概率在约 0.9%-1.2% 附近，2% 已偏乐观；现金槽位可以做低风险微增强，但不能承担修复 3/6 个月理想持有体验的主任务。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage413_cash_sweep_frontier.py`
- 修改脚本：无策略脚本修改；仅修正图表标签为英文，避免字体缺字。
- 删除脚本：无
- 新增参数：
  - 现金年化场景：`0%/0.5%/0.9%/1.0%/1.2%/1.5%/2%/3%/5%`
  - 收益前沿网格：`0%-20%`，步长 `0.25pp`
  - 现实收益上限：`1.2%`
- 修改参数：无交易参数修改。
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30
- 账户规模：61.5万
- 成本口径：复用 Stage403 当前日度 PnL / slippage；Stage103 和现金 sweep 共用 Stage103 成本。
- 样本过滤：`start_2020` 全周期；任意启动 90/180 日窗口。
- 策略/归因口径：`Stage103核心权益 = Stage103权益 - 11.5万现金`，再叠加不同年化现金复利曲线。

## 结果

- Stage079 基准：期末权益 `31,040,650`，总收益 `4947.2602%`，最大回撤 `-29.7007%`，Sharpe `1.3188`，Ulcer `15.0874`，总滑点 `1,556,750`，总交易次数 `757`，胜率 `45.3826%`。
- Stage103：期末权益 `31,730,915`，总收益 `5059.4984%`，最大回撤 `-28.9792%`，Sharpe `1.3681`，Ulcer `14.3132`，3个月/6个月体验分 `121.2041/134.4513`，总滑点约 `1,569,265`，总交易次数约 `1217`。
- 现实上限 `Stage103 + 11.5万现金年化1.2%`：总收益 `5060.9647%`，最大回撤 `-28.9426%`，Sharpe `1.3692`，Ulcer `14.2878`，3个月/6个月体验分 `121.9939/134.8679`。
- 乐观 `Stage103 + 11.5万现金年化2%`：总收益 `5061.9951%`，最大回撤 `-28.9181%`，Sharpe `1.3700`，Ulcer `14.2707`，3个月/6个月体验分 `122.5050/134.9949`。
- 即使把现金收益扫到 `20%` 年化，90日底部5%收益仍只有 `-10.1889%`，90日正收益率 `75.7767%`，180日底部5%收益 `-0.3858%`，仍无法命中理想目标。
- 达标前沿：普通 `target_pass_gate` 从 `0%` 现金收益就已通过；但 `ideal_all_targets`、`90d_p05_gt_minus8`、`90d_positive_ge80`、`180d_p05_gt0` 等关键理想项在 `0%-20%` 年化现金收益内均找不到满足点。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage413_cash_sweep_frontier_report_stage413_cash_sweep_frontier_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage413_cash_sweep_frontier_summary_stage413_cash_sweep_frontier_v1.csv`
- gate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage413_cash_sweep_frontier_gate_stage413_cash_sweep_frontier_v1.csv`
- frontier：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage413_cash_sweep_frontier_frontier_stage413_cash_sweep_frontier_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage413_cash_sweep_frontier_decision_stage413_cash_sweep_frontier_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage413_cash_sweep_frontier_chart_stage413_cash_sweep_frontier_v1.png`

## 结论

- 本阶段结论：`cash_sweep_small_enhancement_not_full_solution`。现实现金 sweep 可作为 Stage103 的低风险小增强，但不值得作为短持有体验优化主候选独立晋级。
- 是否进入下一步：否，不继续扫现金收益率。
- 下一步：转向独立晋级判断，把 Stage103、现金 sweep、股票槽位按可执行性和稳健性重新排序。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：本阶段不改交易规则，不用结果反推收益率；现金收益必须来自外部现实工具。继续扫更高收益率会变成不现实假设。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：现金 sweep 子路线继续价值低；总目标仍有价值。
- 原因：审计证明瓶颈不在现金利息，而在期货权益路径的水下/波动形状。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`，并在 `memory.md` 记录 Stage114 后的晋级判断。
