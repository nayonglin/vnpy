# Stage146：固定EMA等待身份与三代运行时接合

- line_id：`futures_trend_triple_screen`；2026-10-18 10:11—10:24 CST；非重要突破，无新alpha/参数/金融资格。
- 依据root140计划和144采纳，读取143分钟量边界；沿138已读registry/LINE与官方TQ/GitHub调研，继承121/123判断。本次没有新增策略idea、外搜、质量重认证或feature重算。
- 唯一源码所有权：新增 `tools/stage140_ema_wait.py`、`tools/test_stage140_ema_wait.py`；仅新增本记录与 `outputs/stage146_ema_wait_integration/`。不改145作者的checkpoint/runner/auditor/三个测试，不改旧源、LINE、registry或Git；不派子agent。

## 已实现的接缝与复用边界

1. `BoundAsset/EmaRun`仅引用145维护的 `stage140_ema_checkpoint.py`，没有复制第二份类型。新 `EmaOwner/ActualRequest`、`observe_owner/load_owner/current_request/resolve/drive/bootstrap_runtime` 固定 `EMA_LIMIT/stage124_ema_limit_v1`，attempt1、新schema、`stage140_ema_account/EMA_LIMIT/<run_id>` 与本run的 `data_wait`。
2. owner逐次核真实PID/start/argv、context/preflight/readiness/integration review、source/data闭包、原1800/7200限额和actual argv选择的preflight/readiness SHA；context保持其started_at。只有root观察真实活进程、已签实际readiness后才能 `observe_owner`。公开owner/drive/provider/worker/resolve拒fixture；明确fixture纯binding/离线probe不被当金融授权。旧B、跨run、换source/owner/request、非最新waiting与过期wait拒绝。
3. 新wait不调用087 `Owner.verify/load_owner`、109 `owner_inputs/bootstrap_from_env`、旧金融/provider CLI，不把自建对象装成B。数据侧复用045/052/041/051纯数据原语、087 `Bindings/_raw_local_proofs/_proofs`；新身份下自行编排local/cache→确缺daily/minute单packet→独立reader→原021 parser→原子022 pointer。缓存只继承实际exact full/anchor权利，root显式cache列表与实际readiness一致；旧owner只可作为已封存数据的来源绑定读取，不能作为新执行owner。
4. provider只调用原087 `sdk_preflight/_daily_worker/_minute_worker`；保留实际SDK/auth/endpoints guard与原collector/七值算法。worker不签review/response；真实父/worker/terminal成功后由另一reader进程检查完成性、真实daily七值与021合同，再由driver再次核current request并原子发布。
5. 保留soft570/hard600、provider余量840、wait1800/whole7200、每批≤4连接、每packet一次、无自动重试。journal在启动前持久化增加connection，不回减；失败或已有无terminal packet保持fail-closed，不通过重试抹掉失败。
6. 每代新wait子命令都先走自己的stdlib bootstrap：真实022冻结数值模块→真实本机SDK3.10.2选择；仅复用109无owner假设的 `endpoints/sdk_identity`。保存真实PID/ppid/argv、数值模块路径/版本、SDK路径/源SHA与runtime manifest/interpreter sidecar。driver自身也先bootstrap，不能只有child正确而parent在021发布时误入数值栈。运行时实际生成sidecar在run的 `data_runtime`，最终金融审计须另按实际文件闭合；不声称preflight已知道未来sidecar SHA。

143的数据单位边界原样保留：原TQ volume不缩放，`V>=q`为已固定研究近似；本次没有用七值相等重新授予单位或queue/部分成交证明，没有改变127撮合。

## 唯一组合方法与真实TDD终态

采用 `test-driven-development/executing-plans`，按144限界只跑新增方法，不执行技能默认的Git/worktree、旧全suite或额外microreview。共享接口在实施前与145作者对齐；ledger见 `execution_ledger.json`。使本方法失败的实际生产变化包括：省略新namespace/source/request/时钟门、让生产路径接受fixture，或让任何一代回到错误SDK/数值路径。

