# 2026-05-15 00:09 Stage003 盈利锁定低自由度候选搜索

## 基本信息

- 当前模式：`night`
- 所属研究线：`futures_trend_profit_lock_exit`
- 策略基准：Stage78-1 `official_stage78_1_defensive_50w_no_sizing_cap`
- 资金口径：50万
- 是否重要突破：否，但发现一个可进入引擎反证的候选族。

## 外部调研与判断

- 调研关键词：`walk-forward optimization trading GitHub`、`purged cross validation financial machine learning`、`profit trailing stop optimization overfitting`、`White reality check trading strategy overfitting`。
- 判断结论：盈利锁定参数最容易被路径噪声污染，不能用单一全样本最优替换正式参数；应使用低自由度候选、walk-forward、bootstrap/重采样和最终引擎级反证。
- 本阶段采用低自由度族：整体缩放、统一保留比例、两段式保留、平滑 log 保留、少数 trigger set，不做 6 档独立网格。

## 新增/修改

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage273_profit_lock_effectiveness_and_search.py`
- 修改正式参数：无。
- 新增参数：无，复用 Stage272 已加入的实验入口 `profit_lock_tiers`。
- 删除参数：无。

## 实验设计

- 候选数：`141`
- bootstrap 轮数：`240`
- 输入：Stage78-1 实际交易腿 + vn.py 日线 bar。
- 规则复刻：按收盘最大浮盈触发锁盈层；按收盘价跌破/升破锁盈价触发退出。
- 判定：事件级收益、年度/起始年一致性、walk-forward、bootstrap OOS 方向。

## 新增结果

- 事件级 robust-best：`scale_current_1.65`
- 档位：`30%->29.4% / 20%->19.6% / 10%->9.8% / 5%->4.9% / 3%->1.65% / 2%->0.16%`
- weighted_delta_sum：`58.91`
- start_year_win_count：`6`
- min_year_delta_sum：`-3.42`
- walk-forward positive_count：`2/4`
- bootstrap positive_rate：`55.83%`
- 结论：事件级最优不够稳，不能直接晋级正式。

正式层级有效性复查：

- `2%->0.1%`：触发多，但唯一正贡献弱。
- `3%->1%`：触发多，但没有明确正贡献。
- `5%->3%` 与 `10%->8%`：有真实止盈保护贡献，是当前手工分层里最“像在工作”的部分。
- `20%->15%`：样本少，机械上起作用，但统计置信不够。
- `30%->20%`：曾达到但未观察到独立 stop-hit 正贡献，更像尾部保护层。

## 过拟合反思

- 运行前判断：如果逐档找最优，会过拟合。
- 运行后判断：Stage273 本身不是过拟合，但事件级最优 `scale_current_1.65` 有过拟合嫌疑。
- 原因：虽然样本内收益最好，但 walk-forward 和 bootstrap 都不强，不能穿越样本外闸门。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但只能推进到引擎反证。
- 原因：事件级搜索找到候选结构，但必须让组合引擎、冷启动和滑点压力来决定是否继续。

## 输出文件

- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage273_profit_lock_effectiveness_search_report_stage273_profit_lock_effectiveness_search_v1.md`
- candidate_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage273_profit_lock_effectiveness_search_candidate_summary_stage273_profit_lock_effectiveness_search_v1.csv`
- tier_effectiveness：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage273_profit_lock_effectiveness_search_tier_effectiveness_stage273_profit_lock_effectiveness_search_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage273_profit_lock_effectiveness_search_decision_stage273_profit_lock_effectiveness_search_v1.json`
