# Stage001 风险资金0.25倍且关闭连败机制

- line_id：`futures_trend_quarter_risk_no_streak`
- 当前模式：`day`
- 记录时间：`2026-06-09 02:39 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：新研究线首轮 A/C 多窗口回测
- 是否重要突破：否
- 是否触发A/B：是，A/C；该方向可能影响正式资金管理，但本阶段不改正式配置

## 外部调研与判断

- 参考资料：
  - Sandberg & Öhman, *Position sizing methods for a trend following CTA*：趋势跟随里 Fixed Fraction 是核心对照，基于权益曲线的动态 sizing 容易参数敏感，最大回撤最小化类方法能降低风险但常显著降低绝对收益。
  - Concretum Group, *Position Sizing in Trend-Following*：趋势跟随仓位管理和加仓能放大利润，但回撤和尾部反转风险必须同步评估。
  - Reddit / r/algotrading 关于 clustered losses 的讨论：压力测试要保留亏损簇路径，不能只看单笔独立分布。
- 我的判断：把风险资金固定降到正式版 `0.25` 倍、关闭连败机制，是低过拟合的资金管理实验；它不是根据某个红框窗口做补丁。但这个实验若要替代正式版，必须证明“收益只是近似按风险比例缩小，回撤显著下降，Sharpe 不塌陷”。本轮结果没有做到。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage745_quarter_risk_no_streak_multiperiod.py`
- 新增研究线：`research/lines/futures_trend_quarter_risk_no_streak/LINE.md`
- 修改脚本：无正式策略修改
- 删除脚本：无
- 新增参数：
  - `risk_multiplier_after=0.20`
  - `risk_multiplier_scale_to_formal=0.25`
  - `streak_risk_multipliers_after=1.0,1.0,1.0,1.0`
- 修改参数：
  - A 正式 `risk_multiplier=0.80`，C 改为 `0.20`
  - A 正式 `streak_risk_multipliers=1,1,1,0.1`，C 改为 `1,1,1,1`
  - C 关闭 `enable_streak_entry_structure_risk_recovery`
  - C 关闭 `enable_recovery_sleeve`
- 删除参数：C 删除正式版的连败缩放实际效果和 recovery sleeve 实际效果；正式配置未删除任何参数

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`
- 账户规模：`200,000`
- 成本口径：正常成本、2x成本、3x成本
- 样本过滤：无新增过滤；同正式 Stage372/20万信号、AI池、品种池、`maxpos4`、`product_cap_ratio=0.25`、broker10 `95%->80%` 强制减仓
- 策略/归因口径：
  - A：`stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
  - C：`stage526_200k_force95_to80_r020_pc25_maxpos4_no_streak_no_recovery_stage745`
  - 窗口：全周期、`since_2021` 至 `since_2026`、`phase_2020_2021`、`phase_2022_2023`、`phase_2024_2025`、`phase_2026_latest`

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
  - 期末权益 `543,840`
  - 总收益 `171.9200%`
  - 最大回撤 `-27.4322%`
  - Sharpe `0.9699`
  - 总滑点 `41,230`
  - 总交易次数 `524`
  - 胜率 `50.9766%`
  - broker10 保证金峰值 `54.7105%`
- 关键对比：
  - 全周期收益保留只有 `4.0318%`，远低于预声明 `20%` 硬门槛和 `25%` 观察门槛
  - 全周期回撤改善 `+11.2391pp`，C 通过 DD30
  - C 2x成本最大回撤 `-29.5908%`，通过 DD30
  - Sharpe 下降 `-0.6580`，未过 `>= -0.25` 闸门
  - `since_2023`、`since_2024`、`since_2025` C 反而强于 A：分别 `77.5075%`、`45.9425%`、`41.2250%`
  - `since_2021` C 只有 `51.7225%`，A 为 `2221.3050%`
  - `phase_2022_2023` C 为 `-12.1775%`，A 为 `0.2975%`
  - `since_2026` C 为 `-5.8075%`，A 为 `1.1450%`
- 年度拆分：
  - C 在 `2020/2021` 只把权益推到 `466,130`，A 已到 `1,082,930`
  - C 在 `2022` 亏 `-98,265`，年度收益 `-21.0810%`
  - C 在 `2025` 表现较好，赚 `176,460`，年度收益 `43.4438%`
  - A 的核心优势来自早期复利底座和 2023-2026 大权益状态下的右尾放大，C 低风险路径无法复制这个复利凸性

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage745_quarter_risk_no_streak_multiperiod_report_stage745_quarter_risk_no_streak_multiperiod_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage745_quarter_risk_no_streak_multiperiod_summary_stage745_quarter_risk_no_streak_multiperiod_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage745_quarter_risk_no_streak_multiperiod_comparison_stage745_quarter_risk_no_streak_multiperiod_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage745_quarter_risk_no_streak_multiperiod_cost_stress_stage745_quarter_risk_no_streak_multiperiod_v1.csv`
- annual：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage745_quarter_risk_no_streak_multiperiod_annual_stage745_quarter_risk_no_streak_multiperiod_v1.csv`
- monthly：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage745_quarter_risk_no_streak_multiperiod_monthly_stage745_quarter_risk_no_streak_multiperiod_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage745_quarter_risk_no_streak_multiperiod_curves_stage745_quarter_risk_no_streak_multiperiod_v1.csv`
- checks：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage745_quarter_risk_no_streak_multiperiod_checks_stage745_quarter_risk_no_streak_multiperiod_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage745_quarter_risk_no_streak_multiperiod_decision_stage745_quarter_risk_no_streak_multiperiod_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage745_quarter_risk_no_streak_multiperiod_chart_stage745_quarter_risk_no_streak_multiperiod_v1.png`

## 结论

- 本阶段结论：`quarter_risk_no_streak_not_promoted`
- 是否进入下一步：不进入正式替代验证；只保留为“保守账户/低波动口径”的经验样本
- 下一步：
  - 不继续扫 `0.15/0.20/0.25/0.30` 风险倍率
  - 不用关闭连败机制替代正式 `1,1,1,0.1 + recovery_sleeve`
  - 若继续做低回撤体验，优先研究账户层资金分层、出金/锁盈、生存线，而不是把主策略整体低风险化

## 过拟合反思

- 运行前判断：否
- 运行后判断：否，但继续救参会变成过拟合
- 原因：本轮只测试用户指定的单一结构参数，不按结果调整阈值、品种或年份；结论来自多起点/多阶段。若为了修复 `2020-2021` 或 `2022-2023` 去扫风险倍率、恢复仓开关或阶段条件，会转为历史路径拟合。

## 继续价值反思

- 运行前判断：有价值
- 运行后判断：作为正式替代没有继续价值；作为保守账户口径有有限参考价值
- 原因：C 确实把回撤和保证金压力压下来了，证明低风险壳有效；但收益保留只有 `4.0318%`、Sharpe 大幅下降，说明整体低风险化会牺牲趋势策略最重要的早期复利和右尾凸性。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是，新增独立研究线
- 是否追加根目录 `memory.md/back_log.md`：是，记录“0.25倍风险+关闭连败不替代正式版”的跨线结论
