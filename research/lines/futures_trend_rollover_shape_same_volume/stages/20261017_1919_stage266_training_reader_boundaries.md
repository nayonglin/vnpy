# Stage266 隔离研究读取器、120日边界与18池可用范围

> **19:26语义勘误（优先于本记录此前的训练资格表述）**：此前将旧CSV七列完整性称为“原108资格”是过度推论，现撤回。真正月度108由策略PNL/信号滚动统计构成，不直接输入open_oi；市场pairwise_v2另为19项。冻结`legacy108_*`及`train_eligible`命名实际只表示严格旧CSV七数值字段完整性，不是月度108训练必要条件。2010–2019该诊断为0不能证明月度108不可训练；18,649只是严格CSV120日窗口数，不是月度样本数。数据与源码/旧报告不改，详见`outputs/stage266_clean_daily/reader_semantics_erratum.md`及`.json`。本次仅只读核对代码并补文档，不查库、不测试、不回测、不训练。

- line_id：`futures_trend_rollover_shape_same_volume`；记录时间：2026-10-17 19:19 CST；最终10键增量补充19:24 CST；工作区`/Users/mac/Desktop/fian`，分支`codex/ai-training-data-expansion`。
- 阶段性质：已授权全市场清洗的有界读取适配；不是策略突破，不触发A/B，不训练、不生成收益标签、不运行财务回测。不修改正式loader、主库、策略参数、LINE或registry。
- 本agent新增：`tools/stage266_training_reader.py`、`tools/test_stage266_training_reader.py`；无删除脚本。新增研究API参数为明确epoch或exchange/product/YYYYMM、必填candidate_date、可选start_date、open_oi_policy、显式expected_trade_dates和window_rows（默认120）；未修改策略参数。

## 调研、现有入口与实现判断

只读核对旧`examples/portfolio_backtesting/build_qmt_roll_ai_position_training_samples.py:94–117`：按`exchange/contract.csv`读取，核心输入为date、OHLC、volume、open_oi、close_oi。旧runtime的`qmt_roll_ai_selection_pairwise_runtime.py:61–71`在缺逐合约数据时会生成日历日并以前一收盘持仓推开盘持仓。新研究读取器不复用这一回退，缺open_oi保留NaN并明确不可用于旧108特征。

