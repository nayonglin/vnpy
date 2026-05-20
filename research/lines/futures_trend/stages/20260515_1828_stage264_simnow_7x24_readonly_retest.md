# Stage264 SimNow 7x24 只读通路复验

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-15 18:28 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：SimNow/CTP 7x24 环境连通性与只读登录复验
- 是否重要突破：是，7x24 从此前登录失败恢复为只读快照成功
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本阶段未做策略资料调研，只按本仓库 Stage78-1 SimNow Shadow SOP 执行环境探针。
- 我的判断：这是执行环境验证，不属于 alpha 优化；不改变 Stage78-1 策略参数。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 探针参数

- Python：`.py311/bin/python`
- 网络探针：`examples/portfolio_backtesting/run_ctp_stage179_simnow_network_probe.py`
- 只读探针：`SIMNOW_FRONT=7x24 examples/portfolio_backtesting/run_ctp_stage177_simnow_readonly_probe.sh --connect --wait-seconds 90`
- 目标前置：
  - TD：`tcp://182.254.243.31:40001`
  - MD：`tcp://182.254.243.31:40011`
- 账号密码：只从本机 `ctp_simnow.local.env` / 环境变量读取，未写入报告和聊天。

## 结果

- 网络层：
  - `7x24_182` TD/MD 均可达。
  - `trading/trading2/trading_mobile` 当前仍 `Connection refused`。
  - `180.*` 历史前置当前超时。
- 只读 CTP/vn.py 探针：
  - `td_connected=true`
  - `md_connected=true`
  - `td_auth_success=true`
  - `md_login_success=true`
  - `td_login_success=true`
  - `td_login_failed=false`
  - `status=readonly_snapshots_received`
  - `position_snapshot_state=confirmed_flat`
  - `position_rows=0`
  - `nonzero_position_rows=0`
  - `position_query_callback_rows=22`
  - `position_query_last_seen=true`
  - `position_query_error_rows=0`
- 下单状态：
  - `real_order_enabled=false`
  - `order_api_called=false`

## 输出文件

- 网络 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage179_simnow_network_probe_summary_stage179_simnow_network_probe_v1.json`
- 网络 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage179_simnow_network_probe_report_stage179_simnow_network_probe_v1.md`
- 只读 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json`
- 账户快照：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_accounts_stage174_ctp_vnpy_readonly_probe_v1.csv`
- 持仓快照：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_positions_stage174_ctp_vnpy_readonly_probe_v1.csv`
- 日志：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_logs_stage174_ctp_vnpy_readonly_probe_v1.csv`

## 结论

- 本阶段结论：SimNow `7x24` 只读环境已经通了，且拿到了账户/持仓快照；当前账户状态为 `confirmed_flat`。
- 是否进入下一步：是，但不能直接等同于可发策略单。
- 下一步：
  1. 若只做环境监控，可用 7x24 定期跑只读探针。
  2. 若要进入虚拟盘策略委托，必须先跑 Stage251 fresh pre-submit gate。
  3. 若策略信号是平仓，而 SimNow 账户仍 `confirmed_flat`，不得发送平仓单。
  4. 若需要真实 submit-cancel 或策略委托，仍需用户明确确认并保持 SimNow-only adapter。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只验证 CTP/SimNow 环境和账户快照，不改变策略逻辑、不选择参数、不评价收益。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：7x24 只读链路恢复后，可以把账户状态监控、虚拟盘前置检查和每日执行闸门从“等交易时段”推进到更稳定的日常流程。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：否。
