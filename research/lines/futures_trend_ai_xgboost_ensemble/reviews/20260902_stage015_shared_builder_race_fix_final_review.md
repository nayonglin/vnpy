# Stage015 shared builder race fix 第三轮最终独立复核

- 评审时间：`2026-09-02 00:37 +0800`
- 评审范围：仅 `futures_trend_ai_xgboost_ensemble` 的 Stage015 并发故障与当前修复。
- 当前 runner SHA256：`29797754f5a22597f28a29de78ac0d972f46b02b8718116f236b29bcf8662503`
- 当前 test SHA256：`ad064140b3dc8944829a873501b6e6fec95b2e16cb543eea172f6f101705fcd5`

## 结论先行

- 严重度计数：`P0=0 / P1=0 / P2=3`。
- 第二轮唯一 P1 已关闭：跨 job / 跨 validator 调用的 file-identity cache 已删除；completed-job 每次校验均 fresh 读取并哈希当前 job 的输入；aggregate 在所有 receipt/output 读取和全部 gate 计算之后、任何 development labels 或 decision 写入之前，再 fresh 重建完整 campaign manifest。
- 独立行为 probe 证明，同长度 `AAAA -> BBBB` 和异长度 `AAAA -> LONGER` 的持久公共输入漂移均在下一个 completed-job validator 中 fail-stop；发布前持久漂移抛 `campaign_input_identity_drift_before_publish`，`development_labels.csv`、`reconciliation.csv`、`decision.json` 均不存在。
- 第一、二轮涉及 mutable builder、私有产品池、receipt/campaign 绑定、旧 campaign 复用和 TMP/MPL 的旧 P1 均已关闭。三个现存失败 campaign 均被显式拒绝。
- 最终决策：`ALLOW_NEW_CAMPAIGN`。该许可仅适用于从 prepare 开始创建全新 campaign；不得恢复、复制或拼接任何旧 campaign 的 job output。

## P0

无。

## P1

无。

### 第二轮 P1：已关闭

1. **跨 job stale identity cache 已消失。**
   - runner `:837-878` 的 `_worker_execution_manifest(campaign_dir, job, campaign_identity)` 和 `:1480-1585` 的 `_validate_completed_job(campaign_dir, job, campaign_contract)` 均无 cache 参数；AST 与全文检索也没有任何 `*cache*` 标识符。
   - runner `:1561-1568` 每次 validator 都重新读取 `campaign_identity.json` 并重新调用 `_worker_execution_manifest`。run-pending 初扫、单 job 完成后校验、smoke、aggregate 的调用点 `:1641-1645`、`:1695-1697`、`:1753-1758`、`:1954-1960` 均未传递可跨 job 存活的身份对象。
   - runner `:857-872` 仍有函数内 `by_path` 去重：它只让同一次 manifest 重建对同一物理路径哈希一次，每次函数调用都会新建，不能跨 job 或跨 validator 复用。`unique_physical_file_count` 仍按当前 job 的 selected paths 计算。
   - 独立 validator probe：job A 首次校验为 `True`；随后把公共输入改成 `BBBB` 或 `LONGER`，job B 都抛 `worker_execution_input_drift`。公共路径在两次调用中实际被读取两次。

2. **最终身份门严格位于 gate 之后、发布之前。**
   - runner `:1944-2159` 依次完成全体 completed-job fresh 校验、label/receipt/curve/combined/trades 读取、三源金额对账、predecision、A2、runtime/isolation、日期合同与 sealed-holdout absence gate，最后才计算 `passed`。
   - runner `:2160-2166` 随后调用 `_publish_development_label_outputs`；该 helper 在 `:1929` 的第一条有效语句调用 `_assert_final_campaign_identity_before_publish`，而 labels/reconciliation 直到 `:1932-1940` 才写。
   - runner `:1908-1918` fresh 调用 `_aggregate_identity_after`；不等于初始 identity 时立即抛 `campaign_input_identity_drift_before_publish`。`decision.json` 在 runner `:2202` 才写，异常未被吞掉，因此不可能先产生 PASS decision。
   - 独立持久漂移 probe 使用实际临时文件身份：初始 `AAAA`，发布前保持为 `BBBB`，结果为上述异常，labels、reconciliation、decision 三个文件均不存在。

