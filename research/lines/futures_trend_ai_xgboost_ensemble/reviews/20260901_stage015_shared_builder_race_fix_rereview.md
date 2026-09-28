# Stage015 shared builder 并发竞态修复第二轮独立复核

## 结论先行

- 最终决策：`STOP`
- 严重度计数：`P0=0 / P1=1 / P2=4`
- 上一轮三个 P1 的主体修复均已落地：aggregate 不再传过期参数或调用 mutable builder；产品池已按字节复制到 campaign 私有文件且不是共享 inode；receipt、runtime 原始路径和指定废弃 campaign 的拒绝门已经补齐。
- 但当前跨 job `file_identity_cache` 只按 `Path` 缓存哈希，命中时不再查看文件。独立 probe 已证明：公共输入在首个 job 后改为同长度不同内容，第二个 job 的 cached manifest 仍被接受，fresh manifest 则立即报 drift。aggregate 又在这批 cached validation 之前生成 identity-after，之后到发布标签前没有最终重验。因此“当前执行合同已重算”和“campaign 结束身份稳定”仍可被错误宣告，属于阻断新 campaign 的 P1。
- 原始 `EmptyDataError` 竞态已经切断，但身份闭环未完成；按照只有 P0/P1 均为 0 才允许启动的门槛，本轮不能创建新 campaign。

## P0

无。

## P1

### P1-1：跨 job 哈希缓存会接受后续漂移，aggregate 的 identity-after 顺序没有兜底

证据：

- `research/lines/futures_trend_ai_xgboost_ensemble/tools/stage015_development_label_batch.py:859-874` 的 cache 仅以 resolved `Path` 为键；路径一旦存在于 `by_path`，后续调用直接复用旧 `size/sha256`，没有 `stat`、inode、mtime/ctime 或重新哈希。
- 同一 cache 分别在 run-pending 已完成任务扫描 `:1623-1632`、smoke `:1740-1747`、aggregate 全量校验 `:1907-1915` 中跨 job 复用。
- 独立临时目录 probe：首个 job 缓存公共文件内容 `AAAA` 后，将文件改为同长度的 `BBBB`；第二个 job 在共享 cache 下返回 `ACCEPTED`，改用空 cache 则报 `RuntimeError: worker_execution_input_drift:contract_metadata`。这不是理论上的 hash 碰撞，而是确定性的 stale-cache 接受。
- aggregate 在 `:1904-1906` 先生成并写出 `campaign_identity_after.json`，随后才开始上述 cached receipt/output 校验；`development_labels.csv` 在 `:2120-2125` 发布，期间没有第二次完整 manifest 重验。若公共输入在早期 identity-after/hash cache 之后发生持久漂移，最终 gate 仍可能保留 `campaign_input_identity_stable=true`。
- worker 自身 before/after manifest 不使用这个跨 job cache，所以该问题不等于原产品池竞态仍在；问题在最终 validator 和发布身份可以与当前磁盘字节脱节，直接违反预注册的 campaign 始末文件合同。

影响：

- 一个已经漂移的公共执行输入可被后续 completed-job validator 当成当前字节重新验证过；最终标签可能在磁盘输入已不匹配冻结 manifest 时被发布。
- 当前共享工作区、生产代码树和 runtime database 都未受 campaign lock 排他保护，不能把“运行时不会有人改”作为身份合同。

最小修复要求：

1. cache 命中时至少重新读取并比较 `(st_dev, st_ino, st_size, st_mtime_ns, st_ctime_ns)`；任一变化必须重新计算完整身份并与 expected 比较。更简单但更慢的合格修复是 validator 禁用跨 job identity cache。
2. 在全部 receipt/output 读取、对账和 gate 计算完成后，紧邻任何 `development_labels.csv`/PASS decision 发布之前，再重建一次完整 frozen campaign manifest；不一致必须直接 fail-stop，不能只把 gate 置 false 后继续写发布产物。
3. 新增先红后绿测试：共享 cache 第一次命中后修改公共文件，同长度与不同长度两种情况都必须拒绝；在 aggregate 首次身份检查后注入漂移，必须不生成 development labels，也不得输出 PASS decision。

