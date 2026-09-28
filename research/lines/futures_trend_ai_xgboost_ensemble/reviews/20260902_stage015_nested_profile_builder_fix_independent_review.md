# Stage015 nested profile builder 修复独立复审

- 评审时间：`2026-09-02 01:27 +0800`
- 评审对象：Stage015 development label batch runner、对应 tests、真实 production 模块对象链
- runner SHA256：`6d4c5937aa4834e86ac7f1cc66a747b4d0188be0181175fd079edf90576db5f3`
- test SHA256：`d99a764925ea28696e8e9137441a7a7d1993a873e2d96ec96020bb307b9ae90d`
- 旧 smoke campaign：`campaign_20260902T003958+0800_80965`

## 结论先行

- `VERDICT: FAIL`
- 严重度：`P0=0 / P1=1 / P2=1`
- 最终决定：`STOP`
- 本次修复正确封住了 `_c9_profile -> s825.stage819_cfg -> stage813_cfg.stage777_cfg` 这一条已知写路径，新增 profile overrides/private eligibility 的 freeze、identity、worker receipt、validator、smoke、aggregate 也能闭环；四函数 `finally` 在正常返回和异常抛出时均可恢复。
- 但完整 worker 仍有另一条 import-by-value 的 Stage78 路径调用同两个真实共享 builder，而且存在两处调用点：一处在 helper 之前的 `s513._metadata()`，另一处在 helper 内部执行的真实 `s847._run_profile()`。当前只替换 Stage777 模块上的名字，不能覆盖 Stage78 模块自己的绑定。
- 因此 full worker 仍会反复覆盖 shared universe 与 shared post-signal eligibility；`nested_shared_builder_guard_enabled=true` 仍可能在发生共享写后进入 receipt，现有 `25/25` 测试没有覆盖真实 `_run_profile -> s513._c3_overrides` 边界。

## P0

无。

## P1

### P1-1：Stage78 的独立 import-by-value 绑定绕过 Stage777 guard，worker 仍会写共享 CSV

#### 第一处：helper 调用前的 metadata 构造

1. Stage015 worker 在 runner `:1419-1421` 加载 production 模块后先执行 `metadata = s513._metadata()`；直到 `:1430-1435` 才进入 `_run_live_c9_with_frozen_builders()`。因此 helper 内的任何 guard 都无法保护 metadata 阶段。
2. production `analyze_qmt_roll_stage513_stage208_exact_position_margin_audit.py:179-182` 的 `_metadata()` 先调用其模块全局 `_c3_overrides()`。
3. 该名字在 Stage513 `:26` 由 `from analyze_qmt_roll_stage324_true_combo_capital_margin import _c3_overrides` 绑定；Stage324 `:123-127` 又调用其模块全局 `build_official_stage78_overrides()`。
4. Stage324 `:14-18` 通过 `from qmt_roll_official_stage78_config import build_official_stage78_overrides` 持有 Stage78 builder；Stage78 config `:6-11` 再以 import-by-value 持有：
   - `build_static18_plus_fu_universe`；
   - `build_ai_satellite_post_signal_eligibility`。
5. Stage78 `build_official_stage78_paths()` 在 `:107-110` 无条件调用这两个名字；真实函数分别在 robustness runner `:121-133` 和 `:186-204` 用 `DataFrame.to_csv()` 覆盖 shared CSV。

#### 第二处：helper 内的完整 `_run_live_c9` 执行边界

1. `s901._run_live_c9()` 在 production Stage901 `:846` 构造 `_c9_profile()`，在 `:868` 调用 `s847._run_profile()`。
2. 本次修复确实让 `_c9_profile -> s830 -> s827 -> s825._profile` 在 Stage825 `:89` 取得 frozen Stage819 profile snapshot，不再进入 Stage777 builder。
3. 但 Stage847 `_run_profile()` 在 `:517-522` 构造 setting 时再次执行 `s513._c3_overrides(START...)`，随后沿上述 Stage324 -> Stage78 路径再次调用两个共享 builder。
4. runner helper `:1319-1355` 只替换 `stage777_cfg.build_static18_plus_fu_universe` 和 `stage777_cfg.build_ai_satellite_post_signal_eligibility`。它没有替换 Stage78 config 的两个模块全局名，也没有在 metadata 阶段建立 guard。

#### import-by-value 独立证据

只读对象身份 probe（只做导入、取 `__globals__` 和内存赋值，不调用 builder）确认：

- `s513._metadata.__globals__["_c3_overrides"]` 正是 Stage324 函数；
- Stage324 `_c3_overrides.__globals__["build_official_stage78_overrides"]` 正是 Stage78 函数；
- Stage78 和 Stage777 初始绑定指向相同两个原始函数对象；
- 将 Stage777 的两个模块属性替换为 guard 后，Stage78 `build_official_stage78_paths.__globals__` 仍持有两个原始函数，均不是 guard；
- Stage847 `_run_profile` 使用的 `s513._c3_overrides` 与 metadata 路径是同一函数对象。

