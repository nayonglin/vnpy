# Stage015 shared builder 并发竞态修复独立评审

## 结论先行

- 最终决策：`STOP`
- 严重度计数：`P0=0 / P1=3 / P2=3`
- 根因主张成立：失败 campaign 的 worker 并发调用带写副作用的正式 builder；builder 以普通 `DataFrame.to_csv()` 重写同一个产品池 CSV，另一个 worker 在文件被截断后的窗口内执行 `pd.read_csv()`，触发 `pandas.errors.EmptyDataError`。
- 当前修复方向正确但没有闭环。worker 主路径已改成读取 campaign 快照，不再直接调用正式 builder；然而完整聚合存在必现 `TypeError`，快照仍引用全局可写产品池，receipt 也没有绑定 campaign/ABANDONED 状态。按照“只有 P0=0 且 P1=0 才能 ALLOW”的门槛，本次不得启动新 campaign。

## P0

无。

## P1

### P1-1：355 个任务完成后，完整聚合必然因错误关键字参数失败

证据：

- `research/lines/futures_trend_ai_xgboost_ensemble/tools/stage015_development_label_batch.py:813-818` 中 `_campaign_manifest()` 的签名只有 `campaign_dir`、`s901`、`frozen_runtime`。
- 同文件 `:1729-1734` 的 `_aggregate()` 却额外传入 `live_cfg=live_cfg`。
- 独立执行 `inspect.signature(_campaign_manifest).bind(...)` 已复现：`TypeError: got an unexpected keyword argument 'live_cfg'`。
- 当前 13 个 Stage015 测试没有进入 `_aggregate()` 的 identity-after 路径，因此全部通过也无法发现该错误。

影响：新 campaign 即使耗时完成全部 355 个冷进程，也不能生成最终 identity-after、decision 或 development labels；这不是降级行为，而是完整批次的确定性失败。

最小修复要求：删除过期的 `live_cfg` 实参，或恢复一个明确不调用正式 builder 的同名参数；新增最小聚合回归测试，必须真实走到 identity-after 重建，并断言聚合期间正式 builder 调用次数为 0。

### P1-2：`official_overrides.json` 冻结了路径字符串，但没有冻结其指向的共享产品池文件

证据：

- runner `:1002-1044` 只校验 `product_universe_csv_path` 存在后把 overrides 写入 JSON；没有把产品池复制到 campaign 私有路径。
- runner `:1056-1062` 的 worker override 继续返回快照中的原始 `product_universe_csv_path`。
- 测试 `research/lines/futures_trend_ai_xgboost_ensemble/tests/test_stage015_development_label_batch.py:121-124` 也只证明两个 worker override 指向同一个原始 universe 路径。
- 真实 builder 链为：
  - `/Users/bytedance/Desktop/person/vnpy_production_live/examples/portfolio_backtesting/qmt_roll_official_live_config.py:242-251`
  - `/Users/bytedance/Desktop/person/vnpy_production_live/examples/portfolio_backtesting/qmt_roll_official_candidate_stage847_c9_config.py:134-160`
  - `/Users/bytedance/Desktop/person/vnpy_production_live/examples/portfolio_backtesting/qmt_roll_official_candidate_stage777_config.py:173-207`
  - `/Users/bytedance/Desktop/person/vnpy_production_live/examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest.py:121-133`
- 最后一层仍以普通 `universe.to_csv(UNIVERSE_PATH, ...)` 改写共享文件。当前 workspace 与 production 路径还是同一 inode `422227924`。
- runner `:2041-2046` 的 `.create_campaign.lock` 只覆盖单次 prepare；运行中的 campaign 不持有该全局锁。第二个 Stage015 campaign 的 prepare，或任何其他正式 builder 调用，仍可在 worker 读取时截断该共享文件。
- worker 的 before/after SHA 只能发现最终内容漂移，不能阻止“读取时短暂为 0 字节、随后恢复为原 SHA”的同类故障。

影响：本次根因在“同一 campaign 的两个 worker”之间被消除，但在“运行中 campaign worker vs 另一个 prepare/外部 builder”之间仍可原样复发，所以不能称为 campaign-frozen 输入。

最小修复要求：prepare 单次调用正式 builder 后，把生成的产品池按原字节复制到 campaign 私有文件，校验非空、表头、SHA，再以临时文件加原子 replace 落盘；随后把 `official_overrides.json` 的 `product_universe_csv_path` 改为该 campaign 私有文件，并把它纳入 campaign/worker identity 与 receipt。新增回归测试，证明第二次 prepare 或外部共享文件改写不会改变运行中 worker 的产品池路径或内容。

### P1-3：worker receipt 没有绑定 campaign，且恢复入口不读取 `ABANDONED.json`

证据：

