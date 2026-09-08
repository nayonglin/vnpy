# 开仓日证据封存 Implementation Plan（Stage233）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐未来 owned 新开仓的券商 OpenDate 证据，使真实账户定量后的夜盘仓位可在重启及跨日后正常全平。

**Architecture:** Stage931 将已验证的开仓前空仓基线绑定到现有 durable native identity；成交后用有界、串行、完整原始查询生成独立 sidecar。纯 helper 重算证据，现有持仓归属 validator 严格关联原始 canonical fill，仅在内存中补齐已证实的日期元数据。

**Tech Stack:** Python 3.11、现有 CTP query instrumentation、NDJSON execution ledger、pytest；无新增依赖。

**Spec:** `20260908_1700_stage231_broker_sizing_prequalification.md` 第5节及用户本轮“可以”确认；基础提交 `f70c2833055a2a7f59c67942c35b7f2c45dcb9ee`。

## Global Constraints

- line_id：`futures_trend_stage819_intraday_rules`；只修改当前独立 worktree，本阶段不修改 LINE、registry、根历史总账。
- 不过拟合：不改 alpha、止损、retry、资金比例或资格阈值，不跑回测；继续价值是解除已知正常退出 P1。
- 不连接真实 CTP、不调用真实订单/撤单、不修改生产或 master；只允许 Fake API 离线运行。最终真实资金启用由用户操作。
- 原始 `TradeDate`、`TradingDay`、`OpenDate` 是独立字段，不 OR 匹配，不通过自然日推算业务日期；旧无归属仓位不接管。
- 仅在成交 trading day 封存；跨日缺原始证据不可补造。重启可使用原持久化 native 归属，不要求新连接 generation 等于原发单 generation，但每个查询 bundle 自身必须稳定。
- 原 canonical fill 不改写。sidecar 必须可 JSON 往返并完整重验，不能仅靠 `verified=True` 或摘要。
- 所有实现先写/运行失败测试再改源码。所有文件编辑使用 apply_patch，不新增 inline comments。

## 固定接口与证据合同

新增模块 `examples/portfolio_backtesting/qmt_roll_official_live_broker_open_date_seal.py`：

```python
def build_open_date_seals(
    *, execution_ledger_rows, native_order_event, flat_baseline_event,
    query_bundle, account_fingerprint,
) -> list[dict]:
    ...

def validate_open_date_seal(sidecar, canonical_fill, account_fingerprint) -> dict:
    ...
```

- 输入只读 Mapping/Sequence，输出纯 JSON；失败抛 `ValueError("broker_open_date_seal:<reason>")`，不能用空列表掩盖失败。
- validator 的 canonical_fill 是原始持久化逐笔 filled 记录，不是已合并元数据的副本。
- sidecar：`event_type=broker_position_open_date_sealed`、`version=ctp_owned_open_date_seal_v1`、`seal_identity`、稳定 `broker_callback_key`、`physical_batch_id`、账户/合约/方向/open、intent/root/epoch、vt_orderid/TradeID、成交价量/时间、三个日期、HedgeFlag、`canonical_fill_record_checksum`、完整 `evidence` 和 `proof_sha256`。
- 新 metadata 来源为 `ctp_query_open_date_seal_v1`，不得伪装成 `ctp_on_rtn_trade`；已验证的 raw Trade 查询可以提供真实 TradingDay/HedgeFlag，即使原 onRtnTrade 回报缺失。
- seal identity 绑定版本、账户、交易所、开仓交易日、TradeID、native身份及intent/root/epoch；不含 OpenDate、价格、数量或查询 reqid，避免变化被藏在新 key 下。
- evidence 包含原始 native_order_events、完整 flat_baseline_event、canonical_fills、linked_intent_events 和 query_bundle；所有原始 ledger 行保留 checksum，并与实际 ledger 的记录相符。
- baseline：`broker_open_flat_baseline` / `ctp_owned_open_flat_baseline_v1`，绑定 batch/账户/合约/intent/root/epoch、完整物理请求、service/connection generation、trading_day，以及已冻结 O→P→O envelope 和摘要；原文嵌入 native identity，native 字段保存 `flat_baseline_sha256`。
- envelope：generation、前后 trading day、开始/完成/绝对deadline monotonic ns、前后事件与查询水位、有序 queries。query 含 reqid、真实 request、request_ret、完整 callbacks；callback 含 reqid、last、error、data、真实接收 monotonic ns。
- postfill 顺序 O→T→Detail→P→O，reqid 连续、无额外查询、末包唯一、账户正确、无错误/迟到变异；O前后稳定，执行事件水位不变。
- baseline 证明目标合约双向 gross=0 且无活动订单；postfill native→OrderSysID→TradeID→Detail 唯一匹配，所有实际成交完整覆盖 raw remaining detail/gross。终态部分成交可封存，不要求达到原委托量。

