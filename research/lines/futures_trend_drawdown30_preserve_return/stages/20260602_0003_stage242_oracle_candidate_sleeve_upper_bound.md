# Stage242 Oracle6 卫星仓上限验证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-02 00:03 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：hindsight 上限验证；产品来自 Stage241 全样本单品种机会图，因此不能直接晋级。
- 是否重要突破：是，证明“选对品种 + 非挤占式 sleeve”有材料性上限空间；但不是实盘候选。
- 是否触发A/B：是。C 为 Stage526 核心完全保留 + Oracle6 sleeve。

## 外部调研与判断

- 参考资料：
  - AQR 趋势跟随长期证据：市场分散能提高趋势策略穿越周期能力。
  - Time-Series Momentum 多市场数据：品种池越广，越需要低相关和可交易成本约束。
  - managed futures / crisis alpha 研究：多品种趋势组合的收益来自少数市场在少数年份的强趋势，但不能用事后赢家构建实盘池。
- 我的判断：
  - Stage241 的 `lu/v/al/y/c/ao` 是全样本诊断筛出的“可能长相”，不是直接可交易规则。
  - 若这组上限篮子都不能改善 Stage526，扩品种方向可以明显降级；若它能改善，下一步必须研究如何用事前特征在当时识别类似产品。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage542_oracle_candidate_sleeve_upper_bound.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - Oracle6 产品：`lu.INE/v.DCE/al.SHFE/y.DCE/c.DCE/ao.SHFE`
  - C1：`core_plus_oracle6_r030_pc15_maxpos3`
  - C2：`core_plus_oracle6_r050_pc15_maxpos3`
  - C3：`core_plus_oracle6_r050_pc10_maxpos4`
  - sleeve 资金：`115000`
  - 上限通过定义：卫星PnL材料性、总收益提高、最大回撤不劣化、broker10<=100且无穿越
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30。
- 账户规模：Stage526 账户 `615000` 保持不变，Oracle6 用 `115000` sleeve 表达。
- 成本口径：真实下一窗口成交、正常滑点；同时输出 2x/3x 成本压力。
- 样本过滤：使用 Stage241 全样本材料性候选，故本阶段是上限验证，不是可实盘筛选。
- 策略/归因口径：Stage526 核心不替换、不重排；Oracle6 只作为非挤占式卫星仓叠加。

## 结果

| 版本 | 期末权益 | 总收益 | 相对Stage526 | 最大回撤 | Ulcer | Sharpe | broker10最大 | 2x DD | 3x DD | 卫星PnL | 滑点 | 交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage526 control | 23,369,505 | 3699.9195% | 100.0000% | -36.2670% | 14.4691 | 1.6385 | 99.7299% | -39.0565% | -42.0555% | 0 | 1,342,190 | 905 |
| C1 r030 pc15 maxpos3 | 23,428,935 | 3709.5829% | 100.2612% | -36.1775% | 14.3989 | 1.6446 | 98.9521% | -38.9649% | -41.9617% | 59,430 | 1,345,350 | 1,077 |
| C2 r050 pc15 maxpos3 | 23,488,930 | 3719.3382% | 100.5248% | -36.1186% | 14.3536 | 1.6485 | 98.4755% | -38.9027% | -41.8958% | 119,425 | 1,347,620 | 1,150 |
| C3 r050 pc10 maxpos4 | 23,437,065 | 3710.9049% | 100.2969% | -36.1141% | 14.3841 | 1.6458 | 98.8522% | -38.8949% | -41.8845% | 67,560 | 1,345,000 | 1,082 |

### 3/6个月持有体验

| 版本 | 63日p05 | 63日中位 | 126日p05 | 126日中位 | 判断 |
| --- | ---: | ---: | ---: | ---: | --- |
| Stage526 | -18.2169% | 14.2303% | -10.9700% | 27.5593% | 基准 |
| C2 oracle6 | -18.0807% | 14.1928% | -10.8745% | 27.5985% | 左尾小幅改善，中位基本持平 |

### 卫星 standalone

