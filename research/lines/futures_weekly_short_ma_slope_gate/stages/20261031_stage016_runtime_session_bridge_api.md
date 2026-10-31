# Stage016 同会话Runtime桥公共API（候选源码4207284a…）

本文件供root LocalBackend/ExecutionService接线。类不新建gateway、不connect、不query、不发单、不发邮件；source资格、实际CTP、final现金statement和production qualification未获fixture授予。默认require_production_qualification=True；显式False仅离线条件测试。

```python
from qmt_roll_weekly19_session_bridge import build_weekly19_session_service
service, bridge = build_weekly19_session_service(
    args931, runtime_actor=actor, bundle=current_bundle, data=loaded_data,
    authority=typed_controller_authority, state_store=pipeline_store, clock=clock,
    private_root=absolute_private_capture_root,
    execution_ledger_path=absolute_private_execution_jsonl,
    reconcile_cash=backend.reconcile_cash,
    session_provider=backend.session_provider,
    # quote_reader可省略，默认public read_weekly19_quote_snapshot
)
# 此调用只构造并绑定同actor和同service.actor_lock，不start/connect。
# runner/Backend按已有Service生命周期启动与关闭，不另写daemon。
```

Weekly19SessionBridge也可单独构造（同名kwargs，不含args931），随后bridge.bind_service(service)。authority必须实际Weekly19ControllerAuthority，production模式其capture_authority必须实际CaptureAuthority；拒dict真假资格。state_store必须实际PipelineStateStore；初始bundle.runtime SHA必须与actor一致。data至少metadata/calendar/receipt，receipt的release、trading_date与typed authority绑定；市场generation发生变化须clean close旧owner后由root构造新owner，不把新receipt塞旧owner。

clock是已有epoch_ns()/monotonic_ns()/clock_domain_id()时钟；桥给actor注入只读lambda now，sizing deepcopy不复制桥锁或整个service。private_root必须Git外、自有0700，原始packet/ledger snapshot/native capture/MD journal/heartbeat均private0600。

## 注入provider

- reconcile_cash(old_confirmed_cash, actual_snapshot, aware_now)→资金V2state。必须保留真实CP证据；已知final statement缺失/现金未知可返回旧CP并在绑定backend.cash_source_blocker给出明确原因，不能吞schema/account/source错误。桥用资金assert独立阻open；close/reduce不因现金等待消失。
- session_provider(row, *, transport_context, now)→{is_open,trading_date,session_id,starts_at,ends_at}，由root实际phaseD/forward calendar生成，trading_date与真实broker account相同。不得从未验JSON写openTrue。
- quote_reader(path, *, durable_through, symbol, clock, trading_date, session)，默认root public helper，返回实际durable journal bid/ask与ingress身份。
- typed private ledger通过public load_execution_order_intent_bindings保留_VerifiedExecutionBindings；不得list(...)丢证明。

## Service回调（factory已接好）

```python
bridge.authority_provider(*, now)
bridge.fresh_context_provider(row, *, transport_context, runtime_actor)
bridge.event_consumer(kind, row, original, *, runtime_actor)
bridge.native_capture_factory(*, transport_context) -> native_bridge
bridge.publication_inputs_provider(*, runtime_actor,bundle,data,now,transport_context)
bridge.close()
```

同一个runtime_actor对象贯穿全部调用；actor修改/资金/deferred/来源与MDcheckpoint通过同service.actor_lock→PipelineStateStore.transact原子提交。bridge.last_bundle始终是成功提交或异常后实际checked readback的bundle，Backend不得把旧本地bundle覆写它。

_commit发生异常不返回applied。若replace已发生但目录fsync失败，读取实际checked bundle并恢复actor与last_bundle，仍抛原错误；readback/restore失败则poison当前owner，禁止commit/publish/native sourceadmission，须由新owner从实际存储恢复。

### Native factory transport与真实回报

transport_context必须提供同连接main_engine/event_engine/gateway/td_api/rows、service_generation、connection_generation。rows保存931原生签名account/positions/orders/trades四query receipts与capture identity。factory在gateway.connect前安装MD ingress；初期无account时只私有原packet缓冲，不伪造账户。

```python
proof = native_bridge.capture_native('onRtnOrder' | 'onRtnTrade', actual_native_dict,
                                     observed_at=aware_native_receive_time)
native_bridge.admit_completed_startup(*, transport_context)
native_bridge.admit_completed_query_bundle(*, transport_context)
native_bridge.close()
```

