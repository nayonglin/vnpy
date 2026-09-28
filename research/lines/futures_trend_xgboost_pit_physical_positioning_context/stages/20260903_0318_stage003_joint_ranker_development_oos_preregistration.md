# Stage003 逻辑回归与物理信息XGBRanker融合预注册

## 阶段身份与授权边界

- 预注册时间：2026-09-03 03:18 CST
- `line_id`：`futures_trend_xgboost_pit_physical_positioning_context`
- 线上逻辑回归基准：`m0005_20260901T165450+0800_1961d98ccb2b`
- 上游决策：Stage002=`stage002_physical_features_pass_ready_for_training_contract_preregistration`。
- 当前授权：只冻结Stage003机器合同并申请独立预审；当前不授权实现、不读取标签数据行、不训练、不评价效果、不运行策略/真实引擎、不读取sealed holdout标签、不修改生产、不连接CTP、不调用订单API。
- 是否触发A/B：是，但只定义development账户边际代理A/B/C，不是正式策略A/B，更不是上线。
- 是否重要突破：否；只有未来真实引擎和真正未见数据同时证明收益提高、最大回撤下降，才可能成为候选突破。

## 已知信息与多次研究风险

- 本线Stage000-002和本文件编写期间只读取无标签特征、账户任务元数据、聚合标签/对账表头与文件SHA，没有解析账户标签数据行，也没有把物理特征和标签做关联。
- 旧`futures_trend_xgboost_pit_curve_account_labels` Stage006的整体失败结论已知，因此35个月development账户标签已被其他特征假设反复使用，不再是统计意义上的完全未见样本。本Stage003即使通过也只能获得“进入一次development真实引擎A/C预注册”的资格，不能据此读取sealed holdout或接入正式版。
- 本线不是旧Stage006调参：信息源改为basis/member，特征从8项曲线量改为1项逻辑回归差值+5项物理差值，模型从双头共128棵树降为单头32棵树，标签从双模型等权改为事前固定的双目标maximin相关性，selector改为逻辑回归与XGBoost月内名次等权融合。
- 这些结构变化提供新的可证伪假设，但development仅26个活跃月、13个OOS折、完整挑战者仅覆盖13/18品种，过拟合风险仍高。

## 外部调研与判断

- XGBoost官方Learning to Rank要求同一决策月候选用同一`qid`且同组行连续；`rank:ndcg`输出相关性分数，不是概率：<https://xgboost.readthedocs.io/en/stable/tutorials/learning_to_rank.html>。
- 官方参数文档说明树深、树数和正则共同控制复杂度；本阶段固定单一浅树规格，不搜索参数：<https://xgboost.readthedocs.io/en/stable/parameter.html#parameters-for-learning-to-rank-rank-ndcg-rank-map-rank-pairwise>。
- basis/库存与商品期货风险溢价有经济联系，但历史论文不证明当前账户目标可预测：<https://www.nber.org/papers/w13249>。
- 第一性原理判断：逻辑回归继续表达原有趋势/流动性排序，XGBoost只尝试学习“逻辑回归差距在什么物理供需与持仓组合下可以被推翻”。二者不能直接相加原始分数，只能在同月转换为可比名次后融合。

## 冻结输入身份

### 本线无标签特征

- Stage002模型资格特征：`artifacts/stage002_physical_features/model_eligible_feature_panel.csv`，SHA256=`12b1e6afc5b4411e0cbab9b9ea59a6137eefcd7358decd69d2c327cae1407547`。
- Stage002月资格：`artifacts/stage002_physical_features/month_eligibility.csv`，SHA256=`26ee18e1bf9268c2bef98ac6e5138cd35a75589327443bf911ab9eef9f019853`。
- Stage002 summary：SHA256=`13b81dd8b0ee111a022568ceb5a4a76ea88f59e626623c2c305c34af2cc1cf7f`。
- Stage002 manifest：SHA256=`41cfef41f6e4555f4886c5ec71be92637a02250ce1a50ff7499c7b31cc8557ce`。
- Stage002必须保持`15/15`技术门、218模型资格行、35活跃月、六项固定特征、仓单特征0、标签/fit/回测/CTP/order均0。

