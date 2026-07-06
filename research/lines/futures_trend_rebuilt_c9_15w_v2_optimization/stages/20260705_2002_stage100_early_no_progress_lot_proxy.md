# Stage100 早期无进展/回吐 lot-level proxy

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05 20:02 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读 lot-level 生命周期 proxy；不重新跑策略
- 是否重要突破：否
- 是否触发A/B：否，本阶段不提出可合入候选

## 外部调研与判断

- 参考资料：pysystemtrade position buffering、Rob Carver dynamic trend following、Hudson & Thames meta-labeling。
- 我的判断：早期退出最容易误杀趋势右尾，必须先用 lot-level proxy 看损失捕获与右尾牺牲；不能直接改 true engine。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage100_early_no_progress_lot_proxy.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：4 个固定生命周期 proxy：`3bars MFE<0.5R`、`5bars MFE<1R`、`5bars MFE<1R 且水下`、`2R 后回到水下`。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 输入：Stage094 closed lots。
- 账户规模：沿用 Stage094/Stage167 `150,000`，但本阶段不重算账户曲线。
- 成本口径：沿用 Stage094 closed-lot realized PnL；代理退出价使用触发日 EOD close，未加额外滑点压力。
- 引擎口径：不重新跑 true engine。
- 审计口径：lot-level PnL delta；不做产品/方向/日期黑名单。

## Classification Summary

| group_type       | group                                   |   lot_count |   loss_lot_count |           pnl_sum |   median_r |
|:-----------------|:----------------------------------------|------------:|-----------------:|------------------:|-----------:|
| exit_reason      | long_base_stop                          |         282 |              185 |      -3.33471e+06 |  -0.5      |
| exit_reason      | stage847_intraday_05r_stop_no_reentry   |          50 |               50 | -698047           |  -0.536023 |
| exit_reason      | nan                                     |          76 |               76 | -499435           |  -0.413004 |
| exit_reason      | stage827_intraday_c2_1r_stop            |           9 |                9 | -169420           |  -1.58065  |
| exit_reason      | stage847_intraday_retry_failed_05r_stop |          22 |               22 | -136977           |  -0.5      |
| exit_reason      | long_ma_stop                            |          17 |               17 | -124060           |  -0.8125   |
| exit_reason      | short_base_stop                         |          53 |               37 |  205390           |  -1        |
| exit_reason      | forced_margin_deleverage                |          36 |               12 |  341870           |   3.24     |
| exit_reason      | short_risk_cluster_heat_deleverage      |          27 |                6 |  434210           |   0.783784 |
| exit_reason      | long_risk_cluster_heat_deleverage       |         152 |               62 |       1.07285e+06 |   0.243243 |
| exit_reason      | long_rsi_partial_exit_half              |          28 |                0 |       1.47492e+06 |  14.3077   |
| exit_reason      | rollover_close                          |          79 |               18 |       1.82417e+06 |   2.33333  |
| exit_reason      | short_prev2day_stop                     |         294 |              174 |       1.86605e+06 |  -0.6875   |
| exit_reason      | long_prev2day_stop                      |         726 |              336 |       1.41398e+07 |   0.184876 |
| holding_bucket   | 1-2d                                    |         513 |              332 |      -4.67765e+06 |  -0.444444 |
| holding_bucket   | 3-5d                                    |         257 |              211 |      -4.55704e+06 |  -1.35124  |
| holding_bucket   | 0d                                      |         157 |              157 |      -1.50388e+06 |  -0.444072 |
| holding_bucket   | 6-10d                                   |         424 |              253 |      -1.39464e+06 |  -0.346939 |
| holding_bucket   | 40d+                                    |          13 |                0 |  887400           |   0.912524 |
| holding_bucket   | 21-40d                                  |         119 |                1 |       8.20795e+06 |   5.53333  |
| holding_bucket   | 11-20d                                  |         368 |               50 |       1.94344e+07 |   2.93774  |
| loser_mfe_bucket | 0-0.5R                                  |         172 |              172 |      -5.36023e+06 |  -1.45131  |
| loser_mfe_bucket | 1-2R                                    |         257 |              257 |      -5.29103e+06 |  -1.02703  |
| loser_mfe_bucket | 0.5-1R                                  |         172 |              172 |      -3.77386e+06 |  -1.06423  |
| loser_mfe_bucket | 2-5R                                    |         142 |              142 |      -2.37757e+06 |  -0.938776 |
| loser_mfe_bucket | 5R+                                     |          74 |               74 | -888300           |  -2.11538  |
| loser_mfe_bucket | 0                                       |          27 |               27 | -748215           |  -0.448529 |
| loser_mfe_bucket | mfe<0                                   |           0 |                0 |       0           | nan        |

