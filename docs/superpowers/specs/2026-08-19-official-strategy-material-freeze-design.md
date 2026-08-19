# 正式策略物料固化与自动登记设计

- 状态：待用户审阅
- 日期：2026-08-19
- 研究线：`futures_official_strategy_material_governance`
- 当前正式策略：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 设计范围：仓库内物料发布器、不可变发布目录、Git/LFS 门禁、repo-local Skill、Stage935 和后续实验登记协议

## 1. 背景与问题

当前正式运行已经有 Stage179 release manifest：它记录正式版本、资金口径、来源 commit、关键文件 SHA256、tree fingerprint 和资格证据。当前正式生产 worktree 中观察到的 `c9-15w-candidate.json` 为 schema v2，并绑定约 80 个关键文件。它解决了“当前工作树字节是否符合批准版本”的一部分问题。

但现状仍有三个缺口：

1. 当前正式配置引用的 Stage182 AI eligibility CSV 位于被 Git 忽略的 `examples/portfolio_backtesting/backtest_outputs/`。清单能记录生成器代码，却不能保证其他电脑 clone 后获得决策数据字节。
2. Stage935 月更成功后只在 ignored 输出目录生成新池，没有统一的 Git 发布、版本分配和激活协议。
3. 后续实验会生成模型、池快照、特征 schema 和评分结果，但目前没有明确区分“决策/复现资产”与“缓存/展示产物”的统一登记入口。

因此，本设计不替换 Stage179，而是在其上增加“物料实体快照”层，并让 Stage179/正式运行绑定该快照。

## 2. 目标与非目标

### 2.1 目标

- 正式策略的全部决策性物料物理存在于一个固定、不可变、被 Git 或 Git LFS 管理的版本目录中。
- 每个发布版本有单调物料版本号、北京时间/UTC 时间、来源 commit、文件级 SHA256 和整体 fingerprint。
- 新 clone 在安装运行依赖后，不依赖原电脑的 ignored 文件即可验证并运行同一个正式策略物料版本。
- Stage935 月更和后续实验通过共同的登记协议自动生成清单并暂存到 Git。
- 正式物料发布、资格校验、激活和回滚均 fail-closed 且可审计。

### 2.2 非目标

- 不把 `.py311`、vn.py、CTP framework、系统库或其他运行环境提交到 Git。
- 不提交 CTP/SimNow 密码、`.env`、本地账户配置、设备指纹或 SMTP 凭据。
- 不提交原始行情库、完整特征缓存、图表、Dashboard、临时日志、订单 ledger 或 broker 状态。
- 不把当前约 758 个名称含 AI/model/pool 的输出文件全部迁入 Git；只有声明为决策或复现资产的文件进入受控目录。
- 不改变 Stage847/C9 的策略逻辑、AI 排名逻辑、资金口径和下单纪律。
- 不自动 push，不自动部署，不自动发送订单。

## 3. 方案选择

### 3.1 采用：完整不可变快照

每次发布创建一个新目录，将所有已确认的正式物料复制到 `payload/`，保持其仓库相对路径。清单同时绑定快照字节和原逻辑路径。正式运行在激活后从版本指针解析决策资产，并校验正在执行的代码/config 与快照一致。

优点：满足“固定文件夹中具备全部物料”，clone 可获得完整实体，差异可审阅，历史版本可并存。代价是发布目录会有重复文件；Git 的对象去重/增量压缩和 Git LFS 的内容寻址可控制重复成本。

### 3.2 未采用：仅保存 manifest

只记录原路径和哈希最轻量，但无法保存 ignored AI 池实体，也不满足集中固化要求。

### 3.3 未采用：Git tag 加压缩归档

压缩包适合离线备份，但不利于代码审阅、文件级差异、月度 AI 池更新和 LFS 管理。Git tag 可以作为补充标记，不作为物料载体。

## 4. 目录与身份模型

```text
official_strategy_materials/
├── CURRENT.json
└── <strategy_version>/
    ├── index.json
    └── releases/
        └── m0001_20260819T153000+0800_<source-sha12>/
            ├── manifest.json
            ├── inventory.csv
            ├── checksums.sha256
            ├── RELEASE.md
            └── payload/
                └── <原仓库相对路径>
```

