# Stage051 - 修复 jd 源后的逐合约 OI 迁移重跑

- 记录时间：`2026-07-01T20:23`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage051_contract_oi_repaired_rerun_v1`
- 是否重要突破版本：`否`
- 决策：`stage051_contract_oi_migration_source_gap_still_open`

## 本次版本变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage051_contract_oi_repaired_rerun.py`
- 新增测试：`tests/test_rebuilt_c9_stage051_repaired_contract_oi.py`
- 新增参数：无，复用 Stage049 固定条件和 Stage050 数据修复包。
- 修改参数：无，官方 C9/15w 配置未改。
- 删除参数：无。
- 新增回测结果：无，本阶段不是收益回测，只做修复源后的候选级审计重跑。
- 共享 mapping CSV 未改；共享 SQLite 数据库未写；不连接 CTP，不调用订单 API，不触发 A/B。

## 审计结果

- entry_count：`2787`
- matched：`2787`，matched_rate：`100.0000%`
- stable_conditions：`contract_oi_share_ge50, contract_oi_top2_concentration_ge70`
- source_gap_products：`jd.DCE`

## 条件摘要

| condition                           | candidate_eligible   |   count |   total_pnl |   mean_pnl_lift_vs_base |   win_rate_lift_pp |   oos_positive_fold_count |   oos_test_fold_count |   oos_min_fold_pnl | stable_oos_candidate   |
|:------------------------------------|:---------------------|--------:|------------:|------------------------:|-------------------:|--------------------------:|----------------------:|-------------------:|:-----------------------|
| contract_oi_share_ge50              | True                 |    2051 | 7.76711e+07 |                  1.6795 |             4.7007 |                         4 |                     4 |        3.44047e+06 | True                   |
| contract_oi_top2_concentration_ge70 | True                 |    2262 | 7.81243e+07 |                  1.5317 |             3.3089 |                         4 |                     4 |        2.16101e+06 | True                   |
| contract_oi_share_ge33              | True                 |    2654 | 6.26839e+07 |                  1.0474 |             0.2432 |                         3 |                     4 |   -73758.4         | False                  |
| contract_oi_top1                    | True                 |    2655 | 6.20801e+07 |                  1.037  |             0.7168 |                         3 |                     4 |       -1.42048e+06 | False                  |
| contract_oi_top2                    | True                 |    2757 | 6.05813e+07 |                  0.9745 |            -0.4086 |                         3 |                     4 |       -1.42048e+06 | False                  |
| contract_oi_mapping_main            | True                 |       0 | 0           |                  0      |                    |                         0 |                     0 |                    | False                  |
| mapping_main_oi_share_ge40          | True                 |       0 | 0           |                  0      |                    |                         0 |                     0 |                    | False                  |
| contract_oi_tail_rank_ge3           | False                |      30 | 2.26231e+06 |                  3.3443 |            37.5529 |                         1 |                     2 |   -63460           | False                  |
| contract_oi_matched                 | False                |    2787 | 6.28436e+07 |                  1      |             0      |                         3 |                     4 |       -1.42048e+06 | False                  |
| mapping_main_changed_recent_5d      | False                |       0 | 0           |                  0      |                    |                         0 |                     0 |                    | False                  |

## 数据源覆盖

