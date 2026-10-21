# Stage464：原 first-exit 终值目标的删失可识别性审查

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-20 22:42 CST；工作区：`/Users/mac/Desktop/fian`。
- 性质：只读科学筛选；不是重要突破，不触发实际 A/B、拟合或资金；只新增本记录与本阶段 JSON，不改旧文件、LINE、registry、Git 或生产。
- 原目标保持六所 98 产品、95 家族 long-only：先识别高质量信号，再独立验证 0.25N 窄损，最后才有资格讨论加注。
- 开始反思：本次根据新收益救参的过拟合 **否**，未计算收益或修改策略；同史多轮择题风险 **是**。继续价值 **是，但仅到可识别性审查和一次必要条件测量**，不能见到 censor 就开发生存系统。

## 裁决

**当前新生存模型、辅助损失、IPCW 重加权或现金回放均 NO_GO。原130成熟标签纪律正确，尚无证据把它判为 bug。** 有一个未被旧 K_TARGET/DOMAIN 包直接回答、但更窄的问题：原 cutoff 前已成交且持续可观察的未退出前缀，能否完整重建为有意义的风险集？只保留一次不看 Y/价格的状态与时钟支持测量的条件价值。本阶段未执行测量，也未自动授权模型。

可观察前缀确实可能提供原闭合回归未利用的**退出时间信息**，因此不能逻辑上断言“开放样本毫无信息”；但这些信息不自动识别原有符号、无预设截断金额界的终值 R，更不等于识别重叠组合现金。当前不存在一个只换方法名、同时不引入额外观察/尾部/收益联系假设的通用修复。

## 本地事实与原合同

先读 `research/registry.md` 与本线 LINE 对129/130、098—103、209—240的记录，再检查129/130源、070字段声明、129小manifest及240结案。没有打开原actions、Y、COMMON、score、行情或数据库；下文不产生新数量。

1. `stage130_contract_choice_fit.py:60` 的训练域要求 `u_action_eligible==1`、`closed_complete_bar_model`、`u_date<cutoff`、非空且严格 `<cutoff` 的 `label_known_date`、有限 `net_R_stress`。未来才退出的标签不得提前使用；等于cutoff也不成熟。这是必要因果纪律。
2. `stage129_contract_choice_dataset.py:246` 起明确 `risk=.25*N*multiplier`、`net_R_stress=net/risk`。130 scaler标注 COMMON 继承原2N单位。**特征坐标2N不等于目标止损2N，当前没有该错配。**
3. 已完成样本的目标是自己的 NARROW 原始first-exit结果；退出由原止损/20low/anchor/lifecycle政策决定，未设置本阶段新horizon。它是行动的每手归一化结果，不是资金账户终值或完整复利效用。
4. 原130 family-u区间union、动作分摊、等日权重取成熟路径的entry/exit。它们处理相关样本质量，不是删失概率。把未知路径另补一套权重或把union端点截成cutoff都属于新假设/新干预，不能称原训练的机械修正。
5. 本阶段继承累计 **466fit / 254完成cash + 1旧partial**，没有新fit、cash、SQL、下载、重新标签或总体状态计数。源可达只说明材料可用，不说明存在alpha。

## 不能把不同未知都叫作同一种右删失

| 原状态/分支 | 可以知道什么 | 不能直接做什么 |
| --- | --- | --- |
| `closed_complete_bar_model` 且成熟 | 原bar模型下终止时间与净R已知 | 不代表实际成交、全市场因果收益或资金资格 |
| `open_right_censored` | 已知进入，连续可观察前缀内未触发原退出；终止时间晚于该前缀 | 不把当前浮盈当终值、下界或正收益；不宣称原0.25N封顶损失 |
| `intent_right_censored` | 次源日D尚未进入观察范围 | 不假造已成交、T=0幸存或未来取消 |
| `known_nonparticipation` | 由原规则在已知时点取消，没有交易暴露 | 政策诊断可为0，但原trade-Y空；不能塞成0R闭合交易 |
| `entry_execution_unknown` | D缺失/无效，无法确认入场执行 | 不当普通已入场幸存样本，不补0或loss |
| `path_or_execution_unknown` | 最后连续有效前缀之后的持仓路径/执行不明 | 缺失当日不能算已观察且未退出；不能仅凭后续有价跨过中断 |
| `input_or_economics_unresolved` | 要看具体发生阶段：u、entry与exit cost不同 | 不统一当作独立行政删失 |

129先计算 `price_exit_reference`，再尝试exit adverse quote；若后者失败，会在unknown分支停止而不是写入closed/净R。因此代码允许“退出事件已由价格路径触发、金额mark未解析”的概念情形，与“还没观察到退出”不同。本阶段只确认分支语义，**没有测到它实际发生的数量**。129小manifest的末端 `open` 数量也不是各历史cutoff的未成熟数量，不能用小manifest末端频率推断历史训练偏差轻重。

## 外部原方法、官方文档与判断

以下只采用原作者或维护者来源，未安装、执行或复制外部算法。

