# Stage193 Stage372/20万接入 Stage179 执行可靠性链与 no-submit 资格闸门

## 基本信息

- 改动时间：2026-07-19 00:00 CST
- 研究线：`futures_trend_stage819_intraday_rules`
- 当前模式：day/night 共用的盘后预计算与会话执行适配
- 工作区：`/Users/bytedance/Desktop/person/vnpy_stage179_live_reliability`
- 分支：`codex/stage179-live-execution-reliability`
- 基线提交：`699210f61`
- 阶段性质：正式 Stage372/20万执行适配、最终 K 线意图预计算、语义资格闸门与离线可靠性验收
- 是否重要突破版本：否。这是执行可靠性里程碑，不改变 alpha；当前只具备 no-submit 合入候选条件，尚不具备 SimNow 或实盘激活条件。
- 是否触发 A/B：否。没有产生新策略版本，也没有调整 Stage372 的入场、止损、重进场、AI 池、选品、资金或仓位参数。
- 实盘边界：未安装、加载或启动任何新增 LaunchAgent；未连接 CTP/SimNow，未调用真实报单或撤单 API，真实 `send=0/cancel=0`。

## 外部调研与判断

- 参考 vn.py 官方 `BaseGateway`、`EventEngine` 与 CTP gateway 实现，确认行情时间应在 gateway 入队前采集，策略与持久化 I/O 不应阻塞行情线程：
  - <https://github.com/vnpy/vnpy/blob/master/vnpy/trader/gateway.py>
  - <https://github.com/vnpy/vnpy/blob/master/vnpy/event/engine.py>
  - <https://github.com/vnpy/vnpy_ctp>
- 同时复核本线 Stage152 输入重建审计：旧 `tqsdk_main_contract_mapping_2020_2026_04.csv`、旧日线数据库/AI/pairwise 快照和 Stage149 执行代理 detail 当前无法复原；旧提交配当前输入也不能复现冻结收益。
- 我的判断：Stage179 的入口时间、持久化、租约/CAS、故障恢复和预计算改造具有跨品种、跨周期价值，可按 no-submit 方式合入；但 Stage372 策略语义资格必须失败关闭。不能用当前重建回测冒充 Stage435 冻结基准，更不能通过调 alpha 参数贴历史曲线。

## 本次变更

### 新增

- 新增 Stage372 冻结影子配置，绑定 `stage372-20w`、`official_live_stage372_20w_recovery_sleeve`、20万元与恢复袖套覆盖，不引入任何 C9 的 0.5R 实时止损/重进场逻辑。
- 新增 Stage372 最终 K 线事件导出器，独立导出 canonical pending orders、trade events 和 entry candidates，订单 API 始终为 0。
- 新增 16:35 盘后预计算 LaunchAgent 定义，只运行数据刷新、Stage372 决策和 pending audit，不运行 CTP preflight、账户 gate 或 executor；文件仅入库，未安装/加载。
- 新增 `OFFICIAL_LIVE_SIGNAL_INPUT_DIR`，把盘后只读信号输入与每个会话的 runtime/output 目录隔离。
- 发布清单升级到 schema v2，新增 `execution_profile` 与 `strategy_semantics_qualification={status,evidence_id}`；语义未通过时只允许 `offline/production-readonly`，禁止 `simnow/broker-test/production-live`。
- 新增 Stage372 预计算、execution profile、release manifest、launchd 隔离与失败关闭回归测试。

### 修改

- Stage659 支持显式 `--execution-profile`，Stage372 决策补齐 profile、version、capital 和 capital label，避免下游身份门因字段缺失误拦截。
- Stage260/902/903/905/909/930 使用 profile 绑定的 pending path；Stage930 仅显式 C9 profile 才启用 C9 detector fast lane，Stage372 保持 dormant。
- Stage909 支持 `latest-completed`，Stage372 顺序固定为数据刷新、决策生成、pending audit，并使用当前解释器避免 worktree 缺失 `.py311`。
- Stage914/931 在 CTP preflight 与提交边界校验 execution profile；profile、资金、版本或语义资格任一不一致均失败关闭。
- Stage372 day/night plist 使用隔离 runtime/output 与共享只读 signal input，不改变现有调度时间，且未部署。

