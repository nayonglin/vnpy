# Stage006 Stage830 C2 broker10保证金入口闸门

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-14 16:21 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage819 候选内部 live-feasible 账户层 A/C；不改官方正式版、不连接 CTP、不调用下单。
- 是否重要突破：是，首次在候选线内部同时高于 Stage819 A 的收益并改善最大回撤。
- 是否触发A/B：暂不触发正式 A/B；当前只证明 Stage819 候选内部有价值，尚未通过跨起点稳健性，也未与当前正式 Stage372 做替代级验证。

## 外部调研与判断

- 参考资料：
  - Concretum Group 关于 trend-following 仓位管理、vol targeting、vol parity 和 pyramiding 的比较。
  - SSRN/City 公开 stop-loss 研究，重点关注止损频率、再入场和趋势系统的交互。
  - PyTrendFollow、mlm-trend-following 等 GitHub 趋势跟随项目，主要参考其账户级风险预算和仓位约束思想。
- 我的判断：
  - 公开资料一致指向：日内止损本身不是独立 alpha，必须和账户层风险预算一起看，否则止损释放出的资金会被后续同类机会重新放大。
  - Stage827/828 的内部归因也验证了这一点：C2 直接止损事件在 2022 年并不是负贡献，真正问题是释放资金后的手数和风险预算放大。
  - 因此 Stage830 不继续扫 `1R`、冷却天数、品种方向或年份过滤，而是固定一个可实时执行的 broker10 保证金/权益入口上限。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage830_stage827_c2_broker10_margin_cap.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `BROKER_MARGIN_MULTIPLIER = 1.65`
  - `BROKER_MARGIN_CAP_RATIO = 1.0`
  - variant：`stage830_stage819_c2_broker10_100_cap`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2018-01 起至 2026-05-29，沿用 Stage827/Stage819 候选口径。
- 账户规模：Stage819 候选 30万口径。
- 成本口径：沿用 Stage827/Stage819 候选回测成本与滑点口径；C4 总滑点实算为 `2,079,430`。
- 样本过滤：不按年份、品种、方向、收益标签过滤；入口闸门只看当时估算权益、已占用保证金、合约价格和交易乘数。
- 策略/归因口径：
  - A：`stage827_stage819_baseline`，Stage819 原始候选复现。
  - C2：`stage827_stage819_c2_engine`，入场日分钟K若先触发 `1R` 逆向止损而非 `1R` 顺向确认，则同日止损。
  - C4：C2 保持不变；flat-entry 开仓前若 projected broker10 margin/equity 超过 `100%`，则降低本次开仓手数到不超过 `100%`。

## 结果

