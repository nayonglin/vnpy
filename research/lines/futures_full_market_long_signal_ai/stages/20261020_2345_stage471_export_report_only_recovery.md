# Stage471：四本现金已完成后的导出目录修复与显式报告恢复

- line_id：`futures_full_market_long_signal_ai`；改动时间：2026-10-20 23:41—23:45 CST；非重要突破。
- root 独占 session34282 的 actual_run2 已 exit1，但原四 cash kernel **started=4/completed=4**，四本 raw book checkpoint 已全部保存。失败仅发生于导出，绝不重跑现金、不再 restore native。

## 第二次失败事实与现场保存

失败原因：本 wrapper 的 `export` 先 `folder.mkdir(exist_ok=True)`，随后原 `stage148_fx_cash.write_ledgers` 使用 `folder.mkdir(exist_ok=False)`，必然产生 FileExistsError。真实失败在第一个账户 ledger 写入前，属于 I/O 适配缺陷，不是模型、信号、资金或费用计算失败。

在修复前逐字节保存：

| 证据 | 字节 | SHA256 |
| --- | ---: | --- |
| `failed_attempt2_source.py` | 36662 | `d640f3efd92f6561d1a3baa25d65b0e52701a70444da2bf55a38149c5ac9bc85` |
| `failed_attempt2_fixture.py` | 6918 | `acb30c3ce1efa73e27f9aaf28dd83f022cd936e5fb43bb44a24dc45f639d0581` |
| `failed_attempt2_actual_terminal.json` | 735 | `8344be6efa41fd4935905f1bc89c0ae5fd536ed409b173ec0ddddcc051adb01b` |
| `failed_attempt2_manifest.json` | 8606 | `6ca98ad34a77900b7d99d02d8d5b3c33bb87d78cdc1f1eb214f302eb9eaadd9e` |
| 原 `actual_run2/book_checkpoints.json` | 4566 | `540bf9847b4c9db377c400b0e0de6f2de5596cbfb3c6b91a988609b84195b3ea` |

以上位于本线 `outputs/stage471_annual_mature_cash/`。`export_directory_failure_receipt.json` 绑定现场、完整旧 metadata、四本 raw checkpoint 和空目录处置。修复验证时原失败 live manifest/terminal 与 snapshot 相同，四本 raw book 的 SHA 全部与原 checkpoint 一致。

第一个账户目录经实际检查确认为空，只对该空目录执行 `rmdir`；没有删除其他目录、账本或数据。原 actual_run1 的失败现场也保留。root 后续报告恢复可更新 actual_run2 当前报告 manifest/终态，原失败 snapshot、attempt1终态、raw books 与原 checkpoint 不覆盖。

## 最小修复与局部验证

本次按 systematic-debugging 对照原 148 已工作接口，先新增真实目录所有权回归：抽取当前 wrapper 的实际 export 函数，调用原 148 writer 在临时目录写空 ledger；财务报表计算前主动停止，因此不是现金回测。RED 明确复现 wrapper 预建目录使原 writer 的 `exist_ok=False` 冲突。

唯一导出修复：删除 wrapper 中重复的 `mkdir`，由原 writer 独占创建账户目录。GREEN 实测原 writer 正常写出其 8 个账本角色和 rejections，共 9 个 gzip 文件，随后按 fixture 设计在财务计算前停止。

另新增必要恢复授权检查：无精确授权时，新报告 source bundle 被拒；绑定旧现金来源、新报告来源、原四 checkpoint 与不变 metadata 的 root 授权后，合成报告恢复成功，kernel 调用数保持原 4，恢复进程新 cash 0，checkpoint SHA 不变。最新局部 2 项均 exit0，不运行旧 suite 或真实报表。

AST 证明原 `prepare`、`report_context`、`finalize`、gate、run_account、calendar decode、母体/选择/控制/identity 等函数不变；export 函数仅删除该 mkdir，其他 AST 完全一致。原顶层仅 run_four/execute/main 新增显式报告恢复授权与来源披露，新增函数 `validate_report_recovery`，没有改金融、模型或策略参数。

