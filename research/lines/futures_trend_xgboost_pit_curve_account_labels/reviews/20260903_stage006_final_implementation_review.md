# Stage006 最终实现独立评审

- 评审日期：2026-09-03（Asia/Shanghai）
- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 评审性质：只读代码/合同审计、纯合成测试、只读元数据预检
- 决策：`BLOCK_STAGE006_DEVELOPMENT_RUN`
- 严重度：`P0/P1/P2/P3 = 0/2/1/0`
- run authorization：未创建

## 结论

当前实现不能获得 Stage006 冻结 development run 授权。冻结输入、运行时身份、PIT 折、双头参数、选择器、效果门、技术失败输出和正常调用下的原子消费大体与合同一致，但生产级入口仍允许调用者替换消费路径、结果目录和 Ranker 工厂；同时，测试标签开放前的 pre-effect seal 复核只检查部分字段形状，不重新绑定实际模型、预测与选择 payload。两类问题分别破坏“一份授权只运行一次”“冻结双 XGBRanker”以及“先封存、后开标签”的核心边界。

因此本评审不创建 `run_authorization.json`，不授权读取真实 development 标签值、训练、效果评价或任何后续阶段。

## Findings

### P0（0）

未发现 P0。

### P1-1：同一授权可通过可注入消费路径重复消费

`run_frozen_stage006()` 暴露 `consumption_path` 与 `result_dir` 参数，并把前者直接传给 `consume_run_authorization()`。单一路径上的 `os.link` 竞争消费是原子的，但唯一性只约束调用者选择的那个路径，没有把消费位置固定到冻结合同或授权身份。调用者可以对同一授权 SHA、scope 和 nonce 连续传入不同 `consumption_path` 与 `result_dir`，每次都生成新的“首次消费”文件并继续进入数据准备。

- 代码证据：runner 第 1939-1945 行暴露可变路径；第 1962-1966 行按调用参数消费。
- 合同冲突：`authorized_training_entrypoint_invocations=1`，future authorization scope 固定为 `one_frozen_stage006_development_run_only_no_holdout_no_production_no_ctp_no_orders`。
- 纯合成反例：对同一伪授权身份调用两次，仅改变消费/结果路径，并在消费后立即抛出 `STOP_AFTER_CONSUME`；两次均得到 `consumed=True`。
- 并发对照：固定同一消费路径做 16 路竞争，结果为 `success=1, rejected=15`，说明原子原语正确，缺陷在顶层允许改变受保护路径。

必须修复：授权运行的生产入口不得接受消费路径或结果目录覆盖；它们必须由冻结常量/合同唯一导出并在入口处逐项拒绝偏离。新增同一授权使用不同路径、串行与并发混合时仍只能一次成功的回归测试。

### P1-2：冻结 XGBRanker 可由调用参数替换，技术门未验证实际模型类型

`run_frozen_stage006()` 暴露 `ranker_factory`，经 `train_sequential_oos()` 传至 `fit_repeated_ranker()` 后直接实例化。实现只检查预测有限、重复预测一致、UBJ bytes 一致与非恒定；技术资格中的参数来自冻结 contract 和训练结果计数，没有证明实际对象是冻结 runtime 中的 `xgboost.XGBRanker`。现有测试也明确用 `_FakeRanker` 贯穿顶层 run。

- 代码证据：runner 第 1945、1982 行允许/转发工厂；第 818、833 行直接调用工厂。
- 影响：一个确定性的替代实现可以产出形式合规的预测与 bytes，绕过“双 XGBRanker、固定实现和 build identity”约束，形成与预注册不同的模型运行。
- 测试证据：专项测试第 940-945、1012-1016 行以 `_FakeRanker` 调用生产级 `run_frozen_stage006()`，没有生产/测试模式隔离。

必须修复：生产入口固定使用导入并经 runtime identity 绑定的 `XGBRanker`，测试依赖注入下沉到不具授权/发布能力的内部纯函数或显式 test-only harness；技术审计应验证实际 estimator 类型及其参数，而不是只复述 contract。

### P2-1：pre-effect seal 复核不绑定实际 payload，畸形模型 SHA 也可放行标签

`write_pre_effect_seal()` 正确计算并 fsync 模型、重复模型、预测和选择 SHA；但 `verify_pre_effect_seal()` 只检查模型 SHA 字典的 key，既不验证四个模型值是 64 位小写 hex，也不接收并重算实际模型、预测、选择 payload。`open_test_month()` 仅凭这个弱验证就读取当月标签。

- 代码证据：runner 第 929-949 行仅对 prediction/selection SHA 做格式检查；第 1060-1069 行随后开放标签。第 1218-1220 行重复调用同一弱验证。
- 合同冲突：每折顺序要求 `reverify_seal_and_assert_current_test_label_rows_read_equals_zero`，预注册明确要求“重新核验 seal 文件及其模型/预测 SHA 后”才能读取标签。
- 纯合成反例：seal 中 `primary_model_sha256` 写入 `NOT_A_SHA/ALSO_NOT_A_SHA`、repeat 写入 `X/Y`，prediction/selection 使用任意合法 64-hex；`verify_pre_effect_seal()` 返回 `accepted=true`。
- 影响：seal 写入后若被替换或损坏，标签仍可能在模型/预测/选择没有真实封存证明时开放，削弱标签值盲态边界。

