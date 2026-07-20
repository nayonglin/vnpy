# Stage189 Stage179 Task9 运行时隔离、发布清单与默认关闭激活闸门

## 基本信息

- 改动时间：2026-07-18 19:35 CST
- 研究线：`futures_trend_stage819_intraday_rules`
- 工作区：`/Users/bytedance/Desktop/person/vnpy_stage179_live_reliability`
- 分支：`codex/stage179-live-execution-reliability`
- 基线提交：`7c17280eb`
- 代码提交：`f2412e2c14f40721602e5aba03e59ee0793b1545`
- 是否重要突破版本：否。Task9 已达到代码可提交条件，但只是默认关闭的部署基础设施；Task10-13、官方口径冲突、只读 CTP、SimNow、LaunchAgent 和端到端延迟验收均未完成，不能称为可部署激活的实盘版本。
- 实盘边界：未加载真实 env，未连接 CTP/SimNow，未调用真实报单或撤单 API；验证均为离线 `0/0`。Stage931 legacy 路径默认不进入新闸门，代码部署与 Stage179 激活保持隔离。

## 外部调研与判断

执行前复核了官方资料：

- Python 3.11 `pathlib.Path.resolve`：<https://docs.python.org/3.11/library/pathlib.html>
- Git `merge-base --is-ancestor`：<https://git-scm.com/docs/git-merge-base>
- Git 官方文档：<https://git-scm.com/docs>
- vn.py 官方仓库：<https://github.com/vnpy/vnpy>
- vn.py 官方发布记录：<https://github.com/vnpy/vnpy/releases>

判断结论：运行时隔离必须基于解析后的真实路径而不是字符串前缀；发布清单的 source commit 必须存在且是当前提交祖先，关键文件还必须与 source commit 的 Git blob 精确一致；macOS 生产只读/实盘必须把正式 `vnpy_ctp/api/libs` 放在 `.py311/lib` 前。当前 `AGENTS.md` 指定 Stage372/20w，而仓库官方配置仍是 Stage847-C9/15w，代码不能替 operator 选择口径，因此显式 warm production-live 始终以 `operator_policy_conflict_unresolved` fail-close。

## 本次改动

### 新增

- 新增 typed runtime profiles：`offline`、`production-readonly`、`simnow`、`broker-test`、`production-live`，并与 `none/readonly/test/live` order scope 做精确一一映射。
- 新增 profile 独立 output/state/spool/ledger/readiness/activation-receipt 根目录；所有路径先 resolve，再检查 protected production roots 的相等、父子和 symlink/`..` 别名重叠。
- 新增 env 精确映射；生产使用 `ctp_live.local.env`，SimNow 使用 `ctp_simnow.local.env`，broker-test 使用 `ctp_broker_test.local.env`，offline 不使用 env；env 文件本身若是 symlink 则拒绝。
- 新增 immutable release manifest：包含 schema、release ID、官方版本、资金/标签、source commit、排序后的关键文件 SHA256/大小、tree fingerprint、ledger schema/fingerprint versions/reader capabilities、允许的 runtime profiles、UTC 时间和全字段 digest。
- 新增 clean-tree builder：source commit 固定为 HEAD；关键文件工作树摘要必须与该 commit 的 Git blob 一致；构建后再次检查 HEAD/clean，拒绝 TOCTOU；相同字节允许幂等读取，不同内容拒绝覆盖。
- 默认 critical-file closure 纳入 builder、runtime/manifest、ledger/spool、Stage902/903/904/905/914/927/930/931/941。
- 新增 activation receipt 只读验证，绑定 manifest digest、官方版本、资金/标签、`policy_decision=approved`、UTC 时间和 receipt digest；代码不创建回执。
- Stage931 新增显式 `--stage179-warm-executor` opt-in。默认关闭、runtime/order 默认 `offline/none`；只有显式 warm live-real 才强制 `production-live/live` 并在动态导入 `vnpy_ctp/CtpGateway` 前执行新闸门。

### 修改

- Phase D config 改为轻量、本地定义 `OUTPUT_DIR`，避免仅导入激活闸门就拉起历史回测配置链；新增 Stage179 activation env、精确确认文本和 receipt schema version。
- Stage914 增加严格 resolved-profile 复核、release manifest 验证、原 Phase-D/Stage927/kill-switch/broker freshness、activation receipt 和 operator policy conflict 的 pre-adapter gate。
- Stage931 warm opt-in 对 Stage927 要求 `real_submit_permitted=1` 且时间戳存在并在阈值内；legacy protective reduce-close 不继承该新限制。
- Stage930 保持 Task8 冻结字节 `bd4311cf...`，不解析、不透传 Stage179 参数；合入 Task9 不改变 legacy 开仓、平仓或 protective reduce-close。

