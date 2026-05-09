# Stage180 SimNow 账号更新后重试

- 时间：2026-05-08 20:12 CST
- 研究线：`futures_trend`
- 工作模式：day
- 阶段：Stage180
- 主题：用户更新 SimNow 账号后重新迁移本机配置并重跑只读探针

## 本次结论

用户更新了 SimNow 账号信息。本阶段将 `ctp_simnow.example.env` 中非空字段迁移到本机私有配置 `ctp_simnow.local.env`，并清空模板中的敏感字段。重跑 60 秒只读探针后，新账号已生效，但仍未收到 CTP 登录成功、登录失败、账户、合约或错误回报。

因此本次结论不是“账号仍未配置”，而是：账号已被脚本识别；当前阻塞仍在 SimNow 前置连接/服务回报层。

## 配置处理

- `CTP_USERID`：已从模板迁移到 `ctp_simnow.local.env`
- `CTP_PASSWORD`：模板为空，因此保留 `ctp_simnow.local.env` 原有密码
- `SIMNOW_FRONT=7x24`
- `ctp_simnow.example.env` 的 `CTP_USERID` / `CTP_PASSWORD` 已清空
- `ctp_simnow.local.env` 权限已设为 `600`
- `.gitignore` 已包含 `*.local.env`，本机私有配置不会进入 git

## 探针结果

- 命令：`bash examples/portfolio_backtesting/run_ctp_stage177_simnow_readonly_probe.sh --connect --wait-seconds 60`
- `missing_required_env=[]`
- `real_order_enabled=false`
- `order_api_called=false`
- `status=connected_or_attempted_readonly`
- 用户掩码从上一轮 `13***11` 变为 `26***29`，说明新账号已生效
- 日志仅记录：`连接登录 -> CTP`
- 账户/持仓/合约/订单/成交 CSV：无数据行

## 关于“是否因为没开盘”

可能部分相关，但不是唯一解释：

- `trading` / `trading2` 仿真前置可能更依赖交易时段。
- 当前使用的是 `SIMNOW_FRONT=7x24`，理论上应更适合非交易时段连通性测试。
- Stage179 TCP 探针显示多组 SimNow 前置均不可达或拒绝连接，因此当前仍应优先排查网络、前置服务窗口、新账号激活延迟，而不是继续修改策略。

## 过拟合反思

否。本阶段只验证 CTP 连接链路，不改变第78策略参数、不新增收益筛选、不改变交易规则。

## 继续价值反思

有价值。Mac 实盘目标的底层前提是 CTP 连接可稳定登录；在该层未通过前，继续优化策略或影子盘报表意义有限。

## TODO

1. 在 21:00 后夜盘时段重试 `SIMNOW_FRONT=7x24`。
2. 如果仍无回报，切换手机热点/家庭网络重试。
3. 如官网个人中心显示账号刚注册，可等待 SimNow 激活窗口后再试。
4. 前置可达后，再进行 60 秒以上只读探针，目标是拿到账户、合约或明确错误回报。
