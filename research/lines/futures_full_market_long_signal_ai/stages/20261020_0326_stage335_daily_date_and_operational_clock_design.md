# Stage335：日K交易日与操作时钟的最小合同

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 03:25 CST。
- 性质：接收器设计；非重要收益突破、非正式A/B/C。仅读registry、333 next_scope、334最终、小源码与官方/维护者说明，0行情API/下载、0SQL、0旧价格/私有env、0fit/cash、0测试或实现。
- [必要小refs与建议字段](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage335_daily_clock_design/refs.json)。规则已直接同步336实现者与337独审；本stage不自动设T0或启动接收。

## 核心决定

把**交易日标签、按时段闭市的操作完成、实际收到、下一交易日首开**分开。接收器可先完整存raw，再对证据明确的行生成观察；不必证明交易所当年首发PIT，也不能发明vendor不可再修订的finality。source完成时间不能用本地收到时间替代，否则晚取10月19日会被伪装成冻结后样本。

## 日期：已核事实与可实施规则

官方[TqSdk API](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)及[行情说明](https://doc.shinnytech.com/tqsdk/latest/usage/mddatas.html)把86400称为日线，datetime写为K线起点的Unix纳秒。quote提供逐合约day/night交易时段，night可超过24小时记为25:00等。它们没有直接给出“全部日K必为交易日00:00”的统一保证。

维护者[日期helper](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/datetime.py)只有北京18点分界及周末规则；它不查询节假日。[回测源码](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/backtest/backtest.py)对日线及以上把item datetime交给trading-day-start helper，说明作者内部把日线坐标与真实开盘时钟分开。这个内部处理支持交易日标签解释，但不能代替服务端返回语义的普遍保证，更不能用回测CLOSE事件当真实发布时刻。已核本机3.10.2相应行577/637；网页当前3.10.3，未升级或执行API。

建议336采用下面一个明确、可审的操作规则，不根据后续效果更换解释：

1. raw_datetime_ns无损保存为整数，并同时存北京时间ISO；不从科学计数法显示字符串回转，也不依赖本机默认时区。
2. 对86400返回，若**实际ns精确落在北京时间00:00:00且无小数余量，日期在已确认calendar为交易日**，可取该日期为trade_date，状态`operational_midnight_label`，规则`tq_daily_midnight_label_calendar_v1`。这是本批实际格式与日历支持的操作标签，不写成“vendor统一保证”。午夜本身不是实际开盘或完成时间。
3. 非午夜默认`date_mapping_unknown`并保留raw。只有明确声明该源戳是实际session起点，且可唯一命中已确认的逐日具体session区间时，才能映该session所属交易日。不得逐行自由选择自然日或18点helper以凑齐日期；午夜标签也不得因有夜盘再无条件加一日。
4. 周末、节假日、复市与异常时段用有版本的calendar/override。quote.trading_time只是周期模板，不代表每个夜盘日期都开市；25:00按锚定自然日加25小时，不取模变成该日01:00。

有限检索亦见Tq官方论坛一个日K午夜例子，但回复者明确称自己不是官方；本设计不把它升为维护者保证，也不据此重审旧全部价格。334已说明265取自然date、266继承；此处限定新接收规则，不倒推旧研究必然错日。

## 完成：足够操作观察，不冒充最终发布

逐合约保留quote.trading_time快照、实际取得时刻、calendar版本及适用的节假日/临时session override。把该交易日全部实际session转换为带时区绝对区间，`session_end_at`取最后区间末端，不统一硬编码15:00。交易时段资料未知、过期合约特殊日程未知或日期映射未知，就明确对应unknown。

当日标签明确、session_end已确认且已过，随后取得实际fresh-ready的日线快照，可记`completion_state=operational_closed_day_snapshot`。这里的fresh-ready指本次真实连接/更新已取得该序列并完成初始化后实际复制的snapshot；`is_serial_ready`本身不等于bar-final。这个最薄定义接受“闭市后当时可取得的vendor数据”，不声称vendor不存在延迟、更正或后续修订，不要求稳定等待若干秒、两次相同值或等到下一根日K才放行。缺行、not-ready、字段缺失各自保留状态，不补零、不伪造成交。

| 字段 | 唯一含义 |
|---|---|
| `session_end_at` | 该u已确认最后交易时段末端，带时区、有来源版本。 |
| `source_completed_at` | 仅在上述操作完成条件成立时，取该u的`session_end_at`；未知则None。它是闭市规则下的源日完成代理，非vendor首发/最终修订时间。 |
| `received_at` / `completion_observed_at` | 321实际UTC留痕的接收/观察到完成时刻；不得回填、不得赋给source_completed_at。 |
| `vendor_finality` / `source_first_published_at` | 前者unknown，后者None；本次没有找到finality保证，也没有历史首发证据。 |

因此历史10月19日即使在10月20日首次收到，source_completed_at仍属于19日已结束session，不能因收到在T0之后就变forward。既有321判断仍分开检验`T0 < source_completed_at <= received_at <= sealed_at < D_open_at`及其原其他条件；没有T0、Dopen或确认完成，就只能发展/观察，不伪空仓或零收益。跨Dopen的迟到receipt保留gap，不追认active。后来修订另存版本，不改已封存输入/决定。

## D首开：按产品与具体交易日，不按自然日补

[上期所2026休市安排](https://www.shfe.com.cn/services/calenderandholidays/holiday/)列明周末调休仍休市及节前取消夜盘；[能源中心2026中秋/国庆通知](https://www.shfe.com.cn/publicnotice/notice/202609/t20260921_833507.html)明确9月30日晚无夜盘，10月8日08:55—09:00集合竞价、当晚才恢复夜盘。这足以否定“下一工作日固定前夜21点”的普遍算法；本次没有把这两所通知套到其他四所。

具体D_date取下一**已确认源交易日**；对某产品，用其适用day/night模板与该日override生成绝对session区间，D_open_at取该交易日最早实际可成交开盘时点。有正常夜盘时可能在前一个开市自然日晚间；长假复市首日可能仅白盘。collection/auction订单接受起点另外记录`auction_start_at`，不静默用它替换原D开盘门或新增提前五分钟政策；若无法确认首笔可成交/撮合时刻，就D_open_state unknown。

quote模板和calendar配合无异常日期可提供可操作日程；遇假期、特殊最后交易日或临时停市，所需override未核就unknown，无须现在建无限全市场时段工程。若全局caller仍只接一个D_open_at，应使用该次完整决策实际依赖产品/持仓的最早已确认首开，不能等选出赢家后才按赢家更晚首开挑deadline；影响者时段未知则如实披露并维持观察。

## 接线最小字段与本轮边界

336 normalizer输入只需symbol、raw整数ns、86400周期、声明的timestamp语义、已存calendar证据、quote.trading_time快照、session override及321实际receipt。输出trade_date/date_mapping_state/rule、raw_local_iso、session_evidence/session_end、上述三个分离时钟、D_date/open/state以及finality unknown。缺证据也能保存raw，不阻塞整个批次留痕；只是不升级该行资格。具体已知symbol→epoch只复用显式绑定，CZCE三位年份或F真实月等身份缺项不靠日期helper猜补。

继续沿333保留98/95既有母域及DCE.S unavailable，新catalog first_seen/unsupported另列。未来增量续331的744状态；旧epoch缺u16后恢复的indexgap重置由实现者沿既有gap规则处理，不在这里读取110MB价格、重播历史或修改Wilder。T0、实际paper初资与scheduler均未设，也没有订单/CTP/邮件通路。

过拟合反思：开始/结束均为本次不新增按收益调参；日期和时钟规则在真实新收益之前明确，仍不解除旧政策历史选择偏差。继续价值：有，三类时钟分离可防伪forward并避免接收死等下一根bar；继续搜无限首发PIT或改模型没有本轮必要性。新增金融指标均N/A，累计fit/cash不变。不改LINE/registry、旧代码或其他线。
