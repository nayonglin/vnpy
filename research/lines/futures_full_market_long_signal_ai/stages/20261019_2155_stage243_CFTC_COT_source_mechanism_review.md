# Stage243：CFTC COT 原始头寸的新信息与来源可行性独审

- 时间：2026-10-19 21:55（北京时间）；line_id：`futures_full_market_long_signal_ai`。
- 性质：Stage241 的独立来源研究；非重要突破版本；不修改 LINE、registry、旧工具、参数或生产。
- 本次新增 fit/cash 均为 0；累计保持 439 fit / 234 cash。未下载历史压缩包，未读取收益、模型、旧大表或新训练数据；完整 goal 仍 active、未完成。
- 研究前反思：**有同一历史反复择题的过拟合风险**。有价值的是先排除重复输入及不合格时钟；没有资格凭论文或“原始数据”名义开启新一轮拟合。

## 结论先行

**当前不推荐 COT 历史投影或训练，也不推荐把旧 managed-money 或 producer 套保压力标量改名重开。** 本线未发现已实际训练 CFTC 同输入，但其他趋势线已经重复关闭同一类跨境 COT 标量；这不证明所有类别结构永久无效，却足以否决“换个名称、窗口、权重或映射再试”。

类别数量在理论上包含价格及总 OI 无法唯一重构的信息；然而，当前未闭合当时可见分类、首发版本、实际发布日期及中国商品映射。修好这些属于来源资格，不是 alpha 证据。当前已有的有限网页核证已发现实质障碍，不继续制造发布日期库或批量抓取工程。

## 仓库去重：事实与边界

1. 先读 `research/registry.md`、本线 `LINE.md`。本线 Stage078 只引用 CFTC 对总 OI 的定义和类别信息的不可重构性；国内会员排名使用的 AKShare `futures/cot.py` 不是 CFTC COT。未找到本线 CFTC 训练输入或冻结候选的证据。
2. `futures_trend_drawdown30_preserve_return` 的 Stage014、`futures_trend_c9_minrisk_highquality` 的 Stage256、`futures_trend_rebuilt_c9_15w_optimization` 的 Stage048 已研究同一官方 disaggregated futures-only 源。对应 LINE 均关闭稳定交易化资格；本次只查已有结论与小源码，不重新分析其收益。
3. 旧方向标量为 MM net/OI、MM 周变化/OI，经 156 周、最低 52 周标准化，按 0.35/0.65 合并；旧映射含 CF、OI、lh、lc、au、cu、fu、hc/rb，时钟为报告日加 4 天 08:00、最大年龄 45 天。
4. **不能声称 producer 原始信息从未看过。** Stage048 小源码 `build_cot_feature_table` 已计算并输出 `producer_net_oi`、`producer_net_z`，同时保留 MM 原始与标准化量；MM 合并分数是其交易化主方向。PMPU 单标量改名不构成新的源结构。
5. 可区分的潜在结构仅是多类别 gross long/short、spreading 及其联合风险承担分布；“尚不同于旧合并分数”不等于已经取得数据资格，也不授权新增交互、窗口或筛品种。

仓库证据：本线 `stages/20261018_1712_stage078_open_interest_information_feasibility.md`；重建线 `stages/20260701_2001_stage048_cftc_cot_mapping_audit.md` 与 `tools/stage048_cftc_cot_mapping_audit.py:187`；其余两线 Stage014/256 及各自 LINE。

## 公开来源事实：时钟不能用固定 lag 替代

官方常规安排是美国东部周五 15:30 发布通常周二的头寸；节日会延后。换算为北京时间，夏令时是周六 03:30，冬令时是周六 04:30。这是常规发布时间的换算，**不是每份历史报告的实际发布时间证明**。[CFTC 发布安排](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm)

官方异常公告显示 2025-10-01 至 11-12 停摆；09-30 报告原计划 10-03，补发安排为 11-19，随后多期拖至 12 月，且补发计划曾更新。2023 年 ION 事件也造成连续延迟。旧“周二 +4 天 08:00”在正常周偏保守，在这些异常周会提前获得尚未发布的头寸；不能视为严格 PIT。[CFTC 异常公告](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm)

**本线推断：** `known_at` 必须由原首发实际时点、版本与可取得延迟决定，并满足 `known_at <= u` 的决策时点，而非只早于下一次 D 入场。正常周六发布通常最早进入下一个中国交易日的 u 决策，再用于其下一 source-open；不能倒填此前周五 u。中美节假日、夜盘归属及实际延迟必须各自遵守原交易日历，不能把所有周报机械挪到周一。

## 报表含义与历史版本：事实

