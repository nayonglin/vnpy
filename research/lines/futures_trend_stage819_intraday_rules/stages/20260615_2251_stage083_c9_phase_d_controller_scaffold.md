# Stage083 C9 Phase D 控制器骨架

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 22:51 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：官方实盘 C9 Phase D 自动化控制面落地
- 是否重要突破：否。完成常驻控制器骨架，但没有打开真实报单。
- 是否触发A/B：否。只做执行系统，不改策略 alpha。

## 外部调研与判断

- 参考资料：
  - vn.py README：`https://github.com/vnpy/vnpy/blob/master/README_ENG.md`
  - vn.py `MainEngine.send_order/cancel_order` 源码：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/engine.py`
  - FIA automated trading risk controls：`https://www.fia.org/sites/default/files/2024-07/FIA_WP_AUTOMATED%20TRADING%20RISK%20CONTROLS_FINAL_0.pdf`
  - FCA algorithmic trading controls：`https://www.fca.org.uk/publications/multi-firm-reviews/algorithmic-trading-controls-high-level-observations`
- 我的判断：vn.py 是事件驱动交易框架，真实发单最终会落到 `MainEngine.send_order/cancel_order`。完全自动化不能把影子盘脚本直接改成发单脚本，而应拆成控制器、readiness gate、盘中守护、真实 executor、对账 worker 和 kill switch。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/qmt_roll_official_live_phase_d_config.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage903_official_live_phase_d_controller.py`
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage902_official_live_phase_d_readiness_gate.py` 改为读取共享 Phase D 配置常量。
- 删除脚本：无
- 新增参数：
  - Stage903：`--mode monitor-only|dry-run|live-real`
  - Stage903：`--loop`
  - Stage903：`--poll-seconds`
  - Stage903：`--write-launchd-template`
  - Phase D 硬限额：`max_snapshot_age_seconds=300`、`max_tick_age_seconds=10`、`max_order_count_per_cycle=3`、`max_order_count_per_day=12`、`max_cancel_count_per_day=20`、`max_reject_count_per_day=2`、`max_single_order_volume=20`、`max_open_order_count=0`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：读取当前官方 C9 影子盘 `2026-01-01 -> 2026-06-12`
- 账户规模：`300,000`
- 成本口径：读取既有 Stage901 影子盘输出，本阶段不新增回测成本
- 样本过滤：无
- 策略/归因口径：Stage903 控制器 dry-run，一轮控制循环读取 Stage901、Stage902、Stage174 只读摘要、kill switch、当前时间窗口

## 结果

- 期末权益：`265,860`（读取 Stage901 既有影子盘）
- 总收益：`-11.38%`（读取 Stage901 既有影子盘）
- 最大回撤：`-14.8955%`（读取 Stage901 既有影子盘）
- Sharpe：`-1.1331`（读取 Stage901 既有影子盘）
- 总滑点：`3,860`（读取 Stage901 既有影子盘）
- 总交易次数：`27`（读取 Stage901 既有影子盘）
- 胜率：非零日胜率 `45.7143%`（读取 Stage901 既有影子盘）
- 其他关键指标：
  - Stage903 `controller_status=phase_d_controller_dry_run_blocked`
  - 当前 session：`night`
  - `signal_count=1`
  - `pending_order_count=1`
  - `current_position_count=1`
  - `watched_symbols=MA609.CZCE`
  - `kill_switch_active=false`
  - `stage902_blocking_failure_count=4`
  - `order_api_called_count=0`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage903_official_live_phase_d_controller_report_20260615_225111_stage903_official_live_phase_d_controller_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage903_official_live_phase_d_controller_summary_20260615_225111_stage903_official_live_phase_d_controller_v1.json`
- cycle_plan：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage903_official_live_phase_d_controller_cycle_plan_20260615_225111_stage903_official_live_phase_d_controller_v1.csv`
- event_log：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage903_official_live_phase_d_controller_events_20260615_225111_stage903_official_live_phase_d_controller_v1.ndjson`
- heartbeat：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_phase_d_controller_heartbeat.json`
- state：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_phase_d_controller_state.json`
- launchd_template：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage903_official_live_phase_d_controller_launchd_template_20260615_225111_stage903_official_live_phase_d_controller_v1.plist`
- quality：`py_compile` 通过

## 结论

- 本阶段结论：Phase D 的控制面已开始落地，具备一轮自动化循环、心跳、状态、event log、kill switch 检查、交易时段识别和 launchd 常驻模板。但它仍是 dry-run 控制器，不连接 CTP、不发单、不撤单。
- 是否进入下一步：是。
- 下一步：
  1. 把 broker read-only refresh 和 Stage260/251 串入 Stage903 控制器，但默认只读。
  2. 新增 C9 intraday monitor，读取实时 tick/minute，计算 0.5R 止损/重试条件，只生成 dry-run action。
  3. 新增真实 executor dry-run，复用 vn.py `OrderRequest`，但真实 `send_order` 仍由环境变量、确认文本、Stage902、kill switch 和 hard limits 共同阻断。
  4. 新增 reconcile worker，对理论目标、broker 持仓、订单、成交、撤单、拒单做闭环。

## 过拟合反思

- 运行前判断：否。Stage903 是执行控制器，不改策略参数、品种、方向、R 倍数或回测样本。
- 运行后判断：否。输出只是控制状态和 readiness 结果，不反向影响策略。
- 原因：本阶段只构建自动化执行外壳和风控状态机，没有优化任何收益指标。

## 继续价值反思

- 运行前判断：是。Phase D 必须先有常驻控制面，否则无法自动化心跳、熔断和对账。
- 运行后判断：是。Stage903 已把 D 架构的中心骨架落地，后续可以逐步接入只读刷新、盘中监控和 executor dry-run。
- 原因：完全自动化的主要风险已经从“能不能算信号”转成“能不能在真实市场连接、订单状态、异常和对账中保持 fail-closed”。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等 read-only refresh/Stage260/251 串入控制器后更新。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段仍未打开真实自动报单。
