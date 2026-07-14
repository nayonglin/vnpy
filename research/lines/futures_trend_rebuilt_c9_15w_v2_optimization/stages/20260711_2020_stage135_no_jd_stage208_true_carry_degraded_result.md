# Stage135 no-JD Stage208 真成交账本降级证伪结果

- 时间：`2026-07-11 19:12 -> 20:20 CST`
- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 阶段：`Stage135`
- 是否重要突破：否；这是当前 Stage208 路线的预注册 canary 关闭结论。
- 性质：冻结 C9 路径上的单向真实卫星成交/持仓账本；不是完整单体正式引擎，不含 JD，不改正式策略、实盘、CTP、邮件、launchd 或订单路径。

## 外部调研与判断

- TqSdk 官方历史回测/下载接口支持按明确时间边界获取分钟数据；Stage134/136 已把本 canary 实际使用的成交窗口验收到真实 open 且 fallback 为 0。
- 趋势跟随的长期价值来自跨市场右尾和规则化风险控制，低相关腿只有在真实持仓、成本和组合保证金口径下改善路径才有价值，不能用旧代理收益直接叠加。
- 判断：本阶段只运行预声明 `2020-01` canary；最大回撤和最长水下任一不严格改善，就停止，不用 13 起点或参数扫描救援。

参考：

- TqSdk DataDownloader：<https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.tools.download.html>
- TqSdk TqBacktest：<https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html>
- AQR `A Century of Evidence on Trend-Following Investing`：<https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing>

## 冻结口径

- A：Stage167 当前 `Stage847-C9-15w`，初始资金 `150,000`。
- B：C 聚合保证金闸门实际承载的 no-JD xsmom 卫星腿单独权益。
- C：冻结 C9 equity + 同一起点卫星累计真实 PnL。
- 信号：Stage020 `mom_12m_skip1m`；只删除 `jd.DCE`，不递补、不重排。
- scale：63 日年化波动目标 `10%`，过去 63 日 PnL 为正，全部 `shift(1)`，`scale>=0.5` 才执行每腿最低一手。
- 成交：前一 signal day `21:00-21:05` 第一根 open；无夜盘时 fill day `09:00-09:05` 第一根 open。
- 保证金：C9 已有持仓使用前一日已知 exact margin；卫星已有持仓使用前一日 mark，新目标使用真实 open；broker multiplier `1.10`。
- 区间：只跑 `2020-01-02 -> 2026-06-30` canary；13 个逐半年起点和 `2x/3x` 成本只在 canary 全通过后运行。

## 参数变更

- 新增研究参数：`excluded_product=jd.DCE`、`target_vol=0.10`、`vol_lookback=63`、`round_half_threshold=0.5`、`broker_margin_multiplier=1.10`。
- 修改研究语义：独立审查后把聚合保证金从同日收盘状态改为开盘前可知的 T-1 C9/卫星状态；实际使用的 minute source 加 SHA256。
- 删除参数：无。
- 正式策略参数：无任何新增、修改或删除。

## 运行中发现并修复的 P1

- 初版保证金 gate 错用了同日收盘后的 C9 `total_margin_exact` 和卫星 margin，属于未来状态。
- 独立 reviewer `Dirac` 重算：`2020-09-03` 开盘前真实 proposed broker10 ratio 应为 `101.563079%`，必须在该日平仓，而不是继续持有。
- 新增失败测试 `test_margin_gate_uses_previous_close_state_not_current_close_margin`；修复后 `2020-09-02` 开 5 腿、`09-03` 平 5 腿、`09-04` 订单为 0。
- 修复后重新生成全部 Stage135 输出，再交给新的独立 reviewer `Faraday` 从原始 CSV 重算。

## 最终回测结果

| 臂 | 起止权益 | 总收益 | 最大回撤 | Sharpe | 最长水下 | 总滑点 | 交易次数 | 非零日胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A 冻结 C9 | `150,000 -> 5,979,281` | `3886.187333%` | `-55.370112%` | `1.395916704` | `438` | `738,050` | `631` | `52.923387%` |
| B no-JD 腿 | `150,000 -> 146,960` | `-2.026667%` | `-2.433333%` | `-0.327210073` | `1,409` | `260` | `10` | `50.000000%` |
| C 组合 | `150,000 -> 5,976,241` | `3884.160667%` | `-55.422309%` | `1.393387577` | `438` | `738,310` | `641` | `52.923387%` |

