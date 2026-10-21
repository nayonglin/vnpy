# Stage584：BDI月频新增观测设计独审——允许有限清洗，一次低容量检验有条件成立

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-21 06:37 CST。
- 当前模式：收益前独立设计审查；不是实际回测、重要突破、正式策略推广或生产资格认证。
- 工作区：`/Users/mac/Desktop/fian`；本线分支 `codex/ai-training-data-expansion`。先读registry并定向查本线BDI/宏观谱系；未发现既有BDI金融包。不改LINE/registry和其它agent文件。
- 本阶段新增fit/cash/SQL/行情GET/原raw与大cache读取均0。累计535 fit /282 completed cash＋1旧partial不变。

## 裁决

**`GO_SOURCE_CLEANING_AND_ONE_FROZEN_LOW_CAPACITY_TEST_DESIGN`。** 现有源值得按固定合同清洗；在清洗覆盖与真实成熟训练支持完成、收益前协议冻结后，一个已完整月末到三个月前月末的BDI对数增长、一个新斜率的实验有有限价值。06:39最终与root对齐：采纳60成熟月、原权重拟合/月等权诊断、严格增量门及585始终0cash，设计GO。此结论不是现在就启动fit/cash的授权，也不是BDI已能盈利的证据。

它不是已失败PMI的逻辑重复：干散货运价是不同的外部市场观测，不能从COMMON52的本地OHLCV/曲线/成本列代数恢复，也不是制造业问卷值的换名。PMI失败不能推出BDI无效。反过来，BDI是商品需求、船舶运力、港口拥堵、航线与成本等共同作用的价格，不能直接叫“纯全球需求冲击”。新信息是否已被国内价格反映、其方向是否适合本线first-exit多头机会，正是待证伪问题。

## 有界原作者、官方与GitHub调研

