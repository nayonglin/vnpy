# Stage002：六所全市场清洗输入的实际只读盘点

- line_id：`futures_full_market_long_signal_ai`；2026-10-18 11:11 CST；工作区 `/Users/mac/Desktop/fian`，沿用 `codex/ai-training-data-expansion`。
- 先读 registry、新 LINE 和 Stage001。本次是作者盘点，不自签独立 review；没有策略突破或新 A/B。
- 目标为全市场全品种高质量做多，既不按 C9 long_case，也不按正式 AI 月池或旧“57 可用”预筛。新目标不等待旧 B_OFF；旧 19 品种多空表不是本线母体。
- 只写本文和 `outputs/stage002_full_market_input_inventory/`；不改旧线、原数据、reader、LINE、registry 或 Git，不派 agent。

## 实际结论

**可以立即建立保留未知/缺行状态的全市场产品日观察 outer；不能把它直接称为完整可交易 long 机会表或训练集。** 本机规范库实际涵盖六所 97 个有行情历史代码、9,520 个有成交 epoch、1,552,456 条真实合约日线，2010-01-04 至 2026-10-16；聚合成 212,852 个有观察的产品日。这些统计单位都不是独立交易经验或成熟训练样本。

另有一个应保留的范围差异：实际 contracts 表共 **10,880 epoch / 98 产品代码**，不是仅 97 个代码。额外 `DCE.S` 有 25 个可解析元数据身份，但本次 2010 起范围没有 clean 行。原 futures_metadata 中 S 共 29 条（包含不能直接当完整年月真实合约的条目），最晚 de_listed_date 为 2003-01-15，部分 listed_date 为 `0000-00-00`。这支持将其列为范围前历史/未知上市元信息，不能当作当前缺数据，也不能凭没有2010+行删掉历史代码。当前盘点并不证明覆盖国内期货所有史前年份或全部交易所曾上市身份。

| 所 | 有行情代码 | 有行情 epoch | 合约日线 | 有观察产品日 | 首日 | 末日 |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| CFFEX | 8 | 692 | 67,345 | 19,434 | 2010-04-16 | 2026-10-16 |
| CZCE | 33 | 2,408 | 390,570 | 61,631 | 2010-01-04 | 2026-10-16 |
| DCE | 26 | 2,935 | 471,418 | 65,766 | 2010-01-04 | 2026-10-16 |
| GFEX | 5 | 138 | 24,682 | 2,566 | 2022-12-22 | 2026-10-16 |
| INE | 5 | 396 | 62,785 | 7,540 | 2018-03-26 | 2026-10-16 |
| SHFE | 20 | 2,951 | 535,656 | 55,915 | 2010-01-04 | 2026-10-16 |

`coverage_by_product_year.csv` 实际输出 1,666 行＝98代码×17年，包含零观察格，不静默删品种/年份。每格保留合约日线数、去重产品日数、当年 epoch 数、首末日、缺开盘 OI、七字段完整、元信息状态与源日历天数。年份端点/正行数不证明中间无缺日；日历分母不是该品种官方应上市天数；跨年份 epoch 数不能相加充当全历史合约数。

2010 年 24 个有行情代码/5,739 产品日，2020 年 68/15,271，2025 年 86/19,045，2026 截止日 85/15,964。全量逐产品逐年事实在 CSV，不按结果筛选。

## 实际命令、数据库与资格继承

唯一数据盘点命令：`.py311/bin/python research/lines/futures_full_market_long_signal_ai/outputs/stage002_full_market_input_inventory/inventory.py`。

