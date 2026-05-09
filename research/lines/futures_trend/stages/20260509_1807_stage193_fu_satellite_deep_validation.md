# Stage193 fu.SHFE 固定卫星品种深度验证

- 时间：2026-05-09 18:07
- 工作模式：day
- 研究线：futures_trend
- 是否重要突破版本：否，属于第78正式口径的保留/剔除证据补强
- 触发原因：用户要求深度研究是否确实可以加上 `fu.SHFE`

## 运行前调研和判断

外部调研结论：公开的期货趋势跟踪和 time-series momentum 资料普遍支持“多资产、可交易、成本可控”的趋势组合，而不是只因为单个品种历史收益好就加入。可参考：

- Moskowitz / Ooi / Pedersen 的 time-series momentum 研究：趋势效应存在于股票指数、货币、商品、债券等多类期货，核心是跨市场分散和规则化执行。
- Clare / Seaton / Smith / Thomas 的 commodity futures trend following 研究：商品期货中趋势跟踪和动量结合能改善风险调整收益，但仍要检查交易成本和风险。
- Baltas / Kosowski 的 futures trend-following 研究：CTA 与 time-series momentum 有显著关系，重点是广泛合约、容量和稳健性。
- SHFE 燃料油规则说明：`fu` 是上期所燃料油期货，合约乘数 10 吨/手，最小变动 1 元/吨，属于可标准化交易合约。

我的判断：`fu.SHFE` 不能因为 Stage192 全样本收益第一就直接加入；必须检验分周期、起始年份、年度路径和滑点压力。如果这些测试仍然稳健，才说明它更像“适合第78趋势结构的卫星品种”，而不是单纯历史幸运。

## 本次版本变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage193_fu_satellite_deep_validation.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 实验标签：`stage193_fu_satellite_deep_validation_v1`
  - 对照组：`manual18_ai_top8_no_fu`
  - 候选组：`manual18_ai_top8_plus_fu`
  - 候选组继承官方第78的 `fu.SHFE` 固定卫星口径
  - 候选组继承 `streak_risk_state_excluded_products=fu.SHFE`
  - 候选组继承 `streak_risk_state_exclusion_mode=profit_only`
  - 滑点压力倍数：`1.0 / 1.5 / 2.0 / 3.0 / 5.0`
- 修改参数：无正式第78参数修改
- 删除参数：无

## 回测参数

- 数据区间：2020-01-01 至 2026-04-30
- 资金规模：200,000
- 策略基础：第78趋势策略主逻辑，保留当前月度 AI Top8 品种池节奏
- 成本口径：当前元数据滑点口径；本轮 `total_commission=0`
- 对照方式：固定两组口径直接比较，不做阈值搜索，不做失败后参数补救

## 周期拆分结果

| 窗口 | no_fu收益 | with_fu收益 | no_fu回撤 | with_fu回撤 | no_fu Sharpe | with_fu Sharpe | 结论 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| full_2020_2026 | 1865.8150% | 2218.7650% | -36.9907% | -36.9907% | 1.2091 | 1.2922 | 通过 |
| pre_ai_2020_2021 | 592.4525% | 592.4525% | -36.9907% | -36.9907% | 1.6313 | 1.6313 | 中性 |
| post_signal_2022_2026 | 943.0100% | 1350.4125% | -50.5791% | -37.5422% | 1.0525 | 1.3023 | 明显通过 |
| early_ai_2022_2023 | 181.3750% | 260.8600% | -50.5791% | -37.5422% | 0.9895 | 1.3070 | 明显通过 |
| trend_rich_2024_2025 | 279.7500% | 382.0900% | -38.8196% | -31.1166% | 1.2459 | 1.4577 | 通过 |
| latest_2026 | -3.6675% | 2.8325% | -16.2144% | -35.4516% | -0.5017 | 0.0629 | 黄灯 |

## 起始年份冷启动结果

| 起始窗口 | no_fu收益 | with_fu收益 | 收益差 | no_fu回撤 | with_fu回撤 | Sharpe差 | 结论 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| since_2020 | 1865.8150% | 2218.7650% | +352.9500pct | -36.9907% | -36.9907% | +0.0831 | 通过 |
| since_2021 | 1628.7600% | 1981.7100% | +352.9500pct | -42.3203% | -42.3203% | +0.0972 | 通过 |
| since_2022 | 1014.0050% | 1427.1425% | +413.1375pct | -51.0504% | -36.7687% | +0.2525 | 明显通过 |
| since_2023 | 581.8150% | 877.8125% | +295.9975pct | -44.1771% | -39.4397% | +0.2323 | 通过 |
| since_2024 | 250.2275% | 415.2975% | +165.0700pct | -38.8196% | -31.1166% | +0.2445 | 通过 |
| since_2025 | 148.0550% | 360.0475% | +211.9925pct | -35.0367% | -28.8813% | +0.4190 | 通过 |
| since_2026 | -3.6675% | 2.8325% | +6.5000pct | -16.2144% | -35.4516% | +0.5646 | 黄灯 |

## 年度收益拆分

| 年份 | no_fu年收益 | with_fu年收益 | 判断 |
| --- | ---: | ---: | --- |
| 2020 | 122.1325% | 122.1325% | 中性 |
| 2021 | 211.7295% | 211.7295% | 中性 |
| 2022 | 13.0619% | 19.1605% | with_fu更好 |
| 2023 | 44.8352% | 47.1962% | with_fu更好 |
| 2024 | 19.2823% | 19.8189% | with_fu更好 |
| 2025 | 45.9621% | 57.0800% | with_fu更好 |
| 2026 | -0.4260% | 1.4358% | with_fu更好 |

## 滑点压力结果

