# Stage245 Phase B 重复委托与目标持仓校验

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：`2026-05-11 15:27 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：半自动执行提交前附加安全校验
- 是否重要突破：是，Phase B 已补齐重复送单与重复开仓两道核心边界
- 是否触发A/B：否，不修改 `78-1` 策略逻辑

## 外部调研与判断

- 参考资料与仓库内先验：
  - `Stage244` 已建立 `account/env/readonly-probe` 级别的 `fail-closed` 安全闸门。
  - 真实执行事故里，最常见的下一层问题不是“连不上”，而是“同一意图重复送单”与“账户里其实已有目标仓位还继续开”。
- 我的判断：
  - 这两道校验必须独立存在，不能混在 `Stage244` 里。
  - 原因是它们属于“执行幂等与仓位一致性”层，而不是“账户连接是否可用”层。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage245_phaseb_duplicate_and_target_checks.py`
- 修改正式策略脚本：无
- 删除脚本：无
- 新增参数：无策略参数
- 修改参数：无
- 删除参数：无

## 校验逻辑

### 1. same-intent duplicate order check

- 检查本地 `approval ledger` 是否出现：
  - 同一个 `intent_id` 被重复记录
  - 当前行已经存在 `broker_order_id`
  - 当前行 `submit_status != not_submitted`
- 额外检查真实委托快照里，是否已有：
  - 同 `vt_symbol`
  - 同 `direction`
  - 同 `offset`
  - 且仍是活跃状态的委托

### 2. target position already reached check

- 检查真实持仓快照：
  - 同 `vt_symbol`
  - 同方向持仓量
- 再加上同方向未完成开仓量
- 若 `现有仓位 + 挂单量 >= planned_volume`，则不允许再次提交

## 结果

- 样例交易日：`2026-04-30`
- 样例委托：`PHASEB-20260430-001`
- 检查结果：
  - `base_can_submit=0`
  - `duplicate_check_status=passed`
  - `target_position_check_status=not_checked`
  - `target_position_check_reason=position_snapshot_missing`
  - `final_can_submit=0`
  - `final_failure_reason=broker_account_snapshot_missing`

## 解释

- 这次重复委托检查通过，说明当前本地账本里不存在“同一意图已经被提交过”的证据。
- 目标持仓检查无法完成，不是因为逻辑错误，而是因为当前仍然没有真实持仓快照。
- 所以最终阻断原因仍然回到根问题：
  - `broker_account_snapshot_missing`

## 输出文件

- results：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage245_phaseb_duplicate_target_results_20260430_stage245_phaseb_duplicate_and_target_checks_v1.csv`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage245_phaseb_duplicate_target_summary_20260430_stage245_phaseb_duplicate_and_target_checks_v1.json`
- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage245_phaseb_duplicate_target_report_20260430_stage245_phaseb_duplicate_and_target_checks_v1.md`

## 结论

- 当前 `Phase B` 已形成 3 层提交前边界：
  - `Stage244`：账户/环境/连接级校验
  - `Stage245`：重复委托幂等校验
  - `Stage245`：目标持仓已达成校验
- 现在系统不是“简单地禁止提交”，而是能明确指出：
  - 哪一层通过
  - 哪一层缺证据
  - 最终为什么不能提交

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只补执行安全边界，不涉及收益优化或参数调节。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：这一步让 `Phase B` 更接近真正可上线的执行骨架，而不是停留在审批演示。

## 下一步建议

1. 回到 `Stage174/SimNow` 账户快照抓取，优先把 `account/position` 快照拿通。
2. 在账户快照打通后，重新跑 `Stage244 + Stage245`，确认：
   - `target_position_check_status` 能从 `not_checked` 进入 `passed/failed`
3. 在此之前，仍然不要接真实 `submit_order()`。
