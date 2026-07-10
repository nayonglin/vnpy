# Stage002 全市场 PIT AI 底部四分位 veto + 0.02 基础风险真实引擎

- line_id：`futures_trend_full_market_ai_filter_002risk`
- 当前模式：`day`
- 记录时间：`2026-07-09 19:26 CST`
- 阶段性质：独立研究线最小 A/C 真实引擎回测
- 是否重要突破：否，Stage001 失败后的结构性修正验证
- 是否触发A/B：是，A=官方 C9/15w；C=全市场 PIT AI 底部四分位 veto + risk_ratio_* 0.02

## 外部调研与判断

- 参考资料：Time-series momentum、cross-sectional momentum、ML ranking 与 meta-labeling 资料。
- 我的判断：趋势策略收益来自稀疏右尾，过窄 top8 容易砍掉未来赢家；更合理的第一步是只 veto 最差候选，保留主策略分散化。

## 本次变更

- 新增脚本：`research/lines/futures_trend_full_market_ai_filter_002risk/tools/stage002_full_market_ai_bottom_quartile_veto_engine.py`
- 新增参数：`BOTTOM_VETO_QUANTILE=0.25`、`MIN_ACTIVE_PRODUCTS_FOR_VETO=12`
- 修改参数：AI eligibility 从 Stage001 top8 改为底部四分位 veto；`risk_ratio_*` 继续固定 `0.02`；full-market 57 品种 universe 不变。
- 删除参数：删除 Stage001 的硬 top8 允许池；不恢复固定卫星品种。

## 回测/归因参数

- 数据区间：`2020-01-01` 到 `2026-06-30`
- 账户规模：`150,000`
- 成本口径：沿用 C9 真实引擎原成本/slippage 配置。
- 策略/归因口径：A 复用 Stage167 官方 C9/15w 曲线；C 新跑真实引擎。

## 结果

- A 期末权益：`5,979,281.00`；总收益 `3886.1873%`；最大回撤 `-55.3701%`；Sharpe `1.3959`
- C 期末权益：`106,927.80`
- C 总收益：`-28.7148%`
- C 最大回撤：`-94.4881%`
- C Sharpe：`0.2625`
- C 总滑点：`134,940.00`
- C 总交易次数：`1,530`
- C 胜率：`49.1713%`，口径为非零交易日胜率，不是逐笔胜率。
- C 最大 broker10 保证金/权益：`180.3479%`
- C 相对 A 收益差：`-3914.9021` 百分点；回撤差：`-39.1180` 百分点。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage002_full_market_ai_bottom_quartile_veto_engine/full_market_ai002_stage002_full_market_ai_bottom_quartile_veto_engine_report_stage002_full_market_ai_bottom_quartile_veto_engine_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage002_full_market_ai_bottom_quartile_veto_engine/full_market_ai002_stage002_full_market_ai_bottom_quartile_veto_engine_ac_summary_stage002_full_market_ai_bottom_quartile_veto_engine_v1.csv`
- eligibility：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage002_full_market_ai_bottom_quartile_veto_engine/full_market_ai002_stage002_full_market_ai_bottom_quartile_veto_engine_eligibility_stage002_full_market_ai_bottom_quartile_veto_engine_v1.csv`
- feature_panel：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage002_full_market_ai_bottom_quartile_veto_engine/full_market_ai002_stage002_full_market_ai_bottom_quartile_veto_engine_feature_panel_stage002_full_market_ai_bottom_quartile_veto_engine_v1.csv.gz`
- daily：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage002_full_market_ai_bottom_quartile_veto_engine/full_market_ai002_stage002_full_market_ai_bottom_quartile_veto_engine_candidate_daily_stage002_full_market_ai_bottom_quartile_veto_engine_v1.csv.gz`
- quality：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage002_full_market_ai_bottom_quartile_veto_engine/full_market_ai002_stage002_full_market_ai_bottom_quartile_veto_engine_ai_usage_audit_stage002_full_market_ai_bottom_quartile_veto_engine_v1.csv`

## 结论

- 本阶段结论：`stage002_stop_or_attribution_before_more_runs`
- 是否进入下一步：等待独立 agent review 后决定。
- 下一步：若 review 通过且 C 明显优于 Stage001，再考虑逐半年多周期；否则做更深归因。

## 过拟合反思

- 运行前判断：中等。底部四分位是常见低自由度结构，但仍源自 Stage001 失败归因。
- 运行后判断：等待独立 review；本阶段没有扫分位、topN、窗口或权重。
- 原因：只验证一个结构性假设：AI 应先做 veto，而不是硬 top8。

## 继续价值反思

- 运行前判断：有价值，因为它正面修正 Stage001 的过窄过滤问题。
- 运行后判断：等待独立 review。
- 原因：单起点仍只是第一关。

## 独立 Agent Review

- review 时间：`2026-07-09 19:55 CST`
- reviewer：独立 agent `019f46a0-fc8b-7be2-8ead-7d54ed834915`
- review 结论：未发现 P0 级接线/统计 bug；Stage002 结果可信地反映策略形状失败，不是 AI eligibility 未读到、`risk_ratio` 未生效或 summary 算错。
- P1：不建议继续多周期验证。C 候选期末权益 `106,927.80`，总收益 `-28.7148%`，最大回撤 `-94.4881%`，Sharpe `0.2625`，broker10 margin/equity 最大 `180.3479%`；相对 A 官方 C9/15w 的 `5,979,281.00 / 3886.1873% / -55.3701% / Sharpe 1.3959` 是明显失败。
- P2：`bottom 25% veto` 实际是对 `data_available=1` 的 active products 做底部四分位 veto；最新月 `2026-06-30` 为 `57` 总品种、`54` 可用、`41` selected、`13` veto，另 `3` 个因不可用不在允许池，后续表述应写成 active full-market PIT bottom quartile veto。
- P2：`risk_ratio` 全量为 `0.02`，但仍继承 C9 的 `oi_price_confirm_restore`，entry_candidates 中 `923/2434` 行、entry_risk 中 `314/743` 行 `risk_multiplier=2.0`；因此不能把本阶段解释为所有入场有效风险都严格只有 `2%`。
- reviewer 置信度：高。已复算 daily/curves summary，确认 `end_equity`、总收益、最大回撤、Sharpe、slippage、trade_count、broker10 max 与 summary 一致；AI allowed/blocked 与 eligibility key 匹配，blocked opened rows 为 `0`。
- review 后决策：停止 Stage002 多周期扩展；若继续优化，优先验证 `0.02` 有效风险上限与 OI restore 叠加问题，而不是扫 veto 分位、窗口或权重。
