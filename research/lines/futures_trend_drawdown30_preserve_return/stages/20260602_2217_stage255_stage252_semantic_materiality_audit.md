# Stage255 Stage252 年度白名单语义与部署材料性审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-02 22:17 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读候选审计；不重跑策略优化，不新增交易规则，不调 `TopN/risk/cap/maxpos/相关阈值`。
- 是否重要突破：是，负向突破；确认 Stage252 年度 top6 的实盘语义覆盖不完整，且部署材料性不足。
- 是否触发A/B：否。本阶段不提出新策略版本；沿用 Stage252/254 的 A/C 隔离口径，A=`stage526_r080_pc25_maxpos4`，C=`dynamic_prevtop6_r050_pc15_maxpos3`。

## 外部调研与判断

- 参考资料：
  - AQR Trend Following / managed futures 分散化框架：https://www.aqr.com/insights/trend-following
  - Rob Carver / pysystemtrade 多品种、相关性与 instrument diversification multiplier 工程框架：https://github.com/pst-group/pysystemtrade 和 https://github.com/robcarver17/pysystemtrade/blob/develop/docs/backtesting.md
- 我的判断：
  - “降低单笔风险、扩大品种池、避免高相关、年度选对部分品种”有第一性原理价值；趋势跟随天然需要多市场分散。
  - 但本地候选必须满足更硬的可执行语义：品种白名单必须在所有开仓路径上生效，且增量必须大到足以覆盖新增交易、实现复杂度和成本压力。
  - Stage252 top6 在剔除脆弱性上没有一剔就死，但 Stage255 发现它既有语义缺口，又没有足够材料性，因此不能晋级。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage555_stage252_semantic_materiality_audit.py`
- 修改脚本：无正式策略默认逻辑修改；审计脚本重跑前修正了 carry 统计口径，新增非白名单新开/加仓明细输出。
- 删除脚本：无。
- 新增参数：无交易参数；新增审计闸门：
  - `return_relative_vs_stage526_pct >= 100.5`
  - `total_return_improvement_pp >= 18.5`
  - `max_dd_improvement_pp >= 0.5`
  - `ulcer_improvement_pp >= 0.25`
  - `holding63/126_p05_improvement_pp >= 0.5`
  - `3x cost max_dd_pct >= -40`
  - `added_trade_count <= 150 or materiality strong`
  - `satellite_pnl_per_added_trade >= 500`
  - `slippage_to_satellite_pnl_pct <= 10`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage552/254 输出的 `2020-01-02` 至 `2026-04-17`。
- 账户规模：Stage526 主账户口径；Stage252 为 Stage526 核心不替换 + `11.5万` 非核心年度 top6 sleeve。
- 成本口径：沿用 Stage552 正常成本、2x/3x 成本压力表；本阶段只读。
- 样本过滤：只审计 `dynamic_prevtop6_r050_pc15_maxpos3`。
- 策略/归因口径：
  - 语义审计：年度 eligibility 是否只用上一年，selection 是否只用上一年，2021 前是否无卫星持仓，非当年白名单产品是否出现产品级新开/加仓。
  - 材料性审计：收益增量、回撤改善、Ulcer 改善、63/126日左尾改善、3x成本 DD40、新增交易数、单位新增交易贡献和成本占比。

## 结果

- A Stage526：
  - 期末权益：`23,369,505`
  - 总收益：`3699.9195%`
  - 最大回撤：`-36.2670%`
  - Sharpe：`1.6385`
  - Ulcer：`14.4691`
  - 总滑点：`1,342,190`
  - 总交易次数：`905`
  - 胜率：非零日胜率 `53.6330%`
- C Stage252 top6：
  - 期末权益：`23,422,160`
  - 总收益：`3708.4813%`
  - 相对 Stage526：`100.2314%`
  - 最大回撤：`-36.0822%`
  - Sharpe：`1.6432`
  - Ulcer：`14.3839`
  - 总滑点：`1,346,350`
  - 总交易次数：`1,105`
  - 胜率：非零日胜率 `53.7130%`
  - 卫星PnL：`52,655`
- 语义结果：
  - `eligibility_uses_previous_year`：通过，违规 `0`。
  - `selection_uses_previous_year`：通过，违规 `0`。
  - `pre_2021_no_active_satellite_position`：通过，违规 `0`。
  - `no_noneligible_product_open_or_add`：失败，违规 `1`。
  - `carryover_not_forced_flattened`：计数 `0`，不否决。
- 关键违规：
  - `2022-01-04`，`bu.SHFE`，`start_pos=0`、`end_pos=2`、`pos_change_abs=2`、`trade_count=1`、`net_pnl=-420`、`slippage=20`。
  - `bu.SHFE` 不在 2022 年 `dynamic_prevtop6` 白名单，2022 年白名单为 `lu.INE/al.SHFE/y.DCE/v.DCE/pg.DCE/fb.DCE`。
  - 代码复核显示 `ai_product_pool` 白名单过滤主要在 flat entry 候选计划里应用；`reverse_entry`、`regular_add/donchian_add`、`rollover_reopen` 等路径未等价覆盖年度白名单。Stage252 的“当年只允许 top6 新开/加仓”语义不完整。
- 材料性结果：
  - `return_relative_vs_stage526_pct=100.2314`，未达 `100.5`。
  - `total_return_improvement_pp=8.5618`，未达 `18.5`。
  - `max_dd_improvement_pp=0.1848`，未达 `0.5`。
  - `ulcer_improvement_pp=0.0852`，未达 `0.25`。
  - `holding63_p05_improvement_pp=0.2678`，未达 `0.5`。
  - `holding126_p05_improvement_pp=0.2852`，未达 `0.5`。
  - `cost3_dd40_pass=-41.8410`，未达 `>=-40`。
  - `added_trade_count=200`，未通过。
  - `satellite_pnl_per_added_trade=263.275`，未达 `500`。
  - `slippage_to_satellite_pnl_pct=7.9005`，通过，但不能抵消其他核心项失败。
- 视觉复盘：
  - 权益差曲线总体为正，但到 2025-2026 只剩约 `5.3万` 级别，主账户曲线肉眼仍几乎重合。
  - 年度白名单柱状图只有 2022 年出现 `1` 次红色非白名单新开/加仓，carry 为 `0`。
  - 材料性柱状图核心项全部红色，说明体验提升和收益增量都不具备部署幅度。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage555_stage252_semantic_materiality_audit_report_stage555_stage252_semantic_materiality_audit_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage555_stage252_semantic_materiality_audit_decision_stage555_stage252_semantic_materiality_audit_v1.json`
