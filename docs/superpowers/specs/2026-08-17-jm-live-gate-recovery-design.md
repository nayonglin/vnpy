# jm 夜盘实盘闸门修复设计

## 背景与目标

2026-08-17 夜盘，官方 C9/15w 影子盘存在 `jm2609.DCE` 多开 2 手的待执行意图，但生产链路在调用报单 API 前 fail-closed。已确认两个独立缺陷：

1. Stage174 只读快照使用带时区的 ISO-8601 时间，例如 `2026-08-17T21:06:18.283886+08:00`；Stage260 只接受旧的空格分隔时间，导致 `snapshot_age_seconds=None`，把新鲜快照误判为不可用。
2. Stage930 用“全部观察品种同时新鲜”作为新开仓提交条件。AP、SI 在当前夜盘不产生 tick 时，会错误阻断行情本身新鲜的 jm。

目标是在不绕过账户、持仓、活跃委托、Stage927 授权和 Stage931 最终询价的前提下恢复 jm 正常自动执行。

## 方案选择

采用候选合约级修复，不采用以下方案：

- 不把快照年龄闸门整体关闭；这会允许真正过期的账户状态进入报单链路。
- 不把 AP、SI 从官方待执行列表删除；它们仍需在各自可交易时段正常处理。
- 不硬编码“夜盘只允许 jm”；换月或交易时段变化后会再次失效。
- 不直接调用 CTP 报单 API；所有真实订单仍必须经过 Stage260、Stage902、Stage905、Stage927 和 Stage931。

## 设计

### 1. Stage260 时间兼容

- `_parse_generated_at` 优先用 Python 3.11 标准库 `datetime.fromisoformat()` 解析 ISO-8601，同时保留旧格式兼容。
- 计算快照年龄时统一 aware/naive datetime：若快照带时区而测试或调用方传入本地 naive `now`，按快照时区解释该本地时间；若两者都带时区，则转换到同一时区后相减。
- 非法时间、未来时间和超过 TTL 的时间继续 fail-closed。

### 2. Stage930 候选合约级行情闸门

- 保留 `_tick_stream_status` 的全品种诊断信息，不伪造 AP/SI 为新鲜。
- `_stage931_submit_blockers` 读取 durable spool 中当前精确候选的 `vt_symbol`。
- 对新开仓，只在以下任一条件成立时阻断：行情 transport 未就绪、候选合约未知、候选合约本身位于 `blocked_new_risk_symbols`。
- 其他非候选品种缺 tick 只保留诊断，不再阻断当前候选。
- 平仓的既有降风险特例保持不变；最终 Stage931 仍要求可执行报价、涨跌停边界、价格 tick 对齐和账户状态复核。

### 3. jm 最终价格

- 不使用影子盘理论价 `1364.5` 作为未经复核的真实成交价。
- Stage931 在 API 调用前重新订阅并读取 `jm2609.DCE` 最新 tick，以买入方向最新卖一价为基准生成 marketable protected limit，并受既有最大滑点 tick、涨跌停、合约最小变动价位和报价新鲜度约束。
- 无最新卖一价、报价交叉、tick 过期、价格超界或任一授权证据不完整时不下单。

## 测试与验证

测试先行，先观察以下回归测试在旧代码上失败，再做最小实现：

1. Stage260 接受带 `T`、微秒和 `+08:00` 的快照时间，并计算有限、非负、TTL 内的年龄。
2. Stage260 对非法、未来和超 TTL 时间继续阻断。
3. 当前 durable 候选为 jm 且 jm tick 新鲜时，AP/SI 缺 tick 不产生 jm 的行情阻断。
4. 当前候选本身缺 tick，或 transport 未就绪时，继续 fail-closed。
5. Stage931 现有最终询价、价格保护、API 计数和成交回调测试全部通过。

部署前运行聚焦测试和完整相关测试。部署只能通过 Stage948 prepare/activate；激活后核对 stable HEAD、manifest、qualification、activation receipt、7 个 launchd labels 和订单 API 证据。

## 生产切换纪律

- 当前夜盘 daemon 与 warm executor 存活时，不并行启动第二套执行器。
- 源码验证通过不等于已生效；必须完成 Stage948 激活并让唯一生产会话加载新版本。
- 切换前再次只读查询账户、持仓、活跃委托和成交，确保 jm 没有人工或其他系统订单，防止重复开仓。
- 真实提交后立即核对 `send_order` 返回、券商委托状态、成交量、成交均价、剩余未成交量和最终持仓；任何证据缺失都进入 fail-closed，不追单。

## 非目标

- 不调整 C9 alpha、AI 池、仓位算法、0.5R 止损或一次重试规则。
- 不补交易日历史订单。
- 不修改 AP、SI 的策略信号或删除其待执行意图。
