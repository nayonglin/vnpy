# Stage066 下一类新增信息提案：先检验真实结算基准，暂缓会员分布

- line_id：`futures_full_market_long_signal_ai`。
- 记录时间：2026-10-18 16:00 CST；16:03补入parent要求的有限H5/同源行小读；工作区 `/Users/mac/Desktop/fian`，任务沿现有 `codex/ai-training-data-expansion`，未新建分支或 worktree。
- 阶段性质：独立只读资料研究与实验建议；唯一新增文件为本 stage。不改 LINE、registry、其他线、代码、配置或资产索引。
- 是否重要突破：否。没有新增训练、现金、SQL、下载、资产登记或收益成绩，不能把资料与计划当净收益/回撤进步。
- 是否触发正式 A/B：否；没有正式晋级候选，不碰正式池、CTP、邮件或生产。
- 已读：AGENTS、registry、本线近期 LINE、056/057、common26 定义、041 最低经济来源，以及旧线会员排名 079—081 与相关有限源说明。没有读取本轮 061/062 EIA 的模型/收益结果，避免据该成绩选下一题；不重复 EIA 实验。

## 结论与优先顺序

**首选：真实结算价相对收盘价的信息增量。** 本机已有逐真实合约的 `settle/settlement` 观测，但本线 common26 与 Stage266 clean DB 没有该列。它含日内成交价格分布的信息，不能由相同 OHLCV 唯一重建；同时必须明确：这是新增的市场价格观测，**不是独立基本面、逐笔订单流或真实参与者身份**。机制证据只够支持一次小规模、可否决的实验，不足以预认 alpha。

第二条是会员持仓分布/集中度，机制上更接近“风险集中于谁”，但**当前没有可读本地源支撑实施**。旧线记录中的 TopK 缓存与 Stage080 输出目录在本机均不存在；也没有在针对性文件名清单中找到替代的逐会员历史缓存。此处只否决“现成可直接用”的假设，不声称证明整个磁盘绝无其他数据。不要重跑旧 Top20 净仓/净变化/turnover 阈值，也不要为该方向先展开无期限采集工程。

旧期限 q/HGB、同行 rho、DAY 去顶、20bar/RFF、ER/FI/周线/简单 carry/OI/ranking 失败结论均保留。本首选不是换这些包的窗口、seed、树容量或收益目标。

## 一手资料与 GitHub 调研，以及我的判断

