# Stage224 外科式峰值保证金前沿

- 时间：2026-06-01 20:38 CST
- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage524_surgical_peak_margin_frontier.py`
- 性质：A/C 粗前沿；不改 78-1/C3/Stage103 alpha，不改入场/出场，不做日期或品种补丁。
- 决策：`surgical_peak_margin_not_ready`

## 开始前反思

- 是否过拟合：否。只测试粗结构：`productcap30` 近源对照、组合保证金峰值减仓 `95-105/90-105`、最大活跃产品数 `5/4`，没有扫小数或坏窗口。
- 是否值得继续：是。Stage223 已证明 usage gate 太钝，需要验证更窄的峰值治理。

## 调研判断

外部资料给出的原则仍是：managed futures 可以用组合风险预算，但保证金必须按交易所/券商认可的 exact margin 约束。主观净额或事后净掉相关品种不可用；本阶段只测试可在引擎中表达的粗结构。

## 结果

| 版本 | 总收益 | 最大回撤 | Sharpe | broker10最大 | 穿100天数 | 2x成本DD | 结论 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `r080_pc30_control` | 4240.0268% | -36.4617% | 1.5953 | 123.1621% | 5 | -38.6623% | 高收益但保证金失败 |
| `r080_pc30_peak_all_95_105` | 2806.5561% | -32.9017% | 1.5160 | 116.0489% | 7 | -35.6064% | 主动减仓失败 |
| `r080_pc30_peak_all_90_105` | 2806.5561% | -32.9017% | 1.5160 | 116.0489% | 7 | -35.6064% | 同上 |
| `r080_pc30_maxpos5` | 3706.8301% | -34.8408% | 1.6259 | 116.8637% | 1 | -36.8594% | 近通过但仍失败 |
| `r080_pc30_maxpos4` | 4761.7772% | -36.0184% | 1.7207 | 112.7086% | 1 | -38.0134% | 最高收益近通过 |

图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage524_surgical_peak_margin_frontier_chart_stage524_surgical_peak_margin_frontier_v1.png`

视觉判断：主动减仓曲线被压低且仍穿100，说明它不是有效外科手术；`maxpos4` 权益线最高、收益保留最高，但散点仍落在 broker100 上方，不能晋级。

## 标准字段

- 新增参数：`max_concurrent_positions=5/4`；`portfolio_margin_deleverage_start/full=95/105、90/105`。
- 修改/删除参数：无正式参数变更。
- 新增回测结果：见上表。
- 总滑点/交易/胜率：最佳近通过 `r080_pc30_maxpos4` 为 `1,647,100 / 909 / 53.9444%`。

## 结束反思

- 是否过拟合：否，近通过来自粗整数 `maxpos4`，不是小数救参。
- 是否值得继续：是。`maxpos4` 只剩 1 天超限，值得做现金边界和 cap25 组合测试。