| 滑点倍数 | no_fu收益 | with_fu收益 | 收益差 | no_fu回撤 | with_fu回撤 | Sharpe差 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.0x | 1865.8150% | 2218.7650% | +352.9500pct | -36.9907% | -36.9907% | +0.0782 |
| 1.5x | 1800.9375% | 2153.3300% | +352.3925pct | -37.7199% | -37.7199% | +0.0789 |
| 2.0x | 1736.0600% | 2087.8950% | +351.8350pct | -38.4655% | -38.4655% | +0.0797 |
| 3.0x | 1606.3050% | 1957.0250% | +350.7200pct | -40.2491% | -40.2491% | +0.0812 |
| 5.0x | 1346.7950% | 1695.2850% | +348.4900pct | -44.5009% | -44.5009% | +0.0846 |

## 核心结果

- `with_fu` 全样本期末权益：`4,637,530`
- `with_fu` 总收益：`2218.7650%`
- `with_fu` 最大回撤：`-36.9907%`
- `with_fu` Sharpe：`1.2922`
- `with_fu` 总滑点：`261,740`
- `with_fu` 总交易次数：`782`
- `with_fu` 胜率：`42.1053%`
- 对比 `no_fu`：期末权益增加 `705,900`，总收益增加 `352.9500` 个百分点，Sharpe 增加 `0.0831`，全样本最大回撤不变。

历史正式基准字段：旧第78参考口径曾记录期末权益 `1,610,900`、总收益 `705.45%`、最大回撤 `-54.93%`、Sharpe `0.661`、总滑点 `100`、总交易次数 `1000`。本轮不是复跑该旧基准，而是在当前 Stage78 / 月度 AI Top8 / 手工18基础池口径下验证 `fu.SHFE` 固定卫星。

## 结论

`fu.SHFE` 可以保留在第78正式趋势策略的固定卫星品种里，但应标记为“通过、带 2026 冷启动黄灯”。理由：

1. 它不是只在全样本好看；2022-2026、2022-2023、2024-2025 和 since_2022 至 since_2025 冷启动均改善收益和 Sharpe，多数还改善回撤。
2. 它不是靠忽略成本成立；1x 到 5x 滑点压力下，`with_fu` 相对 `no_fu` 的收益优势仍保持在约 `+348` 到 `+353` 个百分点，回撤不恶化。
3. 它不是 2020/2021 旧行情贡献；`pre_ai_2020_2021` 两组完全一致，说明 `fu` 的贡献主要发生在后续 AI/卫星口径生效阶段。
4. 风险点清楚：2026 单独冷启动时，`with_fu` 收益从亏损转正，但最大回撤从 `-16.2144%` 加深到 `-35.4516%`，说明短窗口实盘心理压力会更大，不能因为长期改善就忽略短期路径。

实盘含义：第78影子盘主路径可以继续采用当前官方 `official_stage78_defensive_v1` 中的 `fu.SHFE` 固定卫星设置；但在 30万实盘影子盘里，需要单独日报追踪 `fu` 的持仓贡献、回撤贡献、滑点和换月表现。

## 运行前过拟合反思

- 判断：有过拟合风险，但可控。
- 原因：`fu` 已经在 Stage192 add-one 中表现最好，如果继续围绕它调参，很容易把历史噪声包装成规律。本轮控制方式是预先固定 `no_fu` 与 `with_fu` 两个口径，只做分窗、冷启动、年度和滑点压力验证，不做参数救援。

## 运行后过拟合反思

- 判断：本轮结果本身不像过拟合，但结论不能升级成“fu 永远有效”。
- 原因：证据来自多个窗口和成本压力，且 2020/2021 未贡献优势，说明不是单一早期行情支撑；但 `latest_2026` 回撤恶化是真实瑕疵，后续必须用影子盘和 T+1 实盘成交继续验证。

## 运行前继续价值反思

- 判断：有价值继续。
- 原因：`fu` 是否保留直接影响第78正式品种池和实盘影子盘信号，属于实盘前必须确认的结构性决策。

## 运行后继续价值反思

- 判断：有价值，但下一步不应继续围绕 `fu` 优化参数。
- 原因：本轮已经足够支持“保留 `fu`”；继续价值转向实盘化验证：30万初始资金、T+1 成交、真实手续费/滑点、影子盘日报和 `fu` 单品种归因。

## 输出文件

- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage193_fu_satellite_deep_validation.py`
- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage193_fu_satellite_deep_validation_report_stage193_fu_satellite_deep_validation_v1.md`
- 资金曲线HTML：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage193_fu_satellite_deep_validation_equity_curves_stage193_fu_satellite_deep_validation_v1.html`
- 周期汇总：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage193_fu_satellite_deep_validation_summary_stage193_fu_satellite_deep_validation_v1.csv`
- 周期对比：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage193_fu_satellite_deep_validation_comparison_stage193_fu_satellite_deep_validation_v1.csv`
- 起始年份对比：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage193_fu_satellite_deep_validation_start_year_comparison_stage193_fu_satellite_deep_validation_v1.csv`
- 年度收益：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage193_fu_satellite_deep_validation_annual_returns_stage193_fu_satellite_deep_validation_v1.csv`
- 滑点压力：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage193_fu_satellite_deep_validation_slippage_comparison_stage193_fu_satellite_deep_validation_v1.csv`

## 后续规划和 TODO

- 保留 `fu.SHFE` 为第78正式固定卫星，不继续为它调参。
- 在影子盘日报中新增 `fu` 单品种归因字段：持仓、PnL、滑点、换月、是否触发风控。
- 后续如研究 `sn.SHFE`，必须作为独立 Stage，不应与 `fu` 结果混在一起。
- 实盘前继续跑 30万 T+1 成交和真实成本口径，确认短期最大回撤是否仍在用户 40% 可接受边界内。
