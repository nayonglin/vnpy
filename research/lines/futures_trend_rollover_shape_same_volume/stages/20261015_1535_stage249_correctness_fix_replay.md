# Stage249 正式回测权益与成交正确性修复及全周期重跑

**最终验收摘要：已完成2020-01-01至2026-10-14的严格离线重跑，初始15万元，期末2,262,595元，总收益1408.40%，最大回撤-48.79%，Sharpe 1.367364。全程402个完整周期，胜率28.36%。2025-09以来9/63盈利，胜率14.29%，期间收益-38.84%。两位独立reviewer的来源、执行、账本与统计审计均通过；DD40仍未通过，未发布或部署生产。**

正文保留每轮诊断历史；最终验收数字、年度/月度表和63个近期完整周期明细见下方“最终严格回放结果”。旧Stage246/247结果原样保留，不再作为修复后的业绩依据。

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：day；用户授权“先修复问题并重跑吧”。
- 记录时间：2026-10-15 15:35 Asia/Shanghai起。
- 工作区：`/Users/mac/.codex/worktrees/formal-correctness-replay/fian`，冻结起点`77538e394167c290d5f2923f4d08931b9bbd7c4f`。
- 阶段性质：Stage247已确认缺陷的正确性修复；不是alpha优化或参数搜索，不触发新策略晋升/A/B。生产部署、正式物料发布另属执行流程，本阶段仅离线修复和复验。
- 是否重要突破：否（不是alpha突破或正式策略晋升）；这是已独立验收的基础正确性修复，不以收益提高作为成功条件。

## 外部调研与判断

