# Stage811 Stage804 盈利趋势确认 long heat 半仓滚动三年验证

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：2026-06-11 21:59 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：研究验证、滚动三年多周期回测
- 是否重要突破：否。本阶段反证了“5%浮盈 + MA20/MA40趋势确认才半平”的具体定义。
- 是否触发A/B：读取并遵循 `skills/version-ab-experiment/SKILL.md`；本阶段不接正式 A/B，只做 Stage804/806/810 对照验证。

## 外部调研与判断

- 参考资料：
  - Graham Capital trend-following primer：趋势跟随常用 moving average 与 breakout 模型作为趋势识别基础。
  - TradersPost pyramiding guide：加仓/保留仓位应建立在原始交易已经盈利且趋势仍被确认的基础上。
  - ReturnStacked managed futures trend following：管理期货趋势策略的收益来自长期趋势延续和跨市场风险管理。
  - SSRN trend-following practical guide：趋势跟随具有右偏收益，但要通过稳健的仓位和风控穿越不同市场环境。
- 我的判断：Stage810 的无条件半平过松，本阶段用“已有盈利 + 当前趋势确认”约束半平是合理的第一性方向；但不能为 2025 年某次 jm 走势临时改阈值，所以本次只用预声明 `5%` 浮盈与 `MA20/MA40` 趋势确认，不扫参数。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage811_stage804_long_heat_profit_trend_half_rolling3y.py`
- 修改脚本：同上脚本从 v1 修正到 v2。
- 删除脚本：无。
- 新增参数：
  - `long_heat_profit_trend_min_profit_pct=0.05`
  - `long_heat_profit_trend_ma_fast=20`
  - `long_heat_profit_trend_ma_slow=40`
  - `long_heat_profit_trend_slope_days=3`
- 修改参数：
  - 基础为 Stage804：Stage777 + 多头更紧初始止损。
  - long heat 触发时，只有同时满足 `close > avg_entry_price`、历史最大浮盈 `>=5%`、`close > MA20 > MA40`、`MA20 > 3天前MA20`，才调用 Stage810 的单次半平。
  - 不满足则回到 Stage804 原逻辑，平掉 heat 层。
  - 空头 heat 不改。
  - v1 曾错误要求 `MA40 + slope_days` 历史长度，AM41 下导致趋势条件不可达；已在 v2 修正为 `need=max(MA40, MA20+slope_days)`。
- 删除参数：无。

## 回测/归因参数

- 数据区间：完整三年滚动窗口，起点 `2018-01` 到 `2023-05`，共 `65` 个窗口；每个窗口结束日为 `start + 3 years - 1 day`。
- 账户规模：沿用 Stage804/Stage777 研究口径，初始资金 `500,000`。
- 成本口径：沿用现有回测成本、滑点和合约乘数口径。
- 样本过滤：只统计完整三年窗口。
- 策略/归因口径：
  - AM41、旧正式 AI 老师、OI 命中恢复风险资金到 `0.8`、不命中基础等效 `0.4`。
  - 关闭连败缩放和 recovery sleeve。
  - 本阶段只改多头 heat 全平/半平的选择规则。

## 结果

- 期末权益：窗口期末权益中位数 `3,873,970`（由收益中位 `774.794%` 对应 `500,000` 起算）
- 总收益：收益中位数 `774.794%`；p10 `90.9892%`；最小 `54.172%`；最大 `2678.298%`
- 最大回撤：回撤中位数 `-36.2093%`；最差 `-56.6470%`
- Sharpe：中位数 `1.7623`；p10 `0.8437`
- 总滑点：窗口滑点中位数 `182,240`
- 总交易次数：合计 `17,493`；窗口中位 `285`
- 胜率：沿用 rolling 报表口径未单列；与 Stage804 几乎一致。
- 其他关键指标：
  - 正收益窗口 `65/65`
  - DD30 失败 `51/65`
  - DD40 失败 `24/65`
  - DD50 失败 `6/65`
  - DD60 失败 `0/65`
  - 多头 heat 半平仓仅触发 `3` 次，合计减仓 `274` 手。
  - 多头 heat 全平触发 `409` 次，合计平仓 `39,918` 手。
  - 空头 heat 平仓触发 `48` 次。
  - vs Stage804：收益胜出 `4/65`、回撤胜出 `1/65`，收益中位差 `0.0pp`、回撤中位差 `0.0pp`；真实差异只有 `3` 个窗口，且全部收益不如 Stage804。
  - vs Stage810：收益胜出 `48/65`、回撤胜出 `44/65`，收益中位差 `+78.31pp`、回撤中位差 `+1.0774pp`；说明条件半平比无条件半平稳健，但基本退回 Stage804。
  - vs Stage806：收益胜出 `48/65`、回撤胜出 `46/65`，收益中位差 `+82.046pp`、回撤中位差 `+4.2500pp`。
  - 触发层审计：代表窗口 `2023-02`、`2021-01`、`2020-04` 中，heat 触发时 `MA20/MA40` 趋势多数通过，但 `max_profit_pct>=5%` 一次都没通过；例如 `2025-07-09 jm2509` heat 触发时 `close 871.5`、均价 `843.5`、最大浮盈约 `3.3195%`，低于 5%。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage811_stage804_long_heat_profit_trend_half_rolling3y_report_stage811_stage804_long_heat_profit_trend_half_rolling3y_v2.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage811_stage804_long_heat_profit_trend_half_rolling3y_summary_stage811_stage804_long_heat_profit_trend_half_rolling3y_v2.csv`
