# Stage146 TqBacktest分钟线执行代理抽取

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-28 04:08 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：执行代理分钟线抽取；不新增策略、不修改交易规则
- 是否重要突破：否；但重要地解除“完全没有分钟线”的阻断
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：TqSdk 回测文档说明 `TqBacktest` 可进入历史回放模式；`get_kline_serial(duration_seconds=60)` 可取得1分钟K。
- 我的判断：虽然 DataDownloader 专业版下载被阻断，但 TqBacktest 可以按目标时间段回放分钟K；因此下一步可以构造局部执行代理价，不必停在“缺数据”。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage446_tqsdk_backtest_minute_proxy_extract.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`STAGE446_MAX_SYMBOLS=5`、`STAGE446_MAX_SECONDS_PER_SYMBOL=180`、窗口前后 padding `10` 分钟
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage144/145 高优先级前5个合约的目标窗口范围
- 账户规模：不适用
- 成本口径：不适用
- 样本过滤：按高优先级排序取前5个合约，含 `MA605.CZCE`、`jm2509.DCE`、`fu2209.SHFE`、`fu2503.SHFE`、`rb2605.SHFE`
- 策略/归因口径：用 `TqBacktest + get_kline_serial(60)` 抽取 `14:55/21:00/09:00` 等代理窗口分钟K

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：目标窗口 `60`
- 胜率：不适用
- 其他关键指标：
  - 决策标签：`priority_proxy_windows_partially_covered_need_calendar_session_mapping`
  - 抽取合约数：`5`
  - 成功抽取合约数：`5`
  - 失败/超时合约数：`0`
  - 抽取分钟K数量：`28,455`
  - 覆盖目标窗口：`35 / 60`
  - 覆盖率：`58.3333%`
  - `same_day_close_last_5m` 覆盖率：`12 / 12 = 100%`
  - `night_session_open_2100_2105` 覆盖率：`12 / 12 = 100%`
  - `day_session_open_0900_0905` 覆盖率：`11 / 12 = 91.6667%`
  - `day_session_auction_0855_0900` 与 `night_auction_2055_2100` 覆盖率均为 `0%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage446_tqsdk_backtest_minute_proxy_extract_report_stage446_tqsdk_backtest_minute_proxy_extract_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage446_tqsdk_backtest_minute_proxy_extract_coverage_summary_stage446_tqsdk_backtest_minute_proxy_extract_v1.csv`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage446_tqsdk_backtest_minute_proxy_extract_priority_window_coverage_stage446_tqsdk_backtest_minute_proxy_extract_v1.csv`
- daily：不适用
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage446_tqsdk_backtest_minute_proxy_extract_decision_stage446_tqsdk_backtest_minute_proxy_extract_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage446_tqsdk_backtest_minute_proxy_extract_proxy_prices_stage446_tqsdk_backtest_minute_proxy_extract_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage446_tqsdk_backtest_minute_proxy_extract_minute_bars_stage446_tqsdk_backtest_minute_proxy_extract_v1.csv`

## 结论

- 本阶段结论：分钟线代理价可以通过 TqBacktest 获取；可用代理窗口应优先从 `14:55最后5分钟`、`21:00开盘5分钟`、`09:00开盘5分钟` 中选择，暂不依赖 `08:55/20:55` 集合竞价窗口。
- 是否进入下一步：是。
- 下一步：将代理价接回 Stage443 订单 ledger，量化日线代理价与分钟会话价错位。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：只抽取执行数据，覆盖失败不用于删除日期或品种。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：分钟K已经可取得，继续做执行路径重建比继续调策略参数更有价值。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；不追加 `memory.md`。
