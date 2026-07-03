# Stage041 Broker/Production Same-Source Replay Readiness

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T09:29:59
- 阶段性质：只读执行回放数据合同审计；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：Bailey/Lopez de Prado 回测过拟合、Portfolio Optimization 回测危险、QuantStart 交易成本、pysystemtrade backtesting/capital correction。
- 我的判断：同源执行回放可以提升滑点、延迟、部分成交和执行风控建模真实性，但不能作为 alpha 或 AI 选品输入；保护实盘日志、研究 trade_events、脚本/文档都不算 accepted replay。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage041_broker_replay_readiness.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage041_broker_replay_readiness.py`
- 新增参数：`STAGE041_MIN_ACCEPTED_COVERAGE_DAYS=20`、`STAGE041_MAX_HEADER_SAMPLE_ROWS=200`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`stage041_broker_replay_no_accepted_same_source_dataset`
- best_next_direction：`external_authorized_replay_or_real_cash_ledger_audit`
- file_count：`16530`
- schema_candidate_file_count：`0`
- schema_complete_file_count：`0`
- accepted_same_source_replay_count：`0`
- protected_live_log_count：`3`
- research_artifact_count：`16513`
- immediate_strategy_candidate_count：`0`
- 策略变更：`False`
- true engine：`False`
- order API：`0`
- CTP：`False`

## Summary

| asset_kind                    |   file_count |   total_size_bytes |   schema_candidate_count |   schema_complete_count |   accepted_same_source_replay_count |   protected_live_log_count |   research_artifact_count | blocking_reasons                                 |
|:------------------------------|-------------:|-------------------:|-------------------------:|------------------------:|------------------------------------:|---------------------------:|--------------------------:|:-------------------------------------------------|
| configuration_file            |            2 |                363 |                        0 |                       0 |                                   0 |                          0 |                         0 | configuration_file_not_replay_dataset            |
| execution_code_or_doc         |            3 |              26472 |                        0 |                       0 |                                   0 |                          0 |                         0 | code_or_doc_not_replay_dataset                   |
| non_data_replay_hit           |            9 |               1995 |                        0 |                       0 |                                   0 |                          0 |                         0 | not_data_file                                    |
| protected_live_execution_log  |            3 |              13266 |                        0 |                       0 |                                   0 |                          3 |                         0 | protected_live_log_not_signal_source             |
| research_or_backtest_artifact |        16513 |          365820928 |                        0 |                       0 |                                   0 |                          0 |                     16513 | research_backtest_artifact_not_production_replay |

## 过拟合反思

- 运行前判断：否。本阶段只审计 same-source replay 数据合同，不跑收益、不新增交易规则。
- 运行后判断：否。即使发现候选文件，也只允许后续做执行成本校准，不允许作为入场信号。

## 继续价值反思

- 运行前判断：有。Stage040 后缺少 TqSdk 期权链权限，必须确认是否存在同源执行回放可用于提升回测真实性。
- 运行后判断：有但偏工程真实性；若没有 accepted replay，下一步只能导入授权 replay 或转真实现金账本/出入金约束，不能继续拿研究输出救参。

## 输出文件

- inventory：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage041_broker_replay_readiness/rebuilt_c9_v2_stage041_broker_replay_readiness_inventory_stage041_broker_replay_readiness_v1.csv`
- readiness：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage041_broker_replay_readiness/rebuilt_c9_v2_stage041_broker_replay_readiness_readiness_stage041_broker_replay_readiness_v1.csv`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage041_broker_replay_readiness/rebuilt_c9_v2_stage041_broker_replay_readiness_summary_stage041_broker_replay_readiness_v1.csv`
- data_contract：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage041_broker_replay_readiness/rebuilt_c9_v2_stage041_broker_replay_readiness_data_contract_stage041_broker_replay_readiness_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage041_broker_replay_readiness/rebuilt_c9_v2_stage041_broker_replay_readiness_decision_stage041_broker_replay_readiness_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage041_broker_replay_readiness/rebuilt_c9_v2_stage041_broker_replay_readiness_report_stage041_broker_replay_readiness_v1.md`