参考[Python 3.11 SQLite URI官方文档](https://docs.python.org/3.11/library/sqlite3.html#how-to-work-with-sqlite-uris)采用`mode=ro`、参数化查询和`query_only`，不使用可能忽略WAL的immutable。GitHub CPython测试页尝试未成功读取，不作为实现正确性的证据。判断：来源与日期语义应显式校验，不能因列名相近就自动接入训练。

旧`main_contract_mapping.py:21–24`优先读取现存all-futures映射；`qmt_universe.py:108–130`的18品种仍只是全市场的子集。按每条映射自身交易日期解析真实年月，再强匹配`EXCHANGE.PRODUCT.YYYYMM`；2015与2025的SM501分开，ME/MA与RO/OI不自动改名，DCE的L_F/PP_F/V_F保留独立family。该映射解析不是交易所上市/PIT资格证明。

## 读取合同与边界证据

1. `load_contract_bars`只读`daily_bars`，必填候选日；SQL先做候选/起始日截断，再验证所选范围。精确年月隔离、日期重复、字段schema不符、open_interest不等于close_oi、身份冲突均拒绝，不保留最后一条掩盖重复。
2. 默认`mark_unusable`保留缺值和逐行`reader_row_issues`；只有真实`source_observed`开盘持仓、accepted质量、七项数值完整且来源行资格为真才具有旧108逐行字段资格。真实观测的open_oi=0有效；空值、非观测状态不能补0或shift。显式支持clean库的`legacy108_row_usable`列名，输出同义`legacy108_usable`；源两列同时存在但不一致时拒绝。
3. `strict`只检查调用者明确选择的候选/起始日范围。若旧历史缺字段而最近窗口完整，应先mark加载，再调用`require_legacy108_window`。窗口检查最后120个**预期源交易日**，不以tail(120)观测行凑数；缺日、窗口内非日历观察、候选日不是日历日均不能通过。
4. 逐行字段资格不等于窗口资格。只有require函数成功返回的窗口才标`legacy108_window_qualified=True`；仍未核未来60日标签成熟、PIT可交易性或模型时间切分。原Stage262标签合同不变：120日历史、随后60个源交易日标签，训练时label_end不晚于prediction_date且eval_date更早。
5. `audit-mapping`只对既有18池、真实epoch与源日历做字段/历史覆盖普查，不自动扩全市场池。输入字节指纹前后相等才输出全量审计报告。

边界测试先红后绿。最终命令：

```sh
PYTHONPATH=research/lines/futures_trend_rollover_shape_same_volume/tools .py311/bin/python -m unittest test_stage266_training_reader -q
```

27项测试通过，覆盖真实临时SQLite只读/不创建、候选截断先于严格检查、CZCE跨十年、F家族、缺/零开盘持仓、窗口缺日、重复日历、时区拒绝、非日历行、映射代码冲突，以及纯CSV删键传播。没有金融回测，因此期末权益、收益、回撤、Sharpe、滑点、交易数、胜率均N/A。

冻结源码SHA：reader为`eaa0b51a4e76ab139c4b9b64af005304a19c895b20529f7366b8b88b6ad86c2c`（30,932B），测试为`dcba709dcb5988683c790d6ca7ca32e5c097397313b86f22fcba5543a12d3716`（14,778B）。

## 初版审计、294键隔离与可追溯增量（中间快照）

全量审计初版直接读取初版clean库，只读URI；初版DB SHA为`2fe4a557747370e254e5be48b902763f94c3d66651730688f0201aaa71f75c14`，映射SHA`55e95a468f4ebd989e5db4da282d69a319ebc75ea08a068e1be8ff87ef1ff325`，日历SHA`57dd7f539d1cdbefb528978a6c7bd79b118790f933ce63c37b10747b999f9585`。保留原`czce_reader_mapping_availability_final.json/.csv.gz`及第一轮聚合，不能把初版结果伪称最终DB重新全窗核查。

root随后整键隔离294个OHLC跨源争议键，冻结`price_conflict_quarantine.csv`。此时中间DB SHA为`4191dc61218b8f4cc804f239f46f099769bd34beddff74929e284a51dc1bd598`，本agent只读文件字节重算确认，未再次查询SQLite。`apply_deletions_to_availability`只用旧普查CSV、精确epoch/date删除表和原日历撤销资格：当天删除使clean/字段失效；同epoch最后120个源交易日期中含删除日使窗口失效。没有任何资格提升。

294键导致7个映射当天clean/字段行失效、1,069个原先通过的历史窗口失效。另用独立的“逐候选显式120日期集合与同epoch删除日期集合相交”算法重算，1,069逐行全等，结果见`czce_reader_delta_independent_check.json`。部分被删日当时尚不是该合约主力，仍会进入后来主力合约的120日历史，因此窗口失效数量大于当天行数。

## 最终可用范围（既有18池，非训练样本数）

2010-01-04—2026-10-16共4,074源交易日×18=73,332产品日。真实映射50,270（837 epoch），缺映射23,062，身份解析错误0；映射当日clean行48,506，真实旧108字段完整22,065，严格120日特征窗口18,649。close-only独占26,441，定义为已有clean行但缺旧108字段，与字段完整互斥。

| 期间 | 映射当日clean | close-only独占 | 旧108字段完整 | strict120特征窗口 |
| --- | ---: | ---: | ---: | ---: |
| 2010–2019 | 21,809 | 21,809 | 0 | 0 |
| 2020–2026-10-16 | 26,697 | 4,632 | 22,065 | 18,649 |

| 年份 | clean | 字段完整 | strict120特征窗口 |
| --- | ---: | ---: | ---: |
| 2020 | 3,336 | 1,796 | 1,410 |
| 2021 | 3,624 | 3,624 | 2,494 |
| 2022 | 3,633 | 3,633 | 3,301 |
| 2023 | 4,048 | 4,048 | 3,517 |
| 2024 | 4,345 | 4,345 | 3,833 |
| 2025 | 4,367 | 4,149 | 3,956 |
| 2026至10/16 | 3,344 | 470 | 138 |

字段完整映射日首末为2020-03-23—2026-10-14；strict120首末为2020-04-02—2026-03-18，首末仅是端点，不声称中间连续。这里是“候选所映射单合约自身历史”窗口，不是连续主力序列窗口，故前者可使用该合约尚非主力时的实际历史字段。

映射文件名虽然包含`2026_04`，实际映射到2026-10-14；10/15与10/16全18池缺映射。10/16日历状态为映射0、clean匹配0、字段0、strict120为0，不能由行情已下载到10/16推导当前训练输入可用。2026月末strict120：1月4产品、2月2产品，3月至10月均0；9月末12产品当天字段完整，但120日历史仍不完整。SM原77个零成交日保持缺观察，不制造价格。

## 产物与结论

294键中间快照产物均在`outputs/stage266_clean_daily/`，完整保留；最新304键冻结产物见下：

- `czce_reader_mapping_availability_post_quarantine.json/.csv.gz`：最终73,332产品日覆盖、基线与delta指纹、最终DB指纹；JSON SHA`d074570048660a79dd3392b87a578e19fb4da966eaa269a04ca58b14d36ff7bb`。
- `czce_reader_year_product_counts_post_quarantine.csv`：306年×品种行，含clean、字段完整、close-only与strict120计数及首末日。
- `czce_reader_month_end_status_post_quarantine.csv.gz`：202月×18=3,636行，以每月最后源交易日提取明确状态。
- `czce_reader_year_product_month_summary_post_quarantine.json`：分段/年份/月末总结、定义及基线与增量指纹，SHA`e50aa0fc1f87635265cc1b7cee176eedd04102e8db449e06e354b460737aec1f`。
- `czce_reader_delta_independent_check.json`：对删键窗口传播的另一算法核对。

独立reader复审已于19:21落盘：`outputs/stage266_independent_validation/independent_reader_review.json`，SHA`5815be9694817bb487d91ac27b3e92cd34635c1d32e401fa69b8006c9625e79b`。另一agent绑定上述冻结源码与当时294键快照DB指纹（4191…），独立运行27测试，实际`INE.SC.202212`截至2022-11-29的默认120日窗（2022-06-07起）通过；在内存注入缺预期日（仍>120总行且伪造attrs）、缺开盘OI、拷收盘OI但状态非观测、V0平价、错OHLC、负OI、falseflag、mixedepoch共8类故障均拒绝。实际缺openOI仍为NaN且不可用，DB字节未变，review_findings为空。该review不认证60日标签或模型样本。

## 19:24最终10键增量：累计304，18池可用范围不变

root最后隔离旧主库价格重叠差异表`stage266_legacy_db_price_overlap_differences.csv`中的10个RQ观察，未修价、未新增来源。10键涉及CZCE.SR、DCE.A/J/PG、SHFE.AL/ZN，与既有18池完全无交集（JM不等于J）。本agent以`_post_quarantine`为基线，再使用同一纯CSV删键函数；73,332产品日的clean/字段/strict120三类资格标记逐行全部不变，失效0、提升0。累计价格隔离304键唯一；累计从初版撤销7当天clean/字段、1,069窗口的结果不变。

最终DB SHA为`a63f92ce7e1d51080ba92f7214fc493f1e6a69aa0079d6ecef7190eea9b58711`，最终contract SHA为`3009ee06c0db70f6df3736569392c5d1da2a593ca3b0b95825ad601b139f4149`；两者只读文件字节核实，未查询SQLite。全量初版2fe4…、294键中间4191…、304键最终a63f…三层指纹明确分开，不把增量推导称为最终DB重新逐窗审计。读取器源码与测试未改动。

最新冻结产物（旧报告全部保留，不覆盖最早已名为`*_final.json`的初版）：

- `czce_reader_mapping_availability_304_final.json/.csv.gz`：最新资格与三层谱系；JSON SHA`9dabe9f518f234d70c5ae3f85adeb3ce20d1f9a7c382c5d416ca746315d31d0d`。
- `czce_reader_year_product_counts_final.csv`：306年品种行；内容SHA`dffa1b93361d97289a2d1d79816a313af083d99c896c80a55d4200e8e910fc05`，与294键版相同。
- `czce_reader_month_end_status_final.csv.gz`：3,636月末产品行。
- `czce_reader_year_product_month_summary_final.json`：分段/年/月末聚合；SHA`41fcacde732f805f388cbcb69f0a8aeabc8c77b7108e3580785908171743f309`。
- `czce_reader_last10_delta_check.json`：10键与18池互斥、全部旧资格逐行相同、仅文件指纹读取的核对结果。

最终18池计数仍为clean48,506、字段完整22,065、strict120特征窗口18,649、close-only独占26,441；2010–2019字段/严格窗0及10/15–16映射缺失的限制不变。本次仅用事先固定规则追加争议隔离，不涉及收益选择或过拟合；继续保留审计价值，不扩大源或运行训练。

本阶段结论：读取适配和字段/历史可用范围核查已具备，独立reader复审PASS；“所有新数据都能直接用于旧108训练”不成立。18,649是历史特征窗口候选计数，未来60日标签、成熟、PIT及时间切分尚未认证；没有改接正式入口。全量数据准确性验证由root另行归并。

运行前/后过拟合判断：否。规则在观察任何模型收益前按字段语义、真实身份与时间边界固定，没有通过金融表现选择数据或参数。继续价值判断：是。它把下载覆盖与实际可训练条件分开，并量化早期数据仍缺开盘持仓、近期映射与完整窗口的限制。下一步应先补真实证据或另行设计获授权的缺字段模型合同，不能伪造open_oi或下调历史门槛来制造样本。

本线同线并行，本agent不更新LINE/registry/memory/back_log，由root统一归并。
