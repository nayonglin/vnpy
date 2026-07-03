# Stage023 Stage022 剩余负窗口归因

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T06:24:37
- 阶段性质：只读归因；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否；本阶段不是候选规则，只判断 Stage022 改善剩余失败来自哪里

## 外部调研与判断

- 参考：pyfolio drawdown/underwater period 归因、pysystemtrade capital correction / risk exposure 思路、趋势跟随 drawdown 文献。
- 我的判断：Stage022 已经证明 xsmom 入场确认有增量，但目标仍失败；继续优化前必须先拆剩余负窗口，确认是 base 趋势持仓亏损、加风险 proxy 拖累，还是二者共同导致。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage023_stage022_residual_window_attribution.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage023_stage022_residual_window_attribution.py`
- 新增参数：`TARGET_VARIANT=stage022_stage013_guarded_quality_xsmom12_not_opposed`、`TOP_N_FOCUS_WINDOWS=256`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 输入窗口：Stage022 `goal_worst_windows` 中目标变体的负收益窗口，按收益从低到高取前 256 个。
- 输入曲线：Stage022 `curves` 中 `stage013_guarded_quality_xsmom12_not_opposed` 条件曲线。
- 输入 delta：Stage022 `lot_deltas` 中同一条件的退出日 proxy delta。
- 口径：窗口内 `(start_date, end_date]` 的 base `net_pnl` 与 `stage022_daily_delta` 拆分，校验二者和是否等于权益变化。

## 结果

- focus windows：`12`
- worst window：`{'source_start_month': '2022-07', 'start_date': '2022-07-15', 'end_date': '2023-07-17', 'return_pct': -40.537589684932925, 'variant_equity_delta': -116955.0, 'base_net_pnl_in_window': -126350.00000000001, 'stage022_delta_in_window': 9395.0}`
- focus variant equity delta：`-1085347.5000`
- focus base net pnl：`-1132935.0000`
- focus Stage022 delta：`47587.5000`
- Stage022 delta / loss abs：`4.3845%`
- dragged window count：`6`
- helped window count：`6`
- neutral window count：`0`
- max component reconciliation abs diff：`0.00000000`
- max lot delta reconciliation abs diff：`0.00000000`
- 决策：`stage023_residual_loss_base_dominant_stage022_still_helping`

## 源起点汇总

| source_start_month   |   window_count |   worst_return_pct |   median_return_pct |   variant_equity_delta |   base_net_pnl_in_window |   stage022_delta_in_window |   selected_lot_count |   selected_lot_realized_pnl |   max_component_reconciliation_abs_diff |   max_lot_delta_reconciliation_abs_diff | stage022_component_effect   |
|:---------------------|---------------:|-------------------:|--------------------:|-----------------------:|-------------------------:|---------------------------:|---------------------:|----------------------------:|----------------------------------------:|----------------------------------------:|:----------------------------|
| 2022-07              |              3 |           -40.5376 |            -40.4856 |                -350395 |                  -378580 |                    28185   |                    6 |                      112740 |                             1.45519e-11 |                                       0 | helped                      |
| 2021-07              |              3 |           -35.7299 |            -35.7299 |                -402058 |                  -423125 |                    21067.5 |                   12 |                       84270 |                             0           |                                       0 | helped                      |
| 2022-01              |              6 |           -33.7953 |            -32.6259 |                -332895 |                  -331230 |                    -1665   |                   15 |                       -6660 |                             0           |                                       0 | dragged                     |

## 过拟合反思

- 运行前判断：否。本阶段只做固定 Stage022 最优变体的失败归因，不根据结果改阈值、品种、方向、lookback 或资金权重。
- 运行后判断：否。本阶段没有产生新策略规则；如果拿归因中的具体产品/日期做黑名单，会变成过拟合。

## 继续价值反思

- 运行前判断：有价值。Stage022 已显示结构性改善，剩余负窗口归因能决定下一步该转真实引擎还是换信息源。
- 运行后判断：有价值。focus 窗口中 Stage022 delta 仍在帮忙，剩余失败主要来自 base 趋势持仓路径，下一步应做真实引擎可实现性和 base residual 持仓归因。

## 输出文件

- focus_windows：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage023_stage022_residual_window_attribution/rebuilt_c9_v2_stage023_stage022_residual_window_attribution_focus_windows_stage023_stage022_residual_window_attribution_v1.csv`
- window_attribution：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage023_stage022_residual_window_attribution/rebuilt_c9_v2_stage023_stage022_residual_window_attribution_window_attribution_stage023_stage022_residual_window_attribution_v1.csv`
- daily_detail：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage023_stage022_residual_window_attribution/rebuilt_c9_v2_stage023_stage022_residual_window_attribution_daily_detail_stage023_stage022_residual_window_attribution_v1.csv.gz`
- source_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage023_stage022_residual_window_attribution/rebuilt_c9_v2_stage023_stage022_residual_window_attribution_source_summary_stage023_stage022_residual_window_attribution_v1.csv`
- product_direction_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage023_stage022_residual_window_attribution/rebuilt_c9_v2_stage023_stage022_residual_window_attribution_product_direction_summary_stage023_stage022_residual_window_attribution_v1.csv`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage023_stage022_residual_window_attribution/rebuilt_c9_v2_stage023_stage022_residual_window_attribution_component_chart_stage023_stage022_residual_window_attribution_v1.png`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage023_stage022_residual_window_attribution/rebuilt_c9_v2_stage023_stage022_residual_window_attribution_decision_stage023_stage022_residual_window_attribution_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage023_stage022_residual_window_attribution/rebuilt_c9_v2_stage023_stage022_residual_window_attribution_report_stage023_stage022_residual_window_attribution_v1.md`