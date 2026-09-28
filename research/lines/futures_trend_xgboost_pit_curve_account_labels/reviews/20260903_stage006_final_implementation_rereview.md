# Stage006 最终实现 BLOCK 修复第二轮独立复审

- 复审日期：2026-09-03（Asia/Shanghai）
- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 复审性质：只读代码/合同审计、纯合成反例、只读 metadata/header preflight
- 决策：`ALLOW_FROZEN_STAGE006_DEVELOPMENT_RUN`
- 严重度：`P0/P1/P2/P3 = 0/0/0/0`

## 结论

首轮最终实现 review 的 P1-1、P1-2、P2-1 已在当前 runner 与 tests 中逐项关闭，且未发现修复引入的新 P0/P1/P2。当前实现可以创建一份绑定本轮冻结 runner、tests、预注册、training contract、runtime identity、本复审文件和唯一 64-hex nonce 的 Stage006 单次 development run authorization。

该放行仅允许严格按冻结合同执行一次 Stage006 development OOS run。它不代表模型有效、收益提升或可晋级，也不授权 true-engine、holdout、生产、CTP、实盘或订单。

## Findings

### P0（0）

未发现 P0。

### P1（0）

首轮两个 P1 均已关闭，未发现新 P1。

### P2（0）

首轮 P2 已关闭，未发现新 P2。

### P3（0）

未发现需要单列的 P3。

## 原 Finding 复验

### P1-1：生产入口和一次性授权消费已关闭

- `run_frozen_stage006` 的签名参数集合精确为 `{"expected_authorization_sha256"}`；传入 `consumption_path` 等旧参数会直接触发 Python `TypeError`。
- `_canonical_stage006_run_paths()` 从当前 runner 的 `Path(__file__).resolve().parents[1]` 唯一导出 authorization、consumption 和 result 路径，分别固定为本研究线 Stage006 artifact 目录下的 `run_authorization.json`、`authorization_consumption.json` 和 `frozen_run`。
- 生产入口不再接收 `authorization_path`、`consumption_path`、`result_dir` 覆盖；先检查固定结果目录不存在，再从固定授权文件核验身份并写固定消费文件。
- 消费原语使用同目录临时文件、file fsync、`os.link` 原子创建、固定消费文件 fsync 和 directory fsync；已存在时 fail closed。
- 独立纯合成复验：同一路径 16 路并发结果精确为 1 成功、15 拒绝；随后串行重试仍返回 `stage006_authorization_already_consumed`。

结论：同一授权通过更换调用参数重复消费的首轮 P1-1 已关闭。

### P1-2：冻结 XGBRanker 与精确参数门已关闭

- 生产入口没有 `ranker_factory` 参数，调用 `train_sequential_oos()` 时显式固定传入模块内冻结的 `XGBRanker`。
- `build_estimator_audit()` 以对象身份 `ranker_factory is XGBRanker` 检查实际工厂，并把实际/期望 module、qualname、params 记录入 `training_result["estimator_audit"]`。
- 参数比较使用当前训练实际接收的 params 与磁盘冻结 training contract 的 XGBoost params 精确相等，不依赖调用方自行声明。
- `evaluate_technical_qualification()` 新增 `frozen_estimator_and_params_exact` 布尔门；FakeRanker 或参数漂移使技术资格失败，不进入 effect claim。
- Fresh 只读复验：冻结 `XGBRanker`、冻结参数得到 `factory_exact=true`、`params_exact=true`、`estimator_audit_passed=true`；专项合成测试验证 `_FakeRanker` 对应技术门为 false。

结论：调用者替换生产 Ranker 或以 FakeRanker 通过技术门的首轮 P1-2 已关闭。内部纯函数保留 factory 注入仅服务合成测试，不具授权路径和发布能力。

### P2-1：pre-effect seal 真实 payload 重算已关闭

- seal 顶层 key 必须精确等于 stage、test date、seal 前读取计数和四类摘要，额外/缺失字段均拒绝。
- 主模型与重复模型摘要各自必须精确含 `return/drawdown`；四个模型摘要、prediction 摘要和 selection 摘要全部要求 64 位小写 hex。
- `verify_pre_effect_seal()` 必须接收实际主模型 bytes、重复模型 bytes、ordered predictions DataFrame 和 selection mapping，使用与写 seal 相同的规范化序列化重新计算全部 SHA，并与 seal 逐项精确比较。
- `PhaseGatedLabelStore.open_test_month()` 在调用 `_load_month()` 前执行上述强复核；任何异常直接抛出，不会读取该测试月标签。
- `train_sequential_oos()` 在写 seal 后先强复核一次，再把同一实际 payload 交给 `open_test_month()` 二次强复核，随后才允许加载当月标签。
- 独立纯合成反例：主模型、重复模型、ordered predictions、selection 四类实际 payload 分别篡改，全部返回 `pre_effect_payload_sha_mismatch`；四类对应摘要分别篡改也全部拒绝；增加额外 key 返回 `pre_effect_seal_invalid`。合法原始 payload 正常通过。

