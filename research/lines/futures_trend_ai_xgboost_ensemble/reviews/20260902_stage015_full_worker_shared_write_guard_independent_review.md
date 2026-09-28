# Stage015 full-worker shared-write guard 独立评审

## 结论先行

- 门禁结论：`STOP`
- 严重度计数：`P0=0`、`P1=1`、`P2=1`
- 当前 runner SHA256：`ec5199c0df6c7d1013f7f3b4256354a6d0d361c18361c7271576a5f556560855`，与送审值一致。
- 本轮确认 import-by-value 的实际执行绕过已被 outer redirect 覆盖；但 worker receipt 声称的 `original_shared_builder_call_count=0` 不是运行时观测值，而是恒定初始化值。receipt/validator/smoke/aggregate 因而不能阻断未扫描引用对原 builder 的调用，不满足本轮明确要求的 fail-closed 证明。
- 旧 review 均保留；runner、tests、artifacts 未修改。本轮未读取或分析任何 label 收益分布，未执行真实 shared builder、模型训练、CTP 或订单 API。

## P0

无。

## P1

### P1-1：`original_shared_builder_call_count` 为恒定 0，receipt 不能证明原 builder 未调用

证据链：

1. `_redirect_shared_builder_bindings` 在 runner 第 1339 行把 `audit["original_shared_builder_call_count"]` 初始化为 `0`。
2. 两个 redirect 只递增各自的 redirect call count；代码中没有包装、替换或监测 original function object 的调用，也没有任何路径递增 `original_shared_builder_call_count`。
3. worker 第 1671-1673 行把该恒定值写入 receipt；completed-job validator 第 1879 行、smoke 第 2186 行、aggregate 第 2474 行只检查其等于 0。
4. 因此，只要出现 module-global 扫描范围外的引用，例如定义期默认参数、closure cell、提前缓存的局部变量、对象属性、partial/container 或 reload 后的新函数对象，原 builder 即使被调用，该字段仍会是 0，后续所有 gate 仍可能通过。

本轮对象 probe 对当前冻结加载图未发现上述隐藏引用，且通过临时保持原函数对象身份、把其函数体改成调用即失败的只读保险，实测原 universe/eligibility 调用数均为 0；这说明当前已知路径已修好，但一次 reviewer probe 不能替代 355 个 worker 自身的持久 fail-closed receipt。门禁要求审查的是 receipt 是否足以阻断，当前答案是否定的。

最低闭环要求：worker 在 outer context 前后记录并校验两个共享源的 `dev/inode/size/mtime_ns/SHA256` 完全一致，并让“原函数调用数”来自真实拦截/计数机制；若保留该字段，不得用固定初始化值充当观测值。相应 validator、smoke、aggregate 及负向测试须验证任一原调用或任一共享文件身份变化都会失败。

## P2

### P2-1：binding receipt 只校验数量和列表长度，不校验实际绑定集合

当前 context 自身要求 universe/eligibility 各至少 3 个绑定，真实 worker 加载图也正好是 3+3；但 receipt 仅保存一个总数与字符串列表，validator 只要求总数 `>=6` 且列表长度等于总数，没有要求两类各自数量，也没有锁定六个关键绑定名称。另有一个恢复边界：初次扫描后、context 内新加载并执行 `from origin import ...` 的模块会取得 redirect，但该新绑定不在初始 `bindings` 中，outer finally 不会恢复它。当前冻结执行链没有观察到这种动态加载，所以列为 P2，不单独阻断。

## 已通过核查

### 真实对象链与绑定覆盖

- 真实对象链确认：`s901.s847.s825.stage819_cfg -> stage813_cfg.stage777_cfg`。
- Stage777 两个函数的 origin 均为 `run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest`。
- worker production modules 加载后，按对象身份找到恰好 6 个直接绑定：origin、`qmt_roll_official_stage78_config`、`qmt_roll_official_candidate_stage777_config` 各持有 universe/eligibility 两个绑定。
- context 内 6 个绑定全部变为 redirect；origin module attr 同样被替换，context 内新执行 `from origin import ...` 得到的也是 redirect。
- 对真实已加载 production 函数、类方法及模块值扫描，未发现原函数藏于 positional defaults、keyword defaults、closure、partial 或容器。
- 对 production portfolio 全部 Python 源码做 AST/文本核查，发现 7 个模块存在 import-by-value；当前 worker 路径实际加载其中 Stage78、Stage777 两个消费者和 origin。未发现以两个 builder 为默认参数或模块级容器别名的代码，也未发现该链使用 `importlib.reload`、删除 `sys.modules` 或动态重载 origin。

