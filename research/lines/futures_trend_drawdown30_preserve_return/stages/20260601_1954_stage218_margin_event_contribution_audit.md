# Stage218 保证金超限日持仓贡献审计

- 时间：2026-06-01 19:54 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 阶段性质：只读归因，不修改交易规则，不做坏日期/坏品种黑名单。
- 对应脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage518_margin_event_contribution_audit.py`
- 输出报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage518_margin_event_contribution_audit_report_stage518_margin_event_contribution_audit_v1.md`
- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage518_margin_event_contribution_audit_chart_stage518_margin_event_contribution_audit_v1.png`
- 决策：`targeted_margin_postmortem_not_surgical_enough`

## 外部调研与判断

- 调研参考：managed futures 的分散价值来自低相关收益源，但相关性会在危机/拥挤状态下变化；清算保证金和券商上浮是硬约束，不能用净值层相关性替代真实持仓保证金。
- GitHub/vn.py 方向判断：框架能支持组合策略、价差策略和账户级组合管理，但不能替代本账户的整数手、真实成交窗口、exact position margin 与 broker10 上浮审计。
- 本阶段判断：先做逐日持仓保证金贡献排序，比继续扫组合保证金阈值更接近问题本质。

## 本次变更

- 新增参数：无交易参数；审计固定 `broker_multiplier=1.10`。
- 修改参数：无。
- 删除参数：无。
- 新增结果：生成超限日事件、产品贡献排序、产品聚合、summary、decision、report、chart。
- 修改结果：无。
- 删除结果：无。

## 核心结果

| 版本 | 超100天数 | broker10最大保证金/权益 | 事件中位保证金/权益 | 中位所需削减占总保证金 | 单产品足够比例 | Top1同产品集中度 | 所需产品数 | 总收益 | 最大回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| r060 legacy no-cap | 17 | 138.9327% | 108.7656% | 8.0591% | 100.00% | 35.2941% | 10 | 3263.0472% | -36.2870% |
| r070 legacy no-cap | 25 | 140.3161% | 112.8131% | 11.3578% | 100.00% | 24.0000% | 10 | 3348.8675% | -38.5861% |
| r070 cluster35 | 11 | 127.6314% | 107.4575% | 6.9399% | 100.00% | 45.4545% | 4 | 2774.2431% | -38.2323% |
| r070 pm all 90/110 | 15 | 127.2622% | 112.0004% | 10.7146% | 100.00% | 40.0000% | 6 | 2262.0772% | -37.6796% |

r070 legacy 超限日中，单日第一大产品通常足以把 broker10 拉回 100 以下，但第一大产品不是固定品种。主要 required 产品包括 `si.GFEX`、`lh.DCE`、`fu.SHFE`、`AP.CZCE`、`lc.GFEX`、`jm.DCE` 等，其中 `si/lh` 在 required 事件中还是正贡献，不能简单删除。

## 图表复盘

- broker10 路径显示超限是尖峰式，而不是长期慢性超限。
- 散点图显示单日第一大产品保证金通常大于所需削减额，因此“集中度治理”有工程价值。
- 产品柱状图显示第一大产品轮换明显；如果做坏品种黑名单，会同时误伤赚钱腿，并且无法解释下一次轮换。

## 结论

- 不是过拟合：本阶段只读归因，没有改参数、没有按日期/品种做过滤。
- 继续有价值：有价值，但方向应从“产品黑名单”改成“单产品保证金集中度上限”。
- 下一步：做一次预声明的单产品保证金 cap 前沿，若仍不能过 `DD40 + broker10<=100 + 2x成本DD40`，停止该形状。

## 标准回测字段

- 期末权益：本阶段不产生新交易版本；引用 r070 legacy no-cap `21,210,535`。
- 总收益：`3348.8675%`
- 最大回撤：`-38.5861%`
- Sharpe：引用 Stage519 同口径 `1.4353`
- 总滑点：引用 r070 legacy no-cap `1,228,400`
- 总交易次数：引用 r070 legacy no-cap `973`
- 胜率：引用 r070 legacy no-cap 非零日胜率 `52.4887%`
