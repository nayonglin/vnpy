# Stage021 same_direction_correlation_crowding_proxy 同向相关拥挤风险代理审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-19 21:22 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读 closed-lot 归因 + 日度 active-risk proxy，不是撮合级真引擎
- 是否重要突破：否
- 是否触发A/B：否，本阶段预声明 `candidate_ready=0`，不改正式配置、不连接 CTP、不调用订单 API

## 外部调研与判断

- 参考资料：
  - Rob Carver `When endogenous risk management isn't enough: a simple risk overlay`：趋势系统内生风控仍可能因相关性、波动跳跃和风险估计误差失效，因此可在主系统外做简洁风险覆盖层。链接：https://qoppac.blogspot.com/2020/05/when-endogenous-risk-management-isnt.html
  - Rob Carver `Exogenous risk overlay: take two`：风险覆盖层应关注 expected risk、correlation shock、jump volatility、leverage 等组合状态，且 multiplier 在 `0-1` 之间，不应该变复杂。链接：https://qoppac.blogspot.com/2022/02/exogenous-risk-overlay-take-two.html
  - `pysystemtrade` GitHub backtesting 文档：系统化期货组合使用 instrument weights 和 diversification multiplier 处理多品种组合风险。链接：https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md
  - AQR `Demystifying Managed Futures`：managed futures 收益可由跨市场 time-series momentum 解释，趋势有效性来自广义市场行为和跨市场暴露，不是单个品种/年份补丁。链接：https://www.aqr.com/Insights/Research/Journal-Article/Demystifying-Managed-Futures
- 我的判断：
  - Stage019/020 已反证“入场后分钟标签削仓”和“固定出金锁盈”直接达成目标；继续微调窗口、比例、提款阈值会过拟合。
  - 同向相关/拥挤风险是更普世的组合状态，入场当时可见，理论上可能解释组合左尾；但它必须先通过只读代理证明覆盖足够大、曲线真的降回撤。
  - 本阶段只冻结一个代理规则：`corr>=0.60` 开始降权，`corr>=0.80` 降到最低 `50%`，不扫 `0.55/0.65/0.75` 或 floor 权重。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage021_same_direction_correlation_crowding_proxy.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage021_same_direction_correlation_crowding_proxy/`
- 新增参数：
  - `CORR_GATE_START=0.60`
  - `CORR_GATE_FULL=0.80`
  - `CORR_GATE_FLOOR_WEIGHT=0.50`
- 修改参数：无正式参数修改。
- 删除参数：无。
- 验证：
  - `.py311/bin/python -m py_compile research/lines/futures_trend_c9_minrisk_highquality/tools/stage021_same_direction_correlation_crowding_proxy.py` 通过。
  - `.py311/bin/python research/lines/futures_trend_c9_minrisk_highquality/tools/stage021_same_direction_correlation_crowding_proxy.py` 成功生成 CSV/JSON/Markdown/PNG。

## 回测/代理参数

- 输入：
  - Stage016 closed-lot 特征：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage016_intersection_stability_audit/qmt_roll_stage016_c9_minrisk_intersection_stability_audit_features_stage016_intersection_stability_audit_v1.csv`
  - Stage019 官方 A 日度曲线：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage019_no_follow_light_shave_true_engine/qmt_roll_stage019_c9_minrisk_no_follow_light_shave_true_engine_curve_stage019_no_follow_light_shave_true_engine_v1.csv`
  - Stage019 官方 summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage019_no_follow_light_shave_true_engine/qmt_roll_stage019_c9_minrisk_no_follow_light_shave_true_engine_summary_stage019_no_follow_light_shave_true_engine_v1.csv`
- A：当前官方 C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- C：同向相关拥挤 daily active-risk proxy：
  - closed-lot 入场时若 `same_direction_correlation_active_count >= 1` 且 `same_direction_correlation_max_corr > 0.60`，标记为同向相关拥挤风险。
  - `0.60 -> 0.80` 之间线性把该 active lot 风险权重从 `1.0` 降到 `0.5`，`>=0.80` 最低 `0.5`。
  - 每个交易日按 active lot 的 `risk_base` 加权得到全账户日度 `risk_weight`，再对官方日度 `net_pnl/slippage/broker10_margin` 做 proxy 缩放。
