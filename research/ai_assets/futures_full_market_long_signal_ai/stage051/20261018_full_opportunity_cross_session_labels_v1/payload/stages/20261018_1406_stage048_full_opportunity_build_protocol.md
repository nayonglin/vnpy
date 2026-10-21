# Stage048：完整机会经济标签与期限关系的一次构建协议

- line_id：`futures_full_market_long_signal_ai`；2026-10-18 14:06 CST。
- 工作区 `/Users/mac/Desktop/fian`，分支 `codex/ai-training-data-expansion`。root冻结实施计划；不新分支、工作树、提交、推送或生产操作。
- 非重要突破、非正式A/B候选。用户全市场高质量做多、更高收益低回撤、随后窄止损与加注的完整目标保持未完成。

## 决策与调研判断

接受045的单一标签合同与046的单一期限对应关系，授权049实现并在必要合成检查通过后实际构建一次。047提出的两项设计缺口由本协议绑定；模型训练和现金回放尚不授权，之后须另冻学习器、成熟时钟、共同输入、三臂及实际账户比较。不能将047的两臂18fit建议机械用于046需要的COMMON/ALIGNED/SHUFFLED三臂，具体次数不在本轮扩大。

本轮实查[Bianchi等原作者论文摘要](https://arxiv.org/abs/2308.00383)及[MLFinLab标签接口源码](https://raw.githubusercontent.com/hudson-and-thames/mlfinlab/master/mlfinlab/labeling/labeling.py)、[并发源码](https://raw.githubusercontent.com/hudson-and-thames/mlfinlab/master/mlfinlab/sampling/concurrent.py)。前者研究曲线不同维度的变化及其风险补偿，不能作为国内期货小损做多有效的证据；后两者公开相关函数为pass，只借鉴自然终点/成熟与重叠定义，不安装后冒称实现。045/046所述原作者、GitHub及旧失败谱系核查保留。其他交割月价格是新增观察；收益与期限的线性对应只是待证伪推导，不是原论文复制或已有alpha。

上轮关于三重滤网的概念解释没有改变研究证据，本轮必须落成可独审数据。旧三重滤网研究不因用户询问定义而恢复；不把周/FI规则重新包装成新增信息。

## 固定标签合同

1. 唯一母体004的399252行、event_id及原顺序不变，98产品/六所/4074报告source日。212852 observed、186400无观察分别保留，不按未来成交、55突破、C9/月池、family占用或资金筛选。
2. 当时同真实epoch至少20连续合法正量bar才history_ready。沿042的连续段首TR=H-L、首20TR均值种子、后续 `(19*N_previous+TR)/20`；low20含u；缺失/非法bar重置连续段。20ready与经济、期限、特征资格分列，不继承009的21或042的56门。
3. 每ready且经济可解释、期限允许的u独立计划严格下source日D同epoch open做多；缺D价未知，末端未到D为右删失。D的F<=u.low20或F-2N<=0理性取消，保留known_nonparticipation；trade目标与label_known均null，只有已知不参与政策贡献诊断为0。u可知期限禁入也不作为已成交亏损样本。
4. SL0=理想F-2N(u)，当日边界max(SL0,此前完成的low20)。强制旧epoch开盘退出优先，否则O<=B按O、L<=B按B；收盘后更新下一日max(SL0,low20(v))。无PT、最长持仓日、强制单调止损、重试、加仓或自动续仓；代表改变/无观察在当晚发出下一source旧epoch open退出请求。
5. 生命周期沿041最早名义月首、已知maturity/delist映射完整source日历；不得以回看最后bar代替。缺持仓/退出bar为吸收unknown，后续有价不能恢复主标签。正常末开放不强平，target null。
6. 只有实际参与且完整按模型闭合有标签：每lot净CNY=真实epoch乘数×(不利卖fill-不利买fill)-两侧费用；固定现金风险分母=2N(u)×乘数。主y=stress净R，base辅助；不采用047建议的含成本分母，以045为唯一口径。不截尾、分类阈值或按赢家放大R。round_lot作为数量单位/归一说明，不将独立事件求和成账户。
7. base/stress使用042固定tick/bps滑点及每lot费用，绑定同一价格路径，不用margin选择标签。滑点已经包含在fill不重复扣。静态vendor规格、理想日线成交、收盘后可得均为研究重建假设，不是broker逐日或真正历史发布时间资格。
8. label_known=完整退出日全源收盘之后，未来fit仅在严格之后可用。输出entry/exit/known区间；本轮不算全样本训练权重。unknown、right-censor、未ready和非参与不能填0/负类；未来训练集合内再算family并发唯一性，普通/F经济身份分开、依赖同族。

## 固定新增输入与负对照

- 完整product内（普通与_F分开）排除query，u及严格前一source日均有合法正量同epoch bar，名义交割月首晚于u。同行成员不按未来存活、持仓、成交排名或静态maturity筛；至少3个不同月份的非query peers。
- r=log(C_u/C_prev)，tau=(名义月首-u日历日期)/365，beta为r对tau带截距OLS斜率。**本协议明确046的ATR20归一取042的N(u)/C(u)**，采用上述20TR种子/递推；不用009另一滚动ATR或未来波动。q=beta/(N/C)。q正只表示远端相对强，不先规定其做多含义。
- ALIGNED用真实对应；SHUFFLED按SHA256键 `stage046_maturity_relation_v1|product_id|u|epoch` 排序收益来源，分配至固定tenor顺序；同peer身份、期限集合、收益集合、缺失和容量，允许偶然原排列。COMMON未来q槽为常数0。未来三臂共同保留n、期限跨度、r均值/总体标准差/min/max、normalizer和缺失；同训练缩放合同由下一机器协议绑定，不能先看成绩。
- 另保存旧front/next控制：取同完整product同两日合法且未来名义月份池（包含query）的最早两个不同月份，保存u与prev的log(C_next/C_front)、期限跨度和缺失。它们属于未来三臂共同条件，不另加旧carry候选。不能仅凭同值bag排除一切旧基础差异。
- 所有399252行保留，q_missing不能删除机会；不得使用D参与状态、标签成熟/结果或未来价生成输入。保存可复验的peer epoch、名义月份、tau、log_return及排列对应，不复制原始OHLC。有限原生审计切片另标raw、不进Git。

## 实施、实际运行和独审

1. dataset agent只写049主builder和少量合成测试，experiment agent只写049期限模块及少量合成测试；root冻结输入协议和审源码。两人不改已接受042及其他研究线，所有Python `.py311/bin/python`。
2. 复用039小绑定、004母表、041投影、已接受native与完整日历；一次读取原生SQL同时服务labels/features。每epoch缓存生命周期、每product/day缓存同行，避免逐event查SQL或重新hash大库。不运行旧DAY、042账户、其他模型、新下载或全面重新验收。
3. 必要测试覆盖20vs56/缺口重置、D严格后继、stale取消、同日止损、旧low次日才生效、换月/期限、缺价吸收、正常开放、经济单位与费用，以及query/F隔离、同bag固定shuffle、未来污染不改过去输入。失败前置与修复如实记录，不把fixture当真实训练。
4. root实读源与测试终态后，向新输出目录启动一次构建；禁止覆盖/自动重跑。保存actual_started/terminal、源绑定、全母表标签与特征、normalized peer mapping、dependency intervals、按年/product/family覆盖与状态、价格路径退出原因、成本分解及manifest。摘要不得报告独立事件累加权益/收益/回撤/Sharpe。
5. 完成实际运行后独立050 agent复核完整表的身份、状态/null/成熟、所有闭合经济公式、期限对应与同值排列，并用首次构建保存的有限native案例自行复算路径与因果性，不再读整个SQL、不import作者核心计算冒充独立。root接受前不训练。
6. 数据和复核通过后，按freeze skill显式角色登记决策所需源码/合同/规范化数据/证据；排除原生库/OHLC/私密/可再生缓存，精确本地暂存，保留既有index，不commit/push。root再更新本线LINE和registry唯一行，普通记录不写根总账。

## 当前成绩与反思

本048无新fit、现金账户或实证成绩；期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率均N/A。上一已接受042现金弱/负结论不变，累计288模型fit/18研究现金账本。

新增参数只是在收益前一次固定20最小历史、2N/20low标签、>=3peer及固定映射，与045/046相同；不是按新结果选优。开始过拟合判断：本次不按结果调参，但历史择题和条件filled样本风险存在。继续价值：是，完整经济结果与新观察是下一次实际AI比较所必需；单独生成标签不能声称AI优势，更不能证明极小止损或加注可行。结束须以实际049/050证据更新，不预先宣称通过。若新增信息无增量，停止本q包，不换窗/seed/模型救参；完整目标仍active。
