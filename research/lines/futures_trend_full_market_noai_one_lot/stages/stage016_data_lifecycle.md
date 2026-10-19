# Stage016 非交割账户生命周期数据与到期前退出合同调查

- line_id：`futures_trend_full_market_noai_one_lot`。
- 时间：2026-10-18 20:28 CST。
- 范围：按root分派只读本机既有元数据、日历、真实行情与官方/GitHub资料；只新增本记录，不改策略、运行入口、inputs、旧结果或clean库，不跑金融回测、不下载行情。
- 用户已明确要求修复到期卡死并移除最多4品种限制。本记录提供生命周期数据事实；根agent负责新执行合同与实现。
- 重要突破：否，属于执行正确性修复的资料准备。

## 直接可用的数据与覆盖

1. 真实合约元数据：`/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/rqalpha/futures_metadata.json`，SHA256 `7feb3e6a98b9f6c054b329fb74a2044be2700ae83f7f11c8de07632cd9f2ae89`。11,355条真实期货；有order_book_id、exchange、underlying_symbol、product、listed_date、maturity_date、de_listed_date、start_delivery_date、end_delivery_date、trading_hours等。
2. 冻结交易日历：同目录`trading_dates.npy`，SHA256 `57dd7f539d1cdbefb528978a6c7bd79b118790f933ce63c37b10747b999f9585`；int64 YYYYMMDD，5,587日，2005-01-04—2027-12-31。应使用此交易日序列移位，不能用自然日、工作日或该合约出现过报价的日期来代替。
3. clean`contracts`保存完整EXCHANGE.PRODUCT.YYYYMM、上市/退市/maturity及来源状态；主键不依赖CZCE三位native名。研究inputs的contract_metadata.csv有4,328个已物化epoch，仍须以完整epoch接上RQ分类，不能从字符串“IF”或_F的错误正则猜身份。
4. 对全部4,328个已用epoch逐一核对：精确RQ metadata缺失0；maturity/de_listed/listed缺失0；maturity和de_listed完全相同；maturity/de_listed落在冻结日历外0。分类为Commodity 3,831、Index 351、Government 146；start_delivery_date缺160条，故不能要求该列完整后才处理到期，也不能用其空值随意推到下一天。字段当前可计算截止，但vendor快照不是历史公告发布时间/PIT证明。

RQ全体分类为Commodity 10,619、Index 561、Government 175。**product分类不是delivery_method**：没有直接的cash/physical字段。

- 股指IF/IH/IC/IM可明确为现金交割类；Government的T/TF/TS/TL不能当现金股指。
- INE EC虽然RQ写Commodity，但2023年官方标准合约明确现金交割。当前已用18个EC epoch。
- DCE L_F/PP_F/V_F虽然也写Commodity，但为现金交割月均价家族。当前已用10/9/8个epoch；没有抓到DCE官网最终生效原条文，本次以明确已有maturity作截止数据，现金分类仍应附直接规则来源补齐。不能去_F后与普通实物L/PP/V合并。
- 不需要为了修复卡死先实现现金交割：可选择固定、保守的到期前市场退出政策，但必须叫研究账户政策，不能把全部Commodity声称实物。

## 原残仓的可复现日期与真实报价

所有日期先按合约年月/maturity和全市场日历算出，再查询报价；没有挑有利或最后正量日作为截止。

| 精确合约 | maturity | 名义交割月前最后日 | maturity前1日 | maturity前5日 | 关键数据事实 |
| --- | --- | --- | --- | --- | --- |
| DCE.FB.201801 | 2018-01-15 | 2017-12-29 | 2018-01-12 | 2018-01-08 | 12/29真实V单边38、O102.65/H105.7/L99.25/C105.7、OI4；1/2才是事后最后正量日，不能用它定义政策 |
| CFFEX.IH.201812 | 2018-12-21 | 2018-11-30 | 2018-12-20 | 2018-12-14 | 12/20真实V14395、O2371.4；12/14 V17315。原5日换月延迟到期后才给退出意图，补expiry报价也救不了迟到订单 |
| CFFEX.IC.202112 | 2021-12-17 | 2021-11-30 | 2021-12-16 | 2021-12-10 | 12/16真实V41452、O7320.6；12/10 V47047。12/17 clean正量V19835/OI0已接受 |
| CZCE.ZC.202209 | 2022-09-07 | 2022-08-31 | 2022-09-06 | 2022-08-31 | 8/31 V9、O858/H975/L802/C974.6、OI1；9/1 V1/OI0是最后正量日，继续开进交割月才成为残仓 |

