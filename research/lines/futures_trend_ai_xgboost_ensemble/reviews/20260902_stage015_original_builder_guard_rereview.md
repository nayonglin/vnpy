# Stage015 original builder guard 独立复审

## 结论先行

- 结论：`ALLOW_NEW_CAMPAIGN`
- 严重度：`P0=0`、`P1=0`、`P2=0`
- 上一轮 `20260902_stage015_full_worker_shared_write_guard_independent_review.md` 的 P1/P2 已闭环：原始函数对象现在有真实计数且调用即失败；共享源有 worker 内始末七项身份封印；context 内新出现的 import-by-value redirect 会在 finally 二次扫描并恢复；receipt 三层消费统一走同一个 fail-closed gate。
- 本结论只允许从零创建全新 campaign。`campaign_20260902T003958+0800_80965` 继续废弃且禁止复用；本复审没有运行 smoke/full batch，也没有授权跳过新 campaign 的既有冻结门禁。

## 审查边界与身份

- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- line_id：`futures_trend_ai_xgboost_ensemble`
- runner SHA256：`1033b573d3c9faf6f9630acf637649127c8731adaa639f4d66e65c84c51a1c92`，与送审值一致。
- tests SHA256：`b1bd4fdaa2f191bbb80874c7b6534b7062c66dacd6dcfe300139cb728f41d541`
- 上一轮 review SHA256：`49ab94a73b05971a6117b0e2116ef48c074909f00c2b7a2f482169acd9ca97d9`
- runner、tests、campaign、artifacts 及旧 review 均未修改；唯一新增文件为本 review。
- 未读取或分析 campaign label/收益分布，未执行真实 shared builder，未训练模型，未连接 CTP，未调用订单 API。

## P0

无。

## P1

无。

上一轮 P1 已通过以下静态证据、真实对象 probe、异常 probe 和测试共同关闭。

## P2

无。

上一轮 P2 的 required-binding 可信度与动态 import 恢复缺口已关闭；未发现新的可操作 P2。

## 1. 原始函数对象 guard

runner 第 1333-1344 行定义 universe/eligibility 两个 blocker。context 从真实 Stage777 取得两个 original function object 后：

1. 在原函数的 `__globals__` 注入本次 audit；
2. 保存原函数的 `__code__`、`__defaults__`、`__kwdefaults__`；
3. 保持函数对象身份不变，把 `__code__` 换成 blocker code；
4. blocker 分别递增 universe、eligibility 和 total original-call count，随后立即抛错；
5. finally 逆序恢复 code/defaults/kwdefaults，并删除注入的 guard global。

该设计覆盖所有仍指向同一函数对象、但不在 module-global 扫描范围内的引用。Python 官方数据模型明确区分函数对象身份及其可写的 `__code__`、`__defaults__`、`__kwdefaults__`，并说明 `__globals__`/`__closure__` 的绑定语义：

- https://docs.python.org/3.11/reference/datamodel.html#user-defined-functions
- https://docs.python.org/3.11/reference/compound_stmts.html#function-definitions

独立真实 production 对象 probe 缓存了以下五种扫描外引用，并对 universe/eligibility 各调用一次：

- 局部变量
- 定义期默认参数
- closure cell
- 对象属性
- `functools.partial`

结果：10 次调用全部抛出对应 `stage015_original_shared_builder_called:*`；audit 为 universe `5`、eligibility `5`、total `10`，context 退出再以 `stage015_original_shared_builder_call_detected` fail closed。退出后两个函数的 code/defaults/kwdefaults、Stage777 绑定和 guard global 全部按对象身份恢复；共享源身份未变化。

真实正常 production 路径的 audit 为 universe original calls `0`、eligibility original calls `0`、total `0`，证明 receipt 字段来自运行时 blocker 计数，不再是上一轮的固定占位值。

## 2. 共享源始末封印与不发布

`_shared_builder_source_identity` 持久记录并比较两个共享源的：