Disaggregated 将交易者分为 PMPU、swap dealers、managed money、other reportables，分类依据主要业务，并非逐笔交易动机；MM 不等于聪明资金，PMPU 也不是每笔都在套保。该报告 2009 年开始发布、回溯到 2006 年；官方明确早期历史使用较近分类回填，因为不维护完整分类历史。不能把当前回溯文件称为当时已发布分类；也不能因此断言 2009 年之后所有记录都必然有前视。[CFTC 分类说明](https://www.cftc.gov/MarketReports/CommitmentsofTraders/DisaggregatedExplanatoryNotes/index.htm)

Futures-only 与 futures-and-options-combined 是不同口径；combined 以交易所 delta 折算期货等价数量，变化可能包含 delta 变化。报告聚合多个到期月，数量不是资金流入金额；总多 OI 与总空 OI 相等。报送阈值也可变动，不能跨口径拼接“长历史”。[CFTC 一般说明](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ExplanatoryNotes/index.htm)

官方历史下载分别提供上述报表族；“官方现在提供的历史文件”没有自动包含首发版本证据。重新下载、更正后的值与当时可知值应分开，未知不能填零、不能用后来的分类静默补齐。[CFTC 历史文件](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm)

## 单位、映射与中国传导：事实及推断

COMEX 标准黄金与铜对应 100 troy ounces 与 25,000 pounds；这是合约规格，不能直接套到每个同名 COT 汇总市场。必须绑定 CFTC market code、报表族、交易所、原字段单位及合并/微型合约规则，再核中国合约单位与交割规格，不能按中文商品名直接换算手数。[CME 合约资料](https://www.cmegroup.com/trading/metals/files/weekly-options-fact-card.pdf)

**推断：** 黄金/铜的全球商品联系相对直接，但汇率、税费、品级、交割地、进口约束及参与者结构仍不同。豆油映射菜油是替代关系，HRC 映射螺纹钢不是同品种，氢氧化锂映射碳酸锂不是同化学品；旧 mapping confidence 数字不是因果证据。不能在看收益后选择最成功的海外代理。

**推断：** 可能的机制是实体风险暴露改变海外套保需求，风险承担者要求补偿，再经国际定价/贸易条件影响中国价格；但同样的生产商净空也可能对应真实供给利空，MM 净多既可能传递信息，也可能反映已经上涨后的追随或拥挤。因此方向、持续期及短 K 净收益均不由类别名称决定。

**不可重构性的思想实验：** 令总 OI=100、价格路径相同；PMPU 多20空80、MM 多80空20，与二者方向互换，都满足总多空各100，却有不同风险承担分布。52 价格/总 OI 特征不能唯一恢复此分布。这只证明存在额外数量信息，未证明真实类别口径稳定、跨境有效或预测收益。

**本线结构限制：** 一条周度、商品级 COT 对同一 mother 各到期月通常给出相同值。只追加相同的线性加项，不能直接改变该 mother 内的月合约相对排序；可能影响跨商品准入，或在重训后间接改变原52系数。后者不能被解释成已经获得月合约新信息。独立信息量也接近周度商品冲击及共同因子簇，不能按百万 action 数计独立样本。

## 原始学术与 GitHub：证据限度

de Roon、Nijman、Veld（2000）原作者/出版社摘要支持自身及跨市场套保压力与期货风险溢价相关；不证明当前中国映射、当前样本或本线 long-only/K 窄止损目标。只核到摘要，未把未取得的全文当已读。[原论文](https://onlinelibrary.wiley.com/doi/abs/10.1111/0022-1082.00253)；[作者机构记录](https://research.tilburguniversity.edu/en/publications/hedging-pressure-effects-in-futures-markets/)

Fan、Zhang（2020）原出版社摘要强调中国商品风险溢价会受保证金和持仓限制影响，恰好提示跨制度泛化风险；不是海外 COT 的中国 alpha 证明。未取得作者公开复现仓库。[原论文](https://onlinelibrary.wiley.com/doi/10.1002/fut.22087)

GitHub 原维护者 `NDelventhal/cot_reports` 支持多个官方报表族，说明取数实现可参考；它不是 CFTC 官方、经济机制论文或历史首发时间/分类 vintage 认证。未安装、运行或克隆；未将聚合下载器当成时钟证据。[原仓库](https://github.com/NDelventhal/cot_reports)

## 有限下一步与明确停止条件

- **当前决定：停止旧 MM/PMPU 标量迁移；不投影历史、不训练、不测现金。** 本线没有实际试过同输入，不是忽略跨线重复失败的理由；修旧发布时间也不能反向证明旧标量值得再试。
- 仅在外部已有可信首发存档出现时，才值得另行冻结一个来源小探针：单一同物理商品、固定少数原报告，核首发原件/后续修订、实际发布时间及单位/market code；全程不接价格、标签或收益。不新造完整发布日库，不自动授权此探针。
- 若只有当前回溯分类、计划发布时间或固定 lag，停止；若结构仍只有旧 net/flow/producer-z，停止；若只能以替代品映射或事后挑市场解释，停止。缺失、抑制、未发布与真实零分别保留，不能默认为中性已知值。
- 即使来源小探针通过，也仅取得继续讨论信息结构的资格；没有 alpha、same-C、现金、加注或生产资格。尚未形成新的模型、参数、回测结果，原各项收益/权益/回撤/胜率等指标均未新增或修改。

研究后反思：**继续救旧 COT 标量属于高过拟合风险，否决；本次只做去重与来源否决具有有限价值。** 多类别数量结构值得保留为事实层可能性，但当前缺首发/vintage 证据且跨境链条弱，不值得立即展开工程。完整用户目标仍未达成。
