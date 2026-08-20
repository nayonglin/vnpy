# Stage002：正式策略物料无 PR 直推 master

- 改动时间：2026-08-20 14:16 CST
- 是否重要突破版本：是（正式物料发布治理里程碑，不是 alpha 突破）
- 研究线：`futures_official_strategy_material_governance`
- 正式策略：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 资金口径：C9 / 15 万

## 本阶段结论

按用户明确授权，已将正式策略物料发布流程改为“不走人工 PR，产物目录直接 fast-forward 合入并推送 `origin/master`”。本次真实发布成功，远端 `master` 从 `c758edbc4e8f589eeb75f3a3b75a3fa5a1b447bc` 前进到 `cba6d2f5fe7a20bf36848b94a19b9a885ef72ac1`。

这次发布只改变 `official_strategy_materials/`，共 `607` 个路径，目录外变更为 `0`。发布器没有复制、提交或推送 `CURRENT.json`，所以“发布物料”和“激活正式策略”继续严格分离；当前远端物料可复现，但 `m0004` 仍是 `candidate`，没有部署、没有连接 CTP，也没有改变线上正式策略运行状态。

本次发布版本：

- 物料版本：`m0004`
- release ID：`m0004_20260820T141305+0800_f06a2885df5c`
- 来源 commit：`f06a2885df5cdca77c77b08fcee1414e39cfe6f9`
- 本地 release commit：`7dbaff8d42aae8672bea9b8f9259a401434ec209`
- 远端 master 发布 commit：`cba6d2f5fe7a20bf36848b94a19b9a885ef72ac1`
- 远端 master 发布前 commit：`c758edbc4e8f589eeb75f3a3b75a3fa5a1b447bc`
- 创建时间：`2026-08-20T06:13:05.218873Z` / `2026-08-20T14:13:05+08:00`
- 文件数：`148`
- manifest SHA256：`ffc7309508722db684de31196b62e2f21e18914e6d95d56851440ca4dd09d7a0`
- tree fingerprint：`1b82013e863414359bfa531af80c4e8671d037af5ef1eb89d46741f094e8eccb`
- 父物料版本：`m0003`
- 存储方式：普通 Git；本次没有 Git LFS 文件
- AI publication request SHA256：`24ca99879a238ead7dfe9d3b22aecbaa991f67b5e85249f39492bbea7c664fdf`
- Stage179 manifest SHA256：`7b374eaea60f8ab36fff987ffd15b3c90249f0e1a3c2dc9b0beeb579ece24e3b`
- AI 评估日：`2026-07-31`
- 数据截止日：`2026-08-03`
- 训练标签截止日：`2026-05-07`
- 资格状态：`candidate`
- 下单 API 调用：`0`
- 撤单 API 调用：`0`

## 改动摘要

### 新增

- 发布器新增 `publish-master` 动作，要求逐 release 的精确确认口令。
- 只允许目标分支 `master`，只接受精确的 `release(materials): <release_id>` 提交，拒绝 activation commit 或后续混合提交冒充 release commit。
- 发布前 fetch 并锁定远端 head；基于 detached worktree 合并不可变 release 目录和 index，以 `git push --no-force ... HEAD:refs/heads/master` 直推。
- 对 source、target、merged index 和 release 目录做全集及逐字段交叉校验；校验 release ID、material version、时间、来源 commit、manifest SHA256、tree fingerprint、文件数和策略版本。
- no-change 幂等路径也重新读取远端 head，防止 fetch 后竞态变化被误报为已发布。
- push 后通过 `git ls-remote` 回读，要求远端 head 与本次发布 commit 完全一致。
- Git LFS 在远端上传、pointer 和重新下载能力未被证明前 fail-closed，不能借直推绕过。

### 修改

- repo-local Skill、物料合同和 agent 描述统一为“产物目录直接合入 master，不走 PR，不 force push”。
- 发布器只合并 release 目录与 index；即使来源工作树存在 `CURRENT.json`，也不会随物料发布进入远端。
- 版本治理从只按 release ID 合并，收紧为 release ID 与 material version 双唯一并验证完整父链事实。

### 删除

- 删除“发布后必须人工 PR 才能进入 master”的流程要求。
- 未删除或修改任何策略 alpha、AI 排名逻辑、资金、品种、止损或下单规则。

## 参数与协议变化

### 新增参数/协议

- action：`publish-master`
- 确认口令：`I_APPROVE_DIRECT_OFFICIAL_MATERIAL_PUSH_TO_MASTER:<release_id>`
- 目标：`remote=origin`、`target_branch=master`
- push 规则：只允许 fast-forward、禁止 force、发布后 remote head readback
- LFS 规则：未证明目标远端对象上传与重下载前阻断发布

### 修改参数

- 无策略参数修改。

### 删除参数

- 无策略参数删除。

## 独立复审与问题关闭

独立 agent 对直推实现进行了多轮只读复审。首轮发现并随后关闭了以下会影响正式发布可信度的问题：activation commit 可能冒充 release commit并带入 `CURRENT.json`、幂等路径缺少最终远端 CAS、material version 可重复、`.gitattributes` 合并可能改变既有规则，以及 index 与 manifest 缺少引用完整性交叉校验。最终复审结论为没有剩余 Critical/Important，可继续真实直推。

## 验证结果

- 发布器聚焦测试：`11 passed`。
- 独立复审补充验证：`13 passed`，并验证伪造 index 会以 `release_index_manifest_mismatch` 阻断。
- 最终 Stage179 必需测试集：`879 passed, 694 subtests passed`，候选路径通过 `PYTHONPATH` 绑定当前 worktree。
- 远端回读：`origin/master=cba6d2f5fe7a20bf36848b94a19b9a885ef72ac1`，父提交为 `c758edbc4e8f589eeb75f3a3b75a3fa5a1b447bc`。
- 远端变更边界：`607` 个路径全部位于 `official_strategy_materials/`，目录外路径 `0`。
- 从已 fetch 的远端提交创建 detached worktree 后重新校验：`m0004` 的 `148` 个文件、manifest SHA256 和 tree fingerprint 全部通过。
- 远端 index 共有 `4` 个 release，最后一项为 `m0004`；远端 `CURRENT.json` 不存在。
- 未 clone 新仓库、未部署、未连接 CTP、未调用下单/撤单 API、未改 launchd。

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
- 原因：本阶段只治理物料依赖闭包、不可变版本、哈希、远端一致性和 Git 发布边界，没有根据收益曲线选择参数、日期、品种或模型阈值。

## 继续价值判断

- 是否还有价值继续：是。
- 原因：正式物料已经有稳定的直推 master 路径，后续 AI 池月更和实验晋级产物可以沿同一合同自动固化；同时保留资格与激活的独立门禁，避免“上传物料”等同于“切换线上策略”。

## 后续规划与 TODO

1. 后续 Stage935 月更或实验 AI 资产被正式晋级时，先统一登记，再生成新物料版本并运行 `publish-master`；普通 Git 资产可直推，任何 LFS 资产在远端能力未证明前继续阻断。
2. 如需让某个 material release 成为正式运行版本，仍需单独完成 Stage179 资格并走独立 activation/CURRENT 发布流程，不能由物料直推隐式激活。
3. 持续保留 remote head CAS、限定路径、索引引用完整性、不可变目录和远端 readback 回归测试。
