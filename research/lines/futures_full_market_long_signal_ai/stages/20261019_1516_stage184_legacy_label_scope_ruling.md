# Stage184：早期缺VARID/WHTYPE的声明scope兼容性ruling

2026-10-19 15:16 CST；line_id=`futures_full_market_long_signal_ai`。先读registry，另仅读181 `source_structure_groups.json`的小keysets/对应起止日期、176及183设计；未读新raw、数量、scalar、金融成绩或181其余审计输出。根提供的181完整审通过事实不在本分工重审。唯一产物为本stage及[小ruling.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage184_legacy_label_scope_ruling/ruling.json)，供185根判；非重要突破、非norm/金融授权。

**有条件可兼容“声明的源行scope”，不兼容任何自动物理类型恢复。** 183以2025样式为前提列入VARID/WHTYPE，需要表示层补充：字段不存在可以保真记为NOT_DISCLOSED，不应凭缺字段把整段历史自动判成不存在仓单，也不应填1/2让其假装成为新schema。能否形成单个有效比较对仍须后续规范逐项证明；本ruling不宣布可用比例或source整体通过。

181小表在新body中给出三种行keyset：2014-05-19—2023-11-16只有11字段、无VARID/WHTYPE；2023-11-17起13字段含两者；2024-03-21起去掉排序字段，余10字段。所读结构表是**new_bodies_only**，最后观察日不能当全archive版本终点，复用报告未重读。每个行keyset作为最小表示版本断点；加字段、删排序字段以及JSON/HTML两侧不跨界比较。相同keyset本身不认证同语义。

声明键应完整保留：源格式/表示版本、**原VARNAME完整值、原WGHTUNIT、各字段presence**，以及已披露的原VARID/WHTYPE值。字段absent、存在但空串、null和原字面值分开；NOT_DISCLOSED只记录未披露，不是“All types”、默认仓库或物理代码。不得拆名/模糊匹配/取共同中文前缀来拼scope，不用行序号或仓库名称推断缺失WHTYPE。原label本身显式写有厂库等字样可以原样作标签，仍不能把该文字反写为虚构type码。

在此键内，原label必须唯一识别一个**原普通总计及其完整、非重复的源明细覆盖**。v/w均有同一scope、同覆盖、唯一总计和已知原qty，才可在明确同对象/同尺度假设下沿183原F比较。唯一不是“第一个/最后一个总计”，也不是几项加起来数字恰好吻合；ROWSTATUS等层级角色若无法由可靠原结构判明，同样unknown。

以下任一情形均不可组装修复：同label/单位/presence下出现多个无法唯一归属的普通总计；混码/混单位；父子、税类或小计覆盖重叠；跨日覆盖变化/空缺；原label不足以唯一识别登记范围。不得加总模糊总计、取仓库交集、回找最近成功报告、按数量变化或收益挑组。按183任一应有scope坏则**整个product scalar unknown**，全母域行仍留，不靠丢坏scope后平均提高可用性。

必须分清三层：①源行group及其不重复覆盖可由原文结构条件性识别；②其物理仓库/厂库/保税类型、单位释义仍可能未认证；③不同源group的物理货物是否非重叠/独立，不能从不同标签或行不重复推出。183的均值只是假设可用登记表征的等权pooling，绝非总物理库存合并；不混加原qty、不假定独立货物、不因相同标签便认定十年同对象。若源层父子重复都不能排除，则源partition不成立、unknown；若任务要求认证物理货物partition，则此证据仍no-go。

研究product mapping作为**独立overlay**：原label若已有唯一、精确研究product身份，可另存映射依据/适用段和mapped_research_product_id。rawVARID始终absent；不能以2023后VARID存在本身倒证早期身份/语义不变，更不能回填原字段或改变原scope。映射歧义保留missing，不按近似名字合并；映射成功也不认证物理类型。product不是合约epoch，普通/F及六所全母体的原身份/缺失规则不变。

本次只纠正“2025字段普遍存在”的表示假设。F、双0、等权、时间关系u=预定entry/D=prev(u)决策/v=prev(D)/w=prev(v)、完整原日历、format断点、target、训练模型/权重/切分、共同K、风险/止损/资金和统计门**全不改**。172物理语义门不降低，旧码仍unknown；183另签条件归档研究须事前诚实承担同对象/同覆盖/同正尺度与发布/修订假设、strictPIT=false。原label若做不到scope身份识别，相关域no-go，不能人为恢复类型或继续无限字典工程。

0代码/SQL/fit/cash/raw读取/联网/下载；累计409fit/218cash不变，无新金融参数或权益/收益/DD/Sharpe/滑点/交易数/胜率。调研继承176/183已读主源，不重复检索。开始/结束新增结果调参过拟合否，因为只看字段存在性、尚未看新scalar/收益；长期择题/归档风险仍是。此最小兼容性澄清有价值，篡改物理状态或为可用率拼组无价值；185根判之后才可另定一次norm协议，未自动金融、未加注，完整目标未完成。不改LINE/registry/旧设计或源。
