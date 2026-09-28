# Stage005A 父编排环境修复补充预注册

- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 记录时间：2026-09-02 18:44 +0800
- 分支：`codex/stage130-option-probe`
- 阶段性质：固定 smoke 的 pre-worker 编排缺口修复
- 是否重要突破：否
- 是否触发 A/B：否

## 已发生事实

- 第一个 Stage005A campaign：`campaign_20260902T183807+0800_62957`。
- campaign 合同：`bea7c4be69f2a4494c2e5dae5d59a6d672c329d963c5b035d2d9daaefb5437ab`。
- `--smoke` 在任何 worker 创建前失败；`job_outputs/` 不存在，没有回测结果、标签或交易数据。
- 直接错误：生产运行时 guard 发现父进程未设置 `QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR=1`。
- 根因：Stage005A 的独立 smoke 进程没有调用 Stage005 已有的 `parent_environment` 安装逻辑；campaign prepare 是另一个进程，其环境不会传递给后续 smoke 进程。
- 旧 campaign 必须写入 `ABANDONED.json`，不得复用。

## 冻结 snapshot 处理

- v2 runtime snapshot 已在旧授权下完整通过，receipt SHA256 为 `f67186f8e1603c81afeb5800e3e742287228862e61e984aac6c843a1a69bf0c2`。
- 该 snapshot 未运行策略，四份冻结输入和 SQLite 身份均精确；本次不删除、不重建、不选择新数据。
- 新授权必须把旧授权、snapshot receipt 和本补充预注册全部按 SHA 绑定，才允许新 campaign 使用该不可变 snapshot。

## 唯一代码改动

- Stage005A 各父入口显式调用 `batch_core.parent_environment`，设置：
  - `QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR=1`
  - 独立可写 `MPLCONFIGDIR`
  - 独立可写 `TMPDIR`
- 不修改任务、日期、rank、策略参数、数据输入、成本口径、账户口径或通过条件。
- 新建一个全新 campaign，仍只运行原预注册 4 个任务。

## 重新授权门

- 旧 `ALLOW_STAGE005A_SMOKE` 与 run authorization 只作为历史证据，不得直接授权修改后的 runner。
- 修改后必须重新运行专项测试和 `py_compile`，并由独立 reviewer 给出新的结构化 `ALLOW_STAGE005A_SMOKE`，P0=0、P1=0。
- 新授权须绑定 runner、runner tests、scope core 及 tests、原始预注册、本补充预注册、全部历史 BLOCK/ALLOW/authorization 和 runtime snapshot receipt。
- 新 campaign worker 前仍执行 root、ABANDONED、execution plan、authorization SHA、job 和 campaign identity 门。

## 过拟合与继续价值

- 运行前过拟合判断：否；本次只补环境传播，不接触任何结果或策略参数。
- 继续价值：是；已有 snapshot 身份有效，修复父环境后仍需用完全相同的 4 个任务完成最小复验。
- 停止条件：若新独立评审不放行，或同一环境问题再次出现，则不得继续 worker。
