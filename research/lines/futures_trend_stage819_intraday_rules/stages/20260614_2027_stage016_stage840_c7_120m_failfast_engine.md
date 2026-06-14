# Stage016 Stage840 C4叠加120m 0.5R fail-fast真实引擎反证

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-14 20:27 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage819 候选独立研究线的冻结规则真实组合引擎 A/C；不改正式版、不改候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否。本阶段是 Stage839 H3 线索的真实引擎反证。
- 是否触发A/B：否。C7 相对 C4 收益、Sharpe、最大回撤和 broker10 路径均变差。

## 外部调研与判断

- 参考资料：
  - CME futures risk management / stop loss / position sizing 资料强调期货交易需要预定义风险、控制仓位和止损纪律。
  - GitHub / vn.py / 开源日内策略资料中常见模块是 stop loss、take profit、opening range、breakeven / trailing stop，但没有可直接复制到本仓库的 `120m 0.5R` 规则证据。
- 我的判断：本阶段不复制外部策略，只把 Stage839 的 H3 形状放进真实组合引擎。规则参数已在 Stage015 固定为 `120` 根分钟K、`0.5R` 逆向止损、`0.5R` 顺向进展确认、无重试；不能继续扫 `15/30/60/120` 或 `0.4/0.6R` 救结果。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage840_stage830_c4_120m_failfast_engine.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `enable_stage840_120m_half_r_failfast=True`
  - `stage840_failfast_bars=120`
  - `stage840_failfast_stop_r=0.5`
  - `stage840_failfast_progress_r=0.5`
