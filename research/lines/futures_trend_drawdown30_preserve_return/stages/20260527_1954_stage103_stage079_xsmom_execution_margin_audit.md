# Stage103 Stage079 xsmom执行保证金审计

- 时间：2026-05-27 19:54 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 阶段性质：执行保证金审计 / execution-relative candidate
- 是否重要突破版本：是。Stage103 将 Stage102 原候选从“研究晋级候选”进一步拆成执行口径：原 `round_half_true` 研究指标继续通过，但在10%保证金上浮下会在2024窗口引入相对Stage079更差的拒单风险；新增 `broker10_guard` 后，在不增加资金占用、不继续调alpha参数的前提下，相对Stage079保证金压力不劣化。
- 本次脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage403_stage079_xsmom_execution_margin_audit.py`
- 输出报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage403_stage079_xsmom_execution_margin_audit_report_stage403_stage079_xsmom_execution_margin_audit_v1.md`
- 输出图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage403_stage079_xsmom_execution_margin_audit_chart_stage403_stage079_xsmom_execution_margin_audit_v1.png`

## 开始前反思

- 是否在过拟合：否。Stage102 已固定 `10%年化波动目标 + 63日波动 + 63日自身动量为正 + scale>=0.5整数手映射`，本阶段不再调这些参数，只审计保证金上浮和执行闸门。
- 是否仍有价值继续做：是。Stage102 的 `start_2024/phase_2024_2025` 最大保证金/权益达到 `99.6696%`，真实经纪商保证金、冻结资金或日内波动略偏差都可能造成拒单，必须先审计执行边界。

## 外部调研与判断

- 参考资料：
  - Schwab Futures Margin：https://www.schwab.com/futures/futures-margin
  - Interactive Brokers Futures Margin：https://www.interactivebrokers.com/en/trading/margin-futures-fops.php
  - CME Futures and Options Margin Model：https://www.cmegroup.com/solutions/risk-management/performance-bonds-margins/futures-and-options-margin-model.html
  - AMP Futures Margin Calculator：https://www.ampfutures.com/trading-info/margins
  - SSRN, *Volatility Targeting Is Trendy*：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4773781
- 我的判断：
  - 保证金不是静态常数；交易所和经纪商都可能根据风险、波动、账户类型或临时事件上调。
  - Stage102 的 `99.6696%` 虽然历史回放未拒单，但真实部署没有足够容错。
  - 因此本阶段只做固定执行风险审计：`1.00/1.02/1.05/1.10` 保证金上浮压力，以及一个预声明的 `10%经纪商保证金缓冲闸门`。

## A/B/C定义

- A：Stage079，50万C3下单 + 11.5万外部现金。
- C1：`xsmom_vt10_q_momq_round_half_true`，Stage102 原晋级候选。
- C2：`xsmom_vt10_q_momq_round_half_true_broker10_guard`，若当日 C3+xsmom 组合保证金按 `1.10` 倍计算会超过上一日权益，则跳过当日 xsmom 篮子。

## 版本变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage403_stage079_xsmom_execution_margin_audit.py`
- 新增参数：
  - `margin_multiplier=1.00/1.02/1.05/1.10`，只用于执行审计。
  - `broker10_guard`，固定 10% 经纪商保证金上浮缓冲，不是收益参数。
- 修改参数：
  - 无正式策略默认修改。
  - 未修改 Stage102 的 `0.5`、`10%`、`63日`、动量窗口。
- 删除参数：无。

## 核心结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 结论 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Stage079 | 31,040,650 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 基准 |
| `round_half_true` | 31,726,460 | 5058.7740% | -28.9792% | 1.3679 | 14.3146 | 研究晋级，但执行相对风险不通过 |
| `broker10_guard` | 31,730,915 | 5059.4984% | -28.9792% | 1.3681 | 14.3132 | 执行相对候选 |

补充：

- 252/504日滚动破30回撤率：`broker10_guard` 为 `0% / 0%`。
- 年度/季度回撤30内通过率：`broker10_guard` 为 `100% / 100%`。
- 总滑点：Stage079 `1,556,750`；`round_half_true` `1,568,935`；`broker10_guard` `1,569,265`。
- 总交易次数：Stage079 `757`；`round_half_true` `1207`；`broker10_guard` `1217`。
- 胜率：C3逐笔胜率沿用 `45.3826%`；xsmom卫星仍是日级信号手数模拟，尚未形成逐笔平仓胜率。

## 3个月/6个月体验

`broker10_guard`：

