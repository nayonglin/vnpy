# Stage005 第二次批量前独立复审

- 复审时间：2026-09-02 20:58 CST
- 结论：`BLOCK_STAGE005_BATCH`
- 严重度：`P0=0/P1=0/P2=1/P3=0`
- 当前分支：`codex/stage130-option-probe`
- 当前 Git HEAD：`098ca5b99af76ab6f7fc3fb3442e4be17931caff`
- 审查边界：只读代码、冻结合同、既有证据和临时目录治理反例；未执行 prepare campaign、run-batch、worker、回测、模型、holdout、CTP、order，未创建 run authorization。

## Finding

### P2-1：attempt end receipt 合同不完整时仍可通过 gate

`tools/stage005_development_label_batch.py:1258-1270` 对 end receipt 只校验 `attempt_id`、`phase` 和 `status`，随后在 `:1292-1301` 将其视为有效最终 receipt。它没有核对 `generated_at`、`completed_job_ids_after`、`completed_job_count_after`，也没有要求 `complete` 的 `error=null`、`failed` 的 error 非空。

独立临时目录反例：保留最新 attempt 的 `status=complete`，把 `completed_job_count_after` 改为 `999`，同时把 `error` 改为 `error_on_complete`；`_attempt_receipt_gate()` 仍返回 `passed=true`、`receipt_shape_valid=true`、`final_status=complete`。这违反新预注册“end 合同不一致均 fail closed”的冻结要求。

该缺口不直接绕过 270 个输出、scope、reconciliation 或 Stage005A 身份门，因此定为 P2；但本次放行条件要求 P0/P1/P2 全零，所以仍必须 BLOCK。修复时应机械校验 end 全字段、计数与列表一致性及 status/error 关系，并补上述负例。

## 指定重点复核

1. **attempt sequence 主问题已关闭。** start receipt 写入正整数 `attempt_sequence`；gate 按 sequence 认最新。缺失 sequence、重复 sequence、active attempt 非最新均返回 `passed=false`。
2. **同秒 PID 反例已关闭。** 旧 attempt 为大 PID 且 complete，新 attempt 为小 PID 且 failed；最终识别新 attempt 为 latest，`final_status=failed`、`passed=false`。
3. **authorization scope/nonce 已关闭。** `validate_run_authorization()` 在 Stage005 调用中严格要求 `scope=one_new_stage005_campaign_only` 和小写 64 hex nonce；`unlimited_campaigns`、63 位、非 hex、大小写不符均拒绝。
4. **单次消费已关闭。** prepare 在 campaign 目录创建前以文件模式 `x` 写消费回执；同一 authorization 第二次消费抛 `FileExistsError`。resume 与 worker 均校验消费回执的 authorization SHA、nonce、scope 和唯一 campaign_id。
5. **manifest 绑定已关闭。** campaign identity 的输入集合包含 `stage005_authorization_consumption`，生成 identity manifest 时按文件 SHA 纳入 file contract；progress/tombstone 也记录消费回执 SHA。
6. **金额 delta 已关闭。** `net_pnl_delta`、`slippage_delta` 统一调用逐操作数 `0.000001` 量化 helper；`0.0000006 - 0` 得到 `0.000001`，反向得到 `-0.000001`。

## 首轮其它项与 Stage005A v2

- Stage005 静态输入校验通过 22 项；v2 runtime receipt、smoke receipt、scope audit、post-run decision SHA 分别为 `f67186f8e1603c81afeb5800e3e742287228862e61e984aac6c843a1a69bf0c2`、`d373a16588f2a2ce4125982ebe5bcbaa21534b25ba02c935d9376b818ef2e053`、`a9ffbb58520f94c0c2bbb6af530afa0fd4eb12530c90f60e0fa575d8833de3bc`、`631d5e8842362e421c08cd0e1209beadeaa1b7e9e69d4da5fa0161c3c290bcf8`。
- 固定任务仍为 `266 main + 4 A2 = 270`、35 个 development 月；12 个 sealed holdout 月与 development 不相交。
- worker TMP/MPL 隔离、aggregate 生命周期、post-complete failure、精确 scope/命令树、逐操作数量化、结构化 review/auth、rank10 resume 五文件复核、最终零字段机械派生均有现有专项测试覆盖，fresh 运行未见回归。
- Stage005A v2 的 4 任务 scope audit 仍为 13 个危险计数字段全零；这只证明运行身份、隔离和标签可辨识，不授权 Stage005 批量，也不证明 XGBoost 效果。

## Fresh 验证

- 三个相关 pytest 文件 fresh 运行：`38 passed in 25.52s`。
- 三个相关工具文件和三个测试文件 `py_compile`：exit 0。
- pytest 已知会覆盖 Stage005 `LATEST.json`；运行后已按保留副本恢复，SHA256 回到运行前 `d4eab76d1de22fae20699b6658fd70a11bd2adfc94fc1a8c47b4c2ea792e10f6`。
- Stage005 artifact root 只有既有 `LATEST.json`；无 `campaigns`、无 `reviews/20260902_stage005_run_authorization.json`、无 `authorization_consumption.json`。

## 当前文件 SHA256

- batch core：`365b50c47c8147196a8a4741475ec7613641fee99564e165374737f775b0b0bd`
- Stage005 runner：`c5d948350f7ef54ab72afe404d61005f5762e1a4d35000e6d67a6b6aaf8d2210`
- Stage005A runner：`d707b6589520bf078c5eced3f9d67d2fa823fc9b3c62a6fc9d4153877c1860ee`
- core test：`a4eb68fac325564036aae2322260fe3d6e833d31e783eb1fb11b5639e47f8e6e`
- Stage005 runner test：`23eccf6d1ba433a00ce96572f9729c89b8a65c85cf8ca96b0cf5d573136bfc19`
- Stage005A test：`99b7490730afa1e9c53002cca50fcb89c4c713f792d3a9053e973a0b67d037b3`

## 调研、过拟合与继续价值

- 外部调研：Python 官方文档确认文件模式 `x` 为独占创建、目标已存在时失败；`Decimal.quantize()`按指定指数执行定点舍入。当前实现的授权消费与金额量化方向正确，剩余阻断点是本地 end receipt 合同校验。
- 过拟合：**否。** 本轮只验证治理状态机、授权单次消费、金额表示和冻结身份；没有读取新标签、挑选月份/品种/rank、训练模型或比较策略结果。
- 继续价值：**是，但仅限修复 P2 后再次独立复审。** 在 P0/P1/P2 全零前不得创建 Stage005 run authorization，不得 prepare 或运行 270 任务。
- 最终决策：`BLOCK_STAGE005_BATCH`。
