# Stage291：持仓初始风险占用是否应随保护位释放

- line_id=`futures_full_market_long_signal_ai`；2026-10-20 01:37 CST。非重要突破，仅只读资金口径审查，不重开290动态组合/盘口，不找新数据源。
- 顺序为3个网上query、3个原始/维护者页面，再读registry、本线LINE、039/068/128/157合同与必要042/070/131源码。没有读取大账本、价格、SQL、标签、模型或新金融结果；没有import内核、运行fixture或任何actual。
- 只新增本唯一stage，不改LINE、registry、旧代码或正式版。新增/修改/删除策略参数与金融结果均0；新增fit/cash及下一actual预算均0，累计441fit/238cash不变；权益、收益、DD、Sharpe、滑点、交易次数、胜率全部N/A。

## 裁决

**常量初始风险占用是有意的资金纪律，不是已证实漏更新bug；它是有经济含义的“入场风险额度存量”，却不是当前权益的真实损失估计或普遍保守上界。** 本轮找不到可由唯一合同与现有资格直接确定的gap/延迟退出stress，故对“改成动态剩余损失并据此释放新仓预算”作**NO-GO**，不硬填一个gap倍数开展实验。

这项机制在本线没有找到已实施的直接动态占用对照；039与068反而明确选择不释放。尚未做过不等于现在值得跑。结论针对当前可实施性，不等于一切动态风险计量无效。

## 当前代码实际做什么

1. [039资金合同](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261018_1322_stage039_cross_session_reference_protocol.md:49)规定已有仓按初始入场风险持续占用，不因浮盈或退出位提高增加额度；[068窄损合同](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261018_1614_stage068_narrow_initial_stop_cross_session_proposal.md:69)明确把它带入0.25N政策，不是遗留2N未适配。
2. [070单位风险](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage070_policy_kernel.py:42)为`0.25N×M＋入场时估计往返费滑`。131在D实际入场写入risk_per_lot，此后部分退出仅减少qty；[042 totals](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage042_cross_session_experiment.py:233)汇总`Σqty×初始risk_per_lot`。
3. [131 prepare](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage131_contract_choice_kernel.py:93)同时将这一口径用于超额判定、新仓预留和旧仓共同减量；并非只有一个展示列未更新。权益为cash＋当前close mark浮盈，保证金也按当前mark计。因此**现政策并非完全不随盈利变化**：2%乘当前权益的绝对额度仍会变，只是不额外按保护价释放原入场额度。
4. [131收盘顺序](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage131_contract_choice_kernel.py:168)先以当日已完成low20更新下一日boundary，再调用prepare，D只使用u已预留配额。它是研究撮合边界，不等于broker已接受并持续生效的保证成交止损单。源码函数为`max(SL0,low20)`，不是显式`max(previous_boundary,...)`；在连续有效bar且按旧boundary未触发退出的存活路径中，滚动low20的构造支持非降低性质。本轮未读全路径，未声称完成历史单调性审计。

F0的经济含义是：一次机会获得多少初始风险额度，该额度在持有期间持续占用，抑制同一笔尚未结束的机会反复腾挪额度。它可以比某些当前止损距离更紧，也可以更松，不能改名为“最多还会亏多少”。其含已付入场成本也不构成重复扣权益，因为预算额度与实际现金扣费是两个不同对象。

## 当前权益风险不能用入场盈亏替代

对已盯市的long仓，当前权益到理想保护成交的损失应从**当前mark**出发，结构为：

`L_stop(u)=q×M×[mark(u)−sell_fill(B_next(u))]＋尚未发生的退出费`。

若进一步加入gap/无法立即退出情景，应先定义只依u信息的stress成交价，再从当前mark计算情景损失。不能用`max(entry−stop,0)`代表当前权益风险：即使stop已高于entry，mark到stop仍可能回吐已经记入权益的浮盈。**B上移不蕴含mark−B下降；若mark涨得更快，剩余回撤距离可变大。** 这是计量恒等关系，不是本线历史效果证据。

动态量原则上必须允许增加也允许减少已有仓占用；只把它裁成“不超过F0以便释放”已预定方向。已付入场fee/slippage已体现在cash/entry fill及浮盈中，不能再充作未来退出成本。保证金则仍随名义敞口与规则占用，保护价提高不会自动释放broker保证金。

## 有界原始方法调研与判断