### 删除

- 删除 Stage372 走 C9 detector、C9 0.5R 实时止损/重进场和 C9 15万口径的隐式路径。
- 删除 controller 对 Stage372 `profile_input_refresh_not_implemented` 的永久阻断；由独立盘后预计算链提供最终意图。
- 未删除或修改任何策略 alpha 参数和正式历史基准。

## 参数变化

- 新增参数：`--execution-profile stage372-20w`、`--target-date-mode latest-completed`、`OFFICIAL_LIVE_SIGNAL_INPUT_DIR`、release manifest `strategy_semantics_qualification`。
- 修改参数：Stage372 资金/版本身份显式固定为 `200000/20w` 与 `official_live_stage372_20w_recovery_sleeve`；会话 output/runtime 改为互相隔离。
- 删除参数：Stage372 对 C9 profile、15万资金和 0.5R detector fast lane 的隐式继承。
- 策略参数变化：无。

## 回测/归因参数

- 数据区间：2026-01-01 至当前可用日线（诊断复跑）；冻结比较点为 2026-06-09 Stage435 记录。
- 账户规模：200,000。
- 成本口径：沿 Stage372/Stage435 既有口径，不改滑点。
- 样本过滤：不手工挑选 JM 或其他品种；只比较冻结记录和当前输入重建结果。
- 策略/归因口径：只诊断输入可复现性，不把当前重建曲线晋升为正式基准。

## 回测结果

### 冻结 Stage435 期望基准

- 期末权益：`204,470`
- 总收益：`2.235%`
- 最大回撤：`-16.3027%`
- Sharpe：`0.3314`
- 总滑点：`1,580`
- 总交易次数：`23`
- 胜率：`45.4545%`
- JM 关键事件：`jm2609.DCE Short Close 2 @1360`，原因 `long_prev2day_stop`

### 当前可用输入诊断复跑

- 期末权益：`172,030`
- 总收益：`-13.985%`
- 最大回撤：`-25.502%`
- Sharpe：`-1.183`
- 总交易次数：`34`
- 总滑点：本轮临时诊断产物未保留稳定 artifact，不作为候选指标。
- 胜率：本轮临时诊断产物未保留稳定 artifact，不作为候选指标。
- 关键差异：未复现上述 JM pending event。
- 结论：当前结果与冻结基准显著不一致，原因落在 Stage152 已确认的历史输入快照不可复原；发布清单必须标记 `blocked`，当前结果不得覆盖或修改正式回测结果。
- 新增回测结果：仅新增上述诊断对比，不形成新正式候选。
- 修改回测结果：无。
- 删除回测结果：无。

## 执行可靠性验证

- 精确执行回归：`650 passed, 243 subtests passed`，覆盖 28 个 Stage179/Stage372/Stage930/Stage931 执行模块，耗时 `69.79s`。
- 60 秒性能门：20 合约、2000 tick/s、共 120,000 tick，`17/17` 检查通过；ingress p99/max `0.021541/0.449666ms`，EventEngine sentinel p99/max `0.749416/1.413875ms`，durable lag p99/max `62.999750/103.937958ms`，drain `0.054907s`，RSS 增量 `44.734375MiB`。
- 性能证据：`/tmp/stage179-stage372-performance.*`；gate SHA-256 `24db1027cbe65bb9c078d8c8713f5f10c7d192ac6bacbf45cc0f26085baf457f`，ticks SHA-256 `0822ec5b8a136a9f0dedf3d7404e92def438e833c3b8725d1b8bd9818536ed21`。
- 故障门：24 个故障场景、100 轮 API-slot fork race、100 轮双 executor process race 全部通过；每轮最多一个发送赢家/一次 fake physical send，真实 `send=0/cancel=0`。
- 故障证据：`/tmp/stage179-stage372-fault.MkjQee`；process race SHA-256 `e8a6bc3207d08d723035d515209500bca303ec7f52f068c2b3b6da3b027e6688`。
- plist：3 份 Stage372 plist 均通过 `plutil -lint`；修改/新增 Python 通过静态编译；`git diff --check` 通过。
- Stage909 plan-only：正确解析最新已完成交易日 `2026-07-17`，profile/资金/命令均为 Stage372/20万，未运行命令、未连接 CTP、未报单。