FB1801在2017-12-01、04、12、18、25、26、27、28、29有正量bar，V依次7、2、6、1、1、14、23、2、38。12/28 O=H=L=C=100.7；12/27 O103.7/H103.75/L98.1/C98.85。流动性已很薄；12/29虽有V38，也不能用日线量承诺真实新订单一定成交。

FB 2018-01-03—15全V0/OI0平价不恢复；本调查不制作这些日期的成交或结算。ZC 8/30有V10、OI5，8/29 V39、OI14；这里只证明预定月末截止附近有真实历史输入，不以这些行情挑最佳退出日。

查询复现的核心SQL：

```sql
SELECT trade_date,open,high,low,close,volume,close_oi
FROM daily_bars
WHERE contract_epoch_id = ? AND trade_date >= ?
ORDER BY trade_date;
```

日期复现：`calendar[calendar < first_day_of_nominal_contract_month][-1]`；maturity前N日为`calendar[calendar < maturity_date][-N]`。截止必须来自该日期算法，不能把SQL返回的最后有量日塞回截止。

## 名义月份与实际最后交易日错位

- SC1812名义2018-12，maturity=2018-11-30；maturity前8日为11/20，前5日11/23；名义月前最后日也是11/30，若只按月前退出仍会碰到最后交易日。
- FU1807名义2018-07，maturity=2018-06-28；RQ start_delivery_date=6/27甚至早于maturity，证明不能机械从start_delivery字段推执行时钟。
- L2602F名义2026-02，maturity/start_delivery=2026-01-30；不能等到2026-02再禁止新开。
- T1803名义2018-03，maturity3/9，交割月前最后日2/28、倒数第2日2/27。此精确epoch在这些取样日没有clean真实bar，显示确定截止不等于有成交证据。

## 官方资料与适用边界

本轮核对公开官方检索原文，以下用于约束方案，不把现代条文一律追溯到2015：

