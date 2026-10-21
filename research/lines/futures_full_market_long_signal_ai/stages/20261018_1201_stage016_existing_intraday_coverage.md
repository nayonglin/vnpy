# Stage016：现成真实合约日内路径的有界盘点

line_id=`futures_full_market_long_signal_ai`；2026-10-18 12:01 CST。先读registry、本线LINE与014。只新增本文及`outputs/stage016_existing_intraday_coverage/`，不改策略、LINE、registry或Git；没有下载、provider、CTP、fit、回测或大库重hash。非重要突破，不签数据新资格。

## 结论

**可以复用部分真实合约日内证据，不能声称六所98代码已有完整分钟。** 当前workspace发现1,641个标准命名的分钟CSV，涉及30产品、CZCE/DCE/GFEX/SHFE四所；另有95个按交易日命名的分钟文件，只记录路径/stat，不自动接入。标准文件含旧19及额外11产品：CY、PK、EB、JD、M、RR、V、Y、AG、NI、ZN。没有在本次限定目录/旧清单中确认CFFEX、INE分钟覆盖；不是全机不存在的证明。不同文件可能重复同一分钟，数量不是独立样本数。

旧57池是历史日线/可交易筛选口径，不是分钟资格范围。其原reader引用的`qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv`在本机原路径缺失，故本阶段57成员对应关系记unknown，没有用当前19、30或98代替。全市场98代码的日线目录保持完整；其中68代码在上述标准文件清单没有候选路径，不能因此删除其日线观察或可识别的OHLC界限。

## 本次实际证据与限制

一次有界metadata盘点完成，实际`5a9481` exit 0，0.411秒；5个CSV只读各首尾最多4KB，数据库2个索引查询合计4行。首次命令`b93caa`在57原清单缺失处exit 1，尚未扫描分钟或查询payload；保留异常后把缺失设为unknown，未补造源文件。产物汇总曾因defaultdict输出98行时插入空键而误报候选98；已直接从保留的1,641行路径清单校正为30，无源重扫或资格变化，`input_inventory.json`明确记录。其后`1ecf56`仅补95个非标准文件路径/stat。脚本末态保留，未为记录整理重复执行。

`.vntrader/database.db`实存112,726,016B。`dbbaroverview`仅17个`1m`合约、11产品、22,770根，时间概览2020-03-06 09:00至2026-06-23 22:59；这不是连续覆盖。旧db中1,001,334根日线与这些分钟不能混计。CF005/2020-03-06和fu2509/2025-07-23各读前2根，实际字段可用；没有全表count或扫描分钟payload。概览及真实样例见`database_metadata_and_probes.json`。

现有七个预检绑定分钟asset均实际存在，大小与153预检声明相同：base 221,112,973B；002 overlay 201,153,206B；011 497,229,678B；015 48,448,039B；020 8,983,498B；061 delta 3,293,608B；135 delta 2,630,128B。逐路径、mtime及继承SHA保存在inventory；**仅继承旧完整资格/指纹，本轮没有重hash内容，大小相同不是字节一致新证明。** 153 prepare成功也不扩大这些源的价格资格。

旧004清单列五个workspace共7,912条候选路径，本次stat均仍在；主要是同源副本、且旧清单限19 metadata，不增加独立日期或资格。当前workspace标准1,641条与旧清单本workspace1,584条范围不同，不能按差57推断57个新合约。246旧下载工具存在，但其原`outputs/stage246_2020_20261014`目录本次未发现，不凭工具存在声称保留全期parquet。

## 已接受范围与年代

实际只读四份现存session manifest及小summary，汇总在`inherited_accepted_session_product_year.csv`。下表是接受记录，不是所有本机分钟的总覆盖；大量后续记录只认证anchor。

| 层 | 接受session键 | 显式full_session键 |
| --- | ---: | ---: |
| 旧002 attempt2 | 3,509 | 3,509 |
| 旧011 | 13,752 | 556 |
| 旧015 | 1,480 | 80 |
| 旧020 | 259 | 13 |

四层显式full键去重4,158，日期2020-01-10至2026-10-12，范围是旧19。这个数不含base及后续逐键delta，不是新setup的完整率。前后两端之间仍有大量缺日；2010—14和2015—19没有从这些接受清单获得完整范围资格。base一个实际端点为AP001/2019-12-05，证明存在该行，不能证明2019全年的分钟覆盖；CSV按合约排序，最后一行日期也不是全文件最大日期。其他四文件端点显示CY209/2022、jd2005/2020、lc2505/2025、ag2212/2022，仅作真实字段和日期样例，全部保留zeroV，不把端点跨度当连续时间。

