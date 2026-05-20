# Stage009 周线顺势回撤后第一根无下影线点火

- line_id：`futures_swing_no_lower_shadow`
- 当前模式：`day`
- 记录时间：2026-05-15 20:19 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / 当前分支
- 阶段性质：看大做小版本 B 回测
- 是否重要突破：否，只有弱正收益
- 是否触发A/B：否，Sharpe 过低且成本敏感不通过

## 外部调研与判断

- 参考资料：沿用 Stage007 调研。
  - AQR/Moskowitz-Ooi-Pedersen Time Series Momentum：期货自身过去 12 个月趋势对未来收益有正向预测证据。https://www.aqr.com/insights/research/journal-article/time-series-momentum
  - Elder Triple Screen/多周期系统：高周期定方向，中周期找位置，小周期做入场 timing。https://traders.mba/support/how-to-implement-the-triple-screen-trading-system/
  - MultiTF-EMA-Backtest GitHub：工程上常见高周期 EMA 趋势确认 + 低周期触发。https://github.com/shubhamlodha21/MultiTF-EMA-Backtest
  - NinjaTrader Top-Down Futures：期货多周期 top-down 的主要价值是风险管理和避免低周期逆势交易。https://ninjatrader.com/Futures/Blogs/top-down-analysis-trading-guide
- 我的判断：
  - 本阶段实现 Stage007 预先定义的 B 版：高周期顺势不变，小周期从“连续两天加速”改为“回撤后第一根点火”。
  - 这是不同触发机制，不是对 A 版参数扫优。
  - 本阶段仍不加成交量、RSI、强势品种池或年度筛选。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_no_lower_shadow_swing_top_down_pullback_stage009.py`
- 修改脚本：
  - `tests/test_qmt_no_lower_shadow_swing.py`
- 删除脚本：无
- 新增参数：
  - `daily_ma_days=20`
  - `pullback_lookback_days=5`
  - `pullback_ma_buffer_pct=0.01`
  - `recent_ignition_block_days=3`
  - `stop_mode=pullback_low`
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
- 中周期口径：
  - 信号日前 5 日最低的连续收益指数触及/低于 20 日均线 1% 缓冲范围。
- 小周期口径：
  - 信号日为第一根 strict `open == low` 且 `close > open` 的无下影线上涨K。
  - 信号日收回 20 日均线上方且高于前一日连续收益指数收盘。
  - 信号日前 3 日不能已有 strict 无下影线点火。
  - 次日开盘做多。
  - 初始止损为信号日和此前 5 日回撤窗口低点。

## 结果

- 期末权益：`502,385`
- 总收益：`0.4770%`
- 最大回撤：`-5.1529%`
- Sharpe：`0.0481`
- 总滑点：`13,050`
- 总交易次数：`515`
- 完整回合：`215`
- 开仓数：`216`
- 期末未平仓：`1`
- 胜率：`33.0233%`
- 候选数：`2,692`
- 周线门通过数：`996`
- 回撤点火条件通过数：`1,313`
- 近期点火阻断数：`310`
- 跳过原因：
  - `weekly_trend_gate_failed`：1,478
  - `pullback_setup_failed`：400
  - `risk_budget_below_one_contract`：253
  - `weekly_trend_warmup_missing`：154
  - `rollover_between_signal_and_entry`：106
  - `recent_ignition_already_fired`：52
  - `pullback_stop_history_missing`：33
- 退出原因：
  - `long_trailing_stop`：158 笔，净损益 `37,845`
  - `long_initial_stop`：14 笔，净损益 `-31,135`
  - `long_gap_stop`：31 笔，净损益 `-5,250`
  - `rollover_forced_exit`：12 笔，净损益 `375`
- 腿部归因：
  - `first_day_half_exit`：84 次，净损益 `4,400`
  - `long_trailing_stop` 成交腿：158 次，净损益 `34,880`
  - `long_initial_stop` 成交腿：14 次，净损益 `-30,475`
- 成本敏感：
  - 0 倍滑点：已平仓净损益约 `14,875`
  - 1 倍滑点：已平仓净损益约 `1,835`
  - 2 倍滑点：已平仓净损益约 `-11,205`
  - 3 倍滑点：已平仓净损益约 `-24,245`

### 年度拆分

| 年份 | 净损益 | 回合数 | 胜率 | 滑点 |
| --- | ---: | ---: | ---: | ---: |
| 2020 | 13,405 | 32 | 43.7500% | 2,350 |
| 2021 | -7,595 | 37 | 43.2432% | 1,680 |
| 2022 | -8,325 | 21 | 19.0476% | 1,510 |
| 2023 | 6,000 | 50 | 36.0000% | 2,220 |
| 2024 | -3,975 | 29 | 27.5862% | 1,310 |
| 2025 | 345 | 30 | 26.6667% | 2,510 |
| 2026 | 1,980 | 16 | 18.7500% | 1,460 |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_stage009_weekly_pullback_ignition_top_down_report.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_stage009_weekly_pullback_ignition_top_down_summary.json`
- statistics：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_stage009_weekly_pullback_ignition_statistics.json`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_stage009_weekly_pullback_ignition_daily.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_stage009_weekly_pullback_ignition_trades.csv`
- candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_stage009_weekly_pullback_ignition_candidates.csv`
- roundtrips：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_stage009_weekly_pullback_ignition_roundtrips.csv`

## 结论

- 本阶段结论：
  - B 版比 A 版更接近正确方向：样本从 15 笔扩大到 216 次开仓，收益从 `-0.8590%` 转为 `0.4770%`。
  - 机制上也更合理：runner 的 `long_trailing_stop` 合计正贡献 `37,845`，说明“回撤后第一根点火”比“连续两天加速后追入”更能跑出后续空间。
  - 但收益非常薄，Sharpe 只有 `0.0481`，两倍滑点即转为明显亏损；这不是可升级策略。
  - 年度表现不稳定，2021/2022/2024 为负，2025 只有微利。
  - 期末还有 1 个未平仓 TA.CZCE 浮盈约 `560`，不影响大结论但说明最终净值仍含少量 mark-to-market。
- 是否进入下一步：不建议继续在本线加过滤器。
- 下一步：
  - 若继续，只能做只读归因：成本敏感、按交易腿拆分、最差年份/品种复盘。
  - 不建议继续加过热过滤、成交量过滤或品种筛选；那会从“验证机制”滑向“救结果”。
  - 当前线应暂时降为“弱线索保留”，等待真实 OOS 或更强触发证据。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：轻微风险开始出现，但尚未实质过拟合。
- 原因：
  - B 版是 Stage007 预先声明的机制，并非看到 A 失败后任意扫条件。
  - 但 B 版已经引入 `5日回撤`、`20日均线`、`1%缓冲`、`3日冷却` 等结构参数，继续微调这些参数会很容易过拟合。
  - 结果只是微弱转正，不能用来倒推优化。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有研究价值，但没有策略升级价值。
- 原因：
  - 有价值：证明看大做小 + 回撤后第一根点火，比孤立K线和连续加速追入更符合市场结构。
  - 没有升级价值：收益/成本比太薄，年度稳定性不足，滑点敏感不过关。
  - 人类盘感上，恢复K可以作为趋势中“有人重新接力”的痕迹，但一根日线形态仍不足以稳定穿越周期。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 B 版弱正但不升级。
- 是否更新 `research/registry.md`：是，更新最新阶段与状态。
- 是否追加根目录 `memory.md/back_log.md`：否，尚非重要突破、正式候选或路线废弃。
