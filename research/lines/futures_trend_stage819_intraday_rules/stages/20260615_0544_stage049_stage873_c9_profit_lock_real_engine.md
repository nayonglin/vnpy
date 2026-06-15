# Stage049 Stage873 C9 +2R/1R 真实利润锁定引擎验证

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：day
- 记录时间：2026-06-15 05:44 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：基于 Stage819 候选和 C9 的冻结真实逐分钟引擎验证；不改 Stage372 官方正式版、不改 Stage819 候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否。Stage872 的乐观锁盈上限被真实资金联动反证。
- 是否触发A/B：否。C14 未达到“可能接入正式版本或候选 A/B”的标准。

## 外部调研与判断

- 参考资料：
  - Turtle Trading 原始规则强调趋势跟随系统应通过止损控制风险，同时让利润奔跑：https://oxfordstrat.com/coasdfASD32/uploads/2016/01/turtle-rules.pdf
  - Backtrader StopTrail 文档说明追踪止损/锁盈是常见订单语义，但需要由回测引擎按真实触发顺序验证：https://www.backtrader.com/docu/order-creation-execution/trail/stoptrail/
  - Backtrader stop-trading 示例和 GitHub 代码提供固定止损/追踪止损的参考形状：https://github.com/mementum/backtrader/blob/master/samples/stop-trading/stop-loss-approaches.py
  - vn.py CTA 引擎本身支持本地 stop order 触发状态流，但本研究需要组合层 per-layer 分钟路径语义，不能直接搬外部样例：https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/engine.py