- orders：无单独订单文件；本阶段使用 trade events 统计 heat 全平/半平。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage811_stage804_long_heat_profit_trend_half_rolling3y_curves_stage811_stage804_long_heat_profit_trend_half_rolling3y_v2.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage811_stage804_long_heat_profit_trend_half_rolling3y_comparison_vs_stage804_806_810_stage811_stage804_long_heat_profit_trend_half_rolling3y_v2.csv`
- 图表：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage811_stage804_long_heat_profit_trend_half_rolling3y_return_heatmap_stage811_stage804_long_heat_profit_trend_half_rolling3y_v2.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage811_stage804_long_heat_profit_trend_half_rolling3y_dd_heatmap_stage811_stage804_long_heat_profit_trend_half_rolling3y_v2.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage811_stage804_long_heat_profit_trend_half_rolling3y_selected_equity_curves_stage811_stage804_long_heat_profit_trend_half_rolling3y_v2.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage811_stage804_long_heat_profit_trend_half_rolling3y_return_delta_vs_stage804_heatmap_stage811_stage804_long_heat_profit_trend_half_rolling3y_v2.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage811_stage804_long_heat_profit_trend_half_rolling3y_return_delta_vs_stage810_heatmap_stage811_stage804_long_heat_profit_trend_half_rolling3y_v2.png`

## 结论

- 本阶段结论：Stage811 不升级。当前定义过严，真正想保护的 2025 趋势右尾在 heat 触发时还没有达到 `5%` 最大浮盈，因此没有被保护；少数触发半平的窗口反而损害收益。
- 是否进入下一步：不沿着 Stage811 原定义继续推广，也不直接扫 `3%/4%/5%`。
- 下一步：如果继续，应把“已有盈利”从固定 `5%` 改为更贴近风险单位的定义，例如 `>= 1R`、`>= 初始止损距离`、或 `盈利超过当前 heat 层风险距离`；这比扫百分比更有结构含义。

## 过拟合反思

- 运行前判断：过拟合风险低到中等。低是因为用已有 `5% profit lock + MA20/MA40` 语义；中等是因为动机来自 2025 右尾错杀。
- 运行后判断：本次没有过拟合，但结果说明定义错位；若直接把 `5%` 改成 `3%` 迎合 jm 这笔交易，会有明显过拟合风险。
- 原因：heat 触发时很多多头已经满足趋势确认，但浮盈还浅。右尾真正启动前，百分比浮盈阈值来得太晚。

## 继续价值反思

- 运行前判断：有价值，验证“只保护盈利趋势仓”能否修复 Stage810 的坏尾部释放。
- 运行后判断：Stage811 这个具体版本无继续推广价值；但“盈利趋势仓不应和普通仓同等全平”的方向仍有价值。
- 原因：当前固定百分比阈值没有抓住核心机制。后续必须改成风险单位或持仓结构单位，而不是继续扫固定百分比。

## 合入建议

- 是否更新本线 `LINE.md`：否，暂不改变研究线主状态。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 摘要；不追加 `memory.md`。
