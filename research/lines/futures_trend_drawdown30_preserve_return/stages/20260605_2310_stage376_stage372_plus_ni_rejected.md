# Stage376 - Stage372 + ni 扩池多周期反证

- 时间：2026-06-05 23:10 CST
- line_id：`futures_trend_drawdown30_preserve_return`
- 当前工作模式：`day`
- 当前正式版本：`official_live_stage372_20w_recovery_sleeve`
- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage664_stage372_plus_ni_multiperiod.py`
- 决策：`stage372_plus_ni_candidate_rejected`
- 是否重要突破：否；这是扩池候选反证，不改变正式版。

## 运行前判断

- 候选假设：`ni.SHFE` 在 2022 年有清晰外生趋势冲击和流动性基础，可能补足当前 Stage372 在部分金属/工业品趋势上的覆盖。
- A：当前 Stage372/20万正式版 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`。
- C：Stage372/20万逻辑不变，只把 `ni.SHFE` 加入产品宇宙和每个月 AI eligibility。
- 过拟合判断：有风险。`ni` 是在复盘 2022 趋势后被点名加入，存在单年份 hindsight 风险。
- 继续价值判断：有价值。加入单品种属于产品池结构变更，必须用全周期、多起点、成本压力和品种贡献验证是否可接正式池。

## 外部调研与判断

- 上期所资料显示 `NI` 是镍期货，合约单位 1 吨、报价为人民币元/吨，具备期货合约基础。
- S&P Global 对 2022 年镍市场的复盘显示，俄乌冲突、LME 镍逼仓/停牌和流动性危机共同造成极端价格波动。
- 本地 2022 年商品趋势复盘显示 `ni.SHFE` 当年收益/波动确实突出，但这更要求做跨周期反证，而不是直接扩池。
- 调研结论：`ni` 有纳入研究池的理由，但没有直接纳入正式池的充分理由。

参考：

- `https://www.shfe.com.cn/eng/Home/othercontents/2026Futures/QA_NI.pdf`
- `https://www.spglobal.com/market-intelligence/en/news-insights/articles/2022/3/nickel-price-spike-and-lme-trade-halt-presages-extended-nickel-deficit-69269697`

