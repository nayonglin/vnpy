# Stage152：非交割投机账户退出边界的本地元数据可行性

- line_id：`futures_full_market_long_signal_ai`；2026-10-19 00:49 CST；只读可行性，非重要突破。
- 已读registry、LINE顶部及151 root决策。目标沿151固定为**不参与实物交割的投机账户**；本轮不再追两只个案。
- 新fit/cash/SQL/价格读取/下载/大库hash均0，累计仍397fit/206cash。只新增本stage和小型[counts.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage152_local_non_delivery_metadata_feasibility/counts.json)，不改源、旧数据、LINE或registry。

## 判断

**现有资料不足以直接生成六所全历史、当时可知的非交割账户最晚持仓/退出边界。** 合约身份、静态listed/maturity/delisted和部分交割日期可复用，但不能把它们改名为账户退出日期。现有`known_lifecycle_exit_boundary`只是已冻结研究日期政策，源自2026年vendor快照，不含历史账户规则与发布时间证据。

旧Stage038已指出自然人权限缺口，并明确名义交割月首日是自选保守政策，非六所统一法定期限；041已说明静态vendor日期不是历史PIT资格。检索本线stage的非交割/自然人/账户生命周期字段，没有发现此前已完成本次“六所统一非交割账户边界”覆盖盘点。151已决定先做本项有限可行性；本轮新增的是下表实数与字段区分，没有重审旧现金结果。

调研判断：本地元数据足够做**规则适用对象的身份底表**，尚不足以做可执行历史退出日期表。外部历史规则的代表性核验由root并行负责；不能用当前规则补2010历史、单一交易所模板套六所、或缩成少数已找到规则的品种来宣称全市场可行。

## 实际覆盖计数

仅解析JSON/小inventory与生成代码，不读取其指向的价格文件。Stage265 metadata原11355条，沿原`contract_id`归一为10862个唯一真实epoch（排除493条连续/无法归一记录）；与Stage266 clean inventory并集得到本地目录10880epoch/98代码。新增18个是clean中仅有symbol身份、缺精确RQ metadata的2027尾合约。**目录分母不是“有行情、已能交易”分母，也不是已证明囊括交易所历史所有品种的法定全集。**

| 交易所 | 目录代码/epoch | 其中RQ精确metadata epoch | clean代码/epoch | 041精确经济字段及known_lifecycle | 原metadata交割起/止日期非空 |
| --- | ---: | ---: | ---: | ---: | ---: |
| SHFE | 20 / 3477 | 3465 | 20 / 2951 | 2939 | 3462 / 3462 |
| INE | 5 / 397 | 394 | 5 / 396 | 393 | 394 / 394 |
| DCE | 27 / 3286 | 3283 | 26 / 2935 | 2932 | 3283 / 3283 |
| CZCE | 33 / 2889 | 2889 | 33 / 2408 | 2408 | 2621 / 2883 |
| CFFEX | 8 / 692 | 692 | 8 / 692 | 692 | 692 / 692 |
| GFEX | 5 / 139 | 139 | 5 / 138 | 138 | 0 / 139 |
| 合计 | **98 / 10880** | **10862** | **97 / 9520** | **9502** | **10452 / 10853** |

10862条归一metadata的listed/maturity/delisted均有日期；clean对应的9502条精确经济记录也均有这三字段。其余18条保持unresolved（SHFE12/INE3/DCE3），不能复制相邻合约日期解除。041全部9520键都有名义月份首日，它只是合约身份派生值。

六所下列结构化覆盖**每所均0**：个人/非交割账户最晚持仓日、账户退出边界、规则生效起止、规则公布时点、规则来源URL。这里的0指所读metadata与economic_projection没有这些字段或等价规则对象，**不是断言历史上没有公开规则**。投影全局source_bindings与bundle URL是数据来源，不能计成历史账户规则证明。

## 可复用字段与不能替代的字段

| 现有资料 | 可直接复用 | 当前限制 |
| --- | --- | --- |
| Stage265 futures_metadata | 精确exchange/product/epoch、合约年月、listed/maturity/delisted；start/end_delivery_date另留原字段 | 19字段全集没有账户类型、交割资格、最晚持仓、规则版本/发布时间/历史官方来源；交割开始/结束不等于账户退出日 |
| Stage266 contracts生成schema | epoch、exchange、product、YYYYMM、listed/delisted/maturity、metadata_status | 没有个人/非交割账户规则；新增symbol-only身份的三日期均null |
| Stage041 economic_projection | 9520完整clean键、9502精确经济对象、18明确unresolved；来源和静态假设标签 | 不保存start/end_delivery_date；known_lifecycle不是原始账户权限字段 |
| 日历身份 | 现有绑定日历可支持“按某个已明确规则计算第n交易日”的机械实现 | 本轮不重新读取日历；日历本身不给规则、节假日临时调整通知或当年发布时间 |