- A 期末权益：`26,322,730`
- A 总收益：`8674.24%`
- A 最大回撤：`-54.75%`
- A Sharpe：`1.436`
- A 总滑点：`2,149,150`
- A 总交易次数：`666`
- A 胜率：`53.11%`
- C2 期末权益：`37,022,638.4`
- C2 总收益：`12240.88%`
- C2 最大回撤：`-62.77%`
- C2 Sharpe：`1.458`
- C2 总滑点：`2,512,570`
- C2 总交易次数：`672`
- C2 胜率：`53.15%`
- C4 期末权益：`30,523,910.8`
- C4 总收益：`10074.64%`
- C4 最大回撤：`-50.79%`
- C4 Sharpe：`1.452`
- C4 总滑点：`2,079,430`
- C4 总交易次数：`677`
- C4 胜率：`53.63%`
- 其他关键指标：
  - C4 相对 A：期末权益 `+4,201,180.8`，最大回撤改善 `+3.9646pp`，Sharpe `+0.0156`，总滑点减少 `69,720`，交易次数增加 `11`，胜率提升 `0.5225pp`。
  - C4 相对裸 C2：期末权益少 `6,498,727.6`，但最大回撤改善 `+11.9788pp`。
  - C4 cap events 共 `35` 次，blocked `0` 次，reduced volume `906` 手。
  - C4 全路径 max broker10 margin/equity 仍为 `115.4012%`，p95 为 `60.5631%`；入口闸门不能保证后续盯市路径不超过 100%。
  - 2022-03-09 至 2022-06-29 窗口，C4 净损益相对 A 为 `+2,651,945`，窗口内 max broker10 `96.917%`，但窗口末权益仍低于 A `1,774,037.2`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage830_stage827_c2_broker10_margin_cap_report_stage830_stage827_c2_broker10_margin_cap_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage830_stage827_c2_broker10_margin_cap_summary_stage830_stage827_c2_broker10_margin_cap_v1.csv`
- orders/trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage830_stage827_c2_broker10_margin_cap_trades_stage830_stage827_c2_broker10_margin_cap_v1.csv`
- daily/curve：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage830_stage827_c2_broker10_margin_cap_curve_stage830_stage827_c2_broker10_margin_cap_v1.csv`
- quality/diagnostics：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage830_stage827_c2_broker10_margin_cap_comparison_stage830_stage827_c2_broker10_margin_cap_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage830_stage827_c2_broker10_margin_cap_entry_risk_stage830_stage827_c2_broker10_margin_cap_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage830_stage827_c2_broker10_margin_cap_entry_candidates_stage830_stage827_c2_broker10_margin_cap_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage830_stage827_c2_broker10_margin_cap_trade_events_stage830_stage827_c2_broker10_margin_cap_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage830_stage827_c2_broker10_margin_cap_intraday_events_stage830_stage827_c2_broker10_margin_cap_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage830_stage827_c2_broker10_margin_cap_closed_lots_stage830_stage827_c2_broker10_margin_cap_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage830_stage827_c2_broker10_margin_cap_cap_events_stage830_stage827_c2_broker10_margin_cap_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage830_stage827_c2_broker10_margin_cap_path_chart_stage830_stage827_c2_broker10_margin_cap_v1.png`

## 结论

- 本阶段结论：
  - C4 是目前本线最有价值的候选内部变体：它保留 C2 的日内实时止损，并用实时可得的 broker10 入口保证金闸门抑制释放资金后的二阶放大。
  - 与 Stage819 A 相比，C4 同时提高收益、降低最大回撤、降低总滑点，方向明显优于 Stage829 的 A opened volume cap 反事实。
  - 但 C4 仍不是官方正式候选替代：第一，尚未做跨起点/分段稳健性；第二，full-path max broker10 仍到 `115.40%`，说明入口上限不是完整保证金生存线。
- 是否进入下一步：是。
- 下一步：
  - Stage831 做冻结参数的跨起点稳健性验证，不调 `100%`、不调 `1.65`、不调 `1R`。
  - 优先跑年度或月度起点的 A vs C4，观察收益胜率、回撤胜率、DD40/DD50 失败次数和 broker10 超限分布。
  - 只有 Stage831 证明稳健后，才讨论是否进入正式 A/B，与当前官方 Stage372/20w 比较。

## 过拟合反思

- 运行前判断：不是明显过拟合。
- 运行后判断：当前 Stage830 本身不是明显过拟合，但继续扫阈值会迅速进入过拟合。
- 原因：
  - `100% broker10` 是账户生存闸门，来自风控约束，不是从某一年、某品种或某几笔交易反推出来的小数最优。
  - 规则只使用开仓当时可得信息，不引用 A 路径、不引用未来收益、不引用回撤窗口标签。
  - 但当前只看了 2018 起点全周期；如果后面为了让 broker10 全路径不超限而扫 `95/90/85` 或单独修 2022，就会变成路径补丁。

## 继续价值反思

- 运行前判断：有价值继续。
- 运行后判断：有价值继续，但下一步必须是稳健性验证，不是继续加规则。
- 原因：
  - Stage830 首次在候选线内部同时改善收益和最大回撤，说明 C2 的问题不是日内止损方向错，而是资金释放后的账户风险再分配。
  - 限制也很清楚：入口保证金闸门无法覆盖持仓后价格变化导致的 broker10 超限，所以若继续，有两个方向：先验证 C4 稳健性；若稳健，再研究全路径持仓保证金生存线。

## 合入建议

- 是否更新本线 `LINE.md`：是，作为 Stage006 当前状态。
- 是否更新 `research/registry.md`：否，当前仍是并行研究线内阶段，不由本工作区频繁改总索引。
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；等 Stage831 稳健性或正式 A/B 比较通过后，再作为重要合入摘要记录。
