# Stage278 Stage526策略本体优化边界审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-03 15:34 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因汇总；不改策略、不改参数、不扫阈值、不生成新交易版本。
- 是否重要突破：否，但属于策略本体方向的收束性边界结论。
- 是否触发A/B：否。没有新版本满足“可能接入正式版本/需要与第78正式基准结合”的条件。

## 外部调研与判断

- 参考资料：
  - Two centuries of trend following：`https://arxiv.org/abs/1404.3274`
  - Trend Following, Risk Parity and Momentum in Commodity Futures：`https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2126813`
  - Optimal Allocation of Trend Following Strategies：`https://arxiv.org/abs/1410.8409`
  - Stop-loss strategies with serial correlation, regime switching, and transaction costs：`https://www.sciencedirect.com/science/article/abs/pii/S1386418117300472`
  - GitHub futures trend-following reference：`https://github.com/jironghuang/trend_following`
- 我的判断：
  - 长期趋势策略的本质优势主要来自多品种/多资产趋势暴露、组合风险预算与相关性治理，而不是频繁用紧止损砍掉短期不利波动。
  - 紧止损或快失败过滤只有在入场前能稳定识别低质量趋势、且交易成本可覆盖时才可能有效；本地 Stage535/537 证据没有满足该条件。
  - “失败后趋势更容易成功”这个直觉有经验价值，但当前只能作为诊断/复盘线索，不能直接变成交易门禁。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage576_stage526_strategy_body_optimization_boundary.py`
- 修改脚本：无既有策略脚本被修改。
- 删除脚本：无。
- 新增参数：无交易参数；仅新增只读汇总口径。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage526/531/532/533/535/536/537/562 既有输出，权威全周期为 `2020-01-01` 至 `2026-04-30`。
- 账户规模：Stage526 口径，`50万` 策略资金。
- 成本口径：正常成本为主，同时读取 Stage531/532 的 `2x/3x` 成本压力结果。
- 样本过滤：不新增过滤；只汇总已有已冻结候选和反证结果。
- 策略/归因口径：
  - Stage531：退出形状/ATR中位止损边界。
  - Stage532/533：同向相关门控与事件归因。
  - Stage535：快失败入场代理。
  - Stage536/537：成本换手脆弱性与持仓生命周期。
  - Stage562：失败记忆诊断。

## 结果

- 决策：`strategy_body_no_new_promotion_keep_stage526_floor50_observation_failure_memory_diagnostic`
- 晋级结论：`none`
- 闸门：`3/8`
- 当前主基准 Stage526：
  - 期末权益：`23,369,505`
  - 总收益：`3699.9195%`
  - 最大回撤：`-36.2670%`
  - Sharpe：`1.6385`
  - 总滑点：`1,342,190`
  - 总交易次数：`905`
  - 胜率：`53.6330%`
- 候选边界：
  - 关闭 ATR 中位止损：收益 `3552.4398%`，最大回撤 `-39.5864%`，3x成本最大回撤 `-43.7930%`，不晋级；默认 ATR 中位止损应保留。
  - alignment-break exit：收益增加 `+535.1951pp`，但 broker10 最大 `104.5349%`、3x最大回撤 `-44.0674%`、63/126日 p05 左尾均变差，不晋级。
  - profit giveback stop：最大回撤/Ulcer略好，但总收益下降 `-801.4455pp`、broker10 最大 `104.6165%`，不晋级。
  - corr floor50：总收益增加 `+98.6789pp`、最大回撤改善 `+1.0665pp`、Ulcer改善 `-0.1333`，但 3x最大回撤 `-40.9656%`、63日 p05 略差，且 Stage533 直接 corr scaled edge 为 `-26,805`，优势主要来自 downstream equity sizing delta `+627,290`；仅 paper 观察。
  - 关闭同向相关门控：最大回撤恶化到 `-45.3266%`，Ulcer `17.1767`，不晋级；默认 floor35 相关门控必须保留。
- 机制归因：
  - 1-5天持仓段净亏 `-13,589,580`，但 6-60天段净赚 `35,697,900`；所有全周期早停守卫 estimated_exit_delta 不正，最好也只有 `-10,540`。
  - Stage535 最宽快失败代理捕获负 edge `26.8364%`，但正 edge at risk `16.5793%`，不能写成入场过滤。
  - Stage562 失败记忆有诊断价值：`consecutive_loss>=2` 段净 PnL `17,374,465`，胜率 `55.1282%`；但 `only_after_consecutive_loss_ge1` 正 PnL at risk 仍为 `24.7838%`，不能做交易门禁。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage576_stage526_strategy_body_optimization_boundary_report_stage576_stage526_strategy_body_optimization_boundary_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage576_stage526_strategy_body_optimization_boundary_mechanism_summary_stage576_stage526_strategy_body_optimization_boundary_v1.csv`