### 既有账户任务与标签隔离资产

- Stage003完整split元数据：`research/lines/futures_trend_xgboost_pit_curve_account_labels/artifacts/stage003_account_label_plan/full_feature_split.csv`，SHA256=`a87c73e94eb2afae47ffb106ec60d2720ff881fcecda496aa81af5895165c2b1`；只允许读取`eval_date,next_eval_date,product_vt_symbol,a_rank,split`。
- Stage003 development jobs：SHA256=`7ee2062e9700d1c1e8800f42ce8dd0ba75470e4953e30c099c37741aed39b8f3`；只允许读取主任务键、`job_id`和资格身份，4个A2任务禁止进入模型。
- Stage003 summary：SHA256=`b44e21dc5070675b23c03a26973cc76f4ad8c93d79c6add7be4fd480cd945c0a`。
- Stage005完成决策：SHA256=`1cffbfcf0872de9c2a0256071de95ca4a750a72b74025865a1beb8b18fe8a111`，必须保持`stage005_development_account_labels_complete_allow_stage006_training_preregistration`且270/270任务完成。
- Stage005聚合标签：SHA256=`b4e5f7f638298ff1bd572b378ae096345273488df67c5b5386ba776deec3798d`；只允许核验整文件身份和首行14列表头，不得解析数据行。
- Stage005 reconciliation：SHA256=`f964992306202c2589a6ff20962aa10144beca58fa393a93dc650b543073b75c`；只允许核验整文件身份和首行18列表头，不得解析数据行。
- Stage005 manifest：SHA256=`526f945c2e7523b78076331a2473a606f6f8ce775a0a8ac7850dcd593a31eedf`。
- Stage005独立post-run review/decision：SHA256分别为`d1933474704dfa116bb88ca5c32465c686166f5541755081e559af9db5816d32`和`d35d46f90614e3c8a4c59510b05de845afedae5a1db8c8ca1a17913fad1fc6b0`；必须保持`P0/P1/P2=0/0/0`和只允许训练预注册。
- 标签值唯一来源固定为Stage005成功campaign `campaign_20260902T214308+0800_13888/job_outputs/<job_id>/label.json`中的266个main任务；不得使用A2、聚合CSV数据行、reconciliation数据行或其他campaign。

### 冻结运行时

- 运行时身份文件：`research/lines/futures_trend_xgboost_pit_curve_account_labels/artifacts/stage006_dual_ranker_development_oos/runtime_identity.json`，SHA256=`f0a469f5a8387ba8171be5b3e2c8c6b0d9fc0e8de7f5b0914e08ef4f327fddbc`。
- 固定环境：Darwin/arm64、Python `3.11.15`、numpy `2.4.4`、pandas `2.3.3`、scikit-learn `1.8.0`、xgboost `3.2.0`。
- Python可执行文件、`xgboost/__init__.py`、`libxgboost.dylib` SHA必须分别为`34fa8a7b9a08bdb58d3e111b3414440ce3fc1cf9803b037043f7efd5f5f19a15`、`56764c9980ac59493185ee45d56822d4490f12475b741801f0405f3f19cd193f`、`d9ce25b06844b278c9a9eeb7d44ed9e0357c795e59ed129998ff0055620aab47`；实现必须在训练前、全部模型后、效果评价后三次重建身份逐字段相等。
- Stage003预注册、未来机器合同、runner、tests、最终实现review和一次性authorization的SHA必须在运行前全部冻结；任一漂移失败关闭。

## 固定连接与样本

