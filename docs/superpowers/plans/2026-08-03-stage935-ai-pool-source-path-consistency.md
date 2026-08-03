# Stage935 AI Pool Source Path Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Stage935 始终把本次 Stage183 生成的隔离源交给 Stage182，候选通过验证后才以 combined eligibility 为激活点发布 `eval_date=2026-07-31` 的新 AI 池。

**Architecture:** Stage183 报告实际回测 artifact root，Stage182 通过显式 `source_dir`/`output_dir` 读写候选，Stage935 验证源路径与日期后运行 Stage182，再将候选 bundle 以 combined eligibility 最后替换的顺序原子发布；发布后失败则恢复旧 combined 文件。正式交易读取路径保持不变。

**Tech Stack:** Python 3.11、pandas、unittest、`pathlib.Path`、SHA-256、POSIX `fsync`/`os.replace`。

## Global Constraints

- 使用 `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python`，但所有命令的工作目录保持为隔离 worktree `/Users/bytedance/Desktop/person/vnpy_stage174_postclose_orchestration`。
- 所有 Python 命令均设置 `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy_stage174_postclose_orchestration`，以加载 worktree 的 `sitecustomize.py` 和隔离 `.vntrader`；不得使用 `QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR` 绕过 runtime guard。
- 不连接 CTP，不导入交易网关，不调用报单、撤单或成交 API。
- 不修改 AI 模型、训练窗口、特征、Top8 加固定 `fu.SHFE` 的 Top9 规则。
- 不修改 Stage847-C9-15w 的入场、止损、一次重试、止盈或仓位逻辑。
- 不强制 `--eval-date`，不伪造稀疏候选事件日期。
- 任一路径、日期、校验、发布或回滚异常均 fail-closed。
- 不停止、杀死、bootout 或 kickstart 任何 production launchd job；安装继续等待 PID 自然归零和 Stage174/Stage948 门禁。

---

### Task 1: 用回归测试固定路径分叉故障

**Files:**
- Create: `tests/test_stage935_ai_pool_path_consistency.py`
- Read: `examples/portfolio_backtesting/build_qmt_roll_stage182_ai_product_pool_live_inference_runner.py`
- Read: `examples/portfolio_backtesting/build_qmt_roll_stage183_ai_product_pool_source_refresh.py`

**Interfaces:**
- Consumes: 当前 Stage183 静态 `OUTPUT_DIR` 与 `run_qmt_alignment_backtest.OUTPUT_DIR` 的分叉行为。
- Produces: 可证明旧实现读取 stale source 的失败测试，以及后续任务共用的临时 CSV fixture。

- [ ] **Step 1: 写 Stage183 真实 artifact root 失败测试**

在新测试文件中导入 Stage183，创建 `data_root` 与 `control_root`，只在 `control_root` 写覆盖到 `2026-08-03` 的 daily、position changes 和 entry snapshots。调用计划新增的：

```python
paths = stage183._build_artifact_paths(
    source_prefix="qmt_roll_stage183_ai_source_floor35",
    artifact_root=control_root,
)
assert paths["position_changes"].parent == control_root
assert stage183._max_csv_date(paths["position_changes"], ("date",)) == "2026-08-03"
```

- [ ] **Step 2: 运行测试并确认 RED**

Run:

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage935_ai_pool_path_consistency.Stage935AiPoolPathConsistencyTest.test_stage183_artifact_paths_use_real_runtime_root -v
```

Expected: FAIL，原因是 `_build_artifact_paths` 尚不存在。

- [ ] **Step 3: 写 Stage182 显式 source-dir 失败测试**

在 `data_root` 写最大日期 `2026-07-21` 的旧 position changes，在 `control_root` 写最大日期 `2026-08-03` 的新文件。断言计划新增接口只绑定 `control_root`：

```python
source_paths = stage182._configure_source_paths(
    "qmt_roll_stage183_ai_source_floor35",
    source_dir=control_root,
)
assert Path(source_paths["position_changes"]).resolve().parent == control_root.resolve()
assert stage182.suitability.POSITION_CHANGES_PATH.resolve().parent == control_root.resolve()
```

- [ ] **Step 4: 运行测试并确认 RED**

Run:

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage935_ai_pool_path_consistency.Stage935AiPoolPathConsistencyTest.test_stage182_source_dir_does_not_fall_back_to_stale_data_root -v
```

Expected: FAIL，原因是 `_configure_source_paths` 不接受 `source_dir`。

