# Stage005 Stage829 C2基线开仓手数上限反事实

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-14 16:12 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：账户层 counterfactual attribution；检验 C2 裸规则收益/回撤是否依赖止损释放资金后的仓位放大
- 是否重要突破：否。C3 能缓和 C2 回撤，但仍不能修回 A 的回撤水平，且本身不是实时可用规则。
- 是否触发A/B：否。仍是 Stage819 候选内部研究，不与 Stage372/20w 官方正式版做 promotion A/B/C。

## 外部调研与判断

- 参考资料：
  - Concretum trend following position sizing：https://concretumgroup.com/position-sizing-in-trend-following-comparing-volatility-targeting-volatility-parity-and-pyramiding/
  - SSRN stop loss and trading frequency：https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2349848_code1794015.pdf?abstractid=2349848&mirid=1
  - City trend-following stop-loss paper：https://openaccess.city.ac.uk/id/eprint/17842/8/BLACKBOX%20%20%20SSRN-id2126476.pdf
  - Semantic Scholar stop-loss and re-entry：https://www.semanticscholar.org/paper/Assessing-Stop-Loss-and-Re-Entry-Strategies-Klement/92428c679f6d1cc97d2e66d34087cadf90b69e5a
  - PyTrendFollow：https://github.com/chrism2671/PyTrendFollow
  - MLM trend-following with IBKR：https://github.com/amstrdm/mlm-trend-following
- 我的判断：
  - 外部资料和 Stage004 一致：趋势系统里止损规则必须和再入场、仓位和组合风险预算一起评估。
  - C2 的问题不是分钟止损触发本身，而是释放资金后的组合路径；所以 Stage005 应做账户层反事实归因，而不是继续调 `1R`、冷却天数或品种过滤。
  - A 路径开仓手数上限不能作为实盘规则，因为真实交易时不知道 A 会怎么开；它只能用来证明“放大仓位”是不是 C2 收益和回撤的关键来源。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage829_stage827_c2_baseline_volume_cap.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `MODEL_TAG=stage829_stage827_c2_baseline_volume_cap_v1`
  - C3 反事实 cap key：`date/product_vt_symbol/direction/signal/entry_context`
  - C3 规则：C2 仍实时触发入场日 1R 止损，但 flat-entry 手数不得超过 Stage827 A 在同 key 上的实际开仓手数；A 没开则 C3 不开
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2018-01-01 至 2026-05-29
- 账户规模：30万，沿用 Stage819 候选配置
- 成本口径：沿用 Stage819/Stage827 滑点、手续费和组合日线统计口径
- 样本过滤：
  - A 和 C2 直接读取 Stage827 已冻结输出。
  - C3 重新跑完整组合路径；分钟K缺失时不触发 C2。
  - A opened cap map 共 `314` 个 key。
- 策略/归因口径：
  - A：Stage827 baseline，Stage819 原始候选复现。
  - C2：Stage827 裸 C2，入场日分钟K先触发 1R 逆向止损则同日合成平仓。
  - C3：C2 + A opened volume cap；这是反事实归因，不是 live-feasible 策略。
  - 不修改 Stage372/20w 官方正式版，不连接 CTP，不调用下单 API。

## 结果

- A 期末权益：26,322,730
- A 总收益：8,674.24%
- A 最大回撤：-54.75%
- A Sharpe：1.436
- A 总滑点：2,149,150
- A 总交易次数：666
- A 胜率：53.11%
- C2 期末权益：37,022,638.4
- C2 总收益：12,240.88%
- C2 最大回撤：-62.77%
- C2 Sharpe：1.458
- C2 总滑点：2,512,570
- C2 总交易次数：672
- C2 胜率：53.15%
- C3 期末权益：29,771,186.8
- C3 总收益：9,823.73%
- C3 最大回撤：-59.23%
- C3 Sharpe：1.439
- C3 总滑点：2,078,970
- C3 总交易次数：653
- C3 胜率：53.62%
- 新增回测结果：
  - C3 相对 A：期末权益 +3,448,456.8，总收益 +1,149.49pp，最大回撤恶化 -4.47pp，Sharpe +0.0025。
  - C3 相对裸 C2：期末权益 -7,251,451.6，最大回撤改善 +3.54pp，最大 broker10 保证金/权益从 `119.66%` 降到 `101.12%`。
  - C3 cap sizing events：703 次，其中 block 613 次，reduced_volume 合计 189,957；这些是 sizing attempt 级事件，不等同于最终成交笔数。
  - C3 C2 intraday stop events：50 次，少于裸 C2 的 51 次。
  - 2022-03-09 至 2022-06-29 窗口：
    - A 净损益：-6,146,050，谷值权益 5,601,205，最大保证金/权益 81.72%。
    - 裸 C2 净损益：-6,920,100，相对 A -774,050，谷值权益 4,542,658.4，最大保证金/权益 115.17%。
    - C3 净损益：-5,680,185，相对 A +465,865，谷值权益 4,343,665.8，最大保证金/权益 101.12%。
    - C3 在该窗口的损益比 A 好，但因前期已牺牲右尾、峰值更低，最终最大回撤仍比 A 差。
  - C3 最大回撤峰值日：2022-03-09，峰值权益 10,653,310.8。
  - C3 最大回撤谷值日：2022-06-29，谷值权益 4,343,665.8，最大回撤 -59.2271%。
