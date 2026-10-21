# Stage350：19—21日最薄操作日程依据

2026-10-20 03:58 CST；line_id=`futures_full_market_long_signal_ai`。先读registry/345nextscope/335refs/347。只调研设计，0行情/quote/经济/raw/SQL/实现/测试/fitcash，T0None；不改LINE/registry或生产材料。

**结论：可以冻结`operational_regular_schedule`，不能签“六所全部具体session已无例外证实”。** 最薄依据是后续一次真实quote的逐symbol周期模板＋已接日历19/20/21为True＋下面普通日锚定。root已接受此口径；缺模板、生命周期/日期适用冲突或已知停市override就unknown，不要求穷举全站负面证明。本阶段没有读取该quote，故不填写874合约的实际区间。

## 证据及一项纠正

[上期所当前交易时间](https://www.shfe.com.cn/services/calenderandholidays/tradinghours/)直接规定夜盘从上个工作日21:00开始，并按产品列23:00、次日01:00或02:30结束，日盘一般15:00结束；能源集运等仅日盘，不能把夜盘复制给所有商品。SHFE/INE2026休市与复市通知支持10月8日恢复后的普通安排；GFEX官方2026年表亦列国庆1—7日休市、8日起开市。这些通知没有把19—21日列为节日，也不是排除所有临时事件的证明。

**纠347的旧口径：国债09:15不得沿用。** [中金所10年国债修订细则原文PDF](https://www.e-cffex.com.cn/u/cms/www/202007/08152235b2ys.pdf)第11条为普通日09:30—11:30、13:00—15:15，最后交易日仅09:30—11:30；集合竞价申报/撮合另列。股指普通日到15:00，不能和债统一收盘。其他国债仍以本次各自quote模板与适用规则核对，不只靠T推广。

有限检索未直接取得DCE/CZCE/CFFEX2026休市原页，转载仅作通知线索，不升为primary或声称已查尽。详细链接与访问限制见[小refs](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage350_regular_session_design/refs.json)。这不阻止采用明确声明的普通日操作假设，也不把较弱证据伪作交易所逐日担保。

## 日期展开：仅三个交易日及相关前夜

| 所属交易日 | 有夜盘模板时的锚定自然日 | 白盘锚定日 |
|---|---|---|
| u19（周一） | 10月16日周五 | 10月19日 |
| u20（周二） | 10月19日周一 | 10月20日 |
| D21（周三） | 10月20日周二 | 10月21日 |

按实际quote.day/night逐区间展开，不能以交易日减一天生成周一夜盘。`25:00`必须按锚日00:00加25小时，例如16日25:00是17日01:00，仍属u19；不是19日01:00。[Tq官方定义](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.objs.html#tqsdk.objs.TradingTime)及维护者日期源码支持这种锚法，18点/周末helper仍不能替代节假日override。无夜盘模板的产品只展开day；空模板与确认无夜盘须区分。

每symbol/date只需保存：template及实际取得时间/版本、calendar依据、night_anchor、具体带时区区间、`applicability=operational_regular_schedule`、已知override/冲突、session_end与execution_open；不存“已证明不存在异常”布尔真值。当前模板应用到附近三日是限定操作解释，不倒证当年首发或永久时段。

## u20完成与D21截止

对完整观察实际依赖域取所有已确认末端的最大值：包含普通国债时，u20最晚通常是20日15:15，而非15:00；缺失/冲突影响者不假定已完成。闭市后实际fresh-ready快照才观察到操作完成；`source_completed_at`取确认的session_end，**不能取receipt**。completion_observed_at/received_at各留实际接收UTC，vendor_finality仍unknown，不等下一根日K。

D21的原execution_open：有正常夜盘模板通常为20日21:00；无夜盘商品通常21日09:00，中金所按各模板通常09:30。全局同批选择用依赖域最早open，不能选完赢家再挑晚deadline。auction申报起点、撮合窗口单列，不静默把原Dopen提前到20:55/09:25或改预算政策。可操作窗口因此通常为20日15:15之后、20日21:00之前；须以真实模板/冲突结果为准，不保证未来必可及时取得。

开始/结束反思：无收益调参，不新增该类过拟合；核清普通日展开有价值，不再扩大原页搜集或生产资格。金融指标N/A、累计不变。下一步仅由root接一次metadata后展开日期；本stage不授权新probe、T0或账户。