- [ ] **Step 5: 提交 RED 测试**

```bash
git add tests/test_stage935_ai_pool_path_consistency.py
git commit -m "test: reproduce Stage935 AI pool source path split"
```

---

### Task 2: 让 Stage183 摘要绑定真实 artifact root

**Files:**
- Modify: `examples/portfolio_backtesting/build_qmt_roll_stage183_ai_product_pool_source_refresh.py`
- Modify: `tests/test_stage935_ai_pool_path_consistency.py`

**Interfaces:**
- Consumes: `run_qmt_alignment_backtest.OUTPUT_DIR`，它在生产中由 `OFFICIAL_LIVE_OUTPUT_DIR` 解析。
- Produces: `_build_artifact_paths(source_prefix: str, artifact_root: Path) -> dict[str, Path]`；Stage183 summary 新增 `artifact_root`、`daily_max_date` 和真实绝对输出路径。

- [ ] **Step 1: 实现最小路径构造函数**

导入实际 runtime root：

```python
from run_qmt_alignment_backtest import OUTPUT_DIR as BACKTEST_ARTIFACT_ROOT


def _build_artifact_paths(source_prefix: str, artifact_root: Path) -> dict[str, Path]:
    root = artifact_root.expanduser().resolve(strict=False)
    return {
        "daily": root / f"{source_prefix}_daily.csv",
        "trades": root / f"{source_prefix}_trades_2020_2026_04.csv",
        "position_changes": root / f"{source_prefix}_position_changes_2020_2026_04.csv",
        "entry_candidate_snapshots": root / f"{source_prefix}_entry_candidate_snapshots_2020_2026_04.csv",
        "statistics": root / f"{source_prefix}_statistics.json",
    }
```

`main()` 用该映射构建源输出和日期审计；summary/report 仍写现有 `SUMMARY_PATH`/`REPORT_PATH`。`artifact_dates` 增加 `daily_max_date`，entry snapshot 日期继续只作为稀疏事件证据。

- [ ] **Step 2: 运行 Task 1 的 Stage183 测试并确认 GREEN**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage935_ai_pool_path_consistency.Stage935AiPoolPathConsistencyTest.test_stage183_artifact_paths_use_real_runtime_root -v
```

Expected: PASS。

- [ ] **Step 3: 增加稀疏事件日期语义测试**

构造 daily/position changes 最大日期为 `2026-08-03`、entry snapshots 最大日期为 `2026-07-31`，断言摘要日期提取保留两个不同日期，不把 sparse event max 当成 source calendar max。

- [ ] **Step 4: 运行 Stage183 聚焦测试**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage935_ai_pool_path_consistency.Stage935AiPoolPathConsistencyTest.test_stage183_sparse_candidate_date_is_not_daily_cutoff -v
```

Expected: PASS。

- [ ] **Step 5: 提交 Stage183 修复**

```bash
git add examples/portfolio_backtesting/build_qmt_roll_stage183_ai_product_pool_source_refresh.py tests/test_stage935_ai_pool_path_consistency.py
git commit -m "fix: report Stage183 runtime artifact paths"
```

---

### Task 3: 让 Stage182 显式读源并只写候选

**Files:**
- Modify: `examples/portfolio_backtesting/build_qmt_roll_stage182_ai_product_pool_live_inference_runner.py`
- Modify: `tests/test_stage935_ai_pool_path_consistency.py`

**Interfaces:**
- Consumes: `--source-dir PATH`、`--output-dir PATH`；默认值均为现有 `OUTPUT_DIR`。
- Produces: `_configure_source_paths(source_prefix: str, source_dir: Path = OUTPUT_DIR) -> dict[str, str]`；`_build_output_paths(output_dir: Path) -> dict[str, Path]`。

- [ ] **Step 1: 让 source-dir 回归测试 GREEN**

把 `_configure_source_paths` 改为以显式 `source_dir` 构造并验证两个源文件；返回值增加解析后的 `source_dir`。不得在显式目录缺文件时回退到全局 `OUTPUT_DIR`。

- [ ] **Step 2: 运行 source-dir 测试**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage935_ai_pool_path_consistency.Stage935AiPoolPathConsistencyTest.test_stage182_source_dir_does_not_fall_back_to_stale_data_root -v
```

Expected: PASS。

- [ ] **Step 3: 写 output-dir RED 测试**

断言 `_build_output_paths(candidate_root)` 返回五个 Stage182 候选路径且全部位于 `candidate_root`；同时断言正式 `COMBINED_ELIGIBILITY_PATH` 不在该目录。

- [ ] **Step 4: 运行 output-dir 测试并确认 RED**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage935_ai_pool_path_consistency.Stage935AiPoolPathConsistencyTest.test_stage182_output_dir_is_candidate_only -v
```