- runner `:248-253` 的 `file_contract_sha256` 只哈希文件大小和内容 SHA，不包含 campaign ID 或路径；相同输入的新 campaign 可得到相同 contract。
- runner `:1219-1253` 写出的 worker receipt 没有 `campaign_id` 或当前 campaign 的绝对路径。
- runner `:571-579` 对 runtime 哈希时主动归一化 `STAGE015_CAMPAIGN_DIR`、`STAGE015_JOB_ID`、`TMPDIR` 和 `MPLCONFIGDIR`。
- runner `:1364-1414` 的 completed-job 校验只检查 campaign contract、snapshot SHA、输出 SHA 和一个长度为 64 的 execution contract；没有把 receipt 的原始 campaign/runtime 路径与当前 campaign 对齐，也没有重算 execution contract 后比较。
- 当前测试 `tests/test_stage015_development_label_batch.py:278-315` 构造了一个完全没有 campaign ID 的 receipt，并明确断言其校验为 `True`。
- runner 全文没有 `ABANDONED`、`reuse_forbidden` 或 `failure_receipt` 的恢复拒绝逻辑；`:2008-2024` 只做身份重算，`:2083-2087` 的直接 worker 入口也没有 tombstone gate。
- 对本次指定旧 campaign，当前代码会因为缺少 `official_overrides.json` 且 runner SHA 已从 `7c85022e...` 变为 `f3ab2aff...` 而失败；这是 schema/哈希变化带来的偶然阻断，不是对 `ABANDONED.json` 的显式执行。

影响：把一个采用当前新 schema、输入相同但已废弃 campaign 的完整 job 目录复制到另一个 campaign 后，validator 可以接受它，违反“同一 campaign 冷进程、旧 campaign 禁止复用”的预注册合同。

最小修复要求：worker receipt 写入并校验 `campaign_id` 与 resolved campaign path；校验未归一化的 `STAGE015_CAMPAIGN_DIR`/job ID 与 tmp 路径前缀；重算当前 `_worker_execution_manifest()` 并与 receipt 精确比较；在 orchestrator 和直接 worker 入口最前面显式拒绝 `ABANDONED.json` 或任一 `reuse_forbidden=true` receipt。新增“同内容双 campaign 复制 receipt 必须失败”和“本次废弃 campaign 必须失败”的回归测试。

## P2

### P2-1：prepare 失败会留下无统一 tombstone 的半成品目录

runner `:1288-1350` 先创建 campaign 目录、351 份 eligibility、审计文件和 overrides，最后才写 `campaign_identity.json`；`:1351-1361` 又在所有步骤成功后才写 progress/LATEST。该区间没有异常收口。builder、JSON 校验、hash 或数据库身份任一步失败都会留下状态不明确的目录。它通常因 identity 缺失而不能恢复，但审计语义不完整。

最小修复要求：在 campaign 目录创建后统一捕获 prepare 异常，原子写入 `ABANDONED.json`（含阶段、异常、`reuse_forbidden=true`），或先在私有 staging 目录完成全部准备后原子 rename；增加 builder 抛错、NaN、hash 失败三类残留测试。

### P2-2：负向测试覆盖不足，13/13 绿灯高估了修复闭环

新增测试只覆盖“一次 freeze、之后 helper 不再调用 builder”的 happy path。没有覆盖：真实 `_run_worker -> s901._run_live_c9` 的 builder 调用次数、NaN/Inf/非标量、prepare 失败残留、identity-after 聚合、跨 campaign receipt、ABANDONED 拒绝、第二个 prepare 干扰共享产品池。尤其 P1-1 是可静态绑定复现的错误，却未被测试触达。

最小修复要求：补齐上述边界测试；至少一条测试必须把 `s901.build_official_live_strategy_overrides` 设为调用即失败，并走完整 worker 调用边界，而不是只测 `_candidate_strategy_overrides()`。

### P2-3：Git 无法提供本次修复的前后 diff

`research/lines/futures_trend_ai_xgboost_ensemble/` 整体未被 Git 跟踪；`git diff -- tools/... tests/...` 为空，`git log --all -- <path>` 也无历史。只能从失败 campaign identity 的旧 runner SHA `7c85022e...`、failure receipt 的 replacement SHA 和当前 SHA `f3ab2aff...` 对齐版本，无法由 Git 独立证明改动只限于共享 builder 修复。

最小修复要求：在下一次评审前，把 runner、测试、预注册和必要的小型合同文件纳入可审查提交，提供真实 parent diff；大 campaign 产物仍可保持不入 Git。

## 已确认通过的部分

