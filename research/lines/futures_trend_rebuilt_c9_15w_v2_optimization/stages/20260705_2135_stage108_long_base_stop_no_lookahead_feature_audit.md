# Stage108 long_base_stop 无前视状态可行性审计

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05 21:35 CST
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读 no-lookahead feature audit；不改策略、不跑 true engine
- 是否重要突破：否；未发现足够稳定的无前视识别条件
- 是否触发A/B：否，本阶段不是可合入策略；若后续进入真实引擎，已读取 `skills/version-ab-experiment/SKILL.md`

## 外部调研与判断

- 参考资料：Backtrader stop trading、Rob Carver dynamic trend following、pysystemtrade backtesting docs。
- 我的判断：Stage107 是事后机会，Stage108 必须回答触发日当时能不能识别 whipsaw。若不能，就停止 base_stop 延迟退出路线。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage108_long_base_stop_no_lookahead_feature_audit.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：主 horizon `3`；预声明状态 `['pretrend_positive', 'exit_close_above_ma20_prev', 'mild_exit_shock', 'whipsaw_core', 'profitable_base_stop', 'profitable_pretrend', 'not_deep_loss', 'quality_rank_top8']`；机制闸门固定为事件数/起点数/物理事件/exit-close PnL/正起点率/负正比/单事件占比/min representative。
- 修改参数：无正式策略参数。
- 删除参数：无。

## 审计参数

- Stage107 event panel：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage107_long_base_stop_post_exit_continuation_audit/rebuilt_c9_v2_stage107_long_base_stop_post_exit_continuation_audit_event_panel_stage107_long_base_stop_post_exit_continuation_audit_v2_reviewed_representative_sensitivity.csv.gz`
- Stage107 decision：`stage107_long_base_stop_post_exit_positive_but_representative_sensitive_followup_only`
- Stage096 positions：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage096_position_concentration_predictive_audit/rebuilt_c9_v2_stage096_position_concentration_predictive_audit_positions_stage096_position_concentration_predictive_audit_v1.csv.gz`
- true engine：未运行。
- 订单 API：`0`
- CTP：未连接。

## 结果摘要

- 决策：`stage108_no_lookahead_feature_not_sufficient_for_base_stop_delay`
- 候选规则数：`0`
- 最佳候选信号：`无`
- event rows：`282`
- 起点数：`13`
- 物理事件数：`47`
- 全样本 exit-close continuation：`5,116,880.00`
- 全样本 actual-fill continuation：`7,214,105.00`
- 预声明状态数：`8`

## Signal Summary

