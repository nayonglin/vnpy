# Stage214 第78执行延迟、滑点压力与蒙特卡洛尾部审计

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-10 12:18
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：第78正式基准实盘可行性三件套审计
- 是否重要突破：否，属于准实盘前风险审计
- 是否触发A/B：否，本轮不修改策略，只做执行与尾部压力测试

## 外部调研与判断

- 参考资料：
  - 多篇期货策略回测稳健性资料都强调：不能只看单次回测，应组合使用分段/滚动样本、walk-forward、滑点成本压力、Monte Carlo/bootstrap和paper/dry-run。
  - Monte Carlo/bootstrap的价值在于暴露路径顺序风险，尤其是同一组交易换一个发生顺序后是否会出现不可承受回撤。
- 我的判断：
  - 第78是否穿越周期，重点不在继续死磕2015-2018，而在可信样本内验证执行延迟、成本冲击、坏路径和弱窗口。
  - 本阶段是实盘门槛审计，不是调参。

## 本次变更

- 新增策略代码：无
- 修改策略代码：无
- 删除策略代码：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测口径

- 策略版本：`official_stage78_defensive_v1`
- 账户规模：`200,000`
- 基础风险：`0.045`
- 数据库：项目级 `/Users/bytedance/Desktop/person/vnpy/.vntrader/database.db`
- 运行目录：仓库根目录
- 门禁：Stage196哨兵数据检查通过
- 窗口：`2020-01-01` 至 `2026-04-21`
- 基线执行：同日收盘撮合
- T+1执行：上一交易日生成订单，下一真实合约有实际bar时按开盘价撮合
- 滑点压力：`1x/2x/3x/5x`
- 蒙特卡洛：`1000`次
  - daily block bootstrap：20日块
  - trade block bootstrap：5笔交易块
  - 爆仓概率按路径中途最小权益 `<=0` 计算，不只看最终权益

## 执行延迟结果

| execution | 期末权益 | 总收益 | 最大回撤 | Sharpe | 交易次数 | 总滑点 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| same_day_close | 4,600,090 | 2,200.0450% | -36.9907% | 1.2919 | 779 | 260,110 |
| t1_next_open | 4,629,455 | 2,214.7275% | -35.4737% | 1.3135 | 786 | 260,810 |

## 执行延迟观察

- T+1次日开盘没有击穿第78，反而略好。
- 这不应解读为T+1必然更优，因为开盘成交模型仍是代理口径。
- 但它至少反证了一个关键风险：第78不是完全依赖“同日收盘成交”的脆弱策略。

## 滑点压力结果

| execution | slip | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| same_day_close | 1x | 4,600,090 | 2,200.0450% | -36.9907% | 1.4520 | 260,110 |
| same_day_close | 2x | 4,339,980 | 2,069.9900% | -38.4655% | 1.3836 | 520,220 |
| same_day_close | 3x | 4,079,870 | 1,939.9350% | -40.2491% | 1.3164 | 780,330 |
| same_day_close | 5x | 3,559,650 | 1,679.8250% | -44.5009% | 1.1866 | 1,300,550 |
| t1_next_open | 1x | 4,629,455 | 2,214.7275% | -35.4737% | 1.4700 | 260,810 |
| t1_next_open | 2x | 4,368,645 | 2,084.3225% | -37.4625% | 1.4034 | 521,620 |
| t1_next_open | 3x | 4,107,835 | 1,953.9175% | -39.5467% | 1.3375 | 782,430 |
| t1_next_open | 5x | 3,586,215 | 1,693.1075% | -44.0296% | 1.2080 | 1,304,050 |

## 滑点压力观察

- `5x`滑点下仍有较高收益，说明第78不是微利高频型成本幻觉。
- 但最大回撤会扩大到约 `-44%`，尾部承受力仍是部署约束。
- 同日和T+1在滑点压力下表现接近，说明成本敏感性没有因执行延迟显著恶化。

## 蒙特卡洛结果

