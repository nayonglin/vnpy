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
5. 自动化可以生成、复制、校验、`git add`，并在显式确认后创建限定路径的 commit；物料 release 经第二次精确确认后可不走 PR、仅以 fast-forward 方式直推 `origin/master`，禁止 force push，且必须回读远端 head。
6. 已发布目录不可原地修改；回滚只切换激活指针，不覆盖历史版本。

## 当前状态

- 2026-08-20 Stage002：已实现并真实执行“正式物料产物目录无 PR 直推 master”；`origin/master` 从 `c758edbc4e8f589eeb75f3a3b75a3fa5a1b447bc` 前进到 `cba6d2f5fe7a20bf36848b94a19b9a885ef72ac1`。
- 最新候选为 `m0004_20260820T141305+0800_f06a2885df5c`，包含 `148` 个文件；manifest SHA256 为 `ffc7309508722db684de31196b62e2f21e18914e6d95d56851440ca4dd09d7a0`，tree fingerprint 为 `1b82013e863414359bfa531af80c4e8671d037af5ef1eb89d46741f094e8eccb`。
- 远端发布提交的 `607` 个变更路径全部位于 `official_strategy_materials/`；远端 detached worktree 重算校验通过，index 包含 `m0001` 至 `m0004`。
- 最终 Stage179 必需测试为 `879 passed, 694 subtests`；独立复审未发现剩余 Critical/Important。
- 远端 `master` 不包含 `CURRENT.json`，所以 `m0004` 仍是 `candidate`，尚未执行正式 Stage179 资格、激活或部署；本地历史 bootstrap 指针也没有随发布进入远端。
- 当前 AI 资产体积可由普通 Git 管理；仓库没有已证明可用的远端 LFS 链路，未来大于 `10 MiB` 或模型/二进制资产会 fail-closed。
- 设计文档：`docs/superpowers/specs/2026-08-19-official-strategy-material-freeze-design.md`。
- 最新阶段：`stages/20260820_1416_stage002_direct_master_material_publish.md`。

## 反过拟合判断

- 否。本线只治理资产身份、时序、版本和发布流程，不依据回测收益调整策略参数或筛选品种。

## 继续价值判断

- 有价值。它直接消除“本机能运行、其他电脑 clone 后缺正式 AI 池或派生产物”的隐性风险，并为月更、回滚和审计提供统一事实源。

## 下一步

1. 后续 Stage935 月更和实验 AI 资产晋级时，先统一登记，再生成新 material release 并运行受控 `publish-master` 直推物料目录。
2. 任何 Git LFS 资产在目标远端的上传、pointer 和重新下载能力被证明前继续 fail-closed。
3. 如需让 `m0004` 或后续 release 成为正式运行版本，单独完成 Stage179 资格和 activation/CURRENT 发布，不允许物料直推隐式激活。
4. 持续回归限定路径、remote head CAS、索引引用完整性、不可变目录和远端 readback。
