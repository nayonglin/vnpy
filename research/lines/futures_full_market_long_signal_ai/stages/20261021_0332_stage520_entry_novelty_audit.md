# Stage520：境外同标的与开仓前信息排重审计

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-21 03:32 CST。
- 独立只读排重；非重要突破、非正式A/B、非回测。先读`research/registry.md`和本线`LINE.md`，再限定检索本线阶段Markdown及必要的小段源码；不遍历outputs，不读取行情、训练、预测或现金大表。
- 完整目标仍是独立于正式C9月池的六所98历史产品/95family高质量做多入场识别，最终验证更高净收益和更低回撤，再谈窄止损/加注。518已关闭续持固定包；累计511fit/278完成cash及1旧partial仅继承已接受记录，本轮不重新认证。

## 裁决

**境外同经济标的、国内关闭期间形成的新价格信息，并未被本线既有金融实验直接实证否定；但已经被Stage365提出并在来源/时钟层NO-GO，不能包装成首次发现，也不能立即开始fit/cash。** 当前结论仍为金融NO-GO、actual预算0；没有合格历史源的证据变化时，重开外盘窗口、lag、收益变换或复杂模型没有价值。

最值得保留的一个未实证否定的入场机制，是：**目标国内品种收盘以后、实际决定以前已经公开可得的境外同经济标的价格创新，是否揭示国内下一真实开盘以后仍未完成的重新定价，从而区分原来国内状态相同的long机会。** “最值得”是相对于继续改旧loss/模型/窗口的研究顺序判断，不是已确认alpha或高成功概率判断。它最贴近“入场后还有没有收益空间”，而不是重复预测已有走势。

## 已做对象、未做对象及精确边界

| 对象 | 可核证据与实际状态 | 本次边界判断 |
| --- | --- | --- |
| 国内市场四项lag摘要 | [Stage014](20261018_1147_stage014_structured_entry_review.md)第18行引用010的72fit、screen=false；[Stage010](20261018_1140_stage010_fixed_day_proxy_experiment.md)第43行停止固定四特征+DAY代理 | 已实际失败的是该国内摘要/固定代理；“跨市场”旧称不能据此覆盖境外同标的价格 |
| 同行统计关联 | [Stage198](20261019_1837_stage198_information_novelty_history.md)第27行及[Stage425](20261020_1857_stage425_untried_mechanism_novelty_review.md)第18行：032—037同步20日Pearson权重乘u−1同行shock，035实际108fit后关闭，033不称因果lead-lag | 不能换lag/图模型救它；该输入不是国内收盘之后新发生的海外观测 |
| 国内历史reopening贡献q20 | [Stage293](20261020_0140_stage293_reopening_gap_information_proof.md)区分daily open与9am/纯隔夜；[Stage299](20261020_0159_stage299_reopening_contribution_decision.md)关闭6fit/4cash固定线性offset，四CI跨0，主stress DD加深 | 已实证关闭固定q20包；它只压缩过去20个国内日bar，不测当前u收盘至下一D开盘的新海外信息。不能把q20改名“外盘隔夜”重开 |
| 指定国内成品→原料关系 | [Stage429](20261020_1912_stage429_product_material_timing_root_decision.md)：RB/HC坏消息→I的next-open之后方向/年度门失败，0fit/cash后继 | 该固定经济链/时段已反证；不能翻符号、换链或lag救它。它不是同经济标的的跨国时段输入 |
| CL官方结算与免费版次 | [Stage365](20261020_0427_stage365_overseas_settlement_clock_no_go.md)第5、9、18—36行：仅CL真实合约官方日结算；初版历史、首见与中国决定时钟未闭合；0actual | 已有来源NO-GO，不是价格收益实证失败。425第23行再次确认。当前没有新证据解除该决定 |
| FOMC原始意外×事前流动性 | [Stage492](20261021_0130_stage492_fomc_residual_root_decision.md)第15—17行：常数/L、FF4/SP500及L交互；12fit/8cash后固定包unsupported | 不是同标的海外商品价格流，也没有直接测试国内休市间隔的境外商品创新。它的失败不授权缩短25h、换宏观字段救参 |
| COT/集中度 | [Stage409](20261020_1513_stage409_cot_source_assets_and_lineage_decision.md)第20—22行：PMPU旧净标量后继价值NO-GO，不谎称同域已金融否定；[Stage460](20261020_2225_stage460_Con4_root_decision.md)第15、18行：固定滞后Con4追加列，6fit/4cash后稳定增量不支持 | 周度持仓数量/身份和发布延迟，与连续海外价格发现是不同观测。不能从“海外”两字将两者合并，也不重开已关闭COT包 |
| 固定续持/退出 | [Stage518](20261021_0328_stage518_continuation_root_decision.md)：四收益落后、四CI跨0；6fit/4cash固定包关闭 | 本题重新询问入场前新增信息，不能以它为514—519换特征、目标或阈值救参 |

