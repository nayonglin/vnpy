# Stage058 - 连续风险预算 proxy 审计

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01T22:00:20 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读 proxy 审计，不改官方实盘配置。
- 是否重要突破：`否`
- 是否触发A/B：`否`

## 外部调研与判断

- 参考资料：pysystemtrade/Rob Carver forecast scaling、time-series momentum volatility scaling、trend-following position sizing / target volatility 资料。
- 我的判断：Stage057 已反证硬 cap，Stage058 只审计连续预算是否同时有压力减亏和全样本收益保留，不直接写交易规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage058_continuous_budget_proxy_audit.py`
- 新增测试：`tests/test_rebuilt_c9_stage058_continuous_budget_proxy.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：无交易参数；proxy 固定审计 `quality_linear_floor25/50`、`quality_recovery_floor75`、`quality_top8_recovery_floor`。
- 修改参数：无。
- 删除参数：无。

## 结果

- 决策：`stage058_continuous_budget_proxy_no_variant_passed_keep_readonly`。
- 通过 proxy gate 的 variant：`0`。
- 最优 variant：`quality_linear_floor25`。
- 最优 pressure delta PnL：`132501.90`。
- 最优 full retention：`64.9748%`。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage058_continuous_budget_proxy_audit/rebuilt_c9_stage058_continuous_budget_proxy_audit_report_stage058_continuous_budget_proxy_audit_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage058_continuous_budget_proxy_audit/rebuilt_c9_stage058_continuous_budget_proxy_audit_summary_stage058_continuous_budget_proxy_audit_v1.csv`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage058_continuous_budget_proxy_audit/rebuilt_c9_stage058_continuous_budget_proxy_audit_chart_stage058_continuous_budget_proxy_audit_v1.png`

## 过拟合反思

- 运行前判断：否。Stage058 只做固定 proxy 审计，不按结果调 TopN、手数、品种或阈值。
- 运行后判断：否。本阶段没有调参，也没有进入真引擎；若根据结果微调 floor/分层才会过拟合。

## 继续价值反思

- 运行前判断：有。Stage057 后需要验证连续预算方向是否比硬 cap 更有生命力。
- 运行后判断：有限。连续预算方向仍有机制价值，但本批固定 proxy 不能直接进入真引擎。
