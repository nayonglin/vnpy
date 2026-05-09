# Stage170 前向数据缺口检查

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-08 14:45 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：前向数据时效检查；不改策略、不做新回测、不触发A/B
- 是否重要突破：否；这是影子盘数据链路诊断，不是策略收益突破
- 是否触发A/B：否；固定Stage78，不引入新策略版本

## 外部调研与判断

- 参考资料：
  - 交易所2026年劳动节安排：5月1日至5月5日休市，5月6日起照常开市，5月6日晚恢复夜盘。
  - 中金所2026年部分节假日休市安排同样显示劳动节5月6日起照常开市。
  - 大商所/上期所/能源中心相关劳动节交易时间公告均指向同一结论：5月6日不是休市日。
- 我的判断：
  - 用户指出“今天已经是5月7日/5月8日了，为什么没有最新日报”是正确问题。
  - 到2026-05-08，保守按上一完整交易日，Stage169应能生成2026-05-07日报。
  - 当前未生成不是因为策略判断无信号，也不是需要真实下单数据，而是本地前向行情和Stage155/154产物没有更新。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/build_qmt_roll_stage170_forward_data_gap_check.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `--as-of-date`：指定检查日期，默认系统日期
  - `target_latest_complete_trading_day`：as-of日前一完整交易日
  - `EXCHANGE_HOLIDAY_RANGES_2026`：用于识别2026年主要休市段
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：未新增回测
- 账户规模：沿用Stage168 `300000`
- 成本口径：未新增成本回测
- 样本过滤：检查Stage168/154/155和Stage78正式产物的日期时效
- 策略/归因口径：固定Stage78 `official_stage78_defensive_v1`

## 结果

- 期末权益：未新增回测；Stage78参考为`4,600,090`
- 总收益：未新增回测；Stage78参考为`2200.0450%`
- 最大回撤：未新增回测；Stage78参考为`-36.9907%`
- Sharpe：未新增回测；Stage78参考为`1.2919`
- 总滑点：未新增回测；Stage78参考为`260,110`
- 总交易次数：未新增回测；Stage78参考为`779`
- 胜率：未新增回测；本阶段未重新统计
- 其他关键指标：
  - as-of日期：`2026-05-08`
  - 目标最新完整交易日：`2026-05-07`
  - 是否能用本地数据生成目标日报：`false`
  - 缺失交易日数：`9`
  - 缺失交易日：`2026-04-22`、`2026-04-23`、`2026-04-24`、`2026-04-27`、`2026-04-28`、`2026-04-29`、`2026-04-30`、`2026-05-06`、`2026-05-07`
  - `formal_daily`最新日期：`2026-04-21`
  - `stage155_daily_control`最新日期：`2026-04-21`
  - `stage155_historical_intent`最新决策日期：`2026-04-15`
  - 是否需要真实下单数据：`false`
  - 是否需要前向行情数据：`true`
  - 完整对账是否需要QMT只读：`true`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage170_forward_data_gap_check_report_20260508_stage170_forward_data_gap_check_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage170_forward_data_gap_check_summary_20260508_stage170_forward_data_gap_check_v1.json`
- artifact_status：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage170_forward_data_gap_check_artifact_status_20260508_stage170_forward_data_gap_check_v1.csv`
- missing_trading_days：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage170_forward_data_gap_check_missing_trading_days_20260508_stage170_forward_data_gap_check_v1.csv`
- action_plan：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage170_forward_data_gap_check_action_plan_20260508_stage170_forward_data_gap_check_v1.csv`

## 结论

- 本阶段结论：
  - 没有生成2026-05-07日报的直接原因是本地前向数据链断在2026-04-21/2026-04-15，而不是因为5月6日或5月7日不是交易日。
  - 生成信号日报不需要真实下单数据；需要先补前向行情到2026-05-07，并用冻结Stage78生成前向理论信号。
  - 完整对账日报需要QMT只读数据，但仍不需要真实报单。
- 是否进入下一步：是
- 下一步：
  - 补齐2026-04-22至2026-05-07的前向行情。
  - 用固定Stage78口径生成前向daily和理论信号。
  - 再运行Stage169生成2026-05-07目标日报。
  - 同步准备QMT只读连接，用于资金、持仓、委托、成交对账。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：
  - Stage170只检查数据时效和缺口，不改策略、不筛信号、不调整参数。
  - 明确缺口反而能避免用旧历史样例伪装成前向影子盘。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：
  - 没有最新日报的问题必须自动暴露，否则影子盘无法前向运行。
  - 下一步补前向行情和QMT只读对账，才是真正从历史样例切换到准实盘影子盘。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新；本阶段未改变正式基准状态
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否；非重大突破、非正式候选、非路线废弃
