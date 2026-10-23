# Stage022：8条缺键生命周期与来源语义独立复核

- 时间：2026-10-23T19:46:06.345165+08:00；line_id=`futures_weekly_formal_no_half_r`；重要突破：否。
- 结论：**7条可按真实新Tq源补入，FU单条物理身份未解决继续隔离**。没有金融回放、下载、旧工具/元数据/旧probe修改，不按收益决定数据资格。
- 根因修正：这7条不是RQ到期日错误。原contracts的listed/delisted均合理；旧clean正确剔除了1条RQ零量、6条RQ非法OHLC。新合法Tq日线独立证明可补源，不能恢复旧坏值。

| 合约日键 | 原listed / delisted（含端点） | 交易日序号 | 新Tq OHLC / V / closeOI | 旧源排除理由 | 判定 |
|---|---|---|---|---|---|
| jm2005.DCE / 2020-05-19 | 2019-05-20 / 2020-05-19 | 10 | 1234.5/1234.5/1234.5/1234.5; 101; 0 | no_trade | 接受新源 |
| jm2605.DCE / 2026-05-19 | 2025-05-20 / 2026-05-19 | 10 | 1148/1148/1148/1148; 43; 0 | invalid_ohlc | 接受新源 |
| jm2609.DCE / 2026-09-14 | 2025-09-15 / 2026-09-14 | 10 | 1711.5/1711.5/1711.5/1711.5; 102; 0 | invalid_ohlc | 接受新源 |
| lc2609.GFEX / 2026-09-14 | 2025-09-15 / 2026-09-14 | 10 | 150440/150440/150440/150440; 129; 0 | invalid_ohlc | 接受新源 |
| lh2609.DCE / 2026-09-24 | 2025-09-26 / 2026-09-24 | 倒数4 | 10300/10300/10300/10300; 9; 0 | invalid_ohlc | 接受新源 |
| si2609.GFEX / 2026-09-09 | 2025-09-15 / 2026-09-14 | 7 | 8780/8780/8780/8780; 16; 82 | invalid_ohlc | 接受新源 |
| si2609.GFEX / 2026-09-14 | 2025-09-15 / 2026-09-14 | 10 | 8695/8695/8695/8695; 32; 0 | invalid_ohlc | 接受新源 |
| fu1905.SHFE / 2018-05-09 | 2018-07-16 / 2019-04-30 | 6 | 3693/4000/3693/4000; 2; 0 | before_candidate_listing | 继续隔离 |

## 官方规则与真实日历

- JM：交割月第10个交易日。2020及2026年5月真实DCE映射日序前10天均为 `06,07,08,11,12,13,14,15,18,19`，故5月19日是合法最后交易日。原冻结mapping.csv按exchange=DCE逐月重算；2020官方国内市场劳动节公告仅作交叉核验。
- JM/LC/SI：2026年9月前10交易日为 `01,02,03,04,07,08,09,10,11,14`，9月14日第10日，SI的9月9日第7日。GFEX官方2026休市公告、上期所官方日历及冻结各交易所mapping逐值一致。
- LH：业务细则第十三条规定交割月倒数第4个交易日。2026年中秋9月25日休市，月底最后4个真实DCE映射交易日为 `09-24,09-28,09-29,09-30`，故9月24日合法。不把国务院调休周末计为期货交易日。