| profile | method | 亏损概率 | 爆仓概率 | DD>30% | DD>40% | DD>50% | 5%收益分位 | 5%最小权益分位 | 5%回撤分位 | 中位收益 | 中位回撤 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| same_day_close | daily_block | 0.4% | 0.0% | 91.6% | 53.0% | 20.2% | 163.0994% | 125,138 | -59.4893% | 1,225.9618% | -40.6219% |
| same_day_close | trade_block | 0.0% | 7.2% | 60.3% | 44.5% | 33.8% | 1,208.9634% | -39,918 | -116.0644% | 2,140.2440% | -36.2506% |
| t1_next_open | daily_block | 0.4% | 0.0% | 91.7% | 49.9% | 18.2% | 159.6703% | 120,533 | -59.9693% | 1,246.9071% | -39.9617% |
| t1_next_open | trade_block | 0.0% | 7.4% | 59.3% | 44.5% | 31.1% | 1,284.2876% | -45,996 | -121.0003% | 2,217.2008% | -36.3437% |

## 蒙特卡洛观察

- daily bootstrap显示长期收益分布仍强，最终亏损概率只有 `0.4%`。
- trade-block bootstrap显示路径尾部更危险，路径中途爆仓概率约 `7.2%~7.4%`。
- 这说明第78的主要风险不是均值不够，而是交易顺序极差时资金曲线可能先被打穿。
- 如果部署，应重点降低尾部资金暴露，而不是追求更高收益。

## 总结判断

- 第78通过了T+1执行延迟压力：没有因次日开盘代理成交而失效。
- 第78通过了高滑点收益压力：`5x`滑点仍有收益，但回撤接近 `-44%`。
- 第78未完全通过尾部路径压力：trade-block路径爆仓概率约 `7%`，这是黄灯。
- 当前结论应是：第78具备准实盘验证价值，但正式实盘前需要更强资金风控或更小初始资金暴露。

## 输出文件

- 汇总：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage214_stage78_execution_slippage_mc_suite_summary_stage214_stage78_execution_slippage_mc_suite_v1.csv`
- 滑点压力：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage214_stage78_execution_slippage_mc_suite_slippage_stress_stage214_stage78_execution_slippage_mc_suite_v1.csv`
- 蒙特卡洛摘要：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage214_stage78_execution_slippage_mc_suite_monte_carlo_summary_stage214_stage78_execution_slippage_mc_suite_v1.csv`
- 蒙特卡洛明细：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage214_stage78_execution_slippage_mc_suite_monte_carlo_simulations_stage214_stage78_execution_slippage_mc_suite_v1.csv`
- 同日权益：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage214_stage78_execution_slippage_mc_suite_same_day_daily_stage214_stage78_execution_slippage_mc_suite_v1.csv`
- T+1权益：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage214_stage78_execution_slippage_mc_suite_t1_next_open_daily_stage214_stage78_execution_slippage_mc_suite_v1.csv`
- 同日成交：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage214_stage78_execution_slippage_mc_suite_same_day_trades_stage214_stage78_execution_slippage_mc_suite_v1.csv`
- T+1成交：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage214_stage78_execution_slippage_mc_suite_t1_next_open_trades_stage214_stage78_execution_slippage_mc_suite_v1.csv`

## 过拟合反思

- 运行前判断：否。本轮没有选择参数，只检验执行与尾部。
- 运行后判断：否，但不能因为T+1略好就切换正式执行口径。
- 原因：
  - T+1开盘只是更保守的代理成交模型之一。
  - 蒙特卡洛暴露的是路径风险，不应被用来反向优化参数。

## 继续价值反思

- 运行前判断：有价值。它直接检验第78能不能走向实盘。
- 运行后判断：有价值，但结论是黄灯。
- 下一步：
  - 做资金曲线尾部治理：降低单笔资金上限、冷启动更小资金、回撤后降档。
  - 做影子盘日报和真实盘口对账，验证开盘代理价与真实可成交价差异。
  - 做最差交易簇归因，找出trade-block爆仓路径来自哪些品种/方向/风险模式。

## 合入建议

- 是否更新本线 `LINE.md`：建议后续整理时补充“第78通过T+1/滑点压力，但Monte Carlo尾部黄灯”。
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
