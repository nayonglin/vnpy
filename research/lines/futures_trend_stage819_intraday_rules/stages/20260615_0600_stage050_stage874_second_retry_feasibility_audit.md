# Stage050 Stage874 C9 retry_failed 后同日第二次重试可行性审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：day
- 记录时间：2026-06-15 06:00 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读法证；基于 Stage863 全量分钟K口径 C9 stop/retry events 审计“二次重试”是否值得进入真实引擎；不改 Stage372 官方正式版、不改 Stage819 候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否。它是对“多次尝试”分支的边界反证。
- 是否触发A/B：否。没有新策略版本进入正式候选或 A/B。

## 外部调研与判断

- 参考资料：
  - Turtle Trading 原始规则把 entry、stop、exit、position sizing 拆开，趋势系统接受 whipsaw，但每次错误必须用 stop 控制：https://oxfordstrat.com/coasdfASD32/uploads/2016/01/turtle-rules.pdf
  - Backtrader StopTrail / stop order 文档说明 stop 类语义可执行，但不保证“增加重试次数”有统计价值：https://www.backtrader.com/docu/order-creation-execution/trail/stoptrail/
  - Backtrader stop-loss 示例代码可作为 stop/re-entry 工程参考，但不能直接替代本仓库组合资金联动验证：https://github.com/mementum/backtrader/blob/master/samples/stop-trading/stop-loss-approaches.py
  - vn.py CTA strategy 引擎支持本地 stop order 管理，但本线要验证的是 Stage819/C9 组合层 per-entry 分钟路径，不是单策略样例：https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/engine.py
- 我的判断：外部资料支持“错了先退、重新确认再进”的思想，但不支持在一次重试失败后继续机械加重试次数。Stage874 只做 C9 `flat_retry_failed` 后的自然二次 reclaim 法证，不接引擎、不扫次数。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage874_stage863_second_retry_feasibility_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无策略参数。审计规则固定为 C9 `flat_retry_failed` 后，同日剩余分钟K若再次触及原入场价则记为 `second_reclaim`，之后若再次触及同一 `0.5R` stop 则记为 `second_stop`。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage819/C9 全周期。
- 账户规模：30万候选研究口径。
- 成本口径：沿用 Stage863/C9 输出，Stage874 自身不生成真实交易。
- 样本过滤：只看 Stage863 全量分钟K口径下 C9 的 `flat_retry_failed` 事件，共 `25` 笔；不按年份、品种、方向筛选。
- 策略/归因口径：
  - 基准：`stage847_stage819_c4_05r_stop_retry_once`
  - 输入事件：`qmt_roll_stage863_stage847_c10_budget_lock_engine_stop_retry_events_stage863_stage847_c10_budget_lock_engine_v1.csv`
  - 分钟源：Stage861 full minute bars `1,479,592` 根。

## 结果

- 期末权益：不适用，本阶段不接真实引擎。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - C9 `flat_retry_failed` 事件：`25`
  - 同日第二次 reclaim：`9`，占 `36.0000%`
  - 无同日第二次 reclaim：`16`
  - 第二次 reclaim 后再次触发同一 `0.5R` stop：`7`
  - 二次重试条件失败率：`77.7778%`
  - 第二次 reclaim 后能保持到日内结束：`2`
  - 第二次 reclaim 后达到 `+0.5R progress`：`3`
  - 二次失败额外亏损保守估计：`-218,210`
  - 两笔 open_after_second_reentry 的日内收盘盯市：`+61,020`
  - 保守 same-day proxy：`-157,190`
  - 决策：`stage874_second_retry_not_promoted_no_engine`

## 视觉复核

- summary chart 显示 `25` 笔 retry_failed 中，`16` 笔没有第二次 reclaim，`7` 笔第二次 reclaim 后再次失败，只有 `2` 笔能保持到日内结束。
- atlas page001/page002 显示，若严格实时止损，部分 EOD 看起来会反弹的路径在第二次重试后已经先触发 stop，不能用事后收盘收益救参。
- atlas page003 的 `OI505.CZCE` 是少数能保持到 EOD 的样本，但只有一笔，不能支撑“多重试一次”的全局规则。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage874_stage863_second_retry_feasibility_audit_report_stage874_stage863_second_retry_feasibility_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage874_stage863_second_retry_feasibility_audit_summary_stage874_stage863_second_retry_feasibility_audit_v1.csv`
- event_audit：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage874_stage863_second_retry_feasibility_audit_event_audit_stage874_stage863_second_retry_feasibility_audit_v1.csv`
- yearly：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage874_stage863_second_retry_feasibility_audit_yearly_stage874_stage863_second_retry_feasibility_audit_v1.csv`
- summary_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage874_stage863_second_retry_feasibility_audit_summary_chart_stage874_stage863_second_retry_feasibility_audit_v1.png`
- atlas_manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage874_stage863_second_retry_feasibility_audit_atlas_manifest_stage874_stage863_second_retry_feasibility_audit_v1.csv`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage874_stage863_second_retry_feasibility_audit_atlas_page001_stage874_stage863_second_retry_feasibility_audit_v1.png`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage874_stage863_second_retry_feasibility_audit_atlas_page002_stage874_stage863_second_retry_feasibility_audit_v1.png`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage874_stage863_second_retry_feasibility_audit_atlas_page003_stage874_stage863_second_retry_feasibility_audit_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage874_stage863_second_retry_feasibility_audit_decision_stage874_stage863_second_retry_feasibility_audit_v1.json`

## 结论

- 本阶段结论：二次重试不进入真实引擎。C9 一次重试失败后，同日第二次 reclaim 样本少，且 `7/9` 随后再次触发同一 `0.5R` stop；这不是“可多次尝试”的强证据，而是 whipsaw 成本继续堆叠。
- 是否进入下一步：否，不接 Stage875 二次重试引擎。
- 下一步：停止重试次数分支，不扫 `2/3` 次、等待分钟数、R 小数、品种、方向或年份。若继续本线，只能转向不直接截断右尾、也不增加 whipsaw 的账户/持仓层生存问题，或暂停等待新的低自由度外生信息。

## 过拟合反思

- 运行前判断：否。只做 C9 已发生 retry_failed 事件后的自然同日路径审计，不改变策略、不扫参数。
- 运行后判断：否；但如果继续把二次重试接引擎或改成不同等待时间/次数，就会变成过拟合。
- 原因：样本总量 `25`，二次 reclaim 只有 `9`，其中多数再次失败；继续细分到年份、品种、方向或时段会依赖极少数路径。

## 继续价值反思

- 运行前判断：有有限价值。原始目标允许“可以多次尝试”，需要确认 C9 一次重试是否太保守。
- 运行后判断：二次重试分支没有继续价值；研究线整体仍有有限价值，但应回到账户/持仓层风险，而不是增加入场日 whipsaw 次数。
- 原因：实时止损纪律要求第二次失败必须真实记亏，不能用后验 EOD 反弹忽略 stop；保守 proxy 已为负。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage050/Stage874 结论。
- 是否更新 `research/registry.md`：否，本阶段不是正式候选、重要突破或路线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是本线内反证，不属于重要合入摘要。
