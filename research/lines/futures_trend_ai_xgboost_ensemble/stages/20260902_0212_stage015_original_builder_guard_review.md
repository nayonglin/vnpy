# Stage015 原始 builder 函数对象门禁复审

## 时间与性质

- 时间：2026-09-02 02:12（Asia/Shanghai）。
- 研究线：`futures_trend_ai_xgboost_ensemble`。
- 是否重要突破版本：否；这是 development 标签基础设施的执行隔离闭环，不是 alpha 结果。
- 当前线上：`m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1`，生产目录未修改。

## 变更

- 新增原始 universe / eligibility builder 函数对象级 guard：临时替换同一函数对象的 `__code__`，扫描外的局部缓存、默认参数、closure、对象属性和 `partial` 调用也会真实计数并立即失败。
- 新增两个共享源文件的 worker 前后七项身份封印：`path/dev/inode/size/mtime_ns/ctime_ns/SHA256`，任一变化或不可读均阻止 job 发布。
- 新增 context 退出时二次扫描，恢复运行期间新出现的 import-by-value redirect。
- 新增 origin、Stage78、Stage777 六个必需绑定的逐项覆盖门，以及 universe / eligibility 分项绑定计数。
- worker receipt、completed-job validator、smoke、aggregate 统一消费 `_shared_builder_receipt_gate`，不再把固定的 `original_shared_builder_call_count=0` 当作证据。
- 新增参数：无。修改参数：无。删除参数：无。冻结特征、XGBoost 参数、样本月份、rank 网格、并发数、超时及对账阈值均未改变。

## 验证与决定

- runner SHA256：`1033b573d3c9faf6f9630acf637649127c8731adaa639f4d66e65c84c51a1c92`。
- TDD：五个关键负向测试先红后绿；Stage015 `30/30`，整线 `98/98`。
- 独立复审：`P0=0 / P1=0 / P2=0`，决定 `ALLOW_NEW_CAMPAIGN`。
- Reviewer 额外验证 10 次扫描外原函数调用全部被阻断、动态 import 正常/异常恢复、共享源始末一致、31 类 receipt 篡改全部被拒绝。
- 旧 `campaign_20260902T003958+0800_80965` 继续永久废弃，4 个 smoke 输出禁止复用；`development_labels.csv` 不存在，sealed holdout 标签读取数为 0。
- 下一步只能从零创建新 campaign，并先运行冻结的四个 smoke job。

## 回测指标

- 新增回测结果：无；本阶段没有运行新 campaign、smoke 或完整批次。
- 修改/删除回测结果：无；仅补充旧废弃 campaign 的 replacement runner 与 review 追踪字段。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均不发布，因为完整 development 标签批次尚未开始。

## 反思

- 是否过拟合：否。全部修改只针对 Python 对象绑定、共享文件身份和 receipt 门禁，没有读取标签收益分布、没有修改模型合同、没有触碰 holdout。
- 是否值得继续：是。已把上一轮可复现的共享写风险闭环；下一步 4-job smoke 能以较低成本验证真实冷进程路径。若再次出现新的共享状态绕过，应停止继续叠加 monkeypatch，转向 worker 级隔离运行目录。