| signal_name                | signal_definition                                                     | selected_value   |   events |   start_count |   unique_physical_events |   symbol_count |   actual_fill_pnl_sum |   exit_close_pnl_sum |   exit_close_positive_sum |   exit_close_negative_abs_sum |   exit_close_negative_to_positive |   help_rate_exit_close |   help_rate_actual_fill |   positive_start_count |   positive_start_rate |   start_pnl_min |   start_pnl_median |    start_pnl_max |   top_event_positive_share |   mean_exit_ret_z |   mean_ret20_prev |   mean_exit_close_vs_ma20_prev |   exit_close_pnl_sum_proxy_first_start_representative_sum |   exit_close_pnl_sum_proxy_last_start_representative_sum |   exit_close_pnl_sum_proxy_min_representative_sum |   exit_close_pnl_sum_proxy_max_representative_sum |   exit_close_pnl_sum_proxy_mean_per_physical_key_sum |   share_of_all_exit_close_pnl | mechanism_gate_pass   |
|:---------------------------|:----------------------------------------------------------------------|:-----------------|---------:|--------------:|-------------------------:|---------------:|----------------------:|---------------------:|--------------------------:|------------------------------:|----------------------------------:|-----------------------:|------------------------:|-----------------------:|----------------------:|----------------:|-------------------:|-----------------:|---------------------------:|------------------:|------------------:|-------------------------------:|----------------------------------------------------------:|---------------------------------------------------------:|--------------------------------------------------:|--------------------------------------------------:|-----------------------------------------------------:|------------------------------:|:----------------------|
| not_deep_loss              | base_stop 平仓 R 倍数大于 -1，不是深亏止损。                          | True             |      153 |            13 |                       24 |             24 |           8.10967e+06 |          5.86898e+06 |               8.3594e+06  |                   2.49042e+06 |                          0.297919 |               0.588235 |                0.54902  |                     13 |             1         |           29270 |              94460 |      2.31471e+06 |                   0.140221 |         0.318763  |       0.0780225   |                    0.0536559   |                                               2.28573e+06 |                                                    54220 |                                 -851550           |                                       3.17218e+06 |                                             560893   |                      1.14698  | False                 |
| pretrend_positive          | 退出前一日收盘在 MA20 上方，MA20 五日前向上，且退出前 20 日收益为正。 | True             |      235 |            13 |                       36 |             33 |           7.27309e+06 |          4.99037e+06 |               9.4468e+06  |                   4.45643e+06 |                          0.47174  |               0.523404 |                0.480851 |                     13 |             1         |           29270 |              73670 |      1.95601e+06 |                   0.12408  |         0.103516  |       0.0880378   |                    0.0500201   |                                               1.92975e+06 |                                                    65640 |                                      -1.62396e+06 |                                       3.59945e+06 |                                             505119   |                      0.975276 | False                 |
| exit_close_above_ma20_prev | 触发日收盘仍在退出前 MA20 上方。                                      | True             |      217 |            13 |                       35 |             32 |           8.21084e+06 |          4.94032e+06 |               9.40577e+06 |                   4.46545e+06 |                          0.474756 |               0.562212 |                0.589862 |                     13 |             1         |           29270 |              77320 |      1.93355e+06 |                   0.124621 |         0.383819  |       0.0849252   |                    0.0565969   |                                               1.90664e+06 |                                                    46290 |                                      -1.64379e+06 |                                       3.5768e+06  |                                             458934   |                      0.965495 | False                 |
| mild_exit_shock            | 触发日 close-to-close 跌幅不超过 1.5 个退出前 20 日波动。             | True             |      267 |            13 |                       44 |             40 |           7.31861e+06 |          4.88704e+06 |               9.8304e+06  |                   4.94336e+06 |                          0.502865 |               0.505618 |                0.509363 |                     13 |             1         |           29270 |              73750 |      1.91946e+06 |                   0.119238 |         0.21189   |       0.0714392   |                    0.0434282   |                                               1.89255e+06 |                                                    73300 |                                      -1.8005e+06  |                                       3.74827e+06 |                                             477953   |                      0.955082 | False                 |
| whipsaw_core               | pretrend_positive + exit_close_above_ma20_prev + mild_exit_shock。    | True             |      192 |            13 |                       29 |             26 |           8.08496e+06 |          4.8112e+06  |               9.0969e+06  |                   4.2857e+06  |                          0.471117 |               0.578125 |                0.557292 |                     13 |             1         |           29270 |              77320 |      1.87056e+06 |                   0.128853 |         0.411708  |       0.0948286   |                    0.0620662   |                                               1.8443e+06  |                                                    23620 |                                      -1.60166e+06 |                                       3.44966e+06 |                                             416900   |                      0.94026  | False                 |
| quality_rank_top8          | 入场时 AI rank 在 1-8。                                               | True             |      202 |            13 |                       30 |             29 |           4.77605e+06 |          2.85502e+06 |               6.63589e+06 |                   3.78087e+06 |                          0.569761 |               0.5      |                0.475248 |                     13 |             1         |            6860 |              26440 |      1.16588e+06 |                   0.176639 |         0.153564  |       0.0705188   |                    0.046461    |                                               1.13962e+06 |                                                    64910 |                                      -1.35506e+06 |                                       2.55541e+06 |                                             355528   |                      0.557961 | False                 |
| profitable_base_stop       | base_stop 平仓本身仍为正收益，说明更像保护利润后的回撤。              | True             |       84 |            13 |                       15 |             15 |           2.60564e+06 |          1.91467e+06 |               2.41157e+06 |              496900           |                          0.206048 |               0.619048 |                0.583333 |                     11 |             0.846154  |            -970 |              15080 | 783230           |                   0.125064 |         0.166793  |       0.109382    |                    0.06713     |                                          767930           |                                                     6680 |                                 -162690           |                                  916620           |                                             229975   |                      0.374187 | False                 |
| profitable_pretrend        | profitable_base_stop + pretrend_positive。                            | True             |       75 |            13 |                       13 |             13 |           2.71702e+06 |          1.88372e+06 |               2.24942e+06 |              365700           |                          0.162575 |               0.626667 |                0.586667 |                     11 |             0.846154  |            -970 |              15080 | 771630           |                   0.134079 |         0.249035  |       0.118785    |                    0.0769986   |                                          756330           |                                                     7330 |                                 -108740           |                                  851720           |                                             230345   |                      0.368138 | False                 |
| profitable_pretrend        | profitable_base_stop + pretrend_positive。                            | False            |      207 |            13 |                       34 |             30 |           4.49709e+06 |          3.23316e+06 |               7.81376e+06 |                   4.5806e+06  |                          0.586222 |               0.458937 |                0.463768 |                     13 |             1         |           22410 |              57850 |      1.24453e+06 |                   0.150012 |         0.0347168 |       0.0569015   |                    0.0281848   |                                               1.23292e+06 |                                                    80150 |                                      -1.67866e+06 |                                       2.99435e+06 |                                             307100   |                    nan        | False                 |
| profitable_base_stop       | base_stop 平仓本身仍为正收益，说明更像保护利润后的回撤。              | False            |      198 |            13 |                       32 |             29 |           4.60847e+06 |          3.20221e+06 |               7.65161e+06 |                   4.4494e+06  |                          0.581499 |               0.454545 |                0.459596 |                     13 |             1         |           22410 |              57850 |      1.23293e+06 |                   0.153191 |         0.0598657 |       0.0580778   |                    0.0301527   |                                               1.22132e+06 |                                                    80800 |                                      -1.62471e+06 |                                       2.92945e+06 |                                             307470   |                    nan        | False                 |
| quality_rank_top8          | 入场时 AI rank 在 1-8。                                               | False            |       80 |            13 |                       17 |             15 |           2.43806e+06 |          2.26186e+06 |               3.42729e+06 |                   1.16543e+06 |                          0.340044 |               0.5125   |                0.55     |                     13 |             1         |           22410 |              42270 | 850280           |                   0.24847  |        -0.0644499 |       0.0805332   |                    0.0278004   |                                          849630           |                                                    22570 |                                 -432340           |                                       1.29066e+06 |                                             181917   |                    nan        | False                 |
| whipsaw_core               | pretrend_positive + exit_close_above_ma20_prev + mild_exit_shock。    | False            |       90 |            12 |                       18 |             18 |     -870850           |     305680           |          966280           |              660600           |                          0.683653 |               0.344444 |                0.366667 |                      5 |             0.416667  |           -7180 |              -1020 | 145600           |                   0.146231 |        -0.590932  |       0.0275596   |                   -0.0034172   |                                          144950           |                                                    63860 |                                 -185740           |                                  396410           |                                             120545   |                    nan        | False                 |
| mild_exit_shock            | 触发日 close-to-close 跌幅不超过 1.5 个退出前 20 日波动。             | False            |       15 |             8 |                        3 |              3 |     -104500           |     229840           |          232780           |                2940           |                          0.01263  |               0.466667 |                0.266667 |                      4 |             0.5       |             -80 |               3730 |  96700           |                   0.391786 |        -2.04737   |       0.107546    |                    0.000922056 |                                           96700           |                                                    14180 |                                   13100           |                                   97800           |                                              59492.5 |                    nan        | False                 |
| exit_close_above_ma20_prev | 触发日收盘仍在退出前 MA20 上方。                                      | False            |       65 |            12 |                       12 |             12 |     -996730           |     176560           |          657410           |              480850           |                          0.731431 |               0.307692 |                0.184615 |                      5 |             0.416667  |           -8300 |              -1020 |  82610           |                   0.214934 |        -0.883456  |       0.034749    |                   -0.0103441   |                                           82610           |                                                    41190 |                                 -143610           |                                  269270           |                                              78510.9 |                    nan        | False                 |
| pretrend_positive          | 退出前一日收盘在 MA20 上方，MA20 五日前向上，且退出前 20 日收益为正。 | False            |       47 |             9 |                       11 |             11 |      -58980           |     126510           |          616380           |              489870           |                          0.794753 |               0.404255 |                0.574468 |                      4 |             0.444444  |           -3020 |                  0 |  60150           |                   0.229242 |         0.0327187 |      -3.04299e-05 |                   -0.00309726  |                                           59500           |                                                    21840 |                                 -163440           |                                  246620           |                                              32326   |                    nan        | False                 |
| not_deep_loss              | base_stop 平仓 R 倍数大于 -1，不是深亏止损。                          | False            |      129 |            12 |                       23 |             21 |     -895565           |    -752100           |               1.70378e+06 |                   2.45588e+06 |                          1.44143  |               0.403101 |                0.434109 |                      1 |             0.0833333 |         -298550 |             -18920 |    630           |                   0.101515 |        -0.177571  |       0.0678295   |                    0.0263551   |                                         -296480           |                                                    33260 |                                 -935850           |                                  673890           |                                             -23447.5 |                    nan        | False                 |

