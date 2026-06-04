# Stage318 策略本体剩余优化空间关账板

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 05:53 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因关账；不改策略、不改参数、不跑交易引擎、不连接 CTP、不调用订单 API、不生成交易白名单。
- 是否重要突破：否。结论是策略本体小规则方向主动继续价值低，但它把 ATR/退出/K线/失败记忆/成本弹性放到同一张证据板里，避免后续重复浅扫。
- 是否触发 A/B：否。没有新版本满足“可能接入正式版本”的条件。

## 外部调研与判断

- Stop-loss strategies with serial correlation, regime switching, and transaction costs：紧止损在交易成本存在时并不天然改善趋势策略，只有当收益序列相关足够强时才可能抵消换手成本。
- `pysystemtrade` position sizing / backtesting 资料：趋势系统的关键更偏向组合层风险目标、仓位缓冲、相关性和分散，而不是单一 K 线小条件。
- GitHub trend-following reference：工程实现通常把 ATR/趋势/仓位作为系统组件，但是否有效仍必须回到多周期、成本和组合路径验证。
- 本地判断：Stage526 的剩余矛盾不是“缺一个更紧的 ATR/K线止损”，而是趋势策略必须容忍 1-5 天亏损，才能保留 6-60 天右尾；本体小规则继续调参已经接近过拟合边界。

参考：

- https://www.sciencedirect.com/science/article/pii/S1386418117300472
- https://deepwiki.com/robcarver17/pysystemtrade/3.2-position-sizing-and-optimization
- https://github.com/robcarver17/pysystemtrade/blob/develop/docs/backtesting.md
- https://github.com/jironghuang/trend_following

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage618_strategy_body_residual_closure_board.py`
- 修改正式策略参数：无。
- 新增交易参数：无。
- 修改交易参数：无。
- 删除交易参数：无。
- 新增回测：无。只读聚合 Stage526/535/537/564/576/581 冻结输出。
- 修改回测结果：无。
- 删除回测结果：无。

## 审计输入

- Stage526：当前 `r080_pc25_maxpos4` 主研究候选路径。
- Stage535：快失败入场前 K线/价格质量代理。
- Stage537：持仓生命周期与早停 guard。
- Stage564：成本弹性与 2022 坏窗口月度拆解。
- Stage576：策略本体优化边界审计。
- Stage581：failure-memory micro sizing 修复后真实引擎复验。

## 结果

- 决策：`strategy_body_residual_closed_no_new_trade_rule_reroute_to_execution_source_slot`
- 新交易规则晋级数：`0`
- hard gates：`2/8`
- `promotion_allowed=false`
- `paper_selector_allowed=false`
- `trading_whitelist_allowed=false`
- `body_subroute_active=false`

Stage526 当前主基准：

| 指标 | 数值 |
| --- | ---: |
| 期末权益 | `23,369,505` |
| 总收益 | `3699.9195%` |
| 最大回撤 | `-36.2670%` |
| Ulcer | `14.4691` |
| Sharpe | `1.6385` |
| 总滑点 | `1,342,190` |
| 总交易次数 | `905` |
| 非零日胜率 | `53.6330%` |

核心归因：

| 证据 | 数值 | 解释 |
| --- | ---: | --- |
| 1-5 天持仓段净 PnL | `-13,589,580` | 短期亏损真实存在 |
| 6-60 天持仓段净 PnL | `35,697,900` | 中期趋势右尾更大，不能简单砍早期亏损 |
| 全样本最佳早停 estimated_exit_delta | `-10,540` | 全样本仍为负；坏窗口局部正数不能交易化 |
| 2022 坏窗口净亏 | `-1,614,915` | 主风险来自路径亏损 |
| 2022 坏窗口 3x 额外成本 | `147,420` | 占绝对亏损 `9.1287%`，成本会推穿边界但不是亏损主因 |
| failure-memory 收益增量 | `+238.0000pp` | 右尾变厚 |
| failure-memory 最大回撤增量 | `-0.9390pp` | 回撤变差 |
| failure-memory 2x/3x 回撤增量 | `-0.9888pp / -1.0427pp` | 成本压力下更差 |
| failure-memory 63/126日 p05 增量 | `-0.9114pp / -0.7649pp` | 短周期持有体验左尾变差 |

机制矩阵：

| 机制 | 证据阶段 | 结论 |
| --- | --- | --- |
| ATR mid stop | Stage531/576 | 关闭后回撤恶化，默认 ATR 中位止损应保留 |
| alignment break exit | Stage531/576 | 收益提高但 broker10 和 3x 成本失败，不能晋级 |
| profit giveback stop | Stage531/576 | 回撤略好但收益下降过多，不符合“现有指标不能劣化” |
| corr gate floor50 | Stage532/533/576 | 可 paper 观察，但 3x 仍破 DD40，直接事件 edge 为负，不能替换 |
| remove corr gate | Stage532/576 | 最大回撤恶化到 `-45.3266%`，默认相关门控必须保留 |
| entry K-line / fast-fail proxy | Stage535/576 | 捕获负 edge 的同时误伤正 edge，不能交易化 |
| time stop / early adverse exit | Stage537/576 | 全样本最佳 estimated delta 仍为 `-10,540`，不晋级 |
| failure-memory micro sizing | Stage581 | 收益更高但风险路径和短周期体验劣化，不晋级 |

## 图表视觉复盘

- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage618_strategy_body_residual_closure_board_chart_stage618_strategy_body_residual_closure_board_v1.png`
- 左上：所有机制均为红色非晋级；`corr floor50` 分数最高但也只是 paper observation，不是替换候选。
- 右上：1-5 天持仓段亏损明显，但 6-60 天右尾更大，说明“早停/紧止损”容易砍掉趋势策略的主要收益来源。
- 左下：failure-memory 多赚 `238pp`，但最大回撤、Ulcer、2x/3x 成本、63/126 日左尾全部劣化，视觉上不应被收益增量掩盖。
- 右下：2022 坏窗口成本压力可见，但月度路径亏损更大；成本监控必要，但不能把亏损主因归咎于单一执行成本或止损开关。