### 2026-07-19 00:08-00:26 独立终审与 P1 修复

- 冻结 HEAD `31d2793a6` 的独立 Agent 终审结果：`P0=0、P1=4、P2=5`；代码合入、production-readonly、SimNow、production-live 均判定 NO-GO。
- P1-1 身份缺失：Stage260 原来允许 summary 的 version/capital/label 全缺失并反向注入 Stage372 身份。修复后强制 `execution_profile/version/capital/capital_label` 四项全部存在且精确匹配；全缺失、部分缺失和错 profile/version 均失败关闭。
- P1-2 旧 pending 重标日期：新增 schema v1 pending cohort audit；cohort 精确绑定 target date、profile、version、capital、official summary、signal plan、current positions 与 pending CSV 的 SHA-256。CSV 使用临时文件、fsync、rename 发布，audit 最后发布；Stage260/902/905/909 全链校验同一 cohort，decision 和 intent 必须携带相同 trade date/cohort。
- P1-3 语义资格自签：当前分支硬拒 Stage372 的任何 `passed + simnow/broker-test/production-live` manifest；公共 builder 和 loader 两侧均失败关闭。未来只有引入专用、可验证资格证书后才允许另行改代码放开。
- P1-4 不可变清单：旧清单不复用；P1 修复提交后必须重新从干净树生成 Stage372 no-submit manifest。
- 同时关闭 P2 的 Stage914 旧 C9 口径：Stage914 改为显式 execution profile，Stage903 精确透传 Stage372/C9 profile；Stage260 审计来源改为 `stage372_pending_order/stage372_signal_plan`。
- 修复后执行回归：两组共 `657 passed, 245 subtests passed`；新增缺身份、旧日期 pending、cohort 交叉、Stage372 自签 passed、原子发布和 Stage914 profile 测试全部通过。
- 修复后 60 秒性能门：20 合约、2000 tick/s、120,000 tick，`17/17` 通过；ingress p99/max `0.090917/2.217292ms`，EventEngine p99/max `2.327750/6.642583ms`，durable lag p99/max `72.243000/96.236291ms`，drain `0.054519s`，RSS 增量 `44.406250MiB`。证据目录 `/tmp/stage179-stage372-p1fix-performance.52VB0L`，gate SHA-256 `b641af1adfdd1703bc56f8dbe2f159d1f97dfa9d4d44476fd63333fc4b2fdd56`，ticks SHA-256 `af2cad5f8f24deba0ef553a16a126c5dafecdcc6903a8d0d95b146b452f4c526`。
- 修复后故障门：`3 passed, 24 subtests passed`；24 类故障、100 轮 API-slot race、100 轮双 executor race 全部失败关闭/单赢家。证据目录 `/tmp/stage179-stage372-p1fix-fault.1VFE0D`；fault cases SHA-256 `520ed47c1e6ab812377b5b402c00244234036a4627dc1e282b9a2ef08db433a7`，API-slot race SHA-256 `050280daf729bb08600c4b3d28b70946bd2c03a6c2d6890f56a3336efe5ec8fb`，two-executor race SHA-256 `56db189defcf1fe2f836a4d9f19f0d843a08df6acc999b303548f273eb7b1331`。
- 生产只读 CTP：Stage174 combined gateway 连接尝试在 native teardown 以 `exit 139` 退出且未落完整 summary；随后 Stage655 TD-only 使用正式 env、`0600` 权限与正式 framework 优先运行 35 秒，`send/cancel=0/0`，但 `front_connected/auth/login/account/position` 全部未就绪。summary SHA-256 `6e7c62d82bd8c35c3dc6491dbabadb6231dd01bfa2fd5beaf5c17a58a0b72eb7`。结论为 production-readonly NO-GO，不得继续提交链。
- 修复后不可变清单：由干净 detached worktree 从源码提交 `d113a4bd4065b895f7bed06098abe556fa4b021b` 生成 `release_manifests/stage179/stage372-candidate.json`，schema v2、61 个 critical files、profile `stage372-20w`、资格 `blocked`、仅允许 `offline/production-readonly`；manifest digest `c0dde1dead9d2e00140dd1be4dcde63f2d39c73e7e7a2466bde79f6c03f9363e`，文件 SHA-256 `1969762c185d214d3703876c51cf264a5fe86a44cf6f9f2021b50652d389f0eb`。loader 的 production-readonly 校验通过，SimNow/broker-test/production-live 均拒绝。

