# Stage199 全商品统一双向震荡 v10

- line_id：`futures_range`
- 当前模式：`day`
- 记录时间：`2026-09-01 20:27 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe` / `098ca5b99`
- 阶段性质：震荡策略独立 A/B 扩容验证
- 是否重要突破：否；实现了全商品池入口，但策略效果不通过
- 是否触发A/B：是；A 为冻结 Core4 v8，B 为全商品 v10

## 外部调研与判断

- 参考资料：
  - Miffre 与 Rallis（2007），Commodity Futures Momentum：<https://doi.org/10.1016/j.jbankfin.2006.12.005>
  - Moskowitz、Ooi 与 Pedersen（2012），Time Series Momentum：<https://doi.org/10.1016/j.jfineco.2011.11.003>
  - Han（2023），Commodity Momentum and Reversal：<https://doi.org/10.1002/fut.22424>
  - 中国商品期货日内信息与反转研究（2023）：<https://doi.org/10.1016/j.jempfin.2023.03.001>
- 我的判断：商品期货的反转不是跨品种无条件普适规律，动量通常更稳定；反转收益依赖市场状态、时间尺度与品种结构。因此“所有商品统一参数、统一双向均值回归”属于高风险假设，只能以固定规则一次性证伪，失败后不得按品种、方向、年份或阈值救参。

## 预声明合同

