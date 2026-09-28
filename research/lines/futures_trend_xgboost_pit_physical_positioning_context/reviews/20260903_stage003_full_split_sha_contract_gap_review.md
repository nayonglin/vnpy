# Stage003 full split SHA 机器合同缺口独立评审

- 日期：2026-09-03（Asia/Shanghai）
- 决定：`BLOCK_STAGE003_IMPLEMENTATION_FOR_FULL_SPLIT_SHA_CONTRACT_GAP`
- 严重度：P0=0，P1=0，P2=1，P3=0
- 边界：只读核验原预注册、原始概率 remediation、当前机器合同字段及实际 full split 文件 SHA；未读取任何标签值或解析数据行，未运行实现、测试、fit、训练、预测、效果评价或回测，未修改代码、合同或测试，未创建 authorization。

## Finding

### P2-1：机器合同中的冻结输入 SHA 被截断，合法 identity-only 必然失败

当前 `contracts/stage003_joint_ranker_development_oos_training_contract.json` SHA256 为 `37dc6533143d1ed457088400e75d7a04364f62a70ea4c4a8fb95bd26e9cbe698`。其中 `input_sha256.full_feature_split` 实际为：

`a87c73e94eb2afae47ff881fcecda496aa81af5895165c2b1`

该值只有49个字符，不是小写64hex SHA256。以下三个独立身份均一致指向正确值：

- 原始 Stage003 预注册：`a87c73e94eb2afae47ffb106ec60d2720ff881fcecda496aa81af5895165c2b1`。
- 原始概率输入 remediation：`a87c73e94eb2afae47ffb106ec60d2720ff881fcecda496aa81af5895165c2b1`。
- 实际已冻结 `full_feature_split.csv` fresh SHA256：`a87c73e94eb2afae47ffb106ec60d2720ff881fcecda496aa81af5895165c2b1`。

因此这不是输入文件漂移，而是机器合同叶值被截断。严格 identity-only 实现必须在任何 feature/label 读取和 fit 前拒绝该合同；绕过检查或按前缀接受都会破坏冻结身份治理。该问题不产生标签泄漏或结果污染，但使当前 TDD 合同无法合法执行，故为阻断实现的 P2。

## 最小无标签修复

1. 新增不可变 remediation，记录当前缺陷机器合同 SHA、49字符错误值和正确64字符值；不得修改原预注册、既有 remediation、review 或 decision。
2. remediation 只允许把机器合同的 `input_sha256.full_feature_split` 改为正确的64字符 SHA；样本、输入路径、六列投影、标签规则、模型、参数、selector、seal 和 effect gates 不得改变。
3. corrected contract 必须通过语义 diff 证明相对当前合同只有该 JSON leaf 改变，并得到新的整文件 SHA256。
4. 机器身份校验应对 `input_sha256` 的每个值统一要求 native JSON string、精确小写64hex并与实际文件 SHA 相等；错误长度、前缀匹配、大小写、非字符串和文件不匹配均失败关闭。
5. 新增/保留无标签合成测试，明确证明49字符截断值在任何标签读取、feature parsing、fit 和结果写入前被拒绝；正确64字符值可通过 identity-only。不得用测试绕过 production validator。
6. 修复后必须进行新的独立 prereview，核验 corrected contract SHA、单叶语义 diff、正确文件身份及授权链；在该 review 的 P0/P1/P2 清零前不得恢复实现。

## Authorization 绑定链判断

**必须新增不可变 remediation、corrected contract 身份和新 rereview；仅原19项链不足。**

- `training_contract` 既有键继续指向同一路径，但未来 authorization 必须绑定 corrected contract 的新实际 SHA，不能绑定当前缺陷 SHA。
- 为保留完整治理历史，19项 exact set 应增加5个独立键：本 gap review、本 gap decision、新 SHA remediation、新 SHA remediation rereview及其 decision，形成24项 exact key set。
- 新 remediation 必须完整列出24项键和固定路径，并在机器合同中同步更新 `bound_file_keys`/`bound_file_paths`；两集合须唯一、数量均为24且完全相等。
- 当前缺陷合同 SHA 由本 gap review和新 remediation记录；不需要另造可变“旧合同”路径。最终 authorization 仍只绑定 corrected `training_contract` 文件及其新 SHA。
- authorization 只能在 corrected contract、新 rereview、实现/测试和最终实现 review 全部完成且用户另行明确授权后创建。

## 过拟合与继续价值

- 过拟合：否。该修复只纠正冻结文件身份字符串，不读取标签、效果或改变统计规则。
- 继续价值：有。修复成本低且能恢复 identity-only 的可执行性，但在不可变 remediation 和新独立 prereview完成前继续实现没有治理价值。

## 决策边界

存在1个P2，决定为 `BLOCK_STAGE003_IMPLEMENTATION_FOR_FULL_SPLIT_SHA_CONTRACT_GAP`。当前不允许继续Stage003实现、读取标签、fit、训练、预测、效果评价、回测、创建authorization、holdout、生产、CTP或order。
