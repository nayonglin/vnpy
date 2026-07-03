# Stage048 - CFTC COT 跨市场映射资格审计

- 记录时间：`2026-07-01T20:01`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage048_cftc_cot_mapping_audit_v1`
- 决策：`stage048_cftc_cot_low_coverage_no_stable_oos_keep_readonly`

## 外部调研与判断

- CFTC COT 是官方周频持仓报告，能提供交易商类别和 open interest 的公开背景，但报告日和发布时间有天然滞后。
- GitHub `cot_reports` 这类库说明该数据适合标准化下载和研究，但不能解决中国商品期货映射问题。
- 旧线 Stage014/Stage256 已显示 COT 在第78/旧 C9 上样本外排序失败；本阶段只在重建线复验，不把它当策略优化参数。

## 口径

- COT 数据：`2020` 至 `2026` 本地 `external_cftc_cot_cache/fut_disagg_txt_*.zip`。
- 映射：沿用旧线冻结映射 `CF/OI/lh/lc/au/cu/fu/hc/rb`，不根据本次结果改品种。
- 可用时间：报告日后第 4 天 08:00 中国时间；只允许 `available_datetime <= entry_datetime`。
- 匹配窗口：最近 `45` 天内一条 COT 信号。
- 公式：`0.35 * managed_money_net_z + 0.65 * managed_money_flow_z`，`156` 周滚动、最低 `52` 周历史。
- 本阶段只读审计；不改官方配置、不运行 true engine、不连接 CTP/SimNow、不调用 order API。

## 覆盖

| feature                    | present   |   non_null_count |   active_count |   coverage_pct |
|:---------------------------|:----------|-----------------:|---------------:|---------------:|
| cot_matched                | True      |             2787 |           1117 |        40.0789 |
| cot_available_datetime     | True      |             1117 |           1117 |        40.0789 |
| cot_external_quality_score | True      |             1117 |           1117 |        40.0789 |
| cot_supportive             | True      |             2787 |            209 |         7.4991 |
| cot_strong_support         | True      |             2787 |             59 |         2.117  |
| cot_direct_mapping         | True      |             2787 |            442 |        15.8593 |
| cot_supportive_direct      | True      |             2787 |            102 |         3.6598 |
| cot_headwind               | True      |             2787 |            156 |         5.5974 |

## COT Source Summary

| product_vt_symbol   | product_key   | cftc_market_name                                        | source_name                | mapping_type        |   confidence |   market_available |   raw_rows | signal_start        | signal_end          |
|:--------------------|:--------------|:--------------------------------------------------------|:---------------------------|:--------------------|-------------:|-------------------:|-----------:|:--------------------|:--------------------|
| CF.CZCE             | cf.czce       | COTTON NO. 2 - ICE FUTURES U.S.                         | CFTC COT Cotton No.2       | direct_global_proxy |         0.7  |                  1 |        333 | 2020-01-11 08:00:00 | 2026-05-23 08:00:00 |
| OI.CZCE             | oi.czce       | SOYBEAN OIL - CHICAGO BOARD OF TRADE                    | CFTC COT Soybean Oil       | oilseed_proxy       |         0.6  |                  1 |        333 | 2020-01-11 08:00:00 | 2026-05-23 08:00:00 |
| lh.DCE              | lh.dce        | LEAN HOGS - CHICAGO MERCANTILE EXCHANGE                 | CFTC COT Lean Hogs         | direct_global_proxy |         0.7  |                  1 |        333 | 2020-01-11 08:00:00 | 2026-05-23 08:00:00 |
| lc.GFEX             | lc.gfex       | LITHIUM HYDROXIDE  - COMMODITY EXCHANGE INC.            | CFTC COT Lithium Hydroxide | new_market_proxy    |         0.45 |                  1 |        145 | 2023-08-19 08:00:00 | 2026-05-23 08:00:00 |
| au.SHFE             | au.shfe       | GOLD - COMMODITY EXCHANGE INC.                          | CFTC COT Gold              | direct_global_proxy |         0.75 |                  1 |        333 | 2020-01-11 08:00:00 | 2026-05-23 08:00:00 |
| cu.SHFE             | cu.shfe       | COPPER- #1 - COMMODITY EXCHANGE INC.                    | CFTC COT Copper            | direct_global_proxy |         0.75 |                  1 |        224 | 2022-02-12 08:00:00 | 2026-05-23 08:00:00 |
| fu.SHFE             | fu.shfe       | FUEL OIL-3% USGC/3.5% FOB RDAM - ICE FUTURES ENERGY DIV | CFTC COT Fuel Oil          | energy_proxy        |         0.5  |                  1 |        226 | 2022-01-29 08:00:00 | 2026-05-23 08:00:00 |
| hc.SHFE             | hc.shfe       | STEEL-HRC - COMMODITY EXCHANGE INC.                     | CFTC COT HRC Steel         | steel_proxy         |         0.55 |                  1 |        224 | 2022-02-12 08:00:00 | 2026-05-23 08:00:00 |
| rb.SHFE             | rb.shfe       | STEEL-HRC - COMMODITY EXCHANGE INC.                     | CFTC COT HRC Steel         | steel_proxy         |         0.55 |                  1 |        224 | 2022-02-12 08:00:00 | 2026-05-23 08:00:00 |

## 状态摘要

| cot_audit_group         |   entry_count |   product_count |   year_count |     pnl_sum |   pnl_mean |   win_count |   big_winner_count |   min_pnl |       max_pnl |   win_rate_pct |   big_winner_rate_pct |   pnl_sign_conflict |
|:------------------------|--------------:|----------------:|-------------:|------------:|-----------:|------------:|-------------------:|----------:|--------------:|---------------:|----------------------:|--------------------:|
| cot_headwind            |           156 |               6 |            5 | 2.53616e+06 |    16257.5 |          75 |                 37 |   -976000 | 852500        |        48.0769 |               23.7179 |                   1 |
| cot_neutral             |           752 |               9 |            7 | 2.72953e+07 |    36296.9 |         297 |                202 |   -515080 |      3.01e+06 |        39.4947 |               26.8617 |                   1 |
| cot_supportive          |           209 |               8 |            6 | 2.14538e+06 |    10265   |          89 |                 25 |   -237600 | 455280        |        42.5837 |               11.9617 |                   1 |
| cot_missing_or_unmapped |          1670 |              14 |            7 | 3.08668e+07 |    18483.1 |         722 |                403 |   -947520 |      2.45e+06 |        43.2335 |               24.1317 |                   1 |

## 条件 OOS 摘要

| condition             | description                                           | feature_family   | candidate_eligible   |   count |   coverage_pct |   source_count |   year_count |   product_count |    total_pnl |   pnl_share_pct |   mean_pnl |   mean_pnl_lift_vs_base |   median_r |   median_r_lift_vs_base |   win_rate_pct |   win_rate_lift_pp |   big_win_rate_pct |   big_win_rate_lift_pp |   oos_test_fold_count |   oos_positive_fold_count |   oos_min_fold_pnl |   oos_total_test_pnl |   oos_min_fold_count | stable_oos_candidate   |
|:----------------------|:------------------------------------------------------|:-----------------|:---------------------|--------:|---------------:|---------------:|-------------:|----------------:|-------------:|----------------:|-----------:|------------------------:|-----------:|------------------------:|---------------:|-------------------:|-------------------:|-----------------------:|----------------------:|--------------------------:|-------------------:|---------------------:|---------------------:|:-----------------------|
| cot_strong_support    | COT managed-money 方向一致分数 >= 0.50                | cftc_cot         | True                 |      59 |         2.117  |             15 |            4 |               5 |  2.12768e+06 |          3.3857 |   36062.4  |                  1.5993 |     0.8182 |                 -2.898  |        66.1017 |            23.6546 |            27.1186 |                 3.1861 |                     4 |                         3 |    -8730           |          2.12768e+06 |                    8 | False                  |
| cot_supportive_direct | COT supportive 且 direct mapping                      | cftc_cot         | True                 |     102 |         3.6598 |             13 |            5 |               4 |  3.04236e+06 |          4.8412 |   29827.1  |                  1.3228 |    -0.1525 |                  0.5402 |        42.1569 |            -0.2902 |            23.5294 |                -0.4031 |                     4 |                         2 |  -866430           |          3.04236e+06 |                   13 | False                  |
| cot_supportive        | COT managed-money 方向一致分数 >= 0.25                | cftc_cot         | True                 |     209 |         7.4991 |             17 |            6 |               8 |  2.14538e+06 |          3.4138 |   10265    |                  0.4552 |    -0.1935 |                  0.6855 |        42.5837 |             0.1367 |            11.9617 |               -11.9708 |                     4 |                         3 |  -214870           |          2.14538e+06 |                   15 | False                  |
| cot_direct_mapping    | 仅直接/较强跨市场映射品种                             | cftc_cot         | True                 |     442 |        15.8593 |             16 |            6 |               4 | -1.43689e+06 |         -2.2865 |   -3250.88 |                 -0.1442 |    -0.3542 |                  1.2545 |        36.1991 |            -6.248  |            15.1584 |                -8.7742 |                     4 |                         1 |       -3.88794e+06 |         -1.56394e+06 |                   64 | False                  |
| cot_matched           | COT 在 45 天内点时化命中；覆盖基线                    | cftc_cot         | False                |    1117 |        40.0789 |             17 |            7 |               9 |  3.19768e+07 |         50.8831 |   28627.4  |                  1.2696 |    -0.3222 |                  1.1413 |        41.2713 |            -1.1758 |            23.6347 |                -0.2978 |                     4 |                         3 |  -423290           |          3.15984e+07 |                   89 | False                  |
| cot_headwind          | COT managed-money 方向一致分数 <= -0.25；只读风险提示 | cftc_cot         | False                |     156 |         5.5974 |             15 |            5 |               6 |  2.53616e+06 |          4.0357 |   16257.5  |                  0.721  |    -0.2778 |                  0.9839 |        48.0769 |             5.6298 |            23.7179 |                -0.2146 |                     4 |                         3 |  -532650           |          2.53616e+06 |                   17 | False                  |

## 覆盖薄弱产品

| product_vt_symbol   |   entry_count |   matched_count |   supportive_count |   headwind_count |          pnl_sum |   pnl_mean |   win_rate_pct |   matched_pct |   supportive_pct |
|:--------------------|--------------:|----------------:|-------------------:|-----------------:|-----------------:|-----------:|---------------:|--------------:|-----------------:|
| MA.CZCE             |           231 |               0 |                  0 |                0 |     -4.65653e+06 |  -20158.1  |        46.3203 |        0      |           0      |
| jm.DCE              |           212 |               0 |                  0 |                0 |      9.54485e+06 |   45022.9  |        55.6604 |        0      |           0      |
| ru.SHFE             |           191 |               0 |                  0 |                0 |      6.13005e+06 |   32094.5  |        49.2147 |        0      |           0      |
| SM.CZCE             |           169 |               0 |                  0 |                0 |      1.50778e+07 |   89218    |        46.1538 |        0      |           0      |
| FG.CZCE             |           161 |               0 |                  0 |                0 |      2.88646e+06 |   17928.3  |        38.5093 |        0      |           0      |
| AP.CZCE             |           153 |               0 |                  0 |                0 |      4.47677e+06 |   29259.9  |        41.8301 |        0      |           0      |
| SA.CZCE             |           110 |               0 |                  0 |                0 |     -1.22894e+06 |  -11172.2  |        40.9091 |        0      |           0      |
| sp.SHFE             |           106 |               0 |                  0 |                0 |     -2.2946e+06  |  -21647.2  |        26.4151 |        0      |           0      |
| SH.CZCE             |            93 |               0 |                  0 |                0 |     -6.43443e+06 |  -69187.4  |        13.9785 |        0      |           0      |
| si.GFEX             |            69 |               0 |                  0 |                0 |      8.32898e+06 |  120710    |        53.6232 |        0      |           0      |
| hc.SHFE             |           114 |              48 |                 24 |                0 |      4.72181e+06 |   41419.4  |        47.3684 |       42.1053 |          21.0526 |
| rb.SHFE             |           120 |              59 |                 39 |                0 | 959440           |    7995.33 |        38.3333 |       49.1667 |          32.5    |
| cu.SHFE             |           156 |             112 |                 39 |               11 |     -6.60137e+06 |  -42316.4  |        16.6667 |       71.7949 |          25      |
| CF.CZCE             |           101 |              97 |                 24 |               24 |      2.96962e+06 |   29402.2  |        63.3663 |       96.0396 |          23.7624 |
| fu.SHFE             |           357 |             357 |                 22 |               14 |      5.24543e+06 |   14693.1  |        40.056  |      100      |           6.1625 |
| lh.DCE              |           141 |             141 |                 19 |               55 |     -4.17316e+06 |  -29596.9  |        28.3688 |      100      |          13.4752 |
| OI.CZCE             |           124 |             124 |                 22 |               44 |      1.07136e+06 |    8640.04 |        54.8387 |      100      |          17.7419 |
| au.SHFE             |            92 |              92 |                 20 |                8 |      4.87312e+06 |   52968.7  |        55.4348 |      100      |          21.7391 |
| lc.GFEX             |            87 |              87 |                  0 |                0 |      2.19469e+07 |  252263    |        51.7241 |      100      |           0      |

## 判断

- COT 命中：`1117/2787`，命中率 `40.0789%`。
- supportive 样本：`209`。
- 稳定 OOS 候选：`[]`。
- 若没有稳定 OOS 候选或覆盖低于 60%，COT 只能保留为外盘温度背景，不能进入 AI 选品、开仓过滤或加减仓。

## 输出

- signals：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage048_cftc_cot_mapping_audit/rebuilt_c9_stage048_cftc_cot_mapping_audit_signals_stage048_cftc_cot_mapping_audit_v1.csv`
- source_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage048_cftc_cot_mapping_audit/rebuilt_c9_stage048_cftc_cot_mapping_audit_source_summary_stage048_cftc_cot_mapping_audit_v1.csv`
- joined：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage048_cftc_cot_mapping_audit/rebuilt_c9_stage048_cftc_cot_mapping_audit_joined_feature_matrix_stage048_cftc_cot_mapping_audit_v1.csv`
- condition_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage048_cftc_cot_mapping_audit/rebuilt_c9_stage048_cftc_cot_mapping_audit_condition_oos_summary_stage048_cftc_cot_mapping_audit_v1.csv`
- feature_coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage048_cftc_cot_mapping_audit/rebuilt_c9_stage048_cftc_cot_mapping_audit_feature_coverage_stage048_cftc_cot_mapping_audit_v1.csv`
- product_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage048_cftc_cot_mapping_audit/rebuilt_c9_stage048_cftc_cot_mapping_audit_product_summary_stage048_cftc_cot_mapping_audit_v1.csv`
- state_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage048_cftc_cot_mapping_audit/rebuilt_c9_stage048_cftc_cot_mapping_audit_state_summary_stage048_cftc_cot_mapping_audit_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage048_cftc_cot_mapping_audit/rebuilt_c9_stage048_cftc_cot_mapping_audit_decision_stage048_cftc_cot_mapping_audit_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage048_cftc_cot_mapping_audit/rebuilt_c9_stage048_cftc_cot_mapping_audit_report_stage048_cftc_cot_mapping_audit_v1.md`
- stage_record：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/stages/20260701_2001_stage048_cftc_cot_mapping_audit.md`

## 反思

- 运行前过拟合反思：否。使用旧线冻结映射、窗口、阈值和发布滞后，只做复验。
- 运行后过拟合反思：否。无论结果好坏，本阶段不调整 COT 映射、窗口、权重、阈值或品种。
- 运行前继续价值反思：有。COT 是仓库里已有的官方外生源，必须在重建线明确排除或确认。
- 运行后继续价值反思：`stop_cot_rule_search_turn_to_domestic_pit_sources`。
