# Stage140：真实 EMA_LIMIT 账户最小接合实施计划

> 后续实施按下列任务顺序完成；只新增本线文件，全部接合后做一次整体独立审查。本阶段仅交计划，未实施、测试或启动账户。

**Goal：**让已接受127组件以真实独立身份完成一次原预算账户、持久化和完整独立验账，优先验证净收益更高且最大回撤更低的目标。
**Architecture：**固定 EMA 一次入口＋typed 身份/快照＋独立等待工具＋独立账本适配；复用实际现有无身份限制的接口，不建设插件框架。
**Tech Stack：**`.py311/bin/python`、原冻结数值环境/vn.py/native847、SDK3.10.2；无新依赖。
**Spec：**124单一定义、126两项语义裁决、127组件、132整体接受、135/137已接受独立159层、139源级继承决定；它们的真实最终SHA在未来preflight绑定。

## 范围、判断与不变量

- line_id=`futures_trend_triple_screen`；2026-10-18 10:04 CST；当前工作区；非重要突破。已读registry和LINE，registry未列既有本线，不建重复线、不改索引。
- 本轮为有界实施接合规划，继承121/123原著/GitHub与138官方TQ文档调研：限价机制值得一次透明证伪，来源存在不等于完成/逐值资格；不新增外搜或alpha结论。
- 选择固定新入口。改旧arm常量/借B owner会破坏接受身份；复制整套065/087/095会放大漂移面，均不选。B2仅列未来可选，不为支持它扩大本次工程。
- 不改任何旧源/旧schema/行情/PnL；不mock真实guard、鉴权或数值runtime。读取旧源的函数级复用须绑定实际SHA，不执行旧main、prepare、owner/readiness、金融CLI或旧金融审计CLI。
- 原期`2020-01-01..2026-10-14`、150000、1641日、月AI10非fu＋固定fu、OFF八键、原recipe/退出/换月/0.5R及一次retry保留；EMA13/26/DAY/一tick/V≥q、错侧gap同母保护且不retry、合法retry可越L沿124/126。
- 原限额完整保留：wait1800、whole7200、provider启动余量840、soft570/hard600、每批至多4连接；不因B超时放宽。旧190独立继承，不合并重存或重审。
- 原B已真实预算失败且无完整raw/seal/summary；不能补成完整绩效。当前累计11attempt/4完整独立accepted、训练0；本轮新增账户/数据/模型/provider/网络调用均0。

## 新增文件与真实接口（以下均尚不存在）

约定`T=research/lines/futures_trend_triple_screen/tools/`；新路径名明确为建议实施名，不冒称已有API。

1. `T/stage140_ema_checkpoint.py`：stdlib引导、固定typed身份和账户文件持久化；定义不可变`BoundAsset(path: Path, sha256: str, bytes: int)`、`EmaRun(run_id: str, attempt: int, global_attempt: int, output: Path, started_at: str, fixture_only: bool)`。
   `start_run(*, preflight: Mapping, readiness: BoundAsset, started_at: str, global_attempt: int) -> EmaRun`；`save_raw(run: EmaRun, payload: Mapping) -> BoundAsset`；`seal_raw(run: EmaRun, raw: BoundAsset, validation: Mapping) -> BoundAsset`；`load_sealed(run: EmaRun) -> tuple[Mapping, Mapping]`；`export_sealed(run: EmaRun, destination: Path) -> dict`；`save_failure(run: EmaRun, partial: Mapping, error: str, phase: str) -> BoundAsset`。
2. `T/stage140_run_ema_account.py`：固定输入准备、薄feature reader、profile/资格/capture接线和一次dispatch；定义`PreparedEma`保存profile/engine、原metadata、已接受层、lookup、recorder、holder及preflight，不进入raw pickle。
   `read_ema_features(manifest: BoundAsset, review: BoundAsset) -> Mapping[tuple[str, str], Mapping]`；`prepare_ema(*, feature_manifest: BoundAsset, feature_review: BoundAsset, delta159_manifest: BoundAsset, delta159_review: BoundAsset) -> PreparedEma`；`capture_ema(engine_class: type, run: EmaRun) -> ContextManager[dict]`；`execute_ema(prepared: PreparedEma, *, readiness: BoundAsset) -> dict`。
