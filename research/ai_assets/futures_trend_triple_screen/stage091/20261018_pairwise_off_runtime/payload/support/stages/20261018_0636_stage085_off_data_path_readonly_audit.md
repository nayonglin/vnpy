# Stage085：OFF 实际请求数据通路只读接线审计

- line_id：`futures_trend_triple_screen`；2026-10-18 06:35 CST；独立于084 runner实现。只读已有源并写本文/085证据，不实施wrapper，不启动provider、金融或模型。
- 核心结论：**旧044/048/052/037/041/051 CLI main不能直接接新OFF账户；必须新增显式owner/scope适配层。资格算法和021/022通道可复用，不能只换driver的PID参数或给旧provider传fixture-root。** 这些是新入口待接通边界，不是把旧B专用工具追认为有bug。
- root已明确固定新账户root：`outputs/stage065_pairwise_off_account`，只有A_OFF/B_OFF、每臂attempt1。只读检查时新root及新runner文件尚不存在；没有新PID或金融已启动的声明。runner最终SHA、真实PID/lstart及实际run_context须随后按真实084终态绑定，不能现在填虚构值。

## 硬编码实际阻断点

| 源/位置 | 直接复用main会怎样 | 新scope必须适配什么 |
| --- | --- | --- |
| 044 第20—25、47—54行 | WAIT锁旧036/B_TS；engine_identity只允许PID21822、旧runner名称/--run/固定SHA | 新arm精确wait_root、新runner SHA、真实owner PID+lstart/命令、run_id；每轮verify及publish都检查同owner |
| 044 第141—178、215—250行 | provider只许旧037/041路径；041角色由path==旧PROVIDER判断；只有reader/resolver能以flags选新源 | root新allowlist要显式family角色与新provider/reader/output，不按旧basename推断；保留全部SHA/终态/批次计数 |
| 037/041 第28行及read_request/prepare/preflight/worker | actual request父目录必须旧B_TS/data_wait；fixture_root虽能读新root，但会写fixture_scope=True，worker拒运行 | 新真实root reader、packet owner/output/preflight与新worker自身身份；不能假借fixture开真实连接 |
| 052 main 第291行及045 original_provider | 最早调用冻结037.read_request，因此新root先被拒；provider选择仍返回固定旧037/041，即使换reader flags也无效 | 新current-request reader及provider binding投影；仍复用固定045/052数据验收helpers，不修改原globals/源码 |
| 048 第23—49、90—105行 | 只认旧037/041模块SHA和OUTPUT；随后旧read_packet/read_request再次复核旧root | 新provider source/output/packet/current-request绑定及独立新review输出；其完成/聚合/R-E/M/021 parser逻辑保留 |
| 051 frozen_inputs 第109—114行 | 既调用旧037 reader，又直接读旧REQUEST_ROOT/audit | 若未来真实缺daily raw，须新owner-aware普通daily scope；旧051不具新owner main参数，不能伪称已通 |

044.current_request虽有wait_root参数，但prepare/run/publish都直接按默认旧WAIT调用；不构成现成通用main。037/041.read_request的fixture_root只可作为测试边界，不能给真实worker放行。052.validate051_origin对**旧缓存origin**仍必须保留旧037路径验证；不能为了读新current request把旧origin的归属改写为新OFF。

## 最小适配层与确定接口

单一建议是新增一个OFF真实scope层，把driver、current resolver、provider scope和independent delivery reader这四个角色绑定同一个不可变owner manifest；底层仍调用冻结012 collector/018 budget、037 packet_targets/choose_daily_reference/qualify_target、041 reviewed_exact_daily、045 Review/recover_daily/qualify_local、052 request_key_scope/assemble_delivery/普通raw来源核验以及原021/022。仅迁移必要scope入口控制流，不复制金融runner、修改SDK或给旧模块运行时改globals后仍声称旧身份。

下面是**待新wrapper实现的边界接口合同建议，不是已存在API**：

```python
read_actual_request(owner, request_path, request_file_sha256) -> current
resolve_actual(owner, current, *, provider_bindings) -> result
prepare_packet(owner, current, *, family, packet_index=0,
               daily_review_path=None, daily_review_sha256=None) -> packet
review_packet(owner, packet_dirs, terminal_sha256s) -> accepted_result
publish_reviewed(owner, current, receipt_path, receipt_sha256) -> pointer_evidence
```

