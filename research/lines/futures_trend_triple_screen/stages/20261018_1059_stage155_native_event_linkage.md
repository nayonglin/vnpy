# Stage155：原生事件身份与账户去向的单次接合

- line_id=`futures_trend_triple_screen`；2026-10-18 10:55—10:59 CST。已先读registry、当前LINE和Stage152；本线已有但未入registry，本次不修索引。
- 只新增本文及 `outputs/stage155_native_event_linkage/` 脚本/有限产物。不改交易、旧数据、tools、LINE、registry、其他阶段或Git；不派agent、不联网、训练、回测、prepare、provider或模型执行。
- 开始/结束新增过拟合判断：**否**。本次只接既定事件身份、原始状态和真实订单关系，不按未来PnL筛样或调参。开始/结束继续价值：**是**，身份表现在足够交独立审查，再决定有限事件路径合同；它不证明AI有优势，也不直接进入加注。

## 实际结论

**原始五键足够唯一：900个005 potential事件全部保留，886个同时进入A0与A_OFF候选表，14个仅见005；两臂无额外键、重复键或无效键。** 不需补入第六键。两账户各886个候选是同一事件的两份独立账户观测，不能加成1772个独立标签。

固定键是 `(u_date, product_vt_symbol, contract_vt_symbol, direction, signal)`。005映射 `signal_date→u_date, vt_symbol→contract_vt_symbol`，direction仅由该表原signal字面 `long_`/`short_` 前缀取得；账户使用原date/产品/真实合约/direction/signal。真实合约格式和产品前缀一致性均实际检查，大小写不改写，不用产品连续合约、成交方向或未来结果猜原信号。事件ID为 `stage155_native_event_v1_` 加该五字段canonical JSON的完整SHA256，两臂共用；原source row、candidate_index、logical datetime及状态分表保留。

005是**potential initial signal母体，非全体eligibility-qualified机会，更非已成熟经济母交易**。899条原状态potential_initial_signal、1条terminal_pending均保留。900条覆盖682个u日期、19产品；候选886条覆盖673个u日期、19产品。这些是唯一日期数，不是相互独立的有效样本量；统计单位不能换成817 fills、分钟根数或两臂之和。

| 实际关系/状态 | 数量 | 边界 |
| --- | ---: | --- |
| 全outer事件 | 900 | 005∩A0∩A_OFF=886；005-only=14；账户-only=0 |
| source_observations | 2672 | 900＋886＋886原观测，不是监督样本数 |
| 两臂各opened / skipped | 312 / 574 | 保留原reason，未选不等于负类 |
| A_OFF完整原诊断→精确初开order/trade→四表clock | 311 | 279个u日期；不把同日同合约当唯一证据 |
| 另1条flat_entry诊断 | 1 | 原signal_order_id为空，保留unresolved，不补造订单或收益0 |
| retry关系 | 85 | 原审查root/retry_fill/parent_order与实际order/episode/时钟全部核对；82可沿原初开回到event，3条父单属roll故event ID留空 |
| roll关系 | 8 | 只继承106显式fill→diagnostic关系并核目标实际初开/诊断；source_close_trade_id、source/target_event_id、economic_mother_id均留空 |
| 四表实际fill身份 | 817 | trades/clock/usage/actual_trade_identities的trade_id集合一致且各唯一；404 open、413 close |
| 已连event的实际open fill | 393 | 311初开＋82 retry；不把它们当393个独立event |
| 尚未连原生event的fill | 424 | 413 close本次未做事件归属，8 roll初开、3 roll retry；不是价格或经济结果错误结论 |
| 原pending order | 1 | cu2611.SHFE的Close/Submitting原行独立保留，无显式event绑定 |

574个skipped的原reason，两臂相同：`short_signal_rejected=320, ai_product_pool_blocked=151, sizing_zero_volume=87, concurrent_limit=16`。不能统称574条AI拒绝；本次没有将任何skipped、无order或q=0转换成收益0。1条无记录order的opened诊断准确为：u=`2020-05-11`、CF.CZCE/CF009.CZCE、long/long_case2、candidate_index=37、entry_index=14。原因仅能证明原signal_order_id为空，不能推断是否从未成交、为何未成或经济结果。

