# Stage002 独立终态审查

- 时间：2026-10-17 23:08 CST。
- 结论：**本地append-only数据及A0路径等价证明通过；C0_attempt2因新的真实分钟缺口严格失败。累计4次金融账户尝试，仅A0_attempt2完整验收，C0仍没有可接受收益/回撤或alpha结论。**
- 生产资格false，真实订单/撤单API均0。审查者未运行金融引擎，未重算周表或A0全账。

|账户attempt|终态|可接受金融结果|
|---|---|---|
|A0|sklearn生产者/消费者版本不兼容，保留失败|无|
|A0_attempt2|冻结runtime恢复，独立审账与旧A精确重现|有，已在Stage001验收|
|C0|缺rb2010的2020-05-18会话开盘anchor|无|
|C0_attempt2|旧缺口已有完整overlay，推进后又缺2020-08-12会话开盘anchor|无|

Stage002数据审查结果保持有效：134个已接受源、1,078,530新增键逐原行绑定，3369个实际添键session的独立网格及日线7字段聚合最大误差0；与旧base键和A0实际106,731读键均零交集，原base不改。881个隔离session未贡献新键。16个SQLite日线fallback源的502个session全部隔离，实际新分钟全部经CSV日线核验。详细证据见`data_review.md`和`overlay_independent_checks.json`，没有把局部覆盖承诺为所有潜在策略session齐全。

consumer最终冻结预检通过后才由根启动唯一C0_attempt2：实际runner SHA`928df4ba…969d4`；summary、overlay、source/session manifest、协议原快照、builder及独立数据检查SHA全部绑定。研究wrapper只append并拒绝原键重叠，scope及原调用链finally恢复缓存/loader/全局；没有修改已接受四个正式修复源码、AI、周特征、参数、成本、退出、retry或换月。

新失败原bar为`intraday_open_anchor_missing:rb2010.SHFE:2020-08-12:2020-08-11 21:00:00`。独立精确查询原base只找到8月11日日盘224行（09:00–14:58），没有所需21:00；overlay和134源中对应rb2010 Stage491原文件在8月11/12均0行，确认不是交易日/自然日映射假缺口。原5月18日的345分钟已独立完整验收且目标key在overlay，新的失败在更晚8月；失败receipt没有保留5月18日单笔scan事件，因此本审查不冒称又独立重建了一遍该日实际成交。

`C0_attempt2`目录保留attempt_started、runner_used、engine.log与run_failure，没有metrics/daily。原始bar错误可追溯，严格门没有用日线或旧代理乐观回退。独立对本次实际记录的403个输入、595,608,855字节做纯SHA复核，变化0；runner_used与预检SHA完全一致，overlay/source/独立审查引用正确。没有进行原始行情重清洗或第二次金融回放。

当前必须停止逐缺口补数—账户重跑循环。下一步先做全潜在信号session覆盖清单，区分已有完整、部分、冲突和完全无源，再决定数据补齐成本及是否还有必要重跑同一固定假说。禁止报告截断C0权益、收益、回撤、胜率、成本胜负或晋级，也不因失败改MACD/产品/年份参数。

过拟合判断：新增按收益选参为否；数据源选择性和累计历史偏差保留。继续价值：全面覆盖审计有价值，当前没有价值继续逐个新gap跑账户。不能把数据失败当作周滤网alpha失败，也不能称其有效。遵根明确限定，本轮没有新增网络调研，依据已接受本地源和前轮公开官方计算/模型文档继续核验。

证据：`C0_attempt2_failure_checks.json`、`consumer_checks.json`、`overlay_independent_checks.json`及Stage001的A0独立账本证据。
