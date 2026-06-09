# Stage014 慢趋势一致性审计：0.1 档高质量机会豁免

- line_id：`futures_trend_winner_trade_forensics`
- 时间：`2026-06-08 22:09 CST`
- 阶段性质：只读特征审计；不改正式配置、不连接 CTP、不调用下单。
- 是否重要突破：否。慢趋势出现 watch 线索，但没有达到可靠特征门槛。

## 开始前判断

- 是否过拟合：否。120/200 日收益、50/200 与 100/200 均线一致性是趋势跟随里的通用慢趋势定义，不按红框或单品种定制。
- 是否仍有价值继续：是。Stage723/724 已证明 `directional_edge60` 更像右尾放大器而不是可靠闸门；慢趋势可以验证“更大级别趋势”是否更稳。

## 外部调研与判断

- 调研来源：
  - [Time Series Momentum](https://research.cbs.dk/en/publications/time-series-momentum)：期货在 1-12 个月存在时间序列动量证据。
  - [FuturesBacktest Trend Following](https://www.futuresbacktest.com/docs/strategies/trend/)：趋势系统常见指标族包括均线/指数均线、breakout、线性趋势等。
  - [QuantConnect Adjusted Trend on Futures](https://www.quantconnect.com/research/15959/adjusted-trend-on-futures/)：趋势预测可影响期货仓位大小，但需要实证验证。
- 我的判断：慢趋势是比 60 日边缘更通用的候选方向；但如果它只在十几笔样本里有效，就不能声称穿越周期。

## 本次新增

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage731_slow_trend_throttle_features.py`
- 输入：
  - Stage723 enriched 的基础 0.1 档 H40 可标注候选：`73` 条。
  - 本地 `.vntrader/database.db` 产品日线。
- universe：`18` 个产品。
- 新增特征：
  - `product_signed_ret120_bucket`
  - `product_signed_ret200_bucket`
  - `product_directional_edge120_bucket`
  - `product_directional_edge200_bucket`
  - `product_ma50_200_alignment_bucket`
  - `product_ma100_200_alignment_bucket`
  - `product_slow_trend_consensus_bucket`
  - `product_fast_slow_agreement_bucket`
  - `product_slow_trend_without_fast_edge_bucket`

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
- 120 日收益覆盖：`93.1507%`
- 200 日收益覆盖：`90.4110%`
- MA200 覆盖：`93.1507%`
- 可靠性门槛通过特征：`0`

| 特征 | 桶 | rows | good rate | bad rate | good lift | 失败原因 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `product_fast_slow_agreement_bucket` | `fast_edge_and_slow_consensus` | 14 | 57.1429% | 42.8571% | +27.0059pp | rows<30 |
| `product_slow_trend_consensus_bucket` | `slow_consensus_aligned` | 24 | 45.8333% | 50.0000% | +15.6963pp | rows<30 |
| `product_directional_edge120_bucket` | `directional_edge120` | 19 | 47.3684% | 52.6316% | +17.2314pp | rows<30，positive-score years 不足 |
| `product_ma50_200_alignment_bucket` | `ma50_200_aligned` | 30 | 40.0000% | 56.6667% | +9.8630pp | good lift<10pp |
| `product_signed_ret200_bucket` | `signed_ret_strong_pos` | 24 | 41.6667% | 54.1667% | +11.5297pp | rows<30 |

## 产物

- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage731_slow_trend_throttle_features_decision_stage731_slow_trend_throttle_features_v1.json`
- metrics：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage731_slow_trend_throttle_features_feature_metrics_stage731_slow_trend_throttle_features_v1.csv`
- enriched：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage731_slow_trend_throttle_features_enriched_candidates_stage731_slow_trend_throttle_features_v1.csv`
- year detail：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage731_slow_trend_throttle_features_year_detail_stage731_slow_trend_throttle_features_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage731_slow_trend_throttle_features_chart_stage731_slow_trend_throttle_features_v1.png`

## 结论

- 决策：`no_slow_trend_reliable_exemption_feature_found`
- 慢趋势一致性是目前最像“高质量机会”的 watch 线索，但还不是可靠特征。
- `fast_edge_and_slow_consensus` 的 good rate 高达 `57.1429%`，bad rate 低到 `42.8571%`，但只有 `14` 条；`slow_consensus_aligned` 也只有 `24` 条。
- `ma50_200_aligned` 满足 rows=30、years=7、products=14、bad rate=56.6667%，但 good lift 只有 `+9.8630pp`，没有越过预声明 `+10pp` 门槛。不能因为差 `0.137pp` 就降低门槛。
- 不进入 A/C 回测；不改正式版。

## 过拟合反思

- 运行前判断：否，慢趋势窗口来自趋势跟随通用经验，不是针对红框。
- 运行后判断：若现在为了让 `ma50_200_aligned` 过线而改 `10pp` 门槛，或扫 `100/150/180/250` 日窗口，就是明显过拟合。

## 继续价值反思

- 本形状不值得立刻回测交易化。
- 但慢趋势一致性值得放入 forward watch：未来每笔 0.1 档候选提前记录是否 `fast_edge_and_slow_consensus`，积累 OOS 样本后再判断。
