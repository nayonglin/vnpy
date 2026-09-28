# Stage005 campaign post-run independent review

- 审计日期：2026-09-03
- 研究线：`futures_trend_xgboost_pit_curve_account_labels`
- campaign：`campaign_20260902T214308+0800_13888`
- campaign 目录：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_xgboost_pit_curve_account_labels/artifacts/stage005_development_label_batch/campaigns/campaign_20260902T214308+0800_13888`
- 审计性质：独立、只读 post-run 评审
- 审计边界：未运行 `--validate-only`、`--run-batch` 或 worker，未创建 attempt/campaign，未训练模型，未读取或生成 holdout 标签，未连接 CTP，未调用 order；只读取现有代码、元数据和 campaign 产物，并运行 `python -B` 只读核验脚本。

## 结论

**ALLOW_STAGE006_TRAINING_PREREGISTRATION_ONLY**

P0/P1/P2 均为 0，campaign 的生命周期、任务全集、证据哈希、量化对账、进程隔离、执行作用域、身份冻结、授权消费和最终收据链相互自洽。存在 1 个非阻断 P3：`research/registry.md` 尚保留 Stage005 批次未运行的前置描述，与本 campaign 已完成的事实不同；受本次只写两个 review 文件的约束，本评审不修改该文件。

本放行仅允许编写 Stage006 训练方案预注册，并对该预注册进行独立预审。它不允许训练模型，不允许解封、读取或生成 holdout 标签，不证明收益提升、样本外有效性或可上线性，也不允许实盘、CTP 连接或下单。任何 Stage006 训练仍需另行冻结方案、限定 development-only 输入并取得新的明确授权。

## Findings

- P0：0
- P1：0
- P2：0
- P3：1

### P3-1 研究线注册表状态滞后

`research/registry.md` 当前仍称该研究线的 Stage005 “开发批次/模型尚未运行”，而指定 campaign 已有 complete 生命周期和最终 decision。该问题不破坏 campaign 内部证据链，也不阻断 Stage006 训练方案预注册，但后续合入者应在不违反并行研究写入规则的前提下同步研究线状态，避免后续审阅者误判当前阶段。

## Fresh 独立核验

### 1. Lifecycle 与最终 decision

- `progress.json`：`status=complete`、`completed_jobs=270`、`total_jobs=270`，decision 为 `stage005_development_account_labels_complete_allow_stage006_training_preregistration`。
- `attempt_audit.json`：`passed=true`、`attempt_count=1`、`final_status=complete`；attempt sequence 唯一且连续，start/end 各恰好一个，post-failure 为 0。
- 独立读取 attempt receipts：start 的 pending 集合恰为全部 270 个 job、completed 为空；end 的 completed 集合恰为全部 270 个 job、pending 为空、`error=null`。270 条 worker command 与 jobs.csv 一一对应，命令 shape 无异常。
- `decision.json`：`passed=true`；14/14 gates 均为 `true`。其 SHA256 为 `1cffbfcf0872de9c2a0256071de95ca4a750a72b74025865a1beb8b18fe8a111`。

### 2. 任务全集、月份与 predecision

- `jobs.csv` 共 270 个唯一 job：266 个 main 加 4 个 A2 sentinel；main 全为 development split。
- development 月份集合为 35 个，标签汇总 `development_labels.csv` 为 266 行，job_id 与 266 个 main job 精确相等且唯一。
- `predecision_evidence_audit.json` 覆盖 35 个月，每月恰有 `curve`、`entry_candidates`、`entry_risk`、`trade_events`、`trades` 五类原始文件，共 `35 * 5 = 175` 个；独立复算文件 SHA256 与 receipts 的记录全部一致。

### 3. 四个 A2 sentinel exact

- A2 job 为 `20220128_R10_A2`、`20221230_R10_A2`、`20231229_R10_A2`、`20241129_R10_A2`。
- 每个 A2 与对应 main baseline 的七个规定文件均逐字节同 SHA256：`combined.csv`、`curve.csv`、`entry_candidates.csv`、`entry_risk.csv`、`label.json`、`trade_events.csv`、`trades.csv`。
- 独立复算结果为 4/4 audit 通过、28/28 文件 exact，未依赖 `A2_audit.json` 的布尔结论直接放行。

### 4. 1e-6 量化对账

- 对 266 个 main job，独立从现有 raw label、curve、combined 和 trades 证据重算 reconciliation。
- 采用冻结顺序 `quantize_each_operand_to_0.000001_then_add_subtract`，每个货币操作数先量化到 `0.000001` 再加减；所有逐操作 delta 均为 0，独立最大绝对误差为 0，最终 receipt 记录为 `0.0`，满足 `<= 1e-6`。
- 方法依据 Python 官方 `decimal` 对固定 exponent 的 `quantize()` 语义；SHA256 复算依据官方 `hashlib` 的 digest/hexdigest 语义。外部资料只用于核验方法，不替代本地 artifact 证据。

### 5. Worker 隔离与无结果复用

- 270 份 worker receipt 均存在；PID、`TMPDIR`、`MPLCONFIGDIR` 分别为 270/270/270 唯一，路径均绑定 campaign、job 和独立 run。
- `checkpoint_reused=false`、`completed_result_reused=false` 在 270 个 job 上全部成立；未发现 output hash、job identity、source identity 或 contract mismatch。
- normalized runtime SHA256 只有一个值：`abeb07901315d742a348f39baaede71877a8f746c6a5622cd0c8a33465baf6b9`。
- 重新以文件名末尾 attempt 序号反向解析日志，得到日志 270 个、未知 0、缺失 0、重复 0。此前按 job 前缀匹配会把四个 A2 名称误归到 main；修正为末尾切分后无异常，故不将解析器假阳性计入 finding。

### 6. Execution scope 与封存集隔离

- `execution_scope_audit.json` 的 13 个显式计数均为精确整数 0：CTP command/log、holdout job/label/output、model artifact、model training command/log、order command/log、unexpected artifact、unexpected worker command、unknown output job。
- 独立扫描 manifest、jobs、worker receipts、commands 和 logs：model artifact 0、holdout 路径命中 0、意外 artifact 0、缺失预期 artifact 0、危险日志关键词命中 0；worker command 为 270 条且 shape 全部合法。
- `decision.json` 明示 `trains_model=false`、`sealed_holdout_label_count=0`、`ctp_connected=false`、`order_api_called_count=0`。其中 `runs_backtest=true` 仅描述已完成 campaign 用反事实回测产生 development 标签；本 reviewer 没有重跑回测，也未把这些互斥反事实结果解释为可同时持有的组合收益。

### 7. 标签语义与无误聚合

- `development_labels.csv` 仅含 266 个 main job 的逐 job 标签；未发现 portfolio/strategy aggregate 列或聚合收益产物。
- job 类型、development split、job_id 集合与 `jobs.csv` 精确一致；互斥反事实标签保留为各自独立行，`mutually_exclusive_not_aggregated=true`。
- 因此，本结果只建立 development 标签生产完整性，不建立策略收益、模型预测能力、walk-forward/OOS 效果或 holdout 表现。

### 8. Identity、授权消费与 manifest/receipt 自洽

- `campaign_identity.json` 与 `campaign_identity_after.json` 完全相等；contract SHA256 为 `eb9fdfd95f27d85dfc98cc3dd6a86999efb60b3888e573ef133cba2e866cab18`，file-contract SHA256 为 `191c6e9b5487fefc5ad68304d4d034e150d36bb1b94e2598e33a0ce9ffcb45da`。
- 独立复算 2,195 个冻结输入绑定：缺失、大小错误和 SHA 错误均为 0。production HEAD 前后均为 `d492ee072aa5a9d71477235d79f17d2a5db59db3`，production/workspace runtime status 均未变化；runtime、input 和 source identity 前后一致。
- 授权 SHA256 为 `fe83c65963b94a645426794544c1e653bd060717cd4911cc4c71083446481132`；nonce 为 64 位小写十六进制 `8b88739e38da755af3c206f1ce5caaaf3bde7817b3d2e3f8852943fd293aed6b`；scope 为 `one_new_stage005_campaign_only`。25 个授权绑定文件独立复算无 mismatch。
- Stage005 artifact 根目录只发现这一个 campaign 目录和一份 consumption receipt；consumption 的 authorization SHA、nonce、scope、campaign_id 与授权及 campaign identity 精确一致，支持单次消费结论。
- `artifact_manifest.json` 声明 3,431 个文件，manifest entries 为 3,431，磁盘实际受管文件亦为 3,431；缺失、额外、size mismatch、SHA mismatch 均为 0。manifest SHA256 为 `526f945c2e7523b78076331a2473a606f6f8ce775a0a8ac7850dcd593a31eedf`。
- `latest`、`progress`、attempt end、decision、artifact manifest 与 authorization consumption 的 campaign_id、job 全集、contract 和最终状态一致，未发现最终零字段在 receipt 链中回归。

## 核验命令与限制

- 运行了 `.py311/bin/python -B -c ...` 的只读独立审计：复算 manifest/输入/授权/输出哈希、CSV 集合、attempt lifecycle、A2 exact、Decimal 对账、worker isolation、scope 和标签语义；未导入或调用 campaign orchestrator/worker 入口。
- 运行了只读日志关键词扫描及修正后的 270 日志一一映射检查。
- 未运行 pytest、`py_compile`、`--validate-only`、`--run-batch`、worker、训练、holdout、CTP 或 order。pytest/py_compile 不是本次 post-run 产物一致性结论的必要条件，且本评审不以旧测试结果冒充 fresh 证据。

## 过拟合与继续价值

- 过拟合：**否（就本评审动作而言）**。本次没有调参、训练、筛选模型或比较 holdout，只审计冻结 development 标签生产的完整性、隔离和会计恒等式。campaign 内部反事实回测也没有被聚合或宣称为策略收益。不过，Stage005 标签本身仍可能承载设计者先验，后续 Stage006 必须通过预注册、development-only 训练纪律及最终独立 holdout 评估控制研究者自由度。
- 是否值得继续：**是，但仅值得继续到 Stage006 训练方案预注册和独立预审**。270 个标签任务的证据链已足以支持设计下一阶段；尚无任何证据支持直接训练、解封 holdout、宣称收益提升、接入实盘或下单。