- semantic audit：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage555_stage252_semantic_materiality_audit_semantic_audit_stage555_stage252_semantic_materiality_audit_v1.csv`
- annual boundary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage555_stage252_semantic_materiality_audit_annual_boundary_stage555_stage252_semantic_materiality_audit_v1.csv`
- semantic violations：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage555_stage252_semantic_materiality_audit_semantic_violations_stage555_stage252_semantic_materiality_audit_v1.csv`
- materiality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage555_stage252_semantic_materiality_audit_materiality_stage555_stage252_semantic_materiality_audit_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage555_stage252_semantic_materiality_audit_chart_stage555_stage252_semantic_materiality_audit_v1.png`
- daily：只读引用 Stage552 `combined_daily`。
- orders：无新增订单文件。
- quality：以 semantic/materiality/decision 输出替代。

## 结论

- 本阶段结论：Stage252 top6 不晋级。决策为 `semantic_effective_date_violation_and_materiality_failed_reject`。
- 是否进入下一步：Stage252 top6 不作为部署候选继续推进；只能作为 paper/经验记录。
- 下一步：
  - 不再扫 `TopN/risk/cap/family cap/相关阈值/maxpos` 小数。
  - 如果要继续年度选品，只允许做一次“修复所有开仓路径白名单闸门”的工程正确性重放；但从材料性看，即使语义修复，也大概率只能得到更小或接近噪声的增量。
  - 更有价值的方向是回到 forward 外生状态账本，积累真实接收时间戳的库存、基差、会员/资金流、舆情，再验证能否事前解释“哪一年哪些品种有趋势土壤”。

## 过拟合反思

- 运行前判断：否。Stage255 是固定候选审计，不调交易参数，不使用结果筛品种。
- 运行后判断：否。发现失败后直接降级，不删除 `bu.SHFE`、不改白名单年份、不救材料性阈值。
- 原因：这是语义和材料性审计，目的是防止把薄弱 edge 过度解释成实盘 alpha；继续为了保留 Stage252 而修小口径、删单笔或调整阈值才会过拟合。

## 继续价值反思

- 运行前判断：有价值。Stage254 只证明候选不脆弱到一剔就死，还缺实盘语义和部署幅度审计。
- 运行后判断：Stage252 子路线主动继续价值低，总目标仍有价值。
- 原因：Stage252 被语义缺口和材料性不足同时拦住；但“选对品种”方向作为第一性原理仍成立，只是应从真实外生状态/forward 账本寻找更强特征，而不是继续在年度 top6 小 edge 上调参。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新当前状态为 Stage255，明确 Stage252 top6 不晋级。
- 是否更新 `research/registry.md`：是，摘要替换 Stage254。
- 是否追加根目录 `memory.md/back_log.md`：是，本阶段属于重要负向突破，影响后续是否继续年度 top6 路线。
