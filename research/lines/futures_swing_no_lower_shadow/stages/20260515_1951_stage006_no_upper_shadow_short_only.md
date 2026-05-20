# Stage006 无上影线空头镜像回测

- line_id：`futures_swing_no_lower_shadow`
- 当前模式：`day`
- 记录时间：2026-05-15 19:51 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / 当前分支
- 阶段性质：方向镜像/空头-only 回测
- 是否重要突破：否
- 是否触发A/B：否，结果仍为负，不具备候选价值

## 外部调研与判断

- 参考资料：
  - Traders.MBA Marubozu Candlestick Strategy：Bearish Marubozu 定义为开盘在高点、收盘在低点，代表卖方全天控制；入场可用下一根K线或确认，止损常放在形态高点上方。https://traders.mba/support/marubozu-candlestick-strategy/
  - GoCharting Bearish Marubozu：Bearish Marubozu 是无上下影线或极短影线的长阴，可能代表下跌趋势延续或新下跌趋势开始。https://docs.gocharting.com/docs/charting/technical-indicator/candlestick-patterns/bearish-marubozu
  - Ultima Markets Marubozu：Marubozu 本质是 momentum candle；bearish Marubozu 表示卖方持续压制价格，部分策略会等待短暂回撤后延续。https://www.ultimamarkets.com/academy/marubozu-candle-explained-for-traders/
- 我的判断：
  - 用户说“只做空头”后，本阶段先按真正空头镜像测试：连续两天无上影线下跌，而不是拿原上涨无下影线信号反手做空。
  - 反手做空原上涨信号更像衰竭/均值回归策略，机制不同，不能混在本阶段里。
  - 为避免过拟合，本阶段只测 strict 空头形态和两个止损锚点，不加趋势、成交量、品种过滤。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_no_upper_shadow_short_swing_backtest.py`
- 修改脚本：
  - `tests/test_qmt_no_lower_shadow_swing.py`
- 删除脚本：无
- 新增参数：
  - `stop_mode=signal2_high`
  - `stop_mode=two_signal_high`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-01 到 2026-04-30
- 账户规模：500,000
- 风险比例：0.5% * 上日收盘权益
- 成本口径：沿用合约 metadata 中的 `rate`、`slippage`；本次结果中 commission 为 0，slippage 进入现金扣减。
- 样本过滤：eligible 全市场主力映射。
- 策略/归因口径：
  - 信号：连续两根严格 `open == high` 且 `close < open`。
  - 方向：只做空。
  - 入场：第三天主力合约开盘价做空。
  - 首日处理：若未先触发止损，收盘回补一半；一手仓无法减半则保留。
  - 移动止损：剩余仓以前一交易日最高价做只下移止损。
  - 换月：信号两日到入场日切换主力则跳过；持仓中换月按旧合约收盘强平。

## 结果

| 止损锚点 | 候选数 | 开仓数 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 胜率 | 总交易次数 | 总滑点 | 初始止损次数 | 初始止损净损益 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `signal2_high` | 103 | 76 | 453,985 | -9.203% | -9.2030% | -0.9132 | 28.9474% | 192 | 17,400 | 24 | -62,625 |
| `two_signal_high` | 103 | 63 | 476,295 | -4.741% | -5.4858% | -0.6806 | 30.1587% | 168 | 10,130 | 11 | -27,770 |

### 最好组合：`two_signal_high`

- 期末权益：`476,295`
- 总收益：`-4.741%`
- 最大回撤：`-5.4858%`
- Sharpe：`-0.6806`
- 总滑点：`10,130`
- 总交易次数：`168`
- 胜率：`30.1587%`
- 候选数/开仓数：`103` / `63`
- 退出原因：
  - `short_initial_stop`：11 笔，净损益 `-27,770`
  - `short_trailing_stop`：35 笔，净损益 `-4,055`
  - `short_gap_stop`：13 笔，净损益 `1,345`
  - `rollover_forced_exit`：4 笔，净损益 `6,775`
- 年度拆分：
  - 2020：`2,400`
  - 2021：`-7,210`
  - 2022：`8,030`
  - 2023：`-6,185`
  - 2024：`-5,885`
  - 2025：`-9,130`
  - 2026：`-5,725`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_no_upper_shadow_short_swing_stage006_report.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_no_upper_shadow_short_swing_stage006_summary.csv`
- summary_json：`examples/portfolio_backtesting/backtest_outputs/qmt_no_upper_shadow_short_swing_stage006_summary.json`
- best_daily：`examples/portfolio_backtesting/backtest_outputs/qmt_no_upper_shadow_short_swing_stage006_twosignalhigh_daily.csv`
- best_trades：`examples/portfolio_backtesting/backtest_outputs/qmt_no_upper_shadow_short_swing_stage006_twosignalhigh_trades.csv`
- best_candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_no_upper_shadow_short_swing_stage006_twosignalhigh_candidates.csv`
- best_roundtrips：`examples/portfolio_backtesting/backtest_outputs/qmt_no_upper_shadow_short_swing_stage006_twosignalhigh_roundtrips.csv`

## 结论

- 本阶段结论：
  - 空头镜像没有跑出原始边际；`two_signal_high` 虽然显著降低初始止损亏损，但总体仍亏 `-4.741%`，Sharpe 为 `-0.6806`。
  - 两日高点止损与多头 Stage005 的两日低点止损一样，确实比第二根信号K单点止损更合理，但只能降亏，不能让形态转正。
  - 空头 2022 年为正，但 2021、2023、2024、2025、2026 均为负，不能解释为穿越周期的空头 alpha。
  - 最好组合中 `short_trailing_stop` 也为负，说明后续 runner 没有贡献，这比多头 `open + two_signal_low` 更弱。
- 是否进入下一步：不建议继续沿“镜像空头形态”深挖。
- 下一步：
  - 若继续本线，只剩一个机制不同的反事实：原 bullish 无下影线连续上涨后，第三天反手做空，验证“短期衰竭/均值回归”。
  - 但这应视作新假设，不应和当前 Marubozu 动量线混为一谈；若结果仍弱，应停止本线。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但不应继续调参。
- 原因：
  - 本阶段只做预先定义的镜像形态和两个止损锚点；没有根据结果筛品种、年份、趋势或阈值。
  - 结果为负，不存在“因为跑得好而过拟合选择”的问题。
  - 如果下一步为了救空头去筛 2022 年、筛 `rr/fu` 等品种，就会进入明显过拟合。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：镜像空头本身不值得继续。
- 原因：
  - 有价值的地方：它验证了无影线动量假设在多空两侧都缺少稳定独立边际。
  - 不值得继续的地方：最好空头版本比多头 Stage005 最好版本还弱，年度稳定性也差。
  - 人类盘感上，连续两根无上影线下跌常常已经释放了短期卖压，第三天继续追空并不占优，这和结果一致。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录空头镜像被反证。
- 是否更新 `research/registry.md`：是，更新最新阶段与下一步。
- 是否追加根目录 `memory.md/back_log.md`：否，尚非重要突破、正式候选或路线废弃。