- [scikit-survival IPCW官方文档](https://scikit-survival.readthedocs.io/en/stable/api/generated/sksurv.metrics.concordance_index_ipcw.html)说明该实现借训练集估删失分布，要求时间支持，并以随机、与特征独立的删失作为KM前提；[维护者metrics.py](https://github.com/sebp/scikit-survival/blob/main/sksurv/metrics.py)有同样条件并调用 `CensoringDistributionEstimator`。它给的是删失下C-index方法，不能据此宣布原终值R已无偏。
- [IPCRidge官方文档](https://scikit-survival.readthedocs.io/en/stable/api/generated/sksurv.linear_model.IPCRidge.html)的AFT对象是正的事件时间，形式为log-duration线性模型；有随机删失假设。原R可正可负，不能直接取log。以其时长预测替原R，或额外平移/变换R，都会改变问题。
- [Royston与Parmar原文](https://pmc.ncbi.nlm.nih.gov/articles/PMC3922847/)把RMST定义为指定时间上限前的生存曲线面积。它估计有限区间的平均时长；为了得到稳定量而另挑tau，会新增固定horizon，且仍不是原净现金R。
- [维护者competing-risks文档](https://scikit-survival.readthedocs.io/en/stable/api/generated/sksurv.nonparametric.cumulative_incidence_competing_risks.html)以时间和风险类型估各事件累积概率。止损/anchor/lifecycle等类型概率不包含对应退出价格、跳空和成本分布；把类型乘固定奖惩会新增收益映射。
- [Overgaard与Hansen原文](https://arxiv.org/html/1905.02508v1)区分可识别性与代表性条件。完整独立删失是常见充分表述，并非所有方法唯一必要表述；采用较弱条件也必须把它和目标联系写清楚，不能说“通过统计检验就证明非信息性”。
- [Ding与Nan原文](https://arxiv.org/abs/1307.8369)指出非参数均值估计的支持问题，也给出线性模型及协变量支持等额外条件下的可估例外。因此不能说有限随访永远无解；当前也没有证据满足这些额外假设，而且其对象仍是生存时间。
- [Lin的金额删失原研究摘要](https://pubmed.ncbi.nlm.nih.gov/12933524/)说明常规生存方法不直接适用于未完全随访的总医疗成本，需针对金额过程修改估计。这里只借此确认“时间终点与金额终点不同”，不把非负累积医疗成本方法直接移植成期货带符号、可跳空的mark-to-market收益解法；未以摘要推导或执行其算法。

## 为什么成熟必要，但完整终值仍未自动识别

以下期望论证仅在目标有定义的已进入交易风险集内，取消与入场未知另列，不给它们造trade-R。设X为u时点信息，T为原first-exit时长，R为该退出的原 `net_R_stress`，C为能持续观察的时长。原成熟回归在其固定权重下拟合闭合已知域的投影。即使暂不考虑线性近似与权重，`E[R|X,T≤C]`也不自动等于`E[R|X]`：若长短路径与终值相关，完成筛选会改变样本。这是**可能的选择问题**，本阶段没有读取数据证明其大小、方向或是否伤害原选择。长期持有可以盈利也可以亏损，不能把它自动解释成漏学大赢家；更不能以此跳过参与机制直接声称识别全部u合格动作的政策价值。

一个简单识别反证不需要行情：保持所有已观察前缀和已完成R完全相同，为尚未退出的轨迹安排不同的后续价格/退出mark，便可得到不同的终值条件均值。原规则对未见尾部尚未提供一个已验证固定金额界，初始止损也不能消除缺价和跳空。**“存活到c”只约束T，不能推出R大于c时浮盈、R≥0或R≥−1。** 把0.25N换成更宽止损、把unknown填loss、把终值截断成某tau收益，都不是这个识别问题的答案。

在一个理想标记事件模型里，若 `P(C≥T|T,R,X)=G(T-|X)>0`，且目标可积，则有

`E[ I(T≤C) * R / G(T-|X) | X ] = E[R|X]`。

这是本阶段用于说明条件的期望恒等式，**不是本项目已经成立的估计器或新权重方案**。它要求观察概率对终值mark也可忽略；只假设C与T独立、只拟合退出hazard都不够。条件化路径的更一般动态观察机制可以写，但需明确序贯可忽略性、状态充分性和正支持；增加复杂系统不会凭空获得这些证据。原多动作union权重的投影目标还需另行定义，不能把上式当其即插即用修正。

行政截尾的C由entry日期与cutoff决定。给定精确entry日期，cutoff之后的观察概率本来为零；通过更早cohort借长随访，隐含跨时期关系可迁移，不能靠边际KM把市场年代、上市/生命周期与流动性差异抹掉。持仓缺bar/退出成本未知更不自动独立于R。这些假设无法仅从已经缺失的尾部验证；状态核查最多发现反证、时钟错误或支持缺口。

## 与旧失败包的真实差别

- 098—103已经以固定log曲率做过4fit/8cash并关闭。本题不改变风险偏好或效用；不能换一个survival名称把log包重启。
- 209—221 DOMAIN52改变D<K训练loss域/质量，保持成熟原Y；本题只问原未完成轨迹是否提供可用的观察信息，不重筛月份/样本域。
- 226—240已经测量K时钟/标签对象，并以固定same-C K_TARGET52做6fit、0cash反证。本题保持原first-exit终点；不把“cutoff前还没观察完整”重包成“原标签和K错配修复”。不再改K、duration、target、weights小数或资金目标。
- 非线性模型改变给定完整样本的函数容量。本题若有新增信息，来自未完成轨迹的观察前缀；若原前缀不能重建，换AFT/forest/深度模型并未增加可识别信息。即便能重建，时间规律到R金额的桥梁也仍未获得。

## 唯一可保留的最小下一步：状态/时钟支持测量，未执行

科学问题仅为：**在原130两个cutoff及原六fold划分下，未成熟但u合格动作中，有没有能用现存metadata严格证明的“已进入、连续观察到cutoff前且未退出”的额外前缀；还是主要属于未入场、已取消、缺价中断或金额未知？** 这是可证伪的必要条件，不是检验其是否盈利。

如将来单独安排一次，优先复用同源已接受metadata投影，不为本题重复大读；缺对应投影才允许原actions一次白名单流投影。字段白名单及严格禁读字段写在本阶段JSON。只需identity、u/D、entry/exit/label_known、unknown、last_path/holding日数、各participation/label状态与原因；母体只复用七列identity以保留nochild，日历只用原绑定index/date。**不需Y、价格、N、止损价、COMMON、scores、q、SQL或下载。** 这是未来测量的边界，本阶段没有执行权限扩张。

行政cutoff只沿原130的 `2020-01-01`、`2023-01-01`。以原source calendar求 `j_c=searchsorted(dates,c,side='left')−1`，即严格早于cutoff的最后源日，phase沿 `after_all_source_close`，**不是另造固定持有期**。确认进入且仍处于连续无退出前缀时，暴露年龄为 `max(0,min(j_c,最后验证无退出index)−entry_index+1)`；终止当天不可又计为无退出幸存。

时钟重建按cutoff严格 `<`：最终在cutoff后才closed的行，cutoff前应还原为当时状态，不能用末端label_state作u特征。原模拟在首个unknown即停止，因而以后closed可证明此前连续前缀，但后来的退出日/原因/结果不得进入训练信息。held-bar在k缺失时，最多证明至k−1的无退出暴露；entry unknown没有已入场暴露；exit cost unknown即便last_path_index为k，也不可把事件日k假装为未退出。

输出只要原fold/cutoff状态支持、完整母/子身份保持、精确source-day年龄的暴露/退出/中断计数、原family与entry年覆盖，以及矛盾/未分类表。不选新年龄分箱或期限，不算收益、胜率、显著性，不拟合G或hazard。动作与family-u都只是相关支持，不能算独立经验数；最大已观察时长也不能证明未知尾部已覆盖。

停止条件：

1. 若原cutoff前没有额外非零可验证开放前缀，立即关闭该经验方向，0fit/0cash。
2. 若日期/phase/entry语义不能区分行政开放、入场未知、持仓中断和取消，报告缺证即停，不读价格强补、不重标unknown。
3. 若任何前缀或event/censor时钟矛盾，停止推断并逐条披露；不自动改129/130或回跑旧数据。
4. 若目标域支持不足，继续必须删family/年份、另挑horizon、外推未见尾部或直接断言无法验证的reward独立删失，则保持NO_GO，不以小阈值救参。
5. 即便支持测量全部干净，也只证明一种观察信息可构造；**不授权辅助训练、IPCW、survival模型、资金或加注**。后续仍须另行提出原终值目标为何可识别的明确可反驳条件，而非增加统计工程。

## 变更、计数与结束反思

新增本中文stage及 `outputs/stage464_censoring_mechanism_assessment/assessment.json`；没有代码模型、交易参数新增/修改/删除，原止损/horizon/目标/资金口径不变。实际fit/cash/SQL/下载/新数据测量全0；累计保持466fit/254完成cash及1旧partial。期末权益、总收益、最大回撤、Sharpe、总滑点、实际交易次数、胜率均N/A，未运行新回测；提议的观察暴露不能冒充回测成绩。

结束过拟合判断：本次按成绩调参 **否**，未读收益、未试参数；同史方向适应性风险 **是**，不能因Con4弱而在censoring下继续救目标/时长/权重。继续当前survival训练包价值 **否**，可识别前提未有证据；一次必要条件状态/时钟测量的条件价值 **是**，它能在无Y/价格下及时否决不可构造风险集的路线。继续完整全市场高质量做多AI目标价值 **是**，本阶段只限制这条具体推论，不宣布所有AI无效。

置信度高在源码语义与“时间信息不足以自动识别金额终值”的逻辑；对本数据偏差实际大小、方向、alpha完全未知。没有窄损封顶、加注、正式晋级或生产资格。仅由root按各stage合入，不修改本线LINE/registry或根历史总账。
