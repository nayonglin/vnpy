# Stage104 Stage079剩余短持有体验缺口归因

- 时间：2026-05-27 20:03 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 阶段性质：只读归因；固定 Stage103 `broker10_guard`，定位未达理想目标的3个月/6个月持有体验缺口。
- 是否重要突破版本：否。重要边界确认：Stage103 已经通过晋级分数，但距离用户理想目标仍有明显差距；剩余缺口不是 `broker10_guard` 小参数能解决。
- 本次脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage404_stage079_residual_holding_gap_attribution.py`
- 输出报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage404_stage079_residual_holding_gap_attribution_report_stage404_stage079_residual_holding_gap_attribution_v1.md`
- 输出图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage404_stage079_residual_holding_gap_attribution_chart_stage404_stage079_residual_holding_gap_attribution_v1.png`

## 开始前反思

- 是否在过拟合：否。本阶段只读取 Stage103 固定候选的滚动持有期窗口，不创建交易规则、不调阈值、不挑品种。
- 是否仍有价值继续做：是。Stage103 虽然满足晋级分数，但没有达到多个理想体验目标；继续前必须知道剩余坏体验来自哪里，避免盲目扫参。

## 外部调研与判断

- 参考资料：
  - pfolio, *Ulcer index: measuring drawdown severity over time*：https://www.pfolio.io/academy/ulcer-index
  - PerformanceAnalytics `UlcerIndex` 文档：https://timelyportfolio.github.io/PerformanceAnalytics/reference/UlcerIndex.html
  - jQuantStats GitHub：https://github.com/Jebel-Quant/jquantstats
  - Berkeley drawdown/path dependency 研究资料：https://cdar.berkeley.edu/sites/default/files/2015-04.pdf
- 我的判断：
  - 持有体验不是单点收益问题，而是路径顺序、回撤深度、回撤持续时间的组合。
  - Stage103 的剩余问题应先按滚动窗口拆解为：左尾收益、破20回撤、Ulcer、水下天数、启动日前状态、C3贡献和xsmom贡献。
  - 这类归因只能决定下一步方向，不能直接把某个日期、月份或坏窗口状态硬编码为规则。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage404_stage079_residual_holding_gap_attribution.py`
- 新增参数：
  - 固定诊断窗口：`90` 天、`180` 天。
  - 输出归因特征：启动日前20/60/120日收益、启动日全路径回撤、窗口C3 PnL、窗口xsmom PnL、xsmom活跃率、Stage101 scale、guard跳过天数。
  - 坏窗口分组：收益底部5%、破20回撤、Ulcer顶部5%、水下天数顶部5%。
- 修改参数：无正式策略默认修改。
- 删除参数：无。

## 目标缺口

Stage103 `broker10_guard` 仍未达成的理想目标：

| 指标 | 3个月实际 | 3个月目标 | 6个月实际 | 6个月目标 |
| --- | ---: | ---: | ---: | ---: |
| 5%分位收益 | -10.9102% | > -8.0% | -0.6313% | > 0.0% |
| 中位收益 | 13.4787% | >= 13.52% | 35.8014% | >= 33.92% |
| 正收益率 | 74.6961% | >= 80.0% | 94.3688% | >= 95.0% |
| 年化低于5%概率 | 27.9604% | <= 22.0% | 8.4467% | <= 6.0% |
| 最差期内回撤 | -28.9792% | >= -29.20% | -28.9792% | >= -29.70% |
| 破20回撤率 | 16.6141% | <= 12.0% | 35.7109% | <= 25.0% |
| 破30回撤率 | 0% | 0% | 0% | 0% |
| Ulcer P95 | 16.4708 | <= 15.0 | 19.1255 | <= 17.0 |
| P95最长水下天数 | 88 | <= 80 | 167 | <= 150 |

## 坏窗口归因

收益底部5%窗口对比：

| 口径 | 3个月底部5% | 其他3个月 | 差值 | 6个月底部5% | 其他6个月 | 差值 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 候选收益 | -15.2410% | 22.1159% | -37.3570pp | -10.4390% | 49.4417% | -59.8808pp |
| 相对Stage079 | +0.5605pp | -0.0531pp | +0.6136pp | +0.3330pp | +0.2805pp | +0.0526pp |
| C3窗口PnL | -437,842 | 1,299,281 | -1,737,122 | -245,814 | 2,572,334 | -2,818,149 |
| xsmom窗口PnL | +6,188 | +29,455 | -23,267 | +26,441 | +60,347 | -33,906 |
| xsmom活跃率 | 26.44% | 51.65% | -25.21pp | 27.89% | 53.83% | -25.94pp |
| Stage101平均scale | 0.1770 | 0.4295 | -0.2525 | 0.1902 | 0.4435 | -0.2534 |

启动日前状态：

- 3个月收益底部5%窗口的启动日前60日收益均值为 `45.7990%`，其他窗口为 `12.6712%`，高 `33.1278pp`。
- 6个月收益底部5%窗口的启动日前60日收益均值为 `29.8507%`，其他窗口为 `13.5773%`，高 `16.2734pp`。
- 启动日通常接近或处在全路径高位：3个月底部5%启动日全路径回撤均值 `-4.7192%`，其他窗口 `-12.8625%`；6个月底部5%为 `-6.1276%`，其他窗口 `-12.9844%`。
- 典型坏窗口集中在 `2021-05`、`2021-11`、`2022-03`、`2022-07` 以及早期 `2020-01/02`。其中 `2022-07` 的3个月底部尾部率高达 `61.29%`。

## 结论

- Stage103 候选在坏窗口里并没有拖累 Stage079：3个月底部5%窗口平均相对 Stage079 好 `+0.5605pp`，6个月底部5%窗口平均好 `+0.3330pp`。
- 剩余痛点来自 C3 本体的趋势暴涨后反转/长水下路径：坏窗口启动前经常已经大涨且接近净值高位，随后 C3窗口PnL显著为负。
- xsmom 卫星在坏窗口平均仍为正，但活跃率和scale明显偏低，不能靠继续调 `0.5/10%/63日` 把体验推到理想目标。
- `broker10_guard` 继续作为当前执行相对候选保留；本阶段不产生新候选。

## 后续规划和TODO

1. 不继续调 Stage103 的 `0.5/10%/63日`、动量窗口、保证金缓冲小数或 xsmom篮子细节。
2. 下一步只允许研究新结构：专门覆盖“趋势暴涨后反转/长水下恢复”的低相关收益源或外生状态层，而不是直接砍 C3 仓位。
3. 可考虑 Stage105 方向：寻找一个非价格同源、低交易频率、在 `prior60_return` 高且接近权益高位后仍能提供保护或正收益的承载；若只是 C3 暴涨后减仓，必须先证明不牺牲长期收益。
4. 工程化/paper路径仍可并行：固定 `broker10_guard` 做复跑配置和影子盘日报，但不把它当作已达成所有理想目标。

## 结束后反思

- 是否在过拟合：不是。本阶段没有新增交易规则；只做跨所有启动日的滚动窗口归因。
- 是否还有价值继续做：有，但方向变窄。继续优化的价值不在 Stage103 小参数，而在寻找能覆盖趋势反转和长水下的新结构。