- 修改参数：无。C2 的 `1R/1R` 与 C4 的 broker10 入场 cap 保持不变。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2018-01-01` 到 `2026-05-29`
- 账户规模：Stage819 候选 `300,000`
- 成本口径：沿用 Stage819 / Stage827 / Stage830 回测默认手续费、滑点和 broker10 保证金代理。
- 样本过滤：只跑 `2018-01` 全周期起点；A/C2/C4 读取 Stage830 已有输出，C7 新跑一条真实组合路径。
- 策略/归因口径：
  - A：`stage827_stage819_baseline`
  - C2：`stage827_stage819_c2_engine`
  - C4：`stage830_stage819_c2_broker10_100_cap`
  - C7：`stage840_stage819_c4_120m_05r_failfast`
  - C7 规则：C4 保持不变；若 C2 未触发，入场日起前 `120` 根分钟K先触达 `0.5R` 逆向、没有先触达 `0.5R` 顺向进展，则按 `-0.5R` 合成实时平仓；同一根同时触发按保守 fail-fast 先发生；不增加重试。

## 结果

### A 原始 Stage819 baseline

- 期末权益：`26,322,730`
- 总收益：`8674.2433%`
- 最大回撤：`-54.7546%`
- Sharpe：`1.4363`
- 总滑点：`2,149,150`
- 总交易次数：`666`
- 胜率：`53.1069%`
- broker10 峰值：`90.6200%`

### C4 当前可比基准

- 期末权益：`30,523,910.8`
- 总收益：`10074.6369%`
- 最大回撤：`-50.7900%`
- Sharpe：`1.4519`
- 总滑点：`2,079,430`
- 总交易次数：`677`
- 胜率：`53.6294%`
- broker10 峰值：`115.4012%`

### C7 本阶段候选

- 期末权益：`26,118,143.3`
- 总收益：`8606.0478%`
- 最大回撤：`-52.6280%`
- Sharpe：`1.3351`
- 总滑点：`1,993,300`
- 总交易次数：`682`
- 胜率：`52.7928%`
- broker10 峰值：`132.7826%`
- 相对 C4：
  - 期末权益差：`-4,405,767.5`
  - 最大回撤差：`-1.8380pp`
  - Sharpe 差：`-0.1168`
  - broker10 峰值差：`+17.3814pp`
- 相对 A：
  - 期末权益差：`-204,586.7`
  - 最大回撤改善：`+2.1267pp`
  - Sharpe 差：`-0.1012`

### 其他关键指标

- C7 C2 事件：`52`
- C7 fail-fast 事件：`25`
- C7 cap 事件：`32`
- C7 cap blocked：`0`
- C7 cap reduced volume：`809`
- C7 closed lots：`349`
- C7 `stage840_intraday_120m_05r_failfast_stop` closed lots：`25`
- C7 最大回撤峰谷：`2022-07-15 -> 2023-03-08`，从 `8,221,721.3` 回撤到 `3,894,797.1`，最大回撤 `-52.6280%`
- C7 在 `2022-03-09 -> 2022-06-29` 窗口相对 A 的净 PnL 差 `+3,194,185`，但窗口末端权益仍低于 A `-2,650,223.7`，且 broker10 峰值 `108.1730%`、p95 `92.3859%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage840_stage830_c4_120m_failfast_engine_report_stage840_stage830_c4_120m_failfast_engine_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage840_stage830_c4_120m_failfast_engine_summary_stage840_stage830_c4_120m_failfast_engine_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage840_stage830_c4_120m_failfast_engine_comparison_stage840_stage830_c4_120m_failfast_engine_v1.csv`
- curve：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage840_stage830_c4_120m_failfast_engine_curve_stage840_stage830_c4_120m_failfast_engine_v1.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage840_stage830_c4_120m_failfast_engine_trades_stage840_stage830_c4_120m_failfast_engine_v1.csv`
- entry_risk：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage840_stage830_c4_120m_failfast_engine_entry_risk_stage840_stage830_c4_120m_failfast_engine_v1.csv`
- entry_candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage840_stage830_c4_120m_failfast_engine_entry_candidates_stage840_stage830_c4_120m_failfast_engine_v1.csv`
- trade_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage840_stage830_c4_120m_failfast_engine_trade_events_stage840_stage830_c4_120m_failfast_engine_v1.csv`
- intraday_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage840_stage830_c4_120m_failfast_engine_intraday_events_stage840_stage830_c4_120m_failfast_engine_v1.csv`
- c2_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage840_stage830_c4_120m_failfast_engine_c2_events_stage840_stage830_c4_120m_failfast_engine_v1.csv`
- failfast_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage840_stage830_c4_120m_failfast_engine_failfast_events_stage840_stage830_c4_120m_failfast_engine_v1.csv`
- closed_lots：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage840_stage830_c4_120m_failfast_engine_closed_lots_stage840_stage830_c4_120m_failfast_engine_v1.csv`
- cap_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage840_stage830_c4_120m_failfast_engine_cap_events_stage840_stage830_c4_120m_failfast_engine_v1.csv`
- path_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage840_stage830_c4_120m_failfast_engine_path_chart_stage840_stage830_c4_120m_failfast_engine_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage840_stage830_c4_120m_failfast_engine_decision_stage840_stage830_c4_120m_failfast_engine_v1.json`
- quality：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage840_stage830_c4_120m_failfast_engine.py` 通过。
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage840_stage830_c4_120m_failfast_engine.py` 完成，`order_api_called=false`。
  - path chart 已视觉检查，C7 紫线在收益、回撤和 broker10 图上与表格结论一致。

## 结论

- 本阶段结论：`stage840_c7_not_promoted_stop_failfast_timewindow_route`
- 是否进入下一步：不沿 `120m 0.5R fail-fast` 时间窗路线继续。
- 下一步：
  - 停止 `15/30/60/120`、`0.4/0.5/0.6R`、重试次数、年份、品种、方向过滤等救参。
  - C7 的失败说明“入场初期小逆向”常常对应后续可恢复的右尾或会改变后续复利路径；把它机械止掉会丢 C4 的大部分收益，并把 broker10 压力推迟到更差路径。
  - 若继续本研究线，应回到分钟K视觉图谱和未覆盖亏损 taxonomy，寻找更本质、低自由度的形状，例如区分“无进展且同方向结构破坏”与“初期抖动后恢复”，而不是继续调 fail-fast 窗口。

## 过拟合反思

- 运行前判断：否，风险可控。
- 运行后判断：否，本次验证本身不是过拟合；但如果继续改窗口、改 R 倍数或按产品/年份排除失败事件，就是过拟合。
- 原因：C7 规则在运行前由 Stage015 固定，只测一条真实引擎路径；结果明确失败，没有继续搜索参数。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：本路线继续价值低，但整条研究线仍有价值。
- 原因：本阶段有效淘汰了一个看似有 gross delta 的 lot-level 线索，避免把它误接入候选；但用户目标仍是分钟级规则类日内入场/出场，后续应转向新的视觉 taxonomy 或更少误伤右尾的结构，而不是停止整条研究线。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage016 结论和下一步边界。
- 是否更新 `research/registry.md`：否。不是重要突破，也没有正式候选晋级或路线合并。
- 是否追加根目录 `memory.md/back_log.md`：否。只属于本研究线内部反证。
