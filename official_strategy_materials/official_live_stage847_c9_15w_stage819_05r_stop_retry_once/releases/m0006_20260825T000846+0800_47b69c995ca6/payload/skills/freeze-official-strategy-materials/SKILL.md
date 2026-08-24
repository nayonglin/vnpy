---
name: freeze-official-strategy-materials
description: Use when freezing, publishing, validating, activating, or restoring official vn.py strategy materials, when a Stage935 monthly AI pool needs Git publication, or when decision-relevant AI experiment artifacts must be registered for reproducibility.
---

# 保存正式策略物料

## 核心原则

正式策略必须只依赖一个不可变、可校验、已资格通过的 Git/Git LFS 快照。发布提交与激活提交分离；任何哈希、来源或资格不完整时 fail closed。正式物料 release commit 完成后，不走人工 PR，使用受控发布动作只把 `official_strategy_materials/` 直接快进推送到远端 `master`。

**REQUIRED SUB-SKILL:** 涉及正式实盘、Stage935 或月度 AI 池时，先使用 `futures-live-execution-sop`。

## 开始前

1. 读取 `work-type.txt`、`research/registry.md`、当前正式配置和对应研究线。
2. 从 `qmt_roll_official_live_config.py` 解析当前正式版本、资金和 AI 池，不硬编码历史版本。
3. 明确说明：是否过拟合、是否仍有继续价值。
4. 检查稳定生产 worktree、来源 worktree、HEAD、clean 状态和运行依赖绑定。
5. 稳定生产 worktree 只允许生成私有控制目录中的 publication request；不得在那里运行 Git 发布器。

## 选择工作流

| 请求 | 使用入口 | 结果 |
| --- | --- | --- |
| 保存/发布正式策略物料 | `build_qmt_roll_official_strategy_material_release.py prepare` | 不可变候选目录并精确 `git add` |
| Stage935 月更成功 | Stage935 自动写 publication request | 等待干净来源 worktree 消费 |
| 保存实验 AI 决策资产 | `qmt_roll_ai_artifact_registry.register_experiment_artifacts()` | `research/ai_assets/` 快照、manifest、精确 `git add` |
| 校验已有 release | 发布器 `verify` | manifest、inventory、payload 全量 SHA256 |
| 发布产物到远端 master | 发布器 `publish-master` | 仅产物目录的 fast-forward commit 和直接 push，无 PR |
| 激活已资格 release | 发布器 `activate` | 仅更新 `CURRENT.json` 的独立提交 |

## 正式发布流程

1. 在独立、干净、候选代码绑定正确的来源 worktree 工作。
2. publication request 必须包含明确角色、来源 commit、数据截止日、eval date、训练标签截止日和五个 Stage182 文件。
3. 运行 `prepare`；发布器负责依赖闭包、复制、SHA256、manifest、inventory、checksums、版本分配和精确暂存。
4. 运行 `verify`，再检查 `git diff --cached --name-only`。只允许本次 release、对应 `index.json` 和必要的 `.gitattributes`。
5. 只有用户已明确要求提交时，才使用发布器输出的精确确认文本执行 `commit`。不得手写确认文本绕过门禁。
6. 用 `git clone --no-local` 验证 release commit；LFS 文件必须是实际内容，不得是 pointer 文本。
7. 用户要求“保存/发布正式物料”即授权在 release 校验通过后运行 `publish-master`：从最新 `origin/master` 建临时 detached worktree，只合并 `official_strategy_materials/`，创建 `publish(materials)` 提交并用非强制 fast-forward push 直推 master，不创建 PR。
8. 远端 master 在 fetch 与 push 之间变化、staged 路径越界、历史 release/material version 冲突或 readback SHA 不一致时必须阻断；禁止 force-push、禁止合并来源功能分支。
9. 运行 Stage179 资格时必须显式绑定候选 release ID。生产资格失败时保留候选但不激活；发布到 master 不等于生产激活。
10. 只有资格状态、release commit、证据 ID、send/cancel API 零计数均匹配，才允许 `activate`。
11. `publish-master` 永远不新增或修改远端 `CURRENT.json`；激活只暂存本地 `CURRENT.json` 并再次从新 clone 验证。远端激活需要独立的资格绑定发布动作，不能复用 release 发布入口。

## AI 资产登记

生成器必须显式声明每个产物：

- `decision_asset`、`model_artifact`、`feature_contract`、`qualification_evidence`：影响决策或复现，必须保存。
- `cache_or_visualization`：可再生缓存/展示产物，不复制实体。

不得靠扫描文件名猜测重要性。实验登记器只复制 `reproducibility_required=true` 的文件，只执行精确 `git add`，不 commit、不 push。

详细字段和目录协议见 [material-contract.md](references/material-contract.md)。

## 硬性停止条件

- 发现密码、token、`.env`、账户状态或其他秘密。
- 正式代码/config 未跟踪、依赖指向仓库外，或 payload 是 symlink。
- LFS 文件超过阈值或属于模型格式，但本地 filter/远端能力未证明。
- direct-master 发现任一 `git_lfs` 资产；在目标 remote 的上传、pointer 和重新下载闭环未实现前保持阻断。
- publication request 的源文件已漂移。
- release 目录已存在、版本冲突或来源树不干净。
- payload、inventory、checksums、manifest 任一哈希不一致。
- bootstrap pointer 被用于生产资格。
- 资格未通过、证据为空、release commit 不匹配或订单 API 计数非零。

## 禁止事项

- 不在稳定生产 worktree 中 Git 发布、commit、push 或 activate。
- 不 push 来源功能分支、不创建 PR、不 force-push；唯一允许的远端写入是受控 `publish-master` 将产物目录快进直推 `master`。
- 不部署、修改 launchd、连接 CTP 或调用订单 API。
- 不把运行环境、数据库、原始行情、缓存和秘密塞进 Git。
- 不覆盖历史 release；回滚只能用新的 activation commit 指回已资格版本。
- 不从 ignored `backtest_outputs` 直接运行正式策略。

## 交付报告

用中文报告：正式策略版本、物料版本、release ID、CST/UTC 时间、source/release/activation commit、master 发布前后 commit、远端 readback、文件数、manifest SHA256、tree fingerprint、AI eval/source/training cutoff、资格状态、证据 ID、clone 校验、订单 API 零计数、未执行的部署/CTP，以及结束时的过拟合与继续价值判断。
