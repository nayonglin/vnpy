# Stage533：共享52头的类别输入排重与部分共享边界

记录时间：2026-10-21 04:06 CST；line_id=`futures_full_market_long_signal_ai`。非重要突破；仅有界只读盘点及本唯一阶段文档。独立于正式C9，不修改代码、LINE、registry、其他研究线、正式配置或Git。累计仍为511次fit、278本完整cash与1本旧partial，本轮新增fit/cash/SQL/下载/旧score重算/COMMON或native或label大表读取均0。

**结论：有条件GO仅一个低容量、固定产业类别的截距残差对照设计；当前不授权actual。不支持“完全pooling已经被证明错误”，也不支持八套分组头。** 理由不是“未测所以继续”，而是原显式52没有经济类别输入，而收益外既有八类映射确实早于本线存在。它提供一项未被本线显式输入的静态经济元数据；不是新市场观测，亦未证明在52条件下具有统计增量。若root不接受这项弱先验，直接NO_GO合理；不得以HGB失败为由增加容量、换分组或救旧q。

## 开始时反思

开始按本次收益调参过拟合：否，本轮不读新候选收益且不训练。长期同史择题的过拟合风险：是；已有511fit的研究选择不能靠低容量或一次冻结消除。继续本次盘点价值：是，它能核清DOMAIN/会员身份与产业类别是否重复，并为“只换模型容量”划界；继续旧532相对q或518续持包：否。

## 实际外部调研与判断

