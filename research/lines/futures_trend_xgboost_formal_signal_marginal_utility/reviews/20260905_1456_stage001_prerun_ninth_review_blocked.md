# Stage001 第九轮运行前独立审查（阻断）

- 审查时间：2026-09-05 14:56 +0800
- 审查角色：第九轮独立只读prereviewer
- reviewer session：`01a07048-afd1-7490-9595-fa11d4044eef`
- 决策：`BLOCK_STAGE001_UNIQUE_RUN`
- 严重度：P0=0，P1=0，P2=1，P3=2
- 执行边界：仅静态读取；未修改研究线文件，未运行测试、Stage001或策略回放，未读取标签或收益，未训练或预测，未联网，未导入生产策略，未连接CTP，未读取账户/持仓，未调用订单API，未写生产目录

## 第八轮关闭矩阵

| 项目 | 第九轮结论 | 判断 |
|---|---|---|
| R8-P2-001 | 部分关闭 | 状态目录fd锁、目录inode校验、claim缺失fail-close、`O_NOFOLLOW`和当前claim绑定已实现；但最终event写入仍按路径rename，验证对象与落盘目录之间仍有TOCTOU。 |
| R8-P3-001 | 已关闭 | final已rename后的错误同时保留initial与reconcile异常。 |
| R7-P2-001 | 已关闭 | 正常与reconcile恢复共用完成原语。 |
| R7-P2-002 | 部分关闭 | 状态机、完整event CAS及completed幂等成立，最终路径原子边界仍开放。 |
| R6-P2-001 | 已关闭 | authorization单次bytes读取及当前输入、bound files多时点重验成立。 |
| R5-P1-001 | 已关闭 | worker、单次回放、身份、sandbox、guard、counter及A1/A2重算校验仍在。 |
| R5-P2-001 | 部分关闭 | 完整授权与输入绑定成立，当前claim/event最终原子绑定仍开放。 |
| R5-P2-002 | 已关闭 | 独立枚举同向持仓，history unknown或未测全均fail-close。 |

## 阻断项

1. P2（R9-P2-001）：event最终落盘仍存在claim/path TOCTOU。
   - 目录锁已绑定稳定目录fd，claim也在锁内安全读取并校验；但通用writer与success completed CAS在最终写入时仍调用路径型`_atomic_replace_json`。
   - 该函数先按路径创建临时文件，最后按路径执行`os.replace`；在最后一次claim/event校验之后替换claim、event或整个状态目录，可能让sequence 7落入不再匹配冻结claim的当前路径。
   - claim读取只有一次`fstat`和一次路径`stat`，缺少读后fd再次取证与路径长度/时间元数据比较，同inode原地改写仍可能漏检。

## P3项

1. P3（R9-P3-001）：真实双进程测试没有“进程B已经尝试获取锁”的确定性握手，仅以ready、100ms等待和done缺失推断阻塞，可能因调度延迟误通过。
2. P3（R9-P3-002）：非final-success失败路径以`finally`更新event；failure publish或event更新再次异常时可能覆盖最初执行异常，诊断链不完整。

## 整改要求

- 所有锁内claim/event/temp操作改为锁定状态目录fd下的`dir_fd`相对操作；writer不得重建父目录。
- claim在读取前后对fd重复取证，并与当前目录fd相对路径的类型、device/inode、size及时间元数据一致。
- event读取、临时文件创建、rename和目录fsync均绑定同一个锁定目录fd；rename紧前重新校验目录锚点、完整claim bytes和expected event。
- 增加最后校验后、rename前分别替换claim、event和整个状态目录的确定性反例，失败时当前event不得被旧writer覆盖。
- 双进程锁测试增加确定性的attempted/entered握手；失败发布链同时保存initial、publish和event-update异常。

## 冻结事实复核

- authorization、execution state、success/failure final及隐藏staging/publish均不存在；Stage001未授权、未执行，唯一机会未消费。
- 独立静态重算为1410项；logical-key SHA为`a972f46932585adf1ad5bfc4f0c3d76d5b654cd587204b8c4bd0512b791aacd2`，file contract SHA为`b51f0b1c3d43f607952012102ab08486f714511bc2c48394d19ff35470a4906f`，runtime SHA为`04396eb74da1ed4812b0eabcc94e28cd2a64f90a1839d08ace6630faf2149e1e`。
- 生产目录保持干净，HEAD为`d492ee072aa5a9d71477235d79f17d2a5db59db3`；m0005、正式策略、C9-15万执行版本和资金一致。
- reviewer未运行测试，不采信主agent此前的152/884测试计数。

## 决定

- 不创建一次性authorization，不运行Stage001；唯一运行机会未消费。
- 先按TDD关闭R9-P2-001及两项P3，完成专项与跨线回归，再进入第十轮独立只读预审。

## 过拟合与继续价值

- 过拟合：否；本轮只审查无标签状态机与文件系统原子边界，没有观察收益或调整模型。
- 是否继续：是，但仅限修复dir-fd落盘原子边界、异常链和确定性进程测试并重新预审；当前运行Stage001没有价值且不允许。
