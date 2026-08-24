# 正式版本晋升闭环 Skill 设计

- 状态：待用户审阅
- 日期：2026-08-25
- 研究线：`futures_trend_rollover_shape_same_volume`
- 当前正式策略：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 当前正式 ruleset：`stage021_q_rollover_volume_atr_v1`
- 设计范围：正式源码、物料、master、研究基线、生产安装和最终身份审计

## 1. 背景

现有正式物料发布器已经能够生成不可变 release、计算 SHA256、维护 `index.json`、直接非强制推送远端 `master`，并在独立 activation commit 中更新 `CURRENT.json`。但“发布物料”“激活物料”“把正式源码纳入 master”“更新研究默认基线”“安装生产”仍是分开的人工步骤。

Stage021-Q 晋升暴露了三个实际缺口：

1. 远端 `master` 已包含 `m0009` release 和 index，但顶层可编辑策略源码仍是晋升前版本。
2. 远端 `master` 的 `CURRENT.json` 仍指向 `m0001`；resolver 从新 clone 会解析到旧物料。
3. `version-ab-experiment`、实盘 SOP 和 registry 仍存在 Stage78、Stage372 或旧研究线默认值。

因此，“物料已经推到 master”不能再作为“正式版本已完整保存”的完成条件。

## 2. 目标与非目标

### 2.1 目标

- 新增一个可自动发现的 repo-local Skill，处理“保存正式版、晋升正式、推 master、安装实盘”等请求。
- 每次晋升将正式源码、正式物料、激活指针、研究基线和生产安装绑定为同一套身份。
- 从远端 `master` 新 clone 后，顶层源码和 resolver 均指向当前正式 ruleset，可直接作为后续研究分支的基线。
- 只有远端与生产最终审计全部通过时，才允许报告“正式版本已保存并安装”。
- 保留直接合入并推送 `master` 的既定授权模式，不引入人工 PR。

### 2.2 非目标

- 不提交 Python、vn.py、CTP framework、数据库、行情、密码、token、设备指纹或运行日志。
- 不重写 Stage78、Stage372 等明确命名的历史回测入口；它们继续作为冻结对照。
- 不在 Skill 内重新实现策略回测、物料哈希或生产执行逻辑。
- 不因本设计修改 Q 的任何策略参数、资金参数或订单规则。

## 3. 方案选择

### 3.1 采用：薄 Skill + 确定性发布器扩展 + 独立闭环审计

Skill 负责授权边界、顺序、停止条件和汇报；仓库脚本负责可测试的 Git、manifest、resolver 和身份校验。现有发布器扩展一个正式晋升路径，独立审计器对远端 clone 与生产目录做最终只读检查。

该方案复用现有实现，同时把容易遗漏的项目变成结构化必填合同。

### 3.2 不采用：只修改 Skill 文案

纯文档提醒无法阻止发布器继续只推 release/index，也不能验证远端 `CURRENT.json`、顶层源码和生产身份。

### 3.3 不采用：重写为单个大型部署程序

把资格、Git 发布、生产安装和 launchd 全部合并为一个新程序，改动面和回滚风险过大。保留现有组件，通过清晰的阶段收口更容易审计。

## 4. 权威身份合同

一次正式晋升必须同时记录并验证以下六项：

| 字段 | 含义 |
| --- | --- |
| `strategy_version` | 正式策略家族标识 |
| `ruleset_version` | 区分同一策略名下的实际规则，例如 Stage021-Q |
| `source_commit` | 被资格验证的候选源码提交 |
| `material_release_id` | 不可变正式物料 release |
| `remote_master_sha` | 包含顶层源码、物料和激活指针的远端 master 提交 |
| `production_source_commit` | 生产稳定目录和 release manifest 绑定的源码提交 |

`strategy_version` 单独相同不代表规则相同。任意消费者声称“当前正式版”时，至少同时校验 `strategy_version + ruleset_version + material_release_id`。

## 5. 组件

### 5.1 Repo-local Skill

新增 `skills/futures-official-version-promotion/`：

