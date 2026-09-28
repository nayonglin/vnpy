# Stage000 线上LR基准偏置XGBoost残差修正合同

- line_id：`futures_trend_lr_xgboost_base_margin_residual`
- 当前模式：day
- 记录时间：2026-09-04 15:32 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：新研究线、模型合同和Stage001无标签审计预注册。
- 是否重要突破：否；当前只有独立结构假设，没有模型或收益证据。
- 是否触发A/B：是；冻结未来A/B，但Stage001不执行模型或回测。
- 用户授权：用户已授权数据源重建并要求持续探索XGBoost，目标为全周期收益提高、回撤下降；本阶段只执行最小无标签前置审计。

## 外部调研与判断

- XGBoost官方intercept教程说明，`base_margin`是逐样本全局偏置，可把已有模型输出作为XGBoost起点；使用logistic link时必须传入raw margin而不是概率：<https://xgboost.readthedocs.io/en/stable/tutorials/intercept.html>。
- XGBoost官方预测文档说明，训练和预测都可提供`base_margin`，用于在其他模型输出基础上继续训练：<https://xgboost.readthedocs.io/en/stable/prediction.html>。
- XGBoost官方learning-to-rank文档说明排序任务依赖query group边界；本线不改成rank objective，避免同时改变基准偏置、目标函数和分组语义：<https://xgboost.readthedocs.io/en/release_3.2.0/tutorials/learning_to_rank.html>。
- 本地全仓搜索未发现XGBoost模型使用`base_margin`、LR raw margin或logistic residual stacking；现有`base_margin`命中均指保证金金额，不是机器学习参数。
- 我的判断：直接XGBoost替代、双Ranker、固定50/50融合和账户边际标签已被多条研究线反证；当前最小的新机制不是再换标签或特征，而是保留正式LR作为结构先验，仅允许低容量树学习残差。

## 已知失败家族与禁止复刻

1. `futures_trend_ai_xgboost_ensemble`已关闭直接XGBoost、固定50/50融合及九特征账户边际双回归头；不得以换scaler、树参数或阈值救援。
2. `futures_trend_xgboost_pit_curve_account_labels`已关闭双XGBRanker和严格双头selector。
3. `futures_trend_ai_pit_scorer_rebuild`已证明直接XGBoost及固定融合可退化或无增量。
4. 本线不新增身份特征、不筛月份/品种、不把既有失败残差样本变成规则，也不把历史尾段重新命名为holdout。

## 方案比较

1. 直接XGBoost替代LR：实现简单，但已被现有研究覆盖，且会丢失正式LR先验；拒绝。
2. LR与独立XGBoost固定平均：能同时接入两个模型，但平均权重是额外自由度，既有50/50形状已失败；拒绝。
3. LR raw margin + XGBoost残差：只增加有限非线性修正，A/B差异单一、可归因；采用。

## 当前正式身份与冻结输入

1. 当前指针：`/Users/bytedance/Desktop/person/vnpy_production_live/official_strategy_materials/CURRENT.json`，SHA256=`f17c0f6bfeea4a08ec7c22a1eb63d4b51e4cfb2472f1ce07fac8ce2cc570b219`。
2. 当前release：`m0005_20260901T165450+0800_1961d98ccb2b`；manifest SHA256=`d62e58d01284e30b28054387592604862ffeff6e55a13c63192793e95bc55c21`。
3. 正式LR源码`analyze_qmt_roll_ai_product_suitability_walkforward.py`，SHA256=`7734d1768728a4e591b80e98da2b5bac90636904dad82e0fed5f331a6eb45de4`；m0004与m0005逐字节一致。
4. 月更推理源码`build_qmt_roll_stage182_ai_product_pool_live_inference_runner.py`，SHA256=`ca15504e946e39fe6c5b0180e5bdf07bf38749973ceedd2085ba77480e3c9edc`；m0004与m0005逐字节一致。
5. m0005 Stage182 summary，SHA256=`e119fcdaddb16d173bf8737edd39e3241dc2b277ea96f908d6eeb71bf9bdd5c3`；冻结`training_label_cutoff=2026-06-05`、`train_rows=1386`、`train_months=77`、`feature_count=108`。
6. m0005最新正式池`latest_pool.csv`，SHA256=`9c28774c5f7d02de837a30408c93cd5ba9aa925e03280b1d9b294fbaaf70a814`；Stage001只读身份和108项特征，不读概率、排名或`future_*`列。
7. Stage183 position changes，SHA256=`17c81f2dbb30f836b544161c3fc4d4bd6415151d89b8f8937378739e868c21aa`。
8. Stage183 entry snapshots，SHA256=`f838186527b1453923635bda31ec8e1656a0bdacfec633a6b85f2cda8e3b26a0`。
9. 旧正式76月特征面板`research/lines/futures_trend_ai_score_attribution/artifacts/stage001_20260731/training_samples.csv`，SHA256=`92f36b6647cae9d8db04b0a1351749f9103a1988799dbb8dff0ad1d350d1d431`；Stage001只按`usecols`读取日期、品种和108项特征。

