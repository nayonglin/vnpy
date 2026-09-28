# Stage003 预审阻断项修复预注册

## 修复身份与边界

- 修复时间：2026-09-03 03:31 CST
- 原始Stage003预注册：`stages/20260903_0318_stage003_joint_ranker_development_oos_preregistration.md`，SHA256=`859d060217e6ef381170d439086ec0d7097d2c18152f2c0ff0aaacb78124cbea`。
- 首次独立review：`reviews/20260903_stage003_prerun_independent_review.md`，SHA256=`53491926fc97c8bed6d04cc522b7d27eda572fe1f84d38ebb72a5c4c478c6000`。
- 首次review decision：`reviews/20260903_stage003_prerun_review_decision.json`，SHA256=`f7506bbb2d551291c6dfab294623218387167ccc77ca739dc1d0ac3356032b03`。
- 首次决策：`BLOCK_STAGE003_IMPLEMENTATION`，`P0/P1/P2/P3=0/0/2/1`。
- 当前授权：只允许修订无标签治理合同并再次独立预审；不允许实现、创建authorization、读取任何标签数据行、训练、评价、回测、holdout、生产、CTP或订单。
- 本文件与原预注册共同构成修订后合同；发生冲突时，本文件只在authorization、seal复核和空替换JSON语义三类治理项上取代原文，样本、特征、标签目标、模型参数、selector和11项效果阈值完全不变。

## P2-1修复：一次性authorization精确合同

### 固定路径

