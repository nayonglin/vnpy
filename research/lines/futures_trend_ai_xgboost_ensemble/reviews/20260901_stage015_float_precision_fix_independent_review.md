# Stage015 R14 浮点 fail-stop 与最小修复独立审查

## 结论

- 审查结论：`PASS`
- 严重度：`P0=0 / P1=0 / P2=1`
- 授权：`ALLOW_NEW_CAMPAIGN`
- 授权边界：只允许创建全新 campaign，并从 0 执行该 campaign 自己的 prepare 与四个 smoke job。新 smoke 仍须独立审查通过，之后才可在同一新 campaign 内继续剩余 351 个任务；本结论不是 `ALLOW_FULL_DEVELOPMENT_BATCH`，也不授权训练、holdout 或实盘接入。

## Findings

### P2：回归测试缺少真实差额的负向控制

`test_monetary_reconciliation_quantizes_real_r14_float_ulps` 已锁定 R14 三个原值并证明旧 float 残差大于 `1e-9`、新表示层结果为 0，但没有在仓库测试中继续断言：

- 增加一个完整金额量化单位 `0.000001` 元时必须保留该差额并被 `1e-9` 门拒绝；
- 调用金额对账函数不得改写输入值或标签值。

独立只读探针已补充验证当前实现：输入未变化；R14 量化误差为 `0.0`；人为增加 `0.000001` 元后误差为 `1e-06`，满足 `abs(error) > 1e-9`。因此这是未来回归保护不足，不是当前实现错误，不阻断新 campaign。

## 核心判断

### 1. `Decimal('0.000001')` 是否只修表示层

判断：合理，当前实现只改变金额一致性门的比较表示，不改变经济标签。

- 旧失败原值为 `base_equity=5280488.799999999`、`end_equity=5628573.799999996`、`future_net_pnl=348084.9999999986`；原生 float 残差为 `-1.3969838619232178e-09`。
- 当前 runner 在 `MONEY_QUANTUM = Decimal('0.000001')` 下，用 `Decimal(str(float(value))).quantize(...)` 分别规范化 end/base/net，再计算金额误差。
- `label` 仍直接来自未修改的 Stage010 `future_period_label()`；随后原样写入 `label.json`。量化值没有写回 `label`，`future_return`、`future_max_drawdown`、`future_net_pnl`、`future_slippage`、`future_trade_count` 等训练字段均保持原始值。
- 对旧 campaign 输入按当前代码重算身份，发生变化的文件键只有 `stage015_runner` 与 `stage015_preregistration`；Stage010 标签公式及其他上游输入未变化。
- worker receipt 新增 `monetary_reconciliation_quantum` 只是审计元数据，不进入标签。

需要精确定义“阈值不变”：金额项先规范化到微元，因此其误差只能以 `1e-6` 元为步长，之后仍执行原 `> 1e-9` fail-stop。它等价于“微元规范化后必须精确闭合”，不是继续分辨原始二进制 float 的纳元尾差。这个表示合同会吞掉不足半个微元附近的原始残差，但微元远低于人民币最小货币单位，且一个完整微元的真实差额仍会失败；作为预注册的表示层修复可以接受。

Python 官方文档说明，`Decimal` 从字符串构造可避免把二进制 float 的完整尾差带入十进制表示，而 `quantize()` 用于固定指数舍入，适合货币类固定精度计算：https://docs.python.org/3/library/decimal.html

### 2. `1e-9`、标签原值与七项跨来源对账是否保持

判断：保持。

- worker 仍对 `internal_errors` 的最大绝对值执行 `> 1e-9` 拒绝；aggregate 仍以 `<= 1e-9` 验收所有 `_error` 字段。
- 只有 `end_equity_vs_future_net_pnl_error` 及候选相对基线的同类金额误差使用微元规范化。
- 七项跨来源误差仍用原始数据与原始标签计算，未量化、未改公式：curve 净 PnL、curve 滑点、curve 交易数、combined 净 PnL、combined 滑点、combined 交易数、trades 行数。
- R14 原失败日志和 `failure_receipt.json` 显示上述七项均为 `0.0`；当前源码仍保留同名七项及统一 `1e-9` 门。
- 收益差对账 `return_vs_equity_delta_error` 仍使用原始 `future_return`、原始权益差和共同基准权益，没有进入 Decimal 量化路径。

### 3. 旧 campaign 与 133 个输出是否明确禁止复用

判断：明确禁止，文档门和机器身份门均成立。

- `failure_receipt.json` 的决策为 `stage015_float_representation_gate_failed_abandon_campaign`，并显式记录 `campaign_reuse_allowed=false`、`cross_campaign_job_output_reuse_allowed=false`、`development_labels_published=false`。
- 旧 campaign `progress.json` 与 `LATEST.json` 均为 `status=failed`；父进程计数 132，磁盘上有 133 个 in-flight 收尾后的 job 目录；不存在 `development_labels.csv`、`reconciliation.csv` 或 `decision.json`。
- 旧 runner SHA 为 `f4033547169feaa33c04ade69c58403a4a8b05717abff4517328fcbef2e1f9b4`，当前 runner SHA 为 `7c85022ed4d2094fd1f10c559863a5d4ce95f1193510906bac52c65702bc954f`。
- 旧 campaign contract 为 `4c374c8869abfe17a6234b82b136ba36f6795e77ead97929328f3bc0ee21557f`；以当前 runner/预注册对同一 frozen 输入重算为 `3d590fb95596564e6ad5d34a4190651eb9215c657a624c06dfe02126d21ca03e`，两者不相等。
- 同一旧 smoke 输出在旧 contract 下校验为有效，在当前 contract 下校验为无效。`_resume_identity_gate()` 又比较完整 campaign manifest，因此当前 runner 无法续跑旧 campaign；新 campaign 也不能把旧 worker receipt 当成已完成任务。

### 4. 新 campaign 是否必须从 0 重跑

判断：必须。

- 当前目录中尚未创建修复后的新 campaign，也没有 Stage015 worker 在运行。
- 新 campaign 必须重新 prepare，形成包含当前 runner 与修订后预注册文件的新身份合同；不得复制、链接或登记旧 133 个 job 输出。
- 四个 smoke job 必须在新 campaign 中重新冷跑。它们通过独立 smoke 审查后，可作为新 campaign 自己的 355 个任务中的已完成部分继续剩余 351 个任务；这不属于复用旧 campaign。
- 任一新 smoke 的标签、七项跨来源对账、A/A、输入身份、输出 SHA、PID/TMP 隔离或 600 秒门失败，均应再次 fail-stop，不得进入完整批次。

## 只读验证

- 定向测试：`12 passed in 1.55s`。
- R14 数值探针：原始误差 `-1.3969838619232178e-09`；规范化误差 `0.0`；增加一个微元后的误差 `1e-06`；输入未改写。
- 身份探针：旧/当前完整 manifest 不相等，差异文件键仅为 runner 与预注册；旧输出无法通过当前 contract。
- 未运行新的历史回测，未读取 133 个部分标签作绩效或参数判断，未生成 development/holdout 标签，未连接 CTP，未调用订单 API。

## 过拟合与继续价值

- 是否过拟合：否。修复依据是确定性的浮点表示失败和跨来源零误差，没有按收益、回撤、月份、rank 或部分标签值调整模型、样本、特征或门槛。
- 是否值得继续：是。当前最小修复保持标签与 alpha 合同，并通过新 campaign 身份强制隔离旧结果；下一步只应创建新 campaign、从 0 重跑 smoke 并再次独立审查。
