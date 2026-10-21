# Stage601 WASDE逐份预测修订：不同于已关闭level包，尚非金融ready

- line_id：`futures_full_market_long_signal_ai`；2026-10-21 07:41 CST。
- 只读registry/LINE及直接相关284、289两份stage；本轮fit/cash/SQL/大表下载/模型/LINE改动全部0。非突破、非训练授权。

**判断：逐份原始发布、同作物年Production预测修订具有可辨识的新对象；本线未实测。只保留一个最小源合同，当前金融NO_GO，不能称数据已齐或PIT已认证。** 旧289关闭的是World Corn当份最新Proj `Ending Stocks/Domestic Total`＋发布当月单scalar offset：2fit后所有执行选择不变，4cash依法跳过。修订量不能由这个单时点比值唯一恢复；但若只对旧比值差分、改有效期/符号/映射救参，仍属禁开的旧包。

## 本次真实浏览的新证据

- [Cornell旧publication](https://usda.library.cornell.edu/concern/publications/3t945q76s)实际重定向到[NAL逐份归档](https://esmis.nal.usda.gov/publication/world-agricultural-supply-and-demand-estimates)，当前能列每次release的独立TXT/PDF/XLS/XML。旧USDA短URL403，正式新目录可访问，故不用猜旧CDN地址。
- 已从目录实际打开[2026-09-11原TXT](https://esmis.nal.usda.gov/sites/default/release-files/796054/wasde0926.txt)与[2026-10-09原TXT](https://esmis.nal.usda.gov/sites/default/release-files/796099/wasde1026.txt)：两份各有US CORN、2026/27 Proj、Production及Million Bushels；当份当前列分别15,800与16,034。只是证明一个同MY跨发布量可以读，不是全历史覆盖、首发不可变或收益证据；不能用10月表中的Sep列代替9月独立原件。
- [官方发布页](https://www.usda.gov/about-usda/general-information/staff-offices/office-chief-economist/commodity-markets/wasde-report)写明2026年12:00 ET，并标合并CSV在翌日更新。没有读取/认证CSV逐行vintage语义，既不把它当原始首发，也不武断声称它必定全量回填。
- 实读维护者[parser.py](https://github.com/fdfoneill/wasdeparser/blob/master/wasdeparser/parser.py)与[downloader.py](https://github.com/fdfoneill/wasdeparser/blob/master/wasdeparser/downloader.py)：parser日期fallback将月标题解析为月首，Excel页/格和部分列硬编码；下载`pull`未实现。只作解析实践参照，**不是可直接安装即得到可靠历史PIT的工具**，不复制其日期/页码假设。

## 唯一待授权的最小合同草案

只看**US Corn / Production / 同一marketing-year / 两份相邻自然月独立原始发布**：`x=(P_current−P_previous)/P_previous`。field/region/分母在收益前固定，不从stocks、use、yield、soy或cotton中挑最好项。取两份都明确Proj的最新共同MY；新作物年首次出现、Est/Proj不匹配、缺月、NA、单位/版本/范围歧义均unknown，不跨季强接、不补0。Million Bushels只与同单位配对；不混world的million metric tons，不以同名bushel对不同作物套一套重量，棉480-lb bale也不接入。

直接映射仅`DCE.C`，不顺带映射淀粉、大豆链、非转基因豆或棉。MY仅用于对齐预测对象，**不等于中国合约到期年**；全98/95母体保持，其他品种原基准原样。本轮没有生成特征或信号。

每份保存release ID/URL/原hash、实际release date、文件version/更正证据、表标题/作物/region/MY/Proj/单位/原数值与单元位置。归档“发布日期”不证明当前文件就是当年v1；文件名没有v2也不足。若只能取得晚出的更正件且更正时点未知，两份pair禁用。不可拿最新PSD、当前CSV快照或当前报告回顾列冒充历史原先值。

clock保留旧284的保守`release date+2自然日 America/New_York 00:00`，然后仅映射到其后原合格u及后继D；不搬到公告前中国交易日，不扫lag。ET随夏令时变化，不能恒用EST/固定UTC；更早历史具体release time尚未逐份认证。该保守date上界也救不了日期不明的v2。独立信息单元是报告pair，不是子合约/u日行；未来若获训练授权，重复暴露不得伪装成额外独立月报。

机制只是供给预测修订可能补充价格表示；它不是相对市场共识的surprise。价格和预测都可响应天气/需求信息；其他USDA数据同步发布，不能将反应因果归给WASDE单项。中国进口政策/内外价差会削弱传导；两日lag后消息也可能已反映。原Corn分数曾全部为负，不能为了让新量产生交易而放大系数/降低原门。

## 结论与停止边界

公共归档对上述小pair真实可达，故不因旧短URL403把所有通路判死；但历史版本、时钟和连续支持**未闭合**。仅此新对象可保留源层候选，不授权批量、提取器、fit或现金。若将来root另冻源审，应先复用已保存原件做极小vintage/字段验证，不重复已有58原件；没有可核的同MY原先值就NO_GO，不用最新版救。

新增/修改/删除策略参数与金融结果均无，权益/收益/DD/Sharpe/滑点/交易数/胜率N/A。开始/结束过拟合判断：本轮没有收益选字段或拟合，但同史反复择题风险高；开始/结束继续价值：**仅这个版本可辨识性源问题有条件值得，直接训练/扩全农业无价值。** 不把此次source判断称稳定alpha、生产资格或全目标完成。
