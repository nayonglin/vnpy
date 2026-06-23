# Stage049 product trend t-stat pre-entry audit

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 03:18 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读前置审计，不是真实组合引擎，不是 A/B 候选，不是实盘规则。
- 是否重要突破：否。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：
  - CME / Baltas & Kosowski, `Improving Time-Series Momentum Strategies`：用过去价格路径拟合线性趋势，并以趋势统计显著性判断是否存在真实 trend，可减少噪声交易和换手。
  - `pysystemtrade` backtesting 文档：系统化趋势策略应在连续期货价格与固定规则上验证，而不是按品种/年份临时修补。
  - Rob Carver `systematictradingexamples/ewmac.py`：趋势质量应作为固定形状的系统性 forecast/信号来源，避免用最终盈亏反推局部阈值。
- 我的判断：`252` 日线性趋势 t-stat、`±2.0` 显著性阈值有第一性依据，适合做一次冻结审计；但本仓库当前可用的 completed-preclose 源覆盖太低，不能直接成为 C9 正式版的交易规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage049_product_trend_tstat_preentry_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `TREND_WINDOW = 252`
  - `TREND_MIN_PERIODS = 126`
  - `TREND_TSTAT_CUTOFF = 2.0`
  - `TARGET_COHORT = no_significant_aligned_trend`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：官方 C9/15w closed lots 全样本 `2018-2026`；产品 preclose 趋势来自本地 `qmt_roll_stage4*_completed_preclose_full*_synthetic_preclose_bars_*.csv`。
- 账户规模：官方正式 `150,000`。
- 成本口径：沿用官方 C9/15w 输出，官方总滑点 `2,730,130`。
- 样本过滤：不筛品种、不筛年份、不筛方向；仅按是否有足够 `252` 日产品 preclose 序列分为 trend-ready / trend-missing。
- 策略/归因口径：方向对齐趋势 t-stat = 产品趋势 t-stat × 官方交易方向；`direction_aligned_tstat < 2.0` 视为无显著同向趋势；乐观上限为 closed-lot cashflow 级别跳过目标 cohort，不代表真实引擎。

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
  - trend-ready lots：`26`，覆盖 `6.5163%`
  - 目标 cohort：`no_significant_aligned_trend`
  - 目标 lots：`7`，`6` 个产品，`4` 个年份
  - 目标净 PnL：`+2,620,130.00`
  - 目标正收益覆盖：`4.6900%`
  - 目标负收益覆盖：`2.2371%`
  - 乐观跳过目标 cohort 后期末权益：`36,556,307.60`
  - 乐观跳过后总收益：`24270.8717%`
  - 乐观跳过后最大回撤：`-58.4830%`，日期 `2023-03-08`
  - 乐观跳过后 Sharpe：`1.5558`
  - 最大回撤改善：`-13.4003pp`，即显著恶化
  - 收益保留：`93.2863%`
  - 排除 `2026` 后剩余 PnL：`NA`，目标 cohort 无 `2026` 样本
  - 排除最大亏损产品后剩余 PnL：`+3,004,130.00`
  - 决策：`stage049_product_trend_tstat_coverage_limited_no_engine`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage049_product_trend_tstat_preentry_audit/qmt_roll_stage049_c9_minrisk_product_trend_tstat_preentry_audit_report_stage049_product_trend_tstat_preentry_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage049_product_trend_tstat_preentry_audit/qmt_roll_stage049_c9_minrisk_product_trend_tstat_preentry_audit_summary_stage049_product_trend_tstat_preentry_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage049_product_trend_tstat_preentry_audit/qmt_roll_stage049_c9_minrisk_product_trend_tstat_preentry_audit_decision_stage049_product_trend_tstat_preentry_audit_v1.json`
- features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage049_product_trend_tstat_preentry_audit/qmt_roll_stage049_c9_minrisk_product_trend_tstat_preentry_audit_features_stage049_product_trend_tstat_preentry_audit_v1.csv`
- target lots：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage049_product_trend_tstat_preentry_audit/qmt_roll_stage049_c9_minrisk_product_trend_tstat_preentry_audit_target_lots_stage049_product_trend_tstat_preentry_audit_v1.csv`
- upper-bound curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage049_product_trend_tstat_preentry_audit/qmt_roll_stage049_c9_minrisk_product_trend_tstat_preentry_audit_upper_bound_curve_stage049_product_trend_tstat_preentry_audit_v1.csv`
- quality / visuals：
  - `qmt_roll_stage049_c9_minrisk_product_trend_tstat_preentry_audit_upper_bound_path_chart_stage049_product_trend_tstat_preentry_audit_v1.png`
  - `qmt_roll_stage049_c9_minrisk_product_trend_tstat_preentry_audit_cohort_contribution_chart_stage049_product_trend_tstat_preentry_audit_v1.png`
  - `qmt_roll_stage049_c9_minrisk_product_trend_tstat_preentry_audit_bucket_year_heatmap_stage049_product_trend_tstat_preentry_audit_v1.png`
  - `qmt_roll_stage049_c9_minrisk_product_trend_tstat_preentry_audit_product_bucket_heatmap_stage049_product_trend_tstat_preentry_audit_v1.png`
  - `qmt_roll_stage049_c9_minrisk_product_trend_tstat_preentry_audit_trend_tstat_scatter_stage049_product_trend_tstat_preentry_audit_v1.png`