身份字段分三层：

- `strategy_version`：来自 `qmt_roll_official_live_config.py`，描述策略语义，例如 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- `material_version`：同一策略版本下从 `m0001` 单调递增，只在物料字节或资格绑定变化时增加。
- `release_id`：`<material_version>_<created_at_cst>_<source_commit前12位>`，同时提供可读时间和 Git 身份。

发布快照的 Git commit 无法无循环地写入同一个被哈希的 manifest。设计采用两阶段提交解决：

1. release commit 提交不可变目录；manifest 记录其准备来源 `source_commit`。
2. activation commit 更新 `CURRENT.json`，记录 `release_id`、`release_commit` 和资格证据。

Git 历史与 activation commit 共同提供发布 commit 身份，不在 manifest 中伪造自引用哈希。

## 5. 物料分类

每个 inventory 行必须属于以下一类：

| 分类 | 示例 | 是否进入正式快照 |
| --- | --- | --- |
| `runtime_code` | 策略、执行 gate、解析器、公共模块 | 是 |
| `strategy_config` | 正式版本、资金、路径和 profile 配置 | 是 |
| `decision_asset` | 正式 AI 池、eligibility、固定 universe | 是 |
| `model_artifact` | 被正式推理直接加载的模型权重 | 是 |
| `feature_contract` | 特征 schema、预处理/编码规则、类别映射 | 是 |
| `qualification_evidence` | Stage179 资格摘要、必要的测试/审核引用 | 是 |
| `operational_config` | 无秘密的 launchd/plist、运行参数模板 | 是 |
| `external_runtime_contract` | Python/vn.py/CTP 版本约束 | 只记录，不复制依赖实体 |
| `raw_market_data` | 原始行情、数据库 | 否 |
| `cache_or_visualization` | 特征缓存、曲线、Dashboard | 否 |
| `runtime_state` | ledger、broker snapshot、日志 | 否 |
| `secret` | 密码、token、账户 env | 禁止 |

“AI 文件”不通过名称猜测。生成器必须显式声明文件角色；没有角色的输出仍留在 ignored 工作目录，不能被正式策略引用。

## 6. 组件设计

### 6.1 确定性发布库

新增仓库代码模块，职责仅包括：

- 解析当前正式 profile 和策略版本；
- 收集、规范化、分类和校验物料；
- 复制到临时发布目录；
- 生成 canonical JSON、inventory、checksums 和人类摘要；
- 独立重读并验证全部哈希；
- 原子重命名为最终不可变目录；
- 生成限定路径的 Git 暂存/提交计划。

发布库不调用网络、不运行回测、不连接 CTP、不调用订单 API。

### 6.2 发布 CLI

CLI 提供三个显式动作：

- `prepare`：发现、校验、复制、生成 manifest，并执行精确路径的 `git add`。
- `commit`：要求确认文本、干净来源树和成功的 `prepare` 结果，只提交本次 release 目录、对应 `index.json` 及必要 `.gitattributes` 变更。
- `activate`：要求 release commit 已存在、资格证据有效且重新验 hash，更新 `CURRENT.json` 并创建独立 activation commit。

默认动作是 `prepare`。`commit` 和 `activate` 不 push；任何部署仍沿用正式实盘 SOP。

### 6.3 Repo-local Skill

新增 `skills/freeze-official-strategy-materials/`：

- `SKILL.md` 只保存触发条件、授权边界、流程判断和停止条件；
- `references/material-contract.md` 记录 manifest 字段、物料分类和生成器登记协议；
- Skill 调用仓库中的确定性 CLI，不在提示词中重写复制、哈希或 Git 逻辑；
- 当用户要求“保存/固化/发布正式策略物料、生成正式版本快照、月更 AI 池入库、验证 clone 可复现”时触发；
- 普通回测、alpha 优化和仅查看报告时不触发。

### 6.4 正式运行解析器

