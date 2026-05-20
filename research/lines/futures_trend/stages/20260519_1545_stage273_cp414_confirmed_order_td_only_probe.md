# Stage273：券商确认 41407/41415 后的 CP Mac SDK 与 TD-only 复测

- 时间：2026-05-19 15:45 CST
- 研究线：`futures_trend`
- 类型：Stage78-1 CTP/券商测试柜台执行通路诊断，不涉及 alpha 优化
- 是否重要突破版本：否，属于实盘前连接诊断
- 是否过拟合：否。本阶段没有改策略、没有调参数、没有根据收益挑选版本，只验证真实 CTP 前置兼容性。
- 是否仍有继续价值：是。Mac 上能否稳定登录券商测试/仿真柜台，是后续 Stage78-1 虚拟盘与实盘前对账的必要条件。

## 本次输入

券商截图确认：

- 经纪商代码：`1010`
- 交易前置：`tcp://182.140.218.46:41407`
- 行情前置：`tcp://182.140.218.46:41415`
- 账号、密码、AppID、认证码只保留在本机 local env，未写入记录。

## 新增文件

- `examples/portfolio_backtesting/run_ctp_stage273_cp_mac_td_only_probe.py`
- `examples/portfolio_backtesting/run_ctp_stage273_cp_mac_td_only_probe.sh`

该探针只创建底层 `TdApi`，不启动 vn.py `MainEngine/Gateway`，不连接行情接口，不调用下单接口。

## 测试结果

1. CP Mac SDK + 确认端口顺序的 combined readonly：
   - 命令：`bash examples/portfolio_backtesting/run_ctp_stage271_broker_cp_mac_sdk_readonly_probe.sh --connect --wait-seconds 45`
   - 输出日志：`/private/tmp/stage273_cp414_confirmed_order_retry.log`
   - 结果：`exit_code=139`
   - 现象：行情服务器连接成功、行情服务器登录成功；随后底层进程段错误，未拿到交易端认证/登录/账户快照。

2. CP Mac SDK + TD-only 探针：
   - 命令：`CTP_TD_ONLY_WAIT_SECONDS=35 bash examples/portfolio_backtesting/run_ctp_stage273_cp_mac_td_only_probe.sh`
   - 输出日志：`/private/tmp/stage273_td_only_cp414_retry2.log`
   - 结果：`exit_code=139`
   - 摘要：`front_connected=False, auth_ok=False, login_ok=False, settlement_ok=False, account_count=0, position_count=0`
   - 说明：交易端 35 秒内未收到 `onFrontConnected`，退出时仍出现底层段错误。

3. 老 `vnpy_ctp 6.7.2.1` + 414xx 对照：
   - 命令：`bash examples/portfolio_backtesting/run_ctp_stage267_broker_test_readonly_probe.sh --connect --wait-seconds 35`
   - 输出日志：`/private/tmp/stage273_normal_vnpyctp_414_retry.log`
   - 结果：行情接口 `decode err`，交易服务器反复 `4097` 断开。
   - 说明：414xx 不是当前 6.7.2.1 老 API 能稳定连接的前置。

4. 网络端口：
   - `182.140.218.46:41407` 可达
   - `182.140.218.46:41415` 可达
   - `182.140.218.46:41207` 可达
   - `182.140.218.46:41215` 可达

## 判断

- 端口顺序现在已确认：`TD=41407 / MD=41415`。
- 行情端在 CP Mac SDK 下可登录，说明账号和行情前置不是完全不可用。
- 交易端尚未达到认证/登录阶段，TD-only 也没有 `onFrontConnected`，更像是 41407 交易前置与当前 Python 封装/CP Mac SDK 运行方式存在兼容性问题，或者券商交易前置权限/认证登记仍未完全匹配。
- 当前不能把 414xx 作为 Stage78-1 默认执行路径。
- 已通过的 `41207/41215` broker-test 通路仍是当前唯一可用于虚拟盘只读/1手 smoke order 的稳定路线。

## 回测指标

本阶段未做回测，以下指标不适用：

- 期末权益：N/A
- 总收益：N/A
- 最大回撤：N/A
- Sharpe：N/A
- 总滑点：N/A
- 总交易次数：N/A
- 胜率：N/A

## 后续 TODO

1. 把上述三条现象发给券商技术：`41415` 行情可登录、`41407` TD-only 无 `onFrontConnected` 且退出段错误、老 API 连 414xx 为 `decode err/4097`。
2. 问券商是否有与 `v6.7.7_MacOS_CP_20240716` 匹配的 Python/vn.py 封装，或是否只支持 C++ SDK。
3. 问券商 41407 交易前置是否需要对该测试账号单独登记 CP AppID/AuthCode。
4. 在券商给出新 API 或确认前，Stage78-1 日常虚拟盘继续沿用已通过的 `41207/41215` 路线。