- [VeighNa官方Portfolio回测源码](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py)：参考日初持仓盯市与本日成交盈亏分开计算的守恒关系，以本地冻结vendor为实际验证对象。
- [上期所交易时段](https://www.shfe.cn/services/calenderandholidays/tradinghours/)：夜盘按所属交易日归属，不能直接以自然日筛选。
- [Backtrader官方订单撮合说明](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/)：参考跳空穿越stop时使用可实现开盘价格；不复制整套引擎，不升级依赖。
- 判断：使用会计恒等式和时间因果约束修复；不依据回测利润挑选修法。分钟OHLC不能恢复tick先后，对歧义采用事先固定、明确标记的审慎约定。

## 已授权设计与实现计划

用户已批准上轮报告列出的“权益记账、交易日、跳空价格、最小跳价、分钟内顺序”修复范围；在现有类和回测入口内做有界修复，不重写alpha。

- [x] 权益任务：`qmt_roll_portfolio_strategy.py`使用日初继承仓位计算持仓盯市；本日成交只计算成交到收盘部分及成本。先写手算开仓、平仓、加减仓、反向和多合约失败测试；再修复并核对每日内部权益与最终账。
- [x] 执行任务：Stage847/827从开仓的实际执行时刻起，扫描同一交易日合法时段；排除下一夜盘。先验证周末/节假日夜盘和无夜盘品种；合成成交价必须符合合约tick和对应bar范围；跳空及同bar歧义有固定审计语义。
- [x] 回放任务：独立Stage249入口验证冻结m0008 AI/参数和明确代码补丁；不改CURRENT/manifest，不把修复源码冒称已发布正式物料。保留代码、数据、模型SHA及离线标识。
- [x] 数据任务：复用Stage246已验收数据的独立副本；按新路径实际访问闭环补缺分钟。每次只补数据缺口，不能拿缺数据的路径作为正式结果。
- [x] 验证任务：失败测试→修复通过→相关集成测试；全窗口回放每轮结束由独立agent审核数据、逻辑、指标、置信度和bug。最终核对权益、tick、分钟范围、交易日、AI池、输入不可变及参数无漂移。
- [x] 交付任务：全周期与2025-09以来的前后结果、年度/月度归因、剩余限制，中文stage与可复验工具。不按收益决定是否保留正确性修复。

## 冻结回测参数

- 窗口：2020-01-01至2026-10-14，沿用上一轮已验收数据截止，修复为严格交易日边界；预热2019-06-01起。
- 账户：150,000元；C9/Stage847/Stage037，0.5R止损、最多一次重试、Top10非fu+固定fu。
- AI：m0008_20261008T204054+0800_2a7420a9f955；2020年至2022-01沿既有静态池，之后真实历史月池；不伪造缺失历史月池、不重训。
- 手续费/滑点：沿正式零手续费、原品种滑点、成本倍率1.0，不另改成本假设。
- Alpha/风险/AI/成本参数新增、修改、删除均为0；执行完整性开关新增1项（默认True），新增历史tick规则和诊断信息；删除参数0。
- 不改原始Stage246/247结果；生产/CTP订单API为0。

## 结果

### 16:08中间记录：diagnostic_round1，明确不验收业绩

第一轮以 `--diagnostic-incomplete-minutes` 收集修复后实际路径；账户/风险/AI/成本字段逐项与Stage246冻结参数一致，代码与6,230个输入文件回放前后hash一致。运行正常完成，但316个唯一合约交易日中203个分钟覆盖不完整，缺27,135分钟；没有完成数据门，因此以下仅用于保存这轮诊断，不是修复后正式结论。

|指标|诊断值（不得作为验收业绩）|
|---|---:|
|期末权益|2,893,020.00|
|总收益|1,828.68%|
|最大回撤|-42.76597%|
|Sharpe|1.434733|
|总滑点|661,970.00元|
|总成交数|763|
|完整持仓周期/盈利周期|376/120|
|完整周期胜率|31.9149%|
|期末未平仓|cu2611.SHFE 多10手，净盯市6,000元|

独立review：逐日内部权益与vendor净账最大差`2.33e-9`元，独立成交现金流+期末持仓市值最大差`1.86e-9`元；763笔成交/usage/clock一一对应且时序单调、交易日截止通过；224笔合成成交都能找到触发分钟且无bar范围外价格。数据门尚未通过，完整pytest的基线也已有21失败+1可选polars导入错误，不能宣称全仓测试通过。

新增已确认缺陷仍在修：

1. 同日收盘成交入口在结算后更新承接仓位；已由真实SameDayClose 5项红→绿以及21项权益测试和独立review关闭。
2. 普通T+1成交没有按原订单信号批次同步实际入场价到layer/entry-risk，影响后续锁盈/账面归因；必须按订单身份修复，保留信号日期与持仓年龄。
3. 碳酸锂历史tick不能用当前20代替；[广期所发〔2024〕337号的会员原文转发](https://www.ciccwmf.cn/gsgg/89279.jhtml)规定2024-12-17结算后变更，即12-18交易日起从50改为20。原交易所URL超时，两个会员完整转发交叉一致。诊断的3笔原始价符合历史50网格，1笔合成价需修；不改既有滑点成本假设。
4. 普通开盘代理沿用的旧夜盘名单漏SH，导致烧碱部分21:00成交被延到次日09:00；必须以统一交易时段的首分钟确定next-real-open，首分钟缺失时严格模式失败。
5. 空消息异常需可靠传播；导出以trade_id补全合成平仓原因，分别保留物理时间与所属交易日。

没有按这一轮利润保留或取消任何修法。后续待全部缺口补齐和上述修复复核后严格重跑；诊断结果不覆盖Stage246历史结果。

### 16:12中间记录：diagnostic_round2按防错条件中止

第二轮在第一笔普通开仓触发`intraday_unmatched_open_fill:BACKTESTING.1`，引擎正确向上抛错；未产出指标，不属于完成回测。此前40项执行窄测试、21项账户测试通过但未涵盖此真实订单关联情形。已交实现者定位、独立reviewer复核，补真实集成用例后继续；不关闭此防错条件来跳过问题。分钟源补数在独立目录继续，无cache合并。

### 16:24中间记录：diagnostic_round3正常完成，仍不验收业绩

真实日期合同已修：仅比较时解析`YYYYMMDD`/ISO日期，保留原layer日期及年龄。新增真实`_open_position → _apply_state_target → rebalance发单 → _fill_order`集成红→绿；执行41项、权益21项独立通过。

本轮仍用未合并完整分钟的诊断开关；固定参数、AI、费用不变，源码与数据单轮hash未改变。诊断权益3,620,395.00元，总收益2313.5967%，最大回撤-43.63929%，Sharpe1.508878，滑点789,610元，760笔成交，完整周期374个/盈利122个/胜率32.6203%。这些不是最终业绩：314个合约交易日有201个扫描不完整，缺26,835分钟；536个ordinary首锚有367个尚不完整。

独立逐笔复核：760个trade/usage/clock身份、价量、物理时间一致；tick异常0、合成触发bar缺失0、bar范围外成交0、退出原因缺失0。按tape重建每日仓位差0，现金流+持仓市值最大误差`2.79e-9`元；内部权益最大误差`2.33e-10`元。314普通开仓与314已填风险诊断一一对应，实际量差0、价格最大差`1.14e-13`；另2个无成交和8个少于计划量的诊断均有同信号日forced_margin_deleverage解释，未静默忽略。

统计口径：期末cu2611多13手，未完成周期净盯市7,800元；同一原始信号首止腿已亏20,150元，未完成信号合计为-12,350元。报告分别保留cycle与episode，不能混合加总。

下载一次TLS错误后fail-stop，保留207/249段共26,490分钟已核验片段；单连接受控10000根探针的480分钟×7字段与旧完成源完全一致，再恢复最多3路批量。独立数据工具31项测试通过；最终首锚+扫描后缀来源闭环尚待全部补齐。完整pytest目前与基线同样21失败/1可选依赖collection error，无新增失败；最终冻结版再作一次全套验证。

最终冻结源码全套pytest：`2384 passed / 21 failed / 1 collection error`，337.97秒；基线`2322 passed / 21 failed / 1 collection error`。失败名字集合逐项相同，无新增失败；新增权益21+执行41共62项均通过。既有失败主要为目录名历史断言、正式物料路径历史断言、该研究机缺少CTP生产framework/资格证据，以及可选polars依赖缺失。没有放松生产门或删除失败测试来获得通过。另数据工具31项、报告交易日2项通过。

### 16:46中间记录：diagnostic_round4，来源补齐后继续闭环新路径

第一轮补数候选已独立验收并原子合入：470任务、33,282补丁分钟；新增28,505键，重叠4,777键的七行情字段变化为0，旧键零删除。独立复核294个proof、232,974个行情字段值，raw→patch→candidate完全一致。输入SHA从`e78af805778ca7af7976d0b6d79b3248dda756aafd8c26fa98c0e59f7b9560b9`变为`761ad13a8ed77bd5d143f01bd1dce59189f9f3c659d0f0e8f2d62ddaf8bdbe97`，保留原始完整备份。

第四轮在固定策略源码、AI、风险与成本下正常完成：期末权益2,242,915.00，总收益1395.2767%，最大回撤-48.70382%，Sharpe1.366282，总滑点598,510元，817笔成交；402完整周期/115盈利/胜率28.6070%。仍是诊断轮，不验收业绩：实际319个扫描key中3个不完整，缺1,125个唯一分钟（6条原始请求）；537个普通开平首锚中19个不完整。原因是补齐先前路径后，止损、重试和后续账户状态产生新的访问路径，需要继续补数至实际请求闭合。

独立账面重建最大残差`2.33e-9`元；内部权益`1.86e-9`元，定仓权益`1.40e-9`元；期末未平周期净盯市4,800元，含已平腿的未完成信号净盯市-6,000元。执行独立review通过算术与时序：817个trade/usage/clock同值、280合成成交均有bar且符合tick/时段，319普通开仓与实际填充risk逐订单价量一致，8个计划量差额全部由同日forced_margin_deleverage解释；537首锚中19个缺失，数据仍不验收。不能以已有诊断3来源通过替代本轮实际覆盖。

独立review另确认研究入口异常传播P1：冻结vendor会捕获`new_bars`异常后正常return，导致入口try/except不能发现部分中途终止。仅在Stage249研究adapter记录被吞异常并在context退出时重新抛错，保持finally恢复方法；不改冻结策略或vendor。真实vendor故障注入（预热、最后交易日、空消息AssertionError）3项红→绿，正常路径1项继续通过；完整回放前加入此门；独立reviewer已重跑4项通过并审阅异常链与方法恢复，P1关闭。首次从MAIN运行测试因缺少本地.vntrader而被系统拒绝创建家目录缓存，随后切到已配置FIX环境完成真实红绿验证；没有改家目录或生产环境。

### 16:54中间记录：diagnostic_round5，只剩两个普通平仓首分钟

第二次补数独立验收后合入：累计502任务/312proof/34,649补丁分钟，raw→patch→cache的242,543个行情字段值完全一致。此次新增1,141键，旧键零删除；缓存SHA为`cc46709864db5b4d22f13673c02558c10d786d1f9846b9c11a2d3d8435974c22`，前版完整备份保留。

本轮含已审的异常传播门，`vendor_swallowed_bar_exception_guard=true`且捕获异常0，策略、AI、风险与成本不变。期末权益2,262,595.00元，总收益1408.3967%，最大回撤-48.78985%，Sharpe1.367364，总滑点605,450元，816笔成交；402完整周期/114盈利/胜率28.3582%。仍不验收业绩：319扫描key的全部要求分钟直接从cache独立重算均齐全；535个普通首锚有2个不完整，分别jm2305.DCE的2023-03-01交易日首分钟与au2602.SHFE的2025-12-05交易日首分钟（均为前一自然日21:00）。

独立执行review：816成交、281合成成交的时序、交易日、历史tick、bar范围全部通过；319普通开仓与实际risk价量一致，8个计划差额均由同日forced_margin_deleverage解释。日持仓逐笔重建0差、滑点605,450元精确一致；现金流+持仓盯市残差`4.66e-9`元，内部权益`1.86e-9`元。新请求的来源独立核验与最后两个首锚补齐继续进行，正式验收仍待关闭诊断开关并严格重跑。

## 反思

- 运行前是否过拟合：否，修复来自会计恒等式、交易日与可执行价格约束，不扫描参数；同bar约定需预先固定并披露，避免凭收益选择。
- 运行前是否值得继续：是，Stage247已证明定仓账和成交价存在基础错误，必须先恢复评估可信度。
- 运行后是否过拟合：否；逐轮只补实际路径缺口，按会计守恒、交易所时段及合法tick修复，没有利润驱动的参数挑选。现有模型训练与规则形成过程仍不构成全窗口严格样本外证据。
- 运行后是否值得继续：本轮值得且已完成；可信回测基准已恢复。后续真实成本及严格样本外研究仍有价值，但当前DD40未通过，不能从本次正确性验收推出生产资格。
- 同线并行：各实现者只写分工代码/测试；研究只写唯一stage与Stage249输出，不修改LINE、registry或根账。

<!-- STAGE249_FINAL_VERIFIED_REPLAY -->

## 最终严格回放结果

记录时间：2026-10-15T17:06+08:00。窗口2020-01-01至2026-10-14，交易日边界严格，初始本金150,000元。以下替代诊断轮作为本次重跑结果；旧Stage246/247文件保留。

|指标|旧Stage246（含缺陷）|Stage249严格修复重跑|
|---|---:|---:|
|期末权益|9,468,247.25|2,262,595.00|
|总收益|6212.16%|1408.40%|
|最大回撤|-53.30%|-48.79%|
|Sharpe|1.471423|1.367364|
|总滑点（元）|2,513,280.00|605,450.00|
|成交笔数（开平分计）|800|816|
|完整周期胜率|119/395 = 30.13%|114/402 = 28.36%|
|broker10保证金/权益峰值|149.53%|63.12%|
|保证金占用>100%的日数|17|0|

胜率按合约从空仓到再次空仓的完整持仓周期计算；开仓和平仓不是两次胜率样本。同日重试单独形成周期，另提供按原订单父子关系合并的信号统计。期末未平仓不当作输赢。
期末仍有1个未平合约，相关净盯市盈亏4,800.00元已计入账户权益；完整周期净盈亏与净值之间的差额由此解释。
合并重试的未完成信号净盯市为-6,000.00元，包含同一信号已平仓腿；它与单独未平仓周期盯市口径不同。

### 2025年9月以来

期初权益3,699,405.00元，期末2,262,595.00元，期间净盯市盈亏-1,436,810.00元，收益-38.84%，区间内峰值回撤-42.16%。
本期开仓且已平仓的周期：9/63盈利，胜率14.29%；净利润因子0.3197。合并重试后的完整信号：8/44盈利，胜率18.18%。这两个统计不是独立样本，也不能与按日胜率混用。

|月份|月末权益|净盯市盈亏|月收益|当月平仓胜率|
|---|---:|---:|---:|---:|
|2025-09|3,778,605.00|79,200.00|2.14%|1/3，33.33%|
|2025-10|3,768,045.00|-10,560.00|-0.28%|0/2，0.00%|
|2025-11|3,471,645.00|-296,400.00|-7.87%|0/5，0.00%|
|2025-12|3,396,645.00|-75,000.00|-2.16%|1/4，25.00%|
|2026-01|3,290,025.00|-106,620.00|-3.14%|0/7，0.00%|
|2026-02|3,266,925.00|-23,100.00|-0.70%|0/3，0.00%|
|2026-03|3,063,785.00|-203,140.00|-6.22%|2/9，22.22%|
|2026-04|3,092,135.00|28,350.00|0.93%|1/1，100.00%|
|2026-05|3,035,705.00|-56,430.00|-1.82%|0/2，0.00%|
|2026-06|2,789,595.00|-246,110.00|-8.11%|1/6，16.67%|
|2026-07|2,726,115.00|-63,480.00|-2.28%|0/2，0.00%|
|2026-08|2,965,275.00|239,160.00|8.77%|3/9，33.33%|
|2026-09|2,286,615.00|-678,660.00|-22.89%|0/7，0.00%|
|2026-10|2,262,595.00|-24,020.00|-1.05%|0/3，0.00%|

### 年度结果

|年份|年末权益|净盯市盈亏|年收益|年内回撤|成交数|
|---|---:|---:|---:|---:|---:|
|2020|304,965.00|154,965.00|103.31%|-14.00%|145|
|2021|896,870.00|591,905.00|194.09%|-27.16%|130|
|2022|791,275.00|-105,595.00|-11.77%|-35.02%|138|
|2023|1,022,450.00|231,175.00|29.22%|-16.50%|95|
|2024|2,911,135.00|1,888,685.00|184.72%|-12.88%|119|
|2025|3,396,645.00|485,510.00|16.68%|-23.12%|90|
|2026|2,262,595.00|-1,134,050.00|-33.39%|-33.39%|99|

### 修复与验证

1. 日初持仓、当日成交到收盘盈亏和费用分开记账；同时兼容收盘后成交，避免重复盯市和下一日漏记持仓。
2. 普通开平仓统一到交易日第一个实际分钟；前夜、跨午夜、周末及节后开盘按同一日历处理，修复SH漏夜盘。
3. 从真实入场时刻起扫描同一交易日；跳空使用可到达价格，按历史合法tick向不利方向取整。分钟内同时触发止损与进展，固定采用开盘优先、其后不利顺序；重试当根再次触及止损也计入。
4. T+1实际成交价按信号订单关联到正确layer，保留信号日期和持仓年龄；分批成交拆层、加权归因，同日重试独立身份避免改错层。
5. 完整分钟和首分钟缺失、过期状态及执行异常都阻断严格回放；诊断缺数据开关仅用于补数，不得交付为验收业绩。

逐日内部权益最大残差1.86e-09元；候选定仓权益最大残差9.31e-10元；独立成交现金流+日末仓位市值重建最大残差4.66e-09元。
AI沿用原正式历史政策：2020年至2022-01为静态18品种池；从2022-02起采用历史月池，57个月快照完整（另有1个静态边界），Top10非fu加固定fu。未把2020年冒称为每月AI选品，也未重训。
模型、正式策略参数、手续费与滑点字段与冻结基线一致；数据/模型/源码在单轮回放期间hash不变。新增执行完整性开关默认True，诊断轮单独False；新增历史tick规则与审计字段不是alpha参数。正式参数删除0，模型重训0。

### 近期亏损分布与重试观察

以下是完整周期的描述性分组，不是移除某条规则后的因果收益；复利定仓、交易路径和组合占用会相互影响。未对规则做优化或筛选。

|类别|完整周期|盈利数/胜率|净盈亏|
|---|---:|---:|---:|
|非重试|45|6/45 = 13.33%|-898,835.00|
|同日重试|18|3/18 = 16.67%|-542,775.00|

|品种|完整周期|盈利数/胜率|净盈亏|
|---|---:|---:|---:|
|SA.CZCE|4|0/4 = 0.00%|-343,200.00|
|lc.GFEX|5|0/5 = 0.00%|-335,360.00|
|MA.CZCE|4|1/4 = 25.00%|-218,160.00|
|SH.CZCE|6|0/6 = 0.00%|-214,500.00|
|jm.DCE|6|0/6 = 0.00%|-169,020.00|
|sp.SHFE|3|1/3 = 33.33%|-159,480.00|
|FG.CZCE|4|0/4 = 0.00%|-145,440.00|
|ru.SHFE|6|0/6 = 0.00%|-113,200.00|
|rb.SHFE|4|1/4 = 25.00%|-26,790.00|
|cu.SHFE|4|0/4 = 0.00%|-24,500.00|
|AP.CZCE|1|0/1 = 0.00%|-6,700.00|
|fu.SHFE|5|1/5 = 20.00%|360.00|
|si.GFEX|2|1/2 = 50.00%|54,800.00|
|OI.CZCE|5|2/5 = 40.00%|127,100.00|
|au.SHFE|4|2/4 = 50.00%|132,480.00|

|最终退出标签|周期数|净盈亏|
|---|---:|---:|
|stage847_intraday_05r_initial_stop|25|-698,765.00|
|long_prev2day_stop|9|-542,100.00|
|stage847_intraday_retry_failed_05r_stop|13|-302,370.00|
|stage827_intraday_c2_1r_stop|1|-23,460.00|
|rollover_close|1|-13,620.00|
|long_risk_cluster_heat_deleverage|7|-8,865.00|
|short_risk_cluster_heat_deleverage|2|8,250.00|
|short_prev2day_stop|1|25,200.00|
|long_base_stop|4|114,120.00|

标签说明：`initial_stop`为首次入场0.5R止损；`retry_failed`为同日重试后再触0.5R；`prev2day_stop`为前两日保护退出；`base_stop`为基础止损/保护退出；`heat_deleverage`为风险集中度减仓；`rollover_close`为换月退出。保护退出也可能实现盈利；标签是周期最后一腿的原因，不能替代该周期所有分批成交记录。

### 每笔完整周期明细（2025-09以来入场）

下表保留盈利与亏损，价格时间为回测模拟成交的物理时刻；月份和日账按所属交易日。手数为累计开仓量；存在分批成交时，表内首/末价格不能直接代替逐笔盈亏。完整成交、月池、候选、首分钟与止损事件证据在CSV中可按trade_id追溯。

|首成交ID→末成交ID|合约/方向|物理入场→退出|首入场→末退出价|手数|净盈亏|是否重试|退出原因|
|---|---|---|---:|---:|---:|---|---|
|BACKTESTING.690→BACKTESTING.691|au2510.SHFE/多|2025-09-01 21:00:00→2025-09-18 21:00:00|799.54→829.88|5|151,500.00|否|long_prev2day_stop|
|BACKTESTING.692→BACKTESTING.693|cu2511.SHFE/多|2025-09-26 21:00:00→2025-09-26 21:00:00|82270→82260|19|-2,850.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.694→BACKTESTING.695|cu2511.SHFE/多|2025-09-29 09:01:00→2025-09-29 09:01:00|82270→82260|19|-2,850.00|是|stage847_intraday_retry_failed_05r_stop|
|BACKTESTING.696→BACKTESTING.697|FG601.CZCE/多|2025-09-29 21:00:00→2025-10-09 09:00:00|1224→1217|222|-39,960.00|否|long_base_stop|
|BACKTESTING.698→BACKTESTING.699|jm2601.DCE/多|2025-10-27 21:00:00→2025-10-28 09:33:00|1265→1251.5|40|-37,200.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.700→BACKTESTING.701|FG601.CZCE/空|2025-11-04 21:00:00→2025-11-04 21:01:00|1110→1113|305|-30,500.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.702→BACKTESTING.703|FG601.CZCE/空|2025-11-04 21:09:00→2025-11-04 21:09:00|1110→1113|305|-30,500.00|是|stage847_intraday_retry_failed_05r_stop|
|BACKTESTING.704→BACKTESTING.709|sp2601.SHFE/多|2025-11-11 21:00:00→2025-11-18 21:00:00|5490→5410|171|-143,640.00|否|long_prev2day_stop|
|BACKTESTING.705→BACKTESTING.706|lc2601.GFEX/多|2025-11-12 09:00:00→2025-11-12 09:07:00|86760→86240|74|-45,880.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.707→BACKTESTING.708|lc2601.GFEX/多|2025-11-12 09:53:00→2025-11-12 11:07:00|86760→86240|74|-45,880.00|是|stage847_intraday_retry_failed_05r_stop|
|BACKTESTING.710→BACKTESTING.711|au2602.SHFE/多|2025-11-28 21:00:00→2025-11-28 21:17:00|951.92→948.82|9|-28,260.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.712→BACKTESTING.715|au2602.SHFE/多|2025-11-28 22:00:00→2025-12-04 21:00:00|951.92→954.5|9|22,860.00|是|long_risk_cluster_heat_deleverage|
|BACKTESTING.713→BACKTESTING.714|ru2601.SHFE/多|2025-12-02 21:00:00→2025-12-02 21:11:00|15340→15260|32|-28,800.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.716→BACKTESTING.717|lc2605.GFEX/多|2025-12-18 09:00:00→2025-12-19 09:00:00|106800→106100|51|-40,800.00|否|long_base_stop|
|BACKTESTING.718→BACKTESTING.719|rb2605.SHFE/多|2026-01-13 21:00:00→2026-01-13 21:00:00|3158→3154|268|-16,080.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.720→BACKTESTING.721|rb2605.SHFE/多|2026-01-13 21:01:00→2026-01-13 21:01:00|3158→3154|268|-16,080.00|是|stage847_intraday_retry_failed_05r_stop|
|BACKTESTING.722→BACKTESTING.723|fu2603.SHFE/多|2026-01-19 21:00:00→2026-01-19 21:00:00|2536→2530|220|-17,600.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.724→BACKTESTING.725|fu2603.SHFE/多|2026-01-20 09:00:00→2026-01-20 09:03:00|2536→2530|220|-17,600.00|是|stage847_intraday_retry_failed_05r_stop|
|BACKTESTING.726→BACKTESTING.731|MA605.CZCE/多|2026-01-26 21:00:00→2026-01-26 21:13:00|2328→2314|111|-17,760.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.727→BACKTESTING.728|ru2605.SHFE/多|2026-01-26 21:00:00→2026-01-26 21:00:00|16180→16165|43|-10,750.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.729→BACKTESTING.730|ru2605.SHFE/多|2026-01-26 21:01:00→2026-01-26 21:02:00|16180→16165|43|-10,750.00|是|stage847_intraday_retry_failed_05r_stop|
|BACKTESTING.732→BACKTESTING.733|ru2605.SHFE/多|2026-02-12 21:00:00→2026-02-12 21:00:00|16460→16450|43|-8,600.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.734→BACKTESTING.736|ru2605.SHFE/多|2026-02-12 21:01:00→2026-02-13 09:00:00|16465→16415|43|-25,800.00|是|stage847_intraday_retry_failed_05r_stop|
|BACKTESTING.735→BACKTESTING.737|AP605.CZCE/多|2026-02-13 09:00:00→2026-02-24 09:00:00|9738→9730|67|-6,700.00|否|long_risk_cluster_heat_deleverage|
|BACKTESTING.738→BACKTESTING.741|ru2605.SHFE/多|2026-02-24 21:00:00→2026-03-03 21:00:00|17030→16850|15|-28,500.00|否|long_prev2day_stop|
|BACKTESTING.739→BACKTESTING.740|SH605.CZCE/空|2026-03-02 21:00:00→2026-03-03 13:32:00|2080→2102|109|-78,480.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.742→BACKTESTING.746|MA605.CZCE/多|2026-03-04 21:00:00→2026-03-05 21:00:00|2502→2508|252|10,080.00|否|long_base_stop|
|BACKTESTING.743→BACKTESTING.744|OI605.CZCE/多|2026-03-04 21:00:00→2026-03-04 21:01:00|9458→9444|70|-11,200.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.745→BACKTESTING.747|OI605.CZCE/多|2026-03-04 21:31:00→2026-03-05 21:00:00|9458→9511|70|35,700.00|是|long_risk_cluster_heat_deleverage|
|BACKTESTING.748→BACKTESTING.750|SA605.CZCE/多|2026-03-13 21:00:00→2026-03-13 21:00:00|1270→1264|132|-21,120.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.749→BACKTESTING.751|SH605.CZCE/多|2026-03-13 21:00:00→2026-03-13 21:00:00|2576→2563|50|-22,500.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.752→BACKTESTING.755|SH605.CZCE/多|2026-03-13 21:01:00→2026-03-16 09:20:00|2593→2563|50|-48,000.00|是|stage847_intraday_retry_failed_05r_stop|
|BACKTESTING.753→BACKTESTING.754|SA605.CZCE/多|2026-03-13 21:02:00→2026-03-13 21:19:00|1270→1264|132|-21,120.00|是|stage847_intraday_retry_failed_05r_stop|
|BACKTESTING.756→BACKTESTING.757|sp2605.SHFE/空|2026-04-01 21:00:00→2026-04-17 21:00:00|5080→5040|70|25,200.00|否|short_prev2day_stop|
|BACKTESTING.758→BACKTESTING.759|SH607.CZCE/空|2026-04-29 21:00:00→2026-05-06 09:00:00|2028→2034|105|-25,200.00|否|short_risk_cluster_heat_deleverage|
|BACKTESTING.760→BACKTESTING.761|rb2610.SHFE/多|2026-05-07 21:00:00→2026-05-08 21:00:00|3272→3262|234|-28,080.00|否|long_risk_cluster_heat_deleverage|
|BACKTESTING.762→BACKTESTING.763|OI609.CZCE/多|2026-06-01 21:00:00→2026-06-01 21:01:00|9916→9903|63|-9,450.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.764→BACKTESTING.765|OI609.CZCE/多|2026-06-01 21:02:00→2026-06-01 21:02:00|9916→9903|63|-9,450.00|是|stage847_intraday_retry_failed_05r_stop|
|BACKTESTING.766→BACKTESTING.767|jm2609.DCE/多|2026-06-02 21:00:00→2026-06-02 21:01:00|1363→1356.5|46|-23,460.00|否|stage827_intraday_c2_1r_stop|
|BACKTESTING.768→BACKTESTING.769|MA609.CZCE/多|2026-06-10 21:00:00→2026-06-15 21:00:00|2986→2769|88|-192,720.00|否|long_prev2day_stop|
|BACKTESTING.770→BACKTESTING.772|rb2610.SHFE/空|2026-06-22 21:00:00→2026-06-23 21:00:00|3127→3110|223|33,450.00|否|short_risk_cluster_heat_deleverage|
|BACKTESTING.771→BACKTESTING.773|FG609.CZCE/空|2026-06-23 21:00:00→2026-06-23 22:09:00|967→973|278|-44,480.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.774→BACKTESTING.775|jm2609.DCE/空|2026-07-13 21:00:00→2026-07-13 21:29:00|1239→1248.5|46|-31,740.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.776→BACKTESTING.777|jm2609.DCE/空|2026-07-14 10:37:00→2026-07-14 10:58:00|1239→1248.5|46|-31,740.00|是|stage847_intraday_retry_failed_05r_stop|
|BACKTESTING.778→BACKTESTING.779|cu2609.SHFE/多|2026-08-04 21:00:00→2026-08-05 21:00:00|107490→107350|10|-8,000.00|否|long_risk_cluster_heat_deleverage|
|BACKTESTING.780→BACKTESTING.791|OI609.CZCE/多|2026-08-06 21:00:00→2026-08-24 21:00:00|10168→10440|45|121,500.00|否|long_prev2day_stop|
|BACKTESTING.781→BACKTESTING.782|jm2609.DCE/多|2026-08-17 21:00:00→2026-08-17 21:01:00|1367.5→1361|44|-22,440.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.783→BACKTESTING.784|jm2609.DCE/多|2026-08-17 22:02:00→2026-08-18 13:54:00|1367.5→1361|44|-22,440.00|是|stage847_intraday_retry_failed_05r_stop|
|BACKTESTING.785→BACKTESTING.792|fu2609.SHFE/多|2026-08-18 21:00:00→2026-08-25 21:00:00|4081→4523|42|184,800.00|否|long_base_stop|
|BACKTESTING.786→BACKTESTING.787|si2611.GFEX/多|2026-08-19 09:00:00→2026-08-19 09:02:00|8725→8680|137|-37,675.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.788→BACKTESTING.790|si2611.GFEX/多|2026-08-19 09:54:00→2026-08-20 09:00:00|8725→8870|137|92,475.00|是|long_risk_cluster_heat_deleverage|
|BACKTESTING.789→BACKTESTING.793|MA610.CZCE/多|2026-08-19 21:00:00→2026-08-26 21:00:00|2828→2756|24|-17,760.00|否|long_prev2day_stop|
|BACKTESTING.794→BACKTESTING.795|lc2701.GFEX/多|2026-08-31 09:00:00→2026-08-31 10:54:00|160500→158440|30|-64,800.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.796→BACKTESTING.797|lc2701.GFEX/多|2026-08-31 11:08:00→2026-09-03 09:00:00|160500→156000|30|-138,000.00|是|long_prev2day_stop|
|BACKTESTING.798→BACKTESTING.799|fu2611.SHFE/多|2026-09-03 21:00:00→2026-09-04 21:00:00|3866→3772|122|-117,120.00|否|long_risk_cluster_heat_deleverage|
|BACKTESTING.800→BACKTESTING.801|SH611.CZCE/多|2026-09-07 21:00:00→2026-09-07 21:00:00|1942→1937|96|-20,160.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.802→BACKTESTING.803|SH611.CZCE/多|2026-09-08 10:06:00→2026-09-08 10:10:00|1942→1937|96|-20,160.00|是|stage847_intraday_retry_failed_05r_stop|
|BACKTESTING.804→BACKTESTING.805|SA701.CZCE/多|2026-09-08 21:00:00→2026-09-09 09:43:00|1080→1070|198|-47,520.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.806→BACKTESTING.807|SA701.CZCE/多|2026-09-09 14:43:00→2026-09-14 21:00:00|1080→1018|198|-253,440.00|是|long_prev2day_stop|
|BACKTESTING.808→BACKTESTING.809|sp2611.SHFE/多|2026-09-21 21:00:00→2026-09-28 09:00:00|4978→4874|38|-41,040.00|否|long_prev2day_stop|
|BACKTESTING.810→BACKTESTING.813|au2610.SHFE/空|2026-09-28 21:00:00→2026-10-13 21:00:00|899.12→903.62|3|-13,620.00|否|rollover_close|
|BACKTESTING.811→BACKTESTING.812|fu2611.SHFE/多|2026-10-08 21:00:00→2026-10-08 21:04:00|5217→5146|44|-32,120.00|否|stage847_intraday_05r_initial_stop|
|BACKTESTING.814→BACKTESTING.815|cu2611.SHFE/多|2026-10-13 21:00:00→2026-10-13 23:29:00|110950→110700|8|-10,800.00|否|stage847_intraday_05r_initial_stop|

### 解释边界与结论

这次修复不是过拟合：修法来自会计守恒、交易日因果和历史合约规格，未按收益筛选参数或删除亏损月份；也未改AI TopN、阈值、风险比例或重试次数。正式pairwise模型训练包含2020–2022，策略规则事后形成，因此全窗口仍不是严格样本外收益证明。
有继续价值：正确性与来源闭环恢复了可讨论的基准；后续应研究真实成本、严格样本外和风险承受能力。不能因修复结果某项改善就晋升或加仓。此次只完成离线修复和回放，没有修改CURRENT、发布正式物料或部署生产。
保留的模型限制：原正式手续费为0、滑点固定，broker10是固定保证金压力口径；OHLC无法还原tick先后、成交队列、深度、涨跌停可成交性，保守规则是明确模拟约定。
本轮DD40门：未通过；组合部署门：未通过。结果不得自动替代生产资格。

![修复前后与近期月度结果](/Users/mac/.codex/worktrees/formal-correctness-replay/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage249_correctness_replay/strict_comparison.png)

- [完整逐笔周期](/Users/mac/.codex/worktrees/formal-correctness-replay/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage249_correctness_replay/strict_final/statistics_audit/complete_cycles.csv)
- [全部回测成交](/Users/mac/.codex/worktrees/formal-correctness-replay/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage249_correctness_replay/strict_final/trades.csv)
- [期末未平仓周期](/Users/mac/.codex/worktrees/formal-correctness-replay/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage249_correctness_replay/strict_final/statistics_audit/open_positions.csv)
- [期末未完成信号](/Users/mac/.codex/worktrees/formal-correctness-replay/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage249_correctness_replay/strict_final/statistics_audit/open_episodes.csv)
- [年度/月度结果](/Users/mac/.codex/worktrees/formal-correctness-replay/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage249_correctness_replay/strict_final/statistics_audit/year_month_results.csv)
- [会计与统计审计](/Users/mac/.codex/worktrees/formal-correctness-replay/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage249_correctness_replay/strict_final/statistics_audit/summary.json)
- [源码与输入溯源](/Users/mac/.codex/worktrees/formal-correctness-replay/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage249_correctness_replay/strict_final/run_provenance.json)
- [逐日权益](/Users/mac/.codex/worktrees/formal-correctness-replay/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage249_correctness_replay/strict_final/daily.csv)

## 最终独立验收、交付与后续

记录时间：2026-10-15T17:11+08:00。最终严格模式正常退出，缺数诊断开关关闭，bar异常捕获0。1,641个交易日日账、816笔回测成交、319个入场扫描key及535个开平首锚全部核对；实际需要106,515个扫描分钟，与首锚去重合计106,731个分钟键，缺口0、来源错误0。最终输入SHA为`a9566e64c1165a5fd0e62bbae6191b522526646a081e724064876a24bc80a74e`；6,233个数据/模型输入在单轮期间不变。

累计504个补数任务、34,651补丁分钟已逐源验证。原始源→补丁→缓存的242,557个行情值独立比较一致；历轮真实缓存原子替换均保留校验备份，旧基线未改。严格最终交易、时钟、持仓、候选及净账与第五轮诊断除验收标签外逐字段精确相同，证明最后两个首锚补证没有改变经济路径。

独立执行审计：281个合成成交均能定位合法触发bar；价格越界、历史tick错误、错交易日/时段、截止之后成交、缺失退出原因均为0；逐日持仓差0。8条计划量与成交量差异均由既有风险减仓解释，实际填充量、价和按原tick下限计算的风险逐订单一致。独立统计复算了402个完整持仓周期、318个完整原始信号及89条年/月记录，未平cu2611.SHFE多8手的周期净盯市4,800元、含首止腿的未完成信号-6,000元均正确。

验证结果：权益21项、执行41项、研究入口异常门4项共66项直接相关测试通过；数据工具31项及报告交易日2项通过。冻结源码完整pytest为2384通过、21失败、1个collection error，失败集合与旧基线完全相同，没有新增失败。既有失败涉及历史路径断言、该研究机缺少生产CTP/资格证据及可选polars依赖，不能宣称全套测试绿色。补丁`git apply --check`及`git diff --check`通过，7个修复源码/测试文件SHA与交付清单一致。

本次新增严格回测结果1套，保留所有诊断与失败证据；旧回测结果修改0、删除0。正确性结论在已声明的分钟OHLC模拟约定内置信度较高；对未来收益的外推置信度有限，因为手续费仍为0、历史保证金采用原固定口径、分钟bar不包含队列/深度，并且全窗口非严格样本外。

- [最终验收汇总](/Users/mac/.codex/worktrees/formal-correctness-replay/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage249_correctness_replay/final_acceptance.json)
- [最终实际数据来源闭环](/Users/mac/.codex/worktrees/formal-correctness-replay/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage249_correctness_replay/strict_final_source_validation/final_data_summary.json)
- [独立来源绑定审计](/Users/mac/.codex/worktrees/formal-correctness-replay/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage249_correctness_replay/independent_reviews/stage249_independent_strict_binding.json)
- [独立统计审计](/Users/mac/.codex/worktrees/formal-correctness-replay/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage249_correctness_replay/independent_reviews/stage249_independent_strict_final_statistics.json)
- [独立逐笔执行与账本审计](/Users/mac/.codex/worktrees/formal-correctness-replay/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage249_intraday_execution_fix/independent_review_strict_final.json)
- [严格/诊断结果精确等价证明](/Users/mac/.codex/worktrees/formal-correctness-replay/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage249_correctness_replay/strict_vs_diagnostic5_equivalence.json)
- [全部正确性源码与测试补丁](/Users/mac/.codex/worktrees/formal-correctness-replay/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage249_correctness_replay/complete_correctness_fix.patch)
- [代码交付清单](/Users/mac/.codex/worktrees/formal-correctness-replay/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage249_correctness_replay/code_delivery_manifest.json)
- [可复验研究工具清单](/Users/mac/.codex/worktrees/formal-correctness-replay/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage249_correctness_replay/research_tools_manifest.json)
- [全套测试与基线对照](/Users/mac/.codex/worktrees/formal-correctness-replay/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage249_correctness_replay/test_comparison.json)

回放命令、解释器、源码/模型/输入SHA保存在`strict_final/run_provenance.json`与`input_manifest.json`；重现时沿用该argv与环境，输出改成新的研究目录，保留本次原始证据。工作区为`/Users/mac/.codex/worktrees/formal-correctness-replay/fian`，解释器`.py311/bin/python`，`PYTHONPATH=.:/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor:examples/portfolio_backtesting`，设置`PYTHONDONTWRITEBYTECODE=1`和`MPLCONFIGDIR=/private/tmp/stage249_mpl`。

后续研究TODO：在新的独立阶段评估实际手续费/保证金敏感性与严格样本外证据；若提出风险或重试规则新版本，另走A/B隔离流程。本轮没有执行这些优化，也没有提交订单、改写正式发布物料或部署生产。运行后反思：本次不是过拟合，完成它有价值；修复后的近期低胜率与较大回撤仍需正视。
