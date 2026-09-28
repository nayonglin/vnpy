# Stage005A 运行时身份漂移修复预注册

- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 当前模式：研究；只读生产身份、冻结副本、固定 smoke，不训练模型、不读封存标签、不连接 CTP、不报单
- 记录时间：2026-09-02 17:48 +0800
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage005 批量执行前的运行时身份修复与技术复验预注册
- 是否重要突破：否
- 是否触发 A/B：否；本阶段不比较策略收益，仅复验标签运行时

## 外部调研与判断

- 参考资料：沿用 Stage005 已完成的 XGBoost 官方文档与 Python `subprocess`/`sqlite3` 官方文档调研；本阶段不引入新模型方法。
- 我的判断：生产数据库和主力映射已同时漂移，继续复用 Stage004 旧 smoke 结论会破坏输入同一性。应先冻结新身份并复跑完全相同的 4 个任务，禁止扩大样本或根据结果改任务。

## 漂移事实与冻结输入

- 生产数据库源：`/Users/bytedance/Desktop/person/vnpy_production_live/.vntrader/database.db`
- 预注册 SHA256：`db3342006f4220767f06e466bb40c046f372961cea41cef9a6d8bc1727fa0c4b`
- 预注册大小：`112271360` bytes
- 预注册 `dbbardata`：`1020420` 行；最大时间 `2026-09-02 00:00:00`
- 主力映射源 SHA256：`093d3bc767c09d9e0e4f4fbeb9846a091bf25c163cc31eddfd382cc1ff5490b7`
- 全量分钟线源 SHA256：`8e861633b08a82819a668c30c6799e2098d2beaa6863698351145018ea586784`
- 合约元数据源 SHA256：`24a3573e847e024411b13a3a3b775791ded57563b0a68b717d1065078201635a`
- 新运行时根目录：`/private/tmp/vnpy-stage005-curve-account-runtime-v2`
- 数据库冻结源、主力映射、分钟线、合约元数据均复制到新运行时 `frozen_inputs/`；worker 只允许读取冻结副本。
- `vt_setting.json` 固定写入 `{}`，SHA256 必须为 `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a`。
- 冻结前后必须重算所有源文件 SHA256；任一源发生变化立即失败，不接受自动更新预注册值。

## 固定 smoke 合约

- 任务集合严格固定为：`20220128_R10`、`20220128_R10_A2`、`20220228_R10`、`20220228_R11`。
- 任务来源仍为 Stage003 冻结 `development_jobs.csv`，不得替换日期、品种或 rank。
- 每个任务使用独立新进程、独立 `TMPDIR`、独立 `MPLCONFIGDIR`；`MAX_WORKERS=2`，单任务超时 `600s`。
- 禁止 checkpoint、completed result、跨 campaign 复用；只允许一个全新 Stage005A campaign。
- `20220128_R10` 与 `20220128_R10_A2` 的冻结输出必须逐文件完全一致。
- `20220228_R10` 与 `20220228_R11` 只用于确认反事实标签在新身份下仍可区分，不作为模型收益结论。
- 必须保留每个 worker 的输入身份、predecision 哈希、边界语义、进程/临时目录和耗时证据。

## 运行门禁

- worker 前必须有独立 reviewer 对本预注册、runner、核心 helper 和测试给出结构化 `ALLOW_STAGE005A_SMOKE`，且 P0=0、P1=0。
- snapshot、campaign 和 worker 分阶段授权；snapshot 只复制冻结输入，不运行策略。
- smoke 通过后仍不得直接运行 270 任务；需独立 reviewer 审核 Stage005A 结果和 Stage005 全部修复，再给出新的结构化 `ALLOW_STAGE005_BATCH`。
- 执行范围必须从命令、日志和产物推导：sealed holdout label、模型训练/模型文件、CTP 连接、order API 均为显式 0。
- 生产 checkout 必须保持 `d492ee072aa5a9d71477235d79f17d2a5db59db3` 且 clean；不写生产数据库和生产文件。

## 回测/归因参数

- 数据区间：由固定任务和冻结输入决定，不新增时间窗。
- 账户规模：继承正式回测引擎冻结口径；本阶段不修改。
- 成本口径：继承正式回测引擎冻结口径；本阶段不修改。
- 样本过滤：仅 4 个预注册 smoke 任务。
- 策略/归因口径：账户曲线反事实标签技术复验，不形成可交易组合曲线。

## 结果

- 期末权益：待运行；不得作为晋级指标。
- 总收益：待运行；不得作为晋级指标。
- 最大回撤：待运行；不得作为晋级指标。
- Sharpe：待运行；不得作为晋级指标。
- 总滑点：待运行；仅用于 A/A 与标签可辨识性核验。
- 总交易次数：待运行；仅用于 A/A 与标签可辨识性核验。
- 胜率：待运行；不得作为晋级指标。
- 其他关键指标：冻结身份精确、4/4 冷任务、A/A 精确、scope 零计数、无复用、worker 隔离。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：待 smoke 后复核。
- 原因：任务、日期、rank 和通过条件沿用 Stage004，且在观察新结果前冻结；没有调参、补样本或选择赢家。

## 继续价值反思

- 运行前判断：是，但仅限身份修复和固定 smoke。
- 运行后判断：待 smoke 和独立评审后复核。
- 原因：只有新身份可重复，后续 270 标签和模型对比才有可信基础；若固定 smoke 失败，应停止批量运行。

## 合入建议

- 是否更新本线 `LINE.md`：Stage005A 结果与独立评审完成后更新。
- 是否更新 `research/registry.md`：本次仍属既有研究线，不新增 line。
- 是否追加根目录 `memory.md/back_log.md`：预注册不追加；产生真实 smoke 回测数据后按要求追加 `back_log.md`。