- candidate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage576_stage526_strategy_body_optimization_boundary_candidate_boundary_stage576_stage526_strategy_body_optimization_boundary_v1.csv`
- probe：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage576_stage526_strategy_body_optimization_boundary_probe_boundary_stage576_stage526_strategy_body_optimization_boundary_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage576_stage526_strategy_body_optimization_boundary_gates_stage576_stage526_strategy_body_optimization_boundary_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage576_stage526_strategy_body_optimization_boundary_decision_stage576_stage526_strategy_body_optimization_boundary_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage576_stage526_strategy_body_optimization_boundary_chart_stage576_stage526_strategy_body_optimization_boundary_v1.png`

## 图表视觉复盘

- 左上：收益增量与最大回撤增量用双轴显示，避免收益尺度吞掉回撤变化；`floor50` 1x路径更好但仍不能覆盖3x成本。
- 右上：3个月/6个月左尾体验显示 `floor50` 6个月改善但3个月略差；alignment-break 在左尾上明显不稳。
- 左下：快失败和失败记忆探针都存在正收益风险，尤其失败记忆虽然胜率改善但会暴露大量右尾。
- 右下：只有 Stage526 本体和默认相关门控处于保留状态；其余为拒绝、诊断或执行监控。

## 结论

- 本阶段结论：Stage526 策略本体当前不应被退出形状、快失败代理、早停或失败记忆门禁替换；默认 ATR 中位止损和同向相关 floor35 应保留，`floor50` 只做 paper 观察。
- 是否进入下一步：策略本体层不继续扫小条件；如继续，只允许一个预注册、低幅度、冻结规则的 failure-memory micro-sizing paper 探针。更高优先级仍是 Stage277 的真实执行 TCA 和 Stage276/274 的 point-in-time 外生 selector。
- 下一步：
  - 不继续扫 ATR/止损/退出/相关阈值小数。
  - 不把失败次数直接写成开仓门禁。
  - 若做本体下一步，只做一次固定低幅 micro-sizing paper，闸门必须包括总收益、DD、Ulcer、63/126日左尾、broker10、2x/3x成本。
  - 更建议优先补 P0 实盘执行证据和外生 forward selector 样本。

## 过拟合反思

- 运行前判断：否。本阶段只读汇总既有冻结结果，不新增交易阈值。
- 运行后判断：否。结论主要是拒绝和停止，而不是用历史窗口拟合新规则。
- 原因：没有扫参数、没有改产品名单、没有挑单个坏窗口生成规则；对 `floor50` 和失败记忆这种有正信号的方向也没有晋级。

## 继续价值反思

- 运行前判断：是。策略本体方向已经积累多个局部结果，需要统一边界，避免重复实验。
- 运行后判断：有，但价值显著变窄。继续做大量本体小条件的边际价值低；真正值得继续的是真实执行证据、外生点时选品，或唯一一个低自由度 failure-memory micro-sizing paper。
- 原因：当前问题的第一性矛盾不是“没有一个更紧的退出规则”，而是趋势策略必须容忍短期亏损才能保留 6-60 天右尾。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage278 摘要和下一步约束。
- 是否更新 `research/registry.md`：否，本阶段不是跨线合入或正式候选。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段为本线收束结论，不属于重要突破或正式候选。
