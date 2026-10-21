# Stage402：原周报共同生育暴露不足，固定天气面板规格NO-GO

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 14:32 CST；非重要突破，是有明确停止边界的来源资格结果，不是策略收益结果。
- 先读registry、400盲提案、401scope及2019年报日程修订；随后绑定root403正式协议SHA256 `a82d624d870e4e6f748644b6e61e6818d020f61255a3f0de7b14538a785a8f60`。与正式C9、月度AI池、原361/359/375前瞻账本隔离。
- 开始反思：本阶段没有查看新天气数值、金融标签或收益，不按结果选年/州/阈值，直接调参过拟合否；长期同史适应性择题风险仍是。一次整理原报告覆盖有价值，因为可以在昂贵天气下载和拟合前证伪本规格的可测样本量。

## 结论与实际数量

**NO-GO：400/403这一固定规格在原报告阶段已不满足最低样本量，停止该规格，不启动新天气获取、标签读取或fit/cash。** 这是否定该样本构造当前足以支持增量检验，不是否定所有天气信息、美国大豆经济机制或全市场研究目标。

2018—2025每年7月1日至10月31日Monday00UTC共141个候选，最终只有20个来源合格周事件。每年均少于8，因此“按时间取前8”没有截掉任何来源合格事件：

| 作物年 | 全候选 | 来源合格并选定 | unknown候选 |
| --- | ---: | ---: | ---: |
| 2018 | 18 | 2 | 16 |
| 2019 | 18 | 1 | 17 |
| 2020 | 17 | 3 | 14 |
| 2021 | 17 | 3 | 14 |
| 2022 | 18 | 3 | 15 |
| 2023 | 18 | 2 | 16 |
| 2024 | 18 | 3 | 15 |
| 2025 | 17 | 3 | 14 |
| 总计 | 141 | 20 | 121 |

- 训练2018—2022：**12**，低于原底线30；五个训练年均至少有一个，但总量不足。
- 留出2023—2025：**8**，低于原底线15；逐年**2、3、3**，每年均低于原底线4。
- 20个不同候选天气周复用**13份**原周报；7份原报各复用于两个相邻天气周，其余6份各一次。不能说有20个独立原生育调查，更不能用18州/县/格点/98产品的行数充独立事件。金融标签从未读取，其持有期重叠/独立性仍unknown。

这些只是来源资格计数，天气X和Y均未取得；因此即使之后每个合格周都能读到天气，样本量上界仍不足。没有为增加数量把训练底线降低到12、每年门槛降低到2、扩大月份/年份、改州域/地图或从旧周报一般LOCF补值。

## 只消费401终态原表，没有重抓或另一套原文解析

401作者确认同一真实session86101已exit0后才构建；输入是`outputs/stage401_original_crop_archive/actual_run1/`的`harvest_manifest.json`、`reports_index.json`与`parsed_original_tables.json`。完整源为309份CropProgress、9份真正Annual及2019Jan改期通知1份。402没有GET、重新下载391原表、调用401 parser或读取当前QuickStats重建值；只使用401已保留的原表行及源绑定。

逐release采用**完整库存**选择A前最近原报告，包括未收到/无TXT的库存状态；不会因为最新报告不完整就退回更早“能用”的表。401本次实际GET都成功，所以最终失败来自共同阶段表覆盖，并非网络没下好。

时钟严格沿400/403：new=Monday00UTC、old=previousSunday00UTC、A=new+37h（周二13UTC/21CST）；V=new+48h至new+216h只写入候选身份，不读天气。每份原报告的操作可用约定是**原release label之后的纽约次日00:00**，使用America/New_York真实夏令时，按实际holiday release日期。取A前最近可用原release；不把Sunday参考期或ESMIS12UTC元数据当发布时刻。这个保守约定不是经验证的2020实际first-seen，输出明确`historical_received_at_known=false`。

年度Q用yearY原Annual的Q(Y−1)/原US分母，18州权重不重新归一到100%。2019年Jan11是改期通知，不当数字；实际Feb08原表用于2019生长期，实际日期与非产量通知身份都保留。没有用晚期修订版换原值，或因Annual正文没有完整Released标签而丢掉官方原发布日期已定位的产量表。

## g规则与实物失败原因

固定18州为391既定域，所有正生产权重州都需可解释的pods/leaves；合法g=0保留，不把unknown当0。只读原表当次current列；表内dash只有401记录明确原zero图例才取0。当前表缺列、缺州、异常字面、pods<leaves或冲突保持unknown。

唯一完成继承仅针对原文**确实缺整张阶段表**：同作物年同州同阶段较早原报告明确100，且没有更晚明确值小于100撤销它时，才带完整原出处继承完成100；非100值不做LOCF。对于表存在但schema/州/字面不明，不能用旧100掩盖问题。原最新报告无法取得也不能假定其缺表。最终20个来源合格事件都来自可直接解释的原当前阶段数据，**合格事件的完成继承单元数0**。

121个unknown候选中，按“每候选每原因只数一次”统计：75个至少有一个必需州缺Leaves表且没有可继承的原明确100；63个至少有一个必需州缺Pods表且没有可继承的100；其中17个同时出现两类。它们不是75+63个独立事件。季节早期Leaves尚未报、后期Pods停止报但并非每州最后都明确100，使两阶段共同可解释的时间很短；不把“没再报”推成100，也不把叶尚未报推成0。

