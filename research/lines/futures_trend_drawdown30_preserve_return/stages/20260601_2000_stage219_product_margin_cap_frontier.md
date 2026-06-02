# Stage219 单产品保证金上限前沿

- 时间：2026-06-01 20:00 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 阶段性质：A/C 部署层结构实验；不修改 C3/Stage079/Stage103/xsmom alpha。
- 对应脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage519_product_margin_cap_frontier.py`
- 输出报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage519_product_margin_cap_frontier_report_stage519_product_margin_cap_frontier_v1.md`
- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage519_product_margin_cap_frontier_chart_stage519_product_margin_cap_frontier_v1.png`
- 决策：`product_margin_cap_not_ready`

## 外部调研与判断

- 调研参考：managed futures/CTA 组合常用低相关和风险预算控制暴露，但真实部署中交易所/券商保证金、整数手和合约路径才是硬约束。
- 本阶段判断：Stage218 说明超限来自轮换的第一大保证金产品，所以单产品 cap 是比产品黑名单更低自由度、更可解释的结构。

## 本次变更

- 新增参数：把每个产品作为独立风险簇，测试单产品保证金上限 `35%/30%/25%`；另测 `risk_multiplier=0.80 + productcap30`。
- 修改参数：无正式策略参数修改；脚本中通过既有风险簇 cap 机制临时定义产品簇。
- 删除参数：无。
- 新增结果：summary、cost stress、window metrics、rolling holding、exact margin daily/events、product events、decision、report、chart。
- 修改结果：无。
- 删除结果：无。

## 核心结果

硬通过定义为 `DD40 + broker10<=100 + 2x成本DD40`。本阶段无硬通过版本。

| 版本 | 期末权益 | 总收益 | 收益保留vs Stage079 | 最大回撤 | Sharpe | broker10最大保证金/权益 | 超100天数 | 2x成本最大回撤 | 总滑点 | 交易次数 | 胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| r060 legacy no-cap | 20,682,740 | 3263.0472% | 65.9567% | -36.2870% | 1.5114 | 138.9327% | 17 | -38.9342% | 1,231,020 | 978 | 52.8614% |
| r070 legacy no-cap | 21,210,535 | 3348.8675% | 67.6914% | -38.5861% | 1.4353 | 140.3161% | 25 | -41.4962% | 1,228,400 | 973 | 52.4887% |
| r070 broadcluster35 | 17,676,595 | 2774.2431% | 56.0764% | -38.2323% | 1.4667 | 127.6314% | 11 | -41.6213% | 1,034,010 | 980 | 53.1627% |
| r070 productcap35 | 24,633,835 | 3905.5016% | 78.9427% | -35.1255% | 1.6170 | 120.7337% | 5 | -38.0719% | 1,373,240 | 995 | 53.0030% |
| r070 productcap30 | 22,091,640 | 3492.1366% | 70.5873% | -35.6884% | 1.5920 | 116.0430% | 5 | -38.6089% | 1,300,800 | 995 | 52.8882% |
| r070 productcap25 | 20,724,010 | 3269.7577% | 66.0923% | -33.6962% | 1.5860 | 116.3891% | 5 | -36.5020% | 1,258,670 | 997 | 52.6237% |
| r080 productcap30 | 26,691,165 | 4240.0268% | 85.7045% | -36.4617% | 1.5953 | 123.1621% | 5 | -38.6623% | 1,555,370 | 991 | 52.9323% |

## 图表复盘

- 单产品 cap 明显优于 broad cluster cap：收益保留更高，broker10 尖峰从 `140%` 附近压到 `116%-123%`。
- 但所有 productcap 点仍在 broker10 `100%` 线上方，说明只控制“单产品集中”还不足以部署。
- `r080_productcap30` 收益最好，但保证金压力也最高，不能按收益直接晋级。

## 结论

- 不是过拟合：只测粗档 `35/30/25%` 和 `risk=0.80`，没有按日期/品种修补。
- 继续有价值：有价值，但 product cap 单独不够；只允许做一次机制消融，叠加粗粒度总资金占用门控。
- 下一步：测试 `productcap30/25 + total usage 80/75`；若没有硬通过，停止该方向，不扫 `34/33/32%` 或 `78/77/76%` 小数。

## 标准回测字段

- 本阶段最优形状：`r080_productcap30`
- 期末权益：`26,691,165`
- 总收益：`4240.0268%`
- 最大回撤：`-36.4617%`
- Sharpe：`1.5953`
- 总滑点：`1,555,370`
- 总交易次数：`991`
- 胜率：非零日胜率 `52.9323%`