1. [上期所 2020 年结算细则原文](https://www.shfe.com.cn/upload/20200930/1601455533699.pdf)与[上期所 BR 业务规则手册](https://www.shfe.com.cn/content/2023_BR/manual.pdf)区分收盘与成交量加权结算；[上期能源结算细则](https://www.shfe.com.cn/regulation/ineregulation/businessmethods/settlement/202606/t20260622_832188.html)也区分有成交和无成交时的结算办法，并允许异常情况下调整。**判断：结算价不是另一种 close，也不是所有日期都能当成交 VWAP；无成交、异常调整与规则变更必须保留状态。** 当前规则不能机械回套全部历史。
2. [中金所2020结算细则原文](https://www.cffex.com.cn/u/cms/www/202003/27161736r3ck.pdf)描述最后一小时成交加权基准及无成交回退；[2025版](https://www.cffex.com.cn/u/cms/www/202501/071747590uho.pdf)将定义写为相应时段，并非给所有产品保证全天。具体[IF合约交易细则](https://www.cffex.com.cn/u/cms/www/202003/27165505w3j5.pdf)的日结算为末小时加权、交割结算为标的指数末2小时算术均值；[T合约2020交易细则](https://www.e-cffex.com.cn/u/cms/www/202007/08152235b2ys.pdf)日结算也是末小时加权，但精度为小数点后三位，[国债交割细则2020版](https://www.e-cffex.com.cn/u/cms/www/202007/08151817ah9p.pdf)最后交易日交割基准为期货当日全部成交加权。**判断：CFFEX股指与国债的日结算虽在所核版本都用末小时，其精度、最终交割对象/算法仍不同；SHFE/INE所核商品规则为全日加权。** 首选只能称“收盘相对当时适用结算基准的位置”，不能统称全天VWAP或买压。上述历史PDF不代表已核完2026全部规则或每个新品种。
3. Hendershott、Menkveld 的 [Price Pressures 作者原文](https://faculty.haas.berkeley.edu/hender/price_pressures.pdf)将信息成分与流动性中介承受的暂时价格压力区分。样本为 NYSE 股票与特定中介数据，**不是中国期货 close-minus-settlement 的获利证明**。它提供双向反证：收盘偏离均价可能是持续重新定价，也可能只是随后回归的压力；不能预设“高于均价一定做多”。
4. [RQAlpha 维护者 data_source.py](https://github.com/ricequant/rqalpha/blob/master/rqalpha/data/base_data_source/data_source.py)将 `get_settle_price` 映射到日 bar 的 `settlement`；[维护方类型文档](https://www.ricequant.com/doc/rqalpha-plus/api/types)也将 `settlement/prev_settlement` 与 OHLC 分开。**判断：可复用字段接口，不复制策略或假定 vendor 当时版本已被保留。** 本机包身份仍以已有 receipt 为准，在线 master 不冒充本机数据资格。
5. 会员方向额外核对[上期所排名原表](https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/?query_params=pm)、[公布门槛](https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/dailyranking/decl/202401/t20240117_331641.html)和 [AKShare 维护者 cot.py](https://github.com/akfamily/akshare/blob/main/akshare/futures/cot.py)。原表披露的是会员代客业务，多、空榜分别排序；达到合约持仓门槛才公布。`cot.py` 的约16:30/建议之后获取是实现经验，不能当官方历史发布保证。**判断：经纪商汇总不是最终投资者，缺榜不为0，同排名行不可相减。**
6. Liu 等的 [Traders’ Concentration, Hedging Pressure, and Risk Premium in Futures Markets 原始论文](https://www.management-review.org/uploads/pdf/paper/mr_2023_42-3_jul_02eng.pdf)讨论美国 CFTC 交易者集中度相对套保压力的增量，短期证据弱于较长持有期。**判断：可支持区别“分布”与“总量”的问题，不能把美国最终交易者集中度迁移成中国经纪商看多信号。**

资料调研没有找到可直接证明本首选在中国全市场、下一可交易开盘、扣压力成本后稳定获利的一手证据。因此它只是合理且便宜的新增观测证伪题，不应称高置信度优质信号。

## 本地已实际读取的载体、schema 与覆盖边界

以下路径均以 `/Users/mac/Desktop/fian/` 为根；只读目录/少量头部/已有清单，没有 SQL、H5 全键扫描或 whole-DB hash。

| 可读路径 | 本次小读确认 | 覆盖及限制 |
|---|---|---|
| `research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/other_exchanges/normalized/SHFE_futures_2020.csv.gz` | header 与前2行，含 `exchange,product,source_symbol,contract_yyyymm,contract_epoch_id,vt_symbol,date,open,high,low,close,volume,open_interest,settle,pre_settle,turnover,source_id,unit_regime,oi_timing,source_member,source_sheet,source_row,row_quality`。例 `ag2001,2020-01-02,close=4293,settle=4310,turnover=413.79`。 | 对应 inventory 给2020年37014条 accepted OHLC 行；这不是37014条结算资格已核。端点 inventory：2010-01-04—2010-12-31有20087条，2026-01-05—09-30有38437条；10月另有官方 daily 尾文件。没有在本阶段逐年计算字段非空率。 |
| 同目录 `INE_futures_2020.csv.gz` | 同一 schema；`bc2103,2020-11-19,close=47090,settle=47170,turnover=178205.89`。 | inventory 2018首段1405条、2026截至09-30为9117条；这些仍是OHLC行数。source identity/单位与 settlement 有效性须分开。 |
| 同目录 `CFFEX_futures_options_202610.csv.gz` | 同一 schema；前行 `IC2610,2026-10-08,close=7242.6,settle=7214.6`。 | 当月 inventory accepted futures 196条，2026-10-08—16；2010-04首月44条。文件名含 options，但规范层接受的真实期货与 raw 中排除的期权不可混用；本提案不转做期权研究。 |
| `research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/dce/official_fullmarket_daily.csv` | header 与前2行含 `contract_epoch_id,vt_symbol,product,contract_yyyymm,date,open,high,low,close,settlement,volume,close_open_interest,source_year,source_key,raw_member,raw_row,volume_unit,oi_unit,oi_timing`。 | 已有 normalization 记录333766个唯一有效OHLC行、2245合约、2006-01-04—2022-12-30；源量仓仍为 native unscaled。只用价格列不自动解决结算规则/PIT。没有2023后该官方层的完整证明，不能假称全期。 |
| `research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/rqalpha/futures.h5` | parent要求后，用`.py311/bin/python`+h5py只读3个确定键的header与各末2行，没有写代码文件或遍历全键。AG2001/IF2612/T2612均有 `datetime,open,close,high,low,prev_close,limit_up,limit_down,volume,total_turnover,settlement,prev_settlement,open_interest`，时间为i8，其余f8；shape分别244/113/137行。 | 已有全市场 inventory 称10547个真实有dataset合约、2010起97个有行情品种、bundle截止2026-09-30；**不能由此推为全10547键结算字段存在或数值可用**。旧`.../czce/rqalpha_SM77_raw_rows.csv`的无成交flat填充也有结算，更说明不能把有结算值当可交易K线。 |
| `research/lines/futures_trend_rollover_shape_same_volume/outputs/stage266_clean_daily/` 与本线 `outputs/stage002_full_market_input_inventory/input_inventory.json` | 已有 `daily_bars` schema 为 epoch/date/OHLC/volume/close_oi/open_oi/source locator等，无 settlement。 | 已接受1552456合约日、9520 epochs、97有观察/98目录代码只是本线原母体数据事实，不自动认证新列。该母体不重建、不缩池。 |

16:03小读的H5六行又按同symbol、完整交割年月与同交易日从现有官方规范CSV各取一行。AG源为`SHFE_futures_2020.csv.gz`，IF/T源为`CFFEX_futures_options_202609.csv.gz`；OHLC、volume、OI、settlement、prev_settlement均逐值一致。仅列新增字段核对：

| epoch | date | close（两源一致） | settlement（两源一致） | prev_settlement（两源一致） |
|---|---|---:|---:|---:|
| SHFE.AG.202001 | 2020-01-14 | 4219 | 4222 | 4293 |
| SHFE.AG.202001 | 2020-01-15 | 4219 | 4219 | 4222 |
| CFFEX.IF.202612 | 2026-09-29 | 4277.2 | 4285 | 4274 |
| CFFEX.IF.202612 | 2026-09-30 | 4300.8 | 4299.4 | 4285 |
| CFFEX.T.202612 | 2026-09-29 | 109.655 | 109.625 | 109.545 |
| CFFEX.T.202612 | 2026-09-30 | 109.415 | 109.410 | 109.625 |

所读H5 `total_turnover`是官方规范`turnover`的10000倍，符合该官方层万元说明；没有将其加入信号，也不把这6例推广为全历史单位证明。AG2020-01-15的`C=S`是有正成交量170的合法零偏离，不是缺失。反之零价格、非finite、无成交填充或未证定义的结算都不能生成真实零x。此处没有读取clean DB：**尚未证明本线每条accepted close都等于将来拟用结算源的close**；它仍是下一步最先需要回答的来源可比性问题。

旧会员缓存本机缺项已逐路径确认：

- `examples/portfolio_backtesting/backtest_outputs/external_domestic_member_rank_cache/` 不存在。
- `research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage080_member_rank_2022_backfill_feasibility/` 不存在。
- 旧 stage 文本称原缓存68857行/2023-01-03—2026-04-17/15产品，后加19792非DCE行；这些是历史机器记录，**本阶段不把它们计入本机可用覆盖**。源码显示 `get_rank_sum_daily` 型字段是 TopK 聚合，不等于逐会员名单。
- 对研究目录与预期 backtest cache 的针对性文件名盘点未见会员缓存替代；没有解压handoff、没有新取排名，也不将 OHLC/OI 或文件名中的“position”伪装为参与者分布。

## 首选的第一性原理与唯一输入

相同 O/H/L/C/V 可由完全不同的成交量价格分布实现：成交大量发生于低位、仅少量成交把 close 推高，与大量成交已接受高位，可以有相同端点/极值/总量但不同加权均价。S11 的 body/range/close-location 与 common26 的期限摘要不能唯一恢复这件事。真实结算基准因此是**新观测**；对 OHLC 做 HLC3、再换归一化或加深网络则不是。

可证伪问题：在已经看见自身价格反应、成本和退出距离后，**上一完整 source 日收盘相对其正式结算基准的位置，是否还能改善下一 source 日起完整跨日 long-only 经济结果与实际研究现金**？偏离可反映收盘前持续信息，也可反映暂时流动性压力；训练决定符号，不手定“高于结算买入”。

仅提一个标量：`x(u) = [C(v)-S(v)]/N(v)`，其中 `v` 为 `u` 前一个完整 source 日。C/S必须来自同一源记录、同一真实epoch、同一交易日的未复权原价，且该源OHLC必须与accepted参考价建立事前冻结的可比关系；N用该同epoch已冻结ATR口径。不能从源A取close、源B取settlement后默认可减。参考epoch在v缺少同约记录时 x=missing，不拼主力、不借邻约、不将今天参考约的昨天价格误投影成另一epoch。普通/F严格按各自经济身份读取，共同family风险规则不变。

前置字段状态至少区分`finite_positive_with_trading / nonfinite_or_zero / no_trade_fallback / final_delivery_or_definition_unknown / source_conflict`；只有正成交、规则身份可解释且价格可比的记录生成x，x=0本身仍可合法。真正成交加权基准原则上应在该时段成交价极值内；若超出同日OHLC，不裁剪、不当强买卖压，保留最终交割/调整/来源冲突核查。涨跌停或V>0本身不证明下一开盘能成交；不修改原现金missing与执行假设。

不增加 turnover、成交额逆推VWAP、settlement收益率、cross-exchange交互、变化率、滚动均价、分位、极值门槛、额外序列或参与者列。采用 settlement 而不同时试成交额，是为避免再引入历史乘数/成交额单位与统计边数映射。跨所结算窗异质性是失败可能，不是看完结果再加分组模型的理由。

## 当时可知、修订与最小冻结缺项

结算在日盘闭市后形成，不能拿S(u)回填u收盘决策。本提案固定上一日v值到u收盘才使用，D仍为u之后的下一source同epoch open；夜盘合成交易日不能只按日期字符串推可得时刻。**一天滞后是保守实验定义，不等于历史公布时分已被证明。**

冻结前只补以下最小事实，不开泛资格工程：

1. **先回答覆盖与同源可比性。** 对本线实际参考epoch映射做一次有界字段投影，按原399252母体输出新字段family×年可用计数，以及新源OHLC与accepted OHLC相等/可解释舍入/冲突/无重叠计数；没有这些不能签训练accepted。三个H5 header与六行对照已小读，其余source族仍需最少代表记录与原raw行绑定，明确未复权价格、日结算/交割结算之别。无需扫raw全库hash，不因覆盖较好改池。
2. 保存每个采用的结算规则族在其适用时期的最少规则证据，注明全天/末小时/特殊F及异常回退。无法确认的规则族保持 `settlement_definition_unknown`；不猜成同一种VWAP，也不机械沿用现行规则。
3. 给出新列的 `data_date/available_at/source_locator/reconstruction_status`。有官方公布时刻者用实际时刻；只有“当日结算后发布”而无历史时分者，用有来源支持的当日保守最晚边界并到u收盘使用。若连此前已发布都无从支持，则该行 missing。当前年包或vendor快照是历史重建，不能冒称当年采集字节；异常调整与今日修订可能污染早期值，未解决差异保留unknown，不以现代值前向填完。

允许在明确“历史重建+固定滞后”的研究假设下做一次经济证伪；不把所有历史逐秒PIT/券商资格当共同前置，也不因此签严格首发/PIT事实。若最小事实仍不可支持，就停止本字段研究；source audit成功也不算净收益进步。官方CSV与RQ若同epoch/date冲突，不据收益挑source，先按冻结来源顺序并标冲突未知。

## 若由root采用，建议一次冻结的对照与预算

本段是可审核建议，**不是已经冻结的执行合同，也不是本阶段已获成绩**。root应先将上述字段与最小来源选择写定，然后连续完成一次输入、6fit、12现金与独立复核；不要把另一个盘点当终点。

- 全部049 `399252`身份保留；全family、普通/F、unknown/open/cancel、无新字段与不交易行都保留。没有月Top10、55突破、交易所名单、源可用名单或未来完整闭合硬筛测试机会。
- 三臂 `COMMON / SETTLEMENT / OHLC_PROXY`，使用已存在 common26及26缺失列，再加同一 `external_missing` 与一标量槽，共54槽，固定 `Ridge(alpha=1, fit_intercept=True, solver=cholesky)`；不加载053或061模型/score，不搜索模型、alpha或特征组合。
- SETTLEMENT槽用上述x。OHLC_PROXY槽用 `x0=[C(v)-(H(v)+L(v)+C(v))/3]/N(v)`，它是明确可由旧OHLC计算的同一尺度替代，不称VWAP。两臂严格共享x实际可用mask，COMMON标量为0。这个对照有助区别新增成交分布信息和给线性头增加一个旧价格非线性摘要；**不是严格随机因果试验，也不保证代理同分布**。actual胜proxy但不胜COMMON仍算失败。
- 两个cutoff固定2020-01-01和2023-01-01，各只训练 `u<cutoff、label_known<cutoff、closed_complete_bar_model` 的049 stress净R，同训练行、并发唯一性/u均衡权重；全部标准化仅用成熟训练集，x/x0的缩放用两臂训练观测各半权重共同计算。缺失标量归训练标准化空间0，缺失indicator共享。未知/未闭合目标保持null，不补0；这一条件标签选择限制持续披露。
- 每臂对完整2020+机会预测，当时ready20且score>0才请求开仓；缺字段的family仍可由共同信息得到score，不从交易母体消失。三臂都采用同一日级决策频率，不能拿EIA周事件或054旧结果当这次共同参照。
- 现金为3臂×2020连续/2023冷启动×base/stress共12账本；沿042纯cash核与已冻结100w、单family0.25%/总2%、margin25%/buffer1.10、u联合预留/D只减量、2N/20low自然退出/无PT、两成本、旧epoch退出与unknown政策。退出、风险、保证金、窄损/加注均不变。
- 主证据为SETTLEMENT同时对两参照净收益更高且最大回撤不更深；同source日配对log增长按已用252日circular block/2000次固定seed作95%CI，两比较下端都>0；自身stress净增长为正，2023冷启动两成本方向一致。完整披露年度/family贡献、最大赢家、未解暴露/估值情景、手续费/滑点/交易/胜率。未知差异足以翻转方向则结论unknown。没有family训练外留出，不称zero-shot或全品种普适；大量重叠机会也不是独立样本。
- 若只有一所/一family/单年赚钱，只接受局部事实，不把该子集改成下一轮池；若增量CI跨0/点负/压力自身负，停止该固定字段+滞后+小学习器+执行包，不改成同日、改窗口、加turnover、加交互、换树或窄止损救结果。

## 第二条：参与者分布有机制，但当前不应实施

只有拿到真正逐会员、逐side、逐epoch、逐发布日的源，或至少有同口径Top5/10/15/20分层聚合，才能讨论集中度。一个可推翻的未来问题是：控制可见Top20总仓/变化后，头部占比不对称是否新增风险承接/拥挤信息，而非“净多越大越买”。最低可读schema应包含 `exchange,contract_yyyymm,trade_date,side,rank,member_name,position,reported_change,available_at,source_url,source_row,disclosure_scope`，每侧独立保留榜单。

本阶段不冻结会员指标/拟合预算，不在缺数据时把Top20总量当HHI。未来如果只能恢复聚合，可观察Top5/Top20侧内占比，不能宣称最终交易者集中度；若有逐会员，截断HHI也仅是可见贡献下界，未上榜仓位不能填0。会员更名/合并、每日排名成员变化、两侧榜单不一致、披露门槛、换月和2020单双边切换都可制造伪变化；完整family照留missing。发布时钟仍需原始证据，16:30不是保证。

旧079—081在另一目标/母体上否决简单方向，不能证明本线全机会分布AI失败，也不能反过来当本线成功支持。**当前继续会员alpha实施：否；继续有边界的来源可用性确认：仅在能够恢复确切现成源时有价值，不能凭论文或API存在新增采集工程。**

## 结果、反思与交接

- 本阶段新增/修改/删除策略参数：无；上文均为未来建议。新增/修改/删除回测结果：无。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率全部N/A。
- 模型fit/现金/SQL/新数据下载/资产登记/commit/push/正式操作：全部0。本次仅本stage；外部资料子agent独立给出会员资料与反证，未读写仓库。
- 开始是否过拟合：**否（本阶段没有收益搜索），但研究者已见历史的多轮择题风险存在**。结束是否新增过拟合：**否**；未读EIA新结果、未据收益选择本字段、未调旧失败包。真实结算观测与旧OHLC代理需同容量对照；只因列新或论文正就推进会增加选择偏差。
- 开始继续完整目标是否有价值：**是**。结束继续完整目标是否有价值：**是**；“真正新增但现成可读的观测”仍是能被低成本推翻的方向。继续本首选：**是，仅值得一次有限检验；当前置信度低到中，尚无净收益资格**。继续无源会员信号实施：**否**。
- 极窄止损与加注仍未证明。结算基准即使有效，也不能给出bar内顺序、跳空穿越、排队与加仓边际效用；不提前在本实验中优化它们。
- 合入建议：root读取本稿后只选一个下一行动；先补最小结算字段绑定事实，再决定是否冻结一次研究。暂不改LINE/registry、根memory/back_log或其他线；不是生产候选，不以计划宣称达成用户目标。
