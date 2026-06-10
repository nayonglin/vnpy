# Stage028 开仓日持仓量变化与盈亏关系验证

- 时间：2026-06-09 14:17 CST
- line_id：`futures_trend_winner_trade_forensics`
- 工作模式：`day`
- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage754_entry_oi_change_winner_loser.py`
- 决策：`entry_oi_change_candidate_watch_not_trade_rule`

## 外部/GitHub调研结论

- 期货 OI 常被用作趋势确认或资金参与度指标，但资料普遍强调它是确认工具，不是独立入场信号。
- 常见解释是：价格沿趋势方向运动且 OI 增加，说明新资金参与，趋势更可能有延续性；单看 OI 上升则容易过宽。
- 本次判断：用户目测有合理第一性原理，值得做只读验证；但不能直接把 OI 上升写成正式加仓/过滤规则。

## 本次变更

- 新增只读统计脚本，不修改正式策略、不连接 CTP、不调用下单。
- 数据源：Stage719 正式版 closed lots + 本地合约日线 `close_oi`。
- 盈亏定义：
  - 主口径：理论方向收益率，多头 `(exit-entry)/entry`，空头 `(entry-exit)/entry`。
  - 复核口径：实际 realized PnL；本批样本符号与理论收益一致。
- OI 特征：
  - `entry_oi_gt_prev1`：开仓日 `close_oi` 大于前1个交易日。
  - `entry_oi_gt_prev2`：开仓日 `close_oi` 大于前2个交易日。
  - `recent2_any_oi_up`：最近两个日变化中至少有一天 OI 上升。
  - `recent2_both_oi_up`：最近两个日变化都 OI 上升。
  - `entry_oi_price_confirm`：开仓日 OI 上升，且价格也沿交易方向运动。

## 样本

- closed lots：`320`
- OI 可用样本：`277`
- OI 缺失样本：`43`
- 理论盈利样本：`145`，其中 OI 可用 `128`
- 理论亏损样本：`175`，其中 OI 可用 `149`

## 全样本统计

| 特征 | 盈利单 | 亏损单 | 差值 |
| --- | ---: | ---: | ---: |
| 开仓日 OI > 前1日 | `61.7188%` | `42.9530%` | `+18.7657pp` |
| 开仓日 OI > 前2日 | `66.4063%` | `55.0336%` | `+11.3727pp` |
| 最近两日任一天 OI 上升 | `84.3750%` | `77.1812%` | `+7.1938pp` |
| 最近两日连续 OI 上升 | `40.6250%` | `30.2013%` | `+10.4237pp` |
| OI 上升 + 价格方向确认 | `57.8125%` | `26.1745%` | `+31.6380pp` |

关键结论：用户目测方向成立，但“最近两日任一天 OI 上升”太宽，亏损单也大量满足；最强的是 `entry_oi_price_confirm`。

## Top/Worst 对照

公平取 OI 可用样本里 top N 理论盈利 vs worst N 理论亏损：

| N | 组别 | 开仓日 OI > 前1日 | 最近两日连续 OI 上升 | OI+价格确认 | OI 1日变化中位数 |
| ---: | --- | ---: | ---: | ---: | ---: |
| 29 | top_profit | `79.3103%` | `62.0690%` | `75.8621%` | `+3.1793%` |
| 29 | worst_loss | `41.3793%` | `20.6897%` | `20.6897%` | `-1.2528%` |
| 50 | top_profit | `68.0000%` | `50.0000%` | `66.0000%` | `+2.5013%` |
| 50 | worst_loss | `38.0000%` | `22.0000%` | `20.0000%` | `-1.2350%` |
| 100 | top_profit | `61.0000%` | `38.0000%` | `58.0000%` | `+1.6825%` |
| 100 | worst_loss | `39.0000%` | `27.0000%` | `18.0000%` | `-1.0143%` |

视觉图册里的强盈利/强亏损对照中，OI 特征很明显。

## 多空分开

| 方向 | 结果 | 样本 | 开仓日 OI > 前1日 | OI+价格确认 |
| --- | --- | ---: | ---: | ---: |
| long | profit | `109` | `61.4679%` | `57.7982%` |
| long | loss | `118` | `43.2203%` | `24.5763%` |
| short | profit | `19` | `63.1579%` | `57.8947%` |
| short | loss | `31` | `41.9355%` | `32.2581%` |

多空分开后仍然成立，说明不是单纯长单样本偏差。

## 跨年稳定性

- `entry_oi_gt_prev1` 的盈利-亏损差值：
  - 2020：`+43.5897pp`
  - 2021：`+22.3708pp`
  - 2022：`+22.0690pp`
  - 2023：`+15.0794pp`
  - 2024：`+0.7519pp`
  - 2025：`-1.3889pp`
  - 2026：样本仅 `3`，不可解释
- 结论：2020-2023 很强，2024-2025 明显变弱，因此不能直接作为正式规则。

## 输出文件

- enriched：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage754_entry_oi_change_winner_loser_enriched_stage754_entry_oi_change_winner_loser_v1.csv`
- group stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage754_entry_oi_change_winner_loser_group_stats_stage754_entry_oi_change_winner_loser_v1.csv`
- feature quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage754_entry_oi_change_winner_loser_feature_quality_stage754_entry_oi_change_winner_loser_v1.csv`
- year stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage754_entry_oi_change_winner_loser_year_stats_stage754_entry_oi_change_winner_loser_v1.csv`
- direction stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage754_entry_oi_change_winner_loser_direction_stats_stage754_entry_oi_change_winner_loser_v1.csv`
- top contrast：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage754_entry_oi_change_winner_loser_top_contrast_stage754_entry_oi_change_winner_loser_v1.csv`

## 过拟合与继续价值反思

- 本次是否过拟合：否。它验证的是用户从图册中提出的单一、事前可见、可解释特征，没有调参和策略改动。
- 如果直接上线为硬过滤：有过拟合风险，原因是 2024-2025 差异明显变弱，且“最近两日任一天 OI 上升”过宽。
- 是否有价值继续：有。最值得继续的是 `OI 上升 + 价格方向确认`，可以作为候选质量加分项或入场后确认标签，而不是单独入场条件。

## TODO

- 下一步建议做只读验证：
  1. `entry_oi_price_confirm` 是否能提升 post-entry 5/10/20 根 MFE/MAE。
  2. 与成交量同步放大组合：`OI 上升 + volume 高于20日中位数`。
  3. 分品种/滚动阶段检查，排除主力合约换月导致的 OI 假信号。