这符合 Python 的名字绑定语义：`from module import name` 会在导入方模块命名空间建立独立绑定；给另一个模块属性重新赋值，不会联动更新该绑定。

#### 影响

- 每个 worker 至少会经 metadata 和 `_run_profile` 两次进入 Stage78 paths；每次分别调用 universe/eligibility builder，即当前已知至少 `4` 次共享 builder 调用/worker。
- `MAX_WORKERS=2` 时仍存在共享覆盖写并发；完整 `355` job 会放大该副作用。
- 两个 shared CSV 不在 `_collect_campaign_files()` 中：production tree identity 只收 `.py`，当前 `product_universe`、Stage819 profile eligibility 均指向 campaign-private snapshot。因此共享写不会造成 campaign/worker identity drift。
- worker receipt 在 runner `:1564-1571` 无条件声明 profile snapshot SHA 和 `nested_shared_builder_guard_enabled=true`；validator 只能验证 snapshot SHA 与该布尔声明，不能证明 Stage78 路径未写共享文件。该 P1 可以在现有 receipt/smoke/aggregate gates 全绿时继续存在。

#### 测试缺口

- 新测试 `test_full_live_c9_boundary_never_calls_nested_shared_builders` 在 test `:283-298` 使用简化 `S901._run_live_c9`，只依次调用 Stage819 profile builder 和 live builder。
- 它没有模拟真实 Stage901 `:868` 的 `_run_profile()`，也没有模拟 worker helper 前的 `s513._metadata()`，所以无法覆盖 Stage78 绕过。
- `25/25` 和 `93/93` 绿色只证明当前测试合同通过，不能关闭这条真实生产调用链。

#### 关闭条件

1. 把共享写禁止边界提升到完整 worker 作用域，覆盖 helper 前的 metadata 和 helper 内的 `_run_profile`；或改为完全从冻结 private snapshot 构造 metadata/base overrides，使 worker 不调用任何会写共享输出的 builder。
2. guard 必须覆盖实际运行时 Stage78 模块绑定；仅替换 origin module 或 Stage777 的同名属性均不足以覆盖全部 import-by-value 引用。
3. 增加真实等价测试，至少同时执行 metadata 构造路径和 `_run_profile` 的 base overrides 构造路径；把 Stage78、Stage777 及 origin module 的共享 builder 都设为调用即失败，并验证全程调用数为 `0`。
4. 修复后重新跑专项/整线测试和独立复审；旧 campaign 继续禁止复用，后续只能从 prepare 创建全新 campaign。

## P2

### P2-1：顶层 `LATEST.json` 仍把已废弃 campaign 标为 smoke passed

- 旧 campaign 的 `ABANDONED.json` 已为 `status=abandoned`、`reuse_forbidden=true`，`failure_receipt.json` 也明确禁止复用；runner 的 `_campaign_reuse_forbidden()` 会对任何含 `ABANDONED.json` 的显式目标 fail closed，因此这不是当前 P1 的替代阻断项。
- 但 artifacts 根目录 `LATEST.json` 仍指向 `campaign_20260902T003958+0800_80965`，并保留 `status=smoke_passed` 与旧的 full-batch 许可 decision。外部状态查看器或人工读取可能得到与 authoritative tombstone 相反的信息。
- 后续 abandonment 流程应原子更新 `LATEST.json` 为 abandoned/reuse-forbidden 状态，或让消费方解析 LATEST 后强制复核目标 campaign tombstone。

## 已通过的修复项

### 真实 Stage819 对象链与已知 profile 写路径

- runtime object probe 全部为 `true`：
  - `s901.s847.s825.stage819_cfg` 是实际 Stage819 config module；
  - `s825._profile.__globals__["stage819_cfg"]` 与该对象相同；
  - `stage819_cfg.stage813_cfg.stage777_cfg` 是实际 Stage777 config module；
  - Stage819/Stage813 path builders 的模块全局分别指向上述 Stage813/Stage777 对象；
  - Stage777 path builder 的 `__globals__` 就是 Stage777 模块命名空间。
- 因此本次对 Stage819 profile builder 与 Stage777 两个名字的替换，确实能关闭上一份 review 指出的 `_c9_profile -> Stage819 -> Stage813 -> Stage777` 路径；问题是它不是完整 worker 中唯一共享写路径。

### freeze、manifest、receipt 闭环

- prepare 在 runner `:1682-1691` 依次冻结 live overrides/private universe、Stage819 profile overrides/private eligibility，再构建 campaign identity。
- profile eligibility snapshot 在 `:1202-1255` 校验 source before/after identity、bytes SHA/size、必需 CSV 列和非空 symbol，并以文件 `fsync + replace` 落到 campaign-private 路径。
- Stage819 freeze 在 `:1258-1287` 校验 shared universe 与既有 private universe 的 size/SHA 相同，重写 universe/eligibility 两个路径，再保存 profile overrides。
- 两个新增文件在 runner `:171-192` 纳入 worker exact keys，在 `:739-821` 纳入 campaign identity；worker execution manifest 会在执行前后 fresh 重算并比较。
- worker receipt 写入两个 snapshot SHA 和 guard 声明；completed-job validator 在 `:1755-1771` fresh 重算两份 SHA。smoke 与 aggregate 都先调用 completed-job validator，因此 snapshot/manifest/receipt 本身闭环。

