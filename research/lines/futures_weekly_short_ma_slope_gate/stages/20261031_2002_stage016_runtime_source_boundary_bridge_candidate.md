# Stage016 Runtime来源边界修复与同会话桥候选封存

- 时间：2026-10-31 20:02（Asia/Shanghai）；重要突破：执行边界可审候选，非实盘晋升。
- 本线：futures_weekly_short_ma_slope_gate；旧8df runtime/f4ed updater来源锁和旧失败证据保留，新锁为runtime-data-bridge-source-lock.v3。
- 过拟合判断：否。本轮只修真实DTO来源与成交/持久化边界，没有更改alpha、参数、原565 class/function AST，也没有金融回测。
- 是否值得继续：是。来源污染、旧查询与真实成交错位、文件替换后的提交失败都直接影响持仓/风险正确性，必须在连接或晋升前解决。

## 来源负向与修复

Runtime原入口仅绑定close。现OHLC/volume/closeOI全部有限并与approved source精确绑定（同reader1e-9容差），OHLC价格关系、volume>0、OI>=0；缺closeOI直接拒，无openOI/0 fallback。真实OI0合法。新增本地时钟门，future及当日15:00前forming bar即使存在source row也拒。原RangeHistory与策略方法未动，full source lookup仅用于输入验证并在只读sizing clone共享。

Updater显式known epoch路径原漏真实quote delivery年月校验。现每个新增bar选择的原epoch均须与native delivery_year/month一致；AP612旧202612配2036quote/expiry反例拒绝并保持latest与原数据SHA；正常202612通过。仅检新增日，不用当前quote重写已批准历史。相同VT跨十年新epoch仍fail-closed。

## 会话桥

新增qmt_roll_weekly19_session_bridge.py，只把同一个runtime actor接入已有ExecutionService和已有931 warm连接。所有actor修改由service.actor_lock串行，通过PipelineStateStore.transact持久后才返回applied。实际provider typed authority/typed private ledger保留类型；公开源码qualification缺口仍拒，不用fixture bool替代。

连接前仅保存0600原始native packet缓冲，四查询完成后由实际public warm reader验证、真实fills先于orders、再与真实positions对账。native回调使用原packet capture_reference，由provider实际reader还原，绝不从vn.py规范化对象拼native来源。Order累计traded超过已消费actualTrade时保存durable deferred队列；临时阻全部new sends、cancel/query/实际回报可继续。真实Trade/query到达且fsync重放后仅清精确resolved IDs，跨重启恢复该barrier。

MD复用同main_engine/event_engine/CTP gateway。真实EVENT_TICK走已有TickStreamPipeline framedjournal，完成warm account/contract后订阅固定19main+actualheld/pending。publication返回实际durable cursor与全部当前pending（含已准资金重计划、close retry），不bootstrap全历史、不另建CTP。跨MD会话必须旧writer实际clean shutdown且cursor真实commit；缺失或fault阻断，不能只写clean=true。

fresh context只读取当前同连接四查询，不新query。使用真实journal quote、process-local session、actual ContractData tick/size/min/max、当前真实E/Available与原parent sizing重验。margin ratio仅冻结模型估计，标注frozen_model_estimate_not_broker_receipt，原fresh rawaccount及ReqQryMaxOrderVolume最终容量门保留。成交推进actor后旧四查询仍flat时明确requires_source_reconciliation，停止新child，不推算/改写positions。

actual_fill_lifecycle从bridge已持久provider原trade envelope逐项核对runtime实际fill semantic ledger；business approved/filled/remaining与immutable signed delivery parent cap/actual own-delivery filled/remaining分别列出，不把dynamic child量当parent cap，保留actual trade IDs/current state SHA。原quote durable state门严格保留，无一般state-advance豁免。

## 独审提交异常P1

旧_commit在os.replace成功、directory fsync失败后无条件恢复before，造成disk新actor旧。owned两反例先红。现异常读回checked actual store，恢复actor与last_bundle到文件实际状态，但继续抛原错误、不返回applied。读回或restore失败poison当前owner，下一commit/publish/sourceadmission拒并要求新owner恢复。原文件未前进时读回原state自然回滚。独审v2原反例绿。

## 验证与量测

- 全weekly19离线444调用/32.690秒绿；桥owned17/9.971秒绿；独审atomicity v2 1/0.403秒绿。
- 原565 AST与factory/MRO、purewarmup、周信号、全成交计划价等价仍由原equivalence测试验证。
- actual approved392382 physical rows、2015 positive contracts、2093metadata技术benchmark，0 on_bars/金融回测/下载/订单API。新runtime source before/end均5a7a911…；readonlyclone0.126秒，revalidate3.924秒，hotexport3.859秒，restore27.068秒。两runtime快照实际bundle10,186,712 bytes<64MB，fsync0.141秒，读回0.128秒，restore state SHA一致；peak约2.813GB。build/warmup只bootstrap，非每slot执行。
- 这说明实际fixture技术可行，不证明实盘deadline、收益或CTP资格。原研究经济结果未改、未复制为live结果。

## 明确限制与TODO

- 部分physical child已发/成交、其余child未知/未发时，不能从broker查询缺失制造terminal；保持父pending/reduce-only，manual_reconciliation_required边界，需另行真实日志协议/人工对账。普通全child真实回报路径已覆盖，不能声称全部batch事故恢复完成。
- 原四查询落后于actual native fill时只停止新增委托；离开当前batch后由实际refresh恢复。同batch不造updated snapshot、不放宽原quote state。
- 真实final现金statement、capture authority/source registry、release/qualification/activation及实际CTP生产证据仍由root后续提供；production_qualified始终false。
- parent/root负责Backend/CLI/production接线及Git，agent未操作index/commit/push/生产/CTP/SMTP。

参数与回测结果：新增/修改/删除策略参数均无；新增/修改/删除金融结果均无。期末权益、收益、最大回撤、Sharpe、滑点、交易数、胜率等本轮不适用（未运行金融回测）。
