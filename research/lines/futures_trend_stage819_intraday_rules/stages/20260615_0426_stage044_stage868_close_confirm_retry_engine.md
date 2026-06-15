# Stage044 Stage868 close-confirm next-open retry 真实引擎

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-15 04:26 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：研究线内冻结 A/C 真实组合引擎验证；只比较 Stage830 C4、Stage847 C9、Stage868 C12；不改 Stage372 官方正式版，不改 Stage819 官方候选配置，不连接 CTP，不调用下单。
- 是否重要突破：否
- 是否触发A/B：否，`formal_ab_triggered=false`，本阶段仍是 Stage819 候选研究线内部验证，不进入正式 Stage78/Stage372 A/B。

## 外部调研与判断

- 参考资料：
  - vn.py GitHub：https://github.com/vnpy/vnpy
  - Backtrader order execution docs：https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/
  - Klement, Assessing Stop-Loss and Re-Entry Strategies：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2466252
- 我的判断：
  - 止损策略不能只定义“什么时候离场”，还必须定义“什么时候允许重新入场”；否则 lot-level proxy 会高估组合可执行性。
  - Stage867 已证明“事后知道 retry failed 才 no-retry”不能直接实时化；Stage868 因此测试另一个实时可执行结构：不再用 intrabar 触碰原入场价立即重试，而是要求一分钟收盘重新站回原入场价，下一分钟开盘才重试。
  - 这个规则不是 AI、不是机器学习，也不使用未来二次失败标签；代价是接受更晚、更真实的再入场成交。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage868_stage847_close_confirm_retry_engine.py`
- 修改脚本：
  - 新增脚本内修正 event summary：C9 没有 `reentry_price` 字段时不再把 `0-entry_price` 误写成负的 `reentry_price_minus_entry`。
- 删除脚本：无
- 新增参数：
  - `enable_stage868_close_confirm_retry`
- 修改参数：
  - C9 的重试成交语义从“触碰原入场价按原入场价重试”改成“分钟收盘站回原入场价后，下一分钟开盘价重试”。
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage847/C9 全周期 `START` 到 `END`。
- 账户规模：沿用 Stage819/Stage830/Stage847 的组合回测口径。
- 成本口径：沿用既有组合回测成本和滑点口径。
- 样本过滤：无额外年份、品种、方向过滤；不扫描阈值、R、时间窗、品种、方向。
- 策略/归因口径：
  - A：`stage830_stage819_c2_broker10_100_cap`，即 C4。
  - B：`stage847_stage819_c4_05r_stop_retry_once`，即 C9。
  - C：`stage868_stage819_c9_close_confirm_next_open_retry`，即 C12。
  - C12 规则：首次 `0.5R` stop 不变；若后续一分钟收盘回到原入场价有利侧，则下一分钟开盘重试一次；重试后仍用原 `0.5R` stop；同一根分钟K保守判定止损优先。

## 结果

| arm | 期末权益 | 相对C4 | 相对C9 | 总收益 | 最大回撤 | 相对C9回撤 | Sharpe | 相对C9 Sharpe | 总滑点 | 总交易次数 | 胜率 | max broker10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C4 `stage830_stage819_c2_broker10_100_cap` | 46,015,805.0 | 0.0 | -4,621,339.6 | 15,238.6017% | -47.1915% | -4.5602pp | 1.5996 | -0.0316 | 3,023,410 | 678 | 53.0630% | 111.4255% |
| C9 `stage847_stage819_c4_05r_stop_retry_once` | 50,637,144.6 | +4,621,339.6 | 0.0 | 16,779.0482% | -42.6313% | 0.0000pp | 1.6312 | 0.0000 | 3,607,030 | 786 | 53.5299% | 114.3987% |
| C12 `stage868_stage819_c9_close_confirm_next_open_retry` | 50,061,893.1 | +4,046,088.1 | -575,251.5 | 16,587.2977% | -43.1561% | -0.5249pp | 1.6233 | -0.0079 | 3,593,170 | 786 | 53.5778% | 114.0579% |

- 期末权益：C12 `50,061,893.1`，低于 C9 `575,251.5`。
- 总收益：C12 `16,587.2977%`，低于 C9 `16,779.0482%`。
- 最大回撤：C12 `-43.1561%`，比 C9 差 `-0.5249pp`。
- Sharpe：C12 `1.6233`，低于 C9 `1.6312`。
- 总滑点：C12 `3,593,170`，略低于 C9 `3,607,030`，但收益损失更大。
- 总交易次数：C12 `786`，与 C9 相同。
- 胜率：C12 `53.5778%`，略高于 C9，但不足以弥补权益和回撤损失。
- 风险路径：C12 max broker10 `114.0579%`，仅比 C9 低 `0.3408pp`，改善太小。

### 事件结果

| profile | final_state | events | volume | touch reclaim | close confirmed | reentered | retry failed |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| C9 | `flat_no_reentry` | 70 | 14,095 | N/A | N/A | 0 | 0 |
| C9 | `flat_retry_failed` | 25 | 4,795 | N/A | N/A | 25 | 25 |
| C9 | `open_after_reentry` | 26 | 5,292 | N/A | N/A | 26 | 0 |
| C12 | `flat_no_close_confirm_reentry` | 70 | 14,079 | 0 | 0 | 0 | 0 |
| C12 | `flat_close_confirm_retry_failed` | 25 | 4,788 | 25 | 25 | 25 | 25 |
| C12 | `open_after_close_confirm_reentry` | 26 | 5,277 | 26 | 26 | 26 | 0 |

- C12 stop/retry events `121`，touch reclaim observed `51`，close-confirm reentries `51`，retry failed `25`。
- 与 C9 对比，C12 并没有减少重试数量：C9 也是 `25` 个 retry failed + `26` 个 open_after_reentry。
- 重试价差分布：`51` 笔重试中 `40` 笔重试价不同于原入场价，`price_delta` 中位数 `0`，均值 `+0.2078`，最差负向 `-37`，最大正向 `+37`；重试确认延迟中位 `78` 根分钟K，下一分钟重试延迟中位 `79` 根分钟K。
- 失败机制：C12 只是把 C9 的重试成交时间/价格后移，没有筛掉原本会二次失败的重试；因此它没有带来实质风险治理，反而损失部分右尾复利。

### K线视觉复核

- atlas page001/page002 已复核，能看到 `first stop`、`touch reclaim`、`close confirm`、`next open reentry`、`retry fail` 标记。
- 代表事件如 `CF905.CZCE 2019-01-31`、`OI001.CZCE 2019-10-21`、`sp2012.SHFE 2020-08-17`、`rb2305.SHFE 2023-01-12`，close confirm 后仍会在后续路径触发 retry fail。
- 人眼结论：收盘确认的方向性强度不够。它证明“价格曾经站回原入场价”，但没有证明趋势重新恢复，也没有约束组合层后续 sizing/broker10。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage868_stage847_close_confirm_retry_engine_report_stage868_stage847_close_confirm_retry_engine_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage868_stage847_close_confirm_retry_engine_summary_stage868_stage847_close_confirm_retry_engine_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage868_stage847_close_confirm_retry_engine_comparison_stage868_stage847_close_confirm_retry_engine_v1.csv`
- curve：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage868_stage847_close_confirm_retry_engine_curve_stage868_stage847_close_confirm_retry_engine_v1.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage868_stage847_close_confirm_retry_engine_trades_stage868_stage847_close_confirm_retry_engine_v1.csv`
- entry_risk：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage868_stage847_close_confirm_retry_engine_entry_risk_stage868_stage847_close_confirm_retry_engine_v1.csv`
- entry_candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage868_stage847_close_confirm_retry_engine_entry_candidates_stage868_stage847_close_confirm_retry_engine_v1.csv`
- trade_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage868_stage847_close_confirm_retry_engine_trade_events_stage868_stage847_close_confirm_retry_engine_v1.csv`
- intraday_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage868_stage847_close_confirm_retry_engine_intraday_events_stage868_stage847_close_confirm_retry_engine_v1.csv`
- stop_retry_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage868_stage847_close_confirm_retry_engine_stop_retry_events_stage868_stage847_close_confirm_retry_engine_v1.csv`
- closed_lots：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage868_stage847_close_confirm_retry_engine_closed_lots_stage868_stage847_close_confirm_retry_engine_v1.csv`
- event_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage868_stage847_close_confirm_retry_engine_event_summary_stage868_stage847_close_confirm_retry_engine_v1.csv`
- path_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage868_stage847_close_confirm_retry_engine_path_chart_stage868_stage847_close_confirm_retry_engine_v1.png`
- atlas_manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage868_stage847_close_confirm_retry_engine_atlas_manifest_stage868_stage847_close_confirm_retry_engine_v1.csv`
- atlas_pages：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage868_stage847_close_confirm_retry_engine_atlas_page001_stage868_stage847_close_confirm_retry_engine_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage868_stage847_close_confirm_retry_engine_atlas_page002_stage868_stage847_close_confirm_retry_engine_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage868_stage847_close_confirm_retry_engine_atlas_page003_stage868_stage847_close_confirm_retry_engine_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage868_stage847_close_confirm_retry_engine_atlas_page004_stage868_stage847_close_confirm_retry_engine_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage868_stage847_close_confirm_retry_engine_decision_stage868_stage847_close_confirm_retry_engine_v1.json`

## 结论

- 本阶段结论：`stage868_close_confirm_retry_not_promoted`。
- 是否进入下一步：close-confirm next-open retry 这一分支不进入下一步，不进入正式候选，不触发正式 A/B。
- 下一步：
  - 不继续扫 close-confirm 窗口、下一分钟/下两分钟、`0.5R`、重试次数、品种、方向或年份。
  - 不再围绕 C9 的“重试成交语义”做小变体；Stage868 证明触碰重试和收盘确认重试命中的是同一批事件。
  - 如果继续本研究线，应回到更高一级的结构：重试后的组合风险预算/产品方向压力，或完全独立的实时趋势恢复信号，而不是仅用“是否站回原入场价”判断。

## 过拟合反思

- 运行前判断：否。规则是单一固定成交语义变化，不做参数扫描。
- 运行后判断：本次实现本身不是过拟合；但若继续救 close-confirm 窗口、确认分钟数、R 倍数或按品种方向过滤，就是过拟合。
- 原因：失败不是因为确认窗口没调好，而是因为 close confirm 没有改变“哪些事件被重试”。继续微调只是在同一 `51` 笔事件上做成交价/时间拟合。

## 继续价值反思

- 运行前判断：有继续价值。它是 Stage043 后一个低自由度、实时可执行的重试质量假设。
- 运行后判断：close-confirm retry 分支没有继续价值；更大的分钟级研究线仍有价值，但方向应切换。
- 原因：C12 比 C9 少赚 `575,251.5`、回撤差 `0.5249pp`、Sharpe 低 `0.0079`，broker10 只改善 `0.3408pp`。这是“略微更保守但没有抓住主要矛盾”的版本。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage044 否决结论，并停止重试成交语义小变体。
- 是否更新 `research/registry.md`：否，本线未变更归属。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、不是路线合并、不是正式候选、也没有触发正式 A/B。
