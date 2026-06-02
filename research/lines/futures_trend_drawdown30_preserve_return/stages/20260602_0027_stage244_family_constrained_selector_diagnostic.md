# Stage244 产品族约束事前选品诊断

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-02 00:27 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读诊断；检验产品族分散、低核心相关预算能否改善 Stage243 事前选品失败。
- 是否重要突破：否，但有结构性收获。产品族约束有改善，但不足以进入动态 sleeve 回测。
- 是否触发A/B：否。本阶段没有生成交易版本，只做事前选择器诊断；若后续形成动态品种池并接入 Stage526，才需要 A/C。

## 外部调研与判断

- 参考资料：
  - managed futures / trend following portfolio construction 资料普遍强调跨市场、跨部门分散，同时控制相关性和风险预算。
  - `pysystemtrade` 等系统化期货框架将 instrument diversification、相关性和风险预算作为组合层核心，而不是简单历史赢家排序。
  - 商品期货品种有明显产业链/产品族共振，黑色、有色、油化工、农产品内部相关性通常高于跨族相关性。
- 我的判断：
  - 用户“扩大品种池但避免高相关风险”的方向是对的，但必须变成事前约束：同产品族上限、低核心相关、保证金可承受。
  - 这类约束能减少风险堆叠，但不等于能选到收益源；因此本阶段只做 selector 诊断，不接入交易。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage544_family_constrained_selector_diagnostic.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增静态产品族映射：`grains_oilseeds`、`energy_oil`、`petrochem`、`base_metals`、`black_ferrous`、`soft_agri`、`rubber`、`livestock`、`precious_metals`、`financial_index`、`other`。
- 新增选择模式：
  - `memory_unconstrained`：Stage543 最好季度口径对照。
  - `memory_family_cap2`：同产品族最多2个。
  - `memory_family_cap1`：同产品族最多1个。
  - `memory_family_cap2_lowcorr030`：同产品族最多2个，并优先要求与 Stage526 核心 `252日相关 <=0.30`。
  - `simple_family_cap1_lowcorr030`：simple 趋势分 + 同产品族最多1个 + 低核心相关。
  - `hybrid_family_cap1_lowcorr030`：混合分 + 同产品族最多1个 + 低核心相关。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 输入：Stage543 scored samples。
- 评估产品：Stage541 的 `38` 个非核心产品。
- 评估窗口：月度样本与季度去重样本。
- 未来标签：每个产品未来 `60/120` 交易日 Stage541 单品种真实成交 PnL。
- 通过定义：季度去重 Top6 未来60日相对全非核心均值 `>=500元/产品`，捕获 Oracle6 未来60日参考 `>=50%`，60日正月份率 `>=55%`，平均召回 Oracle6 `>=2`。

## 结果

- 决策：`family_constrained_selector_improves_but_not_ready`
- 通过项：`0`
- 最好季度去重模式：`simple_family_cap1_lowcorr030`
  - 未来60日均值：`196.1765`
  - 全非核心未来60日均值：`11.4087`
  - 相对全非核心 edge：`184.7678`
  - Oracle6 未来60日参考：`832.4020`
  - Oracle6 捕获比例：`23.5675%`
  - 60日正月份率：`47.0588%`
  - 120日均值：`115.8824`
  - 平均 Oracle6 召回数：`1.2353`
  - 平均产品族数：`6.0000`
  - 平均同族最大数量：`1.0000`
  - 平均核心相关绝对值：`0.0193`
- 相对 Stage543 最好季度模式 `strategy_memory_equal`：
  - edge 改善：`+104.7549`
  - 60日正月份率改善：`+5.8824pp`
  - Oracle6 捕获比例改善：`+12.5847pp`

### 季度去重摘要

