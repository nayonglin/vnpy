# Stage024 - 因果高波动 regime 暂停新开仓真实引擎候选

## 变更时间

- 2026-07-01T15:40:18 CST

## 是否重要突破版本

- 否。独立研究 profile，未改官方线上 C9/15w。

## 本次版本改动内容

- 新增工具：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage024_causal_high_vol_pause_engine.py`
- 新增独立策略类：`QmtRollPortfolioStrategyStage024CausalHighVolPause`
- 只在前一交易日因果 regime 为 `high_vol_high_eff` 时暂停新的 `flat_entry`，不强平已有仓位。

## 新增参数

- `enable_stage024_regime_pause_gate=True`
- `stage024_pause_target_regimes=high_vol_high_eff`

## 修改参数

- 无。官方线上配置未改。

## 删除参数

- 无。

## 新增回测结果

- 正收益起点：`17/17`
- 期末收益最小/中位/最大：`1.9011% / 232.0954% / 10189.7746%`
- 最大回撤最差：`-44.0955%`
- Sharpe 最小/中位：`0.2860 / 1.2722`
- 严格任意结束日 `>1` 年负窗口：`298012`
- 严格最差收益：`-44.0955%`
- 到 `2026-06-30` 负窗口：`0`
- 80% 收益保留：`17/17`
- 暂停事件：`156`
- 减少手数：`13576`

## 修改回测结果

- 无。

## 删除回测结果

- 无。

## 交易成本指标

- 总滑点、总交易次数、胜率见 summary 输出；本阶段不新增成本模型。

## 调研与判断结论

- 调研结论：regime filter 有理论依据，但容易错杀趋势右尾；必须以收益保留为硬门。
- 判断结论：`stage024_not_promoted`。

## 过拟合与继续价值反思

- 运行前是否过拟合：否。规则只来自 Stage023 的候选前兆并做因果化，不按品种/日期/source 调整。
- 运行前是否有价值继续：有。该阶段验证坏环境前兆是否能真实改变 holding PnL 路径。
- 运行后是否过拟合：否。本阶段没有用结果反调阈值；若继续在同类 regime 上扫参会过拟合。
- 运行后是否有价值继续：有限。若失败，下一步应转向新的外生信息源或重新审计右尾错杀，而不是继续调 regime 分位。

## 后续规划和 TODO

- 若收益保留失败或负窗口未清零，不晋级，不继续扫同类 regime 阈值。
- 若有局部改善，下一步只能做更强因果稳定性和右尾错杀归因。

## 输出文件

- `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage024_causal_high_vol_pause_engine/rebuilt_c9_stage024_causal_high_vol_pause_engine_report_stage024_causal_high_vol_pause_engine_v1.md`
- `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage024_causal_high_vol_pause_engine/rebuilt_c9_stage024_causal_high_vol_pause_engine_decision_stage024_causal_high_vol_pause_engine_v1.json`
- `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage024_causal_high_vol_pause_engine/rebuilt_c9_stage024_causal_high_vol_pause_engine_performance_chart_stage024_causal_high_vol_pause_engine_v1.png`
- `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage024_causal_high_vol_pause_engine/rebuilt_c9_stage024_causal_high_vol_pause_engine_goal_audit_chart_stage024_causal_high_vol_pause_engine_v1.png`
