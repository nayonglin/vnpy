# Stage362：native CP 开盘时段连接复测

- 时间：2026-06-04 21:23 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 当前官方实盘版本：`official_live_stage653_20w_force95_to80`
- 决策：`native_cp_open_session_retest_blocked_tcp_ports_timeout`
- 是否重要突破版本：否。本阶段是开盘时段 CTP 前置可达性复测，不是策略 alpha 或参数优化。

## 本次测试

- 已读取 `work-type.txt`、`research/registry.md`、`skills/futures-live-execution-sop/SKILL.md` 和 `qmt_roll_official_live_config.py`。
- 运行 native CP 只读账户/保证金探针：
  - `bash examples/portfolio_backtesting/run_ctp_stage656_native_cp_account_margin_probe.sh`
- 运行基础 TCP 端口探测：
  - `182.140.218.46:41407`
  - `182.140.218.46:41415`
  - `182.140.218.46:41207`
  - `182.140.218.46:41215`
- 运行基础网络对照：
  - `ping 182.140.218.46`
  - 公网 TCP 对照连接

## 结果

- Stage656 生成时间：`2026-06-04 21:21:55`
- `front_connected=false`
- `auth_ok=false`
- `login_ok=false`
- `settlement_ok=false`
- `account_rows=0`
- `position_rows=0`
- `explicit_margin_rows=0`
- `system_info_source=collector_api:_Z28CTP_GetSystemInfoUnAesEncodePcRi`
- `system_info_len=264`
- `send_order_api_called_count=0`
- `cancel_order_api_called_count=0`
- 状态：`readonly_native_cp_no_account_margin_received`

TCP 端口探测：

- `182.140.218.46:41407`：timeout
- `182.140.218.46:41415`：timeout
- `182.140.218.46:41207`：timeout
- `182.140.218.46:41215`：timeout

基础网络对照：

- `182.140.218.46` ping 成功，`3/3` 收包，平均约 `37.778 ms`
- 公网 TCP 对照正常：`www.baidu.com:443/80`、`www.sina.com.cn:80` 均可连接

## 结论

- 当前不是本机整体断网，也不是终端信息采集失败；`system_info_len=264` 已正常生成。
- 阻断点在券商/SimNow 前置 TCP 端口不可达：目标 IP 可 ICMP 到达，但 CTP TD/MD 端口全部超时。
- 因没有 300 秒内 fresh read-only 账户/持仓/保证金快照，本阶段不能进入 dry-run，也不能发送 1 手测试单。
- 当前官方 Stage653 signal_plan 与 current_positions 仍为空文件头，当前没有策略理论委托需要执行。

## 输出文件

- Stage656 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage656_native_cp_account_margin_probe_summary_stage656_native_cp_account_margin_probe_v1.json`
- Stage656 raw log：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage656_native_cp_account_margin_probe_raw_stage656_native_cp_account_margin_probe_v1.log`
- Stage656 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage656_native_cp_account_margin_probe_report_stage656_native_cp_account_margin_probe_v1.md`

## 回测结果

- 本阶段未新增回测。
- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用

## 反思

- 过拟合反思：否。本阶段只验证开盘时段 CTP 前置可达性和只读账户快照，不修改策略、参数、品种池或执行规则。
- 继续价值反思：有价值。它排除了“只是非开盘时段导致不可达”的一部分可能性，下一步应把 `IP 可 ping、端口 timeout、21:21 CST 开盘时段仍无 front_connected` 反馈给券商，要求确认测试前置开放时间、源 IP 白名单、防火墙、端口号和账号权限。

## TODO

- 等券商确认前置端口开放后，先重跑 Stage656 只读探针。
- 只有 `front/auth/login/settlement=true` 且账户/持仓/保证金快照新鲜，才允许进入 dry-run。
- 只有 dry-run 通过并再次确认测试环境/1手测试单，才允许 submit-cancel smoke order。