### 2026-07-19 00:27-00:48 冻结复审与产物快照 P1 修复

- 独立 Agent 对冻结 HEAD `e5750f6d9` 的 follow-up 结果为 `P0=0、P1=1、P2=3`。前述身份、cohort、语义资格和不可变清单四项 P1 均确认关闭；新发现的唯一 P1 是 Stage260 公共接口可同时接收已解析 DataFrame 与调用方提供的 hash，无法证明“被校验的字节”就是“生成执行候选的字节”。独立 Agent 已用自洽假 hash 加替换信号表复现可执行候选。
- 修复方式：Stage372 的 official summary、signal plan、current positions、pending orders 与 audit 现在由 loader 在 audit-before/audit-after 同一代次窗口内读取为不可变字节快照；按快照原始字节重新计算四个 SHA-256、校验 profile/date/cohort/row identity 后才物化 DataFrame。Stage260、Stage902、Stage909 只消费这份密封快照，不再接受调用方拼接的 Stage372 DataFrame/hash 组合。
- 快照额外绑定五个 canonical artifact 路径，不能从另一组文件加载后换绑到当前 profile；构造器不再作为公共 API 暴露。读取期间 audit 变化、路径换绑、外部 signal DataFrame 覆盖均新增失败关闭测试。
- 修复后聚焦测试：`47 passed, 11 subtests passed`；扩大回归两组共 `661 passed, 245 subtests passed`，其中 Stage179/Stage372 组 `392 passed, 190 subtests passed`，历史 C9/账本/CTP gate 组 `269 passed, 55 subtests passed`。Python 静态编译与 `git diff --check` 通过。
- 本修复不调整入场、止损、重进场、AI 池或仓位参数；没有运行新回测、没有连接 CTP、没有调用报撤单 API。
- 快照修复提交 `513b3028c7baf108a8ab5222158b3fcdeaa9fcb1` 后，从干净 detached worktree 重新生成 61 个 critical files 的 schema v2 no-submit manifest。release id `stage179-stage372-no-submit-513b3028c`，manifest digest `cc88bf26658c3099a1828e818c83247896e2bf705d4528156d4ecbd5a0048533e`，文件 SHA-256 `cf50ce2b530a78f2e2ee983c78efece3e710171b270d2e91aa81ef70c2aa954a`。实际 loader 验证 production-readonly 通过；SimNow、broker-test、production-live 均以 runtime profile 不允许而拒绝。

### 2026-07-19 00:49-01:05 canonical profile 换绑 P1 修复

