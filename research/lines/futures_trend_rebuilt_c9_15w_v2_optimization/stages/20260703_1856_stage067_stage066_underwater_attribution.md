# Stage067 Stage066 水下时长归因

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-03T18:56:42
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 是否重要突破：否，归因阶段；不改策略、不调参数、不晋级
- 是否触发A/B：否，本阶段不提出接入正式版的候选变更

## 外部调研与判断

- GIPS/TWR 的核心提醒是外部现金流要和投资能力分离，本阶段继续把储备释放作为现金流和 sizing 变量，不计入 alpha。
- GitHub/backtesting 常用最大回撤持续期和 underwater 概念说明，水下时长要和最大回撤幅度分开看；本阶段同时拆 `days below initial`、trough shortfall 和 recovery_after_trough。
- Man Group/AQR 趋势跟随资料都提示趋势策略存在长期小亏等待右尾的结构；但本样本的问题不是一般趋势等待，而是部分起点右尾不足以补回前段缺口。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage067_stage066_underwater_attribution.py`
- 修改正式入口：无
- 删除文件：无
- 新增参数：无交易参数；归因固定选取 Stage066 最长水下 8 条代表路径
- 修改参数：无
- 删除参数：无

## 归因口径

- 总账户权益：`broker_equity_with_cashflow + reserve_remaining`。
- 水下：`total_account_equity < 300000`。
- 储备释放：只改变后续 broker sizing equity，不创造 PnL。
- 逐品种归因：仅对关键路径锁定 Stage062 candidate AI 文件后重放，按 positions 的日净 PnL 聚合。
- 关键路径重放校验：`8/8` 通过。

## 结果摘要

| version                              | variant_label     |   start_count |   max_underwater_days |   median_underwater_days |   end_below_count |   median_trough_shortfall |   median_final_shortfall |
|:-------------------------------------|:------------------|--------------:|----------------------:|-------------------------:|------------------:|--------------------------:|-------------------------:|
| stage066_30w_idle_reserve_no_release | no_release        |            55 |                  1070 |                       77 |                18 |                     15165 |                        0 |
| stage066_30w_daily_floor_release     | daily_release     |            55 |                  1057 |                       75 |                 9 |                     18728 |                        0 |
| stage066_30w_month_end_floor_release | month_end_release |            55 |                  1020 |                      109 |                12 |                     16110 |                        0 |

## 最长水下路径

|   rank | variant_label     | requested_start_month   |   total_account_days_below_initial | trough_date   |   trough_shortfall_to_300k |   recovery_after_trough |   final_shortfall_to_300k | ends_below_initial   |   max_external_cashflow_used |
|-------:|:------------------|:------------------------|-----------------------------------:|:--------------|---------------------------:|------------------------:|--------------------------:|:---------------------|-----------------------------:|
|      1 | no_release        | 2021-12                 |                               1070 | 2024-03-14    |                      49405 |                 13068.1 |                   36336.9 | True                 |                            0 |
|      2 | daily_release     | 2021-12                 |                               1057 | 2023-10-27    |                      61620 |                 35943.1 |                   25676.9 | True                 |                        99200 |
|      3 | month_end_release | 2022-04                 |                               1020 | 2023-10-27    |                      76340 |                 29403.1 |                   46936.9 | True                 |                        89600 |
|      4 | month_end_release | 2021-11                 |                                996 | 2023-10-27    |                      48750 |                 28993.1 |                   19756.9 | True                 |                        82050 |
|      5 | no_release        | 2022-08                 |                                933 | 2024-03-14    |                      68895 |                 37818.5 |                   31076.5 | True                 |                            0 |
|      6 | daily_release     | 2022-03                 |                                933 | 2023-10-27    |                      56120 |                 42728.1 |                   13391.9 | True                 |                        84540 |
|      7 | month_end_release | 2022-03                 |                                908 | 2023-10-27    |                      55410 |                 48788.1 |                    6621.9 | True                 |                        75570 |
|      8 | no_release        | 2021-11                 |                                897 | 2024-03-14    |                      50300 |                 36633.5 |                   13666.5 | True                 |                            0 |

## 决策

- 决策：`underwater_attribution_keep_research_only`
- 原因：长水下不是储备会计 bug，主要来自若干起点在前段快速跌破 300k 后，后续趋势盈利不足以补回缺口；月末释放和日级释放会改变后续 sizing，但也会把坏阶段暴露放大，不能直接晋级。

## 后续规划和 TODO

- 如果继续，应先做“恢复段暴露治理”：区分储备释放后新增的好/坏开仓，而不是扫释放日期。
- 不做基于单品种/单方向亏损的黑名单。
- 修复或封装重放入口，确保未来逐品种归因默认绑定 Stage062 AI 文件，避免 AI 路径漂移。

## 过拟合反思

- 运行前：否。归因只读 Stage066 已有曲线并固定代表路径，不根据结果修改参数。
- 运行后：否。没有按水下月份调释放日、储备金额、品种或方向；逐品种结果只用于解释，不生成黑名单。

## 继续价值反思

- 运行前：有。用户关心 22/23 启动水下久，必须先拆清楚是口径、现金流、早期亏损还是后续恢复不足。
- 运行后：有，但方向应转向账户层暴露治理和恢复段质量识别；不应继续按单月曲线 sweep 参数。

## 输出

- path_metrics: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage067_stage066_underwater_attribution/rebuilt_c9_v2_stage067_stage066_underwater_attribution_path_underwater_metrics_stage067_stage066_underwater_attribution_v1.csv`
- key_paths: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage067_stage066_underwater_attribution/rebuilt_c9_v2_stage067_stage066_underwater_attribution_key_paths_stage067_stage066_underwater_attribution_v1.csv`
- monthly_pnl: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage067_stage066_underwater_attribution/rebuilt_c9_v2_stage067_stage066_underwater_attribution_monthly_pnl_attribution_stage067_stage066_underwater_attribution_v1.csv`
- phase_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage067_stage066_underwater_attribution/rebuilt_c9_v2_stage067_stage066_underwater_attribution_phase_summary_stage067_stage066_underwater_attribution_v1.csv`
- product_attribution: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage067_stage066_underwater_attribution/rebuilt_c9_v2_stage067_stage066_underwater_attribution_key_product_direction_attribution_stage067_stage066_underwater_attribution_v1.csv`
- product_top_losers: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage067_stage066_underwater_attribution/rebuilt_c9_v2_stage067_stage066_underwater_attribution_key_product_direction_top_losers_stage067_stage066_underwater_attribution_v1.csv`
- rerun_validation: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage067_stage066_underwater_attribution/rebuilt_c9_v2_stage067_stage066_underwater_attribution_key_rerun_validation_stage067_stage066_underwater_attribution_v1.csv`
- cashflow_attribution: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage067_stage066_underwater_attribution/rebuilt_c9_v2_stage067_stage066_underwater_attribution_cashflow_attribution_stage067_stage066_underwater_attribution_v1.csv`
- chart_burden: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage067_stage066_underwater_attribution/rebuilt_c9_v2_stage067_stage066_underwater_attribution_underwater_burden_stage067_stage066_underwater_attribution_v1.png`
- chart_product: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage067_stage066_underwater_attribution/rebuilt_c9_v2_stage067_stage066_underwater_attribution_key_product_losers_stage067_stage066_underwater_attribution_v1.png`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage067_stage066_underwater_attribution/rebuilt_c9_v2_stage067_stage066_underwater_attribution_report_stage067_stage066_underwater_attribution_v1.md`