## P2

### P2-1：一个历史废弃 campaign 的旧式禁止字段没有被显式 gate 识别

- `_campaign_reuse_forbidden()` 在 runner `:1131-1142` 只识别 `ABANDONED.json` 的存在或 `failure_receipt.reuse_forbidden is true`。
- 实际历史 `campaign_20260901T191852+0800_76524/failure_receipt.json` 没有 `reuse_forbidden`，而是记录 `campaign_reuse_allowed=false`、`cross_campaign_job_output_reuse_allowed=false`，且目录没有 `ABANDONED.json`。独立 probe 得到 `_campaign_reuse_forbidden(...) == False`，`_assert_campaign_reusable()` 也接受。
- 该旧 campaign 当前仍会被 runtime/旧 manifest schema 间接挡住，因此本轮不把它升级为可实际恢复的 P1；但这仍不是“历史失败 campaign 显式禁止复用”的完整实现。

最小修复要求：同时识别旧 receipt 的 `campaign_reuse_allowed is false`（以及已有的 cross-campaign false 字段），并增加三个现存历史 campaign 的参数化拒绝测试。不要依赖 runner SHA 或 snapshot schema 漂移作为永久 tombstone。

### P2-2：prepare tombstone 能 fail-closed，但失败记录语义仍不完整

- runner `:1386-1396` 在准备刚开始时就写 `status=prepare_failed`；实际此时尚在 preparing。任意后续异常会留下 tombstone，这是安全的，但代码没有异常收口来补写失败阶段、异常类型/消息和失败时间。
- runner `:1452-1463` 的成功顺序正确：identity、progress、LATEST 全部写完后才删除 tombstone。独立成功 probe 也确认 prepared campaign 的 tombstone 被删除；现有失败测试确认早期异常会保留 `reuse_forbidden=true`。
- post-replace SHA 校验异常时，私有目标文件会保留而临时文件已清理；因为 tombstone 仍在，恢复是 fail-closed 的，但审计人无法从 tombstone 判断失败发生在 copy 后校验。

最小修复要求：初始状态改为 `preparing_reuse_forbidden`；用统一 `try/except BaseException` 原子更新为 `prepare_failed`，写入 `failed_stage`、异常类型/消息和时间后重新抛出。补 builder 抛错、NaN、copy/hash 失败和成功删除四类测试。

### P2-3：receipt schema 与私有 CSV 语义测试仍偏薄

- worker 在 runner `:1337-1338` 同时写顶层 `tmpdir/mplconfigdir`，validator 在 `:1527-1542` 只校验 `runtime.environment` 内的原始值；aggregate 却在 `:2053-2070` 用顶层字段判断隔离。当前测试构造的可通过 receipt 甚至没有这两个顶层字段。真实 worker 会写一致值，所以目前不是运行路径 P1，但 validator 没有约束 aggregate 实际消费的字段。
- `_snapshot_product_universe()` 在 `:1077-1081` 检查 DataFrame 非空和 symbol 表头；独立 probe 表明一行数据但 symbol 全空仍会通过。真实 builder 当前输出有效，所以降为 P2。
- 17 个 Stage015 测试没有覆盖 cache 漂移、post-identity aggregate 漂移、direct `_run_worker` builder 调用边界、private inode 或 post-replace mismatch；本轮 probe 补了证据，但测试资产尚未形成永久回归门。

最小修复要求：validator 必须要求顶层 TMP/MPL 与 `runtime.environment` 精确相等；私有 CSV 至少要求 symbol 列存在一条非空、strip 后非空的值；把本轮反例转成正式测试，并让完整 worker 边界把 mutable builder 设为调用即失败。

### P2-4：仍没有可审计的 Git parent diff

