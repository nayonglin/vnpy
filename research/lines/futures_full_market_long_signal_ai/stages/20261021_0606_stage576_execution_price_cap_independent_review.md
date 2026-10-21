# Stage576：D执行价格上限的独立结构审查（0实际）

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-21 06:06 CST；day；独立概念/接口审查，非重要突破。
- 已先读registry；全98历史产品/95家族long目标active，535fit/278完成cash及1旧partial不变。正式C9与月度AI选品不在本次范围。
- 本轮只读原131/157、070和042的相关纯函数、015/020/079/082/291/299的有限关闭边界，及少量交易所/维护者资料。不读原大表、不回放旧现金、不新增行情或参数尝试。

## 结论

**有条件值得一次固定的研究报价政策反证；不是原执行bug修复，不是已证明真实限价alpha。** 候选仅增加：原u收盘已选定的同epoch intent，在D原模型化不利买价`P_buy(D) <= C_u`才允许按旧规则进入，否则当日取消。模型、分数、原156候选域、0.25N/20low/K、风险/保证金/容量/费用算法全部保持，D不换约补位、不重分当批取消预算。

区别于继续换特征，它直接改变“已经决定做多，执行时是否愿意支付这个价格”的动作，且只依D当前报价参考与u已知锚。原D数量只减规则已响应实际成本/保证金，却没有支付价格上限；数量仍足够时，即使价高于u.close也可能买入，所以新条件不由旧规则逻辑推出。无需新增fit，原A157四账可复用，新增至多四C现金研究账户可回答完整政策的收益/DD问题。

这只是**最小可证伪价值**。u.close是一个研究者选择的参照价，不是合理价值、所有信号的永久有效价或未来回报上界。零gap不代表零研究自由度；“绝不追高所以一定更安全”没有成立。它可能主要漏掉消息重估和右尾趋势，也可能买到恶化消息后的低开，仍会止损、跳空和出现尾部损失。

## 与已关闭政策的边界

- 015/020是达到u.high后才确认入场，使用不同的盘中触发及其之后路径，固定4R/DAY代理、识别外界大量非单值；原结论只关闭该固定确认比较及阈值救参。当前政策在D单一执行参考时允许/取消，不等待盘中触碰u.close或u.high，不复活旧CONFIRM标签/策略。
- 079/082在u预算缩放之前排除一手不可行者，改变共同分母；本政策保留原当批缩放，随后D取消一项，不让其释放额度给同批他人，非重新做一手预过滤。
- 291动态风险占用释放会改变持仓风险计量/旧仓减量，本政策不动该定义，不用浮盈释放预算。
- 299 q20为u当时已知的过去20bar重开盘贡献，失败后不可改window/符号等救该字段；当前D价格不是该历史摘要或其变换，作用时钟与执行动作不同。此区别不授权再训练gap特征或为q20换标签。
- 066/073的turnover/VWAP关闭边界不提供本政策依据，本政策不用结算/VWAP。退出514、HGB430、annual469、行业533、PMI564、PCR501、OI541全部保持关闭。

因此没有发现本精确定义已实测失败的同政策，**但这仍是看过大量同史结果后的新择题**，不得称真正未见OOS或因无fit就无过拟合。

## 必须说清的因果时钟

数学判定不需要D.high/low/close或未来盈亏；gate只读原`adverse_quote(D.open, BUY, economics, scenario)`结果和同epoch `u_close`。042定义该报价为open加既定bps/tick不利滑点、再向不利方向tickize；不是逐笔BBO、主动卖价或已承诺可成交报价。

**D.open是开盘时已打印的交易参考，不能声称先看它再回到同一拍的开盘成交。** 因此此政策在现有数据下最多是“预先声明价格上限、按原研究open+不利slip模型筛选进入”的情景，不是已认证真实报价触发、竞价排队或开盘后即时成交。如果选择在真实开盘后看BBO再下单，实际价格/时间会是后续事件；当前日线不提供该精确路径。该限制应在协议和结果保留，不必为这一轮先补全98品种分钟/Tick或部署真实限价单。

