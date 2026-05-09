# Stage169 30万QMT影子盘每日Runner第一版

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-07 13:51 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：影子盘日报runner；离线/只读结构验证；不改策略、不做新回测、不触发A/B
- 是否重要突破：否；这是影子盘日常流程闭环，不是策略收益突破
- 是否触发A/B：否；固定Stage78，不引入新策略版本

## 外部调研与判断

- 参考资料：
  - QMT/xtquant公开接口：资金、持仓、委托、成交既可查询也可回调，应同时落表。
  - GitHub/PyPI `qmt-bridge`类方案：桥接可作为工程参考，但真实报单前必须先验证只读、权限和断线边界。
  - 国内期货夜盘交易日口径：有夜盘品种的下一交易日可从前一自然日`21:00`开始。
- 我的判断：
  - 每日runner第一版应先把“信号、风险、QMT就绪、日报”结构跑通，不应直接接真实报单。
  - `review`级别应区分“允许影子盘记录”和“允许真实新增开仓”；前者可以为`1`，后者必须为`0`。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/build_qmt_roll_stage169_30w_qmt_shadow_daily_runner.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `--trade-date`：可指定日报交易日，默认取Stage155历史意图ledger中最新`decision_date`
  - `offline_shadow_read_only`：当前运行模式
  - `allow_shadow_record`
  - `allow_real_new_orders`
  - `real_t1_open_proxy_price`
  - `day_session_open_proxy_price`
  - `proxy_quality`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：未新增回测；样例日报取历史`2026-04-15`
- 账户规模：`300000`
- 成本口径：未新增成本回测；沿用Stage155历史代理字段
- 样本过滤：默认取最近一个有Stage155历史意图的交易日
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
  - 样例交易日：`2026-04-15`
  - 样例信号数：`1`
  - 风险级别：`review`
  - 触发原因：`daily_loss_review`
  - 是否允许影子盘记录：`1`
  - 是否允许真实新增开仓：`0`
  - 当前历史代理回撤：`5.3600%`
  - 当日历史代理亏损：`14,400`
  - 执行不利冲击代理：`3,360`
  - QMT查询状态：`not_configured`

## 输出文件

- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage169_30w_qmt_shadow_daily_runner_summary_20260415_stage169_30w_qmt_shadow_daily_runner_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage169_30w_qmt_shadow_daily_runner_daily_report_20260415_stage169_30w_qmt_shadow_daily_runner_v1.md`
- signal_plan：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage169_30w_qmt_shadow_daily_runner_signal_plan_20260415_stage169_30w_qmt_shadow_daily_runner_v1.csv`
- risk_snapshot：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage169_30w_qmt_shadow_daily_runner_risk_snapshot_20260415_stage169_30w_qmt_shadow_daily_runner_v1.json`

## 结论

- 本阶段结论：
  - 每日影子盘日报结构已经可以离线生成。
  - 当前日报能区分影子记录和真实新增开仓；`review`级别不会误放真实新增开仓。
  - `day_session_open_proxy_price`仍需接入分钟线或QMT行情后补齐。
  - QMT只读查询尚未接入，当前只验证本地日报结构和风控闸门。
- 是否进入下一步：是
- 下一步：
  - 接入QMT只读健康检查：账户、资金、持仓、委托、成交、连接状态。
  - 接入分钟线或QMT行情，补齐`day_session_open_proxy_price`和夜盘真实T+1开盘代理价差异。
  - 在真实未来交易日跑日报，而不是只用历史样例。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：
  - Stage169只是按固定Stage155意图和Stage168风控生成单日日报，不改Stage78信号。
  - 没有根据日报结果修改参数、筛掉信号或改变品种池。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：
  - 日报runner是影子盘能否连续运行的基本闭环。
  - 下一步接入QMT只读查询和分钟线代理价后，可以进入真实前向影子盘记录。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新；本阶段未改变正式基准状态
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否；非重大突破、非正式候选、非路线废弃
