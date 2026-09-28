# Stage001 第八轮运行前独立审查（阻断）

- 审查时间：2026-09-05 14:16 +0800
- 审查角色：第八轮独立只读prereviewer
- reviewer session：`01a0701b-c33b-7fc3-8637-557735b01a81`
- 决策：`BLOCK_STAGE001_UNIQUE_RUN`
- 严重度：P0=0，P1=0，P2=1，P3=1
- 执行边界：仅静态读取；未修改研究线文件，未运行测试、Stage001或策略回放，未读取标签或收益，未训练或预测，未联网，未导入生产策略，未连接CTP，未读取账户/持仓，未调用订单API，未写生产目录

## 第七轮关闭矩阵

| 第七轮项 | 第八轮结论 | 判断 |
|---|---|---|
| R7-P2-001 | 原始范围已关闭 | 正常路径和reconcile恢复在cleanup后共用完成原语；rename前后、cleanup后和sequence=7前均重验当前authorization、bound files、1410项输入/runtime及正式身份。 |
| R7-P2-002 | 部分关闭 | 完整publishing event校验、CAS、sequence 6到7、generic completed自更新禁止和精确幂等读取已实现；但claim锁仍可fail-open，且当前claim未在锁内绑定。 |

## R6/R5回归矩阵

| 项目 | 第八轮结论 | 判断 |
|---|---|---|
| R6-P2-001 | 已关闭、未回归 | authorization由同一次bytes解析payload和SHA，成功发布与完成前当前绑定重验完整。 |
| R5-P1-001 | 已关闭、未回归 | 恢复仍验证worker completed、一次回放、固定身份/资金/区间、sandbox/guard和零敏感计数。 |
| R5-P2-001 | 部分开放 | authorization、bound files、输入/runtime、生产身份和publishing event已绑定，当前状态claim仍未绑定。 |
| R5-P2-002 | 已关闭、未回归 | 独立trace先枚举同向持仓，对unknown和未测全均fail-close。 |

## 阻断项

1. P2（R8-P2-001）：claim锁可静默绕过，完成原语未绑定当前状态claim。
   - `_execution_event_lock`在同级`claim.json`不存在时直接yield，event写入退化为无进程锁。
   - reconcile先预读claim，cleanup后才进入完成原语；完成原语只比较success bundle claim与调用方传入的旧claim，从未在锁内重读并核对当前`CLAIM_PATH`。
   - 可利用路径：final与sequence=6合法；reconcile预读claim；cleanup期间删除或替换claim；随后完成路径无锁或锁住新inode，继续用旧claim写出sequence=7，留下缺claim或claim与event/final不一致的状态。
   - generic failed/running writer也可能在锁静默绕过后由两个进程基于旧event覆盖，丢失phase、sequence或敏感计数。

2. P3（R8-P3-001）：final已rename后的reconcile异常被丢弃。
   - `run_stage001`在final存在的异常分支捕获并忽略全部reconcile异常，只抛通用错误。
   - 当前仍fail-close，但最初异常和恢复异常的诊断信息丢失。

## 整改要求

- claim不存在必须fail-close；所有writer必须使用不可静默降级的固定锁锚点。
- 锁内从被锁定claim文件读取并精确核对当前payload、nonce/lease、authorization SHA和输入合同，再读取或更新event。
- 增加cleanup期间删除/替换claim的reconcile反例，失败后event bytes必须保持原sequence=6。
- 增加真实双进程event竞争反例，不能只依赖线程测试或持锁线程内的人工替换。
- 保留final已rename后初始异常与reconcile异常，补永久漂移调用链诊断测试。

## 冻结事实复核

- authorization、execution state、success/failure final、artifacts目录及隐藏staging/publish均不存在；Stage001未授权、未执行，唯一机会未消费。
- 独立静态重算为1410项，logical-key SHA为`a972f46932585adf1ad5bfc4f0c3d76d5b654cd587204b8c4bd0512b791aacd2`，file contract SHA为`49b3048d4a7458530e007f18b155c84db754d775f00a6f6b9041929e787ca9a6`，runtime SHA为`04396eb74da1ed4812b0eabcc94e28cd2a64f90a1839d08ace6630faf2149e1e`。
- 生产目录保持干净，HEAD为`d492ee072aa5a9d71477235d79f17d2a5db59db3`；m0005、正式策略、C9-15万执行版本和资金一致。
- reviewer未运行测试，因此不采信主agent的145/877测试计数；静态确认当前缺少真实双进程完成竞争覆盖。

## 决定

- 不创建一次性authorization，不运行Stage001；唯一运行机会未消费。
- 先按TDD关闭R8-P2-001并整改R8-P3-001，完成专项与跨线回归，再进入第九轮独立只读预审。

## 过拟合与继续价值

- 过拟合：否；本轮只审查无标签状态机和证据合同，没有观察收益或调整模型。
- 是否继续：是，但仅限修复claim锁、补真实双进程反例及重新预审；当前运行Stage001没有价值且不允许。
