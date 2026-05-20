# Stage267 CTP券商仿真实盘测试入口准备

- 时间：2026-05-19 11:23
- 所属研究线：futures_trend
- 工作模式：day
- 是否重要突破版本：否，属于Stage78-1实盘前链路接入准备
- 本次目标：在不落库、不打印敏感凭证的前提下，给券商提供的CTP仿真/测试柜台建立只读探针入口。

## 本次改动

- 新增 `examples/portfolio_backtesting/ctp_broker_test.example.env`：券商CTP仿真本地环境变量模板，只保留占位符。
- 新增 `examples/portfolio_backtesting/run_ctp_stage267_broker_test_readonly_probe.sh`：读取 `ctp_broker_test.local.env` 后复用Stage176/174通用CTP只读探针。
- 未写入用户提供的账户密码、授权码等敏感信息；`*.local.env` 已由 `.gitignore` 忽略。

## 已完成检查

- 交易端口 TCP 可达。
- 行情端口 TCP 可达。
- 当前只做网络/只读登录准备，不触发任何委托。

## 回测/交易结果

- 本阶段不涉及策略参数变化，不产生回测绩效。
- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：0
- 胜率：不适用

## 过拟合判断

否。本阶段没有调参、没有选择品种、没有根据结果优化策略，只验证交易通路和安全执行纪律。

## 继续价值判断

有价值。端口可达后，下一关是本机local env只读登录、账户/持仓快照、合约订阅与日志诊断；这些是Stage78-1进入虚拟盘前的必要闸门。

## TODO

1. 用户在本机创建 `ctp_broker_test.local.env` 并填入券商测试账户信息。
2. 运行 `run_ctp_stage267_broker_test_readonly_probe.sh --connect --wait-seconds 90` 做只读登录。
3. 若只读登录成功且持仓快照明确，再进入1手提交-撤单 smoke test；未显式确认前不得发送委托。
