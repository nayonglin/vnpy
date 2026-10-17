# Stage098：A_OFF 返回后 checkpoint 拒绝的只读定位与最小修复准备

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
