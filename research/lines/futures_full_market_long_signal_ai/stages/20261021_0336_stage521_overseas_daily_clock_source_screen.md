# Stage521：海外同标的日级定价的真实来源与国内夜盘时钟

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-21 03:36 CST；分支：`codex/ai-training-data-expansion`。
- 阶段性质：独立、有界的原始资料/来源/时钟可构造性审查；不是重要突破，不是金融实验，不触发正式策略 A/B 或生产执行。
- 完整六所 98 历史产品 / 95 family 的 long 入场目标不变，独立于正式 C9 月池；没有把全市场缩成 SGX 可覆盖品种。本次仅真实取得两日 SGX 官方原件，未证明全时期覆盖、训练支持或 alpha。
- 开始反思：本轮尚无新收益可供救参，按新成绩调参为**否**；长期同史择题的过拟合风险为**是且高**。继续价值为**有条件的是**：先核真正晚于国内决策的新观测是否存在、何时可以使用；不以外盘名称替旧 OHLC 换指标。

## 裁决与边界

**存在无需分钟工程的真实新观测：SGX 铁矿石按真实合约月份列示的日结算曲线。两份真实官方 HTML 均把铁矿石定价时点标在新加坡 17:30，晚于国内日盘 15:00。** 当前只支持原始来源存在与字段可分离；尚不支持同晚 21:00 前使用所取的 T+1 后版，也不支持立即训练或资金回放。

**同晚首开：NO-GO；完整国内源日滞后的历史重建：可以保留，须由 root 明确接受重建时钟假设后另立协议。** 两者不可混写。缺少逐条历史 first-seen 不等于所有保守重建都不值得研究；但增加一天延迟也不会把最终档案自动升级为首发 PIT。本阶段停在样本/时钟/构造性，下一步仅独立源 schema/time 复审；没有批量历史、模型、标签或资金预算。

## 先读的本线事实与排重

读取 `research/registry.md`、本线 `LINE.md` 顶部及尾部当前状态、Stage365、Stage425 相关段落及 Stage501/503；使用 `rg` 有界导航。Stage365 只核过 CL 官方结算/免费发布时钟，没有实际海外价格实验，不能扩写成“所有外盘信息已失败”。Stage429 的 RB/HC→I 为国内已知同行价格对应，Stage035 的相关同行冲击、旧 FX/宏观包和 Stage518 的续持动作均与本次外部日级原观测不同；旧失败结论不复活。

开始时累计继承 root 已确认的 **511 fit / 278 completed cash＋1 旧 partial**；本轮增量均为 0。未读原 129/Y/action 大表、COMMON、旧预测大表、现金账本、SQL/native cache、私密配置或凭证。

## 一手研究、GitHub 与判断

