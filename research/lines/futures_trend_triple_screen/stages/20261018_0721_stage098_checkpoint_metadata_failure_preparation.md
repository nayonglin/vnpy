# Stage098：A_OFF checkpoint 元数据误拒定位与 Stage099 合同最小修复

> 本文件保留 07:21 的修复前法证，后半追加 root 07:23 Stage099 合同授权后的实施收据。当前状态：两个新定向测试已 GREEN，源码已冻结并交 root 安排 Stage100 独立复核；未运行新金融。原准备版本完整保存于 `outputs/stage098_checkpoint_metadata_fix/stage098_preparation_before_implementation.md`，原 SHA `eac46e40d6d5af2f465176759acba6f047d9edcc398aae2a7e8a7733c26f67c7`。

- line_id：`futures_trend_triple_screen`。
- 记录时间：2026-10-18 07:21 CST。
- 工作区：`/Users/mac/Desktop/fian`；当前来源身份由真实 preflight 记录为 `4e439c2e5d653d4171c4396afdc2aad037c547c7`。本阶段没有运行 Git 命令。
- 阶段性质：修复前法证与设计，尚未修改冻结源码；不是重要 alpha 突破。
- 授权边界：root 要求精确定位后等待明确修复合同；不运行金融、B_OFF、旧测试、整库 preflight、网络、训练、预测、CTP 或订单，不另派 agent。

## 外部调研与判断

本次为已有真实失败的本地只读排障，遵守 root 本轮禁止网络的范围，没有新增外部调研。依据实际终态、同字节绑定后的 JSON/pickle、当前冻结 guard 及 runner 的实际接线判断，不凭历史模型或绩效反推修复。采用 systematic-debugging 的先确定根因再改源原则；尚未进入修复与测试阶段。

## 真实终态及字节绑定

实际工具 `13114`、终态 chunk `8c75d9`，A_OFF attempt1，run_id=`982636a096884e7e9610b1ad49eb1ae1`，exit `1`。Stage096 明确记录 `engine_returned_before_checkpoint=true`，失败位置 `save_raw_checkpoint._account_only(payload)`，错误 `ValueError(checkpoint_forbidden_engine_or_history)`。

| 材料 | SHA256 |
| --- | --- |
| `outputs/stage096_A_OFF_actual_failure/actual_tool_terminal.json` | `8eb4dfbfd675102a01ad4f6cf7b3aa8cfb814e590f00a396935a088d753fb085` |
| `outputs/stage065_pairwise_off_account/A_OFF/preflight_used.json` | `4612f307b30e6917d227d624cdbf35c9ff74238a73cd1d0bd7a8267a53d92bf5` |
| 同 owner `run_context.json` | `46126a8af641d76e47978bd10d5aba9b7a5f8072af24ef7f0f781b0f7f1db7f7` |
| 同 owner `run_failure.json` | `6a21416440f3f3441599435ebf55c1ae688006d865d5683a537fea5af2c3d082` |
| 同 owner `failure_capture.pkl.gz` | `443216dc4e7b3b2550f97aeafee33c9f4376a94aa1513ad3f8e19f5c71cfd96f` |

JSON 均用读取并 SHA 验证后的同一 bytes 解析；pickle 先核对 Stage096 与 `run_failure.json` 两处 capture SHA，再对同一 bytes 解压。首次严格禁止任何 global 的受限解包按预期在 pandas Timestamp 上停止；随后只允许 `pandas._libs.tslibs.timestamps._unpickle_timestamp` 这一真实 global，拒绝其余 class/global。使用 `.py311/bin/python`，在导入 pandas 前采用 022 的 ROOT/VENDOR/PROJECT/FROZEN_SITE 顺序；实际 pandas 为冻结路径下 2.3.3，没有调用 `configure_runtime` 的目录写入部分，没有导入模型或调用 engine。检查输出只报告结构、类型、长度与文件存在性，没有计算 partial 绩效。

## 精确合法 metadata 碰撞

实际碰撞路径是：

```text
payload.preflight.ai_pool_audit.strategy
type = str
value = ai_top10_plus_fu_official_live_v1
```

这不是 strategy 实例。runner 第 258—261 行调用既有 `stage249_historical_replay.audit_historical_ai_pool` 得到 `ai_audit`，并验证月 AI 池 eligibility SHA；第 326 行原样放入 `preflight.ai_pool_audit`。该字符串是保留月 AI 池的身份审计元数据。

