# Stage003 Stage819候选C2组合引擎A/C

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-14 15:56 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：隔离 subclass + 自定义 engine 的组合路径验证
- 是否重要突破：否。C2 收益更高但最大回撤显著恶化，不能晋级。
- 是否触发A/B：否。仍是 Stage819 候选内部研究，不与 Stage372/Stage78 正式基准做 promotion A/B/C。

## 外部调研与判断

- 参考资料：
  - 继续沿用 Stage001/Stage002 的 ORB、固定止损止盈、失败退出等日内规则参考。
  - 本阶段不新增外部参数，只验证 Stage002 最强线索 C2 在组合路径中是否成立。
- 我的判断：
  - Stage002 lot-level overlay 只改 closed lot，不重算后续资金/仓位/再入场，容易高估路径质量。
  - Stage003 必须用组合引擎检验 C2 是否破坏回撤和后续仓位路径。
  - 如果组合路径暴露回撤恶化，不能用调阈值修补，应先做失败归因。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `MODEL_TAG=stage827_stage819_intraday_c2_engine_ac_v1`
  - `STOP_R=1.0`
  - `CONFIRM_R=1.0`
  - 同K线同时触发时使用 `conservative_stop_first`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2018-01-01 至 2026-05-29
- 账户规模：30万，沿用 Stage819 候选配置
- 成本口径：沿用 Stage819 滑点、手续费和组合日线统计口径
- 样本过滤：组合引擎全路径；分钟缺失时不触发 C2
- 策略/归因口径：
  - A：Stage819 原始候选，用同一个 Stage827 subclass 但关闭 C2，必须复现官方候选
  - C：开仓成交后，用入场日分钟K判断 1R 逆向止损是否先于 1R 顺向确认；若触发，则同日合成平仓成交，并让组合状态、资金、保证金和后续信号继续滚动
  - 不修改 Stage372/20w 官方正式版，不连接 CTP，不调用下单 API

## 结果

- A 期末权益：26,322,730
- A 总收益：8,674.24%
- A 最大回撤：-54.75%
- A Sharpe：1.436
- A 总滑点：2,149,150
- A 总交易次数：666
- A 胜率：53.11%
- C 期末权益：37,022,638.4
- C 总收益：12,240.88%
- C 最大回撤：-62.77%
- C Sharpe：1.458
- C 总滑点：2,512,570
- C 总交易次数：672
- C 胜率：53.15%
- 新增回测结果：
  - C2 组合引擎触发 51 次日内 1R 止损。
  - C 比 A 期末权益增加 10,699,908.4。
  - C 最大回撤比 A 恶化 8.01pp，从 -54.75% 恶化到 -62.77%。
  - C 滑点增加 363,420，交易次数增加 6。
  - A 已复现 Stage819 官方候选：期末权益、总收益、最大回撤、Sharpe、滑点、交易次数均对齐。
- 修改回测结果：Stage002 的 C2 “回撤改善”结论被 Stage003 组合路径反证，改为“收益增强但回撤恶化”。
- 删除回测结果：无

## 事件分布

- 2020：13 次，7 个品种，合计 448 手
- 2021：11 次，7 个品种，合计 1,419 手
- 2022：8 次，5 个品种，合计 1,918 手
- 2023：5 次，5 个品种，合计 1,651 手
- 2024：5 次，4 个品种，合计 2,380 手
- 2025：7 次，6 个品种，合计 3,186 手
- 2026：2 次，2 个品种，合计 792 手
- C 最深回撤日：2022-06-29，账户权益 4,542,658.4，最大回撤 -62.77%
- A 同日最深回撤：2022-06-29，账户权益 5,601,205，最大回撤 -54.75%

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage827_stage819_intraday_c2_engine_ac_report_stage827_stage819_intraday_c2_engine_ac_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage827_stage819_intraday_c2_engine_ac_summary_stage827_stage819_intraday_c2_engine_ac_v1.csv`
- curve：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage827_stage819_intraday_c2_engine_ac_curve_stage827_stage819_intraday_c2_engine_ac_v1.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage827_stage819_intraday_c2_engine_ac_trades_stage827_stage819_intraday_c2_engine_ac_v1.csv`
- entry_risk：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage827_stage819_intraday_c2_engine_ac_entry_risk_stage827_stage819_intraday_c2_engine_ac_v1.csv`
- entry_candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage827_stage819_intraday_c2_engine_ac_entry_candidates_stage827_stage819_intraday_c2_engine_ac_v1.csv`
- trade_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage827_stage819_intraday_c2_engine_ac_trade_events_stage827_stage819_intraday_c2_engine_ac_v1.csv`
- intraday_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage827_stage819_intraday_c2_engine_ac_intraday_events_stage827_stage819_intraday_c2_engine_ac_v1.csv`
- closed_lots：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage827_stage819_intraday_c2_engine_ac_closed_lots_stage827_stage819_intraday_c2_engine_ac_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage827_stage819_intraday_c2_engine_ac_decision_stage827_stage819_intraday_c2_engine_ac_v1.json`

## 结论

- 本阶段结论：
  - C2 作为 lot-level overlay 是强线索，但进入组合路径后暴露出明显路径副作用。
  - 收益更高不等于可晋级；最大回撤恶化 8.01pp，已经违反“穿越周期”和风险路径优先原则。
  - C2 可能通过提前止损释放资金，让后续高收益交易更激进地参与，但也在 2022 路径上放大风险暴露；这需要归因，不应直接推广。
  - “日内实时止损”在本策略里不是天然改善回撤，必须看组合再入场和资金释放后的二阶效应。
- 是否进入下一步：是，但不是调参推进
- 下一步：
  - Stage004 只做归因：拆解 C2 为什么在 2022-06-29 附近造成更深回撤，包括释放资金后的新增/放大交易、品种、方向和保证金路径。
  - 禁止调 `0.8R/1.2R`、确认倍数、分钟窗口或冷却天数来救结果。
  - C2 暂不晋级，不接正式候选，不做正式 A/B。

## 过拟合反思

- 运行前判断：否。C2 仍是 Stage002 冻结的 1R/1R 规则，没有调参。
- 运行后判断：规则本身没有新增过拟合，但 Stage002 的乐观解读属于证据不足；组合路径证明 lot-level overlay 不够。
- 原因：
  - Stage003 让止损影响后续仓位和资金，发现了 Stage002 看不到的二阶风险。
  - 如果现在为了修复 -62.77% 回撤去加冷却、改倍数或限制年份/品种，就是明显过拟合。

## 继续价值反思

- 运行前判断：有。Stage826 C2 太强，必须进组合路径验证。
- 运行后判断：有，但价值从“推广 C2”转为“研究日内止损释放资金后的二阶风险”。
- 原因：
  - C2 确实能提高收益，说明止损释放资金有价值。
  - 但 C2 同时恶化回撤，说明释放资金后组合重新承担了更糟的风险路径。
  - 继续做归因有价值；继续扫参数没有价值。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新为 Stage003 已完成、C2 不晋级、Stage004 做回撤归因。
- 是否更新 `research/registry.md`：否。按并行研究记录纪律，暂不频繁改 registry。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、不是重要突破、不是跨线合并。
