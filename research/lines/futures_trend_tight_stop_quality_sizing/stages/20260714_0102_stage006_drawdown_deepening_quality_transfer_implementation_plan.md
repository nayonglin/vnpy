# Stage006 实施计划

- 时间：`2026-07-14 01:02 CST`
- line_id：`futures_trend_tight_stop_quality_sizing`

## 隔离实现

- 新增独立脚本、测试和输出目录，不修改 Stage847、Stage003/004/005 或正式配置。
- 在策略每日 `_refresh_risk_state` 中记录刷新前后的回撤；同一日全部候选共用该日状态快照。
- sizing 前仅按 `current > prior` 临时启用 Stage003，`finally` 恢复原开关。

## fail-close

1. `current/prior/delta/gate` 必须逐行严格相符。
2. gate 关闭时 weight 必须 `1.0`；gate 开启时只允许 quality `1.25`、other `0.75` 或既有豁免 `1.0`。
3. 风险金额、特征日期、AI 月池、配置、成交与止损重试继续做守恒审计。
4. 运行期分钟缺口使整轮回测失败；输入输出清单写 SHA-256。
