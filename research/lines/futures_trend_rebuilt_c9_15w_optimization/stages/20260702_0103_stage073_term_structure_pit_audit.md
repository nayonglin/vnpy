# Stage073 期限结构 PIT 审计

- 记录时间：2026-07-02 01:03 CST
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage073_term_structure_pit_audit_v1`
- 是否重要突破版本：否
- 新增参数：front/next 期限结构、backwardation_pct、product 内 prior percentile、directional_carry_aligned
- 修改参数：无
- 删除参数：无

# Stage073 term structure PIT audit

## 结论

- 决策：`stage073_term_structure_no_stable_oos_candidate_keep_readonly`
- 下一步：继续寻找真正新PIT信息源；不要扫front/next阈值、percentile或month_gap救参
- 样本行数：`2787`；期限结构快照：`21770`；覆盖品种：`15`
- 匹配覆盖：`76.5339%`；方向顺风覆盖：`36.4191%`
- 全样本 PnL：`62843641.40`；方向顺风子样本 PnL：`18762542.80`
- 稳定 OOS 候选数：`0`

## 外部调研判断

- Quantpedia、CME、Wharton carry paper 与 basis-momentum 研究都支持商品期限结构/roll yield/carry 可能含有预测信息。
- 本阶段不复制外部策略，只验证本地逐合约 close/open_interest 能否在 T+1 口径构造 front/next backwardation 特征。

## 过拟合与继续价值反思

- 开始是否过拟合：否；本阶段先验证独立PIT信息源和可见性，不围绕坏窗口调参。
- 结束是否过拟合：若只拿 stable 条件做固定低自由度 proxy 才不是过拟合；若继续扫分位、月差、品种则会过拟合。
- 开始是否值得继续：有；现有内部同源特征已低覆盖或证伪，期限结构是商品期货特有的新信息维度。
- 结束是否值得继续：取决于是否出现稳定OOS候选；无稳定候选则只保留数据资产，停止救参。

## Stable OOS 候选

_无数据_

## 条件 OOS 摘要 Top 20

| condition                                         | description                                    | feature_family                | candidate_eligible   |   count |   coverage_pct |   source_count |   year_count |   product_count |         total_pnl |   pnl_share_pct |   mean_pnl |   mean_pnl_lift_vs_base |   median_r |   median_r_lift_vs_base |   win_rate_pct |   win_rate_lift_pp |   big_win_rate_pct |   big_win_rate_lift_pp |   oos_test_fold_count |   oos_positive_fold_count |   oos_min_fold_pnl |   oos_total_test_pnl |   oos_min_fold_count | stable_oos_candidate   |
|:--------------------------------------------------|:-----------------------------------------------|:------------------------------|:---------------------|--------:|---------------:|---------------:|-------------:|----------------:|------------------:|----------------:|-----------:|------------------------:|-----------:|------------------------:|---------------:|-------------------:|-------------------:|-----------------------:|----------------------:|--------------------------:|-------------------:|---------------------:|---------------------:|:-----------------------|
| ai_oi_account_and_directional_carry_aligned       | AI rank 1-9 + OI确认 + 账户干净 + 期限结构顺风 | ai_oi_account_term_structure  | True                 |      52 |         1.8658 |             15 |            5 |               8 |       8.01121e+06 |         12.7478 |  154062    |                  6.8324 |     1      |                 -3.542  |        75      |            32.5529 |            42.3077 |                18.3751 |                     4 |                         2 |   -12180           |          7.86828e+06 |                    1 | False                  |
| term_backwardation_positive                       | front/next backwardation > 0                   | term_structure                | True                 |     790 |        28.3459 |             17 |            7 |              12 |       2.3391e+07  |         37.2209 |   29608.8  |                  1.3131 |    -0.0769 |                  0.2725 |        44.8101 |             2.3631 |            29.1139 |                 5.1814 |                     4 |                         3 |       -3.43741e+06 |          2.32707e+07 |                  124 | False                  |
| full_market_ai_top8_and_directional_carry_aligned | full-market AI top8 且期限结构顺风             | full_market_term_structure    | True                 |      48 |         1.7223 |             16 |            3 |               4 |       1.17919e+06 |          1.8764 |   24566.5  |                  1.0895 |    -0.25   |                  0.8855 |        47.9167 |             5.4696 |            18.75   |                -5.1825 |                     2 |                         2 |    44200           |          1.17919e+06 |                   18 | False                  |
| directional_carry_misaligned                      | 方向与期限结构 carry 逆风                      | term_structure                | True                 |    1118 |        40.1148 |             17 |            7 |              14 |       2.45635e+07 |         39.0868 |   21971    |                  0.9744 |    -0.2823 |                  1      |        44.6333 |             2.1862 |            26.0286 |                 2.0961 |                     4 |                         2 |       -6.98486e+06 |          2.32724e+07 |                  212 | False                  |
| term_backwardation_prior_p80                      | backwardation prior percentile >= 0.8          | term_structure                | True                 |     511 |        18.3351 |             17 |            7 |              12 |       1.07349e+07 |         17.082  |   21007.7  |                  0.9317 |    -0.3974 |                  1.4077 |        40.7045 |            -1.7426 |            29.7456 |                 5.8131 |                     4 |                         3 |       -3.4078e+06  |          1.09484e+07 |                   62 | False                  |
| volume_gt1_and_directional_carry_aligned          | 当前真实手数 > 1 且期限结构顺风                | current_budget_term_structure | True                 |     978 |        35.0915 |             17 |            7 |              14 |       1.86995e+07 |         29.7556 |   19120.1  |                  0.8479 |    -0.1935 |                  0.6855 |        42.4335 |            -0.0135 |            24.7444 |                 0.8118 |                     4 |                         3 |       -5.10646e+06 |          1.86685e+07 |                  100 | False                  |
| ai_rank_1_9_and_directional_carry_aligned         | Stage182 AI rank 1-9 且期限结构顺风            | ai_term_structure             | True                 |     924 |        33.1539 |             17 |            7 |              13 |       1.7594e+07  |         27.9965 |   19041.2  |                  0.8444 |    -0.1166 |                  0.4128 |        42.9654 |             0.5183 |            24.4589 |                 0.5263 |                     4 |                         3 |       -5.10571e+06 |          1.75839e+07 |                   66 | False                  |
| directional_carry_aligned                         | long 配 backwardation 或 short 配 contango     | term_structure                | True                 |    1015 |        36.4191 |             17 |            7 |              14 |       1.87625e+07 |         29.8559 |   18485.3  |                  0.8198 |    -0.1935 |                  0.6855 |        42.7586 |             0.3115 |            24.6305 |                 0.698  |                     4 |                         3 |       -5.10571e+06 |          1.87335e+07 |                  102 | False                  |
| term_contango_negative                            | front/next backwardation < 0，即 contango      | term_structure                | True                 |    1330 |        47.7216 |             17 |            7 |              14 |       2.03761e+07 |         32.4235 |   15320.4  |                  0.6794 |    -0.3043 |                  1.078  |        43.5338 |             1.0868 |            23.3835 |                -0.5491 |                     4 |                         2 |       -7.02049e+06 |          1.91763e+07 |                  186 | False                  |
| term_backwardation_prior_p20                      | backwardation prior percentile <= 0.2          | term_structure                | True                 |     533 |        19.1245 |             17 |            7 |              14 |       5.8712e+06  |          9.3426 |   11015.4  |                  0.4885 |    -0.3411 |                  1.2083 |        37.5235 |            -4.9236 |            17.0732 |                -6.8594 |                     4 |                         2 |       -8.62261e+06 |          4.97163e+06 |                   36 | False                  |
| directional_carry_extreme_aligned                 | 方向顺风且 product 内 prior percentile 达极端  | term_structure                | True                 |     601 |        21.5644 |             17 |            7 |              14 | -104929           |         -0.167  |    -174.59 |                 -0.0077 |    -0.4    |                  1.4168 |        37.2712 |            -5.1759 |            22.4626 |                -1.47   |                     4 |                         2 |       -5.71799e+06 |     -63923.8         |                   84 | False                  |
| term_structure_matched                            | 逐合约 front/next 期限结构特征可 T+1 匹配      | term_structure                | False                |    2133 |        76.5339 |             17 |            7 |              14 |       4.33261e+07 |         68.9427 |   20312.3  |                  0.9008 |    -0.2222 |                  0.7871 |        43.7412 |             1.2941 |            25.3633 |                 1.4308 |                     4 |                         3 |       -6.18405e+06 |          4.2006e+07  |                  325 | False                  |

## 覆盖率

| feature                                          | present   |   non_null_count |   active_count |   coverage_pct |
|:-------------------------------------------------|:----------|-----------------:|---------------:|---------------:|
| term_structure_matched                           | True      |             2787 |           2133 |       100      |
| term_structure_backwardation_pct                 | True      |             2133 |           2133 |        76.5339 |
| term_structure_backwardation_prior_pctile        | True      |             2094 |           2094 |        75.1346 |
| term_structure_directional_carry_aligned         | True      |             2787 |           1015 |       100      |
| term_structure_directional_carry_extreme_aligned | True      |             2787 |            601 |       100      |
| snapshot_product_count                           | True      |               15 |             15 |                |

## 产品摘要

| product_vt_symbol   |   row_count |   matched_count |   matched_coverage_pct |   aligned_count |   aligned_coverage_pct |         base_pnl |      matched_pnl |       aligned_pnl |   aligned_mean_pnl |   base_mean_pnl |
|:--------------------|------------:|----------------:|-----------------------:|----------------:|-----------------------:|-----------------:|-----------------:|------------------:|-------------------:|----------------:|
| si.GFEX             |          69 |              69 |               100      |              43 |                62.3188 |      8.32898e+06 |      8.32898e+06 |       9.01902e+06 |          209745    |       120710    |
| CF.CZCE             |         101 |             101 |               100      |              20 |                19.802  |      2.96962e+06 |      2.96962e+06 |       1.27535e+06 |           63767.5  |        29402.2  |
| AP.CZCE             |         153 |             153 |               100      |              59 |                38.5621 |      4.47677e+06 |      4.47677e+06 |       3.0183e+06  |           51157.6  |        29259.9  |
| jm.DCE              |         212 |             195 |                91.9811 |             122 |                57.5472 |      9.54485e+06 |      8.32781e+06 |       4.07762e+06 |           33423.1  |        45022.9  |
| ru.SHFE             |         191 |             191 |               100      |              73 |                38.2199 |      6.13005e+06 |      6.13005e+06 |       2.31085e+06 |           31655.5  |        32094.5  |
| SA.CZCE             |         110 |             110 |               100      |              18 |                16.3636 |     -1.22894e+06 |     -1.22894e+06 |  452840           |           25157.8  |       -11172.2  |
| fu.SHFE             |         357 |             357 |               100      |             246 |                68.9076 |      5.24543e+06 |      5.24543e+06 |       4.45441e+06 |           18107.4  |        14693.1  |
| FG.CZCE             |         161 |             148 |                91.9255 |              45 |                27.9503 |      2.88646e+06 |      3.12614e+06 |  582940           |           12954.2  |        17928.3  |
| OI.CZCE             |         124 |             107 |                86.2903 |              94 |                75.8065 |      1.07136e+06 | 434085           |  789640           |            8400.43 |         8640.04 |
| rb.SHFE             |         120 |             120 |               100      |              88 |                73.3333 | 959440           | 959440           |  619970           |            7045.11 |         7995.33 |
| sp.SHFE             |         106 |             106 |               100      |              15 |                14.1509 |     -2.2946e+06  |     -2.2946e+06  |   77960           |            5197.33 |       -21647.2  |
| SM.CZCE             |         169 |             169 |               100      |              60 |                35.503  |      1.50778e+07 |      1.50778e+07 | -939550           |          -15659.2  |        89218    |
| MA.CZCE             |         231 |             214 |                92.6407 |              71 |                30.7359 |     -4.65653e+06 |     -1.79213e+06 |      -3.11412e+06 |          -43860.8  |       -20158.1  |
| SH.CZCE             |          93 |              93 |               100      |              61 |                65.5914 |     -6.43443e+06 |     -6.43443e+06 |      -3.8627e+06  |          -63322.9  |       -69187.4  |
| au.SHFE             |          92 |               0 |                 0      |               0 |                 0      |      4.87312e+06 |      0           |       0           |                    |        52968.7  |
| cu.SHFE             |         156 |               0 |                 0      |               0 |                 0      |     -6.60137e+06 |      0           |       0           |                    |       -42316.4  |
| hc.SHFE             |         114 |               0 |                 0      |               0 |                 0      |      4.72181e+06 |      0           |       0           |                    |        41419.4  |
| lc.GFEX             |          87 |               0 |                 0      |               0 |                 0      |      2.19469e+07 |      0           |       0           |                    |       252263    |
| lh.DCE              |         141 |               0 |                 0      |               0 |                 0      |     -4.17316e+06 |      0           |       0           |                    |       -29596.9  |

## 起点摘要

| requested_start_month   |   row_count |   aligned_count |         base_pnl |      aligned_pnl |   aligned_mean_pnl |
|:------------------------|------------:|----------------:|-----------------:|-----------------:|-------------------:|
| 2018-01                 |         280 |             100 |      1.2606e+07  |      3.957e+06   |          39570     |
| 2018-07                 |         280 |             100 |      1.47362e+07 |      3.99261e+06 |          39926.1   |
| 2019-01                 |         280 |             100 |      1.36926e+07 |      3.90386e+06 |          39038.6   |
| 2019-07                 |         280 |             100 |      7.60527e+06 |      2.30425e+06 |          23042.5   |
| 2020-01                 |         278 |             100 |      5.80157e+06 |      1.82483e+06 |          18248.3   |
| 2020-07                 |         254 |              88 |      4.65776e+06 |      1.49761e+06 |          17018.3   |
| 2021-01                 |         218 |              76 |      2.23272e+06 | 721946           |           9499.28  |
| 2021-07                 |         193 |              70 | 348870           | 158295           |           2261.36  |
| 2022-01                 |         146 |              59 | 146769           |  41302.8         |            700.048 |
| 2022-07                 |         132 |              51 | 287104           | 120704           |           2366.75  |
| 2023-01                 |         114 |              47 | 168009           |  80828.2         |           1719.75  |
| 2023-07                 |         105 |              41 | 245695           |  90083.6         |           2197.16  |
| 2024-01                 |          84 |              31 | 168019           |  39922.8         |           1287.83  |
| 2024-07                 |          56 |              19 |  67102.8         |  12832           |            675.368 |
| 2025-01                 |          42 |              16 |  36937.4         |   5946.6         |            371.663 |
| 2025-07                 |          31 |              11 |  35582.4         |  17491.6         |           1590.15  |
| 2026-01                 |          14 |               6 |   7451.6         |  -6958.4         |          -1159.73  |

## 输出

- snapshots：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage073_term_structure_pit_audit/rebuilt_c9_stage073_term_structure_pit_audit_snapshots_stage073_term_structure_pit_audit_v1.csv`
- joined feature matrix：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage073_term_structure_pit_audit/rebuilt_c9_stage073_term_structure_pit_audit_joined_feature_matrix_stage073_term_structure_pit_audit_v1.csv`
- condition summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage073_term_structure_pit_audit/rebuilt_c9_stage073_term_structure_pit_audit_condition_oos_summary_stage073_term_structure_pit_audit_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage073_term_structure_pit_audit/rebuilt_c9_stage073_term_structure_pit_audit_decision_stage073_term_structure_pit_audit_v1.json`
