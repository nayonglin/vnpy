# Stage147 分钟代理价与日线账本错位审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-28 04:10 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：执行代理价账本校准；不新增策略、不修改交易规则
- 是否重要突破：是，确认日线 `same_day_close/next_open` 不能作为真实会话可成交价代理
- 是否触发A/B：否；这是执行口径审计

## 外部调研与判断

- 参考资料：执行回测需要区分信号价格、可成交价格、日线合成价格；TqSdk 的 `TqBacktest` 分钟K回放为本阶段提供了目标窗口可观测价格。
- 我的判断：Stage141-143 看到的 T+1 回撤失真并不只是 “next open 更差”；Stage147 显示日线 close/open 与真实会话分钟价有系统性错位，必须先重建执行路径。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage447_proxy_price_ledger_mismatch.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增错位阈值审计为 `20 * price_tick`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage146 前5个高优先级合约覆盖到的 `12` 笔订单
- 账户规模：沿用 Stage079/Stage103 账本口径；本阶段只做订单级价格校准
- 成本口径：不新增成本
- 样本过滤：只使用 Stage146 已抽取成功的目标窗口，不按收益结果筛选
- 策略/归因口径：
  - 比较日线 `same_day_close` 与分钟 `same_day_close_last_5m` vwap-like
  - 比较日线 `next_open` 与优先真实开盘代理价：夜盘品种优先 `21:00` first open，否则 `09:00` first open
  - 按订单方向/开平仓估算相对日线同日 close 的执行现金影响

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：样本订单 `12`
- 胜率：不适用
- 其他关键指标：
  - 决策标签：`daily_bar_proxy_mismatch_requires_session_rebuild`
  - 14:55代理价相对日线同日 close 的大错位笔数：`11 / 12`
  - 真实开盘代理价相对日线 next_open 的大错位笔数：`10 / 12`
  - 最大 14:55 vs 日线同日 close 绝对价差：`440.2000`
  - 最大真实开盘 vs 日线 next_open 绝对价差：`473.0000`
  - `same_last5_abs_minus_same_close`：均值 `89.7000`，中位 `36.1000`，P95 `305.8900`
  - `preferred_real_open_abs_minus_daily_next_open`：均值 `96.7500`，中位 `32.0000`，P95 `335.5000`
  - 样本中最大错位：`BACKTESTING.752 / MA605.CZCE / Long Open`，日线 same close `3122.0`，14:55 vwap-like `3562.2`，21:00 first open `3560.0`，日线 next_open `3087.0`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage447_proxy_price_ledger_mismatch_report_stage447_proxy_price_ledger_mismatch_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage447_proxy_price_ledger_mismatch_summary_stage447_proxy_price_ledger_mismatch_v1.csv`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage447_proxy_price_ledger_mismatch_detail_stage447_proxy_price_ledger_mismatch_v1.csv`
- daily：不适用
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage447_proxy_price_ledger_mismatch_decision_stage447_proxy_price_ledger_mismatch_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage447_proxy_price_ledger_mismatch_largest_mismatches_stage447_proxy_price_ledger_mismatch_v1.csv`

## 结论

- 本阶段结论：Stage103 不能真实晋级 paper；Stage079/Stage103 的同日收盘口径和 T+1日线 open 口径都不能直接视为真实会话可执行口径。
- 是否进入下一步：是，但下一步必须是分钟线会话执行路径重建，不是继续优化 3/6个月指标或救小参数。
- 下一步：
  1. 基于分钟K定义可执行代理：`14:55最后5分钟`、`21:00开盘5分钟`、`09:00开盘5分钟`。
  2. 对全量 Stage443 订单逐步抽取分钟K并重放 ledger。
  3. 若全量分钟执行路径仍保持 <30% 回撤，再重新评估 Stage103 paper 晋级；否则 Stage103 只能保留研究候选。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：只比较价格口径，不因为错位去过滤坏日期/坏品种。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：错位规模足够大，继续修执行模型比继续优化策略参数更有价值。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；不追加 `memory.md`。