- `path`
- `dev`
- `inode`
- `size`
- `mtime_ns`
- `ctime_ns`
- `sha256`

context 在安装 guard 前读取 before，在 body 结束或抛错后的 finally 读取 after，并要求两个完整字典严格相等。original call count 非零、任一身份变化、after 不可读都会设置 post error；恢复动作仍在嵌套 finally 中执行。

独立 probe 结果：

- 模拟 after 身份不可读时，context 抛出 `stage015_shared_builder_source_identity_unreadable`；`source_identity_pass=false`、after 为 null，两个函数 code、Stage777 绑定和 guard global 仍全部恢复。
- source-change 单测修改临时共享 universe 后，抛出 `stage015_shared_builder_source_identity_changed`，before/after 不同且绑定恢复。
- synthetic worker 注入同一 source-change 错误后，final job output 不存在、partial output 数为 `0`、worker receipt 不存在。
- 代码顺序也保证 final rename 位于 context 成功退出之后；任一异常进入 worker 外层 `except BaseException` 并删除 partial directory。

真实共享源本轮所有 probe、Stage015 tests 和整线 tests 始末一致：

- universe：`dev=16777232`、`inode=422227924`、`size=6272`、`mtime_ns=1788283354851973304`、`ctime_ns=1788283354851973304`、SHA256=`72c5ca576bfe8aebe12da1e750d9eac980633a43ab9944479a77a7e824a71e34`
- eligibility：`dev=16777232`、`inode=422227925`、`size=51303`、`mtime_ns=1788283354864122779`、`ctime_ns=1788283354864122779`、SHA256=`fa5fb5c1cfe06ace44dadc92bd2cc1a77bd4ee74beeab362234952950ca5bb3b`

## 3. context 内新 import-by-value 恢复

finally 调用 `capture_bindings(original_values=False, dynamic=True)`，按 redirect 对象身份再次扫描当时全部 `sys.modules`；新发现的绑定加入同一 restore list，增加分项 binding count 与 `dynamic_binding_restore_count`，随后统一恢复为 original function object。

独立 probe 在 context 内创建真实 module 并执行：

```python
from <origin> import build_static18_plus_fu_universe
from <origin> import build_ai_satellite_post_signal_eligibility
```

正常退出和 body 主动抛异常两条路径均得到：

- context 内两个新名字为 redirect，不是 original；
- `dynamic_binding_restore_count=2`；
- 最终 binding count `8`，universe/eligibility 各 `4`；
- 退出后两个新名字均恢复为 original；
- body 原异常保持原样传播，guard 和共享源 seal 均通过。

Python import 语义说明 import 同时执行模块查找与名字绑定，`sys.modules` 是已加载模块缓存；本实现的二次对象身份扫描与该语义一致：

- https://docs.python.org/3.11/reference/import.html

## 4. 六个 required bindings 与分项计数

真实对象链再次确认：

`s901.s847.s825.stage819_cfg -> stage813_cfg.stage777_cfg`

两个 shared builder 的 origin 均为 `run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest`。worker 初始真实加载图恰好有六个关键直接绑定：

1. origin universe
2. origin eligibility
3. Stage78 universe
4. Stage78 eligibility
5. Stage777 universe
6. Stage777 eligibility

runner 不再只依赖总数：它逐一验证六个 namespace/key 当前是否为正确 redirect，并要求 ordered `shared_builder_required_bindings` 精确等于冻结常量；同时要求 universe/eligibility 各至少 `3`，总数严格等于两个分项之和。真实 production audit 为总数 `6`、universe `3`、eligibility `3`、required coverage true。

## 5. receipt 与统一 fail-closed gate

worker receipt 现持久记录：

- universe/eligibility/total original-call runtime counts
- guard installed
- before/after 两套共享源七项身份及 identity pass
- required six binding list及 coverage pass
- total/universe/eligibility binding counts
- redirect call counts
- dynamic restore count及完整 binding list

`_shared_builder_receipt_gate` 是唯一共享门禁实现，并由以下三处直接调用：

