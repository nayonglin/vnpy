# Stage154 预收盘一致信号bar数据覆盖审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-28 05:46 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：执行语义工程可行性审计；不新增策略，不修改 Stage079/C3 交易规则。
- 是否重要突破：是。确认“信号生成bar和成交价一致”的预收盘口径当前数据基础不足，不能直接回放。
- 是否触发A/B：否。本阶段没有产生可晋级策略版本。

## 外部调研与判断

- 参考资料：
  - Backtrader order execution: https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/
  - ML4T execution semantics: https://ml4trading.io/docs/backtest/user-guide/execution-semantics/
  - NautilusTrader backtesting / simulated exchange: https://nautilustrader.io/docs/latest/concepts/backtesting
  - TqSdk 1分钟K示例： https://tqsdk-python.readthedocs.io/en/latest/usage/ta.html
  - TqSdk 回测多行情序列： https://tqsdk-python.readthedocs.io/en/stable/usage/backtest.html
- 我的判断：
  - 开源回测框架的共同约束是：信号可见时间、订单提交时间、撮合价格必须在同一事件序列里闭合；用日线收盘信号去假设同一根bar的盘中分钟价成交，会形成执行语义泄漏。
  - Stage153 已证明三种“日线收盘信号 + 预收盘成交价”的路径都不能晋级，但它仍然没有解决信号本身是否能在收盘前冻结的问题。
  - 本阶段只审计数据覆盖，不筛收益、不筛品种、不调参数，因此不是过拟合。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage454_preclose_signal_bar_data_readiness.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `MODEL_TAG=stage454_preclose_signal_bar_data_readiness_v1`
  - 覆盖对象：2020-01-02 至 2026-04-30 每个交易日、每个 C3 产品对应主力合约。
  - 最低数据需求：每日主力合约 `14:55-15:00` 1分钟窗口。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30。
- 账户规模：不适用；本阶段不生成权益曲线。
- 成本口径：不适用；本阶段不撮合成交。
- 样本过滤：无。
- 策略/归因口径：
  - 固定读取 Stage079/C3 产品宇宙与日度主力映射。
  - 统计每个 `(date, vt_symbol)` 是否已有 `14:55-15:00` 分钟窗口覆盖。
  - 生成缺口最多合约、产品覆盖率和按连续缺口合并的下载计划。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：

| 指标 | 数值 |
| --- | ---: |
| 必需主力合约日键 | 26,380 |
| 已覆盖键 | 4,905 |
| 缺口键 | 21,475 |
| 覆盖率 | 18.5936% |
| 必需合约数 | 462 |
| 已覆盖合约数 | 229 |
| 缺口合约数 | 455 |
| 产品数 | 19 |
| 下载计划span数 | 547 |
| 下载计划合约数 | 455 |

覆盖率最低产品：

| product_vt_symbol | 必需 | 已覆盖 | 缺口 | 覆盖率 |
| --- | ---: | ---: | ---: | ---: |
| SH.CZCE | 632 | 19 | 613 | 3.0063% |
| si.GFEX | 811 | 33 | 778 | 4.0691% |
| cu.SHFE | 1,532 | 157 | 1,375 | 10.2480% |
| lc.GFEX | 672 | 86 | 586 | 12.7976% |
| hc.SHFE | 1,532 | 200 | 1,332 | 13.0548% |
| fu.SHFE | 1,532 | 226 | 1,306 | 14.7519% |
| SA.CZCE | 1,532 | 228 | 1,304 | 14.8825% |
| sp.SHFE | 1,532 | 248 | 1,284 | 16.1880% |
| OI.CZCE | 1,532 | 250 | 1,282 | 16.3185% |
| au.SHFE | 1,532 | 252 | 1,280 | 16.4491% |

缺口最多合约：

