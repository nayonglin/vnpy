# Stage015 original guard 新 campaign 4-job smoke 独立评审

## 结论先行

- 结论：`ALLOW_FULL_DEVELOPMENT_BATCH`
- 严重度：`P0=0`、`P1=0`、`P2=0`
- 当前 campaign 的冻结 4-job smoke 通过独立文件重算、生产 validator 和 Stage015 测试。未发现共享 builder 写入、跨 campaign 复用、输出/receipt 脱绑、会计误差、holdout 标签读取或训练/交易接口活动。
- 授权边界只覆盖本 campaign 按冻结合同继续完成 `351` 个 development main jobs 和 `4` 个 A2 sentinels；不代表标签有预测价值，不授权修改合同、读取 sealed holdout、训练模型、连接 CTP 或调用订单 API。

## 审查对象与不可变身份

- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- line_id：`futures_trend_ai_xgboost_ensemble`
- campaign：`campaign_20260902T021241+0800_98656`
- campaign 路径：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_ai_xgboost_ensemble/artifacts/stage015_development_label_batch/campaign_20260902T021241+0800_98656`
- campaign file contract：`ac8e5a6e77b081eaad97bcc30ef89769d6586eecd1b079ccef713e8d3d8d5d4f`
- runner SHA256：`1033b573d3c9faf6f9630acf637649127c8731adaa639f4d66e65c84c51a1c92`
- tests SHA256：`b1bd4fdaa2f191bbb80874c7b6534b7062c66dacd6dcfe300139cb728f41d541`
- 前置代码复审 SHA256：`cdb124f2bbd6726239bec30dc844a4c2345ea50b75f3c497c66ec2042cbfc950`
- `campaign_identity.json` SHA256：`00ebd9b2ab86185a1be4f98b3c3001573e2adf89ef31055fa3441d49eae2a93f`
- `smoke_receipt.json` SHA256：`fa61a3b2a460abd425a78e56f9c2eee127e92bb8bcddc8be4eeab85be528488c`
- 审查期间未修改 runner、tests、campaign、artifacts、共享源或旧 review；唯一新增文件为本 review。

外部方法核对使用 Python 3.11 官方文档：`os.stat_result` 的 `st_dev/st_ino/st_size/st_mtime_ns/st_ctime_ns` 语义，以及 `hashlib.sha256` 文件摘要。判断是 inode 只能证明物理文件身份，必须与 size、纳秒时间和内容 SHA 一起核验：

- https://docs.python.org/3.11/library/os.html
- https://docs.python.org/3.11/library/hashlib.html

## P0

无。

## P1

无。

## P2

无。

## 1. campaign 从零准备与冻结网格

独立读取 `jobs.csv`、`eligibility_audit.csv`、351 个 eligibility 文件和 manifest，结果为：

- jobs 共 `355`，job_id 唯一；其中 main `351`、A2 sentinel `4`。
- main 覆盖 `39` 个 development 月，每月 rank 严格为 `10..18`；sealed holdout jobs 为 `0`。
- `eligibility/` 恰有 `351` 个 CSV，文件名集合与 main job 的 `eligibility_key` 完全一致。
- eligibility audit 恰有 `351` 行，`changed_target_rank10_only` 全部为真；ranking alignment 为 `351/351`、mismatch `0`。
- campaign identity 有 `2235` 个条目、`2234` 个唯一物理路径。独立对约 `406 MB` 当前文件逐一重算，missing `0`、size drift `0`、SHA drift `0`；按冻结算法重算 file contract 仍为 `ac8e...d4f`。
- manifest 明确收录 `product_universe`、`stage015_official_overrides`、`stage015_stage819_profile_overrides`、`stage015_stage819_profile_eligibility`。

从零与不复用证据：

- prepare 使用新 campaign 目录的 `mkdir(..., exist_ok=False)`；快照目标若预先存在会失败。
- `campaign_identity.json` 的 ctime_ns 为 `1788286377254575353`，早于最早 worker receipt 的 `1788286521636594285`。
- 四份 receipt 均为 `checkpoint_reused=false`、`completed_result_reused=false`。
- 四个 worker PID 分别为 `99684/99685/569/592`，锁文件 PID、日志 job_id 和完成回执一致；四份 wall 为 `55.178130/55.178556/55.643878/54.760459` 秒。
- 新 campaign 四个 job 的全部输出/receipt 与所有旧 campaign 对应文件的 dev+inode 交集为 `0`，没有 hardlink 复用证据。

## 2. 私有 universe/profile eligibility

当前共享源：

- universe：dev `16777232`、inode `422227924`、size `6272`、mtime_ns/ctime_ns `1788286367623480595`、SHA256 `72c5ca576bfe8aebe12da1e750d9eac980633a43ab9944479a77a7e824a71e34`。
- eligibility：dev `16777232`、inode `422227925`、size `51303`、mtime_ns/ctime_ns `1788286367631031389`、SHA256 `fa5fb5c1cfe06ace44dadc92bd2cc1a77bd4ee74beeab362234952950ca5bb3b`。

campaign 私有快照：

- `official_product_universe.csv` inode `527263648`，与共享 universe 不同；size/SHA 相同。
- `stage819_profile_eligibility.csv` inode `527263650`，与共享 eligibility 不同；size/SHA 相同。
- `official_overrides.json.product_universe_csv_path` 精确指向 campaign 私有 universe。
- profile overrides 的 product/eligibility 路径分别精确指向上述两个 campaign 私有文件。

因此两份快照不是共享源 hardlink，内容冻结一致，且两条 overrides 路径没有回指共享输出。

## 3. 仅有冻结 4-job smoke

`job_outputs/` 恰有：

1. `20220429_R10`
2. `20220429_R10_A2`
3. `20220531_R10`
4. `20220531_R12`

每个目录恰有固定八个输出和一份 worker receipt，没有额外文件。campaign 内不存在：

- partial payload：预建 `.partial/` 目录存在，但条目数为 `0`
- `failure_receipt.json`
- `ABANDONED.json`
- `development_labels.csv`
- pickle/joblib/model/UBJ/BST 等训练模型文件

## 4. smoke 十项 gate 独立重算

没有调用会写回 campaign 的 `_validate_smoke`；使用独立只读脚本按冻结 gate 定义重算，并核对 receipt。结果十项全为真，且与 `smoke_receipt.gates` 精确相等：

1. `four_smoke_jobs_complete_and_fixed_outputs=true`
2. `rank10_AA_outputs_exact=true`
3. `active_month_predecision_payloads_exact=true`
4. `active_month_boundary_nonempty_and_complete=true`
5. `curve_combined_trades_reconciliation_exact=true`
6. `normalized_runtime_exact=true`
7. `pid_tmp_mpl_isolation_exact=true`
8. `timeout_and_execution_identity=true`
9. `active_challenger_label_identifiable=true`
10. `development_labels_not_published=true`

重点证据：

- A/A 的 `combined/curve/entry_candidates/entry_risk/label/summary/trade_events/trades` 八个文件逐字节一致；八项 SHA gate 也全部为真。
- `20220531_R10/R12` 的 `curve/trades/entry_candidates/entry_risk/trade_events` 五类 predecision canonical SHA 分别一致；这是按冻结 gate 从两份已绑定 receipt 重新计算集合基数，不读取收益分布。
- 两份 `20220531` label 文件 SHA 不同，challenger label 可区分；没有输出或比较标签收益分布。
- 两份活跃月 entry boundary 均为 target rows `11`、nonnull signal `11`，target signal date 仅 `2022-05-31`；receipt 中全部 predecision signal dates 严格早于 eval date。
- 四个 job 的八项 reconciliation 均从 output CSV 和 label 会计字段独立重算为 `0.0`，与 receipt 精确一致。
- 货币恒等式使用 `Decimal` 和冻结 quantum `0.000001` 重算，四个 job 均为 `0.0`。
- 四份 normalized runtime SHA 均为 `8b37a9dbf8de6b7774d08be4729b4a197a258abdf018ccdc2f52ec7abf991028`。
- 原始 TMPDIR/MPLCONFIGDIR 各自四路唯一，均位于 `/private/tmp/vnpy-stage015-development-label-batch/<campaign>/<job>/<run>/{tmp,mplconfig}`，与 receipt runtime environment 一致。
- 最大 wall 为 `55.643878 < 600` 秒。

四份 worker receipt 与 smoke receipt 的实际绑定：

- `20220429_R10` receipt SHA：`f77d41584e245a947f62a4605ac113f505fdacb70d3b09a36ed2ef53f2921f51`
- `20220429_R10_A2` receipt SHA：`77753990b0fa4066244b2478c1fa7224febee2c0e6265909bb965c5a76dd957a`
- `20220531_R10` receipt SHA：`bea525977d6db22b16aa7ec773a0bee27f20b7466e283381b34dbf80e78a1ced`
- `20220531_R12` receipt SHA：`5f5d2f2e728ca4224e250fbb87a139370f37d1baba2984ff4e494d3b988f3721`

四份 receipt SHA 和各自八个 output SHA 均与 smoke binding 及当前文件重算一致；campaign id/path/contract 与 jobs 行也全部一致。

## 5. original guard 与共享源不写

四份 worker receipt 独立检查结果完全一致：

- required bindings 精确为冻结六项，顺序一致。
- total/universe/eligibility binding counts 为 `6/3/3`，binding list 长度为 `6`。
- universe/eligibility redirect calls 为 `2/2`。
- original universe/eligibility/total calls 为 `0/0/0`。
- `nested_shared_builder_guard_enabled=true`。
- `original_shared_builder_guard_installed=true`。
- required binding coverage 和 source identity pass 均为 true。
- dynamic binding restore count 为非负值，当前四份均为 `0`。

每份 receipt 的 universe/eligibility before 与 after 都包含且只包含 path、dev、inode、size、mtime_ns、ctime_ns、SHA256 七项；before==after，并且精确等于本次审查时的当前共享源身份。四份 worker 均未触发 original builder，证明 smoke 期间没有共享源写入。

## 6. execution identity 与生产 validator

独立从 `campaign_identity.json` 按 worker exact-key/prefix/本 job eligibility 规则重建四份 execution manifest：

- 每份 `execution_unique_physical_file_count=1869`。
- 四份重算 execution contract 均与各自 receipt 一致；R10/A2 因复用同一冻结 eligibility，contract 相同，R10/R12 challenger 则各自绑定对应 eligibility。
- 四个 output 目录的固定文件集合、当前 SHA、receipt output map、smoke output binding 四层一致。

随后直接调用生产 `_validate_completed_job` 做只读验证，四个 job 均返回 `true`。

## 7. active 指针、旧 campaign 与安全边界

- `LATEST.json` 精确绑定当前 campaign id/path/contract，状态 `smoke_passed`、completed `4/355`；SHA256 为 `3794b506194af3984989d67575f5cf027125ab072655476adf03598dde590622`。
- 当前 `smoke_receipt.json` 精确绑定当前 campaign、合同和固定四 job，`passed=true`，decision 为 `stage015_smoke_pass_allow_full_development_batch`。
- 四个旧 campaign 经当前 `_campaign_reuse_forbidden` 规则独立重算均为禁止复用；最近旧 campaign `campaign_20260902T003958+0800_80965/ABANDONED.json` 仍在，SHA256 为 `52c9fce25bc271d70c7920e28b640e42fababb82352100c83936901c8b302cbb`，`reuse_forbidden=true`。
- smoke receipt 为 `trains_model=false`、`publishes_training_labels=false`、sealed holdout label count `0`、order API count `0`、CTP disconnected。runner 静态扫描未发现 `fit/train_model/send_order/cancel_order/connect` 调用，campaign 也无模型文件。
- 本审查只读取四个 smoke label 的必要会计字段以验证八项 reconciliation；没有读取其他 development label，更没有分析部分标签的收益分布。

## 8. 测试与运行后复核

独立运行：

```text
Stage015: 30 passed in 21.00s
production _validate_completed_job: 4/4 true
```

测试使用 `.py311/bin/python`、`PYTHONDONTWRITEBYTECODE=1`、`PYTHONNOUSERSITE=1`、`-p no:cacheprovider` 和 `/private/tmp` MPL/TMP；没有触发真实 shared builder。测试及 probe 后 runner、campaign contract、smoke receipt、LATEST、旧 ABANDONED 和两份共享源七项身份均保持不变。

## 过拟合与继续价值

- 过拟合判断：`否`。本次只审核冻结执行身份、隔离、确定性、边界和会计闭环，没有调参数、挑月份/品种、查看标签收益分布或训练模型。A/A 和 active predecision 检查验证的是实验基础设施，不是 alpha。
- 继续价值判断：`有`。4-job smoke 已证明当前 runner/campaign 能在原始 builder guard 下稳定、隔离地产出可辨识 development label。继续完成冻结 `351+4` batch 有价值，因为它产生后续预注册研究所需的完整 development 数据；在完整 batch、aggregate 和独立评审前，不得对模型有效性、泛化或实盘价值下结论。
