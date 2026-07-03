# Stage037 - 外生/AI 特征资格审计

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01 18:05:33 CST`
- 阶段性质：只读特征资格审计；不做收益回测、不改官方实盘配置、不连接 CTP、不调用订单 API。
- 是否重要突破：`否`
- 是否触发A/B：`否`

## 外部调研与判断

- CFA commodity ML 资料强调商品 ML 应使用 momentum、basis、carry、skewness、open interest 等 theory-grounded 特征，并持续做成本和可交易性审计。
- Fuertes/Miffre/Fernandez-Perez 商品策略研究说明 momentum、term structure 和 idiosyncratic volatility 不完全重叠，组合前应先验证独立信息源。
- CME open interest 教育资料说明 OI 可用于确认趋势强弱，但不是单独交易信号。
- GitHub `Machine-Learning-on-Futures` 说明中国商品期货机器学习可以用 Wind/商品特征，但这类数据必须先解决点时化和授权/覆盖问题。
- 我的判断：当前不能继续扫风险门槛；下一步应该先确认哪些特征可以合法接入当前重建 C9 的 AI/候选流。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage037_feature_eligibility_audit.py`
- 新增测试：`tests/test_rebuilt_c9_stage037_feature_eligibility.py`
- 修改正式策略脚本：无
- 删除脚本：无
- 新增参数：`MIN_FORWARD_RUNS=20`、`MIN_FORWARD_DATES=20`、`MIN_HISTORY_COVERAGE_RATIO=0.8`
- 修改参数：无正式参数修改。

## 结果

- 决策：`stage037_feature_eligibility_audit_complete_no_trade_rule`
- history selector ready：`stage182_ai_pool_rank_score, oi_price_confirm_fields, account_state_fields`
- forward monitor only：`pairwise_selection_features, basis_inventory_forward_ledger, sentiment_manual_event_ledger, jd_full_market_monthly_evidence`
- post-entry confirmation only：`post_entry_first_minute_quality`
- jd 结论：`jd_not_shared_ai_ready`
- 外生 ledger：`3` runs / `2` received dates，未达 `20/20`，不得历史回填做 selector。
- 订单/CTP API：`0`

## 结论

- 当前能继续做的是“当前 C9 候选级 PIT 特征矩阵 + 只读预测力审计”，不是直接上新交易规则。
- `jd.DCE` 仍不能直接进入共享 AI 池；只能保留为非挤占观察或等新证据。
- basis/inventory/sentiment 只能 forward monitor，不能历史收益回测。
- 开仓后早段质量标签只能做确认层，不能作为入场前 AI 选品特征。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage037_feature_eligibility_audit/rebuilt_c9_stage037_feature_eligibility_audit_report_stage037_feature_eligibility_audit_v1.md`
- feature registry：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage037_feature_eligibility_audit/rebuilt_c9_stage037_feature_eligibility_audit_feature_registry_stage037_feature_eligibility_audit_v1.csv`
- artifact inventory：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage037_feature_eligibility_audit/rebuilt_c9_stage037_feature_eligibility_audit_artifact_inventory_stage037_feature_eligibility_audit_v1.csv`
- candidate coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage037_feature_eligibility_audit/rebuilt_c9_stage037_feature_eligibility_audit_candidate_column_coverage_stage037_feature_eligibility_audit_v1.csv`
- external summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage037_feature_eligibility_audit/rebuilt_c9_stage037_feature_eligibility_audit_external_ledger_summary_stage037_feature_eligibility_audit_v1.csv`
- jd summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage037_feature_eligibility_audit/rebuilt_c9_stage037_feature_eligibility_audit_jd_summary_stage037_feature_eligibility_audit_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage037_feature_eligibility_audit/rebuilt_c9_stage037_feature_eligibility_audit_decision_stage037_feature_eligibility_audit_v1.json`

## 过拟合反思

- 运行前判断：否。本阶段只做特征资格和点时边界审计，不根据收益挑规则。
- 运行后判断：否。但若下一步拿 shallow forward ledger 或 future labels 回填训练，就是严重过拟合/泄漏。

## 继续价值反思

- 运行前判断：有。用户目标要求 AI 选品优化、鸡蛋和高质量信号，必须先确认特征是否合法可接。
- 运行后判断：有。下一步应做候选级 PIT feature matrix，而不是写交易规则。

## 后续规划

- Stage038 建议：构建当前重建 C9 的候选级 PIT feature matrix，只读评估 AI rank/score、OI/volume、account state、simple trend、full-market rank 的预测力和稳定性；不得用 post-entry 标签或 external forward ledger 做入场前训练。
