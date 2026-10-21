# Stage386：美国大豆热害暴露到豆粕的单一经济定义与来源边界

- line_id：`futures_full_market_long_signal_ai`；记录时间2026-10-20 13:27 CST（文件名沿任务预留1320），写作按分钟记录，不作为天气文件到达时钟。
- 类型：379天气来源缺口的有界原始资料研究；非重要突破、非模型候选、非正式C9 A/B。先读`research/registry.md`及379原文；与正式C9、月度AI池和生产账户完全隔离。
- 本文只提出**美国大豆→进口压榨→DCE豆粕`m.DCE`**一个映射和一个待冻结经济量。不读价格/收益、不运行测试/训练/回测、不调用行情API、不下载天气大包、不安装依赖、不改模型或账户。只新增本文，LINE/registry由root维护。
- 开始判断：按新收益调参**否**；长期同史适应性择题风险**是**，不能因“此前没用天气”就把当前选择当无成本的新独立试验。继续补379缺的经济定义**有价值**，因为它能区分可计算的物理假说和泛泛天气故事。

## 结论先行

379中“未指定作物、产区、事前权重和生育期”的笼统空缺，现在可以缩到可审核的单一对象。美国不是2026年中国最大大豆来源国；选择它是因为USDA原发布年度逐州产量、当周逐州生育进度与已知年份的原热害研究能够形成清楚的时序和失败条件，**不是**按国内m历史收益选出来的区域。不能把当前巴西/美国份额反投所有年份。

经济供给链有第一性原理支撑；“热害修订→中国豆粕成本后做多收益”仍是未证假说。**本阶段只支持后续有限来源验收，不支持立即拟合、金融回测或加注。**尚未闭合的是逐年原发布实体覆盖、州内作物栅格的历史版本及实际GEFS字段/可知时钟；root并行调查天气档案。它们是具体数据问题，不应再次泛化为整个研究只能等待今天日线。

## 为什么只选m，不把所有大豆相关品种都标正号

