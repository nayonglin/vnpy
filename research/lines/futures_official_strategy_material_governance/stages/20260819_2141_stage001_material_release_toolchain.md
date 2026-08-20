# Stage001：正式策略物料固化与 AI 资产自动登记

- 改动时间：2026-08-19 21:41 CST
- 是否重要突破版本：是（正式策略物料治理里程碑，不是 alpha 突破）
- 研究线：`futures_official_strategy_material_governance`
- 正式策略：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 资金口径：C9 / 15 万

## 本阶段结论

已实现“完整不可变快照 + 两阶段 Git 发布/激活 + repo-local Skill + AI 资产登记协议”。正式策略的代码、配置、AI 决策资产、特征契约和必要资格物料可固化到 `official_strategy_materials/`，逐文件记录 SHA256，并通过 `CURRENT.json` 单独激活。

最终候选为：

- 物料版本：`m0003`
- release ID：`m0003_20260819T213850+0800_709f7dce1c9f`
- 来源 commit：`709f7dce1c9fafd5d62810d33637c718649c3b1b`
- release commit：`e15f33e1118f1a4dbc18dfd709f15329a7afb1c3`
- 创建时间：`2026-08-19T13:38:50.151819Z` / `2026-08-19T21:38:50+08:00`
- 文件数：`148`
- manifest SHA256：`6770cf12782173940f5cbfd14c7ec6033b5842232a2910f19a882c598b1b32a5`
- tree fingerprint：`731099259b3b2adb1d5aa60a1757aedfaff0efffe84a1de930c19ad40d5da8a2`
- AI publication request SHA256：`24ca99879a238ead7dfe9d3b22aecbaa991f67b5e85249f39492bbea7c664fdf`
- Stage179 manifest SHA256：`7b374eaea60f8ab36fff987ffd15b3c90249f0e1a3c2dc9b0beeb579ece24e3b`
- AI 评估日：`2026-07-31`
- 数据截止日：`2026-08-03`
- 训练标签截止日：`2026-05-07`
- 资格状态：`candidate`
- 下单 API 调用：`0`
- 撤单 API 调用：`0`

`CURRENT.json` 暂时仍指向 `m0001`，激活模式是 `bootstrap_non_deployable`。这是有意的 fail-closed 状态：它可用于离线导入和迁移验证，但 Stage179 正式生产资格会拒绝它。`m0003` 尚未伪装成正式已激活版本，因为本阶段没有连接 CTP，也没有完成正式只读账户/持仓资格捕获。

## 改动摘要

### 新增

- 确定性物料 manifest、SHA256、tree fingerprint 和不可变目录校验。
- 正式物料依赖发现：显式声明、Python import 闭包、Stage179 关键文件和 AI publication request 合并；未解析依赖 fail-closed。
- `prepare`、`verify`、`commit`、`activate` 发布器，限定路径 `git add`，不自动 push。
- 正式运行 resolver：从 `CURRENT.json` 解析 AI eligibility，并校验运行代码/config 与快照字节一致。
- AI 资产登记器：实验产物自动复制到 `research/ai_assets/<line>/<stage>/<run>/` 并精确 `git add`；正式候选由 Stage935 生成 publication request。
- `skills/freeze-official-strategy-materials/`，封装保存、校验、提交和激活边界。
- clone smoke、manifest/discovery/registry/resolver/Stage935/Stage179 回归测试。

### 修改

- Stage935 成功发布后生成五类 AI 资产的 publication request，但仍以 ignored 输出目录作为候选 staging，不直接覆盖正式快照。
- Stage179 将物料 release ID、manifest digest 和新模块纳入正式关键闭包；生产模式拒绝 bootstrap release。
- 轻量上下文与正式配置改为从激活物料解析 AI eligibility，不再回退到 `backtest_outputs/`。

### 删除

- 未删除策略参数、AI 排名逻辑、正式品种池或实盘执行规则。

## 参数变化

### 新增参数/协议字段

- `schema_version=1`
- `material_version`、`release_id`、`source_commit`、`release_commit`
- `created_at_utc`、`created_at_cst`
- `manifest_sha256`、`tree_fingerprint`
- `material_release_id`、`material_release_commit`
- `data_cutoff`、`eval_date`、`training_label_cutoff`
- `qualification.status/evidence_ids`
- Git LFS 门槛：大于 `10 MiB` 或模型/二进制扩展名必须先通过 LFS/remote 能力门禁
- 激活模式：`bootstrap_non_deployable` 与正式资格激活分离

### 修改参数

- 无策略 alpha、风险倍率、资金、品种或执行参数修改。

### 删除参数

- 无。

## 验证结果

- 候选工作树完整必需测试：在 `PYTHONPATH` 绑定当前 worktree 且先校验 `vnpy.__file__` 位于候选目录后，`872 passed, 694 subtests`。
- 一次未绑定候选根目录的验证曾得到 `1 failed, 871 passed`；取证显示共享 `.py311` 的 editable 安装把 `vnpy` 导入主 checkout，并使枚举值从中文变成 `Short/Close`。绑定候选路径后原失败用例 `1 passed`，完整门禁也通过；该失败不归因于 m0003 代码，但证明候选运行时路径门禁不能省略。
- m0003 clone 后物料校验：通过，`148` 个文件全部重算成功。
- m0003 clone 后 resolver/config/Stage179 聚焦测试：`45 passed, 39 subtests`。
- Skill frontmatter：Ruby YAML 解析通过；系统、仓库和 bundled Python 均缺少 `PyYAML`，因此官方 `quick_validate.py` 未能执行。
- 未 push、未部署、未连接 CTP、未调用下单/撤单 API。

## 回测结果

本阶段没有运行回测，也没有改变策略逻辑，因此不存在新增、修改或删除的回测结果。以下指标均为“不适用”，不能沿用历史结果冒充本阶段结果：

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用

## 反过拟合判断

- 是否过拟合：否。
- 原因：本阶段只约束物料身份、依赖闭包、时序、哈希、资格和发布边界，没有依据收益曲线筛参数、日期、品种或模型阈值。

## 继续价值判断

- 是否还有价值继续：是。
- 原因：代码层和 clone 物料完整性已经闭环，但正式启用仍需在明确授权下完成 Stage179 可信资格、激活提交和远端推送/clone 验证；这是从“候选可复现”到“正式可运行”的必要最后一段。

## 后续规划与 TODO

1. 在用户明确授权后，按正式实盘 SOP 对 `m0003` 做 Stage179 只读资格捕获；任何门禁失败继续 fail-closed。
2. 资格通过后单独创建 `activate(materials)` 提交，把 `CURRENT.json` 从 bootstrap 切换到 `m0003`。
3. 用户确认远端后再 push，并从远端新 clone 做一次完整物料/LFS 校验；当前小型 AI 资产走普通 Git，大文件在 LFS remote 未证明前必须阻断。
4. 后续 Stage935 月更和实验生成器继续走 AI 资产登记协议，禁止正式配置直接引用 ignored 输出。
