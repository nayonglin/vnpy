# Stage081 噪声地板止损距离只读审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 10:26`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读 preflight 审计；不写真引擎、不新增交易规则、不触发 A/B、不改正式配置、不连接 CTP、不调用订单 API。
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - KTH/DiVA `Position sizing methods for a trend following CTA`：趋势跟随仓位方法研究支持 target volatility / drawdown-aware sizing 作为风险治理方向，但不是分钟阈值调参依据。
  - SSRN `Trade Sizing Techniques for Drawdown and Tail Risk Control`：回撤/尾部风险控制应通过可预先定义的 sizing 算法，而不是事后按亏损 cohort 反推。
  - vn.py `vnpy_ctastrategy/engine.py`：stop/order 需要明确触发与成交语义；若未来写真引擎，必须先定义事件顺序，不能用图上后验路径补规则。
- 我的判断：Stage080 已关闭 Tq tick 同源微观规则化，下一步若仍围绕分钟路径，只能看普世风险几何。`stop_distance / prior20 median true range` 是一个合理的只读体检项，但如果它承载右尾，就不能变成过滤、降仓或扩 stop 减手规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage081_noise_floor_stop_distance_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：只读审计参数 `NOISE_LOOKBACK_DAYS=20`、`NOISE_MIN_PERIODS=10`、`UNDER_FLOOR_RATIO=1.0`
- 修改参数：无正式参数修改
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-01 -> 2026-06-15`
- 账户规模：`150000`
- 成本口径：沿用官方 C9/15w Stage010 official curve；本阶段无新增交易成本。
- 样本过滤：official closed lots `399` 笔；Stage861 分钟聚合产品连续 prior20 true range ready `244/399=61.1529%`。
- 策略/归因口径：A 为当前官方正式 C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`；本阶段只把每笔 official closed lot 绑定到 entry 前产品级 `prior20_median_true_range`，若 `stop_distance < prior20_median_true_range` 则标记 `under_noise_floor`。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`53.2560%`
- 其他关键指标：
  - 决策：`stage081_data_not_ready_and_underfloor_contains_right_tail_no_rule`
  - noise ready：`244/399=61.1529%`
  - missing noise：`155` 笔，净 PnL `+5,027,390.00`
  - `under_noise_floor`：`197` 笔，净 PnL `+32,122,278.80`，正贡献 `+49,989,590.00`，负贡献 `-17,867,311.20`，大赢家 `20` 笔
  - `adequate_or_wide_stop`：`47` 笔，净 PnL `+5,904,943.80`，大赢家 `3` 笔
  - `ratio_lt0_5`：`107` 笔，净 PnL `+27,232,772.10`，大赢家 `15` 笔

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage081_noise_floor_stop_distance_audit/qmt_roll_stage081_c9_minrisk_noise_floor_stop_distance_audit_report_stage081_noise_floor_stop_distance_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage081_noise_floor_stop_distance_audit/qmt_roll_stage081_c9_minrisk_noise_floor_stop_distance_audit_summary_stage081_noise_floor_stop_distance_audit_v1.csv`
- daily：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage081_noise_floor_stop_distance_audit/qmt_roll_stage081_c9_minrisk_noise_floor_stop_distance_audit_contribution_curve_stage081_noise_floor_stop_distance_audit_v1.csv`
- quality：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage081_noise_floor_stop_distance_audit/qmt_roll_stage081_c9_minrisk_noise_floor_stop_distance_audit_features_stage081_noise_floor_stop_distance_audit_v1.csv`
- visuals：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage081_noise_floor_stop_distance_audit/qmt_roll_stage081_c9_minrisk_noise_floor_stop_distance_audit_official_path_noise_floor_chart_stage081_noise_floor_stop_distance_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage081_noise_floor_stop_distance_audit/qmt_roll_stage081_c9_minrisk_noise_floor_stop_distance_audit_noise_ratio_scatter_stage081_noise_floor_stop_distance_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage081_noise_floor_stop_distance_audit/qmt_roll_stage081_c9_minrisk_noise_floor_stop_distance_audit_bucket_year_heatmap_stage081_noise_floor_stop_distance_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage081_noise_floor_stop_distance_audit/qmt_roll_stage081_c9_minrisk_noise_floor_stop_distance_audit_atlas_page001_stage081_noise_floor_stop_distance_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage081_noise_floor_stop_distance_audit/qmt_roll_stage081_c9_minrisk_noise_floor_stop_distance_audit_atlas_page002_stage081_noise_floor_stop_distance_audit_v1.png`

## 视觉分析

- 资金曲线：`under_noise_floor` 橙线从 `2023` 后承担主要上行台阶，`2025` 有明显大跳升；这不是坏信号集合。
- 年度热力图：`ratio_lt0_5` 在 `2021-2025` 连续为正，`2023` 单年约 `+1032w`，`2025` 约 `+695w`；`ratio_0_5_1` 虽有 `2022/2024/2026` 负贡献，但 `2023/2025` 大幅正贡献，不能写成普世规则。
- 散点图：最高 R 倍数和最大 PnL 均集中在 `stop/noise < 1` 区域；`>=1` 区域没有形成更强右尾。
- 分钟 atlas：under-floor 亏损样本并不都由初始噪声打掉，部分亏损来自后续趋势失败；under-floor 赢家样本入场后很快沿趋势方向走开，说明低 stop/noise 也可能是 C9 凸性来源。

## 结论

- 本阶段结论：不进入真引擎。产品连续 prior20 噪声覆盖只有 `61.1529%`，且已 ready 的 `under_noise_floor` 样本承载 `+3212w` 右尾净贡献和 `20` 个大赢家；用 `stop/noise < 1` 做降风险、过滤、扩 stop 减手，都会直接伤害 C9 的收益来源。
- 是否进入下一步：不沿该规则化方向继续。
- 下一步：若继续低回撤目标，不再围绕 stop/noise ratio 扫 `lookback/min_period/ATR multiplier/ratio bucket`；只能换真正外生、入场前可见、覆盖完整的数据源，或做不改变 C9 单笔路径的账户层固定规则多起点审计。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但若继续按 `ratio_lt0_5/0_5_1`、lookback、产品、方向、年份或月份调规则，就是过拟合。
- 原因：本阶段只做一个 conventional prior20 true-range 只读诊断，没有优化阈值；结论来自资金曲线、热力图、散点和分钟 atlas 的一致反证。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：该噪声地板直接规则化方向无继续价值；整条研究线仍有价值。
- 原因：Stage081 证明“官方止损小于日线噪声”并不等于低质量信号，反而常是右尾凸性的载体；继续价值应转向更独立的信息源或账户层路径，而不是把这个比率参数化。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
