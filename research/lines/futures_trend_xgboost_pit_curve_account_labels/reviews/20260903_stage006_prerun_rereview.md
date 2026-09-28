# Stage006 首次 BLOCK 修订后第二轮独立预运行复审

- 复审日期：2026-09-03
- 研究线：`futures_trend_xgboost_pit_curve_account_labels`
- 修订预注册：`stages/20260903_0101_stage006_dual_ranker_development_oos_preregistration.md`
- 机器合同：`artifacts/stage006_dual_ranker_development_oos/training_contract.json`
- 运行时身份：`artifacts/stage006_dual_ranker_development_oos/runtime_identity.json`
- 修复记录：`stages/20260903_0113_stage006_prerun_block_remediation_preregistration.md`
- 复审性质：独立、只读、标签值盲态下的第二轮 pre-run review
- 执行边界：未读取 `development_labels.csv` 或 `reconciliation.csv` 的数据行，未打开任何 job `label.json`；未训练、未实现、未创建模型或预测文件、未运行 Stage005/006 入口、未访问 holdout 标签、未连接 CTP、未调用订单 API。

## 决策

**ALLOW_STAGE006_IMPLEMENTATION_ONLY**

严重度精确计数：

- P0：0
- P1：0
- P2：0
- P3：0

首次 review 的 P2-1、P2-2、P2-3 均已在修订 Markdown 与机器合同中同步关闭，独立复算未发现修复引入的新 P0/P1/P2。该结论只授权按冻结合同进行 TDD 实现和不接触真实标签的合成测试；不授权训练、读取任何 development/holdout 标签值、效果评价、真实引擎回测、生产修改、CTP 或订单。实现完成后仍需代码/合同复核，并另建绑定冻结身份与唯一 nonce 的单次训练 authorization。

## Findings

未发现 finding。

## 原 P2 逐项关闭

### P2-1：标签访问状态机与 holdout 隔离已关闭

- 聚合 `development_labels.csv` 和 `reconciliation.csv` 在合同中固定为整文件 SHA/size 与表头核验，数据行解析计数必须为精确整数 0。复审仅流式计算整文件 SHA、读取第一行表头，实际数据行解析为 0；两项 SHA 分别为 `b4e5f7f638298ff1bd572b378ae096345273488df67c5b5386ba776deec3798d` 和 `f964992306202c2589a6ff20962aa10144beca58fa393a93dc650b543073b75c`。
- 标签值源固定为 266 个 main `job_outputs/<job_id>/label.json`，A2 允许数为 0。复审不打开标签文件，只从冻结 Stage005 manifest 和 266 份 worker receipt 核验身份：manifest 中 270 个 label 路径恰为 266 main 加 4 A2；266 个 main 的 job_id/type 及 receipt `output_sha256.label.json` 与 manifest 全部一致，mismatch 为 0。
- Stage003 日期/任务元数据独立重算：development 35 月；前 18 月为 115 行，最大 `eval_date=2023-06-30`、最大 `next_eval_date=2023-07-31`；后 17 个测试月合计 151 行。
- 17 折训练月份数精确为 18..34，训练行数依次为 `115,123,131,140,149,158,167,176,185,194,203,212,221,230,239,248,257`。每折训练集合都只含当时已经开放且满足 `next_eval_date <= test.eval_date` 的月份；当前测试月在自身 seal 前未开放。
- 修订合同明确允许某测试月标签在自身 `pre_effect_seal` 后做效果读取，并仅在后续折已成熟时进入训练；禁止进入同折或更早折。该顺序不会把已见测试标签反向用于自身模型、预处理、调参、选择或 tie-break。
- `required_final_integer_counts` 对聚合解析、115 初始行、151 测试行 seal 前/后访问、同折训练/预处理/调参/选择/tie-break及 holdout prediction/read/generate/train/effect 均给出精确整数；类型核验无 bool 冒充 count。
- holdout 108 行只可作特征/分割身份计数；预测、标签读取、生成、训练和效果评价全部固定为整数 0。

### P2-2：数据、selector、效果门和 scope 已机器化

- `data_policy` 明确 8 项 `float64` 特征必须全有限，missing、正负无穷均禁止；缩放、填补、winsorize、符号翻转、交互、特征选择、产品编码和年份编码全部为 `none`。
- 月内规则明确为一个 rank10、rank 10 至月最大 rank 连续且最大 18、产品/连接键唯一；稳定排序固定 `mergesort(eval_date,candidate_rank,product_vt_symbol)`，三列升序。
- qid 固定从升序 `eval_date` 零基编码为 `int64`，同组连续且全序列非递减，符合 XGBoost ranker 的 group 要求。
- 两头分数映射固定为测试月内升序 `average percentile`、`pct=true`、值域 `(0,1]`；A/B/C、两头 0.5/0.5 权重和四级 tie-break 均结构化，无 dense/min/max percentile 歧义。
- effect contract 固定完整 17 月序列，未替换月份收益与回撤均填精确 `0.0`；9 个布尔门的 comparator、threshold、必需年份和联合正命中率均逐项机器化，独立字段计数为 9。
- 模型数量固定 34 主模型、34 重复模型、68 次 fit；训练入口 1 次，参数搜索、early stopping、额外 fit、holdout prediction、生产写、CTP、order、意外命令和意外 artifact 均为精确整数 0。
- artifact contract 要求 17 个 pre-effect seal、34 主 UBJ、34 重复模型 SHA、预测、选择、fold/label/runtime/input/scope 审计和最终 receipt 全部纳入 manifest；失败目录不可覆盖，发布采用同父目录原子 rename 和 file/directory fsync。