- [郑商所2015年TC/ZC合约调整及限仓条文](https://www.czce.com.cn/cn/rootfiles/2015/05/08/1425547808690959-1425547808761440.pdf)：自然人在交割月份限仓为0，旧TC与新ZC分开列示。支持TC/ZC均不应以自然人政策新开进入交割月。
- [郑商所2018年风险规则](https://www.czce.com.cn/cn/rootfiles/2018/08/24/1533012131105040-1533012131128874.pdf)：交割月份自然人0仓及交割单位调整。说明一手模型需要更早离开交割环节。
- [中金所国债交割细则2020](https://www.e-cffex.com.cn/u/cms/www/202007/08151817ah9p.pdf)：未通过托管审核账户从交割月份前1个交易日起持仓0。因此Government若建非交割账户，应至迟前2交易日收盘完成市场退出；单写“交割月前最后日退出”不够。
- [上期能源2020交割细则](https://www.ine.com.cn/upload/20201214/1607941018468.pdf)：原油自然人maturity前8交易日收市后0仓。不能只用名义交割月前末日。
- [上期所投资者问答](https://www.shfe.cn/index/othercontents/2025_AD/QA.pdf)：自然人最后交易日前5交易日收盘后0仓，后4日起强平；该现代规则的历史修订生效点没有在本次全量恢复。
- [中金所早期IF交易细则](https://www.cffex.com.cn/u/cms/www/oldsys/W020130830532922649672.pdf)：第三个周五为最后交易日，假期顺延；最后日与交割日关系明确。研究已有精确maturity，不必自己用第三周五猜历史异常调整。
- [上期所2023年EC标准合约](https://www.shfe.com.cn/products/futures/index_f/ec_f/standard_ec_f/202312/t20231205_330609.html)：现金交割，名义月最后一个期货交易周一为最后交易日。RQ Commodity标签不能代替交割分类。
- 大商所直接最终月均价规则的官网正文本次未取得；[上海证券报对大商所2025年发布的报道](https://paper.cnstock.com/html/2025-07/26/content_2098554.htm)明确现金交割与名义月前一月末到期。这是二级资料，仅作分类待补线索，不作为已完成所有历史规则认证的证据。

## GitHub参考与取舍

查看[RQAlpha官方position_model.py](https://github.com/ricequant/rqalpha/blob/master/rqalpha/mod/rqalpha_mod_sys_accounts/position_model.py)：期货settlement在`de_listed_at(next_date)`时生成系统清仓成交并清持仓，成本设为零；其结算价缺失时可能转close/last。这提示生命周期应是引擎/账户事件，不能仅依赖alpha退出或主力5日等待。

**取舍：采用提前识别生命周期与独立事件的结构，不复制其缺结算价兜底、零费系统成交假设。** 本研究需要真实当日可成交bar和明确费用；没有结算证据不能创建一笔假市场成交。

## 建议根agent冻结的因果合同

1. 以精确epoch的已知maturity、名义YYYYMM和冻结日历计算`last_permitted_execution_date`。全部计算不读取未来OHLC、成交量、策略PNL或当前四个残仓名单。
2. 股指IF/IH/IC/IM可固定N≥1交易日前退出；如选择N=5，应说明风险缓冲政策并一次冻结，不按收益扫描N。EC与_F应显式归类或采用统一更保守的非股指政策，不能伪称实物。
3. 非交割实物账户至少在名义交割月前完成；Government必须考虑上述“前1日已要求零仓”，SC考虑maturity前8日，其他SHFE/INE可取maturity前5日的更早限制。实现可以选择一个比所有已核规则更早的统一保守缓冲，以避免逐历史法规重建，但应明确这是新研究账户政策、不是2015—2026全部历史法规定时复刻。缺分类/生命周期时禁止该合约新开，不静默延至expiry。
4. 最稳妥的截止表达是适用限制的最早值，例如`min(month_boundary_exit, maturity_buffer_exit, account_specific_exit)`。这些是账户安全条件，和市场信号case无关。
5. **T+1开盘撮合必须提前发意图**：如果最晚执行日为C，C前一个交易日收盘就强制目标0并取消该合约全部pending OPEN；C开盘只凭真实当日bar平仓。C收盘才发退出会在C+1开盘执行，属于越界。因果查询next_session只看已知日历，不看次日行情。
6. 从进入生命周期退出状态起，禁止新增/加仓/重试/换月再开旧合约；生命周期退出优先于原5日换月等待。真实旧仓未平之前，不用删除state或清零target假装释放gross仓位；新合约也需遵守每品种总gross一手。
7. 可预声明一个固定提前清仓窗口，在窗口内重复发送close-only意图，增加真实成交机会；窗口不能通过未来最后有量日反推。截止日缺bar仍不可伪造close或回溯早先行情；记录未完成退出、到期残仓和性能资格限制。没有实盘担保“永不残仓”的数据保证。
8. 取消4产品上限是用户明确的另一项政策改动；不应顺带取消总资金、gross保证金、方向/相关风险或每品种一手约束。新结果需报告实际最大并发和保证金峰值，而不是只检查max_positions字段。

## 缺口和结论

当前4,328个epoch具备计算固定因果截止所需的maturity+名义月+日历，不必下载行情即可实现一般生命周期修复。尚缺逐历史法规生效表、显式交割方式、历史PIT公告链、全部截止日成交覆盖和broker清算模型。生命周期政策能避免“明知即将到期还继续新开/等待5日”的确定性bug；它不能凭空创造极不流动合约的退出成交。新的真实回测如仍出现截止前已缺真实bar的残仓，必须保留并如实审查，不能继续选更早有量日救结果。

本次新增/修改/删除策略参数无；实现方案由root冻结。本阶段金融回测、拟合、行情下载、CTP和订单API均0。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。

开始/结束过拟合判断：**否（本阶段没有按结果挑合约、日期或退出价）**。修复由到期法律/账户事实触发，通用截止只依生命周期与日历；这是发现bug后的新执行合同，需保留旧失败包并注明修订，不声称完全先验设计。继续价值：**是**，生命周期是全市场真实合约回测的必要前提。下一步是root实现固定合同、测试T+1与pending单优先级、运行新run，并按用户要求独立review结果/数据/会计与置信度。

## root拟固定的统一研究运营政策之结构核对

后续root明确倾向固定：CFFEX IF/IH/IC/IM且RQ product=Index时，deadline为maturity前1T；其余全部产品（明确包括现金EC与_F，不称全实物）为`min(名义合约月首交易日前2T, maturity前10T)`；signal再提前1T。这是新增的保守研究运营提前量，不扫N/天数收益最优，不称正式策略原规则或完整历史法规复刻。

本agent只读按该算法计算全部4,328个epoch：截止日历/偏移缺失0；deadline早于或等于listed的例0。样例deadline/signal：FB201801=2017-12-28/12-27，IH201812=2018-12-20/12-19，IC202112=2021-12-16/12-15，ZC202209=2022-08-24/08-23，SC201812=2018-11-16/11-15。该核验只读生命周期/日历，未算PNL，未按合约截止bar有无改变日期。

结构意见：无明显结构性错误。deadline D应解释为D收盘前零仓，D-1收盘已强制close-only；预计在D或之后执行的OPEN全部禁止，包括旧pending及retry，避免只检查signal<D却在D开盘新增。maturity前10T能覆盖本次核到SC8T/普通5T的操作提前量，但不是保证所有历史法律/临时公告均完整复现。D缺实价仍不可造平仓；生命期闸门和真实撮合失败必须分开披露。新政策与原v4是不同运行合同，旧结果保持原样。
