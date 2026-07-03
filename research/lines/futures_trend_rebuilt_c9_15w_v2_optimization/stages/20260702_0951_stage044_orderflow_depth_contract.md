# Stage044 授权 orderflow/depth 数据合同与本地 readiness 审计

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T09:51:51
- 阶段性质：只读数据合同/readiness；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：CME Market by Order、Databento MBO/MBP-10 schema、HftBacktest order book imbalance、LOB signal extraction 研究。
- 我的判断：orderflow/depth 是当前 C9 本地字段之外的优先新信息源，但必须先拿到授权 MBP10/MBO 历史和 hash；分钟线、研究 trade_events、保护日志都不能替代。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage044_orderflow_depth_contract.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage044_orderflow_depth_contract.py`
- 新增参数：`STAGE044_MAX_HEADER_SAMPLE_ROWS=500`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`stage044_orderflow_depth_no_accepted_dataset_data_contract_only`
- best_next_direction：`import_authorized_mbp10_or_mbo_history_with_hashes_or_keep_route_blocked`
- file_count：`5524`
- schema_candidate_file_count：`0`
- schema_complete_file_count：`0`
- accepted_orderflow_dataset_count：`0`
- minute_or_bar_cache_count：`4237`
- research_artifact_count：`5058`
- protected_live_or_config_count：`0`
- immediate_strategy_candidate_count：`0`
- 策略变更：`False`
- true engine：`False`
- order API：`0`
- CTP：`False`

## Summary

| asset_kind                    |   file_count |   total_size_bytes |   schema_candidate_count |   schema_complete_count |   accepted_orderflow_dataset_count |   pit_rule_audit_allowed_count | blocking_reasons                                         |
|:------------------------------|-------------:|-------------------:|-------------------------:|------------------------:|-----------------------------------:|-------------------------------:|:---------------------------------------------------------|
| minute_ohlcv_or_bar_cache     |          466 |            3714691 |                        0 |                       0 |                                  0 |                              0 | bars_do_not_contain_book_queue_or_depth_events           |
| research_or_backtest_artifact |         5058 |         2014745401 |                        0 |                       0 |                                  0 |                              0 | research_or_backtest_artifact_not_orderflow_depth_source |

## Data Contract

| contract_id                       | schema_family   | required_fields                                                                                                                 | required_checks                                                                                                                                                          | allowed_use                                                                                                | forbidden_shortcut                                                |
|:----------------------------------|:----------------|:--------------------------------------------------------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-----------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------|
| authorized_mbp10_depth_history    | mbp10           | ts_event,ts_recv,vt_symbol/instrument_id,bid_px_00..09,ask_px_00..09,bid_sz_00..09,ask_sz_00..09,source_system,source_file_hash | exchange_event_time_before_signal,receive_or_publish_time_present,continuous_target_pool_calendar,per_file_hash,roll_symbol_mapping,session_filter,cost_latency_join_key | PIT depth imbalance, micro-price, VAMP, liquidity stress and entry quality audit after coverage validation | do_not_use_minute_bars_or_research_trade_events_as_l2_depth_proxy |
| authorized_mbo_full_depth_history | mbo             | ts_event,ts_recv,vt_symbol/instrument_id,order_id,action,side,price,size,source_system,source_file_hash                         | book_replay_reconstructable,add_cancel_modify_trade_actions,queue_position_replay,exchange_event_time_before_signal,per_file_hash,continuous_target_pool_calendar        | queue pressure, cancellation imbalance, large order persistence and passive fill/adverse selection audit   | do_not_infer_queue_position_from_l1_or_ohlcv                      |

## 过拟合反思

- 运行前判断：否。本阶段不回测、不挑阈值，只检查 Stage043 第一优先级数据路线是否真的可用。
- 运行后判断：否。若无 accepted orderflow dataset，继续保持 data-first，避免用分钟线或研究成交事件制造伪微观结构特征。

## 继续价值反思

- 运行前判断：有。目标需要更强的高质量信号识别，orderflow/depth 是结构上不同于日线/AI桶的外生信息源。
- 运行后判断：有但取决于数据。没有授权 MBP10/MBO 历史时不能进入信号审计；若后续导入，下一步先做只读 PIT 深度特征审计，再决定是否进入真实引擎。

## 输出文件

- inventory：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage044_orderflow_depth_contract/rebuilt_c9_v2_stage044_orderflow_depth_contract_inventory_stage044_orderflow_depth_contract_v1.csv`
- readiness：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage044_orderflow_depth_contract/rebuilt_c9_v2_stage044_orderflow_depth_contract_readiness_stage044_orderflow_depth_contract_v1.csv`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage044_orderflow_depth_contract/rebuilt_c9_v2_stage044_orderflow_depth_contract_summary_stage044_orderflow_depth_contract_v1.csv`
- data_contract：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage044_orderflow_depth_contract/rebuilt_c9_v2_stage044_orderflow_depth_contract_data_contract_stage044_orderflow_depth_contract_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage044_orderflow_depth_contract/rebuilt_c9_v2_stage044_orderflow_depth_contract_decision_stage044_orderflow_depth_contract_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage044_orderflow_depth_contract/rebuilt_c9_v2_stage044_orderflow_depth_contract_report_stage044_orderflow_depth_contract_v1.md`