必须修复：复核函数接收或读取待封存的实际 payload，重算四个模型、ordered predictions 和 selection 的 SHA 并与 seal 精确比较；全部摘要先做 exact-key 和 64-hex 类型检查。新增篡改每一类 payload/摘要后均拒绝开放标签的测试。

### P2（除 P2-1 外）与 P3（0）

未发现其他 P2；未单列 P3。缺失的反例测试已计入对应阻断 finding，不重复计数。

## 已通过的独立核验

- 冻结身份：runner SHA256 `b6b83e6f798de088a747bc0cde52bd713484c44d0ea06dc221ba21be8c1fa3dc`；tests SHA256 `dd1a5add83c518d305931141c58e2fd8c45a3f3a6a7c6560a65d17d7e9292252`。
- 合同身份：prereg `53c9a6e0caad907d21c4fc4e94052836978dd8f81b74ede4e825d94a2b265525`；remediation `72a1ca52459586b0d46fb03ecad78c02119c505e6152f380a85f71d29959a6b0`；training contract `543bd677790fd4d28ed429ae743af39a57f94dece26dfa9fae898b318e6b06ac`；runtime identity `f0a469f5a8387ba8171be5b3e2c8c6b0d9fc0e8de7f5b0914e08ef4f327fddbc`。
- 只读 preflight：冻结合同和当前 runtime identity 精确匹配；全部冻结输入身份通过；`development_labels.csv` 与 `reconciliation.csv` 只做整文件哈希、大小和表头核验，数据行解析计数均为精确整数 0；identity digest 为 `cd5a990efa96873fdcad00a4e3b94c40b4fd47f0eae101ed012f128334ce991b`。
- 标签/PIT 静态路径：aggregate CSV 不交给 pandas；真实标签源仅在 `PhaseGatedLabelStore._load_month()` 中按 manifest 的 per-job `label.json` 身份打开；首批 115 行和逐折 151 行的调用顺序、`next_eval_date <= test_date`、同折测试标签不进入训练的实现路径与合同一致。
- 排序/模型/选择：dense relevance、qid 连续排序、稳定 mergesort、average percentile、A/B/C 和 rank10 外不变的机械实现与合同一致；17 折、34 主+34 repeat、固定参数、无搜索/early stopping 的计数门存在。
- 效果与失败：9 个布尔效果门同时约束收益和回撤；技术失败不发布预测、选择、模型、seal 或 effect，仅发布诊断类工件。
- scope：实现生成 holdout prediction/read/generate/train/effect、production write、CTP、order、参数搜索和额外 fit 的零计数审计；本次评审没有触发这些行为。
- 发布：正常路径先在同父临时目录写文件、fsync、构建 manifest 后 rename，且预先拒绝已存在结果目录。Python 官方文档说明 `os.link` 创建硬链接，`os.rename` 在成功时提供原子重命名语义；这支持固定路径上的实现判断，但不能弥补调用者可改路径的问题。
- XGBoost 外部核对：官方 learning-to-rank 文档确认 ranking 数据由 query/group 组织，`qid` 用于表示 query 边界；当前 qid 组织方向与官方接口语义一致。

## Fresh 验证

- Stage006 专项：`22 passed in 6.47s`。
- 研究线全部 pytest：`79 passed in 19.04s`。
- `py_compile`：runner 与专项测试均通过；pycache 定向到 `/private/tmp`，未写研究线缓存。
- 授权固定路径并发反例：1 成功、15 拒绝，通过。
- 授权路径替换反例：同一授权身份两次消费均成功，失败。
- seal 畸形摘要反例：非法模型 SHA 被接受，失败。
- 当前 Stage006 `run_authorization.json`、`authorization_consumption.json`、`frozen_run` 均不存在。
- 未读取真实 per-job label JSON，未训练模型，未评价真实效果，未运行 Stage005/006 CLI，未读取或生成 holdout 标签，未连接 CTP，未调用订单接口。

## 过拟合与继续价值

- 过拟合判断：本次评审动作本身不是过拟合，因为没有读取真实标签值、训练、比较效果或调整阈值。实现仍处在高研究者自由度风险前，阻断修复只能收紧治理边界，不得据未来结果修改双头、selector、月份、品种或效果门。
- 继续价值判断：有，但仅限修复上述三个实现缺口并增加纯合成回归测试，再做独立复审。当前没有任何模型效果证据，不应据此宣称收益提升，也不应进入真实 development 训练、true-engine、holdout 或生产链路。

## 决策边界

`P0/P1/P2` 非全 0，因此 decision 为 `BLOCK_STAGE006_DEVELOPMENT_RUN`，`allowed=false`。本结论不授权创建或消费 Stage006 run authorization，不授权训练、读取真实 development 标签值、效果评价、真实引擎回测、解封或预测 holdout、模型晋级、收益提升声明、生产修改、CTP、实盘或下单。
