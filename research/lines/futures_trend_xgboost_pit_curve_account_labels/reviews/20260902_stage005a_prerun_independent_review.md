# Stage005A 预运行独立评审

- 评审时间：2026-09-02 18:18 +0800
- 评审角色：独立只读 reviewer
- 评审结论：`BLOCK_STAGE005A_SMOKE`
- 严重度：P0=0，P1=2，P2=2，P3=1
- 置信度：99%
- 运行边界：未创建 runtime/campaign/artifact，未运行 worker/backtest，未连接 CTP，未调用订单 API

## P1 必须修复

1. Stage005A scope audit 把扫描到的全部实际文件再次作为 `allowed_artifact_paths`，形成循环自证。加入未声明的 `sealed_holdout_labels.csv` 后仍会通过。必须改成由预注册合同生成的精确静态 allowlist，并增加未知 CSV、holdout 文件和根目录外文件负向测试。
2. `run_worker` 只校验 job ID，未在写 lock 前校验 campaign 位于 `CAMPAIGN_ROOT`、无 `ABANDONED.json`、identity/plan 匹配。必须在进入 Stage004 worker 前完成这些门禁。

## P2/P3

- P2：结构化 severity 使用 `isinstance(value, int)`，JSON 布尔值可被当成整数；应改为 `type(value) is int and value >= 0`。
- P2：专项测试需补授权门、worker root 越界、snapshot 清理和真实 legacy loader 路径覆盖。
- P3：snapshot 目录创建发生在清理 `try` 之前；应只清理本次实际创建的路径，并确保初始化失败也不留部分目录。

## 身份核验

- DB：`db3342006f4220767f06e466bb40c046f372961cea41cef9a6d8bc1727fa0c4b`，112271360 bytes，1020420 行，最大时间 `2026-09-02 00:00:00`，integrity `ok`。
- Mapping：`093d3bc767c09d9e0e4f4fbeb9846a091bf25c163cc31eddfd382cc1ff5490b7`，18363526 bytes，342433 行。
- Minute：`8e861633b08a82819a668c30c6799e2098d2beaa6863698351145018ea586784`，201354181 bytes，1291049 行。
- Metadata：`24a3573e847e024411b13a3a3b775791ded57563b0a68b717d1065078201635a`，11173 bytes，86 行。
- Production checkout：`d492ee072aa5a9d71477235d79f17d2a5db59db3`，clean。
- loader 实测最终指向 v2 `frozen_inputs`；worker command 会重新进入 Stage005A wrapper。

## 验证

- 专项 pytest：29 passed。
- 定向 `py_compile`：通过。
- 无授权 preflight：按预期 fail closed。
- 被否决输入 SHA256：
  - runner：`a31f0e9fa110520fa21fc82367decc74ddb591e40508b08b565016d4f7547560`
  - runner_test：`552de62009b616ae9b49a78b5011db76eb7cd510b16b40afd1e46fae1507d9a5`
  - scope_core：`8459ff839869437c3fac97808029606b8e63500ff8b179348b44bce883474ca4`
  - stage004_runner：`8c8de4037e4bc64096b88a87a1a76a18a17033f2a9b16ce6c3aa3238fb1bc819`
  - runtime_core：`c651cac7d515189edbed22b107899fef5464e5179179320b341e0e1f12a055e4`
  - account_label_plan：`ba4029611323d50bc274efd20dbee79f7b62b94c6564fd0b4e69f4c36fefea88`
  - preregistration：`77f5560d3193ad4eefce66f59918344ebe2ce62e8bbb8593cf0b9344752e9925`

以上 SHA 只用于记录被否决输入，不得生成运行授权。

## 判断

- 过拟合：否；本次只审计冻结身份与执行治理，没有选样、调参或读取新回测结果。
- 继续价值：是，但仅限修复两个 P1、补负向测试并重新独立评审；修复前不得创建 runtime/campaign 或运行 smoke。
