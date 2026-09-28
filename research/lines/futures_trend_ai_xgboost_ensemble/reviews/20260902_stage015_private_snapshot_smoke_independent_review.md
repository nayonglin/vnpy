# Stage015 private snapshot smoke 独立审查

- 评审时间：`2026-09-02 01:01 +0800`
- campaign：`campaign_20260902T003958+0800_80965`
- campaign 路径：`research/lines/futures_trend_ai_xgboost_ensemble/artifacts/stage015_development_label_batch/campaign_20260902T003958+0800_80965`
- 冻结 file contract：`d8649b5d5c1d7215100834f372733d170c703ce168097ed11252545806eda2e2`
- runner SHA256：`29797754f5a22597f28a29de78ac0d972f46b02b8718116f236b29bcf8662503`
- test SHA256：`ad064140b3dc8944829a873501b6e6fec95b2e16cb543eea172f6f101705fcd5`

## 结论先行

- `VERDICT: FAIL`
- 严重度：`P0=0 / P1=1 / P2=0`
- 最终决定：`STOP`
- 不授权完整 development batch。四个 smoke job 的当前产物、身份、A/A、边界、八项三源对账、runtime 和旧 campaign 隔离均通过独立重算，但 shared builder race 没有从完整 worker 调用链移除。
- 当前 worker 只替换了 `s901.build_official_live_strategy_overrides`；`s901._run_live_c9()` 在使用该替换函数前先构造 `_c9_profile()`，后者仍经 Stage819 -> Stage813 -> Stage777 调用两个会覆盖共享 CSV 的 builder。当前 smoke 期间两个共享文件确实在 worker 运行窗口内同步更新，独立内存 monkeypatch probe 也证明一次 `_c9_profile()` 会调用这两个 builder。
- private universe 能保护本 campaign 最终运行 spec 不去读取共享 universe，所以四个 smoke job 可以全部通过；但它没有消除共享写副作用。完整批次会继续以两个 worker 反复覆盖 workspace/production hardlink 共享文件，重新暴露并发写和外部读者竞态，且该副作用不在当前 campaign/worker identity 中，现有 gates 无法发现。
- 修复必然改变 runner SHA 和 file contract；当前 campaign 已发生共享写，不能在原 identity 下续跑。后续必须修复、补回归测试、独立复审，并从 0 创建另一个新 campaign。

## P0

无。

## P1

### P1-1：worker 仍通过嵌套 profile builder 覆盖共享 universe 与 eligibility

1. Stage015 runner `:1214-1219` 仅把 `s901.build_official_live_strategy_overrides` 临时替换为 campaign snapshot builder，然后调用 `s901._run_live_c9()`。
2. production `analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py:_run_live_c9` 先在 `:846` 调用 `s847._c9_profile(metadata)`，到 `:861` 才调用已被替换的 `build_official_live_strategy_overrides()`。
3. `_c9_profile` 经 `analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine.py:433-435`、`analyze_qmt_roll_stage825_stage819_intraday_rule_forensics.py:86-89` 进入 `build_official_candidate_stage819_30w_overrides()`；再经 Stage813 到 `qmt_roll_official_candidate_stage777_config.py:173-176` 调用：
   - `build_static18_plus_fu_universe()`；
   - `build_ai_satellite_post_signal_eligibility()`。
