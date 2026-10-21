# Stage153：有限补源结案，修正INE分组并保留全域缺项

- line_id：`futures_full_market_long_signal_ai`；2026-10-19 01:05 CST；非重要突破。
- 延续152固定研究账户，不改真实用户资格；完整全市场long目标不缩小。三分工各限3个有目的查询，仅补已定位关键缺口；root已读三最终stage、catalog/收据并核两件实际原响应身份。相同失败URL不再循环。

## 本次实际取得什么

| 范围 | 新证据/判断 | 仍然未知 |
| --- | --- | --- |
| INE | 当前官方全文明确SC T−8，LU/NR/BC T−5；不能将全所实物都改成T−5，也不能保留BC始终T−3 | 2023-08-25公布、10/18实施、2311起适用来自同期提示卡候选；正式修订原件未取得，strict_transition_primary_ready=false |
| DCE F | 严格列出L_F/PP_F/V_F各14、共42 metadata epoch，202602—202703；首listed=2025-10-29，与普通身份隔离 | 正式合约及上市两原URL仍缺正文；现金身份/前月末/首2602F—2604F为候选，不能把草案或broker转述变成正式合同 |
| GFEX | 取得2022交割通则署名托管HTML、SI初始署名PDF；PT/PD来源门户web正文各有个人交割月0及2025初始日期 | 原站字节未核；LC初始点/PS主文、全部后续适用区间仍unknown；五品种完整保留 |