061继承190 delivery、44,614 accepted keys、44,565 full-right keys；135继承159 delivery、36,391 accepted keys、36,345 full-right keys。其权限是exact-key：**full-right分钟键不是完整session数量**。这两份manifest本身状态仍是pending文本，接受依赖后续独立/root归档与153绑定；本轮没有重新签发。旧021是等待/交付逻辑资格，不能把它单独当全源价格审计。旧020也明确“inherited_ready_not_global_price_qualification”。

## 可复用定位与reader

1. 从全市场观察行取`event_id/product_id/reference_epoch/planned_execution_date=D`，固定同一真实epoch；不能再次按D主力换合约。Stage266日线reader身份为`EXCHANGE.PRODUCT.YYYYMM`，应先经metadata的真实symbol、上市/到期、日期范围映射成vt_symbol。CZCE三位合约名跨十年可重用，不能只用`AP005`串联不同epoch，也不能把`*_F`家族和原产品合并为经济同合约。
2. 用上述session manifest查精确`vt_symbol+trading_date/execution_trade_date`及requirement_kind，沿来源路径定位accepted overlay；对061/135再查`rights.csv`逐键权限。anchor-only只支持那根锚点，不能扩为触发后完整区间。不同来源冲突保持原拒绝，不能随意latest-wins。
3. 可复用`stage002_local_minute_overlay.normal_times/session_grid`的时区处理和限定网格逻辑；`qmt_roll_intraday_execution.session_minutes(vt_symbol,trading_date,calendar)`明确只支持固定19商品、2020+，包含夜盘跨自然日、周五夜盘归周一、疫情夜盘暂停。它对非19直接拒绝，不能直接扩为CFFEX或98代码通用历史calendar。输入calendar必须含前一真实交易日，不能拿自然日期截D的CSV代替完整D。
4. CSV字段为`vt_symbol,tq_symbol,bar_datetime,bar_id,open,high,low,close,volume,open_oi,close_oi`；base另含`bar_date,minute_source`。CSV没有随机访问索引：现有按合约的文件路径索引可先缩小文件；大overlay的旧reader是流式/全读后按symbol与时刻筛选，不应声称天然SQL索引。要实际比较时，只按预先冻结的少量(epoch,D)需求有界读取并复用接受来源，不预建全市场分钟库。
5. SQLite可按唯一索引`(symbol,exchange,interval,datetime)`精确范围查`interval='1m'`。字段`open_price/high_price/low_price/close_price,volume,open_interest`，OI只是收盘OI，缺open_oi；overview仅定位提示，真实区间与完整性仍依选定D判断。不能用17合约DB替代CSV栈。

## 原作者资料与无法识别项

本次实际核[TqSDK官方API文档](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html#tqsdk.TqApi.get_kline_serial)：60秒Kline返回起点时间、OHLC、期间volume及首尾OI。我的判断：这支持本机分钟字段映射，**不支持分钟内高低顺序、完整交易日、实际成交或历史费用资格**。未运行外部代码、实例化SDK或连接provider。

跨不同分钟可分清先后；同一分钟触发突破、止损和目标若多侧触达，仍必须保留路径区间/歧义。缺先前分钟不能证明“第一次触发”，缺后段不能证明“从未止损”，形成中末bar没有后继完成证据也不能当完成。日线全根low/high可能发生在确认前，不能直接当确认后的回撤。零V bar保留为真实源记录，不自动解释成可交易量；分钟总量不证明触发价队列成交。历史tick/费用缺生效日期、限价成交量、涨跌停/跳价可成交性均未由本轮补足。

## 最小下一步与反思

有价值继续的方式是先冻结同一全市场long setup和单项确认规则，再把每个(epoch,D)标为已有完整路径、仅anchor、局部路径或缺失；可识别者给边界，其余保持unknown并报告相同母体的覆盖与参与率。不要按盈利选“有分钟”的事件，不把旧19已验子集当新全市场代表性证据；不为一项入场问题启动全市场下载/费用补库，也不以分钟不全阻止日线确定分支或保守界限研究。017数学归其独立任务，本阶段未审该源码。

新增/修改/删除策略参数与回测结果均0；权益、收益、回撤、Sharpe、滑点、次数、胜率均N/A。开始/结束新增过拟合判断均**否**：只看输入身份与覆盖，不看收益择样或调参；已有缓存围绕旧策略选择的偏差仍在。开始/结束继续价值均**有条件是**：这次已经足够说明可复用部分、未知边界和不必扩工程，不能由盘点直接授权全市场真实执行或高质量AI训练。