## 视觉观察

- upper-bound 资金/回撤图显示，跳过无显著同向趋势 cohort 会砍掉 `2022` 右尾台阶，橙线在 `2022-2023` 低于官方，最大回撤从官方 `-45.0827%` 恶化到 `-58.4830%`。
- cohort contribution 图显示 `trend_missing` 紫线几乎解释全部收益：`373/399` 笔、净 PnL `+39,417,271.10`。trend-ready 样本只占 `6.5163%`，不是可覆盖全周期的规则基础。
- 年度热图显示可用 t-stat bucket 面积很小，主收益年份仍由 `trend_missing` 承担；scatter 中样本点很少，且目标 cohort 包含 `rb2210.SHFE` `+2,135,000` 这种大赢家。

## 结论

- 本阶段结论：`252` 日产品趋势 t-stat 是合理外部思想，但在当前 completed-preclose 数据覆盖下，不能形成 C9/15w 的低回撤候选；目标 cohort 自身净盈利，乐观跳过还会让最大回撤恶化 `13.4003pp`。
- 是否进入下一步：不进入 true engine，不触发 A/B，不改正式配置。
- 下一步：关闭当前 12m trend t-stat 直接交易化路线。若未来继续这条信息源，必须先补齐 `2018-2026` 产品 preclose 覆盖并按同一固定 spec 重跑；不能扫 `60/126/252`、min periods、t-stat 阈值、产品、年份、方向来救参。

## 过拟合反思

- 运行前判断：否。规则来自外部趋势跟踪文献，参数固定为 `252` 日、`±2.0` 显著性，不按历史亏损窗口选择。
- 运行后判断：审计本身不属于过拟合；但若把当前 `7` 笔目标 cohort 或 `26` 笔 trend-ready 样本继续拆阈值、拆产品、拆年份，就会过拟合。
- 原因：覆盖率只有 `6.5163%`，且目标 cohort 包含大额赢家，缺乏可穿越周期的单调坏信号证据。

## 继续价值反思

- 运行前判断：有价值。线性趋势显著性是普世趋势跟踪思想，值得作为入场前质量源做一次冻结审计。
- 运行后判断：当前数据源下直接交易化价值不足；更广义目标仍有价值。
- 原因：本阶段证明问题不是阈值没调好，而是数据覆盖和解释力不足。继续推进应转向覆盖完整、入场前可见、与最终盈亏无关的信息源，或先做产品 preclose 数据工程。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage049 关闭结论和后续边界。
- 是否更新 `research/registry.md`：否，非重要突破、非正式候选、非路线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破、非正式候选、非路线废弃总账事件。
