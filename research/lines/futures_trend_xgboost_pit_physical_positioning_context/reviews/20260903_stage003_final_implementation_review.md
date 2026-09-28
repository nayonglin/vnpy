# Stage003 最终实现独立审查

- 日期：2026-09-03（Asia/Shanghai）
- 决策：`BLOCK`
- 严重度：P0=0，P1=0，P2=2，P3=1
- 审查边界：只读原始预注册、三份 remediation、全部既有 review/decision、机器合同、runner 和三组 Stage003 tests；仅运行无真实标签、无真实 fit 的 pytest、py_compile 与静态检查。未运行 `run_stage003/main`，未读取任何真实 per-job label 或 aggregate/reconciliation 数据行，未训练、预测、效果评价或回测，未创建 authorization，未访问 holdout 标签，未连接生产/CTP/order。

## Findings

### P0：0

未发现真实 holdout 标签泄漏、生产或订单执行。

### P1：0

未发现现有代码可绕过24项 authorization、重复消费同一 receipt 或在 active payload seal 复核前调用生产 label store 的直接路径。

### P2-1：full split 的右侧额外连接记录不会被拒绝，规定的 adversarial test 缺失

`_join_raw_probability_projection()` 对 split 采用 feature-left `merge(validate="one_to_one")`，随后将：

`extra_join_rows = max(0, len(joined) - len(features))`

作为额外连接计数。left join 的结果行数在两侧键唯一时恒等于 feature 行数，因此 split 中不与任何 feature 匹配的右侧额外记录会被静默忽略，`extra_join_rows` 仍为0。反例是：合法两行 feature、对应两行 split，再向 split 添加第三个键唯一、数值合法、月份锚点不冲突的记录；代码会返回成功并报告 `extra_join_rows=0`。

第三份 remediation 明确要求“缺失和额外连接均为0”，概率缺口 review 也要求对抗测试拒绝 extra connection。当前 adversarial 参数只覆盖 extra column、两侧 duplicate、missing match、类型/范围和 delta 冒充，没有 right-only extra row。现有 frozen 文件恰好为218行不能替代 fail-closed 实现和规定反例；测试也无法证明未来受绑定输入检查的算法语义完整。

必须修复：使用 outer merge indicator，或在 join 前后比较两侧键集合，显式计算并拒绝 `right_only`；增加独立反例，证明右侧额外键在任何 label read/fit/artifact 写入前失败。

### P2-2：technical scope 与 forbidden-label 零计数由期望常量自证，不是运行事件证据

`_build_execution_scope_audit()` 先复制 `EXECUTION_SCOPE_COUNTS`，其中 parameter/feature/seed search、early stopping、rerun selection、holdout prediction/read、true-engine、production、CTP、order、unexpected command 全部预填期望值；函数只用 training 数据覆盖三项 fit count 和 unexpected artifact count，然后用该字典与同一个常量比较来决定 `passed`。因此调用者只需提供13个 active seal、26个 fit 和空 unexpected-files，即可自动得到其余敏感计数全0，函数从未观测这些事件。

`PhaseGatedJobLabelStore.final_audit()` 同样直接返回 aggregate rows、seal 前 test label、其他 development main、A2、holdout、same-fold training 和 preprocessing/selection 使用量为0；这些字段没有对应事件计数器。`decision.json`、summary 和报告又重复写死 holdout/production/CTP/order 为0。technical gate 随后把这些字面量与合同期望值比较，形成自证闭环。

当前 runner 静态上确实没有 subprocess、CTP、order 调用，holdout panel 也没有进入 `_run_frozen_training()`；但用户要求的是不可由写死计数自证的运行证据。现有 technical qualification 可以在没有相应 observation ledger 的情况下声称这些门通过，且 prepublication artifact audit 只检查模型/payload/seal，后续 summary/report/effect 等最终文件没有与冻结 expected final-file set 做差集核验。

必须修复：

1. 所有允许的 label file open、fit、prediction、artifact create/publish 通过单一事件账本或不可绕过的受控接口计数，并按 phase/job type/split 记录。
2. seal 前 test-label、other-main、A2、holdout 等零值必须由实际访问事件集合差集得出，不能由 `final_audit()` 返回常量。
3. search/early-stop/rerun/command/production/CTP/order 等不可达性应由绑定 runner 的静态 AST/import/call allowlist 审计产物证明，或由统一受控执行接口事件证明；不能在 runtime audit 中直接复制期望0。
4. final publish 前应以冻结的完整 expected artifact set 对 staging 中所有最终文件做 missing/unexpected 差集校验，publish 后重核 manifest 文件身份。
5. 增加反例证明伪造 training summary、插入额外访问/命令/最终 artifact 时 technical gate 必须失败。

### P3：1

第一次 remediation 的 consumption receipt exact schema 只有两个 SHA 字段，但 prose 写成“三个SHA字段”。runner 与机器合同均按两个 SHA 加独立 nonce 实现，不产生代码分支；该既有文案问题继续计 P3。

## 已通过的实现核验

### Authorization 与身份