- 独立 Agent 对 HEAD `245410f5e` 再次复审得到 `P0=0、P1=1、P2=4`。原外部 DataFrame 覆盖攻击已关闭，但复现出公共调用者可用 `dataclasses.replace` 保留 `stage372-20w` 身份、把五个路径改到临时目录，再用同一替代 profile 自签/加载/执行任意信号。
- 根因：上一版证明了“snapshot 与传入 profile 一致”，但没有证明“传入 profile 就是 registry 中唯一的 canonical profile”。修复后公共 loader、materializer 与 Stage260 gate 均将完整 frozen profile 与 `resolve_execution_profile(profile_key)` 的注册实例做精确相等校验；任何身份或五路路径替换均返回 `execution_profile_not_canonical`。
- 新增两条直接复现测试：公共 loader 拒绝预先换绑路径的 profile；即使 snapshot 已在替代 registry 下生成，恢复正式 registry 后 Stage260 也拒绝该 profile/snapshot。测试使用临时 patch registry 隔离文件，不放宽生产 API。
- 修复后聚焦测试：`49 passed, 11 subtests passed`；扩大回归两组共 `663 passed, 245 subtests passed`，其中 Stage179/Stage372 组 `394 passed, 190 subtests passed`，历史 C9/账本/CTP gate 组 `269 passed, 55 subtests passed`。Python 静态编译与 `git diff --check` 通过。
- 本轮仍未运行新回测、未连接 CTP、未读取生产 env、未加载 launchd、未调用报撤单 API。当前 manifest 因关键源码变化必须从本修复提交再次刷新，旧 digest 只作历史记录。
- canonical profile 修复提交 `acbe4825df9266cedf4dc5f59356d7e7725054a8` 后，从干净 detached worktree 再次生成 61 个 critical files 的 schema v2 no-submit manifest。release id `stage179-stage372-no-submit-acbe4825d`，manifest digest `df99726f0c1bb17c5cd7e7e04fbe72d3045c530d09e43d1d6ca80d3ceb3d2d91`，文件 SHA-256 `458e6d069338e5afc8bd341cc3df58c7cbb5ed74da488a16f031e1c83006e545`；资格保持 `blocked`，只允许 offline/production-readonly。

### 2026-07-19 01:06-01:12 最终独立终审

- 最终冻结 HEAD `1f2a7cae211c122af756cbfc80ba60ed13553dc5` 的独立 Agent 结论：`P0=0、P1=0、P2=4`。
- 独立重放外部 DataFrame/hash 覆盖攻击和 `dataclasses.replace` 五路径预换绑攻击，前者无法覆盖密封 snapshot，后者在公共 loader、materializer、Stage260 三处均以 `execution_profile_not_canonical` 失败关闭。
- 独立复跑 49 个聚焦测试全部通过；manifest source `acbe4825d...` 的 61 个 critical files/hash/digest/祖先关系全部通过；当前 HEAD 仅 production-readonly 资格可加载，SimNow、broker-test、production-live 均拒绝。
- 最终四类判断：no-submit 代码与 dormant plist 合入 `GO`；production-readonly `NO-GO`；SimNow/券商测试 `NO-GO`；production-live `NO-GO`。
- 剩余 P2：安装前需创建并校验 Stage372 日志/output/runtime 目录；Stage903 后续应使用唯一 run id 绑定本次 Stage914 结果；尚无真实 20:55 启动至 21:00 decision/submit-ready 的端到端时间戳证据。以上不影响 no-submit 代码合入，但全部属于部署/激活前置。

### 2026-07-19 01:02-01:07 部署前 P2 收口与生产只读复验