| 模式 | 未来60均值 | edge | Oracle捕获 | 60日正月份率 | Oracle召回 | 家族数 | 平均核心相关 | 通过 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| simple族1+低核心相关 | 196.1765 | 184.7678 | 23.5675% | 47.0588% | 1.2353 | 6.0000 | 0.0193 | 0 |
| 历史记忆族上限2 | 106.4216 | 95.0129 | 12.7849% | 41.1765% | 2.4706 | 4.5294 | 0.0502 | 0 |
| 历史记忆族2+低核心相关 | 105.1961 | 93.7874 | 12.6377% | 35.2941% | 2.4706 | 4.3529 | 0.0383 | 0 |
| 历史记忆无族约束 | 91.4216 | 80.0129 | 10.9829% | 41.1765% | 2.3529 | 4.1176 | 0.0494 | 0 |
| 混合族1+低核心相关 | -153.7255 | -165.1342 | -18.4677% | 47.0588% | 1.6471 | 6.0000 | 0.0233 | 0 |
| 历史记忆族上限1 | -180.3431 | -191.7518 | -21.6654% | 47.0588% | 2.7647 | 6.0000 | 0.0451 | 0 |

## 图表视觉复盘

- 左上 edge 图：`simple族1+低核心相关` 是最佳结构，蓝条约 `185`，明显好于 Stage543 对照的 `80`，但距离红色 `500` 晋级线仍很远。
- 右上质量图：best 模式的 60日正月份率约 `47%`，低于黑色 `55%` 线；Oracle 捕获约 `24%`，远低于红色 `50%` 线。说明它改善了平均 edge，但不是稳定收益源。
- 左下季度累计图：best 模式蓝线长期高于全非核心均值，也高于多数 family 模式，但 2024 年附近有明显回撤，最终仍只捕获 Oracle6 红线的一小段。
- 右下产品族频率：best 模式实现了每族最多1个，但高频选中的 `grains_oilseeds` 平均贡献偏负；`base_metals/petrochem/soft_agri` 贡献较好。这说明“产品族分散”只是第一层，后续还要有产品族状态/基本面强弱判断。

## 输出文件

- family map：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage544_family_constrained_selector_diagnostic_family_map_stage544_family_constrained_selector_diagnostic_v1.csv`
- selections：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage544_family_constrained_selector_diagnostic_selections_stage544_family_constrained_selector_diagnostic_v1.csv`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage544_family_constrained_selector_diagnostic_summary_stage544_family_constrained_selector_diagnostic_v1.csv`
- family summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage544_family_constrained_selector_diagnostic_family_summary_stage544_family_constrained_selector_diagnostic_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage544_family_constrained_selector_diagnostic_decision_stage544_family_constrained_selector_diagnostic_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage544_family_constrained_selector_diagnostic_report_stage544_family_constrained_selector_diagnostic_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage544_family_constrained_selector_diagnostic_chart_stage544_family_constrained_selector_diagnostic_v1.png`

## 结论

- 产品族约束/低核心相关预算是有用的风险设计原则，但还不是可交易选品器。
- 直接基于 Stage543 的价格/账本分数加产品族约束，仍不能稳定选出每年趋势收益。
- 下一步若继续选品，应把产品族约束固定为风控壳，再寻找点时化的产品族状态变量，例如基差/仓单覆盖、库存变化、成交/OI结构、产业链价差、新闻事件的真实接收时间戳。
- 不建议在 family cap `1/2`、相关阈值 `0.25/0.35` 或 simple/hybrid 小权重上继续扫参。

## 过拟合反思

- 运行前判断：否。产品族映射是静态经济分类，不使用未来收益。
- 运行后判断：本阶段不是过拟合，但若继续围绕当前六个模式的小阈值调参，就会变成过拟合。
- 原因：季度去重样本并未通过硬门槛，说明现有结构只是弱改善，不足以晋级。

## 继续价值反思

- 运行前判断：有价值。它直接回应“扩大品种池但避免高相关风险”的核心问题。
- 运行后判断：有价值但方向收窄。产品族约束应保留为风险预算原则，不能单独作为 alpha。
- 下一步价值在于：为每个产品族增加实盘可更新的基本面/交易结构状态，而不是继续调产品族 cap 小数。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；暂不追加 `memory.md`，因为不是正式候选或路线废弃。
