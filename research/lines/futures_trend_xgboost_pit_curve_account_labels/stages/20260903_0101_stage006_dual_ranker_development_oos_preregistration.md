# Stage006 双XGBRanker账户边际development OOS预注册

## 阶段信息

- 预注册时间：2026-09-03 01:01 CST。
- 研究线：`futures_trend_xgboost_pit_curve_account_labels`。
- 当前线上基准：`m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1`。
- 当前授权：首次独立预审结论`BLOCK_STAGE006_IMPLEMENTATION`、`P0/P1/P2/P3=0/0/3/0`；本文件已按三个P2修订，当前只允许独立复审，不授权实现、测试、模型训练、读取sealed holdout标签、真实引擎回测、生产修改、CTP或订单。
- 标签盲态声明：本预注册前只读取Stage005标签CSV表头、文件身份、任务数、日期边界、账务/隔离审计和独立review；未读取266行标签值，未计算标签分布、候选胜率、品种/月度聚合或任何模型结果。
- 阶段性质：逻辑回归A底座与XGBoost第10席挑战器并行的单一冻结development OOS资格实验。
- 是否重要突破：否；只有后续真实引擎A/C同时提高全周期收益并降低最大回撤，才可能成为候选突破。
- 是否触发A/B：是；本阶段只做development账户边际代理A/B/C，不做正式策略A/B或上线。

## 首次预审阻断与修复

- 首次review：`reviews/20260903_stage006_prerun_independent_review.md`，SHA256=`0afee27b68f7a34c12dfcc18326604e52c3bba4b9b4dd95116cecf4ce5410286`；decision SHA256=`9d40e3ca946e9009f02159c8ffce8ccd2dad7dcc3463ee99e9cbaa96e3f9704a`。
- P2-1修复：训练不解析聚合`development_labels.csv`或`reconciliation.csv`的数据行，改为按Stage003元数据和Stage005 manifest定位266个main `job_outputs/<job_id>/label.json`。首折前只开放已成熟的前18月115行；每折先训练、预测、完成B/C选择并把两个主模型、两个重复模型和有序预测的SHA写入并fsync该月`pre_effect_seal`，随后才开放该测试月标签。17个测试月151行在各自seal前读取数必须为0，seal后效果读取151；同折预处理、训练、调参、候选选择和tie-break使用测试标签均为0。
- P2-1 holdout修复：108行holdout只允许读取Stage003特征/分割元数据做身份和边界计数；holdout特征进入预测、holdout标签读取/生成/训练/效果评价均必须为整数0。
- P2-2修复：特征有限性和全部变换禁令、月内rank/qid/稳定排序、`average` percentile、未替换月zero-fill、17月完整序列、manifest范围、68次固定fit和全部命令/scope零计数均写入机器合同。
- P2-3修复：新增`runtime_identity.json`，冻结Darwin `24.6.0`、macOS `15.7.4`、arm64、CPython可执行文件、五个包版本、XGBoost build info、`xgboost/__init__.py`和`libxgboost.dylib`路径/大小/SHA；训练前、训练后和效果评价后必须重建并逐字段相等。未来单次authorization必须绑定修订后的预注册、机器合同、runtime、runner、tests、最终预审和唯一nonce。

## 外部调研与判断

- XGBoost官方Learning to Rank文档要求按查询组组织样本，`qid`必须排序并保持同组连续；默认排序目标为LambdaMART `rank:ndcg`，输出是组内相关性分数而不是概率：<https://xgboost.readthedocs.io/en/stable/tutorials/learning_to_rank.html>。
- 官方文档对小数据建议使用NDCG或pairwise目标并配合`mean` pair构造；本阶段固定`rank:ndcg + mean`，不扫描objective、pair method或pair数量：<https://xgboost.readthedocs.io/en/stable/tutorials/learning_to_rank.html>。
- 官方参数文档说明树深、最小子节点权重和正则项共同控制复杂度；本阶段用深度2、其他复杂度项接近默认值、全量行列采样和单线程，目的是得到一个低自由度、可重复的基线，不是追求development最优：<https://xgboost.readthedocs.io/en/stable/parameter.html#parameters-for-learning-to-rank-rank-ndcg-rank-map-rank-pairwise>。
- 旧`futures_trend_ai_xgboost_ensemble` Stage016的原始金额双回归30/30模型单叶退化，Stage017标准化后虽能分裂但收益依赖单月且回撤恶化。本阶段不能继续救旧回归参数；结构变化必须同时来自新的8项全曲线PIT特征、按月序数排序目标和严格账户边际标签。
- 我的判断：逻辑回归与XGBoost可以同时使用，但不能随意相加不同量纲分数。A继续负责正式Top9和rank10基准；XGBoost只在rank10及以后候选中竞争第10席，固定`fu.SHFE`及其他正式规则不变。

