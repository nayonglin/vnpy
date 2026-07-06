# Stage086 official C9 underwater route evidence

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T17:22:46
- 阶段性质：正式 C9 水下路线证据综合；只读，不新增候选
- 是否重要突破：否，路线排除/下一步选择
- 是否触发A/B：否，本阶段不提出接入正式版候选

## 外部调研与判断

- 本轮外部调研提示趋势系统长期水下和回撤期是结构性成本，常见改善方向是分散、独立收益腿、波动/资金治理；但本仓库已有 cash/account overlay 与 stop/retry/budget lock 证据必须先复用。
- 本阶段判断：不继续在 stop/retry、同日重进、C10 budget lock、简单回撤刹车上扫参；下一步应转向独立收益腿真承载或真实暴露归因。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage086_official_c9_underwater_route_evidence.py`
- 新增参数：无交易参数。
- 修改参数：无。
- 删除参数：无。

## 结果

- Stage167 起点数：`17`；2020+ 起点数：`13`。
- 最差最大回撤：`-56.2069%`。
- 最大水下天数：`500`；最大连续水下天数：`387`。

### Stage167 Worst Paths

| requested_start_month   |   total_return_pct |   max_drawdown_pct |   days_below_initial |   max_consecutive_below_initial_days | drawdown_peak_date   | drawdown_trough_date   |   max_broker10_margin_to_equity_pct |   broker10_days_gt70 |
|:------------------------|-------------------:|-------------------:|---------------------:|-------------------------------------:|:---------------------|:-----------------------|------------------------------------:|---------------------:|
| 2018-01                 |           8471.44  |           -56.2069 |                  384 |                                  116 | 2022-07-15           | 2023-07-05             |                             91.495  |                   58 |
| 2019-01                 |           9084.65  |           -55.7845 |                  127 |                                  110 | 2022-07-15           | 2023-07-05             |                             96.6295 |                   51 |
| 2020-01                 |           3886.19  |           -55.3701 |                   20 |                                   17 | 2022-07-15           | 2023-07-05             |                             88.3398 |                   36 |
| 2018-07                 |           9833.65  |           -55.3357 |                   88 |                                   80 | 2022-07-15           | 2023-07-05             |                             89.9439 |                   59 |
| 2022-07                 |            203.642 |           -55.1835 |                   60 |                                   60 | 2022-07-15           | 2023-07-05             |                             72.7529 |                    2 |
| 2019-07                 |           5156.61  |           -54.8159 |                    4 |                                    4 | 2022-07-15           | 2023-07-05             |                             87.0606 |                   32 |
| 2020-07                 |           3147.57  |           -54.7368 |                    0 |                                    0 | 2022-07-15           | 2023-07-05             |                             85.9526 |                   28 |
| 2021-01                 |           1496.83  |           -54.318  |                    0 |                                    0 | 2022-07-15           | 2023-07-05             |                             80.7461 |                   17 |

### Evidence Table

| evidence_id                            | source                                                                                                                                                                                                                                                                                           | observation                                                                                                                                       | implication                                                                                                    | supports_next_route                              |   aux_rows |
|:---------------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:--------------------------------------------------------------------------------------------------------------------------------------------------|:---------------------------------------------------------------------------------------------------------------|:-------------------------------------------------|-----------:|
| stage167_current_c9_path_shape         | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv                                                                                                  | 17 starts; worst max DD -56.2069%, max days below initial 500, max consecutive below 387                                                          | C9 right tail is strong but water experience is concentrated in a few long cold-start paths.                   | path_attribution_not_cash_overlay                |        nan |
| stage167_worst_starts                  | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage086_official_c9_underwater_route_evidence/rebuilt_c9_v2_stage086_official_c9_underwater_route_evidence_stage167_path_metrics_stage086_official_c9_underwater_route_evidence_v1.csv | 2018-01:DD=-56.21%,water=384; 2019-01:DD=-55.78%,water=127; 2020-01:DD=-55.37%,water=20; 2018-07:DD=-55.34%,water=88; 2022-07:DD=-55.18%,water=60 | The most painful paths are not a single date-only anomaly, but repeated cold-start/denominator stress.         | multi_start_structural_filter_or_sleeve          |        nan |
| stage158_stop_retry_not_main_dd_driver | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage158_current_rebuild_c9_c4_drawdown_pressure_attribution_window_summary_stage158_current_rebuild_c9_c4_drawdown_pressure_attribution_v1.csv                                                    | Stage158 C9 max-DD windows: 7/9 rows have zero stop/retry events; event sum=2.                                                                    | Do not keep scanning stop/retry R multiple, retry count or same-day retry shape for the main water problem.    | stop_retry_route_deprioritized                   |        nan |
| stage158_event_windows_are_sparse      | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage158_current_rebuild_c9_c4_drawdown_pressure_attribution_event_window_summary_stage158_current_rebuild_c9_c4_drawdown_pressure_attribution_v1.csv                                              | Event-window rows=18, total event_count=11.                                                                                                       | Stop/retry diagnostics remain useful for execution safety, not for broad underwater reduction.                 | execution_safety_only                            |        nan |
| stage848_peak_trough_pressure          | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage848_stage847_c9_peak_trough_forensics_window_summary_stage848_stage847_c9_peak_trough_forensics_v1.csv                                                                                        | Peak-trough C9 window cum net pnl=-5010930, trade_count=40, max broker10=100.49%.                                                                 | The known bad window is a holding/exposure pressure problem, not just entry-day execution.                     | position_exposure_attribution                    |        nan |
| stage848_c9_minus_c4_delta             | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage848_stage847_c9_peak_trough_forensics_window_summary_stage848_stage847_c9_peak_trough_forensics_v1.csv                                                                                        | C9-C4 peak-to-trough equity delta=-1709745, window net pnl delta=-1516825, slippage delta=58600.                                                  | C9 extra right-tail machinery also creates exposure/denominator risk in bad windows.                           | structural_sleeve_or_true_exposure_governance    |        nan |
| stage848_pressure_days                 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage848_stage847_c9_peak_trough_forensics_pressure_days_stage848_stage847_c9_peak_trough_forensics_v1.csv                                                                                         | Pressure-day rows=20; top rows show concentrated product-direction exposure and broker10 stress.                                                  | If a future rule is tried, it should be validated as exposure concentration governance, not product blacklist. | exposure_concentration_governance_readonly_first |        nan |
| stage863_budget_lock_no_effect         | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage863_stage847_c10_budget_lock_engine_summary_stage863_stage847_c10_budget_lock_engine_v1.csv                                                                                                   | Stage863 C10 budget lock path was identical to C9; lock created/released but no reduce/block.                                                     | Do not repeat same stop-retry budget-lock shape; it is already falsified.                                      | budget_lock_route_deprioritized                  |          1 |
| stage863_budget_lock_events_no_reduce  | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage863_stage847_c10_budget_lock_engine_budget_lock_events_stage863_stage847_c10_budget_lock_engine_v1.csv                                                                                        | budget events created=100, released=100, reduced=0, block_like=0.                                                                                 | The lock accounting was active, but it did not actually reduce or block exposure.                              | budget_lock_route_deprioritized                  |        200 |
| stage863_comparison_available          | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage863_stage847_c10_budget_lock_engine_comparison_stage863_stage847_c10_budget_lock_engine_v1.csv                                                                                                | Stage863 comparison rows=3 available for audit.                                                                                                   | Existing full-engine comparison should be reused rather than rerunning the same C10 shape.                     | reuse_prior_negative_result                      |        nan |
| stage049_true_carry_blocker            | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage049_stage208_true_carry_replay_gate/rebuilt_c9_v2_stage049_stage208_true_carry_replay_gate_decision_stage049_stage208_true_carry_replay_gate_v1.json                               | contract_specs_exact:missing_exact_specs:jd.DCE;current_minute_fill_bars:missing_minute_contracts:39                                              | Independent xsmom true-carry remains the more structural route, but data blockers must be cleared first.       | stage208_true_carry_data_first                   |        nan |

## 结论

- 决策：`stage086_stop_retry_heat_budget_routes_deprioritized_next_true_sleeve_or_exposure_data`。
- 关键判断：Stage158 显示 C9 最大回撤窗口里的 stop/retry 事件稀疏，Stage863 budget lock 已经无效，Stage848 指向持仓/暴露压力；所以不能继续做 stop/retry 参数、预算锁或简单回撤刹车救参。
- 审计加固：Stage049 blocker 字符串展示已修正；Stage863 budget lock 额外引用 budget_lock_events；输入文件 size/mtime/sha256 已固化。
- 下一步：优先清理 Stage208/xsmom 真承载数据阻塞；若做 exposure governance，必须先做全路径持仓暴露归因，不能直接按产品/日期/方向黑名单。

## 独立 Agent 评估

- 评估 agent：`019f3192-a2d4-7ba3-b130-4709daf2012d`。
- 结论：未发现严重问题；主结论成立；置信度 `0.86`。
- 复核结果：Stage167 起点 `17`、2020+ 起点 `13`、最差最大回撤 `-56.206935956180295%`、最大水下天数 `500`、最大连续水下天数 `387` 均复算一致。
- 关键审计意见：Stage086 只能证明 stop/retry、同日重进、Stage863 budget lock 降优先级；不能直接证明某个 exposure governance 规则有效。
- 已处理问题：Stage049 blocker 字符串展示 bug；Stage863 budget_lock_events 引用；输入文件 hash/mtime 固化。

## 回测记录字段

- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率；仅汇总 Stage167 和既有法证阶段。

## 过拟合反思

- 运行前：否。只读冻结证据，不新增规则。
- 运行后：否。结论是排除已弱证据路线，不按亏损日期/产品救参。

## 继续价值反思

- 运行前：有。Stage085 收束现金路线后，必须确定下一轮是否还值得做 stop/retry/预算锁。
- 运行后：有，但方向明确切换到独立收益腿真承载或真实暴露归因。

## 输出

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage086_official_c9_underwater_route_evidence/rebuilt_c9_v2_stage086_official_c9_underwater_route_evidence_report_stage086_official_c9_underwater_route_evidence_v1.md`
- path_metrics：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage086_official_c9_underwater_route_evidence/rebuilt_c9_v2_stage086_official_c9_underwater_route_evidence_stage167_path_metrics_stage086_official_c9_underwater_route_evidence_v1.csv`
- evidence：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage086_official_c9_underwater_route_evidence/rebuilt_c9_v2_stage086_official_c9_underwater_route_evidence_evidence_table_stage086_official_c9_underwater_route_evidence_v1.csv`
- input_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage086_official_c9_underwater_route_evidence/rebuilt_c9_v2_stage086_official_c9_underwater_route_evidence_input_audit_stage086_official_c9_underwater_route_evidence_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage086_official_c9_underwater_route_evidence/rebuilt_c9_v2_stage086_official_c9_underwater_route_evidence_decision_stage086_official_c9_underwater_route_evidence_v1.json`
