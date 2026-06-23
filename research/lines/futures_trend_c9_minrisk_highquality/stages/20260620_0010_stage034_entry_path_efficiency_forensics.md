# Stage034 入场前 30 分钟 close-path efficiency 只读法证

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：day
- 记录时间：2026-06-20 00:10
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读分钟 close path 法证；不新增交易规则，不改正式配置，不连接 CTP，不调用订单 API。
- 是否重要突破：否。有强右尾保护线索，但不是低回撤候选。
- 是否触发A/B：否。`candidate_ready=0`，`ab_triggered=0`。

## 外部调研与判断

- 参考资料：
  - AQR/JPM `A Century of Evidence on Trend-Following Investing`：https://fairmodel.econ.yale.edu/ec439/hurst.pdf
  - `Intraday Time Series Momentum: International Evidence`：https://centaur.reading.ac.uk/95566/1/Accepted-Version.pdf
  - `A Guide to Trend Following Strategies`：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4438260
  - Opening Range Breakout 论文：https://www.econ.umu.se/ueslpnr/ues845.pdf
- 我的判断：
  - 趋势跟随长期有效的第一性来源是跨市场、跨周期的价格趋势与风险归一化，不是某一年、某品种、某窗口补丁。
  - 日内 time-series momentum 和 opening range 文献支持审计入场后首段路径是否有延续性；但本线 Stage009 已反证 opening-range 反向突破硬退出会砍掉 C9 右尾，不能照搬成规则。
  - Stage034 因此只做 close path 的方向持久性/噪声审计，不使用当根 OHLCV，不触发任何交易动作。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage034_entry_path_efficiency_forensics.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `FIRST_N_BARS=30`
  - `ATLAS_WINDOW_BARS=120`
  - `EFFICIENCY_THRESHOLD=0.50`
  - `HEAT_R=0.50`
  - `CAPITAL=150000`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage010 official C9/15w closed lots 与 Stage861 entry-day minute close path，`2018-01-01` 至 `2026-06-15`。
- 账户规模：`150,000`。
- 成本口径：沿用官方 C9/15w 基准曲线与 Stage010 成本口径；本阶段不新增交易、不重算滑点。
- 样本过滤：
  - official closed lots：`399`
  - path ready lots：`333`
  - missing/invalid path：`66`