## Stage001无标签合同

Stage001独立复刻正式源码的因果部分，但绝不调用会计算`future_net_pnl_60d`的`add_rolling_features`。它只从当日及历史数据生成20/60/120日滚动特征，并执行以下硬门：

1. 所有冻结输入运行前后SHA256一致；当前指针仍指向m0005，正式策略标识仍为`ai_top10_plus_fu_official_live_v1`。
2. m0004与m0005的正式LR源码、月更推理源码分别逐字节一致，且与冻结hash一致。
3. 因果特征精确108项；按`training_label_cutoff`截取后精确77个月、1386行，每月18品种，全部有限。
4. 与旧正式面板共同的76个月、1368行在108项特征上逐值一致，最大绝对误差不超过`1e-10`。
5. 与m0005 `2026-08-31`最新正式池的11个已发布品种在108项特征上逐值一致，最大绝对误差不超过`1e-10`。
6. 只根据全局交易日历构造`label_end = eval_date后的第60个交易日`；扩展窗每折至少24个训练月，训练月`label_end <= test_eval_date`，泄漏行和泄漏折均为0，active folds至少48。
7. 读取的CSV列名不得以`future_`、`target_`、`sample_weight_`开头；标签值读取、LR/XGBoost fit/predict、策略回测、CTP、订单和生产写入全部为0。
8. 输出只能原子发布到本线`artifacts/stage001_label_free_contract/`；已有final禁止覆盖，manifest必须在发布前后复核。

通过决策：`stage001_m0005_causal_feature_and_pit_contract_pass_allow_stage002_preregistration_only`。

失败决策：`stage001_m0005_causal_feature_or_pit_contract_fail_close_no_labels`。失败后本线关闭，不修改容差、月份、品种、窗口、最少折数或源文件救援。

## 冻结未来模型

- A：每折使用正式108项特征、`StandardScaler`、`LogisticRegression(C=0.20, solver='lbfgs', max_iter=3000, random_state=42)`和正式样本权重。
- B：先拟合A；训练XGBoost时把A的训练集`decision_function`作为`base_margin`，预测时把A的测试集`decision_function`作为`base_margin`。
- B固定参数：`objective='binary:logistic'`、`eval_metric='logloss'`、`n_estimators=32`、`max_depth=1`、`learning_rate=0.03`、`min_child_weight=20`、`gamma=0.1`、`subsample=0.8`、`colsample_bytree=0.8`、`reg_alpha=1.0`、`reg_lambda=20.0`、`max_delta_step=1.0`、`tree_method='hist'`、`random_state=42`、`n_jobs=1`。
- 目标与正式LR一致：`target_future_top_half_60d`；样本权重与正式LR一致。这样A/B只改变残差结构，不同时改变目标、特征和排序空间。
- 禁止直接XGBoost、固定平均、early stopping、参数扫描、概率阈值、标签驱动特征选择、删月删品种及失败后重跑。

## Stage002与真实目标边界

- Stage001通过后仍须另写绑定实现SHA和单次执行授权的Stage002预注册，才能读取既有标签值并fit。
- Stage002必须先证明B相对A在严格development OOS上有稳定增量，且树split nodes大于0、重复运行预测逐字节一致、PIT违规0。
- 产品标签和未来产品PnL不是期末权益或组合最大回撤；只有Stage002通过并经独立review后，才允许冻结真实C9 A/B回测。
- 用户目标的最终必要门仍是：B相对A全周期总收益严格提高、最大回撤绝对值严格下降，并通过分周期、leave-best-period和成本敏感性；任一未过均不得接入正式版本。

## 回测记录占位

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 过拟合反思

- 运行前判断：Stage001否；整体研究是。
- 原因：Stage001只验证身份、因果特征和时间边界；但模型机制由多轮历史失败后提出，且全部可用历史已被广泛观察，后续结果不能冒充独立样本外。

## 继续价值反思

- 运行前判断：有，限Stage001。
- 原因：`base_margin`残差结构在本仓尚未实验，且比直接替换或固定融合少一个模型竞争和权重自由度；如果连m0005特征与PIT折叠都不能无标签复现，应立即停止。

## 合入建议

- 是否更新本线`LINE.md`：是。
- 是否更新`research/registry.md`：Stage001形成结论后登记。
- 是否追加根目录`memory.md/back_log.md`：否；Stage000/001没有回测或正式候选。
