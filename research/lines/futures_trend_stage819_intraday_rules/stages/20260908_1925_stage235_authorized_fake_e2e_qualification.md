# Stage235：完整授权链离线 E2E 与发布资格前置审计

- 开始时间：2026-09-08 19:25 CST。
- 研究线：`futures_trend_stage819_intraday_rules`，延续 Stage233/234 的执行安全修复，不新增 alpha 研究线。
- 来源：`codex/live-broker-account-sizing`，开始时 clean HEAD `0a49b904a47937bad9bb45c556fab6ddb3ea303b`。
- 用户完整授权继续推进；授权不是缺失的端到端证据。本阶段继续离线测试和资格准备，不连接真实 CTP、不委托/撤单、不安装或激活自动交易、不更改生产与 master。
- 过拟合判断：否。资金比例、止损、retry、alpha、AI 池和交易门阈值全部不变，没有回测和收益筛选。
- 继续价值判断：是。Stage234 已证明组件和模拟 instrumentation 链路，但完整 `fresh_bundle→send_order` 授权链还未证明，应优先补证据而非绕过门禁。

## 调研与判断

- 上游 vn.py CTP gateway：<https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py>。
- SQLite 原子提交说明：<https://www.sqlite.org/atomiccommit.html>。
- 判断：外部回调、内部状态和持久化不是同一事实，Fake 外部 API 可以验证本地授权链，但不能替代真实账户采集，也不能证明生产已启用。
- 本地 SOP 明确要求不可变 release、clean commit、独立评审、精确受信 runner 和两次正式只读采集。当前完整授权不改变这些技术门。

## 执行计划

1. Aquinas 补实际 warm factory 的完整授权 E2E，只模拟外部 CTP，不手填 native context、不替换内部授权 gate；先报告真实失败，若涉及生产源码由主 agent 决定修复边界。
2. 主 agent 并行审计资格 builder、正式物料和当前发布身份，记录缺失证据及下一步，不运行会连接 CTP 的 builder。
3. 新测试经过独立 reviewer 检查；对实际变更运行相应回归，保存真实失败与成功，不通过放宽时间/风险门获得绿色。
4. 确认源码与证据绑定后保存开发分支；正式物料、master 晋升和生产资格仍按 SOP 单独闭环。真实资金交易启用交由用户操作。

## 参数与回测

- 策略参数新增/修改/删除：均无。
- 回测结果新增/修改/删除：均无；权益、收益、回撤、Sharpe、滑点、交易次数和胜率不适用。
- 初始状态：`offline_authorized_e2e_in_progress_production_not_qualified`。

## 19:27 发布资格前置只读审计

- 生产 HEAD 与远端 `refs/heads/master` 均为 `d492ee072aa5a9d71477235d79f17d2a5db59db3`，生产 tracked clean；本次没有改变它们。
- 新候选顶层配置与旧 m0005 的规则集身份仍匹配，但完整 `active_release_critical_files(require_deployable=True)` 明确拒绝：13 个既有运行/测试文件与旧物料漂移。这是候选代码变化的预期结果，不能把窄范围的 baseline identity 通过误写成新代码已取得物料资格。
- 生产现有 m0005 的完整物料检查通过，262 个关键文件；此结果只证明旧安装物料一致，不证明进程、账户或下一时段可交易。
- 候选 `_production_runtime_identity` 拒绝 `release_builder_production_env_identity_missing`：隔离工作区未复制生产凭证，符合此前离线约束。禁止以开发 runtime 回执代替完整生产 env/runtime 身份。
- 生产 release manifest、qualification、activation audit、daily receipt 均仍绑定旧 SHA；资格生成日为 2026-09-02，最新 daily receipt 为 2026-09-08 16:40:15 CST。没有借用这些回执为新代码签署资格。
- 私有审计原始产物：`~/Library/Application Support/qmt-roll-stage179/development-verification/broker-sizing-stage235-20260908T1925/prerequisite-audit.json`，只含脱敏身份、哈希与阻断原因，不含账户/密码。
- 精确前置顺序：测试补齐并冻结 clean 新提交 → 以原 AI 五项不可变资产及真实截止日期构造新 publication request → publisher 分配新 release 并校验依赖闭包 → 新 release/commit 的独立评审与精确 runner → 两次正式只读账户采集及日数据/历史归属迁移资格 → 受控晋升。不能修改旧 m0005 payload 或仅移动 CURRENT。
- `build_trusted_production_qualification_bundle.py` 会在测试后直接调用两次 Stage907 production-live refresh；不存在纯离线参数。本阶段不运行该 builder，也不调用私有 assembler 拼装伪造正式资格。
- Volta 独立只读闭包审计：182 个 critical、54 套必需测试、270 项源码/声明闭包，动态导入未解析项为 0；六个新增 broker 模块及其测试和 905/931/941/sent 集成均已登记，未发现清单漏接。正式物料 builder 复用这套清单，不能继续复用缺少新模块的 m0005。

