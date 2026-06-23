# Stage084 固定资本结构多起点边界审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 11:03 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读账户层多起点边界审计 / 不是真实撮合引擎 / 不生成交易规则
- 是否重要突破：否，属于边界关闭版本，不是收益突破或正式候选
- 是否触发A/B：否，`candidate_ready_count=0`

## 外部调研与判断

- 参考资料：
  - Market Simulation under Adverse Selection：`https://arxiv.org/html/2409.12721v2`
  - Moskowitz/Ooi/Pedersen Time Series Momentum：`https://elmwealth.com/wp-content/uploads/2017/06/timeseriesmomentum.pdf`
  - CME/Baltas/Kosowski Demystifying Time-Series Momentum：`https://www.cmegroup.com/education/files/demystifiing-time-series-momentum-strategies.pdf`
  - Rob Carver Vol Targeting and Trend Following：`https://qoppac.blogspot.com/2018/07/vol-targeting-and-trend-following.html`
  - vn.py CTA strategy engine：`https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/engine.py`
- 我的判断：
  - 趋势跟随的收益核心来自跨资产右尾趋势延续；任何固定账户层保险如果长期降风险，必须付出复利右尾代价。
  - Stage083 已反证滞后波动闸门；Stage017/020 已反证单起点 CPPI/TIPP 和出金锁盈。本阶段只做多起点边界复核，不扫参数。
  - 结果显示账户层固定结构依然是收益-回撤 trade-off，不是“高质量信号最小风险参与”的答案。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage084_fixed_capital_multistart_boundary_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；固定复用 `fixed80`、`cppi80_m4`、`tipp50_m4`、`balanced_tranche_v1` 四个账户层 archetype；新增多起点审计口径 `monthly_start_count=102`、`mature_start_count=90`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-02` 至 `2026-06-15`
- 账户规模：`150000`
- 成本口径：复用 Stage010 官方日度资金曲线、slippage 和 broker10 proxy；本阶段用官方日收益流重置月度起点，不重跑整数手撮合。
- 样本过滤：`102` 个自然月首个交易日起点；成熟窗口要求 `>=252` 个交易日，成熟起点 `90` 个。
- 策略/归因口径：
  - A：`A_official_return_stream`，官方 C9/15w 日收益流月度重置。
  - C1：`C_fixed80_cash_reserve_return_stream`，固定 `80%` 风险暴露 + `20%` 现金。
  - C2：`C_cppi80_initial_floor_m4_return_stream`，初始本金 `80%` floor，multiplier `4`。
  - C3：`C_tipp50_hwm_floor_m4_return_stream`，高水位 `50%` floor，multiplier `4`。
  - C4：`C_balanced_tranche_v1_return_stream`，复用 Stage020 既有 `balanced_tranche_v1`，不改提款阈值或比例。

## 结果

- 期末权益：官方代表性全周期 `39,176,437.60`
- 总收益：官方代表性全周期 `26017.6251%`
- 最大回撤：官方代表性全周期 `-45.0827%`
- Sharpe：官方代表性全周期 `1.6339`
- 总滑点：官方代表性全周期 proxy `2,730,130`
- 总交易次数：官方代表性全周期参考 `787`
- 胜率：本阶段不重算逐笔胜率；沿用官方参考 `53.2560%`
- 其他关键指标：
  - `monthly_start_count=102`
  - `mature_start_count=90`
  - `candidate_variant_count=4`
  - `candidate_ready_count=0`
  - `total_candidate_window_pass_count=77`
  - `total_significant_dd_window_pass_count=3`
  - `best_median_dd_variant=C_fixed80_cash_reserve_return_stream`
  - `best_median_dd_improvement_pp=7.6114`
  - `best_median_return_retention_pct=62.2918`
  - `C_fixed80`：成熟窗口 `90`，pass `0`，中位收益保留 `62.2918%`，中位回撤改善 `+7.6114pp`。
  - `C_tipp50`：成熟窗口 `90`，pass `51`，significant pass `0`，中位收益保留 `83.0106%`，中位回撤改善 `+0.9796pp`。
  - `C_cppi80`：成熟窗口 `90`，pass `26`，significant pass `3`，中位收益保留 `92.3430%`，中位回撤改善 `0.0000pp`；有效窗口集中在少数 2022 后起点。
  - `C_balanced_tranche_v1`：成熟窗口 `90`，pass `0`，中位收益保留 `100.0000%` 但中位回撤改善 `0.0000pp`；改善集中在早期高利润起点，非普世。

## 视觉分析

- path/drawdown/weight 图：
  - `fixed80` 明显压低权益曲线，虽然回撤曲线较浅，但代价是复利右尾长期少一截。
  - `balanced_tranche_v1` 在 `2022` 后风险权重逐步降到约 `0.3`，总财富更平滑，但主要靠退出风险而非保留 C9 右尾。
  - `tipp50` 大部分时间贴着官方走，所以权益保留较好，但最大回撤结构几乎不变。
- monthly-start frontier scatter：
  - 大幅回撤改善点大多位于 `80%` 收益保留线左侧。
  - 位于 `80%` 收益线右侧的点多数只改善 `0-1pp`；少数 CPPI 过线点集中在特定起点，不是普世规则。
- start-year heatmap：
  - `fixed80` 跨年改善最稳定，但它用收益保留失败换来。
  - `balanced_tranche_v1` 只在 `2018-2019` 起点有明显中位改善，后期起点失效。
  - `tipp50` 各年中位改善约 `0-1pp`，不是目标级改进。
- worst-start path chart：
  - 最差官方成熟起点为 `2021-11-01`；账户结构能压浅局部回撤，但同时压低后续恢复斜率和最终权益。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage084_fixed_capital_multistart_boundary_audit/qmt_roll_stage084_c9_minrisk_fixed_capital_multistart_boundary_audit_report_stage084_fixed_capital_multistart_boundary_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage084_fixed_capital_multistart_boundary_audit/qmt_roll_stage084_c9_minrisk_fixed_capital_multistart_boundary_audit_summary_stage084_fixed_capital_multistart_boundary_audit_v1.csv`