capture_native只接受实际native dict；normalizedObject不得冒充。返回weekly19_native_proof含native/source_callback/nativeSHA/capture_reference/conn/service。collector public persist/load均传预加载typed capture_authority_capability，仍验证reference/identity/source SHA，不每回报重跑整production qualification。

四query完成后actual public warm reader→fills先orders→realpositions reconcile→吸收原始startupbuffer。native callbacks由public load_native_broker_events(capture_reference, typedledger, **policy)读取真实source，并核proof.nativeSHA绑定。Callback返回：

- applied/duplicate：state_sha256、durable_bundle_sha256、pipeline_revision，及已fsync真实重放的resolved_deferred_ids。
- deferred_durable：前述stateSHA及durable_deferred_id；order.traded大于已消费actualTrade，queue持久后返回，绝不假applied。
- source/identity异常直接抛，交既有Service barrier处理。

启动admit先恢复durable pending IDs至931 `_weekly19_deferred_broker_events`，receipt另给实际warm_capture_reference/source_qualified。未解决队列临时阻全部new sends，cancel duty/readquery/native回报仍可继续；仅真实Trade/query补齐且fsync重放后清精确IDs。

### 当前fresh context与成交守恒

fresh读取同连接当前已签四query，不在API slot新增query。实际native fill后旧四query仍旧持仓时抛weekly19_requires_source_reconciliation:broker_strategy_position_mismatch，继续停止next child；不构造updated query，不一般放宽quote durable state。真实refresh完成后才能恢复。

metadata来自同main_engine.get_contract，tick/size须与approved metadata相同；Min/MaxLimitOrderVolume来自实际contract。broker_margin_rate仅冻结模型ratio×原multiplier估计，明确margin_rate_source=frozen_model_estimate_not_broker_receipt/final_broker_capacity_gate_required=True，最终原native freshaccount+ReqQryMaxOrderVolume容量门不得省略。

context含typed execution_ledger_rows、真实quote/session/account/positions/orders、当前cash/state SHA、open_risk_proof与actual_fill_lifecycle。partial cap取immutable signed delivery parent，不取actual dynamic child。931传递：

```text
weekly19_immutable_parent_intent = 实际leased业务delivery parent
weekly19_current_physical_child = 实际converted request
weekly19_current_physical_batch = 实际quota batch/manifest/checksum
current_delivery_lease = 实际lease
```

actual_fill_lifecycle.v1字段：planned_intent_id/delivery_intent_id/signal_order_id；business_approved_volume/business_filled_volume/business_remaining_volume；delivery_approved_volume/delivery_filled_volume/delivery_remaining_volume；delivery_trade_ids；physical_batch_id/physical_children；durable_state_sha256。每条已接受provider原trade envelope与runtime实际fill semantic SHA逐项相符，累计量与actor order_filled相符，不能caller自报成交。original quote state严格门保留；ownbatch并不自动允许旧source继续发单。

rollover completed_close_intents仅全实际目标成交且actor terminal=filled、actual envelope累积完整才给，旧仓flat仍由执行gate核fresh actualpositions。reopen publication明确rollover_from_vt_symbol来自原close计划，依赖ID不改。

### publication与MD生命周期

publication_inputs返回{decision（全部当前非terminal pending intents）,journal_segment_path,durable_through[,feed_rollover_evidence]}。原ordinary approved cap不重计划扩大；真实T或原fundwait/低E admission才按当前实际E source-bound replan。当前资金revision/account raw/receipts SHA随真实确认更新，original funding admission ID不变；close retry使用fresh quote。缺现金来源只拦open，schema/source异常不吞。

MD在同warm gateway真实CTP EVENT_TICK捕获并落TickStreamPipeline journal，过滤其他gateway；warm account/contractready后订阅固定19main+actualheld/pending。关闭先恢复hook/unregister，再真实writer drain，现有Service spool中cursor以空intent detector batch真实commit；心跳只有该流程完成才clean。跨feed的typed DetectorFeedRolloverEvidence由私有旧clean checkpoint、旧cursor与当前header证明生成，缺失/fault不能假造clean。Backend须调用service/bridge既有close流程，不可直接丢owner。

## 候选边界

partial child已发但另一child未知/未发，且无经审核native未发送证明时，不能由query缺席造terminal；父pending/reduce-only，明确manual_reconciliation_required。真实final statement、registry/release/qualification/activation/CTP生产证据仍缺则blocked。离线完整dry integration只证明真实组件可条件接通，不表示生产晋升。

当前owned17 tests、全weekly19444tests及独立atomicity反例见同目录新v3 source锁与20:02 stage。未金融回测/下载/连接CTP/订单/SMTP/Git操作。