- Stage903 串读根因已定位并修复：Stage914 本身会在本次子进程 stdout 输出完整 JSON，但 Stage903 原来忽略 stdout、按 mtime 扫描“最新 summary 文件”，并发或隔离 output root 配置漂移时可能串读另一轮/profile。新增失败测试先复现 stale C9 文件覆盖本次 Stage372 blocked summary；修复后 Stage903 直接解析同一 `subprocess.run` 的 stdout，解析失败即 `_read_error` 并失败关闭。
- 新增 Stage372 LaunchAgent 目录 provisioner。它从 3 份 dormant plist 提取 log parent、official-live output、signal input 和 Stage179 runtime root，只允许 `stage179_stage372` 专属根内路径；默认 check，显式 create 才创建，永不调用 `launchctl`。
- 已在真实部署根创建/校验专属根与 8 个子目录，共 9 个 required directories，全部 `bytedance:staff`、权限 `0750`；重复 create 的 `created_count=0`，最终 check 为 `directories_ready`、permission mismatch `0`、`launchctl=0`、order API `0/0`。三份 plist 仍未加载。
- 发布清单 builder 已把 provisioner 纳入 critical files；对应默认清单覆盖测试先红后绿。
- 修复后扩大回归：Stage179/Stage372 组 `396 passed, 190 subtests passed`，历史 C9/账本/CTP gate 组 `269 passed, 55 subtests passed`，合计 `665 passed, 245 subtests passed`；3 份 plist lint、Python compile、`git diff --check` 均通过。
- 生产只读 guard：`ctp_live.local.env` 权限 `0600`，9 个必需 env key 全部存在且未输出明文；formal trader/MD frameworks 存在并优先于 `.py311/lib`。
- Stage655 TD-only 用正式 env/framework 运行 35 秒，严格 `send/cancel=0/0`，但 `front_connected/auth/login/settlement/account/position` 全部未就绪，状态 `readonly_no_account_margin_received`。summary SHA-256 `6f10c5044ae28abf6c806d9a997940e77784f4f18e99914daa130f179084ca4f`。
- 随后的不打印地址 TCP 探测确认 TD/MD 前置端口均不可达，当前失败根因收敛为周末/外部生产前置不可用，而不是本地 framework、Stage179 执行链或策略逻辑。production-readonly 继续 `NO-GO`，等待交易服务窗口复验；不得绕过只读 gate。
- 本轮没有新回测、没有加载 launchd、没有调用任何报撤单 API。新增关键源码后 manifest 必须从新干净 HEAD 再次冻结，旧 digest 只作历史证据。
- P2 修复提交 `270819ea6837a590302007eaef12e192d5fb74a5` 后，从干净 detached worktree 生成 62 个 critical files 的 schema v2 no-submit manifest；新增 provisioner 已纳入冻结范围。release id `stage179-stage372-no-submit-270819ea6`，manifest digest `4341c58ae238d66f354fe72a54cf6815edb2a356d099f68aa9fd03c77d8bd1a8`，文件 SHA-256 `e1e212e3d90c40f9779f3a72b78cba0447fcb2d9d3aaed1e8423d549fc594cd7`；资格保持 `blocked`，只允许 offline/production-readonly。

### 2026-07-19 01:13-01:21 provisioner 与 Stage914 资格绑定终审修复

- 独立 Agent 对冻结 HEAD `aa810d9e1a60c7d77d9a8a487dd108e9376fc649` 的审查结果为 `P0=0、P1=1、P2=3`。唯一 P1 是目录 provisioner 暴露 `--allowed-root/--plist`，调用者可把 `/Users/bytedance` 等宽根本身加入 required set，并在 create 模式执行 `chmod 0750`；原有测试因只使用临时专属根而没有覆盖该攻击面。
- provisioner 现只允许从模块内固定的 `DEFAULT_ALLOWED_ROOT/DEFAULT_PLISTS` 构造密封 plan，执行前重新解析 canonical plist 并逐项核对 root、plist 和目录集合；公共 CLI 删除 `--allowed-root/--plist`，只保留 `--mode check/create`。任意越界 plist、非 canonical plan 或旧宽根 CLI 参数均失败关闭。
- create 模式新增修复前权限漂移证据 `permission_mismatches_before`，修复后继续报告最终 mismatch；重复执行保持幂等，`launchctl=0`、order API `0/0`。
- Stage903 的 Stage914 readiness 现同时要求：同一子进程 `exit_code` 为严格整数 `0`、summary 为本次 stdout JSON、profile key 精确匹配、official version/capital/capital label 完整匹配、preflight passed 且 blocker 为 0。独立审查复现的 `exit 139 + passed JSON` 和错 profile/资金 summary 均不能进入 ready。
- TDD 聚焦验证 `7 passed`；扩大执行链回归覆盖 `test_qmt_* + test_official_live_* + test_stage*`，结果 `697 passed, 245 subtests passed`，耗时 `74.66s`。Python compile 与 `git diff --check` 通过。
- 本轮没有调整任何 alpha 参数，没有运行新回测，没有连接 CTP/SimNow，没有加载 launchd，也没有调用报撤单 API。由于关键源码再次变化，`aa810...` manifest 已失效，必须从修复提交重新冻结并再次独立审查。
- P1/P2 修复提交 `b1d05d8c8a18b0652b8730e748f401ed3f01bdbb` 后，已从干净 detached worktree 重新生成 62 个 critical files 的 schema v2 no-submit manifest。release id `stage179-stage372-no-submit-b1d05d8c8`，manifest digest `e2abd74d53d7e4d26752db1534209c445a6a956ad027d3cd59ee6ead5bd79c57`，文件 SHA-256 `80f580328ff6b7f2bb42dde64f0b11c1f176394f12930a86233d502400d87e14`；实际 loader 验证 production-readonly 通过，SimNow、broker-test、production-live 均以 runtime profile 不允许而拒绝。

