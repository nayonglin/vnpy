# C9 官方正式候选晋升闸门 v1

- 更新时间：2026-06-16 12:57 CST
- 研究线：`futures_trend_stage819_intraday_rules`
- 当前候选：`official_candidate_stage847_c9_30w_stage819_05r_stop_retry_once_v1`
- 当前实盘默认：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 前任资金口径：`official_live_stage847_c9_30w_stage819_05r_stop_retry_once`
- legacy 前任实盘默认：`official_live_stage372_20w_recovery_sleeve`
- 结论状态：C9 已按用户 operator override 切为 live default；后续真实报单仍必须走执行 SOP。
- 执行边界：本文件记录 C9 晋升闸门状态；当前已完成 live default 切换，但本文件不连接 CTP，不调用下单。

## 已接受事实

1. C9 的旧数据硬伤已修复：Stage900 补齐 Stage898 指出的 8 个 entry-day 分钟K缺口，Stage898 复审 `metric_fail_count=0`、`p0_fail_count=0`、`c9_open_missing_full_minute_entry_day_count=0`。
2. C9 的右尾收益有材料性：Stage863 全周期期末权益 `51,297,786.20`，总收益 `16,999.2621%`，Sharpe `1.6404`。
3. C9 的回撤尾部必须显式接受：Stage896 完整 3 年窗口最差回撤 `-56.1208%`，DD40/DD50 `4/1`，broker100 `2`；Stage899 月度起点全路径最差回撤 `-58.0872%`。
4. C9 不是 Stage372 的低风险替代：相对 Stage372，C9 Stage896 收益胜 `7/7`、Sharpe 胜 `6/7`，但回撤只胜 `1/7`，broker10 胜 `0/7`。
5. C9 的冷启动体验可接受但不完美：Stage899 月度起点 `101` 个中 `99` 个曾转正，成熟 1 年以上 `89/89` 曾转正且当前全部正收益；未转正窗口仍有 `2026-04`、`2026-05` 两个近端样本。

## 晋升阶段

| 阶段 | 状态 | 说明 |
| --- | --- | --- |
| 候选冻结 | 已完成 | 新增 C9 官方候选配置，冻结 30w、Stage819 基底、C2 stop、broker10 cap、0.5R stop/retry once。 |
| primary candidate 切换 | 已完成 | 官方 manifest 的 primary official candidate 指向 C9；live default 已为 C9/15w。 |
| 数据完整性 | 已完成 | Stage898 P0 清零，旧 8 笔分钟K缺口不再作为否决理由。 |
| 风险接受 | 已完成（operator override） | 用户已明确表示能接受 C9 回撤，并要求切到实盘默认；系统记录为高风险 operator override。 |
| 注册后 A/C | 部分完成 | Stage079 已完成候选注册；Stage080 已用 live default 入口跑 C9 shadow。后续仍建议保留 Stage372 对照报告。 |
| 最新 shadow | 等待 6/16 日线完成 | Stage094 已把官方 shadow 起点切为 `2026-06-16`；当前 12:56 最新完成日仍为 `2026-06-15`，系统 fail-closed 等待。 |
| dry-run | 待完成 | 6/16 cold-start shadow 产生 pending 后，先做只读账户/持仓 gate，再做 dry-run，要求 `order_api_called=0`。 |
| 工程化 | 部分完成 | 已新增 Stage901 live shadow runner，并处理 C9 profile 依赖 Stage660 official spec 的污染问题；长期仍建议把 C9 wrapper 从研究脚本中工程化。 |
| 实盘切换 | 已完成（配置层） | `OFFICIAL_LIVE_VERSION` 已切为 C9/15w；真实报单尚未开始，必须另走 SOP。 |

## 硬闸门

- `OFFICIAL_LIVE_VERSION` 当前为 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`；C9/30w 仅作为 previous capital profile，Stage372 仅作为 legacy previous live default 和风险对照。
- `OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE` 当前为 `2026-06-16`；旧 `2026-01-01` YTD shadow 只能作兼容验证，不能作为实盘执行依据。
- 最新 shadow 若出现 P0 数据缺口、指标无法复现、final-day pending 丢失、信号计划与 diagnostics 冲突，停止晋升。
- dry-run 若出现真实下单 API 调用、账户/持仓快照过期、risk level 为 `review` 但仍尝试新开仓，停止晋升。
- CTP/SimNow/券商虚拟盘只在用户明确要求时进入；进入前必须先过 read-only env/runtime gate。
- 任何以 R 倍数、重试次数、月份、品种、方向、窗口长度继续调 C9 的行为，视为过拟合风险上升，不能作为晋升依据。

## 风险接受口径

- 这不是低回撤版本；它是高右尾、高波动、高保证金压力的正式候选。
- 用户已表达能接受 C9 回撤，并在 2026-06-15 21:52 CST 前后要求切为实盘默认；2026-06-16 12:57 CST 又在实盘账户补齐 15 万后要求切为 15w 资金口径。执行口径应视为接受历史 `-58%` 月度起点最大回撤、broker10 曾超过 `100%`、近端起点可能需要数月转正这些风险。
- 当前已做 live default 配置切换和 15w 账户匹配；真实执行仍建议先以 6/16 cold-start shadow/paper 确认近期执行语义，再讨论资金分层、出金/锁盈或保证金压力 fail-closed 规则。

## Stage094 15w 当前状态

- 当前版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 当前资金口径：`150000`
- 当前 shadow 起点：`2026-06-16`
- 只读账户：`balance/available=150000.449813`
- 只读持仓：`confirmed_flat`
- 订单 API：`0`
- 2026-06-16 12:56 CST 目标日解析：最新完成日 `2026-06-15` 早于 shadow 起点，状态 `target_date_before_live_shadow_start_waiting_fail_closed`
- Stage909 plan-only：确认将使用 `--analysis-start 2026-06-16 --target-date 2026-06-16`

## Stage901 历史 YTD shadow

- 区间：`2026-01-01 -> 2026-06-12`
- 期末权益：`265,860`
- 总收益：`-11.38%`
- 最大回撤：`-14.8955%`
- Sharpe：`-1.1331`
- 总滑点：`3,860`
- 总交易次数：`27`
- 非零日胜率：`45.7143%`
- max broker10：`54.8506%`
- 风险层级：`normal`
- 目标日信号计划：`MA609.CZCE` `Long Open` `12` 手，理论价 `3029`，这是历史回放成交记录，不等同于下一交易时段待处理指令
- target-date 后 pending：`MA609.CZCE` `Short Close` `12` 手，理论价 `3010`，原因 `long_risk_cluster_heat_deleverage`
- 当前影子持仓：`MA609.CZCE` 多单 `12` 手，2026-06-12 收盘价 `3010`，估算保证金 `43,344`
- 下单状态：`order_api_called=false`

## 反思

- 过拟合反思：当前 live default 切换本身不是新增过拟合，因为没有新增参数、没有按 2026 年亏损或目标日信号救参；但这是一次明确的风险接受，不能再用回测高收益掩盖左尾。
- 继续价值反思：有价值。C9 已进入实盘默认治理面，下一步价值在 shadow、dry-run、账户对账、工程化和 fail-closed 监控，而不是继续调策略参数。