- [Backtrader维护者的Sizers—Smart Staking](https://www.backtrader.com/blog/posts/2016-07-23-sizers-smart-staking/sizers-smart-staking/)区分持仓大小与动态ATR stop。其Van Tharp部分是维护者转述，正文示例sizer是固定stake；它没有提供“剩余风险可随stop提高归零并重用”的资金定理，也不是原书作者对本线盈利的证明。
- [LEAN维护者TrailingStopRiskManagementModel源码](https://github.com/QuantConnect/Lean/blob/master/Algorithm.Framework/Risk/TrailingStopRiskManagementModel.cs)按持仓价值峰值触发目标清零。实际动作是提交PortfolioTarget(symbol,0)，不是计算可释放风险或证明损失上界；不能把源码注释中的maximum loss措辞当保证成交。
- [CME Futures Order Types](https://www.cmegroup.com/education/courses/futures-trading-mechanics-and-regulation/futures-order-types)区分stop触发、限价与保护范围；触发并不等于按触发价全部成交。它支持把执行不确定性与计划stop距离分开，但不是国内六所规则认证，也没有给统一gapstress数值。

调研结论：原方法支持“头寸大小、保护退出、可用资金是不同对象”，没有一个可直接移入本线的唯一动态占用定义。没有安装、复制或执行外部算法，3查询/3原文页预算未扩。

## 事前支持与阻断

现有代码结构可在u提供持仓数量、原risk_per_lot、last_mark、下一保护边界、经济身份、stale/deferred状态、当前费用情景及保证金。**这足以定义一个理想mark-to-stop诊断量，不足以唯一确定可再投注的真实风险释放量。** 本轮未读账本，故不知道预算是否绑定、多少订单可能改变或动态量通常高于/低于F0，不编造影响数量。

关键缺口如下：

| 必须冻结的对象 | 当前不能机械填的理由 |
|---|---|
| gap/延迟退出stress成交价、适用时域 | base/stress的tick/bps不利滑点不是跨session跳空或连续停板损失分布；选ATR倍数、历史分位或窗口会新增风险自由度 |
| stale、缺价、待强退、退出容量未知的处理 | last_mark和理想boundary不代表当前可成交；预计D退出不能提前腾空u预算，旧费用/缺价模型没有给严格有限退出保证 |
| 同时多仓的风险口径 | 按仓求和只是所选情景，不自动覆盖共同跳空；不能为此顺带重开covariance优化 |
| 同一口径贯穿预留、超额减量与报告 | 只替换reserve的existing_risk会与旧initial_risk超额及reduction_targets冲突；这是政策变更，不是修一个展示值 |

强行设`gap=0`只能得到理想stop情景；强行加某个倍数会把核心结论交给主观参数。反过来若用原F0作不可降低的floor，便没有支持“释放初始风险”的这一假说；也不能因此重开已关闭riskfloor包。当前没有唯一的有经济依据且已资格化的gap合同，故不进入金融验证。

## 与旧政策的区别、不利可能和停止点

本题有别于riskfloor按账户状态改风险倍率、covariance按联合协方差改组合、0.25N改初始损距；它只讨论已有仓的预算占用定义。但即使单family0.25%/总2%数字不变，允许释放后增开其他仓仍会改变实际名义额、并发敞口与换手，是新的资金政策，不能称“没有增加风险”。

可能的不利结果包括：保护位靠近entry但浮盈回撤被低估；顺势行情中腾出的额度累积到同向相关仓，随后共同gap；动态占用增加时强制减掉长尾赢家；仅减少风险cap而margin仍绑定、实际动作0变化；新增交易费滑抵消任何资金利用率收益。没有新预测信息，不能凭资金更满就宣称高质量long识别改善。

**明确NO-GO，下一actual预算0。** 本阶段不实现诊断器、不先扫大账本找好看的释放量、不写新现金臂，不以暂时缺合同为由无限补来源。若未来另有独立依据给出唯一风险/退出情景合同，必须作为新资金政策收益前冻结，完整候选、预留、减仓、stale及各自现金路径一起对照；不能拼接旧被拒订单的事后PnL。这里没有自动授权。

开始/结束过拟合反思：本次按收益调参**否**，未读取新金融/选择产物或任何大账本，也未按设计记录附带的旧金融数字选择公式；同史选题风险仍为**是**。继续这一次只读经济口径审查**有价值且已足够**；把它包装成漏更新bug、立即释放预算或挑gap倍数试历史**无价值，停止**。原完整目标仍未达成，不授窄损或加注资格。