- 口径限制：
  - 这是日度 active-risk proxy，不是整数手重算，不生成真实订单。
  - 胜率和交易次数只沿用官方参考。
  - 因为本阶段不是分钟 K 进出场规则，没有生成分钟 atlas；已生成资金曲线、回撤、broker10、权重/覆盖和 closed-lot 贡献图。

## 结果

| 版本 | 期末权益 | 总收益 | 收益保留 | 最大回撤 | 回撤改善 | Sharpe | 总滑点/代理滑点 | 总交易次数参考 | 胜率参考 | broker10峰值 | over100天数 | 日权重<1天数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A 官方 C9/15w | `39,176,437.60` | `26017.6251%` | `100.0000%` | `-45.0827%` | `0.0000pp` | `1.6339` | `2,730,130.00` | `787` | `53.2560%` | `111.7365%` | `5` | `0` |
| C 同向相关拥挤代理 | `38,871,697.61` | `25814.4651%` | `99.2191%` | `-46.2563%` | `-1.1736pp` | `1.6138` | `2,725,117.27` | `787` | `53.2560%` | `111.7157%` | `6` | `76` |

- closed-lot 归因：
  - 全样本 `399` 笔，净 PnL `43,054,612.60`。
  - `corr_gate_applied_060_080_floor50` 只有 `21` 笔、`9` 产品、`6` 年，净 PnL `57,020.60`。
  - 该组正收益覆盖仅 `0.6231%`，负收益覆盖 `1.4855%`，`1` 个正收益年份、`5` 个负收益年份。
  - 更严格的 `corr_ge_075_active_ge1` 为 `12` 笔、`4` 产品、`5` 年，净 PnL `-93,601.10`，`0` 个正收益年份。
- 日度权重：
  - 总交易日 `2048`，权重低于 `1` 的日期 `76` 天。
  - 平均日权重 `0.9973`，最低日权重 `0.5031`。
  - 平均同向相关拥挤 active-risk 占比仅 `1.0772%`，最大占比可接近 `100%` 但很稀疏。

