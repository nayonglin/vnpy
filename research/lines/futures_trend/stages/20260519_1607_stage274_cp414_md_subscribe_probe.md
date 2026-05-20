# Stage274：41415 行情前置 MD-only 订阅探针

- 时间：2026-05-19 16:07 CST
- 研究线：`futures_trend`
- 类型：Stage78-1 CTP/券商测试柜台行情链路诊断，不涉及 alpha 优化
- 是否重要突破版本：否，属于实盘前连接诊断
- 是否过拟合：否。本阶段没有改策略、没有调参数、没有根据收益挑选版本，只验证 CTP 行情前置订阅能力。
- 是否仍有继续价值：是。它能区分“行情登录成功”“行情订阅请求被接受”“连续实时 tick 推送正常”三件事。

## 新增文件

- `examples/portfolio_backtesting/run_ctp_stage274_cp_mac_md_subscribe_probe.py`
- `examples/portfolio_backtesting/run_ctp_stage274_cp_mac_md_subscribe_probe.sh`

该探针只创建底层 `MdApi`，不创建 `TdApi`，不连接交易前置，不查询资金/持仓/结算，不调用下单接口。

## 测试设置

- API：SimNow Mac CP SDK `v6.7.7_MacOS_CP_20240716`
- 行情前置：`tcp://182.140.218.46:41415`
- 订阅合约：`MA609, ru2609`
- 等待时间：45 秒
- 输出日志：`/private/tmp/stage274_cp414_md_subscribe.log`

账号、密码等敏感信息只从本机 local env 读取，未写入本记录。

## 测试结果

进程退出码：`0`

关键日志：

```text
[0.14s] onFrontConnected: market-data front connected
[0.14s] reqUserLogin ret=0
[0.17s] onRspUserLogin reqid=0 last=True ErrorID=0 ErrorMsg=CTP:No Error
[0.17s] subscribeMarketData symbol=MA609 ret=0
[0.17s] subscribeMarketData symbol=ru2609 ret=0
[0.21s] onRspSubMarketData instrument=MA609 last=True ErrorID=0 ErrorMsg=CTP:No Error
[0.21s] onRtnDepthMarketData symbol=MA609 trading_day=20260519 action_day=20260519 update_time=15:00:00.0 last_price=2965.0 bid1=2963.0 ask1=2964.0
[0.21s] onRspSubMarketData instrument=ru2609 last=True ErrorID=0 ErrorMsg=CTP:No Error
[0.21s] onRtnDepthMarketData symbol=ru2609 trading_day=20260519 action_day=20260519 update_time=15:41:16.0 last_price=20640.0 bid1=20960.0 ask1=1.7976931348623157e+308
[45.10s] summary front_connected=True login_ok=True subscription_response_count=2 tick_count=2
```

## 判断

- `41415` 行情前置可以连接。
- `41415` 行情登录成功。
- `MA609` 和 `ru2609` 的订阅请求均返回 `ErrorID=0`。
- 收盘阶段仍收到 2 条行情快照/最后 tick。
- 由于当前是收盘后、夜盘前空档，本次不能证明连续实时行情推送稳定；需要在夜盘 `20:55-21:05` 或日盘 `08:55-09:10` 再测。
- `ru2609` 的 `ask1=1.7976931348623157e+308` 是 CTP 常见的无效浮点占位，表示该档位价格不可用，不能当成真实卖一价格。
- 本次仍不代表交易链路成功；结算、账户、持仓、下单撤单仍取决于 `41407` 交易前置。

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

1. 将本次 MD-only 证据发给券商，说明 `41415` 可登录、可订阅、可收到收盘阶段行情快照。
2. 夜盘开盘附近复测，确认连续 tick 推送。
3. 继续要求券商定位 `41407` 交易前置未成功连接/登录的问题。
