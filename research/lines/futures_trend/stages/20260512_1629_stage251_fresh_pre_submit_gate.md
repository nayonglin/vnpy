# Stage251 Phase B 提交前即时再探针闸门

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：`2026-05-12 16:29`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：真实提交前即时账户/持仓/挂单快照闸门
- 是否重要突破：是
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - vn.py `MainEngine.send_order` / `OrderRequest` 流程
  - vnpy_ctp 网关登录、查询资金、查询持仓逻辑
  - 本地 Stage174/244/245/249/250 输出
- 我的判断：真实下单前不能复用旧快照；必须在提交前即时重跑只读探针。如果探针没有拿到 `readonly_snapshots_received` 和可确认持仓状态，就应该停止后续闸门，不再污染审批账本。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage251_phaseb_fresh_pre_submit_gate.py`
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage250_phaseb_vnpy_order_request_builder.py`
- 删除脚本：无
- 新增参数：
  - `--wait-seconds`
  - `--max-snapshot-age-seconds`
  - `--simnow-front`
  - `--skip-real-block-test`
- 修改参数：无
- 删除参数：无
- 代码修正：
  - Stage251 串行执行：Stage174 新鲜只读探针 -> Stage244 -> Stage245 -> Stage249 dry-run -> Stage250 dry-run -> Stage250 real 阻断测试。
  - Stage251 若 Stage174 未拿到有效快照，立即停止后续步骤，避免陈旧或空快照污染 ledger。
  - Stage250 对空合约 CSV 改为优雅阻断，不再抛 `EmptyDataError`。

## 回测/归因参数

- 数据区间：不适用
- 账户规模：不适用
- 成本口径：不适用
- 样本过滤：不适用
- 策略/归因口径：Phase B 样例委托 `2026-04-30` / `PHASEB-20260430-001`

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - `trading` 前置复验：`readonly_logs_without_ctp_progress`，最终阻断，真实 submit/send_order 调用次数 `0`
  - `7x24` 前置复验：`readonly_trading_login_failed`
  - `7x24` 登录失败信息：`CTP:不合法的登录`
  - 最新 Stage251 最终状态：`fresh_pre_submit_gate_blocked`
  - 最新阻断原因：`all_commands_ok;readonly_status_not_snapshots_received;position_snapshot_not_confirmed`
  - 后续 Stage244/245/249/250：`not_run`，因为新鲜探针未通过
  - 真实 submit/send_order 调用次数：`0`

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage251_phaseb_fresh_pre_submit_gate_report_20260430_stage251_phaseb_fresh_pre_submit_gate_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage251_phaseb_fresh_pre_submit_gate_summary_20260430_stage251_phaseb_fresh_pre_submit_gate_v1.json`
- orders：不适用
- daily：不适用
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage251_phaseb_fresh_pre_submit_gate_command_log_20260430_stage251_phaseb_fresh_pre_submit_gate_v1.txt`

## 结论

- 本阶段结论：Stage251 闸门已实现，且在当前 SimNow 前置不可用/登录失败时正确 fail-closed，没有触发任何真实下单调用。
- 是否进入下一步：是，但不是继续写真实 submit；应先解决 SimNow/CTP 前置登录稳定性。
- 下一步：在交易前置可用时段重跑 `SIMNOW_FRONT=trading`；若仍失败，检查 SimNow 密码、前置、AppID/AuthCode 是否与所选前置匹配。

## 过拟合反思

- 运行前判断：否。即时再探针只检查执行状态新鲜度，不改策略信号或参数。
- 运行后判断：否。本阶段阻断是交易连接/账户状态问题，不会反向优化历史结果。
- 原因：这是实盘安全闸门，目标是防止陈旧状态下单。

## 继续价值反思

- 运行前判断：是。真实提交前必须有即时快照。
- 运行后判断：是。闸门成功证明了失败时会停住，下一步应处理连接稳定性。
- 原因：实盘系统不只要能在顺境通过，也要能在前置异常时干净地停下来。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：暂不追加，等 Stage251 在可用交易前置通过后再写重要合入摘要
