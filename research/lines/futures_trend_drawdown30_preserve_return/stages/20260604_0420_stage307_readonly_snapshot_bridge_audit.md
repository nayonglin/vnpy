# Stage307 只读快照桥接审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 04:20 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读文件快照桥接审计；不重放收益、不连接 CTP、不刷新 broker、不调用 `send_order`。
- 是否重要突破：否。它把 Stage606 validator 接上了既有 Stage174 文件快照，但同时证明旧快照不能关掉执行无偏差缺口。
- 是否触发A/B：否。本阶段不是策略候选，不产生收益曲线或交易白名单。

## 外部调研与判断

- 参考资料：
  - vn.py MainEngine/OmsEngine 查询入口：`https://deepwiki.com/vnpy/vnpy/2.2-main-engine`
  - vn.py 事件系统：`https://deepwiki.com/vnpy/vnpy/2.1-main-engine-and-event-system`
  - vn.py gateway 合同源码镜像：`https://gitee.com/vnpy/vnpy/blob/master/vnpy/trader/gateway.py`
- 我的判断：
  - vn.py 的 `get_contract/get_tick/get_all_accounts/get_all_positions` 适合作为 read-only live context collector 的来源；`EVENT_ORDER/EVENT_TRADE/EVENT_TICK` 和 `vt_orderid` 适合作为后续 TCA join 的证据链。
  - 但文件快照只能证明“曾经读到过账户/持仓/合约”，不能证明当前 submit plan 的真实可成交上下文。必须同时满足新鲜度、合约覆盖、tick覆盖、持仓状态、涨跌停/价格带、保证金与人工确认。
  - Stage591 的 submit plan 是历史 2024-2025 合约，不能用 2026 年旧 read-only snapshot 去证明这些历史行当时可成交；下一步需要当前/未来 submit plan 对齐的 read-only snapshot。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage607_readonly_snapshot_bridge_audit.py`
- 修改脚本：
  - `examples/portfolio_backtesting/qmt_roll_live_context_adapter.py`
    - 新增 `load_stage174_readonly_snapshot()`，把 Stage174 summary 指向的 contracts/accounts/positions/ticks CSV 读入 Stage606 validator snapshots。
    - 修复 `confirmed_flat` 口径：只有 meta 快照本身新鲜时，`confirmed_flat/positions_received` 才能算作 fresh position snapshot。
- 删除脚本：无。
- 新增参数：
  - `STAGE174_SUMMARY = qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json`
  - `max_snapshot_age_seconds = 300`
  - `max_tick_age_seconds = 30`
- 修改参数：无交易参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：无新增收益回测；只读 Stage591 submit plan 和 Stage174 read-only probe 输出。
- 账户规模：不适用；本阶段只检查执行上下文证据。
- 成本口径：不适用；本阶段不模拟成交、不加滑点。
- 执行口径：文件读取；`ctp_connection_attempted=false`，`send_order_api_called_count=0`。
- 样本过滤：
  - Stage591 submit plan `5` 行：`fu2509.SHFE/lc2505.GFEX/AP505.CZCE/SM501.CZCE/SM505.CZCE`。
  - Stage174 persisted snapshot：contracts/accounts/positions/ticks/meta。
- 策略/归因口径：
  - 不改 Stage079、Stage526 或 78-1 策略逻辑。
  - 不把旧 reference price 当 live price。
  - 不把旧 `confirmed_flat` 当当前 fresh position snapshot。

## 结果

- 新增交易回测：无。
- 决策：`persisted_readonly_snapshot_bridge_loads_but_stale_no_tick_no_symbol_coverage`
- 是否允许晋级：否。
- 是否允许声明真实交易无偏差：否。
- 期末权益：不适用；无收益回测。
- 总收益：不适用；无收益回测。
- 最大回撤：不适用；无收益回测。
- Sharpe：不适用；无收益回测。
- 总滑点：不适用；无成交回放。
- 总交易次数：不适用；无成交回放。
- 胜率：不适用；无成交回放。
- 其他关键指标：
  - Stage174 状态：`readonly_snapshots_received`
  - Stage174 snapshot generated_at：`2026-05-20 22:02`
  - snapshot age：`1,232,062.355` 秒
  - contracts rows：`19,079`
  - accounts rows：`6`
  - positions rows：`7`
  - ticks rows：`0`
  - Stage591 contract coverage：`0/5`
  - Stage591 tick coverage：`0/5`
  - live context present rows：`0/45`
  - real submit allowed rows：`0/5`
  - hard gates：`8/13`
  - `ctp_connection_attempted=false`
  - `send_order_api_called_count=0`

## 失败闸门

| 闸门 | 观测值 | 要求 | 判断 |
| --- | ---: | --- | --- |
| `ticks_available` | `0` | `>0` | tick 缺失，无法形成真实窗口限价证据 |
| `snapshot_fresh_300s` | `0/5` | all components | 快照过期，不能证明当前状态 |
| `stage591_contract_coverage` | `0/5` | all Stage591 rows | 历史合约不在旧快照中 |
| `stage591_tick_coverage` | `0/5` | all Stage591 rows | tick 覆盖为零 |
| `validator_context_ready` | `0/45` | all live context fields | validator 继续 fail-closed |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage607_readonly_snapshot_bridge_audit_report_stage607_readonly_snapshot_bridge_audit_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage607_readonly_snapshot_bridge_audit_decision_stage607_readonly_snapshot_bridge_audit_v1.json`
- snapshot inventory：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage607_readonly_snapshot_bridge_audit_snapshot_inventory_stage607_readonly_snapshot_bridge_audit_v1.csv`
- symbol coverage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage607_readonly_snapshot_bridge_audit_symbol_coverage_stage607_readonly_snapshot_bridge_audit_v1.csv`
- context rows：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage607_readonly_snapshot_bridge_audit_context_rows_stage607_readonly_snapshot_bridge_audit_v1.csv`
- order readiness：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage607_readonly_snapshot_bridge_audit_order_readiness_stage607_readonly_snapshot_bridge_audit_v1.csv`
- pre submit heatmap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage607_readonly_snapshot_bridge_audit_pre_submit_heatmap_stage607_readonly_snapshot_bridge_audit_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage607_readonly_snapshot_bridge_audit_gates_stage607_readonly_snapshot_bridge_audit_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage607_readonly_snapshot_bridge_audit_chart_stage607_readonly_snapshot_bridge_audit_v1.png`

## 图表视觉复盘

- 图表已视觉检查。
- 左上图显示 Stage174 文件快照确实存在，contracts `19,079` 行很大，但颜色是 stale 红色；这说明问题不是“没有文件”，而是文件不能代表当前实盘上下文。
- 右上图显示 Stage591 submit plan 的 contract/position/tick 覆盖全部为 `0/5`，视觉上没有任何蓝色覆盖条；这直接否定用旧快照证明历史 submit plan 可成交。
- 左下 heatmap 中 `ref/payload` 为绿色，说明 Stage591 交易意图和干跑 payload 仍可读；从 `contract/account/position/limit/band/margin/operator` 开始全部为红色，说明 validator 没有错误放行旧 context。
- 右下失败闸门全部集中在 tick、freshness、symbol coverage、validator context；下一步非常明确，不是继续收益回测，而是刷新当前/未来信号的 read-only snapshot 并捕获 tick。

## 结论

- Stage607 证明：Stage174 persisted read-only snapshot 可以被 Stage606 validator 加载，文件桥接层成立。
- Stage607 也证明：现有旧快照不能让 Stage079/Stage526 类结构声明真实交易无偏差，因为它过期、无 tick、且与 Stage591 历史合约不对齐。
- 当前不能进入 exact `vt_orderid` writer，也不能启动真实 submit。下一步必须先对当前/未来 submit plan 做 fresh read-only snapshot，字段至少包括 contract/account/position/tick/limit/band/margin，并保持 `operator_confirmation=false` 时 fail-closed。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有收益回测、没有策略参数、没有筛品种、没有交易白名单。
  - 输出主动拒绝旧快照，不用它硬凑执行通过。
  - 修复 `confirmed_flat` 新鲜度判断减少了误放行风险，而不是让指标更好看。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：
  - 它把 Stage606 的空快照 fail-closed 往真实 read-only 文件桥接推进了一步。
  - 现在断点清晰落在 fresh snapshot、tick capture、当前/未来 submit plan 对齐，而不是泛泛说“缺实盘证据”。
  - 继续做该方向比继续扩池收益扫描更直接服务目标里的“真实交易不存在偏差”。

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_live_context_adapter.py examples/portfolio_backtesting/analyze_qmt_roll_stage607_readonly_snapshot_bridge_audit.py`：通过。
- Stage607 decision JSON 已复读。
- Stage607 report/gates/symbol coverage 已核对。
- Stage607 chart 已视觉检查。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新最新状态和下一步。
- 是否更新 `research/registry.md`：是，更新当前线最新阶段摘要。
- 是否追加根目录 `memory.md/back_log.md`：否。没有正式候选、重要突破或路线废弃。
