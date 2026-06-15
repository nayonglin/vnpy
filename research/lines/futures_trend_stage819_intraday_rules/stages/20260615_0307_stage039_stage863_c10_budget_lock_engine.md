# Stage039 Stage863 C10预算锁真实引擎

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 03:07 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage819 候选研究线隔离真实引擎回放；不改 Stage372 正式版、不改 Stage819 候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否。C10 新增规则无效，但确认 C9 在 Stage861 全量分钟K口径下相对 C4 更强。
- 是否触发A/B：否。C10 未改变 C9 路径，不进入官方候选。

## 外部调研与判断

- 参考资料：
  - vn.py GitHub：`https://github.com/vnpy/vnpy`
  - backtesting.py 逐 bar 回放文档：`https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html`
- 我的判断：
  - 外部资料只支持事件驱动回放、逐 bar 触发、策略信号与风险约束隔离的工程纪律，不能提供可直接搬用的日内阈值。
  - 本阶段沿用 Stage847 冻结的 `0.5R` 和一次重试，不新增 R 倍数、重试次数、年份、品种、方向或分钟窗口扫描。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage863_stage847_c10_budget_lock_engine.py`
- 修改脚本：无正式策略脚本修改；仅新增研究脚本。
- 删除脚本：无。
- 新增参数：
  - `enable_stage863_stop_retry_budget_lock`
- 修改参数：
  - 无。`stop_retry_r=0.5`、`max_retries=1` 沿用 Stage847/C9。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2018-01-01` 到 `2026-05-29`
- 账户规模：Stage819 候选 `30w` 口径。
- 成本口径：沿用 Stage819/Stage830/Stage847 研究线成本、滑点、合约乘数、保证金元数据。
- 样本过滤：无品种、年份、方向过滤。
- 分钟K口径：Stage861 full minute bars，`1,479,592` 根，`216` 个 symbols；Stage825 原始分钟源 + Stage860 patch 去重。
- 策略/归因口径：
  - C4：Stage830/C4，`C2 1R` 同日止损 + broker10 projected margin/equity `100%` 入口上限。
  - C9：Stage847/C9，C4 + `0.5R` 先逆向止损 + 同日重回原入场价只重试一次 + 二次 `0.5R` 失败即平。
  - C10：C9 + 同品种同方向 stop/retry 后预算锁；方向仍有持仓时新增手数不得超过锁内剩余额度，方向归零后释放。

## 结果

### C4

- 期末权益：`46,015,805.0`
- 总收益：`15,238.6017%`
- 最大回撤：`-47.1915%`
- Sharpe：`1.5996`
- 总滑点：`3,023,410`
- 总交易次数：`678`
- 胜率：`53.0630%`
- max broker10 margin/equity：`111.4255%`
- p95 broker10 margin/equity：`63.5392%`

### C9

- 期末权益：`50,637,144.6`
- 相对 C4 期末权益：`+4,621,339.6`
- 总收益：`16,779.0482%`
- 最大回撤：`-42.6313%`
- 相对 C4 最大回撤改善：`+4.5602pp`
- Sharpe：`1.6312`
- 总滑点：`3,607,030`
- 总交易次数：`786`
- 胜率：`53.5299%`
- max broker10 margin/equity：`114.3987%`
- p95 broker10 margin/equity：`61.5244%`

### C10

- 期末权益：`50,637,144.6`
- 相对 C9 期末权益：`0`
- 总收益：`16,779.0482%`
- 最大回撤：`-42.6313%`
- 相对 C9 最大回撤：`0pp`
- Sharpe：`1.6312`
- 总滑点：`3,607,030`
- 总交易次数：`786`
- 胜率：`53.5299%`
- max broker10 margin/equity：`114.3987%`
- p95 broker10 margin/equity：`61.5244%`
- stop_retry_events：`242`（C9+C10 合计，各 `121`）
- budget_lock_events：`242`
- budget_lock_created：`121`
- budget_lock_effective_events：`0`
- budget_lock_blocked：`0`
- budget_lock_reduced_volume：`0`
- 决策：`stage863_c10_no_effect_budget_lock_not_promoted`

## 峰值归因补充

