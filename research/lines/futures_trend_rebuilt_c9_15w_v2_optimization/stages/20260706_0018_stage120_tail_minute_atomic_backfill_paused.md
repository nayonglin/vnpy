# Stage120 tail minute atomic backfill paused

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-06T00:18
- 阶段性质：按用户要求暂停目标；中断 Stage120 真实下载；不回测收益、不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考：TqSdk TqBacktest/get_kline_serial 文档、vn.py BarData 语义。
- 我的判断：Stage120 只是补齐 2026 尾部非 jd 分钟数据的准入步骤，不代表策略收益提升；由于用户要求明天先验收当前结果，本阶段暂停，不形成有效补数结果。

## 本次状态

- Stage120 dry-run 已完成，计划补 6 个非 jd tail minute files：
  - `cu2607.SHFE`
  - `au2608.SHFE`
  - `lh2609.DCE`
  - `SM609.CZCE`
  - `SH609.CZCE`
  - `cu2608.SHFE`
- Stage120 真实下载已启动但按用户要求中断，退出码 `130`。
- 中断发生在 `run_backfill_download` 阶段，尚未进入 Stage112 strict audit / publish 阶段。
- 回测可发现 final 目录没有发布这 6 个 tail 文件。
- tmp 中 5 个临时文件已移入 interrupted quarantine：
  - `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/quarantine_interrupted/20260706_001722/`
- `cu2608.SHFE` 在中断前未形成临时文件。

## 当前有效数据门槛

- Stage119 后 jd 分钟缺口已归零。
- 最新有效 Stage112 仍是 `20260705_2356_stage112_strict_minute_content_gate.md`：
  - `manifest_contract_count=39`
  - `minute_file_ready_count=33`
  - `strict_ready_count=33`
  - `minute_missing_count=6`
  - `strict_failed_count=0`
  - `remaining_jd_not_ready_count=0`
  - `jd_margin_history_ready=False`
  - `ready_for_true_ledger_replay=False`

## 回测记录字段

- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率。

## 过拟合反思

- 运行前：否。Stage120 只处理数据准入，不看收益曲线、不调策略参数。
- 运行后：否。中断后没有形成策略绩效结果，也没有发布新数据进入可发现目录。

## 继续价值反思

- 运行前：有。6 个 tail minute files 与 jd 保证金仍阻塞 Stage208 true ledger。
- 运行后：有，但按用户要求暂停。明天验收后，如果继续，应优先决定是否恢复 Stage120 真实补数；恢复前应从 clean tmp 状态重跑，不直接消费 interrupted quarantine 文件。

## TODO

- 明天验收当前结果。
- 若恢复目标，先从 Stage120 dry-run 记录确认 6 个计划合约，再决定是否重新跑真实下载。
- 在 `minute_missing_count=0` 且 `jd_margin_history_ready=True` 前，不跑 Stage208 true ledger。
