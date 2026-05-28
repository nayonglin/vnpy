# Stage150 分钟代理执行权益重构审计

- 研究线：`futures_trend_drawdown30_preserve_return`
- 时间：2026-05-28 05:00 CST
- 工作模式：`day`
- 是否重要突破：是。Stage149 的分钟价格已从“和日线 close/open 比较”推进到“相对原引擎成交价 theoretical_price 的一阶实现偏差”，可以开始评价分钟执行代理对 Stage079/Stage103 权益的影响。
- 是否触发 A/B：否。本阶段不新增策略候选、不修改 Stage079/C3/Stage103 交易规则，只做执行口径重构。
- 决策标签：`minute_execution_first_order_rebuild_complete_need_true_path_replay`

## 外部调研与判断

- Implementation shortfall 的核心是模型/决策价格与真实成交价格之间的损益差，而不是分钟价与另一个日线字段之间的价差。
- Backtrader、NautilusTrader 等回测框架均强调订单执行时点必须明确，通常发生在后续 bar 或具有清晰时间戳语义的 bar 上。
- TqSdk 分钟回放可作为当前本地可用的数据通路，但一阶实现偏差仍不能替代真实路径重放。
- 判断：Stage150 是必要的修正。Stage149 中 `proxy - same_day_close` 只能说明日线字段错位；要重建权益，必须使用 `proxy - theoretical_price`。

参考：

- Backtrader order execution：<https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/>
- NautilusTrader backtesting：<https://nautilustrader.io/docs/latest/concepts/backtesting>
- Implementation shortfall 说明：<https://trading.glass/en/academy/execution-precision/execution-metrics/implementation-shortfall>
- TqSdk 文档：<https://tqsdk-python.readthedocs.io/>

