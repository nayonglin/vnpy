# Stage137 - Stage136 best1_vt 严格鲁棒性与反过拟合审计

- 时间：2026-05-28 02:57 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 工作模式：`day`
- 阶段性质：固定 Stage136 候选的只读鲁棒性审计，不新增信号、不修改交易规则、不扫参数。
- 审计对象：`stage103_plus_low_skew252_best1_vt10_mom63_round_half_guard`
- 结论：降级为 `paper_candidate_only_overfit_warning`。它通过 Stage079 原始目标，但反过拟合审计有明显缺口，不能作为主策略替代或工程主候选。

## 外部调研与判断

- 调研方向：商品期货偏度异常、PBO / Deflated Sharpe / PSR、moving block bootstrap、walk-forward / rolling holding 反过拟合审计。
- 参考结论：
  - 商品期货低偏度/高偏度方向有文献依据，不是凭空补丁。
  - PBO / Deflated Sharpe / PSR 框架强调，多候选回测后不能只看全样本收益和 Sharpe，需要检查选择偏差、路径依赖、贡献集中和样本外退化。
  - block bootstrap、月份顺序重排、leave-one-year-out、top edge day ablation 更适合回答“这个版本是不是靠少数路径赢”。
- 本次专业判断：Stage136 的 self-validation 设计本身不算过拟合，但审计结果显示它的收益优势厚度不足，风险体验改善比 alpha 增强更可靠。

## 版本变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage437_stage136_robustness_audit.py`
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage437_stage136_robustness_audit_summary_stage437_stage136_robustness_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage437_stage136_robustness_audit_rolling_holding_stage437_stage136_robustness_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage437_stage136_robustness_audit_pairwise_rolling_stage437_stage136_robustness_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage437_stage136_robustness_audit_block_bootstrap_stage437_stage136_robustness_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage437_stage136_robustness_audit_month_permutation_stage437_stage136_robustness_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage437_stage136_robustness_audit_year_contribution_stage437_stage136_robustness_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage437_stage136_robustness_audit_leave_one_year_ablation_stage437_stage136_robustness_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage437_stage136_robustness_audit_top_edge_day_ablation_stage437_stage136_robustness_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage437_stage136_robustness_audit_psr_edge_stage437_stage136_robustness_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage437_stage136_robustness_audit_decision_stage437_stage136_robustness_audit_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage437_stage136_robustness_audit_report_stage437_stage136_robustness_audit_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage437_stage136_robustness_audit_chart_stage437_stage136_robustness_audit_v1.png`
- 修改正式策略：无。
- 修改 Stage079/C3/Stage103/Stage136 参数：无。
- 删除参数：无。

## 核心固定路径结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 3个月分 | 6个月分 | broker10拒绝 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 | 31,040,650 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 100.0000 | 100.0000 | 4 |
| Stage103 | 31,730,915 | 5059.4984% | -28.9792% | 1.3681 | 14.3132 | 121.2041 | 134.4513 | 2 |
| Stage136 best1_vt | 32,120,290 | 5122.8114% | -27.5906% | 1.3918 | 13.9133 | 141.2265 | 144.5203 | 0 |

## 通过项

- Stage079 原始目标通过：全周期收益、最大回撤、Sharpe、Ulcer、3个月/6个月体验分、rolling252/504、年度/季度、多起点、成本压力和 broker10 绝对保证金都通过。
- block bootstrap 相对 Stage079 中位收益差为正：
  - 20日块：`+84.6388pp`，收益胜率 `59.3667%`
  - 60日块：`+59.1556pp`，收益胜率 `56.9333%`
  - 120日块：`+47.0830pp`，收益胜率 `54.4333%`
- 风险体验相对 Stage079 稳定改善：block bootstrap 中最大回撤不劣化率 `96.60%` 到 `97.57%`，Ulcer 不劣化率 `99.83%` 到 `99.90%`。
- 月份顺序重排下，相对 Stage079 收益差保持 `+175.5512pp`，最大回撤和 Ulcer 仍明显更好。

## 失败项与反过拟合警告

- 任意启动收益胜率弱：相对 Stage079 的 90/180/252/504日收益胜率仅 `46.0603%/44.7677%/41.3793%/26.5634%`；相对 Stage103 为 `34.3539%/28.2966%/27.3919%/34.4217%`。风险体验更好，但不是多数窗口收益更好。
- leave-one-year-out 显示收益优势依赖 2021：剔除 2021 后，候选相对 Stage079 总收益差为 `-262.4845pp`，相对 Stage103 为 `-87.0686pp`。这说明全样本收益优势不够分散。
- 按日收益贡献剔除最大正 edge 后很脆弱：
  - 相对 Stage079：剔除最大1天后仍高 `+32.6405pp`；剔除最大3天后变为 `-192.6946pp`。
  - 相对 Stage103：剔除最大1天后即变为 `-55.0864pp`。
  - 注意：Stage136 的 PnL 贡献剔除更宽松，本阶段改用日收益 edge，是更贴近复利路径的严格口径。
- daily edge PSR 不支持稳定 alpha：
  - 相对 Stage079：annualized edge Sharpe `-0.1165`，PSR `0.000003`
  - 相对 Stage103：annualized edge Sharpe `-0.0592`，PSR `0.016744`

## 决策

- Stage136 best1_vt 不继续晋级为主策略替代，也不进入工程主候选。
- 当前正式判断：`paper_candidate_only_overfit_warning`。
- 它可以保留为 paper/体验观察线索：如果未来真实盘遇到与 2021 类似的偏度/反转结构，可能有价值；但当前不能宣称为稳定穿越周期的改进。
- Stage103 重新保持为当前主执行相对候选。
- 停止救偏度路线，不继续扫 `SKEW_LOOKBACK_DAYS`、`top_n`、`TARGET_VOL`、`VOL_LOOKBACK_DAYS`、`ROUND_HALF_THRESHOLD`、日期、品种或 broker10 小数。

## 过拟合反思

- Stage137 本身不是过拟合：它没有新增规则，也没有修改参数，只是用更严的扰动审计去反证 Stage136。
- Stage136 候选存在过拟合/路径依赖警告：它不是坏窗口补丁，但收益优势集中在 2021 和少数日收益 edge；这不满足“必须不能过拟合”的主线要求。

## 继续价值反思

- 偏度 self-validation 子路线继续主动优化价值低。继续救它会变成围绕贡献日、年份和阈值做历史拟合。
- 总目标仍有价值：下一步应回到 Stage103 主候选落地验证，或寻找全新、低自由度、样本更分散、保证金更轻的风险源。

## TODO

- 不再调偏度窗口、top_n、目标波动、动量窗口、执行阈值或保证金缓冲小数。
- 若继续优化 Stage079，只允许探索新的低自由度风险源，且必须先定义经济含义，再做真实整数手和多起点审计。
- Stage103 仍可作为工程化复跑 / paper 影子盘主线；Stage136 只保留 paper 观察。
