# Stage015 Decimal smoke campaign 独立审查

## 结论

- `VERDICT: PASS`
- 问题计数：`P0=0 / P1=0 / P2=0`
- 执行决定：`ALLOW_FULL_DEVELOPMENT_BATCH`
- 授权边界：仅允许在 `campaign_20260901T205915+0800_36804` 的冻结 identity 下复用该 campaign 自己已完成的 4 个 smoke job，并继续剩余 351 个 development job。不授权修改样本、rank、特征、标签、模型参数或门槛，不授权训练模型、生成 sealed holdout 标签、接入 shadow/实盘、连接 CTP 或调用订单 API。

## 审查对象与方法

- 新 campaign：`research/lines/futures_trend_ai_xgboost_ensemble/artifacts/stage015_development_label_batch/campaign_20260901T205915+0800_36804`
- 禁止复用的旧 campaign：`campaign_20260901T191852+0800_76524`
- 冻结 runner SHA256：`7c85022ed4d2094fd1f10c559863a5d4ce95f1193510906bac52c65702bc954f`
- 预注册 SHA256：`0e3c406f560aad95ebdff9d35f28bfa9e3ffa914ed38f2a7c4e2006cfd3063f7`
- 定向测试 SHA256：`34aac77a10e4b292da7c3db13a6ebe5d740c6fdd9c4ff1163616c97bf3695018`
- 本次采用只读实物重算：逐文件重算身份与 SHA、独立重算 campaign/worker contract、读取原始 CSV 对账、检查 inode/链接数/创建时间/日志/PID/TMP、执行不写 pytest cache 的定向测试。没有重跑回测，没有读取部分标签来挑模型或参数，没有连接 CTP，也没有修改 campaign、runner、预注册或测试文件。
- 除本审查文档外未写入研究线其他文件。该任务是冻结执行证据审计，不需要外部资料来替代本地实物证据。

## 分级问题

### P0

无。

### P1

无。

### P2

无。决策前五类 payload 按冻结的紧凑产物合同只保存归一化 SHA，不保存完整历史副本；本次通过冻结 runner、完整 worker 执行输入合同、两个活跃 worker receipt 和当前 target 实物交叉验证，符合预注册合同。

## 实物核验

### 1. 新 campaign 从 0 生成且未复用旧输出：PASS

- 旧 campaign 的 `failure_receipt.json` 明确记录 `stage015_float_representation_gate_failed_abandon_campaign`、`campaign_reuse_allowed=false`、`cross_campaign_job_output_reuse_allowed=false`；旧目录有 133 个有效输出，状态为 `failed`。
- 旧 campaign file contract 为 `4c374c8869abfe17a6234b82b136ba36f6795e77ead97929328f3bc0ee21557f`；新 campaign file contract 为 `b2b529c15293c320d5f2ac1c6b410e4ed1c3243bec43dcfaaa5a6557168b9f14`，两者不同。
- 新 campaign 目录创建于 `2026-09-01 20:59:15 +08:00`；当前只有固定四个输出目录、四份独立运行日志和五份 orchestrator/worker 锁记录，`.partial` 为空。
- reviewer 对四个 job 的 8 份业务输出和 1 份 worker receipt 共 36 个文件逐一比较：新旧 inode 全部不同，新文件硬链接数全部为 1，新文件创建时间全部晚于旧文件。runner 中不存在旧 campaign ID，也不存在跨 campaign copy、hardlink 或 link 路径。
- 四份 receipt 均为 `checkpoint_reused=false`、`completed_result_reused=false`。日志显示四个 worker 实际完成冷进程执行；独立 PID、TMP 和文件创建证据与 receipt 一致。
- 四份新 `label.json` 与旧 campaign 对应标签逐字节相同，这是相同冻结输入和标签公式的确定性结果；独立 inode、创建时间、日志、PID 和新 contract 证明它们不是旧文件复用。

### 2. campaign 与 worker contract 绑定：PASS

- `campaign_identity.json` 有 2,232 个清单键，对应 2,231 个唯一物理文件。逐文件重算结果为：缺失 0、大小漂移 0、SHA 漂移 0。
- 独立重算 file contract 得到 `b2b529c15293c320d5f2ac1c6b410e4ed1c3243bec43dcfaaa5a6557168b9f14`；包含 frozen runtime 的完整 contract 得到 `a5ecfc5c6795d922e41cbed06d57b0528be0e50892c7d8e6622286ec689e2136`，均与清单一致。
- production HEAD 为 `d492ee072aa5a9d71477235d79f17d2a5db59db3`，冻结 runtime 中 production status 与 workspace `vnpy` 核心状态为空。数据库 SHA 为 `ecbe812bd092ec8cedbd00d8b4b3ec2b1fa9311034dc8379fc6981033405eaf3`。
- 四份 worker contract 各有 1,867 个清单键、1,866 个唯一物理文件，reviewer独立重算均与 receipt 一致：`20220429_R10/R10_A2=74ff23cf...`、`20220531_R10=2780bea3...`、`20220531_R12=12417c4f...`。
- `smoke_receipt.json` 的 campaign ID、固定 job 列表、campaign contract、四份 worker receipt SHA 和每个 job 的八份输出 SHA 均与当前实物重算值一致。

### 3. 固定任务与 eligibility：PASS

