# Stage351 Stage526 20万动态保证金执行层审计

- 时间：2026-06-04 12:16 CST
- line_id：`futures_trend_drawdown30_preserve_return`
- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage651_stage526_200k_dynamic_margin_gate.py`
- 决策：`stage526_200k_dynamic_margin_gate_not_ready`
- 是否重要突破版本：否。它反证了“遇到保证金过多当天少开一点即可解决”的朴素版本，但没有形成可部署版本。

## 运行前判断

- 过拟合判断：否。候选只用当时可见权益、已有持仓保证金和拟开仓保证金做资金执行约束，不按坏日期、坏品种或历史收益结果修补。
- 继续价值判断：是。Stage350 显示 20万 all-in 原版只在少数保证金日打穿，值得验证动态保证金执行层是否可以在不改 alpha 的情况下修复。
- 外部调研判断：vn.py PortfolioStrategy 面向多合约组合策略实盘，风险/资金治理放在组合策略或风控执行层是合理方向；但期货小资金账户必须用真实整数手、保证金、权益路径和券商保证金上浮共同验收，不能只看线性缩放收益。

## 本次代码和参数

新增文件：

- `examples/portfolio_backtesting/analyze_qmt_roll_stage651_stage526_200k_dynamic_margin_gate.py`

修改文件：

- `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`

新增参数：

- `incremental_margin_budget_gate_reduce_volume=False`：默认关闭；开启后超预算时把拟开仓手数向下取整到预算内。
- `incremental_margin_budget_gate_entry_contexts="flat_entry"`：默认只覆盖原 flat entry；Stage651 显式覆盖 `flat_entry,reverse_entry,rollover_reopen,regular_add,donchian_add`。

修改参数：

- Stage651 中 `entry_reduce95` 实际内部使用 `0.95 / 1.10` 的交易所保证金预算，对应 broker10 95%。
- Stage651 中 `entry_reduce90` 实际内部使用 `0.90 / 1.10` 的交易所保证金预算，对应 broker10 90%。
- 组合降杠杆使用 `portfolio_margin_deleverage_start_ratio=0.80`、`full_ratio=1.00`、`layer_kinds=base,add,donchian`、`min_pressure=0.50`。

删除参数：

- 无。

## 回测参数

- 账户资金：`200,000`
- C3资金：`200,000`
- Stage526 核心：`risk_multiplier=0.80`、`product_cap_ratio=0.25`、`max_concurrent_positions=4`
- xsmom/现金腿：关闭
- 成本压力：`1x/2x/3x`
- 通过标准：正常成本账户不穿、最大回撤 `>= -40%`、broker10 保证金/权益 `<= 100%`；2x成本账户不穿且最大回撤 `>= -40%`

## 新增回测结果

| 版本 | 期末权益 | 总收益 | 年化 | 最大回撤 | Sharpe | 最大 broker10 保证金/权益 | 超100%天数 | 总滑点 | 总交易次数 | 胜率 | 实际成交降手次数 | hard_pass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 原版20万 all-in | 11,554,320 | 5,677.16% | 89.9139% | -38.0459% | 1.6639 | 120.0983% | 2 | 683,440 | 656 | 52.4871% | 0 | 0 |
| entry_reduce95 | 11,554,320 | 5,677.16% | 89.9139% | -38.0459% | 1.6639 | 120.0983% | 2 | 683,440 | 656 | 52.4871% | 0 | 0 |
| entry_reduce90 | 11,554,320 | 5,677.16% | 89.9139% | -38.0459% | 1.6639 | 120.0983% | 2 | 683,440 | 656 | 52.4871% | 0 | 0 |
| pm_all80_100 | 11,554,320 | 5,677.16% | 89.9139% | -38.0459% | 1.6639 | 120.0983% | 2 | 683,440 | 656 | 52.4871% | 0 | 0 |
| entry95_pm80_100 | 11,554,320 | 5,677.16% | 89.9139% | -38.0459% | 1.6639 | 120.0983% | 2 | 683,440 | 656 | 52.4871% | 0 | 0 |

成本压力：

- 2x成本：期末权益 `10,870,880`、总收益 `5,335.44%`、最大回撤 `-40.5836%`、Sharpe `1.5864`、最大 broker10 保证金/权益 `126.542%`、超100% `5` 天。
- 3x成本：期末权益 `10,187,440`、总收益 `4,993.72%`、最大回撤 `-43.2876%`、Sharpe `1.5094`、最大 broker10 保证金/权益 `133.717%`、超100% `13` 天。

## 修改/删除回测结果

- 修改回测结果：无。Stage651 的全部动态闸门版本权益路径与原版一致。
- 删除回测结果：无。

## 关键归因

- flat entry 候选层面确实出现降手：`entry_reduce95` 降 `1` 个候选、合计 `57` 手；`entry_reduce90` 降 `2` 个候选、合计 `94` 手。
- 但这些降手候选没有实际成交，`executed_entry_gate_volume_reduced_count=0`，所以权益和保证金路径不变。
- 最大保证金日是 `2022-02-17`，账户权益 `1,181,355`，broker10 保证金/权益 `120.0983%`，持仓为 `lh.DCE,jm.DCE,cu.SHFE,sp.SHFE`。
- 关键 `lh2205` 开仓信号日是 `2022-02-16`，当时 estimated equity `1,766,655`，已有保证金 `852,852`，95% broker10 预算下仍可承受 `24` 手，实际只开 `16` 手；到 `2022-02-17` 权益下降后才变成保证金超限。因此这不是事前就能通过“当天少开一点”直接识别的场景。
- 组合持仓降杠杆本阶段未触发，说明当前内置 `portfolio_margin_deleverage` 还不能解决这类“信号日通过、次日权益/保证金路径打穿”的风险。

## 结论

用户的直觉方向是对的：实盘不能在保证金过高时硬开，应降低或跳过开仓数量。但这次审计显示 Stage526 20万原版的主要超限不是“新开仓当时已经超预算”，而是复利权益参与放大后，已有多品种持仓在次日权益路径变差时打穿。

因此，单纯新增动态开仓降手不够。20万要实盘，需要转向更结构化的小资金执行版本，例如：

1. 限制滚动权益参与下单，测试 `sizing_equity_cap=200,000` 或分段利润参与；
2. 继续保留 Stage350 的防守探针方向：`risk0.50 + maxpos2` 已基本通过保证金硬闸门；
3. 如果还想保留较高收益，只能设计账户层 pre-submit/next-day stress gate，而不是用事后风险日救参。

## 后续 TODO

- 不继续扫 `90/95/80-100` 这类保证金小数。
- 下一步若继续 20万实盘准备，优先跑“小资金权益参与上限”粗结构：`no_profit_reinvest`、`profit_participation_25%`、`risk0.50/maxpos2` 三组，而不是救原版 Stage526。
- Stage526 live TCA 缺口仍未关闭，任何保证金层通过也不能直接实盘。

## 运行后判断

- 过拟合判断：否。失败后没有继续按坏日期或坏品种调阈值，反而识别出问题本质是权益参与和次日路径风险。
- 继续价值判断：有价值，但方向应从“只在开仓时降手”转向“20万账户资金参与上限/防守版本/真实 pre-submit stress gate”。原版 Stage526 20万 all-in 仍不应实盘。

## 输出文件

- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage651_stage526_200k_dynamic_margin_gate_report_stage651_stage526_200k_dynamic_margin_gate_v1.md`
- 汇总：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage651_stage526_200k_dynamic_margin_gate_summary_stage651_stage526_200k_dynamic_margin_gate_v1.csv`
- 入场风险诊断：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage651_stage526_200k_dynamic_margin_gate_entry_risk_stage651_stage526_200k_dynamic_margin_gate_v1.csv`
- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage651_stage526_200k_dynamic_margin_gate_chart_stage651_stage526_200k_dynamic_margin_gate_v1.png`