3. `T/stage140_ema_wait.py`：只支持本EMA命名空间的真实owner、当前request、独立resolver/reviewer/publisher及原provider子进程runtime；定义`EmaOwner`携真实文件binding/document，`ActualRequest`携request/path/file_sha/digest/wait。
   `observe_owner(run: EmaRun, *, engine_pid: int, process_identity: str, readiness: BoundAsset, integration_review: BoundAsset) -> BoundAsset`；`load_owner(path: Path, digest: str) -> EmaOwner`；`current_request(owner: EmaOwner) -> ActualRequest | None`；`resolve(owner: EmaOwner, current: ActualRequest) -> dict`；`drive(owner: EmaOwner, *, batch_id: str, max_connections: int=4, budget_seconds: int=3600) -> dict`；`bootstrap_runtime(owner: EmaOwner) -> dict`。
4. `T/stage140_independent_ema_review.py`：新身份/终态/raw-export binder＋EMA语义审查＋原独立会计算术；`audit_ema(*, completion: BoundAsset, output: Path) -> dict`。不调用065/095/106整段带旧身份的入口，不生成或改写账户收益。
5. `T/test_stage140_ema_account_integration.py`：只含下面四个组合方法；不复制127六方法或跑旧suite。未来具体源码、测试与计划一起freeze。

## 现有API的可复用范围

- `065.run_profile_once(s901, profile, metadata, *, engine_class, start, end, minute_audit)`没有arm门，真实只调用一次；不复用`build_account_profile/prepare_account/execute_account`及065 checkpoint的旧身份guard。
- `127.build_ema_account_profile(formal, native_strategy, native_engine, *, weekly, fi, next_days, ema_lookup, qualify)`真实存在；027旧weekly/FI2/next_days继续经031原reader，不重算。新feature仅按139/141/142实际接受cache解析，不能再次调用EMA build或在运行期补指标。
- `022.InputRecorder/capture_actual_settings/capture_engine/FileWaitResolver/whole_run_budget`、`031.build_execution_clock/actual_trade_identities/read_reused_A0/read_reused_anchor/temporary_reused_anchor/ordered_predicates/build_qualification_callback`可按原合同接用；OFF用065 policy实际check函数。
- `061.load_accepted_delta/temporary_accepted_wait_delta/append_equal_only/compose_qualification`复用数据容器、等值七值与分权数学；135只兼容DATA schema，真实builder/旧B来源及新独立资格必须另列，不调用061旧terminal freeze。
- 087的`Owner.verify/load_owner`、109的`owner_inputs/bootstrap_from_env`均硬绑旧065/099，不能用新身份直接调通；新wait实现本EMA的严格等价门。只复用无owner假设的087 `Bindings/_proofs/_raw_local_proofs`、provider `sdk_preflight/_minute_worker/_daily_worker`及其045/052/041/051数据原语；不把自建对象塞进087整段orchestration绕owner验证。
- 109的`endpoints()/sdk_identity()`可复用；新bootstrap照原路线先`022.configure_runtime`并加载核实冻结数值模块，再将本机site优先选择真正SDK3.10.2。新scope/provider每代子进程都先bootstrap，保存真实PID/ppid/argv/模块路径/版本/源SHA sidecar，不改旧109或sitecustomize。
- 065纯export使用的`canonical_trade_enums/attach_trading_dates/build_execution_clock`与原650 `_metrics`可复用；新checkpoint自行验证真实EMA类/identity/schema，不把EMA写成B_TS。
- 095的`pure_functions/module`支持冻结函数读取；沿其030 `audit_inventory/reconstruct_metrics/reconstruct_episodes`、033 `identity_audit/serialized_csv_sha/use_raw_positions_once`及106 `signal_day/adapt_exports`复用原独立数学。030母链函数的`CONDITIONAL`在独立函数namespace显式绑定真实`stage127_ema_limit_initial_primary`，不改raw price_source；不调用旧B `ordered_evidence/b_artifact_review`冒充EMA审查。

## 按序实施任务

