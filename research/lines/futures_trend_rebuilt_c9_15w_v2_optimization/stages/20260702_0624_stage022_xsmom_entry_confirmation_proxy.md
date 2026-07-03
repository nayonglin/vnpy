# Stage022 xsmom 入场确认加风险 proxy

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T06:16:15
- 阶段性质：closed-lot + curve proxy；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否；若出现达标候选，也必须先转真实引擎/保证金/整数手审计

## 外部调研与判断

- 参考：meta-labeling / bet sizing、trend-following signal confidence、cross-sectional momentum alignment。
- 我的判断：方向应由 C9 主策略给出，二级层只负责决定哪些入场值得加风险；xsmom 作为独立收益袖失败后，作为入场确认仍值得只读验证。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage022_xsmom_entry_confirmation_proxy.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage022_xsmom_entry_confirmation.py`
- 新增参数：`ADD_RISK_FRACTION=0.25`、`SPECS=['mom_12m_skip1m', 'mom_6m_skip1m']`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 输入事件：Stage009 quality events。
- xsmom 状态：Stage020 satellite daily，使用入场前一交易日 long/short 产品列表。
- proxy：每个条件选中 lot 在退出日增加 `realized_pnl * 25%`。
- 基础曲线：Stage013 account-state pilot curves；不是 Stage167 current C9 真引擎。

## 结果

- tagged events：`2867`
- lot deltas：`7321`
- stable condition count：`10`
- 基准严格 `>1` 年负窗口：`330947`，最差 `-43.7940%`
- 最优候选：`stage022_stage013_guarded_quality_xsmom12_not_opposed`
- 最优候选严格 `>1` 年负窗口：`231382`，最差 `-40.5376%`
- 最优候选最小收益保留：`1.0828`
- 目标通过 variant 数：`0`
- 决策：`stage022_xsmom_confirmed_quality_improves_left_tail_need_failure_attribution`

## 目标门汇总

| variant                                               |   all_gt1y_negative_count |   all_gt1y_min_return_pct |   to_final_negative_count |   min_retention |   median_total_return_pct |   worst_max_drawdown_pct |   objective_pass |
|:------------------------------------------------------|--------------------------:|--------------------------:|--------------------------:|----------------:|--------------------------:|-------------------------:|-----------------:|
| stage022_stage013_guarded_quality_xsmom12_not_opposed |                    231382 |                  -40.5376 |                         0 |          1.0828 |                   275.905 |                 -40.5376 |                0 |
| stage022_stage013_guarded_quality                     |                    232390 |                  -40.5376 |                         0 |          1.2234 |                   297.728 |                 -40.5376 |                0 |
| stage022_stage013_guarded_quality_xsmom6_not_opposed  |                    244483 |                  -40.5376 |                         0 |          1.1873 |                   290.399 |                 -40.5376 |                0 |
| stage022_stage013_guarded_quality_xsmom12_aligned     |                    245464 |                  -40.5376 |                         0 |          1      |                   253.69  |                 -40.5376 |                0 |
| stage022_stage010_quality                             |                    269509 |                  -41.2213 |                         0 |          1.1683 |                   286.72  |                 -41.2213 |                0 |
| stage022_stage010_quality_xsmom12_not_opposed         |                    274451 |                  -41.2213 |                         0 |          1.0198 |                   265.537 |                 -41.2213 |                0 |
| stage022_stage010_quality_xsmom12_aligned             |                    284047 |                  -42.314  |                         0 |          0.9901 |                   246.607 |                 -42.314  |                0 |
| stage022_stage010_quality_xsmom6_not_opposed          |                    284452 |                  -41.2213 |                         0 |          1.1244 |                   279.49  |                 -41.2213 |                0 |
| stage022_stage013_guarded_quality_both_xsmom_aligned  |                    287995 |                  -43.8676 |                         0 |          1      |                   246.094 |                 -43.8676 |                0 |
| stage022_stage013_guarded_quality_xsmom6_aligned      |                    288798 |                  -43.8676 |                         0 |          1      |                   246.769 |                 -43.8676 |                0 |
| stage022_stage010_quality_both_xsmom_aligned          |                    316377 |                  -45.1154 |                         0 |          0.9807 |                   240.427 |                 -45.1154 |                0 |
| stage013_engine                                       |                    330947 |                  -43.794  |                         0 |          1      |                   238.369 |                 -43.794  |                0 |
| stage022_stage010_quality_xsmom6_aligned              |                    333014 |                  -45.8953 |                         0 |          0.9807 |                   239.602 |                 -45.8953 |                0 |

## 条件质量摘要

| condition                                    |   event_count |   year_count |   positive_year_count |   total_pnl |   mean_pnl_lift |   bad_path_rate_delta_pp | stable_quality_candidate   |
|:---------------------------------------------|--------------:|-------------:|----------------------:|------------:|----------------:|-------------------------:|:---------------------------|
| stage013_guarded_quality_both_xsmom_aligned  |           112 |            6 |                     4 | 1.73175e+07 |          7.0058 |                   2.5923 | True                       |
| stage013_guarded_quality_xsmom12_aligned     |           157 |            7 |                     5 | 2.40574e+07 |          6.9429 |                  -2.9354 | True                       |
| stage013_guarded_quality_xsmom6_aligned      |           162 |            7 |                     5 | 1.82981e+07 |          5.1178 |                  -9.5329 | True                       |
| stage013_guarded_quality_xsmom6_not_opposed  |           717 |            7 |                     7 | 4.96625e+07 |          3.1384 |                  -3.918  | True                       |
| stage010_quality_both_xsmom_aligned          |           194 |            6 |                     4 | 1.3034e+07  |          3.0442 |                   3.5128 | True                       |
| stage010_quality_xsmom12_aligned             |           306 |            7 |                     5 | 1.99709e+07 |          2.9571 |                   0.2347 | True                       |
| stage013_guarded_quality_xsmom12_not_opposed |           732 |            7 |                     7 | 4.03414e+07 |          2.4971 |                  -5.136  | True                       |
| stage010_quality_xsmom6_aligned              |           263 |            7 |                     5 | 1.28475e+07 |          2.2134 |                  -3.2333 | True                       |
| stage010_quality_xsmom6_not_opposed          |          1184 |            7 |                     7 | 5.04117e+07 |          1.9292 |                   1.6512 | True                       |
| stage010_quality_xsmom12_not_opposed         |          1177 |            7 |                     6 | 3.96854e+07 |          1.5277 |                  -0.3298 | True                       |
| stage013_guarded_quality                     |           903 |            7 |                     7 | 5.99671e+07 |          3.009  |                  -4.3568 | False                      |
| stage010_quality                             |          1414 |            7 |                     7 | 6.03914e+07 |          1.9352 |                  -0.2719 | False                      |

## 过拟合反思

- 运行前判断：否。只复用 Stage010/013 冻结质量条件和 Stage020 固定 xsmom 状态，且用前一交易日信号；不按产品、日期、方向或坏窗口调参。
- 运行后判断：否。本阶段没有根据结果改 xsmom lookback/topN/权重；若失败后继续调这些细节，就是过拟合。

## 继续价值反思

- 运行前判断：有价值。Stage021 说明 xsmom 不适合作独立收益袖，但它仍可能作为入场质量确认，直接服务 AI 高质量信号加风险目标。
- 运行后判断：有但未达标。xsmom 确认能改善左尾且保留收益，下一步归因剩余负窗口并评估真实引擎。

## 输出文件

- tagged_events：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage022_xsmom_entry_confirmation_proxy/rebuilt_c9_v2_stage022_xsmom_entry_confirmation_proxy_tagged_events_stage022_xsmom_entry_confirmation_proxy_v1.csv.gz`
- condition_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage022_xsmom_entry_confirmation_proxy/rebuilt_c9_v2_stage022_xsmom_entry_confirmation_proxy_condition_summary_stage022_xsmom_entry_confirmation_proxy_v1.csv`
- lot_deltas：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage022_xsmom_entry_confirmation_proxy/rebuilt_c9_v2_stage022_xsmom_entry_confirmation_proxy_lot_deltas_stage022_xsmom_entry_confirmation_proxy_v1.csv.gz`
- curves：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage022_xsmom_entry_confirmation_proxy/rebuilt_c9_v2_stage022_xsmom_entry_confirmation_proxy_curves_stage022_xsmom_entry_confirmation_proxy_v1.csv`
- goal_aggregate：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage022_xsmom_entry_confirmation_proxy/rebuilt_c9_v2_stage022_xsmom_entry_confirmation_proxy_goal_aggregate_stage022_xsmom_entry_confirmation_proxy_v1.csv`
- retention：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage022_xsmom_entry_confirmation_proxy/rebuilt_c9_v2_stage022_xsmom_entry_confirmation_proxy_retention_vs_stage013_stage022_xsmom_entry_confirmation_proxy_v1.csv`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage022_xsmom_entry_confirmation_proxy/rebuilt_c9_v2_stage022_xsmom_entry_confirmation_proxy_goal_chart_stage022_xsmom_entry_confirmation_proxy_v1.png`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage022_xsmom_entry_confirmation_proxy/rebuilt_c9_v2_stage022_xsmom_entry_confirmation_proxy_decision_stage022_xsmom_entry_confirmation_proxy_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage022_xsmom_entry_confirmation_proxy/rebuilt_c9_v2_stage022_xsmom_entry_confirmation_proxy_report_stage022_xsmom_entry_confirmation_proxy_v1.md`