- 实际 11:09:02.095863—11:09:17.954897 CST，15.858875 秒；先返回 session 28291/chunk 53a7a4，终态 chunk 49e768，**exit 0**。actual_invocations=1；后续只读盘点输出和小元信息解释，没有再跑 aggregate 或旧套件。
- 规范库：`../futures_trend_rollover_shape_same_volume/outputs/stage266_clean_daily/clean_daily.sqlite`，实际 378,552,320 B，mtime 2026-10-17 19:22:50.627662+08:00；读前后 size/mtime 相同，无 WAL/SHM。
- 使用 SQLite `mode=ro` + `PRAGMA query_only=ON`，按固定2010-01-01..2026-10-16聚合实际 daily_bars、contracts、sources；没有只抄 catalog。全量行数和有行情 epoch 数与既有独审核对一致。
- 大库 SHA **继承** `a63f92ce7e1d51080ba92f7214fc493f1e6a69aa0079d6ecef7190eea9b58711`，本次未重新计算全 DB hash。stat 与 aggregate 一致不等同本次完整逐字节重验，明确保留这一边界。
- 小合同当前 SHA 实验核对：contract `3009ee06c0db70f6df3736569392c5d1da2a593ca3b0b95825ad601b139f4149`；最终独审 `c8067bfad40db0f1817f5e81be9b7c0e4b024a09356d097ed0f5a7aa0b904576`；reader `eaa0b51a4e76ab139c4b9b64af005304a19c895b20529f7366b8b88b6ad86c2c`。其余小 receipt 与7.1MB元信息绑定在 input_inventory.json。
- 原 Stage266 独审已验证 4,831 源文件与初版 1,552,466 选中行；最后仅删除 10 个价格争议键，保留行值不变、sources/contracts 不变。最终 PASS_BOUNDED_SOURCE_CONTRACT_ACCURACY_AND_READER、P0/P1/P2=0/0/0 是继承结论，不是本作者新签。
- 原 RQ futures.h5 实际存在 377,901,136 B，mtime 2026-10-17 18:20:44.456073+08:00，记录原 SHA `d288f6e4c7468981e95fbb0c1c9e2e1e66bfb99f5ba607843728aec535c8bfee`；本次只 stat，不读内容、不重 hash、不解包1GB原包。没有重新验完全部旧源或9520 CSV。

## Reader 的实际入口与返回

`../futures_trend_rollover_shape_same_volume/tools/stage266_training_reader.py:115` 的 `load_contract_bars(db_path, *, candidate_date, contract_epoch_id=None, exchange=None, product=None, contract_yyyymm=None, start_date=None, open_oi_policy='mark_unusable', table='daily_bars')` 可直接使用。必须明确真实 epoch 或 exchange/product/YYYYMM 和候选日；SQL 先截断起止日期，再验证身份/字段。返回 pandas DataFrame，保留原26列，增加 date、reader_row_issues、legacy108_usable；实际 columns/dtypes/attrs 见 reader_probes.json。

原列含 epoch、交易所/产品、完整年月、原 source_symbol、trade_date、OHLC、volume、close_oi/open_oi、open_interest、source_id/source_locator、单位因子、native量仓、字段状态及旧资格标志。数据访问是只读，不 import native/策略/模型。无缺值填充。

实际7次有界调用共41行：六所分别 CFFEX.IC.202610、CZCE.AP.202610、DCE.A.202611、GFEX.LC.202610、INE.BC.202611、SHFE.AD.202611，2026-10-09..16各6行；另 CZCE.CF.201001 的2010-01-04..08共5行。抽取按日期与字典序、未按收益选择，全部成功。CFFEX/INE/SHFE上述尾部及早期CF仍真实保留缺开盘OI（共23 probe行），不因mark_unusable将其丢掉。probe只证明有界读取可用，不是完整PIT或窗口/训练资格。

## 身份、日历、单位、零量和尾部

- 身份固定 `EXCHANGE.PRODUCT.YYYYMM`，CZCE 十年同名不得用短码合并；L_F/PP_F/V_F 月均价家族独立，不按普通L/PP/V自动复用执行规则。所选报价是真实合约，非主连/复权价格。
- contracts 的10,862行来自 RQ vendor metadata，18行仅current/official symbol；其中36条clean日线为symbol-only。有1,360个元数据epoch没有当前scope clean行，原因可能范围前/零量/隔离/未上市/缺源，未统一归因。listed/delisted/maturity是候选来源信息，不是逐条官方上市公告或当年可发布字节。
- 固定日历实际4074日，2010-01-04..2026-10-16，SHA `57dd7f539d1cdbefb528978a6c7bd79b118790f933ce63c37b10747b999f9585`。这是vendor交易日历，不自动给每所/每品种完整会话、夜盘、涨跌停和上市资格。
- volume、close_oi统一单边手。规则只绑定固定来源：pre2020商品RQ明确0.5因子，CFFEX及已单边TQ不得再除二；官方未知单位不强收，DCE年度包仅交叉参考。open_interest 实际为 close_oi 别名（本次 aggregate mismatch=0）。
- 784,746行旧七字段完整，767,710行缺真实open_oi；close_oi缺失0、非accepted0、clean非正量0。旧 train_eligible/legacy108 标志只代表旧CSV字段完整性，不是任何新AI必要或充分条件，close-only不应全删。
- V0/无成交保留在原源排除账，不补成有效K线。继承 source_stats 的 no_trade=757,938、unknown_unit=127,156、invalid_ohlc=807、before_candidate_listing=698；这些是**来源观察**，不能与唯一合约日/产品日相加。原2294数量+304价格争议整键隔离边界不变，本次未重新逐键认证或逐条修数。
- 最新已完成来源日是2026-10-16；六所均有记录，不等于全部品种当天可交易。85代码当天有clean行；12个有历史行情代码未见当日clean：ER/JR/LR/ME/PM/RI/RO/TC/WH/WS/WT/ZC，另DCE.S无scope行情。JR/PM/RI/WH/ZC仍有元数据声明在期合约但无尾部clean；保持“无clean、原因未推断”，不能把无成交、停牌、结束与缺数据合并成零收益。旧主力mapping仅到10/14的限制不是本线观察outer的必要闸门，选约合同须另定。

