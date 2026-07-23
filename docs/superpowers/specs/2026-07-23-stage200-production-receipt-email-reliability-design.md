# Stage200 C9/15万生产 receipt 与失败邮件可靠性设计

## 1. 状态与决策

- 日期：2026-07-23
- 研究线：`futures_trend_stage819_intraday_rules`
- 当前生产口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 决策：采用方案 B——修复三个已验证根因，并在现有 Stage945/Stage947 前置边界增加幂等、脱敏的失败邮件。
- 用户确认：2026-07-23 明确选择方案 `B`。
- 过拟合判断：否。本设计只修生产控制面、指标退化值和通知可靠性，不修改 alpha、资金、价格、手数、止损或重进场逻辑。
- 继续价值判断：是。三个缺陷已经分别阻断 daily receipt、盘后报告和月检，且造成应有邮件缺失。

## 2. 现场事实与根因

### 2.1 Stage901 首日 cohort 无法发布

2026-07-23 是当前 production shadow 冷启动首日，权益序列只有一个观测值。Stage650 `_sharpe()` 对该序列使用 `std(ddof=1)`，结果是原生 Python `float('nan')`；现有 `std <= 0` 判断无法识别 NaN。

Stage901 在发布 canonical cohort 时使用 `json.dumps(..., allow_nan=False)`。严格 JSON 正确地拒绝了 `decision.current_variant.sharpe = NaN`，导致 Stage909 无法完成 shadow refresh，也无法签发当天 daily receipt。

根因不是行情缺失、信号逻辑或 pending order 逻辑，而是单样本统计指标缺少退化语义。

### 2.2 Stage922 冷启动超过 60 秒

Stage922 本应只解析最新已完成交易日，却在模块顶层导入 Stage173、TqSdk、vn.py、完整策略配置链、Plotly、回测引擎和 main-contract 元数据链，并扫描约 18.3 MB、341,882 行 mapping。

已复现同一代码首轮约 66.13 秒、缓存后约 2.09 秒。Stage945 的 60 秒上限因而在重启后的冷缓存场景触发。`subprocess.TimeoutExpired` 又未转换为 production typed error，Stage947 最终输出 raw traceback 和 exit 1，没有进入结构化 fail-closed 通知边界。

根因是控制面绑定了重型研究运行时，不是交易逻辑本身需要 60 秒以上。

### 2.3 Stage935 混用了 control root 与 data root

Stage947 为生产子进程注入私有 `OFFICIAL_LIVE_OUTPUT_DIR`。Stage935 将该目录同时用于自身 lock/report 和 Stage173/182/183 数据资产；但三个数据任务实际固定写入 stable checkout 的 `backtest_outputs` data root。

现场中私有 control root 的四个依赖文件均不存在，共享 data root 的文件均存在；Stage173 summary 已是 `max_saved_date=2026-07-23` 且无失败。Stage935 因读取错误目录产生了虚假的 stale/missing blocker。

### 2.4 失败发生在正常邮件所有权移交之前

Stage947 目前依赖 Stage907、Stage929、Stage935 在业务流程末尾发送正常邮件。今天的 receipt invalid 和 target resolver timeout 都发生在这些脚本启动前，因此没有邮件。

Stage935 则已经发送“AI池月更需处理”邮件后以非零状态退出。若 Stage947 对所有非零退出无条件补发，会产生重复邮件。

## 3. 方案比较

### 方案 A：只修三个直接根因

优点是代码最少。缺点是下一次前置资格、receipt 或 resolver 异常仍可能没有邮件，不能闭环“任务失败但用户无感知”的问题。

### 方案 B：根因修复 + 前置失败幂等通知（采用）

在不改变 launchd 标签、调度和进程生命周期的前提下，修复三个根因，并在 Stage945/Stage947 尚未把邮件所有权移交给下游脚本时发送一次安全失败通知。

该方案覆盖 2026-07-23 的真实失败，避免 Stage935 重复邮件，同时不把本次修复扩展成生产调度重构。

