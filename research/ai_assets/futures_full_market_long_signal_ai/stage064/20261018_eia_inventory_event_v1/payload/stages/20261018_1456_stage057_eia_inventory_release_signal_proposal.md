# Stage057：只检验一次 EIA 实物库存公布创新的日级做多价值

- line_id：`futures_full_market_long_signal_ai`。
- 记录时间：2026-10-18 14:56 CST；当前 `codex/ai-training-data-expansion`。
- 阶段性质：只读研究设计；采用 brainstorming 的研究回答路径，输出问题、取舍和可推翻的实验设计。本阶段没有实施代码、训练、回测、SQL、分钟下载、提交、推送或生产操作。
- 是否重要突破：否。新外生信息有机制，尚无成绩；完整全市场 long-only、更高净收益/更低回撤、极窄止损与加注目标均未完成。
- 边界：停止旧 maturity q、旧 HGB 包及其救参；始终沿当前全市场高质量 long AI 目标。不改 053/054、旧数据、LINE 或 registry。

## 先接受已经发生的否决

实读 registry、本线 LINE、052 合同、054 已完成现金输出及 055 独审。054 三臂中的 ALIGNED 主 2020 base 期末权益 `1,026,053.41`、收益 `2.605341%`、最大回撤 `-8.168680%`、Sharpe `0.124878`；COMMON 与 SHUFFLED 同为 `3.381142%`。两组配对平均日 log 增长差的 95% CI 同为 `[-0.0000236005842, +0.0000127959320]`，没有信息增量支持。ALIGNED 的 2023 冷启动 base/stress 分别 `-5.541878%/-7.878773%`，主 stress `-0.930606%`。

本阶段仅对已存的 ALIGNED 主账户 position_days 做了一次很小的分组读取，没有重放：base 的一笔 `SHFE.WR.202301` 在 2023-01-03—2026-10-16 有 915 个 stale 持仓日；stress 的 `SHFE.WR.202210` 在 2022-10-10—2026-10-16 有 975 个。账户出现 stale 的 source 日共 936/994 天，这些天大多来自同一持续未解决暴露，不能称为数百个独立市场失败。这里只识别了保存账本里的集中来源，没有判定原生缺价原因，也没有假想成交替它平仓。

ALIGNED 期末 base/stress 仍分别有 3/2 个开放仓、各 1 个 stale 仓；把全部开放多头标为零的情景权益为 `892,633.41/907,133.94`，都低于本金。这是特定估值情景，不是普适下界。旧 q 的否决已经充分，不需要先修完这些仓才接受否决；同样也不能删除它们，把名义微正提升为可实现收益。

## 三个方向的比较，只选一个

| 方向 | 新增机制与可执行性 | 不选/选择的判断 |
| --- | --- | --- |
| **EIA 每周实物库存公布创新** | 原油、汽油、馏分油的实物数量来自美国供需统计，具有明确 release cohort，可检验库存变化后全市场是否存在未计价的共同定价/风险传导。官方公开表很小，现有 049 标签与现金核可以复用。 | **选择。** 信息本体不是国内自身价格、国内同行收益、仓单/会员排名或期限曲线；最大的反证也清楚：到中国下一次日收盘时可能早已计价。训练、预测及可交易选择覆盖全family；四油品只作为事前直接物理暴露诊断组，不能凭其成功声称全品种有效。 |
| 单一美元/人民币公开发布创新 | 美元融资与人民币进口替代成本具有跨商品机制，理论覆盖更广；FRED/ALFRED 支持 vintage。 | 暂不选。Fed H.10 是美东周一 16:15 才发布上周 daily FX；不能拿 observation date+1 当可得时间。按真实公布时钟后，这个公开载体偏慢，首项实验的经济解释不如定时库存事件直接。不是否定全部外盘/FX 信息。 |
| 利用现有现金状态重定义风险/持仓动作 | 不需要新数据，可以直接优化账户净增长。 | 暂不选。当前 own OHLC 与账户变换无法凭空增加方向信息；本次直接改持仓、止损、风险额度容易变成对失败成绩的救援。先处理一个真正不同的观测来源。 |

