# Stage168 30万QMT影子盘启动包

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-07 13:48 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：准实盘工程启动包；不改策略、不做新回测、不触发A/B
- 是否重要突破：否；这是影子盘工程落地，不是收益突破
- 是否触发A/B：否；固定Stage78，不与新模块合成候选

## 外部调研与判断

- 参考资料：
  - QMT/xtquant公开接口文档显示`XtQuantTrader`支持账户资金、持仓、委托、成交查询，以及订单/成交/账户状态回调。
  - GitHub/PyPI上的`qmt-bridge`类项目说明，若策略机和QMT客户端不在同一环境，可用HTTP/WebSocket桥接，但真实交易前必须单独验收安全边界。
  - QMT实盘经验资料普遍强调：回调、查询和本地客户端状态可能存在异步差异，实盘系统应自建订单/成交/持仓账本。
- 我的判断：
  - 不能直接照搬外部QMT框架；当前最稳妥是先做只读接入和本地账本，再考虑模拟报单。
  - 第78最大历史回撤约`36.99%`，低于用户`40%`硬边界但缓冲只有约`3.01`个百分点，所以不能满风险直接真钱启动。
  - 30万账户下，Stage155最大计划保证金占用按第78正式资金口径粗略折算约`59.99%`，刚好贴近我设定的`60%`watch线，必须日报监控真实保证金。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/build_qmt_roll_stage168_30w_qmt_shadow_startup_pack.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `SHADOW_CAPITAL = 300000`
  - `MAX_TOLERABLE_DRAWDOWN_PCT = 40`
  - `DRAW_DOWN_WARN_PCT = 20`
  - `DRAW_DOWN_REVIEW_PCT = 30`
  - `DRAW_DOWN_STOP_PCT = 40`
  - `MARGIN_WATCH_PCT = 60`
  - `MARGIN_REVIEW_PCT = 70`
  - `MARGIN_NO_NEW_ORDERS_PCT = 80`
  - `DAILY_LOSS_WATCH_PCT = 2`
  - `DAILY_LOSS_REVIEW_PCT = 4`
  - `DAILY_LOSS_NO_NEW_ORDERS_PCT = 6`
  - `EXECUTION_ADVERSE_WATCH_PCT = 1`
  - `EXECUTION_ADVERSE_REVIEW_PCT = 2`
  - `real_order_enabled = false`
  - `real_money_night_auto_order = false`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：未新增回测；读取Stage155历史影子协议产物
- 账户规模：`300000`
- 成本口径：未新增成本回测；后续由影子盘真实成交偏差校准
- 样本过滤：无
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
  - 输出启动闸门状态：`PASS=3`，`WATCH=2`，`BLOCKED_BY_USER_ENV=1`，`NOT_ALLOWED_YET=1`
  - Stage155历史每日控制行数：`1525`
  - Stage155历史意图行数：`779`
  - 风控规则行数：`11`
  - QMT字段映射行数：`8`
  - 允许下一模式：`30w_qmt_shadow_read_only`
  - 真实报单：`false`
  - 夜盘自动报单：`false`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage168_30w_qmt_shadow_startup_report_stage168_30w_qmt_shadow_startup_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage168_30w_qmt_shadow_startup_summary_stage168_30w_qmt_shadow_startup_v1.json`
- config：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage168_30w_qmt_shadow_startup_config_stage168_30w_qmt_shadow_startup_v1.json`
- risk_policy：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage168_30w_qmt_shadow_startup_risk_policy_stage168_30w_qmt_shadow_startup_v1.csv`
- qmt_field_map：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage168_30w_qmt_shadow_startup_qmt_field_map_stage168_30w_qmt_shadow_startup_v1.csv`
- daily_report_template：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage168_30w_qmt_shadow_startup_daily_report_template_stage168_30w_qmt_shadow_startup_v1.md`
- runbook：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage168_30w_qmt_shadow_startup_runbook_stage168_30w_qmt_shadow_startup_v1.md`

## 结论

- 本阶段结论：
  - 第78可以进入`30w_qmt_shadow_read_only`阶段。
  - 当前不能直接进入真钱自动交易。
  - QMT第一步只读查询资金、持仓、委托、成交和连接状态；账号密码不进入聊天、仓库或日报。
  - 夜盘继续按Stage167口径处理：影子盘记录真实T+1开盘代理价，真钱第一版不自动夜盘报单。
- 是否进入下一步：是
- 下一步：
  - 实现每日影子盘runner：生成冻结信号、补`real_t1_open_proxy`和`day_session_open_proxy`、读取QMT只读账户状态、生成日报。
  - 待用户在本机配置`QMT_SHADOW_ACCOUNT_ID`、`QMT_USERDATA_PATH`、`QMT_SESSION_ID`后，再做QMT只读连通性检查。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：
  - 本阶段只把资金边界、夜盘口径、QMT只读字段和风控阈值写成启动包。
  - 没有新增买卖规则，没有筛选更好的品种或日期，也没有用结果反推参数。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：
  - 第78进入实盘前最缺的不是收益，而是真实前向执行、持仓和资金闭环。
  - 启动包已经把“能不能接QMT、能不能每日对账、什么时候暂停”变成可执行清单，下一步可以推进真实影子盘runner。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新；本阶段未改变正式基准状态
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否；非重大突破、非正式候选、非路线废弃
