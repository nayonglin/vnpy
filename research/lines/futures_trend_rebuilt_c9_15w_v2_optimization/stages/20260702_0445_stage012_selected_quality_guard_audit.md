# Stage012 Selected Quality Guard Audit

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T04:40:51
- 阶段性质：只读 guard 审计；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否；本阶段只决定是否值得进入路径 proxy/真实引擎

## 外部调研与判断

- 参考资料：Lopez de Prado / Hudson & Thames meta-labeling、trend-following right-tail/risk sizing、pysystemtrade capital/risk overlay。
- 我的判断：Stage010 的高质量加风险方向值得继续，但 guard 必须只用入场前可见状态，且不能产品/方向/日期黑名单化。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage012_selected_quality_guard_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage012_selected_quality_guard_audit.py`
- 新增参数：`MIN_RETAINED_COUNT=500`、`MIN_YEAR_COUNT=5`、`MIN_RETAINED_TOTAL_PNL_SHARE_PCT=80.0`、`MIN_FOCUS_PROXY_IMPROVEMENT=1.0`
- 修改参数：无
- 删除参数：无

## 结果

- Stage010 selected lots：`1414`
- focus selected lots：`43`
- selected total PnL：`60391409.40`
- focus proxy delta：`-276692.50`
- candidate guard 数：`0`
- 决策：`stage012_no_stable_generic_guard_candidate_keep_readonly`
- 原因：没有通用 PIT guard 同时满足保留收益、跨年正贡献、focus proxy 改善和非正 excluded PnL。

## 候选 guard

_无数据_

## guard 总表

| guard_name                          |   excluded_count |   excluded_total_pnl |   retained_total_pnl |   retained_total_pnl_share_pct |   retained_positive_year_count |   focus_proxy_delta_before_guard |   focus_proxy_delta_after_guard |   focus_proxy_delta_improvement | candidate_for_true_engine_audit   |
|:------------------------------------|-----------------:|---------------------:|---------------------:|-------------------------------:|-------------------------------:|---------------------------------:|--------------------------------:|--------------------------------:|:----------------------------------|
| exclude_risk_multiplier_ge2         |              511 |     424282           |          5.99671e+07 |                        99.2974 |                              7 |                          -276692 |                          136632 |                        413325   | False                             |
| exclude_rsi_extreme_follow          |              441 |          1.53036e+07 |          4.50879e+07 |                        74.6594 |                              7 |                          -276692 |                           57155 |                        333848   | False                             |
| exclude_loss_streak_gt0             |              878 |          5.50805e+07 |          5.31088e+06 |                         8.7941 |                              4 |                          -276692 |                          -93465 |                        183228   | False                             |
| exclude_entry_risk_distance_gt2pct  |              218 |          8.32341e+06 |          5.2068e+07  |                        86.2176 |                              7 |                          -276692 |                         -218522 |                         58170   | False                             |
| exclude_active_ge2_and_rsi_extreme  |              190 |          1.38561e+07 |          4.65353e+07 |                        77.0562 |                              7 |                          -276692 |                         -273070 |                          3622.5 | False                             |
| exclude_trend_not_aligned           |                0 |          0           |          6.03914e+07 |                       100      |                              7 |                          -276692 |                         -276692 |                             0   | False                             |
| exclude_high_entry_risk_and_corr    |              129 |          4.24454e+06 |          5.61469e+07 |                        92.9716 |                              7 |                          -276692 |                         -286098 |                         -9405   | False                             |
| exclude_rsi_not_directional_follow  |              196 |          1.04252e+07 |          4.99662e+07 |                        82.7372 |                              6 |                          -276692 |                         -287395 |                        -10702.5 | False                             |
| exclude_active_ge3_and_corr_present |              143 |          9.43956e+06 |          5.09519e+07 |                        84.3694 |                              6 |                          -276692 |                         -349368 |                        -72675   | False                             |
| exclude_active_positions_ge3        |              151 |          1.0816e+07  |          4.95755e+07 |                        82.0902 |                              6 |                          -276692 |                         -349368 |                        -72675   | False                             |
| exclude_account_drawdown_ge20       |              389 |          2.5023e+07  |          3.53684e+07 |                        58.5654 |                              6 |                          -276692 |                         -484382 |                       -207690   | False                             |
| exclude_breakout_false              |              866 |          5.39346e+07 |          6.4568e+06  |                        10.6916 |                              3 |                          -276692 |                         -504898 |                       -228205   | False                             |
| exclude_same_direction_corr_present |              695 |          3.96327e+07 |          2.07587e+07 |                        34.3737 |                              5 |                          -276692 |                         -589442 |                       -312750   | False                             |

## 过拟合反思

- 运行前判断：否。本阶段固定 Stage010 候选，只用预声明 PIT 状态字段，不用产品/方向/日期/坏窗口黑名单。
- 运行后判断：否。本阶段没有继续调阈值或按产品/日期救参；当前 guard 家族未提供足够稳健候选。

## 继续价值反思

- 运行前判断：有价值。Stage011 已经证明 Stage010 候选里存在负拖累簇，必须先确认是否有通用状态能过滤。
- 运行后判断：有限。若无候选，应转向新 PIT 信息源或真实持仓路径，不继续扩展同类 guard。

## 输出文件

- tagged_lots: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage012_selected_quality_guard_audit/rebuilt_c9_v2_stage012_selected_quality_guard_audit_tagged_lots_stage012_selected_quality_guard_audit_v1.csv.gz`
- guard_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage012_selected_quality_guard_audit/rebuilt_c9_v2_stage012_selected_quality_guard_audit_guard_summary_stage012_selected_quality_guard_audit_v1.csv`
- guard_year_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage012_selected_quality_guard_audit/rebuilt_c9_v2_stage012_selected_quality_guard_audit_guard_year_summary_stage012_selected_quality_guard_audit_v1.csv`
- chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage012_selected_quality_guard_audit/rebuilt_c9_v2_stage012_selected_quality_guard_audit_guard_chart_stage012_selected_quality_guard_audit_v1.png`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage012_selected_quality_guard_audit/rebuilt_c9_v2_stage012_selected_quality_guard_audit_decision_stage012_selected_quality_guard_audit_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage012_selected_quality_guard_audit/rebuilt_c9_v2_stage012_selected_quality_guard_audit_report_stage012_selected_quality_guard_audit_v1.md`