Expected: FAIL，原因是 `_build_output_paths` 尚不存在。

- [ ] **Step 5: 实现候选输出路径**

新增：

```python
def _build_output_paths(output_dir: Path) -> dict[str, Path]:
    root = output_dir.expanduser().resolve(strict=False)
    return {
        "live_pool": root / LIVE_POOL_PATH.name,
        "live_eligibility": root / LIVE_ELIGIBILITY_PATH.name,
        "combined_eligibility": root / COMBINED_ELIGIBILITY_PATH.name,
        "summary": root / SUMMARY_PATH.name,
        "report": root / REPORT_PATH.name,
    }
```

`main()` 新增两个参数并只向返回的候选路径写文件。`_build_combined_eligibility` 仍读取正式 Stage78 eligibility 与已有 combined 历史快照，但不直接写正式 combined 文件。

- [ ] **Step 6: 运行 Stage182 聚焦测试**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage935_ai_pool_path_consistency -k stage182 -v
```

Expected: 全部 PASS。

- [ ] **Step 7: 提交 Stage182 修复**

```bash
git add examples/portfolio_backtesting/build_qmt_roll_stage182_ai_product_pool_live_inference_runner.py tests/test_stage935_ai_pool_path_consistency.py
git commit -m "fix: isolate Stage182 source and candidate outputs"
```

---

### Task 4: Stage935 校验同源候选并原子激活

**Files:**
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py`
- Modify: `tests/test_stage935_ai_pool_path_consistency.py`
- Modify: `tests/test_stage947_production_support_launcher.py`

**Interfaces:**
- Consumes: Stage183 summary、`CONTROL_OUTPUT_DIR`、Stage182 candidate paths、正式 data asset paths。
- Produces: `_validate_stage183_source(...) -> dict[str, Any]`、`_stage182_paths(root: Path) -> dict[str, Path]`、`_publish_stage182_candidate(...) -> dict[str, Any]`，以及 publication receipt 证据。

- [ ] **Step 1: 写 Stage183 源门禁 RED 测试**

覆盖四种输入：真实路径位于 control root 且逐日日期到 target；路径指向 stale data root；路径越界；daily/position changes 日期不足。合法 sparse candidate max 早于 target 的 case 必须 valid。

- [ ] **Step 2: 运行源门禁测试并确认 RED**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage935_ai_pool_path_consistency.Stage935AiPoolPathConsistencyTest.test_stage935_rejects_cross_root_stage183_sources tests.test_stage935_ai_pool_path_consistency.Stage935AiPoolPathConsistencyTest.test_stage935_accepts_sparse_candidate_with_complete_daily_sources -v
```

Expected: FAIL，原因是 `_validate_stage183_source` 尚不存在。

- [ ] **Step 3: 实现 Stage183 源门禁和 Stage182 命令参数**

Stage935 在 Stage183 成功后、Stage182 启动前读取摘要并验证：source prefix、artifact root、路径 containment、文件非空、daily/position max 等于 `resolved_target_date`、candidate max 不晚于 target。Stage182 命令必须包含：

```python
"--source-dir", str(CONTROL_OUTPUT_DIR),
"--output-dir", str(CONTROL_OUTPUT_DIR),
```

- [ ] **Step 4: 运行源门禁测试并确认 GREEN**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage935_ai_pool_path_consistency -k stage935_rejects_cross_root -v
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage935_ai_pool_path_consistency -k stage935_accepts_sparse -v
```

Expected: 全部 PASS。

- [ ] **Step 5: 写候选不发布 RED 测试**

构造 candidate eval date 错误或缺 9 行的情形，调用 Stage935 更新流程后断言正式 combined eligibility 的字节和 SHA-256 完全不变，状态为 `monthly_ai_pool_update_blocked`。

- [ ] **Step 6: 写成功发布与回滚 RED 测试**

成功 case 断言非激活文件先发布、combined 最后替换、正式与候选 SHA-256 一致。失败 case 在 combined 替换后的 post-validation 注入 invalid 结果，断言旧 combined 被恢复且 SHA-256 等于发布前值。

- [ ] **Step 7: 实现 durable copy、发布顺序和回滚**

