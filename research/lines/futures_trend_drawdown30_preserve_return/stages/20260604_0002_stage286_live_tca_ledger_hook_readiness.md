# Stage286 Live TCA 账本 hook readiness 审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 00:02 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读工程审计；不连接 CTP，不调用下单 API，不修改策略逻辑。
- 是否重要突破：否，但属于重要工程边界确认。
- 是否触发A/B：否。本阶段没有产生可接入正式版本的新策略候选。

## 外部调研与判断

- 参考资料：
  - vn.py / vnpy GitHub：`EVENT_ORDER`、`EVENT_TRADE`、`OrderData`、`TradeData` 是订单状态和成交回报的自然入口。
  - TCA / implementation shortfall / VWAP 资料与开源实现：有效成交质量评估必须把 signal、submit、fill、VWAP benchmark、unfilled/cancelled volume、participation 与 broker reject/filter 放到同一条生命周期账本。
- 我的判断：
  - Stage526 当前缺的不是再扫一次历史收益，而是结构化 live TCA 账本。
  - 现有 Python CTP 脚本已经能抓 `EVENT_ORDER/EVENT_TRADE/EVENT_TICK`，工程上可接。
  - 但现有脚本是 smoke/proof/reconnect 接受测试，不是 Stage526 `event_id -> vt_orderid -> trade fill -> VWAP/shortfall` 桥，因此仍不能声明“真实交易不存在偏差”。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage586_live_tca_ledger_hook_readiness.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - 审计字段：`18` 个 live actual fields，包括 `signal_generated_at/signal_price/order_submit_at/order_submit_price/order_type/limit_price/fill_first_at/fill_last_at/avg_fill_price/filled_volume/cancelled_volume/unfilled_volume/commission_cash/actual_slippage_cash/actual_implementation_shortfall_bps/actual_vs_window_vwap_bps/account_equity_before/broker_margin_before`。
  - 硬闸门：`8` 个，覆盖事件捕获、TCA模板、P0 watchlist、信号意图关联、自动TCA计算、live字段实际值、P0有效样本、零执行偏差声明。
- 修改参数：无交易参数修改。
- 删除参数：无。

## 审计参数

- 数据区间：不做收益回测；读取当前本地脚本和既有 Stage568/575/583/585 输出。
- 策略口径：Stage526 `r080_pc25_maxpos4` 仅作为参考候选，不改入场、出场、AI池、相关门控、风险预算或执行语义。
- 检查对象：
  - CTP/vn.py 脚本：`run_ctp_stage174/258/285/287/288` 以及 native C++ probe/smoke 脚本。
  - live template：Stage568 execution quality ledger template 与 Stage575 P0 live evidence template。
  - P0 缺口：`fu2509.SHFE/lc2505.GFEX/AP505.CZCE`。
  - Stage583/585 证据缺口决策。

## 结果

- 决策：`live_tca_hook_partial_event_capture_ready_bridge_not_wired`
- Stage526 参考：
  - 期末权益：`23,369,505`
  - 总收益：`3699.9195%`
  - 最大回撤：`-36.2670%`
  - Sharpe：`1.6385`
  - Ulcer：`14.4691`
  - 总滑点：`1,342,190`
  - 总交易次数：`905`
  - 胜率：`53.6330%`
- 工程 readiness：
  - 闸门：`3/8` 通过。
  - 组件：`3/6` 通过。
  - 已通过：vn.py order/trade/tick 事件捕获可用；Stage568/575 模板包含 `18/18` 个 required actual fields；P0 watchlist 已有 `3` 个 P0。
  - 未通过：Stage526 signal intent 到 `vt_orderid` 的桥不存在；自动 live TCA metric reducer 不存在；当前模板 live actual values 为 `0/18`；P0 有效 live TCA 样本仍为 `0/9`。
  - Stage585 延续：非 CSV 证据中 P0 live TCA close files 仍为 `0`。

## 图表视觉复盘

- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage586_live_tca_ledger_hook_readiness_chart_stage586_live_tca_ledger_hook_readiness_v1.png`
- 左上 component readiness 显示明显断层：`vnpy_event_capture`、`stage526_live_tca_template`、`p0_execution_watchlist` 为绿；`signal_intent_to_order_join`、`automatic_tca_computation`、`existing_valid_live_tca_samples` 为红。
- 右上 script capability matrix 显示 Stage174/258/285/287 Python 脚本在 raw event capture、CSV持久化和 dry-run gate 上较完整，但 `signal_event_id_link` 与 `tca_metric_compute` 列几乎全空。
- 左下 required field coverage 显示 Stage568/575 字段列全绿，但 `automatic_compute_ready` 与 `current_live_values_present` 全红；说明 schema 已经准备好，缺的是填值管道。
- 右下 promotion gates 只有前三项绿灯，后五项红灯；视觉上支持“可以开始建桥，但不能关账真实偏差”的结论。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage586_live_tca_ledger_hook_readiness_report_stage586_live_tca_ledger_hook_readiness_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage586_live_tca_ledger_hook_readiness_decision_stage586_live_tca_ledger_hook_readiness_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage586_live_tca_ledger_hook_readiness_chart_stage586_live_tca_ledger_hook_readiness_v1.png`
- runbook：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage586_live_tca_ledger_hook_readiness_runbook_stage586_live_tca_ledger_hook_readiness_v1.md`
- script matrix：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage586_live_tca_ledger_hook_readiness_script_capability_matrix_stage586_live_tca_ledger_hook_readiness_v1.csv`
- field matrix：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage586_live_tca_ledger_hook_readiness_field_mapping_matrix_stage586_live_tca_ledger_hook_readiness_v1.csv`
- component matrix：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage586_live_tca_ledger_hook_readiness_component_readiness_stage586_live_tca_ledger_hook_readiness_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage586_live_tca_ledger_hook_readiness_gates_stage586_live_tca_ledger_hook_readiness_v1.csv`

## 结论

- 本阶段结论：可以继续做，而且应优先做 live TCA bridge；但当前 Stage526 仍不能声明“真实交易不存在偏差”。
- 是否进入下一步：进入。
- 下一步：
  - 新建 dry-run `live_tca_ledger_bridge`：从 Stage575 P0/live template 读取 intent row，在提交时写入 `event_id/signal_id/vt_orderid`，再由 `EVENT_ORDER/EVENT_TRADE/EVENT_TICK` 归并出 avg fill、unfilled、VWAP、implementation shortfall、participation。
  - 仍必须遵守 Stage78/CTP SOP：默认 dry-run，普通审计中 `send_order_api_called_count=0`；任何 submit 都必须走 SimNow/券商测试确认闸门。
  - 三个 P0 bucket 各累计 `3` 个有效样本前，Stage526 只能称为正常成本候选，不能关账真实偏差。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：
  - 本阶段只审计工程 hook、字段和证据链，不搜索收益参数，不使用未来收益。
  - 结果主动拒绝“零执行偏差”声明，避免把模板或历史代理误当实盘证据。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：
  - 真实执行偏差是 Stage526/DD40 目标的硬阻塞项。
  - 审计证明底层事件 hook 已有，缺口集中在可实现的账本桥上，下一步有明确工程落点。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。该阶段改变下一步工程优先级。
- 是否追加根目录 `memory.md/back_log.md`：是。该阶段属于重要执行边界记录。
