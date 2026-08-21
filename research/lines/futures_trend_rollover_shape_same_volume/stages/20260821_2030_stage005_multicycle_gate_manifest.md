# Stage005 多周期 A/C 运行前 Gate Manifest

- line_id：`futures_trend_rollover_shape_same_volume`
- 冻结时间：`2026-08-21 20:30 CST`
- 冻结目的：在读取 Stage005 新结果前固定多周期窗口、A/C 身份、晋级门和全部资金曲线输出。
- A：当前正式 C9/15万，换月续仓开关关闭。
- C：A + `enable_rollover_shape_same_volume_reopen=True` + `backwards_ratio_continuous` + `shrink_to_allowed`。
- 数据区间：`2018-01-01` 至 `2026-05-29`。
- 起点：每年 `1月1日`、`6月1日`。
- 周期：`1年/2年/3年`；decision 只使用完整窗口。每个周期允许额外保留一个距离自然终点不超过 `7` 天的 near-complete terminal 窗口，只作观察。
- 完整周期预期：1年 `15` 个、2年 `13` 个、3年 `11` 个；加各1个 near-complete 和1个完整全周期，共 `43` 窗口、`86` 次 A/C 真引擎运行。
- 完整周期逐组门：C 收益胜率 `>=50%`、收益差中位 `>=0`、DD 非劣 `2pp` 比例 `>=80%`、DD50 失败数不多于 A、Sharpe 非劣 `0.05` 比例 `>=80%`、聚合滑点 C/A `<=105%`、账户全部生存、broker100 失败数不多于 A。
- 完整全周期门：C 收益不低于 A、DD 恶化 `<=1pp`、Sharpe 差 `>=-0.01`、滑点 C/A `<=105%`、账户生存。
- 决策：全部通过只允许 `reopen_official_promotion_review`，不自动晋级；任一失败为 `confirm_do_not_promote_after_multicycle`。
- 输出：summary/comparison/aggregate/全部日级 curves/decision；完整周期、1年、2年、3年和 aggregate 共5张 PNG。
- 安全边界：不改正式配置、物料、master、生产、CTP、订单或撤单链路。
- 运行前过拟合判断：否，周期、起点和门在结果前冻结，不按 Stage004 的 `2018/2022` 调参。
- 运行前继续价值判断：有，用于判断 Stage004 反证是否跨周期普遍存在。
