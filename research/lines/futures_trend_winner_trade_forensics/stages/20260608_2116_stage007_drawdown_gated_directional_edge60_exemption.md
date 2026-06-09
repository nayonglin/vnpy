# Stage007 账户健康门控的 directional_edge60 高质量豁免验证

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：`day`
- 记录时间：`2026-06-08 21:16 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：当前正式版 Stage372/20万三连败后正常风险豁免 A/C 多周期验证。
- 是否重要突破：否；属于有信息量的负结论。
- 是否触发A/B：已读取并遵循 `skills/version-ab-experiment/SKILL.md`；本阶段为 A/C 验证，因未通过鲁棒性门槛，不进入正式 A/B 或 promotion。

## 外部调研与判断

- 参考资料：
  - 趋势跟踪仓位/回撤纪律参考：`https://github.com/trustdan/trend-following-backtesting-strategies`
  - Regime filter 概念参考：`https://www.darwintiq.com/articles/what-is-a-regime-filter`
  - Meta-labeling/交易过滤概念参考：`https://en.wikipedia.org/wiki/Meta-Labeling`
- 我的判断：外部资料支持把信号质量过滤和账户/市场状态结合，而不是只看 entry 本身；但这些资料不能证明本组合的豁免规则有效。Stage725 因此只做一个预声明结构：机会必须满足 `directional_edge60`，账户必须仍接近高水位，且不扫 drawdown 阈值。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage725_drawdown_gated_directional_edge60_exemption.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - `ACCOUNT_HEALTH_MAX_DRAWDOWN=0.05`
  - `DIRECTIONAL_EDGE_PERIOD=60`
  - `LONG_CLOSE_POSITION_MIN=0.80`
  - `SHORT_CLOSE_POSITION_MAX=0.20`
  - `RECOVERY_SIGNALS=long_case1a,long_case2,long_case3,short_case1a,short_case2,short_case3`
- 修改参数：
  - C 候选启用 `enable_streak_entry_structure_risk_recovery=True`
  - C 候选启用 `streak_entry_structure_recovery_require_directional_edge60=True`
  - C 候选设置 `streak_entry_structure_recovery_max_portfolio_drawdown_pct=0.05`
  - C 候选关闭 `enable_recovery_sleeve=False`，使通过条件的机会恢复正常风险 sizing，而不是一手 sleeve。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`，并输出 `since_2021` 至 `since_2026` 起始年窗口和 `2020-2021`、`2022-2023`、`2024-2025`、`2026_latest` 阶段窗口。
- 账户规模：`200,000`。
- 成本口径：官方回测成本；另输出 `1x/2x/3x` 成本压力。
- 样本过滤：不按品种、方向、年份、红框窗口筛选；只用事前可得账户回撤和 K 线区间位置。
- 策略/归因口径：
  - A：当前正式 Stage372/20万 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
  - C：A 的连败倍率仍为 `1,1,1,0.1`，仅在 `directional_edge60` 且账户回撤 `<=5%` 时允许三连败后的 clean-book recovery 正常风险开仓。

## 结果

- A 全周期：
  - 期末权益：`8,728,285`
  - 总收益：`4264.1425%`
  - 最大回撤：`-38.6713%`
  - Sharpe：`1.6279`
  - 总滑点：`506,220`
  - 总交易次数：`633`
  - 胜率：`52.2586%`
- C 全周期：
  - 期末权益：`10,415,070`
  - 总收益：`5107.5350%`
  - 最大回撤：`-38.8730%`
  - Sharpe：`1.6384`
  - 总滑点：`597,710`
  - 总交易次数：`655`
  - 胜率：`52.3156%`
- C 相对 A：
  - 全周期收益保留 `119.7787%`
  - 全周期回撤仅恶化 `0.2017pp`
  - Sharpe 增加 `0.0105`
  - 2x 成本全周期回撤仅恶化 `0.6587pp`
  - broker10 峰值 `83.3212%`，未穿 `100%`
- 关键失败窗口：
  - `since_2021`：C `1975.5425%/-49.1004%/Sharpe1.4846`，A `2221.3050%/-38.1656%/Sharpe1.5636`，回撤恶化 `10.9348pp`。
  - `since_2022`：C `-19.6200%/-34.2150%/Sharpe-0.2795`，A `133.8550%/-28.0550%/Sharpe0.8895`。
  - `phase_2022_2023`：C `-32.2300%/-32.2300%/Sharpe-2.0381`，A `0.2975%/-28.0550%/Sharpe0.1053`，C 交易 `34` 笔，A 交易 `78` 笔。
  - `since_2026` / `phase_2026_latest`：C `1.9600%/-13.9446%/Sharpe0.3598`，A `1.1450%/-16.3027%/Sharpe0.2783`；Stage725 修复了 Stage724 的 2026 独立起点失败。
- hard_fail_checks：
  - `start_years_min_retention_ge70`
  - `start_years_dd_not_worse_by_5pp`
  - `phase_min_retention_ge65`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage725_drawdown_gated_directional_edge60_exemption_report_stage725_drawdown_gated_directional_edge60_exemption_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage725_drawdown_gated_directional_edge60_exemption_summary_stage725_drawdown_gated_directional_edge60_exemption_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage725_drawdown_gated_directional_edge60_exemption_curves_stage725_drawdown_gated_directional_edge60_exemption_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage725_drawdown_gated_directional_edge60_exemption_comparison_stage725_drawdown_gated_directional_edge60_exemption_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage725_drawdown_gated_directional_edge60_exemption_cost_stress_stage725_drawdown_gated_directional_edge60_exemption_v1.csv`
