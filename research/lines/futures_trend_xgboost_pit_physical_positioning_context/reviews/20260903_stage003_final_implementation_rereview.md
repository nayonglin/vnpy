# Stage003 最终实现修订独立复审

- 日期：2026-09-03（Asia/Shanghai）
- 决策：`ALLOW_STAGE003_ONE_TIME_RUN_AUTHORIZATION_REQUEST`
- 严重度：P0=0，P1=0，P2=0，P3=1
- 审查边界：只读审查 Stage003 runner、机器合同、修复预注册、历史 review/decision 与三份测试；只运行无真实标签、无真实 fit 的测试及 py_compile。未调用 `run_stage003()`/`main()`，未读取真实 aggregate/per-job/holdout 标签数据行，未训练、预测、评价、回测，未创建 authorization/receipt/model/result，未连接真实引擎、生产、CTP 或 order。

## Findings

### P0：0

未发现 holdout 标签泄漏、生产写入、CTP 或订单执行路径。

### P1：0

未发现绕过一次性授权、在 active fold 封存复核前读取该折测试标签、复用 receipt，或技术失败后发布效果数据的直接路径。

### P2：0

首次 BLOCK 的两个 P2 均已在生产代码和对抗测试中同步关闭，未发现修复引入的新 P2。

### P3：1

既有 `20260903_0331_stage003_prerun_block_remediation_preregistration.md` 的 receipt exact schema 实际只有两个 SHA 字段，但相邻 prose 仍写“`三个SHA字段`”。runner 与机器合同一致采用两个 SHA 字段并单独验证 64hex nonce，不形成实现分支或运行门禁绕过，因此继续记为非阻断 P3。

## 原阻断项复核

### P2-1：full split right-only 审计已关闭

- 连接前分别建立 feature 与 full-split 键集合；feature 左侧缺失立即失败，split 重复键立即失败。
- 冻结合同精确约束 feature 218 行、split 374 行、合法 right-only 156 行，并绑定 canonical right-only key SHA256 `b23dea181667fd436a1b9ab55b8e141b0e3fadd378610da3aa8e4e07b644aa41`。
- production join 仅返回 218 个 feature 键，审计为 development 153 行、sealed holdout feature 65 行；right-only 不进入模型面板。
- 新增 right-only 源键会改变行数或键摘要并触发 `projection_right_only_source_invalid`；独立合成反例在 label read、fit、artifact 创建前失败。
- raw probability 仍仅用于 selector，模型矩阵严格排除该列；范围、有限值、rank10 零 delta 与 `1e-12` delta 一致性检查无回归。

### P2-2：事件证据、静态不可达与最终文件集合已关闭

- 单一 `ExecutionEventLedger` 按递增 sequence 记录 aggregate header、eligibility、label read、training-label use、fit start/complete、prediction、selection、seal verification、artifact 与敏感事件；导出为 canonical 深拷贝。
- label audit 从事件序列派生 initial/test/unique、seal 前读取、other-main、A2、holdout、同折训练及选择前读取计数。注入 holdout label 事件会得到非零计数，不再由固定零字段自证。
- execution-scope 的 13 primary、13 repeat、26 total fit 来自生命周期事件，并与 training summary、seal 数和 prediction/selection 事件交叉核验；伪造 summary 但无事件时 `passed=false`。
- 绑定 runner 的 AST 审计要求固定 import surface、唯一 `.fit` 调用点位于 `_fit_repeated_ranker`，并统计 search、early stopping、命令、真实引擎、生产、CTP、order；插入 subprocess/order 节点会失败。
- pre-effect staging 的实际文件集合与 artifact 事件集合双向比较。最终发布前对冻结完整 expected set 做 missing/unexpected 差集，记录每个文件 size/SHA；fsync 后 rename，发布后重读 manifest 并再次核验集合、size、SHA。额外最终文件反例在 rename 前失败。
- `decision.json`、summary、report 的敏感零值均取自上述 label/scope audit；未发现直接写死这些最终字段的回归。

## 生产链与失败关闭