- A：`range_reversion_core4_directed_product_signal_back_adjusted_v8_two_stage_stop`。
- B：来自 `full_market_tradable_universe_v1` 的全部 `eligible=1` 商品品种，排除 `exchange=CFFEX`，所有品种统一允许 long+short。
- “全市场”定义为已有可交易性审计通过的商品池，不包含数据/流动性不合格的休眠或不可用合约。
- A/B 共用资金 `200,000`、`risk_ratio=0.008`、最多 `4` 个并发仓位，以及 v8 的 score、ADX、效率率、通道、持有期和两段式止损参数。
- B 首轮若不能同时保留正收益、可接受回撤和风险调整后表现，则停止；不做成本、顺序敏感性或参数救援。
- 趋势策略和 Stage78 不参与、不修改、不组合。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/run_qmt_range_reversion_full_commodity_v10_backtest.py`
- 新增品种池：`examples/portfolio_backtesting/qmt_range_reversion_full_commodity_universe_v10.csv`
- 新增测试：`tests/test_futures_range_full_commodity_v10.py`（含被忽略审计源缺失时读取冻结池的干净 checkout 回退）
- 修改脚本：无
- 删除脚本：无
- 新增参数：无；新增的是独立品种池入口和过滤规则
- 修改参数：B 将方向约束改为全品种 `both`；其余继承 v8
- 删除参数：B 不读取 Core4 `range_direction_hints_path`

## 回测/归因参数

- 数据区间：统一仓库边界 `2020-01-01 -> 2026-04-30`；A 首个可交易日 `2020-02-05`，B 首个统计日 `2020-01-02`
- 账户规模：`200,000`
- 成本口径：合约元数据滑点；佣金 `0`
- 样本过滤：源池 `eligible=1` 且 `exchange != CFFEX`
- B 品种数：`56`；交易所分布 `CZCE 17 / DCE 16 / GFEX 2 / INE 4 / SHFE 17`
- B 历史合约预检：`3,073` 个合约，size 与 margin 元数据均 `3,073/3,073`
- 策略口径：日线信号、产品连续序列 additive back-adjust、同日收盘撮合、v8 两段式止损
- 限制：同日收盘撮合是研究引擎既有的执行乐观偏差，本结果不能称实盘可执行收益。
- 限制：56品种资格使用样本末端可交易性审计，不是逐日 point-in-time universe，存在存续/后视筛选偏差；该偏差阻止把B视为无偏收益估计，但B在此口径下仍全面落后A，因此不影响拒绝结论。

## 结果

| 指标 | A：Core4 v8 fresh | B：全商品 v10 | B-A |
|---|---:|---:|---:|
| 期末权益 | `210,820` | `204,120` | `-6,700` |
| 总收益 | `5.410%` | `2.060%` | `-3.350pp` |
| 最大回撤 | `-1.981%` | `-15.585%` | `-13.603pp` |
| Sharpe | `0.5642` | `0.0536` | `-0.5106` |
| 总滑点 | `2,040` | `26,570` | `+24,530` |
| 总交易次数 | `80` | `1,259` | `+1,179` |
| 完整回合 | `40` | `634` | `+594` |
| 胜率 | `52.50%` | `47.63%` | `-4.87pp` |

- B 年度净PnL：2020 `-3,510`、2021 `-17,430`、2022 `-3,075`、2023 `+20,240`、2024 `+1,765`、2025 `+7,035`、2026截至4月 `-905`；`4/7` 年为负，结果依赖 2023 单年。
- B 分品种守恒：56 个品种中正收益 `25`、负收益 `20`、零收益 `11`，净PnL合计 `4,120`，滑点合计 `26,570`，成交合计 `1,259`。
- B 内 Core4 四品种合计净PnL `+13,260`、滑点 `2,640`、成交 `120`；新增52品种合计净PnL `-9,140`、滑点 `23,930`、成交 `1,139`。该分桶包含 B 的统一双向与组合竞争效应，不是纯边际反事实，但足以证明扩容集合没有贡献正收益。
- B 最差品种：`fb.DCE -11,055`、`AP.CZCE -8,460`、`MA.CZCE -6,440`、`SA.CZCE -5,320`、`al.SHFE -4,375`。
- B 候选快照：开仓 `596`、跳过 `1,196`；其中 `sizing_zero_volume=1,097`、`concurrent_limit=99`。开仓方向 long `309`、short `287`。
- 共同统计区间敏感性（只重算B日度统计，不改变交易路径）：`2020-02-05 -> 2026-04-30`，B为期末`206,220`、收益`3.110%`、最大回撤`-15.424%`、Sharpe`0.08198`、滑点`26,330`、交易`1,257`；仍全面弱于同区间A。该结果用于回答引擎原生日表起点差异，不冒充独立冷启动回测。

## 输出文件

- A statistics：`examples/portfolio_backtesting/backtest_outputs/qmt_range_reversion_core4_directed_product_signal_back_adjusted_v8_two_stage_stop_statistics.json`
- B statistics：`examples/portfolio_backtesting/backtest_outputs/qmt_range_reversion_full_commodity_v10_statistics.json`
- B daily：`examples/portfolio_backtesting/backtest_outputs/qmt_range_reversion_full_commodity_v10_daily_equity.csv`
- B trades：`examples/portfolio_backtesting/backtest_outputs/qmt_range_reversion_full_commodity_v10_trades_2020_2026_04.csv`
- B position attribution：`examples/portfolio_backtesting/backtest_outputs/qmt_range_reversion_full_commodity_v10_position_changes_2020_2026_04.csv`
- B candidate snapshots：`examples/portfolio_backtesting/backtest_outputs/qmt_range_reversion_full_commodity_v10_entry_candidate_snapshots_2020_2026_04.csv`
- B dashboard：`examples/portfolio_backtesting/backtest_outputs/qmt_range_reversion_full_commodity_v10_professional_dashboard.html`
- 说明：`backtest_outputs/` 被 `.gitignore` 忽略，冻结输出保留在当前工作区，可由新增入口复现。

## 验证

- TDD RED：模块缺失时 3 个测试失败；metadata 产品计数、审计源缺失回退写回、金融后缀防御和运行身份测试均先失败。
- TDD GREEN：`.py311/bin/python -m unittest tests.test_futures_range_full_commodity_v10 -v`，`6/6` 通过。
- 语法：`.py311/bin/python -m py_compile ...` 通过。
- 池校验：56 个产品、CFFEX `0`、direction_hint 全为 `both`。
- A/B 都由当前工作区冷启动重新运行，统计文件完整落盘；身份增强后B再次冷启动，核心数值逐项精确复现。
- B statistics 已记录 `setting/product universe/source universe/strategy source/runner source` SHA256、`same_day_close_on_bar` 撮合标签和请求分析边界。

## 独立评审

- reviewer：`Ptolemy / 01a05cf0-381b-7772-a204-b18f05789e5a`
- 首轮：`P0/P1/P2/P3=0/2/3/0`，结论为实现基本正确、策略候选应拒绝。
- 两个P1：非PIT品种池与同日收盘撮合，属于研究结构限制，阻断晋级但不推翻拒绝结论。
- 三个P2：A/B原生日表起点不同；statistics身份字段不足；缺源回退未把过滤结果写回实际引擎输入。
- 处理：共同区间敏感性已补；身份字段与实际写回已用TDD修复并重跑B。
- 最终复审：原身份与写回两个P2关闭，无新增finding；剩余`P0/P1/P2/P3=0/2/1/0`。剩余P2仅为A/B原生日表起点不同，已由共同区间敏感性覆盖；不改变拒绝结论。

## 结论

- 本阶段结论：`reject_full_commodity_uniform_both_v10_keep_core4_v8_internal_baseline`
- 实现层面：仓库现在具备“全可交易商品、排除金融期货”的独立震荡回测入口。
- 策略层面：B 不晋级。扩容把交易数放大约 `15.7x`、滑点放大约 `13.0x`，但收益更低、回撤约为 A 的 `7.9x`，Sharpe 接近零。
- 是否进入下一步：否；不做参数优化、品种剔除、方向筛选、顺序敏感性、成本压力或 Stage78 组合。
- 下一步：保留 Core4 v8 为震荡路线内部基准，按原 LINE 计划继续 `cs.DCE short` 状态归因；若未来研究全市场反转，必须另开线并使用事前状态分类或横截面机制，不得复用本次亏损名单选品。

## 过拟合反思

- 运行前判断：风险高，但本轮本身不是后验过拟合；只测试一个固定、低自由度的全商品统一规则。
- 运行后判断：当前结果没有通过门槛，若继续按亏损品种、方向或年份筛选就是明显过拟合。
- 原因：52 个扩展品种整体亏损、年度结果高度集中，市场并不存在无条件普适的统一反转边际。

## 继续价值反思

- 运行前判断：有；可以直接检验“Core4 是否只是小池过拟合”和“全市场扩容是否提升分散”。
- 运行后判断：当前全市场统一双向路线无继续价值；代码入口保留用于复验和负向基准。
- 原因：候选已被完整样本、成本和跨年度结果共同否决，再扫参数只会扩大研究者自由度。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否；该文件已有其他研究线未提交改动，避免并行冲突
- 是否追加根目录 `memory.md/back_log.md`：是；本阶段关闭了一条明确扩容路线
