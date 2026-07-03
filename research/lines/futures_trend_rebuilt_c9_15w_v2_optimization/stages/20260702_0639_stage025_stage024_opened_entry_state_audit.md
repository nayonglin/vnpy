# Stage025 - Stage024 opened/traded 入场状态审计

- 记录时间：2026-07-02 06:39 CST
- 所属研究线：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 是否重要突破版本：否，当前是只读法证审计，不是正式策略候选。

## 本次版本改动

- 新增：`tools/stage025_stage024_opened_entry_state_audit.py`
- 新增：Stage024 opened/traded 负净损失行到 Stage019 closed lots 的 entry exposure 映射。
- 新增：Stage022 xsmom 标签 join，用于只读检查 `xsmom12/xsmom6` 入场确认状态。
- 修改参数：无。
- 删除参数：无。

## 回测结果

- 本阶段未新增正式回测。
- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 审计结果

- Stage024 opened/traded 负净损失行：`146`。
- entry exposure rows：`307`，unique exposed lots：`92`。
- matched net loss：`874105.0000`，matched share：`100.0000%`。
- stable candidate conditions：`['ai_rank_1_8_and_selected_volume_gt1', 'selected_volume_gt1', 'rsi_exhaustion_zone', 'risk_multiplier_ge2', 'ai_rank_5_8']`。
- 决策：`stage025_opened_entry_states_have_loss_concentration_candidates_need_true_guard_or_quality_split`。
- 理由：存在跨 source、入场前可见条件，其 lot 占比低于净亏损占比且 lift 达标；只能作为下一步真实 guard/质量拆分假设，不能直接上线。

## 条件 Top 10

| condition                           | description                           | candidate_eligible   |   population_count |   population_share_pct |   source_count |   loss_source_count |   date_count |   residual_exposed_lot_count |   residual_exposed_lot_rate_pct |   residual_exposure_count_sum |   allocated_net_loss_abs |   allocated_net_loss_share_pct |   allocated_holding_loss_abs |   allocated_holding_loss_share_pct |   net_loss_lift_vs_population |   realized_pnl_sum |   realized_pnl_mean |   median_ai_rank |   median_selected_volume |   median_risk_multiplier |   median_active_positions_before |   median_drawdown_abs_pct |   median_rsi | stable_candidate   |
|:------------------------------------|:--------------------------------------|:---------------------|-------------------:|-----------------------:|---------------:|--------------------:|-------------:|-----------------------------:|--------------------------------:|------------------------------:|-------------------------:|-------------------------------:|-----------------------------:|-----------------------------------:|------------------------------:|-------------------:|--------------------:|-----------------:|-------------------------:|-------------------------:|---------------------------------:|--------------------------:|-------------:|:-------------------|
| ai_rank_1_8_and_selected_volume_gt1 | AI rank 1-8 且 selected_volume>1      | True                 |                 28 |                26.4151 |              3 |                   3 |           14 |                           23 |                         82.1429 |                            87 |                   444922 |                        50.9003 |                       392105 |                            53.3204 |                        1.9269 |            -128700 |            -4596.43 |                5 |                      6   |                        2 |                                0 |                   20.0448 |      62.5279 | True               |
| selected_volume_gt1                 | selected_volume >1                    | True                 |                 36 |                33.9623 |              3 |                   3 |           19 |                           29 |                         80.5556 |                           106 |                   483525 |                        55.3166 |                       414189 |                            56.3235 |                        1.6288 |            -149750 |            -4159.72 |                5 |                      6   |                        2 |                                0 |                   22.9135 |      64.0809 | True               |
| rsi_exhaustion_zone                 | RSI 极端顺势区：long>=75 或 short<=25 | True                 |                 30 |                28.3019 |              3 |                   3 |           15 |                           29 |                         96.6667 |                            95 |                   355819 |                        40.7066 |                       306730 |                            41.7108 |                        1.4383 |             -97555 |            -3251.83 |                6 |                      1   |                        2 |                                0 |                   32.1798 |      76.8434 | True               |
| risk_multiplier_ge2                 | risk_multiplier >=2                   | True                 |                 55 |                51.8868 |              3 |                   3 |           26 |                           51 |                         92.7273 |                           168 |                   600241 |                        68.6692 |                       520502 |                            70.7805 |                        1.3234 |            -158770 |            -2886.73 |                4 |                      1   |                        2 |                                0 |                   27.5823 |      67.7083 | True               |
| ai_rank_5_8                         | AI rank 5-8                           | True                 |                 35 |                33.0189 |              3 |                   3 |           18 |                           30 |                         85.7143 |                            96 |                   362330 |                        41.4515 |                       348465 |                            47.386  |                        1.2554 |            -113580 |            -3245.14 |                6 |                      2   |                        2 |                                0 |                   29.7025 |      67.4273 | True               |
| xsmom12_aligned                     | 前一交易日 12-1m xsmom 与入场方向一致 | True                 |                 19 |                17.9245 |              3 |                   3 |            9 |                           15 |                         78.9474 |                            51 |                   253350 |                        28.9839 |                       232770 |                            31.6532 |                        1.617  |             -65160 |            -3429.47 |                5 |                      3   |                        2 |                                0 |                   23.925  |      69.6504 | False              |
| xsmom6_aligned                      | 前一交易日 6-1m xsmom 与入场方向一致  | True                 |                 18 |                16.9811 |              3 |                   3 |            8 |                           17 |                         94.4444 |                            56 |                   221955 |                        25.3923 |                       149715 |                            20.359  |                        1.4953 |             -67900 |            -3772.22 |                5 |                      2.5 |                        2 |                                0 |                   25.2586 |      71.1275 | False              |
| xsmom6_opposed                      | 前一交易日 6-1m xsmom 反向            | True                 |                  5 |                 4.717  |              2 |                   2 |            3 |                            5 |                        100      |                            15 |                    59190 |                         6.7715 |                        91830 |                            12.4875 |                        1.4356 |             -18790 |            -3758    |                3 |                      1   |                        2 |                                1 |                   24.7658 |      26.6456 | False              |
| ai_rank_1_8                         | AI rank 1-8                           | True                 |                 79 |                74.5283 |              3 |                   3 |           35 |                           69 |                         87.3418 |                           225 |                   742005 |                        84.8874 |                       654220 |                            88.9641 |                        1.139  |            -176480 |            -2233.92 |                4 |                      1   |                        2 |                                0 |                   31.6557 |      67.4273 | False              |
| ai_rank_1_4                         | AI rank 1-4                           | True                 |                 44 |                41.5094 |              3 |                   3 |           21 |                           39 |                         88.6364 |                           129 |                   379675 |                        43.4359 |                       305755 |                            41.5781 |                        1.0464 |             -62900 |            -1429.55 |                2 |                      1   |                        2 |                                0 |                   31.8117 |      68.3439 | False              |

## 反思

- 是否过拟合：否。没有根据单一日期、品种、方向做黑名单，也没有扫小参数；只是验证亏损 lot 的 PIT 状态。
- 是否还有价值继续：是。如果稳定条件能转成真实引擎 A/B 并保留右尾，才有继续价值；否则停止这条 focus-window 挖掘。

## TODO

- 下一步先 review Stage025 稳定条件是否具备第一性原理解释。
- 若具备，再做冻结条件的真实引擎 A/B；若不具备，转账户状态或外生确认源。