实现 `_sha256_file(path)`；实现同目录临时文件写入、file fsync、`os.replace`、parent directory fsync 的 `_atomic_copy_file(source, target)`。`_publish_stage182_candidate` 按 summary/report/live pool/live eligibility 的证据文件顺序发布，备份正式 combined，最后替换 combined，调用正式路径验证；失败时用备份恢复。返回 receipt 至少包含候选/正式 hash、激活文件、恢复状态和已发布清单。

- [ ] **Step 8: 运行候选发布测试并确认 GREEN**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage935_ai_pool_path_consistency -k publish -v
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage935_ai_pool_path_consistency -k rollback -v
```

Expected: 全部 PASS。

- [ ] **Step 9: 更新既有 Stage947 fixture**

把 `test_stage935_reads_successful_stage173_from_data_root_when_control_is_empty` 重命名为 `test_stage935_reads_stage173_from_data_and_ai_candidates_from_control`，在 control root 构造 Stage183 真源和 Stage182 候选，并断言命令包含显式目录参数；保留 control/data root 分离契约。

- [ ] **Step 10: 提交 Stage935 修复**

```bash
git add examples/portfolio_backtesting/run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py tests/test_stage935_ai_pool_path_consistency.py tests/test_stage947_production_support_launcher.py
git commit -m "fix: validate and publish Stage935 AI pool candidates"
```

---

### Task 5: 集成验证、研究记录与审查

**Files:**
- Create: `research/lines/futures_trend_stage819_intraday_rules/stages/20260803_2121_stage212_stage935_ai_pool_path_fix.md`
- Modify only if review finds a material defect: files from Tasks 2-4.

**Interfaces:**
- Consumes: 完整候选实现和所有测试。
- Produces: fresh verification evidence、零 API 审计、中文 Stage212 记录和独立审查结论。

- [ ] **Step 1: 运行聚焦测试**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage935_ai_pool_path_consistency -v
```

Expected: 0 failures，0 errors。

- [ ] **Step 2: 运行 Stage947 与 post-close 回归**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage947_production_support_launcher tests.test_official_live_postclose_pipeline -v
```

Expected: 0 failures，0 errors。

- [ ] **Step 3: 运行静态零 API 审计**

```bash
rg -n "send_order|cancel_order|req_order_insert|req_order_action|CtpGateway|vnpy_ctp" \
  examples/portfolio_backtesting/build_qmt_roll_stage182_ai_product_pool_live_inference_runner.py \
  examples/portfolio_backtesting/build_qmt_roll_stage183_ai_product_pool_source_refresh.py \
  examples/portfolio_backtesting/run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py
```

Expected: 无新增交易 API 调用；若已有计数字段，仅作为安全证据，不执行 API。

- [ ] **Step 4: 运行隔离 fixture qualification**

使用临时目录和 2026-08-03 fixture 执行 Stage935 内部流程，断言候选/正式 `eval_date=2026-07-31`、Top9 含 `fu.SHFE`、最近四个月快照完整、正式与候选 SHA-256 一致。不得运行正式 Stage183 全量回测或 CTP capture。

- [ ] **Step 5: 写 Stage212 中文记录**

记录分钟级时间、根因、文件改动、测试结果、candidate eval date、Top9、hash、零 API 证据、是否过拟合和继续价值。由于本任务不运行策略回测，明确写明期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数和胜率均未新增、修改或删除。

- [ ] **Step 6: 请求独立代码审查**

使用 `superpowers:requesting-code-review`，要求审查路径 containment、candidate/canonical 分离、combined-last 激活、回滚、partial publish、日期语义、测试真实性和零 API 边界。P0/P1 必须为 0；影响正确性的 P2 必须修复并重跑验证。

- [ ] **Step 7: fresh 全量验证后提交记录**

```bash
git add research/lines/futures_trend_stage819_intraday_rules/stages/20260803_*_stage212_stage935_ai_pool_path_fix.md
git commit -m "docs: record Stage935 AI pool path fix evidence"
git status --short
```

Expected: worktree clean。

- [ ] **Step 8: 保持部署门禁**

只读检查七个 production launchd job 和 warm executor PID。任何 PID 非零时只记录等待，不 stop/kill/bootout/kickstart。全部自然归零后仍须完成 Stage174 两次正式只读 qualification、审查和 Stage948 prepare/activate；任一 SIGSEGV、handshake、source mismatch、证据不完整、P0/P1 或 API counter 非零均 fail-closed。
