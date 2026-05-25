# Stage014 CFTC COT 外生开仓质量探针

## 基本信息

- 记录时间：2026-05-25 18:03 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 上游基准：`official_stage78_1_defensive_50w_no_sizing_cap`
- 本阶段性质：真实官方外生数据只读探针，不修改第78-1交易规则。
- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage313_cftc_cot_external_quality_probe.py`
- 参考数据源：CFTC Historical Compressed Disaggregated Futures Only 周度持仓数据。

## 本阶段要回答的问题

用户修正后的问题不是“公告附近是否导致亏损”，而是：

- 能不能用公告、舆情、政府数据或类似外生数据改善开仓质量？
- 能不能让好开仓多一点、差开仓少一点或小一点，从而把最大回撤压到30%以内，同时不明显牺牲收益？

本阶段先选一个低自由度、官方、可点时化的数据源：CFTC COT。它不是中国期货市场本土持仓真相，只能作为外盘资金温度计，验证其是否对第78-1开仓候选有样本外排序能力。

## 点时化处理

- COT 报告日期是周二持仓。
- 为避免未来函数，本脚本把可用时间设为报告日后第4天早上8点中国时间。
- 第78-1开仓候选只匹配此前45天内最近一条 COT 信号。
- 不使用报告日当天或未来收益，不根据回测结果调 COT 参数。

## 外生信号构造

核心字段：

- `managed_money_net_oi = (Managed Money Long - Managed Money Short) / Open Interest`
- `managed_money_flow_oi = (Change Managed Money Long - Change Managed Money Short) / Open Interest`
- 156周滚动 zscore，最低52周才启用。
- 方向一致性分数：`0.35 * 净持仓分量 + 0.65 * 净流入分量`
- 做多时同向加分，做空时取反。
- `suggested_volume_multiplier` 只做建议倍率，不进入实盘。
- `veto_flag` 只作为候选禁止提示，不进入实盘。

覆盖映射：

- `CF.CZCE` 对 ICE Cotton No.2
- `OI.CZCE` 对 CBOT Soybean Oil
- `lh.DCE` 对 CME Lean Hogs
- `lc.GFEX` 对 Lithium Hydroxide
- `au.SHFE` 对 COMEX Gold
- `cu.SHFE` 对 COMEX Copper
- `fu.SHFE` 对 ICE Fuel Oil
- `hc.SHFE`、`rb.SHFE` 对 HRC Steel

## 运行结果

- 外生信号行数：`4750`
- 开仓候选样本数：`953`
- 实际开仓候选数：`315`
- 候选命中外生信号数：`401`
- 实际开仓命中外生信号数：`117`
- 候选命中率：`42.0776%`
- 实际开仓命中率：`37.1429%`
- 判定：`fail_quality_score_not_monotonic_on_oos_forward_r`

## 分桶结果摘要

| 样本切分 | 外生分桶 | 样本数 | 平均20日R | 平均20日不利波动R |
| --- | --- | ---: | ---: | ---: |
| train | 低分 | 41 | 0.5111 | 7.4247 |
| train | 中分 | 41 | 3.0064 | 3.4284 |
| train | 高分 | 41 | 4.2458 | 4.6019 |
| valid | 低分 | 30 | -1.3700 | 5.3497 |
| valid | 中分 | 30 | -2.1322 | 5.6587 |
| valid | 高分 | 31 | -0.6836 | 3.5593 |
| test | 低分 | 62 | 2.7677 | 3.2436 |
| test | 中分 | 62 | 0.1758 | 7.1111 |
| test | 高分 | 63 | -0.7065 | 5.5624 |

## 结论

- COT 在训练段看起来有一定方向一致性，但到 test 段后不成立。
- test 高分桶的20日R反而低于低分桶，且不利波动R也不占优。
- 因此 CFTC COT 不应作为第78-1的开仓质量因子、禁止开仓因子或加减仓因子。
- 也不应启动 A/C 回测，因为只读分桶闸门已经失败。
- COT 可以保留为研究用外盘温度计，但不能单独承担“最大回撤30以内且保收益”的目标。

## 和用户补充截图的关系

截图里的判断方向基本正确：COT 对中国期货不能“直接用”，只能作为部分强关联品种的外生参考。本阶段的实证结果进一步说明，即使做了点时化和方向匹配，它对当前第78-1开仓候选也没有稳定样本外排序能力。

所以后续不应继续围绕 COT 做小数阈值微调。更合理的下一步是转向更贴近中国盘的点时化数据：

- 交易所会员成交持仓排名；
- 交易所库存/仓单；
- 国内政策和监管公告；
- 产业库存、开工率、利润和基差；
- 对能源、农产品等强外盘品种，可把 EIA、USDA、外盘COT作为辅助温度，而不是主因子。

## 回测指标

本阶段没有运行新的策略收益回测，因此没有新的期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数或胜率。

当前对照仍沿用 Stage012 最强内部风控线索：

- `C_pressure040`
- 期末权益：`25,429,055`
- 总收益：`4985.811%`
- 最大回撤：`-31.0767%`
- Sharpe：`1.2650`
- 总滑点：`2,047,490`
- 总交易次数：`862`
- 胜率：`45.0346%`

## 过拟合反思

- 运行前：不是过拟合。
- 原因：COT 是官方周度数据，构造公式预先固定，没有根据回测收益调参。
- 运行后：仍不是过拟合。
- 原因：分桶失败后直接拒绝接入交易，没有为了让结果好看而改映射、改阈值或改窗口。
- 风险提示：如果继续反复试 COT 的窗口、分位、品种映射，直到某个切分好看，那就会进入过拟合。

## 继续价值反思

- 运行前：有价值。
- 原因：外生开仓质量因子是不同于“回撤后降风险”的结构路线。
- 运行后：继续有价值，但不应继续深挖 COT 单因子。
- 下一步：优先做国内交易所持仓/库存/仓单/政策公告的数据可得性探针，先构造点时化表，再沿用 Stage013 评估器做 valid/test 分桶。

## 输出文件

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage313_cftc_cot_external_quality_probe_external_signals_stage313_cftc_cot_external_quality_probe_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage313_cftc_cot_external_quality_probe_joined_candidates_stage313_cftc_cot_external_quality_probe_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage313_cftc_cot_external_quality_probe_bucket_summary_stage313_cftc_cot_external_quality_probe_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage313_cftc_cot_external_quality_probe_report_stage313_cftc_cot_external_quality_probe_v1.md`
