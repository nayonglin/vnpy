# Stage015：development批次浮点金额门fail-stop

## 阶段信息

- 失败时间：2026-09-01 20:42 CST；诊断完成：20:45 CST
- 是否重要突破版本：否；标签生产基础设施数值表示缺陷
- campaign：`campaign_20260901T191852+0800_76524`
- campaign contract：`4c374c8869abfe17a6234b82b136ba36f6795e77ead97929328f3bc0ee21557f`
- 当前线上与策略参数无变化：m0005、15万元C9正式规则
- 本批次运行真实历史回测，但不训练模型、不发布部分development标签、不生成holdout标签、不连接CTP、不调用订单API

## 运行结果

- 父进程在`20230630_R14`失败后立即停止继续排队；progress计数132，另一个在途worker正常收尾后共有133个有效job输出目录。
- `development_labels.csv`未生成；132/133个部分标签不得用于特征、参数、月份、rank或模型门槛调整。
- 失败job用原runner、原campaign、原eligibility独立复现，错误完全一致。

## 根因证据

- `base_equity = 5,280,488.799999999`
- `end_equity = 5,628,573.799999996`
- `future_net_pnl = 348,084.9999999986`
- 原始Python float执行`end - base - net`得到`-1.3969838619232178e-09`，略超过预注册`1e-9`。
- 同一job的目标期curve净PnL、combined净PnL、curve/combined滑点、curve/combined交易数、逐笔trade行数七项独立误差全部为0。
- 根因不是经济金额不闭合，而是约528万元量级的账户权益累计值与逐日PnL累计值经过不同二进制浮点路径后相差约1-2个ULP。

## 当前版本变更与结果边界

- 新增参数：无。
- 修改参数：无策略参数、模型参数或样本参数修改。
- 删除参数：无。
- 新增回测结果：133个冷进程输出，但campaign整体判定失败，禁止跨campaign复用。
- 修改/删除回测结果：无；不删除失败证据。
- 已登记`failure_receipt.json`，决策为`stage015_float_representation_gate_failed_abandon_campaign`。

## 修复预注册

- 不放宽`<=1e-9`门槛，不修改标签公式，不改任何alpha规则。
- 只修金额表示层：比较账户权益与净PnL前，先把三者分别按`Decimal('0.000001')`元统一量化，再计算误差；百万分之一元远小于实际人民币最小货币单位，同时消除二进制float ULP假失败。
- 必须先增加包含本次三个原值的回归测试并观察旧实现失败，再实现最小修复；curve/combined/trades七项原始误差门保持不变。
- runner哈希变化后原campaign永久废弃；新建campaign、重新prepare/smoke/独立review，并从0运行全部355任务，不复用133个旧输出。

## 回测指标说明

- 本次fail-stop发生在账户金额一致性门，不是策略绩效门；完整批次没有形成可发布的期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数或胜率汇总。
- 四个已完成smoke的正式指标已单独记录在`20260901_1922_stage015_smoke_receipt.md`，本记录不重复把部分网格汇总成策略结论。

## 过拟合与继续价值（失败后）

- 是否过拟合：否。失败后没有根据收益或回撤结果改样本、特征、模型或门槛；拟修复的是确定性的金额数值表示。
- 是否值得继续：是。七项跨来源对账与原runner复现已把根因限定为ULP误差，使用严格微元量化可在不改变经济标签的前提下修复；但旧campaign不得继续。
