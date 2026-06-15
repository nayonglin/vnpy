# Stage028 Stage852 Stage851后路线复盘与分钟K覆盖缺口审计

## 基本信息

- 改动时间：2026-06-15 00:18 CST。
- 所属研究线：`futures_trend_stage819_intraday_rules`。
- 阶段性质：只读路线复盘与数据覆盖审计。
- 是否重要突破：否。
- 是否触发 A/B：否。本阶段没有新策略候选，也没有可接入正式版的规则。
- 是否修改正式版：否。
- 是否连接 CTP/SimNow：否。
- 是否调用下单：否。
- 决策标签：`stage852_route_review_no_new_rule_until_minute_coverage_or_new_first_principle`。

## 外部/GitHub调研

- CME futures order types 说明 stop order 是触发后进入市场的条件订单；这支持“日内错误必须实时止损”的工程语义，但也提醒止损执行会受触发价、流动性和滑点影响，不能把分钟K里的止损价当成无成本确定成交。
- CFTC stop-loss order 投资者教育材料同样强调 stop-loss 不能保证成交在 stop price，本线后续若做真实分钟引擎必须继续做成本/滑点压力。
- vn.py / VeighNa GitHub 提供 CTA 策略、K线聚合和交易接口生态；本阶段只把它作为实现框架背景，不引用外部策略逻辑，也不引入 AI。
- 调研判断：外部资料支持“规则逐根分钟K可判定 + 止损/仓位管理分层 + 真实成本压力”的方向；不支持从 Stage851 的失败结果继续救小数阈值。

参考链接：

- https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/futures-order-types
- https://www.cftc.gov/sites/default/files/Stoploss_final_ada.pdf
- https://github.com/vnpy/vnpy

## 版本改动

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage852_stage851_route_review.py`
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage852_stage851_route_review_summary_stage852_stage851_route_review_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage852_stage851_route_review_coverage_by_year_stage852_stage851_route_review_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage852_stage851_route_review_coverage_by_product_stage852_stage851_route_review_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage852_stage851_route_review_pressure_episode_coverage_stage852_stage851_route_review_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage852_stage851_route_review_route_scoreboard_stage852_stage851_route_review_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage852_stage851_route_review_coverage_gap_chart_stage852_stage851_route_review_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage852_stage851_route_review_report_stage852_stage851_route_review_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage852_stage851_route_review_decision_stage852_stage851_route_review_v1.json`
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 回测结果：无新增回测；只读取 Stage825/849/851 既有输出。
- 期末权益：不适用，本阶段不是回测。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 输入与方法

- 输入 Stage825 全周期逐笔分钟特征：`341` 笔 closed lots。
- 输入 Stage849 压力 episode 分钟特征与 paired lots。
- 输入 Stage851 PDEG-v0 决策 JSON。
- 方法：
  - 重新按逐笔行统计 entry-day minute coverage，而不是只看汇总表。
  - 按 entry year 和 product 统计缺分钟K的 lot 数、缺口 PnL 绝对影响、缺口中的 big winner。
  - 按 Stage849 pressure episode 统计关键日期分钟K覆盖。
  - 汇总 Stage022-027 的路线评分，判断哪些分支已被反证，哪些还需要数据补齐。

## 新增结果

- Stage825 全周期 closed lots：`341`。
- 入场日分钟K覆盖：`227/341 = 66.5689%`。
- 入场日分钟K缺口：`114` 笔。
- 缺口绝对 PnL 影响：`14,948,615`。
- 缺口中的 big winner：`8` 笔。
- 压力段关键日期：`19` 个。
- 压力段关键日期分钟K覆盖：`7/19 = 36.8421%`。
- Stage851 PDEG-v0：
  - entry flag rate：`47.4320%`
  - closed lot flag rate：`50.5405%`
  - pressure pairs flagged：`7/8`
  - flagged big-winner PnL：`24,065,430`

### 年份覆盖

- `2018`：`0/25 = 0%`
- `2019`：`0/45 = 0%`
- `2020`：`63/74 = 85.1351%`
- `2021`：`55/61 = 90.1639%`
- `2022`：`34/45 = 75.5556%`
- `2023`：`25/28 = 89.2857%`
- `2024`：`23/26 = 88.4615%`
- `2025`：`22/25 = 88.0000%`
- `2026`：`5/12 = 41.6667%`

