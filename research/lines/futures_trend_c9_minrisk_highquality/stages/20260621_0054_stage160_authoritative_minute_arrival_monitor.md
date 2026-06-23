# Stage160 权威分钟数据到货监控

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-21 00:54`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：真实授权 1m OHLCV + real volume/OI 到货只读监控与触发闸门
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - GitHub `gorakhargosh/watchdog`：`https://github.com/gorakhargosh/watchdog`
  - watchdog API 文档：`https://python-watchdog.readthedocs.io/en/stable/api.html`
  - Databricks file-arrival triggers：`https://docs.databricks.com/gcp/en/jobs/file-arrival-triggers`
  - NCEI data integrity practices：`https://ioos.github.io/ncei-archiving-cookbook/practices.html`
- 我的判断：本阶段不应该直接做事件监听后台进程，也不应该自动触发策略。文件到货触发适合做“manifest/marker 驱动的轻量监控”：先只读比对 Stage152 expected raw/normalized/proof 三件套，输出可复跑快照和缺口；只有三件套全到齐且无意外文件时，才允许 operator 运行 Stage153 intake validator。NCEI 对 manifest + checksum 的实践也说明：到货监控只证明“文件出现”，不证明“数据有效”，有效性仍必须交给 Stage153 的 proof/schema/hash/window coverage。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage160_authoritative_minute_arrival_monitor.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增固定到货快照、role progress、exchange progress、product gap、trigger gate、operator action queue。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage045/Stage159 官方路径资金曲线作视觉跟踪；本阶段不运行新回测。
- 账户规模：沿用当前研究线官方路径口径。
- 成本口径：沿用 Stage159 官方路径总滑点口径。
- 样本过滤：无新增过滤；只读 Stage152 的 `233` 个 request 和 `699` 个 expected files。
- 策略/归因口径：data arrival monitor；不创建策略规则、不运行 true engine、不触发 A/B、不改变 official config、不连接 CTP、不调用 order API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - `decision=stage160_authoritative_minute_arrival_monitor_waits_real_data_no_rule`
  - `incoming_root_exists=0`
  - `stage152_request_count=233`
  - `expected_file_count=699`
  - `present_expected_file_count=0`
  - `missing_expected_file_count=699`
  - `arrival_completion_pct=0.0000%`
  - `raw_file_present_count=0/233`
  - `normalized_file_present_count=0/233`
  - `proof_file_present_count=0/233`
  - `request_complete_triplet_count=0/233`
  - `request_partial_triplet_count=0`
  - `request_missing_triplet_count=233`
  - `unexpected_file_count=0`
  - `observed_expected_bytes=0`
  - `stage153_trigger_allowed=0`
  - `readonly_feature_atlas_allowed_now=0`
  - `current_package_promotion_allowed=0`
  - `true_engine_allowed=0`
  - `strategy_feature_usable=0`
  - `objective_completion_proven=0`
  - `max_broker10_margin_to_equity_pct=111.7365%`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage160_authoritative_minute_arrival_monitor/qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_report_stage160_authoritative_minute_arrival_monitor_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage160_authoritative_minute_arrival_monitor/qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_summary_stage160_authoritative_minute_arrival_monitor_v1.csv`
- request snapshot：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage160_authoritative_minute_arrival_monitor/qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_request_arrival_snapshot_stage160_authoritative_minute_arrival_monitor_v1.csv`
- role progress：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage160_authoritative_minute_arrival_monitor/qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_role_progress_stage160_authoritative_minute_arrival_monitor_v1.csv`
- exchange progress：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage160_authoritative_minute_arrival_monitor/qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_exchange_progress_stage160_authoritative_minute_arrival_monitor_v1.csv`
- product gap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage160_authoritative_minute_arrival_monitor/qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_product_gap_stage160_authoritative_minute_arrival_monitor_v1.csv`
- trigger gate：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage160_authoritative_minute_arrival_monitor/qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_trigger_gate_status_stage160_authoritative_minute_arrival_monitor_v1.csv`
- operator queue：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage160_authoritative_minute_arrival_monitor/qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_operator_action_queue_stage160_authoritative_minute_arrival_monitor_v1.csv`
- unexpected inventory：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage160_authoritative_minute_arrival_monitor/qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_unexpected_file_inventory_stage160_authoritative_minute_arrival_monitor_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage160_authoritative_minute_arrival_monitor/qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_decision_stage160_authoritative_minute_arrival_monitor_v1.json`
- orders：无；本阶段禁止报单和 true engine。
- daily：无新增回测 daily；使用官方路径资金曲线图跟踪。
- quality：5 张 PNG 视觉产物均非空：
  - `qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_official_path_arrival_status_stage160_authoritative_minute_arrival_monitor_v1.png`
  - `qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_role_progress_bar_stage160_authoritative_minute_arrival_monitor_v1.png`
  - `qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_exchange_arrival_progress_stage160_authoritative_minute_arrival_monitor_v1.png`
  - `qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_product_missing_bar_stage160_authoritative_minute_arrival_monitor_v1.png`
  - `qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_trigger_gate_matrix_stage160_authoritative_minute_arrival_monitor_v1.png`

