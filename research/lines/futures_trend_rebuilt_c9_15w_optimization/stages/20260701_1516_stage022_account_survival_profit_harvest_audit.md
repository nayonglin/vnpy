# Stage022 账户层生存线与利润锁定可行性审计

- 记录时间：`2026-07-01T15:16`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage022_account_survival_profit_harvest_audit_v1`
- 是否重要突破版本：`否`
- 决策：`stage022_profit_harvest_not_enough`

## 本次版本变更

- 新增参数：primary `profit_harvest_threshold=3x capital`、`lock_fraction=0.50`；另有 sensitivity 版本仅作可行性观察。
- 修改参数：无，Stage021/官方 C9 配置未改。
- 删除参数：无。
- 本阶段只读账户层代理，不新增真实交易规则、不接实盘。

## 调研和判断结论

- 外部资料支持账户层波动目标、drawdown control、dynamic lock-in，但也提示保护会牺牲参与度。
- 当前结果证明利润锁定能减少部分负窗口，但不能让所有 `>1` 年窗口转正。
- sensitivity 最好项也未达标，因此不能把阈值/比例继续扫成候选。

## 代理结果

- Stage021 baseline 严格负窗口：`321446`。
- primary 严格负窗口：`310012`。
- primary 严格最差收益：`-42.0358%`。
- primary 到 `2026-06-30` 最差：`18.0338%`。
- primary 收益保留：`10/17`。
- sensitivity 最少负窗口：`stage022_harvest_3x_lock67_sensitivity` = `305800`，最差 `-42.0358%`。

## 策略审计表

| variant                                  | policy_role               |   threshold_mult |   lock_fraction |   negative_window_count |   min_return_pct |   to_final_negative_count |   to_final_min_return_pct |   min_total_return_pct |   median_total_return_pct |   worst_max_dd_pct |   median_max_dd_pct |   retention_pass_count |   retention_rows |     max_deficit |   max_deficit_pct_of_start |
|:-----------------------------------------|:--------------------------|-----------------:|----------------:|------------------------:|-----------------:|--------------------------:|--------------------------:|-----------------------:|--------------------------:|-------------------:|--------------------:|-----------------------:|-----------------:|----------------:|---------------------------:|
| stage022_harvest_3x_lock67_sensitivity   | sensitivity_not_candidate |              3   |            0.67 |                  305800 |         -42.0358 |                         0 |                   13.8302 |                1.90107 |                   272.524 |           -42.0358 |            -23.2812 |                     10 |               17 | 366790          |                    42.0358 |
| stage022_harvest_1p5x_lock50_sensitivity | sensitivity_not_candidate |              1.5 |            0.5  |                  308657 |         -37.5097 |                         0 |                   17.4202 |                1.90107 |                   229.038 |           -37.5097 |            -22.0437 |                     10 |               17 | 418834          |                    37.5097 |
| stage022_harvest_2x_lock50_sensitivity   | sensitivity_not_candidate |              2   |            0.5  |                  308870 |         -42.0358 |                         0 |                   17.6436 |                1.90107 |                   250.678 |           -42.0358 |            -23.1955 |                     10 |               17 | 483000          |                    42.0358 |
| stage022_harvest_3x_lock50_primary       | predeclared_primary       |              3   |            0.5  |                  310012 |         -42.0358 |                         0 |                   18.0338 |                1.90107 |                   273.043 |           -42.0358 |            -23.7752 |                     10 |               17 | 590115          |                    42.0358 |
| stage022_harvest_3x_lock33_sensitivity   | sensitivity_not_candidate |              3   |            0.33 |                  314213 |         -42.0358 |                         0 |                   22.7834 |                1.90107 |                   273.551 |           -42.0358 |            -27.2317 |                     10 |               17 | 942544          |                    42.0358 |
| stage021_combo_stage020_plus_consensus   | baseline                  |            nan   |          nan    |                  321446 |         -42.0358 |                         0 |                   29.8486 |                1.90107 |                   274.508 |           -42.0358 |            -36.4175 |                     17 |               17 |      2.2937e+06 |                    42.0358 |

## 缺口汇总

| variant                                  |   negative_window_count |     max_deficit |   max_deficit_pct_of_start | source_start_month   |
|:-----------------------------------------|------------------------:|----------------:|---------------------------:|:---------------------|
| stage021_combo_stage020_plus_consensus   |                  321446 |      2.2937e+06 |                    42.0358 | ALL                  |
| stage022_harvest_1p5x_lock50_sensitivity |                  308657 | 418834          |                    37.5097 | ALL                  |
| stage022_harvest_2x_lock50_sensitivity   |                  308870 | 483000          |                    42.0358 | ALL                  |
| stage022_harvest_3x_lock33_sensitivity   |                  314213 | 942544          |                    42.0358 | ALL                  |
| stage022_harvest_3x_lock50_primary       |                  310012 | 590115          |                    42.0358 | ALL                  |
| stage022_harvest_3x_lock67_sensitivity   |                  305800 | 366790          |                    42.0358 | ALL                  |

## 文件

- curves: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage022_account_survival_profit_harvest_audit/rebuilt_c9_stage022_account_survival_profit_harvest_audit_curves_stage022_account_survival_profit_harvest_audit_v1.csv`
- summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage022_account_survival_profit_harvest_audit/rebuilt_c9_stage022_account_survival_profit_harvest_audit_summary_stage022_account_survival_profit_harvest_audit_v1.csv`
- goal_aggregate: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage022_account_survival_profit_harvest_audit/rebuilt_c9_stage022_account_survival_profit_harvest_audit_goal_aggregate_stage022_account_survival_profit_harvest_audit_v1.csv`
- goal_to_final: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage022_account_survival_profit_harvest_audit/rebuilt_c9_stage022_account_survival_profit_harvest_audit_goal_to_final_windows_stage022_account_survival_profit_harvest_audit_v1.csv`
- goal_fixed_horizon: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage022_account_survival_profit_harvest_audit/rebuilt_c9_stage022_account_survival_profit_harvest_audit_goal_fixed_horizon_windows_stage022_account_survival_profit_harvest_audit_v1.csv`
- goal_worst_windows: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage022_account_survival_profit_harvest_audit/rebuilt_c9_stage022_account_survival_profit_harvest_audit_goal_worst_windows_stage022_account_survival_profit_harvest_audit_v1.csv`
- deficit_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage022_account_survival_profit_harvest_audit/rebuilt_c9_stage022_account_survival_profit_harvest_audit_deficit_summary_stage022_account_survival_profit_harvest_audit_v1.csv`
- deficit_top_windows: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage022_account_survival_profit_harvest_audit/rebuilt_c9_stage022_account_survival_profit_harvest_audit_deficit_top_windows_stage022_account_survival_profit_harvest_audit_v1.csv`
- retention: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage022_account_survival_profit_harvest_audit/rebuilt_c9_stage022_account_survival_profit_harvest_audit_retention_stage022_account_survival_profit_harvest_audit_v1.csv`
- policy_audit: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage022_account_survival_profit_harvest_audit/rebuilt_c9_stage022_account_survival_profit_harvest_audit_policy_audit_stage022_account_survival_profit_harvest_audit_v1.csv`
- chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage022_account_survival_profit_harvest_audit/rebuilt_c9_stage022_account_survival_profit_harvest_audit_chart_stage022_account_survival_profit_harvest_audit_v1.png`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage022_account_survival_profit_harvest_audit/rebuilt_c9_stage022_account_survival_profit_harvest_audit_decision_stage022_account_survival_profit_harvest_audit_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage022_account_survival_profit_harvest_audit/rebuilt_c9_stage022_account_survival_profit_harvest_audit_report_stage022_account_survival_profit_harvest_audit_v1.md`

## 后续规划和 TODO

- 不继续扫利润锁定阈值/比例；下一步找更早的风险前置信号或真实引擎暂停/恢复机制。
- 若继续账户层路线，需要验证真实成交、保证金、暂停后重启、右尾保留和实盘可执行边界。

## 反思

- 过拟合反思：否。本阶段没有根据 sensitivity 最优项晋级；若挑最少负窗口的阈值直接上线会过拟合。
- 继续价值反思：有，但利润锁定本身不足以达标。下一步应转向更早的风险前置信号、真实引擎级暂停/恢复机制或非价格外生信息。