## Variant Summary

| variant                     | label                                                  |   lot_count |   triggered_lot_count |   triggered_lot_share |   path_missing_lot_count |   start_count |   positive_delta_start_count |   negative_delta_start_count |   positive_delta_start_rate |   original_pnl_sum |   proxy_pnl_sum |   proxy_delta_sum |   loss_reduced_sum |   gain_sacrificed_sum |   loss_reduced_to_gain_sacrificed |   original_positive_pnl_sum |   original_negative_abs_sum | candidate_for_true_engine   |
|:----------------------------|:-------------------------------------------------------|------------:|----------------------:|----------------------:|-------------------------:|--------------:|-----------------------------:|-----------------------------:|----------------------------:|-------------------:|----------------:|------------------:|-------------------:|----------------------:|----------------------------------:|----------------------------:|----------------------------:|:----------------------------|
| underwater_5bars_mfe_lt1r   | 5 completed daily bars, MFE < 1.0R and current PnL < 0 |        1851 |                    21 |             0.0113452 |                      224 |            13 |                            0 |                           10 |                    0        |        1.63966e+07 |     1.59673e+07 |           -429250 |    83450           |      512700           |                          0.162766 |                 3.81777e+07 |                 2.17811e+07 | False                       |
| no_progress_5bars_mfe_lt1r  | 5 completed daily bars, MFE < 1.0R                     |        1851 |                    32 |             0.017288  |                      224 |            13 |                            0 |                           10 |                    0        |        1.63966e+07 |     1.5929e+07  |           -467550 |    93200           |      560750           |                          0.166206 |                 3.81777e+07 |                 2.17811e+07 | False                       |
| no_progress_3bars_mfe_lt05r | 3 completed daily bars, MFE < 0.5R                     |        1851 |                    29 |             0.0156672 |                      224 |            13 |                            4 |                            5 |                    0.307692 |        1.63966e+07 |     1.57169e+07 |           -679710 |   181680           |      861390           |                          0.210915 |                 3.81777e+07 |                 2.17811e+07 | False                       |
| giveback_2r_to_underwater   | After MFE >= 2R, exit if EOD PnL turns negative        |        1851 |                   249 |             0.134522  |                      224 |            13 |                            8 |                            4 |                    0.615385 |        1.63966e+07 |     1.57125e+07 |           -684035 |        1.13054e+06 |           1.81458e+06 |                          0.623034 |                 3.81777e+07 |                 2.17811e+07 | False                       |

## Variant By Start

