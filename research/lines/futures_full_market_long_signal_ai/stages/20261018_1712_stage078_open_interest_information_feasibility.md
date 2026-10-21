# Stage078：真实合约日终OI能否增加参与风险观测

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-18 17:12 CST。
- 工作区/分支：`/Users/mac/Desktop/fian`；`codex/ai-training-data-expansion`。
- 阶段性质：独立、只读、后继信息可行性反证；不阻断075支持审计，不实施新实验。
- 重要突破：否。没有alpha、策略候选或金融成绩；不触发正式版本A/B或晋级。
- 开始过拟合判断：**本次不新增按收益择参；历史选择风险存在。** OI题目由派工先固定，再查资料/代码；不能把已有多轮研究当首次外生假设。开始继续价值：**是，仅限查清信息差与旧否决边界**，不据教科书确认口诀直接训练或加风险。

## 唯一结论

**有条件保留一个信息问题：真实同epoch的净未平仓合约变化，相对当日成交活动的比例，是否在共同26列之外含有可泛化的做多质量信息。只建议一个标量和两个臂的最小比较；本阶段不授权、不实现、不跑比较。**

理由分两层：close OI及其变化在本线common26中确实没有被学习器消费，且本机已接受源可提供这一观测；但它不是仓库从未研究过的新数据通道。旧线已经多次否决“顺势价格必须被OI扩张确认”、OI收缩必差以及OI据此放大/恢复风险。不得借新名字、63改1、换分母或扩大到全市场，宣称这些旧确认规则复活。本次保留的范围仅是**不预设OI正负有利、不乘价格、不写扩张阈值的条件信息检验**；不是对旧OI确认交易规则再试一次。

此次有界检索**未发现同一个全399252机会/common26控制/真实epoch日终净变化连续标量/成熟跨日经济目标的完整对照已被做过并否决**。这不是穷尽全仓库的不存在证明，更不是预测它会成功。若后续找到同目标同信息对照的停止证据，应直接撤回本问题，不能再换OI变换。

## 阅读范围与暴露说明

按AGENTS先读registry和本线LINE，二者嵌入了近期阶段的汇总，因此**不能声称严格收益盲**。OI选题在派工时已固定，本文不引用近期收益选公式、滞后、方向或参数。未直接打开070/071/072实际模型、预测、标签或现金产物，未打开073收益/decision产物，也未打开076预算审计产物。

另有一处过程失误必须留痕：跨线`rg`曾先搜索`research/lines/*/stages/*.md`，再在输出管道中过滤禁读阶段/本线；进程可能扫描过这些stage文档，虽然没有向本agent显示其匹配文本。故同样不能声称严格路径盲。后续改为精确白名单读取，没有依据这些文档成绩选择本问题。该限制不影响下述common26源码、源单位合同和旧OI机制边界的可核事实，但削弱任何“完全独立于既有结果”的表述。

本阶段实际操作为网页/维护者GitHub源码读取，以及既有小文档、schema、manifest和相关旧stage/code片段读取。新SQL、fit、cash、label、行情下载、全库hash、H5全键扫描、分钟读取、源重建均**0**。未改LINE、registry、其他线、旧记录、正式版或生产。

## 一手资料：支持新增观测，不支持方向圣杯