Python 官方语义支持上述审查边界：import 会把结果绑定到导入方名字，module cache 位于 `sys.modules`；函数 global 名称运行时解析，而默认参数在函数定义时只求值一次。参考：

- https://docs.python.org/3.11/reference/import.html
- https://docs.python.org/3.11/reference/executionmodel.html
- https://docs.python.org/3.11/reference/compound_stmts.html#function-definitions

### metadata、run-profile 与嵌套恢复

- outer context 位于真实 worker 的 `s513._metadata()`、`s901._ensure_c9_minute_bars()` 和完整 `_run_live_c9_with_frozen_builders()` 外层。
- 真实 `s513._metadata()` probe 后，universe/eligibility redirect call count 为 `1/1`，metadata 非空，`vt_symbols=798`。
- 真实 `s847._run_profile` 第 520 行通过其 module global `s513._c3_overrides(...)` 再走 Stage324 -> Stage78；对象核查确认该 `s513` 与 worker 的 `s513` 是同一模块。直接调用这一精确目标后计数变为 `2/2`，两个 override path 均为 campaign 私有文件。
- 在 inner helper 的等价边界 probe 中，Stage819 profile builder 返回 frozen profile，profile 的 universe/eligibility 均为私有路径；Stage777 两个名字处于调用即失败 guard，live builder 返回 candidate snapshot。
- inner helper 正常返回后恢复为 outer redirects；inner 边界主动抛异常后也恢复为 outer redirects。outer 正常退出及主动抛异常后，六个初始绑定与 Stage777/Stage819 属性均恢复原对象。

### 共享文件只读证据

两轮对象/行为 probe 都没有执行真实 shared builder。行为 probe 额外对共享目标的 `open/Path.open/DataFrame.to_csv/os.open/os.replace` 设置调用即失败保险，并对两个 original function object 设置调用即失败计数器；结果：

- original universe calls：`0`
- original eligibility calls：`0`
- shared write attempts：`[]`
- universe 始末：`dev=16777232`、`inode=422227924`、`size=6272`、`mtime_ns=1788283354851973304`、`SHA256=72c5ca576bfe8aebe12da1e750d9eac980633a43ab9944479a77a7e824a71e34`
- eligibility 始末：`dev=16777232`、`inode=422227925`、`size=51303`、`mtime_ns=1788283354864122779`、`SHA256=fa5fb5c1cfe06ace44dadc92bd2cc1a77bd4ee74beeab362234952950ca5bb3b`

两文件五元身份与 SHA256 始末完全一致。

## 测试边界

- 已审阅新增真实 production metadata 测试及既有完整 `_run_live_c9` 等价边界测试；新增测试确实调用真实 `s513._metadata()` 并检查共享文件身份不变、redirect 被调用、Stage777 恢复。
- 本轮在用户要求立即停止扩展后没有继续运行 Stage015 26 项或整线 94 项测试，因此不把提交方报告的 `26/26`、`94/94` 记为独立复验结果。
- 现有测试没有证明 receipt 的 original-call 字段来自真实计数，也没有负向注入一个扫描外原函数调用并要求 worker/validator 失败；这正是 P1-1 未闭环之处。

## campaign 状态

- `campaign_20260902T003958+0800_80965/ABANDONED.json` 存在。
- `LATEST.json` 为 `status=abandoned`、`reuse_forbidden=true`，旧 campaign 不可复用。
- 本轮没有创建或运行新 campaign。

## 过拟合与继续价值

- 过拟合判断：`否`。本轮只审查执行隔离、Python 名称绑定、文件身份和 receipt 门禁，没有观察部分 label 的收益、分布或策略表现，也没有调整冻结合同。
- 继续价值判断：`有，但仅限修复 P1 后重新评审`。当前 known call graph 的 import-by-value 绕过已经修复，工程方向有效；但在 worker 自证仍可产生假阴性时启动 355-job campaign，会再次把可避免的基础设施不确定性带入昂贵批量计算。先补真实 original-call/shared-file-identity fail-closed，再创建全新 campaign。

