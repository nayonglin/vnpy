# Stage474：失败谱系去重后，仅保留 FOMC 原始意外的一次有限开题

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-21 00:06 CST。
- 当前模式：独立只读选题，非重要突破；只写本 stage，不改 LINE、registry、代码、原四前瞻账户或其他研究线。
- 目标：六所98历史产品/95家族的全市场高质量 long 识别，再独立检验窄损与增加投注；不是正式 C9 月池研究。
- 本阶段新增模型 fit、cash、标签、行情/SQL、本地源下载、生产操作均为0；未运行外部代码、未安装依赖、未启动实验或子 agent。研究线累计按473为481完成fit/258完成cash及1旧partial，本阶段没有重验其大物料。
- 阅读：先 registry/LINE，再有界读取161、189、270、290、292、473等小记录。下表除特别说明外是LINE对旧阶段的已接受摘要与原stage定位，未重新读取旧训练、预测、账本或原始大文件。此稿已知旧成绩，不是盲选题。

## 裁决

**只提出一个新问题：公告附近真实利率意外与股票反应所揭示的信息类别，在严格延迟到本线可行动时刻以后，是否仍含有对全市场做多质量的增量信息。**

建议先接受一次小源获取/时钟检查，再决定是否值得一次有界经济反证；当前**不授权 fit/cash，也不把宏观新名字自动变成统一 veto**。若原作者原始变量、时区、计算窗口或实际支持不能闭合，就在源阶段 NO-GO，不改成其他央行、BVAR、全样本PCA、第三方延展或另一种意外指标。

这条路优于继续annual频率/窗口救参的原因是：原始FOMC事件意外不是旧52项价格摘要、已有ECB汇率变动或成熟时钟的确定函数；它确有独立观测来源。它仍可能在国内可入场前已被价格吸收，不能预先称为alpha。原料到位只使一次反证可实施，不使成功概率高。

## 已失败谱系与本题边界

| 旧证据 | 已确认的失败或否决对象 | 本题为什么不同，以及仍受什么限制 |
| --- | --- | --- |
| 010/024/035；056、097 | 短历史/有序表示/同行价格关系/期限scalar；097四收益增加但四DD更深、四CI跨0 | 不扩大旧价量表示、容量或学习器；使用国外事件窗口原始利率和股价变化 |
| 064、115、170、193 | EIA季节库存创新、会员类别/集中度、仓单登记变化各自固定包unsupported | 新题不是库存、具名持仓或其另一种归一化；这些物理/持仓包不能为FOMC签方向 |
| 073、082、103 | 窄损交换收益/DD、一手预过滤、固定log效用均未达目标 | 不换止损/风险floor/效用标签，不把宏观状态当加注许可 |
| 126、133—142、150、159 | 长历史、选月/条件排序、FX及交割日历；选择/资金正线索未形成稳定资格 | 不是重复FX回报或重新分解旧资金赢家；保持全母体，不从旧正分成交集合起步 |
| 208、221、240 | 局部曲线、训练loss域与纯K目标替换分别关闭 | 目标/训练域/预算保持原对象；不以新宏观变量掩盖旧标签重训 |
| 223—225、270 | 季节/VIX直接scalar被设计否决；270明确拒绝EBP一列/统一信用veto | **必须正面继承270：同日共同scalar主要改变日期准入，其直接项不能区分同日月份/品种；不能冒称全市场异质识别。** 新源与EBP的区别是可直接观察的事件金融价格变化，并可避开月度模型全历史修订；不是免除发布/PIT问题 |
| 269、284—289、299、309 | 现货S过滤、WASDE当月量offset、reopening q20与成交月池OI份额均关闭 | 不重命名月报/旧标量或翻符号；WASDE无动作增量也不证明所有外部事件没有信息 |
| 290、292、315—316 | 泛动态组合/盘口/未校准LCB不值得当前启动；整数包技术fail-stop，非经济反证 | 不上优化器/置信门，不改solver救旧包；新问题先回答事件信息是否在允许入场后仍存在 |
| 405、409、429、443、460、465 | 固定天气样本量不足；旧COT净标量金融后继关闭；RB/HC→I延迟传导、作物GE、Con4无稳定优势 | 新题不复活这些源。429/443的“发布后可成交窗口”方法纪律值得继承；原公告瞬时效应绝不能当延迟入场收益 |
| **469—473** | 固定annual成熟扩窗：2020base C87.687797%/DD−19.374476%，A122.927022%/−15.627420%；主stress DD恶化，四CI跨0 | **实读473。** 不换月/季/rolling/decay；FOMC是在给定旧样本时添加独立观测，非以更新时钟重训旧52翻案 |

