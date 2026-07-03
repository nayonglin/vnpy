# Stage019 xsmom 原始输入重建

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 记录时间：2026-07-02 05:46 CST
- 阶段性质：只重建低相关收益腿原始输入，不跑旧 C3 组合，不产生正式候选，不改实盘。
- 决策：`stage019_xsmom_raw_inputs_need_daily_backfill_keep_readonly`

## 调研判断

- 外部趋势跟随资料支持使用跨规则/横截面动量作为低相关收益源，但必须先保证本地输入可复验。
- 旧 Stage345 绑定 C3 组合日报；当前二期线只复用其产品收益与横截面动量构造，不复用旧 C3 组合评估。
- 本阶段显式把 `jd.DCE` 加入研究输入池；这不代表线上 AI 池或实盘池已经改变。

## 输入池

- 请求产品数：`19`。
- 额外加入：`jd.DCE`。

## 输出摘要

- product_returns rows：`26380`，products：`19`，名义区间：`2020-01-02 -> 2026-04-30`。
- 有效结束日（每天至少 `8` 个产品有 close）：`2025-12-15`；目标终点：`2026-06-30`。
- product_returns missing_main_close_rows：`3156`，all_missing_close_dates：`77`，nonzero_return_rows：`22550`。
- features rows：`53865`。
- satellite rows：`3064`，specs：`2`，active_signal_rows：`2806`。
- max long/short count：`3` / `3`。

## 输出文件

- product_returns：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage019_rebuild_xsmom_raw_inputs/rebuilt_c9_v2_stage019_rebuild_xsmom_raw_inputs_product_returns_stage019_rebuild_xsmom_raw_inputs_v1.csv`
- features：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage019_rebuild_xsmom_raw_inputs/rebuilt_c9_v2_stage019_rebuild_xsmom_raw_inputs_features_stage019_rebuild_xsmom_raw_inputs_v1.csv`
- satellite_daily：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage019_rebuild_xsmom_raw_inputs/rebuilt_c9_v2_stage019_rebuild_xsmom_raw_inputs_satellite_daily_stage019_rebuild_xsmom_raw_inputs_v1.csv`
- summary：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage019_rebuild_xsmom_raw_inputs/rebuilt_c9_v2_stage019_rebuild_xsmom_raw_inputs_summary_stage019_rebuild_xsmom_raw_inputs_v1.json`

## 过拟合反思

- 运行前判断：否。原因：本阶段只恢复预声明输入链，不看回测结果调参数。
- 运行后判断：否。原因：没有根据收益筛品种、日期、方向或权重；`jd.DCE` 是用户目标中的基础池扩展要求。

## 继续价值反思

- 运行前判断：是。原因：Stage018 已确认低相关腿方向有历史线索但输入缺失。
- 运行后判断：是，但若有效结束日早于目标终点，必须先补日线覆盖，不能把缺 close 的 0 收益尾部拿去做 proxy。
