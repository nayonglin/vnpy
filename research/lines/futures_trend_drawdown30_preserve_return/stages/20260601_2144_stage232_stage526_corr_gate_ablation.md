# Stage232 Stage526同向相关性门控强度/关闭反证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-01 21:44 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：固定 Stage526 主候选的 A/C 真实引擎反证；只测试同向相关性门控强度放宽与完全关闭。
- 是否重要突破：否，未形成替代候选；但形成重要机制判断：门控本身有用，当前 floor0.35 可能略过严。
- 是否触发A/B：是。该门控若通过会改变当前候选入场侧风险治理，已读取 `skills/version-ab-experiment/SKILL.md`，按隔离 A/C 记录。

## 外部调研与判断

- 参考资料：
  - Moskowitz/Ooi/Pedersen 的 time-series momentum 研究说明趋势跟随需要跨市场分散组合，且通常用期货多资产组合承载趋势收益：https://research.cbs.dk/en/publications/time-series-momentum
  - `Time series momentum and volatility scaling` 强调趋势组合结果很大程度受波动缩放/风险预算影响：https://www.sciencedirect.com/science/article/pii/S1386418116301379
  - PyTrendFollow 是公开的系统化期货趋势跟随工程样例，强调自动换月、回测和 IB 交易链路：https://github.com/chrism2671/PyTrendFollow
  - MLM style trend-following repo 使用连续合约信号、前月合约执行和波动过滤，说明工程上常见做法是先保持简单可解释：https://github.com/amstrdm/mlm-trend-following
- 我的判断：
  - 相关性/分散化治理是趋势组合的一阶问题，但不能机械压制所有同向高相关信号，因为大趋势常常以同向扩散形式出现。
  - 因此本阶段不扫相关性阈值，只做两个机制性反证：`floor0.35 -> 0.50` 与 `disable`。

## 本次变更

- 新增脚本：无。
- 修改脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage532_stage526_corr_gate_frontier.py`
- 删除脚本：无。
- 新增参数：
  - `r080_pc25_maxpos4_corr20_f50`：`same_direction_correlation_gate_weight_floor=0.50`
  - `r080_pc25_maxpos4_no_corr_gate`：`enable_same_direction_correlation_gate=False`
- 修改参数：
  - 原控制组确认继承 C3 override：`enable_same_direction_correlation_gate=True`、`lookback=20`、`start=0.60`、`full=0.80`、`floor=0.35`
  - 报告/图表口径从“开启门控”修正为“门控强度/关闭反证”。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-01` 至 `2026-04-30`
- 账户规模：C3 `500,000` 下单口径，组合账户沿用 Stage526 当前口径。
- 成本口径：正常成本 `1x`，压力成本 `2x/3x`。
- 样本过滤：固定 Stage526 `risk_multiplier=0.80 + product cap25 + max_concurrent_positions=4`，不改 AI 池、入场信号、退出规则、品种池。
- 策略/归因口径：
  - control：Stage526 当前候选复刻，含同向相关性门控 `floor0.35`
  - C1：同向相关性门控下限放宽到 `floor0.50`
  - C2：完全关闭同向相关性门控

## 结果

### 1x 全周期

| 版本 | 期末权益 | 总收益 | 最大回撤 | Ulcer | Sharpe | broker10最大 | 总滑点 | 总交易次数 | 胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| control floor0.35 | 23,369,505 | 3699.9195% | -36.2670% | 14.4691 | 1.6385 | 99.7299% | 1,342,190 | 905 | 53.6330% |
| C1 floor0.50 | 23,976,380 | 3798.5984% | -35.2005% | 14.3359 | 1.6390 | 99.5891% | 1,382,590 | 905 | 53.5581% |
| C2 no gate | 20,529,765 | 3238.1732% | -45.3266% | 17.1767 | 1.5647 | 101.3947% | 1,301,020 | 909 | 53.3033% |

### 成本压力

| 版本 | 2x最大回撤 | 3x最大回撤 | 3x收益 | 3x broker10最大 |
| --- | ---: | ---: | ---: | ---: |
| control floor0.35 | -39.0565% | -42.0555% | 3263.4350% | 115.5222% |
| C1 floor0.50 | -37.9788% | -40.9656% | 3348.9756% | 115.6513% |
| C2 no gate | -48.4485% | -51.8046% | 2815.0772% | 119.8230% |

### 任意启动持有体验

