# Stage152 Stage079 14:55 VWAP fallback补齐迭代回放审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-28 05:28 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：执行代理覆盖补齐与真实路径稳定性审计；不新增策略，不修改 Stage079/C3 交易规则。
- 是否重要突破：是，属于执行口径否决型突破。
- 是否触发A/B：否。本阶段没有产生可晋级策略版本。

## 外部调研与判断

- 参考资料：
  - Backtrader order execution: https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/
  - NautilusTrader backtesting: https://nautilustrader.io/docs/latest/concepts/backtesting
  - Implementation Shortfall: https://trading.glass/en/academy/execution-precision/execution-metrics/implementation-shortfall
  - TqSdk docs: https://tqsdk-python.readthedocs.io/
  - TqSdk disclaimer: https://www.shinnytech.com/blog/disclaimer/
- 我的判断：
  - 事件驱动回测里，成交价会改变后续仓位、止损、再开仓路径；不能用一阶权益差替代真实路径回放。
  - 混用真实分钟代理价和原理论订单价 fallback 会污染结论，因此必须先把 Stage151 的 `101` 笔 fallback 清零。
  - 本阶段不是优化 alpha，而是校准执行语义；如果补齐后仍失败，应否决这个执行口径，而不是继续救参数。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage452_iterative_1455_proxy_backfill.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `MODEL_TAG=stage452_iterative_1455_proxy_backfill_v1`
  - `TRUE_PATH_VARIANT=stage079_true_path_1455_vwap_symbol_date_backfilled`
  - 代理价键从 Stage151 的订单队列语义改为 `(交易日, 合约)` 固定 14:55 VWAP。
  - `MAX_ITERATIONS=4`
  - `MAX_SECONDS_PER_SYMBOL=180`
  - raw 数据源优先级：`tqsdk_stage452_true_path_fallback_1455`、`tqsdk_stage448_minute_session_rebuild_batch`
  - fallback 补齐窗口：交易日 `14:55-14:59` 1分钟K VWAP。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30。
- 账户规模：Stage079 账户口径 `615,000`，即 `50万C3下单 + 11.5万外部现金`。
- 成本口径：沿用 Stage079/C3 原滑点；另做 `1x/2x/3x/5x` 成本压力。
- 样本过滤：无；只补齐真实路径产生的 fallback 日期/合约。
- 策略/归因口径：
  - baseline：Stage079 Stage403 冻结日权益。
  - rerun：同日收盘口径真实引擎重跑，用于确认入口可复现。
  - true path：先按同日收盘撮合产生订单，再把成交价替换为 `(日期, 合约)` 14:55 VWAP，并让该成交价进入后续仓位路径。

## 结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 252日破30率 | 504日破30率 | 年度/季度冷启动回撤30内 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 baseline | 31,040,650 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 0.0000% | 0.0000% | 100.0000% / 100.0000% |
| Stage079 same-day rerun | 31,040,650 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 0.0000% | 0.0000% | 100.0000% / 100.0000% |
| Stage079 true path 14:55 VWAP backfilled | 35,470,684 | 5667.5909% | -30.1914% | 1.3504 | 14.8757 | 5.2913% | 19.9668% | 60.0000% / 54.5455% |

交易与覆盖：

- Stage079 baseline 总滑点：`1,556,750`
- Stage079 baseline 总交易次数：`757`
- Stage079 baseline 非零日胜率：`48.3478%`
- true path 总滑点：`1,828,100`
- true path 总交易次数：`774`
- true path 非零日胜率：`51.9548%`
- 初始代理键数：`692`
- 最终代理键数：`797`
- 新增/补齐代理键数：`105`
- Stage151 fallback 笔数：`101`
- Stage152 最终 fallback 笔数：`0`
- 最终代理成交数：`774`
- 迭代次数：`3`

3个月/6个月体验：

| 版本 | 周期 | 5%分位收益 | 中位收益 | 正收益率 | 年化低于5%概率 | 最差期内回撤 | 破20回撤率 | 破30回撤率 | Ulcer P95 | P95最长水下 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 baseline | 3个月 | -11.4702% | 13.5434% | 73.4804% | 29.4012% | -29.1988% | 18.5052% | 0.0000% | 17.7786 | 88.0 |
| true path backfilled | 3个月 | -11.5925% | 16.4426% | 75.9568% | 26.5196% | -29.3748% | 18.1450% | 0.0000% | 18.5661 | 87.0 |
| Stage079 baseline | 6个月 | -2.0393% | 33.9947% | 93.4772% | 9.0099% | -29.7007% | 35.7109% | 0.0000% | 19.9011 | 167.0 |
| true path backfilled | 6个月 | -0.2969% | 33.6513% | 94.4158% | 7.0389% | -30.1914% | 30.5960% | 1.7832% | 20.5756 | 162.5 |

