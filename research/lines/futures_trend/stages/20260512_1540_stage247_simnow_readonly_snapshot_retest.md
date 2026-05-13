# Stage247 SimNow 只读快照重试与 Phase B 闸门复验

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：`2026-05-12 15:40`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：SimNow 密码修正后的只读连接复验 + Phase B 预提交安全闸门复跑
- 是否重要突破：是
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本阶段未新增外部资料检索，沿用 Stage246 对 SimNow / vn.py CTP 只读链路的既有判断；本次目标是验证用户手动修正密码后链路是否恢复。
- 我的判断：这不是策略收益研究，也不是参数优化；它是执行工程闸门验证。密码问题修正后，连接、登录、结算确认、合约与账户快照均已经打通，说明“SimNow 登录失败”不再是当前主阻塞。

## 本次变更

- 新增脚本：无
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage244_phaseb_pre_submit_check.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage245_phaseb_duplicate_and_target_checks.py`
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无
- 代码修正：
  - Stage244 增加 `readonly_snapshots_received` 为合法只读成功状态，避免把真实成功快照误判为 `readonly_probe_not_connected`。
  - Stage245 在 `target_position_check_status=not_checked` 时也写入最终阻断原因，并清理 `nan` 展示。

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
  - SimNow 只读探针状态：`readonly_snapshots_received`
  - 交易服务器：连接成功、授权验证成功、登录成功、结算信息确认成功、合约信息查询成功
  - 行情服务器：连接成功、登录成功
  - `real_order_enabled=false`
  - `order_api_called=false`
  - 账户快照：21 行
  - 持仓快照：0 行
  - 委托快照：0 行
  - 成交快照：0 行
  - 合约快照：19,943 行
  - Stage244：`passed / can_submit=1`
  - Stage245：`final_can_submit=0`
  - Stage245 最终阻断原因：`position_snapshot_missing`

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage244_phaseb_pre_submit_check_report_20260430_stage244_phaseb_pre_submit_check_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage245_phaseb_duplicate_target_report_20260430_stage245_phaseb_duplicate_and_target_checks_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage244_phaseb_pre_submit_check_summary_20260430_stage244_phaseb_pre_submit_check_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage245_phaseb_duplicate_target_summary_20260430_stage245_phaseb_duplicate_and_target_checks_v1.json`
- orders：不适用
- daily：不适用
- quality：不适用

## 结论

- 本阶段结论：用户手动修改 SimNow 密码后，只读连接已经成功，Stage244 账户/挂单预提交闸门已经通过；但 Stage245 仍因 `position_snapshot_missing` 阻断真实提交。
- 是否进入下一步：是
- 下一步：补齐“空持仓快照”语义识别，区分“账户确实空仓”和“持仓事件未回调/未确认”，再决定是否允许 Phase B 继续走到 submit 前的最后一步。

## 过拟合反思

- 运行前判断：否。本阶段不改变第78-1策略、AI选品、资金管理或交易参数。
- 运行后判断：否。所有变更都在执行安全闸门与报告准确性，不能提升历史收益。
- 原因：连接复验和 fail-closed 逻辑只决定是否允许提交，不根据结果反向调参。

## 继续价值反思

- 运行前判断：是。SimNow 只读链路是后续 Mac 上 CTP 实盘/影子盘的基础。
- 运行后判断：是。连接问题已经排除，剩余问题更聚焦，值得继续补齐持仓快照语义。
- 原因：真实执行最怕“以为没仓又重复开仓”，当前阻断虽然保守，但方向正确。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否，待 Phase B submit 前最后闸门完成后再写重要合入摘要
