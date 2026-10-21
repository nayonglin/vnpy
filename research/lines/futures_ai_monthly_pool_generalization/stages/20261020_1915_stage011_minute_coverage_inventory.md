# Stage011：保留C2的现有分钟入口与185参考事件次日日期覆盖盘点

- line_id：`futures_ai_monthly_pool_generalization`；时间：2026-10-20 19:15 CST。
- 类型：只读本机文件目录、header、既有session/rights manifest和有界symbol＋timestamp列投影。重要突破：否；非回测/训练/未来60日标签。
- 只写本线`outputs/stage011_minute_coverage_inventory/`及本记录，不修改LINE/registry、其他线、正式策略或任何数据源。
- 开始新增按成绩选参型过拟合＝否；不读盈亏，不改C2、信号或宇宙。继续价值＝是；保留C2后必须区分日线输入可算与分钟路径可识别。

## 实际结果与判断

**现有分钟缓存不能支持“2010起全市场完整C2可回放”的声称。**185个`fresh_after_hardblocks=True`仅是月末参考信号，不是185笔实际交易，也不代表未来持仓窗口。按既有公共源日历严格取评分日后的下一日期，185事件涵盖68产品、179真实native合约名，下一源交易日2010-06-01—2026-10-08。

| 有界来源证据 | 命中参考事件数 |
| --- | ---: |
| 同名标准分钟缓存文件存在 | 26 |
| 标准缓存有下一源交易日的自然日期时间行 | 21 |
| Stage861有下一源交易日的自然日期时间行 | 15 |
| 四份旧session manifest命中该合约×交易日 | 13 |
| 其中旧`accepted`且`full_session`收据命中 | 11 |
| 另13个日期命名cache的自然日期行 | 5（已包含于并集） |
| SQLite分钟库目标自然日期行 | 0 |
| 后续Stage061/135 exact-key rights元数据命中 | 0 |
| 上述下一日期证据并集 | **27 / 185，18产品** |
| 在本轮有界来源未见目标日期证据 | **158 / 185** |

27事件最早2018-03-01，最晚2026-04-01。2010—2017共有63参考事件，在本轮来源没有下一日期证据；其余年份逐年计数保留在`event_year_coverage.csv`。无日期证据仅限此次已盘点入口，不宣称磁盘上所有可能文件都不存在。发现文件或自然日期行均不证明完整session、正成交、OHLC合法、逐分钟键无冲突、同epoch与日线聚合一致或C2可识别。

**不应关闭C2来消除缺口，不应把158个缺口当无信号/0收益/负类，也不应以只有缓存的旧品种幸存子集宣称全市场验证。**继续优先由root核实际session要求与边界；本阶段不生成经济标签，不执行任何金融状态机。

## 机器入口

1. [逐事件覆盖表](/Users/mac/Desktop/fian/research/lines/futures_ai_monthly_pool_generalization/outputs/stage011_minute_coverage_inventory/event_next_day_coverage.csv)：185行，精确epoch/native symbol、asof、next源日、各层行数和未授资格状态。所有布尔为CSV字符串，必须显式解析`== 'True'`，禁止`bool('False')`。事件来自`fresh_after_hardblocks == 'True'`，并断言input_ready/fresh_qualification_complete真。
2. [来源文件统计](/Users/mac/Desktop/fian/research/lines/futures_ai_monthly_pool_generalization/outputs/stage011_minute_coverage_inventory/scanned_timestamp_source_files.csv)：Stage861及83个标准cache，逐文件header、stat、最早/最晚时间戳、投影行数。additional日期cache在summary的`additional_dated_cache_sources`。
3. [命中session收据](/Users/mac/Desktop/fian/research/lines/futures_ai_monthly_pool_generalization/outputs/stage011_minute_coverage_inventory/matched_session_manifest_rows.csv)：13个匹配事件对应的原收据行，可追source/overlay路径及其旧资格范围。本轮没有重新认证这些旧收据。
4. [summary](/Users/mac/Desktop/fian/research/lines/futures_ai_monthly_pool_generalization/outputs/stage011_minute_coverage_inventory/summary.json)：数据入口headers、DB overview、晚期rights来源状态、全部计数和限制。

## 现有可读分钟数据入口

### Stage861汇总缓存

`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_stage861_stage860_full_visual_atlas_v1.csv`实际221,112,973B。只投影`vt_symbol,bar_datetime`，读取1,411,116行键/时间；观察范围2018-01-15 09:00—2026-10-14 23:59，**不是这段连续覆盖**。

header：`vt_symbol,tq_symbol,bar_datetime,bar_id,open,high,low,close,volume,open_oi,close_oi,bar_date,minute_source`。该汇总含多个来源和fragment，不能把文件名full或时间戳存在当完整分钟认证；本轮没有读取数值列，零量/填充/非法值都不能在这里被验收。

