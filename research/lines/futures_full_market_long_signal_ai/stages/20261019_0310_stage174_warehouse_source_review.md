# Stage174：连续七日报仓单原文与新解析的独立审查

- 时间：2026-10-19 03:10（Asia/Shanghai）。
- 研究线：`futures_full_market_long_signal_ai`；先读registry、当前LINE及171/172，未读取旧原文、模型、策略或金融结果。
- 类型：冻结七报告日source-only小量全表审查；非重要突破，不是金融/backtest或新模型版本。
- 结论：**这七份官方归档原响应到173新解析的数值、物理行身份、字段/层级/来源及unknown保留通过；不认证跨格式物理单位、全历史覆盖或首发PIT。**
- 174完整新输出复核：**C/I/M=0/0/0、errors=[]，0.219514209秒**。root唯一173 actual exit0、0.323070333秒；本agent没有启动173或重跑其解析。
- 新增fit/cash/SQL/network/价格/标签均0；累计仍 **409 fit / 218 cash**。本stage无新增权益、收益、DD、Sharpe、手续费、滑点、交易次数或胜率，均不适用；不从旧金融结果借成绩。

## 固定范围与独立方法

172在取数前冻结2025-11-13/14/17/18/19/20/21，前三日JSON、后四日HTML。root每日报告一次普通公开HTTPS，七次HTTP200 expected envelope、合计845,130B，用时12.526406209秒；未重试、挑战绕过、全史抓取或取价格。174独立一次读完这七个body，并核各自原bytes/SHA；未重复下载、未重新读取七body。原响应继续保存在172原目录。

174先独立用标准库JSON/HTMLParser形成小型原字段/物理cell与span基准；依据显式header做独立逻辑网格、数值与层级参考。原文检查完成后只使用本缓存参考对173全部新输出一次核验，**未import173计算函数**，未采用维护者silent coercion、当前合约乘数或新单位反填旧值。复核3736 normalized rows、全部1560 intra checks、609 adjacent checks、7 report_schema、summary、inputs/source/artifact bindings；没有新通路/URL/codebook搜索、安装bs4/lxml或运行JS。

| 请求日 | 原格式 | 完整物理行 | table数/载体 | 正文报告日检查 |
|---|---|---:|---|---|
| 20251113 | json | 479 | JSON o_cursor | matches |
| 20251114 | json | 479 | JSON o_cursor | matches |
| 20251117 | json | 479 | JSON o_cursor | matches |
| 20251118 | html | 574 | 34 | matches |
| 20251119 | html | 574 | 34 | matches |
| 20251120 | html | 574 | 34 | matches |
| 20251121 | html | 577 | 34 | matches |

七期编号209—215、总期编号4159—4165与本固定序列连续，只说明**本七日报告**的这段序列，不外推2010+或2020+覆盖。JSON的report_date/o_tradingday及HTML intro日期均与请求日一致；请求日期、正文报告日、归档update_date、HTTP头和2026取回时点分别保留。

## 原始语义与单位边界

前三日每日报479个JSON rows，共1437行；每日报23个VARID、31个原产品/类型组。原字段有 `WGHTUNIT`，代码分布每日报1为7行、2为447行、3为25行；有 `WHTYPE`，1为405行、2为74行；`ROWSTATUS`0/1/2分别373/76/30。不能把“没有单位文字”写成“没有单位字段”。本次没有正式codebook，**代码的物理语义保持unmapped**；不能按后四日吨/千克/桶或合约报价/乘数倒签旧值。厂库产品名可明确记录其原文厂库字样，但不据此认证所有WHTYPE历史代码。

后四日各34 tables，含1 intro与33产品/类型表；每日报30张表明确单位吨、黄金/白银2张表千克、中质含硫原油1张表桶。33表相对旧31组多出胶版印刷纸仓库/厂库，不把旧无行补0。源由SHFE网站发布但内容含部分INE品种；不按网站宿主把全部产品强归SHFE，也未自动投到98目录代码/逐合约、普通/F两份库存。

