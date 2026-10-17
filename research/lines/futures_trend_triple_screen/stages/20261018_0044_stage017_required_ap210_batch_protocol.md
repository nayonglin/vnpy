# Stage017 补齐受影响AP210完整session的单次公开历史流

- line_id：futures_trend_triple_screen；冻结时间2026-10-18 00:44 CST。
- 目标：为Stage016取得AP210.CZCE/2022-04-06真实completed替代；同批可纳入Stage015剩余真实需求在2022-03-28至04-06内的其他session，最多8合约/20000分钟。AP210强制包含，其余合约按代码排序分包，不看PnL。
- 调研判断：复用Stage012已实测公开get_kline_serial(10000)正常暖机机制。普通多合约价差序列因官方API第4条的窗口不重合限制，不能保证相隔数月到期合约回到所需历史，本阶段不尝试这条捷径、不剥授权或私有网络调用。

## 固定操作

1. 在连接前冻结target/grid/原CSV七字段参考、工具与Stage012 collector核心、SDK及协议SHA。一个正常TqApi/TqBacktest＋本地TqSim，provider start为2022-04-07 09:01、end09:05；每个真实合约独立序列，禁止list对齐丢时戳。
2. 复用已测BatchCollector.frames/observe，不修改冻结Stage012代码。初始全10000历史扫描、只接受更晚K线后继；最后形成行不接收。完整session网格、唯一/合法OHLCV/OI及原CSV七字段须匹配。与旧source859差异不在下载阶段覆盖。
3. 570秒软/600秒硬、8合约/20000目标分钟，DEVNULL原始SDK输出、仅safe_error，不重连/不自动重试、不写旧数据、不下单/CTP/金融。部分完成/拒绝如实保留。
4. 可记录本次正常登录的`tq_dl`许可布尔：仅调用未改SDK内部自身的只读授权检查（与DataDownloader使用同一逻辑），不读出或打印grants内容、token或用户信息，不更改任何检查。该项只判当前是否具备批量范围下载许可，不以旧记忆当当前权限，也不因此自动转接口下载。
5. 只把本次原raw/evidence/quality和未变输入交给独立审查；AP210合格后Stage016才真实构建。金融attempt仍4/完成1，不能因下载成功启动C0或称策略改善。

小测试复用原collector并验证AP必含/预算/后继与输入门；真实连接由root审preflight后唯一执行。过拟合判断：否，来源缺陷与剩余数据决定批次；继续价值：是，修复已经证实影响盘中价格资格的源，而非为截断收益救参数。