正式运行新增只读解析器：

1. 读取 `official_strategy_materials/CURRENT.json`；
2. 校验 active release 的 manifest 和 payload 哈希；
3. 将正式 AI eligibility 等决策资产解析到 active release payload；
4. 校验当前运行代码/config 与 release inventory 中对应字节一致；
5. 任何缺失、漂移或错误版本均阻断正式启动。

运行依赖仍从本机环境加载；解析器只保证策略语义物料身份。

### 6.5 AI 资产登记接口

生成器成功后输出结构化 `ai_artifacts` 列表，每项至少包含：

- `path`
- `role`
- `logical_name`
- `generator`
- `data_cutoff`
- `eval_date` 或不适用原因
- `feature_schema_version` 或不适用原因
- `reproducibility_required`
- `promotion_scope`：`experiment` 或 `official_candidate`

实验资产先发布到：

```text
research/ai_assets/<line_id>/<stage>/<run_id>/
```

其中仅保存决策/复现资产及 manifest。晋级正式版本时，正式发布器消费该 manifest 并重新复制、重新哈希到 `official_strategy_materials/`；正式快照不引用实验目录中的可变路径。

## 7. 物料发现协议

发现采用四层并集：

1. Stage179 `DEFAULT_CRITICAL_FILES` 和正式 release manifest 的已声明关键文件。
2. 正式配置中的 `*_path`、`*_file`、eligibility、universe、schema 和 model 路径。
3. 从正式入口开始的仓库内 Python import 静态闭包。
4. Stage935/182/183 和未来生成器输出的显式 `ai_artifacts` 声明。

以下情况必须阻断，而不是猜测：

- 动态 import 或动态路径无法解析且未显式声明；
- 正式代码读取 repo 外文件作为策略决策输入；
- 决策资产处于 ignored/untracked 状态；
- 发现符号链接、路径穿越、重复逻辑名称或同名不同字节；
- Stage179 关键文件与新快照 inventory 发生未解释的不一致。

## 8. Manifest 与版本信息

`manifest.json` 使用 canonical JSON，至少包含：

- schema version、release ID、strategy/material version；
- 创建时间 UTC、北京时间、创建工具版本；
- source commit、source tree fingerprint、branch 仅作诊断字段；
- official profile、capital、capital label、research line；
- AI pool eval date、effective month、source max date、training label cutoff；
- generator 名称/commit/参数和命令摘要；
- feature schema、preprocessing contract、模型格式；
- qualification status、evidence IDs、Stage179 manifest digest；
- parent material version 和新增/修改/删除统计；
- 文件 inventory、整体 tree fingerprint、manifest SHA256；
- `send_order_api_called_count=0`，用于证明发布流程没有订单副作用。

时间字段必须同时保存机器可解析 UTC 和用户可读 `Asia/Shanghai` 时间。branch 不是身份；40 位 source commit 和文件哈希才是身份。

## 9. Git 与 Git LFS

- 小型文本、JSON、Python、Markdown、普通 CSV 直接进入 Git。
- 模型权重、Parquet 和超过 10 MiB 的文件默认进入 Git LFS。
- 因 `.gitattributes` 不能按大小表达规则，发布器为每个超过阈值的精确仓库路径生成排序稳定的 LFS attribute 行；模型/二进制扩展名可使用受控模式。
- `.gitattributes` 必须与首个 LFS 资产一起提交。
- 发布前必须验证 Git LFS 已安装、filter 配置有效、目标 remote 支持上传和下载；验证失败时阻断大文件发布，不退化成普通 Git 大对象。
- clone 验证必须检查 LFS 文件不是仅有 pointer 文本，并复算 SHA256。

## 10. 发布与激活数据流

### 10.1 Prepare