仓库、厂库、保税/完税总计保留原文口径。厂库登记不自动改称现货实物库存；“期货”列与SC“本日数量”列的真实字段名分别保留。原注“期货为已制成仓单的货物数量”是本表口径，不证明全社会库存、总供需或方向alpha。

## 全部物理行与数值来源

原3,736行全保留：2698 leaf、548 region_subtotal、21 bonded_total、14 duty_paid_total、183 grand_total、8 intro、132 column_header、132 section_header。真实数字行3464，每行quantity与official_delta合计 **6,928个数值cell，6,928个唯一原值origin**，逐项核原值、原类型、Decimal精确字符串、明确0/非0状态、列名、source row/table及span来源。JSON quantity/delta原值均为int；不随意转换异常为0。

quantity统计numeric_zero1864、numeric1600；official_delta统计numeric_zero2870、numeric594。每field另有8个intro missing_field及264个列头/单位标题parse_failure。**这264个parse_failure都来自被保留的元数据文字，不是测量行失败；测量行parse_failure=0。** 不为展示名称重跑或改173摘要。

独立特别核了：

- 胶版印刷纸厂库表头为“厂库/地区”，不能固定第一列地区、第二列仓库。
- 氧化铝厂库11月21日也反转表头，并增加原leaf context；必须按header取值，不能用前一日列位填齐。
- 黄金位置cell colspan2，地区与仓库合并上下文不能冒充两个独立地点；其原合并来源保留，地区state为unknown。
- 螺纹/热卷/低硫厂库等地区或“厂库提货地”rowspan仅提供上下文，不能把继承数量重复计作leaf；qty/delta origin逐项核。
- 铜/铝有保税总计、完税总计与plain总计重叠；燃料油保税总计和plain总计也覆盖重复。不能分项+小计+总计重复累加。

## 表内与相邻报告的全部诊断

所有plain总计与不重叠leaf的数量/增减核和，旧JSON3天150项数值一致、新HTML4天216项一致；旧部分仅同原码内算术，不认证物理单位。173更完整的全部诊断也已逐项独立核：

| 检查域 | 总数 | primary状态 | 纯算术状态 |
|---|---:|---|---|
| intra | 1560 | match870、unknown_unit618、unknown_tax_leaf_coverage70、unknown_no_leaf_coverage2 | match1488、unknown72、mismatch0 |
| adjacent | 609 | match331、unknown_unit212、unknown_coverage66 | match543、unknown66、mismatch0 |

税类leaf没有独立完整保税/完税标识列；个别仓库名含(保税)不能据此把所有无标记仓库自动列为完税。因此70项保留tax_leaf_coverage unknown；原明确的“保税+完税→总计”只能作为单独partition_sum诊断，不能宣称leaf税类已识别。

intra另2项unknown_no_leaf_coverage来自11月21日氧化铝厂库“四邦实业”跨甘肃/新疆rowspan内的“合计”落在地区列；简单地区分组不能确定该厂库小计叶范围，原值和来源保留为unknown，没有制造总计或补0。黄金、不锈钢厂库等原无独立总计，仍保留原单leaf，不创造一个新“官方总计”；部分表只有合计，不能强迫每组都有grand_total。

相邻原官方delta与相邻总量差**分别保存**，只有同scope、同单位口径、完整leaf context覆盖一致才做相减诊断；绝不把差额反填官方delta。跨格式11/17→18，因为scope包括原格式/品名/代码/类型/单位原值，31+33共64项保留unknown_coverage；没有通过数字相似或名字猜测强合并。

余2项unknown_coverage是11/20→21：氧化铝厂库增加“四邦实业(甘肃/新疆)、厦门国贸同歆(河南)”三个原context；丁二烯橡胶厂库原名称“四邦实业(浙江)”变成“四邦实业”。后者即使看似同一家也未手工归并。这里的unknown是诚实覆盖限制，不是应靠丢行消除的错误。首日不造前日，官方增减可能对应的更早报告本轮没有取；未据七日季节变化推交易方向。

## 时钟、物理及历史资格不升级

