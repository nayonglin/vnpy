# Stage005A worker 环境失败与修复预注册

- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 记录时间：2026-09-02 19:03 +0800
- 分支：`codex/stage130-option-probe`
- 阶段性质：真实 partial smoke 失败记录 + worker 环境角色修复预注册
- 是否重要突破：否
- 是否触发 A/B：否

## 已发生的真实运行

- campaign：`campaign_20260902T185715+0800_65899`
- campaign contract：`2e6c5da0b173ed586443359a03fa5444c12ae0246fa0d3da5e78d2018a080a2c`
- 固定 4 个任务已按计划启动；前两个并发任务 `20220128_R10`、`20220128_R10_A2` 产出后，父进程 completed-job validator 拒绝 R10，后两个任务未启动。
- campaign 已由 `failure_receipt.json` 标记 `smoke_worker_failed/reuse_forbidden`，本记录再追加 `ABANDONED.json`；不得复用任何输出或继续剩余任务。
- 该 campaign 运行了回测，但没有通过 smoke 身份门，因此不是有效 Stage005A 结果，不允许据此启动 Stage005 批量。

## partial 数值

- R10 与 R10_A2 的 `label.json` SHA256 均为 `fa6ba74a589420af2071ac3bbe99c62bba7dc73d26fe0f381a9df7b6a07a94e1`，A/A 数值一致。
- 未来标签窗口：期末权益 `4,740,258.80`，未来收益 `15.1871002934%`，未来最大回撤 `-8.4023449781%`，未来净利润 `624,990.00`，未来滑点 `11,160`，未来交易 `8`，未来交易日 `16`。
- prefix summary `2018-01-02 -> 2022-02-28`：账户初始资金 `150,000`，期末权益 `4,740,258.80`，总收益 `3060.172533%`，最大回撤 `-39.914746%`，Sharpe `2.065862`，总滑点 `184,620`，总交易次数 `408`，非零日胜率 `55.948553%`。
- 两个 worker wall 为 `42.851273s/42.851289s`，normalized runtime SHA 一致为 `abeb07901315d742a348f39baaede71877a8f746c6a5622cd0c8a33465baf6b9`。
- 未产出 R11 active challenger，因此没有新的收益/回撤改进结论；以上 A/A 数据仅用于失败审计。

## 根因证据

- 父 smoke 入口已正确安装 orchestrator 环境，并为 subprocess 生成 job 专属环境。
- worker wrapper 启动后再次调用 `_install_parent_environment`，把已注入的 job 专属 `TMPDIR/MPLCONFIGDIR` 覆盖为：
  - `/private/tmp/vnpy-stage005a-runtime-identity-smoke/orchestrator/tmp`
  - `/private/tmp/vnpy-stage005a-runtime-identity-smoke/orchestrator/mplconfig`
- 两个 receipt 的 TMP/MPL 完全相同，不满足独立 worker 隔离合同。parent validator 正确拒绝，不得放宽 validator。

## 唯一修复

- `run_worker` 不再调用父环境安装函数。
- 新增 worker environment gate：要求 QMT guard 为 `1`，TMP/MPL 均位于 `TMP_ROOT/<campaign>/<job>/<run>/`，同一 run parent，目录名严格为 `tmp/mplconfig`。
- 父级 preflight/prepare/smoke 仍显式安装 orchestrator 环境。
- 不修改任务、样本、rank、策略参数、数据、成本、账户口径或 smoke 通过条件。

## 重新授权门

- 专项与全线测试、`py_compile` 必须通过。
- 必须由独立 reviewer 同时审查本次 partial backtest、根因、worker gate、失败 campaign 禁复用和 immutable snapshot。
- 只有新的结构化 `ALLOW_STAGE005A_SMOKE` 且 P0=0、P1=0，才允许第三个全新 campaign；若第三次仍出现环境/身份链失败，则停止运行并重新评估复用架构，不再继续补丁重试。

## 参数变更

- 新增参数：无策略参数；只新增 worker environment identity gate。
- 修改参数：无。
- 删除参数：无。
- 新增回测结果：上述两个无效 A/A partial 输出。
- 修改/删除回测结果：无；原 Stage004 成功 smoke 结果不变。

## 过拟合与继续价值

- 运行前过拟合判断：否；任务与门事前冻结。
- 运行后过拟合判断：否；失败后没有换样本、改 rank 或调参数，只修环境角色。
- 运行前继续价值：是；用于验证新输入身份。
- 运行后继续价值：仍有，但只允许一次修复后的固定 4 任务重跑；若再次失败则停止该复用执行架构。
