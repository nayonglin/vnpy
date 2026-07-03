# Stage050 jd 真承载数据补齐清单

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T10:55:27
- 阶段性质：数据获取 manifest；不回测收益，不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：DCE 鸡蛋期货/期权合约页与交易参数说明。
- 我的判断：DCE 官方合约信息足以确认鸡蛋 size/tick 口径，但保证金会按市场情况调整；当前不能用静态最低保证金或默认 `0.12` 当作 Stage208 级真承载证据。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage050_jd_true_carry_data_manifest.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage050_jd_true_carry_data_manifest.py`
- 新增参数：无交易参数
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`stage050_jd_true_carry_data_manifest_ready_no_strategy_candidate`
- minute_gap_contract_count：`44`
- jd_minute_gap_contract_count：`38`
- contract_spec_request_count：`1`
- ready_for_true_ledger_replay：`False`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## JD Minute Gap

| contract_vt   | product_vt_symbol   | request_start_date   | request_end_date   |   observed_price_rows | required_bar_interval   | required_fields                                                           | preferred_source                  | acceptance_rule                                    | priority                 |
|:--------------|:--------------------|:---------------------|:-------------------|----------------------:|:------------------------|:--------------------------------------------------------------------------|:----------------------------------|:---------------------------------------------------|:-------------------------|
| jd2005.DCE    | jd.DCE              | 2020-01-02           | 2020-04-08         |                    63 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2006.DCE    | jd.DCE              | 2020-04-09           | 2020-05-27         |                    32 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2007.DCE    | jd.DCE              | 2020-05-28           | 2020-06-12         |                    12 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2009.DCE    | jd.DCE              | 2020-06-15           | 2020-08-18         |                    45 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2010.DCE    | jd.DCE              | 2020-08-19           | 2020-09-17         |                    22 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2011.DCE    | jd.DCE              | 2020-09-18           | 2020-10-21         |                    18 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2101.DCE    | jd.DCE              | 2020-10-22           | 2020-12-08         |                    34 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2105.DCE    | jd.DCE              | 2020-12-09           | 2021-04-14         |                    84 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2109.DCE    | jd.DCE              | 2021-04-15           | 2021-08-18         |                    86 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2201.DCE    | jd.DCE              | 2021-08-19           | 2021-12-10         |                    75 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2205.DCE    | jd.DCE              | 2021-12-13           | 2022-04-06         |                    75 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2209.DCE    | jd.DCE              | 2022-04-07           | 2022-08-12         |                    88 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2301.DCE    | jd.DCE              | 2022-08-15           | 2022-12-13         |                    81 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2305.DCE    | jd.DCE              | 2022-12-14           | 2023-04-13         |                    80 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2309.DCE    | jd.DCE              | 2023-04-14           | 2023-08-14         |                    82 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2310.DCE    | jd.DCE              | 2023-08-15           | 2023-09-07         |                    18 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2311.DCE    | jd.DCE              | 2023-09-08           | 2023-10-12         |                    19 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2401.DCE    | jd.DCE              | 2023-10-13           | 2023-12-14         |                    45 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2402.DCE    | jd.DCE              | 2023-12-15           | 2024-01-09         |                    17 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2403.DCE    | jd.DCE              | 2024-01-10           | 2024-02-20         |                    24 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2405.DCE    | jd.DCE              | 2024-02-21           | 2024-04-09         |                    33 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2409.DCE    | jd.DCE              | 2024-04-10           | 2024-08-21         |                    92 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2410.DCE    | jd.DCE              | 2024-08-22           | 2024-09-06         |                    12 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2501.DCE    | jd.DCE              | 2024-09-09           | 2024-12-13         |                    63 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2502.DCE    | jd.DCE              | 2024-12-16           | 2025-01-14         |                    21 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2505.DCE    | jd.DCE              | 2025-01-15           | 2025-04-15         |                    58 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2506.DCE    | jd.DCE              | 2025-04-16           | 2025-05-19         |                    21 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2507.DCE    | jd.DCE              | 2025-05-20           | 2025-06-10         |                    15 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2508.DCE    | jd.DCE              | 2025-06-11           | 2025-07-14         |                    24 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2509.DCE    | jd.DCE              | 2025-07-15           | 2025-08-12         |                    21 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2510.DCE    | jd.DCE              | 2025-08-13           | 2025-09-10         |                    21 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2511.DCE    | jd.DCE              | 2025-09-11           | 2025-10-20         |                    22 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2512.DCE    | jd.DCE              | 2025-10-21           | 2025-11-14         |                    19 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2601.DCE    | jd.DCE              | 2025-11-17           | 2025-12-17         |                    23 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2603.DCE    | jd.DCE              | 2025-12-31           | 2026-02-11         |                    29 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2605.DCE    | jd.DCE              | 2026-03-05           | 2026-04-08         |                    24 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2606.DCE    | jd.DCE              | 2026-04-09           | 2026-05-14         |                    23 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |
| jd2607.DCE    | jd.DCE              | 2026-05-15           | 2026-06-12         |                    21 | 1m                      | bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash | tqsdk_or_vendor_historical_minute | no_fallback_fill_for_2100_2105_or_0900_0905_window | P0_jd_true_carry_blocker |

## Contract Spec Manifest

| product_vt_symbol   |   current_size |   current_price_tick |   current_slippage |   current_margin_ratio | blocking_reason      | static_spec_status                | required_margin_granularity   | required_fields                                                                                                           | preferred_source                                   | acceptance_rule                                          | priority             |
|:--------------------|---------------:|---------------------:|-------------------:|-----------------------:|:---------------------|:----------------------------------|:------------------------------|:--------------------------------------------------------------------------------------------------------------------------|:---------------------------------------------------|:---------------------------------------------------------|:---------------------|
| jd.DCE              |             10 |                    1 |                  1 |                      0 | missing_margin_ratio | size_tick_ready_from_dce_contract | contract_daily                | contract_vt,trade_date,exchange_margin_ratio,broker_margin_ratio,source_system,source_file_hash,publish_or_effective_time | broker_statement_or_vendor_contract_margin_history | margin_ratio_must_be_time_aligned_and_not_default_filled | P0_jd_margin_blocker |

## Source Contract

| dataset_id                             | purpose                                                | required_time_range                                                 | required_fields                                                                                                           | pit_rule                                                                    | acceptance_test                                                                                     |
|:---------------------------------------|:-------------------------------------------------------|:--------------------------------------------------------------------|:--------------------------------------------------------------------------------------------------------------------------|:----------------------------------------------------------------------------|:----------------------------------------------------------------------------------------------------|
| jd_and_tail_contract_minute_1m_history | Stage208 true carry current C9 no-fallback fill replay | per contract request_start_date to request_end_date                 | bar_datetime,vt_symbol,open,high,low,close,volume,open_oi,close_oi,source_file_hash                                       | bar_datetime must be exchange timestamp; no future-published patched values | all Stage049 missing contracts present in 21:00-21:05 or 09:00-09:05 fill windows when orders exist |
| jd_contract_daily_margin_history       | Stage208 true carry current C9 broker10 margin gate    | 2020-01-02 to 2026-06-30 for each jd main contract used by Stage020 | contract_vt,trade_date,exchange_margin_ratio,broker_margin_ratio,source_system,source_file_hash,publish_or_effective_time | margin ratio must be effective on or before trade_date                      | no jd.DCE margin ratio rows default-filled in Stage049 contract spec audit                          |

## 过拟合反思

- 运行前判断：否。本阶段只把 Stage049 阻塞转成数据请求，不产生策略收益曲线。
- 运行后判断：否。清单要求 source_hash、PIT 时间和无默认填充，避免后续用隐性假设救结果。

## 继续价值反思

- 运行前判断：有。Stage049 已把真承载阻塞定位到 jd 规格和分钟线，下一步必须 data-first。
- 运行后判断：有但依赖外部/授权数据。拿到清单里的分钟线和保证金历史前，不应继续 xsmom 真承载回测。

## 输出文件

- minute_gap_manifest：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage050_jd_true_carry_data_manifest/rebuilt_c9_v2_stage050_jd_true_carry_data_manifest_minute_gap_manifest_stage050_jd_true_carry_data_manifest_v1.csv`
- contract_spec_manifest：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage050_jd_true_carry_data_manifest/rebuilt_c9_v2_stage050_jd_true_carry_data_manifest_contract_spec_manifest_stage050_jd_true_carry_data_manifest_v1.csv`
- source_contract：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage050_jd_true_carry_data_manifest/rebuilt_c9_v2_stage050_jd_true_carry_data_manifest_source_contract_stage050_jd_true_carry_data_manifest_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage050_jd_true_carry_data_manifest/rebuilt_c9_v2_stage050_jd_true_carry_data_manifest_decision_stage050_jd_true_carry_data_manifest_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage050_jd_true_carry_data_manifest/rebuilt_c9_v2_stage050_jd_true_carry_data_manifest_report_stage050_jd_true_carry_data_manifest_v1.md`
