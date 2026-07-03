# Stage049 - 逐合约 OI 迁移与主力映射 PIT 审计

- 记录时间：`2026-07-01T20:12`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage049_contract_oi_migration_audit_v1`
- 是否重要突破版本：`否`
- 决策：`stage049_contract_oi_migration_candidate_but_source_gap_keep_readonly`

## 本次版本变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage049_contract_oi_migration_audit.py`
- 新增测试：`tests/test_rebuilt_c9_stage049_contract_oi_migration.py`
- 新增参数：`MAX_FEATURE_AGE_DAYS=10`、`EMBARGO_DAYS=20`、`N_SPLITS=4`。
- 修改参数：无，官方 C9/15w 配置未改。
- 删除参数：无。
- 新增回测结果：无，本阶段不是收益回测，只做逐合约 OI 点时审计。
- 本阶段不连接 CTP，不调用订单 API，不触发 A/B。

## 调研和判断结论

- CME OI / Pace of the Roll 资料支持把逐合约 OI 迁移作为换月和流动性质量信息；pysystemtrade/Databento 资料提示 roll rule 应与 alpha 信号隔离。
- 因此 Stage049 不训练模型、不扫阈值，只判断现有 opened flat-entry 样本在逐合约 OI 迁移上的 OOS 稳定性。

## 审计结果

- entry_count：`2787`
- matched：`2787`，matched_rate：`100.0000%`
- stable_conditions：`contract_oi_share_ge50, contract_oi_top2_concentration_ge70, mapping_main_oi_share_ge40`
- source_gap_products：`jd.DCE`

## 条件摘要

| condition                           | candidate_eligible   |   count |    total_pnl |   mean_pnl_lift_vs_base |   win_rate_lift_pp |   oos_positive_fold_count |   oos_test_fold_count |   oos_min_fold_pnl | stable_oos_candidate   |
|:------------------------------------|:---------------------|--------:|-------------:|------------------------:|-------------------:|--------------------------:|----------------------:|-------------------:|:-----------------------|
| contract_oi_share_ge50              | True                 |    2051 |  7.76711e+07 |                  1.6795 |             4.7007 |                         4 |                     4 |        3.44047e+06 | True                   |
| contract_oi_top2_concentration_ge70 | True                 |    2262 |  7.81243e+07 |                  1.5317 |             3.3089 |                         4 |                     4 |        2.16101e+06 | True                   |
| mapping_main_oi_share_ge40          | True                 |    2427 |  6.82901e+07 |                  1.2479 |             2.5467 |                         4 |                     4 |        1.62156e+06 | True                   |
| contract_oi_share_ge33              | True                 |    2654 |  6.26839e+07 |                  1.0474 |             0.2432 |                         3 |                     4 |   -73758.4         | False                  |
| contract_oi_top1                    | True                 |    2655 |  6.20801e+07 |                  1.037  |             0.7168 |                         3 |                     4 |       -1.42048e+06 | False                  |
| contract_oi_mapping_main            | True                 |    2787 |  6.28436e+07 |                  1      |             0      |                         3 |                     4 |       -1.42048e+06 | False                  |
| contract_oi_top2                    | True                 |    2757 |  6.05813e+07 |                  0.9745 |            -0.4086 |                         3 |                     4 |       -1.42048e+06 | False                  |
| contract_oi_tail_rank_ge3           | False                |      30 |  2.26231e+06 |                  3.3443 |            37.5529 |                         1 |                     2 |   -63460           | False                  |
| contract_oi_matched                 | False                |    2787 |  6.28436e+07 |                  1      |             0      |                         3 |                     4 |       -1.42048e+06 | False                  |
| mapping_main_changed_recent_5d      | False                |     294 | -3.24804e+06 |                 -0.4899 |           -25.4403 |                         1 |                     4 |       -3.8483e+06  | False                  |

## 数据源覆盖