- 修改回测结果：无。Stage827/Stage828 对 C2 裸规则“不晋级”的结论被保留。
- 删除回测结果：无。

## 视觉复盘

- Stage829 path chart 显示：
  - C3 绿线长期位于 A 蓝线与裸 C2 红线之间。
  - 2022 附近 C3 的保证金/权益峰值低于裸 C2，但仍高于 A。
  - 后期 C3 放弃了裸 C2 的一大段右尾，因此收益介于 A 与 C2 之间。
- 视觉判断：
  - A opened volume cap 确实能压住 C2 的部分路径风险。
  - 但它没有把回撤修回 A，也不是实时规则；因此不能晋级，只能证明下一步需要 live-feasible 风险预算。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage829_stage827_c2_baseline_volume_cap_report_stage829_stage827_c2_baseline_volume_cap_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage829_stage827_c2_baseline_volume_cap_summary_stage829_stage827_c2_baseline_volume_cap_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage829_stage827_c2_baseline_volume_cap_comparison_stage829_stage827_c2_baseline_volume_cap_v1.csv`
- curve：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage829_stage827_c2_baseline_volume_cap_curve_stage829_stage827_c2_baseline_volume_cap_v1.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage829_stage827_c2_baseline_volume_cap_trades_stage829_stage827_c2_baseline_volume_cap_v1.csv`
- entry_risk：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage829_stage827_c2_baseline_volume_cap_entry_risk_stage829_stage827_c2_baseline_volume_cap_v1.csv`
- entry_candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage829_stage827_c2_baseline_volume_cap_entry_candidates_stage829_stage827_c2_baseline_volume_cap_v1.csv`
- trade_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage829_stage827_c2_baseline_volume_cap_trade_events_stage829_stage827_c2_baseline_volume_cap_v1.csv`
- intraday_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage829_stage827_c2_baseline_volume_cap_intraday_events_stage829_stage827_c2_baseline_volume_cap_v1.csv`
- closed_lots：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage829_stage827_c2_baseline_volume_cap_closed_lots_stage829_stage827_c2_baseline_volume_cap_v1.csv`
- cap_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage829_stage827_c2_baseline_volume_cap_cap_events_stage829_stage827_c2_baseline_volume_cap_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage829_stage827_c2_baseline_volume_cap_decision_stage829_stage827_c2_baseline_volume_cap_v1.json`
- path chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage829_stage827_c2_baseline_volume_cap_path_chart_stage829_stage827_c2_baseline_volume_cap_v1.png`

## 结论

- 本阶段结论：
  - C3 证明账户层风险预算约束是正确方向：它把裸 C2 最大回撤从 `-62.77%` 修到 `-59.23%`，最大保证金/权益从 `119.66%` 降到 `101.12%`。
  - 但 C3 仍比 A 回撤差 `4.47pp`，收益又比裸 C2 少 `7,251,451.6`，所以它不是可晋级版本。
  - C3 是用了 A 路径信息的反事实归因，实盘不可用；不能把它包装成正式候选。
  - 分钟级实时止损仍有价值，但必须转译成实时可判定的账户层预算规则，不能依赖“基线 A 会开多少手”的事后信息。
- 是否进入下一步：是，但仍不是 promotion
- 下一步：
  - Stage006 只做 live-feasible 账户层规则候选，要求不引用 A 路径、不引用未来结果。
  - 优先考虑：C2 止损后释放的资金不立即用于放大同方向/同风险簇；或以实时 broker10 保证金/权益上限限制新增仓位。
  - 不做 R 倍数、年份、品种、方向、冷却天数的扫描救参。

## 过拟合反思

- 运行前判断：否。本阶段不扫参数，只用 A opened volume cap 做机制反事实。
- 运行后判断：规则本身不应晋级；如果把 A 路径 cap 当实盘规则，就是数据泄漏/过拟合。
- 原因：
  - A opened volume cap 使用了对照路径信息，真实交易时不可得。
  - 它的价值是回答“释放资金后的仓位放大是否是 C2 关键来源”，不是产生可部署策略。

## 继续价值反思

- 运行前判断：有。Stage004 已证明 C2 的直接止损不是 2022 回撤恶化主因，需要验证账户层约束是否能缓和二阶风险。
- 运行后判断：有，但方向更窄。
- 原因：
  - C3 确实缓和了 C2 回撤和保证金峰值，说明账户层约束方向有价值。
  - C3 仍未修复到 A 的回撤水平，说明不能简单“限手数”就结束；下一步必须设计实时可执行的风险预算，而非继续反事实。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新 Stage005 结论和 Stage006 方向。
- 是否更新 `research/registry.md`：否。按并行研究记录纪律，暂不频繁改 registry。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、不是重要突破、不是跨线合并。