### 方案 C：Stage947 supervisor + 独立 watchdog

将 `execve` 改为受监督子进程，再增加独立 watchdog，可覆盖下游脚本接管后崩溃等更广故障。但它会改变信号处理、退出码、launchd KeepAlive 和终止传播语义，生产改动面过大。本阶段不采用。

## 4. 设计原则与不变量

1. 保持 C9/15万唯一生产口径，不改任何策略参数。
2. 保持 Stage948 管理的 7 个 `c9-production-live-*` LaunchAgent、调度时刻和标签不变。
3. 保持 Stage945 -> Stage930、Stage947 -> Stage907/909/929/935/946 的入口关系和现有 `os.execve` 所有权移交。
4. 保持 Stage901 `allow_nan=False`；不得用非标准 JSON、历史权益回填或恢复旧 shadow 起点规避首日问题。
5. 所有异常继续 fail-closed；失败邮件不构成交易授权，也不得改变任何 gate 结果。
6. 单元、集成、并发和性能 smoke 不得连接 CTP；最终 production qualification 只允许沿用正式 runner 的两次 CTP 只读账户/持仓采集，且 send/cancel/order API 必须精确为 `0/0/0`。任何阶段均不得调用报单或撤单 API。
7. production release 变化后，旧 qualification、activation 和 daily receipt 不得继承；必须重新生成并绑定新 commit/tree/manifest。

## 5. 组件设计

### 5.1 单样本 Sharpe 退化语义

修改 Stage650 shared `_sharpe()`：

- 计算样本标准差后，若 `not math.isfinite(std)` 或 `std <= 0`，返回 `0.0`。
- 空序列、单观测序列和零波动序列均得到有限、中性的 Sharpe `0.0`。
- 正常多观测序列的公式和结果不变。
- Stage901 strict serializer 保持不变，继续作为其他非有限值的 fail-closed 防线。

不通过把 NaN 转成 JSON `null` 作为唯一修复，因为这会隐藏指标语义缺陷；也不放宽为 `allow_nan=True`。

### 5.2 轻量 production live context

新增 `qmt_roll_official_live_lightweight_context.py`，该模块仅使用 Python 标准库，并集中提供 Stage922 所需的：

- `OFFICIAL_LIVE_VERSION`
- `OFFICIAL_LIVE_ALIAS`
- `OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE`
- stable `DATA_ASSET_DIR`
- env-aware `CONTROL_OUTPUT_DIR`
- env-aware `SIGNAL_INPUT_DIR`
- Stage901 summary、Stage173 summary/status、main-contract mapping 的 canonical 路径

现有 `qmt_roll_official_live_config.py` 从该模块 re-export 相同 identity 常量，避免两套常量漂移。轻量模块不得导入 pandas、TqSdk、vn.py、Plotly、回测模块或 candidate strategy config。

### 5.3 Stage922 轻量日期解析器

Stage922 改为从轻量 context 获取 identity 与路径，并使用标准库 `csv`、`json`、`datetime`、`pathlib` 完成：

- mapping 的 `date` 列读取、去重和最大交易日判断；
- Stage173 status 的 `max_date` 与目标日覆盖率统计；
- Stage173/Stage901 JSON 摘要读取；
- 冷启动日前目标、data refresh 和 shadow refresh 判定；
- evidence CSV、summary JSON 和 Markdown 报告写入。

输出字段、resolver status、交易日来源语义和 `order_api_called_count=0` 保持兼容。输入资产始终来自 data/signal root，Stage922 自身 evidence 始终写 private control root。

Stage945 继续保留 60 秒上限作为最后保险，并显式捕获 `subprocess.TimeoutExpired`，转换成稳定 blocker `production_launcher_target_date_resolver_timeout`。Stage947 将 resolver typed/raw 失败统一转换为 `production_support_target_date_resolver_failed`，不再泄漏 traceback。

### 5.4 Stage935 路径分离

Stage935 明确使用两个根目录：

