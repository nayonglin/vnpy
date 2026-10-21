# Stage318：单一纯52研究参考的最小前瞻观察合同建议

- 时间：2026-10-20 02:46（Asia/Shanghai）；line_id=`futures_full_market_long_signal_ai`；独立设计建议，非重要收益突破，尚未冻结或实施。
- 先读registry、316及[317盘点](20261020_0246_stage317_forward_minimum_dependency_inventory.md)与[317小refs](20261020_0246_stage317_forward_minimum_dependency_refs.json)。refs本次读取20361B，SHA256 `5bc49a11fdf6e1873ac575f6a7f2d9766cf9632c185d50796d9144b8b08e3cf4`；模型/旧源码身份继承317，没有再次打开模型、旧大表或行情。
- 本阶段只新增本文：0实现、0数据获取、0fit/cash/SQL、0旧suite；外部只读下列2个官方/维护者页面，无安装、clone或行情下载。不改变315失败结论、LINE、registry或任何策略代码。累计完整453fit/246cash不变，315另记的started1/completed0不改。

**判断：有条件GO一个最小、无事后标签的新日生成与研究观察接线；当前尚非未来生成器ready。** 已有模型/scaler足够，不需要重训。真正缺项是新日接收与完成时钟、无label的纯u适配、未来日历/元数据、连续paper own-state。下一任务可只做这些薄接线与3组tiny；本文不执行它们、不安装调度、不使用真实资本，也不重新开放已关闭的信号、risk或solver包。

## 1. 唯一参考及最小身份闭包

只固定已有纯COMMON52最新`main/2023-01-01`、156全域同K选择、157信号语义与原070/131 NARROW预算。它是历史研究后选定的观察载体，不是已晋级赢家；不新增特征、臂、阈值、权重、cutoff、成本或分配算法，不使用held模型部署，不引入312整数算子。

| 必须一次绑定的对象 | 本合同的具体要求 |
| --- | --- |
| portable模型 | 本线`outputs/stage130_contract_choice_fit/actual_run1/folds/main/2023-01-01/portable_model.json`，2787B，SHA `a9d3e60d70d3b0d30be3bcee49074131ef1be0ae1660dff3bbaa1bb1217330a4`；52coef及原intercept，不重训。 |
| scaler与列序 | 同目录`scaler.json`，4680B，SHA `130ddae5588b257097a0e91fa7bceba1c86ae049cbab5849140369443fd47932`。原26数值按原mean/scale变换，非有限位置置0，再追加原26 missing flags；严格沿原52列序，`score=z·coef+intercept`，不滚动居中、不对未来fit。 |
| 因果特征/母体 | 继承317所列004母anchor、129 own11/maturity13/最后2列、042 Wilder状态及原资格语义。own11含u的21连续有效bar/SMA20TR，与N的20TR seed后Wilder递推不同；必须续原N/run/last close及窗口，不能只拿21bar重播N。mother最大正V、OI并列和epoch规则、普通/_F隔离保留。 |
| 选择/执行 | 原156 eligibility、有限正score、D<K在argmax前、tie及family规则；原157边界语义、070/131费用/预算/退出与D只减量、不回收重分。旧129 action_stream调用simulate_action，旧157历史join/4365缓存均不能作未来入口。 |
| 当时的输入 | 新日原件/规范化输入的source、版本/内容身份、first_seen/received_at、完成判据、交易日与session日历；实际使用的catalog、lifecycle、单位/质量、tick/lot/multiplier/fee/margin及经济映射版本；历史warmup/递推seed的身份。 |
| 运行闭包 | 新薄适配器及实际调用的纯函数/资金核源码身份、配置、实际Python/NumPy等依赖版本、初始与连续状态身份。复用317继承的263/279接受边界，不重做94依赖盘点。portable算术不要求恢复训练CSV/Y、旧scores、六fold或unpickle joblib。 |

root后续用同一份冻结记录绑定上述对象及下述T0/操作时点即可，不另建资格审批框架。若接线仍必须读取未来label、调用fit或跑历史CLI，便未完成这里的最小任务；本合同不以模型小文件齐全冒称端到端已完成。

## 2. T0、真正forward与迟到

