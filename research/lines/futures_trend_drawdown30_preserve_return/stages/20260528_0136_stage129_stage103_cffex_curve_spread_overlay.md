# Stage129 - Stage103 中金所 TF/T 曲线价差 Overlay 审计

- 时间：2026-05-28 01:36 CST。
- 研究线：`futures_trend_drawdown30_preserve_return`。
- 阶段性质：A/C 固定低自由度独立风险源审计；不修改 C3、Stage079、Stage103 交易规则，不新增账户资金。
- 是否重要突破：否。重要反证：TF/T 曲线中性均值回归没有提供相对 Stage103 的稳定增量。
- 是否触发 A/B：是。A=Stage079；C0=Stage103；C1=Stage103 + 中金所国债 TF/T 曲线价差 MR120 overlay。

## 调研和判断

- 外部调研结论：CME/TradeStation 等资料显示，国债期货曲线价差/相对价值交易是成熟范式，核心是用不同期限合约表达曲线形状变化，并注意 DV01/hedge ratio。这个先验支持测试“利率曲线价差”作为商品趋势之外的低相关风险源。
- 本阶段没有按结果搜索比例或阈值，只固定 `TF:T=2:1`、`LOOKBACK_DAYS=120`、`ENTRY_Z=1.0`、`BROKER10_MULTIPLIER=1.10`。
- 开始前过拟合反思：否。原因是结构来自利率曲线相对价值先验，不是从本地坏窗口倒推。
- 开始前继续价值反思：有。原因是它和商品趋势/xsmom 的收益来源不同，若能过 Stage103 闸门，理论上更有穿越周期价值。

## 版本变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage429_stage103_cffex_curve_spread_overlay.py`。
- 新增参数：`LOOKBACK_DAYS=120`、`ENTRY_Z=1.0`、`TF:T=2:1`、`BROKER10_MULTIPLIER=1.10`。
- 修改参数：无。
- 删除参数：无。
- 修改正式策略默认：无。

## 核心结果

| version | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 总滑点 | 总交易次数 | 日胜率 | 非零日胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 | 31,040,650 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 1,556,750 | 757 | 36.2924% | 48.3478% |
| Stage103 | 31,730,915 | 5059.4984% | -28.9792% | 1.3681 | 14.3132 | 1,569,265 | 1,217 | 43.0809% | 50.3432% |
| Stage103 + TF/T curve MR120 | 31,722,165 | 5058.0756% | -28.9835% | 1.3667 | 14.3238 | 1,594,865 | 1,729 | 46.8016% | 50.2101% |

- 新增 TF/T overlay 净 PnL：`-8,750`。
- 新增 overlay 滑点：`25,600`。
- 新增 overlay 换手：`512` 手。

## 3个月/6个月体验

| version | horizon | p05收益 | 中位收益 | 正收益率 | 年化低于5%率 | 最差窗口回撤 | Ulcer p95 | 体验分 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 | 90d | -11.4702% | 13.5434% | 73.4804% | 29.4012% | -29.1988% | 17.7786 | 100.0000 |
| Stage103 | 90d | -10.9102% | 13.4787% | 74.6961% | 27.9604% | -28.9792% | 16.4708 | 121.2041 |
| Stage103 + TF/T | 90d | -10.9874% | 13.4787% | 74.6511% | 28.0504% | -28.9835% | 16.5798 | 119.9354 |
| Stage079 | 180d | -2.0393% | 33.9947% | 93.4772% | 9.0099% | -29.7007% | 19.9011 | 100.0000 |
| Stage103 | 180d | -0.6313% | 35.8014% | 94.3688% | 8.4467% | -28.9792% | 19.1255 | 134.4513 |
| Stage103 + TF/T | 180d | -0.7635% | 35.9352% | 94.1342% | 8.4467% | -28.9835% | 19.1578 | 129.6376 |

## 决策

- 决策：`no_new_promotion`。
- 相对 Stage079：全周期硬闸门通过。
- 相对 Stage103：总收益、最大回撤、Sharpe、Ulcer、成本压力和部分 broker10 保证金窗口均未过增量闸门。
- 判断：TF/T 曲线价差方向有理论价值，但当前固定 `2TF:1T`、120日均值回归在本地样本中只是增加成本和保证金占用，没有带来足够收益或短持有改善。
- 后续规划：本形状停止；不继续扫 TF/T 比例、z-score 阈值、lookback、TS/TL 组合、方向过滤、日期或保证金小数。

## 输出

- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage429_stage103_cffex_curve_spread_overlay_report_stage429_stage103_cffex_curve_spread_overlay_v1.md`
- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage429_stage103_cffex_curve_spread_overlay_chart_stage429_stage103_cffex_curve_spread_overlay_v1.png`
- 决策 JSON：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage429_stage103_cffex_curve_spread_overlay_decision_stage429_stage103_cffex_curve_spread_overlay_v1.json`

## 反思

- 运行后过拟合反思：不是过拟合。原因是候选失败后停止，没有继续挑比例、窗口或阈值。
- 运行后继续价值反思：本子路线主动优化价值低；利率曲线相对价值作为大类仍可保留经验，但在当前资金、整数手、保证金口径下不应继续救这个形状。总目标仍有价值，但现实上 Stage103 已是当前最干净主执行相对候选。
