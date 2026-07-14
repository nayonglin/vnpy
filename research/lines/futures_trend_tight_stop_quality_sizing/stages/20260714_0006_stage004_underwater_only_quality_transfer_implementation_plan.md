# Stage004 实施计划

- 时间：`2026-07-14 00:06 CST`
- line_id：`futures_trend_tight_stop_quality_sizing`

## 隔离实现

- 新脚本/新测试/新输出目录，不修改 Stage847、正式配置、实盘入口或 Stage003 冻结结果。
- Stage004 class 继承修复后的 Stage003 class，只在调用 sizing 前根据当前 `portfolio_drawdown_pct` 决定是否临时启用风险转移，并在 `finally` 中恢复。
- 新增审计：signal-date drawdown、underwater gate active、gate reason；同时保留全部 Stage003 T-1 特征和风险前后字段。

## fail-close

1. `drawdown == 0` 的 flat-entry 必须 weight `1.0`、reason `high_water_unchanged`。
2. `drawdown > 0` 的 flat-entry 才允许出现 `1.25/0.75`。
3. feature date 必须等于 signal date，覆盖率至少 99%。
4. A/C 公共配置零漂移；新增 AI 字段为 0；AI 月覆盖全部 PASS。
5. A/C trade count 与 daily 对齐，retry count/volume、`stop_r=0.5`、`max_retries=1` 全部守恒。
6. output/input manifest 全量 hash 通过。