## 已有参数与缺的执行资格

本次实际读取11,173B的 `tqsdk_all_futures_contract_metadata.csv`，86行快照，86个代码有正tick/multiplier，正margin_ratio为0。相对98代码缺tick/multiplier快照的是 ER/ME/RO/TC/WS/WT、DCE L_F/PP_F/S/V_F、GFEX PD/PT；这些代码仍留观察母体，不先剔除。此处只描述该快照，不宣称其他文件没有参数。

RQ futures_metadata 确有 contract_multiplier/round_lot/trading_hours/margin_rate/listed/maturity/de_listed。root 另一次实际只读观察（chunk e0b47a/7033d3）确认 future_info.json 共7574行＝7480 order_book_id+94 underlying_symbol，含tick/commission/margin但无effective_date；LC示例tick20与已知历史变更、IF平今差异均提示不能将单快照全期套用。本作者不重复打开future_info，不将root观察冒称本次独立参数验收。

缺的是可用于目标时点的执行合同/资格，而非断言磁盘无字段：历史有效tick/multiplier、开平/平今费用、交易所和broker保证金/限额、真实分钟或其他明确路径及会话/价格限制、事前滞后选约和换月规则、特征可得时刻与成熟目标。新 long-only 执行不能直接继承全部旧C9政策，更不能以日线单根OHLC判定窄止损先后或未成交概率。缺时间序列不阻塞只观察的product-day表，阻塞把它宣称为可训练执行结果。

## 最小下一步与调研判断

可以仅用规范库、98代码目录和固定日历建立描述性产品×日outer：保留无观察/元信息未知/范围前等状态；有观察时保存全部真实epoch候选及当日OHLCV/close-OI，不做C9/月池/未来收益预筛。只允许u收盘已完成信息影响其后执行；不使用未来最大成交量选历史合约，不把全周期最后状态当当天资格。若要一品种一合约，先另冻结滞后选约、tie-break和换月合同，不能凭当前主力映射回填未来。

下一次最小安全读取应选结构覆盖的少量产品日（六所、缺openOI、同名跨epoch、F、无clean及尾部），按明确u/end和epoch调用已验reader，先核观察outer的日期与状态语义；不先造收益标签，不铺完整训练或反事实系统。由root安排本次产物的独立review，本作者不自行接受。

调研沿Stage001已实际查看的交易所、AKShare官方GitHub、Mlfin.py标签/并发区间与既有Stage266来源文档，不新增联网或下载。判断：这些材料支持明确来源、因果时钟和标签区间；不证明窄止损可执行、模型有优势或应该加杠杆。已有源级资格足以复用输入，不必换线就重hash/重建清洗数据。

## 变更、结果和反思

新增本文及本目录 inventory.py、coverage_by_product_year.csv、product_state_inventory.csv、reader_probes.json、input_inventory.json、actual_terminal.json、handoff_manifest.json。策略/训练/回测参数新增修改删除均0；新增金融、native、prepare、网络、下载、训练、订单均0。权益、收益、最大回撤、Sharpe、总滑点、交易次数、胜率N/A；没有新alpha或production资格。

开始/结束新增过拟合判断：**否**，只按用户范围和固定来源读取，不按收益选品种/行或调参；仍需警惕将样本数量扩大、未知状态填0、窄R和重注联合优化冒称预测能力。开始/结束继续价值：**是**，已从实际reader确认可启动全市场观察层，并保留98/97差异与执行字段边界。目标active，未形成模型或合格训练数据；异常保留，本次盘点结束，不追加无限清洗循环。LINE/registry由root维护。
