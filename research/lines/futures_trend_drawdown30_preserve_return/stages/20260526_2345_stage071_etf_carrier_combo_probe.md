# Stage071 ETF/指数类小资金承载组合探针

- 时间：`2026-05-26 23:45 CST`
- 研究线：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 阶段性质：小资金可承载的低相关工具探针；出现候选，但不是正式版本。
- 是否重要突破：谨慎看待。`95%C3+5%ETF` 首次在当前50万内的小额承载口径下进入 `30%` 回撤以内，并略优于同权重现金稀释；但增量很小，必须进入真实执行复核。

## 调研与判断

- 外部资料方向上，跨资产/ETF/指数类低相关承载有可能改善组合路径；但本阶段没有把外部结论直接当策略依据，只把它作为选择下一类工具的先验。
- 本地判断的核心不是“ETF一定有效”，而是 Stage070 已经证明 2.5万个股整手股票腿无法复刻股票 paper，ETF/指数类产品在小资金、交易单位和分散度上更适合作为下一层承载工具。
- 本阶段必须打败同权重现金稀释，否则只能说明降低 C3 暴露有效，不能说明 ETF 腿有新增价值。

## 版本变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage371_etf_carrier_combo_probe.py`
- 新增回测输出：Stage071 summary、window_summary、annual_summary、daily、decision、report、html。
- 未修改正式 `78-1`、C3、ETF/指数类独立腿交易逻辑。

## 参数

- 组合权重：仅测试 `95%C3+5%ETF`、`90%C3+10%ETF`。
- 现金对照：同权重 `C3+现金`。
- ETF信号篮子：
  - `primary_core_liquid_p10_50000__connors_rsi2_ma200__sleeve10__cap50__cost20bp`
  - `primary_core_liquid_p10_50000__connors_rsi2_ma200__sleeve10__cap30__cost20bp`
  - `primary_core_liquid_p10_50000__connors_rsi2_ma200__sleeve5__cap30__cost20bp`
  - `primary_long_all__connors_rsi2_ma200__sleeve10__cap50__cost20bp`
- 固定ETF候选：
  - `510300.SH bollinger20_2_ma200 sleeve10 cost20`
  - `510300.SH bollinger20_2_ma200 sleeve5 cost20`
  - `515810.SH bollinger20_2_ma200 sleeve10 cost20`
- 预声明闸门：
  - 最大回撤 `>= -30%`
  - 相对 C3 收益保留 `>= 80%`
  - 收益、回撤、Ulcer 同时优于同权重现金
  - ETF独立腿为正收益
  - 多起点和弱窗口不失败

## 核心结果

| 版本 | 总收益 | 最大回撤 | Sharpe | Ulcer | 说明 |
| --- | ---: | ---: | ---: | ---: | --- |
| 正式78-1 | `5062.9570%` | `-40.1659%` | `1.1603` | `20.7905` | 当前正式参照 |
| C3 | `5957.0200%` | `-31.0767%` | `1.3094` | `16.2048` | 当前最强单策略底座 |
| `95%C3+5%ETF核心流动Connors` | `5026.1982%` | `-29.7079%` | `1.3109` | `15.4141` | 本阶段最佳候选 |
| `95%C3+5%现金` | `5003.2797%` | `-29.7155%` | `1.3094` | `15.4303` | 同权重现金对照 |

最佳候选：

- 版本：`C_c3_95_etf_05_sig_core_connors_sleeve10_cap50_cost20bp`
- ETF腿：`primary_core_liquid_p10_50000__connors_rsi2_ma200__sleeve10__cap50__cost20bp`
- 总收益：`5026.1982%`
- 最大回撤：`-29.7079%`
- 相对 C3 收益保留：`84.3744%`
- Sharpe：`1.3109`
- Ulcer：`15.4141`
- ETF独立腿总收益：`8.3869%`
- 现金对照收益：`5003.2797%`
- 决策：`candidate_etf_carrier_requires_real_execution_review`

## 多窗口摘要

| 窗口 | 候选总收益 | 候选最大回撤 | 相对C3收益保留 |
| --- | ---: | ---: | ---: |
| full_common | `5026.1982%` | `-29.7079%` | `84.3744%` |
| start_2021 | `3983.4200%` | `-29.7079%` | `84.7009%` |
| start_2022 | `1473.1495%` | `-29.0421%` | `87.5627%` |
| start_2023 | `672.6641%` | `-18.3172%` | `89.7926%` |
| start_2024 | `277.2683%` | `-18.3172%` | `92.1961%` |
| ytd_2026 | `7.5688%` | `-10.8022%` | `96.1630%` |
| c3_2021_peak_to_trough | `-22.8630%` | `-29.7079%` | `95.2154%` |

## 年度摘要

| 年份 | 候选总收益 | 候选最大回撤 |
| --- | ---: | ---: |
| 2020 | `25.5369%` | `-27.0753%` |
| 2021 | `159.5697%` | `-29.7079%` |
| 2022 | `103.6007%` | `-29.0421%` |
| 2023 | `104.8049%` | `-15.5563%` |
| 2024 | `42.2533%` | `-18.0467%` |
| 2025 | `146.5480%` | `-16.4087%` |
| 2026 | `7.5688%` | `-10.8022%` |

## 结论

- `95%C3+5%ETF核心流动Connors` 是一个可继续复核的候选，不是正式版本。
- 它相对正式78-1明显更平滑：最大回撤从 `-40.1659%` 降至 `-29.7079%`，Ulcer 从 `20.7905` 降至 `15.4141`。
- 它相对 C3 损失收益但仍保留 `84.3744%`，满足当前研究线的收益保留闸门。
- 它相对同权重现金只多约 `22.9185` 个百分点总收益，回撤和 Ulcer 改善也很小。因此不能夸大 ETF 腿 alpha，只能说“略优于现金稀释，值得进入真实性复核”。
- `90%C3+10%ETF` 虽更平滑，最佳为 `4222.9975%/-28.3194%`，但收益保留仅 `70.8911%`，不满足“收益不显著降低”。

## 后续规划

- Stage072 应做 ETF 真实执行复核：
  - ETF最小交易单位、单笔金额、佣金、最低费用、冲击成本。
  - ETF腿真实调仓清单和换手率。
  - 25,000 元 ETF腿是否能真实承载篮子分散度。
  - 1x/2x/3x 成本压力。
  - 最新OOS或paper路径。
- 禁止继续围绕 `4%/6%/7%/8%` ETF权重、单一ETF代码或 Connors 参数小数救援。

## 过拟合反思

- 运行前：不是过拟合。ETF路线来自 Stage070 后的承载约束，而不是按某个历史窗口倒推。
- 运行后：当前结果仍不判定为过拟合，因为只测粗权重、预声明候选、且必须打败现金对照；但候选边际优势很小，继续扫权重或ETF列表会迅速变成过拟合。

## 继续价值反思

- 运行前：有价值。目标是寻找当前50万内可承载的低相关工具。
- 运行后：继续有价值，但下一步只能做真实性复核和OOS，不应继续扫参数。

## 输出

- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage371_etf_carrier_combo_probe_report_stage371_etf_carrier_combo_probe_v1.md`
- HTML：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage371_etf_carrier_combo_probe_equity_drawdown_stage371_etf_carrier_combo_probe_v1.html`
- 决策：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage371_etf_carrier_combo_probe_decision_stage371_etf_carrier_combo_probe_v1.json`
