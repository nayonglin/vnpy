# Stage178 单批仓单历史全日报归档方案

时间：2026-10-19 03:12 CST；line_id `futures_full_market_long_signal_ai`。先读registry；仅新增本stage与 `outputs/stage178_warehouse_history_plan/plan.json`，不改LINE、registry、旧数据或代码。**只是范围/预算proposal，不执行网络、规范化、金融或安装**；0新fit/cash/SQL/标签/价格/大库/矩阵读取，累计409 fit / 218 cash。旧raw未打开/重散列，未全盘搜索，不是重要突破。

## 日期边界及完整预定集合

只读取052已绑定calendar（44824 B，SHA `57dd7f539d1cdbefb528978a6c7bd79b118790f933ce63c37b10747b999f9585`）及本线小元数据。该calendar有5587日、2005-01-04—2027-12-31，**未来日历不代表未来行情已完成**。accepted004母域manifest的calendar_scope为2010-01-04—2026-10-16，4074日/399252母行；052 scope同样end=2026-10-16。132 cache manifest仅证明1552456 native rows/9520 epoch，不独立给日期终点，因此没有借cache推断更晚日期。

建议起点 **2014-05-19** 仅沿171维护者JSON通路线索，为候选可取起点，不是已验证历史首日；终点严格为已完成研究母域上限 **2026-10-16**，不取today或calendar末日。两者之间052全部源日 **3018日=2798 JSON＋220 HTML**。整份日报全产品/所有原行，无赢家品种、年份或收益筛选；不是多轮锚点pilot，也不声称尚未请求的3018日已连续成功。

plan保存完整有序3018日期数组、年/格式计数及确定性生成定义/摘要hash：20251118前为 `https://www.shfe.com.cn/data/tradedata/future/dailydata/{YYYYMMDD}dailystock.dat`，此日及之后为 `https://www.shfe.com.cn/data/tradedata/future/stockdata/dailystock_{YYYYMMDD}/ZH/all.html`。每日期仅reuse或固定URL的一次new_get，完整action集合及净新请求集合各有canonical SHA；不换日期、格式、host或来源。

## 既有原文只复用，不重抓

172七日完整manifest/date_manifest已有HTTP200、原bytes/hash、URL及获取/响应元数据，复用20251113/14/17/18/19/20/21七日报。104 `probe_receipt.json` 与 `verification_receipt.json` 可交叉确认另外两个SHFE仓单日报：20200102（72764 B）及20230103（87908 B）；原status200/未截断/hash一致。规划仅读这些元数据，没有再读原文。

104“第三份仓单”是**CZCE20200102 XLS**，不是第三个SHFE日；作为已知但不纳入本SHFE通路的来源记录保留，不用它填SHFE，也不把会员排名raw当仓单。因此共 **9 reuse、3009净新GET=2793 JSON＋216 HTML**；已知复用原body共1005802 B。plan列每份原path/bytes/hash、原URL/获取与headers及证据文件，旧物不复制/覆盖。实际另签后，应在第一GET前一次核9份复用绑定；缺失或hash不符立即停，不默许改为重下载。已完成响应永久沿原日期状态继承，绝不整批重新抓已成功日期。

## 建议网络/磁盘上限与失败纪律

这只是待下一turn冻结的建议预算：单逻辑批、串行1并发、请求间最少1秒；最多3009 GET，自动retry=false、redirect=false、TLS verify=true，connect8秒/read20秒/每篇实际35秒，整批wall cap4小时。首次HTTP/网络/TLS/重定向、异常envelope、显式正文日期冲突、bytes或wall上限即停；保存失败响应/异常/截断状态，其余日期写not_attempted，不换代理、cookie、账号、证书策略或第三方源。正文缺日期可忠实归档为absent，不伪造首发时点；明确冲突则失败停批。

单原文上限沿172为5 MiB；**全批新增response body硬上限512 MiB**，超限探测至多额外1 sentinel byte，即536870913 B。请求/TLS协议开销不在body字节计量内。建议元数据另限64 MiB；新增原body按原样plain保存，旧raw只引用，不建重复副本。因全局guard，新增raw＋metadata最高603979777 B，远小于3009×单篇5 MiB的形式和；达到任一guard就标未完成，不自行放宽。

仅以已知5份JSON/4份HTML的body均值按格式外推，净新原body约 **290862724 B（277.39 MiB）**；所有新篇都按当前已见最大134762 B外推约 **405498858 B（386.71 MiB）**。二者只是容量估算，不是历史大小上界或成功保证；硬上界仍以上述global guard为准。172七篇耗时12.5264秒，按其平均及1秒间隔外推约8393秒，亦非ETA或连续可得保证。

逐日journal须预建全部3018状态，记录frozen序号/URL/请求日/格式、原获取起止、HTTP headers/status/exception、原body或明确截断前缀、bytes/body hash、正文日期及archive clock、复用binding、全批started/terminal。失败结束当前批，不自动resume；之后若root明确另签续取，只能继承已完成证据、处理被授权的未完成域，不改原记录、不暗重试或重抓成功日期。失败不能报告完整历史。

## 不变的科学限制与后续决定

WGHTUNIT/WHTYPE代码没有codebook不妨碍**忠实保存原文**，但绝不降低172/173/174的物理单位/类型认证要求：旧码仍unmapped，不以新HTML或期货乘数回填，不填0，不把税类汇总当逐leaf已识别。不同年代/格式/warehouse-factory-bonded/覆盖与时钟以后另审；按日归档成功也不是首发PIT、全六所来源、可比物理库存或alpha资格。此方案不做normalize，不冻结feature/lag/基准窗口/方向、模型、标签或现金；未来条件研究另签，98代码/六所完整母域不因SHFE来源缺失而缩小。

root通知175已接受174七日算术，但那不自动授权此历史采集；root认可本文件为下一批范围proposal，将下一goal turn另签单批协议。当前没有采集脚本、真实GET或自动启动。

最终plan **82071 B**，SHA256 `06129933ce2c892d6855ae7ba499a63b36b1b4bc4503c0163e4ee9cbc83d69b8`。其中包含全日期集合、9复用证据、1个CZCE排除记录、所有输入metadata绑定、精确新请求集合定义及预算；本stage与plan为本分工全部新增物。

开始/结束新增过拟合：**否，范围由候选source起点和已完成研究终点机械确定，不按金融结果选年/品种**；长期研究择题与归档回填风险仍在。继续价值：**有，限root另签的一次有界全日报忠实归档**，不是单位补证无限工程或自动金融；是否进入条件研究须在实际覆盖/unknown及独审后另决定。原完整long目标未达成，不加注。
