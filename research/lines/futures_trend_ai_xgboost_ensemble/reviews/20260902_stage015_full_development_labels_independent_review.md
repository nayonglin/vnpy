# Stage015 完整 development 标签批次独立评审

## 结论先行

- 结论：`ALLOW_FROZEN_STAGE016_TRAINING`
- 严重度：`P0=0`、`P1=0`、`P2=0`
- 没有采信 `decision.json` 的自报结论。独立分层重算确认：355 个 cold jobs、2840 个固定输出、355 份 receipt、2235 项 campaign 输入、351 行 development labels、351 行 reconciliation、4 个 A2、39 个月 predecision、共享源始末身份和最终发布身份全部闭环。
- 本授权只允许 Stage016 使用本 review 冻结的 `development_labels.csv` 和 `reconciliation.csv` 字节身份进行预注册训练；不授权修改 Stage015 合同、读取 sealed holdout 标签、根据 development 收益结果调参、连接 CTP 或调用订单 API。

## 审查对象与冻结身份

- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- line_id：`futures_trend_ai_xgboost_ensemble`
- campaign：`campaign_20260902T021241+0800_98656`
- campaign 路径：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_ai_xgboost_ensemble/artifacts/stage015_development_label_batch/campaign_20260902T021241+0800_98656`
- campaign file contract：`ac8e5a6e77b081eaad97bcc30ef89769d6586eecd1b079ccef713e8d3d8d5d4f`
- runner SHA256：`1033b573d3c9faf6f9630acf637649127c8731adaa639f4d66e65c84c51a1c92`
- tests SHA256：`b1bd4fdaa2f191bbb80874c7b6534b7062c66dacd6dcfe300139cb728f41d541`
- 前置 smoke review SHA256：`4bbb866bbfb3d5b4b7405691ae5d82e8e96e4aa5b04d0c9eefcea1f4b899d167`
- `jobs.csv` SHA256：`aa0a14ae17aa5089faf4be6767e97a5838e8a1c7b0f88cd4139ea2a2f2925555`
- `development_labels.csv` SHA256：`39e969783adc2ac54f771cf03e685a4cec45ce09adeb2d1eefc6ca54ef2cbce2`
- `reconciliation.csv` SHA256：`d595547fa81906093c0fd530acbfa5d0f2b7c3fe489987efa79da304b977eb95`
- 355 份 worker receipt 及其 output map 的稳定聚合 SHA256：`02ac33aea55f820a1f7f6d94525a8195d0f96e261aa4c5c650c48974ad8f62ed`
- `decision.json` SHA256：`14ba5dda1f895893d3b50b776fbedf58e1c042744cf8013e0bed2de591604c81`
- `progress.json` 与 active `LATEST.json` 字节一致，SHA256：`c811c538a045fb3b089ed0780e81350bf12ec128a5a0cad413861bef726a0d8e`

审查期间未修改 runner、tests、campaign、artifacts、共享源或其他文件；唯一新增文件为本 review。

外部方法核对使用 Python 3.11 官方文档：文件身份同时使用 `st_dev/st_ino/st_size/st_mtime_ns/st_ctime_ns` 与 SHA256；货币恒等式使用 `Decimal.quantize(Decimal("0.000001"))`。这避免只看 inode、mtime 或二进制 float 所造成的假一致/假漂移：

- https://docs.python.org/3.11/library/os.html
- https://docs.python.org/3.11/library/hashlib.html
- https://docs.python.org/3.11/library/decimal.html

## P0

无。

## P1

无。

## P2

无。

## 1. 355 jobs 与固定产物

独立读取 `jobs.csv` 和目录结构：

- jobs 共 `355`，job_id 唯一；main `351`、A2 sentinel `4`。
- main 覆盖 `39` 个 development 月，每月 rank 严格为 `10..18`。
- sealed holdout jobs 为 `0`。
- `job_outputs/` 的目录名集合与 355 个 job_id 精确一致。
- 每个 job 目录恰有八个固定输出和一份 `worker_receipt.json`，没有缺项或额外文件。
- 独立重算八类 output SHA 共 `355 x 8 = 2840` 项，全部与各自 worker receipt 的 `output_sha256` 精确一致。
- 预建 `.partial/` 目录存在但条目数为 `0`；目标 campaign 不存在 `failure_receipt.json` 或 `ABANDONED.json`。
- 四个旧 campaign 均未进入当前 output 集合；active progress/LATEST 只绑定当前 campaign。

## 2. campaign manifest、runtime 与 repository

采用不会隐藏漂移的两层重算：

1. 先对 manifest 的全部 2235 个条目、2234 个唯一物理路径逐文件重算当前 size/SHA；missing `0`、size drift `0`、SHA drift `0`。
2. 再从已验证 manifest 按 worker exact keys、prefixes 和对应 eligibility key 重建每个 job 的 execution manifest，并加入当前 `campaign_identity.json` 身份。

结果：

- 2235 项重算 file contract 为 `ac8e5a...d4f`，与送审合同和 manifest 完全一致。
- `campaign_identity.json`、`campaign_identity_after.json`、`campaign_identity_before_publish.json` 内容和 SHA 完全一致，SHA256 均为 `00ebd9b2ab86185a1be4f98b3c3001573e2adf89ef31055fa3441d49eae2a93f`。
- 三份 identity 的 runtime/repository 内容完全一致。
- 在复现冻结 environment 和 sys.path 后调用当前 runner `_runtime_contract()`，与 manifest runtime 逐字段精确相等。
- repository identity 为 production head `d492ee072aa5a9d71477235d79f17d2a5db59db3`、production status 空、workspace vnpy status 空；当前复算无漂移。
- 355 份 execution manifest 重算全部通过；每份 `execution_unique_physical_file_count=1869`，contract 与 worker receipt 精确一致。
- 测试后再次全量哈希 2235 项，drift 仍为 `0`，合同不变。

该分层方式只对共享输入物理文件哈希一次，但每个 job 的 key 集合、eligibility、contract 和 unique physical count 都单独重建；不会因缓存旧结果而掩盖某个输入漂移。

## 3. worker 隔离、runtime 与不复用

355 份 receipt 全量检查：

- unique fresh PID：`355`
- unique TMPDIR：`355`
- unique MPLCONFIGDIR：`355`
- normalized runtime SHA 种类：`1`
- normalized runtime SHA256：`8b37a9dbf8de6b7774d08be4729b4a197a258abdf018ccdc2f52ec7abf991028`
- 最大 wall：`96.01085916601005 < 600` 秒
- `checkpoint_reused=false`：`355/355`
- `completed_result_reused=false`：`355/355`
- 每个 TMP/MPL 均位于本 campaign、本 job、本 run 的私有 `/private/tmp/vnpy-stage015-development-label-batch/.../{tmp,mplconfig}`，receipt 顶层值与 runtime environment 一致。
- campaign id/path/contract、job id/type/eval/next/rank 与 `jobs.csv` 精确一致。
- official overrides、private universe、profile overrides、private profile eligibility 的四个当前 SHA 与全部 355 份 receipt 一致；snapshot source 均为 `campaign_snapshot`。

生产 `_shared_builder_receipt_gate` 对 355 份 receipt 全部返回 true；另取首月基准、中段 challenger、末段 A2 和最后一个 challenger 调用生产 `_validate_completed_job`，四个跨时间样本均返回 true。

## 4. original shared builder guard 与共享源

355 份 receipt 全部满足：

- required bindings 精确为冻结六项，顺序一致。
- binding total/universe/eligibility 为 `6=3+3`。
- universe redirect 最小调用数 `2`，eligibility redirect 最小调用数 `2`。
- original universe/eligibility/total calls 始终为 `0/0/0`。
- nested guard、original function guard、required coverage、source identity pass 均为 true。
- binding list 长度与 count 一致，dynamic restore count 非负。

当前共享源七项身份：

- universe：path 为冻结共享路径，dev `16777232`、inode `422227924`、size `6272`、mtime_ns/ctime_ns `1788286367623480595`、SHA256 `72c5ca576bfe8aebe12da1e750d9eac980633a43ab9944479a77a7e824a71e34`。
- eligibility：path 为冻结共享路径，dev `16777232`、inode `422227925`、size `51303`、mtime_ns/ctime_ns `1788286367631031389`、SHA256 `fa5fb5c1cfe06ace44dadc92bd2cc1a77bd4ee74beeab362234952950ca5bb3b`。

355 份 source before 只有一个唯一身份，355 份 source after 也只有同一个身份；每份 before==after，并且都精确等于当前七项身份。receipt 时间覆盖 `2026-09-02T02:15:21+08:00` 到 `2026-09-02T06:06:29+08:00`，因此完整 batch 前后没有共享源写入。

## 5. 四个 A2 与 39 月 predecision

四个 A2 sentinel：

- `20220429_R10_A2`
- `20230428_R10_A2`
- `20240430_R10_A2`
- `20250430_R10_A2`

每个 A2 与同月 main rank10 的 `label.json` 及六类目标 payload：`curve/combined/trades/entry_candidates/entry_risk/trade_events` 均逐字节一致，`4 x 7` 文件 gate 全部通过。

对 39 个月分别收集当月 rank10..18，并在含 A2 的四个月同时包含 sentinel receipt；`curve/trades/entry_candidates/entry_risk/trade_events` 五类 predecision canonical SHA 的集合基数每月均为 `1`，共 `39 x 5` gate 全部通过。这里只验证决策前状态一致性，没有读取或比较候选收益优劣。

## 6. 351 行 development labels

独立从 355 个原始 `label.json` 按 `jobs.csv` 重建标签表，然后只保留 351 个 main jobs：

- 行数 `351`、job_id 唯一，集合和顺序均与 main jobs 一致。
- `job_type/eval_date/next_eval_date/product_vt_symbol/candidate_rank` 与 jobs 精确一致。
- 39 个日期及逐月 next date 精确符合冻结合同，rank 为 `10..18`。
- 原始 base/end equity、return、max drawdown、net PnL、slippage、trade count、trading days 均来自对应 job label。
- return delta、drawdown improvement、net PnL delta、slippage delta、trade count delta 均相对同月 rank10 独立重算。
- 在内存中按 aggregate 相同的稳定序列化规则生成 CSV，结果与当前 `development_labels.csv` 逐字节相同，SHA256 同为 `39e969...bce2`。
- 使用标准库 `csv+float` 和 pandas `float_precision=round_trip` 再读，所有原始及派生数值与独立重算最大差为 `0`。
- 没有 A2 行、sealed holdout 行或非 development job。

首次用 pandas 默认 C 浮点解析器读取时曾产生 `1.862645149230957e-09` 的读入 ULP；标准库与 round-trip 解析均为 `0`，且最终 CSV 可字节级重建，因此这是 reviewer 解析器假阳性，不是文件或会计误差。

## 7. 逐 job 会计与 reconciliation

对全部 355 个 job，独立读取原始 `label.json/curve.csv/combined.csv/trades.csv` 并重算：

- `end_equity - base_equity - future_net_pnl`
- target curve 的 net PnL、slippage、trade count
- target combined 的 net PnL、slippage、trade count
- target trades 行数与 future trade count

355 个 job 的上述八项最大绝对误差为 `0.0`，与 worker receipt 的最大差也为 `0.0`。355 份 receipt 的 monetary quantum 均为 `0.000001`；金额恒等式按 `Decimal(str(float(value))).quantize(Decimal("0.000001"))` 重算。

对 351 个 main jobs，再以每月 rank10 为 baseline 独立重算：

- base/end equity delta
- net PnL delta
- return delta 与 `end_equity_delta/base_equity` 恒等式
- drawdown improvement
- slippage delta
- trade count delta
- 七项 target curve/combined/trades reconciliation

结果：

- reconciliation rows：`351`
- 所有 `_error` 列最大绝对值：`0.0`
- `base_equity_delta` 最大绝对值：`0.0`
- 全部值均满足 `<=1e-9`
- 在内存中重建的 `reconciliation.csv` 与当前文件逐字节相同，SHA256 同为 `d59554...eb95`

本审查只读取完成上述恒等式所需的会计字段；没有生成分布、分位数、均值、胜率、rank 收益比较、最佳月份/品种或任何择优结果。

## 8. 最终发布身份与 active 指针

- 三份 campaign identity 字节一致，证明 aggregate 前、aggregate 后和 publish 前的冻结输入完全稳定。
- `development_labels.csv` 和 `reconciliation.csv` 均由当前原始 artifacts 独立字节级重建；本 review 将其 SHA 固定为 Stage016 输入锚点。
- 当前 `decision.json` campaign/contract 正确；11 项 gate 按独立结果重建后全部为 true，并与 decision gate map 一致。
- `progress.json` 和 `LATEST.json` 字节一致，均绑定当前 campaign id/path/contract，状态 `complete`、completed `355/355`。
- Stage016 若观察到 labels SHA、reconciliation SHA、campaign contract、runner SHA 或任一 campaign identity 变化，必须停止并重新评审，不得沿用本授权。

## 9. holdout、训练与交易边界

- jobs 中 sealed holdout 为 `0`；outputs 与 jobs 集合精确一致；development labels 中 sealed holdout 为 `0`。
- 没有读取 sealed holdout label 值或收益。
- campaign 内没有 pickle/joblib/model/UBJ/BST 等训练模型文件。
- runner 静态扫描未发现 `fit/train_model/xgboost.train/send_order/cancel_order/connect` 调用。
- decision 为 `trains_model=false`、sealed holdout label count `0`、order/send/cancel API count 均 `0`、CTP disconnected。

## 10. 测试与最终复核

独立运行：

```text
Stage015 tests: 30 passed in 17.29s
整线 tests:     98 passed in 17.29s
production _validate_completed_job 跨时间样本: 4/4 true
production _shared_builder_receipt_gate: 355/355 true
```

测试使用 `.py311/bin/python`、`PYTHONDONTWRITEBYTECODE=1`、`PYTHONNOUSERSITE=1`、`-p no:cacheprovider` 和独立 `/private/tmp` MPL/TMP。测试后再次验证：runner/tests/三份 identity/final labels/reconciliation/decision/progress/LATEST 哈希不变；2235 项 manifest drift `0`；共享源七项身份不变；仍为 355 个 output、空 `.partial/`、无 failure/ABANDONED。

## 过拟合与继续价值

- 过拟合判断：`否`。本轮只验证标签生产的冻结身份、隔离、A/A、决策前一致性和会计恒等式；没有查看标签收益分布、比较候选优劣、筛选月份/品种或修改参数。本结论不能证明标签具有预测力。
- 继续价值判断：`有`。Stage015 已形成完整、可复验、未触碰 holdout 的 frozen development label 集，可进入预注册 Stage016 训练以检验模型是否能在不泄漏条件下学习稳定关系。下一阶段必须固定本 review 的两个发布 SHA，并继续把 development 拟合、模型选择和 sealed holdout 最终检验分开。
