# Stage059 正式版 vs Stage058 净值缺陷对比

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T15:48:05
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读可视化；不重跑策略、不改参数、不连接 CTP、不调用订单 API
- 是否重要突破：否
- 是否触发A/B：否；复用既有正式版与 Stage058 曲线

## 外部调研与判断

- 参考资料：pysystemtrade/backtesting、underwater graph/drawdown analysis、drawdown definition。
- 我的判断：用户需要看的不是绝对收益曲线堆叠，而是同日起点、同日期下研究版相对正式版的净值缺口和 underwater 缺陷。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage059_official_vs_stage058_net_defect_compare.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；新增可视化口径 `Stage058 NAV / Official NAV - 1`、`drawdown_gap_pp`、`lag_day_ratio`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：复用 Stage053 与 Stage058 既有曲线，终点 `2026-06-30`
- 账户规模：两者均按各自曲线首日净值归一化，初始 NAV=1
- 成本口径：不重算，沿用原曲线成本
- 样本过滤：逐半年起点 `2018-01` 到 `2026-01`
- 策略/归因口径：只读比较正式版与 Stage058 的净值相对缺口、回撤缺口和落后天数比例

## 结果

- 终点缺口最差起点：`2023-01`，终点相对缺口 `-18.8057%`
- 历史最深相对落后起点：`2023-01`，最深相对缺口 `-33.2690%`，发生日 `2025-11-20`
- 研究版低于正式版天数比例最高：`2023-01`
- 期末权益/总收益/Sharpe/交易次数：本阶段不重跑回测，详见 Stage058 和 Stage053 原始 summary。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage059_official_vs_stage058_net_defect_compare/rebuilt_c9_v2_stage059_official_vs_stage058_net_defect_compare_report_stage059_official_vs_stage058_net_defect_compare_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage059_official_vs_stage058_net_defect_compare/rebuilt_c9_v2_stage059_official_vs_stage058_net_defect_compare_start_defect_summary_stage059_official_vs_stage058_net_defect_compare_v1.csv`
- daily：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage059_official_vs_stage058_net_defect_compare/rebuilt_c9_v2_stage059_official_vs_stage058_net_defect_compare_pair_curves_stage059_official_vs_stage058_net_defect_compare_v1.csv`
- chart_relative_gap：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage059_official_vs_stage058_net_defect_compare/rebuilt_c9_v2_stage059_official_vs_stage058_net_defect_compare_relative_gap_grid_stage059_official_vs_stage058_net_defect_compare_v1.png`
- chart_deficit_only：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage059_official_vs_stage058_net_defect_compare/rebuilt_c9_v2_stage059_official_vs_stage058_net_defect_compare_deficit_only_grid_stage059_official_vs_stage058_net_defect_compare_v1.png`
- chart_focus：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage059_official_vs_stage058_net_defect_compare/rebuilt_c9_v2_stage059_official_vs_stage058_net_defect_compare_nav_drawdown_focus_stage059_official_vs_stage058_net_defect_compare_v1.png`
- chart_bars：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage059_official_vs_stage058_net_defect_compare/rebuilt_c9_v2_stage059_official_vs_stage058_net_defect_compare_defect_bar_summary_stage059_official_vs_stage058_net_defect_compare_v1.png`

## 结论

- 本阶段结论：Stage058 的缺陷主要体现在部分起点的相对净值落后、回撤缺口和落后天数，而不是简单的整体收益低。
- 是否进入下一步：否；这是解释图，不改变 Stage058 不晋级判断。
- 下一步：若继续研究，应换新 PIT 源或账户外层，不围绕 Stage058 的 OI 阈值/AI topN/权重救参。

## 过拟合反思

- 运行前判断：否；只读比较既有曲线，不写交易规则。
- 运行后判断：否；没有新增策略参数。
- 原因：这是诊断可视化，不改变历史结果。

## 继续价值反思

- 运行前判断：有；用户明确看不懂原图，需要解释 Stage058 为什么不晋级。
- 运行后判断：有但仅限展示；图已解释缺陷，不支持继续救参。
- 原因：可视化能帮助决策，但不能替代新证据。
