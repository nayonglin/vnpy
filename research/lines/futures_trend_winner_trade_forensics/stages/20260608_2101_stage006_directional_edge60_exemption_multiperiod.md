# Stage006 directional_edge60 正常风险豁免多周期验证

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：`day`
- 记录时间：`2026-06-08 21:01 CST`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：当前正式版 A/C 策略回放验证
- 是否重要突破：否；有收益线索，但可靠性闸门失败
- 是否触发A/B：是，按 `skills/version-ab-experiment/SKILL.md` 执行；本候选属于可能接入正式版的风险 sizing / high-quality exemption

## 外部调研与判断

- 参考资料：
  - 趋势跟随/Donchian 突破资料支持用价格是否仍处于顺方向区间边缘判断动量持续质量。
  - 三重障碍和 meta-labeling 方法支持先固定候选、再做样本外/多窗口检验，而不是在失败后继续叠条件。
  - 参考链接：`https://github.com/mchiuminatto/triple_barrier`、`https://www.40in20out.com/`、`https://www.tradingview.com/script/DJSQzde0-Breakout-Evidence-Board-TradeDots/`
- 我的判断：`directional_edge60` 是合理的趋势质量特征，但“通过就恢复正常风险开仓”是强干预，必须同时看收益、回撤、成本和冷启动；若只全周期赚钱但弱窗口恶化，就不能作为可靠豁免。

## 预声明 A/C

- A：当前正式 Stage372/20万 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
- C：`stage526_200k_force95_to80_directional_edge60_normal_risk_exemption_stage724`
- C 改动：
  - `enable_streak_entry_structure_risk_recovery=True`
  - `streak_entry_structure_recovery_signals=long_case1a,long_case2,long_case3,short_case1a,short_case2,short_case3`
  - `streak_entry_structure_recovery_require_directional_edge60=True`
  - `streak_entry_structure_recovery_directional_edge_period=60`
  - long `close_pos60 >= 0.80`
  - short `close_pos60 <= 0.20`
  - `enable_recovery_sleeve=False`，通过条件后恢复正常风险 sizing，而不是 one-lot scout
  - `streak_risk_multipliers` 仍为 `1.0,1.0,1.0,0.1`
- 删除参数：无。
- 正式配置修改：无。
- CTP/下单：未连接 CTP，`order_api_called=0`。

## 预声明通过条件

- 全周期收益不低于 A。
- 全周期最大回撤相对 A 不恶化超过 `3pp`。
- 全周期 Sharpe 不恶化超过 `0.05`。
- 总滑点和交易次数增长不超过 A 的 `140%`。
- 2x 成本 full DD 相对 A 不恶化超过 `3pp`。
- broker10 保证金不超过 `100%`。
- start-year 最低收益保持 `>=70%`，最大回撤不恶化超过 `5pp`。
- phase 最低收益保持 `>=65%`，最大回撤不恶化超过 `5pp`。

## 回测结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A 正式版 | 8,728,285 | 4264.1425% | -38.6713% | 1.6279 | 506,220 | 633 | 52.2586% |
| C directional_edge60 正常风险豁免 | 11,819,665 | 5809.8325% | -44.4559% | 1.6294 | 699,640 | 657 | 52.4014% |

- C 相对 A：
  - 期末权益 `+3,091,380`
  - 收益保持 `136.2486%`
  - 最大回撤恶化 `-5.7846pp`
  - Sharpe 基本持平 `+0.0015`
  - 滑点为 A 的 `138.2087%`
  - 交易次数为 A 的 `103.7915%`
  - 强制减仓平仓手数从 `299` 增至 `370`
- 成本压力：
  - A 2x 成本：期末 `8,222,065`，最大回撤 `-40.6555%`
  - C 2x 成本：期末 `11,120,025`，最大回撤 `-46.7784%`
  - 2x 成本回撤相对 A 恶化 `-6.1229pp`
- 关键多窗口：
  - `since_2022`：A `133.8550%/-28.0550%/Sharpe0.8895`；C `451.2450%/-32.8213%/Sharpe1.2088`
  - `since_2024`：A `33.3550%/-29.4347%/Sharpe0.5945`；C `204.5175%/-25.4740%/Sharpe1.4165`
  - `since_2026`：A `1.1450%/-16.3027%/Sharpe0.2783`；C `-9.2950%/-24.5241%/Sharpe-0.6537`
  - `phase_2020_2021`：A `441.4650%/-24.2699%/Sharpe2.1114`；C `438.9575%/-27.8733%/Sharpe2.0920`
  - `phase_2026_latest`：同 `since_2026`，C 明显失败