1. [CME Open Interest](https://www.cmegroup.com/education/lessons/open-interest)区分交易活动量与日末未平仓合约存量，也介绍用OI辅助判断趋势。其“资金流入”教学比喻不能直接成为本研究变量名；[CME量仓定义](https://www.cmegroup.com/trading/about-volume.html)明确每张合约同时有买方和卖方、OI只数一边。**判断：OI增加是未平仓匹配风险增加，不是市场净多、不证明买方身份或资金净流入。**
2. [CFTC COT解释](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ExplanatoryNotes/index.htm)明确全体long OI等于全体short OI，并另外区分参与者分类、跨期spread和集中度。**强反证：总OI本身无法恢复是谁在承担风险，也不能从增仓判定新增多头比新增空头更多。** 本阶段不引入COT或国内会员数据。
3. [Hong–Yogo论文入口](https://www.nber.org/papers/w16712)及[原发表期刊页面](https://www.sciencedirect.com/science/article/pii/S0304405X12000657)的本次检索可读摘要支持：存在套保需求等条件时，OI可能含价格未充分表达的经济信息。期刊检索文本讨论的是聚合市场兴趣和较长周期回报；**不能外推为中国单合约日级高质量long、窄损或低DD证据**。NBER正文/PDF及期刊直接open均403，本文没有假称本次读完/复核论文正文、数据或回归。
4. [INE 2019官方口径问答](https://www.ine.com.cn/eng/circularnews/news/201910/t20191029_820252.html)的官方检索内容说明2020-01-01改单边；直接open遇WAF。制度变化不是每个vendor历史文件已统一的证明，必须服从本机固定文件的校准合同。
5. 实际读取维护者[shinnytech/tqsdk-python的api.py](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)：`get_kline_serial`/历史K线说明分别把`open_oi`定义为K线起点持仓、`close_oi`定义为终点持仓；与[官方字段文档](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)一致。另读取[RiceQuant维护者api_rqdatac.py](https://github.com/ricequant/rqalpha/blob/master/rqalpha/apis/api_rqdatac.py)，其主力规则使用收盘持仓、次日生效；主连换月是显式身份变化，不能差分拼接的主连OI。本次只读参考，没有下载运行第三方代码。

整体判断：OI是一种存续风险数量观测，经济上值得检验；“涨价增仓=好趋势”远比原始观测更强，既没有由会计恒等式推出，也已受本仓反例反证。Polanyi式经验直觉可以提示“相同涨幅可能来自新增对手风险，也可能来自平仓挤压”，但总OI不能把两者唯一识别；直觉必须转成有限可失败的问题。

## 相对common26是否真有信息差

实际核对`tools/stage053_maturity_information_fit.py:35–41,169–206`：模型明确从`frame[COMMON]`构造输入，26列如下，不含`close_oi/open_oi/open_interest`或其变化：

|组|完整列名|
|---|---|
|自身11|`r1_atr,r5_atr,r20_atr,body_atr,range_atr,close_location,gap_atr,compression5_20,log_volume_ratio20,breakout20_atr,atr_pct`|
|期限控制13|`normalizer,peer_count,tenor_span_years,return_mean,return_std,return_min,return_max,front_next_basis_u,front_next_basis_prev,front_next_tenor_span_years,q_missing,front_next_missing,normalizer_missing`|
|经济距离2|`stress_u_cost_R,low20_distance_R`|

其余26 missing列与独立`q`槽不改变这个事实。期限q是同品种跨月份价格变化的排列关系，不观测未平仓合约数量。未打开053模型或预测产物。

实际核对`tools/stage004_product_day_opportunities.py:166–181`：OI只在**u成交量相同**时以非负closeOI降序、随后epoch字典序选参考；选出的OI列也被保存。它确实参与了母体代表身份的选择，故不能声称本线“从未接触OI”；但**持有一列或用作tie-breaker不等于模型已消费其数值/历史变化**。新问题必须保留004原代表、event_id和完整母体，不改变选约规则争取成绩。

形式反例说明信息差：同样的价格路径、成交量100和期初OI100，可能有90笔双开/10笔双平，末OI180；也可能10笔双开/90笔双平，末OI20。两条路径可有相同OHLCV、期限价格控制，但净未平仓变化相反。因而无法从common26唯一重建OI；这只是信息不可恢复的说明，不是预测收益证明。

必须与以下方向区分：

- Force Index的常见价差×成交量是交易活动与价格的组合；它不能恢复交易后剩余多少匹配合约。简单ER是价格净位移与路径总波动的比，同样不含OI。它们可能是OHLCV的不同压缩，不能被改名为新增风险存续观测。
- Top20净仓/净变化是部分会员long与short的差，不是全市场OI。旧Stage081的否决与当前会员缓存缺失都保留，本文不重启它，也不把OI当会员身份替代品。
- 跨月份期限q是价格关系；同epochOI变化不需要>=3个peer，不以q可得或月Top10/19产品筛母体。但只看一个合约仍可能主要观察到换月迁移，不能据“不是q”就认定是独立alpha。

## 旧否决究竟覆盖什么

本次读取下列旧stage及必要源码片段，没有重算旧资金曲线：

|旧证据|实际信息与目标|保留的否决；与本问题的边界|
|---|---|---|
|`futures_trend_drawdown30_preserve_return` Stage125|逐合约汇总的产品总OI；63日价格动量由63日总OI增长确认，周频best1/top3 overlay|不升候选，停止窗口/阈值/topN/频率救援。它已试过OI趋势确认，不能称全新；不是common26下真实epoch日级连续信息的条件检验。|
|`futures_trend_c9_minrisk_highquality` Stage061|19产品synthetic总OI、63日价格/OI符号、官方闭合lots的乐观跳过上界|“顺势但OI收缩即低质量”被反证；收缩桶也承载右尾。不允许把本问题变成同一跳过/削仓规则。|
|同线Stage253/254|官方timestamp-ready订单、入场前60根closed 1m的价格/OI四象限，再审收缩反例|扩张确认与收缩交易化均被阻断；源ready不等于有低风险优势。这是最强机制反证，但不是当前日级全市场机会/common26对照；本文不再读分钟。|
|`futures_trend_rebuilt_c9_15w_optimization` Stage038/062/068|已有`oi_price_confirm_passed/oi_confirmed`、AI/account组合与确认单最多1手的真实预算cap|确认特征/反向预算并无稳定晋级资格，停止OI阈值/手数救援。不能把OI当恢复仓位、窄损加注的许可。|
|重建二期Stage029/043|已失败路线资格/失败谱系|禁止本地旧字段相邻参数救援；该停止证据不能被新线名抹去。|

因此，**旧“价格×OI确认”的交易机制应继续停止**。当前尚未被完整否决的是更弱的条件信息命题：不规定OI增减与long质量的单调关系，只看真实epoch净风险存续比例是否增加训练外信息。不能说旧结果已经证明所有OI无效，也不能靠目标换成全市场就忽略旧结果。旧负证据使本问题的先验置信度偏低，最多值得一次最小反证，不值得建立OI变换库。

## 现成源小盘点与不可越过的边界

只读`stage266_clean_daily/README.md`、`dataset_manifest.json`（4965B）、`unit_contract.json`（6280B）、Stage266单位/reader/最终验收文档，以及本线既有`stage002_full_market_input_inventory/input_inventory.json`（21444B）。schema来自已接受Stage002记录与清洗器声明；**本阶段没有打开SQLite连接、CSV逐合约集合或H5**。

- 既有manifest记载1,552,456真实成交合约日、9,520 epochs、97有观察历史产品；本线004保持98目录代码的399252产品日母体。这里复用接受事实，没有本次重核全库。
- 已保存`close_oi,open_oi,open_interest,source_id,source_locator,volume_factor,oi_factor,native_volume,native_close_oi,native_open_oi,open_oi_status,quality_status`。既有Stage002 aggregate记载缺closeOI=0、`open_interest!=close_oi`=0；不是本次新SQL结果。
- 单位合同仅绑定固定RQ H5/已枚举来源：RQ 2010—2019四商品所V/closeOI×0.5、2020+×1；CFFEX全目标期×1，GFEX自上市×1；old/recent TQ单边×1。官方必须有明确unit_regime，不能按年份猜；DCE年度包仍只交叉证据，不进入来源优先层。canonical已是单边手，消费时不能再除2。
- 767,710行缺真实openOI；`open_interest`是closeOI别名。不能宣称开盘OI全史存在，不能把前收移位冒充当天开盘OI，也不能计算`closeOI/openOI`再把这些行删出母体。
- 来源整行选择且已隔离量仓冲突2,294键、价格冲突304键；不能为新OI问题补源、择优拼字段、撤销隔离或重建源工程。单位批准只覆盖固定文件，不是任意vendor保证。
- 既有验收是固定来源内准确性，不是当年首次发布/修订与broker真值证明；单纯多滞后一天也不能把归档重建升级为严格PIT。期末OI可能受交割、到期、结算/更正等影响，跨收盘差不自动等于盘内交易产生的净增仓。

## 唯一标量与最小可证伪比较建议

只提出**净未平仓存续率**一个标量，名称只描述数量：

`x(u) = [close_oi(e,t) − close_oi(e,t−1)] / volume(e,t)`

其中`e=004原reference_epoch(u)`，`t`是u之前一个**完整源交易日**，`t−1`再前一完整源交易日，按冻结source-calendar而非自然日减1。采用一完整源日滞后是处理日终发布时钟的保守研究约定，不由收益选择。这里“因果”只指输入在决策前可得的时间顺序，**不声称ΔOI是价格或收益的因果处理效应**。

这不是`price×volume`、63日动量确认或OI增长排名；不乘价格，不反转符号，不声明x越大越好。价格/波动/期限背景由同一common26提供，问题是这些已知条件之外x是否还能改变未来成熟经济目标的预测。它与旧研究共享OI原始通道，归一化本身不是新外部数据；价值只能来自此前没有检验过的具体观测与条件问题，不能由新命名获得。

若未来另行授权，先固定以下语义，不能边看结果边修：

1. `e,t,t−1`必须是同一完整YYYYMM真实epoch，不能用前一天的代表合约替代e；允许查询e尚不是代表时的已有真实历史。换代表不跨合约差分，普通/F不拼；不会以全生命周期或未来主力重选。
2. 两个lag日均须连续、accepted、OI有限非负，分母V有限且>0；同source_id最直接可比，来源/时钟/单位转换不一致且无既有接受证据则x为unknown。缺日、首bar、未知来源保留明确原因；不carry、不造0、不用真openOI缺失作拒绝。以当前两源日暖机，不再加63/120日门槛或借tail凑齐日历。
3. 当OI相等时x=0是合法观察；两日OI同为0也不自动改missing。不得宣称`|ΔOI|≤V`普适成立，不为超界值截尾/缩放或用量仓恒等式补值；非交易调整、来源可比性未知应显式保留限制，不能暗改数量。
4. 所有399252母体及既有经济/历史资格均保留，x未知用共享missing状态；不要求98目录产品或所有family每期都有x才能保留母体，不缩回月Top10/19品种。缺失不能变成“拒绝交易”硬门。

**最小比较只有两臂**：共同26列+共享x-missing+预留零槽，与共同26列+同一missing+x槽；同一固定小学习器、成熟时钟、训练内权重、数据切分和一个预先冻结母政策。不得再同时加OI水平、log增长、rolling窗口、price交互、四象限、多个denominator或额外止损政策。若学习器不能检验所声称的条件关系，应在收益前说明其实际检验范围，不能失败后加容量。

比较必须评估训练外年份与family、共同可观察机会、同一成本/整数资金约束下的配对净收益/DD及未知敞口，不能只报选中标签均值、训练拟合或总体相关。持续更高收益与更低DD、窄损生存仍是完整目标；不能因x可计算就给窄损加注。新增结果后按AGENTS由独立agent全面审数据、逻辑、结果、置信度和bug。是否启动、最终冻结参数/预算和实际比较协议均留给root下一步；本文没有签发实施权限或扩矩阵。

若该唯一问题不支持训练外增量，**停止总OI日级变化这一个信息包**；不换1/5/20/63窗、符号、分母、阈值、品种/年份或更大模型救援，不先展开补源/分钟/会员采集。旧OI确认规则继续保持停止。

## 变更、指标与结束反思

新增仅本文和可选小`outputs/stage078_oi_feasibility/read_receipt.json`；代码、策略/模型新增/修改/删除参数、回测结果均无。上述x是尚未实施的定义建议，不是新增生产参数。数据区间、账户资金、成本参数没有新运行版本；期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均**N/A**。SQL/fit/cash/label/新行情下载/订单API均0。

结束过拟合判断：**本阶段没有新增按收益择参，但不是严格收益盲、不是无历史选择风险。** 已见的旧OI负证据约束结论；没有依据当前赢家/输家换公式。若只用63→1或换分母作为复活理由，就属于旧路线救援，应否决；本建议仅保留一次未见完整同目标对照的条件信息反证。

结束继续价值判断：**有，范围严格限于上述单一信息问题；补源、重启旧OI确认/风险恢复、建立多种OI特征扫描的价值为否。** 可计算与新观测都不是alpha，原目标仍为全市场高质量long、窄损与更低DD。本文不宣布目标完成、不晋级、不加注；常规只读可行性不追加根memory/back_log，不更新LINE/registry，交root统一合入。
