# Stage242-243 Phase B 半自动执行原型

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：`2026-05-11 14:57 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：半自动执行原型落地
- 是否重要突破：是，Phase B 从流程设计进入可运行原型
- 是否触发A/B：否，不修改 `78-1` 策略逻辑

## 外部调研与判断

- 参考资料与仓库内先验：
  - `Stage154/155` 已提供 `signal_intent / order_event / fill_event / reconcile` 数据 schema。
  - `Stage238` 已提供信号日报与部署账本日报的组合输入。
- 我的判断：
  - 真实执行前，先把 `order_draft` 和 `approve/reject` 状态机落地，是最小且最不危险的一步。
  - 只要真实 submit 还没接上，就不会污染策略层，也不会引入下单事故。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/build_qmt_roll_stage242_phaseb_order_draft.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage243_phaseb_approval.py`
- 修改正式策略脚本：无
- 删除脚本：无
- 新增参数：无策略参数
- 修改参数：无
- 删除参数：无

## 原型口径

- 输入：
  - `Stage186 2026 cold start summary`
  - `Stage186 signal_plan`
  - `Stage238 balanced_tranche shadow daily bundle summary`
- 样例交易日：`2026-04-30`
- 样例信号：
  - `MA609.CZCE Long Open 16手`
- Phase B 目标：
  - 先生成 `pending_manual_approval` 草案
  - 再通过人工命令把状态切换到 `approved_waiting_precheck`
  - 不触发真实下单

## 结果

- Stage242 结果：
  - 已生成 `order_draft`
  - 当日 `1` 笔信号被映射为 `1` 笔待审批草案
  - 初始状态：`pending_manual_approval`
- Stage243 结果：
  - 已对 `PHASEB-20260430-001` 执行 `approve`
  - 新状态：`approved_waiting_precheck`
  - `pre_submit_check_status=pending`
  - `submit_status=not_submitted`
- 关键事实：
  - 本阶段没有真实下单
  - 只是跑通了 `draft -> approve -> pending precheck` 状态流

## 输出文件

- Stage242 draft：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage242_phaseb_order_draft_draft_20260430_stage242_phaseb_order_draft_v1.csv`
- Stage242 summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage242_phaseb_order_draft_summary_20260430_stage242_phaseb_order_draft_v1.json`
- Stage242 report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage242_phaseb_order_draft_report_20260430_stage242_phaseb_order_draft_v1.md`
- Stage243 approval ledger：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage243_phaseb_approval_ledger_20260430_stage243_phaseb_approval_v1.csv`
- Stage243 events：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage243_phaseb_approval_events_20260430_stage243_phaseb_approval_v1.csv`
- Stage243 summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage243_phaseb_approval_summary_20260430_stage243_phaseb_approval_v1.json`
- Stage243 report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage243_phaseb_approval_report_20260430_stage243_phaseb_approval_v1.md`

## 结论

- 本阶段结论：Phase B 已经不是文档设计，而是可运行原型。
- 当前已打通的状态流：
  - `signal_plan -> order_draft -> pending_manual_approval -> approved_waiting_precheck`
- 当前还没做的部分：
  - 真正的 `pre-submit broker-state check`
  - 真实 `submit_order()`
  - 订单/成交回报写回

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只落地执行状态机，不调策略参数，不做收益导向修改。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：现在已经把半自动执行最核心的两步固定下来，后续可以安全地接 `pre-submit check`。

## 下一步建议

1. 做 `Stage244 pre-submit broker-state check`：
   - 读取真实账户/持仓/未完成委托
   - 校验是否允许真正提交
2. 保持 `submit_order()` 仍然关闭。
3. 等 precheck 跑稳后，再讨论接柜台真实发单。
