# Stage821 Stage813 20w/30w/50w三资金口径3年滚动窗口回测

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：2026-06-12 14:59
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：资金规模压力测试 / 滚动窗口稳健性验证
- 是否重要突破：否
- 是否触发A/B：是，属于 Stage813 50w、Stage819 30w、Stage817 20w 的资金部署口径对照；不触发正式配置替换

## 外部调研与判断

- 参考资料：
  - Interactive Brokers Campus walk-forward analysis 文章：`https://www.interactivebrokers.com/campus/ibkr-quant-news/the-future-of-backtesting-a-deep-dive-into-walk-forward-analysis/`，滚动窗口能避免单一验证区间带来的虚假信心。
  - vn.py 官方 GitHub README：`https://github.com/vnpy/vnpy/blob/master/README_ENG.md`，组合策略模块支持多合约策略历史回测和自动交易。
- 我的判断：
  - 固定终点到 2026 的年度起点回测会共享后段行情，容易把末端行情收益重复计入多个起点。
  - 3 年滚动窗口更适合检验资金口径是否跨不同市场段稳定，而不是只看长复利终点。
  - 本次只改本金并改变评估窗口，不改 Stage813 信号、选品、仓位和退出逻辑。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage821_stage813_capital_rolling3y.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `MODEL_TAG = stage821_stage813_capital_rolling3y_v1`
  - `ROLL_YEARS = 3`
  - `CAPITALS = 50w / 30w / 20w`
  - `WINDOWS = 2018_2021, 2019_2022, 2020_2023, 2021_2024, 2022_2025, 2023_2026, 2023_06_2026_05`
- 修改参数：
  - 50w：`account_capital/c3_capital = 500000`
  - 30w：`account_capital/c3_capital = 300000`
  - 20w：`account_capital/c3_capital = 200000`
- 删除参数：无
- 保持不变：
  - Stage813 的 `AM41`
  - 基础风险 `0.40`
  - `OI上升+价格沿方向` 命中恢复到 `0.80`
  - 旧正式 AI 选品池
  - `maxpos4`
  - 多头更紧初始止损
  - `RSI95` 半平
  - 关闭连败缩放和 recovery sleeve
- 正式配置/CTP/下单：不改官方配置、不连接 CTP、不调用下单。

## 回测/归因参数

- 窗口口径：
  - `2018-01-01 -> 2020-12-31`
  - `2019-01-01 -> 2021-12-31`
  - `2020-01-01 -> 2022-12-31`
  - `2021-01-01 -> 2023-12-31`
  - `2022-01-01 -> 2024-12-31`
  - `2023-01-01 -> 2025-12-31`
  - `2023-06-01 -> 2026-05-29`
- 账户规模：20w、30w、50w。
- 成本口径：沿用 Stage813 / QMT roll 组合回测成本口径，按脚本输出累计滑点。
- 样本过滤：三资金口径均跑同一批 `7` 个窗口，共 `21` 次回测。
- 策略/归因口径：Stage813 逻辑不变，只比较资金口径在滚动窗口中的收益、回撤、Sharpe、保证金和曲线路径。

## 结果

### 聚合结果

| 资金口径 | 正收益窗口 | 中位收益 | 最小收益 | 最大收益 | 中位回撤 | 最差回撤 | DD30失败 | DD40失败 | DD50失败 | 中位Sharpe | 总滑点 | 总交易次数 | 胜率/生存 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 20w | 7/7 | 171.3700% | 42.5425% | 1593.0575% | -31.5065% | -43.8305% | 5 | 3 | 0 | 1.2192 | 527,650 | 1,706 | 无broker100/无权益跌破0 |
| 30w | 7/7 | 352.8550% | 97.9583% | 1885.8950% | -32.8556% | -44.6223% | 5 | 2 | 0 | 1.6721 | 917,790 | 1,743 | 无broker100/无权益跌破0 |
| 50w | 7/7 | 146.5920% | 65.1840% | 2194.5210% | -32.5478% | -56.0975% | 5 | 2 | 1 | 1.2779 | 1,630,140 | 1,753 | 无broker100/无权益跌破0 |

### 窗口明细

