# Stage031 - Stage029 信号日/成交日滞后匹配归因

- 时间：`2026-07-01T16:57:54`
- 是否重要突破版本：否；这是只读归因，不是候选策略。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 新增回测结果：无新增真实回测；复用 Stage006/Stage030 产物做滞后匹配归因。
- 修改回测结果：无。
- 删除回测结果：无。
- Stage006 实际打开的暂停事件：`2587`。
- 滞后 closed-lot 匹配事件：`2517`，匹配率 `97.2942%`。
- Stage006 滞后匹配 realized PnL：`60296707.20`。
- loss_streak_only 事件/PNL：`2088` / `58285212.40`。
- candidate AI rank 1-9 PNL：`60903256.60`；rank>9 PNL：`-838450.20`。
- 胜率：不新增策略胜率；使用滞后 matched event 正负 PnL 事件。
- 过拟合反思：否。本阶段只修正归因口径并输出只读证据；如果直接按 lc/SM/si 或单年月份写豁免规则，会变成过拟合。
- 继续价值反思：有。下一步值得验证一个极低自由度的高质量恢复标签，但必须跨 source、跨年份、跨产品成立；否则应转非交易账户层资金安排。
- 后续规划：可做一个预声明、低自由度的高质量恢复标签只读验证；不得按产品/日期/年份硬编码。

## 输出

- 报告：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage031_stage029_execution_lag_recovery_signal_audit/rebuilt_c9_stage031_stage029_execution_lag_recovery_signal_audit_report_stage031_stage029_execution_lag_recovery_signal_audit_v1.md`
- 决策：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage031_stage029_execution_lag_recovery_signal_audit/rebuilt_c9_stage031_stage029_execution_lag_recovery_signal_audit_decision_stage031_stage029_execution_lag_recovery_signal_audit_v1.json`
- 图表：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage031_stage029_execution_lag_recovery_signal_audit/rebuilt_c9_stage031_stage029_execution_lag_recovery_signal_audit_execution_lag_recovery_chart_stage031_stage029_execution_lag_recovery_signal_audit_v1.png`
