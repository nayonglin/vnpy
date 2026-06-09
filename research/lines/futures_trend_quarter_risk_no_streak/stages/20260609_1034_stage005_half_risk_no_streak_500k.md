# Stage005 C 版本 50万本金敏感性回测

- line_id：`futures_trend_quarter_risk_no_streak`
- 当前模式：`day`
- 记录时间：2026-06-09 10:34 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：C 版本本金规模敏感性验证
- 是否重要突破：否，属于机制澄清，不是正式候选
- 是否触发A/B：是；已读取并遵循 `skills/version-ab-experiment/SKILL.md`

## 外部调研与判断

- 参考资料：
  - `https://www.stator-afm.com/tutorial/fixed-fractional-position-sizing/`
  - `https://chartmini.com/blog/position-sizing-guide`
- 我的判断：固定比例风险 sizing 的第一性逻辑是用账户风险预算除以止损距离得到手数；但期货不能交易分数手，最小一手会让小本金账户出现明显颗粒度误差。把 C 从 20 万改成 50 万，是验证“风险预算过小/整数手压制”而不是验证新 alpha，因此不应把收益改善直接解释为策略更强。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage748_half_risk_no_streak_500k.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`MODEL_TAG=stage748_half_risk_no_streak_500k_v1`、`CAPITAL_500K=500000.0`、`CANDIDATE_500K_VARIANT=stage526_500k_force95_to80_r040_pc25_maxpos4_no_streak_no_recovery_stage748`
- 修改参数：仅 C 版本 `account_capital/c3_capital 200000 -> 500000`；保持 `risk_multiplier=0.40`、`streak_risk_multipliers=1.0,1.0,1.0,1.0`、关闭 `enable_streak_entry_structure_risk_recovery`、关闭 `enable_recovery_sleeve`
- 删除参数：无
- 正式配置/CTP/下单：不改正式配置、不连接 CTP、不调用下单

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`，并补 `since_2021` 至 `since_2026`、`phase_2020_2021`、`phase_2022_2023`、`phase_2024_2025`、`phase_2026_latest`
- 账户规模：C50 为 `500,000`；对照 C20 为 Stage746 `200,000`
- 成本口径：正常成本、2x成本、3x成本压力测试
- 样本过滤：沿用当前官方 Stage372/20万同信号、同 AI 池、同品种池、同 `maxpos4`、同 broker10 `95%->80%` 强制减仓
- 策略/归因口径：用 NAV 对比 C20/C50，避免本金不同造成绝对权益误读

## 结果

- C50 全周期期末权益：`5,565,350`
- C50 全周期总收益：`1013.0700%`
- C50 全周期最大回撤：`-39.7082%`
- C50 全周期 Sharpe：`1.3285`
- C50 全周期总滑点：`470,250`
- C50 全周期总交易次数：`686`
- C50 全周期胜率：`52.7165%`
- C50 保证金：broker10 峰值 `74.8301%`，p95 `43.6029%`，强制减仓 `3` 次、减仓手数 `229`
- C50 成本压力：2x成本 `5,095,100/919.0200%/-42.9625%/Sharpe1.2352`，3x成本 `4,624,850/824.9700%/-46.4274%/Sharpe1.1425`
- C20 对照全周期：`1,639,200/719.6000%/-38.7135%/Sharpe1.2214`，总滑点 `139,780`，交易 `659`，胜率 `52.0034%`
- C50 相比 C20：收益 `+293.4700pp`，回撤恶化 `-0.9946pp`，Sharpe `+0.1070`，交易 `+27`，滑点 `+330,470`
- 当前正式 A 全周期参考：`8,728,285/4264.1425%/-38.6713%/Sharpe1.6279`，总滑点 `506,220`，交易 `633`，胜率 `52.2586%`
- 起始年窗口：`since_2021 398.9600%/-37.0618%/Sharpe1.1106`；`since_2022 137.1850%/-31.2204%/Sharpe0.8594`；`since_2023 185.1370%/-19.5236%/Sharpe1.3012`；`since_2024 105.9200%/-19.0944%/Sharpe1.2024`；`since_2025 71.5650%/-18.4594%/Sharpe1.4100`；`since_2026 -5.9200%/-17.4047%/Sharpe-0.3384`
- 阶段窗口：`phase_2020_2021 260.6030%/-19.7108%/Sharpe2.0460`；`phase_2022_2023 17.4790%/-31.2204%/Sharpe0.4412`；`phase_2024_2025 115.7920%/-17.3502%/Sharpe1.5286`；`phase_2026_latest -5.9200%/-17.4047%/Sharpe-0.3384`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage748_half_risk_no_streak_500k_report_stage748_half_risk_no_streak_500k_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage748_half_risk_no_streak_500k_summary_stage748_half_risk_no_streak_500k_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage748_half_risk_no_streak_500k_comparison_20w_stage748_half_risk_no_streak_500k_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage748_half_risk_no_streak_500k_cost_stress_stage748_half_risk_no_streak_500k_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage748_half_risk_no_streak_500k_curves_stage748_half_risk_no_streak_500k_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage748_half_risk_no_streak_500k_chart_stage748_half_risk_no_streak_500k_v1.png`

## 结论

- 本阶段结论：`half_risk_no_streak_500k_not_promoted`。C50 证明 C20 的确受到小本金和整数手颗粒度压制；本金放到 50 万后，交易次数、收益和 Sharpe 都改善。
- 但 C50 不是正式候选：全周期 DD30 失败，2x成本 DD40 失败，`since_2026` 仍为负，且全周期收益仍远低于正式 A。它改善的是执行粒度，不是选品/信号质量。
- 是否进入下一步：不进入正式版，不继续用“放大本金”修 C。
- 下一步：若用户继续追求低回撤体验，应转向账户层资金分层、出金/锁盈、生存线或独立 sleeve；不要继续沿固定低风险关闭连败路线扫参。

## 过拟合反思

- 运行前判断：不是过拟合。本阶段只改本金规模，用于验证最小一手和资金粒度问题，没有新增历史窗口阈值或信号条件。
- 运行后判断：结论本身不是过拟合，但如果把 C50 在 `2024-2025` 的局部强势当作接正式版理由，就会过拟合。
- 原因：C50 的主要改善来自手数颗粒度更细、能参与更多信号；它没有解决正式版右尾复利底座和成本压力问题。

## 继续价值反思

- 运行前判断：有价值，因为 Stage003/004 已显示 C 版本可能被过小风险预算压制，需要区分“策略弱”和“本金粒度弱”。
- 运行后判断：本阶段验证有价值，但该路线不值得继续作为正式替代推进。
- 原因：50 万本金修复了一部分 C 的低效，但仍不能接近正式版收益，也没有降低核心尾部回撤；继续扫本金/倍率会偏离“穿越周期”的目标。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是，记录“C50 改善来自本金粒度但不晋级”的跨阶段经验
