# Stage277：接受部分WASDE原件和163期数量，尚未进入金融实验

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 01:05 CST；非重要突破、非正式候选。
- 上一goal轮为progress：269完成四候选现金与268独审并关闭S过滤。本轮也有实质进展：真实取得原件、构造新物理量并独立复算；不是仅改计划或重复旧成绩。完整目标仍未完成。
- 本阶段270—277新增fit/cash=0/0；累计439fit/238cash。未改止损、风险、旧模型、原结果或正式版，金融指标全部N/A。

## 调研判断与选择

270独立否决EBP单列/统一信用veto：机制不同于VIX，但原[Fed说明](https://www.federalreserve.gov/econres/notes/feds-notes/updating-the-recession-risk-and-the-excess-bond-premium-20161006.html)允许全历史修订和发布延期，又缺产品异质融资暴露，当前不值得开金融包。这不是回测证明全部信用信息无效。

271核[USDA历史vintage入口](https://www.usda.gov/historical-wasde-report-data-3)及[维护者wasdeparser](https://github.com/fdfoneill/wasdeparser)，只保留世界玉米仍为Proj的预计期末库存/预计总消费状态。排除由期货派生的农场价、跨作物扫描和“修订=意外”的解释，未复制旧解析器的月初日期或未实现下载函数。

root核[NBER原论文](https://www.nber.org/papers/w13249)：库存状态与便利收益/风险溢价有关，同时基差、价格动量已反映库存信息。判断为这项数量有区别于已发生EIA库存创新的含义，但不天然有COMMON52之外的预测增量，也不是严格外生冲击。未来营销年预计库存不等于实时库存或交割月预测。

## 真实数据结果

|项目|实际结果|
|---|---|
|官方目录原件|161116B，HTTP200；真实链接冻结2ZIP+69月CSV=71|
|下载进程|session22590实际exit0，但业务stopped_early|
|请求/保留/失败/未试|51 / 47 / 4 / 20|
|成功原件字节|48,332,328|
|源CSV/member|2汇总ZIP成员+45独立CSV，共47流|
|原始全部行|843079|
|Corn/World原字段行|3612，带source/member/行号|
|报告数量|172|
|符合固定数量定义|163|
|报告未知|2010九期不满足最高本期唯一Proj条件，保持unknown|

成功源跨度2010-04至2024-10，并非完整覆盖至今。2023-01发生SSL EOF，2024-11/12及2025-01连续连接重置后按规则停止；不把传输失败称“报告不存在”。目录未列2025-10另记；两ZIP内未观察到2013-10/2019-01报告，不从月槽推断发布或编造日期。24个失败/未试源月、1目录未列月、2档案内未观测月分开记录。

实际统一16字段包括WasdeNumber、ReleaseDate、ReleaseTime、MarketYear、ProjEstFlag、ForecastYear/Month。日期使用明确ISO或US MM/DD/YYYY；旧时间原样保留。数量仅精确World Corn Supply and Use/Corn/World/Annual，本期forecast年月、最高营销年且仍Proj；唯一Ending Stocks / Domestic Total，百万公吨、S>=0/U>0，Decimal精度50。不按结果补缺/修方向，不从更低Proj替换更高Est。

候选可用边界为release date+2 calendar days的NewYork00再转UTC，属于主动延迟假设，不是历史HTTP首见证明。当前无daily/futures join；未知新报告不carry旧量、无真实日期的缺源月不造release。V2两期本批未取；以后若取得，仍保留更正known_at未知。

## 独立验证和边界

275唯一source提取session9281实际exit0/3.911381秒，3有意义合成检查通过，无旧suite/金融重放。作者每成功CSV/member一次流；root早先必要schema探读（两ZIP目录/前三行，2021Jan前三行及全CSV实体确认）另披露，不冒称原件仅被打开过一次；没有额外完整性重hash。

276独立审阅进程exit0，core0：3612原Corn行、172报告、163有效数量及NY延迟时钟全部重算一致，Decimal差0E-50。固定2010-04、2016-01、2021-01三个原件样本完整16字段/出处一致；第四固定2026-10未取得记unknown，没有换样本。仅接受来源投影/算术一致性，不授历史首见PIT、可交易性、alpha或训练上线资格。

新量只直接对应DCE.C，其余97产品与完整98研究域均保留；没有把全市场任务缩成玉米单品收益任务。163期报告不是大量独立日样本，相邻预测相关，不能把同一预测重复到多合约/多天后充作独立证据。

## 下一步及反思

1. 优先20份尚未尝试的官方原href，下一阶段另定一次预算；复用47成功原件和本量表，不自动重启旧采集、不为四个小缺口反复修补。
2. 后续原件只增量提取，保留V2/无日期/月缺口unknown。先处理日级状态可知边界/缺源月，不以旧量填补2025—26测试期。
3. 数据足够后才收益前冻结一项线性offset：原52模型系数/截距不动、无新可学习missing/ID，缺源修正0。必须预测129完整前向动作/母体，允许原非正转参与，按原D<K选择；不能只过滤旧4365信号。原157四控制精确复用，不重放。原fold没有有效数量变异时unsupported，不从main借系数充held泛化。当前尚未冻结或运行offset、cash/CI预算。
4. 继续以全账户成本后收益/回撤及不确定性评价，不据数据源质量缩小止损或加注，不重开269失败S窗口。

开始/结束新增按本轮收益调参过拟合：否，本轮没有新金融结果；长期同史适应性选题风险：是。继续有限取得未试新源并检验单项增量：是；扩作物/变换/时钟/阈值救参、无限来源资格工程或正式晋级：否。完整全市场高质量long、更高收益更低回撤、极窄损及增加投注资格都未证明，goal active。

本阶段新增数据预算/数量定义和原件，修改/删除旧策略参数及回测结果0。期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率全部N/A。

[276收据](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage276_wasde_projection_review/receipt.json)；SHA `0d33f61f820630a8795ad07b39bfa7e7c24a049fd2b4e880a62ebbdfd0ef3064`。
