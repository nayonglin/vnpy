# Stage006 训练预注册独立预运行评审

- 评审日期：2026-09-03
- 研究线：`futures_trend_xgboost_pit_curve_account_labels`
- 预注册：`stages/20260903_0101_stage006_dual_ranker_development_oos_preregistration.md`
- 机器合同：`artifacts/stage006_dual_ranker_development_oos/training_contract.json`
- 评审性质：独立、只读、标签值盲态下的 pre-run review
- 执行边界：未读取 `development_labels.csv` 的任何数据行，仅读取表头并复算整文件 SHA256；未计算标签分布；未训练、未创建模型文件、未运行 Stage005/006 runner、未读取或生成 holdout 标签、未连接 CTP、未调用订单 API。

## 决策

**BLOCK_STAGE006_IMPLEMENTATION**

严重度精确计数：

- P0：0
- P1：0
- P2：3
- P3：0

预注册文本的统计设计总体自洽，冻结输入身份也全部匹配；但机器合同没有逐项编码三个会影响泄漏防护、可机械复算性和确定性的关键约束。按照“任一 P0/P1/P2 非 0 即阻断”的规则，当前不得开始 Stage006 实现或测试，更不得训练和评价效果。

## Findings

### P2-1 机器合同未封死测试标签访问阶段和 holdout prediction 为零

预注册文本要求测试月真实标签只能在训练完成后用于资格门，禁止参与特征处理、候选选择；还要求 108 行 holdout 特征只可用于身份/边界计数，不得产生预测行。机器合同只写了：

- `target_construction.test_labels_used_for_training=false`
- `technical_gates.holdout_label_rows_read_or_generated=0`

它没有机器可验的 `test_label_rows_read_before_predictions_sealed=0`、`test_labels_used_for_preprocessing_or_selection=0`、`holdout_prediction_rows=0`，也没有定义“先封存模型/预测 SHA，再开放对应测试月标签做 effect gate”的阶段顺序。因此，一个提前读取测试标签用于 selector/tie-break，或对 108 行 holdout 特征提前打分的实现，仍可能通过当前 JSON 字段。这是伪 OOS 和封存集污染的合同缺口。

必须先修：在预注册和机器合同中共同冻结标签访问状态机及显式整数计数；至少覆盖训练、预处理、调参、候选选择、tie-break、效果评价、holdout prediction 七个阶段，并要求测试预测及模型身份封存后才允许读取该折测试标签。

### P2-2 预注册的数据/selector 精确定义未逐项进入机器合同

以下会改变训练或选择结果的规则只存在于 Markdown，JSON 没有对应结构化字段：

- 8 项特征必须全有限；禁止缩放、填补、winsorize、符号翻转、交互、特征选择和品种/年份编码。
- 每月恰有一个 rank10，rank 从 10 连续到月最大值且不超过 18。
- 训练数组必须按 `eval_date,candidate_rank,product_vt_symbol` 稳定排序；qid 的具体编码及组边界必须精确。
- 两头分数的月内映射必须是升序 `average percentile rank` 且值域 `(0,1]`；当前 `selector.arm_b` 仅写“monthly percentile”，无法排除 dense/min/max percentile。
- 未替换月的收益和回撤增量必须以 0 纳入完整 17 月效果序列；效果门的机器字段没有显式 comparator、序列长度和 zero-fill 规则。
- 模型、重复模型、预测、选择、技术门、效果门、运行环境及输入输出必须全部进入 manifest，且命令/非预期 artifact 计数必须为 0。

这些不是文案细节：不同 percentile tie 规则、排序稳定性、缺失值处理或 zero-fill 会直接改变 B/C 和 8 类效果门。当前不能声称“预注册和机器合同逐项一致”，也无法只依据机器合同写出无歧义的 TDD oracle。

必须先修：把上述规则以明确类型、枚举、列名、计数和零值写入 `training_contract.json`，并让 Markdown 与 JSON 一一映射；后续独立复审应比较结构化字段，而不是依靠实现者解释 prose。

### P2-3 随机 pair 构造缺少冻结运行时身份

模型固定 `lambdarank_pair_method=mean`、`lambdarank_num_pair_per_sample=1`。XGBoost 3.2 官方 Learning-to-Rank 文档说明：`mean` 会对每个 document 随机采样 pairs；固定种子在同一环境可复现，但不同平台的随机数实现可能导致不同结果。当前 Markdown 仅冻结 Python 和五个包版本，机器合同甚至没有 environment/runtime 字段；两处都没有冻结 OS/架构、XGBoost build/runtime identity 或训练前后 runtime digest。

重复拟合预测和 UBJ SHA 一致只能证明“同一次环境内重复”一致，不能证明授权运行使用了预注册环境。一次性训练若换平台或二进制构建，仍可能得到另一套、但内部重复一致的模型。

必须先修：冻结并由机器合同绑定 Python executable/version、OS/arch、xgboost/numpy/pandas/scikit-learn 版本及可复算的 runtime/build identity；训练前后必须相等。后续单次 authorization 还应绑定修订后的 prereg SHA、contract SHA、runtime identity 和唯一 nonce。

## 已通过的独立核验

### 输入身份与 blind state

- 预注册 SHA256 实测为 `9da4733439fb7dbecfc36bee8efb864e1a3789f250ec9784e8ad607587c01b90`，与指定值一致。
- 机器合同 SHA256 实测为 `c0a78756c9c1aa79078e4cc2a85173def086cc2e08340873a80afc9b6cab40f5`，与指定值一致。
- Stage002 feature/summary/manifest、Stage003 full split/development jobs/summary、Stage005 decision/labels/reconciliation/manifest、Stage005 post-run review/decision 共 12 项列示 SHA 全部与磁盘真实文件一致。
- Stage005 decision 为 `passed=true`，13 个 model/holdout/CTP/order/unexpected scope 计数均为精确整数 0；post-run review decision 为 `ALLOW_STAGE006_TRAINING_PREREGISTRATION_ONLY` 且 P0/P1/P2 为 0。
- Stage006 artifact 目录目前仅有 `training_contract.json`；未发现模型、预测、训练 receipt 或 authorization。标签值盲态属于预注册者声明，历史上“从未读取”的否定事实无法仅靠文件系统完全证明；本 reviewer 没有突破该盲态。

