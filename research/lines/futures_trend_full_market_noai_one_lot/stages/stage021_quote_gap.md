# Stage021 AL2110截止日价格缺口的原源调查

- line_id：`futures_trend_full_market_noai_one_lot`。
- 时间：2026-10-18；本次只读调查，不跑金融回测，不下载，不修改clean/旧inputs/expiry overlay。
- 重要突破：否。问题属于数量争议整键隔离对已有仓位平单的连带影响，需建立单独执行资格，不是新alpha。

## 根因与三源证据

精确epoch `SHFE.AL.202110`，native `al2110`，maturity=2021-10-15。新实际运行于2021-09-24生命周期截止未能平仓；已有close意图在9/23产生。该天accepted clean缺失，但不是原档没有价格。

| 来源 | 精确定位 | open/high/low/close | V | closeOI |
| --- | --- | --- | ---: | ---: |
| RQ | futures.h5 / AL2110 / row232，date20210924 | 23520/23635/22760/23115 | 180549 | 87233 |
| 官方SHFE | SHFE_futures_2021 normalized row26893；原2021.09.xls第271行 | 同上 | 191338 | 90833 |
| 旧TQ | SHFE/al2110.csv，含表头第234行（DictReader零基数据行232） | 同上 | 191338 | 90833 |

三源OHLC完全一致。官方和旧TQ的V/收盘OI亦一致；RQ的V与OI不同。原单位制度已是单边，不是简单单双边换算；不能随意按比例修正RQ或宣称真量已被认证。`stage266_units_quarantine.csv`将此键列为`unresolved_cross_source_quantity_conflict`；`excluded_observations.csv.gz`完整保存三源记录；该键不在price_conflict_quarantine。

官方原zip路径：`/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/other_exchanges/shfe/raw_years/shfe_futures_2021.zip`，SHA256 `e9962695770b84da1001a108fd42b2422ce5be2b9c954fcd7c40e879c32eba48`。

zip中2021.09.xls原member因旧编码显示为`╦∙─┌║╧╘╝╨╨╟Θ▒¿▒φ2021.09.xls`；member字节SHA `897666bd3505f8606a4beac50822210329e92bc6c065ce8e85714d2a3bc29e80`。实际sheet`所内合约行情报表`；第256行的al2110合约标识向下延续，第271行日期明确20210924，未跨epoch或跨日引用。

官方normalized已锁SHA `79c1961919782278852c237fd44ff3a323a41aadebd47365f29c803ef2313663`；旧TQ路径`/Users/mac/Desktop/fian/examples/portfolio_backtesting/downloaded_futures/tqsdk_daily_2010_2026_04/SHFE/al2110.csv`，SHA `a6c8777c2add75bc418f6446e8550234862037d89c3a194c0458a48147f2e5b3`，与clean sources表锁值一致。RQ H5锁SHA仍`d288f6e4c7468981e95fbb0c1c9e2e1e66bfb99f5ba607843728aec535c8bfee`。

近邻accepted clean：9/23 V188359/C23500，9/27 V145748/C22760；它们不是9/24平仓的替代报价，不能回溯或延期后仍声称在截止日成交。

## 与旧expiry overlay的区别

旧Stage010要求maturity当天、官方与RQ OHLCV完全同、仅官方OI0与RQ正OI时点差异。AL9/24不在maturity，且V亦不同，**不能假装旧合同已经允许它**。但三源逐价一致给已有仓位真实市场价格提供了独立资格依据；数量仍有争议，应保留quote_only边界。

全数量隔离的初步只读排除账census（2014—2026-10-16，尚未限4328/未验全部原档）：2294键；1045键有唯一RQ+官方、所有在场源OHLC同且V正；50键存在至少一个源的价格分歧；1199键缺唯一RQ或官方。该1045是候选，不是已生成可执行价格数，不能直接填回训练数据。

root已在用户修复授权内批准Stage023通用独立价格overlay，条件为精确epoch/date、quantity-only隔离、所有在场源OHLC完全一致且合法、规范化各源V>=1、至少RQ+官方原行/hash证明、已知epoch且不晚于maturity；剔除与accepted/expiry重复。所有同结构键统一覆盖，不点名AL、不按收益或截止成功筛选。执行V取各源正V最小值只作一手资格门，OI以官方quote_only保留；二者不认证真实量仓。不准用于信号/新开仓/主力选择/AM预热/训练。

具体实现与最终逐行来源receipt在本线`tools/stage023_quantity_price_overlay.py`及`outputs/stage023_quantity_price_overlay/`，与本调查分开。原数据完整保留；所有价格分歧键继续拒绝。root应让独立review审该新overlay和加载器之后另开新run，不把已失败run_v1改写成成功。

## 调研判断与反思

本轮沿用前序已查看的vn.py官方组合引擎与本机Stage265冻结原档reader；判断是把“价格执行资格”与“训练量仓接受资格”分开，原训练整键隔离仍有价值。不把RQ、官方、TQ的同价视作真实反事实委托必然有流动性，也不猜数量分歧具体发生在哪一时段。

开始/结束新增过拟合判断：否，此类数据接受条件不看收益、产品表现或截止成功，只看身份、价格和来源证据；属于故障发现后的显式合同修订，仍需披露post-discovery边界。继续价值：是，已有仓位平单不应因无价格分歧的数量争议被不必要地阻断，但不能因此放宽价格争议或伪造缺价成交。

新增/修改/删除alpha参数与金融结果无。权益、收益、回撤、Sharpe、滑点、交易次数、胜率N/A；本agent金融回测、模型拟合、下载、CTP、订单API均0。