## 冻结输入

- Stage002候选特征：`artifacts/stage002_curve_features/candidate_curve_feature_panel.csv`，374行/47月，SHA256=`9c57370ef9896ab9d64adadf2b8f3feb83e5873dba6a9bbffaad36de2670d7b3`。
- Stage002 summary：SHA256=`16db41bcf756903302006e6444421161240f898b160eab62ea25342ddb30fc4e`；manifest SHA256=`aefe27338abaac7a0c4204d4327824f7bc96e6338b6e4b7f2720bb86c1a49187`。
- Stage003完整split：`artifacts/stage003_account_label_plan/full_feature_split.csv`，SHA256=`a87c73e94eb2afae47ffb106ec60d2720ff881fcecda496aa81af5895165c2b1`。
- Stage003 development jobs：SHA256=`7ee2062e9700d1c1e8800f42ce8dd0ba75470e4953e30c099c37741aed39b8f3`；summary SHA256=`b44e21dc5070675b23c03a26973cc76f4ad8c93d79c6add7be4fd480cd945c0a`。
- Stage005 decision：SHA256=`1cffbfcf0872de9c2a0256071de95ca4a750a72b74025865a1beb8b18fe8a111`，必须保持`passed=true`和`stage005_development_account_labels_complete_allow_stage006_training_preregistration`。
- Stage005 development labels：266行/35月，SHA256=`b4e5f7f638298ff1bd572b378ae096345273488df67c5b5386ba776deec3798d`。
- Stage005 reconciliation：266行，SHA256=`f964992306202c2589a6ff20962aa10144beca58fa393a93dc650b543073b75c`；manifest SHA256=`526f945c2e7523b78076331a2473a606f6f8ce775a0a8ac7850dcd593a31eedf`。
- Stage005独立review：SHA256=`d1933474704dfa116bb88ca5c32465c686166f5541755081e559af9db5816d32`；decision SHA256=`d35d46f90614e3c8a4c59510b05de845afedae5a1db8c8ca1a17913fad1fc6b0`，必须保持`ALLOW_STAGE006_TRAINING_PREREGISTRATION_ONLY`和`P0/P1/P2=0/0/0`。
- 连接键固定为`eval_date,product_vt_symbol,a_rank=candidate_rank`，再与Stage003的`next_eval_date,split`逐行核对；必须一对一得到35月266行development，不能删行、补值或重复。
- 12个月、108行`sealed_account_label_holdout`特征可用于身份/边界计数，但本阶段不得有对应label文件、label行、训练行或预测行；holdout label读取/生成必须为0。
- 标签值源固定为Stage005 campaign的266个main `job_outputs/<job_id>/label.json`；4个A2 label禁止进入模型。聚合`development_labels.csv`和`reconciliation.csv`在Stage006中只做整文件SHA、大小和表头身份核验，不得解析数据行。
- 运行时身份：`artifacts/stage006_dual_ranker_development_oos/runtime_identity.json`，SHA256=`f0a469f5a8387ba8171be5b3e2c8c6b0d9fc0e8de7f5b0914e08ef4f327fddbc`。

## 冻结特征与标签

- 特征顺序固定为8项：`formal_probability_delta_vs_rank10`、`formal_rank_distance`、`front_next_basis_annualized_delta_vs_rank10`、`full_curve_backwardation_slope_delta_vs_rank10`、`full_curve_fit_rmse_delta_vs_rank10`、`open_interest_hhi_delta_vs_rank10`、`volume_hhi_delta_vs_rank10`、`oi_weighted_maturity_days_delta_vs_rank10`。
- 不做缩放、填补、winsorize、符号翻转、交互项、特征选择或品种/年份编码；8项必须全有限，35个rank10锚点必须逐项精确为0。
- 对每个开发月，rank10为账户锚点：`return_delta = candidate.future_return - rank10.future_return`；`drawdown_improvement = candidate.future_max_drawdown - rank10.future_max_drawdown`，数值越大越好；rank10两项必须精确为0。
- 两个训练头分别将本月`return_delta`和`drawdown_improvement`按升序`dense rank - 1`转换为非负整数相关性标签；真实并列保持同级，不用`first`打散，不把两个目标提前加权成单一效用。
- 相关性标签只在每个训练折内由该折允许使用的成熟训练行构造；测试月真实标签仅用于训练完成后的资格门，不得参与训练、特征处理或候选选择。

