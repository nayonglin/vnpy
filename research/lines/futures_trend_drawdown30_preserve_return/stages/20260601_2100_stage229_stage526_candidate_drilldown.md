# Stage229 Stage526候选深复盘

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-01 21:00 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：固定候选只读深复盘；不改策略、不扫参数、不重跑入场逻辑
- 是否重要突破：否；但明确了 `r080_pc25_maxpos4` 的未完成风险来源
- 是否触发A/B：否。本阶段没有产生新策略版本，只是对已晋级候选做候选级归因。

## 外部调研与判断

- 参考资料：
  - Tushare `fut_holding` 说明：会员成交持仓排名可按交易日、品种、交易所查询，说明国内期货基本面/持仓外生数据具备日级实盘化可能。
  - Tushare 期货接口说明：合约行情带交易所后缀，品种级持仓/仓单等使用品种代码，后续工程接入需要统一映射口径。
  - AKShare 期货数据文档：仓单、基差等数据可通过 Python 接口获取，但必须检查交易日发布时间和历史覆盖。
  - 趋势跟踪/ATR止损资料：ATR止损常用于控制单笔风险和横盘反复亏损，但容易在趋势中被噪音洗出，不能直接当作免费午餐。
- 我的判断：
  - 基本面数据有继续研究价值，但必须先保证 `品种映射 + 发布时间 + 缺失处理 + 实盘日更` 四件事，不允许只做回测端 hindsight。
  - 舆情数据当前优先级低于基本面和逐笔复盘。舆情可执行性最大问题是稳定来源、发布时间、噪音和中文商品口径映射；没有点时化数据前不能接入候选。
  - ATR/K线形态不是禁止方向，但本阶段证据显示 2022 的坏窗口是长路径亏损叠加成本，不是保证金峰值；若测 ATR，应从 2022 `fu/MA/sp/FG/jm` 这类窗口做逐笔退出复盘，而不是扫 ATR 倍数。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage529_stage526_candidate_drilldown.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30
- 账户规模：`615,000`
- 成本口径：正常成本、2x滑点成本、3x滑点成本
- 样本过滤：固定 `r080_pc25_maxpos4`
- 策略/归因口径：
  - 使用 Stage526 已生成的日度权益、逐日持仓和 exact margin 文件。
  - 产品贡献只统计 C3 持仓逐日 PnL；xsmom 作为独立 sleeve 只在窗口级汇总。
  - 不新增交易信号，不新增过滤条件，不改变已有候选。

## 结果

- 期末权益：`23,369,505`
- 总收益：`3699.9195%`
- 最大回撤：`-36.2670%`
- Sharpe：`1.6385`
- 总滑点：`1,342,190`
- 总交易次数：`905`
- 胜率：`53.6330%`
- 其他关键指标：
  - 决策：`candidate_drilldown_3x_cost_is_main_unfinished_risk`
  - 3x成本最大回撤窗口：`2022-03-09 -> 2022-12-07`
  - 3x成本最大回撤：`-42.0555%`
  - 同窗口正常成本最大回撤：`-36.2670%`
  - 该窗口 broker10 最大保证金/权益：`64.4959%`
  - 该窗口总净PnL：`-1,614,915`
  - 该窗口 C3净PnL：`-1,551,400`
  - 该窗口 xsmom净PnL：`-63,515`
  - 该窗口总滑点：`73,710`
  - 3x 相对 1x 在谷底额外累计成本：`508,430`
  - 最差63日窗口：`2021-10-19 -> 2022-01-17`，收益 `-31.1143%`，窗口回撤 `-32.6605%`
  - 最差126日窗口：`2022-03-09 -> 2022-09-09`，收益 `-33.1790%`，窗口回撤 `-34.5134%`

## 产品归因

Top profit：

| 产品 | net_pnl | 滑点 | 交易次数 | 活跃天数 | 最大C3保证金 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `jm.DCE` | `7,808,190` | `141,000` | `55` | `171` | `5,119,992` |
| `OI.CZCE` | `3,706,830` | `23,920` | `33` | `166` | `4,933,202` |
| `lh.DCE` | `2,464,880` | `115,360` | `41` | `103` | `3,781,709` |
| `ru.SHFE` | `2,051,000` | `111,250` | `56` | `139` | `4,698,672` |
| `FG.CZCE` | `1,619,480` | `137,880` | `51` | `175` | `1,833,720` |

Top loss：

| 产品 | net_pnl | 滑点 | 交易次数 | 活跃天数 | 最大C3保证金 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `MA.CZCE` | `-2,232,070` | `92,740` | `52` | `125` | `1,691,208` |
| `AP.CZCE` | `-844,960` | `34,080` | `38` | `136` | `3,415,526` |
| `SH.CZCE` | `-189,090` | `51,780` | `9` | `15` | `3,223,771` |
| `sp.SHFE` | `-39,160` | `51,920` | `31` | `122` | `2,508,000` |