4. 两个函数分别在 `run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest.py:121-133` 和 `:186-204` 使用普通 `DataFrame.to_csv()` 覆盖共享目标，不是 campaign-private 原子写。
5. 独立只读行为 probe 在内存中把这两个 builder 替换为不写文件的计数函数，调用一次真实 `_c9_profile(metadata)`，结果为 `call_count=2`，调用列表精确为上述两个 builder。该 probe 没有执行实际 builder，也没有改 artifact。
6. 现场旁证：共享 universe 与 shared post-signal eligibility 的 mtime 都为 `2026-09-02 00:42:22 +0800`；第二批 worker 在 `00:42:02/00:42:03` 取得锁，`00:42:57/00:42:58` 生成 receipt。两个共享路径在 workspace 与 production checkout 中是同一 inode `422227924`/`422227925`、链接数 `2`。
7. 当前 private universe 是独立 inode `527245654`、链接数 `1`，SHA 与共享源同为 `72c5ca576bfe8aebe12da1e750d9eac980633a43ab9944479a77a7e824a71e34`；这解释了当前业务输出稳定，但不能否定 worker 对共享文件的额外写入。
8. 现有 test `:85-135` 只验证 `_freeze_official_overrides` 后 `_candidate_strategy_overrides` 不再调用 official builder，`:138-182` 只验证 aggregate identity；没有执行 mocked 完整 `_run_worker` / `_run_live_c9` 边界。`23/23` 绿色没有覆盖本调用路径。

影响：`MAX_WORKERS=2` 的 full batch 会继续并发执行这些非原子共享写；当前 identity 只收录 private universe 和正式 eligibility，不收录这两个被嵌套 builder 改写的共享输出，因此执行身份、发布前 identity 和 smoke receipt 都可能保持 PASS。该问题阻断 full development batch。

关闭条件：完整 worker 调用链不得执行任何共享输出 builder；增加 mocked `_run_worker` 或等价集成回归，把上述两个嵌套 builder 设为调用即失败；新 runner 通过 Stage015/整线测试和独立复审后，从 0 创建新 campaign，禁止复用本 campaign 四个输出。

## P2

无独立 P2。缺失的完整 worker 回归覆盖是 P1-1 能漏过现有测试的直接组成部分，不重复计数。

## 正向实物核验

### 1. campaign 初始化、任务和身份

- `jobs.csv` 为 `355` 行任务：`351` main + `4` A2，覆盖 `39` 个 development 月，每月 rank `10..18` 完整；sealed holdout job 为 `0`。
- `eligibility/` 恰有 `351` 份 CSV，`eligibility_audit.csv` 恰有 `351` 行；rank10 改动行为 `0`，rank11..18 均只改目标月 rank10 行，审计字段全部通过。
- 当前只有固定四个输出目录：`20220429_R10`、`20220429_R10_A2`、`20220531_R10`、`20220531_R12`；`.partial` 为空，`ABANDONED.json` 不存在。
- `campaign_identity.json` 有 `2,233` 个清单键、`2,232` 个唯一路径；逐文件重算缺失 `0`、size 漂移 `0`、SHA 漂移 `0`、hash 期间变化 `0`。
- 独立重算 file contract 为 `d8649b5d...eda2e2`，完整 runtime contract 为 `bd121576544e88a1d64c4e330126ab888bcd3d7336dd183dd53e0963185d68ea`，均与 identity 一致。
- private `official_product_universe.csv` 已以 `product_universe` 键收录 identity；`official_overrides.json.product_universe_csv_path` 精确指向该 private 文件。private/shared 内容 SHA 相同但 inode 不同。
- campaign identity 于 `00:40:20` 创建；当前 36 个 smoke 文件全部在此后创建，均为普通文件、链接数 `1`，支持 smoke 前不存在可直接复用的当前输出。

### 2. smoke receipt、worker receipt 和 output binding