## 本次改动

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage664_stage372_plus_ni_multiperiod.py`
- 新增输入：
  - `examples/portfolio_backtesting/backtest_outputs/stage664_generated_inputs/qmt_roll_stage664_stage372_plus_ni_multiperiod_universe_stage664_stage372_plus_ni_multiperiod_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/stage664_generated_inputs/qmt_roll_stage664_stage372_plus_ni_multiperiod_historical_eligibility_stage664_stage372_plus_ni_multiperiod_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/stage664_generated_inputs/qmt_roll_stage664_stage372_plus_ni_multiperiod_latest_eligibility_stage664_stage372_plus_ni_multiperiod_v1.csv`
- 新增参数：
  - `NI_PRODUCT=ni.SHFE`
  - `PLUS_NI_STRATEGY=stage664_stage372_plus_ni_entry_filter`
- 修改参数：
  - 产品宇宙从当前正式 `19` 个品种扩展到 `20` 个：新增 `ni.SHFE`
  - 每个 AI eligibility `eval_date` 固定追加 `ni.SHFE`，不重训、不重排、不改变原有产品分数顺序
- 删除参数：无
- 正式配置修改：无
- CTP/实盘连接：无
- order API 调用：无

## 回测参数

- 账户资金：`200,000`
- 策略体：Stage372/20万恢复仓 sleeve
- 历史窗口：`2020-01-01` 至 `2026-04-30`
- 最新 YTD：`2026-01-01` 至 `2026-06-05`
- 成本压力：`1x/2x/3x`
- 历史 eligibility 来源：Stage78 固定 `ai_top8_plus_fu_satellite_post_signal_entry_filter`
- 最新 YTD eligibility 来源：Stage182 最新 AI 池，最新 eval_date `2026-05-29`

## 核心结果

| 窗口 | A收益 | C收益 | 收益差 | A回撤 | C回撤 | Sharpe差 | 结论 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 全周期 | 4264.1425% | 971.4700% | -3292.6725pp | -38.6713% | -35.7823% | -0.4573 | 收益和 Sharpe 明显失败 |
| since_2021 | 2221.3050% | 603.8100% | -1617.4950pp | -38.1656% | -37.2978% | -0.4396 | 明显失败 |
| since_2022 | 133.8550% | 39.3350% | -94.5200pp | -28.0550% | -28.0550% | -0.4028 | 没有修复 2022 |
| since_2023 | 70.2100% | 76.3675% | +6.1575pp | -24.5662% | -18.1978% | +0.0953 | 局部改善 |
| since_2024 | 33.3550% | 32.1475% | -1.2075pp | -29.4347% | -19.1508% | +0.0604 | 回撤改善但收益略低 |
| since_2025 | 17.9975% | -1.4600% | -19.4575pp | -17.6662% | -25.2320% | -0.5944 | 失败 |
| phase_2022_2023 | 0.2975% | 10.4975% | +10.2000pp | -28.0550% | -28.0550% | +0.2439 | 局部改善 |
| latest YTD | 8.0400% | 8.0400% | 0.0000pp | -16.3027% | -16.3027% | 0.0000 | 最新池未实际改变 |

全周期 C：

- 期末权益：`2,142,940`
- 总收益：`971.4700%`
- 最大回撤：`-35.7823%`
- Sharpe：`1.1706`
- 总滑点：`244,360`
- 总交易次数：`688`
- 胜率：`52.2040%`
- broker10 保证金峰值：`80.0613%`
- 超90/100天数：`0/0`
- 强制减仓：`4` 次，`84` 手

成本压力：

- 1x：`2,142,940 / 971.4700% / -35.7823% / Sharpe 1.1706`
- 2x：`1,898,580 / 849.2900% / -37.9671% / Sharpe 1.0817`
- 3x：`1,654,220 / 727.1100% / -40.3347% / Sharpe 0.9922`

ni 直接贡献：

- `ni` 全周期净 PnL：`-351,320`
- `ni` 滑点：`6,600`
- `ni` trade_count：`74`
- `ni` active_days：`159`
- `ni` 活跃区间：`2020-07-07` 至 `2026-01-29`

## 归因判断

- `ni` 自身亏损 `-351,320`，但 C 相对 A 全周期期末权益少约 `6,585,345`，所以主要损害不是 `ni` 单品种亏损本身。
- 更本质的问题是路径交互：`ni` 进入候选池后占用仓位、保证金和风险状态，挤掉了原 Stage372 中更有效的右尾机会。
- 2020、2021、2022、2023、2024、2025、2026 年度 PnL 均弱于 A；2025 差距尤其大，说明它不是单一 2022 窗口问题。
- C 的回撤更浅，但收益和 Sharpe 降得太多，不符合当前“保收益”目标。

## 输出文件

- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage664_stage372_plus_ni_multiperiod_summary_stage664_stage372_plus_ni_multiperiod_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage664_stage372_plus_ni_multiperiod_comparison_stage664_stage372_plus_ni_multiperiod_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage664_stage372_plus_ni_multiperiod_cost_stress_stage664_stage372_plus_ni_multiperiod_v1.csv`
- ni_activity：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage664_stage372_plus_ni_multiperiod_ni_activity_stage664_stage372_plus_ni_multiperiod_v1.csv`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage664_stage372_plus_ni_multiperiod_report_stage664_stage372_plus_ni_multiperiod_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage664_stage372_plus_ni_multiperiod_chart_stage664_stage372_plus_ni_multiperiod_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage664_stage372_plus_ni_multiperiod_decision_stage664_stage372_plus_ni_multiperiod_v1.json`

## 结论

- 不把 `ni.SHFE` 加入当前正式实盘品种池。
- 不修改 `qmt_roll_official_live_config.py`。
- 当前正式版本仍是 Stage372/20万 `official_live_stage372_20w_recovery_sleeve`。
- `ni` 可以保留为研究池观察对象，但不能作为“固定加一品种”接入正式池。

## 运行后反思

- 过拟合判断：是，若继续围绕 `ni` 调权重、调入池月份、过滤年份或只保留某些方向，会明显变成 2022 hindsight 拟合。
- 是否还有价值继续：当前形状没有继续价值。只有当未来做的是通用扩池 selector、风险槽位或外生状态驱动的 point-in-time 选品，而不是单独救 `ni`，才有继续价值。

## TODO

- 停止 Stage372 固定加 `ni` 路线。
- 若继续扩池，必须走通用 selector 或低相关风险槽机制，不做单品种手工加入正式池。
- 每次扩池候选都必须报告 direct product PnL 和 opportunity-cost/path interaction，不能只看候选品种自身盈亏。
