# Stage045：全机会跨日经济标签合同建议

- line_id：`futures_full_market_long_signal_ai`；记录时间2026-10-18 13:58 CST；沿`codex/ai-training-data-expansion`，不新建分支/工作树。
- 性质：只读设计，0实现、0SQL、0fit、0金融、0行情下载。只新增本stage与小read_receipt，不修改LINE/registry/039/041/042/044。不是策略候选、正式A/B或已实现标签。
- 已读registry本线、LINE、044决策、039固定合同/机器协议、042相关因果原语及041来源合同。044的55/20/2N账户弱/负结论保持：不救55包，不扫描2N、20low、horizon、PT、本金或成本，不重训024/035。

## 选择与真正要回答的问题

**推荐下一步只构建一个固定的、覆盖完整399252行的跨日经济标签母表；可以冻结实施，但本合同本身不授权训练或现金回放。** 问题是：“在u收盘当时可观察的每个产品机会，若下source open独立做多同一个真实epoch，按固定因果退出/成本规则，最终得到什么净经济结果及何时可知？”这不是“若已满足55突破，是否值得再过滤”，不是优化退出，也不是给042已有root换名字。

固定方案：删除55突破/56bar触发资格、账户占用、family择一、C9/月池及资金可用性筛选；**只需20连续合法同epoch bar**形成N20与low20。每个history-ready行各自计划独立counterfactual订单，不因其他event已持有同epoch/family而取消；D仅按预声明的本订单quote/生命周期规则确认参与或取消，所有u行仍保留。保持2N初始保护下界、因果20low退出、旧epoch换月/期限退场、无PT/最长持有日。base/stress两套固定费用对**同一条价格事件路径**计费，不因margin重算标签选择。

选择保留2N的理由是把“全机会空间”与“原55选时”分开，同时沿用已复核的退出和现金单位；**2N不是本次从负结果中找出的好止损，也不代表已贴合极小止损目标**。全母体修正可能产生更多负结果，照样保留。若只允许借新标签重训失败的同OHLC包，这项工作不应被当作新alpha研究；下一次训练须另有真正新增事前信息和收益前实验合同。

主标签采用连续值`net_R_stress`，base为同时交付的经济参照；不先造任意“4R/8R/前10%/年内赢家”高质量正类，不对右尾截顶或按全样本分位重标。`net_R>0`仅可作净盈利描述，不能命名为“超高质量”。这个优先级在未生成全机会标签前确定，不依据哪条成本曲线更好而挑选。

## 原作者资料/GitHub实查与取舍

