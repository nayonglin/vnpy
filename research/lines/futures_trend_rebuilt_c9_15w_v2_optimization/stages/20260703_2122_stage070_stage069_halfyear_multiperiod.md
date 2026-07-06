# Stage070 Stage069 half-year multiperiod view

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-03T21:22:02
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 是否重要突破：否；这是 Stage069 三臂半年起点视图，不是新 alpha 或新执行候选
- 是否触发A/B：否；结论仍是不晋级

## 外部调研与判断

- Backtrader/CME stop-order 资料支持触发价与成交价分离；本阶段不新增成交假设，只复用 Stage069 结果筛半年起点。
- 独立审计已指出 Stage069 base/layer 动态保护线存在当日日K后验口径风险；本阶段仅作诊断图表。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage070_stage069_halfyear_multiperiod.py`
- 修改正式入口：无
- 删除文件：无
- 新增参数：无；半年起点只是 Stage069 逐月结果的精确子集
- 修改正式参数：无
- 删除参数：无

## 回测参数

- 起点：`2021-07, 2022-01, 2022-07, 2023-01, 2023-07, 2024-01, 2024-07, 2025-01, 2025-07, 2026-01`
- 终点：`2026-07-02`
- 资金：`150,000`
- 对照臂：A Stage013 baseline；C1 全周期动态保护线分钟止损不重进；C2 全周期动态保护线分钟止损、每天最多一次重进

## 结果摘要

- A baseline：正收益 `7/10`，最小/中位收益 `-19.8589%/11.7706%`，最差回撤 `-46.6622%`，最长水下 `891` 天。
- C1 no reentry：正收益 `5/10`，最小/中位收益 `-25.4113%/35.2543%`，最差回撤 `-58.2760%`，最长水下 `390` 天。
- C2 daily reentry：正收益 `4/10`，最小/中位收益 `-38.5259%/-18.4105%`，最差回撤 `-54.5606%`，最长水下 `520` 天。

## 统计口径 Review

- 本阶段没有重跑策略逻辑，直接使用 Stage069 逐月结果中的 Jan/Jul 起点，避免引入新口径。
- 曲线完整性按 `version/requested_start_month` 审计，要求每臂 `10` 个起点且终点一致。
- Stage069 的动态 stop PIT 风险仍然存在，因此图表只用于比较，不用于晋级。

## 结论

- 决策：`stage070_halfyear_view_confirms_stage069_not_promoted`
- 原因：半年视图没有推翻 Stage069 结论；C1 是局部改善但左尾/回撤更差，C2 仍明显不合格。

## 后续规划和 TODO

- 不继续同日重进形状。
- 若继续研究日内止损，应新开 PIT-correct 版本：分钟级顺序更新，或只使用开盘前已知保护线。

## 过拟合反思

- 运行前：否。半年起点是预声明可读视图，不新增筛选阈值或救参。
- 运行后：否。结果来自完整 Stage069 逐月回测子集，没有按收益挑月份。

## 继续价值反思

- 运行前：有。半年视图更容易看清真实冷启动路径。
- 运行后：有，但价值是确认不晋级和指导下一步做 PIT-correct 慢确认/资金层，而不是继续当前 Stage069。

## 输出

- summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage070_stage069_halfyear_multiperiod/rebuilt_c9_v2_stage070_stage069_halfyear_multiperiod_summary_stage070_stage069_halfyear_multiperiod_v1.csv`
- variant_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage070_stage069_halfyear_multiperiod/rebuilt_c9_v2_stage070_stage069_halfyear_multiperiod_variant_summary_stage070_stage069_halfyear_multiperiod_v1.csv`
- delta_vs_baseline: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage070_stage069_halfyear_multiperiod/rebuilt_c9_v2_stage070_stage069_halfyear_multiperiod_delta_vs_baseline_stage070_stage069_halfyear_multiperiod_v1.csv`
- curves: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage070_stage069_halfyear_multiperiod/rebuilt_c9_v2_stage070_stage069_halfyear_multiperiod_curves_stage070_stage069_halfyear_multiperiod_v1.csv.gz`
- chart_return_dd: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage070_stage069_halfyear_multiperiod/rebuilt_c9_v2_stage070_stage069_halfyear_multiperiod_return_dd_stage070_stage069_halfyear_multiperiod_v1.png`
- chart_equity: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage070_stage069_halfyear_multiperiod/rebuilt_c9_v2_stage070_stage069_halfyear_multiperiod_equity_curves_stage070_stage069_halfyear_multiperiod_v1.png`
- chart_delta: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage070_stage069_halfyear_multiperiod/rebuilt_c9_v2_stage070_stage069_halfyear_multiperiod_delta_vs_baseline_stage070_stage069_halfyear_multiperiod_v1.png`
- chart_underwater: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage070_stage069_halfyear_multiperiod/rebuilt_c9_v2_stage070_stage069_halfyear_multiperiod_underwater_stage070_stage069_halfyear_multiperiod_v1.png`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage070_stage069_halfyear_multiperiod/rebuilt_c9_v2_stage070_stage069_halfyear_multiperiod_report_stage070_stage069_halfyear_multiperiod_v1.md`
