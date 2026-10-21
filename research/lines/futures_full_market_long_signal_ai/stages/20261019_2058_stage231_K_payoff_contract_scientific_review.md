# Stage231：K 单动作收益测量合同的独立科学审查

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-19 20:58 CST。
- 性质：Stage230 冻结前的独立设计审查；非重要突破，不是标签构建或训练授权。
- 已先读 registry、本线 LINE、Stage229，并核读209/211/212/225的对象、时钟、复用边界；只读129单动作函数、042报价核、130/218训练域定义、156日历门、132独立路径及cache schema、227分类源码。没有打开原actions、原mothers、价格、NPZ、六traincache或现金账本。
- 本阶段新增历史标签/fit/cash/SQL/大输入hash/行情下载均0；累计仍为433fit/234cash。完整目标未达成，不能加注。

## 判断先行

**有条件支持一次有限 K 单动作收益测量；现在不支持把旧218直接认证为未来同C控制。** 可以证明：对原完整closed且事前D<K的动作，K开盘费用报价及有限净R通过时，新严格标签成熟日不晚于旧标签成熟日。但旧完整closed本身不能保证K报价可表示；必须实际执行机械报价门，再逐六fold验证，不能把条件定理写成无条件事实。

本次只识别原单动作first-exit目标与固定K目标的数值/状态差异。它不是新信息、预测能力、旧标签bug或既有失败根因的证明。COMMON52没有明确自身剩余duration输入；这不自动授权补duration，也不预先保证现有52项能学习K目标差异。

## 网上与GitHub原来源的核证及判断

