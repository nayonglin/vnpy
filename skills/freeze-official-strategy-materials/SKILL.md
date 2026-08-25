---
name: freeze-official-strategy-materials
description: Use when freezing or publishing candidate official vn.py materials, promoting a qualified strategy as the complete formal version to remote master and production, restoring an official release, publishing a Stage935 monthly AI pool, or registering decision-relevant AI experiment artifacts for reproducibility.
---

# 保存正式策略物料

## 核心原则

正式策略必须由一个不可变、可校验、资格通过的物料 release 定义，并以 `CURRENT.json` 作为唯一活动指针。`strategy_version` 相同不代表规则相同；每次都必须解析并核对 `OFFICIAL_LIVE_RULESET_VERSION`。任何源码、规则集、物料、远端 master、生产安装或资格身份不完整时 fail closed。

**REQUIRED SUB-SKILL:** 涉及正式版本晋升、生产安装、Stage935 或月度 AI 池时，先使用 `futures-live-execution-sop`。

## 开始前

1. 读取 `work-type.txt`、`research/registry.md`、当前研究线、正式配置和 `official_strategy_materials/CURRENT.json`。
2. 使用 `qmt_roll_official_baseline_identity.py` 解析当前 `strategy_version`、`ruleset_version`、`source_commit`、`material_release_id`、release commit 和 manifest SHA；不得硬编码 Stage78/Stage372 等历史名字。
3. 检查来源 worktree、稳定生产 worktree、HEAD、clean 状态、远端 master 和运行绑定；不得覆盖用户的脏改动。
4. 明确本次是“候选物料发布”还是“正式版本晋升”。用户说“晋升正式版、合入 master、安装实盘、以后从 master 基于它研究”等，必须选择正式版本晋升；不得用候选发布冒充完成。
5. 明确说明是否过拟合、是否仍有继续价值。发布治理本身不改变 alpha，但不能抹掉候选的历史选择风险。

## 两种正向工作流

| 模式 | 适用请求 | 完成边界 |
| --- | --- | --- |
| 候选物料发布 | 保存候选快照、发布 AI 池、尚未授权正式晋升 | `prepare → commit → verify → publish-master`；只发布不可变 release/index，不更新远端 `CURRENT.json`、顶层正式源码或生产 |
| 正式版本晋升 | 明确要求成为正式版、合入 master 并安装实盘 | 资格通过 → release/activate → `promote-master` → fresh clone 审计 → Stage948 安装 → 最终闭环审计 |

## 共同冻结步骤

1. 只在独立、干净、候选代码绑定正确的来源 worktree 工作；稳定生产 worktree 只允许生成私有 publication request。
2. publication request 必须包含角色、来源 commit、数据截止日、eval date、训练标签截止日和所有决策相关 AI 文件。
3. 运行发布器 `prepare`；由发布器完成依赖闭包、复制、SHA256、manifest、inventory、checksums、版本分配和精确暂存。
4. 运行 `verify`，检查 `git diff --cached --name-only`；只允许本次 release、对应 `index.json` 和必要 `.gitattributes`。
5. 用户明确授权提交后，使用发布器输出的精确确认文本执行 `commit`。不得手写或猜测确认文本绕过门禁。
6. 用 `git clone --no-local` 校验 release commit；Git LFS 文件必须是实际内容，不能是 pointer；所有运行入口的 Git 可执行位必须与来源一致，并至少对 supervisor/launcher 运行 `test -x`。
7. 运行资格时显式绑定 release ID、release commit、证据 ID，并要求 order/send/cancel API 计数均为零。资格失败时保留候选，不激活、不晋升。

## 候选物料发布

1. 执行 `publish-master`。它从最新远端 master 创建 detached worktree，只合并 `official_strategy_materials/` 的不可变 release/index，提交 `publish(materials): <release_id>` 并非强制快进推送，不创建 PR。
2. `publish-master` 不新增或修改远端 `CURRENT.json`，也不发布顶层正式源码或生产绑定。
3. 报告必须明确写“候选物料已发布，尚未成为远端活动正式版，尚未安装生产”；禁止声称后续从 master 切分支一定基于该候选。

## 正式版本晋升