## 视觉输出

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage021_same_direction_correlation_crowding_proxy/qmt_roll_stage021_c9_minrisk_same_direction_correlation_crowding_proxy_report_stage021_same_direction_correlation_crowding_proxy_v1.md`
- metrics：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage021_same_direction_correlation_crowding_proxy/qmt_roll_stage021_c9_minrisk_same_direction_correlation_crowding_proxy_metrics_stage021_same_direction_correlation_crowding_proxy_v1.csv`
- closed-lot attribution：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage021_same_direction_correlation_crowding_proxy/qmt_roll_stage021_c9_minrisk_same_direction_correlation_crowding_proxy_closed_lot_attribution_stage021_same_direction_correlation_crowding_proxy_v1.csv`
- daily weights：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage021_same_direction_correlation_crowding_proxy/qmt_roll_stage021_c9_minrisk_same_direction_correlation_crowding_proxy_daily_weights_stage021_same_direction_correlation_crowding_proxy_v1.csv`
- curves：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage021_same_direction_correlation_crowding_proxy/qmt_roll_stage021_c9_minrisk_same_direction_correlation_crowding_proxy_curves_stage021_same_direction_correlation_crowding_proxy_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage021_same_direction_correlation_crowding_proxy/qmt_roll_stage021_c9_minrisk_same_direction_correlation_crowding_proxy_path_drawdown_chart_stage021_same_direction_correlation_crowding_proxy_v1.png`
- daily weight chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage021_same_direction_correlation_crowding_proxy/qmt_roll_stage021_c9_minrisk_same_direction_correlation_crowding_proxy_daily_weight_share_chart_stage021_same_direction_correlation_crowding_proxy_v1.png`
- contribution chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage021_same_direction_correlation_crowding_proxy/qmt_roll_stage021_c9_minrisk_same_direction_correlation_crowding_proxy_closed_lot_contribution_chart_stage021_same_direction_correlation_crowding_proxy_v1.png`
- scatter：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage021_same_direction_correlation_crowding_proxy/qmt_roll_stage021_c9_minrisk_same_direction_correlation_crowding_proxy_corr_pnl_scatter_stage021_same_direction_correlation_crowding_proxy_v1.png`
- yearly heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage021_same_direction_correlation_crowding_proxy/qmt_roll_stage021_c9_minrisk_same_direction_correlation_crowding_proxy_year_return_heatmap_stage021_same_direction_correlation_crowding_proxy_v1.png`

## 视觉结论

- path chart 中红蓝权益线几乎重合，说明该代理不破坏大部分右尾；但 `2022` 回撤谷红线略深，最大回撤从官方 `-45.0827%` 恶化到 `-46.2563%`，没有完成降回撤目标。
- broker10 子图中 C 的峰值只微降 `0.0208pp`，且 `days_over_100pct` 从 `5` 增至 `6`，组合拥挤降权没有实际解决保证金尖峰。
- daily weight/share 图显示权重触发稀疏：多数时间权重为 `1`，只有少数日期明显降权；这解释了收益保留高但回撤不能系统性改善。
- closed-lot contribution 图显示红色 `corr_gate_applied` 贡献曲线贴近 `0`，官方主要右尾来自未触发相关拥挤的绿线；该状态不是 C9 收益和回撤主干。
- scatter 图显示高相关样本偏负但样本很少，不能作为真引擎候选；按阈值继续加宽只会变成参数救援。

## 结论

- 本阶段结论：`stage021_corr_crowding_proxy_no_candidate_insufficient_explanatory_power`。
- 是否进入下一步：不进入真实引擎，不接正式版，不触发 A/B。
- 是否更新本线 `LINE.md`：是，追加 Stage021 结论和下一步边界。
- 是否更新 `research/registry.md`：否，并行研究线日常不更新 registry。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、正式候选或跨线合入。
- 不修改当前 official live config，不连接 CTP，不调用订单 API。

## 删除/修改的假设

- 删除假设：同向相关/拥挤状态是当前 C9/15w 最大回撤的主解释变量，固定低自由度相关风险代理可以明显降回撤且保留 `80%+` 收益。
- 新增结果：该状态入场可见、逻辑普世，但覆盖面太小，代理最大回撤反而恶化 `1.1736pp`；它只能保留为风险解释标签，不值得进真引擎。

## 过拟合反思

- 运行前判断：否。规则来自系统化期货组合风险理论中的相关性/拥挤风险，不按坏年份、品种、方向或月份反推。
- 运行后判断：否，本次只测一个预声明代理；但如果继续扫 `0.55/0.65/0.75/0.85`、floor 权重、按品种或年份扩大覆盖，就是过拟合。

## 继续价值反思

- 运行前判断：有。Stage019/020 后需要从真正外生的组合状态找解释，而不是继续分钟削仓或出金参数。
- 运行后判断：该相关拥挤风险代理没有候选价值；整条目标仍有价值，但下一步应换更贴近“预先可见系统风险”的低自由度状态，例如波动/保证金压力的入场前预判、多起点固定规则审计，或先做当前 `2022` 回撤段的只读归因而不写规则。

## 后续规划和 TODO

- 停止 Stage021 的相关阈值/权重参数救援，不做 `0.55/0.65/0.75/0.85`、floor 权重、品种、方向、年份、月份筛选。
- 同向相关/拥挤只保留为风险解释标签，可用于后续报告观察，不进入真引擎。
- 下一步若继续本目标，优先做只读归因：把 Stage021 未命中的 `2022` 主回撤段、broker10 尖峰日、官方 active lots 的入场前波动/保证金/权益分母状态合并到一张路径图，先确认是否存在更强的可预见系统风险源。
