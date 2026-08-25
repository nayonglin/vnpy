# 正式策略物料合同

## 目录

```text
official_strategy_materials/
├── CURRENT.json
└── <strategy_version>/
    ├── index.json
    └── releases/<release_id>/
        ├── manifest.json
        ├── inventory.csv
        ├── checksums.sha256
        ├── RELEASE.md
        └── payload/<logical_path>
```

`release_id` 为 `<material_version>_<created_at_cst>_<source_commit前12位>`；`material_version` 使用单调 `m0001` 格式。历史 release 不修改、不覆盖、不删除。

## Manifest 必填身份

- schema、release ID、strategy/material/parent version
- source commit、UTC/CST 创建时间、研究线、资金口径
- provenance：generator、数据截止日、eval date、training label cutoff、Stage179 manifest 或 publication request 摘要
- qualification：状态与 evidence IDs
- added/changed/deleted 清单
- order/cancel API 零计数
- 文件 inventory、tree fingerprint、manifest SHA256

每个文件行必须有：

- `logical_path`：跨电脑稳定的逻辑名
- `payload_path`：release 内 `payload/` 相对路径
- `role`：`runtime_code`、`strategy_config`、`decision_asset`、`model_artifact`、`feature_contract`、`qualification_evidence` 或 `operational_config`
- `storage`：`git` 或 `git_lfs`
- `size_bytes`、`sha256`、`source_path`

## AI 生成器协议

每次实验或月更必须显式登记：文件路径、逻辑名、角色、是否为复现必需、feature schema version。Stage935 正式候选固定登记五项：latest pool、live eligibility、combined eligibility、summary、report。

原始行情、数据库、临时特征缓存和图表默认不保存实体。若某文件实际影响决策或无法廉价、确定性重建，必须改为复现必需资产。

## Git LFS

超过 10 MiB 或扩展名为 `.parquet/.pkl/.pickle/.joblib/.pt/.pth/.onnx` 的文件使用 Git LFS。发布前同时证明本地 filter 和远端上传能力；无法证明即阻断，不允许静默回退普通 Git。

## 提交边界

- Git 管理的脚本必须保留来源 executable bit；冻结、晋升和 fresh clone 三处均需校验。发布器只归一化为 `0755`（来源可执行）或 `0644`（来源不可执行），不得依赖本机事后 `chmod`。
- fresh clone 的 Python、行情目录、`.vntrader` 数据库和本地 env 属于运行依赖，可在资格前从受信本机路径链接/复制，但不得被 `git add` 或写入物料。

- Prepare：release 目录、strategy index、必要 attributes。
- Release commit：`release(materials): <release_id>`。
- Activation commit：只含 `CURRENT.json`，`activate(materials): <release_id>`。
- Candidate master publication：`publish-master` 从最新远端 master 创建只含 `official_strategy_materials/` release/index 的 `publish(materials): <release_id>` 快进提交并直接 push；不新增或修改 `CURRENT.json`，不发布顶层源码，不创建 PR、不 force-push。
- Formal master promotion：资格与 activation 都通过后，`promote-master` 将 inventory 允许的顶层正式源码、不可变物料根、活动 `CURRENT.json` 和显式治理路径组装为 `promote(official): <release_id>`，非强制快进 push。提交必须保留 activation/release 可达历史并通过 fresh clone 身份审计。
- Production install：只在完整正式晋升模式中，按 live SOP 用 Stage948 从已读取回的远端 master SHA 安装；不连接 CTP、不调用订单 API，安装审计必须为 order/send/cancel `0/0/0`。

## 活动身份

`CURRENT.json` schema-v1 的既有字段继续可读；新 activation 必须额外写入：

- `ruleset_version`：从 release payload 内 `qmt_roll_official_live_config.py` 的唯一字面量 `OFFICIAL_LIVE_RULESET_VERSION` 解析。
- `source_commit`：与 manifest 的 `source_commit` 完全一致。

正式闭环必须同时给出并校验 `strategy_version`、`ruleset_version`、`source_commit`、`material_release_id`、`remote_master_sha`、`production_source_commit`。策略名相同但 ruleset 不同视为不同正式基线。