## 19:41 新测试首轮独立失败与预审

- 主 agent 用白名单 `build_trusted_runner_environment(readonly=False)`、隔离 HOME/TMP 运行新单例，结果 `1 failed in 10.53s`。保存 `stage235/main-e2e-probe.output`（实际在上述私有审计目录）。
- 已进入真实 `execute_spool_lease`，由于测试 payload 的 execution profile/version/capital/source 字段不完整，返回 `no_side_effect_retryable`；这是门禁拒绝不完整 fixture 的证据，不是生产门禁应被取消的理由。
- Turing 只读预审确认新成功入口确实使用真实 spool snapshot、授权 publisher、guard/pin、lease、post-lease 和 execute；没有通过旧测试的手填 native context 或 validator mock 放行。
- 仍需补：native 前 ledger/reservation/API slot/spool sending 的直接断言；Fake 请求字段映射检查；canonical/seal 与 consumer 实际 2 手的对应；JSON 重载次日归属消费。测试名称不得把未执行的跨日段算成成功。
- controller Stage902/927 的输入仍是合成测试证据，本阶段只证明真实授权发布/消费与执行链，不证明完整生产 controller、真实券商或生产资格。

## 授权链发现的真实阻断及先红后绿

1. `send_base` 没有复制已验证 intent 的 `source`，实际 `native_order_identity_persisted_before_insert` 记录缺来源；pure seal 正确拒绝 `native_owner_missing`。主 agent 独立重放 `1 failed, 2 passed`（16.23 秒），输出 `native-source-red.output`；只补 native 上下文来源，不改 canonical fill schema、fingerprint 或 pure 校验。
2. 补来源后已产生 canonical/seal 并通过 JSON 重载的实际 2 手归属，但普通全平遭遇 `blocked_c9_source_offset_mismatch`。最初怀疑 fixture，核对 Stage905 真实输出后否决该判断：普通平仓确实是 `stage901_pending_order + close`，而 Stage931 将该来源固定成 open。没有把测试改成 Stage904 来源掩盖真实路径。
3. 新增 reprice 回归在源码修改前为 `4 failed, 1 passed, 2 subtests passed`（包含 3 个 subtest failure）：正常 close 被拒；显式 close/invalid row 却可配 open request；fresh quote 用例未能走到报价门。修复为从原始已验证 row 的 offset 确定 expected offset；无 offset 仍保留原 open 默认，非法非空值和不匹配 request 拒绝，仍须真实 post-Q2 fresh tick。没有调价格保护、时间门、alpha 或风控参数。
4. 两处修复后，新三项授权 E2E 加两项 reprice 测试在白名单环境为 `5 passed, 5 subtests passed`（22.98 秒）；输出 `source-and-close-green.output`。缺失/撤销授权各自确认 native/API slot/ledger 为零；成功例严格请求及 native 前落盘断言通过，再经真实 callback/worker 生成 seal，JSON 重载后空当日 Order/Trade 查询仍可证明昨仓 2 手并通过 resized-close gate。
5. 准确数量边界：成功例是提交 4 手、实际成交 2 手、shadow 全平 4 手据真实归属缩为 2 手；不是该例证明开仓从 4 手缩到 2 手。开仓 broker sizing 的比例逻辑沿用之前独立回归。
- 正在冻结源码进行完整离线矩阵和独立复审；以上定向通过不是正式 production qualification。

