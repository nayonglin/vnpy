# Stage178 SimNow 连接探针结果

- 时间：2026-05-08 20:05 CST
- 研究线：`futures_trend`
- 工作模式：day
- 阶段：Stage178
- 主题：使用用户本机 SimNow 账号尝试 Mac CTP 只读连接

## 本次结论

本次已确认 `ctp_simnow.local.env` 被正确读取，`CTP_USERID`、`CTP_PASSWORD`、BrokerID、交易前置、行情前置、AppID、AuthCode 均已配置；`vnpy_ctp` 和 `CtpGateway` 也可正常导入。

但本次尚未确认 CTP 登录成功。探针只记录到 `连接登录 -> CTP`，没有收到账户、持仓、合约或 CTP 错误事件；随后对 SimNow 常见前置端口做 TCP 探测，均超时。因此当前判断为：本机/当前网络到 SimNow 前置不可达，或 SimNow 当前时段/网络策略未开放。

## 本次工程修复

- 修复 `examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py` 中重复启动 `EventEngine` 的问题。
- 原因：`MainEngine(event_engine)` 初始化时已经会调用 `event_engine.start()`，探针脚本再次调用会触发 `RuntimeError('threads can only be started once')`。
- 修复后脚本能够进入真实连接尝试阶段。

## 连接探针结果

- 命令：`bash examples/portfolio_backtesting/run_ctp_stage177_simnow_readonly_probe.sh --connect --wait-seconds 30`
- 结果：
  - `vnpy_ctp_import_available=true`
  - `gateway_import.ctp_gateway_import_available=true`
  - `missing_required_env=[]`
  - `real_order_enabled=false`
  - `order_api_called=false`
  - `status=connected_or_attempted_readonly`
  - 事件日志：仅 `连接登录 -> CTP`
  - 账户/持仓/合约/订单/成交 CSV：无数据行

## TCP 前置探测

- `180.168.146.187:10130`：timeout
- `180.168.146.187:10131`：timeout
- `180.168.146.187:10201`：timeout
- `180.168.146.187:10211`：timeout

## 安全边界

- `ctp_simnow.local.env` 已作为本机私有配置保存，使用 `*.local` 忽略规则，不进入 git。
- `ctp_simnow.example.env` 中账号密码已清空。
- 本阶段没有任何下单调用。

## 过拟合反思

否。本阶段是 CTP 连接链路验证，不改第78策略参数、不改变交易逻辑、不筛选收益结果。

## 继续价值反思

有价值，但下一步应先解决网络/时段/前置地址可达性，而不是继续改策略。只有 CTP 可稳定登录后，才值得接 Stage78 影子盘账户对账。

## 后续规划

1. 在交易时段或 SimNow 官方可用时段重试。
2. 换网络重试，例如家庭网络、手机热点、关闭公司代理/VPN 后重试。
3. 如仍超时，登录 SimNow 官网确认当前前置地址是否变化。
4. 前置 TCP 可达后，再运行 60 秒只读探针，目标是拿到账户、合约或明确的 CTP 错误回报。
