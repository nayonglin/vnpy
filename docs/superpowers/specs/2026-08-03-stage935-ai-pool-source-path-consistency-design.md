# Stage935 AI 池源路径一致性修复设计

## 背景与根因

2026-08-03 的 Stage935 月更按计划执行，但没有发布 `eval_date=2026-07-31` 的新 AI 池。只读取证确认：

- Stage183 的回测产物遵循 `OFFICIAL_LIVE_OUTPUT_DIR`，实际写入 production-live 的 `official-live` 隔离目录；其中 daily、position changes 和 entry candidate snapshots 均覆盖到 `2026-08-03`，并包含 `2026-07-31`。
- Stage183 自己的摘要路径和 Stage182 的输入路径仍由 `PROJECT_DIR/backtest_outputs` 构造。该路径在生产 release 中指向仓库的历史输出目录，相关旧文件只覆盖到 `2026-07-21`。
- 因此同一次 Stage935 运行中，Stage183 生成了新源，但 Stage182 读取了另一目录的旧源，最终解析出 `eval_date=2026-06-30`。Stage935 随后因缺少 `2026-07-31` 快照而 fail-closed。

问题本质是生产 artifact root 与 data asset root 混用，不是行情缺失、交易日历缺失或 AI 模型失效。

## 目标

1. Stage182 必须读取本次 Stage183 刚生成并通过完整性检查的同目录源文件。
2. 2026-08-03 的正常月更候选必须解析为 `eval_date=2026-07-31`。
3. Stage182 先写候选，不得在 Stage935 验证完成前覆盖正式 AI 池。
4. 验证通过后原子发布候选，并对发布后的正式文件再次校验。
5. 任一路径、日期、文件身份、历史月快照或安全字段不一致时继续 fail-closed。

## 非目标

- 不修改 AI 模型、训练窗口、特征、Top8 加固定 `fu.SHFE` 的 Top9 规则。
- 不强制指定缺少特征的月末日期，也不填造行情、持仓或候选事件。
- 不修改 Stage847-C9-15w 入场、止损、重试、止盈或仓位规则。
- 不连接 CTP，不查询账户，不调用报单、撤单或成交 API。
- 不绕过 Stage174 原生只读 qualification、Stage948 prepare/activate 或生产进程自然退出门禁。

## 架构

### 1. Stage183 统一声明真实产物根目录

Stage183 从实际保存回测产物的 `run_qmt_alignment_backtest.OUTPUT_DIR` 获取 artifact root。摘要中的 `outputs.daily`、`outputs.position_changes`、`outputs.entry_candidate_snapshots` 和日期审计全部基于该真实目录，不再基于静态 `PROJECT_DIR/backtest_outputs` 推测路径。`daily` 与 position changes 是逐交易日产物，必须覆盖本次 analysis end；entry candidate snapshots 是稀疏事件产物，允许最后事件日早于 analysis end，不能单独用它判断交易日历是否完整。

Stage183 摘要继续写入现有 data asset 位置，供 Stage935 读取；摘要必须同时记录真实 artifact root、各输入文件的绝对解析路径、最大日期与文件元数据。摘要声明的源文件只要不位于 Stage935 允许的隔离目录内，Stage935 就拒绝继续。

### 2. Stage182 支持显式源目录与候选输出目录

Stage182 新增两个显式参数：

- `--source-dir`：position changes 与 entry candidate snapshots 的唯一读取根目录。
- `--output-dir`：live pool、live eligibility、combined eligibility、summary 与 report 的候选输出根目录。

两者默认仍为现有 `OUTPUT_DIR`，保持研究和历史入口兼容。生产 Stage935 必须显式传入本次 `CONTROL_OUTPUT_DIR`，不能依赖默认值。

Stage182 构建 combined eligibility 时从正式 data asset 读取官方 Stage78 eligibility 与当前历史快照，但只把新 combined 文件写入候选目录。它不得直接修改正式 combined eligibility。

### 3. Stage935 验证后原子发布

Stage935 的生产数据流为：

1. Stage183 将新源生成到 `CONTROL_OUTPUT_DIR`。
2. Stage935 校验 Stage183 摘要中的真实路径、文件存在性、最大日期和本次 `resolved_target_date`。
3. Stage182 从同一个 `CONTROL_OUTPUT_DIR` 读取源，并把五类输出写回该目录作为候选。
4. Stage935 对候选执行完整校验。
5. 仅当候选有效时，将 summary、report、live pool 和 live eligibility 作为非激活证据文件先通过同文件系统临时文件加 `os.replace` 发布；正式 combined eligibility 是 Stage901 的唯一激活文件，必须最后发布。
6. 发布 combined eligibility 前保留同文件系统备份；通过 `os.replace` 激活后立即重新读取并校验。若校验失败，必须用备份原子恢复旧 combined eligibility，再把任务标记 blocked。
7. 正式文件与候选文件的 SHA-256、`eval_date`、Top9 行数和最近四个月快照必须一致，否则整次任务标记 blocked，并保留证据。只有 combined eligibility 激活且发布后校验成功，才允许状态变成 `monthly_ai_pool_updated`。

