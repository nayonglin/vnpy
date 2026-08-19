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

- Prepare：release 目录、strategy index、必要 attributes。
- Release commit：`release(materials): <release_id>`。
- Activation commit：只含 `CURRENT.json`，`activate(materials): <release_id>`。
- 所有命令均不 push、不部署、不连接 CTP、不调用订单 API。