| vt_symbol | 产品 | 必需 | 已覆盖 | 缺口 | 缺口区间 | 覆盖率 |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| lh2109.DCE | lh.DCE | 148 | 0 | 148 | 2021-01-08 至 2021-08-17 | 0.0000% |
| SH405.CZCE | SH.CZCE | 146 | 11 | 135 | 2023-09-15 至 2024-04-26 | 7.5342% |
| lc2407.GFEX | lc.GFEX | 131 | 0 | 131 | 2023-12-08 至 2024-06-26 | 0.0000% |
| si2308.GFEX | si.GFEX | 127 | 0 | 127 | 2022-12-22 至 2023-07-04 | 0.0000% |
| au2112.SHFE | au.SHFE | 121 | 9 | 112 | 2021-05-28 至 2021-11-24 | 7.4380% |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage454_preclose_signal_bar_data_readiness_report_stage454_preclose_signal_bar_data_readiness_v1.md`
- required：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage454_preclose_signal_bar_data_readiness_required_keys_stage454_preclose_signal_bar_data_readiness_v1.csv`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage454_preclose_signal_bar_data_readiness_summary_stage454_preclose_signal_bar_data_readiness_v1.csv`
- product_coverage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage454_preclose_signal_bar_data_readiness_product_coverage_stage454_preclose_signal_bar_data_readiness_v1.csv`
- symbol_coverage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage454_preclose_signal_bar_data_readiness_symbol_coverage_stage454_preclose_signal_bar_data_readiness_v1.csv`
- download_plan：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage454_preclose_signal_bar_data_readiness_download_plan_stage454_preclose_signal_bar_data_readiness_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage454_preclose_signal_bar_data_readiness_decision_stage454_preclose_signal_bar_data_readiness_v1.json`

## 结论

- 决策标签：`consistent_preclose_replay_data_not_ready_need_main_contract_window_backfill`
- 本阶段结论：当前不能做可信的“预收盘信号bar + 同一预收盘窗口成交价”真实路径回放。最低限度的 `14:55-15:00` 主力合约分钟窗口覆盖率只有 `18.5936%`，直接回放会大量 fallback，结论会被数据缺口污染。
- 是否进入下一步：进入执行数据工程下一步，不进入策略候选晋级。
- 下一步：
  - 先做 Stage155 最小数据规格确认：如果只替换 signal close 和 fill price，`14:55-15:00` 是最低需求；如果要完整替换策略看到的日K，则还需要当日截至冻结时点的 open/high/low/close 分钟聚合。
  - 按 `download_plan` 分片补齐主力合约分钟数据，优先选择覆盖缺口最大且对历史回撤窗口影响大的合约span。
  - 数据覆盖足够后，再做真正一致的预收盘信号bar与成交价回放；在此之前不继续做同日收盘口径 alpha 补丁。

## 独立判断

- 不按目标也没有值得晋级的策略版本；本阶段唯一值得晋级的是执行数据工程本身。
- Stage153 的三种成交语义失败后，继续强行挑一个好看的 `14:59 close-like` 路径，本质是在挑执行假设；这不是穿越周期的策略改进。
- 但我认为继续沿执行一致性路线有价值，因为它能回答一个更底层的问题：Stage079/Stage103 的日线同日收盘收益，到底有多少能转换为真实会话可成交路径。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只统计数据覆盖，不生成收益曲线，不根据收益筛日期、品种或参数；它是在减少执行假设自由度，而不是增加拟合自由度。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但路径必须收窄。
- 原因：同日收盘口径 alpha 补丁价值已经很低；真正值得继续的是先把信号可见时间、bar字段和成交价格统一起来。当前覆盖率只有 `18.5936%`，说明下一步应优先补数据/定义最小数据规格，而不是继续做策略优化。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录一致预收盘回放当前数据未就绪。
- 是否更新 `research/registry.md`：是，本阶段改变下一步优先级。
- 是否追加根目录 `memory.md/back_log.md`：是，属于重要执行口径长期记忆。