`T0`是root最终绑定合同、生成器代码、输入路径与初始化状态的不可变真实时点，不是318写稿时点，也不是旧cache末日。保留时区与UTC。只有真实源交易日u完成时刻严格晚于T0才进入forward观察域；u完成时刻未知就保留`completion_clock_unknown`，不能只凭文件名日期授予forward。

已发生但晚取的2026-10-19始终是历史补档；不能因本机cache止于10月16日而称其为forward。10月20日也仅在其真实完成晚于T0时才可能成为首个u，不在本文承诺当前已收到或已确认日历。冻结前历史可在后续授权后用于因果warmup，永不计作前瞻收益样本。

forward观察域与及时可决策域分别记录：每个u完整记覆盖/缺失；只有所需输入真实收到、u确已完成、D已确认，且decision在该品种D实际首开之前封存，才有及时的forward决策。D指下一个源交易session，不是自然日加一；夜盘归属和日盘首开按冻结日历处理。**迟于D首开的接收或计算记`no_forward_decision/late_input`，不补发D、不回填成当时已知，也不静默删去这个失败日。** 冻结时须写明各会话的操作deadline，不能事后挑一个尚未开盘的窗口。

最少同时记录`source_trading_date、source_completed_at/判据、received_at、source/version、decision_sealed_at、D及其open/deadline`。first_seen是这条接收路径可证明的最早接收时间，不冒充厂商/交易所首次发布日期；发布vintage未知如实保留，不等待无限历史PIT工程才允许有限观察。输入修订另存版本；既往决策引用的原件、特征、score和状态不被新版本静默覆盖。

K_target仍是交割前月1日，K才是其后首个源交易日。精确K pending但真实D已知且`D_date<K_target`时，原156已经能证明D<K，必须保留这个分支，不新增“所有K先落日历”的严门。不能证明的情况沿原pending/unknown/blocked，不拿未来收到的calendar回补过去known。

## 3. 完整域和最少每日记录

98既有产品/95family是固定接受母域，不是未来永久全市场。每个规定u保留全部98父观察与当时可见真实月份：无交易、无正分、未选择、无报价、窗口不足、资格不满足和unknown均有行。按当时catalog另记新上市/新family/新epoch的first_seen与`unsupported/economics_unknown`，不能默默drop、用邻月代理或臆造旧别名。对它们先报告覆盖缺口，不擅自扩输入/模型；报告同时列固定98覆盖和所知市场目录缺口，不能把98/98写成未来全市场100%。

最少保留一条可串起证据的记录链，无需新观察系统：

1. **输入/观察**：u、product/family、原anchor与各真月身份，引用所用版本，原资格/缺失、26raw/52设计或可重建的紧凑特征状态、固定模型score、全池选择结果及原因。禁止只存入选与成交者；不先读`trade_label_known`或事后退出筛机会。
2. **decision/intent**：sealed时间、selected/no_trade/取消/pending原因、D/K_target/K状态、实际参与预算与初始止损、引用该场景自己的E/F0/margin和上一个状态身份。未知与已知不参与分开，unknown不填成收益0。
3. **后续账**：D实际行情到达后，才按原日线核将pending更新为研究假设成交/取消/执行unknown；保留行情接收时间，不把后来算得的成交说成当时已经看到报价。按原规则连续记录open、退出、费用滑点、标记缺失/延期及K；只有实际退出且所需价费可知才给成熟的政策收益。日线内顺序和真实可成交性仍是原研究假设，不是订单回执。

记录可追加更正并指向原件，不能重写既往决定后仍自称同一条原始forward路径。仅保存快照/receipt与所用输入，不在本阶段建数据库、恢复系统或新站点工程。

## 4. 一个政策、连续own-state、原风险成本

从T0后首个合法观察起点**一次空仓、100万研究初资**开始；不带入旧2020/2023路径已知的持仓/利润，不倒推补单。base和stress是同一政策的既有成本情景，各自独立连续权益/持仓/pending，不能共享另一情景的已知状态；不再复制历史双起点为新臂。

原单family风险0.0025、总risk0.02、margin cap0.25、buffer1.1、NARROW初始0.25N、原容量/费滑/报价/退出规则全保留。base/stress成本公式及经济映射沿317绑定的执行协议与原070/131，不重估或省略成本，不因账面盈利释放原F0、改止损、加注或救参。