短持有体验分：

- Stage079 baseline：3个月 `100.0000`，6个月 `100.0000`，综合 `100.0000`
- true path backfilled：3个月 `112.0785`，6个月 `153.3823`，综合 `134.7956`

成本压力：

| 版本 | 1x最大回撤 | 2x最大回撤 | 3x最大回撤 | 5x最大回撤 |
| --- | ---: | ---: | ---: | ---: |
| Stage079 baseline | -29.7007% | -31.2917% | -33.0035% | -40.1055% |
| true path backfilled | -30.1914% | -31.9483% | -33.8567% | -38.5592% |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage452_iterative_1455_proxy_backfill_report_stage452_iterative_1455_proxy_backfill_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage452_iterative_1455_proxy_backfill_chart_stage452_iterative_1455_proxy_backfill_v1.png`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage452_iterative_1455_proxy_backfill_daily_stage452_iterative_1455_proxy_backfill_v1.csv`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage452_iterative_1455_proxy_backfill_summary_stage452_iterative_1455_proxy_backfill_v1.csv`
- horizon：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage452_iterative_1455_proxy_backfill_horizon_stage452_iterative_1455_proxy_backfill_v1.csv`
- score：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage452_iterative_1455_proxy_backfill_score_stage452_iterative_1455_proxy_backfill_v1.csv`
- gate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage452_iterative_1455_proxy_backfill_gate_stage452_iterative_1455_proxy_backfill_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage452_iterative_1455_proxy_backfill_cost_stress_stage452_iterative_1455_proxy_backfill_v1.csv`
- trade_usage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage452_iterative_1455_proxy_backfill_trade_usage_stage452_iterative_1455_proxy_backfill_v1.csv`
- backfill_status：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage452_iterative_1455_proxy_backfill_backfill_status_stage452_iterative_1455_proxy_backfill_v1.csv`
- proxy_map：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage452_iterative_1455_proxy_backfill_proxy_map_stage452_iterative_1455_proxy_backfill_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage452_iterative_1455_proxy_backfill_decision_stage452_iterative_1455_proxy_backfill_v1.json`

## 结论

- 决策标签：`iterative_1455_backfill_hard_fail_reject_1455_execution`
- 本阶段结论：补齐成功，但 `14:55 VWAP` 真实路径仍硬失败。
- 是否进入下一步：本执行口径不晋级；Stage103/xsmom 真实 paper 晋级继续暂停。
- 下一步：
  - 不继续在同日收盘口径上做 3个月/6个月 alpha 补丁。
  - 只允许预先定义其它少数可部署成交语义后重放，例如最后1分钟、收盘前可成交窗口、夜盘/白盘开盘窗口；不能按收益选择成交价。
  - 如果可部署成交语义普遍破30，应重新定义真实执行资金缓冲，而不是继续用 alpha 覆盖执行模型风险。

## 独立判断

- 不按用户目标机械看，Stage152 也不值得晋级。
- 理由：
  - 3个月/6个月分数确实更高，6个月破20率也下降。
  - 但全周期最大回撤破 `30%`，504日滚动破30率接近 `20%`，年度/季度冷启动通过率从 `100%/100%` 掉到 `60%/54.5455%`。
  - 这不是稳定改善持有体验，而是更高权益峰值后的更深水下路径。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只补执行价覆盖和重放固定成交语义，没有按收益、坏窗口、品种或日期调参；失败后也没有救参数。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但方向改变。
- 原因：执行模型审计仍然有价值，因为它决定 Stage079/Stage103 能否真实 paper/影子盘；但继续救 `14:55 VWAP` 或继续做同日收盘口径 alpha 优化价值低。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 `14:55 VWAP` 补齐后仍硬失败。
- 是否更新 `research/registry.md`：是，本阶段改变当前下一步优先级。
- 是否追加根目录 `memory.md/back_log.md`：是，属于重要执行口径长期记忆。
