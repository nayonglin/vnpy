# Stage003 C版本风险扩大一倍到正式版0.5倍

- line_id：`futures_trend_quarter_risk_no_streak`
- 当前模式：`day`
- 记录时间：`2026-06-09 02:56 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage001 C 版本风险扩大一倍的 A/C 多窗口回测
- 是否重要突破：否
- 是否触发A/B：是，A/C

## 外部调研与判断

- 参考资料：本阶段快速复核 fixed fractional / trend following position sizing 资料，结论仍是“风险比例直接决定止损距离下可开手数，同时也决定亏损簇放大程度”。
- 我的判断：把 Stage745 的 C 从 `risk_multiplier=0.20` 扩到 `0.40`，是合理的单点验证；但不能继续展开小数扫描，否则会变成救参。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage746_half_risk_no_streak_multiperiod.py`
- 修改脚本：无正式策略修改
- 删除脚本：无
- 新增参数：
  - `risk_multiplier_after=0.40`
  - `risk_multiplier_scale_to_formal=0.50`
  - `scale_to_stage745_candidate=2.0`
- 修改参数：
  - Stage745 C 的 `risk_multiplier=0.20` 扩大一倍为 `0.40`
  - 仍保持 `streak_risk_multipliers=1,1,1,1`
  - 仍关闭 `enable_streak_entry_structure_risk_recovery`
  - 仍关闭 `enable_recovery_sleeve`
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`
- 账户规模：`200,000`
- 成本口径：正常成本、2x成本、3x成本
- 样本过滤：无新增过滤；同正式 Stage372/20万信号、AI池、品种池、`maxpos4`、`product_cap_ratio=0.25`、broker10 `95%->80%` 强制减仓
- 策略/归因口径：
  - A：`stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
  - C：`stage526_200k_force95_to80_r040_pc25_maxpos4_no_streak_no_recovery_stage746`

## 结果

- A 正式全周期：
  - 期末权益 `8,728,285`
  - 总收益 `4264.1425%`
  - 最大回撤 `-38.6713%`
  - Sharpe `1.6279`
  - 总滑点 `506,220`
  - 总交易次数 `633`
  - 胜率 `52.2586%`
  - broker10 保证金峰值 `79.6015%`
- C 全周期：
  - 期末权益 `1,639,200`
  - 总收益 `719.6000%`
  - 最大回撤 `-38.7135%`
  - Sharpe `1.2214`
  - 总滑点 `139,780`
  - 总交易次数 `659`
  - 胜率 `52.0034%`
  - broker10 保证金峰值 `73.9380%`
  - 2x成本最大回撤 `-41.8567%`
- 与 Stage745 C `risk_multiplier=0.20` 对比：
  - 期末权益从 `543,840` 提升到 `1,639,200`
  - 总收益从 `171.9200%` 提升到 `719.6000%`
  - 最大回撤从 `-27.4322%` 恶化到 `-38.7135%`
  - Sharpe 从 `0.9699` 提升到 `1.2214`，但仍低于正式 A
  - p95 保证金占用从 `27.4386%` 提升到 `40.0666%`
  - 平均保证金占用从约 `7.2272%` 提升到 `14.7021%`
- 多窗口：
  - `since_2023` C 为 `151.1500%/-17.8826%/Sharpe1.2214`，强于 A `70.2100%/-24.5662%`
  - `since_2024` C 为 `79.0175%/-18.2310%/Sharpe1.0682`，强于 A `33.3550%/-29.4347%`
  - `since_2025` C 为 `66.9775%/-17.9730%/Sharpe1.3840`，强于 A `17.9975%/-17.6662%`
  - `since_2021` C 只有 `365.7175%`，A 为 `2221.3050%`
  - `phase_2022_2023` C 为 `-1.0875%/-31.0611%`，A 为 `0.2975%/-28.0550%`
  - `since_2026` C 为 `-9.4625%`，A 为 `1.1450%`
- 检查项：
  - `full_return_retention_ge35` 失败，收益保留仅 `16.8756%`
  - `full_dd30_pass` 失败，全周期 DD `-38.7135%`
  - `full_sharpe_not_much_lower` 失败，Sharpe 下降 `0.4064`
  - `cost2_full_dd40_pass` 失败，2x成本 DD `-41.8567%`
  - broker10 100% 通过

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage746_half_risk_no_streak_multiperiod_report_stage746_half_risk_no_streak_multiperiod_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage746_half_risk_no_streak_multiperiod_summary_stage746_half_risk_no_streak_multiperiod_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage746_half_risk_no_streak_multiperiod_comparison_stage746_half_risk_no_streak_multiperiod_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage746_half_risk_no_streak_multiperiod_cost_stress_stage746_half_risk_no_streak_multiperiod_v1.csv`
- annual：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage746_half_risk_no_streak_multiperiod_annual_stage746_half_risk_no_streak_multiperiod_v1.csv`
- monthly：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage746_half_risk_no_streak_multiperiod_monthly_stage746_half_risk_no_streak_multiperiod_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage746_half_risk_no_streak_multiperiod_curves_stage746_half_risk_no_streak_multiperiod_v1.csv`
- checks：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage746_half_risk_no_streak_multiperiod_checks_stage746_half_risk_no_streak_multiperiod_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage746_half_risk_no_streak_multiperiod_decision_stage746_half_risk_no_streak_multiperiod_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage746_half_risk_no_streak_multiperiod_chart_stage746_half_risk_no_streak_multiperiod_v1.png`

## 结论

- 本阶段结论：`half_risk_no_streak_not_promoted`
- 是否进入下一步：不进入正式替代验证
- 下一步：
  - 不继续扫 `0.30/0.35/0.45` 等小数风险倍率
  - 无连败固定风险版本局部改善近端窗口，但全周期收益保留和成本压力不达标
  - 正式版继续保持 `1,1,1,0.1 + recovery_sleeve`

## 过拟合反思

- 运行前判断：否，但存在中等救参风险
- 运行后判断：不晋级；继续扫小数会过拟合
- 原因：本轮只验证用户指定的“C扩大一倍风险”，没有按结果补年份/品种/窗口条件；但结果显示 0.40 已把回撤拉回正式版附近，继续在 0.20 和 0.40 之间找小数没有第一性原理。

## 继续价值反思

- 运行前判断：有价值
- 运行后判断：这一条固定无连败风险倍率路线没有继续价值
- 原因：0.20 仓位太小，0.40 回撤和成本压力又回到不可接受区间；问题不在某个倍率，而在“关闭连败机制后缺少账户状态防守”。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：可选；本线状态需要标记 Stage003 不晋级
- 是否追加根目录 `memory.md/back_log.md`：是，作为“0.40无连败也不替代正式”的重要边界
