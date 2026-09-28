# Stage016 运行前独立代码审查

## 结论先行

- 审查结论：`BLOCK_FROZEN_STAGE016_RUN`。
- 严重度：`P0=0 / P1=3 / P2=2`。
- `ALLOW_FROZEN_STAGE016_RUN=NO`。
- 审查未运行Stage016真实入口、未读取`development_labels.csv`数据行、未生成`frozen_run`、未修改任何文件。

## P1

### 1. 技术门失败后仍可能披露真实效果

- 入口先计算技术门，但未在失败时短路，随后仍调用效果评价并发布含真实标签结果的预测、月度选择和效果报告。
- 这与预注册“技术失败只允许修复实现错误”冲突；一旦披露效果，修复后重跑不再是盲评。
- 必须在`technical_pass=false`时停止效果计算，只发布不含真实效果值的技术失败审计包，并增加“效果函数不得被调用”的合成测试。

### 2. 非有限值可绕过fail-closed门

- `np.nanmax`会忽略部分`NaN`；reconciliation、rank10相对标签及两头预测没有先执行全量有限值检查。
- 独立合成探针观察到`RECON_NAN_ACCEPTED 0.0`和`INF_SELECTION_ACCEPTED 11 True`。
- 必须对reconciliation、相对标签和两头预测显式要求`np.isfinite(...).all()`，并增加NaN及正负无穷回归测试。

### 3. 运行入口未前置绑定本次审查与runner/test身份

- 合同和预注册已有固定SHA，数据输入也有前后校验；但runner/test只在训练完成后计算一次SHA，没有运行前授权值或前后稳定性比较。
- 当前四个送审文件均未被Git跟踪。审查后或运行中修改代码，可能在事后才被发现。
- 必须使用不可变提交或独立运行授权清单绑定审查结论、runner/test SHA，并在读取标签前及发布前验证身份稳定。

## P2

1. 同目录临时目录加`os.rename`具备目录级原子可见性，但全量文件identity未持久化，也没有文件和父目录`fsync`；建议增加非循环artifact manifest和故障注入测试。
2. 现有14项合成测试未覆盖技术失败短路、非有限值拒绝、review/runner身份绑定及显式holdout标签注入；修复P1时应补齐。

## 已确认正确

- PIT条件是`train eval_date < test eval_date`且`next_eval_date <= test eval_date`。
- 15折、训练月份`24..38`、每折9候选的技术门已实现。
- 双头等权月内分位、固定tie-break及C双正预测门与预注册一致。
- 入口只硬编码development标签路径，未发现holdout标签读取入口。
- `stage016_decision`不会在技术门失败时授权真实引擎A/C；当前问题是技术失败仍可能披露效果。

## 验证记录与反思

- 合成单测：`14 passed`；AST静态解析通过。
- 过拟合判断：当前风险高。若技术失败仍披露效果，修复重跑会受到结果污染。
- 继续价值判断：有，但仅在全部P1修复、补测试并重新独立审查后；此前不得运行真实Stage016。
- reviewer agent：`01a05f34-1404-7020-89a4-654a0ada4ca7`。
