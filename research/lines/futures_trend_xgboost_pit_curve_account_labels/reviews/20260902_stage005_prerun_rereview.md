# Stage005 批量前独立复审

- 复审时间：2026-09-02 20:30 CST
- 模式：独立只读代码、合同与既有证据审计；仅运行有界测试
- 结论：`BLOCK_STAGE005_BATCH`
- 严重度：`P0=0/P1=2/P2=1/P3=0`
- 未执行：`prepare-campaign`、`run-batch`、worker、策略回测、模型、holdout、CTP、order
- 当前代码身份：branch=`codex/stage130-option-probe`，HEAD=`098ca5b99af76ab6f7fc3fb3442e4be17931caff`

## Findings

### P1-1：attempt 最终状态可被同秒 PID 字典序绕过

`tools/stage005_development_label_batch.py:1117-1125` 用 attempt_id 的字典序选择“最后”状态；attempt_id 在秒级时间后先拼 PID、再拼 `time_ns`（`:724-728`）。两个独立进程若在同一秒启动，较新的 attempt 可能因 PID 更小而排在较旧 attempt 前面。临时目录反例中，实际较新的 attempt 为 `failed`、较旧 attempt 为 `complete`，`_attempt_receipt_gate()` 仍返回 `passed=true/final_status=complete`。这会让失败恢复后的 campaign 被错误视为最终闭合，违反 fail closed。

必须把 attempt 顺序变成可验证的 append-only 单调序列，或按不可歧义的纳秒时间/前驱哈希链判断最新 attempt，并增加“同秒跨 PID：旧 complete、新 failed 必须拒绝”的测试。

### P1-2：run authorization 未机械限制只创建一个新 campaign

`tools/development_label_batch.py:361-400` 只校验 `decision` 和 bindings；不校验授权 scope、nonce、最大 campaign 数或消费状态。临时目录反例给出 `decision=ALLOW_STAGE005_BATCH`、精确 bindings、`scope=unlimited_campaigns`，校验仍返回 `passed=true`。`tools/stage005_development_label_batch.py:504-606` 每次调用都可创建新 campaign，也没有把授权标记为已消费。

因此，即使后续另建 run authorization，当前实现也不能执行“只允许创建一个新 campaign”的运行边界。必须结构化校验 `scope=one_new_stage005_campaign_only`，绑定唯一 nonce，并在 prepare 时以不可重放方式消费；或用等价的原子单次授权门实现。修复后重新独立复审，当前不得创建 authorization。

### P2-1：货币差值仍有未按操作数 1e-6 量化的派生字段

逐行 `curve/combined` 求和已改为每个操作数先 `Decimal(...).quantize(0.000001)`，reconciliation 主门已关闭首轮问题。但 `tools/stage005_development_label_batch.py:1331-1336` 的 `net_pnl_delta`、`slippage_delta` 仍直接做 float 相减；例如 `0.0000006 - 0` 输出 `0.0000006`，而合同要求的逐操作数量化结果为 `0.000001`。这两个字段当前不参与 pass gate，故定为 P2；仍需统一走量化 helper，并补边界测试。

## 首轮 BLOCK 逐项复核

1. **Stage005A v2 绑定：已关闭。** Stage005 静态绑定 v2 runtime receipt、成功 smoke、scope audit、post-run review/decision；数据库、主力映射、分钟数据、合约元数据重新计算 SHA 分别为 `db334200...0c4b`、`093d3bc...490b7`、`8e861633...6784`、`24a3573e...35a`。成功 campaign `campaign_20260902T192840+0800_77391` 的 manifest 同时包含四项冻结输入，resume 前重算完整 manifest。当前 Stage005 campaign 目录不存在。
2. **worker TMP/MPL：已关闭原问题。** worker 不重装父环境；job/run 级 `TMPDIR`、`MPLCONFIGDIR` 和 QMT guard 在进入 lock 前校验，orchestrator 路径负例被拒绝。
3. **attempt 生命周期：部分关闭，仍被 P1-1 阻断。** aggregate 期间 attempt 保持 active；`validate-only` 创建零 worker-command attempt；post-complete failure 写 post-failure 并使 gate 失败。最终 attempt 选择仍存在同秒跨 PID 绕过。
4. **scope 精确允许树与命令：已关闭。** artifact allowlist 由合同树派生，worker 命令要求精确形状；隐藏 holdout `label.json`、`ranker.json`、`send_order`、普通 CTP/model/order 日志及未知文件/命令负例均 fail closed。成功 smoke scope 的 13 个危险计数字段全为 0。
5. **逐操作数 1e-6：部分关闭，仍有 P2-1。** reconciliation 的序列求和已逐元素量化；两个货币 delta 派生字段尚未统一。
6. **结构化 review/auth：部分关闭，仍被 P1-2 阻断。** review decision 已精确校验 decision、P0-P3 整数和 review SHA；authorization bindings 已精确校验路径/SHA，但授权 scope 和单次消费未校验。
7. **rank10 resume 五文件：已关闭。** completed rank10 job 在跳过 worker 前重算 `curve/trades/entry_candidates/entry_risk/trade_events` 五个原始 predecision 文件 SHA；损坏任一文件即不视为 completed。
8. **最终零字段机械派生：已关闭。** `trains_model`、`sealed_holdout_label_count`、`ctp_connected`、`order_api_called_count` 均由 execution scope counts 回填，不再硬编码。

