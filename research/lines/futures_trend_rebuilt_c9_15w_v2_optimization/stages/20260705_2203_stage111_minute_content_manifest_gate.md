# Stage111 minute content manifest gate

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T22:03:06
- 阶段性质：只读数据内容验收；不下载、不回测收益、不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考：TqSdk market data、TqBacktest、`get_kline_serial` 官方文档。
- 我的判断：文件存在不是足够证据；真账本前必须有机器可验内容 manifest。该阶段仍不是策略优化。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage111_minute_content_manifest_gate.py`
- 新增参数：无。
- 修改参数：无正式策略参数修改。
- 删除参数：无。

## 结果

- decision：`stage111_minute_content_ready_for_existing_files_margin_or_missing_files_blocked`
- manifest_contract_count：`39`
- minute_file_ready_count：`17`
- content_strict_ready_count：`17`
- minute_missing_count：`22`
- content_failed_count：`0`
- remaining_jd_content_or_file_missing：`16`
- jd_margin_history_ready：`False`
- ready_for_true_ledger_replay：`False`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Summary

| product_vt_symbol   |   contract_count |   minute_file_ready |   content_basic_ready |   content_strict_ready |   missing_file_count |   failed_content_count |
|:--------------------|-----------------:|--------------------:|----------------------:|-----------------------:|---------------------:|-----------------------:|
| SH.CZCE             |                1 |                   0 |                     0 |                      0 |                    1 |                      0 |
| SM.CZCE             |                1 |                   0 |                     0 |                      0 |                    1 |                      0 |
| au.SHFE             |                1 |                   0 |                     0 |                      0 |                    1 |                      0 |
| cu.SHFE             |                2 |                   0 |                     0 |                      0 |                    2 |                      0 |
| jd.DCE              |               33 |                  17 |                    17 |                     17 |                   16 |                      0 |
| lh.DCE              |                1 |                   0 |                     0 |                      0 |                    1 |                      0 |

## Content Failures

_无记录_

## Missing Files

| contract_vt   | product_vt_symbol   | priority                 | request_start_date   | request_end_date   |
|:--------------|:--------------------|:-------------------------|:---------------------|:-------------------|
| jd2005.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2020-01-02           | 2020-04-08         |
| jd2009.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2020-06-15           | 2020-08-18         |
| jd2101.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2020-10-22           | 2020-12-08         |
| jd2105.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2020-12-09           | 2021-04-14         |
| jd2109.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2021-04-15           | 2021-08-18         |
| jd2201.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2021-08-19           | 2021-12-10         |
| jd2205.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2021-12-13           | 2022-04-06         |
| jd2209.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2022-04-07           | 2022-08-12         |
| jd2301.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2022-08-15           | 2022-12-13         |
| jd2305.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2022-12-14           | 2023-04-13         |
| jd2309.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2023-04-14           | 2023-08-14         |
| jd2401.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2023-10-13           | 2023-12-14         |
| jd2405.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2024-02-21           | 2024-04-09         |
| jd2409.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2024-04-10           | 2024-08-21         |
| jd2501.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2024-09-09           | 2024-12-13         |
| jd2505.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2025-01-15           | 2025-04-15         |
| SH609.CZCE    | SH.CZCE             | P1_tail_contract_gap     | 2026-06-17           | 2026-06-30         |
| SM609.CZCE    | SM.CZCE             | P1_tail_contract_gap     | 2026-06-04           | 2026-06-30         |
| au2608.SHFE   | au.SHFE             | P1_tail_contract_gap     | 2026-05-26           | 2026-06-30         |
| cu2607.SHFE   | cu.SHFE             | P1_tail_contract_gap     | 2026-05-22           | 2026-06-23         |
| cu2608.SHFE   | cu.SHFE             | P1_tail_contract_gap     | 2026-06-24           | 2026-06-30         |
| lh2609.DCE    | lh.DCE              | P1_tail_contract_gap     | 2026-06-02           | 2026-06-30         |

## 回测记录字段

- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率。

## 过拟合反思

- 运行前：否。本阶段只做分钟数据内容验收，不看收益、不调参数、不筛策略结果。
- 运行后：否。结论来自数据完整性和保证金阻塞，不来自绩效表现。

## 继续价值反思

- 运行前：有。Stage110 已补 6 个 jd 文件，但独立评估要求机器可验 manifest 才能继续。
- 运行后：有。若现有文件内容验收通过，可继续补剩余分钟缺口；但 jd 逐日保证金未 ready 前仍不能 true ledger replay。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage111_minute_content_manifest_gate/rebuilt_c9_v2_stage111_minute_content_manifest_gate_report_stage111_minute_content_manifest_gate_v1.md`
- content_manifest：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage111_minute_content_manifest_gate/rebuilt_c9_v2_stage111_minute_content_manifest_gate_content_manifest_stage111_minute_content_manifest_gate_v1.csv`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage111_minute_content_manifest_gate/rebuilt_c9_v2_stage111_minute_content_manifest_gate_summary_stage111_minute_content_manifest_gate_v1.csv`
- input_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage111_minute_content_manifest_gate/rebuilt_c9_v2_stage111_minute_content_manifest_gate_input_audit_stage111_minute_content_manifest_gate_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage111_minute_content_manifest_gate/rebuilt_c9_v2_stage111_minute_content_manifest_gate_decision_stage111_minute_content_manifest_gate_v1.json`

## 独立 Agent 评估

- 评估 agent：Dewey（`019f3297-f5c1-73e0-b4df-8bd3c0720030`）
- 置信度：`0.93`
- 结论：Stage111 是数据内容验收 gate，不是策略回测；未发现下载数据、连接 CTP、调用订单/邮件、改策略或跑 true engine 的行为。`ready_for_true_ledger_replay=false` 的结论成立，阻塞仍是剩余分钟缺口和 `jd_contract_daily_margin_history` 未 ready。
- 高风险 bug：未发现。
- 复算一致项：
  - `manifest_contract_count=39`，`minute_file_ready_count=17`，`content_strict_ready_count=17`，`minute_missing_count=22`，`content_failed_count=0`，`remaining_jd_content_or_file_missing=16`，`jd_margin_history_ready=false`，`ready_for_true_ledger_replay=false`。
  - 17 个 ready jd 文件 `sha256` 不匹配数 `0`，OHLC 空值 `0`，重复键 `0`，OHLC 高低关系异常 `0`，行数不匹配 `0`，每日非 `225` 行的文件数 `0`，时间窗越界 `0`，首尾日期不等于 request_start/request_end 的文件数 `0`。
  - Stage050 manifest 为 `39` 个缺口：`jd.DCE` P0 合约 `33` 个，非 jd P1 tail 合约 `6` 个；Stage111 将非 jd 缺失计入 missing，但没有误判为 content failure。
  - Stage091 显示 `accepted_route_count=0` 且 `ready_for_true_ledger_replay=false`，保证金硬阻塞成立。
- 中风险/潜在风险：
  - `monotonic_datetime` 被计算但未进入 `content_basic_ready` 判定；当前 17 个文件全为 monotonic，不影响本次结论，但未来乱序文件可能 false pass。
  - `within_request_window` 只按首尾日期包含判断，不强制首日/末日精确相等、每个交易日 `225` 行、或 session minute 集合完整。当前复算这些都通过，但脚本口径偏宽。
  - `volume_null_count`、`oi_null_count`、`negative_oi_count` 没纳入 ready 硬门槛；当前 ready 文件这些计数均为 `0`，但若 true ledger 依赖 OI，应补成硬 gate。
  - Stage052 的 `build_minute_file_index()` 扫描整个 `downloaded_futures`；本次 39 个 manifest 合约无冲突，但全仓同名分钟文件冲突很多，后续最好限制索引来源或遇到多源同名直接 fail。
- 建议：不要进入 Stage208 true ledger replay。先补齐剩余 `16` 个 jd P0 分钟文件，同时解决 jd 逐日保证金历史；非 jd P1 缺口是否阻塞 true ledger，后续需要明确拆成 P0/P1 readiness。
- 下一版 gate TODO：把 `monotonic_datetime`、`unique_trade_dates == observed_price_rows`、每日 `225` 行、volume/OI 非空与非负、精确 session minute 校验纳入 strict ready，并把分钟索引限制到预期 backfill root 或遇到多源同名直接 fail。
- 独立评估过拟合反思：否。全程只验数据完整性，不看收益、不调参数。
- 独立评估继续价值反思：有，但下一步价值在补齐剩余 jd 分钟线和 jd 逐日保证金，不在救参。