1. 读取 `work-type.txt`、registry、正式配置和当前研究线。
2. 要求来源 worktree 的 tracked 文件和 index 无修改，且不存在未被忽略的 untracked 文件；ignored runtime 输出可以存在但不得被直接引用。
3. 解析 profile、分配下一 `material_version`。
4. 发现并分类全部物料。
5. 校验 Git/LFS、秘密路径、时序、资格来源和未解析依赖。
6. 在同一文件系统临时目录复制 payload，逐文件 fsync、SHA256。
7. 生成清单后重新从磁盘独立验证。
8. 持有仓库级发布锁，重新读取 `index.json`，确认版本号未被并发发布占用后，原子重命名到最终 release 目录。
9. 原子更新并校验 `index.json`。
10. 只 `git add` 本次 release 路径、对应 index 及必要 attributes；输出变更摘要和 commit 建议。

### 10.2 Commit

1. 要求显式确认文本包含 release ID。
2. 再次验证 staged path 集合只含允许文件。
3. 创建 `release(materials): <release_id>` commit。
4. 输出 commit SHA；不 push、不激活。

### 10.3 Qualify and Activate

1. 从 release commit 重新读取物料，不信任工作目录缓存。
2. 运行 Stage179/正式路径一致性/clone smoke 等资格门禁。
3. 资格失败则保留不可变候选但不更新 `CURRENT.json`。
4. 资格通过后，`CURRENT.json` 写入 strategy version、release ID、release commit、资格证据和 activation 时间。
5. 创建 `activate(materials): <release_id>` commit；不 push、不部署。

## 11. Stage935 月更集成

Stage935 保留现有锁、完整月末、Stage183 源刷新、Stage182 inference、Top9、安全字段、邮件和零订单 API 校验。只在其已有成功条件全部满足后增加发布动作：

1. Stage935 仍先在 ignored 工作目录生成候选。
2. 校验通过后生成 `ai_artifacts` 声明。
3. 发布器创建新的正式物料 release candidate，并自动 `git add`。
4. 定时任务默认停在 `publication_required`，不在生产 worktree 静默 commit。
5. 用户或受控 bot 在显式授权下执行 release commit、资格门禁和 activation commit。
6. 当月日度策略只读取已激活池；未激活的新池不能通过路径覆盖进入正式运行。

## 12. 后续实验自动管理

- 新实验生成器必须通过共享 API 登记 `reproducibility_required=true` 的 AI 资产。
- 登记器将这些文件复制到 `research/ai_assets/...`，生成 SHA256/manifest 并 `git add`。
- 原始行情、可再生大特征表、图表和缓存保持 ignored；manifest 可以记录其来源摘要，但不把实体提交。
- 生成器返回成功但声明的必需资产缺失时，整个实验发布状态为 blocked。
- 旧生成器按使用频率逐步接入，不通过一次性扫描迁移全部历史输出。

## 13. 失败处理与安全边界

- 发布目录不可覆盖；release ID 已存在即失败。
- 在最终原子重命名前失败，只删除本次创建且路径已验证的临时目录，不删除既有资产。
- copy 前后源文件大小/mtime/SHA256 漂移即失败。
- worktree、index 或 submodule 身份不清晰时失败，不自动 stash/reset。
- Git LFS remote 未验证时，大文件发布失败。
- manifest、inventory、checksums 或 payload 任一不一致时失败。
- qualification 过期、blocked、source commit 不一致或 current pointer 指向不存在 commit 时禁止激活。
- Skill 不读取、打印或提交凭据；命中 denylist 的路径直接阻断并只报告路径类别。
- 所有发布命令保证订单 API 调用计数为零，不连接 CTP。

## 14. 测试策略

实现遵循测试先行。核心自动化测试包括：

1. canonical manifest 和稳定 tree fingerprint。
2. material version 单调分配、重复 release ID 拒绝。
3. import/config/explicit artifact 四层发现及未解析依赖阻断。
4. ignored/untracked 正式资产阻断。
5. secret、repo 外路径、符号链接和路径穿越阻断。
6. copy 期间源字节漂移阻断和临时目录原子性。
7. 普通 Git/LFS 分类与 `.gitattributes` 稳定排序。
8. staged path 白名单和限定路径 commit。
9. release commit 与 activation commit 分离。
10. payload 被篡改、LFS pointer 未展开、CURRENT 指针错误时验证失败。
11. Stage935 成功后登记、失败时不发布、定时任务不静默 commit。
12. 实验登记只接收声明为决策/复现资产的文件。
13. 临时本地 Git 仓库 clone smoke：新 clone 能解析 active release 并通过全量 SHA256。
14. 正式运行解析器保证不再读取 ignored AI eligibility。

