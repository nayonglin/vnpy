# Stage003 首次 BLOCK 修订后第二轮独立预运行复审

- 评审日期：2026-09-03（Asia/Shanghai）
- 评审性质：独立、只读、预运行复审
- 最终决定：`ALLOW_STAGE003_TDD_IMPLEMENTATION_ONLY`
- 严重度计数：P0=0，P1=0，P2=0，P3=1

## 评审边界

本次仅核验既有 Markdown 合同、review/decision、测试与文件身份；未读取 aggregate label/reconciliation 数据行、任何 job `label.json`、holdout、Stage006 prediction/effect。未实现或训练模型，未运行 Stage005/Stage006/Stage003 入口，未回测，未创建 authorization，未连接 CTP，未调用 order。

本次绑定文件及 fresh SHA256：

| 文件 | SHA256 | 结论 |
|---|---|---|
| `stages/20260903_0318_stage003_joint_ranker_development_oos_preregistration.md` | `859d060217e6ef381170d439086ec0d7097d2c18152f2c0ff0aaacb78124cbea` | 与委托值一致 |
| `reviews/20260903_stage003_prerun_independent_review.md` | `53491926fc97c8bed6d04cc522b7d27eda572fe1f84d38ebb72a5c4c478c6000` | 与委托值一致，保持原样 |
| `reviews/20260903_stage003_prerun_review_decision.json` | `f7506bbb2d551291c6dfab294623218387167ccc77ca739dc1d0ac3356032b03` | 与委托值一致，保持原样 |
| `stages/20260903_0331_stage003_prerun_block_remediation_preregistration.md` | `52bb25107cbd8b1848c2e9da0b138958ead54d7ca85f3a0a45fe4e6611baf1c1` | 与委托值一致 |

## Findings

### P0：0

未发现会造成 holdout 泄漏、未经授权标签读取、生产/CTP/order 触达或把开发结果冒充生产结论的问题。

### P1：0

未发现授权可绕过、单次消费可复用、标签在 seal 前开启、磁盘篡改后仍可读标签等高风险缺口。

### P2：0

原 P2-1 与 P2-2 均已在修订 Markdown 中以可实现、可测试的精确合同关闭，且未因修复引入新的 P2。

#### 原 P2-1：授权、绑定与单次消费闭合

- production 入口固定为零参数 `main()` 调用零参数 `run_stage003()`；禁止 CLI、环境变量、路径、输入、factory、参数和 label-store override。
- authorization 使用固定绝对路径；顶层键严格且仅为 6 个：`decision`、`scope`、`nonce`、`bound_files`、`result_dir`、`consumption_receipt_path`。
- `decision` 固定为 `AUTHORIZE_ONE_STAGE003_DEVELOPMENT_OOS_RUN`，`scope` 固定为 `one_new_stage003_development_oos_run_only`；nonce 必须是 JSON string、64 位小写 hex，明确拒绝 bool、number、null、大小写或长度错误。
- `bound_files` 严格且仅含 14 个约定键；每项都要求 exact `path`/`sha256`、规范绝对路径、真实普通文件、严格 resolve，并计算 canonical `bound_files_identity_sha256`。
- consumption receipt 严格且仅含 7 个键，并绑定 authorization 路径/SHA、nonce、scope、bound-files identity 与 result dir。
- 消费采用 `O_CREAT|O_EXCL`、权限 `0600`、canonical JSON 加 LF、文件 fd `fsync`、关闭后父目录 `fsync`、再读 exact 校验。并发只能一胜，串行重试永久拒绝，禁止删除、复用或覆盖 receipt。
- 所有授权、输出目录、临时目录与消费前置检查均位于 feature 解析、job label 读取和 fit 之前；result 使用不可覆盖的原子 rename。
- 对抗测试明确覆盖额外/缺失键、非法 nonce、路径/factory override、并发双启动、串行重放、receipt 与 result 预占/篡改等拒绝路径。

#### 原 P2-2：五类磁盘 payload、seal 与 effect-open 闭合

