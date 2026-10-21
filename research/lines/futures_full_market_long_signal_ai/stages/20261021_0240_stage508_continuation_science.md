# Stage508：把持仓继续价值定义成原现金政策的一次改进

- 研究线：`futures_full_market_long_signal_ai`；时间：2026-10-21 02:40 CST；分支沿用 `codex/ai-training-data-expansion`。
- 先读 registry 与 LINE 最新507。六所98历史产品/95家族完整域保留，独立于正式C9；实际有子97/94不等于缩小研究域。本稿只读小代码、记录、manifest与公开原文，不读旧大source/native数组/价格/数值Y，不训练、不回放现金、不SQL或下载行情。
- 开始反思：长期使用同一历史择题的过拟合风险**是且高**；本轮按收益救参**否**。继续价值**有条件的是**：507只证明钟表候选不退化，下一必须证实另一个真实决策对象可顺序构造，不能把候选数当alpha。

## 独立裁决

**推荐只研究原A157政策的一个固定policy-improvement步骤：在本来仍持有、当时资料完整且无已知强退责任的收盘，选择继续原政策，或者提出下一源交易日开盘卖出。当前只做native状态构造，不做Y、模型或现金actual。**

必须更换507严格内层区间的用途：它仍是有效的必要支持计数，但不是训练风险集。必须从每个原行动的u资格、D实际入场顺序推进，不能先挑最后closed、filled或能活到x−2的交易，再回贴收盘状态。下一日就止损、随后缺价、最终尚未平仓的路径，也有当时真实可见的收盘状态；删去它们会让学习器看到一个事后幸存世界。

baseline明确为**A157沿用的131现金持仓退出规则，source lifecycle与common K取交集**，不是129保存的最终exit。129遇首个缺失/invalid held bar就把标签变unknown并停止；131遇缺价会mark stale、挂deferred，并在下一合法报价优先强退。两个对象不能混用。当前可以构造无账户数量的单位机会路径，保留stale/force/unknown；它仍不是实际现金账户风险集，因为没有家族占用、保证金预算、整数手数或账户减仓。

## 原文与GitHub调研及判断