Skill 另做行为测试：先让独立 agent 在没有 Skill 时处理“正式 AI 池月更后立即覆盖并提交”的压力场景，记录其是否漏掉依赖、混入缓存、静默 commit/push 或绕过资格；再加载 Skill 重跑相同场景，确认其调用确定性发布器并遵守两阶段门禁。

本任务不运行策略回测；若实施过程中触发任何回测，必须按仓库规则写 stage 记录并另拉独立 agent 审核结果、数据、逻辑和置信度。

## 15. 迁移顺序

1. 实现发布库、CLI、manifest schema 和单元测试，不改正式运行路径。
2. 实现 repo-local Skill，并完成无 Skill/有 Skill 行为测试。
3. 验证 Git LFS remote；失败则先解决存储能力，不提交大资产。
4. 在干净的正式候选 worktree 中，从现有 Stage179 清单和当前正式 AI 池建立 `m0001`。
5. 完成独立 hash、Stage179 资格和新 clone smoke。
6. 增加正式运行解析器并把 AI eligibility 切到 active release，重新完成正式资格。
7. 创建 activation commit；部署仍走 futures live execution SOP。
8. 接入 Stage935 月更。
9. 接入未来实验登记 API；不批量迁移无消费方的历史缓存。

## 16. 回滚

- release 目录永不修改或删除。
- 物料回滚通过新的 activation commit 把 `CURRENT.json` 指回上一个已资格通过的 release commit。
- 回滚前仍重新验证目标 manifest/payload 和当前 runtime reader capability。
- 不通过复制旧 ignored 文件覆盖当前池，不通过修改历史 manifest 伪造回滚。

## 17. 验收标准

- 当前正式版本的每个策略决策依赖均出现在 active release inventory 中，且实体被 Git 或 Git LFS 管理。
- 正式配置和运行链路不再读取 ignored 目录中的 AI 池或其他决策资产。
- 新 clone 在安装运行依赖并拉取 LFS 后，能够通过 active release 全量 hash 校验和只读启动前门禁。
- 修改、删除或漏拉任一正式物料都会 fail-closed。
- Stage935 新池不会在未经 release commit、资格和 activation commit 时进入正式运行。
- 发布/激活过程不连接 CTP，订单 API 调用计数为零。
- 任何一次发布均能回答：是什么版本、何时生成、由哪个 commit/生成器/参数产生、用了什么数据截止日、包含哪些文件、与上一版差异是什么、由哪些证据批准。

## 18. 调研与判断

- Git LFS 官方机制使用 Git pointer 和独立 LFS 存储保存大文件；已有文件不会仅因安装 LFS 自动迁移，因此必须提交 `.gitattributes` 并做 clone 验证：<https://git-lfs.com/>。
- Git attributes 是仓库版本化的路径属性机制，适合把确定路径绑定到 LFS filter：<https://git-scm.com/docs/gitattributes>。
- SLSA provenance 强调记录产物由什么输入、构建过程和身份产生；本设计借鉴其来源字段，但不宣称达到某个 SLSA level：<https://slsa.dev/spec/v1.0/provenance>。
- 判断：采用完整快照而不是仅 manifest，能最直接满足跨电脑复现；采用显式登记而不是文件名扫描，能控制仓库体积并避免把缓存误当成策略资产；采用发布/激活双提交，能避免未资格的新 AI 池静默进入正式运行。

## 19. 过拟合与继续价值

- 过拟合判断：否。设计没有读取收益结果反向改变参数，只冻结已经被正式流程消费的物料和来源证据。
- 继续价值判断：是。当前真实缺口是正式 AI 池实体未被 Git 管理，且历史复现已经因旧池字节缺失出现困难；物料治理能从根源上减少该类风险。
