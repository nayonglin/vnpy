# Stage001 盈利回撤止盈默认开关消融（Stage249）

- line_id：`futures_trend_profit_giveback_stop`
- 当前模式：`day`
- 记录时间：`2026-05-11 18:18`
- 工作区/分支：本机工作区
- 阶段性质：A vs C 单变量消融
- 是否重要突破：否（首轮结论偏负面）
- 是否触发A/B：是（A=显式OFF，C=显式ON；不设B）

## 外部调研与判断

- 参考资料：
  - [Investopedia: Trailing Stops](https://www.investopedia.com/terms/t/trailingstop.asp)
  - [TradeVAE: Exiting Winning Trades](http://www.tradevae.com/academy/risk-management/stop-losses-exits/exiting-winning-trades/)
- 我的判断：
  - 第一性原理上，盈利回撤止盈是“先让趋势跑起来，再限制利润回吐”，比“RSI过热就减仓”更接近趋势系统的本性。
  - 但它仍然是典型的路径依赖退出规则，非常容易在历史里通过调 `trigger/retain/min_lock` 过拟合。
  - 因此本阶段严格按用户要求，只验证“打开当前默认开关”是否值得，不做任何参数搜索。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage249_stage78_1_profit_giveback_ablation_suite.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-01` 到 `2026-04-30`
- 账户规模：`500,000`
- 成本口径：策略内既有费率/滑点，并做滑点倍数压力 `x1/x2/x3/x5`
- 样本过滤：无
- 策略/归因口径：
  - 基准：`official_stage78_1_defensive_50w_no_sizing_cap`
  - 唯一变量：`enable_profit_giveback_stop` 显式开/关
  - ON 使用当前默认参数：
    - `profit_giveback_trigger_pct=0.08`
    - `profit_giveback_retain_ratio=0.70`
    - `profit_giveback_min_lock_pct=0.03`

## 结果

主回测（since_2020）：

- A（显式 OFF）：`profit_giveback_off`
  - 期末权益：`25,542,885`
  - 总收益：`5008.577%`
  - 最大回撤：`-40.0607%`
  - Sharpe：`1.1295`
  - 总滑点：`1,968,150`
  - 总交易次数：`880`
  - 胜率：`43.2432%`
- C（显式 ON）：`profit_giveback_on`
  - 期末权益：`17,328,525`
  - 总收益：`3365.705%`
  - 最大回撤：`-39.5655%`
  - Sharpe：`1.0308`
  - 总滑点：`1,896,000`
  - 总交易次数：`879`
  - 胜率：`43.1151%`
  - `profit_giveback_stop_update_count=156`

多周期要点（ON - OFF）：

- `since_2020 ~ since_2025`：ON 收益全部显著低于 OFF，仅回撤有轻微改善。
- `phase_2020_2021`：ON 略优（`+22.408%`），但优势很小。
- `phase_2022_2023`：ON 略优（`+3.952%`），仍属于弱优势。
- `phase_2024_2025`：ON 明显更差（`-181.677%`）。
- `since_2026 / phase_2026_latest`：ON 略好（收益 `+0.832%`，回撤改善约 `4.88pct`），但样本很短，不足以推翻长期负面结论。

滑点压力：

- ON 在 `x1/x2/x3/x5` 各档下的收益都低于 OFF。
- `x5` 极端压力下：
  - OFF：总收益 `3434.057%`
  - ON：总收益 `1848.905%`
- 说明该规则并不是“成本压力下更稳健的替代版本”。

## 输出文件

- report：
  - `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage249_stage78_1_profit_giveback_ablation_suite_report_stage249_stage78_1_profit_giveback_ablation_suite_v1.md`
- summary：
  - `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage249_stage78_1_profit_giveback_ablation_suite_main_summary_stage249_stage78_1_profit_giveback_ablation_suite_v1.csv`
  - `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage249_stage78_1_profit_giveback_ablation_suite_multiperiod_summary_stage249_stage78_1_profit_giveback_ablation_suite_v1.csv`
- daily：
  - `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage249_stage78_1_profit_giveback_ablation_suite_main_daily_stage249_stage78_1_profit_giveback_ablation_suite_v1.csv`
- quality：
  - `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage249_stage78_1_profit_giveback_ablation_suite_slippage_stress_stage249_stage78_1_profit_giveback_ablation_suite_v1.csv`

## 结论

- 本阶段结论：
  - 在当前 `78-1` 口径下，只打开默认 `profit_giveback_stop` 开关，会明显伤害长期收益与 Sharpe；最大回撤只改善了一点点。
  - 从结果看，它比 “RSI>95 减半” 更有结构性理由，但当前默认参数依然不适合作为 `78-1` 默认模块。
- 是否进入下一步：有条件继续
- 下一步：
  - 做一次触发归因，统计 `profit_giveback_stop` 具体把哪些持仓提前打掉，确认它是“普遍更稳”还是“少数关键大赢家被截断”。

## 过拟合反思

- 运行前判断：是
- 运行后判断：否
- 原因：理念上有过拟合风险，但本次实验自由度极低，只验证“当前默认开关”，没有做任何参数搜索。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：虽然默认开关首轮为负，但它属于有明确结构意义的路径保护规则，值得做一轮低自由度触发归因，弄清楚为什么它在 `78-1` 上失效。

## 合入建议

- 是否更新本线 `LINE.md`：否（等归因后再更新状态）
- 是否更新 `research/registry.md`：否（遵守并行规则，不频繁改 registry）
- 是否追加根目录 `memory.md/back_log.md`：否（当前只是首轮负结论）