- [大连商品交易所焦煤期货合约制度设计说明（二〇一三年二月）](https://www.dce.com.cn/dalianshangpin/resource/cms/2016/11/焦煤期货合约制度设计说明.pdf)：交割月第10个交易日；历史JM2005规则依据。取证状态：official_domain_search_index; direct PDF fetch unavailable。
- [DCE 焦煤/焦炭官方 FACTSHEET](https://www.dce.com.cn/dce/file/2026-01-15/17684624156122c9a882b9ae6dcbb289019bc092f6fc1681.pdf)：焦煤最后交易日合约月份第10个交易日。取证状态：official_domain_search_index。
- [广州期货交易所工业硅期货合约（2022年12月12日版）](https://www.gfex.com.cn/gfex/llbb/202402/73cd6f4cc26b4dd5b3d127b5462b59a7/files/广州期货交易所工业硅期货合约（2022年12月12日版）.pdf)：合约月份第10个交易日。取证状态：official_domain_search_index; direct PDF fetch unavailable。
- [广州期货交易所碳酸锂期货合约](https://www.gfex.com.cn/gfex/sytslqhhy/202307/9ad927b8ec4c458594e172fd1ada2a9b.shtml)：合约月份第10个交易日。取证状态：official_domain_search_index; direct page timeout。
- [大连商品交易所生猪期货业务细则（2025年6月24日修改）第十三条](https://www.dce.com.cn/dalianshangpin/fgfz/6142914/6142926/6262877/大连商品交易所生猪期货业务细则（根据2025年6月24日〔2025〕59号文件修改）.pdf)：合约月份倒数第4个交易日。取证状态：official_domain_search_index with article13; direct PDF fetch unavailable。
- [Notice on 2026 GFEX Market Holiday Arrangements](https://www.gfex.com.cn/en/Notices/202601/ecd5e39ce8a04d2eb0a88d47ba2abd26.shtml)：5月1至5日/9月25至27日休市，5月6日/9月28日复市；调休周末不开市。取证状态：official_domain_search_index_full_notice; English reference translation, Chinese original prevails。
- [上期所2026年休市安排](https://www.shfe.com.cn/services/calenderandholidays/holiday/)：同上2026劳动节及中秋日历；交叉核验。取证状态：official_page_body_read。
- [大商所发〔2025〕437号：2026年部分节假日休市安排](https://www.dce.com.cn/dce/content/2025/ywggytz/18625615.html)：DCE自身公告定位；直取超时，不声称读取原站全文。取证状态：locator_only; NOT sole calendar evidence。
- [关于2020年劳动节休市安排的公告](https://big5.sse.com.cn/site/cht/www.sse.com.cn/disclosure/announcement/general/c/c_20200416_5040105.shtml)：5月1至5日休市/5月6日复市及5月9日周末休市；仅同年国内市场日历交叉核，不替代DCE实测日历。取证状态：official_page_search_body_read。
- [关于180燃料油期货合约终止交易以及保税380燃料油期货合约挂牌有关事项的通知](https://www.shfe.com.cn/publicnotice/notice/201806/t20180626_793285.html)：旧180 FU1905等自2018-06-27终止；新380 FU1905等2018-07-16重挂牌。取证状态：official_page_body_read。

## 来源裁决与范围

- 239合约/456请求键已完成原批取证，缺失0；本审查只裁决预声明8键。8键逐一独立从raw serial重解交易日、合约symbol、86400秒duration、唯一id/date，核有限正OHLC、合法区间、正量、非负OI及raw SHA。全部与旧M价格/成交量一致，全部不在旧main映射，但这不证明未影响指标或换月路径。
- 7条补源均使用新Tq原始合法OHLC、volume不缩放、open_interest=当日close_oi。旧M该7条持仓量逐项等于Tq open_oi，不能把旧M字段当closeOI；到期日closeOI=0不是坏bar理由。保持全新增Tq来源的一致口径，不按品种/日期/收益变换。
- 历史旧RQ坏值示例：JM2609的O/H/L=1585而close=1711.5；新Tq当日O/H/L/C均1711.5。JM2005旧RQ成交量0，新Tq101。其余原排除理由和raw_values逐行保存于JSON，旧clean清洗记录不改。
- FU1905的2018-05-09在当时可能是有效旧180合约交易，官方公告明确旧同名合约与2018-07-16新380重挂牌不同；不能把两者拼为 `SHFE.FU.201905` 单一物理epoch，也不能因新380 listed_date否认旧交易存在。未证明独立旧物理epoch与规格，本轮保守不纳入该行。这里不是删除亏损样本，也不能声称数据源全覆盖。
- 原probe对8条统一写的REJECT_UNRESOLVED_LIFECYCLE是保守初始字段，未做官方规则判断；保留原字节。本独立review只覆盖其来源资格解释，runner应另存固定7接受/1拒的决策manifest，所有现存accepted-clean键不被新值覆盖。
- 待runner在N/P完成后审计FU缺口是否触及AM源、候选、换月、订单、实际持仓或成交。未完成前不预称路径无影响；有影响则相应结果必须限缩或否决。
- 未看金融回报。判断过拟合：否；依据是统一规则、物理身份与真实源，不是收益。继续价值：有，属于历史数据资格治理；没有策略晋级结论。

- JSON证据：`stage022_lifecycle_rule_review.json`；输入/逐raw/收据SHA、逐键原元数据与完整月交易日序全部在JSON。冻结adapter SHA仍为 `6fb1abcfac3b6bc36b270a9ec10fdd49be7500a7d1dbcc4c4c9d9d36de9498b7`。
