# Stage127 C9 当前实盘15万止损执行压力版

> 修正说明（2026-06-23 13:53 CST）：本记录中的数值已被 Stage128 作废。原因是 Stage901 `_run_live_c9()` 当时未注入 Stage861 全量分钟K，导致 `intraday_only` 被误报为 `0`。修正后 `intraday_only=203`，详见 `20260623_1353_stage128_stage901_minute_bar_injection_fix.md`。

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-23 13:41 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：当前实盘版本的止损执行成本压力 overlay
- 是否重要突破：否。它不改变策略，只把“止损触发后实际成交更差”的成本压力量化。
- 是否触发A/B：否。本阶段不引入新策略、不替换实盘版本、不调整参数。

## 外部调研与判断

- 参考资料：
  - Backtrader 官方 slippage 文档：https://www.backtrader.com/docu/slippage/slippage/
  - QuantConnect 官方 slippage model 文档：https://www.quantconnect.com/docs/v2/writing-algorithms/migrations/zipline/quick-reference
- 我的判断：止损执行压力不应该通过调策略参数来“救结果”，而应该作为成交模型/TCA 成本 overlay。固定 tick 档位比按年份、品种或某几笔止损反向调参更稳健，也更符合实盘成交偏差评估的第一性问题。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage937_c9_live_15w_stop_execution_stress.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `STRESS_TICKS=(0, 1, 2, 5)`
  - `intraday_only`：只统计 Stage827 C2 1R intraday stop 和 Stage847 C9 0.5R stop/retry close 事件
  - `all_strategy_stop_close`：统计所有 `exit_reason` 包含 `stop` 的策略平仓成交
- 修改参数：无策略参数修改
- 删除参数：无

## 回测/归因参数

- 当前实盘版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `Stage847-C9-15w`
- 当前实盘 profile：`stage847_c9_15w_stage819_05r_stop_retry_live`
- 账户规模：`150,000`
- AI 池：Stage182 月更 AI 池，路径为 `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_stage182_ai_product_pool_live_inference_v1.csv`
- 起点：从 `2020-01-01` 起，每年 `1月1日` 和 `7月1日`
- 数据终点：`2026-06-15`
- horizon：只统计完整半年/一年；半年样本 `12` 个，一年样本 `11` 个
- 压力公式：`extra_cost = stress_ticks * pricetick * contract_size * close_volume`
- 执行语义：不改变信号、手数、止损线、重进逻辑或持仓路径，只在止损平仓日从权益中扣除额外不利成交成本
- CTP/订单：不连接 CTP，不读取账户，不调用 send/cancel/order API

## 结果

- `intraday_only` 口径：
  - 事件数：`0`
  - 半年收益：最低 `-26.42%`、中位 `13.58%`、最高 `157.86%`，正收益 `11/12`
  - 一年收益：最低 `-32.18%`、中位 `35.99%`、最高 `428.51%`，正收益 `10/11`
  - 结论：当前这些历史 live-pool 半年/一年窗口里，真正 Stage827/Stage847 分钟级止损/重进场事件没有触发，所以该口径压力对结果没有影响。
- `all_strategy_stop_close` 口径事件数：
  - 所有完整起点合计 `376` 个策略止损类平仓事件
- `all_strategy_stop_close` 半年结果：
  - 0 tick：最低 `-26.42%`、中位 `13.58%`、最高 `157.86%`，正收益 `11/12`，最差最大回撤 `-35.1231%`
  - 1 tick：最低 `-27.13%`、中位 `13.27%`、最高 `156.60%`，正收益 `11/12`，中位收益少 `0.6250pp`
  - 2 tick：最低 `-27.85%`、中位 `12.97%`、最高 `155.34%`，正收益 `11/12`，中位收益少 `1.2500pp`
  - 5 tick：最低 `-29.99%`、中位 `12.05%`、最高 `151.56%`，正收益 `10/12`，中位收益少 `3.1250pp`
- `all_strategy_stop_close` 一年结果：
  - 0 tick：最低 `-32.18%`、中位 `35.99%`、最高 `428.51%`，正收益 `10/11`，最差最大回撤 `-40.7369%`
  - 1 tick：最低 `-33.09%`、中位 `34.91%`、最高 `423.75%`，正收益 `10/11`，中位收益少 `1.0833pp`
  - 2 tick：最低 `-33.99%`、中位 `33.82%`、最高 `418.99%`，正收益 `10/11`，中位收益少 `2.1667pp`
  - 5 tick：最低 `-36.71%`、中位 `30.54%`、最高 `404.71%`，正收益 `10/11`，中位收益少 `5.4167pp`
