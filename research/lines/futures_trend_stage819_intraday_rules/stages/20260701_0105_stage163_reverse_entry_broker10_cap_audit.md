# Stage163：reverse_entry 与 broker10 cap 边界审计

- 研究线：`futures_trend_stage819_intraday_rules`
- 工作模式：`day`
- 执行时间：`2026-07-01 01:05 CST`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 分支：`master`
- 本阶段性质：只读源码/输出审计，不改策略参数，不连接 CTP，不调用订单 API。

## 外部调研与判断

按用户约束，本阶段不做外部搜索；只使用当前仓库源码、Stage160/162 暴露的 WARN、Stage830/847/901 已生成输出和本地研究记录。

判断：Stage162 的 `broker10_cap_flat_entry_scope` WARN 不是当前已经发生的交易错误，但它是一个需要工程收敛的 P2 边界。不能简单把 Stage830 flat-entry cap 扩展到 `reverse_entry`，因为反手路径是先设置平仓 target，再计算新方向 sizing；此时 `_reserved_margin_in_use()` 仍按 `total_margin_in_use + pending_margin_reservation` 计算，旧仓保证金不一定已经释放，直接套用 flat-entry cap 可能双算旧仓保证金并误杀反手。

## 本次版本变更

新增文件：

- `examples/portfolio_backtesting/analyze_qmt_roll_stage163_reverse_entry_broker10_cap_audit.py`

新增输出：

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage163_reverse_entry_broker10_cap_audit_source_audit_stage163_reverse_entry_broker10_cap_audit_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage163_reverse_entry_broker10_cap_audit_output_audit_stage163_reverse_entry_broker10_cap_audit_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage163_reverse_entry_broker10_cap_audit_decision_stage163_reverse_entry_broker10_cap_audit_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage163_reverse_entry_broker10_cap_audit_report_stage163_reverse_entry_broker10_cap_audit_v1.md`

新增参数：无。

修改参数：无。

删除参数：无。

策略逻辑改动：无。本阶段没有修改开仓、反手、AI、止损、重试、仓位或保证金 cap 行为。

## 执行命令

```bash
.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage163_reverse_entry_broker10_cap_audit.py
.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage163_reverse_entry_broker10_cap_audit.py
```

## 审计结果

决策：`stage163_reverse_entry_not_current_bug_but_guard_required`

当前输出证据：

- Stage830 entry candidates：`926` 行，`reverse_string_hits=0`，`entry_context={"flat_entry": 926}`
- Stage830 trade events：`864` 行，`reverse_string_hits=0`
- Stage830 cap events：`35` 行，`entry_context={"flat_entry": 35}`
- Stage847 entry candidates：`923` 行，`reverse_string_hits=0`，`entry_context={"flat_entry": 923}`
- Stage847 trade events：`892` 行，`reverse_string_hits=0`
- Stage901 entry candidates：`11` 行，`reverse_string_hits=0`，`entry_context={"flat_entry": 11}`
- Stage901 trade events：`0` 行
- 汇总：`reverse_hits_total=0`

源码证据：

- 基础策略存在 `2` 个 `entry_context="reverse_entry"` sizing call site，分别对应 long->short 和 short->long。
- 当前 `_record_entry_candidate_snapshot` 只观察到 `flat_entry` 字面量；如果未来 reverse 触发，只看 entry_candidates 会低估。
- Stage830 cap 明确是 `entry_context != "flat_entry"` 时 `reason=not_flat_entry` 并直接返回 sizing。
- `_close_all_layers_and_set_flat_target` 设置 `set_target(contract_vt_symbol, 0)`，但该函数内不更新 `total_margin_in_use`。
- `_reserved_margin_in_use()` 使用 `total_margin_in_use + pending_margin_reservation`。

## 逻辑 bug 判断

当前已复现 bug：否。

理由：

- 当前 Stage830/847/901 输出里没有 reverse 交易或 reverse candidate 命中。
- 当前实盘 shadow 最新输出没有订单 API 调用，也没有 pending/signal 触发该路径。

潜在 bug / 工程风险：是，P2。

理由：

- 反手路径在源码里存在，一旦未来触发，Stage830 broker10 cap 不会作用于 reverse_entry。
- 但不能直接复用 flat-entry cap 公式，因为旧仓保证金释放时序不同，可能双算旧仓。
- 现有 entry_candidates 对 reverse 可观测性不足，未来如果只看 entry_candidates 可能漏报反手行为。

## 回测指标

本阶段没有新增策略回测，不应把审计结果当作收益指标。

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用

## 反过拟合反思

开始前判断：否。Stage163 是 execution path 审计，不使用收益结果，也不改参数。

结束后判断：否。结论来自源码时序和当前输出是否命中 reverse，不按年份、品种、方向或收益表现倒推规则。

## 继续价值反思

开始前判断：有价值。Stage162 的 WARN 指向一个可能影响未来执行安全的路径，需要分清“当前 bug”和“潜在边界”。

结束后判断：有价值。当前没有复现 reverse 执行错误，但发现了两个应收敛点：reverse 可观测性不足，以及 reverse broker10 cap 不能直接套用 flat-entry 公式。

## 决策

决策：`stage163_reverse_entry_not_current_bug_but_guard_required`

解释：

- 不把这个风险升级成当前实盘 P0/P1 bug。
- 不直接修改 Stage830 cap 行为，以免引入双算保证金的新问题。
- 下一步应先补 reverse_entry 的可观测性；如果要让 broker10 cap 覆盖 reverse，需要设计 post-close margin projection 或明确 fail-closed reverse guard。

## 后续 TODO

1. 补 reverse_entry 的 entry candidate / entry risk 可观测字段，至少能在输出里区分 flat/reverse/rollover/add。
2. 设计 reverse_entry 的 broker10 cap 语义：
   - 方案 A：post-close projected margin，即从 `reserved_margin_before` 中扣除待平旧仓估算保证金后再测新仓。
   - 方案 B：fail-closed guard，即在 broker10 cap 开启且 reverse cap 未验证前，未来 reverse 信号不直接开反手，只平旧仓，等下个交易日按 flat_entry 重新评估。
3. 以上任一方案都必须做单元/targeted path test 和至少 Stage156/157 级别回放验证；不得直接用当前旧收益记录证明安全。
