# Stage016 订单原生桥、qualification-backed authority接口与macOS冷锁IO修复

- line_id：futures_weekly_short_ma_slope_gate；day；2026-10-31 17:23 CST。
- 只在weekly19-official隔离树修改owned组件；不改alpha、资金schema v2或15万/15万比例。
- 是否重要突破/A-B：否。没有金融回测或真实CTP/银行/SMTP，production_qualified=false。
- 旧V1/V2合同、manifest、独审与checkpoint全部保留，本记录是新源修订，不覆盖历史证明。

## 外部/仓库核验与判断

- 沿用前阶段[官方CTP结构定义](https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/api/include/ctp/ThostFtdcUserApiStruct.h)的Order/Trade/TransferSerial字段。
- 实读931 on_warm_order/on_warm_trade：实际event_consumer收到_object_to_row(vnpy Object)规范化行，不能声明它就是raw CTPdict。必须在CtpTdApi.onRtnOrder/onRtnTrade规范化之前保存真正native packet。
- 实读931 final query epochs：orders/trades的pending_callbacks完成后被清空，只剩authoritative normalized rows；account.raw_rows、position.broker_sizing_raw_positions保留原始。warm builder必须等待新冻结native_receipt，不能逆造raw或另起不同连接Stage174冒充same-connection fresh。
- 判断：订单累计状态/实际成交和源资格分层；真实查询本身不等于生产策略已通过。HMAC只检测非runner改写，不对抗同OS owner，完整qualification和active release外层pin仍必需。

## macOS锁IO修订

- 原51资金/WAL业务例全部保留。先补8轮x8进程cold barrier首创，旧实现8/8轮出现1-2个ENOENT/store_path_or_io_invalid；另补确定性非EXCL O_CREAT失效、removed-race、bounded失败反例。
- 修为相对dirfd O_CREAT|O_EXCL创建；EEXIST后O_NOFOLLOW纯open-existing，removed-race最多8轮重试，耗尽明确fail-closed。不预建锁，不退回绝对路径，不降低owner/0600/nlink1/0700父目录/逐dir防symlink。
- 修后55tests全部绿，8/8轮均恰好1个create+7个already_exists。只改funding_store IO，funding.py/schema v2原字节未改。

## 订单query与native push桥

- load_broker_order_updates(summary_path,manifest_path,execution_ledger_rows,**既有policy) -> weekly19.ctp-order.v1/source_kind=ctp_order_callback/source_callback=onRspQryOrder。严格绑定原始stable broker order ID、账户/release/profile、原intent、symbol、direction、业务/券商offset、volume/traded/status，未知status拒绝。
- status口径 accepted|working|partially_filled|filled|cancelled|rejected；累计traded仅来自native VolumeTraded，不能用caller completed_volume。必须先consume验证后的真实fills，再apply累计orders，否则runtime正确拒绝traded超过已知fills。
- event_semantic_sha256按runtime约定13字段canonical hash：account_key/material_release_id/intent_id/signal_order_id/signal_identity四原键/broker_order_id/vt_symbol/direction/offset业务/broker_offset/volume/traded/status；event_id='ctp-order:'+digest。source generation/时间/rawSHA变化不改变同一实际状态ID，原raw SHA照存。
- 原业务ID=planned_intent_id or ledger.intent_id，严格核signal_identity原业务ID；输出intent_id仍原业务ID，delivery_intent_id保留W19EXEC实际投递ID，不能混称。跨delivery/重启的唯一native->ledger映射仍必需。
- NativeBrokerCallbackCollector(account_envelope,connection_generation,service_generation,execution_ledger_rows)；bind_execution_ledger_rows更新已持久原始intent绑定；record只接受真正native CTP字段dict，拒vnpy Object/规范化行/撤销generation。
- instrument_native_broker_callbacks(td_api,collector,connection_generation=callable,clock=awareClock,on_recorded=callback)：先record原始onRtnOrder/Trade，再同步on_recorded供durable private保存，最后call原方法产生vnpy Object；退出恢复方法。
- persist_native_broker_capture(path,collector,now,after_sequence=已持久游标,capture_authority_registry=ref可选)保存0600原始proof；load_native_broker_events(ref,ledger,**policy)返回fills/orders和apply_order=['fills','orders']，保留native callback/connection/service generation/ledger内容SHA；重复、partial/cancel和restart语义可判定。

## 真实authority入口与调用合同