重新读取[作者mlOSP论文](https://arxiv.org/html/2012.00729v2)的timing value、后向拟合与独立测试段落：数值方法比较继续与停止，并要求训练和政策估值分开。它的样本来自指定随机过程，不能据此保证中国期货历史学习无偏或盈利；风险中性期权定价也不能直接替代本线物理概率下的净交易现金。

实际核[作者GitHub](https://github.com/mludkov/mlOSP/)及R目录：实现包括Longstaff–Schwartz与Tsitsiklis–van Roy，提供回归、模拟器、payoff与实验设计接口。判断：可借鉴目标、政策与独立估值的分离；本轮不clone、不安装、不复制其多学习器赛马或模拟价格过程。

另读[Ma/Stachurski原文](https://qingyin-ma.github.io/papers/optiming_19.pdf)的继续价值定义：等待后再优化与现在停止不同。判断：理论澄清的是对象，不替我们识别未来物理价格分布、执行成本、历史可得性或账户最优行为。以下具体合同是本研究的设计判断，不是论文已验证的交易规则。

## 代码事实决定的构造合同

静读129 `simulate_action`、131 `run_cash_account/anchor_request`、132 `audit_label_path/persist_native_cache`、156 `calendar_boundary`、157 `apply_boundaries`，确认：

1. u仅使用当时合法资格；D=u+1才检查原合约开盘、stale boundary取消及入场执行未知。原初始风险点数`R0=.25*N_u`，原`SL0=entry_reference−R0`；不能用今日N重新设置旧仓SL0。
2. 当日按原优先级处理已知强退、deferred、账户减仓及保护性退出，之后仍活着的仓位才到收盘。原边界为`max(SL0, own_low20_t)`，自己的真实合约20low，不借当前主力、其他月份或未来最低点。
3. 原anchor始终是该u的canonical身份；当日canonical缺失/变化形成持续的下一开盘强退责任。不能把anchor更新成held epoch来延长仓位。effective lifecycle=min(source lifecycle,K)，不能把K裁到样本尾日。
4. 缺价不创造可成交close/open；单位路径依131规则保留stale/deferred，不能因129已unknown就把以后状态删除。stale、已知force或无法计算当时状态时不调用自愿退出头；原机械处置仍执行。不能把未入场、未知或缺价当收益0。
5. t收盘只能知道下一日期、既有交易规则及提交条件，不能提前知道D=t+1的actual open、整根bar是否accepted、盘中低点或下一次风险减仓。future valid只能是执行/标签的事后状态，不能作为t风险集筛选。

原132小manifest声明缓存9520 epochs、1552456 native行，字段为days/OHLCV/accepted/valid/N/low20/run，文件110273488B、SHA `d2976090f9353b071eb62e28eca843b96b4a33a33a4233a508049cfeab9360b7`。**本稿只读取该小manifest，没有恢复cache或重验其当前内容**；原purpose是local recovery，新研究必须由root明确另绑定用途。

root提出一次full mother+causal行动投影+native三源顺序读取，科学上足以支持本次构造性目标，前提是原source lifecycle/身份规则随现有材料可得。母表提供完整anchorgrid，causal投影提供全部行动身份与u可见资格/N/low20，native前推D和持有状态。若改用466 metadata，只取身份与u可见字段，不能按其future filled/closed/exit/known日期筛入或回填状态。**不用为寻找terminal outcome再读129大表。** 所有98/95无子/无数据状态仍保留，不把实际有子97/94误断言成域损失。

## 最小后续X/Y建议，当前不授权数值生成

先定义在t close、同一个旧仓状态、同一个成本场景下的两个动作。`continue`继续上述原policy直至其退出；`exit`提出D=t+1开盘卖出，遇原不可报价/deferred/保护性优先规则仍按现金核处理。已知force的收盘两者本无自由度，单列而不训练。下一日gap或原force导致两动作相同应得到0增量；下一日盘中才止损的状态也应保留，不能按x−2规则排除。

若下一开盘合法可执行、两种退出均已观察且报价可表示，设`V_sell(ref,c)=multiplier*adverse_sell_fill(ref,c)−sell_fee(ref,c)`，建议目标：

`Y(t) = [V_sell(reference_exit_original_policy,c) − V_sell(open_D,c)] / (R0*multiplier)`。

Y>0表示继续原policy相对卖出更好；模型预测Y<0才提出退出。共同BUY fill和入场费已经沉没，成对相减取消；卖出滑点已在fill里，不再扣一遍。分母使用旧入场时固定正风险单位，不以未来波动/利润标准化。若D不可报价，两动作的路径响应必须按同一现金规则另记；尚未辨清或后续任一退出未知，Y仍unknown，不能照抄以上简式补值。该目标是每单位价格路径差，**不包含释放保证金后的再投资价值，也不是账户最优价值**。

一个最小、可提前冻结的候选X只有六个当时可知状态：`(C_t−SL0)/R0`、`(C_t−boundary_next)/R0`、`(C_t−C_{t−1})/R0`、`N_t/R0`、已持有源日数、到已知effective lifecycle的剩余源日数。采用其中哪些、变换及单一低容量线性头须在任何数值Y/收益揭示前另冻；本稿不是新超参授权。原入场score、今天重新开仓的N/SL、entry后的未来最高/最低、exit_reason/exit_date、最终持有期、终值收益和未来bar有效性均不作X。已持有年龄是过去信息，最终survived-duration是未来信息，二者不可混称。

## 成熟cohort、重叠权重及OOS

**建议先按事前责任期而非事后closed定义训练cohort**：在2020/2023各原cutoff，取u<cutoff、原D<K且K_date<cutoff的所有行动，或者其更早、同样事前可知的effective lifecycle已过的等价cohort。入选与未来盈亏/终止方式无关。为了合同简单，root可只用严格K已过，不因某些K未到但提前止损已知而混入短命样本。K未到cohort的过去alive状态照样保留计数，不在该cutoff拟合。此设计避免行政尾部只成熟短交易的选择，但不是全市场无偏定理。

K已过也不等于Y可知：报价缺失、延迟强退、economics未决仍unknown。必须报告完整cohort→u不合格/取消/入场未知→存活状态→原force/stale→可决策→已知配对Y/未知Y的守恒。已知训练标签必须两个动作都在cutoff前真实完成且可报价，原持仓以cash policy为准；不得仅以129 label_known早于cutoff签成熟。只在已知Y拟合会受潜在信息性缺失影响，不能宣称MAR或独立删失；没有依据时不做IPCW。硬止损不限制gap损失，不能随意给unknown有限负下界。

状态行大量共享同日价格、重叠u和月份。建议后续固定权重以决策源日等质量、该日family等质量、同family-day并行候选路径分质量，使一日或一个市场冲击不因月份/路径多而扩票；完全重复的可观察仓位状态先去重但保留映射。不要把原130入场family-u权重原样当成持有state权重，也不要把行数当独立N。权重和scaler只由本cutoff训练补集构造，训练值缺失规则在Y揭示前冻结。

沿原两个cutoff×main/两个family-hash训练补集；held family从训练、scaler、权重及调参均排除。训练截至cutoff，OOS按真实source日向前；不能随机拆prefix或把同路径相邻日分入两边。已反复披露的2020—26和held是诊断样本，不能重称全新盲检；真正未来前瞻仍需保留。不同cutoff与四现金场景也互相重叠，不能当独立实验次数。

## 为什么先做一次基准改进，不直接做完整最优停止

一次改进的Y来自固定原policy，不使用本次拟合头来生成自己的未来标签；这样可明确检验新信息在已持仓条件下是否帮助。每天重复应用同一个预测头是新的政策，必须实际前向执行来评价，不能把各日负Y单独加总或事后选最赚钱退出日。若假设转移完整、价值精确与标准MDP条件成立，policy improvement有理论依据；本线的估计误差、状态不完备、缺价和账户耦合使这些条件未被证实。

后向最优停止需要从末端递推、用后期拟合policy生成早期目标，并处理跨年龄/距K层、交叉拟合与多重估值偏差。它能优化另一个更广对象，却同时增加模型数量、标签内生性和容量。当前没有一个固定继续头胜过原policy的证据，直接上多层RMC/神经网/强化学习不合算，也不能借已知未来路径挑best exit当监督最优标签。

若以后构造性通过并单独冻结金融实验，原六入场52模型、K、0.25N止损、100w、风险/保证金/整数/成本/容量均固定；最多一个头/每原fold，不加仓、不延迟原保护性退出、不重训原入场分数。候选现金必须自己推进持仓、同族占用、预算、entry、deferred、account risk reduction、fees、next-open voluntary exit和后续再投资，原强退及风控优先。比较A157 OWN四账原结果与候选四本完整财富，而非原A的position_days剪切PnL。需独立agent审查所有新结果，收益/DD、held、跨期、成本与未知一起裁决；DD浅但收益下降不足以通过，路径模型胜出也不授权放大投注。

## 本轮结果、下一步与结束反思

- 新增/修改/删除策略参数：0；新增数值X/Y、fit、预测、现金、SQL、native/cache/旧大表读取、行情下载：0。没有读取全市场任何新价格或收益；本轮只有科学定义和静态源合同。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率：**N/A**。累计仍505实际估计/274完成现金+1旧partial。本轮不是重要突破，不改LINE/registry或根历史总账，不改正式/生产/CTP/邮件/调度/Git状态。
- 唯一下一步：root另冻并授权一次native单位机会路径构造；输出全状态守恒、K已过/未过cohort、force/deferred/缺价、当时可算特征和下一日期提交条件，保留未知。**不在该阶段生成上述Y、拟合、现金或最佳退出日。** 为避免下一阶段重复读native，支持同一次恢复把原baseline退出和每个t计划卖出的原始reference、SELL fill/fee/multiplier、日期/phase、两个成本场景保存到物理分离的label-only分区；这些是以后目标的原料，不能回流X或风险集。D缺价时两分支按同一现金核转deferred，到同一first-valid-open强退应一致。若首个原核可用bar的quote/economics仍不可表示，只记unknown，不得跳到以后更有利日期；原“可执行”仅是bar-model，不认证涨跌停、全量容量或首发PIT。若真实可决策状态或所需原身份/规则不可构造，就停这一具体实现，不换同日close成交或放宽stop/K救样本。
- 结束反思：本轮按成绩救参过拟合**否**，长期同史择题风险**是且高**。继续一次native构造性测量**有条件价值是**；现在训练完整最优停止或加大投注**否**。完整全市场高质量做多/更高收益更低回撤/极窄损加注目标仍active、未完成；历史研究不等待今日日线。
