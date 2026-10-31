# Stage016 同actor会话执行接线与最终数量门

- line_id：futures_weekly_short_ma_slope_gate；记录时间：2026-10-31 20:02（北京时间）。
- 工作区：/Users/mac/.codex/worktrees/weekly19-official-20261031/fian。
- 状态：CANDIDATE_SOURCE_REVIEW_ONLY；production_qualified=false。固定Stage014工程迁移，非重要突破，不改alpha或风险参数，不运行金融回测。
- 本阶段不操作Git/index、生产目录、CTP连接、SMTP、订单或转资。root保留正式发布、master与安装所有权。

## 调研与判断

沿用既有SOP、迁移合同和此前核对的VeighNa官方OffsetConverter/PortfolioStrategyTemplate语义。复用原931的订单转换、实际native API、幂等/CAS、quota、撤单、offset和回报链，不新增sender或daemon。当前任务是工程正确性，不筛收益参数，不构成过拟合；值得继续，因为未接通的Backend stub、启动锁反转和旧数量静默放行都足以令固定策略执行不正确。

## 实际接线

LocalEvidenceBackend.publish_execution已移除session_controller_binding_not_installed stub。首次只在真实production source/manifest/qualification/activation/daily receipt、私有context、原生产runtime路径、provider typed私有ledger、durable bundle与真实Runtime身份、已验行情代次全部匹配时，调用公开build_weekly19_session_service。参数显式weekly19-15w-r150k、production-live/live、原931 serve/live-real，使用原确认常量与原环境闸门；JSON不能注入sender、runner、qualified或gateway能力，也不替调用方设置实盘env开关。

- prepare_session(target_date, now)：在任何read-only连接前验source、receipt、registry、私有ledger和source-pinned forward calendar。CLI先验实际session_end，窗外直接拒绝。
- publish_execution(runtime=..., bundle=..., data=..., now=...)：首次创建真实bridge/service，之后必须仍是同一个actor；不每秒恢复392k历史或重建AM。
- execution_session_cycle(target_date=..., now=...)：active shortcut复用同actor和bridge.last_bundle/data；只改pipeline的session函数，不碰root支持/邮件流程。
- close_session()：原service bounded stop；stop_pending时保留owner，停止成功后才close bridge。关闭的owner不能原地恢复。
- CLI设置绝对context_file。无显式target时调用root resolver按已验calendar/15:00完成日动态解析；health/禁用AI保持cached target，不联网。
- CLI原duration与实际session截止取min，作为process-local deadline绑定原runner.stop_requested，且实际readiness授权expiry不超过该deadline；不新增timer线程。

并发warm线程可能执行真实API，Backend顶层API计数因此明确unknown(None)/evidence_complete=false。纯controller的0另存controller_publication_order_api_called_count，不把pure publish的0冒充整个服务0。

## Source authority与现金引用

Controller required最小源码闭包已增加session bridge、runtime、pipeline state、data/update、quote/spool、context update、backend/pipeline、daily receipt、funding/store、warm/broker evidence、advice/report、official config、session clock和CLI。它仍验生产release-manifest.source_commit等于实际production HEAD；material source单独记录，未放宽原451/Stage179身份门。

context语义digest覆盖全部字段，仅cash_sources排除。每poll及cash reconcile受控private_json重读，除cash_sources外canonical内容必须完全相同；现金字段仅为待核对source references，仍逐条由真实provider与fundV2验原始来源，绝不凭路径或Balance变化虚拟到账。profile、risk、source、registry/ref、market/target或release变化会撤当前process-local authority；即使文件改回也需新owner，不恢复当前actor授权。

## 锁、时钟与数量门

