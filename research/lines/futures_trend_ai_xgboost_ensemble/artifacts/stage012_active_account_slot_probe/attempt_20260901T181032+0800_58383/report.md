# Stage012 首个活跃边际月份账户标签探针

- 决策：`stage012_account_label_identifiable_continue_coverage_study`
- A/A确定性：`True`；决策日前路径同一：`True`。
- 完整输入身份：`True`；标签可识别：`True`；单臂<=600秒：`True`。
- 本阶段不训练模型，不据单月结果选择候选，不连接CTP，不调用订单API。

|   base_equity |   end_equity |   future_return |   future_max_drawdown |   future_net_pnl |   future_slippage |   future_trade_count |   future_trading_days | arm   |   candidate_source_rank |   delta_vs_A1_future_return |   delta_vs_A1_future_max_drawdown |   delta_vs_A1_future_net_pnl |   delta_vs_A1_future_slippage |   delta_vs_A1_future_trade_count |
|--------------:|-------------:|----------------:|----------------------:|-----------------:|------------------:|---------------------:|----------------------:|:------|------------------------:|----------------------------:|----------------------------------:|-----------------------------:|------------------------------:|---------------------------------:|
|   4.07588e+06 |  4.22815e+06 |      0.0373588  |            -0.0828428 |           152270 |             14860 |                    7 |                    21 | A1    |                      10 |                    0        |                        0          |                            0 |                             0 |                                0 |
|   4.07588e+06 |  4.22815e+06 |      0.0373588  |            -0.0828428 |           152270 |             14860 |                    7 |                    21 | A2    |                      10 |                    0        |                        0          |                            0 |                             0 |                                0 |
|   4.07588e+06 |  4.1608e+06  |      0.0208348  |            -0.0810833 |            84920 |              8860 |                    5 |                    21 | C12   |                      12 |                   -0.016524 |                        0.00175951 |                       -67350 |                         -6000 |                               -2 |
|   4.07588e+06 |  4.05508e+06 |     -0.00510319 |            -0.0808288 |           -20800 |             10760 |                    9 |                    21 | C13   |                      13 |                   -0.042462 |                        0.00201394 |                      -173070 |                         -4100 |                                2 |

| arm   | frame            | date_column   |   all_rows |   target_period_rows |
|:------|:-----------------|:--------------|-----------:|---------------------:|
| A1    | entry_candidates | date          |        400 |                   11 |
| A1    | entry_risk       | date          |        202 |                    3 |
| A1    | trade_events     | date          |        476 |                    6 |
| A2    | entry_candidates | date          |        400 |                   11 |
| A2    | entry_risk       | date          |        202 |                    3 |
| A2    | trade_events     | date          |        476 |                    6 |
| C12   | entry_candidates | date          |        400 |                   11 |
| C12   | entry_risk       | date          |        201 |                    2 |
| C12   | trade_events     | date          |        475 |                    5 |
| C13   | entry_candidates | date          |        400 |                   11 |
| C13   | entry_risk       | date          |        203 |                    4 |
| C13   | trade_events     | date          |        477 |                    7 |
