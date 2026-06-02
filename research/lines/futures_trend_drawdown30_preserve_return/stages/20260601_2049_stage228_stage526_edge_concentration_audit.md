# Stage228 Stage526候选edge集中度审计

- 时间：2026-06-01 20:49 CST
- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage528_stage526_edge_concentration_audit.py`
- 性质：只读反过拟合审计；不改策略、不重跑回测。
- 决策：`edge_not_one_day_leave_year_positive`

## 开始前反思

- 是否过拟合：需要检验。Stage226 候选相对旧硬通过壳收益优势较大，必须确认不是一两个交易日或单一年份贡献。
- 是否值得继续：是。若 edge 集中，候选只能降级 paper；若不过度集中，才可进入下一轮候选复盘。

## 结果

相对旧收益优先硬壳 `r080_pc25_u75`：

- 总 edge PnL：`5,939,790`
- 正 edge PnL：`26,410,815`
- 负 edge PnL：`-20,471,025`
- top5 正贡献占比：`10.4406%`
- top10 正贡献占比：`16.8134%`
- 最大年度 edge：`2,292,025`
- 最大年度占总 edge：`38.5876%`
- edge 为正的日占比：`37.7937%`
- 剔除任意一年后，剩余 edge 仍全部为正；剔除 2025 后仍有 `3,647,765`。

相对 `r070_pc30_u75`：

- 总 edge PnL：`6,879,210`
- top5 正贡献占比：`10.6518%`
- 剔除任意一年后仍为正。

相对 near-pass `r080_pc30_u80`：

- 总 edge PnL：`3,146,970`
- top5 正贡献占比：`8.2094%`
- 剔除任意一年后仍为正。

图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage528_stage526_edge_concentration_audit_chart_stage528_stage526_edge_concentration_audit_v1.png`

视觉判断：累计 edge 长期向上，2025 年贡献最大但不是唯一来源；年度柱状图显示 2021、2023、2024、2025、2026 均为正，2022 略负但不推翻整体。

## 结论

`r080_pc25_maxpos4` 的优势不是一日型，也不是单一年份型。它可以作为当前主研究候选进入下一轮“更严格真实部署复盘”：逐笔/产品归因、最差窗口复盘、成本和保证金安全垫评估。

## 结束反思

- 是否过拟合：当前证据倾向否；但 3x成本失败和短持有左尾仍是限制。
- 是否值得继续：是。下一步不再扫 `cap=24/26` 或 `maxpos=3/5`，而是固定 `r080_pc25_maxpos4` 做候选级深复盘。

