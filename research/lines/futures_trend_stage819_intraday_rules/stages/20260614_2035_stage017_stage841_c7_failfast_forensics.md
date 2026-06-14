# Stage017 Stage841 C7 fail-fast误伤法证

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：day
- 记录时间：2026-06-14 20:35 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读数据分析 + 分钟K视觉法证；不新增策略规则、不跑新组合引擎、不连接 CTP、不调用下单。
- 是否重要突破：否。它解释 Stage840 C7 失败原因，但不构成可接正式候选的新版本。
- 是否触发A/B：否。C7 已被 Stage840 反证，本阶段仅做失败归因。

## 外部调研与判断

- 参考资料：
  - CME futures order types：止损单是预定义触发条件下的风险控制工具，但触发后仍需考虑执行与保护范围，不等于策略 alpha。[CME Futures Order Types](https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/futures-order-types)
  - CME position and risk management：风险控制应围绕可承受亏损、保证金和持仓风险，而不是事后按单笔噪音优化。[CME Position and Risk Management](https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/position-and-risk-management)
  - CFTC stop order study：公开研究关注止损单在期货市场中的使用与订单簿行为，提醒止损触发本身只是市场微结构事件，不天然区分趋势失败和短期波动。[CFTC Stop Orders in Select Futures Markets](https://www.cftc.gov/sites/default/files/Stoploss_final_ada.pdf)
  - vn.py GitHub：vn.py 提供 CTA/backtesting 等基础设施，但没有可直接复制到本线的“分钟级 fail-fast 修复 Stage819 候选”的现成规则。[vn.py GitHub](https://github.com/vnpy/vnpy)
- 我的判断：公开资料只支持“止损必须预定义、风险和保证金必须受控”的纪律，不支持把初期 0.5R/120m 逆向直接解释为错误入场。Stage840 的 C7 失败更像趋势跟随早期噪音误杀，而不是时间窗或 R 倍数还没调准。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage841_stage840_c7_failfast_forensics.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增只读归因标签 `forensic_bucket`、`recovered_after_stop_shape`、`post_hit_mfe_r`、`entry_day_close_return_r`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage819/Stage840 全周期订单与分钟K可覆盖样本。
- 账户规模：上游 Stage819/Stage840 口径 `300,000`。
- 成本口径：本阶段不新增成交和成本；对比沿用 Stage840 C4/C7 已实现订单结果。
- 样本过滤：仅分析 Stage840 C7 的 `fail-fast` 触发事件，共 `25` 个；所有事件均匹配到 C4 同入口 lots。
- 策略/归因口径：把 C7 fail-fast 事件与 C4 同入口持仓结局配对，区分 `killed_c4_winner`、`saved_c4_loser`、`worse_than_c4_loser`、`c4_flat`，并生成分钟K atlas 做视觉复核。

## 结果

- 期末权益：不适用，本阶段是只读事件法证；上游 Stage840 C7 期末权益为 `26,118,143.3`，C4 为 `30,523,910.8`。
- 总收益：不适用，本阶段不跑新组合权益；上游 Stage840 C7 总收益 `8606.0478%`，C4 总收益 `10074.6369%`。
- 最大回撤：不适用，本阶段不跑新组合权益；上游 Stage840 C7 最大回撤 `-52.6280%`，C4 最大回撤 `-50.7900%`。
- Sharpe：不适用，本阶段不跑新组合权益；上游 Stage840 C7 Sharpe `1.3351`，C4 Sharpe `1.4519`。
- 总滑点：不适用，本阶段不新增成交；上游 Stage840 C7 总滑点 `1,993,300`。
- 总交易次数：不适用，本阶段不新增成交；上游 Stage840 C7 交易次数 `682`。
- 胜率：不适用，本阶段不新增成交；上游 Stage840 C7 胜率 `52.7928%`。
- 其他关键指标：
  - C7 fail-fast 事件 `25` 个，C4 匹配事件 `25` 个，路径特异未匹配 `0` 个。
  - 匹配事件中 C4 总 PnL `+1,417,025.0`，C7 总 PnL `-2,059,431.3`，C7 相对 C4 净损 `-3,476,456.3`。
  - `killed_c4_winner` `10` 个，C4 PnL `+3,588,270.0`，C7 PnL `-824,985.2`，净损 `-4,413,255.2`。
  - `saved_c4_loser` `10` 个，C4 PnL `-1,838,295.0`，C7 PnL `-753,655.3`，净改善 `+1,084,639.7`。
  - `worse_than_c4_loser` `4` 个，净损 `-120,340.8`；`c4_flat` `1` 个，净损 `-27,500.0`。
  - 止损后当日重新站回入场 `6` 个，到达 `+0.5R` `3` 个，到达 `+1R` `2` 个。
  - 最大误伤集中在 OI、lh、sp、fu 等趋势右尾事件；最差事件为 `OI405.CZCE` long 2024-03-15，C4 `+665,000`、C7 `-217,160`，净损 `-882,160`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage841_stage840_c7_failfast_forensics_report_stage841_stage840_c7_failfast_forensics_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage841_stage840_c7_failfast_forensics_summary_stage841_stage840_c7_failfast_forensics_v1.csv`
- orders：不适用；本阶段不生成新成交。
- daily：不适用；本阶段不生成新权益曲线。
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage841_stage840_c7_failfast_forensics_event_diagnostics_stage841_stage840_c7_failfast_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage841_stage840_c7_failfast_forensics_bucket_stats_stage841_stage840_c7_failfast_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage841_stage840_c7_failfast_forensics_atlas_manifest_stage841_stage840_c7_failfast_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage841_stage840_c7_failfast_forensics_atlas_page001_stage841_stage840_c7_failfast_forensics_v1.png` 至 `page007`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage841_stage840_c7_failfast_forensics_decision_stage841_stage840_c7_failfast_forensics_v1.json`
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage841_stage840_c7_failfast_forensics.py` 已通过。
  - 已视觉检查 atlas page001：典型误伤事件显示先触发 -0.5R/120m fail-fast，随后重新站回或继续趋势；图形证据与统计结论一致。

## 结论

- 本阶段结论：`stage841_diagnostic_only_c7_failfast_hurts_by_killing_recoverable_entries`。C7 失败的核心不是无法匹配事件，也不是纯交易成本问题，而是 fail-fast 条件太粗，把趋势初期可恢复抖动当成错误入场。它节省了部分亏损，但误杀 C4 后续赢家造成的损失更大。
- 是否进入下一步：进入下一步只读研究；不进入真实引擎、不进入官方候选、不进入 A/B。
- 下一步：停止 `120m/0.5R/retry` 扫描。若继续，优先做“止损后结构破坏”只读 taxonomy，例如止损后不能重新站回入场、不能重新突破 OR15、持仓后同方向结构连续破坏；必须先在 Stage841 事件与 Stage825 全量 lots 上只读验证，再决定是否冻结一个低自由度引擎。

## 过拟合反思

- 运行前判断：否。本阶段只解释一个已经失败的冻结规则，不用结果反推新参数。
- 运行后判断：否，但继续价值边界更清楚。若接下来继续扫 `120m/90m/150m`、`0.4R/0.6R` 或品种方向过滤，就是过拟合。
- 原因：25 个事件虽然数量不大，但本阶段结论是“不要继续这条 fail-fast 形状”，不是用 25 个事件训练新策略。视觉图谱只用来识别失败机制，不直接变成交易规则。

## 继续价值反思

- 运行前判断：有价值。Stage840 给出 C7 失败结果，但需要知道失败来自误伤右尾、救亏不足、路径匹配问题还是资金联动问题。
- 运行后判断：有价值但需要换问题。fail-fast 时间窗路线继续做价值低；“结构破坏而非初期抖动”的只读分类仍有价值。
- 原因：C7 净损 `-3,476,456.3` 中，`killed_c4_winner` 贡献 `-4,413,255.2`，远大于 `saved_c4_loser` 的 `+1,084,639.7`。这说明必须寻找能保留 recoverable trend 的实时退出条件，而不是更紧的固定时间止损。

## 合入建议

- 是否更新本线 `LINE.md`：是，补充 Stage017 结论和后续规划。
- 是否更新 `research/registry.md`：否，非正式候选、非重要突破、非跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，仅本线内部失败归因。
