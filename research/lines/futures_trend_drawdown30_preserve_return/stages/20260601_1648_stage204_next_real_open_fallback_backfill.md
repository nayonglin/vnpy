# Stage204 下一真实窗口 fallback 补齐复核

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-01 16:48 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：真实可成交证据清理；不新增策略、不修改 Stage079/C3 信号
- 是否重要突破：是。Stage203 `risk060/risk070` 已清零 fallback，固定风险倍率边界变成真实窗口价格证据
- 是否触发A/B：否。清理后仍没有满足 DD40 + 收益保留的最终候选

## 外部调研与判断

- 参考资料：
  - Backtrader Orders：https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/
  - QuantConnect Understanding Time：https://www.quantconnect.com/docs/v1/key-concepts/understanding-time
  - Kim, Tse, Wald, Time series momentum and volatility scaling：https://doi.org/10.1016/j.finmar.2016.05.003
- 我的判断：
  - 真正可部署的候选不能混入 `fallback_daily_next_open`，否则还是日线代理价格。
  - 本阶段只补成交窗口数据，不调参数；若清理后仍不达标，应转向状态风险预算，而不是继续救固定倍率小数。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage504_next_real_open_fallback_backfill.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `RISK_MULTIPLIERS=(0.7, 0.6)`
  - `MAX_ITERATIONS=3`
  - `MAX_SECONDS_PER_SYMBOL=240`
  - 新增 raw 根目录：`examples/portfolio_backtesting/downloaded_futures/tqsdk_stage504_next_real_open_fallback_backfill`
- 修改参数：无
- 删除参数：无

## 回测/补数参数

- 数据区间：2020-01-02 至 2026-04-30
- 账户规模：`615,000`
- 策略规则、品种池、AI池、入场/出场逻辑：不变
- 成交口径：完整日K确认后，所有订单在下一真实窗口成交
- 补数口径：对 Stage203 fallback 成交键补抽 `21:00-21:05 first_open` 与/或 `09:00-09:05 first_open`
- 样本过滤：无日期、品种、坏窗口过滤

## 结果

- 补数：
  - 迭代轮数：`3`
  - 补数合约数：`63`
  - 请求 fallback 窗口：`129`
  - 剩余 fallback：`0`
- `risk060`：
  - 期末权益：`20,036,555`
  - 总收益：`3157.9764%`
  - 相对 Stage079 收益保留：`63.8328%`
  - 最大回撤：`-39.0499%`
  - Sharpe：`1.1786`
  - Ulcer：`16.3184`
  - fallback：`0`
  - 3个月 p05：`-17.2167%`，中位 `12.6636%`，DD30破例 `1.4408%`
  - 6个月 p05：`-7.5695%`，中位 `23.2719%`，DD30破例 `13.2332%`
  - `2x/3x/5x` 成本压力最大回撤：`-41.9536%/-45.0563%/-62.9588%`
- `risk070`：
  - 期末权益：`20,564,350`
  - 总收益：`3243.7967%`
  - 相对 Stage079 收益保留：`65.5675%`
  - 最大回撤：`-42.1055%`
  - Sharpe：`1.1153`
  - Ulcer：`17.6263`
  - fallback：`0`

## 图表视觉复盘

- `risk060` 橙线是真实窗口价格清理后的 DD40 边界，但 NAV 明显低于 Stage079，收益保留不足。
- `risk070` 绿线收益保留过 `65%`，但 2022 初水下穿过 `-40%`，图上不是孤立误差。
- 两条线在 2021-2023 多次贴近或低于 `-30%`，短持有体验仍差；固定风险倍率已经到边界，不值得继续调小数。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage504_next_real_open_fallback_backfill_report_stage504_next_real_open_fallback_backfill_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage504_next_real_open_fallback_backfill_summary_stage504_next_real_open_fallback_backfill_v1.csv`
- frontier：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage504_next_real_open_fallback_backfill_frontier_stage504_next_real_open_fallback_backfill_v1.csv`
- trade usage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage504_next_real_open_fallback_backfill_trade_usage_stage504_next_real_open_fallback_backfill_v1.csv`
- backfill status：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage504_next_real_open_fallback_backfill_backfill_status_stage504_next_real_open_fallback_backfill_v1.csv`
- fallback audit：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage504_next_real_open_fallback_backfill_fallback_audit_stage504_next_real_open_fallback_backfill_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage504_next_real_open_fallback_backfill_chart_stage504_next_real_open_fallback_backfill_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage504_next_real_open_fallback_backfill_decision_stage504_next_real_open_fallback_backfill_v1.json`

## 结论

- 决策：`next_real_fallback_clean_dd40_but_return_retention_short`。
- Stage204 证明 Stage203 的 fallback 不是主要矛盾；清理后 `risk060` 仍只是在 DD40 内保住 `63.8328%` 收益，`risk070` 收益保留够但回撤穿线。
- 不按目标独立判断：不晋级，但保留为真实可成交风险下界。
- 下一步：停止固定倍率小数救线，测试上一日可见状态驱动的低自由度风险预算。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只补成交窗口数据并重跑预声明的 `0.7/0.6` 档，不做日期/品种筛选，也没有调 `0.61/0.62`。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：固定倍率继续价值低，总目标仍有价值。
- 原因：真实边界已明确；下一步必须从“同风险倍率”转为“上一日可见状态下的风险预算”，否则只是在收益和回撤之间机械换挡。

## TODO

- 测试 `risk070/risk080 + 组合回撤状态门控/降仓`，只允许粗阈值。
- 每个新图继续做视觉复盘，特别关注是否只是把 2022 风险挪到 2025。
