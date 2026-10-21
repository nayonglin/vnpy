# Stage527：2019年1月SGX单月源与清洗独立复审

- line_id：`futures_full_market_long_signal_ai`；记录时间2026-10-21 03:49 CST；工作区 `/Users/mac/Desktop/fian`。
- 模式：独立来源/清洗复审，非重要突破、非正式A/B、非金融实验。先读526冻结协议并核SHA，再等作者code_ready和actual终态；没有读取半成品或重复轮询。
- 协议SHA：`b40e8447b3c63f35915b2061df320cfbd9004bfe66146208703cb6b4140e8d9c`；实际作者工具SHA：`848e5accbd4da0e59efbb1294856f23be6dd1f035f1c078e71c3243d1c8ff8e2`，均独核与started/manifest绑定一致。
- 本次只写自身527输出目录及本stage；不改526/525源、旧工具、LINE、registry、根账、正式/生产或其他研究线。

## 裁决及实测范围

**接受526这一次2019年1月来源获取与14列清洗的有限算术/映射范围。** 独立审查真实exit0，223项检查无失败；全1056个月份行、14784个字段与作者CSV一致，2112个有限数值的最大绝对差为0。没有发现本范围内的实质字段差异或阻止有限源接受的bug。

**这不是连续全历史、交易日历、可成交价、严格PIT或alpha认证。** 源接受可以支持随后冻结的历史重建研究，不应要求先有收益证据才允许研究；同时本复审不自动授权模型、现金或加注。完整目标仍是全市场高质量做多及成本后增收益、降DD，来源工程不等于目标已完成。

| 实际对象 | 作者记录与独立复核 |
|---|---|
| 请求母域 | 2019-01-01—01-31全部23个weekday；明确**不是SGX exchange calendar** |
| 实际新增GET | 22；21个HTTP200、Jan1一个HTTP404，零retry/redirect；Jan9引用525缓存，新增GET为0 |
| 独立raw范围 | 23件、合计14,150,020B，每件恰1次；含118B的Jan1错误体与Jan9缓存 |
| 日期状态 | 22个`ok`、1个`http_error`；Jan1错误体封存且不产生价格行 |
| 原文monthly | 每个ok日期48行，共1056行；月份范围2019-01—2022-12，无重复month |
| 数值状态 | 1056行均`dsp=finite;prev=finite`；2112个数值逐个一致 |
| 时间 | 所有1056行明确20:00:00+08:00；不是17:30 |
| 独审新增金融/网络 | **0 GET / 0 fit / 0 cash / 0 SQL**；0作者parser执行、0旧2020/2023/2026 raw读取 |

223是检查条数，14784是字段比较数，均不是独立金融样本数。22个源日和每日报价月份高度共享，并不产生1056次独立经济验证。

## 实际方法、边界与读取计数

1. 先静读526新工具，核缓存排除、固定22任务、no-redirect/no-retry、错误体保留、列白名单、源日期隔离、按日追加及Prev不回写的路径。没有import或执行作者下载器/normalizer，没有重跑其4项fixture或旧suite。
2. 在自身目录另写std库HTMLParser，从HTML表格独立识别精确TSI62章节、表头、所有month原串与DSP/Prev两格；Decimal先验数值检查再转float，用独立逻辑与CSV逐格核对。没有复制作者parser，也没有借用作者已清洗值作为源真值。
3. 自身4组合成边界覆盖合法0/缺失、NaN/Inf、明确8pm与month/非quarter、重复month与精确章节。为保留HTML解析后的原串与区分invalid/nonfinite，在真实源读取之前小幅完善后又跑同4组，共8次fixture求值；全部0真实raw/0金融，不能记为8条新市场经验。
4. 收到actual完成通知后唯一运行独审。每件raw读入一次、独算SHA/bytes，再独立解析；未通过HTTP的错误体只绑定身份与状态，不把错误HTML解析成价格。所有日期事实及白名单投影在比较作者CSV前已落入527目录，随后不再打开raw。
5. 作者CSV仅读一次；后续结案检查只读自身小receipt/date facts。23个raw读取路径和次数在receipt逐个保存，排除了旧2020/23/26原件。Jan9缓存是本次明确授权的新月组成部分，不能与禁止重读的旧锚点混同。

独审内部计时约0.717秒；工具返回进程exit0。作者此前实际session39554/32.578303秒/exit0由其终态通知与526started/finished支持，本复审没有重新获取一次来源来“验证获取”。离线SHA一致接受的是当前封存体与manifest绑定，不伪装第二次独立远端TLS/发布验证。

## 14列、月身份、缺失与排除字段

逐行核对协议14列：请求日、原header日、as-at原句、明确时刻重建、raw SHA、章节原文、month原文、YYYY-MM、DSP原串、Prev DSP原串、两个finite数值、value_status、Last-Modified元数据。原串是HTML cell文本解码后的原串，不以数值格式化重建；有限数值不改变原串，源“-”和无数状态不覆盖为0。