| 新 source bundle | 字节 | SHA256 |
| --- | ---: | --- |
| `tools/stage471_annual_mature_cash.py` | 40162 | `e7bbd9d375bfcb472bf1c2cf7f475514e3fa5a9bd3ddd8c6243cba36d23b6ebe` |
| `outputs/stage471_annual_mature_cash/synthetic_fixture.py` | 10960 | `d13de1391bbc408d4f08f90f9622022e6941c03a59bedee685361a40010a2434` |

证据见 `export_report_recovery_verification.json`。本修复实际 fit/cash/native/SQL 均 0，四 raw books 仅 hash 检查，没有 kernel 重放。

## 仅报告恢复的明确身份合同

root 创建并签发一个 JSON，schema=`stage471_exact_report_recovery_authorization_v1`，包含：

- `authorized_by=root`、`mode=reports_only`、原 actual_run2 绝对 `output`、原 469 `protocol_sha256`。
- `old_book_source_bundle`：原 actual_started metadata 的 d640 源/旧 fixture；`new_report_source_bundle`：上表新来源。
- `unchanged_non_source_metadata`：原 metadata 删除 source_bundle 后的完整对象，所有协议、handoff、fit manifest、授权和连续性字段必须不变。
- `failed_manifest`、`failed_terminal`：本次已保存的精确失败 snapshot 绑定，且报告启动前必须与实际失败文件 SHA/字节数相同。
- `book_checkpoints` 与完整 `books`：原四书索引和每本 raw binding，与失败 manifest/原 checkpoint 严格一致；checkpoint.metadata 仍等原现金 metadata。
- `new_cash=0`、`native_cache_loads=0`、`SQL=0`。

原 CLI 同 output/协议/handoff，新增 `--reports-only --report-recovery-authorization <JSON> --report-recovery-authorization-sha256 <SHA>`。此入口不会调用 prepare/native/cash；不会静默跳过任何协议、handoff、非 source metadata 或原账身份核验。新 report manifest 明确记录 `old_book_source`、`new_report_source` 和授权 binding，report terminal 明确本进程新 cash/native 都 0。

本 agent 只准备源码和证据，由 root 独占发起报告进程；没有第三次准备或新增现金授权。

## 指标、累计与后续

当前累计 481 fit/258 **已完成 kernel 的现金账户**，其中本年度更新 15 新 fit/4 新 cash。actual_run1 为准备失败且现金 0；actual_run2 四 cash 均完成，导出尚未完整。native 累计 2=第一次失败准备 1+完整四账共享 1；报告恢复必须新增 0，不能把累计写成 1。

新增/修改/删除策略参数均 0，金融结果重算均 0。原四 raw books 固定，尚未完成报告时，本阶段期末权益、总收益、最大回撤、Sharpe、手续费、总滑点、总交易次数、胜率均 N/A，不从部分导出推断策略结论。待 root 报告恢复终态后，只补中文结果与同一个独立 agent 的合并审查，不重复任何已完成模型、选择或四现金 phase。

## 调研判断与反思

本次工作实现调研结论：原 148 ledger writer 已明确拥有账户目录创建权，wrapper 不能重复创建。恢复来源必须分开披露，旧现金 d640 与新报告 e7bb 不可混成同一次源码运行。这是 I/O 证据链修复，没有新增 alpha 假说。

开始/结束新增过拟合：否。修复由真实 FileExistsError 和目录所有权合同触发，没有依据财务表现改特征、时钟、风险、费用或 gate；历史同史择题风险仍在。

开始/结束继续价值：是，限于完成原四书的报告和审查。现金已经计算完成，重新运行资金会浪费预算并污染来源；本次显式 report-only 可以保住原路径并产出可审查结果。工程修复不是策略进步，goal active，未授权晋级、加注或生产。
