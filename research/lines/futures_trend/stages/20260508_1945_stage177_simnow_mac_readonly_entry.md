# Stage177 SimNow Mac 只读入口

- 时间：2026-05-08 19:45 CST
- 研究线：`futures_trend`
- 工作模式：day
- 阶段：Stage177
- 主题：为 Mac 原生 CTP 路线补 SimNow 只读探针入口

## 本次结论

Stage176 已证明 Mac arm64 + `.py311` + `vnpy_ctp==6.7.2.1` 可以导入 `CtpGateway`。Stage177 不改变第78策略参数，不新增回测收益结果，只补 SimNow 仿真/只读连接入口，作为后续接入真实 CTP 前的低风险工程闸门。

## 新增文件

- `examples/portfolio_backtesting/ctp_simnow.example.env`
- `examples/portfolio_backtesting/run_ctp_stage177_simnow_readonly_probe.sh`

## 新增参数

- `SIMNOW_FRONT=7x24|trading`
  - `7x24`：默认，使用 SimNow 7x24 前置，便于非交易时段做连通性测试。
  - `trading`：使用更贴近交易时段的 SimNow 前置。

## 修改参数

- 无。

## 删除参数

- 无。

## 回测结果

- 本阶段不做策略回测。
- 期末权益：沿用 Stage78 正式基准记录 `1,610,900`
- 总收益：沿用 Stage78 正式基准记录 `705.45%`
- 最大回撤：沿用 Stage78 正式基准记录 `-54.93%`
- Sharpe：沿用 Stage78 正式基准记录 `0.661`
- 总滑点：沿用 Stage78 正式基准记录 `100`
- 总交易次数：沿用 Stage78 正式基准记录 `1000`
- 胜率：本阶段未新增统计

## 验证结果

- dry-run 命令：`bash examples/portfolio_backtesting/run_ctp_stage177_simnow_readonly_probe.sh`
  - `vnpy_ctp_import_available=true`
  - `gateway_import.ctp_gateway_import_available=true`
  - `default_name=CTP`
  - `status=dry_run_not_connected`
  - 自动补齐 SimNow 公开字段：`CTP_BROKERID`、`CTP_TD_ADDRESS`、`CTP_MD_ADDRESS`、`CTP_APPID`、`CTP_AUTH_CODE`
  - 缺失字段：`CTP_USERID`、`CTP_PASSWORD`
- 带连接参数但无账号命令：`bash examples/portfolio_backtesting/run_ctp_stage177_simnow_readonly_probe.sh --connect --wait-seconds 3`
  - `status=blocked_missing_env`
  - 未尝试真实连接
  - `real_order_enabled=false`
  - `order_api_called=false`

## 安全边界

- 不写真实账号密码。
- `ctp_simnow.local.env` 使用 `*.local` 忽略规则，不进入 git。
- 只读探针沿用 Stage174 逻辑，`real_order_enabled=false`，`order_api_called=false`。
- 只有用户本机填入 SimNow 账号密码并显式传 `--connect` 时才尝试连接。

## 过拟合反思

否。本阶段是执行链路建设，不调策略参数、不筛选收益结果、不改变品种池或交易逻辑，因此不构成策略过拟合。

## 继续价值反思

有价值。用户目标是最终在 Mac 上跑实盘，SimNow 是真实 CTP 前最便宜、最低风险的连通性验证层；这一层不过，后续真实账户只读和影子盘都没有工程基础。

## TODO

1. 用户在本机创建 `ctp_simnow.local.env` 并填入 SimNow `CTP_USERID` / `CTP_PASSWORD`。
2. 先运行无连接 dry-run，确认默认项完整。
3. 再运行 `--connect --wait-seconds 30`，观察是否产生日志、合约、账户或错误回报。
4. 连接稳定后，将 Stage78 每日影子报告与 CTP 行情/账户只读结果对账。