当前 checkpoint 第 196—215 行递归 `_account_only`，第 199 行无论值类型、来源、上下文，只要 Mapping 的 key 是 `strategy` 就在第 200 行抛同一个异常。`save_raw_checkpoint` 第 239—241 行已经检查 payload 的 preflight 与已落盘 preflight 相等，但随后第 246 行仍把这个合法字符串按禁止对象拒绝，且第 247—249 行创建 raw 的动作尚未发生。

只读最小复核（不是旧 suite，也不是金融重跑）：将真实 preflight bytes 核 SHA 后解析，直接传入当前 `_account_only(preflight)`，得到相同 `ValueError('checkpoint_forbidden_engine_or_history')`；仅在内存 deepcopy 中删去 `ai_pool_audit.strategy` 后，整个 preflight 通过同一个未修改 guard。遍历该 JSON 的所有 Mapping 键，六个禁止名仅此一处；run_context JSON 没有这六个键名的碰撞。

这个诊断证明了真实普通 metadata 的确定性误拒。由于完整返回 payload 未落盘，本阶段不冒称已检查丢失的所有 frame cells，也不冒称排除此后可能出现的其他错误。

## 保存边界与恢复判断

实际 capture 压缩 `430064` bytes、解压 `2471879` bytes。外层只有 `schema/partial/run_context/capture`；内部 partial 的实际字段为：

```text
capture, ordered, actual, effective_off_policy,
wait_audit, resolver_audit, qualification_audit, isolation_audit,
input_fingerprints, failure_phase
```

`capture` 内有 `usage=817`、`equity=1697`、`trades=817`、`minute_requests=500`、`anchor_requests=534`、`failures=0`、`weekly_gate=0` 条；`actual=1`、`effective_off_policy=1`、`input_fingerprints=5274`；A 的 `ordered` 为真实 `None`。这些是局部结构计数，不是完整账户资格或收益结论。

实际没有保存 `combined`、`frames`、`spec`、`parameters` 或独立 `actual_trade_identities` 字段。runner 第 406—414 行已收到 `combined,frames,spec` 后尝试 raw 保存；但 except 第 441—444 行重新构造的 partial 只保留上列字段，丢弃返回的账户表。native 847 第 474—525 行真实生成的 daily/combined、positions、entry_risk、entry_candidates、trade_events、intraday/c2/stop_retry、rollover/long_signal diagnostics、pending_orders 等并没有出现在该 failure capture。

owner 中 `checkpoint/raw_account.pkl.gz`、`raw_manifest.json`、`validation_seal.json` 均不存在；`engine.log` 实际为 0 bytes。不能以成交、usage 或 estimated equity 推造缺失的 daily PnL、margin、positions 和完整 frames。本阶段没有证明等价纯恢复，完整绩效及正式比较仍为 **N/A**；097 的独立恢复审查由 root 管理。

另一个确定的错误是 failure phase：第 380 行初始为 `engine_not_returned`，第 415 行只有 raw 保存成功后才切到 `post_engine_validation`。所以真实 capture 的 `failure_phase='engine_not_returned'` 是置位太晚导致的阶段误标，不能覆盖 Stage096 对 engine 已返回的实际终态确认。

## 待 root 明确合同后的最小设计建议

1. 对已被 context/preflight 同字节绑定约束的合法 metadata 路径提供窄处理：仅允许 `payload.preflight.ai_pool_audit.strategy` 为纯字符串，并继续正常递归其余内容；不得全局放开 `strategy` 键，不跳过整个 preflight，不放开 engine/history/cache 对象、DataFrame attrs/object cells 中的隐藏对象或其他非账户类。具体实现形式由 root 确认后再改。
2. 在任何未来金融启动前，用真实 preflight 的普通 metadata 做该兼容性门，避免跑完才发现确定性元数据冲突。只证明数据结构可保存，不代表金融 readiness。
3. engine 返回后立即记录独立的返回阶段，先形成一份完整返回 payload，再做 raw 持久化；异常通路应保留已经取得的合格账户表及未 seal 身份，不能把“返回但 raw 失败”退回“engine 未返回”。任何对象安全检查仍必须 fail-closed；不得为了落盘把 engine 或分钟全集塞进 pickle，也不允许给不完整/失败材料补 seal。
4. 修改 checkpoint 后，runner 的冻结 checkpoint SHA 必须显式同步；旧 attempt1 owner、旧 context/source snapshots/失败 capture 必须保持原字节。后续是否另一次账户运行只由 root 决定，不在本次授权内。
5. 修复测试先以这个真实 metadata 形状的微型 fixture 有效 RED，再做最小 GREEN，覆盖危险对象仍拒绝和已返回经济表在 checkpoint 故障后的保留边界；不通过重新跑金融来验证代码修复。

