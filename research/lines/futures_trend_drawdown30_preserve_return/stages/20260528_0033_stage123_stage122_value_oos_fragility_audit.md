# Stage123：Stage122 value756 OOS 与脆弱性审计

- 时间：2026-05-28 00:33 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 阶段性质：固定 Stage122 `stage103_plus_value_proxy756_monthly_guard` 做反证审计；不新增策略参数，不扫 lookback、top_n、调仓频率、日期、品种或保证金小数。
- 是否重要突破：是，重要纠偏；将 Stage122 从“研究级候选”降为“研究经验/后续观察”，不继续执行晋级。
- 决策：`downgrade_to_research_memory`

## 调研与判断

- FuturesBacktest 将期货策略族拆为 trend、value、carry，并说明 value 是趋势的长期反方向思路，通常需要 `5年+` 时间尺度；这支持“长期 value proxy 可以试”，也提示当前 2020 后本地样本偏短。
- Miffre/Rallis 的商品期货动量与反转研究显示，商品期货中短期动量更明确，长期 contrarian 并不稳定；因此不能因为 value756 在后半段有效就直接部署。
- Bailey / López de Prado 的 PBO/CSCV 思路提示，最优回测需要拆成 IS/OOS、贡献集中度和组合切分反证；本阶段正是按这个原则检验 Stage122。

参考：

- FuturesBacktest strategies: https://www.futuresbacktest.com/docs/strategies/
- Miffre & Rallis, Momentum strategies in commodity futures markets: https://www.sciencedirect.com/science/article/abs/pii/S037842660700026X
- Bailey 等 Backtest Overfitting / PBO: https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf

## 新增、修改、删除

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage423_stage122_value_oos_fragility_audit.py`
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage423_stage122_value_oos_fragility_audit_report_stage423_stage122_value_oos_fragility_audit_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage423_stage122_value_oos_fragility_audit_chart_stage423_stage122_value_oos_fragility_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage423_stage122_value_oos_fragility_audit_decision_stage423_stage122_value_oos_fragility_audit_v1.json`
- 新增审计参数：
  - 激活日过滤：从 value756 首次真实持仓日 `2023-02-23` 开始。
  - 激活后 rolling 窗口：`90/180/252/504` 日。
  - 年份贡献剔除：`2023/2024/2025/2026`、`2024_2025`、激活后前 `12` 个月。
  - moving block bootstrap：`20/60/120` 日块长，各 `3000` 次。
  - broker10 保证金比较：只看 `1.10x`，相对 Stage103 是否更差。
- 修改参数：无。
- 删除参数：无。

## 核心结果

| 版本 | 样本 | 总收益 | 最大回撤 | Sharpe | Ulcer |
| --- | --- | ---: | ---: | ---: | ---: |
| Stage079 | full | 4947.2602% | -29.7007% | 1.6231 | 15.1468 |
| Stage103 | full | 5059.4984% | -28.9792% | 1.6841 | 14.3669 |
| Stage103+value756 | full | 5183.5439% | -28.9792% | 1.6998 | 14.2186 |
| Stage079 | 2023-02-23后 | 573.5346% | -19.1880% | 1.7453 | 10.5716 |
| Stage103 | 2023-02-23后 | 548.2987% | -18.2641% | 1.7626 | 10.1224 |
| Stage103+value756 | 2023-02-23后 | 563.2172% | -18.0623% | 1.8016 | 9.6992 |

说明：Stage423 的 full Sharpe 使用日收益序列重算，和 Stage422 汇总口径的 Sharpe 数值不同；收益、回撤和方向判断一致。

## 样本覆盖

- value756 首次有效持仓：`2023-02-23`。
- 有效持仓天数：`699` 天。
- 激活后日历样本：`772` 天。
- 有 `120+` 有效持仓日的年份：`3` 年。
- 但有效持仓天数 `699 < 756`，未覆盖完整一个 value lookback 周期，因此 `data_sufficiency_pass = false`。
- `2026` 只有 `5` 个有效持仓日，不能视为新的有效 OOS 年。

## 激活后 rolling 反证

相对 Stage103：