| variant                     | variant_label                                          | requested_start_month   |   lot_count |   triggered_lot_count |     original_pnl |        proxy_pnl |   proxy_delta |   loss_reduced |   gain_sacrificed |   path_missing_lot_count |
|:----------------------------|:-------------------------------------------------------|:------------------------|------------:|----------------------:|-----------------:|-----------------:|--------------:|---------------:|------------------:|-------------------------:|
| giveback_2r_to_underwater   | After MFE >= 2R, exit if EOD PnL turns negative        | 2020-01                 |         322 |                    42 |      6.64435e+06 |      6.28129e+06 |       -363065 |         421665 |            784730 |                       37 |
| giveback_2r_to_underwater   | After MFE >= 2R, exit if EOD PnL turns negative        | 2020-07                 |         297 |                    42 |      5.33488e+06 |      5.03507e+06 |       -299810 |         351770 |            651580 |                       24 |
| giveback_2r_to_underwater   | After MFE >= 2R, exit if EOD PnL turns negative        | 2021-01                 |         247 |                    35 |      2.51854e+06 |      2.45455e+06 |        -63990 |         197490 |            261480 |                       15 |
| giveback_2r_to_underwater   | After MFE >= 2R, exit if EOD PnL turns negative        | 2021-07                 |         210 |                    34 | 417820           | 389180           |        -28640 |          37580 |             66220 |                       15 |
| giveback_2r_to_underwater   | After MFE >= 2R, exit if EOD PnL turns negative        | 2022-01                 |         158 |                    22 | 197069           | 200099           |          3030 |          16220 |             13190 |                       14 |
| giveback_2r_to_underwater   | After MFE >= 2R, exit if EOD PnL turns negative        | 2022-07                 |         141 |                    22 | 349674           | 358054           |          8380 |          30560 |             22180 |                       15 |
| giveback_2r_to_underwater   | After MFE >= 2R, exit if EOD PnL turns negative        | 2023-01                 |         122 |                    16 | 211619           | 224209           |         12590 |          16930 |              4340 |                       15 |
| giveback_2r_to_underwater   | After MFE >= 2R, exit if EOD PnL turns negative        | 2023-07                 |         116 |                    14 | 304935           | 322525           |         17590 |          23260 |              5670 |                       16 |
| giveback_2r_to_underwater   | After MFE >= 2R, exit if EOD PnL turns negative        | 2024-01                 |          89 |                     9 | 205629           | 214269           |          8640 |          11820 |              3180 |                       14 |
| giveback_2r_to_underwater   | After MFE >= 2R, exit if EOD PnL turns negative        | 2024-07                 |          58 |                     6 |  89342.8         |  99422.8         |         10080 |          11490 |              1410 |                       14 |
| giveback_2r_to_underwater   | After MFE >= 2R, exit if EOD PnL turns negative        | 2025-01                 |          44 |                     4 |  59717.4         |  67067.4         |          7350 |           7560 |               210 |                       16 |
| giveback_2r_to_underwater   | After MFE >= 2R, exit if EOD PnL turns negative        | 2025-07                 |          33 |                     3 |  57622.4         |  61432.4         |          3810 |           4200 |               390 |                       16 |
| giveback_2r_to_underwater   | After MFE >= 2R, exit if EOD PnL turns negative        | 2026-01                 |          14 |                     0 |   5371.6         |   5371.6         |             0 |              0 |                 0 |                       13 |
| no_progress_3bars_mfe_lt05r | 3 completed daily bars, MFE < 0.5R                     | 2020-01                 |         322 |                     6 |      6.64435e+06 |      6.3509e+06  |       -293450 |          62550 |            356000 |                       37 |
| no_progress_3bars_mfe_lt05r | 3 completed daily bars, MFE < 0.5R                     | 2020-07                 |         297 |                     5 |      5.33488e+06 |      5.07434e+06 |       -260540 |          50750 |            311290 |                       24 |
| no_progress_3bars_mfe_lt05r | 3 completed daily bars, MFE < 0.5R                     | 2021-01                 |         247 |                     4 |      2.51854e+06 |      2.39147e+06 |       -127070 |          21050 |            148120 |                       15 |
| no_progress_3bars_mfe_lt05r | 3 completed daily bars, MFE < 0.5R                     | 2021-07                 |         210 |                     4 | 417820           | 404340           |        -13480 |          30620 |             44100 |                       15 |
| no_progress_3bars_mfe_lt05r | 3 completed daily bars, MFE < 0.5R                     | 2022-01                 |         158 |                     3 | 197069           | 210219           |         13150 |          13710 |               560 |                       14 |
| no_progress_3bars_mfe_lt05r | 3 completed daily bars, MFE < 0.5R                     | 2022-07                 |         141 |                     1 | 349674           | 350424           |           750 |            750 |                 0 |                       15 |
| no_progress_3bars_mfe_lt05r | 3 completed daily bars, MFE < 0.5R                     | 2023-01                 |         122 |                     2 | 211619           | 212009           |           390 |            750 |               360 |                       15 |
| no_progress_3bars_mfe_lt05r | 3 completed daily bars, MFE < 0.5R                     | 2023-07                 |         116 |                     3 | 304935           | 304725           |          -210 |            750 |               960 |                       16 |
| no_progress_3bars_mfe_lt05r | 3 completed daily bars, MFE < 0.5R                     | 2024-01                 |          89 |                     1 | 205629           | 206379           |           750 |            750 |                 0 |                       14 |
| no_progress_3bars_mfe_lt05r | 3 completed daily bars, MFE < 0.5R                     | 2024-07                 |          58 |                     0 |  89342.8         |  89342.8         |             0 |              0 |                 0 |                       14 |
| no_progress_3bars_mfe_lt05r | 3 completed daily bars, MFE < 0.5R                     | 2025-01                 |          44 |                     0 |  59717.4         |  59717.4         |             0 |              0 |                 0 |                       16 |
| no_progress_3bars_mfe_lt05r | 3 completed daily bars, MFE < 0.5R                     | 2025-07                 |          33 |                     0 |  57622.4         |  57622.4         |             0 |              0 |                 0 |                       16 |
| no_progress_3bars_mfe_lt05r | 3 completed daily bars, MFE < 0.5R                     | 2026-01                 |          14 |                     0 |   5371.6         |   5371.6         |             0 |              0 |                 0 |                       13 |
| no_progress_5bars_mfe_lt1r  | 5 completed daily bars, MFE < 1.0R                     | 2020-01                 |         322 |                     7 |      6.64435e+06 |      6.46784e+06 |       -176515 |          42390 |            218905 |                       37 |
| no_progress_5bars_mfe_lt1r  | 5 completed daily bars, MFE < 1.0R                     | 2020-07                 |         297 |                     5 |      5.33488e+06 |      5.1887e+06  |       -146185 |          34410 |            180595 |                       24 |
| no_progress_5bars_mfe_lt1r  | 5 completed daily bars, MFE < 1.0R                     | 2021-01                 |         247 |                     3 |      2.51854e+06 |      2.44833e+06 |        -70205 |          13400 |             83605 |                       15 |
| no_progress_5bars_mfe_lt1r  | 5 completed daily bars, MFE < 1.0R                     | 2021-07                 |         210 |                     4 | 417820           | 400670           |        -17150 |           2000 |             19150 |                       15 |
| no_progress_5bars_mfe_lt1r  | 5 completed daily bars, MFE < 1.0R                     | 2022-01                 |         158 |                     4 | 197069           | 188494           |         -8575 |           1000 |              9575 |                       14 |
| no_progress_5bars_mfe_lt1r  | 5 completed daily bars, MFE < 1.0R                     | 2022-07                 |         141 |                     2 | 349674           | 336259           |        -13415 |              0 |             13415 |                       15 |
| no_progress_5bars_mfe_lt1r  | 5 completed daily bars, MFE < 1.0R                     | 2023-01                 |         122 |                     2 | 211619           | 202944           |         -8675 |              0 |              8675 |                       15 |
| no_progress_5bars_mfe_lt1r  | 5 completed daily bars, MFE < 1.0R                     | 2023-07                 |         116 |                     2 | 304935           | 293100           |        -11835 |              0 |             11835 |                       16 |
| no_progress_5bars_mfe_lt1r  | 5 completed daily bars, MFE < 1.0R                     | 2024-01                 |          89 |                     2 | 205629           | 196954           |         -8675 |              0 |              8675 |                       14 |
| no_progress_5bars_mfe_lt1r  | 5 completed daily bars, MFE < 1.0R                     | 2024-07                 |          58 |                     1 |  89342.8         |  83022.8         |         -6320 |              0 |              6320 |                       14 |
| no_progress_5bars_mfe_lt1r  | 5 completed daily bars, MFE < 1.0R                     | 2025-01                 |          44 |                     0 |  59717.4         |  59717.4         |             0 |              0 |                 0 |                       16 |
| no_progress_5bars_mfe_lt1r  | 5 completed daily bars, MFE < 1.0R                     | 2025-07                 |          33 |                     0 |  57622.4         |  57622.4         |             0 |              0 |                 0 |                       16 |
| no_progress_5bars_mfe_lt1r  | 5 completed daily bars, MFE < 1.0R                     | 2026-01                 |          14 |                     0 |   5371.6         |   5371.6         |             0 |              0 |                 0 |                       13 |
| underwater_5bars_mfe_lt1r   | 5 completed daily bars, MFE < 1.0R and current PnL < 0 | 2020-01                 |         322 |                     5 |      6.64435e+06 |      6.48201e+06 |       -162340 |          37190 |            199530 |                       37 |
| underwater_5bars_mfe_lt1r   | 5 completed daily bars, MFE < 1.0R and current PnL < 0 | 2020-07                 |         297 |                     3 |      5.33488e+06 |      5.20042e+06 |       -134460 |          29860 |            164320 |                       24 |
| underwater_5bars_mfe_lt1r   | 5 completed daily bars, MFE < 1.0R and current PnL < 0 | 2021-01                 |         247 |                     2 |      2.51854e+06 |      2.45531e+06 |        -63230 |          13400 |             76630 |                       15 |
| underwater_5bars_mfe_lt1r   | 5 completed daily bars, MFE < 1.0R and current PnL < 0 | 2021-07                 |         210 |                     3 | 417820           | 402220           |        -15600 |           2000 |             17600 |                       15 |
| underwater_5bars_mfe_lt1r   | 5 completed daily bars, MFE < 1.0R and current PnL < 0 | 2022-01                 |         158 |                     3 | 197069           | 189269           |         -7800 |           1000 |              8800 |                       14 |
| underwater_5bars_mfe_lt1r   | 5 completed daily bars, MFE < 1.0R and current PnL < 0 | 2022-07                 |         141 |                     1 | 349674           | 337034           |        -12640 |              0 |             12640 |                       15 |
| underwater_5bars_mfe_lt1r   | 5 completed daily bars, MFE < 1.0R and current PnL < 0 | 2023-01                 |         122 |                     1 | 211619           | 203719           |         -7900 |              0 |              7900 |                       15 |
| underwater_5bars_mfe_lt1r   | 5 completed daily bars, MFE < 1.0R and current PnL < 0 | 2023-07                 |         116 |                     1 | 304935           | 293875           |        -11060 |              0 |             11060 |                       16 |
| underwater_5bars_mfe_lt1r   | 5 completed daily bars, MFE < 1.0R and current PnL < 0 | 2024-01                 |          89 |                     1 | 205629           | 197729           |         -7900 |              0 |              7900 |                       14 |
| underwater_5bars_mfe_lt1r   | 5 completed daily bars, MFE < 1.0R and current PnL < 0 | 2024-07                 |          58 |                     1 |  89342.8         |  83022.8         |         -6320 |              0 |              6320 |                       14 |
| underwater_5bars_mfe_lt1r   | 5 completed daily bars, MFE < 1.0R and current PnL < 0 | 2025-01                 |          44 |                     0 |  59717.4         |  59717.4         |             0 |              0 |                 0 |                       16 |
| underwater_5bars_mfe_lt1r   | 5 completed daily bars, MFE < 1.0R and current PnL < 0 | 2025-07                 |          33 |                     0 |  57622.4         |  57622.4         |             0 |              0 |                 0 |                       16 |
| underwater_5bars_mfe_lt1r   | 5 completed daily bars, MFE < 1.0R and current PnL < 0 | 2026-01                 |          14 |                     0 |   5371.6         |   5371.6         |             0 |              0 |                 0 |                       13 |