## 冻结源码核验与本阶段变更

下列当前源码 SHA/bytes 与 A_OFF 已落盘 `run_context.source_bindings` 实际相等：

| 源码 | SHA256 | bytes |
| --- | --- | ---: |
| `tools/stage065_account_checkpoint.py` | `7e5a265a23b8fce871c895292e0738831604eefb9a341f7a83bd0320a68cf15b` | 27561 |
| `tools/stage065_run_pairwise_off.py` | `d83b4cc20c09e07e9bcecfd541ba223fbf602db194430e6ed307a80e5e25ed09` | 34458 |

现有 test 文件 SHA 为 `ffba7e347075cc966a71f3177e5f853eb4ea13062963ff74b2b37f93639d0719`；本阶段没有修改或运行它，也不把此前有限测试边界表述为本次真实账户成功。

- 新增：仅本 Stage098 准备记录。
- 修改/删除源码、参数、限额、策略 alpha：均无。
- 新增金融运行、测试 suite 运行、模型调用、B_OFF 启动：均 0。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均 N/A，无完整账户 checkpoint。
- 不修改 LINE、registry、memory/backlog；不 stage/commit/push；不申请新 reviewer。

## 反思与后续

运行前后过拟合判断均为否：本次只定位确定性序列化边界错误，不查看或按收益选择参数，不把 partial 结果作为 alpha 反馈。继续价值判断均为是：阻止合法 metadata 再次导致昂贵账户返回结果丢失，并如实标明不可恢复的证据缺口，有利于原定完整 2020—2026 更高收益且更低回撤的公平验证。目标本身尚未被证明，不能只胜弱基准，也没有任何生产完成声明。

下一步等待 root 明确最小修复合同及 097 独立恢复意见；在此之前冻结源码和失败 owner，不启动 B 或重跑 A。

## Stage099 07:23 合同授权后的唯一修复波次

root 随后明确授权按 `stages/20261018_0723_stage099_checkpoint_repair_run_family_contract.md` 执行本轮最小修复，不再等待 097 同义长文。以下是实际实施结果，修复冻结到分钟的时间见 `outputs/stage098_checkpoint_metadata_fix/fix_source_manifest.json` 的 `recorded_at`。本次只应用 TDD、executing-plans 和 verification-before-completion 的相关流程；root 明确禁止运行旧三测/旧 suite、Git 或另派 agent，故没有执行 skill 中与本次授权相冲突的全套验证、提交或自主派审步骤。Stage100 由 root 另交独立作者。

### 先保留再修改

`outputs/stage098_checkpoint_metadata_fix/before_manifest.json` 登记了 12 个真实文件的 ABS 路径、SHA、bytes 和快照：checkpoint、runner、087 scope/provider、原 integration test，加真实 096 terminal 及旧 A owner 的 context、preflight、failure JSON、failure capture、engine.log、attempt_started。各快照由读取的原始 bytes 写入，未改写旧 owner 或原证据。

完成后逐字检查：旧 owner 六文件、096 terminal、原 integration test 与 provider 均与 before 快照完全相等。087 scope 当前源码也与 before 源做精确字符串差分，确认只替换 `ACCOUNT_ROOT` 与 `PROTOCOL` 两行常量，任何其余内容都没变。旧 A_OFF attempt1 仍为失败，不删除、不清空、不重命名，也不向其补 raw/seal。

### 实际源码变化

