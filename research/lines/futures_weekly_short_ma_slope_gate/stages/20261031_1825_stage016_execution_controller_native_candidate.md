# Stage016 周线19独立授权、长连接与原生回报工程候选

- line_id：`futures_weekly_short_ma_slope_gate`；北京时间：2026-10-31 18:25。
- 工作区：`/Users/mac/.codex/worktrees/weekly19-official-20261031/fian`。原冻结树及生产只读；本组件未运行Git、CTP、SMTP、launchctl或金融回测。
- 性质：固定Stage014 C_R150工程迁移续阶段，非alpha改动，非重要突破版本；状态 `EXECUTION_CONTROLLER_NATIVE_CANDIDATE_FOR_REVIEW`，`production_qualified=false`。
- 本记录承接 `20261031_1641_stage016_execution_candidate.md`；未替代其原始负面证据，也不把旧C9默认下的测试沿用为本次资格。

## 调研与判断

继续采用此前已核对的 VeighNa 官方 [OffsetConverter](https://github.com/vnpy/vnpy/blob/master/vnpy/trader/converter.py) 与 [Portfolio StrategyTemplate](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/template.py) 的offset/回报语义；不升级本机冻结依赖。实际代码沿用已有Stage931发送器、物理批次锁、配额日志、幂等、最终报价、撤单与回报链。新增周线独立来源与授权，不让C9检测器或Stage903旧状态代替周线证据。

## 本次代码变化

1. 新 `qmt_roll_weekly19_controller.py`：只有实际 `LocalEvidenceBackend.require_production()`、当前weekly daily receipt、真实source registry能力与完整critical files闭包，才能加载process-local controller authority。JSON的qualified标记无效。生产manifest.source_commit必须等于真实生产HEAD；material来源提交另记material_source_commit，不混为生产HEAD。controller能力最多1天，静态qualification仍按已有validator处理，不另加生成日期老化规则。
2. controller读取实际spool候选，验证当前same-connection account/positions/orders/trades原始SHA及签名源、fresh风险/资金/报价/会话，再双读spool/cursor无变化后走现有slow_controller发布协议。独立weekly controller/arming/broker/quote schema不声称Stage903或旧Stage927通过。全部精准绑定source/material/qualification/activation/daily/data/origin-state、原planned signal、delivery、physical epoch、durable state、funding state、broker snapshot、quote proof、service/connection generation、spool/cursor和expiry。缺真实来源撤销授权并阻断。
3. 共享submit authorization增加weekly独立严格分支，旧C9分支保留。931 leased authorization核对实际不可变周信号、release/account、data、quote、position/durable state字段，不只相信caller的qualified布尔值。
4. 新 `qmt_roll_weekly19_execution_service.py`：持有一个runtime actor及RLock，原931长连接线程持续运行，禁止每个1秒周期替换actor或重建全历史。authority先验后才启动原runner。publication只处理原顺序中的一个未交付business候选；缺资金的blocked候选按原顺序轮询，不饿死后续减风险单。候选进入实际905、MD journal、spool、controller，再唤醒原executor。停止走原service退出，物理发送未结束时不强杀sender或越锁撤销。
5. publication前的四类真实查询刷新在exclusive authorization锁内完成，随后再取readiness。缺账户资金不能阻止只读刷新或真实减风险单，open仍受完整资金/风险门控制。macOS睡眠后即使monotonic未增加，只要实际账户receipt墙钟年龄过期就刷新。最终API-slot只读已冻结/已签源，不额外新起查询破坏原水位。完成的新account/position reqid同步更新readiness身份，避免长会话裁剪旧回调后永久失效。
6. 931在真实CtpTdApi.onRtnOrder/onRtnTrade原生包进入vn.py规范化前，交process-local native bridge持久化，再把真实proof引用匹配到规范化对象。数量、品种、方向、原生offset、OrderRef/TradeID必须一致。持久化失败保留实际broker事实并撤销新发送资格，不吞实际成交；旧连接迟到包不会冒充当前generation。原生query回调在pending_callbacks清空前deepcopy冻结完整data/error/reqid/last、真实request_ret、aware请求/完成时点及service/connection身份。原方法在正常/异常退出均尝试恢复；transport/native bridge关闭失败也继续恢复hook。
7. SHFE/INE拆单用实际converted requests生成 `weekly19.physical-batch-manifest.v1`，随原 `api_slot_reserved` 单次fsync事务保存完整logical children，任一insert前已知expected count/volume/offset但不伪造未来brokerID。actual batchID、full expected_children/SHA、approved_parent_volume及每个child ID贯穿before-native audit、send和callback；重启回报从durable row恢复相同证明。child实际broker_order_volume/child_order_volume与parent planned_volume分开，原生close/closetoday/closeyesterday不丢失。provider/runtime的V6整父聚合由其各自owner实现。
8. 修复实际warm lease materialization把weekly业务long/close覆盖为vn.py枚举的问题：现在先核对request枚举一致，再保留原业务字段。周Friday信号时间、next broker TradingDay和当期quote仍分别保存。
9. weekly同一已durable cursor允许另一真实business信号原子append；仅weekly19 consumer与两种周线source可用，真实MD字节和原25秒deadline继续验证，不借重复组装续期。C9默认cursor严格推进规则保留。
10. controller/service及其测试加入Stage179 critical files和required tests。root负责的backend、私有bridge、CLI/数据/邮件/正式release仍由root整合，本组件未修改top formal config/CURRENT。

## 可接入接口

`Weekly19ExecutionService(args931, *, authority_provider, fresh_context_provider, event_consumer, native_capture_factory, publication_inputs_provider, clock=None)`：

- `start(runtime_actor=actor)`、`publish(runtime=同一actor, bundle=..., data=..., now=...)`、`stop(timeout=...)`；提供active/runtime_actor/actor_lock。
- fresh_context_provider(row, transport_context=..., runtime_actor=...)返回实际资金/原规则风险/账户/当前quote上下文；最终每次provider仍应检查source authority当前。
- event_consumer(kind, normalized_row, original_intent, runtime_actor=...)接实际native proof引用，持久化并消费provider实际源桥，先fill后order，不把规范化对象伪称原生CTP字典。
- publication_inputs_provider(runtime_actor=..., bundle=..., data=..., now=..., transport_context=...)返回 `{decision, journal_segment_path, durable_through, optional feed_rollover_evidence}`；decision.intents应来自当前所有pending引擎意图，含真实补资后的replan/close retry，不限冻结Friday数组。
- native_capture_factory(transport_context=...)返回bridge：identity必须有account_key/material_release_id/execution_profile；capture_native(method, native, observed_at=aware)先持久化原始包返回private path/SHA；startup可返回admission_state=buffered，必须等同连接真实账户才能source-admit/replay；admit_completed_startup/admit_completed_query_bundle只消费已有四类完成receipt，返回source_qualified及真实warm_capture_reference；close恢复资源。API-slot不得由该bridge另起查询。
- 新provider公开 `load_execution_order_intent_bindings(privateLedgerPath, ...)` 产生typed来源，不能将其转普通JSON/list后冒充verified。

## 验证

两份日志均在**同一测试进程先打印**formal_default=`official_live_weekly19_base15w_reserve15w_stage014`、material_ready=false：

- 全部周线离线suite：338 tests，15.892秒，OK。日志 `20261031_stage016_execution_weekly_suite.txt`。
- controller/service/native/quote、原931 warm executor/shared authorization/spool/trace/execution ledger回归：245 tests，3.038秒，OK。日志 `20261031_stage016_execution_native_controller_regression.txt`。
- 两组有重复，不能相加当独立用例。negative CLI fixture打印usage是预期拒绝。
- 关键新增反例：伪qualified、旧903状态、material来源与生产HEAD混同、生产HEAD漂移、旧connection回调、query pending清空、native落盘失败、关闭失败仍恢复hook、真实quota原子childset、重启callback batch恢复、业务枚举覆盖、同cursor不续TTL、单周期全候选耗尽TTL、睡眠stale永久自锁。均以离线fixture先失败再实现。
- 中间曾在资金owner并发V6 TDD时看到15 failures/3 errors，后续稳定source的338全绿已重跑；不把中间RED删成未发生，也不把fixture当真实资格。

源码及测试SHA256与日志摘要见 `20261031_stage016_execution_controller_native_manifest.json`。本次新增/修改/删除金融回测结果均无；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。

## 边界与反思

组件已具备可接通的实际源码接口，仍等待root的最终backend/bridge接线、整分支独立review、source-bound生产selected suite、真实只读capture/行情receipt和不可变release/qualification/activation/Stage948证据；缺失时明确阻断，不声称正式已安装或已加载。用户已授权正式替换，本阶段没有再次风险许可流程；也未把旧研究限制改写为新的收益证明。

运行前后过拟合判断：否，此处只修复确定的身份、时序和实际执行证明，不筛参数或收益。继续价值：是，正确的外部现金、同连接native事实、整父拆单生命周期和可靠授权是固定策略真实执行的必要条件。仅写本独立stage及manifest，不改同线LINE/registry或根总账。
