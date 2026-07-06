# Stage094 Stage167 全路径入场状态 closed-lot 审计

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05 18:56 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读真实引擎复跑 + closed-lot outcome 审计
- 是否重要突破：否
- 是否触发A/B：否，本阶段不提出可合入候选

## 外部调研与判断

- 参考资料：trend-following signal filtering、robust trend following、trend filters。
- 我的判断：入场状态过滤只有在全路径 closed lots 上负期望稳定、且右尾牺牲少于亏损捕获时，才值得进入 proxy；不能从坏窗口亏损仓直接反推。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage094_stage167_closed_lot_entry_state_audit.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：预声明入场状态条件族；不新增正式交易参数。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01` 至 `2026-01` 逐半年起点，统一终点 `2026-06-30`。
- 账户规模：`150,000`
- 引擎口径：复用 Stage901/Stage167 official live C9 wrapper；额外用 Stage719 `_build_closed_lots` 生成每笔 closed-lot outcome。
- 成本口径：沿用 live wrapper trades 和 closed-lot 实现。
- 审计口径：只用入场前可见字段分组；不做产品/方向/日期黑名单；不生成订单。

## Run Summary

| requested_start_month   |   daily_rows |   trade_rows |   entry_risk_rows |   entry_candidate_rows |   closed_lot_rows |   closed_lot_realized_pnl |   order_api_calls | ctp_connected   |
|:------------------------|-------------:|-------------:|------------------:|-----------------------:|------------------:|--------------------------:|------------------:|:----------------|
| 2020-01                 |         1571 |          631 |               296 |                    839 |               322 |               6.64435e+06 |                 0 | False           |
| 2020-07                 |         1454 |          582 |               270 |                    789 |               297 |               5.33488e+06 |                 0 | False           |
| 2021-01                 |         1328 |          489 |               231 |                    733 |               247 |               2.51854e+06 |                 0 | False           |
| 2021-07                 |         1210 |          418 |               200 |                    675 |               210 |          417820           |                 0 | False           |
| 2022-01                 |         1085 |          315 |               154 |                    613 |               158 |          197069           |                 0 | False           |
| 2022-07                 |          968 |          281 |               136 |                    546 |               141 |          349674           |                 0 | False           |
| 2023-01                 |          843 |          243 |               117 |                    476 |               122 |          211619           |                 0 | False           |
| 2023-07                 |          725 |          229 |               109 |                    422 |               116 |          304935           |                 0 | False           |
| 2024-01                 |          601 |          178 |                86 |                    345 |                89 |          205629           |                 0 | False           |
| 2024-07                 |          484 |          117 |                57 |                    280 |                58 |           89342.8         |                 0 | False           |
| 2025-01                 |          359 |           88 |                42 |                    196 |                44 |           59717.4         |                 0 | False           |
| 2025-07                 |          242 |           66 |                32 |                    127 |                33 |           57622.4         |                 0 | False           |
| 2026-01                 |          116 |           29 |                15 |                     66 |                14 |            5371.6         |                 0 | False           |

## Condition Summary

| condition                                   | label                                 |   lot_count |   lot_share |   start_count |   negative_start_count |   negative_start_rate |   realized_pnl_sum |   realized_pnl_mean |   positive_pnl_sum |   negative_pnl_abs_sum |   loss_capture_share |   gain_sacrifice_share |   loss_minus_gain_share |   winner_rate |   median_r_multiple |   big_winner_count |   big_winner_pnl |   big_winner_pnl_share | candidate_rule_viable   |
|:--------------------------------------------|:--------------------------------------|------------:|------------:|--------------:|-----------------------:|----------------------:|-------------------:|--------------------:|-------------------:|-----------------------:|---------------------:|-----------------------:|------------------------:|--------------:|--------------------:|-------------------:|-----------------:|-----------------------:|:------------------------|
| cond_risk_multiplier_ge2                    | risk_multiplier >= 2                  |         639 |    0.345219 |            13 |                     12 |             0.923077  |       -1.47257e+06 |           -2304.49  |        9.37977e+06 |            1.08523e+07 |            0.498245  |              0.245687  |              0.252558   |      0.345853 |           -0.432039 |                 47 |      4.26532e+06 |             0.232858   | True                    |
| cond_dd30_and_risk_multiplier_ge2           | DD>=30% and risk_multiplier>=2        |         190 |    0.102647 |            12 |                     10 |             0.833333  |       -1.21103e+06 |           -6373.86  |        1.64113e+06 |            2.85216e+06 |            0.130947  |              0.0429866 |              0.08796    |      0.352632 |           -0.322224 |                  6 | 100180           |             0.00546916 | True                    |
| cond_breakout                               | breakout                              |         556 |    0.300378 |            13 |                     10 |             0.769231  |   992624           |            1785.29  |        8.59876e+06 |            7.60614e+06 |            0.349208  |              0.22523   |              0.123978   |      0.359712 |           -0.322224 |                 24 |      2.51683e+06 |             0.137402   | False                   |
| cond_portfolio_dd_ge30pct                   | portfolio drawdown >= 30%             |         539 |    0.291194 |            12 |                      9 |             0.75      |   366082           |             679.187 |        6.94994e+06 |            6.58386e+06 |            0.302274  |              0.182042  |              0.120232   |      0.393321 |           -0.277778 |                 16 |      1.07672e+06 |             0.0587818  | False                   |
| cond_dd30_and_selected_volume_gt1           | DD>=30% and selected_volume>1         |         508 |    0.274446 |            12 |                      6 |             0.5       |   411137           |             809.324 |        6.93992e+06 |            6.52879e+06 |            0.299745  |              0.18178   |              0.117966   |      0.409449 |           -0.25     |                 16 |      1.07672e+06 |             0.0587818  | False                   |
| cond_rsi_exhaustion_zone                    | RSI exhaustion: long>=75 or short<=25 |         502 |    0.271205 |            13 |                      3 |             0.230769  |        2.93055e+06 |            5837.74  |        9.02105e+06 |            6.0905e+06  |            0.279623  |              0.236291  |              0.0433321  |      0.422311 |           -0.277778 |                 50 |      4.84634e+06 |             0.264578   | False                   |
| cond_loss_streak_ge3                        | loss_streak >= 3                      |         355 |    0.191788 |            13 |                      1 |             0.0769231 |        2.22146e+06 |            6257.62  |        7.36339e+06 |            5.14193e+06 |            0.236073  |              0.192872  |              0.0432015  |      0.374648 |           -0.307692 |                 33 |      5.70016e+06 |             0.311191   | False                   |
| cond_rsi_exhaustion_and_selected_volume_gt1 | RSI exhaustion and selected_volume>1  |         438 |    0.236629 |            13 |                      3 |             0.230769  |        2.94596e+06 |            6725.93  |        8.91953e+06 |            5.97357e+06 |            0.274255  |              0.233632  |              0.0406226  |      0.442922 |           -0.193548 |                 50 |      4.84634e+06 |             0.264578   | False                   |
| cond_selected_volume_gt1                    | selected_volume > 1                   |        1550 |    0.837385 |            13 |                      0 |             0         |        1.47109e+07 |            9490.92  |        3.54397e+07 |            2.07287e+07 |            0.951684  |              0.928282  |              0.0234017  |      0.44129  |           -0.25     |                146 |      1.82014e+07 |             0.993675   | False                   |
| cond_recovery_sleeve                        | recovery sleeve applied               |           0 |    0        |             0 |                      0 |           nan         |        0           |             nan     |        0           |            0           |            0         |              0         |              0          |    nan        |          nan        |                  0 |      0           |           nan          | False                   |
| cond_streak_recovery                        | streak recovery applied               |           0 |    0        |             0 |                      0 |           nan         |        0           |             nan     |        0           |            0           |            0         |              0         |              0          |    nan        |          nan        |                  0 |      0           |           nan          | False                   |
| cond_stop_distance_ge2pct                   | entry stop distance >= 2%             |         316 |    0.170719 |            13 |                      2 |             0.153846  |        3.05097e+06 |            9654.98  |        6.99514e+06 |            3.94416e+06 |            0.181082  |              0.183226  |             -0.00214401 |      0.515823 |            0.11564  |                 21 |      2.32582e+06 |             0.126975   | False                   |
| cond_ai_rank_1_8                            | AI rank 1-8                           |        1301 |    0.702863 |            13 |                      0 |             0         |        1.33303e+07 |           10246.2   |        2.90306e+07 |            1.57003e+07 |            0.720822  |              0.760408  |             -0.0395862  |      0.419677 |           -0.304348 |                119 |      1.71021e+07 |             0.933661   | False                   |
| cond_ai_rank_1_8_and_selected_volume_gt1    | AI rank 1-8 and selected_volume > 1   |        1137 |    0.614263 |            13 |                      0 |             0         |        1.32876e+07 |           11686.5   |        2.87518e+07 |            1.54642e+07 |            0.709984  |              0.753105  |             -0.0431205  |      0.4292   |           -0.282326 |                111 |      1.70014e+07 |             0.928162   | False                   |
| cond_same_direction_corr_abs_ge05           | abs same-direction corr >= 0.5        |         157 |    0.084819 |            12 |                      5 |             0.416667  |        3.10934e+06 |           19804.7   |        4.56291e+06 |            1.45357e+06 |            0.0667355 |              0.119518  |             -0.0527822  |      0.579618 |            0.64595  |                 27 |      2.89005e+06 |             0.157778   | False                   |
| cond_ai_rank_5_8                            | AI rank 5-8                           |         647 |    0.349541 |            13 |                      0 |             0         |        8.92727e+06 |           13797.9   |        1.66794e+07 |            7.75217e+06 |            0.355913  |              0.43689   |             -0.0809772  |      0.446677 |           -0.287234 |                 56 |      9.61506e+06 |             0.524918   | False                   |
| cond_same_direction_active_ge1              | same-direction active count >= 1      |         602 |    0.32523  |            13 |                      0 |             0         |        9.29014e+06 |           15432.1   |        1.47247e+07 |            5.43454e+06 |            0.249507  |              0.385688  |             -0.136181   |      0.493355 |            0        |                 81 |      9.66742e+06 |             0.527777   | False                   |
| cond_active_positions_ge2                   | active_positions_before >= 2          |         339 |    0.183144 |            13 |                      3 |             0.230769  |        7.23176e+06 |           21332.6   |        9.338e+06   |            2.10624e+06 |            0.0967004 |              0.244593  |             -0.147893   |      0.589971 |            0.530303 |                 62 |      6.39318e+06 |             0.349025   | False                   |

## Condition By Start

| condition                                | label                               | requested_start_month   |   lot_count |   realized_pnl_sum |   positive_pnl_sum |   negative_pnl_abs_sum |   winner_rate |
|:-----------------------------------------|:------------------------------------|:------------------------|------------:|-------------------:|-------------------:|-----------------------:|--------------:|
| cond_active_positions_ge2                | active_positions_before >= 2        | 2020-01                 |          75 |        3.12747e+06 |        3.96481e+06 |       837342           |      0.573333 |
| cond_active_positions_ge2                | active_positions_before >= 2        | 2020-07                 |          67 |        2.55049e+06 |        3.25501e+06 |       704523           |      0.58209  |
| cond_active_positions_ge2                | active_positions_before >= 2        | 2021-01                 |          47 |   793818           |        1.14365e+06 |       349832           |      0.531915 |
| cond_active_positions_ge2                | active_positions_before >= 2        | 2021-07                 |          36 |   215030           |   289520           |        74490           |      0.555556 |
| cond_active_positions_ge2                | active_positions_before >= 2        | 2022-01                 |          27 |   108525           |   145540           |        37015           |      0.666667 |
| cond_active_positions_ge2                | active_positions_before >= 2        | 2022-07                 |          20 |   154350           |   186250           |        31900           |      0.6      |
| cond_active_positions_ge2                | active_positions_before >= 2        | 2023-01                 |          15 |    84155           |    96280           |        12125           |      0.666667 |
| cond_active_positions_ge2                | active_positions_before >= 2        | 2023-07                 |          21 |   125405           |   154420           |        29015           |      0.619048 |
| cond_active_positions_ge2                | active_positions_before >= 2        | 2024-01                 |          14 |    81510           |    88730           |         7220           |      0.714286 |
| cond_active_positions_ge2                | active_positions_before >= 2        | 2024-07                 |           7 |    -4050           |     5350           |         9400           |      0.571429 |
| cond_active_positions_ge2                | active_positions_before >= 2        | 2025-01                 |           4 |    -3950           |     2740           |         6690           |      0.5      |
| cond_active_positions_ge2                | active_positions_before >= 2        | 2025-07                 |           4 |    -3950           |     2740           |         6690           |      0.5      |
| cond_active_positions_ge2                | active_positions_before >= 2        | 2026-01                 |           2 |     2960           |     2960           |           -0           |      1        |
| cond_ai_rank_1_8                         | AI rank 1-8                         | 2020-01                 |         192 |        5.50883e+06 |        1.16866e+07 |            6.17776e+06 |      0.463542 |
| cond_ai_rank_1_8                         | AI rank 1-8                         | 2020-07                 |         189 |        4.39754e+06 |        9.5874e+06  |            5.18986e+06 |      0.465608 |
| cond_ai_rank_1_8                         | AI rank 1-8                         | 2021-01                 |         165 |        2.1653e+06  |        4.51946e+06 |            2.35416e+06 |      0.454545 |
| cond_ai_rank_1_8                         | AI rank 1-8                         | 2021-07                 |         150 |   354460           |   894060           |       539600           |      0.4      |
| cond_ai_rank_1_8                         | AI rank 1-8                         | 2022-01                 |         115 |   119839           |   385690           |       265851           |      0.391304 |
| cond_ai_rank_1_8                         | AI rank 1-8                         | 2022-07                 |         109 |   225594           |   577950           |       352356           |      0.385321 |
| cond_ai_rank_1_8                         | AI rank 1-8                         | 2023-01                 |          93 |   109009           |   307850           |       198841           |      0.387097 |
| cond_ai_rank_1_8                         | AI rank 1-8                         | 2023-07                 |          89 |   189365           |   431990           |       242625           |      0.393258 |
| cond_ai_rank_1_8                         | AI rank 1-8                         | 2024-01                 |          73 |   138679           |   288150           |       149471           |      0.383562 |
| cond_ai_rank_1_8                         | AI rank 1-8                         | 2024-07                 |          48 |    49932.8         |   145970           |        96037.2         |      0.375    |
| cond_ai_rank_1_8                         | AI rank 1-8                         | 2025-01                 |          37 |    37797.4         |    98305           |        60507.6         |      0.351351 |
| cond_ai_rank_1_8                         | AI rank 1-8                         | 2025-07                 |          28 |    28602.4         |    73360           |        44757.6         |      0.392857 |
| cond_ai_rank_1_8                         | AI rank 1-8                         | 2026-01                 |          13 |     5371.6         |    33850           |        28478.4         |      0.461538 |
| cond_ai_rank_1_8_and_selected_volume_gt1 | AI rank 1-8 and selected_volume > 1 | 2020-01                 |         191 |        5.50969e+06 |        1.16866e+07 |            6.1769e+06  |      0.465969 |
| cond_ai_rank_1_8_and_selected_volume_gt1 | AI rank 1-8 and selected_volume > 1 | 2020-07                 |         187 |        4.3997e+06  |        9.58726e+06 |            5.18756e+06 |      0.465241 |
| cond_ai_rank_1_8_and_selected_volume_gt1 | AI rank 1-8 and selected_volume > 1 | 2021-01                 |         164 |        2.16285e+06 |        4.517e+06   |            2.35416e+06 |      0.45122  |
| cond_ai_rank_1_8_and_selected_volume_gt1 | AI rank 1-8 and selected_volume > 1 | 2021-07                 |         122 |   376165           |   859830           |       483665           |      0.42623  |
| cond_ai_rank_1_8_and_selected_volume_gt1 | AI rank 1-8 and selected_volume > 1 | 2022-01                 |          91 |    74319           |   318300           |       243981           |      0.362637 |
| cond_ai_rank_1_8_and_selected_volume_gt1 | AI rank 1-8 and selected_volume > 1 | 2022-07                 |          86 |   239254           |   544770           |       305516           |      0.418605 |
| cond_ai_rank_1_8_and_selected_volume_gt1 | AI rank 1-8 and selected_volume > 1 | 2023-01                 |          72 |    82999.4         |   257420           |       174421           |      0.375    |
| cond_ai_rank_1_8_and_selected_volume_gt1 | AI rank 1-8 and selected_volume > 1 | 2023-07                 |          73 |   187825           |   403860           |       216035           |      0.410959 |
| cond_ai_rank_1_8_and_selected_volume_gt1 | AI rank 1-8 and selected_volume > 1 | 2024-01                 |          54 |   122294           |   249270           |       126976           |      0.37037  |
| cond_ai_rank_1_8_and_selected_volume_gt1 | AI rank 1-8 and selected_volume > 1 | 2024-07                 |          36 |    44832.8         |   129490           |        84657.2         |      0.361111 |
| cond_ai_rank_1_8_and_selected_volume_gt1 | AI rank 1-8 and selected_volume > 1 | 2025-01                 |          28 |    42977.4         |    91225           |        48247.6         |      0.392857 |
| cond_ai_rank_1_8_and_selected_volume_gt1 | AI rank 1-8 and selected_volume > 1 | 2025-07                 |          22 |    36422.4         |    72920           |        36497.6         |      0.454545 |
| cond_ai_rank_1_8_and_selected_volume_gt1 | AI rank 1-8 and selected_volume > 1 | 2026-01                 |          11 |     8221.6         |    33850           |        25628.4         |      0.545455 |
| cond_ai_rank_5_8                         | AI rank 5-8                         | 2020-01                 |          91 |        3.56004e+06 |        6.61178e+06 |            3.05174e+06 |      0.472527 |
| cond_ai_rank_5_8                         | AI rank 5-8                         | 2020-07                 |          90 |        2.87224e+06 |        5.4645e+06  |            2.59226e+06 |      0.466667 |
| cond_ai_rank_5_8                         | AI rank 5-8                         | 2021-01                 |          81 |        1.44721e+06 |        2.58708e+06 |            1.13988e+06 |      0.469136 |
| cond_ai_rank_5_8                         | AI rank 5-8                         | 2021-07                 |          74 |   244580           |   511070           |       266490           |      0.405405 |
| cond_ai_rank_5_8                         | AI rank 5-8                         | 2022-01                 |          59 |    73996.2         |   208220           |       134224           |      0.389831 |
| cond_ai_rank_5_8                         | AI rank 5-8                         | 2022-07                 |          54 |   197319           |   366190           |       168871           |      0.462963 |
| cond_ai_rank_5_8                         | AI rank 5-8                         | 2023-01                 |          48 |    94656.2         |   185870           |        91213.8         |      0.4375   |
| cond_ai_rank_5_8                         | AI rank 5-8                         | 2023-07                 |          47 |   156152           |   272980           |       116828           |      0.425532 |
| cond_ai_rank_5_8                         | AI rank 5-8                         | 2024-01                 |          40 |   121521           |   191980           |        70458.8         |      0.45     |
| cond_ai_rank_5_8                         | AI rank 5-8                         | 2024-07                 |          24 |    62250.8         |   112140           |        49889.2         |      0.458333 |
| cond_ai_rank_5_8                         | AI rank 5-8                         | 2025-01                 |          18 |    42135.8         |    76305           |        34169.2         |      0.388889 |
| cond_ai_rank_5_8                         | AI rank 5-8                         | 2025-07                 |          14 |    44510.8         |    66730           |        22219.2         |      0.5      |
| cond_ai_rank_5_8                         | AI rank 5-8                         | 2026-01                 |           7 |    10650           |    24580           |        13930           |      0.571429 |
| cond_breakout                            | breakout                            | 2020-01                 |         108 |   547464           |        3.65617e+06 |            3.10871e+06 |      0.435185 |
| cond_breakout                            | breakout                            | 2020-07                 |         101 |   514222           |        3.09871e+06 |            2.58449e+06 |      0.475248 |
| cond_breakout                            | breakout                            | 2021-01                 |          80 |   245971           |        1.37672e+06 |            1.13075e+06 |      0.425    |
| cond_breakout                            | breakout                            | 2021-07                 |          67 |   -15770.3         |   254300           |       270070           |      0.343284 |
| cond_breakout                            | breakout                            | 2022-01                 |          43 |   -80468.8         |    45780           |       126249           |      0.255814 |
| cond_breakout                            | breakout                            | 2022-07                 |          42 |   -70375.7         |    66530           |       136906           |      0.261905 |
| cond_breakout                            | breakout                            | 2023-01                 |          32 |   -31078.8         |    33850           |        64928.8         |      0.25     |
| cond_breakout                            | breakout                            | 2023-07                 |          32 |   -41788.4         |    36180           |        77968.4         |      0.25     |
| cond_breakout                            | breakout                            | 2024-01                 |          24 |   -14863.8         |    26800           |        41663.8         |      0.25     |
| cond_breakout                            | breakout                            | 2024-07                 |          11 |   -23539.2         |     2840           |        26379.2         |      0.181818 |
| cond_breakout                            | breakout                            | 2025-01                 |           9 |   -18669.2         |      440           |        19109.2         |      0.111111 |
| cond_breakout                            | breakout                            | 2025-07                 |           6 |   -14829.2         |      440           |        15269.2         |      0.166667 |
| cond_breakout                            | breakout                            | 2026-01                 |           1 |    -3650           |        0           |         3650           |      0        |
| cond_dd30_and_risk_multiplier_ge2        | DD>=30% and risk_multiplier>=2      | 2020-01                 |          25 |  -665323           |   430760           |            1.09608e+06 |      0.36     |
| cond_dd30_and_risk_multiplier_ge2        | DD>=30% and risk_multiplier>=2      | 2020-07                 |          27 |  -296011           |   608510           |       904521           |      0.407407 |
| cond_dd30_and_risk_multiplier_ge2        | DD>=30% and risk_multiplier>=2      | 2021-01                 |          28 |  -195669           |   270460           |       466129           |      0.357143 |
| cond_dd30_and_risk_multiplier_ge2        | DD>=30% and risk_multiplier>=2      | 2021-07                 |          27 |   -24115.1         |    74150           |        98265.1         |      0.333333 |
| cond_dd30_and_risk_multiplier_ge2        | DD>=30% and risk_multiplier>=2      | 2022-01                 |          17 |    37729           |    77590           |        39861           |      0.470588 |
| cond_dd30_and_risk_multiplier_ge2        | DD>=30% and risk_multiplier>=2      | 2022-07                 |          16 |    20953.7         |    81750           |        60796.3         |      0.5      |
| cond_dd30_and_risk_multiplier_ge2        | DD>=30% and risk_multiplier>=2      | 2023-01                 |           9 |   -28720.6         |     5210           |        33930.6         |      0.222222 |
| cond_dd30_and_risk_multiplier_ge2        | DD>=30% and risk_multiplier>=2      | 2023-07                 |           8 |    -9004.8         |    35900           |        44904.8         |      0.25     |
| cond_dd30_and_risk_multiplier_ge2        | DD>=30% and risk_multiplier>=2      | 2024-01                 |           8 |    -3281           |    28720           |        32001           |      0.25     |
| cond_dd30_and_risk_multiplier_ge2        | DD>=30% and risk_multiplier>=2      | 2024-07                 |           8 |    -6877.2         |    21540           |        28417.2         |      0.25     |
| cond_dd30_and_risk_multiplier_ge2        | DD>=30% and risk_multiplier>=2      | 2025-01                 |           9 |   -21777.6         |     3270           |        25047.6         |      0.222222 |
| cond_dd30_and_risk_multiplier_ge2        | DD>=30% and risk_multiplier>=2      | 2025-07                 |           8 |   -18937.6         |     3270           |        22207.6         |      0.25     |
| cond_dd30_and_risk_multiplier_ge2        | DD>=30% and risk_multiplier>=2      | 2026-01                 |           0 |        0           |        0           |            0           |    nan        |
| cond_dd30_and_selected_volume_gt1        | DD>=30% and selected_volume>1       | 2020-01                 |          68 |   -60002.6         |        2.47558e+06 |            2.53558e+06 |      0.411765 |
| cond_dd30_and_selected_volume_gt1        | DD>=30% and selected_volume>1       | 2020-07                 |          75 |   268944           |        2.41387e+06 |            2.14493e+06 |      0.453333 |
| cond_dd30_and_selected_volume_gt1        | DD>=30% and selected_volume>1       | 2021-01                 |          79 |   205191           |        1.27118e+06 |            1.06598e+06 |      0.443038 |
| cond_dd30_and_selected_volume_gt1        | DD>=30% and selected_volume>1       | 2021-07                 |          62 |   -16090.1         |   205590           |       221680           |      0.370968 |
| cond_dd30_and_selected_volume_gt1        | DD>=30% and selected_volume>1       | 2022-01                 |          42 |    37999           |   125080           |        87081           |      0.428571 |
| cond_dd30_and_selected_volume_gt1        | DD>=30% and selected_volume>1       | 2022-07                 |          42 |     3963.7         |   142530           |       138566           |      0.428571 |
| cond_dd30_and_selected_volume_gt1        | DD>=30% and selected_volume>1       | 2023-01                 |          26 |    -1170.6         |    59930           |        61100.6         |      0.346154 |
| cond_dd30_and_selected_volume_gt1        | DD>=30% and selected_volume>1       | 2023-07                 |          26 |   -10464.8         |    82910           |        93374.8         |      0.346154 |
| cond_dd30_and_selected_volume_gt1        | DD>=30% and selected_volume>1       | 2024-01                 |          23 |    -4181           |    56340           |        60521           |      0.347826 |
| cond_dd30_and_selected_volume_gt1        | DD>=30% and selected_volume>1       | 2024-07                 |          21 |     1032.8         |    46600           |        45567.2         |      0.380952 |
| cond_dd30_and_selected_volume_gt1        | DD>=30% and selected_volume>1       | 2025-01                 |          23 |   -15167.6         |    24330           |        39497.6         |      0.391304 |
| cond_dd30_and_selected_volume_gt1        | DD>=30% and selected_volume>1       | 2025-07                 |          21 |     1082.4         |    35990           |        34907.6         |      0.428571 |
| cond_dd30_and_selected_volume_gt1        | DD>=30% and selected_volume>1       | 2026-01                 |           0 |        0           |        0           |            0           |    nan        |
| cond_loss_streak_ge3                     | loss_streak >= 3                    | 2020-01                 |          48 |   731765           |        2.75508e+06 |            2.02332e+06 |      0.416667 |
| cond_loss_streak_ge3                     | loss_streak >= 3                    | 2020-07                 |          44 |   523935           |        2.22408e+06 |            1.70014e+06 |      0.409091 |
| cond_loss_streak_ge3                     | loss_streak >= 3                    | 2021-01                 |          35 |   235100           |        1.03494e+06 |       799835           |      0.342857 |
| cond_loss_streak_ge3                     | loss_streak >= 3                    | 2021-07                 |          48 |   122655           |   337930           |       215275           |      0.333333 |
| cond_loss_streak_ge3                     | loss_streak >= 3                    | 2022-01                 |          45 |    92482.8         |   196270           |       103787           |      0.377778 |
| cond_loss_streak_ge3                     | loss_streak >= 3                    | 2022-07                 |          31 |   130019           |   240550           |       110531           |      0.387097 |
| cond_loss_streak_ge3                     | loss_streak >= 3                    | 2023-01                 |          23 |    76316.2         |   123540           |        47223.8         |      0.304348 |
| cond_loss_streak_ge3                     | loss_streak >= 3                    | 2023-07                 |          22 |   147854           |   201820           |        53966.4         |      0.409091 |
| cond_loss_streak_ge3                     | loss_streak >= 3                    | 2024-01                 |          20 |   112053           |   144610           |        32557.2         |      0.45     |
| cond_loss_streak_ge3                     | loss_streak >= 3                    | 2024-07                 |          14 |    23332           |    45900           |        22568           |      0.357143 |
| cond_loss_streak_ge3                     | loss_streak >= 3                    | 2025-01                 |          12 |     4631.6         |    18950           |        14318.4         |      0.333333 |
| cond_loss_streak_ge3                     | loss_streak >= 3                    | 2025-07                 |           7 |     -719.2         |    10120           |        10839.2         |      0.142857 |
| cond_loss_streak_ge3                     | loss_streak >= 3                    | 2026-01                 |           6 |    22031.6         |    29610           |         7578.4         |      0.5      |
| cond_portfolio_dd_ge30pct                | portfolio drawdown >= 30%           | 2020-01                 |          68 |   -60002.6         |        2.47558e+06 |            2.53558e+06 |      0.411765 |
| cond_portfolio_dd_ge30pct                | portfolio drawdown >= 30%           | 2020-07                 |          75 |   268944           |        2.41387e+06 |            2.14493e+06 |      0.453333 |
| cond_portfolio_dd_ge30pct                | portfolio drawdown >= 30%           | 2021-01                 |          79 |   205191           |        1.27118e+06 |            1.06598e+06 |      0.443038 |
| cond_portfolio_dd_ge30pct                | portfolio drawdown >= 30%           | 2021-07                 |          70 |   -18565.1         |   215120           |       233685           |      0.371429 |
| cond_portfolio_dd_ge30pct                | portfolio drawdown >= 30%           | 2022-01                 |          46 |    33734           |   125570           |        91836           |      0.413043 |
| cond_portfolio_dd_ge30pct                | portfolio drawdown >= 30%           | 2022-07                 |          45 |    -5311.3         |   142530           |       147841           |      0.4      |
| cond_portfolio_dd_ge30pct                | portfolio drawdown >= 30%           | 2023-01                 |          27 |    -3750.6         |    59930           |        63680.6         |      0.333333 |
| cond_portfolio_dd_ge30pct                | portfolio drawdown >= 30%           | 2023-07                 |          26 |   -10464.8         |    82910           |        93374.8         |      0.346154 |
| cond_portfolio_dd_ge30pct                | portfolio drawdown >= 30%           | 2024-01                 |          25 |    -8361           |    56340           |        64701           |      0.32     |
| cond_portfolio_dd_ge30pct                | portfolio drawdown >= 30%           | 2024-07                 |          25 |    -5977.2         |    46600           |        52577.2         |      0.32     |
| cond_portfolio_dd_ge30pct                | portfolio drawdown >= 30%           | 2025-01                 |          27 |   -22177.6         |    24330           |        46507.6         |      0.333333 |
| cond_portfolio_dd_ge30pct                | portfolio drawdown >= 30%           | 2025-07                 |          26 |    -7177.6         |    35990           |        43167.6         |      0.346154 |
| cond_portfolio_dd_ge30pct                | portfolio drawdown >= 30%           | 2026-01                 |           0 |        0           |        0           |            0           |    nan        |
| cond_risk_multiplier_ge2                 | risk_multiplier >= 2                | 2020-01                 |         119 |  -496001           |        3.84882e+06 |            4.34482e+06 |      0.445378 |
| cond_risk_multiplier_ge2                 | risk_multiplier >= 2                | 2020-07                 |         113 |  -306025           |        3.2975e+06  |            3.60352e+06 |      0.451327 |
| cond_risk_multiplier_ge2                 | risk_multiplier >= 2                | 2021-01                 |          88 |  -228713           |        1.42605e+06 |            1.65476e+06 |      0.386364 |

## 结论

- 本阶段结论：`stage094_entry_state_guard_candidate_for_proxy`。
- 候选数：`2`。
- 最优候选：`cond_risk_multiplier_ge2`。
- 是否进入下一步：`False`。
- 下一步：先对 `cond_risk_multiplier_ge2` 做曲线/交易级 no-lookahead proxy，只有 proxy 保留右尾才允许 true engine。

## 回测记录字段

- closed-lot realized pnl：`16396571.3000`
- 总滑点/交易次数：本阶段未新增策略版本汇总曲线；详见 run summary 和 Stage167 baseline。
- 期末权益/总收益/最大回撤/Sharpe/胜率：本阶段不是新策略回测，保留 Stage167 baseline。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。只用预声明入场前字段做全样本 outcome 审计；没有按产品/方向/坏窗口黑名单或小数阈值救参。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有
- 原因：有候选但仍只是 ex-post lot outcome，需要先做 proxy 反事实。

## 合入建议

- 是否更新本线 `LINE.md`：否。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段无重要突破。

## 独立 Agent 审查

- agent：Gibbs `019f31ed-9db0-7ef0-98d5-88888cab41c6`
- 审查结论：同意只进入下一步无前视 proxy；不同意直接进入 true engine，更不能上线。
- 置信度：总体 `0.64`；对“不能直接 true engine/上线”的置信度高；对这两个条件有稳定交易价值的置信度约 `0.45`。
- 主要风险：`risk_multiplier>=2` 本质是既有 sizing/风险恢复状态，不是独立信息源；13 个逐半年起点高度重叠；`risk_multiplier>=2` 在 2021 年右尾收益明显，直接 hard veto 可能误伤趋势右尾；closed-lot outcome 是事后归因，不是路径一致反事实。
- 口径修正：本记录里的“是否进入下一步：False”应理解为 `promote_to_true_engine=False`，不是“不进 proxy”。下一阶段优先审计 `DD>=30% and risk_multiplier>=2`，同时把全量 `risk_multiplier>=2` 作为上界/反证。
- 必补校验：entry-risk 匹配覆盖与错配抽样、去重后统计、时间切分、日级路径 proxy、2021 右尾误伤审计、与既有 OI/质量链路重叠检查。
