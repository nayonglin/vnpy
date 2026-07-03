# Stage046 broker/production 同源回放导入验收包

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T10:05:54
- 阶段性质：只读数据导入合同；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：FIX Execution Report、CQG FIX Execution Report、FIA automated trading risk controls、NautilusTrader execution/live reconciliation、QuantStart transaction costs。
- 我的判断：broker/production same-source replay 只适合先做执行成本、延迟、部分成交、撤改和重启对账校准；它不是 AI alpha 输入。缺少 `source_file_hash`、完整信号到持仓时间链、订单状态和账户/持仓对账时，不允许进入回测校准或信号研究。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage046_broker_replay_import_manifest.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage046_broker_replay_import_manifest.py`
- 新增参数：`STAGE046_MAX_HEADER_SAMPLE_ROWS=500`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`stage046_broker_replay_import_manifest_data_first_no_accepted_dataset`
- best_next_direction：`procure_or_export_broker_same_source_replay_then_run_acceptance_gate`
- required_field_count：`25`
- file_count：`16596`
- schema_candidate_file_count：`0`
- schema_complete_file_count：`0`
- accepted_same_source_replay_count：`0`
- protected_preserve_file_count：`3`
- research_artifact_count：`16579`
- immediate_strategy_candidate_count：`0`
- 策略变更：`False`
- true engine：`False`
- order API：`0`
- CTP：`False`

## Summary

| asset_kind                    |   file_count |   total_size_bytes |   schema_candidate_count |   schema_complete_count |   accepted_same_source_replay_count |   protected_live_log_count |   preserve_by_default_count | blocking_reasons                                         |
|:------------------------------|-------------:|-------------------:|-------------------------:|------------------------:|------------------------------------:|---------------------------:|----------------------------:|:---------------------------------------------------------|
| configuration_file            |            2 |                363 |                        0 |                       0 |                                   0 |                          0 |                           0 | configuration_file_not_replay_dataset                    |
| execution_code_or_doc         |            3 |              26472 |                        0 |                       0 |                                   0 |                          0 |                           0 | code_or_doc_not_replay_dataset                           |
| non_data_replay_hit           |            9 |               1995 |                        0 |                       0 |                                   0 |                          0 |                           0 | not_data_file                                            |
| protected_live_evidence_log   |            3 |              13266 |                        0 |                       0 |                                   0 |                          3 |                           3 | preserve_live_or_evidence_log_not_research_import_source |
| research_or_backtest_artifact |        16579 |          383760670 |                        0 |                       0 |                                   0 |                          0 |                           0 | research_backtest_artifact_not_same_source_broker_replay |

## Request Manifest

| required_field   | source_layer            | why_required                                   | required   | request_start_date   | request_end_date                 | acceptance_gate                                                                                           | forbidden_shortcut                                                       |
|:-----------------|:------------------------|:-----------------------------------------------|:-----------|:---------------------|:---------------------------------|:----------------------------------------------------------------------------------------------------------|:-------------------------------------------------------------------------|
| session_id       | session_context         | 区分夜盘/日盘和重启边界                        | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| strategy_version | strategy_signal         | 锁定产生信号的线上策略版本                     | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| signal_time      | strategy_signal         | 计算信号到下单延迟和 PIT 边界                  | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| signal_id        | strategy_signal         | 把信号、计划、订单和成交串起来                 | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| plan_id          | strategy_signal         | 对应 Phase D/submit 前订单草案                 | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| order_time       | order_submission        | 计算下单延迟和订单队列                         | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| order_id         | broker_execution_report | 券商/交易所订单编号                            | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| vt_orderid       | broker_execution_report | vn.py 内部订单编号                             | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| vt_symbol        | broker_execution_report | 合约级执行归因                                 | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| order_status     | broker_execution_report | 区分 accepted/partial/filled/canceled/rejected | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| direction        | order_submission        | 方向与滑点符号                                 | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| offset           | order_submission        | 开平仓归因                                     | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| requested_volume | order_submission        | 部分成交和撤单残量校准                         | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| order_price      | order_submission        | arrival/order price benchmark                  | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| fill_time        | broker_execution_report | 成交时间和排队/延迟校准                        | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| trade_id         | broker_execution_report | 成交唯一编号和撤改冲正去重                     | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| fill_price       | broker_execution_report | 真实成交价                                     | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| fill_volume      | broker_execution_report | 真实成交量                                     | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| commission       | broker_execution_report | 直接成本                                       | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| slippage         | execution_cost          | 相对预期价格的执行偏差                         | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| position_time    | position_reconciliation | 成交后持仓更新时间                             | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| position_after   | position_reconciliation | 对账后的合约净持仓                             | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| account_equity   | account_reconciliation  | 账户权益和保证金容量归因                       | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| source_system    | lineage                 | 确认来自 broker/CTP/SimNow 同源导出            | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |
| source_file_hash | lineage                 | 防止事后改写和重复导入                         | True       | 2026-06-16           | forward_and_historical_available | all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present | do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature |

## Data Contract

| contract_id                          | required_source                                                                             | required_fields                                                                                                                                                                                                                                                                                        | required_checks                                                                                                                       | allowed_use                                                                    | forbidden_shortcut                                                                           |
|:-------------------------------------|:--------------------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:--------------------------------------------------------------------------------------------------------------------------------------|:-------------------------------------------------------------------------------|:---------------------------------------------------------------------------------------------|
| broker_production_same_source_replay | 同一生产/SimNow/CTP链路导出的信号、订单、成交、撤改单、持仓和账户权益事件，不是研究回测输出 | session_id,strategy_version,signal_time,signal_id,plan_id,order_time,order_id,vt_orderid,vt_symbol,order_status,direction,offset,requested_volume,order_price,fill_time,trade_id,fill_price,fill_volume,commission,slippage,position_time,position_after,account_equity,source_system,source_file_hash | signal_time<=order_time<=fill_time<=position_time,source_file_hash,source_system,strategy_version,session_id,no_manual_posthoc_labels | 执行成本、滑点、延迟、部分成交、撤单和重启对账校准；后续仍需只读审计和用户确认 | 保护实盘日志和研究 trade_events 不得直接作为 AI/alpha 特征；缺 hash 或时间链的成交表不得入模 |

## 过拟合反思

- 运行前判断：否。本阶段是数据合同和验收闸门，不跑收益、不扫参数、不产生策略规则。
- 运行后判断：否。输出继续 data-first，保护日志只保留为证据，不被读成 alpha 或训练样本。

## 继续价值反思

- 运行前判断：有。当前本地字段路线已被多次反证，执行回放可帮助判断回测和实盘滑点/部分成交是否偏离。
- 运行后判断：有但前提是拿到同源数据。若没有 accepted replay，下一步应导入券商/SimNow 同源回放或冻结 forward OOS，不能继续用研究 trade_events 救参。

## 输出文件

- inventory：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage046_broker_replay_import_manifest/rebuilt_c9_v2_stage046_broker_replay_import_manifest_inventory_stage046_broker_replay_import_manifest_v1.csv`
- readiness：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage046_broker_replay_import_manifest/rebuilt_c9_v2_stage046_broker_replay_import_manifest_readiness_stage046_broker_replay_import_manifest_v1.csv`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage046_broker_replay_import_manifest/rebuilt_c9_v2_stage046_broker_replay_import_manifest_summary_stage046_broker_replay_import_manifest_v1.csv`
- request_manifest：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage046_broker_replay_import_manifest/rebuilt_c9_v2_stage046_broker_replay_import_manifest_request_manifest_stage046_broker_replay_import_manifest_v1.csv`
- data_contract：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage046_broker_replay_import_manifest/rebuilt_c9_v2_stage046_broker_replay_import_manifest_data_contract_stage046_broker_replay_import_manifest_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage046_broker_replay_import_manifest/rebuilt_c9_v2_stage046_broker_replay_import_manifest_decision_stage046_broker_replay_import_manifest_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage046_broker_replay_import_manifest/rebuilt_c9_v2_stage046_broker_replay_import_manifest_report_stage046_broker_replay_import_manifest_v1.md`