- C10 与 C9 完全重合，说明同品种同方向的加仓预算锁没有碰到真实路径；C9 的剩余矛盾不是“stop/retry 后同品种继续加仓”。
- C9/C10 broker10 峰值日期：`2020-11-23`，max broker10 `114.3987%`；C4 峰值日期：`2022-04-07`，max broker10 `111.4255%`。后续需要单独做峰值持仓归因，不应继续微调 C10 锁。
- 以 `2022-03-09` 右尾/压力窗口为例，C9 相对 C4 同一批多头持仓手数更大：
  - `sp2205.SHFE long`：`364` vs `318`，差 `+46`
  - `au2206.SHFE long`：`76` vs `65`，差 `+11`
  - `MA205.CZCE long`：`498` vs `494`，差 `+4`
  - `SM205.CZCE long`：`502` vs `502`，差 `0`
- 这类差异来自 C9 早期 stop/retry 后路径权益、资金释放与后续 sizing 联动，而不是当前 C10 规则可以拦截的 add/reopen。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage863_stage847_c10_budget_lock_engine_report_stage863_stage847_c10_budget_lock_engine_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage863_stage847_c10_budget_lock_engine_summary_stage863_stage847_c10_budget_lock_engine_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage863_stage847_c10_budget_lock_engine_comparison_stage863_stage847_c10_budget_lock_engine_v1.csv`
- curve：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage863_stage847_c10_budget_lock_engine_curve_stage863_stage847_c10_budget_lock_engine_v1.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage863_stage847_c10_budget_lock_engine_trades_stage863_stage847_c10_budget_lock_engine_v1.csv`
- entry_risk：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage863_stage847_c10_budget_lock_engine_entry_risk_stage863_stage847_c10_budget_lock_engine_v1.csv`
- entry_candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage863_stage847_c10_budget_lock_engine_entry_candidates_stage863_stage847_c10_budget_lock_engine_v1.csv`
- trade_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage863_stage847_c10_budget_lock_engine_trade_events_stage863_stage847_c10_budget_lock_engine_v1.csv`
- intraday_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage863_stage847_c10_budget_lock_engine_intraday_events_stage863_stage847_c10_budget_lock_engine_v1.csv`
- stop_retry_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage863_stage847_c10_budget_lock_engine_stop_retry_events_stage863_stage847_c10_budget_lock_engine_v1.csv`
- budget_lock_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage863_stage847_c10_budget_lock_engine_budget_lock_events_stage863_stage847_c10_budget_lock_engine_v1.csv`
- closed_lots：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage863_stage847_c10_budget_lock_engine_closed_lots_stage863_stage847_c10_budget_lock_engine_v1.csv`
- path_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage863_stage847_c10_budget_lock_engine_path_chart_stage863_stage847_c10_budget_lock_engine_v1.png`

## 结论

- 本阶段结论：
  - C10 不晋级。预算锁没有真实 reduce/block 事件，无法解释或修复 C9 的 broker10 峰值。
  - C9 在 Stage861 全量分钟K口径下相对 C4 明显改善期末权益、最大回撤和 Sharpe，但 max broker10 从 C4 `111.4255%` 升到 `114.3987%`，仍不能直接进入官方候选。
- 是否进入下一步：
  - 是，但不是继续 C10。下一步应做 C9 broker10 峰值归因，重点找 `2020-11-23` 和压力窗口中“早期止损重试如何通过权益/资金路径放大后续 sizing”的实时可控变量。
- 下一步：
  - Stage864 只读峰值归因：对 C9/C4 broker10 峰值日做 active lots、entry_risk、trade_events、closed_lots 和分钟K图谱对齐；先解释风险来自权益分母、保证金分子还是具体产品簇，再决定是否有低自由度规则。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有扫描阈值、年份、品种、方向、分钟窗口或重试次数。
  - 规则是从 Stage862 预声明的 `H1 + risk-budget lock + second-failure discipline` 派生，并且被真实路径反证为无效新增。
  - C9 的正结果不能被当作晋级证据，因为 broker10 峰值仍恶化。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有，但研究方向要收窄。
- 原因：
  - C10 本身没有继续价值；继续微调同品种同方向锁会变成补丁。
  - C9 在全量分钟覆盖下仍有明显收益/回撤价值，值得解释 broker10 峰值来源。
  - 下一步价值在归因 broker10 峰值的实时可控机制，而不是继续写 C10 变体。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage039 当前状态和后续规划。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重要突破或跨线合并；仅为本线内部真实引擎反证与归因。
