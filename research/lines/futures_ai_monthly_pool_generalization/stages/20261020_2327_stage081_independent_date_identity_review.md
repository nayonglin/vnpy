# Stage081 独立审查079本地日期与identity预检

2026-10-20 23:27；非重要突破版本。只读独审，不修改079/其他core/LINE/registry；未启动080或注入source。

实际1,206独立checks、0失败，P0/P1/P2=0。079工具SHA为cb81c976b1c862ed06d5b11ba2520c5bcbaa114779bf7d35784ca25d36fc4883，作者7TDD另复跑通过。081在读取079实现前，从原052 exact states∩056 unsupported∩054 native库存独立重建27events/27CSV/35links/15,948,783bytes及事前doc7/gap20分层；独立投影全部27CSV，rawSHA/stat/原始行数均一致。

全部35 providerlinks逐一复核exact epoch/source_trade_date/前共同source工作日、payload native、metadata年月与生命周期、binding/source_id、显式row identity、broad/day行数/首尾/无效OHLC/aggregate/target OHLC比较及全False资格标志。结果与079一致：22events有目标broad行（doc7全部、gap15），5events无行；35providerlinks为22有行、13空，所有空/reject仍在，没有收益筛选或provider合并。独立合成检查包括前夜21:00起点、跨周末至周一、15:00/15:01端点、9点前后、范围外行、重复时间和无效价格。

观察窗口是前一共同source工作自然21:00至D15:01、D09:00至D15:00半开；这不是交易session定义。22有行provider的broad聚合与当前clean exact日OHLC均不匹配，但不能仅据此推导按有证据exact grid筛选后也必不匹配，例如多余端点可能影响聚合。079/081可接纳为日期/identity盘点；有rows不等于已知标签、grid或历史PIT资格。是否按066/070对doc7做有界统一reference audit，由root另行决定，不增加时段假设救数据。gap20始终事前证据分层，不能混成已证时段。

旧058已知矩阵、060 robust矩阵、旧117 manifest以及039/042/055/056 core SHA在审前后不变。0grid资格、0C2结果、0source replay/injection、0fit、0label变更、0下载/订单/正式变更。策略/模型参数新增修改删除均0；权益、总收益、最大回撤、Sharpe、滑点、交易次数和胜率N/A。

调研读[pandas官方to_datetime](https://pandas.pydata.org/docs/reference/api/pandas.to_datetime.html)及[维护者GitHub源码](https://github.com/pandas-dev/pandas/blob/main/pandas/core/tools/datetimes.py)。判断：timezone转换须保留同一instant，解析失败须保留NaT/拒绝证据，不能补造或移位timestamp；SDK静态时段不充当历史制度证据。本次没有用软件文档推导历史session。

开始与结束过拟合判断均否：闭集来自缺失与本地库存，分层先于payload，不按收益/C2择样或调参。继续价值是：有实物资料的候选才值得下一有限规则审计；本轮不能因希望继续而降低身份、日线或历史规则闸门。若下一统一规则仍无可用输入，应如实收束。

证据：outputs/stage081_independent_date_identity_review/{review.json,checks.json,independent27_scope.csv,independent35_links.csv,independent_raw_sources.json,independent_raw_components.json,prebindings.json}；独立可执行脚本independent_projection.py及review.py。