### 17:44 独立评审后的合同补充

- pure 初版存在五类 P1：过滤查询被当完整查询、水位/时间不完整、显式账户及 intent/lease 冲突未校验、日期关系不闭合、重复 Position 行虚增 gross；另有终态状态与成交量矛盾 P2。独立 reviewer 已用重算摘要的离线输入复现，不将单纯 hash 失败当作语义验收。
- 逐查询保存真实 `started_monotonic_ns`；事件水位严格为现有三个 `event_*_count` 字段，另保存实际 native API 水位。native 保存发起时间和插入前事件/native/query 水位；同连接要求 baseline→native→postfill 因果顺序，跨重启不比较旧 monotonic 时钟。
- 每个完整查询窗口上限沿用既有 final query 默认 8 秒，不扩大执行 deadline；保存实际 `max_window_ns` 并重验。
- raw 请求只允许账户级完整查询和白名单中的空可选过滤项；日期范围要求 `TradeDate <= OpenDate <= TradingDay`，不把 OpenDate 推算或 OR 成另一日期。还须核验 Position 的 TradingDay、分类及唯一原始身份。
- 正常 warm 路径在最终 O→P→O 后还有既有账户/最大量只读查询。因此 native reqid 必须严格晚于 baseline，但不能错误要求紧邻；同时要求 native reqid 等于其实际插入前 query 水位加一，baseline→native 的执行事件及 native API 水位不变。不得为了满足错误紧邻条件新增查询循环。
- FAK 终态零成交必须经完整 raw 终态/零敞口证明才能清除 pending；缺 fill 或 native 返回不确定本身不证明零敞口。无 seal pending 仅阻新开，不能绕过任何 close 自身门。
- 以上仍在实现和复验，未关闭原正常退出 P1，未获得发布资格。

## Ruling

- 首版 C9 OPEN 必须在任何 native insert 之前验证恰好一个 physical child（index=0/count=1）；否则零订单拒绝，不截断或调整手数。理由：多 child 部分发送失败时缺少 durable 未发送终态证明，不能在已成交后才因集合不完整拒绝封存。CLOSE 今昨拆单不受此限制。
- 缺 seal、超时、冲突只新增 open-risk 阻断状态，不直接塞进全局阻断列表误阻保护 close；close 保持原自身安全门。
- cold 聚合 fill 没有逐笔证明时，必须在新增 C9 OPEN 前明确拒绝，不能先开再以不支持聚合为由无法退出。
- 已有效封存的同身份同值记录保留原文，重查 reqid/采集时间变化不能导致假冲突；新的不一致 OpenDate 必须拒绝，不能换 key 隐藏。

### Task 1：纯证据 builder / validator

**Files:** 新增上述纯模块；新增 `tests/test_official_live_broker_open_date_seal.py`。

- [ ] 编写真实 ledger fixture：用既有 append API 获得 checksum，构造 flat/native/canonical fill 和完整 raw query envelope；首先运行缺模块/缺函数失败。
- [ ] 实现唯一 native/order/trade/detail 关联、终态部分成交、原始字段范围、callback/时间/水位验证、sidecar hash 和重算。
- [ ] 测试必须证明 `validate_open_date_seal(seals[0], original_fill, fingerprint)` 返回 raw Detail.OpenDate；改变 raw OpenDate 但不更新 proof、换 root、删末包、改账户、混合 reqid、错误 trading day、缺原始 native/baseline 都失败。
- [ ] 参数、原始记录和返回值均 JSON-safe，调用前后输入完全一致；同 evidence 重建相等，费用、账户余额等无关字段不写 sidecar。
- [ ] 运行 `.py311/bin/python -m pytest -q tests/test_official_live_broker_open_date_seal.py`，保留红绿回执。

