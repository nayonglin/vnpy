# Stage029 全市场同OPEN/DAY只删4R目标的固定政策实验

- line_id：`futures_full_market_long_signal_ai`。
- 当前模式：六所全历史long-only、全feature_ready机会的理想政策归因；不是AI训练或金融账户回测。
- 记录时间：2026-10-18 12:54 CST；完整运行12:52:49—12:53:06 CST。
- 工作区/分支：`/Users/mac/Desktop/fian`，`codex/ai-training-data-expansion`；无新分支/工作树。
- 阶段性质：执行028收益前固定的单项政策反证；实际2启动、1完整，首次纯输入适配失败保留。
- 是否重要突破：否，未发现可继续窄损加注的盈利资格。当前原整体目标未完成。
- 是否触发A/B：A/B为匹配理想历史政策，不是正式版金融A/B/C；不改正式策略或生产配置。

## 外部调研与判断

沿027/028已实际调研的原始资料：[Potters与Bouchaud](https://arxiv.org/abs/physics/0508104)、[Backtrader作者broker源码](https://github.com/mementum/backtrader/blob/master/backtrader/brokers/bbroker.py)。本agent没有重复搜索、安装或运行外部代码。判断：正偏与少数大赢家可以来自风格而非alpha；去顶是否有益，必须同时看真实DAY收盘的新增尾部、已经触目标后的回吐、双触达路径损失和成本，不能以D.high/MFE当已经兑现的收益。

## 本次变更和固定参数

- 新增：`tools/stage029_uncapped_day_experiment.py`、`tools/test_stage029_uncapped_day_experiment.py`及本阶段输出。
- 修改/删除旧脚本、旧结果、正式策略参数：0。
- 研究唯一政策差异：A保留4R PT，B删除PT；两边均同一个下一source日同reference_epoch的OPEN入场、R=.25ATR、SL=F−R、DAY退出。
- 基础研究成本0.2R/共同fill；1R压力使用同一机会，双方各再减0.8R；配对成本代数精确取消。
- 不使用024模型、预测、mask、AI池、排序或阈值；新增模型fit/SQL/网络/分钟下载/金融回测均0。
- 同399252母体、194709 ready、194168 identified、541 ready未知；所有未观察/未就绪/未知原状态保留，不用D是否可评价筛输入。
- 统计为当日共同identified机会等权，再source日期等权；2010+、2020+及2010—2026逐年，main、family_0、family_1、family_combined；家族分组只是异质性，不能称训练外留出。main两个期间60 source日moving-block、2000次、seed20261018、所有列共同索引。固定11门，无参数搜索。

冻结协议SHA `5c2ed793c64f74d503e7a474a93e4885905087b087e7925756c8395eb35100f2`。原009 manifest `ea26675e8322bee8a3c71d4ba0c731055a52a161359c1ac456de628029a5071e`及011收据绑定；feature-label原52MB与audit原14MB以SHA核验。不读SQL，不重hash378MB原库，不复制raw audit入Git。

## 共路径、数值和输入

经济分支只沿原009 `label_state`：stop_only和double_touch的B gross=-1；day_close继承原gross而不是重新除算触边，pair精确0；profit_only的B gross=(D.close−F)/R，pair=closeR−4。double的same-path配对为[-5,0]，stop/day为[0,0]。未知保持NaN。

逐事件保留归一A/B gross/net/stress、same-path pair和tail_gain/giveback/double_penalty分解；每个事件和每个source日都断言三部分和等于pair。新兑现尾部严格按B gross>4，不能以盘中高点定义。所有输出没有绝对OHLC、F、SL、PT、ATR或volume；D_close_R及原触价诊断位明确是label-only。

audit是212852条原observed全集，不是194709 ready子集。严格验证audit与原表observed集合完全相等，event_id、u、reference_epoch、D、history_state和label_state逐条对齐。已识别原价有限/正风险、OHLC、R/ATR/SL/PT、原state谓词和day_close数值做适配核验；仅数值一致性可用协议atol1e-9/rtol1e-12，绝不用于重定经济分支、触价、尾部或门。

最终adaptation结果：399252母体、212852 audit/observed、194709 ready、194168 known、541 ready未知全部保留；原stop/profit触价诊断差异均0，day_close gross核验最大差0。无新B结果用于输入修复或选参。

## 必要测试与两次真实进程

5个新行为：四状态的同路径差；共同fill费用精确取消；audit含未ready且母体/未知不变；极小原价触边数值差不能改state分支；收盘尾部和逐日分解/空日NaN。初始RED `ba7c3b` 5失败，GREEN `fa79ab` 5通过；fixture fit0，旧套件0。

第一次实际启动：chunk `bb0244` 返回session76823，终态 `64f988` exit1，12:50:09—12:50:12 CST/2.918259秒。失败为作者误把009 status的观察语义写成不存在的字面`observed`；实际枚举为`observed_long_research_opportunity`=212852、`no_accepted_observation`=186400，全部194709 ready都属于前者。失败发生于readiness断言，尚无事件/统计/B成绩，fit/金融0。

保留`experiment/actual_terminal.json`、原stdout、attempt01源/测试快照和`input_status_diagnosis.json`。用真实枚举更新fixture后，`d3d199`复现3项输入错误；仅修新脚本两处status比较，`fc6faf` 5/5 GREEN，协议/payoff/统计门均未改。root fresh核失败终态后明确授权新目录完成同一固定政策。

第二次：chunk `db6684` 返回session22593，终态 `518e23` exit0；12:52:49—12:53:06 CST，17.067514秒，唯一完整结果位于`experiment_after_status_fix/`。模型fit、金融、SQL、网络0。没有因观察timeout重新启动；如实为2启动1完整，不写成一次无故障运行。

实际stdout有一次Pandas对空字符串替换未来行为的FutureWarning；当前未知结果断言及完整计算通过，不为这一提示改冻结源或重复计算。

## 结果

以下为全机会分母下date_equal normalized代理效用，不能累加成组合回报；B单值也只指连续理想模型，不代表真实金融标签已获资格。

| 2020至今main | 下端均值 | 上端均值 |
| --- | ---: | ---: |
| A基础净 | -0.2136743838 | -0.0526714522 |
| B基础净 | -0.1835797188 | -0.1835797188 |
| B−A same-path配对 | -0.1309082667 | 0.0300946649 |
| B同mask 1R压力 | -0.9835797188 | -0.9835797188 |
| 成本精确取消后的压力配对 | -0.1309082667 | 0.0300946649 |

- 2020+ B基础净95%CI `[-0.2217563716,-0.1563068006]`；paired_lower的95%CI `[-0.1467047318,-0.1148652759]`，paired_upper的CI `[0.0237054019,0.0356362627]`。配对部分识别区间跨0，不等于真实去顶一定更差；但B自身在本固定成本和连续模型下为负，未获得继续资格。
- 配对分解：新增兑现尾部增益 `+0.0784712610`、profit_only回吐 `-0.0483765961`、double路径下端罚项 `-0.1610029316`（上端0）。非双触达的净变化为 `+0.0300946649`，不能把这部分直接当整政策优势。
- primary母表161014、ready107844、identified107437、ready未知407；新增实际DAY gross>4兑现4655条、1244日期、85家族；profit_only回吐4210条，原双触达3470条。尾部事件支持充足但无法抵偿成本与路径风险。
- 全2010+ B净均值 `-0.1835976557`；pair `[-0.1226997162,0.0259426952]`；兑现>4尾8255条、2623日期、93家族；回吐7446条、原双触达6000条。
- 两个family组primary paired_lower分别 `-0.1335360963/-0.1287261154`；2020—2025完整6年paired_lower正0/6，2026部分年B净 `-0.1589006643`。
- 固定11门 **2真9假**，仅尾部日期/家族支持通过，`uncapped_policy_screen_pass=false`。无选择品种、年份、成本或过滤来救结果。
- 期末权益、总收益、最大回撤、Sharpe、真实滑点、总成交笔数、真实胜率：全部N/A；金融回测次数0。

## 输出身份和独审

最终目录：`outputs/stage029_uncapped_day_experiment/experiment_after_status_fix/`，完整normalized事件、8个daily、所有annual/scopes/期间和11门。原输入价格仅外部绑定，不作为输出或模型输入。

- 最终源SHA `ee388ea4439b240054b8b5eb6dfa9907c6e982104ce8e6418cbe5057849d0fe2`。
- 最终tests SHA `6b89c3cfd44b472cb0b7cc19b050fcb9f5e49db68fb13e8a1b4c4c7d40a7dbd6`。
- 最终manifest SHA `3af02dfdf3eda1b61a5a1e325bb21f72bfd2f309edb589ffdc6633497732181a`。
- metrics SHA `e6168d857c963fc86397ca370a0aa2bc5ba8ad476d0ee296306dcd28f63e88cb`。
- final terminal SHA `29f4d6660d20d1026360f97062cbd48a9b9c25dad4d3a83d48f454cd74cc46a5`。
- failed terminal SHA `8758da89305a25d3f9e0deaff289bcb5f977f1096c68cfd6759dfb84a6e8f274`。
- bootstrap共同索引全2010为`f394bca43850bdce417cf2664a80142142c703bad1c11ee48839b3433933bed4`，primary为`5c0b1b714adfa5aac8e05636efabd8d8b26606cf46693031b1dcf3a9c24321de`。

030设计审查已无实质阻塞；本记录冻结时数字独立复算待root确认最终manifest后触发，不提前写通过。源、协议和结果现已冻结，不继续改分支或选参。

## 反思、后续和合入建议

运行前过拟合判断：按成绩救参否；有长期研究选择风险。此次预声明只删PT，0模型/0阈值搜索。运行后判断：未通过则停止本全ready OPEN/.25ATR/DAY去顶包；继续改5R/8R、持有期、SL、年份/品种/过滤/成本救结果会增加过拟合，不能复用024失败模型换目标重评。

运行前价值：有，一次低成本且直接可证伪的经济结构问题；运行后重复本包无继续价值，保留新兑现尾部、回吐与双触达损失的分解有价值。结果不否定多日趋势、全市场AI或跨周期信息，但也没有达成真实净收益、低回撤、窄损加注生存目标。金融/生产资格false，原goal继续。

TODO：030独立核全事件/原state/共路径/分解/日年期间/两个CI/11门；root统一归档并决定新的独立问题。本agent不改LINE、registry、root memory/back_log，不commit/push/deploy、不连接CTP、邮件或委托。