| 指标 | Stage079 3个月 | 候选3个月 | Stage079 6个月 | 候选6个月 |
| --- | ---: | ---: | ---: | ---: |
| 5%分位收益 | -11.4702% | -10.9102% | -2.0393% | -0.6313% |
| 中位收益 | 13.5434% | 13.4787% | 33.9947% | 35.8014% |
| 正收益率 | 73.4804% | 74.6961% | 93.4772% | 94.3688% |
| 年化低于5%概率 | 29.4012% | 27.9604% | 9.0099% | 8.4467% |
| 最差期内回撤 | -29.1988% | -28.9792% | -29.7007% | -28.9792% |
| 破20回撤率 | 18.5052% | 16.6141% | 35.7109% | 35.7109% |
| 破30回撤率 | 0% | 0% | 0% | 0% |
| Ulcer P95 | 17.7786 | 16.4708 | 19.9011 | 19.1255 |
| P95最长水下天数 | 88 | 88 | 167 | 167 |

体验分：

- 3个月分：`121.2041`，相对Stage079提升 `21.2041%`。
- 6个月分：`134.4513`，相对Stage079提升 `34.4513%`。
- 综合短持有体验分：`128.4901`。
- 用户目标8项改善计数：3个月 `6/8`，6个月 `6/8`。

## 成本压力

`broker10_guard` vs Stage079：

| 滑点倍率 | Stage079最大回撤 | broker10_guard最大回撤 | 是否不更差 |
| ---: | ---: | ---: | --- |
| 1x | -29.7007% | -28.9792% | 是 |
| 2x | -31.2917% | -30.4073% | 是 |
| 3x | -33.0035% | -31.9135% | 是 |
| 5x | -40.1055% | -39.1469% | 是 |

## 保证金执行审计

10%经纪商保证金上浮压力：

| 窗口 | Stage079最大保证金/权益 | round_half最大保证金/权益 | broker10_guard最大保证金/权益 | 判断 |
| --- | ---: | ---: | ---: | --- |
| start_2020 | 109.4677% | 101.8765% | 100.4467% | Stage079自身也穿；guard相对不更差 |
| start_2021 | 108.5595% | 100.4477% | 100.4477% | Stage079自身也穿；guard相对不更差 |
| start_2024 | 82.3126% | 109.6366% | 94.5070% | 原round_half相对劣化；guard修复 |
| phase_2024_2025 | 82.3126% | 109.6366% | 94.5070% | 原round_half相对劣化；guard修复 |
| ytd_2026 | 60.2720% | 60.2720% | 60.2720% | 无新增风险 |

关键解释：

- `round_half_true` 在 `start_2024/phase_2024_2025` 会引入相对 Stage079 更差的10%保证金上浮拒单风险，不能直接进入执行准备。
- `broker10_guard` 在这些窗口只跳过 `1` 天 xsmom 篮子，反而略提升全周期收益和Ulcer；这不是拟合收益，而是刚好避开一笔保证金过紧的卫星执行日。
- `broker10_guard` 仍不是“绝对10%上浮零拒单”版本，因为 Stage079 自身在 `start_2020/start_2021` 历史段按10%上浮也会穿线；因此本阶段只能给出“相对Stage079执行风险不劣化”，不能给出“券商10%上浮绝对可部署”。

## 晋级判断

- `xsmom_vt10_q_momq_round_half_true_broker10_guard`：晋级为 Stage079 执行相对候选 / execution-relative candidate。
- `xsmom_vt10_q_momq_round_half_true`：保留为研究候选，但由于 `start_2024/phase_2024_2025` 10%保证金上浮相对Stage079劣化，不能直接进入执行准备。
- 没有 absolute deployment candidate。原因是 Stage079 自身在10%保证金上浮历史压力下也会出现拒单，必须先确认真实券商保证金率、冻结规则和账户可用资金口径。

## 后续规划和TODO

1. 固定 `broker10_guard`，禁止继续调 `0.5`、`10%`、`63日`、动量窗口或改成相邻小数。
2. 做 Stage104：工程化复跑配置/策略开关，默认关闭；验证固定配置输出与 Stage403 一致。
3. 做 Stage105：paper/影子盘日报，列出当日 C3 持仓、xsmom 目标手数、`1.00/1.05/1.10` 保证金压力和是否触发 guard。
4. 部署前必须接入真实券商保证金率和可用资金口径；否则只能作为研究候选/影子盘候选，不能替代 Stage079 当前执行口径。

## 结束后反思

- 是否在过拟合：目前不是。`broker10_guard` 是执行风险规则，不是 alpha 规则；它没有使用坏窗口收益来挑阈值，而是使用经纪商保证金上浮这一外部执行约束。
- 是否还有价值继续做：有。当前已经从“指标候选”推进到“相对执行风险候选”，下一步价值在工程化复跑和paper/影子盘验证，不在继续找小参数。

