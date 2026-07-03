# Stage011 Stage010 剩余左尾归因

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T04:32:01
- 阶段性质：只读归因；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否；本阶段不跑新资金曲线，只归因 Stage010 失败窗口

## 外部调研与判断

- 参考资料：meta-labeling bet sizing、trend-following right-tail/drawdown attribution、pysystemtrade capital correction。
- 我的判断：Stage010 已证明质量加风险有信息量，但剩余左尾必须先分清是持仓路径、覆盖不足还是选中负贡献，不能继续扫 `25%/rank/topN/产品/方向`。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage011_stage010_remaining_left_tail_attribution.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage011_stage010_remaining_left_tail_attribution.py`
- 新增参数：`TOP_N_FOCUS_WINDOWS=64`、`TARGET_VARIANT=stage010_quality_add_risk_proxy`
- 修改参数：无
- 删除参数：无

## 结果

- focus windows：`64`
- Stage010 focus loss abs：`4,466,367.50`
- proxy delta / loss abs：`-6.1950%`
- selected closed-lot PnL：`-1,106,770.00`
- unselected quality event PnL：`-1,225,840.00`
- base delta minus quality-event PnL：`-1,857,065.00`，占 focus loss abs `-41.5789%`
- 选中负贡献 product/direction 数：`10`
- 决策：`stage011_selected_quality_has_negative_drag_need_true_engine_guard_audit`
- 原因：Stage010 选中质量事件中仍存在负贡献簇；只能做通用 guard 审计，不能做产品/方向黑名单。

## Source Summary

| source_start_month   |   focus_window_count |   worst_return_pct |   stage010_equity_delta_sum |   base_equity_delta_sum |   proxy_delta_sum |   selected_closed_lot_pnl_sum |   unselected_quality_event_pnl_sum |   base_delta_minus_quality_event_pnl_sum |
|:---------------------|---------------------:|-------------------:|----------------------------:|------------------------:|------------------:|------------------------------:|-----------------------------------:|-----------------------------------------:|
| 2022-07              |                   13 |           -41.2213 |                -1.16292e+06 |            -1.12648e+06 |          -36437.5 |                       -145750 |                            -289105 |                                  -691625 |
| 2022-01              |                   42 |           -35.4655 |                -2.1607e+06  |            -1.95867e+06 |         -202035   |                       -808140 |                            -657240 |                                  -493290 |
| 2021-07              |                    9 |           -35.3322 |                -1.14274e+06 |            -1.10452e+06 |          -38220   |                       -152880 |                            -279495 |                                  -672150 |

## Selected Negative Product/Direction

| stage010_selected   | product   | direction   |   duplicated_lot_rows |   unique_lot_count |   focus_window_count |   realized_pnl |   proxy_delta_pnl |
|:--------------------|:----------|:------------|----------------------:|-------------------:|---------------------:|---------------:|------------------:|
| True                | SM.CZCE   | long        |                    54 |                  4 |                   13 |        -738540 |         -184635   |
| True                | sp.SHFE   | long        |                    67 |                  4 |                   18 |        -591840 |         -147960   |
| True                | SA.CZCE   | long        |                    64 |                  3 |                   18 |        -426000 |         -106500   |
| True                | SM.CZCE   | short       |                    64 |                  3 |                   18 |        -399000 |          -99750   |
| True                | rb.SHFE   | long        |                   106 |                  4 |                   18 |        -391160 |          -97790   |
| True                | MA.CZCE   | short       |                    45 |                  2 |                   13 |        -270300 |          -67575   |
| True                | si.GFEX   | long        |                     9 |                  1 |                    3 |         -76950 |          -19237.5 |
| True                | AP.CZCE   | long        |                    64 |                  3 |                   18 |         -41650 |          -10412.5 |
| True                | hc.SHFE   | long        |                    27 |                  4 |                    4 |         -12300 |           -3075   |
| True                | CF.CZCE   | long        |                     9 |                  1 |                    3 |         -10350 |           -2587.5 |

## 过拟合反思

- 运行前判断：否。本阶段只归因 Stage010 已冻结 proxy 的失败窗口，不新增交易参数、不按产品/方向做规则。
- 运行后判断：否。输出是归因，不是交易规则；若据负贡献产品直接黑名单或调 rank/topN/25%，才会过拟合。
- 原因：本阶段只归因，不产生交易规则；若直接按产品/方向负贡献做黑名单就是过拟合。

## 继续价值反思

- 运行前判断：有价值。Stage010 是当前最强方向但未达目标，必须定位剩余左尾来源。
- 运行后判断：有价值。归因将决定下一步是持仓级 replay、真实引擎 guard 审计，还是转新 PIT 信息源。

## 输出文件

- focus_windows: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage011_stage010_remaining_left_tail_attribution/rebuilt_c9_v2_stage011_stage010_remaining_left_tail_attribution_focus_windows_stage011_stage010_remaining_left_tail_attribution_v1.csv`
- window_attribution: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage011_stage010_remaining_left_tail_attribution/rebuilt_c9_v2_stage011_stage010_remaining_left_tail_attribution_window_attribution_stage011_stage010_remaining_left_tail_attribution_v1.csv`
- product_direction: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage011_stage010_remaining_left_tail_attribution/rebuilt_c9_v2_stage011_stage010_remaining_left_tail_attribution_product_direction_attribution_stage011_stage010_remaining_left_tail_attribution_v1.csv`
- source_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage011_stage010_remaining_left_tail_attribution/rebuilt_c9_v2_stage011_stage010_remaining_left_tail_attribution_source_summary_stage011_stage010_remaining_left_tail_attribution_v1.csv`
- chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage011_stage010_remaining_left_tail_attribution/rebuilt_c9_v2_stage011_stage010_remaining_left_tail_attribution_chart_stage011_stage010_remaining_left_tail_attribution_v1.png`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage011_stage010_remaining_left_tail_attribution/rebuilt_c9_v2_stage011_stage010_remaining_left_tail_attribution_decision_stage011_stage010_remaining_left_tail_attribution_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage011_stage010_remaining_left_tail_attribution/rebuilt_c9_v2_stage011_stage010_remaining_left_tail_attribution_report_stage011_stage010_remaining_left_tail_attribution_v1.md`
