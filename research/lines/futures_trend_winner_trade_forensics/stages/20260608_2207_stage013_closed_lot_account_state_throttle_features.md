# Stage013 已平仓交易簇账户状态审计：0.1 档高质量机会豁免

- line_id：`futures_trend_winner_trade_forensics`
- 时间：`2026-06-08 22:07 CST`
- 阶段性质：只读特征审计；不改正式配置、不连接 CTP、不调用下单。
- 是否重要突破：否。新增了一个与 Stage012 不同的账户状态口径，但没有找到可靠豁免特征。

## 开始前判断

- 是否过拟合：否。特征只使用候选日前已经平仓的正式版交易结果，不使用未来收益，不按年份、品种、红框窗口倒推。
- 是否仍有价值继续：是。Stage012 用的是账户日级路径，本阶段改看“最近已平仓交易簇”的 realized R、赢家年龄、同方向/同品种同方向历史状态，是另一种账户恢复语义。

## 外部调研与判断

- 调研来源：
  - [Meta-Labeling](https://en.wikipedia.org/wiki/Meta-Labeling)：二级模型/过滤层把方向预测和仓位/是否交易分开。
  - [Hudson & Thames meta-labeling/triple barrier](https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/)：用 primary signal 后的二级标签判断是否交易，但必须防止样本内拟合。
  - [amstrdm/mlm-trend-following](https://github.com/amstrdm/mlm-trend-following)：开源期货趋势策略强调固定趋势规则、波动过滤和 paper 验证，而不是事后挑交易。
- 我的判断：用账户已实现交易状态过滤三连败后的机会，在第一性原理上成立；但 `73` 条 0.1 档样本太小，必须用硬门槛，不能训练模型或扫阈值。

## 本次新增

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage730_account_state_throttle_features.py`
- 输入：
  - Stage716 0.1 档 H40 可标注候选：`73` 条。
  - Stage719 official closed lots：`320` 条。
- 新增特征：
  - `acct_recent_r3/r5/r10_bucket`
  - `acct_recent_win5_bucket`
  - `acct_recent_mfe5_bucket`
  - `acct_last_winner_age_bucket`
  - `acct_last_big_winner_age_bucket`
  - `acct_recent_close_velocity20_bucket`
  - `same_direction_recent_r5_bucket`
  - `same_product_direction_last/r3_bucket`
  - `account_recovery_state_bucket`

## 可靠性门槛

- rows `>=30`
- years `>=4`
- products `>=6`
- dominant product share `<=35%`
- H40 `+2R` first-hit good lift `>=10pp`
- H40 `-1R` first-hit bad rate `<=60%`
- good years `>=4`
- positive-score years `>=4`

## 结果

- baseline H40 good rate：`30.1370%`
- baseline H40 bad rate：`68.4932%`
- baseline path score：`9.9391R`
- 可靠性门槛通过特征：`0`

| 特征 | 桶 | rows | good rate | bad rate | good lift | 失败原因 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `acct_recent_r3_bucket` | `sum_mild_loss` | 30 | 33.3333% | 63.3333% | +3.1963pp | good lift 不足，bad rate 超 60% |
| `acct_last_big_winner_age_bucket` | `age_old_gt60d` | 46 | 34.7826% | 65.2174% | +4.6456pp | good lift 不足，bad rate 超 60%，good years 不足 |
| `acct_last_winner_age_bucket` | `age_mid_21_60d` | 38 | 34.2105% | 65.7895% | +4.0735pp | good lift 不足，bad rate 超 60% |
| `account_recovery_state_bucket` | `mixed_account_state` | 20 | 35.0000% | 65.0000% | +4.8630pp | rows 不足，good lift 不足，bad rate 超 60% |
| `acct_recent_r10_bucket` | `sum10_deep_loss_le_minus5r` | 37 | 35.1351% | 64.8649% | +4.9981pp | good lift 不足，bad rate 超 60%，good years 不足 |

## 产物

- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage730_account_state_throttle_features_decision_stage730_account_state_throttle_features_v1.json`
- metrics：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage730_account_state_throttle_features_feature_metrics_stage730_account_state_throttle_features_v1.csv`
- enriched：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage730_account_state_throttle_features_enriched_candidates_stage730_account_state_throttle_features_v1.csv`
- year detail：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage730_account_state_throttle_features_year_detail_stage730_account_state_throttle_features_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage730_account_state_throttle_features_chart_stage730_account_state_throttle_features_v1.png`

## 结论

- 决策：`no_account_state_reliable_exemption_feature_found`
- 已平仓交易簇状态没有找到能作为正式豁免的可靠特征。
- 这批特征最好的大样本 lift 只有 `+3~5pp`，而 bad rate 仍高于 `60%`，说明它更像弱解释变量，不是高质量机会闸门。
- 不进入 A/C 回测；不改正式版。

## 过拟合反思

- 运行前判断：否，特征事前可定义，且只用候选日前可见 closed lots。
- 运行后判断：若继续调 `3/5/10` 个交易簇窗口、winner age 天数、R-sum 阈值，会变成在 `73` 条样本上过拟合。

## 继续价值反思

- 本形状继续价值低。
- 总目标仍有价值，但下一步应转向更独立的信息源，或只把慢趋势/账户状态放进 forward watch，不在历史样本里继续拼组合。