`current`固定含真实request/path/file_sha/digest及原fingerprint；`owner`只取root冻结身份，不由resolver决定。CLI保持现有resolver `--request/--request-file-sha256`、provider `--prepare/--request/--request-file-sha256/--packet-index`及可选daily-review对、run `--run/--packet-dir`、reader `--packet-dir .../--terminal-sha256 ...`的结果契约，新增prepare时显式`--owner-manifest/--owner-sha256`。packet保存owner原件路径/SHA及完整input fingerprints；run只读packet重验，不靠额外runflags改preflight。driver按新的root绑定四个path/SHA，不执行resolver任意返回的文件。

resolver仍只返回：accepted（request_sha256/receipt_path/receipt_sha256）；needs_provider（request_sha256/packet_count=1/provider_path/SHA/reviewer_path/SHA，exact_daily时另daily_review_path/SHA）；blocked必须非0。保留原1—8实际需求/单packet边界，不扩理论上界。新binding显式`family=original_daily|exact_daily`；新driver不可沿用“任何不是旧041的路径都按037”的判断。reader输出继续原`stage021_independent_minute_delivery_v1`及accepted parse_result，不创造放宽的交付schema。

新scope最少绑定以下字段，后续工程师不得自行猜测：

1. account_arm、attempt1、run_id、root固定account_output、wait_root=account_output/data_wait；runner绝对path与最终SHA、preflight/run_context/execution-readiness绝对path及SHA；021/022/新scope源码与协议SHA。新源必须进入实际account InputRecorder闭包，首次消费后保持immutable。
2. 真实engine_pid、ps -ww lstart+完整args、精确新runner/--arm A_OFF或B_OFF/--run及readiness身份；每次循环/启动provider前/发布前重验，PID复用或换arm拒绝。新PID须真实启动后由root观察并绑定；不能先伪造owner。代码准备配置可先冻结，实际owner另在真实等待后绑定。
3. provider path/SHA、family、provider output、reviewer path/SHA/output、resolver path/SHA；source inventory及raw缓存origin白名单、每个实际使用对象SHA。packet/terminal/receipt也绑定该owner，不把新文件藏在旧provider family身份下。
4. 保留022 wait=1800/run=7200、044每batch至多4条新provider连接、driver原840—3600批预算与启动前至少840秒reserve、provider570/600父子预算和单次attempt/无自动retry。driver预算不能延长engine原时钟；启动连接还须有当前wait/全run的有效余量。若新wrapper自动接普通daily，daily连接也占该batch4条；不得藏成额外免费连接。没有daily scope时准确blocked needs_daily_raw，不能fallback或宣称全路径齐数。
5. 061固定manifest=`outputs/stage061_accepted_wait_delta/ccc4a13cbc8e4691af41a16916c659f2/manifest.json`、SHA`48bc356b8723c4ae7104f7055ad8480de31fffb7fca6f115b537152eafc7900f`；081review=`outputs/stage081_accepted_wait_dataset_review/review_receipt.json`、SHA`8cca4707388f9b957b77117f11370183b98f89c7a810e550d4f7a753d782daaf`。190实际commit/44614精确键及anchor/full权限是已审范围，未来缺口没有自动资格。

021 canonical request**没有arm/run_id**，因此两账户可能payload相同而同digest。新decision/packet/review/journal必须按owner+run_id再分request_digest目录；不可让旧052全局request_digest输出或044 existing_binding误当新owner已处理。raw缓存可共同只读。request schema/digest算法保持原样，owner在外层manifest绑定，不为隔离修改021请求。

mutable audit.json/journal只作当前live状态读取，不能把其不断变化的整文件当immutable receipt source，造成后续account末尾inputguard自相冲突；应绑定immutable request/fingerprint/owner/packet/终态/receipt等真实消费对象，审计状态仍照原022推进。

## 实际请求到原021的完整链