| product_vt_symbol   | product_key   |   contract_count |   snapshot_rows | oi_feature_start   | oi_feature_end   |   mapping_rows | mapping_start   | mapping_end   | covers_entry_end_tminus1   | mapping_covers_entry_end   |
|:--------------------|:--------------|-----------------:|----------------:|:-------------------|:-----------------|---------------:|:----------------|:--------------|:---------------------------|:---------------------------|
| AP.CZCE             | ap.czce       |               44 |           10139 | 2019-12-02         | 2026-06-30       |           1593 | 2019-12-02      | 2026-06-30    | True                       | True                       |
| au.SHFE             | au.shfe       |               72 |           11283 | 2019-12-02         | 2026-06-30       |           1593 | 2019-12-02      | 2026-06-30    | True                       | True                       |
| CF.CZCE             | cf.czce       |               37 |            8683 | 2019-12-02         | 2026-06-30       |           1593 | 2019-12-02      | 2026-06-30    | True                       | True                       |
| cu.SHFE             | cu.shfe       |               80 |           17695 | 2019-12-02         | 2026-06-30       |           1593 | 2019-12-02      | 2026-06-30    | True                       | True                       |
| FG.CZCE             | fg.czce       |               72 |           16811 | 2019-12-02         | 2026-06-30       |           1593 | 2019-12-02      | 2026-06-30    | True                       | True                       |
| fu.SHFE             | fu.shfe       |               71 |           16240 | 2019-12-02         | 2026-06-30       |           1593 | 2019-12-02      | 2026-06-30    | True                       | True                       |
| hc.SHFE             | hc.shfe       |               72 |           16637 | 2019-12-02         | 2026-06-30       |           1593 | 2019-12-02      | 2026-06-30    | True                       | True                       |
| jd.DCE              | jd.dce        |               67 |           16083 | 2019-12-02         | 2026-03-26       |           1554 | 2019-12-02      | 2026-04-30    | False                      | False                      |
| jm.DCE              | jm.dce        |               72 |           16016 | 2019-12-02         | 2026-06-30       |           1593 | 2019-12-02      | 2026-06-30    | True                       | True                       |
| lc.GFEX             | lc.gfex       |               30 |            6726 | 2023-07-24         | 2026-06-30       |           1593 | 2019-12-02      | 2026-06-30    | True                       | True                       |
| lh.DCE              | lh.dce        |               31 |            7135 | 2021-01-11         | 2026-06-30       |           1593 | 2019-12-02      | 2026-06-30    | True                       | True                       |
| MA.CZCE             | ma.czce       |               72 |           16813 | 2019-12-02         | 2026-06-30       |           1593 | 2019-12-02      | 2026-06-30    | True                       | True                       |
| OI.CZCE             | oi.czce       |               38 |            8657 | 2019-12-02         | 2026-06-30       |           1593 | 2019-12-02      | 2026-06-30    | True                       | True                       |
| rb.SHFE             | rb.shfe       |               72 |           16844 | 2019-12-02         | 2026-06-30       |           1593 | 2019-12-02      | 2026-06-30    | True                       | True                       |
| ru.SHFE             | ru.shfe       |               59 |           13929 | 2019-12-02         | 2026-06-30       |           1593 | 2019-12-02      | 2026-06-30    | True                       | True                       |
| SA.CZCE             | sa.czce       |               71 |           16722 | 2019-12-09         | 2026-06-30       |           1593 | 2019-12-02      | 2026-06-30    | True                       | True                       |
| SH.CZCE             | sh.czce       |               27 |            6023 | 2023-09-18         | 2026-06-30       |           1593 | 2019-12-02      | 2026-06-30    | True                       | True                       |
| si.GFEX             | si.gfex       |               35 |            7194 | 2022-12-23         | 2026-06-30       |           1593 | 2019-12-02      | 2026-06-30    | True                       | True                       |
| SM.CZCE             | sm.czce       |               73 |           16225 | 2019-12-02         | 2026-06-30       |           1593 | 2019-12-02      | 2026-06-30    | True                       | True                       |
| sp.SHFE             | sp.shfe       |               72 |           16790 | 2019-12-02         | 2026-06-30       |           1593 | 2019-12-02      | 2026-06-30    | True                       | True                       |

## 输出

- snapshots：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage049_contract_oi_migration_audit/rebuilt_c9_stage049_contract_oi_migration_audit_contract_oi_snapshots_stage049_contract_oi_migration_audit_v1.csv`
- joined：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage049_contract_oi_migration_audit/rebuilt_c9_stage049_contract_oi_migration_audit_joined_feature_matrix_stage049_contract_oi_migration_audit_v1.csv`
- condition_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage049_contract_oi_migration_audit/rebuilt_c9_stage049_contract_oi_migration_audit_condition_oos_summary_stage049_contract_oi_migration_audit_v1.csv`
- feature_coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage049_contract_oi_migration_audit/rebuilt_c9_stage049_contract_oi_migration_audit_feature_coverage_stage049_contract_oi_migration_audit_v1.csv`
- product_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage049_contract_oi_migration_audit/rebuilt_c9_stage049_contract_oi_migration_audit_product_summary_stage049_contract_oi_migration_audit_v1.csv`
- source_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage049_contract_oi_migration_audit/rebuilt_c9_stage049_contract_oi_migration_audit_source_summary_stage049_contract_oi_migration_audit_v1.csv`
- state_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage049_contract_oi_migration_audit/rebuilt_c9_stage049_contract_oi_migration_audit_state_summary_stage049_contract_oi_migration_audit_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage049_contract_oi_migration_audit/rebuilt_c9_stage049_contract_oi_migration_audit_decision_stage049_contract_oi_migration_audit_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage049_contract_oi_migration_audit/rebuilt_c9_stage049_contract_oi_migration_audit_report_stage049_contract_oi_migration_audit_v1.md`

## 反思

- 运行前过拟合反思：否。Stage049 不扫收益阈值，只用固定的逐合约 OI 占比、排名、主力映射一致性做点时审计。
- 运行后过拟合反思：否。本阶段只报告固定条件的 OOS 表现和数据覆盖；任何后续按本表反复调 0.33/0.50/0.70 阈值都会变成过拟合。
- 运行前继续价值反思：有。C9 当前损益质量问题可能来自换月/合约流动性细节；这是比外盘 COT 更贴近国内成交路径的可复验信息源。
- 运行后继续价值反思：有条件。若稳定候选非空且数据覆盖完整，下一步只能冻结一个低自由度 proxy 进 true engine；若覆盖或 OOS 不足则继续找更强 PIT 信息源。

## 后续规划和 TODO

- 下一步：`fix_contract_oi_source_gap_before_proxy_engine`。
- 如果稳定候选存在，下一步只能冻结一个低自由度 proxy 进入 true engine，不允许继续扫 OI 阈值。
- 如果覆盖或 OOS 不足，继续找国内 PIT 信息源或修复数据源缺口，不把本阶段条件接入实盘。
