# Stage534：经济行业身份与部分共享截距的独立科学审查

- line_id：`futures_full_market_long_signal_ai`。
- 时间：2026-10-21 04:06 CST；工作区 `/Users/mac/Desktop/fian`；day 模式。
- 性质：收益前机制与低自由度设计审查，非重要突破，未创建正式 A/B/C 臂。
- 完整目标保持六所 98 历史产品 ID / 95 family、全市场高质量 long、更高成本后收益与更低回撤；窄损、加注另验。非正式 C9 月池。
- 已读 registry、本线 LINE 顶部与532、129/130小记录及少量129/130/071源码；未读行情、动作标签大表、模型文件、预测/收益大表。旧 HGB、annual、DOMAIN、K、log、会员 identity、退出、q 固定包均不重开。

## 独立结论

**有条件 GO，仅支持一次“固定 COMMON52 头 + 行业残差截距”的可证伪检验；不支持先搭完整多任务模型或立刻跑现金。** 行业身份是收益以外的对象信息，可成为未见 family 的可迁移先验；它不是实时冲击，也不是某行业永远值得做多的方向定律。合格命题是：在既有52项信息已经给定后，物理用途/生产与套保结构相近的品种，其成本后 long 结果是否仍有可跨时期、跨 family 转移的基率残差。命题可以为零，也允许为负。

这比“行业不同所以应分模型”严格：必须胜过原完全池化头，也必须胜过同容量的任意 family 分组。只有前者改善，是额外容量/历史校准的证据，不能归因于经济 taxonomy。只有训练内分行业均值不同，不是增量预测证据。当前没有任何新盈利结果，不要求测试前保证盈利。

## 原作者资料、代码与经济边界

