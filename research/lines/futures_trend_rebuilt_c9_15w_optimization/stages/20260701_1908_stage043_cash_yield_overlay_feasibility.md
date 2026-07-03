# Stage043 - 现金收益账户外层可行性审计

- 记录时间：`2026-07-01T19:08`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage043_cash_yield_overlay_feasibility_v1`
- 决策：`stage043_cash_yield_overlay_not_enough_requires_new_exogenous_source`

## 口径

- 只读复用 Stage042 的 `32` 个日级冷启动曲线。
- 不改变交易信号、不改变持仓路径、不连接 CTP、不调用订单 API。
- 现金收益 overlay 公式：`overlay_equity = strategy_equity + 150000 * annual_yield * elapsed_days / 365`。
- 这是账户外层可行性下界审计，不是策略 alpha。

## 现金收益敏感性

| source_variant                                   |   cash_yield_rate |   cash_yield_rate_pct |   requested_start_count |   negative_probe_start_count |   window_count |   negative_count |   negative_rate_pct |   min_return_pct | worst_requested_start   | worst_end_date   |   to_final_min_return_pct |   required_yield_to_clear_pct |
|:-------------------------------------------------|------------------:|----------------------:|------------------------:|-----------------------------:|---------------:|-----------------:|--------------------:|-----------------:|:------------------------|:-----------------|--------------------------:|------------------------------:|
| stage013_daily_cold_start_engine                 |              0    |                     0 |                      32 |                           32 |          24422 |             7624 |            31.2178  |        -36.5967  | 2022-03-30              | 2023-07-07       |                   55.0954 |                       34.2196 |
| stage013_daily_cold_start_engine                 |              0.03 |                     3 |                      32 |                           32 |          24422 |             7020 |            28.7446  |        -32.7994  | 2022-04-01              | 2023-07-07       |                   66.6598 |                       34.2196 |
| stage013_daily_cold_start_engine                 |              0.05 |                     5 |                      32 |                           32 |          24422 |             6362 |            26.0503  |        -30.5435  | 2022-04-01              | 2023-04-28       |                   74.3694 |                       34.2196 |
| stage013_daily_cold_start_engine                 |              0.08 |                     8 |                      32 |                           28 |          24422 |             4799 |            19.6503  |        -27.3216  | 2022-04-01              | 2023-04-28       |                   85.9338 |                       34.2196 |
| stage013_daily_cold_start_engine                 |              0.12 |                    12 |                      32 |                           27 |          24422 |             3204 |            13.1193  |        -23.0257  | 2022-04-01              | 2023-04-28       |                  101.353  |                       34.2196 |
| stage013_daily_cold_start_engine                 |              0.2  |                    20 |                      32 |                           20 |          24422 |              748 |             3.06281 |        -14.4339  | 2022-04-01              | 2023-04-28       |                  132.191  |                       34.2196 |
| stage013_daily_cold_start_engine                 |              0.4  |                    40 |                      32 |                            0 |          24422 |                0 |             0       |          5.79626 | 2022-03-30              | 2023-03-31       |                  209.287  |                       34.2196 |
| stage042_daily_cold_start_stage039_ai_top8_proxy |              0    |                     0 |                      32 |                           32 |          24422 |             7624 |            31.2178  |        -36.4775  | 2022-03-30              | 2023-07-07       |                   64.2808 |                       34.2296 |
| stage042_daily_cold_start_stage039_ai_top8_proxy |              0.03 |                     3 |                      32 |                           32 |          24422 |             7064 |            28.9247  |        -32.7014  | 2022-04-01              | 2023-04-28       |                   75.8452 |                       34.2296 |
| stage042_daily_cold_start_stage039_ai_top8_proxy |              0.05 |                     5 |                      32 |                           32 |          24422 |             6216 |            25.4525  |        -30.5535  | 2022-04-01              | 2023-04-28       |                   83.5548 |                       34.2296 |
| stage042_daily_cold_start_stage039_ai_top8_proxy |              0.08 |                     8 |                      32 |                           28 |          24422 |             4847 |            19.8469  |        -27.3316  | 2022-04-01              | 2023-04-28       |                   95.1192 |                       34.2296 |
| stage042_daily_cold_start_stage039_ai_top8_proxy |              0.12 |                    12 |                      32 |                           27 |          24422 |             3162 |            12.9473  |        -23.0357  | 2022-04-01              | 2023-04-28       |                  110.538  |                       34.2296 |
| stage042_daily_cold_start_stage039_ai_top8_proxy |              0.2  |                    20 |                      32 |                           14 |          24422 |              634 |             2.59602 |        -14.4439  | 2022-04-01              | 2023-04-28       |                  141.377  |                       34.2296 |
| stage042_daily_cold_start_stage039_ai_top8_proxy |              0.4  |                    40 |                      32 |                            0 |          24422 |                0 |             0       |          5.78626 | 2022-03-30              | 2023-03-31       |                  218.473  |                       34.2296 |

## 所需收益率最高的窗口

| requested_start   | end_date   |   elapsed_days |   start_equity |   end_equity |   return_pct |   required_simple_annual_yield |   required_simple_annual_yield_pct | source_variant                                   | probe_bucket   |
|:------------------|:-----------|---------------:|---------------:|-------------:|-------------:|-------------------------------:|-----------------------------------:|:-------------------------------------------------|:---------------|
| 2022-03-30        | 2023-03-31 |            366 |         150000 |        98515 |     -34.3233 |                       0.342296 |                            34.2296 | stage042_daily_cold_start_stage039_ai_top8_proxy | both_negative  |
| 2022-03-30        | 2023-03-31 |            366 |         150000 |        98530 |     -34.3133 |                       0.342196 |                            34.2196 | stage013_daily_cold_start_engine                 | both_negative  |
| 2022-04-01        | 2023-04-03 |            367 |         150000 |        98515 |     -34.3233 |                       0.341363 |                            34.1363 | stage042_daily_cold_start_stage039_ai_top8_proxy | both_negative  |
| 2022-04-01        | 2023-04-03 |            367 |         150000 |        98530 |     -34.3133 |                       0.341263 |                            34.1263 | stage013_daily_cold_start_engine                 | both_negative  |
| 2022-04-01        | 2023-04-04 |            368 |         150000 |        98515 |     -34.3233 |                       0.340435 |                            34.0435 | stage042_daily_cold_start_stage039_ai_top8_proxy | both_negative  |
| 2022-04-01        | 2023-04-04 |            368 |         150000 |        98530 |     -34.3133 |                       0.340336 |                            34.0336 | stage013_daily_cold_start_engine                 | both_negative  |
| 2022-03-30        | 2023-04-03 |            369 |         150000 |        98515 |     -34.3233 |                       0.339513 |                            33.9513 | stage042_daily_cold_start_stage039_ai_top8_proxy | both_negative  |
| 2022-03-30        | 2023-04-03 |            369 |         150000 |        98530 |     -34.3133 |                       0.339414 |                            33.9414 | stage013_daily_cold_start_engine                 | both_negative  |
| 2022-04-01        | 2023-04-06 |            370 |         150000 |        98515 |     -34.3233 |                       0.338595 |                            33.8595 | stage042_daily_cold_start_stage039_ai_top8_proxy | both_negative  |
| 2022-03-30        | 2023-04-04 |            370 |         150000 |        98515 |     -34.3233 |                       0.338595 |                            33.8595 | stage042_daily_cold_start_stage039_ai_top8_proxy | both_negative  |
| 2022-04-01        | 2023-04-06 |            370 |         150000 |        98530 |     -34.3133 |                       0.338496 |                            33.8496 | stage013_daily_cold_start_engine                 | both_negative  |
| 2022-03-30        | 2023-04-04 |            370 |         150000 |        98530 |     -34.3133 |                       0.338496 |                            33.8496 | stage013_daily_cold_start_engine                 | both_negative  |
| 2022-04-01        | 2023-04-07 |            371 |         150000 |        98515 |     -34.3233 |                       0.337682 |                            33.7682 | stage042_daily_cold_start_stage039_ai_top8_proxy | both_negative  |
| 2022-04-01        | 2023-04-07 |            371 |         150000 |        98530 |     -34.3133 |                       0.337584 |                            33.7584 | stage013_daily_cold_start_engine                 | both_negative  |
| 2022-03-30        | 2023-04-06 |            372 |         150000 |        98515 |     -34.3233 |                       0.336775 |                            33.6775 | stage042_daily_cold_start_stage039_ai_top8_proxy | both_negative  |
| 2022-03-30        | 2023-04-06 |            372 |         150000 |        98530 |     -34.3133 |                       0.336677 |                            33.6677 | stage013_daily_cold_start_engine                 | both_negative  |
| 2022-03-30        | 2023-04-07 |            373 |         150000 |        98515 |     -34.3233 |                       0.335872 |                            33.5872 | stage042_daily_cold_start_stage039_ai_top8_proxy | both_negative  |
| 2022-03-30        | 2023-04-07 |            373 |         150000 |        98530 |     -34.3133 |                       0.335774 |                            33.5774 | stage013_daily_cold_start_engine                 | both_negative  |
| 2022-04-01        | 2023-04-10 |            374 |         150000 |        98515 |     -34.3233 |                       0.334974 |                            33.4974 | stage042_daily_cold_start_stage039_ai_top8_proxy | both_negative  |
| 2022-04-01        | 2023-04-10 |            374 |         150000 |        98530 |     -34.3133 |                       0.334876 |                            33.4876 | stage013_daily_cold_start_engine                 | both_negative  |

## 判断

- Stage042 proxy 要把全部 `>365` 天窗口打到非负，所需简单年化现金收益率为 `34.2296%`。
- 固定 `8%` 年化现金收益仍有 `4847` 个负结束日。
- 固定 `20%` 年化现金收益仍有 `634` 个负结束日。
- 因此普通现金管理/备用金利息不是足够强的左尾解法。

## 输出

- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage043_cash_yield_overlay_feasibility/rebuilt_c9_stage043_cash_yield_overlay_feasibility_summary_stage043_cash_yield_overlay_feasibility_v1.csv`
- required_windows：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage043_cash_yield_overlay_feasibility/rebuilt_c9_stage043_cash_yield_overlay_feasibility_required_windows_stage043_cash_yield_overlay_feasibility_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage043_cash_yield_overlay_feasibility/rebuilt_c9_stage043_cash_yield_overlay_feasibility_decision_stage043_cash_yield_overlay_feasibility_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage043_cash_yield_overlay_feasibility/rebuilt_c9_stage043_cash_yield_overlay_feasibility_report_stage043_cash_yield_overlay_feasibility_v1.md`
- stage_record：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/stages/20260701_1908_stage043_cash_yield_overlay_feasibility.md`

## 反思

- 运行前过拟合反思：否。本阶段不新增交易规则，只验证账户外层的数学下界。
- 运行后过拟合反思：否。结论不依赖选择某个阈值入场；若用不现实收益率或按窗口注入资金救曲线才是过拟合/口径漂移。
- 运行前继续价值反思：有。Stage042 后必须判断账户外层是否值得继续。
- 运行后继续价值反思：账户外层普通现金收益路线继续价值低；更有价值的是新外生信息源或真正能改变坏窗口持仓路径的因果特征。