## 14个准确差集及原因边界

两臂对以下五键均无候选行；`key_differences.csv`逐行保存source absence证据及原状态。现有读取不能解释缺失原因，统一标记 `source_row_absence_only_cause_unresolved`；不根据持仓、skip或PnL补齐、删去或推断AI拒绝。

| u日期 | 产品 | 真实合约 | 方向/原signal |
| --- | --- | --- | --- |
| 2020-04-20 | sp.SHFE | sp2009.SHFE | short / short_case3 |
| 2020-12-01 | SM.CZCE | SM101.CZCE | long / long_case2 |
| 2021-03-23 | hc.SHFE | hc2105.SHFE | long / long_case3 |
| 2021-04-21 | rb.SHFE | rb2110.SHFE | long / long_case3 |
| 2022-03-04 | SM.CZCE | SM205.CZCE | long / long_case1a |
| 2023-08-21 | fu.SHFE | fu2310.SHFE | long / long_case3 |
| 2023-11-07 | lc.GFEX | lc2401.GFEX | short / short_case3 |
| 2024-08-09 | lh.DCE | lh2411.DCE | long / long_case2 |
| 2024-11-20 | ru.SHFE | ru2501.SHFE | short / short_case2 |
| 2025-04-22 | AP.CZCE | AP510.CZCE | long / long_case2 |
| 2025-06-10 | cu.SHFE | cu2507.SHFE | long / long_case3 |
| 2025-08-08 | fu.SHFE | fu2509.SHFE | short / short_case3 |
| 2026-08-11 | OI.CZCE | OI609.CZCE | long / long_case2 |
| 2026-09-01 | lc.GFEX | lc2701.GFEX | long / long_case1a |

## 实际身份证据与时钟

此次发现的有效桥是原 `A_OFF/entry_risk.csv`，同时保存原完整五键、entry_context和signal_order_id；319/320行该order字段非空。生产者 `analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac.py:223` 的 `_sync_entry_risk_diagnostic` 只处理非intraday episode的原初开，以真实TradeData信号时间匹配pending诊断，实际回填 `signal_order_id`。本次没有重跑该生产者，只将已接受结果与真实表核对：候选完整五键唯一且原status=opened → 原诊断原signal/order → `trades.order_id`和实际初开 → `trade_id`精确连接另外三表。

817条四表连接实际核对产品真实合约、方向、开平、交易日、物理执行时刻、signal_datetime、signal_order_id和intraday_episode_id；`usage.orderid`按实际gateway前缀还原后须逐字等于trades.order_id。原表中的无时区时间按既有Asia/Shanghai合同解释。本次不改原价、volume或时钟，也没有凭同日同合约连接actual初开。

u_date是原逻辑决策日；候选/诊断的00:00是原逻辑标识，**不据此声称真实盘中决策发生在午夜或所有特征已经可得**。order绑定是旧生产者在实际fill后记录的对应关系，不声称该字段当时已存在于入场前日志。本表不产生feature_known_at、label_known_at或新PIT资格。

retry单独核旧审查显式父order、真实root trade、synthetic order前缀、episode ID、同signal时刻、方向合约以及先后时钟。roll只证明既有目标fill与diagnostic关系；不按同日旧合约close粗连经济母链。413 close归属不是本次实现范围，保留原ID/clock并显式unresolved，不为凑闭合数继承signal_order_id。所有事件maturity均unknown_not_assessed，未成熟原状态未删除；没有任何经济mother或质量标签。

## 单次命令与绑定

实际唯一导出：`.py311/bin/python research/lines/futures_trend_triple_screen/outputs/stage155_native_event_linkage/build_linkage.py`。工具chunk=`03adb4`，10:58:46起止，**exit0**、0.207604333秒、stderr空；actual_terminal.json记actual_invocations=1。脚本是stdlib，所有输入各read_bytes一次，SHA和CSV解析消费同一份bytes；旧已知关键SHA逐一一致，未重hash7663行情源、未运行原native/旧suite。12项检查/范围标记均true，其中行数、集合、唯一性与关系一致断言实际执行；这只是本次接合一致性，不是新数据资格或独立审查。

