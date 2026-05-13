# Stage256 SimNow交易时段通路恢复与Phase B总闸门复验

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-13 11:18
- 阶段性质：SimNow通路复验/只读快照/Phase B dry-run总闸门
- 是否重要突破：是
- 是否触发A/B：否，本阶段不改策略、不改参数、不跑收益对比

## 外部调研与判断

- SimNow官网产品说明显示第一套环境交易时间与实际生产环境保持一致；今日在日盘交易时段测试，符合使用第一套 `trading` 前置的预期。
- 官网同时说明第二套/7x24环境有独立服务时间，新注册用户对第二套环境有生效等待要求；因此本次不再把7x24失败视为本地代码主因。
- 本阶段判断应以本地实测为准：网络、行情登录、交易授权、交易登录、结算确认和只读快照均已通过。

## 本次运行

### Stage179 网络前置探针

- 运行时间：`2026-05-13 11:14`
- 可达 front：`trading`, `trading2`, `trading_mobile`
- 当前不可达：
  - `7x24_182`：`40001/40011` 均 `Connection refused`
  - `7x24_180`：`10130/10131` 超时
  - `first_180_group1/2`：超时
- 结论：当前应使用第一套 `trading`：`tcp://182.254.243.31:30001` / `tcp://182.254.243.31:30011`

### Stage174 只读探针

- 前置：`trading`
- 状态：`readonly_snapshots_received`
- 行情服务器连接：成功
- 行情服务器登录：成功
- 交易服务器连接：成功
- 交易服务器授权验证：成功
- 交易服务器登录：成功
- 结算信息确认：成功
- 合约信息查询：成功
- 账户文件行数：`13`，约12条账户字段/快照行
- 持仓文件行数：`1`，无持仓数据行
- 合约文件行数：`19,386`，约19,385条合约行
- 委托/成交文件行数：均为`1`，无历史委托/成交数据行
- 持仓快照语义：`confirmed_flat`
- 真实发单：`false`
- `order_api_called`：`false`

### Stage251 Fresh Pre-submit Gate

- 交易日样例：`2026-04-30`
- 前置：`trading`
- 最终状态：`fresh_pre_submit_gate_passed`
- 新鲜快照年龄：`122.477` 秒，小于 300 秒阈值
- `stage244_passed`：`true`
- `stage245_final_can_submit`：`true`
- `stage249_dry_run_ready`：`true`
- `stage250_dry_request_ready`：`true`
- `stage250_real_blocked`：`true`
- 真实 submit/send_order 调用次数：`0`

## 输出文件

- Stage179报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage179_simnow_network_probe_report_stage179_simnow_network_probe_v1.md`
- Stage174 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json`
- Stage251 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage251_phaseb_fresh_pre_submit_gate_summary_20260430_stage251_phaseb_fresh_pre_submit_gate_v1.json`
- Stage251 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage251_phaseb_fresh_pre_submit_gate_report_20260430_stage251_phaseb_fresh_pre_submit_gate_v1.md`

## 结论

- SimNow 第一套 `trading` 通路已经恢复。
- 当前可以进入“SimNow虚拟盘最小链路测试”的准备阶段，但本阶段仍未发单。
- 7x24 当前不可达，不影响第一套交易时段路径。
- 下一步若要从只读进入虚拟盘委托，必须新增/使用真实 submit adapter，并继续保留显式环境变量开关、人工确认和新鲜快照闸门。

## 过拟合反思

- 运行前判断：否。通路复验不修改策略，不影响历史收益。
- 运行后判断：否。本阶段只证明外部SimNow链路可用，不证明策略有效性。

## 继续价值反思

- 运行前判断：有价值。此前阻塞点是SimNow连接/账号/服务窗口，必须复验。
- 运行后判断：有价值。只读与总闸门均通过，下一步可以围绕虚拟盘最小发单链路推进。

## TODO

- 不要直接用策略正常手数自动发单；先实现/复验SimNow-only submit adapter。
- 第一笔虚拟盘委托仍建议做1手链路测试，确认报单、回报、撤单/成交、持仓同步完整。
- 若要执行最新 `si2609.GFEX` 平仓信号，需要先生成对应Phase B草案并确认SimNow持仓真实存在。
