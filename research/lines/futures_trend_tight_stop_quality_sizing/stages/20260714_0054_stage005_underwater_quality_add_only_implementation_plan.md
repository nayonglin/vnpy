# Stage005 实施计划

- 时间：`2026-07-14 00:54 CST`
- line_id：`futures_trend_tight_stop_quality_sizing`

## 隔离实现

- 新增独立脚本、测试与输出目录，不修改正式策略、Stage003 或 Stage004。
- 继承 Stage004 的严格分钟证据和因果水下状态门，仅把 `stage003_other_weight` 冻结为 `1.0`。
- 新增 `stage005_reason/stage005_budget_weight/stage005_quality_add_only` 审计字段，避免把普通机会 `1.0x` 错记为降风险。

## fail-close

1. 高水位所有候选必须 `1.0x`。
2. 水下 quality 必须 `1.25x`；水下 other 必须 `1.0x`。
3. 风险金额前后必须严格满足 `after = before * weight`。
4. T-1 特征覆盖、AI 月池、配置差异、成交与止损重试继续沿用 Stage003/004 守恒审计。
5. 输入输出清单写入 SHA-256；任何运行期分钟缺口使整次回测失败。