- authorization唯一canonical路径：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_xgboost_pit_physical_positioning_context/authorizations/stage003_joint_ranker_development_oos_authorization.json`。
- consumption receipt唯一canonical路径：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_xgboost_pit_physical_positioning_context/authorizations/stage003_joint_ranker_development_oos_authorization.consumed.json`。
- 最终结果目录：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_xgboost_pit_physical_positioning_context/artifacts/stage003_joint_ranker_development_oos`。
- 临时结果目录：上述最终目录名加固定后缀`.tmp`；authorization消费前最终/临时目录和consumption receipt必须都不存在。
- 生产入口固定为零参数`main()`调用零参数`run_stage003()`；生产函数不得接受或读取CLI/env中的authorization、consumption、result、input、estimator factory、model params或label store覆盖。测试只能调用独立私有纯函数和临时fixture，不能给生产入口注入路径或factory。

### authorization顶层schema

- 顶层exact keys固定为`decision,scope,nonce,bound_files,result_dir,consumption_receipt_path`，不得缺键或多键。
- `decision`必须是JSON string精确等于`AUTHORIZE_ONE_STAGE003_DEVELOPMENT_OOS_RUN`。
- `scope`必须是JSON string精确等于`one_new_stage003_development_oos_run_only`。
- `nonce`必须是JSON string且精确匹配小写正则`^[0-9a-f]{64}$`；bool、number、null、大小写混合或其他长度全部拒绝。
- `result_dir`和`consumption_receipt_path`必须是JSON string并分别逐字节等于上面固定绝对路径；对现有父目录做`resolve(strict=True)`后拼接固定basename，结果也必须一致，拒绝symlink/`..`/相对路径别名。
- `bound_files`必须是JSON object，键和值类型严格，不允许bool冒充整数或字符串。

### bound_files exact keys

`bound_files`的键集合必须精确等于以下14项，不得缺失或新增：

1. `stage003_original_preregistration`
2. `stage003_remediation_preregistration`
3. `stage003_initial_review`
4. `stage003_initial_review_decision`
5. `stage003_rereview`
6. `stage003_rereview_decision`
7. `training_contract`
8. `runner`
9. `test_contract`
10. `test_state_machine`
11. `test_adversarial`
12. `runtime_identity`
13. `final_implementation_review`
14. `final_implementation_review_decision`

- 每个值必须是exact keys为`path,sha256`的JSON object；`path`必须是canonical绝对string且逐字节等于机器合同中的该键路径，文件必须存在、是普通文件且`resolve(strict=True)`等于声明；`sha256`必须是匹配`^[0-9a-f]{64}$`的JSON string并等于实际文件字节SHA256。
- 14个固定文件路径将在修订后预审、TDD实现和最终实现review完成后写入机器合同；authorization必须逐键与机器合同完全一致，不能由调用者增加或替换键。
- `bound_files`按键排序、每项只含canonical path和sha256后，以UTF-8、`ensure_ascii=false,sort_keys=true,separators=(',',':')`序列化，不带换行；其SHA256固定写入consumption receipt的`bound_files_identity_sha256`。

### consumption receipt exact schema与消费顺序

- consumption receipt顶层exact keys固定为`decision,scope,nonce,authorization_path,authorization_sha256,bound_files_identity_sha256,result_dir`。
- 各字段必须是JSON string；`decision=STAGE003_AUTHORIZATION_CONSUMED`、scope/nonce/result_dir复用已验证authorization，`authorization_path`逐字节等于固定authorization绝对路径，三个SHA字段均为小写64hex并现场复算。
- receipt采用与上面相同的canonical JSON序列化并追加单个LF。
- 生产入口顺序冻结为：第一步只定位固定路径；第二步核验authorization exact schema、14个bound file、runtime和所有SHA；第三步确认receipt、最终结果目录、临时结果目录均不存在；第四步才消费authorization。此前禁止解析Stage002特征/任务表、打开任何job label、创建模型、fit或创建结果工件。
- 消费必须使用固定receipt路径执行`os.open(path, O_WRONLY|O_CREAT|O_EXCL, 0o600)`；完整写入canonical bytes后`fsync(fd)`、关闭，再`fsync`父目录。随后重新读取receipt并逐字段/逐字节复核，只有复核通过才允许创建固定临时结果目录和解析特征。
- receipt已存在、最终/临时结果目录已存在、authorization已漂移或任一bound/runtime不匹配时，必须在label读取、fit、特征解析和结果写入前拒绝。
- 并发两个进程只能一个`O_EXCL`成功；失败者立即停止且不能读取标签或fit。成功进程无论之后成功、失败或崩溃，authorization均已永久消费；串行重试必须失败，不能覆盖/删除receipt或复用nonce。
- 发布结果只能在全部工件完成后把固定临时目录原子rename到固定最终目录；最终目录已存在时禁止覆盖。生产入口不得暴露path/factory override。

### authorization恶意反例测试

- 必须覆盖顶层extra/missing key、错误decision/scope、bool/number/null nonce、非小写或非64hex nonce、bound key替换/缺失/额外、bound value extra key、相对/`..`/symlink路径、SHA漂移、receipt/result/tmp预存在。
- 必须用两个并发进程竞争同一receipt，证明恰好一个消费成功且失败者label read/fit/feature parse计数均0；再串行调用证明永久拒绝。
- 必须证明调用者无法替换authorization/receipt/result路径、estimator factory、model参数和label store。

## P2-2修复：pre-effect seal实际payload强复核

### canonical payload文件

每个活跃折在打开测试标签前必须先持久化以下5个实际文件，均在固定结果临时目录下、按`eval_date`命名且create-once：

1. `models/<eval_date>_primary.ubj`
2. `models/<eval_date>_repeat.ubj`
3. `fold_inputs/<eval_date>.json`
4. `predictions/<eval_date>.json`
5. `selections/<eval_date>.json`

- 两个UBJ必须是实际拟合模型字节；fold input exact keys固定为`eval_date,feature_order,qid,group_boundaries,ordered_training_job_identities,ordered_test_keys`；prediction exact keys固定为`eval_date,ordered_rows`；selection exact keys固定为`eval_date,arm_a,arm_b,arm_c,tie_break_trace`。
- JSON实际payload均使用UTF-8 canonical序列化：`ensure_ascii=false,sort_keys=true,separators=(',',':')`并追加单LF；数组顺序是合同的一部分。
- `feature_order`必须逐项等于冻结六特征；qid、group boundaries和ordered training job identities必须由当前已开放训练状态按固定mergesort重新生成；prediction rows必须逐行绑定测试键、LR概率、原始XGB分数、两个percentile和ensemble；selection必须由prediction实际payload机械重算。

### active seal exact schema

- 路径固定为`pre_effect_seals/<eval_date>.json`；顶层exact keys固定为`seal_type,eval_date,label_read_count_before_seal,primary_model_sha256,repeat_model_sha256,fold_input_sha256,prediction_sha256,selection_sha256`。
- `seal_type`精确为`active_model_fold`；日期为ISO string；读取计数必须是JSON integer精确0且拒绝bool；五个SHA必须是小写64hex string并分别来自上述实际文件字节。
- 5个payload和seal均用同目录临时文件create-once写入并file fsync，再用同目录`os.link(temp,target)`原子创建不可覆盖目标；target已存在或extra payload存在即失败。link成功后fsync目录、unlink临时文件、再次fsync目录。
- seal写入并fsync前测试月label store `_load`调用和行计数必须均为0。

### effect_open前强复核

- `effect_open`必须丢弃用于写seal的内存摘要，从磁盘重新打开seal并要求exact keys/type；再重新读取两个实际UBJ字节和三个JSON payload。
- 必须逐文件重算五个SHA并与seal逐项相等；必须重新解析fold input，复算feature order、qid数组、group boundaries、ordered training job identities和ordered test keys，与当前受控训练状态逐项相等。
- 必须从实际prediction rows重新计算LR/XGB percentile、ensemble和稳定排序，再从实际payload重新生成A/B/C与tie-break trace，要求与selection逐项相等；effect评价只能使用这次重新读取并复算通过的selection，不得使用可变内存选择。
- primary/repeat模型实际bytes SHA必须分别匹配seal，且二者SHA相等；从实际prediction rows重算主/重复预测一致性和非退化门。
- 只有上述全部复核完成后，代码才能调用该测试月label store `_load`并增加计数。任何payload/摘要篡改、extra/missing key、非64hex、类型错误、排序变化或当前状态不一致，必须在label读取计数增加前失败。

### fallback seal exact schema

- 4个fallback seal同样固定为`pre_effect_seals/<eval_date>.json`并create-once；exact keys固定为`seal_type,eval_date,reason,arm_a,arm_b,arm_c,label_read_count_before_seal,label_read_count_after_seal`。
- `seal_type=fallback_fold`、`reason=fallback_no_complete_physical_evidence`；A/B/C三个身份必须逐项相等于该月线上rank10；两个读取计数必须是拒绝bool的JSON integer 0。
- fallback路径不得创建模型/fold input/prediction/selection文件，不得调用label store `_load`。extra/missing key、日期/reason/arm篡改或任一读取计数非0必须失败。
- 恶意反例必须分别篡改五类active payload、seal摘要/extra key和fallback每个关键字段，证明均在测试label read计数增加前拒绝。

## P3-1修复：空替换集合JSON语义

- `replacement_count=0`时，`median_replacement_return_delta`和`median_replacement_drawdown_improvement`两个metric固定写JSON `null`，对应两个gate固定为严格JSON `false`。
- replacement非空时两个metric必须是有限JSON number，禁止NaN/Infinity；gate用显式比较生成原生JSON bool。
- 11项效果gate的键集合必须精确等于机器合同，全部值必须是原生JSON bool，拒绝整数/float/string/null；`effect_gate_pass`必须用`all(value is True for value in gates.values())`计算。
- 最少5个替换门失败时不得短路其余gate，所有metric和11个gate仍需按固定语义完整输出。

## 未改变项

- 样本仍为218特征行、153 development、65 holdout feature；13个初始qid/62行、13折/91测试行、4个fallback月不变。
- 六项特征、`joint_relevance=min(return_relevance,drawdown_relevance)`、单头32棵深度2 XGBRanker全部参数不变。
- LR/XGB月内average percentile各50%、A/B/C、tie-break、物理split门和11项效果阈值不变。
- 153个唯一job标签访问、聚合/reconciliation数据行0、其他113 development main/A2/holdout标签0不变。
- 失败后闭线、不运行true engine、不读holdout、不改生产/CTP/order的边界不变。

## 反思

- 是否过拟合：**否**。本次只补原子授权、seal复核和JSON空集合语义，没有读取标签或改变任何统计样本、模型、selector、效果门；这些修复不能提高预期结果。
- 是否值得继续：**只有修订后独立复审P0/P1/P2全0才值得一次TDD实现**。治理漏洞不应被小样本研究速度所豁免；若仍有可绕过的标签/授权路径，应继续阻断。