- production 入口为零参数，固定 authorization/receipt/temp/final 路径和 `xgboost.XGBRanker` factory，不接受 CLI/env/path/model/label-store override。
- 初始成熟标签先开启；每个 active 月先完成两次 fit、两次 prediction、selection、两份 UBJ、fold input、prediction、selection及 seal 的 create-once 落盘和 SHA/canonical 重验，再记录 `active_seal_verified`/`selection_recomputed`，最后才读取本月测试标签。
- 后续折训练要求 `eval_date < test_date` 且 `next_eval_date <= test_date`，因此已成为后续成熟训练标签的历史测试月不会进入自身折训练或自身选择。13 active 月共 26 fit；4 fallback 月固定 rank10、零填充且不读取标签。
- 效果门仅在 before-training 与 after-all-models 两点身份稳定且其余技术门通过后计算；随后执行 after-effect 第三 checkpoint。任一技术门失败时 effect 被置空，最终 expected set 排除 effect qualification/sequence/selection/prediction 文件，报告不披露效果。
- 三个 checkpoint 均重新核验 authorization、27 个 bound files、冻结输入、governance、机器合同、绑定 runner AST 与 runtime identity；最终门要求三个命名 checkpoint 的 authorization/input 与 runtime 摘要完全一致。
- authorization exact 绑定链为 27 项，保留首次 BLOCK review/decision，并绑定本 remediation、当前 runner/contract/三份 tests、runtime identity及本次 rereview/decision 的固定绝对路径。当前 authorization、consumption receipt、temp result、final result 均不存在。

## Fresh 验证

- Runner SHA256：`2bbd6af436af2b761720269695e1c052aee3980ed7bedcc4969b1483b10d0a86`。
- Machine contract SHA256：`e800b2b347bcb92472234a0a391b77b487de27de1f79ee191354b635232c15a2`。
- Tests SHA256：contract `34fcf3d9e1fc9d70511e5f5c27c843e430d90e794d26d710fd8c64a7e7f66974`；state-machine `f47a3c276d6e3da0e99c2159ee8311d8de57a74dcc3959c306bea602643cc55c`；adversarial `23c11fe4973677ef268ce7e490a30f8ce26bb698298084257cb39604d670076c`。
- Remediation SHA256：`cb6d29fc0e9247f30f1698a5b19790cb2b87dff01dbe576534cec34ed97eff80`。
- 历史 BLOCK review/decision 保持原文件，SHA256 分别为 `2479f673c1a60e1032a39b7452142a101fcf03919f7be7548c7f051b131443af`、`46aef3e6415c51e61f3a87e493d3efc02f9c965c00b77c2d80cd5d5cf0bcdfc1`。
- Fresh pytest：`68 passed in 2.47s`。测试读取的真实冻结内容仅为无标签 feature/split/job 元数据和身份；模型训练测试使用 fake ranker，label 状态机使用合成临时数据。
- Fresh py_compile：runner 与三份 tests 全部通过；pycache 定向到 `/private/tmp/stage003-final-rereview-pycache`。

## 过拟合与继续价值

- 过拟合：否。本次只核验治理、时序、证据与失败关闭，不读取真实标签或结果，不改特征、参数、选择器或门槛。development 已被多轮治理审查，未来一次运行仍必须遵守冻结合同和“一次失败永久闭线”，不得结果后救援。
- 继续价值：有，但仅限申请一次性 Stage003 development OOS 运行授权。当前实现已具备让一次结果可归因、可审计、失败关闭的最低条件；这不证明模型有效，也不授权扩大搜索或访问 holdout。

## 决策与边界

P0/P1/P2 均为 0，决定 `ALLOW_STAGE003_ONE_TIME_RUN_AUTHORIZATION_REQUEST`，`allowed=true`。该决定只允许另行提出一次性运行授权请求，不是 authorization 本身，也不允许本 reviewer 创建 authorization。

未来 authorization 必须是新建、单次消费、绑定当前 27 项文件实际 SHA，使用独立小写 64hex nonce，且 `scope=one_new_stage003_development_oos_run_only`。在 authorization 明确获批和创建前，仍禁止运行入口、读取真实标签值、fit/训练/预测/效果评价/回测、holdout、真实引擎、生产、CTP 与 order。
