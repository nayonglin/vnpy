# Stage001：官方与国际商品基本面数据源核验

- 研究线：`futures_fundamental_data_sources`
- 调研日期：2026-11-08（北京时间；文件名15:00为并行阶段归档批次，非逐请求时间戳）。
- 性质：只读来源调研与少量公开文件/API抽样；不安装依赖、不用凭证、不跑回测、不交易。
- 是否重要突破版本：否；确认了影响后续研究可信度的发布时间与修订边界。
- 开始反思：本次不选参数、不筛收益，**不是策略过拟合**；**有价值继续**，因为先证实历史可得性与时点信息，能够排除未来数据泄漏。
- 证据口径：**文档**仅证明发布方声明；**样本**证明本次特定请求/文件结果；**PIT**须另证数据在历史决策时点已经公开。三个层次不能互相替代。未逐一验收所有品种、国家、指标与2015年以来每期完整性。

## 主要判断

1. 最值得优先建设的是真实供需发布事件：WASDE逐期报告、EIA逐期库存报告、国内统计发布原文。CFTC是持仓结构补充，世界银行/FAO价格指数是背景变量，不能把它们全部叫作实物供需。
2. **WASDE历史CSV保留报告当时值，PSD提供修订后历史值**；前者适合构造逐期预期变动，后者适合研究当前已知的结构事实。二者禁止混用。WASDE现行CSV在报告发布次日更新；不能据此声称历史研究当天已经能用CSV自动取得数据。
3. **CASDE首期为2016年7月**。首期含2015/16年度估计，并不意味着2015年存在CASDE公告。
4. **海关在线查询可追溯2015年以来有较新官方行业指南支持，但输出是月度正式数据，不是当期快讯初值**。平台当前查询未成功，历史每条序列尚未实测验收。
5. “来源历史很久”不等于每条序列2015年完整；“有发布时间字段”也不等于保留历史首次发布版本。需要按具体序列建立覆盖清单和修订分层。

## 10类核心来源

### 1. USDA WASDE：优先级最高的国际农业发布事件