041的`known_lifecycle_exit_boundary=min(名义月份首日,maturity_date,de_listed_date)`，由041记录定义，042 `lifecycle_index`（代码100—106行）及132 `lifecycle`实现均消费相同字段。9502行`lifecycle_source=exact_epoch_metadata_snapshot`，投影另有`economic_snapshot_not_historical_broker_proof=true`及`historical_broker_specification_qualified=false`。**known是模型使用已给定日期的知晓假设，不是当年公告已取得的证明。**

元数据bundle为`rqbundle_202610.tar.bz2`，下载状态记录2026-10-17获取；041投影issued_at为2026-10-18。不能因每个历史合约有成熟/摘牌日期，就声称该日期及其后续变更在历史u已可知。规则生效区间、公布日和首次可用时钟目前没有。

`product`分类也不足以自动定交割方式：CFFEX metadata分Index537epoch、Government155；其余均Commodity。不能把CFFEX全部当现金结算，也不能把Commodity全部当实物交割。现金结算、实物交割、月均价等须有各自制度对象，不能从高层标签猜测。CZCE另外的2018第三方候选metadata只提供部分合约发行/最后交易日线索，标记来源与完整生命周期未认证，没有非交割账户截止与全历史规则版本，不能补足此缺口。

## 最小追加合同与下一步边界

若要继续，最小对象应是**规则区间表加精确合约调整表**，再按完整目录join，至少保存：

1. 适用exchange/product/epoch、结算与交割方式、账户身份/交割资格适用条件；不能只写“投机”便推断其法律身份。
2. 官方规则文号/URL/页码或条款、公布时点、effective_from/to、例外调整及来源证据身份；公布时点未知须保留unknown。
3. 最晚持仓的计算表达式及交易日历/时区、截止发生在开盘/收盘或夜盘哪一时段；与目标最晚主动退出时点区分。
4. 每epoch的计算结果、known_at、来源版本、覆盖状态/缺项原因；不按收益/将来stale筛选适用对象。没有证据的目录行继续保留unknown。

**当前不能直接复用一个完整全市场日期表，也不宜立即建设庞大全版本工程。** root可在官方代表性资料核验后判断是否存在少量有历史证据的共性规则足以覆盖全部本地目录及其制度变更；若不够，本轮应结束为具体数据缺项，而非强行套统一提前n天、重训或资金回放。把非交割身份明确并不自动证明一个安全且可成交的退出日；成交未知仍独立保留。

## 复现来源与反思

- 元数据：[futures_metadata.json](/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/rqalpha/futures_metadata.json)，原始19字段；[bundle_download_status.json](/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/rqalpha/bundle_download_status.json)只作获取身份。
- 归一函数：[stage265_rqalpha_inventory.py](/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/tools/stage265_rqalpha_inventory.py:42)；本轮以runpy仅加载函数、未调用main或其行情入口。
- clean分母：[csv_inventory.json](/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage266_clean_daily/csv_inventory.json)，仅读epoch身份；生成schema：[stage266_clean_daily.py](/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/tools/stage266_clean_daily.py:113)。未执行该Builder或SQL。
- 经济投影：[economic_projection.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage041_minimum_cash_economics_sources/economic_projection.json)；定义及知晓限制：[Stage041](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261018_1322_stage041_minimum_cash_economics_sources.md)。
- CZCE候选范围：[metadata_summary.json](/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/czce/metadata_summary.json)及metadata_candidates/work_fullmarket_metadata CSV，仅字段与来源说明。

所有Python使用`.py311/bin/python`。本轮参数/回测结果新增、修改、删除均0；新权益、收益、DD、Sharpe、总滑点、交易次数、胜率均N/A。

开始/结束新增按收益救参过拟合：**否**，只计身份和规则证据字段，未看价格/收益或调退出天数。继续本轮有界可行性：**有价值且本地事实现已足够，应结束**；立即把snapshot maturity当历史非交割资格或扩成无限补规则工程：**否**。完整高质量long目标仍active，本次不产生alpha、金融或增加投注资格。