1. 原service外层actor_lock会与connect lifecycle lock及callback ingress形成锁反转。现在publication mutex只串行producer；同一actor_lock只保护actor/prepare/store，真实query与transport/readiness probe均在锁外。CtpExecutionSession新增nonblocking connection_ready：startup未完成即warming，让原生durable replay取得actor锁。
2. 原readiness TTL仅3秒，原风险proof可能约3.9秒；controller在fresh context/risk工作之后取得实际readiness，并重新取真实时钟。最终API gate同样在fresh provider返回后采样真实时钟，不用开始前时间把新source误报future。未延长原TTL、25秒quote deadline或静默续期原trace。
3. 最终API门不能只看gate.allowed：签100而当前risk只50时必须拒绝，不能gate返回50却仍发100。对子单也核原immutable parent的总remaining cap，防100→50拆成25手绕过。
4. actual_fill_lifecycle由bridge读取已被runtime接纳且逐条semantic核对过的provider原始Trade envelope；business与delivery的approved/filled/remaining守恒、唯一trade IDs、current durable state均要匹配。225批准、真实成交100、当前实际child125且当前risk125时，纯数量门可通过；若请求仍225则拒绝，绝不修改实际payload来冒充缩量。
5. provider _VerifiedExecutionBindings是身份投影，不能当作含event_type/status的完整执行事件。新gate显式识别真实private reader的typed list：只有实际当前lease/payload/service/connection、quota batch ID、完整expected childset/hash、immutable parent与signal全部一致的自身batch可继续；旧delivery、旧batch、错lease/generation、childset变动和退化为普通list都拒绝。原普通完整ledger事件的严格语义保留。

931 transport新增process-local字段weekly19_immutable_parent_intent、weekly19_current_physical_child（实际converted OrderRequest）、weekly19_current_physical_batch（真实quota的api_slot_batch_id/weekly19_batch_manifest/reservation checksum）。不预填未发送child的broker ID，不把原parent业务close覆盖实际closeToday/closeYesterday。

## 必须保留的边界

同batch first native Trade已推进actor，但原同连接四query positions仍是成交前快照时，不能在最终API槽内另起查询破坏watermark，也不能伪造updated positions。桥owner补的真实顺序反例返回weekly19_requires_source_reconciliation:broker_strategy_position_mismatch；停止新增child，原cancel duty继续，待物理batch退出后真实query/来源对账。quote durable_state仍严格，不增一般state-advance豁免。

因此上述partial125测试只证明在完整当前来源证明下的数量守恒，不证明旧query快照下同batch自动继续。未发/unknown child不使父计划terminal；需要来源对账/受控恢复的分支仍blocked，不宣称自动生产恢复已完备。

root报告真实TD/MD TCP preflight均Timeout，尚无实际可验样本；TransferSerialCollector有实现但每周/暖查询自动producer尚未安装，vendor最终cash day-close parser未接收实际statement格式。仍缺真实现金连续性、实际capture、全clean source selected、独立review、不可变release/qualification/activation及master/install。不得用fixture、actualBalance变化、旧资格或已锁V6整文件SHA替代。

## 验证与证据

12个定向套件：194 tests / 17.125秒，OK，日志20261031_stage016_execution_execution_integration_final.log。覆盖本阶段最终gate/physical identity、native callbacks、service、Backend/CLI、controller、真实离线bridge、pipeline/store/context、原Stage179 executor serve；fixture条件来源和原生字典均明确标注，非生产资格。预期negative CLI参数用例会打印usage。

新锁、缺连接warming、风险100→50、拆子绕过、225→100实际fill→125 remaining、typed quota映射、immutable context改回仍撤权、slow proof后readiness、source后时钟、CLI动态target、窗外先拒、deadline与stop_pending等均保留RED→GREEN日志。14个owned源码/测试compile与全行trailing whitespace检查通过。当前931七个quota/native/deferred关键函数AST与18:57 manifest逐项相同；18:35 V6原整文件未取证，不声称全文件相同。精确SHA、artifact列表和AST关系见20261031_stage016_execution_session_manifest.json。

新增/修改/删除参数仅工程接口，无策略参数。新增/修改/删除回测结果均无；期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率均N/A。运行后过拟合判断仍否；继续价值为完成受控来源/可靠性验证，不能把工程绿灯变成金融或生产资格。
