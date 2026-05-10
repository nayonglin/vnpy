# Stage217 第78正式基准切换30万与三件套复验

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-10 14:05
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：第78正式基准资金口径切换与执行/滑点/蒙特卡洛复验
- 是否重要突破：是，正式基准资金从 `200,000` 切换为 `300,000`
- 是否触发A/B：否，本轮只切换账户规模口径，不修改信号、品种池、风险比例或出入场逻辑

## 外部调研与判断

- 参考资料：
  - 交易策略验证资料普遍强调，策略上线前应同时验证执行延迟、滑点/交易成本压力和 Monte Carlo/bootstrap 路径风险。
  - Monte Carlo 的价值在于暴露交易顺序风险；同一组交易不同发生顺序，可能产生完全不同的最大回撤和资金最低点。
- 我的判断：
  - 本轮不是为了找更好的参数，而是把第78正式基准统一到更接近真实账户的 `300,000` 口径。
  - 期货策略存在手数取整、保证金和并发仓位约束，`200,000` 与 `300,000` 不能简单线性换算，必须实跑。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage217_stage78_30w_execution_slippage_mc_suite.py`
- 修改脚本：
  - `examples/portfolio_backtesting/qmt_roll_official_stage78_config.py`
  - `examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 删除脚本：无
- 新增参数：无
- 修改参数：
  - `OFFICIAL_STAGE78_CAPITAL`：`200,000` -> `300,000`
  - `run_qmt_roll_backtest.py` 默认 `capital`：`200,000` -> `300,000`
  - `run_qmt_roll_backtest.py` 默认 `capital_base`：`200,000` -> `300,000`
  - `OFFICIAL_STAGE78_REFERENCE_METRICS` 更新为30万口径
- 删除参数：无

## 回测口径

- 策略版本：`official_stage78_defensive_v1`
- 账户规模：`300,000`
- 基础风险：`0.045`
- 数据库：项目级 `/Users/bytedance/Desktop/person/vnpy/.vntrader/database.db`
- 运行目录：仓库根目录
- 门禁：Stage196哨兵数据检查通过
- 窗口：`2020-01-01` 至 `2026-04-30`
- 基线执行：同日收盘撮合
- T+1执行：上一交易日生成订单，下一真实合约有实际bar时按开盘价撮合
- 滑点压力：`1x/2x/3x/5x`
- 蒙特卡洛：`1000`次
  - daily block bootstrap：20日块
  - trade block bootstrap：5笔交易块
  - 爆仓概率按路径中途最小权益 `<=0` 计算

## 执行延迟结果

| execution | 期末权益 | 总收益 | 最大回撤 | Sharpe | 交易次数 | 总滑点 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| same_day_close | 5,388,370 | 1,696.1233% | -39.5952% | 1.3113 | 811 | 283,680 |
| t1_next_open | 5,612,110 | 1,770.7033% | -35.8933% | 1.4278 | 813 | 284,180 |

## 执行延迟观察

- T+1次日开盘没有击穿第78，收益和Sharpe反而略高。
- 这不代表真实执行必然优于同日收盘，因为 T+1 开盘仍然是代理撮合模型。
- 它能反证一个关键风险：30万口径下第78仍不是完全依赖同日收盘理想成交。

## 滑点压力结果

| execution | slip | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| same_day_close | 1x | 5,388,370 | 1,696.1233% | -39.5952% | 1.4752 | 283,680 |
| same_day_close | 2x | 5,104,690 | 1,601.5633% | -41.7005% | 1.4050 | 567,360 |
| same_day_close | 3x | 4,821,010 | 1,507.0033% | -43.9253% | 1.3362 | 851,040 |
| same_day_close | 5x | 4,253,650 | 1,317.8833% | -48.7762% | 1.2031 | 1,418,400 |
| t1_next_open | 1x | 5,612,110 | 1,770.7033% | -35.8933% | 1.5769 | 284,180 |
| t1_next_open | 2x | 5,327,930 | 1,675.9767% | -37.7611% | 1.5084 | 568,360 |
| t1_next_open | 3x | 5,043,750 | 1,581.2500% | -39.7291% | 1.4403 | 852,540 |
| t1_next_open | 5x | 4,475,390 | 1,391.7967% | -43.9991% | 1.3059 | 1,420,900 |

## 滑点压力观察

- `5x`滑点下仍保持较高收益，说明30万口径下第78仍不是成本幻觉。
- 但同日口径最大回撤扩大到 `-48.7762%`，已经超过常见实盘心理阈值。
- T+1口径在滑点压力下更平滑，但不能直接把它当成真实成交优势。

