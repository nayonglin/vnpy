# Stage451：Con4 单一发布时钟合同设计（0 actual）

- line_id：`futures_full_market_long_signal_ai`。
- 记录时间：2026-10-20 21:51 CST。只读合同设计；非重要突破；未触发实际 A/B/回测或发布。
- 本 agent 先读 registry、LINE 顶部与450 next_scope；仅核408例外面板/必要408与410纯代码/410小receipt、407 aggregate的日期元数据，以及408 catalog中2018浓度准确与2011MFG caution两个必要片段。未看原ZIP、Con4数值、价格、Y、score、模型或账户；未联网。

## 调研与判断

父 agent 负责刷新 CFTC 原始官方资料与 GitHub，本 agent 未重复联网。现有408/410已核的资料表明，普通周 Friday15:30 NY 是通常规则，2010–2025每周真实首发和完整假日历未取得；2023七条 today issuing 是实际发布日期确认；2025初版17/修订13行全是计划。2026下载时间不能变成历史可得时间。Legacy2018集中度更正与本目标不同，2018-09-25公告明确说 Disaggregated/TFF 集中度准确。

判断：可以在明确回溯假设、已知异常保守隔离的单一合同下继续历史研究设计；首见/vintage未知不自动封死全部历史研究。835仅是持仓asof数，6680仅是八映射源行，均不是独立可见发布数。本阶段不签训练、金融、加注或生产 GO。

## 唯一合同

1. 普通周只对未被高优先级例外触及的原生周二asof假设同周五15:30 NY发布；研究可得边界统一为所采用发布日期的次日 NY00。该午夜只处理选定日期内的时刻不确定，不能保证未知假日没有更晚发布。其他星期原生asof默认unknown，只有明确asof和实际发布日期的源覆盖可放行。
2. source事实与research假设分栏；confirmed/plan/asof/announcement/download绝不互相替代。NY日期以zoneinfo构造，不能固定加UTC24小时跨DST。
3. 2013按408原scheduled-date mask隔离10/4—11/8，之后只允许`normal_after_expected_resumption_assumption`恢复，事实层仍是未确认恢复。此独立假设必须由root接受，不把11/8写成实际补发完成。2019按原asof隔离12/24—3/25，3/26报告于3/29发布是后续锚点，非停摆持续至3月的证据。
4. 2023七条已发布日期取次NY00。前四用源明确asof；后三严格以源给出的原scheduled-date与407原生日期唯一对齐，元合同得到Feb28/Mar7/Mar14，但源position_asof仍null，链接必须标为回溯normal-slot假设。对不上或多解即unknown；不拿实际发布日期减4天。
5. 2025全计划不放行；13修订行及初版独有但仍在448源内的12/30均quarantine，至源尾不恢复。2015完整报告7/6只是计划且asof未明，按7/6计划槽并额外隔离[6/29,7/6)原生候选日，不能让普通周7/3绕过。其余无asof的已知异常统一用明确scheduled/plan/closure锚点的前7个日历日作**仅隔离候选窗**，不据此认定原asof或首发。2015 incomplete的7/6锚点显式链接complete2015_plan，2018 mourning显式存closure date 12/5；反向7日候选窗覆盖未证明，窗外留存行也不能宣称strict-PIT安全。
6. 四个target后修订只隔离各自精确asof×code的当前年包行：2012全8；2017仅corn/sugar；2019-03七映射不含copper；2019-10仅corn/oil/meal。选择整行隔离，避免把当前snapshot倒填到首发或未证实的某次修订vintage。2011 OI调整发生在原发布，不误当后修订；Legacy、combined options、格式、改名不自动污染目标Con4。2011 MFG单asof作显式保守caution隔离，不声称八映射数值被证错。
7. unknown/quarantine必须作为状态参与join，不能先删null再merge_asof到旧值。遇已知停发/未知新批次写reset阻断；新实际补发可开有限episode。有效期不晚于可得后7个NY日历日、更新报告边界、适用隔离起点三者最早。TTL本身不足，必须同时有阻断；未知行不准回退更老已知值。mask排除行，reset仅消灭此前episode，不能永久否决后来已证补发；区间统一[available,expiry)。2023-03-17 NY00先做不发布reset，再装入3/16已发布的新cohort边界，原scheduled3/17批次仍unknown，避免同刻顺序不定。
8. 发布episode/time group计数去重，不乘8、不乘日级forward-fill、不乘child。未映射90产品与时钟unknown各自留原因；任何将来依赖unknown的差分/滞后/滚动量传播unknown，本阶段不授权新衍生特征。

## 精确处置与独立检查

`proposal.json`逐项保留并处置10 mask、11 correction、54 event，包含原字段语义、匹配basis、作用范围、状态与NY边界；没有构建6680条visible数值。前三个2023未明asof仍在source字段保持null，仅proposal链接另列。独立子agent`clock_contract_check`只读408/410与本proposal，核对了2013恢复、普通假日、2015 Monday-schedule绕过、mask/reset区别、2023同刻排序及候选窗覆盖未证明等定义漏洞，已在合同明确。

该JSON是待root接受的设计，不能直接充当实际clock panel。后续若固定实现的独立发布支持门不过，保留unknown/停止，不缩短mask、采纳计划或扫描lag救门。完整普通假日历和首见vintage仍未知，不扩大下载/归档工程。

## 变更、结果与反思

只新增本唯一stage和`outputs/stage451_Con4_clock_contract/proposal.json`；LINE、registry、原源、源panel、模型、账户、Git、生产均未修改。交易参数/结果新增、修改、删除均0；价格/Y/score/模型/原ZIP/数值Con4读取0，visible build/网络/SQL/fit/cash/futureD/API均0。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。

运行前/后新增收益择参过拟合：**否**，只定义信息时钟与已知风险，不看成绩或支持数选mask；既有择题反馈风险仍有。运行前/后继续价值：**是，仅限一次条件性合同与后续固定支持检查**，能防止asof当release、计划当actual和异常carry；不意味着来源具备alpha或值得无限首见工程。

合入由root读取本stage后决定是否接受这组假设；本agent不改LINE/registry或根memory/back_log。
