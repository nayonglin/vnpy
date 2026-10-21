# Stage143：真实合约日终OI的外部语义复核与重复实验否决

时间：2026-10-18 23:36 CST；line_id：`futures_full_market_long_signal_ai`；独立外部调研 agent。非重要突破。本阶段只读registry、本线LINE末段与078/084/085/089/142小报告，未读大型结果、数据库、模型或账本；已见历史结论，不能称收益盲。新增SQL/fit/cash/标签/行情下载/账号调用均0；累计仍391fit/202cash。

开始反思：新增按收益调参过拟合＝否；长期复用历史、选择新解释的风险＝是。继续有限来源与重复性审查有价值＝是；继续已失败OI公式/52槽包救参＝否。

## 独立结论：OI不是本线的新来源

最优单一命题是：**总OI为未平仓风险存量，可能含OHLCV之外的信息；但当前没有理由重启同类日终OI实验。** Stage084—089已用真实完整YYYYMM合约e，而非主连拼接，检验`[closeOI(e,u−1)−closeOI(e,u−2)]/V(e,u−1)`；严格连续源日、同source、canonical单边、共享missing，12fit/8cash。四配对CI均跨0，两训练外family组已知增量均负，三组资金收益差负，已有明确停止条款。Stage142只定位事后资金会计差，不提供翻转OI负证据的依据。

范围必须准确：084的e是当时代表合约，并未测试128以后全部候选月份的OI排序，因此不能声称“所有选月OI均已失败”。然而“真实合约而非主连”已经不是新颖性；换成子月、分母、窗口、符号或模型，也不会产生新观测。若要提出不同选月经济命题，须先独立证明任务和信息支持的差别，不能借此把旧停止结论抹掉。本轮建议0fit/0cash。

## 网上及GitHub核查：语义成立，方向性不成立

[CME量仓定义](https://www.cmegroup.com/trading/about-volume.html)明确每张未平仓合约有买卖双方，OI只计一侧；[CFTC解释](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ExplanatoryNotes/index.htm)区分总OI和参与者分类。故OI增加不是“多头比空头增加更多”，不是净多资金、资金净流入金额、主动买入或聪明钱。市场价格上涨同时增仓，也可能是空方新增套保，不能仅靠总量辨认身份或动机。[CME教学页](https://www.cmegroup.com/education/lessons/open-interest)关于趋势确认的说法是一般性教学，不能替代中国日级long与极窄损的收益验证。

OI相对OHLCV确有不可唯一重建性：同一起始OI=100、成交10手、同样的成交价路径，可以是双方新开使OI=110，也可以是持仓转手使OI=100，或双方平仓使OI=90。OHLCV相同而OI不同，构成反例；这是信息论边界，不是预测优势。总OI仍不能恢复逐笔开平结构，日内相互抵消也会留下相同日终差。

已读维护方[shinnytech/tqsdk-python api.py](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)：`open_oi/close_oi`分别为K线起点/终点持仓，按日期的历史接口注明权限限制。**终点持仓不是开仓量，日K线终点字段也不能不经核对就冒称交易所结算后首发值。** 开源接口存在不证明本账户有历史权限、全合约覆盖或首次发布PIT。未调用SDK、登录或下载数据。

## 2019/2020统计制度：不能按年份机械除二

[INE 2019官方问答](https://www.ine.com.cn/eng/circularnews/news/201910/t20191029_820252.html)明确2020-01-01切换，原金融期货已有单边统计；变更涉及交易系统和网站数据。会员/投资者买卖不必相等，会员级统计不随交易所总量机械减半。该页英文历史处理段出现旧静态页“single-sided”与末段旧数据仍标“double-counted”的内在矛盾；本轮直接open为WAF，官方域名定向检索可读全文，故保留访问与翻译限制，不借一个句子批准全历史转换。[上期所2019行情平台规范](https://www.shfe.com.cn/upload/20190220/1550653663710.pdf)还显示同年可有不同统计模式的行情主题。

可验证方法是绑定**具体source＋字段＋原注脚＋下载/版本时间**，核2019/2020边界的真实合约原量与canonical值；网页静态历史、会员系统历史查询、vendor已回溯统一序列须分别处理。原本已单边的CFFEX不能再除二；本机084已接受canonical量仓也不能重复转换。制度日期仅定位重点审查段，不替代Stage266固定unit_contract。OI与V若仅一侧错误，ΔOI/V将被人为翻倍；跨制度差分甚至可制造虚假断崖。

## 历史可得性和u时点资格

[上期所历史下载入口](https://www.shfe.com.cn/reports/tradedata/datadownload/)、[上期能源下载入口](https://www.ine.cn/reports/tradedata/datadownload/)和[郑商所2019历史月报](https://www.czce.com.cn/cn/rootfiles/2019/04/04/1545641548649138-1545641548661614.pdf)证明存在公开历史数量材料；[中金所原始行情格式](https://www.cffex.com.cn/u/cms/www/202201/20211342wucd.pdf)明确昨持仓和成交量的单边字段。它们不证明六所全部年份、全部真实合约的连续PIT历史。本机旧accepted closeOI是已有数据事实，本轮没有重验其覆盖，也没有为DCE/GFEX补做连续资格。

[上期所2026-10-16日行情页](https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/?query_date=20261016&query_options=1&query_params=kx&query_product_code=sn_f)注明交易期数显示后为结算后数据。因此“归属于u交易日”不等于“u收盘瞬间已经发布”；夜盘自然日期与交易日也须分别记。合法接线至少需要event/trade_date、available_at、version/retrieved_at以及来源身份；只有available_at≤决策时刻才能消费。当前u−1完整源日lag能降低同日结算延迟问题，仍不能证明历史无修订、没有晚发。归档文件只有行日期而无首发时间时，只能保留重建假设，不签严格PIT。

## 拒绝条件与后续边界

下列任一项足以拒绝新金融实验：①新提案只是084变量或其可逆变换；②不能解释与代表合约旧任务的实质差别；③把OI叫净多资金；④跨来源/主连/不同合约差分；⑤缺单位证据或二次除二；⑥以当前归档日期替代历史发布时间；⑦按未来闭合/缺失删预测；⑧靠选年、选族、阈值和模型容量修复旧失败。来源有差异应先精确证伪单位或时钟，不先fit证明其“有用”。

本阶段新增/修改/删除策略参数、回测结果均无；期末权益、收益、最大回撤、Sharpe、滑点、交易数、胜率均N/A，不把旧数写成本轮成绩。只新增本文，不改LINE/registry、其他线、正式策略或生产。结束反思：新增收益择参过拟合＝否，重复选题与事后叙事风险＝是；继续这个OI包＝否，继续寻找真正新增且可证PIT的独立信息/执行证据＝是。高质量long、窄损损失上界、低回撤和加注资格仍未实现。