- checks：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage725_drawdown_gated_directional_edge60_exemption_checks_stage725_drawdown_gated_directional_edge60_exemption_v1.csv`
- annual：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage725_drawdown_gated_directional_edge60_exemption_annual_stage725_drawdown_gated_directional_edge60_exemption_v1.csv`
- monthly：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage725_drawdown_gated_directional_edge60_exemption_monthly_stage725_drawdown_gated_directional_edge60_exemption_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage725_drawdown_gated_directional_edge60_exemption_decision_stage725_drawdown_gated_directional_edge60_exemption_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage725_drawdown_gated_directional_edge60_exemption_chart_stage725_drawdown_gated_directional_edge60_exemption_v1.png`

## 结论

- 本阶段结论：`drawdown_gated_directional_edge60_exemption_not_promoted`。
- 是否进入下一步：不进入正式 A/B，不接正式版；可作为“账户健康门控能修复 2026，但不能修复 2022-2023”的研究材料。
- 下一步：不扫 `5%/10%/15%` 账户回撤阈值，不叠 RSI/OI/volume/品种/年份条件救参。若继续当前目标，应转向更上游的账户级 selector 或 forward watch；selector 的目标必须显式惩罚 `2022-2023` 冷启动损伤，而不是只优化全周期和 2024-2025。

## 过拟合反思

- 运行前判断：不是直接过拟合。`directional_edge60 + 账户回撤<=5%` 是事前结构，`5%` 来自已有 near-high 账户健康语义，不是从结果扫出来。
- 运行后判断：如果推广会过拟合。它全周期好看、2026 也修复，但 `since_2022` 与 `phase_2022_2023` 明确失败，说明这不是穿越周期的可靠豁免。
- 原因：账户健康门控能在账户受伤后停止继续放大风险，但无法识别“刚开始从高水位犯错”的阶段；2022 独立启动里早期正常风险错误叠加后，账户脱离近高水位，又错过后续恢复交易，导致收益和参与率双杀。

## 继续价值反思

- 运行前判断：有价值继续，因为 Stage724 的核心失败在坏路径和 2026，账户健康门控是第一性原理上合理的修正。
- 运行后判断：目标仍有价值，但当前形状不值得继续调参。
- 原因：Stage725 明确把问题从“单一趋势边缘不行”推进到“趋势边缘 + 账户近高水位仍不能跨 2022-2023”；这减少了后续搜索空间。继续价值在于重新定义 selector 目标或 forward watch，而不是继续加条件。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，作为影响后续搜索边界的重要负结论。