不得用D.low<=u.close补成passive成交、把被取消intent改为盘中重试，或把虚构fill价格截在u.close。这些都会改变问题并引入顺序/队列未知。通过gate时仍用旧模型报价，不“改善”fill；若原bar/quote未知保持原unknown，不当成便宜价通过，也不改成已知零收益标签。

报价阈值是**价格**，不额外把fee塞进判据；fee仍按原unit/PnL算法处理。“含不利滑点”不等于“已经包括全部手续费的净成本”。base/stress的报价不同，通过集合也可不同，压力比较因此同时包含成本和参与变化，不能描述成同交易名单只多扣费。

## 原纯函数可复用的位置与两项措辞修正

静读131执行核：`prepare(u)`根据本账户equity/持仓先处理减量、同族占用、原候选和生命周期，再调用原共同`reserve_capped`；D先处理旧仓退出，再执行pending；原`execution_quantity`只按该intent已分到的risk、margin+fee和qty_cap减量，不重新分配他人额度。原u_close已经随selected signal保存，为选中epoch自身close，而非canonical锚或连续价格。

可在独立适配器中保留全部原逻辑，只在原全部入场资格和qty>0成立、`ledger.enter`之前增加gate及明确取消状态。旧代码/模型/标签不改、不全局monkeypatch。报价采用同一次`execution_quantity`返回的buy，避免两套滑点算式和变相阈值；等号通过，原价精确比较，不加epsilon。

“u intent和预算不动”须解释为**候选与算法固定**，不能要求未来所有日期的实际数字等同A：

1. 同一D批，C已经冻结的每个intent分配/qty_cap不因另一个取消而重新scale、换约或补单。被取消者D_qty=0，原would-enter qty、报价、u_close和取消理由可留审计，不把当批未用额度重新塞给其他intent。
2. 取消后本就没有该持仓和手续费。未来u的权益、占用/空闲家族、margin与预算必须按C自己的账户状态自然演进。不能复制A未来预算或影子持仓，也不能永久冻结一份虚构风险；两种做法均变成另一个非自洽政策。

所以后续C的actual intents、数量和仓位可以不同，即使原156所有模型选择完全一样。政策对最终账户的影响也不止“少做被取消那几笔”，不得从A删除几条trades后累加当作C账户。

## 一次4新cash与原A复用的最小建议

这不是本阶段启动授权；root应先冻结唯一协议和实现。预算可保持0fit、同原157两起点×base/stress四C账户，原157 A的准确已验收summary/daily/必要账本直接复用，0A重放。历史窗口/现金起点/结束日/原模型更新日期必须与A逐一相同；不趁机延长到新日线再把旧A当共同参照。

原157已有恢复native缓存、make_voluntary_signals、K边界、4账户循环、报告和固定比较门。可复用这些纯函数/冻结小投影，而不重建COMMON52/重训130/重选156。若借旧工具的`execute`会自动跑A，不能直接调用其金融入口；只复用定义，新增C适配器一次执行。实际后独立审查须核新gate、全部C账本/报价和预算路径、对照绑定、报告与结论，不重做旧基准全套价格/模型认证。

最少结果应包括：

- 四组C/A期末权益、总收益、最大DD、Sharpe、费用/滑点、闭合交易/胜率；主2020stress严格收益更高且DD更浅，其他三点沿原157不反向恶化，保留原配对252日块/2000draw固定indices和主CI门，不因新结果改统计方法。
- 全98/95候选域保留；原u模型选择相同；四场景pending中原状态、gate评估/pass/cancel/unknown、would-enter qty、实际qty与累计取消名义预算。避免把原本qty0/占用拒绝/旧unknown都算“价格上限有效拦截”。
- 未成交机会成本通过完整C−A账户路径体现；可列A中相同event的原贡献作为描述，需标注其A手数/预算路径，不叫C的可实现反事实利润。省手续费与错过赢家均保留，不用“取消=0”替代未知路径。
- 原年度/家族贡献、右尾与2026不完整年、实际风险/margin/exposure、open/stale/容量未知、财富正性及破产状态。不能只凭DD更小和交易更少称识别更优；少参与导致收益下降应按原严格目标失败。

