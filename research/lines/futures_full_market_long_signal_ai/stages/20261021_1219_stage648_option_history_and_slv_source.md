# Stage648：期权历史排重与SLV官方份额原件有界核验

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-21 12:19 CST；工作区：`/Users/mac/Desktop/fian`。
- 阶段性质：原始来源与历史字段核验；非重要突破；不触发A/B；不交易期权、不改正式C9。
- 本阶段新增fit/cash/Y/native/行情/model/SQL读取、分钟/BBO、新依赖、参数及回测结果均0。继承root计数551fit/294完成cash及1旧partial，本648不增加计数。

## 裁决

**期权价格skew当前仍NO_GO；新增来源SLV官方Shares Outstanding历史已实际取得，仅源级GO，不自动训练。** 不是所有期权信息已实证失败，也不把源级成功当收益、窄损加注或生产资格。98历史产品/95family全母域与原fallback保留。

先读registry并只按关键词定位本线LINE，继而读取244、501、570与573指针。244已明确知道郑商所年度TXT及其完整字段，570/573关闭同一结算面skew重复资料方向；没有期权金融回测反证。本轮再见同一下载路径，并没有新的完整链、历史行权规格或发布时钟证据，故不重开、不取期权日链、不写IV系统。六所上市边界、商品/指数标的与结算模型面等既有约束仍保留，不再次穷举目录。

## 原资料、GitHub与判断