1. 资格通过后执行 `activate`，产生仅更新本地 `CURRENT.json` 的 `activate(materials): <release_id>` 提交。新的 `CURRENT.json` 必须显式记录 `ruleset_version` 和 manifest `source_commit`。
2. 使用完整确认文本执行 `promote-master`，同时传入 release commit、activation commit、qualification JSON 和需要同步的治理路径。
3. `promote-master` 只从物料 inventory 复制允许的 `examples/portfolio_backtesting/`、`tests/`、`skills/` 顶层正式文件，合并不可变物料根和活动 `CURRENT.json`，并复制显式治理路径；禁止绝对路径、`..`、symlink、未登记源码和并发漂移。
4. 在目标 detached master worktree 中先运行 `assert_official_checkout_matches_active_material()`；再创建 `promote(official): <release_id>` 提交，非强制快进推送并独立读取远端 SHA。远端在 fetch/push 间变化立即阻断。
5. 对远端 master 做 fresh clone，运行 `audit_qmt_roll_official_promotion_closure.py` 的 Git/身份部分；必须证明 master 顶层正式源码、活动物料和规则集一致，ahead/behind 为 `0/0`。执行测试前只补本机运行依赖：`.py311`、`backtest_outputs`、`.vntrader/database.db` 等已有运行态链接和权限为 `0600` 的本地 env；它们不得进入 Git，补齐后 `git status` 仍须干净。
6. 按 `futures-live-execution-sop` 和 Stage948 从已验证的远端 master SHA 安装生产。不得连接 CTP；安装/激活审计中的 order/send/cancel API 必须为 `0/0/0`，7 个 launchd 必须精确绑定稳定生产目录，冲突为 0。
7. 运行最终闭环审计。审计器必须按生产 qualification schema 读取并校验 `selected_suite_aggregate`、`formal_ctp_readonly`、`review` 三个引用证据的相对路径与 SHA256；测试汇总必须通过且零失败，正式 CTP 只读证据必须 qualified 且 order/send/cancel 为 `0/0/0`，独立评审 P0/P1/P2 必须为 `0/0/0`。只有远端 master、生产 Git HEAD、生产 active material、release manifest、qualification、activation receipt、activation audit 和 7 个 plist 全部一致，才可报告完成。
8. 最终必须同时报告六个身份字段：`strategy_version`、`ruleset_version`、`source_commit`、`material_release_id`、`remote_master_sha`、`production_source_commit`。缺一项不能声称“以后基于实盘版本”已唯一指向新正式版。

## AI 资产登记

生成器必须显式声明每个产物：

- `decision_asset`、`model_artifact`、`feature_contract`、`qualification_evidence`：影响决策或复现，必须保存。
- `cache_or_visualization`：可再生缓存或展示产物，不复制实体。

不得靠文件名猜重要性。实验登记器只复制 `reproducibility_required=true` 的文件，只执行精确 `git add`，不自动 commit/push；晋升时它们必须进入正式 release inventory。

详细字段与目录协议见 [material-contract.md](references/material-contract.md)。

## 硬性停止条件

- 发现密码、token、`.env`、账户状态或其他秘密。
- 正式代码/config 未跟踪、依赖指向仓库外、payload 或治理路径是 symlink。
- LFS filter、目标远端上传或 fresh clone 下载未证明。
- publication request 源文件漂移、来源树不干净、release 已存在或物料版本冲突。
- payload、inventory、checksums、manifest 任一哈希不一致。
- release payload 或 fresh clone 中任一声明的可执行入口丢失 Git 可执行位。
- `strategy_version` 相同但 `ruleset_version`、顶层 config 或 payload 不同。
- bootstrap pointer 被用于生产资格。
- 资格未通过、证据为空、release commit 不匹配或任一订单 API 计数非零。
- 远端 master 并发变化、非快进、readback 不一致、fresh clone 不一致。
- 生产 source/material/ruleset/receipt/plist 任一不匹配，或 launchd 不足 7 个、存在冲突。

## 禁止事项

- 不在稳定生产 worktree 中 Git 发布、commit、push 或 activate。
- 不创建 PR、不 force-push、不 stash/reset 用户改动。
- 候选模式不得推顶层源码、远端 `CURRENT.json` 或生产；正式晋升只能走受控 `promote-master`，不得手工拼装提交。
- 不连接 CTP，不调用订单 API，不因安装授权绕过每日数据、账户、持仓或交易时段闸门。
- 不把运行环境、数据库、原始行情、缓存和秘密塞进 Git。
- 不覆盖历史 release；任何字节变化都新建 material version，回滚用新的 activation commit 指回已资格版本。
- 不从 ignored `backtest_outputs` 直接运行正式策略。

## 交付报告

候选模式报告 release/material/manifest/clone/远端发布信息，并显式说明未激活、未安装。正式晋升模式必须报告六个身份字段，以及 release/activation commit、CST/UTC 时间、远端推送前后与 readback、ahead/behind、文件数、manifest/tree fingerprint、AI cutoff、资格证据、fresh clone、Stage948 安装、7/7 launchd、冲突数、order/send/cancel `0/0/0`、当前 fail-closed 运行闸状态，并给出结束时的过拟合与继续价值判断。