1. 新084按每臂实际账户启动一次；A原native普通订单走真021，B原035/028合法条件intent以OPEN stub提前请求完整D，未触发也须资格。021按真实active batch合并实际requirements，不下载理论日期上界。
2. 原022 FileWaitResolver在对应arm/data_wait写request、fingerprint和waiting audit并开始原1800/7200时钟。新driver只读该真实最后等待，核owner、schema、canonical digest、文件SHA及exact absolute path，不创建假request。
3. 新resolver按原优先级：原CSV/013approved优先；不足时仅引用013/040/已root真实exit0的051绑定raw，对当前实际目标重新独立DB六字段+合法id/time后继，DB closeOI仍N/A。旧rejected、已有实值冲突、缺后继不能被新源救；origin与新目标日分开记。
4. local只验实际R：full完整canonical grid及七值日聚合/完成后继；anchor只第一分钟七值合法、真实后继、daily open/可用openOI，明确不授full。多symbol全wanted集合必须一次齐备；部分local只留审计，有一个缺失就按整个实际request交provider，不能签partial整单。
5. R/E/M维持E⊆R、M⊆R且R-E⊆M；交付数据仍等于整R。A0新键disjoint只核R-E，不声称审者重载比较旧值。最后真实021在**所有symbol commit前**用np.array_equal逐项比较重叠七值；旧值有任何真实冲突仍拒绝，绝不覆盖或改mapping。新scope不得删此门或为旧价四舍五入。
6. 真provider仅常规SDK/原collector。新driver的Popen communicate/wait真实returncode0及原parent/worker真0/inputs不变后才可写tool-terminal观察证据；已有attempt无终态/失败不推断完成、不重试。独立reader核provider/preflight/parent/raw/evidence/daily七值/精准scope后签receipt，不写engine response。driver复核receipt全部源SHA及真实021 parser，重新确认同owner/current path/fileSHA/audit仍等待该request，再原子发布stage022_delivery_pointer_v1。
7. 原022再绑定pointer/receipt/输入闭包返回QualifiedDelivery；原021 ensure七值比较、原子append及权限更新。只有data_qualified_appended才算commit，pointer accepted或provider成功不算。失败保持原目录和无完整金融结果，不能重启旧036或延长当前计时。

## 缓存可复用与191限界

已有request-scoped source是**可重新验收的数据来源**，不是新owner资格。旧052 main只枚举002/011固定source_manifest及013/040/051日线raw；它没有通用遍历037/041旧packet completed raw的local cache reader，也不能直接消费新root。新scope若要减少重下，须对白名单旧packet/旧local delivery分别保留原origin request、独立receipt/terminal（确有网络的来源）、raw与completion evidence SHA，再对当前R按同算法重新资格；不能把“已有同合约文件”当完成证明。多个source同key真冲突仍拒绝，不挑较有利值。

最后191包没有061继承/旧B commit权，仍必须排除061overlay与rights。其已独立资格的345完成值及原真实来源证明可以在未来新的真实request重新审查，不能直接搬原191 receipt/request identity、response、data_qualified_appended标记；075临时fixture wrapper严格不在可消费source/receipt白名单。source859隔离后实际E/M很可能不同，须让真021自行生成新request；不得手写新request迎合旧receipt。

## 冻结字节、判断与后续

旧044/048/052/045/047/037/041/051、012/018、021/022及全部已消费协议/receipt/source保持原字节；不修改原021 strict gate，不改sdk授权/collector/570/600，不重写旧B失败或191末包，不回写旧manifest加入新OFF。新wrapper、协议和来源清单由root一次冻结，并纳入新OFF inputs；新增未审family不能自动引用。精确十源SHA及AST接口行号见085 audit_evidence.json，均仅源级小文件读，不是全市场数据重资格。

本次剩余事项是root取得084最终runner身份后实现上述新scope并作一次有限接合接受；没有声称任何新wrapper已实现/已运行、数据集已齐或新金融可启动。原OUTPUT固定不再待猜；最终runner SHA/实际owner PID是执行时真实绑定项。未增加策略alpha或预算。

新增/修改/删除参数与回测结果均0。期末权益、收益、最大回撤、Sharpe、滑点、交易次数、胜率均N/A。测试/金融/provider启动/网络/训练/预测/外部订单0；不读PnL，不改084/LINE/registry，不stage/commit。

开始及结束过拟合判断：否，按既定数据资格与owner机制审查，不依收益选参数。继续价值：是，明确的旧scope阻断会使未来正确账户无法补真实缺口，此审计给出一次性最小接通边界，同时保留严格完成/旧值门。沿062/083既有官方调研，不按本次禁止网络范围重复联网；资料方法不能证明alpha或市场数据普遍正确。