- 每个 active fold 必须实际落盘五类 payload：primary UBJ、repeat UBJ、fold-input JSON、prediction JSON、selection JSON；不是只记录内存摘要。
- active seal 严格且仅含 8 个键：`seal_type`、`eval_date`、`label_read_count_before_seal` 及五个 payload SHA；计数要求 integer 0 且拒绝 bool，五个 SHA 均要求小写 64hex。
- active seal 只创建一次，采用临时文件加 `os.link`，并对相关目录执行 `fsync`；禁止覆盖既有 seal。
- `effect_open` 必须丢弃内存 digest，从磁盘重新读取五类 payload，逐一重算 SHA，并重算 feature order、qid/group、training identities、test keys、分数、选择与 tie-break；还要验证模型字节和重复预测确定性。任何篡改均在 label load 和 label-read 计数增长前失败。
- fallback seal 严格且仅含 8 个键，记录固定 reason、A/B/C、前后 label-read count；fallback 不得生成模型、fold input、prediction 或 selection，也不得读取标签。
- 合成/对抗测试覆盖 active/fallback schema、create-once、磁盘篡改、内存 digest 欺骗、模型/预测/选择/feature/qid/training identity 不一致，并要求失败路径标签读取数保持 0。

#### 原 P3：空 replacement 语义已关闭

- replacement 为空时，两项 effect metric 必须为 JSON `null`，相关 gates 必须为 JSON `false`。
- 11 个 gate 字段要求 native JSON boolean，禁止 `0/1`、字符串与 null；最终判定使用全部 11 项逐项 `is True`，禁止短路或缺项默认为真。

### P3：1

1. **Consumption receipt 的 SHA 字段数量文案不一致。** exact 7-key schema 中只有两个 SHA 字段：`authorization_sha256` 与 `bound_files_identity_sha256`，但紧随其后的 prose 写成“`三个SHA字段`”。由于 exact-key schema 禁止增加第三个 SHA，且 nonce 已另有独立 64hex 约束，此处不造成实现歧义或门禁绕过，按 P3 文字计数错误处理。TDD 实现应以 exact schema 为准，验证两个 SHA 字段，并单独验证 nonce；后续修订文案时应将“三个”更正为“两个”。

## 冻结设计无回归

对照原预注册与 remediation，以下核心设计未被修复过程改写：

- 样本仍为 218 个样本月，153 development 加 65 holdout；initial 训练 13 个 qid/62 行，13 个 active fold 共 91 个测试月，另有 4 个 fallback 月，development 标签总计 153 行。
- 特征仍为冻结的 6 个 physical-positioning 特征；联合 relevance 仍按两头 relevance 的逐行最小值构造。
- 仍为单个固定参数 XGB ranker，`n_estimators=32`、`max_depth=2`，没有结果后调参、折内选择或救援分支。
- 选择器仍为 LR/XGB 各 50% 月内 percentile 融合，physical split gate、tie-break 与替换席位规则未变。
- 8 类效果要求展开为 11 个显式布尔门，收益、回撤、稳定性及 non-degradation 阈值未变。

## Fresh 验证

执行命令：

```text
env PYTHONDONTWRITEBYTECODE=1 .py311/bin/python -B -m pytest -q -p no:cacheprovider --basetemp=/private/tmp/physical-stage003-rereview research/lines/futures_trend_xgboost_pit_physical_positioning_context/tests
```

结果：`6 passed in 0.42s`。测试使用禁写 bytecode、禁 pytest cache 和仓库外临时目录；未创建 campaign attempt、authorization 或模型/效果产物。另行只读检索未发现 Stage003 authorization 或运行 artifact。

## 过拟合与继续价值

- **是否在过拟合：否，就本次行为而言。** 本轮没有读取标签值、训练或评估效果，只审计预先冻结的授权、状态机、磁盘身份与失败关闭语义，因此没有依据结果调规则的机会。合同本身仍有多重效果门，不能证明未来模型不会过拟合；该风险必须留待获得独立授权后的 development OOS 评估处理，且不得用 holdout 救援。
- **是否值得继续：是，但仅值得进入 TDD 实现与合成测试。** 两项阻断缺口已变成精确、可对抗测试的机器合同，继续实现能验证门禁是否真实成立；当前不存在任何训练、标签值读取、回测或效果结论，因此不支持扩大授权范围。

## 决策与边界

P0/P1/P2 均为 0，决定为 `ALLOW_STAGE003_TDD_IMPLEMENTATION_ONLY`。

该决定只允许严格按冻结合同进行 TDD 实现、机器合同落地及不含真实标签值的合成/对抗测试。它不授权读取 aggregate/job/development/holdout 标签值，不授权 fit、训练、预测、效果评估、回测、创建 authorization、运行 Stage003/Stage005/Stage006 入口、生产接入、CTP 或 order。后续任何真实运行必须另经实现后独立 review，并取得与当前文件 SHA、一次性 64hex nonce 和单次 scope 精确绑定的独立 authorization。
