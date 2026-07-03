# Stage015 Purged Meta-label OOS Audit

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T05:03:56
- 阶段性质：当前重建 C9 二级信号质量模型只读 OOS 复验；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否；只有 OOS 稳定后才允许进入后续 proxy/A/B

## 外部调研与判断

- 参考资料：Lopez de Prado meta-labeling、Hudson & Thames triple-barrier/meta-labeling、旧 `futures_trend_signal_quality_ai` Stage235/236 反证。
- 我的判断：二级 AI 的正确位置是给已有主信号做 sizing/approval，不是生成方向；当前 C9 样本更大，值得一次严格复验，但 OOS 不稳定就必须停止。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage015_purged_meta_label_oos_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage015_purged_meta_label_oos_audit.py`
- 新增参数：`EMBARGO_DAYS=20`、`MIN_TRAIN_ROWS=200`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- 输入 panel rows：`2867`
- 去重模型样本：`1995`
- OOS scored rows：`1281`
- OOS 年数：`5`
- high 质量率胜 low 年数：`3`
- high PnL 胜 low 年数：`3`
- high bad_path 低于 low 年数：`3`
- high OOS total PnL：`16790604.40`
- low OOS total PnL：`20376989.70`
- high 最差年度 PnL：`-3610956.40`
- 决策：`stage015_oos_meta_label_not_stable_keep_readonly`
- 原因：OOS 高分桶没有跨年稳定优于低分桶，不能用于当前重建 C9 加风险。

## 年度高低分桶对比

|   entry_year |   count_high |   count_low |   count_mid |   quality_rate_pct_high |   quality_rate_pct_low |   quality_rate_pct_mid |   total_realized_pnl_high |   total_realized_pnl_low |   total_realized_pnl_mid |   mean_realized_pnl_high |   mean_realized_pnl_low |   mean_realized_pnl_mid |   big_winner_rate_pct_high |   big_winner_rate_pct_low |   big_winner_rate_pct_mid |   bad_path_rate_pct_high |   bad_path_rate_pct_low |   bad_path_rate_pct_mid |   mean_oos_score_high |   mean_oos_score_low |   mean_oos_score_mid |   high_minus_low_quality_rate_pp |   high_minus_low_total_pnl |   high_minus_low_bad_path_rate_pp |   high_quality_beats_low |   high_pnl_beats_low |   high_bad_path_below_low |
|-------------:|-------------:|------------:|------------:|------------------------:|-----------------------:|-----------------------:|--------------------------:|-------------------------:|-------------------------:|-------------------------:|------------------------:|------------------------:|---------------------------:|--------------------------:|--------------------------:|-------------------------:|------------------------:|------------------------:|----------------------:|---------------------:|---------------------:|---------------------------------:|---------------------------:|----------------------------------:|-------------------------:|---------------------:|--------------------------:|
|         2022 |           96 |          95 |          96 |                 35.4167 |                48.4211 |                38.5417 |              -3.61096e+06 |              8.08512e+06 |        -594786           |                -37614.1  |                85106.5  |                -6195.69 |                     2.0833 |                   25.2632 |                    0      |                  51.0417 |                 66.3158 |                 44.7917 |                0.9278 |               0.2208 |               0.599  |                         -13.0044 |               -1.16961e+07 |                          -15.2741 |                        0 |                    0 |                         1 |
|         2023 |           81 |          80 |          80 |                 51.8519 |                33.75   |                37.5    |               2.86476e+06 |         196640           |        -369205           |                 35367.5  |                 2458    |                -4615.06 |                    13.5802 |                    3.75   |                   11.25   |                  43.2099 |                 58.75   |                 35      |                0.5888 |               0.1035 |               0.2956 |                          18.1019 |                2.66812e+06 |                          -15.5401 |                        1 |                    1 |                         1 |
|         2024 |          117 |         117 |         117 |                 55.5556 |                55.5556 |                60.6838 |               1.06965e+07 |              1.08742e+07 |              2.12241e+06 |                 91423.1  |                92941.8  |                18140.3  |                    18.8034 |                    5.1282 |                    5.9829 |                  16.2393 |                 24.7863 |                 23.0769 |                0.618  |               0.1474 |               0.3656 |                           0      |          -177685           |                           -8.547  |                        0 |                    0 |                         1 |
|         2025 |           90 |          89 |          89 |                 40      |                30.3371 |                53.9326 |               6.61592e+06 |              1.14144e+06 |              1.0155e+07  |                 73510.2  |                12825.2  |               114101    |                     8.8889 |                   15.7303 |                   25.8427 |                  37.7778 |                 26.9663 |                 38.2022 |                0.6721 |               0.11   |               0.3458 |                           9.6629 |                5.47448e+06 |                           10.8115 |                        1 |                    1 |                         0 |
|         2026 |           45 |          44 |          45 |                 62.2222 |                56.8182 |                48.8889 |          224371           |          79601.2         |         821160           |                  4986.02 |                 1809.12 |                18248    |                     0      |                    0      |                    0      |                  33.3333 |                 25      |                 44.4444 |                0.525  |               0.1064 |               0.2979 |                           5.404  |           144770           |                            8.3333 |                        1 |                    1 |                         0 |

## 分桶摘要

|   entry_year | score_bucket   |   count |   quality_rate_pct |   total_realized_pnl |   mean_realized_pnl |   big_winner_rate_pct |   bad_path_rate_pct |   mean_oos_score |
|-------------:|:---------------|--------:|-------------------:|---------------------:|--------------------:|----------------------:|--------------------:|-----------------:|
|         2022 | high           |      96 |            35.4167 |         -3.61096e+06 |           -37614.1  |                2.0833 |             51.0417 |           0.9278 |
|         2022 | low            |      95 |            48.4211 |          8.08512e+06 |            85106.5  |               25.2632 |             66.3158 |           0.2208 |
|         2022 | mid            |      96 |            38.5417 |    -594786           |            -6195.69 |                0      |             44.7917 |           0.599  |
|         2023 | high           |      81 |            51.8519 |          2.86476e+06 |            35367.5  |               13.5802 |             43.2099 |           0.5888 |
|         2023 | low            |      80 |            33.75   |     196640           |             2458    |                3.75   |             58.75   |           0.1035 |
|         2023 | mid            |      80 |            37.5    |    -369205           |            -4615.06 |               11.25   |             35      |           0.2956 |
|         2024 | high           |     117 |            55.5556 |          1.06965e+07 |            91423.1  |               18.8034 |             16.2393 |           0.618  |
|         2024 | low            |     117 |            55.5556 |          1.08742e+07 |            92941.8  |                5.1282 |             24.7863 |           0.1474 |
|         2024 | mid            |     117 |            60.6838 |          2.12241e+06 |            18140.3  |                5.9829 |             23.0769 |           0.3656 |
|         2025 | high           |      90 |            40      |          6.61592e+06 |            73510.2  |                8.8889 |             37.7778 |           0.6721 |
|         2025 | low            |      89 |            30.3371 |          1.14144e+06 |            12825.2  |               15.7303 |             26.9663 |           0.11   |
|         2025 | mid            |      89 |            53.9326 |          1.0155e+07  |           114101    |               25.8427 |             38.2022 |           0.3458 |
|         2026 | high           |      45 |            62.2222 |     224371           |             4986.02 |                0      |             33.3333 |           0.525  |
|         2026 | low            |      44 |            56.8182 |      79601.2         |             1809.12 |                0      |             25      |           0.1064 |
|         2026 | mid            |      45 |            48.8889 |     821160           |            18248    |                0      |             44.4444 |           0.2979 |

## 主要特征系数

|   test_year |   rank | feature                                      |   coefficient |   abs_coefficient |
|------------:|-------:|:---------------------------------------------|--------------:|------------------:|
|        2022 |      1 | cat__rsi_bucket_short_rsi_gt50               |       -1.4394 |            1.4394 |
|        2022 |      2 | cat__rsi_bucket_long_rsi_ge70                |       -1.4267 |            1.4267 |
|        2022 |      3 | cat__rsi_bucket_short_rsi_30_40              |        1.1516 |            1.1516 |
|        2022 |      4 | cat__rsi_bucket_long_rsi_lt50                |        1.0246 |            1.0246 |
|        2022 |      5 | cat__product_lh.DCE                          |       -0.9477 |            0.9477 |
|        2022 |      6 | num__rsi_value                               |        0.9099 |            0.9099 |
|        2022 |      7 | cat__product_FG.CZCE                         |        0.8112 |            0.8112 |
|        2022 |      8 | cat__product_ru.SHFE                         |        0.6192 |            0.6192 |
|        2022 |      9 | num__contracts_by_risk                       |       -0.5992 |            0.5992 |
|        2022 |     10 | cat__loss_streak_bucket_loss_streak_ge3      |       -0.5726 |            0.5726 |
|        2022 |     11 | cat__product_cu.SHFE                         |       -0.5512 |            0.5512 |
|        2022 |     12 | cat__product_jm.DCE                          |        0.5425 |            0.5425 |
|        2022 |     13 | num__contracts_by_margin                     |        0.4722 |            0.4722 |
|        2022 |     14 | cat__stop_distance_bucket_stop_le1pct        |       -0.4675 |            0.4675 |
|        2022 |     15 | cat__product_OI.CZCE                         |        0.4549 |            0.4549 |
|        2022 |     16 | num__same_direction_correlation_active_count |       -0.4545 |            0.4545 |
|        2022 |     17 | cat__product_AP.CZCE                         |       -0.4527 |            0.4527 |
|        2022 |     18 | cat__loss_streak_bucket_loss_streak_1_2      |        0.4504 |            0.4504 |
|        2022 |     19 | cat__signal_long_case2                       |        0.4069 |            0.4069 |
|        2022 |     20 | cat__stop_distance_bucket_stop_1_2pct        |        0.3988 |            0.3988 |
|        2023 |      1 | cat__rsi_bucket_long_rsi_ge70                |       -1.2582 |            1.2582 |
|        2023 |      2 | cat__rsi_bucket_short_rsi_gt50               |       -1.1071 |            1.1071 |
|        2023 |      3 | cat__product_cu.SHFE                         |       -1.0973 |            1.0973 |
|        2023 |      4 | cat__product_au.SHFE                         |        1.0171 |            1.0171 |
|        2023 |      5 | num__rsi_value                               |        0.9167 |            0.9167 |
|        2023 |      6 | cat__product_ru.SHFE                         |        0.8832 |            0.8832 |
|        2023 |      7 | cat__ai_rank_bucket_rank_1_3                 |        0.878  |            0.878  |
|        2023 |      8 | cat__product_AP.CZCE                         |       -0.8033 |            0.8033 |
|        2023 |      9 | cat__product_lh.DCE                          |       -0.8019 |            0.8019 |
|        2023 |     10 | cat__risk_mode_volume_open_interest_surge    |       -0.7902 |            0.7902 |

## 过拟合反思

- 运行前判断：中等。二级模型天然容易过拟合；本阶段用去重、年份 OOS、embargo 和低复杂度逻辑回归压低风险。
- 运行后判断：若 OOS 不稳定后继续调模型/特征/桶阈值，就是过拟合；本阶段只记录一次冻结审计。

## 继续价值反思

- 运行前判断：有价值。目标要求 AI 选品/高质量信号加风险，当前 C9 样本比旧 78-1 样本更大，值得一次严格复验。
- 运行后判断：有限。继续调特征、模型、桶阈值大概率是过拟合；除非引入新外生特征源。

## 输出文件

- scored_samples: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage015_purged_meta_label_oos_audit/rebuilt_c9_v2_stage015_purged_meta_label_oos_audit_scored_samples_stage015_purged_meta_label_oos_audit_v1.csv`
- bucket_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage015_purged_meta_label_oos_audit/rebuilt_c9_v2_stage015_purged_meta_label_oos_audit_bucket_summary_stage015_purged_meta_label_oos_audit_v1.csv`
- year_comparison: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage015_purged_meta_label_oos_audit/rebuilt_c9_v2_stage015_purged_meta_label_oos_audit_year_comparison_stage015_purged_meta_label_oos_audit_v1.csv`
- feature_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage015_purged_meta_label_oos_audit/rebuilt_c9_v2_stage015_purged_meta_label_oos_audit_feature_summary_stage015_purged_meta_label_oos_audit_v1.csv`
- chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage015_purged_meta_label_oos_audit/rebuilt_c9_v2_stage015_purged_meta_label_oos_audit_oos_bucket_chart_stage015_purged_meta_label_oos_audit_v1.png`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage015_purged_meta_label_oos_audit/rebuilt_c9_v2_stage015_purged_meta_label_oos_audit_decision_stage015_purged_meta_label_oos_audit_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage015_purged_meta_label_oos_audit/rebuilt_c9_v2_stage015_purged_meta_label_oos_audit_report_stage015_purged_meta_label_oos_audit_v1.md`