源码`analyze_qmt_roll_stage861_stage860_full_visual_atlas.py`实际将`bar_date=bar_datetime.dt.normalize()`，所以bar_date是自然日；直接按bar_date分组会拆开跨夜的同一交易日。

### downloaded_futures各缓存

继承Stage016现成standard-symbol候选清单1,641文件、30产品，仅作定位索引。对185事件的179 exact-native身份，实查83个标准cache文件约67.7MB；补扫文件名定位另13个日期命名cache约0.64MB。上述96文件仅读header及symbol/time列，不读OHLC/volume，不hash大载荷。

标准header通常`vt_symbol,tq_symbol,bar_datetime,bar_id,open,high,low,close,volume,open_oi,close_oi`；日期补齐文件另有`required_date,minute_source,bar_date`。带completed/minute/backtest的文件名不授予完成资格。

CZCE native名由Stage006精确epoch对应RQ `order_book_id -> trading_code`解析，不按当前十年给三位年月猜年。处理按casefold比较原symbol，但完整epoch保留，禁止把2010和2020同名串成一条经济合约。

### 已有accepted overlays

以下是可读入口，由其相邻session manifest定位资格；本轮只读header/stat和manifest，不重读这些大overlay的数值：

- `research/lines/futures_trend_triple_screen/outputs/stage002_local_minute_overlay/attempt2/overlay.csv`（201,153,206B）及`session_manifest.csv`；
- `.../stage011_needed_local_completed/overlay.csv`（497,229,678B）及`session_manifest.csv`；
- `.../stage015_daily_recovered_minute_delta/overlay.csv`（48,448,039B）及`session_manifest.csv`；
- `.../stage020_reviewed_provider_overlay/overlay.csv`（8,983,498B）及`session_manifest.csv`。

summary保存实际完整路径和headers；命中的11个旧accepted full_session收据只表示此前特定源/日历/合同下接受过，不自动授予本线C2或2010全市场资格。

晚期小delta：`stage061_accepted_wait_delta/ccc4a13cbc8e4691af41a16916c659f2/`和`stage135_accepted_off_wait_delta/81ffc8f704ce4c5eb701e97e0397b12a/`的`rights.csv/manifest.json`已只读。原manifest仍记`frozen_pending_independent_review`，保留状态，不能凭目录accepted或schemacompatible把exact-key rights提升为完整session。本轮185目标next日期匹配0。

### SQLite分钟库

`.vntrader/database.db`，overview仅17分钟合约、11产品、22,770根，概览2020-03-06—2026-06-23；非连续覆盖。只读取overview，并只在目标symbol×date落入overview区间时允许索引计数；185目标自然日期命中0。没有全表金融扫描，也没有重hash112MB库。

## 时间语义边界

本机`qmt_roll_intraday_execution.py`说明minute是左标签、上海本地时间；`local_timestamp`对带时区输入先`tz_convert('Asia/Shanghai')`再去时区。CSV多为naive字符串，本轮按继承的上海本地标签盘点，未重新认证历史供应商时钟。

该文件的`session_minutes`明确为冻结2020+特定商品交易时刻，按前一源交易日夜盘并处理星期五/星期一，且有COVID暂停例外；它只支持硬编码商品集合。**不能机械用它给68事件产品/2010历史全域授予会话完整资格。**本轮仅分别记录next自然日期行与前一源日18时后行，不把前一天18时以后自动当有效夜盘，不因夜盘跨自然日误称缺分钟。周六凌晨/长假/历史夜盘制度需要下一步root的session合同。

## 执行与可复核性

主盘点exit0，2.734秒；late rights/header补充exit0，1.582秒；额外13小cache timestamp补充exit0，0.571秒。主盘点与两个补充脚本留在输出目录，没有重复跑大载荷聚合。大文件只用stat与旧清单声明hash，不重算大SHA，不冒充新hash认证。

新增/修改/删除策略或模型参数：无。金融回放、拟合、下载、CTP、账户/凭证、订单：全部0。期末权益/总收益/最大回撤/Sharpe/滑点/交易数/胜率：N/A。不是backtest，不声称已有收益或通过金融独立review。

结束新增按成绩选参型过拟合＝否；未按表现/数据便利挑品种或关闭C2。现有分钟缓存来自旧任务的选择性补数，会带强选择偏差，完整覆盖的子集也不能当全市场无偏验证。继续价值＝是；本轮把真实阻塞缩小到可定位的事件和session来源，root可以对明确边界做下一阶段识别，而不用重复全库盘点或下载。
