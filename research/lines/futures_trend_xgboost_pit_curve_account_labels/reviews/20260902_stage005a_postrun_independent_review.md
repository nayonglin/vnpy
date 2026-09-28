# Stage005A post-run independent review

- 审计日期：2026-09-02
- 审计对象：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_xgboost_pit_curve_account_labels/artifacts/stage005a_runtime_identity_remediation/campaigns/campaign_20260902T192840+0800_77391`
- 审计性质：快速、独立、只读 post-run 审计
- 审计边界：仅判断是否允许“Stage005 迁移到 v2 并再做批量前复审”；不授权任何 270 任务，不授权模型训练、holdout、CTP、报单或生产变更

## 结论

**允许 Stage005 迁移到 v2，并进入下一次批量前独立复审。**

本结论不是批量运行授权。当前不得启动 266 个 main 加 4 个 A2 的 270 任务；后续必须以迁移后的冻结 v2 执行计划、身份与 scope 证据再次完成独立复审，另行取得明确授权后才可讨论批量启动。

## 核验结果

1. `smoke_receipt.json`：`passed=true`；16 个 gates 全部为 `true`，即 16/16 通过。receipt 决策本身也限定为 `stage005a_runtime_identity_smoke_pass_allow_stage005_batch_rereview_only`。
2. `execution_scope_audit.json`：`passed=true`；固定输出任务集准确，job/worker/output 均为 4；13 个危险计数全部为 0，包括 CTP、订单、模型训练、模型产物、holdout、未知输出、意外产物及意外 worker command。
3. 四个 `worker_receipt.json`：四个任务均为 fresh process；PID、`TMPDIR`、`MPLCONFIGDIR` 为 4/4/4 唯一，路径均包含 campaign id、各自 job id 和独立 run 目录，满足 job-scoped 隔离。
4. 四个 worker 的 `input_identity_pass=true`；`checkpoint_reused=false`、`completed_result_reused=false`，未发现输入身份失败或 checkpoint/result 复用。
5. 202201 A/A：`20220128_R10` 与 `20220128_R10_A2` 的 `label.json` SHA256 均为 `fa6ba74a589420af2071ac3bbe99c62bba7dc73d26fe0f381a9df7b6a07a94e1`，输出完全一致。
6. 202202 R11-R10 标签差：未来净利润 `+120,910.00`；未来收益 `+0.02550704615537015`，约 `+2.5507pp`；未来最大回撤由 `-0.15433910887160407` 改善到 `-0.14041407927923688`，改善 `+0.01392502959236719`，约 `+1.3925pp`。该差异只证明标签可辨识，不证明模型价值、样本外收益或可上线性。
7. 测试证据：引用已有独立 fresh 证据，三个相关测试文件合计 `30 passed`，`py_compile` 通过。本次审计按约束未运行 pytest、未运行回测，也未访问网络。

## Findings

- P0：0
- P1：0
- P2：0
- P3：0

未发现阻断“迁移到 v2 并再次进行批量前复审”的问题。该零 finding 仅覆盖本次指定 campaign 的 runtime identity remediation smoke 与 execution scope，不外推为 270 任务授权或 XGBoost 有效性结论。

## 独立判断

- 过拟合：否。本次只审计执行身份、隔离、作用域和固定标签输出，没有新增模型、参数搜索或回测结果；202202 差值不作为 alpha 证据。
- 是否值得继续：是，但只值得继续到 v2 迁移后的批量前独立复审。当前证据足以关闭 runtime identity smoke 门，不足以跳过下一道复审或启动 270 任务。
