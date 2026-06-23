# Stage052 product trend t-stat Stage496 全量 preclose 源复核

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 04:04 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage049 固定产品趋势 t-stat spec 的数据工程复核；只读，不是真实组合引擎，不是 A/B 候选，不是实盘规则。
- 是否重要突破：否。它修正了覆盖判断，但反证该固定 t-stat 交易化路线。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：
  - Baltas / Kosowski `Improving Time-Series Momentum Strategies`：用价格路径的线性趋势和统计显著性衡量 trend quality 是合理的趋势跟踪思想，但应作为固定系统规则验证，不能按结果调阈值。
  - Rob Carver / `pysystemtrade` 与 `systematictradingexamples`：趋势系统应使用连续、点时化、可复验的数据源，并在固定 forecast 形状下验证，而不是按品种/年份补丁。
  - AKShare GitHub issue `#7002`：DCE 期货接口存在 `BadZipFile` / JSON 解析类公开错误报告，提醒我们不能把“接口名存在”当成历史数据源可用。
  - SHFE/DCE/CZCE/GFEX 官方日行情、仓单/持仓排名页面：官方源存在，但各交易所格式和历史 selector 不一致，必须先做覆盖与点时化审计。
- 我的判断：
  - Stage049 的 `252` 日 t-stat 思想本身不是问题，问题之一是它只读取到 `547` 个 shard 目标点，导致 `26/399` 覆盖太低。
  - 仓库已有 Stage496 `all_required_preclose_full_bar_after_all_backfill` 数据，摘要显示 `26,380/26,380` required keys strict ready，值得在不改任何参数的前提下复核覆盖和目标 cohort。
  - 但覆盖修复后如果目标 cohort 仍是大额正贡献，就必须关闭该交易化方向；不能继续扫 `60/126/252`、`±1/±2/±3`、产品、年份或方向。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage052_product_trend_tstat_stage496_reaudit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - 仅数据源替换：从 Stage049 shard preclose 源改为 Stage496 all-required preclose full-bar 源。
  - `MAX_SIGNAL_AGE_DAYS = 7`
- 修改参数：
  - 无交易参数修改。继续固定 `TREND_WINDOW = 252`、`TREND_MIN_PERIODS = 126`、`TREND_TSTAT_CUTOFF = 2.0`。
- 删除参数：无。

## 回测/归因参数

- 数据区间：
  - 官方 C9/15w closed lots：`2018-01-15` 至 `2026-06-08`
  - Stage496 all-required preclose 源：`2020-01-02` 至 `2026-04-30`
- 账户规模：官方正式 `150,000`
- 成本口径：沿用官方 C9/15w 输出，官方总滑点 `2,730,130`
- 样本过滤：
  - official lots 全量 `399` 笔保留。
  - `2018/2019` 因 Stage496 源起始于 `2020-01-02` 保持 missing，不硬补。
  - 每笔 lot 仅使用入场前 `prev_state_date` 之前可见的 product preclose t-stat，最大信号滞后 `7` 自然日。
- 策略/归因口径：
  - 产品 log preclose 做 `252` 行线性趋势 t-stat。
  - 方向对齐 t-stat = 产品 t-stat × 官方交易方向。
  - 目标 cohort 仍为 `no_significant_aligned_trend`，即 ready 且方向对齐 t-stat `< 2.0`。
  - 乐观上限为 closed-lot cashflow 级别跳过目标 cohort，不代表真实可执行引擎。

## 结果

- 官方期末权益：`39,176,437.60`
- 官方总收益：`26017.6251%`
- 官方最大回撤：`-45.0827%`，日期 `2022-06-29`
- 官方 Sharpe：`1.6339`
- 官方总滑点：`2,730,130`
- 官方总交易次数：`787`
- 官方胜率：`53.2560%`
- 其他关键指标：
  - official lots：`399`
  - Stage049 trend-ready：`26/399 = 6.5163%`
  - Stage052 trend-ready：`269/399 = 67.4185%`
  - Stage052 ready products：`19`
  - Stage052 missing：`130` 笔，missing net PnL `+1,965,892.90`
  - 目标 `no_significant_aligned_trend`：`120` 笔、`18` 产品、`7` 年
  - 目标净 PnL：`+24,730,154.80`
  - 目标正收益：`+35,095,105.00`
  - 目标负收益绝对值：`10,364,950.20`
  - 目标正收益覆盖：`51.9544%`
  - 目标负收益覆盖：`42.3142%`
  - 乐观跳过目标后期末权益：`14,446,282.80`
  - 乐观跳过目标后总收益：`9530.8552%`
  - 乐观跳过目标后最大回撤：`-61.3272%`，日期仍为 `2022-06-29`
  - 乐观跳过目标后 Sharpe：`1.1489`
  - 收益保留：`36.6323%`
  - 最大回撤改善：`-16.2445pp`，即显著恶化
  - 决策：`stage052_stage496_tstat_target_right_tail_no_engine`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage052_product_trend_tstat_stage496_reaudit/qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit_report_stage052_product_trend_tstat_stage496_reaudit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage052_product_trend_tstat_stage496_reaudit/qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit_summary_stage052_product_trend_tstat_stage496_reaudit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage052_product_trend_tstat_stage496_reaudit/qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit_decision_stage052_product_trend_tstat_stage496_reaudit_v1.json`
- features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage052_product_trend_tstat_stage496_reaudit/qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit_features_stage052_product_trend_tstat_stage496_reaudit_v1.csv`
- target lots：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage052_product_trend_tstat_stage496_reaudit/qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit_target_lots_stage052_product_trend_tstat_stage496_reaudit_v1.csv`
- upper-bound curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage052_product_trend_tstat_stage496_reaudit/qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit_upper_bound_curve_stage052_product_trend_tstat_stage496_reaudit_v1.csv`
- coverage：
  - `qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit_coverage_by_year_stage052_product_trend_tstat_stage496_reaudit_v1.csv`
  - `qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit_coverage_by_product_stage052_product_trend_tstat_stage496_reaudit_v1.csv`
