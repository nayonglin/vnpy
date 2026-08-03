# Stage174 关闭后原生 API 访问修复设计

日期：2026-08-03

## 背景与根因

Stage174 正式 CTP 只读采集已经两次以退出码 `-11` 结束，macOS 崩溃报告将故障定位到 `TdApi::getTradingDay()` 的空指针访问。当前代码在 `main_engine.close()` 之后，仍可能通过兜底表达式再次调用 `td_api.getTradingDay()`。此时 CTP native 对象已经被 `exit()` 释放，Python 包装对象仍存在，但其底层指针已经失效。

因此，根因不是 schema v2 兼容改动，也不是磁盘容量，而是 Stage174 在关闭边界之后访问了已经失效的 native TdApi。

## 目标

1. `main_engine.close()` 之后不再调用任何 TdApi/CTP native 方法。
2. 保留 vn.py 当前正常的 `main_engine.close()` 清理流程。
3. 在连接仍有效、只读快照仍处于同一连接世代时，把交易日冻结成纯 Python 字符串。
4. 如果关闭前没有取得有效券商交易日，按现有安全语义正常 fail-closed，不以 native 兜底，也不生成可放行的伪证据。
5. 不改变策略 alpha、信号、下单数量、止损重试或任何报单路径。
6. 修复通过现有正式生产资格认证后，才允许由 Stage948 切换 stable。

## 非目标

- 不升级 `vnpy_ctp` 或替换 CTP framework；升级会扩大 ABI 和运行时风险，且目前没有证据表明它能消除此调用时序问题。
- 不采用 `os._exit()` 绕过正常析构；该方案会扩大清理语义的变化范围。
- 不放宽 Stage927、Stage931、Stage948 或任何生产证据门禁。
- 不强制停止、重启或插入当前正在运行的生产会话。

## 设计

Stage174 的只读采集分成两个明确阶段：

1. **native 有效阶段**：在 readiness 与 query snapshot 已确认属于同一连接世代时，调用 `getTradingDay()`，清洗并保存到 `summary["broker_trading_day"]`。这里是唯一允许读取 native 交易日的位置。
2. **关闭边界**：设置现有 closing fence 后调用 `main_engine.close()`。从这一行开始，所有后续逻辑只允许使用已冻结的 Python 数据、查询行和计数器。
3. **证据组装阶段**：query bundle 的 `broker_trading_day` 只读取 `summary["broker_trading_day"]`，不得再访问 `td_api`。若值为空，则 bundle 保持不完整并由既有资格规则 fail-closed。

这一设计把 native 对象生命周期与证据序列化彻底分开，修复范围只覆盖崩溃边界，不改变业务决策。

## 测试驱动修复

先新增一个回归测试，使用可观察的假 TdApi：

- `main_engine.close()` 后把假 TdApi 标记为失效；
- 失效后任何 `getTradingDay()` 调用立即抛错并记录调用；
- 当前实现应先出现 RED，证明测试能捕获关闭后访问；
- 最小代码修复后变为 GREEN，并断言关闭后的 native 调用次数为零；
- 另测关闭前未取得交易日时仍正常 fail-closed，不发生崩溃或兜底读取。

## 验证范围

本地静态与回归验证至少包括：

- Stage174 query bundle 定向测试；
- schema v1/v2 与手工成交纳管测试；
- durable state 集成测试；
- 修改文件 `py_compile`；
- 变更集审查，确认没有新增报单、撤单或策略行为修改。

正式生产资格认证仍按 SOP 执行：固定测试矩阵、两次独立 CTP 正式只读采集、source commit 一致性、P0/P1 为零、资格证据完整。任何一步失败都不得激活。

## 部署与回滚

1. 等待全部正式交易会话自然退出，确认相关 launchd job 均无 PID；不打断当前运行中的会话。
2. 激活前重新检查磁盘、源码提交、正式 env 与 CTP framework 优先级。
3. 仅通过 Stage948 prepare/activate 安装，禁止手工复制 plist、直接改 stable 或强制 kickstart。
4. 激活期间要求 CTP 连接、查询、报单、撤单计数全部为零。
5. 若修复、资格认证或激活任一步失败，stable 与现有 7 个正式 launchd 标签继续保持旧版本；由 Stage948 的原子切换/回滚语义保护生产。

## 成功标准

- Stage174 两次正式只读采集均正常退出，不再出现 SIGSEGV；
- 两份采集证据完整且 source commit 与候选提交一致；
- P0/P1 问题数均为零；
- Stage948 prepare 与 activate 均成功；
- stable、manifest、receipt 指向同一新提交；
- 正式环境仍严格只有预期的 7 个 launchd 标签；
- 激活期间报单、撤单和订单 API 调用均为零；
- 当前生产会话未被人为中断。

## 过拟合与继续价值判断

这不是过拟合。修复针对可复现的 native 生命周期违规，约束的是资源安全边界，与品种、行情样本和策略收益参数无关，能够跨周期成立。

值得继续。该缺陷阻断了正式只读资格认证，使已经通过业务回归的 schema v2 修复无法安全发布；消除崩溃后才能恢复生产证据链，但仍必须保留全部 fail-closed 门禁。