### 产品缺口优先级

按缺分钟K lot 的绝对 PnL 影响排序，优先级靠前：

- `fu.SHFE`：缺 `12` 笔，missing_abs_pnl `2,969,840`，missing_big_winner `1`
- `ru.SHFE`：缺 `10` 笔，missing_abs_pnl `2,899,250`，missing_big_winner `1`
- `hc.SHFE`：缺 `12` 笔，missing_abs_pnl `1,466,330`，missing_big_winner `2`
- `rb.SHFE`：缺 `7` 笔，missing_abs_pnl `1,194,960`，missing_big_winner `1`
- `jm.DCE`：缺 `7` 笔，missing_abs_pnl `1,148,640`
- `FG.CZCE`：缺 `6` 笔，missing_abs_pnl `1,048,140`，missing_big_winner `1`

### 压力段覆盖

- 完整覆盖：
  - `ap_long_20220428_0510`：`3/3`
  - `fu_short_20220622_0629`：`3/3`
- 部分覆盖：
  - `fu_long_20220325_0401`：`1/4`
- 完全缺失：
  - `fg_short_20220524_0602`：`0/3`
  - `fu_long_20220418_0419`：`0/2`
  - `fu_long_20220506_0509`：`0/2`
  - `fu_long_20220527_0531`：`0/2`

## 路线复盘判断

- `entry_day_stop_retry`：Stage022/023 证明 `0.5R realtime stop + original-entry reclaim retry` 有收益/Sharpe 价值，但 C9 相对 C4 最大回撤恶化，不能继续扫 R 倍数或重试次数。
- `opening_range_confirmation`：Stage010 已反证，OR15 过滤左尾但伤害 target_first 右尾。
- `fail_fast_or_structure_break_exit`：Stage016-021 已反证，真实引擎会误杀可恢复右尾或恶化 broker10/Sharpe。
- `post_stop_cooldown_or_reuse_gate`：Stage012/020/021 已反证，止损后释放资金再利用总体并非负贡献，不能做 blanket cooldown。
- `holding_product_direction_survival`：Stage024-027 显示压力段是“同路径更大仓”的问题，但 PDEG-v0 触发面过宽，不能进引擎。
- `minute_visual_evidence`：Stage825/849 已有图谱，但关键压力段覆盖只有 `36.8421%`，不足以支撑新规则。

## 结论

- 本阶段不写新规则、不接引擎。
- PDEG-v0 明确不进入下一步，因为它虽然命中 `7/8` pressure pairs，但也命中约一半 entry rows / closed lots，并覆盖大量右尾。
- 当前最有价值的推进不是策略参数，而是数据工作：
  1. 补 `fu.SHFE/ru.SHFE/hc.SHFE/rb.SHFE/jm.DCE/FG.CZCE` 等缺口产品的入场日分钟K。
  2. 补 Stage849 中 `fu_long` 与 `FG_short` 压力 episode 的关键日期分钟K。
  3. 重画缺口 episode atlas 后，再判断是否存在新的、非阈值救参的第一性规则。
- 如果不补分钟数据，应暂停持仓后 product-direction survival 分支，避免继续过拟合。

## 后续规划和 TODO

- TODO 1：优先做分钟K数据缺口补齐审计，确认当前 `.csv` 源里是缺合约、缺日期，还是字段/时区/合约命名映射问题。
- TODO 2：补齐后先只重跑 Stage825/849 的图谱和覆盖表，不直接写规则。
- TODO 3：只有当补齐后的视觉证据显示通用、实时、低自由度的结构，才进入冻结规则设计；否则暂停本分支。

## 反思

- 运行前过拟合判断：否。本阶段是只读审计，不新增阈值、不修改策略、不选择赢家窗口。
- 运行后过拟合判断：否。结果明确收敛自由度，禁止继续把 PDEG-v0 救成小参数补丁。
- 运行前继续价值判断：有价值。因为 Stage027 已到路线岔路口，需要判断是否继续投入。
- 运行后继续价值判断：有条件有价值。继续价值只在补分钟K覆盖和视觉证据；如果不补数据，继续写规则价值很低。
