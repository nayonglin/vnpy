# Stage004 - 0.1风险档豁免规则OOS压力测试

- 时间：2026-06-08 20:38 CST
- 工作模式：day
- line_id：`futures_trend_winner_trade_forensics`
- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage722_throttle_exemption_rule_oos.py`
- 输出前缀：`qmt_roll_stage722_throttle_exemption_rule_oos`
- 决策：`no_reliable_exemption_rule_found`
- 是否重要突破版本：否；这是只读压力测试，不是正式策略变更。

## 本次问题

Stage721 已经证明：在 Stage716 的 0.1 风险档候选里，单变量特征没有一个能通过可靠性门槛。

本阶段继续问一个更尖锐的问题：如果允许最多两个条件组成简单规则，是否能找到可用于“高质量机会豁免”的稳定规则。

## 外部调研与判断

- Meta-labeling / triple-barrier 的思路适合本问题：原始趋势策略负责方向，二级标签只判断某个已有入场信号是否值得通过或放大。
  - https://github.com/Decentralised-AI/trading-triple-barrier
  - https://github.com/Neyt/How-To-Backtest-Correctly
  - https://tradingstrategy.ai/docs/learn/machine-learning.html
- 但资料也强调，walk-forward / purged OOS / CPCV 是为了对抗选择偏差；如果在小样本里扫很多组合，即使看起来通过，也可能只是二次过拟合。
- 本阶段判断：允许最多两个条件只是为了压力测试“有没有明显强特征”，不能作为正式上线依据；若它都全灭，则说明现有字段下继续拼历史规则的价值很低。

## 新增内容

- 新增只读脚本 `analyze_qmt_roll_stage722_throttle_exemption_rule_oos.py`。
- 读取 Stage716 的 0.1 档 H40 标签可用候选。
- 构建预声明原子条件 `52` 个，包括：
  - status/sizing、direction、signal；
  - AI rank/score；
  - pairwise rank/score；
  - RSI 方向强度；
  - 相关性、账户回撤、active positions；
  - contracts_by_risk、stop distance、breakout、recovery sleeve。
- 组合规则限制：
  - 最多 `2` 个条件；
  - 禁止品种名、年份名、红框日期；
  - 已被历史真实回测反证的 `sizing_zero_volume/pair_missing/cooldown/contracts_by_risk=0` 形状自动降级。

## 参数与门槛

- `MAX_RULE_ATOMS = 2`
- `MIN_RULE_ROWS = 30`
- `MIN_RULE_YEARS = 4`
- `MIN_RULE_PRODUCT_COUNT = 6`
- `MAX_DOMINANT_PRODUCT_SHARE = 35%`
- `MIN_GOOD_LIFT_PP = 10`
- `MAX_BAD_RATE_PCT = 60`
- `MIN_LOO_TEST_YEARS = 4`
- `MIN_LOO_TEST_ROWS = 12`
- `MIN_LOO_GOOD_YEARS = 3`
- `MIN_LOO_SCORE_POSITIVE_YEARS = 3`
- anchored selector 至少需要过去两年训练样本，且训练规则必须满足基本样本、年份、good lift、bad rate、品种分散和无历史反证。

## 结果

- 0.1 档 H40 标签可用候选：`73`
- 原子条件：`52`
- 筛选规则：`971`
- 通过完整规则门槛：`0`
- anchored selector 测试年份：`5`
- anchored selector 实际选出规则年份：`2`
- anchored selector 选出样本：`3`
- anchored selector OOS good rate：`0.0000%`
- anchored selector OOS bad rate：`100.0000%`
- anchored baseline good rate：`30.0000%`
- anchored baseline bad rate：`68.3333%`

最强 watch 规则全部失败：

| 规则 | 样本 | H40 good | 失败原因 |
| --- | ---: | ---: | --- |
| `status_scope=sizing_zero_volume & direction=short` | 8 | 62.5000% | 样本/年份/LOO不足，且被 Stage411/420 反证 |
| `direction=short & recovery_sleeve_reason=cooldown` | 8 | 62.5000% | 样本/年份/LOO不足，且 recovery/scout 扩展未 promotion |
| `status_scope=sizing_zero_volume & ai_score_ge050` | 14 | 57.1429% | 样本/年份不足，且 sizing-zero 真实回测反证 |
| `status_scope=sizing_zero_volume & rsi_direction_bucket=rsi_strong` | 18 | 55.5556% | 样本不足、单品种占比超限，且真实回测反证 |
| `recovery_sleeve_reason=cooldown` | 9 | 55.5556% | 与 Stage721 一致，仍是小样本 watch，不可交易化 |

anchored selector：

| 测试年 | 选出规则 | 测试样本 | OOS good | OOS bad |
| --- | --- | ---: | ---: | ---: |
| 2022 | 无 | 0 | 不适用 | 不适用 |
| 2023 | 无 | 0 | 不适用 | 不适用 |
| 2024 | 无 | 0 | 不适用 | 不适用 |
| 2025 | `ai_rank_bucket=rank_1_3 & rsi_direction_bucket=rsi_strong` | 2 | 0.0000% | 100.0000% |
| 2026 | `direction=short & ai_score_ge050` | 1 | 0.0000% | 100.0000% |

## 资金类字段

本阶段不是资金曲线回测，而是只读 OOS 压力测试，因此以下字段不新增：

- 期末权益：不适用；参考正式基准 `8,728,285`
- 总收益：不适用；参考正式基准 `4264.1425%`
- 最大回撤：不适用；参考正式基准 `-38.6713%`
- Sharpe：不适用；参考正式基准 `1.6279`
- 总滑点：不适用；参考正式基准 `506,220`
- 总交易次数：不适用；参考正式基准 raw trades `633`
- 胜率：不适用；参考 closed lots 胜率 `45.3125%`

## 结论

现有 Stage716/719 字段下，没有找到可以作为高质量机会豁免的可靠特征或简单规则。

更重要的是，最强规则几乎都落在 `sizing_zero_volume / pair_missing / cooldown` 这一类历史已反证或小样本区域。它们在固定 H40 标签上看起来亮眼，但真实路径回测和 anchored OOS 都不支持用来恢复正常仓位。

## 过拟合反思

- 开始前判断：继续做 Stage722 有价值，因为 Stage721 只否决了单变量；用户目标仍是寻找可靠豁免特征。
- 结束后判断：继续在这 73 个历史样本里组合条件，过拟合风险已经非常高；再往下做三条件、更多阈值、按年份/方向微调，基本就是历史拟合。
- 当前结论不是“永远找不到高质量机会”，而是“现有字段和历史样本不能证明有可上线豁免规则”。

## 是否值得继续

- 继续挖现有历史字段：价值低。
- 继续目标本身：仍有价值，但必须换证据源：
  - 增加 forward watch 样本，不真实加仓，只记录若恢复正常仓位会如何；
  - 引入外生特征，例如板块/产业链状态、跨品种持仓拥挤、期限结构、主力换月流动性，而不是只看已有入场日志；
  - 如果坚持规则化，先预声明一个单一候选，再做 paper，不再从 `971` 个组合里挑。

## TODO

- 不把 Stage722 任何规则接入正式版。
- 当前正式版继续保持 `loss_streak>=3 -> 0.1` 无豁免。
- 下一步若继续本目标，应转为 forward watch 或新增外生特征源；不继续在现有 `73` 个 0.1 档样本上扫组合。
