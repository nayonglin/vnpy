# Stage241—245：独立信息初筛，只继续有限现货来源验证

- line_id：`futures_full_market_long_signal_ai`；2026-10-19 21:58 CST；非重要突破。上轮240是进展：6新模型反证并关闭固定target包，原goal active。当前439fit/234cash，本阶段新增0/0。
- 开始反思：新增按收益调参数否，反复历史择题风险是；继续来源去重/有限原始内容核有价值，不以新名称重开旧标量。

## 来源裁决

| 来源 | 独立信息及来源事实 | 决定 |
| --- | --- | --- |
| 商业现货S与真实期货F | S不是现有52期货摘要的确定函数；root真实取得2020日报42条数值报价，2011起点页却空。已有旧C9 high/low主力basis负证据，非全新未测。raw商品/原单位/品级与时钟待核 | 只继续固定小跨年覆盖，不用开源成品basis立即金融/批量history |
| CFTC COT | 类别数量非价格/总OI可唯一恢复，但MM和producer net/z已被其他线测过；实际延迟发布、早期分类回填与跨境代理未闭合 | 不迁移旧标量，不造release库，不投影或训练 |
| 本地期权隐含分布 | 真实期权报价可以提供新信息，但当前全链覆盖和时钟不足；结算价含交易所估值面，美式/欧式/指数标的不可统一套Black | 当前直接用免费结算价重建全市场skew的金融包否决；不否定期权概念，不重复旧稀疏probe |

独立spot可影响产品准入，不自动改善母内月份排序：共同logS在同product-u线性差中抵消。储藏理论讨论库存与风险溢价，不等于中国日级窄止损高胜率。参考[NBER原作者研究](https://www.nber.org/papers/w13249)；论文的部分spot代理是最近期货，不能拿它证明100ppi现金报价有效。

## 本次真实来源内容

241在web读取器失败后，冻结同两个固定URL各一次直连（15秒/128KB上限/no retry/no latest fallback）。session90693 exit0：2011页22,940B、2020页51,854B，两HTTP200、日期标题正确、完整无截断。stdlib解析显示2011 fdata仅3行/暂无数据/0正数spot；2020 fdata47行/42正数spot，包括铜49,140、螺纹3,705、锌18,610。两页显示16:30，但不是当年首发vintage证明；旧页共用后来烧碱脚注模板，不由此断言价格被回填。

独立agent以另一套stdlib regex/表深度方法读取两raw，各核SHA/日期/行数、三条机械价格、近月/主力文本与单位说明，coreblockers0。只接受内容一致性，不授连续历史、实际成交、同质品级/税费/湿干吨/结算与close等价或PIT。root最初bs4 import在读raw前失败，未安装环境、未重抓，改用stdlib成功；没有研究重跑。

[原站2020日报](https://www.100ppi.com/sf/day-2020-01-02.html)给S−F的说明；[AKShare维护者源码](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/futures/futures_basis.py)实际计算F−S，且有JD/FG/LH硬编码单位变换，不能直接采用其基差列。code许可也不等于数据再分发许可；当前只本地研究原件，不发布数据。42数值行不是42可交易品种资格。

COT常规周五并非实际发布日期；[官方历史异常公告](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm)存在2025数周补发，固定Tue+4天会偷看未发布数据。Stage243保留旧MM/PMPU失败，不以修时钟当alpha。[INE现行规则](https://www.shfe.com.cn/regulation/ineregulation/businessmethods/trade/202606/t20260622_832194.html)明确非到期结算含IV理论估值；244没有把现行规则倒推全部历史，也没有把所有期权数据声称必须付费。

## 下一行动及记录

选择一次按原日历机械选年的rawspot覆盖小批次，复用2020已得原页，保留暂无数据/HTTP失败/单位未知；不找收益最好的日期，不扩新交易池，不构造标准化basis或读取本机价格/标签。通过也仅允许讨论后续历史获取，不自动训练。其他两方向不继续工程。

代码/交易参数新增修改删除无；fit/cash/SQL/行情及分钟下载均0，权益/收益/DD/Sharpe/滑点/交易/胜率N/A。原target/q/OI/FX/会员/仓单等失败不重开，正式版/生产/Git/其他线不改，根总账不追加。

结束：新增收益调参过拟合否、历史适应性风险是；有限现货来源验证价值是，旧标量/期权结算面直接金融价值否。更高收益/更低回撤/高质量AI/窄损加注尚未证明，goal active。详见242/243/244及`outputs/stage245_novel_source_decision/decision.json`。