| 窗口 | 收益胜率 | 收益差中位数 | 收益差5%分位 | 回撤不劣化率 | Ulcer不劣化率 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 90日 | 59.1799% | +0.1845pp | -1.6212pp | 77.1668% | 91.7987% |
| 180日 | 67.8535% | +0.4232pp | -3.3259pp | 93.5910% | 94.9135% |
| 252日 | 63.2272% | +0.7403pp | -1.7040pp | 100.0000% | 98.6828% |
| 504日 | 93.9302% | +1.9884pp | -0.0556pp | 100.0000% | 100.0000% |

判断：

- 相对 Stage103，value756 风险体验较好，180/252/504 日收益胜率也强。
- 但 90 日收益胜率 `59.1799%` 未达到预设 `60%` 强通过线。
- 相对 Stage079，激活后收益胜率只有 `49.5806%/51.3733%/52.0307%/37.1775%`，不能证明它对 Stage079 的任意启动收益体验有稳定优势。

## 年度贡献与集中度

| 年份 | edge PnL | 贡献占比 | 有效持仓日 | 正 edge 日比例 |
| ---: | ---: | ---: | ---: | ---: |
| 2023 | 169,155 | 22.1732% | 209 | 58.5714% |
| 2024 | 39,355 | 5.1587% | 242 | 51.2397% |
| 2025 | 509,350 | 66.7667% | 243 | 60.9053% |
| 2026 | 45,020 | 5.9013% | 5 | 3.8961% |

贡献明显偏向 `2025`，但不是单日贡献：剔除最大 `20` 个相对贡献日后，相对 Stage103 仍有 `+35.3740pp`。

## 年份剔除

- 剔除 `2025` 年 value edge 后，总收益仍为 `5100.7228%`，仍高于 Stage103 `5059.4984%`。
- 同时剔除 `2024+2025` 后，总收益仍为 `5094.3236%`，仍高于 Stage103 `34.8252pp`。
- 剔除激活后前 `12` 个月，仍高 Stage103 `94.9902pp`。

结论：value756 不是完全靠某一年或前12个月撑起来，边际收益有一定真实性。

## Bootstrap

| block_len | 正edge概率 | 5%分位edge PnL | 中位edge PnL |
| ---: | ---: | ---: | ---: |
| 20 | 99.9000% | 355,701.75 | 762,920 |
| 60 | 99.9667% | 360,100.50 | 793,637.5 |
| 120 | 99.9333% | 396,681.00 | 833,895 |

结论：按当前有效样本做 block bootstrap，边际收益不脆弱；这个结果支持“保留研究经验”，但不能覆盖样本年限不足和保证金执行风险。

## Broker10 保证金反证

- `start_2020`：
  - Stage103：`1` 天拒单，需额外现金约 `13,665.70`。
  - value756：`2` 天拒单，需额外现金约 `78,920.08`。
  - 相对 Stage103 额外现金差 `65,254.38`。
- `start_2024` 和 `phase_2024_2025` 虽无拒单，但 value756 的最大保证金/权益到 `99.6009%`，接近上限。
- 这违反“账户资金口径不增加、保证金压力不能比 Stage103 更差”的执行晋级原则。

## 最终判断

- 不按目标放宽晋级：value756 不进入执行候选，也不替代 Stage103。
- 降级为研究经验：长期 value/contrarian 方向有真实边际收益证据，但本地样本和保证金约束不足。
- 当前主执行相对候选仍是 Stage103。

## 过拟合反思

- 运行前判断：不是过拟合；本阶段只审计固定候选，不做参数选择。
- 运行后判断：不是过拟合；它主动反证并降级了 Stage122，而不是为了救结果增加过滤条件。
- 若继续扫 `504/756/1008`、top_n、调仓频率、日期/品种过滤或保证金小数，会转为过拟合。

## 继续价值反思

- 运行前判断：有价值；Stage122 是少数出现边际收益的结构，必须严查。
- 运行后判断：value756 子路线主动优化价值低；总目标仍有价值，但下一步不应继续救 value 参数，应该回到 Stage103 工程化/影子盘，或寻找新的、样本更长且保证金更轻的不同风险源。

## 输出文件

- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage423_stage122_value_oos_fragility_audit.py`
- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage423_stage122_value_oos_fragility_audit_report_stage423_stage122_value_oos_fragility_audit_v1.md`
- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage423_stage122_value_oos_fragility_audit_chart_stage423_stage122_value_oos_fragility_audit_v1.png`
- 决策：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage423_stage122_value_oos_fragility_audit_decision_stage423_stage122_value_oos_fragility_audit_v1.json`
