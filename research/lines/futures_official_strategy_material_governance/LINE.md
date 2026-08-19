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

- 2026-08-19 Stage001：已实现“完整不可变快照 + Skill + 确定性发布器 + AI 资产登记协议”。
- 最终候选为 `m0003_20260819T213850+0800_709f7dce1c9f`，包含 `148` 个文件；manifest SHA256 为 `6770cf12782173940f5cbfd14c7ec6033b5842232a2910f19a882c598b1b32a5`，tree fingerprint 为 `731099259b3b2adb1d5aa60a1757aedfaff0efffe84a1de930c19ad40d5da8a2`。
- 候选工作树必需测试为 `872 passed, 694 subtests`；新 clone 后物料校验通过，resolver/config/Stage179 聚焦测试为 `45 passed, 39 subtests`。
- `CURRENT.json` 仍指向 `m0001` 的 `bootstrap_non_deployable` 激活；`m0003` 保持 `candidate`，尚未执行正式 Stage179 资格、激活、push 或部署。
- 当前 AI 资产体积可由普通 Git 管理；仓库没有已证明可用的远端 LFS 链路，未来大于 `10 MiB` 或模型/二进制资产会 fail-closed。
- 设计文档：`docs/superpowers/specs/2026-08-19-official-strategy-material-freeze-design.md`。
- 最新阶段：`stages/20260819_2141_stage001_material_release_toolchain.md`。

## 反过拟合判断

- 否。本线只治理资产身份、时序、版本和发布流程，不依据回测收益调整策略参数或筛选品种。

## 继续价值判断

- 有价值。它直接消除“本机能运行、其他电脑 clone 后缺正式 AI 池或派生产物”的隐性风险，并为月更、回滚和审计提供统一事实源。

## 下一步

1. 在用户明确授权后，按正式实盘 SOP 对 `m0003` 做 Stage179 只读资格捕获。
2. 资格通过后创建独立 activation commit，将 `CURRENT.json` 切换到 `m0003`。
3. 用户确认远端后再 push，并从远端新 clone 做完整物料/LFS 校验。
4. 后续 Stage935 月更和实验生成器持续通过统一登记协议发布决策/复现资产。