### Task 2：Stage931 原始采集与 warm/recovery 接线

**Files:** 修改 `run_qmt_roll_stage931_official_live_ctp_submit_adapter.py`；新增 `tests/test_stage931_broker_open_date_seal.py`。

- [ ] 先补 Fake API 集成失败用例：走既有 warm factory、原始 query callbacks 和 durable ledger，而不是在测试里直接填 broker_open_date。
- [ ] 在查询完成时冻结 callback 原文和接收时间；final proof 保存真实 O→P→O envelope。baseline 只能从该已验证副本产生，native 临界区仅校验同一 proof，不新增查询或 ledger reread。
- [ ] 在现有 native identity durable append 中绑定基线；在任何 native 调用前执行单 OPEN child / cold-unproven OPEN 前置限制。
- [ ] postfill 在现有查询锁下执行共同 deadline 的 O→T→Detail→P→O，校验后持久化 sidecar；旧合法 seal 精确复用，冲突记录为阻断。
- [ ] 覆盖 terminal/priced worker、order callback 快捷 resolve、启动时“终态已filled但缺seal”的发现；callback 内不阻塞查询。
- [ ] 验收新开被缺 seal 阻断但保护 close 仍走原门；断线、时间耗尽、ledger写失败、晚到callback、broker day变化都不得报告封存成功。
- [ ] 运行新增集成测试、Stage931 sizing/fill/post-reprice/readiness 与 authorization 测试。

### Task 3：重启后 consumer 严格 join

**Files:** 修改 `qmt_roll_official_live_broker_position_ownership.py`、`tests/test_official_live_broker_position_ownership.py`。

- [ ] 在 `_ledger_fills` 的 canonical fill 解析与确定 open_date 之间，用新纯 validator 重验 sidecar；原始 fill 和实际 ledger 中的 native/intent 引用精确一致。
- [ ] 新封存可补 raw query 已证明的三个日期/HedgeFlag，但不假冒 onRtnTrade；已有字段有实质冲突即拒绝。元数据来源差异单独处理，不将两个合法来源的同值误判为日期冲突。
- [ ] 仅向内存副本合入字段。无seal、orphan、同identity不同内容、checksum错误、后续metadata conflict sentinel一律保持拒绝。
- [ ] 两项手填跨日期成功 fixture 改成调用真实pure producer；JSON往返后的完整ledger在次日空Trade/Order查询场景仍能进入既有正常全平门。
- [ ] 运行 `.py311/bin/python -m pytest -q tests/test_official_live_broker_position_ownership.py tests/test_official_live_broker_close_sizing.py`。

### Task 4：发布闭包、独立评审与验证

**Files:** `build_qmt_roll_stage179_release_manifest.py`、相关release清单测试、本研究线唯一阶段回执。

- [ ] 把新纯模块与新增测试纳入 critical files / required suites；不修改当前immutable release。
- [ ] 独立reviewer审查真实producer→durable ledger→重启consumer→次日全平、晚回包和故障边界，主agent复核每个P0/P1。
- [ ] 先完整运行影响套件，再用固定白名单逐组运行所需离线套件；压力测试按既定taskpolicy且完整留存，不降低阈值或盲目重复。
- [ ] 保存中文实际结果与剩余限制；只有实际关闭的缺陷才标记完成。未满足clean-commit、正式物料、只读资格和生产绑定前不晋升master或启用生产。
- [ ] 验证后按既有授权保存源码提交；不自动推送共享分支、安装或启用交易。

## 18:40 执行状态

- Task 1、Task 3 的实现、语义 TDD 和交叉评审已完成；Task 2 的模拟真实 instrumentation、worker/recovery、JSON 重载及次日正常退出 gate 已完成，完整授权 fresh_bundle→send_order E2E 仍未覆盖。
- Task 4 的 critical/required 闭包、独立竞态复审及最终 54 套离线矩阵已完成：1647 passed、828 subtests passed，critical 前后 SHA 一致。
- 具体失败、修复、两次矩阵及保留阻断以同目录 `20260908_1810_stage234_open_date_seal_verification.md` 为准。源码按授权保存开发分支；正式资格、master 晋升与真实启用没有执行，不能把本计划未完成的生产事项勾为完成。
