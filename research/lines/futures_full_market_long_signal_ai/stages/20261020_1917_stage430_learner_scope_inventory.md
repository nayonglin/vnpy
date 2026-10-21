# Stage430：最终52输入是否已经测过浅树学习器

记录时间：2026-10-20 19:17 CST；line_id=`futures_full_market_long_signal_ai`。只读有界核查，非突破版本。未读大X/Y、完整成绩表、SQL或模型；未实施、拟合、预测或回测。根状态由root维护。

结论：**有条件GO一次固定浅树对照的设计；当前不授权actual。** 已查代码不能支持“最终真实逐月52输入、当前原child收益目标、K执行已经测过非线性且失败”。这也不是“未测所以必有价值”：前面大量同史尝试给很低先验，唯一合理价值在于检验原输入是否有被线性可加结构遗漏的条件交互。没有新增信息，假设空间更大，过拟合风险会上升；不得复活q、失败target/domain或按结果换树。

## 已测事实与边界

|谱系|实际代码和协议|已经测了什么|不能外推成什么|
|---|---|---|---|
|052/053 HGB|`tools/stage053_maturity_information_fit.py:35-53,189-221`；052协议第15、23、35行|049代表epoch的2N first-exit stress R；共同26原值+26missing+q槽=53，COMMON/ALIGNED/SHUFFLED；固定浅HGB，三cutoff三scope三arm。实际terminal记录27/27fit完成|不是最终每个真实合约child的.25N标签，不带后来K执行；COMMON即使q恒定也不能当作最终训练/动作/目标已测|
|069/071 NARROW|069协议第27-33行；`tools/stage071_settlement_narrow_fit.py:342`|WIDE与.25N分别模拟，各COMMON/SETTLEMENT/OHLC_PROXY；Ridge；代表epoch母体|不是逐月child，也没有树；不能因窄损对照失败就否定当前child输入全部非线性交互|
|092/094 RFF|092协议第25-39行；`tools/stage094_crossday_order_fit.py:37-40,113-146`|共同52+sequence_missing+128RFF=181；RFF的91输入是11自身摘要+20×4序列；ORDER/BAG，同NARROW代表标签，Ridge头。实际terminal12/12fit完成|是非线性表示实验，但主对比是时间顺序与集合，不是最终52的浅树与线性对照；没有逐月动作/K，也无新COMMON对照|
|128-130最终child52|128协议第9-13行；`tools/stage130_contract_choice_fit.py:19-25,146-168`；`tools/stage129_contract_choice_dataset.py:295-345`|每个真实月份自身重建52；.25N初损、20low、anchor/lifecycle first-exit stress net R；family-u区间union/分月/等u权重；Ridge1；实际6/6fit完成|这是当前主要学习谱系，未见HGB或RFF替换同一52输入的actual|
|156/157 K|156/157实施记录；`tools/stage157_voluntary_cash.py:67-86,159,223`|复用130分数；新入场D<K并重选，持仓有效生命周期min(原边界,K)，四新现金完成（原报告定位错误、元数据续接透明保留）|不新增训练、不将原label自动改成K收益；K执行与原训练目标并不完全一致，但这不是未经验证就改目标的理由|
|217/218 DOMAIN|217协议第15-19行；`tools/stage218_training_domain_loss_fit.py:205`|仅改变训练支持与质量总量，仍52/Ridge/旧原Y|不能把失败域筛选当浅树失败，也不应为新实验顺手复活DOMAIN|
|237/238 K-target|237协议第9-17行；238 actual terminal|六原scaler、DOMAIN支持/权重固定，只替换Kstress Y；仍Ridge，6/6fit；held门失败、0cash|未测试非线性；失败不能成为改树去救K-target的理由|
|373最新成熟|`tools/stage373_latest_mature_refit.py:233-272`|扩成熟训练池，仍原child `net_R_stress`、union权重、52和Ridge；不是K-target|当前前瞻两模型仍不能给本次新学习器提供未见历史绩效|

上述actual终态只核053、094、130、238小terminal；069/217的详细经济胜负未重审，且本结论不依赖其胜负。代码范围内未发现最终组合的非线性actual；这是有限谱系核查，不能声称穷尽一切未归档外部实验。

## 外部调研与判断

实际阅读[sklearn HGB官方文档](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html)与[官方GitHub 1.6.1源码](https://github.com/scikit-learn/scikit-learn/blob/1.6.1/sklearn/ensemble/_hist_gradient_boosting/gradient_boosting.py)。树允许同一路径连续在不同字段分裂，所以能表达例如“距离止损小，且价格位置/流动性状态适合”这种非加性交互；这是函数类能力，**不是期货alpha证据**。文档支持sample_weight、深度/叶/最少样本约束；early_stopping='auto'在大样本可能自动留出验证，公平时序实验应沿旧052显式关闭。在线stable当前显示1.9.1，本仓冻结1.6.1不升级；实现应绑定旧已接受参数。

另打开Friedman原论文入口，但页面无正文返回，不作为实际读过或支持论断的来源。有效来源仅上述两项；未安装外部算法或skill。

## 最小公平比较建议（待root冻结）

1. 控制直接复用130训练身份、已接受scaler/权重/原child `net_R_stress`、原六fold预测及156/157/205 K控制，不重训Ridge。不加入q、不换DOMAIN或K-target，不因标签尾部不一致顺手改变目标。
2. 唯一候选沿052原HGB参数：squared_error、learning_rate=.05、max_iter=100、max_leaf_nodes=7、max_depth=3、min_samples_leaf=100、l2_regularization=1、max_bins=127、max_features=1、categorical_features=None、early_stopping=False、warm_start=False、random_state=20261018；相同标准化52输入/权重、相同成熟时钟与两个cutoff×三scope，最多6fit；无网格/新seed/早停/新阈值，不用树对missing的内建处理替换原52合同。
3. 同完整child/mother域；完全相同score>0、D<K、母内排序、普通/F家族顺序、anchor、容量、.25N/风险/费滑。模型变化会改品种数和手数，是完整筛选政策对照，不是固定交易的纯预测因果效应。
4. root事前选一个明确控制的证伪门。建议两held家族×两部署段的完整等u原target差都>0且无可翻转unknown，再准许最多4个候选自有现金，与原K四本配对；2020stress自身正、成本后收益提高且DD变浅，其他三本同方向，并报告固定252日块CI。不得用训练R²/持仓少/DD低代替目标。无动作变化或held失败则0cash；门不能在结果后改。
5. 每个真实训练/回测阶段独立审查一次，保存模型、全预测与真实账本；不重复旧suite/旧金融。即使通过也只是高度适应性历史证据，需要未来数据验证，不授予加注或生产资格。

上述严格门是有限价值预算建议，不是已获准协议。root若认为当前研究者选择风险已经大于可识别增量，可直接NO-GO，不应凭“新信息优先”把模型类能力混同数据的数学冗余，也不应凭“尚未测”无限开模型家族。

## 结果、反思与TODO

新增/修改/删除策略参数、训练、资金回测、旧成绩均0。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。

开始与结束判断：本次核查本身不按收益调参；若执行更强函数类，同史多轮择题的过拟合风险**是**，固定浅树只能限制不能消除。继续价值**有条件是**，仅一次同输入/目标/执行的低容量函数类证伪；结果失败不换深度/窗口/目标/q/风险救参。整体目标未完成。TODO由root裁决是否冻结一次6fit方案，当前0实施/0训练。
