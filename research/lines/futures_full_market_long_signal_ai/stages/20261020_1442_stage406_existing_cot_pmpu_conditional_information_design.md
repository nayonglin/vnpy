# Stage406：既有COT中PMPU实物风险承接测量的有限后继判断

记录时间：2026-10-20 14:42 CST。line_id=`futures_full_market_long_signal_ai`。本阶段为只读提案，非重要突破；0原始数据下载、0实现、0fit、0cash、0SQL、0市场连接，不修改400、LINE、registry、其他线、正式C9或月池。累计仍454fits/246cash及原金融partial。

先读registry、本线LINE、129/130/320特征定义，后读root指定旧COT的014/256/048有限记录和相关评分代码。外部共3次定位调用，限CFTC官方资料及维护者GitHub；没有取得年包或读行情/标签/训练大表。按root已报告的402事实：141候选最终20周、13原周报、train12/held8，未过30/15底线；**固定weekly pods−leaves天气规格停止，不改变月份、日频、地图或阈值凑行**。不以397单例符号为本提案依据。

## 结论与新颖性的准确边界

**有限GO仅限一次年包复用/缺年补齐和真实发布例外面板准备；当前NO-GO任何金融实施。** 唯一保留问题是：美国实物商品Producer/Merchant/Processor/User（PMPU）的净卖出风险承接背景，在国内COMMON52、同源Managed Money净仓以及来源可用状态之外，是否还有成本后做多识别增量。

这**不是全新COT来源或全新字段**。旧重建线[Stage048](/Users/mac/Desktop/fian/research/lines/futures_trend_rebuilt_c9_15w_optimization/stages/20260701_2001_stage048_cftc_cot_mapping_audit.md)承接旧014/256，已否决`0.35*MM net_z+0.65*MM flow_z`的156周/最低52周C9条件排序包。048源码还计算`producer_net_oi`及`producer_net_z`并附到joined；但在此次限定核验的三条实际链中，最终评分与candidate条件只用MM，未见PMPU的独立条件增量测试。不能因只导出过就说PMPU已被金融证伪，也不能把其换符号叫新信息。此后若发现其已被同域实测关闭，应直接撤销本后继，不再改类别。

我先由本线去重选择PMPU，随后收到root的旧COT定位才收窄上述声明；这不是一个完全未接触历史反馈的盲假说。继续价值仅来自**不同参与者经济含义、完整机会母域及足量周频档案**，不来自天气样本失败后必须再找一个包。旧MM/NFC/FX等负证据使先验偏弱，源准备成功不算alpha进展。

## 为何不同于COMMON52，但必须控制MM

129 COMMON26是11项自身日线几何/量、13项同品种期限池摘要与缺失状态、成本及low20距离；52是这些数值加26个missing flag，没有参与者身份。LINE已关闭期限/局部曲率、EIA、国内会员类别、OI变化/月份池份额、FX、仓单、现货过滤、WASDE、旧序列/重开gap及数种目标/分配包，不能重新命名它们。

唯一拟测量为futures-only同报告市场的

`H=(Prod_Merc_Positions_Short_All−Prod_Merc_Positions_Long_All)/Open_Interest_All`。