1. [SLV官方产品页](https://www.ishares.com/us/products/239855/ishares-silver-trust-fund)明确列Shares、吨、盎司及`Data Download`。网页吨/盎司按trade-date activity，bar list按accounting date，二者不可替换；本轮实际下载由该页面观察到的官方链接获取，未从第三方拼地址。
2. [官方Data Download原件](https://www.blackrock.com/varnish-api/blk-one01-product-data/product-data/api/v1/get-fund-document?appSubType=ISHARES&appType=PRODUCT_PAGE&component=fundDownload&locale=en_US&portfolioId=239855&targetSite=us-ishares&userType=individual)实读为XML Spreadsheet：`Historical`只有`As Of / NAV per Share / Ex-Dividends / Shares Outstanding`四列；确有2006-04-21—2026-10-20的历史份额，**不含历史吨/盎司**。
3. [SLV 2024官方10-K](https://www.sec.gov/Archives/edgar/data/1330568/000143774925004259/slv20241231_10k.htm)说明AP用实物白银申赎、费用售银，以及NAV/Basket金额通常纽约16:00后计算。这支持“份额是净发行/赎回数量对象”，不支持“当日吨数差就是净资金流”；16:00也不是Shares网页发布上界。

维护者GitHub核验：[AKShare期权年度源](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/option/option_czce.py)仍是244已审CZCE年度路径；[macro_cons_silver源码](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/economic/macro_constitute.py)实际调用Jin10分页，不是iShares官方原件，且docstring沿用错误的Gold Trust/2004范围，不能拿其注释认证白银历史。未安装、clone或执行库。

## 实际获取、错误与字段验收

- web工具点击官方Excel时只报告不支持Content-Type；本地沙箱首次尝试DNS失败，无HTTP响应。随后一次出沙箱GET成功，1,889,085B、8.4311秒，但严格ET解析失败且未保存raw；这一可避免的失误已向root明确报告。
- root明确授权一次解析恢复，第2次GET≤2MiB/15s、3.9688秒、HTTP200，保存原件后本地解析；两次成功响应SHA完全相同，无第3 GET、无每次内部HTTP重试。原件SHA：`b89cf4141b56f072bbc11be181b4d1d0095706e4c5a58accda710f70137cede9`。
- 原件附件名`iShares-Silver-Trust_fund.xls`，声明`application/vnd.ms-excel`，实际是ss:Workbook XML。严格错误`line47,column138`位于免责声明超链接未转义`&`。保留原字节，按literal ss:Worksheet/Row/Cell/Data标签提值、解码实体；未修XML、推断缺失或改数值。
- 三张表：Disclaimers14行、Historical5161行（表头+5160日期）、Performance265行。历史5160日期全部唯一且严格降序；5158个正整数Shares；2024-03-29及2024-03-31为`--`，其中03-31为周末。全部历史数据行4列，缺失保留；没有交易日历完整性证明，不称逐交易日无缺口。
- 最新2026-10-20 Shares552000000，最早2006-04-21为1500000。只作原始字段核验，不从NAV反算资金流、吨数或可交易收益。

## 时钟、调整和许可

`As Of`是经济归属日期，不是当年首发时间。本次HTTP Date/接收时刻只绑定2026-10-21本次文件；当前下载是可修订归档，未获历史首发字节与发布时间上界。**严格PIT未知；可明确标注保守滞后假设做条件历史研究，但不能改称当年实际已知。** 不为了追求理想源而要求所有条件研究停止，也不默认美盘日期能在中国同日日线收盘或夜盘前使用。若root继续，先固定完整美国会话滞后、时区/节假日与原next-D规则，不扫描lag择优，严格PIT与条件口径分别报告。

[2009原10-Q](https://www.sec.gov/Archives/edgar/data/1330568/000119312509106967/d10q.htm)确认2008年7月23收盘后10:1拆股。归档7月23—25 Shares都199500000，提示统一调整后口径，仍不能由三行签全历史修订规则。2020以后的拟议研究不跨该事件，但不能冒称2006原始首发。Shares不同于GLD存量吨数，净发行可能反映投资需求/做市套利；不包含最终投资者主动方向，正负alpha尚未知。

原件Disclaimers和[官方条款](https://www.blackrock.com/corporate/compliance/terms-and-conditions)只给个人非商业下载并保留权利声明，未建立开放数据或公开/商用再分发许可；自动抓取另有限制。仅保存私人研究原件，不建立定时抓取或向外发布源数据。本轮未把AKShare代码许可扩展到上游数据。

## 有界下一步与反思

建议不再下载：独立核已存原件的Historical字段、5158有效份额/2缺失、拆股/修订解释一次；若通过，由root先冻结一个Shares数量命题与明确标为假设的保守时钟，再决定是否做唯一无Y的可用性对照。直接经济关联最多先指向SHFE.AG，其余母域不伪造白银观测、不删除；不能复制到所有98产品后宣称全市场信息充分。当前不预签方向、窗口、阈值、风险或任何新fit/cash预算。

- 运行前/后新增按收益调参过拟合：**否**；未读Y/新收益或选择最有利日期；长期同史多轮择题风险：**是且高**，新源不能消除此风险。
- 开始核验继续价值：**是**；结束本次来源核验：**有价值且完成**，实际得到长期官方份额；重复期权archive/skew资料包价值：**否**；完整高质量long目标继续价值：**是**。
- 新增/修改/删除策略代码、参数、回测结果均0；期末权益、收益、回撤、Sharpe、滑点、交易数、胜率均N/A。无订单、生产、Git变更。

输出：本stage、`outputs/stage648_option_history_and_slv_source/decision.json`、`slv_official_fund.xls`、`slv_probe_receipt.json`、`slv_local_field_audit.json`。只写本648唯一记录和有界源证据，不改LINE/registry/根memory/back_log/其他研究线。


## root要求的必要规范化交付（2026-10-21 12:22 CST）

不再GET。保存`daily.csv.gz`全5160原顺序行，含ISO date、sheet、原source row、AsOf literal、Shares literal/parsed、missing_state及NAV/Ex-Dividends literal；NAV仅溯源，不作信号。73,203B，SHA `0dfc76c172793134fb6d7a184da906c1c07cc14397eee2db8ddb4e5bd47ff72e`。`manifest.json`保留字段、状态定义、raw/daily身份、时钟/修订与许可边界；`split_evidence.json`为已实读SEC原页的来源笔记，非另行下载原件。

为排除宽容提值漏行，直接将**未改字节的Historical完整片段**置于外部命名空间wrapper中，标准ElementTree严格解析成功；该数据子树无非法`&`，全部5160数据行都保留。Performance也严格通过；仅Disclaimers片段含6个未转义`&`，严格错误位于超链接属性元数据，不在Historical值。此次规范化由严格Historical子树生成，不靠修补值；未应用拆股因子、没前填或删2个`--`。原XLS保持原SHA。Stage650独立复核待定，source_ready只指物料可审，不是alpha准入。
