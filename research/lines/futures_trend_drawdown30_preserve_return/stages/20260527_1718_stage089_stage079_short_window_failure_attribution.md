# Stage089 Stage079短窗口失败归因

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-27 17:18 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因；不修改策略、不构造候选。
- 是否重要突破：否，但提供 Stage090 的强线索来源。
- 是否触发A/B：否，本阶段仅诊断 Stage079 的3个月/6个月坏窗口。

## 外部调研与判断

- 参考资料：
  - 趋势跟踪文献普遍强调趋势收益具有路径依赖，短期反转/拥挤后的回撤是持有体验差的主要来源之一。
  - QuantStats / PerformanceAnalytics 一类评价框架提示，仅看全周期收益不够，需要看滚动窗口、回撤深度和水下持续。
- 我的判断：
  - Stage088 已显示“恢复再风险”改善6个月但不改善3个月；因此必须先归因3个月左尾。
  - 本阶段不把最差窗口品种变成黑名单，避免把 `fu/jm/hc` 等局部结果过拟合成永久规则。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage389_stage079_short_window_failure_attribution.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - 归因持有期：`90/180` 自然日。
  - 每个持有期取最差收益窗口前 `10` 个。
  - 对最差前 `5` 个窗口做品种亏损与最大亏损日归因。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-01` 至 `2026-04-30`。
- 账户规模：Stage079 `61.5万`。
- 成本口径：沿用 Stage383/Stage360 既有 C3 日度净盈亏和品种日盈亏。
- 样本过滤：无。
- 策略/归因口径：Stage079 任意起点 `90/180` 日窗口，C3 品种日盈亏归因。

## 结果

- 3个月最差收益窗口：
  - `2022-07-15` 至 `2022-10-13`，收益 `-27.2573%`，期内最大回撤 `-27.2630%`。
  - 启动日 C3 回撤为 `0%`，前20日收益约 `98.3334%`，前60日收益约 `123.0938%`。
  - 主要亏损品种：`fu.SHFE -365,090`、`jm.DCE -205,470`、`au.SHFE -74,000`。
  - 最大亏损日：`2022-07-18`，Stage079 单日净亏 `-932,620`。
- 另一个3个月坏窗口：
  - `2021-05-12` 至 `2021-08-10`，收益 `-23.3534%`，期内最大回撤 `-29.1988%`。
  - 启动日 C3 回撤为 `0%`，前20日收益约 `101.7238%`，前60日收益约 `123.7200%`。
  - 主要亏损品种：`hc.SHFE -130,190`、`SM.CZCE -110,840`、`SA.CZCE -72,380`、`FG.CZCE -58,180`。
- 6个月最差收益窗口：
  - 早期 `2020-01-01` 至 `2020-06-29` 为最差，收益 `-21.9846%`，最大回撤 `-23.1138%`。
  - 2022年7月启动窗口也进入前列：`2022-07-15` 至 `2023-01-11`，收益 `-19.2457%`，最大回撤 `-29.7007%`。
- 状态上下文：
  - 3个月最差5%窗口的启动日 C3 回撤中位数 `-5.8920%`，前20日收益中位数 `13.6766%`，前60日收益中位数 `47.6833%`。
  - 全部3个月窗口的前20日收益中位数仅 `0.3822%`，前60日收益中位数 `6.6863%`。
  - 结论：坏窗口不是典型“深水下启动”，而更像“强趋势暴涨后反转/回吐”。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率：本阶段不重算策略绩效，沿用 Stage079/Stage083。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage389_stage079_short_window_failure_attribution_report_stage389_stage079_short_window_failure_attribution_v1.md`
- worst_windows：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage389_stage079_short_window_failure_attribution_worst_windows_stage389_stage079_short_window_failure_attribution_v1.csv`
- product_attribution：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage389_stage079_short_window_failure_attribution_product_attribution_stage389_stage079_short_window_failure_attribution_v1.csv`
- loss_days：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage389_stage079_short_window_failure_attribution_loss_days_stage389_stage079_short_window_failure_attribution_v1.csv`
- state_context：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage389_stage079_short_window_failure_attribution_state_context_stage389_stage079_short_window_failure_attribution_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage389_stage079_short_window_failure_attribution_decision_stage389_stage079_short_window_failure_attribution_v1.json`

## 结论

- 本阶段结论：`diagnostic_only_no_candidate_generated`
- 是否进入下一步：进入 Stage090 PnL 层诊断，测试“暴涨后冷却”。
- 下一步：验证近高位暴涨状态下短暂降低风险，是否比深水下刹车更能改善3个月/6个月体验。

## 过拟合反思

- 运行前判断：不是过拟合，本阶段只做归因。
- 运行后判断：归因本身不是过拟合，但把最差窗口品种直接黑名单化会过拟合。
- 原因：坏窗口横跨不同年份和品种，真正共性更像权益路径状态，而不是单一品种。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，且线索清晰。
- 原因：它解释了为什么 Stage088 的深回撤恢复再风险只改善6个月、不改善3个月；3个月痛点更接近“暴涨后快速反转”。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，Stage090 若形成强线索再追加。