保留合法0；OI非正、必要字段缺失、重复冲突为unknown，不fillna(0)，不沿旧156周zscore/截断/45日score。它不是资金净流入、逐笔套保量或“商业人士知道未来价格”。CFTC按实体主营业务分类，一家PMPU的仓位也可含投机；美国实体风险背景向中国价格传导只是待检验假说。[CFTC分类解释](https://www.cftc.gov/MarketReports/CommitmentsofTraders/DisaggregatedExplanatoryNotes/index.htm)

可识别反例是：国内价格、期限、成交和总OI不变，美国同一份未平仓合约的持有者由非PMPU转为PMPU，H改变，国内52不必变。但市场各类净仓相加为0，H也可能只镜像MM或其他类别。因此主对照必须有**原MM净仓/OI、相同source availability/age**；不能只拿纯52比H，再把守恒关系当新证据。不同时加入MM flow、swap、其他reportables、分位数或多个窗口来选优。

## 足量历史与非今日成分回看

[CFTC官方Historical Compressed](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm)列有按年的Disaggregated Futures Only原Text ZIP；不是付费终端/API-key方案。固定2010–2025全16年原包，2010留作披露/制度边界核对，主识别拟从2011起，避免把2006回溯分类当当年已发布。原档案覆盖与连续有效周数仍须实际计数；15年约780个持仓周是数量级预期，**不是已核780次及时发布或780个iid样本**。同周多市场、全98行或持仓月数不增加独立发布事件数；跨周仓位持续性也会降低有效样本。

原件保留全部历史market codes、原名称和所有行，包括后来退市/改名，不先按今天现存清单筛选。绑定用CFTC market code，名称改动不重新开始历史；代码/定义真变而无证据时unknown，不拼接。只作以下八个事前物理通道，不沿旧OI←soy oil、rb/hc←US HRC等替代关系扩映射：

| 中国产品 | CFTC code/实物参考 |
|---|---|
| SHFE.AU / SHFE.AG / SHFE.CU | 088691 Gold / 084691 Silver / 085692 Copper |
| DCE.M / DCE.Y / DCE.C | 026603 Soybean Meal / 007601 Soybean Oil / 002602 Corn |
| CZCE.CF / CZCE.SR | 033661 Cotton No.2 / 080732 Sugar No.11 |

原年包必须逐行印证这些code/物理定义，缺失留unknown，不按盈利改表。不同质量、关税、配额、汇率、区域基差及参与者结构都可能阻断传导；“同实物”不等于同一可交割合约或可套利价格。全部98产品95family及其历史母域仍保留，其他90产品为unmapped/原政策继承，**不能以8映射声称全市场成功**。H对同品种月份相同，主要问题是参与/做多背景，不冒称发现月份内排序信息。

## 先复用本机原年包，不重复获取

旧048声明缓存位置是`examples/portfolio_backtesting/backtest_outputs/external_cftc_cot_cache/fut_disagg_txt_*.zip`。本次只做目录/stat和checkout文件名搜索：该目录本机不存在，也未在本checkout找到同名ZIP；**这不证明整台机器或旧bytedance环境没有缓存**。没有打开/重hash任何旧年包，未全盘扫描巨库。下一步root若定位到已保存2020–2026原包，应按原绑定复用2020–2025，最多补缺年；不能因旧绝对路径失效就先全部重下载。

[维护者cot_reports说明](https://github.com/NDelventhal/cot_reports)及[对应源码入口](https://github.com/NDelventhal/cot_reports/blob/main/cot_reports/cot_reports.py)提供按年官方ZIP获取实现，足以定位直接访问方式；不安装库、不跑`cot_all()`，不用其派生信号或旧脚本的补零/简单时钟。一次从官方页面Disaggregated Futures Only区解析各年Text href即可，不能用猜文件名多路径碰运气。现成公开入口已核，**本机HTTP可达与文件大小尚未实际验证**。

## 发布时间与修订：当前真正的实施边界

[官方release规则](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm)是通常周五美东15:30发布此前周二仓位，假日可推迟；报表as-of不是发布时间。[官方历史special announcements](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm)记录了2018/19政府停摆、2023 ION及2025停摆/追赶发布，也有更正和漏报。例：2023-02-24才发布原定02-03的报告；因此旧`report_date+4天08CST`并非保守普适规则，**本后继不继承它**。

同一次源准备需输出一份release/exception panel，最少分开：`positions_asof`、`scheduled_release_at`、`confirmed_release_at/证据`、`correction_known_at/范围`、`research_available_at`和2026实际`downloaded_at`。按America/New_York处理DST，官方“计划/将于”不得写成实际已发布。普通周依据原发布规则与当年例外，确证补发按真实补发；无法给出可靠边界的周保留unknown，不能用当前下载时间倒填历史或把周二统一当周五。

本阶段**不另拍一个10日/30日lag来掩盖例外**。金融使用只能在root冻结上述实际可用边界后，映射到第一个严格在该边界之后完成的中国u及原D规则，不能追入已开盘会话。补发多期同日/同u必须合并成一个可见事件，不能把回补的旧周分散到过去；同市场取当时已发布的最大as-of，不因档案有缺就从未来倒查。

年度ZIP是当前归档，不天然是first-publication字节。官方说明早期回溯分类采用后来掌握的类别；2019等年也有已公布更正。对明确影响字段的更正须用更正可知时刻或将受影响行unknown，不能把更正后的H放回更正前。未发现公告不等于保证无修订；若只获得常规归档假设，要明确标为retrospective研究，不宣称strict PIT。**publication/correction边界未完成前金融预算0**；无法闭合且有效事件不足，就关闭这一路，不再建设无限vintage工程。

## 下一turn能直接做什么，以及停止点

下一步只是一批可实证的source preparation：先查root已知缓存绑定并复用，缺年最多16个官方年包，另保存一次官方release规则及历史exception正文；无需几千日报/行情请求。压缩每年硬上限8MiB、总新body≤128MiB、解压member每年≤128MiB、并发≤2、timeout30s/retry0；403/429停止，不转付费代理或安装新包。大小是预算，未下载不能写成实际数十MB。ZIP只按member流读、不extractall；当次读取同时核字节/字段并提取上述8市场的PMPU/MM/OI及完整历史身份/缺失清单，不反复全流审计。

最少交付为原件bindings、八通道周表、release/修订例外表、合并后的独立可见事件数及按年覆盖。建议进入金融设计的最低条件是≥400个有可靠时钟的独立周事件、2023/24/25各≥35个，且各映射原始量/定义可解释；这是可行性底线，不是功效或置信度证明。按真实缺口判，不能为过门改类别/年份或把事件×产品充数。达不到就0fit/cash停止。

若源准备通过，再由root另冻结一次最多6fit/0cash的三年扩窗条件对照：原52+共享MM net/OI/availability/age，对比同域同目标同成熟时钟再加唯一H；每周总权重相同，训练/scaler仅用该cutoff前资料。全母域含非正分、未知和无观察行；不恢复C9信号子集。原MM作为共同控制而非新MM策略。2023/24/25逐年留出、报告年度/映射覆盖和周相关，不用县/合约bootstrap造窄置信度；若H只是MM镜像、增量反号/不稳定或只靠一物一年来，则关闭，不转试一排COT类别/窗口。此为后继预算建议，**本turn没有授权或运行这6fit**。

## 反思

开始与结束的过拟合风险：**是，有历史适应性和旧COT反馈风险**；本阶段没有按新收益调参，但不能自称完全新颖盲题。保持一个测量、同源MM控制、原目标/成本、最多一次后继是必要约束。继续是否有价值：**有限是，仅源/时钟面板准备；当前金融否**。PMPU并不保证做多溢价，海外风险承接未必传到中国，窄损first-exit也未必适合周频风险背景。若失败，接受无可信新增增量，而不是维持忙碌。

本轮实际新增/修改/删除金融参数和结果均0；期末权益、收益、DD、Sharpe、滑点、交易次数和胜率均N/A。未建立正式C9/月池候选、未发布/Git、未追加生产或账户资格。唯一406提案结束，不回写blind400。