- 我的判断：固定止盈已经在 Stage872 被反证，`+2R 后锁 +1R` 只配做一次冻结真实引擎验证。若真实资金联动后仍显著砍右尾，就必须停止利润锁定分支，不应继续扫 R、小数阈值、年份、品种或方向。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage873_c9_profit_lock_real_engine.py`
- 修改脚本：同上，重跑前修正持仓日锁盈状态的时间顺序保护：若已有 activation_time 晚于当前分钟，不允许先按 lock_price 出场；同一根分钟K触发与回落仍只激活不出场。
- 删除脚本：无。
- 新增参数：
  - `stage873_profit_lock_trigger_r=2.0`
  - `stage873_profit_lock_lock_r=1.0`
  - `same_bar_policy=activate_only_no_exit_on_same_bar_trigger_and_lock`
- 修改参数：无正式参数修改；只在 Stage873 研究脚本内冻结 C14 规则。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage819/C9 全周期；分钟源为 Stage861 full minute bars。
- 账户规模：30万候选研究口径。
- 成本口径：沿用 Stage819/C4/C9 组合回测成本口径。
- 样本过滤：无年份、品种、方向过滤；加载 `1,479,592` 根分钟K、`216` 个 symbols。
- 策略/归因口径：
  - C4：`stage830_stage819_c2_broker10_100_cap`
  - C9：`stage847_stage819_c4_05r_stop_retry_once`
  - C14：`stage873_stage819_c9_lock1_after2r`
  - C14 规则：每个 live layer 按实际成交 entry 与原始 stop distance 计算 R，逐分钟先触及 `+2R` 后把保护位上移到 `+1R`，之后逐分钟触及 `+1R` 合成平仓。

## 结果

- C4：
  - 期末权益：`46,015,805.0`
  - 总收益：`15,238.6017%`
  - 最大回撤：`-47.1915%`
  - Sharpe：`1.5996`
  - 总滑点：`3,023,410`
  - 总交易次数：`678`
  - 胜率：`53.0630%`
  - max broker10 margin/equity：`111.4255%`
- C9：
  - 期末权益：`50,637,144.6`
  - 总收益：`16,779.0482%`
  - 最大回撤：`-42.6313%`
  - Sharpe：`1.6312`
  - 总滑点：`3,607,030`
  - 总交易次数：`786`
  - 胜率：`53.5299%`
  - max broker10 margin/equity：`114.3987%`
- C14：
  - 期末权益：`38,695,654.4`
  - 相对 C4 期末权益：`-7,320,150.6`
  - 相对 C9 期末权益：`-11,941,490.2`
  - 总收益：`12,798.5515%`
  - 最大回撤：`-42.8439%`
  - 相对 C4 最大回撤：`+4.3475pp`
  - 相对 C9 最大回撤：`-0.2127pp`
  - Sharpe：`1.6288`
  - 相对 C9 Sharpe：`-0.0024`
  - 总滑点：`3,533,330`
  - 总交易次数：`809`
  - 胜率：`53.5749%`
  - max broker10 margin/equity：`119.6549%`
  - p95 broker10 margin/equity：`56.6459%`
- 其他关键指标：
  - C14 profit lock events：`62`
  - entry-day lock events：`30`
  - holding-day lock events：`32`
  - 修正后 `activation_time > exit_time`：`0`
  - 决策：`stage873_profit_lock_not_promoted`

## 视觉复核

- path chart 显示 C14 在 2021/2022 之后持续低于 C9，收益曲线的复利底座被锁盈保护削薄。
- drawdown 图显示 C14 相对 C4 有改善，但没有超过 C9；这说明 C9 的 stop/retry 已经吃掉了主要收益/风险平衡，额外利润锁定不是免费保护。
- broker10 图显示 C14 max broker10 到 `119.6549%`，比 C9 更高，主要逻辑仍是右尾被削弱后权益分母下降。
- K线 atlas 显示锁盈出场确实多为“先到 +2R，随后回落到 +1R”的可执行形态；但这些机械保护也截断了一批后续右尾，不能只看单笔锁住盈利。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage873_c9_profit_lock_real_engine_report_stage873_c9_profit_lock_real_engine_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage873_c9_profit_lock_real_engine_summary_stage873_c9_profit_lock_real_engine_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage873_c9_profit_lock_real_engine_comparison_stage873_c9_profit_lock_real_engine_v1.csv`
- curve：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage873_c9_profit_lock_real_engine_curve_stage873_c9_profit_lock_real_engine_v1.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage873_c9_profit_lock_real_engine_trades_stage873_c9_profit_lock_real_engine_v1.csv`
- profit_lock_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage873_c9_profit_lock_real_engine_profit_lock_events_stage873_c9_profit_lock_real_engine_v1.csv`
- event_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage873_c9_profit_lock_real_engine_event_summary_stage873_c9_profit_lock_real_engine_v1.csv`
- path_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage873_c9_profit_lock_real_engine_path_chart_stage873_c9_profit_lock_real_engine_v1.png`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage873_c9_profit_lock_real_engine_atlas_page001_stage873_c9_profit_lock_real_engine_v1.png`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage873_c9_profit_lock_real_engine_atlas_page002_stage873_c9_profit_lock_real_engine_v1.png`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage873_c9_profit_lock_real_engine_atlas_page003_stage873_c9_profit_lock_real_engine_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage873_c9_profit_lock_real_engine_decision_stage873_c9_profit_lock_real_engine_v1.json`

## 结论

- 本阶段结论：C14 不晋级。`+2R 后锁 +1R` 在真实逐分钟引擎和资金联动下没有保住 C9 的核心右尾，期末权益相对 C9 少 `11,941,490.2`，最大回撤和 Sharpe 也没有超过 C9，max broker10 反而更高。
- 是否进入下一步：利润锁定分支不进入下一步。
- 下一步：停止固定止盈、保本、锁盈阈值、追踪锁盈 R 倍数的救参。若本线继续，应回到 C9 的一阶矛盾：如何不砍右尾地治理 broker10/权益分母脆弱，而不是继续在盈利单上加机械退出。

## 过拟合反思

- 运行前判断：否。本阶段只把 Stage872 已筛出的单一上限线索冻结为真实引擎，不扫描 R、时间窗、品种、方向、年份或重试次数。
- 运行后判断：否，但继续扫锁盈会立刻变成过拟合。
- 原因：真实引擎反证已经足够清晰；若在 `2R/1R` 失败后继续调成 `2.5R/1.2R`、分品种、分年份或分方向，本质是用历史路径寻找不会砍赢家的后验补丁。

## 继续价值反思

- 运行前判断：有价值。Stage872 的乐观代理给了一个低自由度、可执行、可被反证的线索。
- 运行后判断：利润锁定分支没有继续价值；研究线整体仍有有限价值，但必须换到不直接截断右尾的账户层/持仓层生存问题。
- 原因：C14 没有同时改善收益、回撤、Sharpe 和 broker10，且失败机制符合趋势跟随第一性原理：过早保护利润会削弱右尾复利，权益分母下降后还可能放大保证金压力百分比。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage049 结论。
- 是否更新 `research/registry.md`：否，本阶段不是正式候选、重要突破或路线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是本线内反证，不属于重要合入摘要。
