# Stage032 - 恢复段高质量标签只读审计

- 时间：`2026-07-01T17:09:52`
- 是否重要突破版本：否；这是只读审计，不是候选策略。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 新增回测结果：无新增真实回测；复用 Stage006/007/021/030/031 产物做标签归因。
- 修改回测结果：无。
- 删除回测结果：无。
- Stage031 恢复集合 lot/event/PNL：`2606` / `2517` / `60296707.20`。
- `tag_entry_or_first_aligned` lot/PNL/PNL占比/source正率：`1150` / `60459052.40` / `1.0027` / `100.00%`。
- `rank_1_9_and_entry_or_first` lot/PNL/PNL占比：`955` / `58108480.00` / `0.9637`。
- 纯入场前 `preentry_core` PNL：`3113093.60`；`OI confirm` PNL：`-8607389.10`。
- full-market consensus top8 lot/year/PNL：`86` / `2` / `13106559.20`。
- 胜率：不新增策略胜率；详见 label_summary。
- 过拟合反思：否。Stage032 没有按结果写交易规则；但若把 lc/SM/2024-2025 或 consensus 的小样本直接交易化，会明显过拟合。
- 继续价值反思：有。开仓日早段质量标签足够强，值得写一个冻结真实引擎验证；纯入场前 OI/consensus 路线暂不值得晋级。
- 后续规划：冻结验证开仓日早段确认后加风险真实引擎；不得按产品/日期/年份/small consensus 样本交易化。

## 输出

- 报告：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage032_recovery_quality_label_audit/rebuilt_c9_stage032_recovery_quality_label_audit_report_stage032_recovery_quality_label_audit_v1.md`
- 决策：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage032_recovery_quality_label_audit/rebuilt_c9_stage032_recovery_quality_label_audit_decision_stage032_recovery_quality_label_audit_v1.json`
- 图表：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage032_recovery_quality_label_audit/rebuilt_c9_stage032_recovery_quality_label_audit_chart_stage032_recovery_quality_label_audit_v1.png`
