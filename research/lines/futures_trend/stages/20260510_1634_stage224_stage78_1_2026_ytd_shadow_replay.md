# Stage224 Stage78-1 2026年初至今影子盘回放

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-10 16:34
- 阶段性质：78-1影子盘冷启动回放
- 是否重要突破：否
- 是否触发A/B：否，本阶段固定78-1口径，不引入新策略

## 调研与判断

- 外部调研结论：影子盘回放应明确初始资金、起止日期、交易口径、是否真实报单、信号计划和风险闸门；不能只给期末收益。
- 我的判断：本阶段不是优化，不应根据2026弱表现调参数；它的价值在于确认若年初用78-1启动，到本地最新数据日的资金、回撤、目标日信号和风控状态。

## 口径

- 版本：`78-1`
- 官方版本：`official_stage78_1_defensive_50w_no_sizing_cap`
- 初始资金：`500,000`
- sizing资金封顶：`0.0`
- 分析起点：`2026-01-01`
- 本地最新数据日：`2026-04-30`
- 预热起点：`2025-01-01`
- 执行模型：同日收盘撮合
- AI选品：开启
- 真实报单：`false`

## 运行过程

- 首次运行发现入口兼容bug：
  - `run_backtest()` 向 `build_backtest_engine()` 传入 `backtest_end`
  - 但 `build_backtest_engine()` 签名缺少 `backtest_end`
- 修复：
  - `examples/portfolio_backtesting/run_qmt_roll_backtest.py`
  - 在 `build_backtest_engine()` 签名中恢复 `backtest_end: datetime = END_DT`
- 验证：
  - `py_compile` 通过
  - 重新运行78-1年初至今影子回放成功

## 回测结果

| 指标 | 数值 |
| --- | ---: |
| 期末权益 | 450,540 |
| 总收益 | -9.8920% |
| 最大回撤 | -28.5861% |
| Sharpe | -0.6975 |
| 总滑点 | 4,660 |
| 总交易次数 | 27 |
| 胜率 | 16.6667% |

## 目标日风控

- 目标日：`2026-04-30`
- 风险级别：`watch`
- 允许影子盘记录：`1`
- 允许真实新增开仓：`1`
- 触发原因：`drawdown_watch`
- 当前回撤：`24.2981%`
- 当日净盈亏：`-2,570`
- 当日亏损现金：`2,570`

## 目标日信号

| vt_symbol | direction | offset | volume | theoretical_price | proxy_quality |
| --- | --- | --- | ---: | ---: | --- |
| MA609.CZCE | Long | Open | 16 | 3,010 | requires_next_trading_session_minute_or_qmt_bar |

## 输出产物

- 总报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage186_stage78_2026_50w_cold_start_report_stage186_stage78_2026_50w_cold_start_v1.md`
- 日报：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage186_stage78_2026_50w_cold_start_daily_report_stage186_stage78_2026_50w_cold_start_v1.md`
- 信号计划：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage186_stage78_2026_50w_cold_start_signal_plan_stage186_stage78_2026_50w_cold_start_v1.csv`
- 汇总JSON：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage186_stage78_2026_50w_cold_start_summary_stage186_stage78_2026_50w_cold_start_v1.json`
- 日度曲线：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage186_stage78_2026_50w_cold_start_20260101_50w_to_20260430_daily.csv`
- 交易明细：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage186_stage78_2026_50w_cold_start_20260101_50w_to_20260430_trades_2020_2026_04.csv`

## 过拟合反思

- 运行前判断：否。固定78-1口径，只做年初冷启动回放。
- 运行后判断：否。没有根据2026弱表现修改参数。
- 注意：不能因为2026年初至今亏损就临时加入过滤条件，否则容易过拟合近期弱窗口。

## 继续价值反思

- 运行前判断：有价值。该结果直接对应当前50万影子盘资金边界。
- 运行后判断：有价值。当前年初冷启动仍处于回撤压力带，适合继续影子盘观察，并补T+1代理价/分钟线验证。

## TODO

- 补目标日 `MA609.CZCE` 的下一交易时段分钟线或QMT真实行情代理价。
- 用78-1继续跑T+1、滑点压力、Monte Carlo三件套。
- 复核2026信号质量与当前回撤来源，但不要直接调参。
