# Stage428 Recovery All Cases RSI Confirmation

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-08 15:55 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / 当前工作区
- 阶段性质：Stage421 all-cases recovery 的趋势强度确认消融
- 是否重要突破：否；这是重要负结论
- 是否触发A/B：已按 `skills/version-ab-experiment/SKILL.md` 做 A/C 验证；因硬失败，不进入正式 A/B

## 外部调研与判断

- 参考资料：
  - Concretum Group, Position Sizing in Trend-Following: https://concretumgroup.com/position-sizing-in-trend-following-comparing-volatility-targeting-volatility-parity-and-pyramiding/
  - QuantConnect, Futures Trend Following and Carry in Different Risk Regimes: https://www.quantconnect.com/research/15989/futures-trend-following-and-carry-in-different-risk-regimes/
  - GitHub `amstrdm/mlm-trend-following`: https://github.com/amstrdm/mlm-trend-following
- 我的判断：外部资料支持趋势系统用仓位和风险 regime 管理风险，也支持用波动/趋势强度做通用过滤；但这些过滤本身也会改变右尾路径。Stage421 失败点不是“任意 all-cases 都太宽”这么简单，因此本阶段只测已有 RSI 确认开关，不扫 `55/60/65` 或 short 阈值。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage714_recovery_all_cases_rsi_confirm_multiperiod.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `CANDIDATE_VARIANT=stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_recovery_all_cases_rsi_confirm_stage714`
  - `RECOVERY_SIGNALS=long_case1a,long_case2,long_case3,short_case1a,short_case2,short_case3`
  - `streak_entry_structure_recovery_require_rsi_confirmation=True`
  - `streak_entry_structure_recovery_long_min_rsi=60.0`
  - `streak_entry_structure_recovery_short_max_rsi=40.0`
- 修改参数：候选分支仅把 Stage421 all-cases recovery 增加 RSI 方向确认；`streak_risk_multipliers` 仍为 `1.0,1.0,1.0,0.1`
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-01` 至 `2026-04-30`，并包含起始年份和阶段独立启动窗口
- 账户规模：`200,000`
- 成本口径：正常成本 + 2x/3x 成本压力
- 样本过滤：不按品种、年份、月份、case 子集或收益结果过滤
- 策略/归因口径：
  - A：当前正式 Stage372/20万 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
  - C：Stage421 all-cases recovery + RSI 确认，其他正式配置不变
  - 不改正式配置、不连接 CTP、不调用下单

## 结果

- 期末权益：C `6,374,500`，A `8,728,285`
- 总收益：C `3087.2500%`，A `4264.1425%`
- 最大回撤：C `-45.9347%`，A `-38.6713%`
- Sharpe：C `1.5225`，A `1.6279`
- 总滑点：C `374,580`，A `506,220`
- 总交易次数：C `636`，A `633`
- 胜率：C `51.7967%`，A `52.2586%`
- 其他关键指标：
  - 收益保留：`72.4003%`，低于 `80%` 闸门
  - 2x 成本全周期 DD：C `-48.3697%`，失败
  - `since_2021`：C `1382.8100%/-35.6901%/Sharpe1.4494`，A `2221.3050%/-38.1656%/Sharpe1.5636`
  - `since_2022`：C `384.7875%/-24.8748%/Sharpe1.2289`，A `133.8550%/-28.0550%/Sharpe0.8895`
  - `since_2023`：C `209.5325%/-37.1618%/Sharpe1.1360`，A `70.2100%/-24.5662%/Sharpe0.7818`；收益更高但回撤恶化 `12.5957pp`
  - `since_2026` / `phase_2026_latest`：C `-2.8600%/-17.4541%/Sharpe-0.1288`，A `1.1450%/-16.3027%/Sharpe0.2783`
  - 硬失败：`full_return_retention_ge80`、`full_dd30_pass`、`cost2_full_dd40_pass`、`start_years_min_retention_ge70`、`start_years_dd_not_worse_by_3pp`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage714_recovery_all_cases_rsi_confirm_multiperiod_report_stage714_recovery_all_cases_rsi_confirm_multiperiod_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage714_recovery_all_cases_rsi_confirm_multiperiod_summary_stage714_recovery_all_cases_rsi_confirm_multiperiod_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage714_recovery_all_cases_rsi_confirm_multiperiod_comparison_stage714_recovery_all_cases_rsi_confirm_multiperiod_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage714_recovery_all_cases_rsi_confirm_multiperiod_curves_stage714_recovery_all_cases_rsi_confirm_multiperiod_v1.csv`
- annual：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage714_recovery_all_cases_rsi_confirm_multiperiod_annual_stage714_recovery_all_cases_rsi_confirm_multiperiod_v1.csv`
- monthly：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage714_recovery_all_cases_rsi_confirm_multiperiod_monthly_stage714_recovery_all_cases_rsi_confirm_multiperiod_v1.csv`
- checks：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage714_recovery_all_cases_rsi_confirm_multiperiod_checks_stage714_recovery_all_cases_rsi_confirm_multiperiod_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage714_recovery_all_cases_rsi_confirm_multiperiod_decision_stage714_recovery_all_cases_rsi_confirm_multiperiod_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage714_recovery_all_cases_rsi_confirm_multiperiod_chart_stage714_recovery_all_cases_rsi_confirm_multiperiod_v1.png`

## 结论

- 本阶段结论：`recovery_all_cases_rsi_confirm_not_promoted`
- 是否进入下一步：否，不进入正式版，不进入季度验证
- 下一步：
  - 不继续扫 RSI 阈值，不做 `55/60/65`、long/short 阈值或 RSI 周期补丁
  - Stage421 all-cases recovery 的问题不能靠单一趋势强度确认解决
  - 当前正式版继续保持 Stage372/20万 `1,1,1,0.1 + recovery_sleeve`

## 过拟合反思

- 运行前判断：否。RSI 方向确认是策略体已有通用参数，不按产品、年份、case 或弱窗口过滤。
- 运行后判断：若继续调 RSI 阈值会转为过拟合。
- 原因：候选没有解决 Stage421 的 `since_2026` 负收益问题，却把全周期回撤打到 `-45.9347%`，说明它不是稳定的趋势质量过滤，而是在关键路径上误改了仓位和右尾/左尾分布。

## 继续价值反思

- 运行前判断：有价值。它是对 Stage421 最自然的简单质量门控反证。
- 运行后判断：本形态无继续价值；总目标仍有价值。
- 原因：RSI 确认改善了 `since_2022`，但破坏全周期和 `since_2023` 回撤，且近端失败仍在。后续应放弃“给 all-cases recovery 再加一个技术指标确认”的方向，回到账户级 selector、预声明 forward watch 或真正独立正期望风险槽。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：是，作为重要负结论追加