- 只接受精确`SGX TSI IRON ORE 62% DERIVATIVES`下monthly行；所有month均来自原件，不借FE别名推断月份，不混quarter/calendar aggregate、其他品质或HotMetal。本次不新建FE交易代码映射。
- 所有日期/所有月份的原DSP和原Prev分别保存；静态路径不读取前一日清洗值，也无覆盖历史DSP操作，逐格比较进一步核实该字段未被前日值替代。**Prev的具体上一有效报告日身份仍未由本次证明**，不凭名称补日历/修订链或计算交易回报。
- 14列严格白名单，没有T+1 Volume、任何OI、HotMetal、其他品质、quarter/calendar、returns、labels或score列。Raw本身包含其他信息，独审没有将其输出为研究特征；同页17:30/20:00也不使T+1量仓提前可知。
- 本月实际1056行的DSP/Prev均finite，因此“缺失不造0、NaN/Inf不产生有限数值”的边界证据来自必要合成例及静态逻辑，**不冒称本月存在实际缺失价样本**。实际Jan1 404确实被隔离而非变为零价格行。
- `ok`仅表示原件/字段在本协议中可解析，不代表该48个月份当天均有可交易成交、同单位、经济身份或流动性。未检查真实instrument代码、每手乘数、物理单位、国内I映射、汇率税费或执行价格。

## 日期状态、2019时刻与发布边界

独立按日核原header日期、as-at、目标章节、month数及重复状态，22个源日均与对应请求日匹配。Jan1只是冻结weekday请求中HTTP404的一个状态；本复审没有把它进一步认证为交易所休市，也没有据weekday列表补造exchange calendar。若未来出现日期错配，可解析原行必须继续与该日期的隔离状态一起保留，而不是静默接纳或改日期。

2019这些原件的页首明确为`As at ... 8pm SG Time`，独立重建均为源报告日20:00+08:00；不能从2020/2023锚点把Iron Ore 17:30倒套进2019。SG Time在该范围为UTC+8；本任务没有联网查询新制度，也没有重读旧锚点，相关制度背景仅继承522/524已核PRIMARY资料，实际结论以本月原件文字为据。

本月成功原件所留Last-Modified转SG当地时刻，最早2019-01-03 07:00:15，最晚2019-02-01 10:00:48。各日期原头与转换在独立date facts中保留。**20:00是as-at，不是published_at；Last-Modified也是当前所取版本元数据，不是first-seen或首发。** 2026抓取HTTP Date更不能当历史发布日。

允许root随后采用有依据、收益前固定的保守消费延迟做历史重建；不要求不可得的完美vintage才允许产生历史收益证据。延迟必须参照真实source日期、实际打印20:00和明确版本限制，不能为赶当晚21:00而把这些T+1页写成17:30公开。本次尚未冻结消费延迟，也没有把Last-Modified自动写成首发；严格PIT、连续全历史版次和同晚可得仍未认证。

## 输出、未知与下一步

- [独审receipt](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage527_sgx_201901_independent_review/review_receipt.json)：31,159B，SHA `0e384cfb99a0663ba5d0c6fe78d2dedd7ebf6313c36a78e457e4250faf28d579`；含scope、223checks、零差异、输入绑定和逐raw读取次数。
- [独立日期事实](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage527_sgx_201901_independent_review/independent_date_facts.json)及[独立14列投影](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage527_sgx_201901_independent_review/independent_projection.csv)是仅用于本次复核的派生证据；不是新训练集/收益标签或额外金融产物。
- 未知保留：23weekday不是exchange calendar；一个月不能证明2010+连续支持；first-publication、未来修订、源原价格经济真实性、Prev日期链、跨年度schema/定义、国内可执行/PIT/alpha/收益DD均未由本任务认证。
- **核完即止。** root可以接受该单月清洗，再基于实际缺口决定后继来源/历史重建协议；没有自动授权新GET、全vintage工程、全历史扩展、母表投影、fit/cash或加注。后续若实际回测，仍需新独立agent全面审查数据、逻辑、置信度和bug。

## 指标与开始/结束反思

- 新增/修改/删除金融结果、交易参数均0；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均**N/A**。累计本线仍511fit/278完成cash及1旧partial，未重验旧计数。
- 开始/结束新增按收益调参过拟合：**否**；实际没有使用收益或赢家选月份/延迟。长期同史择题风险：**是**，来源工程不能消除。
- 开始继续价值：**是，限单月有限来源与清洗复审**；结束：本次有价值且已完成。可支持后继有界来源判断，重复下载/重复源核验或把成功清洗当金融进步没有当前价值。
- 原完整全市场高质量long、更高净收益/更低DD和窄损加注目标仍未完成；`goal_complete=false`、`production_qualified=false`、`increased_betting_qualified=false`。
