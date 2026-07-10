# Stage004 全市场 AI active top quartile + 有效风险 0.02 真实引擎

- line_id：`futures_trend_full_market_ai_filter_002risk`
- 当前模式：`day`
- 记录时间：`2026-07-09 21:28 CST`
- 阶段性质：独立研究线最小 A/C 真实引擎回测
- 是否重要突破：否，Stage001/003 失败后的低自由度中间选择器验证
- 是否触发A/B：是，A=官方 C9/15w；C=active full-market top quartile + risk_ratio_* 0.02 + OI restore disabled

## 本次变更

- 新增脚本：`research/lines/futures_trend_full_market_ai_filter_002risk/tools/stage004_top_quartile_effective_risk_cap_engine.py`
- 新增参数：`TOP_SELECTION_QUANTILE=0.25`、`MIN_ACTIVE_PRODUCTS_FOR_SELECTION=12`、`enable_oi_price_confirm_risk_restore=False`、`oi_price_confirm_risk_restore_multiplier=1.0`
- 修改参数：AI eligibility 从 Stage003 broad-veto 改为 active top quartile；继续关闭 OI confirm 风险恢复，保持有效风险 `0.02`。
- 删除参数：删除 broad-veto 允许池，删除 OI confirm restore 对本候选的加风险效果。

## 回测参数

- 数据区间：`2020-01-01` 到 `2026-06-30`
- 账户规模：`150,000`
- 成本口径：沿用 C9 真实引擎原成本/slippage 配置。

## 结果

- A 期末权益：`5,979,281.00`；总收益 `3886.1873%`；最大回撤 `-55.3701%`；Sharpe `1.3959`
- C 期末权益：`568,439.20`
- C 总收益：`278.9595%`
- C 最大回撤：`-66.3656%`
- C Sharpe：`0.7040`
- C 总滑点：`78,600.00`
- C 总交易次数：`758`
- C 胜率：`49.2237%`，口径为非零交易日胜率，不是逐笔胜率。
- C 最大 broker10 保证金/权益：`98.5545%`
- C 相对 A 收益差：`-3607.2279` 百分点；回撤差：`-10.9955` 百分点。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage004_top_quartile_effective_risk_cap_engine/full_market_ai002_stage004_top_quartile_effective_risk_cap_engine_report_stage004_top_quartile_effective_risk_cap_engine_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage004_top_quartile_effective_risk_cap_engine/full_market_ai002_stage004_top_quartile_effective_risk_cap_engine_ac_summary_stage004_top_quartile_effective_risk_cap_engine_v1.csv`
- eligibility：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage004_top_quartile_effective_risk_cap_engine/full_market_ai002_stage004_top_quartile_effective_risk_cap_engine_eligibility_stage004_top_quartile_effective_risk_cap_engine_v1.csv`
- feature_panel：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage004_top_quartile_effective_risk_cap_engine/full_market_ai002_stage004_top_quartile_effective_risk_cap_engine_feature_panel_stage004_top_quartile_effective_risk_cap_engine_v1.csv.gz`
- daily：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage004_top_quartile_effective_risk_cap_engine/full_market_ai002_stage004_top_quartile_effective_risk_cap_engine_candidate_daily_stage004_top_quartile_effective_risk_cap_engine_v1.csv.gz`
- risk_restore_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage004_top_quartile_effective_risk_cap_engine/full_market_ai002_stage004_top_quartile_effective_risk_cap_engine_risk_restore_audit_stage004_top_quartile_effective_risk_cap_engine_v1.csv`

## 结论

- 本阶段结论：`stage004_stop_or_attribution_before_more_runs`
- 是否进入下一步：不进入逐半年多周期；收益保留率仅 `7.1782%`，明显破坏 A 的收益。
- 下一步：若仍明显失败，停止 full-market score-only selector 方向，只做失败归因。

## 过拟合反思

- 运行前判断：中等。top quartile 是自然分位，不是 topN 扫描，但属于失败后的中间形状验证。
- 运行后判断：中等偏高。虽然不是小数扫描，但在 Stage001/003 失败后继续沿同一 score-only selector 方向，收益保留只有 `7.1782%`，继续救参会过拟合。

## 继续价值反思

- 运行前判断：有价值，因为它验证 top8 过窄与 broad-veto 过宽之间是否存在低自由度中间解。
- 运行后判断：作为候选推进无价值；作为失败归因有价值。

## 独立 Agent Review

- review 时间：`2026-07-09 21:40 CST`
- reviewer：独立 agent `019f4711-4943-7853-9d6f-82238f978122`
- review 结论：无 P0。没有发现让 Stage004 结果整体失效的实现错误、AI 未接入、同日泄漏或 summary 计算错误。
- P1：不建议进入逐半年多周期。C 收益保留率只有 `278.9595 / 3886.1873 = 7.1782%`，最大回撤从 A 的 `-55.3701%` 恶化到 `-66.3656%`，Sharpe 从 `1.3959` 降到 `0.7040`。按“不能明显破坏 A 的收益/路径”原则，单起点已经失败。
- P2：Stage004 不是全程严格 top quartile。前两个 `eval_date` 因 `data_available_count < 12` 走 `cold_start_neutral_all_pass`，57 个品种全放行；从 `2020-03-31` 起才是 active available 集自然 top quartile。该点不构成泄漏，但结论描述需带上 cold-start 例外。
- 审查细节：Stage004 确认是 active full-market PIT top quartile，不是 Stage003 broad-veto 残留；warmup 后 `selected_count = ceil(data_available_count * 0.25)`，复算无 selection mismatch。
- PIT/接线：`signal_date >= candidate_date` 为 `0`，最小 lag 为 `1` 天；entry_candidates 共 `2447` 行，AI enabled `2447`，allowed `593`，blocked `1854`，opened `352`；`allowed but not in eligibility key = 0`，`blocked but key exists = 0`，`opened but not allowed = 0`。
- 风险审计：entry_risk `371` 行和 entry_candidates `2447` 行均为 `risk_ratio_min=max=0.02`、`risk_multiplier_min=max=1.0`、`oi_restore_enabled/applied=0`。
- reviewer 置信度：高，约 `0.88`。主要保留项是旧 feature 文件生成过程未逐行追溯，但 Stage004 实际加载的旧特征列不包含 `future_*`，且入场生效日审计通过。
- review 后决策：不进入逐半年多周期；停止 full-market score-only selector 候选推进。若继续，只做失败归因或换成结构不同的 selector，不继续救 topN/分位。
