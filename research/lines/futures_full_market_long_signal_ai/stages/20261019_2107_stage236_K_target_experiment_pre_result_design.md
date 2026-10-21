# Stage236：未读K数值前的纯目标实验科学设计建议

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-19 21:07 CST；非重要突破，非正式A/B或生产。
- 先核registry/LINE、230冻结合同、217/204及220小段gate；未读233任何actual产物、K数值、原actions、NPZ、六traincache或现金大表。新label/fit/cash/SQL/价格读取均0，累计433fit/234cash。
- 本稿是在结果前固定推荐门，不签发actual；root仍须在测量及独审接受后另冻最终protocol。完整用户goal仍active、未达成，不加注。

## 调研和判断

按本次有限范围，不再扩展外部搜索；沿231已实际核证的[SPO原文§2](https://arxiv.org/html/1710.08005v5)、[作者GitHub](https://github.com/paulgrigas/SmartPredictThenOptimize)、[CME订单说明](https://www.cmegroup.com/content/dam/cmegroup/education/files/a-traders-guide-to-futures.pdf)及[Dwork等数据复用原文](https://www.cs.toronto.edu/~toni/Papers/holdout-cacm.pdf)。判断不变：应先对齐明确政策payoff和评价对象；论文不证明要换学习器，同史预冻结也不恢复盲OOS。

**只有同C、同尺度可证时，才值得考虑一次6fit/最多4cash的纯Y替换反证；不值得把它扩成新的训练系统。** 目标不同不等于可预测，COMMON52无自身duration也不保证能学习差异。新增duration、模型、窗口、正分门或权重会破坏当前唯一轴，均不带入。

## 两个必须同时保留的比较

| 比较 | 固定控制 | 可识别问题及通过要求 |
| --- | --- | --- |
| 纯target主比较 | 218 DOMAIN52原Y的6模型/完整score/choices，219四本K现金 | 同S/52/scaler/精确权重/模型/部署政策，仅把Y换成Y_K，是否改善；必须通过下述全部门 |
| 用户目标必要比较 | 130纯COMMON52/156同K选择及已接受heldK选择，157四本K现金 | 新候选是否优于原研究基准；只胜已失败DOMAIN52不足，必须同时通过相同门 |

新候选对218的变化可归于这个固定有限学习程序的target替换，不能据对157的变化单归因目标（157原训练域还不同）。两个比较不做结果后择优；原DOMAIN52关闭结论保持，只复用其已接受产物作必要控制。旧模型/score/choices/cash都只读复用，0重训、0重预测、0重选择、0旧现金重放；新的held payoff join不算重跑旧选择。

## 0fit资格门：共同训练域、clock及尺度

六fold仍为main/held0/held1×2020-01-01/2023-01-01；held family哈希、训练排除与前向测试归属沿原130/218，不能改family或截取收益好的时期。原T_f是130严格旧成熟域，原S_f=T_f∩156原D<K；218在S_f上使用旧权重乘W/W_A。

逐fold证明`C_f=M_f(Y_0)∩M_f(Y_K_stress)∩A=S_f`，全部identity、原成熟clock和新stress finite/known/phase相符；K前copy或K重算均须`tK<=t0<cutoff`。231条件定理及230全原closed primary通过，只是支持子集论证的证据，不能替代六fold实际身份核对。任一S_f行新stress unknown/非finite/clock不满足或C≠S：**0fit停止**，报告失败身份及原权重mass，不自动补控制训练、不删除失败行后复用218。

训练仍按原218旧成熟集合和cutoff严格时钟取行，不利用K提前成熟来扩大样本；原unknown_afterK682及open_K_reached62共744条潜在新known动作，即使测量后确已known，也只留在完整测量与前向评价，不加入训练。原closed但仅K在cutoff前成熟、原Y在cutoff后才成熟的行同样不加入。不能把“新值可早知”同时改成“候选额外学了新行”。

六原130 scaler坐标、52=26值+26missing、alpha=1、intercept=True、cholesky、同一精确218允许行权重向量及总loss mass全部固定。旧interval union/uniqueness/等u权重不重算，scaler不重估，不改R分母为2N/含费unit-risk；只将stress Y值替换为230严格Y_K。base不另训一套模型。

## 6fit后、现金前：完整预测、同K held门

六新模型各物理fit一次，保存portable参数/正规方程/身份与真实计数；不仿204新造一个系数符号门，因为本次无预声明新q方向。所有资格预检先于任一fit；fit错误保留终态，不以经济重跑修复自由度。完整前向身份沿既有1,933,480 child、main161,014母体与held0+held1合计161,014母体合同，缺失/nochild/不合资格均保留。

选择仍156完整池D<K→score>0→母内argmax→既定普通/F family优先，anchor/K/费用/容量及所有账户参数固定。held0/1分别在两个cutoff的部署区间评价：2020模型只对应2020≤u<2023；2023模型对应2023≤u≤2026-10-16。两family×两区间共4格，不把早期正值与后期负值合并救门；固定年度可披露但不另挑年份作决定。

**held的主评价必须是230 strict stress K payoff，不能沿旧first-exit R充当通过证据。** 对每个完整family-u身份，将候选选择与每个控制的既定K选择分别join到同一完整标签；不只取两边都成交/closed子集。无选择/已知政策不参与为policy0；不同选择任一strict未知则差值未知；同一action的差值恒为0，即使自身payoff未知也需单列披露，不能把该action本身Y填0。

每个控制的4格都要求：family-u内聚合再等u的已知增量均值严格>0、distinct unknown差值数量=0、存在有效日期支持；共8格全部通过。same-action未决、绝对known覆盖、取消/open/意向全量披露。base held可同口径报告一致性诊断，不另立训练目标或放宽stress门；旧原R held只作连续性诊断，不能覆盖同K失败。held不是账户cash，未来现金成功也不能覆盖held失败。

推荐现金前停止：任一同K held格失败/未知，关闭固定target包，0cash；若main完整action/selected/anchor向量与218或157任一必要控制完全相同，则无法胜过该控制的严格主收益门，0cash关闭。分数改变而动作不变不构成经济增量；不改阈值制造动作变化。

## 最多四新cash与固定收益/DD/pairedCI门

仅前述门全过才运行候选自己的四本资金：2020连续（2023按冻结cutoff换模型）及2023独立冷启动×base/stress，截至2026-10-16。100w、0.25N初损、单family风险0.25%、总风险2%、buffered margin25%/buffer1.1、1%容量、原费滑/tick/anchor/K/整数化不改。候选各自现金递推，不能用独立R累加或匹配成交替代。

对219与157分别用同一候选四本日账进行比较，不增加新cash。每个控制均须：候选四本自身总收益>0；2020stress收益严格更高且DD严格更浅；其余三本收益/DD不劣；全部四个配对日log收益差的95%CI下界严格>0。两控制合计8个CI均过，不取最佳成本/起点/控制。DD沿负数口径比较，差值>0表示变浅；不得把回撤增加写成改善。

CI直接复用原070已接受252日块、2000次的固定bootstrap indices和同日对齐定义，不换block/seed/百分位或重抽更有利索引。一个候选日账与两个旧控制各算一次配对，0旧现金重放。所有日权益有限且>0、无破产，日历不缺行/丢弱日；置信区间只是同史条件描述，不是累计433fit后的盲测证明。Sharpe、胜率、交易/滑点和年度归因完整报告，但不得替代收益/DD/CI硬门。

## 未知门不可在结果后松动

沿220原gate分开报告`cash_nominal_pass`（上述算术比较）与`strict_unknown_clear`：候选及两个控制的四本任一历史stale、execution/capacity未知、entry execution未知、非有限DD或未识别财富均使严格资格失败；不同路径的未知不能因同日同时出现而抵消，不删这些日、不改成0、不以期末stale=0覆盖历史。

原157/219已经有历史stale/执行未知限制，因此本实验不能预承诺取得严格执行资格；这一点在看新K数值前写明。即使cash_nominal和held门全过，也只能报告“固定target在研究理想账本中的有限比较支持，严格执行资格未过”，不能宣布稳定超高质量、穿越周期、窄损封顶或加注可行。若root只接受能立即取得完整资格的工作，这些既有未知已经足以在6fit前停止；若root选择有限对象反证，应显式承担这个限制，不能跑后改门让它通过。

## 与204/217的关系、预算及停止

217只改变loss域、原Y不变，本提案只在其固定S上换Y；不能把先后两个失败包组合成隐式新搜索。204的q系数方向门是特定假说所需，本次不照搬；204/217原R held曾明言不是K目标，本次必须改成同K held才对齐问题，这是结果前的评价合同修正，不是看到held失败后救门。

预算上限6新fit、最多4新cash；无动作或held失败0cash，资格失败0fit。0新特征、0新label（只读已独审230/233标签）、0旧模型/score/choices/cash重算、0SQL/下载/新价/新分钟；必要输入仅按新最终协议一次读取，不为证据清单重复旧工程。若全部运行，累计最多439fit/238cash；这里只是预算，当前仍433/234。

未来实际仍须另一个独立agent全面审查新六模型身份/数学、全新score/selection/同K held、各新现金/费滑/预算/持仓/unknown/双控制CI与gate、bug及置信度；旧已接受源/控制算术继承，不为独审重训或重放。独审失败不签完成；只在最终protocol、精确源绑定和root授权后单次actual，本稿不代替这些步骤。

任一资格/held/任一控制现金收益-DD-CI/未知门失败，结案关闭固定Y_K/COMMON52/Ridge/K包；不换K、duration、clock、weights/scaler、family/年份、alpha/模型、stop/risk/阈值救参。不借“target更正确”豁免盈利失败；全部名义门通过也须真正未见证据、多周期及执行验证，非生产、不晋级、不加注。

## 记录与前后反思

- 新增仅本唯一Stage236建议稿；代码/参数/历史结果修改删除均0；不改231、LINE、registry、根账本、其他线、生产或Git。期末权益/收益/DD/Sharpe/滑点/交易/胜率均N/A，无新实际回测。
- 开始/结束过拟合风险：**是**；新K数值未读，但目标择题来自反复历史研究。单项冻结只能限制后续自由度；同C成功、K差异或本稿更严格都不增加alpha置信度。
- 开始/结束继续这份结果前设计价值：**是**，防止看完数值再选held目标/控制/门。继续一次纯target实验价值：**有条件的是**，以同C与研究未知限制先验接受为前提；直接自动6fit/4cash：**否**。根目标仍active，超高质量识别、窄损可靠性、加注资格均未完成。
