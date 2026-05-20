# Stage005 入场执行与两日止损锚点反事实

- line_id：`futures_swing_no_lower_shadow`
- 当前模式：`day`
- 记录时间：2026-05-15 16:31 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / 当前分支
- 阶段性质：执行结构与风险锚点反事实
- 是否重要突破：否，但有结构性发现
- 是否触发A/B：否，所有版本仍未形成独立正收益优势

## 外部调研与判断

- 参考资料：
  - StockGro Bullish Marubozu：强调完美无影线稀少，形态需要结合趋势结构、支撑阻力和确认；交易方式可选择突破/次日开盘，也可等待回踩到实体中部或前阻力回踩。
  - Traders.MBA Marubozu Candlestick Strategy：把立即入场归为 aggressive entry，把等待回踩到 Marubozu 实体内归为 conservative entry，止损通常放在蜡烛低点下方。
  - ChoiceIndia Marubozu Pattern：明确提示不要 chase candle，错过初始动能后更合理的是等 pullback/retracement。
- 我的判断：
  - 外部经验与 Stage002/Stage004 归因方向一致：问题不是“没有足够多近似无下影线”，而是第三天开盘追价后很容易遇到首日反向波动。
  - 本阶段不能加趋势、成交量、RSI 或品种过滤；只允许测试执行价和止损锚点，避免把归因实验变成扫参救收益。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_no_lower_shadow_swing_entry_timing_counterfactual.py`
- 修改脚本：
  - `tests/test_qmt_no_lower_shadow_swing.py`
- 删除脚本：无
- 新增参数：
  - `entry_timing_variant`：`open`、`pullback_signal2_close`、`pullback_signal2_mid`
  - `stop_mode`：`signal2_low`、`two_signal_low`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-01 到 2026-04-30
- 账户规模：500,000
- 成本口径：沿用合约 metadata 中的 `rate`、`slippage`；本次结果中 commission 为 0，slippage 进入现金扣减。
- 样本过滤：eligible 全市场主力映射；信号固定为 `strict`，不做放松下影线。
- 策略/归因口径：
  - `open`：第三天开盘入场。
  - `pullback_signal2_close`：第三天只在最低价触及信号2收盘价时入场。
  - `pullback_signal2_mid`：第三天只在最低价触及信号2实体中位时入场，中位价按最小跳动向上取整，避免乐观。
  - 回踩单只允许入场日触发；未触发记为 `entry_pullback_not_touched`。
  - 回踩单日内路径采用保守假设：若同日最低价触及止损，按入场后止损处理。
  - `signal2_low`：初始止损为第二根信号K线低点。
  - `two_signal_low`：初始止损为两根信号K线低点的更低值。

## 结果

### 全部组合

| 入场 | 止损锚点 | 开仓数 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 胜率 | 初始止损次数 | 初始止损净损益 | 总滑点 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `open` | `signal2_low` | 86 | 463,825 | -7.235% | -13.5818% | -0.4146 | 23.2558% | 33 | -80,505 | 21,130 |
| `open` | `two_signal_low` | 71 | 497,005 | -0.599% | -5.9223% | -0.0440 | 29.5775% | 13 | -29,145 | 10,590 |
| `pullback_signal2_close` | `signal2_low` | 78 | 448,775 | -10.245% | -13.6387% | -0.7764 | 20.5128% | 33 | -76,945 | 16,420 |
| `pullback_signal2_mid` | `signal2_low` | 63 | 460,100 | -7.980% | -13.3075% | -0.4233 | 25.8065% | 33 | -87,925 | 26,460 |
| `pullback_signal2_close` | `two_signal_low` | 64 | 478,980 | -4.204% | -7.8281% | -0.4520 | 23.4375% | 13 | -29,785 | 8,130 |
| `pullback_signal2_mid` | `two_signal_low` | 53 | 486,615 | -2.677% | -6.2289% | -0.2134 | 37.7358% | 13 | -29,970 | 10,280 |

### 最好组合：`open + two_signal_low`

- 期末权益：`497,005`
- 总收益：`-0.599%`
- 最大回撤：`-5.9223%`
- Sharpe：`-0.0440`
- 总滑点：`10,590`
- 总交易次数：`187`
- 胜率：`29.5775%`
- 候选数/开仓数：`112` / `71`
- 退出原因：
  - `long_initial_stop`：13 笔，净损益 `-29,145`
  - `long_trailing_stop`：42 笔，净损益 `14,200`
  - `long_gap_stop`：10 笔，净损益 `-3,555`
  - `rollover_forced_exit`：6 笔，净损益 `15,505`
- 年度拆分：
  - 2020：`-85`
  - 2021：`-4,685`
  - 2022：`-2,445`
  - 2023：`4,530`
  - 2024：`-11,230`
  - 2025：`11,130`
  - 2026：`-210`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_entry_timing_counterfactual_stage005_report.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_entry_timing_counterfactual_stage005_summary.csv`
- summary_json：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_entry_timing_counterfactual_stage005_summary.json`
- best_daily：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_stage005_open_twosignallow_daily.csv`
- best_trades：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_stage005_open_twosignallow_trades.csv`
- best_candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_stage005_open_twosignallow_candidates.csv`
- best_roundtrips：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_stage005_open_twosignallow_roundtrips.csv`

## 结论

- 本阶段结论：
  - “第三天等回踩再入场”没有改善，反而在 `signal2_low` 止损下收益更差；这说明问题不只是入场价格高，而是回踩触发的样本本身常常继续走弱。
  - 真正有效的结构变化是把初始止损从信号2低点放宽到两根信号K线的低点：初始止损次数从 33 降到 13，初始止损亏损从 `-80,505` 降到约 `-29,145`。
  - 但最好组合仍为负收益，且总滑点 `10,590` 大于最终净亏 `2,995`，说明这条边际非常薄，交易成本一变就可能改变结论。
  - `open + two_signal_low` 更像“把过紧止损修正为合理风险锚点后接近零边际”，不是可以升级的正收益策略。
- 是否进入下一步：谨慎进入一次非参数化归因，不继续放松信号，不做趋势/成交量/品种筛选。
- 下一步：
  - 只做 `open + two_signal_low` 的成本敏感与腿部归因：首日减半腿、剩余 runner、滑点对净值的影响。
  - 如果扣除滑点后也只呈现微弱毛利，或收益主要来自少数年份/品种，则停止本线。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：仍未明显过拟合，但已经接近需要停止扩展的边界。
- 原因：
  - 本阶段只测试预先声明的执行结构和两日止损锚点，没有根据结果增加指标过滤。
  - `two_signal_low` 的改善有第一性原理解释：两根连续无下影线的完整形态失效位应该是两日结构低点，而不一定是第二天低点。
  - 但如果继续为了把 `-0.599%` 变正而筛品种、筛年份、筛趋势，很容易进入过拟合。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：只剩一次归因价值，不再有大规模调参价值。
- 原因：
  - 有价值的地方：Stage005 明确反证了回踩入场，确认止损锚点才是更关键的结构问题。
  - 价值有限的地方：最好组合仍是负收益，且年度稳定性不够；2023/2025 为正，但 2021/2024 仍拖累明显。
  - 人类经验直觉上，这类形态更像“短促动能痕迹”而不是能独立穿越周期的 alpha；缺少更高层次市场状态约束时，不应强行升级。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage005 后把下一步收束为成本/腿部归因。
- 是否更新 `research/registry.md`：是，更新最新阶段与下一步。
- 是否追加根目录 `memory.md/back_log.md`：否，尚非重要突破、正式候选或路线废弃。