详细日期与原报复用在最终`failure_mechanics_detail.json`，全候选18州逐项原因和继承原出处在`all_candidate_events.json`。例如2020-09-07事件A在假日后周报可用约定之前，仍使用已可用的8月31日原报；这不是为凑样本选旧表，而是实际label/可用时钟规则的结果。

## 一次局部机械修正：原值正确、派生器漏行，科学规格未变

首次402表`actual_run1`已完成且冻结，当时训练9/held8，2018/2019因为401派生行缺NorthCarolina而各0。随后定位到401旧窄State列的完整`North Carolina :`无dotleader，401 `_rows`要求点leader而漏行；原TXT与`raw_table_lines`里的原值完全存在，**不是原产量缺失、改州名或alias匹配**。

经root与404核原文，授权仅402局部恢复两条已观察完整州名行；同一pass把同样漏掉的SouthCarolina作源投影addendum，**SouthCarolina没有加入固定18州事件域**。保留原token、列5、年份/单位、行号和源SHA，401原件/既存manifest完全不改：

| 原发布 | 原州名 | 原TXT行号 | 使用的上一作物年 | 原产量（千蒲式耳） |
| --- | --- | ---: | ---: | ---: |
| 2018-01-12 | North Carolina | 2694 | 2017 | 67,600 |
| 2019-02-08 | North Carolina | 2645 | 2018 | 53,380 |
| 2018-01-12 | South Carolina | 2700 | 2017 | 14,820 |
| 2019-02-08 | South Carolina | 2651 | 2018 | 11,063 |

证据分别在402根输出`observed_no_dot_NC_original_evidence.json`与`observed_no_dot_SC_original_addendum.json`；最终的`local_observed_row_adapter.json`和`original_annual_tables_with_observed_no_dot_rows.json`保留可复用完整年表投影。原2018年报SHA=`755aa0520291efec0bf8eebe8100391852ed305ff94e75694bd46819589213e3`；原2019Feb年报SHA=`1ed719be80f2712dc990b15ceca7de26b3eb8d1a2b3389415b208b1f0b4914e1`。

只完成**一次**fresh `actual_run2_observed_row_adapter`适配表重建，计数变成最终train12/held8。初表与源绑定不覆盖。适配第一次脚本启动时缺标准库`re`导入，在构建事件表及创建fresh输出之前NameError退出；`adapter_preflight_error.json`保留。补导入后才完成唯一适配重建，未改数据或规则。实际总3次脚本启动、2次完整事件表、1次pre-event机械错误，不能将它们算成3个研究/金融尝试。没有旧suite或为其他小差异增加循环。

即使在发现漏行时把2018/2019各年都给予上限8，train9+16最多25仍小于30、held8仍不够；因此NO-GO方向在机械修正前就不依赖该问题。修正是为数据准确性，不是换方法救规格。

## 最终交付与停止边界

唯一工具`tools/stage402_source_event_panel.py`。当前应引用的最终目录：

`outputs/stage402_source_event_panel/actual_run2_observed_row_adapter/`

- `all_candidate_events.json/csv`：141候选、run/A/V、最新原报告身份/原文绑定、Annual原Q/US与18州phase证据、unknown原因。
- `selected_events.csv`、`selected_event_ids.json`：按时间每年最先8合格规则得到20事件；`unknown_events.csv`：121未合格候选；不以sourceunknown替代零收益。
- `qualification_summary.json`：逐年计数、30/15/每年4门与NO-GO；`failure_mechanics_detail.json`：阶段缺表和13份原报复用明细。
- `annual_original_exposure_evidence.json`、`source_report_registry.json`：原发布、原来源、实际Feb2019时钟、Q出处与通知；局部原无点行恢复单独标注，不冒充401原parser已包含。
- `event_table_manifest.json`：来源401终态/索引/全解析、403协议、当前脚本及候选/选择/unknown产物hash；原`actual_run1`同样完整留存。

最终主manifest为5,119B，SHA256 `f0563b958883079ab7fe5468d97544e272db406d87e2b08710bb12ed4f13bd43`。额外只读计数`failure_mechanics_detail.json`5,503B，SHA256 `1593843d5f5121acf592567b0ac83c9dd335a1706e1e3a2b2b09e8a43d413d75`；它在主表冻结之后从同一原候选表生成，不是重建/重选事件。独立404已取得最终产物审查，本作者不自称独立通过。

所有source event表在任何**新增**天气或标签读取之前保存并hash。原397单例早已存在，402未读取其数值或贡献来择事件；本阶段未处理395的46102地理缺失，也未把该28像元缺项扩成所有原报告否决。全98产品/95family母域维持，当前只是m的解释来源资格，不称全市场策略成功。

本轮HTTP/新天气/金融标签读取/fit/cash/行情API/SQL/生产/Git/原账户变更全部0；没有新增、修改、删除策略参数或回测结果，权益/收益/回撤/Sharpe/滑点/交易次数/胜率均N/A。

结束反思：没有利润导向改样本量、阶段代理或日期，直接调参过拟合否，但继承的历史择题与回顾结构/可知时钟风险仍在。本轮来源资格核查有价值，已经给出改变下一行动的明确证据；**继续400/403该固定规格天气下载或拟合没有当前价值，应停止**。不能从此推断天气永远无增量，也不因此将整个全市场研究重新标成“必须等今天日线”。完整高收益/低回撤/极小止损加注目标未完成。
