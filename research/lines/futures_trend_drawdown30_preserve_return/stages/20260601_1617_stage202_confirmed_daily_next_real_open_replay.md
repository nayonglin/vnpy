# Stage202 完整日K确认后下一真实窗口回放

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-01 16:17 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：真实可成交日线基准；不新增策略、不修改 Stage079/C3 交易规则
- 是否重要突破：是。它给出“完整日K信号 + 全订单下一真实窗口成交”的无偏基准边界
- 是否触发A/B：否。本阶段是执行口径审计，不是新策略候选

## 外部调研与判断

- 参考资料：
  - Backtrader Orders：https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/
  - QuantConnect Understanding Time：https://www.quantconnect.com/docs/v1/key-concepts/understanding-time
  - Kim, Tse, Wald, Time series momentum and volatility scaling：https://doi.org/10.1016/j.finmar.2016.05.003
- 我的判断：
  - 已完成日K信号只能在后续可用价格点成交，这是事件驱动回测的底线。
  - 趋势跟随里风险预算/波动目标化是合理方向，但必须用低自由度结构，不能按坏窗口调小数。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage502_confirmed_daily_next_real_open_replay.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `NEXT_REAL_VARIANT=stage079_confirmed_daily_all_orders_next_real_open`
  - 所有订单统一在下一真实窗口成交：夜盘品种优先 `21:00-21:05 first_open`，否则次日 `09:00-09:05 first_open`
  - 账户口径：`50万C3下单 + 11.5万外部现金`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30
- 账户规模：`615,000`
- 策略规则、品种池、AI池、入场/出场逻辑：不变
- 成本口径：沿用 C3/Stage079 原始手续费、滑点、合约乘数、保证金设置；另做 `1x/2x/3x/5x` 滑点压力
- 样本过滤：无日期、品种、坏窗口过滤

## 结果

- Stage079 baseline：
  - 期末权益：`31,040,650`
  - 总收益：`4947.2602%`
  - 最大回撤：`-29.7007%`
  - Sharpe：`1.3188`
  - Ulcer：`15.0874`
  - 总滑点：`1,556,750`
  - 总交易次数：`757`
  - 非零日胜率：`48.3478%`
- Stage202 下一真实窗口基准：
  - 期末权益：`32,220,595`
  - 总收益：`5139.1211%`
  - 相对 Stage079 收益保留：`103.8781%`
  - 最大回撤：`-52.7518%`
  - Sharpe：`1.2077`
  - Ulcer：`19.3997`
  - 总滑点：`1,997,870`
  - 总交易次数：`781`
  - 非零日胜率：`51.0407%`
  - 下一真实窗口成交：`781` 笔
  - fallback：`54` 笔
- 3个月体验：
  - Stage079：p05 `-11.4702%`，中位 `13.5434%`，DD30破例 `0.0000%`
  - Stage202：p05 `-15.7853%`，中位 `14.4324%`，DD30破例 `10.8960%`
- 6个月体验：
  - Stage079：p05 `-2.0393%`，中位 `33.9947%`，DD30破例 `0.0000%`
  - Stage202：p05 `-8.1560%`，中位 `30.0993%`，DD30破例 `22.0084%`
- 成本压力：
  - `1x` 最大回撤 `-52.7518%`
  - `2x` 最大回撤 `-57.1061%`
  - `3x` 最大回撤 `-61.8130%`
  - `5x` 最大回撤 `-72.4713%`

## 图表视觉复盘

- 图上 Stage202 不是收益失效，而是路径风险失控：最终 NAV 略高于 Stage079，但 underwater 在 `2021-09` 到 `2022-02` 深穿 `-50%`。
- `2025` 也出现明显二次深水区，说明问题不是一笔 fallback 或单日异常，而是下一真实窗口后的趋势反转暴露会把复利账户打穿。
- 视觉结论与指标一致：收益保留过关，DD40 明确不过关；下一步应做风险预算，而不是回到同 bar 执行语义。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage502_confirmed_daily_next_real_open_replay_report_stage502_confirmed_daily_next_real_open_replay_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage502_confirmed_daily_next_real_open_replay_summary_stage502_confirmed_daily_next_real_open_replay_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage502_confirmed_daily_next_real_open_replay_daily_stage502_confirmed_daily_next_real_open_replay_v1.csv`
- trade usage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage502_confirmed_daily_next_real_open_replay_trade_usage_stage502_confirmed_daily_next_real_open_replay_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage502_confirmed_daily_next_real_open_replay_chart_stage502_confirmed_daily_next_real_open_replay_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage502_confirmed_daily_next_real_open_replay_decision_stage502_confirmed_daily_next_real_open_replay_v1.json`

## 结论

- 决策：`confirmed_daily_next_real_open_baseline_fails_need_risk_structure`。
- Stage202 保住了收益，但最大回撤 `-52.7518%`，不满足目标。
- 是否进入下一步：是，作为真实可成交基准继续；但不作为候选晋级。
- 下一步：在同一真实执行口径下测试低自由度风险预算/风险状态结构，并优先清理 fallback。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但不能按坏窗口补丁救。
- 原因：本阶段只建立无偏执行基准，不调策略参数、不筛日期、不筛品种。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：它证明 Stage079 的 alpha 在下一真实窗口仍存在，主要缺口是暴露和路径风险；这值得继续用更稳健的风险结构尝试。

## TODO

- 补 Stage203 固定风险预算前沿。
- 对最佳 DD40 边界版本做 fallback 来源审计。
- 若 fallback 无法清零，不得把该版本视为“真实交易不存在偏差”的最终候选。
