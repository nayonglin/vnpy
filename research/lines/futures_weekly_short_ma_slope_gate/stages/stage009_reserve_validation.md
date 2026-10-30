# Stage009 reserve wrapper 实现与验证（未回测）

- 只新增 `tools/stage009_reserve.py`、`tools/test_stage009_reserve.py` 与本组 Stage009 日志；旧 Stage005/008 源码未改，未启动金融引擎、下载或生产访问，未 commit。
- 采用已批准设计，不另调金额或触发范围。API：`reserve_strategy_class(base, range_history, range_enabled, account_start, enabled=True)`；base 必须是已经装有原 range wrapper 的 Stage008 链，本 factory 不再装 range。
- 入口：仅实际起点之后 flat_entry/reverse_entry、原生方向信号/许可、既有周止损资格有效，且 C 空头未被原 range snapshot 底20%拒绝时，父资金 sizing 前执行 T。env_probe 不记实际候选去重键、不补资；换月/退出/加仓/预热不补。按 date|symbol|direction|signal|context 去重，不改候选顺序，跨品种共享一个账户和备用桶。
- 资金：以原 `_estimate_equity(strategy_engine.bars)` 计算完整含 MTM 与已发生成本的 E；settled_balance 只增加 T，base_capital 与原 engine 150000 不变。备用桶初始150000、只减；盈利按全部 E 动态 sizing，不回填 R。零/负 E 的父 `or base_capital` 退回被 sizing snapshot 与最终 selected_volume=0 阻止，范围是信号规划。
- T 后仅重算当前资金缓存：`_refresh_portfolio_drawdown_state`（原高水位保留）、`_refresh_portfolio_margin_deleverage_state`、`_refresh_risk_cluster_heat_pressure_snapshot`、heat gate weight 和 current_risk_per_trade。不得调用 `_refresh_risk_state`；不重复记录日波动/过热收益，不清空连败或历史，不清理实际仓位/计划 target/保证金 reservation。
- cluster margin cap 和 broker cap 从新的 `_sizing_equity/estimated_equity` 即时取值；correlation 是原价格/仓位历史统计，无备用桶资金输入。原日末 forced deleverage 从新 E 计算。volatility/overheat 的实际开关由 runner 单独导出并断言，不靠 setting 缺失推断。
- public：`reserve_balance`、`reserve_cumulative_transfer`、`reserve_transfer_events`、`reserve_signal_checks`、`reserve_daily_snapshots`；`reserve_snapshot(date, phase)` 可补最终快照。自动快照阶段为 `after_on_bars_settlement` 和 `after_update_trade`，选择同日最大 sequence 为最终快照；起点前不写快照。始终有 raw=E−cumT，W=E+R=raw+150000；转账不是交易盈亏。
- callback 快照若失败，外层 on_bars/update_trade 会设置 strict engine 的 intraday_execution_failure 后重新抛出，防止 vn.py 吞异常后误交付部分账本。

## RED/GREEN 与只读核查

1. 初始 RED 日志 `stage009_reserve_red.txt`，无 wrapper 的父类不能满足补资/隔离/边界行为。
2. callback guard 独立 RED→GREEN 日志 `stage009_reserve_callback_guard_red.txt` 与最终 `stage009_reserve_green.txt`。
3. 最终 16 个 reserve 行为测试全部通过，包含原 RangeStrategy 实际组合链；原 Stage005 的 8 个测试全部通过。py_compile 通过。未运行整个仓库金融/生产相关测试；根协调者另做完整研究测试集与独审。
4. 只读核查 vendor/vnpy_portfoliostrategy/backtesting.py：capital 仅在初始化/结果统计中使用，日账本 balance=capital+cumsum(net_pnl)，未发现 engine 买卖前现金购买力 gate。保留原 next-open 计划/成交机制；隔夜跳空使成交时 E 非正，原引擎仍可能执行已排队委托。没有新增执行时现金硬门，不把规划级保证冒充成交级保证。

运行前过拟合判断：有历史内迭代风险，固定15万/15万与触发条件，不扫比例/年份；继续价值：有，测试资金治理而非增加预测 alpha。此处仅实现/测试，金融结果和运行后结论待固定完整46窗口独审，不能提前声称策略有效。
