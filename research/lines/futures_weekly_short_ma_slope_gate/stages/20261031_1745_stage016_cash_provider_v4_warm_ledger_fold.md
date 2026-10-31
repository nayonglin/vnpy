# Stage016 同连接 warm 原始查询证据与执行账本身份折叠

- line_id：futures_weekly_short_ma_slope_gate；2026-10-31 17:45 CST。
- 原1723 V3、1650 V2及1622 V1证明全部保留；本次是新增源修订，不改旧manifest。
- 不改alpha、原风险或15万/15万比例，不运行金融回测、CTP连接、银行、SMTP、生产安装、Git index或commit。
- 重要突破/A-B：否；production_qualified=false；没有真实registry/key/qualification/capture。

## 调研与判断

- 对照[上游vnpy_ctp gateway源](https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py)和本机已安装6.7.2.1 gateway：原生onRtnOrder/onRtnTrade在内部生成OrderData/TradeData；收到vnpy Object后的规范化行不能冒充原始CTP字段。原生query的reqid/error/last与push回调也须保留区别。
- 仓库931现有query epoch完成后会清理pending；executionowner负责在原生入口冻结weekly19_native_receipt。本组件只消费冻结receipt，不另起Stage174连接或query冒充同连接fresh。
- 判断：完整原始证据、采集source authority、策略production qualification是三层独立门。HMAC只检测非runner改写，不对抗同OS owner；真实qualification registry和active release外层pin仍必需。

## 新增pure warm API

- 新源qmt_roll_weekly19_warm_evidence.py；load_warm_broker_snapshot(transport_context, **policy)，policy沿用expected_account_key/material_release_id/execution_profile/now aware/trusted_source_hashes/require_production_qualification=True/capture_authority_registry；可传预先FULL验证的typed capture_authority_capability避免最终API槽重做资格校验。
- transport_context含rows/service_generation/connection_generation；rows['_weekly19_capture_identity']绑定账户/release/profile及两generation；rows['_weekly19_native_receipts']必须恰好account/positions/orders/trades四类。
- 每receipt schema=weekly19.warm-native-query-epoch.v1、kind、query_reqid、request_sent_at/completed_at、request_return_code/request_ret真实一致0、last_seen、error_rows=0、late_callback_blockers=[]、身份/generation与native_callbacks原dict完整保留。
- callbacks逐条核reqid/connection/error/last唯一且位于末尾/aware时间顺序及300秒fresh；原始data不接受normalized Object替代。四query reqid唯一，账户必须唯一CNY且含真实Balance/Available/Deposit/Withdraw；position split按Position聚合，不重复加YdPosition。
- 若epoch镜像存在，complete_reqid/active_reqid及完整receipt必须与权威冻结对象相同。缺失receipt时禁止normalized/pending fallback。
- 订单原生Front/Session/OrderRef与Exchange+OrderSysID唯一，未知enum、累计status/volume冲突、发生晚于承载callback均拒绝；SHFE closeToday/closeYesterday保留原flag。TradeID稳定原身份/金额/时间来自raw，trade与唯一raw order direction/offset一致；未来trade不重贴query时间。
- 输出account/positions/orders原有raw envelope，加trades集合weekly19.ctp-trades.v1/source_kind=ctp_trade_query及native_source_sha256、connection/service generation；集合本身不是已绑定intent的实际成交事件。
- warm服务允许真实order计数，因此不错误套Stage174全程API0；只核每个query的完整只读返回/reqid/error/generation。整个loader不调用td_api任何方法。
- persist_warm_native_query_capture(privatePath,transport_context,**policy)在query完成边界保存0600不可覆盖artifact，签名ref放transport_context['weekly19_warm_capture_reference']；最终API槽只读已完成epochs及该ref，不发新query。
- 生产默认缺signed frozen epochs/active registry明确warm_capture_authority_missing。CAPTURE_SOURCE_FILES仍5；CAPTURE_AUTHORITY_SOURCE_FILES从V3的8补warm源为9，registry必须明确授权warm_epoch_snapshot。caller qualified:true、native-looking dict、普通rawSHA不能给生产源资格。

## 执行账本公开fold

- provider新增derive_order_intent_bindings(full_generic_ledger_rows, *, expected_account_key, material_release_id, execution_profile) -> 按真实broker_order_id/vt_orderid排序的唯一derived bindings；再交load_broker_fills/load_broker_order_updates/load_native_broker_events和collector.bind_execution_ledger_rows。
- 无nativeID的reserve/API-slot行不绑定回调。相同原订单的reserve/send/callback等同语义事件折叠，不因事件数量大于1误判原intent歧义；冲突身份立即拒绝。
- 支持account_key/account_fingerprint和signal_identity/signal_identity_json双表示，双值必须一致；严格原4字段identity。业务ID=planned_intent_id or delivery intent_id；保留二层ID，不把W19EXEC和原策略ID混称。
- 只从planned_volume/broker_order_volume/order_request_volume建立原订单量上限；不同明确cap须一致。成交callback.volume绝不推断为原订单量。direction/offset仅long|short/open|close，broker_offset/native_offset_flag可保留真实值并交叉核。
- 原query/native loaders仍严格要求唯一derived bindings；fold不证明来源，不认证未知用户ledger。caller需先提供原执行账本验证链。

## 验证与限制

- TDD：新增3组ledger fold测试先因API缺失RED；实现后GREEN。新增warm重复订单（无成交路径）、终态冲突与future order测试先RED，修后GREEN。更多warm反例覆盖缺raw、reqid/last/error/late/return/conn、stale/future/naive、现金/身份/枚举、mirror/sourcepins、SHFE、伪qualification。
- 最终provider47 + warm11 + funding61 + Stage174旧22 + account旧25 =166项unittest全绿；Python compile及git diff --check通过。完整输出和锁源SHA见同前缀manifest/unittest文件。
- 没有真正的成功source-authority qualification分支证据；测试fixtures仅条件解析且production_qualified=false。真实registry/statement/CTP capture缺项仍保留，不声称生产、银行到账或端到端通过。
- 银行final day-close依旧缺accepted原始最终statement及parser，load_cashflow_day_close明确missing_statement，不用clock或query-last构造封账。正常日切缺证据应停新开，已持仓减仓不由资金建议伪锁。
- 本次没有金融参数或业绩增删：期末权益、收益、回撤、Sharpe、滑点、交易次数、胜率/PF均不适用。root/931 owner负责实际hook/controller接线和release全传递源pin；独审另记。

## 反思

- 运行前/后是否过拟合：否，只补证据与身份合同，没有按历史收益调参数。
- 运行前/后是否值得继续：是，同连接真实原始证明和稳定重启去重是执行正确性所必需；下一步以真实资格和最终statement为门，不以更多fixture替代。