结论：弱 seal 只检查形状、无法证明标签开放前实际 payload 已封存的首轮 P2-1 已关闭。

## 冻结身份

- runner SHA256：`3dd5bd70875994924c291741e144244a021c8465b67504a2a414a691c824eaac`
- tests SHA256：`fd5ca6151525b42248fa154de247a1702417cbb13ddf89cd05b3fe1c3399d031`
- BLOCK remediation SHA256：`963aef38379bdc65f6806e79abd9f0a1af171ea7b1dc0a3a7ad6091890644976`
- 首轮 BLOCK review SHA256：`5458b1c43456b19d81aa3ca6bb2a45f54763a28c79d65dbe605fde0c01488c55`
- 首轮 BLOCK decision SHA256：`0286bd5af52af2c7c992d795de62706a5cf347c692bd3be076aef9fa122f2740`
- preregistration SHA256：`53c9a6e0caad907d21c4fc4e94052836978dd8f81b74ede4e825d94a2b265525`
- training contract SHA256：`543bd677790fd4d28ed429ae743af39a57f94dece26dfa9fae898b318e6b06ac`
- runtime identity SHA256：`f0a469f5a8387ba8171be5b3e2c8c6b0d9fc0e8de7f5b0914e08ef4f327fddbc`

## 其他无回归核验

- 冻结合同、预注册、runtime identity、既有独立预审及全部冻结输入身份 fresh 通过；input identity digest 为 `cd5a990efa96873fdcad00a4e3b94c40b4fd47f0eae101ed012f128334ce991b`。
- `development_labels.csv` 和 `reconciliation.csv` 只做整文件 SHA、大小与表头核验，数据行 parsed count 分别为精确整数 `0/0`；本复审没有读取真实 per-job `label.json`。
- 115 初始成熟行、17 折逐月 151 测试行、`next_eval_date <= test_date`、后开标签只进入未来已成熟折的 PIT 状态机没有因本次修复改变。
- dense relevance、qid、稳定 mergesort、average percentile、17 月未替换 zero-fill、A/B/C、rank10 外不变、9 个效果布尔门保持冻结。
- 34 主模型、34 repeat 模型、68 fit、固定参数、无参数搜索/early stopping/额外 fit 的技术计数门保持冻结。
- runtime identity 训练前、模型后、效果后三次精确复核，holdout prediction/read/generate/train/effect、生产写、CTP、order、非预期 artifact 等显式零计数保持冻结。
- 技术失败仍只发布诊断，不发布模型、预测、selection、seal 或 effect；正常发布仍采用同父临时目录、file/directory fsync、manifest 和不可覆盖原子 rename。

## Fresh 测试

- Stage006 专项 pytest：`30 passed in 1.94s`。
- 研究线全部 pytest：`87 passed in 21.28s`。
- `py_compile`：runner 与专项测试均通过，pycache 定向至 `/private/tmp`。
- 只读 metadata/header preflight：runtime 和全部输入身份通过；aggregate data rows parsed=`0/0`。
- 授权消费：16 路并发 `1/15`，串行重试拒绝。
- seal：合法 payload 通过；四类 payload、四类摘要及 extra key 篡改全部拒绝。
- 当前复审开始前 Stage006 authorization、consumption、frozen result 均不存在。
- 未运行 Stage005/006 CLI，未训练模型，未做真实效果评价或回测，未读取/生成 holdout 标签，未连接 CTP，未调用订单接口。

## 过拟合与继续价值

- 过拟合判断：本次只收紧并复验授权、模型身份和标签盲态，不读取真实标签值、不训练、不比较效果、不调整模型参数或效果门，因此本次动作不构成结果后过拟合。未来单次 development run 的结果仍只是开发集 OOS 证据，不能替代独立 holdout。
- 继续价值判断：是。三个治理缺口已闭合，执行一次冻结 development run 可以检验双 ranker 结构是否有继续进入 true-engine A/C 预注册的价值；若失败，必须按冻结 fail-stop 停止，不能调参、删月、删品种、改 selector 或读取 holdout 救援。

## 决策与授权边界

`P0/P1/P2=0/0/0`，decision 为 `ALLOW_FROZEN_STAGE006_DEVELOPMENT_RUN`。允许创建且仅创建一份 scope 为 `one_frozen_stage006_development_run_only_no_holdout_no_production_no_ctp_no_orders` 的 authorization，并绑定当前 runner、tests、预注册、training contract、runtime identity、本复审文件及唯一 64-hex nonce。

该 authorization 仅允许一次冻结 Stage006 development OOS run；不授权第二次训练、参数搜索、结果后救援、true-engine 回测、holdout prediction/read/generate/train/effect、模型晋级、收益提升声明、生产写、CTP、实盘或下单。