- `smoke_receipt.json` 的全部总 gates、八个 `AA_file_gates` 和五个 `active_predecision_gates` 均为 `true`；`passed=true`，decision 为 `stage015_smoke_pass_allow_full_development_batch`。
- smoke receipt 的 campaign ID、固定四 job、file contract 均正确。该 receipt 本身不含 `campaign_path` 字段；`progress.json` 和四份 worker receipt 的绝对 path 均精确绑定当前 campaign，且 full runner 会在目标目录上重新执行 `_validate_smoke`，因此本项不另列 P2。
- 四份 worker receipt SHA 和各自八份业务输出 SHA 均由当前文件独立重算，并与 smoke binding、worker receipt 三方一致。
- 四份当前执行 identity 由冻结 validator fresh 重算均通过，每份 `1,867` 个唯一物理文件；contract 分别为：
  - `20220429_R10` / `R10_A2`：`a2ab5fc15a60c5af8ed33d11d0d03ada66b5628081575deb51e96267df8ac8cc`；
  - `20220531_R10`：`6e54a692948dcb43417c2f6708629d04090c0df69b3631126a4053084bd42dc1`；
  - `20220531_R12`：`c5d1781e5123a672e3dd326fd9246d04c72ff5d8fc89b9462cba8d10e59ecabf`。
- 四份 receipt 均声明 `official_overrides_source=campaign_snapshot`、private universe SHA 正确、`input_identity_pass=true`、`checkpoint_reused=false`、`completed_result_reused=false`。

### 3. runtime、wall、金额与三源对账

- PID 为 `81107 / 81108 / 81205 / 81212`，互不相同；锁文件 PID 与 receipt 一致，四 PID 在审查时均已退出。
- 四套 raw `TMPDIR/MPLCONFIGDIR` 均唯一，路径同时绑定 campaign、job 和 run id；receipt 顶层值与 `runtime.environment` 精确相同。
- 仅归一化 `TMPDIR/MPLCONFIGDIR/STAGE015_CAMPAIGN_DIR/STAGE015_JOB_ID` 后，四份 runtime SHA 独立重算均为 `8b37a9dbf8de6b7774d08be4729b4a197a258abdf018ccdc2f52ec7abf991028`。
- 最大 worker wall 为 `54.84300437499769s < 600s`；四份 `monetary_reconciliation_quantum` 均为 `0.000001` 元。
- 未输出任何部分 label 数值或收益分布。只按冻结公式从各 job 的 `label.json` 与 target `curve/combined/trades` 重算以下八项误差：end equity 对 future net PnL、curve net PnL/slippage/trade count、combined net PnL/slippage/trade count、trade rows。`4 x 8` 项全部为 `0.0`，与四份 receipt 完全一致，global max abs error 为 `0.0 <= 1e-9`。

### 4. A/A、predecision 与 entry boundary

- `20220429_R10` 与 `20220429_R10_A2` 的八份业务文件逐文件 SHA 完全一致：`summary/label/curve/combined/trades/entry_candidates/entry_risk/trade_events`。
- `20220531_R10` 与 `20220531_R12` 的五类 predecision SHA 全部一致：`curve/trades/entry_candidates/entry_risk/trade_events`。紧凑合同不保存 predecision 原始副本，本次只验证 receipt 内哈希一致及冻结生成/测试路径，没有读取或分析部分标签分布。
- 四个 job 的六类 target payload 日期均满足 `(eval_date, next_eval_date]`；target entry candidates 非空，signal date 全部非空且等于当前 eval date；receipt 行数和当前 CSV 独立重算一致。
- `summary.csv` 与 `curve.csv` 的 `window_label` 均为真实 `2018-01-01_to_<next_eval_date>`。

### 5. development/holdout/模型/CTP/order 边界

- `development_labels.csv`、聚合 `reconciliation.csv`、`decision.json`、`report.md` 均不存在；只有四个 smoke job 自己的 `label.json`。
- 四个 label job 全部属于 development；sealed holdout job、holdout 命名 artifact 和 sealed holdout label 均为 `0`。
- 未发现模型 artifact。Stage015 runner AST 没有直接导入 XGBoost/LightGBM/sklearn/vnpy_ctp，也没有 `fit/train/connect/send_order/cancel_order/subscribe` 调用；smoke receipt 为 `trains_model=false`、`ctp_connected=false`、`order_api_called_count=0`。
- 本次未连接 CTP、未调用 broker/order API、未训练模型、未读取 sealed holdout 标签。

