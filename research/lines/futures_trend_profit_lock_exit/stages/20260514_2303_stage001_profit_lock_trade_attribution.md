# Stage001 / Stage271：盈利锁定分层交易级归因

- line_id：`futures_trend_profit_lock_exit`
- 当前模式：day
- 记录时间：2026-05-14 23:03 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：新研究线启动；交易级归因；不改正式参数
- 是否重要突破：否
- 是否触发A/B：是，未来可能作为 Stage78-1 退出规则候选；本阶段只做 A 基准归因，不做 C 候选回测

## 外部调研与判断

- 参考资料：
  - Walk-forward optimization / out-of-sample validation
  - Purged cross-validation / embargo for overlapping financial labels
  - Futures trailing stop / trade management literature
- 我的判断：
  - 盈利锁定分层有第一性原理价值：它决定趋势策略如何在“让利润奔跑”和“避免大幅回吐”之间取舍。
  - 但退出阈值是高度易过拟合区域，不能直接用全周期最优收益选参数。
  - 本阶段只做交易级 MFE/MAE/回吐/离场后继续趋势归因，不做逐档参数搜索。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage271_profit_lock_trade_attribution.py`
- 修改脚本：无正式策略修改
- 删除脚本：无
- 新增参数：无正式参数；脚本内固化当前锁盈档位用于归因
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage78-1 当前产物 `2020-01-01` 至 `2026-04/05` 口径
- 账户规模：`500,000`
- 成本口径：沿用 Stage78-1 交易产物；本阶段不重算成本
- 样本过滤：读取 `qmt_roll_official_stage78_1_trades_2020_2026_04.csv`，FIFO 配对平仓腿，并从 vn.py 本地日线数据库读取交易期间 OHLC
- 策略/归因口径：
  - 当前正式基准：`official_stage78_1_defensive_50w_no_sizing_cap`
  - 当前锁盈档位：`30->20,20->15,10->8,5->3,3->1,2->0.1`
  - 重要口径修正：策略实际触发锁盈用收盘价更新后的 `max_profit_pct`，不是日内 high/low MFE；脚本同时输出 MFE 作为路径归因

## 结果

- 期末权益：本阶段不重跑回测；引用基准统计 `26,353,935`
- 总收益：引用基准统计 `5170.7870%`
- 最大回撤：引用基准统计 `-40.1659%`
- Sharpe：引用基准统计 `1.1374`
- 总滑点：本阶段不重算；基准统计见 Stage78-1 文件
- 总交易次数：基准统计 `883`
- 胜率：本阶段交易腿归因，不替代正式胜率
- 其他关键指标：
  - 已配对平仓腿数：`444`
  - 按收盘最大浮盈曾触发当前锁盈档位：`209`
  - 触发锁盈但最终亏损：`28`
  - 按当前锁盈地板估算低于地板退出：`76`
  - `2%->0.1%`：`37`腿，胜率`62.16%`，平均最终收益`0.34%`，平均 MFE`3.43%`
  - `3%->1%`：`70`腿，胜率`84.29%`，平均最终收益`1.34%`，平均 MFE`5.02%`
  - `5%->3%`：`48`腿，胜率`95.83%`，平均最终收益`4.03%`，平均 MFE`8.43%`
  - `10%->8%`：`41`腿，胜率`97.56%`，平均最终收益`9.22%`，平均 MFE`16.43%`
  - `20%->15%`：`7`腿，胜率`100%`，平均最终收益`14.12%`，平均 MFE`25.77%`
  - `30%->20%`：`6`腿，胜率`100%`，平均最终收益`29.23%`，平均 MFE`39.43%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage271_profit_lock_trade_attribution_report_stage271_profit_lock_trade_attribution_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage271_profit_lock_trade_attribution_summary_stage271_profit_lock_trade_attribution_v1.json`
- orders：无
- daily：无新增
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage271_profit_lock_trade_attribution_trades_stage271_profit_lock_trade_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage271_profit_lock_trade_attribution_bucket_summary_stage271_profit_lock_trade_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage271_profit_lock_trade_attribution_trigger_summary_stage271_profit_lock_trade_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage271_profit_lock_trade_attribution_exit_reason_summary_stage271_profit_lock_trade_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage271_profit_lock_trade_attribution_year_summary_stage271_profit_lock_trade_attribution_v1.csv`

## 结论

- 本阶段结论：
  - 当前手工分层不是明显荒谬；高浮盈档位样本虽少，但捕获趋势能力较强。
  - 最值得怀疑的是低档位：`2%->0.1%` 和 `3%->1%`，它们样本较多、最终收益较薄、离场后继续趋势空间中位数约 `5%-6%`。
  - 但归因不能直接证明“改低档一定更好”，因为当前交易路径已经被现有止损规则影响。
- 是否进入下一步：可以，但只能进入低自由度候选 A/B/C。
- 下一步：
  - Stage272 只测试少量结构化候选：如保留比例曲线、低档位延迟触发、平滑单调锁盈曲线。
  - 不允许逐档网格搜索，不允许围绕 2026 或某个弱窗口补丁化调参。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：本阶段不是过拟合；但若基于这份表直接调 6 个档位，会变成过拟合。
- 原因：本阶段只做事实归因，没有按结果修改正式参数；下一阶段必须限制自由度并做样本外验证。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但要克制。
- 原因：低档位确实出现可疑结构，值得做最小 A/B/C；但锁盈退出是高过拟合风险模块，不能做大规模扫参。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，新增研究线索引。
- 是否追加根目录 `memory.md/back_log.md`：本阶段非突破，不追加 `memory.md`；可在 `back_log.md` 做轻量新增线摘要。