## By Start Signal

| signal_name                | requested_start_month   | selected_value   |   events |   exit_close_pnl_sum |   help_rate_exit_close |   symbol_count |
|:---------------------------|:------------------------|:-----------------|---------:|---------------------:|-----------------------:|---------------:|
| exit_close_above_ma20_prev | 2020-01                 | False            |       12 |      82610           |               0.5      |             12 |
| exit_close_above_ma20_prev | 2020-01                 | True             |       30 |          1.93355e+06 |               0.566667 |             29 |
| exit_close_above_ma20_prev | 2020-07                 | False            |       12 |      75900           |               0.5      |             12 |
| exit_close_above_ma20_prev | 2020-07                 | True             |       30 |          1.58533e+06 |               0.566667 |             29 |
| exit_close_above_ma20_prev | 2021-01                 | False            |       10 |      32650           |               0.4      |             10 |
| exit_close_above_ma20_prev | 2021-01                 | True             |       27 |     764380           |               0.592593 |             26 |
| exit_close_above_ma20_prev | 2021-07                 | False            |        8 |       1770           |               0.25     |              8 |
| exit_close_above_ma20_prev | 2021-07                 | True             |       29 |     135030           |               0.551724 |             27 |
| exit_close_above_ma20_prev | 2022-01                 | False            |        6 |       4820           |               0.333333 |              6 |
| exit_close_above_ma20_prev | 2022-01                 | True             |       20 |      45550           |               0.55     |             19 |
| exit_close_above_ma20_prev | 2022-07                 | False            |        4 |      -8300           |               0        |              4 |
| exit_close_above_ma20_prev | 2022-07                 | True             |       16 |      98790           |               0.5625   |             16 |
| exit_close_above_ma20_prev | 2023-01                 | False            |        3 |      -2610           |               0        |              3 |
| exit_close_above_ma20_prev | 2023-01                 | True             |       15 |      86960           |               0.6      |             14 |
| exit_close_above_ma20_prev | 2023-07                 | False            |        3 |      -3650           |               0        |              3 |
| exit_close_above_ma20_prev | 2023-07                 | True             |       14 |      77320           |               0.5      |             14 |
| exit_close_above_ma20_prev | 2024-01                 | False            |        2 |      -2550           |               0        |              2 |
| exit_close_above_ma20_prev | 2024-01                 | True             |       12 |      47790           |               0.5      |             12 |
| exit_close_above_ma20_prev | 2024-07                 | False            |        2 |      -2040           |               0        |              2 |
| exit_close_above_ma20_prev | 2024-07                 | True             |        7 |      51010           |               0.571429 |              7 |
| exit_close_above_ma20_prev | 2025-01                 | False            |        2 |      -2040           |               0        |              2 |
| exit_close_above_ma20_prev | 2025-01                 | True             |        7 |      42670           |               0.571429 |              7 |
| exit_close_above_ma20_prev | 2025-07                 | False            |        1 |          0           |               0        |              1 |
| exit_close_above_ma20_prev | 2025-07                 | True             |        7 |      42670           |               0.571429 |              7 |
| exit_close_above_ma20_prev | 2026-01                 | True             |        3 |      29270           |               0.666667 |              3 |
| mild_exit_shock            | 2020-01                 | False            |        3 |      96700           |               0.666667 |              3 |
| mild_exit_shock            | 2020-01                 | True             |       39 |          1.91946e+06 |               0.538462 |             37 |
| mild_exit_shock            | 2020-07                 | False            |        3 |      81700           |               0.666667 |              3 |
| mild_exit_shock            | 2020-07                 | True             |       39 |          1.57953e+06 |               0.538462 |             37 |
| mild_exit_shock            | 2021-01                 | False            |        3 |      44200           |               0.666667 |              3 |
| mild_exit_shock            | 2021-01                 | True             |       34 |     752830           |               0.529412 |             32 |
| mild_exit_shock            | 2021-07                 | False            |        2 |       7520           |               0.5      |              2 |
| mild_exit_shock            | 2021-07                 | True             |       35 |     129280           |               0.485714 |             32 |
| mild_exit_shock            | 2022-01                 | False            |        1 |        -60           |               0        |              1 |
| mild_exit_shock            | 2022-01                 | True             |       25 |      50430           |               0.52     |             23 |
| mild_exit_shock            | 2022-07                 | False            |        1 |        -80           |               0        |              1 |
| mild_exit_shock            | 2022-07                 | True             |       19 |      90570           |               0.473684 |             19 |
| mild_exit_shock            | 2023-01                 | False            |        1 |        -60           |               0        |              1 |
| mild_exit_shock            | 2023-01                 | True             |       17 |      84410           |               0.529412 |             16 |
| mild_exit_shock            | 2023-07                 | False            |        1 |        -80           |               0        |              1 |
| mild_exit_shock            | 2023-07                 | True             |       16 |      73750           |               0.4375   |             16 |
| mild_exit_shock            | 2024-01                 | True             |       14 |      45240           |               0.428571 |             14 |
| mild_exit_shock            | 2024-07                 | True             |        9 |      48970           |               0.444444 |              9 |
| mild_exit_shock            | 2025-01                 | True             |        9 |      40630           |               0.444444 |              9 |
| mild_exit_shock            | 2025-07                 | True             |        8 |      42670           |               0.5      |              8 |
| mild_exit_shock            | 2026-01                 | True             |        3 |      29270           |               0.666667 |              3 |
| not_deep_loss              | 2020-01                 | False            |       21 |    -298550           |               0.47619  |             20 |
| not_deep_loss              | 2020-01                 | True             |       21 |          2.31471e+06 |               0.619048 |             21 |
| not_deep_loss              | 2020-07                 | False            |       22 |    -229930           |               0.454545 |             21 |
| not_deep_loss              | 2020-07                 | True             |       20 |          1.89116e+06 |               0.65     |             20 |
| not_deep_loss              | 2021-01                 | False            |       18 |    -111300           |               0.444444 |             17 |
| not_deep_loss              | 2021-01                 | True             |       19 |     908330           |               0.631579 |             19 |
| not_deep_loss              | 2021-07                 | False            |       19 |     -18460           |               0.421053 |             18 |
| not_deep_loss              | 2021-07                 | True             |       18 |     155260           |               0.555556 |             18 |
| not_deep_loss              | 2022-01                 | False            |       13 |     -19380           |               0.384615 |             12 |
| not_deep_loss              | 2022-01                 | True             |       13 |      69750           |               0.615385 |             13 |
| not_deep_loss              | 2022-07                 | False            |        9 |     -27520           |               0.333333 |              9 |
| not_deep_loss              | 2022-07                 | True             |       11 |     118010           |               0.545455 |             11 |
| not_deep_loss              | 2023-01                 | False            |        8 |     -12860           |               0.375    |              7 |
| not_deep_loss              | 2023-01                 | True             |       10 |      97210           |               0.6      |             10 |
| not_deep_loss              | 2023-07                 | False            |        6 |     -20790           |               0.166667 |              6 |
| not_deep_loss              | 2023-07                 | True             |       11 |      94460           |               0.545455 |             11 |
| not_deep_loss              | 2024-01                 | False            |        5 |     -11120           |               0.2      |              5 |
| not_deep_loss              | 2024-01                 | True             |        9 |      56360           |               0.555556 |              9 |
| not_deep_loss              | 2024-07                 | False            |        3 |      -1410           |               0.333333 |              3 |
| not_deep_loss              | 2024-07                 | True             |        6 |      50380           |               0.5      |              6 |
| not_deep_loss              | 2025-01                 | False            |        3 |      -1410           |               0.333333 |              3 |
| not_deep_loss              | 2025-01                 | True             |        6 |      42040           |               0.5      |              6 |
| not_deep_loss              | 2025-07                 | False            |        2 |        630           |               0.5      |              2 |
| not_deep_loss              | 2025-07                 | True             |        6 |      42040           |               0.5      |              6 |
| not_deep_loss              | 2026-01                 | True             |        3 |      29270           |               0.666667 |              3 |
| pretrend_positive          | 2020-01                 | False            |       10 |      60150           |               0.5      |             10 |
| pretrend_positive          | 2020-01                 | True             |       32 |          1.95601e+06 |               0.5625   |             31 |
| pretrend_positive          | 2020-07                 | False            |       11 |      50340           |               0.454545 |             11 |
| pretrend_positive          | 2020-07                 | True             |       31 |          1.61089e+06 |               0.580645 |             30 |
| pretrend_positive          | 2021-01                 | False            |        8 |      12030           |               0.375    |              8 |
| pretrend_positive          | 2021-01                 | True             |       29 |     785000           |               0.586207 |             28 |
| pretrend_positive          | 2021-07                 | False            |        8 |       -420           |               0.375    |              8 |
| pretrend_positive          | 2021-07                 | True             |       29 |     137220           |               0.517241 |             27 |
| pretrend_positive          | 2022-01                 | False            |        4 |       7430           |               0.5      |              4 |
| pretrend_positive          | 2022-01                 | True             |       22 |      42940           |               0.5      |             21 |
| pretrend_positive          | 2022-07                 | False            |        3 |      -3020           |               0.333333 |              3 |
| pretrend_positive          | 2022-07                 | True             |       17 |      93510           |               0.470588 |             17 |
| pretrend_positive          | 2023-01                 | False            |        1 |          0           |               0        |              1 |
| pretrend_positive          | 2023-01                 | True             |       17 |      84350           |               0.529412 |             16 |
| pretrend_positive          | 2023-07                 | False            |        1 |          0           |               0        |              1 |
| pretrend_positive          | 2023-07                 | True             |       16 |      73670           |               0.4375   |             16 |
| pretrend_positive          | 2024-01                 | False            |        1 |          0           |               0        |              1 |
| pretrend_positive          | 2024-01                 | True             |       13 |      45240           |               0.461538 |             13 |
| pretrend_positive          | 2024-07                 | True             |        9 |      48970           |               0.444444 |              9 |
| pretrend_positive          | 2025-01                 | True             |        9 |      40630           |               0.444444 |              9 |
| pretrend_positive          | 2025-07                 | True             |        8 |      42670           |               0.5      |              8 |
| pretrend_positive          | 2026-01                 | True             |        3 |      29270           |               0.666667 |              3 |
| profitable_base_stop       | 2020-01                 | False            |       29 |          1.23293e+06 |               0.517241 |             28 |
| profitable_base_stop       | 2020-01                 | True             |       13 |     783230           |               0.615385 |             13 |
| profitable_base_stop       | 2020-07                 | False            |       30 |          1.01002e+06 |               0.5      |             29 |
| profitable_base_stop       | 2020-07                 | True             |       12 |     651210           |               0.666667 |             12 |
| profitable_base_stop       | 2021-01                 | False            |       26 |     466320           |               0.461538 |             25 |
| profitable_base_stop       | 2021-01                 | True             |       11 |     330710           |               0.727273 |             11 |
| profitable_base_stop       | 2021-07                 | False            |       26 |      74200           |               0.423077 |             24 |
| profitable_base_stop       | 2021-07                 | True             |       11 |      62600           |               0.636364 |             11 |
| profitable_base_stop       | 2022-01                 | False            |       18 |      31490           |               0.388889 |             17 |
| profitable_base_stop       | 2022-01                 | True             |        8 |      18880           |               0.75     |              8 |
| profitable_base_stop       | 2022-07                 | False            |       15 |      75410           |               0.4      |             15 |
| profitable_base_stop       | 2022-07                 | True             |        5 |      15080           |               0.6      |              5 |
| profitable_base_stop       | 2023-01                 | False            |       14 |      57850           |               0.428571 |             13 |
| profitable_base_stop       | 2023-01                 | True             |        4 |      26500           |               0.75     |              4 |
| profitable_base_stop       | 2023-07                 | False            |       12 |      62060           |               0.333333 |             12 |
| profitable_base_stop       | 2023-07                 | True             |        5 |      11610           |               0.6      |              5 |
| profitable_base_stop       | 2024-01                 | False            |       10 |      46080           |               0.4      |             10 |
| profitable_base_stop       | 2024-01                 | True             |        4 |       -840           |               0.5      |              4 |
| profitable_base_stop       | 2024-07                 | False            |        6 |      49940           |               0.5      |              6 |
| profitable_base_stop       | 2024-07                 | True             |        3 |       -970           |               0.333333 |              3 |
| profitable_base_stop       | 2025-01                 | False            |        6 |      35730           |               0.5      |              6 |
| profitable_base_stop       | 2025-01                 | True             |        3 |       4900           |               0.333333 |              3 |
| profitable_base_stop       | 2025-07                 | False            |        5 |      37770           |               0.6      |              5 |
| profitable_base_stop       | 2025-07                 | True             |        3 |       4900           |               0.333333 |              3 |
| profitable_base_stop       | 2026-01                 | False            |        1 |      22410           |               1        |              1 |
| profitable_base_stop       | 2026-01                 | True             |        2 |       6860           |               0.5      |              2 |
| profitable_pretrend        | 2020-01                 | False            |       31 |          1.24453e+06 |               0.516129 |             29 |
| profitable_pretrend        | 2020-01                 | True             |       11 |     771630           |               0.636364 |             11 |
| profitable_pretrend        | 2020-07                 | False            |       32 |          1.01878e+06 |               0.5      |             30 |
| profitable_pretrend        | 2020-07                 | True             |       10 |     642450           |               0.7      |             10 |
| profitable_pretrend        | 2021-01                 | False            |       28 |     472040           |               0.464286 |             26 |
| profitable_pretrend        | 2021-01                 | True             |        9 |     324990           |               0.777778 |              9 |
| profitable_pretrend        | 2021-07                 | False            |       28 |      75620           |               0.428571 |             25 |
| profitable_pretrend        | 2021-07                 | True             |        9 |      61180           |               0.666667 |              9 |
| profitable_pretrend        | 2022-01                 | False            |       19 |      34940           |               0.421053 |             17 |
| profitable_pretrend        | 2022-01                 | True             |        7 |      15430           |               0.714286 |              7 |
| profitable_pretrend        | 2022-07                 | False            |       15 |      75410           |               0.4      |             15 |
| profitable_pretrend        | 2022-07                 | True             |        5 |      15080           |               0.6      |              5 |
| profitable_pretrend        | 2023-01                 | False            |       14 |      57850           |               0.428571 |             13 |
| profitable_pretrend        | 2023-01                 | True             |        4 |      26500           |               0.75     |              4 |
| profitable_pretrend        | 2023-07                 | False            |       12 |      62060           |               0.333333 |             12 |
| profitable_pretrend        | 2023-07                 | True             |        5 |      11610           |               0.6      |              5 |
| profitable_pretrend        | 2024-01                 | False            |       10 |      46080           |               0.4      |             10 |
| profitable_pretrend        | 2024-01                 | True             |        4 |       -840           |               0.5      |              4 |
| profitable_pretrend        | 2024-07                 | False            |        6 |      49940           |               0.5      |              6 |
| profitable_pretrend        | 2024-07                 | True             |        3 |       -970           |               0.333333 |              3 |
| profitable_pretrend        | 2025-01                 | False            |        6 |      35730           |               0.5      |              6 |
| profitable_pretrend        | 2025-01                 | True             |        3 |       4900           |               0.333333 |              3 |
| profitable_pretrend        | 2025-07                 | False            |        5 |      37770           |               0.6      |              5 |
| profitable_pretrend        | 2025-07                 | True             |        3 |       4900           |               0.333333 |              3 |
| profitable_pretrend        | 2026-01                 | False            |        1 |      22410           |               1        |              1 |
| profitable_pretrend        | 2026-01                 | True             |        2 |       6860           |               0.5      |              2 |
| quality_rank_top8          | 2020-01                 | False            |       16 |     850280           |               0.5      |             14 |
| quality_rank_top8          | 2020-01                 | True             |       26 |          1.16588e+06 |               0.576923 |             26 |
| quality_rank_top8          | 2020-07                 | False            |       16 |     689530           |               0.5      |             14 |
| quality_rank_top8          | 2020-07                 | True             |       26 |     971700           |               0.576923 |             26 |
| quality_rank_top8          | 2021-01                 | False            |       13 |     339500           |               0.538462 |             11 |
| quality_rank_top8          | 2021-01                 | True             |       24 |     457530           |               0.541667 |             24 |
| quality_rank_top8          | 2021-07                 | False            |       12 |      70330           |               0.5      |             10 |
| quality_rank_top8          | 2021-07                 | True             |       25 |      66470           |               0.48     |             25 |
| quality_rank_top8          | 2022-01                 | False            |        8 |      31070           |               0.5      |              6 |
| quality_rank_top8          | 2022-01                 | True             |       18 |      19300           |               0.5      |             18 |
| quality_rank_top8          | 2022-07                 | False            |        3 |      57190           |               0.333333 |              3 |
| quality_rank_top8          | 2022-07                 | True             |       17 |      33300           |               0.470588 |             17 |
| quality_rank_top8          | 2023-01                 | False            |        3 |      42270           |               0.333333 |              3 |
| quality_rank_top8          | 2023-01                 | True             |       15 |      42080           |               0.533333 |             14 |
| quality_rank_top8          | 2023-07                 | False            |        3 |      47230           |               0.333333 |              3 |