完整19项source binding的绝对路径、全SHA、bytes、CSV全部header与行数在manifest。关键SHA：

| 来源 | SHA256 |
| --- | --- |
| 005 potential | `47f51b17bea78f52153866af93241bd9cbb1949246967e84125cdf0c594b1e61` |
| A0候选 | `600850b38a33deaf25f96a15dfd8fccf966b37824a6442bce93f6e4cf0217852` |
| A_OFF候选 | `a2f34a4280f281f655b83550a6bc60fa9954dcbd355e8263d46d851ff35ad597` |
| A_OFF entry_risk | `9a178df2e383582b73daf29ed4feb79a941f9a30eaa720058f2c634b46b70d52` |
| trades | `f09ef7c85210813b41f7923f25db813ffd436943dce67e3c70d24ac442082a1e` |
| execution_clock | `d7bfb6a1d68794b80528212e7f0c7f4f66a2f7a3954cd80eb123145325387ccd` |
| execution_proxy_usage | `981769c7c632cb9272584bdd0e4671c0f6158ed2fa0c72f57fcd625f83956d37` |
| actual_trade_identities | `d3caaa2badb21de10f23e774639223a1044a6ebe661ddfab9127a4bd61b57d40` |
| 106独立retry关系 | `0899ad1dfa06cfca0f6d4ecc3d2b11b0ecedb293deb5b9af536e919c50cf81a8` |
| 106独立roll关系 | `bf326016e6402d5c4f584c0e36a89474fe9cd0f3e1c88429e2b6c432f8ab5d65` |

| 新产物 | SHA256 |
| --- | --- |
| build_linkage.py | `a2b083a8aa4116d989d59bf82b7873441b80f78c56dff0cd4f955ba496950358` |
| manifest.json | `92134793ed171db1e38541614fbe627fcc9ae3ec3146347782574225dd143301` |
| actual_terminal.json | `d5192b8b1349baf55f616b2be220c5b2618c0eee1bd41a6db2153e648ae57770` |
| event_outer.csv | `58dca829c7b5787ba477f85a8c81ca0f98f509a9486fd7f6475fae13227522b4` |
| source_observations.csv | `15aba0691c731105ea9b2a698e5d90c49ead6be8537c56ef7610698fb591b627` |
| key_differences.csv | `3e32e9128425f31b9f0123c042efa710dc6935225db5461a4a0397ff70778dcd` |
| initial_order_edges.csv | `88943dadb6ba4bb2d9fbad85740cf7d980e710c2c24d65a937b41aeecaf8b1ad` |
| retry_edges.csv | `1f16958a163e513c6ee92c4ac58809a25ace2985b535d31df9af3819d798f069` |
| roll_edges.csv | `618fed4e38ef2059ab6262c11acc96b571cfcc79994c7d607f67cdb9c18a7452` |
| checks_and_counts.json | `ac961b83628f6b91ff3bca5eb692ab8e7a24f2a34d96e68a4089a6e203573b5f` |

## 交接边界与判断

沿用152已读primary资料，不新增外搜：Boyd风险约束/分布稳健Kelly仅支持未来考虑分布误差、回撤约束；不证明本仓库有alpha。Hudson&Thames官方源码页面多函数pass，仍只参考purge/interval合同。055/103/236及重建一期/二期、全市场002risk的失败约束原样继承，不重做高分加风险、meta-label或阈值/品种年份救参。

最短下一步是root独立接受该**身份/去向表**，之后另冻结必要有限形状的原生事件路径合同。此处暂停，不自行实现反事实replay adapter，不解14个缺行的推测因果，不扩新框架或清洗循环。全机会成本后质量标签、跨roll经济母链、最终成熟时钟仍未实现；AI选别增量、窄止损、加注继续分开，先固定风险核选别，不能把杠杆效果当识别力。

新增/修改/删除策略参数及回测结果均0；权益、收益、回撤、Sharpe、滑点、交易次数与胜率均N/A；financial/model/provider=0。root处理的prepare与本次无依赖，金融累计沿交接仍11attempt/4accepted，无新金融。新增过拟合否、继续此身份接合有价值；继续旧失败分数救参无价值，立即训练/加注仍缺标签与独立证据。production_qualified=false。
