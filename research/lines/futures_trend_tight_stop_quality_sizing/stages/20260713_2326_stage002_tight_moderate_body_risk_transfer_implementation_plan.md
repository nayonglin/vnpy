# Stage002 实施计划

- 时间：`2026-07-13 23:26 CST`
- line_id：`futures_trend_tight_stop_quality_sizing`
- 阶段：`Stage002`

## 代码边界

- 新增独立研究脚本和独立测试，不修改主策略类、官方配置、实盘入口或其他研究线。
- 候选类继承当前 `QmtRollPortfolioStrategyStage847C9StopRetry`。
- 仅在 `_calculate_entry_sizing` 调用基类前临时缩放当前信号对应的 risk ratio，并在 `finally` 中恢复原参数。
- T-1 ATR 与 K 线实体由当前引擎 `history.iloc[:-1]` 计算；当前开仓日 bar 的修改不得改变这两个特征。

## 必测问题

1. Wilder ATR 与 TA-Lib 对齐。
2. 当前开仓日行情突变不影响 T-1 特征。
3. 高质量/普通/恢复袖套三条分支权重分别为 `1.25/0.75/1.0`。
4. 临时 risk ratio 在异常时也能恢复，避免跨品种污染。
5. 候选新增审计字段不包含 AI 名称或 AI 派生值。
6. A/C 只有 strategy class 和 Stage002 参数存在差异，主策略公共 overrides 完全相同。
7. 每个锚点的日线收益和摘要可从落盘文件独立复算。

## 回测输出

- 四锚点 A/C 摘要和逐日资金曲线。
- 收益保留、回撤改善、Sharpe、滑点和交易次数差异。
- 高质量命中、风险放大、风险缩小、恢复袖套豁免与缺失特征计数。
- 绝对权益、归一化净值、回撤三联图。
- 决策 JSON、报告和 SHA256 manifest。