原记录定位均在本线`stages/`：056 `20261018_1453_stage056_maturity_information_cash_decision.md`；064 `20261018_1559_stage064_eia_inventory_event_cash_decision.md`；073 `20261018_1658_stage073_settlement_narrow_joint_decision.md`；097 `20261018_1842_stage097_crossday_order_bag_decision.md`；103 `20261018_1905_stage103_log_utility_decision.md`；150 `20261019_0037_stage150_fx_fixed_comparison_decision.md`；208 `20261019_1930_stage208_local_curve_information_decision.md`；221 `20261019_2031_stage221_training_domain_loss_decision.md`；240 `20261019_2146_stage240_K_target_decision.md`；270 `20261020_0042_stage270_credit_supply_information_screen.md`；292 `20261020_0138_stage292_calibrated_uncertainty_participation_review.md`；429 `20261020_1912_stage429_product_material_timing_root_decision.md`；443 `20261020_2114_stage443_crop_condition_root_decision.md`；473 `20261020_2358_stage473_annual_mature_root_decision.md`。本表不宣称旧所有包已证明一切AI无效。

## 外部原始方法与GitHub核证

本轮使用web阅读原论文/机构说明与维护者源码；未clone、下载本地CSV或执行其代码。搜索中第三方汇总和社区推测不用于下列核心判断。

