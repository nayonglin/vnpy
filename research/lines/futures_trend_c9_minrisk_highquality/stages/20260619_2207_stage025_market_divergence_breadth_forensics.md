# Stage025 market divergence / breadth 入场前状态只读归因

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-19 22:07 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读法证，不是交易规则，不是撮合级真引擎
- 是否重要突破：否
- 是否触发A/B：否，本阶段 `candidate_ready=0`，不改正式配置、不连接 CTP、不调用订单 API

## 外部调研与判断

- 参考资料：
  - Hurst/Ooi/Pedersen `A Century of Evidence on Trend-Following Investing`：时间序列动量在长历史、多资产和多宏观环境中都有稳健证据，但表现受跨市场相关性环境影响；低相关环境下趋势跟随表现更好。链接：https://fairmodel.econ.yale.edu/ec439/hurst.pdf
  - Shi/Lian `Trend Following Strategies: A Practical Guide`：趋势跟随具有跨资产与中国期货市场适用性，但困难来自高相关、低趋势、杠杆敏感和短期回撤；风险管理必须接受趋势策略的不完美。链接：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5140633
  - Rob Carver `When endogenous risk management isn't enough`：趋势系统的内生风控来自波动率缩放、趋势退出和资金缩放，但有时仍需系统级 overlay；overlay 应在系统外层处理风险，不应按历史局部样本补丁化。链接：https://qoppac.blogspot.com/2020/05/when-endogenous-risk-management-isnt.html
  - `pysystemtrade` issue #141：相对价值/横截面类 raw data 应作为可复用原始数据进入系统，避免每个单品种规则里临时计算。链接：https://github.com/robcarver17/pysystemtrade/issues/141
  - Lukas Andersson `Market Divergence as a Regime Signal`：用 Market Divergence Indicator 衡量广泛期货市场趋势强度，并尝试识别 CTA 相关市场 regime；但样本外存在切换过度和识别延迟。链接：https://www.diva-portal.org/smash/get/diva2%3A1991124/FULLTEXT01.pdf
