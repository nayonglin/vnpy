# Stage045 - basis/warehouse T+1 PIT 外生特征审计

- 记录时间：`2026-07-01T19:23`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage045_external_pit_basis_warehouse_audit_v1`
- 决策：`stage045_external_pit_candidate_found_requires_proxy_engine`

## 口径

- 只读复用 Stage038 候选级 opened flat-entry 样本，不写交易规则。
- `basis/warehouse` 每条数据只允许在 `data_date + 1` 之后使用；同日入场不得使用同日外生数据。
- 分位数为单品种 expanding percentile，默认至少 `60` 个历史观测后才输出。
- 不改官方 C9、不连接 CTP、不调用订单 API。

## 覆盖

| feature                                    | present   |   non_null_count |   active_count |   coverage_pct |
|:-------------------------------------------|:----------|-----------------:|---------------:|---------------:|
| external_feature_date                      | True      |             2783 |           2783 |        99.8565 |
| external_dom_basis_rate                    | True      |             2630 |           2630 |        94.3667 |
| external_dom_basis_rate_pctile             | True      |             2564 |           2564 |        91.9986 |
| external_warehouse_receipt_quantity        | True      |             1353 |           1353 |        48.5468 |
| external_warehouse_receipt_quantity_pctile | True      |             1279 |           1279 |        45.8916 |
| external_warehouse_change_20d_sum          | True      |             1369 |           1369 |        49.1209 |
| external_tight_inventory_basis_high        | True      |             2787 |             28 |       100      |
| external_inventory_build_basis_low         | True      |             2787 |             39 |       100      |

## 条件 OOS 摘要

| condition                           | description                              | feature_family     | candidate_eligible   |   count |   coverage_pct |   source_count |   year_count |   product_count |    total_pnl |   pnl_share_pct |   mean_pnl |   mean_pnl_lift_vs_base |   median_r |   median_r_lift_vs_base |   win_rate_pct |   win_rate_lift_pp |   big_win_rate_pct |   big_win_rate_lift_pp |   oos_test_fold_count |   oos_positive_fold_count |   oos_min_fold_pnl |   oos_total_test_pnl |   oos_min_fold_count | stable_oos_candidate   |
|:------------------------------------|:-----------------------------------------|:-------------------|:---------------------|--------:|---------------:|---------------:|-------------:|----------------:|-------------:|----------------:|-----------:|------------------------:|-----------:|------------------------:|---------------:|-------------------:|-------------------:|-----------------------:|----------------------:|--------------------------:|-------------------:|---------------------:|---------------------:|:-----------------------|
| external_warehouse_build_20d        | 近 20 个观测日仓单净增加                 | external_warehouse | True                 |     764 |        27.413  |             16 |            6 |              14 |  7.29925e+07 |        116.149  |    95539.9 |                  4.237  |     0.2245 |                 -0.795  |        54.4503 |            12.0032 |            37.4346 |                13.502  |                     4 |                         4 |   126482           |          7.22305e+07 |                   90 | True                   |
| external_warehouse_high_p80         | 仓单量处于本品种历史高 20%               | external_warehouse | True                 |     481 |        17.2587 |             17 |            7 |              12 |  3.5786e+07  |         56.9444 |    74399.1 |                  3.2995 |     0.3983 |                 -1.4108 |        53.4304 |            10.9833 |            35.5509 |                11.6184 |                     4 |                         4 |        1.04994e+06 |          3.57918e+07 |                   37 | True                   |
| external_tight_inventory_basis_high | 低仓单 + 高主力基差率                    | external_combo     | True                 |      28 |         1.0047 |             16 |            2 |               2 |  1.34005e+07 |         21.3236 |   478591   |                 21.2246 |    75.25   |               -266.536  |        78.5714 |            36.1244 |            57.1429 |                33.2103 |                     1 |                         1 |        1.33704e+07 |          1.33704e+07 |                   16 | False                  |
| external_warehouse_low_p20          | 仓单量处于本品种历史低 20%               | external_warehouse | True                 |     106 |         3.8034 |             16 |            4 |               6 |  1.41285e+07 |         22.482  |   133288   |                  5.9111 |    -0.75   |                  2.6565 |        34.9057 |            -7.5414 |            28.3019 |                 4.3693 |                     3 |                         1 |  -657000           |          1.43697e+07 |                    8 | False                  |
| external_basis_high_p80             | 主力基差率处于本品种历史高 20%           | external_basis     | True                 |     794 |        28.4894 |             17 |            7 |              18 |  4.86211e+07 |         77.3684 |    61235.7 |                  2.7157 |     0.3878 |                 -1.3734 |        52.5189 |            10.0718 |            30.2267 |                 6.2942 |                     4 |                         3 |       -3.30967e+06 |          4.76373e+07 |                  139 | False                  |
| external_basis_low_p20              | 主力基差率处于本品种历史低 20%           | external_basis     | True                 |     350 |        12.5583 |             17 |            7 |              15 |  4.41798e+06 |          7.0301 |    12622.8 |                  0.5598 |    -0.2105 |                  0.7457 |        41.4286 |            -1.0185 |            29.4286 |                 5.496  |                     4 |                         3 |  -310470           |          4.30339e+06 |                   39 | False                  |
| external_inventory_build_basis_low  | 高仓单 + 低主力基差率                    | external_combo     | True                 |      39 |         1.3994 |             13 |            1 |               3 | -1.1922e+06  |         -1.8971 |   -30569.2 |                 -1.3557 |    -0.5126 |                  1.8156 |         0      |           -42.4471 |             0      |               -23.9325 |                     1 |                         0 |       -1.1922e+06  |         -1.1922e+06  |                   39 | False                  |
| external_warehouse_draw_20d         | 近 20 个观测日仓单净减少                 | external_warehouse | True                 |     437 |        15.6799 |             16 |            6 |              10 | -1.40662e+07 |        -22.3828 |   -32188   |                 -1.4275 |    -0.5376 |                  1.904  |        28.833  |           -13.6141 |            12.1281 |               -11.8044 |                     4 |                         1 |       -8.44836e+06 |         -1.37361e+07 |                   61 | False                  |
| external_warehouse_available        | warehouse receipt T+1 可用；只作覆盖基线 | external_warehouse | False                |    1353 |        48.5468 |             17 |            7 |              15 |  6.87692e+07 |        109.429  |    50827.2 |                  2.2541 |    -0.1166 |                  0.4128 |        46.3415 |             3.8944 |            29.1944 |                 5.2618 |                     4 |                         3 |       -5.70124e+06 |          6.83441e+07 |                  175 | False                  |
| external_basis_available            | basis T+1 可用；只作覆盖基线             | external_basis     | False                |    2630 |        94.3667 |             17 |            7 |              18 |  5.83129e+07 |         92.7904 |    22172.2 |                  0.9833 |    -0.2823 |                  1      |        42.3954 |            -0.0516 |            23.8783 |                -0.0542 |                     4 |                         3 |       -1.26926e+06 |          5.68623e+07 |                  390 | False                  |

## 覆盖较弱产品

| product_vt_symbol   |   count |        total_pnl |   basis_coverage_pct |   warehouse_coverage_pct |   tight_inventory_basis_high_count |   inventory_build_basis_low_count |
|:--------------------|--------:|-----------------:|---------------------:|-------------------------:|-----------------------------------:|----------------------------------:|
| AP.CZCE             |     153 |      4.47677e+06 |               0      |                 100      |                                  0 |                                 0 |
| CF.CZCE             |     101 |      2.96962e+06 |              96.0396 |                  96.0396 |                                 12 |                                 0 |
| jm.DCE              |     212 |      9.54485e+06 |             100      |                   0      |                                  0 |                                 0 |
| lh.DCE              |     141 |     -4.17316e+06 |             100      |                   0      |                                  0 |                                 0 |
| rb.SHFE             |     120 | 959440           |             100      |                   0      |                                  0 |                                 0 |
| hc.SHFE             |     114 |      4.72181e+06 |             100      |                   0      |                                  0 |                                 0 |
| sp.SHFE             |     106 |     -2.2946e+06  |             100      |                  23.5849 |                                  0 |                                 0 |
| SH.CZCE             |      93 |     -6.43443e+06 |             100      |                  29.0323 |                                  0 |                                 0 |
| au.SHFE             |      92 |      4.87312e+06 |             100      |                  29.3478 |                                  0 |                                 0 |
| cu.SHFE             |     156 |     -6.60137e+06 |             100      |                  36.5385 |                                  0 |                                 0 |
| fu.SHFE             |     357 |      5.24543e+06 |             100      |                  43.1373 |                                  0 |                                 0 |
| ru.SHFE             |     191 |      6.13005e+06 |             100      |                  50.2618 |                                  0 |                                13 |
| MA.CZCE             |     231 |     -4.65653e+06 |             100      |                  63.6364 |                                  0 |                                 0 |
| SM.CZCE             |     169 |      1.50778e+07 |             100      |                  71.5976 |                                  0 |                                13 |
| FG.CZCE             |     161 |      2.88646e+06 |             100      |                  72.0497 |                                  0 |                                 0 |
| OI.CZCE             |     124 |      1.07136e+06 |             100      |                  76.6129 |                                  0 |                                 0 |
| SA.CZCE             |     110 |     -1.22894e+06 |             100      |                  85.4545 |                                  0 |                                 0 |
| lc.GFEX             |      87 |      2.19469e+07 |             100      |                  86.2069 |                                 16 |                                 0 |
| si.GFEX             |      69 |      8.32898e+06 |             100      |                 100      |                                  0 |                                13 |

## 判断

- 稳定 OOS 候选：`['external_warehouse_build_20d', 'external_warehouse_high_p80']`。
- 若稳定候选为空，说明当前固定的 basis/warehouse 低自由度 PIT 条件还不足以直接进入 selector。
- 若存在稳定候选，下一步也只能冻结一个条件做 proxy/真引擎验证，不能扫分位阈值、品种、年份或方向。

## 输出

- feature_matrix：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage045_external_pit_basis_warehouse_audit/rebuilt_c9_stage045_external_pit_basis_warehouse_audit_feature_matrix_stage045_external_pit_basis_warehouse_audit_v1.csv`
- condition_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage045_external_pit_basis_warehouse_audit/rebuilt_c9_stage045_external_pit_basis_warehouse_audit_condition_oos_summary_stage045_external_pit_basis_warehouse_audit_v1.csv`
- feature_coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage045_external_pit_basis_warehouse_audit/rebuilt_c9_stage045_external_pit_basis_warehouse_audit_feature_coverage_stage045_external_pit_basis_warehouse_audit_v1.csv`
- product_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage045_external_pit_basis_warehouse_audit/rebuilt_c9_stage045_external_pit_basis_warehouse_audit_product_summary_stage045_external_pit_basis_warehouse_audit_v1.csv`
- fold_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage045_external_pit_basis_warehouse_audit/rebuilt_c9_stage045_external_pit_basis_warehouse_audit_fold_summary_stage045_external_pit_basis_warehouse_audit_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage045_external_pit_basis_warehouse_audit/rebuilt_c9_stage045_external_pit_basis_warehouse_audit_decision_stage045_external_pit_basis_warehouse_audit_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage045_external_pit_basis_warehouse_audit/rebuilt_c9_stage045_external_pit_basis_warehouse_audit_report_stage045_external_pit_basis_warehouse_audit_v1.md`
- stage_record：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/stages/20260701_1923_stage045_external_pit_basis_warehouse_audit.md`

## 反思

- 运行前过拟合反思：否。本阶段先做 T+1/PIT 审计，不根据收益反推交易规则。
- 运行后过拟合反思：否。结果只说明当前固定条件是否有 OOS 信息量；后续扫 `20/80` 分位、产品、年份或方向才是过拟合。
- 运行前继续价值反思：有。Stage044 找到的外生源必须先点时化，否则不能进入 AI 选品。
- 运行后继续价值反思：取决于稳定候选是否存在；无稳定候选则停止直接 selector，转更宽日级网格或更有理论约束的外生特征。