- [ ] **任务1：固定输入与scope。**137已实际接受159层，root交接receipt `outputs/stage137_off_wait_delta_independent_review/review_receipt.json` SHA `b3fbb16d219484bdac9329e6c4f12db18a3b762de3adbea7b79710c79f8dee68`、manifest `563556d9a70a4f841f606e6b668c6422ae11c7f28f0dcc9203451c20ab2e694a`；按原061loader使用，不另造layerloader。等141/142日线与固定feature实际接受后，thin reader从同一已hash bytes解析严格bool/有限数值与唯一`(asof,contract)`，按manifest解析source_ref；核真实合约、u/D/tick、资格receipt/DB/日历/127源绑定，不补值、不重复全keys到每行。缺feature保持unknown；缺绑定或类型非法fail-closed。
- [ ] **任务1 scope准确顺序：**base＋原stack各overlay（含002）＋016修正→原两anchor→原061190→071隔离剩余unqualified source859→实际append新135159。`completed_keys`供071只含隔离之前已接受证明，不提前借159救旧859；进入scope后再触发实际minute load，确保wrapper调用顺序正是上述数据顺序。
- [ ] **任务1 权利：**原inherited predicates→031两anchor分权→061190 compose→135159 compose，分别传各层真实`newly_appended_keys`；159的full/anchor权利由其新receipt精确授予。原190不重存；旧七值有差立即失败，不能调整scope顺序吞冲突。
- [ ] **任务2：独立身份与capture。**固定`account_id=EMA_LIMIT`、`mechanism_id=stage124_ema_limit_v1`、primary；新root为`outputs/stage140_ema_account/EMA_LIMIT/<run_id>/`，attempt=本机制1，global attempt由root真实总账签入。新schema前缀`stage140_ema_*_v1`，不借旧B目录/owner/readiness。
- [ ] **任务2 接线。**`capture_ema`只作用于本次127工厂返回的新engine class；在真实`add_strategy`返回、任何bar前设`strategy.ema_limit_run_id=run_id`并核未成交，确保真实economic_mother_id有run。复用原capture，再显式保存`ts_decision_audit/ts_fill_audit/ema_limit_execution_audit/ema_limit_final_budget_audit`、新scalar pending及实际TradeData的mechanism/mother字段；原031 capture/pending projection会漏EMA字段，不能原样套用。
- [ ] **任务2 持久化。**preflight、实际类、原完整参数/OFF实际策略、数据closure/feature manifest、所有新旧源与测试/协议binding一次freeze并留源快照；run刚返回立即save_raw，再核1641日/全部settings/参数/分钟/输入不变后seal，再纯export。raw保留原native经济frames与完整审计表，拒engine/history/model对象；沿原065 `_account_only`路径精确guard，不以字段名白名单大放行。
- [ ] **任务2 失败。**engine未完整返回只留partial＋cause/真实终态，绩效N/A；已raw而validate失败不能seal；export失败只可从同一sealed raw导出新目录，禁止重跑账户替代。export-only在任何行情/native/model加载前dispatch，零金融调用。
- [ ] **任务3：owner/等待/runtime。**owner只能由root观察真实活进程后签实际PID/start/argv、run_context/preflight/readiness/integration review及工具源闭包，启动等待工具前每次重验。current request必须属于本run/data_wait最新waiting记录且canonical/file SHA吻合；跨run/换request/fixture/旧B身份均拒绝。
- [ ] **任务3 最小数据路线。**新wait只编写身份/路径/编排胶水：复用上述原语做local/cache exact取证；确缺才准备一个实际daily/minute packet；provider独立worker不能签review/response。真实terminal→独立completion/七值/021 parser审查→再次核当前request→原子pointer；receipt保持原021数据合同但写本EMA真实owner/provenance。所有子命令从新wait bootstrap，不能递归旧087/109 CLI。
- [ ] **任务3 限额/归档。**durable先记connection再启动，原570/600/840/1800/7200/4不变；每packet一次、不自动重试；原SDK/auth/endpoint guard实际执行。runtime manifest/interpreter/parent/worker/terminal/receipt均保存，最终金融receipt绑定实际运行产生的这些sidecar闭包；不谎称启动前已知未来sidecar SHA。
- [ ] **任务4：独立账本。**真实账户跑完由独立agent执行`audit_ema`并review结果/数据/逻辑/置信度/bug，非作者自签。绑定root真正tool terminal/exit0、context、raw/manifest/seal、export成功和freeze；逐表核raw-export同一账户，再沿原独立算法重建现金/库存/逐fill佣金滑点、逐日权益、开放MTM、retry/roll母链与指标，余额残差原容差不变。已知0佣金/日收盘保证金非分钟峰等限制公开继承。
- [ ] **任务4 EMA证据。**单独核intent/setup唯一消费、DAY失效、u冻结L/S/q与最终gross/no refill、实际F/tick/穿透量条件、预测/实际风险margin差、错误侧R=N/A同母保护双成本且无retry、合法retry可越L、首分钟双consumer屏蔽。fill_price从真实execution audit按order_id与native trade逐值核对后供原母链函数；不得由fill_audit缺字段补造价格或把初开标签改为B。
- [ ] **任务4 判定。**A0与已接受A_OFF均保留强对照和原限制；只有本EMA完整独立accepted后才作双目标判断，不能仅赢较弱A_OFF就达标。主口径通过后仍须124已固定悲观反证、成本/多起点与生存门；不靠事后改参数救结果。