1. **checkpoint guard**：递归携带结构路径与根 preflight 的 `active_parameter_identity.strategy_version`。唯一例外是精确路径 `preflight.ai_pool_audit.strategy`，且 `type(value) is str`，同时等于根绑定策略版本和固定已核实身份 `ai_top10_plus_fu_official_live_v1`。错误路径、任意其他字符串/对象、缺少或改变根身份都不能获得例外。Mapping、list/tuple、DataFrame attrs/index/columns/object cells 和 numpy object 项的递归保留路径前缀，避免对象 cell 藏一份同形 preflight 后重置成合法根路径。原六种危险键名及非账户对象拒绝仍生效；没有扩大允许的对象类型，没有全 payload pickle fallback，没有修改 raw→验证→seal 顺序。
2. **runner prepare**：在真实 preflight（含实际 readiness）构造完成后、返回 prepared 前，直接调用同一个 `checkpoint._account_only(dict(preflight=preflight,spec=asdict(profile['spec']),parameters=_parameters(profile['spec'],metadata)))`。该 guard 使用实际根路径封装，且发生在任何 account dispatch/engine 开始前。checkpoint 冻结 SHA 同步为本次真实值。
3. **返回阶段**：在 `run_profile_once` 实际返回的下一行加入 `phase='returned_before_checkpoint'`，之后才准备 ordered/parameters 并尝试保存 raw。仅修本次误标的一行，不扩 diagnostics 或错误恢复系统。raw 保存成功后的既有 `post_engine_validation` 阶段保留。
4. **新运行族**：runner OUTPUT 固定为 `outputs/stage099_pairwise_off_account`；087 scope 的 ACCOUNT_ROOT 同指新族，PROTOCOL 指 root 的新 Stage099 合同。provider 算法、连接与预算均未改；没有任意 output、自动 retry 或复用旧 owner 的路径。
5. **父失败与历史次数**：TERMINAL_BINDINGS 增加 `prior_A_OFF_checkpoint_failure`，固定真实 096 terminal ABS 路径及 SHA `8eb4dfbfd675102a01ad4f6cf7b3aa8cfb814e590f00a396935a088d753fb085`；原 063/064/原 B 的三项 binding 全保留。`_readiness` 严格要求 `repaired_checkpoint_family='stage099_checkpoint_metadata_fix_v1'`、整数 `global_financial_attempts_before_family=9`、整数 `global_arm_attempt={'A_OFF':2,'B_OFF':1}[arm]`，bool 不能冒充整数。新父 binding 也必须存在且精确匹配，并以同一 hash bytes 读取真实 JSON；旧 readiness 因缺族身份和父失败门而不能重启。

新族各臂的 attempt1 是族内序号；历史仍为全研究 **9 次 financial attempt / 3 个 accepted ledger**，下一真实 A_OFF 是全局该臂第 2 次、下一 B_OFF 是第 1 次，全研究下一次金融为第 10 次。本轮没有执行它们。日期、15 万本金、成本、八项 OFF、月 AI10+fu、0.5R/retry、原 hand/风险/数据资格、1800/7200 和原 provider 连接/packet 预算均未改。095 作者自行同步其被授权路径/pin，本作者未改 095。

### 两个新回归的有效 RED → GREEN

唯一新增测试文件为 `tools/test_stage098_checkpoint_metadata_fix.py`，没有修改或运行原 `test_stage065_pairwise_off_integration.py`，没有运行旧三测或旧 suite。

命令（RED 与 GREEN 同一条）：

```sh
PYTHONDONTWRITEBYTECODE=1 .py311/bin/python research/lines/futures_trend_triple_screen/tools/test_stage098_checkpoint_metadata_fix.py
```

- 首次 fixture 运行：因 macOS 临时目录祖先的 symlink 被真实 `_read_regular` 拒绝，包含 1 个测试环境错误；完整日志另存 `red_initial_fixture_path_error.log`。仅将测试临时目录规范为真实 `.resolve()` 路径后重跑，没有改生产源来迎合 fixture。
- **有效 RED**：工具 chunk `bcffa5`，exit `1`，`Ran 2 tests in 0.647s`，8 个预期 subtest/assertion failures、**0 errors**。真实 metadata 误拒、旧 A owner 被复用、父失败 pin 缺失未拒、修复族/9 次历史/全局臂次数缺门，以及 engine-return phase 误标均实际失败；危险对象原有拒绝已成立，没有故意破坏旧行为制造 RED。
- 随后应用上述最小生产变化。
- **GREEN**：工具 chunk `654a5c`，exit `0`，`Ran 2 tests in 0.423s`，`OK`。完整输出在 `green.log`；源码冻结后未重复运行已完成验证。

两个具名测试分别是：