- 连接键固定为`eval_date,product_vt_symbol,a_rank=candidate_rank`；Stage002的218行必须与full split一对一连接，得到development `153`行/`26`活跃月和sealed holdout feature `65`行/`9`活跃月，缺失/重复均为0。
- development前18个日历月包含`13`个初始训练查询组/`62=13锚点+49挑战者`行。
- development OOS日历区间固定为`2023-07-31 -> 2024-11-29`共17个月；其中13个活跃测试折、4个非活跃回退月。
- 13个活跃测试月固定为：`2023-07-31, 2023-08-31, 2023-09-28, 2023-10-31, 2023-11-30, 2024-01-31, 2024-03-29, 2024-04-30, 2024-06-28, 2024-07-31, 2024-08-30, 2024-09-30, 2024-11-29`。
- 4个回退月固定为：`2023-12-29, 2024-02-29, 2024-05-31, 2024-10-31`；不得训练、预测或读取这些月的标签，A/B/C均为线上rank10，效果增量精确0。
- 13折训练查询组固定为`13..25`，训练行固定为`62,69,75,82,88,94,100,107,114,122,130,138,145`。
- 13折测试行固定为`7,6,7,6,6,6,7,7,8,8,8,7,8`，合计91；每折必须有1个rank10和至少2个挑战者。
- 只有`train.eval_date < test.eval_date AND train.next_eval_date <= test.eval_date`的已开放完整月份可训练；不得按标签值删月、删行、改起点或改变完整证据子宇宙。
- 65行sealed holdout特征只允许做身份和边界计数；holdout预测、标签读取/生成、训练、selector和效果评价全部固定为0。

## 冻结六项模型特征

顺序固定且只允许：

1. `formal_probability_delta_vs_rank10`
2. `basis_dom_rate_delta_vs_rank10`
3. `basis_near_rate_delta_vs_rank10`
4. `member_net_position_ratio_delta_vs_rank10`
5. `member_net_position_change_ratio_delta_vs_rank10`
6. `member_turnover_pressure_ratio_delta_vs_rank10`

- 不允许rank距离、产品、交易所、日期、年份、月份、来源时间/年龄、可用性、仓单、缺失指示器或历史策略结果进入矩阵。
- 六项必须全部有限；不做填补、缩放、winsorize、clip、符号翻转、分位变换、手工交互、PCA或特征选择。
- 训练和测试数组固定按`eval_date,a_rank,product_vt_symbol`稳定`mergesort`；`qid`按`eval_date`升序编码，同组必须连续。

## 冻结账户双目标相关性标签

- 对每个已开放训练月，以rank10为账户锚点：`return_delta=candidate.future_return-rank10.future_return`；`drawdown_improvement=candidate.future_max_drawdown-rank10.future_max_drawdown`，数值越大越好；rank10两项必须精确0。
- 每个训练月内分别计算`return_relevance=dense_rank_ascending(return_delta)-1`和`drawdown_relevance=dense_rank_ascending(drawdown_improvement)-1`，真实并列保持同级，不用行序打散。
- 单一训练目标固定为`joint_relevance=min(return_relevance,drawdown_relevance)`，即候选的较弱目标决定相关性；不得改成均值、加权和、乘积、分类标签或按运行结果选目标。
- 每个训练查询组`joint_relevance`必须是有限非负整数且至少2个唯一等级；任一组退化直接技术失败，不删该月、不换标签。
- 测试月标签只能在模型、预测、A/B/C选择和pre-effect seal完全持久化并复核SHA后读取；不得参与同折特征处理、训练、调参、selector或tie-break。

## 冻结单一XGBRanker