## 标准回测指标

- 期末权益：不适用，本阶段只读归因未重跑策略。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 决策

```json
{
  "stage": "Stage108",
  "model_tag": "stage108_long_base_stop_no_lookahead_feature_audit_v1",
  "line_id": "futures_trend_rebuilt_c9_15w_v2_optimization",
  "generated_at": "2026-07-05T21:35:08",
  "decision": "stage108_no_lookahead_feature_not_sufficient_for_base_stop_delay",
  "stage107_decision": "stage107_long_base_stop_post_exit_positive_but_representative_sensitive_followup_only",
  "candidate_rule_count": 0,
  "best_candidate_signal": "",
  "best_candidate_exit_close_pnl_sum": 0.0,
  "best_candidate_events": 0,
  "best_candidate_start_count": 0,
  "main_horizon": 3,
  "event_rows": 282,
  "start_count": 13,
  "unique_physical_events": 47,
  "all_exit_close_pnl_sum": 5116879.999999998,
  "all_actual_fill_pnl_sum": 7214105.000000002,
  "predeclared_signal_count": 8,
  "promote_to_proxy": false,
  "promote_to_true_engine": false,
  "strategy_changed": false,
  "true_engine_run": false,
  "order_api_calls": 0,
  "ctp_connected": false,
  "next_step": "停止把 long_base_stop 后延续收益直接转成延迟退出规则；转回账户层或外生信息源。",
  "overfit_after": "否。固定特征族没有通过宽样本与代表值闸门，按预设停止。",
  "continue_after": "有但不沿 base_stop 延迟",
  "continue_reason": "post-exit 有恢复，但当前无前视状态无法稳定识别可等待事件。"
}
```