- quality / visuals：
  - `qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit_upper_bound_path_chart_stage052_product_trend_tstat_stage496_reaudit_v1.png`
  - `qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit_cohort_contribution_chart_stage052_product_trend_tstat_stage496_reaudit_v1.png`
  - `qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit_coverage_improvement_chart_stage052_product_trend_tstat_stage496_reaudit_v1.png`
  - `qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit_bucket_year_heatmap_stage052_product_trend_tstat_stage496_reaudit_v1.png`
  - `qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit_product_bucket_heatmap_stage052_product_trend_tstat_stage496_reaudit_v1.png`
  - `qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit_trend_tstat_scatter_stage052_product_trend_tstat_stage496_reaudit_v1.png`

## 视觉观察

- coverage improvement chart 显示 Stage496 让 `2021-2026` 大部分年份覆盖接近或达到 `100%`，但 `2018/2019` 仍为 `0`，`2020` 只有 `50%`；这说明 Stage496 是重要数据工程改进，但不是完整 `2018-2026` 产品 preclose 覆盖。
- upper-bound path chart 显示跳过 `no_significant_aligned_trend` 后，橙线从 `2022` 开始显著低于官方蓝线，最大回撤加深到 `-61.3272%`，并不是低回撤路径。
- cashflow impact 子图显示目标桶累计贡献长期为正，`2023-2025` 期间是官方右尾的重要来源。
- cohort contribution chart 显示 `opposite_significant_le_neg2` 和 `no_significant_aligned_trend` 不是坏信号集合；趋势显著同向和非显著同向都能贡献大额右尾。
- product heatmap 显示目标桶正贡献主要来自 `jm.DCE/OI.CZCE/lh.DCE/AP.CZCE/fu.SHFE` 等产品块，负贡献如 `ru.SHFE/rb.SHFE/MA.CZCE` 不足以支持产品补丁。

## 结论

- 本阶段结论：Stage496 全量 preclose 源显著修复了 Stage049 的覆盖缺陷，但固定 `252/126/+2` 产品趋势 t-stat 的交易化目标仍失败。
- 是否进入下一步：不进入 true engine，不触发 A/B，不改正式配置。
- 下一步：
  - 关闭 `no_significant_aligned_trend` 直接削仓/跳过路线；不得继续扫 `60/126/252`、min periods、`±1/±2/±3`、产品、方向、年份或月份。
  - Stage496 可作为点时化产品 preclose 数据工程资产保留；若继续趋势质量源，只允许先补 `2018-2019` 与 `2026-05` 以后覆盖，并用同一固定 spec 做 forward/只读审计。
  - 更优先的外生路线仍是新信息源或数据覆盖：会员持仓历史 selector 修复、官方仓单/库存源点时化、或完全新且入场前可见的风险状态。不能从本阶段目标桶里的亏损产品反推规则。

## 过拟合反思

- 运行前判断：否。Stage052 没有新增交易阈值，只把 Stage049 已固定的 `252/126/+2` 规则换到更完整的数据源复核。
- 运行后判断：审计本身不是过拟合；但如果继续按本阶段产品热图挑 `ru/rb/MA`、排 `jm/OI/lh`，或调 t-stat 阈值救结果，就是过拟合。
- 原因：覆盖修复后目标 cohort 变成 `120` 笔、`18` 产品、`7` 年的大额净正贡献；失败不是因为阈值差一点，而是“无显著同向趋势”并不等于坏信号。

## 继续价值反思

- 运行前判断：有价值。Stage050 要求优先做点时化外生数据覆盖，Stage049 又明确存在覆盖不足；复核 Stage496 是最小自由度的数据工程推进。
- 运行后判断：本阶段交易化路线没有继续价值；本研究总目标仍有价值。
- 原因：Stage052 把趋势 t-stat 路线从“覆盖不足不可判”推进为“覆盖显著改善后仍不是候选”。这减少了错误继续方向；后续价值应转向更独立、更直接的外生信息源，或补齐尚缺的 `2018-2019` 数据后做固定 spec forward watch。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage052 覆盖修复和反证结论。
- 是否更新 `research/registry.md`：否，非正式候选、非跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破、非正式候选、非路线废弃总账事件。
