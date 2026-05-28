# Stage122：Stage103 长周期 value proxy overlay 审计

- 时间：2026-05-28 00:20 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 阶段性质：文献驱动的低自由度固定结构审计；不修改 Stage079、Stage103、C3 或 78-1 核心交易规则。
- 是否重要突破：是，研究级突破；但不是执行级晋级。
- 决策：`research_candidate_only`
- 主结论：`stage103_plus_value_proxy756_monthly_guard` 可以作为 Stage103 后继研究候选继续审计；当前不能替代 Stage103 执行候选。

## 调研与判断

- 外部调研参考 FuturesBacktest 对期货策略族的定义：trend、value、carry 是不同的期货收益信号族；value 更接近长期反趋势/便宜贵的横截面信号，通常需要 `5年+` 的时间尺度验证。
- FuturesBacktest 的 weighting 文档也明确提示，同一资产类别内保持相同权重有助于降低过拟合风险；本阶段因此只用固定 top/bottom、月频、1手和统一保证金闸门，不做品种或坏窗口补丁。
- GitHub/公开代码调研判断：通用 managed futures / trend following 代码可参考，但没有能直接迁移到本地中国商品期货池、整数手、保证金、Stage079 资金口径的现成 value proxy 实现。
- 我的判断：长期 value/contrarian 是值得尝试的不同风险源，但本地连续数据从 2020 开始，`756` 日也只是短样本代理；因此即使结果好，也只能先晋级为研究候选，不应直接部署。

参考：

- FuturesBacktest strategies: https://www.futuresbacktest.com/docs/strategies/
- FuturesBacktest weighting: https://www.futuresbacktest.com/docs/weighting/

## A/B/C 设计

- A：Stage079，`50万C3下单 + 11.5万外部现金`。
- C0：Stage103，`xsmom_vt10_q_momq_round_half_true_broker10_guard`。
- C1：Stage103 + `504` 日 long value proxy。
- C2：Stage103 + `756` 日 long value proxy。

固定候选假设：

- 如果一个品种长期明显跑输，可能更接近“便宜/反转”端；长期明显跑赢则可能更接近“昂贵/拥挤”端。
- 用 `-过去N日收益` 做 value proxy，买长期输家、空长期赢家，和 Stage103 的趋势/xsmom 暴露不同源，理论上可能改善趋势暴涨后反转和长水下路径。

## 新增、修改、删除

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage422_stage103_long_value_proxy_overlay.py`
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage422_stage103_long_value_proxy_overlay_report_stage422_stage103_long_value_proxy_overlay_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage422_stage103_long_value_proxy_overlay_chart_stage422_stage103_long_value_proxy_overlay_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage422_stage103_long_value_proxy_overlay_decision_stage422_stage103_long_value_proxy_overlay_v1.json`
- 新增参数：
  - value lookback：`504`、`756` 个交易日。
  - 方向：`reversal`，买长期输家、空长期赢家。
  - 篮子：top/bottom 各 `3` 个品种。
  - 调仓：每 `20` 个交易日。
  - 手数：每腿 `1` 手。
  - 保证金闸门：沿用 Stage103 的 `1.10` broker multiplier。
- 修改参数：无。
- 删除参数：无。
- 没有修改正式策略入口、Stage079、Stage103 或 C3 逻辑。

## 核心结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 总滑点 | 总交易次数 | 非零日胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 | 31,040,650 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 1,556,750 | 757 | 48.3478% |
| Stage103 | 31,730,915 | 5059.4984% | -28.9792% | 1.3681 | 14.3132 | 1,569,265 | 1,217 | 50.3432% |
| Stage103+value504 | 32,514,510 | 5186.9122% | -28.9792% | 1.3784 | 13.9997 | 1,580,795 | 1,535 | 52.1269% |
| Stage103+value756 | 32,493,795 | 5183.5439% | -28.9792% | 1.3808 | 14.1660 | 1,578,855 | 1,461 | 51.8802% |

## 3个月与6个月持有体验

| 版本 | 90日分 | 180日分 | 综合短持有分 | 90日收益5%分位 | 180日收益5%分位 | 90日正收益率 | 180日正收益率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 | 100.0000 | 100.0000 | 100.0000 | -11.4702% | -2.0393% | 73.4804% | 93.4772% |
| Stage103 | 121.2041 | 134.4513 | 128.4901 | -10.9102% | -0.6313% | 74.6961% | 94.3688% |
| Stage103+value504 | 130.2819 | 146.5086 | 139.2066 | -10.5394% | -0.3272% | 76.1369% | 94.7443% |
| Stage103+value756 | 130.2395 | 143.3501 | 137.4504 | -10.5242% | -0.3415% | 75.8217% | 94.5565% |

