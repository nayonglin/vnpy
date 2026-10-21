# Stage529：SGX—DCE对应月曲线偏离的机制审查——当前NO-GO

- line_id：`futures_full_market_long_signal_ai`。
- 记录时间：2026-10-21 03:57 CST；工作区 `/Users/mac/Desktop/fian`；只新增本唯一stage，不操作Git。
- 阶段性质：来源规则、原始研究与代数机制审查；非回测、非重要突破，不触发正式A/B。
- **裁决：当前SGX—DCE相对月份曲线偏离命题NO-GO；不为它扩完整历史，不追加特征投影、fit或cash。** 这不是所有跨市场信息、SGX源或一切未来q模型的永久否定。

## 完整目标与已接受边界

完整目标保持六所98历史产品ID/95family的全市场高质量long入场，独立于正式C9月池，以更高成本后净收益、更低回撤为标准，随后再分别验证极窄止损和增加投注。不能把目标缩成铁矿套利，不能以数据工程成功或相对价差收敛替代单腿做多价值。

先读取registry、本线LINE顶部、[Stage528结案](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261021_0352_stage528_overseas_source_root_decision.md)，继承而不重复验证：2019Jan有22个成功日期×48个monthly=1,056条TSI62 DSP/Prev观测；[Stage527](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261021_0349_stage527_sgx_201901_independent_source_review.md)独审14,784字段、2,112数值差0，只认证有限源投影。2019页整体20:00，后年锚点17:30，不等于公开发布时刻；Prev的上一有效报告日身份未闭合。沿用528的保守重建约定：源日r之后至少经过首个完整国内源日u，在u收盘接纳；版本元数据晚于截点则再后移，再到下一真实日bar首开D执行。此为研究约定，非strict PIT，D.open也不一律等于09:00。

本阶段只审一个尚未冻结方向/anchor的草案：`q=log(SGX_query/SGX_anchor)-log(CN_query/CN_anchor)`。SGX真实独立观测可以改变q，故它不只是国内字段的代数换名；信息新颖性成立不自动授予金融实验资格。

## 官方/原始规则核验及经济判断