本表仅据本线限定记录，不声称其他研究线或全仓从未做过相似问题；旧实验结果继承接受链，没有重新审查金融大物料。

## 源码说明了什么没有被测

1. [129源码第29—34行](../tools/stage129_contract_choice_dataset.py#L29)的COMMON26是OWN11、同product月份关系13项与两项经济字段；[own11第88—114行](../tools/stage129_contract_choice_dataset.py#L88)只读国内同epoch完整u及历史bar，[maturity_pool第117—128行](../tools/stage129_contract_choice_dataset.py#L117)只构建国内同product月份池。[130第18—19行](../tools/stage130_contract_choice_fit.py#L18)才将其扩为26数值+26missing。这里没有境外同标的价格输入。保持这些国内输入完全相同而改变其后境外交易价格是一个逻辑可行反例；所以该外部输入不能由原52机械恢复。**这只证明信息对象不同，不证明可预测。**
2. [295第57—83行](../tools/stage295_reopening_contribution_source.py#L57)的q明确是国内数组`gaps=v[1:,0]-v[:-1,3]`的20项和；不读取海外价格，也没有u收盘后的当前观测。因此299不能覆盖本题。
3. [489第168—188行](../tools/stage489_fomc_residual_experiment.py#L168)的B/C设计明确是`L_centered, FF4, SP500`与交互；[484第68—119行](../tools/stage484_fomc_event_requests.py#L68)固定纽约公告→UTC+25h→上海15:15可消费u→下一源D。这是一套特定事件观察时钟，不是所有海外输入的一般25h规则，也不能把现有FOMC头当海外商品价格实验。
4. [129第291—306行](../tools/stage129_contract_choice_dataset.py#L291)由D原bar open设F与`SL0=F-.25*N`；[131第146—164行](../tools/stage131_contract_choice_kernel.py#L146)按D.open含不利成交价/费用进入并检验退出。这里购买成本已经包含开盘重新定价。将u.close→D.open的上涨算成新入场获利，是对象错误。海外信息若只解释这个gap而不解释买入后的质量，就不支持本目标。

## 必须同时满足的因果可得时点边界

对一条候选海外观测，至少区分交易所事件时刻`t_x`、数据通路可消费时刻`t_a`、冻结决定时刻`t_dec`和目标国内真实可执行开盘`t_Dopen`：`t_x <= t_a < t_dec < t_Dopen`。历史回溯文件的当前下载时间不是`t_a`，结算计算时刻也不是免费网页发布时间；未知保持未知。

- **不能在15:15已经冻结的决定中用15:15以后的海外更新。** 若以后研究要消费国内晚间开盘前更新，须明确另冻该决定时钟、完整国内输入完成域与执行域，不能仅因“还未到21点”便回填旧u决定。[Stage355](20261020_0408_stage355_input_and_execution_clock_domains.md)说明输入完成域与D执行域须在score/赢家之前定义；既有义务、unknown和不同品种时段不能用最终赢家筛掉。本文没有改时钟。
- D是原下一源交易日对应的真实合约首开；带夜盘者可能是前一民用日晚间，日盘者不同。中美假期、DST与历史夜盘制度必须按各自历史日期映射，禁止按同名日期merge或机械shift(1)。不是所有98产品都能用一套“美国昨收/中国今早”。
- 同经济标的不等于同一可交割资产：等级、交割地、币种、月份和税运费有差异；国外连续主力复权价格、未来主力身份或事后最相关合约不能充当当时可知真实合约。缺映射产品保留完整母域及原动作/unknown，不能把研究悄悄缩为少数有海外对应物的幸存品种。
- 国内u.close→D.open只作已支付的重新定价段；D.open→原退出才与新入场净价值相连。前者有关系、后者没有，或关系仅来自一个事件/产品，都不足以继续金融。不得用闭合赢家/未来D价格选择源支持。
- 以该机制补足“默会判断”的合理方式，是把交易者会辨别的“信息何时形成、我买入时已付了多少、开盘后是否仍持续”拆成事前可审对象；不能用无法证伪的市场直觉代替字段、时钟或收益证据。

## 本轮网上与GitHub核查、独立判断

本轮仅读网页/公开README；无行情下载、clone、安装、外部代码执行或源采集。

- [CME官方结算FAQ](https://www.cmegroup.com/articles/faqs/access-to-cme-group-settlement-data-faq.html)实读：结算通过MDP等通路在计算附近传播，免费网站延至午夜CT；授权通路与免费网页可得时点不同。[官方Daily Bulletin](https://www.cmegroup.com/market-data/daily-bulletin.html)实读：初版约下一业务日00:00CT，最终版10:00CT。当前规则支持365的时钟警惕，但不能倒证多年初版已归档。本轮没有取得可解除365缺口的历史版次证据。
- [Hoffmann/Rosenbaum/Yoshida原论文摘要](https://arxiv.org/abs/1303.4871)研究非同步观察下lead-lag参数的一致估计；[维护者GitHub](https://github.com/philipperemy/lead-lag)README提供带时间戳的非同步序列接口。它们说明“同日标签相关”不能代替严格时钟，**不证明经济因果、可交易时滞或中国long利润**。本轮不复制其估计器、不搜最优lag；用更复杂非同步估计救无源资格没有价值。

因此，**真实新信息的机制边界仍在；当前可实施金融题仍不存在。** 本阶段不推荐新实验，不自动要求补大海外数据库。只有根任务以后得到一个与365缺口直接相关的新证据——精确真实合约、事前可得通路/时钟、有限可回溯历史及修订边界——才值得再裁决一个固定对象；“找到日线有数值”不是该证据。若没有证据变化，到此停止排重，不继续翻商品/ETF/窗口凑题。

## 记录、反思和后续

- 开始是否过拟合：**本步新增收益调参否，长期同史适应性择题风险是且高**；结束判断相同。没有新收益不等于选题没有自由度；读过旧结果后的机制选择不是盲OOS。
- 开始是否值得继续：**有条件是**，防止把来源NO-GO混写成实证失败、或将旧对象改名。结束继续本次扫题/立即训练：**否**，边界已清楚且源证据未变；继续完整高质量long目标：**有条件是**，须靠不同可得信息/新事实，不能靠旧Ridge/HGB/阈值/风控救参。
- 新增仅本唯一stage；策略代码、参数、旧结果新增/修改/删除均0。新fit/cash/SQL/行情API/下载/测试/模型推理/旧大源重hash均0；未改LINE、registry、根memory/back_log、其他线、正式策略、生产、CTP、邮件、launchd或Git。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率全部N/A；本轮没有回测，不触发回测后新结果独审。`goal_complete=false`、`production_qualified=false`、`increased_betting_qualified=false`。
- TODO仅为保留上述来源证据变化条件；不授权下一actual，不重置原四前瞻账户，不把历史研究阻塞归因于今天尚未完成的日线。
