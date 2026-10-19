# Stage002 六所全历史品种因果日线源与环境预检

- line_id：`futures_trend_full_market_noai_one_lot`。
- 记录时间：2026-10-18 16:23 CST。
- 工作树：`/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian`，独立分支`codex/full-market-noai-one-lot`。只写本线工具、输入和本记录；未修改主工作区、原始行情、正式策略或其他研究线。
- 本阶段是数据接入准备，不是金融回测。重要突破：否，属于研究源基础设施进展。

## 数据与运行环境

使用`/Users/mac/Desktop/fian/.py311/bin/python`。现有`/Users/mac/Documents/Codex/fian-research-20261014/.py311/lib/python3.11/site-packages`可提供matplotlib 3.10.8、pandas 2.3.3、numpy 2.4.4、talib和plotly；matplotlib Agg画布实际draw通过。组合vendor位于`/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor/vnpy_portfoliostrategy`，实际import通过。未安装依赖。matplotlib缓存默认目录不可写会转临时缓存，runner宜将`MPLCONFIGDIR`显式放本线outputs中。

Stage266 clean SQLite按只读URI与`PRAGMA query_only=ON`读取；378,552,320字节，SHA256`a63f92ce7e1d51080ba92f7214fc493f1e6a69aa0079d6ecef7190eea9b58711`，构建前后未变。数据全库2010—2026-10-16共97历史代码；2015年以来93历史代码。原all_futures主力映射虽覆盖六所86品种，但截至2026-10-14，且缺ME、TC、L_F/PP_F/V_F、PD/PT，不能当成93全历史宇宙。

clean库10/12—10/16每日均有六所真实正成交日线，10/16活跃产品为CFFEX 8、CZCE 21、DCE 26、GFEX 5、INE 5、SHFE 20，共85。故本研究源可到10/16，原Stage267截止10/14来自旧映射边界；不表示10/15—16无行情。这里的完整日指固定已验收clean来源的六所最新收盘日，不保证每一上市合约都无缺口。

## 固定数据合同与新增工具

`tools/stage002_market_source.py`提供`load_source() -> (market, mapping, metadata, source_manifest)`，直接只读已生成CSV并校验各SHA。`--build`只生成研究输入，已有非空输出拒绝覆盖，不会启动金融回测。

- 预热开始2014-01-01；交易分析开始2015-01-01；截止2026-10-16。
- 宇宙为2015年以来有已验收clean记录的全部93历史产品代码，不用当代86池或期末存续筛选。ME与MA、TC与ZC以及F月均价家族均保持独立身份。
- 交易日t的主力只从**上一个源日历交易日t-1**的真实bar选择：close_oi降序、volume降序、epoch升序。交割年月不得早于t所在年月；已知maturity不得早于t。t-1没有合格真实观察则t无映射，不延用t-2；不读取t量仓、不按未来存续或表现选合约。上市/到期资料是vendor生命周期快照，尚非历史可发布时间认证。
- t被选合约缺真实bar时保留缺口，不能替换为当天其他更活跃合约，不能用缓存/平价bar授权成交。
- YYYYMM研究symbol避免CZCE十年同名，如`TA201505.CZCE`；F研究symbol如`l_F202602.DCE`，native仍`l2602F.DCE`。metadata显式product_vt_symbol免正则误拆_F。
- 只物化因果政策历史上曾选中epoch的完整可用预热/持仓日线；只有当日映射主力可入场，历史数据是否物化不作为当日入场资格。root需按时钟逐日推送，不得直接读未来行。
- 每个已物化epoch的size都来自精确RQ真实合约metadata；不退化为size=1。tick/fee精确合约优先、产品fallback显式标记。margin优先精确fee合约、再精确instrument、最后产品fallback，来自同源条款快照；无size/tick/margin/fee会失败，不生成虚假默认参数。
- 收费保留`fee_method=by_volume/by_money`及`fee_open/fee_close/fee_close_today`，`volume_multiple/size`、`pricetick`、`margin_ratio`、`slippage`。按手费用不可直接传rate=0后忽略；root须扩展engine和策略成本统一收费，并区分平今。所有开仓手续费均>0，平今0有原源明确值。
- 滑点固定每边1tick，原正式JM至少1价格单位；这是研究成本合同，不是真实TCA。费用、保证金、tick为vendor快照，不认证历史逐日PIT，更不能冒充历史券商保证金。

