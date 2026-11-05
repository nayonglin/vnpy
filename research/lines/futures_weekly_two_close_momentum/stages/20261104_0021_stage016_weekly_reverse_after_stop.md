# Stage016 周线止损后同日反向开仓

- 研究线 `futures_weekly_two_close_momentum`，时间见文件名（上海时间）。
- 对照为 Stage015 N。候选 O 增加 `--reverse-after-stop`。19 品种、30 万元、2015-01-05 至 2026-11-03。双边均关闭斜率和 MA40，保留固定一手、实体同向、断档后最多加一手、原周线止损、原换月和成本代理。
- 每个交易周末先按持仓合约检查止损。若触发，同一信号日另按普通空仓入场规则，以当日主力实物合约的三根完整周线判断反向。触发条件仍为连续两周收盘变动及最近两根周 K 实体同向。初始止损按新方向取信号周低点（多）或高点（空），新周期独立计量。
- 下一交易日以原开盘成交代理先平旧仓，若旧仓当日平完且反向标的可成交，则再开反向一手。旧仓首个开盘缺失时，撤销该反向信号，原止损继续等待可用开盘。新仓开盘不可成交时仅完成平仓。入场和出场分别记滑点，沿用 N 的固定手数资金口径。
- 设计参考 [TradingView 的仓位反转说明](https://www.tradingview.com/pine-script-docs/concepts/strategies/#reversing-positions)。本研究选择按期货实物合约分别记平仓和开仓，以便审计换月、交易成本及新旧周期。
- 实施顺序为添加组合入口回归样例并观察失败、实现可选的止损后依赖订单、运行 N/O 验证和独立复算。沪铜 2022-07-29 用于验证执行时点。固定规则无择参，用全样本对照检验反手时机的经济价值。

基准指纹

```text
f4f3d37370276fd03759dfa665d99c1f24f3777174ba76d6d405fb3b451d5b63  research/lines/futures_weekly_two_close_momentum/outputs/stage015_N_2015_20261103/SHA256SUMS
8b452e9327991c7a0d28a58124e1497e00f6f60ea1df702c1adf6b7f7c35aeb1  research/lines/futures_weekly_two_close_momentum/outputs/stage015_N_2015_20261103/inputs.json
6a064a252b98a43e1eef68ba0bc461e0c637441f8309d160aef96f7a2d5d4797  research/lines/futures_weekly_two_close_momentum/tools/run_weekly_portfolio.py
584f7835a13ef4af8f3681a25971ebad66cb6081fa8bbd3537d950606203cb28  research/lines/futures_weekly_two_close_momentum/tools/weekly_two_close_momentum.py
```

候选源码指纹

```text
4b9b2070be92d7b0ae5448c359a08d28c2234dc03fbcf3534e245b9c45935fb3  research/lines/futures_weekly_two_close_momentum/tools/run_weekly_portfolio.py
584f7835a13ef4af8f3681a25971ebad66cb6081fa8bbd3537d950606203cb28  research/lines/futures_weekly_two_close_momentum/tools/weekly_two_close_momentum.py
08aa36861ed85257c2e3456045fe8ced58edc2627cfaa792583f1004a31c0aea  research/lines/futures_weekly_two_close_momentum/tools/test_weekly_portfolio_reversal.py
```