- `CONTROL_OUTPUT_DIR`：Stage935 自身 lock、run summary、latest summary 和 report。
- `DATA_ASSET_DIR`：Stage173/182/183 summary、eligibility、combined eligibility 和 mapping。

`STAGE182_COMBINED_ELIGIBILITY_PATH` 必须与 canonical `OFFICIAL_LIVE_AI_ELIGIBILITY_PATH` 完全相同。Stage173、Stage182、Stage183 三个现有数据生成器不修改其输出路径。

Stage935 不再从 `run_qmt_alignment_backtest` 导入 `OUTPUT_DIR`，避免再次把研究运行时的 env-aware control root 当成数据资产根。

### 5.5 前置失败通知 helper

新增 `qmt_roll_official_live_failure_notify.py`，职责仅为生产 launcher 的 best-effort 失败通知：

- 输入只接受 `job`、`boundary`、稳定 blocker code、调度日期/时段和可选 release commit。
- subject 固定为 `[C9/15w][生产任务失败][<job>] <blocker>`。
- body 仅包含任务、边界、稳定 blocker、时间、短 commit、`send/cancel/order API=0`，并明确“正常信号邮件未生成，不能解释为无交易信号”。
- 不附加文件，不接受原始异常、命令、环境变量或 CTP/SMTP 凭证。
- `job`、`boundary`、`blocker` 均按 allowlist 清洗和长度限制；未知异常只映射为稳定的 `*_unexpected_failure`。
- helper 内部捕获自身所有普通异常，返回结构化结果，绝不能改变原任务的 fail-closed exit code，也不能递归调用自己。

### 5.6 幂等与冷却

失败通知状态固定写入 private control root 下的
`qmt_roll_official_live_failure_notification_state.json`，锁文件固定为同目录的
`qmt_roll_official_live_failure_notification.lock`。状态文件与锁文件要求：

- `fcntl.flock` 串行化；
- 临时文件 + `os.replace` 原子更新；
- 文件权限 `0600`，父目录沿用 production private root 的 `0700`；
- fingerprint 为 `release-or-unknown + schedule-date + job + boundary + blocker`。

同一 fingerprint：

- `sent` 或 `dry_run_written`：本调度日期永久抑制重复发送；
- `send_failed`、`disabled`、`blocked_missing_config` 或 helper internal failure：30 分钟冷却，避免 launchd 高频重试造成邮件风暴；冷却后允许下一次自然重试；
- 并发调用最多只有一个调用者获得发送资格。

helper 在持有文件锁时完成“检查旧状态 -> 写入 reserved -> 单次调用 mailer -> 写入最终状态”的状态迁移。若进程在发送期间崩溃，`reserved` 按 internal failure 使用 30 分钟冷却；不通过无锁的“先发后记”换取表面上的低延迟。

SMTP 不提供 exactly-once 事务，因此本设计承诺“进程内和重试场景的幂等/冷却”，不声称网络故障下严格 exactly-once。

### 5.7 Stage945/Stage947 通知所有权

Stage945：

- Stage930 `execve` 成功前，任何 typed 或归一化 unexpected failure 由 Stage945 调用失败 helper。
- `execve` 成功后，Stage930 继续拥有会话生命周期；本次不改 supervisor 语义。

Stage947：

- `day-close-readonly`、`postclose-report` 在 `execve` 成功前失败：Stage947 发送 fallback。
- `postclose-precompute` 没有正常业务邮件；其子进程或 receipt 签发失败：Stage947 发送 fallback。
- `monthly-ai-pool`：Stage947 即使看到非零退出，也先解析 Stage935 最终 JSON。若 `email_result.email_status` 表明 Stage935 已经尝试正常通知（`sent`、`dry_run_written`、`send_failed`、`disabled`、`blocked_missing_config`），Stage947 不再调用同一 SMTP 通道；只有没有到达 Stage935 notifier 时才发送 fallback。
- `health` 维持当前无邮件策略；health 自身失败由既有日志/状态证明。本次不新增 watchdog。

