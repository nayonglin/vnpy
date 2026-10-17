# Stage251：同源数据副本与实际路径补数记录

- 记录时间：2026-10-15 20:37 +0800。
- 所属研究线：`futures_trend_rollover_shape_same_volume`。
- 工作位置：MAIN 的 `codex/stage251-disable-half-r-stop` 分支；遵照用户最新要求，没有新建工作树。
- 本记录负责数据与来源证明；策略开关、会计及回测绩效由主阶段记录和独立审计负责。本次数据准备不是新 alpha 突破。

## 固定窗口与隔离

A/C 均采用 2020-01-01 至 2026-10-14。源数据为 Stage249 已修复并验收的 FIX 工作区，初始分钟缓存 SHA 为 `a9566e64c1165a5fd0e62bbae6191b522526646a081e724064876a24bc80a74e`。

复制前先核碰撞。MAIN 已有 6,026 个下载文件逐 SHA 与 FIX 相同，保持原状；只新增缺少的 6 个下载文件、38 个 backtest_outputs 文件和数据库/本地配置 2 个文件，共 46 文件、519,405,479 字节。所有 6,072 项均与 FIX 不同 inode。没有覆盖已有不同内容，没有修改旧 FIX、OLD、Stage249 或 Stage250 研究文件。

证据：`../outputs/stage251_half_r_ab/data_preparation/copy_plan.json`、`copy_report.json`。随后独立审计确认 MAIN 的 6,233 项回放输入 SHA 与 Stage249 一致。

## 解释器与工具

实际解释器继续为 `MAIN/.py311/bin/python`（Python 3.11.5），进程 PYTHONPATH 复用已验收 Documents runtime site-packages；没有安装包或替换 MAIN venv。实测 pandas 2.3.3、pyarrow 23.0.1、numpy 2.4.4、sklearn 1.8.0、TqSdk 3.9.4、TA-Lib 0.6.8，可完成 parquet 内存往返。环境证据为 `data_preparation/runtime_overlay.json`。

复用六个未修改的 Stage249 数据工具。新增 `tools/stage251_data_paths.py`，用同一个 `qmt_roll_intraday_execution.py` 的交易日 grid 构造实际入场后缀和普通成交首分钟。显式 `--allow-empty-entry` 允许关闭机制后合法空入场集合；普通锚仍须逐键验源。`--allow-cache-change` 仅用于候选文件验源，并明确标记其不是已消费输入身份。

9 项新增单测经历先红后绿，35 项原数据窄测通过；独立审计复核新增 9 项与薄适配逻辑通过。旧 strict_final 对 MAIN 初始副本回归验源：106,731 个 union 分钟全闭环、零缺口。

## C_diagnostic2 实际缺口

317 条入场扫描形成 1,227 个时段；其中缺 6 段、585 分钟可信源。558 个普通成交首锚缺 30 个可信源，其中 6 个已有缓存而没有完整源证明。去重后的差集为 34 段、613 分钟。再次逐分钟检查，613/613 均缺可信源，且与旧 504 个任务已证明分钟交集为零。

旧完成 raw 快照复用 5 个首分钟，保留 parent proof SHA。剩余 29 段、608 分钟按小于 14 自然日批次下载，共 20 批；首批成功后最多 3 路稳定日期分片（7/7/6 批）。行情使用 TqSim，合约各自独立 10,000 根 serial；没有 CTP、委托或撤单调用。所有批次成功，未发生失败/限流；原始快照、边界、SHA、完整 grid 和片段 OHLC/量/持仓逐值证据保留。

路径：`C_diagnostic2_data`、`minute_reused_C_diagnostic2`、`minute_additional_C_diagnostic2`；每次命令及准备来源保存在 `data_preparation` 和 `minute_additional_C_diagnostic2/commands.json`。

## 候选审计和原子合入

34 个任务形成 25 个 proof、613 分钟。独立审计重算 raw→patch→candidate 的 4,291 个七字段数值，全部精确相等。原 1,410,508 个旧时间键七字段均未改变；6 个重叠键只刷新来源标签，607 个新增键，零旧键删除。候选总行数 1,411,115。