JSON update_date原文分别为 `20251113 15:13:00`、`20251114 15:06:04`、`20251117 15:11:00`；它们及当前HTTP Last-Modified只能作为归档字段，不能证明2025首次发布时间、历史补发/更正版本或可交易时点。HTML报告日/期号也不证明首发时分。2026获取2025归档不是vintage首发字节，不假设某个任意lag就消灭PIT问题，夜盘跨自然日亦未解决。

HTML `explicit`单位表述与check内declared-unit标志，只表示本表写明单位，不认证所有仓单都是等质实物、全部厂库义务、交割资格或流动性。本次独审通过不把unknown_unit、coverage、tax context、历史覆盖或首发PIT消除。receipt保持 `unit_codebook_known=false`、`cross_format_physical_join_certified=false`、`strict_first_publication_PIT_established=false`、`historical_coverage_certified=false`、`training_authorized=false`、`financial_authorization=false`。

## 反思与有限终点

开始/结束新增按收益调参过拟合：**否**；七日及跨格式节点在看新策略收益前固定，本轮无策略、符号、归一化、窗口或模型选择。但历史选题、最终归档与覆盖差异风险仍在。

继续价值：**这次有限源/解析核验有价值，已完成；继续本批补码表、扫年份、扩六所或直接训练/金融没有本轮授权。** 本七日“可取且可保真解析”与“可形成长期PIT、经济同口径特征”是不同证据等级。root可据上述精确未知决定是否另冻最小下一步；不能自动启动fullbatch、恢复旧q、改变原目标为少数有仓单品种或加注。全市场研究目标active，本stage不声称目标完成、生产合格或alpha成立。

新增/修改/删除科学参数均无；只新增本唯一174记录和本子目录的小型独立原表参考、checkpoint、receipt。没有改变171/172/173源、输出、LINE、registry或其他agent文件。外部资料沿root本轮已读SHFE官方入口与维护者源码；174遵守0web/0download，不重复旧三日或另联网追codebook。

## 可核资产

- [172事前协议](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage172_warehouse_pilot_protocol/protocol.json)：3432B，SHA `7359cd6fbd9d1bbf65d30dd89b8b4b2d7da4d49463de2018d737814a39b17b00`。
- [172七原文manifest](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage172_warehouse_pilot_raw/actual_run1/manifest.json)：5362B，SHA `1460d64762d6e90822aeb7bca3a96299574df3e149721c6548debc08b8c7f545`；包含所有官方原URL、取回时点、HTTP头与bytes/hash。
- [173新解析manifest](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage173_warehouse_normalize/actual_run1/manifest.json)：7236B，SHA `ca601bd185d732c66e9cb650f090e9b8aede9b7b77707760666de6dd5db812fe`。
- [173最终源码](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage173_warehouse_normalize.py)：25747B，SHA `350d74fb8373aaa9bd2b980db7c0051efedfd0754225194ff5671ac2972e1db2`；7有限fixture由作者/root核，174未重复运行。
- [174原物理参考](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage174_warehouse_pilot_review/independent_raw_reference.json.gz)：56983B，SHA `3cd8307fb3ac8b03ed07b08fd3be26f22ed4b9028cb4a9b5e2e32badd3f43b4b`。
- [174独立语义参考](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage174_warehouse_pilot_review/independent_semantic_reference.json.gz)：108226B，SHA `12ce31a1586a22822b6b7524cdd06deb91805dc6b4ad0015d25e4db65210af01`。
- [174原文阶段checkpoint](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage174_warehouse_pilot_review/raw_review_checkpoint.json)：5633B，SHA `6558ad8769b1d286ff6592d507984998cf4c5d9123bfc42124fb90aa759a79a4`；其parser_pending是当时真实状态，不事后改写，最终完成以receipt为准。
- [174最终独立receipt](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage174_warehouse_pilot_review/receipt.json)：12078B，SHA `520c9aea78dc30fe08c5fcf0b77dd3b35bbebececbf88e6914f4001f08fa7022`；C/I/M0/0/0、errors=[]，全部有限新输出通过。
