# Stage020 SQLite + jd 修复包 xsmom 输入重建

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 记录时间：2026-07-02 05:56 CST
- 阶段性质：数据输入重建/覆盖审计，不做收益回测，不改官方实盘。
- 决策：`stage020_xsmom_inputs_target_covered_no_gaps_ready_for_proxy`

## 调研判断

- 外部趋势跟随/横截面动量资料支持低相关收益腿方向，但本阶段只修数据覆盖，不把信号交易化。
- 本地 SQLite 日线覆盖 18 个非 jd 产品到目标终点；旧恢复线 Stage050 jd 修复包可覆盖 jd 的 2026-03-27 到 2026-06-30；剩余 jd2005/jd2006/jd2007/jd2604/jd2605 缺口用只读 TqSdk 行情补齐，只写本线输出，不改共享库。
- 仍保留 missing close 明细，避免把缺口静默当作真实 0 收益。

## 覆盖摘要

- 产品数：`19`，行数：`27121`。
- 区间：`2020-01-02 -> 2026-06-30`。
- 目标终点 `2026-06-30` 有效产品数：`19`，min_valid：`8`。
- last_date_with_min_valid_products：`2026-06-30`。
- missing_close_rows：`0`，missing_close_products：`0`，all_missing_close_dates：`0`。

## Satellite 摘要

- satellite rows：`3142`，specs：`2`，active_signal_rows：`2884`。
- satellite date range：`2020-01-02 -> 2026-06-30`。

## 输出

- product_returns：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage020_sqlite_jd_repair_xsmom_inputs/rebuilt_c9_v2_stage020_sqlite_jd_repair_xsmom_inputs_product_returns_stage020_sqlite_jd_repair_xsmom_inputs_v1.csv`
- features：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage020_sqlite_jd_repair_xsmom_inputs/rebuilt_c9_v2_stage020_sqlite_jd_repair_xsmom_inputs_features_stage020_sqlite_jd_repair_xsmom_inputs_v1.csv`
- satellite_daily：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage020_sqlite_jd_repair_xsmom_inputs/rebuilt_c9_v2_stage020_sqlite_jd_repair_xsmom_inputs_satellite_daily_stage020_sqlite_jd_repair_xsmom_inputs_v1.csv`
- missing_close_rows：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage020_sqlite_jd_repair_xsmom_inputs/rebuilt_c9_v2_stage020_sqlite_jd_repair_xsmom_inputs_missing_close_rows_stage020_sqlite_jd_repair_xsmom_inputs_v1.csv`
- source_summary：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage020_sqlite_jd_repair_xsmom_inputs/rebuilt_c9_v2_stage020_sqlite_jd_repair_xsmom_inputs_source_summary_stage020_sqlite_jd_repair_xsmom_inputs_v1.csv`
- summary：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage020_sqlite_jd_repair_xsmom_inputs/rebuilt_c9_v2_stage020_sqlite_jd_repair_xsmom_inputs_summary_stage020_sqlite_jd_repair_xsmom_inputs_v1.json`

## 过拟合反思

- 运行前判断：否。原因：只合并预先存在的数据源，不根据收益调参数。
- 运行后判断：否。原因：缺口明细被保留，没有把 missing close 静默伪装为全量有效。

## 继续价值反思

- 运行前判断：是。原因：Stage019 暴露的覆盖缺口阻止后续 proxy。
- 运行后判断：是。原因：目标终点已可覆盖且 missing close 为 0；下一步可以进入当前 C9 独立资金袖非挤占 proxy，但 Stage020 本身还不是策略候选。