## 冻结模型

- 两个`XGBRanker`分别学习收益相关性和回撤改善相关性。
- 固定参数：`objective=rank:ndcg`、`eval_metric=ndcg`、`n_estimators=64`、`max_depth=2`、`learning_rate=0.03`、`min_child_weight=1`、`gamma=0`、`subsample=1`、`colsample_bytree=1`、`reg_alpha=0`、`reg_lambda=1`、`tree_method=hist`、`lambdarank_pair_method=mean`、`lambdarank_num_pair_per_sample=1`、`lambdarank_normalization=true`、`lambdarank_score_normalization=true`、`ndcg_exp_gain=false`、`random_state=42`、`n_jobs=1`。
- 不使用early stopping、验证集调参、样本权重、类别/品种权重或GPU；不扫描树数、深度、学习率、pair数、正则、行列采样或随机种子。
- 环境冻结为Python `3.11.15`、numpy `2.4.4`、pandas `2.3.3`、scikit-learn `1.8.0`、xgboost `3.2.0`。
- 每折、每个头在同一输入上独立重复拟合两次；测试预测最大绝对差必须`<=1e-12`，原始UBJ模型SHA必须一致。正式输出只保留第一份模型，第二份只作确定性审计。
- 授权运行固定34个主模型和34个重复模型，共68次`fit`；训练入口调用恰好1次，参数搜索、early stopping、重跑择优和额外fit均为0。
- `mean` pair存在随机采样，因此单一运行平台冻结为`runtime_identity.json`中的Darwin/arm64与XGBoost二进制；训练前、全部34个主模型完成后、效果评价后各重建一次运行时身份，三次必须与冻结文件逐字段相等。

## 冻结PIT切分

- development月份固定为`2022-01-28 -> 2024-11-29`共35个月；最少训练月份固定为18。
- OOS测试月固定为第19至第35个月，即`2023-07-31 -> 2024-11-29`共17折；不根据标签值调整起点或删月。
- 每个测试月只允许`train.eval_date < test.eval_date`且`train.next_eval_date <= test.eval_date`的完整月份进入训练；预期训练月份数精确为`18..34`。
- 每月候选必须有且仅有一个rank10，rank从10连续到该月最大rank且不超过18，产品和连接键唯一；`qid`按`eval_date`升序编码，训练数组按`eval_date,candidate_rank,product_vt_symbol`稳定排序并保持组连续。
- 每折两个头的测试分数都必须至少有2个唯一值；任一头常数输出表示该折无法承担双目标排序，技术门失败，不以tie-break伪造替换。

## 冻结标签访问状态机

1. `identity_only`：只哈希所有冻结输入并读取聚合标签/对账表头；标签数据行读取数必须为0。
2. `initial_mature_training_open`：只按job独立JSON开放前18个成熟月份115行标签；其余151个OOS测试行和全部holdout标签保持未读。
3. 每折`train_predict_select_seal`：只用已开放且`next_eval_date <= test.eval_date`的标签训练；对测试月特征生成两头预测，完成A/B/C选择，序列化两个主模型、两个重复模型和按冻结顺序排列的预测payload，计算SHA，写入并fsync唯一`pre_effect_seals/<test_eval_date>.json`。该seal写入前，本月测试标签读取必须为0。
4. 每折`effect_open`：重新核验seal文件及其模型/预测SHA后，才允许读取本月main job JSON标签，核算实际增量和效果门；这些标签可在下一折因已成熟而进入训练，但禁止反向改变已封存模型、预测或选择。
5. `final_audit`：17个seal必须完整；OOS测试标签seal前读取0、seal后效果读取151、同折或更早折训练使用0、预处理/调参/选择/tie-break使用0；holdout预测/标签/训练/效果全部0。任一计数不等即技术失败且不发布效果。

## 冻结A/B/C选择器

- A：线上条件PIT逻辑回归正式rank10；正式Top9和固定`fu.SHFE`保持不变，不重新训练逻辑回归。
- 每个测试月内，将两个XGBoost原始相关性分数分别按升序`average percentile rank`映射到`(0,1]`；`dual_ranker_score=(return_percentile+drawdown_percentile)/2`，固定等权，不训练融合权重。
- B：在rank10及以后候选中选择`dual_ranker_score`最高者；并列依次按收益头原始分数更高、回撤头原始分数更高、正式rank更低、`product_vt_symbol`字典序更小选择。
- C：只复用B选中的同一候选。仅当B不是rank10，且B的收益头原始分数严格高于当月rank10、回撤头原始分数也严格高于当月rank10时，才替换第10席；否则保持A。
- 禁止把逻辑回归概率与XGBoost相关性原始分数直接相加；禁止按测试真实标签修改候选、权重、门槛、tie-break、TopN、年份或品种。

