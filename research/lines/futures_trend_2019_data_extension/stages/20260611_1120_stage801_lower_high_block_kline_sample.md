# Stage801：lower-high 拦截信号随机30笔K线图

- 记录时间：2026-06-11 11:20 CST
- 研究线：`futures_trend_2019_data_extension`
- 当前工作模式：day
- 是否重要突破版本：否
- 阶段性质：只读法证/图形复盘，不修改策略、不修改候选版本、不新增推广结论

## 本次调研和判断结论

外部快速调研结论：蜡烛图/形态类规则容易出现视觉错觉，单靠图形观察不能证明可交易性；需要固定定义、随机样本、多周期验证。这个结论和 Stage800 年度回测一致：连续 lower-high 作为硬过滤没有通过收益/回撤验证。本阶段只用于看“被拦截的信号到底长什么样”，不能反向救参。

参考：

- TradesViz candlestick pattern backtesting discussion：强调形态需要系统化验证
- QuantStrategy chart-pattern backtesting guide：强调 OOS / walk-forward / 多市场验证
- Reddit/交易社区讨论：提示蜡烛形态容易事后解释

## 样本口径

- 源规则：Stage800 `block_long_two_lower_highs=True`
- 起点：`2018-01`
- 抽样池：最长路径 `2018-01 -> 2026-05-29` 中正式区间内的 lower-high 拦截信号
- 原始拦截信号数：`49`
- 正式区间内可抽样信号数：`47`
- 随机种子：`801`
- 抽样数：`30`
- 每笔图形范围：前 `50` 根K线 + 后 `50` 根K线
- 图形内容：K线、MA5/10/20/40、成交量、OI
- 标记：
  - 蓝色 X：被拦截信号日
  - 黄色背景：触发 `high[t] < high[t-1] < high[t-2]` 的三根K线

## 数据补齐说明

- 本轮先重放 Stage800 规则并补齐 `vt_symbol/date` 上下文，因为 Stage800 原拦截日志只保存了 high 数值，没有合约和日期，无法直接画图。
- 对老合约 K 线，额外读取 `tushare_stage196_stage78_2015_2019` 日线目录。
- 对新合约缺日线的情况，沿用分钟线聚合日线 fallback。
- 最终随机 30 笔均成功画图：
  - missing：`0`
  - 常规日线：`21`
  - 分钟聚合日线：`3`
  - Tushare老合约日线：`6`

## 抽样明细