- `jobs.csv` 为 39 个 development 月、351 个 main job 加 4 个 A2 sentinel，共 355 个任务；不存在 sealed holdout job。
- 当前输出目录集合精确为：`20220429_R10`、`20220429_R10_A2`、`20220531_R10`、`20220531_R12`。
- eligibility 文件与 audit 均为 351 行/份。全量 audit 中 rank10 的改动数均为 0，rank11..18 均只改目标月正式 rank10 行，`changed_target_rank10_only` 全部为真。

### 4. A/A、决策前 payload 与 signal 边界：PASS

- `20220429_R10` 与 `20220429_R10_A2` 的八份业务输出逐文件 SHA 完全一致：`summary`、`label`、`curve`、`combined`、`trades`、`entry_candidates`、`entry_risk`、`trade_events`。
- 活跃月 `20220531_R10` 与 `20220531_R12` 的决策前五类归一化 SHA 全部一致：`curve`、`trades`、`entry_candidates`、`entry_risk`、`trade_events`。
- 两个活跃 job 的 target `entry_candidates` 各 11 行，执行日期全部满足 `2022-05-31 < date <= 2022-06-30`；`ai_product_pool_signal_date` 无缺失且全部等于 `2022-05-31`。
- receipt 中决策前 signal date 全部严格早于当前 eval date，target signal date 集合与当前 CSV 独立重算一致。六类 target payload 的日期也全部位于各自 `(eval_date, next_eval_date]`。

### 5. curve/combined/trades 三路对账与 Decimal 修复：PASS

- reviewer 从四个 job 当前 `label.json`、`curve.csv`、`combined.csv` 和 `trades.csv` 独立复算期末权益差、目标期净 PnL、滑点、交易数及 trade 行数。
- 四个 job 每份 8 项对账误差全部为 0，最大绝对误差为 `0.0`，并与各自 worker receipt 的记录逐项相同。
- 四份 receipt 均存在 `monetary_reconciliation_quantum="0.000001"`。runner 只在金额一致性比较层使用 `Decimal(...).quantize(Decimal("0.000001"))`；Stage010 原始 label 仍直接写入 `label.json`，量化结果没有回写标签。
- 对旧 R14 表示失败原值独立复算：原始二进制 float 残差为 `-1.3969838619232178e-09`，微元规范化后为 `0.0`；人为增加完整 `0.000001` 元后误差保留为 `0.000001`，大于原 `1e-9` fail-stop 门。
- 四个 smoke 标签与旧 campaign 对应 `label.json` 内容和 SHA 均完全相同，确认收益、回撤、PnL、滑点、交易数等标签原值未因 Decimal 修复改变。

### 6. runtime、PID、TMP/MPL 与 timeout：PASS

- 四份 runtime 独立归一化后只有一个 SHA：`8b37a9dbf8de6b7774d08be4729b4a197a258abdf018ccdc2f52ec7abf991028`。归一化仅覆盖预声明的 campaign/job 临时环境字段。
- 四个 worker PID 互不相同且审查时均已退出；四个 TMPDIR 和四个 MPLCONFIGDIR 均互不相同，并同时绑定新 campaign、job 和唯一 run ID。
- worker receipt 最大完整内部墙钟为 `54.543959834001726` 秒；按日志创建到完成 mtime 的父进程侧粗粒度上界为 56 秒，均远低于 600 秒。
- AST 独立检查确认 `MAX_JOB_SECONDS=600.0`，父进程 `subprocess.run(..., timeout=MAX_JOB_SECONDS)` 已绑定真实超时；worker 在发布 receipt 前也执行自身墙钟门。

### 7. 训练标签与 holdout 发布隔离：PASS

- campaign 中不存在 `development_labels.csv`、聚合 `reconciliation.csv`、`decision.json`、模型文件或名称包含 holdout 的产物。
- 当前只有固定四个 smoke job 自己的 `label.json`，没有发布可供训练的 351 行 development 标签面板。
- 四个 label job 全部属于 development 且 eval date 早于 sealed holdout 起点 `2025-07-31`；sealed holdout 标签数为 0。
- `LATEST.json` 指向本次新 campaign，状态为 `smoke_passed`，完成数为 `4/355`。

## 只读验证

- 定向测试：`12 passed in 0.77s`。包含真实 R14 float 尾差、完整 `0.000001` 元负向控制、signal snapshot 边界、互斥锁和完成产物固定集合。
- pytest 禁用了仓库 cache provider，`PYTHONDONTWRITEBYTECODE=1`，临时目录位于 `/private/tmp`。
- 审查落盘前后 campaign 全树均为 402 个文件，摘要 SHA256 均为 `cb7d2397cb61312031aafbccb98501213ce4b893ce9335b0e3dd982ce839b963`。

## 最终判断

- 是否过拟合：否。本次只检查执行身份、确定性、边界和会计闭合，没有按四个部分标签的收益、回撤、月份、rank 或方向调整研究合同。
- 是否值得继续：是。新 campaign 已与失败旧 campaign 硬隔离，Decimal 修复保留标签原值，四 job 的执行和数值门全部闭合，继续补齐同一 campaign 的剩余 351 个冻结 development job 有明确价值。
- 完整批次完成后仍须重新执行 355 个 job 的终态 identity、A/A、逐月决策前 payload、signal 边界、三路对账、runtime 和 holdout absence 门；任一漂移必须 fail-closed，不得训练或读取 sealed holdout。