1. create_capture_authority_registry(registry_path, qualification_path/qualification_sha256, expected_account_key, material_release_id, execution_profile, source_commit, official_version, critical_files, manifest_created_at_utc, now, capture_kinds=('stage174_query',...))。
2. 不是读一个qualified:true：先核qualification原字节SHA、authority 8源闭环，再调用已有load_and_validate_production_qualification_evidence FULL验证（source/runtime/独审/tests/真实readonly artifacts）；同时核真实readonly账户、完整queries、trusted_subprocess runner和API0。失败不创建key/registry。
3. 成功后才在repo外已有0700私有目录原子创建0600 key/registry，返回{path,sha256}。key不回显、不进Git；active release必须外层pin registry digest，避免循环hash。默认只授权stage174_query，其它native_push/warm_epoch_snapshot/transfer_serial_query需registry明确scope。
4. load_capture_authority_registry(ref,expected_account_key,material_release_id,execution_profile,trusted_source_hashes,now)重新核完整真实qualification、源/账户/release/profile/原字节pin，返回typed CaptureAuthority，用户dict或boolean不能伪装。
5. Stage174新增 --weekly19-capture-authority-registry 与 --weekly19-capture-authority-sha256（配合原private capture/release/profile/invocation flags）；实际runner完整query/API0/counter窗口关闭/sourcecommit匹配时才签source-bound receipt。receipt绑定raw capture SHA、generation/conn/invocation/query内容/nonce/HMAC，summary与manifest同时引用。
6. load_broker_snapshot(...,capture_authority_registry=activeRef,require_production_qualification=True)可验证真实registry+runner receipt；不再永久stub。返回source_qualified标识只代表源授权验证，整体production_qualified仍false，策略部署/activation仍由root独立验证。缺真实registry/receipt具体block。
7. native persist/load也接受相同registryref，scope必须native_push；原始callback/ledger/generation完整内容被签名，不冒充query恢复。
8. 银行：persist_transfer_serial_capture(...,capture_authority_registry=activeRef)可签transfer_serial_query源；load_bank_cashflow_receipt(raw_query_envelope,state=...,request_id=...,bank_serial=真实BankSerial,now=...,capture_authority_registry=activeRef,capture_authority_receipt=privateRef['authority_receipt'],require_production_qualification=True)。仍核原生完整回调/时间/金额/账户/request/Deposit资金模块守恒。
9. load_cashflow_day_close目前仍明确accepted_cashflow_source_missing:missing_statement:final_cashflow_statement_parser；没有真实最终statement样本，不用clock或query-last代替现金封账。

## warm same-connection交接（本封存尚未实现warm loader）

- executionowner已接管931 native hook/controller。建议每epoch冻结weekly19_native_receipt：schema weekly19.warm-native-query-epoch.v1，kind account/positions/orders/trades，query_reqid、request_sent_at/completed_at aware、request_return_code、last_seen/error_rows、connection_generation/service_generation/account/release/profile、native_callbacks完整data/error/reqid/last/received_at/generation。
- 在last后、pending清空前deepcopy冻结；raw_rows仅从callbacks非空data派生，不能normalized逆造。账户必须保留Deposit/Withdraw/TradingDay/Balance/Available/CurrMargin/PositionProfit。
- 最终API slot只消费同连接已完成epochs，不再发任何query；warm真实允许orders，不套Stage174全程API0，仅核每个只读query的return/error/reqid/last/同gen/fresh以及native原始字段。
- root/executionowner后续授权独立warm纯builder任务，不属于本次44tests通过证明；缺冻结或qualified warm签名具体block。

## 验证/保留限制

- provider原31+9桥例+1二层ID+3authority拒伪/MAC例 =44绿；资金原51+4IO例=55绿；Stage174旧22/account旧25绿，共146tests。
- authority测试只验证拒伪registry、无效真实资格不生成key，以及离线测试key的nonce/payload MAC完整性；**没有创建真实registry/key，没有执行真实资格，没有拿fixture声明真实signed capture或生产通过。**
- Python内存compile/git diff --check通过；当前源码SHA、完整日志见同前缀manifest.json/unittest.txt。
- 原39独审cash/WAL反例由独审agent在新IO源上复验；本记录不冒称已重跑这些外部脚本。
- 没有金融回测，期末权益/收益/回撤/Sharpe/滑点/交易次数/胜率/PF均不适用，旧业绩原样保留。
- 后续独审锁源、真实资格registry/最终statement、same-connection warm/controller接线由root协调；不改LINE/registry/根总账/Git index/生产。

## 反思

- 运行前/后过拟合：否，只修执行证据与平台IO，不按历史收益修改策略。
- 运行前/后继续价值：是，补订单生命周期/真实源边界与冷并发可靠性；后续价值在真实资格与连接内原始证据，不是参数寻优。