### 分割、连接键与 17 折 PIT

- 只读取 Stage002/003 的任务、日期、产品、rank、split、next_eval_date、qid 元数据：feature panel 为 374 行/47 月；full split 与其键集合一对一精确相等。
- development 为 266 行/35 月，`2022-01-28 -> 2024-11-29`；holdout 为 108 行/12 月，`2024-12-31 -> 2025-11-28`。两者月集合不重叠；holdout 的 `label_values_read_allowed=False`。
- 266 个 main development job 与 development split 的 `eval_date,product,candidate_rank` 键精确相等；另有固定 4 个 A2，不进入模型训练行。
- 47 个月均恰有一个 rank10，rank 从 10 连续且最大不超过 18；每月 qid 元数据唯一。
- 以 `train.eval_date < test.eval_date and train.next_eval_date <= test.eval_date` 独立机械重算，测试月恰为 `2023-07-31 -> 2024-11-29` 17 折，训练月数精确为 18、19、...、34；未发现未来月进入训练。该扩展窗满足时间顺序要求。

### 双 Ranker、A/B/C 与效果门

- 月内 `dense rank ascending - 1` 会生成非负整数、多级且保留真实并列的 relevance；配合 `rank:ndcg`、`ndcg_exp_gain=false` 在 XGBoost 3.2 语义上成立。
- qid 按月分组、样本按 qid 非递减且同组连续符合 XGBoost 官方要求；`mean` pair method 对小样本是官方列出的可用策略，pair 数 1 也在允许范围内。
- 34 个主模型、每头每折非退化、重复预测 `<=1e-12` 和 UBJ SHA exact 都是明确的 fail-closed 技术门。
- A 固定逻辑回归 rank10；B 为两头等权月内 percentile；C 仅在 B 非 rank10 且两头原始分数都严格胜 rank10 时替换。Top9 与固定 `fu.SHFE` 保持不变，禁止把逻辑回归概率和 ranker 原始分数直接相加。
- 8 类效果门同时覆盖收益与回撤：总和、leave-best-out、2023/2024 分年非负均双边镜像，另有替换跨年/数量和双目标联合命中率。失败后的固定 stop/no-rescue 文案明确，足以禁止结果后调参，但须先把 P2-2 的关键规则结构化。

### 与 Stage016/017 的结构差异

- Stage016/017 使用 9 项账户路径 z-score 特征、两个连续目标 `XGBRegressor`、39 development 月/15 折；Stage016 原始金额目标 30/30 单叶退化，Stage017 折内标准化后虽有 5,444 个 split nodes，但 9 项效果门仅 3 项通过，收益依赖单月且回撤恶化。
- Stage006 使用 2 项正式排序差异加 6 项全曲线/集中度 PIT 特征、月内 dense relevance、双 `XGBRanker`、35 development 月/17 折，并把 C 门改为相对 rank10 的两头原始分数严格同时胜出。特征信息源和标签机制均不同，满足旧路线“未来只能换不同特征或不同标签机制”的结构变化要求，不是简单替换 scaler 或树参数。
- 但 Stage006 仍是看过 Stage016/017 失败后的自适应后继实验，且复用了双头等权、第10席挑战器和多数效果门。它是可检验的新假设，不是独立于历史选择的首轮实验，过拟合先验风险仍高。

## 外部资料核验

- XGBoost 3.2 Learning to Rank：<https://xgboost.readthedocs.io/en/release_3.2.0/tutorials/learning_to_rank.html>。用于核验 qid 排序/连续组、ranker 输出为 relevance score、`mean` pair sampling 及跨平台可复现限制。
- XGBoost 3.2 参数文档：<https://xgboost.readthedocs.io/en/release_3.2.0/parameter.html>。用于核验 `rank:ndcg`、pair method、normalization 和 `ndcg_exp_gain`。
- scikit-learn TimeSeriesSplit：<https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html>。用于核验训练应早于测试、扩展训练集的基本时间顺序；本评审仍以项目自己的 `next_eval_date` 成熟规则为更严格合同。

## 过拟合与继续价值

- 过拟合判断：本次只读预审本身否；Stage006 实验的先验风险高。原因是它是在多条 XGBoost 失败之后设计，development 只有 35 月、实际 OOS 资格月只有 17 个。只要看到效果后改 pair 数、参数、percentile、C 门、年份、月份、品种或效果门，就构成结果后救援。
- 继续价值判断：有，但当前只能先修合同并重新独立预审。全曲线 PIT 特征和月内序数目标确实与 Stage016/017 不同，值得一次冻结实验；合同未闭合前实现会把本来可证伪的实验变成解释空间过大的实现。

## 解除 BLOCK 的最小条件

1. 同步修订预注册与机器合同，补齐 P2-1 的标签访问状态机、测试预测先封存及 holdout prediction 精确零字段。
2. 将 P2-2 的数据变换禁令、有限值/rank/qid/sort、average percentile、17 月 zero-fill、manifest 与命令/scope 计数逐项结构化。
3. 补齐 P2-3 的平台、解释器、包和 XGBoost build/runtime 身份，并定义训练前后相等门。
4. 修订后重新计算 prereg/contract SHA，重新做独立预运行评审。当前 review 不授权 implementation、测试、训练或效果评估。
