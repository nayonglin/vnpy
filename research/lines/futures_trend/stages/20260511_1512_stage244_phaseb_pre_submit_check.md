# Stage244 Phase B 提交前 broker-state 校验

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：`2026-05-11 15:12 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：半自动执行提交前安全闸门
- 是否重要突破：是，Phase B 已具备 fail-closed 的提交前校验
- 是否触发A/B：否，不修改 `78-1` 策略逻辑

## 外部调研与判断

- 参考资料与仓库内先验：
  - `Stage174` 只读探针已经能给出 `summary/accounts/positions/orders/logs` 快照。
  - `Stage243` 审批状态机已经能把委托推进到 `approved_waiting_precheck`。
- 我的判断：
  - 在接真实 `submit_order()` 之前，最重要的不是“能不能发单”，而是“缺信息时能不能坚决不发单”。
  - 所以这一步必须是 `fail-closed`：只要真实账户状态不充分，就判定 `can_submit=0`。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage244_phaseb_pre_submit_check.py`
- 修改正式策略脚本：无
- 删除脚本：无
- 新增参数：无策略参数
- 修改参数：无
- 删除参数：无

## 校验逻辑

- 输入：
  - `Stage243 approval ledger`
  - `Stage174 readonly probe summary`
  - `Stage174 readonly probe accounts/positions/orders/logs`
- 失败条件：
  - `approval_status != approved_waiting_precheck`
  - `allow_real_new_orders != 1`
  - `readonly_probe_status != connected_or_attempted_readonly`
  - `missing_required_env != []`
  - `ctp_gateway_import_available != true`
  - 日志中出现明显错误关键词
  - `broker_account_rows == 0`
  - 存在未完成真实委托

## 结果

- 样例交易日：`2026-04-30`
- 样例委托：`PHASEB-20260430-001`
- pre-submit check 结果：
  - `pre_submit_check_status=failed`
  - `can_submit=0`
  - `failure_reason=broker_account_snapshot_missing`
- 只读探针状态：
  - `connected_or_attempted_readonly`
  - 说明连接/尝试连接发生过，但没有形成可用账户快照

## 输出文件

- results：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage244_phaseb_pre_submit_check_results_20260430_stage244_phaseb_pre_submit_check_v1.csv`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage244_phaseb_pre_submit_check_summary_20260430_stage244_phaseb_pre_submit_check_v1.json`
- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage244_phaseb_pre_submit_check_report_20260430_stage244_phaseb_pre_submit_check_v1.md`

## 结论

- 当前结论：Phase B 的安全闸门已经跑通，并且行为正确。
- 正确之处不在于“放行提交”，而在于“真实账户快照不完整时，坚决不放行”。
- 这意味着：
  - 当前系统已经具备 `draft -> approve -> precheck -> fail-closed` 的执行骨架
  - 但仍然不能接真实 `submit_order()`

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只做执行安全闸门，不涉及策略收益优化。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：现在已经能明确区分“可审批”和“可提交”，这是真实执行的核心边界。

## 下一步建议

1. 继续完善 `Stage174/SimNow` 账户快照抓取。
2. 只有当 `broker_account_snapshot_missing` 被消除后，才允许讨论真实 submit。
3. 在真实 submit 前，再补一层：
   - `same-intent duplicate order check`
   - `target position already reached check`