H.10 的公布时钟来自 [Federal Reserve H.10](https://www.federalreserve.gov/releases/h10/)，vintage 语义来自 [FRED realtime period](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html)；[fredapi 维护方源码](https://github.com/mortada/fredapi/blob/master/fredapi/fred.py)提供 all releases/first release 的接口参考。此次不新增宏观列或获取 FX 数据。

## 一手论文与 GitHub 调研，及我的取舍

1. Gorton、Hayashi、Rouwenhorst 的 [The Fundamentals of Commodity Futures Returns](https://www.nber.org/papers/w13249)研究实物库存、便利收益与商品风险溢价的联系。它支持“数量状态具有独立经济含义”这个出发点，**不证明** EIA 周度创新能在中国日级交易里赚钱，也不保证库存下降总是做多。
2. Ye、Karali 的 [The informational content of inventory announcements: Intraday evidence from crude oil futures market](https://www.sciencedirect.com/science/article/pii/S0140988316302110)及[作者公开会议稿](https://ageconsearch.umn.edu/record/205595/files/AAEA_Ye_Karali-2015.pdf)研究 API/EIA 库存公告对即时收益与波动的影响，并指出 API 与分析师预期会影响 EIA 的新增内容。**对本案最有用的结论是反证约束：已有证据主要发生在分钟级，不能外推成隔夜或多日 alpha。** 本案不拿季节变化替代付费调查预期而称作市场 surprise。
3. EIA 的 [WPSR archive](https://www.eia.gov/petroleum/supply/weekly/archive/)将 release date 与 data-ending date 分列；实读的 [2011-08-03 旧期](https://www.eia.gov/petroleum/supply/weekly/archive/2011/2011_08_03/wpsr_2011_08_03.html)和 [2020-01-03 旧期](https://www.eia.gov/petroleum/supply/weekly/archive/2020/2020_01_03/wpsr_2020_01_03.php)都提供 Table 1 的 CSV。前者证明有可执行的小型旧期载体，后者明确 2019-12-27 的统计值到 2020-01-03 才发布；不能按统计周结束日回填。
4. [EIA release schedule](https://www.eia.gov/petroleum/supply/weekly/schedule.php)通常为美东周三 10:30，假期会变日、变时。获取技术参考看了 [EIA API v2 官方文档](https://www.eia.gov/opendata/documentation.php)、[rOpenSci/eia 维护仓库](https://github.com/ropensci/eia)及其 API v1 退役 issue。借鉴小表获取、类型、分页和元数据处理；不安装 R、不复制未经验证的老 API v1 下载逻辑，也不把 wrapper 当经济 alpha。

判断：值得做一次低预算的**新信息证伪**；不是已有论文替我们证明中国日级延续。库存减少可能由供给受损，也可能是炼厂活动/出口/统计调整造成，方向需要训练前冻结的规则和对照共同约束，不能只挑某一分量或弱年解释。

## 唯一信号与当时可知时刻

### 输入与数据量

只新增三个全国库存系列，单位 thousand barrels：商业原油剔除 SPR（[WCESTUS1](https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=WCESTUS1&f=W)）、[总汽油 WGTSTUS1](https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=WGTSTUS1&f=W)、[馏分油 WDISTUS1](https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=WDISTUS1&f=W)。不加 Cushing/PADD、进口、产量、炼厂、美元、新闻或其他库存族。

实施时一次获取 archive index 与每期 Table 1 小表，最多 900 期；只提取三库存值、当期表中的周变化、单位、data-ending、release ID/date/time 与原链接。当前 archive 从 2011 年可见的部分开始；没有声称 2010 已有完整旧期。现代历史 XLS/API 只作数值/单位对照，不将今日修订值混入当年发布的创新。无需取全球期货价格库、下载分钟或重新构建 399252 个标签。

当时 archive 的历史重建是本实验的观测口径，不冒称当年实际下载留存的字节证据。优先从每期自己留存的 Table 1 取当期数值；缺旧期时保留 `external_value_unknown`，不以今日 revised series 填完后声称 PIT。孤立缺期不触发整套资格工程：全母体和动作结果仍输出，缺值三臂共同中性处理，是否还能作出判断由实际信息量及未知风险决定。

### 公布时钟与事件机会

- `available_at` 用 timezone-aware UTC 瞬间保存。官方历史记录能确认时分的按实际时分；只有 official release date 的旧期，固定用该 release date 的 **23:59:59 America/New_York** 作为保守日末可得时刻，并标 `date_only_conservative_end_of_day`。不将当前通常 10:30 机械回套所有历史假期；DST 由 IANA 时区转换。
- 公告发生在中国夜盘中时，不能假设能在日 bar 的最早 open 追单。只在 `available_at` 后第一个完整中国 source 日收盘 u 决策，再在下一 source 日 D 的同 epoch open 请求成交。日 bar 是含夜盘的合成交易日，不能用标签日期代替实际 close 瞬间。
- 具体例子：美国周三10:30 EDT约为中国周三22:30，名为周四D日的native open可能已经在周三21:00发生，不能追溯成交。首次纳入中国周四u收盘，随后周四21:00的夜盘/名为周五D日的native open才可执行。保守旧期日末时钟也沿同一规则；检验的是留下来的库存状态价值，不是即时抢新闻。边际很弱也不缩短这个延迟救参。
- 每个 report 最多形成一个中国 u 事件；中国长假若多个 report 在同一首次可用 u 前发布，只保留最新一期作本次观测，较早一期标记 `superseded_before_first_decision`，不为它们补发订单。库存预测的历史状态可以按公布顺序更新。
- 母体仍为完整 049 `399252` 行，普通/F 共享 family。报告缺失、未就绪、取消、unknown、open 和非事件日都留在输出；“公告事件日”及暴露是 u 时已知的政策定义，完全不看未来 filled/closed/标签。

### 一个创新标量，禁止寻找最优分量

对按**发布次序**编号的每期 r、每库存分量 k，令 `delta[k,r]` 为该期 Table 1 自己公布的周变化，`I[k,r-1]` 为上一期已公布库存：

`z[k,r] = -(delta[k,r] - delta[k,r-52]) / I[k,r-1]`

`s[r] = mean(z[crude,r], z[gasoline,r], z[distillate,r])`

52 是固定年度发布 lag，不扫 26/52/104，也不把缺期压缩成连续周：少报/重复报告以完整官方 release calendar 的编号识别，不能将缺一周后的第 52 个非空值当旧52周。任一必需值缺失则 scalar 缺失，三分量不按可用个数临时重加权。早期未满52期也缺失。这个量只叫“相对上一年周变化的季节创新”，**不是市场调查 surprise，不宣称因果识别**。它可能非常噪；若无用就停止本定义，不换季节窗救它。

固定直接物理暴露诊断组为 `INE.SC、INE.LU、SHFE.FU、SHFE.BU` 与当前 004 母表的交集。它们是原油或直接油品暴露，不用 054 赢家/stale 名单挑选；这四个 family **仅作事前解释分组，绝不是交易池或训练过滤器**。全母表每个当时有行情与20bar历史的品种均可由模型决定开/不开；非油品也可以开仓，普通/F 都是合法表达但共同占 family 风险。库存与油价可能经成本替代、通胀/风险定价传导至其他品种，也可能根本无可交易溢出；这是待检验假设，不预认全市场因果。共同参数重估造成其他family预测变化属于完整信息模型包的效果，不能把三臂差异冒称纯油品因果效应。

## 对照、模型、训练/测试时钟和一次规模

新问题是“库存发布之后，全市场哪些当时机会还有足以覆盖成本的继续做多价值”，不是把 q 换名字后继续旧53槽 HGB。新建事件研究入口，不能覆盖或加载 053 的预测/模型作新成绩。

- 三臂 `COMMON_EVENT / INVENTORY / PAST_SHAM` 都在同一已知 report event、相同全family母体内提出开仓，退出沿已有 2N/20low、无PT，不改资金、成本、止损或加注。非报告事件日不产生新开仓，但保留全部原行与退出请求；这只是事前可知的共同决策时间setup，绝不是品种池。`COMMON_EVENT` 只是该新事件问题的共同参照，与054每日 COMMON不同，不能拿054的3.38%直接当它的结果。
- 共同控制只用 u 已知的 `stress_u_cost_R、low20_distance_R、r1_atr` 及对应3个missing indicator，再加同一 `external_missing` 标志。新增三槽为 `s、s×r1_atr、s×low20_distance_R`，共 **10槽**。共同列只作已看到的价格反应/交易成本控制；不恢复 S11 其余列、market lag、RFF、rho、carry、OI 或会员排名。
- 模型只用固定 `Ridge(alpha=1, fit_intercept=True, solver=cholesky)`；三臂相同10槽。COMMON 的新增槽在标准化空间恒0；INVENTORY 用真实当期 s；PAST_SHAM 用下述严格过去标量。交互用同一 mature-train common scaler 后的 r1/low-distance，缺失 s 的新增槽归0，external_missing 保留。训练内 finite mean/population std、无clip、无目标变换；q/scalar scaler 由同训练行两信息臂各半权重联合计算。不换模型、alpha或seed。
- **PAST_SHAM 明确定义**：当前 r 可用且有历史时，在 r 之前52期已实际发布且 scalar 可知的报告中，用 `SHA256('stage057_past_sham_v1|'+report_id)` 固定选择一期 j；用 `s[j]`，所有family及普通/F共用同一 j，再重算交互。当前 s 缺失或无过去可用候选时，两信息臂一起标缺失。任何测试期将来报告都不能当候选；不得全期乱序、不得同日交换这个共同 scalar。此对照保持因果时钟与相同容量，**不承诺相同bag或完全相同分布**；它检验新鲜库存创新相对陈旧历史伪信息的价值，不能单靠赢它声称严格随机因果效应。
- 两个固定训练 cutoff：`2020-01-01、2023-01-01`；第一组只负责 2020—22 的 u，第二组负责 2023—2026-10-16。训练为报告事件中**全family**满足 `u<cutoff、label_known<cutoff、closed_complete_bar_model` 的049 stress netR；其他标签仍null。三臂严格共享完全相同的训练行、权重、事件预测母体和10槽容量，不以是否油品过滤。训练内 family 含首尾区间 uniqueness，先按 report cohort 归一再均值1；不把一个公告的普通/F、多品种和持仓天数视为独立消息。scaler 和模型都只见这个成熟集。
- 一次最多 **6真实fit**（2cutoff×3臂），不CV、扫参、family矩阵或新标签build。保留全2020+母体输出；报告事件内每个family的唯一动作为当时 history_ready20 且 finite score>0，其他family不被硬设为0。非报告事件的 `selected=0` 是统一时间setup；外部值缺失则共同中性处理并留unknown标志，而不是删除某个品种的机会。完全不按未来已闭合/无stale过滤。
- 一次 **12现金账户**（3臂×2020连续/2023冷启动×base/stress），只复用已独审042纯现金核。100万元、单family0.25%、总2%、margin25%、buffer1.10、u联合预算、D只减不增、旧epoch退出、两成本情景均不变。6fit与12账户是未来单次实施的上限，本057实际均0。数据导入、拟合、现金比较可连续完成，不把“又完成一次源资格盘点”当研究终点。

这6个模型没有 family 留出训练，因此各 family 结果只作运输范围的描述，不能称 strict held/zero-shot。独立信息量按 report cohort 报实际数量；2020以后仅约数百次周公告的量级，而且历史已多次看过，不是真正研究者未见样本。把不同品种重复消息数十倍放大并不会增加宏观历史。

## 如何走到现金、回撤、窄损与加注，及最大的反证

**本次只允许三种结论：支持一次有限的信息候选、不支持、因未知风险无法判断。** 先看新信息是否产生可复验的增量，再看现有执行/估值限制下是否能解释为经济优势；两件事分开报告。

1. 主2020 base 的 INVENTORY 对 COMMON_EVENT、PAST_SHAM 都要净收益更高、最大回撤不更深；同 source 日配对 log 增长差，固定252日 circular block bootstrap/2000次/seed20261018，两对比共同95%CI下端>0。bootstrap不制造独立新市场；极少公告和长持仓会让区间很宽，宽区间就是未获支持，不能扩大模型/换窗口寻求通过。
2. INVENTORY 自身 stress 净增长为正、无破产；2023冷启动两成本相对两参照方向一致且回撤不恶化。报告全部开放/unknown/stale、相关本金/名义暴露、费用和滑点，保存预算与现金恒等式。若未解差异暴露足以翻转配对方向，则只能“不确定”；不得剔除未来stale事件、补零未知标签、假定强平或只展示已闭合域。零值情景照报但不是普适下界。
3. 成绩必须同时披露每个family、每个完整年度、最大赢家，以及预声明四油品直接暴露组/其他family组的贡献。油品组只是诊断，不另拟合、不改变动作。多个family不是多个独立宏观市场；如果只有一个品种或一次冲击在赚钱，最多接受局部事实，不扩称全市场普适。不会删除最大赢家再筛参数，也不从弱年另挑条件；共同系数重估影响其他family是完整模型包对照的一部分，不伪装为纯油品因果效应。

最大反证是**信息在可执行的日级决策前已经被吸收**：论文的分钟级响应若到中国下一完整日close已消失，INVENTORY就不应稳定优于同事件共同控制。此时直接停止这一个新鲜库存季节创新/日级决策组合，不把动作前移到当天早盘、不下载分钟寻找另一个时间窗、不加分量、调查预期、交互、模型、seed或窄止损救结果。未通过也不否定所有外生信息或所有AI。

极窄止损不是本次调参目标。先证明已公布消息在实际可交易时点留下的**净**条件优势；仅有日OHLC无法证明小止损不会先被打掉、没有跳空穿越或可按bar内理想路径成交。若这一步通过，后续另冻持仓内路径/摩擦问题，用因果精度足够的少量执行证据检验同一信号的止损后生存；成本/tick/gap已经超过窄损预算时就承认目标不可能。加注也必须等条件尾部风险与额外手数的边际净价值被独立现金验证，不能因score更高就倍增风险。本提案对窄损/加注授权与资格均为0。

## 本阶段结果、反思与交接

- 新增：本中文 stage 与很小的来源/只读收据；没有新增或修改实现代码。新增/修改/删除交易参数、回测结果均为无；上文只是未来单次实验设计，须与052分开冻结后才能实施。
- 本阶段新增期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率：均 N/A。引用054 ALIGNED主base的已完成结果为：总滑点 `15,811.762946 CNY`、closed trades `461`、closed net win rate `37.527115%`；这些不是本057新回测。
- 055代理对草案做了只读挑战：跨周shuffle会有未来泄漏、共同参数重估会改变非oil动作、现代修订值不是首次发布值、样本是公告不是行数。最终设计使用过去52期 causal sham、archive数值及保守日末可得时钟、report聚类；root审查后修正范围为全family相同资格，并明确接受全局系数变化是信息模型包效果，四油品仅诊断。没有新增试验成绩。
- 开始过拟合判断：**否（没有新增搜索）**，但重复历史择题本身有选择风险。结束判断相同：没有用054成绩选EIA分量/窗口/品种赢家，机制清单与最大反证均在任何新收益前写定；将来如改它们应视为新实验并累计选择成本。
- 继续旧q/旧HGB包：**否**；继续全市场目标：**是**；继续本提案：**是，仅值得一次6fit/12账本的有限证伪**，不能预先说值得加注或晋级。EIA是可执行的一块新增实物信息；全family参与选择仍不代表它对所有品种都有信息，局部成功不能等同于完整目标。
- 本阶段不更新 LINE/registry，不改根memory/back_log；合入者可读本稿决定唯一下一行动。无本057训练/回测成功声称，无提交/推送/生产。