1. `test_real_096_metadata_and_prepare_prevalidation`：读取固定 SHA 的真实 096 preflight（`4612f307...92bf5`），再从其实际 data_bindings 提取旧 accepted `A_final3/effective_parameters.json` 的 pin，同 bytes 核 SHA 后解析（SHA `e0b45b2f62bc6b5f0b1c49f067c58b7635a5b0145764a9fa77f1348b785d7268`，83553 bytes），应用冻结八键 OFF 投影，检查真实 preflight/spec/parameters envelope 通过同 guard。还从当前真实 prepare AST 提取并执行新增 guard 调用语句，传入同一完整 metadata，确认正确路径传入，错误策略 ID 实际被该调用拒绝；不是复制 prepare 或运行其上游数据加载。
2. `test_dangerous_objects_family_readiness_and_return_phase`：实际 guard 拒 engine/history/history_data/cache、错误路径 strategy、非账户对象、错误类型/ID/根身份、DataFrame 对象 cell/attrs 和 list 中伪装的合法根结构。真实 CLI 在旧 A owner 存在时仍先到新族 readiness 分派的阻断 sentinel，不进 runtime/prepare；实际 `_readiness` 读取临时的明确 fixture 文档，测试真实父证据 pin 与新族次数门，并核 A=2/B=1。临时二源 review 只用于 parser 单测，不是独立复审或金融授权。最后提取真实 execute 中 engine-return→raw 调用这一段语句，以有限返回/强制 raw 故障 sentinel 执行，确认失败阶段为 `returned_before_checkpoint`；未构造真实 engine、未运行 execute_account 或 run_backtesting。

因此这些测试证明的是 guard、预验语句接线、CLI/根 readiness 门与返回阶段的有限边界；**没有执行真实 prepare_account，没有加载整库，没有运行真实账户，没有新金融资格/绩效或数据 provider 启动声明**。所有变更源与新测试还用 Python `compile(raw,filename,'exec')` 做了内存编译，不写 pyc、不运行模块入口。

### 冻结交付（源码先于文档交 root）

| 文件 | 当前完整 SHA256 | bytes |
| --- | --- | ---: |
| `tools/stage065_account_checkpoint.py` | `ff2790a36d8b66d8de7e854c6daf3bd6efd7f275d474f4374883ead66e21fe99` | 28541 |
| `tools/stage065_run_pairwise_off.py` | `1717f2ef30d098f4e503906c032f9b6ddac7aa9b968ae072b60b32b86b0725fb` | 35215 |
| `tools/stage087_off_data_scope.py` | `73c8957f577908b322387aa65a547bd3dc25c6d40e211718bba99fa3f176a3b1` | 52684 |
| `tools/stage087_off_data_provider.py`（未改） | `33b6bca67115e3c8438de768b6e180d055139470fa2b7069b7a4459b1d101b46` | 16901 |
| `tools/test_stage098_checkpoint_metadata_fix.py`（新，仅 2 tests） | `e581f47c4a1c5008487a99d080e7c2c4a8481c1c9a652930808510894e3b67d9` | 11022 |

`fix_source_manifest.json`、`targeted_test_evidence.json`、完整 RED/GREEN 日志、before/after 源码快照及原准备稿都位于唯一 `outputs/stage098_checkpoint_metadata_fix/`。原 integration test 历史 SHA `ffba7e347075cc966a71f3177e5f853eb4ea13062963ff74b2b37f93639d0719` 保持，不把旧已审测试身份覆盖成本次测试身份。当前作者收据不是 Stage100 独立接受收据。

### 结论与执行后反思

已按 root 合同修复确定性合法元数据误拒，并把同 guard 前移到真实 prepare 末端、新族 lineage/readiness 门和本次失败阶段接线。原失败不能完整等价恢复，仍不补造数据或计算 partial 绩效。新族账户 owner 实际创建数 **0**，金融/旧 suite/网络/模型调用均 **0**，生产资格 false；全部新绩效指标 N/A，原完整 2020—2026 更高收益且更低回撤目标未达成。

结束过拟合判断：否，只修正确性与执行身份，不使用收益反馈调参。继续价值判断：是，这次修复及前置预验降低再次浪费完整账户运行并丢失结果的确定性风险。下一步只由 root 安排 Stage100 定向独立复核、保存资产和新真实 preflight/readiness，随后另行明确授权才可开始新族 A/B；本作者交付后冻结源码，不自行运行或继续修改。