| 窗口 | 50w收益/回撤/Sharpe | 30w收益/回撤/Sharpe | 20w收益/回撤/Sharpe | 收益赢家 | 回撤赢家 | Sharpe赢家 |
|---|---:|---:|---:|---|---|---|
| 2018_2021 | 146.5920% / -23.8078% / 1.2779 | 352.8550% / -32.8556% / 1.6879 | 104.1950% / -30.3319% / 0.9629 | 30w | 50w | 30w |
| 2019_2022 | 2194.5210% / -32.5478% / 2.2754 | 1885.8950% / -31.9143% / 2.2453 | 1411.8650% / -31.5065% / 2.1133 | 50w | 20w | 50w |
| 2020_2023 | 1648.0560% / -56.0975% / 1.8849 | 1718.8467% / -44.6223% / 1.9387 | 1593.0575% / -43.8305% / 1.9444 | 30w | 20w | 20w |
| 2021_2024 | 978.0710% / -42.9311% / 1.7260 | 866.9933% / -42.8163% / 1.6721 | 870.1625% / -41.6131% / 1.7215 | 50w | 20w | 50w |
| 2022_2025 | 102.1750% / -33.6344% / 0.8600 | 97.9583% / -37.8438% / 0.8349 | 42.5425% / -40.0867% / 0.5273 | 50w | 50w | 50w |
| 2023_2026 | 82.2610% / -28.6321% / 0.9319 | 223.6083% / -25.9209% / 1.3670 | 171.3700% / -28.2390% / 1.2192 | 30w | 30w | 30w |
| 2023_06_2026_05 | 65.1840% / -30.1523% / 0.7950 | 173.5483% / -25.2356% / 1.2205 | 143.3550% / -23.2963% / 1.0882 | 30w | 20w | 30w |

### 配对统计

- 30w vs 50w：收益胜出 `4/7`，回撤胜出 `5/7`，Sharpe胜出 `4/7`，收益+回撤双胜 `3/7`；中位收益差 `+70.7907pp`，中位回撤差 `+0.6334pp`，中位Sharpe差 `+0.0538`。
- 20w vs 50w：收益胜出 `2/7`，回撤胜出 `5/7`，Sharpe胜出 `3/7`，收益+回撤双胜 `2/7`；中位收益差 `-54.9985pp`，中位回撤差 `+1.0413pp`，中位Sharpe差 `-0.0045`。
- 30w vs 20w：收益胜出 `6/7`，回撤胜出 `2/7`，Sharpe胜出 `5/7`，收益+回撤双胜 `2/7`；中位收益差 `+55.4158pp`，中位回撤差 `-0.7917pp`，中位Sharpe差 `+0.1324`。

## 输出文件

- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage821_stage813_capital_rolling3y_summary_stage821_stage813_capital_rolling3y_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage821_stage813_capital_rolling3y_curves_stage821_stage813_capital_rolling3y_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage821_stage813_capital_rolling3y_comparison_stage821_stage813_capital_rolling3y_v1.csv`
- pairwise：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage821_stage813_capital_rolling3y_pairwise_stage821_stage813_capital_rolling3y_v1.csv`
- aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage821_stage813_capital_rolling3y_aggregate_stage821_stage813_capital_rolling3y_v1.csv`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage821_stage813_capital_rolling3y_report_stage821_stage813_capital_rolling3y_v1.md`
- absolute_curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage821_stage813_capital_rolling3y_absolute_curves_stage821_stage813_capital_rolling3y_v1.png`
- normalized_curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage821_stage813_capital_rolling3y_normalized_curves_stage821_stage813_capital_rolling3y_v1.png`

## 结论

- 本阶段结论：`stage821_30w_watch_not_promoted`。
- 是否进入下一步：30w 可保留为观察臂，但不升级正式候选，不改变当前实盘默认。
- 核心理由：
  - 30w 在滚动窗口里比固定终点验证更有说服力：收益胜出 50w `4/7`，回撤胜出 `5/7`，Sharpe 胜出 `4/7`，且 DD50 从 50w 的 `1` 个降为 `0`。
  - 30w 相对 20w 的收益和 Sharpe 优势明显，但回撤只赢 `2/7`，说明 30w 是更高效的资金颗粒度，不是更强的防守结构。
  - 50w 在 `2019_2022`、`2021_2024`、`2022_2025` 仍胜出，不能说 30w 全局支配。
- 下一步：
  - 不继续扫 `25w/28w/32w/35w`。
  - 若继续，应做 `2020_2023` 和 `2022_2025` 两个关键窗口的逐笔/品种/保证金归因：前者验证 50w DD50 的来源，后者验证 30w/20w 在弱窗口中是否只是少做少错。

## 过拟合反思

- 运行前判断：不是过拟合；窗口和资金臂预先固定，且只是外生资金口径压力测试。
- 运行后判断：仍不是过拟合；没有据结果修改交易规则或继续扫本金。
- 原因：rolling 3y 是更严格的稳健性验证，但若根据赢家窗口继续调本金小数或窗口边界，会转为过拟合。

## 继续价值反思

- 运行前判断：有价值；固定到 2026 的年度起点可能共享末端行情，滚动窗口可以验证各资金口径在不同市场段是否稳定。
- 运行后判断：有价值且结论更清楚；30w 的效率优势存在，但并非全局支配，也没有解决趋势策略深回撤本质。
- 原因：本次把资本颗粒度效应和市场段效应分开了一层；继续价值应转向风险归因和 Stage372 20w 公平对照，而不是继续资金数值搜索。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，Stage821 不是正式候选替换。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 摘要；不更新 `memory.md`。