不要求增加同参与率随机C、第三风险臂或重新做全部held模型；本问题是固定主政策现金效果，不是新增模型的跨家族学习证明。若选择不变或实际gate无支持，可据协议直接判无增量，不制造额外金融。

## 外部刷新与判断

- [CME官方期货订单类型](https://www.cmegroup.com/education/courses/futures-trading-mechanics-and-regulation/futures-order-types)区分最高购买价、限价可能不成交和market保护范围。判断：价格上限是独立执行动作，但牺牲成交机会；它不证明以昨收盘作上限有alpha，也不认证国内六所真实竞价成交。
- [QuantConnect官方市场单说明](https://www.quantconnect.com/docs/v2/writing-algorithms/trading-and-orders/order-types/market-orders)说明市价单对成交价格的不确定性。判断：不能把最终市场fill当成事前已知且可拒绝的实盘报价。
- [LEAN维护者FillModel源码](https://github.com/QuantConnect/Lean/blob/master/Common/Orders/Fills/FillModel.cs)可见报价时间、order.Time、新旧数据与滑点处理，限价另有触发/成交模型。判断：需区分订单在bar之前已存在与bar后观察再下单；开源fill假设不等于真实可成交。本轮没有复制外部引擎、安装依赖或运行示例。

## 变更、指标和反思

新增脚本/参数/模型/标签/回测结果 **0**；新增期末权益/总收益/DD/Sharpe/总滑点/交易数/胜率均 **N/A**。本阶段没有读取新候选收益，引用原157仅确认复用结构，不重跑现金。开始/结束均0fit/cash/SQL/行情下载/原大表读取，累计535/278及1旧partial不变。

开始新增收益后调参过拟合：**否**；历史同史择题风险：**是且高**。结束：仍**否**，本精确cap没有按新收益选gap阈值，但u.close作为锚本身是一个自由度。若失败，关闭此固定cap，不扫close±N/百分比/成本容忍/时间、改stop、重选月、补单或加注来救成绩。

开始继续价值：**有条件是**，它问新的执行动作，不再收集邻近新列。结束继续价值：**有条件是**，一次0fit/最多4新cash能在已声明open报价模型内反证完整收益/DD目标，成本小且可独立全审。真实成交资格、.25N损失上界或加注资格：**否，未证明**。不把条件GO写成已启动或已通过；root需冻结后唯一actual。完整目标保持active且未完成。

本唯一576stage不改LINE/registry、根总账、原accepted源、正式C9/生产/CTP/邮件/launchd或Git。历史研究不需等待今天日线。


## 577冻结协议的收益前定向核（2026-10-21 06:07 CST）

只读`outputs/stage577_open_execution_cap_protocol/protocol.json`一次，SHA256 `69b39cd7d330d267d73bd30a8479f05eac4dc6376687d125f69bcda5dc8ff48e`。未见重大合同、因果或对照问题：原A157四个自身账绑定、原固定窗口/2000个252日循环块indices、原模型和selected epoch u_close、完整98/95母体均明确；C未来按自身状态prepare，同D批不重分；原qty0/unknown状态优先，base/stress各自报价和参与差异披露，模型open成交时钟限制保留。机器容差至多tick×1e−9，仅浮点适配，不是经济cap偏移或另一个阈值。

**协议定向接受，尚未验收实现或actual结果。** 575源码ready后只需核隔离执行函数除新guard外与131逐项保持、未知/qty0优先、没有有效tick时容差不放大、取消D_qty归零且不enter、不换fill/stop/预算路径；有小而相关的等号/超价/滑点取整/原qty0/unknown合成检查即可。不新增旧全套测试、A回放或来源认证门。本次0fit/cash/SQL/大表，累计不变，原目标未完成。


## 575源码唯一收益前定向核（2026-10-21 06:15 CST）

已读575 kernel、7个小fixture源码、runner和source_ready1；不重跑fixture，不读大输入。独立用AST定位函数并从原文删除BEGIN/END575 guard，剩余`run_cash_account`与131逐字完全一致；`cap_accepts`是exact `<=`，没有使用协议允许的可选机器tol。新gate在原未知/占用/生命周期/stop合法性/qty0之后，在`ledger.enter`之前；用同次unit.buy的不利滑点和tick取整报价，拒绝D_qty=0、唯一原因、无fills。其余prepare、共同scale、D只减量、旧仓退出与未来C路径完全继承。

runner绑定四个accepted157自身账户，不使用157更早baseline；小A fills只取BUY身份重叠，不作反事实PnL。原signals与母7列/cache一次路径、原窗口/风险/K/2000固定indices、最多且恰4新账户，0fit/0A回放/0SQL均明确。四OWN映射、guard顺序和纯函数复用未发现重大问题，给root **GO：唯一actual可启动**。这只是实现收益前接受，不是金融结果或真实开盘成交资格。

三文件SHA：runner `d80c31df2f319c1d5f6b7409937b050bda05d237c674837607fd817a37d98586`；kernel `09ef1c6de31900006007f8bf83de906f317654bd3ed452c752814ec234f794e6`；test `88d42e8b3e9e53d118afe0b8d64fefb2e354eb69dcfce7e6e81fb200e53beb58`，与source_ready1一致。完整实际四本终态后再独立审全部新账，复用独立132/102/158框架，无旧A回放。


## 575实际结果与576独立全账终审（2026-10-21 06:23 CST）

### 实际尝试与小适配边界

575作者actual_run1在读首份157小manifest后、任何账户启动前失败，0started/0cash/0fit。真实schema仍为`stage157_voluntary_cash_v1`，只是既有已验收status是`completed_with_metadata_continuation`，最初代码只许`completed`。ready3仅将该状态白名单改为两种完整状态，独立反向替换后整runner SHA精确还原旧版，guard与其它金融逻辑不变。最终runner SHA `392672d8fd6ed12732f1eca692814dd450f6ca7a5161bdbfc5ecb78fd4ead5d4`；kernel/test不变，未重跑fixture。

root fresh actual_run2 session18121，exit0，3.984267秒，4started=4complete，0fit/SQL/GET/A回放。没有重复作者资金实验，失败0cash单独保留。累计由535fit/278完成cash改为 **535fit/282完成cash及1旧partial**。

### 独审范围、实现及透明恢复

复用独立132/102/158/500的现金数学、预算/原生/诊断框架，不导入575作者金融生成器。独立核全部新四本fills/reservations/daily/positions/closed/open/rejections/capacity/entryunknown；同epoch报价、原u close/N/low20、K、同D不重分、C未来自身预算、全部cap_audit、95家族零贡献网格、年度、尾部与sector/variant、原A OWN四曲线和BUY身份重叠、四组2000个固定bootstrap draw及原门。未重选156/重训130/重审旧52，0策略/0A回放/0SQL。

审查器run1 session91067在8.886861秒停于首本cap_audit比较：`set_index`移掉event_id列后仍按列读取，是审查器KeyError，0完整核心账户。root授权只改`drop=False`并fresh独审run2；原失败源/terminal保留，native110MB、母表7列、signals累计各2次读，不能写成全过程只读1次。

独审run2 session8150的四本核心账务/预算/原生/价格cap全部完成并保存四checkpoint；随后BUY参与表比较遇Categorical填空的审查器类型适配。进程`-i`仍保留RAM，按root授权仅cast object续元数据尾段，并只比较作者实际导出的paired fields（权益差由独审另推导留receipt，不要求原导出一个不存在列）。**没有第三次读取原大输入、没有重核四个核心账户、没有重跑策略/模型/A。** 此次尾段失败terminal/source亦保留，最终同handle exit0。run2每个所需源文件最多一次物理读取，全部派生重复调用来自RAM。

最终核心问题：**Critical0 / Important0 / Minor1**。Minor是同一可选summary字段`unknown_capacity_fills`四本未单列：独审从全capacity_audit验证真实计数，并核capacity_unknown_roots、entryunknown和execution_unknown等原标志；不是丢失未知路径，也不影响算术或否决，不要求作者修复或重跑。

终审核心4本、对照曲线4本，cap veto **953/761/384/341** 与作者一致；独审新标量断言计数198409（不含旧helper内部断言，绝非样本数）。native1552456行/9520epoch一次恢复于run2，全98目录产品/95家族399252母/161014前向母保留。原模型selected signals复用且对原生u字段逐一核对。新fit/cash/SQL/下载/A回放均0。

### 新C资金结果（研究报价模型）

| C账户 | 期末权益元 | 总收益 | 最大回撤 | Sharpe | 总滑点元 | 闭合交易 | 净胜率 | cap取消 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| primary_2020/base | 1,592,408.3920 | 59.240839% | -13.998160% | 0.777480 | 65,053.2737 | 716 | 14.944134% | 953 |
| primary_2020/stress | 1,421,955.1180 | 42.195512% | -14.910754% | 0.792839 | 89,632.2238 | 528 | 13.257576% | 761 |
| cold_2023/base | 1,637,474.1885 | 63.747419% | -6.079820% | 1.422460 | 30,541.0708 | 289 | 15.570934% | 384 |
| cold_2023/stress | 1,525,384.5850 | 52.538459% | -5.585914% | 1.507496 | 49,403.6252 | 247 | 15.384615% | 341 |

原A为157自身四账，费用已计入权益、滑点已在fill内，不重复扣除。取消仍存在错过盈利机会和未来资金/占仓反馈，完整C现金路径包含这些机会成本，不把A删除若干交易累加成C。

| C−A | 收益差pp | DD差pp（正为更浅） | 固定配对每日log均值95%CI |
| --- | ---: | ---: | --- |
| primary_2020/base | -63.686183 | +1.629259 | [-0.000382059337, -0.000035569111] |
| primary_2020/stress | -10.646459 | -3.551453 | [-0.000137582502, 0.000054139425] |
| cold_2023/base | -18.796237 | +3.822329 | [-0.000286887908, 0.000067399128] |
| cold_2023/stress | -0.126124 | +0.836848 | [-0.000097979238, 0.000101070346] |

**接受算术，否决固定cap政策。** 四组收益全部低于A；主2020stress回撤还加深3.551453pp，原严格收益和DD门均false；主base CI全负，其余三CI含0，主stress CI下界不大于0。四C本身仍正收益、财富为正，不足以支持“高质量识别更强”。少做交易/省部分费滑未补偿错过机会及组合路径变化。

原历史stale、entry/capacity未知保留，financial_unknown=true。否决不只是未知造成：已知名义收益/DD必要门已经失败。open+不利slip仍为研究成交情景，不是真实开盘前后BBO/队列或窄止损损失上界；不晋级、不加注、不宣称跨品种新模型泛化或目标完成。

### 收据与最终决定

- 小摘要：`outputs/stage576_open_cap_independent_review/actual_run2/acceptance_summary.json`，14658B，SHA `69c68265b8cce754184471054a035aa1e39341328fa32ee42d24021fe6ba4e9e`。
- 完整receipt：同目录`review_receipt.json`，31763B，SHA `0a02092f101524128a769786015b79b4bf1bef2519ca0df3954fa43799ec8c6a`；terminal与四checkpoint、两次字段适配现场另存。最终审查器源及同RAM元数据恢复指令一并存本审计目录，未复制大源。
- 固定577 gate：status=`unsupported`，cash_nominal_pass=false、nominal_pass=false；own_returns_positive_all_four=true；return_gate=false、drawdown_gate=false、primary_daily_log_CI_lower_positive=false。

结束新增按新收益调参过拟合：**否**，没有改cap/止损/风险/模型，只修审查器读字段。历史多轮适应性择题风险仍**是且高**。继续这个精确cap：**否，失败关闭**，不改成raw open、不翻符号、不扫close±ATR/百分比/容忍或换产品/窗口救参。继续完整全98/95高质量long目标：**是但未达成**；本stage不制造下一提案。历史研究无需今天日线，只有原独立前向账户结算需完整收盘事实。

本轮不改LINE/registry/根总账/正式C9/CTP/生产/邮件/调度/Git。实际更新记录与最终结案由root578统一办理；本576接受算术而不接受alpha，先前有条件GO只是允许一次有限反证，现已由实测关闭。