本轮实际读取[Gelman、Hill、Yajima原论文作者提交页与摘要](https://arxiv.org/abs/0907.2478)。作者说明多层模型把组参数向共同中心收缩，和完全共享或不收缩的逐组估计不同。这仅支持统计结构上的部分共享概念，不支持中国期货的八类划分、long方向或收益改善。作者站两个PDF入口连接失败，不冒充已读正文；没有下载论文文件、软件或数据，也不堆重复搜索。这里的固定惩罚残差头是受限的频率学派收缩对照，不应写成已经完成完整Bayesian层级推断或由论文保证alpha。

## 现有模型排重：身份用于管理，不等于进入X

| 谱系与精确证据 | 已经测试的内容 | 对本问题的边界 |
|---|---|---|
| `tools/stage130_contract_choice_fit.py:18-21,60-73,144-169`；26名原字段在`tools/stage071_settlement_narrow_fit.py:40-45` | 原26值经各fold训练加权全体标准化，追加26missing；52个共享斜率与一个共享截距。family用于并发权重、整族held和普通/F去重，product用于身份/选择，不进入design | 显式输入没有product/family/sector one-hot或类别截距。不能从列名证明52完全不携带间接身份代理，更不能证明加sector一定增加条件信息 |
| Stage217协议第15-20行；`stage218_training_domain_loss_fit.py` | 仅D<K可行动训练支持及总loss质量调整；原Y、原52、scaler与Ridge不改 | DOMAIN不是sector domain，不含分组斜率、截距或每family头；并非“按sector部分共享已失败” |
| Stage495协议第11-14行；`tools/stage496_member_identity_residual.py:44-85,95-138` | token为`N|exchange|member_name`或无名时`I|exchange|member_id`，归一签名持仓向量；B=[1,r]与受约束具名会员残差头 | 会员身份不是产品/family身份；product/family只确定观测绑定与held。会员可跨family共享不等于sector输入；该旧失败不重开 |
| Stage430盘点与`tools/stage433_fixed_hgb_fit_select.py:29-33,59-72,195-214` | 一次固定浅HGB只用原52坐标；categorical_features=None，实际x=原design52 | HGB无显式product/sector输入；其表达能力可能利用52的间接代理，但它未直接测试产业截距。失败不得靠加深树或换树参救 |
| 032/033同行、其他信息offset与本线fit源码/阶段有界搜索 | 同行图不使用sector门；未发现本线实际sector/family ID头、group-specific heads或partial-pooling actual | 这是有界源码/阶段排重，不声称穷尽仓库外未归档实验。新后继仍不得恢复DOMAIN、K_TARGET、旧q、会员或HGB失败包 |

26原字段涵盖收益/形态/量比/ATR、期限统计/basis/missing、成本及20low距离；没有经济产业标签。无量纲化只统一数值单位，逻辑上不推出不同产业条件收益函数或基准截距相同。不过这一逻辑差异本身仍非经济优势证据。

## 两种“既有sector”必须区分

1. **本线现金报告的market_sector只有两类。** `tools/stage148_fx_cash.py:349-359`与`tools/stage157_voluntary_cash.py:241-250`的定义是`CFFEX.`前缀=financial，其余=commodity；另有独立维度ordinary/F。它是事后归因程序中的静态身份函数，不按PnL设组；但报告函数不是事前学习输入声明。对本线004小manifest的98目录产品而言，financial=8、commodity=90；按去_F的95family为8/87。规则无漏分，但“其余均商品”的覆盖不等于完整产业taxonomy，更不证明其历史first-seen/PIT。
2. **真正八类产业表来自上游Stage269，不来自本线现金表。** 维护源码`research/lines/futures_trend_rollover_shape_same_volume/tools/stage269_market_efficiency.py:25-35`写死黑色、有色/新能源、贵金属、能源化工、农林、股指、利率、其他商品/运价。其Stage268预声明文档第40-42行明确逐产品归属在联PnL前固定；269源码第350-355行先写映射再读行情。JSON自述`recorded_at=2026-10-17T21:53:12.792265+08:00`、`declared_before_feature_computation=true`、`strategy_pnl_accessed=false`。它早于本线2026-10-18起始，但不能宣称研究者从未看过其他历史收益。

实际只读的登记文件：`research/ai_assets/futures_trend_rollover_shape_same_volume/stage269/20261017_market_efficiency_attribution/payload/market/product_sectors.json`，3530B，SHA256=`04bd27f400bfcf3a0abea283b62bf2ae20e41bd1975c2173b7229870f5fec7e2`。原产物`research/lines/futures_trend_rollover_shape_same_volume/outputs/stage269_market_efficiency_validation/market/product_sectors.json`同尺寸同SHA；AST展开当前源码的94项映射与二者逐值相等。没有读上游现金账本/收益结果取分组。该映射是仓库自定义产业taxonomy，并非交易所统一官方分类，SS归黑、胶/玻璃/纯碱归化工等约定必须原样保留，不能按本线收益重分。

**小metadata覆盖核对**只用本线`outputs/stage004_product_day_opportunities/export/manifest.json`的`product_year_counts`目录身份，以及上述3530B映射；未流399252母表或任何label大表。目录98产品/95family：

| 固定产业类 | family数 |
|---|---:|
| 黑色 | 11 |
| 有色/新能源 | 12 |
| 贵金属 | 4 |
| 能源化工 | 25 |
| 农林 | 33 |
| 股指 | 4 |
| 利率 | 4 |
| 其他商品/运价 | 1 |
| 未映射DCE.S | 1 |

原94普通代码无多余项；exact产品缺`DCE.L_F、DCE.PP_F、DCE.V_F、DCE.S`。原Stage269为市场聚合排除了三F；本线绝不能继承其删F规则。仅依本线早已固定的family=`product.removesuffix('_F')`给三F继承普通类后，映射97/98产品、94/95family。`DCE.S`不凭代码猜为大豆，不删除、不放入第九个可训练“未知类”；后继若批准应明确缺映射修正为0、回原共享52，仍保留98/95全域与全部身份。未知fallback不是完整taxonomy已认证。

## 只允许一个容量上界：固定52加类别截距残差

建议供root裁决的唯一版本是：冻结130六个原52模型、scaler、成熟训练行、原Y与原权重算法/值；只按这份已固定八类映射拟合一个强收缩截距修正`score_new = score52 + delta_sector`。只估计产业相对基准的常数偏移，不能重训52系数、逐产品单独估计、加入sector×X斜率、时间/年份截距、新目标或多组alpha。缺映射或该fold未见训练sector的机会严格修正0，不删除训练/预测身份，不用新missing截距救它。

一个可明确约束的低容量表达：原训练权重归一为sum(w)=1；映射且在训练有支持的八类one-hot，按映射样本训练加权频率p中心化`Z_i=e_sector−p`，未知行Z=0；对原残差`Y−s52`仅拟合无新全局截距的Ridge lambda=1。不得逐列zscore放大稀疏类别。G=Z'WZ半正定，trace(G)<=1，因此有效df=sum(g/(g+1))<=trace(G)<=1；每fold实际应保存中心化/有效df证据。这个界只限制新增容量，不给收益保证；训练支持未知不能现在伪称通过。也可以root直接拒绝，但不能再在两类/八类、不同中心化、lambda或是否重训52之间挑收益最好者。

**可识别动作范围很窄：**同产品同u的所有真实月份属于同sector，修正完全相同，因此数值加性且无阈值边界时原月份之间排序不变；ordinary/F同family亦共享修正。唯一直接经济动作是原score>0参与门的类别校准，继而影响持仓数量和账户路径；它不是新的最优月份信息或绝对long行情信号。若完整选择不变就0cash关闭，不能以分数更漂亮继续。原K、anchor、.25N/20low退出、100w、family风险.25%/总2%/buffered margin25%、费用滑点及所有unknown纪律都不改。

若root决定GO，最多两cutoff×main/held0/held1的6个微型头，至多4本候选现金；对照复用原52/K账不重放。先冻结唯一模型、映射SHA、DCE.S fallback与主经济门，再单次actual；每次真实回测后独立全面review。须保留两held、全98/95、所有年度/集中/未知，并沿主2020stress成本后收益严格更高且DD严格更浅及既有配对CI门，不把少交易/DD低或组内赢家解释当通过。此处仅范围建议，不是协议、实施或新增actual授权。

## NO_GO边界与后续

以下均直接NO_GO：八套52头、每family头、sector×52交互；把新sector称真正外生行情信息；按已有赢家选“能源/农林/股指”或删除S/运价等小类；按亏损结果重分SS/胶/玻璃；加深HGB；复活DOMAIN/Ktarget/会员/q；用held验证失败后换归一化或lambda。若root认为“固定静态类别基准”仍只是capacity救参而无独立经济价值，本轮应停在本文件，不强推实验。不能用未测这个事实无限生成算法族。

本轮新增文档1；新增/修改/删除策略参数0；新增/修改/删除金融结果0。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A。没有提交、推送、订单、CTP、生产或定时任务行为。

结束反思：本次按新收益救参过拟合**否**，但后继类别学习及同史择题风险**是**，预先经济分组与df<=1只能约束不能消除。继续当前结构问题价值**有条件是**，它补足了显式静态产业类别这一未测约束，且仅能证伪一项类别截距偏差；继续扩模型/分组/旧失败包**否**。完整高质量long、成本后更高收益且更低回撤、跨周期/全产品及极窄损加注目标仍未完成。root统一决定是否冻结该唯一版本，本agent不改LINE/registry。