## 冻结技术门

以下门必须全部通过，否则不评价效果：

1. 所有输入SHA、Stage005/review决策、266行一对一连接、35月、rank连续性、rank10零基准和reconciliation精确成立。
2. 17折精确覆盖`2023-07-31 -> 2024-11-29`，训练月份数`18..34`，PIT标签成熟违规为0，holdout label读取/生成/训练/预测为0。
3. 两头共34个主模型；34组重复预测最大差`<=1e-12`且UBJ SHA一致，模型参数与机器合同逐项相等。
4. 每折两个测试头都非退化，qid组连续，A严格为rank10，B/C选择和tie-break可由冻结预测机械复算。
5. 17个pre-effect seal、34个主模型、34个重复模型的SHA、预测、选择、资格门、三次运行时身份、标签访问审计、命令/scope审计和全部输入输出均进入artifact manifest；训练命令只允许一次授权run，参数扫描、额外fit、意外artifact、生产写、CTP和order计数为0。
6. 标签访问状态机全部整数计数精确成立；holdout prediction/read/generate/train/effect均为0，测试标签不得参与同折预处理、训练、调参、选择或tie-break。

## 冻结development效果门

C相对A必须同时通过以下9个布尔门（8类约束，第一类拆为替换数和跨年覆盖两门）；未替换月份的两项实际增量必须写入精确`0.0`并计入完整17月序列：

1. 实际替换月份数`>=4/17`，且至少覆盖2023和2024两个日历年。
2. 17个月实际`return_delta`合计严格`>0`。
3. 17个月实际`drawdown_improvement`合计严格`>0`。
4. 收益增量序列剔除最好一个月后，合计仍严格`>0`。
5. 回撤改善序列剔除最好一个月后，合计仍严格`>0`。
6. 2023和2024各自收益增量合计都`>=0`。
7. 2023和2024各自回撤改善合计都`>=0`。
8. 实际替换月份中，真实`return_delta > 0`且`drawdown_improvement > 0`的联合命中率`>=50%`。

这些是互斥账户边际标签的development代理门，不是可复利组合收益/最大回撤。Stage006不得发布期末权益、策略总收益、组合最大回撤、Sharpe、总滑点、总交易次数或交易胜率。

## 决策与执行边界

- 当前状态：`stage006_prerun_block_remediated_pending_independent_rereview`。
- 预审若存在P0/P1/P2或不明确授权：停止，不实现、不训练。
- 技术门失败：`stage006_contract_or_pit_invalid_stop_no_effect_claim`。只允许修复可证明的实现错误，并重新独立review；不得根据已见效果改合同。
- 技术门通过但任一效果门失败：`stage006_dual_ranker_development_oos_fail_stop_no_true_engine_no_holdout`。停止当前8特征、双排序头、等权融合、第10席双严格门形状；不得调参、换目标、换权重、删月、删品种、改rank或读holdout救援。
- 全部门通过：`stage006_dual_ranker_development_oos_pass_allow_true_engine_ac_preregistration`。只允许冻结17月C选择，另行预注册一次development真实账户引擎A/C；仍不允许直接回测、读取holdout、修改正式版或上线。
- 修订后的独立复审只有`P0/P1/P2=0/0/0`才可授权TDD实现；实现完成后必须通过专项测试和代码/合同复核。训练run仍需另一个绑定runner/tests/合同/预注册/runtime/final review和唯一nonce的单次authorization receipt。

## 过拟合反思

- 运行前判断：风险高，但本预注册动作本身否。
- 原因：已有多条XGBoost失败路线，且development仅35月；控制手段是标签值盲态下冻结新信息源、单一浅树规格、17折严格PIT、双目标同时成立、leave-best-out和分年度非负。若失败后调整任何模型或选择规则，即构成结果后过拟合。

## 继续价值反思

- 运行前判断：是，但只值得一次冻结实验。
- 原因：Stage005首次把严格PIT全曲线信息与正式账户边际标签对齐；排序模型可规避原始货币目标的尺度退化，并保持逻辑回归Top9不动。它仍只是一个可证伪假设，失败后没有继续扫参价值。

## 合入建议

- 是否更新本线`LINE.md`：预审完成后更新。
- 是否更新`research/registry.md`：预审完成后更新。
- 是否追加根目录`memory.md/back_log.md`：预注册不追加；只有实际训练结果或路线关闭后按重要性追加`back_log.md`，不因代理通过自动追加`memory.md`。
