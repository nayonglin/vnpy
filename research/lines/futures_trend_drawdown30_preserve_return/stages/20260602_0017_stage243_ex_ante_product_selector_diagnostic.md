# Stage243 事前选品诊断

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-02 00:17 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读诊断；检验 Stage241/242 的 Oracle6 是否能被当时可见的特征事前选出。
- 是否重要突破：是，重要性在于反证。它阻止把 hindsight Oracle6 误升为实盘品种池。
- 是否触发A/B：否。本阶段没有形成可交易 C 版本，只做事前选择器诊断；若后续进入动态 universe sleeve，才需要 A/C 正式回测。

## 外部调研与判断

- 参考资料：
  - AQR《A Century of Evidence on Trend-Following Investing》：趋势跟随依赖跨市场分散，但分散收益来自长期、广泛且可交易的市场集合，不等于事后挑赢家。
  - AQR Time-Series Momentum 原始数据页：多市场时间序列动量研究强调跨资产/跨市场样本，而非单一历史赢家池。
  - GitHub `robcarver17/pysystemtrade` 等系统化期货框架：工程重点通常放在点时数据、风险预算、分散化和执行可复验，而不是用全样本收益静态选品。
- 我的判断：
  - Stage542 证明“选对品种 + 非挤占 sleeve”有上限空间，但不是 alpha 证明。
  - 本阶段必须先问：不看未来收益，能否在历史每个月/每季度把 `lu/v/al/y/c/ao` 或类似产品排到足够靠前。
  - 如果事前选择器只能略好于全非核心均值，且远低于 Oracle6 参考，就不能进入正式动态 sleeve 回测。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage543_ex_ante_product_selector_diagnostic.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数/诊断口径：
  - 评估产品：Stage541 的 `38` 个非核心产品。
  - Oracle 标签：Stage241 全样本材料性候选 `al.SHFE/ao.SHFE/c.DCE/lu.INE/v.DCE/y.DCE`，只用于召回诊断，不进入打分。
  - 选择器：已有 AI 概率、已有 simple 趋势分、市场地形等权、策略历史记忆等权、混合等权。
  - TopK：`3`、`6`。
  - 评估窗口：月度样本与季度去重样本；未来 `60/120` 个交易日单品种真实成交 PnL。
  - 通过定义：季度去重 Top6 未来60日相对全非核心均值 `>=500元/产品`，捕获 Oracle6 未来60日均值 `>=50%`，未来60日正月份率 `>55%`，平均召回 Oracle6 产品数 `>=2`。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage541 单品种账本 `2020-01-02` 至 `2026-04-30`；walk-forward 预测样本 `2022-01-28` 至 `2026-02-27`。
- 成本口径：继承 Stage541 单品种真实下一窗口成交、正常滑点。
- 账户口径：本阶段不生成新账户权益曲线；只读取每个产品 `115000` sleeve 单品种 PnL 作为未来诊断标签。
- 对照：
  - Stage526 control：`23,369,505/3699.9195%/-36.2670%/Sharpe1.6385`。
  - Stage542 Oracle6 C2 上限：`23,488,930/3719.3382%/-36.1186%/Sharpe1.6485`，但含未来信息。

## 结果

- 决策：`ex_ante_selector_not_ready_keep_oracle_as_upper_bound`
- 通过项：`0`
- 最好季度去重 Top6：`strategy_memory_equal`
  - 平均未来60日 PnL：`91.4216`
  - 全非核心均值：`11.4087`
  - 相对全非核心 edge：`80.0129`
  - Oracle6 参考均值：`832.4020`
  - 捕获 Oracle6 比例：`10.9829%`
  - 未来60日正月份率：`41.1765%`
  - 平均 Oracle6 召回数：`2.3529`
  - 未来120日均值：`-104.5588`
- 最好月度 Top6：`strategy_memory_equal`
  - 平均未来60日 PnL：`245.3667`
  - 相对全非核心 edge：`206.9167`
  - Oracle6 参考均值：`981.9333`
  - 捕获 Oracle6 比例：`24.9881%`
  - 未来60日正月份率：`50.0000%`
  - 未来120日均值：`-34.4667`

### Top6 关键表

