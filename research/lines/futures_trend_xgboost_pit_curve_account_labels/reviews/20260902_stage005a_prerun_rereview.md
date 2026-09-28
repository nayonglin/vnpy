# Stage005A 预运行独立复审

- 复审时间：2026-09-02 18:35 +0800
- 复审角色：第二位独立只读 reviewer
- 复审结论：`ALLOW_STAGE005A_SMOKE`
- 严重度：P0=0，P1=0，P2=1，P3=1
- 置信度：97%
- 授权范围：仅固定 4 个 Stage005A smoke 任务；不授权 Stage005 的 270 任务批量
- 运行边界：未创建 runtime/campaign/artifact，未运行 worker/backtest，未连接 CTP，未调用订单 API

## BLOCK 修复复验

- 静态 artifact allowlist 已拒绝未知/holdout CSV 和模型产物，负向测试通过。
- worker 在写 lock 前依次校验结构化授权、runtime receipt、campaign root、`ABANDONED.json`、固定 job、execution plan、授权哈希和 campaign identity。
- JSON 布尔 severity 已由 `type(value) is int` 拒绝。
- snapshot 初始化失败回滚测试通过。
- 真实 legacy loader 指向 v2 `frozen_inputs`；子进程命令重新进入 Stage005A wrapper。
- rereview/decision/authorization/runtime/campaign 在复审时均不存在，因此执行门仍 fail closed。

## 输入身份

- 生产 checkout：`d492ee072aa5a9d71477235d79f17d2a5db59db3`，clean。
- DB、mapping、minute、metadata 的 SHA、大小、SQLite 1020420 行、最大时间 `2026-09-02 00:00:00` 和 integrity 均匹配预注册。

## 剩余非阻断项

- P2：bool severity 回归测试位于 `test_development_label_batch.py`，未作为 Stage005A runtime binding；实际运行的 `development_label_batch.py` 已绑定，故不影响本次代码身份。Stage005 批量授权前应绑定完整核心测试集。
- P3：snapshot 清理依赖进入前目标目录不存在；并发初始化时存在理论清理竞争。本次只允许单实例顺序执行，且不触碰生产数据。

## 验证

- 限定 pytest：16 passed。
- 7 个目标文件 `py_compile`：通过。
- 无授权 preflight：按预期 fail closed。

## 判断

- 过拟合：否；仅审计执行身份和 fail-closed 治理，没有读取新回测结果、选样或调参。
- 继续价值：是，仅限授权后的固定四任务 Stage005A smoke；该 ALLOW 不授权 270 任务批量运行。