### 删除

- 未删除任何 alpha、止损、重进场、AI 池、资金或 legacy 执行规则。
- 未生成 activation receipt，未创建发布 manifest 实例，未修改真实 env 或 LaunchAgent。

## 参数变化

- 新增 `--stage179-warm-executor`：默认关闭。
- 新增 `--runtime-profile`：Stage931 默认 `offline`。
- 新增 `--order-scope`：Stage931 默认 `none`。
- 新增 `--stage179-release-manifest`、`--stage179-activation-receipt`、`--confirm-stage179-activation`。
- 新增 activation env：`OFFICIAL_LIVE_STAGE179_WARM_EXECUTOR_ENABLED=1`，仅显式 warm production-live 检查。
- 新增 activation 确认文本：`I_UNDERSTAND_THIS_ACTIVATES_STAGE179_WARM_CTP_EXECUTION`。
- 修改参数：无 alpha、资金、止损、重进场或选品参数修改。
- 删除参数：无。

## 验证结果

- Task9 定向测试：`20/20`，覆盖 profile/scope、路径别名、env symlink、伪造 profile、default-off、submit-disabled canary、policy conflict、receipt、manifest tamper、Git ancestry、Git blob TOCTOU、critical closure 和 Stage931 import 顺序。
- Stage930/Stage931 兼容回归：`124/124`，耗时 `15.216s`；为纯内存 fake 测试使用仓库提供的 `QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR=1` emergency override，未访问数据库、未读取真实 env、未连接 CTP。
- 关联账本/耐久状态/意图链：`140/140`，耗时 `5.198s`。
- `py_compile`、`git diff --check`：通过。
- 订单 API：send `0`、cancel `0`。
- 代码提交：`f2412e2c14f40721602e5aba03e59ee0793b1545`。

## 独立审查

- 第一轮：`P0=0, P1=4, P2=1`。发现新闸门未接可执行路径、字符串 profile 可绕过、builder clean/hash TOCTOU、critical files 未覆盖 Stage931；全部修复，env symlink P2 同步修复。
- 第二轮：原 4 个 P1 均关闭，但发现无条件接入 Stage931 会让“代码部署”等于“冻结 legacy 实盘”，包括 protective reduce-close；结论 `P0=0, P1=1, P2=2`。
- 第三轮最终终审：显式 warm opt-in、默认 offline/none、Stage930 legacy 字节恢复、Stage927 freshness 和 producer closure 完成后，`P0=0, P1=0, P2=1`；结论为 Task9 code-submit eligible、live-activation not eligible。
- 接受延期 P2：Stage931 接线回归当前主要是源码顺序/参数断言；Task10 必须补行为级 CLI 矩阵，覆盖 legacy live-real 不调用新 gate、warm dry-run 不导入 CTP且不要求 receipt、warm live-real 错 profile fail-close、正确 profile 仍被 policy conflict 阻断。

## 回测结果

本阶段没有改变策略 alpha，也没有运行回测；以下指标均为不适用：

- 期末权益：N/A
- 总收益：N/A
- 最大回撤：N/A
- Sharpe：N/A
- 总滑点：N/A
- 总交易次数：N/A
- 胜率：N/A
- 新增/修改/删除回测结果：无

## 反思与后续

- 开始前是否过拟合：否。目标是运行环境、发布完整性和激活授权的跨周期不变量，不根据某天、某品种或收益曲线调参。
- 完成后是否过拟合：否。实现只收紧 profile、路径、提交谱系、回执和 import-before-side-effect 边界，未反馈到 alpha。
- 是否仍值得继续：是。Task9 阻止错误环境、错误代码树和未授权激活，但尚未消除 Stage931 每次冷连接、执行代际/ready lease 和服务生命周期延迟。
- 下一步：按 Spec 执行 Task10，抽取 generation-bound warm Stage931 session/executor service，并补最终审查要求的行为级 CLI 矩阵；保留 one-shot legacy 路径。
- 硬门禁：operator policy conflict、Tasks10-13、独立终审、真实 `0/0` 只读 CTP、SimNow、LaunchAgent 和端到端延迟验收全部完成前，Stage179 warm production-live 禁止激活。
- 记录隔离：本工作区只新增唯一 Stage189 文件，未修改同线 `LINE.md`、`research/registry.md`、根目录 `memory.md` 或 `back_log.md`。
