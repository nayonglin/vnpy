# Stage101 C9 止损后一次自动重试开仓执行链补齐

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：day
- 记录时间：2026-06-16 20:15 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：官方 C9/15w 实盘自动化执行语义补齐
- 是否重要突破：是，补齐了 C9 “止损后只重试一次再开仓”的自动化链路
- 是否触发A/B：否，本阶段不改 alpha、参数、回测逻辑，只补执行层

## 外部调研与判断

- 参考资料：
  - vn.py GitHub `OrderRequest` 定义：`symbol/exchange/direction/type/volume/price/offset/reference`
  - vn.py GitHub `MainEngine.send_order` / `OffsetConverter.convert_order_request`
- 我的判断：
  - 现有 Stage905/931 的 `OrderRequest` payload 结构和 vn.py 官方用法一致，不需要引入新交易框架。
  - C9 的一次重试应复用现有 dry-run intent、Stage927 arming gate、Stage931 live-real submit adapter 和 ledger 去重，而不是写一条绕过闸门的快捷下单路径。

## 本次变更

- 新增脚本：无
- 修改脚本：
  - `examples/portfolio_backtesting/qmt_roll_official_live_execution_ledger.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage904_official_live_c9_intraday_monitor.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage905_official_live_executor_dry_run.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage903_official_live_phase_d_controller.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py`
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：不适用
- 账户规模：C9/15w 实盘默认执行口径
- 成本口径：不适用
- 样本过滤：不适用
- 策略/归因口径：执行层语义验证，不跑新回测

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - Stage904 新增 `retry_open_dry_run_count`、`retry_watch_count`、`retry_candidate_rows`
  - Stage905 新增 `STAGE905-C9RETRY-xxx` retry open intent，带 `intent_role=c9_retry_open_once`
  - 合成验证中，初始开仓成交 + C9 止损平仓成交 + broker 空仓 + fresh tick 回到原开仓价时，生成 1 条 `retry_open_dry_run`
  - 已有 retry reserve 后，同一交易日同合约方向不会再生成第二条 retry open

## 输出文件

- report：不适用
- summary：不适用
- orders：不适用
- daily：不适用
- quality：本阶段以 `py_compile` 与合成执行链测试为准

## 结论

- 本阶段结论：
  - C9/15w 的“入场日 0.5R 止损后，只允许一次重试开仓”已经接入自动化执行链。
  - 触发条件必须同时满足：真实初始开仓成交、真实 C9 monitor 止损平仓成交、broker 对应方向空仓、fresh tick 重新回到原始成交价、ledger 未出现过 retry open reserve/submit/fill。
  - Stage904 只生成候选，Stage905 生成 `OrderRequest` dry-run payload，真实提交仍由 Stage927/931 的 live-real 闸门控制。
- 是否进入下一步：是
- 下一步：
  - 观察今晚 `20:55` Stage930 与 `21:05` 报告邮件。
  - 若真实发生开仓、止损或 retry，立即做 TCA、成交回报、委托残量、账户持仓与 ledger 对账。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：
  - 本阶段没有调整 C9 的 `0.5R`、重试次数、品种、方向、月份或窗口，只把已冻结的执行语义补齐到自动化链路。
  - 新增闸门基于真实成交和账户状态，不基于历史收益补丁。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：
  - 如果只自动止损、不自动重试，实盘行为会偏离 C9 正式语义。
  - 补齐后仍保留 Stage927/931/ledger/fresh tick/broker flat 的 fail-closed 约束，自动化价值高于新增风险。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等今晚自动化运行结果一起整理
- 是否更新 `research/registry.md`：否，日常工程补齐不更新总索引
- 是否追加根目录 `memory.md/back_log.md`：暂不追加，若今晚真实订单链路验收通过再追加重要合入摘要
