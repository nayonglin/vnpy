# Stage003 唯一授权运行技术失败独立复核

- 日期：2026-09-03（Asia/Shanghai）
- 决策：`BLOCK`
- 严重度：P0=0，P1=0，P2=1，P3=1
- 评审边界：只读 runner、机器合同、authorization/consumption receipt 元数据、既有预注册/review、temp/final 文件集合和无真实标签测试。未再次调用 `run_stage003()`/`main()`，未读取 aggregate 数据行、任何真实 per-job label 内容或 holdout 标签，未 fit、预测、评价、回测，未修改 authorization/receipt/temp/result，未连接真实引擎、生产、CTP 或 order。

## Findings

### P0：0

未发现 holdout、生产、CTP 或订单访问证据；final result 不存在，temp 目录无任何条目。

### P1：0

authorization 已被原子单次消费，现存 receipt 会使相同授权的任何再次运行在副作用前失败。未发现删除、覆盖或复用 receipt 的路径。

### P2-1：失败路径没有持久化事件账本或技术失败 bundle，关键零计数无法独立复验

runner 只在 `_run_frozen_training()` 正常返回后才把 `event_ledger.events()` 加入最终 JSON payload，并只在全部后续步骤完成时调用 `_publish_result_bundle()`。`run_stage003()` 没有异常捕获分支用于持久化失败时的 event ledger、异常类型/栈、checkpoint、label/fit/predict/artifact 计数或固定 technical-fail decision。因此本次异常后只留下 consumption receipt 和空 temp 目录，没有与该次消费绑定的失败证据文件。

所提供终端错误为 `Stage003Error: joint_relevance_degenerate:2022-01-28`，调用栈位于 `_run_frozen_training -> _prepare_ranker_fold -> _build_joint_relevance`。如果将这段未持久化终端输出视为真实且完整，则绑定 runner 的严格控制流可以推出：

- `open_initial_labels()` 已完整返回且通过 `62` 行、`13` qid 形状检查，故初始 development main 标签读取为62。
- 第一 active fold 在 `_prepare_ranker_fold()` 的 joint relevance 构造处失败，尚未到 `_fit_repeated_ranker()`；因此 fit、prediction、selection、seal 和 pre-effect artifact 均为0。
- active 测试标签只会在 fit、预测、selection、五类 payload/seal 落盘并复核后由 `_effect_open()` 打开；因此91条OOS测试标签尚未打开。
- production label store 只接受冻结153条 development main 元数据；初始62条不包含 other-main、A2 或 holdout，因此这些访问为0。

但上述精确计数依赖未落盘的终端 traceback。空 temp 只能证明没有成功落盘工件，不能排除另一条在首个 artifact 前已经启动 fit/predict 的失败路径；receipt 本身也不包含事件摘要。独立 reviewer 无法从现存持久状态把 traceback 与该 nonce/receipt 做密码学绑定，也不能重读标签或重跑来补证。此前最终实现复审要求敏感零计数必须由事件而非常量或摘要自证，本次失败分支未满足同一证据标准。

这是审计完整性 P2，不是允许重跑的实现修复理由。Stage003 的一次性授权已经消费，不能通过重跑补齐证据；该缺口只能作为未来新研究线失败持久化设计的经验。

### P3：1

既有 `20260903_0331_stage003_prerun_block_remediation_preregistration.md` 仍把 receipt exact schema 中实际两个 SHA 字段写成“`三个SHA字段`”。机器合同与 runner 均采用两个 SHA 加独立 nonce，不影响本次单次消费，继续作为既有非阻断文字问题记录。

## 授权与现场

- Authorization SHA256：`8b7b77c037419702e40390945e48a274bdb61d10722a0d583ce82c099b4c348f`；exact 6 keys，权限 `0600`。
- Receipt SHA256：`11cbb1af3806707368e6269c8aff5c5441fa36ef8bbf381b51f80116f16ab127`；exact 7 keys、canonical JSON+LF，权限 `0600`，decision=`STAGE003_AUTHORIZATION_CONSUMED`。
- nonce：`558332d4683c115524391c6ca430eb467b9016db510b2b1f7881987a7a8e4161`，为小写64hex，authorization 与 receipt 一致。
- scope：`one_new_stage003_development_oos_run_only`，authorization 与 receipt 一致。
- 27/27 bound files 均为当前非 symlink 普通文件且逐项 SHA 匹配；canonical bound-files identity SHA256=`e6355d8a06161cfa36968fdf10f0865ca8514301d7fed8afb100700b069d000c`，与 receipt 一致。
- Runner SHA256：`2bbd6af436af2b761720269695e1c052aee3980ed7bedcc4969b1483b10d0a86`；contract SHA256：`e800b2b347bcb92472234a0a391b77b487de27de1f79ee191354b635232c15a2`。
- temp `artifacts/stage003_joint_ranker_development_oos.tmp` 存在、权限 `0700`、条目数精确为0；final `artifacts/stage003_joint_ranker_development_oos` 不存在。

## 合同失败与停止规则

- 冻结目标明确为每月 return/drawdown dense relevance 后逐行取 `min`；每个训练 qid 必须至少两个 joint relevance 等级。`2022-01-28` 退化按合同必须直接技术失败，不允许删月、换标签、改目标。
- 技术失败 decision 在合同中固定为 `stage003_contract_or_pit_invalid_stop_no_effect_claim`。实际 runner 以未捕获异常退出且没有发布该 decision，这正是 P2 的失败证据缺口；它不改变停止语义。
- 当前六特征、joint maximin、单头32树 XGBRanker、LR/XGB 50/50 月内 percentile 融合形状应立即停止。不得调参、改权重、换标签、删月/品种、读取更多标签、访问 holdout 或再次运行救援。

## Fresh 检查

- 独立结构化复算通过：authorization/receipt exact keys、nonce/scope、authorization SHA、27个 bound-file SHA、bound identity、result path 与 canonical receipt bytes全部一致。
- 文件现场复核：temp 条目数0，final不存在；复核前后 authorization/receipt SHA保持不变。
- 仅运行4个纯合同/运行时/joint-relevance测试：`4 passed in 2.16s`。没有运行生产入口、label store 状态机或任何 fit/predict 测试。
- 当前任务无法读取来源任务的 app terminal；所给 traceback 没有仓库内持久副本，因此未将其视为独立可重放证据。

## 过拟合与继续价值

- 是否过拟合：本 reviewer 行为否，没有读取标签或效果、没有修改模型。但在已知首月 joint relevance 退化后删月、换标签、调参、改融合或再跑会是明确的结果后救援和过拟合。
- 是否值得继续：同一 Stage003 形状不值得继续，且一次性授权已消费。仅值得记录本次技术失败、永久停止本形状，并把“异常时先持久化最小审计证据”作为未来独立研究线的事前设计要求；不得为本线补实现后重跑。

## 决策

由于 P2=1，现有持久证据不足以独立确认全部精确零计数，不能签发 `CONFIRM_STAGE003_TECHNICAL_FAIL_STOP_NO_RERUN`。决定 `BLOCK`，`allowed=false`。

该 BLOCK 不允许重跑、修合同、修模型或读取更多标签。操作结论仍是：authorization 已永久消费，Stage003 当前冻结形状停止，禁止 true engine、holdout、生产、CTP 和 order。
