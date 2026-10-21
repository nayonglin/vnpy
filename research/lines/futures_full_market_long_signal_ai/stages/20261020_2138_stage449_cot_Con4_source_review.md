# Stage449：Con4两原集中比率投影的独立有界源复审

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-20 21:38 CST。
- 性质：root447固定scope与448一次actual后的独立数值源审查；非重要突破，不触发A/B，不授权金融。仅写本记录和449 review receipt，不改448/445/LINE/registry/其他线/正式版。
- 结果：**passed；remaining_core_problems=0**。一次实际审查，1.124秒，80,219项机械核对；未导入/调用448 numeric，不重跑作者或旧suite。

## 核验事实

一次完整读取448新JSONL，按独立Decimal恢复全部6,680行、13,360个原集中比率token的pct/Con/状态/unknown原因，核835×8完整唯一grid、128个year×channel统计和总数守恒。已知Con 6,680，未知0；最大Con绝对数值差 `1.0101010101010101010101010101010101E-16`，验收上限1e−15。独立范围`[-0.68602150537634408602150537634408602150537634408602, 0.35519125683060109289617486338797814207650273224044]`。来源代码、scope、作者授权、源manifest/小aggregate/parsed manifest绑定与16年作者收据计数一致；这些绑定检查不冒充重复独审所有原档。

逐行核原代码保留前导0、市场名、FutOnly口径、两个原日期字段与asof、源ZIP/member/物理行号及原rowhash格式。原数据按Monday或Tuesday如实保留，不强制周二。原token parse计数 `{'reported_finite_0_to_100': 13360}`；真实合法零pct token 0、Con零37。缺行0、多原行slot 0；没有把未在实表出现的缺失/den0/冲突分支说成实表验证。

源码与既有小fixture只静态核对：单端0合法±1，正数相等合法0，双0保留原零但Con unknown；缺失、非有限、越界、冲突/缺行不填0。没有追加suite、调用作者或改变数值。

三个预定anchor：2010-01-05/002602/DCE.C，2017-01-03/085692/SHFE.CU，2025-12-30/084691/SHFE.AG。各原ZIP一次读字节核SHA/bytes，并从指定member按CSV物理line_number定位，仅保留目标原行；七项选中tokens、起止行号、完整原行tokens SHA均匹配。总共为定位遍历22,343条原CSV记录，保留3个anchor，不说只读了3行，也没有全重扫16包。具体tokens、source绑定和行号均在receipt。

所有6680行严格保持`publication_available_at=null`、`strict_firstseen=false`、`clock408=retained_not_yet_applied`；asof只是持仓日期。835个日期和6680槽不是独立发布事件或可训练经验数，当前数值已知不授时钟/PIT或金融资格。

## 外部资料、判断与边界

复用root447已查的CFTC定义、维护者实现及Liu等2023原研究，449新网络0。原论文Con量与当前固定两原字段测量一致，不由此推断中国次日、窄止损或成本后long alpha。原档一致性继承407/448既有绑定与审查，加上3个独立锚点；其余13原ZIP本次未读，不能称16包全数值再次独审。

本次新增下载/API/SQL、价格/Y/分数/模型读取、fit/cash、前瞻D、账户/生产/订单均0；额外suite0、作者工具重跑0、旧mapped/canonical读取0。金融参数和回测结果新增/修改/删除0；权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率均N/A。

开始/结束过拟合：无本轮收益择参，原3锚点预定；长期同一历史适应性择题风险仍高，源值通过不归零。开始/结束继续价值：一次数值源独核有价值且已结束；不再扩旧来源/框架，不自动金融或加注。

receipt 44,896B，SHA `9362281c7551bd17f74362752a1abb596cd622c83ae98002ba3fc250b30f84c7`。源448收据SHA `c5490dc40ddb465fb7aeab827c325c2cb0be3742009812c0e8cd7efe124b8ed2`；新6680行SHA `e9e5fdb21dcca96cb33b662db781ffa1382947c8a5913f005d598706fa87e9db`；scope SHA `ff5b700ac93499739a09d4afb1c6680af1864f86015db563d833bd327b190760`。交root统一承接，本agent不改LINE/registry/根总账。
