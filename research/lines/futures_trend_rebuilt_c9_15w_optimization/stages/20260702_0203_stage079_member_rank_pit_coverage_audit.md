# Stage079 国内会员持仓排名 PIT 覆盖审计

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：day
- 记录时间：2026-07-02 02:03:02 CST
- 阶段性质：只读外生源覆盖审计，不改线上、不改 AI 池、不接 CTP/SimNow。
- 是否重要突破：否。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：CFTC COT 报告说明持仓报告按周发布并存在报告门槛和分类限制；CME OI 教程说明 OI/持仓变化可以反映资金进入或退出；pysystemtrade 作为开源系统化交易框架强调可复验输入和成本/风险纪律。
- 我的判断：会员持仓/排名在经济含义上可能有价值，但必须先证明点时可用和关键左尾覆盖；当前阶段只审覆盖，不写规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage079_member_rank_pit_coverage_audit.py`。
- 新增测试：`tests/test_rebuilt_c9_stage079_member_rank_pit_coverage_audit.py`。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：`MAX_MEMBER_RANK_AGE_DAYS=7`、`MIN_LEFT_TAIL_ENTRY_COVERAGE_PCT=50.0`、`MIN_LEFT_TAIL_LOSS_COVERAGE_PCT=50.0`。
- 修改参数：无正式交易参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage038 候选 `2020-01-02` 到 `2026-06-24`；Stage071 剩余左尾窗口 `2021-11-01` 到 `2023-10-18`；会员排名源 `2023-01-03` 到 `2026-04-17`。
- 账户规模：不适用，本阶段无资金曲线回测。
- 成本口径：不适用，本阶段无交易回放。
- 样本过滤：会员排名 `T+1` 可见，最大旧值 7 天；同日/未来数据禁止匹配。
- 策略/归因口径：Stage038 全候选 + Stage071 剩余左尾 entries 的 PIT 覆盖审计。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 决策：`stage079_member_rank_not_history_selector_missing_left_tail`。
- Stage038 全样本覆盖：`1251/2787` = `44.8870%`。
- Stage071 左尾窗口覆盖：`652/1314` = `49.6195%`。
- Stage071 左尾亏损金额覆盖：`1042730.00/10154100.00` = `10.2691%`。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage079_member_rank_pit_coverage_audit/rebuilt_c9_stage079_member_rank_pit_coverage_audit_report_stage079_member_rank_pit_coverage_audit_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage079_member_rank_pit_coverage_audit/rebuilt_c9_stage079_member_rank_pit_coverage_audit_decision_stage079_member_rank_pit_coverage_audit_v1.json`
- daily/features：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage079_member_rank_pit_coverage_audit/rebuilt_c9_stage079_member_rank_pit_coverage_audit_member_features_stage079_member_rank_pit_coverage_audit_v1.csv`
- joined：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage079_member_rank_pit_coverage_audit/rebuilt_c9_stage079_member_rank_pit_coverage_audit_joined_feature_matrix_stage079_member_rank_pit_coverage_audit_v1.csv`、`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage079_member_rank_pit_coverage_audit/rebuilt_c9_stage079_member_rank_pit_coverage_audit_joined_window_entries_stage079_member_rank_pit_coverage_audit_v1.csv`
- coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage079_member_rank_pit_coverage_audit/rebuilt_c9_stage079_member_rank_pit_coverage_audit_year_coverage_stage079_member_rank_pit_coverage_audit_v1.csv`、`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage079_member_rank_pit_coverage_audit/rebuilt_c9_stage079_member_rank_pit_coverage_audit_product_coverage_stage079_member_rank_pit_coverage_audit_v1.csv`

## 年度覆盖

| sample             |   entry_year |   entry_count |   available_count |   coverage_pct |      realized_pnl |   covered_realized_pnl |
|:-------------------|-------------:|--------------:|------------------:|---------------:|------------------:|-----------------------:|
| stage038_all       |         2020 |           336 |                 0 |         0      |       1.87376e+06 |            0           |
| stage038_all       |         2021 |           394 |                 0 |         0      |       1.72585e+07 |            0           |
| stage038_all       |         2022 |           390 |                 0 |         0      |       2.87089e+06 |            0           |
| stage038_all       |         2023 |           390 |               334 |        85.641  | -384970           |           -3.08269e+06 |
| stage038_all       |         2024 |           532 |               421 |        79.1353 |       2.7571e+07  |            2.10575e+07 |
| stage038_all       |         2025 |           483 |               315 |        65.2174 |       2.09065e+07 |           -2.17633e+06 |
| stage038_all       |         2026 |           262 |               181 |        69.084  |      -7.25196e+06 |           -2.14588e+06 |
| stage071_left_tail |         2021 |            65 |                 0 |         0      | -183950           |            0           |
| stage071_left_tail |         2022 |           620 |                 0 |         0      |      -5.4353e+06  |            0           |
| stage071_left_tail |         2023 |           694 |               652 |        93.9481 | -822100           |      -659800           |

## 覆盖最低品种

| sample             | product   |   entry_count |   available_count |   coverage_pct | first_entry_date   | last_entry_date   |
|:-------------------|:----------|--------------:|------------------:|---------------:|:-------------------|:------------------|
| stage038_all       | jm.DCE    |           212 |                 0 |         0      | 2020-01-10         | 2026-06-03        |
| stage038_all       | lh.DCE    |           141 |                 0 |         0      | 2021-04-12         | 2025-08-13        |
| stage038_all       | lc.GFEX   |            87 |                 0 |         0      | 2023-11-07         | 2025-12-18        |
| stage038_all       | si.GFEX   |            69 |                 0 |         0      | 2023-08-24         | 2025-07-10        |
| stage038_all       | hc.SHFE   |           114 |                24 |        21.0526 | 2020-03-16         | 2023-07-24        |
| stage038_all       | sp.SHFE   |           106 |                25 |        23.5849 | 2020-01-14         | 2025-11-12        |
| stage038_all       | au.SHFE   |            92 |                27 |        29.3478 | 2020-02-06         | 2025-09-02        |
| stage038_all       | OI.CZCE   |           124 |                40 |        32.2581 | 2020-05-18         | 2026-06-02        |
| stage038_all       | CF.CZCE   |           101 |                36 |        35.6436 | 2020-01-02         | 2024-01-19        |
| stage038_all       | rb.SHFE   |           120 |                50 |        41.6667 | 2020-01-09         | 2026-01-14        |
| stage038_all       | SM.CZCE   |           169 |                71 |        42.0118 | 2020-07-17         | 2026-03-06        |
| stage038_all       | SA.CZCE   |           110 |                55 |        50      | 2020-07-20         | 2025-07-22        |
| stage038_all       | MA.CZCE   |           231 |               120 |        51.9481 | 2020-07-02         | 2026-06-11        |
| stage038_all       | FG.CZCE   |           161 |                96 |        59.6273 | 2020-02-19         | 2026-06-24        |
| stage038_all       | cu.SHFE   |           156 |               103 |        66.0256 | 2020-06-03         | 2025-06-10        |
| stage038_all       | AP.CZCE   |           153 |               103 |        67.3203 | 2020-04-27         | 2026-02-13        |
| stage038_all       | ru.SHFE   |           191 |               141 |        73.822  | 2020-01-13         | 2026-01-27        |
| stage038_all       | fu.SHFE   |           357 |               284 |        79.5518 | 2022-02-25         | 2026-01-20        |
| stage038_all       | SH.CZCE   |            93 |                76 |        81.7204 | 2024-03-26         | 2026-04-30        |
| stage071_left_tail | jm.DCE    |            98 |                 0 |         0      | 2021-11-15         | 2023-02-24        |

## 结论

- 本阶段结论：`stage079_member_rank_not_history_selector_missing_left_tail`；国内会员排名源缺 2022 左尾，不能作为当前历史目标的选择器，只能保留 forward monitor 或后续补历史后再审。
- 是否进入下一步：不进入规则/proxy/真引擎。
- 下一步：寻找覆盖 2022-2023 左尾的新 PIT 信息源，或者把会员排名只作为 2023 以后 forward 观察，不用它修当前目标。

## 过拟合反思

- 运行前判断：否；只做覆盖审计，不用坏窗口回推阈值。
- 运行后判断：若基于覆盖不足的会员排名继续挖历史规则，就是过拟合。
- 原因：关键亏损期缺数据，任何后验阈值都无法证明当时可用。

## 继续价值反思

- 运行前判断：有；Stage078 后需要验证新 PIT 源。
- 运行后判断：会员排名对当前目标继续价值低，但可保留 forward monitor。
- 原因：它的源从 2023-01-03 才开始，关键 2022 左尾覆盖不足。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage079 关闭该历史选择器方向。
- 是否更新 `research/registry.md`：是，最新关键阶段推进到 Stage079。
- 是否追加根目录 `memory.md/back_log.md`：仅追加 `back_log.md` 重要摘要，不改 `memory.md`。