| 版本 | 63日p05 | 126日p05 | 252日p05 | 504日p05 | 63日胜率 | 126日胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| control floor0.35 | -18.2169% | -10.9700% | 5.1196% | 74.0517% | 76.7869% | 86.3442% |
| C1 floor0.50 | -18.3507% | -9.8247% | 5.7953% | 76.1962% | 77.1273% | 86.6287% |
| C2 no gate | -18.4771% | -17.9666% | -8.8218% | 54.1991% | 74.6767% | 84.9929% |

### 2022 主失败窗口

- 最大回撤窗口仍是 `2022-03-09 -> 2022-12-07`，说明本阶段没有改变风险发生时点，只改变损失强度。
- control 正常成本窗口净亏 `-1,614,915`，C1 `-1,583,125`，C2 `-2,374,835`。
- 3x成本窗口最大回撤：control `-42.0555%`，C1 `-40.9656%`，C2 `-51.8046%`。
- C2 关闭门控后 `fu.SHFE/MA.CZCE/sp.SHFE/FG.CZCE` 等亏损扩大，说明该门控确实在 2022 长水下有保护作用。

### 门控触发

- control：候选行 `1082`，门控生效行 `1082`，被缩放行 `84`，最低权重 `0.35`，最终开仓且缩放 `28` 行。
- C1：候选行 `1082`，门控生效行 `1082`，被缩放行 `84`，最低权重 `0.50`，最终开仓且缩放 `28` 行。
- C2：候选行 `1083`，门控生效 `0`，实际开仓 `318`，比 control 多 `2` 次，但回撤显著恶化。

## 图表视觉复盘

- 图表：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage532_stage526_corr_gate_frontier_chart_stage532_stage526_corr_gate_frontier_v1.png`
- 视觉判断：
  - 红线 C1 在 2022 主回撤期只小幅减伤，之后逐步累积正 edge，最终略高于 control。
  - 蓝线 C2 关闭门控在 2022 后显著掉队，水下曲线跌破 -40%，2024-2026 也没有修复相对劣势。
  - p05 柱状图显示 C1 的 126日左尾改善，但 63日左尾轻微恶化；C2 在 126日左尾明显恶化。
  - 因此图表支持“门控必须保留，但 floor0.35 可疑偏严”，不支持关闭门控。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage532_stage526_corr_gate_frontier_report_stage532_stage526_corr_gate_frontier_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage532_stage526_corr_gate_frontier_summary_stage532_stage526_corr_gate_frontier_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage532_stage526_corr_gate_frontier_margin_daily_stage532_stage526_corr_gate_frontier_v1.csv`
- candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage532_stage526_corr_gate_frontier_candidate_snapshots_stage532_stage526_corr_gate_frontier_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage532_stage526_corr_gate_frontier_decision_stage532_stage526_corr_gate_frontier_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage532_stage526_corr_gate_frontier_chart_stage532_stage526_corr_gate_frontier_v1.png`

## 结论

- 本阶段结论：`r080_pc25_maxpos4_corr20_f50` 不替代 Stage526，但进入观察候选；`no_corr_gate` 明确失败。
- 是否进入下一步：是，但不是继续扫 `floor=0.45/0.55/0.60`。下一步应做“相关性门控触发日逐笔归因”：确认 28 个实际缩放开仓中，哪些是保护性、哪些是误伤趋势扩散。
- 下一步：
  - 固定 control 与 C1，输出 28 个缩放开仓的逐笔对照账本。
  - 重点看 2022 主窗口和 2024-2026 后段 edge，判断 floor0.50 的正 edge 是否来自少数大波段，还是分散稳定。
  - 若误伤集中在高趋势强度状态，再考虑用低自由度趋势强度条件释放门控；若误伤不稳定，则保留 Stage526 control。

## 过拟合反思

- 运行前判断：否。只做机制性 A/C 反证，不扫阈值。
- 运行后判断：否，但不能继续细扫 floor 小数。
- 原因：C1 改善不是靠单一窗口定制，full/since2021/since2022/phase2022_2023 多个口径均改善；但 63日 p05 未过闸门，且 3x成本仍未回到 -40% 内，因此不能为了这点改善继续调小数。

## 继续价值反思

- 运行前判断：是。Stage526 未完成风险来自长水下与成本压力，相关性门控是低自由度组合风险变量。
- 运行后判断：是，但方向要收窄。
- 原因：关闭门控大幅失败，证明该模块是有效风险部件；floor0.50 改善全周期、回撤、Ulcer、2x/3x成本和126/252/504日左尾，说明当前强度存在可优化空间。不过 C1 未通过完整晋级闸门，只能进入逐笔误伤/保护归因，不能直接合入。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage232 结论。
- 是否更新 `research/registry.md`：是，更新最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；不追加 `memory.md`，因为没有形成未来默认政策变更。