大豆压榨共同产出粕与油，进口原料成本、油粕比、国内饲料需求、库存、汇率、关税和南美替代会共同影响m。CME自己的[CBOT与DCE压榨关系说明](https://www.cmegroup.com/trading/agricultural/cbot-soybeans-vs-dce-soybean-meal-and-soybean-oil.html)及[原维护方PDF](https://www.cmegroup.com/trading/agricultural/files/pm374-cbot-soybeans-vs-dce-soybean-meal-and-soybean-oil.pdf)明确把CBOT原料大豆和DCE豆粕/豆油放进同一压榨利润关系。这支持物理成本传导，不证明m对美国减产信息必涨。本文不采用其套保比率作新参数，也不将文中示例当统计证据。

USDA FAS[2018年8月油籽月报](https://www.fas.usda.gov/sites/default/files/2025-05/2018-Aug-Oilseeds.pdf)原文报告中国2017/18压榨量与当季进口量，说明进口原料和中国压榨需求的巨大重叠；当前存储路径含2025不等于报告当时2025才存在，必须取正文的2018报告期。后续若把进口份额变成数值权重，必须另取当时已发布的历史实体，本阶段没有这么做。USDA FAS[2025中国油籽年报](https://apps.fas.usda.gov/newgainapi/api/Report/DownloadReportByFileName?fileName=Oilseeds+and+Products+Annual_Beijing_China+-+People%27s+Republic+of_CH2025-0055.pdf)同时指出进口是中国压榨主要来源及贸易壁垒影响，**当前**进口依赖不意味着恒定美国权重。

只把m作为第一项可证伪对象，`a/b/y`及其他97产品均为本源未建模/未知。尤其不得把国产食用黄大豆一号`a`机械等同进口压榨大豆；也不把m的证据传播成全市场每个产品的天气多头分数。全市场宇宙不因此缩成m专用策略，未来若研究本源，仅m拥有该字段，其他产品不伪造天气值。

## 已实读的原论文及规则已知年份

[Schlenker与Roberts，PNAS 2009原文](https://doi.org/10.1073/pnas.0906865106)与[PubMed原摘要](https://pubmed.ncbi.nlm.nih.gov/19717432/)把美国1950—2005县级作物产量和日内温度暴露结合：大豆约30°C以上的暴露对应明显不利的产量变化。原文的大豆主要样本限于100°W以东、排Florida，采用固定3—8月生长季；这不是所有州/现代品种/灌溉条件下无条件成立的生理硬阈值。原研究2009已公开，若后来从GEFS业务档案2017年以后起步，30°C阈值不来自该金融样本优化。

因此本轮否决“降水减少就做多”的简单符号，保留**EDD30热害预期修订**。水分、灌溉和生育期会改变热害敏感性，不能声称单一温度字段已识别全部损害。USDA ARS维护的[2023原研究：花期和早期结籽干旱实验](https://www.ars.usda.gov/ARSUserFiles/60663500/Publications/Reddy/2023/Poudel%20et%20al_2023_SR_13-1277_13pgs.pdf)进一步支持生殖期水分暴露的生物重要性，但它2023年发表，不得声称2017年已知此篇，也不据此另起第二个干旱实验。

root给出的Illinois作者[2021年大豆天气风险溢价反证](https://farmdocdaily.illinois.edu/wp-content/uploads/2021/06/fdd230621.pdf)指出所考察2000—2020样本不支持简单大豆生长季天气溢价；南美替代和库存缓冲是重要背景。本subagent未重新统计该样本，引用作为root已实读的反证来源线索，**不将“减产会影响供给”偷换成“可获利买入”**。

## 公开历史权重：不用本年收成反投本年

已实读USDA官方ESMIS[2018-01-12年度产量归档页](https://esmis.nal.usda.gov/publication/crop-production-annual-summary/2018-01-12)，页面提供PDF、TXT、ZIP；[直接PDF实体](https://esmis.nal.usda.gov/sites/default/release-files/k3569432s/f4752k06n/th83m180b/CropProdSu-01-12-2018.pdf)第52—53页给出2015/2016/2017大豆逐州播种、收获面积、单产与产量。它证明至少一个可定位历史发布版本存在，**不是**已证明2017—2026所有年有完整PIT覆盖。当前Quick Stats修订库仅可辅助核数，不能自动冒充旧发布vintage。

拟使用收成年度`y-1`在`y`年1月年报**原发布**中的产量；`y`年的暴露权重全年冻结：

`w[s,y] = Q_original_Jan(y)[s,y-1] / Q_original_Jan(y)[US,y-1]`。

这里`Q`单位均为1000 bushels，同一表同一版；年度更新发生在本年生长期之前。2018年研究可使用2018-01-12公布的2017产量；2017年不能使用这份报告中的2017收成值。每年须保存`release_date、commodity、state、crop_year、statistic、unit、value、原文件URL/hash、解析表页码`。不得用当年最终产量、跨年平均最新产量或2026产量覆盖历史，也不得在看到金融结果后切换产量/面积权重。

州集合只取当年NASS官方周度大豆报告所覆盖州，按报告实体保留；不得按收益删州。分母保持全美产量，未覆盖州权重不偷偷分给覆盖州；另报覆盖产量权重。这是“官方观测覆盖部分的供给热害量”，不是100%美国全产区真值。年报未单列/抑制或周报缺失的州保留未覆盖标记。

## 生育期：原报告可得，不能用收获后重建进度

USDA官方[2010-10-29播收日历归档](https://esmis.nal.usda.gov/publication/usual-planting-and-harvesting-dates-us-field-crops/2010-10-29)有PDF/TXT/ZIP；[直接TXT](https://esmis.nal.usda.gov/sites/default/release-files/vm40xr56k/dv13zw65p/z603r1055/planting-10-29-2010.txt)第25页表的schema是州、2009播种面积、通常播种begin/most-active/end、通常收获begin/most-active/end。它2010年已知，可以做季节合理性和历年不可能日期核验；**没有逐州开花/灌浆日期，不能按播收中点捏造关键生育期**。

动态暴露拟取最新已公开的当周原报告`SETTING PODS`与`DROPPING LEAVES`两列：

`g[s,t] = (pods[s,asof(t)] - leaves[s,asof(t)]) / 100`。

NASS[阶段原定义页](https://www.nass.usda.gov/Publications/National_Crop_Progress/terms_definitions.php)底部标注2016-10-19更新：Setting Pods表示下部节点结荚且上部仍可能开花，Dropping Leaves表示约30—50%叶黄落。`g`是本轮新提出的“已结荚、尚未进入落叶的面积份额”代理，**不是**NASS现成的精准R3—R6字段，也不是2009论文原公式。以事前真实进度替代人为按月选季节，仍付出一次新设计自由度，不能从中再扫多种阶段组合。

已实际打开两个历史原PDF：

- [2020-08-10原周报](https://www.nass.usda.gov/Publications/Todays_Reports/reports/prog3320.pdf)：有对应周日参考期，正文发布日期晚一天。不能把参考周日当可知日。
- [2020-08-31原周报](https://www.nass.usda.gov/Publications/Todays_Reports/reports/prog3620.pdf)：第3页Setting Pods与第4页Dropping Leaves同时存在，18州覆盖上年96%大豆播种面积。列为州、上年同周、上周、本周、5年均值；只取此原文件当次发布的本周列，不能把以后报告的上周修订列替换成初值。本文只核schema，不把网页抽取文本逐行数值当已清洗数据。

同一2020原报明确：首个工作日**16:00 ET之后**发布，次周可修订；[官方Crop Progress档案总入口](https://esmis.nal.usda.gov/publication/crop-progress)提供按日期的PDF/TXT/ZIP与季节说明。夏令时要按America/New_York转换，通常周二中国凌晨才可知；不得固定UTC偏移、固定周一国内开盘已知，发布日期本身也不是精确first-seen。

并非每周都有两个阶段表：2020-08-31原报预告次周只列Dropping Leaves，说明已完成阶段会停止展示。**未发布不是0**，不能拿未来报告倒填开始前0或完成后100。若两值不能由当前及此前原报告明确证明，则`g=unknown`；遇`leaves>pods`、非[0,100]或缺州拒绝本次完整特征，不clip掩盖问题。未来是否采用明确完成值的单调延续，须先写唯一规则并按原始发布核验，不能收益后决定。本轮未核所有年份两阶段同时可得的覆盖，不宣称全季节完整。

root另外核到NASS[gridded layers说明](https://www.nass.usda.gov/Research_and_Science/Crop_Progress_Gridded_Layers/)存在2023-09-29对2020及以前大豆进度的重处理，且栅格是synthetic county construction。因此主路径只承认当周逐州原PDF/TXT，不用当前grid替换原始调查。

## 州内作物分布：公开下载不等于当时版本

NASS[CDL下载页](https://data.nass.usda.gov/Research_and_Science/Cropland/Release/)列出2008起全国年度GeoTIFF压缩包，2008—2023为30m、2024起改变分辨率；本轮只看网页，不下载GB包。[NASS原FAQ](https://data.nass.usda.gov/Research_and_Science/Cropland/sarsfaqs2.php)明确2010 CDL在2011年1月首周公布，且历史catalog曾在2012/2014重新编码/发布、2008/2009曾2017重处理。这说明不能把“影像标签2010”当“当前文件2010当时可得”。

合理空间量应在GEFS每个州内网格上按**事前可得的上一年大豆种植像元面积**分配，而不是按整个州土地等权平均（Texas等大州非作物面积会严重稀释）。未来解析schema至少`mask_crop_year、mask_version/release、state_fips、gefs_grid_id、soy_area_m2、within_state_fraction、origin_url/hash、asof_bound`。大豆代码及双季作物代码须按该版原字典确认；不能只凭现代字典挑码。

目前未逐年绑定旧图版本，也未验证哪些像元版本被替换；所以本阶段**未闭合**州内真实作物权重。不以当前全年图反投同年，不改用未来多年频率层，不用当前synthetic进度grid补洞，也不为了运行方便无声退化成州面积等权。固定更早的已发布作物地图可以成为另一个有披露的历史重建口径，但不能在结果差后切换；本轮没有同时开这个备选实验。

## 可冻结的唯一物理经济量（尚未执行）

若root后续完成源验收，建议只保留下面一个标量与完整覆盖/缺失元信息，不同时试雨、干旱、热害阈值和多个窗口：

`EDD30[g,run,V] = mean_over_members( sum_over_3h_valid_intervals_in_V( max(T2m_C[g,member,valid] - 30, 0) * 3/24 ) )`。

`X_m[t] = sum_s( w[s,y] * g[s,t] * sum_g_in_s( Asoy_asof[g,s,y] * (EDD30[g,newrun,V] - EDD30[g,oldrun,V]) ) )`。

其中`Asoy`是州内归一化、经版本证明事前可得的大豆像元面积权重。`V`固定为新run起算的未来完整7天，同一批有效时点；旧run取前一日同循环且覆盖**同一个V**，不能把两次rolling horizon错位当预报修订。7天是本次为隔离同一周物理预期设的设计选择，非原论文认定最优；不得再试3/5/10/14天。30°C来自2009原论文，不调29/31/35。必须每个成员先做非线性热暴露再平均，不能先平均温度再截断（Jensen偏差）；3小时瞬时2m温度只是日内积分近似，不能把日平均温度或某6小时最大值直接代入当等价。

单位为“覆盖美国生产加权、当前结荚未落叶暴露下，未来一周预报新增的°C·日”，正值只解释**预计供给热压力上修**，不是价格百分点或减产吨数。不从2009长周期回归系数直接换算现代短期吨数，也不在本轮对m设买入阈值/手数。更高物理供给压力可能在公告前已计价、被南美库存替代或被国内需求下修抵消；最终问题仍是给定旧价格/52特征后该外生修订是否有成本后增量。

源量需要逐条保存`run_init_utc、valid_time_utc、step/stepType、levelType/level、units、member、grid、model_version、object_URL/ETag/hash、archive_stamp、取得时间/历史保守可知上界`。GRIB上的起报标签不等于到达时间；不得将reforecast、analysis或今天回填的再分析当当年发布的预测。跨GEFS版本成员数与分辨率变更必须披露，不能用目前31成员去伪造旧期成员。

唯一有用的GitHub维护实践参考是[NOAA-MDL/grib2io](https://github.com/NOAA-MDL/grib2io)：它是NCEP GRIB2原维护体系的Python读取接口，README解释表驱动metadata及依赖。其作用是将变量、层次、单位、forecast step保留下来供校验；不是新alpha代码，也不证明历史文件可得或版本正确。本轮没有安装、克隆或执行它。先前猜测的NOAA-EMC路径打开失败后已用搜索确认正确维护方为NOAA-MDL，失败不作数据不存在证明。

## 失败条件与当前裁决

本阶段不得进入金融拟合的条件清楚可证：

1. 历史业务预报对应run/变量/同V时段不可定位，或仅剩后来reforecast；禁止替代后当PIT。
2. 年度权重依赖当年最终收成、当前修订库或缺失原发布日期；禁止反投未来权重。
3. 关键阶段缺失被补0/100、修订列被当初值，或只有收获后重处理grid；保持unknown。
4. 州内crop mask无法绑定历史公开版本；保持来源未闭合，不拿整州等权冒充已完成作物暴露。
5. 时钟晚于国内决策/开仓而被回填到前一会话；该观测不合格，不靠推迟一两分钟的收益结果选延迟。
6. 因现有m结果好坏修改州、月份、热阈值、窗口或供给到价格的符号；该轮失去预声明含义，不能继续救参。

若这些来源条件将来通过，也仅够做一次预声明的物理量检查和条件信息检验，绝不是直接加风险资格。若未看到独立成本后增量，不能靠放大m权重或极小止损救经济收益。极小止损会遇隔夜跳空、涨跌停和滑点，天气供给证据本身没有消除它们。

本轮结束判断：没有按收益调参或新增金融尝试，fit=0、cash=0、行情API=0、大天气/栅格下载=0、账户/正式策略变更=0。期末权益/总收益/最大回撤/Sharpe/滑点/交易次数/胜率均N/A，不复述旧结果为新增成绩。新增、修改、删除参数均0（上式为待root裁决的源定义，不是已激活模型参数）。已知金融结果不变、研究完整目标未达成。

结束过拟合判断：本轮没有结果导向搜索，但“只挑美国大豆/m并选择EDD30和周窗口”仍是新假说选择，不能宣称没有研究自由度。继续补这一个对象的历史可用性**有价值**；当前先接一个同valid-time热害修订与一份原发布暴露样本，足以把已定位的缺项继续推进，不把完整全史覆盖当有限实物验证的前置条件。天气run和mask时序仍不闭合时不直接金融拟合，不扩大成全史下载或反复泛搜。日线前瞻观察和本次历史来源研究可并行，不再把一条线路的等待升格为全部研究阻塞。