最差窗口归因：

- 最差63日主要亏损：`lh.DCE -705,680`、`ru.SHFE -264,000`、`AP.CZCE -221,910`、`cu.SHFE -157,200`、`sp.SHFE -106,320`。
- 最差126日/全周期最大回撤主要亏损：`fu.SHFE -916,390`、`MA.CZCE -336,870`、`sp.SHFE -243,320/-313,020`、`FG.CZCE -210,320`、`jm.DCE -205,440`。
- `fu.SHFE` 全周期仍为 `+878,660`，但在 2022 最大回撤窗口贡献最大亏损；这说明直接产品黑名单会误杀有效收益源。

## 视觉判断

- 成本压力图显示 1x/2x/3x 曲线形状几乎一致，3x 不是改变收益来源，而是把同一段 2022 长回撤整体下移。
- 产品贡献图显示收益端集中在 `jm/OI/lh/ru`，但亏损端不是同一组产品的简单镜像；`MA` 是稳定拖累，`fu` 则是“全周期赚钱但坏窗口伤害大”。
- 最差3/6个月产品柱状图显示坏窗口不是保证金峰值，也不是 xsmom 造成，主要是 C3 趋势腿在多个品种上连续反复亏损。
- 保证金峰值图表明最大 broker10 日在 `2022-02-17`，而 3x失败窗口是 `2022-03-09 -> 2022-12-07`；两者错位，不能用继续降保证金占用解释全部问题。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage529_stage526_candidate_drilldown_report_stage529_stage526_candidate_drilldown_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage529_stage526_candidate_drilldown_product_summary_stage529_stage526_candidate_drilldown_v1.csv`
- windows：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage529_stage526_candidate_drilldown_bad_windows_stage529_stage526_candidate_drilldown_v1.csv`
- attribution：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage529_stage526_candidate_drilldown_window_product_attribution_stage529_stage526_candidate_drilldown_v1.csv`
- margin：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage529_stage526_candidate_drilldown_margin_peak_products_stage529_stage526_candidate_drilldown_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage529_stage526_candidate_drilldown_cost_failure_stage529_stage526_candidate_drilldown_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage529_stage526_candidate_drilldown_chart_stage529_stage526_candidate_drilldown_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage529_stage526_candidate_drilldown_decision_stage529_stage526_candidate_drilldown_v1.json`

## 结论

- 本阶段结论：
  - `r080_pc25_maxpos4` 仍可保留为主研究候选，但未完成风险已经清晰：`3x成本 + 2022长回撤路径`。
  - 3x失败不是保证金峰值造成，不能靠继续压 broker10 或加现金小修小补解决。
  - 产品黑名单不成立。亏损产品少，但坏窗口和全周期贡献不一致，尤其 `fu.SHFE` 全周期正收益但最大回撤窗口亏损最大。
  - 下一步应做“坏窗口退出/降暴露形态”的低自由度验证，优先检查 ATR/趋势破坏/波动扩张是否能在 2022 窗口减少亏损，同时不能损坏 `jm/OI/lh/ru` 的趋势捕捉。
- 是否进入下一步：是
- 下一步：
  1. 固定 `r080_pc25_maxpos4`，做逐笔级坏窗口复盘，重点 `2021-10-19 -> 2022-01-17` 与 `2022-03-09 -> 2022-12-07`。
  2. 做 ATR/趋势破坏退出的“单次粗规则”反证，不扫倍数小数；只允许一个能解释为通用风控的形状。
  3. 同步做基本面数据可执行性清单，优先仓单、基差、会员持仓；舆情只做来源可执行性审计，暂不进回测。

## 过拟合反思

- 运行前判断：否。本阶段固定候选做归因，不调参数。
- 运行后判断：否，但出现了容易诱导过拟合的陷阱。
- 原因：
  - 归因发现 `MA/AP` 全周期亏损、`fu` 坏窗口亏损，直觉上容易做品种黑名单；但这属于高过拟合风险，且 `fu` 全周期为正，不能这样做。
  - 合理下一步只能测通用退出/降暴露形态，不允许按品种、年份、月份补丁。

## 继续价值反思

- 运行前判断：是。候选已通过硬约束，需要知道失败边界。
- 运行后判断：是。失败边界已经从“保证金问题”收敛为“2022长回撤 + 成本压力问题”。
- 原因：
  - 这能指导下一步优先级：不再继续扫保证金小数，转向坏窗口退出、成本敏感和点时化外生防守数据。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是，本阶段明确了候选未完成风险的本质。