1. [Jiang/Kellard/Liu 2020 原论文](https://onlinelibrary.wiley.com/doi/10.1002/fut.22147)，另有[作者单位全文](https://repository.essex.ac.uk/27740/1/fut.22147.pdf)：研究沪金沪银引入夜盘后与 COMEX 重叠的市场质量和信息流。论文使用国内 5 分钟及美国逐笔数据组成更低频序列，讨论信息更及时反映、次日日盘开盘波动下降。**判断：支持跨市场信息与交易时钟必须匹配，也警告信息可能先进入跳空；没有证明本线全品种 long、下一开盘后的成本净收益。** 本阶段未复刻其高频分析。
2. [原期刊铁矿石价格发现研究](https://journals.vilniustech.lt/index.php/JBEM/article/view/10604)可读到 DCE/现货长期关系与价格发现摘要。**判断：长期共整合/价格发现不等于可在下一国内开盘之后赚钱，不据此先定 SGX 领先方向。** 原精确标题/作者 GitHub 检索未确认对应作者代码；不宣称找到可复刻包。
3. 实读 [Junxiao-Zhao/SGX-web_crawler README](https://github.com/Junxiao-Zhao/SGX-web_crawler)：其接口示例实际针对 `WEBPXTICK_DT` / `TC` 等文件，README 的 18:00 定时示例是运行设置。**判断：它是独立维护者的接口实践，既非上述论文作者代码，也非 SGX 公布“日结算必在18:00免费发布”的证据；没有 clone、安装、运行，不取分钟/tick ZIP。**

不能从论文名、GitHub 命中、公开当前页面或发布日期字段推出“历年首发可得”“稳定领先”或“已存在 alpha”。本轮真实数据证据是下面的固定 GET 及封存原件。

## 国内与国外的四个时钟

[上期所现行交易时间](https://www.shfe.com.cn/services/calenderandholidays/tradinghours/)及[交易规则](https://edu.shfe.com.cn/TradingAssistant/RulesIntroduction/518.html)明确：实行连续交易者的某交易日从前一个工作日夜盘开始。这里用于说明交易日标签问题，**不以现行上期所表替六所、各历史产品和节假日补齐历史时段资格**。本轮尝试读取 DCE 官方铁矿合约页发生 web timeout，不能把第三方时钟网页冒充已新验 DCE 历史规则。

| 时钟 | 本轮事实 | 对研究的约束 |
| --- | --- | --- |
| 国内源日 `u` 日盘结束 | 本线通常在 `u` 收盘后形成决策；`u` 标签可能已含前一自然日夜盘 | 必须等源 bar 完整，不在该收盘价同时决策并成交 |
| SGX 定价时点 | 两官方原件的铁矿石 as-at 均为当地 17:30；新加坡与北京时间同为 UTC+8 | 它晚于当日日盘15:00，是后来出现的一次外部定价观测；不是17:30首发证明 |
| SGX 报告版本/发布 | 所取文件名明确为含 T+1 量仓版本；当前 HTTP `Last-Modified` 在次日早晨 | 不能将整个后版塞进源日当晚21:00前。mtime 不是历史首发，也不能凭“只取DSP”证明后版DSP从未改过 |
| 国内下一真实首次开盘 `D` | 有夜盘者常为 `u` 自然日21:00；无夜盘者另有日盘首开 | `D.open` 不是统一次日09:00；已错过21:00后再买09:00需单独日盘开盘价，原完整日线 O/H/L/C 无法恢复 |

美国一侧不可用日期偷换时点：[CME 结算 FAQ](https://www.cmegroup.com/articles/faqs/access-to-cme-group-settlement-data-faq.html)区分结算计算/授权实时通路与网站延到美国中部午夜。[CL 结算规则](https://cmegroupclientsite.atlassian.net/wiki/display/EPICSANDBOX/NYMEX%2BCrude%2BOil?src=contextnavpagetreemode)给出美东14:28—14:30区间，对应北京时间翌日02:28—02:30或03:28—03:30，均已晚于常见前一自然日21:00的 `D` 首开。免费中部午夜还更晚。**美盘日线 date 不代表国内该 date 首开前可知；“04:00拿到美盘日价、09:00买入”不能使用已包含21:00夜盘的 `D.open`。**

## 真实 GET、原件与固定代表值

原计划先写 `probe_plan.json`：两个固定日期/URL、每次15秒、单体上限2MiB、不跟随重定向、不重试，只保存少量元数据，明确 `raw_body_saved=false`。首两次都200，内存 body 算 SHA 后丢弃。root 后要求原件供独审，随后**明确授权额外两次同 URL GET**；补充计划先写，第二轮原字节保存。**累计4次GET，不是2次；0自动重试/0重定向。** 第二轮两份 SHA 均与首轮被丢弃 body 完全一致；没有追版本或换日期。

| 固定原件 | 两轮状态/长度 | SHA256 | 当前 HTTP Last-Modified 换算为 UTC+8 |
| --- | --- | --- | --- |
| 2020-01-02 | 200/200，641,541B | `a3c8644c4a75d28e9a1dd6254d51fa842bb3f7ac484d03a4bf0dd99d18a9ef13` | 2020-01-03 09:00:20 |
| 2023-01-13 | 200/200，573,298B | `19db8bb3a5fa7decfd1c09eafa29fea09e970d255d7f780e759254bacff7f5c8` | 2023-01-14 07:30:10 |

真实端点为以下两项；2020 URL 起初由已 web 打开的2023官方路径推导，**其存在性后来由真实200和原件确认**，不是把推测算实证。

- [2020-01-02 SGX 官方原件端点](https://api2.sgx.com/sites/default/files/reports/settlement-prices/2020/01/wcm@sgx_en@iron_dsp@02-Jan-2020@Iron_Ore_DSP_%28T%2B1_Volume_and_Open_Interest%29.html)
- [2023-01-13 SGX 官方原件端点](https://api2.sgx.com/sites/default/files/reports/settlement-prices/2023/01/wcm@sgx_en@iron_dsp@13-Jan-2023@Iron_Ore_DSP_%28T%2B1_Volume_and_Open_Interest%29.html)

原字段不是字面 `SETTLE`，而是 section `SGX TSI IRON ORE 62% DERIVATIVES` / 组 `SWAPS / FUTURES PRICES` 下的 `Contract Month`、`DSP (US$)`、`Prev DSP (US$)`，另有变动/高低/不同产品量仓列。不能把列展平后碰巧取到 T+1 成交量，或把重复组合表行当独立新合约。

| root 在补充 GET 前固定的规范别名 | 原表字面月份 | DSP | Prev DSP | US$ Change |
| --- | --- | --- | --- | --- |
| `FE202002` | `Feb-20` | 91.81 | 90.50 | 1.31 |
| `FE202302` | `Feb-23` | 125.50 | 122.14 | 3.36 |

两个 FE 别名都**不是原 HTML 的字面 symbol**；它们表示 root 预定的月份映射，不认证 vendor/exchange 的正式 symbol 绑定。没有换月份取更合适数值。价格列独立于后面的 `T+1 Volume` / `Open Interest`，因此可做明确白名单投影；**分列不证明当年首版与后版价格相同**。[SGX Clearing Rule 7.11.2](https://rulebook.sgx.com/rulebook/sgx-dc-clearing-rules)允许清算所修订结算价，[Practice Note 7.11.1.2](https://rulebook.sgx.com/rulebook/practice-notes-0)也允许收盘价差、模型、询价等方法。结算可存在而无当日成交，不是可在其价格买入的成交证明。

当前核实的历史范围只是**2020-01-02和2023-01-13两个点**，没有证实2010—2026连续覆盖、免费全部历史、最早档案日期或2019年前训练支持。没有核实完整 history ZIP/索引；不把上述日期路径模板写成已验全历史API。SGX现行研究/产品网页仅返回浏览器兼容提示，不能据页面标题声称下载链闭合。

## 已有原件内的两个 spread：只登记定义，不转金融

root 追加要求仅在已有 raw 内查 section，无新增网络：两份原件都有 TSI62% 相对 MB58% 的价差区和 Hot Metal Spread 区。**2020 Hot Metal 的钢价项写 HRC，2023 写 Shanghai Rebar**，其余打印系数均为铁矿1.6、焦煤0.77。这是重要的经济定义/版本差异，不能仅因同名就无缝拼接。

仅在 `section_presence_metadata.json` 保存存在性与短上下文，不挑新固定月份、不计算品位溢价/利润特征或收益。MB58 行缺量不等于结算缺失，但结算也不等于成交。521不替 root 决定 grade-premium 实验；它没有新金融预算。

## 最保守可保留的日级研究时钟

首先区分“新观测”和“纯新时段冲击”。SGX 17:30 的价格是国内15:00之后的一次外部观测，不能由相同国内 OHLC 唯一恢复；但 `DSP_t / DSP_(t-1)` 跨越了国内已知交易时段，**不能称它是纯15:00→17:30收益**。若要严格隔离该2.5小时外盘收益，需要一个15:00外盘对照观测；本轮没有它，不能用日价伪造。这里可保留的是**已滞后的外部定价状态/曲线**，不宣称严格新冲击或外生因果。

当前没有已证实、适用于整段历史的精确免费首发 SLA，因此不能写一个“事实已认证的最早可用时刻”。可以提出以下**保守历史重建约定**供 root 接受，而不要求一开始就有每日报价首发字节：

1. 报告的国外 as-at 日期为 `r`；其铁矿17:30观测不得进入 `r` 国内日盘收盘决策，也不得回填 `r` 当晚21:00。先经过 `r` 之后第一个完整国内源日 `u`，在 `u` 收盘并完成接纳后才允许进入特征。
2. 只允许在 `u` 之后的下一真实源交易日 `D` 的首次开盘执行。对正常有夜盘产品，这通常是 `u` 自然日21:00，原 daily `D.open` 可继续承担首次开盘语义；对无夜盘/节假日按本线已接受的真实日历与开盘定义，不统一改成09:00。
3. 原件只白名单产品/月份/DSP/PrevDSP/as-at与来源身份；排除 T/T+1 量仓及其它后版状态，不把 archive mtime 变成当年 first-seen。逐日缺失、定义版本不明、source date/月份映射不符必须保留未知/fallback，不能为了形成样本删母体或补0。
4. 若将来采到明确晚于这一约定时刻才形成/更正的版本，应推迟接纳或保留未知；不能因为多数 mtime 看起来较早就推定所有版本早到。当前最终档案与当年版本可能不同的风险仍保留，并须在任何实证协议中事前接受、与PIT分开。

两锚例子：2020-01-02 17:30观测，其所取文件mtime是次日09:00；保守研究应至少在完整2020-01-03源日收盘后才考虑，之后使用下一真实首开，不能回贴1月2日夜盘。2023-01-13为周五，所取文件mtime到周六早晨；可按后续第一个完整国内源日的收盘接纳，再等之后首开，不能据交易日标签把它放回周五21:00。**这些只示范重建约定；未在本轮读取/认证两日的全历史交易日历，具体D标签须由原日历映射。**

这会让新信息在下一次实际开仓之前已旧一些，甚至已反映进国内 `u` 全日价格，经济先验比同晚更弱；不能把剩余信息增量当已证实。但时钟弱先验不等于必须建设分钟工程，也不等于它是旧国内OHLC的恒等函数。该命题可以被有界研究证伪，当前尚无成绩。

## 其它已见来源的取舍

- [LME 官方发布表](https://www.lme.com/Market-Data/Reports-and-data/Publication-schedule)把实时定价与官网次日延迟明确区分。定价区间中某些时刻落在国内15:00后/21:00前不等于免费网页同时到达；本阶段不追加LME历史工程。
- [LBMA 官方说明](https://www.lbma.org.uk/index.php)涉及历史/实时基准授权；官方公告已说明历史表转成员门户。没有以镜像或过时免费接口绕过此缺口。
- [EIA WTI官方日历史页](https://www.eia.gov/dnav/pet/hist/RWTCd.htm)实际可见1986年以来日值及下载入口，但[定义页](https://www.eia.gov/dnav/pet/TblDefs/pet_pri_spt_tbldef2.asp)中的日现货价格不提供逐条发布时间链。这是另一个较晚到达的外部价格来源，不是能在中国夜盘首开前拿到的美国当日最终价，本轮没有下载或转新假说。它的历史存在不填补SGX连续覆盖。

只保留 SGX 这个已真实取得的日级对象供复审，停止继续无穷搜索端点、公式或其它外盘替代品。

## 新增文件、计数与输出

本轮只新增本 stage 和 `outputs/stage521_overseas_daily_clock_screen/`；不改LINE/registry/根日志、其它研究线、旧代码/参数、正式配置或生产。没有新增/修改/删除策略参数。

- 原首取计划/元数据：`probe_plan.json`、`probe_results.json`。
- 原件封存补充授权计划/完整HTTP/新旧SHA对比：`supplemental_retention_plan.json`、`supplemental_retention_results.json`。
- 原件：`sgx_iron_dsp_2020-01-02_Tplus1.raw.html`、`sgx_iron_dsp_2023-01-13_Tplus1.raw.html`。
- 固定月份原列/表头：`fixed_representative_schema.json`；spread定义存在性：`section_presence_metadata.json`。
- 新实际官方样本GET：**4 attempts /4 HTTP200 /0 retry /0 redirects**，其中首2 body丢弃、后2 body保存，各配对SHA一致；没有把正文浏览/检索混算为四份独立数据。
- 新 SQL、fit、cash、旧金融重放、分钟/tick下载、CTP/订单/凭证/安装：**均0**。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率：**全部N/A**，没有用0代替未测。
- 未完成：独立源schema/time审查、连续历史覆盖、来源归档研究时钟接受、训练支持、信号/净收益/资金账户与置信区间；不提前写“全面复审通过”。

## 结束反思与合入建议

- 过拟合：新增按本包收益救参为**否**；长期同史自适应择题风险仍为**是且高**。真实新观测不等于独立盲样本，不因换海外源清零既有选择偏差，也不开始扫月份、滞后、品位、窗口或模型。
- 继续价值：独立源schema/time审查为**是**，因为两原件与定义差异已提供可核对象；同晚回填、分钟扩建和立即金融为**否**。完整源日滞后的外部定价状态有**条件研究价值**，须先核覆盖/接受重建假设，不能据两个日期造整市场外盘工程。
- 全市场目标仍active、未完成；没有高质量入场、窄损加注、真实执行或晋级资格。unsupported品种保留在98/95完整母体，只能预声明缺失/fallback，不能把一个铁矿样本说成全市场支持。
- 建议 root 由另一agent独立核原件、固定schema、as-at/版本时钟和HRC/Rebar定义差异后裁决；本阶段不自行更新LINE、registry、根memory/back_log，不自动授权后继实际。