1. [Evgeniou、Micchelli、Pontil，JMLR 2005原文](https://www.jmlr.org/papers/volume6/evgeniou05a/evgeniou05a.pdf)把任务关系放进二次正则项，说明完全共享与独立学习之间可作受约束的共享。它支持统计结构，不证明任务相关、不选定商品行业，更不证明交易 alpha。本文没有找到并核到原作者的对应可运行仓库，不把第三方复刻冒充原代码。
2. 原作者的[Ong、Herremans 2023论文](https://arxiv.org/html/2306.13661v1)及[固定提交的模型代码](https://github.com/joelowj/mtl-tsmom/blob/b07fa1d0a3c71bef3d3614e0d8f4233477e42df1/core/model.py)已核：代码为共享 LSTM 后接任务网络；论文的主要/辅助任务是组合构建与多种未来波动率。**这不是行业随机截距实验**，其连续期货、多空组合和收益不能外推为本线真实合约 long/窄损证据。这里只接受“共享什么必须讲清”这一设计约束。
3. [Momentum Transformer原作者示例源码](https://github.com/kieranjwood/trading-momentum-transformer/blob/master/examples/run_dmn_experiment.py)第9—11行明确把所有 ticker 映射为 `COMB`，没有在这个示例填真实 asset class。不能因为接口叫 `ASSET_CLASS_MAPPING` 就声称其公开示例验证过经济分类增量。[PyMC维护者原始示例](https://github.com/pymc-devs/pymc-examples/blob/main/examples/generalized_linear_models/multilevel_modeling.ipynb)实际区分 varying intercept/common slope 与 varying intercept/slope；它是数值语义参考，不是金融证据，也不为本轮引入 MCMC 或学习方差超参数。
4. [RBA Hambur、Stenner 2016原始研究](https://www.rba.gov.au/publications/bulletin/2016/mar/7.html)给出的绝对 long 传导是：若生产者卖出套保需求大于消费者买入需求，承接风险的多方可能获补偿；反向套保结构也可能补偿空方。期限、商品与时期会改变这条关系，近月个体风险溢价难以统计识别。这提供经济异质性的理由，**不推出静态行业截距在本线短止损路径上恒定，也不推出某行业的正号**。
5. [Bianchi、Jung《The Sector Anatomy of Commodity Risk Premia》作者页](https://www.whitesphd.com/workingpapers/wp3/)可读摘要指出 sector-wide 与 sector-adjusted 两类特征互补，且只有后者具有超标准商品因子的 alpha。它是 working paper；本轮 SSRN全文403，未声称读过全文/代码。其意义是反对把行业归属、行业共同风险和可交易信息混为一谈，不据摘要挑赢家行业。
6. [南华2019编制细则公告](https://www.nanhua.net/news/2019/05/910ca2e9-f28d-4fe1-8d33-67afcaecfece.html)与[2022官方分类细则](https://www.nanhua.net/cmsbigfile/2022/11/76b2ec32-618d-44b7-89a4-97d22ed2f3c1/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E7%BC%96%E5%88%B6%E7%BB%86%E5%88%99%EF%BC%882022%EF%BC%89%E5%8F%91%E5%B8%83%E5%85%AC%E5%91%8A.pdf)说明经济分类并非根据本线收益发明。但指数成分/流动性门不能成为本线母体筛选；2019/2022文件也不认证2010年存在同一版本。逐95 family映射仍须由root冻结、保留来源与重建身份。本轮只核官方入口与网页可见分类说明，未逐页审PDF、未认证全98映射。

我的经济判断：稳定的用途、储存/生产周期、套保者结构可以令“相同技术特征”的条件分布不完全可交换；行业是这类机制的粗糙代理。**因此存在可测试的新条件变量，不只是为旧列换一个名字；但行业本身不保证旧52列之外仍有剩余信息。** 共同宏观冲击、金融化和制度变化也会使该先验失效。没有依据先指定贵金属、黑色或农产品的正/负号，更没有依据同时加行业斜率、时间交互、隐类或 embedding。

## 本地已验证的作用位置

- 130使用26项原值及26项missing flags；071 COMMON 列名不含 sector、family one-hot 或经济行业。130为统一 `Ridge(alpha=1, fit_intercept=True, solver=cholesky)`，2 cutoff × main/held0/held1，共六个头。
- 原训练：成熟/已知时刻严格在cutoff前；family-u持有区间union、按月份分配质量、等u，再把 sample weight 均值归一为1。不能把百万动作行误认为百万独立经历。
- 行业截距在同 family、同product的所有合约月上相同，因此 `argmax_month(base_score + delta_sector)` 与原排序相同。它能改变 `score>0` 准入；普通/F资格和后续账户占用可能因此改变。它不能被宣传成改善月份相对排序，不能用改month/退出来救分。
- 157已有的 `sector` 归因仅 financial/commodity；不等于已验收了完整经济行业表。不能凭该字段称 taxonomy 已ready。

## 唯一建议设计：固定头的、零均值行业残差截距

只保留三个事前定义的预测臂：A=原共同头，T=真实taxonomy截距，P=一次固定任意分组截距。此处A/T/P是新比较别名，三个臂全部沿同一个当前accepted月份政策；不能拿130的A-canonical去比较T-all-months。它们共同使用**相同的每fold base score、scaler、52列、训练身份、标签成熟合同及原权重**。不重训/挑选任何COMMON字段，不引入年度版本或新目标。若当前 accepted 头与当前拟检验标签/生命周期并非同一合同，必须先在小manifest层说明；不能悄悄换标签并宣称只加行业。

对每个原fold，训练残差 `r_i = y_i - base_score_i`。仅训练区内成熟标签参与，预测区标签绝不反流。用原权重 `w_i` 定义 `v_i = w_i / sum_{j:u_j=u_i} w_j`，故每个有训练样本的源日质量总和恰为1。这个固定缩放保留原权重相对关系，把单位改成**全市场源日质量**，并不把源日宣称为统计独立样本。

每个分组的训练质量为 `m_s=sum(v_i)`、残差总量 `b_s=sum(v_i*r_i)`。唯一收缩常数固定 `kappa=252` 个全市场源日质量：这是一次事前保守约定，取一交易年的常用尺度，**不是论文给出的最优强度**。不能在结果后改成21/63/126/504，也不能直接把原均值1的动作行权重配alpha1并称强收缩。[sklearn维护者源码](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/linear_model/_ridge.py)使用带权平方损失加惩罚，改变损失总质量会改变同一数值alpha的含义。

固定 base 头后求解：

```text
min_delta  sum_i v_i (r_i-delta_s(i))^2 + 252 * sum_s delta_s^2
subject to sum_s m_s delta_s = 0
```

该约束保持全局截距，避免实验混入整体准入阈值平移。可用唯一闭式解：

```text
eta = [sum_s m_s*b_s/(m_s+252)] / [sum_s m_s^2/(m_s+252)]
delta_s = (b_s-eta*m_s)/(m_s+252)
```

对训练质量为0的行业/未知taxonomy，固定 `delta=0`、完整A fallback，并保留未支持状态。只有一个有效行业时约束给全0。T/P均不估计额外global intercept、先验方差或行业斜率。训练残差来自固定已训练头，不冒称cross-fit残差；这是受约束残差校准器，而非联合最优hierarchical regression。它可能保守，失败不得改成联合重估52个斜率救参。

### taxonomy、任意标签和留族如何隔离

1. taxonomy以底层family为单位，F与普通品种相同；分类粒度与95行映射在读新结果前冻结，一family一类，金融/退市/缺行情身份不删除。按标的物用途/合约对象归类；重建或未知明确标注，不用历史盈利、相关性聚类或本线成绩分组。
2. P仅一次：在既有 `sha256(family_id)%2` 的两个组内分别按 `sha256('stage534-sector-placebo-v1:'+family_id)` 排序，把各组真实行业标签的固定排序多重集合分配给该排序。由此保留每hash组的行业family数、完整母体和名义参数数，不重新抽seed。**全局重命名行业无效**，那不会改变分组；必须打乱family与标签的关系。
3. 每个原held fold：训练完全排除被测试family；该family只凭收益前taxonomy接受另一hash组同行业的截距。不可从main头借训练残差，不可把同family普通/F放到两边，不允许held目标影响scaler/offset。原main与两个held scope均保留，不以有利组替代。
4. 逐fold公开T/P的行业训练family数、测试family数、源日质量、0支持fallback、上市/成熟mask造成的质量差异及有效自由度。固定置乱保留名义容量，未保证相同历时/权重质量，不能假称“有效容量逐点严格相同”。一个训练peer只是单peer迁移；一个随机分组只是一个负对照，**不产生对所有任意分组的显著性证明**。成功只能先记“此固定taxonomy胜过此固定负对照”，不能写“行业关系已因果确证”。
5. source日/标签/exit/成本/容量/score>0及普通/F优先级均沿精确accepted合同。相同月份排序不变是结构不变量；若实现改变，先判bug，不据收益接受。

## 最省的实际下一步与停止规则

下一步先由root冻结小taxonomy映射、上述精确base/标签bindings和三个臂、原诊断门；然后**仅一次残差截距/预测检验，不先生成新行情或cash**。六fold各T/P一次闭式估计，若实际执行应如实计12个offset fit；base模型0重训，不把闭式估计记成0fit。只读一次必要旧输入；不用新行情、SQL或下载工程。正式完整A/B Skill当前未触发，未来晋级仍另受正式合同约束。

首轮同时看A、T、P的完整前瞻选择结果、原held组配对增量及完整年份；主问题T-A和T-P，未支持family保持ITT母体、不填未知0。不能只看训练MSE或只挑正行业。若T不能在两个原held组维持事前要求的同向增量，或只胜A而不胜P，停止这套taxonomy/252/固定头设计，不改粒度、强度、seed、窗口、目标或共同头。若获支持，才签一次固定三臂现金与独立review预算；预测改善不等于账户高收益低DD，之后窄损和加注继续分别检验。

实际任何回测完成后必须独立agent全面审结果、数据、时刻/留族逻辑、置信度、bug；本轮没有跑回测，不虚构回测后review。

## 本轮记录、反思与合入边界

- 新增文件：本唯一中文stage；脚本新增/修改/删除0，策略/模型/训练/执行参数实际变更0；上面的252仅设计建议，尚未激活或拟合。
- 新回测/修改/删除回测0；fit/cash/SQL/行情下载0，未打开行情/标签/模型/收益大表。外部论文/源码网页阅读不算行情下载，未clone、安装或运行第三方代码。
- 本线累计保持 **511 fit / 278 完成 cash + 1旧partial**。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：全部 **N/A，无新回测**。
- 开始反思：**已有过拟合风险是且高**，原因是同史上已反复自适应择题；本轮没有因新收益调参。结束：该风险仍是；本轮新增按结果救参否。固定一个外部经济标签、一个强度和一个负对照只能限制新增自由度，不能清除511次fit历史选择风险。
- 开始继续价值：**是，仅值得这次有界机制审查**。结束：**是，仅一次上述低成本证伪**；经济分类具有COMMON缺失的可转移身份含义，且能与等容量任意标签区分。继续无边界行业模型/seed/shrink扫描：否。若不肯接受固定设计失败后停止，则不值得实施。
- Polanyi式经验判断：老练交易者会先问标的物由谁生产、谁需要保值，而不是先看哪个行业过去赚得最多；本轮把这种直觉压成不含收益的静态映射与能失败的跨family检验，不把直觉当证据。
- 不改LINE/registry、根memory/back_log、正式物料、生产、CTP、邮件、任务或Git。由root合入时裁决；常规设计审查不追加根总账。完整高收益/低DD/窄损加注目标未完成。
