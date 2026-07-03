# Stage050 - jd.DCE 逐合约 OI 数据源线内修复

- 记录时间：`2026-07-01T20:20`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage050_jd_contract_oi_source_repair_v1`
- 是否重要突破版本：`否`
- 决策：`stage050_jd_contract_oi_source_gap_repaired_line_local`

## 本次版本变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage050_jd_contract_oi_source_repair.py`
- 新增测试：`tests/test_rebuilt_c9_stage050_jd_oi_source_repair.py`
- 新增参数：`REPAIR_START=2026-03-27`、`MAPPING_FETCH_START=2026-05-01`、`TARGET_END=2026-06-30`、`MONTHS_BEFORE=2`、`MONTHS_AFTER=12`。
- 修改参数：无，官方 C9/15w 配置未改。
- 删除参数：无。
- 新增回测结果：无，本阶段不是收益回测，只做 jd 数据源修复/覆盖审计。
- 共享 mapping CSV 未改；共享 SQLite 数据库未写；不连接 CTP，不调用订单 API，不触发 A/B。

## 调研和判断结论

- TqSdk 支持期货合约日线和 open interest，`KQ.m@DCE.jd` 可用于主力映射；主力规则是数据源构造，不能直接当 alpha。
- 因此 Stage050 先做线内 jd 数据源修复包，为 Stage049 重跑和后续 proxy/true-engine 做准备。

## 覆盖结果

| product_vt_symbol   |   mapping_rows | mapping_start   | mapping_end   |   mapping_contract_count |   bar_rows | bar_start   | bar_end    |   bar_contract_count | mapping_covers_target_end   | bars_cover_target_tminus1   |
|:--------------------|---------------:|:----------------|:--------------|-------------------------:|-----------:|:------------|:-----------|---------------------:|:----------------------------|:----------------------------|
| jd.DCE              |           3073 | 2013-11-08      | 2026-06-30    |                       59 |        751 | 2026-03-27  | 2026-06-30 |                   15 | True                        | True                        |

## 合约状态

| contract_vt_symbol   | status   |   bar_count | min_date   | max_date   | message          |
|:---------------------|:---------|------------:|:-----------|:-----------|:-----------------|
| jd2601.DCE           | empty    |           0 |            |            | no bars returned |
| jd2602.DCE           | empty    |           0 |            |            | no bars returned |
| jd2603.DCE           | empty    |           0 |            |            | no bars returned |
| jd2604.DCE           | fetched  |          21 | 2026-03-27 | 2026-04-27 |                  |
| jd2605.DCE           | fetched  |          39 | 2026-03-27 | 2026-05-26 |                  |
| jd2606.DCE           | fetched  |          60 | 2026-03-27 | 2026-06-25 |                  |
| jd2607.DCE           | fetched  |          63 | 2026-03-27 | 2026-06-30 |                  |
| jd2608.DCE           | fetched  |          63 | 2026-03-27 | 2026-06-30 |                  |
| jd2609.DCE           | fetched  |          63 | 2026-03-27 | 2026-06-30 |                  |
| jd2610.DCE           | fetched  |          63 | 2026-03-27 | 2026-06-30 |                  |
| jd2611.DCE           | fetched  |          63 | 2026-03-27 | 2026-06-30 |                  |
| jd2612.DCE           | fetched  |          63 | 2026-03-27 | 2026-06-30 |                  |
| jd2701.DCE           | fetched  |          63 | 2026-03-27 | 2026-06-30 |                  |
| jd2702.DCE           | fetched  |          63 | 2026-03-27 | 2026-06-30 |                  |
| jd2703.DCE           | fetched  |          63 | 2026-03-27 | 2026-06-30 |                  |
| jd2704.DCE           | fetched  |          42 | 2026-04-28 | 2026-06-30 |                  |
| jd2705.DCE           | fetched  |          24 | 2026-05-27 | 2026-06-30 |                  |
| jd2706.DCE           | fetched  |           3 | 2026-06-26 | 2026-06-30 |                  |

## 输出

- fetched_mapping：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage050_jd_contract_oi_source_repair/rebuilt_c9_stage050_jd_contract_oi_source_repair_fetched_mapping_stage050_jd_contract_oi_source_repair_v1.csv`
- combined_mapping：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage050_jd_contract_oi_source_repair/rebuilt_c9_stage050_jd_contract_oi_source_repair_combined_mapping_stage050_jd_contract_oi_source_repair_v1.csv`
- contract_bars：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage050_jd_contract_oi_source_repair/rebuilt_c9_stage050_jd_contract_oi_source_repair_contract_bars_stage050_jd_contract_oi_source_repair_v1.csv`
- contract_status：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage050_jd_contract_oi_source_repair/rebuilt_c9_stage050_jd_contract_oi_source_repair_contract_status_stage050_jd_contract_oi_source_repair_v1.csv`
- source_coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage050_jd_contract_oi_source_repair/rebuilt_c9_stage050_jd_contract_oi_source_repair_source_coverage_stage050_jd_contract_oi_source_repair_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage050_jd_contract_oi_source_repair/rebuilt_c9_stage050_jd_contract_oi_source_repair_decision_stage050_jd_contract_oi_source_repair_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage050_jd_contract_oi_source_repair/rebuilt_c9_stage050_jd_contract_oi_source_repair_report_stage050_jd_contract_oi_source_repair_v1.md`

## 反思

- 运行前过拟合反思：否。Stage050 只修复 jd.DCE 数据源覆盖，不根据收益选择合约、日期或阈值。
- 运行后过拟合反思：否。本阶段只判断数据源是否覆盖目标终点；若据此直接交易或扫 OI 阈值才是过拟合。
- 运行前继续价值反思：有。Stage049 已出现低自由度 OI 集中度候选，但 jd 缺口阻止目标品种池扩展验证。
- 运行后继续价值反思：有条件。若 jd 映射和逐合约 OI 覆盖到 2026-06-30，下一步才允许重跑 Stage049/冻结一个 proxy。

## 后续规划和 TODO

- 下一步：`rerun_stage049_with_line_local_jd_repair_then_freeze_one_proxy`。
- 若覆盖完整，下一步重跑 Stage049，使用线内 jd 修复包检查数据源缺口是否清除。
- 仍不得直接把 OI 集中度接入 AI 选品、开仓过滤或加风险。