- C2 sleeve 期末权益 `234,425`，sleeve 总收益 `103.8478%`，最大回撤 `-14.8095%`，Sharpe `1.0293`，交易 `245`，滑点 `5,430`，最大 sleeve 保证金 `41,979`。
- 产品年度贡献显示 C2 的主要贡献来自：
  - `lu.INE`：2026 `+55,020`，但 2022/2023/2024 为负，近端贡献占比高。
  - `v.DCE`：2020-2025 多年稳定正贡献。
  - `y.DCE`：2020/2021/2023/2024/2025 有正贡献，2022 小负。
  - `ao.SHFE`：2024 强，2025 小负。

## 图表视觉复盘

- 权益图：C2 相对 Stage526 有肉眼可见但不大的抬升，主要在 2026 之后变明显。
- 回撤图：C2 在 2021-2022 深坑略浅，但没有改变主风险形状；最大回撤只从 `-36.2670%` 到 `-36.1186%`。
- 卫星PnL：2020-2021 已有一段抬升，2023 附近回吐，2024/2025 横盘震荡，2026 因 `lu` 快速拉升。这说明它不是均匀年度收益源，仍需防止近端过拟合。
- 3/6个月左尾：改善为 `0.1362pp/0.0955pp`，比 Stage540 明确，但仍不是“持有体验大改造”。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage542_oracle_candidate_sleeve_upper_bound_report_stage542_oracle_candidate_sleeve_upper_bound_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage542_oracle_candidate_sleeve_upper_bound_summary_stage542_oracle_candidate_sleeve_upper_bound_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage542_oracle_candidate_sleeve_upper_bound_combined_daily_stage542_oracle_candidate_sleeve_upper_bound_v1.csv`
- satellite daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage542_oracle_candidate_sleeve_upper_bound_satellite_daily_stage542_oracle_candidate_sleeve_upper_bound_v1.csv`
- satellite standalone：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage542_oracle_candidate_sleeve_upper_bound_satellite_standalone_stage542_oracle_candidate_sleeve_upper_bound_v1.csv`
- product harvest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage542_oracle_candidate_sleeve_upper_bound_satellite_product_harvest_stage542_oracle_candidate_sleeve_upper_bound_v1.csv`
- rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage542_oracle_candidate_sleeve_upper_bound_rolling_holding_stage542_oracle_candidate_sleeve_upper_bound_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage542_oracle_candidate_sleeve_upper_bound_cost_stress_stage542_oracle_candidate_sleeve_upper_bound_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage542_oracle_candidate_sleeve_upper_bound_decision_stage542_oracle_candidate_sleeve_upper_bound_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage542_oracle_candidate_sleeve_upper_bound_chart_stage542_oracle_candidate_sleeve_upper_bound_v1.png`

## 结论

- 本阶段结论：`oracle_sleeve_upper_bound_positive_requires_ex_ante_selector`
- 是否进入下一步：进入下一步，但不能晋级为交易版本。
- 下一步：
  - 研究 `lu/v/al/y/c/ao` 的共同事前特征：低相关、低/中保证金、产业链不与核心黑色/化工过度同振、活跃度、近端趋势效率、基本面可解释性。
  - 做 purged walk-forward 或年份留一：用过去信息选产品，再在未来年份验证，而不是全样本选产品。
  - 结合基本面/舆情可执行性：这组产品分别对应低硫燃料油、PVC、铝、豆油、玉米、氧化铝，基本面数据可从交易所库存/仓单、产业供需、价差/利润、新闻时间戳监控中寻找事前证据，但必须先确认可回放和实盘可更新。

## 过拟合反思

- 运行前判断：有过拟合风险。Oracle6 来自 Stage241 全样本结果，天然有未来信息。
- 运行后判断：仍有过拟合风险，不能晋级。
- 原因：C2 的收益虽有材料性，但很大一部分来自 2026 的 `lu.INE`，而 2026 是样本末端；如果直接接入，就是典型按历史赢家选品。

## 继续价值反思

- 运行前判断：有价值。它是对“选对品种”方向的必要上限检验。
- 运行后判断：有价值。上限验证为正，说明方向不是死路。
- 原因：如果能用事前特征在历史上提前识别类似产品，非挤占式 sleeve 有机会在不破坏 Stage526 的前提下补收益和略降回撤。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；暂不追加 `memory.md`，因为没有形成可实盘规则。
