# 2026-05-15 00:12 Stage006 盈利锁定 D 候选逐笔归因与冻结审查

## 基本信息

- 当前模式：`night`
- 所属研究线：`futures_trend_profit_lock_exit`
- 策略基准：Stage78-1 `official_stage78_1_defensive_50w_no_sizing_cap`
- 资金口径：50万
- 是否重要突破：是，形成最终防过拟合结论：D 有强研究线索，但不替换正式 78-1。

## 新增/修改

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage276_profit_lock_trade_drilldown.py`
- 修改正式参数：无。
- 删除参数：无。

## 审查设计

- 不再搜索参数。
- 使用 Stage273 事件级交易腿，比较 D 与当前 official 在同一真实交易路径上的逐笔差异。
- 使用 Stage275 作为引擎级稳定性背景。
- 重点检查：年份集中度、品种集中度、正贡献集中度、锁盈层贡献。

## 新增结果

D 候选事件级：

- trade_legs：`444`
- stop_hit_rate：`17.79%`
- early_exit_rate：`2.93%`
- weighted_delta_sum：`19.12`
- year_win_count：`6`
- start_year_win_count：`6`
- min_year_delta_sum：`0`

集中度：

- 正贡献交易腿：`10`
- 负贡献交易腿：`2`
- flat 交易腿：`432`
- top10 positive share：`100%`
- top5 positive share：`93.93%`
- top3 product positive share：`90.45%`
- 主要正贡献品种：`lc.GFEX`、`fu.SHFE`、`SM.CZCE`

按 D 触发层：

- `10%->9%`：weighted_delta_sum `14.03`，主贡献层。
- `2%->0.6%`：weighted_delta_sum `3.21`，有正贡献但样本少。
- `20%->18%`：weighted_delta_sum `1.88`，样本很少。
- `3%->0.9%`、`5%->1.5%`、`30%->27%`：本次事件级没有净贡献。

最终判定：

- `pass_stage276`: `false`
- `promotion_decision`: `hold_no_promotion`
- `next_step`: `keep_stage78_1_formal`

## 结论

- 当前每一层在代码机制上都能起作用；但统计上，真正有较明确贡献的是 `5/10` 当前档，以及 D 候选里的 `10%->9%`。
- D 是目前找到的“最强研究候选”，但不够分散，正贡献集中于 10 笔交易和少数品种，不能直接说它是可实盘替换的最优参数。
- 正式 Stage78-1 继续保持当前手工档位。
- 后续如果继续，只能做机制级自适应锁盈，例如按趋势强度/波动率调整锁盈斜率，而不是继续微调这 6 个固定数字。

## 过拟合反思

- 运行前判断：有必要防过拟合。
- 运行后判断：D 有明显过拟合风险，不能 promotion。
- 原因：虽然多周期和滑点压力很好，但逐笔正贡献高度集中；这可能是路径偶然，而不是稳定规律。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但当前固定档位搜索应停止。
- 原因：研究已经回答了用户问题：层级确实在机制上起作用，D 是统计候选但不过最终闸门；继续扫固定档位会进入过拟合。

## 输出文件

- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage276_profit_lock_trade_drilldown_report_stage276_profit_lock_trade_drilldown_v1.md`
- leg_delta：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage276_profit_lock_trade_drilldown_leg_delta_stage276_profit_lock_trade_drilldown_v1.csv`
- by_year：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage276_profit_lock_trade_drilldown_by_year_stage276_profit_lock_trade_drilldown_v1.csv`
- by_product：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage276_profit_lock_trade_drilldown_by_product_stage276_profit_lock_trade_drilldown_v1.csv`
- by_tier：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage276_profit_lock_trade_drilldown_by_tier_stage276_profit_lock_trade_drilldown_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage276_profit_lock_trade_drilldown_decision_stage276_profit_lock_trade_drilldown_v1.json`
