# Stage042 真实现金账本/出入金边界审计

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T09:36:22
- 阶段性质：只读账户现金流边界审计；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：pysystemtrade capital correction/backtesting、TWR/MWR 回报口径、FIA 自动交易风险控制。
- 我的判断：真实现金账本可以约束账户容量、追加保证金、出金/备用金和流动性治理；但外部现金流不能计入策略目标信用，不能证明“任意起点一年以上正收益”或“AI 高质量信号”。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage042_cashflow_boundary_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage042_cashflow_boundary_audit.py`
- 新增参数：`STAGE042_MAX_HEADER_SAMPLE_ROWS=200`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`stage042_cashflow_no_accepted_actual_cash_ledger`
- best_next_direction：`import_actual_broker_or_bank_cashflow_ledger_or_stop_account_layer_route`
- file_count：`474`
- schema_candidate_file_count：`0`
- schema_complete_file_count：`0`
- accepted_cashflow_ledger_count：`0`
- strategy_objective_credit_allowed_count：`0`
- research_artifact_count：`471`
- protected_live_or_config_count：`1`
- immediate_strategy_candidate_count：`0`
- 策略变更：`False`
- true engine：`False`
- order API：`0`
- CTP：`False`

## Summary

| asset_kind                             |   file_count |   total_size_bytes |   schema_candidate_count |   schema_complete_count |   accepted_cashflow_ledger_count |   account_layer_audit_allowed_count |   strategy_objective_credit_allowed_count | blocking_reasons                                  |
|:---------------------------------------|-------------:|-------------------:|-------------------------:|------------------------:|---------------------------------:|------------------------------------:|------------------------------------------:|:--------------------------------------------------|
| cash_code_or_doc                       |            2 |              10037 |                        0 |                       0 |                                0 |                                   0 |                                         0 | code_or_doc_not_actual_cashflow_ledger            |
| protected_live_or_config_cash_artifact |            1 |               3135 |                        0 |                       0 |                                0 |                                   0 |                                         0 | protected_live_or_config_not_research_cash_ledger |
| research_or_backtest_cash_artifact     |          471 |          306646209 |                        0 |                       0 |                                0 |                                   0 |                                         0 | research_artifact_not_actual_cashflow_ledger      |

## 过拟合反思

- 运行前判断：否。本阶段只审计现金流边界，不用现金流修饰收益曲线。
- 运行后判断：否。外部入金/出金被明确排除出策略目标信用，避免把账户行为当 alpha。

## 继续价值反思

- 运行前判断：有。Stage041 后没有同源 replay，新数据缺失时只能确认账户层是否有真实现金账本可做可执行性约束。
- 运行后判断：有限。没有 accepted cashflow ledger 时，账户层也不能继续；若未来导入真实账本，也只能做实盘容量治理，不能替代新 PIT 信号或策略回测目标。

## 输出文件

- inventory：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage042_cashflow_boundary_audit/rebuilt_c9_v2_stage042_cashflow_boundary_audit_inventory_stage042_cashflow_boundary_audit_v1.csv`
- readiness：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage042_cashflow_boundary_audit/rebuilt_c9_v2_stage042_cashflow_boundary_audit_readiness_stage042_cashflow_boundary_audit_v1.csv`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage042_cashflow_boundary_audit/rebuilt_c9_v2_stage042_cashflow_boundary_audit_summary_stage042_cashflow_boundary_audit_v1.csv`
- data_contract：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage042_cashflow_boundary_audit/rebuilt_c9_v2_stage042_cashflow_boundary_audit_data_contract_stage042_cashflow_boundary_audit_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage042_cashflow_boundary_audit/rebuilt_c9_v2_stage042_cashflow_boundary_audit_decision_stage042_cashflow_boundary_audit_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage042_cashflow_boundary_audit/rebuilt_c9_v2_stage042_cashflow_boundary_audit_report_stage042_cashflow_boundary_audit_v1.md`