## 固定任务与隔离

- `development_jobs.csv`：270 个任务，固定 `266 main + 4 A2`，35 个 development 月，job_id 唯一。
- `full_feature_split.csv`：12 个 sealed holdout 月；与 35 个 development 月完全不相交。
- 当前 Stage005 artifact root 只有历史测试遗留的 `LATEST.json`，没有 `campaigns/`；`reviews/20260902_stage005_run_authorization.json` 不存在。
- 现有 Stage005A 成功 smoke/post-run 只证明运行身份、隔离和标签可辨识，不授权 270 任务，也不证明 XGBoost 收益或回撤改善。

## Fresh 验证

- `.py311/bin/python -m pytest` fresh 运行三个相关测试文件：`34 passed in 17.37s`。
- `PYTHONPYCACHEPREFIX=/private/tmp/stage005-rereview-pycache .py311/bin/python -m py_compile` fresh 编译三个工具文件和三个测试文件：exit 0。
- 有界 attempt 同秒跨 PID 反例：复现错误 `passed=true`。
- 有界 authorization scope 反例：`scope=unlimited_campaigns` 仍错误通过。
- pytest 对 Stage005 `LATEST.json` 的临时写入已恢复为运行前 SHA256 `046f32dc57acba59c904c28d389f6c800639cdbdea7139ee708131dd543728dd`；未保留测试 campaign、worker 或其他产物。

## 关键 SHA256

- Stage005 runner：`4b0e6c9a7367115acfa99d318740e5d9f1fe4558ab9ee6dd3d4f1d33d7774a06`
- batch core：`89a34e411008ce44628fcaa6a62d854c3b44486062338b5beac2d6231b1f25c4`
- Stage005 runner test：`beb00d81e81fde1c5c2ec95e229873a7deefe8623aa9feff902d13504d6cf3db`
- core test：`1f006eb04c131b4062de74607b7dc9b8428e93f65da826437366a22bb1a73d5d`
- Stage005A runner/test：`d707b6589520bf078c5eced3f9d67d2fa823fc9b3c62a6fc9d4153877c1860ee` / `99b7490730afa1e9c53002cca50fcb89c4c713f792d3a9053e973a0b67d037b3`
- v2 migration preregistration：`dd67ce27e3a18d582371c102e1607a34b3b524fab5b3d7daf25e71e8d2b3a148`
- v2 runtime/smoke/scope/post-run decision：`f67186f8...f0c2` / `d373a165...053` / `a9ffbb58...e3bc` / `631d5e88...bcf8`

## 调研与判断

Python 官方 `decimal` 文档确认 `quantize()` 用指定指数执行十进制定点舍入，支持本合同的逐操作数量化；XGBoost 官方 Learning-to-Rank 文档确认训练样本需按 query/group 身份组织。两者都不改变本次结论：当前阻断点在批量治理与证据状态机，不在模型参数。

## 最终判断

- **过拟合：否。** 本次只审计冻结代码、合同和既有四任务 smoke，并运行治理反例；没有读取新标签、挑月份/品种/rank、训练模型或比较策略结果。
- **继续价值：是，但仅限修复上述 2 个 P1 和 1 个 P2 后再次独立复审。** 技术方向仍值得完成开发标签资格验证，但当前不得 prepare campaign、运行任务或创建 run authorization。
- **决策：`BLOCK_STAGE005_BATCH`。** 不满足 `P0/P1/P2` 全零条件，不能签发 `ALLOW_STAGE005_BATCH`。