- 我的判断：
  - Stage024 已排除资金颗粒度/风险距离路线，下一步必须使用入场前可见、与最终盈亏无关的外生状态。
  - 市场趋势分散度/广度是合理的普世方向：趋势跟随依赖多市场中持续趋势的存在，而非单个品种或单个年份。
  - 但任何 market divergence 状态都只能先做只读归因；如果不能跨年、跨产品、单调地区分风险，就不能交易化。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage025_market_divergence_breadth_forensics.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage025_market_divergence_breadth_forensics/`
- 新增只读市场状态：
  - `mdi_abs_trend_60_mean`：各产品 `60` 日标准化趋势强度绝对值均值。
  - `mdi_abs_trend_60_z`：上述强度相对过去 `252` 日滚动均值/标准差的 z 分数。
  - `trend_participation_pct`：`|trend_score_60d| >= 1.0` 的产品占比。
  - `directional_balance_abs`：全市场趋势方向同向程度。
  - `cross_sectional_ret60_dispersion`：产品 `60` 日收益横截面离散度。
- 新增固定分桶：
  - `mdi_z_low/mid/high`：`mdi_abs_trend_60_z <= -0.75`、中间、`>= 0.75`。
  - `part_lt25/25_50/50_75/ge75`。
  - `dir_bal_lt20/20_40/40_70/ge70`。
  - `broad_market_state_stage025`：低分散低参与、高分散高参与、单边拥挤趋势、normal mixed、missing。
- 新增参数：无交易参数；以上为固定只读诊断边界。
- 修改参数：无正式参数修改。
- 删除参数：无。
- 验证：
  - `.py311/bin/python -m py_compile research/lines/futures_trend_c9_minrisk_highquality/tools/stage025_market_divergence_breadth_forensics.py` 通过。
  - `.py311/bin/python research/lines/futures_trend_c9_minrisk_highquality/tools/stage025_market_divergence_breadth_forensics.py` 成功生成 CSV/JSON/Markdown/PNG。

## 回测/归因参数

- 输入：
  - Stage024 features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage024_preentry_risk_granularity_forensics/qmt_roll_stage024_c9_minrisk_preentry_risk_granularity_forensics_features_stage024_preentry_risk_granularity_forensics_v1.csv`
  - Stage022 official daily state：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage022_path_risk_state_forensics/qmt_roll_stage022_c9_minrisk_path_risk_state_forensics_daily_state_stage022_path_risk_state_forensics_v1.csv`
  - Stage459/460/461-483 合成 preclose 日线 shards。
- A：当前官方 C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- 方法：
  - 按 `product-date` 汇总合成 preclose close，构造产品 `20/60` 日收益、`20` 日波动率、`60` 日标准化趋势分数。
  - 每日对产品趋势分数做横截面聚合，得到 market divergence / breadth 状态。
  - 把每笔官方 closed lot 绑定到 `prev_state_date` 的市场状态。
  - 不重跑策略、不改仓位，只做 cohort closed-lot PnL、年度矩阵、产品热图和资金曲线视觉归因。
- 覆盖限制：
  - market daily 覆盖 `2020-04-03` 至 `2026-04-30`，`1472` 日，中位产品数 `15`。
  - 官方 lots `399` 笔，其中 market state missing `129` 笔，主要包括 `2018/2019` 和滚动 z 不足期/最新缺口；不能据此声称完整全周期 market divergence 规则。

## 结果

- 官方 C9/15w 基准参考：
  - 期末权益 `39,176,437.60`
  - 总收益 `26017.6251%`
  - 最大回撤 `-45.0827%`
  - Sharpe `1.6339`
  - 总滑点 `2,730,130`
  - 总交易次数 `787`
  - 胜率参考 `53.2560%`
- all lots：
  - `399` 笔、`35` 产品、`9` 年
  - closed-lot realized PnL `43,054,612.60`
- 决策：`stage025_market_divergence_no_candidate_nonmonotonic_or_incomplete`
- `market_state_missing`：
  - `129` 笔、`28` 产品、`4` 年
  - 净 PnL `694,772.90`
- `mdi_z_low`：
  - `59` 笔、`22` 产品、`7` 年
  - 净 PnL `3,104,791.90`
  - 正收益年份 `6`、负收益年份 `1`
  - 不是坏状态。
- `mdi_z_mid`：
  - `164` 笔、`32` 产品、`7` 年
  - 净 PnL `36,848,482.10`
  - 正收益覆盖 `76.8167%`，负收益覆盖 `61.4040%`
  - 官方右尾主要落在 normal/mid divergence，不应削。
- `mdi_z_high`：
  - `47` 笔、`17` 产品、`6` 年
  - 净 PnL `2,406,565.70`
  - 正收益年份 `3`、负收益年份 `3`
  - 非单调，也不是坏状态。
- `participation_lt25`：
  - `51` 笔、`22` 产品、`7` 年
  - 净 PnL `1,389,974.30`
- `participation_ge50`：
  - `76` 笔、`26` 产品、`6` 年
  - 净 PnL `7,184,812.40`
  - 正收益年份 `2`、负收益年份 `4`，但整体为正且不适合做机械削仓。
- `one_sided_crowded_trend`：
  - `40` 笔、`21` 产品、`6` 年
  - 净 PnL `4,662,038.00`
  - 正收益年份 `4`、负收益年份 `2`
  - 单边拥挤不是坏状态；它也承载趋势右尾。

## 视觉输出

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage025_market_divergence_breadth_forensics/qmt_roll_stage025_c9_minrisk_market_divergence_breadth_forensics_report_stage025_market_divergence_breadth_forensics_v1.md`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage025_market_divergence_breadth_forensics/qmt_roll_stage025_c9_minrisk_market_divergence_breadth_forensics_decision_stage025_market_divergence_breadth_forensics_v1.json`
- market state daily：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage025_market_divergence_breadth_forensics/qmt_roll_stage025_c9_minrisk_market_divergence_breadth_forensics_market_state_daily_stage025_market_divergence_breadth_forensics_v1.csv`
- features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage025_market_divergence_breadth_forensics/qmt_roll_stage025_c9_minrisk_market_divergence_breadth_forensics_features_stage025_market_divergence_breadth_forensics_v1.csv`
- bucket summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage025_market_divergence_breadth_forensics/qmt_roll_stage025_c9_minrisk_market_divergence_breadth_forensics_bucket_summary_stage025_market_divergence_breadth_forensics_v1.csv`
- bucket-year matrix：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage025_market_divergence_breadth_forensics/qmt_roll_stage025_c9_minrisk_market_divergence_breadth_forensics_bucket_year_matrix_stage025_market_divergence_breadth_forensics_v1.csv`
- cohort summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage025_market_divergence_breadth_forensics/qmt_roll_stage025_c9_minrisk_market_divergence_breadth_forensics_cohort_summary_stage025_market_divergence_breadth_forensics_v1.csv`
- state path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage025_market_divergence_breadth_forensics/qmt_roll_stage025_c9_minrisk_market_divergence_breadth_forensics_market_state_path_chart_stage025_market_divergence_breadth_forensics_v1.png`
- cohort contribution chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage025_market_divergence_breadth_forensics/qmt_roll_stage025_c9_minrisk_market_divergence_breadth_forensics_cohort_contribution_chart_stage025_market_divergence_breadth_forensics_v1.png`
- bucket-year heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage025_market_divergence_breadth_forensics/qmt_roll_stage025_c9_minrisk_market_divergence_breadth_forensics_bucket_year_heatmap_stage025_market_divergence_breadth_forensics_v1.png`
- state scatter：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage025_market_divergence_breadth_forensics/qmt_roll_stage025_c9_minrisk_market_divergence_breadth_forensics_state_scatter_stage025_market_divergence_breadth_forensics_v1.png`
- product-state heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage025_market_divergence_breadth_forensics/qmt_roll_stage025_c9_minrisk_market_divergence_breadth_forensics_product_state_heatmap_stage025_market_divergence_breadth_forensics_v1.png`

## 视觉结论

- state path chart 显示 MDI z 与 trend participation 有明显 regime 波动，但不能干净领先官方最大回撤；`2022` 深回撤期间 MDI 既有低点也有反弹，不是稳定触发器。
- cohort contribution chart 显示 `mdi_z_mid` 才是最大右尾贡献来源，`mdi_z_low` 和 `mdi_z_high` 也最终为正；没有“低分散/高分散必削”的路径。
- bucket-year heatmap 显示 `mdi_z_high` 在 `2022` 为负、`2024` 为正，`mdi_z_low` 多数年份为正；年度非单调。
- state scatter 显示盈亏点在 MDI z 与 participation 空间高度混杂，缺少可见的干净边界。
- product-state heatmap 显示净收益仍主要来自 `jm/OI/au/fu/hc/SM` 等右尾产品块，若按产品或年度解释会走向过拟合。

## 结论

- 本阶段结论：`stage025_market_divergence_no_candidate_nonmonotonic_or_incomplete`。
- 是否进入下一步：不进入真实引擎，不接正式版，不触发 A/B。
- 是否更新本线 `LINE.md`：是，追加 Stage025 结论和下一步边界。
- 是否更新 `research/registry.md`：否，并行研究线日常不更新 registry。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、正式候选或跨线合入。
- 不修改当前 official live config，不连接 CTP，不调用订单 API。

## 删除/修改的假设

- 删除假设：低市场分散度 / 低趋势参与度可以作为普世削仓状态。
- 删除假设：高市场分散度 / 单边拥挤趋势可以作为普世削仓状态。
- 保留观察：market divergence 是有解释价值的外生状态，可用于 forward watch，但不能在当前证据下交易化。

## 过拟合反思

- 运行前判断：否。市场趋势分散度来自外部 CTA 文献和入场前日线，不按 C9 最终盈亏反推。
- 运行后判断：否。本阶段没有生成候选；如果继续按 `2022` 的 `mdi_z_high` 负贡献或 `jm/OI/ru` 产品格做规则，才会变成过拟合。
- 原因：普世规则应跨年、跨品种、跨状态单调或有强第一性解释；Stage025 不满足。

## 继续价值反思

- 运行前判断：有。Stage024 后需要测试真正外生、入场前可见的状态源。
- 运行后判断：有，但不应沿当前 MDI 分桶继续扫阈值。它有解释价值，却不足以形成低回撤高保真候选。
- 原因：目标仍未达成，继续价值在于排除一类外生状态的机械削仓用法，并提示后续必须找更接近“具体信号质量”的可见信息，而不是全市场粗 regime。

## 后续规划和 TODO

- 停止 market divergence / breadth 阈值分支，不扫 MDI z、participation、directional balance、dispersion、rolling window 或产品/年份。
- 若继续外生信息源，优先找更具体且点时化的供需/期限结构/基差/持仓变化，而不是全市场粗 regime。
- 若继续分钟级目标，应回到单笔信号质量，但必须避免“先小仓观察”切断右尾；更可行的是只做右尾保护或 forward-watch，不直接削仓。
