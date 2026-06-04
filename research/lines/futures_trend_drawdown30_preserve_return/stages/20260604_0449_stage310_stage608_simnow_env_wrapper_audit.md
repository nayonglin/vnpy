# Stage310 Stage608 SimNow 环境 wrapper 审计

- 时间：2026-06-04 04:49 CST
- 所属研究线：`futures_trend_drawdown30_preserve_return`
- 对应脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage610_stage608_simnow_env_wrapper_audit.py`
- 修改文件：`examples/portfolio_backtesting/run_ctp_stage608_readonly_tick_snapshot_probe.sh`
- 输出报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage610_stage608_simnow_env_wrapper_audit_report_stage610_stage608_simnow_env_wrapper_audit_v1.md`
- 输出图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage610_stage608_simnow_env_wrapper_audit_chart_stage610_stage608_simnow_env_wrapper_audit_v1.png`
- 决策：`stage608_simnow_env_wrapper_ready_dry_run_no_connect`
- 是否重要突破：否。属于真实可成交无偏差链路的环境合同补强，不是收益候选。
- 是否触发 A/B：否。
- 是否新增回测：否。
- 是否修改策略：否。
- 是否连接 CTP/SimNow：否。
- 是否订阅行情：否。
- 是否调用 `send_order`：否。

## 开始前反思

- 是否过拟合：否。本阶段不修改交易规则、不筛选品种、不使用收益结果，只加强 read-only tick snapshot 的环境 wrapper。
- 是否有价值继续：有。当前真实交易无偏差链路仍缺 fresh tick/account/position/contract context；Stage608 必须先能安全地在显式 read-only connect 时读取本地 SimNow 环境和正确前置。

## SOP 与外部调研判断

- 已读取 `skills/stage78-simnow-shadow-sop/SKILL.md`。本阶段遵守默认 dry-run、50万口径、密码不入库、无显式确认不得连接/订阅/下单的纪律。
- vn.py/CTP 网关标准路径支持 `connect(setting)` 后通过事件回调获得合约、账户、持仓、行情；`SubscribeRequest + main_engine.subscribe` 是只读 tick snapshot 的正确抽象。
- `vnpy_ctp` 官方/文档资料确认 CTP gateway 是 VeighNa 的期货接口，环境参数应由连接配置提供；因此 SimNow front/default/env 放在 wrapper，而不是写死进策略或提交逻辑。

参考：

- vn.py gateway contract: https://deepwiki.com/vnpy/vnpy/7.2-creating-custom-gateways
- vnpy_ctp gateway package: https://github.com/vnpy/vnpy_ctp
- VeighNa CTP gateway usage: https://www.vnpy.com/docs/cn/community/info/gateway.html

## 本阶段做了什么

- 修改 Stage608 wrapper：
  - 支持 source 本地 `ctp_simnow.local.env`，但不打印密钥；
  - 保留外部 `SIMNOW_FRONT/CTP_TD_ADDRESS/CTP_MD_ADDRESS` 覆盖；
  - 默认 `SIMNOW_FRONT=7x24`；
  - 支持 `7x24/trading/trading2/trading_mobile` 四类 SimNow front；
  - 默认 `CTP_BROKERID=9999`、`CTP_APPID=simnow_client_test`、`CTP_AUTH_CODE=0000000000000000`、`CTP_PRODUCT_INFO=""`；
  - 保留 macOS `DYLD_FRAMEWORK_PATH` 指向 `vnpy_ctp/api/libs`。
- 新增 Stage610 wrapper 审计脚本。
- dry-run 运行 Stage608 wrapper；没有使用 `--connect`。
- 首次图表视觉检查发现 pending 项 0 宽度不明显、dry-run 值标签拥挤；已修成 checklist + 红色 pending 满条并重跑。

## 参数与变更

- 新增策略参数：无。
- 修改策略参数：无。
- 删除策略参数：无。
- 新增执行 wrapper 参数/环境语义：
  - `SIMNOW_FRONT` 可选值：`7x24/trading/trading2/trading_mobile`
  - `CTP_TD_ADDRESS/CTP_MD_ADDRESS` 可由外部覆盖
  - 本地 `ctp_simnow.local.env` 只作为本机环境源，不进入记录
- 新增输出：
  - `qmt_roll_stage610_stage608_simnow_env_wrapper_audit_capability_stage610_stage608_simnow_env_wrapper_audit_v1.csv`
  - `qmt_roll_stage610_stage608_simnow_env_wrapper_audit_dry_run_status_stage610_stage608_simnow_env_wrapper_audit_v1.csv`
  - `qmt_roll_stage610_stage608_simnow_env_wrapper_audit_gates_stage610_stage608_simnow_env_wrapper_audit_v1.csv`
  - `qmt_roll_stage610_stage608_simnow_env_wrapper_audit_decision_stage610_stage608_simnow_env_wrapper_audit_v1.json`
  - `qmt_roll_stage610_stage608_simnow_env_wrapper_audit_report_stage610_stage608_simnow_env_wrapper_audit_v1.md`
  - `qmt_roll_stage610_stage608_simnow_env_wrapper_audit_chart_stage610_stage608_simnow_env_wrapper_audit_v1.png`

## 回测结果

本阶段没有新增回测，因此以下字段不适用：

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用

## Dry-run 结果

- wrapper capabilities：`10/10`
- hard gates：`5/5`
- `status`：`dry_run_not_connected`
- `connect_requested`：`false`
- `target_symbol_count`：`5`
- `missing_required_env_count`：`0`
- `vnpy_ctp_import_available`：`true`
- `send_order_api_called_count`：`0`
- `cancel_order_api_called_count`：`0`
- `subscribe_api_called_count`：`0`
- `tick_rows`：`0`，符合 dry-run 预期
- 连接目标前置：`7x24` 的 `40001/40011`
- 密钥安全：wrapper 未发现 password/auth echo pattern；Python summary 只脱敏账号/经纪商，不打印密码和授权码

## 图表视觉复盘

- 左上 capability 全绿：wrapper 可执行、本地 env、外部覆盖、SimNow front、DYLD、显式 connect、无订单路径均通过。
- 右上 dry-run checklist 全绿：没有连接、没有订阅、没有订单 API，目标合约仍是 `5` 个。
- 左下 safety gates 中 `fresh_tick_snapshot_evidence` 红色 pending：这不是本阶段失败，而是明确剩余 live evidence gap。
- 右下执行证据阶梯只完成 `dry-run env wrapper`；`explicit read-only --connect`、`target tick rows >0`、`Stage606/607 validator all green`、`vt_orderid TCA writer` 均仍 pending。

## 结论

- Stage608 wrapper 已具备下一次显式 read-only `--connect` 所需的环境合同。
- 当前仍没有连接、没有行情订阅、没有 tick rows；不能声明真实交易无偏差已经闭合。
- 下一步只有在用户确认测试环境和 read-only 动作后，才运行 Stage608 wrapper `--connect` 捕获 target symbols tick snapshot，并喂给 Stage606/607 validator。

## 结束后反思

- 是否过拟合：否。所有输出都是执行环境、安全闸门和 dry-run 证据，不使用历史收益优化。
- 是否有价值继续：有。环境缺口已闭合，后续可以更低风险地推进显式 read-only tick capture。

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/run_ctp_stage608_readonly_tick_snapshot_probe.py` 通过。
- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage610_stage608_simnow_env_wrapper_audit.py` 通过。
- `examples/portfolio_backtesting/run_ctp_stage608_readonly_tick_snapshot_probe.sh` dry-run 通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage610_stage608_simnow_env_wrapper_audit.py` 通过。
- 图表已两轮视觉检查；第一轮发现可读性问题并修正，第二轮通过。

## TODO

- 用户明确确认测试环境和 read-only 动作后，运行：
  - `examples/portfolio_backtesting/run_ctp_stage608_readonly_tick_snapshot_probe.sh --connect --wait-seconds 90`
- 继续保持 `send_order_api_called_count=0`。
- 若 tick rows >0，把 Stage608 snapshot 输入 Stage606/607 validator，验证 contract/account/position/tick/limit/band/margin 字段从红变绿。
- 在 validator 全绿且用户明确确认 submit 动作前，不允许 exact `vt_orderid` writer 和任何订单 API。
