# Stage276：夜盘开盘时段 414xx / 412xx CTP 只读复测

- 时间：2026-05-19 21:20 CST
- 研究线：`futures_trend`
- 类型：Stage78-1 CTP/券商测试柜台连接诊断，不涉及 alpha 优化
- 是否重要突破版本：否，属于实盘前连接诊断
- 是否过拟合：否。本阶段没有改策略、没有调参数、没有根据收益挑选版本，只验证开盘时段 CTP 前置可达性。
- 是否仍有继续价值：是。它能验证此前“收盘时段导致 41407 不能登录”的假设是否成立。

## 本次目标

用户反馈当前已到夜盘开盘时段，复测：

1. `41407` 交易前置 TD-only 是否能收到 `onFrontConnected`。
2. `41415` 行情前置 MD-only 是否能连接、登录、订阅并收到 tick。
3. 已打通过的 `41207/41215` 路线是否可作为网络/柜台对照。

所有测试均为只读，没有调用下单接口。

## 本地配置

`ctp_broker_test.local.env` 当前仍为：

- `CTP_BROKERID=1010`
- `CTP_TD_ADDRESS=tcp://182.140.218.46:41407`
- `CTP_MD_ADDRESS=tcp://182.140.218.46:41415`
- 账号、密码、AppID、AuthCode 只确认已配置长度，未写入记录。

## 测试结果

### 1. TCP 端口可达性

命令：`nc -vz -G 5 182.140.218.46 <port>`

- `41407`：`Operation timed out`
- `41415`：`Operation timed out`
- `41207`：`Operation timed out`
- `41215`：`Operation timed out`

这和下午曾经端口可达、且 41415 可登录/订阅的状态不同。

### 2. 41407 TD-only 交易端探针

命令：

```bash
CTP_TD_ONLY_WAIT_SECONDS=75 bash examples/portfolio_backtesting/run_ctp_stage273_cp_mac_td_only_probe.sh
```

输出日志：`/private/tmp/stage276_cp414_td_only_open_session.log`

结果：

```text
td_exit_code=139
summary front_connected=False auth_ok=False login_ok=False settlement_ok=False account_count=0 position_count=0
```

结论：夜盘开盘时段仍没有交易前置连接回调，未进入认证/登录/结算/账户持仓查询阶段。

### 3. 41415 MD-only 行情订阅探针

命令：

```bash
CTP_MD_SUBSCRIBE_WAIT_SECONDS=60 CTP_MD_SUBSCRIBE_SYMBOLS=MA609,ru2609 bash examples/portfolio_backtesting/run_ctp_stage274_cp_mac_md_subscribe_probe.sh
```

输出日志：`/private/tmp/stage276_cp414_md_subscribe_open_session.log`

结果：

```text
md_exit_code=4
summary front_connected=False login_ok=False subscription_response_count=0 tick_count=0
latest_tick symbol=MA609 none
latest_tick symbol=ru2609 none
```

结论：和 16:07 的 Stage274 不同，本次 `41415` 行情前置也未收到连接回调，无法登录/订阅。

### 4. 41207/41215 老路线对照

`run_ctp_stage267_broker_test_readonly_probe.sh` 会读取 local env 覆盖临时端口，因此先前一次对照实际仍连到 `414xx`，已判为无效对照。

随后直接调用 `run_ctp_stage176_mac_readonly_probe.sh` 并显式覆盖：

```bash
CTP_TD_ADDRESS=tcp://182.140.218.46:41207 \
CTP_MD_ADDRESS=tcp://182.140.218.46:41215 \
bash examples/portfolio_backtesting/run_ctp_stage176_mac_readonly_probe.sh --connect --wait-seconds 45
```

输出日志：`/private/tmp/stage276_412_readonly_open_session_retry2.log`

结果：

```text
status=readonly_logs_without_ctp_progress
connection_target TD=41207 / MD=41215
td_connected=False
md_connected=False
td_auth_success=False
md_login_success=False
td_login_success=False
position_snapshot_state=position_query_not_available
```

结论：本次 `41207/41215` 也没有连接进展。

## 判断

- “下午收盘导致 41407 不能登录”这个解释不充分。因为现在夜盘时段复测，`41407` 仍无连接回调。
- 本次 `41415` 也没有连接回调，和下午 `41415` 可登录、可订阅、可收到快照不同。
- `41207/41215` 对照同样无进展，说明今晚这个时点更像是本机到券商前置整体网络不可达、券商前置服务未开放/重启、白名单/路由限制或柜台时段状态变化，而不只是 `41407` 单点认证问题。
- 当前不允许进入任何下单/虚拟盘执行；只能把连接诊断结果反馈券商。

## 回测指标

本阶段未做回测，以下指标不适用：

- 期末权益：N/A
- 总收益：N/A
- 最大回撤：N/A
- Sharpe：N/A
- 总滑点：N/A
- 总交易次数：0
- 胜率：N/A

## 后续 TODO

1. 将 21:16-21:20 的端口超时和 CTP 无回调结果发给券商，询问该时间段前置是否开放、是否有 IP 白名单或网络限制。
2. 请券商分别查询 `41207/41215` 与 `41407/41415` 当前是否在线、是否有来自本机公网 IP 的连接尝试。
3. 等券商确认前置开放后，再复测 Stage273 TD-only 与 Stage274 MD-only。
4. 若需要继续走 `414xx`，仍需券商提供 Mac CP Python/vn.py 兼容封装或明确 C++ SDK 使用方式。