- 生产入口 `run_stage003()`/`main()` 均为零参数；固定 authorization、receipt、temp、final 路径，没有 CLI/env/factory/path override。
- authorization exact 6 keys；24个 bound keys与机器合同路径集合一致。每项要求 canonical absolute regular file、exact `{path,sha256}` 和现场 SHA。
- receipt 使用 `O_CREAT|O_EXCL`、`0600`、完整 write、file fsync、parent fsync和 canonical reread；并发测试证明两进程仅一胜，串行重试失败。
- consumption 前先完成 before-training checkpoint；三阶段分别重核 authorization、24 bound files、全部冻结输入和 runtime identity，并比较稳定摘要。
- 当前 authorization、consumption receipt、temp result 和 final result 均不存在。

### 输入、标签与 PIT

- `input_sha256` exact 14 keys且全部为小写64hex；full split SHA已修复并匹配实际冻结文件。Stage002/003/005、runtime、manifest及 review decision 均在 checkpoint 中验证。
- aggregate label 和 reconciliation 先哈希整文件，只用二进制 `readline()` 解析首行；审计固定 `data_rows_parsed=0`，测试用不可解码尾部证明未解析数据行。
- production label store只接收153行 eligible development metadata；逐 job 验证 eligibility文件和 `label.json` 的 Stage005 manifest `{size,sha256}`，payload exact 8 value keys且有限。
- initial 13个月62行先开；13个测试月共91行按时间推进，只在 `_effect_open()` 完成 active disk verification 后打开。训练 join要求当前所有 train rows均已成熟并满足 `eval_date < test_date`、`next_eval_date <= test_date`。
- 13 active、4 fallback、91 test rows、153 unique jobs、A2未进入模型、65 holdout feature仅构建边界且不进入训练路径的结构实现成立。

### 模型、selector 与 seal

- ranker严格使用冻结六特征、按 mergesort 排序和月 qid；joint relevance为两目标月内 dense relevance 的逐行最小值，退化组失败。
- production factory固定 `xgboost.XGBRanker`，参数 exact，13折各 primary/repeat 两次，共26 fit；无参数/feature/seed search、early stopping 或择优代码路径。重复预测误差 `<=1e-12`、UBJ bytes相等、每折分数非退化。
- LR与XGB均使用月内 ascending average percentile，C固定50/50；B/C tie-break依次为原始LR概率、a_rank、symbol，A固定rank10。
- 每个 active fold先create-once落盘两份UBJ、fold input、prediction、selection和seal；effect-open重读五类payload、复核SHA/canonical bytes、fold identity、prediction percentile、selection/tie-break及主重复一致性后才调用 label store。
- fallback只落盘固定rank10 seal，不创建模型/prediction/selection且不读标签。physical split要求13个模型各使用至少一项物理特征、并集至少3项。

### 技术门、效果门与发布

- aggregate `_evaluate_effects()` 仅在两点身份稳定且除三点延迟门外的技术门均通过时执行；第三 checkpoint 后重新计算完整15项 technical gates。技术失败时 effect payload不发布。
- 11项 effect gate均为native bool；空 replacement的两项中位数为null且门为false；17月序列要求13 active加4个精确零 fallback。
- receipt消费后以权限0700创建固定 temp；fold payload create-once并fsync。最终写入文件、manifest、文件和目录fsync后以 rename发布至固定 final，再fsync父目录。

## Fresh 验证

- Runner SHA256：`c169bd4f39b979193ab2d5a2a8ee4eeab3a025e1197812493bd54ede89ea3306`。
- Machine contract SHA256：`e894e93b697b313d55afbaab8f112efc2c877f9a5abd7200deba5af5377630d1`。
- Tests SHA256：contract `36c759854babc952135321dfad7554f22e552844263e951e02e22552924791cb`；state-machine `93f18b01ff407ce10662f96d92df1711e414c5d2fcc2818b8be2513c830b1765`；adversarial `82ae15d505ebe9e3f1d0c70e246e364149ec2ba948c1b5648a6c46f0480ed5bf`。
- Fresh pytest：`63 passed in 7.13s`。仅使用真实无标签冻结 metadata/header 身份和合成 label/fake ranker；未调用真实 fit或生产入口。
- Fresh py_compile：runner与三组tests全部通过，pycache写入 `/private/tmp`。
- 绿色测试没有覆盖 P2-1 的 right-only extra row，也把 P2-2 的常量零审计当作预期，因此不能覆盖上述 blockers。

## 过拟合与继续价值

- 过拟合：本次审查没有读取真实标签或效果，也没有修改策略、特征、参数和阈值，因此本次行为不构成过拟合。未来development已复用多次，合同原有的“一次失败永久闭线、不得holdout救援”仍必须保持。
- 继续价值：有，但仅限无标签治理修复。两个P2都是可确定修复的证据完整性问题；在关闭前运行模型只会产生无法被合同证明的结果，没有继续训练价值。

## 决策

P2=2，决定 `BLOCK`，`allowed=false`。不得申请或创建 Stage003 one-time run authorization；不得读取真实标签、fit、训练、预测、效果评价、回测、holdout、true-engine、production、CTP或order。只允许先修复两项P2、补齐反例，并重新进行独立最终实现review。
