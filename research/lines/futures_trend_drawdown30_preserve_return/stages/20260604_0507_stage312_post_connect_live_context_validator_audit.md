# Stage312 post-connect live context validator 审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 05:07 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：执行无偏差链路只读验证器；不重放交易引擎、不修改策略、不连接 CTP、不订阅行情、不调用订单 API。
- 对应脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage612_post_connect_live_context_validator_audit.py`
- 输出报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage612_post_connect_live_context_validator_audit_report_stage612_post_connect_live_context_validator_audit_v1.md`
- 输出图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage612_post_connect_live_context_validator_audit_chart_stage612_post_connect_live_context_validator_audit_v1.png`
- 决策：`post_connect_validator_ready_dry_run_fail_closed_waiting_for_live_snapshot`
- 是否重要突破：否。它让未来 read-only connect 后的验证可复验，但当前仍未闭合真实执行证据。
- 是否触发 A/B：否。没有新策略候选、没有 paper selector、没有白名单。
- 是否新增回测：否。
- 是否修改策略：否。
- 是否连接 CTP/SimNow：否。
- 是否调用 `send_order`：否。

## 开始前反思

- 是否过拟合：否。本阶段只验证执行证据，不碰收益、参数、品种或 selector。
- 是否有价值继续：有。当前目标要求“真实交易不存在偏差”，而 Stage608/610 仍停留在 dry-run；需要一个连接后可复验的 fail-closed 清单。

## 外部调研判断

- vn.py `MainEngine` 通过 `OmsEngine` 暴露 `get_tick/get_contract/get_account/get_position` 等缓存查询能力。
- vn.py 的 `EVENT_TICK/EVENT_CONTRACT/EVENT_ACCOUNT/EVENT_POSITION` 事件会更新 OMS 状态缓存，因此 post-connect validator 应读取缓存快照，而不是使用历史回测 reference price。
- 本阶段判断：验证器应只读 Stage608 输出文件和 Stage591 submit plan；只要 contract/tick/account/position/operator 任一缺失，就禁止 real submit 和 zero-bias claim。

参考：

- vn.py MainEngine query APIs: https://deepwiki.com/vnpy/vnpy/2.2-main-engine
- vn.py OmsEngine state cache: https://deepwiki.com/vnpy/vnpy/2.3-gateways
- vn.py source tree: https://github.com/vnpy/vnpy/tree/master/vnpy/trader
- vnpy_ctp gateway package: https://github.com/vnpy/vnpy_ctp

## 本阶段做了什么

- 新增 Stage612 脚本，读取：
  - Stage591 submit plan；
  - Stage608 read-only tick snapshot probe summary/files；
  - Stage610 wrapper/env 审计 decision。
- 复用 `qmt_roll_live_context_adapter.evaluate_submit_plan_live_context`，保证与 Stage606/607 使用同一套 live context 字段。
- 生成 source inventory、symbol validation、context rows、order readiness、pre-submit heatmap、gates、decision、report 和 chart。
- 当前仍是 dry-run，不连接、不订阅、不下单。

## 新增/修改/删除

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage612_post_connect_live_context_validator_audit.py`
- 修改脚本：无既有策略脚本修改。
- 删除脚本：无。
- 新增参数：无策略参数。
- 修改参数：无。
- 删除参数：无。

## 回测结果

本阶段没有新增交易回测，因此以下字段不适用：

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 核心结果

- Stage608 status：`dry_run_not_connected`
- Stage608 connect requested：`false`
- target symbols：`5`
- submit plan rows：`5`
- contract coverage：`0/5`
- tick coverage：`0/5`
- account coverage：`0/5`
- position symbol coverage：`0/5`
- live context present rows：`0/45`
- real submit allowed rows：`0/5`
- hard gates：`5/12`
- `send_order_api_called_count=0`
- `cancel_order_api_called_count=0`
- `subscribe_api_called_count=0`
- zero execution bias claim allowed：`false`

## 图表视觉复盘

- 左上：post-connect gates 中 summary、wrapper、no-order、target symbols、fail-closed 为绿；explicit connect、contract/tick/account/position/live context/fresh tick 全红，语义清楚。
- 右上：5 个 target symbol 的 contract/tick/position/account/submit 全为 `N`，没有把 dry-run 误认为可交易。
- 左下：shared validator heatmap 只有 `ref/payload` 为绿，`contract/account/position/limit/band/margin/operator` 全红，说明历史 reference price 没有被当成 live price。
- 右下：blocker 分布集中在 account、margin、contract、position、live limit、operator 等缺口，每个 blocker 都覆盖 5 单。

## 结论

- Stage612 让未来显式 `--connect` 后的验证变成可复验流程。
- 当前仍不能声明“真实交易不存在偏差”：没有 live tick、没有 contract/account/position 覆盖，没有 live context。
- 当前仍正确 fail-closed：real submit allowed `0/5`，zero-bias claim `false`。
- 下一步只有在用户确认测试环境和 read-only 动作后，才能用 Stage608 wrapper 显式 `--connect --wait-seconds 90` 刷新 tick/account/position/contract，再重跑 Stage612。

## 结束后反思

- 是否过拟合：否。脚本只验证 live context，不处理收益曲线、品种选择或参数。
- 是否有价值继续：有。它把“真实交易无偏差”的下一步从人工检查变成了可量化闸门。

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage612_post_connect_live_context_validator_audit.py`：通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage612_post_connect_live_context_validator_audit.py`：通过。
- 图表视觉检查：通过，红绿语义清楚，没有误导为可部署。
- decision JSON：输出有效。
- 输出文件存在：通过。

## TODO

- 等用户明确确认测试环境和 read-only 动作后，运行 Stage608 wrapper：`--connect --wait-seconds 90`，仍保持 `send_order=0`。
- 用刷新后的 Stage608 文件重跑 Stage612；目标是 contract/tick/account/position coverage 全部转绿，但 real submit 仍需 operator confirmation 才能转绿。
- 继续把 `bridge_signal_id -> vt_orderid -> EVENT_ORDER/EVENT_TRADE/EVENT_TICK` 的 TCA writer 接到真实事件链。
