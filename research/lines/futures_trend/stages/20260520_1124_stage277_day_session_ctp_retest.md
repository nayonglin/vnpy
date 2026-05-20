# Stage277：日盘时段 414xx / 412xx CTP 只读复测

- 时间：2026-05-20 11:24 CST
- 研究线：`futures_trend`
- 类型：Stage78-1 CTP/券商测试柜台连接诊断，不涉及 alpha 优化
- 是否重要突破版本：否，属于实盘前连接诊断
- 是否过拟合：否。本阶段没有改策略、没有调参数、没有根据收益挑选版本，只验证日盘时段 CTP 前置可达性和登录状态。
- 是否仍有继续价值：是。本阶段把 `414xx` 评测/CP 路线和 `412xx` 普通/生产 API 路线的状态差异重新确认清楚。

## 本次目标

用户反馈当前是日盘交易期间，复测：

1. `41407` 交易前置 TD-only 是否能收到 `onFrontConnected`。
2. `41415` 行情前置 MD-only 是否能连接、登录、订阅并收到 tick。
3. `41207/41215` 老路线是否可作为交易链路对照。

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

- `41407`：连接成功
- `41415`：连接成功
- `41207`：连接成功
- `41215`：连接成功

结论：和 Stage276 夜盘时段整体超时不同，日盘当前端口层已恢复可达。

### 2. 41407 TD-only 交易端探针

命令：

```bash
CTP_TD_ONLY_WAIT_SECONDS=75 bash examples/portfolio_backtesting/run_ctp_stage273_cp_mac_td_only_probe.sh
```

输出日志：`/private/tmp/stage277_cp414_td_only_day_session.log`

结果：

```text
td_exit_code=139
summary front_connected=False auth_ok=False login_ok=False settlement_ok=False account_count=0 position_count=0
```

结论：即使端口可达、且处于日盘时段，`41407` 交易前置仍没有交易连接回调，未进入认证/登录/结算/账户持仓查询阶段。

### 3. 41415 MD-only 行情订阅探针

命令：

```bash
CTP_MD_SUBSCRIBE_WAIT_SECONDS=60 CTP_MD_SUBSCRIBE_SYMBOLS=MA609,ru2609 bash examples/portfolio_backtesting/run_ctp_stage274_cp_mac_md_subscribe_probe.sh
```

输出日志：`/private/tmp/stage277_cp414_md_subscribe_day_session.log`

结果：

```text
md_exit_code=0
front_connected=True
login_ok=True
subscription_response_count=2
tick_count=3
MA609 latest_tick update_time=11:23:40 last_price=2977 bid1=2977 ask1=2978
ru2609 latest_tick update_time=10:30:00.500 last_price=19760 bid1=19780 ask1=1.7976931348623157e+308
```

结论：`41415` 行情前置在日盘可连接、可登录、可订阅，并收到 tick/快照。`ru2609` 的 `ask1=1.7976931348623157e+308` 是 CTP 无效价格占位，不能当成真实卖一价。

### 4. 41207/41215 老路线对照

命令：显式覆盖端口后直接调用 `run_ctp_stage176_mac_readonly_probe.sh`，避免 `run_ctp_stage267` 读取 local env 覆盖回 `414xx`。

```bash
CTP_TD_ADDRESS=tcp://182.140.218.46:41207 \
CTP_MD_ADDRESS=tcp://182.140.218.46:41215 \
bash examples/portfolio_backtesting/run_ctp_stage176_mac_readonly_probe.sh --connect --wait-seconds 45
```

输出日志：`/private/tmp/stage277_412_readonly_day_session.log`

结果：

```text
行情服务器连接成功
交易服务器连接成功
行情服务器登录成功
交易服务器授权验证成功
交易服务器登录成功
结算信息确认成功
合约信息查询成功
status=readonly_snapshots_received
position_snapshot_state=positions_received
position_rows=352
nonzero_position_rows=341
```

结论：`41207/41215` 普通/生产 API 路线在日盘完整打通，可交易登录、结算确认、账户/持仓/合约快照。

## 判断

- `41415` 行情链路正常；券商如果查行情前置，应该能看到行情登录/订阅相关连接。
- `41407` 交易链路仍不正常；券商如果查交易前置，当前仍不应看到成功交易登录。
- `41207/41215` 交易链路正常，说明本机网络、账号基本信息、普通 API 封装并不是整体坏的。
- 当前阻塞集中在 `41407` 评测/CP 交易前置与 Mac CP SDK/Python 封装/权限登记之间，不是单纯“现在不是交易时间”的问题。
- Stage78-1 仍应 fail-closed；未完成交易端确认前不得用 `414xx` 进入虚拟盘或实盘执行。

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

1. 将本次结果发给券商：`41415` MD 成功、`41407` TD 无连接回调、`41207/41215` 完整成功。
2. 请券商重点查询 `41407` 是否有来自本机的连接尝试，以及该测试账号/AppID/AuthCode 是否已开通 41407 交易权限。
3. 若券商确认 41407 必须使用特定 CP 交易 API，请提供 macOS 版交易库和 Python/vn.py 兼容封装说明。
4. 短期 Stage78-1 broker-test 仍优先使用已打通的 `41207/41215` 路线。
