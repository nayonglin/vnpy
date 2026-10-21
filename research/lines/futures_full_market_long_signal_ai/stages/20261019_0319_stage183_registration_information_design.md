# Stage183：一项 coded-registration 变化信息的事前对照建议

2026-10-19 03:19 CST；line_id=`futures_full_market_long_signal_ai`。先读registry、175/178/176；未读179新raw、数量/覆盖结果、180/181输出或新收益。只交设计，不实现/授权金融；非重要突破。固定q包已关闭，不恢复HHI、lag、K、模型、stop或risk救参。沿brainstorming整理条件和可证伪终点，root可接受或否决。[小design.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage183_registration_information_design/design.json)给出同一建议的机器可读约束。

**仅建议一个“各原登记scope相邻比例变化的等权指数”，前提是root以后另签条件归档研究并接受测量/时钟假设；否则no-go。** 不改172显式物理单位契约，不把WGHTUNIT/WHTYPE未知码解释为吨/千克/桶或具体厂库类型，不跨JSON/HTML连接。

有限联网为一轮两query、两次primary open。[Gorton/Hayashi/Rouwenhorst，NBER13249](https://www.nber.org/papers/w13249)的出版者索引摘要研究实物库存、仓储理论与期货风险溢价，并指出价格变量已反映部分库存状态；这降低“加库存必有独立增量”的先验。[Acharya/Lochstoer/Ramadorai，NBER16875](https://www.nber.org/papers/w16875)的出版者摘要讨论套保需求/风险承受能力对库存与风险溢价的内生影响。两次原文打开均403、未重试，**仅采用primary索引摘要，不声称读完论文或验证其数据**。它们不是国内仓单日报流量、更不是本scalar的alpha证明。维护者详细源码链接继承175，不重复下载或执行其聚合接口。

## 唯一标量与必要语义

对一个原product内的原scope，取两个已知非负数量 `Qv,Qw`：若和>0，`s=(Qv−Qw)/(Qv+Qw)`；仅在两者明确0时定义s=0。缺失/错误/缺行不代0。s在[−1,1]，交换两日改变符号，未知共同正乘法消去；不加epsilon、不截尾、不设小库存阈值。它度量登记扩张/收缩，不预设涨跌方向。原官方delta保持单独字段，只作原文/算术诊断，不替代两数量计算。

scope至少含原product/type/unit token、源格式及语义版本；使用唯一原普通总计与完整覆盖指纹。税类父/叶、小计/总计不得重复入组；若不能得到唯一非重叠scope partition或总计定义，则该product未知。两报告scope集合和各scope覆盖须相同，所有scope均有效才把各s**等权均值**作为product标量。原qty从不跨单位/仓库/厂库/保税混加；该均值是各登记口径相对变动的指数，**不是总物理库存的变动率**。小scope与大scope等权是因无可信跨scope物理换算，不是按收益定权；其小基数噪声与不同scope经济重要性是明确代价。

任一应有scope缺失/不可比，整个product标量missing，不仅平均容易解析的组；不取共同仓库交集，不回找最近成功报告，不前填。scope集合只由当时这两份原报告定义，不用全史未来类型并集决定今天可得性。新type/单位/覆盖/格式切点使该相邻对missing，随后同口径对方可重新判断。判定只凭source状态/身份，不凭数量变动幅度或收益。

条件假设是同一对确实同对象、同覆盖、同正比例尺度，且代码释义/仓单规格/精度未发生未标记变化；**相同代码不证明这些条件**。同scope叶/总计/增减吻合能发现解析反例，不能认证物理语义恒定。未知WHTYPE仍只叫原代码组；若证明其混含不可分口径，涉及对不可用。不据此寻找全版本字典，也不为pipeline通过改173/174源状态。

选比例变化的第一性理由是：它直接询问“同一登记系统记录的相对扩张是否增添信号信息”，在共同未知单位下仍有定义；实物库存水平、跨品种总吨数、原qty权重没有同样资格。本轮只推荐这一项，不并行试库存水平、速度窗口、符号、分位、熵或不同聚合方案。注销换单、厂库担保、季节性到期、保税转换和登记激励都可能改变记录；仓单不等于社会库存/供需/聪明钱。

## 唯一可得时钟建议及完整母域

按root本轮澄清统一记号：**u=预定拟入场source交易日，D=prev(u)收盘决策日；v=prev(D)=u前第二个052日，w=prev(v)**。原166/168的`u_old=D`、`D_old=u`，原parent日期/索引/标签保持原身份，不为展示记号重命名数据。u不是事后延期成交日期，缺价/延迟成交不能事后移动特征时钟。只使用v/w，不假定reportD在Dclose可得；v后有一个完整D交易session缓冲，不新增lag扫描。

可得假设严格表述为：v的原报告在原D收盘决策时点已公开，当前归档未包含后来实质修订，**strictPIT=false**。不新设08:00等额外钟点，不引用177 WMS项目切片作为首发证据；root的记号澄清纠正了初稿把旧u当entry造成的额外一天歧义，并非看数据挑lag。若不能接受这个清楚但未证的假设，直接no-go，不靠继续加lag伪装PIT。格式/档案起点处拿不到v/w时missing，2014前训练行全留。

先固定精确原product到已有研究product的映射；歧义留missing，不用今日近似名字或厂库字符串随意合并。观测属于product，不属于某个期货epoch；同product/决策D的child共享该值，不能编造逐月库存。普通/F保持原身份；确为同底层时须事前明确共享映射/原family-u_old依赖，不新增独立样本。全部六所399252母/98代码/95family及每臂161014前向父行保留，其他所/无制度/无源/未知分别留状态，不硬门缩成有仓单的小宇宙。

## 未来对照与停止条件

尽量原样复用166/168：CONTROL54=COMMON52+同一missing+恒0；REGISTRATION54=相同COMMON52+同一missing+本标量。missing可能改变，**两臂都新fit**，不能复用旧q/130fit或旧现金作新control。两臂同6fold成熟身份、原unionweight、COMMON scaler；标量仅用各fold有限成熟训练值计算加权均值/方差，missing的标准化值为0。所有6fold正有限方差的预检先于任何fit；失败整包0fit0cash，不救字段/模型。上限提议12fit、8新现金，不是授权。

目标仍用129原own net_R_stress first-exit标签，held仍原target诊断；共同K仅沿166/168执行、.25N/noPT/预算/保证金/容量/费滑/132cache/070固定索引不变。它识别固定算法在共同K下的信息增量，不是K标签预测质量。线性标量在同product/决策D各child相同，直接作用主要是product时点准入；重估COMMON系数可能间接影响月份排序，不能称逐月库存机制。

未来门仍要求候选四R>0、八本wealth positive；主2020 stress收益更高/DD更浅/配对日log CI95下界>0，另三R/DD不差；CONTROL DD null/空参考unknown，不置0；两held已知等u增量>=0且差异unknown阻止泛化资格。所有execution/stale/容量未知保留，held不充作K现金新标签。阴性结果关闭此scalar/Ridge/K包，不按scope/品种/年/方向/lag/模型/stop/risk救参。source假设不诚实、映射/覆盖不可识别或fold支持失败即no-go，不无限补证。实际新金融之后须另派完整独审。

本轮0fit/cash/SQL/标签/历史raw下载，无新权益/收益/DD/Sharpe/滑点/交易数/胜率；累计409/218不变。开始/结束新增结果调参过拟合否，因为新归档结果未看、只给单项事前建议；同史择题/归档风险仍是。继续一次有边界的条件新信息判断有价值；立即金融、降低物理契约、复活q/K包或无限资格工程无价值。完整goal及加注/正式资格均未达成。