- 固定一个`XGBRanker`学习`joint_relevance`，不再训练收益头和回撤头。
- 固定参数：`objective=rank:ndcg`、`eval_metric=ndcg`、`n_estimators=32`、`max_depth=2`、`learning_rate=0.03`、`min_child_weight=1`、`gamma=0`、`subsample=1`、`colsample_bytree=1`、`reg_alpha=0`、`reg_lambda=5`、`tree_method=hist`、`lambdarank_pair_method=mean`、`lambdarank_num_pair_per_sample=1`、`lambdarank_normalization=true`、`lambdarank_score_normalization=true`、`ndcg_exp_gain=false`、`random_state=42`、`n_jobs=1`。
- 不使用early stopping、验证集、样本/类别/产品权重、GPU或自定义目标；参数搜索、特征搜索、seed搜索、重跑择优均为0。
- 每个活跃折在完全相同输入上独立拟合主模型和重复模型各一次；固定13个主模型+13个重复模型=`26`次fit。测试预测最大绝对差必须`<=1e-12`，UBJ模型SHA必须一致。
- 每折测试分数至少2个唯一值；每个主模型必须至少使用1项物理特征产生split，13个主模型合计至少使用3项不同物理特征。形式概率不能作为“XGBoost接入”的唯一信息。

## 冻结A/B/C融合

- A：线上逻辑回归正式rank10；Top9、固定`fu.SHFE`及其他正式规则不变，不重训逻辑回归。
- 每个活跃测试月内，逻辑回归概率和XGBoost原始分数各自按升序`average percentile rank`映射到`(0,1]`。
- B：纯XGBoost诊断臂，选择`xgb_percentile`最高者；并列依次按正式逻辑回归概率更高、`a_rank`更低、`product_vt_symbol`字典序更小。
- C：`ensemble_score=(lr_percentile+xgb_percentile)/2`固定等权；选择ensemble最高者，并列依次按逻辑回归概率更高、`a_rank`更低、symbol字典序更小。只有C不是rank10时才替换第10席，否则保持A。
- 禁止直接相加原始逻辑回归概率和XGBoost分数，禁止学习融合权重、加margin阈值、按品种/年份分支、从B/C中看标签择优或在结果后改变tie-break。
- 4个非活跃OOS月和所有非完整候选固定不能被B/C选择；17个月效果表必须完整，未替换和回退月两项C增量写精确`0.0`。

## 冻结标签访问状态机与seal

1. `identity_only`：核验全部输入、预注册、review、authorization和运行时；聚合标签/reconciliation只读首行表头，数据行解析0；job label读取0。
2. `initial_mature_open`：只打开首个活跃测试月前已成熟的13个查询组/62个main job JSON；核验键、资格SHA、rank10零基准和有限标签。
3. 对每个活跃测试月执行`train_predict_select_seal`：仅用此前已开放且成熟的标签训练主/重复模型，完成预测与A/B/C选择；保存模型、预测、选择、特征顺序、qid、训练行身份与SHA到唯一`pre_effect_seals/<eval_date>.json`并`fsync`文件和目录。本月测试label读取数在seal前必须为0。
4. `effect_open`：重新复核seal及模型/预测SHA后，只打开本月固定main job JSON，计算C相对A真实增量；这些91行每行只首次打开一次，随后可在满足成熟期时从内存状态进入后续训练。
5. 4个回退月只生成`fallback_no_complete_physical_evidence` seal，不读取任何label；最终必须有17个seal，其中13个模型seal+4个回退seal。
6. 完成后标签唯一行访问固定为`62+91=153`；聚合CSV/reconciliation数据行、A2、其余113个development main标签、65行holdout标签及任何其他campaign标签访问均为0。

## 冻结技术门

效果评价前以下全部必须通过：

