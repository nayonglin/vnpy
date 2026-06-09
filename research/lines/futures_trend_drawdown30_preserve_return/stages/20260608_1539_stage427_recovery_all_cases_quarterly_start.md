# Stage427 Recovery All Cases Quarterly Start Robustness

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-08 15:39 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / 当前工作区
- 阶段性质：Stage421 all-cases recovery 的季度独立启动鲁棒性验证
- 是否重要突破：否；这是重要反证和边界确认，不是正式候选突破
- 是否触发A/B：已按 `skills/version-ab-experiment/SKILL.md` 做 A/B 前置纪律检查；因硬失败，不进入正式 A/B

## 外部调研与判断

- 参考资料：
  - Keel Research Team, Walk-Forward Optimization: https://usekeel.io/learn/walk-forward-optimization
  - Concretum Group, Position Sizing in Trend-Following: https://concretumgroup.com/position-sizing-in-trend-following-comparing-volatility-targeting-volatility-parity-and-pyramiding/
  - GitHub `chrism2671/PyTrendFollow`: https://github.com/chrism2671/PyTrendFollow
  - GitHub `pst-group/pysystemtrade` backtesting docs: https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md
- 我的判断：外部资料和开源实现都强调两点：趋势系统不能只看一个长样本权益曲线，必须看不同起点/不同 regime 的稳定性；仓位和风控会显著改写趋势右尾分布。Stage421 全周期看起来很强，但如果季度冷启动尾部失败，就不能因为全周期回撤低于 30% 而直接晋级。本阶段不复制外部代码，只把验证思想落成本仓库的季度起点反证。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage713_recovery_all_cases_quarterly_start_robustness.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `START_DATES=2020-01-01` 至 `2026-01-01` 的季度起点，共 `25` 个独立启动
  - `ANALYSIS_END=2026-04-30`
  - 新增鲁棒性检查：收益胜率、回撤胜率、收益+回撤双胜率、负收益起点数、DD30失败起点数、收益保留 p10、中位收益保留、2x 成本最差回撤
- 修改参数：无；候选沿用 Stage421/Script707 的 all-cases recovery
- 删除参数：无

## 回测/归因参数

- 数据区间：各季度起点独立启动至 `2026-04-30`
- 账户规模：`200,000`
- 成本口径：正常成本 + 2x/3x 成本压力
- 样本过滤：不按年份、品种、方向、case 或收益结果过滤
- 策略/归因口径：
  - A：当前正式 Stage372/20万 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
  - C：Stage421 all-cases recovery，保持 `streak_risk_multipliers=1.0,1.0,1.0,0.1` 不变，仅把 clean-book recovery lift 从 `long_case1a/short_case1a` 扩到全部原生趋势入场 case：`long_case1a,long_case2,long_case3,short_case1a,short_case2,short_case3`
  - 不改正式配置、不连接 CTP、不调用下单

## 结果

- 期末权益：C 全周期季度起点 `2020Q1` 为 `7,289,850`，A 为 `8,728,285`
- 总收益：C `3544.9250%`，A `4264.1425%`
- 最大回撤：C `-28.6384%`，A `-38.6713%`
- Sharpe：C `1.6631`，A `1.6279`
- 总滑点：C `359,770`，A `506,220`
- 总交易次数：C `600`，A `633`
- 胜率：C `52.0188%`，A `52.2586%`
- 其他关键指标：
  - 季度独立启动数：`25`
  - C 收益胜率：`17/25 = 68.00%`
  - C 回撤胜率：`15/25 = 60.00%`，低于预设 `70%`
  - C 收益+回撤双胜率：`10/25 = 40.00%`
  - C 负收益起点：`2` 个，分别是 `2025Q4`、`2026Q1`
  - C DD30 失败起点：`4` 个，分别是 `2021Q3 -30.0757%`、`2021Q4 -33.9215%`、`2022Q3 -30.9383%`、`2023Q4 -34.7308%`
  - 收益保留中位数：`107.2627%`
  - 收益保留 p10：`54.7107%`，低于预设 `70%`
  - C 最差季度启动 DD：`-34.7308%`
  - C 2x 成本最差 DD：`-37.3005%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage713_recovery_all_cases_quarterly_start_robustness_report_stage713_recovery_all_cases_quarterly_start_robustness_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage713_recovery_all_cases_quarterly_start_robustness_summary_stage713_recovery_all_cases_quarterly_start_robustness_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage713_recovery_all_cases_quarterly_start_robustness_comparison_stage713_recovery_all_cases_quarterly_start_robustness_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage713_recovery_all_cases_quarterly_start_robustness_curves_stage713_recovery_all_cases_quarterly_start_robustness_v1.csv`
- checks：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage713_recovery_all_cases_quarterly_start_robustness_checks_stage713_recovery_all_cases_quarterly_start_robustness_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage713_recovery_all_cases_quarterly_start_robustness_cost_stress_stage713_recovery_all_cases_quarterly_start_robustness_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage713_recovery_all_cases_quarterly_start_robustness_decision_stage713_recovery_all_cases_quarterly_start_robustness_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage713_recovery_all_cases_quarterly_start_robustness_chart_stage713_recovery_all_cases_quarterly_start_robustness_v1.png`

## 结论

- 本阶段结论：`recovery_all_cases_quarterly_start_not_promoted`
- 是否进入下一步：不进入正式版，不进入正式 A/B；只能保留为 paper/forward watch 或后续账户级 selector 研究材料
- 下一步：
  - 当前官方实盘默认仍保持 Stage372/20万 `1,1,1,0.1 + recovery_sleeve`
  - 不要为修复 `2025Q4/2026Q1` 去做年份、月份、品种、case 子集或阈值补丁
  - 如果继续该方向，只允许做预声明 forward watch，或转向账户级 selector/真正独立正期望风险槽

## 过拟合反思

- 运行前判断：否。本阶段不是优化参数，而是对 Stage421 已有候选做季度独立启动反证。
- 运行后判断：候选若强行推广会有明显过拟合风险；实验本身是反过拟合验证。
- 原因：C 在全周期和早期起点能明显降低回撤，但在最近短起点转负、DD30 有 4 个季度失败、收益保留 p10 只有 `54.7107%`。这种结构说明它仍依赖特定长路径的复利顺序，尚未证明能穿越不同启动点。

## 继续价值反思

- 运行前判断：有价值。Stage421 是当前主账户连败风控方向最强的简单结构线索，需要更严验证。
- 运行后判断：目标仍有价值，但该候选不值得继续调参。
- 原因：C 的中位收益保留 `107.2627%`、2x 成本最差 DD `-37.3005%` 说明 all-cases recovery 有结构性材料；但负收益起点和 DD30 失败说明它不能作为正式风控机制。后续价值在观察和重新定义账户级选择器，而不是继续扫 all-cases 的细分开关。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录为 Stage427 不晋级
- 是否更新 `research/registry.md`：否，当前主线状态未变化
- 是否追加根目录 `memory.md/back_log.md`：是，作为重要负结论和研究边界追加