命令固定：`.py311/bin/python -m unittest discover -s research/lines/futures_trend_triple_screen/tools -p test_stage140_ema_wait.py -k test_owner_request_and_runtime_descendants -v`。

| 实际chunk | 终态 | 说明 |
| --- | --- | --- |
| `b5c864` | exit1，预期RED | 新wait尚不存在，明确断言缺EMA typed owner/runtime适配 |
| `832e88` | exit1，环境阻断 | `ps`读取本测试真实子进程被沙箱拒绝；未伪造PID/argv，未到runtime probe |
| `115800` | exit0，1方法/4.311秒 | 同离线命令经自动审查允许所需进程读取后GREEN |
| `e36b4a` | exit0，1方法/4.157秒 | 增补sidecar持久化后的同方法检查 |
| `19cdda` | **exit0，1方法/4.150秒** | 最终父进程bootstrap、真实失败terminal保留及闭包收口后的GREEN |

微型子进程是真实fixture进程，持有真实新schema/context/readiness，但 `issued_by=fixture_only`、`financial_execution_authorized=false`；只在纯binding检查中接受。生产 `observe_owner/load_owner/drive` 及provider/worker/resolve CLI实际拒fixture。原B/跨run/owner SHA/source/request bytes/跨run request path/过期wait/endpoint poison均实际拒绝。

末次三代真实PID为 **66701→66706→66709**，各代ppid等于上一代PID；SDK版本均3.10.2，实际package为本机`.py311`，五类数值模块均来自冻结site。原 `sdk_preflight` 的实际版本/endpoint检查通过后，在读取凭证的下一条真实语句前由trace停止；未改guard、版本字符串或distribution。`sdk_imported=false, credentials_read=false, network_calls=0`；该probe明确不声称完成了读取凭证后的完整SDK preflight。

末次8份manifest/interpreter/probe terminal sidecar按原bytes归档于 `fixture_runtime_sidecars/`，manifest SHA `3b85d6f3ee7252d799ba9463cfef5bf0ed42adf58f48089254ae73bf0d4a1a4e`。归档保留原真实临时路径作为证据，不能拿fixture sidecar当未来金融runtime。较早GREEN证据保留，不抹掉RED或沙箱阻断。

## 交接与未覆盖边界

- 最终wait源SHA：`c313e92058e516f089951bdbde3ba8a0a0fa00f0025911e72de9ac536dc39e8b`。
- 最终test源SHA：`c207f3c2b6f8281dbda6667cbe4c8bc8050f8dd0adb30f081d90b4f33a2ea0ef`。
- `finite_test_evidence.json` SHA：`499d923d4df871c067ac1b5548a34059bfd50d39eb36e6beb351680bf45d4192`；最终命令终态在 `actual_terminal.json`。
- 两源已冻结并把写入权交145作者；由145按144统一四方法组合GREEN/compile一次，再由root安排一次整体独审。146不另派review或重跑旧109测试/127六方法。

**这次真实验证覆盖fixture身份/request拒绝与离线runtime，不覆盖真实local/cache数据resolver、prepare、provider、review/publish或完整金融账户。** 这些分支已按实际旧函数签名实施，但本阶段没有启动它们，不能将单方法GREEN说成真实数据通路或金融readiness。后续必须受整体源码审查与root当时真实preflight/readiness/活进程owner约束；实际生产/数据权限仍false。139/141/142已接受数据产物由root接收，本次没有重认证、重新下载或构建features。

## 变更、绩效与反思

新增/修改/删除策略参数均0，新增/修改/删除回测结果均0；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均 **N/A（未运行）**。fixture-only测试不计金融attempt；本次金融/provider packet/网络/凭证读取/CTP/邮件/推送/部署均0。

开始/结束新增过拟合判断：**否**，只接收益前固定的身份、源和预算，不按PnL或品种年份救参；历史选择偏差仍在。开始/结束继续价值判断：**是**，实际错owner/错request/错runtime反例已可拒绝，为统一入口审查提供必要证据；不等于alpha、目标完成或真实金融ready。146工作到此交接，等待145/root后续整合。