1. 所有文件SHA、Stage002/Stage003/Stage005/review决策、runtime和未来authorization身份精确；运行前后输入不变。
2. 218行连接为153 development+65 sealed holdout feature；13/13 active split、4回退月、训练/测试行序列、rank/qid和成熟期精确，重复/缺失/PIT违规0。
3. 六项特征有限且顺序固定；模型实际estimator类和全部参数逐项等于机器合同；无隐藏预处理、缺失分支或额外列。
4. 13主+13重复=`26`次fit；13组预测差`<=1e-12`且UBJ SHA一致；每折非退化、每模型至少1个物理split、全体至少3个不同物理特征。
5. A/B/C和tie-break可由冻结预测机械复算；17个pre-effect seal均完整且先于对应测试标签访问，回退月label访问0。
6. 153个唯一job label按状态机精确访问；聚合/reconciliation数据行、A2、其他development、holdout、同折测试训练/调参/选择和所有未授权标签访问均为0。
7. 三次运行时身份完全一致；artifact manifest覆盖机器合同、authorization消费回执、模型、重复模型、预测、seal、标签访问、特征使用、效果表、summary/report及全部SHA。
8. 授权训练入口调用恰好1次；参数/特征/seed搜索、early stopping、额外fit、重跑择优、真实引擎、意外命令/工件、生产写、CTP和order计数均为0。

任一技术门失败，决策固定为`stage003_contract_or_pit_invalid_stop_no_effect_claim`；只允许修复与结果无关、可证明的实现缺陷并重新独立review，不得读取或引用效果后修改合同。

## 冻结development效果门

C相对A必须全部通过以下门；完整17月序列含回退/未替换月精确0：

1. C实际替换月份数`>=5`，且至少覆盖2023和2024两个日历年。
2. 被替换候选至少覆盖3个不同`product_vt_symbol`。
3. 17个月`return_delta`合计严格`>0`。
4. 17个月`drawdown_improvement`合计严格`>0`。
5. 收益增量剔除最好一个月后合计仍严格`>0`。
6. 回撤改善剔除最好一个月后合计仍严格`>0`。
7. 2023和2024各自收益增量合计都`>=0`。
8. 2023和2024各自回撤改善合计都`>=0`。
9. 实际替换月中`return_delta>0 AND drawdown_improvement>0`的联合命中率`>=60%`。
10. 实际替换月收益增量中位数`>=0`。
11. 实际替换月回撤改善中位数`>=0`。

- B只作诊断，不允许B结果替换C决策或触发另一分支。
- 这些是互斥账户边际标签的development代理，不是可复利组合资金曲线；不得发布期末权益、策略总收益、组合最大回撤、Sharpe、总滑点、总交易次数或交易胜率。
- 因development标签已被多条假设复用，即使11门全过也不能视为确认alpha，更不能直接打开sealed holdout。

## 决策与停止规则

- 独立预审只在`P0/P1/P2=0/0/0`且明确决定`ALLOW_STAGE003_TDD_IMPLEMENTATION_ONLY`时允许TDD实现；仍不授权训练。
- 实现完成后必须做专项测试、机器合同、标签访问状态机和恶意反例review。只有最终review再次`P0/P1/P2=0/0/0`，才允许向用户申请绑定全部SHA、64个十六进制字符随机nonce、`scope=one_new_stage003_development_oos_run_only`的一次性authorization。
- 技术门通过但任一效果门失败：`stage003_joint_ranker_development_oos_fail_stop_no_true_engine_no_holdout`。本六特征、joint maximin、单头32树、LR/XGB等权融合形状永久关闭；禁止调参、换标签、换权重、删月/品种、改完整性或读取holdout救援。
- 技术门和11项效果门全部通过：`stage003_joint_ranker_development_oos_pass_allow_true_engine_ac_preregistration_only`。只允许冻结17月C选择并另写一次development真实引擎A/C合同；不自动运行真实引擎，不读取holdout，不修改正式版。
- 无论结果如何，不连接CTP、不调用订单、不切换线上版本。

## 开始反思

- 是否过拟合：**预注册动作本身否，但后续实验风险高**。模型、标签、样本、参数、融合、门和停止规则在标签数据行打开前固定；然而同一35月development标签已用于多条研究，首折仅13个qid，任何失败后再改模型都将是明确的数据窥探。
- 是否值得继续：**只值得一次冻结实验**。basis/member提供独立经济信息且六项差值非退化，单头浅树能直接检验非线性交互；若11项双目标门不能一次通过，就没有继续在该小样本上优化的价值。