- window stats：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage084_fixed_capital_multistart_boundary_audit/qmt_roll_stage084_c9_minrisk_fixed_capital_multistart_boundary_audit_window_stats_stage084_fixed_capital_multistart_boundary_audit_v1.csv`
- variant summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage084_fixed_capital_multistart_boundary_audit/qmt_roll_stage084_c9_minrisk_fixed_capital_multistart_boundary_audit_variant_summary_stage084_fixed_capital_multistart_boundary_audit_v1.csv`
- daily/path：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage084_fixed_capital_multistart_boundary_audit/qmt_roll_stage084_c9_minrisk_fixed_capital_multistart_boundary_audit_path_drawdown_weight_chart_stage084_fixed_capital_multistart_boundary_audit_v1.png`
- quality/frontier：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage084_fixed_capital_multistart_boundary_audit/qmt_roll_stage084_c9_minrisk_fixed_capital_multistart_boundary_audit_multistart_frontier_scatter_stage084_fixed_capital_multistart_boundary_audit_v1.png`
- heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage084_fixed_capital_multistart_boundary_audit/qmt_roll_stage084_c9_minrisk_fixed_capital_multistart_boundary_audit_start_year_heatmap_stage084_fixed_capital_multistart_boundary_audit_v1.png`
- worst-start：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage084_fixed_capital_multistart_boundary_audit/qmt_roll_stage084_c9_minrisk_fixed_capital_multistart_boundary_audit_worst_start_path_chart_stage084_fixed_capital_multistart_boundary_audit_v1.png`

## 结论

- 本阶段结论：`stage084_fixed_capital_multistart_no_candidate`
- 是否进入下一步：进入，但不沿账户层 fixed weight/floor/sweep 参数继续。
- 下一步：
  - 关闭账户层固定资本结构参数救援，不扫 fixed weight、floor、multiplier、提款阈值、提款比例、锁盈/扩张拆分或起点筛选。
  - 继续目标应回到真正点时化、入场前/入场瞬间可见的新信息源，例如授权盘口/队列/成交流、会员持仓/仓单/库存/基差细颗粒数据；没有新增数据前，不要再从历史 closed-lot 或账户曲线反推规则。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否；但继续救参会过拟合。
- 原因：
  - 本阶段只复用 Stage017/020 已存在的固定 archetype，并用所有月度起点复核，不按品种、方向、年份、亏损段或单笔结果筛选。
  - 没有新增候选、没有 A/B、没有改正式配置。
  - 若现在改 `80%`、`50%`、`m=4`、`5,000,000` 等参数去找好看的点，就是用历史路径拟合收益-回撤边界。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：账户层固定结构方向继续价值低；总目标仍有价值。
- 原因：
  - Stage084 证明固定账户结构不是“高质量信号最小风险搏最大收益”，而只是收益和回撤之间的机械交换。
  - 总目标仍未完成，但下一步价值应集中在新增点时化外生数据或授权真实微观结构数据，而不是账户层参数。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage084 结论与下一步边界。
- 是否更新 `research/registry.md`：否，本阶段不是重要突破、正式候选、路线废弃或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要合入摘要或正式候选。
