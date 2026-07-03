# Stage080 国内会员持仓排名 2022 补数可行性审计

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：day
- 记录时间：2026-07-02 02:20:30 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读外生源补数可行性与覆盖审计，不改线上、不改 AI 池、不接 CTP/SimNow。
- 是否重要突破：否，除非后续信号审计证明有稳定 OOS 价值。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：AKShare 期货数据文档列出 `get_rank_sum_daily`、`get_rank_table_czce`、`get_shfe_rank_table`、`futures_dce_position_rank` 等接口；上期所、郑商所、大商所官网均有历史日排名/持仓数据入口。
- 我的判断：会员排名数据有可能重建 2022 非 DCE 左尾输入，但 DCE 当前接口仍不稳定；因此本阶段只补非 DCE 覆盖，不写交易规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage080_member_rank_2022_backfill_feasibility.py`。
- 新增测试：`tests/test_rebuilt_c9_stage080_member_rank_backfill_feasibility.py`。
- 修改脚本：无正式交易脚本修改。
- 删除脚本：无。
- 新增参数：`BACKFILL_START=2022-01-01`、`BACKFILL_END=2022-12-31`、`FETCH_CHUNK_DAYS=31`、`MIN_AFTER_LOSS_COVERAGE_PCT=80.0`。
- 修改参数：无正式交易参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：会员排名既有源 `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/external_domestic_member_rank_cache/member_rank_sum_daily_20230101_20260417.csv` + AKShare 非 DCE `2022-01-01` 到 `2022-12-31` 补数。
- 账户规模：不适用，本阶段无资金曲线回测。
- 成本口径：不适用，本阶段无交易回放。
- 样本过滤：Stage071 左尾窗口；会员排名 `T+1` 可见，最大旧值 `7` 天；DCE 先排除。
- 策略/归因口径：只比较补数前后 PIT 覆盖率和亏损金额覆盖率。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 决策：`stage080_member_rank_backfill_coverage_ready_for_signal_audit`。
- 抓取行数：`19792`。
- 合并后原始行数：`88649`。
- 补数前左尾亏损金额覆盖：`10.2691%`。
- 补数后左尾亏损金额覆盖：`86.9947%`。
- 覆盖提升：`76.7257pp`。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage080_member_rank_2022_backfill_feasibility/rebuilt_c9_stage080_member_rank_2022_backfill_feasibility_report_stage080_member_rank_2022_backfill_feasibility_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage080_member_rank_2022_backfill_feasibility/rebuilt_c9_stage080_member_rank_2022_backfill_feasibility_decision_stage080_member_rank_2022_backfill_feasibility_v1.json`
- fetched_raw：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage080_member_rank_2022_backfill_feasibility/rebuilt_c9_stage080_member_rank_2022_backfill_feasibility_fetched_raw_stage080_member_rank_2022_backfill_feasibility_v1.csv`
- combined_raw：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage080_member_rank_2022_backfill_feasibility/rebuilt_c9_stage080_member_rank_2022_backfill_feasibility_combined_raw_stage080_member_rank_2022_backfill_feasibility_v1.csv`
- combined_features：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage080_member_rank_2022_backfill_feasibility/rebuilt_c9_stage080_member_rank_2022_backfill_feasibility_combined_member_features_stage080_member_rank_2022_backfill_feasibility_v1.csv`
- joined：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage080_member_rank_2022_backfill_feasibility/rebuilt_c9_stage080_member_rank_2022_backfill_feasibility_before_joined_window_entries_stage080_member_rank_2022_backfill_feasibility_v1.csv`、`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage080_member_rank_2022_backfill_feasibility/rebuilt_c9_stage080_member_rank_2022_backfill_feasibility_after_joined_window_entries_stage080_member_rank_2022_backfill_feasibility_v1.csv`、`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage080_member_rank_2022_backfill_feasibility/rebuilt_c9_stage080_member_rank_2022_backfill_feasibility_after_joined_feature_matrix_stage080_member_rank_2022_backfill_feasibility_v1.csv`
- fetch_manifest：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage080_member_rank_2022_backfill_feasibility/rebuilt_c9_stage080_member_rank_2022_backfill_feasibility_fetch_manifest_stage080_member_rank_2022_backfill_feasibility_v1.csv`

## 年度覆盖对比

| sample   |   entry_year |   entry_count |   available_count |   coverage_pct |         loss_abs |   covered_loss_abs |
|:---------|-------------:|--------------:|------------------:|---------------:|-----------------:|-------------------:|
| after    |         2021 |            65 |                 0 |         0      | 322650           |        0           |
| before   |         2021 |            65 |                 0 |         0      | 322650           |        0           |
| after    |         2022 |           620 |               490 |        79.0323 |      8.94907e+06 |        7.7908e+06  |
| before   |         2022 |           620 |                 0 |         0      |      8.94907e+06 |        0           |
| after    |         2023 |           694 |               652 |        93.9481 |      1.20503e+06 |        1.04273e+06 |
| before   |         2023 |           694 |               652 |        93.9481 |      1.20503e+06 |        1.04273e+06 |

## 抓取状态

|   start_day |   end_day | products                               | status   |   rows | error   |
|------------:|----------:|:---------------------------------------|:---------|-------:|:--------|
|    20220101 |  20220131 | AP,AU,CF,CU,FG,FU,HC,MA,OI,RB,SA,SM,SP | ok       |   1356 |         |
|    20220201 |  20220303 | AP,AU,CF,CU,FG,FU,HC,MA,OI,RB,SA,SM,SP | ok       |   1456 |         |
|    20220304 |  20220403 | AP,AU,CF,CU,FG,FU,HC,MA,OI,RB,SA,SM,SP | ok       |   1763 |         |
|    20220404 |  20220504 | AP,AU,CF,CU,FG,FU,HC,MA,OI,RB,SA,SM,SP | ok       |   1484 |         |
|    20220505 |  20220604 | AP,AU,CF,CU,FG,FU,HC,MA,OI,RB,SA,SM,SP | ok       |   1640 |         |
|    20220605 |  20220705 | AP,AU,CF,CU,FG,FU,HC,MA,OI,RB,SA,SM,SP | ok       |   1730 |         |
|    20220706 |  20220805 | AP,AU,CF,CU,FG,FU,HC,MA,OI,RB,SA,SM,SP | ok       |   2009 |         |
|    20220806 |  20220905 | AP,AU,CF,CU,FG,FU,HC,MA,OI,RB,SA,SM,SP | ok       |   1744 |         |
|    20220906 |  20221006 | AP,AU,CF,CU,FG,FU,HC,MA,OI,RB,SA,SM,SP | ok       |   1527 |         |
|    20221007 |  20221106 | AP,AU,CF,CU,FG,FU,HC,MA,OI,RB,SA,SM,SP | ok       |   1719 |         |
|    20221107 |  20221207 | AP,AU,CF,CU,FG,FU,HC,MA,OI,RB,SA,SM,SP | ok       |   1952 |         |
|    20221208 |  20221231 | AP,AU,CF,CU,FG,FU,HC,MA,OI,RB,SA,SM,SP | ok       |   1412 |         |

## 结论

- 本阶段结论：`stage080_member_rank_backfill_coverage_ready_for_signal_audit`。
- 是否进入下一步：只有 `coverage_ready_for_signal_audit=True` 时，才进入下一阶段信号方向/OOS 审计；本阶段不进入规则/proxy/真引擎。
- 下一步：若覆盖达标，冻结补数源哈希并做会员排名特征方向审计；若不达标，关闭会员排名历史 selector。

## 过拟合反思

- 运行前判断：否；只补可见历史输入，不按坏窗口调规则。
- 运行后判断：若后续只因 2022 左尾表现好而定制阈值，会过拟合；必须做跨年、跨品种、OOS 稳定性。
- 原因：补数解决的是输入缺失，不自动证明信号有预测力。

## 继续价值反思

- 运行前判断：有；Stage079 已定位主要缺口在 2022。
- 运行后判断：看覆盖结果决定；覆盖达标则有继续审计价值。
- 原因：会员排名是外生 PIT 源，若能补齐左尾，比继续扫内部阈值更有研究价值。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage080 覆盖变化和下一步边界。
- 是否更新 `research/registry.md`：是，最新关键阶段推进到 Stage080。
- 是否追加根目录 `memory.md/back_log.md`：仅追加 `back_log.md` 重要摘要，不改 `memory.md`。