## 输出文件

- script：`examples/portfolio_backtesting/analyze_qmt_roll_stage618_strategy_body_residual_closure_board.py`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage618_strategy_body_residual_closure_board_decision_stage618_strategy_body_residual_closure_board_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage618_strategy_body_residual_closure_board_report_stage618_strategy_body_residual_closure_board_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage618_strategy_body_residual_closure_board_chart_stage618_strategy_body_residual_closure_board_v1.png`
- mechanism matrix：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage618_strategy_body_residual_closure_board_mechanism_matrix_stage618_strategy_body_residual_closure_board_v1.csv`
- residual metrics：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage618_strategy_body_residual_closure_board_residual_metrics_stage618_strategy_body_residual_closure_board_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage618_strategy_body_residual_closure_board_gates_stage618_strategy_body_residual_closure_board_v1.csv`

## 结论

- 策略本体小规则方向暂时关账：不继续扫 ATR/止损/K线/失败次数/倍率/产品名单。
- Stage526 默认 ATR 中位止损、同向相关 floor35 和当前本体结构应保留。
- 后续优先级转回三条更有价值的主线：
  1. 真实执行 TCA 与滑点证据。
  2. point-in-time 外生/舆情 selector 样本累计。
  3. 低单笔风险、低相关、source/TCA 可闭合的独立风险槽。

## 过拟合反思

- 运行前判断：否。本阶段是只读关账板，不新增交易规则，不扫 ATR/K线/失败次数/倍率/品种名单。
- 运行后判断：否。结论是拒绝/收束，而不是用坏窗口局部现象救规则。
- 关键反过拟合点：坏窗口局部早停有正 delta，但全样本最佳早停 delta 为 `-10,540`，所以不能用局部窗口特判生成交易规则。

## 继续价值反思

- 运行前判断：有价值。目标要求深度研究策略本体优化，需要把已有零散结果统一到一张可复核证据板。
- 运行后判断：总目标继续有价值，但策略本体小条件方向主动继续价值低。
- 原因：本体层已有足够证据显示短期亏损和中期右尾纠缠，继续调小条件大概率只会过拟合；更高价值的边际工作在真实执行、点时外生选品和独立风险槽。

## TODO

- 不继续救 `failure-memory >=2 / 252d / 1.10`、ATR 倍数、K线形态和早停小条件。
- 继续推进 Stage317 的 source/event ledger 修复：P2 `source_url/authorized endpoint`、P1 `j/i` official/member/warehouse route。
- 在用户确认测试环境和 read-only 动作后，推进 Stage608/612 live snapshot 与 TCA reducer。
- 继续寻找两个非 DCE、低相关、source 可执行、TCA 可闭合的新独立经济驱动。

## 合入建议

- 是否更新本线 `LINE.md`：是，最新阶段更新到 Stage318。
- 是否更新 `research/registry.md`：是，当前线最新关键阶段更新到 Stage318。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重要突破或跨线合入。