## 结论

- 本阶段结论：`stage100_no_lot_proxy_candidate`。
- 候选数：`0`。
- 最优候选：``。
- 是否进入 true engine：`False`。
- 下一步：不进入 true engine；早期无进展/回吐 proxy 没有达到跨起点收益改善与右尾保留门槛。下一步优先做更底层的交易事件/退出原因分解，或回到独立收益腿数据补齐。

## 独立 agent 审查

- 审查 agent：`019f3228-5921-7272-a771-51a87655af97`。
- 审查结论：严重问题 0；当前已覆盖数据下 `candidate_rule_count=0` 可以复核成立，不建议进入 true engine。
- 置信度：`0.78`。主要扣分来自 `224/1851` 条 lot 缺少日线合约路径。
- 中等问题：每个 variant 的 `path_missing_lot_count=224`，缺失 lot 合计 PnL `-1,187,732.2`；这些是合约 CSV 文件缺失，不是空窗口。若要把 Stage100 作为最终否定证据，应先补齐或显式解释缺失路径后只读重跑；但当前结果不支持进入 true engine。
- 低级问题 1：`gain_sacrificed` 是所有负 delta/机会损失，不应全部表述为右尾损伤。审查复核 giveback 的 `gain_sacrificed=1,814,580`，其中赢家牺牲 `1,382,760`、亏损恶化 `431,820`。
- 低级问题 2：3/5 bars 规则当前使用 `len(path) > bar_count`，等价于“第 N 根 EOD 后原始交易仍存续才可触发”。审查额外复核 exact 3-bar 样本若纳入会让 3bar 版本更差，exact 5-bar 样本无满足 `MFE<1R`，不改变无候选结论。
- 关键复核：上游 Stage094 sha256 与 input_audit 一致；lot_proxy `7404=1851*4` 行；非触发行 `proxy_delta=0`；触发日期均在 entry/exit 窗口内；触发日 close 重算 `proxy_pnl` 最大误差 `1.8e-12`；四个 proxy 逻辑输出层面一致。
- 结论写窄：Stage100 是“当前覆盖数据下无 lot-level proxy 候选”，不是字节级全覆盖的最终否定；补齐 224 条缺失路径前，不应把它当作正式路线关闭证据。

## 回测记录字段

- 期末权益/总收益/最大回撤/Sharpe/总滑点/总交易次数/胜率：本阶段不是新策略曲线，不新增这些汇总。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。只测试预声明 4 个生命周期 proxy，不按品种、方向、月份、坏窗口或小数阈值救参；但若继续扫 bar_count/MFE 阈值就会过拟合。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有但需换层
- 原因：lot-level 代理未证明早期退出能稳健改善，继续扫 bar_count/MFE 阈值会过拟合。

## 合入建议

- 是否更新本线 `LINE.md`：否，独立 agent 已审查但无可晋级候选；缺失路径问题先保留为后续数据补齐 TODO。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段无重要突破。