每次保存现金、权益、持仓qty/原entry risk/F0、mark/费用、pending/D/K和递推特征状态，下一u从自己的前态推进。重启不得从100万重置、重复处理一个D，或为获得较好结果回放已知未来。旧历史run_cash_account自建空账本、受end限制，尚非这种滚动接口；连续状态接线是实际缺项。

缺行情沿原unknown/deferred语义保留；如果运行中断使状态本身无法确认，明确记录`state_continuity_unknown`和没有产生及时decision的区间，不能填成空仓、现金不动或零收益。必要的核对恢复不抹去缺口，也不由318授权重放旧完整现金。当前不声称未来费用、静态margin或日线假设等于实盘真值。

## 5. 固定复核时点与3组tiny上限建议

后续同一合同可预定：每周一12:00（上海）只核前周输入/时钟/覆盖/状态连续性；每月第一个周一12:00汇总前月完整观察与账；T0后第12个公历月同日12:00作固定年度盘点，月无同日取月末。root冻结时将规则写为明确时刻，不安装定时任务。信息未成熟照时报告unknown，不等收益变好再报告，也不因每周盈亏改参数、换品种、cutoff、停损、成本或重置账户。技术故障可如实停记并修复接线，保留缺口；不以故障为入口改变政策后接续同一绩效名义。

以上只是复核/报告日历，**不是“一年/几周/N笔就足以跨周期”的功效承诺或晋级门**。每次披露可及时决策日/缺失日、可用产品与月份、selected/取消/成交、closed/open/K未到/unknown、仓位与权益风险、费用滑点、净胜率、DD及净收益成熟范围。成交重叠、同日/family相关、尚未退出和跨期持续持仓均不能当独立样本数；短窗口Sharpe只作描述。一个参考政策无新对照，只能观察自身未来表现与操作可得性，不能证明AI相对增量、高质量已证、普遍alpha或实盘资格；旧历史选择偏差没有被洗掉。

后续实现至多先做这3组必要tiny，本318不运行：

- **时钟**：冻结前u晚取仍历史；冻结后但迟于D首开的输入不补决策；K pending且D<K_target可证明分支与不能证明分支均保留。
- **因果**：保持u及以前同一输入版本与完整peer pool，仅追加/改变u以后bar不得改变u特征/score/选择；原scaler不fit，Wilder续接不以21bar重播种，整个过程不需事后Y。
- **状态**：两个小相邻session拆开执行与一次推进一致，保存/恢复不重置或重复记账；pending、取消、缺失和原D不回收含一例即可。只检新接线，不重训或跑旧完整现金/suite。

## 6. 调研、GO缺项与反思

官方[scikit-learn common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html)要求新输入沿用训练时的变换，并避免用测试数据学习预处理。本文据此保留现有scaler与列序，不把部署期居中当无害维护。该网页版本不构成本地升级理由。

维护者[Freqtrade GitHub lookahead-analysis说明](https://github.com/freqtrade/freqtrade/blob/develop/docs/lookahead-analysis.md)指出全时段dataframe可能暴露未来，并比较切片前后输出，同时明确未触发信号与跨品种逻辑会限制诊断。本文只借其因果不变性原则设计tiny，验证时保留u时点peer pool；不运行其历史回测CLI，也不把检查通过等同中国期货alpha。外部核验仅此2页，不新增方法综述。

可执行的下一步只有：沿317小refs复用原固定52，抽出无label纯u薄入口，接当时可得的calendar/元数据与输入receipt，再做上述tiny和连续paper-state接线。缺项明确就是这几项；不需重新训练、恢复joblib或旧全动作、回放旧4控制，也不需正式C9 production/activation、CTP、邮件或调度。

开始与结束判断一致：本318没有新增结果搜索，新增过拟合操作为否；所观察政策的历史择题风险仍为是。继续这项有限准备有价值，因为下一批证据在冻结后产生且能核对实际输入时钟；继续同史换列、救solver或以短期盈亏选择下一版本没有本合同授权。当前只完成建议稿，不宣称生成器、输入接收、未来自动化或生产ready。新增/修改/删除模型及金融参数、回测结果均0；期末权益、收益、DD、Sharpe、滑点、交易次数和胜率全部N/A。用户全市场高质量long→小止损→加注目标仍未完成。
