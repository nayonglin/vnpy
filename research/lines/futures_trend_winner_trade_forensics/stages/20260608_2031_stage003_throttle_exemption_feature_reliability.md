# Stage003 - 0.1风险档高质量豁免特征可靠性检验

- 时间：2026-06-08 20:31 CST
- 工作模式：day
- line_id：`futures_trend_winner_trade_forensics`
- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage721_throttle_exemption_feature_reliability.py`
- 输出前缀：`qmt_roll_stage721_throttle_exemption_feature_reliability`
- 决策：`no_reliable_positive_exemption_feature_found`
- 是否重要突破版本：否；这是只读法证边界确认，不是正式策略改动。

## 本次问题

用户提出：既然连续亏损 3 笔后风险倍率变成 `0.1` 的阈值在参数扫描里表现最好，那么它到底是不是相对好的参数，是否只是过拟合。

本阶段只回答其中一个关键反证：如果阈值 3 是严重过拟合，那么 `loss_streak>=3` 后的 `0.1` 风险档里应该能找到一批被错杀的高质量机会；若这些高质量机会不能稳定识别，说明阈值 3 更像防守闸门，而不是简单收益曲线拟合。

## 外部调研与判断

- Walk-forward / OOS 验证被多数策略研究资料作为识别过拟合的最低标准；但资料也提醒，即使 walk-forward 本身如果被反复调参，也会产生 meta-overfitting。
  - https://tradingstrategy.ai/glossary/walk-forward-analysis
  - https://quanthop.com/learn/backtesting-optimization/parameter-optimization
  - https://falcoalgo.com/insights/walk-forward-analysis/
- 对连败后减仓的资料和交易实践，本质都不是 alpha 逻辑，而是 capital survival / drawdown throttling。要绕开它，证据门槛应高于普通入场过滤器。
- 本次判断：不能因为某个 0.1 档子样本在历史路径上好看，就允许恢复正常仓位。必须同时满足样本量、年份分散、品种分散、固定标签提升、真实回测不反证。

## 新增内容

- 新增只读检验脚本 `analyze_qmt_roll_stage721_throttle_exemption_feature_reliability.py`。
- 读取 Stage716 的 0.1 档候选标签表：
  - `qmt_roll_stage716_official_throttle_quality_readonly_labeled_candidates_stage716_official_throttle_quality_readonly_v1.csv`
- 只分析 `actionable_throttle=True` 且 H40 标签可用的候选，不修改正式策略、不接 CTP、不调用下单。

## 参数与门槛

新增可靠性门槛：

- `MIN_RELIABLE_ROWS = 30`
- `MIN_RELIABLE_YEARS = 4`
- `MAX_DOMINANT_PRODUCT_SHARE = 35%`
- `MIN_GOOD_LIFT = 10pp`
- `MAX_BAD_RATE = 60%`
- `MIN_SCORE_POSITIVE_YEARS = 4`
- `MIN_GOOD_YEARS = 4`
- 必须没有被历史真实路径回测反证。

候选特征桶：

- 方向、signal case、risk mode、AI rank、RSI、相关性、账户回撤、active positions、pairwise rank、contracts_by_risk、target_risk、stop_distance、breakout、recovery sleeve、risk_multiplier 等。

## 结果

- Stage716 原始候选：`1,082`
- 0.1 档可操作候选：`86`
- H40 标签可用候选：`73`
- H40 baseline +2R first-hit good rate：`30.1370%`
- H40 baseline -1R first-hit bad rate：`68.4932%`
- 通过完整可靠性门槛的特征数：`0`

前五个看起来较强、但未通过的 watch 特征：

| 特征 | 样本 | H40 +2R good | 未通过原因 |
| --- | ---: | ---: | --- |
| `recovery_sleeve_reason=cooldown` | 9 | 55.5556% | 样本不足、年份不足、正年份不足、此前 recovery/scout 类扩展未 promotion |
| `status_scope=sizing_zero_volume` | 20 | 50.0000% | 样本不足；Stage411 强制最小 1 手已显著反证 |
| `pairwise_rank_bucket=pair_missing` | 20 | 50.0000% | 与 sizing-zero 样本高度重合；Stage411/Stage420 反证 |
| `corr_bucket=corr_mid` | 9 | 44.4444% | 样本不足、正年份不足 |
| `contracts_by_risk_bucket=contracts_0` | 11 | 45.4545% | 样本不足、单品种占比超限 |

历史真实路径反证：

- Stage411 zero-volume min-one：正式基准期末权益 `8,728,285`，强制最小 1 手后降至 `6,901,460`；Stage407 口径也从 `3,284,935` 降至 `2,643,000`。
- Stage420 low-risk scout sleeve：正式基准 `8,728,285`，加 scout 后 `8,705,625`，scout PnL `-22,660`。

## 资金类字段

本阶段不是资金曲线回测，而是只读候选特征可靠性检验，因此以下字段不新增：

- 期末权益：不适用；参考正式基准 `8,728,285`
- 总收益：不适用；参考正式基准 `4264.1425%`
- 最大回撤：不适用；参考正式基准 `-38.6713%`
- Sharpe：不适用；参考正式基准 `1.6279`
- 总滑点：不适用；参考正式基准 `506,220`
- 总交易次数：不适用；参考正式基准 raw trades `633`
- 胜率：不适用；参考 closed lots 胜率 `45.3125%`

## 结论

截至 Stage721，连续亏损 3 笔触发 `0.1` 风险倍率更像一个有效的防守阈值，而不是一个可以被内部高质量机会轻易绕开的收益参数。

更严格地说：不能证明它完全没有过拟合，但目前证据不支持“3 是纯过拟合”。理由：

1. 阈值扫描里 `3` 明显优于 `4~12`，且不是通过小数阈值精修得来。
2. Stage719/720 的逐笔法证显示 `loss_streak_ge3`、`risk_floor_01`、`recovery` 是稳定负向状态，分别只有 `1/7` 或 `1/5` 年份正贡献。
3. Stage721 没有在 0.1 档内部找到可靠豁免特征；历史上看起来好的小样本，实际回测已经有反证。

## 过拟合反思

- 开始前判断：继续验证有价值，因为用户的问题不是“再扫参数”，而是要证明阈值 3 是否有机制和反证支撑。
- 结束后判断：本阶段降低了过拟合风险，因为没有新增交易规则，只用预声明门槛去否决看似漂亮的小样本。
- 风险：仍不能把 `3` 视为数学上必然最优；它只是当前历史和机制下最有证据的防守阈值。
- 禁止动作：不要为了证明可以绕过 `0.1`，继续堆叠 `cooldown + sizing_zero + corr_mid` 这类小样本组合，这会非常像过拟合。

## 是否值得继续

- 继续做“在 0.1 档历史样本里挖豁免条件”的价值偏低。
- 更有价值的方向是：
  - 固定阈值 3，做多起点/季度冷启动/弱窗口/成本压力的稳健性验证；
  - 把 `0.1` 档豁免改成 forward watch，不接正式仓位；
  - 如果要找高质量机会，改做账户层独立 selector 或外生特征，而不是在 73 个历史样本里继续组合条件。

## TODO

- 若继续回答“3 是否普适”，下一步优先做阈值 `3/4/6` 的多起点、滚动起始年份、成本翻倍、弱窗口、季度冷启动验证。
- 不继续增加 `loss_streak` 小数或多个复合条件。