Stage907/Stage929 在 `execve` 成功后的内部异常、Stage930 生命周期监督和独立 watchdog 明确不属于 Stage200；它们需要改变进程所有权或扩大运行边界，应另立设计。

## 6. 数据流与错误流

### 6.1 16:35 postclose-precompute

1. Stage947 校验 stable release、qualification 和 canonical paths。
2. Stage909 运行 Stage173 与 Stage901。
3. 单日 `_sharpe()` 输出 `0.0`，Stage901 strict JSON cohort 成功发布。
4. Stage947 校验 Stage909 summary 和最新 resolved target。
5. Stage947 签发绑定当前 release 的 daily receipt。
6. 任一步在正常邮件所有权之外失败，Stage947 best-effort 发送一次失败邮件；交易仍保持 fail-closed。

### 6.2 16:55 postclose-report

1. Stage947 调用轻量 Stage922，正常冷启动不加载研究/回测栈。
2. resolver 返回 target 与 evidence；receipt 必须匹配当前 release 和 target。
3. 校验通过后 `execve` Stage929，由 Stage929 生成正常信号邮件。
4. resolver/receipt/qualification 在 `execve` 前失败时，Stage947 发送 fallback，明确“未知是否有信号”。

### 6.3 18:20 monthly-ai-pool

1. Stage935 自身状态写 private control root。
2. Stage173/182/183 依赖从 stable data root 读取。
3. Stage935 先生成 summary/report，再按既有 policy 发送业务邮件。
4. Stage947 根据最终 JSON 判断邮件所有权；已尝试则不重复，未到达 notifier 才 fallback。

### 6.4 20:55/日盘生产会话

1. Stage945 使用轻量 resolver 和现有 release/receipt/broker gates。
2. 任何前置 blocker 继续拒绝 CTP/订单链路，并发送一次失败邮件。
3. 所有 gate 通过后仍按原设计 `execve` Stage930；价格、手数、止损和重进场不受 Stage200 影响。

## 7. 测试设计

全部实现遵循 red-green-refactor，先提交能复现当前缺陷的失败测试。

### 7.1 Stage901/Stage650

- 单观测权益的 Sharpe 必须 finite 且等于 `0.0`。
- 空序列、零波动序列必须返回 `0.0`。
- 固定多日样本结果与修复前一致。
- 用真实 `_metrics()` 构造首日 `current_variant`，Stage901 strict cohort publish 成功；summary 中 Sharpe 为 `0.0`，audit seal 最后发布。
- 注入其他未知 NaN 时 strict serializer 仍必须失败，证明没有放宽 JSON 边界。

### 7.2 Stage922

- 在独立子进程导入 Stage922 后，`sys.modules` 不得包含 `tqsdk`、`plotly`、`vnpy_portfoliostrategy`、Stage173 builder、`run_qmt_alignment_backtest` 或完整 backtest runner。
- 使用固定 mapping/summary/status fixtures，验证交易日、节假日、冷启动日前目标、requires data/shadow refresh、coverage 与当前语义一致。
- mock `subprocess.run` 抛出 `TimeoutExpired`，Stage945 必须转换为稳定 typed error；Stage947 必须输出 `blocked_fail_closed`、exit 2 和三项订单 API=0，不得输出 raw traceback。
- 验证 source files 位于 data/signal root，evidence outputs 位于 private control root。
- 性能只作为 qualification smoke 记录，不用脆弱的秒数断言代替依赖边界测试。

### 7.3 Stage935

- 注入 private `OFFICIAL_LIVE_OUTPUT_DIR` 后，Stage935 自身 lock/report/summary 位于 private root。
- Stage173/182/183 路径仍位于 stable data root；combined eligibility 等于 canonical AI eligibility。
- private root 为空而 data root 有合法 fixture 时，不得产生虚假 Stage173 stale 或 `current_stage182_outputs_invalid` blocker。

### 7.4 失败通知