## 本阶段改动

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage450_minute_execution_equity_rebuild.py`
- 新增输出：
  - 日权益：`qmt_roll_stage450_minute_execution_equity_rebuild_daily_stage450_minute_execution_equity_rebuild_v1.csv`
  - 交易实现偏差：`qmt_roll_stage450_minute_execution_equity_rebuild_trade_delta_stage450_minute_execution_equity_rebuild_v1.csv`
  - summary/horizon/score/cost/gate/report/chart/decision
- 新增参数：无策略参数。仅固定审计口径：
  - `14:55 last5 VWAP`
  - `14:55 first open`
  - `preferred real open = 21:00/09:00 first open`
- 修改参数：无。
- 删除参数：无。
- 策略规则变更：无。未修改入场、出场、仓位、品种池、AI池、资金占用或滑点规则。

## 关键口径

本阶段不再使用：

`proxy_price - same_day_close`

而使用：

`side_multiplier * (proxy_price - theoretical_price) * volume * size`

其中 `theoretical_price` 是原 SameDayClose 引擎订单成交价；这才是可接回权益的一阶实现偏差。

## 一阶实现偏差

| 指标 | 数值 |
| --- | ---: |
| Stage149接回交易数 | 692 |
| 有效 theoretical price 交易数 | 692 |
| 14:55 VWAP 可用交易数 | 692 |
| preferred real open 可用交易数 | 624 |
| 14:55 VWAP 一阶执行差合计 | 303,272.00 |
| preferred real open 一阶执行差合计 | -322,325.00 |
| 14:55 VWAP 单笔中位差 | 30.00 |
| preferred real open 单笔中位差 | 0.00 |
| preferred real open 单笔最大有利差 | 480,000.00 |
| preferred real open 单笔最大不利差 | -260,000.00 |

## 全周期核心结果

| 版本 | 总收益 | 最大回撤 | Sharpe | Ulcer | rolling252破30 | rolling504破30 | 年度/季度DD30通过 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Stage079 original | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 0.0000% | 0.0000% | 100% / 100% |
| Stage079 14:55 VWAP 一阶 | 4996.5727% | -29.6662% | 1.3236 | 15.0330 | 0.0000% | 0.0000% | 100% / 100% |
| Stage079 14:55 first-open 一阶 | 5022.3740% | -29.4110% | 1.3175 | 15.0315 | 0.0000% | 0.0000% | 100% / 100% |
| Stage079 preferred open 一阶 | 4894.8496% | -30.3000% | 1.3252 | 14.1679 | 9.2718% | 24.5022% | 80.00% / 77.27% |
| Stage103 original | 5059.4984% | -28.9792% | 1.3681 | 14.3132 | 0.0000% | 0.0000% | 100% / 100% |
| Stage103 14:55 VWAP C3-only 一阶 | 5108.8109% | -28.9206% | 1.3724 | 14.2690 | 0.0000% | 0.0000% | 100% / 100% |
| Stage103 preferred open C3-only 一阶 | 5007.0878% | -29.8627% | 1.3741 | 13.4834 | 0.0000% | 0.0000% | 100% / 100% |

## 3个月/6个月体验要点

- Stage079 `14:55 VWAP` 一阶曲线相对 Stage079：
  - 3个月分 `106.1686`，改善 `7/8` 项，但没有达到 `>=110`。
  - 6个月分 `105.2451`，改善 `5/8` 项，但没有达到 `>=110`。
  - 5x成本压力回撤 `-41.7024%`，比 Stage079 `-40.1055%` 更差，因此不满足硬约束。
- Stage079 `preferred open` 一阶曲线：
  - 总收益降至 `4894.8496%`，最大回撤打到 `-30.3000%`。
  - rolling252/504破30分别为 `9.2718%/24.5022%`。
  - 直接淘汰。
- Stage103 `14:55 VWAP C3-only` 一阶曲线机械分数过线：
  - 3个月分 `128.5630`，6个月分 `121.4349`，各改善 `6/8` 项。
  - 但这不是实际晋级，因为它没有重放因成交价变化导致的后续持仓路径，也没有审计 xsmom 腿分钟执行。

## 回测指标字段

本阶段为执行口径一阶审计，不是新策略回测：

- 期末权益：见 summary 输出，不作为新候选权益。
- 总收益/最大回撤/Sharpe/Ulcer：用于执行敏感性比较。
- 总滑点/总交易次数：沿用原交易路径的一阶处理，不能解释为真实重放交易次数。
- 胜率：不适用。

## 输出文件

- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage450_minute_execution_equity_rebuild.py`
- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage450_minute_execution_equity_rebuild_report_stage450_minute_execution_equity_rebuild_v1.md`
- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage450_minute_execution_equity_rebuild_chart_stage450_minute_execution_equity_rebuild_v1.png`
- 决策 JSON：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage450_minute_execution_equity_rebuild_decision_stage450_minute_execution_equity_rebuild_v1.json`
- 日权益：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage450_minute_execution_equity_rebuild_daily_stage450_minute_execution_equity_rebuild_v1.csv`
- 交易实现偏差：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage450_minute_execution_equity_rebuild_trade_delta_stage450_minute_execution_equity_rebuild_v1.csv`

## 结论

- `preferred real open` 口径下，Stage079 一阶曲线已经打穿核心硬约束，说明“下一会话开盘执行”不是可直接晋级的口径。
- `14:55 VWAP` 口径下，Stage079 一阶曲线整体接近并略优于原路径，但仍有 5x 成本压力劣化，不能作为完成目标的候选。
- Stage103 `14:55 VWAP C3-only` 一阶结果有价值，值得进入真实路径重放；但当前不能实际晋级。
- 下一步应做 `14:55 VWAP` 的 SameDayClose 引擎成交价覆盖重放，观察成交价改变后止损、加仓、减仓和后续持仓路径是否仍稳定。

## 后续规划和 TODO

1. 新建真实路径重放引擎：在 `cross_limit_order_on_close` 中用 `14:55 VWAP` 覆盖实际成交价。
2. 先重放 Stage079/C3 主体；若交易路径大量分叉，记录 fallback 和 unmatched 订单。
3. 再决定是否接 Stage103 xsmom 腿分钟执行。
4. 只有真实路径重放仍通过 Stage079 硬约束后，才继续寻找提升3个月/6个月体验的低自由度候选。

## 过拟合与继续价值反思

- 运行前过拟合反思：否。只是把分钟代理价相对原引擎成交价接回权益，不改变信号或参数。
- 运行后过拟合反思：否。Stage103 的机械过线没有被晋级，避免把一阶近似当成实盘结论。
- 运行前继续价值反思：是。Stage149 的 `proxy - same close` 现金差不能直接指导权益。
- 运行后继续价值反思：是。`14:55 VWAP` 一阶口径没有直接击穿 Stage079，值得进入真实路径重放；`preferred open` 口径已明显失败，不应继续在该方向优化。