## 首次构建结果（没有回测）

输出`outputs/inputs/{mapping.csv,contract_metadata.csv,product_universe.csv,market_daily.csv,source_manifest.json}`：

| 项目 | 数量 |
| --- | ---: |
| 六所历史产品 | 93 |
| 源日历交易日 | 3,107 |
| 因果政策曾选epoch | 4,328 |
| 物化真实日线 | 809,279 |
| 日历×产品网格 | 288,951 |
| 有因果映射产品日 | 185,722 |
| 无映射产品日（含上市前/退市/观察缺失） | 103,229 |
| 已有映射但有效日缺真实bar | 3,056 |
| 精确合约tick/fee | 3,705 |
| 明示产品fallback tick/fee | 623 |
| 按手收费epoch | 2,456 |
| 按金额收费epoch | 1,872 |

指纹清单记录4个源与4个输出CSV。完整原市场2014+共有8,511个epoch，其中18个远月新合约缺精确RQ metadata，但它们未被固定因果政策选中；所有实际物化4,328个epoch规格解析成功。未将未物化合约称为已认证规格。

## 验证

先写6项测试并看到因功能缺失全部RED，再实现并GREEN；随后精确instrument保证金优先级新增第7项测试，观察到产品默认覆盖精确margin的RED后修复并GREEN：前一日时序/拒绝陈旧延续、交割月与F实际maturity过滤、稳定同值排序与epoch身份、精确合约优先及按手费、缺规格/手续费拒绝、重复合约日期拒绝。7项定向unittest通过；未声称全仓库测试通过。

`load_source()`真实读回与SHA检查通过，合约日期重复0，metadata epoch/symbol均唯一，size/tick/margin均有限正数。额外用独立SQLite窗口排序查询重算2014—2026各年首日、预热第二日及最后日14个日期×93产品=1,302网格，因果映射差异0。此为另算法只读核验，不是独立agent的金融结果审查；本阶段金融回测0，不触发每次回测后的独立agent审查。核验明细见`stage002_data_preflight.json`。

## C9分钟规则边界

正式`qmt_roll_intraday_execution.entry_session()`默认`stage827_require_complete_minutes=True`，缺任一应有分钟直接`intraday_minute_coverage`失败。当前session函数只声明2020+原19商品时段，多数全市场品种先报`intraday_unsupported_session`，CFFEX不能套商品09:00/10:15休市结构；2015年前段夜盘制度也不能机械套2020+规则。C9 0.5R止损/先到进展阈值/停止后的重入先后依赖真实分钟，日OHLC无法恢复顺序。关闭完整分钟要求后empty直接return None相当于跳过该规则，不能称保留正式执行。全市场完整C9回测仍缺六所历史session合同与真实分钟覆盖；日级研究代理只有在用户明确选择后才能进入实际金融回测。

## 外部资料、判断与反思

已查看[vn.py官方组合回测源码](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py)。判断：复用既有组合引擎但由研究adapter逐真实日期输入；数据缺口、手续费模型和分钟执行是独立合同，不能用日线代替分钟后继续命名完整C9。

新增alpha/信号参数：无；新增数据政策为上日OI/V因果主力与明确费用/规格来源。删除/修改alpha参数：无。新增/修改/删除金融回测结果：无。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A；金融回测/模型拟合/市场下载/CTP连接/订单API均0。

开始与结束过拟合判断：**否（本阶段未引入按收益选择型过拟合）**，只固定数据身份和因果接入合同，没有查看收益后筛品种或阈值；正式策略历史研究选择偏差和vendor快照PIT限制仍存在。继续价值：**是**，93历史代码统一输入与费用规格让研究可审计；下一步由root按用户确认选择日级代理或补完整分钟合同，并在实际回测后做独立agent审查。未改LINE、registry、根memory/back_log。

补充规格校验：初包产品fee fallback曾优先使用产品margin，发现后加第7项RED边界测试并修正为优先精确instrument margin，仅重建metadata小表和manifest，不重建mapping、不回测；589个epoch的margin变化，最终margin来源为{"rq_exact_contract": 3705, "rq_exact_instrument": 623}。最终load_source指纹读回通过。
