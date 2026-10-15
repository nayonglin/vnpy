# 仓库随附 Skills

本目录包含原交接包的 10 个 Skill，加上已在本机研究目录找到的 `futures-recap-html`，共 11 个。

## Clone 后如何使用

在 Codex 中打开这个 Git 仓库，或从仓库及其子目录启动 Codex。`.agents/skills/` 中的相对符号链接指向本目录，Codex 会发现这些 Skill，并在任务匹配描述时按需读取；也可用 `$skill-name` 显式指定。发现并不代表每轮全部执行。更新未出现时重新打开项目或重启 Codex。

须先将这些文件提交并推送到所克隆的分支，远端 clone 才能包含它们。Git checkout 需保留符号链接（macOS/Linux 通常默认支持；Windows 需确保 `core.symlinks=true` 且有创建链接权限）。

依据：[OpenAI 官方 Skill 文档](https://learn.chatgpt.com/docs/build-skills)，仓库发现位置是 `.agents/skills/`，支持符号链接。

## 清单

| Skill | 用途 | 来源 |
| --- | --- | --- |
| futures-live-execution-sop | 实盘、CTP/SimNow 执行纪律 | 原仓库 |
| futures-live-automation-startup | 正式启动、身份和调度核验 | 原仓库 |
| freeze-official-strategy-materials | 不可变物料封存与发布 | 原仓库 |
| version-ab-experiment | 策略隔离与 A/B 实验 | 原仓库 |
| futures-multicycle-validation | 多周期稳健性验证 | 原仓库 |
| futures-multicycle-backtest-report | 多周期报告兼容入口 | 原仓库 |
| futures-official-shadow | 绑定生产 receipt 的正式影子盘查询 | 交接包外部 Skill |
| futures-recap-html | 冻结回测的逐笔、多周期 K 线 HTML 复盘 | 本机已恢复的研究参考目录 |
| pdf | PDF 生成、读取和版面校验 | 交接包外部 Skill，可选 |
| playwright | 浏览器页面验证 | 交接包外部 Skill，可选 |
| tushare-data | 股票、基金及宏观数据研究 | 交接包外部 Skill，可选，不是期货运行依赖 |

## 依赖与边界

- Skill 文件完整不代表运行环境已经准备好。Python 3.11、项目依赖、CTP 原生库、历史行情、冻结回测和模型物料需按交接文档恢复；凭证和生产私有状态不随 Git 分发。
- 实盘、启动和正式影子盘 Skill 中的原机生产路径不是当前 clone 的生产授权。正式查询仍需完整且匹配的 release、qualification、activation、daily receipt 和目标日数据证据。
- 影子盘 exporter 保留原脚本。仓库版说明显式传入生产 checkout、私有状态和私有审计输出目录，不能使用旧路径默认值作为本机配置。
- HTML 复盘使用已有 canonical renderer。Stage050 Top30 分钟增强工具未在当前 checkout 或交接源码中找到；对应可选流程未恢复，不能声称其已可运行。输入结果和行情本来也不随普通 clone 自动恢复。
- PDF 需要相应 Python 库和 Poppler；Playwright 需要 Node/npm/npx 及浏览器运行时；Tushare 需要 Python 包、本地 Token 和相应接口权限。本次只迁移 Skill，不触发下载、登录或网络查询。
- 如果另有同名用户/插件 Skill，Codex 不会合并内容；本仓库工作优先使用这里的明确文件路径，并遵循宿主提供的工具限制。

## 维护与来源校验

`HANDOFF_MANIFEST.json` 记录所有 Skill 文件的来源摘要和本次入库摘要。原有 6 个 Skill 中，实盘 SOP 将两处含本地账号标识的 AppID 例子改为 `<broker-confirmed-app-id>`，其余 5 个内容保持不变。新增副本调整 Playwright 路径说明、正式影子盘的路径配置说明，以及 HTML 缺失工具说明；脚本原文保持不变；Playwright wrapper 补上可执行权限（0755）。原交接包与研究参考副本不修改。

迁移后做文件/hash、元数据、链接和 Codex 实际发现检查。本次未执行策略回测、生产查询、发信或下单；这些工作须按具体任务独立验收。