- 策略/归因口径：
  - 每笔 lot 从入场价开始，把前 `30` 根 entry-day minute close 转成持仓方向 R。
  - `path_net_r_30m = 第30根方向R`
  - `path_gross_r_30m = 从入场到前30根 close 的绝对路径增量和`
  - `path_efficiency_30m = path_net_r_30m / path_gross_r_30m`
  - 固定只读分桶：`efficient_follow_path`、`noisy_follow_path`、`follow_but_adverse_heat_path`、`adverse_or_no_follow_path`、`missing_or_invalid_path`

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：closed-lot 胜率 `36.0902%`
- 其他关键指标：
  - path ready lots：`333`，ready ratio `83.4586%`
  - `efficient_follow_path`：`27` 笔、`11` 产品、`9` 年，净 PnL `20,060,975.00`，负收益绝对覆盖 `2.0865%`，中位 net30 `2.3382R`，中位效率 `0.5889`
  - `noisy_follow_path`：`149` 笔、`18` 产品、`9` 年，净 PnL `19,272,503.10`，负收益绝对覆盖 `42.3212%`
  - `follow_but_adverse_heat_path`：`12` 笔、`6` 产品、`7` 年，净 PnL `6,480,115.60`
  - `adverse_or_no_follow_path`：`145` 笔、`19` 产品、`9` 年，净 PnL `-6,100,118.10`，但 2024 年净 PnL `+2,163,600.00`
  - `missing_or_invalid_path`：`66` 笔，净 PnL `3,341,137.00`
  - 决策：`stage034_path_efficiency_readonly_no_trade_rule`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage034_entry_path_efficiency_forensics/qmt_roll_stage034_c9_minrisk_entry_path_efficiency_forensics_report_stage034_entry_path_efficiency_forensics_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage034_entry_path_efficiency_forensics/qmt_roll_stage034_c9_minrisk_entry_path_efficiency_forensics_summary_stage034_entry_path_efficiency_forensics_v1.csv`
- features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage034_entry_path_efficiency_forensics/qmt_roll_stage034_c9_minrisk_entry_path_efficiency_forensics_features_stage034_entry_path_efficiency_forensics_v1.csv`
- bucket stats：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage034_entry_path_efficiency_forensics/qmt_roll_stage034_c9_minrisk_entry_path_efficiency_forensics_bucket_stats_stage034_entry_path_efficiency_forensics_v1.csv`
- bucket-year matrix：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage034_entry_path_efficiency_forensics/qmt_roll_stage034_c9_minrisk_entry_path_efficiency_forensics_bucket_year_matrix_stage034_entry_path_efficiency_forensics_v1.csv`
- product-bucket matrix：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage034_entry_path_efficiency_forensics/qmt_roll_stage034_c9_minrisk_entry_path_efficiency_forensics_product_bucket_matrix_stage034_entry_path_efficiency_forensics_v1.csv`
- contribution curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage034_entry_path_efficiency_forensics/qmt_roll_stage034_c9_minrisk_entry_path_efficiency_forensics_contribution_curve_stage034_entry_path_efficiency_forensics_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage034_entry_path_efficiency_forensics/qmt_roll_stage034_c9_minrisk_entry_path_efficiency_forensics_decision_stage034_entry_path_efficiency_forensics_v1.json`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage034_entry_path_efficiency_forensics/qmt_roll_stage034_c9_minrisk_entry_path_efficiency_forensics_path_efficiency_chart_stage034_entry_path_efficiency_forensics_v1.png`
- bucket-year heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage034_entry_path_efficiency_forensics/qmt_roll_stage034_c9_minrisk_entry_path_efficiency_forensics_bucket_year_heatmap_stage034_entry_path_efficiency_forensics_v1.png`
- scatter：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage034_entry_path_efficiency_forensics/qmt_roll_stage034_c9_minrisk_entry_path_efficiency_forensics_path_efficiency_scatter_stage034_entry_path_efficiency_forensics_v1.png`
- atlas manifest：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage034_entry_path_efficiency_forensics/qmt_roll_stage034_c9_minrisk_entry_path_efficiency_forensics_atlas_manifest_stage034_entry_path_efficiency_forensics_v1.csv`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage034_entry_path_efficiency_forensics/qmt_roll_stage034_c9_minrisk_entry_path_efficiency_forensics_atlas_page001_stage034_entry_path_efficiency_forensics_v1.png` 至 `atlas_page005`

## 视觉分析

- path chart：`efficient_follow_path` 曲线从 2021 后干净上行，是强右尾保护标签；但 `noisy_follow_path` 在 2025 年出现巨大右尾台阶，不能被默认削掉；`adverse_or_no_follow_path` 长期为负但不是单调坏集合。
- bucket-year heatmap：`efficient_follow_path` 在 2021-2024 明显为正，但 2020/2026 仍小负；`noisy_follow_path` 2025 年贡献约 `1,632万`，是不能牺牲的右尾来源；`adverse_or_no_follow_path` 2024 年为正，继续反证硬退出。
- scatter：高效率且高 net30 的点偏向正收益，但中间区域正负盈亏大量混杂；效率不是独立分类器。
- atlas page001：`efficient_follow_path` 也有 `ru2605` 大亏和 `CF101/au2012` 小亏，说明“早段顺且高效率”不是充分胜率条件。
- atlas page004：`jm2509/lh2505/au2510` 前 30 分钟效率低或路径来回穿越，但最终是大赢家，直接否定把 noisy 默认最小风险。
- atlas page005：`SH405/au2412/CF205/SM505` 前 30 分钟 adverse/no-follow 后仍能修复赚钱，继续反证把 no-follow 当错误充分条件。

## 结论

- 本阶段结论：`path_efficiency_30m` 有信息含量，尤其能识别一小组强右尾保护样本；但它不是降低回撤的候选规则，因为 noisy/adverse/heat 桶仍包含大量右尾和跨年正贡献。
- 是否进入下一步：不进入候选、不进入 A/B、不接正式。
- 下一步：
  - 不得把 `efficiency >= 0.50`、`sign_flips`、`30m` 窗口或 `0.5R` heat 直接变成开仓/恢复/降仓规则。
  - 若继续分钟 close-path，只能把 Stage034 作为 right-tail protection tag，与其他入场前外生风险源做只读交叉，检验是否能减少负收益而不漏掉 `jm2509/lh2505/au2510/SH405/au2412` 这类反例。
  - 更优先的方向仍是入场前可见、覆盖完整、非最终盈亏标签的外生风险源；没有新增外生信息时，不继续围绕 30m close path 扫参。

## 过拟合反思

- 运行前判断：不做交易规则时不过拟合；如果把固定效率阈值直接用于降仓/恢复，会有明显过拟合风险。
- 运行后判断：否，本阶段本身不过拟合；但继续救参会过拟合。
- 原因：本阶段只做固定口径的只读分桶、贡献曲线和 atlas；结果没有被用于调阈值或生成候选。视觉反例已证明不能从该特征直接推出规则。

## 继续价值反思

- 运行前判断：有价值，因为 Stage033 后仍需要寻找不依赖当根 OHLCV 的分钟级可见结构。
- 运行后判断：有保留价值，但不值得沿本分支单独深挖参数。
- 原因：它能识别右尾保护样本，但不能单独降低回撤并保留 80% 收益；后续只能作为辅助标签，与真正入场前外生风险源交叉审计。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage034 结论和下一步边界。
- 是否更新 `research/registry.md`：否，本阶段非路线合入/废弃/正式候选。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段没有正式候选、重要突破或跨线合并。