## 后续规划和 TODO

- 停止把 long_base_stop 后延续收益直接转成延迟退出规则；转回账户层或外生信息源。

## 独立 agent 复核

- 复核 agent：Maxwell（`019f327d-a439-7250-8861-12893b4736e9`）
- 复核方式：`.py311/bin/python` 只读复算；未调用脚本 `main()`，未修改文件，未连接 CTP，未调用订单/邮件。
- 高风险：无。
- 中风险：无。
- 样本复核：Stage107 panel 总计 `1,128` 行，过滤 `horizon_days=3` 且 `has_future_price=True` 后 `282` 行；全部为 `long_base_stop` / `long`。
- no-lookahead 复核：`ma5_prev/ma20_prev/ret20_prev/vol20_prev` 均滞后到 exit 日之前；`exit_ret_z` 只用 exit 日 close-to-close 和此前波动；扰动 `future_close_price` 后 8 个 signal 与 help 标签变化数均为 `0`。
- 标签复核：`post_exit_continuation_pnl_from_exit_close` 是 summary/gate/decision 主标签；`post_exit_continuation_pnl` 只作 actual-fill 参考。
- 候选数复核：所有 true signal 的 `mechanism_gate_pass=False`，`candidate_rule_count=0` 成立。主要失败点是代表值闸门不过：`not_deep_loss` min representative `-851,550`、`pretrend_positive` `-1,623,960`、`exit_close_above_ma20_prev` `-1,643,790`、`mild_exit_shock` `-1,800,500`、`whipsaw_core` `-1,601,660`、`quality_rank_top8` `-1,355,060`；`profitable_base_stop/profitable_pretrend` 物理事件数不足 `20`。
- 复核置信度：`0.92`。
- 复核结论：Stage108 当前“无候选、停止直接转延迟退出”的结论有效；若未来替换 intraday stop，还需另做路径和订单语义验证，但不影响本阶段结论。

