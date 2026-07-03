# Stage019 Stage018 regime gate 失败归因

- 记录时间：`2026-07-01T14:49`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage019_stage018_regime_gate_failure_attribution_v1`
- 是否重要突破版本：`否`
- 决策：`stage019_stage018_failed_by_cutting_right_tail_no_rule`

## 本次版本变更

- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 本阶段只读解释 Stage018 触发事件，不新增交易规则、不改实盘配置。

## 调研和判断结论

- 外部趋势跟随资料强调右尾/正偏/凸性，支持先验证减仓是否伤害趋势右尾。
- 本地证据显示 Stage018 的收益保留失败主要是砍掉 Stage013 的正贡献仓位，不应继续在同一 regime gate 上救参。

## 归因结果

- Stage018 gate 事件：`234`。
- 匹配 Stage013 closed-lot 事件：`232`，匹配率 `99.1453%`。
- 累计减少手数：`9,088`。
- 被减少仓位 Stage013 实现盈亏代理：`7,709,757.17`。
- capped 敏感性代理：`7,868,242.17`；手数完全一致事件代理：`933,604.00`。
- 被减少赢家手数占比：`54.5555%`。
- 收益保留失败 source：`7`；被砍 PnL 代理 `7,665,477.17`；实际期末权益差 `-17,606,410.80`。
- 2022-2023 入场事件被砍 PnL 代理：`73,897.60`。

## 收益保留失败 source 明细

| requested_start_month   |   stage018_minus_stage013_end_equity |   stage018_vs_stage013_return_ratio |   event_count |   removed_pnl_proxy_sum |   removed_proxy_to_actual_loss_ratio |
|:------------------------|-------------------------------------:|------------------------------------:|--------------:|------------------------:|-------------------------------------:|
| 2018-01                 |                         -2.67819e+06 |                            0.767482 |            25 |             1.46359e+06 |                             0.546487 |
| 2018-07                 |                         -3.69925e+06 |                            0.750391 |            26 |             2.01317e+06 |                             0.54421  |
| 2019-01                 |                         -3.59789e+06 |                            0.740436 |            26 |             1.69463e+06 |                             0.471007 |
| 2019-07                 |                         -2.97549e+06 |                            0.625602 |            26 |        939478           |                             0.315739 |
| 2020-01                 |                         -2.24208e+06 |                            0.619768 |            26 |        676255           |                             0.301619 |
| 2020-07                 |                         -1.7516e+06  |                            0.63886  |            26 |        595926           |                             0.340219 |
| 2021-01                 |                    -661910           |                            0.696018 |            31 |        282418           |                             0.426671 |

## 文件

- stage013_rebuilt_closed_lots: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage019_stage018_regime_gate_failure_attribution/rebuilt_c9_stage019_stage018_regime_gate_failure_attribution_stage013_rebuilt_closed_lots_stage019_stage018_regime_gate_failure_attribution_v1.csv`
- event_match: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage019_stage018_regime_gate_failure_attribution/rebuilt_c9_stage019_stage018_regime_gate_failure_attribution_event_match_stage019_stage018_regime_gate_failure_attribution_v1.csv`
- source_delta: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage019_stage018_regime_gate_failure_attribution/rebuilt_c9_stage019_stage018_regime_gate_failure_attribution_source_delta_summary_stage019_stage018_regime_gate_failure_attribution_v1.csv`
- bucket_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage019_stage018_regime_gate_failure_attribution/rebuilt_c9_stage019_stage018_regime_gate_failure_attribution_bucket_summary_stage019_stage018_regime_gate_failure_attribution_v1.csv`
- chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage019_stage018_regime_gate_failure_attribution/rebuilt_c9_stage019_stage018_regime_gate_failure_attribution_chart_stage019_stage018_regime_gate_failure_attribution_v1.png`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage019_stage018_regime_gate_failure_attribution/rebuilt_c9_stage019_stage018_regime_gate_failure_attribution_decision_stage019_stage018_regime_gate_failure_attribution_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage019_stage018_regime_gate_failure_attribution/rebuilt_c9_stage019_stage018_regime_gate_failure_attribution_report_stage019_stage018_regime_gate_failure_attribution_v1.md`

## 后续规划和 TODO

- 停止 Stage018 同形状阈值/手数/窗口救参。
- 下一步优先做“不打断强趋势右尾”的新信息源或选择器，只读验证后再决定是否写真引擎。
- 鸡蛋仍不能直接塞进共享 AI topN；如要推进，必须保持非挤占、小预算、可复验。

## 反思

- 过拟合反思：否。本阶段只做失败归因，没有新增规则；直接用产品/年份 Top 表写规则会过拟合。
- 继续价值反思：有。Stage019 明确关闭一个错误方向，把后续研究资源转向更可能保留右尾的路线。