INE当前官方规则是[上期所法规库的能源风控全文](https://www.shfe.cn/regulation/ineregulation/businessmethods/riskcontrol/202607/t20260721_832649.html)，相应第66/70/76/82条。2026现行端点不能证明2023切点；提示卡候选还区分LU/NR旧8改5、BC旧3改5、SC不改。152冻结文件保持原样，此处追加更正，不把候选静默升级。

GFEX[署名交割通则托管副本](https://www.guodu.cc/03/08/2024-09-11/39037.html)为2022-07-27〔126〕号，包含自然人不得实物交割、交割月首日起强平，也明示未平仓后续处理；**不能推成到期必然以某价平仓**。SI为[2022-12-12〔234〕号PDF副本](https://www.zjlnqh.com/member/uploadfile/ueditor/file/20221216/1671160270434431.pdf)。PT/PD文本来自[交易所支持法律门户PT](https://futureslaw.org.cn/czcepzxz/3444.htm)、[PD](https://futureslaw.org.cn/czcepzxz/3445.htm)，是web正文再发布证据，原HTTP410。LC/PS仍列在目录，未为快速回测删去。

DCE F的2025-10-29是已读metadata观察，不由此声称正式上市公告或首发可得性已取得。两个已定位正式公告分别为18619141/18623631，本轮web/真实网络SSL timeout；投资者网可搜资料为草案且直取404。sandbox DNS前置失败与随后真实网络失败分开留存，没有将沙箱故障当网站永久状态。INE原字节请求为DNS失败，web已读当前正文与原字节未保存也分开记录；**原件size/hash保持null，不编造快照**。

## 源包接受范围

接受为分级来源资料与身份/候选语义，不签严格全历史资格。GFEX两件实际原响应共438523B，root读回并核清单SHA：

- delivery_general_2022_broker_copy.html：130524B，SHA `417a62e4ad78f64689d86af11ea30357595d5d054d78665d196c4a4bf3b90d5d`。
- si_initial_20221212_broker_copy.pdf：307999B，SHA `a87414d5b9caa29d0b4af8c8850e8a4b4f2b7f8e839aa16f5c12305277137aed`。

这两件都是署名托管副本，未与GFEX原站字节核对，非当年首发vintage；另三件HTML包装明确是有限web摘录，不能计入原响应数。没有新下载行情、分钟或原始金融库。来源层级是不同证据强度，不是把任意官网字段设为true即通过。

已保存[source_overlay.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage153_non_delivery_source_decision/source_overlay.json)，精确绑定152账户/原catalog与153三组新资料；[decision.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage153_non_delivery_source_decision/decision.json)记录接受范围和下一行动。新增每epoch账户日期仍0，没有新金融资格。

## 实施范围的实际缩减

root只读了现有`stage131_contract_choice_kernel.py`：新入场按`lifecycle_index`拒绝、持仓保存`expiry`、收盘`anchor_request`按下一日到边界发退出。因此**实物提前退出的最小实现可优先是每合约元数据适配，而非重写资金算术**。缺quote仍应保留deferred，不能因期限要求造价成交。这里是静态接口事实，未改代码、未实际运行新规则。

现金到期结算是另一事件，当前接口静态观察不代表已有正确结算数值/费用/法定义务实现；若后续选择统一市场退出政策，须另行固定且区别于法律必须清零，不从“非实物”推出现金合约全部提前强平。本轮没有决定新的现金平仓日或新模型目标。

GitHub取舍沿152的[RQAlpha官方实现](https://raw.githubusercontent.com/ricequant/rqalpha/master/rqalpha/mod/rqalpha_mod_sys_accounts/position_model.py)：拒绝旧last_price/零交易成本合成平仓作为真实履约；没有复制代码或扩大引擎工程。

## 下一步及停止条件

有限来源批次现已完成，应结束搜索/失败重试。下一步用已固定身份及分级来源，**覆盖整个本地目录作分支、适用时间范围和known/候选/unknown映射**；先量化哪些资料确实影响后续计算，再决定最小重建假设和一次必要验证。不能凭候选自动产生“已认证日期”，也不能为让结果通过而只保留易核品种/年份。

历史归档重建可作为透明的研究假设讨论，不能包装成首发PIT/实际券商资格。若某段仍缺正式证据，保留具体状态；不把“更多同类网页”作为无限待办，不立即回放旧资金、重训旧模型或救FX。本次有价值的新信息是SC/BC分组的纠正、DCE F真正时间范围、GFEX署名规则来源与最小接口可复用性，**不是收益进步**。

新增/修改/删除生效策略参数、金融结果均0；新fit/cash/SQL/价格/标签/行情下载/大库hash0。规则原响应2件、web摘录3件如实计。累计397fit/206cash；本轮权益、收益、DD、Sharpe、滑点、次数、胜率均N/A。无新回测，不额外重复启动金融独审；完成新金融实验时仍须独立全面复审。

开始/结束新增按收益调参过拟合：**否**，按制度与固定来源取证，没有读成绩选择期限。未来stale过滤和同史多轮选择风险仍在；不得从两笔例子救参。继续本批取证：**否，已经足够结束**；继续全域状态映射并判断最小可检验规则合同：**有价值**。完整目标active，稳定全市场优势、窄损上界、加注及真实执行资格均未证明。

## 精确分工证据

- [ine_evidence](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage153_ine_rule_transition/source_evidence.json)：3083B，SHA `f1eab06f844cc4468aa02469c5fcb5f2f75268748a9384b969ed0e0132fcecc5`。
- [ine_fetch](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage153_ine_rule_transition/retrieval_manifest.json)：1500B，SHA `38a3cca2341f73eda86c808f858f5844ddb73d612360bf564c8c8bd4523e660a`。
- [dce_F_catalog](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage153_dce_F_source/source_catalog.json)：13146B，SHA `2fce801d0698f215b97b5b9e8972de27e0a48cd618266031fbc46023afbe0198`。
- [dce_F_fetch](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage153_dce_F_source/retrieval_escalated_receipt.json)：1313B，SHA `b31b600b3491c1a80856404bf66f0d37d58293a0983a8e3e8437c12765b5ad35`。
- [gfex_catalog](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage153_gfex_initial_rules/rule_source_catalog.json)：4823B，SHA `98eaa01d3f8bc0ba519efc0e9b85ed0696ad48fbc7219017de6ebe054a878009`。
- [gfex_receipt](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage153_gfex_initial_rules/receipt.json)：2641B，SHA `22a77e42578b411d3fe80a9dc634293c9f190cd3cdfac4c313088eb48763730d`。
- [ine_stage](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261019_0059_stage153_ine_rule_transition.md)：7001B，SHA `73a12271c88386f7752e45875fbd733a2ad0c6773d328788c4e41b7aaa995696`。
- [dce_F_stage](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261019_0100_stage153_dce_F_source.md)：5832B，SHA `05f3cb0fe3beeba77b2d644d777b8d4fc56a61a48f1eae6ca483cf68e07fc5a3`。
- [gfex_stage](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261019_0103_stage153_gfex_initial_rules.md)：6083B，SHA `6fec4f655a9f1022fef2f1e0feb1c04abc597580345ed17da327d650d3995553`。
- [prior_account_contract](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage152_non_delivery_account_contract/account_contract.json)：3862B，SHA `53c43661c77207241511e1e2cabfc45d9ab456434a0187a2cc8d172f56f38425`。
- [prior_rule_catalog](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage152_non_delivery_account_contract/rule_source_catalog.json)：7213B，SHA `72f19ce8649fc61fdc77c06c18bdbd3116c39a2ffafe77468b323df07eca1aad`。

本轮不改根memory/back_log/外线，不Git提交/推送/建分支/worktree，不生产/CTP/订单/邮件/自动化。
