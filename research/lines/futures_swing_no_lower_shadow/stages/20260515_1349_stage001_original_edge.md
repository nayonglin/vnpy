# Stage001 期货无下影线波段原始边际验证

- line_id：`futures_swing_no_lower_shadow`
- 当前模式：day
- 记录时间：2026-05-15 13:49 CST
- 工作区/分支：`master`（用户确认用当前分支）
- 阶段性质：新研究线启动 + 原始边际回测
- 是否重要突破：否
- 是否触发A/B：否，独立新线，暂不接第78正式趋势基准

## 外部调研与判断

- 参考资料：
  - TradingMetrics 对 Marubozu 的说明：该形态表达单边控制，但需要结合环境确认。
  - RobustTrader 对 Marubozu 的说明：孤立 K 线形态容易失效，最好通过回测验证。
  - GitHub 上的 candlestick pattern 代码参考：形态识别可复用 OHLC 规则，但交易逻辑必须单独验证。
- 我的判断：
  - 本策略本质是“连续强势开盘惯性 + 第三天追入”，原始信号值得先测。
  - 本阶段只验证单一形态和固定 0.5% 风险，不加过滤器，因此不是过拟合。
  - 结果为负后不能立刻扫参救结果，应先归因首日打止损是否是结构性问题。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_no_lower_shadow_swing_backtest.py`
  - `tests/test_qmt_no_lower_shadow_swing.py`
- 修改脚本：
  - `research/registry.md`
- 删除脚本：无
- 新增参数：
  - `risk_ratio=0.005`
  - `capital=500000`
  - `max_concurrent_positions=8`
  - `MAX_CAPITAL_USAGE_RATIO=0.90`
  - `MAX_SINGLE_TRADE_CAPITAL_USAGE_RATIO=0.70`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-01 到 2026-04-30
- 账户规模：500,000
- 成本口径：手续费按现有 metadata rate，滑点按现有 metadata slippage
- 样本过滤：`qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv`
- 策略/归因口径：
  - 连续两天按最小跳动取整后 `open == low` 且 `close > open`
  - 第三天开盘开多
  - 初始止损为第二根信号 K 线低点
  - 首日若未先触发止损，收盘减半；一手仓无法减半则保留
  - 剩余仓位用 `max(当前止损, 前一交易日low)` 只上移
  - 信号两日至入场日换月则跳过；持仓中换月按旧合约收盘强平

## 结果

- 期末权益：`463,825`
- 总收益：`-7.2350%`
- 最大回撤：`-13.5818%`
- Sharpe：`-0.4146`
- 总滑点：`21,130`
- 总交易次数：`207`
- 胜率：`23.2558%`
- 候选数：`112`
- 开仓数：`86`
- 其他关键指标：
  - 回合数：`86`
  - `long_initial_stop`：33 笔，净亏 `-80,505`
  - `long_trailing_stop`：42 笔，净赚 `25,250`
  - `rollover_forced_exit`：5 笔，净赚 `17,915`
  - 年度仅 2025 为正收益，2021/2022/2024 明显为负

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_v1_attribution_report.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_v1_statistics.json`
- orders/trades：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_v1_trades.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_v1_daily.csv`
- quality/candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_v1_candidates.csv`
- roundtrips：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_v1_roundtrips.csv`

## 结论

- 本阶段结论：严格无下影线连续两天上涨后第三天开盘追多，原始全市场边际为负。
- 是否进入下一步：谨慎进入归因，不进入参数优化。
- 下一步：
  - 聚焦 `long_initial_stop`，拆开第三天开盘跳空、信号两日实体/振幅、品种流动性、板块状态。
  - 如果首日止损来自普遍追高回落，而非可解释状态变量，则停止本线。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段只有一个形态定义和固定风险比例，没有按结果调参。
  - 负结果本身是有效信息；现在若立刻调整阈值、宽松下影线或加过滤器，才会进入过拟合风险区。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：仍有有限价值，但只限失败归因。
- 原因：
  - 候选 112、开仓 86，样本虽不大但足以说明原始形态没有直接升级价值。
  - `long_initial_stop` 的亏损集中，值得确认是执行假设问题、形态追高问题，还是少数品种/年份导致。

## 合入建议

- 是否更新本线 `LINE.md`：是，已更新。
- 是否更新 `research/registry.md`：是，新增独立研究线索引。
- 是否追加根目录 `memory.md/back_log.md`：否，当前不是重要突破、正式候选或路线废弃，只是新线首轮负结果。