### 6. 旧两个 campaign 无复制/复用

- 旧 `campaign_20260901T191852+0800_76524` 的 failure receipt 明确 `campaign_reuse_allowed=false`、`cross_campaign_job_output_reuse_allowed=false`；旧 `campaign_20260901T205915+0800_36804` 明确 `reuse_forbidden=true`、`partial_job_outputs_reusable=false`。
- 对当前四 job 的八份业务输出加 worker receipt，共 `36` 个文件，分别与两个旧 campaign 同路径文件比较：两个旧 campaign 均为 `same_inode_count=0`，当前文件全部创建得更晚，当前链接数全部为 `1`；worker receipt SHA 均不同。
- 两个旧 campaign 的 `32/32` 业务输出 SHA 与当前相同，符合冻结输入的确定性预期；不同 inode、birthtime、四份新日志、四个新 PID、锁记录以及 `completed_result_reused=false` 共同证明这是新执行，不是旧文件复制/硬链接复用。

## 测试与只读 probe

执行：

```bash
QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR=1 PYTHONDONTWRITEBYTECODE=1 \
MPLCONFIGDIR=/private/tmp/vnpy-stage015-development-label-batch/orchestrator/mplconfig \
TMPDIR=/private/tmp .py311/bin/python -B -m pytest -p no:cacheprovider \
research/lines/futures_trend_ai_xgboost_ensemble/tests/test_stage015_development_label_batch.py -q
```

结果：`23 passed in 0.66s`。

整条研究线 tests：`91 passed in 4.27s`。

必要只读 probes：

- 全量 campaign identity/current worker execution identity fresh 重算均通过。
- 四 job output/receipt binding、八项对账、target boundary、A/A、predecision hash、runtime normalization 均独立重算。
- 嵌套 builder probe 不执行真实写函数，只在内存替换为计数 stub；一次真实 `_c9_profile` 构造命中两个共享 builder，确认 P1 调用链。
- campaign 全树在测试/probe 前后均为 `404` 个文件，摘要 SHA256 均为 `62acb6daf2f61108c93e31a1c69dfe746caa301e25ba3ae4505edbb4449dde4e`；runner、tests、artifacts 均未修改。
- 未运行完整 355-job batch；在 P1 未关闭时继续运行没有审计价值。

## 外部调研与判断

- Python 官方 `os.stat_result` 语义支持以 device/inode/link count 识别同一物理文件；本次 inode 只作为旧文件复用和 hardlink 的证据之一，并与 SHA、birthtime、PID、日志交叉使用。
- pandas 官方源码中 `DataFrame.to_csv` 的默认 `mode="w"`；这与本地两个 builder 对共享目标的覆盖写代码一致。最终阻断结论仍来自本地真实调用链、mtime 和行为 probe，不依赖外部资料替代本地证据。
- 参考：<https://docs.python.org/3.11/library/os.html>；<https://github.com/pandas-dev/pandas/blob/main/pandas/io/formats/format.py>。

## 过拟合与继续价值

- 运行前判断：`不构成过拟合`。本轮是冻结 campaign 的执行与法证审查，没有按部分 label 收益、回撤、月份、rank 或方向改合同；没有读取收益分布或 sealed holdout 标签。
- 运行后判断：`仍不构成过拟合`。发现的是与标签值无关的调用链副作用；正向对账只验证会计闭合，没有据此选择特征、模型或门槛。
- 当前 campaign 是否值得继续 full batch：`否`。P1 未关闭，继续会放大共享写次数；修复后 runner SHA/contract 改变，本 campaign 也不再可续跑。
- 这条研究是否仍值得继续：`是`。冻结的 39 月 x 9 rank 账户边际 development 标签仍是检验预注册双模型的必要输入；有价值的下一步是先消除完整 worker 链的全部共享写并补测试，再创建全新 campaign，从 0 重跑 smoke 和独立审查。

## 最终决定

`STOP`