## 视觉分析

- 官方路径资金曲线只作为基线视觉跟踪；Stage160 不改变交易路径，也没有产生收益改善。
- role progress bar 显示 raw/normalized/proof 三类文件均为 `0/233`，不是某一类 proof 或 normalized 的局部缺口，而是完整授权包尚未到货。
- exchange progress 显示 `SHFE 100`、`CZCE 99`、`DCE 30`、`GFEX 4` 个 request 全部缺失；问题不是单交易所局部缺口。
- product missing bar 显示最大缺口集中在 `SM.CZCE`、`jm.DCE`、`au.SHFE` 等 request 较多的品种，但这只是采购覆盖排序，不是交易信号。
- trigger gate matrix 显示 `stage152_manifest_loaded=1`、`stage159_commands_safe=1`、`true_engine_allowed=0` 安全通过；`incoming_root_exists=0`、raw/normalized/proof/all triplets 全部未通过，所以 Stage153 不允许运行。

## 结论

- 本阶段结论：Stage160 将 Stage152 的 `233` 个 request / `699` 个 expected files 固定成可复跑到货监控；当前没有任何真实授权分钟文件，Stage153 trigger 仍为 `0`。
- 是否进入下一步：可以继续，但必须避免把缺数据状态变成策略研究。
- 下一步：真实数据到货后先重跑 Stage160；若 `request_complete_triplet_count=233/233` 且 `unexpected_file_count=0`，才运行 Stage153 intake validator，然后按 Stage159 runbook 继续 Stage156/157/158。

## 过拟合反思

- 运行前判断：否。Stage160 只做文件存在性和 manifest 对齐，不读取盈亏标签、不选择品种/年份、不调交易阈值。
- 运行后判断：否。结果仍停在 `arrival_completion_pct=0%`，没有任何历史样本被转成交易规则，也没有触发 true engine 或 A/B。
- 原因：本阶段证明的是数据工程状态，不是 alpha；所有缺口都是 expected file 层面的外部交付缺口。

## 继续价值反思

- 运行前判断：有，但应收敛。继续价值来自把真实数据到货后的触发条件透明化。
- 运行后判断：仍有价值，但下一步不能继续加厚 no-data 工程。Stage160 已能回答“文件是否到齐、哪个角色/交易所/品种缺口最大、是否允许 Stage153”；真实数据不到时，继续做策略层假设没有价值。
- 原因：当前瓶颈仍是授权分钟 OHLCV+volume+OI 的 raw/normalized/proof 三件套缺失。只有这个瓶颈解除后，分钟级高质量信号研究才有可审计基础。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage160 摘要。
- 是否更新 `research/registry.md`：否，未新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破、非正式候选、非路线废弃。