- receipt invalid：Stage907 未启动，fallback 恰好一次。
- resolver timeout：Stage929 未启动，fallback 恰好一次。
- precompute/receipt 签发失败：fallback 恰好一次。
- Stage935 `email_result=sent` 后 exit 2：不得补发。
- Stage935 未到 notifier 就失败：必须补发。
- mailer 配置读取、SMTP、audit 写入分别失败：helper 不递归、不改变原 exit code。
- 相同 fingerprint 串行和并发触发只允许一个发送者；新日期、不同 job 或不同 blocker 可发送。
- 注入 CTP password、SMTP password、AuthCode 哨兵，subject/body/metadata/stdout/email audit/失败状态不得包含哨兵。
- 状态和锁文件权限为 `0600`；原子替换后内容可解析。
- 所有邮件测试使用 mock 或 dry-run，不发送真实测试邮件。

### 7.5 回归与资格

- 运行受影响测试文件和全部 production asset/launcher/email 测试。
- 运行全量离线测试、并发重复启动测试、100 轮 fork/lease/CAS 压力测试。
- 运行静态编译、shell、plist、tracked-file、release manifest 和 secret scan。
- Stage922 进行一次干净子进程冷启动 smoke，记录依赖集合和实际耗时，但只把依赖集合设为硬门槛。
- 代码与独立 review 通过后，最终 production qualification 才运行两次正式 CTP 只读采集；必须使用 `ctp_live.local.env` 与正式 framework，且 send/cancel/order API 精确为 `0/0/0`。
- 独立 agent 全面 review 代码、数据路径、并发幂等、秘密保护、退出码和 fail-closed 语义；合入门槛为 `P0=0`、`P1=0`，P2 必须逐条说明是否影响生产正确性。

## 8. 发布与验收

1. 在独立 `codex/stage200-production-reliability-repair` 分支实施和验证。
2. 生成 Stage200 中文阶段记录，不运行策略回测，不伪造回测指标。
3. 独立 review 通过后，本地合入 `master`。
4. 对新 master 重新生成 qualification bundle、release manifest 和 activation receipt；不得复用旧 receipt。
5. 通过 Stage948 原子更新 stable production root 和 7 个 LaunchAgent，不手工复制 plist。
6. 由 canonical support launcher 生成新的 Stage901 cohort 与 daily receipt；在 receipt 有效前 production session 必须继续 fail-closed。
7. 只读核验 stable HEAD、manifest、qualification、activation、7/7 plist、daily receipt、最新 launcher 状态和 `send/cancel/order API=0`。
8. 除 production qualification 内建的两次正式 CTP 只读采集外，不进行其他 CTP 通路操作；不进行真实报单、撤单或 1 手 smoke。

## 9. 成功标准

- 单日冷启动 cohort 可用严格 JSON 发布，Sharpe 为有限值 `0.0`。
- Stage922 不再加载研究/回测/CTP 重型依赖，且所有日期解析语义回归通过。
- Stage935 在 private control root 下运行时仍能正确读取 stable data assets。
- 今天的两类无邮件失败——receipt 前置失败、resolver timeout——均会产生一次脱敏 fallback；Stage935 已发邮件场景不重复。
- 所有故障路径维持 fail-closed 和订单 API 精确 `0/0/0`。
- alpha、资金、下单价格、手数、止损、重进场和调度时刻均无 diff。
- 新版本只有在 qualification、manifest、activation、daily receipt 全部绑定同一 commit 后才可被 production session 使用。

## 10. 明确不做

- 不调整 alpha 或任何策略参数。
- 不将 shadow 起点改回 2026-07-22 或更早，不回填、不追历史理论仓位。
- 不增加 supervisor/watchdog LaunchAgent，不改变现有 `execve` 生命周期。
- 不通过延长 Stage922 timeout 掩盖重型依赖。
- 不发送真实测试邮件；离线测试不连接 CTP；除正式 production qualification 的两次只读采集外不做其他 CTP 操作；任何阶段均不调用报单/撤单 API。
- 不把“SMTP 接受邮件”表述为“用户邮箱必然收到”；生产验收分别记录程序发送结果与外部投递可见性。
