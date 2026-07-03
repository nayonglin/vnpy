# Stage009 Meta-label 入场质量审计

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T04:21:47
- 阶段性质：只读元标签/入场质量审计；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否；本阶段不跑资金曲线，只决定是否值得进入下一步路径代理/真实引擎

## 外部调研与判断

- 参考资料：Lopez de Prado / Hudson & Thames meta-labeling、trend-following right-tail/risk sizing 资料、pysystemtrade capital/risk overlay 资料。
- 我的判断：AI/元标签更适合判断“主策略信号是否值得加风险”，但必须只用入场前可见字段，并通过跨年/多起点稳定性验证。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage009_meta_label_entry_quality_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage009_meta_label_entry_quality_audit.py`
- 新增参数：`MIN_ENTRY_DATE=2020-01-01`、`BIG_WINNER_R=6.0`、`BAD_PATH_R=-1.0`、`BAD_PATH_MAE_R=3.0`、`MIN_EVENT_COUNT=80`、`MIN_YEAR_COUNT=4`、`MIN_MEAN_PNL_LIFT=1.25`、`MAX_BAD_PATH_RATE_DELTA_PP=5.0`
- 修改参数：无
- 删除参数：无

## 审计口径

- 输入：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage019_stage018_regime_gate_failure_attribution/rebuilt_c9_stage019_stage018_regime_gate_failure_attribution_stage013_rebuilt_closed_lots_stage019_stage018_regime_gate_failure_attribution_v1.csv`
- 样本：2020+、AI rank 可见、`flat_entry`、risk/R 可计算的 Stage013 closed lots。
- 标签：`realized_pnl`、`r_multiple`、`big_winner`、`bad_path`；标签仅用于审计，不直接作为交易规则。

## 样本结果

```json
{
  "event_count": 2867,
  "year_count": 7,
  "source_start_month_count": 17,
  "product_count": 19,
  "total_pnl": 63275301.40000001,
  "mean_pnl": 22070.213254272763,
  "winner_rate_pct": 44.436693407743284,
  "big_winner_rate_pct": 9.347750261597488,
  "bad_path_rate_pct": 36.69340774328567
}
```

## 稳定候选

| condition                                  |   event_count |   year_count |   positive_year_count |   total_pnl |   mean_pnl_lift |   big_winner_rate_lift |   bad_path_rate_delta_pp | stable_quality_candidate   |
|:-------------------------------------------|--------------:|-------------:|----------------------:|------------:|----------------:|-----------------------:|-------------------------:|:---------------------------|
| ai_rank_1_8_and_selected_volume_gt1        |          1414 |            7 |                     7 | 6.03914e+07 |          1.9352 |                 1.3542 |                  -0.2719 | True                       |
| ai_rank_1_8_active_lt3_selected_volume_gt1 |          1263 |            7 |                     6 | 4.95755e+07 |          1.7785 |                 1.279  |                   0.5196 | True                       |
| ai_rank_1_8_and_account_healthy            |          1137 |            7 |                     6 | 3.54618e+07 |          1.4132 |                 1.3831 |                   0.2459 | True                       |
| ai_rank_1_6                                |          1571 |            7 |                     6 | 4.86993e+07 |          1.4046 |                 1.035  |                   3.1538 | True                       |
| selected_volume_gt1                        |          2045 |            7 |                     7 | 6.28394e+07 |          1.3923 |                 1.1979 |                  -0.8499 | True                       |
| ai_rank_1_8                                |          2067 |            7 |                     7 | 6.06544e+07 |          1.3296 |                 0.9678 |                   0.2684 | True                       |
| ai_rank_1_8_and_trend_aligned              |          2067 |            7 |                     7 | 6.06544e+07 |          1.3296 |                 0.9678 |                   0.2684 | True                       |
| ai_rank_1_8_active_lt3_account_healthy     |          1021 |            7 |                     6 | 2.98613e+07 |          1.3252 |                 1.3307 |                   2.0921 | True                       |
| ai_rank_1_8_and_rsi_follow                 |          1750 |            7 |                     6 | 5.01253e+07 |          1.2978 |                 0.8925 |                  -1.7791 | True                       |

## 结论

- 本阶段结论：`stage009_has_stable_quality_candidates_need_path_proxy`
- 原因：存在跨年稳定的点时质量条件，但本阶段只是 closed-lot 元标签审计；下一步只能先做代理路径或冻结真实引擎 A/B，不能直接上线。
- 是否进入下一步：若有稳定候选，只允许选一个冻结候选做路径代理或真实引擎 A/B；若无稳定候选，停止该元标签条件集合。

## 过拟合反思

- 运行前判断：有风险。closed-lot 标签天然使用事后收益；本阶段只把它当元标签审计，不直接交易化，且条件集合预声明、禁止产品/日期黑名单。
- 运行后判断：有风险但本阶段可控。发现的稳定候选来自 closed-lot 元标签，不能直接上线；若下一步只冻结一个候选做路径代理/真实引擎，风险可控。
- 原因：本阶段条件固定且只读；后续若按结果继续调 topN、rank、阈值、产品、方向或年份就是过拟合。

## 继续价值反思

- 运行前判断：有价值。用户目标要求 AI 识别超高质量信号并加风险，必须先判断点时字段是否有跨年稳定的正向质量信息。
- 运行后判断：有价值。存在跨年稳定的点时质量候选，值得进入下一步冻结路径代理；但不能继续调 rank/topN 或叠产品方向过滤。
- 原因：只有稳定质量候选能进入下一步；否则应转更外生信息源或账户层结构。

## 输出文件

- quality_events: `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage009_meta_label_entry_quality_audit/rebuilt_c9_v2_stage009_meta_label_entry_quality_audit_quality_events_stage009_meta_label_entry_quality_audit_v1.csv.gz`
- condition_summary: `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage009_meta_label_entry_quality_audit/rebuilt_c9_v2_stage009_meta_label_entry_quality_audit_condition_summary_stage009_meta_label_entry_quality_audit_v1.csv`
- year_summary: `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage009_meta_label_entry_quality_audit/rebuilt_c9_v2_stage009_meta_label_entry_quality_audit_year_summary_stage009_meta_label_entry_quality_audit_v1.csv`
- chart: `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage009_meta_label_entry_quality_audit/rebuilt_c9_v2_stage009_meta_label_entry_quality_audit_condition_quality_chart_stage009_meta_label_entry_quality_audit_v1.png`
- report: `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage009_meta_label_entry_quality_audit/rebuilt_c9_v2_stage009_meta_label_entry_quality_audit_report_stage009_meta_label_entry_quality_audit_v1.md`
- decision: `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage009_meta_label_entry_quality_audit/rebuilt_c9_v2_stage009_meta_label_entry_quality_audit_decision_stage009_meta_label_entry_quality_audit_v1.json`