### P2-3：运行时身份和未来授权绑定已关闭

- `runtime_identity.json` SHA256 实测为 `f0a469f5a8387ba8171be5b3e2c8c6b0d9fc0e8de7f5b0914e08ef4f327fddbc`。
- 用冻结的 `.py311/bin/python3.11 -B` 独立重新生成身份，和 JSON 逐字段完全相等：Darwin `24.6.0`、macOS `15.7.4`、arm64、CPython `3.11.15`、numpy `2.4.4`、pandas `2.3.3`、scikit-learn `1.8.0`、xgboost `3.2.0`。
- Python executable、`xgboost/__init__.py`、`libxgboost.dylib` 的路径、size、SHA 全部真实匹配；XGBoost build info 逐字段匹配，包括 CLANG 15、CPU/OpenMP、CUDA/NCCL/RMM 均关闭或按冻结值一致。
- 合同要求在训练前、34 个主模型完成后、效果评价后三次重建 identity，三次均须与冻结 JSON 完全相等。官方 XGBoost 文档说明 `mean` pair method 会随机采样且可能存在平台差异，因此该三点绑定具有直接必要性。
- 未来训练 authorization 必须绑定 runner、tests、修订预注册、training contract、runtime identity、最终独立预审和唯一 64-hex nonce；scope 固定为一次 development run，明确排除 holdout、生产、CTP 和订单。

## 新回归检查

### Pre-effect seal

- 每折顺序被结构化为 runtime/input 核验、2 主+2 重复训练、当前测试特征预测、无测试标签的 A/B/C 选择、序列化并哈希模型/预测/选择、写入并 fsync 唯一 seal、重新核验 seal 与当前测试标签读取数 0，随后才开放当月标签。
- seal 数固定 17，路径固定 `pre_effect_seals/<test_eval_date>.json`；必须包含主模型 SHA、重复模型 SHA、有序预测 payload SHA 和选择 payload SHA。该定义足以把选择固定在标签开放之前。

### 技术失败不披露效果

- technical decision 固定为 `stage006_contract_or_pit_invalid_stop_no_effect_claim`。
- publication policy 固定 `no_effect_artifacts_on_technical_fail`，只有技术门通过才允许 `effect_qualification` 进入最终 bundle；不确定的 post-rename 状态必须 quarantine。
- 标签访问状态机或任一整数计数失败均属于技术失败并禁止发布效果，不得用部分折效果解释或救援合同。

### 身份与修订范围

- 修订预注册 SHA256：`53c9a6e0caad907d21c4fc4e94052836978dd8f81b74ede4e825d94a2b265525`。
- 机器合同 SHA256：`543bd677790fd4d28ed429ae743af39a57f94dece26dfa9fae898b318e6b06ac`。
- 修复记录 SHA256：`72a1ca52459586b0d46fb03ecad78c02119c505e6152f380a85f71d29959a6b0`。
- 第一轮 review/decision SHA 仍为 `0afee27b68f7a34c12dfcc18326604e52c3bba4b9b4dd95116cecf4ce5410286` / `9d40e3ca946e9009f02159c8ffce8ccd2dad7dcc3463ee99e9cbaa96e3f9704a`，未变化。
- 修订只收紧访问、机器语义、运行时和授权治理；8 特征、35 月、17 折、双 Ranker 参数、A/B/C 与 9 个效果布尔门未发生结果导向变化。

## 外部依据

- XGBoost 3.2 Learning to Rank：<https://xgboost.readthedocs.io/en/release_3.2.0/tutorials/learning_to_rank.html>。用于核验 qid 非递减/同组连续、`mean` pair sampling 和跨平台可复现边界。
- XGBoost 3.2 Python API：<https://xgboost.readthedocs.io/en/release_3.2.0/python/python_api.html>。用于核验 `xgboost.build_info()`；官方同时说明 build-time 与 runtime dependency 不等价，因此冻结 build info、初始化文件和共享库身份是合理补强。

## Fresh 核验命令边界

- 运行了只读 `shasum -a 256`、JSON/CSV 元数据审计脚本和 runtime identity 重建脚本。
- aggregate CSV 仅做流式整文件哈希与第一行表头读取；未把任何数据行交给 CSV parser。
- per-job label 仅通过 Stage005 manifest 和 worker receipt 的路径/SHA 元数据核验，未打开 label 文件。
- 导入 XGBoost 仅调用版本与 `build_info()`，没有构造或拟合模型；未运行 pytest、Stage005/006 runner 或任何训练/效果入口。

## 过拟合与继续价值

- 过拟合判断：本次复审及合同治理修订本身否；Stage006 实验的先验风险仍高。修订没有读取标签或改变模型/效果门，只减少实现自由度；已有多条失败路线和仅 17 个 development OOS 月仍意味着训练结果不能外推为 holdout 或真实收益。
- 继续价值判断：是，但当前仅值得进入冻结合同下的 TDD 实现和合成测试。实现通过不等于模型有效；训练前还必须完成代码/合同复核和一次性授权，训练失败后不得调参、改 selector、删月/品种或读取 holdout 救援。
