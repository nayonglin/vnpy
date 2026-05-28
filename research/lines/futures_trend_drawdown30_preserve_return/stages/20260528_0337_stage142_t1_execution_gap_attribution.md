# Stage142 - T+1执行缺口归因

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-28 03:37 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读执行归因；不新增策略规则，不调参数。
- 是否重要突破：是。重要性在于明确 Stage141 的 T+1 open 失败不是单纯换月日问题，而是延迟成交改变持仓路径和缺口暴露。
- 是否触发A/B：否。本阶段不是候选版本，只是 execution model attribution。

## 外部调研与判断

- 参考资料：
  - Chevalier、Darolles，《Futures Market Liquidity and the Trading Cost of Trend Following Strategies》：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3523005
  - QuantStart，《Continuous Futures Contracts for Backtesting Purposes》：https://www.quantstart.com/articles/Continuous-Futures-Contracts-for-Backtesting-Purposes/
  - TradeStation Continuous Futures Contracts 说明：https://help.tradestation.com/10_00/eng/tradestationhelp/tb/futures_continuous_contracts.htm
- 我的判断：执行缺口应该先按 implementation shortfall / roll gap / path divergence 拆解。连续合约和换月确实可能制造假跳变，但本地 Stage142 结果显示 T+1 风险不是“只修换月”就能解决；更关键的是成交滞后一日后，持仓路径和开盘缺口暴露发生了系统性变化。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage442_t1_execution_gap_attribution.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 修改正式策略：无。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`。
- 账户规模：`61.5万`账户口径；C3 下单资金仍为 `50万`，现金仍为 `11.5万`。
- 成本口径：引擎正常成本。
- 样本过滤：无。
- 策略/归因口径：
  - C3 同日收盘成交：`SameDayCloseBacktestingEngine`
  - C3 T+1开盘成交：`NextOpenDelayedExecutionEngine`
  - 归因维度：日期桶、交易日/非交易日、全宇宙换月日、真实持仓合约切换日、产品贡献、合约日贡献、最大回撤区间。

## 结果

总体差异：

| 口径 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 净PnL | 交易次数 | 滑点 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C3 same-day close + 11.5万现金 | 31,040,650 | 4947.2602% | -29.7007% | 1.6226 | 15.1468 | 30,425,650 | 757 | 1,556,750 |
| C3 T+1 next open + 11.5万现金 | 32,778,250 | 5229.7967% | -52.7518% | 1.4928 | 19.2452 | 32,163,250 | 781 | 2,003,820 |
| T+1 - same | +1,737,600 | +282.5366pp | -23.0511pp | -0.1297 | +4.0983 | +1,737,600 | +24 | +447,070 |

最大回撤区间：

| 口径 | 峰值日 | 谷值日 | 恢复日 | 最大回撤 | 持续天数 |
| --- | --- | --- | --- | ---: | ---: |
| same-day close | 2022-07-15 | 2022-12-07 | 2023-03-14 | -29.7007% | 145 |
| T+1 next open | 2021-09-16 | 2022-02-11 | 2022-07-11 | -52.7518% | 148 |

日期桶归因：

| 日期桶 | 天数 | T+1相对same差额 | 负向差额 | 正向差额 | 负向天数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 全部日期 | 1532 | +1,737,600 | -28,210,665 | +29,948,265 | 507 |
| 全宇宙换月日 | 312 | +97,955 | -5,468,920 | +5,566,875 | 104 |
| 非全宇宙换月日 | 1220 | +1,639,645 | -22,741,745 | +24,381,390 | 403 |
| 真实活跃持仓切换日 | 361 | +3,430,495 | -7,167,445 | +10,597,940 | 128 |
| 非活跃持仓切换日 | 1171 | -1,692,895 | -21,043,220 | +19,350,325 | 379 |
| 交易日 | 878 | -1,243,880 | -21,731,715 | +20,487,835 | 373 |
| 非交易日 | 654 | +2,981,480 | -6,478,950 | +9,460,430 | 134 |

产品负向贡献 Top5：

| 品种 | 总差额 | 负向差额 | 正向差额 | T+1最大回撤窗口差额 |
| --- | ---: | ---: | ---: | ---: |
| ru.SHFE | -436,800 | -4,219,900 | +3,783,100 | -470,750 |
| lh.DCE | +1,600,320 | -3,461,680 | +5,062,000 | -425,600 |
| FG.CZCE | -61,560 | -3,276,540 | +3,214,980 | -234,560 |
| AP.CZCE | -1,053,170 | -3,242,750 | +2,189,580 | -97,640 |
| jm.DCE | -21,690 | -3,042,360 | +3,020,670 | -78,930 |

合约日最差样例：

- `2025-04-07 lc2505.GFEX`：same `+814,800`，T+1 `-155,000`，差额 `-969,800`。
- `2026-04-29 ru2609.SHFE`：same `+837,600`，T+1 `0`，差额 `-837,600`。
- `2023-04-20 FG309.CZCE`：same `+600,480`，T+1 `0`，差额 `-600,480`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage442_t1_execution_gap_attribution_report_stage442_t1_execution_gap_attribution_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage442_t1_execution_gap_attribution_summary_stage442_t1_execution_gap_attribution_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage442_t1_execution_gap_attribution_daily_attribution_stage442_t1_execution_gap_attribution_v1.csv`
- bucket：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage442_t1_execution_gap_attribution_bucket_attribution_stage442_t1_execution_gap_attribution_v1.csv`
- product：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage442_t1_execution_gap_attribution_product_delta_stage442_t1_execution_gap_attribution_v1.csv`
- contract：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage442_t1_execution_gap_attribution_contract_date_delta_stage442_t1_execution_gap_attribution_v1.csv`
- drawdown：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage442_t1_execution_gap_attribution_drawdown_periods_stage442_t1_execution_gap_attribution_v1.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage442_t1_execution_gap_attribution_trades_stage442_t1_execution_gap_attribution_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage442_t1_execution_gap_attribution_decision_stage442_t1_execution_gap_attribution_v1.json`

## 结论

- 本阶段结论：T+1 open 失败不是单纯换月日问题。活跃持仓切换日整体差额为正，非活跃切换日和交易日才是主要负向来源之一；这说明延迟成交改变了持仓路径和缺口暴露。
- 是否进入下一步：是。
- 下一步：
  - 不按最差品种/日期做黑名单或过滤。
  - 优先做 Stage143：验证“日线下一交易日白盘 open”是否等同真实执行计划。如果真实计划是收盘后生成、夜盘集合竞价/开盘或下一可交易时段提交，需要构造更贴近实盘的代理价。
  - 并行只读检查最差合约日是否有连续合约拼接或合约生命周期异常，但不能直接改策略。

## 过拟合反思

- 运行前判断：不是过拟合。本阶段是 Stage141 的归因，不改变交易规则。
- 运行后判断：不是过拟合。没有按 ru/lh/FG/AP/jm 或 2021-2022 坏窗口生成过滤规则。
- 原因：输出只是定位执行模型风险，不把历史坏路径转成 alpha 条件。

## 继续价值反思

- 运行前判断：继续有价值，因为 Stage103 能否实盘化取决于执行时序。
- 运行后判断：继续有价值，但优先级变成执行代理价校准。
- 原因：如果成交代理价错误，继续优化 3/6个月指标会在错误假设上变精细；如果代理价校准后回撤恢复，Stage103 才能继续工程化。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage142 执行归因约束。
- 是否更新 `research/registry.md`：是，更新下一步为真实执行代理价校准。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；暂不追加 `memory.md`。