## 过拟合反思

- 运行前：否，预声明状态和闸门固定，不扫产品、方向、日期或小数阈值。
- 运行后：否。固定特征族没有通过宽样本与代表值闸门，按预设停止。

## 继续价值反思

- 运行前：有，判断 base_stop 事后恢复是否能转成当时可执行状态。
- 运行后：有但不沿 base_stop 延迟。post-exit 有恢复，但当前无前视状态无法稳定识别可等待事件。

## 输出

- 报告：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage108_long_base_stop_no_lookahead_feature_audit/rebuilt_c9_v2_stage108_long_base_stop_no_lookahead_feature_audit_report_stage108_long_base_stop_no_lookahead_feature_audit_v1.md`
- event_features：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage108_long_base_stop_no_lookahead_feature_audit/rebuilt_c9_v2_stage108_long_base_stop_no_lookahead_feature_audit_event_features_stage108_long_base_stop_no_lookahead_feature_audit_v1.csv.gz`
- signal_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage108_long_base_stop_no_lookahead_feature_audit/rebuilt_c9_v2_stage108_long_base_stop_no_lookahead_feature_audit_signal_summary_stage108_long_base_stop_no_lookahead_feature_audit_v1.csv`
- by_start_signal：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage108_long_base_stop_no_lookahead_feature_audit/rebuilt_c9_v2_stage108_long_base_stop_no_lookahead_feature_audit_by_start_signal_stage108_long_base_stop_no_lookahead_feature_audit_v1.csv`
- input_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage108_long_base_stop_no_lookahead_feature_audit/rebuilt_c9_v2_stage108_long_base_stop_no_lookahead_feature_audit_input_audit_stage108_long_base_stop_no_lookahead_feature_audit_v1.csv`