- `_validate_completed_job`
- smoke 的 `timeout_and_identity`
- aggregate 的 `worker_identity_pass`

独立构造一份通过 receipt 后执行 31 个负向篡改，全部被拒绝，覆盖：

- 四个布尔 guard/identity/coverage 标志
- required list 缺项与乱序
- universe/eligibility 分项绑定不足、总数不一致、binding list 长度不符
- 两个 redirect call count 归零
- universe/eligibility/total original-call 非零或不一致
- dynamic restore count 为负
- identity 缺失
- universe 与 eligibility 各自的 path/dev/inode/size/mtime_ns/ctime_ns/SHA256 任一变化

已有 completed-job 单测也实际篡改 source pass 和 original-call counts 并确认拒绝。receipt 不再接受上一轮那种“固定 total=0 即通过”的伪证据。

## 6. 真实 production 路径

独立 probe 使用真实 s513/s901/Stage847/Stage819/Stage777 对象，且未执行真实 shared builder：

1. outer guard 内真实执行 `s513._metadata()`，得到 `798` 个 vt_symbols；两个 redirect call count 为 `1/1`。
2. inner helper 内 Stage777 两个 module name 均已换成调用即失败 guard，Stage819 profile builder 为 frozen profile，live builder 为 candidate snapshot。
3. 真实执行 Stage847 `_run_profile`，只把 engine/dependency 换成无回测副作用的 probe doubles，并在 `_build_setting` 入口主动停止；Python 已先求值第 520 行 `base_c3_overrides=dict(s513._c3_overrides(...))`，实测 universe/eligibility 都是 campaign 私有路径，redirect counts 增至 `2/2`。
4. `_run_profile` 的 START/END/PRELOAD 全部恢复；inner helper 返回后 Stage777 恢复 outer redirects、Stage819 恢复原 profile builder；outer 退出后 Stage777、原函数 code 和 guard global 全部恢复。
5. production audit：original calls `0/0/0`、source identity pass true、required six coverage true、binding count `6=3+3`。

这同时证明 metadata、`_run_profile` 的 Stage324 -> Stage78 路径以及 inner helper 的 frozen Stage819 路径均受同一个 outer guard 覆盖。

## 7. 测试、旧 campaign 与标签边界

独立运行：

```text
Stage015: 30 passed in 14.27s
整线:     98 passed in 15.97s
```

运行参数包含 `PYTHONDONTWRITEBYTECODE=1`、`-p no:cacheprovider`、独立 `/private/tmp`/MPL 路径；测试后 runner/tests/旧 review/LATEST/ABANDONED 和共享源身份均未变化。

旧 campaign 状态：

- `LATEST.json` SHA256=`99af08a3a69cd2f1c0c68551d1412a9a6b72216fb5e95bdd6b598dd4091c0f3e`，仍为 `status=abandoned`、`reuse_forbidden=true`。
- `campaign_20260902T003958+0800_80965/ABANDONED.json` SHA256=`52c9fce25bc271d70c7920e28b640e42fababb82352100c83936901c8b302cbb`。
- artifacts 根目录始终只有原四个 campaign，没有新 campaign。
- 全部 Stage015 campaign 下不存在 `development_labels.csv`。
- 本轮只核查文件存在性和执行隔离，没有读取 job label 或分析收益分布。

## 过拟合与继续价值

- 过拟合判断：`否`。本轮只验证 Python 对象身份、异常恢复、共享文件封印、receipt 门禁和测试，不消费策略收益或标签分布，不调整任何策略参数、样本、特征或冻结合同。
- 继续价值判断：`有`。上一轮阻断属于可证伪的基础设施完整性问题，当前实现已经用函数对象级 guard、共享源七项身份封印、动态绑定恢复和统一 receipt gate 闭环。下一步有价值的动作是从零创建一个全新 campaign 并按冻结流程先跑 4-job smoke；旧 campaign 和旧 outputs 继续禁止复用。

