# Stage105 Stage079反转保护源Scout

- 时间：2026-05-27 20:13 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 阶段性质：结构性保护源 scout；固定 Stage103 `broker10_guard`，测试低频横截面反转能否覆盖 Stage104 发现的“趋势暴涨后反转/长水下恢复”缺口。
- 是否重要突破版本：否。重要反证：简单横截面反转不是合格保护源；横截面动量对照有研究价值但不能晋级。
- 是否触发 A/B/C：是。A=`Stage079`；C0=`Stage103 broker10_guard`；C1=`Stage103+20日横截面反转`；C2=`Stage103+60日横截面反转`；C3=`Stage103+60日横截面动量对照`。
- 本次脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage405_stage079_reversal_protection_scout.py`
- 输出报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage405_stage079_reversal_protection_scout_report_stage405_stage079_reversal_protection_scout_v1.md`
- 输出图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage405_stage079_reversal_protection_scout_chart_stage405_stage079_reversal_protection_scout_v1.png`

## 开始前反思

- 是否在过拟合：否。本阶段预声明 20日反转、60日反转、60日动量对照三个结构，不按坏窗口调月份、品种、阈值或相邻 lookback。
- 是否仍有价值继续做：是。Stage104 已确认剩余短持有痛点来自趋势暴涨后回撤，必须验证是否存在独立保护源，而不是继续救 Stage103 小参数。

## 外部调研与判断

- 参考资料：
  - Miffre and Rallis, *Momentum strategies in commodity futures markets*：https://www.sciencedirect.com/science/article/pii/S037842660700026X
  - Yang, Goncu and Pantelous, *Momentum and Reversal Strategies in Chinese Commodity Futures Markets*：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3069253
  - Liu and Papailias, *Time series reversal in trend-following strategies*：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2971875
  - Thomas, Clare, Seaton and Smith, *Trend Following, Risk Parity and Momentum in Commodity Futures*：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2126813
- 我的判断：
  - 商品期货文献整体更支持动量/趋势是主收益源，简单反转即使存在也常伴随更高成本与回撤风险。
  - 中国商品期货研究提示动量和反转都可能存在，但低频、较长持有才更可能覆盖交易成本。
  - 因此本阶段可以测试反转保护源，但晋级必须同时通过 Stage079 硬指标、Stage103 增量不劣化、成本压力、保证金压力和 Stage104 坏窗口贡献。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage405_stage079_reversal_protection_scout.py`
- 新增参数：
  - `rev20_weekly_min1_guard`：每5个交易日再平衡，买近20日弱者、卖近20日强者，各3个品种，每品种1手。
  - `rev60_weekly_min1_guard`：每5个交易日再平衡，买近60日弱者、卖近60日强者，各3个品种，每品种1手。
  - `mom60_weekly_min1_guard`：每5个交易日再平衡，买近60日强者、卖近60日弱者，各3个品种，每品种1手。
  - 所有 overlay 均叠加 Stage103 `broker10_guard`，且若 C3+xsmom+overlay 保证金按 `1.10` 倍超过上一日权益，则当日跳过 overlay。
- 修改参数：无正式策略默认修改。
- 删除参数：无。

## 回测结果

基准 Stage079：期末权益 `31,040,650`，总收益 `4947.2602%`，最大回撤 `-29.7007%`，Sharpe `1.3188`，Ulcer `15.0874`，总滑点 `1,556,750`，总交易次数 `757`，胜率 `45.3826%`。

Stage103 `broker10_guard`：期末权益 `31,730,915`，总收益 `5059.4984%`，最大回撤 `-28.9792%`，Sharpe `1.3681`，Ulcer `14.3132`，3个月分 `121.2041`，6个月分 `134.4513`，总滑点 `1,569,265`，总交易次数约 `1217`。

20日反转保护：期末权益 `30,854,655`，总收益 `4917.0171%`，最大回撤 `-34.7349%`，Sharpe `1.2951`，Ulcer `15.5870`，3个月分 `87.0336`，6个月分 `72.7247`，Stage104底部5%窗口相对 Stage103：3个月 `-0.6446pp`，6个月 `-1.3512pp`。决策：反证，不晋级。

60日反转保护：期末权益 `30,986,560`，总收益 `4938.4650%`，最大回撤 `-33.9962%`，Sharpe `1.3139`，Ulcer `15.3765`，3个月分 `101.2477`，6个月分 `93.9203`，Stage104底部5%窗口相对 Stage103：3个月 `-0.3654pp`，6个月 `-0.2414pp`。决策：反证，不晋级。

60日动量对照：期末权益 `32,437,815`，总收益 `5174.4415%`，最大回撤 `-27.3580%`，Sharpe `1.4044`，Ulcer `13.4922`，3个月分 `143.2053`，6个月分 `152.0460`，用户目标8项改善 `8/8` 与 `8/8`，Stage104底部5%窗口相对 Stage103：3个月 `+0.3189pp`，6个月 `+0.1357pp`。失败项：`cost_stress_not_worse_than_stage079`、`fresh_start_dd30_pass`；其中 `start_2022` 最大回撤 `-35.3241%`，5倍滑点最大回撤 `-40.9311%`。决策：有研究价值，但不能晋级；进入 Stage106 降换手验证。

## 结论

- `rev20/rev60` 都不能作为保护源：它们没有保护 Stage104 底部坏窗口，且全周期回撤、滚动破30、多起点、成本压力均明显劣化。
- `mom60_weekly` 不是用户原先直觉里的“反转保护”，但数据上更像商品期货文献支持的收益源；它全周期和短持有体验都强于 Stage103。
- `mom60_weekly` 在 `start_2022` 与高滑点下失败，不能作为 Stage079/Stage103 的晋级版本。

## 后续规划和 TODO

1. 停止简单横截面反转保护源，不继续扫 `20/60` 附近 lookback、top_n、再平衡日或坏窗口过滤条件。
2. 允许对 `mom60` 做一次降换手验证：把周频承载改为更低频月度承载，并加入更长期 `120日` 动量对照。
3. 若降换手仍不能通过 `start_2022` 和高滑点压力，则动量承载保留为 paper 研究分支，不再救参数。

## 结束后反思

- 是否在过拟合：不是。失败候选直接反证；没有按结果新增救援条件。
- 是否还有价值继续做：有，但只对动量承载做一次结构性降换手验证；反转保护源本身继续价值低。