## 四个有意义组合测试与一次整体review

未来仅用新增测试文件；各方法先确认预期RED，再同方法GREEN，命令统一`.py311/bin/python -m unittest discover -s research/lines/futures_trend_triple_screen/tools -p test_stage140_ema_account_integration.py -k <方法名> -v`，最后一次整体独立代码/接口review，不循环micro review、不重复旧suite。

1. `test_layer_order_and_exact_rights`：tiny真实loader有旧坏859与159合格替代，按序隔离后等值append成功；故意把159提前则冲突；原190不变，full/anchor不扩权，异常finally恢复cache/loader。
2. `test_owner_request_and_runtime_descendants`：明确fixture-only的实际微型子进程/PID/argv/新schema通过纯binding检查，真实drive/provider CLI仍拒fixture；跨run、旧B、owner或request毒化拒绝。三代离线probe证明冻结数值与真正SDK/原guard路线，凭证/网络前停止；不伪造1641日或fixture=false。
3. `test_native_return_raw_seal_export_and_recovery`：tiny真实127/native执行一次包含已成/未成、不同母单的gap和retry路径，run_id先注入、capture字段齐；原native现金/成本与新完整审计一致。故意错误validation先拒seal，再用正确fixture validation封同raw；注入export错误只从同一sealed raw导出新目录，native run仍一次；export-only毒化prepare/native/model加载使误入即失败。
4. `test_independent_ledger_and_ema_evidence`：从测试3同一tiny sealed raw独立验账，含普通持仓/roll接点及EMA母链；更改成本/库存/母ID/执行价/未知类型或非法R任一拒绝；无修改的合法gap N/A及retry越L通过。检验实际账本与metadata，避免再写一套定价/PnL oracle。

## root需裁定的实质事项与进入条件

- 建议下一账户直接固定EMA primary；B_OFF第2次仅在root认为确需隔离第三层因果时另发新attempt，复用本数据层而非恢复失败账户。本次不强制多臂、不实现B2枚举或再造runner。
- `V>=q`需要D分钟volume为真实单边手数的来源语义。138的日线源盘点没有证明这一点；root须核是否已有可继承vendor/source证据并绑定，若缺只补这一语义证据，不能用七值相等推导单位，也不要求重审全历史价格。
- 第一次financial_run必须等实际159/feature资格接受、上述实际代码/四测试与一次整体review、真实preflight闭包后root readiness；当前不建arm/readiness。139已裁定源级继承与lc公告时点，常规接口/路径/原子落盘选项由实施者按本文确定，不再提审批问答。

## 本阶段结果与反思

- 只新增本文；新增/修改/删除策略参数=0，新增/修改/删除回测结果=0。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A；未改LINE/registry/memory/back_log/Git。
- 开始/结束新增过拟合：**否**，仅把收益前固定机制接到真实身份、数据和独立账本，不看PnL选口径或扫参数；既有研究选择偏差仍保留。
- 开始/结束继续价值：**是**，四个固定接缝直接决定能否取得完整可复验金融证据；本计划已足够实施，不继续规划泛化框架或无限审查。目标active未达成，financial_ready=false、production_qualified=false。