## 闸门与反证

- `stage103_plus_value_proxy504_monthly_guard`：
  - 3/6个月体验最好，综合短持有分 `139.2066`。
  - 但冷启动失败：`phase_2024_2025`、`start_2022`、`start_2024` 最大回撤打穿30%，其中 `start_2022` 最大回撤 `-44.3797%`。
  - 决策：淘汰，不晋级。
- `stage103_plus_value_proxy756_monthly_guard`：
  - 通过 Stage079 硬闸门、3/6个月体验目标、相对 Stage103 增量闸门和成本压力闸门。
  - 冷启动窗口回撤全部通过30%：例如 `start_2022` 为 `754.7821%/-28.5161%`，`start_2024` 为 `308.1480%/-28.8298%`。
  - 相对 Stage103 的任意启动收益胜率明显强于之前多条路线：90/180/252/504日为 `79.3787%/84.2328%/82.7586%/96.6796%`。
  - 顶部贡献日剔除后仍有边际：剔除最大 `20` 个相对贡献日后，相对 Stage103 仍高 `35.3740pp`。
  - 失败点：`start_2020` 的 `1.10x` broker 保证金口径相对 Stage103 更差，Stage103 为 `1` 天拒单，value756 为 `2` 天拒单；最大保证金/权益 `101.6592%`，需要额外约 `78,920.08` 元才能完全消除拒单。
  - 决策：研究候选，不执行晋级。

## 成本压力

- Stage103+value756 在 `1x/2x/3x/5x` 滑点下最大回撤为 `-28.9792%/-30.4073%/-31.9135%/-39.1469%`。
- 该成本压力路径不差于 Stage079，也不差于 Stage103。
- 但它仍不能在 `2x+` 绝对口径下守住30%，这和 Stage079/Stage103 的边界一致，不能包装成高滑点稳健版本。

## 过拟合反思

- 运行前判断：不是过拟合。理由是本阶段不是坏窗口补丁，而是基于外部可解释的 trend/value/carry 框架，预先固定 lookback、月频、top/bottom 各3、1手和保证金闸门。
- 运行后判断：暂不判定为过拟合，但不能执行晋级。理由是 value756 的 rolling 胜率、成本压力、顶部贡献日剔除都支持它有真实研究价值；但本地历史太短，且 756 日 value 信号只在样本后半段真正活跃，存在样本覆盖不足风险。
- 明确禁止：不继续扫 `504/756/1008`、top_n、调仓频率、品种过滤、日期过滤或保证金小数来救结果。

## 继续价值反思

- 运行前判断：有价值。Stage121 后需要新的低参数、低相关、可解释风险源，而长期 value/contrarian 正是与趋势不同源的候选。
- 运行后判断：有价值，但只值得做固定 value756 的严格验证，不值得扩参搜索。原因是 value756 是 Stage103 后少数同时提高收益、Sharpe、Ulcer、3/6个月体验，并且 rolling 相对 Stage103 胜率很高的新增结构。

## 后续规划

- Stage123 应固定 `stage103_plus_value_proxy756_monthly_guard`，做严格 OOS/样本覆盖与脆弱性审计：
  - 按 value 信号首次有效日切分前后样本，不允许把未激活期的 Stage103 表现当成 value 贡献。
  - 统计 value overlay 各年份活跃天数、品种覆盖、交易贡献和保证金占用。
  - 做剔除 2024、剔除 2025、剔除 2024-2025 的边际贡献审计。
  - 复核 `start_2020` broker10 多出拒单的真实现金需求和是否可通过不新增交易规则的执行现金安排解决。
  - 做 value overlay 独立腿与 Stage103 的相关性、坏窗口贡献和 OOS 稳定性审计。
- 在 Stage123 之前，当前主执行相对候选仍是 Stage103；value756 只作为研究级候选。

## 输出文件

- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage422_stage103_long_value_proxy_overlay.py`
- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage422_stage103_long_value_proxy_overlay_report_stage422_stage103_long_value_proxy_overlay_v1.md`
- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage422_stage103_long_value_proxy_overlay_chart_stage422_stage103_long_value_proxy_overlay_v1.png`
- 决策：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage422_stage103_long_value_proxy_overlay_decision_stage422_stage103_long_value_proxy_overlay_v1.json`