| PRIMARY材料 | 本次实际核到的事实 | 对候选的限制 |
| --- | --- | --- |
| [CFTC托管的SGX原始Contract Specifications，2015-01-05版](https://www.cftc.gov/sites/default/files/idc/groups/public/%40otherif/documents/ifdocs/eice14a-4-1contractspecificat.pdf)，PDF第19—20页，SGX TSI Iron Ore CFR China 62% Index Futures列 | futures为100 metric tons、现金结算；最后交易日为当月TSI最后发布日；FSP为到期月全部TSI参考价格算术均值 | 直接核的是futures历史规格，不以swap规格或另一交易所产品代替。历史版本支持月均现金payoff差异，不声称已覆盖2019全部修订 |
| [SGX官方清算附件](https://rulebook.sgx.com/rulebook/appendices-2)，Iron Ore Swap Contracts；及[2015官方修订附件](https://rulebook.sgx.com/sites/default/files/net_file_store/SGX_DC_August_31_2015.pdf)，末页 | 旧TSI62 swap同样月均现金；现附件按expiry区分Jan2026前TSI、Jan2026起IODEX | expiry身份要逐月保留，不能以抓取年份统一更名，也不能混用58/65等品位 |
| [DCE原编《Iron Ore Futures Trading Manual》](https://www.ccbfutures.com/upload/20180403/20180403102227680.pdf)，由建信期货托管；PDF第23—29页 | DCE为人民币/吨、12个月份、指定地点/质量的实物交割；旧表末交易日为交割月第10交易日；书中明确含税价格、VAT发票、仓储与检验等费用 | 此文内容为2013时代教育材料，路径2018不等于2018修订版；不拿其tick、费率、质量标准认证2019或现行制度。它足以确认与SGX月均现金并非同一承诺 |
| [Platts原始Global Iron Ore方法文件，February2024](https://www.spglobal.com/content/dam/spglobal/ci/en/documents/platts/en/our-methodology/methodology-specifications/Global_Iron_Ore.pdf)，第2、4—5页 | 该版TSI62/IODEX62为CFR Qingdao、美元/干吨、具名化学/粒度条件，现货评估为14—56天forward并做时间/条件归一 | 指数发布月份不等于实物同月交货；同Fe标签不等于全部化学/品牌可交割等价。此版不倒证2019全部参数 |
| [ICC原作者CFR解释](https://academy.iccwbo.org/incoterms/article/incoterms-2020-cfr-or-cif/) | CFR中卖方承担到指定目的港的成本与运费 | SGX标的已为CFR中国，不能再机械加一遍全程海运费；仍须区分指定目的港、港杂、仓储、交割地点、税与资金占用 |
| [交易所负责人的原始答复，协会转载](https://www.cfachina.org/industrydynamics/mediaviewoffuturesmarket/202101/t20210128_15207.html) | 2019品牌交割方案用于I2009及以后；后来I2202又调品牌与升贴水 | 不是按观测年份统一拼接一条永恒DCE标的；不同月份可能跨制度身份。该答复不替代完整历史规则验收 |

DCE官网也检索到[同题教育材料PDF入口](https://www.dce.com.cn/dceg/file/2025-05-25/1748165285051ff8080819701ddb3518019706c554bb21f7.pdf)，搜索抽取含physical/CNY/MT及F/DCE I001-2013等文字，但本次打开超时。因此实际可读核验依据是上表建信托管的交易所原编材料；未比较两份字节，不以官网文件路径的2025日期声称规则2025生效或两文件字节相同。

判断：SGX的“某月”是对那个日历月指数的平均现金承诺，DCE同字面月份是按国内质量/仓单/提货制度交割的承诺，期限终点、交付窗口、地点及可交割选择权不同。若query或anchor进入SGX当月，月均还混入已实现部分；即使均为未来月，也没有成为DCE实物点值的严格复制腿。排除当月可减少一项混合，却不能补齐剩余做多方向，本阶段不因此发明新过滤参数。

共同的即期FX与共同乘法税系数在各自两个月价格比中确可约掉；不能以“有汇率”笼统否定q。但若国内价格仅示意为`CN_m=a*S_m+c_m`，则`CN_q/CN_a=(a*S_q+c_q)/(a*S_a+c_a)`，月份相关甚至相同的加法费用/质量调整也不会一般消失。预期远期FX/税制、干湿重、grade/brand替代、港口仓储融资及交割选择权都可能形成期限差异。这是不可直接视为错价的混杂，**不是本阶段量化了这些成本或找到了可用于交易的公允价**。

SGX官方[Practice Note 7.11.1.2 §2.1(c)—(e)](https://rulebook.sgx.com/rulebook/practice-notes-0)允许以典型跨月spread关系、理论模型或polling计算DSP；§2.2还允许特殊处理。因此48个有限DSP不能直接当48个相互独立的真实成交信息。规则允许不证明本地1,056行实际用了何法，也不认证2019逐月流动性。

## 原论文与GitHub：价格发现不等于本任务剩余收益

1. [Hasbrouck原论文（1995），原刊摘要](https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1995.tb04054.x)把information share定义为某市场创新对共同有效价格创新的贡献。它是信息吸收位置的统计量，没有把高贡献或领先市场直接定义为延迟入场后的成本净long收益。本次只据可读原刊摘要，不假称全文已取。
2. [Ge等原论文（2019），原刊](https://journals.vilniustech.lt/index.php/JBEM/article/view/10604)研究DCE与现货的VECM/state-space价格发现。其摘要关于长期均衡、冲击及动态贡献的结论，不能认证SGX期限曲线领先DCE，也没有认证本任务的r→u→D成本后入场。本次原刊摘要可读，全文嵌入页未取得可读正文。
3. [Fan、Fernandez-Perez、Indriawan、Todorova原作者大学工作论文，November2019](https://acfr.aut.ac.nz/__data/assets/pdf_file/0004/323158/Ivan-Internalization-of-Chinese-Futures-Nov19.pdf)，第24—27页，直接研究DCE/SGX：对最活跃合约用一分钟对齐，定义每日平方log价格差之和；观察2018开放前后mispricing变化。作者将下降解释为套利竞争增强。这不是对应月四腿q、不是单腿long，也不是延迟完整国内交易日之后的净利证明。文内把换汇写成RMB/SGD，不能照抄为本线美元价格换算，日期还出现November31；本次只采其研究对象与可识别边界，不移植其公式/数据质量或套利利润说法。
4. [维护者SGX-web_crawler](https://github.com/Junxiao-Zhao/SGX-web_crawler)README针对WEBPXTICK/TC文件，含历史/日更及失败恢复功能；只说明采集实践，不证明本iron_dsp模板完整覆盖、历史首发或q有效。[作者EPAT项目](https://github.com/joomladigger/The-Final-Project-for-EPAT)README是中国期货配对/协整均值回归思路，也不是SGX—DCE对应月、保守延迟及单腿long的预注册复现。本次只浏览README，不clone/安装/运行代码，不借其结果定方向。

调研结论：核到了真实跨市场信息对象和不同payoff，也核到了市场联动/套利竞争研究；没有核到足以使本草案获得确定单腿方向、持续期限与本任务交易时段适用性的原始机制证据。缺乏保证本身不是NO-GO理由；下面的可识别性缺口才是。

## 关键代数反证：四腿收敛不识别query单腿上涨

即使先强行假设相同月份可比、无费用、SGX曲线固定且q必然回归0，也不能推出国内query做多盈利。令SGX query/anchor恒为110/100，国内起点query/anchor=90/100，则q=`log(1.1)-log(.9)=0.20067069546215122`。随后国内query/anchor=88/80=1.1，q恰好变0，但query单腿收益为`88/90-1=−2.2222222%`。这是合成数值，不是市场样本或策略回测；`.py311/bin/python`一次纯math算术确认，市场文件读取/fit/cash均0。

一般地，`dq=dlogS_q−dlogS_a−dlogC_q+dlogC_a`。观察q及期待其收敛，不能唯一识别四条腿中哪条调整；SGX自身回落、国内anchor下跌或二者共同变化都能完成“修复”。给它一个long符号还需要**独立证据说明国内query那一腿在D之后承担正向调整，而其余腿/风险溢价/费用不承担**。用国内动量、anchor稳定窗口或事后选月补这条约束，会变成又一次选择字段、符号、window的alpha搜索，当前没有此证据。

时钟进一步削弱简单“境外更新、国内尚未反应”的直觉：本约定已让国内完整u交易发生，C_u晚于S_r；q可能只是国内已经吸收了源r之后的新消息。若相关性只发生在u内或D.open的gap，实际买价已支付它。保守延迟不意味着一切跨市场alpha不可能，但它撤销了仅靠非重叠交易时段即可确定long剩余的论证。

所以本NO-GO不是“因不能保证盈利而不测”，也不是代数证明q在任何统计条件下都无预测性；是**当前尚无超出相对值叙事、低自由度、能够约束D之后query单腿方向的经济命题**。现有有限先验不足以为长期同史再增一轮搜索和完整源工程支付预算。

## 与旧失败谱系的精确区别

| 旧对象/精确本地依据 | 与本候选的关系 | 本阶段不作的偷换 |
| --- | --- | --- |
| [204事前协议](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage204_local_curve_information_protocol/protocol.json)的`hypothesis`、`feature.name=bracketed_log_price_chord`；[208根结案](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261019_1930_stage208_local_curve_information_decision.md) | 旧包是同exact国内产品相邻月份三点曲率、便宜方向；新q含不能从旧国内资料还原的SGX观测，不是旧q代数同义词 | 不用208的失败推定新q必败；也不把“外国”两字自动当经济机制，不复活旧字段/头/符号/阈值 |
| [429记录的机制定义，第7—18行](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261020_1912_stage429_product_material_timing_root_decision.md:7) | 旧包是国内RB/HC代表月负收益部→I的成品—原料短期传导；新q是同商品跨境期限相对值，来源与关系不同 | 不称旧产业链反证覆盖所有SGX；同样必须问真实开盘之后剩余量 |
| [365原来源/时钟裁决](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261020_0427_stage365_overseas_settlement_clock_no_go.md:7) | 旧对象是CME/NYMEX CL初/最终结算档案与可知时钟未闭合；528已取得新的SGX实际原件，不能继承CL全盘禁令 | 本NO-GO针对当前机制，不假称SGX无源或外盘价格已完成金融失败 |
| [527来源边界，第37—62行](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261021_0349_stage527_sgx_201901_independent_source_review.md:37)及528 | 解析准确、月份标签与保守消费约定已有进展，经济同一性/可成交/首发/alpha仍未认证 | 不拿1056行当独立N，不把新source资格当新模型或加注资格 |

## 下一动作、变更与读取边界

**是否值得为当前q扩完整历史：否。必要新增历史字段与GET预算：0；fit/cash/SQL预算：0。** 不把NO-GO改写为“先做一遍单月q、选anchor、看分布再决定”，因为几何可用率即使100%也无法解决上面的单腿方向缺口；也不展开全vintage、运费、grade、FX或税费库工程来延长此候选。

保留526/527已有原件与清洗证据。未来若有真正独立的新证据明确国内哪条腿为何在真实D之后继续调整，可重新提交**另一个冻结前的机制审查**；最低需要先在纸面说明query/anchor真实身份、两市场payoff转换、可知/执行时刻和单腿传导约束，而不是先补价格再选公式。本段不是自动授权未来数据工程，也不是要求完美first-seen才允许历史研究。现阶段不提出另一商品/另一source/另一模型续包。

新增脚本0，修改/删除脚本0；新增/修改/删除交易或模型参数0；新增/修改/删除回测0。只新增本stage。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A（无新回测）。本线累计511fit/278完成cash＋1旧partial只继承528，未重验或重算。

实际只浏览公开规则/原作者论文/README，没有保存新价格原件、调用行情API、读取数据库、旧actions/COMMON/scores/nativecache或资金账本，没有fit/cash、按赢家family筛选或旧回放。**读取范围偏差如实保留：** 早期为定位528/208等的关键词rg横穿LINE，返回了混排的旧数值摘要；对208做机制提取也返回了旧结果定性句。没有据其选择family、方向、字段或本阶段裁决，随后仅定点读取事前204协议与来源/机制章节，不再取旧金融结果。不能把本阶段写成“从未看见任何旧收益摘要”。

本次不是实际回测，因此没有虚构回测独立review；root另派531独立批判，529先独立形成上述裁决后交换了代数与来源边界。是否采纳由root结案，不由本stage修改LINE/registry。未改其他线、正式策略、生产、CTP、邮件、launchd、Git分支/commit/push。

## 开始与结束反思

- 开始过拟合风险：**是**。长期同史自适应择题的风险仍在；“只有一个scalar”不消除信息源/月份/anchor/方向/窗口选择。
- 结束过拟合风险：**仍是**；本阶段新增按收益调参：**否**。没有用市场新收益确定q，代数合成例也不是市场拟合。不以完整历史工程成功掩盖先验薄弱。
- 开始继续价值：**是，限一次规则与机制审查**。真实SGX外部源值得先确认经济对象，避免错误地套用CL或旧国内包的结论。
- 结束继续价值：**此次有界审查已完成、有价值；继续当前q工程/金融包：否**。完整全市场long、更高净收益/更低回撤及窄损加注目标仍有条件值得继续，但本阶段没有实现，不能用缩成铁矿、放宽目标或再救旧包宣称完成。

合入建议：root可记录本机制NO-GO与历史扩展预算0，保留528已验收源身份；不更新根memory/back_log。本stage作者不改LINE/registry，514—519固定退出包继续关闭。