- 胜率口径为组合 `net_pnl != 0` 的交易日：A/C `525/992`，B `1/2`；不是逐笔胜率。
- A/B/C 最低权益分别为 `141,520 / 146,350 / 141,520`。
- 收益保留：`99.947849%`。
- 卫星 `2020-09-02` gross `-3,520`、滑点 `130`、net `-3,650`；`09-03` gross `+740`、滑点 `130`、net `+610`；累计 `-3,040`。
- fallback order：`0`。
- 持久化 CSV 独立重算 reconciliation 最大误差 `<=2.328306e-10`，低于 `1e-6`。
- actual PIT broker10 最大值 `88.474912%`；EOD 诊断最大值 `97.935845%`。
- 实际 minute source `6` 份均有 SHA256；manifest 当前 `10/10` 路径的 size/mtime/SHA 匹配。

## Canary 闸门

| 检查 | 结果 |
| --- | --- |
| fallback = 0 | 通过 |
| reconciliation <= 1e-6 | 通过 |
| actual PIT broker10 <= 100% | 通过 |
| 收益保留 >= 70% | 通过，`99.947849%` |
| C 最大回撤严格优于 A | **失败**，恶化 `0.052196pp` |
| C 最长水下严格短于 A | **失败**，`438 == 438` |
| B/C 未破产 | 通过 |

- 最终决策：`stage135_canary_failed_close_current_stage208_route`。
- 按预注册规则不运行 13 起点 full，不运行 `2x/3x` 成本压力，不继续补 JD 精确逐日保证金，也不做 lookback、阈值、top/bottomN、权重、品种或方向救参。

## 输入与语义边界

- Stage020 排名宇宙存在 `64` 个上市前 phantom legs：`lc.GFEX=20`、`SH.CZCE=44`。本 canary 实际卫星成交只发生在 2020 年，不受这 64 腿影响，但结果不得表述为无未来成分认证。
- 当前工具是冻结 C9 上的单向 overlay，不是完整单体正式引擎。
- Stage136 证明 AP010 为完整闭合态分钟数据；其余 Stage052 legacy 文件只能作为 `open` 成交价来源，不能用于 high/low/close/volume/OI 研究。Stage135 实际只读取它们的 open。

## 独立 Agent 终审

- reviewer：`Faraday`，只读、未修改文件。
- 独立重算与最终表一致；`P0=0 / P1=0 / P2=4 / P3=3`。
- P2：64 个 phantom legs；同合约直接反向时卫星 margin 仍未把新方向腿按真实 open 重估；`_safe_float`/缺失 scale 的静默归零 fail-close 覆盖不足；缺 AP010/09-03/09-04/manifest 的生产 artifact 端到端测试。
- P3：未冻结 MinuteBarStore 全候选搜索集合和 producer hash；canary decision 声明 4 个仅 full 才生成的 goal 路径；内存重算与持久化 CSV 的 reconciliation 有 `1e-10` 级序列化差异。
- 这些问题不影响本次负面结论：实际无反向、输入完整、fallback 0、会计误差远低于阈值；但禁止复用本工具直接扩 full 或称正式真引擎。
- 数字置信度：`99%`；语义置信度：`94%`。
- 终审许可：允许把 corrected canary 作为 Stage135 最终负面审计结果并关闭路线；不允许表述为完整含 JD、正式真引擎、可上线候选或无未来数据认证。

## 验证

- Stage052/130/131/132/133/134/135/136 联合回归：`96/96` 通过。
- Stage052/134/135/136 工具 `py_compile` 通过。
- `git diff --check` 通过。

## 反思

- 运行前过拟合判断：否。单一规格、单一起点 canary 和 conjunctive gate 均在读取结果前冻结。
- 运行后过拟合判断：否。保证金修复是 PIT 语义纠错；失败后没有调整任何参数，也没有扩大样本寻找局部胜点。
- 运行前继续价值判断：有。它决定是否值得继续投入 JD 历史保证金与完整 Stage208 工程。
- 运行后继续价值判断：当前 Stage208 路线无。卫星只交易两天、累计亏损，既未改善最大回撤，也未缩短水下；继续 full 或补 JD 只会违反预注册停止规则。

## 输出

- 报告：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage135_no_jd_stage208_true_carry_degraded/rebuilt_c9_v2_stage135_no_jd_stage208_true_carry_degraded_canary_stage135_no_jd_stage208_true_carry_degraded_v1_report.md`
- 决策：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage135_no_jd_stage208_true_carry_degraded/rebuilt_c9_v2_stage135_no_jd_stage208_true_carry_degraded_canary_stage135_no_jd_stage208_true_carry_degraded_v1_decision.json`
- 图：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage135_no_jd_stage208_true_carry_degraded/rebuilt_c9_v2_stage135_no_jd_stage208_true_carry_degraded_canary_stage135_no_jd_stage208_true_carry_degraded_v1_chart.png`
