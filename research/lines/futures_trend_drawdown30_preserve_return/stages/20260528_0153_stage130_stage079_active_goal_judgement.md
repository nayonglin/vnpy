# Stage130 Stage079主动目标候选裁决

- 时间：2026-05-28 01:53 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 阶段性质：只读晋级裁决；不新增交易规则、不新增资金、不扫描参数。
- 是否重要突破：是。突破不在新收益，而在纠正口径：按当前用户目标，Stage079 仍是唯一 baseline；Stage103 是最干净主候选，Stage115 虽分数最高但只适合 paper/观察。
- 是否触发 A/B：否。本阶段不提出新交易版本，只读取既有 Stage109/115/116/126/127/129 的冻结结果做裁决。
- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage430_stage079_active_goal_judgement.py`
- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage430_stage079_active_goal_judgement_report_stage430_stage079_active_goal_judgement_v1.md`
- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage430_stage079_active_goal_judgement_chart_stage430_stage079_active_goal_judgement_v1.png`
- 决策 JSON：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage430_stage079_active_goal_judgement_decision_stage430_stage079_active_goal_judgement_v1.json`

## 开始前反思

- 是否在过拟合：否。本阶段不新增候选、不扫参数，只审计已经冻结的候选层级。
- 是否仍有价值继续做：有。当前目标明确要求 Stage079 作为唯一 baseline，而此前多个结论混用了 Stage103 incumbent 口径；必须把“Stage079目标通过”和“不过拟合可主晋级”拆开。

## 外部调研与判断

- 本轮网络/GitHub 检索显示，公开趋势跟随/managed futures/TSMOM/波动目标/relative value 框架与本线已验证方向高度重合，未发现能直接迁移到本地中国期货、整数手、保证金和61.5万账户口径的现成实现。
- 参考：
  - FuturesBacktest 趋势策略说明：https://www.futuresbacktest.com/docs/strategies/trend/
  - Moskowitz/Ooi/Pedersen 时间序列动量论文：https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf
  - `PyTrendFollow`：https://github.com/chrism2671/PyTrendFollow
  - QuantConnect commodities futures trend following：https://www.quantconnect.com/research/15257/commodities-futures-trend-following/p1