3. **旧 P1 的其余路径保持关闭。**
   - mutable official builder 的 Stage015 AST 真正调用点只有 prepare freeze 的 runner `:1108`。worker 在 `:1209-1219` 安装只读 campaign snapshot builder，`_run_live_c9` 调用的是这个进程内替代函数；aggregate identity 在 `:1895-1905` 只重建冻结 manifest，不调用 mutable builder。
   - 私有产品池在 runner `:1050-1100` 做源 before/read/after identity、非空字节、CSV 可解析、symbol 表头及至少一个 strip 后非空 symbol 校验；临时文件 flush+fsync 后同目录 replace，并校验目标 size/SHA。独立 probe 确认源/目标 SHA 相同但 inode 不同，源后续改写不影响目标；注入 replace 异常时无目标文件、无临时残留。
   - runner `:1140-1155` 同时识别 `ABANDONED.json`、`reuse_forbidden=true`、legacy `campaign_reuse_allowed=false`、`cross_campaign_job_output_reuse_allowed=false`。对现存 `185107`、`191852`、`205915` 三个失败 campaign 的独立 probe 全部得到 `campaign_reuse_forbidden`。
   - direct `_run_worker`、CLI worker、orchestrator、resume、run-pending、smoke、aggregate 均在业务读写前执行 reuse gate，见 runner `:1167-1175`、`:1625-1633`、`:1741-1750`、`:1944-1949`、`:2230-2247`、`:2250-2271`、`:2299-2314`。
   - receipt 顶层 TMP/MPL 与 `runtime.environment` 的精确相等校验位于 runner `:1537-1547`，目录前缀、同 run parent 与固定末级目录校验位于 `:1548-1557`。

## P2

### P2-1：关键门禁的集成回归测试仍偏窄

- test `:312-336` 直接调用 `_publish_development_label_outputs`，没有进入 `_aggregate`；其中 `decision.json` 不存在的断言对该 helper 本身是天然成立的。因此当前“所有 gate 后才 final check、final check 后才 decision”的集成顺序仍主要由本轮静态审计确认，测试不能阻止未来把 `_aggregate` 调用顺序改坏。
- test `:85-135` 验证 freeze 后 candidate helper 不再调用 mutable builder，`:138-182` 验证 aggregate identity 不调用 builder，但没有执行 mocked 完整 `_run_worker` 边界。当前真实 worker 源码路径正确，所以不是运行时 P1。
- test `:544-560` 覆盖两类 legacy 字段，但没有把三个现存失败 campaign/receipt shape 固化为参数化回归；本轮独立 probe 已确认当前均拒绝。

最小修复要求：增加一个调用 `_aggregate` 的小型集成测试，注入 gate 后持久输入漂移并断言 labels/reconciliation/decision 全部缺失；增加一个 mocked 完整 `_run_worker` 测试，把原 mutable builder 设为调用即失败；把三个历史失败 schema 固化为参数化 fixture。

### P2-2：prepare tombstone fail-closed，但失败诊断仍不完整

- runner `:1397-1409` 在目录创建后立即写 tombstone，安全语义正确；但尚未发生异常时已写 `status=prepare_failed`，后续异常也没有统一收口写入失败阶段、异常类型/消息和失败时间。
- runner `:1461-1476` 的成功顺序正确：manifest、campaign identity、progress、LATEST 完成后才删除 tombstone。copy/replace 后校验失败也会保留 tombstone，因此不构成可恢复 P1。

最小修复要求：用 prepare 阶段的异常收口原子更新 tombstone，至少记录 `failed_at`、`failed_stage`、异常类型/摘要，同时始终保留 `reuse_forbidden=true`；成功路径继续最后删除。

### P2-3：仍无可审计 Git parent diff

- `research/lines/futures_trend_ai_xgboost_ensemble/` 当前仍整体为 untracked；`git diff -- <runner> <test>` 为空，`git ls-files --stage` 与 `git log --all -- <runner>` 均无记录。
- 因而本轮能确认当前磁盘字节、前两轮 review 哈希未变和冻结合同哈希一致，但不能由 Git 独立证明“第二轮 SHA -> 当前 SHA”的最小变更集合。

最小修复要求：在启动长 campaign 前，将 runner、tests、预注册合同及小型身份文件纳入一个可审计提交；大 campaign 产物不需要进入 Git。

## 失败现场与根因复核