## 独立最终定向评审

- Turing 对两处补丁及三项授权节点、整个 post-reprice suite 独立验证：`32 passed, 371 subtests passed`，28.95 秒，exit 0；源码及两测试 SHA 前后不变，没有 LANGUAGE 注入。两项已确认缺陷复验关闭，限定该变更和覆盖范围没有剩余已确认 P0/P1/P2，不据此扩大为全系统无风险。
- 931 SHA：`6ec8224ac3557a081a6e13def98c36985d6bfe0b74551401e9906c6f70cd7011`；E2E test SHA：`30d70ec35b836519bf89825529866b9a7ab0bd3269e99f9f70ceb08fdc8d1487`；post-reprice test SHA：`3ee71fbc95494fc09f0208c6c763833e76f731840f5a86b3a15c7fe9fe453906`。
- Reviewer 最初把 Stage901 close 失败归为 fixture，核对真实 Stage905 输出后明确纠正为源码 reprice 的硬编码问题；错误初判和实际红结果保留。
- Reviewer 一次 `-k` 误扩大选择，主动中断后返回 exit 2（31 passed），不纳入验收；最终 32 passed 来自后续精确节点完整重跑。
- 范围限制：开仓授权、spool 与 native 链已覆盖；次日平仓覆盖 JSON 重载、归属、定仓、真实 reprice/final-state gate，**没有覆盖平仓自身的授权→spool→native 提交**。另一路 `_stage905_ready_intent_artifact_blockers` 仍有 Stage901 initial-open-only 的既有约束，后续必须做路由取证及平仓整链资格，不能用本例绿色声称普通全平已经端到端可提交。
- Stage902/927 的测试 evidence 不等于运行其 controller；不运行真实 CTP、委托或撤单，不改生产/remote/master。

## 20:03 完整离线矩阵与本阶段结论

- 2026-09-08 19:55:46 至 20:03:34 CST，以同一冻结源码、白名单 HOME/TMP 环境逐套运行现有 `_trusted_pytest_argv`：54/54 返回零，`1652 passed, 833 subtests passed`，零失败。所有 182 个 critical 文件前后 SHA 一致。
- 固定压力套件继续使用原 `/usr/sbin/taskpolicy -a` runner，原压力配置及阈值未修改；本轮一次执行通过，没有为得到绿色重抽压力结果。
- 原始 stdout、JUnit、精确命令、调度策略、环境回执及各文件 SHA 保存于 `~/Library/Application Support/qmt-roll-stage179/development-verification/broker-sizing-stage235-final-20260908T1955/receipt.json` 和同目录逐套文件。
- 该矩阵是开发态离线验证，不是正式 qualification builder 的 clean release + 真实只读采集证据；不得改签为正式资格。
- 按已获授权保存本阶段源码、测试和研究记录到当前开发分支，提交 SHA 由提交后私有回执记录。未合入或推送 master、未冻结/激活新正式物料、未部署、未启动实盘、未连接真实 CTP 或调用真实委托/撤单。
- 剩余工作：普通平仓自身授权→spool→native 的完整路由验证；绑定新 clean release 的正式物料、独立资格、两次只读账户采集和真实历史归属迁移；完成后再按受控流程处理 master。真实资金自动交易启用须用户操作。
- 最终状态：`offline_open_authorization_e2e_verified_production_not_qualified`。
- 结束反思：不过拟合，仅修复执行链来源/开平语义，无 alpha、AI、仓位比例、止损或 retry 调参；继续有价值，后续以真实缺失证据为目标，不将测试绿色当作实盘发布资格。