候选对 A_round1 的 106,515 入场分钟和 535 首锚、C_diagnostic2 的 105,705 入场分钟和 558 首锚均完成独立来源闭环，零缺口/零无证明/零值差。

新 30 个锚中 29 个与原诊断价时一致，唯一差异为 SH601.CZCE、交易日 2025-08-28 的平仓（order BACKTESTING.509 / trade BACKTESTING.557）：诊断价 2688、当日 09:00；真实首分钟为 2025-08-27 21:00、open 2702。因此要求重新生成 C 实际路径，不能继承诊断绩效。

在 root 明确确认无引擎运行、执行审计退出且独立候选 PASS 后，于 2026-10-15 20:31 原子合入 MAIN 私有缓存。最终 SHA 为 `d178037361e0a293de342080798064f7eeb1d507b110de2ef8f273fd6f6d59c0`。新增 patch manifest SHA 为 `688f62bbe2191b0b42fa0efa178238be501176d370bc59ac76781f9b29c53360`。完整旧缓存 a956 备份及原子替换报告均位于 `C_diagnostic2_candidate/actual_merge/`；旧 FIX 保持 a956、OLD 保持 e78af805…60b9。

## 当前验收边界与后续

A_final 和 C_diagnostic3 已开始，缓存、数据库及模型输入保持冻结。接下来只读验证新实际集合；C 新路径零缺口后再由 root 运行 strict C_final。最终绩效和同源比较须绑定各自 strict run_provenance 与同一实际缓存 SHA，不能把候选验源当成已执行验证。

数据准备没有新增、调整或筛选任何策略参数。它不构成过拟合：补数集合由实际数据请求和完整来源差集确定，没有按收益挑日期；继续有价值，因为首锚变动可能改变后续仓位路径。研究记录不改 LINE.md、registry.md 或根总账，留给主线程统一整理。

官方资料复核：TqSdk [API 文档](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html) 与 [SDK 实现](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)确认 10,000 根上限；多合约对齐 serial 会改变可见时间集合，所以沿用每合约独立 serial，并逐请求分钟验收。

## 最终轻量绑定（2026-10-15 20:51 +0800）

后续路径检查仅新增 rb2605.SHFE、2026-01-15 21:00 的 1 分钟，离线复用旧完成快照。raw、patch、C_diagnostic4 trade/clock 均为 3165@21:00，价时完全等价；独立审计确认其余 1,411,115 行整行不变。20:46 原子合入后最终缓存 SHA 为 `5c06124fac52ff37a19d1abe89f6f6a80d36b8ece874eb647286377317289189`，共 1,411,116 行；Stage251 累计新增任务 35 段、614 分钟，两个旧缓存版本均有完整备份，旧 FIX/OLD 保持不变。

此前 A_final/C_diagnostic3 因共享路径 guard 退出，未作为验收结果；入口调整后使用 A_final2/C_diagnostic4 证明，再完成 A_final3/C_final 严格双跑。遵照用户收窄范围，不再做全量重复源扫描。最终 A_final3 的 501 个 entry 请求和 535 个 anchor 请求、C_final 的 317 个 entry 请求和 558 个 anchor 请求，与已完整验收候选集合逐键多重集相等；覆盖状态全 complete，entry 实际数量等于期望且零 missing，anchor 实际时刻等于统一 first。两次严格运行均绑定同一最终 cache SHA，运行输入未变、捕获异常为零。

`../outputs/stage251_half_r_ab/final_data_binding.json` 记录当前请求/旧已验收请求/继承证明/run_provenance 的 SHA 与绑定结果，状态 complete。来源证明复用的 A 实际 union 为 106,731 分钟，C 为 105,946 分钟；最终运行后没有修改任何输入。数据正确性闭环完成，策略绩效以主阶段最终严格运行和独立会计/执行审计为准。
