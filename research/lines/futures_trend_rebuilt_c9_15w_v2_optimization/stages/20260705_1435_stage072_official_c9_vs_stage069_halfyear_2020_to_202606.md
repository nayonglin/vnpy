# Stage072 Official C9 vs Stage069 half-year comparison

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T14:35:15
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 是否重要突破：否；这是把正式 C9 放入同一张半年对比图，不是新策略或新执行候选
- 是否触发A/B：否；只做只读对齐与绘图

## 调研与判断

- 本次本地调研确认：Stage053 已有 Official C9/15w Stage847 逐半年曲线，终点 `2026-06-30`；Stage071 已有三条 Stage069 研究分支同终点曲线。
- 我的判断：不应再重跑正式 C9；直接合并既有正式曲线和研究曲线，能避免重复口径误差。
- Stage069 的动态 stop PIT 风险仍然存在，研究分支仅作诊断；正式 C9 才是当前线上高右尾基准。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage072_official_c9_vs_stage069_halfyear_2020_to_202606.py`
- 修改正式入口：无
- 删除文件：无
- 新增参数：无
- 修改正式参数：无
- 删除参数：无

## 对比口径

- 起点：`2020-01, 2020-07, 2021-01, 2021-07, 2022-01, 2022-07, 2023-01, 2023-07, 2024-01, 2024-07, 2025-01, 2025-07, 2026-01`
- 终点：`2026-06-30`
- 资金：`150,000`
- 对比版本：Official C9/15w Stage847、Stage013 baseline、Stage069 no reentry、Stage069 daily reentry once

## 结果摘要

- Official C9：正收益 `13/13`，最小/中位/最高收益 `1.9011%/126.1993%/3886.1873%`，最差回撤 `-55.3701%`。
- Stage013 research：正收益 `10/13`，最小/中位/最高收益 `-21.5389%/23.7721%/1096.9539%`，最差回撤 `-46.6622%`。
- Stage069 no reentry：正收益 `8/13`，最小/中位/最高收益 `-25.5313%/75.2113%/951.7065%`，最差回撤 `-58.2760%`。
- Stage069 daily reentry：正收益 `7/13`，最小/中位/最高收益 `-38.6459%/11.5849%/493.9792%`，最差回撤 `-54.5606%`。

## 结论

- 决策：`stage072_official_c9_added_as_comparison_not_strategy_change`
- 原因：加入正式 C9 后可以看清：Stage013/Stage069 研究分支不是正式 C9 高收益基准，不能用它们代表线上 C9。

## 过拟合反思

- 运行前：否。只合并既有曲线，不调参数。
- 运行后：否。结果只是口径对齐，没有产生新的交易规则。

## 继续价值反思

- 运行前：有。能修正之前把 Stage013 baseline 误当正式 C9 的误解。
- 运行后：有。后续研究应以 Official C9 为对照，而不是 Stage013 research baseline。

## 输出

- summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage072_official_c9_vs_stage069_halfyear_2020_to_202606/rebuilt_c9_v2_stage072_official_c9_vs_stage069_halfyear_2020_to_202606_summary_stage072_official_c9_vs_stage069_halfyear_2020_to_202606_v1.csv`
- variant_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage072_official_c9_vs_stage069_halfyear_2020_to_202606/rebuilt_c9_v2_stage072_official_c9_vs_stage069_halfyear_2020_to_202606_variant_summary_stage072_official_c9_vs_stage069_halfyear_2020_to_202606_v1.csv`
- delta_vs_official: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage072_official_c9_vs_stage069_halfyear_2020_to_202606/rebuilt_c9_v2_stage072_official_c9_vs_stage069_halfyear_2020_to_202606_delta_vs_official_stage072_official_c9_vs_stage069_halfyear_2020_to_202606_v1.csv`
- curves: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage072_official_c9_vs_stage069_halfyear_2020_to_202606/rebuilt_c9_v2_stage072_official_c9_vs_stage069_halfyear_2020_to_202606_curves_stage072_official_c9_vs_stage069_halfyear_2020_to_202606_v1.csv.gz`
- chart_equity: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage072_official_c9_vs_stage069_halfyear_2020_to_202606/rebuilt_c9_v2_stage072_official_c9_vs_stage069_halfyear_2020_to_202606_equity_curves_stage072_official_c9_vs_stage069_halfyear_2020_to_202606_v1.png`
- chart_focus_recent: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage072_official_c9_vs_stage069_halfyear_2020_to_202606/rebuilt_c9_v2_stage072_official_c9_vs_stage069_halfyear_2020_to_202606_equity_curves_2021_07_plus_stage072_official_c9_vs_stage069_halfyear_2020_to_202606_v1.png`
- chart_return_dd: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage072_official_c9_vs_stage069_halfyear_2020_to_202606/rebuilt_c9_v2_stage072_official_c9_vs_stage069_halfyear_2020_to_202606_return_dd_stage072_official_c9_vs_stage069_halfyear_2020_to_202606_v1.png`
- chart_delta: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage072_official_c9_vs_stage069_halfyear_2020_to_202606/rebuilt_c9_v2_stage072_official_c9_vs_stage069_halfyear_2020_to_202606_delta_vs_official_stage072_official_c9_vs_stage069_halfyear_2020_to_202606_v1.png`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage072_official_c9_vs_stage069_halfyear_2020_to_202606/rebuilt_c9_v2_stage072_official_c9_vs_stage069_halfyear_2020_to_202606_report_stage072_official_c9_vs_stage069_halfyear_2020_to_202606_v1.md`