1. 实际读取 [Elmachtoub/Grigas原论文§2式(1)](https://arxiv.org/html/1710.08005v5)：固定、已知可行集合的线性目标允许使用正确条件均值；整数约束并不使这一点失效。[作者GitHub README](https://github.com/paulgrigas/SmartPredictThenOptimize)说明代码复现论文实验，包含portfolio和shortest-path oracle。判断：先把payoff对象和已知性写准；两来源均不证明本线应更换学习器，本稿不推荐或实施SPO。
2. 实际读取 [CME官方Trader's Guide，印刷第20页](https://www.cmegroup.com/content/dam/cmegroup/education/files/a-traders-guide-to-futures.pdf)：stop触发与可得成交价不同，limit的价格约束也不保证成交。判断：日线开盘参考、费滑模型和真实成交应分别命名；CME教育材料不认证中国六所历史队列、停板或容量。严格K标签仍只是固定日线理想模型。
3. 实际读取 [Dwork等原作者《Guilt Free Data Reuse》§1](https://www.cs.toronto.edu/~toni/Papers/holdout-cacm.pdf)：前次结果会影响下一假说选择，重复使用历史不能靠一轮冻结恢复未见性。判断：本测量可减少对象混淆，但不是新盲OOS；不能凭433次fit的计数机械声称独立试验数，也不能把相关金融样本直接套入其holdout理论保证。

检索范围到此停止；没有扩搜新策略、安装、复制或运行外部仓库。两次网页find传输失败，随后直接打开原文必要段成功；不将未取得的内容冒称已核。

## 唯一测量对象与最小数值域

完整保留已接受227/228的1,552,456 action、399,252 mother、186,400 nochild及各状态身份，不重新定义母体。主域仍是原u资格=1且156原日历D<K，不加score、已选、成交或未来闭合门。全期主域706,910按下表完整分解；计数沿229，不是本稿重新读大表得到。

| 原状态 | 全期数量 | 严格K处理 |
| --- | ---: | --- |
| closed_beforeK | 673,478 | 精确复用原trade Y、原known_at、entry/exit/cost provenance；无须等K或重算原路径 |
| known_nonparticipation | 16,468 | 原policy诊断0及参与known_at可复用；trade Y与trade known_at保持null |
| closed_onK | 1,903 | 必须重算K.open退出；原盘中stop价不能复制 |
| closed_afterK | 11,607 | 在原完整前缀保证下计算K.open退出 |
| unknown_afterK | 682 | 原首未知严格晚于K，可在完整K前缀及新报价通过时识别K结果；原Y仍unknown |
| open_K_reached | 62 | 原完整观察前缀覆盖K，可在新报价通过时闭合K结果；原Y仍open |
| unknown_beforeK / unknown_onK | 1,851 / 17 | 首未知吸收，严格trade Y null；不读取以后价格救标签 |
| intent / open_K_pending | 348 / 494 | 保留右删失/未到K；不以样本末close清算或填0 |

数值K.open计算只允许四类潜在支持14,254行，主域守恒为673,478+16,468+14,254+1,851+17+348+494=706,910。非主域保留原身份、具体资格/日历原因及policy no-action状态，trade Y null；未知资格的fail-closed原因也保留，不能把其基础经济结果写成已知零。无child mother同样保留no-action身份。

`policy_diagnostic=0`只表示该冻结政策已确定不产生暴露，须有相应policy状态和known clock；它不是filled trade收益。账户无资金、family occupied、整数手拒绝属于账户条件，不能补入这个单动作标签。主域取消在D发生时，不能把其known_at提前至u。

原标签在K前闭合的精确复用依赖原accepted129及227/228身份链，而不是重新模拟一遍确认相同。新增原数值读取若获准，应只读必要列并按immutable action/sequence连接，保留17g/round-trip精度；复制的原Y和clock须逐值相等，不能先降精度再声称精确复用。

## 成本对象及不能省略的机械报价门

沿042/129冻结base/stress，不改费率、tick、滑点、entry、0.25N初损、20low、anchor或R分母。每scenario的单手公式为：

`R_K = [M*(sell_fill_K-buy_fill_D)-entry_fee_D-exit_fee_K] / (0.25*N_u*M)`。

入场fill/fee及原N/M可精确复用原129；K退出必须调用同一已接受报价语义。滑点已在fill内，不能再从net扣第二次；分母不是含费滑的预算unit-risk，也不是2N或改成新K波动。费用在新fill价格上计算，不能复用原退出手续费。模型按每手报数，不能把独立PnL累加称账户收益。

042的stress SELL为`slip=max(0.0003*r,3*tick)`，正tick时向下取整；有效正参考价不保证得到正fill。例如tick=1、r=2，报价为floor(2−3)=−1，被核拒绝。正常原路径没有在K卖出，因此从未验证过这次新quote。

**完整前缀反例：**取tick=1、M=1、u.close=D.open=4、N_u=12、low20_u=0.5，SL0=1。u前20根合法bar可取O/C=4、H=12.5、L=0.5，使TR与N均为12；u stress SELL(4)=1可表示，D stress BUY(4)=7也可表示。D之后未超过20根，旧low20仍0.5；令K日O=2、H=3、L=1.5、C=2.5、V>0，无原force且L>boundary=1，因此原政策继续持有。K收盘后anchor变化，下一日O=4执行原force，SELL(4)=1，旧完整closed成立；新K stress SELL(2)=−1失败。这里只构造合法规则输入，不声称市场发生过此规格/路径，亦不是历史回测。

对τ==K有更强局部论证：原forced/gap已用同O；原盘中stop则B<O，固定tick SELL函数随参考价单调不减，原B报价为正可推出O报价为正。然而这不足以覆盖τ>K行，也不能替代finite fee/slip/net/risk及同schema核对。因此仍统一执行机械门：原K精确bar身份/accepted-valid、正有限O，再分别核各成本SELL报价、正有限fill、有限费滑/净PnL/净R、正有限原风险分母。某成本失败，该成本保留失败原因、strict tradeY/known_at置null；不偷用旧Y或下一日价格替代。

原129是两成本共同成功后才closed。root拟显式采用各成本独立的`K_label_state/known_date/known_flag/R/PnL`，可以接受：上述r=2反例中base SELL=1可表示、stress SELL=−1失败，应保留base已知与stress未知，不用单一known掩盖差异。这个新schema须明确，不冒称129原共同known标志原样继承；closed_beforeK仍两成本原值/原clock精确复制。未来共同训练域只按主stress的finite与clock判断，不能为base另加一组训练实验，亦不能用base成功豁免stress未知。

## K、原force、gap和stop的优先级

严格路径先检查原首未知clock；缺/无效bar和未知吸收优先于任一推定成交。在有效bar上，既有pending原force与K强制均按开盘全量退出，早于gap/盘中stop。建议原因编码明确为：**已锁存原force优先保留原reason；否则K_due用voluntary_K_force_open；否则gap；否则stop；否则持有。** 同时另存`K_due`及source/anchor/lifecycle原因，避免单一reason遮掉并发事实。

同日原force与K并发时，两者参考价均为O，数值没有冲突；不能重复卖出或扣两次费。原042/129已锁存请求不会被新请求覆盖；如果未来实现选择沿157 effective lifecycle的reason编码，也须在冻结时明确同一等价报价和并发provenance，不能通过reason变化改变执行日。对τ==K，无论旧reason为何都走新K开盘核；旧reason是盘中stop时，新值可能改变，旧reason是原force/gap时应得到同参考价与同成本值。

K在样本或calendar之后不clip至末日。原closed_beforeK可立即复用，其余open/pending保留。D=K/D>K在原日历门已不参与，不能先入场再在同K退出。强制K不是调整stop或收益封顶，跳空和真实无法成交风险仍存在。

## strict label与deferred执行的隔离

129在首次路径缺失或无法表示的退出报价处停止完整标签。现金层可以保留stale并在以后bar做理想deferred liquidation，但以后观测不能证明未知区间没有触及原stop、先退出或停板。故本测量不生成可训练的deferred已知收益。

- 首未知在K前/当日：tradeY null、known_at null，保留first_unknown；即使K.open本身正价，也不豁免完整bar合同。
- 首未知在K后：原前缀到K已完整，K报价通过可产生新known label，known_at=K日`after_all_source_close`；不是把原未知恢复为原Y已知。
- 新K某成本报价失败：该成本新strict unknown，在K记录失败；以后报价成功也不改该成本strict known_at。另一成本独立通过时可保留自己的known结果。
- 原intent/open pending：保留其删失，不把长期未决当0、负类或非参与。

这意味着本测量的known子集均值仅是条件描述，不能冒充全主域真实收益均值。没有未经假设的普适有限损失界，unknown不能自动被赋予良性或对称误差。

## 成熟时钟支配的条件证明与旧218复用资格

记τ为原完整closed退出日，t0为原known clock（129固定τ日after_all_source_close），A为原156的D<K可行动门；tK为指定成本的新严格known clock。以下未来共同训练域的Y均专指stress。

1. 若τ<K（含K在calendar外但原确证早于其边界），新政策在τ前完全一致；精确copy给出`Y_K=Y_0,tK=t0`。
2. 若τ≥K，原closed证明D至τ每个所需bar完整，且原入场、费用、分母已识别。K之前新政策与原政策相同；没有提前原退出。**再加K.open新报价及有限净R通过**，新政策在K.open退出，并沿同标签约定于K收盘后成熟，所以`tK=K_close<=τ_close=t0`。
3. 此证明不要求收益大小关系；可能`Y_K>Y_0`或`Y_K<Y_0`，也不推出排序或可预测性。反例说明缺失报价条件时tK可为null，因而不能写`tK<=t0`。

令六fold原130成熟训练集合为T_f，218实际训练集合为`S_f=T_f∩A`。未来纯target比较应使用`C_f=M_f(Y_0)∩M_f(Y_K)∩A`。若对每个S_f行都通过上面的复制/报价/finite及clock门，则逐行`tK<=t0<cutoff`，因此**C_f恰等于S_f**；K新增提前成熟但原Y未成熟的行不在该纯target共同域。它们必须保留在完整测量产物中，不能混入候选训练而控制仍用旧S_f。

只有这个逐六fold恒等式及共同身份成立时，旧218的DOMAIN52模型才可以作为未来同C的原Y控制：两臂固定旧130 scaler坐标，固定218使用的旧130允许行权重`w_i*(W/W_A)`原值、相同总loss mass、alpha/intercept/solver和52设计，只替换Y值。不能重新按K区间算union/uniqueness、重新归一、重估scaler或加duration，然后声称仅换目标。旧130全域COMMON52模型本身不是这一同C控制。

若任一S_f行新stress strict unknown、非finite或clock不满足，C_f是S_f的真子集，旧218即失去同C控制资格。届时先报告具体fold、身份、数量和旧权重mass，停止自动进入fit；不能删除这些行后仍复用旧218，也不能在本轮默许补控制重训。是否值得另付控制成本应由测量结果后的新决策回答。

**当前控制复用状态明确为待核，不自动资格。** 本次有限测量不读六traincache/不fit；可只输出对全部原closed且primary动作的逐行stress报价/finite及`tK<=t0`结果。若全局通过，它是覆盖六fold子集的充分报价/clock证据，但还不是六fold身份、C/S恒等式、实际权重和scaler的最终复用认证；若全局有失败，也不能直接断言六fold都失败，因为失败行可能不在旧cutoff训练域。未来仅在另冻设计中按精确失败身份与原训练集合核对，不能为取得资格现在扩大读取。

## 最小验证、停止条件与结论范围

若root另行冻结actual，最少验证应是本新行为的tiny fixtures与随后独立新产物审查，不重跑全部旧suite或原价格路径：

1. exact-copy closed_beforeK；known cancel的policy0/trade null；非主域/nochild身份守恒；aftercalendar与D sentinel不夹至末日。
2. K force优先盘中stop、K与gap参考同O、K与原force只退出/收费一次；τ==K重算；上述低价tick报价反例必须进入strict unknown。
3. K前/同日unknown吸收、K后unknown可在K新闭合、open reached可闭合、open pending不假清算；所有known使用after_all_source_close。
4. 完整action/mother域和229分区计数守恒，只有14,254潜在行新增K报价；全673,478复制行原Y/clock精确相等；全新quote/成本公式和全部原closed primary的stress clock支配逐行核验。当前不读取六traincache、不输出已认证的每fold复用结论；未来六foldC/S恒等式与原权重mass资格另核。

132 cache只有epochs/offsets/days/values/accepted/valid/N/low20/run和database绑定，不自带经济snapshot、原calendar或canonical reference关系；必须由accepted129/128/132精确绑定闭合。其schema原用途是本地恢复，不能仅因文件存在就当新的研究资格；新协议须明确授权复用并冻结其确切身份。若物理上要整体加载NPZ，须如实记录一次全cache加载与仅14,254行新数值计算，不能说只读了14,254行磁盘价格。不得换连续/复权价、当日canonical月份或另找有利报价。

硬停止：身份/输入绑定/状态穷尽/clock守恒失败即停；不能精确复用旧closed前缀、只能从现金fills取值、unknown需deferred或补价才可known时否决该实现；报价失败如实unknown，不改tick、成本或valid门消灭失败。全域测得无识别数值/状态差异，则关闭此固定目标轴，不改K找差异。存在差异也只支持对象非恒等，不自动fit；若差异仅在unknown不可识别域、没有可用共同域或控制成本超过有限研究价值，停在测量结果，不扩成target×clock×weight×duration多轴包。

当前建议root可据此冻结一次单动作测量，仍禁止训练、selection、现金、加注、生产或Git动作。测量结果至少分别报告：完整主域的known/unknown/cancel/open覆盖；原/K可比较known动作的差异；原unknown/open但K新known的数量；全原closed primary的stress支配覆盖及“六fold同C控制资格待核”。任何价格差、2%支持、均值或反序均不能替代未来预测增量、各自资金路径/回撤、执行尾部和真正未见证据。

## 变更、财务指标与前后反思

- 新增仅本唯一Stage231；新增/修改/删除脚本0，新增/修改/删除参数0，新增/修改/删除历史回测结果0。不改LINE、registry、根memory/back_log、其他阶段、其他研究线、生产或Git。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A；低价tick例是逻辑反例，不是市场或现金结果。
- 开始/结束是否有过拟合风险：**是**；失败后选择目标解释仍是同史适应性研究。新增按历史收益调参：否；没有读新收益/价格或选择参数，但这不会清除既有选择风险。
- 开始继续审查价值：**是**；它能阻止无条件成熟支配和错用旧控制。结束继续扩大方法搜索价值：**否**；边界已经足够。继续一次有限对象测量价值：**有条件的是**，限上述严格成本/clock/unknown与控制资格测量；直接fit/cash或复活DOMAIN52价值：**否**。完整全市场目标仍active、未达成；识别超高质量、极小止损可靠性与加注资格仍缺证据。
