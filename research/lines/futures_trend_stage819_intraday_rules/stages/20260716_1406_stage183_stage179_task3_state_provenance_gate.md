# Stage183 Stage179 Task3 状态 provenance 迁移门禁

- line_id：`futures_trend_stage819_intraday_rules`
- 记录时间：`2026-07-16 14:06 CST`
- 当前模式：隔离 worktree 离线 TDD + 只读独立终审；未加载实盘 env、未连接真实 CTP、未操作 launchctl
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy_stage179_live_reliability` / `codex/stage179-live-execution-reliability`
- 基线提交：`66ea905497fef47dbf6feca2ea600c43191b3fc6`（只关闭当前 heartbeat capability 降级）
- Task3 代码提交：`64e388bb3520e3dce84832d9e62dac65d28180da`
- 当前候选：未提交；冻结 Stage904/905/931 SHA-256 分别为 `91fd7cb6f291219a87b185b97541c6b820faca504d9ec87d9618a67958f2278e`、`6c5002d6e1b687dc840c14bd28024dd28cdb5939b77a157ef8ccb90079675bfe`、`ff711eeee0034197bc8340321eb4515a9436d391d638bd62fb17bd561e8928e7`
- 阶段性质：Stage179 Spec Task3 二次终审纠错；关闭旧持久化风险状态被当前 v1 heartbeat 洗白的 P1，不改 alpha
- 是否重要突破：否；这是跨版本状态迁移与执行授权完整性修复
- 是否触发 A/B：否；没有修改信号、AI 池、止损/重进场阈值、方向、手数或资金参数
- 是否连接 CTP：否；测试输出中的 CTP 登录/订阅来自 fake gateway
- 下单/撤单 API 次数：`0/0`

## 前序结论纠正

- Stage182 的 `P0=0、P1=0` 结论已撤回：三元水位虽能识别当前 snapshot 淘汰，却允许字段全缺自动走 legacy。
- 提交 `66ea9054` 关闭了上述当前输入降级，但第一轮“P1 已关闭”仍不完整；第二轮对抗审查复现了持久化状态 laundering：
  - 旧 `initial_progress_latched` 已永久撤销初始止损；升级后即使新 feed 触发 session gap，仍返回健康的 `watch_progress_hit_no_initial_stop`。
  - 旧 `retry_reclaim_latched` 在同 feed fresh v1 输入下会直接恢复 `retry_open_dry_run`，把旧行情授权洗白成新的增风险 open。
  - 旧 `retry_open` 已形成真实风险暴露；不能健康 watch，但 adverse protective close 也不能被迁移门禁挡住。
- 因此 Task3 继续保持 in-progress，直到本次冻结 diff 的独立终审给出 `P0=0、P1=0`。

## 外部调研与判断

- Apache Kafka Protocol：<https://kafka.apache.org/42/design/protocol/>。不支持的协议版本应明确失败，不能由字段缺失静默猜测兼容能力。
- RFC 8446 TLS 1.3：<https://www.rfc-editor.org/rfc/rfc8446>。协议把 downgrade protection 作为版本协商不变量。
- Kubernetes Storage Version Migration：<https://kubernetes.io/docs/tasks/manage-kubernetes-objects/storage-version-migration/>。改变持久化对象 schema 后需要主动重写/迁移旧对象，不能把当前 reader 版本等同于历史对象已迁移。
- Python `collections.deque`：<https://docs.python.org/3/library/collections.html#collections.deque>。有界队列只保留后缀，留存行不能证明已淘汰前缀未触发风险条件。
- 我的判断：当前 heartbeat v1 只能证明当前 snapshot；永久止损豁免和 retry open 授权必须把当时的 coverage provenance 原子写入状态。旧状态不可自动重置，也不可被新 heartbeat 洗白；风险增加一律阻断，已暴露仓位保留风险降低 close。

## 本次版本变更

- Stage608：authoritative heartbeat 继续由同一公共 builder 在 `starting/running/clean_stopped` 三态发布 exact integer `symbol_eviction_watermark_schema_version=1`；新增三态分支回归。
- Stage904：
  - v1 progress/reclaim transition 原子持久化 `risk_transition_tick_coverage_provenance`；
  - provenance 绑定 state identity、record schema、eviction schema、feed session、committed snapshot generation、heartbeat revision、目标 durable/first-buffered/evicted cursor、transition phase/reason/time/feed/sequence；
  - canonical SHA-256 同时写入 provenance 与唯一匹配的 transition row，用于状态内部一致性和篡改检测；它不是外部签名，也不提供来源认证，不能抵抗能同时重写状态与摘要的主动伪造者；
  - `initial_progress_latched`、`retry_reclaim_latched` 缺失/legacy/篡改 provenance 时输出 P1 manual migration block，清空 `intent_role/action_id`；
  - `retry_open` 缺 provenance 时 neutral 路径 `retry_block`，adverse 路径仍保留 `close_dry_run`，并携带 P1/manual metadata；
  - `_apply_state_to_position_action` 与 `_advance_flat_states` 都执行 gate，避免 broker represented/unrepresented 两条路径不一致；
  - target `symbol_stream_sequence` 必须 exact-int 且等于 durable cursor；风险 transition 还交叉绑定 committed generation 与实际 retained target range。
  - 所有 action 明确输出 numeric `manual_intervention_required=0/1`，不再让健康 retry-open 依赖消费者对缺失字段的隐式默认。
- Stage905：
  - 传播 `manual_intervention_required`、`risk_alert_level`、`migration_blocker` 与 operator action；任何 manual/migration/P0/P1 open 一律 fail-close；
  - retry open 只接受精确 `intraday_monitor_retry_open_dry_run`、既有 Stage904 action ID 与正确 retry-open role，不再从缺失身份合成可执行 open；manual flag 只接受数值 `0/1`，字符串、布尔、缺失或其他值都不能授予开仓权限；
  - close 仍接受风险降低状态与 initial/retry stop role，并把审计字段带入 order request。
  - ready `order_request_json` 同时固化 intent ID、source、target、monitor run 与身份字段，并公开最终 request price/volume，供 Stage931 做行与 payload 交叉绑定。
- Stage931：
  - live-real 对 Stage904 retry open 独立重读当前 Stage904 summary，要求同 target、同 monitor run、30 秒内新鲜、精确 retry-open 状态且无 manual/migration/P0/P1；
  - 每个风险增加 child order 在真正调用 `send_order` 前再次重读并绑定当前 Stage904；CTP 登录、O-P-O、重定价或排队期间状态改变会在 API 前阻断；
  - 再校验 canonical manual flag、非空且一致的 intent/action ID 与精确 retry-open role，避免已落盘 Stage905 行被降级或篡改后补权；
  - live-real 在任何 scope/Stage927 override 前校验 Stage905 ready 行与 payload 的 source/target/symbol/exchange/direction/offset/volume/price/reference/action/cycle/role/manual 一致性；伪装成 close 或 Stage901 的 OPEN payload fail-close；
  - `reduce-close-only` 只有在顶层行与 payload 都证明是 Stage904 close 时成立，pre-send 再按实际 `OrderRequest.offset` 防御身份混淆。
  - strict selected close-only 成立后，artifact gate 只审选中的减险集合；无关损坏 open 不得饿死合法 close。普通/open 模式继续审全量。
  - close-only 选择忽略无关 open blocker，保留风险降低可达性。
- 新增参数：无生产参数。既有内部离线兼容参数仍为 `allow_legacy_offline_watermarks=False`，Stage930/官方 CLI 无开启入口。
- 修改参数：无。
- 删除参数：无。
- 删除行为：删除“当前 v1 heartbeat 自动洗白旧风险状态”的路径。

## TDD 与验证

- RED（修复前真实失败）：
  - old feed legacy progress -> new feed current v1：仍健康 watch；
  - legacy retry reclaim -> current v1：仍产生 `retry_open_dry_run`；
  - current v1 progress：状态缺 provenance；
  - unproven retry-open neutral：仍健康 watch，缺 manual metadata。
- GREEN：
  - migration focused `4/4`；
  - provenance round-trip/tamper focused `2/2`；
  - Stage904 全量 `53/53`、Stage905 全量 `8/8`、Stage931 全量 `49/49`；
  - Stage608 + Stage904 + Stage905 + Stage931 联合 `255/255`，用例耗时 `27.637s`、墙钟 `29.21s`；
  - `py_compile` 与 `git diff --check` 通过。
- 冻结 SHA-256：
  - Stage608 producer：`d8148efa9e92ba4116ca302d17cdb766099e6720a0c52cc1a584bf67a9582bc9`
  - Stage904 monitor：`91fd7cb6f291219a87b185b97541c6b820faca504d9ec87d9618a67958f2278e`
  - Stage905 intent builder：`6c5002d6e1b687dc840c14bd28024dd28cdb5939b77a157ef8ccb90079675bfe`
  - Stage931 submit adapter：`ff711eeee0034197bc8340321eb4515a9436d391d638bd62fb17bd561e8928e7`
  - Stage608 tests：`e021782216341171c68ff9232113a50e5985c579ecc5d0aa33554c5cd1c30287`
  - Stage904 tests：`6fd4fe73fce4ede16adf3bd7591560651948137ee3212ef0af4fa3fded338d05`
  - Stage905 tests：`5ff74f5a05a88f3a941a6c21db539c92e4e1baaf73675fd16a6c0c3b3fbf0334`
  - Stage931 tests：`4c9810551e6db72414b018062676704bcd4e89021855870e9750a72b2d0a5955`
- 独立终审：两位只读审查者均复核最终 SHA 并给出 `P0=0、P1=0、P2=0`；各自独立跑通 `255/255`，并定点复验 producer→consumer、row/payload masquerade、TOCTOU、actual offset 与 close-only isolation。

## 回测结果

- 本阶段未运行策略回测；以下指标均不适用：
  - 期末权益：不适用
  - 总收益：不适用
  - 最大回撤：不适用
  - Sharpe：不适用
  - 总滑点：不适用
  - 总交易次数：不适用；验证期间订单/撤单 API `0/0`
  - 胜率：不适用
- 没有新增、修改或删除任何 alpha 回测结果。

## 当前结论与后续

- 当前结论：Task3 冻结代码具备合入条件；这只表示离线代码门禁关闭，不代表已部署、已激活或实盘通路已证明。
- 激活硬门槛：Task8 必须扫描现存 Stage904 state store；任何缺当前 provenance 的 progress/reclaim/retry-open 状态都阻断 activation 并要求人工核验，不得自动重置。
- 后续：提交独立修复与本记录，再进入 Task4 trace/SLA；Task4-13、LaunchAgent/runtime、官方资金口径、严格 0/0 只读 CTP、SimNow 未全部通过前禁止真实报单。
- 已知保守性：新 state 的 `last_consumed=0` 对纯入场前历史 eviction 可能锁存 gap，影响可用性但不错误放行；继续列为 P2。

## 过拟合反思

- 运行前：否。
- 运行后：否。
- 原因：约束来自持久化状态版本、消息覆盖和执行风险方向，不使用收益表现或今晚 JM 的单一路径调参。

## 继续价值反思

- 运行前：是。
- 运行后：是。
- 原因：若旧状态能被新输入洗白，低延迟链路会加速错误授权；先关闭迁移 P1 才有价值继续做 SLA 与实盘灰度。

## 记录归属

- 是否更新 `LINE.md`：否；同线并行阶段只写唯一 stage 文件，合入时统一整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否；尚未达到正式候选激活门槛。
