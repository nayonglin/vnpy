# Stage164：entry_context 可观测性修复

- 研究线：`futures_trend_stage819_intraday_rules`
- 工作模式：`day`
- 执行时间：`2026-07-01 01:09 CST`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 分支：`master`
- 本阶段性质：观测性修复 + 单测，不改策略交易逻辑，不连接 CTP，不调用订单 API。

## 外部调研与判断

按用户约束，本阶段不做外部搜索；只使用当前仓库源码、Stage162/163 结果、当前测试体系和本地输出。

判断：Stage163 已证明 `reverse_entry` 当前没有在 Stage830/847/901 输出中触发，因此不是当前已复现 P0/P1 bug。但源码里确实有反手入口，且旧 `entry_risk` 输出没有原始 `entry_context` 列，未来若 reverse 触发会难以审计。因此本阶段先补可观测性，不改 broker10 cap 行为。

## 本次版本变更

新增测试：

- `tests/test_qmt_entry_context_diagnostics.py`

修改文件：

- `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`

新增审计脚本：

- `examples/portfolio_backtesting/analyze_qmt_roll_stage164_entry_context_observability_audit.py`

新增输出：

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage164_entry_context_observability_audit_source_audit_stage164_entry_context_observability_audit_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage164_entry_context_observability_audit_output_audit_stage164_entry_context_observability_audit_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage164_entry_context_observability_audit_decision_stage164_entry_context_observability_audit_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage164_entry_context_observability_audit_report_stage164_entry_context_observability_audit_v1.md`

新增参数：无。

修改参数：无。

删除参数：无。

策略逻辑改动：无。新增字段只写入 sizing snapshot 和 entry risk diagnostic：

- `_calculate_entry_sizing()` 的 fixed_size 与 risk_budget 两条返回路径新增 `entry_context` 字段。
- `_record_entry_risk_diagnostic()` 新增 `entry_context` 输出列。
- `_append_layer()` 对加仓层补充上下文映射：`regular_add`、`donchian_add`、`post_quality_add`。

这些字段不参与开仓、平仓、止损、重试、AI 选择、手数、保证金 cap 或订单提交。

## TDD 过程

先写红灯测试：

```bash
.py311/bin/python -m unittest tests.test_qmt_entry_context_diagnostics
```

红灯结果：

- `test_entry_sizing_snapshot_preserves_original_context_for_all_branches` 失败：`literal_count=0`
- `test_entry_risk_diagnostic_exports_original_entry_context` 失败：`entry_context` 不在 `_record_entry_risk_diagnostic` 输出中

随后做最小实现，再跑绿灯：

```bash
.py311/bin/python -m unittest tests.test_qmt_entry_context_diagnostics
```

绿灯结果：`Ran 2 tests ... OK`

## Stage164 审计结果

执行命令：

```bash
.py311/bin/python -m py_compile \
  examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py \
  examples/portfolio_backtesting/analyze_qmt_roll_stage164_entry_context_observability_audit.py \
  tests/test_qmt_entry_context_diagnostics.py

.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage164_entry_context_observability_audit.py
```

决策：`stage164_entry_context_observability_source_ready_outputs_need_rerun`

源码检查：

- `sizing_snapshot_preserves_entry_context`：PASS，`literal_count=2`
- `entry_risk_exports_entry_context`：PASS
- `add_layers_have_observable_contexts`：PASS
- `unit_test_exists`：PASS

首次旧输出检查：

- Stage830 entry_risk：`329` 行，`has_entry_context_column=0`
- Stage847 entry_risk：`367` 行，`has_entry_context_column=0`
- Stage901 entry_risk：`1` 行，`has_entry_context_column=0`

解释：这些 CSV 是 Stage164 改动前生成的旧产物；需要重新跑对应 producer 才会物化新列。不能把旧 CSV 缺列理解为源码仍失败。

随后按官方实盘 SOP 只读重跑 Stage901，保持原有区间不变：

```bash
.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py \
  --analysis-start 2026-06-16 \
  --target-date 2026-06-30
```

Stage901 结果：

- analysis_start：`2026-06-16`
- analysis_end：`2026-06-30`
- latest_available_data_date：`2026-06-30`
- target_signal_count：`0`
- pending_order_count：`0`
- current_position_count：`1`
- order_api_called：`false`
- send_order_api_called_count：`0`
- cancel_order_api_called_count：`0`
- risk_level：`normal`

重跑 Stage164 审计后：

- Stage830 entry_risk：旧产物，`has_entry_context_column=0`
- Stage847 entry_risk：旧产物，`has_entry_context_column=0`
- Stage901 entry_risk：已物化新列，`has_entry_context_column=1`，`entry_context_counts={"flat_entry": 1}`
- stale_output_count：从 `3` 降为 `2`

## 回测指标

本阶段没有新增策略回测，不应把观测性修复当成收益指标。

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用

## 逻辑 bug 判断

当前已复现 bug：否。

本阶段修复的是审计盲区：

- 未来如果 `reverse_entry`、`regular_add`、`donchian_add`、`post_quality_add` 出现在 entry risk 中，输出可以直接按 `entry_context` 归因。
- 但本阶段没有改变 reverse broker10 cap 的行为；Stage163 的判断仍成立：不能盲目把 flat-entry cap 原公式套到 reverse_entry。

## 反过拟合反思

开始前判断：否。目标是补执行观测字段，不使用收益反馈，不筛选参数。

结束后判断：否。新增字段只让路径可审计，不进入交易决策，不会因为历史收益而改变策略行为。

## 继续价值反思

开始前判断：有价值。Stage163 显示 reverse path 当前未触发但未来难观测，先补观测比直接改风控公式更稳。

结束后判断：有价值。现在源码层已经能输出 entry_context；下一步若要继续，应选择是否重跑 Stage901 shadow 物化新列，或继续设计 reverse broker10 cap 的 post-close projection/fail-closed guard。

## 决策

决策：`stage164_entry_context_observability_source_ready_outputs_need_rerun`

解释：

- 源码和单测已证明新的观测字段契约成立。
- 当前 Stage901 entry_risk 已经物化新列；Stage830/847 历史大回放 entry_risk 仍是旧产物未重跑，不是代码失败。
- 本阶段不改变当前实盘策略行为；不会影响今晚/后续交易信号生成，只会在重新生成诊断输出时多出 `entry_context` 列。

## 后续 TODO

1. 若要让最新 shadow 诊断产物也带 `entry_context`，下一步跑 Stage901 或对应 producer 重建 entry_risk 输出。
2. 继续 Stage165：reverse broker10 cap 语义设计。优先比较：
   - post-close margin projection；
   - broker10 cap 开启时 reverse fail-closed，只平旧仓，次日按 flat_entry 重新评估。
3. 不继续扫 C9 的 R 倍数、重试次数、月份、品种、方向或窗口。