- 期末权益：
  - `all_strategy_stop_close` 5 tick 半年：最低 `105,020`、中位 `168,070`、最高 `377,340`
  - `all_strategy_stop_close` 5 tick 一年：最低 `94,930`、中位 `195,810`、最高 `757,065`
  - `intraday_only` 5 tick 半年：最低 `110,370`、中位 `170,370`、最高 `386,790`
  - `intraday_only` 5 tick 一年：最低 `101,730`、中位 `203,985`、最高 `792,765`
- 总收益：
  - 最保守的 `all_strategy_stop_close` 5 tick 半年中位 `12.05%`
  - 最保守的 `all_strategy_stop_close` 5 tick 一年中位 `30.54%`
- 最大回撤：
  - `all_strategy_stop_close` 5 tick 半年最差 horizon 内最大回撤 `-37.4842%`
  - `all_strategy_stop_close` 5 tick 一年最差 horizon 内最大回撤 `-43.4091%`
- Sharpe：不适用。本阶段统计多个固定启动 horizon，不计算单一连续路径 Sharpe。
- 总滑点：
  - 基础滑点继承 Stage936 原始 live 回放，本阶段未改基础成交成本
  - `all_strategy_stop_close` 5 tick 额外止损执行成本：半年样本合计 `70,500`，一年样本合计 `164,975`
- 总交易次数：
  - 本阶段不新增交易、不删交易；只对既有止损平仓做成本 overlay
  - `all_strategy_stop_close` 可识别止损类平仓事件 `376` 个
- 胜率：
  - `intraday_only` 半年 `11/12 = 91.67%`，一年 `10/11 = 90.91%`
  - `all_strategy_stop_close` 5 tick 半年 `10/12 = 83.33%`，一年 `10/11 = 90.91%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage937_c9_live_15w_stop_execution_stress_report_stage937_c9_live_15w_stop_execution_stress_v1.md`
- stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage937_c9_live_15w_stop_execution_stress_stats_stage937_c9_live_15w_stop_execution_stress_v1.csv`
- detail：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage937_c9_live_15w_stop_execution_stress_detail_stage937_c9_live_15w_stop_execution_stress_v1.csv`
- events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage937_c9_live_15w_stop_execution_stress_events_stage937_c9_live_15w_stop_execution_stress_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage937_c9_live_15w_stop_execution_stress_curves_stage937_c9_live_15w_stop_execution_stress_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage937_c9_live_15w_stop_execution_stress_decision_stage937_c9_live_15w_stop_execution_stress_v1.json`
- dashboard：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage937_c9_live_15w_stop_execution_stress_dashboard_stage937_c9_live_15w_stop_execution_stress_v1.png`

## 结论

- 本阶段结论：如果只看当前 C9 实时分钟级止损/重进场机制，历史这些窗口里事件数为 `0`，因此无法从这组回测里证明它会造成额外收益损耗。更保守地把所有策略止损类平仓都按额外 5 tick 不利成交处理后，半年中位收益从 `13.58%` 降到 `12.05%`，一年中位收益从 `35.99%` 降到 `30.54%`，收益分布被压低但没有被摧毁。
- 是否进入下一步：是，但下一步不是调参，而是用真实成交回报做 TCA 校准。实盘出现真实止损成交后，应比较触发价、最终挂单价、成交均价、盘口价差和撤改单次数，再决定 1/2/5 tick 哪个压力档更接近真实。
- 下一步：把 Stage937 作为当前 live 版本执行压力基线；后续补真实 TCA 后重跑同一脚本，不按年份或品种单独改策略。

## 过拟合反思

- 运行前判断：否。压力 tick 档位固定，且不改变信号、仓位、止损线或重进逻辑。
- 运行后判断：否。本次只是执行成本 overlay，不用结果反向筛参数；`all_strategy_stop_close` 是保守压力口径，不是新规则。
- 原因：固定成本压力检验的是执行误差承受力，不是在训练新的 alpha 或过滤条件。

## 继续价值反思

- 运行前判断：是。它直接回答用户担心的“止损触发时，实际挂单成交价格更差，会不会破坏回测”。
- 运行后判断：是。5 tick 保守压力下收益中位仍为正，但左尾回撤更深，这对实盘心理预期和 TCA 监控有价值。
- 原因：当前 live 的核心剩余不确定性在执行质量和账户承受，不在继续扫策略参数。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage937 止损执行压力摘要。
- 是否更新 `research/registry.md`：否。未改变路线状态或正式版本。
- 是否追加根目录 `memory.md/back_log.md`：否。不是正式版本切换或重要突破。
