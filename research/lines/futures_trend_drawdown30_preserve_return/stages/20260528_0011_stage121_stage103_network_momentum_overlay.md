# Stage121 Stage103 Network Momentum Overlay审计

- 时间：2026-05-28 00:11 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 阶段性质：低自由度新增风险源审计；不修改 Stage079、Stage103、C3 的交易规则，不增加账户资金，不使用坏窗口日期或品种黑名单。
- 是否重要突破版本：否。结论是 network momentum 有文献依据，但本地真实整数手 overlay 无法在不劣化 Stage079/Stage103 的前提下改善3个月和6个月启动体验。
- 是否触发 A/B：是，已按 `skills/version-ab-experiment/SKILL.md` 执行。A=`Stage079`；C0=`Stage103`；C1/C2=`Stage103 + network momentum overlay`。
- 本次脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage421_stage103_network_momentum_overlay.py`
- 输出报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage421_stage103_network_momentum_overlay_report_stage421_stage103_network_momentum_overlay_v1.md`
- 输出图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage421_stage103_network_momentum_overlay_chart_stage421_stage103_network_momentum_overlay_v1.png`
- 决策 JSON：`no_new_promotion`

## 运行前反思

- 是否在过拟合：否。候选来自 commodity futures network momentum / lead-lag 文献，不是按本线弱窗口补丁；参数为粗粒度固定结构。
- 是否仍有价值继续做：是。Stage120 已证明“少承担早期风险”不能满足收益体验目标；下一步必须尝试真实低相关或领先信息收益源，network momentum 正好测试跨品种领先趋势是否能补短持有左尾。

## 外部调研与判断

- arXiv 论文 `Follow the Leader: Enhancing Systematic Trend-Following Using Network Momentum` 提出在商品期货趋势跟随中叠加 cross-sectional / lead-lag 的 network momentum，用于捕捉 momentum spillover，并报告 Sharpe、偏度和下行表现改善：https://arxiv.org/abs/2501.07135
- 经典 managed futures / time-series momentum 研究说明趋势跟随可以解释 CTA/managed futures 的主要收益来源，且跨市场分散、成本和波动管理很关键：https://docs.lhpedersen.com/DemystifyingManagedFutures.pdf
- GitHub 调研看到 `alipbcs/TSMOM`、`jironghuang/trend_following`、`PyTrendFollow` 等期货/趋势跟随 Python 实现，但没有可直接迁移到本地中国商品池、保证金、整数手和 Stage079 资金口径的 network momentum 版本；因此本阶段只借鉴思想，自行实现点时化网络分数。
- 我的判断：network momentum 是值得反证的一条结构性路线，但若真实一手 overlay 在冷启动和成本压力上失败，就不应继续调相关窗口、top_n 或再平衡频率救结果。

## 候选定义

- A：`stage079`，50万C3下单 + 11.5万外部现金。
- C0：`xsmom_vt10_q_momq_round_half_true_broker10_guard`，即当前主执行相对候选 Stage103。
- C1：`stage103_plus_network_mom20_corr252_weekly_guard`
  - 用过去 `252` 日商品间正相关网络加权过去 `20` 日领先品种动量。
  - 每 `5` 个交易日再平衡。
  - 强者多、弱者空，各 `3` 个品种，每品种 `1` 手。
  - 沿用 `1.10x` 保证金闸门。
- C2：`stage103_plus_network_mom60_corr252_monthly_guard`
  - 用过去 `252` 日商品间正相关网络加权过去 `60` 日领先品种动量。
  - 每 `20` 个交易日再平衡。
  - 强者多、弱者空，各 `3` 个品种，每品种 `1` 手。
  - 沿用 `1.10x` 保证金闸门。

## 版本变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage421_stage103_network_momentum_overlay.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - `CORR_LOOKBACK=252`
  - `signal_lookback=20/60`
  - `rebalance_every=5/20`
  - `top_n=3`
  - `BROKER10_MULTIPLIER=1.10`，沿用 Stage103 逻辑。
- 修改参数：无正式策略参数修改。
- 删除参数：无。
- 新增回测结果：全周期核心指标、3/6个月体验、体验分、成本压力、年度/季度/多起点冷启动、保证金压力、任意启动相对 Stage103、顶部贡献日剔除、Stage104坏窗口贡献。
- 修改回测结果：无。
- 删除回测结果：无。

## 核心结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 252/504滚动破30 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 | 31,040,650 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 0% / 0% |
| Stage103 | 31,730,915 | 5059.4984% | -28.9792% | 1.3681 | 14.3132 | 0% / 0% |
| network20 | 31,812,725 | 5072.8008% | -30.0668% | 1.3634 | 14.2303 | 9.7561% / 25.0574% |
| network60 | 31,711,500 | 5056.3415% | -27.6431% | 1.3693 | 14.2545 | 0% / 0% |

注：network20 虽总收益高于 Stage103，但最大回撤打穿30，且 rolling252/504破30不再为0，直接淘汰。

## 3个月/6个月启动体验

| 版本 | 3个月分 | 6个月分 | 3个月p05 | 3个月中位 | 3个月正收益率 | 3个月DD20 | 6个月p05 | 6个月中位 | 6个月正收益率 | 6个月DD20 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 | 100.0000 | 100.0000 | -11.4702% | 13.5434% | 73.4804% | 18.5052% | -2.0393% | 33.9947% | 93.4772% | 35.7109% |
| Stage103 | 121.2041 | 134.4513 | -10.9102% | 13.4787% | 74.6961% | 16.6141% | -0.6313% | 35.8014% | 94.3688% | 35.7109% |
| network20 | 114.2408 | 91.5285 | -10.9334% | 13.2821% | 75.1013% | 19.8109% | -2.3263% | 36.5475% | 93.1957% | 39.1366% |
| network60 | 117.8177 | 111.9668 | -11.6389% | 13.4361% | 75.3264% | 16.6592% | -1.7035% | 32.9678% | 93.7588% | 37.6818% |

- network20：3个月正收益率提高，但6个月分跌到 `91.5285`，且6个月p05、DD20均劣化。
- network60：3/6个月分都超过110，但6个月改善项只有 `3/8`，6个月中位收益低于 Stage079 与 Stage103。
- 两者都不能满足“3个月和6个月各至少5/8项改善”的晋级标准。

## 冷启动与成本压力

- network20 冷启动失败窗口：`phase_2024_2025,start_2020,start_2021,start_2022,start_2024,weak_2021_full`。
- network60 冷启动失败窗口：`phase_2024_2025,start_2022,start_2024`。
- network20 `1x/2x/3x/5x` 成本压力最大回撤：`-30.0668%/-31.6527%/-33.3315%/-40.3107%`，均不如 Stage103，且多项不如 Stage079。
- network60 `1x/2x/3x/5x` 成本压力最大回撤：`-27.6431%/-29.1586%/-30.7886%/-39.3554%`，1x到3x不差于 Stage079/Stage103，但5x略差于 Stage103；同时总收益低于 Stage103。
- `start_2022` 是关键反证：network20 回撤 `-33.0961%`，network60 回撤 `-41.4842%`，均明显失败。

## 任意启动与反过拟合校验

- network20 相对 Stage103 的任意启动收益胜率：90/180/252/504日为 `57.3615%/52.9798%/45.9446%/47.0393%`，但最大回撤不劣化率只有 `47.0509%/33.6931%/27.6348%/23.8517%`。
- network60 相对 Stage103 的任意启动收益胜率：90/180/252/504日为 `52.2287%/51.1497%/51.5784%/45.7111%`，但504日收益胜率低于50%，且6个月中位收益劣化。
- 顶部贡献日剔除显示：
  - network20 相对 Stage103 的收益优势剔除前仅 `+13.3024pp`，剔除最大3个贡献日后转为 `-1.7268pp`。
  - network60 相对 Stage103 剔除前已经为 `-3.1569pp`。
- Stage104坏窗口贡献没有形成稳定保护：network20 90日略正但180日负；network60 90日负、180日略正，均不具备晋级意义。

## 决策

- 决策：`no_new_promotion`。
- 当前主执行相对候选仍是 Stage103。
- network momentum 子路线不继续扫：
  - 不扫 `20/40/60/120` 相邻动量窗口。
  - 不扫 `126/252/504` 相关窗口。
  - 不扫 `top_n=1/2/3/4`。
  - 不扫周频/月频/双周频。
  - 不做按 `start_2022` 或 `2024` 失败窗口的日期/品种补丁。
- 经验保留：跨品种 lead-lag 理念本身有研究价值，但在当前 19品种中国商品池、1手整数、Stage103已有xsmom、61.5万账户资金和保证金约束下，新增 overlay 更容易变成过暴露，而不是改善“任何时候启动”的真实体验。

## 后续规划

1. 不继续救 network momentum 小参数。
2. 若继续寻找新增收益源，优先考虑更不同风险暴露、天然低保证金/低相关且能在 `start_2022`、`phase_2024_2025` 不放大回撤的结构。
3. Stage103 继续作为当前主执行相对候选；任何新方向必须至少不弱于 Stage079，最好同时不弱于 Stage103。

## 运行后反思

- 是否在过拟合：否。本阶段主动拒绝了全周期局部好看的 network20 和回撤好看的 network60，没有用失败窗口补丁或相邻参数救援。
- 是否还有价值继续做：network momentum 子路线主动优化价值低；总目标仍有价值，但下一步需要换风险源，而不是继续在同一商品动量网络内部加杠杆/加换手。

## 合入建议

- 更新本线 `LINE.md`：是，追加 Stage121 约束。
- 更新 `research/registry.md`：是，最新关键阶段改为 Stage121。
- 追加根目录 `memory.md/back_log.md`：是。本阶段停止 network momentum overlay 子路线。