## Checks

- 通过：
  - `full_return_not_lower`
  - `full_sharpe_not_worse_by_005`
  - `full_slippage_growth_le40pct`
  - `full_trade_count_growth_le40pct`
  - `broker10_100_pass`
  - `account_survival_pass`
- 失败：
  - `full_dd_not_worse_by_3pp`：`-5.7846pp`
  - `cost2_full_dd_not_worse_by_3pp`：`-6.1229pp`
  - `start_years_min_retention_ge70`：最低 `-811.7904%`
  - `start_years_dd_not_worse_by_5pp`：最低 `-8.2214pp`
  - `phase_min_retention_ge65`：最低 `-811.7904%`
  - `phase_dd_not_worse_by_5pp`：最低 `-8.2214pp`

## 路径归因

- C 的收益线索真实存在：全周期多赚 `309.138万`，且 `2022-2025` 多数窗口改善收益和 Sharpe。
- 但 C 的“正常风险豁免”不是可靠特征：
  - 最大回撤窗口提前并加深：A 的最大回撤为 `2022-03-09 -> 2022-12-07`，`-38.6713%`；C 为 `2022-03-09 -> 2022-06-29`，`-44.4559%`。
  - C 在 2022 的深水区放大了早期亏损，说明 `directional_edge60` 仍会把强趋势假突破当作高质量机会。
  - `since_2026` 冷启动失败，A 为 `+1.1450%`，C 为 `-9.2950%`；这不是历史全周期复利能掩盖的风险。
  - full path 里的 2026 C 仍赚更多，是因为 2025 前权益基数更高，不代表 2026 独立样本有效。
- 结论：`directional_edge60` 更像“趋势右尾放大器”，不是“可靠高质量豁免闸门”。它提高收益弹性，但无法控制坏路径。

## 输出文件

- script：`examples/portfolio_backtesting/analyze_qmt_roll_stage724_directional_edge60_exemption_multiperiod.py`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage724_directional_edge60_exemption_multiperiod_summary_stage724_directional_edge60_exemption_multiperiod_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage724_directional_edge60_exemption_multiperiod_comparison_stage724_directional_edge60_exemption_multiperiod_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage724_directional_edge60_exemption_multiperiod_cost_stress_stage724_directional_edge60_exemption_multiperiod_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage724_directional_edge60_exemption_multiperiod_curves_stage724_directional_edge60_exemption_multiperiod_v1.csv`
- annual：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage724_directional_edge60_exemption_multiperiod_annual_stage724_directional_edge60_exemption_multiperiod_v1.csv`
- checks：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage724_directional_edge60_exemption_multiperiod_checks_stage724_directional_edge60_exemption_multiperiod_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage724_directional_edge60_exemption_multiperiod_decision_stage724_directional_edge60_exemption_multiperiod_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage724_directional_edge60_exemption_multiperiod_report_stage724_directional_edge60_exemption_multiperiod_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage724_directional_edge60_exemption_multiperiod_chart_stage724_directional_edge60_exemption_multiperiod_v1.png`

## 结论

- 决策：`directional_edge60_exemption_not_promoted`
- 是否进入正式版：否。
- 是否找到可靠高质量机会豁免特征：否。
- 是否还有研究价值：有，但方向不能是继续给 `directional_edge60` 加小条件；应转向更上游的账户状态/组合状态 selector，或把该特征作为 paper watch 分数而非正常风险豁免。

## 过拟合反思

- 运行前判断：有风险，但可控。只验证 Stage005 唯一初筛候选，阈值固定 `60/0.8/0.2`，不扫品种/年份/红框。
- 运行后判断：不能晋级；若继续加 RSI、OI、volume、年份过滤、品种过滤或调 `0.75/0.85`，会明显转向过拟合。
- 原因：C 的收益提高来自放大趋势右尾，但回撤、成本压力和 2026 冷启动失败说明它没有稳定识别“坏路径中该恢复正常仓位”的机会。

## 继续价值反思

- 运行前判断：有价值，因为 Stage005 是目前唯一外生初筛候选。
- 运行后判断：继续寻找特征仍有价值，但 `directional_edge60` 正常风险豁免本形态没有继续救的价值。
- 下一步 TODO：
  - 不继续扫 `directional_edge_period/close_pos` 小数。
  - 若继续本目标，应把方向转到“账户状态 + 机会质量”联合、但必须预声明并做 forward/冷启动验证。
  - `directional_edge60` 可以保留为 paper/watch 分数，不接正式交易 sizing。