- **官方入口**：[WASDE](https://www.usda.gov/about-usda/general-information/staff-offices/office-chief-economist/commodity-markets/wasde-report)；[历史报告数据](https://www.usda.gov/oce/commodity-markets/wasde/historical-wasde-report-data)。主页面另链接1973年至今的ESMIS报告档案。
- **文档覆盖**：当前主页面列“2010—2026”合并CSV；[USDA 2021官方问答](https://www.nass.usda.gov/Education_and_Outreach/Meeting/2021/2021-spring-questionandanswer.pdf)明确从2010年4月起，保留各纸质报告发布时的数值，不纳入随后修订。这比笼统声称“USDA从1960年有数据”更适合PIT。
- **取得方式/频率**：月度PDF/XML/Excel/Text；历史CSV无key。当前主页面说明CSV在报告发布**次日**更新；[2025官方问答](https://data.nass.usda.gov/Education_and_Outreach/Meeting/2025/2025%20Spring%20Data%20Users%20Meeting%20Question%20and%20Answer%20Summary%20with%20Slides.pdf)亦确认次日。当前日程为12:00 ET；历史每年时刻应查当年公告，不能将2026日程机械套回2015。
- **本次样本**：主页面可读，历史CSV落地页经web与独立Python只读请求均HTTP403；因此本次**没有解析CSV中的2015记录**。文档支持覆盖，不冒称全量下载验收完成。
- **适用**：玉米、小麦、稻米、大豆及油籽、棉花、糖；美国畜牧/蛋奶。中国豆粕、豆油等需自行明确全球/美国/中国供需的传导，不把美国大豆库存当作中国豆粕库存。
- **PIT/不足**：使用`report_date + 原报告可证发布时间`；若依赖次日才发布的CSV，应以CSV的实际可得时间执行，或另建当时PDF解析链路。作物年度与自然月不同，单位/表格位置会变，保留原表、说明及修订脚注。

### 2. USDA PSD与NASS Quick Stats：结构供需及生产/面积/库存

- **PSD入口**：[PSD Online](https://apps.fas.usda.gov/psdonline/app/index.html)、[当前FAS API门户](https://apps.fas.usda.gov/opendatawebv2/)、[Swagger JSON](https://apps.fas.usda.gov/opendatawebv2/assets/swagger/swagger.json)。旧PSD Swagger仍存在，不应默认作为新的唯一集成协议。
- **PSD接口实证**：本次成功读出40,937字节Swagger；`host=api.fas.usda.gov`；认证字段为请求头`X-Api-Key`，当前门户指向API.Data.Gov注册。实证路径包括`/api/psd/commodities`、`/api/psd/commodity/{commodityCode}/country/all/year/{marketYear}`、`/api/psd/commodity/{commodityCode}/dataReleaseDates`。未申请key、未查询受key保护的数据。
- **PSD文档覆盖**：[官方端点说明](https://apps.fas.usda.gov/opendataweb/home)称“most commodities since 1960”，并警告一次发布可能修订同商品多个年份；这不是每个国家商品指标从1960无缺口的保证。PSD页面提供各商品全国家、全年份下载文件，可作为无key文件路线的后续核验对象，本次未下载。
- **PSD PIT**：商品级最近发布日期有助增量同步，但不构成逐行历史vintage档案。PSD是含历史修订的官方序列；回测2015时不能直接使用今天下载的2015值。用于长期产量、消费、进出口与库存结构较有价值。
- **Quick Stats入口/文档**：[Quick Stats API](https://quickstats.nass.usda.gov/api)、[NASS入口](https://www.nass.usda.gov/Quick_Stats/)。免费申请email key，接受服务条款；GET输出JSON/CSV/XML，每请求最多50,000条，`get_counts`预检后按商品/年份分拆；官方也提供工作日/每夜更新的`.gz`批量文件与主要报告发布时JSON。
- **Quick Stats样本边界**：本次读取的是**文档示例**：2012年弗吉尼亚玉米播种面积、`load_time=2012-10-11 11:26:13`；没有实际API调用，不据此证明2015全美每条序列完整。`load_time`是加载字段，不能自动解释成首次公开时刻或完整vintage链。适用玉米/大豆/棉花种植、收获、单产、谷物库存、生猪等；更严谨的事件研究应配NASS逐期原报告。

### 3. EIA：能源库存、生产、炼厂、进出口

- **官方入口**：[API技术文档](https://www.eia.gov/opendata/documentation.php)、[更新FAQ](https://www.eia.gov/opendata/faqs.php)、[WPSR档案](https://www.eia.gov/petroleum/supply/weekly/archive/)。APIv2须免费个人key；`/v2/seriesid/{旧series_id}`提供旧ID兼容。网页/XLS文件可另行下载，无须为小量公开文件申请key。
- **2015实际页面样本**：[2015-01-07报告](https://www.eia.gov/petroleum/supply/weekly/archive/2015/2015_01_07/wpsr_2015_01_07.php)可读；官方档案将**发布日期2015-01-07**与**数据截止2015-01-02**分列。不是把库存统计周五当作已知日。
- **序列覆盖实证**：[美国剔除SPR原油周末库存WCESTUS1](https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=WCESTUS1&f=W)网页实际显示1982年起历史及XLS链接；本次未逐项验证全部2015周值，也未验证其他能源序列同样起始。
- **频率/时间**：周/月/日因序列而异。FAQ明确APIv2取消原API的update字段；WPSR与WNGSR通常在公布后两小时内进入API，秒级访问应看`ir.eia.gov`。故API数据日期不能当发布时刻，API可得时刻也可能晚于原公告。
- **PIT/适用**：API当前库可能修订，PIT优先逐期WPSR归档；SC、FU、LU、LPG及相关油化工的国际背景。美国产品定义、地区/质量、单位和中国合约标的不同，不能直接生成国内库存缺口。

### 4. CFTC COT：可自动化的周度持仓结构，属于辅助变量

- **官方入口**：[COT说明](https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm)、[年包档案](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm)、[2015 Disaggregated Futures ZIP](https://www.cftc.gov/files/dea/history/fut_disagg_txt_2015.zip)。公开年包TXT/Excel，无key；Public Reporting Environment亦支持筛选导出。
- **本次文件实证**：成功只读下载1,697,554字节ZIP，解出`f_year.txt`，9,762行、52个报告日期、236个市场代码；日期范围2015-01-06—2015-12-29。首行WHEAT-SRW/CBT，报告日期2015-12-29，合约市场代码001602。此为**特定年包**覆盖，不证明每个市场52周全有。
- **文档边界**：Legacy futures档案自1986；Disaggregated当前页面正文称自2009-09，另列2006—2016合并包；主FAQ称历史可到2006-06。应以选用具体报告的字段和实际文件为准，不能混并Legacy/Disaggregated或futures-only/combined。
- **PIT**：统计截至周二，通常周五15:30 ET发布，节假日和停发须查当年release schedule；[历史特殊公告](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm)记录2015-07-03曾提前发布不完整报告及随后修正。年包可能含更正，不保证保存首次发布版本。禁止把`Report_Date`当公开时间。
- **适用/不足**：能源、金属、谷物、油籽、软商品的海外资金/套保结构，非中国交易所持仓、非实物库存；商品市场代码需版本化映射，非报告者差额也不能简单等同散户看法。

### 5. FRED/ALFRED：PIT宏观环境，技术能力与权利范围分开

- **文档**：[observations](https://fred.stlouisfed.org/docs/api/fred/series_observations.html)、[vintagedates](https://fred.stlouisfed.org/docs/api/fred/series_vintagedates.html)、[key](https://fred.stlouisfed.org/docs/api/api_key.html)。注册账户申请key；`realtime_start/realtime_end`或`vintage_dates`取历史已知版本；`output_type=4`为初次发布值。vintage日期只列发生新值/修订的发布日期，不等同全部日历发布事件。
- **实际页面证据**：[ALFRED INDPRO](https://alfred.stlouisfed.org/series?seid=INDPRO)展示历史元数据，2015-07-20以前为2007基期、2015-07-21起为2012基期；技术上可反映历史口径变化。本次未用key取得2015 observation/vintage数值，不应将页面历史区间当所有序列PIT全覆盖。
- **适用**：工业生产、美元、利率、通胀、需求周期背景，频率由序列决定；要区分来源机构数据与FRED二次托管。观察值从2015之前开始，不证明ALFRED从当时就收集了该序列vintage。
- **权利范围**：[现行条款](https://fred.stlouisfed.org/legal/terms/)与[说明](https://fred.stlouisfed.org/legal/)对开发/训练用途、第三方版权、API/MCP使用与缓存/归档有具体规定。**不能从开发/训练条款外推“禁止所有AI推理/读取”**；官方MCP使用场景和本地长期PIT归档是不同适用问题。接入Skill前应核清选定通道、实际用途、存储/再分发及单序列权利，本报告不作法律定论，也不因免费key而视为无限制授权。

### 6. World Bank Pink Sheet：跨度长的月度国际现货价格背景

- **入口**：[Commodity Markets](https://www.worldbank.org/en/research/commodity-markets)；[本次主页面实际链接的月度XLSX](https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx)。公开文件无key；通过主页面发现当前附件，不把含发布ID的长链接假定为永久稳定API。
- **本次实证**：成功下载587,760字节XLSX；本机无openpyxl，用Python标准库ZIP/XML解析，不安装依赖。`Monthly Prices`含2015M01—2015M12全部12行；2015M01 Brent48.1、WTI47.3美元/桶；文件注明2026-11-03更新。另有`Monthly Indices`、`Description`、`Index Weights`表。
- **历史/频率**：文件正文写月度名义美元价格1960年至今；这不是每列从1960完整，未检验每列2015非缺失。月度发布，主页面给发布日期及下次更新时间；不是日内交易价。
- **PIT/适用**：本次文件是2026下载的历史序列，不是2015当时vintage；月均价应在月底以后对应发布时才用。涵盖能源、油籽谷物、糖棉橡胶、金属、铁矿及化肥背景；国际报价质量/运费/地域、币种与国内期货不同；保留`Description`及第三方来源权利说明。

### 7. FAO：FFPI月度价格与FAOSTAT年度实物数据必须分层

- **FFPI入口**：[官方页](https://www.fao.org/worldfoodsituation/foodpricesindex/en/)、[官方CSV](https://www.fao.org/media/docs/worldfoodsituationlibraries/wfs-library/food_price_indices_data.csv?download=true&sfvrsn=523ebd2a_85)。无需key；页面列1990年起月度名义指数、1961年起年度数据及全年公布日程。
- **FFPI实证**：下载48,217字节CSV，2015年有12个月；2015-01综合101.0、谷物105.9、油脂95.00、糖95.0；2015-12综合87.0。文件当前基期为2014—2016=100；不得假装这是2015现场看到的同基期初值。
- **修订**：页面说明2020年改基期并扩大价格覆盖，最新公告还直接使用“revised September level”；现价文件会修订。适合跨商品价格压力背景，不是产量或可交易合约结算价。
- **FAOSTAT**：[入口](https://www.fao.org/faostat/en/)、[2026新API门户公告](https://www.fao.org/statistics/highlights-archive/highlights-detail/faostat-launches-a-new-api-developer-portal-to-make-data-access-easier/en)。官方称245多个国家/地区、总体1961年至今，可批量文件；年度产量/面积/单产、贸易、食物平衡用途广，但不同domain有方法及覆盖差异。
- **FAOSTAT边界**：本次未下载大体积年度bulk，也未实测新API认证/限流，故不宣称“无key新API已跑通”。[现行非食物商品平衡元数据](https://data.fao.org/catalog/dataset/6c03f60f-ff40-412b-87a8-66a1c6b45986)给具体修订日、单位与数据来源；旧新方法域不能直接拼接。逐数据集许可也应核验，不能把一个目录页的许可推广全部FAO资产。

### 8. UN Comtrade：有价值的贸易流量，历史时效与完整性需逐reporter核验

- **官方文档**：[API](https://uncomtrade.org/docs/un-comtrade-api/)、[订阅](https://comtradeplus.un.org/Subscriptions)、[可用性](https://uncomtrade.org/docs/data-availability/)。无key public preview最多500记录；免费注册API当前100,000条/调用、500调用/日、1次/秒；完整bulk及async归Premium。定额可能变化，实施时读当期方案。
- **接口**：`https://comtradeapi.un.org/data/v1/get/C/M/HS`为月度货物；`A`为年度；官方示例采用subscription key。无key预览位于`/public/v1/preview/…`。参考代码、HS版本、`getDA`和recent releases均应先查，不按站点创立年份承诺覆盖。
- **本次样本**：无key请求中国reporter156、201501、HS1201、进口M、世界partner0返回`count=0,error="",data=[]`，相应公开data availability亦为空。美国reporter842、201501、HS1201、出口X、世界partner0则返回1条，`classificationCode=H4, primaryValue=fobvalue=3,077,234,860, isReported=false, isAggregate=true`，该记录重量和数量字段为0、单位代码-1，不能当作真实0吨。另一次中国年度预览返回HTTP429。结果证明特定2015月度金额记录可取，但**不证明中国2015全覆盖、数量可用或PIT初值**；也不能从单次空结果断言中国2015月度全部缺失。后续应遵循限流，按data availability和有key小请求复核。
- **PIT/适用**：年度/月度，各报告国上报时间不同，UN接收/发布可晚于本国海关，可能重报/转换。适合大豆、油脂、煤/原油/矿石/金属等国际贸易验证；保留`isReported`、分类版本、估算数量/重量标记。年度总额未必等于月度之和；贸易金额/重量单价不是质量不变的现货价。

### 9. 国家统计局：最基础的国内生产与需求原文证据

- **入口**：[国家数据](https://data.stats.gov.cn/)、[官方数据库使用说明](https://www.stats.gov.cn/zs/tjws/jbtjzswd/tjzn/202412/t20241216_1957774.html)。月/季/年度；网页查询与发布稿可读；本次未找到可作为长期协议承诺的公开版API文档，不能把内部`easyquery`请求当有SLA的官方API。
- **2015实证**：[2015年12月工业发布稿](https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1899018.html)正文实际发布时间**2016-01-19 10:00**，粗钢月度6437万吨、原煤31659万吨、焦炭3518万吨。URL含202302迁移日期，**不等于原公告发布时间**。
- **覆盖/适用**：煤焦钢、油/气、炼油、有色、乙烯、玻璃、水泥以及地产/工业需求等。某份2015发布稿存在，不代表所有细分产品连续公开；规上企业范围、产品定义、可比增长、累计/当月与1—2月合并发布均要跟随脚注。
- **PIT**：官方数据库说明明确普查后集中修订、GDP初步/最终核实后更新相关值。当前数据库2015值不能无条件当2015首次发布值；更合适的是保留原始发布稿、实际公告时间和后续更正。即使原稿仍在线，是否曾覆盖修改也须承认未知。

### 10. 海关总署：国内商品贸易核心，但应保留快讯/正式/年鉴三层

- **入口**：[在线查询平台](https://stats.customs.gov.cn/)、[英文月报](https://english.customs.gov.cn/statics/report/monthly.html)、[对外统计服务办事指南](https://online.customs.gov.cn/static/pages/guides/002029004002/002029004002.html)。免费免注册查询/导出；本次平台web请求超时，未绕过验证码、未找到可据以承诺的公开稳定API。
- **覆盖证据**：[2024《中国海关》查询指南](https://chinacustoms.gmcmonline.com/202405/c/19717.shtml)明确2015年以来、免注册、免费导出、不支持跨年度查询；2019及部分后来转述仍写2017起。应保留文档版本冲突，优先按当前平台逐年实测。[2015-12八位商品/国别量值PDF](https://www.gov.cn/xinwen/2016-05/09/5071547/files/4a650af0c1bd4784b8ed874002bad502.pdf)是政府站历史文件线索，本次未解析全表。
- **是否初值**：[国家统计局关于海关编制公布的说明](https://www.stats.gov.cn/zs/tjws/zytjzbqs/zckze/202501/t20250121_1958385.html)明确快讯是月度初步汇总、月刊及在线查询是修正差错后的正式数据、年鉴后上一年不再更正；该说明关于2017起范围仍属旧表述。英文月报也提示后续核验可能改变已发布数字。**历史在线查询可追溯，不等于保留历史快讯初值**。
- **频率/PIT**：月度；按每年公告的快讯/正式数据日程，不硬编码“每月某日”。[2026公布时间表公告](https://www.mofcom.gov.cn/zcfb/zgdwjjmywg/art/2026/art_f1be0183462142a28dbd9fd727220e3e.html)可作当前日程入口。若研究交易时点，要存两种公告事件，不能在快讯发布日提前使用稍后正式月报值。
- **适用/不足**：铁矿、煤、原油、油品、天然气、大豆/油脂/糖棉/橡胶、金属化工；HS编码和计量单位跨年调整须映射，贸易伙伴口径为进口原产/出口目的地，金额与数量分别核，缺报不作0。

## 补充：农业农村部与国家粮油信息中心

**农业农村部应纳入国内农业优先来源，但不伪造2015 CASDE历史。** [2016-07 CASDE No.1](https://scs.moa.gov.cn/jcyj/201607/t20160711_6410101.htm)实际公告日期2016-07-11；首期覆盖玉米、植物油、食糖等，后来扩展品种。2015年有另外的[2015-01大宗农产品供需月报原页面](https://scs.moa.gov.cn/gzjl/201502/t20150215_6293129.htm)和[2015-03大宗月报PDF](https://scs.moa.gov.cn/gzjl/201504/P020190507408500139092.pdf)，应分别建series/report_type，不能追溯改名为CASDE。

现有[农业农村部数据页](https://data.moa.gov.cn/nyb/pc/index.jsp)、[200指数栏目](https://scs.moa.gov.cn/cst/index.htm)提供日度价格线索，但前者公告2026-05-25指数编制方案调整；[2015第5周市场动态](https://scs.moa.gov.cn/gzjl/201502/t20150212_6293124.htm)则使用2000=100的旧“全国农产品批发价格指数”。两个口径不能直接按同名拼接。公开HTML/PDF无key可读，本次没有验证有公开长期API、完整2015每日价格档案或首次发布时间。

**国家粮油信息中心本次仅列待核线索，不提升为2015可自动抓取的核心PIT源。** [国家粮食和物资储备局官方工作动态](https://lswz.gov.cn/html/gzdt2024year/2024-12/05/content_285211.shtml)证实其玉米市场调研工作；[主管局门户](https://hlw.lswz.gov.cn/)有其外链。搜索发现2015粮油供需月报的二手引用，但未找到并实测2015逐月一手档案、稳定API、原始发布日期与明确自动使用授权；不能用期货研报/招股书引述代替源数据。具体网站域名及其运营/访问条件仍须由官方外链复核，不能凭名称猜域名。

## 样本验收边界与后续清单

| 验证对象 | 本次结论 | 不能推出的结论 |
|---|---|---|
| CFTC 2015 Disaggregated futures-only年包 | 文件解析成功；9762行、52日期、236市场 | 各市场连续52周、历史初次发布值都保存 |
| WB 2026-11更新月度XLSX | 2015有12个月，抽查Brent/WTI数值 | 每列无缺失、2015原始vintage、可作日频数据 |
| FAO当前FFPI CSV | 2015有12个月，当前2014—16基期 | 当年看到的相同基期/未修订初值 |
| EIA 2015-01-07报告页 | 发布日与数据截止分开、旧报告可读 | 所有能源series/PIT版本完整 |
| NBS 2015-12发布原文 | 正文保留2016-01-19 10:00与产量表 | 当前国家数据库值就是原稿值、页面从未覆盖 |
| WASDE历史CSV落地页 | 文档支持逐期原值；实际403 | 本机CSV已拉通或2015记录已解析 |
| PSD/QuickStats/FRED | 文档/Swagger可读；未用key | 有key调用已验证、每条2015序列验收通过 |
| Comtrade 201501大豆预览 | 中国为空；美国出口有1条聚合金额；一请求429 | 中国整体无数据、数量0即实物0、免费预览无限流 |
| 海关平台 | 新指南支持2015起；本次超时 | 实际平台每个2015序列已完整导出 |

后续Skill数据契约至少记录`source_id, series_id, report_type, reference_period, report_date, published_at, timezone, available_at, retrieved_at, vintage/revision, unit, geography, commodity_definition, source_url, raw_hash, rights_status`。将`coverage_verified`限定到实测具体系列/期间，不用来源级布尔值代表所有商品。

后续先做少量序列样本验收：WASDE中国/全球大豆库存与美国玉米；EIA原油库存；NBS粗钢/原煤；海关大豆/铁矿进口；MARA旧月报与CASDE分段。每个样本核原发布时点与现行值差异，再决定是否大规模获取。对无vintage且无法重建历史公告的序列，标记`latest_revised_only`，可用于当前研究背景，但不进入严格历史信号。

结束反思：**不是策略过拟合**，没有按收益挑选来源或参数；**有价值继续**，但应继续做数据可得性与时点验收，不宜马上把所有来源接入模型。此次调研不能证明这些基本面变量能提高策略收益，也不能作为实盘接入资格。
