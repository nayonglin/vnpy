# Stage207 下一真实窗口 + 冻结Stage103 xsmom承载诊断

- 记录时间：2026-06-01 17:45 CST
- 当前模式：day
- 所属研究线：`futures_trend_drawdown30_preserve_return`
- 是否重要突破版本：否，但属于下一步工程化方向筛选。它证明独立收益源比继续给 C3 本体降仓更值得推进。
- 本次脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage507_next_real_xsmom_frozen_carrier_diagnostic.py`
- 输出报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage507_next_real_xsmom_frozen_carrier_diagnostic_report_stage507_next_real_xsmom_frozen_carrier_diagnostic_v1.md`
- 输出图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage507_next_real_xsmom_frozen_carrier_diagnostic_chart_stage507_next_real_xsmom_frozen_carrier_diagnostic_v1.png`

## 外部调研与判断

- 调研参考：Moskowitz/Ooi/Pedersen 的 time-series momentum、Erb/Harvey 的商品期货动量/期限结构研究，以及 managed futures/trend following 文献，都支持“用独立趋势/横截面风险源改善组合路径”这个方向。
- 我的判断：Stage206 已经反证继续在 C3 本体上做相关性、波动、回撤门控的价值；下一步不应再扫 C3 风险小数，而应验证已有独立收益源能否在真实可成交约束下保住边际贡献。

## 版本改动

- 新增脚本：`analyze_qmt_roll_stage507_next_real_xsmom_frozen_carrier_diagnostic.py`
- 修改正式策略：无。
- 新增参数：无。复用 Stage506 下一真实窗口 C3 日 PnL，以及 Stage103 已冻结 `xsmom_vt10_q_momq_round_half_true_broker10_guard` 日级整数手数结果。
- 修改参数：无。
- 删除参数：无。
- 关键限制：xsmom 腿仍是冻结日级结果，没有按 `21:00/09:00` 下一真实窗口成交重放；本阶段是 value-of-information 诊断，不能晋级候选。

## 核心结果

| 版本 | 总收益 | 收益保留 | 最大回撤 | Sharpe | Ulcer | rolling252破30 | rolling504破30 | 诊断通过 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079同日baseline | `4947.2602%` | `100.0000%` | `-29.7007%` | `1.3188` | `15.0874` | `0.0000%` | `0.0000%` | 基准 |
| `risk060_clean` | `3157.9764%` | `63.8328%` | `-39.0499%` | `1.1786` | `16.3184` | `20.5825%` | `38.2190%` | 否 |
| `risk060_clean + frozen Stage103 xsmom` | `3270.2146%` | `66.1015%` | `-36.5873%` | `1.2319` | `15.2783` | `10.8252%` | `36.7257%` | 是 |
| `risk070_clean + frozen Stage103 xsmom` | `3356.0350%` | `67.8362%` | `-38.9638%` | `1.1701` | `16.3349` | `20.2913%` | `37.8872%` | 是 |
| `r080_vol60 + frozen Stage103 xsmom` | `3206.5951%` | `64.8156%` | `-32.1919%` | `1.2083` | `15.0214` | `5.0485%` | `29.3142%` | 否，收益保留差一点 |

## 3个月/6个月体验

- `risk060_clean + frozen Stage103 xsmom`：
  - 90日 p05 `-15.5136%`，中位 `12.9724%`，DD30破例 `0.0000%`，Ulcer P95 `17.1455`。
  - 180日 p05 `-6.7429%`，中位 `22.4328%`，DD30破例 `3.8010%`，Ulcer P95 `20.1386`。
- 相对 `risk060_clean`：
  - 90日 p05 从 `-17.2167%` 改到 `-15.5136%`，DD30破例从 `1.4408%` 降到 `0.0000%`。
  - 180日 p05 从 `-7.5695%` 改到 `-6.7429%`，DD30破例从 `13.2332%` 降到 `3.8010%`。
- 相对 Stage079 同日 baseline：短持有体验仍明显更差，说明诊断通过只是“下一真实窗口 DD40/收益65边界有希望”，不是恢复 Stage079 同日体验。

## 成本压力

- `risk060_clean + frozen Stage103 xsmom` 在 1x/2x/3x/5x 成本压力下最大回撤为 `-36.5873%/-39.2611%/-42.1112%/-58.3244%`。
- `r080_vol60 + frozen Stage103 xsmom` 在 1x/2x/3x/5x 成本压力下最大回撤为 `-32.1919%/-34.5657%/-37.2082%/-51.8905%`。
- 成本结论：冻结 xsmom 可以改善正常成本边界，但高滑点压力仍明显不足；真实执行阶段必须额外审计 xsmom 腿成交成本。

## 图表视觉复盘

- 图上 `risk060_clean + frozen Stage103 xsmom` 相比 `risk060_clean` 的 NAV 有持续抬升，水下图在 2022 初和 2025 两段都浅于纯 `risk060_clean`。
- `risk060_clean + frozen Stage103 xsmom` 不是只靠后段单一收益台阶，确实在核心风险簇中有缓冲。
- `risk070_clean + frozen Stage103 xsmom` 收益更高，但水下更贴近 `-40%`。
- `r080_vol60 + frozen Stage103 xsmom` 水下最好但收益保留卡在 `65%` 以下，不作为主诊断。

## 决策

- 决策标签：`frozen_xsmom_diagnostic_edge_requires_true_execution`
- 不晋级为候选。
- 值得进入下一阶段工程化复验：是。
- 下一阶段目标：做 xsmom 腿的下一真实窗口成交重放，或至少先构建 xsmom 订单/持仓 ledger，确认冻结日级边际贡献是否能真实成交。

## 过拟合与继续价值反思

- 运行前过拟合反思：否。复用已冻结 Stage103 规则，不调窗口、阈值、品种、权重，也不根据坏窗口补丁。
- 运行后过拟合反思：否，但如果继续调 xsmom 的 `63日/0.5/10%/broker10` 或改权重，就会变成过拟合。下一步只能做真实执行重放。
- 运行前继续价值反思：是。Stage206 后继续压 C3 本体的边际价值低，独立收益源是更符合第一性原理的方向。
- 运行后继续价值反思：是。冻结上界诊断已经把 `risk060` 从收益保留不足推回 `DD40 + 收益65`，值得花一次工程成本验证 xsmom 腿是否真实可成交。

## 后续规划和 TODO

- 下一步 Stage208：
  1. 读取 Stage103/xsmom 的信号、目标合约、换仓和日 PnL 构造逻辑。
  2. 生成 xsmom 订单/持仓 ledger。
  3. 使用下一真实窗口价格替换日级 close-to-close 假设。
  4. 与 `risk060_clean/risk070_clean` 组合后重跑全周期、3/6个月、成本压力和图表视觉复盘。
