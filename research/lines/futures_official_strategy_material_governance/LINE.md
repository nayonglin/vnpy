# futures_official_strategy_material_governance - 正式策略物料治理线

## 定位

- 资产：商品期货正式策略的代码、配置、AI 决策资产、资格证据与发布清单。
- 当前正式策略：从 `examples/portfolio_backtesting/qmt_roll_official_live_config.py` 动态解析；建立本线时为 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- 目标：让任一正式版本使用的全部策略物料进入 Git 或 Git LFS，并固化为可校验、可回滚、可从新 clone 恢复的不可变版本目录。
- 边界：不管理 Python/vn.py/CTP 等运行依赖，不保存密码和本地环境文件，不把原始行情、运行日志、订单账本或临时缓存当作策略物料。
- 关系：复用 Stage179 发布清单与 Stage935 月度 AI 池流程，但不改变策略 alpha、资金参数或下单纪律。

## 核心原则

1. 正式运行不得依赖只存在于 ignored 输出目录中的决策资产。
2. 正式物料发布和正式版本激活分为两个 Git 提交；只有完成资格校验的不可变快照才能被 `CURRENT.json` 激活。
3. 物料发现采用“显式声明为主、静态依赖发现补漏、未解析依赖 fail-closed”，不按文件名中是否包含 `ai` 粗暴收集。
4. 每个文件记录用途、逻辑来源路径、SHA256、大小和存储方式；整体记录版本号、时间、来源 commit、数据截止日与资格证据。
5. 自动化可以生成、复制、校验、`git add`，并在显式确认后创建限定路径的 commit；不自动 push。
6. 已发布目录不可原地修改；回滚只切换激活指针，不覆盖历史版本。

## 当前状态

- 2026-08-19：用户确认采用“完整不可变快照 + Skill + 确定性发布器”方案。
- 现有 Stage179 schema v2 发布清单能绑定关键代码文件，但当前正式 AI eligibility 仍来自 ignored `backtest_outputs/`，没有形成可随 clone 获取的物料快照。
- 当前仓库没有 `.gitattributes`，本机虽安装 Git LFS，但远端 LFS 上传/下载能力尚未完成发布前验证。
- 设计文档：`docs/superpowers/specs/2026-08-19-official-strategy-material-freeze-design.md`。

## 反过拟合判断

- 否。本线只治理资产身份、时序、版本和发布流程，不依据回测收益调整策略参数或筛选品种。

## 继续价值判断

- 有价值。它直接消除“本机能运行、其他电脑 clone 后缺正式 AI 池或派生产物”的隐性风险，并为月更、回滚和审计提供统一事实源。

## 下一步

1. 用户审阅并批准设计文档。
2. 按设计编写实施计划，先完成发布器与门禁测试，再创建 repo-local Skill。
3. 在干净的正式候选 worktree 中固化当前正式版本 `m0001`，完成 clone/校验演练后再激活。
4. 把 Stage935 月更和后续实验的决策性 AI 产物接入统一登记协议。