- `research/lines/futures_trend_ai_xgboost_ensemble/` 仍整体未被 Git 跟踪；`git diff -- runner tests` 为空，`git ls-files --stage` 和 `git log --all -- <runner>` 也无记录。
- 当前只能用失败 campaign 中旧 runner SHA `7c85022e...`、上一轮 replacement SHA `f3ab2aff...` 和本轮当前 SHA `2665dd7e...` 建立版本序列，不能独立证明修复 diff 只涉及声明范围。

最小修复要求：在启动长 campaign 前，把 runner、测试、预注册合同及小型身份文件纳入一个可审查提交；大 campaign 产物无需纳入 Git。

## 上一轮 P1 关闭证据

### 旧 P1-1：aggregate 过期参数

- 已关闭。`_aggregate_identity_after()` 位于 runner `:1884-1894`，只向 `_campaign_manifest()` 传 `campaign_dir/s901/frozen_runtime`。
- 新测试把 mutable official builder 设为调用即失败，并确认 aggregate identity helper 只重建 frozen manifest。Stage015 测试通过该路径。

### 旧 P1-2：产品池仍指向共享文件

- 已关闭。runner `:1052-1091` 先后校验源 before identity、原始 payload、source after identity，再把 payload 写入同目录唯一临时文件，执行 flush/fsync、CSV 校验和 `Path.replace()`；`official_overrides.json` 被改写为 campaign 私有路径。
- `_collect_campaign_files()` 的 `product_universe` 在 `:740-753` 从 frozen overrides 取值，worker exact identity 包含 `product_universe` 与 `stage015_official_overrides`；receipt 在 `:1327-1333` 记录 overrides/private product SHA，validator 在 `:1504-1517` 重算。
- 独立 inode probe：源与私有文件 `os.path.samefile=False`，inode 分别为 `527238531/527238532`；截断源文件后私有文件仍保持原 37 字节。
- 空源与错误表头两条异常 probe 均没有生成 destination，临时文件为 0；模拟 replace 后目标 SHA mismatch 时抛 `frozen_product_universe_copy_mismatch`，临时文件为 0，目标留在 tombstoned campaign 中。
- 当前 workspace 与 production 的旧共享 CSV 仍是同一 inode `422227924`，但新 worker 不再读取它。AST 对当前 Stage015 runner 的 mutable builder 调用统计只有 `:1099` 一处，即 prepare freeze。

### 旧 P1-3：receipt/campaign 绑定与废弃恢复

- 主体已关闭。receipt 在 runner `:1305-1344` 写入 campaign ID、resolved path、执行合同、private product SHA 和原始 runtime；validator 在 `:1483-1560` 校验 job/campaign、snapshot、原始 campaign/job 环境、TMP/MPL 前缀与同一 run parent，并重算 execution contract/当前 job unique count。
- 现有 cross-campaign `copytree` 测试返回 false。
- 指定废弃 race campaign `campaign_20260901T205915+0800_36804` 同时有 `ABANDONED.json` 和 `reuse_forbidden=true` failure receipt。独立 probe 对 resume、run_pending、smoke、aggregate、direct `_run_worker`、orchestrator 六条路径全部得到 `campaign_reuse_forbidden`；直接 CLI worker 也在创建 job lock 前退出。

## 失败现场与根因复核

- 指定 campaign 的 `progress.json` 仍为 `226/355`，失败 job 为 `20240430_R17`；failure receipt 和 ABANDONED 都声明整体不可复用、未发布 development labels、sealed holdout 读取数 0。
- R17 日志栈在 `main_contract_mapping.py:47` 的 `pd.read_csv(path)` 抛 `pandas.errors.EmptyDataError`。
- 当前真实上游调用链仍是 official live builder -> Stage847 -> Stage819 -> Stage813/Stage777 -> `build_static18_plus_fu_universe()`；最终源码 `/Users/bytedance/Desktop/person/vnpy_production_live/examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest.py:121-133` 仍以普通 `universe.to_csv(...)` 重写共享 CSV。
- 根因主张保持成立；本轮 private snapshot 的确切断了 Stage015 worker 对该共享 inode 的读取依赖。