1. [Bakshi、Panayotov、Skoulakis原作者论文入口](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1747345)本次直接返回403；提供的[全文镜像](https://signaltradinggroup.com/wp-content/WhitePapers/Baltic%20Dry%20Index%20as%20a%20Predictor.pdf)返回404。搜索可索引的同一原论文PDF摘录给出月度 `g[t−j→t]=ln(BDI_t/BDI_(t−j))`，包括三个月口径；这仅支持预先选择这种定义，不等于已通读或独立复核全文所有结果。它研究全球股票/商品收益及经济活动，不能把其结论搬成本线中国期货`.25N/20low/K`退出下的盈利保证。不采纳二手策略网站的盈利数字。
2. [Apergis与Payne，2013，原作者期刊页](https://www.mdpi.com/2227-7072/1/3/62)直接访问受429限制；[原论文CiteSeer镜像](https://citeseerx.ist.psu.edu/document?doi=9b3f0fe2fd1bb513fa3d3648e2f0ff12463a16e5&repid=rep1&type=pdf)直接打开失败，但搜索索引能返回原论文首页/摘要：作者、DOI `10.3390/ijfs1030062`、1985—2012日频面板研究对象。只使用这部分原文说明研究问题确有前例，未声称读过全文，也不从该摘要推本线因果符号或显著性。
3. 实读[Baltic官方2018 Circular08/18](https://www.balticexchange.com/en/data-services/Circulars/market-announcements-/category-a/2018/circular-08-18---changes-to-the-baltic-dry-index--bdi-.html)：生效日为2018-03-01，Capesize/Panamax/Supramax权重40/30/30，移除Handysize。实读[2017官方变更提案](https://www.balticexchange.com/en/data-services/Circulars/market-announcements-/category-a/2017/circular-51-17-bdi.html)记载此前自2009年7月的四船型等权结构。采用最终生效事实，不能用提案的原计划日期；相同名字和对数差分不会消除成分变化。
4. 实读维护者[AKShare原仓库index_spot.py](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/index/index_spot.py)：BDI有独立symbol，并使用与582相同的Sina接口；代码选取opendate/price/zde/zdf、转型并dropna。该实现只旁证数据载体，不能认证原值/PIT。它的自动dropna和统一收益字段处理不适合直接照搬本次隔离合同；本轮未安装、调用或重新下载。

本阶段已到上述有限核查边界，不因全文访问失败反复换源，不加入新历史GET。文献只提供机制和固定候选定义的依据；本线没有可直接继承的外部验证结果。

## 对583事实的依赖与清洗边界

本次只读583的小`audit.json`及唯一stage，不重读582的852,412B响应。继承的raw SHA为`c825f71fbcfef651fb78720f6655c1d0b946f9ee75ee35c5568aa1742dac17ac`；583一次独立原件读取的4127行结构成立。

583给出4123条现代weekday、正finite价格候选，另2坏年/2周末隔离；2006—2010约周频，2011后接近日频密度；18处price与前一已有price/zde不一致，不能定位究竟哪个字段错；zdf有比例/百分数混杂。以上不等于4123条价格已全部逐值认证。末行是2026-10-12，本次不得称覆盖今天，也不得把未完成2026年10月作为完整月。

同意root的最小方案，仅用原price/date构造月候选，不依赖zde或zdf计算特征。必须先选**月内最后一个日期合格的weekday候选**，再判该候选是否命中已知18处冲突；若命中，整个月endpoint为unknown。不能为了得到q退回该月更早的“干净”行，不能以zde修price。两错年不补2000、两周末不移日期，全部原索引/原因保留。18处只是已观测字段警报，并非穷尽价格错误或已定位全部脏价。

每个公历月都保留状态、候选原行索引、日期r、原price、当月原行数/合格候选数、月末到r的天数和排除原因；不得仅导出成功月份。低频周数据可以支持“当月最后已有观测”的定义，不可伪装成完整日频或真实月末成交价。明显异常长缺保持unknown，但具体任何长缺判定须在收益前根据月覆盖表一次定案，不能看金融表现再调age阈值；不为普通圣诞缺报建立20年假期补价工程。本设计审不宣称已完成全部月覆盖清洗。

## 唯一建议定义及因果时钟

令m为已经结束的公历月，`P_m`为上述月内最后候选通过资格后的price：

`q_m = log(P_m / P_(m−3))`。

这是相隔三个**公历月**的两个观测端点，不是63条数据、不按每天滚动三个月、不把周频展开成日频、不是当月累计变化，也不是未来整月回报。m和m−3各自在其月内有合格端点才计算；不跨月carry、不插值、不造月末价。中间月份存在与否另披露，不假装两端点之间每日连续可观测。

预先按已知2009Jul和2018Mar方法段标记；若两个端点跨越其一，q为unknown，不尝试拼接常数、回归消除断点或拟合制度交互。在月级分段约定下，受影响来源月是2009Jul/Aug/Sep及2018Mar/Apr/May；2009的“Jul”是官方记载的月级界限，不冒称已获得精确小时。此规则只隔离已知两处，不表示已认证全历史定义不变。

q只能在m月结束后使用。令u为第一个**日期严格晚于m月末**且完整完成的中国source session；模型在u完成后决定下一D的intent。原r日期、m月末和u/D均保留。绝不回填r当天中国15:15或紧接r的夜盘，不伪造Sina历史09:30/13:00发布时间。m月q供后续一个公历月状态使用；新来源月缺失就清除旧状态、B/C共同回A，不无限沿用上一次known q。

这是显式保守的**条件历史可知约定**：当前Sina响应没有历史发布/抓取firstseen上界；日期晚用和次完整u也不能数学认证它当年一定已到达。应标`historical_reconstruction_assumption`，不称first-vintage/PIT/生产可交易。缺精确小时不妨碍有边界的历史研究，也不授权生产或要求永不可达的20年首发证明工程。

## 低容量对照为什么有意义、又会失去什么

保持原130/155/156基模型A、训练目标/成熟过滤/权重、完整98产品/95family forward域、VOLUNTARY_RESELECT、成本和所有现金风险参数。只复用已验收538的完整train/Ahat与forward compact，不重训原52、不重放A现金，不恢复旧宏观offset。

- A：原分数。
- B：在q已知且原标签成熟的同一训练支持上，将原w在known子集归一sum1，拟合残差常数a；q缺失时逐值A。
- C：同样支持/权重，`A+a+gamma*z_train(q)`，只增加一个斜率，train-only标准化并明确其权重约定，固定归一loss下Ridge λ=1；常数处理须与B一致，在协议中写明，不把B估计截距与另一个C截距混用而谎称严格嵌套。无sector/family交互、高阶、sign-search或窗口网格。

两cutoff×main/held0/held1，每个B/C各一小head，至多12。q是全市场月公共值，同u加同一数，**同product、同u、同q的child分数差不变**；因此它不能改善该组内部的排序，只能通过共同score>0参与/不参与的校准改变机会集合和后续账户路径。检验的是“共同运输状态有没有超出52及known域常数的参与信息”，不是“BDI给每个品种独立选品”。若这个有限问题被否决，不应改sector、航运敏感品种、非线性或反向符号救结果。

B控制“源存在时恰好是好年份”的普通域校准；C必须同时有相对A与B的增量，不能只凭C−A正就归功BDI，也不能C失败后改选B为赢家。残差常数以及gamma为正/负都只能由预先训练算出，不从forward挑方向。此新观测的机制是合理假说，弱点也明确：干散货与国内所有98/95并不同质，运力冲击可能与商品需求反向，原52可能已经吸收共同价格变化，论文的月收益目标可能不适合短止损first-exit目标。

## 最低支持与检验限制

真正的宏观支持单位是有成熟原训练残差、且因果join后q已知的**不同来源月**，不能用4123行、交易日×品种×child造N。root最终选择训练原w在known子集归一sum1，机会诊断再按来源月等权，本审接受；应称“原权重拟合、来源月等权诊断”，不能误写fit本身报告等权。每fold披露M、年份跨度、每月source-day/family支持、原始权重和、q scale、空月原因。3月增长相邻月份共享端点信息，残差与宏观还会持续，M仍不是独立样本数。

本审建议收益前冻结每个own cutoff/scope **M≥60个成熟已知来源月、train-only scale>0** 的统一preflight，再一次决定是否启动全部12 heads；root已明确采纳60。60是五年月状态的保守可估计性底线，不是论文给出的普遍阈值、统计功效保证或跨经济周期证明；不把文献采用长样本偷换成必须240月的硬门，不先试门槛或看新收益后降低门。本阶段没有读compact统计实际M，未声称六fold已经过门。

root最终收益前方向为：来源月等权已知支持上，main的C−A/C−B均严格>0，main2020—2022及2023以后的C−B各严格>0，两held的C−A/C−B各严格>0；差动作unknown分列不填0。均需过门；失败立即关闭这一包，0CI/0现金，不用正全段均值掩盖held/早段负差。585本身始终0cash；即使通过，最多四个C自身现金账户也须root另行授权并与157 OWN的A比较，未知执行/容量/陈旧持仓限制仍保留。若做区间推断，至少按日历月成块处理重叠与持续性，沿已接受固定12月块办法可行；不能把探索过的历史当untouched OOS或用大行数宣称显著。现在没有bootstrap或现金运行。

## 版本、参数与结果记录

- 新增文件：本唯一584中文stage和`outputs/stage584_bdi_design_review/decision.json`。策略脚本/配置/模型新增、修改、删除均0；没有实现清洗器或运行实际包。
- 本阶段设计建议：完整月、m−3、price-only、两处跨方法unknown、一个新斜率、Ridge1、同缺失A、最多12head/过门后最多4cash。root已采纳M≥60及上述具体门，将由唯一585协议一次冻结；本审不是实际运行。
- 新增/修改/删除回测结果：均0。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：全部N/A，无新金融结果，不填写旧A数值冒充本次。
- 目标全98/95、不加注、不改`.25N/20low/K`；`goal_complete=false`、`production_qualified=false`、`increased_betting_qualified=false`。

## 开始与结束反思、下一步

开始/结束是否过拟合：本次没有按新收益调参，答案为否；全线535fit后的同史自适应择题风险为是且高，BDI新观测不会重置历史试验负担。只保留一个文献预先有据的月3增长及一个自由斜率、固定门和失败后不救参，是限制风险，不是消除风险。

开始/结束是否值得继续：源清洗与这个小问题有条件值得；立即大模型、全历史重训、分行业网格或直接现金无价值。先完成固定源清洗/因果join的小覆盖摘要，再由root冻结一次训练支持和否决门；若不满足就停，不改窗口。后续如实际运行，按仓库要求另由本独审检查新join/head/选择/诊断，避免重做旧52/A全套。历史研究不等待今天日线，只有原独立前瞻账户结算需要已完成的那根线。

本阶段不更新LINE/registry、根memory/back_log，不修改raw、生产/正式策略或Git。结论是有限研究设计有条件成立，不是整体目标完成。