| rank | block_id | date | vt_symbol | signal | high[t-2] | high[t-1] | high[t] |
| ---: | ---: | --- | --- | --- | ---: | ---: | ---: |
| 1 | 3 | 2018-01-29 | rb1805.SHFE | long_case2 | 3998.0 | 3976.0 | 3968.0 |
| 2 | 5 | 2018-03-28 | AP805.CZCE | long_case2 | 7421.0 | 7420.0 | 7357.0 |
| 3 | 6 | 2018-04-18 | au1806.SHFE | long_case2 | 274.9 | 274.85 | 274.75 |
| 4 | 7 | 2018-12-12 | jm1901.DCE | long_case2 | 1455.0 | 1451.0 | 1438.0 |
| 5 | 8 | 2019-02-12 | sp1906.SHFE | long_case1a | 5540.0 | 5516.0 | 5514.0 |
| 6 | 11 | 2019-11-07 | OI001.CZCE | long_case2 | 7662.0 | 7568.0 | 7503.0 |
| 7 | 12 | 2020-01-10 | ru2005.SHFE | long_case2 | 13250.0 | 13215.0 | 13100.0 |
| 8 | 15 | 2020-05-12 | hc2010.SHFE | long_case2 | 3352.0 | 3340.0 | 3335.0 |
| 9 | 16 | 2020-08-26 | cu2010.SHFE | long_case2 | 51560.0 | 51540.0 | 51490.0 |
| 10 | 17 | 2020-09-07 | SM101.CZCE | long_case2 | 6656.0 | 6544.0 | 6516.0 |
| 11 | 18 | 2020-11-18 | cu2101.SHFE | long_rollover | 53850.0 | 53660.0 | 53060.0 |
| 12 | 19 | 2021-02-24 | hc2105.SHFE | long_case2 | 4905.0 | 4876.0 | 4838.0 |
| 13 | 20 | 2021-05-26 | AP110.CZCE | long_case2 | 6619.0 | 6446.0 | 6304.0 |
| 14 | 23 | 2022-03-29 | fu2205.SHFE | long_case2 | 4334.0 | 4244.0 | 4115.0 |
| 15 | 24 | 2022-06-08 | ru2209.SHFE | long_case2 | 13450.0 | 13345.0 | 13305.0 |
| 16 | 25 | 2022-08-04 | sp2209.SHFE | long_case2 | 7278.0 | 7274.0 | 7216.0 |
| 17 | 29 | 2022-10-17 | au2212.SHFE | long_case2 | 394.0 | 393.0 | 392.08 |
| 18 | 30 | 2023-01-04 | SM305.CZCE | long_case2 | 7708.0 | 7660.0 | 7628.0 |
| 19 | 32 | 2023-07-07 | sp2309.SHFE | long_case2 | 5416.0 | 5382.0 | 5350.0 |
| 20 | 33 | 2023-07-18 | SM309.CZCE | long_case2 | 6730.0 | 6696.0 | 6672.0 |
| 21 | 34 | 2023-07-31 | FG309.CZCE | long_case1a | 1756.0 | 1734.0 | 1725.0 |
| 22 | 36 | 2023-11-02 | jm2401.DCE | long_case2 | 1843.0 | 1833.5 | 1820.0 |
| 23 | 38 | 2024-09-11 | ru2501.SHFE | long_case1a | 16950.0 | 16945.0 | 16895.0 |
| 24 | 39 | 2024-10-11 | hc2501.SHFE | long_case2 | 3653.0 | 3630.0 | 3616.0 |
| 25 | 40 | 2024-12-02 | SM501.CZCE | long_case2 | 6430.0 | 6418.0 | 6414.0 |
| 26 | 44 | 2025-07-10 | lc2509.GFEX | long_case2 | 65180.0 | 65000.0 | 64960.0 |
| 27 | 45 | 2025-08-27 | OI601.CZCE | long_case1a | 9945.0 | 9934.0 | 9888.0 |
| 28 | 46 | 2025-09-29 | FG601.CZCE | long_case2 | 1282.0 | 1269.0 | 1253.0 |
| 29 | 48 | 2025-12-10 | sp2605.SHFE | long_case2 | 5504.0 | 5488.0 | 5464.0 |
| 30 | 49 | 2026-03-18 | FG605.CZCE | long_case2 | 1134.0 | 1106.0 | 1100.0 |

## 输出文件

- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage801_lower_high_block_kline_sample.py`
- 全部拦截信号：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage801_lower_high_block_kline_sample_blocked_signals_stage801_lower_high_block_kline_sample_v1.csv`
- 随机样本：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage801_lower_high_block_kline_sample_sample30_stage801_lower_high_block_kline_sample_v1.csv`
- 图1：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage801_lower_high_block_kline_sample_page01_stage801_lower_high_block_kline_sample_v1.png`
- 图2：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage801_lower_high_block_kline_sample_page02_stage801_lower_high_block_kline_sample_v1.png`
- 图3：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage801_lower_high_block_kline_sample_page03_stage801_lower_high_block_kline_sample_v1.png`
- 图4：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage801_lower_high_block_kline_sample_page04_stage801_lower_high_block_kline_sample_v1.png`
- 图5：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage801_lower_high_block_kline_sample_page05_stage801_lower_high_block_kline_sample_v1.png`
- 图6：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage801_lower_high_block_kline_sample_page06_stage801_lower_high_block_kline_sample_v1.png`

## 反思

- 是否过拟合：否。本阶段只是随机抽样可视化，不根据图形新增交易规则。
- 过拟合风险点：如果看完这30张后继续按某个局部形态微调 lower-high 条件，就会过拟合。
- 是否还有价值继续做：有，但只限于只读归因。它可以帮助理解为什么 Stage800 误杀右尾；不能直接推出新过滤条件。

## 后续规划和 TODO

1. 肉眼复盘这30张时，重点看被拦截日之后是否经常仍然沿原多头方向恢复。
2. 若要量化，下一步应做“被拦截信号后 N 日理论收益分布”，而不是继续改规则。
