# Stage633：held0后段负贡献的同路径归因设计审查

- line_id：`futures_full_market_long_signal_ai`；2026-10-21 10:08 CST；非重要突破，唯一633方法文件，不改旧628、LINE/registry或策略。
- 已读registry/629小结与decision；定向核042报价/退出、130目标、129/233字段与分支，和632协调现有测量接口。没有读新大Y、native、score或模型，0fit/cash/SQL/行情GET/新标签/actual实现。财富指标全部N/A，累计551fit、290完成cash＋1旧partial不变。
- **判断：值得一次冻结后的0fit/0cash归因，但它只能定位现有理想价格模型内的账面来源，不足以识别唯一经济因果或批准新策略。** 原629门不改：main条件相对正、held0后段自身负、完整E净R未知。630尚未冻结，本633不授权实际。

## 先固定对象与权重，不能只盯反例

固定627已接受的E/m/原正分动作、K路径、stress费滑、END及unknown；不重选月/品种/F、不调sign/阈值、不重开DOMAIN、K-target、退出或执行限价包。每项仍同时列main/held0/held1、2020—22/2023+及2020—26全部年度。held0后段是触发审查的反例，不能变成唯一分析样本，更不能按品种、年份删除后重判629。

629的A_I是每u的`sum_I(m*Y)/nI`再完整源日历等权，不是已准入交易均值。全E的known/unknown、nI、空I日和原m均须保留；成本细节只需原m=1 union的同源字段，也能解释ownAI负，不必先测所有fallback成本。组件必须使用**同一批可识别动作、同一nI和同一日历权重**；否则拆出的量不能回加原A_I。仅有成本完整子集J时另列其覆盖和同权贡献，不悄悄重算nJ后称629原值；不能由J代表全I。明确无参与的原政策cancel0，各组件可为模型0；路径或字段未知不得补0。

## 一个主分解：只用原stress，同一action的同一K路径

设原始入场参考价F、该路径出口参考价X、相应不利填价f_in/f_out，乘数M；固定risk=`0.25*N*M`。逐动作：

`G_R = M*(X-F)/risk`

`Fee_R = (fee_in+fee_out)/risk`

`Slip_R = M*((f_in-F)+(X-f_out))/risk`

`Y_K,stress = G_R - Fee_R - Slip_R`。

验证原两端slippage字段与参考/填价之差、原净R及同action/epoch/entry/exit/K clocks一致。原不利填价已含滑点，**不能先算fill损益再减一次Slip_R**。原SL0沿F−.25N、20low边界和原规则；不换为actualfill基准，不换cash风险预算R作分母。

同一线性权重应用于G/Fee/Slip，才能形成A_I的精确账面恒等及跨era差的加法拆分。报告R贡献水平和恒等残差即可；避免把近零/负净贡献作分母给不稳定的“亏损百分之几归因”。它是模型内会计分解，未认证盘口冲击/真实券商手续费，更不代表降低假设成本就会获得可实现利润。

**不把base−stress当总成本。** 原129路径先求单一raw出口，再对各scenario报价；233 quote_K也共用同D/同K原始参考，因此在逐action确认参考价/退出路径/数量/known支持完全相同后，两景之差才可叫“模型增量费用滑点差”，base本身也含成本。现金base/stress有自己的预算、数量和持仓路径，二者收益相减不能用于这项分解。最小实验直接拆629原stress，不做费率/滑点敏感性网格。

## 现成字段的可行性与缺口

632与本633小源核实：233 `K_quote_evidence.csv.gz`只有约4.8MB，但只写quote_K；有raw F、native K.open、两端fill/fee/slip、risk、M/N和K clocks，能直接拆该分支。`copy_before_K`在233直接返回、不写这份evidence，所以不能把它当全部准入已知交易。

copy支路需129原action的F/X、entry/exit_reference与boundary、gross_R_reference、stress两端fill/fee/slip、旧net_R、risk/M/N和旧label clocks；129小源确认字段存在。若630选择完整ownAI归因，可另批准一次约334MB actions的顺序投影，只保留冻结m1 union所需字段，结合已接受627缓存和小quote evidence；不重造路径、不读native、不补标签。若不愿该一次I/O，只能先做quote子域或净R尾部类型描述，并明确不能完整解释held0自身负，不能用少数quote交易代表其余copy。当前未读这些载荷。

## 跳空左尾：区分事件贡献和可识别越界差

先按原exit_reason/阶段报告：同日entry-stop、后续gap_stop、stop_boundary、force/lifecycle、K_deadline，以及未知；逐组使用同权净/毛/成本贡献，不删除尾部。净R低于−1可能只是费滑，不能直接叫gap；原`gap_stop`标签也只是日bar模型内的开盘越界，不证明盘中连续成交或真实止损队列。

