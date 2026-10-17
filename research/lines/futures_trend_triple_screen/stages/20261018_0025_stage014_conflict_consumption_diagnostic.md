# Stage014 三个隔离冲突会话的字段与A0消费诊断

- line_id：futures_trend_triple_screen。
- 时间：2026-10-18 00:25 CST。
- 性质：限定数据法证，有实质来源合同发现；不是alpha突破、策略变更或金融回放。
- 改动：只新增本阶段记录。新增/修改/删除参数均无；新增/修改/删除金融回测结果均无。
- 执行：复用Stage011已抽取的三个冲突会话，仅读取对应旧base键、completed候选、A0原anchor/scan身份与相关生产/消费源码；未全量审计行情，未下载/联网/重跑账户或指标流，未改数据。

## 结论

三个冲突会话的全部重叠键和冲突键，与A0实际anchor及scan读取键交集均为0；这些特定冲突没有改变已完成A0的经济字段。此结论**不能扩展为全部Stage859旧数据未被消费**，本阶段没有检查其余会话。

冲突包含H/L/C价格，不能仅按量仓口径差异忽略；原open及openOI在所有重叠键上均相同。如果未来新路径消费这些会话的日内H/L，具有改变止损/retry结果的可能，本阶段没有运行该反事实路径或声称必然影响。

## 字段差异证据

按既有资格容差`rtol=1e-12/atol=1e-8`逐键比较。所有重叠旧行来自原base，Stage002 overlap为0。候选为Stage011已绑定旧manifest SHA的completed来源；三个session继续整段隔离，新增0。

| 精确会话 | completed行数 | 旧重叠键 | 任一字段冲突键 | open | high | low | close | volume | openOI | closeOI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| FG209.CZCE，2022-05-27 | 345 | 225 | 225 | 0 | 151 | 163 | 165 | 225 | 0 | 224 |
| cu2010.SHFE，2020-08-27 | 465 | 284 | 283 | 0 | 185 | 176 | 180 | 283 | 0 | 277 |
| cu2507.SHFE，2025-06-11 | 465 | 181 | 1 | 0 | 1 | 0 | 1 | 1 | 0 | 1 |

表中后七列为各字段不同键数，不是交易数。H/L/C最大绝对差：FG为7/5/5，cu2010为50/60/50，cu2507为30/0/10。open最大差三者均0。量仓最大差V/openOI/closeOI分别为FG 10357/0/2265，cu2010 2054/0/321，cu2507 45/0/22。

具体例子：FG209 2022-05-27 09:00旧high1765、completed1768，旧volume0、completed7625；cu2010 2020-08-27 00:01旧high51490、completed51500，旧volume0、completed55；cu2507唯一冲突2025-06-11 00:00，旧high79130/close79130/V0/closeOI208115，completed为79160/79140/45/208093。示例不是对全部旧行forming状态的统计。

## 来源完成合同的实质发现

所有冲突旧行的`minute_source`均为`stage859_tqsdk_backtest`。候选分别来自Stage461 completed probe（FG）及Stage462 completed shard（两个cu），来源字节SHA已重新核对。

本地原`examples/portfolio_backtesting/analyze_qmt_roll_stage859_stage856_tqsdk_backtest_gap_backfill.py:538`在`is_changing(klines.iloc[-1], "datetime")`为真后，540行立即取`klines.iloc[-1].to_dict()`；542—544行以`seen_ids`跳过后续同id；后续直接保存所取OHLCV/OI。它没有等待该键的后继K线再冻结值。Stage860 `_combined_patch_bars`在143行读入该patch，并在171行给予Stage859 source_priority，重复键保留last。

这是该旧producer不满足本线“观察后继才能视为completed”合同的直接代码证据，且与上述旧标签及已见volume0/未扩展HLC示例一致。本阶段未逐键重走原生成运行链，未取得原serial事件记录，因此不把所有带该标签的旧bar一概判成已逐行证明的forming，也不猜测SDK内部事件或上游价格真值。没有修改生产器、旧cache或alpha。

## A0消费范围

对这三个合约在原A0记录中实际出现的4个anchor键及810个scan键做精确物理时间交集；三个目标会话的全部旧重叠键和冲突键，与两类读取集合分别都为0。目标三个交易日本身也没有anchor/scan请求。

执行源码范围明确：Stage827 `_stage827_order_context`以分钟open定普通成交价，同时读取OHLC作合法性检查；`qmt_roll_intraday_execution.entry_session`读取时间键与OHLC作网格/合法性检查；`first_stop/stop_fill`及Stage847 stop/retry以O/H/L决定触发与价格。这里的分钟V/openOI/closeOI不用于上述触发/成交逻辑；策略仓位volume是手数，不能与分钟V混同。**这三个会话在A0中的实际消费字段集合为空**，因此无需重跑A0。

随后按root限定请求，只对原base必要身份/source列与A0既定106,731个去重实际读取键作join，全部匹配、缺0，没有审查价格/日线真值：

| 原base minute_source | A0实际读取键 | 占比 |
| --- | ---: | ---: |
| stage246_tqsdk_entry_date_snapshot | 72,889 | 68.29224874% |
| stage249_completed_trading_day_fragment | 33,842 | 31.70775126% |
| stage859_tqsdk_backtest | 0 | 0% |

535个唯一anchor键中Stage246=93、Stage249=442；501条scan请求形成106,515个唯一scan键，Stage246=72,870、Stage249=33,645。anchor与scan有重叠，不能直接相加为去重总数。统计保存在`outputs/stage014_conflict_consumption_diagnostic/A0_actual_read_source_distribution.json`。

这不触发“若A0消费Stage859，再对501 entry scan session做有界CSV日聚合资格审查”的条件。本阶段不执行该后续审查，也不把Stage246的snapshot名称自动判为forming；其他来源的数据真值仍不由路径equivalence或source标签证明。

## 资格、风险与后续

三会话仍整段隔离，未判定冲突双方全部字段的最终真值，不授权覆盖旧键、孤立修价、fallback、C0_attempt3或生产使用。可以保留为未来源合同/新路径分钟资格的独立约束；下一步如需处理，应预声明完整源和版本对照合同，不能偷偷把已验base替换为completed后继续沿用同一经济哨兵。

金融指标全部N/A：期末权益、收益、最大回撤、Sharpe、滑点、交易次数、胜率均未产生新结果。累计金融attempt仍4，完整仍1（A0_attempt2）；C0 alpha不可评价。

调研与判断：沿用Stage007官方完成K线定义，本次证据只来自上述本地源码和三个精确会话，没有新增联网市场事实。过拟合判断：否，未按PnL选参数或修改结果；继续价值：是，明确未消费冲突和可影响未来日内价格的来源风险，能避免错误重跑及无声覆盖。