候选文件名沿用当前 Stage182 文件名，但位于隔离目录；正式文件名保持不变，以避免下游 Stage901 和邮件报告入口变化。

## 完整性与安全门禁

Stage935 在发布前必须满足：

- Stage183 的 source prefix 与请求值完全一致。
- Stage183 的 position changes 和 entry candidate snapshots 解析路径均位于本次 `CONTROL_OUTPUT_DIR`。
- daily 与 position changes 存在、非空，最大日期等于 `resolved_target_date`；entry candidate snapshots 存在、非空且最大事件日不晚于 `resolved_target_date`。候选事件日稀疏本身不是阻塞条件。
- Stage182 摘要声明的 source paths 与 Stage183 已验证路径逐字且解析后一致。
- Stage182 的 `source_max_date` 不早于 expected eval date，且 `eval_date` 等于 `2026-07-31`（对本次 2026-08-03 运行）。
- live eligibility 恰有 9 行、产品不重复、包含固定 `fu.SHFE`。
- combined eligibility 包含最近四个应有月末快照，并包含新 eval date。
- `overwrites_official_stage78_eligibility=false`、`uses_future_label_for_eval_date=false`、`real_order_enabled=false`。
- 候选校验或发布后校验任一失败，状态为 `monthly_ai_pool_update_blocked`，不得报告已更新。
- 整个流程的 order/cancel/trade API 计数必须保持 0；此改动不引入任何 CTP import 或调用。

## 错误处理

- 源目录不存在、越界、文件为空或日期不足：Stage935 在调用 Stage182 前停止。
- Stage182 返回非零、摘要缺失或候选校验失败：不发布正式文件。
- 原子发布期间出现异常：任务 blocked，记录已发布文件清单与候选/正式 SHA-256，禁止静默成功。只要 combined eligibility 尚未替换，正式 AI 池仍为旧版本；后续恢复必须重新运行完整候选校验。
- combined eligibility 发布后校验失败：先原子恢复备份，再标记 blocked，保留候选、备份和 receipt 证据；不得启动交易 API 修复。

## 测试设计

测试采用 TDD，至少覆盖：

1. 复现当前故障：Stage183 真实目录到 8 月 3 日、旧 data asset 到 7 月 21 日时，旧实现会选 6 月 30 日。
2. 显式 `source-dir` 后，Stage182 只读取真实目录并解析出 7 月 31 日。
3. Stage183 摘要报告的路径和最大日期来自真实 artifact root，并正确区分逐日文件与稀疏事件文件。
4. Stage935 在源路径指向旧目录、越出允许目录、最大日期不足或两份源不一致时 fail-closed。
5. 候选校验失败时正式 combined eligibility 的字节和 SHA-256 不变。
6. 稀疏候选事件最后日期早于 analysis end、但逐日源完整时，不被误判为日历缺失。
7. 候选通过时 combined eligibility 最后发布，正式摘要、eligibility 和 combined eligibility 与候选一致。
8. combined eligibility 发布后校验失败时恢复旧文件，旧文件 SHA-256 不变。
9. 发布后最近四个月 eval date、Top9、`fu.SHFE` 和安全字段校验通过。
10. 既有 Stage182、Stage183、Stage935 和 post-close orchestration 测试无回归。

正式验证只运行离线/只读 qualification，不运行正式 CTP capture。部署仍受 Stage174 候选 HEAD、磁盘/runtime/env、七个 launchd job 自然归零、两次只读 qualification、审查结果和 Stage948 receipt 约束。

## 发布与成功标准

代码首先合入 `codex/stage174-postclose-orchestration` 隔离候选。所有测试、独立审查和静态零 API 审计通过后，等待现有 production job 与 warm executor PID 自然归零，再按既有 Stage174 → Stage948 流程 prepare/activate。

本次修复的成功标准是：

- Stage935 生成并验证 `eval_date=2026-07-31` 的新 AI Top9 池；
- 正式 combined eligibility 含最近四个月快照且新池已原子发布；
- stable、manifest、receipt 与七个 label 指向同一已审查版本；
- order/cancel/trade API 计数为 0；
- 任一门禁失败时正式版本保持不变并明确报告 blocked。

## 参考判断

Pandas 官方时间序列文档把 `asfreq` 描述为基于明确日期索引的 `reindex`。该模式支持“让数据对齐权威时间/路径索引”，但不支持以强制日期覆盖缺失数据。本修复因此只消除路径分叉，不改变日期选择和业务填充语义。

- https://pandas.pydata.org/docs/user_guide/timeseries.html
- https://pandas.pydata.org/docs/reference/api/pandas.Series.reindex.html