仅copy_before_K且原gap_stop、已知此前冻结边界B与该raw出口X时，可报模型边界越过量`max(B-X,0)/(.25*N)`；代数上gross参考路径可拆`(B-F)/(.25*N) - (B-X)/(.25*N)`。但**entry_date==exit_date的entry-day gap_stop不是已有持仓隔夜跳空损失**，须单列，不能把新建边界的B−O一概当已持仓可避免损失。force优先分支也不能自动套gap_stop解释。

quote_K没有K之前的B，129最终exit_boundary可能发生在K之后，绝不能借未来边界填补；此处gap overshoot留未识别/不适用。若资料不足，原gap类型频次及深损贡献仍可报告，但它们不等于精确gap损失额，更不据此启用gap阈值、止损重试或不同退出。

## 绝对分数偏差必须分清目标

本633实际核130第61/146行：原52以成熟`closed_complete_bar_model`的**未加K net_R_stress**训练，不是Y_K。`Y_K-score`只能叫“当前K决策目标对旧分数的绝对偏差”，不能全归为原训练目标失准；取消0与原closed训练目标的支持差异也须明示。只在m1看误差，是被分数筛选后的条件误差，不是完整模型校准或新独立测试。

有同action原旧Y且旧known clock<=END时，在同一配对子集、同权重上用恒等：

`Y_K-score = (Y_old-score) + (Y_K-Y_old)`。

分别标原目标偏差与退出政策目标变化；旧Y未知不补0，不能借K后来变known反推旧Y。当m1的G已负，说明理想raw路径本身不利；当G正而费用滑点使净值负，说明原模型成本可翻负；大的gap类型负贡献仅定位模型事件；原目标偏差负或K变化负可以同时存在。四类机制并非互斥，不能强迫只选一个“根因”。本诊断不拟合截距、斜率/校准器、不按结果挑分数区间，更不重开已闭合K-target训练包。

## 对root拟冻结合同的明确方法GO

root已采用原nI/完整u权重、仅m1 union成本，一次129新字段流读＋小quote evidence；本633给**方法GO，等待630实际冻结，不是实际执行授权**。0native/新标签/fit/cash/新CI/新gate。资料缺项不阻塞整项解释，也不伪造完整归因：

- J为组件同路径完整的m1已知动作。保持原nI/日历，报告`L_m(G_J)-L_m(Fee_J)-L_m(Slip_J)+L_m(YK_{I\J})=A_I`；最后一项叫原已知净R的未归因贡献，不能洗成0或当成本。这里L_m是原`sum(m·x)/nI`再完整u等权。
- `S_I=L_m(score)`、总decision error=`A_I-S_I`。H为原Y与K-Y均已知且旧clock合格的桥域，保持相同权重：`L_m(Yold-score)_H + L_m(YK-Yold)_H + L_m(YK-score)_{I\H}`精确回加总误差。I\H另列，不宣称H是整体/无选择校准。
- entryday/后续copy gap分列；quoteK gap未知不拿未来B填。全部main/held、早后段、逐年同时输出；只做代数解释，不依结果改政策。

## 最小结果与反过拟合边界

最小输出是一张逐动作literal投影和一组全scope×era/year同权加法表：原A_I/unknown/已准入支持，G/Fee/Slip，原退出类型贡献，可识别gap越界子域，配对旧目标偏差/K变化及各自缺失数。表中所有归因域标清；0新模型、0现金、0成本/阈值网格。root已明确本轮0新CI/0新gate；只引用629已冻结区间，不追加重采样或seed。无需为了归因成立先要求它通过新金融成功门；只要求字段/路径/权重身份成立，错误阻断解释而非救结果。

调研本轮真实读取[Almgren–Chriss原期刊摘要](https://www.risk.net/journal-risk/2161150/optimal-execution-portfolio-transactions)（非全文），其市场冲击/波动风险取舍说明成本依赖执行路径，不能搬用来证明本线滑点真值；另读[Quantopian原pyfolio txn源码](https://raw.githubusercontent.com/quantopian/pyfolio/master/pyfolio/txn.py)的`adjust_returns_for_slippage`，它在既定交易额上施加附加成本，不是另一现金路径收益差的因果归因。该旧代码仅作方法参照，不声称当前维护、安装或应用其扫参。本文同路径恒等来自直接代数及本仓库字段核查，不复制外部收益结论。

开始/结束按新收益选参过拟合：否，当前只有解释设计；反复围绕失败例挑题的历史适应风险高。继续一次有界归因有价值，可以决定“还缺什么证据”，但不预签需优化哪项；继续直接训练/成本救参/按反例调门无价值。全市场98/95高质量long目标仍active，正式/生产/加注资格不变；历史归因不等今天日线。
