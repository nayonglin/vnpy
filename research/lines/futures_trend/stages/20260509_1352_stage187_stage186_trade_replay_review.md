# Stage187 Stage186冷启动交易复盘

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-09 13:52 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：交易复盘 / 影子盘解释层
- 是否重要突破：否
- 是否触发A/B：否。本阶段不修改策略参数，只复盘 Stage186 交易。

## 外部调研与判断

- 参考资料：
  - VeighNa/vn.py 回测资料显示回测流程包含加载历史数据、运行回测、计算日度盈亏和统计指标。
  - vn.py portfolio backtesting 示例显示组合回测支持多标的、多合约参数和 `capital` 初始资金。
- 我的判断：
  - 本次复盘应以 Stage186 的 30万冷启动口径为主。
  - HTML 看板适合交互查看，但仍需补一份 Markdown 摘要帮助快速判断交易伤害来源。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage186_stage78_2026_30w_cold_start_20260101_30w_to_20260508_trade_replay_review.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage186_stage78_2026_30w_cold_start_20260101_30w_to_20260508_round_trip_review.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage186_stage78_2026_30w_cold_start_20260101_30w_to_20260508_open_position_review.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage186_stage78_2026_30w_cold_start_20260101_30w_to_20260508_monthly_review.csv`

## 回测/归因参数

- 数据区间：2026-01-01 至 2026-05-08
- 账户规模：300,000
- 成本口径：沿用 Stage186 日度净值和滑点口径
- 样本过滤：第78正式趋势策略，30万冷启动
- 策略/归因口径：成交配对复盘，按开平仓 FIFO 估算闭合回合毛盈亏

## 结果

- 期末权益：281,890
- 总收益：-6.04%
- 最大回撤：-21.05%
- Sharpe：-0.448
- 总滑点：2,285
- 总交易次数：23
- 胜率：9.09%
- 其他关键指标：
  - 已闭合交易回合：11
  - 已闭合交易毛盈亏合计：-39,740
  - 日度净盈亏合计：-18,110
  - 当前未平仓：`si2609.GFEX` Long 1手
  - 最大伤害月份：2026-02，净盈亏 -52,600

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage186_stage78_2026_30w_cold_start_20260101_30w_to_20260508_trade_replay_review.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage186_stage78_2026_30w_cold_start_20260101_30w_to_20260508_monthly_review.csv`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage186_stage78_2026_30w_cold_start_20260101_30w_to_20260508_trades_2020_2026_04.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage186_stage78_2026_30w_cold_start_20260101_30w_to_20260508_daily.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage186_stage78_2026_30w_cold_start_20260101_30w_to_20260508_trade_review.html`

## 结论

- 本阶段结论：
  - 今年冷启动回放的主要亏损集中在 2月初的多头止损兑现，而不是 5月8日的 `si2609` 新信号。
  - 当前 30万冷启动口径下只有 1手 `si2609` 持仓，实盘影子盘不应参考全周期继承状态下的 44手规模。
- 是否进入下一步：是
- 下一步：
  - 每日影子盘继续以 Stage186 冷启动为主口径。
  - 加入 T+1 开盘/日盘开盘代理成交价复核。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：本阶段只解释固定策略的历史回放交易，没有调参、删品种或挑信号。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：复盘明确了亏损来源和当前真实持仓，有助于后续影子盘和实盘前风险判断。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