### 2026-07-19 01:22-01:29 最终冻结独立复审

- 独立 Agent 对冻结 HEAD `f98c66054c3967a08d0594670f0e038e622a25a3` 复审结论为 `P0=0、P1=0、P2=1`，没有新的代码合入阻断。
- 审查独立重放旧 `--allowed-root /Users/bytedance` 与 `--plist` 攻击均得到 argparse `exit 2`；密封 plan 在恢复 canonical 默认后拒绝复用。create/权限修复前后证据正确，`launchctl/send/cancel/order API=0`。
- Stage903 只有严格整数 `exit_code=0`、同一 stdout 的有效 JSON、完整 Stage372 profile/version/capital/label、passed 状态且 blocker 为 0 才 ready；`exit 139`、字符串 `"0"`、错身份、错状态、blocker、空或坏 stdout 全部失败关闭。
- 独立 51 项聚焦测试通过；62/62 critical files 唯一且 hash 匹配，manifest digest 与文件 SHA-256 重算一致，source `b1d05d8c8...` 是冻结 HEAD 的祖先；offline/production-readonly loader 接受，SimNow/broker-test/production-live 拒绝。3 份 plist lint、Python compile 与 `git diff --check` 通过。
- 四类结论：no-submit 代码与 dormant plist 合入 `GO`；production-readonly `NO-GO`；SimNow/broker-test `NO-GO`；production-live `NO-GO`。唯一 P2 是可用交易服务窗口下严格 `0/0` CTP 与真实 `20:55→21:00 decision/submit-ready` 时间戳证据。

### 2026-07-19 01:30-02:06 只读 canary 证据契约与延迟资格闸门