## 冻结合同与 sealed holdout

- 当前内存生成 jobs 为 `355`，全部 `development`，rank `10..18`；序列化 SHA `aa0a14ae17aa5089faf4be6767e97a5838e8a1c7b0f88cd4139ea2a2f2925555`，与失败 campaign 完全一致。
- Stage010 label helper、Stage013 runner/plan、Stage014 runner/feature panel/month split/feature contract 的当前 SHA 全部与失败 campaign identity 一致；Stage015 预注册文件 SHA 也仍为 `0e3c406f...`。
- Stage014 仍冻结 9 个特征、双 `XGBRegressor` 固定参数、禁止参数扫描与标签特征选择。runner 仍为 `MAX_WORKERS=2`、`MAX_JOB_SECONDS=600`、`MONEY_QUANTUM=0.000001` 元、对账阈值 `1e-9`。
- 未发现 sealed holdout label 读取路径；jobs 构造在 runner `:402-466` 只保留 development 且显式拒绝 holdout job。本轮没有打开任何历史 job 的 `label.json`。

## 验证记录

执行：

```bash
env PYTHONDONTWRITEBYTECODE=1 .py311/bin/python -B -m pytest -p no:cacheprovider \
  research/lines/futures_trend_ai_xgboost_ensemble/tests/test_stage015_development_label_batch.py -q
```

结果：`17 passed in 0.54s`。

执行：

```bash
env PYTHONDONTWRITEBYTECODE=1 .py311/bin/python -B -m pytest -p no:cacheprovider \
  research/lines/futures_trend_ai_xgboost_ensemble/tests -q
```

结果：`85 passed in 6.58s`。

附加 probe：

- private snapshot 与源文件 inode 分离，源被截断后私有字节不变。
- 空源、错误表头均 fail-closed 且无临时残留；post-replace target SHA mismatch 也 fail-closed。
- 普通标量通过；NaN/Inf 因 `allow_nan=False` 被拒绝，list/null 被 non-scalar gate 拒绝。
- mutable official builder 的 Stage015 AST 调用点只有 prepare freeze 一处。
- 指定 race campaign 的六个恢复/执行入口全部拒绝。
- cache drift 反例稳定复现：cached 接受，fresh hash 拒绝。
- prepare 成功时 tombstone 在 identity/progress/LATEST 完成后删除。

未运行真实 mutable builder，因为它会写共享产品池，违反本次只写 review 的边界；未创建新 campaign、未重跑 355-job 批次，也未修改 runner、tests 或 artifacts。

外部调研结论：pandas 官方文档确认 `EmptyDataError` 对应空文件/无表头读取；pandas 源码中 `to_csv` 默认 `mode="w"`；Python 官方文档确认 buffered file 需 flush 后 fsync，POSIX 上成功的 replace 为原子操作。当前 private copy 的核心顺序符合这些语义，但这些原子语义不能修复 path-only identity cache 的 stale read。

- [pandas `EmptyDataError` 官方文档](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.errors.EmptyDataError.html)
- [pandas `to_csv` 官方源码](https://github.com/pandas-dev/pandas/blob/main/pandas/io/formats/format.py)
- [Python `os.fsync` / `os.replace` 官方文档](https://docs.python.org/3.11/library/os.html)

## 过拟合与继续价值

- 本修复是否构成看标签调参/过拟合：`否`。改动是输入快照、并发副作用隔离和身份/receipt 验证；jobs、9 特征、标签 helper、模型参数、并发数、超时、货币量化和对账阈值均未改变，sealed holdout 标签仍未读取。失败后的部分 development labels 也没有进入本轮代码决策或审计读取。
- 从零跑完整 development 标签是否有价值：`有`。冻结的 39 月 x 9 rank 账户边际标签仍是检验双模型结构假设的必要数据，旧 campaign 不能拼接复用。但当前不得开始；先修复本轮 P1 并新增反例测试，再独立复核后从 0 创建 campaign。

## 最终决策

`STOP`