- `SKILL.md`：触发条件、授权边界、阶段顺序、停止条件和最终报告合同。
- `agents/openai.yaml`：保持自动发现；默认提示只描述正式晋升目标，不暗示跳过用户授权。
- Skill 强制先使用 `futures-live-execution-sop`；候选来自策略研究时同时使用 `version-ab-experiment`。

### 5.2 发布器扩展

扩展 `build_qmt_roll_official_strategy_material_release.py` 的 master 发布合同：

- 普通 `publish-master` 继续只发布不可变 release/index，用于“已发布但未激活”的候选物料。
- 新增正式晋升动作，要求显式正式晋升授权和已通过资格证据。
- 正式晋升动作在干净的远端 master 临时工作树中同时写入：
  - 资格通过的顶层正式源码；
  - release、index 和激活后的 `CURRENT.json`；
  - 当前研究线记录、registry 和正式晋升摘要；
  - 会决定后续默认基线的 repo-local Skill。
- 只允许非强制快进推送；远端在准备和推送之间变化时失败并重新规划，不覆盖他人提交。

顶层源码集合由正式 release inventory 的受控类别决定，不允许把整个候选工作树无差别复制到 master。研究记录和 Skill 使用独立白名单。

### 5.3 闭环审计器

新增只读审计入口，对指定远端和生产目录输出机器可读 JSON。审计必须检查：

- 远端 `master` SHA 与预期一致，ahead/behind 为 `0/0`；
- 新 clone 的 `CURRENT.json` 指向本次 release；
- resolver 成功解析本次 release，manifest/payload 哈希通过；
- master 顶层正式配置与 active payload 的 `strategy_version`、`ruleset_version` 和关键 overrides 一致；
- `version-ab-experiment` 不再静态选 Stage78，而是按正式身份解析 A；
- registry 和当前正式研究线明确记录本次 ruleset；
- 生产 manifest、qualification、activation receipt、稳定目录 HEAD 和 launchd 工作目录一致；
- 发布、审计和安装阶段订单/发单/撤单 API 计数均为零。

审计器不连接 CTP、不更新数据、不安装 launchd，也不修改 Git。

## 6. 晋升数据流

1. **冻结候选**：记录候选 commit、策略版本、ruleset、研究线和用户正式晋升授权。
2. **资格验证**：运行与风险相称的策略、物料、clone 和生产前资格；失败则保留研究版本，不晋升。
3. **生成 release**：prepare、commit、verify，得到不可变 release commit。
4. **准备 master 晋升提交**：从最新远端 master 创建干净临时工作树，写入受控顶层源码、正式物料、`CURRENT.json`、研究记录和默认基线 Skill。
5. **本地 clone 门禁**：在推送前用临时裸 remote/clone 证明 resolver、顶层源码和默认 A 身份正确。
6. **直接推送 master**：非强制快进推送；立即独立执行 `ls-remote`、SHA、ancestry 和 ahead/behind 校验。
7. **安装生产**：只从已验证的远端 master 身份安装到 `vnpy_production_live`，沿用正式实盘 SOP、资格 bundle、activation receipt 和 Stage948 launchd 安装。
8. **最终闭环审计**：重新读取远端和生产，不复用发布过程内存；六项身份全部一致后才完成。

如果 master 已推送但生产安装失败，系统保持 fail-closed，并明确报告“master 已晋升、生产未完成”；不得把部分完成描述成全部完成。任何补偿或回滚必须形成新提交和新 receipt，不改写历史。

## 7. 默认研究基线规则

当用户说“基于实盘版本优化”“基于正式版迭代”或等价表述时：

1. 权威来源首先是 `vnpy_production_live` 的 manifest、activation receipt 和稳定目录配置。
2. 远端 master 必须通过闭环审计并与生产 ruleset 一致。
3. 新研究分支从包含该正式源码的远端 master SHA 切出。
4. A 臂记录六项身份；候选只在其上增量修改。
5. 如果 master 与生产不一致，停止创建实验并报告身份漂移，不能回退到 Stage78、Stage372 或仅凭名称相同的旧 C9。

