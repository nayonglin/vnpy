# Stage231 Stage526候选退出形态前沿

- 研究线：`futures_trend_drawdown30_preserve_return`
- 运行时间：`2026-06-01 21:25 CST`
- 阶段性质：A/C 最小真实引擎验证；固定 `r080_pc25_maxpos4 = risk0.80 + 单产品保证金cap25% + 最大活跃产品4`，只比较已有退出开关。
- 是否重要突破：否。重要结论是反证：现有退出开关不能替换 Stage526 主候选；当前 ATR 中位止损不应关闭。
- 运行前过拟合判断：否。只测试已有低自由度开关，不新增品种黑名单、日期过滤或连续阈值扫描。
- 运行前继续价值判断：是。Stage229 已把未完成风险定位到 2022 长回撤与 3x 成本压力，退出形态是最直接的机制验证。

## 外部调研与判断

- 参考资料：
  - Trend following, stop losses and trading frequency: <https://link.springer.com/article/10.1057/jam.2013.11>
  - Commodity futures trend-following re-examination: <https://www.sciencedirect.com/science/article/pii/S037842660900199X>
  - ATR trailing stop 实务说明与 whipsaw 风险：<https://www.incrediblecharts.com/indicators/atr_average_true_range_trailing_stops.php>
- 判断：趋势策略退出通常依赖均线/通道/止损框架，但 stop-loss/ATR trailing 并不天然提升趋势策略；过紧退出会在震荡中反复 whipsaw。因此本阶段只做已有粗结构开关验证，不扫 ATR 倍数、不调小数。

