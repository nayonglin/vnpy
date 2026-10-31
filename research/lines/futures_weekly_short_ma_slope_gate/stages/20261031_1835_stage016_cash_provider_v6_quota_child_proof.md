# Stage016 V6 真实 quota 子批次证明与订单恢复闭环

- line_id：futures_weekly_short_ma_slope_gate；实际封存时间：2026-10-31T18:35:18.860602+08:00。
- 本次root明确授权V6，V5/1745/1723/1650/1622历史proof、源码hash、manifest、独审与失败记录均保留；不以V5独审覆盖V6新源码。
- 重要突破/A-B：否；不改策略alpha、风险参数、15万/15万资金比例、funding schema或旧cash业务；不运行金融回测、CTP connect、银行、SMTP、生产安装、Git index或commit。
- production_qualified=false；无真实registry/key/qualification/capture/到账资格。

## 调研与判断

- 对照[官方vnpy_ctp gateway](https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py)、本机6.7.2.1及当前931原生回调/真实quota闭包。query回调与push分层不变，不能把vnpy Object自称raw CTP。
- 既有reserve_execution_api_slots在exclusive flock内写单条api_slot_reserved，嵌入完整api_slot_batch_children后fsync；这才是父logical名单的证据。单callback自附children/布尔verified/rawSHA不等于该事务。
- 既有执行ledger只有逐record checksum，没有hash-chain，不具同OS owner对抗认证；正式来源依赖私有真实账本、受信runner/source hashes及独立production registry。
- 判断：父状态必须按全部logical child聚合。尚未报出的child没有brokerID，但仍在完整名单中；单个child filled/cancelled不能提前完成父计划。

## 新API与真实来源门

- load_execution_order_intent_bindings(private_ledger_path, *, expected_account_key, material_release_id, execution_profile) -> 进程内typed immutable list。逐directory O_NOFOLLOW、owner/regular/nlink1、parent0700/file0600，SHLOCK读取完整JSONL；严格重复JSON key/nonfinite/末尾残缺和旧integrity哨兵均拒绝。
- 该list持原始ledger SHA、条数及binding SHA，外层/嵌套意外篡改会被摘要门识别；普通list/JSON qualified:true无法制造该能力。source只表示私有读取和完整性，不自动生成source/策略生产资格。
- 生产load_broker_fills/order_updates/load_native_broker_events/load_warm_broker_events要求此能力；普通derive_order_intent_bindings(fullrows)继续用于条件解析/旧离线测试，不能代替生产来源。
- collector.bind可收该能力，原生记录保存源凭证与binding摘要；签native capture时每条record必须有真实reader来源。真实source authority/registry仍是另一层强门，fixtures不获得资格。
- generic ledger旧创建依赖umask，本组件不把0644降级接受。生产bootstrap需在任何quota前安全准备0700/0600或umask077并验证实际模式；旧私有权限不足明确block，不凭研究树测试声称host已就绪。

## quota→native→统一envelope

- 先从完整api_slot_reserved要求非空有效record_checksum、actual 24hex api_slot_batch_id、send_order/计数/全部nested child；按完整账本前缀既有_api_slot_usage及真实base_events重算quota batchID，不能用caller命名。
- 每个nested child必须同一weekly19.physical-batch-manifest.v1、delivery/planned identity、payloadSHA、lease、service/connection、账户/release/profile/source/version/物理epoch，并有完整7键descriptor：child_order_id/index/volume/broker_offset/vt_symbol/direction/trading_date。index连续、ID来自原fingerprint、volume正int、sum=approved_parent_volume，close总量等于父计划。
- 然后要求后序native_order_identity_persisted_before_insert record独立checksum、native_api_called=0、真实reqid/FrontID/SessionID/OrderRef与券商ID、native_offset_flag及实际child量匹配。只能给真正有before-insert记录的child绑定brokerID；不预填未报订单号。
- callback记录如带manifest/batch，必须与quota一致，不能早于before-insert，不能把同一真实brokerID换child/batch。缺quota、prefix残缺、缺/错native proof、重复quota/audit、跨scope、nativeflag/cap/lease或名单冲突全部fail-closed。
- 统一输出execution_batch_id==api_slot_batch_id、api_slot_batch_count、approved_parent_volume、expected_children/digest、child_order_id/index与execution_batch_proof/digest（quota/native身份记录各自checksum+canonical记录SHA；整个私有账本原字节SHA另由reader来源凭证保留）。原始child volume/traded保持native实际量。
- query/native/warm order与fill桥全部携同一父proof，保留真实onRspQry*/onRtn*。原order13字段semantic digest继续不含batch；runtime在重复去重之前独立核immutable batch identity，防跨batch复用。