### finally 恢复

- helper `:1332-1355` 在替换前保存四个原对象，并在无条件 `finally` 中逐一恢复，没有 `return` 或异常吞噬逻辑。
- 使用真实 production 模块对象、但把完整边界替换为不运行回测的内存 probe 后，正常返回和主动抛出 `probe_boundary_failure` 两种路径均观察到四个替换已生效，随后四个对象全部恢复。
- 因此 `finally` 自身安全；当前 P1 来自替换集合不足，不是恢复失败。

### 旧 campaign 禁止复用

- `campaign_20260902T003958+0800_80965/ABANDONED.json` SHA256 为 `52c9fce25bc271d70c7920e28b640e42fababb82352100c83936901c8b302cbb`，字段为 `status=abandoned`、`reuse_forbidden=true`。
- failure receipt 同时声明 `partial_job_outputs_reusable=false`、`development_labels_published=false`。
- worker、resume、pending jobs、smoke 和 aggregate 都会调用 reuse guard；该 campaign 不能由当前 runner 合法续跑。

## 测试与 probes

执行：

```bash
env QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR=1 PYTHONDONTWRITEBYTECODE=1 \
  MPLCONFIGDIR=/private/tmp TMPDIR=/private/tmp \
  .py311/bin/python -B -m pytest -p no:cacheprovider \
  research/lines/futures_trend_ai_xgboost_ensemble/tests/test_stage015_development_label_batch.py -q
```

结果：`25 passed in 1.56s`。

整条研究线 tests：`93 passed in 3.70s`。

测试前后两个 shared CSV 的 inode、size、mtime 均未继续变化，说明 pytest 本身没有执行真实共享 builder。

## 审查过程偏差披露

- 第一个行为 probe 为取得真实 metadata，在安装写监控和 Stage78 guard 之前调用了 `s513._metadata()`。这一步经本次新发现的 Stage78 路径意外执行了两个真实共享 builder，违反了原定“不执行真实共享 builder”的 probe 边界。
- 两个 shared CSV 的 mtime 因此从 `2026-09-02 00:54:22 +0800` 刷新为 `2026-09-02 01:22:34 +0800`；inode、size 和内容 SHA 均未变化：
  - universe：`72c5ca576bfe8aebe12da1e750d9eac980633a43ab9944479a77a7e824a71e34`；
  - post-signal eligibility：`fa5fb5c1cfe06ace44dadc92bd2cc1a77bd4ee74beeab362234952950ca5bb3b`。
- production checkout 对这两个文件的 `git status --short` 无内容差异。未尝试恢复 mtime，避免再次写入或掩盖现场；之后所有对象链 probe 均只做内存名字替换，并以前后 stat 确认无进一步写入。
- 本轮没有读取或分析任何部分 label 的收益分布，没有运行回测、训练模型、连接 CTP 或调用 order API；runner、tests、campaign artifacts 和上一份 smoke review 均未改动。

## 外部调研与判断

- Python 官方 import system 文档说明，import 会把结果绑定到导入方作用域，已加载模块通常由 `sys.modules` 返回同一模块对象；这解释了为什么沿 `import module` 访问并替换同一模块属性可以生效。
- Python execution model 文档说明，import statement 本身是名字绑定操作；因此 Stage78 与 Stage777 的两个 `from ... import builder` 是两个独立模块全局绑定，替换 Stage777 不会重绑 Stage78。
- Python 官方文档也明确 `finally` cleanup 会在正常返回和异常路径执行，与本次恢复 probe 一致。
- 参考：<https://docs.python.org/3.11/reference/import.html>；<https://docs.python.org/3.11/reference/executionmodel.html>。
- 最终判断以本地真实源码、运行时 `__globals__` 对象身份、共享文件现场和 fresh tests 为准，外部文档只用于核对语言语义。

## 过拟合与继续价值

- 运行前判断：`不构成过拟合`。本轮只审查执行隔离、名字绑定和身份合同，没有按 development label 的收益、回撤、月份、rank 或方向调整任何研究合同。
- 运行后判断：`仍不构成过拟合`。P1 来自与标签数值无关的共享副作用和 import 绑定遗漏；没有读取部分 label 收益分布，也没有触碰 sealed holdout。
- 当前修复是否值得创建新 campaign：`否`。Stage78 两处绕过仍会让 worker 写共享 CSV，且现有 receipt 会误报 guard 已启用。
- 这条研究是否仍值得继续：`是`。冻结 development 标签用于后续预注册模型仍有研究价值，但下一步只能先封住完整 worker 的 Stage78/Stage777/origin 全部共享写路径并补真实边界测试，再重新独立复审。

## 最终决定

`STOP`