- 指定失败 campaign `campaign_20260901T205915+0800_36804` 的 `progress.json` 仍为 `226/355`，failure receipt 指向 `20240430_R17`，异常为 `pandas.errors.EmptyDataError: No columns to parse from file`。
- R17 日志 `:3-49` 显示调用栈最终在 production `main_contract_mapping.py:47` 的 `pd.read_csv(path)` 失败。
- 当前真实上游链仍为 official live builder -> Stage847 -> Stage819 -> Stage813 -> Stage777；production `run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest.py:121-133` 仍以普通 `universe.to_csv(...)` 重写共享产品池。
- 当前 Stage015 worker 不再调用该 mutable builder，且读取的是不同 inode 的 campaign 私有副本，因此原始截断写/并发读竞态已从 worker 路径切断。

## 冻结合同与 holdout

- 当前内存重建 jobs 为 `355`，全部 `development`，rank 为 `10..18`；序列化 SHA256 为 `aa0a14ae17aa5089faf4be6767e97a5838e8a1c7b0f88cd4139ea2a2f2925555`，与失败 campaign identity 一致。
- Stage009 full ranking、Stage010 label helper、Stage013 runner/plan/summary、Stage014 runner/feature panel/month split/feature contract、Stage015 preregistration 的当前 size/SHA 均与失败 campaign identity 一致；预注册 SHA 仍为 `0e3c406f560aad95ebdff9d35f28bfa9e3ffa914ed38f2a7c4e2006cfd3063f7`。
- Stage014 合同仍为 9 个冻结特征、两个固定参数 `XGBRegressor`、`parameter_scan_allowed=false`、`label_based_feature_selection_allowed=false`。
- runner 仍为 `MAX_WORKERS=2`、`MAX_JOB_SECONDS=600.0`、`MONEY_QUANTUM=0.000001`，所有金额/收益/滑点/交易数 gate 阈值仍为 `1e-9`。
- jobs 构造明确拒绝 `sealed_holdout`，当前 355 个 job 均为 development；本轮未读取任何 sealed holdout label，也未运行训练。
- JSON 独立 probe：普通 bool/int/float/string scalar 通过；NaN/Inf 因 `allow_nan=False` 被拒绝，list/null 被 non-scalar gate 拒绝。

## 验证记录

执行：

```bash
env PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/private/tmp/stage015-final-review-mpl \
  .py311/bin/python -B -m pytest -p no:cacheprovider \
  research/lines/futures_trend_ai_xgboost_ensemble/tests/test_stage015_development_label_batch.py -q
```

结果：`23 passed in 0.59s`。

执行：

```bash
env PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/private/tmp/stage015-final-review-mpl \
  .py311/bin/python -B -m pytest -p no:cacheprovider \
  research/lines/futures_trend_ai_xgboost_ensemble/tests -q
```

结果：`91 passed in 3.52s`。

未运行真实 mutable builder，因为它会写共享产品池，违反本次只写 review 的边界；未创建新 campaign、未运行 355-job 完整批次，也未修改 runner、tests 或 artifacts。

外部语义复核：pandas 官方文档确认 `EmptyDataError` 表示读取空数据/无可解析列；Python 官方文档确认文件 flush 后可用 `fsync` 强制写入，且同文件系统成功的 replace 提供原子替换语义。当前私有 snapshot 的正常与异常路径符合本次所需语义。

- [pandas `EmptyDataError` 官方文档](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.errors.EmptyDataError.html)
- [Python `os.fsync` / `os.replace` 官方文档](https://docs.python.org/3.11/library/os.html)

## 过拟合与继续价值

- 本修复是否构成看标签调参/过拟合：`否`。变化只涉及并发副作用隔离、不可变输入快照、身份重验和 receipt/reuse gate；jobs、预注册特征、标签定义、模型参数、并发数、超时和对账阈值均未改变，也没有读取 sealed holdout 标签。失败 campaign 的部分 development labels 未参与本轮代码决策。
- 从零跑完整 development 标签是否有价值：`有`。冻结的 39 月 x 9 rank 账户边际标签仍是检验预注册双模型假设的必要数据；旧 campaign 已被明确污染/废弃，继续拼接没有审计价值。应创建全新 campaign，按 prepare -> smoke -> 355 cold jobs -> aggregate 顺序运行，并以新 identity/receipts 为唯一证据。

## 最终决策

`ALLOW_NEW_CAMPAIGN`

适用条件：只允许从零创建新 campaign；三个历史失败 campaign 及其 job outputs 均不得恢复或复用。