## 实际源码接缝、反例与保留失败

- TDD先观察新API缺失、原envelope不含batch与不拒残缺quota等RED，随后8组provider反例及warm专项GREEN；涵盖完整2child只有首child nativeID、caller名单无quota、计数/摘要/原scope/checksum/顺序/offset/cap/重绑、私有symlink/权限/JSON/残尾、source pins、对象篡改。
- 不只手写quota：provider测试调用真实931 session._reserve_api_slot及真实callback builder。先真实reserve_execution_ledger_intent建立close lease/warm reservation，真实quota落盘；模拟native-before身份记录只用于离线连接桥，未执行真实native insert hook。
- 此真实构造发现父order_request_volume可为2、physical broker_order_volume为1。V6按真实优先级broker_order_volume→order_request_volume→planned_volume绑定native，不再强迫父request与child相等；父planned/request和实际child分别保留。callback缺child_order_volume时只用明确的broker_order_volume，不用trade.volume；可选reservation ref若出现须匹配，quota/native核心ref仍严格。
- executionowner补callback真实child_order_volume/ref、重启metadata fallback及本机Offset.value含空格Close Today/Close Yesterday的业务alias；原生3/4保持精确。没有为通过而放宽close CAS。
- 第一轮allweekly341发现owned execution新增正例未建立close lease，正确被CAS拒；失败日志20261031_1830_stage016_cash_provider_v6_quota_child_proof_failed_unittest.txt保留。owner补合法reserved+quota两条事务后全绿。另修掉931一处末尾空格，源SHA重新封存。
- runtimeowner新增provider→runtime真实query fixture接缝：实际open2/close2计划，child3 filled+child4 working，public provider fills/orders→actor；父余1跨restart，第二actual fill才父完成/outcome一次；跨query generation重复no-op。名单来自完整quota fixture，无生产资格。

## 最终验证与边界

- 本次独立执行provider58、warm14、funding61、Stage174旧22、account旧25全部GREEN。
- 进一步allweekly343（包含上述周线组件和provider→runtime聚合/恢复）GREEN；共享execution_ledger_cycles63 GREEN。去重口径343+63+22+25=453项；不把重复单独跑的58/14/61再次加总。
- Python compile及git diff --check GREEN。逐命令输出、hash、受测integration源SHA见同前缀manifest.json/unittest.txt。
- CAPTURE_SOURCE_FILES从V5的5增为6（直接执行ledger语义依赖）；CAPTURE_AUTHORITY_SOURCE_FILES从12增为13。parent负责发行全传递closure与fresh production qualification；不改旧proof，不把candidate材料source和最终productionHEAD混写。
- 尚缺真实最终production registry/两类实际readonly/native capture源链/银行TransferSerial样本及accepted最终cashflow day-close statement parser。load_cashflow_day_close仍具体missing_statement；fixture/clock/rawSHA不能替代。没有实际成交、到账或生产激活E2E通过结论。
- 本轮无金融结果增删，期末权益、收益、回撤、Sharpe、滑点、交易次数、胜率/PF均不适用。资金V3 initial-observation source与schema字节维持原1745合同。
- 最终交root/独审后锁源；继续工作应基于真实证据或复现bug，避免无限增加接口需求。

## 反思

- 运行前/后过拟合：否，只修真实订单拆分、证据和恢复合同，没有按历史收益调参数。
- 运行前/后继续价值：是，此闭环是避免父订单提前终态/重启重复成交的必要条件；下一步价值在独审和真实资格/日结证明。
