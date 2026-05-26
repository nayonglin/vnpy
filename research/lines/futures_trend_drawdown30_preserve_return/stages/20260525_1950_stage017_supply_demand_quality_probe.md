# Stage017 仓单库存与基差开仓质量探针

- 研究线：`futures_trend_drawdown30_preserve_return`
- 时间：2026-05-25 19:50 CST
- 基准版本：`official_stage78_1_defensive_50w_no_sizing_cap`
- 阶段性质：外生供需质量因子只读分桶，不改正式策略。
- 是否重要突破：否。形成可用线索但未通过直接排序闸门。

## 开始前反思

- 是否过拟合：否。原因是先固定低自由度公式，按点时化数据做 valid/test 分桶，不按收益结果调权重。
- 是否有价值继续：是。原因是用户提到的 COT/舆情方向需要落到更贴近中国盘的供需数据；仓单、库存、基差比外盘 COT 更接近国内商品交易。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage316_supply_demand_quality_probe.py`
- 新增输出：供需特征、方向信号、开仓候选匹配、覆盖率、分桶报告。
- 新增正式参数：无。
- 修改正式参数：无。
- 删除正式参数：无。
- 本阶段没有运行收益回测，因此没有新的期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数或胜率。

## 因子口径

- 数据区间：`20230101` 到 `20260417`
- 点时化：仓单和基差视为交易日 20:00 后可用，只影响下一交易日及之后候选。
- 公式：做多方向 = `-基差率zscore * 40%` + `-20日基差率变化zscore * 30%` + `-仓单变化率zscore * 30%`；做空方向取反。
- 最大信号年龄：`7` 个自然日。

## 结果

- 判定：`fail_quality_score_not_monotonic_on_oos_forward_r`
- 特征行数：`14,420`
- 外生信号行数：`28,840`
- 候选样本数：`953`
- 实际开仓候选数：`315`
- 候选命中外生信号数：`552`
- 实际开仓命中外生信号数：`141`
- 候选命中率：`57.9224%`
- 实际开仓命中率：`44.7619%`

valid 分桶：

- 低分平均20日R：`-1.3208`，平均20日不利波动R：`5.8985`
- 中分平均20日R：`0.7801`，平均20日不利波动R：`3.4417`
- 高分平均20日R：`-0.6028`，平均20日不利波动R：`3.5762`

test 分桶：

- 低分平均20日R：`-0.7665`，平均20日不利波动R：`6.3301`
- 中分平均20日R：`6.9556`，平均20日不利波动R：`4.4614`
- 高分平均20日R：`1.1092`，平均20日不利波动R：`3.6817`

补充检查显示，强逆风区间在 valid/test 中都偏差，但高分并不单调更好，因此不能直接做“越高越加仓”。

## 结论

- 供需分数不能作为连续加仓分数。
- 供需强逆风可能适合做防守过滤，但必须冻结阈值后进入真实引擎验证，不能根据分桶结果继续调权重。

## 结束后反思

- 是否过拟合：否。当前只是接受非单调结果，没有为了救因子调权重。
- 是否有价值继续：是，但只能验证“强逆风过滤”这一条低自由度规则。

## 输出文件

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage316_supply_demand_quality_probe_report_stage316_supply_demand_quality_probe_v1.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage316_supply_demand_quality_probe_summary_stage316_supply_demand_quality_probe_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage316_supply_demand_quality_probe_bucket_summary_stage316_supply_demand_quality_probe_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage316_supply_demand_quality_probe_external_signals_stage316_supply_demand_quality_probe_v1.csv`