本次实际浏览了[Original Turtle发布页](https://www.tradingblox.com/originalturtles/originalturtlerules.htm)：其规则还包含入场、加仓、头寸和相关性管理，不能把本合同等同原Turtle。参考[Rob Carver原作者breakout源码](https://raw.githubusercontent.com/pst-group/pysystemtrade/master/systems/provided/rules/breakout.py)，其输出是滚动通道位置再平滑的forecast，不是本合同的经济标签；因此不复制其半窗口暖机、平滑或额外触发门。

实读[Hudson & Thames labeling接口](https://raw.githubusercontent.com/hudson-and-thames/mlfinlab/master/mlfinlab/labeling/labeling.py)：它区分事件起止、水平止盈/止损和可关闭的vertical barrier。这里借鉴明确事件结束和标签成熟的思想，**不引入CUSUM、固定最长持仓日、PT或meta-label预筛**。实读[sampling/concurrent.py](https://raw.githubusercontent.com/hudson-and-thames/mlfinlab/master/mlfinlab/sampling/concurrent.py)、[cross_validation.py](https://raw.githubusercontent.com/hudson-and-thames/mlfinlab/master/mlfinlab/cross_validation/cross_validation.py)和[该团队原文对concurrency/uniqueness的解释](https://hudsonthames.org/bagging-in-financial-machine-learning-sequential-bootstrapping-python/)：重叠收益标签重复使用未来路径，随机逐行切分/普通IID置信区间会夸大证据。公开master相关函数主体当前为`pass`；本次只引用其接口/文档定义，不声称读取到可直接运行的完整实现。作者书籍SSRN页面403、原Turtle PDF跳转失败，不假装已阅读全文。

判断：保留自然事件终点、严格成熟和重叠控制；不把更复杂采样/分类器当新信息，不以库名证明本研究有效。下面是结合本仓库单位/真实epoch条件提出的**自身固定研究合同**，不是复制外部收益结论。

## 1. 母体、当时资格与冷启动

唯一身份来自004已接受母表：399252个`event_id`，98目录产品×4074个2010—2026-10-16报告source日，原顺序一行不删。212852 observed与186400 no observation沿既有分类保留，未上市、缺失、结束、旧flag与_F不被默默删除。未来事件数量不是这里重新盘点出来的；新的ready/闭合/未知数量必须由下一次构建实际报告，不能沿用009的194709或042的174435。

u为完整已完成source日收盘，epoch仍采用004当时max volume→closeOI→epoch代表，不取D未来主力或全生命周期赢家。D为绑定完整source日历中u的严格下一个日期，**不是下一个恰好有该合约bar的日期**。u在报告末尾无已观察D时，保留`intent_right_censored`，不读取2026-10-16之后未来数据。

独立列`label_history_ready20`只依赖u及以前：u代表存在；同epoch最近连续source索引有至少20根accepted、合法OHLC、正成交量bar；N(u)有限且>0，low20(u)>0。TR、缺口重置、N种子完全沿039/042：连续段首TR=H−L，之后max(H−L,|H−prevC|,|L−prevC|)，首20TR均值，随后(19Nprev+TR)/20；low20含u的最近20根low。**因此最低20根足够，不需要21或56根。** 对连续段首TR使用H−L的约定必须写入manifest，不能称为另一个Wilder实现。

沿已绑定的完整5587日历及accepted source历史暖机，不在2010/2020或每年1月重置N。新上市或缺口后重新累计20根；不拼连续/复权/其他epoch补历史。原009 `feature_ready`不得重写；未来特征若需要更长历史，单独缺失编码或声明其支持域，不能因此缩掉本标签母体。

经济资格与history-ready分列：041有9502精确epoch经济快照、18固定unresolved，本轮不得启用fallback_candidate。没有精确经济身份的行仍保留价格/观察状态，但不编CNY/netR经济标签。044已证212852 observed参考均有精确快照；本次不据此声称新ready数量或未来无缺项。u已知D达到生命周期边界时为`known_entry_ineligible_lifecycle`，不模拟禁止的新仓；这属于事前固定合同约束，不是按未来盈利筛选。

## 2. 一个机会一条独立价格路径

每个`label_history_ready20=1`、经济身份可解释且u时已知未触及期限禁入的行，独立计划在D同epoch合法open F买入**一个经济单位**；满足下述固定参与条件后建立自己的root，按041 `round_lot`计量、结果再归一到每lot，不受已有event、family占用、共同现金、margin cap或20日内其他信号限制。_F与普通表达分别有自己的counterfactual，不套普通表达的价格/乘数/到期日。

R0_points=2N(u)，SL0=F−R0_points，入场日已知有效边界B(D)=max(SL0,low20(u))。止损依据理想参考F，不因不利滑点改变SL0以维护账面1R。这里2N是保护下界；若low20更近，实际边界更紧，**不能把所有标签称为精确2N止损交易**。

**首次即stale：推荐沿042理性取消，但不删除u机会。** 在D合法quote确定F<=low20(u)时，边界已经失效，不强制买入再卖一次；记`participation_state=known_nonparticipation`、`cancel_reason=stale_boundary_at_open`、`filled=0`，已知无成交的研究政策贡献为0，**trade-quality主目标必须null**，不能当亏损、净盈利0或已成交训练样本。参与结果的已知时间另存D，不伪装成一笔成熟交易标签。全u-ready分母、取消数量及其u时信息支持域必须报告。

这有两个可辨别的取舍：强制同open买卖会给每个合法quote一个费用损失结果，但它定义了另一条不必要成交的干预政策，会偏离已复核的042执行；理性取消保留真实决策可行性，却使trade-quality标签成为“该固定quote规则参与后”的条件结果。**本合同只推荐后者，不同时实施两套标签。** 完整母体不等于每行都要付两边费用。未来若要直接学习政策价值，须另冻结取消0的估计对象，不能现在把0塞进trade-quality loss后冒称同一目标。

同样沿042保留`SL0<=0`的固定执行取消，标`known_nonparticipation/invalid_initial_stop`；不为移除55而顺便取消或放松这个执行规则，不临时floor/clip止损。R0非正/非有限、身份/单位矛盾属于数据异常null，不能与已知有合法quote却按政策不参与混同。history-ready仍只看u以前；D取消标记不是u时特征，也不允许把取消行从母表删除。

对后续持仓日v：先执行上一收盘已知的强制开盘退出；否则若O(v)<=B(v)，按O(v)参考退出（gap可亏过−1R）；否则L(v)<=B(v)时按B(v)参考退出；否则继续。仅在v收盘后生成下日B(v+1)=max(SL0,low20(v))，low20含v。边界可按20low下降，但不低于SL0，不另加“只收紧”、保本、利润锁定或high跟踪。入场同日边界可触发，含入场日的20low不能反向同日生效。

**同日规则没有隐藏双障碍顺序。** 唯一价格触发是事先B，无PT；开盘入场之后，若同bar low触B即退出，不能先利用该bar high给额外收益或加注。force-open优先于当日B，原因可并列审计但只成交一次。未来MAE/MFE若记录，退出bar高低的发生先后不能凭日线断言；本轮不以其造“先小逆向再大上涨”的精确正类，也不为此扩分钟工程。

## 3. 旧epoch、换月、期限和未知

每个event路径只跟自己u确定的旧epoch。v收盘该产品004代表改变/无accepted代表，则请求下一source旧epoch open退出，理由`liquidity_reference_changed`/`observation_exit_requested`。不自动续仓、不跨epoch拼接收益；同一产品未来u仍可独立启动新的event，其是否重叠不影响旧event标签。代表改变是当时v收盘可观察退出条件，不能提前到v open使用。

期限沿041/039：边界是nominal month first、known maturity/delist日期的最早者，经已绑定source日历searchsorted映射；v收盘知下日到边界，下一旧epoch open退出；D已达到边界则事前禁入。L2703F等已知maturity早于标称月，不能只读YYYYMM，也不能复制18尾缺项的邻约日期或回看最后一bar。静态vendor日期/规格始终带研究重建假设，不包装成当时PIT或全部账户法定期限证明。

| 情形 | 状态与主标签 |
| --- | --- |
| u无观察/历史不足20/N不可用 | 原母表保留，`not_history_ready`及精确原因，经济目标null，不是负类 |
| u已知生命周期禁入 | `known_nonparticipation`及`known_entry_ineligible_lifecycle`理由，模型贡献0但trade目标null；单独记录可行性，不混入盈利分类 |
| D合法quote但F<=u.low20或SL0<=0 | `known_nonparticipation`、filled=0、精确取消理由；模型贡献0、trade目标null，禁止当负类/成交0类 |
| D未到报告截止内 | `intent_right_censored`，目标null，不能末close虚构入场 |
| D本应存在却无合法旧epoch open/bar | `entry_execution_unknown`，目标null，不能将假定取消0收益或后来open当D |
| 已入场后任一source持仓日/强制退出日缺合法旧epoch bar | `path_or_execution_unknown`，首unknown日期与原因保存，主目标永远null；后续延迟退出只能另作研究假设诊断，不能转回已知标签 |
| 价格路径完整，按固定机制闭合 | `closed_complete_bar_model`，才有base/stress净目标；这是日线理想成交研究模型，不是真实成交证明 |
| 截止仍正常持仓，完整路径未退出 | `open_right_censored`，末close未实现mark可诊断，主目标null；不以数据终点强平贴闭合标签 |
| source/单位矛盾 | `input_or_economics_unresolved`，目标null，给精确epoch/day/字段，不默默丢行/改规格 |

缺价unknown是吸收的**证据状态**，不复制042现金层stale mark/延迟成交后给它贴“已证盈利”。本合同也不因同family某event未知而阻止其他event开始：每条路径独立，但每条自己的缺失都必须保真。unknown、right-censor、不可行与已知亏损四者不能合并。完整路径模型也依赖理想日线成交及静态规格假设，`true_execution_qualified=false`始终不变。

## 4. 固定经济单位、目标与成熟时钟

041精确epoch M、tick、round_lot与source scope照搬；base/stress不改变参考入/出场日或边界。沿039费用：base每手每边max(2元,|fill|M×1bp)，不利滑点max(1tick,|reference|×1bp)；stress为6元/3bp/3tick。已知tick买向上、卖向下对齐；缺tick使用bps并标`untickized_research_fill`。滑点已进入fill，不再次扣减；vendor by_volume/by_money旧字段不另混成第三场景。margin仅可另存经济描述，**不是这个独立事件入场/标签筛选条件或收益分母**。

对一个已闭合事件与s场景：

```
net_pnl_s_per_lot = M * (sell_fill_s - buy_fill_s) - entry_fee_s - exit_fee_s
cash_risk_unit = 2 * N(u) * M
net_R_s = net_pnl_s_per_lot / cash_risk_unit
```

主目标`y=net_R_stress`，同时交付`net_R_base`、两场景每lot净CNY、费用/滑点分解、持续source日数、退出原因与经济来源tag。R分母固定u时N和真实乘数，不用最小事后逆向幅度或实际更近20low重新放大R；不裁截gap亏损或右尾。未闭合/未知任何状态均不代入0，也不以同年/同品种均值填。

已成交完整闭合才有`label_known_date=exit_source_date`、`label_known_phase=after_all_source_close`；只允许在其**严格之后**训练使用。即使退出发生open，也不假定盘中即可完成全市场标签/特征发布。未来fit cutoff为T时，仅`label_known_date<T`且完整闭合的event可进入训练；不能用整条最终标签表先决定T时哪些行“将来会成熟”。非参与行只存`participation_known_date`（u可知期限取消为u，quote取消为D），trade label/known date均null。年度边界不截持仓、不把12月末close贴标签；跨年event按真实成熟日进入后续训练，评价归属可按u决策年固定报告，右删失数量分列。

这个阶段不直接给“高质量/加注”标签。正净R只是该固定政策下的一次结果；期望、尾部、低回撤和组合生存是未来模型/账户问题。净R经2N归一仍可能奖励能忍受大幅逆向的趋势，不能据此宣传极窄止损的可行性。

## 5. 重叠、家族和去泄漏合同

每日独立counterfactual会大量共用未来价格，399252行绝不是399252独立交易经验。输出每event的`u_index, entry_index, exit_index, label_known_index, family_id`及状态；同日入退至少占一个source日，区间含首尾。_F保留独立经济身份，依赖分组却与普通表达共享`exchange+去末尾_F产品`family，不能一边做train、一边做held test。

将来只按时间向前的成熟训练/测试；禁止随机拆行、按event_id hash分train/test、同一完整路径两边出现、用未来全样本标准化/分位或先选2020赢家。严格成熟已经阻断训练标签跨入未来测试决策期；若另做双向CV，必须按真实起止信息区间purge，并对全市场共同日期切块，不将一产品测试期的同期其他产品标签放回训练来冒充未来时间泛化。family泛化与时间泛化必须分开声明，_F不可绕过held family。

**不把全样本计算的权重存成可直接训练字段。** 对每个未来训练集合S_T，仅使用T前已成熟且准入的训练事件，定义family日并发数c(g,t)=Σ_i∈S_T 1[g_i=g, entry_i<=t<=exit_i]；事件唯一性U_i为其持有日期上1/c(g_i,t)的均值，训练权重w_i=U_i/mean_S_T(U)。不按收益绝对值、是否赢家或测试event长度加权，不把未来/test/censored事件放进c影响旧训练权重。当前只冻结这个确定性计算合同并输出所需区间，0实际fit/权重选优。

uniqueness只是降低同family重复路径支配，不消除跨品种共同冲击，也不能将样本变成IID。以后置信区间须尊重共同时间与family聚类；本轮不再顺便冻结一组bootstrap窗口/模型比较。测试特征读取当时已公开的过去bar是合法的，不应把“共享过去观察”一律叫未来泄漏；关键是未来标签区间/fit cutoff和所有预处理不越界。

未知、未成熟和known_nonparticipation均不进入本trade-quality监督loss，必须保留完整支持域、取消和删失表；只在完整闭合参与子集上的预测效果是条件结论，不能外推所有当时机会。模型日后在u须给所有当时ready机会打分，不能以未来D是否参与或最终是否闭合作输入/事前测试筛选。实际被选政策的评价须保留已知取消0贡献、未知和开放敞口，不能只展示filled赢家；本合同不同时训练参与概率或policy-value模型。尤其长期右尾较晚成熟，不能用事后closed mask筛未来交易或以“已成熟数量更多”为由改终点。

## 6. 与极小止损/加注的衔接及否决范围

宽参考的价值是先有全机会、同单位、无固定获利顶的经济结果；缺点是“最终赚钱”和“能承受很小初损”并不等价。价格先逆向1N再上涨的event可能在本标签赢很多，在将来的极窄stop先已亏损；low20有时更近也不等于统一极窄止损。一手独立事件不含现金竞争，不能凭net_R大小决定倍投。

因此明确选择**先建立这一宽参考标签，但禁止把它直接作为窄损/加注成功的替代证明**。下一次AI信息试验若有独立稳健增量，也只能证明对这条参考干预的识别；模型、mask及输入先冻结后，才可以在另一个预声明单一窄止损政策中用完整路径重算所有候选及共同账户，不能在本标签赢家中倒找最小MAE挑stop，也不能不断换stop/horizon重训模型。加注要在窄损/退出/组合已固定后单独检验，不能同时放大标签或用−1R截断跳空。

若本标签构建后仅有大量重叠、成本损失或未知，结论应按真实支持域接受，不调2N/20low救分布。若未来新信息在此固定目标无增量，只否决该信息/学习器/政策组合，不证明所有AI或全部小止损无效；也不因此授权换标签继续复试024/035。若有增量，同样不能宣称用户完整收益/DD/窄损/加注目标完成。

## 下一次唯一可行动产物

root可冻结上述合同后，实施**一个独立label builder**：复用004身份和041经济投影、042已接受的N/low20/期限/成本及本单quote取消原语，但显式替换55/56门与family占用；取消保留母表、trade目标null的语义另做清楚。accepted native源只读一次，按epoch缓存N/low20，不为每个event重查SQL。不重跑042账户、旧009/024/035、模型或任何新现金矩阵，不新下载。

一次交付`event_economic_labels.csv.gz`（完整399252行，ID/原顺序不变）、`label_state_summary.json`（全母体、20ready、事前期限禁入、quote取消、已参与、闭合、gap、换月/到期、未知、right-censor按时间/family状态计数）、`dependency_intervals.csv.gz`和绑定manifest/真实terminal。主文件保存净CNY/netR与来源/状态，不将原始OHLC作为Git payload；有限原价审计切片沿042外部排除角色。不能先按未来closed/filled抽小赢家pilot，再把剩余行补成标签。

必要新行为只围绕：20与19bar暖机、未来prefix、D下一source而非下一有价、首次边界失效取消保留母体且trade目标null、入场/后续同日B时钟与gap、旧epoch强退与_F提前期限、缺价吸收unknown/末尾censor、base/stress共价格路径与不重复扣滑点、成熟及fold内uniqueness隔离。测试绿后一次构建，结束由独立agent核全ID、状态分解、经济恒等式、代表性first-hit与成熟/依赖区间。此处只给可直接冻结的单一标签合同，不偷跑实现。

## 工作量、指标与反思

本次0实现/SQL/fit/金融/价格扫描/行情下载/CTP/订单；只有小合同/源码和外部资料只读。无新增/修改/删除正式参数或历史成绩。拟标签参数只有继承N20/2N/20low及固定成本，不增加持有期或PT。是否重要突破：否；修正母体与经济语义不是新增预测信息。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、真实胜率全部N/A。

开始/结束新增按成绩调参过拟合：否；未生成/挑选全机会标签或训练，新母体由用户完整目标推导，原失败完整保留。经典退出及宽目标的研究选择/标签错配风险仍有，不能用无代码掩盖。开始/结束继续价值：是；这一次明确产物能结束“只在旧触发集打分”的目标偏差。继续55包/同OHLC旧模型救参：否。做完本合同并不等于找到高质量long，完整goal保持active。