历史脚本只有在用户明确要求比较对应历史版本时才运行。

## 8. 测试策略

本改动不跑策略回测。测试遵循技能行为和发布代码两层 RED-GREEN：

### 8.1 Skill 行为测试

- 无 Skill 基线：给独立 agent 一个“赶快把候选保存成正式版并推 master”的场景，确认其可能只推物料、漏 `CURRENT.json`、漏顶层源码或继续选 Stage78。
- 有 Skill：相同场景必须先形成六项身份，选择正式晋升动作，并在最终远端/生产审计前拒绝声称完成。

### 8.2 发布器测试

- 保留普通 `publish-master` 只发布候选物料的测试。
- 新增正式晋升动作测试，验证新 clone 同时具备顶层源码、release/index、正确 `CURRENT.json` 和默认基线。
- `CURRENT.json` 旧、顶层 ruleset 旧、payload 不一致、registry/Skill 旧时均失败。
- 远端竞态、非快进、未授权、资格缺失、来源提交不一致时失败。
- 重复执行在身份完全一致时幂等；只要远端身份变化就重新读取并失败。

### 8.3 最终审计测试

- 构造 master 正确但生产旧、生产正确但 master 旧、版本名相同但 ruleset 不同等场景。
- 只有六项身份与零订单 API 证明全部一致时返回成功。

## 9. 迁移与本次 Q 收口

实现完成后，用同一 Skill 对当前 Q 做一次补收口：

- 将 Q 顶层源码和晋升记录合入并推送远端 master；
- 把远端 `CURRENT.json` 从 `m0001` 更新为已激活的 `m0009`；
- 更新 `version-ab-experiment`、实盘 SOP、自动化启动 Skill、registry 和多周期正式基线解析；
- 从远端 master 重新验证或安装生产，使最终生产身份绑定远端 master 中同一套 Q 源码；
- 输出六项身份、冲突数、远端 SHA、生产状态和订单 API 计数。

该迁移不重新选择 Q，不改变用户已有 operator override，也不删除历史反证记录。

## 10. 安全与停止条件

- 不自动 stash、reset、force-push、覆盖脏工作树或删除历史 release。
- 发现用户未授权的远端变更、路径白名单外文件、凭据、LFS 未展开或身份不一致时停止。
- 发布与安装不绕过每日数据、CTP runtime、broker snapshot、账户持仓、kill switch 或 submit authorization gate。
- “用户授权晋升”允许发布与安装正式策略，不等于允许忽略失败资格或强制下单。
- Skill 的完成状态只有两个：`complete` 或明确的 `partial/fail-closed`；没有“基本完成”。

## 11. 验收标准

- 从远端 master 新 clone 后，resolver 得到 `m0009`/后续最新正式 release，而不是旧 `CURRENT.json`。
- master 顶层正式配置、active payload 和生产配置的 ruleset 与关键 overrides 完全一致。
- 新研究分支从远端 master 创建时，默认 A 为当前生产 ruleset。
- 正式晋升记录和 registry 不再把已晋升版本描述为 research-only。
- 最终报告包含六项身份、推送方式、冲突数、ahead/behind、测试结果、生产状态和订单 API 计数。
- 任一验收项缺失时，Skill 不得报告正式晋升完成。

## 12. 调研与判断

- 本设计以当前仓库、远端 Git、正式物料 resolver 和生产 manifest 为权威；外部通用发布资料不能替代这些本地事实，因此本轮无需额外互联网调研。
- 判断：需要优化的不只是提示词，而是“Skill 决策 + 发布器能力 + 最终审计”三者。只修其中一项，仍会再次出现某个表面已经更新、另一个入口仍指向旧版本的问题。

## 13. 过拟合与继续价值

- 过拟合判断：否。本设计只统一版本身份和发布流程，不读取收益结果调整策略参数。
- 继续价值判断：是。它直接消除研究基线漂移、clone 解析旧物料和生产/master 身份分叉，能避免后续实验从错误正式版本起步。