- 失败现场一致：`progress.json` 为 226/355、失败 job 为 `20240430_R17`；失败栈在 `main_contract_mapping.py:47` 的 `pd.read_csv(path)` 抛 `EmptyDataError`。
- 并发证据一致：R17 与 R18 同时启动；R17 于 23:13:22 失败，R18 继续到 23:14:13 完成。progress/failure receipt 记 226 个已确认完成任务，磁盘实际有 227 个完整 job 目录，后者是失败时仍在途的 R18；所有部分输出均已声明不可复用。
- 根因语义与上游文档一致：pandas 将 `EmptyDataError` 定义为空文件或无表头读取错误；`DataFrame.to_csv` 默认写模式为 `w`，Python 的 `open(..., 'w')` 会先截断既有文件。
- 当前 Stage015 runner 中，正式 `build_official_live_strategy_overrides()` 的文本调用只剩 `:1041` 的 prepare freeze；worker 在 `:1110-1120` 将 `s901` 的 builder 替换为读取快照的 candidate builder。
- 快照实现对 JSON 边界是 fail-closed：本地只读 probe 证明普通 bool/int/float/str 可通过，NaN/Inf 因 `allow_nan=False` 失败，list/null 被 non-scalar gate 拒绝。真实 override 源码中的本次字段均为 Python 原生标量。
- `official_overrides.json` 已进入 campaign 文件集合 `:774`、worker execution exact keys `:183`，worker receipt 也记录 snapshot SHA `:1239-1242`；这些方向正确，但不抵消上述 P1。
- 本次指定旧 campaign 当前不能被现 runner 恢复：旧 identity 不含 `stage015_official_overrides`，旧 227 份 receipt 均没有 `official_overrides_source`，直接加载快照得到 `frozen_official_overrides_missing`。
- 冻结研究合同未因修复变化：当前生成的 jobs CSV 内存 SHA 为 `aa0a14ae...`，与失败 campaign 完全一致；351 main + 4 A2、39 个 development 月、rank10..18 均不变。
- Stage010 标签 helper、Stage013 plan、Stage014 runner/feature panel/month split/feature contract 当前 SHA 均与失败 campaign identity 一致。九特征、双 XGBRegressor 固定参数、`MAX_WORKERS=2`、`MAX_JOB_SECONDS=600`、`MONEY_QUANTUM=0.000001` 元、`1e-9` 对账阈值均未改变。
- 未发现 sealed holdout label 读取：jobs 全部为 development，12 个 holdout 月仍为 `label_values_read_allowed=False`，失败 receipt 记录读取数 0；本次审计也没有打开任何 partial `label.json`。

## 验证记录

执行：

```bash
env PYTHONDONTWRITEBYTECODE=1 .py311/bin/python -m pytest -p no:cacheprovider \
  research/lines/futures_trend_ai_xgboost_ensemble/tests/test_stage015_development_label_batch.py -q
```

结果：`13 passed in 0.50s`。

附加只读 probe：

- 当前 jobs 序列化 SHA 与失败 campaign `jobs.csv` 一致。
- NaN/Inf/non-scalar snapshot 均 fail-closed。
- `_aggregate()` 的关键字参数不匹配可稳定复现。
- 本次旧 campaign 因缺少 snapshot 被当前 loader 拒绝。

未运行完整 355-job 回测，也未运行整条研究线测试；前者在本评审写入边界之外，且 P1-1 已证明即使任务完成也会在聚合失败。未执行真实正式 builder，因为它会改写共享产品池，违反本次“除 review 文件外不写入”的审计边界。

外部参考：

- [pandas `EmptyDataError` 官方文档](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.errors.EmptyDataError.html)
- [pandas `to_csv` 源码，默认 `mode="w"`](https://github.com/pandas-dev/pandas/blob/main/pandas/io/formats/format.py)
- [Python `open` 官方文档，`w` 会先截断](https://docs.python.org/3/library/functions.html#open)
- [Python `os.replace` 官方文档](https://docs.python.org/3.11/library/os.html#os.replace)

## 过拟合与继续价值

- 本修复是否构成看标签调参/过拟合：`否`。修复只触及并发输入构建与身份审计；jobs、特征、标签 helper、模型参数、并发数、超时和对账门均保持冻结，sealed holdout 标签读取数为 0。失败后的部分 development 标签没有被用于改特征、参数、月份、rank 或门槛。需要保留的风险是：39 个月 development 本身仍属于可自适应研究样本，完整标签出来后不得再改冻结合同。
- 从零跑完整 development 标签是否有价值：`有`。Stage012 的单月识别不足以训练冻结的账户边际双模型，完整 39 月 x 9 rank 面板仍是回答该结构性假设的必要数据；旧 campaign 受共享写竞态污染且整体废弃，不能拼接 226/227 个部分输出。但必须先清零三个 P1、补关键回归测试并重新独立评审，再创建全新 campaign 从 0 开始。

## 最终决策

`STOP`