| product_vt_symbol   | product_key   |   contract_count |   snapshot_rows | oi_feature_start   | oi_feature_end   |   mapping_rows | mapping_start   | mapping_end   | covers_entry_end_tminus1   | mapping_covers_entry_end   |
|:--------------------|:--------------|-----------------:|----------------:|:-------------------|:-----------------|---------------:|:----------------|:--------------|:---------------------------|:---------------------------|
| AP.CZCE             | ap.czce       |               44 |           10139 | 2019-12-02         | 2026-06-30       |              1 | 2026-06-30      | 2026-06-30    | True                       | True                       |
| au.SHFE             | au.shfe       |               72 |           11283 | 2019-12-02         | 2026-06-30       |              1 | 2026-06-30      | 2026-06-30    | True                       | True                       |
| CF.CZCE             | cf.czce       |               37 |            8683 | 2019-12-02         | 2026-06-30       |              1 | 2026-06-30      | 2026-06-30    | True                       | True                       |
| cu.SHFE             | cu.shfe       |               80 |           17695 | 2019-12-02         | 2026-06-30       |              1 | 2026-06-30      | 2026-06-30    | True                       | True                       |
| FG.CZCE             | fg.czce       |               72 |           16811 | 2019-12-02         | 2026-06-30       |              1 | 2026-06-30      | 2026-06-30    | True                       | True                       |
| fu.SHFE             | fu.shfe       |               71 |           16240 | 2019-12-02         | 2026-06-30       |              1 | 2026-06-30      | 2026-06-30    | True                       | True                       |
| hc.SHFE             | hc.shfe       |               72 |           16637 | 2019-12-02         | 2026-06-30       |              1 | 2026-06-30      | 2026-06-30    | True                       | True                       |
| jd.DCE              | jd.dce        |               67 |           16083 | 2019-12-02         | 2026-03-26       |           4002 | 2010-01-04      | 2026-06-30    | False                      | True                       |
| jm.DCE              | jm.dce        |               72 |           16016 | 2019-12-02         | 2026-06-30       |              1 | 2026-06-30      | 2026-06-30    | True                       | True                       |
| lc.GFEX             | lc.gfex       |               30 |            6726 | 2023-07-24         | 2026-06-30       |              1 | 2026-06-30      | 2026-06-30    | True                       | True                       |
| lh.DCE              | lh.dce        |               31 |            7135 | 2021-01-11         | 2026-06-30       |              1 | 2026-06-30      | 2026-06-30    | True                       | True                       |
| MA.CZCE             | ma.czce       |               72 |           16813 | 2019-12-02         | 2026-06-30       |              1 | 2026-06-30      | 2026-06-30    | True                       | True                       |
| OI.CZCE             | oi.czce       |               38 |            8657 | 2019-12-02         | 2026-06-30       |              1 | 2026-06-30      | 2026-06-30    | True                       | True                       |
| rb.SHFE             | rb.shfe       |               72 |           16844 | 2019-12-02         | 2026-06-30       |              1 | 2026-06-30      | 2026-06-30    | True                       | True                       |
| ru.SHFE             | ru.shfe       |               59 |           13929 | 2019-12-02         | 2026-06-30       |              1 | 2026-06-30      | 2026-06-30    | True                       | True                       |
| SA.CZCE             | sa.czce       |               71 |           16722 | 2019-12-09         | 2026-06-30       |              1 | 2026-06-30      | 2026-06-30    | True                       | True                       |
| SH.CZCE             | sh.czce       |               27 |            6023 | 2023-09-18         | 2026-06-30       |              1 | 2026-06-30      | 2026-06-30    | True                       | True                       |
| si.GFEX             | si.gfex       |               35 |            7194 | 2022-12-23         | 2026-06-30       |              1 | 2026-06-30      | 2026-06-30    | True                       | True                       |
| SM.CZCE             | sm.czce       |               73 |           16225 | 2019-12-02         | 2026-06-30       |              1 | 2026-06-30      | 2026-06-30    | True                       | True                       |
| sp.SHFE             | sp.shfe       |               72 |           16790 | 2019-12-02         | 2026-06-30       |              1 | 2026-06-30      | 2026-06-30    | True                       | True                       |

## 输出

- snapshots：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage051_contract_oi_repaired_rerun/rebuilt_c9_stage051_contract_oi_repaired_rerun_contract_oi_snapshots_stage051_contract_oi_repaired_rerun_v1.csv`
- joined：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage051_contract_oi_repaired_rerun/rebuilt_c9_stage051_contract_oi_repaired_rerun_joined_feature_matrix_stage051_contract_oi_repaired_rerun_v1.csv`
- condition_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage051_contract_oi_repaired_rerun/rebuilt_c9_stage051_contract_oi_repaired_rerun_condition_oos_summary_stage051_contract_oi_repaired_rerun_v1.csv`
- feature_coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage051_contract_oi_repaired_rerun/rebuilt_c9_stage051_contract_oi_repaired_rerun_feature_coverage_stage051_contract_oi_repaired_rerun_v1.csv`
- product_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage051_contract_oi_repaired_rerun/rebuilt_c9_stage051_contract_oi_repaired_rerun_product_summary_stage051_contract_oi_repaired_rerun_v1.csv`
- source_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage051_contract_oi_repaired_rerun/rebuilt_c9_stage051_contract_oi_repaired_rerun_source_summary_stage051_contract_oi_repaired_rerun_v1.csv`
- state_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage051_contract_oi_repaired_rerun/rebuilt_c9_stage051_contract_oi_repaired_rerun_state_summary_stage051_contract_oi_repaired_rerun_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage051_contract_oi_repaired_rerun/rebuilt_c9_stage051_contract_oi_repaired_rerun_decision_stage051_contract_oi_repaired_rerun_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage051_contract_oi_repaired_rerun/rebuilt_c9_stage051_contract_oi_repaired_rerun_report_stage051_contract_oi_repaired_rerun_v1.md`

## 反思

- 运行前过拟合反思：否。Stage051 只用 Stage050 的线内修复包重跑固定 Stage049 条件，不新增阈值或收益筛选。
- 运行后过拟合反思：否。本阶段仍未写交易规则；后续只能冻结一个条件，不能围绕 OI 占比阈值救参。
- 运行前继续价值反思：有。只有确认 jd 数据源缺口清零，逐合约 OI 集中度候选才有资格进入下一步 proxy。
- 运行后继续价值反思：有条件。若 source_gap_products 清零且稳定候选仍在，下一步可做一个低自由度 proxy。

## 后续规划和 TODO

- 下一步：`repair_remaining_source_gap_or_stop_contract_oi_route`。
- 若进入 proxy，只能冻结 `contract_oi_share_ge50` 等一个低自由度条件，不允许扫 OI 阈值。
