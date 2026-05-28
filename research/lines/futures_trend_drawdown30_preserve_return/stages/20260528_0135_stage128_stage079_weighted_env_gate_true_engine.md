# Stage128 - Stage079 weighted_env_gate 默认形状真实引擎审计

- 时间：2026-05-28 01:35 CST。
- 研究线：`futures_trend_drawdown30_preserve_return`。
- 阶段性质：A/C 固定结构真实引擎审计；不修改 Stage079/C3 核心交易规则，不新增资金，不扫阈值。
- 是否重要突破：否。重要反证：环境权重闸门可以明显压低短期回撤，但收益和 Sharpe 牺牲过大，不能晋级。
- 是否触发 A/B：是。A=Stage079 真实引擎基准；C=Stage079 + `weighted_env_gate` 默认形状，`floor=0.35`。

## 调研和判断

- 外部调研结论：趋势策略的风险状态过滤、volatility scaling、回撤/拥挤状态治理在公开研究和 GitHub 趋势框架中都有先验；但这些过滤最容易把历史坏窗口拟合成少交易规则，因此必须固定形状、一次验证，失败不救参。
- 本阶段使用仓库内 Stage096 已存在但未实质启用的 `weighted_env_gate` 字段，只测默认环境阈值和 `weight_floor=0.35`。
- 开始前过拟合反思：否。原因是只验证已存在的默认形状，不按本次结果调 `close_position/range/selected_rate/floor`。
- 开始前继续价值反思：有。原因是它直接针对用户关心的 3个月/6个月持有体验，且落到真实引擎而非日收益层。

## 版本变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage428_stage079_weighted_env_gate_true_engine.py`。
- 新增参数：`enable_weighted_env_gate=True`、close_position good/bad `0.25/0.60`、range good/bad `0.60/0.00`、selected_rate good/bad `0.35/0.75`、`weight_floor=0.35`。
- 修改参数：无。
- 删除参数：无。
- 修改正式策略默认：无。

## 核心结果

| version | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 总滑点 | 总交易次数 | 胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 | 31,040,650 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 1,556,750 | 757 | 45.3826% |
| weighted_env_gate default floor0.35 | 8,382,720 | 1263.0439% | -22.8775% | 1.2225 | 11.1377 | 501,190 | 704 | 42.7762% |

## 3个月/6个月体验

| version | horizon | p05收益 | 中位收益 | 正收益率 | 年化低于5%率 | 最差窗口回撤 | DD20穿越率 | Ulcer p95 | 体验分 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 | 90d | -11.4702% | 13.5434% | 73.4804% | 29.4012% | -29.1988% | 18.5052% | 17.7786 | 100.0000 |
| env gate | 90d | -8.9946% | 9.0389% | 76.3170% | 28.1405% | -22.7482% | 2.2512% | 10.8374 | 204.0442 |
| Stage079 | 180d | -2.0393% | 33.9947% | 93.4772% | 9.0099% | -29.7007% | 35.7109% | 19.9011 | 100.0000 |
| env gate | 180d | -5.0282% | 23.3806% | 90.7086% | 12.9517% | -22.8775% | 8.4467% | 14.5415 | 74.9707 |

## 决策

- 决策：`no_promotion`。
- 失败约束：`total_return_not_lower`、`sharpe_not_lower`、6个月体验目标。
- 成本压力：`1x/2x/3x/5x` 滑点下，候选最大回撤均不差于 Stage079；但正常成本收益和 Sharpe 过低，5x 下收益较高也只是因为大幅降暴露。
- 结论：`weighted_env_gate` 默认形状不晋级。它改善 3个月左尾和回撤，但明显牺牲全周期收益、Sharpe 和 6个月持有体验。
- 后续规划：不继续扫环境阈值、`floor`、close position、range z-score 或 selected rate 小数；这条路线停止。

## 输出

- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage428_stage079_weighted_env_gate_true_engine_report_stage428_stage079_weighted_env_gate_true_engine_v1.md`
- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage428_stage079_weighted_env_gate_true_engine_equity_drawdown_stage428_stage079_weighted_env_gate_true_engine_v1.png`
- 决策 JSON：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage428_stage079_weighted_env_gate_true_engine_decision_stage428_stage079_weighted_env_gate_true_engine_v1.json`

## 反思

- 运行后过拟合反思：不是过拟合。原因是失败后停止，没有围绕阈值继续救参；继续救会变成历史路径拟合。
- 运行后继续价值反思：本子路线主动优化价值低。总目标仍有价值，但应优先固定 Stage103 工程化/影子盘，或只测试全新、低自由度、低相关风险源。
