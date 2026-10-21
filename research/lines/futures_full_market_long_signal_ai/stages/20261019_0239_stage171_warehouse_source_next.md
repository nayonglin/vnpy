# Stage171：仓单连续历史通路的最小可行性判断

2026-10-19 02:39 CST；line_id=`futures_full_market_long_signal_ai`；非重要突破，只做 source 事前判断。先读 registry 与160；沿用104仅有三日、非连续本地材料的已知事实，不全盘搜索、不重查六锚点。registry尚未合入最新阶段，以root刚完成168/等待169的事实为准，不改索引。固定q包关闭，不改lag、HHI、模型或K；本轮不根据新收益选仓单品种/时期/变换。

**结论：SHFE官方按日仓单原表值得一次有限 source 试取；当前不具备直接金融条件。** 连续历史有明确地址/解析分支线索，但本轮没有取历史日报，故不声称2010+训练或2020+执行连续可用。CZCE/DCE列为待取通路，本轮阻塞即止，不换第三方成品补洞。

| 通路 | 本轮一级证据 | 尚缺什么 |
| --- | --- | --- |
| SHFE | [官方日周入口](https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/?query_params=dailystock)明确分开仓单日报和库存周报；[维护者详细实现](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/futures/futures_warehouse_receipt.py)给出2014-05-19起JSON、2025-11-18起HTML分支及仓库/厂库、合计/总计层级 | 各年代原表单位、类型与总计语义、连续成功率、首发及修订时间。本轮只读页面/代码，未验证任一历史数据响应 |
| CZCE | 同一详细实现按日期构造官方 `DFSStaticFiles/Future/{year}/{date}/FutureDataWhsheet.xls`，2025-11-01后改xlsx；[官方入口](https://www.czce.com.cn/cn/jysj/cdrb/H770310index_1.htm)本轮412 | 现通路可取性未知；代码的verify=False不照抄。格式切点是维护者实现证据，非交易所历史生效认证 |
| DCE | 同一实现以tradeDate/all访问官方 `dcereport/publicweb/dailystat/wbillWeeklyQuotes`，保留仓库/分库、可选提货地点，数量标手；明确遇412抛错。[官方入口](https://www.dce.com.cn/dce/channel/list/187.html)本轮超时 | 不证明现接口可用或历年单位恒定；不绕验证、不试账号、不自动重试 |

不能直接采用维护者聚合结果：[`receipt.py`](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/futures/receipt.py)含两个SHFE历史日硬编码，并标记另两个历史日缺失；CZCE若干解析异常分支写0。这些是接口定位/反例，不能当已核验官方观测。须保留原表及解析状态，不把异常零、无行、未上市或不适用合并。GitHub使用可变main，只完成静读，没有安装/执行库或取得可复验commit/原字节hash。

时钟有一条有限历史主源：[CZCE2018年第56号、2018-10-08施行的交易细则](https://www.czce.com.cn/cn/rootfiles/2018/09/28/1538460464633765-1538460464684431.pdf)第35条把标准仓单数量/相对上次增减列入每日信息，并规定交易日结束后发布。它未给精确时分、异常补发或后续修订上界，不能延伸认证2010—2026全区间。SHFE/DCE本轮未取得同等明确时钟证据。报告日期、首次可得、当前获取及历史回填/修订须分开；URL日期、当前Last-Modified及人为滞后一日都不是首发PIT证明。夜盘跨自然日也不能以报告日字符串消除。

仓单是价格/OI不能唯一恢复的登记交割状态；国内指定品种/地点/资格也不同于已测EIA美国实物库存。相同价格、期限、OI、类别及席位集中度，可对应不同登记量，故有独立信息先验。反机制是货权登记、注销换单、厂库担保、保税/完税、强制注销和交割季节都能改变数字；可交割登记量不等于全部实物库存、总供需或看多强度。[已读官方标准仓单指引](https://www.shfe.cn/services/delivery/warehousewarrant1/)支持这个语义限制。库存风险溢价论文只作先验，不能证明本策略alpha；本轮不冻结方向、窗口、归一化或新特征。

下一步只建议 **一份SHFE跨格式的连续7报告日source pilot**：事先按既有052calendar固定含2025-11-18的2025-11-13/14/17/18/19/20/21七日；每日报告一次获取全表全部品种，不挑CU/RU等收益赢家，不获取价格或SQL。旧三日不重做。较早日期地址模板为 `https://www.shfe.com.cn/data/tradedata/future/dailydata/{YYYYMMDD}dailystock.dat`；新段为 `https://www.shfe.com.cn/data/tradedata/future/stockdata/dailystock_{YYYYMMDD}/ZH/all.html`。这仅提议后续动作，本stage未执行，不借七日声称全历史覆盖。

该pilot只交原响应/URL/获取时点/HTTP状态/bytes/hash与逐表字段收据：报告日、原品种名、warehouse/factory/bonded类型、单位、仓库/地区、row层级、数量、官方增减、原总计；核总计不重复计数，原增减能否与相邻同口径数量核对，空白与明确0分开。不由期货报价单位猜仓单单位，不将手/吨/千克/桶混用，不凭当前合约乘数回填历史；类型/单位改变须unknown，不能为了连续强合并。

停止条件：普通公开访问被阻挡即保存失败并止，不绕证书/反爬；若七日同口径总计/单位/日期无法核对，或所有可用原文仍无法形成可诚实声明的可得时钟假设，则source no-go，结束此批，不扫全版本/六所/年度包。pilot成功也只允许root再决定有限历史覆盖动作，不自动金融。全市场399252母/98代码/六所必须保留；无制度、无源、未上市/不适用和未知分别记录，两臂共享缺失，不能只保留有仓单品种。普通/F不自动别名重复计样；product观测也不是每个交割月的独立库存。

本轮严格两组各3query，必要官网/维护者小源码与一份16页规则PDF仅web文本读取；未落地历史日报、未历史bulk、未试账号/价probe。0fit/cash/SQL/标签/下载，现累计409fit/218cash不变；权益/收益/DD/Sharpe/滑点/交易数/胜率均无新结果。只新增本stage。开始/结束新增收益调参过拟合：否；同史择题及归档回填风险仍是。继续有限source pilot有价值；立即金融、无限资格工程或救固定q包无价值。169未终审，不写accepted，不加注，完整目标未完成。