## 蒙特卡洛结果

| profile | method | 亏损概率 | 爆仓概率 | DD>30% | DD>40% | DD>50% | 5%收益分位 | 5%最小权益分位 | 5%回撤分位 | 中位收益 | 中位回撤 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| same_day_close | daily_block | 0.9% | 0.0% | 82.9% | 53.1% | 21.8% | 138.0452% | 179,311 | -61.2256% | 1,024.8711% | -40.9641% |
| same_day_close | trade_block | 0.0% | 4.4% | 56.6% | 38.8% | 24.5% | 1,031.1910% | 21,168 | -93.1228% | 1,777.2742% | -33.2649% |
| t1_next_open | daily_block | 0.3% | 0.0% | 69.9% | 32.9% | 8.9% | 186.0480% | 196,718 | -54.6516% | 1,181.7933% | -34.9723% |
| t1_next_open | trade_block | 0.0% | 3.6% | 52.9% | 35.7% | 24.0% | 1,103.6184% | 30,370 | -89.3383% | 1,840.1558% | -31.5105% |

## 蒙特卡洛观察

- 30万口径下最终亏损概率仍低，说明策略均值没有被资金口径切换破坏。
- trade-block路径爆仓概率从旧20万口径约 `7.2%~7.4%` 降到 `3.6%~4.4%`，尾部生存性改善。
- 但极端路径仍可能把权益打到约 `2.1万~3.0万` 的5%最小权益分位，说明风险不是消失，而是从“容易穿仓”变成“极端深回撤”。

## 2026最新参考

- 30万口径下 `2026-01-01` 至 `2026-04-30`：
  - 期末权益：`295,430`
  - 总收益：`-1.5233%`
  - 最大回撤：`-38.5290%`
  - Sharpe：`-0.1212`
  - 总滑点：`4,830`
  - 总交易次数：`29`

## 输出文件

- 汇总：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage217_stage78_30w_execution_slippage_mc_suite_summary_stage217_stage78_30w_execution_slippage_mc_suite_v1.csv`
- 滑点压力：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage217_stage78_30w_execution_slippage_mc_suite_slippage_stress_stage217_stage78_30w_execution_slippage_mc_suite_v1.csv`
- 蒙特卡洛摘要：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage217_stage78_30w_execution_slippage_mc_suite_monte_carlo_summary_stage217_stage78_30w_execution_slippage_mc_suite_v1.csv`
- 蒙特卡洛明细：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage217_stage78_30w_execution_slippage_mc_suite_monte_carlo_simulations_stage217_stage78_30w_execution_slippage_mc_suite_v1.csv`
- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage217_stage78_30w_execution_slippage_mc_suite_report_stage217_stage78_30w_execution_slippage_mc_suite_v1.md`

## 总结判断

- 第78切换30万后，策略收益能力没有被破坏；同日和T+1路径都保持高收益。
- 30万显著改善了部分尾部路径的生存性，trade-block路径爆仓概率下降到 `3.6%~4.4%`。
- 但第78仍不是低回撤策略；30万口径下 `5x`滑点和 Monte Carlo 极端路径仍显示 `40%~50%+` 深回撤风险。
- 当前结论应从“准实盘黄灯”调整为“30万口径更适合影子盘，但仍必须带回撤降档和新增开仓门禁”。

## 过拟合反思

- 运行前判断：否。本轮只把正式资金口径切到真实部署更接近的30万，没有调信号、品种池或风险比例。
- 运行后判断：否。但不能因为30万口径更好，就反向证明30万是最优资金。
- 原因：
  - 30万改善主要来自手数取整和资金缓冲，不是策略逻辑优化。
  - 三件套用于检验执行和尾部风险，不用于调参。

## 继续价值反思

- 运行前判断：有价值。20万与30万在期货手数约束下不能线性外推。
- 运行后判断：有价值。30万口径确实改变了尾部风险和2026冷启动体验。
- 下一步：
  - 重跑30万多周期资金曲线，替换Stage216的20万曲线报告。
  - 做30万口径下 `2022-2023` 弱周期归因。
  - 做30万口径下回撤后降档/暂停新增开仓实验，目标是压低 `DD>40%` 和 trade-block深回撤。

## 合入建议

- 是否更新本线 `LINE.md`：建议后续整理时补充“第78正式基准资金已切换30万，三件套通过收益验证但尾部回撤仍黄灯”。
- 是否更新 `research/registry.md`：暂不更新，由合入者统一整理。
- 是否追加根目录 `memory.md/back_log.md`：建议后续在正式合入摘要中追加。