## 版本变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage531_stage526_exit_shape_frontier.py`
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage531_stage526_exit_shape_frontier_summary_stage531_stage526_exit_shape_frontier_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage531_stage526_exit_shape_frontier_cost_stress_stage531_stage526_exit_shape_frontier_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage531_stage526_exit_shape_frontier_rolling_holding_stage531_stage526_exit_shape_frontier_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage531_stage526_exit_shape_frontier_cost_failure_windows_stage531_stage526_exit_shape_frontier_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage531_stage526_exit_shape_frontier_bad_window_product_attr_stage531_stage526_exit_shape_frontier_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage531_stage526_exit_shape_frontier_report_stage531_stage526_exit_shape_frontier_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage531_stage526_exit_shape_frontier_chart_stage531_stage526_exit_shape_frontier_v1.png`
- 修改正式策略默认参数：无。
- 删除参数：无。

## 预声明实验臂

| 版本 | 改动 |
| --- | --- |
| `r080_pc25_maxpos4_control` | Stage526 主候选复刻。 |
| `r080_pc25_maxpos4_no_atr_mid` | 关闭已有 `atr_2x_mid_stop_enabled`。 |
| `r080_pc25_maxpos4_align_break` | 开启已有 `exit_on_alignment_break`。 |
| `r080_pc25_maxpos4_profit_giveback` | 开启已有 `enable_profit_giveback_stop`，沿用默认粗档 `8%/70%/3%`。 |

## 预声明晋级门槛

- 正常成本：最大回撤 `>= -40%`。
- 正常成本：exact broker10 保证金/权益全程 `<= 100%`。
- 2x成本：最大回撤 `>= -40%`。
- 相对 control：总收益不低于 `95%`，最大回撤不劣化，Ulcer 不劣化。
- 任意启动体验：63日和126日 p05 收益不劣化。
- 若只改善 3x 成本但损害上述指标，只能作为研究经验，不能替换候选。

## 全周期结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Ulcer | Sharpe | 最大broker10保证金/权益 | 穿100天数 | 总滑点 | 总交易次数 | 胜率/非零日 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| control | 23,369,505 | 3699.9195% | -36.2670% | 14.4691 | 1.6385 | 99.7299% | 0 | 1,342,190 | 905 | 53.6330% |
| no_atr_mid | 22,462,505 | 3552.4398% | -39.5864% | 15.0863 | 1.6091 | 100.1935% | 1 | 1,297,090 | 903 | 53.5581% |
| align_break | 26,660,955 | 4235.1146% | -36.0959% | 14.8060 | 1.6534 | 104.5349% | 2 | 1,604,930 | 925 | 53.2731% |
| profit_giveback | 18,440,615 | 2898.4740% | -36.0402% | 14.4023 | 1.5517 | 104.6165% | 1 | 1,374,030 | 906 | 53.6384% |

## 成本压力

| 版本 | 1x最大回撤 | 2x最大回撤 | 3x最大回撤 |
| --- | ---: | ---: | ---: |
| control | -36.2670% | -39.0565% | -42.0555% |
| no_atr_mid | -39.5864% | -41.6379% | -43.7930% |
| align_break | -36.0959% | -39.9587% | -44.0674% |
| profit_giveback | -36.0402% | -38.9204% | -42.0228% |

## 任意启动持有体验

| 版本 | 63日p05 | 63日中位 | 63日最差窗口DD | 126日p05 | 126日中位 | 126日最差窗口DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| control | -18.2169% | 14.2303% | -34.5484% | -10.9700% | 27.5593% | -34.5484% |
| no_atr_mid | -18.4689% | 14.4909% | -36.0487% | -12.1191% | 27.1689% | -39.5864% |
| align_break | -18.6954% | 13.0018% | -35.6837% | -14.0084% | 24.8082% | -35.6837% |
| profit_giveback | -18.8296% | 15.2130% | -35.7244% | -9.7576% | 28.5248% | -35.7244% |

## 3x最大回撤窗口

| 版本 | 峰值日 | 谷底日 | 3x最大回撤 | 窗口broker10最大 | 窗口滑点 | 窗口交易数 |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| control | 2022-03-09 | 2022-12-07 | -42.0555% | 64.4959% | 73,710 | 68 |
| no_atr_mid | 2021-10-11 | 2022-02-11 | -43.7930% | 65.4145% | 50,280 | 59 |
| align_break | 2021-11-18 | 2022-12-07 | -44.0674% | 100.5621% | 174,845 | 128 |
| profit_giveback | 2022-03-09 | 2022-12-07 | -42.0228% | 66.8877% | 77,510 | 68 |

## 视觉复盘

- 净值图显示 `align_break` 红线收益最高，但这不是干净胜利：它把保证金打穿到 `104.5349%`，3x成本回撤恶化到 `-44.0674%`，63/126日 p05 均低于 control。
- `profit_giveback` 紫线在水下图上局部更平滑，Ulcer 从 `14.4691` 降到 `14.4023`，126日 p05 提升 `1.2124pp`，但总收益只剩 control 的 `78.3388%`，broker10 也打穿 100%，不能替换。
- `no_atr_mid` 关闭 ATR 后全周期收益、最大回撤、Ulcer、2x/3x成本、63/126日左尾全部劣化，说明当前已有 ATR 中位止损不能关。

## 决策

- 决策标签：`exit_shape_no_promotion_keep_stage526_candidate`。
- 保留版本：`r080_pc25_maxpos4_control`。
- 不晋级原因：
  - `no_atr_mid` 证明 ATR 中位止损是有价值保护，关闭后劣化。
  - `align_break` 虽提高收益，但 exact broker10 打穿 100%，3/6个月左尾和 3x 成本压力均更差。
  - `profit_giveback` 只带来轻微 Ulcer/126日左尾改善，代价是收益大幅下降且保证金打穿。
- 后续规划：停止沿已有退出开关继续救 `r080_pc25_maxpos4`；下一步若继续优化，应转向真正可提前识别 2021-2022 长水下状态的低自由度状态变量，或寻找低保证金独立收益源，而不是继续调退出阈值。

## 运行后反思

- 过拟合判断：否。实验主动拒绝了“收益更高但保证金/左尾更差”的 `align_break`，也没有用 2022 窗口继续调阈值。
- 继续价值判断：该退出形态子方向继续价值低；总目标仍有价值，但应换机制，不应继续扫 ATR倍数、盈利回吐阈值、趋势破坏小条件或产品黑名单。