| 选择器 | 样本 | 未来60均值 | 相对全非核心edge | Oracle6参考 | 捕获比例 | 60日正月份率 | Oracle6召回 | 通过 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 策略历史记忆等权 | quarterly_purged | 91.4216 | 80.0129 | 832.4020 | 10.9829% | 41.1765% | 2.3529 | 0 |
| simple趋势分 | quarterly_purged | 1.5686 | -9.8400 | 832.4020 | 0.1884% | 47.0588% | 1.5294 | 0 |
| 混合等权 | quarterly_purged | -174.4608 | -185.8695 | 832.4020 | -20.9587% | 41.1765% | 1.9412 | 0 |
| 市场地形等权 | quarterly_purged | -346.5196 | -357.9283 | 832.4020 | -41.6289% | 17.6471% | 0.7647 | 0 |
| AI概率 | quarterly_purged | -198.0392 | -209.4479 | 832.4020 | -23.7913% | 11.7647% | 0.7059 | 0 |

## 图表视觉复盘

- 左上 edge 图：所有季度去重 Top6 的未来60日 edge 都远低于红色 `500元/产品` 门槛；`strategy_memory_equal` 虽为正，但只是微弱正 edge，不足以解释 Oracle6 上限。
- 右上召回图：`strategy_memory_equal` 能平均召回 `2.35` 个 Oracle6 产品，超过召回门槛，但收益仍弱，说明“叫对名字”不等于“在正确时间拿到收益”。
- 左下季度累计图：Oracle6 reference 红线持续拉开，所有事前选择器都贴近零或转负，`market_terrain_equal` 后段明显下沉。这个视觉差距比单个均值更关键：现有特征没有复刻 hindsight 上限的路径。
- 右下热力图：Oracle6 的混合排名不是持续全绿。`v` 和 `lu` 某些阶段可选，但 `al` 多数阶段偏弱，`ao/c/y` 有明显周期性退潮；这解释了为什么静态 Oracle6 强，但动态事前选择器收益不稳定。

## 输出文件

- scored samples：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage543_ex_ante_product_selector_diagnostic_scored_samples_stage543_ex_ante_product_selector_diagnostic_v1.csv`
- selections：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage543_ex_ante_product_selector_diagnostic_selections_stage543_ex_ante_product_selector_diagnostic_v1.csv`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage543_ex_ante_product_selector_diagnostic_summary_stage543_ex_ante_product_selector_diagnostic_v1.csv`
- oracle selectability：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage543_ex_ante_product_selector_diagnostic_oracle_selectability_stage543_ex_ante_product_selector_diagnostic_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage543_ex_ante_product_selector_diagnostic_decision_stage543_ex_ante_product_selector_diagnostic_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage543_ex_ante_product_selector_diagnostic_report_stage543_ex_ante_product_selector_diagnostic_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage543_ex_ante_product_selector_diagnostic_chart_stage543_ex_ante_product_selector_diagnostic_v1.png`

## 结论

- 不能把 Oracle6 直接晋级，也不值得立刻跑动态 sleeve 正式组合回测。
- 当前可见的价格/成交/历史策略账本/已有 AI 适应度特征，只能弱召回一部分 Oracle6 名字，不能稳定捕获其未来收益时段。
- 扩池方向仍有价值，但下一步必须换更强的点时化解释变量：产品族风险预算、产业链基本面可得性、仓单/库存/基差覆盖、交易所成交结构，以及低相关状态下的趋势地形；否则继续在现有分数上调权重就是过拟合。

## 过拟合反思

- 运行前判断：否。本阶段不调交易规则、不按结果实盘，只检验事前可选性。
- 运行后判断：本阶段本身不是过拟合；它反而揭示 Oracle6 若直接实盘就是过拟合。
- 原因：Oracle6 来自全样本单品种收益；当前事前选择器没有足够证据复刻这个上限。

## 继续价值反思

- 运行前判断：有价值。Stage542 上限为正，必须继续验证是否能事前化。
- 运行后判断：仍有价值，但方向应收窄。
- 原因：单纯价格/账本特征不够，下一步若继续选品，应引入可实盘更新、可点时回放的外生/产品族结构特征；不应在现有五个分数上扫权重。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；暂不追加 `memory.md`，因为不是正式候选或路线废弃，只是关键反证。