1. [Jarociński、Karadi（2020），AEA原论文](https://www.aeaweb.org/articles?id=10.1257/mac.20180090)：利率与股票在公告窗口的相反/同向变化，可以区分政策意外与央行传达的经济信息；利率上升本身不等于利空。**判断：保留联合原始观测，拒绝“降息就是所有期货高质量long”的统一符号。**
2. [原作者维护仓库README](https://github.com/marekjarocinski/jkshocks_update_fed)：提供按公告日期时间的原始窄窗变量及最终分解。原始来源涉及许可行情，公开发布的源/最终数据标示CC BY4.0，代码BSD3；应记录原作者归属。**判断：只取公开派生原始意外，不尝试绕开行情许可，也不运行Matlab/PCA/旋转。**
3. [作者原始CSV，web已实见](https://raw.githubusercontent.com/marekjarocinski/jkshocks_update_fed/main/source_data/fomc_surprises_jk.csv)：头部具有`start,Event,...FF4,...SP500,SP500FUT...`，可见尾行到2026-09-16。**判断：有精确小源可取；web可见并不等于本地已获取、完整覆盖/单位/时区已验收。** FF4可避免ED→SOFR名称切换；不按哪一列历史成绩更好来选择变量。
4. [作者README原始链接](https://raw.githubusercontent.com/marekjarocinski/jkshocks_update_fed/main/README.md)与[main.m](https://raw.githubusercontent.com/marekjarocinski/jkshocks_update_fed/main/code/main.m)：最终`pc1`含全样本降维、最终分解含识别旋转。**判断：不直接使用`shocks_fed_jk_t.csv`、`*_m.csv`、pc1或median shock。** 原始FF4与SP500是新观测，最终研究识别量不是天然PIT交易输入。
5. [Ivan、Banti、Kellard（2025），BoE1114原工作论文](https://www.bankofengland.co.uk/-/media/boe/files/working-paper/2025/liquidity-monetary-policy-and-the-commodity-futures-market.pdf)，§4—6：作者以事前名义成交额表示交易流动性，报告紧缩影响在更活跃商品上更强，扩张结果弱。其样本是2000—2008海外19商品、公告日研究。**判断：它只给“冲击×事前交易暴露”一个可否决的异质传导依据；不证明2010后中国98产品同符号、不证明25h以后仍有效或可改善本线cash/DD。**

附带筛查了USDA日度大额出口销售：它确有不同于WASDE/作物状态的新需求观测，但此次未确认可直接绑定的完整原发布档案；周度查询终值存在修订，出口需求与中国进口供给对国内价格也可相反。[FAS制度原文](https://www.fas.usda.gov/programs/export-sales-reporting-program)及[原作者会议论文](https://farmdoc.illinois.edu/assets/meetings/nccc134/conf_2023/pdf/Mckenzie_Johnson_NCCC-134_2023.pdf)不足以在本轮直接支持低成本中国延迟long检验，故**不提出第二金融问题、不采集该源**。这不是历史回测反证。

## 一次小源获取的精确绑定建议

- 原始CSV：`https://raw.githubusercontent.com/marekjarocinski/jkshocks_update_fed/main/source_data/fomc_surprises_jk.csv`。
- README：`https://raw.githubusercontent.com/marekjarocinski/jkshocks_update_fed/main/README.md`。
- 优先把`main`换成实际核得的40位commit后获取同一版本两文件；此次GitHub commit API与history网页均返回Internal Error，**本阶段commit SHA未知，不编造版本**。若root只能得到branch URL，记录响应URL、UTC获取时刻、原body字节数/SHA256及branch可变性，以本次源快照绑定，不冒称commit已锁定。
- 仅这两个小文件、各一次。校验列名/事件时间/计划与非计划类别/空值/重复，逐年和两cutoff前后支持；没有足够原始数据就NO-GO，不第三方补齐。原始数值与缺失保留，不计算最终shock，不为了样本门改FF4为另一项。
- `start`的时区在本轮所读README中没有明确说明。先保持naive/unknown，须与Fed官方公告及DST锚点明确核对，不能当UTC或机械固定差13小时。
- **计算窗口关键：**作者post值原取`[t+15min,t+25min)`附近中位数，少于3观测时可能再扩展最多24h。因此单写`t+24h`可能仍早；后继若没有逐事件实际endpoint，建议最早可消费研究上限取`t+25h`，并按时区/DST转上海时刻后，映射其后第一个真实可决策u，再使用原下一全局D开盘。此延迟只覆盖已知计算窗口风险，**不证明作者当年已发表该CSV、原行情firstseen或strict PIT**。原始历史重建假设须明确标示，不能因此认证实盘。
- 公开源若后续修订/供应商修补仍可能改变过去原始数值；接受条件仅为带限制的研究快照。不得用“固定滞后”消灭所有修订风险。

## 最小实测设计建议：源通过后另冻一次，不立即跑模型

**问题表述：**给定原52与当时可观察的本品种状态，`FF4>0、SP500<0`的政策紧缩类原始事件，是否在本线可行动之后，仍对做多stress净R质量产生可重复的负向差异；其他同向信息类是否呈不同关系。只有原事件原始量，不复刻因果SVAR，不以“纯政策冲击”命名未识别raw类别。

1. **先固定来源，再冻结经济检验。** 两输入只选FF4和SP500，SP500缺失不以FUT自动fallback；两者合法0与缺失分开，非事件与缺源也分开。用原生正/负/0分类，不选分位或力度阈值；25h消费延迟不扫描。2010—2019只作开发描述，2020—2025为预声明反证期、2026不完整另报。既有历史已被研究反复使用，这不是全新盲OOS。
2. **全98/95母域和原始可行动子域。** 不从原AI正分/成交/闭合赢家起步；每事件按真实u、same epoch、原资格与共同K保留全部月份。未知/取消/未成熟/缺价不填0，动作、同族月份与同事件多产品均不算独立公告。训练/held若未来使用，同行聚合不得泄漏被留出的family。
3. **先回答可交易时段是否还有信息，0预测fit/0cash。** 一次有限关联测量优先使用原129已接受的stress净R对象及已成熟时钟，不更换为log/K标签；另将公告到入场前价格调整与D开盘以后变化分列，不能把前者记为可得利润。若无法给未决样本有限完整界，结论保留unknown；不能仅在已闭样本上宣布完整机会质量改善。诊断回归/相关量若需估计，也应与新增预测模型fit严格分别记账。
4. **异质载体不得补故事。** 单独共同FF4/SP500直接项不能在同u内排序；若欲走全市场识别，唯一当前有原方法支持的载体是**公告前已完成日的名义成交额**，按原epoch成交量×当时乘数×原可比价格取log，不用公告后成交量。优先已验收settlement；若缺源则unknown，不静默用close替代并声称论文复刻。只检验预先固定的“紧缩类强度×事前流动性”一项；不扫5/20/60窗、不用事后赢家选暴露或产品方向。金融/股指与商品的异质性必须完整报告，不能取表现好的类别晋级。
5. **否决条件：**在允许入场后的响应方向不稳定、原129质量关联不能超越旧状态、完整样本界不可识别、仅公告前/开盘gap有关系、或只由一两个事件/产品贡献，则停止这一具体规格；不缩短25h、换FF4/FF1/ED4、合并类别或调TTL续试。原事件足够而测量不支持与源支持不足要分别报告。
6. **后续真正用户目标的检验须另冻。** 即使测量支持，也只是允许考虑一次共同控制下的增量模型/完整重选/连续现金递推，不代表现金成功。随后固定原52/目标/成本/0.25N/K/风险，保留原四A157自身账，候选2020连续与2023冷启×base/stress最多4cash；不凭choice相同自动推现金相同、不回放控制或annual失败包。新增预测预算须由root另定，不在本提案预授权。若有任何实际回测，随后必须新派独立agent一次全面审查数据、模型、现金、置信度与bug，才可root裁决。

源阶段与第3项均不是用户目标完成。只有实际收益/DD在跨期、跨品种、成本与未知边界下站得住，才值得讨论窄损加注；不得把此次新原料、事件条数、方向相关或名义统计显著性当作那个证明。

## 本次变更、指标、反思与合入

- 唯一新增：本stage；新增/修改/删除脚本、策略参数、旧回测结果均0。
- 本阶段期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A；不是新的金融结果。
- 开始新增按结果调参过拟合：否；结束：否。没有运行新金融或调整旧包；**长期同史反复择题风险是**，宏观名字、分类和暴露选择也消耗研究自由度，不能声称零过拟合风险。
- 开始继续价值：有条件是；结束：**只限一次小源与一个可否决的延迟信息问题有价值**。旧annual/效用/风险floor/一手patch/弱特征续训没有继续价值。新源若不闭合立即停止，不以持续工程表示进展。
- 不修改LINE/registry、根memory/back_log，不触发正式A/B或生产发布，不改CTP、邮件、launchd、正式C9月池或原四前瞻账户。
- `goal_complete=false`；`production_qualified=false`；`increased_betting_qualified=false`。本stage不是下一actual授权。