- 我的判断：继续救 Stage087-129 里已失败路线的小参数，边际价值低且过拟合风险高；当前最有价值的是固定 Stage103 做工程化/paper/真实保证金验证，Stage115 只作为高分 paper 对照。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage430_stage079_active_goal_judgement.py`
- 新增输出：
  - `qmt_roll_stage430_stage079_active_goal_judgement_summary_stage430_stage079_active_goal_judgement_v1.csv`
  - `qmt_roll_stage430_stage079_active_goal_judgement_anti_overfit_stage430_stage079_active_goal_judgement_v1.csv`
  - `qmt_roll_stage430_stage079_active_goal_judgement_report_stage430_stage079_active_goal_judgement_v1.md`
  - `qmt_roll_stage430_stage079_active_goal_judgement_chart_stage430_stage079_active_goal_judgement_v1.png`
  - `qmt_roll_stage430_stage079_active_goal_judgement_decision_stage430_stage079_active_goal_judgement_v1.json`
- 新增参数：无交易参数；只读审计读取 Stage126 候选表、Stage127/129 gate、Stage109/116 反过拟合证据。
- 修改参数：无。
- 删除参数：无。
- 修改正式策略默认：无。

## 基准

- Stage079：期末权益 `31,040,650`
- 总收益：`4947.2602%`
- 最大回撤：`-29.7007%`
- Sharpe：`1.3188`
- Ulcer：`15.0874`
- 总滑点：`1,556,750`
- 总交易次数：`757`
- 胜率：非零日胜率约 `48.3478%`

## 裁决结果

| 候选 | 层级 | 总收益 | 最大回撤 | Sharpe | Ulcer | 3个月分 | 6个月分 | 判断 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `xsmom_vt10_q_momq_round_half_true_broker10_guard` | 主候选 | `5059.4984%` | `-28.9792%` | `1.3681` | `14.3132` | `121.2041` | `134.4513` | Stage103，当前最干净主候选 |
| `stage103_plus_cffex_index_best1_tsmom60_guard` | 高分paper | `5364.6659%` | `-23.5184%` | `1.4810` | `12.0786` | `183.4601` | `210.3930` | Stage115，分数最高但被Stage116降级 |
| `stage103_plus_oi_confirm63_best1_weekly_guard` | paper | `5128.7927%` | `-26.8963%` | `1.4092` | `13.5225` | `146.4538` | `155.0300` | 相对Stage103任意启动收益胜率弱 |
| `stage103_plus_value_proxy756_monthly_guard` | paper | `5183.5439%` | `-28.9792%` | `1.3808` | `14.1660` | `130.2395` | `143.3501` | 有效样本不足，不能证明穿越周期 |
| `xsmom_vt10_q_momq_short_only_round_half_broker10_guard` | 次级备选 | `5001.1220%` | `-28.7881%` | `1.3555` | `14.4485` | `114.6444` | `119.8979` | 保证金更轻但被Stage103双边结构支配 |

本阶段额外纳入 Stage127/129：`stage103_plus_pair_spread_mr120_best1_guard`、`stage103_plus_pair_spread_mr120_all_guard`、`stage103_plus_cffex_tf_t_curve_mr120_2tf1t_guard` 均通过 Stage079 目标闸门，但新增腿净 PnL 为负或弱于 Stage103，只能作为 objective-only / paper 观察，不升主候选。

## 反过拟合证据

- Stage103：
  - Stage109 裁决：保留为当前最强执行相对候选，可进入工程化复跑 / paper影子盘，但不升为绝对部署或正式替代版本。
  - 固定路径、冷启动、成本压力和路径扰动下的回撤/Ulcer优势成立。
  - 弱点：任意窗口收益胜率不足，block bootstrap 收益胜率约 `55%-59%`，剔除最大 `3` 个相对贡献日后收益低于 Stage079。
- Stage115：
  - Stage116 裁决：不建议进一步晋级，保留为研究候选或回到 Stage103。
  - 相对 Stage079，原始收益差 `+417.4057pp`，剔除最大 `1` 个相对贡献日后仍为 `+119.1846pp`，但剔除最大 `3` 个后转负 `-349.4080pp`。
  - 相对 Stage103，剔除最大 `1` 个相对贡献日后总收益降到 `5046.0926%`，低于 Stage103。
  - 结论：风险改善真实，但收益优势有贡献日集中和路径选择风险。

## 决策

- 决策 JSON：`stage103_main_candidate_stage115_high_score_paper`
- 主候选：Stage103 `xsmom_vt10_q_momq_round_half_true_broker10_guard`
- 高分 paper：Stage115 `stage103_plus_cffex_index_best1_tsmom60_guard`
- 当前不再推荐继续救：
  - 连续失败信号/冷却
  - 分批启动/风险爬坡
  - 默认 weighted_env_gate
  - 商品动量、basis、OI、value、贵金属、network、产业链价差、TF/T 曲线价差等已降级路线的小参数

## 后续规划和 TODO

1. 固定 Stage103 做工程化复跑、paper/影子盘和真实券商保证金接入。
2. Stage115 只作为高分 paper 对照，不按主候选推进；若未来真实保证金和OOS样本支持，再重新立独立验证阶段。
3. 若继续主动研究短持有体验，只允许找全新、低自由度、保证金更轻、样本更充分、且非坏窗口归因的新风险源；不再围绕已降级路线救小数参数。

## 结束后反思

- 是否在过拟合：否。本阶段通过分层裁决降低过拟合风险，没有新增规则，也没有因为目标而救失败候选。
- 是否还有价值继续做：有，但价值已经从“继续扫候选”转向“Stage103工程化验证 / paper影子盘 / 真实保证金接入”，以及少量全新风险源探索。
