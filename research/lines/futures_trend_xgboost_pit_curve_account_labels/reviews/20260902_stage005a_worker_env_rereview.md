# Stage005A worker 环境修复独立复审

- 复审时间：2026-09-02 19:21 +0800
- 复审结论：`ALLOW_STAGE005A_SMOKE`
- 严重度：P0=0，P1=0，P2=0，P3=0
- 置信度：99%
- 授权范围：第三个且最后一个全新 campaign 的原固定 4 个 smoke；不授权 Stage005 270-job 批量

## partial backtest 复算

- 实际仅产生 `20220128_R10/R10_A2`，恰好 2 个 output、2 个 lock、2 个 log；`20220228_R10/R11` 未启动。
- A/A 八类输出逐字节一致：combined `e8233f...ec5a`、curve `43e7ae...87d2`、entry_candidates `eaa503...f058`、entry_risk `d46e55...6e4d`、label `fa6ba7...94e1`、summary `8ac2e1...cf9`、trade_events `b63eb2...bae`、trades `c0b9f0...277b`。
- label 复算：基准权益 `4,115,268.80`，期末 `4,740,258.80`，净利润 `624,990.00`，收益 `15.1871002934%`，最大回撤 `-8.4023449781%`，滑点 `11,160`，交易 `8`。
- summary 复算：初始资金 `150,000`，期末权益 `4,740,258.80`，总收益 `3060.172533%`，最大回撤 `-39.914746%`，Sharpe `2.065862`，滑点 `184,620`，交易 `408`，非零日胜率 `55.948553%`。

## 根因与修复

- 两个 worker 均完成策略计算，`input_identity_pass=true`、边界门通过、内部 reconciliation error 全为 0。
- 失败点是旧 worker wrapper 二次安装 parent environment，导致两个 receipt 的 TMP/MPL 都变成同一 orchestrator 路径；parent validator 正确拒绝。
- 当前 `run_worker` 不再调用 parent installer；`_worker_environment_gate` 在 lock 前要求 `TMP_ROOT/<campaign>/<job>/<run>/tmp|mplconfig`，正测试保留注入环境，负测试拒绝 orchestrator 路径。
- 旧 campaign 同时有 `failure_receipt.json` 和 `ABANDONED.json`，均禁止复用。

## Fresh 验证

- 三个指定测试文件：30 passed。
- runner、核心模块及相关测试：`py_compile` 通过。
- `_authorization_bindings()` 共 25 项，复审时 23 项存在且 SHA 已重算；只缺本 review 和 decision，run authorization 也按预期尚未创建。
- 无授权 preflight 精确 fail closed。
- 未运行 prepare、smoke、worker、backtest、CTP 或 order。

## 判断

- 过拟合：否；只修复和验证运行环境身份，未改变任务、日期、rank、输入、策略参数或通过门。
- 继续价值：是，但仅限第三个且最后一个固定 4 任务 smoke；若仍发生环境或身份失败，停止该复用架构。
