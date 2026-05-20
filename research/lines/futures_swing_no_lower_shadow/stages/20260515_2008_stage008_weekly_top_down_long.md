# Stage008 周线顺势看大做小 A 版

- line_id：`futures_swing_no_lower_shadow`
- 当前模式：`day`
- 记录时间：2026-05-15 20:08 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / 当前分支
- 阶段性质：看大做小版本 A 回测
- 是否重要突破：否
- 是否触发A/B：否，结果仍未转正

## 外部调研与判断

- 参考资料：沿用 Stage007 调研。
  - AQR/Moskowitz-Ooi-Pedersen Time Series Momentum：期货自身过去 12 个月趋势对未来收益有正向预测证据。https://www.aqr.com/insights/research/journal-article/time-series-momentum
  - Elder Triple Screen/多周期系统：高周期定方向，中周期找位置，小周期做入场 timing。https://traders.mba/support/how-to-implement-the-triple-screen-trading-system/
  - MultiTF-EMA-Backtest GitHub：工程上常见高周期 EMA 趋势确认 + 低周期触发。https://github.com/shubhamlodha21/MultiTF-EMA-Backtest
  - NinjaTrader Top-Down Futures：期货多周期 top-down 的主要价值是风险管理和避免低周期逆势交易。https://ninjatrader.com/Futures/Blogs/top-down-analysis-trading-guide
- 我的判断：
  - 本阶段只验证最干净的 A 版：周线顺势门 + 原 strict 两日无下影线触发 + `two_signal_low` 止损。
  - 不加入过热过滤、成交量、RSI、品种强弱筛选，避免把多周期框架变成事后救收益。
  - 周线状态只使用入场日前上一完整周，当前周未完成数据不可用。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_no_lower_shadow_swing_top_down_weekly_stage008.py`
- 修改脚本：
  - `tests/test_qmt_no_lower_shadow_swing.py`
- 删除脚本：无
- 新增参数：
  - `weekly_ma_weeks=20`
  - `top_down_filter=previous_completed_week_close_gt_ma20_and_ma20_slope_up`
  - `stop_mode=two_signal_low`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-01 到 2026-04-30
- 账户规模：500,000
- 风险比例：0.5% * 上日收盘权益
- 成本口径：沿用合约 metadata 中的 `rate`、`slippage`；本次结果中 commission 为 0，slippage 进入现金扣减。
- 样本过滤：eligible 全市场主力映射。
- 大周期口径：
  - 用主力映射日线构造产品级连续收益指数。
  - 换月首日若没有同合约前一日收盘，则中性化换月价差跳变。
  - 上一完整周的连续收益指数收盘高于 20 周均线，且 20 周均线高于上一周。
- 小周期口径：
  - 连续两根日线 strict `open == low` 且 `close > open`。
  - 第三天开盘做多。
  - 初始止损为两根信号K线低点。
  - 首日若未先触发止损，收盘平掉一半；剩余仓以前一日低点做只上移移动止损。

## 结果

- 期末权益：`495,705`
- 总收益：`-0.8590%`
- 最大回撤：`-1.9902%`
- Sharpe：`-0.1500`
- 总滑点：`2,100`
- 总交易次数：`36`
- 胜率：`26.6667%`
- 候选数/开仓数：`117` / `15`
- 周线门通过数：`35`
- 周线门失败数：`66`
- 周线 warmup 缺失：`13`
- 跳过原因：
  - `weekly_trend_gate_failed`：66
  - `risk_budget_below_one_contract`：17
  - `weekly_trend_warmup_missing`：13
  - `rollover_between_signal_and_entry`：6
- 退出原因：
  - `long_initial_stop`：6 笔，净损益 `-13,425`
  - `long_trailing_stop`：7 笔，净损益 `4,990`
  - `long_gap_stop`：1 笔，净损益 `4,180`
  - `rollover_forced_exit`：1 笔，净损益 `-40`

### 年度拆分

| 年份 | 净损益 | 回合数 | 胜率 | 滑点 |
| --- | ---: | ---: | ---: | ---: |
| 2020 | -2,345 | 5 | 20.0% | 340 |
| 2021 | -2,420 | 3 | 0.0% | 140 |
| 2022 | 810 | 2 | 50.0% | 210 |
| 2023 | 2,730 | 2 | 50.0% | 410 |
| 2025 | 30 | 2 | 50.0% | 380 |
| 2026 | -3,100 | 1 | 0.0% | 620 |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_stage008_weekly_trend_long_top_down_report.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_stage008_weekly_trend_long_top_down_summary.json`
- statistics：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_stage008_weekly_trend_long_statistics.json`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_stage008_weekly_trend_long_daily.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_stage008_weekly_trend_long_trades.csv`
- candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_stage008_weekly_trend_long_candidates.csv`
- roundtrips：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_stage008_weekly_trend_long_roundtrips.csv`

## 结论

- 本阶段结论：
  - 周线顺势门确实降低了风险：相对 Stage005 `open + two_signal_low` 的最大回撤 `-5.9223%`，Stage008 降到 `-1.9902%`。
  - 但收益仍为负，Sharpe 仍为负，说明大周期趋势门只过滤了部分坏环境，没有把 strict 无下影线触发变成正 alpha。
  - 交易数从 71 笔完整回合降到 15 笔，样本进一步变薄；不能把低回撤误读为策略有效。
  - `long_initial_stop` 仍为主要亏损来源，6 笔亏 `-13,425`；runner 有正贡献但不足以覆盖首日失败和成本。
- 是否进入下一步：可以进入 B 版，但只应做一次。
- 下一步：
  - B 版应改为“周线上升趋势中，回撤后第一根 strict 无下影线点火”，不再追连续两天加速。
  - 如果 B 版仍无法转正或样本过薄，则停止无影线动量线。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但继续空间已经很窄。
- 原因：
  - 本阶段只跑预先声明的 A 版，没有扫周线周期、均线组合或品种池。
  - 周线状态使用上一完整周，未使用未来函数。
  - 结果为负，不存在“挑出最优参数”的风险；真正风险在下一步若继续加过热/成交量/品种过滤。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：仍有一次 B 版验证价值，但 A 版本身不值得升级。
- 原因：
  - A 版证明多周期状态能降风险，这说明“看大做小”的方向有解释力。
  - 但 A 版没有证明无下影线连续两天加速是好触发，反而提示它可能太晚。
  - B 版改成“回撤后第一根点火”更符合 top-down 的本质；若 B 也弱，应停止。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage008 A 版结果。
- 是否更新 `research/registry.md`：是，更新最新阶段与下一步。
- 是否追加根目录 `memory.md/back_log.md`：否，尚非重要突破、正式候选或路线废弃。
