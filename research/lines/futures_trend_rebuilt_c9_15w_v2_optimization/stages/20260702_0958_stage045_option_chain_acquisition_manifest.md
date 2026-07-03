# Stage045 vendor/TqSdk 商品期权链导入验收包

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T09:58:28
- 阶段性质：只读数据采购/导入验收；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：TqSdk 专业版/DataDownloader、TqSdk 合约行情历史数据、RQData options、CME Greeks/IV、Databento options。
- 我的判断：vendor 商品期权链是 Stage043 第二优先级的合理新信息源，但本阶段只建立导入验收包；没有 accepted 历史链前不能做 IV/skew 规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage045_option_chain_acquisition_manifest.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage045_option_chain_acquisition_manifest.py`
- 新增参数：`STAGE045_MAX_HEADER_SAMPLE_ROWS=500`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`stage045_option_chain_acquisition_manifest_data_first_no_accepted_dataset`
- best_next_direction：`procure_or_import_vendor_option_chain_history_then_run_acceptance_gate`
- target_product_count：`14`
- jd_included：`True`
- file_count：`50`
- schema_candidate_file_count：`0`
- schema_complete_file_count：`0`
- accepted_option_chain_dataset_count：`0`
- immediate_strategy_candidate_count：`0`
- 策略变更：`False`
- true engine：`False`
- order API：`0`
- CTP：`False`

## Summary

| asset_kind                 |   file_count |   total_size_bytes |   schema_candidate_count |   schema_complete_count |   accepted_option_chain_dataset_count |   pit_rule_audit_allowed_count | blocking_reasons                                                    |
|:---------------------------|-------------:|-------------------:|-------------------------:|------------------------:|--------------------------------------:|-------------------------------:|:--------------------------------------------------------------------|
| research_or_probe_artifact |           50 |            4620059 |                        0 |                       0 |                                     0 |                              0 | research_probe_or_backtest_artifact_not_vendor_option_chain_history |

## Target Product Manifest

| target_product   | product_root   | exchange   | requested_start_date   | requested_end_date   | required_if_listed   | current_rebuilt_ai_pool_hint   | goal_jd_extension   | required_granularity                                   | required_vendor_return                                                      |
|:-----------------|:---------------|:-----------|:-----------------------|:---------------------|:---------------------|:-------------------------------|:--------------------|:-------------------------------------------------------|:----------------------------------------------------------------------------|
| SA.CZCE          | SA             | CZCE       | 2018-01-01             | 2026-06-30           | True                 | True                           | False               | daily_full_chain_minimum; tick_or_1min_quote_preferred | return_empty_with_official_no_listing_flag_if_product_had_no_listed_options |
| si.GFEX          | si             | GFEX       | 2018-01-01             | 2026-06-30           | True                 | True                           | False               | daily_full_chain_minimum; tick_or_1min_quote_preferred | return_empty_with_official_no_listing_flag_if_product_had_no_listed_options |
| FG.CZCE          | FG             | CZCE       | 2018-01-01             | 2026-06-30           | True                 | True                           | False               | daily_full_chain_minimum; tick_or_1min_quote_preferred | return_empty_with_official_no_listing_flag_if_product_had_no_listed_options |
| MA.CZCE          | MA             | CZCE       | 2018-01-01             | 2026-06-30           | True                 | True                           | False               | daily_full_chain_minimum; tick_or_1min_quote_preferred | return_empty_with_official_no_listing_flag_if_product_had_no_listed_options |
| OI.CZCE          | OI             | CZCE       | 2018-01-01             | 2026-06-30           | True                 | True                           | False               | daily_full_chain_minimum; tick_or_1min_quote_preferred | return_empty_with_official_no_listing_flag_if_product_had_no_listed_options |
| jm.DCE           | jm             | DCE        | 2018-01-01             | 2026-06-30           | True                 | True                           | False               | daily_full_chain_minimum; tick_or_1min_quote_preferred | return_empty_with_official_no_listing_flag_if_product_had_no_listed_options |
| AP.CZCE          | AP             | CZCE       | 2018-01-01             | 2026-06-30           | True                 | True                           | False               | daily_full_chain_minimum; tick_or_1min_quote_preferred | return_empty_with_official_no_listing_flag_if_product_had_no_listed_options |
| rb.SHFE          | rb             | SHFE       | 2018-01-01             | 2026-06-30           | True                 | False                          | False               | daily_full_chain_minimum; tick_or_1min_quote_preferred | return_empty_with_official_no_listing_flag_if_product_had_no_listed_options |
| fu.SHFE          | fu             | SHFE       | 2018-01-01             | 2026-06-30           | True                 | True                           | False               | daily_full_chain_minimum; tick_or_1min_quote_preferred | return_empty_with_official_no_listing_flag_if_product_had_no_listed_options |
| SM.CZCE          | SM             | CZCE       | 2018-01-01             | 2026-06-30           | True                 | True                           | False               | daily_full_chain_minimum; tick_or_1min_quote_preferred | return_empty_with_official_no_listing_flag_if_product_had_no_listed_options |
| ru.SHFE          | ru             | SHFE       | 2018-01-01             | 2026-06-30           | True                 | False                          | False               | daily_full_chain_minimum; tick_or_1min_quote_preferred | return_empty_with_official_no_listing_flag_if_product_had_no_listed_options |
| SH.CZCE          | SH             | CZCE       | 2018-01-01             | 2026-06-30           | True                 | False                          | False               | daily_full_chain_minimum; tick_or_1min_quote_preferred | return_empty_with_official_no_listing_flag_if_product_had_no_listed_options |
| lh.DCE           | lh             | DCE        | 2018-01-01             | 2026-06-30           | True                 | False                          | False               | daily_full_chain_minimum; tick_or_1min_quote_preferred | return_empty_with_official_no_listing_flag_if_product_had_no_listed_options |
| jd.DCE           | jd             | DCE        | 2018-01-01             | 2026-06-30           | True                 | False                          | True                | daily_full_chain_minimum; tick_or_1min_quote_preferred | return_empty_with_official_no_listing_flag_if_product_had_no_listed_options |

## Data Contract

| contract_id                           | required_access                                                                                         | required_fields                                                                                                                                                                                                                                                                      | required_pit_checks                                                                                                                                                 | allowed_use                                                                                                                        | forbidden_shortcut                                                               |
|:--------------------------------------|:--------------------------------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-----------------------------------------------------------------------------------------------------------------------------------|:---------------------------------------------------------------------------------|
| vendor_commodity_option_chain_history | TqSdk professional DataDownloader, RQData commodity option APIs, or equivalent authorized vendor export | quote_datetime,publish_datetime/receive_time,underlying_product,underlying_symbol,option_symbol,exchange,expiry_date,strike,option_type,underlying_price,option_price_or_settlement,bid_price,ask_price,implied_volatility,delta,open_interest,volume,source_system,source_file_hash | publish_or_exchange_timestamp,per_file_hash,continuous_calendar_by_product,official_no_listing_flag,call_put_pair_integrity,no_forward_filled_iv_before_publication | readonly IV level/skew/term-structure/stress audit; only after multi-product coverage passes may enter proxy or true engine review | do_not_use_single_day_probe_sparse_year_sample_or_installed_vendor_sdk_as_signal |

## 过拟合反思

- 运行前判断：否。本阶段不构造 IV/skew 规则，只把 vendor 期权链导入前置条件机器化。
- 运行后判断：否。没有 accepted option chain 时继续 data-first，避免把稀疏探针或 SDK 安装状态当信号。

## 继续价值反思

- 运行前判断：有。目标需要更强的 AI 选品和高质量信号，商品期权 IV/skew 是与日线趋势不同的信息源。
- 运行后判断：有但仍受数据约束。Stage045 给出了 jd 在内的目标产品 manifest 和验收合同；拿不到 vendor 历史链时不能进入规则研究。

## 输出文件

- inventory：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage045_option_chain_acquisition_manifest/rebuilt_c9_v2_stage045_option_chain_acquisition_manifest_inventory_stage045_option_chain_acquisition_manifest_v1.csv`
- readiness：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage045_option_chain_acquisition_manifest/rebuilt_c9_v2_stage045_option_chain_acquisition_manifest_readiness_stage045_option_chain_acquisition_manifest_v1.csv`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage045_option_chain_acquisition_manifest/rebuilt_c9_v2_stage045_option_chain_acquisition_manifest_summary_stage045_option_chain_acquisition_manifest_v1.csv`
- target_manifest：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage045_option_chain_acquisition_manifest/rebuilt_c9_v2_stage045_option_chain_acquisition_manifest_target_product_manifest_stage045_option_chain_acquisition_manifest_v1.csv`
- request_manifest：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage045_option_chain_acquisition_manifest/rebuilt_c9_v2_stage045_option_chain_acquisition_manifest_vendor_request_manifest_stage045_option_chain_acquisition_manifest_v1.csv`
- data_contract：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage045_option_chain_acquisition_manifest/rebuilt_c9_v2_stage045_option_chain_acquisition_manifest_data_contract_stage045_option_chain_acquisition_manifest_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage045_option_chain_acquisition_manifest/rebuilt_c9_v2_stage045_option_chain_acquisition_manifest_decision_stage045_option_chain_acquisition_manifest_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage045_option_chain_acquisition_manifest/rebuilt_c9_v2_stage045_option_chain_acquisition_manifest_report_stage045_option_chain_acquisition_manifest_v1.md`