- 改动时间：2026-07-19 01:30-02:06 CST；是否重要突破版本：否。这是运行态证据和资格验收收口，不改变策略 alpha，也不把离线通过误写成实盘已启用。
- 新增只读 canary 资格审计器：每个会话必须绑定同一冻结 manifest/source commit、Stage372/20万身份、daemon 与 plist 的双重 runtime/mode/submit-mode、08:55 或 20:55 调度、完整 Stage914/Stage907 只读快照、会话完成状态和显式订单 API 证据。
- Stage608 心跳新增严格整数 `generated_epoch_ns`，每个 watched symbol watermark 新增入口 `ingress_epoch_ns`；Stage930 固化 daemon/cycle 纳秒时间、首个开盘分钟行情入口与耐久发布时间。只读资格要求日盘 09:00、夜盘 21:00 后首分钟内出现行情，`ingress -> durable` 不超过 1 秒，缺时间戳或类型错误均失败关闭。
- Stage903 新增 Stage907 刷新后的只读状态/持仓快照状态，以及 Stage905 的显式 `send_order_api_called_count/cancel_order_api_called_count`。Stage930 对慢控制器、fast lane、warm Stage931 和 post-submit reducer 分源累计 send/cancel，并输出 `order_api_evidence_complete`；任何来源缺计数、fast-lane 异常或 cycle 异常均不能用默认零洗白。
- P1 资格固定要求至少 5 个唯一完整日/夜盘会话、日夜覆盖、全量 `send/cancel/order=0/0` 和一次断线重连。断线重连不能由布尔参数自报，必须绑定同一 session/profile 的旧/新 connection generation、readiness 撤销/恢复时间和该证明自身的 `send/cancel=0/0`。
- 资格 evidence 文件使用只新建、不覆盖的原子写入与父目录 fsync；capture 时重新用当前仓库字节校验冻结 manifest，qualify 时精确绑定 manifest digest/source commit。审计器只读文件，不调用 `launchctl`、不连接 CTP、不导入报单适配器。
- 新增参数：`capture --session-id/--session-date/--session-kind/--scheduled-start-epoch-ns/--disconnect-evidence`，`qualify --session-evidence/--expected-manifest-sha256/--expected-source-commit/--required-session-count`。修改参数：无策略参数变化。删除参数：无正式参数删除。
- 最终扩大回归：`715 passed, 245 subtests passed`，耗时 `68.54s`；另一次相关全组回归 `237 passed, 115 subtests passed`。Python compile、`git diff --check` 与 3 份 Stage372 plist lint 全部通过；环境缺少 `ruff`，因此没有声称 ruff 通过。
- 证据代码提交 `eaa62fa609b2041987132a73d811dcf376d56a5d` 后，已从干净 detached worktree 生成 65 个 critical files 的 schema v2 no-submit manifest。release id `stage179-stage372-no-submit-eaa62fa60`，manifest digest `86ca4ac818d5fef24d5eac0468d66d9d39f72cdad07d9d8f4694836d297e6978`，文件 SHA-256 `127062b96bb26d2cba1b83138ad1a6d8ce1522c34692204699fd71b00f64fd7e`；实际 loader 对 `production-readonly` 校验通过，资格保持 `blocked`，允许 profile 仍只有 `offline/production-readonly`。
- 本轮没有运行新回测；期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均为“不适用/未变更”。没有加载生产 env、没有连接 CTP/SimNow、没有安装或加载 LaunchAgent、没有调用真实报单或撤单 API，真实调用保持 `send=0/cancel=0`。
- 延迟判断：代码现在能机器判定“20:55 是否准时拉起、21:00 首 tick 是否及时耐久、证据是否完整”，并继续沿既有 trace/SLA 判定真实信号到执行的 25 秒 hard deadline；但当前仍没有 5 场真实服务窗口证据，因此不能宣称今天的线上延迟已被运行态证明解决。
- 过拟合反思：否。没有根据 JM 单晚结果或收益曲线调参，只补时间因果、显式证据和失败关闭。
- 继续价值反思：是。下一步价值已经从继续堆离线规则转为冻结 manifest、独立终审和真实服务窗口的严格 0/0 验收。

## 结论与硬门禁

- 代码合入判断：`GO`，严格限定 no-submit 代码与 dormant plist。最终冻结独立复审为 `P0=0、P1=0、P2=1`；合入不等于部署或激活。
- 部署判断：9 个 Stage372 专属部署目录已完成 `0750` provisioning；新增 plist 尚未安装/加载，合入不等于部署。
- 激活判断：release manifest 只允许离线和 `production-readonly`，但实际 production-readonly 仍因 CTP 未就绪而 `NO-GO`。Stage372 语义资格为 `blocked`，SimNow、broker-test 和 production-live 必须拒绝。
- 延迟判断：盘后在 16:35 预计算最终 K 线意图，消除了 21:00 会话启动时现算回测/信号链导致的结构性延迟；但在真实只读 CTP 与运行态时间戳证据完成前，不能宣称已解决线上端到端延迟。
- 后续：可由合入者合入冻结 no-submit 候选，但必须保持所有 plist dormant。待生产前置在交易服务窗口恢复后，重跑 production-readonly 严格 `0/0` CTP；通过后才允许真实 LaunchAgent 20:55→21:00 时间戳 canary。未获得用户新的明确报单授权前，不做 SimNow smoke order。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本轮只治理时间因果、阻塞 I/O、持久化、身份、租约/CAS、故障恢复和资格闸门，没有按单晚 JM 结果或收益曲线调整 alpha。发现历史输入漂移后选择失败关闭，而不是调参数贴基准。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但下一步价值集中在发布资格、独立审查和只读 CTP 证据，不在继续堆离线规则或反复跑不可复现的旧回测。
- 原因：执行可靠性门已形成可复验的跨品种证据；剩余风险是策略语义来源与真实运行通路，边界明确且能用 fail-closed 控制。

## 合入建议

- 是否更新本线 `LINE.md`：否；同线并行按规则只新增唯一 stage 文件，待合入者统一整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否；尚未通过生产只读 CTP 与语义资格，不记为正式实盘候选里程碑。
